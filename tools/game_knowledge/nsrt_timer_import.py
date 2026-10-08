#!/usr/bin/env python3
"""Extract boss-ability timer data from NorthernSkyRaidTools' EncounterAlerts Lua files.

    python tools/game_knowledge/nsrt_timer_import.py \\
      --addon-dir "E:/World of Warcraft/_retail_/Interface/AddOns/NorthernSkyRaidTools" \\
      --pack MidnightS2 --zone venomous-abyss \\
      # -> data/raid/12_1/venomous_abyss/<nn>_<boss>/timers.json

See docs/design/23-boss-timer-dataset.md for the full spec this implements.

Why not a real Lua interpreter: the files in EncounterAlerts/<pack>/*.lua are extremely
regular -- a sequence of

    local data = { <table literal, possibly nested> }
    self:AddEncounterAlert(data)

wrapped in one big `NSI.InitializeAlerts[encID] = function(self) ... end`, plus unrelated
addon plumbing (event handlers, macros, UI helper functions) before/after/between those
pairs that we don't care about and never attempt to parse structurally. So instead of a
full Lua grammar this module has:

  1. A tokenizer (`tokenize`) that is a *complete* lexer -- it must correctly delimit every
     string, long-bracket string (`[[...]]` / `[=[...]=]`, which can itself contain braces,
     brackets and even full Lua source, e.g. embedded `func = [[return function() ... end]]`
     option-panel callbacks), comment (line and long-bracket) and number in the file, even
     though most of what it produces is never semantically interpreted.
  2. A single left-to-right scan of the resulting token stream (`extract_locals_and_alerts`)
     that recognises exactly two patterns anchored at each position -- `local IDENT = <value>`
     (captured into a `locals` table, exactly mirroring Lua's own top-to-bottom scoping so a
     `local data = {...}` immediately followed by `self:AddEncounterAlert(data)` sees the
     right table, and so `encID = encID` / `dur = bombDuration`-style bare-identifier field
     values resolve against locals defined earlier in the same file) and
     `self:AddEncounterAlert(data)` (which reads back whatever `data` currently holds and
     emits it as one alert). Everything else -- `if`/`for`/`function...end` bodies, other
     local declarations, method calls -- is walked token-by-token without being structurally
     parsed at all; since neither trigger pattern can appear *inside* an expression we do not
     otherwise recurse into, walking past it one token at a time is sufe and correct.
  3. A recursive table-literal reader (`parse_table` / `parse_value`) used only when a trigger
     fires, handling nested tables, `[key] = value` and positional (`{a, b, c}`) fields,
     trailing commas, and Lua's `nil`/`true`/`false`, all per the traps section of the design
     doc. A value that isn't a literal, a nested table, or a resolvable local/indexed-local
     reference is recorded as an `Unresolved(raw=...)` marker rather than crashing; callers
     turn that into `null` plus an entry in the ability's `unresolved_fields` dict rather than
     losing the fact that something couldn't be read.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import datalayout as D  # noqa: E402
DEFAULT_ADDON_DIR = "E:/World of Warcraft/_retail_/Interface/AddOns/NorthernSkyRaidTools"

# encID -> slug, seeded from docs/design/00-overview.md's "Seed reality check" and confirmed
# against each file's own `local encID = <n>` declaration while writing this tool.
ENCOUNTER_SLUG_MAP: dict[int, str] = {
    3379: "nymrissa",
    3470: "nekzali",
    3445: "sentinels",
    3455: "vashnik",
    3497: "explorers",
    3420: "sszorak",
    3421: "twinfangs",
    3429: "coiledaltar",
    3492: "ulatek",
}

# Recorded per the acceptance criterion "cross-check at least two encounters' cadences
# against BigWigs ... record agreement or disagreement". Derived by hand from
# BigWigsMods/BigWigs/TheVenomousAbyss (installed locally as the separate
# BigWigs_TheVenomousAbyss addon) on 2026-08-25; see this task's PROGRESS.md entry for the
# short version. BigWigs doesn't ship absolute timestamps at all -- it reacts live to
# Blizzard's own ENCOUNTER_TIMELINE_EVENT_ADDED durations and only hardcodes small "gap"
# tables keyed by (spellId, roundedDuration) -> secondsUntilNext, so the comparison below is
# necessarily about *cadence*, not raw seconds.
CROSS_CHECK_NOTES: list[str] = [
    "BigWigs cross-check (2026-08-25) against the locally installed BigWigs_TheVenomousAbyss "
    "addon, not a source download -- BigWigs has no absolute timers to diff directly, only "
    "duration-keyed gap constants, so cadence (interval between hits) is what's comparable.",
    "AGREE: Vashnik 'TankHits' (Dripping Fangs, spell 1280935), Heroic. NSRT's absolute "
    "timers (10.1, 39.1, 66.1, 94.1, ...) have successive gaps of 27-29s throughout. "
    "Vashnik.lua's gapTimer table hardcodes a flat 29s gap for this spell after both the "
    "pull-duration(~8s) and repeat-duration(~28s) timeline events. The dominant cadence "
    "matches; the 1-2s jitter is expected (BigWigs keys off whole-second-rounded live event "
    "durations, NSRT's dataset carries decimal precision from real logs).",
    "DISAGREE: Nek'zali 'HungeringPyre' (spell 1289855 in NSRT; BigWigs keys the same "
    "ability's gap under spell 1305421 -- a cast-vs-effect spellId split that recurs across "
    "this addon pair and isn't itself a disagreement). NSRT's phaseTimers give the SAME value "
    "(35s into phase 1.5) for BOTH difficulty 15 (Heroic) and difficulty 16 (Mythic). "
    "Nekzali.lua's gapTimer table distinguishes them explicitly: "
    "timersMythic[1305421][1.5] = {[11] = 35} but timersOther[1305421][1.5] = {[11] = 30} -- "
    "BigWigs believes Heroic's gap is 30, not 35. Left as-is per this task's rule (no winner "
    "picked silently); a consumer snapping the timeline editor to NSRT's Heroic value for "
    "this ability should know it may run ~5s ahead of BigWigs' own model.",
]


# --------------------------------------------------------------------------------------
# Lua tokenizer
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    kind: str  # "NUM" | "STR" | "IDENT" | "PUNCT" | "EOF"
    text: str
    value: object = None


_EOF = Token("EOF", "", None)
_NUM_RE = re.compile(r"\d+\.\d+|\d+")
_IDENT_START_RE = re.compile(r"[A-Za-z_]")
_IDENT_CONT_RE = re.compile(r"[A-Za-z0-9_]")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}


def _long_bracket_level(src: str, i: int) -> int | None:
    """If src[i:] opens a long bracket (`[`, `=`*N, `[`), return N; else None."""
    if i >= len(src) or src[i] != "[":
        return None
    j = i + 1
    level = 0
    while j < len(src) and src[j] == "=":
        level += 1
        j += 1
    if j < len(src) and src[j] == "[":
        return level
    return None


def _read_long_bracket(src: str, i: int, level: int) -> tuple[str, int]:
    """Read a long-bracket string/comment body starting at the opening `[`. Returns
    (content, index_after_closer). Lua semantics: content stops at the *first* matching
    closer at this level (no nesting), and a single immediate newline after the opener is
    stripped."""
    start = i + 2 + level
    if start < len(src) and src[start] == "\r":
        start += 1
    if start < len(src) and src[start] == "\n":
        start += 1
    closer = "]" + "=" * level + "]"
    end = src.find(closer, start)
    if end == -1:
        return src[start:], len(src)
    return src[start:end], end + len(closer)


def _read_short_string(src: str, i: int) -> tuple[str, int]:
    quote = src[i]
    j = i + 1
    buf: list[str] = []
    n = len(src)
    while j < n:
        c = src[j]
        if c == "\\" and j + 1 < n:
            buf.append(_ESCAPES.get(src[j + 1], src[j + 1]))
            j += 2
            continue
        if c == quote:
            j += 1
            break
        buf.append(c)
        j += 1
    return "".join(buf), j


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if src.startswith("--", i):
            level = _long_bracket_level(src, i + 2)
            if level is not None:
                _, i = _read_long_bracket(src, i + 2, level)
            else:
                nl = src.find("\n", i + 2)
                i = nl if nl != -1 else n
            continue
        if c == '"' or c == "'":
            text, i = _read_short_string(src, i)
            tokens.append(Token("STR", text, text))
            continue
        if c == "[":
            level = _long_bracket_level(src, i)
            if level is not None:
                text, i = _read_long_bracket(src, i, level)
                tokens.append(Token("STR", text, text))
                continue
            tokens.append(Token("PUNCT", "[", None))
            i += 1
            continue
        if c.isdigit():
            m = _NUM_RE.match(src, i)
            assert m is not None
            text = m.group(0)
            num: float | int = float(text) if "." in text else int(text)
            tokens.append(Token("NUM", text, num))
            i = m.end()
            continue
        if _IDENT_START_RE.match(c):
            j = i + 1
            while j < n and _IDENT_CONT_RE.match(src[j]):
                j += 1
            text = src[i:j]
            tokens.append(Token("IDENT", text, text))
            i = j
            continue
        # Permissive fallback: any other character is its own single-char PUNCT token.
        # We never structurally parse multi-char operators (==, ~=, .., etc.) since the
        # regions that contain them are walked token-by-token without interpretation.
        tokens.append(Token("PUNCT", c, None))
        i += 1
    return tokens


def _at(tokens: list[Token], i: int) -> Token:
    return tokens[i] if 0 <= i < len(tokens) else _EOF


def _is_punct(t: Token, text: str) -> bool:
    return t.kind == "PUNCT" and t.text == text


def _is_kw(t: Token, text: str) -> bool:
    return t.kind == "IDENT" and t.text == text


# --------------------------------------------------------------------------------------
# Lua table-literal reader
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Unresolved:
    """Placeholder for a field value that is a Lua expression we didn't attempt to
    evaluate (a function/method call, an unknown identifier, etc). Carries the raw source
    text so the miss is diagnosable rather than silently losing information."""

    raw: str


LuaScalar = None | bool | int | float | str
LuaTable = dict[int | float | str, "LuaValue"]
LuaValue = LuaScalar | LuaTable | Unresolved

_OPEN_BRACKETS = {"(", "{", "["}
_CLOSE_BRACKETS = {")", "}", "]"}


def _reconstruct_raw(tokens: list[Token], start: int, end: int) -> str:
    return " ".join(tokens[k].text for k in range(start, end))


def _consume_balanced(tokens: list[Token], i: int) -> tuple[str, int]:
    """Consume tokens from i until a `,`/`;` at depth 0, or an unmatched close bracket at
    depth 0 (which is left unconsumed -- it belongs to the enclosing table/call). Used to
    skip past an expression we don't know how to evaluate while still leaving the scan
    position correct for whatever follows."""
    start = i
    depth = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        if t.kind == "PUNCT" and t.text in _OPEN_BRACKETS:
            depth += 1
        elif t.kind == "PUNCT" and t.text in _CLOSE_BRACKETS:
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and t.kind == "PUNCT" and t.text in (",", ";"):
            break
        i += 1
    return _reconstruct_raw(tokens, start, i), i


def _parse_key(tokens: list[Token], i: int) -> tuple[int | float | str, int]:
    """Parse the key expression inside `[ ... ]` (the `[` itself already consumed)."""
    t = _at(tokens, i)
    if _is_punct(t, "-") and _at(tokens, i + 1).kind == "NUM":
        num_tok = _at(tokens, i + 1)
        assert isinstance(num_tok.value, (int, float))
        return -num_tok.value, i + 2
    if t.kind == "NUM":
        assert isinstance(t.value, (int, float))
        return t.value, i + 1
    if t.kind == "STR":
        assert isinstance(t.value, str)
        return t.value, i + 1
    raw, j = _consume_balanced(tokens, i)
    return raw, j


def parse_value(
    tokens: list[Token], i: int, scope: dict[str, LuaValue]
) -> tuple[LuaValue, int]:
    t = _at(tokens, i)
    if _is_punct(t, "{"):
        return parse_table(tokens, i, scope)
    if _is_punct(t, "-") and _at(tokens, i + 1).kind == "NUM":
        num_tok = _at(tokens, i + 1)
        assert isinstance(num_tok.value, (int, float))
        return -num_tok.value, i + 2
    if t.kind == "NUM":
        assert isinstance(t.value, (int, float))
        return t.value, i + 1
    if t.kind == "STR":
        assert isinstance(t.value, str)
        return t.value, i + 1
    if _is_kw(t, "true"):
        return True, i + 1
    if _is_kw(t, "false"):
        return False, i + 1
    if _is_kw(t, "nil"):
        return None, i + 1
    if t.kind == "IDENT":
        name = t.text
        nxt = _at(tokens, i + 1)
        if _is_punct(nxt, "["):
            key, j = _parse_key(tokens, i + 2)
            if _is_punct(_at(tokens, j), "]"):
                j += 1
            base = scope.get(name)
            if isinstance(base, dict) and key in base:
                return base[key], j
            return Unresolved(raw=f"{name}[{key!r}]"), j
        if _is_punct(nxt, ":") or _is_punct(nxt, ".") or _is_punct(nxt, "("):
            raw, j = _consume_balanced(tokens, i)
            return Unresolved(raw=raw), j
        if name in scope:
            return scope[name], i + 1
        return Unresolved(raw=name), i + 1
    raw, j = _consume_balanced(tokens, i)
    return Unresolved(raw=raw), j


def parse_table(tokens: list[Token], i: int, scope: dict[str, LuaValue]) -> tuple[LuaTable, int]:
    assert _is_punct(_at(tokens, i), "{")
    i += 1
    result: LuaTable = {}
    array_index = 1
    n = len(tokens)
    while i < n:
        t = _at(tokens, i)
        if _is_punct(t, "}"):
            i += 1
            break
        if _is_punct(t, "["):
            i += 1
            key, i = _parse_key(tokens, i)
            if _is_punct(_at(tokens, i), "]"):
                i += 1
            if _is_punct(_at(tokens, i), "="):
                i += 1
            value, i = parse_value(tokens, i, scope)
            result[key] = value
        elif t.kind == "IDENT" and _is_punct(_at(tokens, i + 1), "="):
            key_name = t.text
            i += 2
            value, i = parse_value(tokens, i, scope)
            result[key_name] = value
        else:
            value, i = parse_value(tokens, i, scope)
            result[array_index] = value
            array_index += 1
        sep = _at(tokens, i)
        if sep.kind == "PUNCT" and sep.text in (",", ";"):
            i += 1
    return result, i


def _value_start_is_safe(tokens: list[Token], i: int) -> bool:
    """True if the value starting at i has a well-defined, boundable end that
    parse_value/parse_table can find on their own (a table literal, a plain literal, or a
    bare/indexed identifier reference). False for anything else -- notably a call or
    method-call expression, which Lua has no statement terminator to bound in a flat token
    scan. See the caller for why this matters."""
    t = _at(tokens, i)
    if _is_punct(t, "{"):
        return True
    if t.kind in ("NUM", "STR"):
        return True
    if _is_kw(t, "true") or _is_kw(t, "false") or _is_kw(t, "nil"):
        return True
    if _is_punct(t, "-") and _at(tokens, i + 1).kind == "NUM":
        return True
    if t.kind == "IDENT":
        nxt = _at(tokens, i + 1)
        return not (_is_punct(nxt, ":") or _is_punct(nxt, ".") or _is_punct(nxt, "("))
    return False


def extract_locals_and_alerts(tokens: list[Token]) -> tuple[dict[str, LuaValue], list[LuaTable]]:
    """Single forward scan implementing exactly the two trigger patterns described in this
    module's docstring: `local IDENT = <value>` (captured into `scope`) and
    `self:AddEncounterAlert(data)` (reads back `scope[data]` and emits it as an alert)."""
    scope: dict[str, LuaValue] = {}
    alerts: list[LuaTable] = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        if (
            _is_kw(t, "local")
            and _at(tokens, i + 1).kind == "IDENT"
            and _is_punct(_at(tokens, i + 2), "=")
            and _value_start_is_safe(tokens, i + 3)
        ):
            # Only actually parse+capture the RHS when its shape has a well-defined,
            # boundable end (table literal, plain literal, or a bare/indexed identifier
            # reference). Anything else -- crucially, a call/method-call expression like
            # `self:DefaultLoadConditions()` -- has no reliable end token in a flat scan
            # with no statement terminators, so deliberately DON'T consume it here: falling
            # through to the token-by-token default advance below walks past it safely
            # without ever needing to know where the statement ends. (An earlier version of
            # this function called parse_value() unconditionally, whose "unknown expression"
            # fallback scans for the next top-level `,`/`;`/close-bracket -- for a bare call
            # expression with no such thing to hit nearby, that ran away and silently
            # consumed the rest of the file, including every `local data = {...}` after it.
            # Caught by test_local_call_expression_does_not_swallow_rest_of_file.)
            name = tokens[i + 1].text
            value, j = parse_value(tokens, i + 3, scope)
            scope[name] = value
            i = j
            continue
        if (
            _is_kw(t, "self")
            and _is_punct(_at(tokens, i + 1), ":")
            and _is_kw(_at(tokens, i + 2), "AddEncounterAlert")
            and _is_punct(_at(tokens, i + 3), "(")
            and _at(tokens, i + 4).kind == "IDENT"
            and _is_punct(_at(tokens, i + 5), ")")
        ):
            arg = scope.get(tokens[i + 4].text)
            if isinstance(arg, dict):
                alerts.append(arg)
            i += 6
            continue
        i += 1
    return scope, alerts


# --------------------------------------------------------------------------------------
# Alert -> ability record
# --------------------------------------------------------------------------------------

_COLOR_CODE_RE = re.compile(r"\|c[0-9A-Fa-f]{8}|\|r")


def strip_color_codes(text: str) -> str:
    """WoW colour escapes (|cFFRRGGBB ... |r) verbatim in an addon string; strip for
    anything meant to be displayed as plain text. See this task's "Traps" section."""
    return _COLOR_CODE_RE.sub("", text)


