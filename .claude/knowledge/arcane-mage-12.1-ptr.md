# Arcane Mage — 12.1 PTR, Sunfury single-target

Sources: Raidbots report `38BorEbHSzMrsQmgug8J2B` (sim), WarcraftLogs `vAtQGNpDqJHyw9mn`
(actual play, character "Funkywand"), talent tree dump
[data/talents/arcane_mage_12.1_ptr.json](../../data/talents/arcane_mage_12.1_ptr.json).

**Sim and log are the same character on the same gear** — head/shoulder/chest/hands/legs
(271564/271562/271567/271565/271563), both trinkets (250215, 270164) and weapon (258047)
match between the simc profile and the logged `CombatantInfo`. So 161,530 DPS is a valid
benchmark for this character, not a generic one.

## Build — now fully resolved (no longer a gap)

The previous note flagged the talent allocation as unresolvable from the opaque loadout
string. **It is resolvable**: WCL's `events(dataType: CombatantInfo)` returns a
`talentTree` array of `{nodeID, id, rank}` that maps 1:1 onto the `id`/`entries[].id` pairs
in the Raidbots talent dump. Confirmed: **Sunfury, all 14 hero nodes**, apex **Prismatic
Bolt** (all 3 ranks), and the spec picks that drive the rotation — Arcane Salvo, Spellfire
Salvo, Arcane Singularity 2/2, Intuition, Focusing Crystal, High Voltage, Amplification,
Overpowered Missiles, Orb Barrage, Charged Orb, Expanded Mind, Impetus, Eureka, Improved
Clearcasting, Concentrated Power, Prodigious Savant 2/2. Gear carries **5 pieces of setID
2060** → 4pc active, which is what arms the `cumulative_power` gate in the APL.

## The actual engine: Arcane Salvo, cap 25

Salvo caps at **25** (20 from base Arcane Salvo's "3%, up to 60%", +5 from **Spellfire
Salvo**). Verified empirically — `maxStack=25` on buff 1242974 in every logged fight.

