# Sszorak, Mythic — the mechanic model and what the field actually does

Measured 2026-09-24 from **30 guilds at progress ranks 250–750, 451 pulls, all with kills**,
sampled across each guild's own first/middle/last third (stages 1–2 of the pipeline in
[boss-death-timelines.md](../../../method/boss-death-timelines.md):
`tools/warcraftlogs/guild_progress_sample.py` and `wipe_death_profile.py`). Published report
`reports/sszorak_winds_and_venom.html`.

The analysis scripts after that stayed in the local working area, not the repo. Their stage
order is load-bearing — each stage adds to one shared payload, and running them out of order
silently drops a section rather than failing — so it is recorded here:

1. fetch the pulls and the deaths stream (API, slow, resumable; once by hand)
2. re-reduce the cached cast stream **by target** (externals: Rescue, Leap of Faith, mitigation
   cooldowns on carriers)
3. reduce per-pull records into one roll-up
4. findings → payload (**rebuilds the payload from scratch**, so everything below must follow it)
5. partner-assignment permutation test
6. immunities, externals and the race question
7. grade floats by consequence rather than pair rate
8. bomb drops in **room** coordinates, filtered to before the pull's third death
9. what a vortex breaks when it catches a job holder
10. binned series for the figures
11. the token table the prose quotes
12. template + payloads → report, then a DOM smoke test

Read [boss-death-timelines.md](../../../method/boss-death-timelines.md) and
[analysing-a-pull.md](../../../method/analysing-a-pull.md) first for method; this file is data plus the
mechanics that are not in any tooltip.

## The log's spell ids are not the journal's

Resolve **by name** from each report's `masterData`, never by a remembered id. On this boss
the journal id and the firing id differ for most of the kit:

| Mechanic | Journal | What the log actually uses |
|---|---|---|
| Raging Crosswinds | 1285419 | cast 1285419 + **four direction debuffs** 1285425 / 1285453 / 1297096 / 1297111; DoT 1312219; 6-yard burst 1285616, 1285444 |
| Turbulent Gusts | 1285447 | 1285447 (the one that matches) |
| Venomous Surge | 1305959 | cast 1305959, **debuff 1305963**, DoT 1312156, raid detonation 1306120 |
| Viscous Cyst | 1287008 | **1287205** |
| Caustic Residue | 1296602 | **1296667** |
| Serpent's Fury | 1297367 | **1305621** |
| Tempest | 1287072 | **1287083** |
| Glide (Dracthyr racial) | &mdash; | **358733**, and the Demon Hunter Glide is **131347** |
| Rescue (Evoker) | &mdash; | 370665, cast from the ground so a caster-side filter never sees it |
| Ravage | 1277002 | **1277105** |
| Mutilate | 1277027 | 1277027 / 1277031, damage **1285999**, Gash **1285998** |
| Virulence | 1297707 | **1297707 and 1299899** (two), damage 1312189 / 1300089 |

**`Debilitating Venom` (1295123) is a trinket, not a mechanic.** It presents exactly like
one — three players at a time, ~128s cadence, absent from the Adventure Journal — and its
Wowhead tooltip reads "Take a small sip of venom, gaining 518 of a random secondary stat".
Trap 10 of [boss-death-timelines.md](../../../method/boss-death-timelines.md) in a new costume. **To the Slaughter emits no damage and
no cast event**; use the `Serpent's Fury` debuff *removal* as its timestamp.

## The mechanics, as they actually behave

- **Raging Crosswinds** marks **eight** players, two per direction id, for 8s. On expiry:
  500k inside 6 yards, then a knock and **Turbulent Gusts** (10s of slow falling).
- **Turbulent Gusts dissipates on contact with another floating player, and a collision
  strips the aura from both in the same server tick.** That tick is the entire basis for
  measuring pairing. Tolerance 25ms — the distribution has a gap there, not a crowd.
  Validate the classification against time-in-air, which it never looks at: paired floats
  sit at a median 0.44s, unpaired at 2.0s, cleanly bimodal.
- **You cannot pair with someone thrown the same direction.** Of 3,853 unambiguous
  two-player collisions only **2.4%** shared a direction, against a 14.3% chance baseline.
  Parallel travel never converges. Pile-ups of 3+ auras in one tick (1,311 floats) cannot
  attribute a partner and must be excluded from that test — including them reads 7.0% and
  hides the effect.
- **Nothing sits at the aura's full 10s.** An unpaired player is not stuck; they drift down
  and land. "Unmatched" costs uptime, not health.
- **Venomous Surge** puts the bomb on exactly **two** players per cast, applied ~2s apart,
  10s each. On expiry: a raid-wide distance-scaled hit plus a **Viscous Cyst** where the
  carrier stood.
