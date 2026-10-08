#!/usr/bin/env python3
"""Build first-draft timeline suggestions for a (zone, spec, difficulty) from logged play.

    python3 tools/warcraftlogs/plan_suggestion_sync.py --zone venomous-abyss --spec balance-druid \\
        --difficulty 15
    # -> data/raid/12_1/venomous_abyss/<nn>_<boss>/plan_suggestions/balance-druid-15.json

The site's timeline editor starts empty, so every row has to be typed by hand. That is the
wrong default: for any boss that has been killed a few thousand times, *when the field
presses each cooldown* is already recorded, and the interesting part of planning is
disagreeing with it — not reconstructing it. This tool samples the ranking pool for an
encounter and emits the rows the editor would otherwise ask a person to invent, each one
carrying the evidence that produced it so it can be argued with rather than merely trusted.

What it is not
--------------
It is **not** a check (``tools/warcraftlogs/``). A check answers a question about *one* report and
is per-pull by construction. This reads N strangers' pulls and emits a dataset, which puts
it with ``nsrt_timer_import.py`` and ``talent_tree_sync.py``: a ``data/`` builder whose
output is reviewed, committed, and loaded by the seed loader.

The four things that make the output trustworthy
------------------------------------------------
1. **Nothing is timed from the pull start.** Kill times on one boss ranged 317s to 465s in
   the sample this was written against, so an absolute-second median is a median of
   different fights. Every time here is *phase-relative*: seconds since the start of the
   phase the cast landed in, which is stable across pull lengths (measured: Phase 3's first
   Incarnation clustered 5.1-7.5s across seven pulls, where its absolute time spanned 130s).

2. **Pulls with a different phase structure are dropped, loudly.** A pull whose log records
   fewer phase transitions than the rest puts every one of its casts in phase 1, which then
   pollutes phase 1's ordinals with times from the whole fight. The modal transition count
   wins and the rest are excluded with a reason, rather than silently widening every
   spread. This was not hypothetical: it produced the 127.9s and 253.5s outliers in the
   first version's "Phase 1, second Incarnation" group.

3. **Cooldowns are classified, not listed.** An ability pressed nineteen times on a
   four-hundred-second pull is "press it on cooldown" — emitting nineteen suggested rows
   for it is noise that buries the four rows that encode an actual decision. A cooldown
   earns per-instance rows only when its timing genuinely clusters (see ``TIGHT_IQR``).

4. **The anchor is a boss mechanic, not a number.** "6.7s into Stage Three" is only useful
   while the phase list holds; "2.1s after the first Ghastly Regeneration" survives a
   retuning and is what a person actually plans against. Anchors are voted on across the
   contributing pulls and carry their agreement count, so a weak anchor looks weak.

The candidate cooldown set is **derived from the sampled pulls**, not from a hardcoded
list: any ability whose median gap between casts across the pool is at least
``MIN_RECHARGE_S`` is a candidate. ``data/classes/<class>/<spec>/12_1_cooldowns.json`` is therefore
optional and only supplies presentation metadata (role, display order) plus a deny list for
things that pass the gap test without being decisions — shapeshift forms, an emergency
heal. A spec with no such file still produces suggestions; it just labels them all
``unclassified``.

Traps this had to work around
-----------------------------
* **The talent tree's spell id is not the cast log's spell id.** ``data/classes/<class>/<spec>/12_1_talents.json``
  gives Incarnation: Chosen of Elune as 394013 and Celestial Alignment as 395022; the cast
  events in every sampled log are 102560 and 194223. Building the candidate list from the
  tree would therefore have matched nothing, with no error. Everything here is keyed off
  ids observed in ``Casts`` events, and names are resolved through the report's own ability
  table. (Same family as CLAUDE.md's Wowhead live-vs-PTR trap: the wrong answer arrives
  looking exactly like the right one.)
* **Wild Charge is 102383 in Moonkin Form**, not the 102401 a class-wide list would carry.
  Another reason the set is observed rather than declared.
* WCL difficulty numbering is not the game's. This tool takes the in-game number
  (14/15/16), which is what the site stores, and maps to WCL's raid numbering at the API
  boundary only — see ``WCL_DIFFICULTY``.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import statistics
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import datalayout as D  # noqa: E402

from checks import encounter as E  # noqa: E402
from lib import wclapi as W  # noqa: E402

#: In-game difficulty (what the site stores, per docs/design/00-overview.md's Vocabulary)
#: -> WarcraftLogs raid difficulty. The two numbering schemes do not match and mixing them
#: silently samples the wrong bracket.
WCL_DIFFICULTY = {14: 3, 15: 4, 16: 5}

#: An ability is a candidate cooldown if the pool's median gap between its casts is at
#: least this. Below it, the ability is filler or a proc and belongs to the rotation, which
#: is the APL's business and not a timeline's.
MIN_RECHARGE_S = 25.0

#: ...and if it is not pressed more than this many times on a typical pull. The gap test
#: alone admits an ability used twice at either end of a long fight; this bounds the other
#: side, so a "cooldown" that fires twenty times is classified rather than enumerated.
MAX_USES_FOR_INSTANCES = 8

#: A (phase, ordinal) group is a real, plannable instant if the middle half of its
#: contributing pulls agree within this many seconds. Calibrated against the sample: real
#: scheduled uses landed inside ~2.5s, while "wherever the cooldown came up" groups spread
#: over 30s or more, so anything in between is genuinely ambiguous and is reported with its
#: spread rather than rounded to a number.
TIGHT_IQR_S = 8.0

#: A group is only emitted when at least this share of the usable pulls contributed to it.
MIN_SUPPORT = 0.4
MIN_SUPPORT_PULLS = 3

#: How far from a cast to look for a boss mechanic to anchor it to.
ANCHOR_WINDOW_S = 15.0

#: An enemy ability cast more often than this on one pull is a rotational boss attack, not
#: a mechanic worth naming in a plan.
MAX_MECHANIC_CASTS = 12

RANK_Q = """query { worldData { encounter(id: %d) { name
  characterRankings(className: "%s", specName: "%s",
                    difficulty: %d, metric: dps, page: %d) } } }"""


# ---------------------------------------------------------------------------- sampling


def rankings(encounter_id, class_name, spec_name, wcl_difficulty, pages=1, refresh=False):
    """Top ``pages * 100`` logged pulls for this encounter, DPS-descending."""

    def go():
        out = []
        for page in range(1, pages + 1):
            r = W.query(RANK_Q % (encounter_id, class_name, spec_name, wcl_difficulty, page))
            cr = r["data"]["worldData"]["encounter"]["characterRankings"]
            out.extend(cr["rankings"])
            if not cr.get("hasMorePages"):
                break
        return out

    key = "plansugg|%d|%s|%s|%d|%d" % (encounter_id, class_name, spec_name, wcl_difficulty, pages)
    return W.cached("_pool", key, go, refresh)


def pull_profile(rank):
    """One sampled pull, reduced to what a suggestion needs.

    Returns ``None`` for a pull we cannot read (a private report, a renamed character),
    which the caller counts and reports rather than treating as an empty pull.
    """
    code, fid = rank["report"]["code"], rank["report"]["fightID"]
    # `SystemExit` is deliberately in the tuple: `wclapi.actor_id` raises it (not a plain
    # Exception) when a name is absent from a report, which is routine here rather than
    # fatal -- WCL returns rankings for players who have anonymised themselves, and their
    # name comes back as the literal "Anonymous", matching no actor. Catching only
    # `Exception` let one such row abort a whole-zone run on the first boss.
    try:
        fight = E.fight(code, fid)
        actor_id = W.actor_id(code, rank["name"])
        casts = W.events(code, fid, "Casts", source_id=actor_id)
        enemy = E.enemy_events(code, fid, "Casts")
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - one unreadable pull must not end the run
        return {"skipped": f"{type(exc).__name__}: {exc}", "code": code, "fight": fid, "player": rank["name"]}

    t0, t1 = fight["startTime"], fight["endTime"]
    phases = [(p["startTime"] - t0) / 1000.0 for p in (fight.get("phaseTransitions") or [])]
    if not phases or phases[0] > 0:
        phases = [0.0, *phases]

    names = W.ability_names(code)

    player = collections.defaultdict(list)
    for e in casts:
        if e.get("type") == "cast":
            player[e["abilityGameID"]].append((e["timestamp"] - t0) / 1000.0)

    mechanics = collections.defaultdict(list)
    for e in enemy:
        if e.get("type") not in ("cast", "begincast"):
            continue
        gid = e.get("abilityGameID")
        name = names.get(gid)
        if not name:
            continue
        mechanics[name].append((e["timestamp"] - t0) / 1000.0)
    # A boss's filler attack is not a mechanic. Dropping by frequency rather than by name
    # keeps this working on a boss nobody has written a guide for.
    mechanics = {
        n: sorted(ts) for n, ts in mechanics.items() if len(ts) <= MAX_MECHANIC_CASTS
    }

    return {
        "code": code,
        "fight": fid,
        "player": rank["name"],
        "duration": (t1 - t0) / 1000.0,
        "phases": phases,
        "casts": {g: sorted(ts) for g, ts in player.items()},
        "mechanics": mechanics,
        "names": {g: names.get(g, str(g)) for g in player},
    }


def phase_of(phases, t):
    """1-based phase index for a fight-relative second, plus that phase's start."""
    idx = 0
    for i, start in enumerate(phases):
        if start <= t:
            idx = i
        else:
            break
    return idx + 1, phases[idx]


