# WCL check toolkit

Reusable analyses over a WarcraftLogs report, so a question that has been answered
once never has to be re-derived. Every check is a function in `checks/<class_spec>.py`
(or `checks/common.py` for spec-agnostic ones), exposed through one CLI.

```
tools/warcraftlogs/
  lib/          shared utilities - check.py (Check + Report), timeline.py, format.py,
                spell.py, wclapi.py
  checks/       one file per class/spec (mage_arcane.py, druid_balance.py), plus common.py
  tests/        contract tests for the Check base class (no network, no credentials)
  run.py        CLI - merges every checks/*.py module's CHECKS dict
```

A check has two surfaces from one computation: `json()` returns the findings as data and
does all the log reading, `print()` renders that data as the text below. **The unit is one
pull** — a check computes `fight_json(fight)` and the base class maps it over the
selection, so nothing pools several pulls into one number by accident. `--json` emits the
data instead of the text, and [`tools/reporting`](../reporting/README.md) turns it into a report page
— one React component per check `id`. See § Adding a check.

```bash
wsl.exe -d Ubuntu -e python3 tools/warcraftlogs/run.py <check> -r <REPORT> -a <ACTOR> [-f <fights>]
```

The first argument is either a single check name or a **group**: `common`, `mage`
(Arcane), `druid` (Balance) run one module's whole suite; `all` runs literally
everything and mixes specs, which is rarely what you want.

Windows note: a bare `python` is the Microsoft Store stub. Run scripts with the `py`
launcher, or through `wsl.exe -d Ubuntu -e python3` from the repo root (the repo is mounted
at the same relative path, so `tools/...` works in both).

- `-r` report code — the last path segment of a warcraftlogs.com/reports/<code> URL
- `-a` character name, e.g. `Funkywand`
- `-f` fight selector: `all` · `encounters` (default) · `kills` · `raid` · `dungeon` ·
  or explicit ids `37,41,52`
- `--refresh` bypasses the cache for that call

Credentials come from `.env` (`WARCRAFTLOGS_CLIENT_ID` / `_SECRET`). The token and every
fetched event page are cached under `.wclcache/` (gitignored), so the first run of a
report is slow and every run after it is instant.

## The checks

| check | question it answers |
|---|---|
| `list` | what fights and players are in this report (no `-a` needed) |
| `abc` *(common)* | GCD uptime proxy - share of the fight with a gap over the GCD between casts |
| `cancels` *(common)* | hard-casts started vs. completed - cancelled or interrupted mid-cast |
| `mana` *(common)* | time spent in each mana band, and what was cast while dry |
| `consumables` *(common)* | food, flask, augment rune, weapon rune and potions, for every player |
| `potion` *(common)* | each combat potion against the kill: seconds of buff past the end, measured stat uplift, and what drinking it 30s before the kill was worth |
| `displaced` *(common)* | enemy debuffs on the player that halved their damage against their own surrounding seconds (same phase) - bombs, fixates, run-outs; seconds to extract before grading anything |
| `charges` | Arcane Charge economy: overcapped generation, charges held at each Barrage, Orb timing |
| `bolt` | Prismatic Bolt graded per **proc** - munched, expired, or spent against the APL's gates |
| `barrage` | every Barrage graded against the Sunfury APL's actual spend gates |
| `salvo` | Arcane Salvo spent per Barrage, share at max stacks, time overcapped |
| `soul` | is the Arcane Soul window being entered at max Salvo, or dumped into |
| `clearcasting` | how long Clearcasting sits capped at 3 and how many procs are lost |
| `tom-target` | how much of the Touch of the Magi window actually feeds the explosion |
| `cooldowns` | do Surge/ToM line up with Bloodlust and with the big/dangerous packs |
| `cd-usage` | raw cooldown efficiency: casts vs the theoretical maximum |
| `waves` | waves per Missiles channel — the empirical test for the Season 2 2-piece |
| `gaps` | dead time after a Missiles channel ends |
| `gear` | enchants/gems/secondaries for every player, as a control test |

Balance Druid (`checks/druid_balance.py`, group `druid`):

