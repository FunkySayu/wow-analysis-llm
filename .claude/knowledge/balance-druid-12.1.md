# Balance Druid — 12.1.0 (live)

Reference notes for Balance Druid on patch 12.1.0, build **12.1.0.69299** (hotfix
2026-08-15). Structured talent data with names, spellIds, icons and PTR-correct
description strings lives at
[data/talents/balance_druid_12.1.json](../../data/talents/balance_druid_12.1.json)
— 53 class nodes, 38 spec nodes, and both hero subtrees split out (14 nodes each).
Read that file rather than re-fetching; regenerate only when the build moves.

**Patch is live, not PTR.** Use the plain `nether.wowhead.com/tooltip/spell/<id>`
endpoint and `https://www.raidbots.com/static/data/live/talents.json`. The `/ptr/`
trap described in [CLAUDE.md](../../CLAUDE.md) applies in reverse here — a `/ptr/`
pull would describe a *future* build, not this one.

## The 12.1 redesign: Eclipse is an activated ability

This is the single change that reorganizes everything else, and it invalidates most
pre-12.1 Balance intuition.

**Eclipse** (spellId 1239669) is no longer a state you fall into by casting Wrath or
Starfire. It is now a **button on a 32 sec cooldown with charges**:

> You may draw the sun and moon into alignment for 15 sec, empowering either your
> Nature or Arcane spells. Casting Wrath or Starfire changes what mode of Eclipse
> will be entered, and the two modes of Eclipse share a button and 32 sec cooldown.
> Eclipse (Solar): Nature spells deal 15% additional damage and Wrath damage is
> increased by 40%. Eclipse (Lunar): Arcane spells deal 15% additional damage and
> Starfire damage is increased by 40%.

Wrath/Starfire now only *steer* which mode you'll get; they don't trigger it. So
Eclipse **entries are a spendable, rate-limited resource** — 15s of uptime per
charge, on a 32s recharge, with `Improved Eclipse` (1240906) granting a second
charge and `Sculpt the Stars` (1240188) shaving 3 sec off the recharge.

### Why entry *count* matters more than Eclipse uptime

A large amount of 12.1's power budget is attached to the **moment of entering**
Eclipse, not to being in one. Every one of these fires once per entry:

| Talent | spellId | On-entry payout |
|---|---|---|
| **Ascendant Eclipses** (apex, rank 1) | 1261564 | Next Wrath/Starfire becomes **instant**; first **3** Starsurges/Starfalls this Eclipse deal **+20%** |
| **Ascendant Eclipses** (apex, rank 3) | 1261566 | Launches Solar Bolt (632.5% SP) or 3× Lunar Bolts, **always critical** |
| Balance of All Things | 394048 | +20% crit, decaying 2%/sec |
| Cenarius' Might (KotG) | 455797 | +6% haste for 6 sec |
| Sylvan Beckoning (KotG) | 1264614 | Summons a Dryad for 8 sec (Starsurge + Starfall at 250%) |
| Astral Communion | 450598 | Next spender costs 15 less AP |
| Total Eclipse | 1240206 | 15% chance to get **both** Eclipses at once |

That is the resource-economy framing from [CLAUDE.md](../../CLAUDE.md) applied here:
the resource is *Eclipse entries*, generated only by the Eclipse button's charges,
and spent by a long list of talents that each convert one entry into damage. Talents
that add charges or cut the recharge (`Improved Eclipse`, `Sculpt the Stars`) are
therefore **multiplicative with the entire on-entry package**, including the apex —
they are not the small utility picks their tooltips make them look like.

The corollary for APL reading: any condition that *delays* pressing Eclipse (an
Astral Power threshold, a cooldown-alignment gate) is spending on-entry value to buy
something else, and is worth testing rather than trusting.

## Astral Power economy

Astral Power (AP) is the secondary resource, capped at 100 base (+20 from
`Expansiveness`, +20 from `Astral Communion`).

**Generators:** Wrath / Starfire (the fillers; `Wild Surges` adds +2 each and +10%
crit), `Nature's Balance` (1 AP / 2 sec passive), Shooting Stars procs off
Moonfire/Sunfire (2 AP each), `Force of Nature` (20 AP), Sunseeker Mushroom
(up to 20), Fury of Elune (40 over its duration), the Moon chain (New/Half/Full).

