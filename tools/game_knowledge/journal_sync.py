#!/usr/bin/env python3
"""Pull an instance's Adventure Journal -- every ability, its text, and its role notes.

    python3 tools/game_knowledge/journal_sync.py --zone venomous-abyss
    # -> data/raid/12_1/venomous_abyss/<nn>_<boss>/journal.json

Why this exists
---------------
Planning a fight needs a *catalogue* of what the boss can do before any measurement of
when it does it. Until now this repo had timings (``data/raid/<patch>/<tier>/<nn>_<boss>/timers.json``, from NSRT) and
cooldown suggestions (``data/raid/<patch>/<tier>/<nn>_<boss>/plan_suggestions/``) but no answer to "what is this ability,
and what does it do to me" -- which is the question a person actually asks when they see an
unfamiliar bar on the timeline. This builds that catalogue from Blizzard's own data, so it
is complete by construction rather than as complete as whoever wrote a guide felt like
being.

The two sources, and why it takes two
-------------------------------------
**Blizzard Game Data** (``/data/wow/journal-instance``, ``/data/wow/journal-encounter``)
gives the *structure*: which encounters, which abilities, how they nest (Mutilate ->
Mutilated Gash), each ability's spell id, the boss's flavour description, the per-role
sections ("Damage Dealers", "Healers", "Tanks") and the difficulty modes the encounter has.
It does **not** give ability descriptions: an ability section carries a title and a spell
reference and nothing else. Only the Overview and role sections have ``body_text``.

**Wowhead's tooltip API** (``nether.wowhead.com/tooltip/spell/<id>``) supplies the missing
half, and it is the *only* source in this project's experience that carries **tuned damage
numbers** for a current tier -- e.g. Venomous Surge reads "inflicting 100009 Nature damage
every 1 sec for 10 sec". See .claude/knowledge/raid/12_1/venomous_abyss/venomous-abyss-12.1.md's sourcing table: the
Adventure Journal's own in-game text ships literal ``X`` placeholders, and Wowhead's
*database pages* have no damage fields, which made two earlier research passes conclude the
numbers did not exist anywhere. They do; they are behind the tooltip endpoint.

Traps this had to work around
-----------------------------
* **Blizzard's ``/data/wow/spell/<id>`` 404s on these ids.** Every boss spell checked here
  (1286033 Dig In, 1285732 Howling Maelstrom, 1305959 Venomous Surge) returns HTTP 404 from
  the static spell endpoint while resolving fine on Wowhead. So the tooltip fetch is not a
  nicety layered on Blizzard's text -- it is the only text there is.
* **The tooltip's number is one difficulty's number, and it does not say which.** The
  endpoint has no difficulty parameter. Treat a magnitude here as an order-of-magnitude
  anchor and cross-check the realised value against a log (see
  ``tools/warcraftlogs/encounter_profile_sync.py``, which measures damage taken per ability from actual
  Mythic pulls). ``meta.readMe`` records this rather than leaving a bare number to be
  misread as Mythic-tuned.
* **The same ability appears under more than one section id.** Sszorak's "Apex Predator"
  subtree is present twice (37046 and 37271) with identical children -- the journal
  duplicates a block when it applies to more than one phase or difficulty. Abilities are
  therefore deduplicated by spell id, keeping the first occurrence and recording how many
  further sections referenced it, rather than emitting the same ability twice.
* ``$bullet;`` is the journal's own bullet marker in ``body_text``. Left verbatim in
  ``bodyText`` and split into a ``bullets`` list beside it, so nothing is lost to a
  reformat.
"""

from __future__ import annotations

import argparse
import base64
import collections
import datetime as dt
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import datalayout as D  # noqa: E402

BNET_TOKEN_URL = "https://oauth.battle.net/token"
BNET_HOST = "https://eu.api.blizzard.com"
BNET_NAMESPACE = "static-eu"
WOWHEAD_TOOLTIP = "https://nether.wowhead.com/tooltip/spell/%d?locale=0"


# --------------------------------------------------------------------------- clients


