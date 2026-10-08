"""Peer comparison: one player's fight against the WCL ranking pool for that boss.

Every other check in this toolkit measures a player against the APL. This one
measures them against *other players on the same encounter*, which is the only
way to answer "what are the people ahead of me actually doing differently".

The pool comes from `worldData.encounter.characterRankings`, ordered by DPS
descending across every logged pull. Two things about it matter:

  * The top pages are ~99th-percentile players, not "average good" players. A
    player at the 81st percentile is nowhere near page 1, so the comparison is
    deliberately aspirational - read the deltas, not the rank.
  * `bracketData` is the item level. Comparing rates (casts/min, damage share)
    is gear-robust; comparing raw DPS is not. Both are printed, and an
    item-level-matched subset is selected so the two can be told apart.

Per-peer cost is 4 cached queries (meta + Casts/DamageDone/Buffs tables), so a
25-peer run is ~100 queries once and free on every re-run.
"""

import collections
import statistics

from lib import check as C
from lib import format as F
from lib import wclapi as W

from checks.druid_balance import (
    WRATH, STARFIRE, STARSURGE, STARFALL, MOONFIRE, SUNFIRE,
    ECLIPSE_LUNAR, ECLIPSE_SOLAR, CELESTIAL_ALIGNMENT, INCARNATION,
    FURY_OF_ELUNE, FORCE_OF_NATURE, CONVOKE, WILD_MUSHROOM,
    NEW_MOON, HALF_MOON, FULL_MOON,
)

# Casts we rate-compare, in rotational reading order.
CAST_METRICS = [
    ("Eclipse", {ECLIPSE_LUNAR, ECLIPSE_SOLAR}),
    ("CA/Inc", {CELESTIAL_ALIGNMENT, INCARNATION}),
    ("Fury of Elune", {FURY_OF_ELUNE}),
    ("Convoke", {CONVOKE}),
    ("Force of Nature", {FORCE_OF_NATURE}),
    ("Moon chain", {NEW_MOON, HALF_MOON, FULL_MOON}),
    ("Mushroom", {WILD_MUSHROOM}),
    ("Starsurge", {STARSURGE}),
    ("Starfall", {STARFALL}),
    ("Starfire", {STARFIRE}),
    ("Wrath", {WRATH}),
    ("Moonfire", {MOONFIRE}),
    ("Sunfire", {SUNFIRE}),
]

# Derived rates. These are the ones that actually separate players: the first is
# a direct GCD-throughput proxy (every id here costs one GCD), and the second is
# the spender count the whole Astral Power economy exists to produce.
ALL_ROTATIONAL = set().union(*(g for _, g in CAST_METRICS))
DERIVED_METRICS = [
    ("ALL rotational GCDs", ALL_ROTATIONAL),
    ("spenders SS+SF", {STARSURGE, STARFALL}),
    ("fillers SFire+Wrath", {STARFIRE, WRATH}),
    ("DoT recasts MF+SF", {MOONFIRE, SUNFIRE}),
]

# Damage rows group by NAME because several abilities log under two guids
# (Starfall 191034/1301742, Starsurge 78674 + Star Cascade 1271222).
DMG_GROUPS = [
    ("Starfall", {"Starfall"}),
    ("Starfire", {"Starfire"}),
    ("Starsurge", {"Starsurge", "Starsurge (Star Cascade)"}),
    ("Moonfire", {"Moonfire"}),
    ("Sunfire", {"Sunfire"}),
    ("Shooting Stars", {"Shooting Stars"}),
    ("Fury of Elune", {"Fury of Elune"}),
    ("Astral Smolder", {"Astral Smolder"}),
    ("Ascendant Eclipses", {"Ascendant Eclipses"}),
    ("Denizen", {"Denizen of the Dream"}),
    ("Moon chain", {"Full Moon", "Half Moon", "New Moon", "Minor Moon"}),
    ("Treants", {"Treant", "Force of Nature", "Grove Guardian"}),
    ("Wrath", {"Wrath"}),
]

RANK_Q = '''query { worldData { encounter(id: %d) { name
  characterRankings(className: "Druid", specName: "Balance",
                    difficulty: %d, metric: dps, page: %d) } } }'''


def rankings(encounter_id, difficulty, pages=10, refresh=False):
    """Top `pages` * 100 logged pulls for this encounter, DPS-descending."""
    def go():
        out = []
        for p in range(1, pages + 1):
            r = W.query(RANK_Q % (encounter_id, difficulty, p))
            cr = r["data"]["worldData"]["encounter"]["characterRankings"]
            out.extend(cr["rankings"])
            if not cr.get("hasMorePages"):
                break
        return out
    return W.cached("_pool", "rank|%d|%d|%d" % (encounter_id, difficulty, pages),
                    go, refresh)