| check | question it answers |
|---|---|
| `eclipse` | Eclipse entries per minute and how much charge recharge was thrown away |
| `apex` | Ascendant Eclipses: are all 3 premium spenders used inside each Eclipse |
| `ap` | Astral Power overcapped, and which generator it leaked from |
| `dots` | Sunfire/Moonfire uptime on the boss, drops, and Shooting Stars rate |
| `spenders` | Starsurge/Starfall inside Eclipse vs. off-plan; procs consumed vs. expired |
| `cds` | CA/Incarnation, Fury of Elune, Force of Nature, Convoke usage and lust overlap |
| `apl` | priority-inversion audit — six rules, each citing the APL line it comes from |
| `refresh` | Moonfire/Sunfire re-applied while still ticking - the wasted-GCD count |
| `trace` | annotated cast-by-cast timeline (AP, Eclipse mode, apex stacks, live procs) |
| `fury` | Fury of Elune held after ready, graded per cast: FAIL = held 2s+ with an Eclipse charge already available. Cooldown reconstructed (45s - 1.5s per Starfire/Moonfire/Starsurge/Starfall), validated on 562 casts |

Groups: `common` · `fight` · `mage` · `druid` · `mage-compare` · `compare` · `all`.

Encounter structure (`checks/encounter.py`, group `fight`) — **spec-agnostic, and the
first thing to run on a boss you have not analysed before.** Nothing here is looked up;
it is all derived from the pull:

| check | question it answers |
|---|---|
| `fightmap` | phases, boss ability cadence, and the **measured** windows of opportunity — every bounded enemy self-buff scored by what the *raid's* damage rate does inside it |
| `addvalue` | is anything other than the boss worth a GCD here, i.e. is "hold cooldowns for the add wave" even a real option |

`fightmap` uses raid-wide damage rather than one player's on purpose: a single player's
own burst window would otherwise "detect" itself as a boss mechanic. A ratio above 1.15
is a window to put cooldowns in, below 0.85 is an immunity/soak/movement phase to keep
them out of, and — the useful case — **an ability the journal calls a vulnerability that
measures at ~1.0x means the raid is not converting it**, which is a finding about the
raid, not about the boss.

Arcane Mage peer comparison (`checks/mage_peers.py`, group `mage-compare`). **Run these
in order — the group already does.** They answer "why is my parse low" by eliminating
causes from the outside in:

| check | question it answers |
|---|---|
| `bar` | is the *pool* different, or am I? Your DPS on every ranked fight in the report against that encounter's own top-500 median. No `-f` needed. |
| `peers-arc` | split the DPS gap into hits/min (throughput) and damage/hit (how hard each lands), plus cast rates and damage per cast |
| `peers-buffs` | control test for a damage/hit gap: raid buffs and consumables the pool carries and you do not |
| `windows` | do you convert the fight's vulnerability window — as a multiplier over your **own** background rate, so gear and buffs cancel out — and what is the gap worth in damage |

Balance Druid peer comparison (`checks/peers.py`, group `compare`):

| check | question it answers |
|---|---|
| `peers` | you vs the top 25 on this boss: rates, damage share, DoT efficiency, buff uptime |
| `peers-builds` | is your talent build the one the top parses run, or are you missing a pick |
| `peers-stats` | secondary ratings and itemisation mix against the same 25 |

These need `-f <one fight id>`, not a selector — they compare one pull against the
ranking pool for that encounter and difficulty. The pool is
`worldData.encounter.characterRankings`, 1000 pulls deep by default; the top pages are
~99th-percentile players, so read the deltas rather than the rank. `bracketData` in the
rankings is item level, so `peers` also selects an ilvl-matched subset — rates and damage
shares are gear-robust, raw DPS is not.

### Worked examples