def _env():
    """Repo-root ``.env``, same file and format tools/warcraftlogs/lib/wclapi.py reads."""
    out = {}
    path = REPO / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class Blizzard:
    """Minimal client-credentials Game Data client.

    Reuses the site's Battle.net application credentials (``WOWSITE_BNET_CLIENT_ID`` /
    ``_SECRET``). Client-credentials tokens carry no user scope, which is all the static
    Game Data APIs need.
    """

    def __init__(self, env):
        cid = env.get("WOWSITE_BNET_CLIENT_ID")
        secret = env.get("WOWSITE_BNET_CLIENT_SECRET")
        if not cid or not secret:
            raise SystemExit("WOWSITE_BNET_CLIENT_ID / WOWSITE_BNET_CLIENT_SECRET missing from .env")
        body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
        req = urllib.request.Request(BNET_TOKEN_URL, data=body)
        req.add_header(
            "Authorization",
            "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode(),
        )
        with urllib.request.urlopen(req, timeout=30) as fh:
            self.token = json.load(fh)["access_token"]
        #: The namespace the API echoes back is build-stamped (e.g. static-12.1.0_68914-eu).
        #: Recorded in the output so a stale dataset is diagnosable against a later build.
        self.build_namespace = None

    def get(self, path, **params):
        params.setdefault("namespace", BNET_NAMESPACE)
        params.setdefault("locale", "en_US")
        url = BNET_HOST + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + self.token)
        with urllib.request.urlopen(req, timeout=30) as fh:
            doc = json.load(fh)
        if self.build_namespace is None:
            href = (doc.get("_links") or {}).get("self", {}).get("href", "")
            m = re.search(r"namespace=([^&]+)", href)
            if m:
                self.build_namespace = m.group(1)
        return doc


_TAG = re.compile(r"<[^>]+>")
_WOWHEAD_CACHE = REPO / ".wclcache" / "_wowhead"


def wowhead_tooltip(spell_id, refresh=False):
    """Tooltip name + plain-text description for a spell id, cached on disk.

    Cached under ``.wclcache/_wowhead/`` alongside the WCL caches: these are immutable for
    a given game build, and re-fetching a few hundred of them on every run is rude to a
    service this project does not pay for.
    """
    _WOWHEAD_CACHE.mkdir(parents=True, exist_ok=True)
    path = _WOWHEAD_CACHE / f"{spell_id}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))

    req = urllib.request.Request(WOWHEAD_TOOLTIP % spell_id)
    # Wowhead 403s an unset User-Agent.
    req.add_header("User-Agent", "Mozilla/5.0 (wow-analysis journal_sync)")
    try:
        with urllib.request.urlopen(req, timeout=30) as fh:
            raw = json.load(fh)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        out = {"id": spell_id, "error": f"{type(exc).__name__}: {exc}"}
        path.write_text(json.dumps(out), encoding="utf-8")
        return out

    tooltip = raw.get("tooltip") or ""
    # The tooltip is a two-table HTML blob: the first table is the name and cast time, the
    # second is the description inside <div class="q">. Take the description div when it is
    # there and fall back to the whole stripped blob when it is not, rather than returning
    # an empty description for a shape this has not seen.
    m = re.search(r'<div class="q[^"]*">(.*?)</div>', tooltip, re.S)
    desc_html = m.group(1) if m else tooltip
    desc = html.unescape(_TAG.sub("", desc_html.replace("<br />", "\n").replace("<br/>", "\n")))
    desc = re.sub(r"[ \t]+", " ", desc).strip()

    cast = None
    mc = re.search(r"<br />([^<]*(?:cast|Instant|Channeled)[^<]*)", tooltip)
    if mc:
        cast = html.unescape(mc.group(1)).strip()

    out = {
        "id": spell_id,
        "name": raw.get("name"),
        "icon": raw.get("icon"),
        "cast": cast,
        "description": desc or None,
    }
    path.write_text(json.dumps(out), encoding="utf-8")
    time.sleep(0.12)
    return out


# ------------------------------------------------------------------------- magnitudes

