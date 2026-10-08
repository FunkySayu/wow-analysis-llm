# Fire Mage — 12.1.0 (live)

Valid as of **2026-10-08**: simc 1210-01, WoW 12.1.0.69299 (hotfix 2026-08-15), live talent feed.
The patch is live, so the plain `nether.wowhead.com/tooltip/spell/<id>` endpoint is the correct one.
A `/ptr/` pull would describe a future build.

Data behind every number here:

| source | what |
|---|---|
| [data/classes/mage/fire/12_1_talents.json](../../../../data/classes/mage/fire/12_1_talents.json) | full tree with live tooltip text (`tools/raidbots/talent_tree_sync.py --class 8 --spec 63`) |
| [data/sims/12_1/spec_matrix/](../../../../data/sims/12_1/spec_matrix/) | the sim profiles and the scenario matrix (see [dps-specs-boss-profile-12.1.md](../dps-specs-boss-profile-12.1.md)) |
| census, 2026-10-08 (not kept in the repo) | 120 top Mythic pulls (20 per boss × 6 bosses): gear, stats, talents, auras, damage by ability and by target; top-100 rankings per boss × difficulty × spec; per-second damage of 12 top Mythic Sszorak pulls per spec |

Cross-spec comparison (what Fire is good and bad at, against Frost, Feral, Arcane and Balance) is
in [dps-specs-boss-profile-12.1.md](../dps-specs-boss-profile-12.1.md). This file is the spec itself.

## The engine: Hot Streak is the resource, Pyroblast is the only spender

Read through the resource-economy lens from [resource-economy.md](../../method/resource-economy.md):

- **Heating Up → Hot Streak** (48107 → 48108). Two direct-damage Fire crits in a row make the next
  Pyroblast or Flamestrike instant and give it **double Ignite**. A non-crit in between resets the pair.
- **Generators of crits:** Fireball (Pyrotechnics, 157644, adds +20% crit per non-crit Fireball),
  Scorch, Pyroblast, Meteor, and above all **Fire Blast** (108853). Fire Blast *always* crits, is
  off-GCD, and is castable while casting. It converts Heating Up into Hot Streak on demand. Charges
  come from Fervent Flickering and Flame On (3 charges, −2s). Recharge comes from From the Ashes
  (−0.5s per direct hit), Fired Up rank 2 (−2.5s per stack), Spellfire Salvo (−1s), Pyrocosm
  (−0.5s per Meteorite), and Fiery Rush (50% faster inside Combustion).
- **The spender:** Pyroblast (or Flamestrike in AoE), and nothing else. Nearly every payoff in the
  tree hangs off *consuming Hot Streak*:
  - Fired Up (apex, 20% for +2% Fire damage for 8s)
  - Spellfire Sphere (12%, +12% from Rondurmancy)
  - Mana Cascade (0.5% haste)
  - Pyroclasm (15%: next hardcast Pyroblast deals +230%)
  - Pyromaniac (6% to repeat at 50%)
  - Inflame (+25% Ignite)

  That makes Pyroblast the highest-leverage cast in the kit: 33% of the field's damage pooled,
  45% on single target.
- **Ignite** (12654, mastery 12846) is the second engine. 4% × mastery of the direct damage from
  Fireball, Fire Blast, Pyroblast, Meteor and Flamestrike rolls into one 9s DoT, and a reapplication
  carries the remainder forward. It is **28.8% of the field's damage** (27.5% on Sszorak), plus
  Intensifying Flame's flare (+30% while Ignite is on ≤3 targets), which WCL folds into the Ignite
  line.
  - Fire Blast spreads Ignite: Ignition 50% to 1 enemy, Wildfire +1 target, Master of Flame +50%.
  - Burnout detonates 75% of the remaining Ignite when Combustion ends.

  This is the cleave mechanism, and why Fire's 2-target number is soft (see below).
