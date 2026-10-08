#!/usr/bin/env python3
"""Measure a raid tier's fight structure from the top logged pulls.

    python3 tools/warcraftlogs/encounter_profile_sync.py --zone venomous-abyss \\
        --spec balance-druid --difficulty 16 --sample 100

What it answers
---------------
"What actually happens on this boss, when, and to whom" -- measured, not looked up:

* **Phase transitions.** When each phase segment starts and how long it lasts, in seconds,
  with the spread across the pool.
* **Boss ability timings.** Every mechanic the encounter casts, when each occurrence lands
  (both from the pull start and from the start of its own phase segment), and its cadence.
* **Raid composition.** The tank/healer/dps split the field actually brings, and the specs
  in it -- the "2/4/14" question.
* **Damage taken.** What each ability is worth in a real pull, so the journal's tuned
  tooltip number can be sanity-checked against a realised one.

This is the *encounter* counterpart to ``tools/warcraftlogs/plan_suggestion_sync.py``, which measures
what the **player** presses. Same pool, same phase-relative discipline, different subject.
Neither is a check (``tools/warcraftlogs/``): a check answers a question about one report, and both
of these read a hundred strangers' pulls and emit a reviewed dataset under ``data/``.

The five things that make the output trustworthy
------------------------------------------------
1. **An "ability" is a name, not a spell id.** Sszorak's Raging Crosswinds is *five*
   distinct ids (1285419, 1285425, 1285453, 1297096, 1297111) and Mutilate is two
   (1277027 cast, 1277031 effect). Keying on the id would draw five lanes for one mechanic
   and halve every Mutilate count. Abilities are grouped by name and the contributing id
   set is recorded, so the split stays visible rather than being silently chosen between.

2. **One mechanic instance is a burst of casts, not one cast.** Those five Crosswinds ids
   fire *nine casts inside one second* (39.0 -> 40.0), once per gale. Counting raw casts
   says "54 Raging Crosswinds"; counting instances says "6", which is the number a person
   plans against. Casts of one ability within ``COLLAPSE_S`` collapse into a single
   instance that records how many raw casts it absorbed, so an over-collapse is visible in
   the output instead of being invisible in it.

3. **Nothing is timed only from the pull start.** Kill times vary by minutes across a
   ranking pool, so an absolute-second median is a median of different fights. Every
   occurrence carries ``atSeconds`` (from the pull) *and* ``atSegmentSeconds`` (from the
   start of its own phase segment); the second is the stable one and is what a timeline
   should snap to. Same reasoning, and the same measurement, as
   ``tools/warcraftlogs/plan_suggestion_sync.py``'s point 1.

4. **Phases cycle, and a segment index is not a phase number.** Sszorak's transition list
   reads 1, 2, 1, 2, 1, 2, 1 -- it alternates between "Sszorak" and "Howling Maelstrom"
   three times. Treating the position in that list as "the phase" invents a phase 7 that
   does not exist. Each segment here carries its real ``phaseId``, its ``cycle`` (which
   pass through that phase this is) and the phase's *name* from the report's own phase
   table, so "Howling Maelstrom #2" is expressible and "phase 4" is never claimed.

5. **A cast in the enemy stream is not necessarily a boss ability.** WCL attributes some
   player ground effects to a synthetic NPC actor called "Environment" flagged
   ``subType: Boss``: on the reference Sszorak pull, ``hostilityType: Enemies`` returns 48
   casts of **Anti-Magic Zone (145629)** -- a Death Knight raid cooldown -- indistinguishable
   by shape from a real mechanic. Nothing here filters that by hand. Instead every logged
   ability is joined against ``data/raid/<patch>/<tier>/<nn>_<boss>/journal.json`` (the Adventure Journal catalogue,
   built by ``tools/game_knowledge/journal_sync.py``) and the join result is recorded per ability, with
   both sides' misses reported: ``inJournal`` false is the flag, and ``journalOnly`` lists
   catalogued abilities the pool never cast, which is how a mechanic that only appears in a
   phase the top 100 never reach becomes visible rather than absent.

Cost
----
One combined GraphQL query per pull (fights + phases + playerDetails + masterData +
enemy casts) costs ~5.3 rate-limit points against a 3600/hour budget, versus ~8 for the
same data fetched as four queries. A 100-pull sample of seven encounters is therefore
~3.7k points and does not fit in one hour: the run checks the remaining budget and sleeps
until reset rather than failing partway through a boss. Everything is cached under
``.wclcache/`` so a re-run is free.
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

from lib import wclapi as W  # noqa: E402

#: In-game difficulty (what the site stores) -> WarcraftLogs raid difficulty. The two
#: numbering schemes do not match and mixing them silently samples the wrong bracket.
#: Same map, same reason, as tools/warcraftlogs/plan_suggestion_sync.py.
WCL_DIFFICULTY = {14: 3, 15: 4, 16: 5}

#: Casts of one ability closer together than this are one mechanic instance. Calibrated
#: against the widest real burst in the sample (Raging Crosswinds' nine casts spanning 1.0s)
#: and the tightest real repeat (Ravage at 186.1 and 190.0, 3.9s apart), so the threshold
#: sits with room on both sides. ``rawCasts`` on every instance is what makes a wrong
#: choice here detectable.
COLLAPSE_S = 2.0

#: Report an occurrence only when this share of the pulls that *reached its segment* had
#: one. Below it, the row is one raid's variation rather than the fight's structure.
MIN_OCCURRENCE_SUPPORT = 0.5

#: A segment is reported when at least this many pulls reached it. Late cycles of a
#: repeating phase only exist in long kills, and a "median" over two pulls is not one.
MIN_SEGMENT_PULLS = 5

RANK_Q = """query { worldData { encounter(id: %d) { name
  characterRankings(className: "%s", specName: "%s",
                    difficulty: %d, metric: dps, page: %d) } } }"""

#: Everything one pull needs, in one request. See the module docstring's "Cost".
PULL_Q = """query { reportData { report(code: "%(code)s") {
  fights(fightIDs: [%(fid)d]) { id name encounterID difficulty kill startTime endTime
                                phaseTransitions { id startTime } }
  phases { encounterID phases { id name isIntermission } }
  playerDetails(fightIDs: [%(fid)d], includeCombatantInfo: false)
  masterData { actors { id name type subType } abilities { gameID name } }
  events(fightIDs: [%(fid)d], dataType: Casts, hostilityType: Enemies,
         limit: 10000, startTime: 0, endTime: 999999999) { data nextPageTimestamp }
} } }"""

DAMAGE_Q = """query { reportData { report(code: "%s") {
  table(dataType: DamageTaken, fightIDs: [%d], hostilityType: Friendlies) } } }"""


# ------------------------------------------------------------------------ budgeting


#: Sleeping for the hourly reset lives in the API layer (``wclapi.wait_for_budget``) rather
#: than here: ``tools/warcraftlogs/plan_suggestion_sync.py`` walks the same pool for the same reason and
#: needs the identical guard, and a second copy would drift.
wait_for_budget = W.wait_for_budget


# -------------------------------------------------------------------------- sampling


def rankings(encounter_id, class_name, spec_name, wcl_difficulty, sample, refresh=False):
    """The best ``sample`` logged pulls for this encounter, DPS-descending.

    WCL pages rankings 100 at a time. A pool can be smaller than asked for -- Mythic
    progression on a fresh tier thins out sharply on the last bosses -- and that is
    reported by the caller rather than treated as an error.
    """

    def go():
        out = []
        for page in range(1, (sample // 100) + 2):
            r = W.query(RANK_Q % (encounter_id, class_name, spec_name, wcl_difficulty, page))
            enc = r["data"]["worldData"]["encounter"]
            if enc is None:
                return []
            cr = enc["characterRankings"]
            out.extend(cr["rankings"])
            if not cr.get("hasMorePages") or len(out) >= sample:
                break
        return out[:sample]

    key = "encprof|%d|%s|%s|%d|%d" % (encounter_id, class_name, spec_name, wcl_difficulty, sample)
    return W.cached("_pool", key, go, refresh)


def distinct_pulls(ranks):
    """Collapse rankings to distinct (report, fight) pairs, keeping the best-ranked name.

    Two Balance Druids in the same raid produce two rankings for one pull. Measuring that
    pull twice would double its weight in every median for no reason.
    """
    seen = {}
    for r in ranks:
        key = (r["report"]["code"], r["report"]["fightID"])
        if key not in seen:
            seen[key] = r
    return list(seen.values())


# ---------------------------------------------------------------------------- phases


def segments_of(fight, phase_names):
    """The fight's phase segments, each with its real phase id, cycle and name.

    See the module docstring, point 4: the index in ``phaseTransitions`` is a *segment*
    number, not a phase number, because a boss can return to an earlier phase.
    """
    t0, t1 = fight["startTime"], fight["endTime"]
    trans = list(fight.get("phaseTransitions") or [])
    if not trans or trans[0]["startTime"] > t0:
        trans.insert(0, {"id": 1, "startTime": t0})

    seen = collections.Counter()
    out = []
    for i, tr in enumerate(trans):
        pid = tr["id"]
        seen[pid] += 1
        end = trans[i + 1]["startTime"] if i + 1 < len(trans) else t1
        out.append(
            {
                "index": i + 1,
                "phaseId": pid,
                "cycle": seen[pid],
                "name": phase_names.get(pid) or f"Phase {pid}",
                "start": (tr["startTime"] - t0) / 1000.0,
                "end": (end - t0) / 1000.0,
            }
        )
    return out


def segment_of(segments, t):
    """The segment a fight-relative second falls in."""
    chosen = segments[0]
    for s in segments:
        if s["start"] <= t:
            chosen = s
        else:
            break
    return chosen


# ------------------------------------------------------------------------ one pull


def pull_profile(rank, encounter_id):
    """One sampled pull, reduced to what a profile needs.

    Returns a ``{"skipped": ...}`` row for a pull that cannot be read (a private report, a
    deleted fight) so the caller can count and report it rather than treating it as an
    empty pull.
    """
    code, fid = rank["report"]["code"], rank["report"]["fightID"]
    try:
        rep = W.cached(
            code,
            f"encprof|{fid}",
            lambda: W.query(PULL_Q % {"code": code, "fid": fid})["data"]["reportData"]["report"],
        )
        fights = rep["fights"]
        if not fights:
            raise ValueError("fight not present in report")
        fight = fights[0]
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - one unreadable pull must not end the run
        return {"skipped": f"{type(exc).__name__}: {exc}", "code": code, "fight": fid}

    t0, t1 = fight["startTime"], fight["endTime"]
    phase_names = {}
    for block in rep.get("phases") or []:
        if block.get("encounterID") == encounter_id:
            phase_names = {p["id"]: p["name"] for p in block.get("phases") or []}
    segments = segments_of(fight, phase_names)

    master = rep.get("masterData") or {}
    names = {a["gameID"]: a.get("name") for a in master.get("abilities") or []}
    actors = {a["id"]: a for a in master.get("actors") or []}

    # Group raw casts by ability *name* (docstring point 1), keeping the ids and the
    # casting NPC so a name collision or an environment-sourced cast stays diagnosable.
    raw = collections.defaultdict(list)
    ids = collections.defaultdict(set)
    sources = collections.defaultdict(collections.Counter)
    events = (rep.get("events") or {}).get("data") or []
    truncated = bool((rep.get("events") or {}).get("nextPageTimestamp"))
    for e in events:
        if e.get("type") != "cast":
            continue
        gid = e.get("abilityGameID")
        name = names.get(gid)
        if not name:
            continue
        raw[name].append((e["timestamp"] - t0) / 1000.0)
        ids[name].add(gid)
        src = actors.get(e.get("sourceID"))
        sources[name][src["name"] if src else "?"] += 1

    # Collapse a burst into one instance (docstring point 2).
    abilities = {}
    for name, times in raw.items():
        times.sort()
        instances, cur = [], [times[0]]
        for t in times[1:]:
            if t - cur[-1] <= COLLAPSE_S:
                cur.append(t)
            else:
                instances.append(cur)
                cur = [t]
        instances.append(cur)
        abilities[name] = {
            "ids": sorted(ids[name]),
            "sources": [s for s, _ in sources[name].most_common()],
            "instances": [{"at": round(g[0], 1), "rawCasts": len(g)} for g in instances],
        }

    details = ((rep.get("playerDetails") or {}).get("data") or {}).get("playerDetails") or {}
    comp, specs = {}, collections.Counter()
    for role in ("tanks", "healers", "dps"):
        members = details.get(role) or []
        comp[role] = len(members)
        for m in members:
            for s in m.get("specs") or []:
                spec = s.get("spec") if isinstance(s, dict) else s
                specs[f"{spec} {m.get('type')}"] += 1

    return {
        "code": code,
        "fight": fid,
        "duration": (t1 - t0) / 1000.0,
        "kill": bool(fight.get("kill")),
        "segments": segments,
        "abilities": abilities,
        "composition": comp,
        "specs": specs,
        "eventsTruncated": truncated,
    }


# ----------------------------------------------------------------------- aggregation


def spread(values):
    """Median and quartiles. Same shape as plan_suggestion_sync's, so the two datasets
    read alike."""
    values = sorted(values)
    if len(values) == 1:
        v = round(values[0], 1)
        return {"median": v, "p25": v, "p75": v, "iqr": 0.0, "min": v, "max": v}
    q = statistics.quantiles(values, n=4, method="inclusive")
    return {
        "median": round(statistics.median(values), 1),
        "p25": round(q[0], 1),
        "p75": round(q[2], 1),
        "iqr": round(q[2] - q[0], 1),
        "min": round(values[0], 1),
        "max": round(values[-1], 1),
    }


def aggregate_segments(pulls):
    """Per segment index: the phase it is, and when it starts and ends.

    The phase id and name are taken by majority vote across the pulls rather than from the
    first pull, and the vote's margin is reported: a segment index that means different
    phases in different pulls is a fact about the fight (a skipped intermission, a
    different pull order), not a detail to average away.
    """
    by_index = collections.defaultdict(list)
    for p in pulls:
        for s in p["segments"]:
            by_index[s["index"]].append(s)

    out = []
    for index in sorted(by_index):
        members = by_index[index]
        if len(members) < MIN_SEGMENT_PULLS:
            continue
        vote = collections.Counter((m["phaseId"], m["cycle"], m["name"]) for m in members)
        (pid, cycle, name), agree = vote.most_common(1)[0]
        same = [m for m in members if (m["phaseId"], m["cycle"], m["name"]) == (pid, cycle, name)]
        out.append(
            {
                "index": index,
                "phaseId": pid,
                "cycle": cycle,
                "name": name,
                "label": name if cycle == 1 else f"{name} #{cycle}",
                "startSeconds": spread([m["start"] for m in same]),
                "durationSeconds": spread([m["end"] - m["start"] for m in same]),
                "support": {"pulls": len(same), "reachedIndex": len(members), "of": len(pulls)},
                "agreement": round(agree / len(members), 2),
            }
        )
    return out


def aggregate_abilities(pulls, journal):
    """Per ability: cadence, per-occurrence timings, and the journal join."""
    reached = collections.Counter()
    for p in pulls:
        for s in p["segments"]:
            reached[s["index"]] += 1

    names = {n for p in pulls for n in p["abilities"]}
    out = []
    for name in sorted(names):
        present = [p for p in pulls if name in p["abilities"]]
        ids, sources = set(), collections.Counter()
        counts, gaps, firsts = [], [], []
        # (segment index, ordinal within that segment) -> the times it landed at
        cells = collections.defaultdict(list)

        for p in present:
            a = p["abilities"][name]
            ids.update(a["ids"])
            for s in a["sources"]:
                sources[s] += 1
            times = [i["at"] for i in a["instances"]]
            counts.append(len(times))
            firsts.append(times[0])
            gaps.extend(y - x for x, y in zip(times, times[1:]))
            seen = collections.Counter()
            for t in times:
                seg = segment_of(p["segments"], t)
                seen[seg["index"]] += 1
                cells[(seg["index"], seen[seg["index"]])].append(
                    {"at": t, "atSegment": t - seg["start"]}
                )

        occurrences = []
        for (index, ordinal), hits in sorted(cells.items()):
            floor = max(1, MIN_OCCURRENCE_SUPPORT * reached.get(index, len(pulls)))
            if len(hits) < floor:
                continue
            occurrences.append(
                {
                    "segmentIndex": index,
                    "ordinal": ordinal,
                    "atSeconds": spread([h["at"] for h in hits]),
                    "atSegmentSeconds": spread([h["atSegment"] for h in hits]),
                    "support": {"pulls": len(hits), "reachedSegment": reached.get(index, len(pulls))},
                }
            )

        j = journal.get(name.lower())
        out.append(
            {
                "name": name,
                "ids": sorted(ids),
                "sources": [s for s, _ in sources.most_common()],
                "seenInPulls": len(present),
                "of": len(pulls),
                "instancesPerPull": spread([float(c) for c in counts]),
                "cadenceSeconds": spread(gaps) if gaps else None,
                "firstAtSeconds": spread(firsts),
                "inJournal": j is not None,
                "journal": j,
                "occurrences": occurrences,
            }
        )
    # Journal-confirmed mechanics first, then by how often they fire.
    out.sort(key=lambda a: (not a["inJournal"], -a["seenInPulls"], a["name"]))
    return out


def aggregate_composition(pulls):
    """The raid composition the field actually brings, as a distribution not an average.

    Averaging a composition produces "2.0 tanks, 3.7 healers" which describes no raid.
    The modal split and its share is the honest summary; the full distribution is kept
    beside it so a genuinely split field is visible.
    """
    combos = collections.Counter()
    specs = collections.Counter()
    spec_pulls = collections.Counter()
    for p in pulls:
        c = p["composition"]
        combos[(c.get("tanks", 0), c.get("healers", 0), c.get("dps", 0))] += 1
        for spec, n in p["specs"].items():
            specs[spec] += n
            spec_pulls[spec] += 1
    if not combos:
        return None
    (t, h, d), n = combos.most_common(1)[0]
    return {
        "modal": {"tanks": t, "healers": h, "dps": d, "label": f"{t}/{h}/{d}"},
        "modalShare": round(n / len(pulls), 2),
        "distribution": [
            {"label": f"{a}/{b}/{c}", "pulls": k}
            for (a, b, c), k in combos.most_common()
        ],
        "specs": [
            {"spec": s, "totalSlots": specs[s], "pulls": spec_pulls[s],
             "perPull": round(specs[s] / spec_pulls[s], 2)}
            for s, _ in specs.most_common()
        ],
    }


def damage_taken(pulls, limit, journal):
    """Per-ability damage taken, summed over a subset of the pool.

    Deliberately a *subset*: a magnitude is a tuned constant, so it converges in a handful
    of pulls, while the timing measurements genuinely need the whole pool. Fetching a
    damage table for all hundred would roughly double the run's cost to sharpen a number
    that is already sharp.

    The rows carry the same ``inJournal`` join as the cast timings, and for the same
    reason: a damage-taken table is not a table of boss abilities. On the reference Sszorak
    pulls it also contains **Burning Rush** (111400) and **Stretch Time** (413924) -- a
    Warlock movement talent and a Time Rune, both of which damage their own caster -- which
    would otherwise read as mechanics. The join is also what makes the *other* direction
    legible: Ula'tek's Presence, Mutilated Gash and Viscous Cyst are journal abilities that
    never appear in the cast stream because they are applied auras rather than casts, and
    together they are over 70% of everything the raid takes on that fight.
    """
    totals = collections.defaultdict(lambda: {"total": 0, "reduced": 0, "pulls": 0, "ids": set()})
    used = []
    for p in pulls[:limit]:
        try:
            data = W.cached(
                p["code"],
                f"encprof-dmg|{p['fight']}",
                lambda: W.query(DAMAGE_Q % (p["code"], p["fight"]))
                ["data"]["reportData"]["report"]["table"]["data"],
            )
        except (Exception, SystemExit):  # noqa: BLE001
            continue
        used.append({"code": p["code"], "fight": p["fight"]})
        per_ability = collections.defaultdict(lambda: [0, 0])
        for entry in data.get("entries") or []:
            for ab in entry.get("abilities") or []:
                agg = per_ability[(ab.get("name"), ab.get("guid"))]
                agg[0] += ab.get("total") or 0
                agg[1] += ab.get("totalReduced") or 0
        for (name, guid), (tot, red) in per_ability.items():
            row = totals[name]
            row["total"] += tot
            row["reduced"] += red
            row["pulls"] += 1
            row["ids"].add(guid)

    if not used:
        return None
    rows = [
        {
            "name": name,
            "ids": sorted(v["ids"]),
            "meanPerPull": round(v["total"] / v["pulls"]),
            "meanReducedPerPull": round(v["reduced"] / v["pulls"]),
            "pulls": v["pulls"],
            "inJournal": (name or "").lower() in journal,
        }
        for name, v in totals.items()
    ]
    rows.sort(key=lambda r: -r["meanPerPull"])
    grand = sum(r["meanPerPull"] for r in rows) or 1
    for r in rows:
        r["shareOfRaidDamageTaken"] = round(r["meanPerPull"] / grand, 4)
    return {"sampledPulls": used, "abilities": rows}


# ------------------------------------------------------------------------ encounters


def journal_index(journal_doc, slug):
    """Journal abilities for one encounter, keyed by lower-cased name.

    Keyed by every name the catalogue knows for an ability -- its section title, the
    journal's own spell name and the tooltip's name -- because the three disagree often
    enough to matter and the log only ever gives one of them.
    """
    out = {}
    for enc in journal_doc.get("encounters") or []:
        if enc.get("slug") != slug:
            continue
        for a in enc.get("abilities") or []:
            row = {
                "spellId": a["spellId"],
                "title": a["title"],
                "description": a.get("description"),
                "damage": a.get("damage"),
                "parentTitle": a.get("parentTitle"),
            }
            for key in (a.get("title"), a.get("journalSpellName"), a.get("tooltipName")):
                if key:
                    out.setdefault(key.lower(), row)
    return out


def build_encounter(enc, class_name, spec_name, difficulty, sample, journal_doc, damage_limit, refresh):
    wcl_diff = WCL_DIFFICULTY[difficulty]
    ranks = rankings(enc["wcl_encounter_id"], class_name, spec_name, wcl_diff, sample, refresh)
    if not ranks:
        return {"slug": enc["slug"], "skipped": "no ranked pulls for this class/spec/difficulty"}

    wanted = distinct_pulls(ranks)
    profiles, unreadable = [], []
    for i, r in enumerate(wanted):
        if i % 10 == 0:
            wait_for_budget()
        p = pull_profile(r, enc["wcl_encounter_id"])
        (unreadable if p.get("skipped") else profiles).append(p)

    if len(profiles) < MIN_SEGMENT_PULLS:
        return {
            "slug": enc["slug"],
            "skipped": f"only {len(profiles)} readable pull(s) -- too thin to measure",
            "sample": {"rankings": len(ranks), "distinctPulls": len(wanted), "unreadable": unreadable},
        }

    journal = journal_index(journal_doc, enc["slug"])
    abilities = aggregate_abilities(profiles, journal)
    damage = damage_taken(profiles, damage_limit, journal)

    # A catalogued ability the pool never *cast* is usually not missing -- it is an applied
    # aura (Corroding Venom), a spawned object's damage (Viscous Cyst) or an umbrella the
    # journal uses to group two real casts (Apex Predator over Ravage and Mutilate). Saying
    # which is which turns a bare list of 13 names into a readable one, and leaves a genuine
    # gap -- a mechanic in a phase the top 100 never reach -- standing out as the only kind
    # with neither casts nor damage behind it.
    logged_names = {a["name"].lower() for a in abilities}
    damaging = {(r["name"] or "").lower() for r in (damage or {}).get("abilities", [])}
    parents = {(j.get("parentTitle") or "").lower() for j in journal.values()}
    journal_only, seen_titles = [], set()
    for key, j in journal.items():
        if key in logged_names or j["title"] in seen_titles:
            continue
        seen_titles.add(j["title"])
        if key in damaging:
            why = "applied rather than cast: deals damage in the pool but emits no cast event"
        elif key in parents:
            why = "an umbrella section grouping other abilities, not a cast in its own right"
        else:
            why = "neither cast nor damaging in this pool"
        journal_only.append({"title": j["title"], "spellId": j["spellId"], "why": why})
    journal_only.sort(key=lambda r: r["title"])

    return {
        "slug": enc["slug"],
        "wclEncounterId": enc["wcl_encounter_id"],
        "name": enc.get("name"),
        "sample": {
            "requested": sample,
            "rankings": len(ranks),
            "distinctPulls": len(wanted),
            "readable": len(profiles),
            "kills": sum(1 for p in profiles if p["kill"]),
            "unreadable": unreadable,
            "truncatedEventStreams": [
                {"code": p["code"], "fight": p["fight"]} for p in profiles if p["eventsTruncated"]
            ],
        },
        "durationSeconds": spread([p["duration"] for p in profiles]),
        "composition": aggregate_composition(profiles),
        "segments": aggregate_segments(profiles),
        "abilities": abilities,
        "journalOnly": journal_only,
        "damageTaken": damage,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--zone", required=True, help="zone slug, e.g. venomous-abyss")
    ap.add_argument("--spec", required=True, help="spec slug, e.g. balance-druid")
    ap.add_argument(
        "--difficulty", type=int, default=16, choices=sorted(WCL_DIFFICULTY),
        help="in-game difficulty: 14 Normal, 15 Heroic, 16 Mythic (NOT the WCL numbering)",
    )
    ap.add_argument("--sample", type=int, default=100, help="pulls to sample per encounter")
    ap.add_argument("--damage-sample", type=int, default=10,
                    help="pulls to sum damage taken over (a magnitude converges fast)")
    ap.add_argument("--encounter", action="append", help="limit to these encounter slugs")
    ap.add_argument("--out", type=pathlib.Path,
                    help="write one whole-tier file here instead of the per-encounter "
                         "profiles/<spec>-<difficulty>.json files")
    ap.add_argument("--refresh", action="store_true", help="bypass the ranking cache")
    args = ap.parse_args(argv)

    encounters = [e for e in D.encounters(args.zone) if e.get("wcl_encounter_id")]
    if args.encounter:
        wanted = set(args.encounter)
        encounters = [e for e in encounters if e["slug"] in wanted]
    if not encounters:
        raise SystemExit("no encounters matched")

    journal_doc = D.load_tier(args.zone, "journal.json")
    if journal_doc is None:
        raise SystemExit(f"no journal.json under {D.rel(D.tier_dir(args.zone))} -- run tools/game_knowledge/journal_sync.py first")

    spec_doc = json.loads(D.talent_tree_path(args.spec).read_text(encoding="utf-8"))
    class_name = spec_doc["spec"]["class_name"]
    spec_name = spec_doc["spec"]["spec_name"]

    rows = []
    for enc in encounters:
        print(f"  {enc['slug']} ...", file=sys.stderr, flush=True)
        row = build_encounter(
            enc, class_name, spec_name, args.difficulty, args.sample,
            journal_doc, args.damage_sample, args.refresh,
        )
        if row.get("skipped"):
            print(f"    skipped: {row['skipped']}", file=sys.stderr)
        else:
            n_occ = sum(len(a["occurrences"]) for a in row["abilities"])
            print(
                f"    {row['sample']['readable']} pulls, {len(row['segments'])} segments, "
                f"{len(row['abilities'])} abilities, {n_occ} timed occurrences",
                file=sys.stderr,
            )
        rows.append(row)

    doc = {
        "meta": {
            "zone": args.zone,
            "spec": args.spec,
            "difficulty": args.difficulty,
            "wclDifficulty": WCL_DIFFICULTY[args.difficulty],
            "class": class_name,
            "specName": spec_name,
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "generator": "tools/warcraftlogs/encounter_profile_sync.py",
            "journal": "journal.json",
            "parameters": {
                "sample": args.sample,
                "damageSample": args.damage_sample,
                "collapseSeconds": COLLAPSE_S,
                "minOccurrenceSupport": MIN_OCCURRENCE_SUPPORT,
                "minSegmentPulls": MIN_SEGMENT_PULLS,
            },
            "readMe": (
                "The pool is the top DPS rankings for one spec, which biases it toward fast "
                "kills: a mechanic that only appears late may be under-represented or absent, "
                "and 'journalOnly' lists catalogued abilities the pool never cast. Times are "
                "given both from the pull start (atSeconds) and from the start of the phase "
                "segment they landed in (atSegmentSeconds); the second is the stable one. A "
                "segment index is not a phase number -- phases repeat, so read phaseId/cycle."
            ),
        },
        "encounters": rows,
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        written = [args.out]
    else:
        written = D.write_tier(args.zone, f"profiles/{args.spec}-{args.difficulty}.json", doc["meta"], rows)
    for out in written:
        print(f"wrote {D.rel(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
