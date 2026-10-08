# tools/simc/ — local patches to the vendored SimulationCraft

`vendor/simc` is a pinned submodule. These patches fix simc bugs that **return wrong data
rather than an error**, found while modelling encounters
(`.claude/knowledge/method/modelling-a-fight-in-simc.md`, traps table). Stock simc is fine for
Patchwerk and `desired_targets` sims; apply these before running any fight script that uses
distance targeting or targeted vulnerability windows (the Twin Fangs profile in
`data/raid/12_1/venomous_abyss/06_twinfangs/sim/` needs them).

| patch | files | fixes |
|---|---|---|
| `distance_targeting.patch` | `engine/action/action.cpp`, `engine/player/ground_aoe.cpp`, `engine/class_modules/sc_druid.cpp` | a re-cast ground effect (Fury of Elune, Efflorescence) kept the first cast's coordinates; `target_if` under distance targeting only saw targets in the previous spell's splash, so an AoE spell could never retarget onto a separate group |
| `vulnerable_runtime_target.patch` | `engine/sim/raid_event.cpp` | `vulnerable`/`invulnerable` raid events with `target=` resolved the name before raid-event adds existed and, on a miss, **applied to the boss instead** |

Apply, then rebuild (the binary does not follow the source):

```bash
git -C vendor/simc apply ../../tools/simc/distance_targeting.patch ../../tools/simc/vulnerable_runtime_target.patch
cmake --build vendor/simc/build --target simc --config Release -- -m
```

Check what a working tree carries with
`git -C vendor/simc apply -R --check ../../tools/simc/*.patch` (succeeds when both are applied).
After bumping the submodule, re-apply and rebuild; if a patch no longer applies, check whether
upstream fixed the bug before porting it.
