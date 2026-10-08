# The Venomous Abyss on Mythic — fight structure, measured

Companion to [venomous-abyss-12.1.md](venomous-abyss-12.1.md), which covers the tier's
Heroic shape and the Balance Druid build conclusions. **This file is Mythic and it is
measured**: every number below comes from the top ~100 Balance Druid Mythic logs per boss,
667 distinct pulls in total, sampled 2026-09-09.

Two datasets back it, and they are the thing to read rather than this summary:

| File | Built by | Holds |
|---|---|---|
| `data/raid/12_1/venomous_abyss/<nn>_<boss>/journal.json` | `tools/game_knowledge/journal_sync.py` | 284 catalogued abilities, descriptions, tuned damage numbers, per-role journal notes |
| `data/raid/12_1/venomous_abyss/<nn>_<boss>/profiles/balance-druid-16.json` | `tools/warcraftlogs/encounter_profile_sync.py` | phase segments, per-occurrence ability timings, composition, damage taken |

Method and traps: [docs/design/63-encounter-profiles.md](../../../../../docs/design/63-encounter-profiles.md).

## Mythic progression has not reached the whole raid

This is the first fact any Mythic question about this tier has to start from, three weeks
into the tier. Balance Druid ranking pool depth, at difficulty 5:

| Boss | Rankings | Measured |
|---|---|---|
| Nymrissa, Nek'zali, Sentinels, Vashnik, Explorers, Sszorak | 200+ each | 94–99 pulls |
| The Twin Fangs | 92 | 86 pulls |
| The Coiled Altar | **1** | no — too thin |
| Ula'tek | **0** | no — none exist |

The last two bosses have no usable Mythic sample. Anything said about them on Mythic is
inference from Heroic, and should be labelled as such. This is a live frontier: re-run the
sync rather than trusting this table after a reset.

## Raid composition: it is not 2/4/14 everywhere

The field's composition, as a distribution rather than an average — averaging compositions
produces "2.0 tanks, 3.7 healers", which describes no raid.

| Boss | Modal | Share | Note |
|---|---|---|---|
| Nek'zali, Sentinels, Sszorak, Twin Fangs | 2/4/14 | 0.99–1.00 | unanimous |
| The Lost Explorers | 2/4/14 | 0.77 | 22 of 96 pulls ran 2/5/13 |
| **Vashnik the Malignant** | **2/5/13** | **0.93** | the field brings a *fifth healer* here |
| **Nymrissa Wavecaller** | **3/5/17** | 0.51 | **25 players** — a Lair boss, not a 20-player raid |

Two findings worth carrying:

- **Vashnik is the healer-check.** 90 of 97 pulls dropped a DPS for a fifth healer, and it is
  the only boss in the raid where the field does that. It lines up with the Heroic note that
  Siphoning Infection cuts healing received, making it the highest-value Barkskin in the tier.
- **Nymrissa is not a 20-player fight.** Lair bosses run flexible-size, and the modal
  composition holds in only half the pulls (3/5/17, then 3/5/16, 3/5/15, 3/5/14). Any
  per-player damage figure from that boss is not comparable to the raid's.

## Phase structure, measured

Times are median seconds from the pull start; `iqr` is the interquartile range across the
pool, which is the honest measure of how scripted a transition is.

**Sszorak — perfectly deterministic.** Segment starts have an IQR of **0.0s** through six of
seven segments across 94 pulls. Phases *cycle*, alternating three times:

```
Sszorak          0.0s  (100.0s)      Howling Maelstrom   100.0s  (25.0s)
Sszorak #2     125.0s  (102.0s)      Howling Maelstrom #2 227.0s (25.0s)
Sszorak #3     252.0s  (102.0s)      Howling Maelstrom #3 354.1s (25.0s)
Sszorak #4     379.1s
```

This is a timeline you can plan to the second. Note that the transition list reads
`1,2,1,2,1,2,1` — there is no phase 4, only a fourth *segment*.

**Entombed Sentinels — a 103s cycle, nine segments.** Stage One runs 91s, Vitriolic Stasis
11–12s, repeating. IQR widens from 0.2s to 8.7s as the pull goes on, which is drift
accumulating, not variance in the mechanic.

**Nek'zali — three stages, HP-gated not time-gated.** The intermission starts at 177.4s with
an **IQR of 20.2s**, and Stage Two at 289.3s with an IQR of 30.9s. Compare Sszorak's 0.0.
That spread *is* the finding: these transitions are damage-driven, so a plan anchored to an
absolute second on this boss will drift by half a minute.