- **Combustion** (190319): +100% crit for 10s, plus mastery equal to 75% of crit chance.
  - **Kindling** (−60s) makes it a 60-second cooldown.
  - **Fired Up** rank 3 extends it +1s per stack, so it averages **13.7s** in the sim (5 casts in
    300s, 22.8% uptime).
  - Sunfury summons the **Arcane Phoenix** on Combustion. When the Phoenix leaves, **Memory of
    Al'ar** grants **Hyperthermia** for 4s: instant, guaranteed-crit Pyroblasts.

### Why crit rating is the worst stat (and the field knows it)

The sim's per-point scale factors on Funkywand's gear:

| | 1 target | 3 targets |
|---|---|---|
| Int | 1.00 | 1.00 |
| Haste | 0.67 | 0.60 |
| Vers | 0.53 | 0.51 |
| Mastery | 0.49 | 0.57 |
| **Crit** | **0.23** | **0.24** |

Crit is worth about a third of any other secondary, and the field gears accordingly. Median
secondary split over 120 top pulls is **haste 43.5%, mastery 28.8%, vers 20.0%, crit 5.6%**
(p25–p75 of crit share is 4–13%). Flask of Thalassian Resistance (vers) is used in 64 pulls and
Blood Knights (haste) in 39.

The mechanism is not isolated by an experiment here. The plausible reading is that the spec's crits
are already bought elsewhere: Combustion's +100%, Fire Blast's guaranteed crit, Pyrotechnics'
self-correcting Fireball, Firestarter above 90%, Scald/Scorch below 30%, Hyperthermia. Treat that
as the explanation, not as a measured one.

## Reading the APL (simc `mage_fire.simc`)

Structural gates first, per [reading-an-apl.md](../../method/reading-an-apl.md):

```
actions+=/run_action_list,name=ff_combustion,if=talent.frostfire_bolt&((time>=variable.combustion_delay)&(...))
actions+=/run_action_list,name=sf_combustion,if=!talent.frostfire_bolt&((time>=variable.combustion_delay)&(...))
actions+=/run_action_list,name=ff_filler,if=talent.frostfire_bolt
actions+=/run_action_list,name=sf_filler
```

- **Frostfire (`ff_*`) vs Sunfury (`sf_*`)** is decided by `talent.frostfire_bolt`. Every top Mythic
  Fire pull is Sunfury, so only `sf_combustion` / `sf_filler` / `fireblast` are live.
- **`variable.combustion_delay = 18*talent.firestarter - ...`** holds Combustion for the first ~18s.
  It simulates the boss staying above 90% health, where Firestarter already makes Fireball and
  Pyroblast auto-crit. The logs agree: the first damage peak in 12 top Sszorak pulls lands at
  11–38s, median ~18s. Consequence: **Fire's opener is not a burst.** The first 20s run at
  1.04× its average DPS, against 1.8–2.0× for Arcane, Feral and Spellslinger Frost.
- **Hot Streak is held** when Combustion is <5s away (`cooldown.combustion.remains>=5`).
- **`fireblast` list** fires Fire Blast while casting (`use_while_casting=1`), only with Heating Up
  (`hot_streak_spells_in_flight+buff.heating_up.react=1`), so a Fire Blast is never wasted on a
  crit pair already in flight. The exception is the Spontaneous Combustion pre-cast, which dumps
  all charges.
- `variable.sf_*_flamestrike = 3+999*!talent.fuel_the_fire+...` sets the **Flamestrike threshold at
  3 targets**. That is the jump from 1.32× at 2 targets to 1.79× at 3 in the sim.

## What the field plays (census, 120 top Mythic pulls, 2026-10-08)

- **Hero tree: Sunfury 120/120.** Frostfire does not appear on any boss.
- **Apex Fired Up: all four ranks** in every pull.
- **Contested nodes:**
  - Flamestrike *at target* (1254851) 79 vs *at location* (2120) 41
  - Explosive Potential 75 vs Lessons in Debilitation 45
  - Time Walk 101 vs Temporal Realignment 19
  - Burn It All over Slow Burn
