# What makes a spec good or bad on a boss — Fire, Frost, Feral vs Arcane, Balance (12.1)

Valid as of **2026-10-08**: simc 1210-01 / 12.1.0.69299, rankings pulled the same day.

This is the comparison layer for [fire-mage-12.1.md](mage/fire-mage-12.1.md),
[frost-mage-12.1.md](mage/frost-mage-12.1.md) and [feral-druid-12.1.md](druid/feral-druid-12.1.md). Arcane and
Balance are carried as references, because they are the two specs the project already understands.
It is about **damage** only, not utility.

## The axes, and how each one was measured

A boss rewards a spec along a handful of independent axes. Each is measured two ways where
possible: a sim with everything else held fixed, and the ranking field.

| axis | sim measure | field measure |
|---|---|---|
| single target | DPS, 1 target, 300s | Sszorak (zero adds) |
| sustained cleave | 2 / 3 / 5 permanent targets | Twin Fangs, Explorers (2 bosses all fight) |
| burst AoE | 3 adds for 15s every 60s; 1 add for 30s every 90s | Vashnik, Nymrissa (add waves) |
| burst size | best 10s / 20s of the damage timeline ÷ the average | same, from per-second log damage on Sszorak |
| burst clock | dominant autocorrelation period of the timeline | same, from logs |
| vulnerability | a +30% / +100% window; gain ÷ the gain a flat profile would get | Sszorak Dig In: DPS inside ÷ outside, 12 top pulls per spec |
| fight length | 60 / 120 / 450s vs 300s | — |
| execute | last 30% of a health-based fight vs the average | — |
| mobility | 10% and 20% of the fight moving | not measurable from WCL (see the traps) |

## Sim matrix

Default simc APLs, field-majority talents (except Arcane/Balance: simc's MID2 Arcane Sunfury
string and Funkitty's Twin Fangs profile), Patchwerk with the Twin Fangs script's raid buffs,
4000 iterations.

Mages run Funkywand's gear (324.9). Druids run Funkitty's armor. So **compare ratios across
rows, and levels only within a gear set.**

| profile | 1T DPS | 2T | 3T | 5T | adds 3×15s/60s | add 1×30s/90s | 60s | 120s | 450s | move 10% | move 20% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Fire (Sunfury) | 178.2k | 1.32 | 1.79 | 2.79 | **1.38** | 1.12 | 1.27 | 1.12 | 0.98 | 0.98 | 0.96 |
| Frost Spellslinger | 169.2k | 1.85 | 2.19 | 2.87 | 1.33 | 1.29 | 1.38 | 1.13 | 0.97 | 0.99 | 0.97 |
| Frost Frostfire | 154.5k | **2.09** | **2.42** | **3.08** | 1.35 | **1.35** | 1.19 | 1.07 | 0.99 | 0.99 | 0.98 |
| Feral Wildstalker | 206.5k | 1.34 | 1.74 | 2.53 | 1.22 | 1.11 | 1.33 | 1.08 | 0.97 | (0.99)* | (0.98)* |
| Arcane Sunfury (ref) | 199.5k | 1.39 | 1.76 | 2.41 | 1.26 | 1.13 | 1.29 | 1.13 | 0.98 | 0.96 | 0.93 |
| Balance (ref) | 199.2k | 1.44 | 1.88 | 2.70 | 1.21 | 1.13 | **1.60** | **1.20** | 0.96 | 0.97 | 0.93 |

\* simc's `movement` raid event keeps a melee in range, so Feral's movement cost is not modelled.

### Burst shape and clock

| profile | peak 10s ÷ avg | peak 20s ÷ avg | first 20s ÷ avg | period | last 30% ÷ avg |
|---|---|---|---|---|---|
| Fire | 2.36 | 2.13 | **1.04** | **61s** | **1.08** |
| Frost Spellslinger | 2.15 | 1.96 | 1.85 | ~89s, weak | 0.91 |
| Frost Frostfire | 1.67 | **1.50** | 1.44 | none | 0.93 |
| Feral Wildstalker | 2.56 | 2.10 | **2.01** | 121s | 0.96 |
| Arcane | 2.13 | 1.81 | 1.81 | 92s | 0.92 |
| Balance | 2.52 | 2.21 | 1.28 | 125s | 0.90 |

Logs agree (12 top Mythic Sszorak pulls per spec, median):

| spec | peak 10s | peak 20s | DoT share | period (autocorr) |
|---|---|---|---|---|
| Fire | 2.78 | 2.37 | 0.24 | 64s (0.19) |
| Frost | 2.40 | 1.97 | 0.15 | none (0.12) |
| Feral | 2.75 | 2.16 | **0.51** | 125s (0.26) |
| Balance | **3.85** | **2.56** | 0.20 | 124s (0.23) |
| Arcane | 2.75 | 2.04 | — | 95s (0.16) |

**Peak 20s is the aligned vulnerability multiplier.** A +X% window of 20s placed exactly on a
spec's burst gains `peak20 ×` what a flat profile would gain. So Balance, Fire and Feral are the
specs that profit most from a window *they can reach*. Frostfire profits least; it is the flattest
profile measured.

## Vulnerability windows: reach matters more than burst size

Sszorak's Dig In is +30% for 25s at 100.0 / 227.0 / 354.0s, IQR 0.0 over 94 pulls. Twelve top
Mythic pulls per spec:

| spec | DPS inside ÷ outside | pulls bursting inside window 1 | why |
|---|---|---|---|
| Balance | **2.82×** | 12 / 12 | Incarnation charges (Whirling Stars) can be pointed anywhere |
| Frost | 1.70× (aligned: 1.84×) | 11 / 12 | two banked Ray of Frost charges |
| Arcane | 1.55× | 12 / 12 | 90s Surge plus Touch of the Magi |
| Fire | 1.54× (aligned **1.93×**, not **0.84×**) | 7 / 12 | 60s Combustion must be held ~22s; the field splits on it, and aligned pulls do +5% DPS |
| Feral | **0.99×** | **0 / 12** | a 2-minute Berserk pressed at the pull returns at 120s, after the window opens |

A flat damage profile reads 1.30× here. So Feral is not merely failing to gain: its burst is
anti-aligned with the window. **Cooldown flexibility (charges, short cooldowns, cooldowns that bank)
decides vulnerability capture more than burst size does.** Feral has a 2.10× peak and still captures
nothing.

The sim cannot show this. With default APLs, cooldowns go on cooldown, and the windows land wherever
that happens to be relative to them. The sim's "unplanned capture" (Dig In: Fire 0.69×, Frost
0.95–0.96×, Feral 0.97–1.07×, Arcane 1.04×, Balance 0.90×) measures luck of phase, not skill or
spec. Use it only as a floor.

