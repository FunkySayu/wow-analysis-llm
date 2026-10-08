# Twin Fangs (Mythic) sim profile: reference card

Valid as of 2026-10-08 (simc 1210-01 vendored + patches, 12.1.0 data). This is the profile to use
for any Balance Druid question on The Twin Fangs: gear, trinkets, consumables, rotation choices.
Method behind it is in [modelling-a-fight-in-simc.md](../../../method/modelling-a-fight-in-simc.md);
the encounter measurements it encodes are in [venomous-abyss-mythic.md](venomous-abyss-mythic.md)
("The Twin Fangs"); what the Balance field wears and chooses on this boss is in
[balance-druid-12.1.md](../../../classes/druid/balance-druid-12.1.md).

## Run it

The files are in `data/raid/12_1/venomous_abyss/06_twinfangs/sim/`. From there, in this order
(later files override earlier ones):

```
../../../../../../vendor/simc/build/Release/simc.exe twinfangs.simc funkitty_current.simc apl_plan.simc \
    [<profilesets>.simc] iterations=10000 threads=16 json2=out.json html=out.html
```

| piece | file | what |
|---|---|---|
| fight | `twinfangs.simc` | 402s, both bosses, 5 Spawn waves, raid buffs |
| actor | `funkitty_current.simc` | Funkitty, 2026-10-07 23:18 export, field talents, Recklessness, Vantus |
| APL | `apl_plan.simc` | simc default Balance APL + Model B wave routine + **the player's Incarnation schedule** |
| binary | `vendor/simc` + the patches in `tools/simc/` | stock simc gets the geometry wrong (below) |

**Baseline: 297.6k boss DPS** (±0.15k at 10k iterations), 328.5k total. (Re-checked from the
repo copy on 2026-10-08: 328.8k total at 300 iterations.)

**Read `prioritydps`, not `dps`.** Boss damage is the metric. `merge_enemy_priority_dmg=1`
counts both bosses as priority targets; the Spawns are `type=add` and count only in `dps`.

**Profilesets** need two lines, or they silently go wrong:
- `profileset_main_actor_index=2`: actors 0 and 1 are the bosses Ithraz and Vexhul. Without it
  the profileset is applied to Ithraz.
- `profileset_metric=prioritydps,dps`.
- A profileset name containing `.` is dropped without an error.

Variants of the fight: `twinfangs_ref.simc` (one real pull, for validation only),
`twinfangs_p10.simc` / `_p90.simc` (short / long Spawn lifetimes, for robustness).

## The fight, as scripted

Medians over 30 kills sampled from the top-200 world rankings, all classes. Every scheduled
anchor has a population sd of 0.08s across those pulls.

| event | time | how it is scripted |
|---|---|---|
| Heroism | 0.1s | `override.bloodlust=1` |
| Spawn of Vexhul waves | 34 / 95 / 189 / 250 / 344.1s (+0/+1/+2s) | one `adds` raid event per Spawn, `duration=` = measured median life (11–15s) |
| Vile Flood, bosses split | 133.5 / 288.5s, 24s | `move_enemy` Ithraz to (−15,−25) |
| Vexhul dies | 385.9s | `invulnerable` + moved to x=500 |
| Fight end | 402s | `fixed_time=1`, no length variance |

- **Geometry.** This is why the script exists. Bosses are stacked at (0,0), and the Spawns are
  stacked at (−15,25), outside every splash radius. In the log, Starfire and FoE cast on a boss
  hit both bosses and never a Spawn, and Lunar Bolt cast on a Spawn hits all three Spawns.
- **Boss amp 1.135×** relative to a Spawn, from a raid-applied debuff:
  `vulnerable,multiplier=0.135`. The multiplier is the *increase*; 1.135 would mean 2.135×.
- **Raid buffs:** every Droptimizer buff except Power Infusion. Bloodlust, Arcane Intellect,
  Fortitude, Mark of the Wild, Battle Shout, Mystic Touch, Chaos Brand, Skyfury, Hunter's Mark,
  Bleeding.
  - Power Infusion stays off on purpose. The APL's `invoke_external_buff,name=power_infusion`
    never fires, because none is configured.
  - The script also sets the three `midnight.crucible_of_erratic_energies_*` options.
- **Not modelled:**
  - Barbed Bulwark: excluded on purpose, everywhere.
  - Broodlings of Ithraz: ~3.4M in the log, mostly Starfall collateral.
  - Movement.
  - A 6th wave: only 5/30 kills reach it.

## The actor

`funkitty_current.simc` = `funkitty_v4.simc` + Potion of Recklessness + Vantus. Gear corrections,
each validated against a real log's stat sheet:

- **Talents are the field's, not the export's.** The export carries an M+ build. The modal loadout
  of 199 top Twin Fangs parses is stored in `field_loadout.json`. The only real split is
  Orbit Breaker 78% vs Sundered Firmament 22%.
- **Aqirbane Reliquary** (neck) needs
  `stats=2199sta_101crit_101haste_101vers_101mastery`. Simc otherwise gives 404 crit.
- **Crafted stat pairs are bonus ids.** 8790 crit/haste, 8791 crit/mastery, 8792 haste/vers,
  8793 mastery/haste, 8794 mastery/vers, 8795 crit/vers. `crafted_stats=` is ignored.
- **Haste food** is `enchant_haste_rating=71`, folded into the 91 haste.
- **Rite of the Hash'ey** has no simc handler. It is modelled as `enchant_id=0` plus measured
  constant stats: +68 crit, +38 mastery, +20 haste, +5 vers.
- **Vantus Rune: Tides** (spell 1303171, rank 3) is +162 versatility. Simc has no vantus option,
  so `enchant_versatility_rating=167` = 162 + Rite's 5.
