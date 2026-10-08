"""Output formatting utilities shared by every check."""

import statistics


def pct(n, d):
    return 100.0 * n / d if d else 0.0


def describe(vals):
    if not vals:
        return "n=0"
    v = sorted(vals)
    return (f"n={len(v)} mean={statistics.mean(v):.2f} median={statistics.median(v):.2f} "
            f"p90={v[int(len(v) * .9)]:.2f} max={v[-1]:.2f}")


def hdr(cols, widths):
    line = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    return line + "\n" + "-" * len(line)


def fight_seconds(f):
    return (f["endTime"] - f["startTime"]) / 1000.0


def fight_label(f):
    k = f" +{f['keystoneLevel']}" if f.get("keystoneLevel") else ""
    return f"{f['name']}{k}"


# --- per-instance verdict ledgers --------------------------------------------
# WoWAnalyzer's most useful idea is grading every *instance* of an ability, not
# just the aggregate: "102 Barrages" tells you nothing, "13 of them at 3 Salvo
# with Touch of the Magi still 20s out" tells you what to fix. These helpers
# render that. Verdicts are ordered worst-last so a plain sort surfaces failures.

PERFECT, GOOD, OK, FAIL = "PERFECT", "GOOD", "OK", "FAIL"
VERDICTS = (PERFECT, GOOD, OK, FAIL)
_RANK = {v: i for i, v in enumerate(VERDICTS)}


def mmss(ms, origin=0):
    """Fight-relative m:ss for a WCL absolute timestamp."""
    s = max(0.0, (ms - origin) / 1000.0)
    return f"{int(s // 60)}:{s % 60:04.1f}"


def instance(when, verdict, why, **facts):
    """One graded instance, in the shape a check's `json()` should emit.

    `when` is the fight-relative m:ss label, `facts` the raw numbers the verdict
    was decided on (kept as numbers, not folded into the `why` string, so the
    presentation layer can chart or filter on them).
    """
    return {"when": when, "verdict": verdict, "why": why, "facts": facts}


def tally(instances):
    """{verdict: count} over ledger instances, always with every verdict key."""
    return {v: sum(1 for r in instances if _verdict(r) == v) for v in VERDICTS}


def _row(r):
    """Accept either a (label, verdict, detail) tuple or an `instance()` dict."""
    if isinstance(r, dict):
        return r["when"], r["verdict"], r["why"]
    return r


def _verdict(r):
    return r["verdict"] if isinstance(r, dict) else r[1]


def ledger(title, rows, limit=12):
    """Print a graded per-instance table.

    `rows` is [(label, verdict, detail)] or a list of `instance()` dicts - the
    latter is what a ported check passes straight from its JSON payload, so the
    text and the component render the exact same instances.

    Prints the verdict tally first - that is the number worth quoting - then the
    individual instances that were not clean, worst first, because those are the
    only ones that carry an action.
    """
    rows = [_row(r) for r in rows]
    if not rows:
        print(f"{title}: no instances found")
        return
    tally = {v: sum(1 for r in rows if r[1] == v) for v in VERDICTS}
    line = " / ".join(f"{tally[v]} {v}" for v in VERDICTS if tally[v])
    print(f"{title}: {len(rows)} instances   {line}")
    bad = [r for r in rows if r[1] in (OK, FAIL)]
    if not bad:
        print("   every instance graded GOOD or better")
        return
    bad.sort(key=lambda r: (-_RANK[r[1]], r[0]))
    print(f"   {'when':>7}  {'verdict':<7}  why")
    for label, verdict, detail in bad[:limit]:
        print(f"   {label:>7}  {verdict:<7}  {detail}")
    if len(bad) > limit:
        print(f"   ... and {len(bad) - limit} more")


def bands(pairs, total, width=40):
    """Horizontal histogram. `pairs` is [(label, value)]; value shares `total`."""
    for label, v in pairs:
        share = pct(v, total)
        print(f"   {label:>9}  {share:>5.1f}%  {v:>7.1f}s  "
              f"{'#' * int(round(share * width / 100.0))}")
