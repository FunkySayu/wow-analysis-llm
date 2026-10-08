"""Checks that apply to any class/spec - no spell IDs, just cast timing.

Add a new check by subclassing `check.Check` (see tools/warcraftlogs/lib/check.py) and
registering it in CHECKS below. `json()` does the log reading and returns the
findings as data; `print()` renders that data as the terminal text and reads
nothing else.
"""

import collections

from lib import check as C
from lib import format as F
from lib import timeline as T
from lib import wclapi as W


# ============================================================== ABC (uptime)

class AbcCheck(C.Check):
    """Always Be Casting: share of the fight with no GCD-consuming cast in flight.

    Spec-agnostic proxy for GCD uptime - it looks at gaps between consecutive
    `cast` events for the actor, not any specific ability. A gap longer than
    `gcd` (default 1.5s, the unhasted GCD) counts as downtime. This overcounts
    uptime around casts that don't share the GCD (trinkets, off-GCD utility)
    since they still close a gap - read it as an upper bound on true GCD
    uptime, not an exact figure.
    """

    id = "abc"
    title = "GCD uptime"
    group = "common"
    GCD = 1.5

    def params(self):
        return {"gcd": self.GCD}

    def fight_json(self, fight):
        cs = T.casts(self.report.events(fight, "Casts"))
        # A fight the player never cast in carries no derived fields at all, so
        # "silent here" can never be misread downstream as "100% downtime".
        if not cs:
            return {"label": F.fight_label(fight), "casts": 0}
        gaps = []
        prev = fight["startTime"]
        for e in cs:
            gaps.append(e["timestamp"] - prev)
            prev = e["timestamp"]
        gaps.append(fight["endTime"] - prev)
        down = sum(g / 1000.0 - self.GCD for g in gaps if g / 1000.0 > self.GCD)
        d = F.fight_seconds(fight)
        return {
            "label": F.fight_label(fight),
            "casts": len(cs),
            "downtimeSeconds": down,
            "uptimePct": F.pct(d - down, d),
            "longestGapSeconds": max(gaps) / 1000.0,
        }

    def combine(self, parts):
        # Fights with no casts are counted in `fights` but contribute no seconds -
        # they are part of the selection, not part of the measurement.
        live = [(f, d) for f, d in parts if d["casts"]]
        dur = sum(F.fight_seconds(f) for f, _ in live)
        down = sum(d["downtimeSeconds"] for _, d in live)
        return {"fights": len(parts), "measuredFights": len(live), "seconds": dur,
                "downtimeSeconds": down, "uptimePct": F.pct(dur - down, dur)}

    def print(self):
        d = self.json()
        print(F.hdr(["fight", "dur", "casts", "downtime", "uptime%", "longest gap"],
                    [26, 6, 6, 9, 8, 12]))
        for row in d["fights"]:
            f, r = row["fight"], row["data"]
            if not r["casts"]:
                print(f"{r['label'][:26]:26}  {f['seconds']:<6.0f}  no casts recorded")
                continue
            print(f"{r['label'][:26]:26}  {f['seconds']:<6.0f}  {r['casts']:<6d}  "
                  f"{r['downtimeSeconds']:<9.1f}  {r['uptimePct']:<8.1f}  "
                  f"{r['longestGapSeconds']:<12.2f}")
        t = d["overall"]
        if t["seconds"]:
            print(f"\n{t['fights']} fights, {t['seconds']:.0f}s total: "
                  f"{t['uptimePct']:.1f}% GCD uptime "
                  f"(gaps over {d['params']['gcd']:.1f}s counted as downtime)")


# ============================================================== cancelled casts