## The ranking boards, per boss

Median DPS of the top 100 per boss and spec, divided by the five-spec mean on that boss, then
divided by the spec's own average across bosses.

The second normalisation matters. A rare spec's top 100 reaches deeper into its field than a
popular spec's top 100, which biases the *level*. Mythic Fire has 8 ranked Twin Fangs parses while
Frost has hundreds. The cross-boss *shape* survives that bias. The `level` row is the spec's raw
average, popularity bias included.

**Heroic** (100 parses for every spec on every boss, so this is the cleaner table):

| boss | Fire | Frost | Feral | Balance | Arcane |
|---|---|---|---|---|---|
| Nymrissa | 0.98 | **0.88** | 0.93 | **1.16** | 1.02 |
| Nek'zali | 1.03 | 0.94 | 1.04 | 0.98 | 1.01 |
| Sentinels | 1.00 | 1.05 | 0.99 | 1.05 | 0.91 |
| Vashnik | 1.07 | 0.93 | 0.99 | 0.92 | 1.09 |
| Explorers | **0.91** | 1.12 | **0.91** | 1.10 | 0.94 |
| Sszorak | 1.08 | **0.90** | **1.15** | 0.96 | 0.94 |
| Twin Fangs | 0.92 | **1.21** | 0.98 | 0.94 | 0.96 |
| Coiled Altar | 1.08 | 1.02 | 1.01 | 0.92 | 0.99 |
| Ula'tek | 0.94 | 0.94 | 1.01 | 0.96 | **1.13** |
| level | 0.85 | 0.99 | 0.94 | 1.09 | 1.12 |

**Mythic** (same shape where samples exist; Fire, Feral and Frost run out on the last three bosses):

| boss | Fire | Frost | Feral | Balance | Arcane |
|---|---|---|---|---|---|
| Nymrissa | 0.91 | 0.87 | 0.93 | **1.29** | 1.02 |
| Vashnik | **1.17** | 0.89 | 0.98 | 0.97 | 1.08 |
| Explorers | 0.89 | **1.14** | 0.94 | 1.09 | 0.98 |
| Sszorak | 1.07 | 0.90 | **1.17** | 0.96 | 1.00 |
| Twin Fangs | — (8 parses) | 1.13 | 0.95 | 0.91 | 0.93 |

The full table, with Nek'zali, Sentinels, Coiled Altar and Ula'tek, comes from
`scratch/specs/rank_summary.json`.

