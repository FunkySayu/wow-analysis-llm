# Balance Druid — 12.1.0 (live)

Reference notes for Balance Druid on patch 12.1.0, build **12.1.0.69299** (hotfix
2026-08-15). Structured talent data with names, spellIds, icons and PTR-correct
description strings lives at
[data/classes/druid/balance/12_1_talents.json](../../../../data/classes/druid/balance/12_1_talents.json)
— 53 class nodes, 38 spec nodes, and both hero subtrees split out (14 nodes each).
Read that file rather than re-fetching; regenerate only when the build moves.

**Patch is live, not PTR.** Use the plain `nether.wowhead.com/tooltip/spell/<id>`
endpoint and `https://www.raidbots.com/static/data/live/talents.json`. The `/ptr/`
trap described in [CLAUDE.md](../../../../CLAUDE.md) applies in reverse here — a `/ptr/`
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

That is the resource-economy framing from [resource-economy.md](../../method/resource-economy.md) applied here:
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
  Nature, **Celestial Alignment / Incarnation**, and Convoke. The Raidbots talent text
  (and so `data/classes/<class>/<spec>/12_1_talents.json`) drops the CA/Incarnation clause: Wowhead renders it as a
  conditional segment (`<!--sp394013-->`, "Celestial Alignment, " / "Incarnation: Chosen
  of Elune, "), and simc lists `incarnation_chosen_of_elune` in `control_cooldowns`
  (`sc_druid.cpp`, `trigger_control_of_the_dream_t`). Measured on 29 top Mythic Vashnik
  pulls (2026-09-30), zero violations: FoN readiness is `max(prev_ready + 45, cast + 30)`,
  so a FoN pressed within 15s of coming up loses nothing. On a 2-charge Incarnation
  (Whirling Stars) the refund only applies when you cast **at max charges**, which in
  practice means the opener only. The opener gets the full 15s even at 4.4s into the pull,
  so the 5th Incarnation is ready at exactly `opener + 345s` (105 + 120 + 120). Every top
  pull's 5th cast landed at opener + 345.0–345.7.
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
`name=kotg_st`). Per [reading-an-apl.md](../../method/reading-an-apl.md)'s note on structural gates, check
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
   permutation testing (see [simc-simulation](../../../skills/simc-simulation/SKILL.md));
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

No validator for rules 2 and 3 is kept in `tools/` yet (the site has one for its talent
editor, `site/backend/app/services/tree_validate.py`, against the same tree files). The
pattern: BFS from `entryNode` following `prev` edges only, then for each node with
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

## Reading a Balance log: spell IDs and the checks that use them

Reusable checks live in [tools/warcraftlogs/checks/druid_balance.py](../../../../tools/warcraftlogs/checks/druid_balance.py)
and run as `run.py <check> -r <report> -a <actor> -f raid|<ids>` (group name `druid`
runs all eight). Run those rather than re-deriving an analysis; add a new question
there as a check rather than as a one-off script.

`eclipse` · `apex` · `ap` · `dots` · `spenders` · `cds` · `apl` · `trace`.

**IDs confirmed against report `ThRfrJBk1ZGwyCWc`, not from memory.** The ones that
silently return the wrong thing:

| thing | cast | damage / DoT | buff |
|---|---|---|---|
| Moonfire | 8921 | **164812** (8921 has *no* ticks) | — |
| Sunfire | 93402 | **164815** (both damage and DoT) | — |
| Eclipse | **1233272** Lunar / **1233346** Solar | — | 48517 Solar / 48518 Lunar |
| Touch the Cosmos | — | — | **450360** (talent is 450356) |
| Balance of All Things | — | — | 394049 / 394050 (talent is 394048) |
| Ascendant Eclipses | — | — | 1263382 Stars (3 stacks) / 1263363 Fires |
| Shooting Stars | — | **202497 and 1272339** — two IDs, one name | — |

Astral Power is `classResources` type **8**, stored ×10. On a *spender's* cast event
the value is the pool **before** the cost (what the APL saw); on a *generator's* it is
**after** that cast's own energize.

### CA/Incarnation applies both Eclipses at once

Solar and Lunar are separate auras and Celestial Alignment / Incarnation (and the
`Total Eclipse` proc) apply both simultaneously. Any "Eclipse uptime" that sums the two
auras double-counts those windows, and any "entry count" that counts applications
without deduping counts each CA as two entries. Confirmed: Funkitty's Eclipse (Solar)
uptime in fight 5 equals the Incarnation uptime to the millisecond.

