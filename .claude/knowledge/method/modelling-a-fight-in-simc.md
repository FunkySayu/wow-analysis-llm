# Modelling a real fight as a simc fight script

Method notes, written after building a phase-1 script for Ula'tek heroic from a raid log.
Deliberately encounter- and spec-agnostic; the Ula'tek numbers are illustration, not the
point. The worked case lives in
[scratch/bdruid/ulatek/README.md](../../../scratch/bdruid/ulatek/README.md).

Companion to [analysing-a-pull.md](analysing-a-pull.md). That file is for *what went wrong
in this pull*. This one is for *what is better in general* — when the question stops being
"did I play this pull well" and becomes "which of these two rotations is better on this
boss", and in-game A/B testing cannot answer it.

## The core idea

**A scripted encounter is a measurement instrument you can rebuild.** If the adds spawn on a
timer and the phases land on a clock, the whole fight can be re-expressed as a simc fight
script, and a question that needed forty pulls to answer needs one sim run.

But the script is the cheap part. **The value is entirely in the validation loop**, and the
failure mode is shipping a script that runs, produces plausible numbers, and is wrong. A sim
that reproduces the fight's *timings* but not its *mechanics* will confidently rank your
variants backwards. Budget most of the effort for proving each piece matches the log
separately.

## Step 0: prove the exercise is worth doing

Before any of this, measure **pull-to-pull spread** on the metric you care about. Take every
pull that reached the end of the window and compute the metric per pull.

If the spread dwarfs the effect size you are chasing, that is the whole justification. On
Ula'tek P1 seven pulls spanned 314,816 → 354,190 DPS — a **12.5% swing** — against
micro-adjustments worth 1–3%. That is unmeasurable in game at any realistic pull count, and
it is why the sim is worth building. A sim converges to ±0.1% at 10k iterations.

If the spread is small, or the effect is large, skip all of this and just play more pulls.

Then prove the fight is actually scripted, or the premise collapses:

- Pull phase transitions for every pull and compare. Identical to a tenth of a second is the
  signal you want.
- Compute mean **and population stddev** of every spawn time across pulls. Report the stddev;
  it is what licenses the whole approach. On Ula'tek, spawn stddevs were 0.2–1.5s over
  seven pulls.

## Step 1: get the actor from an authoritative source, never by hand

Pull gear and talents out of a Raidbots report's `sim.players[0].gear` (each entry has an
`encoded_item` string that is already valid simc syntax) and generate the profile
programmatically. Hand-transcribing sixteen slots of bonus IDs is a silent-error machine, and
a wrong bonus ID does not fail — it produces a plausible number.

Check the report's timestamp against the log's. A snapshot from a different night is a
different character.

## Step 2: derive the fight's structure from the log

Per enemy *instance* — `(targetID, targetInstance)`, never just the NPC name — collect:

| what | how | caveat |
|---|---|---|
| spawn | first damage taken | **there is no spawn event.** This is an upper bound: the raid must notice and hit the add first |
| despawn | last damage taken | |
| death | a `Deaths` event | its *absence* is the signal that the add despawns rather than dying |
| effective HP | total damage taken | if this is byte-identical across every instance and every pull, the add has fixed HP and always dies |

That last row is a free consistency check. Ula'tek's Blightscale Rawlings took exactly
5,206,644 across all thirteen instances in all seven pulls — which both confirms the extract
is sound and tells you they die rather than despawn.

Then aggregate by (NPC name, ordinal-within-pull) across pulls so you get mean ± stddev per
wave rather than one pull's accident.

## Step 3: find the real damage window, not the phase label

**The phase transition the log marks is a UI event and is usually not the boundary you
want.** On Ula'tek the P2 marker is at 164.1s, but the boss goes untargetable at 155.95s —
the last 8 seconds of "phase 1" are dead. Simming to the label would have padded every
iteration with 8 seconds of nothing and silently deflated every DPS number.

Find the boundary by looking for **gaps in damage taken** by the boss, not by trusting the
phase list.

## Step 4: hunt the mechanics that do not show up as timings

This is the step that separates a script that ranks variants correctly from one that does
not. Two classes, both invisible in a naive extract:

### Untargetability — split damage into direct and tick

A boss that is untargetable but still has your DoTs on it produces **no gap in total damage
taken**. Ula'tek's 4.5s Submerge was invisible to a gap check over all damage and obvious the
moment damage was split on the `tick` flag: direct damage stopped dead at 62.0 and resumed at
66.6, tick damage had no gap at all.

Generalise: **whenever you check for a gap, check it separately on direct and periodic
damage.** A gap in one and not the other is a mechanic.

Cross-check by looking at enemy *casts* in the window — the boss usually announces it
("Submerge" at 62.0).

### Damage amplification — two independent methods that must agree

If one target is taking wildly more damage than its share, suspect an amp. Measure it two
ways and only believe the answer if they agree:

1. **`amount / unmitigatedAmount` per ability, per target.** This isolates target-side
   modifiers, because player-side buffs are already in both numbers. Compare the ratio on the
   suspect target against the same ability on a normal target.
