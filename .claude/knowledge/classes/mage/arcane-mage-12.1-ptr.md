# Arcane Mage — 12.1 PTR, Sunfury single-target

Sources: Raidbots report `38BorEbHSzMrsQmgug8J2B` (sim), WarcraftLogs `vAtQGNpDqJHyw9mn`
(actual play, character "Funkywand"), talent tree dump
[data/classes/mage/arcane/12_1_ptr_talents_raidbots.json](../../../../data/classes/mage/arcane/12_1_ptr_talents_raidbots.json).

**Sim and log are the same character on the same gear** — head/shoulder/chest/hands/legs
(271564/271562/271567/271565/271563), both trinkets (250215, 270164) and weapon (258047)
match between the simc profile and the logged `CombatantInfo`. So 161,530 DPS is a valid
benchmark for this character, not a generic one.

## Build — now fully resolved (no longer a gap)

The previous note flagged the talent allocation as unresolvable from the opaque loadout
string. **It is resolvable**: WCL's `events(dataType: CombatantInfo)` returns a
`talentTree` array of `{nodeID, id, rank}` that maps 1:1 onto the `id`/`entries[].id` pairs
in the Raidbots talent dump. Confirmed: **Sunfury, all 14 hero nodes**, apex **Prismatic
Bolt** (all 3 ranks), and the spec picks that drive the rotation — Arcane Salvo, Spellfire
Salvo, Arcane Singularity 2/2, Intuition, Focusing Crystal, High Voltage, Amplification,
Overpowered Missiles, Orb Barrage, Charged Orb, Expanded Mind, Impetus, Eureka, Improved
Clearcasting, Concentrated Power, Prodigious Savant 2/2. Gear carries **5 pieces of setID
2060** → 4pc active, which is what arms the `cumulative_power` gate in the APL.

## The actual engine: Arcane Salvo, cap 25

Salvo caps at **25** (20 from base Arcane Salvo's "3%, up to 60%", +5 from **Spellfire
Salvo**). Verified empirically — `maxStack=25` on buff 1242974 in every logged fight.