- **Gear:**
  - Jan'thrazet + Aln'hara Lantern (88/120) or Aln'hara Cane (2H, 32).
  - Trinkets: Vile Vial of Volatile Venom 84, Gebbo's Bottomless Bag 55, Wavecaller's Seastone 40.
  - Aqirbane Reliquary 94; 4-piece in 88 pulls, 5 pieces in 32.
  - Weapon enchant: Acuity of the Ren'dorei 60 vs Rite of the Hash'ey 53.
  - Embellishments: Arcanoweave Lining 134 and Hunter's Ritual Stone 95.
- **Damage composition (pooled):**

  | ability | share |
  |---|---|
  | Pyroblast | 33.4% |
  | Ignite | 28.8% |
  | Flamestrike | 10.9% (in 58 of 120 pulls) |
  | Meteor | 6.1% |
  | Meteorite | 5.7% |
  | Fire Blast | 4.1% |
  | Arcane Phoenix | 3.6% |
  | Scorch | 3.4% |
  | Fireball | 2.5% |
- **Mythic Fire is rare.** Twin Fangs has 8 ranked Mythic Fire parses, Coiled Altar 1, Ula'tek 0,
  while Frost, Balance and Arcane fill the top 100 on all of them. The census therefore covers six
  bosses, not nine.

## The sim profile

```
cd data/sims/12_1/spec_matrix
../../../../vendor/simc/build/Release/simc.exe base.simc fw_fire_field.simc tal_fire_sunfury.simc funkywand_gear.simc
```

