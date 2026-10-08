#!/usr/bin/env python3
"""Reusable WarcraftLogs checks for this project.

    wsl.exe -d Ubuntu -e python3 tools/warcraftlogs/run.py <check> -r <REPORT> -a <ACTOR> [-f <fights>]

Examples
    run.py soul       -r AgzVT69J8kKRWGrt -a Funkywand -f raid
    run.py tom-target -r AgzVT69J8kKRWGrt -a Funkywand -f dungeon
    run.py cooldowns  -r AgzVT69J8kKRWGrt -a Funkywand -f 41
    run.py apl        -r ThRfrJBk1ZGwyCWc -a Funkitty  -f 5
    run.py druid      -r ThRfrJBk1ZGwyCWc -a Funkitty  -f raid   # whole spec suite
    run.py list       -r AgzVT69J8kKRWGrt

A check name runs one check. A GROUP name runs every check in one module:
`common`, `mage` (Arcane), `druid` (Balance) - or `all` for literally everything,
which mixes specs and is rarely what you want once more than one spec exists.

-f accepts: all | encounters | kills | raid | dungeon | 1,5,12   (default: encounters)
Everything is cached under .wclcache/; pass --refresh to bypass.

--json emits the machine-readable payload instead of the text - one envelope per
check, which is what tools/reporting renders. Checks that have not been ported to the
`Check` base class yet have no payload and are reported in `unported`:

    run.py common -r AgzVT69J8kKRWGrt -a Funkywand -f raid --json > scratch/common.json
"""

import argparse
import datetime
import json as jsonlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checks import (common, druid_balance, encounter, mage_arcane, mage_peers,  # noqa: E402
                    peers)
from lib import check as C  # noqa: E402
from lib import wclapi as W  # noqa: E402

CHECKS = {}
CHECKS.update(common.CHECKS)
CHECKS.update(encounter.CHECKS)
CHECKS.update(mage_arcane.CHECKS)
CHECKS.update(mage_peers.CHECKS)
CHECKS.update(druid_balance.CHECKS)
CHECKS.update(peers.CHECKS)

# Group name -> the checks in that module, so a spec's whole suite runs in one go
# without dragging in another spec's checks (which quietly report nothing useful).
GROUPS = {
    "common": sorted(common.CHECKS),
    "fight": sorted(encounter.CHECKS),   # encounter structure, spec-agnostic
    "mage": sorted(mage_arcane.CHECKS),
    "mage-compare": sorted(mage_peers.CHECKS),   # `bar` first, then peers-arc, then peers-buffs
    "druid": sorted(druid_balance.CHECKS),
    "compare": sorted(peers.CHECKS),   # `peers` alone is a check name, not a group
    "all": sorted(CHECKS),
}


def cmd_list(code):
    m = W.report_meta(code)
    print(f"{m['title']}   zone={m['zone']['name'] if m.get('zone') else '?'}")
    print(f"{'id':>4} {'enc':>7} {'kill':>5} {'key':>4} {'dur':>7}  name")
    for f in m["fights"]:
        if not f["encounterID"]:
            continue
        print(f"{f['id']:>4} {f['encounterID']:>7} {str(f.get('kill')):>5} "
              f"{str(f.get('keystoneLevel') or ''):>4} "
              f"{(f['endTime'] - f['startTime']) / 1000:>7.0f}  {f['name']}")
    players = [a["name"] for a in m["masterData"]["actors"] if a["type"] == "Player"]
    shown = ", ".join(players[:40])
    more = f" ... (+{len(players) - 40} more)" if len(players) > 40 else ""
    print(f"\nPlayers ({len(players)}): {shown}{more}")


def emit_json(names, report, out):
    """Write the viz payload: one envelope per ported check.

    A not-yet-ported check is listed by name rather than skipped silently - a
    missing section in a report should be traceable to "nobody ported it" and
    not to a check that ran and found nothing.
    """
    envelopes, unported = [], []
    for name in names:
        entry = CHECKS[name]
        if not C.is_check(entry):
            unported.append(name)
            continue
        envelopes.append(entry(report).envelope())
    payload = {
        "schema": C.SCHEMA,
        "generated": datetime.datetime.now(datetime.timezone.utc)
                             .replace(microsecond=0).isoformat(),
        "context": report.context(),
        "checks": envelopes,
        "unported": unported,
    }
    jsonlib.dump(payload, out, indent=2, default=str)
    out.write("\n")
    if unported:
        print(f"{len(unported)} check(s) have no JSON payload yet: "
              f"{', '.join(unported)}", file=sys.stderr)


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("check", choices=sorted(CHECKS) + ["list"] + sorted(GROUPS))
    p.add_argument("-r", "--report", required=True)
    p.add_argument("-a", "--actor")
    p.add_argument("-f", "--fights", default="encounters")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--json", action="store_true",
                   help="emit the viz payload on stdout instead of the text report")
    p.add_argument("-o", "--out", help="write --json to this file instead of stdout")
    a = p.parse_args()

    if a.check == "list":
        cmd_list(a.report)
        return
    if not a.actor:
        p.error("-a/--actor is required for this check")

    report = C.Report.load(a.report, a.actor, a.fights, refresh=a.refresh)
    names = GROUPS.get(a.check, [a.check])

    if a.json:
        if a.out:
            with open(a.out, "w", encoding="utf-8") as fh:
                emit_json(names, report, fh)
            print(f"wrote {a.out}", file=sys.stderr)
        else:
            emit_json(names, report, sys.stdout)
        return

    for i, name in enumerate(names):
        title = f" {name}  |  {a.actor}  |  {len(report.fights)} fight(s) [{a.fights}] "
        print(("\n" if i else "") + "=" * len(title))
        print(title)
        print("=" * len(title))
        C.instantiate(CHECKS[name], report).print()


if __name__ == "__main__":
    main()
