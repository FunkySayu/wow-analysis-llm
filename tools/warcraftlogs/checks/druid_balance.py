"""Balance Druid checks, built around the 12.1 default simc APL.

Patch 12.1 turned Eclipse into an *activated* ability on a charge cooldown, so
Eclipse entries are a spendable resource and most of this file measures how well
they are spent. Background: .claude/knowledge/classes/druid/balance-druid-12.1.md.

Every spell ID below was confirmed against real log data (report ThRfrJBk1ZGwyCWc,
Funkitty / Mooshtarda) or against the live Wowhead tooltip - never from memory.
The ones that bite are called out inline.

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
WRATH = 190984
STARFIRE = 194153
STARSURGE = 78674
STARFALL = 191034
MOONFIRE = 8921          # the CAST. The enemy DoT is 164812 (see below).
SUNFIRE = 93402          # the CAST. Damage AND the enemy DoT are both 164815.
ECLIPSE_LUNAR = 1233272  # "Lunar Eclipse" - the button, 32s cooldown, 1 charge base
ECLIPSE_SOLAR = 1233346  # "Solar Eclipse" - same button, other mode
CELESTIAL_ALIGNMENT = 194223
INCARNATION = 102560     # Incarnation: Chosen of Elune (the CA/Inc slot when talented)
FURY_OF_ELUNE = 202770
FORCE_OF_NATURE = 205636
CONVOKE = 391528
WILD_MUSHROOM = 88747
NEW_MOON, HALF_MOON, FULL_MOON = 274281, 274282, 274283

# --- damage / DoT ids (differ from the cast ids!) -----------------------------
MOONFIRE_DOT = 164812    # <- the enemy debuff. Querying 8921 as a debuff returns nothing.
SUNFIRE_DOT = 164815
SHOOTING_STARS = 202497
SHOOTING_STARS_ALT = 1272339  # a SECOND id under the same name, ~10% of the procs.
                              # Counting only 202497 silently undercounts them.
ASTRAL_SMOLDER_DOT = 1263250
STAR_CASCADE = 1271222   # "Starsurge (Star Cascade)" - a free proc'd Starsurge, no cast event
SUNDERED_FIRMAMENT = 394108
BOUNDLESS_MOONLIGHT = 428682
NATURES_BALANCE = 202430
SHOOTING_STARS_IDS = {SHOOTING_STARS, SHOOTING_STARS_ALT}

# --- player auras -------------------------------------------------------------
ECL_SOLAR = 48517        # Eclipse (Solar)
ECL_LUNAR = 48518        # Eclipse (Lunar)
ASCENDANT_STARS = 1263382  # apex: first 3 spenders per Eclipse +20%. STACKING, cap 3.
ASCENDANT_FIRES = 1263363  # apex: next Wrath/Starfire after an Eclipse entry is instant
TOUCH_THE_COSMOS = 450360  # buff id; the TALENT is 450356 - they are different numbers
STARWEAVERS_WARP = 393942  # free Starfall   (not present in the reference log)
STARWEAVERS_WEFT = 393944  # free Starsurge  (not present in the reference log)
UMBRAL_EMBRACE = 393763
STARLORD = 279709
BOAT_ARCANE = 394049     # Balance of All Things; the TALENT is 394048
BOAT_NATURE = 394050
SOLSTICE = 343648
HARMONY_OF_THE_GROVE = 428731  # Keeper of the Grove; absent => Elune's Chosen

# --- enemy debuffs ------------------------------------------------------------
STELLAR_AMPLIFICATION = 450214  # Starsurge -> +periodic damage taken
ATMOSPHERIC_EXPOSURE = 430589   # Full Moon / Fury of Elune -> +damage taken (Elune's Chosen)
FOE_DEBUFF = 202770

# --- external / raid cooldowns -----------------------------------------------
# "Lust" is EIGHT different 30%-haste buffs, not the four everyone remembers, and
# which one you get depends on the raid's classes - so a check that hardcodes
# Bloodlust/Heroism/Time Warp/Primal Rage reports "no lust in this fight" for a
# raid that lusted perfectly. Verified concretely on JqywQ2R1XpgZrVKL fight 18:
# a Mage cast Time Warp and it applied to NOBODY (the raid was already Sated),
# while every player actually held `Harrier's Cry` for 40s from a Hunter. The
# first version of this list missed it and the report wrongly said "no lust".
# All eight share one tooltip line - "Increases haste by 30% for all party and
# raid members" - and all cause an exhaustion debuff, which is the real test for
# membership in this set.
BLOODLUST = 2825               # Shaman (Horde)
HEROISM = 32182                # Shaman (Alliance)
TIME_WARP = 80353              # Mage
PRIMAL_RAGE = 264667           # Hunter pet
HARRIERS_CRY = 466904          # Hunter (Eagle) - the one that bit us
ANCIENT_HYSTERIA = 90355       # Hunter pet (Core Hound)
NETHERWINDS = 160452           # Hunter pet (Nether Ray)
FURY_OF_THE_ASPECTS = 390386   # Evoker
LUST_BUFFS = {BLOODLUST, HEROISM, TIME_WARP, PRIMAL_RAGE, HARRIERS_CRY,
              ANCIENT_HYSTERIA, NETHERWINDS, FURY_OF_THE_ASPECTS}

# Drums are only +15% haste but still trigger the same exhaustion debuff, so they
# occupy the lust slot without filling it. Tracked separately: a fight "covered"
# by drums is not the same as a fight covered by a real lust.
DRUMS = {256740, 309658, 381301}   # Maelstrom / Deathly Ferocity / Feral Hide

# Exhaustion debuffs - the definitive marker that a lust landed on this player.
EXHAUSTION = {57724, 57723, 80354, 264689}   # Sated/Exhaustion/Temporal Disp./Fatigued

AP_TYPE = 8              # classResources type for Astral Power. amount is AP x10.
ECLIPSE_RECHARGE = 32.0  # base. `Sculpt the Stars` cuts it to 29.0 - see EclipseCheck.

# DoT duration model, used by RefreshCheck. Base 18s is from the live Moonfire and
# Sunfire tooltips (both "over 18 sec"), NOT from memory. Pandemic carry-over is the
# standard 30% of base. `Aetherial Kindling` (327541) adds 3s per Starfall cast to a
# 28s ceiling, which is why gap-between-casts is NOT remaining duration.
DOT_BASE = 18.0
AETHERIAL_EXTEND = 3.0
AETHERIAL_CAP = 28.0

ECLIPSE_CASTS = {ECLIPSE_LUNAR, ECLIPSE_SOLAR}
CA_INC = {CELESTIAL_ALIGNMENT, INCARNATION}
SPENDERS = {STARSURGE, STARFALL}
FILLERS = {WRATH, STARFIRE}
ROTATIONAL = (SPENDERS | FILLERS | ECLIPSE_CASTS | CA_INC |
              {MOONFIRE, SUNFIRE, FURY_OF_ELUNE, FORCE_OF_NATURE, CONVOKE,
               WILD_MUSHROOM, NEW_MOON, HALF_MOON, FULL_MOON})

NAMES = {
    WRATH: "Wrath", STARFIRE: "Starfire", STARSURGE: "Starsurge", STARFALL: "Starfall",
    MOONFIRE: "Moonfire", SUNFIRE: "Sunfire", ECLIPSE_LUNAR: "Eclipse (Lunar)",
    ECLIPSE_SOLAR: "Eclipse (Solar)", CELESTIAL_ALIGNMENT: "Celestial Alignment",
    INCARNATION: "Incarnation", FURY_OF_ELUNE: "Fury of Elune",
    FORCE_OF_NATURE: "Force of Nature", CONVOKE: "Convoke the Spirits",
    WILD_MUSHROOM: "Wild Mushroom", NEW_MOON: "New Moon", HALF_MOON: "Half Moon",
    FULL_MOON: "Full Moon",
    # not castable, but they show up as Astral Power sources in ApCheck
    SHOOTING_STARS: "Shooting Stars", SHOOTING_STARS_ALT: "Shooting Stars",
    NATURES_BALANCE: "Nature's Balance", SUNDERED_FIRMAMENT: "Sundered Firmament",
    BOUNDLESS_MOONLIGHT: "Boundless Moonlight", STAR_CASCADE: "Starsurge (Star Cascade)",
}

# Buff -> the casts that legitimately consume it. Used to tell "spent" from "expired".
PROC_CONSUMERS = {
    TOUCH_THE_COSMOS: SPENDERS,
    STARWEAVERS_WARP: {STARFALL},
    STARWEAVERS_WEFT: {STARSURGE},
    ASCENDANT_FIRES: FILLERS,
}
PROC_NAMES = {
    TOUCH_THE_COSMOS: "Touch the Cosmos", STARWEAVERS_WARP: "Starweaver's Warp",
    STARWEAVERS_WEFT: "Starweaver's Weft", ASCENDANT_FIRES: "Ascendant Fires",
}
FREE_SPENDER_PROCS = (TOUCH_THE_COSMOS, STARWEAVERS_WARP, STARWEAVERS_WEFT)

# Everything the APL ranks ABOVE `eclipse` in ec_st / kotg_st / aoe. Spending a GCD
# on one of these at max Eclipse charges is the priority working as written, not a
# mistake - only the lines BELOW eclipse (spenders, moons, mushroom, filler) are.
ABOVE_ECLIPSE = {SUNFIRE, MOONFIRE, CONVOKE, FURY_OF_ELUNE, FORCE_OF_NATURE} | CA_INC

# Casts that `Lunation` counts as "Arcane abilities" for Fury of Elune's cooldown. Fitted,
# not assumed: with exactly these four, none of 562 Furies over 40 Mythic pulls is cast
# before the reconstructed ready time; drop any one and 119+ become impossible.
LUNATION_CASTS = {STARFIRE, MOONFIRE, STARSURGE, STARFALL}


# ============================================================== small helpers

def _ap(e):
    """Astral Power at an event, in AP. WCL stores it x10 in classResources.

    Verified against the raw stream: on a SPENDER's cast event this is the pool
    BEFORE the cost is paid - i.e. what the APL saw when it made the decision,
    which is what every condition here wants. On a GENERATOR's cast event it is
    the pool AFTER that cast's own energize, so it reads ~12 high for Starfire.
    """
    for r in e.get("classResources") or []:
        if r.get("type") == AP_TYPE:
            return r["amount"] / 10.0
    return None


def _ap_max(e):
    for r in e.get("classResources") or []:
        if r.get("type") == AP_TYPE:
            return r.get("max", 1000) / 10.0
    return None


def _casts(code, fid, aid):
    """Cast events WITH resources attached.

    `includeResources` is what puts `classResources` on each event, and without it
    every Astral Power reading here comes back None - silently, as an empty list,
    not as an error. Always go through this helper rather than W.events directly.
    """
    return W.events(code, fid, "Casts", aid, resources=True)


def _merge(wins):
    """Merge overlapping (start, end) pairs."""
    out = []
    for s, e in sorted(wins):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _eclipse_windows(buffs):
    """Any-Eclipse-up windows. Solar and Lunar are separate auras and BOTH are up
    during Celestial Alignment / Incarnation, so they have to be merged."""
    return _merge(T.windows(buffs, ECL_SOLAR, default_ms=15000) +
                  T.windows(buffs, ECL_LUNAR, default_ms=15000))


def _entries(buffs, dedupe_ms=500):
    """Eclipse entries as [(ts, {modes})].

    An entry is an application of either Eclipse aura. CA/Incarnation and the
    `Total Eclipse` proc apply BOTH at the same instant - that is one entry, not
    two, so applications within `dedupe_ms` collapse into one.
    """
    ev = []
    for guid, tag in ((ECL_SOLAR, "solar"), (ECL_LUNAR, "lunar")):
        ev += [(e["timestamp"], tag) for e in buffs
               if e.get("abilityGameID") == guid
               and e["type"] in ("applybuff", "refreshbuff")]
    ev.sort()
    out = []
    for ts, tag in ev:
        if out and ts - out[-1][0] <= dedupe_ms:
            out[-1][1].add(tag)
        else:
            out.append([ts, {tag}])
    return [(ts, m) for ts, m in out]


def _apex_stacks(buffs):
    """[(ts, stacks_after)] for Ascendant Stars.

    Not `T.stack_timeline`: that helper assumes an aura starts at 1 stack and
    builds up, but Ascendant Stars is applied at its cap of 3 and is spent down,
    and WCL's `applybuff` carries no stack field - so the generic helper would
    report 1 for a freshly applied, completely unspent buff.
    """
    tl = []
    for e in sorted(buffs, key=lambda x: x["timestamp"]):
        if e.get("abilityGameID") != ASCENDANT_STARS:
            continue
        ty = e["type"]
        if ty in ("applybuff", "refreshbuff"):
            tl.append((e["timestamp"], 3))
        elif ty in ("applybuffstack", "removebuffstack"):
            tl.append((e["timestamp"], e.get("stack", 0)))
        elif ty == "removebuff":
            tl.append((e["timestamp"], 0))
    return tl


def _charge_pool(ts, start, end, charges, recharge):
    """Simulate a charge cooldown over cast times `ts`.

    Returns (violations, capped_seconds, pool_before_each_cast, capped_intervals).
    `violations` is the number of casts the model says were impossible (pool below
    1) - a nonzero count means the model is wrong, which is how the charge count
    gets detected. `capped_seconds` is time sitting at max charges, i.e. recharge
    thrown away, and `capped_intervals` is where it was spent, so a caller can ask
    whether the player was actually able to use it.
    """
    pool, last, bad, capped, at_cast, iv = float(charges), start, 0, 0.0, [], []
    for t in ts:
        full_at = last + max(0.0, charges - pool) * recharge * 1000.0
        if full_at < t:
            capped += (t - full_at) / 1000.0
            iv.append((full_at, t))
        pool = min(charges, pool + (t - last) / 1000.0 / recharge)
        last = t
        at_cast.append(pool)
        if pool < 0.98:
            bad += 1
            pool = 0.0
        else:
            pool -= 1.0
    full_at = last + max(0.0, charges - pool) * recharge * 1000.0
    if full_at < end:
        capped += (end - full_at) / 1000.0
        iv.append((full_at, end))
    return bad, capped, at_cast, iv


def _active_windows(code, fid, aid, gap_ms=5000):
    """When the actor was actually engaged, from their own damage events.

    Needed to read `capped` honestly: an encounter with a long untargetable phase
    banks Eclipse charges for reasons that are not the player's fault, and holding
    the button through a phase with nothing to hit is correct play, not waste.
    """
    ts = [e["timestamp"] for e in W.events(code, fid, "DamageDone", aid)]
    return [(s, e) for s, e, _ in T.segments(ts, gap_ms)]


def _detect_charges(code, aid, fights, recharge=ECLIPSE_RECHARGE):
    """Fewest Eclipse charges that make every observed cast possible.

    2 means `Improved Eclipse` is talented. This is empirical inference, not a
    talent read - the log exposes no resolved talent list.
    """
    for ch in (1, 2, 3):
        bad = 0
        for f in fights:
            c = _casts(code, f["id"], aid)
            ts = sorted(e["timestamp"] for e in T.casts(c)
                        if e["abilityGameID"] in ECLIPSE_CASTS)
            bad += _charge_pool(ts, f["startTime"], f["endTime"], ch, recharge)[0]
        if bad == 0:
            return ch
    return 2


def _dot_windows(code, fid, aid, guid, gap_ms=5000):
    """[(start, end, (targetID, targetInstance))] for one of this actor's DoTs,
    reconstructed from its TICKS rather than from applydebuff/removedebuff.

    This is not the obvious way round, and the obvious way is wrong. WCL's debuff
    apply/refresh/remove events are keyed on the *aura on the target*, not on the
    caster: when several druids Moonfire one boss, the second druid's application
    logs as `refreshdebuff` and only one `removedebuff` is emitted for the lot.
    Verified on fight 10 of ThRfrJBk1ZGwyCWc, where four druids share the target -
    this actor's Moonfire shows apply at 1.7s, refresh at 2.6s, then nothing until
    60.4s and no remove at all, which reads as a 38-second DoT drop. The tick
    stream over the same span is continuous, so the drop never happened.

    Damage events always carry the true sourceID, so ticks give per-caster truth.
    Moonfire and Sunfire tick roughly every 1-2s here, so a gap over `gap_ms`
    (default 5s) is a genuine lapse rather than haste jitter.

    Pass the DoT's DAMAGE id (MOONFIRE_DOT / SUNFIRE_DOT), not the cast id -
    Moonfire's cast id 8921 produces no tick events at all.
    """
    ev = W.events(code, fid, "DamageDone", aid, ability_id=guid)
    by_target = collections.defaultdict(list)
    for e in ev:
        if e.get("tick"):
            by_target[(e.get("targetID"), e.get("targetInstance", 1))].append(e["timestamp"])
    out = []
    for key, ts in by_target.items():
        for s, e, n in T.segments(ts, gap_ms):
            # the DoT lands ~one tick before its first tick; use the segment's own
            # median tick interval so the estimate follows the actor's haste
            lead = ((e - s) / (n - 1)) if n > 1 else 1000.0
            out.append((s - lead, e, key))
    return out


def _primary_target(dmg):
    """The (targetID, targetInstance) with the largest max HP the actor damaged."""
    hp = {}
    for e in dmg:
        if e.get("maxHitPoints"):
            k = (e.get("targetID"), e.get("targetInstance", 1))
            hp[k] = max(hp.get(k, 0), e["maxHitPoints"])
    return max(hp, key=hp.get) if hp else None


def _hero_tree(code, aid, fights):
    """'keeper' if Harmony of the Grove is ever on the player, else 'elune'.

    Empirical, per .claude/knowledge/method/resource-economy.md: the log exposes no resolved talent list, so this is
    inferred from a tree-exclusive buff rather than asserted.

    Deliberately NOT per-fight-then-consensus, unlike `barrage`'s hero tree. The
    evidence here is one-sided: seeing Harmony proves Keeper, but not seeing it in
    a 40-second trash pull proves nothing at all. So a fight-scoped check reports
    what it saw in that fight and the roll-up ORs them together
    (`_combine_tree`), rather than letting a majority of uninformative pulls
    outvote the one that carried the proof.
    """
    for f in fights:
        for e in W.events(code, f["id"], "Buffs", aid):
            if e.get("abilityGameID") == HARMONY_OF_THE_GROVE:
                return "keeper"
    return "elune"


def _fight_tree(report, f):
    """Per-fight half of `_hero_tree`: 'keeper', or None for "no evidence here"."""
    for e in report.events(f, "Buffs"):
        if e.get("abilityGameID") == HARMONY_OF_THE_GROVE:
            return "keeper"
    return None


def _combine_tree(parts):
    """Any pull proving Keeper settles it; otherwise Elune's Chosen by default."""
    seen = [d.get("heroTree") for _, d in parts]
    return "keeper" if "keeper" in seen else "elune"