def _sort_key(k: object) -> tuple[int, object]:
    if isinstance(k, bool):
        return (2, str(k))
    if isinstance(k, (int, float)):
        return (0, float(k))
    return (1, str(k))


def _fmt_num_key(k: int | float | str) -> str:
    if isinstance(k, float) and k.is_integer():
        return str(int(k))
    return str(k)


def to_list_if_array(value: LuaValue) -> list[LuaValue] | None:
    """A Lua table is a JSON array if its keys are exactly 1..N (an ordinary `{a, b, c}`
    positional literal, possibly empty). Returns None if `value` isn't such a table."""
    if not isinstance(value, dict):
        return None
    if not value:
        return []
    if not all(isinstance(k, int) and not isinstance(k, bool) for k in value):
        return None
    keys = sorted(k for k in value if isinstance(k, int))
    if keys != list(range(1, len(keys) + 1)):
        return None
    return [value[k] for k in keys]


def _as_number_list(items: list[LuaValue]) -> list[float | int]:
    out: list[float | int] = []
    for item in items:
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            out.append(item)
        # An Unresolved/non-numeric entry inside a timer array hasn't been observed in the
        # real files; defensively drop it rather than crash or emit non-numeric JSON.
    return out


def _convert_timers(raw: LuaValue) -> dict[str, list[float | int]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[float | int]] = {}
    for diff_key in sorted(raw.keys(), key=_sort_key):
        arr = to_list_if_array(raw[diff_key])
        if arr is None:
            continue
        out[_fmt_num_key(diff_key)] = _as_number_list(arr)
    return out


