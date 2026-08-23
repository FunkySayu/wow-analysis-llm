"""Per-check analyses. Each `check_*` takes (code, actor_id, fights) and prints a report.

Add a new check by writing `check_<name>` and registering it in run.py's CHECKS map.
"""

import collections
import statistics

import arcane as A
import wclapi as W


def _dur(f):
    return (f["endTime"] - f["startTime"]) / 1000.0


def _label(f):
    k = f" +{f['keystoneLevel']}" if f.get("keystoneLevel") else ""
    return f"{f['name']}{k}"


def _hdr(cols, widths):
    line = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    return line + "\n" + "-" * len(line)


# ============================================================== salvo cycle

def check_salvo(code, aid, fights):
    """Arcane Salvo spent per Barrage, share at max stacks, time overcapped."""
    print(_hdr(["fight", "dur", "Barr", "avgSalvo", "at25", "<20", "capped%", "AM>=12%"],
               [26, 6, 5, 9, 7, 7, 8, 8]))
    agg = []
    for f in fights:
        b = W.events(code, f["id"], "Buffs", aid)
        c = W.events(code, f["id"], "Casts", aid)
        tl = A.stack_timeline(b, A.SALVO)
        soul = A.windows(b, A.ARCANE_SOUL, default_ms=4000)
        barr = [(e["timestamp"], A.stacks_at(tl, e["timestamp"] + 1))
                for e in A.casts(c, A.BARRAGE)]
        ns = [s for t, s in barr if not A.in_windows(soul, t)]
        mis = [A.stacks_at(tl, e["timestamp"] + 1) for e in A.casts(c, A.MISSILES)]
        capped, pt, ps = 0.0, None, 0
        for t, s in tl:
            if pt is not None and ps >= 25:
                capped += (t - pt) / 1000.0
            pt, ps = t, s
        d = _dur(f)
        if not ns:
            continue
        row = (_label(f)[:26], d, len(ns), statistics.mean(ns),
               A.pct(sum(1 for s in ns if s >= 25), len(ns)),
               A.pct(sum(1 for s in ns if s < 20), len(ns)),
               A.pct(capped, d), A.pct(sum(1 for s in mis if s >= 12), len(mis)))
        agg.append(row)
        print(f"{row[0]:26}  {row[1]:<6.0f}  {row[2]:<5d}  {row[3]:<9.1f}  "
              f"{row[4]:<7.1f}  {row[5]:<7.1f}  {row[6]:<8.1f}  {row[7]:<8.1f}")
    if agg:
        n = sum(r[2] for r in agg)
        print(f"\n{len(agg)} fights, {n} non-Soul Barrages, "
              f"weighted avg Salvo {sum(r[3] * r[2] for r in agg) / n:.1f}, "
              f"at max {sum(r[4] * r[2] for r in agg) / n:.1f}%")
    print("\nBenchmark: simc spends 22.4 Salvo/Barrage with 65% at max stacks.")


# ============================================================== arcane soul

def check_soul(code, aid, fights):
    """Arcane Soul window setup: Soul lands 17.4s after Surge and Barrages inside
    it do NOT consume Salvo, so entry stacks are the whole value of the window."""
    lags, predump, entry, nbarr, ends = [], [], [], [], 0
    for f in fights:
        b = W.events(code, f["id"], "Buffs", aid)
        c = W.events(code, f["id"], "Casts", aid)
        tl = A.stack_timeline(b, A.SALVO)
        surge = [e["timestamp"] for e in b
                 if e.get("abilityGameID") == A.SURGE_BUFF and e["type"] == "applybuff"]
        soul = A.windows(b, A.ARCANE_SOUL, default_ms=4000)
        barr = [e["timestamp"] for e in A.casts(c, A.BARRAGE)]
        for s, e in soul:
            pr = [x for x in surge if x < s]
            if pr:
                lags.append((s - pr[-1]) / 1000.0)
            pb = [x for x in barr if x < s]
            if pb:
                predump.append((s - pb[-1]) / 1000.0)
            entry.append(A.stacks_at(tl, s))
            nbarr.append(sum(1 for x in barr if s <= x <= e))
            ends += 1
    if not entry:
        print("no Arcane Soul windows found")
        return
    print(f"Arcane Soul windows: {ends}")
    print(f"  Arcane Surge -> Soul lag      : median {statistics.median(lags):.1f}s  "
          f"(n={len(lags)}, spread p10-p90 "
          f"{sorted(lags)[len(lags)//10]:.1f}-{sorted(lags)[int(len(lags)*.9)]:.1f}s)")
    print(f"  Salvo on entry                : mean {statistics.mean(entry):.1f} / 25   "
          f"median {statistics.median(entry):.0f}   min {min(entry)}   max {max(entry)}")
    print(f"     entered at 25 (Intuition)  : {A.pct(sum(1 for x in entry if x >= 25), len(entry)):.0f}%")
    print(f"     entered below 15           : {A.pct(sum(1 for x in entry if x < 15), len(entry)):.0f}%")
    print(f"  Barrage fired <3s before Soul : "
          f"{A.pct(sum(1 for x in predump if x < 3), len(predump)):.0f}%  "
          f"(median gap {statistics.median(predump):.1f}s)   <-- dumping the window")
    print(f"  Barrages inside the window    : mean {statistics.mean(nbarr):.1f}")
    print("\nFix: Soul is on a clock. After Arcane Surge, count ~17s and bank Salvo to 25\n"
          "rather than spending it in the last GCDs before the window opens.")


