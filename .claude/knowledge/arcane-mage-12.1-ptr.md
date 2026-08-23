# Arcane Mage — 12.1 PTR, Sunfury single-target

Sources: Raidbots report `38BorEbHSzMrsQmgug8J2B` (sim), WarcraftLogs `vAtQGNpDqJHyw9mn`
(actual play, character "Funkywand"), talent tree dump
[data/talents/arcane_mage_12.1_ptr.json](../../data/talents/arcane_mage_12.1_ptr.json).

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
- `data/keystoneloot_sources.json` slot IDs use the addon's `EQUIP_LOC_SLOT`:
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

Everything below is implemented in **[tools/wcl/](../../tools/wcl/)** — see its README for the
full table. Never hand-roll one of these again; run it and read the output:

```bash
wsl.exe -d Ubuntu -e python3 tools/wcl/run.py <check> -r <REPORT> -a <ACTOR> -f raid|dungeon|<ids>
# checks: list salvo soul clearcasting tom-target cooldowns cd-usage waves gaps gear all
```

Events and the OAuth token cache to `.wclcache/` (gitignored), so only the first run costs
API points. Adding a check = one function in `checks.py` + one line in `run.py`'s `CHECKS`.

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