### Empirical talent detection beats guessing at the loadout

Per [resource-economy.md](../../method/resource-economy.md)'s rule on unverifiable talent lists, the checks infer
rather than assert:
- **Improved Eclipse** — simulate the charge pool and pick the fewest charges that make
  every observed Eclipse cast possible. `Sculpt the Stars` (29s vs 32s recharge) is
  *not* separable this way, so 32s is assumed and the waste figure is a lower bound.
- **Whirling Stars** — same trick over `[(1, 180s), (2, 120s)]` for CA/Incarnation.
- **Hero tree** — Harmony of the Grove on the player means Keeper of the Grove; its
  absence means Elune's Chosen. This selects which APL list (`kotg_st` vs `ec_st`) is
  even live, which per reading-an-apl.md must be settled before reading any priority order.
- When a cooldown is cast faster than any fixed candidate allows, a talent is shortening
  it dynamically (Lunation on Fury of Elune, Control of the Dream on Force of Nature).
  There is then no fixed cooldown to score against, and `cds` reports the rate and
  **refuses to compute an efficiency** rather than inventing one.

### "Lust" is eight buffs, not four — and the wrong list reports the wrong answer

A lust check that hardcodes Bloodlust/Heroism/Time Warp/Primal Rage will report
**"no lust in this fight"** for a raid that lusted perfectly. All of these are the
same 30% haste raid buff and all cause an exhaustion debuff:

| spell | id | source |
|---|---|---|
| Bloodlust | 2825 | Shaman (Horde) |
| Heroism | 32182 | Shaman (Alliance) |
| Time Warp | 80353 | Mage |
| Primal Rage | 264667 | Hunter pet |
| **Harrier's Cry** | **466904** | **Hunter (Eagle)** |
| Ancient Hysteria | 90355 | Hunter pet (Core Hound) |
| Netherwinds | 160452 | Hunter pet (Nether Ray) |
| Fury of the Aspects | 390386 | Evoker |

Drums are a separate, weaker tier — **+15%**, not 30% — but they still trigger the
same exhaustion debuff, so they occupy the lust slot without filling it: Drums of
the Maelstrom (256740), Drums of Deathly Ferocity (309658), Feral Hide Drums
(381301). Exhaustion debuffs, the definitive marker that a lust actually landed on
a player: Sated (57724), Exhaustion (57723), Temporal Displacement (80354),
Fatigued (264689).

Verified concretely on `JqywQ2R1XpgZrVKL` fight 18, and it produced a **wrong
published finding** before it was caught. A Mage cast Time Warp and 80353 had
**zero buff events** — the raid was already Sated — while every player actually
held `Harrier's Cry` for 40s from a Hunter who pressed it at 1.6s. The report said
"no lust on a 429-second pull, worth +3,700 DPS"; the truth was a full 40s window
with CA/Incarnation up for 82% of it, which is *good* usage. **Check the buff the
player received, never the cast someone made** — a cast that lands on nobody looks
identical to a cast that worked, from the caster's side.

### Two thirds of Balance's Astral Power is haste-scaled

This is the correction to the naive "haste just gives you more GCDs" intuition, and
it matters because it makes a haste deficit compound rather than add. On the
reference log the generation split was:

| source | share | scales with haste? |
|---|---|---|
| Starfire | 41% | **yes** — hard cast, so haste raises casts/min directly |
| Shooting Stars | 26% | **yes** — procs off Moonfire/Sunfire *ticks*, and haste raises tick rate |
| Fury of Elune | 15% | no |
| Moonfire / Sunfire / Boundless Moonlight | 17% | no |

So **~68% of generation is haste-scaled**, and Astral Power is the sole gate on
spender count. Measured across six Heroic Twin Fangs logs, Starfire hardcast time
and AP/min line up almost monotonically:

| player | Starfire hardcast | AP/min | spenders/min |
|---|---|---|---|
| Funkitty | 1.729s | 450 | 16.63 |
| Dakd | 1.632s | 531 | — |
| Canexxone | 1.582s | 487 | 20.27 |
| Lerepam | 1.497s | 577 | — |
| Попопелапой | 1.275s | 560 | — |
| Cotti (rank 1) | 1.229s | 614 | 22.23 |

**Measure haste from the log, never from the rating** — see the next section for the probes
and how far the rating misleads.