# ============================================================== clearcasting

def check_clearcasting(code, aid, fights):
    """Clearcasting capped at 3 = procs thrown away. High Salvo blocks Missiles
    (APL gate arcane_salvo.stack<12), which is what causes the cap."""
    capped_s = wasted = total_s = 0.0
    for f in fights:
        b = sorted(W.events(code, f["id"], "Buffs", aid), key=lambda x: x["timestamp"])
        st, last = 0, None
        for e in b:
            if e.get("abilityGameID") != A.CLEARCASTING:
                continue
            t = e["timestamp"]
            if last is not None and st >= 3:
                capped_s += (t - last) / 1000.0
            ty = e["type"]
            if ty == "applybuff":
                st = 1
            elif ty in ("applybuffstack", "removebuffstack"):
                st = e.get("stack", 0)
            elif ty == "refreshbuff":
                if st >= 3:
                    wasted += 1
            elif ty == "removebuff":
                st = 0
            last = t
        total_s += _dur(f)
    print(f"across {len(fights)} fights / {total_s:.0f}s")
    print(f"  time at 3/3 Clearcasting : {capped_s:.0f}s  ({A.pct(capped_s, total_s):.1f}% of combat)")
    print(f"  procs onto a full buff   : {int(wasted)}  (hard-wasted, ~1 free Missiles each)")
    print("\nRelease valve: the APL allows Barrage at Salvo>=12 WHEN Clearcasting is banked,\n"
          "specifically to unblock Missiles. That is the one case where an early dump is right.")


# ============================================ NEW: Touch of the Magi targeting

