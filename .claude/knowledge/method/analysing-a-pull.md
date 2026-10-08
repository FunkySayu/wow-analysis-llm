# Analysing a pull: the angles, and how to work through them

Method notes, written after a session that started as "why is my parse low" and only became
useful once it stopped being about the rotation. This file is deliberately spec- and
encounter-agnostic; the examples are illustration, not the point. Companion files carry the
worked cases ([arcane-mage-12.1-ptr.md](../classes/mage/arcane-mage-12.1-ptr.md) for the one this was
distilled from).

## The core idea

**A pull is not one thing that went well or badly. It is about ten independent things, and
the rotation is one of them — usually not the largest.** A player's damage is the product of
what they brought, what the raid gave them, what the fight let them do, and what they chose
to press. Any of those can be the whole story, and they fail in ways that look identical
from the summary number.

So the job is **elimination across axes**, not depth on the axis you know best. The failure
mode this replaces is real and I fell into it: given a low parse, the instinct is to open the
cast list, find something that looks wrong, and stop. Everything downstream of that is a
narrative built to fit the first anomaly found.

## The axes

Ordered outward-in — the ones nearest the top are cheapest to check, most often decisive, and
**invalidate everything below them if you skip them**.

| # | Axis | The question | What it looks like when it's the answer |
|---|---|---|---|
| 0 | **Comparability** | Is this number even comparable to what I'm comparing it to? | Same DPS ranks completely differently on two bosses, because each encounter has its own damage bar |
| 1 | **Preparation** | Item level, talents, gems, enchants, trinket *choice*, tier set | Every ability's damage per cast down by a similar fraction |
| 2 | **Composition** | Raid buffs present, roster size, how fast the raid killed it | A buff at 0% uptime that the whole comparison pool has at 100% |
| 3 | **Agency** | Which seconds were the player's to spend at all? | Deaths, mind control, immunity phases, forced targetability gaps |
| 4 | **Execution** | Uptime lost to mechanics the player *could* have handled better | Cast gaps that don't line up with any mechanic |
| 5 | **Conscientiousness** | The background rotation: proc consumption, resource caps, priority order | Rates fine, but procs overcapped or spent out of order |
| 6 | **Placement** | Positioned to reach extra targets; a mobile spell saved for the movement | Cleave abilities hitting fewer targets than the fight offers |
| 7 | **Planification** | Do cooldowns line up with the fight's structure? | Cooldowns on cooldown, but landing in the fight's worst seconds |
| 8 | **Opportunism** | Resources and procs staged *into* a window before it opens | Entering a burn with the generator blocked or the bank empty |
| 9 | **Deviation** | Is the scripted priority actually right here? | The best players in the pool doing something the APL doesn't say |
| 10 | **Luck** | Proc droughts, crit variance | A decision that was forced, not chosen |

**Axis 0 is the one most often skipped and it poisons everything.** Before comparing a
player to anything, confirm the metric means the same thing on both sides.