```bash
# Is Arcane Soul being set up properly in raid?
run.py soul -r AgzVT69J8kKRWGrt -a Funkywand -f raid

# Am I wasting Touch of the Magi on the wrong target in keys?
run.py tom-target -r AgzVT69J8kKRWGrt -a Funkywand -f dungeon

# Did my cooldowns land on lust and on the packs that mattered, in one dungeon?
run.py cooldowns -r AgzVT69J8kKRWGrt -a Funkywand -f 41

# Do I have the Season 2 2-piece? (7 waves = no, 8 = yes)
run.py waves -r AgzVT69J8kKRWGrt -a Funkywand -f raid

# Does this character actually have no enchants, or does the log just not record them?
run.py gear -r AgzVT69J8kKRWGrt -a Funkywand -f kills

# Did they eat, flask, and use a combat potion? (every player listed as the control)
run.py consumables -r JX1Vd49kL63QPwbY -a Funkywand -f 18

# Was this pull ever a low-mana rotation, or is the spender check just wrong?
run.py mana -r JX1Vd49kL63QPwbY -a Funkywand -f 18

# Which individual casts broke the APL, and why - per instance, not averaged
run.py charges -r JX1Vd49kL63QPwbY -a Funkywand -f 18   # charge economy + Orb timing
run.py bolt    -r JX1Vd49kL63QPwbY -a Funkywand -f 18   # per proc: munched/expired/spent
run.py barrage -r JX1Vd49kL63QPwbY -a Funkywand -f 18   # against the Sunfury spend gates

# What does this boss even look like, and where are the windows?
run.py fightmap  -r JX1Vd49kL63QPwbY -a Funkywand -f 18
run.py addvalue  -r JX1Vd49kL63QPwbY -a Funkywand -f 18       # are the adds worth a GCD?

# Why is my parse on this boss so much worse than on the last one?
run.py bar         -r JX1Vd49kL63QPwbY -a Funkywand           # no -f: every ranked fight
run.py peers-arc   -r JX1Vd49kL63QPwbY -a Funkywand -f 18
run.py peers-buffs -r JX1Vd49kL63QPwbY -a Funkywand -f 18
run.py windows     -r JX1Vd49kL63QPwbY -a Funkywand -f 18     # do I convert the amplify?
run.py mage-compare -r JX1Vd49kL63QPwbY -a Funkywand -f 18    # all four, in order

# Balance Druid: where is this player's rotation actually losing damage?
run.py druid -r ThRfrJBk1ZGwyCWc -a Funkitty -f raid

# Which specific casts broke the priority, and on which pull?
run.py apl -r ThRfrJBk1ZGwyCWc -a Funkitty -f raid

# Eyeball one pull GCD by GCD before trusting any of the summaries
run.py trace -r ThRfrJBk1ZGwyCWc -a Funkitty -f 5
```

## Reading four of them correctly

**`tom-target`** — three separate numbers, don't conflate them:
- *damage into the ToM'd target* is the share that feeds the explosion. In AoE this is
  naturally low (~45% in keys) because cleave hits everything; that is not by itself an error.
- *active time off the target* is small (4–6%) whenever targeting is fine — a high value
  here means genuinely facing the wrong way.
- *Placement* is the actionable one: the share of windows where something with >1.5× the
  HP was being hit in the same window. 0% means ToM always went on the biggest thing.

**`cooldowns`** — lust coverage is measured as **buff overlap, not cast-inside-window**.
A Surge cast one second before lust lands is perfectly aligned, and a cast-based test
scores it as a miss. Arcane Surge lasts ~18s against a 40s lust, so **~45% coverage is
the ceiling** — 43% is a perfect window, not a half-failure.