Generation is *not* spread evenly across the kit (the earlier note said "nearly every cast
builds Salvo" — misleading). In practice:

| Source | Salvo per cast |
|---|---|
| **Arcane Missiles** | ~11–15 (7 waves w/ Amplification, ×1.5 from Focusing Crystal's 50%/wave) |
| **Overpowered Missiles** proc | **straight to 25** ("generates maximum stacks") |
| Prismatic Bolt | +4 (Expanded Mind) |
| Arcane Blast | +2 (Expanded Mind) |
| Arcane Orb | +1 |

So **Arcane Missiles is the generator**; Blast/Prismatic Bolt are the fine-tuning top-off
that bridges ~21 → 25. Missiles is also the main *Arcane Charge* generator (High Voltage,
50%/wave ≈ 3.5 charges/channel), not Arcane Blast.

**Arcane Barrage is the only spender, and it pays out four ways at once:**
1. Salvo damage bonus (3%/stack, linear in stacks consumed)
2. **Prismatic Bolt: 2% per stack consumed** (1% base + 1% from the third apex node) → 50%
   at 25 stacks. Corrects the earlier note's "~1%".
3. **Glorious Incandescence: 1 Meteorite per 5 stacks consumed** (linear)
4. **Orb Barrage: 4% per stack *held*** → guaranteed free Arcane Orb at 25

Three of those four are **linear in stacks consumed**, so dumping early is *not* a
proportional loss. The one genuinely non-linear payoff is **Intuition: +25% Barrage damage
only on reaching max stacks.** That plus the fixed per-cast GCD cost is the entire argument
for holding to 25.

## Why the APL looks the way it does

```
actions.sunfury=arcane_missiles,if=buff.clearcasting.react&buff.arcane_salvo.stack<12,chain=1
actions.sunfury+=/prismatic_bolt,if=((!set_bonus.midnight_season_2_4pc)|buff.cumulative_power.stack=8)&buff.arcane_soul.down
actions.sunfury+=/arcane_barrage,if=(buff.arcane_charge.stack=4&((...|buff.clearcasting.react)&buff.arcane_salvo.react>=12)|((buff.arcane_surge.remains>gcd.max|buff.arcane_surge.down)&buff.arcane_salvo.react=25))|buff.arcane_soul.up
actions.sunfury+=/prismatic_bolt
actions.sunfury+=/arcane_orb,if=buff.arcane_charge.stack<1
actions.sunfury+=/arcane_pulse,if=...
actions.sunfury+=/arcane_blast
```

- The **`arcane_salvo.stack<12` gate on Missiles** exists because a channel adds ~11–15;
  starting one above 12 overflows the 25 cap.
- Barrage therefore has two legal triggers: **Salvo=25** (the Intuition path), or
  **Salvo≥12 with Clearcasting banked** (a release valve — Clearcasting is unusable while
  Salvo≥12 blocks Missiles, so you dump to unblock it).
- **Arcane Orb is gated to `arcane_charge.stack<1`** — it is a charge fallback, not a
  damage cooldown. The sim hard-casts it ~1×/300s; Orb Barrage supplies ~48 free orbs.
- **Prismatic Bolt is held to Cumulative Power 8/8** under the 4pc. Holding the proc ~3s is
  correct, not a mistake — it replaces your next Arcane Blast and does not expire.
- **Arcane Soul** (Memory of Al'ar, 4s, lands a fixed **17.4s after Arcane Surge**): Barrage
  grants +5 Salvo and **does not consume**, so every Barrage in the window fires at whatever
  Salvo you brought in. Entering at 25 vs 0 is the whole value of the window.

## Reading the gap between sim and play (the useful metric)

Comparing raw cast counts is a dead end — the player out-casts the sim (210 vs 198 GCDs,
~0.12s median delay after a channel). The metric that separates them is **Salvo per
Barrage**:

| | Sim | Logged play (5×300s) |
|---|---|---|
| non-Soul Barrages / 300s | 48 | 58 |
| avg Salvo consumed per Barrage | 22.4 | 19.7 |
| Barrages with **Intuition** up | **65%** | **46%** |
| Arcane Blast / 300s | 31 | 21 |
| Arcane Orb hard casts / 300s | 1 | 8 |

Same total Salvo throughput, spread over ~10 more Barrage GCDs. The sim spends those GCDs
on Arcane Blast to bridge 21→25; the player spends them on extra Barrages and Arcane Orbs.

**Correction to the earlier note**, which claimed the costliest mistake is a *missed or
late* Barrage. In the logged data the dominant error is the opposite — Barrage fired **too
early**, below max Salvo. Overcapping does happen too (Salvo sits at 25 ~22s/fight, and 18%
of Missiles casts start above the `<12` gate), so the real failure mode is *cycle timing*,
not a one-directional bias.

## Trust boundaries worth remembering

- The sim's damage table shows **no Arcane Phoenix damage at all**, while the log shows
  Phoenix at ~2.8–2.9%. simc's PTR model of the Sunfury capstone is incomplete here — don't
  read Phoenix's share across sim/log as like-for-like.
- **Correction to an earlier version of this note**, which claimed "Arcane Orb at 0.06%" in
  the sim. That figure was itself a data-reading bug, of exactly the kind this file warns
  about elsewhere: simc's `stats` list splits some abilities into a parent "cast wrapper"
  entry with **no damage fields at all** (Arcane Orb's top-level entry, id 153626, has
  `total_amount: null`) and a separate nested `children[]` entry that carries the real
  `total_amount`/`portion_amount` (id 153640, "arcane_orb_bolt"). Reading only the top level
  reports 0% for Arcane Orb and Touch of the Magi alike; both are wrapper-shaped. Once the
  children are included, the sim shows Arcane Orb at **~3.1%** — matching the logged ~3.2–3.4%
  closely. Re-verified against raidbots report `38BorEbHSzMrsQmgug8J2B` in
  `backend/wow_analysis/raidbots_client.py` (`_flatten_stats`). Arcane Orb is *not* a
  meaningfully mis-simmed ability; Arcane Phoenix still is.
- WCL `Buffs`/`Casts` events carry no Arcane Charge resource data; charge state must be
  inferred, so avoid claims that depend on exact charge counts.
- **PowerShell gotcha that silently corrupted two analysis passes:** variables are
  case-insensitive, so a loop counter `$soul` overwrites a spell-ID constant `$SOUL`. Also
  `,@(...)` around a returned array nests it and silently disables downstream
  `Where-Object` filters. Sanity-check every extract against a known cast count before
  drawing conclusions from it.

---

# 12.1 LIVE — Season 2 audit (2026-08-22)

Report `AgzVT69J8kKRWGrt` (Funkywand: 7 Venomous Abyss normal kills + 4 M+10 dungeons).
**This patch is now live, not PTR** — simc 1210-01 targets `12.1.0.69299 Live`, so
`vendor/simc/build/Release/simc.exe` can sim it directly and Raidbots is no longer required.

## The two tier sets, and which bonus actually matters

Two mage tier sets coexist and are easy to confuse. Resolve them by **setID**, not by name:

| setID | Set | Source | Arcane 2pc | Arcane 4pc |
|---|---|---|---|---|
| **1983** | Voidbreaker's Accordance (S1) | icon `…raidmagemidnight…` | +1% crit per Arcane Charge | +10% Arcane crit damage |
| **2060** | Primal Leywarden's Attire (S2) | icon `…raidmageulatek…`, **Catalyst** | **+1 Missiles wave, +5% Missiles damage** | `cumulative_power` (the APL gate) |

Get the bonus text from `nether.wowhead.com/tooltip/item/<id>` — a set piece's tooltip lists
**all six bonuses for all three specs**, which is far cheaper than hunting a guide.

**The S2 2pc is worth +13.1%; the 4pc adds only +4.4% more.** That inverts the usual
assumption that the 4pc is the prize. Reason: Missiles is ~30% of damage *and* the generator
for both Salvo (Focusing Crystal, 50%/wave) and Arcane Charges (High Voltage, 50%/wave), so
an extra wave accelerates the whole cycle — the sim drops 9% of its Arcane Blast filler GCDs
and gains 4% more Barrages. Never quote the 2pc as just "+5% Missiles".

### Counting Missiles waves is the clean empirical test for the 2pc

Don't infer set bonuses from stat sheets. Pull `DamageDone` events for **ability 7268**
(Missiles *impact* — `5143` is the cast/channel and returns zero damage events), sort
timestamps, and split into channels on gaps > 700 ms. The histogram is multimodal at
**multiples of the base wave count**, because multi-target cleave stacks whole channels:

- 0pc → modes at **7 / 14 / 21 / 42**
- 2pc → modes at **8 / 16 / 24 / 32**

Verified across four independent players. simc agrees exactly (`num_ticks / num_executes`
= 6.98 → 7.97). Read the **mode**, not the mean — the mean is meaningless here because it
mixes 1-, 2- and 6-target channels.

### simc implements only some of these

`grep "MAGE_ARCANE, MID1\|MAGE_ARCANE, MID2" engine/class_modules/sc_mage.cpp` — simc has
`MID1 B2` and `MID2 B4` explicitly, **no `MID1 B4`**. So a sim that swaps away the S1 4pc
loses nothing in simc, and any claim about the S1 4pc's real value is unverified. An
attempted empirical test (avg-crit ÷ avg-nonhit on 6k Missiles impacts) was **inconclusive**
— 2.23 ±0.07 with the 4pc vs 2.17 ±0.11 without, overlapping. Hit-size variance swamps it;
don't retry this without a fixed-damage ability.

## Gear finishing is checkable from the log, and worth ~10%

`CombatantInfo.gear[]` carries `permanentEnchant` and `gems` per slot. Funkywand had **0 of
each on all 15 slots**; all 7 sampled peers had 6–9 enchants and 2–7 gems. Sim: enchants
+6.7%, +gems +10.3% total.

**Always control-test before calling this a finding** — run the same extract over every
player in the report. If everyone reads 0, it's a logging gap; if only your target does,
it's real. The standard load-out (confirmed against simc's own `MID2_Mage_Arcane_Sunfury`
profile) is **8 enchants** — head, shoulders, chest, legs, feet, both rings, weapon — and
**7 gems**. A weapon *rune* is a `temporaryEnchant` and is reported separately; its presence
does not imply permanent enchants exist.

## Stat weights: item level dominates, secondaries barely matter

Scale factors on the target profile (LW 2pc, enchanted, gemmed), per point of rating:

```
Int 47.21  |  Vers 23.30 > Mastery 21.55 ≈ Crit 21.35 > Haste 20.70
```

Intellect is **2.2× any secondary**, and the four secondaries sit within 12% of each other.
Consequence for gearing advice: **take the higher item level, always**; scoring a whole BiS
list on secondary distribution moves it well under 1%. A list built entirely on "haste is
king" ranked last-in-slot on nearly every slot yet was still only 1–2% from optimal per item.
Say that plainly rather than implying the picks were wrong.

## Rotation: what's solved and what isn't

Salvo discipline **improved substantially** vs the earlier PTR note (46% → 52–71% of Barrages
at max Salvo; sim benchmark 65%) and now **beats most ranked peers**. It is no longer the
bottleneck — do not re-report it as one.

The live errors, in impact order:

1. **Arcane Soul entered near-empty.** Soul lands a metronomic **17.4 s after Arcane Surge**
   (median, n=75, zero spread). Barrages inside it don't consume Salvo, so they all fire at
   the stack count you enter with. **55% of raid windows had a Barrage within 3 s before the
   window opened**; mean entry 11.0 of 25, only 14% at max. Dungeons are better (24%, 14.0).
2. **Clearcasting capped** 360 s / 2624 s in raid (13.7%) with **209 procs hard-wasted**
   (refresh at 3/3). This is the flip side of holding Salvo: Missiles is gated to
   `arcane_salvo.stack<12`, so high Salvo blocks Clearcasting spending. The APL's release
   valve (Barrage at Salvo ≥12 *when Clearcasting is banked*) is the intended fix.
3. **Post-channel hesitation.** Median 0.00 s (most chain perfectly) but 23% exceed 1 s.

Already correct, don't flag: **Touch of the Magi chaining** (off-GCD, wants `prev_gcd`
Prismatic Bolt or Barrage — 91% raid / 98% dungeon), **ToM×Surge alignment** at 49–51%
(with 45 s and 90 s cooldowns, every *other* ToM is the ceiling — 50% is perfect, not half
right), raid CD usage 88–100%.

Measured cooldowns: **Touch of the Magi 45 s, Arcane Surge 90 s** (min observed interval
45.4 s / 91.6 s).

## Peer comparison: compare execution, never raw DPS

Peer kills ran 30–50% shorter than Funkywand's, which inflates their DPS regardless of play —
a 2× DPS gap on Lost Explorers was almost entirely kill speed. The comparable metrics are
Salvo-per-Barrage, %-at-25, and **damaging casts per minute**. The one real deficit was
cast rate (37–41 vs 45–46/min), which traces to median GCD 1.175 s vs 1.104 s and a flat
25th-percentile GCD — i.e. straight back to the missing enchants/gems/set bonus.

Find peers via `worldData.encounter(id:).characterRankings(className:"Mage", specName:"Arcane",
difficulty:, metric: dps)`. **`bracketData` is not equipped item level** — it disagreed with
the computed average by 30+ levels on one player. Compute ilvl yourself from `CombatantInfo`.

## Building a KeystoneLoot export (not just parsing one)

The skill only decodes. To **encode**, mirror `Favorites:Export` exactly:

```python
obj = {"62": [{"itemId": i, "tier": t}, ...]}          # tier 3 = BiS, 2 = Must have
"KeystoneLoot:v3," + base64.b64encode(zlib.compress(json.dumps(obj,separators=(',',':')).encode(),9)).decode()
```

Round-trip through the skill's own parser before shipping it. Two things that matter:
- Tier set pieces are **not in any boss loot table** — they live in `data/catalyst.lua`
  (`[271564]={classId=8,slotId=0}` etc.). That is why a zone-derived report shows them with
  no source and a report built only from boss tables silently omits the whole tier set.
- `data/classes/druid/balance/12_1_loot_sources.json` slot IDs use the addon's `EQUIP_LOC_SLOT`:
  `0 head, 1 neck, 2 shoulder, 3 back, 4 chest, 5 wrist, 6 hands, 7 waist, 8 legs, 9 feet,
  10 weapon (1H/2H/ranged all share this), 11 off-hand, 12 finger, 13 trinket`.
  Slot 10 mixing 1H and 2H is why a naive "one BiS per slot" check can't see a
  staff-plus-off-hand conflict.

## Environment note

Windows Python is only the Store stub and `backend/` is a **WSL** venv (`home = /usr/bin`),
unusable from Git Bash. Working combination: `wsl.exe -d Ubuntu -e python3 <script>` from the
Bash tool — the repo is mounted at the same relative path, so `scratch/...` just works. Run
`simc.exe` from PowerShell (and never redirect its stderr; see building-reports.md).

## Run the checks, don't re-derive them (added 2026-08-23)

Everything below is implemented in **[tools/warcraftlogs/](../../../../tools/warcraftlogs/)** — see its README for the
full table. Never hand-roll one of these again; run it and read the output:

```bash
wsl.exe -d Ubuntu -e python3 tools/warcraftlogs/run.py <check> -r <REPORT> -a <ACTOR> -f raid|dungeon|<ids>
# checks: list salvo soul clearcasting tom-target cooldowns cd-usage waves gaps gear all
```

Events and the OAuth token cache to `.wclcache/` (gitignored), so only the first run costs
API points. Adding a check = one function in `checks/mage_arcane.py` (or `checks/common.py`
for a spec-agnostic one) registered in that file's own `CHECKS` dict — see the README.

## Touch of the Magi targeting (`tom-target`)

ToM stores a share of damage dealt **to the debuffed target** and detonates at the end, so
damage into anything else during the window is not stored. Three numbers, and conflating
them produces a wrong conclusion:

| | raid (93 windows) | dungeon (163 windows) |
|---|---|---|
| damage into the ToM'd target | 76.9% | **45.0%** |
| active time *off* the target | 4.1% | 5.9% |
| windows with a >1.5× bigger target being hit | 4% | 8% |

**The low dungeon number is not a targeting error.** Time off-target is only ~5% and
placement is right 92–96% of the time — the dilution is cleave hitting everything else,
which is inherent to AoE and not something to "fix" by dropping cleave. The actionable
part is the placement subset: 17 windows across one session put ToM on a much smaller
target while a far bigger one was being hit (worst: a 730k-HP Bubblefin Shorerunner on
Nymrissa while the 237M boss was up; a 4.8M add in Ruby Life Pools while Kokia Blazehoof
at 47.7M was being damaged).

Multi-target *bosses* are where the raid loss concentrates — Lost Explorers 46%, Twin Fangs
60%. Worst single windows: 10.2% (Trader Gebbo), 19.0% (Blood of Ula'tek), 28.3% (Vexhul).

## Cooldown alignment (`cooldowns`)

**Measure lust coverage as buff overlap, not "was the cast inside the window."** A Surge
cast one second before lust lands is perfectly aligned; a cast-based test scores it as a
miss and makes good play look random. This exact bug produced a "NOT aligned — roughly
random" verdict on a first pass that the overlap metric then contradicted.

Second trap: **Arcane Surge lasts ~18s against a 40s lust, so ~45% coverage is the
ceiling.** 43% is a perfect window, not a half-failure.

Measured: raid **6/7 lust windows at the ceiling**; dungeons **11/15**. All four dungeon
misses and the single raid miss have the same shape — Surge was spent 31–59s before lust
dropped, so it was still on cooldown. Lust timing is usually predictable, so those are
recoverable by banking.

Pack coverage in keys (pull = player damage split on >12s gaps; pack HP = sum of enemy
`maxHitPoints`; danger = friendly damage taken in the pull):

- Arcane Surge landed on **20 of 21 top-quartile packs**; the one miss was on cooldown.
- **Zero pulls anywhere where Surge was off cooldown and simply not used.**
- The real dungeon loss is idle cooldown: **17–29% of each run** (203–405s) with Surge
  available and nothing worth hitting. Raid is 6–12%. That gap is dungeon pacing, not
  a rotation error, and it is where the remaining margin actually sits.

Getting enemy HP: `events(..., includeResources: true)` attaches `hitPoints` /
`maxHitPoints` **of the target** to every damage event, plus a `buffs` string of the
source's active auras. That is the cheapest route to pack size/danger — no separate
enemy query needed.

## Arcane Soul is a deterministic clock, not a proc

Re-measured over 131 windows: the Arcane Surge → Arcane Soul lag is **17.4s with p10 = p90
= 17.4s** — zero spread. It can be counted, and there is no reaction component.

Updated on the full session (the report kept growing during analysis — re-pull `list`
rather than trusting an earlier fight set):

| | raid (48 windows) | dungeon (83 windows) |
|---|---|---|
| mean Salvo on entry | 11.8 / 25 | 15.9 / 25 |
| entered at 25 | 19% | 35% |
| entered below 15 | 67% | 41% |
| Barrage fired <3s before the window | **52%** | 18% |

Clearcasting capped: raid 609s of 4536s (13.4%) with **347** procs hard-wasted;
dungeon 1298s of 9489s (13.7%) with **636**.

---

# Diagnosing a low parse (Heroic Venomous Abyss, 2026-09-04)

Report `JX1Vd49kL63QPwbY`, Funkywand, ilvl 316, 14-man Heroic. Tooling:
`tools/warcraftlogs/checks/mage_peers.py` (`bar` → `peers-arc` → `peers-buffs`), written from this
investigation. Working extracts in `scratch/coiled_altar/`.

## A parse percentile is not comparable between bosses

| | DPS | parse | encounter top-500 p50 | you / p50 |
|---|---|---|---|---|
| Sszorak | 172,305 | **92** | 186,594 | 92.3% |
| The Coiled Altar | 170,521 | **36** | 227,218 | 75.0% |

Same night, same gear, **1% less DPS, 56 fewer percentile points.** The Coiled Altar's
Arcane bar is **22% higher** than Sszorak's — it has a ~35s intermission amplify window
and a second permanent target, and Sszorak has provably zero adds. The comparable number
is DPS against that encounter's own pool median: the real regression is ~17 points, not
56. **Always establish the bar before diagnosing the player.**

The amplify window is directly visible in raw hit sizes and is worth measuring that way:
non-crit Arcane Blast on that pull sat at 47–66k for the whole fight and jumped to
122–175k for exactly 233.9–268.8s, which is precisely the `Ghastly Regeneration`
(1304033 / 1304498) window on Zul'jan. A fixed-size ability's own hits are a cheaper
amp-window detector than hunting for a vulnerability debuff by name.

## Split DPS into hits/min × damage/hit before blaming anything

The rotation was **not** the problem, and every single-log check said "fine" for the right
reason once compared against peers rather than against the sim:

| | you | ilvl-matched peer median |
|---|---|---|
| hits+ticks / min | 427.7 | 435.3 (−1.7%) |
| GCDs / min | 46.1 | 45.7 |
| GCD uptime (`abc`) | 75.2% | 74.7% |
| Salvo per Barrage | 21.5 | 21.3 |
| Barrages at 25 stacks | 65.5% | 61.6% |
| Barrages below 20 | 25.0% | 32.6% |
| Clearcasting wasted / min | 5.8 | 6.1 |
| **damage per hit** | **23,920** | **34,183 (−30.0%)** |

**75% GCD uptime is normal on this fight** — the peer median is 74.7%. Reading the `abc`
number against a generic "90% is good" heuristic would have sent the whole analysis the
wrong way. Likewise `clearcasting` reporting 46 hard-wasted procs is a *fight-length*
artifact: per minute it is better than the pool.

## Damage per cast falls off in a specific order, and the order is the diagnosis

Arcane Blast −12% · Barrage −20% · Missiles −25% · Prismatic Bolt −32% · ToM −37% ·
Orb −41%. That is exactly the ranking of how much each ability compounds on the Salvo
economy and on amplify windows. **Arcane Blast is the pure stat proxy** — it is the last
line of the APL, so it lands unamplified for everybody; its raw median non-crit was 51,899
vs a peer 66,944–68,712 (−22 to −25%), and −30.7% on Sszorak too, i.e. a constant of the
character rather than anything about the boss.

## What the damage/hit gap actually was

Not itemisation split. Weighted by the file's own scale factors (Int 47.21, Vers 23.30,
Mastery 21.55, Crit 21.35, Haste 20.70), total secondary *value* was only −4.2% despite a
very different mix (haste 1301 vs 1041, mastery 770 vs 552, crit 690 vs 745).
Not talents either — only 3 nodes in the whole tree differed from the pool.

It was buffs and consumables, none of which any rotation check can see:

| | you | peers with it |
|---|---|---|
| Hearty Well Fed (food) | **absent** | 10/12 at 100% |
| Mark of the Wild | **absent** | 12/12 at 100% |
| Blessing of the Bronze | **absent** | 11/12 at 100% |
| Versatility rating | **75** | median 570 |
| Intellect | 3,201 | 3,450 (−7.2%) |
| gems socketed | 4 | 5 (best in pool: 7) |

Mark of the Wild is versatility and the raid *had* a Guardian Druid — it was simply never
cast, which is why the vers rating reads as near-zero rather than merely low. Blessing of
the Bronze needs an evoker in the raid at all, so a 14-man roster loses it through no
fault of the player; separate the two kinds when reporting. Trinket: `270161` Fang of
Umbral Malignance (1.5% of damage) against `270164` Gebbo's Bottomless Bag in 10/14 peers.
Flask was present but a different one (`Flask of the Magisters`, used by nobody in the
pool) — which is why `peers-buffs` prints your own consumables separately: a flask the
pool does not run otherwise reads as no flask at all.

## The one genuine rotation finding, and why it is fight-specific

Arcane Blast at **5.66/min against a peer median of 2.80** — 45 casts where the pool cast
~17. On Sszorak the same pool presses it 3.7/min, so this is not a build difference: The
Coiled Altar supplies more procs and the pool converts them. The largest single block was
**12 consecutive Arcane Blasts, 74.3–86.4s, Clearcasting at 0 stacks and no Prismatic Bolt
proc**, each landing for ~48k against Prismatic Bolt's 391k. Both preceding Barrages
consumed 25 Salvo (≈50% Prismatic Bolt proc chance each), so the drought was partly luck —
but Prismatic Bolt casts/min was −27% and Barrage −10%, and that is where the recoverable
damage on this pull sits.

---

# Windows of opportunity — the layer the peer checks miss

Same pull (`JX1Vd49kL63QPwbY` fight 18). The section above concluded "rotation fine, hits
30% small". That is true and it is **not the whole answer**: a second, independent gap sits
in how the fight's amplify window is exploited. Tooling: `checks/encounter.py`
(`fightmap`, `addvalue`) and `windows` in `checks/mage_peers.py`.

## Derive the fight's structure from the log, don't look it up

`phaseTransitions` + enemy `Casts` + enemy `Buffs` + `masterData.abilities` gives the whole
encounter model without a guide. The Coiled Altar, measured:

| phase | window | raid DPS | vs raid average |
|---|---|---|---|
| P1 Zul'jan | 0–131s | 1.40M | 0.85× |
| P2 Malacrass | 131–231s | 1.30M | 0.79× |
| **P3 intermission** | **231–269s** | **3.43M** | **2.07×** |
| P4 both, Soulbound | 269–477s | 1.66M | 1.00× |

**Score candidate windows with the *raid's* damage rate, not your own** — your own burst
would otherwise detect itself as a boss mechanic. Every bounded enemy self-buff, ranked:
Ghastly Regeneration 2.26×, Soulbinding 2.25×, Deathguard 2.07× (all the same 35s),
Defilement 1.28×, Corrupted Toxin 1.18×, **Axegrinder 0.78×** — the last one is the
negative case, 121s of wandering axes where the raid hits *less*.

Mechanically it is one window with three names: `Ghastly Regeneration` (1304033/1304498)
heals Zul'jan 2%/s for 35s and gives him **+100% damage taken**, while `Deathguard`
(1304028) puts Malacrass at **99% damage reduction** — so the amplify and the "all damage
must go into one target" rule are the same event. Every mage measured, including the low
parse, put 100% of the window into Zul'jan; targeting is not where this is won.

**Amplify windows are visible in raw hit sizes.** Non-crit Arcane Blast sat at 47–66k for
the whole pull and jumped to 122–175k for exactly 233.9–268.8s. A fixed-size ability's own
hits are a cheaper amp detector than hunting a vulnerability debuff by name.

## The metric that survives a gear gap: multiplier over your own background

`background` = your DPS outside the vulnerability window *and* outside Surge/Soul. Every
number below is a ratio to the player's own background, so item level, raid buffs and
fight length all cancel — the one measure a badly geared player can be graded on fairly.

| | you | peer median | range |
|---|---|---|---|
| vulnerability window (38s) | **2.67×** | **3.53×** | 2.46 – 4.16 |
| Surge + Soul windows | **1.99×** | **2.62×** | 1.88 – 2.86 |

A +100% amplify hands everyone 2.00× for pressing nothing. Closing to the peer median is
worth **+4.49M = +5.5% of the pull** (~170.5k → ~180k DPS). This is *additive with* the
30% damage-per-hit gap, not an alternative explanation for it.

Two window definitions were computed and they agree: the shipped `windows` check uses the
38s union (Deathguard 231–269 folded into Ghastly Regeneration 234–269) against the pool's
top 10 and gives 2.67× vs 3.53×; restricting to the exact 34.9s Ghastly Regeneration window
against an ilvl-matched 10 gives **2.94× vs 4.08×**, worth +6.6%. Quote the first; it is the
one that reproduces from the CLI.

**The top parse does not win here.** 한맨 at 263k DPS has a window multiplier of 2.46× —
*below* yours — and wins entirely on background rate (193,562 vs your 137,300). Window
exploitation and background throughput are separate axes, and different players are short
on different ones.

## Placement was right; execution inside the window was not

Cooldown *scheduling* was correct and matched the field exactly — every one of 10 peers and
you put Surge + Soul + ToM + lust into the window. Two things differ:

1. **On-use trinket.** Peers: 4 of 4 uses inside a Surge window, 1 inside the amplify,
   universally. You: 2 of 5 in Surge, **0 in the amplify** — used at 193s and 284s, one
   either side of a 234–269s window, the first use locking out the second by its own 90s
   cooldown.
2. **Cast mix inside the window.** 37 GCDs, of which **7 Arcane Blast** (including six
   consecutive, 251–256s, at ~48k a cast). Peers spend 0–1. Their in-window loop is a clean
   `Prismatic Bolt → Barrage → Missiles → Missiles`. Fight-wide inside Surge: Prismatic Bolt
   7.2% of GCDs vs a peer median of 12.5%, Arcane Blast 8.4% vs 4.2%.

## Adds are not a window here — check before assuming they are

Off-boss damage is **~2% for every mage in the pool** (Spiteful Soulcoiler 0.7–1.9%);
Manifestations of Dread spawn `Unassailable` and are never damaged. So the Twin-Fangs-style
reasoning ("hold cooldowns for the add wave") is simply wrong on this boss, and `addvalue`
exists to settle that in one query rather than by assumption.

## The hold/cast tradeoff, priced

Arcane Surge is 90s; the mechanics it must line up with are not multiples of 90s
(Dreadmarch every ~96s, Toxic Deluge ~60s, the intermission at a health gate). So a hold is
forced, and its cost is arithmetic:

- **Coiled Altar.** You: Surge at 3 / 96 / 238 / 344 / 448 — a 52s hold to reach the
  window. The field: 1 / 121 / 213 / 307 — a 30s hold taken *earlier*, at the first
  opportunity, so nothing drifts later. Same cast count per minute either way; the earlier,
  smaller hold is strictly better because the fight cannot end during it.
- **Sszorak, the cross-check.** Dig In is a fixed +30% at 111–136s and 249–274s.
  Your Surges 13/113/212/306 catch window 1 and miss window 2 → **1.40× against a peer
  median of 1.59×** (range 0.93–2.08). The two peers who deliberately take **three** Surges
  instead of four — Unholyarc 10/108/**249** and Vicmage 3/112/**249**, both a ~51s hold —
  are the top two window multipliers in the pool at **2.07× and 2.08×**, and both land 2 of
  3 on-use trinket charges inside a window. Priced on your own log: window gain at 2.08×
  **+4.83M**, one lost Surge cycle **−2.18M**, net **+2.65M (+4.8% of the pull)**. The
  trade is clearly worth taking, and it is why the #1 Arcane parse on that boss runs one
  fewer cooldown than everyone else.

**Sszorak's raid-level Dig In ratio was 0.98× (1.07× and 0.89× per window).** The raid did
not convert a +30% vulnerability at all — while the two peers above converted it personally
at over 2×. This is the reason `windows` does **not** define a window by whether the raid
converted it: `fightmap` scores auras that way (and prints the neutral band rather than
hiding it), but `windows` falls back to the fight's recurring **phase** when no aura clears
the bar. Defining the scheduling target by raid conversion would have deleted the single
most actionable finding on that boss.

## Why the two fights diverge so far

Both pulls show the same weakness — window multipliers below the field. Sszorak's windows
are +30% over 50s of a 321s fight, so a weak multiplier there costs a few percent and the
parse still reads 92. The Coiled Altar's window is +100% and carries **25% of a top
player's damage**; the same weakness there costs 6.6% and the parse reads 36. **Window
exploitation is the variable that makes one player's parse swing 56 points between two
bosses on the same night.**

---

# Correcting the window findings against a stratified sample (2026-09-04)

The section above compared against 10-14 logs drawn from the **top 500**, i.e. a median of
the 99th percentile. Re-run against 26 pulls rank-stratified across 13 bands. Working data:
`scratch/coiled_altar/burn.py`, `burn_report.py`, `burn_profiles.json`.

## How deep the API actually lets you sample

`worldData.encounter.characterRankings` **caps at page 20** (`"The maximum page value
supported by the API is 20"`), and `hasMorePages` is still true there. Those 2000 pulls run
from `rankPercent` 100 down to **84**, which puts the whole ranked field at roughly
**12,300 pulls** and makes **p84 the deepest anything can be sampled**. Nothing below that
is reachable, so "compare against average players" is not a thing this API can do.

`characterRankings` carries no percentile field. The mapping comes from fetching each
sampled pull's own `reportData.report.rankings` and reading its `rankPercent` — one extra
query per log, and the only way to turn a rank index into a band.

## What survived, and what did not

| claim | test | outcome |
|---|---|---|
| On-use trinket belongs in the window | 26 pulls | **CONFIRMED, stronger.** 23 of the 25 that log one fire it inside; the two that don't are at -32s and -35s; **none** fires in the 6s before it opens. Funkywand is at -40.6s = **p0**. |
| Window conversion is worth ~5% | field median | **CONFIRMED.** Median 3.44x (top-10 said 3.53x), so +4.33M = **+5.3%**. |
| The field converts this window and you don't | 13 bands | **RETRACTED as stated.** Spread is 1.44x-4.88x, IQR 2.74-3.72, and it **does not track rank** — the top 0.05% band contains a 2.16x and the top 7.5% band a 4.66x. **23% of the sampled field converts it worse than the p36 pull.** At the field's lower quartile the gain is only +0.7%. |
| Top players bank Clearcasting into the burn | r vs multiplier | **REFUTED.** r = -0.10. Median entry is **1 stack** in every band including the top 1%. Nobody banks. |
| Top players dump Salvo pre-window to open the Missiles gate | r vs multiplier and vs waves | **REFUTED.** r = +0.05 and +0.14. Entry Salvo is **bimodal at 0 and 25** — wherever the Barrage cycle landed. Banded medians (7.5 in the top 1%, 21.5 lower down) looked like a strong finding and were an artifact of that bimodality. |

**The bimodal trap is the transferable lesson.** A banded median over a two-humped
distribution invents a trend that no individual pull shows. Print the raw values per band
before believing a median table — the per-band lists (`[25, 0]`, `[1, 13]`, `[19, 0]`) made
it obvious in one glance where three medians did not.

## Timing: the field is tight and this pull matches it

Seconds from the window opening, n=26, with Funkywand's percentile of the field:

| | p10 | median | p90 | you | your rank |
|---|---|---|---|---|---|
| lust | -0.3 | +1.1 | +3.4 | +1.3 | p58 |
| Arcane Surge | +2.4 | +4.2 | +20.3 | +4.3 | p54 |
| Touch of the Magi | +3.2 | +6.6 | +19.9 | +4.6 | p27 |
| **on-use trinket** | +2.3 | +3.8 | +11.9 | **-40.6** | **p0** |
| first Barrage | -11.5 | -8.6 | -1.4 | -11.1 | p19 |
| first Missiles | -11.4 | -8.9 | +1.4 | -10.0 | p38 |

## There is no "pull the procs into the burn" technique

The question that prompted this pass. Nobody pre-loads the window: Clearcasting entry ~1
stack for everyone, Salvo entry random, first Missiles at -9s median for the whole field
(Funkywand -10.0s, p38). The only thing that differs is **volume delivered inside** —
field median **80 Missiles waves** against this pull's **68** — and even that correlates
only weakly with DPS (r = +0.28) and barely at all with the window multiplier (r = +0.17).
Burn entry is entered on cadence, not set up.

## Report build note

The published page carries **no charset declaration of its own** — the Artifact wrapper
supplies one, a local file reader does not — so a single non-ASCII byte renders as mojibake
for anyone opening the built file directly (`2.63Ã—`, `weak â€" not`). `build_report.py`
now emits payloads with `ensure_ascii=True`, the template uses HTML entities above the
`<script>` boundary and `\uXXXX` escapes below it, and the build **fails** if any non-ASCII
survives into the output.


# WoWAnalyzer vs. the simc APL — where they drift (2026-09-05)

Source for the analyzer side: WoWAnalyzer's own Arcane modules on branch `midnight`
(`src/analysis/retail/mage/arcane/{Guide.tsx,guide/*.tsx,analyzers/*.tsx}`), read as code
rather than as rendered prose. Source for the APL side:
`ActionPriorityLists/default/mage_arcane.simc` at simc `aa9de89aac` (build Sep 5 2026,
`ptr_enabled: 1`), plus the 300s Patchwerk `action_sequence` from Raidbots report
`oY4yqcRKpiTahrDDZG5b2p` (169,887 DPS mean) used as an empirical cross-check on what the
APL actually *does* rather than what it appears to say.

**Getting the page at all**: wowanalyzer.com is behind a Cloudflare bot challenge. Plain
fetches and headless Chromium both get a 403 "security verification" shell that looks like
a successful load and yields 263 characters of body text. Real Chrome via Playwright
(`channel: 'chrome'`, `headless: false`) clears it. Raidbots' `data.json` no longer carries
the APL text at all, so the priority list has to come from simc's GitHub at the revision
the sim reports in `git_revision` — not from the report.

## The drift, in the order it matters

| where | APL (ground truth) | WoWAnalyzer | consequence |
|---|---|---|---|
| Arcane Orb, Sunfury | `arcane_charge.stack<3`, and **not** a cooldown to press — the reference sim casts it 2× in 300s | fails a cast at 4 charges (`<4`), *and* puts Orb on a cast-efficiency bar | the efficiency bar read 25% on the reference pull and implies "press it more", which is backwards for this build. The threshold is also off by one charge. |
| Arcane Barrage, Sunfury | third gate `buff.arcane_salvo.react>8 & cooldown.touch_of_the_magi.ready`, no charge requirement | no such branch in the Sunfury evaluator — **its own on-page explanation lists the condition**, the grading code does not implement it | ToM-setup Barrages come back "Ok, had N Arcane Salvo stacks". 7 casts on the reference pull. |
| Arcane Barrage, Sunfury | Arcane Soul branch is `buff.arcane_soul.up`, unconditional | graded "Good", never Perfect | 18 casts on the reference pull. Together with the row above this reconciles WoWAnalyzer's 24 "GOOD" against our 91 PERFECT almost exactly. |
| Arcane Barrage at 25 Salvo | gated on `(buff.arcane_surge.remains>gcd.max\|buff.arcane_surge.down)` | no Surge-remains awareness | dumping a capped Salvo into the last GCD of Surge grades the same as a clean one. |
| Prismatic Bolt, Sunfury | `((!4pc)\|cumulative_power.stack=8) & **buff.arcane_soul.down**` | Perfect at `cumulativePowerStacks >= 8`, Arcane Soul ignored on the positive side | a Bolt cast under Arcane Soul grades Perfect when the APL says Barrage instead. The sim casts Bolt under Soul **0 times in 31**. |
| Touch of the Magi | `cooldown.arcane_surge.remains>30` (or Surge up) | auto-fails at `surgeCD < 40000` | a ToM with Surge 32s out is APL-legal and WoWAnalyzer-Fail. 10s apart; this is what produced 2 "bad" ToM casts on the reference pull. |
| Touch of the Magi | `prev_gcd.1.prismatic_bolt\|prev_gcd.1.arcane_barrage` — cast it while a bolt is in the air | in the explanation text, **not** in the evaluator | nobody measures it. Genuinely implementable and unclaimed. |
| Arcane Surge | `buff.lustrous_gleam.stack>=2\|buff.lustrous_gleam.down` | active time in the window only | inert for a player without Lustrous Gleam (no such buff in the reference log), so not a live divergence there — but the analyzer has no gate at all. |

Two places WoWAnalyzer is **right and worth keeping**: the Sunfury Missiles gate
`buff.arcane_salvo.stack<12` matches the APL exactly (`chain=1`, full-channel — the
Spellslinger `interrupt_if` clip logic is likewise faithfully mirrored), and its hardcoded
`targetsHit >= 5` for the AoE branch is correct *for a Spellfire Spheres build*, since
`variable.aoe_count = 2 + 3*talent.spellfire_spheres`. Without that talent aoe_count is 2
and the hardcoded 5 is wrong — check for buff `448604` before trusting it.

## The user's hypothesis about low mana, checked

The instinct was right in general and does not bind on this pull. The APL does carry an
explicit low-mana branch — `evocation,if=mana.pct<10&buff.arcane_surge.down&debuff.touch_of_the_magi.down&cooldown.arcane_surge.remains>10`,
with `cancel_action` at 95% — and WoWAnalyzer models none of it: its Barrage evaluator has
a single `NO_MANA_THRESHOLD = 0.1` that grades a sub-10% Barrage "Ok" and stops. So a
player who correctly holds cooldowns into a window and pays for it in mana gets graded on
a rotation the analyzer does not know they were in.

For Funkywand specifically it is not the story: **Evocation is not talented** (zero casts,
and the sim does not use it either), and the mana curve is 86.8% of the fight above 80%
with 6.2s under 20%. The genuinely modelled fallback in that state is structural rather
than a spell — `actions.sunfury` ends in an unconditional `arcane_blast`, so the trailing
`actions+=/arcane_barrage,if=talent.spellfire_spheres&!buff.arcane_surge.up` is reachable
only when Arcane Blast itself is unaffordable. That is the low-mana rotation: Barrage as
the free spender. `common.check_mana` exists to surface this state before a spender check
gets read as a mistake, and `check_barrage` grades a sub-10% Barrage GOOD for that reason.

## Cast-mix drift against the sim, normalised to 300s

The reference pull (477s) against the 300s sim, both Sunfury with 4pc:

| ability | sim /300s | player, normalised | delta |
|---|---|---|---|
| Arcane Missiles | 88 | 75 | −15% |
| Arcane Barrage | 73 | 64 | −12% |
| Prismatic Bolt | 31 | 22 | **−29%** |
| Arcane Blast | 32 | 28 | −13% |
| Arcane Orb | 2 | 3.8 | +90% |

Prismatic Bolt is the outlier and it is the highest-value cast in the kit, so that is the
line to pull on — not Orb, which is up in relative terms but is 2 casts of noise. Note the
sim is Patchwerk single-target and the pull is a real Heroic encounter with downtime, so
read the *spread between abilities*, not the absolute deficit.