A **burn phase** is a short (<30s) vulnerability or a critical DPS check that demands a spike (Coiled Altar's P3→P4 transition, Ula'tek's heart windows) — never a recurring phase that makes up most of the fight.

**Axes 3 and 10 are the "is this even the player's fault" axes.** They are the difference
between a report that helps and a report that blames. Check them before writing a single
sentence that implies a mistake.

## Methods that did the work

### Decompose the headline number before comparing it

`DPS = hits per minute x damage per hit`. These have opposite fixes — one is "press more or
better buttons", the other is never fixable by pressing anything — and a single DPS delta
cannot distinguish them. Splitting it immediately told a "-30%" story that was entirely hit
size while every throughput measure was at field level, which redirected the whole
investigation away from the rotation in one step.

Generalise: **always factor the summary metric into a rate and a magnitude** before reaching
for an explanation. Do the same one level down — damage per cast splits into hits per cast
(targeting, waves, cleave) and damage per hit (stats, amplifies).

### Ratios against the player's own baseline cancel confounds

The single most useful invention of the session. When a player is 30% down on gear you cannot
grade them on any absolute number — every window, every cooldown, every phase will read as a
deficit. But **a ratio of their own output in a window to their own output outside it** has
item level, raid buffs and fight length all cancel out algebraically.

That makes a badly geared player directly comparable to the best in the world on the only
question that is actually about decisions. Build these deliberately:
`window rate / background rate`, `cooldown rate / background rate`,
`damage per cast under buff / damage per cast without`.

Caveat learned the hard way: **define the baseline once and reuse it.** Two different
"background" definitions (excluding just the window, versus excluding the window *and* every
cooldown) produce numbers that look comparable and are not.

### Derive the fight from the log, then validate it against the journal

Both, in that order, and neither alone.

- **The log** gives what actually fired, when, how often, and to whom — cadence, phase
  boundaries, real spell IDs, which mechanics the guides forgot. It is ground truth for
  *timing*.
- **The journal** gives what things *mean* — stage names, which boss owns which ability, that
  a spell is a possession rather than a debuff, that an add spawns immune. It is ground truth
  for *semantics*.

Skipping the journal produced a concrete error: reading a two-boss damage total across a
whole pull as "a permanent second target", when the encounter was one target for most of its
length and two only in the final stage. **Per-phase target composition must be established
per phase, from the per-phase damage split, and named from the journal.** An aggregate hides
sequencing completely.

### Score windows by what the *raid* did in them, not the player

To find a fight's amplify windows without a guide: take every bounded aura the enemies put on
themselves and measure the raid's damage rate inside it against the raid's own average.
Amplifies, immunities and soak phases separate themselves out.

**Use raid-wide damage, never one player's** — a single player's own burst window would
otherwise detect itself as a boss mechanic. This is a general trap in "find the interesting
period" analysis: the detector must be independent of the thing being measured.

Corollary: **a window the raid failed to convert is still a window.** Defining the
scheduling target by whether anyone converted it deletes exactly the finding you want. Fall
back to phase transitions when no aura clears the bar.

### Audit decisions against the priority list's gates, never against outcomes

"N GCDs went to a weak ability" is an outcome. The decision question is **"at that instant,
was anything above it in the priority list legal?"** — which is answerable, because a
priority list states its own conditions and the buff state is in the log.

Doing this converted "seven wasted GCDs" into "six were forced by a proc drought and one was
a real error", which is a completely different report and the only version that leads
anywhere. It also produces the useful follow-up automatically: if the casts were forced, the
lever is *upstream* — whatever state made the good options illegal.

**This is the single highest-value technique in the file.** Any time a cast looks wrong,
reconstruct legality at that timestamp before calling it a mistake.

### Cooldowns are analysed per instance, never in aggregate

"5 of 6 used, 83% efficiency" is nearly useless. It hides that one of the five was worth a
third of the others. **Score every individual cooldown window** — damage, ratio to
background, GCDs inside it, cast mix, and the resource state carried in — and compare each
against a field distribution **for the same context**, because a cooldown inside an amplify
and a cooldown outside it are different jobs with different expectations.

This is where the real coaching lives once the background rotation is clean, and it is the
part I under-delivered on: I built the per-instance table and then narrated only the window I
had already decided was the story, missing that the worst cooldown of the pull was a
different one entirely, with an obvious external cause sitting immediately before it.

### Read your own tables, row by row

Generating a table is not analysing it. **Every row gets a sentence, or an explicit "and the
rest are unremarkable".** A row that contradicts the thesis is the most valuable row on the
page, and it is the one narrative momentum will skip.

Practical rule: before writing prose from a table, sort it by the metric and look at **both
ends**. I looked at the interesting end.

### Sampling: the comparison pool is a parameter, not a given

Comparing against the top N of a ranking makes everything look like a deficit, because the
median of the 99th percentile is not a standard anyone meets. **Stratify the sample across
the rank range**, report `n`, and report where the sample came from.

Then check whether the metric **tracks rank at all**. If it doesn't, it is a description of
this pull and not a grade — say so, and keep it for locating the problem rather than scoring
the player.

Know the sampling floor: rankings APIs typically cap pagination, and the cap may sit well
above the median player. State the floor rather than implying full coverage.

### Beware medians over multi-modal distributions

A banded median table showed a clean monotone trend that no individual pull exhibited: the
underlying distribution was bimodal (values clustered at both extremes), so group medians
moved with the mix, not with any player behaviour. Correlation across the raw values was
approximately zero.

**Print the raw values per group before believing a median table.** Two-line change, caught a
finding that was about to be published.

### On a phased fight, benchmark per phase on the player's own timeline

Kill length correlates with DPS rank (ρ −0.67 in the Lost Explorers top-10% pool), so a
long kill *looks* like a gap by itself. Fix it structurally: take the pool's median DPS for
each phase instance (same index, same length), lay it on the player's own phase timeline and
sum. On Funkitty's 403s kill that gave 285.2k expected against 271.6k actual — so the long
kill explained ~1.6k of a ~15k gap, and the rest was real and *located* per phase. Take phase
damage from time-bounded WCL `table` queries, not summed events: summed events drifted ±10%
per ability on some logs while the table matched the ranking figure exactly.

Three confounds that produced wrong readings first on that pool, each caught by a control:

- **Phase position beats phase identity.** A Command phase on one explorer read 3rd
  percentile; DPS in that phase correlated ρ −0.65 with *which* Command phase it was (early
  ones carry lust and cooldowns). Matched by position it was 31st. Compare phase *instances*
  by index before comparing them by name.
- **Attribute a buff to where its duration lands, not when it was pressed.** Eclipse pressed
  3s before a Final Ascension phase opens is an Eclipse for that phase. Press-time counting said "one entry
  in the window vs the pool's two"; overlap counting put the player at the 82nd percentile.
- **Per-cast ratios of stacking auras depend on cast count.** "Starfall hits per cast" falls
  when a player casts *more* overlapping Starfalls, so it read as a positioning problem that
  was not one. Use per-tick target counts instead.

### Size every finding in parse terms, against an achievable benchmark

A finding is only as useful as the parse it would buy. For each behaviour, estimate
**"fixed in a vacuum, how many places / percentile points"**: convert it to damage on the
player's own numbers, divide by kill length, and place the new DPS in the ranking list
(`characterRankings`, deep enough to reach the player — top 500 was not). Report the *shift in
places* and apply it to WCL's own rank, because the list and the report's rank count parses
differently (the list put a ~459 parse at #607). Around a p89 Mythic Balance parse there were
~33 parses per 1k DPS, so a 1.6k finding was ~60 places, ~1.4 points.

This is expensive — a counterfactual replay plus a deep ranking pull per finding — so spend it
on the findings that survive the cheaper axes, not on everything.

**Benchmark = the best 20% of the sampled top-10% logs on that fight.** Not the median (a
description, not a standard) and not the single best log (luck). It is a level people at that
tier demonstrably hold: on Fury of Elune holds, the best 8 of 39 had *zero* failed holds, which
is what made "never hold with a charge ready" a fair ask rather than a perfectionist one.

**Fixes interact; say how.** Individual estimates do not simply add. Pressing a cooldown sooner
can leave it with a worse setup, re-timing one cooldown drags another (an on-use trinket on a
120s cooldown, a potion's 5 min), and a burst window that moves also moves the resource pooled
into it. Sum the independent ones, and name the coupled ones with the direction of the coupling
rather than silently adding them.

**Check that a counterfactual model is not circular before quoting it.** Removing a cooldown's
boost from the damage it produced assumes the boost is a clean multiplier — but players pool
resources into their windows, so the in-window multiplier is inflated and the out-of-window
baseline depressed. The Incarnation re-timing on the reference pull flipped sign between an
assumed x1.5 and the measured x2.16. Report the sensitivity table, and prefer a variant that
does not depend on the uncertain term (moving only the potion did not: +0.45-0.49M at every
multiplier).

### Separate what was controllable

**Scan the mechanics that targeted the player before reading any window.** The reference
analysis missed a carried bomb that cost ~1.5M (3.6k DPS, ~120 places) and explained the
resulting phase deficit away as "phase position". `run.py displaced` now lists every enemy
debuff that halved the player's damage against their own surrounding seconds in the same
phase. Two traps it had to handle: a carrier keeps pressing buttons (defensives, shapeshifts,
Dash), so **cast count does not drop — damage does**; and a debuff spanning a phase transition
cannot be attributed, so it is listed and never priced. Then compare against other carriers of
the same mechanic before calling any of it avoidable.

Before any gap is called a mistake, check whether the player had control of those seconds.
Mechanics that remove control — possession, stuns, forced movement, phases where the boss
cannot be hit — must be extracted from downtime *first*, because they are indistinguishable
from inattention in a cast-gap analysis and mean the opposite thing.

The same applies to cooldown drift: a cooldown that came late may have come late because its
owner was not in control when it became available.

### Negative results are findings, and cheap

"Are the adds worth a global cooldown here?" measured across the whole pool takes one query
and settles whether a whole category of advice applies. "Hold cooldowns for the add wave" is
correct on some encounters and actively wrong on others; assuming rather than measuring
carries that error into every future report on the fight.

### Say what you could not reach

Resources some APIs never expose, talents that cannot be resolved, ranking depth that caps
out. An analysis that states its blind spots is checkable; one that doesn't is not.

## Step zero, always: the preparation sweep

**Every analysis starts here, before comparability and before any rotation output is
read** (the user's standing instruction, 2026-09-17). It is cheap, it is the axis most
often decisive, and anything it finds would otherwise be misread as a play habit. Check
the player *and* the comparison pool for the same items, so a gap is a gap and not a log
that doesn't record something:

| item | how | trap |
|---|---|---|
| food | `run.py consumables` | name match; "Hearty Well Fed" is the Midnight feast |
| flask **and its stat** | `consumables` `stat` column | **the name does not say the stat.** Funkitty believed they ran Mastery and were on Flask of the Blood Knights (Haste); Magisters is Mastery. Compare against what the pool runs, not against intent |
| augment rune, vantus rune | `consumables` | the Midnight rune is "Ethereal Augmentation" — the old needles missed it for a whole raid; a Vantus for a *different* boss is worthless |
| weapon oil | `consumables` `wpn` | a `temporaryEnchant` on the weapon |
| combat potions, and *when* | `consumables` + cast timestamps vs the fight's windows | Midnight potions are not named "Potion"; pre-pots are invisible in a fight's cast log |
| raid buffs received | `CombatantInfo.auras` not sourced by the player | Blessing of the Bronze / PI are composition, not player choice — label them so |
| secondary-stat *allocation* | `CombatantInfo` rating shares vs the pool | a rating gap is not an effective gap; confirm with a log-measured ratio before sizing it (see the Shooting Stars / Moonfire per-hit test in [balance-druid-12.1.md](../classes/druid/balance-druid-12.1.md)) |
| talents | `talentTree` entry ids -> `data/classes/` `entryId` | diff against the pool's majority; class-tree diffs are usually utility — read the description before calling one a DPS loss |

Report each row as *same as field* / *different, player-controlled* / *different, raid-
controlled*. Only then move on.

## Sequencing a real investigation

0. **Preparation sweep** (above). Always.
1. **Comparability.** Is the metric comparable at all? Establish the reference.
2. **Fight model.** Derive structure from the log; name and validate it against the journal;
   establish per-phase target composition from the per-phase damage split.
3. **Windows.** Score them raid-wide. Identify what to plan around, and what to avoid.
4. **Decompose the gap.** Rate versus magnitude. This chooses the next branch.
5. **External axes** (preparation, composition) — cheap, and they invalidate everything else.
6. **Agency.** Extract the seconds the player did not control.
7. **Background rotation.** Rates, proc consumption, resource caps — against a stratified pool.
8. **Cooldowns, per instance.** Where coaching actually lives once 7 is clean.
9. **Decision audit.** For anything still looking wrong, reconstruct legality at the timestamp.
10. **Luck.** Whatever survives — size it against the field's distribution before calling it.

## Writing it up

- **Lead with what is actionable**, not with what is largest. A 6% window finding the player
  can fix tomorrow outranks a 30% gear gap they cannot.
- **Every number carries its comparison and its `n`.**
- **A summary statistic must be linked to a mechanism** or it is not a finding. "Your window
  multiplier is low" is a location; "six Blasts where the field spends one, entering with the
  generator blocked" is a finding. Always chase the statistic down to the cast list.
- **Wrong leads get one honest section**, with the test and the result. Deleting them silently
  destroys the reader's ability to check the work; narrating them through the body destroys
  the report.
