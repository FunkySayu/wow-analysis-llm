# Midnight Season 2 M+ — Balance Druid utility view

Season opened 2026-08-18; this analysis dated 2026-08-21 (3 days in). Artifact:
"Moonkin Utility Book". Working data in `scratch/s2dungeons/` (see "Pipeline" below).

## Canonical dungeon pool

**WCL `worldData` zone 55 = "Mythic+ Season 2"** (expansion 7, Midnight). Eight encounters:

| Encounter ID | Dungeon |
|---|---|
| 12993 | Altar of Fangs *(new in 12.1)* |
| 12825 | Den of Nalorakk |
| 61762 | Kings' Rest *(BfA)* |
| 12813 | Murder Row |
| 112521 | Ruby Life Pools *(Dragonflight)* |
| 61877 | Temple of Sethraliss *(BfA)* |
| 12859 | The Blinding Vale |
| 12923 | Voidscar Arena |

Season 1 (zone 47) is fully retired. The SEO/boost sites happened to have this list right,
but they were only trusted *after* zone 55 confirmed it — keep that order of operations.

## The measurement traps in this data set

These cost real time and all fail silently.

1. **Typhoon's cast is logged as spell `61391`, not the tooltip's `132469`.** Filtering casts
   on 132469 returns **zero casts in every run**, while Typhoon interrupts plainly exist in
   the same logs. The contradiction is the tell. Solar Beam has the same split: the cast is
   `78675`, the interrupt/silence effect is `97547`.
2. **Solar Beam's AoE is invisible to interrupt logs.** Across 1,764 beams, **not one**
   produced a second interrupt event — the interrupt fires on the primary target only and
   the area component is a *silence*, which prevents casts from starting and writes nothing.
   Any "interrupts landed" comparison is structurally biased against the beam. Measure it by
   counting distinct enemies mid-cast inside the beam's own 8s window instead.
3. **Shapeshifts appear in the dispel table.** Breaking a root by shifting is logged as a
   dispel whose "dispel spell" is `Moonkin Form` / `Bear Form` / `Cat Form` / `Travel Form`.
   This is how shapeshift usage becomes *measurable* rather than theoretical. Tooltip
   confirms the mechanic is baseline on all four forms: "The act of shapeshifting frees you
   from movement impairing effects."
4. **WCL's Casts *table* truncates to the top 5 abilities per player.** Utility spells never
   appear. Use `events(dataType: Casts, filterExpression: "source.class = \"Druid\" and
   ability.id in (...)")` instead.
5. **`table(dataType: Dispels)` nests one level deeper than it looks**: the rows are at
   `data.entries[0].entries`, not `data.entries`.
6. **PowerShell 5.1 `ConvertFrom-Json` does not enumerate when piped.** `Get-Content x |
   ConvertFrom-Json | Sort-Object t` passes the *whole array* as one object; the result is a
   1-element jagged array. Assign first, then sort. Also: `Invoke-WebRequest` needs
   `-UseBasicParsing` or it blocks in non-interactive mode.

## Deriving dispel type without a database

No public source exposes a reliable dispel school for these debuffs. Instead, collect every
dispel of a debuff across the sample and **intersect the capability sets** of the spells
observed removing it (`Remove Corruption` = {Curse, Poison}, `Purify Spirit` = {Magic,
Curse}, `Cleanse Toxins` = {Poison, Disease}, …). Where the intersection is a single school,
that is the school. This resolved all but two abilities in the pool.

Gotchas in that map: `Dispel Magic` and `Mass Dispel` also purge *enemy* magic, and
`Tranquilizing Shot` removes Enrage **or** enemy magic — mis-specifying either produces
spurious empty intersections.

## Findings (160 runs, 20 per dungeon, keys 13–16)

**Druid-only work per run** = Curse/Poison dispels + enrages soothed + roots shapeshifted out
of. This is the ranking that matters, because these are the actions with no substitute.

| Dungeon | Druid-only/run | Rem.Corr | Soothe | Shift | Casters per beam |
|---|---|---|---|---|---|
| Den of Nalorakk | **19.4** | 10.6 | 6.2 | 4.4 | 1.94 |
| Voidscar Arena | 11.6 | 7.0 | 4.4 | 1.2 | 1.51 |
| Murder Row | 9.6 | 7.9 | 4.2 | 0 | **3.33** |
| Altar of Fangs | 8.8 | 5.6 | 3.4 | 1.2 | 2.37 |
| The Blinding Vale | 8.4 | 2.6 | 0.4 | **6.4** | 1.98 |
| Temple of Sethraliss | 6.7 | 7.8 | 0.2 | 0.4 | 1.76 |
| Kings' Rest | 4.4 | 2.3 | 4.0 | 0 | 1.40 |
| **Ruby Life Pools** | **0.2** | **0** | 0.1 | 0.2 | 1.53 |

