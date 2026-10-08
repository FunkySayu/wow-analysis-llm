"""Arcane Mage checks.

Every spell ID below was confirmed against real log data, not from memory. The
ones that bite are called out - see .claude/knowledge/classes/mage/arcane-mage-12.1-ptr.md.

Add a new check by subclassing `check.Check` (tools/warcraftlogs/lib/check.py): implement
`fight_json(fight)` for ONE pull plus an optional `combine(parts)`, and register it
in CHECKS below.
"""

import collections
import statistics

from lib import check as C
from lib import format as F
from lib import timeline as T
from lib import wclapi as W

# --- casts -------------------------------------------------------------------
MISSILES = 5143          # the CHANNEL. Produces NO DamageDone events.
BARRAGE = 44425
BLAST = 30451
PRISMATIC_BOLT = 1295924
ORB = 153626             # wrapper; real damage is child 153640 (arcane_orb_bolt)
ORB_BOLT = 153640
TOTM = 321507            # the CAST
SURGE = 365350
SUPERNOVA = 157980
EVOCATION = 12051
SHIMMER = 212653
TIME_WARP = 80353
MIRROR_IMAGE = 55342

# --- damage ids (differ from cast ids!) --------------------------------------
MISSILES_IMPACT = 7268   # <- use THIS for Missiles damage/wave counting
TOTM_EXPLOSION = 210833
METEORITE = 449569
PHOENIX = 448659

# --- auras -------------------------------------------------------------------
SALVO = 1242974          # stacking, cap 25 with Spellfire Salvo
CLEARCASTING = 263725    # caps at 3 stacks
INTUITION = 1223797
ARCANE_SOUL = 451038     # lands ~17.4s after Arcane Surge
SURGE_BUFF = 365362
OPM_PROC = 1277009
PBOLT_BUFF = 1295942
TOTM_DEBUFF = 210824     # on the ENEMY; carries targetID + targetInstance
CUMULATIVE_POWER = 1296930  # Season 2 4pc only

# --- external / raid cooldowns ----------------------------------------------
BLOODLUST = 2825
HEROISM = 32182
TIME_WARP_BUFF = 80353
PRIMAL_RAGE = 264667
FURY_OF_THE_ASPECTS = 390386
POWER_INFUSION = 10060
LUST_BUFFS = {BLOODLUST, HEROISM, TIME_WARP_BUFF, PRIMAL_RAGE, FURY_OF_THE_ASPECTS}

# cooldowns measured from minimum observed cast interval in real logs
CD_SECONDS = {TOTM: 45.0, SURGE: 90.0}

DAMAGING_CASTS = {MISSILES, BARRAGE, BLAST, PRISMATIC_BOLT, ORB, TOTM, SURGE, SUPERNOVA}

NAMES = {
    MISSILES: "Arcane Missiles", BARRAGE: "Arcane Barrage", BLAST: "Arcane Blast",
    PRISMATIC_BOLT: "Prismatic Bolt", ORB: "Arcane Orb", TOTM: "Touch of the Magi",
    SURGE: "Arcane Surge", SUPERNOVA: "Supernova", SHIMMER: "Shimmer",
    TIME_WARP: "Time Warp", EVOCATION: "Evocation", MIRROR_IMAGE: "Mirror Image",
}


# ============================================================== salvo cycle

class SalvoCheck(C.Check):
    """Arcane Salvo spent per Barrage, share at max stacks, time overcapped."""

    id = "salvo"
    title = "Arcane Salvo cycle"
    group = "mage"
    CAP = 25
    #: simc's own numbers for the same profile, for scale.
    BENCHMARK = {"salvoPerBarrage": 22.4, "atMaxPct": 65.0}

    def params(self):
        return {"cap": self.CAP, "benchmark": self.BENCHMARK}

    def fight_json(self, f):
        b = self.report.events(f, "Buffs")
        c = self.report.events(f, "Casts")
        tl = T.stack_timeline(b, SALVO)
        soul = T.windows(b, ARCANE_SOUL, default_ms=4000)
        barr = [(e["timestamp"], T.stacks_at(tl, e["timestamp"] + 1))
                for e in T.casts(c, BARRAGE)]
        ns = [s for t, s in barr if not T.in_windows(soul, t)]
        mis = [T.stacks_at(tl, e["timestamp"] + 1) for e in T.casts(c, MISSILES)]
        capped, pt, ps = 0.0, None, 0
        for t, s in tl:
            if pt is not None and ps >= self.CAP:
                capped += (t - pt) / 1000.0
            pt, ps = t, s
        d = F.fight_seconds(f)
        return {
            "label": F.fight_label(f),
            "seconds": d,
            # The stack counts themselves, not just their summary - the roll-up
            # needs them to weight correctly, and a component can histogram them.
            "nonSoulSpends": ns,
            "missilesSpends": mis,
            "cappedSeconds": capped,
            "cappedPct": F.pct(capped, d),
            "barrages": len(ns),
            "meanSalvo": statistics.mean(ns) if ns else None,
            "atMaxPct": F.pct(sum(1 for s in ns if s >= self.CAP), len(ns)),
            "belowTwentyPct": F.pct(sum(1 for s in ns if s < 20), len(ns)),
            "missilesAboveTwelvePct": F.pct(sum(1 for s in mis if s >= 12), len(mis)),
        }

    def combine(self, parts):
        live = [d for _, d in parts if d["barrages"]]
        n = sum(d["barrages"] for d in live)
        spends = [s for d in live for s in d["nonSoulSpends"]]
        return {
            "fights": len(live),
            "barrages": n,
            # Weighted by Barrage count, not a mean of per-fight means: a 12-cast
            # pull and a 2-cast pull are not equal evidence.
            "meanSalvo": (sum(d["meanSalvo"] * d["barrages"] for d in live) / n) if n else 0.0,
            "atMaxPct": (sum(d["atMaxPct"] * d["barrages"] for d in live) / n) if n else 0.0,
            "spendHistogram": dict(sorted(collections.Counter(spends).items())),
            "cappedSeconds": sum(d["cappedSeconds"] for d in live),
        }

    def print(self):
        d = self.json()
        print(F.hdr(["fight", "dur", "Barr", "avgSalvo", "at25", "<20", "capped%", "AM>=12%"],
                    [26, 6, 5, 9, 7, 7, 8, 8]))
        for row in d["fights"]:
            r = row["data"]
            if not r["barrages"]:
                continue
            print(f"{r['label'][:26]:26}  {r['seconds']:<6.0f}  {r['barrages']:<5d}  "
                  f"{r['meanSalvo']:<9.1f}  {r['atMaxPct']:<7.1f}  "
                  f"{r['belowTwentyPct']:<7.1f}  {r['cappedPct']:<8.1f}  "
                  f"{r['missilesAboveTwelvePct']:<8.1f}")
        o = d["overall"]
        if o["fights"]:
            print(f"\n{o['fights']} fights, {o['barrages']} non-Soul Barrages, "
                  f"weighted avg Salvo {o['meanSalvo']:.1f}, "
                  f"at max {o['atMaxPct']:.1f}%")
        bm = d["params"]["benchmark"]
        print(f"\nBenchmark: simc spends {bm['salvoPerBarrage']} Salvo/Barrage with "
              f"{bm['atMaxPct']:.0f}% at max stacks.")


# ============================================================== arcane soul