# ---------------------------------------------------------------- structure agreement


def usable_pulls(profiles):
    """Keep only the pulls whose phase structure matches the modal one.

    See the module docstring, point 2. Returns ``(kept, excluded)`` where each excluded
    entry says why, because "we sampled 25 and used 21" is a fact the consumer of this
    dataset needs and a silent filter would hide.
    """
    counts = collections.Counter(len(p["phases"]) for p in profiles)
    if not counts:
        return [], []
    modal, _ = counts.most_common(1)[0]
    kept, excluded = [], []
    for p in profiles:
        if len(p["phases"]) == modal:
            kept.append(p)
        else:
            excluded.append(
                {
                    "code": p["code"],
                    "fight": p["fight"],
                    "player": p["player"],
                    "reason": (
                        f"log records {len(p['phases'])} phase segment(s); "
                        f"{modal} is the pool's structure for this boss"
                    ),
                }
            )
    return kept, excluded


# ------------------------------------------------------------------------ cooldowns


def candidate_cooldowns(pulls, deny):
    """Ability ids whose pool-wide median inter-cast gap makes them a cooldown.

    Derived rather than declared -- see the module docstring. ``deny`` suppresses ids a
    curated ``data/classes`` file marks as non-decisions.
    """
    gaps = collections.defaultdict(list)
    uses = collections.defaultdict(list)
    for p in pulls:
        for gid, ts in p["casts"].items():
            uses[gid].append(len(ts))
            gaps[gid].extend(y - x for x, y in zip(ts, ts[1:]))

    out = {}
    for gid, per_pull in uses.items():
        if gid in deny:
            continue
        # Present on a real share of the pool: one player's off-spec button is not a plan.
        if len(per_pull) < max(MIN_SUPPORT_PULLS, MIN_SUPPORT * len(pulls)):
            continue
        g = gaps[gid]
        # Used once per pull by everyone counts: there is no gap to measure, and a
        # once-a-fight button is the most schedulable thing there is.
        median_gap = statistics.median(g) if g else float("inf")
        if median_gap < MIN_RECHARGE_S:
            continue
        out[gid] = {
            "medianUsesPerPull": statistics.median(per_pull),
            "medianGap": None if median_gap == float("inf") else round(median_gap, 1),
            "pulls": len(per_pull),
        }
    return out


