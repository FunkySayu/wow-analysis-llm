# Arcane Mage — 12.1 PTR Raidbots Report Extraction Notes

Source report: `38BorEbHSzMrsQmgug8J2B` (`https://www.raidbots.com/simbot/report/38BorEbHSzMrsQmgug8J2B/data.json`)
Full structured extract: [raidbots_38BorEbHSzMrsQmgug8J2B_extract.json](raidbots_38BorEbHSzMrsQmgug8J2B_extract.json)
Full talent tree reference (all nodes + PTR descriptions): [../data/talents/arcane_mage_12.1_ptr.json](../data/talents/arcane_mage_12.1_ptr.json)

## Sim identity
- `ptr_enabled: 1`, simc build `Aug 4 2026`, git `7a52c3106e` — this sim ran against PTR spell data, not live.
- WoW client `12.1.0.68914` (from the profile header comment), addon `SimC Addon 12.1.0-01`.
- Fight: single target ("patchwerk"), `desired_targets=1`, `max_time=300` (5 min, matches the in-game boss-dummy benchmark), `iterations=100000`.
- Result: mean DPS **≈161,530** (std_dev ≈8,721) — this is the ceiling number to compare a WarcraftLogs parse against.

## Talents

- **Hero tree: Sunfury.** Not stated directly anywhere in the JSON as a plain field — inferred from two independent signals: (1) the buff `arcane_soul` (spell 451038, Sunfury's signature capstone buff) has a real nonzero `start_count` (~3.67/fight) and nonzero uptime in `collected_data`; (2) the APL's main list only calls `action_list.sunfury` when `!talent.splintering_sorcery` (Splintering Sorcery is a Spellslinger-only hero node) — consistent results, both pointing to Sunfury.
- **Apex talent: Prismatic Bolt** (spellId 1295923 talent node / 1295924 damage spell). This is the 12.1 redesign of the old "Touch of the Archmage" capstone (icon string is a legacy leftover: `inv12_apextalent_mage_touchofthearchmage`). It's the 2nd-highest damage source in the sample (20.7% of total).
- **Talents confirmed present from live proc/gain data:**
  - Spellfire Spheres — buff `spellfire_sphere` (spell 448604) has real stack data throughout the rotation trace.
  - Energized Familiar (spell 452997) — nonzero mana-gain events attributed to it in `gains`.
  - Orb Mastery — referenced by an APL condition (`talent.orb_mastery`) that gates Arcane Orb priority; Arcane Orb is in fact cast in the sample (low damage share, consistent with a charge-generator role rather than a damage cooldown).
- **Gap, flagged rather than guessed:** the report only exposes the opaque Blizzard talent-loadout export string (`C4DAche08tHz49KSVf7iKFnyu...`), not a resolved per-node list. Decoding that string requires implementing Blizzard's bit-packed loadout format, which needs a JS/Python runtime to test safely against — **not available in this environment** (`node`/`python3` both absent). So exact point allocation for the remaining ~15 spec-tree nodes (e.g. the High Voltage vs. Charged Missiles choice — neither shows up in the tracked buff list, so it's genuinely undetermined here) is **not claimed**. The full talent tree with descriptions is saved separately for manual cross-reference against the string if needed.

## Action Priority List (APL)

Full raw simc profile (talents, gear, and complete APL text) is in the extract JSON under `apl.raw`. Structure:

1. **`actions.precombat`** — Arcane Intellect, variable setup (AoE threshold, trinket-type flags), snapshot_stats, Mirror Image, then a pre-pull Arcane Blast so the first real GCD lands with an Arcane Charge already up.
2. **`actions` (main list)** — Counterspell (interrupt) → racials/potion/trinkets gated to Arcane Surge + Touch of the Magi windows → `call_action_list,cooldowns` → branches to `spellslinger` or `sunfury` based on `talent.splintering_sorcery` (this character runs **sunfury**, see above).
3. **`actions.cooldowns`** — Arcane Orb (own cooldown line), Touch of the Magi (timed off the previous cast being Prismatic Bolt/Arcane Barrage plus Arcane Surge state), Arcane Surge itself, Evocation (mana dump below 10%, only outside cooldown windows), Presence of Mind (charge-stack refill utility).
4. **`actions.sunfury`** (active branch) — priority order: dump Clearcasting via Arcane Missiles while under the Arcane Salvo stack cap → Prismatic Bolt during the Arcane Soul window (or tier-set gate) → Arcane Barrage to dump 4 charges/high Salvo or during Arcane Soul → Prismatic Bolt (fallback) → Arcane Orb below 1 charge → Arcane Pulse in AoE → Arcane Blast as filler.
5. **`actions.spellslinger`** — present in the profile (simc ships both branches so the same file works for either hero-tree pick) but **not the branch actually executed** for this character.

## Sample damage rotation

`sim.players[0].collected_data.action_sequence` — a single representative iteration's cast-by-cast trace, 198 events over the 300s fight, each with timestamp, ability, target, mana%, and the full active-buff/stack list at that moment (Arcane Charges, Arcane Salvo stacks, Clearcasting, etc.). Saved in full under `sampleRotation` in the extract JSON. This is the reference timeline to diff a real WarcraftLogs cast export against (see the `warcraftlogs-reports` skill for pulling that).

## Damage breakdown (this sample, sorted by % of total)

| Ability | % of total dmg | Notes |
|---|---|---|
| Arcane Missiles | 34.9% | Clearcasting dump, talent |
| Arcane Barrage | 23.5% | Charge-spender, baseline |
| Prismatic Bolt | 20.7% | Apex talent proc |
| Arcane Blast | 7.5% | Baseline filler/charge builder |
| Touch of the Magi | 6.2% | Talent, damage-amp burst window |
| Meteorite | 5.6% | **Gear/embellishment proc, not a spec ability** |
| Arcane Assault | 0.6% | Sub-bolt component of Arcane Barrage per charge |
| Arcane Surge | 0.6% | Talent, cooldown |
| Rune of Unleashed Fire | 0.3% | **Weapon enchant proc, not a spec ability** |
| Arcane Orb | 0.06% | Talent, charge generator |
| Mirror Image | 0.01% | Talent, precombat opener |

(Arcane Intellect, potion/flask/food procs, and Void-Touched/Silvermoon Parade contribute 0% direct damage in this sample — consumable/buff-only.)

## Spell-coverage verification

Every ability that either appears as a real action token in the APL or is actually cast in the sample rotation now has a PTR-accurate plain-text description available (134 spellIds total: 128 from the talent tree dump + 6 baseline/gear ones fetched separately — Arcane Blast, Arcane Barrage, Arcane Assault, Arcane Intellect, Counterspell, Meteorite, Rune of Unleashed Fire). The only unresolved item is the exact spec-tree point allocation noted above as a gap, not a missing description.
