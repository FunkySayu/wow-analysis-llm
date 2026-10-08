"""Mechanical extraction: reports/venomous_abyss_bdruid.html -> seed JSON skeletons.

docs/design/50-content-migration.md, "The extraction": parse the built report's `const X =
{...}` payloads with a whitespace-tolerant regex rather than hand-transcribing -- the
artifact's own build script was once broken by an aligned `const APLS   =`, and the same
mistake is available here (some consts in this file *are* aligned with extra spaces before
`=`).

What this script does NOT do: write prose. Blurbs, plan summaries and plan-entry notes are
judgement calls (see 50-content-migration.md's "The prose rewrite" section) and are hand-
written directly into the seed JSON afterward -- this script only fills in the mechanical
fields (spell cache, damage segments, links, boss ability timers, loadout strings) so that
hand-editing starts from a structurally-correct base rather than a blank file.

Usage:

    py tools/reporting/extract_report_content.py [--raw-out PATH] [--check]

Writes:
  - scratch/report_extraction_raw.json      -- the raw DRUID/BOSS/META/OVERRIDE/TALENTS
                                                payloads, byte-faithful, base64 icon bytes
                                                dropped (see below). Durable per-report
                                                working extract, per CLAUDE.md's "save raw
                                                data before writing code that consumes it".
  - site/backend/app/seed/data/balance-druid.json  -- specs, hero_trees, builds (mechanical
                                                       fields only -- no prose).
  - site/backend/app/seed/data/venomous-abyss.json -- zone, encounters (blurb/subtitle
                                                       omitted -- filled in by hand next),
                                                       spells, boss_abilities. No `plans` key
                                                       -- plan entries are prose and are
                                                       hand-written directly into the file
                                                       produced here.

Icon bytes: DRUID/BOSS/BICONS in the report inline full base64 JPEG bytes so the artifact's
CSP didn't need an external image host. The site loads icons from wow.zamimg.com by name, so
only the icon *name* is kept:
  - BOSS entries already carry a name in `.i` (e.g. "spell_shadow_deathanddecay") --
    resolved through BICONS in the browser, but BICONS itself is pure image bytes and is
    read here only to confirm the referenced key exists, never for its value.
  - DRUID entries inline the full `data:image/jpeg;base64,...` URI directly with no icon
    *name* anywhere in the report. Names are recovered by matching each DRUID entry's
    ability name (case-insensitively) against data/classes/druid/balance/12_1_talents.json's own
    node entries, which do carry real icon names -- 140 of 147 resolve this way. The
    remaining 7 are baseline Balance Druid abilities absent from the talent-tree feed
    (which only carries *talent* nodes): one (Astral Power, spell_id 0) is not a real spell
    and is dropped entirely; the other 6 were spot-checked individually against
    nether.wowhead.com/ptr/tooltip/spell/<id> on 2026-08-26 -- see FALLBACK_ICONS below.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import datalayout as D  # noqa: E402

REPORT_PATH = REPO_ROOT / "reports" / "venomous_abyss_bdruid.html"
TALENT_TREE_PATH = D.talent_tree_path("balance-druid")
RAW_OUT_PATH = REPO_ROOT / "scratch" / "report_extraction_raw.json"
DRUID_SEED_OUT = REPO_ROOT / "site" / "backend" / "app" / "seed" / "data" / "balance-druid.json"
ZONE_SEED_OUT = REPO_ROOT / "site" / "backend" / "app" / "seed" / "data" / "venomous-abyss.json"

CONST_RE = re.compile(r"^const\s+(\w+)\s*=\s*(.*?);\s*$")
BOSS_CARD_RE = re.compile(
    r'<div class="boss" data-b="(?P<slug>[\w]+)">\s*'
    r'<div class="bhdr" data-sub="(?P<sub>[^"]*)" data-build="(?P<build>[^"]*)" '
    r'data-buildlabel="(?P<buildlabel>[^"]*)" data-tree="(?P<tree>[^"]*)" '
    r'data-flag="(?P<flag>[^"]*)" data-flagclass="(?P<flagclass>[^"]*)">'
)
# Turns the two small hand-authored JS object literals (OVERRIDE, TALENTS -- unquoted
# bare-identifier keys, unlike DRUID/BOSS/BICONS/META which are already valid JSON) into
# valid JSON by quoting keys that directly follow `{` or `,`. Both blocks only ever hold
# quoted-string values, so this is safe without a real JS parser.
BARE_KEY_RE = re.compile(r"([{,])\s*([A-Za-z_]\w*)\s*:")

# 00-overview.md's "Seed reality check" -- the canonical nine encounter slugs, in journal
# order (LAIR, then 1/8..8/8). Encounter.sort follows this order.
ENCOUNTER_ORDER = [
    "nymrissa",
    "nekzali",
    "sentinels",
    "vashnik",
    "explorers",
    "sszorak",
    "twinfangs",
    "coiledaltar",
    "ulatek",
]

# See module docstring's "Icon bytes" section. Spot-checked individually via
# nether.wowhead.com/ptr/tooltip/spell/<id> on 2026-08-26 (this task's PROGRESS.md entry).
FALLBACK_ICONS: dict[int, str] = {
    48518: "ability_druid_eclipse",  # Lunar Eclipse (buff)
    8921: "spell_nature_starfall",  # Moonfire -- yes, really; a long-standing Blizzard icon mismatch
    8936: "spell_nature_resistnature",  # Regrowth
    48517: "ability_druid_eclipseorange",  # Solar Eclipse (buff)
    191034: "ability_druid_starfall",  # Starfall
    190984: "spell_nature_wrathv2",  # Wrath
}
# Astral Power (druid payload slug "astral-power") carries spell_id 0 in the report -- a
# resource display, not a real spell. Dropped from the spell cache entirely.
DROPPED_DRUID_SPELL_IDS = {0}

# mythictrap.com slug corrections. 00-overview.md/CLAUDE.md: "mythictrap.com once served a
# completely unrelated boss under HTTP 200." All nine `mt` slugs from the report were opened
# on 2026-08-26 (via https://www.mythictrap.com/en/venomous-abyss/<slug>) and checked against
# the page's own heading -- see this task's PROGRESS.md entry for the full spot-check list.
# Eight were correct. `coiled-altar` 200'd, but the page it returned was Nymrissa Wavecaller's
# guide -- the exact trap the docs warn about. `the-coiled-altar` is the real slug (confirmed
# against its own page heading, and it also matches the report's own (correct) lorrgs_slug).
MYTHICTRAP_SLUG_FIXES: dict[str, str] = {
    "coiled-altar": "the-coiled-altar",
}

WOWHEAD_GUIDE_KIND = {1: "lair", 2: "raid"}


def find_consts(text: str, names: set[str]) -> dict[str, Any]:
    """Line-scan for `const NAME = {...};`, tolerant of extra whitespace before `=`."""
    found: dict[str, Any] = {}
    for line in text.split("\n"):
        m = CONST_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        if name in names and name not in found:
            found[name] = json.loads(m.group(2))
    missing = names - found.keys()
    if missing:
        raise SystemExit(f"could not find const(s) {sorted(missing)} in {REPORT_PATH}")
    return found


def find_bare_key_block(text: str, name: str) -> Any:
    """Extract a small hand-authored `const NAME = {...};` block (unquoted keys) as JSON."""
    m = re.search(rf"const\s+{name}\s*=\s*(\{{.*?\}})\s*;", text, re.DOTALL)
    if not m:
        raise SystemExit(f"could not find const {name} block in {REPORT_PATH}")
    quoted = BARE_KEY_RE.sub(r'\1"\2":', m.group(1))
    return json.loads(quoted)


def extract_boss_card_attrs(text: str) -> dict[str, dict[str, str]]:
    matches = list(BOSS_CARD_RE.finditer(text))
    if len(matches) != len(ENCOUNTER_ORDER):
        raise SystemExit(
            f"expected {len(ENCOUNTER_ORDER)} boss cards, found {len(matches)} "
            "(BOSS_CARD_RE may need updating)"
        )
    out: dict[str, dict[str, str]] = {}
    for m in matches:
        d = m.groupdict()
        out[d["slug"]] = {
            "subtitle": html.unescape(d["sub"]),
            "build": d["build"],
            "buildlabel": html.unescape(d["buildlabel"]),
            "tree": d["tree"],
        }
    return out


def build_icon_by_name(talent_tree: dict[str, Any]) -> dict[str, str]:
    by_name: dict[str, str] = {}
    for tree in talent_tree["trees"].values():
        for node in tree["nodes"]:
            for entry in node["entries"]:
                nm = entry.get("name")
                icon = entry.get("icon")
                if nm and icon:
                    by_name[nm.lower()] = icon
    return by_name


def build_spells(
    druid: dict[str, Any], boss: dict[str, Any], override: dict[str, Any], icon_by_name: dict[str, str]
) -> list[dict[str, Any]]:
    spells: dict[int, dict[str, Any]] = {}

    for slug, e in druid.items():
        spell_id = e["s"]
        if spell_id in DROPPED_DRUID_SPELL_IDS:
            continue
        icon = icon_by_name.get(e["n"].lower()) or FALLBACK_ICONS.get(spell_id)
        spells[spell_id] = {
            "spell_id": spell_id,
            "name": e["n"],
            "icon": icon,
            "description": e["d"],
            "slug": slug,
            "is_override": False,
            "source": "wowhead-ptr",
        }

    for key, e in boss.items():
        spell_id = int(key)
        ov = override.get(key)
        spells[spell_id] = {
            "spell_id": spell_id,
            "name": ov["n"] if ov else e["n"],
            "icon": e["i"],
            "description": ov["d"] if ov else e["d"],
            "slug": None,
            "is_override": ov is not None,
            "source": "manual" if ov else "wowhead-ptr",
        }

    return [spells[k] for k in sorted(spells)]


def _phase_key_sort(k: str) -> float:
    return float(k)


def build_boss_abilities(timers_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert one encounter's task-23 abilities into BossAbilityIn dicts.

    Two shapes exist in the tier's per-encounter timers.json files (see its own _schema.json):
    a flat `timers: {difficulty: [seconds...]}` (the common case), and a `phase_timers:
    {difficulty: {phase: [seconds...]}}` extension for a recurring ability whose timing
    resets per phase/cycle. `boss_abilities.phase` (models.py) is a single scalar per
    ability row, so a `phase_timers` ability is split into one BossAbilityIn per phase key
    (internal_id suffixed `#p<phase>`, still unique per encounter) rather than losing the
    phase-relative timing by flattening everything into one row. See this task's
    PROGRESS.md entry.

    Ten of the 94 real abilities across the zone (not encounter-specific) carry a null
    `spell_id` -- synthetic NSRT reminders ("Taunt", "Wrong Target", "Orb deadline") with no
    underlying spell. `boss_abilities.spell_id` is NOT NULL (models.py), so these are
    dropped rather than seeded with a fabricated id. A handful of abilities have a real
    spell_id but a null `name` (NSRT's own reminder text, not the addon's ability name) --
    `boss_abilities.name` is also NOT NULL, so `internal_id` is used as a fallback label.
    """
    out: list[dict[str, Any]] = []
    for ab in timers_data:
        if ab["spell_id"] is None:
            continue
        name = ab["name"] or ab["internal_id"]

        if ab["timers"]:
            timers = [
                {"difficulty": int(diff), "at_seconds": secs, "sort": i}
                for diff, arr in ab["timers"].items()
                for i, secs in enumerate(arr)
            ]
            out.append(
                {
                    "spell_id": ab["spell_id"],
                    "name": name,
                    "internal_id": ab["internal_id"],
                    "short_text": ab["short_text"],
                    "display_type": ab["display_type"],
                    "phase": ab["phase"],
                    "group_label": ab["group"],
                    "timers": timers,
                }
            )
        elif ab["phase_timers"]:
            phase_keys: set[str] = set()
            for by_phase in ab["phase_timers"].values():
                phase_keys |= by_phase.keys()
            for phase_key in sorted(phase_keys, key=_phase_key_sort):
                timers = [
                    {"difficulty": int(diff), "at_seconds": secs, "sort": i}
                    for diff, by_phase in ab["phase_timers"].items()
                    if phase_key in by_phase
                    for i, secs in enumerate(by_phase[phase_key])
                ]
                out.append(
                    {
                        "spell_id": ab["spell_id"],
                        "name": name,
                        "internal_id": f"{ab['internal_id']}#p{phase_key}",
                        "short_text": ab["short_text"],
                        "display_type": ab["display_type"],
                        "phase": float(phase_key),
                        "group_label": ab["group"],
                        "timers": timers,
                    }
                )
        else:
            # stub: no timers at all (an untested/UI-helper alert), still worth a row.
            out.append(
                {
                    "spell_id": ab["spell_id"],
                    "name": name,
                    "internal_id": ab["internal_id"],
                    "short_text": ab["short_text"],
                    "display_type": ab["display_type"],
                    "phase": ab["phase"],
                    "group_label": ab["group"],
                    "timers": [],
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-out", type=Path, default=RAW_OUT_PATH)
    parser.add_argument("--check", action="store_true", help="parse only, write nothing")
    args = parser.parse_args(argv)

    report_text = REPORT_PATH.read_text(encoding="utf-8")
    consts = find_consts(report_text, {"DRUID", "BOSS", "META"})
    druid, boss, meta = consts["DRUID"], consts["BOSS"], consts["META"]
    override = find_bare_key_block(report_text, "OVERRIDE")
    talents = find_bare_key_block(report_text, "TALENTS")
    card_attrs = extract_boss_card_attrs(report_text)

    if set(meta.keys()) != set(ENCOUNTER_ORDER):
        raise SystemExit(f"META keys {sorted(meta.keys())} != canonical {ENCOUNTER_ORDER}")

    talent_tree = json.loads(TALENT_TREE_PATH.read_text(encoding="utf-8"))
    icon_by_name = build_icon_by_name(talent_tree)
    spells = build_spells(druid, boss, override, icon_by_name)

    boss_timers = D.load_tier("venomous-abyss", "timers.json")
    timers_by_slug = {enc["slug"]: enc["abilities"] for enc in boss_timers["encounters"]}
    if set(timers_by_slug.keys()) != set(ENCOUNTER_ORDER):
        raise SystemExit(
            f"boss_timers slugs {sorted(timers_by_slug.keys())} != canonical {ENCOUNTER_ORDER}"
        )

    raw_extract = {
        "druid": druid,
        "boss": boss,
        "meta": meta,
        "override": override,
        "talents": talents,
        "boss_card_attrs": card_attrs,
    }
    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    if not args.check:
        args.raw_out.write_text(
            json.dumps(raw_extract, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ---- balance-druid.json (specs, hero_trees, builds -- no prose) ----
    tree_specs = talent_tree["spec"]
    hero_subtrees = {st["slug"]: st for st in talent_tree["trees"]["hero"]["subtrees"]}
    build_tree_map = {
        "ec_lunation": ("elunes-chosen", "lunation"),
        "ec_goldrinn": ("elunes-chosen", "goldrinn"),
        "kotg_bounteous": ("keeper-of-the-grove", "bounteous"),
    }
    builds = []
    for talent_key, loadout_string in talents.items():
        hero_tree_slug, label_suffix = build_tree_map[talent_key]
        tree_label = "EC" if hero_tree_slug == "elunes-chosen" else "KotG"
        builds.append(
            {
                "spec": "balance-druid",
                "slug": talent_key.replace("_", "-"),
                "label": f"{tree_label} · {label_suffix}",
                "loadout_string": loadout_string,
                "hero_tree": hero_tree_slug,
                "loadout_spec_id": tree_specs["spec_id"],
            }
        )

    druid_seed = {
        "specs": [
            {
                "slug": "balance-druid",
                "class_id": tree_specs["class_id"],
                "spec_id": tree_specs["spec_id"],
                "class_name": tree_specs["class_name"],
                "spec_name": tree_specs["spec_name"],
                "role": "dps",
                "hero_trees": [
                    {
                        "slug": "elunes-chosen",
                        "name": "Elune's Chosen",
                        "sub_tree_id": hero_subtrees["elunes-chosen"]["sub_tree_id"],
                        "color": "#4A3AA7",
                    },
                    {
                        "slug": "keeper-of-the-grove",
                        "name": "Keeper of the Grove",
                        "sub_tree_id": hero_subtrees["keeper-of-the-grove"]["sub_tree_id"],
                        "color": "#008300",
                    },
                ],
            }
        ],
        "builds": builds,
    }

    # ---- venomous-abyss.json (zone, encounters, spells, boss_abilities -- no prose) ----
    encounters = []
    for sort, slug in enumerate(ENCOUNTER_ORDER):
        m = meta[slug]
        attrs = card_attrs[slug]
        mt_slug = MYTHICTRAP_SLUG_FIXES.get(m["mt"], m["mt"])
        encounters.append(
            {
                "slug": slug,
                "name": m["name"],
                "sort": sort,
                "journal_index": m["idx"],
                "subtitle": attrs["subtitle"],
                "blurb": None,  # hand-written next -- see 50-content-migration.md
                "dungeon_encounter_id": m["enc"],
                "wcl_encounter_id": m["enc"],
                "mythictrap_slug": mt_slug,
                "lorrgs_slug": m["lorrgs"],
                "wowhead_slug": m["wh"],
                "wowhead_guide_kind": WOWHEAD_GUIDE_KIND[m["whGuide"]],
                "reference_duration": m["dur"],
                "damage_segments": [
                    {
                        "label": seg["n"],
                        "pct": seg["p"],
                        "total_damage": seg["t"],
                        "kill_count": seg["k"],
                        "note": seg["d"],
                        "sort": i,
                    }
                    for i, seg in enumerate(m["seg"])
                ],
                "boss_abilities": build_boss_abilities(timers_by_slug[slug]),
            }
        )

    zone_seed = {
        "zone": {
            "slug": "venomous-abyss",
            "name": "The Venomous Abyss",
            "patch": "12.1",
            "wcl_zone_id": 53,
            "mythictrap_slug": "venomous-abyss",
            "wowhead_guide_base": "midnight",
            "sort": 1,
        },
        "encounters": encounters,
        "spells": spells,
    }

    if not args.check:
        DRUID_SEED_OUT.parent.mkdir(parents=True, exist_ok=True)
        DRUID_SEED_OUT.write_text(
            json.dumps(druid_seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        ZONE_SEED_OUT.write_text(
            json.dumps(zone_seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.raw_out}")
        print(f"wrote {DRUID_SEED_OUT} ({len(builds)} builds)")
        print(f"wrote {ZONE_SEED_OUT} ({len(encounters)} encounters, {len(spells)} spells)")
    else:
        print(
            f"OK: {len(encounters)} encounters, {len(spells)} spells, {len(builds)} builds "
            "(--check, nothing written)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