def check_tom_target(code, aid, fights):
    """How much of the Touch of the Magi window is spent hitting something else.

    ToM stores a share of damage dealt TO THE DEBUFFED TARGET and detonates at the
    end. Damage into any other target during the window does not feed the explosion,
    so time off the ToM'd target is the direct loss.
    """
    tot_win = 0
    dmg_on = dmg_off = 0
    off_time = on_time = 0.0
    per_fight = []
    small_target = []
    worst = []          # (on_pct, fight, target name, target maxHP)
    misplaced = []      # windows where a clearly bigger target was being hit anyway
    names = W.actor_names(code)
    SLICE = 500  # ms

    for f in fights:
        deb = W.events(code, f["id"], "Debuffs", aid, ability_id=A.TOTM_DEBUFF)
        dmg = W.events(code, f["id"], "DamageDone", aid, resources=True)
        if not deb:
            continue
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

        f_on = f_off = 0
        f_offt = f_ont = 0.0
        for s, e, key in wins:
            tot_win += 1
            ev = [x for x in dmg if s <= x["timestamp"] <= e]
            on = sum(x.get("amount", 0) + x.get("absorbed", 0)
                     for x in ev if (x.get("targetID"), x.get("targetInstance", 1)) == key)
            off = sum(x.get("amount", 0) + x.get("absorbed", 0) for x in ev) - on
            f_on += on
            f_off += off
            # time slices: a slice counts as "off" if damage happened but none on the ToM target
            buckets = collections.defaultdict(lambda: [0, 0])
            for x in ev:
                b = (x["timestamp"] - s) // SLICE
                hit_on = (x.get("targetID"), x.get("targetInstance", 1)) == key
                buckets[b][0 if hit_on else 1] += x.get("amount", 0)
            for b, (o, u) in buckets.items():
                if o > 0:
                    f_ont += SLICE / 1000.0
                elif u > 0:
                    f_offt += SLICE / 1000.0
            hp = maxhp.get(key, 0)
            if hp:
                small_target.append(hp)
            # was a bigger target being hit during this same window?
            present = {}
            for x in ev:
                k2 = (x.get("targetID"), x.get("targetInstance", 1))
                if x.get("maxHitPoints"):
                    present[k2] = max(present.get(k2, 0), x["maxHitPoints"])
            if present:
                best_k = max(present, key=lambda k2: present[k2])
                if present[best_k] > hp * 1.5:
                    misplaced.append((_label(f)[:22], names.get(key[0], "?"), hp,
                                      names.get(best_k[0], "?"), present[best_k]))
            if on + off:
                worst.append((A.pct(on, on + off), _label(f)[:22],
                              names.get(key[0], f"#{key[0]}"), hp))
        dmg_on += f_on
        dmg_off += f_off
        off_time += f_offt
        on_time += f_ont
        if f_on + f_off:
            per_fight.append((_label(f)[:26], len(wins), A.pct(f_on, f_on + f_off), f_offt))

    if not tot_win:
        print("no Touch of the Magi debuff windows found")
        return

    print(_hdr(["fight", "ToM", "dmg on target", "off-target s"], [26, 5, 14, 12]))
    for n, w, p, ot in per_fight:
        print(f"{n:26}  {w:<5d}  {p:<14.1f}  {ot:<12.1f}")

    tot = dmg_on + dmg_off
    print(f"\n{tot_win} Touch of the Magi windows")
    print(f"  damage into the ToM'd target : {A.pct(dmg_on, tot):.1f}%  ({dmg_on:,.0f})")
    print(f"  damage into anything else    : {A.pct(dmg_off, tot):.1f}%  ({dmg_off:,.0f})")
    print(f"  active time on the target    : {on_time:.0f}s")
    print(f"  active time OFF the target   : {off_time:.0f}s  "
          f"({A.pct(off_time, on_time + off_time):.1f}% of damaging time in window)")
    if small_target:
        med = statistics.median(small_target)
        print(f"  ToM'd target max HP          : median {med:,.0f}   "
              f"min {min(small_target):,.0f}   max {max(small_target):,.0f}")
        low = [w for w in worst if w[3] and w[3] < med / 4]
        if low:
            print(f"\n  {len(low)} window(s) placed on a target under a quarter of the median HP "
                  "- likely a trash add rather than the priority target:")
            for p, fl, tn, hp in sorted(low)[:10]:
                print(f"     {fl:22} -> {tn[:26]:26} maxHP {hp:>13,.0f}   on-target {p:.0f}%")
    print(f"\n  Placement: {len(misplaced)}/{tot_win} window(s) "
          f"({A.pct(len(misplaced), tot_win):.0f}%) put ToM on a target while something with "
          ">1.5x its HP\n             was being damaged in the same window "
          "(0% = always on the biggest thing you were hitting).")
    for fl, tn, hp, bn, bhp in misplaced[:8]:
        print(f"     {fl:22} ToM on {tn[:20]:20} ({hp:>12,.0f})  "
              f"while hitting {bn[:20]:20} ({bhp:>12,.0f})")
    if worst:
        print("\n  Worst windows by share of damage that actually fed the explosion:")
        for p, fl, tn, hp in sorted(worst)[:10]:
            print(f"     {p:>5.1f}%  {fl:22} -> {tn[:26]:26} maxHP {hp:>13,.0f}")


# ==================================================== NEW: cooldown alignment

def _pulls(code, fid, aid, gap_s=12):
    """Segment a fight into pulls from the player's own damage, and describe each
    pull's size (distinct enemies), effective HP (sum of enemy maxHitPoints) and
    danger (damage taken by friendlies during it)."""
    dmg = W.events(code, fid, "DamageDone", aid, resources=True)
    if not dmg:
        return []
    segs = A.segments([e["timestamp"] for e in dmg], gap_s * 1000)
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