class _RunLevel:
    """Mixin for talent inferences that are genuinely NOT per-pull.

    A charge count or a cooldown model is a property of the character's build, and
    a single short pull carries too few casts to identify one - two Eclipse casts
    are consistent with one charge or with three. So these are resolved once over
    the whole selection and reported in `params()`, which is where configuration
    belongs, rather than being re-derived (badly) inside every `fight_json`.

    This is the documented exception to "compute per fight", not a loophole: it
    covers inputs the check is CONFIGURED with, never findings it measures.
    """

    def _memo(self, key, produce):
        cache = self.__dict__.setdefault("_runlevel", {})
        if key not in cache:
            cache[key] = produce()
        return cache[key]

    def _charges(self):
        return self._memo("charges", lambda: _detect_charges(
            self.report.code, self.report.actor_id, self.report.fights))


# ============================================================== eclipse economy

class EclipseCheck(_RunLevel, C.Check):
    """Eclipse entries: the 12.1 resource everything else hangs off.

    Eclipse is a button on a charge cooldown, and a long list of talents pays out
    once per *entry* (Ascendant Eclipses, Balance of All Things, Cenarius' Might,
    Astral Communion, Sylvan Beckoning). Entry COUNT is therefore the binding
    constraint, not Eclipse uptime - so the number that matters here is the time
    spent sitting at max charges, which is recharge thrown in the bin.

    APL line under audit: `eclipse,if=variable.eclipse_timings` in every list, plus
    `kotg_st`'s extra gate `astral_power>60|charges_fractional=2`.
    """

    id = "eclipse"
    title = "Eclipse economy"
    group = "druid"
    LOW_AP = 40

    def params(self):
        ch = self._charges()
        return {"charges": ch, "rechargeSeconds": ECLIPSE_RECHARGE,
                "improvedEclipse": ch >= 2, "lowApThreshold": self.LOW_AP}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        charges = self._charges()
        b = self.report.events(f, "Buffs")
        c = _casts(code, f["id"], aid)
        d = F.fight_seconds(f)
        ent = _entries(b)
        allc = T.casts(c)
        ecasts = [e for e in allc if e["abilityGameID"] in ECLIPSE_CASTS]
        cainc = [e for e in allc if e["abilityGameID"] in CA_INC]
        _, capped, _, cap_iv = _charge_pool([e["timestamp"] for e in ecasts],
                                            f["startTime"], f["endTime"], charges,
                                            ECLIPSE_RECHARGE)
        # split the capped time by whether the player was engaged at the time -
        # banking charges through an untargetable phase is correct, not waste
        act = _active_windows(code, f["id"], aid)
        live = sum(max(0, min(y, q) - max(x, p))
                   for x, y in cap_iv for p, q in act) / 1000.0
        up = sum(e - s for s, e in _eclipse_windows(b)) / 1000.0
        aps = [x for x in (_ap(e) for e in ecasts) if x is not None]
        return {
            "label": F.fight_label(f), "seconds": d,
            "entries": len(ent), "entriesPerMin": 60 * len(ent) / d,
            "buttonCasts": len(ecasts), "caIncCasts": len(cainc),
            "uptimeSeconds": up, "uptimePct": F.pct(up, d),
            "cappedSeconds": capped, "cappedWhileEngagedSeconds": live,
            "apAtEntry": aps,
            "meanApAtEntry": statistics.mean(aps) if aps else 0.0,
            "lowApPct": F.pct(sum(1 for x in aps if x < self.LOW_AP), len(aps)) if aps else 0.0,
        }

    def combine(self, parts):
        dur = sum(d["seconds"] for _, d in parts)
        if not dur:
            return None
        aps = [x for _, d in parts for x in d["apAtEntry"]]
        entries = sum(d["entries"] for _, d in parts)
        capped = sum(d["cappedSeconds"] for _, d in parts)
        live = sum(d["cappedWhileEngagedSeconds"] for _, d in parts)
        up = sum(d["uptimeSeconds"] for _, d in parts)
        return {
            "fights": len(parts), "seconds": dur,
            "entries": entries, "entriesPerMin": 60 * entries / dur,
            "buttonCasts": sum(d["buttonCasts"] for _, d in parts),
            "caIncCasts": sum(d["caIncCasts"] for _, d in parts),
            "uptimePct": F.pct(up, dur),
            "cappedSeconds": capped, "cappedPct": F.pct(capped, dur),
            "cappedWhileEngagedSeconds": live,
            "cappedWhileEngagedPct": F.pct(live, capped),
            "entriesThrownAway": live / ECLIPSE_RECHARGE,
            "cappedWithNothingToHitSeconds": capped - live,
            "apAtEntry": {
                "mean": statistics.mean(aps), "median": statistics.median(aps),
                "belowThresholdPct": F.pct(sum(1 for x in aps if x < self.LOW_AP), len(aps)),
            } if aps else None,
        }

    def print(self):
        d = self.json()
        p = d["params"]
        print(f"charge model: {p['charges']} charge(s) @ {p['rechargeSeconds']:.0f}s recharge  ->  "
              f"Improved Eclipse {'PRESENT' if p['improvedEclipse'] else 'ABSENT'}")
        print("  (fewest charges that make every observed cast possible)")
        print("  `Sculpt the Stars` (29s recharge) is not distinguishable from cast times")
        print("  alone; 32s is assumed, which UNDER-states the wasted recharge below.\n")
        print(F.hdr(["fight", "dur", "entr", "/min", "button", "CA/Inc", "up%",
                     "capped s", "in combat", "AP@entry", "<40AP"],
                    [24, 6, 5, 5, 7, 7, 6, 9, 9, 9, 6]))
        for row in d["fights"]:
            r = row["data"]
            print(f"{r['label'][:24]:24}  {r['seconds']:<6.0f}  {r['entries']:<5d}  "
                  f"{r['entriesPerMin']:<5.1f}  {r['buttonCasts']:<7d}  "
                  f"{r['caIncCasts']:<7d}  {r['uptimePct']:<6.1f}  "
                  f"{r['cappedSeconds']:<9.0f}  {r['cappedWhileEngagedSeconds']:<9.0f}  "
                  f"{r['meanApAtEntry']:<9.1f}  {r['lowApPct']:<6.0f}")
        o = d["overall"]
        if not o:
            return
        print(f"\n{o['fights']} fights / {o['seconds']:.0f}s")
        print(f"  Eclipse entries              : {o['entries']} "
              f"({o['entriesPerMin']:.2f}/min) - "
              f"{o['buttonCasts']} from the button, {o['caIncCasts']} from CA/Incarnation")
        print(f"  Eclipse uptime               : {o['uptimePct']:.1f}%")
        print(f"  time at max charges          : {o['cappedSeconds']:.0f}s "
              f"({o['cappedPct']:.1f}% of the fight)")
        print(f"     of that, while engaged    : {o['cappedWhileEngagedSeconds']:.0f}s "
              f"({o['cappedWhileEngagedPct']:.0f}% of it) "
              f"~= {o['entriesThrownAway']:.1f} entries actually thrown away")
        print(f"     while nothing to hit      : {o['cappedWithNothingToHitSeconds']:.0f}s "
              "- banking through a phase is correct play, not waste")
        if o["apAtEntry"]:
            a = o["apAtEntry"]
            print(f"  Astral Power when pressed    : mean {a['mean']:.1f}  "
                  f"median {a['median']:.0f}  "
                  f"under 40: {a['belowThresholdPct']:.0f}%")
        print("\nRead the in-combat capped seconds, not the uptime and not the raw total.")
        print("Every 32s at max charges while you had a target is one entry's worth of")
        print("on-entry talent value (apex, BoAT, Solstice) that never paid out.")


