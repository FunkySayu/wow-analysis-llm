"""Peer comparison for Arcane Mage: one pull against the ranking pool for that boss.

`checks/peers.py` does this for Balance Druid and is hard-wired to that spec's
spell list. This module answers the question that actually comes up first -
"why is my parse low" - and it answers it in the order the causes stack up:

  1. `bar`         is the *pool* different, or am I? Two bosses on the same night
                   at the same DPS can parse 92 and 36, because each encounter
                   has its own DPS bar. Always run this before anything else.
  2. `peers-arc`   split the DPS gap into hits/min (throughput) and damage/hit
                   (how hard each one lands). These have completely different
                   fixes and a bare DPS delta cannot tell them apart.
  3. `peers-buffs` the control test for damage/hit: raid buffs and consumables
                   the pool carries and you do not.
  4. `windows`     do you convert this fight's vulnerability window? Measured as a
                   multiplier over your OWN background rate, so gear cancels out
                   and a badly geared player is graded fairly. Needs `fightmap`
                   (checks/encounter.py) to have found a window at all.

Measured on `JX1Vd49kL63QPwbY` fight 18 (Funkywand, Heroic Coiled Altar): 3 and 4
both fired. GCD uptime, cast rates and the whole Salvo economy were at or above
peer level; every hit landed ~30% smaller (buffs and gear), *and* the fight's
vulnerability window returned 2.67x background against a peer median of 3.53x.
Those two are independent and additive - do not let one explain away the other.
"""

import collections
import statistics

from lib import check as C
from lib import format as F
from lib import timeline as T
from lib import wclapi as W

from checks.mage_arcane import (
    MISSILES, BARRAGE, BLAST, PRISMATIC_BOLT, ORB, TOTM, SURGE, EVOCATION,
    SURGE_BUFF, ARCANE_SOUL,
)

CAST_METRICS = [
    ("Arcane Missiles", MISSILES),
    ("Arcane Barrage", BARRAGE),
    ("Prismatic Bolt", PRISMATIC_BOLT),
    ("Arcane Blast", BLAST),
    ("Arcane Orb", ORB),
    ("Touch of the Magi", TOTM),
    ("Arcane Surge", SURGE),
    ("Evocation", EVOCATION),
]

# Buffs that are somebody else's job or a consumable - things no rotation check
# can see, and which multiply every single hit you land.
EXTERNAL_BUFFS = [
    "Mark of the Wild", "Blessing of the Bronze", "Hearty Well Fed", "Well Fed",
    "Skyfury", "Battle Shout", "Arcane Intellect", "Power Infusion",
    "Ebon Might", "Prescience", "Shifting Sands",
    "Time Warp", "Bloodlust", "Heroism", "Primal Rage", "Fury of the Aspects",
]
CONSUMABLE_HINTS = ("Flask", "Well Fed", "Potion", "Rune of", "Phial")

RANK_Q = '''query { worldData { encounter(id: %d) { name
  characterRankings(className: "Mage", specName: "Arcane",
                    difficulty: %d, metric: dps, page: %d) } } }'''


def rankings(encounter_id, difficulty, pages=5, refresh=False):
    """Top `pages` * 100 logged Arcane pulls on this encounter, DPS-descending.

    NOT a percentile sample: page 1 is the world's best pulls. Read the deltas,
    never the rank - a p36 player is nowhere near page 1 by construction.
    """
    def go():
        out = []
        for p in range(1, pages + 1):
            cr = W.query(RANK_Q % (encounter_id, difficulty, p))
            cr = cr["data"]["worldData"]["encounter"]["characterRankings"]
            out.extend(cr["rankings"])
            if not cr.get("hasMorePages"):
                break
        return out
    return W.cached("_pool", "arc|%d|%d|%d" % (encounter_id, difficulty, pages),
                    go, refresh)


