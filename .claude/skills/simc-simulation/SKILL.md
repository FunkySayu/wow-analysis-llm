---
name: simc-simulation
description: Build and run SimulationCraft (simc) locally from the vendored source in vendor/simc, so you can sim a profile directly instead of relying on a pre-made Raidbots link. Use whenever you need to run a simulation the user hasn't already generated on Raidbots — testing a hypothesis, checking a PTR build simc hasn't been packaged for yet, or reproducing/mutating a profile programmatically.
---

# Running SimulationCraft locally

`vendor/simc` is the upstream [SimulationCraft](https://github.com/simulationcraft/simc)
source, vendored as a **git submodule** rather than fetched ad hoc — this repo pins an
exact commit so a session's sim results are reproducible, and updating it is a deliberate
action, not something that happens silently underneath you.

Use this skill to get from "I need a number for profile X" to a built `simc.exe` and a
report. For the *syntax* of the profile string itself (character, gear, talents, action
list, sim options), see [[simc-profile-syntax]] — this skill only covers sync / build / run.

## When to reach for this vs. Raidbots

[[raidbots-reports]] pulls the JSON behind an *already-run* Raidbots report — no build step,
but you're limited to whatever profile and simc build Raidbots already ran. Reach for a
local build instead when:
- You need to sim a profile Raidbots hasn't run (a hypothetical, a manual edit, a batch of
  variants).
- You need to confirm whether simc itself has caught up to the current PTR build — see
  [[wow-ptr-research]] for why this matters before trusting any PTR number, local or hosted.
- You want the raw `action_sequence` / `stats` JSON for a *specific* run you control, rather
  than whatever the Raidbots link happened to configure.

## 1. Syncing vendor/simc

The submodule is pinned to a commit, like any other vendored dependency. It does **not**
update on a normal `git pull` of this repo. To move it forward:

```bash
cd vendor/simc
git fetch origin
git checkout midnight   # simc's default/live-dev branch; renamed across expansions, see below
cd ../..
git add vendor/simc
git commit -m "Update vendor/simc to <short-hash>"
```

`midnight` was `origin/HEAD` (the default branch) as of this writing — simc renames its
primary development branch to the current expansion's codename, so don't assume it stays
`midnight`. Check `git -C vendor/simc remote show origin | grep HEAD` or
`gh api repos/simulationcraft/simc --jq .default_branch` to get the current name rather than
hardcoding it. The running binary prints which build it came from on every invocation, e.g.
`SimulationCraft 1210-01 for World of Warcraft 12.1.0.69299 Live (... git build midnight
bb8107ca22)` — that `git build <branch>` tag is the fastest way to confirm what a given
`simc.exe` was actually built from.

After moving the pointer, **you must rebuild** (step 3) — the binary does not follow the
source automatically. If you only want the currently-pinned commit (the common case), skip
straight to step 2; `git submodule update --init` (already run once for you) is all that's
needed to have the source present.

Check what's currently pinned and whether it's built:
```bash
git -C vendor/simc log -1 --oneline
git -C vendor/simc rev-parse HEAD
```

## 2. Prerequisites (Windows)

- **Visual Studio 2022** with the "Desktop development with C++" workload (provides `cl.exe`
  / MSVC). Already present in this environment.
- **CMake** ≥ 3.10. Installed via `winget install Kitware.CMake` — if a fresh shell can't
  find `cmake`, it's on PATH at `C:\Program Files\CMake\bin` but a shell opened before the
  winget install won't have picked up the PATH change yet; use the full path or open a new
  shell.
- **Qt is NOT required.** simc's GUI (`SimulationCraft.exe`) needs Qt; the CLI (`simc.exe`)
  does not. Always configure with `-DBUILD_GUI=OFF` to skip that dependency entirely — this
  is also what upstream's own Linux CMake instructions recommend when you don't want to
  install Qt.

## 3. Building

CLI-only, Release, out-of-source build directory at `vendor/simc/build`:

```bash
export PATH="/c/Program Files/CMake/bin:$PATH"   # only needed if cmake isn't already on PATH
cmake -S vendor/simc -B vendor/simc/build -DBUILD_GUI=OFF -DBUILD_TESTING=OFF -G "Visual Studio 17 2022" -A x64
cmake --build vendor/simc/build --target simc --config Release -- -m
```

- `-G "Visual Studio 17 2022" -A x64` picks the MSVC toolchain already installed, generating
  an `.sln`/`.vcxproj` tree that `cmake --build` drives via MSBuild — no need to manually run
  `vcvars64.bat` first.
- `--target simc` builds only the CLI executable and the `engine` static lib it depends on,
  skipping tests and (since `BUILD_GUI=OFF`) the Qt GUI.
- `-- -m` passes `/m` (parallel compilation) through to MSBuild. The full engine is ~175
  `.cpp` files including large generated DBC (spell data) files — expect a first build to
  take a while; it is CPU-bound, not network-bound.