# ============================================================== apex talent

class ApexCheck(C.Check):
    """Ascendant Eclipses: are all 3 premium spenders used inside each Eclipse?

    Rank 1 gives the first 3 Starsurges/Starfalls of each Eclipse +20% damage
    (aura `Ascendant Stars`, 3 stacks) and makes the next Wrath/Starfire instant
    (`Ascendant Fires`). Both are per-ENTRY payouts, which is why entry count and
    spender count are one problem: an entry taken while Astral-Power-starved
    cannot cash its 3 stacks.
    """

    id = "apex"
    title = "Apex spender windows"
    group = "druid"
    STACKS = 3

    def params(self):
        return {"stacksPerWindow": self.STACKS}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        b = self.report.events(f, "Buffs")
        c = _casts(code, f["id"], aid)
        spend = sorted(e["timestamp"] for e in T.casts(c) if e["abilityGameID"] in SPENDERS)
        stars = [e for e in b if e.get("abilityGameID") == ASCENDANT_STARS]

        # Count CONSUMPTIONS, not the stack field. Each stack spent fires a
        # `removebuffstack`, EXCEPT the last one, which fires a plain `removebuff` -
        # exactly the same event the buff emits when it expires unspent. Counting
        # `3 - stack` therefore under-reports every fully-used window by one. The two
        # cases are separated by whether a spender was cast at that instant.
        per_window = []
        used, open_ = 0, False
        for e in sorted(stars, key=lambda x: x["timestamp"]):
            ty, ts = e["type"], e["timestamp"]
            if ty in ("applybuff", "refreshbuff"):
                if open_:
                    per_window.append(used)
                used, open_ = 0, True
            elif ty == "removebuffstack":
                used += 1
            elif ty == "removebuff":
                if open_:
                    if any(ts - 1500 <= x <= ts + 250 for x in spend):
                        used += 1
                    per_window.append(used)
                used, open_ = 0, False
        if open_:
            per_window.append(used)

        fires = [e for e in b if e.get("abilityGameID") == ASCENDANT_FIRES]
        fill = sorted(e["timestamp"] for e in T.casts(c) if e["abilityGameID"] in FILLERS)
        fires_used = fires_lost = 0
        for e in fires:
            if e["type"] != "removebuff":
                continue
            t = e["timestamp"]
            if any(t - 1500 <= x <= t + 250 for x in fill):
                fires_used += 1
            else:
                fires_lost += 1
        return {"apexSeen": bool(stars), "spendersPerWindow": per_window,
                "firesUsed": fires_used, "firesLost": fires_lost}

    def combine(self, parts):
        per = [x for _, d in parts for x in d["spendersPerWindow"]]
        seen = any(d["apexSeen"] for _, d in parts)
        used = sum(d["firesUsed"] for _, d in parts)
        lost = sum(d["firesLost"] for _, d in parts)
        if not seen or not per:
            return {"apexSeen": seen, "windows": 0,
                    "firesUsed": used, "firesLost": lost}
        slots = self.STACKS * len(per)
        return {
            "apexSeen": True,
            "windows": len(per),
            "mean": statistics.mean(per), "median": statistics.median(per),
            "allSpentPct": F.pct(sum(1 for x in per if x >= self.STACKS), len(per)),
            "wastedWindowPct": F.pct(sum(1 for x in per if x <= 1), len(per)),
            "histogram": [{"spent": k, "windows": v}
                          for k, v in sorted(collections.Counter(per).items())],
            "firesUsed": used, "firesLost": lost,
            "firesLostPct": F.pct(lost, used + lost),
            "slots": slots, "slotsUnused": slots - sum(per),
        }

    def print(self):
        d = self.json()["overall"]
        if not d["apexSeen"]:
            print("`Ascendant Stars` never appears on this actor - the apex talent")
            print("Ascendant Eclipses is not taken (or is below rank 1). Nothing to measure.")
            return
        print(f"Eclipse windows with the apex buff : {d['windows']}")
        print(f"  premium spenders used            : mean {d['mean']:.2f} / 3   "
              f"median {d['median']:.0f}")
        print(f"     all 3 spent                   : {d['allSpentPct']:.0f}%")
        print(f"     0 or 1 spent (window wasted)  : {d['wastedWindowPct']:.0f}%")
        for h in d["histogram"]:
            print(f"       {h['spent']} spent : {'#' * min(60, h['windows'])} {h['windows']}")
        if d["firesUsed"] + d["firesLost"]:
            print("\n  Ascendant Fires (free instant Wrath/Starfire)")
            print(f"     consumed by a filler          : {d['firesUsed']}")
            print(f"     expired unused                : {d['firesLost']} "
                  f"({d['firesLostPct']:.0f}%)")
        print(f"\n  {d['slotsUnused']} of {d['slots']} premium spender slots went unused. "
              "Each is a +20% Starsurge/Starfall.")


# ============================================================== astral power

class ApCheck(C.Check):
    """Astral Power overcap - the direct cost of not spending, per generator.

    WCL's `resourcechange` events carry a `waste` field, so this is measured, not
    inferred from a reconstructed pool. Spenders are Starsurge and Starfall and
    essentially nothing else, so every wasted point is a spender that was not cast.
    """

    id = "ap"
    title = "Astral Power overcap"
    group = "druid"
    #: One Starfire's worth of headroom - inside this, the next filler overcaps.
    NEAR_CAP_AP = 12

    def params(self):
        return {"nearCapAp": self.NEAR_CAP_AP,
                "spenderCost": {"Starsurge": 30, "Starfall": 50}}

    def fight_json(self, f):
        rc = [e for e in self.report.events(f, "Resources", resources=True)
              if e.get("resourceChangeType") == AP_TYPE]
        gain, waste = collections.Counter(), collections.Counter()
        for e in rc:
            # key by display name: Shooting Stars fires under two different spell IDs
            # and splitting the row makes the biggest leak look like two small ones
            gid = str(NAMES.get(e.get("abilityGameID"), e.get("abilityGameID")))
            gain[gid] += e.get("resourceChange", 0) - e.get("waste", 0)
            waste[gid] += e.get("waste", 0)
        # time spent within one Starfire (12 AP) of the cap
        cap_time = 0.0
        prev = None
        for e in sorted(rc, key=lambda x: x["timestamp"]):
            ap, mx = _ap(e), _ap_max(e)
            if prev and prev[1] is not None and prev[2] and prev[1] >= prev[2] - self.NEAR_CAP_AP:
                cap_time += (e["timestamp"] - prev[0]) / 1000.0
            prev = (e["timestamp"], ap, mx)
        return {"seconds": F.fight_seconds(f), "nearCapSeconds": cap_time,
                "gained": dict(gain), "wasted": dict(waste)}

    def combine(self, parts):
        gain, waste = collections.Counter(), collections.Counter()
        for _, d in parts:
            gain.update(d["gained"])
            waste.update(d["wasted"])
        tg, tw = sum(gain.values()), sum(waste.values())
        dur = sum(d["seconds"] for _, d in parts)
        cap = sum(d["nearCapSeconds"] for _, d in parts)
        return {
            "fights": len(parts), "seconds": dur,
            "generated": tg + tw, "wasted": tw,
            "wastedPct": F.pct(tw, tg + tw),
            "nearCapSeconds": cap, "nearCapPct": F.pct(cap, dur),
            "bySource": [{"source": gid, "wasted": n,
                          "shareOfItsGenerationPct": F.pct(n, gain[gid] + n)}
                         for gid, n in waste.most_common(10) if n],
        }

    def print(self):
        d = self.json()["overall"]
        if not d["generated"]:
            print("no Astral Power resourcechange events found")
            return
        print(f"across {d['fights']} fights / {d['seconds']:.0f}s")
        print(f"  Astral Power generated   : {d['generated']:,}")
        print(f"  overcapped (wasted)      : {d['wasted']:,}  ({d['wastedPct']:.1f}%)")
        print(f"  time within 12 AP of cap : {d['nearCapSeconds']:.0f}s  "
              f"({d['nearCapPct']:.1f}%)")
        if d["wasted"]:
            print("\n  wasted by source:")
            for s in d["bySource"]:
                print(f"     {s['source']:<22} {s['wasted']:>7,}  "
                      f"({s['shareOfItsGenerationPct']:.0f}% of what it generated)")
        print("\n  Starsurge costs 30 AP, Starfall 50. Divide the wasted total by 30 for a")
        print("  floor on the Starsurges that generation alone could have paid for.")