def group_instances(pulls, gid):
    """Cast times for one cooldown, grouped by (phase, ordinal within that phase).

    Keyed on the ordinal *within the phase* rather than within the pull so that one extra
    early use does not renumber every later group — the failure mode that makes a
    whole-fight ordinal useless on a fight with a variable-length opener.
    """
    groups = collections.defaultdict(list)
    for p in pulls:
        seen = collections.Counter()
        for t in p["casts"].get(gid, []):
            phase, phase_start = phase_of(p["phases"], t)
            seen[phase] += 1
            groups[(phase, seen[phase])].append(
                {"pull": p, "at": t, "atPhase": t - phase_start}
            )
    return groups


def spread(values):
    values = sorted(values)
    if len(values) == 1:
        return {"median": round(values[0], 1), "p25": round(values[0], 1),
                "p75": round(values[0], 1), "iqr": 0.0, "min": round(values[0], 1),
                "max": round(values[0], 1)}
    q = statistics.quantiles(values, n=4, method="inclusive")
    return {
        "median": round(statistics.median(values), 1),
        "p25": round(q[0], 1),
        "p75": round(q[2], 1),
        "iqr": round(q[2] - q[0], 1),
        "min": round(values[0], 1),
        "max": round(values[-1], 1),
    }


def anchor_for(members):
    """The boss mechanic the contributing pulls most agree this cast follows.

    Votes on ``(mechanic name, occurrence index)`` across the members and returns the
    winner with its agreement count, so a suggestion anchored by four pulls out of nine
    reads as the weak claim it is instead of as a fact.
    """
    votes = collections.Counter()
    offsets = collections.defaultdict(list)
    for m in members:
        best = None
        for name, times in m["pull"]["mechanics"].items():
            for i, mt in enumerate(times, start=1):
                delta = m["at"] - mt
                if -ANCHOR_WINDOW_S <= delta <= ANCHOR_WINDOW_S:
                    if best is None or abs(delta) < abs(best[2]):
                        best = (name, i, delta)
        if best:
            votes[(best[0], best[1])] += 1
            offsets[(best[0], best[1])].append(best[2])
    if not votes:
        return None
    (name, occurrence), agree = votes.most_common(1)[0]
    return {
        "ability": name,
        "occurrence": occurrence,
        "offsetSeconds": round(statistics.median(offsets[(name, occurrence)]), 1),
        "agreement": agree,
        "of": len(members),
    }