2. **Hits on the two targets paired within a few seconds.** This controls for the player's
   buff state, which is the dominant confound.

On Ula'tek both landed on ~2.0–2.4x for the Venomous Heart.

**Expect the naive version of method 2 to lie on specific abilities and understand why before
dismissing it.** Starfire read 6.4x by pairing but 2.06x by unmitigated — because when the
player targets the add, Starfire's *main* hit lands on the add and only *splash* lands on the
boss, so the pairing was comparing two different components. When the two methods disagree,
the disagreement itself is the finding.

### Geometry: who splashes onto whom

If the question involves cleave, **target count is not enough. Groups matter.** Measure
it from the player's own AoE hits, clustered by timestamp. On Twin Fangs, Starfire on a
boss hit both bosses 88 times and a Spawn zero times, while Lunar Bolt on a Spawn hit all
three. That means two stacked groups, out of each other's splash. A flat
`desired_targets=5` would have let every boss Starfire cleave the adds, which is exactly
the behaviour being priced.

Express it with distance targeting:

- `distance_targeting_enabled=1`
- `x_pos=`/`y_pos=` per `enemy=`
- `spawn_x=`/`spawn_y=` on add events: radius 0 stacks them exactly
- `move_enemy` for temporary splits, e.g. Vile Flood separating the bosses for ~24s

Then confirm every ability's target set in a trace. Distance targeting is where simc's
silent bugs live (see the traps table). Worked case:
[scratch/bdruid/twinfangs/README.md](../../../scratch/bdruid/twinfangs/README.md).

**Price the add/boss exchange rate.** Bosses can carry raid-applied debuffs that
short-lived adds never collect. On Twin Fangs the bosses took 1.135x what a Spawn took,
measured by two agreeing methods. Without that, every "put damage on the adds" variant is
overvalued.

## Step 5: express it in simc

Recurring decisions, with the reasoning that generalises:

**Adds: `duration=`, not `health=`.** A single-player sim has none of the other 19 raiders'
damage, so health-based adds simply never die. Measured lifetimes reproduce the window during
which each add is *available to hit*, which is what the rotation actually responds to. Use
`health=` only if you are simming the whole raid.

**One-shot events use `timestamps=`.** The `first=`/`last=`/`cooldown=` form **silently never
fires when `last == first`** — the sim runs, no add ever spawns, no error. `timestamps=` is
simc's own mechanism for scripted encounters and cannot be combined with `first=`/`last=`.

**Pad the horizon past the damage window and make the boss immune for the tail.** Otherwise
the APL's end-of-fight lines (`fight_remains<20`, `fight_remains<=30`) fire inside the window
you are measuring. On Ula'tek that would have put the stock APL's cooldown dump exactly on
the Heart spawn — every variant would have looked like it burst correctly, for entirely the
wrong reason, hiding the thing being tuned. Pad, and normalise damage by the real window
length when reporting.

**Untargetable is not the same as immune, but `invulnerable` is usually still the right
tool** — because it is the only thing that *enforces* the constraint (`action_t::target_ready`
refuses a harmful cast at an invulnerable target, so the sim cannot park a ground-effect
cooldown on a submerged boss). It also zeroes DoT ticks that really land. **Measure that cost
before accepting it**: on Ula'tek it was 0.115M, 0.22% of a pull. Cheap. If it were 5%, you
would need the APL-discipline approach instead.

**Linked health pools are accounting, not modelling.** Ula'tek's Gore Rattle adds share the
boss health pool, so their damage is boss damage. Nothing changes in the sim; the *reporting*
changes, and it matters — ~7.9M of a 51M pull sitting in the wrong bucket makes every
boss-vs-adds tradeoff read wrong.

### Mapping the metrics

`prioritydps` is damage to `sim->target` and `dps` is everything, which gives a boss-vs-total
split for free. **simc reports nothing per-add**, so any finer breakdown has to come from
differencing: run the same profile with successive add groups removed and subtract. The two
endpoints stay exact; the middle is good to a few percent, because removing a target shifts
the rotation slightly. Say so when you report it.

## Traps that fail silently

Consistent with the rest of this repo's experience: **the dangerous failures return wrong
data, not an error.**

