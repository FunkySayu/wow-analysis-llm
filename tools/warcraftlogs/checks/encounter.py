"""Fight structure from the log itself - phases, boss ability timeline, and the
windows of opportunity, derived rather than looked up.

Spec-agnostic on purpose. Everything here comes out of the report: phase
transitions, enemy casts, enemy self-buffs, and raid-wide damage rate. No
encounter knowledge is hard-coded, so it works on a boss nobody has written a
guide for yet - which, for a tier this new, is most of them.

The one idea worth carrying: **a window of opportunity is measurable, not
looked up.** Take every bounded aura the enemy puts on itself, measure the
*raid's* damage rate while it is up against the raid's own average, and the
amplifies, the immunities and the soak phases separate themselves out. Using
raid damage rather than one player's avoids the obvious circularity - one
player's own burst window would otherwise "detect" itself as a boss mechanic.

Read `fightmap` before any per-player check on an unfamiliar boss. Knowing that
The Coiled Altar pays 2x on Zul'jan for 35 seconds and that its adds are worth
2% of a pull changes which questions about the pull are even worth asking.

Both checks here are per-pull by nature - a "map" of fourteen pulls is not a
map of anything - so they carry no `combine()`. Before the Check base class they
refused a multi-fight selector outright; now the base class maps them and each
pull gets its own section.
"""

import collections

from lib import check as C
from lib import format as F
from lib import wclapi as W

# An aura is a candidate "window" if it is bounded, not permanent, and does not
# fire so often that it is really a rotational debuff rather than a phase.
MIN_WINDOW_S = 4.0
MAX_WINDOW_S = 120.0
MAX_APPLICATIONS = 8

ENEMY_EV = ('query { reportData { report(code: "%s") { events(fightIDs: [%d], '
            'dataType: %s, hostilityType: Enemies, limit: 5000, startTime: 0, '
            'endTime: 999999999) { data } } } }')
RAID_TBL = ('query { reportData { report(code: "%s") { table(dataType: DamageDone, '
            'fightIDs: [%d], hostilityType: Friendlies, startTime: %d, endTime: %d) } } }')
FIGHT_Q = ('query { reportData { report(code: "%s") { fights(fightIDs: [%d]) '
           '{ id name startTime endTime difficulty phaseTransitions { id startTime } } } } }')


def fight(code, fid):
    return W.cached("_fight", "%s|%d" % (code, fid),
                    lambda: W.query(FIGHT_Q % (code, fid))
                    ["data"]["reportData"]["report"]["fights"][0])


def enemy_events(code, fid, kind):
    return W.cached("_en", "%s|%d|%s" % (code, fid, kind),
                    lambda: W.query(ENEMY_EV % (code, fid, kind))
                    ["data"]["reportData"]["report"]["events"]["data"])


ability_names = W.ability_names   # moved to the API layer; now int-keyed


def raid_damage(code, fid, a, b):
    """Total raid damage between two report-relative timestamps."""
    def go():
        t = W.query(RAID_TBL % (code, fid, a, b))["data"]["reportData"]["report"]["table"]["data"]
        return sum(e.get("total") or 0 for e in t.get("entries", []))
    return W.cached("_raid", "%s|%d|%d|%d" % (code, fid, a, b), go)


def aura_windows(code, fid, kind="Buffs"):
    """Bounded (start, end) windows per enemy aura, keyed by (abilityID, targetID).

    Applications without a matching removal are dropped rather than run to the
    end of the fight: a permanent aura is not a window, and treating one as a
    window silently turns the whole fight into its own baseline.
    """
    out = collections.defaultdict(list)
    open_at = {}
    for e in sorted(enemy_events(code, fid, kind), key=lambda x: x["timestamp"]):
        key = (e.get("abilityGameID"), e.get("targetID"))
        if e["type"] in ("applybuff", "applydebuff"):
            open_at.setdefault(key, e["timestamp"])
        elif e["type"] in ("removebuff", "removedebuff") and key in open_at:
            out[key].append((open_at.pop(key), e["timestamp"]))
    return out