### Aetherial Kindling makes hand-refreshing Moonfire a real, common leak

`Aetherial Kindling` (327541): *"Casting Starfall extends the duration of active Moonfires
and Sunfires by 3.0 sec, up to 28 sec."* In a build casting Starfall 11-13x/min the DoTs
are extended nearly continuously, so a manual refresh buys almost nothing — and because
Sunfire/Moonfire sit **above** spenders in the priority, the GCD it costs is always a
Starsurge or Starfall.

This is a **feedback loop**, not a one-off waste, which is why it costs more than the cast
count suggests: a hand-cast Moonfire displaces a Starfall -> less extension -> the DoT
expires sooner -> another hand-cast Moonfire. It also suppresses `Starweaver` income
(Starfall has a 40% chance to make Starsurge free), so spender count falls faster than
GCD count does.

Measured on `JqywQ2R1XpgZrVKL` fight 18 (Funkitty, Heroic Twin Fangs, 429s, 196,612 DPS,
81st percentile) against 25 profiled top-parse peers:

**Read the count, not the clip rate.** Early refreshing is *normal* in this spec —
against the real pandemic rule (5.4s, i.e. 30% of Moonfire's 18s base) the rank-1
parse clipped **67%** of its refreshes and Funkitty clipped **70%**. Clip rate
separates nobody. What separates them is how many re-applications happen at all:
30 (Funkitty) vs 18 (Cotti), 17 (Lerepam), 13 (Canexxone). An earlier version of
`refresh` used a flat "under 12s apart" threshold and got this backwards — gap
since the last cast is **not** remaining duration, because Aetherial Kindling has
been pushing the expiry out the whole time.

The refreshes are also **not forced by the DoT expiring**: median remaining
duration at re-application was 12.8s, with clipped values up to 24.0s. That rules
out the plausible-sounding chain "low haste -> fewer Starfalls -> less extension ->
Moonfire drops -> forced recast". A DoT re-applied with 20 seconds left was not
re-applied out of necessity.

| metric | Funkitty | top-25 median | rank |
|---|---|---|---|
| Moonfire casts / ticks | 36 / 791 (22.0 per cast) | 34.8 per cast | p4 |
| Sunfire ticks per cast | 47.2 | 45.1 | p56 |
| spenders / min | 16.63 | 20.27 | **lowest of 25** |
| all rotational GCDs / min | 44.86 | 49.10 | p4 |
| Eclipse presses / min | 1.96 | 1.96 | p40 |
| damage per Starfall | 236,942 | 241,149 | — |

The shape of the finding matters more than the numbers: **Eclipse usage, AP overcap (0.8%
vs 2.1%), proc consumption (0 expired) and the priority audit were all clean or better than
the field.** The entire deficit was GCD *composition*. Sunfire being at p56 while Moonfire
sat at p4 is what makes it a habit rather than a misread talent.

The control that settles "downtime vs composition": peer Canexxone had 81.7% GCD uptime to
Funkitty's 81.3% and an effective GCD within 4% (modal 1.161s vs 1.171s), and still did
+25% DPS — on 19 Moonfire casts to 36, and 137 spenders to 119, in a fight 43s shorter.
Equal activity, different allocation.

### Rating gaps are not effective-stat gaps — measure haste from the log

`peers-stats` on that log showed haste 624 against a peer median of 829 (p8, 22.0% of the
secondary budget vs 28.6%), which reads as a 25% deficit. Raid buffs, procs and the
rating->percent curve compress raw ratings hard, and every log-side probe read far less:

| probe (most to least trustworthy) | how | gap to peers |
|---|---|---|
| **Starfire hardcast time** | pair `begincast`/`cast` *sequentially* — begincast carries `targetID: -1` while cast carries the real target, so pairing on target silently returns nothing; drop pairs under 0.15s (instant procs) | ~12% vs the peer median |
| **modal rotational cast gap** | median of consecutive rotational cast gaps in the 0.6–2.2s band | ~4% (1.171s vs 1.126s) |
| **DoT tick interval** | median of per-target Moonfire tick deltas; weakest, talents alter tick rate independently | ~0.4% vs the nearest peer (1.148s vs 1.143s) |

The probes disagree with each other in size but all say the rating overstates the gap. Use
them before sizing any stat finding — and remember a stat gap only explains DPS if damage
*per cast* is also low. There it was within 2% of the field, so the deficit was volume.

### WCL trap: DoT uptime must come from ticks, not from debuff events

Debuff `applydebuff`/`refreshdebuff`/`removedebuff` are keyed on the **aura on the
target, not the caster**. With several druids on one boss, the second caster's
application logs as `refreshdebuff` and a single `removedebuff` covers all of them.
Reconstructing one player's DoT uptime from that stream is wrong precisely in raid.
Measured on fight 10 of `ThRfrJBk1ZGwyCWc` (four druids, one boss): the debuff stream
implies a 38-second Moonfire drop that the tick stream shows never happened, and the
first version of the `apl` check reported a 10.2% priority-inversion rate that was
almost entirely this artifact. Damage events always carry the true `sourceID`, so
cluster DoT **ticks** with a ~5s gap threshold instead.

Related: WCL will not combine `sourceID` with `hostilityType: Enemies` in one events
query — it returns zero rows silently. Filter on `sourceID` in Python.

### Mastery double-dips on Astral spells — and the log can show it

`Mastery: Astral Invocation` (393014) in 12.1 is flat: *"Your Nature spells deal X% increased
damage. Your Arcane spells deal X% increased damage."* Astral spells (Starfall, Starsurge,
Shooting Stars, Fury of Elune) are both schools, so they take it **twice**; Moonfire and
Starfire take it once. That is why the Mythic field stacks it (36 of 39 top-10% Lost Explorers
logs on Flask of the Magisters, median mastery 37.7% of secondaries).

