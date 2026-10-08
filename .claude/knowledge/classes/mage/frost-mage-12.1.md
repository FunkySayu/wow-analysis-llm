# Frost Mage — 12.1.0 (live)

Valid as of **2026-10-08**: simc 1210-01, WoW 12.1.0.69299 (hotfix 2026-08-15), live talent feed.
The patch is live, so the plain (non-`/ptr/`) Wowhead tooltip endpoint is correct.

Data behind every number here:

| source | what |
|---|---|
| [data/classes/mage/frost/12_1_talents.json](../../../../data/classes/mage/frost/12_1_talents.json) | full tree with live tooltip text (`tools/raidbots/talent_tree_sync.py --class 8 --spec 64`) |
| [data/sims/12_1/spec_matrix/](../../../../data/sims/12_1/spec_matrix/) | profiles and the scenario matrix |
| census, 2026-10-08 (not kept in the repo) | 140 top Mythic pulls (20 per boss × 7 bosses): gear, stats, talents, damage by ability and target; per-second damage of 12 top Mythic Sszorak pulls |

The cross-spec comparison is in [dps-specs-boss-profile-12.1.md](../dps-specs-boss-profile-12.1.md).

## The 12.1 engine: Freezing is the resource, Ice Lance is the only spender

12.1 rebuilt Frost around a target debuff. **Freezing** (1221389) stacks up to 20 on the target,
and **Ice Lance Shatters it**: each stack removed deals 91.54% SP (logged as **Shatter**, 1246949).

**Generators**, many of them:

| source | Freezing applied |
|---|---|
| Frostbolt / Frostfire Bolt | 1, +1 on crit (Frostbite) |
| Flurry | 4 with Improved Flurry |
| Glacial Spike | 3 (+2 with Glacial Chill) |
| Ray of Frost | 8 over the channel |
| Hand of Frost | 1 |
| Glacial Assault comet | 1 |
| Frost Splinters | 15% chance each (Infused Splinters) |

**The spender is Ice Lance**, and nothing else. It Shatters 4 stacks, +1 from Heart of Ice and +1
from Polished Focus (Spellslinger), so 6 per cast for Spellslinger.

Same shape as Fire's Hot Streak and Balance's Astral Power: many generators, one spender. So the
modifiers concentrate on the spender:

- **Fingers of Frost** (15% on Frostbolt, +25% from Frozen Touch, 2 charges) makes the next Ice
  Lance deal 4 stacks' worth of Shatter *without consuming them*.
- **Thermal Void:** consuming Brain Freeze makes the next Ice Lance Shatter 4 more.
- **Brain Freeze** (25%+ on Frostbolt) resets Flurry and gives it +50%.
- **Deep Shatter** (Shatter crit damage +50% of crit chance) and **Improved Shatter** (+50% crit
  chance on Shatter).

**Shatter is 39.0% of the field's damage** (31% on single target, 42% on two). Those last two
talents are why **crit is Frost's best secondary**:

| sim per-point scale factors | Spellslinger 1T | Spellslinger 3T | Frostfire 1T | Frostfire 3T |
|---|---|---|---|---|
| Crit | **0.73** | **0.78** | **0.75** | **0.78** |
| Mastery | 0.67 | 0.68 | 0.62 | 0.66 |
| Haste | 0.54 | 0.58 | 0.62 | 0.59 |
| Vers | 0.55 | 0.55 | 0.55 | 0.54 |

The field matches: median secondaries are **crit 38.0%, mastery 33.4%, haste 21.2%, vers 6.9%**.
Flask of the Shattered Sun (crit) is in 103 of 140 pulls. This is the exact opposite of Fire, where
crit is the worst stat. Gear is not interchangeable between the two Mage specs at the stat level.