**`eclipse`** — read **`in combat`**, not `up%` and not the raw `capped s`. In 12.1
Eclipse is a charge-cooldown button and most of the spec's power is paid out on *entry*
(the apex talent, Balance of All Things, Solstice, Cenarius' Might), so entry count is
the constraint and Eclipse uptime is a side effect. Seconds at max charges are recharge
deleted — but only the ones where the player had something to hit: banking charges
through an untargetable phase is correct play, and the two are separate columns for
exactly that reason. On the reference log the raw total says 25 entries were thrown away
and the in-combat total says 16; the second number is the true one. The charge count is
**detected, not assumed** —
the check picks the fewest charges that make every observed cast possible, which is a
direct empirical test for `Improved Eclipse`. It cannot distinguish `Sculpt the Stars`
(29s vs 32s recharge), so it assumes 32s and therefore *understates* the waste.

**`dots`** — read the `longest gap` column before blaming the player. One long gap with
high uptime everywhere else is a phase where the boss was untargetable; many short drops
is the actual refresh problem. `1st cast` is separate on purpose — that one is opener
timing, not refresh discipline. `dots avg` is DoT-seconds ÷ fight-seconds across *all*
targets, so it exceeds 2.0 in cleave and is not a percentage.

**`apl`** — the `of` column is the number of *chances* to break each rule, so the rate is
the number that means something; raw hit counts scale with fight length. Rules that need
`fight_remains`, `target.time_to_die`, or a talent gate the log cannot resolve are
deliberately not implemented, so **the list is not exhaustive** — a clean report means
"nothing these six rules can see", not "nothing wrong". Hits are labelled `<fightID>:name`
so a finding can be reopened with `-f <id>` and inspected in `trace`.

**`bar` / `peers-arc` / `peers-buffs`** — the parse question, in the only order that
works. Two mistakes are almost automatic without them:

*A parse percentile is not a performance number across bosses.* Each encounter has its
own DPS bar. On `JX1Vd49kL63QPwbY`, Funkywand did **172,305 DPS on Sszorak for a p92** and
**170,521 on The Coiled Altar for a p36** — same night, same gear, 1% less DPS, 56
percentile points. The Coiled Altar's top-500 Arcane median is 227,218 against Sszorak's
186,594, a **22% higher bar**, because the fight has an intermission amplify window and a
second permanent target. `bar`'s `you/p50` column is the cross-boss-comparable number
(92.3% vs 75.0%): it says the real regression was ~17 points of DPS, not 56 of percentile.

*A DPS delta cannot tell throughput from hit size, and they have opposite fixes.* On that
same pull the rotation was **not** the problem — GCD uptime 75.2% against a peer median of
74.7%, GCDs/min 46.1 vs 45.7, hits+ticks/min 427.7 vs 435.3, Salvo per Barrage 21.5 vs
21.3, Clearcasting waste 5.8/min vs 6.1 — while **damage per hit was 30% low**. When
`peers-arc` reads level on hits/min and low on damage/hit, go to `peers-buffs`, not to
`salvo` or `abc`. There it found no food buff (10/12 peers at 100%), no Mark of the Wild
(12/12), no Blessing of the Bronze (11/12), and versatility at 75 rating against a peer
median of 570.

Two things to hold onto when reading `peers-arc`. The **`Arcane Blast noncrit` line is the
closest thing to a pure stat delta** — Arcane Blast is the last line of the APL, so it
lands in an unamplified state for everybody. And **damage per cast falls off in ability
order**: Blast −12%, Barrage −20%, Missiles −25%, Prismatic Bolt −32%, ToM −37%, Orb −41%,
which is exactly the order of how much each compounds on the Salvo economy and on amplify
windows. The spread between the Blast line and the rest is the part that is *not* raw
stats.

**`windows`** — the layer the three checks above cannot see. They all measure *rates*;
this one measures **conversion of the fight's amplify window**, as a multiplier over the
player's own background rate, so item level and raid buffs cancel out completely. A +100%
amplify hands everybody 2.00x for pressing nothing; everything above that is Surge, Soul,
Touch of the Magi, lust and the on-use trinket landing inside it.

On the reference pull the *placement* was already perfect and identical to the field —
every one of 10 peers and the player put Surge + Soul + ToM + lust into the window — and
the conversion still came out at **2.67x against a peer median of 3.53x**, worth **+4.5M
= +5.5% of the pull**. Two things separated them: the on-use trinket (peers 4 of 4 charges
inside a Surge window and 1 inside the amplify, universally; the player 0 inside the
amplify, having spent it at 193s and 284s on either side of a 231–269s window) and the
cast mix inside the window (7 of 37 GCDs on Arcane Blast, including six consecutive, where
peers spend 0–1 and run a clean `Prismatic Bolt → Barrage → Missiles → Missiles` loop).

Three traps, all of which produced a wrong answer during development:

- **Do not average non-overlapping windows.** An early version merged every aura above
  1.15x into one "window", folding a 1.18x aura lasting 111s into a 2.26x aura lasting 35s
  and reporting 2.02x instead of 2.67x. Auras that co-occur are one mechanic (Ghastly
  Regeneration + Deathguard + Soulbinding are the same 35 seconds); auras that do not are
  different decisions.
- **Do not define the window by whether the raid converted it.** Sszorak's Dig In is a real
  +30% vulnerability that measured **0.98x raid-wide** — the raid ignored it — while the two
  best Arcane parses on that boss converted it personally at over 2x. `windows` therefore
  falls back to the fight's recurring *phase* when no aura clears the bar.
- **The window multiplier does not rank players by itself.** The top parse in the Coiled
  Altar pool sits at 2.46x, *below* the p36 player being diagnosed, and wins on background
  rate instead. Read `windows` next to `peers-arc`, never in place of it.

The hold-versus-cast tradeoff is arithmetic and the check prints both halves. Sszorak,
priced on the player's own log: holding Arcane Surge ~51s to reach the second Dig In gains
**+4.83M** in the window and costs **−2.18M** for the Surge cycle it gives up — net
**+2.65M (+4.8%)**, which is exactly why the #1 parse on that boss runs three Surges where
everyone else runs four.

Fight-specific rotation findings still show up here even when the aggregate is clean:
Arcane Blast at **5.66 casts/min against a peer median of 2.80** (and 3.7/min on Sszorak,
where the pool does press it) — worth checking in `trace`, since the biggest single block
on that pull was 12 consecutive Arcane Blasts at 74.3–86.4s with Clearcasting at 0 stacks
and no Prismatic Bolt proc, each landing for 48k where a Prismatic Bolt lands for 391k.

**`peers` / `refresh`** — read them together, in that order. `peers` says *which*
metric is off; `refresh` says *why* for the DoT ones. The pairing that matters:
`ALL rotational GCDs` is a GCD-throughput proxy and `spenders SS+SF` is what the whole
Astral Power economy exists to produce, so a player low on the second but level on the
first is mis-spending GCDs rather than losing them to downtime — a different problem with
a different fix. `Moonfire ticks/cast` is the efficiency number: `Aetherial Kindling`
(327541) makes every Starfall extend active Moonfires and Sunfires by 3s to a 28s cap, so
in a Starfall-heavy build a low ticks/cast means the player is hand-refreshing a DoT the
rotation was already extending. Measured on `JqywQ2R1XpgZrVKL` fight 18: 36 Moonfire casts
for 791 ticks (22.0/cast) against a top-25 median of 34.8, while Sunfire sat at p56 — the
problem was Moonfire-specific, which is what a habit looks like rather than a
misunderstanding of the talent.

Two traps in `peers-stats` specifically. Ratings are **not** effective percentages: that
log showed haste 624 against a peer median of 829 (p8), which reads as a 25% deficit, but
the measured modal GCD was 1.171s against 1.126s — about 4%. Always confirm a rating gap
against something the log measures directly (DoT tick interval, modal cast gap) before
sizing it. And a stat gap only explains DPS if **damage per cast** is also low; there,
damage per Starfall was within 2% of the field, so the deficit was volume, not itemisation.

## Adding a check

1. Subclass `lib.check.Check` in the right file: `checks/common.py` if it needs no spell
   IDs and applies to any spec, otherwise `checks/<class>_<spec>.py` (e.g.
   `checks/mage_arcane.py`, `checks/druid_balance.py`).
2. Give it an `id`, a `title` and a `group`, and implement:
   - **`fight_json(fight)`** — read the log for **one pull** and return its findings as
     data. Exact numbers, spell IDs, real timestamps; round nothing. Anything the check
     infers about context (which talents are on, how many targets to assume) belongs in
     here, derived from *this* fight.
   - **`combine(parts)`** *(optional)* — roll `[(fight, fight_json), …]` up into the
     whole-selection view. Return `None` when a roll-up would be meaningless. Sum what is
     additive, take extremes where an extreme is the point, and use `C.consensus()` where
     the fights might disagree.
   - **`params()`** *(optional)* — the check's constants (a threshold, the APL text).
     Configuration, not findings, so a reader can tell the two apart.
   - **`print()`** — render the payload as the terminal text. **It must not read the log.**
3. Register it in that file's own `CHECKS` dict at the bottom via
   `CHECKS.update(C.registry(YourCheck))` — `run.py` merges every `checks/*.py` module's
   `CHECKS` automatically, no separate registration step. `registry()` rejects a missing
   or duplicate `id`.
4. Read the log through `self.report` — `self.report.events(fight, "Casts", resources=True)`
   already knows the report code and the actor and inherits caching. Use `lib.timeline`
   for stack/window/segment helpers, `lib.format` for printing (and `F.instance()` /
   `F.tally()` / `F.ledger()` for a per-instance graded check), and
   `lib.spell.get_spell(id)` / `get_aura(id)` if you need a spell's live tooltip text.
   Put any new spell ID as a module-level constant in that spec's check file, with a
   comment saying how it was confirmed.

```python
class AbcCheck(C.Check):
    """Always Be Casting: share of the fight with no GCD-consuming cast in flight."""
    id, title, group = "abc", "GCD uptime", "common"

    def params(self):
        return {"gcd": self.GCD}

    def fight_json(self, fight):          # ONE pull
        return {"casts": n, "downtimeSeconds": d, "uptimePct": u}

    def combine(self, parts):             # [(fight, fight_json), ...]
        return {"seconds": ..., "uptimePct": ...}

    def print(self):
        d = self.json()                   # {scope, params, fights, overall}
        ...

CHECKS.update(C.registry(AbcCheck))
```

**The unit of analysis is one pull.** The base class maps `fight_json` over the
selection, so every payload has the same shape and a check *cannot* pool pulls or reach
a fight it wasn't given:

```json
{"scope": "fight",
 "params":  {"gcd": 1.5},
 "fights":  [{"fight": {"id": 41, "name": "...", "seconds": 349.2}, "data": {...}}, ...],
 "overall": {...}}
```

This is enforced rather than advised because the loose version already shipped two faults.
`mana` blended fourteen pulls into one curve, which is not any pull's curve —
[analysing-a-pull.md](../../.claude/knowledge/method/analysing-a-pull.md): *"an aggregate hides
sequencing completely"*. And `barrage` read the hero tree and `aoe_count` from
`fights[0]` and graded every pull against them; on the reference report `-f all` that pair
takes four different values across 54 fights. Per-fight computation makes that class of
mistake unavailable, and `C.consensus(parts, key)` rolls a per-fight inference up while
*reporting* the disagreement instead of silently taking the first answer.

A check whose finding genuinely is not per-pull — one that reads the raid roster, or
compares actors across a whole night — sets `scope = "run"` and implements `json()`
directly.

**Why the split, and why `print()` may not touch the log.** The `id` is also the key that
pairs the check with a React component in [`tools/reporting`](../reporting/README.md), and `json()` is
what that component renders. A `print()` that reaches past the payload works fine in a
terminal and silently breaks three things at once: `--json`, `Check.from_json(payload)`
(re-rendering the text from a saved extract, with no API), and every report. It is
asserted, not just documented — `tools/warcraftlogs/tests/test_check_base.py` builds checks with
`report=None`.

```bash
# the payload, instead of the text - a group name works too
run.py common -r <REPORT> -a <ACTOR> -f raid --json -o scratch/viz/common.json
# then: tools/reporting/build_report.py scratch/viz/common.json -o reports/<name>.html
wsl.exe -d Ubuntu -e ./site/backend/.venv/bin/python -m pytest tools/warcraftlogs/tests -q
```

**Two scopes, and only two.** `scope = "fight"` is the default and covers 34 of the 35
checks. `scope = "run"` is for a finding that is genuinely not per-pull — `bar` is the
only one, because it compares every ranked fight in the report *against each other*, so
narrowing it to a pull would delete what it measures.

Three kinds of input resist per-pull computation and each has a documented home rather
than a workaround:

| input | where it goes | why |
|---|---|---|
| thresholds, APL text | `params()` | configuration, not a finding |
| talent inferences (Eclipse charges, cooldown models) | `_RunLevel` mixin, surfaced via `params()` | the identifying evidence is the shortest gap across the *whole* selection; one pull cannot carry it |
| an inference that may differ per pull (hero tree, `aoe_count`, 4-piece) | per fight + `C.consensus()` | reports the disagreement instead of picking the first answer |

Peer-comparison checks subclass `C.PoolCheck`, which caps analysis at the first ranked
pull (`POOL_FIGHTS`). Each pull costs 10–25 peer profiles at several queries each, so an
uncapped `-f raid` would fire hundreds of ranking queries from one command.

`run.py` still adapts a plain `check_<name>(code, actor_id, fights)` function if one is
added, but none remain — every check has a payload and `--json` reports an empty
`unported` list.

Spell IDs that bite (Arcane Mage, in `checks/mage_arcane.py`): Arcane Missiles is
`5143` as a **cast** but `7268` as **damage** — querying damage for 5143 silently
returns nothing. Arcane Orb is a wrapper (`153626`) whose damage lives on the child
`153640`. Touch of the Magi is `321507` to cast, `210824` as the enemy debuff, `210833`
as the explosion.

Spell IDs that bite (Balance Druid, in `checks/druid_balance.py`): Moonfire is `8921`
to cast but `164812` as the DoT, and `8921` produces **no tick events at all**. Sunfire
is `93402` to cast and `164815` for both damage and the DoT. Eclipse is two cast IDs for
one button — `1233272` Lunar and `1233346` Solar — while the buffs are the old `48517` /
`48518`, and CA/Incarnation applies **both** at once. Shooting Stars fires under two IDs
(`202497` and `1272339`); counting only the first silently loses ~10% of the procs. The
`Touch the Cosmos` buff is `450360` but the talent is `450356`, and the same split
applies to Balance of All Things (`394048` talent, `394049`/`394050` buffs).

**`charges` / `bolt` / `barrage`** — these three grade every *instance* rather than
reporting an average, and they grade against the **SimulationCraft APL**
(`ActionPriorityLists/default/mage_arcane.simc`, simc `aa9de89aac` / Sep 5 2026), not
against WoWAnalyzer's thresholds. The two disagree in specific, checkable places and the
APL is the ground truth per the project rule; the divergences are written up in
[arcane-mage-12.1-ptr.md](../../.claude/knowledge/classes/mage/arcane-mage-12.1-ptr.md). The practical
consequences:

- **A low Arcane Orb cast count is not a fault for Sunfury.** The APL gates Orb behind
  `arcane_charge.stack<3` and the 300s reference sim casts it *twice*. WoWAnalyzer shows
  Orb on a cast-efficiency bar (25% on the reference pull), which reads as "press it more"
  and is the single most misleading number on that page for this build.
- **`barrage` grades higher than WoWAnalyzer on purpose.** Its Sunfury evaluator has no
  branch for `salvo>8 & cooldown.touch_of_the_magi.ready` — a condition its own on-page
  explanation lists — so Barrages fired to set up ToM come back "Ok". On the reference
  pull that is 7 casts, plus 18 Arcane Soul casts it grades merely "Good"; those 25
  reconcile almost exactly with its 24 "GOOD" against this check's 91 PERFECT.
- **`bolt` is per proc, not per cast**, because a munched or expired proc leaves no cast
  event at all. It also fails a Bolt cast under Arcane Soul (`buff.arcane_soul.down` is
  half the APL gate, and the reference sim casts Bolt under Soul 0 times in 31) where
  WoWAnalyzer grades the same cast Perfect.

**`mana`** — run this *before* concluding a spender check looks bad. Most APLs have a
distinct low-mana branch, and a rotation check reading only buff stacks will score it as a
mistake. The bands cross-validate against WoWAnalyzer's own mana chart (86.8/5.5/2.3/4.1/1.3
against its 86/6/2/4/1 on the reference pull), so a large disagreement means one of the two
is broken rather than that the player changed.