**Spenders:** Starsurge and Starfall — and essentially nothing else. Per the
resource-economy rule, that concentration makes the spenders the highest-leverage
abilities in the kit, and it is why so many talents hang off them:

- `Starweaver` / `Rattle the Stars` (choice) — cost/proc economy vs. flat +8% damage
- `Power of Goldrinn` — 33% proc on Starsurge
- `Stellar Amplification` — Starsurge applies +16% periodic-damage amplification
- `Touch the Cosmos`, `Hail of Stars`, `Starlord`, `Harmony of the Heavens`
- Apex rank 1's "+20% to the first 3 spenders per Eclipse"

The last one couples the two economies directly: **Eclipse entries gate the number
of *premium* spender casts**, so AP banking and Eclipse timing are one problem, not
two. An APL that enters Eclipse while AP-starved wastes the +20% window; one that
banks AP too long wastes Eclipse charge recharge time.

## Hero trees

`heroNodes` in the Raidbots feed are undifferentiated; `subTreeNodes[0].entries[]`
splits them. Note that **some nodes appear in both subtrees' node lists** (e.g.
Boundless Moonlight, node 94608) — don't assume a node's presence in one list
excludes the other.

### Keeper of the Grove (subtree 23)
Treant/Force-of-Nature centric, and the tree that leans hardest into Eclipse entries.
- `Harmony of the Grove` (428731) — **each** active treant gives +4% spell damage.
  With 3 treants that is +12%, so Force of Nature windows are the damage peaks and
  everything wants to align to them.
- `Sylvan Beckoning` (1264614) — Dryad on Eclipse entry (see table above).
- `Dryad's Dance` (1264776) — +10% to most AP generation while a Dryad is out.
- `Cenarius' Might` (455797) — +6% haste on Eclipse entry.
- `Control of the Dream` (434249) — banks up to 15s of unspent cooldown on Force of
  Nature and Convoke, i.e. it forgives *late* cooldown usage rather than adding
  throughput. Its value depends entirely on how sloppy the APL's CD timing is.
- `Treants of the Moon` (428544) — treants cast Moonfire (~1 per 6 sec each).
- `Power of Nature` (428859) — treants stop taunting, +300% melee damage.

### Elune's Chosen (subtree)
Moon/Arcane centric, built around Fury of Elune and the New→Half→Full Moon chain.
- `Lunar Calling` (429523) — Starfire +120% damage to primary target, and **Wrath no
  longer sets Solar Eclipse**. This is a rotation-defining node: it converts the spec
  into a Lunar-locked Starfire build, so it interacts with everything Solar.
- `Lunation` (429539) — Arcane abilities cut Fury of Elune's CD by 1.5s and the Moon
  chain's by 1.0s. Only meaningful if those abilities are talented at all.
- `Atmospheric Exposure` (429532) — Full Moon / Fury of Elune apply +6% damage taken.
- `The Eternal Moon` (424113) / `Boundless Moonlight` (424058) — Fury of Elune ends
  with an AoE flash; Full Moon calls Minor Moons.
- `Star Cascade` (1271206) — 30% chance on Starfire AP gain to launch a 50% Starsurge.

**Trap:** the default simc APL branches on `hero_tree.elunes_chosen` vs
`hero_tree.keeper_of_the_grove` at the top level (`run_action_list,name=ec_st` vs
`name=kotg_st`). Per [CLAUDE.md](../../CLAUDE.md)'s note on structural gates, check
which list is live *before* reading any priority ordering — the two lists differ in
more than cooldown names.

## Dead APL lines are loadout-dependent

The default APL is written to cover every talent combination, so a large fraction of
its lines are unreachable for any given build. Lines gated on untaken talents simply
never fire — they are not evidence that an ability is used. For a build without the
Fury-of-Elune/New-Moon choice node, for instance, `fury_of_elune`, `new_moon`,
`half_moon`, `full_moon` are all dead, and the `kotg_st` list collapses to roughly:

```
sunfire -> moonfire -> (execute-range CA/FoN) -> convoke -> eclipse
       -> starfall (proc-gated) -> starsurge -> wrath filler
```

Always resolve the actual talent list before reasoning about the priority — see
"Resolving a loadout" below.

## Resolving a loadout (talent string -> named talents)

The `talents=` field is an opaque Blizzard export hash, and simc's JSON report only
echoes the string back. Two reliable ways to resolve it:

1. **`debug=1`** — simc prints every allocated trait as
   `Player 'X' adding <tree> talent <Name> (node=N entry=E rank=r/max)`, plus
   `activating sub tree <HeroTree>`. One cheap 1-iteration run resolves the whole
   loadout by name. This is ground truth from the same DBC the sim uses.
2. **Named overrides** — `class_talents=`, `spec_talents=`, `hero_talents=` accept
   `token:rank` lists and are applied *on top of* the hash, overwriting matching
   entries. `token:0` removes a talent, `token:<max>` adds one. This is the lever for
   permutation testing (see [simc-simulation](../skills/simc-simulation/SKILL.md));
   note it does **not** enforce the tree's point budget or prerequisite pathing, so an
   "add" test measures raw value as if the point were free.

Tokens are the talent name lowercased with spaces as underscores and punctuation
stripped (`Elune's Guidance` -> `elunes_guidance`).

## simc talent overrides enforce NO game rules — validate every result

This is the single biggest trap in talent-permutation work, and it fails silently in
all four of the following ways. Every one of these produced a large, plausible-looking,
**completely invalid** DPS number in the 2026-08-17 Balance analysis.

1. **Choice-node exclusivity is not enforced.** `spec_talents=orbital_strike:1` on a
   profile that already has Whirling Stars gives you *both halves of the same node*.
   That read as **+15,576 DPS (+9.1%)**. The legal swap
   (`whirling_stars:0/orbital_strike:1`) is **−9,501**. The sign flipped.
   Same trap: adding Incarnation on top of Convoke read +11,444; the real swap is −5,523.
2. **Point budget and tier gates are not enforced.** A `reqPoints=N` node needs N points
   spent in nodes of a *lower* tier — points inside the gated section cannot pay to open
   it. Moving a point *up* a tier therefore breaks every gate above it; moving one *down*
   is always legal. See the gate-tightness note below.
3. **Connectivity is not enforced.** A node needs at least one *purchased* node in its
   `prev[]`. When checking this, the graph is **directed** — walking `prev`/`next` as an
   undirected graph lets reachability flow backwards up the tree and wrongly passes
   orphaned builds. (Dropping Orbit Breaker orphans Umbral Embrace; Twin Moons' only
   parent is Solar Beam.)