def profile(code, fight_id, player_name, duration_s):
    """Rate + damage-share profile for one player on one fight, from 3 tables."""
    def go():
        try:
            aid = W.actor_id(code, player_name)
        except SystemExit:
            return {"missing": True}
        casts = W.table(code, [fight_id], "Casts", source_id=aid)
        dmg = W.table(code, [fight_id], "DamageDone", source_id=aid)
        buffs = W.table(code, [fight_id], "Buffs", source_id=aid)

        by_guid = collections.Counter()
        for e in casts.get("entries", []):
            by_guid[str(e["guid"])] += e.get("total") or 0
        by_name = collections.Counter()
        ticks_by_name = collections.Counter()
        total_dmg = 0
        for e in dmg.get("entries", []):
            by_name[e["name"]] += e.get("total") or 0
            ticks_by_name[e["name"]] += e.get("tickCount") or 0
            total_dmg += e.get("total") or 0
        aura = {str(a["guid"]): (a.get("totalUptime") or a.get("uptime") or 0)
                for a in buffs.get("auras", [])}
        return {"casts": dict(by_guid), "dmg_by_name": dict(by_name),
                "ticks_by_name": dict(ticks_by_name),
                "total_dmg": total_dmg, "auras": aura}

    p = W.cached(code, "peerprof2|%s|%s" % (fight_id, player_name), go)
    if p.get("missing"):
        return None
    p = dict(p)
    p["duration"] = duration_s
    p["dps"] = p["total_dmg"] / duration_s if duration_s else 0
    p["casts"] = {int(k): v for k, v in p["casts"].items()}
    return p


def _rate(prof, guids):
    return 60.0 * sum(prof["casts"].get(g, 0) for g in guids) / prof["duration"]


def _share(prof, names):
    if not prof["total_dmg"]:
        return 0.0
    hit = sum(v for k, v in prof["dmg_by_name"].items() if k in names)
    return 100.0 * hit / prof["total_dmg"]


def _ticks_per_cast(prof, dot_name, cast_guid):
    """DoT ticks delivered per GCD spent applying it.

    The efficiency number for a DoT: `Aetherial Kindling` means Starfall already
    extends Moonfire/Sunfire, so a low value here is a player re-applying a DoT
    the rotation was extending for free - each one costs a spender's GCD.
    """
    casts = prof["casts"].get(cast_guid, 0)
    if not casts:
        return 0.0
    return (prof.get("ticks_by_name", {}).get(dot_name, 0)) / casts


DOT_EFFICIENCY = [("Moonfire ticks/cast", "Moonfire", MOONFIRE),
                  ("Sunfire ticks/cast", "Sunfire", SUNFIRE)]

# Buff uptimes, as a share of the fight. Solar and Lunar are reported separately
# on purpose: CA/Incarnation applies BOTH at once, so summing them double-counts
# every cooldown window (see .claude/knowledge/classes/druid/balance-druid-12.1.md).
AURA_METRICS = [
    ("Eclipse Solar up%", 48517),
    ("Eclipse Lunar up%", 48518),
    ("Ascendant Stars up%", 1263382),
    ("BoAT Arcane up%", 394049),
    ("Starlord up%", 279709),
]


def _aura_pct(prof, guid):
    return 100.0 * prof.get("auras", {}).get(str(guid), 0) / 1000.0 / prof["duration"]


#: A delta this far from the peer median is called out in the margin.
FLAG_PCT = 0.12


def _srow(s):
    """Render one comparison row from the payload.

    Byte-identical to `_stat_row`, but reading numbers the check already computed
    instead of recomputing them from peer profiles - `print()` may not read the
    log, and peer profiles are log reads.
    """
    fmt = s["format"]
    if not s["peers"]:
        return "  %-20s %9s   (no peers)" % (s["label"], fmt.format(s["mine"]))
    flag = ""
    if s["peerMedian"]:
        rel = s["delta"] / abs(s["peerMedian"])
        flag = "  <<<" if rel <= -FLAG_PCT else ("  +++" if rel >= FLAG_PCT else "")
    return ("  %-20s %9s | %9s %9s | %+9.2f | p%-4.0f%s"
            % (s["label"], fmt.format(s["mine"]), fmt.format(s["peerMedian"]),
               fmt.format(s["peerP90"]), s["delta"], s["percentile"], flag))