## Traps these checks had to work around

**`sourceID` and `hostilityType: Enemies` do not combine.** Passing both to an events
query returns zero rows — no error, just nothing. Fetch by ability with hostility
`Enemies` and filter on `sourceID` in Python.

**Debuff apply/refresh/remove events are keyed on the aura, not the caster.** When
several players put the same DoT on one target, the second caster's application logs as
`refreshdebuff` and only one `removedebuff` is emitted for all of them — so reconstructing
one player's DoT uptime from `applydebuff`/`removedebuff` is wrong in exactly the fights
where it matters most. Verified on fight 10 of `ThRfrJBk1ZGwyCWc` (four druids, one
boss): the debuff stream implies a 38-second Moonfire drop that the tick stream shows
never happened. **Reconstruct DoT uptime from tick events instead** — damage always
carries the true `sourceID`. `_dot_windows` in `checks/druid_balance.py` does this, and
that first, wrong version was reporting a 10.2% priority-inversion rate that was
essentially all false positives.

**Arcane Charges have no aura at all.** Aura `36032` returns **zero** buff events on this
build — not a partial stream, nothing — so charges cannot be read the way Salvo or
Clearcasting are. Rebuild the pool from `dataType: Resources`, where charges arrive as
`resourcechange` with `resourceChangeType: 16` and `maxResourceAmount: 4`. Two rules
change the answer: **`resourceChange` includes the overcapped part and `waste` is that
part**, so effective gain is `resourceChange - waste` and adding both to a waste tally
double-counts (the first version of `charges` reported 127% of generation overcapped,
which is how the bug was caught); and a spender must be evaluated on the charges it held
*before* any energize sharing its timestamp, which is why `_charge_timeline` sorts casts
ahead of gains at equal `ts`.