4. **`hero_talents=<tree_name>` is not a hero-tree swap.** `hero_talents=elunes_chosen`
   enabled *every Druid hero talent in the game* — Feral and Restoration nodes included
   (Ravage, Twin Claw, Root Network, Wildstalker's Power) — layered on top of the
   existing Keeper of the Grove picks. It read **+27.4%**. A hand-built legal Elune's
   Chosen loadout is **−6.6%**. To swap trees, zero each node of the old tree by token
   and add each node of the new one, then validate.

A validator that implements rules 2 and 3 lives in the session scratch work; the pattern
is: BFS from `entryNode` following `prev` edges only, then for each node with
`reqPoints=R` check that points in nodes with `reqPoints < R` total at least R.

### The 12.1 Balance spec tree is exactly gate-tight

For a standard 30-point spec allocation the tiers come out at:

```
tier req=0  :  8 points  -> opens the  8-gate  (EXACTLY tight, zero slack)
tier req=8  : 12 points  -> 8+12 = 20 points   -> opens the 20-gate (EXACTLY tight)
tier req=20 : 10 points
```

There is **no slack at either gate**. Consequently every point is tier-locked upward:
you cannot fund a `req=8` talent (Soul of the Forest, Sculpt the Stars, Nature's Grace,
Meteorites) by dropping a `req=0` talent (Solar Beam, Nature's Balance, Twin Moons),
even though the raw DPS numbers make that look like a large gain. Of **485** candidate
single-point reallocations across the spec and hero trees, only **120 are legal**.

## Empirical values (simc 1210-01, 12.1.0.69299, Patchwerk 300s, 1 target)

Measured on a 344-ilvl Keeper of the Grove profile at ~171.4k DPS. Numbers are the DPS
lost by dropping the talent, i.e. its marginal contribution *in that build*.

**Load-bearing (dropping breaks the build, not just the damage):**
Celestial Alignment's −91% is **an APL artifact, not talent value** — `variable.opener`
is set precombat and only cleared by `buff.ca_inc.up`, so with no CA the actor is trapped
in the opener list and idles **97% of the fight**. Always check `Waiting:` in the text
report before believing a huge drop number. (Spot-checked: Eclipse, Shooting Stars,
Whirling Stars, Convoke all idle 0% — their losses are genuine; Force of Nature idles
6.3%, so its −31% is slightly inflated.)

| Talent | Drop cost | Talent | Drop cost |
|---|---|---|---|
| Force of Nature | −53,175 | Balance of All Things (2) | −11,908 |
| Harmony of the Grove | −27,630 | Starlord (2) | −10,560 |
| Shooting Stars | −20,446 | Cosmic Rapidity (2) | −9,883 |
| Whirling Stars | −18,056 | Improved Eclipse | −8,876 |
| Convoke the Spirits | −16,160 | Touch the Cosmos | −7,736 |

**Cheapest points (still not reallocatable — see gate-tightness):** Solar Beam −47 (n.s.),
Expansiveness −261, Blooming Infusion −509, Nature's Balance −1,315, Orbit Breaker −1,422.

**Result of the legal sweep: 0 of 120 legal single-point moves gained DPS**
(119 significantly negative, 1 neutral: Nature's Balance -> Twin Moons at −171, n.s.).
A well-built 12.1 Balance loadout has essentially no free points.

### Apex talent scaling (Ascendant Eclipses)

| Rank | DPS | vs rank 0 |
|---|---|---|
| 0 | 139,889 | — |
| 1 | 145,922 | +4.3% |
| 2 | 154,112 | +10.2% |
| 3 | 162,398 | +16.1% |
| 4 | 171,421 | **+22.5%** |

### Synergies (2x2 factorial, `synergy = D(AB) - D(A) - D(B)`)

Negative = complementary (worth more together); positive = substitutive (they overlap).

| Pair | Synergy | Conditional value |
|---|---|---|
| Starweaver x Hail of Stars | **−2,533** | Hail of Stars: +4,891 alone -> **+7,424** with Starweaver |
| Improved Eclipse x Sculpt the Stars | **−1,562** | Improved Eclipse: +8,910 -> **+10,472** with Sculpt |
| Harmony of the Grove x Bounteous Bloom | +1,669 | Bounteous Bloom: 3,792 -> 2,123 without Harmony |
| Potent Enchantments x Orbital Strike | +1,497 | Potent Ench.: +2,148 with Whirling Stars -> **+650** with Orbital Strike |

The Improved Eclipse x Sculpt result is the mechanically important one: Eclipse-entry
talents show **increasing**, not diminishing, returns, confirming that entry count (not
Eclipse uptime) is the binding constraint under the apex talent.

The Potent Enchantments result is a tooltip trap worth remembering — the talent *leads*
with "Orbital Strike damage increased by 30%", but its Whirling Stars haste rider is
worth more than the clause it advertises.

### Fight shape

| Targets | DPS | | Fight length | DPS |
|---|---|---|---|---|
| 1 | 171,4xx | | 60s | 260,076 |
| 2 | 202,222 | | 120s | 208,465 |
| 3 | 246,674 | | 300s | 171,410 |
| 5 | 329,313 | | | |
| 10 | 444,378 | | | |

### APL

All 12 tested variants of the default simc APL — loosening/tightening the Eclipse entry
gate (`astral_power>60|charges_fractional=2`), repositioning Eclipse above Force of
Nature/Convoke, and front-loading spenders under the apex buff — landed within ±93 DPS
of baseline against a CI95 of ±145, i.e. **no significant change**. The default APL's
Eclipse gating is already correct for this build; do not "fix" it without new evidence.
