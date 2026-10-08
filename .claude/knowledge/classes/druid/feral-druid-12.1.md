# Feral Druid — 12.1.0 (live)

Valid as of **2026-10-08**: simc 1210-01, WoW 12.1.0.69299 (hotfix 2026-08-15), live talent feed.
The patch is live, so the plain (non-`/ptr/`) Wowhead tooltip endpoint is correct.

Data behind every number here:

| source | what |
|---|---|
| [data/classes/druid/feral/12_1_talents.json](../../../../data/classes/druid/feral/12_1_talents.json) | full tree with live tooltip text (`tools/raidbots/talent_tree_sync.py --class 11 --spec 103`) |
| [data/sims/12_1/spec_matrix/](../../../../data/sims/12_1/spec_matrix/) | profiles and the scenario matrix |
| census, 2026-10-08 (not kept in the repo) | 139 top Mythic pulls (~20 per boss × 7 bosses): gear, stats, talents, damage by ability and target; per-second damage of 12 top Mythic Sszorak pulls |

The cross-spec comparison is in [dps-specs-boss-profile-12.1.md](../dps-specs-boss-profile-12.1.md).
The class tree is shared with Balance: see [balance-druid-12.1.md](balance-druid-12.1.md) for the
talent-override traps, which apply unchanged.

## The engine: two resources, and half the damage is bleeds

- **Energy** pays for everything. Tireless Energy ×2 adds 20 max energy and +5% regeneration.
  Tiger's Fury (5217) restores 50 and, with Savage Fury, gives +10% haste and +25% energy
  regeneration for 8s.
- **Combo points** (5) are built by Shred, Rake, Moonfire in Cat Form (Lunar Inspiration), Swipe,
  and Feral Frenzy (5 at once). Panther's Guile gives Shred and Moonfire a 25% chance to fill all 5.
- **Finishers** spend them:
  - **Rip** (1079), the bleed.
  - **Ferocious Bite** (22568), which eats up to 25 extra energy for up to +100% damage.
  - **Primal Wrath**, an AoE Rip.

**Over half of the damage is periodic.** On Sszorak 51% of top Ferals' damage is DoT ticks
(Fire 24%, Balance 20%, Frost 15%). The pooled shares are:

| ability | share |
|---|---|
| Rip | 21.5% |
| Ferocious Bite | 16.4% |
| Rake | 9.3% |
| Unseen Predator | 8.4% |
| Shred | 7.2% |
| Bloodseeker Vines | 7.0% |
| Melee | 6.5% |
| Feral Frenzy | 6.5% |
| Bursting Growth | 5.7% |
| Moonfire | 4.7% |
| Zul'jin's Guillotine | 2.1% |

Three consequences:

1. **Bleeds snapshot.** Rake and Rip keep the multiplier they were applied with: Tiger's Fury +15%,
   and a stealth Rake (+60%, Pouncing Strikes). The APL tracks this explicitly
   (`persistent_multiplier>pmultiplier`). It re-applies Rake or Moonfire early only when the new
   snapshot is stronger, and it Prowls or Shadowmelds for a Rake when the existing one is below
   1.6×. Incarnation allows one Prowl in combat.
2. **Damage keeps landing after the cat stops attacking.** A ~9–15s tail of bleeds smooths short
   gaps in melee uptime. It also makes window conversion slow: damage put into a target just before
   a window ticks partly inside it, and damage at the window's end ticks partly outside.
3. **Mastery: Razor Claws** (77493) amplifies bleeds, periodic damage *and* finishers, which is
   most of the kit.

### The payoff talents hang off the finisher

- **Unseen Predator (apex, all four ranks in 130/130):**
  - Ferocious Bite has a 15% chance per combo point to flicker to a target and deliver an Unseen
    Slash. The Slash is reduced if fewer than 5 points or 50 energy were spent.
  - Tiger's Fury guarantees one after 2 builders.
  - Rank 4 raises Rip and Unseen Attack damage by +30%.
  - Logged as **1263660**, the rank-4 entry's spell id, not an "Unseen Slash" id.