- **Ruby Life Pools is the floor and it is not close** — zero poison, zero curse, no enrage,
  no shapeshift-breakable root. Every dispel in the dungeon is Magic or an enemy buff.
  Balance brings interrupts and damage there and nothing else.
- **Den of Nalorakk is the ceiling.** `Mother's Wrath` (1238053) is the season's best Soothe:
  a **stacking** +50% damage / +50% speed enrage on Territorial Matriarch, soothed 5×/run.
  `Glacial Tomb` (1241464) is 92% shapeshift-cleared.
- **The Blinding Vale is the shapeshift dungeon.** `Bloodthorn Roots` (1259365) roots "until
  destroyed" — shifting is one global instead of killing it. 127 clears in 20 runs.
- **Murder Row is the beam dungeon** — 3.33 casters in front of each beam, peaking at a
  16-caster Wild Imp / Unleashed Imp `Felfire Burst` window. But **66% of beams there are
  contested**: the packs are wider than one beam, which is why Typhoon (5.8/run) does more
  visible work than the beam does.

**Beam composition, whole sample:** 41% suppressed (casters active before, silent after),
55% contested, only **4% empty**. Beam *discipline* is not the problem; beam *placement*
against spread packs is.

**Stampeding Roar is a routing tool**, not a combat one — most casts land between pulls
(68% in Kings' Rest, 66% in Murder Row). Only ~25% of beams are cast during a boss; in
Voidscar Arena it is 0% across twenty runs.

## Pipeline

`scratch/s2dungeons/` — run in this order:
1. `pull_deep.ps1` — rankings sorted by **keystone level** (not DPS), then one batched query
   per run: masterData actors, `fights{dungeonPulls}`, filtered druid casts, dispel events,
   interrupt events, playerDetails. 160 runs ≈ 1,000 rate-limit points of 3,600/hr.
2. `analyse_deep.ps1` → `deep_casts/dispels/interrupts/runs.csv`, mapping every cast to its
   `dungeonPull` and target NPC.
3. `beam_coverage.ps1` / `beam_prepost.ps1` — enemy `begincast` events filtered to the
   interruptible-spell set, windowed ±8s around each beam.
4. `build_payload.ps1` → tooltips + base64 icons; `make_data.ps1` → `payload_data.json`;
   `build_report.ps1` → `reports/s2_druid_utility.html` with validation.

`dungeonPulls` is coarser than a pack — WCL groups consecutive trash into one segment named
after a representative NPC. Good for boss-vs-trash and rough sectioning, not for "which pack".

## Racials (added 2026-08-21)

**Dwarf cannot be a Druid.** The class is open to Highmountain Tauren, Kul Tiran, Night Elf,
Tauren, Troll, Worgen, Zandalari Troll, and **Haranir** (new in Midnight). Confirmed two ways:
warcraft.wiki.gg's race list, and **zero Stoneform casts by any druid across all 160 runs**.
Haranir's racials are throughput/flavour — *Lash Out* (+1% crit damage/healing), *Thorn Bloom*
(3-min area damage+heal), plus travel and gathering passives — so **Night Elf is still the only
druid race whose racial changes how a pack is played**.

Only three racials were cast by druids at all: Shadowmeld (237 casts / 110 runs),
Berserking (109 / 14 runs, a throughput cooldown), War Stomp (4 / 2 runs).

### Shadowmeld, measured
- Present in **110 of 160 runs** — a *floor* on Night Elf share, since a Night Elf who never
  pressed it is invisible. 2.2 casts per run.
- **97% pressed inside a pull**, only 14% during a boss. It is a combat button here, not a
  skip tool — the "meld to skip a patrol" use barely appears in timed high keys.
- **76% pressed while something was already hitting the druid**; of those, the damage stopped
  entirely 45% of the time.
- **What it answers vs. what it cannot** is the sharp result. Targeted attacks die when you
  leave the target list: Melee 78% stopped, Feast of Misery 100%, Void Beam 100%, Lightning
  Torrent 100%, Lightmaw Beams 90%, Flay 75%. Untargeted ground effects are unaffected:
  Thunderous Stomp **0%**, Heavy Slams **0%**. Shadowmeld removes you from a target list, not
  from a puddle.
- Most anticipatory dungeon: Kings' Rest (40% of melds pressed with nothing yet hitting).
  Least: Murder Row (9%) — there it is a reaction to imp fire already in the air.

### Two more traps found here
7. **`dataType: DamageTaken` silently returns zero events when filtered by `targetID`** (or by
   `filterExpression: target.id = N`), even though the actor plainly appears in the unfiltered
   result. Query a time window unfiltered and filter client-side.
8. **PowerShell variables are case-insensitive.** A `$W` window constant and a `$w` events
   array are the *same variable*; the collision silently inverted the Shadowmeld headline
   (reported 81% "idle" when the true figure is 76% under fire) before it was caught. Any
   single-letter loop/constant name in these scripts is a hazard.