#: "inflicting 100009 Nature damage", "500044 Nature damage every 4 sec". Captures the
#: number and, when stated, the school.
#:
#: The school list is *derived from the corpus*, not guessed: a first version listed the
#: eight schools from memory and silently dropped every Plague hit (9 in this zone) and
#: every Frostfire one (3), because a school it did not know simply failed the match and
#: produced an ability with no magnitude -- indistinguishable from an ability that deals no
#: damage at all. Re-derive it (scan the descriptions for ``<number> <Word> damage``) when
#: adding a zone rather than assuming this list is complete.
#:
#: The school is optional because one real phrasing omits it -- The Lost Explorers'
#: Splinters "causes them to bleed for 25002 damage every 1 sec" -- but the *number* and
#: the literal word "damage" are both required, which is what keeps this from matching
#: percentages, durations and stack counts.
_DAMAGE_RE = re.compile(
    r"([\d,]{3,})\s+"
    r"(?:(Physical|Holy|Fire|Frost|Frostfire|Nature|Shadow|Arcane|Plague|Astral|Chaos|Cosmic|Elemental|Shadowflame)\s+)?"
    r"damage",
    re.I,
)
_PERIOD_RE = re.compile(r"every\s+([\d.]+)\s*sec", re.I)


def magnitudes(description):
    """Every "<n> <school> damage" claim in a tooltip, with its tick period when stated.

    Returns a list rather than one number: an ability routinely states both an impact hit
    and a damage-over-time component ("inflicting 100009 Nature damage every 1 sec for 10
    sec. Upon expiration ... forms a Viscous Cyst"), and collapsing those to a single
    "damage" field would silently pick one and drop the other.
    """
    if not description:
        return []
    out = []
    for m in _DAMAGE_RE.finditer(description):
        amount = int(m.group(1).replace(",", ""))
        # Look for a tick period right after this hit, not anywhere in the description -- a
        # later sentence's "every 4 sec" does not belong to this number.
        tail = description[m.end(): m.end() + 60]
        p = _PERIOD_RE.search(tail)
        out.append(
            {
                "amount": amount,
                "school": m.group(2).title() if m.group(2) else None,
                "everySeconds": float(p.group(1)) if p else None,
            }
        )
    return out


# --------------------------------------------------------------------------- sections


def walk_sections(sections, parent=None, depth=0):
    """Flatten the journal's nested sections, keeping the parent link and the depth.

    The nesting is meaningful -- "Mutilated Gash" under "Mutilate" is the debuff the cast
    leaves behind -- so it is preserved as ``parentSpellId``/``parentTitle`` rather than
    flattened away.
    """
    for s in sections or []:
        spell = s.get("spell") or {}
        yield {
            "sectionId": s.get("id"),
            "title": s.get("title"),
            "spellId": spell.get("id"),
            "spellName": spell.get("name"),
            "depth": depth,
            "parentTitle": (parent or {}).get("title"),
            "parentSpellId": ((parent or {}).get("spell") or {}).get("id"),
            "bodyText": s.get("body_text"),
        }
        yield from walk_sections(s.get("sections"), parent=s, depth=depth + 1)


def split_bullets(body_text):
    if not body_text:
        return []
    return [p.strip() for p in body_text.split("$bullet;") if p.strip()]


def build_encounter(bz, journal_id, slug, refresh):
    enc = bz.get(f"/data/wow/journal-encounter/{journal_id}")
    nodes = list(walk_sections(enc.get("sections")))

    # An ability section is one that names a spell. The rest -- Overview, "Damage Dealers",
    # "Healers", "Tanks" -- are prose, and they are the only nodes carrying body_text.
    notes = []
    abilities = collections.OrderedDict()
    duplicates = collections.Counter()
    seen_notes = set()
    for n in nodes:
        if n["spellId"] is None:
            # The same prose block is repeated whenever it applies to more than one phase or
            # difficulty -- Nymrissa ships two identical "Tank" sections and two identical
            # "Bubblefin Shorerunner" ones. Deduplicate on the text, not the title: two notes
            # under one title can legitimately differ.
            if n["bodyText"] and n["bodyText"] not in seen_notes:
                seen_notes.add(n["bodyText"])
                notes.append(
                    {
                        "title": n["title"],
                        "bodyText": n["bodyText"],
                        "bullets": split_bullets(n["bodyText"]),
                    }
                )
            continue
        sid = n["spellId"]
        if sid in abilities:
            # See the module docstring: the journal repeats a whole subtree when it applies
            # to more than one phase. Count it, do not emit it twice.
            duplicates[sid] += 1
            continue
        abilities[sid] = n

    out = []
    for sid, n in abilities.items():
        tip = wowhead_tooltip(sid, refresh=refresh)
        desc = tip.get("description")
        row = {
            "spellId": sid,
            "title": n["title"],
            "journalSpellName": n["spellName"],
            "tooltipName": tip.get("name"),
            "icon": tip.get("icon"),
            "cast": tip.get("cast"),
            "description": desc,
            "damage": magnitudes(desc),
            "parentTitle": n["parentTitle"],
            "parentSpellId": n["parentSpellId"],
            "depth": n["depth"],
            "sectionId": n["sectionId"],
            "repeatedSections": duplicates.get(sid, 0),
        }
        if tip.get("error"):
            row["tooltipError"] = tip["error"]
        out.append(row)

    return {
        "slug": slug,
        "journalEncounterId": journal_id,
        "name": enc.get("name"),
        "description": enc.get("description"),
        "creatures": [{"id": c.get("id"), "name": c.get("name")} for c in enc.get("creatures") or []],
        "modes": [m.get("type") for m in enc.get("modes") or []],
        "notes": notes,
        "abilities": out,
    }