- **Sabertooth:** Bite +15%, and its target takes +6% per combo point from your bleeds for 4s.
- **Apex Predator's Craving:** Rip ticks proc a free, max-damage Bite.
- **Wildstalker:** Rip and Rake damage grows **Bloodseeker Vines**, a bleed. A Bite on a vined
  target makes them explode for AoE thorns (**Bursting Growth**, plus Rampancy), and Vigorous
  Creepers adds +4% damage taken on vined targets. Vines and explosions together are **12.7%** of
  the damage.

That is the same pattern as the Mage specs. The finisher (Bite) is the one button nearly every
payoff hangs off, and combo points are the resource that feeds it.

## Cooldowns and the burst clock

| button | cadence | what it does |
|---|---|---|
| Tiger's Fury | 30s, 15s duration (Predator) | +15% to everything, snapshotted into bleeds; a mini-burst twice a minute |
| Feral Frenzy | 30s (45 − 15, Focused Frenzy 99/130) | 5 combo points + a bleed |
| **Berserk** | **120s** (180 − 60, Heart of the Lion), 15s | +15% damage, 1 combo point every 1.5s, builders give 2 |
| **Convoke the Spirits** | 120s (103/130 over Incarnation 27/130) | 4s channel of 16 Druid spells; APL lines it up with Berserk + Tiger's Fury |

The burst is one large block every 2 minutes, opened at the pull. In the sim the first 20s run at
**2.01×** the fight's average, the biggest opener of the five specs measured. The damage timeline
has a dominant period of **121s** (sim) and **125s** in 12 top Mythic Sszorak logs, where the
autocorrelation reaches 0.26, the most periodic spec in that sample.

## Reading the APL (simc `druid_feral.simc`)

- **No hero-tree branch.** Unlike Balance, the hero tree is read inside individual lines:
  `hero_tree.wildstalker` in `aoe_builder`, `hero_tree.druid_of_the_claw` for Swipe spam in
  Berserk. One list, conditions vary.
- **Target count picks the lists:**
  - `finisher` / `builder` when `spell_targets=1`.
  - `aoe_finisher` / `aoe_builder` when there are 2 or more.
  - Primal Wrath is the AoE finisher (`combo_points>=5&spell_targets.primal_wrath>1`).
- **Single-target finisher:** Rip at 5 points while refreshable, but only under Tiger's Fury or if it
  would fall off before the next one. Otherwise `pool_resource,for_next=1` then
  `ferocious_bite,max_energy=1`: the APL pools to a full-energy Bite on purpose. That pooling is the
  3.3% "Waiting" in the sim and is correct play, not idle time.