class CancelsCheck(C.Check):
    """Cancelled/interrupted hard-casts: a `begincast` with no matching `cast`.

    WCL emits `begincast` when a non-instant cast starts and `cast` when it
    resolves; a `begincast` with no `cast` for the same ability shortly after
    means the cast was cut short - self-cancelled, interrupted, or the player
    moved/died mid-cast. This check flags the total but doesn't distinguish
    the cause; cross-check `Interrupts` in the raw log if that matters.
    """

    id = "cancels"
    title = "Cancelled casts"
    group = "common"

    def fight_json(self, fight):
        started = 0
        cancelled = collections.Counter()
        pending = {}
        for e in sorted(self.report.events(fight, "Casts"), key=lambda x: x["timestamp"]):
            gid = e.get("abilityGameID")
            if e["type"] == "begincast":
                pending[gid] = e["timestamp"]
                started += 1
            elif e["type"] == "cast" and gid in pending:
                del pending[gid]
        for gid in pending:
            cancelled[gid] += 1
        names = self._names() if cancelled else {}
        return {
            "started": started,
            "cancelled": sum(cancelled.values()),
            "byAbility": [{"spellId": gid, "name": names.get(gid) or str(gid), "count": n}
                          for gid, n in cancelled.most_common()],
        }

    def _names(self):
        if not hasattr(self, "_name_cache"):
            self._name_cache = self.report.ability_names()
        return self._name_cache

    def combine(self, parts):
        started = sum(d["started"] for _, d in parts)
        cancelled = sum(d["cancelled"] for _, d in parts)
        per = collections.Counter()
        names = {}
        for _, d in parts:
            for a in d["byAbility"]:
                per[a["spellId"]] += a["count"]
                names[a["spellId"]] = a["name"]
        return {
            "started": started,
            "cancelled": cancelled,
            "cancelledPct": F.pct(cancelled, started),
            "byAbility": [{"spellId": gid, "name": names[gid], "count": n}
                          for gid, n in per.most_common(10)],
        }

    def print(self):
        d = self.json()["overall"]
        if not d["started"]:
            print("no hard-casts (begincast events) found - this actor may be entirely instant-cast")
            return
        print(f"hard-casts started                              : {d['started']}")
        print(f"cancelled/interrupted (no matching completion)  : {d['cancelled']} "
              f"({d['cancelledPct']:.1f}%)")
        if d["byAbility"]:
            print("\nby ability (spell ID -> count):")
            for a in d["byAbility"]:
                print(f"   {a['spellId']:>10}  {a['count']}")


# ============================================================== mana economy

MANA = 0                 # classResources type for mana
MANA_BANDS = ((80, 100), (60, 80), (40, 60), (20, 40), (0, 20))