- The resulting binary lands at **`vendor/simc/build/Release/simc.exe`** (confirm with
  `find vendor/simc/build -iname simc.exe` if the CMake version/generator changes this).

**After bumping the submodule to a new commit, re-run both commands** — `cmake --build`
alone will pick up new/changed source files under the same configured build dir; you don't
need to delete `vendor/simc/build` and reconfigure unless `CMakeLists.txt` itself changed in
a way that breaks the cache (rare; if configure errors out, delete `vendor/simc/build` and
redo step 3 from the `cmake -S ... -B ...` line).

## 4. Running a sim

`simc.exe` takes any mix of `.simc` profile files and `key=value` option overrides as
positional arguments — see [[simc-profile-syntax]] for what goes inside a profile. Options
are parsed left to right; a later flag overrides an earlier one from a file.

```bash
vendor/simc/build/Release/simc.exe path/to/profile.simc iterations=1000 html=scratch/report.html json2=scratch/report.json
```

- With no `html=`/`json2=`, simc still prints a full **text report to stdout** — DPS mean,
  error bars, ability breakdown. That alone is often enough for a quick check.
- `html=<file>` writes the same interactive report Raidbots links point to (charts, buff
  uptimes, action-sequence-adjacent detail) — open it directly in a browser.
- `json2=<file>` writes the machine-readable report — same shape as the `data.json` pulled
  in [[raidbots-reports]] (`sim.players[].collected_data.dps.mean`,
  `collected_data.action_sequence`, `collected_data.stats`, etc.), so any parsing you've
  already built for Raidbots JSON works unmodified on a local run's output.
- `iterations=<n>` controls precision vs. runtime — a few thousand is typical for a stable
  mean; a few hundred is fine for a quick sanity check.
- Exit code `0` means success; nonzero codes are specific failure classes (invalid APL
  syntax, invalid talent string, unsupported spec, etc.) — a nonzero exit with no obvious
  console error means read the last few lines of stdout carefully, simc reports the cause
  there before exiting.

### Minimal example

```bash
vendor/simc/build/Release/simc.exe vendor/simc/profiles/MID1/MID1_Druid_Balance.simc iterations=100
```

runs one of simc's own bundled example profiles (a level-90 Balance Druid) for a quick
smoke test that the build works end to end.

### Ready-made profiles in this repo

Before writing a profile from scratch, check for one that was already validated against logs:

- `data/sims/12_1/spec_matrix/` — Fire, Frost, Feral, Arcane and Balance on real gear, with a
  scenario runner (targets, fight length, movement, add waves, vulnerability windows, scale
  factors). Its README has the commands and baseline numbers.
- `data/raid/<patch>/<tier>/<nn>_<boss>/sim/` — encounter fight scripts (Twin Fangs so far),
  each with its reference card under `.claude/knowledge/raid/`.

Building a new fight script from a log is its own method:
`.claude/knowledge/method/modelling-a-fight-in-simc.md` (and its table of simc traps that
return wrong data instead of an error).

## Local patches

`tools/simc/` holds two patches for simc bugs that silently misplace damage under distance
targeting and targeted `vulnerable`/`invulnerable` events. Stock simc is fine for Patchwerk and
`desired_targets` work; any fight script that positions enemies needs them. See
`tools/simc/README.md` for what each fixes and how to apply and verify them — and re-apply after
every submodule bump, before rebuilding.

## Common pitfalls

- **Forgetting to rebuild after moving the submodule pointer.** The binary is a snapshot;
  it has no idea the source moved.
- **Trusting a build without checking `ptr`/branch alignment.** If you're comparing against
  a PTR WarcraftLogs report, make sure vendor/simc is checked out to a branch/commit that
  actually targets that PTR build, and pass `ptr=1` in the profile/CLI — see
  [[wow-ptr-research]] for how to confirm simc has caught up to the specific PTR build in
  question before trusting the numbers.
- **`-DBUILD_GUI=ON` (the CMake default) dragging in a Qt requirement you don't need.**
  Always pass `-DBUILD_GUI=OFF` explicitly for CLI-only work.
- **Git Bash rewrites `raid_events+=/...` into a Windows path** ("Invalid raid event type
  'C:'"). `export MSYS_NO_PATHCONV=1`, or put sim options in a file rather than on the command
  line.
- **Never `2>&1` simc from PowerShell.** simc writes routine "Trivial:" notices to stderr, and
  Windows PowerShell turns each stderr line into an error record with a failure exit code.
  Run it from Git Bash, or don't redirect stderr (see
  `.claude/knowledge/method/building-reports.md`, toolchain traps).
- **Appending a UTF-8-with-BOM file to a profile injects a BOM mid-stream**, and simc silently
  skips the line it lands on (a whole profileset disappears). Write profile fragments as ASCII.