def opportunity_windows(code, fid, kind="Buffs"):
    """Every candidate window, scored by what the raid's damage rate does inside it.

    ratio > 1 = the raid hits harder here than its own average. That is either an
    amplify on the boss or a phase where more of the raid's targets are available;
    either way it is where cooldowns belong. ratio well under 1 is the opposite -
    an immunity, a soak, or a movement phase - and is where cooldowns should not
    go. The check does not try to tell those two apart by name, because the name
    is often wrong and the number never is.
    """
    f = fight(code, fid)
    t0, t1 = f["startTime"], f["endTime"]
    dur = (t1 - t0) / 1000.0
    total = raid_damage(code, fid, t0, t1)
    avg = total / dur
    names = ability_names(code)

    # Group by NAME, not by (ability, target). One mechanic routinely arrives as
    # several spell ids applied to several enemies at the same instant - Ghastly
    # Regeneration is two ids, Soulbinding is three - and reporting each of them
    # separately turns one window into five identical-looking rows.
    by_name = collections.defaultdict(list)
    for (gid, _tgt), ws in aura_windows(code, fid, kind).items():
        by_name[names.get(gid, str(gid))].extend(ws)

    rows = []
    for name, ws in by_name.items():
        ws = _merge([(a, b) for a, b in ws
                     if MIN_WINDOW_S <= (b - a) / 1000.0 <= MAX_WINDOW_S])
        if not ws or len(ws) > MAX_APPLICATIONS:
            continue
        secs = sum((b - a) / 1000.0 for a, b in ws)
        dmg = sum(raid_damage(code, fid, a, b) for a, b in ws)
        rows.append({"name": name, "n": len(ws), "secs": secs, "rate": dmg / secs,
                     "ratio": (dmg / secs) / avg,
                     "share": 100.0 * dmg / total,
                     "windows": [((a - t0) / 1000.0, (b - t0) / 1000.0) for a, b in ws],
                     # Per-instance ratios are resolved HERE, not in print(): they
                     # each cost a raid-damage query, and print() may not read the
                     # log. Only the first four are rendered, so only those are
                     # fetched.
                     "perWindow": [(raid_damage(code, fid, a, b) / ((b - a) / 1000.0)) / avg
                                   for a, b in ws[:4]]})
    rows.sort(key=lambda r: -r["ratio"])
    return f, avg, rows


def _merge(ws):
    """Union of overlapping windows, so shared seconds are never counted twice."""
    out = []
    for a, b in sorted(ws):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


# ============================================================== fightmap

class FightmapCheck(C.Check):
    """Phases, boss ability cadence, and the measured windows of opportunity.

    Run this first on any boss you have not analysed before. `-a` is accepted but
    unused - the map is a property of the pull, not of one player.
    """

    id = "fightmap"
    title = "Fight map"
    group = "fight"

    def params(self):
        return {"minWindowSeconds": MIN_WINDOW_S, "maxWindowSeconds": MAX_WINDOW_S,
                "maxApplications": MAX_APPLICATIONS,
                "windowRatio": {"opportunity": 1.15, "avoid": 0.85}}

    def fight_json(self, f):
        code, fid = self.report.code, f["id"]
        meta, avg, rows = opportunity_windows(code, fid)
        t0 = meta["startTime"]
        dur = (meta["endTime"] - t0) / 1000.0

        tr = [(p["id"], (p["startTime"] - t0) / 1000.0)
              for p in (meta.get("phaseTransitions") or [])]
        phases = []
        for (i, s), (_, e) in zip(tr, tr[1:] + [(0, dur)]):
            d = raid_damage(code, fid, t0 + int(s * 1000), t0 + int(e * 1000))
            phases.append({"phase": i, "start": s, "end": e, "seconds": e - s,
                           "raidDps": d / (e - s), "ratio": (d / (e - s)) / avg})

        names = ability_names(code)
        # By name, not id: several mechanics fire two ids under one name (Sszorak's
        # Raging Crosswinds, Zul'jan's Axegrinder) and would otherwise list twice.
        ts_by_name = collections.defaultdict(list)
        for e in enemy_events(code, fid, "Casts"):
            if e["type"] != "cast":
                continue
            ts_by_name[names.get(e.get("abilityGameID"), str(e.get("abilityGameID")))] \
                .append((e["timestamp"] - t0) / 1000.0)
        timeline = []
        for name, ts in sorted(ts_by_name.items(), key=lambda kv: -len(kv[1])):
            ts = sorted(ts)
            gaps = [b - a for a, b in zip(ts, ts[1:]) if b - a > 3]
            timeline.append({"name": name, "casts": len(ts), "at": ts,
                             "cadenceSeconds": (sum(gaps) / len(gaps)) if len(gaps) >= 2 else None})

        return {"name": meta["name"], "difficulty": meta["difficulty"], "seconds": dur,
                "raidDpsAverage": avg, "phases": phases, "windows": rows,
                "bossTimeline": timeline}

    def print(self):
        d = self.json()
        multi = len(d["fights"]) > 1
        for n, row in enumerate(d["fights"]):
            r = row["data"]
            if multi:
                head = f" pull {n + 1}/{len(d['fights'])}: {r['name']} "
                print(("\n" if n else "") + head.center(78, "-") + "\n")
            print("%s  (difficulty %s)  %.0fs   raid average %s dps\n"
                  % (r["name"], r["difficulty"], r["seconds"],
                     format(int(r["raidDpsAverage"]), ",")))
            if r["phases"]:
                print("phases")
                for p in r["phases"]:
                    print("  phase %s  %6.1f - %6.1f  (%5.1fs)  raid %s dps  (%.2fx)"
                          % (p["phase"], p["start"], p["end"], p["seconds"],
                             format(int(p["raidDps"]), ","), p["ratio"]))
                print()

            print("windows of opportunity - raid damage rate inside each enemy self-buff")
            print(F.hdr(["ratio", "aura", "n", "secs", "raid dmg%", "when (s)"],
                        [7, 30, 3, 6, 10, 30]))
            for w in r["windows"]:
                # Everything is listed, including the neutral band. A mechanic that
                # reads as an amplify but measures at 1.0x is a finding in its own
                # right - it means the raid is not converting it, which is exactly
                # the thing worth knowing before deciding whether to hold a cooldown.
                mark = "" if 0.85 < w["ratio"] < 1.15 else (
                    "   <-- window" if w["ratio"] >= 1.15 else "   <-- avoid")
                when = ", ".join("%.0f-%.0f" % tuple(x) for x in w["windows"][:4])
                print("%6.2fx  %-30s %3d %6.0f %9.1f%%  %-30s%s"
                      % (w["ratio"], w["name"][:30], w["n"], w["secs"], w["share"],
                         when[:30], mark))
                if w["n"] > 1:
                    per = ", ".join("%.2fx" % x for x in w["perWindow"])
                    print("%8s  %-30s per window: %s" % ("", "", per))
            print("\n  >1 = the raid hits harder here than its own average: put cooldowns in it.\n"
                  "  <1 = immunity, soak or forced movement: do not.\n"
                  "  ~1 on something the journal calls a vulnerability means the raid is\n"
                  "  not converting it - check the per-window split before planning around it.")

            print("\nboss ability timeline (cast log, most frequent first)")
            for t in r["bossTimeline"][:18]:
                cad = ("  ~%.0fs apart" % t["cadenceSeconds"]) if t["cadenceSeconds"] else ""
                print("  %-30s n=%-3d  %s%s"
                      % (t["name"][:30], t["casts"],
                         ", ".join("%.0f" % x for x in t["at"][:10]), cad))
            print("\n  Cadence is the planning input. A mechanic on a period that does not\n"
                  "  divide into your cooldown - a 96s add wave against a 90s Arcane Surge -\n"
                  "  is what forces a hold decision, and the size of the hold is the cost.")


