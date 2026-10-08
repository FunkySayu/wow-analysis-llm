# Building a boss death timeline: where progression attention should go

Method notes, written after producing the Vashnik the Malignant Mythic report. Deliberately
encounter-agnostic; Vashnik numbers appear only as illustration of a trap or a threshold.
The worked output is the published artifact; its stage 3–5 scripts stayed in the local working
area. A second, larger case on the same pipeline is
[sszorak-mythic.md](../raid/12_1/venomous_abyss/sszorak-mythic.md), which records its stage
order.

**Read [building-reports.md](building-reports.md) first.** It already covers the parts of
this that are not specific to death timelines: template plus injected payload, inlined
icons, the Wowhead tooltip endpoint that carries tuned damage values and how to parse it,
pointer-anchored tooltips, and the build-time validation that catches silent breakage. The
Vashnik report was built without consulting it, and re-derived several of its lessons the
slow way. This file only adds what is new.

## What the deliverable actually is

The question is **"which mechanic should the raid practise next"**, and the answer is a
ranking of mechanics by what they kill. Everything else — death-time distributions, the
shape of the killing blow, progression thirds — is context that *situates* that ranking. It
is not the product.

**The timeline is the product.** One row for the boss's measured schedule, five rows under
it for where deaths cluster. It was the piece the reader used; the statistical sections were
read once. Build the timeline first and let the rest be short.

The unit that carries the meaning is the **name of the killing blow**, not the shape of the
death. "Slow bleed versus one shot" turned out to be almost entirely determined by which
ability landed — one mechanic supplied 94 of the 144 "big hit" deaths — so the shape analysis
is a second-order restatement of the ability breakdown. Lead with the ability.

## The pipeline

Five stages. Each writes a JSON file the next one reads, so a failure late does not re-pull
the API.

| # | Stage | Produces |
|---|---|---|
| 1 | Sample guilds from the progress ladder | `selection.json` — guild, rank, report codes, fight ids per pull |
| 2 | Classify deaths per wipe | `deaths.json` — per pull, the first N deaths with killing blow and 5s damage window |
| 3 | Roll up by journal cluster | `payload.json` — the ranking, breadth/depth, journal coverage |
| 4 | Measure the fight's schedule | schedule marks, including abilities the cast stream cannot see |
| 5 | Fetch icons, render, publish | inlined data URIs, the artifact |

Stages 1 and 2 are already generic: [`tools/warcraftlogs/guild_progress_sample.py`](../../../tools/warcraftlogs/guild_progress_sample.py)
and [`tools/warcraftlogs/wipe_death_profile.py`](../../../tools/warcraftlogs/wipe_death_profile.py) take any encounter id
and difficulty. **Known issue in stage 2:** `wipe_death_profile.py` reads deaths from one
Deaths-*table* query across a report's fights, which `tools/warcraftlogs/README.md` documents
as silently empty after the first few fights of a long report (77 of 120 Sszorak pulls). Check
its per-pull death counts against a second source, or port it to per-fight `Deaths` events,
before relying on it. **Stages 3 to 5 are still encounter-specific scripts that were never
promoted out of the local working area, and that is the single biggest cost to repeat this.** Promote them first next time; the generalisation
boundary is small and is described under "What to build before the next boss".

## The traps

Every one of these returns **wrong or empty data rather than an error**. Each cost real time.

### Querying deaths and damage

1. **`targetID` on a `DamageTaken` event query silently drops enemy-sourced hits.** Asking
   for one victim's damage over the window that killed them returned only their own
   self-damage — neither boss hit that did the killing. `filterExpression: "target.id = N"`
   is worse: it returns **zero events, no error**. The only complete answer is the
   unfiltered window query, filtered by target in Python.

2. **`includeResources: true` is required for health.** Without it the events carry no
   `hitPoints` / `maxHitPoints`, so there is no way to tell a one-shot from a finishing tap.

3. **`overkill` is a sparse field.** It appears only on the killing blow. The blow's true
   size is `amount + overkill`; `amount` alone equals exactly the victim's remaining health
   and makes every death look like a perfect finish.

4. **The Deaths table's `events` array is capped at three entries.** It looks like a death
   recap and is not one — three events spanning as little as 14ms, while the same entry's
   `damage.total` covers five to fifteen times that. Its `deathWindow` is adaptive too (4.5s
   to 14.2s observed), not the fixed window you asked for. Use the table for *who* died and
   *when*, and raw events for the sequence.

### Identifying abilities

5. **The journal's spell id is not the log's spell id.** The Adventure Journal gave Plague
   Froth as 1281907; querying debuffs for it returned zero events on every pull. The log uses
   1281910, 1281913 and 1281925. This is the same failure the talent trees have — see
   `docs/design/60-plan-suggestions.md` for the Incarnation case.

6. **An ability is a name, not an id.** Three ids for one mechanic above, three for
   Congealing Bolt. Filtering on one id sees a fraction of the mechanic with no indication
   that anything is missing. Resolve names through the report's own `masterData.abilities`.