def _peer_profiles(sel):
    out = []
    for r in sel:
        p = profile(r["report"]["code"], r["report"]["fightID"],
                    r["name"], r["duration"] / 1000.0)
        if p:
            p["ilvl"] = r["bracketData"]
            p["name"] = r["name"]
            out.append(p)
    return out


class PeersCheck(C.PoolCheck):
    """You vs the ranking pool on one boss: rates, damage share, DoT efficiency.

    Two peer sets on purpose. The TOP 25 is what winning looks like; the
    ILVL-MATCHED 25 is what winning looks like *with your gear*, and the gap
    between the two answers "how much of this is the character rather than the
    play" before any rotation number is read.
    """

    id = "peers"
    title = "Peer comparison"
    group = "compare"
    SET_SIZE = 25
    ILVL_BAND = 2

    def params(self):
        return {"setSize": self.SET_SIZE, "ilvlBand": self.ILVL_BAND,
                "flagPct": 12}

    def fight_json(self, fight):
        skip = self._skip(fight)
        if skip:
            return {"skipped": skip}
        code, actor_id = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(actor_id, str(actor_id))
        enc, diff = fight["encounterID"], fight["difficulty"]
        dur = F.fight_seconds(fight)
        mine = profile(code, fight["id"], me, dur)
        summ = W.table(code, [fight["id"]], "Summary")
        my_ilvl = None
        for arr in (summ.get("playerDetails") or {}).values():
            for p in arr:
                if p.get("name") == me:
                    my_ilvl = p.get("maxItemLevel")

        pool = [r for r in rankings(enc, diff) if r["report"]["code"] != code]
        ilvls = [r["bracketData"] for r in pool]
        top = pool[:self.SET_SIZE]
        matched = [r for r in pool
                   if my_ilvl and abs(r["bracketData"] - my_ilvl) <= self.ILVL_BAND
                   ][:self.SET_SIZE]

        def stat(label, mine_v, peer_vals, fmt="{:.2f}"):
            v = sorted(peer_vals)
            if not v:
                return {"label": label, "mine": mine_v, "format": fmt, "peers": 0}
            med = statistics.median(v)
            return {
                "label": label, "mine": mine_v, "format": fmt, "peers": len(v),
                "peerMedian": med,
                "peerP90": v[min(len(v) - 1, int(len(v) * 0.9))],
                "delta": mine_v - med,
                "percentile": 100.0 * sum(1 for x in v if x < mine_v) / len(v),
            }

        sets = []
        for label, sel in (("TOP 25 (best parses in the pool)", top),
                           ("ILVL-MATCHED 25 (ilvl %s +-2)" % my_ilvl, matched)):
            profs = _peer_profiles(sel)
            if not profs:
                continue
            groups = [
                ("headline", [
                    stat("DPS", mine["dps"], [p["dps"] for p in profs], "{:.0f}"),
                    stat("fight length s", dur, [p["duration"] for p in profs], "{:.0f}"),
                    stat("item level", float(my_ilvl or 0),
                         [float(p["ilvl"]) for p in profs], "{:.0f}"),
                ]),
                ("throughput (derived rates)",
                 [stat(lab, _rate(mine, g), [_rate(p, g) for p in profs])
                  for lab, g in DERIVED_METRICS]),
                ("DoT efficiency (ticks delivered per GCD spent applying it)",
                 [stat(lab, _ticks_per_cast(mine, dn, g),
                       [_ticks_per_cast(p, dn, g) for p in profs])
                  for lab, dn, g in DOT_EFFICIENCY]),
                ("buff uptime (% of fight)",
                 [stat(lab, _aura_pct(mine, g), [_aura_pct(p, g) for p in profs])
                  for lab, g in AURA_METRICS
                  if max([_aura_pct(p, g) for p in profs] + [_aura_pct(mine, g)]) >= 1.0]),
                ("casts per minute",
                 [stat(lab, _rate(mine, g), [_rate(p, g) for p in profs])
                  for lab, g in CAST_METRICS
                  if max([_rate(p, g) for p in profs] + [_rate(mine, g)]) >= 0.05]),
                ("share of total damage (%)",
                 [stat(lab, _share(mine, n), [_share(p, n) for p in profs])
                  for lab, n in DMG_GROUPS
                  if max([_share(p, n) for p in profs] + [_share(mine, n)]) >= 0.3]),
            ]
            sets.append({"label": label, "peers": len(profs),
                         "groups": [{"heading": h, "rows": rows} for h, rows in groups]})

        return {
            "skipped": None, "name": fight["name"], "difficulty": diff, "actor": me,
            "itemLevel": my_ilvl, "seconds": dur, "dps": mine["dps"],
            "poolSize": len(pool),
            "poolDpsMin": min(r["amount"] for r in pool) if pool else 0,
            "poolDpsMax": max(r["amount"] for r in pool) if pool else 0,
            "poolAbove": sum(1 for r in pool if r["amount"] > mine["dps"]),
            "poolItemLevel": {"min": min(ilvls), "median": statistics.median(ilvls),
                              "max": max(ilvls)} if ilvls else None,
            "sets": sets,
        }

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if r["skipped"]:
                continue
            print("%s (difficulty %s) - %s @ ilvl %s, %.0fs, %s DPS"
                  % (r["name"], r["difficulty"], r["actor"], r["itemLevel"],
                     r["seconds"], format(int(r["dps"]), ",")))
            print("ranking pool: %d logged pulls, DPS %s - %s"
                  % (r["poolSize"], format(int(r["poolDpsMin"]), ","),
                     format(int(r["poolDpsMax"]), ",")))
            if r["poolAbove"] == r["poolSize"]:
                print("  every one of these %d pool entries is ABOVE you" % r["poolSize"])
            else:
                print("  %d of %d pool entries are above you"
                      % (r["poolAbove"], r["poolSize"]))
            pi = r["poolItemLevel"]
            if pi:
                print("  pool item level: min %s  median %.0f  max %s   <- yours is %s"
                      % (pi["min"], pi["median"], pi["max"], r["itemLevel"]))
            for s in r["sets"]:
                print("\n--- %s  (n=%d) ---" % (s["label"], s["peers"]))
                print("  %-20s %9s | %9s %9s | %9s | pct"
                      % ("metric", "YOU", "peer med", "peer p90", "delta"))
                print("  " + "-" * 76)
                for i, g in enumerate(s["groups"]):
                    if i:
                        print("\n  " + g["heading"])
                    for x in g["rows"]:
                        print(_srow(x))
            print("\n  '<<<' = you are >12%% BELOW the peer median, '+++' = >12%% above.")
            print("  Rates and damage shares are gear-robust; raw DPS is not.")
        self._skipped_note(d)