def resolve_encounters(bz, wanted):
    """Map each wanted encounter name to a journal encounter id by scanning instances.

    Matching on the site's own encounter *names* rather than a hardcoded instance id is
    what lets one zone span two journal instances -- The Venomous Abyss holds eight bosses
    and the Tidebound Grotto lair holds Nymrissa Wavecaller, and hardcoding the raid's id
    would silently drop the lair boss.
    """
    found, instances = {}, {}
    for inst in bz.get("/data/wow/journal-instance/index")["instances"]:
        if len(found) == len(wanted):
            break
        detail = bz.get(f"/data/wow/journal-instance/{inst['id']}")
        for enc in detail.get("encounters") or []:
            if enc["name"] in wanted and enc["name"] not in found:
                found[enc["name"]] = enc["id"]
                instances[enc["name"]] = {"id": inst["id"], "name": detail.get("name")}
    return found, instances


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--zone", required=True, help="zone slug, e.g. venomous-abyss")
    ap.add_argument("--out", type=pathlib.Path,
                    help="write one whole-tier file here instead of the per-encounter journal.json files")
    ap.add_argument("--refresh", action="store_true", help="bypass the Wowhead tooltip cache")
    args = ap.parse_args(argv)

    wanted = {e["name"]: e["slug"] for e in D.encounters(args.zone) if e.get("name")}

    bz = Blizzard(_env())
    found, instances = resolve_encounters(bz, wanted)

    missing = sorted(set(wanted) - set(found))
    if missing:
        print(f"  no journal encounter for: {', '.join(missing)}", file=sys.stderr)

    encounters = []
    for name, slug in wanted.items():
        if name not in found:
            encounters.append({"slug": slug, "name": name, "skipped": "not found in any journal instance"})
            continue
        print(f"  {slug} ...", file=sys.stderr, flush=True)
        row = build_encounter(bz, found[name], slug, args.refresh)
        row["journalInstance"] = instances[name]
        n_dmg = sum(1 for a in row["abilities"] if a["damage"])
        print(f"    {len(row['abilities'])} abilities, {n_dmg} with a parsed magnitude", file=sys.stderr)
        encounters.append(row)

    doc = {
        "meta": {
            "zone": args.zone,
            "source": "Blizzard Game Data journal-encounter + Wowhead tooltip API",
            "buildNamespace": bz.build_namespace,
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "generator": "tools/game_knowledge/journal_sync.py",
            "readMe": (
                "Ability text and damage magnitudes come from Wowhead's tooltip endpoint, "
                "which is the only source carrying tuned numbers for this tier -- Blizzard's "
                "/data/wow/spell/<id> returns 404 for these ids and the in-game journal text "
                "ships 'X' placeholders. A magnitude here is ONE difficulty's value and the "
                "endpoint does not say which; cross-check against measured damage taken in "
                "profiles/<spec>-<difficulty>.json before quoting it as a Mythic number."
            ),
        },
        "encounters": encounters,
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        written = [args.out]
    else:
        written = D.write_tier(args.zone, "journal.json", doc["meta"], encounters)
    for out in written:
        print(f"wrote {D.rel(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
