# Spec sim profiles: Fire, Frost, Feral (+ Arcane, Balance references)

Built 2026-10-08 (simc 1210-01, 12.1.0.69299). Findings live in
`.claude/knowledge/classes/mage/{fire,frost}-mage-12.1.md`,
`.claude/knowledge/classes/druid/feral-druid-12.1.md` and
`.claude/knowledge/classes/dps-specs-boss-profile-12.1.md`; this file is how to run the profiles.
Build simc first (the `simc-simulation` skill).

A run is `base.simc` + an actor file + a talents file + a gear file, in that order, from this
directory:

```bash
SIMC=../../../../vendor/simc/build/Release/simc.exe
$SIMC base.simc fw_fire_field.simc          tal_fire_sunfury.simc        funkywand_gear.simc      # 178.2k
$SIMC base.simc fw_frost_spellslinger.simc  tal_frost_spellslinger.simc  funkywand_gear.simc      # 169.2k
$SIMC base.simc fw_frost_frostfire.simc     tal_frost_frostfire.simc     funkywand_gear.simc      # 154.5k (2T: 323k)
$SIMC base.simc fk_feral_wildstalker.simc   tal_feral_wildstalker.simc   funkitty_feral_gear.simc # 206.5k
$SIMC base.simc fw_arcane_ref.simc funkywand_gear.simc                                            # 199.5k (reference)
$SIMC base.simc ../../../raid/12_1/venomous_abyss/06_twinfangs/sim/funkitty_current.simc          # 199.2k (reference)
```

From Git Bash, `export MSYS_NO_PATHCONV=1` first if you pass any `raid_events+=/...` option
(`run.sh` already does).

| file | what |
|---|---|
| `base.simc` | Patchwerk 300s, ±20% length, the Twin Fangs script's raid-buff set. The three `midnight.crucible_*` lines are ignored (no actor wears that trinket). |
| `funkywand_gear.simc` | Funkywand, `HfGDg1K3bRzcqPkN` fight 6 (2026-09-30), ilvl 324.9, 4pc. Shared by every Mage spec. |
| `funkitty_feral_gear.simc` | Funkitty's armor from the Twin Fangs `funkitty_current.simc` + the Feral field's Bardiche and trinkets + Agility leg kit |
| `tal_*.simc` | field node-majority loadouts from the 2026-10-08 census of 120–140 top Mythic pulls per spec, as `class_/spec_/hero_talents=` entry ids. Each one was checked with `debug=1`. |
| `tal_feral_dotc.simc` | 9-pull Druid of the Claw majority, which is a single-target talent set |
| `tal_feral_dotc_aoe.simc` | Druid of the Claw hero picks on Wildstalker's class and spec tree: the fair hero-tree comparison |
| `fw_*.simc`, `fk_*.simc` | actor header + consumables (the field's modal flask per spec) |
| `scen.txt`, `scen_vuln.txt`, `scen_sw.txt`, `scen_hero.txt` | the scenario sets `run.sh` loops over |
| `run.sh` | `[SCEN=…] [ITER=…] ./run.sh <tag> <files…>` → `out/<tag>__<scenario>.json` (skips existing; `out/` is gitignored) |
| `parse.py` | every table in the knowledge files, plus `summary.json` (per-second timelines, gitignored) |
| `ps_feral_flask.simc` | profilesets: Feral flask comparison (the mastery disagreement) |

The census itself (gear, talents and damage per pull) and the script that turns it into
loadouts were not kept in the repository. To rebuild a talents file after a new census: take the
field's node-majority `class`/`spec`/`hero` entry ids, write them in the same form, and resolve
them with `debug=1` before trusting them. The apex is a tiered node with one entry per tier, and
all of them must be present.