# ============================================================== dot uptime

class DotsCheck(C.Check):
    """Sunfire / Moonfire uptime - the top two lines of every APL list.

    `actions.<list>=sunfire,target_if=remains<2|refreshable&buff.eclipse.down` sits
    above every cooldown and every spender, so a DoT that falls off is a priority
    inversion by definition. DoTs also feed Shooting Stars, which is a top-3 damage
    source and pure Astral Power generation, so a drop costs more than its ticks.
    """
    id = "dots"
    title = "DoT uptime"
    group = "druid"
    DROP_SECONDS = 2.0
    SHOOTING_STARS_AP = 2

    def params(self):
        return {"dropThresholdSeconds": self.DROP_SECONDS,
                "shootingStarsAp": self.SHOOTING_STARS_AP}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        d = F.fight_seconds(f)
        dmg = self.report.events(f, "DamageDone", resources=True)
        prim = _primary_target(dmg)
        row, area = {}, {}
        drops, longest, first = 0, 0.0, 0.0
        for guid, tag in ((SUNFIRE_DOT, "SF"), (MOONFIRE_DOT, "MF")):
            wins = _dot_windows(code, f["id"], aid, guid)
            on_prim = _merge([(s, e) for s, e, k in wins if k == prim])
            row[tag] = F.pct(sum(e - s for s, e in on_prim) / 1000.0, d)
            # a "drop" is the DoT falling off mid-fight for >2s. The gap before the
            # first application is reported separately as `1st cast` - that one is a
            # pull-timing problem, not a refresh problem.
            prev = None
            for s, e in on_prim:
                if prev is not None:
                    gap = (s - prev) / 1000.0
                    longest = max(longest, gap)
                    if gap > self.DROP_SECONDS:
                        drops += 1
                prev = e
            if on_prim:
                first = max(first, (on_prim[0][0] - f["startTime"]) / 1000.0)
            area[tag] = sum(e - s for s, e, _ in wins) / 1000.0
        ss = len([e for e in dmg if e.get("abilityGameID") in SHOOTING_STARS_IDS])
        return {
            "label": F.fight_label(f), "seconds": d,
            "sunfireUptimePct": row["SF"], "moonfireUptimePct": row["MF"],
            "drops": drops, "longestGapSeconds": longest, "firstCastSeconds": first,
            "dotSecondsPerFightSecond": (area["SF"] + area["MF"]) / d,
            "shootingStars": ss, "shootingStarsPerMin": 60 * ss / d,
        }

    def combine(self, parts):
        dur = sum(d["seconds"] for _, d in parts)
        if not dur:
            return None
        ss = sum(d["shootingStars"] for _, d in parts)
        return {
            "fights": len(parts), "seconds": dur,
            # Uptime is weighted by fight length, not a mean of percentages.
            "sunfireUptimePct": sum(d["sunfireUptimePct"] * d["seconds"]
                                    for _, d in parts) / dur,
            "moonfireUptimePct": sum(d["moonfireUptimePct"] * d["seconds"]
                                     for _, d in parts) / dur,
            "drops": sum(d["drops"] for _, d in parts),
            "longestGapSeconds": max(d["longestGapSeconds"] for _, d in parts),
            "shootingStars": ss, "shootingStarsPerMin": 60 * ss / dur,
            "shootingStarsAp": self.SHOOTING_STARS_AP * ss,
        }

    def print(self):
        d = self.json()
        print(F.hdr(["fight", "dur", "SF up%", "MF up%", "drops", "longest gap",
                     "1st cast", "dots avg", "SS/min"],
                    [24, 6, 7, 7, 6, 12, 9, 9, 7]))
        for row in d["fights"]:
            r = row["data"]
            print(f"{r['label'][:24]:24}  {r['seconds']:<6.0f}  "
                  f"{r['sunfireUptimePct']:<7.1f}  {r['moonfireUptimePct']:<7.1f}  "
                  f"{r['drops']:<6d}  {r['longestGapSeconds']:<12.1f}  "
                  f"{r['firstCastSeconds']:<9.1f}  "
                  f"{r['dotSecondsPerFightSecond']:<9.2f}  "
                  f"{r['shootingStarsPerMin']:<7.1f}")
        o = d["overall"]
        if o:
            print(f"\n{o['fights']} fights: Sunfire {o['sunfireUptimePct']:.1f}% / "
                  f"Moonfire {o['moonfireUptimePct']:.1f}% on the primary target, "
                  f"{o['drops']} drops over 2s, longest {o['longestGapSeconds']:.0f}s")
            print(f"Shooting Stars procs: {o['shootingStars']} "
                  f"({o['shootingStarsPerMin']:.1f}/min, 2 AP each = "
                  f"{o['shootingStarsAp']:,} AP generated)")
            print("\nRead the longest gap before blaming the player: one long gap and a high")
            print("uptime everywhere else is a phase where the boss was untargetable, not")
            print("sloppy refreshing. Many short drops is the refresh problem.")
            print("'dots avg' is total DoT-seconds / fight-seconds across ALL targets - the")
            print("multi-target spread, not a percentage. It exceeds 2.0 whenever the fight cleaves.")


# ============================================================== spenders

class SpendersCheck(C.Check):
    """Starsurge / Starfall discipline against the APL's spender conditions.

    `starsurge,if=buff.eclipse.down&astral_power.deficit<20|buff.eclipse.up&
    action.starsurge.cost>1|buff.touch_the_cosmos.react|buff.starweavers_weft.react`
    - i.e. spend inside Eclipse, or to avoid overcapping, or because a proc made it
    free. A spender cast with Eclipse down, no proc up, and plenty of Astral Power
    headroom matches none of those branches.
    """
    id = "spenders"
    title = "Spender discipline"
    group = "druid"
    #: Astral Power headroom under which a spender is excused as overcap defence.
    DEFICIT = 20

    def params(self):
        return {"deficitExcuse": self.DEFICIT,
                "procs": {str(g): PROC_NAMES[g] for g in PROC_CONSUMERS}}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        b = self.report.events(f, "Buffs")
        c = _casts(code, f["id"], aid)
        ecl = _eclipse_windows(b)
        procs = {g: T.windows(b, g, default_ms=20000) for g in PROC_CONSUMERS}
        f_in = f_out = f_exc = 0
        ap_at = []
        for e in T.casts(c):
            if e["abilityGameID"] not in SPENDERS:
                continue
            ts = e["timestamp"]
            ap, mx = _ap(e), _ap_max(e)
            if ap is not None:
                ap_at.append(ap)
            if T.in_windows(ecl, ts):
                f_in += 1
            elif (any(T.in_windows(procs[g], ts) for g in FREE_SPENDER_PROCS)
                  or (ap is not None and mx and mx - ap < self.DEFICIT)):
                f_exc += 1
            else:
                f_out += 1

        # proc bookkeeping: gained / consumed / expired
        proc_stat = {}
        for g, consumers in PROC_CONSUMERS.items():
            ev = [e for e in b if e.get("abilityGameID") == g]
            if not ev:
                continue
            s = collections.Counter()
            cts = sorted(e["timestamp"] for e in T.casts(c)
                         if e["abilityGameID"] in consumers)
            for e in ev:
                if e["type"] in ("applybuff", "refreshbuff"):
                    s["gained"] += 1
                    if e["type"] == "refreshbuff":
                        s["overwritten"] += 1
                elif e["type"] == "removebuff":
                    ts = e["timestamp"]
                    key = ("consumed" if any(ts - 1500 <= x <= ts + 250 for x in cts)
                           else "expired")
                    s[key] += 1
            proc_stat[str(g)] = dict(s)
        return {"label": F.fight_label(f), "inEclipse": f_in, "excused": f_exc,
                "offPlan": f_out, "apAtSpend": ap_at, "procs": proc_stat}

    def combine(self, parts):
        inside = sum(d["inEclipse"] for _, d in parts)
        excused = sum(d["excused"] for _, d in parts)
        outside = sum(d["offPlan"] for _, d in parts)
        tot = inside + excused + outside
        ap_at = [x for _, d in parts for x in d["apAtSpend"]]
        # Preserve first-seen proc order across fights so the printed table is
        # stable rather than dict-ordered by whichever pull happened to be first.
        merged = {}
        for _, d in parts:
            for g, s in d["procs"].items():
                acc = merged.setdefault(g, collections.Counter())
                acc.update(s)
        return {
            "spenders": tot,
            "inEclipse": inside, "inEclipsePct": F.pct(inside, tot),
            "excused": excused, "excusedPct": F.pct(excused, tot),
            "offPlan": outside, "offPlanPct": F.pct(outside, tot),
            "apAtSpend": {"mean": statistics.mean(ap_at),
                          "median": statistics.median(ap_at)} if ap_at else None,
            "procs": [{"spellId": int(g), "name": PROC_NAMES[int(g)],
                       "gained": s["gained"], "consumed": s["consumed"],
                       "expired": s["expired"], "overwritten": s["overwritten"],
                       "lostPct": F.pct(s["expired"], s["gained"])}
                      for g, s in merged.items()],
        }

    def print(self):
        d = self.json()
        o = d["overall"]
        if not o["spenders"]:
            print("no Starsurge/Starfall casts found")
            return
        print(F.hdr(["fight", "in Eclipse", "excused", "off-plan"], [24, 11, 8, 9]))
        for row in d["fights"]:
            r = row["data"]
            print(f"{r['label'][:24]:24}  {r['inEclipse']:<11d}  {r['excused']:<8d}  "
                  f"{r['offPlan']:<9d}")
        print(f"\n{o['spenders']} spenders")
        print(f"  cast inside an Eclipse           : {o['inEclipse']}  "
              f"({o['inEclipsePct']:.1f}%)")
        print(f"  excused (proc up, or near cap)   : {o['excused']}  "
              f"({o['excusedPct']:.1f}%)")
        print(f"  off-plan (no Eclipse, no reason) : {o['offPlan']}  "
              f"({o['offPlanPct']:.1f}%)")
        if o["apAtSpend"]:
            print(f"  Astral Power when spending       : "
                  f"mean {o['apAtSpend']['mean']:.1f}  "
                  f"median {o['apAtSpend']['median']:.0f}")
        if o["procs"]:
            print("\n  procs (gained / consumed / expired / re-proc'd while already up):")
            for p in o["procs"]:
                print(f"     {p['name']:<20} {p['gained']:>4} / {p['consumed']:>4} / "
                      f"{p['expired']:>4} / {p['overwritten']:>4}"
                      + (f"   <-- {p['lostPct']:.0f}% lost" if p["expired"] else ""))