**JSON caching stringifies dict keys.** `cached()` round-trips through JSON, so a producer
that returns `{int: ...}` yields int keys on the first, uncached call and **str keys on
every run afterwards** — every lookup then silently returns the fallback. Coerce keys on
the way out of `cached()`, not inside the producer; `wclapi.ability_names` does.

**Combat potions are not named "... Potion".** In Midnight the stat potion is *Light's
Potential*, so matching consumables by name reports zero potions for a player who used
two. `common.COMBAT_POTION_IDS` holds tooltip-confirmed IDs and `consumables` says so
explicitly when it finds none, rather than printing a clean-looking zero.

**An aura applied before the pull has no events inside the fight.** Hunter's Mark
persists through a wipe: on fight 4 of `nLvb3TFZGgXWaNry` one hunter moved their mark to
Trader Gebbo 101s before the kill started and never touched it again, so a debuff query
bounded to the fight shows two targets marked and Gebbo never — and an interval builder
that only opens on `applydebuff` reports the mark missing all fight. The damage stream
disproves it: DoT ticks landing on two explorers in the same 40ms, restricted to moments
when neither carries a boss buff, put Gebbo at x1.03 against both others. For any
long-lived aura (marks, brands, pre-pull DoTs), query `Debuffs` from well before
`startTime`, and check a surprising absence against paired hits.