7. **One cast is N applications.** Plague Froth marks ten players at once, so the raw
   application count is ten times the number of waves. Collapse events inside ~2s into one
   event and **report the per-event target count**, so a wrong collapse is visible rather
   than silent.

8. **Paired casts make the cadence read wrong.** Malignant Catalyst fires twice 5s apart, ten
   times a fight. Taking the median gap over twenty marks says "every 5s"; the raid plans
   around ten events at 39s. Group casts inside ~10s into one marker carrying its own count.

### Things in the log that are not the boss

9. **The enemy cast stream contains player abilities.** Anti-Magic Zone appears in the
   encounter profile attributed to a synthetic `Environment` actor flagged as a boss. Its
   occurrence spread gives it away: an interquartile range of 222s where every real scripted
   ability sat at 0.0 to 0.1s. **A wild variance on a supposedly scripted ability is the
   tell.**

10. **A player item can land a killing blow.** "Seriously Sharp Seashell" appeared in one
    pull's damage-taken stream with **nine different players** as its source, so it is an
    item rather than a mechanic (its Wowhead icon is from the food set,
    `inv_misc_food_legion_seashelld2`; exactly what item it is was not established). Join every killing-blow
    name against the journal **in both directions** and inspect the source actor of anything
    that does not match — never a hand-maintained deny list.

11. **The ladder's kill report may not be the guild's, in either direction.** One guild's
    ladder entry cited a raider's untagged personal upload of a night the guild also logged;
    merging it unconditionally double-counts. Another guild's own reports held no kill until
    a reclear three days later, and refusing to merge answered "5 pulls" instead of 13.
    Merge the ladder report **only when the guild's own reports do not contain the ladder's
    first kill**, and dedupe preferring the guild's copy. `tools/warcraftlogs/guild_progress_sample.py`
    already does this.

### External data

12. **Wowhead tooltips need the `/ptr/` path segment** for a PTR build, or they serve live
    text with no error. Already in `CLAUDE.md`; it bit again here when resolving icons for
    abilities the journal does not carry.

13. **The Artifact CSP blocks external images entirely.** Covered in
    [building-reports.md](building-reports.md); inline as base64. Note that its recommended
    `medium` (36px) icons are enough — this report used `large` (56px) for 20px circles,
    which wastes bytes for no visible gain.

14. **An exact-match regex on the injected `const` line breaks silently.** The Vashnik
    injector matched `^const D = .*;$` literally, which is the form
    [building-reports.md](building-reports.md) warns against: realigning the line for
    readability stops the payload landing, and the page keeps rendering the previous run's
    numbers. Match whitespace-tolerantly (`^const\s+D\s*=`) when promoting it.

## The measurement that matters most

**A cast-based timeline cannot see the biggest killer.** The encounter profiles (`data/raid/<patch>/<tier>/<nn>_<boss>/profiles/`) are built
from the enemy *cast* stream, and the abilities that do most of the killing are applied
auras that emit no cast event. On Vashnik the top mechanic, 39% of all deaths, was absent
from the profile entirely, listed under `journalOnly` as "applied rather than cast".

Recover it from **debuff applications** (`dataType: Debuffs`, `type: applydebuff`) or from
damage events, then collapse per trap 7. Done over 26 pulls it was scripted tighter than
anything in the cast stream: every wave inside 0.2s of its median.

This is the step to do *early*, not last. Check the profile's `journalOnly` list against the
killing-blow ranking before drawing anything; any mechanic in both needs its own measurement
pass.

**Two independent samples that agree are worth far more than one large one.** The schedule
came from 97 ranked kills; the deaths came from 95 wipes by different guilds. All eleven
fountain-eruption deaths landed within 0.2s of a measured Imbibe. That is a real validation.
Keep the samples disjoint and say so.

## Classification, if you keep it

One axis: the killing blow as a share of the victim's maximum health, where the blow is
`amount + overkill` and absorbed damage is **excluded** (a shield that ate half the hit means
the player was not one-shot).

- one shot / near one shot: >= 80%
- big hit on low health: 30-80%
- slow bleed: < 30%

**Validate on an axis the rule does not use.** Health before the killing blow was recorded
and never used for sorting; the buckets came out at 6.8%, 35.5% and 85.6% median health. That
separation is the evidence the rule works. Build this check in from the start — it is free
and it is the only thing that makes the thresholds arguable.

Check the histogram before trusting the thresholds: the distribution was bimodal with a
genuine valley at 70-80%, so both cuts fell in gaps rather than through a crowd.

## Chart construction rules learned the hard way

- **Cluster name versus blow name will confuse the reader.** The top cluster was named after
  the parent ability (Plague Froth) while its biggest circle is the child that lands the blow
  (Plague Wave). Name clusters so the relationship is explicit, and say in the caption that
  lane circles are killing blows.
- **Medians collapse together.** Four mechanics' median death times landed inside four
  seconds. Plan for vertical tiering from the start; do not discover it at layout time.
- **Tier spacing must clear two full-size circles** (`2 * R_MAX + padding`), or marks on
  neighbouring tiers overlap as surely as marks sharing one.