# ============================================================== cooldowns

def _ov(wins, x, y):
    """Seconds of `wins` overlapping [x, y]."""
    return sum(max(0, min(y, q) - max(x, p)) for p, q in wins) / 1000.0


class CdsCheck(_RunLevel, C.Check):
    """Cooldown efficiency and Bloodlust alignment for the big buttons.

    Cooldown lengths are MEASURED from the shortest gap this actor actually
    achieved rather than hardcoded, because Whirling Stars / Control of the Dream /
    Orbital Strike all move them and the log does not expose the talent list.
    Alignment is scored as BUFF OVERLAP, not cast-inside-window - a CA pressed one
    second before lust lands is perfectly aligned and a cast test calls it a miss.
    """
    # (guids, label, [(charges, recharge) candidates, most restrictive first])
    # Base values from the live tooltips; the second candidate is the talented one.
    #   Whirling Stars   : CA/Inc -60s cooldown AND two charges
    #   Elune's Guidance : Convoke cooldown -50%
    #   Lunation         : Fury of Elune -1.5s per Arcane cast, so its floor is soft
    id = "cds"
    title = "Cooldown alignment"
    group = "druid"
    #: (guids, label, [(charges, recharge) candidates, most restrictive first])
    TRACKED = [
        (CA_INC, "CA / Incarnation", [(1, 180.0), (2, 120.0)]),
        ({FURY_OF_ELUNE}, "Fury of Elune", [(1, 60.0), (1, 40.0), (1, 25.0)]),
        ({FORCE_OF_NATURE}, "Force of Nature", [(1, 60.0), (1, 45.0)]),
        ({CONVOKE}, "Convoke", [(1, 120.0), (1, 60.0)]),
    ]

    def _cast_times(self):
        """{label: {fight_id: [timestamps]}} for every tracked cooldown."""
        def go():
            code, aid = self.report.code, self.report.actor_id
            out = {}
            for f in self.report.fights:
                c = _casts(code, f["id"], aid)
                for guids, name, _ in self.TRACKED:
                    ts = sorted(e["timestamp"] for e in T.casts(c)
                                if e["abilityGameID"] in guids)
                    out.setdefault(name, {})[f["id"]] = ts
            return out
        return self._memo("cast_times", go)

    def _model(self):
        """The most restrictive cooldown model every observed cast is possible under.

        Run-level, and necessarily so: the identifying evidence is the SHORTEST
        gap the player achieved anywhere in the selection, which no single pull
        contains. The same empirical trick `eclipse` uses for Improved Eclipse -
        a hardcoded base cooldown would score a talented player as impossibly
        efficient.
        """
        def go():
            all_ts = self._cast_times()
            model, rows = {}, []
            for _, name, cands in self.TRACKED:
                ts_by_fight = all_ts.get(name, {})
                casts = sum(len(v) for v in ts_by_fight.values())
                gaps = sorted(g for v in ts_by_fight.values()
                              for g in [(y - x) / 1000.0 for x, y in zip(v, v[1:])])
                if not casts:
                    rows.append({"name": name, "casts": 0, "minGap": None,
                                 "medianGap": None, "note": "not used / not talented",
                                 "charges": None, "recharge": None})
                    continue
                pick = None
                for ch, r in cands:
                    if all(_charge_pool(ts_by_fight[f["id"]], f["startTime"],
                                        f["endTime"], ch, r)[0] == 0
                           for f in self.report.fights):
                        pick = (ch, r)
                        break
                if pick is None:
                    # Cast faster than any fixed cooldown allows -> a talent is
                    # shortening it dynamically (Lunation trims Fury of Elune per
                    # Arcane cast, Control of the Dream banks idle time). There is
                    # no fixed cooldown to score against, so report the rate and
                    # refuse to compute an efficiency.
                    note = f"faster than {cands[-1][1]:.0f}s - dynamically reduced, not scored"
                else:
                    model[name] = pick
                    note = f"{pick[0]} charge(s) @ {pick[1]:.0f}s"
                rows.append({"name": name, "casts": casts,
                             "minGap": gaps[0] if gaps else 0.0,
                             "medianGap": statistics.median(gaps) if gaps else 0.0,
                             "note": note,
                             "charges": pick[0] if pick else None,
                             "recharge": pick[1] if pick else None})
            return model, rows
        return self._memo("model", go)

    def params(self):
        _model, rows = self._model()
        return {"models": rows}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        model, _rows = self._model()
        all_ts = self._cast_times()
        c = _casts(code, f["id"], aid)
        b = self.report.events(f, "Buffs")
        d = F.fight_seconds(f)
        usage = []
        for _guids, name, _ in self.TRACKED:
            ts = all_ts[name][f["id"]]
            if name not in model:
                usage.append({"name": name, "casts": len(ts),
                              "perMin": 60 * len(ts) / d, "scored": False})
                continue
            ch, r = model[name]
            _, idle, _, _ = _charge_pool(ts, f["startTime"], f["endTime"], ch, r)
            usage.append({"name": name, "casts": len(ts), "scored": True,
                          "possible": ch + int(d / r), "idleSeconds": idle,
                          "idlePct": F.pct(idle, d)})

        lust = _merge([w for g in LUST_BUFFS for w in T.windows(b, g, default_ms=40000)])
        lust_block = None
        if lust:
            lu = sum((y - x) / 1000.0 for x, y in lust)
            ca_w = _merge(T.windows(b, CELESTIAL_ALIGNMENT, default_ms=20000) +
                          T.windows(b, INCARNATION, default_ms=25000))
            ecl = _eclipse_windows(b)
            cainc_ts = sorted(e["timestamp"] for e in T.casts(c)
                              if e["abilityGameID"] in CA_INC)
            base = model.get("CA / Incarnation", (1, 180.0))[1]
            per = []
            for i, (x, y) in enumerate(lust, 1):
                cov = F.pct(_ov(ca_w, x, y), (y - x) / 1000.0)
                prior = [t for t in cainc_ts if t < x]
                gap = (x - prior[-1]) / 1000.0 if prior else 9999.0
                if cov >= 25:
                    verdict = f"CA/Inc up for {cov:.0f}% of it"
                elif gap >= base:
                    verdict = f"CA/Inc READY ({gap:.0f}s since last) and not used - MISSED"
                else:
                    verdict = (f"CA/Inc on cooldown - last cast {gap:.0f}s before lust "
                               f"(needs {base:.0f}s)")
                per.append({"n": i, "atSeconds": (x - f["startTime"]) / 1000.0,
                            "coveragePct": cov, "verdict": verdict})
            lust_block = {
                "windows": len(lust), "seconds": lu, "fightPct": F.pct(lu, d),
                "overlap": [{"label": label,
                             "seconds": sum(_ov(wins, x, y) for x, y in lust),
                             "pct": F.pct(sum(_ov(wins, x, y) for x, y in lust), lu)}
                            for label, wins in (("CA / Incarnation", ca_w),
                                                ("any Eclipse", ecl))],
                "perWindow": per,
            }
        return {"label": F.fight_label(f), "seconds": d, "usage": usage,
                "lust": lust_block}

    def print(self):
        d = self.json()
        print(F.hdr(["cooldown", "casts", "min gap", "median gap", "model picked"],
                    [20, 6, 9, 11, 28]))
        for m in d["params"]["models"]:
            if not m["casts"]:
                print(f"{m['name']:20}  {0:<6d}  {'-':<9}  {'-':<11}  {m['note']}")
                continue
            print(f"{m['name']:20}  {m['casts']:<6d}  "
                  f"{m['minGap']:<9.1f}  {m['medianGap']:<11.1f}  {m['note']:<28}")
        print()
        for row in d["fights"]:
            r = row["data"]
            print(f"=== {r['label']}  ({r['seconds']:.0f}s) ===")
            for u in r["usage"]:
                if not u["scored"]:
                    if u["casts"]:
                        print(f"  {u['name']:20} {u['casts']:>2d} cast(s), "
                              f"{u['perMin']:.1f}/min "
                              "- cooldown dynamically reduced, efficiency not scored")
                    continue
                print(f"  {u['name']:20} {u['casts']:>2d}/{u['possible']} used   "
                      f"time at max charges: {u['idleSeconds']:.0f}s "
                      f"({u['idlePct']:.0f}% of fight)")
            lu = r["lust"]
            if not lu:
                print("  Bloodlust/Time Warp: none in this fight\n")
                continue
            print(f"  Bloodlust/Time Warp: {lu['windows']} window(s), {lu['seconds']:.0f}s "
                  f"({lu['fightPct']:.0f}% of the fight)")
            for o in lu["overlap"]:
                print(f"     lust seconds with {o['label']:16} up : "
                      f"{o['seconds']:.0f}/{lu['seconds']:.0f}s ({o['pct']:.0f}%)")
            for w in lu["perWindow"]:
                print(f"       lust #{w['n']} @{w['atSeconds']:.0f}s: {w['verdict']}")
            print()


# ============================================================== APL audit