# ============================================================== off-boss value

class AddValueCheck(C.Check):
    """Is anything other than the boss worth a global cooldown on this fight?

    The question behind "should I hold cooldowns for the add wave". Adds that are
    immune on spawn, despawn on a timer, or die to cleave anyway are not a window
    no matter how threatening they look. Measured across the whole ranking pool
    this is a property of the encounter, not of one player - on The Coiled Altar
    every Arcane mage measured put 97-98% of a pull into the two bosses, so
    "hold for adds" is simply wrong there, while on The Twin Fangs it is not.
    """

    id = "addvalue"
    title = "Off-boss damage share"
    group = "fight"

    def fight_json(self, f):
        code, fid, aid = self.report.code, f["id"], self.report.actor_id
        q = ('query { reportData { report(code: "%s") { table(dataType: DamageDone, '
             'fightIDs: [%d], sourceID: %d, viewBy: Target) } } }' % (code, fid, aid))
        t = W.cached("_tgt", "%s|%d|%d" % (code, fid, aid),
                     lambda: W.query(q)["data"]["reportData"]["report"]["table"]["data"])
        ent = sorted(t.get("entries", []), key=lambda e: -(e.get("total") or 0))
        tot = sum(e.get("total") or 0 for e in ent) or 1
        targets = [{"name": e["name"], "damage": e.get("total") or 0,
                    "sharePct": 100.0 * (e.get("total") or 0) / tot} for e in ent]
        return {"total": tot, "targets": targets,
                "topTwoPct": 100.0 * sum(t["damage"] for t in targets[:2]) / tot}

    def print(self):
        d = self.json()
        multi = len(d["fights"]) > 1
        for n, row in enumerate(d["fights"]):
            r = row["data"]
            if multi:
                head = f" {row['fight']['name']} "
                print(("\n" if n else "") + head.center(56, "-") + "\n")
            print(F.hdr(["target", "damage", "share"], [30, 14, 8]))
            for t in r["targets"][:12]:
                print("%-30s %14s %7.2f%%"
                      % (t["name"][:30], format(int(t["damage"]), ","), t["sharePct"]))
            print("\ntop two targets carry %.1f%% of the pull." % r["topTwoPct"])
            print("Below ~5%% off-boss there is no add window to plan around, however\n"
                  "dangerous the adds are - hold cooldowns for the amplify instead.")


CHECKS = C.registry(FightmapCheck, AddValueCheck)