**The Deaths *table* truncates across a multi-fight query, silently.** Asking for
`table(dataType: Deaths, fightIDs: [every pull in the report])` is the cheap way to get a
guild's deaths and it is wrong for exactly the reports a progression study uses. On a
four-fight report it returns everything; on a forty-pull report it comes back populated for
the first few fights and **empty for the rest, with no error and no truncation flag**.
Measured on the Sszorak sample, **77 of 120 pulls carried zero entries** while the raid-wide
2s damage tick showed 14 to 18 players stopping in those same pulls. Query `dataType:
Deaths` as *events*, per fight: it is not capped that way and carries `killerID` and
`killingAbilityGameID` directly. The Sszorak analysis did this and cross-checked each
fight's count against the tick detector. **`wipe_death_profile.py` still uses the
multi-fight table query** (`deaths_table`, one request per report) and is exposed to this
on long reports — port it to per-fight events before trusting its counts there.

The cost of not catching it is not a missing section, it is a *wrong* one: a bomb-carrier
mortality rate read 0.7% against a true 6.4%, and a soak-failure comparison showed a
fourfold effect that vanished entirely once wipes-in-progress could be excluded properly.

**`includeResources: true` is what carries `x`/`y`, not just `hitPoints`.** Without it,
cast and damage events come back with no position fields at all and nothing says so — the
events look complete. With it, every event that has a resource actor also carries `x`, `y`,
`facing` and `mapID`, for enemies as well as players, which is how a boss's position is
obtained. Coordinates are in hundredths of a yard.