Generation is *not* spread evenly across the kit (the earlier note said "nearly every cast
builds Salvo" — misleading). In practice:

| Source | Salvo per cast |
|---|---|
| **Arcane Missiles** | ~11–15 (7 waves w/ Amplification, ×1.5 from Focusing Crystal's 50%/wave) |
| **Overpowered Missiles** proc | **straight to 25** ("generates maximum stacks") |
| Prismatic Bolt | +4 (Expanded Mind) |
| Arcane Blast | +2 (Expanded Mind) |
| Arcane Orb | +1 |

So **Arcane Missiles is the generator**; Blast/Prismatic Bolt are the fine-tuning top-off
that bridges ~21 → 25. Missiles is also the main *Arcane Charge* generator (High Voltage,
50%/wave ≈ 3.5 charges/channel), not Arcane Blast.

**Arcane Barrage is the only spender, and it pays out four ways at once:**
1. Salvo damage bonus (3%/stack, linear in stacks consumed)
2. **Prismatic Bolt: 2% per stack consumed** (1% base + 1% from the third apex node) → 50%
   at 25 stacks. Corrects the earlier note's "~1%".
3. **Glorious Incandescence: 1 Meteorite per 5 stacks consumed** (linear)
4. **Orb Barrage: 4% per stack *held*** → guaranteed free Arcane Orb at 25

Three of those four are **linear in stacks consumed**, so dumping early is *not* a
proportional loss. The one genuinely non-linear payoff is **Intuition: +25% Barrage damage
only on reaching max stacks.** That plus the fixed per-cast GCD cost is the entire argument
for holding to 25.

## Why the APL looks the way it does

```
actions.sunfury=arcane_missiles,if=buff.clearcasting.react&buff.arcane_salvo.stack<12,chain=1
actions.sunfury+=/prismatic_bolt,if=((!set_bonus.midnight_season_2_4pc)|buff.cumulative_power.stack=8)&buff.arcane_soul.down
actions.sunfury+=/arcane_barrage,if=(buff.arcane_charge.stack=4&((...|buff.clearcasting.react)&buff.arcane_salvo.react>=12)|((buff.arcane_surge.remains>gcd.max|buff.arcane_surge.down)&buff.arcane_salvo.react=25))|buff.arcane_soul.up
actions.sunfury+=/prismatic_bolt
actions.sunfury+=/arcane_orb,if=buff.arcane_charge.stack<1
actions.sunfury+=/arcane_pulse,if=...
actions.sunfury+=/arcane_blast
```

- The **`arcane_salvo.stack<12` gate on Missiles** exists because a channel adds ~11–15;
  starting one above 12 overflows the 25 cap.
- Barrage therefore has two legal triggers: **Salvo=25** (the Intuition path), or
  **Salvo≥12 with Clearcasting banked** (a release valve — Clearcasting is unusable while
  Salvo≥12 blocks Missiles, so you dump to unblock it).
- **Arcane Orb is gated to `arcane_charge.stack<1`** — it is a charge fallback, not a
  damage cooldown. The sim hard-casts it ~1×/300s; Orb Barrage supplies ~48 free orbs.
- **Prismatic Bolt is held to Cumulative Power 8/8** under the 4pc. Holding the proc ~3s is
  correct, not a mistake — it replaces your next Arcane Blast and does not expire.
- **Arcane Soul** (Memory of Al'ar, 4s, lands a fixed **17.4s after Arcane Surge**): Barrage
  grants +5 Salvo and **does not consume**, so every Barrage in the window fires at whatever
  Salvo you brought in. Entering at 25 vs 0 is the whole value of the window.

## Reading the gap between sim and play (the useful metric)

Comparing raw cast counts is a dead end — the player out-casts the sim (210 vs 198 GCDs,
~0.12s median delay after a channel). The metric that separates them is **Salvo per
Barrage**:

| | Sim | Logged play (5×300s) |
|---|---|---|
| non-Soul Barrages / 300s | 48 | 58 |
| avg Salvo consumed per Barrage | 22.4 | 19.7 |
| Barrages with **Intuition** up | **65%** | **46%** |
| Arcane Blast / 300s | 31 | 21 |
| Arcane Orb hard casts / 300s | 1 | 8 |

Same total Salvo throughput, spread over ~10 more Barrage GCDs. The sim spends those GCDs
on Arcane Blast to bridge 21→25; the player spends them on extra Barrages and Arcane Orbs.

**Correction to the earlier note**, which claimed the costliest mistake is a *missed or
late* Barrage. In the logged data the dominant error is the opposite — Barrage fired **too
early**, below max Salvo. Overcapping does happen too (Salvo sits at 25 ~22s/fight, and 18%
of Missiles casts start above the `<12` gate), so the real failure mode is *cycle timing*,
not a one-directional bias.

## Trust boundaries worth remembering

- The sim's damage table shows **no Arcane Phoenix damage at all**, while the log shows
  Phoenix at ~2.8–2.9%. simc's PTR model of the Sunfury capstone is incomplete here — don't
  read Phoenix's share across sim/log as like-for-like.
- **Correction to an earlier version of this note**, which claimed "Arcane Orb at 0.06%" in
  the sim. That figure was itself a data-reading bug, of exactly the kind this file warns
  about elsewhere: simc's `stats` list splits some abilities into a parent "cast wrapper"
  entry with **no damage fields at all** (Arcane Orb's top-level entry, id 153626, has
  `total_amount: null`) and a separate nested `children[]` entry that carries the real
  `total_amount`/`portion_amount` (id 153640, "arcane_orb_bolt"). Reading only the top level
  reports 0% for Arcane Orb and Touch of the Magi alike; both are wrapper-shaped. Once the
  children are included, the sim shows Arcane Orb at **~3.1%** — matching the logged ~3.2–3.4%
  closely. Re-verified against raidbots report `38BorEbHSzMrsQmgug8J2B` in
  `backend/wow_analysis/raidbots_client.py` (`_flatten_stats`). Arcane Orb is *not* a
  meaningfully mis-simmed ability; Arcane Phoenix still is.
- WCL `Buffs`/`Casts` events carry no Arcane Charge resource data; charge state must be
  inferred, so avoid claims that depend on exact charge counts.
- **PowerShell gotcha that silently corrupted two analysis passes:** variables are
  case-insensitive, so a loop counter `$soul` overwrites a spell-ID constant `$SOUL`. Also
  `,@(...)` around a returned array nests it and silently disables downstream
  `Where-Object` filters. Sanity-check every extract against a known cast count before
  drawing conclusions from it.