class ManaCheck(C.Check):
    """Where the fight was spent on the mana curve, and what was cast while dry.

    Spec-agnostic: reads classResources type 0, so it works for any mana user.
    The reason this is worth its own check rather than a footnote on a rotation
    check is that running dry changes *which rotation you are even in* - most
    APLs have a distinct low-mana branch (a regen cooldown, or falling through
    to a free spender) that a rotation check reading only buff stacks will score
    as a mistake. Read this first when a spender check looks inexplicably bad.

    Time is attributed from each cast to the next, so a long gap holds whatever
    mana the cast before it read - which is the right assumption for downtime
    but will slightly over-weight a band the player idled in.
    """

    id = "mana"
    title = "Mana curve"
    group = "common"
    DRY = 20.0

    def params(self):
        return {"dryThresholdPct": self.DRY, "bands": [f"{lo}-{hi}%" for lo, hi in MANA_BANDS]}

    def _names(self):
        """Ability names, fetched once per check rather than once per fight."""
        if not hasattr(self, "_name_cache"):
            self._name_cache = self.report.ability_names()
        return self._name_cache

    def fight_json(self, fight):
        band_time = {b: 0.0 for b in MANA_BANDS}
        low_casts = collections.Counter()
        total = 0.0
        lowest = None
        cs = T.casts(self.report.events(fight, "Casts", resources=True))
        pts = [(e["timestamp"], T.resource_at(e, MANA)) for e in cs]
        pts = [(t, a, m) for t, (a, m) in pts if a is not None and m]
        for i, (t, a, m) in enumerate(pts):
            nxt = pts[i + 1][0] if i + 1 < len(pts) else fight["endTime"]
            dur = max(0.0, (nxt - t) / 1000.0)
            share = 100.0 * a / m
            if lowest is None or share < lowest[0]:
                lowest = (share, t)
            for lo, hi in MANA_BANDS:
                if lo <= share <= hi:
                    band_time[(lo, hi)] += dur
                    break
            total += dur
            if share < self.DRY:
                low_casts[cs[i].get("abilityGameID")] += 1
        # Names are resolved here, not in print(): print() may not touch the log.
        names = self._names() if low_casts else {}
        dry = sum(band_time[b] for b in MANA_BANDS if b[0] < self.DRY)
        return {
            "totalSeconds": total,
            "bands": [{"label": f"{lo}-{hi}%", "lo": lo, "hi": hi,
                       "seconds": band_time[(lo, hi)],
                       "sharePct": F.pct(band_time[(lo, hi)], total)}
                      for lo, hi in MANA_BANDS],
            "lowest": None if not lowest else {
                "pct": lowest[0],
                "at": F.mmss(lowest[1], fight["startTime"]),
                "timestamp": lowest[1],
                "fight": F.fight_label(fight),
                "fightId": fight["id"],
            },
            "drySeconds": dry,
            "dryPct": F.pct(dry, total),
            "castsWhileDry": [{"spellId": gid, "name": names.get(gid) or str(gid),
                               "count": n} for gid, n in low_casts.most_common(8)],
        }

    def combine(self, parts):
        """Band seconds add; the lowest reading is a minimum, not a mean.

        A curve blended across a raid night is not any pull's curve - it is only
        useful as "how much of the night was spent dry". The per-fight entries
        are where the actual reading happens; this is the index into them.
        """
        band_time = collections.OrderedDict((f"{lo}-{hi}%", 0.0) for lo, hi in MANA_BANDS)
        low_casts = collections.Counter()
        total = 0.0
        lowest = None
        for _, d in parts:
            total += d["totalSeconds"]
            for b in d["bands"]:
                band_time[b["label"]] += b["seconds"]
            for c in d["castsWhileDry"]:
                low_casts[(c["spellId"], c["name"])] += c["count"]
            lo = d["lowest"]
            if lo and (lowest is None or lo["pct"] < lowest["pct"]):
                lowest = lo
        dry = sum(v for (lo, _hi), v in zip(MANA_BANDS, band_time.values()) if lo < self.DRY)
        return {
            "totalSeconds": total,
            "bands": [{"label": f"{lo}-{hi}%", "lo": lo, "hi": hi,
                       "seconds": band_time[f"{lo}-{hi}%"],
                       "sharePct": F.pct(band_time[f"{lo}-{hi}%"], total)}
                      for lo, hi in MANA_BANDS],
            "lowest": lowest,
            "drySeconds": dry,
            "dryPct": F.pct(dry, total),
            "castsWhileDry": [{"spellId": gid, "name": name, "count": n}
                              for (gid, name), n in low_casts.most_common(8)],
        }

    def print(self):
        d = self.json()["overall"]
        d = dict(d, dryThresholdPct=self.json()["params"]["dryThresholdPct"])
        if not d["totalSeconds"]:
            print("no mana readings - this actor may not use mana, or events were "
                  "fetched without resources=True")
            return
        print("time on the mana curve (attributed cast-to-cast):")
        F.bands([(b["label"], b["seconds"]) for b in d["bands"]], d["totalSeconds"])
        if d["lowest"]:
            print(f"\nlowest reading: {d['lowest']['pct']:.1f}% at "
                  f"{d['lowest']['at']} into {d['lowest']['fight']}")
        print(f"time under {d['dryThresholdPct']:.0f}% mana: {d['drySeconds']:.0f}s "
              f"of {d['totalSeconds']:.0f}s ({d['dryPct']:.1f}%)")
        if d["castsWhileDry"]:
            print(f"cast while under {d['dryThresholdPct']:.0f}% mana "
                  f"(spell ID -> count):")
            for c in d["castsWhileDry"]:
                print(f"   {c['spellId']:>10}  {c['count']}")
        else:
            print(f"nothing was cast under {d['dryThresholdPct']:.0f}% mana")


# ============================================================== consumables

# Matched on aura/cast NAME rather than ID: consumable IDs rotate every patch and
# a stale ID list fails silently (reports "no flask" for a player who had one),
# which is exactly the failure mode this check exists to rule out.
FOOD_NAMES = ("well fed", "food")
FLASK_NAMES = ("flask", "phial")
# "Ethereal Augmentation" is the Midnight augment rune; the old needles missed it and
# reported every player in a 20-man raid as rune-less (nLvb3TFZGgXWaNry, 2026-09-17).
RUNE_NAMES = ("augment rune", "augmented", "augmentation")
VANTUS_NAMES = ("vantus rune",)
HEALTH_POTION_NAMES = ("health potion", "healthstone", "healing potion")

