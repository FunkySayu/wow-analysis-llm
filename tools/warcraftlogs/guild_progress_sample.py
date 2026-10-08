#!/usr/bin/env python3
"""Pick a random *publicly logged* guild from a boss's progress ladder, and reconstruct
its progression on that boss: every report that holds a pull, up to and including the
first kill.

    python3 tools/warcraftlogs/guild_progress_sample.py --encounter sszorak --difficulty mythic \\
        --range 101-110 --seed 7

The progress ladder is what the site shows as the kill race for one boss: guilds ordered
by when they first killed it. Many guilds on it log privately, and a private guild's rank
carries no report at all. So "pick rank 104" is not a well-posed request -- the honest
version is "pick a random rank in [lo, hi] that actually has public logs", which is what
this does: it builds the full candidate list for the range, shuffles it under a stated
seed, and pops until one is usable. Every rejected rank is reported with its reason, so
the sample is auditable rather than merely random.

What "progression" means here
-----------------------------
All pulls on the target encounter, **at the target difficulty**, in the guild's own
reports, ordered by wall-clock time and truncated at the first kill. Reports after the
kill are excluded; within the kill report, pulls after the kill are excluded too.

Four traps this exists to handle, each of which produces a wrong answer rather than an
error:

1. **The ladder's kill report and the guild's own reports disagree, in both directions.**
   For Opposite on Sszorak the ladder cites ``RW2Qd7jzF4a83Bn9``, which has ``guild:
   null`` and owner "slt" -- a raider's personal upload of the night the guild also logged
   as ``wX9xBbAKQqzJDWHZ``. Merging it in unconditionally double-counts all ten kill-night
   pulls. But for HKM on Vashnik the opposite holds: their guild reports contain no kill
   until a reclear three days later, because the progression night was uploaded with no
   guild tag, and refusing to merge answers "5 pulls" instead of 13. So the ladder's
   report is fetched and merged **only when the guild's own reports do not already contain
   the ladder's first kill**, and deduplication prefers the guild's copy.

2. **One raid night is often two reports, split by difficulty.** Opposite's "Week 2 Day 2"
   is both ``Qh1AMnm7F2PJkBKq`` (all difficulty 5) and ``2xXyRtq4WdTLj3p6`` (all
   difficulty 4), sharing a ``startTime`` to the millisecond. They look like duplicate
   uploads and are not. Filtering on ``difficulty`` is what separates them, and the
   heroic report genuinely holds one Sszorak pull that must not be counted.

3. **Clock skew between two uploads of the same kill is real.** The kill fight in
   ``wX9xBbAKQqzJDWHZ`` ends 4.1s *after* the ladder's ``killTime`` for the same kill.
   Truncating on "absolute end <= ladder killTime" would therefore drop the kill itself.
   The cut is made at the first fight with ``kill: true`` in the collected reports, and
   the ladder time is compared against it with a tolerance instead of driving it.

4. **A rank with a non-null report code is not yet a usable guild.** The ladder's
   ``report.code`` being present is necessary but not sufficient -- the guild must also
   have readable reports holding at least one pull at the requested difficulty. Each
   candidate is tested and the failures are printed with their reason, so a draw that
   walked past six ranks says so.

Genuine duplicate uploads (the same pull present in two reports) are detected by
absolute start time and reported as a diagnostic, not silently merged away.

Cost
----
One ladder page per 50 ranks in the range, and per candidate tried, one report-list query
(fights are nested in it, so a guild's whole history is a single request) plus at most one
report fetch for the ladder fallback. Ladder pages, report lists and reports are cached
under ``.wclcache/``; ``--refresh`` bypasses them. ``--all-zones`` drops the zone filter
and is markedly slower -- Opposite has 362 reports overall against 20 in this zone.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "warcraftlogs"))

from lib import wclapi as W  # noqa: E402

#: Difficulty name -> WarcraftLogs raid difficulty id. The in-game numbering (14/15/16)
#: used elsewhere in this repo is a *different* scheme; mixing them silently samples the
#: wrong bracket, which is exactly the "don't mix up heroic / normal / mythic" failure.
DIFFICULTIES = {"lfr": 1, "normal": 3, "heroic": 4, "mythic": 5}

#: Ranks per ladder page. Fixed by the API (``fightRankings`` returns ``count: 50``);
#: asserted at runtime rather than trusted, because a change here would silently shift
#: every reported rank number.
PAGE_SIZE = 50

#: How far the guild's own first kill may sit from the ladder's ``killTime`` before the
#: cross-check is reported as a disagreement. Sized for upload clock skew between two
#: recordings of one kill (measured: 4.1s), not for a different pull.
KILL_SKEW_TOLERANCE_MS = 120_000

#: Two matching fights starting within this of each other, in different reports, are the
#: same pull recorded twice rather than a genuine re-pull. A boss cannot be pulled twice
#: this close together.
DUPLICATE_WINDOW_MS = 10_000

LADDER_Q = """query { worldData { encounter(id: %d) { name zone { id name }
  fightRankings(metric: progress, difficulty: %d, page: %d) } } }"""

#: Reports fetched per request. 100 with ``fights`` nested exceeds WarcraftLogs' 50000
#: query-complexity cap and returns an *error* rather than a short page, so this is a hard
#: ceiling and not a tuning knob.
REPORTS_PAGE = 50

REPORTS_Q = """query { reportData { reports(guildID: %d, %slimit: %d, page: %d) {
  has_more_pages total
  data { code title startTime endTime owner { name } zone { id name }
         fights(killType: Encounters) { id encounterID difficulty kill
                                        startTime endTime } } } } }"""

ZONES_Q = """query { worldData { zones { id name encounters { id name } } } }"""


# --------------------------------------------------------------------- encounter lookup


def _slug(text):
    return "".join(c for c in text.lower() if c.isalnum())


def resolve_encounter(token, refresh=False):
    """Accept a WCL encounter id, a boss name, or a slug like ``sszorak``.

    Names are matched against every zone's encounter list rather than against this repo's
    ``data/raid/<patch>/<tier>/<nn>_<boss>/journal.json``, so the tool works on tiers this repo has never pulled.
    """
    if str(token).isdigit():
        eid = int(token)
        r = W.query("query { worldData { encounter(id: %d) { id name zone { id name } } } }" % eid)
        enc = (r.get("data") or {}).get("worldData", {}).get("encounter")
        if not enc:
            sys.exit("No encounter with id %d" % eid)
        return enc

    zones = W.cached("_world", "zones", lambda: W.query(ZONES_Q), refresh)
    want = _slug(token)
    hits = []
    for z in zones["data"]["worldData"]["zones"]:
        for e in z.get("encounters") or []:
            s = _slug(e["name"])
            if s == want or want in s:
                hits.append({"id": e["id"], "name": e["name"], "zone": {"id": z["id"], "name": z["name"]}})
    if not hits:
        sys.exit("No encounter matching %r. Pass a numeric WCL encounter id instead." % token)
    exact = [h for h in hits if _slug(h["name"]) == want]
    if len(exact) == 1:
        return exact[0]
    if len(hits) == 1:
        return hits[0]
    sys.exit(
        "Ambiguous encounter %r -- matches:\n%s"
        % (token, "\n".join("  %d  %s (%s)" % (h["id"], h["name"], h["zone"]["name"]) for h in hits))
    )


# ---------------------------------------------------------------------------- the ladder


def ladder_page(encounter_id, wcl_difficulty, page, refresh=False):
    def go():
        return W.query(LADDER_Q % (encounter_id, wcl_difficulty, page))

    key = "ladder|%d|%d|%d" % (encounter_id, wcl_difficulty, page)
    r = W.cached("_ladder", key, go, refresh)
    enc = (r.get("data") or {}).get("worldData", {}).get("encounter")
    if not enc:
        sys.exit("Encounter %d returned no data" % encounter_id)
    return enc["fightRankings"]


def ladder_range(encounter_id, wcl_difficulty, lo, hi, refresh=False):
    """Ranked entries for ranks [lo, hi], 1-based, each tagged with its rank."""
    out = []
    first_page = (lo - 1) // PAGE_SIZE + 1
    last_page = (hi - 1) // PAGE_SIZE + 1
    for page in range(first_page, last_page + 1):
        fr = ladder_page(encounter_id, wcl_difficulty, page, refresh)
        rankings = fr.get("rankings") or []
        count = fr.get("count")
        if count and count != PAGE_SIZE and fr.get("hasMorePages"):
            sys.exit(
                "Ladder page size is %d, not the assumed %d -- every rank number below "
                "would be wrong. Update PAGE_SIZE." % (count, PAGE_SIZE)
            )
        for i, entry in enumerate(rankings):
            rank = (page - 1) * PAGE_SIZE + i + 1
            if lo <= rank <= hi:
                entry = dict(entry)
                entry["rank"] = rank
                out.append(entry)
        if not fr.get("hasMorePages"):
            break
    return sorted(out, key=lambda e: e["rank"])


def describe(entry):
    guild = entry.get("guild") or {}
    server = entry.get("server") or {}
    return {
        "rank": entry["rank"],
        "guild": guild.get("name"),
        "guildId": guild.get("id"),
        "server": server.get("name"),
        "region": server.get("region"),
        "killTime": entry.get("killTime"),
        "ladderReport": (entry.get("report") or {}).get("code"),
    }


# ------------------------------------------------------------------- guild report history


def guild_reports(guild_id, zone_id, refresh=False, all_zones=False):
    """Every report the guild owns, newest first, with its encounter fights nested.

    ``zone_id`` narrows the query hard -- Opposite has 362 reports overall and 20 in the
    Venomous Abyss -- at the cost of missing a progression pull logged under a report the
    site filed against a different zone. ``all_zones`` trades the cost back for coverage.
    """

    def go():
        out, page = [], 1
        while True:
            zone_arg = "" if all_zones else "zoneID: %d, " % zone_id
            r = W.query(REPORTS_Q % (guild_id, zone_arg, REPORTS_PAGE, page))
            if r.get("errors"):
                raise RuntimeError(
                    "report list query failed: %s" % json.dumps(r["errors"])[:300])
            block = ((r.get("data") or {}).get("reportData") or {}).get("reports")
            if not block:
                break
            out.extend(block.get("data") or [])
            if not block.get("has_more_pages"):
                break
            page += 1
            if page > 40:  # 2000 reports; a guild this size means the filter is wrong
                break
        return out

    key = "guildreports|%d|%s|%d" % (guild_id, "all" if all_zones else str(zone_id), 1)
    return W.cached("_guild", key, go, refresh)


REPORT_Q = """query { reportData { report(code: "%s") {
  code title startTime endTime owner { name } zone { id name }
  fights(killType: Encounters) { id encounterID difficulty kill startTime endTime } } } }"""


def fetch_report(code, refresh=False):
    """One report with its encounter fights, shaped like a row of the guild report list."""

    def go():
        return W.query(REPORT_Q % code)

    r = W.cached("_report", "report|%s" % code, go, refresh)
    return ((r.get("data") or {}).get("reportData") or {}).get("report")


def _collect(reports, encounter_id, wcl_difficulty, source):
    out = []
    for rep in reports or []:
        for f in rep.get("fights") or []:
            if f.get("encounterID") != encounter_id or f.get("difficulty") != wcl_difficulty:
                continue
            out.append(
                {
                    "code": rep["code"],
                    "title": rep.get("title"),
                    "reportStart": rep["startTime"],
                    "fightId": f["id"],
                    "kill": bool(f.get("kill")),
                    "startAbs": rep["startTime"] + f["startTime"],
                    "endAbs": rep["startTime"] + f["endTime"],
                    "source": source,
                }
            )
    return out


def progression(reports, encounter_id, wcl_difficulty, ladder_entry, refresh=False):
    """Per-report pull counts on one encounter/difficulty, truncated at the first kill.

    The guild's own reports are the source. The ladder's kill report is pulled in **only**
    when the guild's reports do not contain the ladder's first kill -- the two failure
    modes are opposite and both are real:

    * Opposite/Sszorak: the guild logged the kill *and* a raider uploaded the same night
      privately. Merging unconditionally would double-count. The guild's copy is there, so
      nothing is merged.
    * HKM/Vashnik: the guild's own reports hold no kill until a reclear three days later,
      because the progression night was uploaded by a member with no guild tag. Without the
      merge the answer is "5 pulls", which is wrong by every pull that mattered.

    Deduplication prefers the guild's own copy, so per-report attribution stays the guild's
    even when both copies are present.
    """
    ladder_kill_time = (ladder_entry or {}).get("killTime")
    ladder_code = ((ladder_entry or {}).get("report") or {}).get("code")

    pulls = _collect(reports, encounter_id, wcl_difficulty, "guild")

    represented = bool(ladder_kill_time) and any(
        p["kill"] and abs(p["endAbs"] - ladder_kill_time) <= KILL_SKEW_TOLERANCE_MS for p in pulls
    )
    merged = None
    if ladder_code and ladder_kill_time and not represented:
        lrep = fetch_report(ladder_code, refresh)
        extra = _collect([lrep] if lrep else [], encounter_id, wcl_difficulty, "ladder")
        if extra:
            pulls += extra
            merged = {
                "code": ladder_code,
                "owner": (lrep.get("owner") or {}).get("name"),
                "guildTagged": bool(lrep.get("guild")),
                "pullsAdded": len(extra),
            }

    pulls.sort(key=lambda p: (p["startAbs"], 0 if p["source"] == "guild" else 1, p["code"], p["fightId"]))

    # Same pull recorded by two uploads: report it, and keep the guild's copy.
    duplicates, kept, last = [], [], None
    for p in pulls:
        if last and p["code"] != last["code"] and abs(p["startAbs"] - last["startAbs"]) <= DUPLICATE_WINDOW_MS:
            duplicates.append({"kept": last["code"], "dropped": p["code"], "startAbs": p["startAbs"]})
            continue
        kept.append(p)
        last = p
    pulls = kept

    kill_index = next((i for i, p in enumerate(pulls) if p["kill"]), None)
    if kill_index is not None:
        cut_reason = "first kill found in the collected reports"
        pulls = pulls[: kill_index + 1]
        kill_pull = pulls[-1]
    elif ladder_kill_time:
        cut_reason = "no kill in any collected report; cut at the ladder's killTime"
        pulls = [p for p in pulls if p["startAbs"] <= ladder_kill_time]
        kill_pull = None
    else:
        cut_reason = "no kill found and no ladder killTime; nothing truncated"
        kill_pull = None

    rows, order = [], []
    for p in pulls:
        if p["code"] not in order:
            order.append(p["code"])
    for code in order:
        mine = [p for p in pulls if p["code"] == code]
        rows.append(
            {
                "code": code,
                "url": "https://www.warcraftlogs.com/reports/%s" % code,
                "title": mine[0]["title"],
                "startTime": mine[0]["reportStart"],
                "source": mine[0]["source"],
                "pulls": len(mine),
                "containsFirstKill": any(p["kill"] for p in mine),
                "fightIds": [p["fightId"] for p in mine],
            }
        )

    skew = kill_pull["endAbs"] - ladder_kill_time if (kill_pull and ladder_kill_time) else None

    return {
        "reports": rows,
        "totalPulls": sum(r["pulls"] for r in rows),
        "cutReason": cut_reason,
        "killFound": kill_pull is not None,
        "killReport": kill_pull["code"] if kill_pull else None,
        "killFightId": kill_pull["fightId"] if kill_pull else None,
        "mergedLadderReport": merged,
        "ladderKillSkewMs": skew,
        "ladderKillAgrees": (skew is None or abs(skew) <= KILL_SKEW_TOLERANCE_MS),
        "duplicatePulls": duplicates,
    }


# ------------------------------------------------------------------------------ selection


def usable(entry, encounter, wcl_difficulty, refresh, all_zones):
    """Try one ladder entry. Returns (result, rejection_reason)."""
    guild = entry.get("guild") or {}
    if not guild.get("id"):
        return None, "no guild attached to the ranking"
    if not (entry.get("report") or {}).get("code"):
        return None, "private logs (ladder carries no report)"

    reports = guild_reports(guild["id"], encounter["zone"]["id"], refresh, all_zones)
    if not reports:
        return None, "guild has no readable reports in this zone"

    prog = progression(reports, encounter["id"], wcl_difficulty, entry, refresh)
    if not prog["reports"]:
        return None, "no pulls on this boss at this difficulty in the guild's own reports"
    return prog, None


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--encounter", required=True, help="boss name, slug, or WCL encounter id")
    ap.add_argument(
        "--difficulty", default="mythic", choices=sorted(DIFFICULTIES),
        help="raid difficulty of the ladder AND of the counted pulls (default: mythic)",
    )
    ap.add_argument("--range", required=True, help="inclusive rank range, e.g. 101-110")
    ap.add_argument("--count", type=int, default=1, help="how many distinct usable guilds to draw")
    ap.add_argument("--seed", type=int, help="seed the shuffle for a reproducible pick")
    ap.add_argument("--guild-id", type=int, help="skip the draw and report this guild (for testing)")
    ap.add_argument("--all-zones", action="store_true", help="scan every guild report, not just the boss's zone")
    ap.add_argument("--refresh", action="store_true", help="bypass the ladder/report caches")
    ap.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = ap.parse_args(argv)

    try:
        lo, hi = (int(x) for x in args.range.replace("..", "-").split("-", 1))
    except ValueError:
        sys.exit("--range must look like 101-110")
    if lo < 1 or hi < lo:
        sys.exit("--range must be increasing and start at 1 or above")

    wcl_difficulty = DIFFICULTIES[args.difficulty]
    encounter = resolve_encounter(args.encounter, args.refresh)
    candidates = ladder_range(encounter["id"], wcl_difficulty, lo, hi, args.refresh)
    if not candidates:
        sys.exit(
            "Ladder for %s (%s) has no entries in ranks %d-%d"
            % (encounter["name"], args.difficulty, lo, hi)
        )

    pool = list(candidates)
    if args.guild_id:
        pool = [e for e in pool if (e.get("guild") or {}).get("id") == args.guild_id]
        if not pool:
            sys.exit("Guild id %d is not in ranks %d-%d" % (args.guild_id, lo, hi))
    else:
        random.Random(args.seed).shuffle(pool)

    # Draws are sequential over one shuffled pool, so `--count N` with a given seed yields
    # the same first guild as `--count 1` with that seed, and adding a guild never reshuffles
    # the ones already drawn.
    rejected, selections = [], []
    for entry in pool:
        if len(selections) >= args.count:
            break
        prog, reason = usable(entry, encounter, wcl_difficulty, args.refresh, args.all_zones)
        if prog:
            selections.append({"guild": describe(entry), "progression": prog})
        else:
            rejected.append(dict(describe(entry), reason=reason))

    result = {
        "encounter": {"id": encounter["id"], "name": encounter["name"], "zone": encounter["zone"]},
        "difficulty": args.difficulty,
        "wclDifficulty": wcl_difficulty,
        "rankRange": [lo, hi],
        "seed": args.seed,
        "requested": args.count,
        "candidatesInRange": [describe(e) for e in candidates],
        "rejected": rejected,
        "selections": selections,
        # Kept so a --count 1 consumer keeps working unchanged.
        "selected": selections[0]["guild"] if selections else None,
        "progression": selections[0]["progression"] if selections else None,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if len(selections) == args.count else 1

    render(result)
    return 0 if len(selections) == args.count else 1


def render(res):
    enc, lo, hi = res["encounter"], *res["rankRange"]
    print("%s -- %s (encounter %d, %s)" % (enc["name"], res["difficulty"], enc["id"], enc["zone"]["name"]))
    print("Progress ladder ranks %d-%d, %d entries%s"
          % (lo, hi, len(res["candidatesInRange"]),
             "" if res["seed"] is None else ", seed %d" % res["seed"]))
    print()
    n_priv = sum(1 for c in res["candidatesInRange"] if not c["ladderReport"])
    print("  %d of %d ranks carry public logs, %d log privately."
          % (len(res["candidatesInRange"]) - n_priv, len(res["candidatesInRange"]), n_priv))

    sels = res.get("selections") or []
    if not sels:
        print("\nNo guild in this range has usable public logs.")
        return
    if len(sels) < res.get("requested", 1):
        print("\nOnly %d of the %d requested guilds were usable; the range ran out."
              % (len(sels), res["requested"]))

    for s in sels:
        sel, prog = s["guild"], s["progression"]
        print("\n%s" % ("-" * 72))
        print("Rank %d  %s  (%s-%s)" % (sel["rank"], sel["guild"], sel["server"], sel["region"]))
        print("%s" % ("-" * 72))
        for r in prog["reports"]:
            note = ", including the first kill for that guild" if r["containsFirstKill"] else ""
            print("* %s %d pull%s%s" % (r["url"], r["pulls"], "" if r["pulls"] == 1 else "s", note))
        n = len(prog["reports"])
        print("Total: %d pulls across %d report%s." % (prog["totalPulls"], n, "" if n == 1 else "s"))

        m = prog["mergedLadderReport"]
        if m:
            print("  note: the guild's own reports held no first kill, so the ladder's kill report")
            print("        %s was merged in (owner %s, %s): %d pulls."
                  % (m["code"], m["owner"] or "unknown",
                     "guild-tagged" if m["guildTagged"] else "not guild-tagged", m["pullsAdded"]))
        if prog["ladderKillSkewMs"] is not None and not prog["ladderKillAgrees"]:
            print("  warning: kill cross-check DISAGREES with the ladder by %+.1fs."
                  % (prog["ladderKillSkewMs"] / 1000.0))
        if not prog["killFound"]:
            print("  warning: no kill fight found; %s" % prog["cutReason"])
        if prog["duplicatePulls"]:
            print("  note: %d duplicate pull(s) dropped (same pull in two reports)."
                  % len(prog["duplicatePulls"]))

    if len(sels) > 1:
        print("\n%s" % ("=" * 72))
        print("Overall, %d guilds sampled from ranks %d-%d" % (len(sels), lo, hi))
        print("%s" % ("=" * 72))
        print("  %-5s %-26s %7s %8s" % ("rank", "guild", "pulls", "reports"))
        for s in sorted(sels, key=lambda x: x["guild"]["rank"]):
            print("  %-5d %-26s %7d %8d"
                  % (s["guild"]["rank"], (s["guild"]["guild"] or "-")[:26],
                     s["progression"]["totalPulls"], len(s["progression"]["reports"])))
        pulls = sorted(s["progression"]["totalPulls"] for s in sels)
        reports = sum(len(s["progression"]["reports"]) for s in sels)
        mid = (pulls[len(pulls) // 2] if len(pulls) % 2
               else (pulls[len(pulls) // 2 - 1] + pulls[len(pulls) // 2]) / 2)
        print("  %-32s %7d %8d" % ("TOTAL", sum(pulls), reports))
        print("\n  median %.1f pulls, range %d-%d." % (mid, pulls[0], pulls[-1]))

    if res["rejected"]:
        print("\nRanks skipped during the draw:")
        for r in res["rejected"]:
            print("  %4d  %-28s %s" % (r["rank"], r["guild"] or "-", r["reason"]))


if __name__ == "__main__":
    raise SystemExit(main())