def profile(code, fight_id, name, duration):
    """Everything one peer contributes, in a single cached bundle.

    Damage is read as (total, hits+ticks) per ability so DPS can be factored into
    throughput x hit size. Arcane Blast is pulled as raw events on purpose: it is
    the last line of the APL, so it lands in an unamplified state for everybody,
    which makes its median non-crit the cleanest available proxy for "how hard
    does this character hit at all".
    """
    def go():
        aid = W.actor_id(code, name)
        casts = [e for e in W.events(code, fight_id, "Casts", aid)
                 if e["type"] == "cast"]
        by = collections.Counter(str(e.get("abilityGameID")) for e in casts)

        dmg = W.table(code, [fight_id], "DamageDone", source_id=aid)
        tot = hits = crit = 0
        per = {}
        for e in dmg.get("entries", []):
            h = (e.get("hitCount") or 0) + (e.get("tickCount") or 0)
            tot += e.get("total") or 0
            hits += h
            crit += (e.get("critHitCount") or 0) + (e.get("critTickCount") or 0)
            per[e["name"]] = [e.get("total") or 0, h]

        blast = W.events(code, fight_id, "DamageDone", aid, ability_id=BLAST)
        nc = sorted((e.get("amount", 0) + (e.get("absorbed") or 0))
                    for e in blast if e.get("hitType") != 2)

        buffs = W.table(code, [fight_id], "Buffs", source_id=aid)
        auras = {a["name"]: (a.get("totalUptime") or 0) / 1000.0
                 for a in buffs.get("auras", [])}

        return {"casts": dict(by), "per": per, "auras": auras,
                "tot": tot, "hits": hits, "crit": crit,
                "blast_med": nc[len(nc) // 2] if nc else 0, "blast_n": len(blast)}

    p = dict(W.cached("_arcpeer", "%s|%d|%s" % (code, fight_id, name), go))
    p["dur"] = duration
    return p


def _row(label, mine, vals, fmt="{:.1f}"):
    if not vals:
        return "  %-24s %11s   (no peers)" % (label, fmt.format(mine))
    med = statistics.median(vals)
    delta = (mine - med) / med * 100 if med else 0.0
    flag = "  <<<" if delta <= -12 else ("  +++" if delta >= 12 else "")
    return ("  %-24s %11s | %11s | %+7.1f%%%s"
            % (label, fmt.format(mine), fmt.format(med), delta, flag))


#: A delta this far from the peer median is called out in the margin.
FLAG_PCT = 12


def _srow(s):
    """Render one `stat()` entry from the payload. Same output as `_row`, but
    reading the already-computed numbers rather than recomputing from profiles -
    `print()` may not touch the log."""
    fmt = s["format"]
    if s["peerMedian"] is None:
        return "  %-24s %11s   (no peers)" % (s["label"], fmt.format(s["mine"]))
    flag = ("  <<<" if s["deltaPct"] <= -FLAG_PCT
            else ("  +++" if s["deltaPct"] >= FLAG_PCT else ""))
    return ("  %-24s %11s | %11s | %+7.1f%%%s"
            % (s["label"], fmt.format(s["mine"]), fmt.format(s["peerMedian"]),
               s["deltaPct"], flag))


def _peer_profiles(code, fight, my_ilvl, n=12):
    """The ilvl-matched slice of the pool, already fetched. Anonymised logs are
    dropped: `actor_id` raises SystemExit on them, which is not an error here."""
    pool = [r for r in rankings(fight["encounterID"], fight["difficulty"])
            if r["report"]["code"] != code and r["name"] != "Anonymous"]
    band = [r for r in pool if abs(r["bracketData"] - (my_ilvl or 0)) <= 4]
    out = []
    for r in (band or pool)[:n]:
        try:
            out.append(profile(r["report"]["code"], r["report"]["fightID"],
                               r["name"], r["duration"] / 1000.0))
        except BaseException:
            continue
    return pool, out


def _my_ilvl(code, fight_id, me):
    summ = W.table(code, [fight_id], "Summary")
    for arr in (summ.get("playerDetails") or {}).values():
        for p in arr:
            if p.get("name") == me:
                return p.get("maxItemLevel")
    return None


class _PoolCheck(C.PoolCheck):
    """Arcane's pool checks share `C.PoolCheck`'s one-pull cap; only the group differs."""

    group = "mage-compare"


# ====================================================== 1. is it me or the boss

class BarCheck(C.Check):
    """Where each encounter's DPS bar sits, and where every fight of yours sits on it.

    The first thing to establish about a low parse, because it is the one cause
    that has nothing to do with how the pull was played. An encounter with an
    amplify window or a permanent second target carries a much higher DPS bar
    than a clean single-target fight, so an identical DPS number parses
    completely differently on each. Verified on report JX1Vd49kL63QPwbY:
    172,305 DPS = p92 on Sszorak and 170,521 DPS = p36 on The Coiled Altar,
    same night, same character, same gear - the Coiled Altar pool's median is
    22% higher.

    Ignores the fight selector - it reports every ranked fight in the report on
    purpose, because the comparison BETWEEN them is the finding. That is what
    makes this the suite's one genuinely run-scoped check rather than a per-pull
    one: narrowing it to a pull would delete the thing it measures.
    """

    id = "bar"
    title = "Encounter DPS bars"
    group = "mage-compare"
    scope = "run"

    def json(self):
        code, aid = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(aid, str(aid))
        q = ('query { reportData { report(code: "%s") { rankings(playerMetric: dps) } } }'
             % code)
        data = W.query(q)["data"]["reportData"]["report"]["rankings"]["data"]
        rows = []
        for f in data:
            enc = f.get("encounter") or {}
            row = None
            for rs in (f.get("roles") or {}).values():
                for c in rs.get("characters", []):
                    if c["name"] == me:
                        row = c
            if not row or not enc.get("id"):
                continue
            pool = [r["amount"] for r in rankings(enc["id"], f.get("difficulty"))]
            p50 = statistics.median(pool) if pool else 0
            rows.append({
                "fightId": f.get("fightID"), "encounter": enc.get("name", "?"),
                "encounterId": enc["id"], "difficulty": f.get("difficulty"),
                "dps": row["amount"], "parsePercent": row.get("rankPercent"),
                "poolMedian": p50,
                "vsPoolMedianPct": 100.0 * row["amount"] / p50 if p50 else 0,
                "poolSize": len(pool),
            })
        return {"scope": "run", "params": {}, "actor": me, "fights": rows}

    def print(self):
        d = self.json()
        print(F.hdr(["fight", "encounter", "diff", "your DPS", "parse", "pool p50", "you/p50"],
                    [5, 24, 5, 10, 6, 10, 8]))
        for r in d["fights"]:
            print("%5s  %-24s %5s  %10.0f  %6s  %10.0f  %7.1f%%"
                  % (r["fightId"], r["encounter"][:24], r["difficulty"],
                     r["dps"], r["parsePercent"], r["poolMedian"],
                     r["vsPoolMedianPct"]))
        print("\n'you/p50' is the honest cross-boss number: your DPS against the median\n"
              "of that encounter's own top-500 pool, so it is comparable between bosses\n"
              "in a way the parse percentile is not. A parse that collapses while\n"
              "you/p50 barely moves is the boss's bar moving, not your play.")


# ============================================ 2. throughput vs damage per hit

class PeersArcCheck(_PoolCheck):
    """Split the DPS gap into hits/min and damage/hit, then attribute each.

    The whole point of the split: a throughput gap is fixed by pressing more or
    better buttons (uptime, cast selection) and a damage/hit gap never is - that
    one is gear, raid buffs, consumables or amplify-window alignment. A bare DPS
    delta cannot distinguish them and sends you to the wrong half of the problem
    about half the time.
    """
    id = "peers-arc"
    title = "Throughput vs damage per hit"

    def fight_json(self, fight):
        skip = self._skip(fight)
        if skip:
            return {"skipped": skip}
        code, aid = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(aid, str(aid))
        dur = F.fight_seconds(fight)
        my_ilvl = _my_ilvl(code, fight["id"], me)
        mine = profile(code, fight["id"], me, dur)
        pool, profs = _peer_profiles(code, fight, my_ilvl)

        def stat(label, fn, fmt="{:.1f}"):
            vals = [fn(p) for p in profs]
            med = statistics.median(vals) if vals else None
            return {"label": label, "mine": fn(mine), "peerMedian": med,
                    "deltaPct": ((fn(mine) - med) / med * 100) if med else 0.0,
                    "format": fmt, "peers": len(vals)}

        headline = [
            stat("DPS", lambda p: p["tot"] / p["dur"], "{:.0f}"),
            stat("hits+ticks / min", lambda p: p["hits"] * 60.0 / p["dur"]),
            stat("damage per hit", lambda p: p["tot"] / p["hits"] if p["hits"] else 0, "{:.0f}"),
            stat("GCDs / min", lambda p: sum(p["casts"].values()) * 60.0 / p["dur"]),
            stat("crit %", lambda p: 100.0 * p["crit"] / p["hits"] if p["hits"] else 0),
            stat("Arcane Blast noncrit", lambda p: float(p["blast_med"]), "{:.0f}"),
        ]
        per_min, per_cast = [], []
        for lab, gid in CAST_METRICS:
            fn = (lambda p, gid=gid: p["casts"].get(str(gid), 0) * 60.0 / p["dur"])
            if max([fn(mine)] + [fn(p) for p in profs]) < 0.05:
                continue
            per_min.append(stat(lab, fn, "{:.2f}"))
        for lab, gid in CAST_METRICS[:6]:
            def fn(p, lab=lab, gid=gid):
                n = p["casts"].get(str(gid), 0)
                return (p["per"].get(lab, [0, 0])[0] / n) if n else 0
            if max([fn(mine)] + [fn(p) for p in profs]) < 1:
                continue
            per_cast.append(stat(lab, fn, "{:.0f}"))
        return {
            "skipped": None, "name": fight["name"], "difficulty": fight["difficulty"],
            "actor": me, "itemLevel": my_ilvl, "seconds": dur,
            "poolSize": len(pool), "peers": len(profs),
            "poolDpsMin": min(r["amount"] for r in pool) if pool else 0,
            "poolDpsMax": max(r["amount"] for r in pool) if pool else 0,
            "headline": headline, "castsPerMinute": per_min, "damagePerCast": per_cast,
        }

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if r["skipped"]:
                continue
            print("%s (difficulty %s) - %s @ ilvl %s, %.0fs"
                  % (r["name"], r["difficulty"], r["actor"], r["itemLevel"], r["seconds"]))
            print("pool: %d logged pulls (%s - %s DPS); comparing against %d at ilvl %s +-4\n"
                  % (r["poolSize"], format(int(r["poolDpsMin"]), ","),
                     format(int(r["poolDpsMax"]), ","), r["peers"], r["itemLevel"]))
            print("  %-24s %11s | %11s | %8s" % ("metric", "YOU", "peer med", "delta"))
            print("  " + "-" * 62)
            for s in r["headline"]:
                print(_srow(s))
            print("\n  casts per minute")
            for s in r["castsPerMinute"]:
                print(_srow(s))
            print("\n  damage per cast")
            for s in r["damagePerCast"]:
                print(_srow(s))
            print("\n  Read hits/min and damage per hit TOGETHER. Level on the first and\n"
                  "  down on the second means the rotation is fine and the character is\n"
                  "  under-buffed or under-geared - run `peers-buffs` next, not `salvo`.\n"
                  "  Damage per cast falls off fastest on the abilities that compound on\n"
                  "  the Salvo economy (Prismatic Bolt, ToM, Orb) and least on Arcane\n"
                  "  Blast, so the Blast line is the closest thing to a pure stat delta.")
        self._skipped_note(d)


# ================================================ 3. the control test for buffs

class PeersBuffsCheck(_PoolCheck):
    """Raid buffs and consumables the pool carries and you do not.

    Run this whenever `peers-arc` shows a damage/hit gap. Every line here is a
    flat multiplier on every hit in the fight, none of them shows up in any
    rotation check, and several are somebody else's global - Mark of the Wild is
    the druid's, Blessing of the Bronze needs an evoker in the raid at all, so a
    short roster can lose several of these through no fault of the player.
    A 0% against a pool at 100% is a finding; a 0% against a pool at 0% is a
    logging gap or a buff that does not exist this patch.
    """
    id = "peers-buffs"
    title = "External buffs and consumables"
    #: A buff this much of the pool carries, that you do not, is called MISSING.
    MISSING_SHARE = 0.6

    def params(self):
        return {"missingShare": self.MISSING_SHARE, "tracked": list(EXTERNAL_BUFFS)}

    def fight_json(self, fight):
        skip = self._skip(fight)
        if skip:
            return {"skipped": skip}
        code, aid = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(aid, str(aid))
        dur = F.fight_seconds(fight)
        my_ilvl = _my_ilvl(code, fight["id"], me)
        mine = profile(code, fight["id"], me, dur)
        _, profs = _peer_profiles(code, fight, my_ilvl)

        def up(p, n):
            return 100.0 * p["auras"].get(n, 0) / p["dur"]

        buffs = []
        for n in EXTERNAL_BUFFS:
            v = [up(p, n) for p in profs]
            if max(v + [up(mine, n)]) < 0.3:
                continue
            have = sum(1 for x in v if x > 0)
            buffs.append({
                "buff": n, "minePct": up(mine, n),
                "peerMedianPct": statistics.median(v) if v else 0.0,
                "peersWith": have, "peers": len(profs),
                "missing": up(mine, n) == 0 and have >= len(profs) * self.MISSING_SHARE,
            })
        seen = collections.Counter()
        for p in profs:
            for n in p["auras"]:
                if any(h in n for h in CONSUMABLE_HINTS):
                    seen[n] += 1
        # Yours that nobody in the pool ran. Without this a flask the pool does
        # not use reads as "no flask at all", a completely different finding.
        solo = sorted(n for n in mine["auras"]
                      if any(h in n for h in CONSUMABLE_HINTS) and n not in seen)
        return {
            "skipped": None, "peers": len(profs), "buffs": buffs,
            "consumables": [{"name": n, "peersWith": c, "peers": len(profs),
                             "mine": n in mine["auras"]}
                            for n, c in seen.most_common(18)],
            "onlyYours": solo,
        }

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if r["skipped"]:
                continue
            print("external buff / consumable uptime, %% of fight   (n peers = %d)\n"
                  % r["peers"])
            print("  %-30s %8s %9s %9s" % ("buff", "you", "peer med", "peers w/"))
            print("  " + "-" * 62)
            for b in r["buffs"]:
                flag = "   <<< MISSING" if b["missing"] else ""
                print("  %-30s %8.1f %9.1f %6d/%-3d%s"
                      % (b["buff"], b["minePct"], b["peerMedianPct"],
                         b["peersWith"], b["peers"], flag))
            print("\n  consumables in the pool (yours marked)")
            for c in r["consumables"]:
                print("    %2d/%-3d %-38s %s" % (c["peersWith"], c["peers"],
                                                 c["name"][:38], "YOU" if c["mine"] else ""))
            if r["onlyYours"]:
                print("    yours, unused by this pool: %s" % ", ".join(r["onlyYours"]))
        self._skipped_note(d)


# ============================================ 4. windows of opportunity

# Every Arcane GCD, so anything cast that is NOT one of these and comes off a
# long cooldown is an on-use trinket. Detecting them by shape rather than by a
# hard-coded item list keeps the check working when the trinket changes.
ROTATIONAL = {MISSILES, BARRAGE, BLAST, PRISMATIC_BOLT, ORB, TOTM, SURGE, EVOCATION,
              212653, 55342, 80353, 235450, 342246, 45438, 66}


def _merge(ws):
    out = []
    for a, b in sorted(ws):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _dmg_in(code, fid, aid, ws):
    """(damage, seconds) inside a set of windows, overlaps counted once."""
    q = ('query { reportData { report(code: "%s") { table(dataType: DamageDone, '
         'fightIDs: [%d], sourceID: %d, startTime: %d, endTime: %d) } } }')
    tot = sec = 0.0
    for a, b in _merge(ws):
        d = W.cached("_win", "%s|%d|%d|%d|%d" % (code, fid, aid, a, b),
                     lambda a=a, b=b: sum(
                         e.get("total") or 0 for e in
                         W.query(q % (code, fid, aid, a, b))
                         ["data"]["reportData"]["report"]["table"]["data"].get("entries", [])))
        tot += d
        sec += (b - a) / 1000.0
    return tot, sec


def _onuse(code, fid, aid):
    """Cast timestamps of on-use trinkets, detected by shape rather than item id.

    Three conditions together, because any two of them let junk through: the
    ability is not part of the rotation, its casts are at least 60s apart, and it
    puts a buff on the caster. That last one is what separates a trinket from a
    racial, a healthstone or a defensive - an earlier version without it reported
    11 "on-use" casts for a character that owns one on-use trinket.
    """
    ev = [e for e in W.events(code, fid, "Casts", aid) if e["type"] == "cast"]
    selfbuffs = {e.get("abilityGameID") for e in W.events(code, fid, "Buffs", aid)
                 if e["type"] == "applybuff" and e.get("targetID") == aid}
    by = collections.defaultdict(list)
    for e in ev:
        g = e.get("abilityGameID")
        if g not in ROTATIONAL and g in selfbuffs:
            by[g].append(e["timestamp"])
    out = []
    for g, ts in by.items():
        ts.sort()
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        if 2 <= len(ts) <= 8 and gaps and min(gaps) >= 60000:
            out.extend(ts)
    return sorted(out)


def _primary_window(code, fid):
    """The fight's single best window, as report-relative (start, end) pairs.

    One mechanic routinely arrives as several auras at once - on The Coiled Altar
    the amplify on one boss (Ghastly Regeneration, 2.26x) and the 99% damage
    reduction on the other (Deathguard, 2.07x) are the same 35 seconds - so
    everything that *co-occurs* with the strongest window is folded into it.
    Everything that does not is left out, however good its ratio looks: an earlier
    version merged a 1.18x aura lasting 111s into a 2.26x window lasting 35s and
    reported the player's window multiplier as 2.02x instead of 2.94x. Windows
    that do not overlap are different decisions and must not be averaged.
    """
    from checks import encounter as E
    f = E.fight(code, fid)
    t0 = f["startTime"]
    _, _, rows = E.opportunity_windows(code, fid)
    cand = [r for r in rows if r["ratio"] >= 1.15]
    if not cand:
        return None
    ms = lambda ws: [(t0 + int(a * 1000), t0 + int(b * 1000)) for a, b in ws]
    base = _merge(ms(cand[0]["windows"]))
    for r in cand[1:]:
        ws = ms(r["windows"])
        span = sum(b - a for a, b in ws) or 1
        over = sum(max(0, min(b, y) - max(a, x)) for a, b in ws for x, y in base)
        if over / span >= 0.8:
            base = _merge(base + ws)
    return base


def _phase_window(code, fid):
    """Fallback when no enemy aura clears the bar: the shortest recurring phase.

    Needed because `opportunity_windows` scores a window by whether the RAID
    converted it, and a window the raid fails is still a window. Sszorak's Dig In
    is a real +30% vulnerability that measured 0.98x raid-wide on the reference
    pull - the raid simply did not use it - while the two best Arcane parses on
    that boss held Arcane Surge 51s to hit it and reached 1.79-1.83x personally.
    Scheduling off "did my raid convert it" would have hidden the whole finding.
    """
    from checks import encounter as E
    f = E.fight(code, fid)
    t0, t1 = f["startTime"], f["endTime"]
    tr = f.get("phaseTransitions") or []
    if len(tr) < 3:
        return None
    edges = [p["startTime"] for p in tr] + [t1]
    segs = collections.defaultdict(list)
    for p, a, b in zip(tr, edges, edges[1:]):
        segs[p["id"]].append((a, b))
    # The scheduling target is a phase that recurs and is short relative to the
    # fight; a phase that is most of the pull is the pull, not a window.
    cand = [(pid, ws) for pid, ws in segs.items()
            if len(ws) >= 2 and sum(b - a for a, b in ws) <= 0.35 * (t1 - t0)]
    if not cand:
        return None
    return _merge(min(cand, key=lambda kv: sum(b - a for a, b in kv[1]))[1])


def _window_profile(code, fid, name):
    """Multipliers over this player's OWN background rate.

    Ratios, not rates, on purpose: a multiplier against your own baseline is
    immune to item level, raid buffs and fight length, so it isolates *window
    exploitation* from everything the previous checks already measure. A player
    30% down on gear and a player at full gear are directly comparable here.
    """
    from checks import encounter as E

    f = E.fight(code, fid)
    t0, t1 = f["startTime"], f["endTime"]
    aid = W.actor_id(code, name)
    vuln = _primary_window(code, fid)
    src = "enemy aura"
    if not vuln:
        vuln = _phase_window(code, fid)
        src = "phase (no enemy aura cleared 1.15x - the raid is not converting it)"
    if not vuln:
        return None

    bf = W.events(code, fid, "Buffs", aid)
    cds = _merge(T.windows(bf, SURGE_BUFF) + T.windows(bf, ARCANE_SOUL, default_ms=4000))
    total, _ = _dmg_in(code, fid, aid, [(t0, t1)])
    dall, sall = _dmg_in(code, fid, aid, vuln + cds)
    dur = (t1 - t0) / 1000.0
    bg = (total - dall) / (dur - sall)
    dv, sv = _dmg_in(code, fid, aid, vuln)
    dc, sc = _dmg_in(code, fid, aid, cds)

    surges = [e["timestamp"] for e in W.events(code, fid, "Casts", aid)
              if e["type"] == "cast" and e.get("abilityGameID") == SURGE]
    onuse = _onuse(code, fid, aid)
    return {"aid": aid, "t0": t0, "dur": dur, "total": total, "bg": bg,
            "vuln": vuln, "cds": cds, "src": src,
            "vuln_rate": dv / sv, "vuln_secs": sv, "vuln_share": 100.0 * dv / total,
            "vuln_x": (dv / sv) / bg, "cd_x": (dc / sc) / bg, "n_surge": len(surges),
            "cycle": (dc / sc - bg) * (sc / len(surges)) if surges else 0,
            "surge_in_vuln": sum(1 for s in surges
                                 if any(a <= s <= b for a, b in vuln)),
            "onuse": len(onuse),
            "onuse_in_vuln": sum(1 for s in onuse if any(a <= s <= b for a, b in vuln)),
            "onuse_in_surge": sum(1 for s in onuse if T.in_windows(T.windows(bf, SURGE_BUFF), s)),
            "surge_t": [(s - t0) / 1000.0 for s in surges],
            "onuse_t": [(s - t0) / 1000.0 for s in onuse]}


class WindowsCheck(_PoolCheck):
    """Do you convert this fight's vulnerability window, and what is the gap worth?

    The measure is a multiplier over the player's OWN background rate, so item
    level and raid buffs cancel out entirely - this is the one check in the suite
    that a badly geared player can be graded on fairly. Two numbers matter:

      window x   how much harder you hit inside the amplify than outside it
      Surge x    how much your own cooldown windows beat your own baseline

    A +100% amplify hands everyone 2.00x for doing nothing. Everything above that
    is Surge, Soul, Touch of the Magi, lust and the on-use trinket landing inside
    it. Measured on The Coiled Altar: 2.67x against a peer median of 3.53x, worth
    4.5M damage - 5.5% of the pull - while the *placement* of the cooldowns was
    already correct and identical to the field's. The gap was execution inside the
    window, not scheduling.

    Neither number grades a player on its own. The top parse in that pool sits at
    2.46x, below the low parse being diagnosed, and wins on background rate
    instead. Read this check next to `peers-arc`, not in place of it.
    """
    id = "windows"
    title = "Vulnerability window conversion"
    PEERS = 10

    def params(self):
        return {"peerCount": self.PEERS}

    def fight_json(self, fight):
        skip = self._skip(fight)
        if skip:
            return {"skipped": skip}
        code, aid = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(aid, str(aid))
        mine = _window_profile(code, fight["id"], me)
        if not mine:
            return {"skipped": None, "name": fight["name"], "window": None}
        pool = [r for r in rankings(fight["encounterID"], fight["difficulty"])
                if r["report"]["code"] != code and r["name"] != "Anonymous"][:self.PEERS]
        profs = []
        for r in pool:
            try:
                p = _window_profile(r["report"]["code"], r["report"]["fightID"], r["name"])
                if p:
                    p["name"] = r["name"]
                    p["dps"] = r["amount"]
                    profs.append(p)
            except BaseException:
                continue

        def brief(p, name):
            return {"name": name, "background": p["bg"], "windowRate": p["vuln_rate"],
                    "windowX": p["vuln_x"], "surgeX": p["cd_x"],
                    "onuse": p["onuse"], "onuseInSurge": p["onuse_in_surge"],
                    "onuseInWindow": p["onuse_in_vuln"],
                    "surgeAt": [round(x) for x in p["surge_t"]],
                    "onuseAt": [round(x) for x in p["onuse_t"]]}

        vx = sorted(p["vuln_x"] for p in profs)
        scenarios = []
        if vx:
            for m, lab in ((statistics.median(vx), "peer median"), (vx[-1], "best peer")):
                gain = (m * mine["bg"] - mine["vuln_rate"]) * mine["vuln_secs"]
                scenarios.append({"multiplier": m, "label": lab, "gain": gain,
                                  "gainPctOfPull": 100.0 * gain / mine["total"]})
        return {
            "skipped": None, "name": fight["name"],
            "window": {"seconds": mine["vuln_secs"], "occurrences": len(mine["vuln"]),
                       "source": mine["src"]},
            "mine": brief(mine, "YOU"),
            "cycleDamage": mine["cycle"],
            "cyclePctOfPull": 100.0 * mine["cycle"] / mine["total"],
            "peers": [brief(p, p["name"]) for p in sorted(profs, key=lambda x: -x["dps"])],
            "peerWindowX": {"median": statistics.median(vx), "min": vx[0], "max": vx[-1]}
            if vx else None,
            "scenarios": scenarios,
        }

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if r["skipped"]:
                continue
            if not r["window"]:
                print("no vulnerability window measured on this pull - run `fightmap` to "
                      "see why.\nA boss with no amplify has nothing to schedule around; "
                      "the whole fight\nis background rotation and `peers-arc` is the "
                      "check you want.")
                continue
            w = r["window"]
            print("%s - vulnerability window %.0fs, %d occurrence(s), identified from %s\n"
                  % (r["name"], w["seconds"], w["occurrences"], w["source"]))
            print("  %-14s %9s %9s %9s %8s %8s %9s"
                  % ("player", "backgrnd", "window", "window x", "Surge x",
                     "onuse", "in window"))
            print("  " + "-" * 76)
            m = r["mine"]
            print("  %-14s %9.0f %9.0f %8.2fx %7.2fx %4d/%-3d %6d/%-3d   <== you"
                  % ("YOU", m["background"], m["windowRate"], m["windowX"], m["surgeX"],
                     m["onuseInSurge"], m["onuse"], m["onuseInWindow"], m["onuse"]))
            for p in r["peers"]:
                print("  %-14s %9.0f %9.0f %8.2fx %7.2fx %4d/%-3d %6d/%-3d"
                      % (p["name"][:14], p["background"], p["windowRate"], p["windowX"],
                         p["surgeX"], p["onuseInSurge"], p["onuse"],
                         p["onuseInWindow"], p["onuse"]))
            if not r["peers"]:
                continue
            px = r["peerWindowX"]
            print("\n  peer window multiplier: median %.2fx (min %.2f, max %.2f)"
                  % (px["median"], px["min"], px["max"]))
            print("  your Surge cycle is worth %.2fM above your own background "
                  "(%.1f%% of the pull)"
                  % (r["cycleDamage"] / 1e6, r["cyclePctOfPull"]))
            for s in r["scenarios"]:
                print("  window at %.2fx (%-11s) instead of %.2fx: %+.2fM = %+.1f%% of your pull"
                      % (s["multiplier"], s["label"], m["windowX"],
                         s["gain"] / 1e6, s["gainPctOfPull"]))
            print("\n  cooldown placement (s into the pull)")
            print("    you        Surge %s   on-use %s" % (m["surgeAt"], m["onuseAt"]))
            for p in r["peers"][:4]:
                print("    %-10s Surge %s   on-use %s"
                      % (p["name"][:10], p["surgeAt"], p["onuseAt"]))
            print("\n  The hold/cast tradeoff is arithmetic, not taste: holding Arcane Surge to\n"
                  "  reach the window costs whatever fraction of a cycle the hold is, and pays\n"
                  "  the window gain above. Compare the two numbers printed above before\n"
                  "  deciding - on a long enough fight the hold costs nothing because the lost\n"
                  "  seconds never add up to a whole extra cast.")
        self._skipped_note(d)


CHECKS = C.registry(BarCheck, PeersArcCheck, PeersBuffsCheck, WindowsCheck)
