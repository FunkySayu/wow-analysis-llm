"""Arcane Mage spell IDs and shared timeline helpers.

Every ID here was confirmed against real log data, not from memory. The ones that
bite are called out — see .claude/knowledge/arcane-mage-12.1-ptr.md.
"""

import statistics

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


# ----------------------------------------------------------------- timelines

def stack_timeline(buff_events, guid):
    """[(ts, stacks_after)] for a stacking aura, sorted by time."""
    tl = []
    for e in buff_events:
        if e.get("abilityGameID") != guid:
            continue
        t = e["type"]
        if t == "applybuff":
            tl.append((e["timestamp"], 1))
        elif t in ("applybuffstack", "removebuffstack"):
            tl.append((e["timestamp"], e.get("stack", 0)))
        elif t == "removebuff":
            tl.append((e["timestamp"], 0))
    tl.sort(key=lambda x: x[0])
    return tl


def stacks_at(tl, ts):
    """Stacks in effect immediately BEFORE ts."""
    cur = 0
    for t, s in tl:
        if t >= ts:
            break
        cur = s
    return cur


def windows(events_, guid, apply_types=("applybuff", "refreshbuff"),
            remove_types=("removebuff",), default_ms=None):
    """[(start, end)] for an aura. `default_ms` closes a window left open at log end."""
    out, start = [], None
    for e in sorted(events_, key=lambda x: x["timestamp"]):
        if e.get("abilityGameID") != guid:
            continue
        if e["type"] in apply_types:
            if start is None:
                start = e["timestamp"]
        elif e["type"] in remove_types and start is not None:
            out.append((start, e["timestamp"]))
            start = None
    if start is not None:
        out.append((start, start + (default_ms or 0)))
    return out


def in_windows(wins, ts):
    return any(a <= ts <= b for a, b in wins)


def casts(cast_events, guid=None):
    cs = [e for e in cast_events if e["type"] == "cast"]
    if guid is not None:
        cs = [e for e in cs if e["abilityGameID"] == guid]
    return sorted(cs, key=lambda x: x["timestamp"])


def segments(timestamps, gap_ms):
    """Split sorted timestamps into clusters separated by > gap_ms. Yields (start, end, n)."""
    if not timestamps:
        return []
    ts = sorted(timestamps)
    out, s, prev, n = [], ts[0], ts[0], 1
    for t in ts[1:]:
        if t - prev > gap_ms:
            out.append((s, prev, n))
            s, n = t, 0
        prev, n = t, n + 1
    out.append((s, prev, n))
    return out


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def describe(vals):
    if not vals:
        return "n=0"
    v = sorted(vals)
    return (f"n={len(v)} mean={statistics.mean(v):.2f} median={statistics.median(v):.2f} "
            f"p90={v[int(len(v) * .9)]:.2f} max={v[-1]:.2f}")
