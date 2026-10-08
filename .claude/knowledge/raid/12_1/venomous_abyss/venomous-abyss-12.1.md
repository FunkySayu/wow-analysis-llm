# The Venomous Abyss — 12.1 raid, Balance Druid view

Tier opened 2026-08-18. Research/sims dated 2026-08-19 (one day in). Report artifact:
"Coiled Isle Fight Book". Working data in `scratch/venomous_abyss/` (encounter research,
`empirical_shape.md`) and `scratch/bdruid/vabyss/` (talent resolution, sims, proofread).

## Canonical encounter list

WCL `worldData.zone` (id 53/54 both resolve to this zone) — in-game journal order:

1. Nek'zali the Soulcoiler · 2. Entombed Sentinels · 3. Vashnik the Malignant ·
4. The Lost Explorers · 5. Sszorak · 6. The Twin Fangs · 7. The Coiled Altar · 8. Ula'tek
Plus **Nymrissa Wavecaller**, the Tidebound Grotto **Lair** boss (12.1 replaced rotating
world bosses with instanced Lairs at four difficulties).

**The raid branches after Nek'zali**, so published orderings disagree — Blizzard's news
post, Icy Veins and the journal all differ. Only Coiled Altar (7) and Ula'tek (8) are
fixed in every ordering. Don't treat "boss N" as unambiguous.

## Where to get data for this tier — the sourcing map

This tier has an unusual failure mode for *guide* sources: **no guide site or database page publishes damage numbers.** The
Adventure Journal ships literal `X` placeholders ("Inflicts X Shadow damage"), Wowhead's
spell DB has no damage fields populated for these IDs, and Icy Veins omits them by choice.

| Need | Source | Notes |
|---|---|---|
| **Damage magnitudes** | **Wowhead's tooltip API** — `nether.wowhead.com/tooltip/spell/<id>` | **Serves fully tuned values** (e.g. Rage of the Shackled = 416,703 Nature every 4 sec). This is the correction: the *database pages* and guide sites have nothing, which made two research passes conclude no numbers existed anywhere. They were looking in the wrong place. |
| **Aggregate damage totals** | **WCL API v2 `raidDamageTakenByAbility`** | total / totalReduced / hitCount / tickCount / per-target. Cross-checks the tooltips. |
| **Where damage went (output shape)** | **WCL API v2 `enemyDamageTaken`** | Per-NPC totals; lets you compute boss vs off-boss share and count concurrent add instances. |
| **Ability cadence in mm:ss** | **BigWigs boss modules** on GitHub (`BigWigsMods/BigWigs/TheVenomousAbyss/`) | Encounter-timeline duration constants straight from the game, commented by difficulty (mythic/heroic/normal). Best cadence source by far. Encodes *when*, never *how much*. |
| **Exact tooltips + spell IDs** | **warcraft.wiki.gg** (Adventure Journal mirror) | Verbatim journal text, durations, stack behaviour, difficulty gating. |
| **Strategy prose** | Method, Icy Veins | Icy Veins is explicit about what is untested. |

**Unusable, and why:** Wowhead *guide* pages (body is client-rendered; direct curl is
CloudFront-403). WCL web statistics pages (403 without auth — use the GraphQL API).
raidstrats.gg (403). **mythictrap.com served a completely unrelated boss under HTTP 200**
on one URL — the exact silent-wrong-data failure CLAUDE.md warns about. All gold-selling
SEO sites fabricate plausible mechanics; never open them.

**A BigWigs module that is a stub is itself evidence.** `Ulatek.lua` sets `barInfo = nil`
and can never emit a bar, while every other module has a populated duration table — an
independent confirmation that the boss shipped untested.

## Empirical fight shape (measured from kill logs)

`off-boss` = share of total raid damage dealt to something other than a boss.