Off-boss share of damage in the census (median of 20 top Mythic pulls), which is what the add
bosses reward:

| boss | Fire | Frost | Feral |
|---|---|---|---|
| Vashnik | **55.8%** | 37.8% | 36.3% |
| Nymrissa | 43.9% | 41.0% | 19.7% |
| Sentinels | 13.3% | 22.2% | 10.3% |
| Nek'zali | 16.3% | 17.1% | 7.6% |

## The verdicts, one line each

- **Fire** is a burst-AoE and execute spec on a 60-second clock. It is best where adds arrive in
  waves (Vashnik) and in the last 30% of a boss. It is the most mobile caster. It is worst on
  sustained 2-target fights, where Flamestrike's 3-target gate leaves only Ignite spread doing the
  cleaving. It catches vulnerability windows only if the player holds Combustion.
- **Frost** is the 2-target spec: Frostfire on two permanent bosses, Spellslinger otherwise. It has
  no long cooldown, so its profile is flat. It reaches windows through Ray of Frost charges rather
  than big numbers. It is weakest on pure single target and on separated add waves.
- **Feral** is the single-target spec with the biggest scripted opener and a rigid 2-minute
  clock. Half its damage is bleeds, so short-lived adds and windows off the 2-minute grid both hurt
  it. Its likely real-world weakness, reaching spread or moving targets, is invisible to simc. The
  ranking boards (worst on Explorers and Nymrissa) are the evidence for it.
- For contrast, **Balance** wins every vulnerability window it can see (charges) and short fights;
  **Arcane** leads the level table and is strongest where a burst target appears (Ula'tek).

## Stat priority at a glance (sim per-point weights, primary = 1.00)

| spec | order (1 target) | field's secondary split | agrees? |
|---|---|---|---|
| Fire | Haste 0.67 > Vers 0.53 > Mastery 0.49 >> **Crit 0.23** | haste 43.5 / mastery 28.8 / vers 20.0 / crit 5.6 | yes |
| Frost | **Crit 0.73–0.75** > Mastery 0.62–0.67 > Haste ≈ Vers 0.54–0.62 | crit 38.0 / mastery 33.4 / haste 21.2 / vers 6.9 | yes |
| Feral | Haste 0.71 > Vers 0.64 > Crit 0.60 > **Mastery 0.52** | mastery 36.8 / haste 30.2 / crit 26.5 / vers 4.7 | **no**: worth ~0.5% (flask test), unresolved |

The two Mage specs want opposite secondaries. **Gear that is best-in-slot for Fire is the wrong
stat split for Frost**, even though every piece is shared.

## Reproduce

```bash
cd scratch/specs/sims
./run.sh <tag> <actor>.simc <talents>.simc <gear>.simc                    # scen.txt: targets, length, movement, adds
SCEN=scen_vuln.txt ./run.sh <tag> ...                                      # Dig In / +100% windows, fixed 380s
SCEN=scen_sw.txt ITER=3000 ./run.sh <tag> ...                              # scale factors, 1T and 3T
wsl.exe -d Ubuntu -e python3 parse.py                                      # every table above
```

From the repo root:

```bash
wsl.exe -d Ubuntu -e python3 scratch/specs/burst_summary.py       # log burst table
wsl.exe -d Ubuntu -e python3 scratch/specs/rank_summary.py        # ranking medians
wsl.exe -d Ubuntu -e python3 scratch/specs/analyze_census.py <fire|frost|feral>
wsl.exe -d Ubuntu -e python3 scratch/specs/sim_vs_log.py <sim tag> <spec> <boss> [scenario]
```

## Traps hit while building this

- **Git Bash rewrites `raid_events+=/movement` into a Windows path** ("Invalid raid event type 'C:'").
  `run.sh` exports `MSYS_NO_PATHCONV=1`. Any simc call from Git Bash with a `+=/` option needs it.
- **Validate a cleave build against a cleave sim.** Frostfire against a 1-target sim read Shatter 32%
  vs 42% logged and looked like a broken model. Against the 2-target sim it matches to 1.5 points.
- **A loadout majority from a thin, skewed sample is a different build.** Druid of the Claw's 9 pulls
  are mostly Sszorak, so their majority loadout has no AoE talents. Compare hero trees on the same
  spec tree.
- **Normalise the ranking table twice.** Spec ÷ boss mean alone still mixes in popularity: a rare
  spec's top 100 is shallower.
- WCL target-view `activeTime` reads ~99.7% for every spec on every boss whenever a DoT ticks. It is
  not an uptime measure.