- **Tiers fill upward before downward, which leaves a lane's mass above its own baseline** and
  reads as a vertical misalignment bug. Recentre each lane's stack on its baseline after
  placement. Horizontal positions stay true — never nudge time sideways.
- **Size lanes to the tiers they actually use.** Fixed lane heights left 114px of dead space
  in one lane and crowded another.
- **A right-aligned label grows leftward out of its column.** At 10px mono, 30 characters is
  ~180px in a 148px label column. Budget ~6px per character and truncate against the column,
  not against a guessed character count.
- **Circle size range needs to be wide.** `R_MIN + (R_MAX-R_MIN)*sqrt(n/maxN)` at 9 to 19 made
  49 deaths look barely larger than 1. 8 to 24 reads correctly.
- The dataviz ordinal ramp validates: `#86b6ef / #2a78d6 / #104281` light,
  `#cde2fb / #5598e7 / #184f95` dark. `--status-critical: #d03b3b` is fixed and never themed.

## Verification without a browser

There is no screenshot tool in this environment, so geometry is checked numerically. A
~40-line DOM stub that records `setAttribute` calls, runs the page's script under `eval`, and
then asserts is enough to catch everything that actually went wrong:

- every element the script writes into is non-empty (catches a silent render failure)
- no circle falls outside the viewBox
- no two markers in a lane overlap by more than 1px
- every icon `href` is a real data URI

The Vashnik and Sszorak builds each had such a stub (`smoke.js`, not yet in `tools/`) for the
populated-element check. The overlap and bounds checks were one-off inline scripts built on the
same stub; they found 11
overlapping marker pairs that looked fine in the code. Fold both into one reusable checker,
and update its list of expected element ids whenever the page changes — a stale list reports
a healthy page as broken.

## Two changes requested for next time

1. **All spell data on the hover card.** The card currently carries the journal description,
   tuned damage, timing and cadence. It should carry the complete tooltip: cast time,
   duration, range and radius, school, whether it stacks, the spell id, and — for anything
   that appears as a killing blow — the measured stats from the sample (deaths, guilds
   reached, median share of max health, whether it ever took two players at once). Sources:
   `data/raid/<patch>/<tier>/<nn>_<boss>/journal.json` for structure and tuned numbers; Wowhead's tooltip endpoint on its `/ptr/`
   path for the full rendered text, parsed as described in
   [building-reports.md](building-reports.md) (description is the last `<div class="q">`);
   WCL's `raidDamageTakenByAbility` for the ids and icon names as they actually fired; and
   the log roll-up for the measured half. Fetch tooltip and icon in one pass per ability and
   cache both. Keep the measured stats and the static spell text as two payloads keyed
   separately, per that file's "two payloads beat one merged map", because killing-blow
   names and spell ids do not map one to one (trap 6).

2. **The statistics take less space.** The ranked mechanic list stays. The killing-blow
   table, the breadth-versus-depth table and the journal-coverage table collapse into one
   compact table or move behind a disclosure. The progression-third distributions, the
   classification histogram and the health validation shrink to a short "how the deaths were
   shaped" strip near the end. Target roughly half the current page length below the
   timeline.

## What to build before the next boss

In priority order. The first two are most of the saving.

1. **`tools/warcraftlogs/encounter_death_timeline.py`** — stages 3 to 5, generalised. The
   encounter-specific inputs are small and can be a per-boss JSON: the cluster map
   (killing blow name to journal parent, derivable from the journal's `parentTitle` chain
   rather than typed), the abilities to draw on the schedule, and the prose for each cluster.
   Everything else in the Vashnik payload and timeline builders was generic.
2. **An `applied-aura schedule` measurement helper**, generalising the Vashnik Plague Froth
   measurement: given
   an ability name, resolve its log ids from `masterData`, pull applications across the N
   longest pulls, collapse into events, and emit marks with support and variance. This is
   the step that makes the timeline complete rather than cast-only.
3. **A shared icon + tooltip fetcher** that resolves an ability name to an inlined icon and a
   tooltip blob, falling back to Wowhead `/ptr/` by spell id when the journal lacks it.
4. **Generalise the smoke stub** into something any artifact in this repo can be checked with.

## The checklist

1. Sample guilds; confirm the ladder ranks and the pull counts against a known example.
2. Pull deaths per wipe; confirm nothing is unclassified before reading any share.
3. Rank by killing blow, then roll up to journal clusters via `parentTitle`.
4. Join killing-blow names against the journal **both ways**; resolve the source actor of
   every name that does not match before writing a word about it.
5. Diff the ranking against the profile's `journalOnly` list; measure any top mechanic the
   cast stream cannot see, from debuff applications.
6. Check the schedule for wild variance on a supposedly scripted ability — that is a player
   ability in the enemy stream.
7. Test the death times against the schedule with a chance baseline, per cluster.
8. Fetch and inline icons; confirm every href is a data URI.
9. Render; verify geometry numerically; publish.
10. Report breadth as well as depth — "eight deaths" means something different across three
    guilds than across ten.
