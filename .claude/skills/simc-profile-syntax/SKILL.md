---
name: simc-profile-syntax
description: Reference for the SimulationCraft "simc string" / Textual Configuration Interface (TCI) — how to write or edit a .simc profile (character, gear, talents, consumables, sim-wide options) and CLI flags, sourced from simc's own wiki. Use whenever writing, editing, or reading a .simc profile file, or constructing simc CLI option overrides, rather than just reading an already-written APL.
---

# The simc string (Textual Configuration Interface)

Everything simc accepts — a `.simc` profile file, command-line arguments, and the GUI's
"overrides" tab — is the same underlying language: a flat sequence of `key=value` lines,
parsed **top to bottom, left to right**. This is why a CLI invocation like
`simc.exe profile.simc iterations=100` works: the file's lines and the trailing CLI args are
just concatenated into one stream before parsing.

This skill covers *writing/editing a profile*: character declaration, gear, talents,
consumables, and sim-wide options. For *reading an action priority list* (the rotation
logic itself) and the trap of misreading a condition's direction, see
`.claude/knowledge/method/reading-an-apl.md` — that content isn't repeated here. To actually
build and run simc against a profile, see [[simc-simulation]]. For raid events, enemies,
distance targeting and the options that fail silently when scripting an encounter
(`raid_events` with `last == first`, `fight_style` resetting raid events,
`vulnerable,multiplier=` being the *increase*, `bloodlust_time=` without the override), see
the traps table in `.claude/knowledge/method/modelling-a-fight-in-simc.md`.