def _convert_phase_timers(raw: LuaValue) -> dict[str, dict[str, list[float | int]]] | None:
    """`phaseTimers` is this task's documented extension over the design doc's `timers`
    shape -- see the module docstring and this task's PROGRESS.md entry for why."""
    if not isinstance(raw, dict) or not raw:
        return None
    out: dict[str, dict[str, list[float | int]]] = {}
    for diff_key in sorted(raw.keys(), key=_sort_key):
        phase_table = raw[diff_key]
        if not isinstance(phase_table, dict):
            continue
        phase_out: dict[str, list[float | int]] = {}
        for phase_key in sorted(phase_table.keys(), key=_sort_key):
            arr = to_list_if_array(phase_table[phase_key])
            phase_out[_fmt_num_key(phase_key)] = _as_number_list(arr) if arr is not None else []
        out[_fmt_num_key(diff_key)] = phase_out
    return out


def build_ability_record(raw: LuaTable) -> dict[str, object]:
    unresolved: dict[str, str] = {}

    def field(name: str) -> LuaValue:
        v = raw.get(name)
        if isinstance(v, Unresolved):
            unresolved[name] = v.raw
            return None
        return v

    def text_field(name: str) -> str | None:
        v = field(name)
        return strip_color_codes(v) if isinstance(v, str) else None

    raw_timers = raw.get("timers")
    raw_phase_timers = raw.get("phaseTimers")
    has_timers = isinstance(raw_timers, dict) and len(raw_timers) > 0
    has_phase_timers = isinstance(raw_phase_timers, dict) and len(raw_phase_timers) > 0
    stub = not has_timers and not has_phase_timers

    internal_id = field("internalID")
    spell_id = field("spellID")
    phase = field("phase")
    duration = field("dur")

    return {
        "internal_id": internal_id if isinstance(internal_id, str) else None,
        "group": text_field("group"),
        "name": text_field("name"),
        "short_text": text_field("text"),
        "spell_id": int(spell_id) if isinstance(spell_id, (int, float)) else None,
        "phase": phase if isinstance(phase, (int, float)) else None,
        "display_type": field("DisplayType") if isinstance(field("DisplayType"), str) else None,
        "duration": duration if isinstance(duration, (int, float)) else None,
        "tts": field("TTS") if isinstance(field("TTS"), (bool, str)) else None,
        "stub": stub,
        "timers": _convert_timers(raw_timers) if has_timers else {},
        "phase_timers": _convert_phase_timers(raw_phase_timers) if has_phase_timers else None,
        "unresolved_fields": unresolved,
    }


