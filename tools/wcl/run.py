#!/usr/bin/env python3
"""Reusable WarcraftLogs checks for this project.

    wsl.exe -d Ubuntu -e python3 tools/wcl/run.py <check> -r <REPORT> -a <ACTOR> [-f <fights>]

Examples
    run.py soul       -r AgzVT69J8kKRWGrt -a Funkywand -f raid
    run.py tom-target -r AgzVT69J8kKRWGrt -a Funkywand -f dungeon
    run.py cooldowns  -r AgzVT69J8kKRWGrt -a Funkywand -f 41
    run.py list       -r AgzVT69J8kKRWGrt

-f accepts: all | encounters | kills | raid | dungeon | 1,5,12   (default: encounters)
Everything is cached under .wclcache/; pass --refresh to bypass.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import checks  # noqa: E402
import wclapi as W  # noqa: E402

CHECKS = {
    "salvo": checks.check_salvo,
    "soul": checks.check_soul,
    "clearcasting": checks.check_clearcasting,
    "tom-target": checks.check_tom_target,
    "cooldowns": checks.check_cooldowns,
    "cd-usage": checks.check_cd_usage,
    "waves": checks.check_waves,
    "gaps": checks.check_gaps,
    "gear": checks.check_gear,
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


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("check", choices=sorted(CHECKS) + ["list", "all"])
    p.add_argument("-r", "--report", required=True)
    p.add_argument("-a", "--actor")
    p.add_argument("-f", "--fights", default="encounters")
    p.add_argument("--refresh", action="store_true")
    a = p.parse_args()

    if a.check == "list":
        cmd_list(a.report)
        return
    if not a.actor:
        p.error("-a/--actor is required for this check")

    aid = W.actor_id(a.report, a.actor)
    fs = W.fights(a.report, a.fights)
    if not fs:
        sys.exit(f"no fights matched selector {a.fights!r}")

    names = [a.check] if a.check != "all" else sorted(CHECKS)
    for i, name in enumerate(names):
        title = f" {name}  |  {a.actor}  |  {len(fs)} fight(s) [{a.fights}] "
        print(("\n" if i else "") + "=" * len(title))
        print(title)
        print("=" * len(title))
        CHECKS[name](a.report, aid, fs)


if __name__ == "__main__":
    main()