def classify(pulls, gid, stats):
    """One cooldown's verdict and the rows it should contribute to a plan."""
    groups = group_instances(pulls, gid)
    floor = max(MIN_SUPPORT_PULLS, int(round(MIN_SUPPORT * len(pulls))))

    tight, loose = [], []
    for (phase, ordinal), members in sorted(groups.items()):
        if len(members) < floor:
            continue
        s = spread([m["atPhase"] for m in members])
        row = {
            "phase": phase,
            "ordinal": ordinal,
            "atPhaseSeconds": s["median"],
            "atSeconds": spread([m["at"] for m in members])["median"],
            "spread": s,
            "support": {"pulls": len(members), "of": len(pulls)},
            "anchor": anchor_for(members),
        }
        (tight if s["iqr"] <= TIGHT_IQR_S else loose).append(row)

    if tight and stats["medianUsesPerPull"] <= MAX_USES_FOR_INSTANCES:
        return "scheduled", tight
    if stats["medianUsesPerPull"] >= 5:
        # Pressed on recharge. One row saying so beats nineteen rows saying when.
        return "on-cooldown", []
    return "situational", loose


# ----------------------------------------------------------------------- encounters


def build_encounter(enc, class_name, spec_name, difficulty, sample_size, catalog, refresh):
    wcl_diff = WCL_DIFFICULTY[difficulty]
    ranks = rankings(enc["wcl_encounter_id"], class_name, spec_name, wcl_diff, refresh=refresh)
    if not ranks:
        return {"slug": enc["slug"], "skipped": "no ranked pulls for this class/spec/difficulty"}

    profiles, unreadable = [], []
    for i, r in enumerate(ranks[:sample_size]):
        # A whole-zone run at a hundred pulls a boss outruns the hourly point budget, and
        # WCL answers an over-budget request with a GraphQL `errors` block inside an
        # otherwise well-formed body -- so without this the run would not crash, it would
        # quietly record every remaining boss as having a handful of usable pulls. Checked
        # every ten pulls because the check itself costs a point.
        if i % 10 == 0:
            W.wait_for_budget(note=f"{enc['slug']} pull {i + 1}/{min(sample_size, len(ranks))}")
        p = pull_profile(r)
        (unreadable if p.get("skipped") else profiles).append(p)

    pulls, excluded = usable_pulls(profiles)
    if len(pulls) < MIN_SUPPORT_PULLS:
        return {
            "slug": enc["slug"],
            "skipped": f"only {len(pulls)} readable pull(s) with a consistent phase structure",
        }

    deny = set(catalog.get("deny", []))
    stats = candidate_cooldowns(pulls, deny)

    meta = catalog.get("abilities", {})
    cooldowns = []
    for gid, st in stats.items():
        verdict, rows = classify(pulls, gid, st)
        name = next((p["names"][gid] for p in pulls if gid in p["names"]), str(gid))
        entry = meta.get(str(gid), {})
        cooldowns.append(
            {
                "spellId": gid,
                "name": name,
                "role": entry.get("role", "unclassified"),
                "verdict": verdict,
                "medianUsesPerPull": st["medianUsesPerPull"],
                "medianGapSeconds": st["medianGap"],
                "seenInPulls": st["pulls"],
                "suggestions": rows,
            }
        )
    cooldowns.sort(key=lambda c: (c["verdict"] != "scheduled", -len(c["suggestions"]), c["name"]))

    phase_model = [round(x, 1) for x in spread_phases(pulls)]
    return {
        "slug": enc["slug"],
        "wclEncounterId": enc["wcl_encounter_id"],
        "encounterName": ranks[0].get("encounterName") or enc.get("name") or enc["slug"],
        "sample": {
            "requested": sample_size,
            "readable": len(profiles),
            "used": len(pulls),
            "unreadable": unreadable,
            "excludedForPhaseStructure": excluded,
            "medianDuration": round(statistics.median([p["duration"] for p in pulls]), 1),
            "durationRange": [
                round(min(p["duration"] for p in pulls), 1),
                round(max(p["duration"] for p in pulls), 1),
            ],
        },
        "phaseModel": phase_model,
        "cooldowns": cooldowns,
    }