def check_cooldowns(code, aid, fights):
    """Are the big cooldowns landing on the moments that matter?

    Three questions: do they line up with Bloodlust, do they land on the biggest /
    most dangerous packs, and how much cooldown time is left banked."""
    for f in fights:
        c = W.events(code, f["id"], "Casts", aid)
        b = W.events(code, f["id"], "Buffs", aid)
        d = _dur(f)
        surge = [e["timestamp"] for e in A.casts(c, A.SURGE)]
        totm = [e["timestamp"] for e in A.casts(c, A.TOTM)]
        lust = []
        for g in A.LUST_BUFFS:
            lust += A.windows(b, g, default_ms=40000)
        lust.sort()

        print(f"\n=== {_label(f)}  ({d:.0f}s) ===")

        # --- 1. availability / banked cooldown time
        for gid, name in ((A.SURGE, "Arcane Surge"), (A.TOTM, "Touch of the Magi")):
            ts = surge if gid == A.SURGE else totm
            cd = A.CD_SECONDS[gid]
            poss = 1 + int(d // cd)
            banked = 0.0
            prev = f["startTime"]
            for t in ts:
                banked += max(0.0, (t - prev) / 1000.0 - cd)
                prev = t
            banked += max(0.0, (f["endTime"] - prev) / 1000.0 - cd)
            print(f"  {name:18} {len(ts):>2d}/{poss} used ({A.pct(len(ts), poss):3.0f}%)   "
                  f"cooldown left idle: {banked:.0f}s ({A.pct(banked, d):.0f}% of fight)")

        # --- 2. Bloodlust alignment
        # Measure BUFF OVERLAP, not "was the cast inside the window" - a Surge cast one
        # second before lust lands is perfectly aligned, and a cast-based test calls it random.
        if lust:
            lu = sum((b_ - a) / 1000.0 for a, b_ in lust)
            sw = A.windows(b, A.SURGE_BUFF, default_ms=20000)
            deb = W.events(code, f["id"], "Debuffs", aid, ability_id=A.TOTM_DEBUFF)
            tw = A.windows(deb, A.TOTM_DEBUFF, apply_types=("applydebuff", "refreshdebuff"),
                           remove_types=("removedebuff",), default_ms=12000)

            def overlap(wins, a, b_):
                return sum(max(0, min(b_, y) - max(a, x)) for x, y in wins) / 1000.0

            s_ov = sum(overlap(sw, a, b_) for a, b_ in lust)
            t_ov = sum(overlap(tw, a, b_) for a, b_ in lust)
            print(f"  Bloodlust/Time Warp: {len(lust)} window(s), {lu:.0f}s "
                  f"({A.pct(lu, d):.0f}% of the fight)")
            print(f"     lust seconds with Arcane Surge up      : {s_ov:.0f}/{lu:.0f}s "
                  f"({A.pct(s_ov, lu):.0f}%)   [ceiling ~"
                  f"{A.pct(18.0 * len(lust), lu):.0f}%: Surge lasts ~18s per 40s lust]")
            print(f"     lust seconds with Touch of the Magi up : {t_ov:.0f}/{lu:.0f}s "
                  f"({A.pct(t_ov, lu):.0f}%)")
            for i, (a, b_) in enumerate(lust, 1):
                cov = A.pct(overlap(sw, a, b_), (b_ - a) / 1000.0)
                prior = [t for t in surge if t < a]
                gap = (a - prior[-1]) / 1000.0 if prior else 999
                if cov >= 25:
                    verdict = f"Surge up for {cov:.0f}% of it"
                elif gap >= A.CD_SECONDS[A.SURGE]:
                    verdict = f"Surge READY ({gap:.0f}s since last) and not used - MISSED"
                else:
                    verdict = (f"Surge on cooldown - last cast {gap:.0f}s before lust "
                               f"(needs {A.CD_SECONDS[A.SURGE]:.0f}s); bank it next time")
                print(f"       lust #{i} @{(a - f['startTime']) / 1000:.0f}s: {verdict}")
        else:
            print("  Bloodlust/Time Warp: none in this fight")

        # --- 3. pack coverage: did the big/dangerous packs get the cooldown?
        pl = _pulls(code, f["id"], aid)
        pl = [p for p in pl if p["dur"] >= 5 and p["packhp"] > 0]
        if len(pl) < 3:
            continue
        for p in pl:
            p["surge"] = any(p["start"] <= t <= p["end"] for t in surge)
            p["totm"] = sum(1 for t in totm if p["start"] <= t <= p["end"])
            # was Arcane Surge off cooldown when the pull started?
            prior = [t for t in surge if t < p["start"]]
            p["ready"] = (not prior) or (p["start"] - prior[-1]) / 1000.0 >= A.CD_SECONDS[A.SURGE]
        by_hp = sorted(pl, key=lambda p: -p["packhp"])
        n_top = max(3, len(pl) // 4)
        top = by_hp[:n_top]
        rest = by_hp[n_top:]
        missed = [p for p in pl if p["ready"] and not p["surge"]]

        print(f"  Pulls: {len(pl)}   (pack HP = sum of enemy max HP; danger = party damage taken)")
        print(f"     Surge on a top-quartile pull : {sum(1 for p in top if p['surge'])}/{len(top)}"
              f"     on the rest: {sum(1 for p in rest if p['surge'])}/{len(rest)}")
        print(f"     Pulls where Surge was READY but unused: {len(missed)}"
              + (f"  (biggest: {max(p['packhp'] for p in missed):,.0f} pack HP)" if missed else ""))
        print(f"     {'#':>3} {'dur':>5} {'foes':>5} {'pack HP':>13} {'danger':>13} "
              f"{'Surge':>6} {'rdy':>4} {'ToM':>4}")
        for i, p in enumerate(by_hp[:8], 1):
            flag = "YES" if p["surge"] else ("MISS" if p["ready"] else "cd")
            print(f"     {i:>3} {p['dur']:>5.0f} {p['enemies']:>5d} {p['packhp']:>13,.0f} "
                  f"{p['taken']:>13,.0f} {flag:>6} {'Y' if p['ready'] else '-':>4} {p['totm']:>4d}")
        # danger-ranked view: the packs that actually hurt
        by_dmg = sorted(pl, key=lambda p: -p["taken"])[:3]
        print("     most dangerous packs (by party damage taken):")
        for p in by_dmg:
            print(f"        {p['taken']:>13,.0f} taken, {p['enemies']:>2d} foes, "
                  f"{p['packhp']:>13,.0f} HP  ->  Surge {'YES' if p['surge'] else 'no '}, "
                  f"ToM x{p['totm']}")


# ============================================================== missiles waves

def check_waves(code, aid, fights):
    """Waves per Arcane Missiles channel. Base 7; the Season 2 2pc makes it 8.

    Read the MODE, not the mean - multi-target channels stack whole multiples
    (7/14/21/42 vs 8/16/24/32)."""
    ts = []
    for f in fights:
        ts += [e["timestamp"] for e in
               W.events(code, f["id"], "DamageDone", aid, ability_id=A.MISSILES_IMPACT)]
    if not ts:
        print("no Arcane Missiles impacts (ability 7268) found")
        return
    ch = [n for _, _, n in A.segments(ts, 700) if n >= 3]
    h = collections.Counter(ch)
    print(f"channels: {len(ch)}   mean {statistics.mean(ch):.2f}   median {statistics.median(ch)}")
    print("wave-count histogram (top 12):")
    for k, v in sorted(h.items(), key=lambda x: -x[1])[:12]:
        print(f"   {k:>3d} waves : {'#' * min(60, v)} {v}")
    base = min((k for k, v in h.items() if v >= max(h.values()) * .25), default=0)
    print(f"\nlowest strong mode = {base} waves  ->  "
          f"{'2-piece PRESENT (8)' if base >= 8 else '2-piece ABSENT (7)' if base == 7 else 'inconclusive'}")


# ============================================================== channel gaps

def check_gaps(code, aid, fights):
    """Dead time after an Arcane Missiles channel ends (channel end = last Salvo tick)."""
    hes = []
    total = 0.0
    for f in fights:
        c = W.events(code, f["id"], "Casts", aid)
        b = W.events(code, f["id"], "Buffs", aid)
        sal = sorted(e["timestamp"] for e in b if e.get("abilityGameID") == A.SALVO
                     and e["type"] in ("applybuff", "applybuffstack"))
        dm = [e for e in A.casts(c) if e["abilityGameID"] in A.DAMAGING_CASTS]
        for i, e in enumerate(dm[:-1]):
            if e["abilityGameID"] != A.MISSILES:
                continue
            nxt = dm[i + 1]["timestamp"]
            tk = [t for t in sal if e["timestamp"] < t <= min(nxt, e["timestamp"] + 7000)]
            if len(tk) >= 2:
                hes.append((nxt - tk[-1]) / 1000.0)
        total += _dur(f)
    if not hes:
        print("no channels measured")
        return
    h = sorted(hes)
    print(f"channels measured: {len(h)}")
    print(f"  median delay after channel : {statistics.median(h):.2f}s")
    for th in (0.5, 1.0, 2.0):
        print(f"  over {th:.1f}s                  : {A.pct(sum(1 for x in h if x > th), len(h)):.0f}%")
    print(f"  total dead time            : {sum(h):.0f}s of {total:.0f}s ({A.pct(sum(h), total):.1f}%)")


# ============================================================== gear audit

def check_gear(code, aid, fights):
    """Enchants, gems and secondaries for every player in the report - the control
    test that separates 'this player has none' from 'the log does not record them'."""
    fid = fights[0]["id"]
    ev = W.events(code, fid, "CombatantInfo")
    names = W.actor_names(code)
    print(_hdr(["player", "ilvl", "ench", "gems", "Int", "secondaries", "sets"],
               [22, 6, 5, 5, 6, 12, 18]))
    for e in sorted(ev, key=lambda x: -(x.get("intellect") or 0)):
        worn = [g for g in (e.get("gear") or []) if g.get("id")]
        if not worn:
            continue
        sets = collections.Counter(g["setID"] for g in worn if g.get("setID"))
        sec = sum(e.get(k, 0) for k in
                  ("critSpell", "hasteSpell", "mastery", "versatilityDamageDone"))
        mark = "  <== " if e.get("sourceID") == aid else ""
        print(f"{names.get(e.get('sourceID'), '?')[:22]:22}  "
              f"{sum(g['itemLevel'] for g in worn) / len(worn):<6.1f}  "
              f"{sum(1 for g in worn if g.get('permanentEnchant')):<5d}  "
              f"{sum(len(g.get('gems') or []) for g in worn):<5d}  "
              f"{e.get('intellect', 0):<6d}  {sec:<12d}  {str(dict(sets))[:18]:18}{mark}")
    print("\nStandard for Arcane: 8 enchants (head/shoulders/chest/legs/feet/2 rings/weapon)\n"
          "and 7 gem sockets. A weapon rune is a temporaryEnchant and is counted separately.")


# ============================================================== cooldown usage

def check_cd_usage(code, aid, fights):
    """Raw cooldown efficiency: casts vs the theoretical maximum for the fight length."""
    print(_hdr(["fight", "dur", "ToM", "poss", "eff", "Surge", "poss", "eff"],
               [26, 6, 4, 5, 6, 6, 5, 6]))
    tot = [0, 0, 0, 0]
    for f in fights:
        c = W.events(code, f["id"], "Casts", aid)
        d = _dur(f)
        r = []
        for gid in (A.TOTM, A.SURGE):
            n = len(A.casts(c, gid))
            poss = 1 + int(d // A.CD_SECONDS[gid])
            r += [n, poss]
        tot = [tot[i] + r[i] for i in range(4)]
        print(f"{_label(f)[:26]:26}  {d:<6.0f}  {r[0]:<4d}  {r[1]:<5d}  "
              f"{A.pct(r[0], r[1]):<6.0f}  {r[2]:<6d}  {r[3]:<5d}  {A.pct(r[2], r[3]):<6.0f}")
    print(f"\nTOTAL  ToM {tot[0]}/{tot[1]} = {A.pct(tot[0], tot[1]):.0f}%   "
          f"Surge {tot[2]}/{tot[3]} = {A.pct(tot[2], tot[3]):.0f}%")
    print("Cooldowns: Touch of the Magi 45s, Arcane Surge 90s (measured min interval).")