**The Lost Explorers — the boss order is not fixed.** Seven segments, but the intermission
segments agree on *which* explorer only 45%, 52% and 62% of the time (Scrollsage Iku, First
Mate Nama, Trader Gebbo). The segment *timing* is tight; the segment *identity* is not. A
plan for this fight has to be written per explorer, not per segment index.

**Nymrissa, Vashnik, Twin Fangs — single-segment.** No phase transitions are recorded at all.
Their structure lives entirely in ability cadence.

## Ability cadence, measured

The full per-occurrence tables are in the dataset. The cadences that anchor a plan:

| Boss | Ability | Cadence | IQR |
|---|---|---|---|
| Sszorak | **Dig In** (the +30% damage-taken window) | **127.0s** | 0.1 |
| Sszorak | Tempest | 51.0s | — |
| Sszorak | Venomous Surge / Raging Crosswinds | 47.5s / 47.0s | — |
| Twin Fangs | eight separate abilities | **61.0s** | — |
| Twin Fangs | Sanguine Storm, Vile Flood | 155.0s | 0.1 |
| Vashnik | Dripping Fangs (tank hit) | 28.0s | 2.0 |
| Vashnik | Imbibe | 84.0s | 0.1 |
| Sentinels | Vitriolic Stasis | 103.0s | 4.0 |
| Nymrissa | Abyssal Rain / Chilling Frost | 44.0s | — |
| Nymrissa | Swirling Whirlpools, Pop! | 110.0s | 0.0 |
| Explorers | Evil Eyes, Mor'zahi's Command, Dark Whispers | ~122s | ~4 |

**The Twin Fangs runs on a single 61-second metronome** — Barbed Bulwark, Blood Torrent,
Coiling Ichor, Corrosive Spit, Envenomed, Ravenous Feast, Rouse the Brood and Stir the Depths
all share it. That is the cadence to build the whole plan around.

### Corrections to the Heroic knowledge file

Both found by cross-checking rather than assuming, and both are now carried back into
[venomous-abyss-12.1.md](venomous-abyss-12.1.md):

- **Sszorak's Dig In is a 127.0s cadence on Mythic** (IQR 0.1 over 94 pulls); the "100 M" first
  recorded was the first window's start, from BigWigs constants one day into the tier.
- **Rage of the Shackled now reads 500,044 Nature every 4 sec**, not the 416,703 recorded on
  2026-08-19. The ability was retuned. Any tooltip magnitude captured during the first week
  of a tier should be treated as expired.

## What actually hurts

Damage taken per ability, summed over 10 pulls per boss, as a share of everything the raid
took. The striking part is how concentrated it is — **two abilities carry 56–71% of all
damage on every boss measured**:

| Boss | Top two | Combined |
|---|---|---|
| The Twin Fangs | Toxic Fumes 40.6%, Eternal Venom 30.3% | **70.9%** |
| The Lost Explorers | Splinters 35.3%, Malevolent Presence 35.2% | **70.5%** |
| Nymrissa | Abyssal Rain 42.0%, Frost Burst 27.9% | **69.9%** |
| Sszorak | Ula'tek's Presence 35.1%, Mutilated Gash 24.7% | 59.8% |
| Entombed Sentinels | Mark of Blood 28.3%, Mark of Acid 28.0% | 56.3% |
| Nek'zali | Soulcoil Rite 34.1%, Corpse Blight 17.6% | 51.7% |
| Vashnik | Caustic Explosion 23.2%, Toxic Vapor 21.3% | 44.5% |

Vashnik is the outlier at the bottom, and that is consistent with it being the boss the field
brings a fifth healer to: its damage is spread across more sources, so there is less to
mitigate with one well-placed cooldown and more to out-heal.

## The gap between what hurts and what the timeline shows

**This is the most important limitation to carry forward.** A cast-based timeline — which is
what NSRT gives and what the site currently draws — cannot show most of the damage:

| Boss | Top damage sources with a cast event |
|---|---|
| Sszorak | **none of the top four** |
| Nek'zali | none of the top three |
| Entombed Sentinels | none of the top two |
| The Lost Explorers | none of the top two |
| Nymrissa | Abyssal Rain (1st) and Water Jet (3rd) |