| trap | symptom |
|---|---|
| `raid_events` with `last == first` | event never fires, sim runs fine, no add ever spawns |
| `fight_style=Patchwerk` alongside `raid_events` | the style resets the raid-event list: no add spawns, no error, header says `fight_style=Patchwerk`. Omit `fight_style` (the header then reads `None`) — confirmed 2026-09-30 on the Vashnik trinket sims |
| `vulnerable` / `invulnerable` with `target=` | resolves in the *constructor*, before raid-event adds exist; on a miss it **silently applies to the boss instead** — the exact opposite of what you asked. Needed a vendored simc patch |
| `fixed_time=1` | `target.time_to_die` returns remaining *fight* time for every add, so APL lines gated on it will dot adds a real player would not |
| add names | adds are pets of the enemy: the runtime name is `<master>_<event name><index>`, e.g. `Fluffy_Pillow_venomous_heart1`, not what you typed |
| `bloodlust_time=` | silently ignored unless `override.bloodlust=1` is also set — sim.cpp only schedules the Bloodlust Check event `if ( overrides.bloodlust )`. Parses fine, runs fine, no buff, no error |
| appending to an APL `if=` with a regex | action lines carry options *after* `if=` (`,line_cd=999`, `,target_if=`); a regex that grabs to end-of-line folds them into the expression. Edit comma-separated option tokens, and parenthesise the existing condition — `&` binds tighter than `|` |
| Git Bash on Windows | `raid_events+=/adds,...` on the command line gets MSYS path-mangled into `C:/Program Files/...`. Put sim options in a file |
| `vulnerable,multiplier=` | it is the damage-taken **increase**, not the factor: `player.cpp` applies `m *= 1 + value`. `multiplier=1.135` gave **2.135x**, and every bucket came out ~1.9x the log (Twin Fangs, 2026-10-06). The Ula'tek script's `multiplier=2` for a measured 2x Heart is therefore **3x** |
| fight file declaring `enemy=` | options and `actions=` lines attach to the most recently declared actor. Put the fight file **before** the actor and its APL, or the APL lands on an enemy |
| invulnerable as "dead" | an invulnerable target still takes 0-damage hits, so it still counts toward AoE target-count scaling. Also `move_enemy` it out of range |
| distance targeting + ground AoE | **needs the vendored patch.** A reused `ground_aoe_params_t` keeps the first cast's coordinates forever, so Fury of Elune cast on an add landed on the boss. The pulse's target cache is also filtered against the *previous* pulse's position |
| profilesets with enemies declared in the fight file | profilesets edit **actor 0** by default and enemies count, so every profileset silently re-geared the boss. Set `profileset_main_actor_index` to the player's index among all actors. `profileset_report_player_index` counts players only |
| a `.` in a profileset name | the profileset is dropped with a "Trivial: Warning: Unknown option". Count results against profilesets sent |
| distance targeting + `target_if` | **needs the vendored patch.** Candidates came from the action's splash-filtered cache, so an AoE spell could never `target_if` onto a separate group (Starfire saw 2 of 5 enemies). Rebuilding that cache stored an unfiltered list as valid, so the spell's next AoE ignored its radius |

## Step 6: validate per bucket, never on the total

**A matching total proves nothing** — two errors of opposite sign cancel, and that is the
common case, not the unlucky one. Validate every damage bucket independently against the log,
and validate *behaviour* as well as damage:

- damage per target group vs the log's median pull
- cooldown *counts* (Ula'tek: Incarnation 2.99 in sim vs exactly 3 in every pull)
- cooldown *timings* (137.5s vs the raid's 138.0s)
- idle windows (sim stops casting 62.19–66.67 vs a measured 5.5–6.1s idle)

**A null result is a claim, and it needs the same proof as a positive one.** Three
variants in this project came back as exactly zero difference and all three were
bugs, not findings: an Eclipse line whose condition could never be true, an extra
Eclipse cast for which the charge did not exist, and a bloodlust option that was
silently never scheduled. Before reporting "X does not matter", open the action
sequence and confirm X actually happened.

Compare against the log's **median pull, decomposed from that same pull** — medians of
components do not sum to the median of the total, and quoting a decomposition that does not
add up undermines everything else you say.

### A residual is a finding, not a failure

When a bucket does not match, the question is *which side is wrong*, and it is often the sim.
On Ula'tek the final script matched boss damage to within 6% and was 39% short on the Heart
while 49% over on trash — which says the sim is spending GCDs on trash that the player spends
on the burn target. That is a real, actionable statement about the APL, not a modelling
error.

### The sim is not an upper bound until it beats the player

The most important thing this exercise taught. The best Ula'tek script came in **4.6% below**
the player's median pull. It is tempting to report that as "you are 4.6% from optimal" — it
is the opposite. The sim is an un-tuned strategy someone wrote; the player's hands were better
at the part that mattered.

**Do not rank variants while the sim is losing to the player on the axis being ranked.** Fix
the sim's execution of that window first, or every conclusion is an artefact of your own APL
being bad. State this explicitly when handing numbers over, because "sim says X" carries an
authority it has not earned yet.

## The checklist

1. Measure pull-to-pull spread. Confirm the effect you want is smaller than it.
2. Confirm the fight is scripted: phase transitions and spawn stddevs across pulls.
3. Generate the actor from a Raidbots snapshot, programmatically.
4. Extract per-instance spawn / despawn / death / effective-HP from the log.
5. Find the real damage window from damage gaps, not the phase label.
6. Split damage into direct vs tick and look for untargetability.
7. Hunt damage amps with two independent methods; make them agree.
8. Build the script: `timestamps=`, `duration=` adds, padded horizon with an immune tail.
9. Map the metrics; plan the differencing runs you will need.
10. Validate every bucket *and* the cooldown counts, timings and idle windows.
11. Only then run variants — and only if the sim is not losing to the player.
