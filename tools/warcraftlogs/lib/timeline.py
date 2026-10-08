"""Generic timeline utilities for WCL event streams.

Spec-agnostic: everything here operates on raw event dicts (timestamp,
abilityGameID, type, stack) and takes the spell/aura ID as a parameter,
so it works the same for any class/spec.
"""


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


# --- resources ---------------------------------------------------------------

def resource_at(event, rtype):
    """(amount, max) for a class resource on an event, or (None, None).

    Only present when the events were fetched with `resources=True`; without it
    `classResources` is simply absent and every reading comes back None with no
    error. Note WCL scales some resources (Astral Power is stored x10) - that
    correction belongs in the spec check, not here.
    """
    for r in event.get("classResources") or []:
        if r.get("type") == rtype:
            return r.get("amount"), r.get("max")
    return None, None


def gains(resource_events, rtype):
    """[(ts, amount, waste, abilityGameID)] from `Resources` resourcechange events.

    Some resources are never logged as an aura - Arcane Charges have no buff
    events at all on this build - so an energize stream is the only way to
    reconstruct the pool. `waste` is the part of the gain that overcapped.
    """
    out = []
    for e in resource_events:
        if e.get("type") != "resourcechange" or e.get("resourceChangeType") != rtype:
            continue
        out.append((e["timestamp"], e.get("resourceChange", 0) or 0,
                    e.get("waste", 0) or 0, e.get("abilityGameID")))
    out.sort(key=lambda x: x[0])
    return out


def targets_hit(damage_events, start, end):
    """Distinct enemies damaged in [start, end]. Instances matter: two adds of the
    same NPC share a targetID and differ only by targetInstance."""
    return len({(e.get("targetID"), e.get("targetInstance"))
                for e in damage_events if start <= e["timestamp"] <= end})