class AplCheck(_RunLevel, C.Check):
    """Priority-inversion audit: casts that no reachable APL line permits.

    Each rule cites the APL line it comes from. Only rules a log can settle are
    implemented - anything depending on `fight_remains`, `target.time_to_die` or an
    unresolvable talent gate is deliberately left out rather than guessed at, so
    every hit below is a real deviation and the list is not exhaustive.
    """
    id = "apl"
    title = "APL priority audit"
    group = "druid"
    RULES = [
        ("R1", "filler/spender into the boss with its DoT dropped",
         "actions.<list>=sunfire,... / +=/moonfire,... sit above every other line"),
        ("R2", "lower-priority GCD at max Eclipse charges",
         "actions.<list>+=/eclipse,... - only casts BELOW that line are counted"),
        ("R3", "spender with no Eclipse, no proc, no overcap pressure",
         "starsurge,if=buff.eclipse.down&astral_power.deficit<20|buff.eclipse.up&..."),
        ("R4", "filler mismatched with the active Eclipse mode",
         "steering fillers (wrath/starfire) are gated on buff.eclipse.down"),
        ("R5", "free-cast proc left to expire",
         "buff.touch_the_cosmos.react / buff.starweavers_*.react"),
        ("R6", "Astral Power overcapped (in AP, not casts)",
         "spenders are the only sink - starsurge / starfall"),
    ]

    def params(self):
        tree = _combine_tree([(f, {"heroTree": _fight_tree(self.report, f)})
                              for f in self.report.fights])
        return {
            "heroTree": tree,
            "heroTreeName": "Keeper of the Grove" if tree == "keeper" else "Elune's Chosen",
            "list": "kotg_st" if tree == "keeper" else "ec_st",
            "charges": self._charges(),
            "rechargeSeconds": ECLIPSE_RECHARGE,
            "rules": [{"id": r, "what": w, "aplLine": line} for r, w, line in self.RULES],
        }

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        charges = self._charges()
        hits = collections.defaultdict(list)     # rule -> [(fight, offset_s, detail)]
        opp = collections.Counter()              # rule -> chances to break it
        b = self.report.events(f, "Buffs")
        c = _casts(code, f["id"], aid)
        # the fight ID, not just the name: a report has several pulls of one boss and
        # a bare name gives no way to go back to the offending pull with `-f <id>`
        lbl = f"{f['id']}:{F.fight_label(f)}"[:22]
        t0 = f["startTime"]
        ecl_s = T.windows(b, ECL_SOLAR, default_ms=15000)
        ecl_l = T.windows(b, ECL_LUNAR, default_ms=15000)
        ecl = _merge(ecl_s + ecl_l)
        procs = {g: T.windows(b, g, default_ms=20000) for g in PROC_CONSUMERS}

        # R1 judges the PRIMARY target only. In AoE the APL caps Moonfire spread
        # (`active_dots.moonfire<10`) and lets adds' DoTs lapse on purpose, so
        # scoring every target would flag the priority working as designed.
        prim = _primary_target(self.report.events(f, "DamageDone", resources=True))
        prim_dots = {g: _merge([(s, e) for s, e, k in _dot_windows(code, f["id"], aid, g)
                                if k == prim])
                     for g in (SUNFIRE_DOT, MOONFIRE_DOT)}

        ec_ts = sorted(e["timestamp"] for e in T.casts(c)
                       if e["abilityGameID"] in ECLIPSE_CASTS)
        # The opener is exempt from R2: charges start full and cannot have been
        # spent pre-pull, and the APL holds Eclipse behind `variable.opener`
        # anyway. Count only from the first Eclipse press (or 10s in, if never).
        r2_from = ec_ts[0] if ec_ts else t0 + 10000

        def charges_at(ts, _ec=ec_ts, _t0=t0):
            """Fractional Eclipse charges immediately before ts."""
            pool, last = float(charges), _t0
            for t in _ec:
                if t > ts:
                    break
                pool = max(0.0, min(charges, pool + (t - last) / 1000.0 / ECLIPSE_RECHARGE) - 1.0)
                last = t
            return min(charges, pool + (ts - last) / 1000.0 / ECLIPSE_RECHARGE)

        for e in T.casts(c):
            gid, ts = e["abilityGameID"], e["timestamp"]
            if gid not in ROTATIONAL:
                continue
            off = (ts - t0) / 1000.0
            ap, mx = _ap(e), _ap_max(e)
            tgt = (e.get("targetID"), e.get("targetInstance", 1))

            # R1 - the DoT lines outrank everything in every list. The last few
            # seconds are exempt: a DoT lapsing as the boss dies is not an inversion.
            if (gid in SPENDERS or gid in FILLERS) and tgt == prim \
                    and ts < f["endTime"] - 5000:
                opp["R1"] += 1
                for g, tag in ((SUNFIRE_DOT, "Sunfire"), (MOONFIRE_DOT, "Moonfire")):
                    wins = prim_dots[g]
                    # only judge once the DoT has been applied at least once - before
                    # that the target may simply have been out of range
                    if not wins or not any(s < ts for s, _ in wins):
                        continue
                    if not T.in_windows(wins, ts):
                        hits["R1"].append(
                            (lbl, off, f"{NAMES[gid]} into the boss with {tag} down"))
                        break

            # R2 - Eclipse charges capped while a LOWER-priority line took the GCD
            if ts >= r2_from and gid not in ECLIPSE_CASTS and gid not in ABOVE_ECLIPSE:
                opp["R2"] += 1
                if charges_at(ts) >= charges - 1e-6:
                    hits["R2"].append(
                        (lbl, off, f"{NAMES[gid]} at {charges}/{charges} Eclipse charges"))

            # R3 - spender outside Eclipse with no proc and no overcap pressure
            if gid in SPENDERS:
                opp["R3"] += 1
                free = any(T.in_windows(procs[g], ts) for g in FREE_SPENDER_PROCS)
                near_cap = ap is not None and mx and mx - ap < 20
                if not T.in_windows(ecl, ts) and not free and not near_cap:
                    where = f", AP {ap:.0f}/{mx:.0f}" if ap is not None and mx else ""
                    hits["R3"].append(
                        (lbl, off, f"{NAMES[gid]} with no Eclipse and no proc{where}"))

            # R4 - filler mismatched with the active Eclipse mode
            if gid in FILLERS:
                opp["R4"] += 1
                s_up, l_up = T.in_windows(ecl_s, ts), T.in_windows(ecl_l, ts)
                if s_up and not l_up and gid == STARFIRE:
                    hits["R4"].append((lbl, off, "Starfire during Solar-only Eclipse"))
                elif l_up and not s_up and gid == WRATH:
                    hits["R4"].append((lbl, off, "Wrath during Lunar-only Eclipse"))

        # R5 - free-cast procs left to expire
        for g, consumers in PROC_CONSUMERS.items():
            ev = [x for x in b if x.get("abilityGameID") == g]
            if not ev:
                continue
            cts = sorted(x["timestamp"] for x in T.casts(c)
                         if x["abilityGameID"] in consumers)
            for x in ev:
                if x["type"] != "removebuff":
                    continue
                opp["R5"] += 1
                t = x["timestamp"]
                if not any(t - 1500 <= q <= t + 250 for q in cts):
                    hits["R5"].append(
                        (lbl, (t - t0) / 1000.0, f"{PROC_NAMES[g]} expired unused"))

        # R6 - Astral Power thrown away (measured, from the `waste` field)
        for x in self.report.events(f, "Resources", resources=True):
            if x.get("resourceChangeType") != AP_TYPE:
                continue
            opp["R6"] += x.get("resourceChange", 0)
            if x.get("waste"):
                hits["R6"].append(
                    (lbl, (x["timestamp"] - t0) / 1000.0,
                     f"{x['waste']} AP overcapped on "
                     f"{NAMES.get(x.get('abilityGameID'), x.get('abilityGameID'))}",
                     x["waste"]))

        return {
            "heroTree": _fight_tree(self.report, f),
            "hits": {rid: [{"fight": h[0], "atSeconds": h[1], "detail": h[2],
                            "amount": h[3] if len(h) > 3 else None}
                           for h in hits[rid]] for rid, _w, _l in self.RULES},
            "opportunities": {rid: opp[rid] for rid, _w, _l in self.RULES},
        }

    def combine(self, parts):
        hits = {rid: [h for _, d in parts for h in d["hits"][rid]]
                for rid, _w, _l in self.RULES}
        opp = {rid: sum(d["opportunities"][rid] for _, d in parts)
               for rid, _w, _l in self.RULES}
        rows = []
        for rid, what, line in self.RULES:
            # R6 counts Astral Power, not casts: one overcap event can throw away
            # 20 AP and another 2, so a hit count would say nothing.
            n = (sum(h["amount"] or 0 for h in hits[rid]) if rid == "R6"
                 else len(hits[rid]))
            rows.append({"id": rid, "what": what, "aplLine": line, "hits": n,
                         "opportunities": opp[rid],
                         "ratePct": F.pct(n, opp[rid]) if opp[rid] else 0.0})
        return {"heroTree": _combine_tree(parts), "rules": rows, "hits": hits}

    def print(self):
        d = self.json()
        p, o = d["params"], d["overall"]
        print(f"hero tree (inferred from Harmony of the Grove): {p['heroTreeName']}")
        print(f"live single-target list: actions.{p['list']}")
        print(f"Eclipse charge model: {p['charges']} @ {p['rechargeSeconds']:.0f}s\n")
        print(F.hdr(["rule", "what it catches", "hits", "of", "rate%"], [5, 50, 7, 9, 7]))
        for r in o["rules"]:
            print(f"{r['id']:5}  {r['what'][:50]:50}  {r['hits']:<7d}  "
                  f"{r['opportunities']:<9d}  {r['ratePct']:<7.1f}")
        print("\nAPL line each rule comes from:")
        for r in o["rules"]:
            print(f"  {r['id']}  {r['aplLine']}")
        for r in o["rules"]:
            got = o["hits"][r["id"]]
            if not got or r["id"] == "R6":
                continue
            print(f"\n{r['id']} - {r['what']}   ({len(got)} hits, first 10 by fight)")
            for h in sorted(got, key=lambda x: (x["fight"], x["atSeconds"]))[:10]:
                print(f"     {h['fight']:22} @{h['atSeconds']:>6.1f}s  {h['detail']}")
        print("\nDeliberately NOT implemented: every condition needing `fight_remains`,")
        print("`target.time_to_die`, or a talent gate the log cannot resolve. A log cannot")
        print("settle those, so testing them would manufacture findings rather than measure.")


# ============================================================== annotated trace

