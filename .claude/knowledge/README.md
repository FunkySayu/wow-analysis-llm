# Knowledge base

Condensed, durable findings, by subject. Data the findings rest on lives under `data/`; the
tools that produce it under `tools/`. Each folder answers one kind of question:

| folder | what lives here | versioned by |
|---|---|---|
| [game/](game/) | how the game works regardless of spec: combat system, itemization, crafting | patch / season in the filename |
| [classes/](classes/) | one file per spec, plus the cross-spec comparison | patch in the filename |
| [raid/](raid/) | one folder per tier (`raid/<patch>/<tier>/`), one file per boss when a boss earns one | patch folder |
| [dungeons/](dungeons/) | the M+ pool for a season | patch folder |
| [method/](method/) | **how** to analyse, model and report — not data; read before the matching task | not versioned |

## game/

- [combat-system.md](game/combat-system.md) — GCD, off-GCD, casts vs channels, and why fight
  configuration decides which APL branches are reachable.
- The **itemization** set — read before any claim about gear, loot, upgrades or crafting,
  because gearing systems change on four clocks (expansion, season, scheduled unlock, hotfix)
  and earlier sessions got them wrong by reasoning from a remembered system:
  - [itemization-fundamentals.md](game/itemization-fundamentals.md) — patch-agnostic model,
    starting with the **stat budget**: ilvl sets a budget, the slot takes 1 / 0.75 / 0.5625 /
    0.5 of it, jewelry trades primary for ~3.6× secondaries, so the same crest buys 5× more
    primary on a caster weapon than on a wrist; then tracks, crests and weekly caps, the
    deterministic valves, slot logic, season arc, alts.
  - [itemization-midnight-s2.md](game/itemization-midnight-s2.md) — 12.1 numbers, calendar,
    acquisition table, **Nebulous Voidcore bonus rolls** (introduced 12.0.5, not 12.0, drawn
    without replacement per loot spec, and the decision that drives S2 priority), plus what
    3,200 top players actually wear.
  - [crafting-midnight-s2.md](game/crafting-midnight-s2.md) — sparks, crafted ilvl ladder,
    embellishments, orders.
  - [itemization-staying-current.md](game/itemization-staying-current.md) — sources and their
    traps, re-validation triggers, the WCL gear-census recipe.

  The S2 files carry a "valid as of" date and named re-check dates — honour them.

## classes/

One file per spec: the spec's resource engine, how to read its APL, the field's
build/gear/stats from ~130 top Mythic pulls, and a sim profile validated against logs
(Fire/Frost on Funkywand's gear, Feral on Funkitty's armor; run files in
`scratch/specs/sims/`).

- [druid/balance-druid-12.1.md](classes/druid/balance-druid-12.1.md)
- [druid/feral-druid-12.1.md](classes/druid/feral-druid-12.1.md)
- [mage/arcane-mage-12.1-ptr.md](classes/mage/arcane-mage-12.1-ptr.md) — also tabulates where
  WoWAnalyzer's thresholds diverge from the simc APL (2026-09-05).
- [mage/fire-mage-12.1.md](classes/mage/fire-mage-12.1.md)
- [mage/frost-mage-12.1.md](classes/mage/frost-mage-12.1.md)
- [dps-specs-boss-profile-12.1.md](classes/dps-specs-boss-profile-12.1.md) — the comparison
  layer: what makes each spec good or bad on a boss, damage-wise, measured on single target,
  2/3/5 targets, add waves, burst size and clock, fight length, execute, movement and
  vulnerability windows, against Arcane and Balance. Its key result is that **cooldown
  flexibility decides vulnerability capture, not burst size**: on Sszorak's Dig In, Balance
  converts 2.82× and Feral 0.99×, because a 2-minute Berserk cannot reach a window at 100s.
  Fire and Frost want **opposite** secondary stats (Fire: crit is worst; Frost: crit is best).

## raid/12_1/venomous_abyss/

- [venomous-abyss-12.1.md](raid/12_1/venomous_abyss/venomous-abyss-12.1.md) — the 12.1 raid
  tier: encounter list, per-boss measured damage shape, and where to source data for a tier
  this new.
- [venomous-abyss-mythic.md](raid/12_1/venomous_abyss/venomous-abyss-mythic.md) — measured
  from 667 top Balance Druid Mythic pulls: where progression actually reaches (the last two
  bosses have **no usable Mythic sample**), the composition the field brings per boss
  (Vashnik is the one boss it takes a fifth healer to; Nymrissa is a 25-player Lair fight),
  which phase transitions are scripted to 0.0s and which drift by 30s because they are
  HP-gated, the measured cadences, two corrections to the Heroic file's numbers, and the gap
  that matters most — **a cast-based timeline cannot show most of the damage**, because the
  top sources on five of seven bosses are applied auras that emit no cast event.
