# Twin Fangs (Mythic) — simc fight script and reference actor

The reference card — what each file models, the gear corrections, validation, reference
deltas — is `.claude/knowledge/raid/12_1/venomous_abyss/twin-fangs-sim-profile.md`. This
folder is the runnable part.

Needs a simc built **with the patches in `tools/simc/`** applied (see its README and the
`simc-simulation` skill): stock simc mis-places re-cast ground effects and cannot `target_if`
across groups, so FoE and Starfire land on the wrong enemies.

From this directory (later files override earlier ones):

```
../../../../../../vendor/simc/build/Release/simc.exe twinfangs.simc funkitty_current.simc apl_plan.simc \
    iterations=10000 threads=16 json2=out.json html=out.html
```

| file | what |
|---|---|
| `twinfangs.simc` | the fight: 402s, both bosses, 5 Spawn waves, raid buffs, boss amp |
| `twinfangs_ref.simc` | one real pull (Shidann, `vP4RTacqbCNzd9JV` fight 9), for validation only |
| `twinfangs_p10.simc` / `twinfangs_p90.simc` | short / long Spawn lifetimes, for robustness |
| `funkitty_current.simc` | the actor, 2026-10-07 export with every gear correction |
| `field_loadout.json` | modal talents of 199 top Twin Fangs Balance parses (the actor uses them) |
| `apl_plan.simc` | default Balance APL + the wave routine + the player's Incarnation schedule |
| `apl_B.simc` | the same with the APL's own Incarnation schedule (the comparison that shows why the schedule matters) |

The fight files were generated from 30 measured kills by a script that stayed in the working
area; regenerate them by hand from the measured clock in
`.claude/knowledge/raid/12_1/venomous_abyss/venomous-abyss-mythic.md` if the encounter is retuned.