class RefreshCheck(C.Check):
    """Moonfire/Sunfire re-applied early - measured against the real pandemic rule.

    An earlier version of this check called any refresh under 12s apart "wasted".
    That was wrong twice over, and both errors mattered:

      * The threshold that decides waste is the **pandemic window**, not a flat
        gap. WoW lets a refresh carry over the remaining duration up to 30% of the
        base, so a refresh at <= 5.4s remaining (30% of Moonfire's 18s) loses
        nothing at all. Gap-since-last-cast is not remaining duration, because
        `Aetherial Kindling` has been pushing the expiry out the whole time.
      * Early refreshing turned out to be NORMAL for the spec. The #1 parse on the
        reference fight clips 67% of its refreshes; the player under audit clipped
        70%. Clip *rate* separates nobody - refresh *count* does.

    So this reconstructs the actual remaining duration at every re-application by
    simulating the DoT: base 18s, `Aetherial Kindling` adding 3s per Starfall up
    to a 28s ceiling, and pandemic carry-over on refresh. Applications come from
    Moonfire's DIRECT (non-tick) damage events, not from cast events, because
    `Twin Moons` makes one cast land on two targets and the cast event names only
    one of them.
    """
    id = "refresh"
    title = "DoT refresh timing"
    group = "druid"

    def params(self):
        return {"baseSeconds": DOT_BASE, "pandemicSeconds": 0.3 * DOT_BASE,
                "aetherialExtendSeconds": AETHERIAL_EXTEND,
                "aetherialCapSeconds": AETHERIAL_CAP}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        starfalls = sorted(e["timestamp"] for e in
                           T.casts(W.events(code, f["id"], "Casts", aid,
                                            ability_id=STARFALL)))
        rows = []
        for tag, dot_id, base in (("Moonfire", MOONFIRE_DOT, DOT_BASE),
                                  ("Sunfire", SUNFIRE_DOT, DOT_BASE)):
            pand = 0.3 * base
            applies = sorted(
                ((e["timestamp"], (e.get("targetID"), e.get("targetInstance", 1)))
                 for e in self.report.events(f, "DamageDone", ability_id=dot_id)
                 if not e.get("tick")),
                key=lambda x: x[0])
            evs = ([(t, 1, k) for t, k in applies] +
                   [(t, 0, None) for t in starfalls])          # Starfall first on ties
            evs.sort(key=lambda x: (x[0], x[1]))
            expiry, remain = {}, []
            for ts, kind, key in evs:
                if kind == 0:
                    for tgt, exp in expiry.items():
                        if exp > ts:
                            expiry[tgt] = min(exp + AETHERIAL_EXTEND * 1000,
                                              ts + AETHERIAL_CAP * 1000)
                else:
                    left = max(0.0, (expiry.get(key, 0) - ts) / 1000.0)
                    if key in expiry:
                        remain.append(left)
                    expiry[key] = ts + (base + min(left, pand)) * 1000
            if not remain:
                continue
            clipped = [x for x in remain if x > pand]
            rows.append({
                "dot": tag, "applies": len(applies), "reapplies": len(remain),
                "inPandemic": len(remain) - len(clipped), "clipped": len(clipped),
                "medianRemainingSeconds": statistics.median(remain),
                "durationLostSeconds": sum(x - pand for x in clipped),
                # The distribution, not just its median: a component can histogram
                # it, and the roll-up needs the raw values to re-derive a median.
                "remaining": remain,
            })
        return {"label": F.fight_label(f), "seconds": F.fight_seconds(f), "dots": rows}

    def combine(self, parts):
        pand = 0.3 * DOT_BASE
        merged = {}
        for _, d in parts:
            for r in d["dots"]:
                acc = merged.setdefault(r["dot"], {"dot": r["dot"], "applies": 0,
                                                   "reapplies": 0, "remaining": []})
                acc["applies"] += r["applies"]
                acc["reapplies"] += r["reapplies"]
                acc["remaining"] += r["remaining"]
        out = []
        for r in merged.values():
            clipped = [x for x in r["remaining"] if x > pand]
            out.append({
                "dot": r["dot"], "applies": r["applies"], "reapplies": r["reapplies"],
                "inPandemic": len(r["remaining"]) - len(clipped),
                "clipped": len(clipped),
                "clippedPct": F.pct(len(clipped), len(r["remaining"])),
                "medianRemainingSeconds": (statistics.median(r["remaining"])
                                           if r["remaining"] else None),
                "durationLostSeconds": sum(x - pand for x in clipped),
            })
        return {"dots": out}

    def print(self):
        d = self.json()
        pand = d["params"]["pandemicSeconds"]
        for row in d["fights"]:
            r = row["data"]
            print(f"\n=== {r['label']}  ({r['seconds']:.0f}s) ===")
            print(F.hdr(["dot", "applies", "re-applies", "in pandemic", "clipped",
                         "median left", "duration lost"],
                        [10, 8, 11, 12, 9, 12, 14]))
            for x in r["dots"]:
                print(f"{x['dot']:<10}  {x['applies']:<8d}  {x['reapplies']:<11d}  "
                      f"{x['inPandemic']:<12d}  {x['clipped']:<9d}  "
                      f"{x['medianRemainingSeconds']:<12.1f}  "
                      f"{x['durationLostSeconds']:<14.0f}")
            print(f"\n  Pandemic window is {pand:.1f}s "
                  f"(30% of an {d['params']['baseSeconds']:.0f}s base).")
            print("  A refresh inside it is free; one outside it throws away the excess.")
            print("  Compare `re-applies` against peers BEFORE reading `clipped` - a high")
            print("  clip rate is normal for this spec, a high re-apply count is not.")


class ApGenCheck(C.Check):
    """Astral Power GENERATION per minute, by source, plus the haste that drives it.

    `ApCheck` measures what was wasted; this measures what was made, which is the
    prior question. On the reference log the audited player wasted less AP than
    every peer and still cast the fewest spenders - because generation, not
    overcap, was the binding constraint.

    Why haste is printed here rather than in a gear check: roughly two thirds of
    Balance's Astral Power is haste-scaled. Starfire is ~40% of generation and is a
    hard cast, so haste raises casts per minute directly; Shooting Stars is ~27%
    and procs off Moonfire/Sunfire TICKS, so haste raises it a second time through
    tick rate. A haste deficit therefore compounds into the spender count instead
    of just costing a few GCDs.

    Starfire's measured hardcast time is the haste probe. It is preferred over the
    stat sheet's haste rating (which is not a percentage and understates nothing
    consistently) and over DoT tick interval (which talents also alter). begincast
    and cast are paired SEQUENTIALLY: begincast carries targetID -1 while cast
    carries the real target, so pairing on target silently yields nothing.
    """
    id = "apgen"
    title = "Astral Power generation"
    group = "druid"
    #: Below this a "hardcast" was really an instant proc cast.
    INSTANT_THRESHOLD_S = 0.15

    def params(self):
        return {"instantThresholdSeconds": self.INSTANT_THRESHOLD_S}

    def fight_json(self, f):
        d = F.fight_seconds(f)
        gain = collections.Counter()
        for e in self.report.events(f, "Resources"):
            if e.get("type") != "resourcechange" or e.get("resourceChangeType") != AP_TYPE:
                continue
            amt = (e.get("resourceChange") or 0) - (e.get("waste") or 0)
            if amt > 0:
                gain[e.get("abilityGameID")] += amt
        total = sum(gain.values())
        if not total:
            return {"label": F.fight_label(f), "seconds": d, "generated": 0}

        # begincast and cast are paired SEQUENTIALLY: begincast carries targetID -1
        # while cast carries the real target, so pairing on target yields nothing.
        ev = sorted(self.report.events(f, "Casts", ability_id=STARFIRE),
                    key=lambda x: x["timestamp"])
        times, pend = [], None
        for e in ev:
            if e.get("type") == "begincast":
                pend = e["timestamp"]
            elif e.get("type") == "cast":
                if pend is not None:
                    sec = (e["timestamp"] - pend) / 1000.0
                    if sec > self.INSTANT_THRESHOLD_S:
                        times.append(sec)
                pend = None

        haste_scaled = sum(v for g, v in gain.items()
                           if g in (STARFIRE, WRATH) or g in SHOOTING_STARS_IDS)
        return {
            "label": F.fight_label(f), "seconds": d,
            "generated": total, "perMinute": 60 * total / d,
            "starfireHardcast": {
                "medianSeconds": statistics.median(times), "hardcasts": len(times),
                "instants": len(ev) // 2 - len(times),
            } if times else None,
            "bySource": [{"spellId": g, "name": str(NAMES.get(g, g)), "ap": v,
                          "perMinute": 60 * v / d, "sharePct": F.pct(v, total)}
                         for g, v in gain.most_common()],
            "hasteScaledPct": F.pct(haste_scaled, total),
        }

    def combine(self, parts):
        dur = sum(d["seconds"] for _, d in parts if d["generated"])
        gain = collections.Counter()
        names = {}
        times = []
        for _, d in parts:
            for s in d.get("bySource", []):
                gain[s["spellId"]] += s["ap"]
                names[s["spellId"]] = s["name"]
            hc = d.get("starfireHardcast")
            if hc:
                times.append(hc["medianSeconds"])
        total = sum(gain.values())
        if not total or not dur:
            return None
        haste_scaled = sum(v for g, v in gain.items()
                           if g in (STARFIRE, WRATH) or g in SHOOTING_STARS_IDS)
        return {
            "seconds": dur, "generated": total, "perMinute": 60 * total / dur,
            # Median of per-pull medians: haste changes between pulls (lust,
            # trinkets), so one pooled median would blur two different states.
            "starfireMedianOfMedians": statistics.median(times) if times else None,
            "bySource": [{"spellId": g, "name": names[g], "ap": v,
                          "perMinute": 60 * v / dur, "sharePct": F.pct(v, total)}
                         for g, v in gain.most_common()],
            "hasteScaledPct": F.pct(haste_scaled, total),
        }

    def print(self):
        for row in self.json()["fights"]:
            r = row["data"]
            if not r["generated"]:
                continue
            print(f"\n=== {r['label']}  ({r['seconds']:.0f}s) ===")
            print(f"  Astral Power generated : {r['generated']:,}  ->  "
                  f"{r['perMinute']:,.0f} per minute")
            hc = r["starfireHardcast"]
            if hc:
                print(f"  Starfire hardcast      : median {hc['medianSeconds']:.3f}s  "
                      f"({hc['hardcasts']} hardcasts, {hc['instants']} instant)")
            print()
            print(F.hdr(["source", "AP", "per min", "share"], [26, 8, 9, 7]))
            for s in r["bySource"]:
                print(f"{s['name'][:26]:<26}  {s['ap']:<8,}  {s['perMinute']:<9.0f}  "
                      f"{s['sharePct']:<7.1f}")
            print(f"\n  haste-scaled sources (fillers + Shooting Stars): "
                  f"{r['hasteScaledPct']:.0f}% of generation")
            print("  Compare `per minute` across peers before reading any rotation finding -")
            print("  a spender deficit on top of normal generation is a different problem")
            print("  from a spender deficit caused by generating less in the first place.")


def _charges_at(ecl_ts, ts, charges, recharge):
    """Eclipse button charges available immediately before `ts`, replaying the casts in
    `ecl_ts` against a `charges` @ `recharge`s pool that starts full."""
    ch, nxt = charges, None
    for t in ecl_ts:
        if t >= ts:
            break
        while nxt is not None and nxt <= t:
            ch += 1
            nxt = nxt + recharge * 1000 if ch < charges else None
        if ch == charges:
            nxt = t + recharge * 1000
        ch -= 1
    while nxt is not None and nxt <= ts:
        ch += 1
        nxt = nxt + recharge * 1000 if ch < charges else None
    return ch


def _fury_readiness(casts, base, red):
    """For every Fury of Elune after the first: (cast ts, ready ts or None, held seconds).

    Cooldown `base` seconds, minus `red` seconds for each Lunation-eligible cast while it
    is cooling down. `held` is negative when the model says the cast was impossible.
    """
    out, remaining, clock, ready = [], None, None, None
    for c in casts:
        t, g = c["timestamp"], c["abilityGameID"]
        if remaining is not None and ready is None:
            if remaining - (t - clock) / 1000 <= 0:
                ready, remaining = clock + remaining * 1000, 0.0
            else:
                remaining -= (t - clock) / 1000
            clock = t
        if g == FURY_OF_ELUNE:
            if remaining is not None:
                out.append((t, ready, (t - ready) / 1000 if ready is not None else -remaining))
            remaining, clock, ready = base, t, None
            continue
        if remaining is not None and ready is None and g in LUNATION_CASTS:
            remaining -= red
            if remaining <= 0:
                ready, remaining = t, 0.0
    return out


