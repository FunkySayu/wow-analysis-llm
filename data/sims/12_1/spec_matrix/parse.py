"""Summarise out/*.json -> one row per (profile, scenario) + burst metrics from the timeline."""
import json, glob, os, sys, statistics as S
rows = {}
for p in sorted(glob.glob("out/*.json")):
    tag, scen = os.path.basename(p)[:-5].split("__")
    try: j = json.load(open(p))
    except Exception: continue
    pl = j["sim"]["players"][0]; cd = pl["collected_data"]
    r = {"dps": cd["dps"]["mean"], "err": cd["dps"]["mean_std_dev"] * 1.96, "pdps": cd.get("prioritydps", {}).get("mean")}
    tl = cd.get("timeline_dmg", {}).get("data")
    if tl and scen in ("fixed300", "len450"):
        n = len(tl); mean = sum(tl) / n
        def best(w): return max(sum(tl[i:i + w]) for i in range(n - w + 1)) / w / mean
        r["peak10"], r["peak20"], r["open20"] = best(10), best(20), sum(tl[:20]) / 20 / mean
        # autocorrelation of the de-meaned timeline -> dominant burst period
        x = [v - mean for v in tl]; var = sum(v * v for v in x)
        ac = {L: sum(x[i] * x[i + L] for i in range(n - L)) / var for L in range(25, min(200, n - 30))}
        L = max(ac, key=ac.get); r["period"], r["ac"] = L, round(ac[L], 2)
        # share of damage in the best 20s of each period-long cycle
        r["tl"] = [round(v) for v in tl]
    rows.setdefault(tag, {})[scen] = r
json.dump(rows, open("summary.json", "w"))
for tag, sc in rows.items():
    b = sc.get("st300", {}).get("dps") or 1
    line = f"{tag:22s} st {b/1000:6.1f}k"
    for s in ("t2", "t3", "t5", "len60", "len120", "len450", "move10", "move20", "adds60", "adds2_90"):
        if s in sc: line += f" {s} {sc[s]['dps']/b:5.2f}"
    f = sc.get("fixed300") or {}
    if "peak10" in f: line += f" | pk10 {f['peak10']:.2f} pk20 {f['peak20']:.2f} open20 {f['open20']:.2f} period {f['period']}s ac {f['ac']}"
    print(line)

# --- vulnerability capture: gain over base380 divided by the gain a perfectly flat profile would get
NEUTRAL = {"digin": 0.3 * 75 / 380, "amp120": 1.0 * 60 / 380, "amp90": 1.0 * 80 / 380}
print("\nvulnerability (gain% / neutral% = capture)")
for tag, sc in rows.items():
    if "base380" not in sc: continue
    b = sc["base380"]["dps"]
    print(f"{tag:22s}", "  ".join(f"{s} +{100*(sc[s]['dps']/b-1):4.1f}%/{100*n:4.1f}% = x{(sc[s]['dps']/b-1)/n:.2f}" for s, n in NEUTRAL.items() if s in sc))
print("\nscale factors (per point, normalised to primary=1)")
for p in sorted(glob.glob("out/*__sw*.json")):
    j = json.load(open(p)); sf = j["sim"]["players"][0].get("scale_factors", {})
    prim = sf.get("Int") or sf.get("Agi") or 1
    print(f"{os.path.basename(p)[:-5]:28s}", {k: round(v / prim, 3) for k, v in sorted(sf.items(), key=lambda kv: -kv[1])}, "raw", {k: round(v, 2) for k, v in sf.items()})
