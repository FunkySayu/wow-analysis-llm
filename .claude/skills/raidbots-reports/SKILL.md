---
name: raidbots-reports
description: Pull the underlying simc JSON data behind a Raidbots simbot report (DPS distribution, per-ability stats, optimal action sequence) for a raidbots.com/simbot/report/<reportID> link. Use whenever the user wants to compare their actual play against a Raidbots simulation.
---

# Raidbots Report Analysis

Raidbots simbot report pages (`raidbots.com/simbot/report/<reportID>/...`) are a
JS single-page app — the HTML itself carries almost nothing. The actual
simulationcraft output is fetched by the page as JSON, and that JSON endpoint is
directly fetchable without a browser.

## Getting the report ID

From a link like `https://www.raidbots.com/simbot/report/38BorEbHSzMrsQmgug8J2B/simc`,
the report ID is `38BorEbHSzMrsQmgug8J2B`.

## The two endpoints

- `.../simbot/report/<id>/simc` — the SPA shell (~3KB of HTML). Only useful for
  opening in an actual browser; nothing to scrape here.
- `.../simbot/report/<id>/data.json` — **302 redirects** to
  `https://www.raidbots.com/reports/<id>/data.json`, which is the real simc
  `--json` output (hundreds of KB). Always follow redirects:

```bash
curl -sL "https://www.raidbots.com/simbot/report/<reportID>/data.json" -o data.json
```

(`-sL`/`--location` is required — a plain `curl` without following the redirect
returns an empty 302 response.)

## Structure of data.json

Top level is simc's native report format:

- `ptr_enabled` — `1` if this sim ran against PTR spell data. **Check this
  matches the context** (PTR vs live) before comparing numbers to a PTR
  WarcraftLogs parse.
- `build_date`, `git_revision` — which simc build produced this sim; relevant if
  cross-checking against [[wow-ptr-research]] for whether simc has caught up to
  the current PTR build.
- `simbot` — run metadata: `simcVersion`, `fightStyle`, `fightLength`,
  `enemyCount`, `totalIterations`, etc.
- `sim.players[]` — one entry per simmed actor:
  - `name`, `talents`, `gear`
  - `collected_data.dps` — `{sum, count, mean, min, max, median, std_dev, ...}`,
    the DPS distribution across iterations. Use `mean` as the benchmark number.
  - `collected_data.action_sequence` / `action_sequence_precombat` — the
    optimal ability-by-ability sequence simc found. This is the reference
    timeline to diff against a WarcraftLogs cast events export
    ([[warcraftlogs-reports]]) to see exactly where real play deviates from
    optimal.
  - `collected_data.stats` — per-ability damage/count breakdown, comparable to
    a WCL damage-done table.

## Example (verified)

```bash
curl -sL "https://www.raidbots.com/simbot/report/38BorEbHSzMrsQmgug8J2B/data.json" -o data.json
```

Returned `ptr_enabled: 1`, `build_date: "Aug 4 2026"`, player `"Funkywand"` with
`collected_data.dps.mean ≈ 161530`. Use this mean DPS as the ceiling to compare
a WarcraftLogs parse against.