| piece | what |
|---|---|
| `funkywand_gear.simc` | Funkywand's gear from `HfGDg1K3bRzcqPkN` fight 6 (2026-09-30), ilvl 324.9, 4pc set 2060. Same corrections as Funkitty's profile: Aqirbane `stats=` override, 879x crafted bonus ids, Rite of the Hash'ey as constant rating. |
| `tal_fire_sunfury.simc` | the field's node-majority loadout (`class_talents=`/`spec_talents=`/`hero_talents=` entry ids). Resolved with `debug=1`; all four apex ranks present. |
| `fw_fire_field.simc` | actor, consumables (Thalassian Resistance flask, the field's modal) |
| `base.simc` | Patchwerk 300s with the same raid buffs as the Twin Fangs Balance script |

**Baseline 178.2k DPS** (1 target, 300s, ±0.15%). On the same gear, Arcane Sunfury sims 199.5k
(Fire −11%). The ranking field puts Fire's level at 0.85 of the five-spec mean against Arcane's
1.12, so sim and field agree on the order.

**Validated against the logs** (sim 1 target vs 20 top Sszorak pulls, single target, no adds):

| | Pyroblast | Ignite + Intensifying Flame | Fire Blast | Scorch | Meteor | Meteorite | Fireball |
|---|---|---|---|---|---|---|---|
| sim | 48.8% | 27.8% | 4.8% | 4.1% | 4.8% | 4.0% | 3.2% |
| log | 45.0% | 27.5% | 4.9% | 4.5% | 4.8% | 5.9% | 2.2% |

**Trust boundary: the Phoenix is under-modelled.** Its pet spells (Arcane Barrage, Greater
Pyroblast, …) total ~1.2% in the sim against 3.1% logged. This is the same gap the Arcane file
records for Sunfury.

## What Fire is good and bad at, damage-wise

Sim ratios are against Fire's own 1-target 300s number; the full cross-spec table is in
[dps-specs-boss-profile-12.1.md](../dps-specs-boss-profile-12.1.md).

| shape | Fire | reading |
|---|---|---|
| 2 targets (sustained) | 1.32× | weakest 2-target scaling of the five specs. Only Ignite spread cleaves; Flamestrike is gated to 3+. |
| 3 / 5 targets | 1.79× / **2.79×** | Flamestrike + Fuel the Fire take over; ahead of Balance (2.70), Feral (2.53) and Arcane (2.41), behind both Frost builds (2.87 / 3.08) |
| 3 adds for 15s every 60s | **1.38×** | best of the five. Flamestrike, Ignite spread and Meteor all land on fresh adds, and Firestarter crits anything above 90% health. |
| 60s fight | 1.27× | the smallest short-fight gain: the opener is deliberately not a burst (Combustion delay) |
| last 30% of a health-based fight | **1.08×** its average | the *only* spec that gets stronger at the end (Scald, Molten Fury, Scorch auto-crit below 30%). Every other spec reads 0.90–0.93×. |
| 20% of the fight moving | 0.96× | Scorch is castable while moving and Hot Streak Pyroblasts are instant; the best of the three casters |
| burst shape | peak 20s = **2.13×** average, period **61s** | a strong burst every minute: Combustion on Kindling |

**On the ranking boards** the per-boss shape agrees on both Heroic (100 parses on every boss) and
Mythic. The table normalises each spec by its own cross-boss average, which cancels the popularity
bias of comparing a rare spec's top 100 with a popular one's.

| boss | Heroic | Mythic | why |
|---|---|---|---|
| **Vashnik** | 1.07 | **1.17** | burst adds: Fire does **55.8%** of its damage off-boss here, more than Frost (37.8%) or Feral (36.3%) |
| Sszorak | 1.08 | 1.07 | pure single target, Dig In every 127s (below) |
| Coiled Altar | 1.08 | — | single target with a +100% intermission |
| Explorers | **0.91** | **0.89** | two bosses held together for the whole fight: the sustained 2-target case |
| Twin Fangs | **0.92** | — | two permanent bosses, the same weakness |

### Vulnerability windows: Fire can catch them, but only if the player holds

On Sszorak, Dig In is +30% damage taken for 25s at 100.0 / 227.0 / 354.0s (IQR 0.0 over 94 pulls).
Split by whether the pull's best 10s landed inside the first window:

| 12 top Mythic Fire pulls | n | DPS inside Dig In ÷ outside | median DPS |
|---|---|---|---|
| Combustion held into Dig In | 7 | **1.93×** | 196k |
| Combustion on cooldown | 5 | **0.84×** | 186k |

The 60s Combustion cannot hit 100s and 227s on cooldown: 18 → 78 → 138 lands outside both. A
22-second hold fixes the first window, and the field splits on whether to take it. Every Arcane and
Balance pull in the same sample aligned, and 11 of 12 Frost pulls did. **For Fire this is a
decision worth about 5% on the boss**, and it is invisible to a sim that presses cooldowns on
cooldown: the unplanned sim captures only 0.69× of a flat profile's Dig In gain.

## Reading a Fire log

Logged damage ids, confirmed from the census:

| ability | id |
|---|---|
| Pyroblast | 11366 |
| Ignite | **12654** (Frostfire Frost logs a *different* Ignite, 1262887) |
| Flamestrike | **2120** at a location and **1254851** at the target: two ids for the choice node |
| Meteor | 153561 |
| Meteorite | 449569 |
| Fire Blast | 108853 |
| Arcane Phoenix | 448659 |
| Scorch | 2948 |
| Fireball | 133 |

Buffs: Hot Streak 48108, Heating Up 48107, Combustion 190319.

## Traps found while building this

- `tools/raidbots/talent_tree_sync.py` crashed on both Mage specs: the Frostfire subtree lists a node with no
  definition in `heroNodes` (94636 on Fire, 109956 on Frost). Fixed: such ids now go to
  `undefined_node_ids` instead of `node_ids`.
- **The apex is a tiered node whose ranks are separate entry ids.** A loadout builder that keeps
  "the best entry per node" silently keeps one rank of four. Keep every tier above the threshold,
  then verify with `debug=1`.
- Two WCL measures are useless here (the `graph` endpoint's ~40s smoothing, target-view
  `activeTime` saturating whenever Ignite ticks); see the cross-spec file's traps.
- The `midnight.crucible_of_erratic_energies_*` sim options from the Twin Fangs script are
  "Unknown option, ignoring" for these actors. They are inert unless that trinket is equipped.