**Icicles** changed too. They are now generated passively every 6s in combat (5s with Hailstones),
and 5 of them upgrade the next Frostbolt into Glacial Spike (1300% SP, 13% of the field's damage).
Mastery: Icicles boosts Frozen Orb, Blizzard, Comet Storm and Ice Lance. **There is no Icy Veins in
the 12.1 tree**: Frost has no long damage cooldown.

## The two hero trees are two different specs

| | Spellslinger | Frostfire |
|---|---|---|
| field share | 99 / 140 | 41 / 140 |
| where | everything single-target or add-based (Sszorak, Nek'zali, Sentinels 20/20; Nymrissa 18/20; Vashnik 15/20) | the two permanent-cleave bosses: **Twin Fangs 20/20, Explorers 14/20** |
| burst button | **Ray of Frost**, 2 charges (apex rank 4) with Frigid Focus, Crystalline Refraction, Glaciate, Splinterstorm | **no Ray of Frost at all** (30 of 41 take neither Ray nor Comet Storm); Glacial Shatter, Hailstones, Rimecaster ×2, Piercing Cold |
| apex Hand of Frost | 4 ranks | 3 ranks (the 4th rank requires Ray of Frost) |
| extra engine | Frost Splinters (13–15% of damage): conjured by Frostbolt and Flurry, by Ice Lance per 2 stacks Shattered (Force of Will), and every Ray tick (Splinterstorm) | Frostfire Bolt, Frostfire Empowerment, Duality (Glacial Spike also casts a Pyroblast), Ignite from Frostfire spells (Molten Chill) |
| sim 1 target | **169.2k** | 154.5k (−8.7%) |
| sim 2 targets | 313k (1.85×) | **323k (2.09×)** |

The crossover sits between 1 and 2 targets, which is exactly where the field draws the line.
**Pick by whether a second target is up for the whole fight, not by AoE in general.** On add waves
(3 adds for 15s every 60s) the two are tied at 1.33× and 1.35×.

Apex entry ids, needed to read `talentTree` correctly: **137034 = tier 1** (Shatter has a 10% chance
to summon a Hand), **137033 = tier 2** (2 ranks), **137032 = tier 3** (Ray of Frost summons Hands).
The entry order in the feed is *not* the tier order; a Frostfire loadout of 137033 + 137034 without
137032 is legal, not a broken string.

## Reading the APL (simc `mage_frost.simc`)

```
actions+=/run_action_list,name=frostfire,if=talent.frostfire_bolt
actions+=/run_action_list,name=spellslinger
```

- **The hero tree picks the list**, and the two lists differ in order, not just in buttons.
- **The opener is scripted once.** In `actions.cds`, Ray of Frost, Flurry (with Wintertide) and
  Frozen Orb carry `line_cd=9999`, so they fire exactly once at the pull. That is why Spellslinger's
  first 20s run at **1.85×** its average DPS.
- **Ice Lance gates are tree-specific:**
  - Spellslinger: `ice_lance,if=debuff.freezing.react>=6`. That is exactly one Ice Lance's capacity
    (4 + Heart of Ice + Polished Focus).
  - Frostfire: `ice_lance,if=debuff.freezing.stack>=12`.
  - Both lead with `ice_lance,if=buff.fingers_of_frost.react=2`, spending before Fingers caps, and
    with `flurry,if=buff.brain_freeze.react&buff.thermal_void.down`, so a Brain Freeze is not spent
    while a Thermal Void is still pending.
- **Ray of Frost is clipped in multi-target** (`interrupt_if=...active_enemies>=2&tick_time>gcd.remains`)
  unless the 4th apex rank is taken. Ray is a channel, and Frost is giving up its later ticks for
  GCDs (see [combat-system.md](../../game/combat-system.md) on channels).
- `actions.movement` ends both lists: Blink, then instant Blizzard (Freezing Rain), Ice Nova /
  Cone of Cold, then Ice Lance. Frost's movement plan is "Ice Lance", which is cheap. The sim loses
  only 2–3% DPS at 20% of the fight moving.

## What the field plays (census, 140 top Mythic pulls, 2026-10-08)

- **Gear:**
  - Jan'thrazet + Aln'hara Lantern (109/140) or Aln'hara Cane (2H, 30).
  - Trinkets: Gebbo's Bottomless Bag 121, Freightrunner's Flask 73, Wavecaller's Seastone 53.
  - Aqirbane Reliquary 132; 4-piece in 78 pulls, 5 pieces in 61.
  - Weapon enchant: Rite of the Hash'ey 85 vs Acuity of the Ren'dorei 43.
  - Embellishments: Arcanoweave Lining 167 and Hunter's Ritual Stone 100.
- **Damage composition (pooled):**

  | ability | share |
  |---|---|
  | Shatter | 39.0% |
  | Glacial Spike | 13.1% |
  | Flurry | 9.3% |
  | Frost Splinter | 9.1% (Spellslinger only) |
  | Ray of Frost | 8.0% |
  | Frozen Orb | 6.6% |
  | Ice Lance | 4.5% |
  | Hand of Frost | 3.3% |
  | Frostfire Bolt / Ignite | 2.1 / 1.9% (Frostfire only) |
- **Off-boss share:** Nymrissa 41.0%, Vashnik 37.8%, Sentinels 22.2%, Nek'zali 17.1%, and 0–0.4%
  on Explorers, Sszorak and Twin Fangs.

## The sim profiles

```
cd data/sims/12_1/spec_matrix
../../../../vendor/simc/build/Release/simc.exe base.simc fw_frost_spellslinger.simc tal_frost_spellslinger.simc funkywand_gear.simc
../../../../vendor/simc/build/Release/simc.exe base.simc fw_frost_frostfire.simc   tal_frost_frostfire.simc   funkywand_gear.simc
```

Same gear file as Fire (Funkywand, 2026-09-30, ilvl 324.9), the field's node-majority loadout per
hero tree, and Flask of the Shattered Sun.

**Spellslinger is the most faithfully modelled spec of the three.** Sim 1 target vs 20 top Sszorak
pulls:

| | Shatter | Splinter | Ray | Glacial Spike | Frozen Orb | Flurry | Ice Lance | Hand of Frost |
|---|---|---|---|---|---|---|---|---|
| sim | 32.5% | 14.5% | 13.4% | 11.6% | 7.5% | 7.1% | 5.8% | 4.7% |
| log | 31.4% | 13.3% | 13.5% | 12.3% | 7.4% | 7.8% | 5.5% | 4.4% |

**Frostfire matches on the 2-target sim** vs 20 Twin Fangs pulls. Shatter is 40.4% vs 41.9%,
Ice Lance 3.2% exact, and Frozen Orb 2.7% vs 2.9%. The sim splits out Flash Freezeburn (4.2%),
Duality's Pyroblast (3.5%) and Frostfire Empowerment (1.7%), none of which appear as separate lines
in the logs. Glacial Spike reads 21.3% logged against 16.1 + 4.2 + 3.5 = 23.8% in the sim, so WCL
very probably folds them into Glacial Spike. That is plausible but **not verified**.

Validating a cleave build against a 1-target sim is the trap here: the same Frostfire comparison
against the 1-target run read Shatter 32% vs 42% and looked like a model failure.

## What Frost is good and bad at, damage-wise

| shape | Spellslinger | Frostfire | reading |
|---|---|---|---|
| 2 targets | **1.85×** | **2.09×** | the best 2-target scaling of the five specs measured; nothing else exceeds 1.44×. Splitting Ice puts Flurry and Frostbolt on a second target at 50%; Fractured Frost does the same for Ice Lance. |
| 3 / 5 targets | 2.19× / 2.87× | 2.42× / **3.08×** | still leads at 5 |
| one add for 30s every 90s | 1.29× | **1.35×** | the best of the five at "sometimes a second target" (Fire 1.12×, Balance 1.13×) |
| 3 adds for 15s every 60s | 1.33× | 1.35× | strong, but behind Fire's 1.38× |
| 60s fight | 1.38× | 1.19× | Spellslinger's scripted opener; Frostfire is the flattest spec measured |
| 20% of the fight moving | 0.97× | 0.98× | Ice Lance, Flurry, Frostfire Empowerment procs: as mobile as a caster gets |
| burst | peak 20s 1.96×, mostly the opener | peak 20s **1.50×** | **no periodic burst**: no Icy Veins; Ray's charges are the only lever. In the logs the autocorrelation of the damage timeline is 0.12 (Fire 0.19, Feral 0.26): there is no clock. |
| last 30% of the fight | 0.91× | 0.93× | no execute talent |

**On the ranking boards** (normalised per-boss shape, see the cross-spec file):

| boss | Heroic | Mythic | why |
|---|---|---|---|
| **Twin Fangs** | **1.21** | 1.13 | two permanent bosses: the Frostfire case |
| **Explorers** | 1.12 | **1.14** | two bosses for the whole fight |
| Sentinels | 1.05 | 1.08 | |
| Nymrissa | **0.88** | **0.87** | separated add waves |
| Sszorak | 0.90 | 0.90 | pure single target |
| Vashnik | 0.93 | 0.89 | burst adds: Frost takes 37.8% off-boss against Fire's 55.8% |

### Vulnerability windows: charges make Frost flexible

On Sszorak's Dig In (+30%, 100/227/354s), 11 of 12 top Mythic Frost pulls put their best 10s
inside the first window. They converted it at a median **1.84×** inside-vs-outside (all 12:
1.70×, IQR 1.30–1.99). Frost can do this without a long cooldown because Spellslinger's burst
is two banked Ray of Frost charges plus Frozen Orb (60s). A charge-based burst can be pointed at a
window, and a fixed 2-minute cooldown cannot (compare Feral, 0 of 12).

## Reading a Frost log

| ability | logged id | note |
|---|---|---|
| Shatter | **1246949** | the damage from Ice Lance consuming Freezing; it is not Ice Lance's own id |
| Ice Lance | 30455 | |
| Glacial Spike | 199786 | |
| Flurry | 44614 | |
| Frost Splinter | 443722 | |
| Ray of Frost | 205021 | |
| Frozen Orb | 84714 | |
| Hand of Frost | 1262769 | |
| Frostfire Bolt | 431044 | |
| Ignite (Frostfire) | **1262887** | not Fire's 12654 |
| Comet Storm | 153596 | |
| Frostbolt | 116 | |