- **Upgrade tracks are bonus ids.** Legs are still Myth 4/6 (12852); 6/6 is 12854. Myth
  1–6/6 = 12849–12854, Hero 1–6/6 = 12841–12846.
- **Trinkets:** Freightrunner's Flask and Gebbo's Bottomless Bag.
- **An item simc does not know** (e.g. Kith'ix, 12.1.5): `stats=` override on a same-slot item id.
- **A trinket simced for its stats only:** empty slot plus `enchant_intellect=`. Any real trinket
  id brings its own effect along.

Stat weights (boss DPS per rating, v2 actor, older but same shape): Int 80.7, Mastery 55.7,
Crit 53.1, Vers 46.3, Haste 41.1. Mastery leads, which is why Recklessness wins over Light's
Potential.

## The APL: `apl_plan.simc`

simc's default Balance APL (Elune's Chosen) with two layers on top:

1. **Model B wave routine.** At each wave: Moonfire on two Spawns, Sunfire on one, and FoE stays
   on the bosses. Filler stays on the bosses. Every boss-side dot line carries `!target.is_add`.
2. **The player's Incarnation schedule: pull / wave 2 / wave 3 / wave 5 (with potion) / 6:00.**
   - It is pinned by `variable.ca_hold`, which is false only for `time<15`, `time>=360`, or a
     fresh wave 2, 3 or 5.
   - The traced casts land at 2.9 / 99.5 / 193.8 / 348.7 / 369.4s. Incarnation has 2 charges.
   - Potions go at pull and wave 5.
   - Freightrunner's Flask gets 4 uses (pull, waves 2, 3, 5).

**Why the schedule matters: on-use trinkets fire only while `ca_inc` is up.** The `use_items` line
is gated on it, so wherever Incarnation lands decides how many times a trinket gets pressed.
`apl_B.simc`, the APL's own schedule (pull / wave 1 / wave 3 / wave 4 / 6:05), gave
the Flask 3 uses and ranked trinkets wrong:

| vs Freightrunner's Flask | apl_B schedule | apl_plan schedule |
|---|---|---|
| Vile Vial of Volatile Venom (120s) | +0.83k | **−0.63k** |
| Hex Lord's Dooming Idol 334 (30s, converts stored stacks) | +2.35k | **+4.23k** |

The player's schedule is also +2.2k over `apl_B` on its own. **Before ranking an on-use trinket
for any other player or boss, pin the cooldown schedule they actually play.**

## Validation and known bias

Model B on `twinfangs_ref.simc` (Shidann's pull, `vP4RTacqbCNzd9JV` fight 9) against that log:

| | log vs sim |
|---|---|
| Boss damage | sim −3.0% |
| Moonfire tick on a boss (non-crit median) | −0.3% |
| Sunfire tick on a boss (non-crit median) | +0.8% |
| Dot casts on Spawns | exact |
| Spawn damage | sim −19%, almost all Moonfire. Eclipse placement around waves is not specified |

The sim is not an upper bound here; it sits ~3% under a top player on boss damage. Effects
under ~0.3k (2× the 10k-iteration error) are noise.

## Reference deltas on this profile (boss DPS, ±0.15k)

On the player schedule. These were measured on an earlier actor revision (Flask, legs 6/6)
with Vantus; older trinket results that predate the schedule fix were not kept — re-run any
trinket comparison on `apl_plan.simc`.

| change | Δ |
|---|---|
| Hex Lord's Dooming Idol 334 for the Flask | +4.26k |
| Idol 321 for the Flask | +1.47k |
| Sash of the Forlorn Vessel 334 | +1.31k |
| Crafted belt 331 mastery/haste (bonus 8793) | +1.30k |
| Vile Vial for the Flask | −0.80k |
| Anything for Gebbo's Bottomless Bag | −7.7k to −13.7k |
| Vantus Rune (+162 vers) | +7.3k |
| Legs Myth 4/6 → 6/6 | +1.4k (measured on apl_B) |

**Findings from the FoE study that predate this profile:**
- FoE on the Spawns loses 4.8–8.0M boss damage in every lifetime scenario.
- Model B's dot routine trades 3.5M boss damage for 5.2M on the Spawns.

## Eclipse at spawn, and banking AP before Incarnation (2026-10-08)

Variants of `apl_plan.simc` (built by hand from the rows below; the variant files were not
kept), 5,000 iterations (±0.21k):

| variant | boss | total |
|---|---|---|
| plan | 297.28k | 328.13k |
| Eclipse held 12s before waves 1 and 4, pressed right after the Spawn dots | +0.27k | +0.55k |
| same + Fury of Elune held to pair with it | +0.08k | +0.16k |
| no paid spender below 90 AP for 8s before Incarnation waves (procs exempt) | **−2.02k** | **−2.85k** |
| same, threshold 70 AP | −0.72k | −0.94k |
| first bank version, which also held free procs (Weft/Warp/Touch the Cosmos) | −3.54k | −5.05k |

- **The plan APL already lands an Eclipse on waves 1 and 4** (39.6s and 249.2s in a traced fight),
  because the 2-charge cadence happens to fit. Forcing it there is a tie.
- **Banking loses, and the field data agrees.** On 109 Incarnation waves in 40 top kills, windows
  entered at <70 AP and at ≥90 AP have the same rate against the player's own average
  (1.76× each, corr 0.17). The field still arrives with ~+11 AP over its own median, so that
  is a habit, not a lever.
- **Trap when writing a hold variant:** wrapping a spender line's condition in
  `(!hold|ap>X)&(...)` also gates its free-proc clauses, which then expire. Exempt `*.react`.
  Also, `a|b|c&!hold` gates only `c`: wrap the original condition in parentheses.