Ula'tek's Presence, Mutilated Gash, Viscous Cyst, Mark of Blood, Mark of Acid, Splinters,
Malevolent Presence, Soulcoil Rite and Toxic Fumes are all **applied auras or spawned-object
damage**. They emit no cast event, so nothing places them on a cast timeline, and on Sszorak
that means the timeline shows Ravage, Mutilate and Dig In while saying nothing about the 83%
of damage coming from three auras.

The dataset records this rather than hiding it — those abilities appear in `journalOnly` with
the reason `applied rather than cast`. Closing the gap needs a damage-intake curve measured
from `DamageTaken` *events* or debuff applications, not from the cast stream. That is not
built as a tool yet; how it was done by hand for Vashnik, and the helper to build, are in
[boss-death-timelines.md](../../../method/boss-death-timelines.md) ("The measurement that
matters most").

## Sourcing, corrected

`venomous-abyss-12.1.md`'s sourcing table stands, with two additions now verified directly:

- **The Blizzard journal API carries this tier in full** — `/data/wow/journal-instance/1320`
  (The Venomous Abyss, 8 bosses) and `/data/wow/journal-instance/1317` (The Tidebound Grotto,
  Nymrissa). It gives ability hierarchy, spell ids, per-role notes and difficulty modes. It
  gives **no ability descriptions**: only Overview and role sections have body text.
- **`/data/wow/spell/<id>` returns HTTP 404 for every boss spell id in this tier** while the
  same ids resolve on Wowhead. So the Wowhead tooltip endpoint is not a convenience, it is
  the only text and the only damage numbers there are.

## Two traps specific to reading these logs

- **The enemy cast stream contains player abilities.** WCL attributes some player ground
  effects to a synthetic actor named `Environment`, flagged `subType: Boss`. **Anti-Magic
  Zone (145629) appeared on all seven measured bosses** and is shaped exactly like a mechanic:
  regular cadence, boss-flagged source. Also seen: Berserk, Concealing Shadows, Creepy Flames,
  Haunting Spirits. In damage-taken tables the same problem appears as Melee, Stagger,
  Refraction, Blessing of Dawn, Burning Rush, Stretch Time and Time Dilation. Filter by
  joining against the journal catalogue, never by a hand-written deny list.
- **One mechanic is a burst of casts across several spell ids.** Sszorak's Raging Crosswinds
  is five ids firing nine casts inside one second; Mutilate and Ravage are each a cast id plus
  an effect id at the identical timestamp. Group by name, collapse a burst, and count
  instances — raw cast counts overstate by 2× to 9×.

## The Lost Explorers — what the top-10% Balance field does (measured 2026-09-17)

39 Mythic pulls, one per 0.25% rank slice from #6 to #412 of 4,173, plus Funkitty's p89 kill.
The general techniques this case produced (per-phase benchmarking, sizing a finding in parse
terms, `run.py displaced`) are in [analysing-a-pull.md](../../../method/analysing-a-pull.md).

- **Phase kinds.** `phaseTransitions` id 1 is the Final Ascension build-up (all three explorers
  possessed), ids 2–4 are a 60s Mor'zahi's Command channel on one explorer. The empowered
  explorer is identified by its unique casts, **by ability name** (Mighty Thud → Nama, Frostfire
  Volley → Iku, Mushroom Toss / Explosive Surprise → Gebbo); the log's ids differ from the
  journal's. Throw Junk fires in every phase and identifies nothing.
- **Command phases pay ~0.56x of Final Ascension DPS** for the median top player (p25 0.53, p75
  0.60) — they are ~45% of a 400s kill and cannot be skipped, so they are half the parse.
- **Kill length correlates with rank at ρ −0.67.** Benchmark per phase on the player's own
  timeline (see analysing-a-pull.md), never on the whole-pull number.
- **Cooldown plan is unanimous:** both Incarnation charges inside the first Final Ascension phase (~7s
  and ~28s), then one per Final Ascension phase, ~0 seconds of Incarnation inside Command phases.
- **Talent fork:** Orbit Breaker 28/39, Sundered Firmament 11/39. Fury of Elune + Full Moon
  come to 8.16% of damage for Orbit Breaker takers vs 7.34% for Sundered Firmament. A lean, not
  a proof: the Sundered Firmament group also had longer kills (389s vs 340s).
- **Starfall is a 40yd stacking aura around the player**; within ±1.5s of a spender cast it
  essentially never reaches only one explorer, for anyone. The positional signal is the share of
  Final Ascension Starfall ticks reaching **all three** (pool median 15.4%, ρ +0.30 with rank;
  one-target ticks ρ −0.49).
- **DoT gaps at ~57s, ~180s and ~360s on every explorer at once** are phase transitions, not
  refresh errors.

### The Lost Explorers — measured on Funkitty's kill (2026-09-17, follow-up)

- **The explorers do NOT share health in practice.** Target `hitPoints` on damage events
  (`resourceActor` 2) at 385s: First Mate Nama 0.2% (0.0% from 390s), Scrollsage Iku 5.1%,
  Trader Gebbo 8.7% (stalled around 9% from 360s). The last ~20s is effectively two targets, one
  dying — a final burst window there pays less than the same window a minute earlier.
- **Explosive Surprise (1297625) on a Balance Druid late in a Command phase collapses damage.**
  Carriers from the top-130: at ~315s, 3 of 3 fell to 4–16 casts/min and lost 1.72–1.83M; at
  ~100–110s, 4 of 4 kept casting (44–52/min), losses 0.12–2.21M. Funkitty at 354.6s: ~1.46M
  against their own same-phase surrounding damage (`run.py displaced`). Treat it as agency, not
  execution, unless the carrier pattern changes.
- **Potion timing vs the kill.** A second potion paired with the last cooldown 18.5s before the
  kill wasted 11.5s of a ×1.22 spell-power buff — ~0.45–0.49M against drinking it 30s before the
  end, independent of the cooldown it was paired with (`run.py potion`).
- **Holding the last Incarnation to ~5:00 with the potion is not supported** by a per-second
  re-timing of that pull: −1.5 to −3.0k DPS at a realistic Incarnation multiplier (×1.5–1.8),
  positive only at the pooling-inflated ×2.16, and it would push the on-use trinket (Empowering
  Venom, 120s) past the kill.

## The Twin Fangs — Spawn of Vexhul and the boss geometry (measured 2026-10-06)

Measured from 30 kills sampled out of the 178 unique pulls in the top-200 Mythic world
character rankings (all classes), plus Shidann's kill `vP4RTacqbCNzd9JV#9`. These
measurements are what the simc fight script encodes: the script is in
`data/raid/12_1/venomous_abyss/06_twinfangs/sim/`, its reference card is
[twin-fangs-sim-profile.md](twin-fangs-sim-profile.md), and the method is
[modelling-a-fight-in-simc.md](../../../method/modelling-a-fight-in-simc.md).

- **Spawn waves run on a fixed clock.** The Venomous Emergence begincast lands at **33.0 /
  94.0 / 188.0 / 249.0 / 343.1s** (sd 0.08s), a cadence of 61/94/61/94s. A sixth wave
  at 404s exists in only 5/30 kills.
- **Each wave is three Spawns, 1-1-1.** They arrive at begincast **+1 / +2 / +3s**: the
  minimum first-event offset is 1.01/2.01/3.01s in every wave. First damage alone reads
  ~0.8s late.
- **Lifetime from the true spawn second is 13.1s on average** (sd 3.1, waves 1–5). Waves
  1–4 run 12–13.5s and are fully cleared ~16s after the begincast. Wave 5 is longer and
  looser: ~15s, p90 ~21s. Fixed ~12.2M HP; 360/360 died in waves 1–4.
- **Geometry.**
  - The bosses are stacked; Starfire on one always hits the other.
  - The three Spawns are stacked with each other.
  - **The two groups are out of each other's splash range**: zero boss-targeted Starfire
    or Fury of Elune hits on a Spawn.
  - Vile Flood (136.0 / 291.0s) separates the bosses for ~24s.
  - Vexhul dies first in 24/30 kills, at a median of 385.9s of a 402.5s kill.
- **The bosses take ~1.135x what a Spawn takes**, from raid-applied debuffs the Spawns
  never live long enough to collect. Two methods agree (1.126–1.149).
- **Barbed Bulwark** (Blood Torrent's globule shields) is not a DPS target. Exclude it
  from damage-done tables.
- **Balance Druid answer:** keep Fury of Elune on the bosses. Sending it at the Spawns
  (and casting into them under Atmospheric Exposure) costs 5–7% of boss damage, and does
  not pay back in total damage, at any Spawn lifetime from p10 to p90.

## The Twin Fangs: cycle clock, positions and how Balance moves (measured 2026-10-08)

Measured from 40 Balance Druid kills, rank-stratified p76–p100, with positions taken from
`includeResources` events. Method notes are in
[tools/warcraftlogs/README.md](../../../../../tools/warcraftlogs/README.md#positions-and-resource-snapshots-the-data-behind-the-replay).
What the Balance field *chooses* on this clock (utility assignments, Incarnation timing, grading
a wipe) is in [balance-druid-12.1.md](../../../classes/druid/balance-druid-12.1.md).

**The 61s cycle**, as seconds from cycle start. Cycles start at 0 / 61 / 155 / 216 / 310 / 371s,
and every pull matches to within 0.1s:

| +s | mechanic |
|---|---|
| 8 | Blood Torrent + Caustic Deluge |
| 11 | Barbed Bulwark |
| 14 | Caustic Globule |
| 23 | Stone Breaker |
| 33 | Rouse the Brood + Venomous Emergence |
| 37, 45 | Corrosive Spit / Visceral Burst |
| 40 | Coiling Ichor |
| 47 | Stir the Depths |
| 57 | Ravenous Feast |

The intermission is cycle 2 / cycle 4 +75s (136.0 / 291.0s): Sanguine Storm and Vile Flood.

**Log ids differ from journal ids, and the journal ids return nothing, with no error:**

| mechanic | log id | journal id |
|---|---|---|
| Ravenous Feast damage | 1290662 | 1290516 |
| Coiling Ichor damage | 1290878 | 1290809 |
| Stir the Depths | 1292806 | — |
| Sanguine Storm | 1306876 | — |
| Vile Flood | 1294605 | — |
| Congealed Gore | 1292552 / 1306925 | — |

- **Coiling Ichor is not a debuff in the log.** Find carriers as players who take 4 or more
  Coiling Ichor ticks in cycle +39–54.
- **Tainted Blood soaks emit no damage event,** so these streams cannot show them.
- **Feast strikes** land at cast +4.25s and +6.3s. Balance druids soak only strike 1 (61%) or
  strike 2 (39%).

**Geometry.** On platform 1 the Spawns appear at (0, 634) and both bosses sit 57 yd away at
y=691: Ithraz at x=+16, Vexhul at x=−16. On platforms 2 and 3 the bosses go to one flank (east
or west depending on the pull) and the Spawn center moves with them. A per-cycle frame works on
every platform:
- origin = the median Spawn position;
- depth = toward the boss midpoint;
- "left, looking from center outward" = `(−u_y, u_x)`, calibrated on a player assigned left.
  On platform 1 that is the Vexhul side.

**Balance in P1 (pool medians):**
- **They never hold GCDs.** 85–95% of seconds are busy, except at the globule soak (+14–17s,
  48–80%), the cycle start (+59 to +2s, 57–77%), and the second Spit (+44–47s).
- **AP rises from ~55 to ~80 between +14 and +40s, then about 4 Starfall and 2 Starsurge go out
  in +40–52s.** That is the Ichor and waves window, and AP is down to 41–51 by +52s. In other
  words, AP is banked as movement currency for the Ichor/waves window, not for a burst. A
  Patchwerk sim cannot value this; the movement is what makes it worth it.
- **Eclipse presses peak at +55–60s** (31 per 100 cycles, against a ~17 uniform rate) and
  dip at +30–35s. The instant Starfire then covers the Feast run-in and knockback.
- **Ichor carriers move ~10 yd** from their +39s spot to the drop, then 14–19 yd to the
  Feast spot.

**Balance in the intermission (+−3 to +26s, n=80):**
- **Totals:** 139 yd travelled, 19s moving, 9.3s with no GCD.
- **Per intermission:** 6.1 Moonfire+Sunfire (5.4 of them while moving), 4.0 Starfall,
  3.2 Starsurge, 3.1 hardcast Starfire, 1.3 instant Starfire.
- **The shared skeleton:**
  1. Stampeding Roar (where assigned) → Moonkin Form.
  2. Walk on dots and spenders.
  3. Fury of Elune at ~+12–16s, then Eclipse 1s later, usually while still moving.
  4. Instant Starfire, then a Starfall/Starsurge chain into the final spot.
  5. Hardcasts from about +19s.
- **AP:** 52 entering at −3s, 61 at +12s.