- **Cooldown plumbing:**
  - `variable.holdBerserk` / `holdPot` hold Berserk for the potion when doing so costs no use.
  - The `*CountRemaining` variables decide trinket timing.
  - `convoke_the_spirits` needs Berserk (or Ashamane's Guidance) and Tiger's Fury, right after a
    finisher.

## What the field plays (census, 139 top Mythic pulls, 2026-10-08)

- **Hero tree: Wildstalker 130 / 139.** Druid of the Claw appears 9 times, 4 of them on Sszorak.
  - Wildstalker's choices: Resilient Flourishing (not Root Network), Twin Sprouts (not Implant).
- **Contested spec nodes:**
  - Convoke 103 vs Incarnation 27.
  - Rip and Tear 74 vs Veinripper 12.
  - Primal Wrath taken in only **69 of 130**: it is an AoE node and drops on single-target bosses.
  - Rampant Ferocity 98, Double-Clawed Rake 26.
- **Gear:**
  - **Abyssal Broodfiend's Bardiche** (268215) in 126 of 139; every pull uses a 2H.
  - Trinkets: **Voracious Heart of Ula'tek** (270175) 128, **Zul'jin's Guillotine Technique**
    (270173) 88, Gebbo's Bag 21.
  - Aqirbane Reliquary 135; 5-piece set in 73, 6 pieces in 28.
  - Weapon enchant: Rite of the Hash'ey 99.
  - Embellishment: Arcanoweave Lining 247 (two per player).
- **Stats:** median secondaries **mastery 36.8%, haste 30.2%, crit 26.5%, vers 4.7%**. Flask of the
  Magisters (mastery) 87, Blood Knights (haste) 33.

### The sim disagrees with the field about mastery (small, unresolved)

Per-point scale factors on the Wildstalker profile:

| | Agi | Haste | Vers | Crit | Mastery |
|---|---|---|---|---|---|
| 1 target | 1.00 | **0.71** | 0.64 | 0.60 | **0.52** |
| 3 targets | 1.00 | 0.72 | 0.60 | 0.62 | 0.54 |

Mastery is the *lowest* secondary in simc, yet it is the field's highest. Tested on the decision the
field actually makes: Flask of the Magisters is the **worst** of the four flasks in simc. Blood
Knights is +1.1k (+0.5%), and Thalassian Resistance and Shattered Sun are both +0.4k (8000
iterations). Balance's weights agreed with its field (see the Twin Fangs gear notes), so this is
not a general simc bias.

Either simc under-values Razor Claws, or the field is following guides that over-value it. Nothing
here separates the two. **It is worth ~0.5%, so do not re-gear over it.** Re-test if a log probe
like Balance's Shooting Stars ÷ Moonfire ratio can be built (a bleed tick ÷ a non-mastery hit).

## The sim profiles

```
cd data/sims/12_1/spec_matrix
../../../../vendor/simc/build/Release/simc.exe base.simc fk_feral_wildstalker.simc tal_feral_wildstalker.simc funkitty_feral_gear.simc
```

`funkitty_feral_gear.simc` is Funkitty's armor, neck and rings from the Twin Fangs actor
(`data/raid/12_1/venomous_abyss/06_twinfangs/sim/funkitty_current.simc`), with all of its
corrections. Leather swaps its primary stat to Agility, so it carries over unchanged. Three
swaps at Funkitty's 334 track:

- the field's Bardiche, with the off-hand removed;
- the field's two trinkets;
- the Agility leg kit (8159) instead of the Intellect spellthread.

**Baseline 206.5k DPS** (1 target, 300s). Funkitty's Balance profile on the same armor sims 199.2k
on the same settings, so as Feral Funkitty is +3.7% at 1 target.

**Validated** (sim 1 target vs 19 top Sszorak pulls), after mapping names:

| | sim | log |
|---|---|---|
| Ferocious Bite | 18.2% | 18.6% |
| Rip + Tear (WCL folds Tear into Rip) | 14.4% | 13.9% |
| Shred | 10.3% | 11.6% |
| Unseen Slash (logged as "Unseen Predator") | 10.2% | 9.5% |
| Feral Frenzy | 7.7% | 9.0% |
| Rake | 9.0% | 7.2% |
| Bloodseeker Vines | 5.6% | 6.2% |
| Lunar Inspiration (logged as "Moonfire") | 5.2% | 4.5% |

Zul'jin's Guillotine reads 4.9% in the sim against 2.4% in the log mean. That is **not** a sim
error: the log mean includes non-wearers. Among the 11 wearers on Sszorak it is 4.17%.

**Druid of the Claw:** `tal_feral_dotc.simc` is the 9-pull majority. That is a *single-target talent
set* (no Primal Wrath, no Rampant Ferocity), so its 1.08× at 2 targets measures the talents, not the
hero tree. With Wildstalker's class and spec tree it is **−2.3% at 1 target, even at 2, +2% at 5**
(`tal_feral_dotc_aoe.simc`). The hero tree is worth less than the spec-tree cleave package, which
costs **4.5% at 1 target** and buys **~18% at 2**.

## What Feral is good and bad at, damage-wise

| shape | Feral (Wildstalker) | reading |
|---|---|---|
| 1 target, 300s | 206.5k, +3.7% over Balance on the same armor (the Mage profiles run on Funkywand's gear, so compare ratios, not levels) | Patchwerk is Feral's best case |
| 2 / 3 / 5 targets | 1.34× / 1.74× / 2.53× | middling; Primal Wrath, Double-Clawed Rake and Bursting Growth do the cleaving |
| 3 adds for 15s every 60s | **1.22×** | the weakest burst-AoE of the five (Fire 1.38×). Rip-based damage needs time on a target, and a 15s add dies before the bleeds pay out. |
| one add for 30s every 90s | 1.11× | same reason |
| 60s fight | 1.33× | the 2.01× opener |
| last 30% of the fight | 0.96× | no execute |
| burst | peak 20s **2.10×**, period **121s** | one big block every 2 minutes, plus Tiger's Fury every 30s |
| movement | **not measurable in simc** | simc's movement event keeps a melee in range, so it reports ~0 loss (0.98× at 20%). The real cost is target reach, and the ranking boards are the only evidence for it (below). |

**On the ranking boards** (normalised per-boss shape, see the cross-spec file):

| boss | Heroic | Mythic | why |
|---|---|---|---|
| **Sszorak** | **1.15** | **1.17** | pure single target, no adds: the Patchwerk case |
| Nek'zali | 1.04 | 1.02 | sequential single targets |
| Explorers | **0.91** | **0.94** | the three explorers spread and swap; 2 targets |
| Nymrissa | 0.93 | 0.93 | separated add waves on a Lair boss |
| Twin Fangs | 0.98 | 0.95 | 2 bosses + short add waves |

The two weakest bosses are the two where targets are spread apart or arrive in short waves. That
is consistent with the reach cost simc can't model, but it is not proven by it.

### Vulnerability windows: Feral's 2-minute clock cannot be moved cheaply

On Sszorak's Dig In (+30% at 100/227/354s for 25s), **0 of 12** top Mythic Ferals put a burst inside
a window:

- DPS inside ÷ outside is **0.99×**, below what a perfectly flat profile would get (1.30×).
- Direct damage reads 0.86× and ticks 0.90×.
- Direct hits still land in 98% of the window's seconds, so melee is *not* being pushed off the boss.
- **Every pull bursts at ~5 / ~128 / ~250s**, which is just *after* each window closes.

Berserk pressed at the pull returns at 120s, after the 100s window opens. Reaching all three
windows means holding the opener until 100s, which costs a whole Berserk cycle on a 330–370s kill.
The field refuses that trade. On a boss whose amp windows do not sit on a 2-minute grid starting at
0, **Feral converts vulnerability worst of the five specs**, while Balance (Incarnation charges)
converted the same window at 2.82×.

The sim does not see this: it places the windows wherever its own cooldowns happen to fall, and
reads Feral's unplanned capture as ~1.0×.

## Reading a Feral log

| ability | logged id |
|---|---|
| Rip | 1079 |
| Ferocious Bite | 22568 |
| Rake | 1822, direct and bleed together. A second "Rake" row, 163505, has no hits or ticks: it is the stealth Rake's stun (Pouncing Strikes), so filter it out of per-cast maths |
| Unseen Predator | **1263660** (the apex rank-4 entry) |
| Bloodseeker Vines | 439531 |
| Bursting Growth | 440122 |
| Shred | 5221 |
| Feral Frenzy | 274838 |
| Moonfire (Cat Form, Lunar Inspiration) | **155625**, not Balance's 8921 / 164812 |
| Zul'jin's Guillotine | 1306604 |
| Swipe | 106785 |
| Ravage (Druid of the Claw) | 441591 |
| Primal Wrath | 285381 |
| Twin Claw | 1271636 |
