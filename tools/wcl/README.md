# WCL check toolkit

Reusable analyses over a WarcraftLogs report, so a question that has been answered
once never has to be re-derived. Every check is a function in `checks.py` exposed
through one CLI.

```bash
wsl.exe -d Ubuntu -e python3 tools/wcl/run.py <check> -r <REPORT> -a <ACTOR> [-f <fights>]
```

Windows note: the repo's `backend/` venv is a WSL venv and Windows `python` is only
the Store stub, so **run everything through `wsl.exe -d Ubuntu -e python3`** from the
repo root. The repo is mounted at the same relative path, so `tools/...` just works.

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
| `salvo` | Arcane Salvo spent per Barrage, share at max stacks, time overcapped |
| `soul` | is the Arcane Soul window being entered at max Salvo, or dumped into |
| `clearcasting` | how long Clearcasting sits capped at 3 and how many procs are lost |
| `tom-target` | how much of the Touch of the Magi window actually feeds the explosion |
| `cooldowns` | do Surge/ToM line up with Bloodlust and with the big/dangerous packs |
| `cd-usage` | raw cooldown efficiency: casts vs the theoretical maximum |
| `waves` | waves per Missiles channel — the empirical test for the Season 2 2-piece |
| `gaps` | dead time after a Missiles channel ends |
| `gear` | enchants/gems/secondaries for every player, as a control test |
| `all` | run every check in sequence |

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
```

## Reading two of them correctly

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

## Adding a check

1. Write `check_<name>(code, actor_id, fights)` in `checks.py` — print, don't return.
2. Register it in `CHECKS` in `run.py`.
3. Use `wclapi.events(...)` / `wclapi.table(...)` so it inherits caching, and put any
   new spell ID in `arcane.py` with a comment saying how it was confirmed.

Spell IDs that bite (all in `arcane.py`): Arcane Missiles is `5143` as a **cast** but
`7268` as **damage** — querying damage for 5143 silently returns nothing. Arcane Orb is
a wrapper (`153626`) whose damage lives on the child `153640`. Touch of the Magi is
`321507` to cast, `210824` as the enemy debuff, `210833` as the explosion.