- **Viscous Cyst residue is knockback resistance** ("better adhere to the ground"). This is
  the hinge of the whole encounter's positioning — see the anchor bomb below.
- **Mutilate is the tank's frontal that the raid soaks**: exactly one tank is in it on 99%
  of casts, plus ~9 other bodies. PTR wording is "fewer than 5 players" → deadly (live says
  "5 or fewer"; the PTR tooltip is the correct one for this build).
- **Ravage hits one player** (the tank) — a swap mechanic, not a soak.
- **Serpent's Fury** marks one player and fires **To the Slaughter** once 14 players are
  within 8 yards. **Raging Crosswinds excludes the mark holder**: 21 picks out of 7,718
  where proportional selection gives ~386. That single rule is why hunters look steered
  (0.61× their roster share) — hunters hold the mark 58.8% of the time.

## The schedule (medians over full-length pulls, IQR 0.0s)

```
To the Slaughter    26.3  75.4  151.9  202.1  278.8  327.0      (raid-controlled, not a timer)
Venomous Surge      32.0  79.3  159.0  206.1  286.1  333.1
Raging Crosswinds   39.7  86.7  166.8  213.8  293.8  340.8
Mutilate            12/20  59/71  137/148  182/198  264/275  313/326
Howling Maelstrom   100–125   227–252   354–379
```

Tight overlaps, every pull: the wind marks eight a median **4.2s after the bombs detonate**
(within 6s on 93.5% of occurrences), and the bomb goes out **4.9s after the charge**.

## What the field does, and does not do

- **Pairing does not improve with progression.** Resolved pair rate 73.3% / 75.6% / 73.8%
  across each guild's own thirds. Airborne seconds per wind cast: 11.4 → 10.7. Both flat.
  What improves is survival (deaths airborne 19.9% → 9.5%; bomb carriers dying 19.7% → 2.9%),
  which is why the *raw* pair share rises from 48% to 62% and means nothing.
- **No guild assigns wind partners.** Permutation test against random legal re-pairing:
  0 of 28 testable guilds beat the null, median z = −1.6, median 0.90× the random
  concentration. Role mix matches independence. Rank does not predict pair rate (r = −0.09).
  This is the largest untouched lever on the boss.
- **Mid-air tools do not explain the class spread.** Across 13 classes tool use vs pair rate
  is r = 0.45, but Paladin is 2nd at 83.8% on a 3.0% tool rate; at guild level the roster's
  tool share correlates at **r = −0.08**; 11.9% of completed pairs had no tool on either
  side; and distance from the boss when thrown explains nothing (r = −0.04, flat by decile).
  In 9 of 13 classes the tool is pressed *more* on failed floats — it is a recovery.
  Priests own nothing usable, sit mid-field at 75.9%, and press nothing at all on successful
  floats: they get rescued rather than rescue.
- **The anchor bomb is the one convention the whole field shares.** The **second carrier of
  each bomb pair that expires ~9s before Howling Maelstrom** — cysts 4, 8 and 12 of the pull
  — is dropped at a fixed room position, median deviation **5.0 yd** against **40.7 yd** for
  every other bomb. Mechanism confirmed: Maelstrom windows are ~20% of the fight and carry
  **77%** of all cyst-standing damage. The raid parks in the residue to resist the gales.
  Adoption splits the band: 20 of 30 guilds hold it inside 10 yd, the loosest at 40.3 yd.
- **Everything else about bomb placement is distance, not direction.** Median 40 yd from the
  boss (middle half 34–45), bearing concentration 0.11. ~10% of the raid still eats
  near-maximum detonation damage, flat across progression.
- **Bomb carriers who die** (6.4% overall) are not killed by standing in bad: Caustic
  Residue exposure has **lift 0.48**, i.e. it is commoner among survivors. The real risk
  factors are **Virulence (5.05×)** — the chain toxin To the Slaughter spreads through the
  stack — and **holding the Serpent's Fury mark (3.4×)**. The top killing blow is Venomous
  Surge itself at 48%.
- **Five classes opt out of the wind entirely, and it is the real class divide.** A full
  immunity up when the 8s mark expires makes the knock fail to apply: the player is marked,
  never lifts, and never enters the float population. Paladins answer **26.1%** of their 737
  marks with Divine Shield at a median **4.7s** into the window; Hunter (Aspect of the
  Turtle) 16.6%, Rogue (Cloak of Shadows) 8.4%, DK (Anti-Magic Shell) 4.2%, Mage 0.4%. The
  other eight classes: zero. It is a good trade personally (damage taken 1.47M -> 0.83M,
  deaths 21.3% -> 4.7%) and it costs the raid one *forced* orphan, because a pair needs two
  different directions and seven in the air has an 85.7% ceiling. Observed 72.7% with seven
  up against 76.0% with eight.
  **Divine Steed and Death's Advance do not work** (23.8% vs a 28.1% base; 3.0% vs 12.1%) --
  forced-movement immunity is not what beats this knock, damage/magic immunity is.