# A flask's NAME does not say which stat it gives, and players get it wrong: a player
# who believed they ran the Mastery flask was on Flask of the Blood Knights, which is
# Haste. IDs -> stat confirmed against the live Wowhead tooltips on 2026-09-17.
FLASK_STATS = {
    1235108: "Mastery",   # Flask of the Magisters
    1235110: "Haste",     # Flask of the Blood Knights
    1235111: "Crit",      # Flask of the Shattered Sun
    1235057: "Vers",      # Flask of Thalassian Resistance
}

# Combat (stat) potions are the exception to name matching: in Midnight they are
# not called "... Potion" at all - the current one is "Light's Potential" - so a
# pure name match reports zero potions used for a player who used two, silently.
# IDs here are confirmed against the Wowhead tooltip (5 min cooldown, primary
# stat for 30s), not guessed. Add to this set when the expansion's potion changes.
COMBAT_POTION_IDS = {
    1236616,      # Light's Potential
    1236994,      # Potion of Recklessness (+highest secondary, -lowest, 30s)
}


def _has(auras, needles):
    for a in auras:
        n = (a.get("name") or "").lower()
        if any(w in n for w in needles):
            return a.get("name")
    return None


class ConsumablesCheck(C.Check):
    """Food, flask, augment rune, weapon rune and combat potions.

    The cheapest damage in the game and the easiest thing to forget, so it is
    worth checking before reading any rotation output - a missing food buff is
    a flat throughput loss that will otherwise get misattributed to the player's
    play. Every player in the report is listed as the control test: if nobody
    has a food buff, the log is not recording them rather than the raid skipping
    dinner.
    """

    id = "consumables"
    title = "Consumables and gear buffs"
    group = "common"

    def _abilities(self):
        if not hasattr(self, "_abil_cache"):
            self._abil_cache = self.report.ability_names()
        return self._abil_cache

    def _players(self):
        if not hasattr(self, "_player_cache"):
            self._player_cache = self.report.actor_names()
        return self._player_cache

    def fight_json(self, fight):
        # CombatantInfo is emitted per fight and is report-wide, not per actor,
        # so it is fetched with source_id=None.
        info = self.report.events(fight, "CombatantInfo", source_id=None)
        names = self._players()
        roster = []
        for e in sorted(info, key=lambda x: -(x.get("intellect") or 0)):
            auras = [a for a in (e.get("auras") or [])
                     if a.get("source") == e.get("sourceID")]
            if not auras and not e.get("gear"):
                continue
            pid = e.get("sourceID")
            roster.append({
                "playerId": pid,
                "name": names.get(pid, "?"),
                "isActor": pid == self.report.actor_id,
                "intellect": e.get("intellect"),
                "food": bool(_has(auras, FOOD_NAMES)),
                "flask": _has(auras, FLASK_NAMES),
                "flaskStat": next((FLASK_STATS[a.get("ability")] for a in auras
                                   if a.get("ability") in FLASK_STATS), None),
                "rune": bool(_has(auras, RUNE_NAMES)),
                "vantus": _has(auras, VANTUS_NAMES),
                "weaponEnchant": any(g.get("temporaryEnchant")
                                     for g in (e.get("gear") or [])),
            })
        abil = self._abilities()
        potions = collections.Counter()
        for c in T.casts(self.report.events(fight, "Casts")):
            gid = c.get("abilityGameID")
            n = abil.get(gid) or str(gid)
            is_combat = gid in COMBAT_POTION_IDS
            if is_combat or "potion" in n.lower() or "healthstone" in n.lower():
                potions[(gid, n, is_combat)] += 1
        return {
            "roster": roster,
            "potions": [{"spellId": gid, "name": n, "combat": combat, "count": k}
                        for (gid, n, combat), k in potions.most_common()],
        }

    #: Fields worth reporting drift on, and how to say each one in a sentence.
    DRIFT_FIELDS = (("food", "food"), ("flask", "flask"),
                    ("rune", "augment rune"), ("weaponEnchant", "weapon rune"))

    def combine(self, parts):
        """Roster from the first pull, plus what actually changed after it.

        A flask lasts the night, so the first pull is a fair reading of what the
        raid brought - but only if it did not change, and over a real raid night
        it does: food lapses, flasks get swapped, weapon runes run out. The
        pre-class version read pull one and presented it as the whole night. This
        reads every pull and reports the drift, summarised per field rather than
        as a list of names - 26 names is not a finding, "food differs for 23
        players" is. The per-pull rosters are in the payload for the detail.
        """
        roster = parts[0][1]["roster"] if parts else []
        by_player = collections.defaultdict(lambda: collections.defaultdict(set))
        names = {}
        for _, d in parts:
            for p in d["roster"]:
                names[p["playerId"]] = p["name"]
                for field, _label in self.DRIFT_FIELDS:
                    by_player[p["playerId"]][field].add(p[field])
        drift = {}
        for field, _label in self.DRIFT_FIELDS:
            drift[field] = sorted(names[pid] for pid, f in by_player.items()
                                  if len(f[field]) > 1)
        actor = self.report.actor_id if self.report else None
        actor_drift = [field for field, _l in self.DRIFT_FIELDS
                       if actor in by_player and len(by_player[actor][field]) > 1]
        potions = collections.Counter()
        for _, d in parts:
            for p in d["potions"]:
                potions[(p["spellId"], p["name"], p["combat"])] += p["count"]
        return {
            "roster": roster,
            "rosterFromFight": parts[0][0]["id"] if parts else None,
            "rosterFromLabel": F.fight_label(parts[0][0]) if parts else None,
            "pulls": len(parts),
            "drift": drift,
            "actorDrift": actor_drift,
            "potions": [{"spellId": gid, "name": n, "combat": combat, "count": k}
                        for (gid, n, combat), k in potions.most_common()],
            "combatPotions": sum(k for (_gid, _n, combat), k in potions.items() if combat),
        }

    def print(self):
        d = self.json()["overall"]
        print(F.hdr(["player", "food", "flask", "stat", "rune", "wpn", "vantus"],
                    [22, 6, 26, 7, 6, 5, 6]))
        for p in d["roster"]:
            mark = "  <== " if p["isActor"] else ""
            print(f"{p['name'][:22]:22}  "
                  f"{'yes' if p['food'] else 'NO':<6}  "
                  f"{(p['flask'] or 'NO')[:26]:26}  "
                  f"{(p.get('flaskStat') or '-'):<7}  "
                  f"{'yes' if p['rune'] else 'NO':<6}  "
                  f"{'yes' if p['weaponEnchant'] else 'NO':<5}  "
                  f"{'yes' if p.get('vantus') else '-':<6}{mark}")
        drifted = [(label, d["drift"][field]) for field, label in self.DRIFT_FIELDS
                   if d["drift"].get(field)]
        if drifted:
            spread = ", ".join(f"{label} for {len(who)}" for label, who in drifted)
            print(f"\n   NOTE: buffs are not identical across the {d['pulls']} pulls "
                  f"({spread}).\n"
                  f"   The table above is {d['rosterFromLabel']}; per-pull rosters are in "
                  f"the JSON payload.")
            if d["actorDrift"]:
                mine = ", ".join(label for field, label in self.DRIFT_FIELDS
                                 if field in d["actorDrift"])
                print(f"   THIS ACTOR: {mine} differs between pulls.")
        print("\npotions used by this actor (a combat potion is on a ~5min cooldown, so a\n"
              "long fight supports two - one pre-pull and one on the second burn window):")
        if not d["potions"]:
            print("   none - no potion casts recorded at all")
        for p in d["potions"]:
            kind = "COMBAT" if p["combat"] else "healing"
            print(f"   {p['name']:<34} x{p['count']}   ({kind})")
        if not d["combatPotions"]:
            print("   no combat potion detected - before reading that as a miss, check the\n"
                  "   player's cast list: the current potion is not named '... Potion' and a\n"
                  "   new one would need adding to COMBAT_POTION_IDS.")