Talent overrides (`class_talents=` etc.) **enforce no game rules** — choice nodes, point
gates, connectivity and hero-tree membership are all unchecked, and the result is a plausible
wrong number. The four ways it fails, with measured examples, are in
`.claude/knowledge/classes/druid/balance-druid-12.1.md` ("simc talent overrides enforce NO game
rules"); resolve any loadout with `debug=1` before trusting it.

Source of truth for everything below: the [simc wiki](https://github.com/simulationcraft/simc/wiki)
(`TextualConfigurationInterface`, `Characters`, `Equipment`, `Options`, `Output`,
`ActionLists`, `TargetOptions` pages) — check there directly if something below seems stale,
since these pages are community-maintained and simc adds options frequently.

## Parsing rules

- **Comments**: `# ...` to end of line.
- **Scopes matter**: an option is *global* (position in file irrelevant), *current character*
  (applies to whichever character was declared most recently), or *ulterior characters*
  (applies only to characters declared *after* this line). Example: `ptr=1` is ulterior-scope
  — set it *before* declaring the character you want simmed on PTR, or it won't apply.
- **Multiline / sequences**: long options (`actions`, `raid_events`) are split with `+=`, and
  individual entries within them with `/`:
  ```
  actions=fireball
  actions+=/fire_blast
  ```
- **Templates**: `$(name)=content` defines a reusable snippet, referenced later as `$(name)`
  — useful for a condition reused across many action lines.
- **Includes**: a bare filename, or `input=<file>`, splices another `.simc` file in at that
  point. `path=` controls the search directories.
- **Whitespace terminates a token** unless wrapped in `"..."` (needed for names with spaces,
  e.g. `enemy="Fluffy Pillow"`).

## Declaring a character

```
druid="Funkywand"
source=default
spec=balance
level=80
race=night_elf
timeofday=night
role=spell
position=back
```

- The class keyword itself (`druid=`, `warrior=`, `mage=`, ...) both creates the character
  and sets its display name — this is the "current character" for every scoped option that
  follows.
- `copy=<new_name>[,<source_name>]` clones the current (or named) character — handy for an
  A/B profile diff without retyping gear.
- `active=<name>|owner|none` switches which character subsequent lines apply to — needed
  after declaring a pet, to switch back to the owner (`active=owner`) before continuing to
  configure the player.
- Import instead of hand-writing: `armory=<region>,<server>,<name>`,
  `wowhead=<id>` or `wowhead=<region>,<server>,<name>`, or `local_json=<file>,spec=...,equipment=...`
  for an offline armory-export JSON. Overrides after an import line patch the imported
  profile (e.g. `gear_strength=20000` after `armory=...`).

### Talents

```
class_talents=19979:1/20024:1/shadowfiend:1
spec_talents=mind_flay:1/vampiric_touch:1/devouring_plague:1
hero_talents=keeper_of_the_grove          # tokenized hero-tree name enables the whole tree
```

- `talents=<hash>` accepts the single Blizzard export string (from in-game or the SimC
  addon) — this is what you'll see in most Raidbots-sourced profiles.
- To hand-edit individual talents, use the three tree-specific options above instead:
  `/`-delimited `talent:rank` pairs, tokenized-name or numeric ID (numeric ID is
  **required** when a talent name collides with another in the same tree).

### Consumables

```
flask=magisters_2
food=harandar_celebration
potion=lights_potential_2
augmentation=void_touched
temporary_enchant=main_hand:thalassian_phoenix_oil_2
```

Set any of these to `disabled` to turn it off entirely. `temporary_enchant` supports an
`if=` suboption (player-scope expression, evaluated once at actor init — not a live
mid-fight condition) when multiple candidate enchants are listed for the same slot.

### Gear

```
<slot>=<item_name>,id=<item_id>,bonus_id=<id>/<id>/...,ilevel=<n>,gem_id=<id>,enchant_id=<id>,crafted_stats=<a>/<b>
```

- Slots: `head neck shoulder back chest wrist hand waist legs feet finger1 finger2 trinket1
  trinket2 main_hand off_hand ranged tabard meta_gem`.
- Give `id=` and simc queries the rest from its item database; `bonus_id=` layers on the
  specific roll (tertiary stats, item-level upgrade track, etc — the same bonus IDs
  WarcraftLogs/Raidbots gear strings use). Manually-specified `stats=` (e.g. `500sta_250str`)
  overrides anything queried via `id`.
- `gems=`, `enchant=` accept either a recognized keyword (`landslide`,
  `power_torrent`) or a raw stat string in the same `<value><stat>` syntax as `stats=`.
- `weapon=<type>_<speed>speed_<min>min_<max>max` (or `_<dps>dps` / `_<dmg>dmg` instead of
  min/max) defines weapon damage on `main_hand`/`off_hand`/`ranged`.

A full real example is any file under `vendor/simc/profiles/**/*.simc` — e.g.
`vendor/simc/profiles/MID1/MID1_Druid_Balance.simc` has a complete character block, gear
list, and APL together, and is a good template to copy from.

Gear facts that `id=` lookups get wrong, each found by comparing simc's stat sheet against a
log (details and the full list in
`.claude/knowledge/raid/12_1/venomous_abyss/twin-fangs-sim-profile.md`, "The actor"):

- **Upgrade track and rank are bonus ids** (Myth 1–6/6 = 12849–12854, Hero 1–6/6 =
  12841–12846). A wrong one does not fail; it sims a different item level.
- **Crafted stat pairs are bonus ids** (8790–8795) and override `crafted_stats=`, which is then
  ignored. To sim a recraft, swap the bonus id.
- Some items carry stats simc resolves wrongly (12.1: the Aqirbane Reliquary neck gets all its
  secondary rating as crit) — override with `stats=`.
- An item or enchant with no simc handler sims as nothing at all (12.1: Rite of the Hash'ey).
  Model it as measured constant stats and say so.

## Sim-wide options (not character-scoped)

These configure the simulation itself, and typically go at the top of a file or as trailing
CLI args:

| Option | Purpose |
|---|---|
| `iterations=<n>` | How many times to run the fight. More = tighter error bars, slower. |
| `max_time=<seconds>` | Target average fight length (default 300). |
| `fight_style=<style>` | `Patchwerk` (pure single-target tank-and-spank, the default-ish baseline), `CastingPatchwerk`, `HecticAddCleave`, `DungeonSlice`, `DungeonRoute`, `CleaveAdd`, `LightMovement`, `HeavyMovement`, `Beastlord`, `HelterSkelter`, `Ultraxion` — changes what raid events/adds/movement are injected, which in turn changes which APL branches are even reachable (an AoE line is "dead" under `Patchwerk` but live under `CleaveAdd`). |
| `desired_targets=<n>` | Simple AoE target count, when you don't need a full `fight_style`/`enemy=` setup. |
| `enemy=<name>` (repeated) | Declare additional enemies explicitly, for AoE or add-phase modeling with per-enemy control (`enemy_health=`, `enemy_fixed_health_percentage=`, etc — see the wiki's `TargetOptions` page). |
| `ptr=1` | Target PTR spell data instead of live. **Ulterior scope** — set before declaring the character. Cross-check with [[wow-ptr-research]] whether simc's data has actually caught up to the PTR build you care about before trusting this. |
| `optimal_raid=1` | Assume a full raid buff/debuff set is present without needing to simulate other players. |
| `single_actor_batch=1` | Sim each actor independently against a clean target rather than together — standard for isolated DPS-ranking sims. |
| `target_error=<pct>` | Instead of a fixed iteration count, run until the DPS error margin is below this — trades a predictable iteration count for a precision guarantee. |

## Getting output

Covered fully in [[simc-simulation]]; option summary:

- No flags → full text report to stdout (DPS mean/error, ability breakdown).
- `html=<file>` → interactive HTML report (same shape as what a Raidbots link shows).
- `json2=<file>` → machine-readable JSON (`json=` also exists but is deprecated — use
  `json2`). Same top-level shape documented in [[raidbots-reports]]
  (`sim.players[].collected_data.dps.mean`, `.collected_data.action_sequence`,
  `.collected_data.stats`), since Raidbots is itself just hosting this same JSON.
- `save=<file>` / `save_gear=<file>` / `save_talents=<file>` / `save_actions=<file>` →
  export the (possibly armory-imported, then hand-edited) resolved profile back out as
  `.simc` text — useful for turning an armory import into a durable, diffable file.

Profilesets (many variants in one run) fail silently in two ways: a name containing `.` is
dropped with only a "Trivial" warning, and when the profile declares `enemy=` actors the
variants edit **actor 0** (an enemy) unless `profileset_main_actor_index=` points at the
player. Count results against variants sent.

Exit code `0` = success. Nonzero codes are specific failure classes (invalid APL: `30`,
invalid talent string: `81`, invalid item string: `82`, unsupported spec: `72`, ...) — check
the tail of stdout for the actual error message before digging further.