# --------------------------------------------------------------------------------------
# File / directory driving
# --------------------------------------------------------------------------------------


def parse_lua_source(src: str) -> tuple[dict[str, LuaValue], list[LuaTable]]:
    return extract_locals_and_alerts(tokenize(src))


def read_addon_version(addon_dir: Path) -> str:
    for toc in sorted(addon_dir.glob("*.toc")):
        text = toc.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r"^##\s*Version:\s*(.+)$", text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return "unknown"


def build_dataset(
    addon_dir: Path,
    pack: str,
    zone: str,
    extracted_at: str,
    addon_version: str,
    notes: list[str],
) -> dict[str, object]:
    lua_dir = addon_dir / "EncounterAlerts" / pack
    lua_files = sorted(lua_dir.glob("*.lua"))

    abilities_by_enc: dict[int, list[dict[str, object]]] = defaultdict(list)
    warnings: list[str] = []

    for path in lua_files:
        src = path.read_text(encoding="utf-8")
        _, alerts = parse_lua_source(src)
        for raw in alerts:
            enc_id_val = raw.get("encID")
            if not isinstance(enc_id_val, (int, float)) or isinstance(enc_id_val, bool):
                warnings.append(
                    f"{path.name}: alert {raw.get('internalID')!r} has an unresolved or "
                    "missing encID; skipped"
                )
                continue
            enc_id = int(enc_id_val)
            abilities_by_enc[enc_id].append(build_ability_record(raw))

    encounters_out: list[dict[str, object]] = []
    for enc_id in sorted(abilities_by_enc):
        slug = ENCOUNTER_SLUG_MAP.get(enc_id)
        if slug is None:
            warnings.append(
                f"encID {enc_id} has no slug mapping for zone {zone!r}; skipped from output "
                "(not a failure -- the addon covers other raids too)"
            )
            continue
        encounters_out.append(
            {
                "dungeon_encounter_id": enc_id,
                "slug": slug,
                "abilities": abilities_by_enc[enc_id],
            }
        )

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)

    return {
        "meta": {
            "source": "NorthernSkyRaidTools",
            "addon_version": addon_version,
            "extracted_at": extracted_at,
            "zone": zone,
            "notes": notes,
        },
        "encounters": encounters_out,
    }


