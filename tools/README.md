# tools/ — Python (and a little Perl) used during analysis

One folder per data source or concern. Scripts are run directly (`python3 tools/<dir>/<x>.py`,
from the repo root); they are not an installed package. Anything that reads or writes
`data/` goes through [datalayout.py](datalayout.py), which is the single place that knows
the `data/` layout ([data/README.md](../data/README.md)).

| folder | what | entry points |
|---|---|---|
| [warcraftlogs/](warcraftlogs/) | WCL API v2: reusable log checks, and the ranking-pool dataset builders | `run.py`, `encounter_profile_sync.py`, `plan_suggestion_sync.py`, `guild_progress_sample.py`, `wipe_death_profile.py` |
| [game_knowledge/](game_knowledge/) | encounter facts from Blizzard's journal, Wowhead and NSRT | `journal_sync.py`, `nsrt_timer_import.py` |
| [raidbots/](raidbots/) | Raidbots' static talent feed -> validated talent trees, plus tree art | `talent_tree_sync.py`, `talent_background_sync.py` |
| [keystoneloot/](keystoneloot/) | KeystoneLoot addon export and loot DB -> item/loot data, and the loot-table page template (used by the `keystoneloot-favorites` skill) | `keystoneloot_sources_sync.py`, `*.pl`, `zone_table_template.html` |
| [wowhead/](wowhead/) | blue-post text extraction (used by the `wowhead-blueposts` skill) | `extract_bluepost.pl` |
| [reporting/](reporting/) | the React presentation layer for check payloads, and report -> site-seed extraction | `build_report.py`, `extract_report_content.py` |
| [simc/](simc/) | patches to the vendored simc for bugs that return wrong data (distance targeting, targeted vulnerability) | `*.patch`, see its README |

Shared: `.env` (credentials) and `.wclcache/` (API cache) sit at the repo root. Tests:
`cd tools && python -m pytest` (ruff/mypy scope is set in `pyproject.toml`).

Adding a tool: put it in the folder of the source it reads; take slugs on the command line
(`--zone venomous-abyss --spec balance-druid`) and resolve them with `datalayout`; write
`meta.generator` as its repo-relative path.

## warcraftlogs/ — reusable log checks

**Run these instead of re-deriving an analysis.**
`run.py <check|group> -r <report> -a <actor> -f raid|dungeon|<ids>`. A group name runs one
spec's whole suite: `mage` (Arcane) covers salvo cycle, Arcane Soul setup, Clearcasting
waste, Touch of the Magi targeting, cooldown/lust/pack alignment, Missiles wave count (the
set-bonus test), channel gaps, and three **per-instance graded** checks (`charges`, `bolt`,
`barrage`) that score every cast against the SimulationCraft APL rather than an average;
`druid` (Balance) covers Eclipse entry economy, the apex spender window, Astral Power
overcap, DoT uptime, spender/proc discipline, cooldown-and-lust alignment, an **APL
priority-inversion audit** and an annotated cast trace; `common` adds GCD uptime, cancelled
casts, the mana curve and a consumables/gear control test. See
[warcraftlogs/README.md](warcraftlogs/README.md) — it also records the API traps these checks
had to work around, all of which return *wrong data* rather than an error. Events cache to
`.wclcache/`. When you answer a new question about a log, add it there as a check rather than
as a one-off script.

A check is a `Check` subclass (`warcraftlogs/lib/check.py`) with two surfaces from one
computation: **`json()`** does all the log reading and returns the findings as data;
**`print()`** renders that data as the terminal text and *must not touch the log* — a rule
the test suite enforces by constructing checks with no report. The check's `id` is the
pairing key: the CLI name, the key in the `--json` envelope, and the key its React component
registers under. All 35 checks are ported, so `--json` covers the whole suite.

**The unit of analysis is one pull, and the base class enforces it.** A check implements
`fight_json(fight)`; the base maps it over the selection and calls `combine(parts)` for the
roll-up, so every payload is `{scope, params, fights[], overall}`. This is structural rather
than advisory because the loose version shipped two real faults: `mana` blended fourteen
pulls into a curve that was no pull's curve, and `barrage` read the hero tree and
`aoe_count` from `fights[0]` and graded all 54 fights against them (that pair takes four
different values across the selection). Use `C.consensus(parts, key)` to roll a per-fight
inference up while *reporting* disagreement; a check whose finding genuinely is not per-pull
sets `scope = "run"` (only `bar` does). Talent inferences that need the whole selection to
identify — the Eclipse charge count, the cooldown models — go through the `_RunLevel` mixin
and are surfaced in `params()`, which is the documented exception and covers
*configuration*, never a measurement. Peer checks subclass `C.PoolCheck`, which caps the
ranking-pool comparison at one pull so `-f raid` cannot fire hundreds of queries.

**When porting an idea from a third-party analyzer (WoWAnalyzer et al.), diff its thresholds
against the current simc APL before implementing them.** Those modules drift from the live
APL, and a threshold that is close-but-wrong is worse than no check. The Arcane divergences
found on 2026-09-05 — including one where WoWAnalyzer's own on-page explanation lists a
condition its grading code never implements — are tabulated in
[arcane-mage-12.1-ptr.md](../.claude/knowledge/classes/mage/arcane-mage-12.1-ptr.md). Note also
that a sim models only what it models: holding cooldowns for a real window can run the
player into a low-mana branch that a Patchwerk sim never enters, so run `mana` before reading
any spender check as a mistake.

The dataset builders in the same folder (`encounter_profile_sync.py`,
`plan_suggestion_sync.py`) are **not** checks: a check answers a question about one report;
they read a hundred strangers' pulls and write a reviewed dataset under `data/raid/`.

## reporting/ — the presentation layer for those payloads

React + Vite, one component per check `id`, built to a single self-contained IIFE that
`reporting/build_report.py` inlines into `reports/_checks_template.html` alongside the JSON.
Use it when a finding is being written up for a person; the text form stays the one to read
when analysing. See [reporting/README.md](reporting/README.md) — it records why the styles are
a JS string, why React is bundled, and which colour rules the charts follow (the `dataviz`
skill's validated ordinal ramp and reserved status palette).