class FuryCheck(_RunLevel, C.Check):
    """Fury of Elune held after it was ready - and whether the hold bought anything.

    Pairing Fury with an Eclipse is worth a lot (a Fury whose 8s sits in an Eclipse or
    Incarnation did 1.70x the damage of one outside, within-player, 40 Mythic pulls), so
    holding it is sometimes right. It is only right while there is no Eclipse charge to
    pair it with: a hold that starts with a charge available buys nothing and delays
    every later Fury. Those are the FAIL instances here.

    The cooldown is RECONSTRUCTED, not read: `Lunation` takes 1.5s off per Starfire /
    Moonfire / Starsurge / Starfall and `Radiant Moonlight` takes 15s off the base, so
    there is no fixed cooldown. The model is chosen per run as the tightest candidate
    under which no observed Fury was impossible. `45s - 1.5s x those four spells` was
    validated on 562 Furies over 40 top-10% Mythic Lost Explorers pulls: zero casts before
    ready, tightest at 0.0s, and dropping any one of the four spells breaks it
    (.claude/knowledge/classes/druid/balance-druid-12.1.md).

    Reference, same pool (seconds per fight minute): failed holds median 0.81, and 0.00
    for the most consistent 20%; all holds median 4.27. A second of hold costs about
    1/22.5 of a Fury (the median experienced cooldown).
    """

    id = "fury"
    title = "Fury of Elune holds"
    group = "druid"
    #: (base cooldown, Lunation reduction). Tightest zero-violation model wins.
    MODELS = [(60.0, 1.5), (45.0, 1.5), (60.0, 0.0), (45.0, 0.0)]
    GOOD_S, FAIL_S = 1.0, 2.0

    def _model(self):
        def go():
            code, aid = self.report.code, self.report.actor_id
            best = None
            for base, red in self.MODELS:
                bad, slack = 0, 0.0
                for f in self.report.fights:
                    for _, ready, held in _fury_readiness(T.casts(_casts(code, f["id"], aid)), base, red):
                        if held < -0.5:
                            bad += 1
                        else:
                            slack += max(0.0, held)
                if bad == 0 and (best is None or slack < best[2]):
                    best = (base, red, slack)
            return None if best is None else {"base": best[0], "lunation": best[1]}
        return self._memo("fury_model", go)

    def params(self):
        return {"model": self._model(), "eclipseCharges": self._charges(),
                "eclipseRecharge": ECLIPSE_RECHARGE, "failAfterSeconds": self.FAIL_S,
                "poolFailedHoldPerMinMedian": 0.81, "poolTop20FailedHoldPerMin": 0.0}

    def fight_json(self, f):
        m = self._model()
        d = F.fight_seconds(f)
        casts = T.casts(_casts(self.report.code, f["id"], self.report.actor_id))
        furies = [c["timestamp"] for c in casts if c["abilityGameID"] == FURY_OF_ELUNE]
        if m is None:
            return {"label": F.fight_label(f), "seconds": d, "furies": len(furies),
                    "furiesPerMin": 60 * len(furies) / d, "modelFits": False, "instances": []}
        ecl = [c["timestamp"] for c in casts if c["abilityGameID"] in ECLIPSE_CASTS]
        starlord = T.stack_timeline(self.report.events(f, "Buffs"), STARLORD)
        charges = self._charges()
        inst, exp_cd, held_total, failed_total = [], [], 0.0, 0.0
        prev = furies[0] if furies else None
        for t, ready, held in _fury_readiness(casts, m["base"], m["lunation"]):
            held = max(0.0, held)
            ch = _charges_at(ecl, ready, charges, ECLIPSE_RECHARGE) if ready else None
            exp_cd.append((t - prev) / 1000 - held)
            prev = t
            held_total += held
            if held < self.GOOD_S:
                verdict, why = F.PERFECT, f"pressed {held:.1f}s after ready"
            elif held < self.FAIL_S:
                verdict, why = F.GOOD, f"held {held:.1f}s"
            elif ch == 0:
                verdict, why = F.OK, f"held {held:.1f}s waiting for an Eclipse charge"
            else:
                failed_total += held
                verdict, why = F.FAIL, f"held {held:.1f}s with {ch} Eclipse charge(s) ready"
            inst.append(F.instance(F.mmss(t, f["startTime"]), verdict, why, heldSeconds=held,
                                   chargesAtReady=ch, starlordAtReady=T.stacks_at(starlord, ready) if ready else None))
        cd = statistics.median(exp_cd) if exp_cd else None
        return {"label": F.fight_label(f), "seconds": d, "modelFits": True,
                "furies": len(furies), "furiesPerMin": 60 * len(furies) / d,
                "heldSeconds": held_total, "failedHoldSeconds": failed_total,
                "failedHoldPerMin": 60 * failed_total / d, "heldPerMin": 60 * held_total / d,
                "experiencedCooldown": cd,
                "furiesLostToFailedHolds": failed_total / cd if cd else None,
                "instances": inst, "tally": F.tally(inst)}

    def combine(self, parts):
        secs = sum(d["seconds"] for _, d in parts)
        failed = sum(d.get("failedHoldSeconds", 0.0) for _, d in parts)
        held = sum(d.get("heldSeconds", 0.0) for _, d in parts)
        lost = sum(d.get("furiesLostToFailedHolds") or 0.0 for _, d in parts)
        return {"seconds": secs, "furies": sum(d["furies"] for _, d in parts),
                "failedHoldPerMin": 60 * failed / secs if secs else 0.0,
                "heldPerMin": 60 * held / secs if secs else 0.0, "furiesLostToFailedHolds": lost}

    def print(self):
        d = self.json()
        m = d["params"]["model"]
        if m is None:
            print("no cooldown model fits every observed Fury of Elune - not graded")
            return
        print(f"cooldown model: {m['base']:.0f}s base, -{m['lunation']:.1f}s per Starfire/Moonfire/"
              f"Starsurge/Starfall (tightest model with no impossible cast)")
        print(F.hdr(["fight", "dur", "Fury/min", "held s/min", "FAILED s/min", "Furies lost"],
                    [22, 5, 9, 11, 13, 11]))
        for row in d["fights"]:
            r = row["data"]
            if not r.get("modelFits"):
                continue
            print(f"{r['label'][:22]:<22}  {r['seconds']:<5.0f}  {r['furiesPerMin']:<9.2f}  "
                  f"{r['heldPerMin']:<11.2f}  {r['failedHoldPerMin']:<13.2f}  {r['furiesLostToFailedHolds'] or 0:<11.2f}")
        print(f"\n  pool reference (40 top-10% Mythic Lost Explorers pulls): failed holds median "
              f"{d['params']['poolFailedHoldPerMinMedian']:.2f}s/min, most consistent 20% "
              f"{d['params']['poolTop20FailedHoldPerMin']:.2f}s/min")
        for row in d["fights"]:
            r = row["data"]
            if r.get("instances"):
                print()
                F.ledger(f"{r['label']} - Fury of Elune", r["instances"])
        print("\n  FAIL = held 2s+ while an Eclipse charge was already available: the pairing was free,")
        print("  so the hold only delayed this Fury and every one after it. OK = held for a charge.")


class TraceCheck(C.Check):
    """Annotated cast-by-cast trace - the raw material every other check reduces.

    Prints Astral Power, Eclipse mode, apex stacks and live procs beside each
    rotational cast, so a reading of the APL can be checked by eye against what
    actually happened. Capped at the first two fights and `LIMIT` casts each.

    No `combine()`: a trace of fourteen pulls concatenated is not a trace of
    anything. This is the one check whose whole value is per-pull.
    """

    id = "trace"
    title = "Annotated cast trace"
    group = "druid"
    LIMIT = 90
    #: How many pulls to render. The trace is for reading by eye, and past two
    #: pulls nobody does.
    FIGHTS = 2
    WATCH = {TOUCH_THE_COSMOS: "TtC", STARWEAVERS_WARP: "Warp", STARWEAVERS_WEFT: "Weft",
             ASCENDANT_FIRES: "AscFires", UMBRAL_EMBRACE: "Umbral"}

    def params(self):
        return {"castLimit": self.LIMIT, "fightLimit": self.FIGHTS,
                "watched": {str(g): tag for g, tag in self.WATCH.items()}}

    def fight_json(self, f):
        code, aid = self.report.code, self.report.actor_id
        # Only the pulls that will be rendered are computed - the trace is capped
        # at FIGHTS, and building 14 of them to print 2 is pure waste.
        if f["id"] not in [x["id"] for x in self.report.fights[:self.FIGHTS]]:
            return {"label": F.fight_label(f), "seconds": F.fight_seconds(f),
                    "rendered": False, "casts": []}
        b = self.report.events(f, "Buffs")
        c = _casts(code, f["id"], aid)
        t0 = f["startTime"]
        ecl_s = T.windows(b, ECL_SOLAR, default_ms=15000)
        ecl_l = T.windows(b, ECL_LUNAR, default_ms=15000)
        wins = {g: T.windows(b, g, default_ms=20000) for g in self.WATCH}
        stars_tl = _apex_stacks(b)
        rows = []
        for e in T.casts(c):
            gid, ts = e["abilityGameID"], e["timestamp"]
            if gid not in ROTATIONAL:
                continue
            s_up, l_up = T.in_windows(ecl_s, ts), T.in_windows(ecl_l, ts)
            rows.append({
                "atSeconds": (ts - t0) / 1000.0,
                "spellId": gid, "cast": str(NAMES.get(gid, gid)),
                "astralPower": _ap(e),
                "eclipse": ("both" if s_up and l_up else "solar" if s_up
                            else "lunar" if l_up else "-"),
                "apexStacks": T.stacks_at(stars_tl, ts + 1),
                "procs": [tag for g, tag in self.WATCH.items()
                          if T.in_windows(wins[g], ts)],
            })
            if len(rows) >= self.LIMIT:
                break
        return {"label": F.fight_label(f), "seconds": F.fight_seconds(f),
                "rendered": True, "truncated": len(rows) >= self.LIMIT, "casts": rows}

    def print(self):
        d = self.json()
        for row in d["fights"]:
            r = row["data"]
            if not r["rendered"]:
                continue
            print(f"\n=== {r['label']}  ({r['seconds']:.0f}s) ===")
            print(F.hdr(["t", "cast", "AP", "eclipse", "apex", "procs up"],
                        [7, 20, 5, 8, 5, 28]))
            for x in r["casts"]:
                ap = x["astralPower"]
                print(f"{x['atSeconds']:<7.1f}  {x['cast'][:20]:20}  "
                      f"{(f'{ap:.0f}' if ap is not None else '?'):<5}  "
                      f"{x['eclipse']:<8}  {x['apexStacks']:<5d}  "
                      f"{','.join(x['procs'])[:28]:28}")
            if r["truncated"]:
                print(f"     ... truncated at {d['params']['castLimit']} casts")


CHECKS = C.registry(
    EclipseCheck, ApexCheck, ApCheck, DotsCheck, SpendersCheck, CdsCheck,
    AplCheck, RefreshCheck, ApGenCheck, TraceCheck, FuryCheck,
)