class SoulCheck(C.Check):
    """Arcane Soul window setup: Soul lands 17.4s after Surge and Barrages inside
    it do NOT consume Salvo, so entry stacks are the whole value of the window."""

    id = "soul"
    title = "Arcane Soul windows"
    group = "mage"

    def fight_json(self, f):
        b = self.report.events(f, "Buffs")
        c = self.report.events(f, "Casts")
        tl = T.stack_timeline(b, SALVO)
        surge = [e["timestamp"] for e in b
                 if e.get("abilityGameID") == SURGE_BUFF and e["type"] == "applybuff"]
        soul = T.windows(b, ARCANE_SOUL, default_ms=4000)
        barr = [e["timestamp"] for e in T.casts(c, BARRAGE)]
        windows = []
        for s, e in soul:
            pr = [x for x in surge if x < s]
            pb = [x for x in barr if x < s]
            windows.append({
                "at": F.mmss(s, f["startTime"]),
                "start": s,
                "surgeLagSeconds": (s - pr[-1]) / 1000.0 if pr else None,
                "secondsSinceLastBarrage": (s - pb[-1]) / 1000.0 if pb else None,
                "salvoOnEntry": T.stacks_at(tl, s),
                "barragesInside": sum(1 for x in barr if s <= x <= e),
            })
        return {"windows": windows}

    def combine(self, parts):
        wins = [w for _, d in parts for w in d["windows"]]
        lags = [w["surgeLagSeconds"] for w in wins if w["surgeLagSeconds"] is not None]
        predump = [w["secondsSinceLastBarrage"] for w in wins
                   if w["secondsSinceLastBarrage"] is not None]
        entry = [w["salvoOnEntry"] for w in wins]
        nbarr = [w["barragesInside"] for w in wins]
        if not entry:
            return {"windows": 0}
        return {
            "windows": len(wins),
            "surgeLag": {
                "median": statistics.median(lags), "n": len(lags),
                "p10": sorted(lags)[len(lags) // 10] if lags else None,
                "p90": sorted(lags)[int(len(lags) * .9)] if lags else None,
            } if lags else None,
            "salvoOnEntry": {
                "mean": statistics.mean(entry), "median": statistics.median(entry),
                "min": min(entry), "max": max(entry),
                "atMaxPct": F.pct(sum(1 for x in entry if x >= 25), len(entry)),
                "belowFifteenPct": F.pct(sum(1 for x in entry if x < 15), len(entry)),
            },
            "predump": {
                "underThreeSecondsPct": F.pct(sum(1 for x in predump if x < 3), len(predump)),
                "medianGapSeconds": statistics.median(predump) if predump else None,
            },
            "barragesInsideMean": statistics.mean(nbarr),
        }

    def print(self):
        d = self.json()["overall"]
        if not d["windows"]:
            print("no Arcane Soul windows found")
            return
        print(f"Arcane Soul windows: {d['windows']}")
        lag = d["surgeLag"]
        print(f"  Arcane Surge -> Soul lag      : median {lag['median']:.1f}s  "
              f"(n={lag['n']}, spread p10-p90 "
              f"{lag['p10']:.1f}-{lag['p90']:.1f}s)")
        e = d["salvoOnEntry"]
        print(f"  Salvo on entry                : mean {e['mean']:.1f} / 25   "
              f"median {e['median']:.0f}   min {e['min']}   max {e['max']}")
        print(f"     entered at 25 (Intuition)  : {e['atMaxPct']:.0f}%")
        print(f"     entered below 15           : {e['belowFifteenPct']:.0f}%")
        p = d["predump"]
        print(f"  Barrage fired <3s before Soul : "
              f"{p['underThreeSecondsPct']:.0f}%  "
              f"(median gap {p['medianGapSeconds']:.1f}s)   <-- dumping the window")
        print(f"  Barrages inside the window    : mean {d['barragesInsideMean']:.1f}")
        print("\nFix: Soul is on a clock. After Arcane Surge, count ~17s and bank Salvo to 25\n"
              "rather than spending it in the last GCDs before the window opens.")


# ============================================================== clearcasting

class ClearcastingCheck(C.Check):
    """Clearcasting capped at 3 = procs thrown away. High Salvo blocks Missiles
    (APL gate arcane_salvo.stack<12), which is what causes the cap."""

    id = "clearcasting"
    title = "Clearcasting waste"
    group = "mage"
    CAP = 3

    def params(self):
        return {"cap": self.CAP}

    def fight_json(self, f):
        b = sorted(self.report.events(f, "Buffs"), key=lambda x: x["timestamp"])
        capped_s = 0.0
        wasted = 0
        st, last = 0, None
        for e in b:
            if e.get("abilityGameID") != CLEARCASTING:
                continue
            t = e["timestamp"]
            if last is not None and st >= self.CAP:
                capped_s += (t - last) / 1000.0
            ty = e["type"]
            if ty == "applybuff":
                st = 1
            elif ty in ("applybuffstack", "removebuffstack"):
                st = e.get("stack", 0)
            elif ty == "refreshbuff":
                if st >= self.CAP:
                    wasted += 1
            elif ty == "removebuff":
                st = 0
            last = t
        d = F.fight_seconds(f)
        return {"seconds": d, "cappedSeconds": capped_s, "cappedPct": F.pct(capped_s, d),
                "procsOntoFull": wasted}

    def combine(self, parts):
        total = sum(d["seconds"] for _, d in parts)
        capped = sum(d["cappedSeconds"] for _, d in parts)
        return {"fights": len(parts), "seconds": total, "cappedSeconds": capped,
                "cappedPct": F.pct(capped, total),
                "procsOntoFull": sum(d["procsOntoFull"] for _, d in parts)}

    def print(self):
        d = self.json()["overall"]
        print(f"across {d['fights']} fights / {d['seconds']:.0f}s")
        print(f"  time at 3/3 Clearcasting : {d['cappedSeconds']:.0f}s  "
              f"({d['cappedPct']:.1f}% of combat)")
        print(f"  procs onto a full buff   : {int(d['procsOntoFull'])}  "
              f"(hard-wasted, ~1 free Missiles each)")
        print("\nRelease valve: the APL allows Barrage at Salvo>=12 WHEN Clearcasting is banked,\n"
              "specifically to unblock Missiles. That is the one case where an early dump is right.")


# ============================================ NEW: Touch of the Magi targeting

class TomTargetCheck(C.Check):
    """How much of the Touch of the Magi window is spent hitting something else.

    ToM stores a share of damage dealt TO THE DEBUFFED TARGET and detonates at the
    end. Damage into any other target during the window does not feed the explosion,
    so time off the ToM'd target is the direct loss.
    """

    id = "tom-target"
    title = "Touch of the Magi targeting"
    group = "mage"
    SLICE = 500        # ms; a damaging slice is "off" if nothing landed on the target
    BIGGER = 1.5       # a target this much larger, hit in the same window, is misplacement

    def params(self):
        return {"sliceMs": self.SLICE, "biggerTargetRatio": self.BIGGER}

    def _names(self):
        if not hasattr(self, "_name_cache"):
            self._name_cache = self.report.actor_names()
        return self._name_cache

    def fight_json(self, f):
        names = self._names()
        deb = self.report.events(f, "Debuffs", ability_id=TOTM_DEBUFF)
        dmg = self.report.events(f, "DamageDone", resources=True)
        if not deb:
            return {"label": F.fight_label(f), "windows": [], "damageOn": 0,
                    "damageOff": 0, "onTimeSeconds": 0.0, "offTimeSeconds": 0.0}

        # windows per (targetID, targetInstance)
        open_ = {}
        wins = []
        for e in sorted(deb, key=lambda x: x["timestamp"]):
            key = (e.get("targetID"), e.get("targetInstance", 1))
            if e["type"] in ("applydebuff", "refreshdebuff"):
                open_.setdefault(key, e["timestamp"])
            elif e["type"] == "removedebuff" and key in open_:
                wins.append((open_.pop(key), e["timestamp"], key))
        for k, s in open_.items():
            wins.append((s, s + 12000, k))

        maxhp = {}
        for e in dmg:
            k = (e.get("targetID"), e.get("targetInstance", 1))
            if e.get("maxHitPoints"):
                maxhp[k] = max(maxhp.get(k, 0), e["maxHitPoints"])

        out = []
        f_on = f_off = 0
        f_ont = f_offt = 0.0
        for s, e, key in wins:
            ev = [x for x in dmg if s <= x["timestamp"] <= e]
            on = sum(x.get("amount", 0) + x.get("absorbed", 0)
                     for x in ev if (x.get("targetID"), x.get("targetInstance", 1)) == key)
            off = sum(x.get("amount", 0) + x.get("absorbed", 0) for x in ev) - on
            f_on += on
            f_off += off
            buckets = collections.defaultdict(lambda: [0, 0])
            for x in ev:
                b = (x["timestamp"] - s) // self.SLICE
                hit_on = (x.get("targetID"), x.get("targetInstance", 1)) == key
                buckets[b][0 if hit_on else 1] += x.get("amount", 0)
            w_ont = w_offt = 0.0
            for _b, (o, u) in buckets.items():
                if o > 0:
                    w_ont += self.SLICE / 1000.0
                elif u > 0:
                    w_offt += self.SLICE / 1000.0
            f_ont += w_ont
            f_offt += w_offt
            hp = maxhp.get(key, 0)
            # was a bigger target being hit during this same window?
            present = {}
            for x in ev:
                k2 = (x.get("targetID"), x.get("targetInstance", 1))
                if x.get("maxHitPoints"):
                    present[k2] = max(present.get(k2, 0), x["maxHitPoints"])
            bigger = None
            if present:
                best_k = max(present, key=lambda k2: present[k2])
                if present[best_k] > hp * self.BIGGER:
                    bigger = {"name": names.get(best_k[0], "?"), "maxHp": present[best_k]}
            out.append({
                "at": F.mmss(s, f["startTime"]),
                "start": s,
                "fightLabel": F.fight_label(f),
                "target": names.get(key[0], f"#{key[0]}"),
                "targetMaxHp": hp,
                "damageOn": on,
                "damageOff": off,
                "onTargetPct": F.pct(on, on + off) if on + off else None,
                "onTimeSeconds": w_ont,
                "offTimeSeconds": w_offt,
                "biggerTargetHit": bigger,
            })
        return {"label": F.fight_label(f), "windows": out,
                "damageOn": f_on, "damageOff": f_off,
                "onTimeSeconds": f_ont, "offTimeSeconds": f_offt,
                "onTargetPct": F.pct(f_on, f_on + f_off) if f_on + f_off else None}

    def combine(self, parts):
        wins = [w for _, d in parts for w in d["windows"]]
        on = sum(d["damageOn"] for _, d in parts)
        off = sum(d["damageOff"] for _, d in parts)
        on_t = sum(d["onTimeSeconds"] for _, d in parts)
        off_t = sum(d["offTimeSeconds"] for _, d in parts)
        hps = [w["targetMaxHp"] for w in wins if w["targetMaxHp"]]
        misplaced = [w for w in wins if w["biggerTargetHit"]]
        med = statistics.median(hps) if hps else None
        return {
            "windows": len(wins),
            "damageOn": on, "damageOff": off,
            "onPct": F.pct(on, on + off), "offPct": F.pct(off, on + off),
            "onTimeSeconds": on_t, "offTimeSeconds": off_t,
            "offTimePct": F.pct(off_t, on_t + off_t),
            "targetMaxHp": {"median": med, "min": min(hps), "max": max(hps)} if hps else None,
            # Windows put on something under a quarter of the median-sized target:
            # almost always a trash add picked up instead of the priority target.
            "smallTargets": sorted(
                (w for w in wins if med and w["targetMaxHp"] and w["targetMaxHp"] < med / 4),
                key=lambda w: (w["onTargetPct"] if w["onTargetPct"] is not None else 0,
                               w["fightLabel"]))[:10],
            "misplaced": misplaced,
            "misplacedPct": F.pct(len(misplaced), len(wins)),
            "worst": sorted((w for w in wins if w["onTargetPct"] is not None),
                            key=lambda w: (w["onTargetPct"], w["fightLabel"]))[:10],
        }

    def print(self):
        d = self.json()
        o = d["overall"]
        if not o["windows"]:
            print("no Touch of the Magi debuff windows found")
            return
        print(F.hdr(["fight", "ToM", "dmg on target", "off-target s"], [26, 5, 14, 12]))
        for row in d["fights"]:
            r = row["data"]
            if not (r["damageOn"] + r["damageOff"]):
                continue
            print(f"{r['label'][:26]:26}  {len(r['windows']):<5d}  "
                  f"{r['onTargetPct']:<14.1f}  {r['offTimeSeconds']:<12.1f}")
        print(f"\n{o['windows']} Touch of the Magi windows")
        print(f"  damage into the ToM'd target : {o['onPct']:.1f}%  ({o['damageOn']:,.0f})")
        print(f"  damage into anything else    : {o['offPct']:.1f}%  ({o['damageOff']:,.0f})")
        print(f"  active time on the target    : {o['onTimeSeconds']:.0f}s")
        print(f"  active time OFF the target   : {o['offTimeSeconds']:.0f}s  "
              f"({o['offTimePct']:.1f}% of damaging time in window)")
        hp = o["targetMaxHp"]
        if hp:
            print(f"  ToM'd target max HP          : median {hp['median']:,.0f}   "
                  f"min {hp['min']:,.0f}   max {hp['max']:,.0f}")
            if o["smallTargets"]:
                print(f"\n  {len(o['smallTargets'])} window(s) placed on a target under a "
                      "quarter of the median HP - likely a trash add rather than the "
                      "priority target:")
                for w in o["smallTargets"]:
                    print(f"     {w['fightLabel'][:22]:22} -> {w['target'][:26]:26} "
                          f"maxHP {w['targetMaxHp']:>13,.0f}   "
                          f"on-target {w['onTargetPct']:.0f}%")
        print(f"\n  Placement: {len(o['misplaced'])}/{o['windows']} window(s) "
              f"({o['misplacedPct']:.0f}%) put ToM on a target while something with "
              ">1.5x its HP\n             was being damaged in the same window "
              "(0% = always on the biggest thing you were hitting).")
        for w in o["misplaced"][:8]:
            b = w["biggerTargetHit"]
            print(f"     {w['fightLabel'][:22]:22} ToM on {w['target'][:20]:20} "
                  f"({w['targetMaxHp']:>12,.0f})  "
                  f"while hitting {b['name'][:20]:20} ({b['maxHp']:>12,.0f})")
        if o["worst"]:
            print("\n  Worst windows by share of damage that actually fed the explosion:")
            for w in o["worst"]:
                print(f"     {w['onTargetPct']:>5.1f}%  {w['fightLabel'][:22]:22} -> "
                      f"{w['target'][:26]:26} maxHP {w['targetMaxHp']:>13,.0f}")


# ==================================================== NEW: cooldown alignment

def _pulls(code, fid, aid, gap_s=12):
    """Segment a fight into pulls from the player's own damage, and describe each
    pull's size (distinct enemies), effective HP (sum of enemy maxHitPoints) and
    danger (damage taken by friendlies during it)."""
    dmg = W.events(code, fid, "DamageDone", aid, resources=True)
    if not dmg:
        return []
    segs = T.segments([e["timestamp"] for e in dmg], gap_s * 1000)
    taken = W.events(code, fid, "DamageTaken", hostility="Friendlies")
    out = []
    for s, e, _ in segs:
        ev = [x for x in dmg if s <= x["timestamp"] <= e]
        hp = {}
        mine = 0
        for x in ev:
            k = (x.get("targetID"), x.get("targetInstance", 1))
            if x.get("maxHitPoints"):
                hp[k] = max(hp.get(k, 0), x["maxHitPoints"])
            mine += x.get("amount", 0)
        dt = sum(x.get("amount", 0) for x in taken if s <= x["timestamp"] <= e)
        out.append({"start": s, "end": e, "dur": (e - s) / 1000.0,
                    "enemies": len(hp), "packhp": sum(hp.values()),
                    "mydmg": mine, "taken": dt})
    return out


def _overlap(wins, a, b):
    return sum(max(0, min(b, y) - max(a, x)) for x, y in wins) / 1000.0


class CooldownsCheck(C.Check):
    """Are the big cooldowns landing on the moments that matter?

    Three questions: do they line up with Bloodlust, do they land on the biggest /
    most dangerous packs, and how much cooldown time is left banked."""

    id = "cooldowns"
    title = "Cooldown placement"
    group = "mage"
    #: Arcane Surge lasts ~18s, so one Surge can cover at most that much of a
    #: 40s lust - the ceiling the coverage percentage is read against.
    SURGE_DURATION = 18.0

    def params(self):
        return {"cooldownSeconds": {"Arcane Surge": CD_SECONDS[SURGE],
                                    "Touch of the Magi": CD_SECONDS[TOTM]},
                "surgeDurationSeconds": self.SURGE_DURATION}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        c = self.report.events(f, "Casts")
        b = self.report.events(f, "Buffs")
        d = F.fight_seconds(f)
        surge = [e["timestamp"] for e in T.casts(c, SURGE)]
        totm = [e["timestamp"] for e in T.casts(c, TOTM)]
        lust = []
        for g in LUST_BUFFS:
            lust += T.windows(b, g, default_ms=40000)
        lust.sort()

        avail = []
        for gid, name in ((SURGE, "Arcane Surge"), (TOTM, "Touch of the Magi")):
            ts = surge if gid == SURGE else totm
            cd = CD_SECONDS[gid]
            poss = 1 + int(d // cd)
            banked = 0.0
            prev = f["startTime"]
            for t in ts:
                banked += max(0.0, (t - prev) / 1000.0 - cd)
                prev = t
            banked += max(0.0, (f["endTime"] - prev) / 1000.0 - cd)
            avail.append({"name": name, "used": len(ts), "possible": poss,
                          "usedPct": F.pct(len(ts), poss), "idleSeconds": banked,
                          "idlePct": F.pct(banked, d)})

        # Measure BUFF OVERLAP, not "was the cast inside the window" - a Surge cast one
        # second before lust lands is perfectly aligned, and a cast-based test calls it random.
        lust_block = None
        if lust:
            lu = sum((y - x) / 1000.0 for x, y in lust)
            sw = T.windows(b, SURGE_BUFF, default_ms=20000)
            deb = self.report.events(f, "Debuffs", ability_id=TOTM_DEBUFF)
            tw = T.windows(deb, TOTM_DEBUFF, apply_types=("applydebuff", "refreshdebuff"),
                           remove_types=("removedebuff",), default_ms=12000)
            per = []
            for i, (a, y) in enumerate(lust, 1):
                cov = F.pct(_overlap(sw, a, y), (y - a) / 1000.0)
                prior = [t for t in surge if t < a]
                gap = (a - prior[-1]) / 1000.0 if prior else 999
                if cov >= 25:
                    verdict = f"Surge up for {cov:.0f}% of it"
                elif gap >= CD_SECONDS[SURGE]:
                    verdict = f"Surge READY ({gap:.0f}s since last) and not used - MISSED"
                else:
                    verdict = (f"Surge on cooldown - last cast {gap:.0f}s before lust "
                               f"(needs {CD_SECONDS[SURGE]:.0f}s); bank it next time")
                per.append({"n": i, "atSeconds": (a - f["startTime"]) / 1000.0,
                            "surgeCoveragePct": cov, "secondsSinceSurge": gap,
                            "verdict": verdict})
            lust_block = {
                "windows": len(lust), "seconds": lu, "fightPct": F.pct(lu, d),
                "surgeOverlapSeconds": sum(_overlap(sw, a, y) for a, y in lust),
                "surgeOverlapPct": F.pct(sum(_overlap(sw, a, y) for a, y in lust), lu),
                "surgeCeilingPct": F.pct(self.SURGE_DURATION * len(lust), lu),
                "tomOverlapSeconds": sum(_overlap(tw, a, y) for a, y in lust),
                "tomOverlapPct": F.pct(sum(_overlap(tw, a, y) for a, y in lust), lu),
                "perWindow": per,
            }

        pl = [p for p in _pulls(code, f["id"], aid) if p["dur"] >= 5 and p["packhp"] > 0]
        packs = None
        if len(pl) >= 3:
            for p in pl:
                p["surge"] = any(p["start"] <= t <= p["end"] for t in surge)
                p["totm"] = sum(1 for t in totm if p["start"] <= t <= p["end"])
                # was Arcane Surge off cooldown when the pull started?
                prior = [t for t in surge if t < p["start"]]
                p["ready"] = (not prior) or (p["start"] - prior[-1]) / 1000.0 >= CD_SECONDS[SURGE]
            by_hp = sorted(pl, key=lambda p: -p["packhp"])
            n_top = max(3, len(pl) // 4)
            top, rest = by_hp[:n_top], by_hp[n_top:]
            missed = [p for p in pl if p["ready"] and not p["surge"]]
            packs = {
                "pulls": len(pl),
                "topQuartileCovered": sum(1 for p in top if p["surge"]), "topQuartile": len(top),
                "restCovered": sum(1 for p in rest if p["surge"]), "rest": len(rest),
                "readyButUnused": len(missed),
                "biggestMissedPackHp": max((p["packhp"] for p in missed), default=None),
                "byPackHp": by_hp[:8],
                "byDanger": sorted(pl, key=lambda p: -p["taken"])[:3],
            }
        return {"label": F.fight_label(f), "seconds": d, "availability": avail,
                "lust": lust_block, "packs": packs}

    def print(self):
        for row in self.json()["fights"]:
            r = row["data"]
            print(f"\n=== {r['label']}  ({r['seconds']:.0f}s) ===")
            for a in r["availability"]:
                print(f"  {a['name']:18} {a['used']:>2d}/{a['possible']} used "
                      f"({a['usedPct']:3.0f}%)   "
                      f"cooldown left idle: {a['idleSeconds']:.0f}s ({a['idlePct']:.0f}% of fight)")
            lu = r["lust"]
            if lu:
                print(f"  Bloodlust/Time Warp: {lu['windows']} window(s), {lu['seconds']:.0f}s "
                      f"({lu['fightPct']:.0f}% of the fight)")
                print(f"     lust seconds with Arcane Surge up      : "
                      f"{lu['surgeOverlapSeconds']:.0f}/{lu['seconds']:.0f}s "
                      f"({lu['surgeOverlapPct']:.0f}%)   [ceiling ~"
                      f"{lu['surgeCeilingPct']:.0f}%: Surge lasts ~18s per 40s lust]")
                print(f"     lust seconds with Touch of the Magi up : "
                      f"{lu['tomOverlapSeconds']:.0f}/{lu['seconds']:.0f}s "
                      f"({lu['tomOverlapPct']:.0f}%)")
                for w in lu["perWindow"]:
                    print(f"       lust #{w['n']} @{w['atSeconds']:.0f}s: {w['verdict']}")
            else:
                print("  Bloodlust/Time Warp: none in this fight")
            p = r["packs"]
            if not p:
                continue
            print(f"  Pulls: {p['pulls']}   (pack HP = sum of enemy max HP; "
                  "danger = party damage taken)")
            print(f"     Surge on a top-quartile pull : "
                  f"{p['topQuartileCovered']}/{p['topQuartile']}"
                  f"     on the rest: {p['restCovered']}/{p['rest']}")
            print(f"     Pulls where Surge was READY but unused: {p['readyButUnused']}"
                  + (f"  (biggest: {p['biggestMissedPackHp']:,.0f} pack HP)"
                     if p["biggestMissedPackHp"] is not None else ""))
            print(f"     {'#':>3} {'dur':>5} {'foes':>5} {'pack HP':>13} {'danger':>13} "
                  f"{'Surge':>6} {'rdy':>4} {'ToM':>4}")
            for i, q in enumerate(p["byPackHp"], 1):
                flag = "YES" if q["surge"] else ("MISS" if q["ready"] else "cd")
                print(f"     {i:>3} {q['dur']:>5.0f} {q['enemies']:>5d} {q['packhp']:>13,.0f} "
                      f"{q['taken']:>13,.0f} {flag:>6} {'Y' if q['ready'] else '-':>4} "
                      f"{q['totm']:>4d}")
            print("     most dangerous packs (by party damage taken):")
            for q in p["byDanger"]:
                print(f"        {q['taken']:>13,.0f} taken, {q['enemies']:>2d} foes, "
                      f"{q['packhp']:>13,.0f} HP  ->  Surge {'YES' if q['surge'] else 'no '}, "
                      f"ToM x{q['totm']}")


# ============================================================== missiles waves

class WavesCheck(C.Check):
    """Waves per Arcane Missiles channel. Base 7; the Season 2 2pc makes it 8.

    Read the MODE, not the mean - multi-target channels stack whole multiples
    (7/14/21/42 vs 8/16/24/32)."""

    id = "waves"
    title = "Missiles wave count"
    group = "mage"
    #: A gap over this splits one channel from the next.
    CHANNEL_GAP_MS = 700
    MIN_WAVES = 3
    #: A mode is "strong" at a quarter of the tallest bar - enough to ignore the
    #: long tail of clipped channels without needing the single tallest bar to be
    #: the base case (on cleave it usually is not).
    STRONG = 0.25

    def params(self):
        return {"channelGapMs": self.CHANNEL_GAP_MS, "minWaves": self.MIN_WAVES,
                "strongModeShare": self.STRONG}

    def fight_json(self, f):
        ts = [e["timestamp"] for e in
              self.report.events(f, "DamageDone", ability_id=MISSILES_IMPACT)]
        return {"channels": [n for _, _, n in T.segments(ts, self.CHANNEL_GAP_MS)
                             if n >= self.MIN_WAVES]}

    def combine(self, parts):
        ch = [n for _, d in parts for n in d["channels"]]
        if not ch:
            return {"channels": 0}
        h = collections.Counter(ch)
        base = min((k for k, v in h.items() if v >= max(h.values()) * self.STRONG), default=0)
        return {
            "channels": len(ch),
            "mean": statistics.mean(ch),
            "median": statistics.median(ch),
            "histogram": [{"waves": k, "count": v}
                          for k, v in sorted(h.items(), key=lambda x: -x[1])],
            "lowestStrongMode": base,
            "twoPiece": (True if base >= 8 else False if base == 7 else None),
        }

    def print(self):
        d = self.json()["overall"]
        if not d["channels"]:
            print("no Arcane Missiles impacts (ability 7268) found")
            return
        print(f"channels: {d['channels']}   mean {d['mean']:.2f}   median {d['median']}")
        print("wave-count histogram (top 12):")
        for row in d["histogram"][:12]:
            print(f"   {row['waves']:>3d} waves : {'#' * min(60, row['count'])} {row['count']}")
        verdict = ("2-piece PRESENT (8)" if d["twoPiece"] else
                   "2-piece ABSENT (7)" if d["twoPiece"] is False else "inconclusive")
        print(f"\nlowest strong mode = {d['lowestStrongMode']} waves  ->  {verdict}")


# ============================================================== channel gaps

class GapsCheck(C.Check):
    """Dead time after an Arcane Missiles channel ends (channel end = last Salvo tick)."""

    id = "gaps"
    title = "Post-channel dead time"
    group = "mage"
    THRESHOLDS = (0.5, 1.0, 2.0)

    def params(self):
        return {"thresholdsSeconds": list(self.THRESHOLDS)}

    def fight_json(self, f):
        c = self.report.events(f, "Casts")
        b = self.report.events(f, "Buffs")
        sal = sorted(e["timestamp"] for e in b if e.get("abilityGameID") == SALVO
                     and e["type"] in ("applybuff", "applybuffstack"))
        dm = [e for e in T.casts(c) if e["abilityGameID"] in DAMAGING_CASTS]
        delays = []
        for i, e in enumerate(dm[:-1]):
            if e["abilityGameID"] != MISSILES:
                continue
            nxt = dm[i + 1]["timestamp"]
            # The channel's own Salvo ticks mark where it really ended; the cast
            # event only says where it started.
            tk = [t for t in sal if e["timestamp"] < t <= min(nxt, e["timestamp"] + 7000)]
            if len(tk) >= 2:
                delays.append({"at": F.mmss(e["timestamp"], f["startTime"]),
                               "timestamp": e["timestamp"],
                               "delaySeconds": (nxt - tk[-1]) / 1000.0})
        return {"seconds": F.fight_seconds(f), "delays": delays}

    def combine(self, parts):
        delays = [x["delaySeconds"] for _, d in parts for x in d["delays"]]
        total = sum(d["seconds"] for _, d in parts)
        if not delays:
            return {"channels": 0, "seconds": total}
        return {
            "channels": len(delays),
            "seconds": total,
            "medianDelaySeconds": statistics.median(delays),
            "overThreshold": [{"seconds": th,
                               "pct": F.pct(sum(1 for x in delays if x > th), len(delays))}
                              for th in self.THRESHOLDS],
            "deadSeconds": sum(delays),
            "deadPct": F.pct(sum(delays), total),
        }

    def print(self):
        d = self.json()["overall"]
        if not d["channels"]:
            print("no channels measured")
            return
        print(f"channels measured: {d['channels']}")
        print(f"  median delay after channel : {d['medianDelaySeconds']:.2f}s")
        for t in d["overThreshold"]:
            print(f"  over {t['seconds']:.1f}s                  : {t['pct']:.0f}%")
        print(f"  total dead time            : {d['deadSeconds']:.0f}s of "
              f"{d['seconds']:.0f}s ({d['deadPct']:.1f}%)")


# ============================================================== gear audit

class GearCheck(C.Check):
    """Enchants, gems and secondaries for every player in the report - the control
    test that separates 'this player has none' from 'the log does not record them'."""

    id = "gear"
    title = "Gear and enchants"
    group = "mage"
    STANDARD = {"enchants": 8, "gems": 7}

    def params(self):
        return {"standard": self.STANDARD}

    def _names(self):
        if not hasattr(self, "_name_cache"):
            self._name_cache = self.report.actor_names()
        return self._name_cache

    def fight_json(self, f):
        names = self._names()
        ev = self.report.events(f, "CombatantInfo", source_id=None)
        rows = []
        for e in sorted(ev, key=lambda x: -(x.get("intellect") or 0)):
            worn = [g for g in (e.get("gear") or []) if g.get("id")]
            if not worn:
                continue
            sets = collections.Counter(g["setID"] for g in worn if g.get("setID"))
            rows.append({
                "playerId": e.get("sourceID"),
                "name": names.get(e.get("sourceID"), "?"),
                "isActor": e.get("sourceID") == self.report.actor_id,
                "itemLevel": sum(g["itemLevel"] for g in worn) / len(worn),
                "enchants": sum(1 for g in worn if g.get("permanentEnchant")),
                "gems": sum(len(g.get("gems") or []) for g in worn),
                "intellect": e.get("intellect", 0),
                "secondaries": sum(e.get(k, 0) for k in
                                   ("critSpell", "hasteSpell", "mastery",
                                    "versatilityDamageDone")),
                "sets": {str(k): v for k, v in sets.items()},
            })
        return {"roster": rows}

    def combine(self, parts):
        """Gear from the first pull, and who re-geared after it.

        Unlike consumables, gear rarely changes mid-night - but a swapped trinket
        or a mid-raid upgrade does happen, and it moves every damage number that
        follows it. Named rather than assumed away.
        """
        by_player = collections.defaultdict(set)
        names = {}
        for _, d in parts:
            for p in d["roster"]:
                names[p["playerId"]] = p["name"]
                by_player[p["playerId"]].add((round(p["itemLevel"], 2), p["enchants"],
                                              p["gems"], p["intellect"]))
        return {
            "roster": parts[0][1]["roster"] if parts else [],
            "rosterFromLabel": F.fight_label(parts[0][0]) if parts else None,
            "changed": sorted(names[pid] for pid, v in by_player.items() if len(v) > 1),
        }

    def print(self):
        d = self.json()["overall"]
        print(F.hdr(["player", "ilvl", "ench", "gems", "Int", "secondaries", "sets"],
                    [22, 6, 5, 5, 6, 12, 18]))
        for p in d["roster"]:
            mark = "  <== " if p["isActor"] else ""
            sets = {int(k): v for k, v in p["sets"].items()}
            print(f"{p['name'][:22]:22}  "
                  f"{p['itemLevel']:<6.1f}  "
                  f"{p['enchants']:<5d}  "
                  f"{p['gems']:<5d}  "
                  f"{p['intellect']:<6d}  {p['secondaries']:<12d}  {str(sets)[:18]:18}{mark}")
        if d["changed"]:
            print(f"\n   NOTE: gear changed between pulls for {', '.join(d['changed'])} - "
                  f"the table above is {d['rosterFromLabel']}.")
        print("\nStandard for Arcane: 8 enchants (head/shoulders/chest/legs/feet/2 rings/weapon)\n"
              "and 7 gem sockets. A weapon rune is a temporaryEnchant and is counted separately.")


# ============================================================== cooldown usage

class CdUsageCheck(C.Check):
    """Raw cooldown efficiency: casts vs the theoretical maximum for the fight length."""

    id = "cd-usage"
    title = "Cooldown efficiency"
    group = "mage"

    def params(self):
        return {"cooldownSeconds": {"Touch of the Magi": CD_SECONDS[TOTM],
                                    "Arcane Surge": CD_SECONDS[SURGE]}}

    def fight_json(self, f):
        c = self.report.events(f, "Casts")
        d = F.fight_seconds(f)
        out = {"label": F.fight_label(f), "seconds": d, "abilities": {}}
        for gid, key in ((TOTM, "tom"), (SURGE, "surge")):
            n = len(T.casts(c, gid))
            poss = 1 + int(d // CD_SECONDS[gid])
            out["abilities"][key] = {"used": n, "possible": poss,
                                     "efficiencyPct": F.pct(n, poss)}
        return out

    def combine(self, parts):
        out = {}
        for key in ("tom", "surge"):
            used = sum(d["abilities"][key]["used"] for _, d in parts)
            poss = sum(d["abilities"][key]["possible"] for _, d in parts)
            out[key] = {"used": used, "possible": poss, "efficiencyPct": F.pct(used, poss)}
        return out

    def print(self):
        d = self.json()
        print(F.hdr(["fight", "dur", "ToM", "poss", "eff", "Surge", "poss", "eff"],
                    [26, 6, 4, 5, 6, 6, 5, 6]))
        for row in d["fights"]:
            r = row["data"]
            t, s = r["abilities"]["tom"], r["abilities"]["surge"]
            print(f"{r['label'][:26]:26}  {r['seconds']:<6.0f}  {t['used']:<4d}  "
                  f"{t['possible']:<5d}  {t['efficiencyPct']:<6.0f}  {s['used']:<6d}  "
                  f"{s['possible']:<5d}  {s['efficiencyPct']:<6.0f}")
        o = d["overall"]
        print(f"\nTOTAL  ToM {o['tom']['used']}/{o['tom']['possible']} = "
              f"{o['tom']['efficiencyPct']:.0f}%   "
              f"Surge {o['surge']['used']}/{o['surge']['possible']} = "
              f"{o['surge']['efficiencyPct']:.0f}%")
        print("Cooldowns: Touch of the Magi 45s, Arcane Surge 90s (measured min interval).")


# ================================================== APL-aligned per-cast grading
#
# The three checks below grade every *instance* of an ability rather than
# reporting an average, and they grade it against the SimulationCraft APL
# (ActionPriorityLists/default/mage_arcane.simc, simc aa9de89aac / Sep 5 2026),
# not against WoWAnalyzer's thresholds. Where the two disagree the APL wins, per
# the project rule that the raw priority line is ground truth. The divergences
# found when this was written are recorded in
# .claude/knowledge/classes/mage/arcane-mage-12.1-ptr.md - read them before retuning anything
# here, because several of WoWAnalyzer's numbers are close but not equal.
#
# Sunfury Barrage gate (actions.sunfury+=/arcane_barrage):
#   (charge=4 & ( (((orb|pulse chargesf>0.95) & AoE) | clearcasting) & salvo>=12
#                 | ((surge.remains>gcd|surge.down) & salvo=25) ))
#   | arcane_soul.up
#   | (salvo>8 & cooldown.touch_of_the_magi.ready)
# Sunfury Prismatic Bolt gate:
#   ((!4pc) | cumulative_power=8) & arcane_soul.down
# Sunfury Orb gate:
#   arcane_charge.stack<3        (NOT <4, and NOT "press it on cooldown")

CHARGE_TYPE = 16            # classResources / resourceChange type for Arcane Charges
MAX_CHARGES = 4
SPELLFIRE_SPHERE = 448604   # presence proves talent.spellfire_spheres
AOE_COUNT_WITH_SPHERES = 5  # variable.aoe_count = 2 + 3*talent.spellfire_spheres
AOE_COUNT_BASE = 2
SALVO_CAP_SUNFURY = 25
PBOLT_STALE_MS = 20000


def _hero_tree(code, fid, aid):
    """('sunfury'|None, evidence string).

    The loadout string is opaque in a WCL report, so the tree is inferred from
    empirical buff evidence rather than asserted - Arcane Soul only exists on
    Sunfury. Anything unproven is reported as unverified rather than guessed.
    """
    ids = {e.get("abilityGameID") for e in W.events(code, fid, "Buffs", aid)}
    if ARCANE_SOUL in ids:
        return "sunfury", "confirmed via Arcane Soul buff (451038)"
    return None, ("unverified - no Arcane Soul buff seen; Spellslinger is likely "
                  "but nothing in this log proves it")


def _aoe_count(code, fid, aid):
    """variable.aoe_count from the APL - the target count that opens the AoE gates."""
    if any(e.get("abilityGameID") == SPELLFIRE_SPHERE
           for e in W.events(code, fid, "Buffs", aid)):
        return AOE_COUNT_WITH_SPHERES, "Spellfire Spheres confirmed (buff 448604)"
    return AOE_COUNT_BASE, "no Spellfire Sphere buff seen - aoe_count falls back to 2"


def _charge_timeline(code, fid, aid):
    """(levels, spends, gained, wasted) for Arcane Charges.

    `levels` is [(ts, level_after)] and `spends` is [(ts, level_before_spend)].

    Arcane Charges have NO buff events on this build - looking for aura 36032
    returns nothing at all, silently - so the pool has to be rebuilt from the
    `Resources` energize stream. Two ordering rules matter and both change the
    answer: a spender is evaluated on the charges it had BEFORE any energize
    sharing its timestamp (simc has a normalizer for exactly this), and Barrage
    zeroes the pool except under Arcane Soul, which refunds it to full.
    """
    res = T.gains(W.events(code, fid, "Resources", aid), CHARGE_TYPE)
    soul = T.windows(W.events(code, fid, "Buffs", aid), ARCANE_SOUL, default_ms=6000)
    barrages = T.casts(W.events(code, fid, "Casts", aid), BARRAGE)
    stream = ([(e["timestamp"], 0, None) for e in barrages]
              + [(t, 1, (amt, waste)) for t, amt, waste, _ in res])
    stream.sort(key=lambda x: (x[0], x[1]))
    level, gained, wasted = 0, 0, 0
    levels, spends = [], []
    for ts, kind, payload in stream:
        if kind:
            # `resourceChange` INCLUDES the overcapped part and `waste` is that
            # part, so the effective gain is the difference - adding both to the
            # tally double-counts and can report more waste than generation.
            amt, waste = payload
            gained += amt
            wasted += waste
            level = min(MAX_CHARGES, level + amt - waste)
        else:
            spends.append((ts, level))
            level = MAX_CHARGES if T.in_windows(soul, ts) else 0
        levels.append((ts, level))
    return levels, spends, gained, wasted


def _level_at(levels, ts):
    """Charges in the pool immediately BEFORE ts."""
    cur = 0
    for t, lv in levels:
        if t >= ts:
            break
        cur = lv
    return cur


class ChargesCheck(C.Check):
    """Arcane Charge economy: overcapped generation, and charges held at each spend.

    The APL never spends Barrage below 4 charges outside its Arcane Soul and
    Touch-of-the-Magi branches, and in a 300s reference sim every one of 73
    Barrages went out at 4/4. A Barrage under 4 is therefore not a judgement
    call, it is lost damage on the charge multiplier itself. Overcap is the
    other half of the same ledger: a charge generated with the pool already full
    is generation you paid a GCD for and threw away.
    """

    id = "charges"
    title = "Arcane Charge economy"
    group = "mage"
    ORB_APL = "actions.sunfury+=/arcane_orb,if=buff.arcane_charge.stack<3"
    ORB_GATE = 3

    def params(self):
        return {"maxCharges": MAX_CHARGES, "orbGate": self.ORB_GATE, "orbApl": self.ORB_APL}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        levels, spends, gained, wasted = _charge_timeline(code, f["id"], aid)
        full = sum(1 for _, c in spends if c >= MAX_CHARGES)
        under = []
        for ts, c in spends:
            if c >= MAX_CHARGES:
                continue
            inst = F.instance(F.mmss(ts, f["startTime"]),
                              F.FAIL if c <= 2 else F.OK,
                              f"Arcane Barrage at {c}/4 charges", charges=c)
            inst.update(timestamp=ts, fightId=f["id"])
            under.append(inst)

        # Arcane Orb is a charge generator of last resort for Sunfury, NOT a
        # cooldown to press on sight: the APL gates it behind
        # `arcane_charge.stack<3` and the reference sim casts it twice in 300s. A
        # cast-efficiency reading of Orb (as WoWAnalyzer reports it) therefore
        # looks damning while being irrelevant.
        dmg = self.report.events(f, "DamageDone", ability_id=ORB_BOLT)
        orbs = []
        for o in T.casts(self.report.events(f, "Casts"), ORB):
            ts = o["timestamp"]
            before = _level_at(levels, ts)
            hit = T.targets_hit(dmg, ts, ts + 3000)
            if hit == 0:
                v, why = F.FAIL, "Orb hit nothing"
            elif before >= self.ORB_GATE:
                v, why = F.FAIL, f"Orb at {before} charges (APL gate is <3), hit {hit}"
            else:
                v, why = F.GOOD, f"Orb at {before} charges, hit {hit}"
            inst = F.instance(F.mmss(ts, f["startTime"]), v, why,
                              charges=before, targetsHit=hit)
            inst.update(timestamp=ts, fightId=f["id"])
            orbs.append(inst)

        tree, ev = _hero_tree(code, f["id"], aid)
        return {
            "label": F.fight_label(f),
            "heroTree": {"value": tree, "evidence": ev},
            "barrages": len(spends), "atMax": full, "underMax": len(spends) - full,
            "generated": gained, "overcapped": wasted,
            "overcappedPct": F.pct(wasted, gained),
            "underMaxInstances": under,
            "orbs": orbs,
            "orbTally": F.tally(orbs),
        }

    def combine(self, parts):
        under = [i for _, d in parts for i in d["underMaxInstances"]]
        orbs = [i for _, d in parts for i in d["orbs"]]
        gained = sum(d["generated"] for _, d in parts)
        wasted = sum(d["overcapped"] for _, d in parts)
        spends = sum(d["barrages"] for _, d in parts)
        full = sum(d["atMax"] for _, d in parts)
        return {
            "heroTree": C.consensus(parts, "heroTree"),
            "barrages": spends, "atMax": full, "underMax": spends - full,
            "atMaxPct": F.pct(full, spends),
            "generated": gained, "overcapped": wasted,
            "overcappedPct": F.pct(wasted, gained),
            "underMaxInstances": under, "underMaxTally": F.tally(under),
            "orbs": orbs, "orbTally": F.tally(orbs),
        }

    def print(self):
        d = self.json()
        o = d["overall"]
        print(F.hdr(["fight", "barrages", "at 4/4", "under 4", "gen", "overcapped"],
                    [26, 9, 7, 8, 6, 11]))
        for row in d["fights"]:
            r = row["data"]
            if not r["barrages"]:
                continue
            print(f"{r['label'][:26]:26}  {r['barrages']:<9d}  {r['atMax']:<7d}  "
                  f"{r['underMax']:<8d}  {r['generated']:<6d}  "
                  f"{r['overcapped']} ({r['overcappedPct']:.0f}%)")
        print()
        F.ledger("Barrage below 4 charges", o["underMaxInstances"])
        tree = o["heroTree"]
        if tree["varies"]:
            spread = ", ".join(f"{v} in {n}" for v, n in tree["byValue"].items())
            print(f"\nhero tree: VARIES across fights - {spread}")
        else:
            print(f"\nhero tree: {tree['value'] or 'unknown'} ({tree['evidence']})")
        F.ledger("Arcane Orb", o["orbs"])
        print(f"   APL: {d['params']['orbApl']}\n"
              "   Orb is a generator of last resort here - a low cast count is not a fault.")


class BoltCheck(C.Check):
    """Prismatic Bolt proc discipline, graded per PROC rather than per cast.

    The apex talent's buff does not stack, so a proc that arrives while one is
    already up is munched and a proc that falls off unused is gone - both are
    invisible in a cast count, which is why this walks the buff timeline instead.
    Two APL conditions do the work:

        ((!set_bonus.midnight_season_2_4pc)|buff.cumulative_power.stack=8)
        &buff.arcane_soul.down

    The `arcane_soul.down` half is the one worth knowing about: during Arcane
    Soul the priority is Barrage, so spending the Bolt proc there is a downgrade
    and munching it there is correct play. WoWAnalyzer grades a Bolt at 8
    Cumulative Power as Perfect regardless of Arcane Soul - a real divergence,
    and the reference sim never once casts Bolt with Arcane Soul up (0 of 31).
    """
    id = "bolt"
    title = "Prismatic Bolt"
    group = "mage"
    LIMIT = 15
    APL = ("((!set_bonus.midnight_season_2_4pc)|buff.cumulative_power.stack=8)"
           "&buff.arcane_soul.down")

    def params(self):
        return {"apl": self.APL, "staleMs": PBOLT_STALE_MS, "cumulativePowerCap": 8}

    def fight_json(self, f):
        buffs = self.report.events(f, "Buffs")
        casts = T.casts(self.report.events(f, "Casts"), PRISMATIC_BOLT)
        cast_ts = [c["timestamp"] for c in casts]
        cp_tl = T.stack_timeline(buffs, CUMULATIVE_POWER)
        salvo_tl = T.stack_timeline(buffs, SALVO)
        soul = T.windows(buffs, ARCANE_SOUL, default_ms=6000)
        dmg = self.report.events(f, "DamageDone", ability_id=PRISMATIC_BOLT)
        # Per fight, not once for the whole selection: the 4-piece is a property
        # of what was worn, and gear can change between pulls.
        has_4pc = bool(cp_tl)
        proc = [e for e in sorted(buffs, key=lambda x: x["timestamp"])
                if e.get("abilityGameID") == PBOLT_BUFF]
        starts = [e["timestamp"] for e in proc
                  if e["type"] in ("applybuff", "refreshbuff")]
        rows = []

        def add(ts, verdict, why, **facts):
            inst = F.instance(F.mmss(ts, f["startTime"]), verdict, why, **facts)
            inst.update(timestamp=ts, fightId=f["id"])
            rows.append(inst)

        open_ts = None
        for e in proc:
            ts, kind = e["timestamp"], e["type"]
            if kind in ("applybuff", "refreshbuff"):
                if open_ts is not None and not _any_between(cast_ts, open_ts, ts):
                    if T.in_windows(soul, ts):
                        add(open_ts, F.GOOD, "proc munched during Arcane Soul "
                                             "(intended - Barrage is the priority there)")
                    else:
                        add(open_ts, F.FAIL, "proc munched (overwritten) unused")
                open_ts = ts
            elif kind == "removebuff" and open_ts is not None:
                if not _any_between(cast_ts, open_ts, ts):
                    add(open_ts, F.FAIL, "proc expired unused")
                open_ts = None
        for c in casts:
            ts = c["timestamp"]
            cp = T.stacks_at(cp_tl, ts)
            sv = T.stacks_at(salvo_tl, ts)
            hit = T.targets_hit(dmg, ts, ts + 2000)
            prior = [t for t in starts if t <= ts]
            delay = (ts - prior[-1]) / 1000.0 if prior else None
            d = (f"cp={cp} salvo={sv} hit={hit}"
                 + (f" delay={delay:.1f}s" if delay is not None else ""))
            facts = {"cumulativePower": cp, "salvo": sv, "targetsHit": hit,
                     "delaySeconds": delay}
            if T.in_windows(soul, ts):
                add(ts, F.FAIL,
                    "cast during Arcane Soul (APL gates on arcane_soul.down) - " + d, **facts)
            elif delay is not None and delay * 1000 > PBOLT_STALE_MS:
                add(ts, F.FAIL, f"sat on the proc {delay:.0f}s - " + d, **facts)
            elif has_4pc and cp < 8:
                add(ts, F.OK, f"cast at {cp}/8 Cumulative Power - " + d, **facts)
            else:
                add(ts, F.PERFECT, d, **facts)
        return {
            "fourPiece": {"value": has_4pc, "evidence":
                          "Cumulative Power stacks seen" if has_4pc
                          else "no Cumulative Power buff in this pull"},
            "instances": rows,
            "tally": F.tally(rows),
        }

    def combine(self, parts):
        rows = [i for _, d in parts for i in d["instances"]]
        return {"fourPiece": C.consensus(parts, "fourPiece"),
                "instances": rows, "tally": F.tally(rows)}

    def print(self):
        d = self.json()
        o = d["overall"]
        fp = o["fourPiece"]
        if fp["varies"]:
            spread = ", ".join(f"{v} in {n}" for v, n in fp["byValue"].items())
            print(f"Season 2 4pc (Cumulative Power): VARIES across fights - {spread}")
        else:
            print("Season 2 4pc (Cumulative Power): "
                  + ("yes" if fp["value"] else "no - the 8-stack gate does not apply"))
        F.ledger("Prismatic Bolt (per proc)", o["instances"], limit=self.LIMIT)
        print("   APL: " + d["params"]["apl"])


def _any_between(ts_list, a, b):
    return any(a <= t <= b for t in ts_list)


def _gate_counts(instances):
    """{APL branch -> casts that satisfied it}, most common first.

    Grouped on `gate` (the branch alone) rather than the printed `why`, which
    has the per-cast facts glued onto it and therefore never groups.
    """
    c = collections.Counter(i["gate"] for i in instances)
    return [{"gate": g, "casts": n} for g, n in c.most_common()]


class BarrageCheck(C.Check):
    """Every Arcane Barrage graded against the Sunfury APL's spend gates.

    This is the check that most deliberately disagrees with WoWAnalyzer. Its
    Sunfury evaluator has no branch for `salvo>8 & cooldown.touch_of_the_magi.ready`
    even though its own on-page explanation lists that condition - so a Barrage
    fired to set up Touch of the Magi gets graded "Ok, had N Arcane Salvo stacks"
    when the APL considers it correct. Barrages are scored here on the gate they
    actually satisfied; one that satisfied none is the only real fault.
    """

    id = "barrage"
    title = "Arcane Barrage"
    group = "mage"
    LIMIT = 15
    APL = ("(charge=4 & (((orb|pulse ready & AoE)|clearcasting) & salvo>=12\n"
           " | ((surge.remains>gcd|surge.down) & salvo=25))) | arcane_soul.up\n"
           " | (salvo>8 & cooldown.touch_of_the_magi.ready)")

    def params(self):
        return {"maxCharges": MAX_CHARGES, "apl": self.APL}

    def fight_json(self, f):
        r = self.report
        code, aid = r.code, r.actor_id
        # Resolved PER FIGHT. The previous version read these once from
        # `fights[0]` and graded every fight against them. On the reference
        # report `-f all`, 13 of 54 fights carry no Spellfire Sphere evidence
        # (aoe_count 2, not the 5 fights[0] reports) and 24 carry no Arcane Soul
        # evidence. Those 13 hold one Barrage between them, so no verdict on
        # THIS report actually moved - the fault was a latent wrong input, not a
        # visible wrong answer, and a selection weighted differently would show
        # it. Note that absent evidence is not proof of a talent change: a short
        # trash pull simply may not contain the buff, which is exactly why the
        # per-fight value belongs in the payload where it can be seen.
        aoe, aoe_ev = _aoe_count(code, f["id"], aid)
        tree, tree_ev = _hero_tree(code, f["id"], aid)
        buffs = r.events(f, "Buffs")
        cs = r.events(f, "Casts", resources=True)
        salvo_tl = T.stack_timeline(buffs, SALVO)
        cc_tl = T.stack_timeline(buffs, CLEARCASTING)
        soul = T.windows(buffs, ARCANE_SOUL, default_ms=6000)
        surge = T.windows(buffs, SURGE_BUFF, default_ms=15000)
        levels, _, _, _ = _charge_timeline(code, f["id"], aid)
        dmg = r.events(f, "DamageDone", ability_id=BARRAGE)
        tom_casts = [c["timestamp"] for c in T.casts(cs, TOTM)]
        instances = []
        for c in T.casts(cs, BARRAGE):
            ts = c["timestamp"]
            sv = T.stacks_at(salvo_tl, ts)
            cc = T.stacks_at(cc_tl, ts)
            ch = _level_at(levels, ts)
            hit = T.targets_hit(dmg, ts, ts + 1500)
            mana, mmax = T.resource_at(c, 0)
            mana_pct = 100.0 * mana / mmax if mana is not None and mmax else None
            d = (f"salvo={sv} charges={ch}/4 cc={cc} hit={hit}"
                 + (f" mana={mana_pct:.0f}%" if mana_pct is not None else ""))
            if T.in_windows(soul, ts):
                v, gate = F.PERFECT, "Arcane Soul window"
            elif mana_pct is not None and mana_pct <= 10:
                v, gate = F.GOOD, "out of mana, Barrage is the free spender"
            elif sv > 8 and _tom_ready(tom_casts, ts):
                v, gate = F.PERFECT, "Touch of the Magi ready (APL salvo>8 branch)"
            elif ch >= MAX_CHARGES and cc and sv >= 12:
                v, gate = F.PERFECT, "Clearcasting + salvo>=12 at 4 charges"
            elif ch >= MAX_CHARGES and sv >= SALVO_CAP_SUNFURY and not _ending(surge, ts):
                v, gate = F.PERFECT, "salvo capped at 25 at 4 charges"
            elif ch >= MAX_CHARGES and hit >= aoe and sv >= 12:
                v, gate = F.PERFECT, f"AoE branch, hit {hit} >= aoe_count {aoe}"
            elif ch < MAX_CHARGES:
                v, gate = F.FAIL, "spent below 4 charges with no gate met"
            else:
                v, gate = F.OK, "no APL gate met"
            # `facts` are the numbers that VARY per cast - MAX_CHARGES is a
            # constant and lives in params(), not repeated 869 times.
            inst = F.instance(F.mmss(ts, f["startTime"]), v, gate + " - " + d,
                              salvo=sv, charges=ch, clearcasting=cc,
                              targetsHit=hit, manaPct=mana_pct)
            # `why` is the printed string; `gate` is the branch alone, which is
            # what a component groups on - the facts are already structured.
            inst.update(gate=gate, timestamp=ts, fightId=f["id"])
            instances.append(inst)
        return {
            "heroTree": {"value": tree, "evidence": tree_ev},
            "aoeCount": {"value": aoe, "evidence": aoe_ev},
            "instances": instances,
            "tally": F.tally(instances),
            "gates": _gate_counts(instances),
        }

    def combine(self, parts):
        instances = [i for _, d in parts for i in d["instances"]]
        return {
            # `consensus` reports disagreement instead of hiding it behind the
            # first fight's answer.
            "heroTree": C.consensus(parts, "heroTree"),
            "aoeCount": C.consensus(parts, "aoeCount"),
            "instances": instances,
            "tally": F.tally(instances),
            "gates": _gate_counts(instances),
        }

    @staticmethod
    def _context_line(label, entry):
        if entry.get("varies"):
            spread = ", ".join(f"{v} in {n}" for v, n in entry["byValue"].items())
            return f"{label} : VARIES across fights - {spread}"
        return f"{label} : {entry['value'] if entry['value'] is not None else 'unknown'} " \
               f"({entry['evidence']})"

    def print(self):
        d = self.json()
        o = d["overall"]
        print(self._context_line("hero tree", o["heroTree"]))
        print(self._context_line("aoe_count", o["aoeCount"]) + "\n")
        F.ledger(self.title, o["instances"], limit=self.LIMIT)
        print("   APL: " + d["params"]["apl"].replace("\n", "\n       "))


def _tom_ready(tom_casts, ts):
    """Was Touch of the Magi off cooldown at ts?

    Derived from the player's own casts, so it is a lower bound: a ToM held past
    its cooldown still reads as ready from the moment the cooldown elapsed, which
    is the reading the APL condition wants anyway.
    """
    prev = [t for t in tom_casts if t <= ts]
    if not prev:
        return True
    return (ts - prev[-1]) / 1000.0 >= CD_SECONDS[TOTM]


def _ending(surge_windows, ts, gcd_ms=1500):
    """True if Arcane Surge is up but has less than a GCD left - the APL refuses
    to dump a capped Salvo Barrage into the tail of the Surge window."""
    return any(s <= ts <= e and e - ts < gcd_ms for s, e in surge_windows)


CHECKS = C.registry(
    SalvoCheck, SoulCheck, ClearcastingCheck, TomTargetCheck, CooldownsCheck,
    CdUsageCheck, WavesCheck, GapsCheck, GearCheck, ChargesCheck, BoltCheck,
    BarrageCheck,
)