def render_dataset(dataset: dict[str, object]) -> str:
    return json.dumps(dataset, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--addon-dir",
        default=DEFAULT_ADDON_DIR,
        type=Path,
        help="NorthernSkyRaidTools addon root (contains EncounterAlerts/). "
        f"Default: {DEFAULT_ADDON_DIR}",
    )
    parser.add_argument("--pack", default="MidnightS2", help="EncounterAlerts subfolder name")
    parser.add_argument("--zone", default="venomous-abyss", help="Zone slug for meta + output")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write one whole-tier file here instead of the per-encounter timers.json files",
    )
    parser.add_argument(
        "--addon-version",
        default=None,
        help="Override meta.addon_version (default: parsed from the addon's own .toc file)",
    )
    parser.add_argument(
        "--extracted-at",
        default=None,
        help="Override meta.extracted_at (RFC3339 UTC). Default: now. Mainly for "
        "reproducible tests -- this is the one field a re-run is allowed to change.",
    )
    args = parser.parse_args(argv)

    addon_dir: Path = args.addon_dir
    addon_version: str = args.addon_version or read_addon_version(addon_dir)
    extracted_at: str = args.extracted_at or (
        dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    notes = list(CROSS_CHECK_NOTES) if args.zone == "venomous-abyss" else []

    dataset = build_dataset(addon_dir, args.pack, args.zone, extracted_at, addon_version, notes)

    encounters = dataset["encounters"]
    assert isinstance(encounters, list)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_dataset(dataset), encoding="utf-8")
        where = str(args.out)
    else:
        meta = dataset["meta"]
        assert isinstance(meta, dict)
        D.write_tier(args.zone, "timers.json", meta, encounters)
        where = D.rel(D.tier_dir(args.zone)) + "/<nn>_<boss>/timers.json"
    n_abilities = sum(len(e["abilities"]) for e in encounters)
    print(f"wrote {where} ({n_abilities} abilities across {len(encounters)} encounters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