| Encounter | Off-boss | Concurrent cleave targets |
|---|---|---|
| Sszorak | **0.0%** | 1 — zero adds, provably |
| The Coiled Altar | 0.0% | 1 (P1/P2/intermission), 2 stacked (P3) |
| The Lost Explorers | 0.0% | 2 (third boss held 30yd away) |
| The Twin Fangs | 4.2% | 2 permanent + 3 adds every 68s (H) |
| Entombed Sentinels | 14.9% | 1 golem per player |
| Vashnik | 17.2% | 1 + **up to 10 concurrent add instances** |
| Nymrissa | 31.2% | 1 + separated add waves |
| Nek'zali | 38.4% | 1 at a time — **sequential, not cleave** |
| Ula'tek | **62.6%** | many; cleave *is* boss progress (Ula'tek's Bond) |

**Off-boss share is not cleave opportunity.** Nek'zali has the second-highest off-boss
share of any raid boss and is still a sequential single-target fight. Always separate
"how much damage went off-boss" from "how many targets were alive at once."

### Burn windows worth planning cooldowns around
- **Sszorak — Dig In**: +30% damage taken, 25s, every **111s Heroic** (100 M / 125 N).
- **Coiled Altar — intermission**: Zul'jan at **+100%** while Ghastly Regeneration heals
  him. A race against a heal, not just an amp.
- **Ula'tek — Venomous Heart**: exposed 20s at **+100%**, in all three stages. Absorbed
  **28.2% of the entire raid's damage** in the reference kill.
- **Nek'zali — Stage Two**: burn from the moment the intermission ends; Bloodlust here.

## Balance Druid conclusion

**Elune's Chosen wins at every target count from 2 up and leads at 1.** Across 5 builds ×
11 fight shapes the hero-tree ordering never changed; Keeper of the Grove was not best in
any scenario. Full numbers in `scratch/bdruid/vabyss/shape_findings.md`.

- 1 target: whole field spans **1.5%** — build barely matters.
- 3 targets: field spans **16.3%** — almost entirely hero tree, not individual picks.

Two builds cover the raid: an EC **Lunation + Radiant Moonlight** variant for anything that
cleaves, and an EC **Power of Goldrinn** variant for anything that doesn't. Keeper of the
Grove is only defensible on **Sszorak**, where it's within 900 DPS at one target and
**Control of the Dream** (banks 15s of Force of Nature / Convoke the Spirits) is the
mechanism for reaching the off-grid 111s Dig In window.

### Cooldown sequences (traced from 1-iteration combat logs)
- **Keeper of the Grove** — Force of Nature → Celestial Alignment → Convoke the Spirits in
  a ~3s block every **~60s**; Eclipse every ~20s underneath.
- **Elune's Chosen (Goldrinn)** — Fury of Elune → Incarnation: Chosen of Elune, same ~60s
  skeleton, different buttons, no cooldown banking.
- **Elune's Chosen (Lunation)** — **no burst block**: Fury of Elune every ~22s (14 casts in
  300s vs 5), Incarnation on a loose ~90s. This flexibility matters because the raid's
  cadences are 68s, 90s and 111s — none of which divide into 60.

### Barkskin is a three-part package
All builds take **Improved Barkskin** (12s → **16s**) and **Matted Fur** ×2 (absorb);
four of five take **Verdant Heart** (**+20% all healing received**) — that last one is the
mechanism that makes Barkskin genuinely additive with a healer's raid cooldown rather than
redundant. **Verdant Heart is absent from the Sentinels/Vashnik build.**
Exception: **Vashnik's Siphoning Infection cuts healing received to 100%** — Verdant Heart
is dead there and the 20% DR + absorb are the only levers. Highest-value Barkskin in the raid.
**Protective Growth** (Keeper builds) = 8% DR while your own Regrowth is on you — one GCD,
castable pre-emptively, unlike Blooming Infusion which needs five Regrowths.

## Sim caveat carried forward

`raid_events+=/adds` with a fixed `duration` gives adds a **lifetime, not health** — they
despawn rather than die. Results reproduce to 0.1% but are **non-monotonic in cadence**
(Early Spring best at 60s waves, worst at 45s and 90s, the opposite of what its 45s Force
of Nature predicts). Do not draw within-hero-tree conclusions from these until the adds are
given real health. The sustained `desired_targets` matrix is clean and is what the
hero-tree conclusion rests on.