**A raid-wide periodic tick is a free position track for everyone.** Sszorak's Ula'tek's
Presence hits all twenty players every 2s; pulled with `includeResources` it gives a
2-second-resolution position for every living player for the whole fight, in one query. The
same events double as a **death detector** — a player the tick stops landing on, well before
the pull ends, is dead — which is what caught the Deaths-table truncation above. Look for
this ability on any boss before writing a bespoke position query: a mechanic's own DoT does
the same job at 1s resolution for exactly the players it is on.

The shared instinct with the two spell-ID traps: an API that returns the *wrong* answer
without complaining is more dangerous than one that errors. Cross-check any reconstructed
signal against an independent stream before building a finding on it.

## Positions and resource snapshots (the data behind the replay)

There is no replay endpoint, and none is needed. `events(..., includeResources: true)` returns,
on every event, a snapshot of **one** unit: `x`, `y`, `facing`, `mapID`, `hitPoints`,
`absorb`, `classResources` (`[{amount, max, type}]`), spell power, versatility, item level.

- `resourceActor` says whose snapshot it is: `1` = source, `2` = target. Your casts and the
  damage you take carry *your* position; your damage done carries the *target's* (that is how
  boss and add positions are read).
- Coordinates look like yards × 100: on `ZvwYhTV74g9bMdL2` fight 20, Funkitty at
  (−2192, 65538) and Ithraz at (−1616, 69157) are ~37 yd apart. Confirm the scale against a
  known distance before relying on it.
- Sampled per event, not continuous: a caster gets ~1 point per second.
- Astral Power is resource `type 8`, scaled ×10 (`380/1000` = 38 AP). Energy shows as
  type 3 while in Cat Form.
- Requires the logger to have Advanced Combat Logging on (otherwise the fields are absent).
