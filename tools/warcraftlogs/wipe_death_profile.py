#!/usr/bin/env python3
"""What kills people on a boss, measured across a sample of guilds' wipes.

    python3 tools/warcraftlogs/guild_progress_sample.py --encounter vashnik --difficulty mythic \\
        --range 250-500 --count 10 --seed 1 --json > selection.json
    python3 tools/warcraftlogs/wipe_death_profile.py --selection selection.json \\
        --out scratch/vashnik_deaths/deaths.json

Input is a ``guild_progress_sample.py --json`` payload, so the sample is drawn and audited
once and this reads it rather than re-drawing. Every pull that is **not** a kill is a wipe
and is analysed; the kill pull is used only to place the wipes in progression order.

The unit of analysis
--------------------
One death. For each wipe the first five deaths are taken in timestamp order:

* **Deaths 1-3 are classified individually.** These are the deaths that say what the raid
  is failing at, because they happen while the raid is still alive and reacting.
* **Deaths 4 and 5 are used only for their timing.** Once three people are down, further
  deaths mostly measure how fast the pull collapsed, not what went wrong. The gap from the
  first death to the fifth separates a single mass-casualty mechanic (all five inside a few
  seconds) from attrition (a fifth death half a minute later).

How a death is classified
-------------------------
Over the five seconds before death, the classifier looks at the **killing blow's size
relative to the victim's maximum health**, where the blow's size is ``amount + overkill``:
the damage that would have landed on a healthy player. Absorbed damage is deliberately
excluded -- a shield that ate half the hit means the player was not one-shot.

===========================  ===========================================================
bucket                       rule
===========================  ===========================================================
one shot / near one shot     killing blow >= 80% of max health
big hit on low health        killing blow 30-80% of max health
slow bleed                   killing blow < 30% of max health
===========================  ===========================================================

The threshold is on the killing blow alone because that is the axis that distinguishes the
three cases the question asks about. Health before the blow and total damage over the
window are **recorded but not used by the rule**, so they stay available as an independent
check: a "one shot" bucket whose victims were mostly near full health is behaving as
named, and one whose victims were all at 20% is not.

Traps this had to work around
-----------------------------
Both return wrong data rather than an error, and both were hit while writing this:

1. **``targetID`` on a ``DamageTaken`` event query silently drops enemy-sourced hits.**
   Asking for target 23's damage over the window that killed them returned 14 events, all
   of them the player's own self-damage, and neither of the two boss hits that actually
   did the killing. ``filterExpression: "target.id = 23"`` is worse: it returns **zero**
   events, with no error. The only complete answer is the unfiltered query for the window,
   filtered by target in Python.

2. **The Deaths table's ``events`` array is capped at three entries.** It looks like a
   death recap and is not one: every death in the probe carried exactly three events
   spanning as little as 14ms, while the same entry's ``damage.total`` covered five to
   fifteen times that. Its ``deathWindow`` is also adaptive (4.5s to 14.2s observed), not
   the fixed five seconds the question asks for. The table is therefore used only to find
   *who* died and *when*; the sequence comes from raw events over a fixed window.

Cost
----
One Deaths-table query per report (all of its fights at once), then the five-second damage
windows batched into single requests with GraphQL aliases -- ``BATCH`` windows per request
-- rather than one request per death. Everything caches under ``.wclcache/``.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import statistics
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "warcraftlogs"))

from lib import wclapi as W  # noqa: E402

#: Seconds of damage examined before each death. The question asks for five; the Deaths
#: table's own window is adaptive and is not used.
WINDOW_S = 5.0

#: Killing blow as a share of the victim's max health. At or above ONESHOT the blow would
#: have killed a healthy player; below BIGHIT no single blow mattered and the death is
#: accumulation.
ONESHOT = 0.80
BIGHIT = 0.30

#: Deaths classified individually per wipe. Beyond this the deaths measure collapse speed
#: rather than cause.
CLASSIFY_N = 3

#: Deaths collected per wipe. The tail beyond CLASSIFY_N only contributes timing.
COLLECT_N = 5

#: Damage windows per GraphQL request. Each alias adds query complexity against a 50000
#: cap; 8 stays well inside it while cutting request count roughly eightfold.
BATCH = 8

LABELS = {
    "oneshot": "one shot / near one shot",
    "bighit": "big hit on low health",
    "bleed": "slow bleed",
}

DEATHS_Q = """query { reportData { report(code: "%s") {
  table(dataType: Deaths, fightIDs: [%s]) } } }"""


def deaths_table(code, fight_ids, refresh=False):
    """Every death in these fights, as the Deaths table reports them."""

    def go():
        ids = ",".join(str(i) for i in sorted(fight_ids))
        return W.query(DEATHS_Q % (code, ids))

    key = "deaths|%s|%s" % (code, ",".join(str(i) for i in sorted(fight_ids)))
    r = W.cached(code, key, go, refresh)
    table = ((r.get("data") or {}).get("reportData") or {}).get("report", {}).get("table")
    if not table:
        return []
    return ((table.get("data") or {}).get("entries")) or []


def damage_windows(code, windows, refresh=False):
    """Raw DamageTaken events for each (fightID, start, end) window, batched by alias.

    Unfiltered by target on purpose -- see trap 1 in the module docstring. Filtering is
    done by the caller in Python.
    """
    out = {}
    todo = []
    for w in windows:
        key = "dmgwin|%s|%d|%d|%d" % (code, w[0], w[1], w[2])
        path = W._cache_path(code, key)  # noqa: SLF001 - same module's cache layout
        if not refresh and os.path.exists(path):
            try:
                out[w] = json.load(open(path))
                continue
            except Exception:  # noqa: BLE001
                pass
        todo.append((w, key))

    for i in range(0, len(todo), BATCH):
        chunk = todo[i : i + BATCH]
        parts = []
        for n, (w, _key) in enumerate(chunk):
            parts.append(
                'w%d: events(fightIDs: [%d], dataType: DamageTaken, startTime: %d, '
                "endTime: %d, limit: 3000, includeResources: true) { data }" % (n, w[0], w[1], w[2])
            )
        gql = 'query { reportData { report(code: "%s") { %s } } }' % (code, " ".join(parts))
        r = W.query(gql)
        rep = ((r.get("data") or {}).get("reportData") or {}).get("report") or {}
        for n, (w, key) in enumerate(chunk):
            data = ((rep.get("w%d" % n) or {}).get("data")) or []
            out[w] = data
            json.dump(data, open(W._cache_path(code, key), "w"))  # noqa: SLF001
    return out


def classify(events, target_id, death_ts):
    """Turn one victim's five-second damage window into a classified death.

    Returns None when the window holds no damage to this target, which happens when a
    death is not damage-driven (a mechanic that removes the player outright) or when the
    log simply carries no events for it.
    """
    mine = [
        e
        for e in events
        if e.get("targetID") == target_id and e.get("type") == "damage" and e.get("timestamp") <= death_ts
    ]
    if not mine:
        return None
    mine.sort(key=lambda e: e["timestamp"])
    kb = mine[-1]
    max_hp = kb.get("maxHitPoints") or next(
        (e.get("maxHitPoints") for e in reversed(mine) if e.get("maxHitPoints")), None
    )
    if not max_hp:
        return None

    # Damage that would have landed on a healthy player: what got through, plus the excess
    # that had nowhere to go. Absorbed damage is excluded -- a shield means not one-shot.
    blow = (kb.get("amount") or 0) + (kb.get("overkill") or 0)
    kb_share = blow / max_hp

    prior = [e for e in mine[:-1] if e.get("hitPoints") is not None]
    hp_before = prior[-1]["hitPoints"] if prior else blow
    window_damage = sum((e.get("amount") or 0) + (e.get("overkill") or 0) for e in mine)

    if kb_share >= ONESHOT:
        bucket = "oneshot"
    elif kb_share >= BIGHIT:
        bucket = "bighit"
    else:
        bucket = "bleed"

    return {
        "bucket": bucket,
        "killingBlowId": kb.get("abilityGameID"),
        "killingBlowShare": round(kb_share, 4),
        "hpBeforeShare": round(min(hp_before / max_hp, 1.0), 4),
        "windowDamageShare": round(window_damage / max_hp, 4),
        "hits": len(mine),
        "maxHitPoints": max_hp,
    }


def analyse(selection, refresh=False, progress=True):
    encounter = selection["encounter"]
    rows = []
    ability_names = {}

    for sel in selection["selections"]:
        guild = sel["guild"]["guild"]
        rank = sel["guild"]["rank"]
        reports = sel["progression"]["reports"]

        # Progression order across the guild's reports, so pull 1 is their first attempt.
        pulls = []
        for rep in reports:
            for fid in rep["fightIds"]:
                pulls.append({"code": rep["code"], "fightId": fid})
        total = len(pulls)

        by_report = collections.defaultdict(list)
        for p in pulls:
            by_report[p["code"]].append(p["fightId"])

        # One Deaths-table query per report covers all of its fights.
        deaths_by_fight = collections.defaultdict(list)
        fight_meta = {}
        for code, fids in by_report.items():
            meta = W.cached(
                code,
                "fightmeta|%s" % ",".join(map(str, sorted(fids))),
                lambda c=code: W.query(
                    'query { reportData { report(code: "%s") { startTime '
                    "fights(fightIDs: [%s]) { id kill startTime endTime } "
                    "masterData { actors { id name } abilities { gameID name } } } } }"
                    % (c, ",".join(map(str, sorted(fids))))
                ),
                refresh,
            )
            rep = meta["data"]["reportData"]["report"]
            for ab in rep["masterData"]["abilities"]:
                ability_names.setdefault(ab["gameID"], ab["name"])
            for f in rep["fights"]:
                fight_meta[(code, f["id"])] = f
            for d in deaths_table(code, fids, refresh):
                deaths_by_fight[(code, d["fight"])].append(d)

        # Batch every five-second window this guild needs, per report.
        need = collections.defaultdict(list)
        for p in pulls:
            f = fight_meta.get((p["code"], p["fightId"]))
            if not f or f.get("kill"):
                continue
            ds = sorted(deaths_by_fight.get((p["code"], p["fightId"]), []), key=lambda d: d["timestamp"])
            for d in ds[:CLASSIFY_N]:
                need[p["code"]].append(
                    (p["fightId"], int(d["timestamp"] - WINDOW_S * 1000), int(d["timestamp"]) + 1)
                )
        fetched = {}
        for code, ws in need.items():
            if progress:
                print("  %s: %d windows" % (code, len(ws)), file=sys.stderr)
            fetched[code] = damage_windows(code, sorted(set(ws)), refresh)

        for idx, p in enumerate(pulls, start=1):
            f = fight_meta.get((p["code"], p["fightId"]))
            if not f:
                continue
            is_kill = bool(f.get("kill"))
            duration = (f["endTime"] - f["startTime"]) / 1000.0
            ds = sorted(deaths_by_fight.get((p["code"], p["fightId"]), []), key=lambda d: d["timestamp"])
            top = ds[:COLLECT_N]
            death_secs = [round((d["timestamp"] - f["startTime"]) / 1000.0, 1) for d in top]

            classified = []
            if not is_kill:
                for d in top[:CLASSIFY_N]:
                    w = (p["fightId"], int(d["timestamp"] - WINDOW_S * 1000), int(d["timestamp"]) + 1)
                    evs = (fetched.get(p["code"]) or {}).get(w) or []
                    c = classify(evs, d["id"], d["timestamp"])
                    classified.append(
                        {
                            "ordinal": len(classified) + 1,
                            "player": d["name"],
                            "playerClass": d.get("type"),
                            "atSeconds": round((d["timestamp"] - f["startTime"]) / 1000.0, 1),
                            "killingBlowName": (d.get("killingBlow") or {}).get("name"),
                            "classification": c,
                        }
                    )

            cascade = None
            if len(top) >= COLLECT_N:
                cascade = round((top[-1]["timestamp"] - top[0]["timestamp"]) / 1000.0, 1)

            # Progression third. The kill is always the guild's last pull, so the late
            # bucket carries one fewer wipe than the others by construction.
            third = min(int((idx - 1) * 3 / total), 2)

            rows.append(
                {
                    "guild": guild,
                    "rank": rank,
                    "report": p["code"],
                    "fightId": p["fightId"],
                    "pullIndex": idx,
                    "pullsTotal": total,
                    "bucket": ["early", "mid", "late"][third],
                    "kill": is_kill,
                    "durationSeconds": round(duration, 1),
                    "deathsTotal": len(ds),
                    "firstFiveDeathSeconds": death_secs,
                    "cascadeSeconds": cascade,
                    "deaths": classified,
                }
            )

    return {
        "encounter": encounter,
        "difficulty": selection["difficulty"],
        "rankRange": selection["rankRange"],
        "seed": selection["seed"],
        "parameters": {
            "windowSeconds": WINDOW_S,
            "oneshotThreshold": ONESHOT,
            "bigHitThreshold": BIGHIT,
            "classifiedPerWipe": CLASSIFY_N,
            "collectedPerWipe": COLLECT_N,
        },
        "abilityNames": {str(k): v for k, v in sorted(ability_names.items())},
        "pulls": rows,
    }


def summarise(doc):
    """Per-bucket distributions: death timing, and the nature of the death."""
    out = {}
    for b in ("early", "mid", "late"):
        pulls = [p for p in doc["pulls"] if p["bucket"] == b and not p["kill"]]
        deaths = [d for p in pulls for d in p["deaths"]]
        by_ordinal = {}
        for n in (1, 2, 3):
            times = sorted(d["atSeconds"] for d in deaths if d["ordinal"] == n)
            by_ordinal[n] = {
                "n": len(times),
                "median": round(statistics.median(times), 1) if times else None,
                "p25": round(times[len(times) // 4], 1) if times else None,
                "p75": round(times[(3 * len(times)) // 4], 1) if times else None,
                "min": times[0] if times else None,
                "max": times[-1] if times else None,
                "values": times,
            }
        nature = collections.Counter(
            d["classification"]["bucket"] for d in deaths if d["classification"]
        )
        unclassified = sum(1 for d in deaths if not d["classification"])
        cascades = sorted(p["cascadeSeconds"] for p in pulls if p["cascadeSeconds"] is not None)
        out[b] = {
            "wipes": len(pulls),
            "deathsClassified": sum(nature.values()),
            "unclassified": unclassified,
            "deathTimes": by_ordinal,
            "nature": {k: nature.get(k, 0) for k in ("oneshot", "bighit", "bleed")},
            "natureShare": {
                k: round(nature.get(k, 0) / sum(nature.values()), 4) if sum(nature.values()) else 0.0
                for k in ("oneshot", "bighit", "bleed")
            },
            "cascadeSeconds": {
                "n": len(cascades),
                "median": round(statistics.median(cascades), 1) if cascades else None,
                "values": cascades,
            },
            "medianWipeSeconds": round(
                statistics.median([p["durationSeconds"] for p in pulls]), 1
            )
            if pulls
            else None,
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--selection", required=True, type=pathlib.Path,
                    help="guild_progress_sample.py --json output")
    ap.add_argument("--out", type=pathlib.Path, help="write the full JSON here")
    ap.add_argument("--refresh", action="store_true", help="bypass the caches")
    args = ap.parse_args(argv)

    selection = json.load(open(args.selection, encoding="utf-8"))
    doc = analyse(selection, args.refresh)
    doc["summary"] = summarise(doc)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        json.dump(doc, open(args.out, "w", encoding="utf-8"), indent=1)
        print("wrote %s" % args.out, file=sys.stderr)

    s = doc["summary"]
    wipes = sum(s[b]["wipes"] for b in s)
    print("\n%s %s -- %d wipes, %d deaths classified"
          % (doc["encounter"]["name"], doc["difficulty"], wipes,
             sum(s[b]["deathsClassified"] for b in s)))
    for b in ("early", "mid", "late"):
        v = s[b]
        print("\n%s (%d wipes, median wipe %ss)" % (b.upper(), v["wipes"], v["medianWipeSeconds"]))
        for n in (1, 2, 3):
            t = v["deathTimes"][str(n)] if str(n) in v["deathTimes"] else v["deathTimes"][n]
            if t["n"]:
                print("   death %d: median %5.1fs  (p25 %.1f, p75 %.1f, n=%d)"
                      % (n, t["median"], t["p25"], t["p75"], t["n"]))
        tot = v["deathsClassified"]
        for k in ("oneshot", "bighit", "bleed"):
            c = v["nature"][k]
            print("   %-26s %3d  %5.1f%%" % (LABELS[k], c, 100.0 * c / tot if tot else 0))
        if v["unclassified"]:
            print("   %-26s %3d" % ("(no damage window)", v["unclassified"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