- **Rescue and Leap of Faith are a real rotation aimed at exactly the two classes that
  cannot help themselves.** 105 Rescues landed on a floater, 94% of them on a paladin or a
  priest (69/30); Leap of Faith 62, half onto paladins. But coverage is one paladin float in
  six and one priest float in fifteen -- a spot fix, not a system. Every other class is under
  22 externals per 1,000 floats.
- **68.5% of clean pairs involve no movement ability from either player.** Paladin 85.2%,
  Priest 79.7%. The partner column is flat across classes, so there is no
  "someone comes to the priest" convention -- pairs are where the wind put them.
- **The Dracthyr priest swap is common and does not work.** 20 of 51 priest characters are
  Dracthyr (detected by casting Glide 358733; the detector validates at 98% of evokers),
  across 17 of 30 guilds. Within the five guilds fielding both, the Dracthyr priest paired
  **60.0% against 89.4%** for the non-Dracthyr priest beside them, worse in 4 of 5. Measured
  flat, Dracthyr who skip Glide read 99.1% -- an artefact, because a float that resolves in
  0.4s leaves no window to press anything. At the 0.5s landmark: non-Dracthyr 62.8%,
  Dracthyr who had not glided 39.6%, Dracthyr who had 27.3%.
- **Tempest is the single biggest cause of a pull's first three deaths, at every stage of
  progression.** Of 1,340 first-three deaths over 450 pulls, **45.8%** had Tempest damage in
  the 4s before dying and were not one-shot by something else; Tempest is the literal killing
  blow on 37.1%. The next-largest killing blow is Venomous Surge at 8.7%. It is *avoidable* --
  spiralling vortices, 500k on contact plus a stacking 208k/s and a 30% slow -- and the share
  barely moves across progression (50.0% -> 42.0%), so the field never solves it, it just
  dies less overall. 56.0% of pulls open with a Tempest death. The one overlap that matters:
  a player holding the Raging Crosswinds mark dies to Tempest at 64.9% of their deaths
  against 42.6% for everyone else, because the mark forces a 6-yard spread while the vortex
  slows them 30%.
- **The pair rate is not a survival metric, and grading floats by consequence changes the
  reading.** Restricted to floats thrown while >=90% of the raid is alive: an unpaired float
  lands in a **Viscous Cyst 9.6% of the time against 2.3%** paired (4.2x, stable at every
  level of raid health) because it rides the wind **2.5s / 17.6 yd** instead of
  **0.43s / 8.4 yd** and is deposited out at the rim where the bombs were dropped. But it
  **does not kill you**: raw it looks 8.1% vs 4.6% lethal, and 106 of those 156 deaths carry
  no killing blow -- wipe cascade. Attributed deaths on a healthy raid are 2.0% alone against
  2.5% paired. Failing the pair is a positioning tax charged later, not a death.
- **Nobody is blown off the platform.** 162 fall/fatigue events over 451 pulls, 3 lethal in
  8,544 deaths, none on a float. The 146 floats that took fall damage had **all paired** --
  the collision strips Turbulent Gusts, which was the thing slowing the fall.
- **A floater never meets a live bomb.** Zero of 5,164 collisions had a partner carrying
  Venomous Surge and zero floats carried one. The schedule forbids it: bombs detonate a
  median 4.2s *before* the wind marks and the knock is 8s after that, so the cycle's bombs
  are ~12s gone by the time anyone is airborne.
- **What actually resolves a mark** (every mark in one bucket). Paladin, 737 marks: 26.1%
  immune, 48.0% collided unaided, 8.3% external-into-collision, 4.6% external without one,
  4.9% drifted alone, 5.6% died. Of the 526 that lifted: **67.3% unaided, 18.1% external
  (Rescue 69 : Leap of Faith 31), 6.8% drifted**. Priest, 566 marks, no immunity: 69.4% of
  lifts unaided, 6.3% external, **20.2% drifted down alone -- three times the paladin rate**.
  That gap is the priest problem, and it is exposure to the cyst field, not deaths.
- **The anchor convention is a ROOM position, not a boss-relative one.** Plotted in room
  coordinates (the frame is shared across reports -- per-guild centroids agree to ~25 yd,
  which is just where each guild tanks), the anchor sits **4.3-6.4 yd** from the field's
  median drop point at every progression third, against **36.6-40.8 yd** for every other
  bomb. It does not tighten with progression, so it is not learned in this band. A
  boss-relative frame smears it into an arc, because Sszorak moves -- that was the flaw in
  the first version of the figure. Filter to bombs whose debuff window is wholly before the
  pull's third death, or triage placement makes a disciplined field look sloppy.