- [sszorak-mythic.md](raid/12_1/venomous_abyss/sszorak-mythic.md) — one boss measured end to
  end from 30 guilds' whole progression (ranks 250–750, 451 pulls): the log-vs-journal
  spell-id table, how the wind-pair collision is detected from two auras ending in the same
  server tick and validated on an axis the rule never uses, the anchor-bomb convention the
  whole field shares and why, and two findings that were wrong on the first pass. Read it
  before touching this encounter.
- [twin-fangs-sim-profile.md](raid/12_1/venomous_abyss/twin-fangs-sim-profile.md) — **the
  ready-to-run Twin Fangs Mythic profile** (fight script + Funkitty's current actor + the
  player's own Incarnation schedule): the one-line run command, what is and is not modelled,
  the gear corrections, validation bias, and reference deltas. Its key trap: on-use trinkets
  fire only inside Incarnation, so a trinket ranking is only as good as the cooldown schedule
  simmed.

## dungeons/12_1/

- [midnight-s2-dungeons.md](dungeons/12_1/midnight-s2-dungeons.md) — the Season 2 M+ pool:
  canonical dungeon list, per-dungeon Druid utility measured from 160 top-key logs, how to
  derive a debuff's dispel school from logs alone, and the spell-ID splits that make Typhoon
  and Solar Beam silently uncountable.

## method/

- [reading-an-apl.md](method/reading-an-apl.md) — APL syntax, structural gates, and the one
  rule: never infer a condition's direction from the ability name.
- [resource-economy.md](method/resource-economy.md) — reason about a kit as resources flowing
  between generators and spenders; resolve talents from data, and confirm a character's
  talents from empirical evidence rather than guessing.
- [analysing-a-pull.md](method/analysing-a-pull.md) — the ~10 independent axes a pull can
  fail on, in the order that stops one from masking another, and the techniques that did the
  work (decompose the metric into a rate and a magnitude; ratios against the player's own
  baseline to cancel gear; audit casts against the priority list's own gates rather than
  against outcomes; score cooldowns per instance, never in aggregate; separate the seconds
  the player did not control). **Read it before starting any new log analysis.**
- [modelling-a-fight-in-simc.md](method/modelling-a-fight-in-simc.md) — how to turn a
  scripted encounter into a simc fight script so an A/B question that needs forty pulls needs
  one sim run. Covers proving the exercise is worth it (pull-to-pull spread vs effect size),
  extracting spawn/despawn/death per enemy instance, finding the *real* damage window rather
  than the phase label, the two invisible mechanic classes (untargetability, found by
  splitting damage into direct vs tick; damage amps, measured two independent ways that must
  agree), the simc traps that return wrong data instead of an error, and why validation has
  to be per damage bucket rather than on the total. It also covers **cleave geometry**: who
  splashes onto whom, expressed with distance targeting. That path needs the vendored simc
  patch in `scratch/bdruid/twinfangs/`, because stock simc mis-places re-cast ground effects
  and cannot `target_if` across groups. Note also that `vulnerable,multiplier=` is the
  *increase*, not the factor. **Read it before modelling any new encounter.**
- [boss-death-timelines.md](method/boss-death-timelines.md) — how to build the "where should
  progression attention go" report for a boss: a timeline of the measured fight schedule over
  lanes of death clusters, ranked by killing blow. Covers the pipeline (stages 1-2 are generic
  tools, 3-5 still encounter-specific scripts to promote first), fourteen traps that return
  wrong or empty data, and the one that matters most: **a cast-based schedule cannot see the
  biggest killer**, because the top mechanics are applied auras with no cast event and must
  be measured from debuff applications. Also records two standing requests for the next one:
  full spell data on every hover card, and far less space spent on statistics. **Read it
  before building any boss death report.**
- [building-reports.md](method/building-reports.md) — how to build the published HTML report
  itself (payload injection, inline spell tooltips, clipboard, and the PowerShell/shell traps
  that silently corrupt a run).

## Adding a file

Put it in the folder for the question it answers, not the session that produced it. A boss
gets its own file under `raid/<patch>/<tier>/` once it has findings beyond the tier file; a
method doc stays in `method/` even when its worked example is one boss. Add a line here, and
link data by its `data/...` path rather than copying numbers that a regenerated dataset would
silently contradict.