class PeersBuildsCheck(C.PoolCheck):
    """What the pool's builds look like - which optional abilities they cast at all.

    Reads the same cached profiles as `peers`. Answers "is my talent build the
    one the top parses are running", which no single-log check can see.
    """

    id = "peers-builds"
    title = "Build fingerprint"
    group = "compare"
    SET_SIZE = 25

    def params(self):
        return {"setSize": self.SET_SIZE}

    def fight_json(self, fight):
        skip = self._skip(fight)
        if skip:
            return {"skipped": skip}
        code, actor_id = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(actor_id, str(actor_id))
        enc, diff = fight["encounterID"], fight["difficulty"]
        dur = F.fight_seconds(fight)
        mine = profile(code, fight["id"], me, dur)
        pool = [r for r in rankings(enc, diff)
                if r["report"]["code"] != code][:self.SET_SIZE]
        profs = _peer_profiles(pool)
        rows = []
        for lab, guids in CAST_METRICS:
            users = [p for p in profs if _rate(p, guids) > 0]
            rows.append({
                "ability": lab,
                "youCast": _rate(mine, guids) > 0,
                "adoptionPct": 100.0 * len(users) / len(profs) if profs else 0,
                "peerMedianPerMin": (statistics.median([_rate(p, guids) for p in users])
                                     if users else 0.0),
            })
        return {"skipped": None, "peers": len(profs), "abilities": rows}

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if r["skipped"]:
                continue
            print("build fingerprint - share of the top %d who cast each ability at all"
                  % r["peers"])
            print("  %-20s %6s  %-28s %s"
                  % ("ability", "you", "top-25 adoption", "med/min"))
            print("  " + "-" * 74)
            for a in r["abilities"]:
                bar = "#" * int(a["adoptionPct"] / 4)
                print("  %-20s %6s  %-28s %.2f"
                      % (a["ability"], "YES" if a["youCast"] else "no",
                         "%3.0f%% %s" % (a["adoptionPct"], bar),
                         a["peerMedianPerMin"]))
            print("\n  A high adoption rate you are missing is a talent difference, not a")
            print("  rotation difference - check it against the tree before reading further.")
        self._skipped_note(d)