A gear-cancelling probe from the log: **Shooting Stars damage per hit ÷ Moonfire damage per
tick.** Shooting Stars procs off the same DoT ticks, so target set, Intellect, Versatility,
raid buffs and Eclipse's Arcane bonus cancel; the second mastery dip does not. Across 39 pulls
it tracks mastery rating at ρ +0.45 (slope +0.0155 per 100 rating). **Starfall ÷ Moonfire does
not** (ρ −0.10) — too many Starfall-specific modifiers ride on it. Funkitty (757 mastery, the
lowest allocation in the pool) read 1.51 against a 1.71 median; the fit predicts only −3.7%
from mastery, so the rating explains a third of that gap and the rest is still unexplained.
Size a stat change with a sim, not with this ratio.

Flask IDs, stat per tooltip: 1235108 Magisters = **Mastery**, 1235110 Blood Knights = **Haste**,
1235111 Shattered Sun = Crit, 1235057 Thalassian Resistance = Vers.

### Tier set, Fury of Elune cooldown, and Starfall vs Eclipse — measured (2026-09-17)

**Set text (12.1, from the tier item tooltip):** 2-piece — Starsurge +20%; Starfall also deals
30.4% SP Astral instantly to all enemies in range on cast (12.2% of Funkitty's Starfall-family
damage). 4-piece — +10% damage in any Eclipse, waning to 2% at the midpoint and waxing back to
10% at the end. No buff is logged for the 4-piece.