def spread_phases(pulls):
    """Median start second of each phase across the pool — the plan's own phase ruler."""
    n = len(pulls[0]["phases"])
    return [statistics.median([p["phases"][i] for p in pulls]) for i in range(n)]


# ----------------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--zone", required=True, help="zone slug, e.g. venomous-abyss")
    ap.add_argument("--spec", required=True, help="spec slug, e.g. balance-druid")
    ap.add_argument(
        "--difficulty", type=int, default=15, choices=sorted(WCL_DIFFICULTY),
        help="in-game difficulty: 14 Normal, 15 Heroic, 16 Mythic (NOT the WCL numbering)",
    )
    ap.add_argument("--sample", type=int, default=25, help="pulls to sample per encounter")
    ap.add_argument("--encounter", action="append", help="limit to these encounter slugs")
    ap.add_argument("--out", type=pathlib.Path,
                    help="write one whole-tier file here instead of the per-encounter "
                         "plan_suggestions/<spec>-<difficulty>.json files")
    ap.add_argument("--refresh", action="store_true", help="bypass the ranking cache")
    args = ap.parse_args(argv)

    encounters = [e for e in D.encounters(args.zone) if e.get("wcl_encounter_id")]
    if args.encounter:
        wanted = set(args.encounter)
        encounters = [e for e in encounters if e["slug"] in wanted]
    if not encounters:
        raise SystemExit("no encounters matched")

    spec_doc = json.loads(D.talent_tree_path(args.spec).read_text(encoding="utf-8"))
    class_name = spec_doc["spec"]["class_name"]
    spec_name = spec_doc["spec"]["spec_name"]

    catalog_path = D.spec_cooldowns_path(args.spec)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}

    out_rows = []
    for enc in encounters:
        print(f"  {enc['slug']} ...", file=sys.stderr, flush=True)
        row = build_encounter(enc, class_name, spec_name, args.difficulty, args.sample, catalog, args.refresh)
        if row.get("skipped"):
            print(f"    skipped: {row['skipped']}", file=sys.stderr)
        else:
            n = sum(len(c["suggestions"]) for c in row["cooldowns"])
            print(f"    {row['sample']['used']} pulls, {n} suggested row(s)", file=sys.stderr)
        out_rows.append(row)

    doc = {
        "meta": {
            "zone": args.zone,
            "spec": args.spec,
            "difficulty": args.difficulty,
            "wclDifficulty": WCL_DIFFICULTY[args.difficulty],
            "class": class_name,
            "specName": spec_name,
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "generator": "tools/warcraftlogs/plan_suggestion_sync.py",
            "catalog": D.rel(catalog_path) if catalog_path.exists() else None,
            "parameters": {
                "sample": args.sample,
                "minRechargeSeconds": MIN_RECHARGE_S,
                "tightIqrSeconds": TIGHT_IQR_S,
                "minSupport": MIN_SUPPORT,
                "anchorWindowSeconds": ANCHOR_WINDOW_S,
            },
            "readMe": (
                "Suggestions, not decisions. Every row carries the spread and the pull count "
                "behind it; a wide spread means the field disagrees, which is information "
                "about the fight rather than a number to copy. Times are phase-relative "
                "because kill times are not comparable."
            ),
        },
        "encounters": out_rows,
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        written = [args.out]
    else:
        written = D.write_tier(args.zone, f"plan_suggestions/{args.spec}-{args.difficulty}.json", doc["meta"], out_rows)
    for out in written:
        print(f"wrote {D.rel(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