- **A vortex hit only threatens the raid through one job: the Serpent's Fury mark holder.**
  Over Tempest contacts on a healthy raid (>=85% alive), 15.9% are followed by >=5 deaths in
  15s. By job: stack mark **24.0% (1.51x)**, bomb 19.8%, wind mark 17.3%, nothing 15.7%,
  airborne 11.9%. Measured over the mark windows themselves: when the holder is caught, a
  median **6** raid members are also in a vortex against **3** when they are not, and
  **37.5%** of those windows precede a collapse against **25.3%** clean. The raid is
  *required* to stack on that player, so the vortex becomes everybody's.
  **The bomb-misplacement mechanism is not real**: only 4.3% of bombs have a hit carrier,
  the anchor moves 4.8 -> 7.1 yd on n=10, and carrier death is 6.8% vs 5.9%. A circulating
  "35% of vortex hits wipe the raid" matches the stack-marker number, not the bomb one.
- **Shadowstep and Wild Charge are not externals.** They are friendly-targeted, so a
  by-target scan picks them up, but they move the *caster* to the ally. Only Rescue and
  Leap of Faith move the target. Counting them as rescues received credits a priest with
  being saved when a rogue merely walked over.
- **Healers barely put externals on bomb carriers, and it is the cheapest win on the
  fight.** Scanned by target over Venomous Surge windows: 184 targeted mitigation cooldowns
  across 2,181 carriers, so only **7.6%** of carriers get one. Blessing of Sacrifice 63,
  Time Dilation 47, Ironbark 29, Life Cocoon 24, Guardian Spirit 21, at a median 3-4s into
  the 10s window. Controlled for raid health (>=90% alive), carriers who got one died
  **0.0% (n=150)** against **5.1% (n=1,527)** who did not -- about eight deaths' worth. The
  confound runs the right way to worry about (healers have spare globals when the raid is
  healthy, and coverage falls 8.9% -> 4.8% -> 1.6% as it degrades), and the effect survives
  it. **The bomb cannot be dispelled instead**: 32 dispels aimed at carriers across the
  benchmark and only 1.5% of carriers lose the debuff early without dying.
- **Stampeding Roar is a stacking tool here, not an escape.** 54.7% of casts land within 3s
  of To the Slaughter at a median offset of −0.04s; Wind Rush Totem does the same 2.1s
  earlier and splits the rest toward the Maelstrom. Neither is used on the winds at all.

## Two results that were wrong first

0. **The shared deaths helper read the embedded Deaths TABLE, not the per-fight stream, until
   2026-09-27.** The fetch stage fixed the stream and the roll-up used it, but the shared
   helper every other consumer called did not -- so each bomb's `diedBefore` was
   computed from a table that is **empty on 255 of the 451 pulls** (the truncation is
   documented in `tools/warcraftlogs/README.md`). Published figures moved:
   carriers dying 6.4% -> **11.4%**, the progression curve 19.7%->2.9% to **25.8%->6.8%**,
   Virulence lift 5.05x -> **3.63x**, mark-holder 3.4x -> **5.5x** (Caustic Residue stays
   disconfirmed at 0.45). For a freshly fetched single report the table is empty outright,
   so a guild comparison read every carrier as a survivor; deaths for a report outside the
   benchmark must be fetched from the stream explicitly. **Fix a data source in the helper,
   not in one caller.**
1. **A bomb carrier's death is logged up to tens of ms *after* the aura falls off the
   corpse.** Testing `death <= aura removal` missed four in five of them. Test instead that
   the aura ended early *and* a death sits within ~1.5s of that ending.
2. **The tank frontal colliding with the stack looked like a fourfold soak-failure effect
   and is not one.** With the truncated Deaths table, wipes already in progress were not
   being excluded and read as soak failures. Corrected: 3.4% under five bodies when it lands
   on the charge against 2.8% when clear — no difference. The overlap is real on the
   schedule and the field absorbs it. This is in the published report as a visible
   retraction rather than a quiet deletion.
3. **"Priests press nothing while airborne" was a missing spell id, not a fact.** Two
   different abilities log under the name "Glide" -- 131347 (Demon Hunter) and 358733
   (Dracthyr racial) -- and only the first was on the tracked list, so every Dracthyr read
   as pressing nothing. Corrected, priests press a tool on 23.1% of floats and evokers on
   47.0%. Same trap as Typhoon/Solar Beam in the M+ file: **resolve by name, then check
   whether the name maps to more than one id.**
4. **Conditioning on the float conditions on the outcome.** Any "did they press X" question
   asked over a float is confounded, because a float that resolves in 0.4s gives no window
   to press anything. Compare at a landmark instead -- among floats still airborne at time T,
   split by what was pressed before T. The Dracthyr result reverses sign between the two.