# ============================================================== potion timing

class PotionCheck(C.Check):
    """Combat potions against the kill: how much of each 30s buff landed before the fight ended.

    Found the hard way on a Mythic Lost Explorers kill (nLvb3TFZGgXWaNry, fight 4): the second
    potion went in with the last Incarnation 18.5s before the kill, so 11.5s of it buffed
    nothing - worth ~0.49M (1.2k DPS) against simply drinking it 30s before the end, and that
    number does not depend on how strong the cooldown it was paired with is. Lining a potion up
    with a cooldown is right; lining it up with a cooldown pressed too late to fit is not.

    The stat uplift is MEASURED from the player's own cast events (spellPower / attackPower
    before vs during the buff), not taken from a tooltip: tooltip values at level scaling
    under-state it, and the log already carries the live number. Damage is treated as
    proportional to that stat, which slightly over-states the value of each potion second.
    """

    id = "potion"
    title = "Combat potion timing"
    group = "common"
    BUFF_S = 30.0
    CD_S = 300.0

    def params(self):
        return {"buffSeconds": self.BUFF_S, "cooldownSeconds": self.CD_S,
                "potionIds": sorted(COMBAT_POTION_IDS)}

    def fight_json(self, fight):
        start, end = fight["startTime"], fight["endTime"]
        secs = F.fight_seconds(fight)
        raw = self.report.events(fight, "Casts", resources=True)
        casts = T.casts(raw)
        pots = [c["timestamp"] for c in casts if c.get("abilityGameID") in COMBAT_POTION_IDS]
        own = [c for c in raw if c.get("type") == "cast" and c.get("resourceActor") == 1]
        dmg = [e for e in self.report.events(fight, "DamageDone") if e.get("type") == "damage"]

        def stat(a, b):
            out = {}
            for k in ("spellPower", "attackPower"):
                v = sorted(c[k] for c in own if a <= c["timestamp"] < b and c.get(k))
                out[k] = v[len(v) // 2] if v else None
            return out

        def rate(a, b):
            if b <= a:
                return 0.0
            return sum(e["amount"] + (e.get("absorbed") or 0) for e in dmg
                       if a <= e["timestamp"] < b) / ((b - a) / 1000)

        avg = rate(start, end)
        inst = []
        for i, t in enumerate(pots):
            active_end = min(end, t + self.BUFF_S * 1000)
            active = (active_end - t) / 1000
            wasted = self.BUFF_S - active
            before, during = stat(t - 30000, t - 500), stat(t + 1000, active_end)
            ratios = [during[k] / before[k] for k in during if during[k] and before[k]]
            uplift = max(ratios) if ratios else None
            # earliest this potion could have started and still run its full 30s before the
            # kill, given the previous potion's cooldown
            earliest = pots[i - 1] + self.CD_S * 1000 if i else start
            fits = end - self.BUFF_S * 1000 >= earliest
            gain = None
            if wasted > 0.5 and fits and uplift:
                shift_from = max(earliest, end - self.BUFF_S * 1000)
                gain = rate(shift_from, t) * (t - shift_from) / 1000 * (uplift - 1)
            window = rate(t, active_end)
            ratio = window / avg if avg else None
            if wasted > 5 and fits:
                verdict, why = F.FAIL, f"{wasted:.1f}s of the buff ran past the kill"
            elif wasted > 0.5:
                verdict, why = F.OK, (f"{wasted:.1f}s past the kill"
                                      + ("" if fits else " (no earlier use fit the cooldown)"))
            elif ratio and ratio >= 1.2:
                verdict, why = F.PERFECT, f"full 30s, damage rate x{ratio:.2f} of the fight average"
            else:
                verdict, why = F.GOOD, f"full 30s, damage rate x{ratio or 0:.2f} of the fight average"
            inst.append(F.instance(F.mmss(t, start), verdict, why, activeSeconds=active,
                                   wastedSeconds=wasted, statUplift=uplift, windowDpsRatio=ratio,
                                   secondsBeforeKill=(end - t) / 1000,
                                   estGainIfDrunk30sBeforeKill=gain))
        return {"label": F.fight_label(fight), "seconds": secs, "potions": len(pots),
                "instances": inst, "tally": F.tally(inst)}

    def combine(self, parts):
        rows = [r for _, d in parts for r in d["instances"]]
        return {"potions": len(rows),
                "wastedSeconds": sum(r["facts"]["wastedSeconds"] for r in rows),
                "estGain": sum(r["facts"]["estGainIfDrunk30sBeforeKill"] or 0 for r in rows),
                "tally": F.tally(rows)}

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            print(f"\n=== {r['label']}  ({r['seconds']:.0f}s)  combat potions: {r['potions']} ===")
            if not r["instances"]:
                print("   none recorded (a pre-pull potion is invisible in the fight's cast log)")
                continue
            print(F.hdr(["when", "verdict", "active", "past kill", "stat x", "dmg rate x",
                         "if 30s before kill"], [7, 8, 7, 10, 7, 11, 18]))
            for i in r["instances"]:
                x = i["facts"]
                gain = x["estGainIfDrunk30sBeforeKill"]
                gtxt = "-" if gain is None else "+%.2fM" % (gain / 1e6)
                print(f"{i['when']:>7}  {i['verdict']:<8}  {x['activeSeconds']:<7.1f}  "
                      f"{x['wastedSeconds']:<10.1f}  {(x['statUplift'] or 0):<7.3f}  "
                      f"{(x['windowDpsRatio'] or 0):<11.2f}  {gtxt:<18}")
        print("\n  'if 30s before kill' re-prices the wasted seconds onto the un-buffed damage just")
        print("  before the potion, using the measured stat uplift. It does not depend on the cooldown")
        print("  the potion was paired with, which is why it is the number to quote.")


# ============================================================== forced out by a mechanic

class DisplacedCheck(C.Check):
    """Enemy mechanics on the player that collapsed their casting - seconds they did not control.

    Scans every debuff an enemy put on this player and keeps the instances where DAMAGE fell
    under half of the player's own rate in the 20s either side, over [applied, removed + recovery]. That
    is how a carried bomb, a fixate, a forced run-out or a stun shows up, and why it has to be
    extracted before any uptime or cooldown finding is read: a cast gap there is not
    inattention. Found missing on nLvb3TFZGgXWaNry fight 4 (Trader Gebbo's Explosive Surprise
    at 5:54: 12 casts/min for 15s, ~1.85M), which an earlier analysis had explained away as
    phase position.

    Damage lost is against that same local rate - an estimate of what the seconds
    were worth, not a verdict. Whether a carrier CAN keep casting is fight-specific: on that
    boss, the 3 top-130 Balance carriers hit late in a Command phase all collapsed the same way
    and lost 1.7-1.8M, while earlier carriers kept casting.
    """

    id = "displaced"
    title = "Forced out by a mechanic"
    group = "common"
    MIN_S = 3.0
    RECOVER_S = 5.0
    LOCAL_S = 20.0
    COLLAPSE = 0.5

    def params(self):
        return {"minDebuffSeconds": self.MIN_S, "recoverySeconds": self.RECOVER_S,
                "localBaselineSeconds": self.LOCAL_S, "collapseBelowRatio": self.COLLAPSE}

    def fight_json(self, fight):
        start, end = fight["startTime"], fight["endTime"]
        aid = self.report.actor_id
        names = self.report.actor_names()
        abil = self.report.ability_names()
        friendly = {a["id"] for a in self.report.meta["masterData"]["actors"]
                    if a["type"] in ("Player", "Pet")}
        deb = self.report.events(fight, "Debuffs", source_id=None, hostility="Friendlies")
        mine = sorted((e for e in deb if e.get("targetID") == aid
                       and e.get("sourceID") not in friendly), key=lambda e: e["timestamp"])
        open_, spans = {}, []
        for e in mine:
            k = e["abilityGameID"]
            if e["type"] == "applydebuff":
                open_[k] = e
            elif e["type"] == "removedebuff" and k in open_:
                a = open_.pop(k)
                if (e["timestamp"] - a["timestamp"]) / 1000 >= self.MIN_S:
                    spans.append((a["timestamp"], e["timestamp"], k, a.get("sourceID")))
        casts = [c["timestamp"] for c in T.casts(self.report.events(fight, "Casts"))]
        dmg = [e for e in self.report.events(fight, "DamageDone") if e.get("type") == "damage"]
        secs = F.fight_seconds(fight)
        cast_avg = 60 * len(casts) / secs if secs else 0
        dps_avg = sum(e["amount"] + (e.get("absorbed") or 0) for e in dmg) / secs if secs else 0
        # Same cache key as encounter.fight(), so the field set must match it exactly:
        # whichever check runs first writes the entry the other one reads.
        fm = W.cached("_fight", "%s|%d" % (self.report.code, fight["id"]), lambda: W.query(
            'query { reportData { report(code: "%s") { fights(fightIDs: [%d]) '
            '{ id name startTime endTime difficulty phaseTransitions { id startTime } } } } }'
            % (self.report.code, fight["id"]))["data"]["reportData"]["report"]["fights"][0])
        transitions = sorted(p["startTime"] for p in (fm.get("phaseTransitions") or [])
                             if p["startTime"] > start)

        def dmg_in(x, y):
            return sum(e["amount"] + (e.get("absorbed") or 0) for e in dmg if x <= e["timestamp"] < y)

        inst, lost_total, kept, unattributable = [], 0.0, [], []
        for a, b, k, src in sorted(spans):
            z = min(end, b + self.RECOVER_S * 1000)
            if any(a < kz and z > ka for ka, kz in kept):
                continue                     # overlaps an instance already kept (bleed inside a bomb)
            # a transition in the recovery tail just ends the window there
            z = min([z] + [t for t in transitions if b <= t < z])
            if any(a < t < b for t in transitions):
                # the phase changed inside the window: the drop cannot be told apart from the
                # transition itself, so it is listed but never priced
                unattributable.append({"when": F.mmss(a, start), "spellId": k,
                                       "name": abil.get(k, str(k)), "debuffSeconds": (b - a) / 1000})
                continue
            dur = (z - a) / 1000
            cpm = 60 * sum(1 for t in casts if a <= t < z) / dur
            dps = dmg_in(a, z) / dur
            # LOCAL baseline, the player's own 20s either side: a phase that is low-damage for
            # everyone must not read as displacement (Splinters in every Command phase did).
            la, lz = max(start, a - self.LOCAL_S * 1000), min(end, z + self.LOCAL_S * 1000)
            # keep the baseline inside the debuff's own phase: clip at the nearest transitions
            la = max([la] + [t for t in transitions if t <= a])
            lz = min([lz] + [t for t in transitions if t >= z])
            local_s = ((a - la) + (lz - z)) / 1000
            local = (dmg_in(la, a) + dmg_in(z, lz)) / local_s if local_s > 0 else dps_avg
            if not local or dps / local >= self.COLLAPSE:
                continue
            kept.append((a, z))
            lost = max(0.0, (local - dps) * dur)
            lost_total += lost
            ratio = dps / local
            inst.append(F.instance(
                F.mmss(a, start), F.FAIL if cpm / cast_avg < self.COLLAPSE else F.OK,
                f"{abil.get(k, k)} ({names.get(src, 'enemy')}) {(b - a) / 1000:.1f}s: damage "
                f"x{ratio:.2f} of the surrounding {self.LOCAL_S:.0f}s, casts {cpm:.0f}/min vs {cast_avg:.0f}",
                spellId=k, debuffSeconds=(b - a) / 1000, castsPerMin=cpm,
                castRatio=cpm / cast_avg, dpsRatio=ratio, estDamageLost=lost))
        return {"label": F.fight_label(fight), "seconds": secs, "instances": inst,
                "spansPhaseTransition": unattributable,
                "estDamageLost": lost_total, "estDpsLost": lost_total / secs if secs else 0}

    def combine(self, parts):
        secs = sum(d["seconds"] for _, d in parts)
        lost = sum(d["estDamageLost"] for _, d in parts)
        return {"instances": sum(len(d["instances"]) for _, d in parts), "estDamageLost": lost,
                "estDpsLost": lost / secs if secs else 0}

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            print(f"\n=== {r['label']}  ({r['seconds']:.0f}s) ===")
            if not r["instances"]:
                print("   no enemy debuff halved the damage rate of the surrounding seconds")
            for i in r["instances"]:
                print(f"   {i['when']:>7}  {i['why']}   ~{i['facts']['estDamageLost'] / 1e6:.2f}M")
            if r["instances"]:
                print(f"   total ~{r['estDamageLost'] / 1e6:.2f}M = {r['estDpsLost'] / 1e3:.2f}k DPS over the pull")
            for u in r.get("spansPhaseTransition", []):
                print(f"   {u['when']:>7}  {u['name']} {u['debuffSeconds']:.1f}s - spans a phase transition, not priced")
        print("\n  Estimates are against the player's own damage rate in the "
              f"{d['params']['localBaselineSeconds']:.0f}s either side of [debuff, removal + "
              f"{d['params']['recoverySeconds']:.0f}s],")
        print("  using only the side in the same encounter phase, so a phase change or a low-damage")
        print("  phase does not read as displacement.")
        print("  Extract these seconds BEFORE reading any uptime, cooldown or parse finding: they were")
        print("  not the player's to spend. Compare against other carriers of the same mechanic before")
        print("  calling any of it avoidable.")


CHECKS = C.registry(AbcCheck, CancelsCheck, ManaCheck, ConsumablesCheck,
                    PotionCheck, DisplacedCheck)