def secondaries(code, fight_id, player_name):
    """Rated secondaries for one player on one fight, from the Summary table.

    These are RATINGS as the log recorded them at the pull, not percentages, and
    they include raid buffs, so they are only comparable between players in the
    same expansion/patch - which is exactly what a same-encounter peer set is.
    """
    def go():
        t = W.table(code, [fight_id], "Summary")
        for arr in (t.get("playerDetails") or {}).values():
            for p in arr:
                if p.get("name") != player_name:
                    continue
                st = (p.get("combatantInfo") or {}).get("stats") or {}
                out = {k: (v or {}).get("min") for k, v in st.items()}
                out["ilvl"] = p.get("maxItemLevel")
                return out
        return {}
    return W.cached(code, "secondaries|%s|%s" % (fight_id, player_name), go)


STAT_KEYS = ["Crit", "Haste", "Mastery", "Versatility", "Intellect"]


class PeersStatsCheck(C.PoolCheck):
    """Secondary stat distribution across the peer set.

    Answers "is my gear itemised the way the people ahead of me itemise theirs",
    which is a separate question from how much item level they have. Rotation
    checks cannot see this, and a genuine itemisation gap would show up as a
    normal cast profile with low damage per cast - so read this together with
    the per-cast damage numbers, not instead of them.
    """

    id = "peers-stats"
    title = "Secondary stats vs peers"
    group = "compare"
    SET_SIZE = 25
    SECONDARIES = ("Crit", "Haste", "Mastery", "Versatility")

    def params(self):
        return {"setSize": self.SET_SIZE, "statKeys": list(STAT_KEYS),
                "secondaries": list(self.SECONDARIES)}

    def fight_json(self, fight):
        skip = self._skip(fight)
        if skip:
            return {"skipped": skip}
        code, actor_id = self.report.code, self.report.actor_id
        me = self.report.actor_names().get(actor_id, str(actor_id))
        enc, diff = fight["encounterID"], fight["difficulty"]
        mine = secondaries(code, fight["id"], me)
        pool = [r for r in rankings(enc, diff)
                if r["report"]["code"] != code][:self.SET_SIZE]
        rows = []
        for r in pool:
            s = secondaries(r["report"]["code"], r["report"]["fightID"], r["name"])
            if s and s.get("Haste") is not None:
                s["name"] = r["name"]
                s["dps"] = r["amount"]
                rows.append(s)

        def stat(label, mine_v, peer_vals, fmt="{:.2f}"):
            v = sorted(peer_vals)
            if not v:
                return {"label": label, "mine": mine_v, "format": fmt, "peers": 0}
            med = statistics.median(v)
            return {"label": label, "mine": mine_v, "format": fmt, "peers": len(v),
                    "peerMedian": med,
                    "peerP90": v[min(len(v) - 1, int(len(v) * 0.9))],
                    "delta": mine_v - med,
                    "percentile": 100.0 * sum(1 for x in v if x < mine_v) / len(v)}

        # Secondaries as a share of the total secondary budget - itemisation,
        # not amount. This is the half that item level does not explain.
        def mix(s):
            tot = sum(s.get(k) or 0 for k in self.SECONDARIES)
            return ({k: 100.0 * (s.get(k) or 0) / tot for k in self.SECONDARIES}
                    if tot else {})

        mymix = mix(mine)
        return {
            "skipped": None, "peers": len(rows), "itemLevel": mine.get("ilvl"),
            "peerItemLevelMedian": statistics.median([r.get("ilvl") or 0 for r in rows])
            if rows else None,
            "ratings": [stat(k, float(mine[k]),
                             [float(r[k]) for r in rows if r.get(k) is not None],
                             "{:.0f}")
                        for k in STAT_KEYS
                        if mine.get(k) is not None
                        and [r for r in rows if r.get(k) is not None]],
            "mix": [stat(k, mymix[k], [mix(r)[k] for r in rows if mix(r)])
                    for k in self.SECONDARIES
                    if k in mymix and [r for r in rows if mix(r)]],
        }

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if r["skipped"]:
                continue
            print("secondary stat ratings - you vs the top %d on this boss" % r["peers"])
            print("  (ratings as logged, raid buffs included; ilvl %s vs peer median %s)"
                  % (r["itemLevel"], r["peerItemLevelMedian"]))
            print()
            print("  %-14s %9s | %9s %9s | %9s | pct"
                  % ("stat", "YOU", "peer med", "peer p90", "delta"))
            print("  " + "-" * 70)
            for s in r["ratings"]:
                print(_srow(s))
            print("\n  itemisation mix (%% of total secondary rating)")
            for s in r["mix"]:
                print(_srow(s))
            print("\n  A stat gap only explains DPS if damage PER CAST is also low.")
            print("  If per-cast damage matches and only cast COUNT is low, the")
            print("  problem is rotation throughput and re-itemising will not fix it.")
        self._skipped_note(d)


CHECKS = C.registry(PeersCheck, PeersBuildsCheck, PeersStatsCheck)