**Fury of Elune's cooldown is exactly `45s − 1.5s × (Starfire + Moonfire + Starsurge + Starfall
casts)`** with Radiant Moonlight + Lunation. Validated on 562 Fury casts over 40 Mythic pulls:
zero casts before the reconstructed ready time, tightest at 0.0s; dropping any one of the four
spells from the set makes 119+ casts impossible. Experienced cooldown median 22.5s.

**Starfall is one stacking aura.** Each cast adds a stack and refreshes (applybuffstack +
refreshbuff), and each tick event carries all stacks — tick size ≈ proportional to stacks. Any
per-tick comparison must hold stack count fixed, or it measures how many Starfalls were up.

**Eclipse bonuses on Starfall ticks are read live, not snapshotted.** At fixed stacks: ×1.47–1.56
inside a button Eclipse, ×1.18–1.28 in the 0–2s after it ends, ×0.99 from 2s on. Damage events
carry the source's active buff ids in `buffs` (with `resources=True`) — that is what makes this
testable; `spellPower` is 0 in these logs.

**The 4-piece V is not visible in damage.** Tick multiplier by seconds into a button Eclipse
(2 stacks): 1.05, 1.45, 1.52, 1.52, 1.55, 1.46, 1.44, 1.40; the Starfall 2-piece instant by 3s
bins: 1.30, 1.60, 1.77, 1.63, 1.46. The in-window ramps (Harmony of the Heavens, Stellar
Amplification, Atmospheric Exposure) dominate it. Priced per cast, a Starfall is worth most at
3–7s into a button Eclipse (≈1.52× an out-of-window cast), 1.38× at 0s, 1.14× at 14s.

**A Fury whose 8s is covered by an Eclipse or Incarnation does 1.70× (IQR 1.37–2.19) the damage
of an uncovered one**, within-player, before counting its 40 AP. At a 22.5s cooldown one second
of hold costs ~4.4% of a Fury, so holding for a pairing breaks even at roughly 9s — but only when
no Eclipse charge is already available.

**Spell order inside a window, measured (pool of 40, ×vs out-of-window, 3s bins).** Button
Eclipse — Starfall 2-piece instant 1.30 / 1.56 / 1.72 / 1.67 / 1.46; **Starfire 1.32 / 1.73 / 1.74 /
1.91 / 1.85**. Incarnation — instant 1.94 / 2.41 / 2.79 / 2.14 / 1.89 / 1.83 / 1.78; Starfire 1.64 /
2.27 / 2.08 / 2.18 / 2.21 / 1.88 / 2.24. Starfall wants the early-middle of a window (its ticks run
8s and read the bonus live); Starfire holds its value to the end. So when both are available,
Starfall first and Starfire later is the value-ordering. The Incarnation *tick* curve at fixed
stacks is sparse (players run 3+ stacks in Incarnation) — treat per-second Incarnation tick
values as ±noise.

**Auditing a spend order: check Astral Power across every intermediate spender.** A first
"could this Starfall have gone earlier" pass counted swaps as affordable because AP covered 50
at the earlier slot, ignoring the Starsurges and Starfalls cast between the two slots, and
counted a free proc that the Starfire itself created on completion. Both inflated the answer
~4×. The corrected check walks AP forward through every cast between the two slots and
excludes procs created by the cast being moved; it is not yet a `tools/warcraftlogs` check.

### Mythic Vashnik: the field's build is Rattle the Stars + Meteor Storm (2026-10-05)

Measured on the top 100 Mythic Vashnik Balance parses (`characterRankings` page 1):
**Rattle the Stars 100/100, Starweaver 0/100; Meteor Storm 92/100, Aetherial Kindling 8/100**
(the best AK parse is #14). Both are choice nodes (88236, 88209), so a talent diff against
the pool lands on them first.

Why it matters on this boss specifically: Shrouded Venom is a burst add on the Imbibe cadence
(spawns at 24/108/192/276/360s, alive ~5-15s per window) and carries ~42% of a top Balance
parse's damage. Meteor Storm ("Starfall deals its damage 100% faster") front-loads Starfall into
those short windows. The log signature of Meteor Storm is Starfall **hits per second on the
boss** during the windows (top 12: ~2.6-3.2/s; an Aetherial Kindling player: 1.78/s) at the
same number of concurrent Starfalls (3.7 vs 3.9). Per-cast Starfall damage reads ~half for a
Kindling + Starweaver build and is *not* a positioning problem: the ratio of add hits to boss
hits was the same as the field's.

Starweaver also changes how the spender checks read: free Starsurges from Starfall mean
10.9 Starsurge/min against the field's 6.9, including during add windows, where the field
spends almost nothing but Starfall (median 0.15 Starsurge/min while Shrouded Venom is up). Under
Starweaver part of that is the proc firing, not a targeting decision, so don't grade it as one.
Worked case: `HfGDg1K3bRzcqPkN` fight 31 (Funkitty, 306.9k, 423s).

### Mythic Twin Fangs: the field's gear, and what simc cannot price (2026-10-06)

Measured on 199 of the top-200 Mythic Twin Fangs Balance parses. The sim profile these
weights and deltas come from, with every gear correction it needed, is
[twin-fangs-sim-profile.md](../../raid/12_1/venomous_abyss/twin-fangs-sim-profile.md).

- **Stat balance:** median buffed secondaries are 39.7% mastery, 28.2% crit, 27.9% haste,
  3.3% vers. Flask of the Magisters is used by 171/199.
- **Weights:** on the Twin Fangs script (boss damage) they read Int 79.9, Mastery 56.7,
  Crit 48.1, Vers 46.6, Haste 44.3, so the stacking is correct.
- **Potion of Recklessness boosts your highest secondary.** It loses to Light's
  Potential on crit-led gear (−2.0k) and wins once mastery leads. That is why the field
  splits 241/153.
- **Rite of the Hash'ey is not modelled by simc** (spell 1297652 has no handler; it
  sims as an empty weapon), yet 170/199 use it. In logs it is four Loa buffs (120
  rating, 15s):
  - Halazzi's 1297663 = crit
  - Akil'zon's 1297664 = mastery
  - Jan'alai's 1297655 = haste
  - Nalorakk's 1297665 = vers

  Average uptimes on 25 users are 56.5 / 31.6 / 16.4 / 4.3%, and the "favours highest
  secondary" clause is not visible. Priced as constant stats, it is worth ~+2.8k boss
  DPS over Arcane Mastery.
- **Eyes of the Eagle adds no stats** in simc; its value is entirely its effect.
  Replacing it with Zul'jin's Mastery on both rings costs ~4k.
- **Embellishments, field standard:** Hunter's Ritual Stone on Aln'hara Lantern
  (150/199) and Arcanoweave Lining on Silvermoon Agent's Deflectors (108) or Sneakers
  (48).
- **Two simc gear traps, both silent, both found by comparing simc's stat sheet with the
  log's:** the Aqirbane Reliquary (268265, worn by 192/199) sims all its secondaries as crit,
  and crafted stat pairs are bonus ids that override `crafted_stats=`. The overrides are on the
  sim card and in the `simc-profile-syntax` skill.
- **Rite of the Hash'ey vs Arcane Mastery** is not sim bait in either direction:
  - Arcane Mastery's proc (Genius Insight, 124 mastery, 15s) is up 61.5% in a real log
    against 58.4% in simc.
  - Rite's four Loa buffs (120 each) total 109% uptime across 25 top users.
- **On-use trinkets must be simmed on the Incarnation schedule actually played.** The APL
  fires `use_items` only while `ca_inc` is up, so the trinket ranking follows wherever the APL
  puts Incarnation — on Twin Fangs it flips Vile Vial vs Freightrunner's Flask. The numbers and
  the `ca_hold` fix are on the sim card ("Why the schedule matters").

### Mythic Twin Fangs: what the field does on the clock, and grading a wipe (2026-10-08)

Measured on 40 kills rank-stratified over ranks 1–300 (p76–p100) of the **full** Balance field.
Funkitty's wipes `ZvwYhTV74g9bMdL2` 20/22/25/26 are the worked case. The fight's own clock
(Spawn waves, intermission, the 61s cycle) and how Balance moves through it are in
[venomous-abyss-mythic.md](../../raid/12_1/venomous_abyss/venomous-abyss-mythic.md); this
section is what the Balance field *chooses* on that clock.

- **The ranking list is not capped here.** `characterRankings` ends at page 13: 1,232 parses.
  So percentiles can be read straight off it: p99 302.4k, p95 289.1k, p90 282.4k, p85 278.0k,
  p50 258.3k. Median kill 410s, median ilvl 327.
- **Augmentation support is removed from the ranked amount, and 25 of 40 pool players had it.**
  Ranked DPS ran 85–99% of each player's raw damage per second. A raw-damage pool is therefore
  inflated against a raid with no Aug. Scale each pool player by their own `amount / raw` before
  comparing any window.
- **Field-wide utility assignments, not choices:**
  - Incapacitating Roar at ~15s and ~75s: 31/40 players.
  - Solar Beam at 39–47s and 100–108s, on the Spawns: 29/40.
  - Roar leaves you in Bear, so it costs Moonkin Form plus a cancelled Starfire. Do not grade
    that as dead time.
- **Nobody uses Cat Form to reposition before 136s** (0/40). 9/40 use Wild Charge.
- **Eclipse goes at ~0 / ~27 / ~45s**, covering 17.1 of wave 1's 18s (median).
- **The 2nd Incarnation is bimodal:** 16/40 press it at 25–43s, 23/40 at 94–102s. Both are the field.
- **Casting nukes into the Spawns does not track rank.** Players with 2 or more
  Starfire/Starsurge/FoE on Spawns did less total in wave 1 (7.06M vs 8.16M) and more in wave 2
  (6.79M vs 5.43M), at the same median percentile both times. The 2 Moonfire + 1 Sunfire dot
  routine is universal.
- **Grading these wipes** used the wipe-projection method in
  [analysing-a-pull.md](../../method/analysing-a-pull.md) ("Grading a wipe"); on this boss a
  projection from a ~60s wipe barely constrains anything.
