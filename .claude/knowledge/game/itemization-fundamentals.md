# Itemization fundamentals — how gearing works in modern WoW

The patch-agnostic model: what an item *is* (a stat budget), how items are acquired and
raised, how they interact, and the questions to ask about any new season before trusting an
old answer. **This file holds mechanisms, not current numbers** — numbers quoted here are
illustrations from Midnight S2 (data build 12.1.0.69299) to make the mechanism concrete. The
current season lives in [itemization-midnight-s2.md](itemization-midnight-s2.md) and
[crafting-midnight-s2.md](crafting-midnight-s2.md); how to re-validate in
[itemization-staying-current.md](itemization-staying-current.md). Derivations:
`scratch/itemization/` (tracks A–F; stat budget in `G_stat_budget.md`).

## Why this file exists

Earlier sessions got gearing wrong by **reasoning from a remembered system instead of the
current one.** Itemization is what Blizzard re-tunes most: systems are replaced between
expansions, re-tuned between seasons, hotfixed mid-season (Midnight S2 alone: a bonus-roll
lockout rule in week 3, a crest-cap lift and a new upgrade stone in week 10, a spark-cap
raise twice in two weeks). The *mechanisms* below have been stable from Dragonflight to
Midnight; **every number attached to them must come from a dated source.**

## The model in one paragraph

An item is a **stat budget**: its **item level** sets a budget, its **slot** takes a fixed
fraction of it, and the item's own **allocation** splits that share between primary stat,
stamina and two secondaries (jewelry: no primary, much larger secondaries). The ilvl is set
by the **source** (content × difficulty) on an **upgrade track**, and raised by spending
**crests** — capped weekly early in a season, uncapped later. Because the crest cost of a rank
is the same in every slot but the stat gain is not, *where* you spend matters as much as how
much. Drops are random, so the game adds **deterministic or targeted valves** (Great Vault,
bonus rolls, tier Catalyst, crafting) that turn weekly activity into a chosen item. A few
**special ceilings** sit above the track cap for the slots that matter most. Gearing well is
managing weekly-gated resources across these valves, putting budget where it buys the most,
and keeping secondaries balanced — not farming drops.

## 1. The stat budget — what an item level actually buys

There is no official player-facing name for this. In the data it is the **RandPropPoints**
table (simc: `random_suffix_type` / "point allocation budget"), which is the term to search.

### The formula

    stat = round( allocation/10000 × Budget[ilvl][slot type] × M )
      primary (Str/Agi/Int):  M = 1
      stamina:                M = StaminaMultiplier[ilvl]
      secondary/tertiary:     M = CombatRatingMultiplier[ilvl][category]

Verified to ±1 against live tooltips for eight S2 items across every slot type (simc
`item_database::scaled_stat`, build 12.1.0.69299; derivation in `G_stat_budget.md`).

### Slot types — the budget fraction a slot gets

| Slot type | Slots | Budget share |
|---|---|---|
| 0 | head, chest, legs, **two-hand weapons** | 1.0 |
| 1 | shoulders, waist, feet, hands, **trinkets** | 0.75 |
| 2 | wrists, back, **neck, rings** | 0.5625 |
| 3 | one-hand / main-hand / off-hand weapons, held off-hands, shields | 0.5 |

The ratios are identical at every item level.

### Allocation — how an item spends its share

Each item carries fixed per-stat allocations; ilvl never changes them. Measured S2 patterns:
- **Armor** (every armor slot): ~5,260 primary, ~7,890 stamina, **~7,000 secondary** split
  between two stats by the item's own weights. Example: a chest at 65/35 crit/haste and a wrist
  at 35/65 haste/mastery have the same totals.
- **Jewelry** (neck, rings): **zero primary**, ~7,890 stamina, **~17,500 secondary** — 2.5× the
  armor allocation.
- **Caster weapons** put power in primary: ~30,600 on a one-hand main hand, ~16,100 on an
  off-hand, each 4–6× an armor piece. Physical-spec weapons scale weapon damage separately;
  not checked here.

### The multipliers — secondaries and stamina are scaled on top

- The **combat-rating multiplier depends on category** — jewelry is ~1.43× armor/weapon/trinket
  (1.148 vs 0.800 at 334). Combined with the allocation, a 334 ring carries **405 secondary
  rating against 113** on a 334 cloak of the same slot type — at the cost of the cloak's 106
  primary.
- The **rating multiplier falls as ilvl rises** (armor 0.997 at 289 → 0.759 at 344), while the
  stamina multiplier rises. So **ilvl growth is mostly primary and stamina**: one rank on a
  chest (331 → 334) is +3.3% primary but only +1.5% secondaries. Across a season ladder
  secondaries grow far slower than primary — character-sheet percentages creep.

### What one upgrade rank buys, by slot (331 → 334, the same 20 crests each)

| Piece | Δ primary | Δ secondaries | Δ stamina |
|---|---|---|---|
| caster 1H main hand | **+15** | +1 | +66 |
| caster off-hand | +8 | +1 | +66 |
| head / chest / legs | +6 | +3 | +133 |
| shoulders / waist / feet / hands | +3–4 | +2 | +100 |
| wrists / back | +3 | +1 | +75 |
| ring / neck | 0 | +6–7 | +75 |

### Consequences for decisions

1. **Upgrade currency is not slot-neutral.** A rank costs the same everywhere but a caster
   main hand gains 5× a wrist's primary. Spend crests and special-ceiling stones in budget
   order — weapon > slot-0 armor > slot-1 > wrist/back — unless an *effect* (trinket, embellishment,
   set bonus) changes the order. This is why mid-season stones target weapons/trinkets.
2. **Accept low ilvl where the budget is small.** Wrist, back and rings are the cheapest slots
   to leave behind; the top S2 players do exactly that (62–64% wear Hero 6/6 rings; back and
   wrist lag; wrist is the slot most often crafted). Conversely, a Hero-track item in a
   slot-0 or weapon slot is expensive to keep.
3. **Two-hand vs one-hand + off-hand:** a 2H is slot type 0 — one item holding the budget of two
   slot-3 items, so one upgrade path instead of two. Creators' "craft a 2H, it saves crests" is
   this mechanism.
4. **Jewelry is the secondary-stat balancing slot.** With ~3.6× the secondaries of a same-type
   armor piece and no primary, which ring/neck you wear decides your stat mix more than any
   other slot. Prismatic sockets (neck/rings, sockets added to helm/wrist/belt) add more
   steerable secondaries via gems.
5. **Stat *pairs* matter as much as ilvl in low-budget slots.** Choosing secondaries is possible
   on crafted gear (missives) and — since Midnight S2 — on tier pieces (the Catalyst keeps the
   source item's secondaries).
6. **Primary vs secondary trade-offs need a sim.** Whether +6 Int beats +3 of a well-weighted
   secondary, or a ring with the right pair beats a higher-ilvl one, depends on the spec's stat
   weights *at the current gear* — use Raidbots Top Gear / Droptimizer, not ilvl.

### Diminishing returns on secondaries

Rating-derived percentages (not base or buff-derived ones) are discounted above **30%**: 30–40%
counts at 90%, 40–50% at 80%, 50–60% at 70%, 60–80% at 60%, 80–100% at 50% (simc
`apply_combat_rating_dr`, curve 21024). At level 90, 1% costs 44 haste, 46 crit or mastery,
54 versatility rating. A full 334 set carries roughly 2,850 secondary rating before
gems/enchants, so a spec that stacks ~60% into one stat crosses the knee — part of why jewelry
and stat pairs are used to *spread* stats, and why stat weights must be re-derived as gear
improves. Tertiaries (leech, speed, avoidance) have their own curve.

### What the budget does not cover

Trinket on-use/proc effects, embellishments and item cantrips scale through **spell scaling**,
not this budget, so a trinket's value is its effect and its ilvl is secondary. Some procs are
**fixed** and do not scale at all (S2: Hunter's Ritual Stone after its hotfix). Never rank
trinkets by ilvl — top S2 Arcane mages wear a Hero-track trinket 13 ilvl below the Myth raid
options (92% of them; measured).

## 2. Item level, tracks and ranks

- **Tracks** (since DF 10.1): a ladder of named tracks (now Adventurer → Veteran → Champion →
  Hero → Myth), each with N ranks. Adjacent tracks **overlap**, and a drop always lands on the
  higher track where they do. The *source* decides which track; the *crests* decide the rank.
  At the top, "which track" is the real question: measured S2 Mythic raiders have 75% of items
  already at 6/6 of *some* track.
- **Which track you can reach follows difficulty**: outdoor → Adventurer/Veteran; Normal raid,
  low keys, mid delves → Champion; Heroic raid, mid-high keys, top delves → Hero; Mythic raid,
  high keys → Myth. Vault and bonus-roll rewards can sit a track above the drop (S2 raid).
- **Season reset** adds a large flat jump (Midnight S1 → S2: +46) and stops old gear upgrading.
  Last season's best is a 1–2 week stopgap (measured: 39% of top Mythic raiders in weeks 1–2,
  1% by week 7).
- **Special ceilings above the track cap** recur in some form every season: Very Rare drops,
  last-boss loot at an extra rank, mid-season stones (TWW Turbo Boost ranks → Midnight Ascendant
  Voidcores → Ascendant Venomstones). They target the high-budget or effect slots — weapon,
  trinket, sometimes neck.

## 3. Upgrade currencies

- **Crests**: one crest per track (Midnight), fixed cost per rank, earned from content of the
  matching difficulty in amounts scaling with difficulty / key level / boss position.
- **Weekly cap, cumulative**: unspent allowance carries forward; over-cap earnings spill to the
  next lower crest; **the cap is lifted mid-season** (DF S2 ~week 6; Midnight S1 and S2 week 10).
- **Early in a season, high-end players are gated by the crest cap, not by drops.** Drops decide
  *which* item gets upgraded, the cap decides *how many* — and §1 decides *which first*. An item
  arriving already at 6/6 (vault, bonus roll) is a pure crest saving.
- **Discounts** grow each expansion: free re-upgrade up to an ilvl the character already reached
  in that slot; a warband alt discount from an ilvl achievement (DF/TWW 33% → Midnight 50%);
  crest trade-down (lossless) and trade-up (lossy, achievement-gated).
- Base currencies beside crests (DF Flightstones, TWW Valorstones) were removed in Midnight
  (gold instead). Don't assume one exists.

## 4. Acquisition vectors — the axes to evaluate any source on

| Axis | Question | Why it matters |
|---|---|---|
| **Output** | What ilvl/track, at which difficulty — drop vs vault vs roll? | Relevance past week 2 |
| **Repeatability** | Unlimited / daily / weekly per boss / weekly / season / character / warband | Caps farming; daily/unlimited dominate alt ramp-up |
| **Probability** | Guaranteed choice, guaranteed random item, or per-player chance? | Expected items/hour; whether a *specific* item is reachable |
| **Time** | Real wall-clock including forming, travel, wipes | A 25-min key is 40–50 min in a pug |
| **Access** | Which week; behind a quest chain, renown, a research timer? | The best week-1 source is rarely the best week-8 source |

Recurring shapes (verify per season):
- **Raid**: weekly lockout per boss per difficulty; group loot since DF at ~1 item per 5
  players per boss (~20% each, far lower for a *specific* item); separate tier tokens; best
  loot on the last bosses.
- **Mythic+**: unlimited; ~40% per player per run; **chest ilvl caps at a key level** — higher
  keys buy crests and rating, not ilvl; the top track arrives via the vault and rolls.
- **Solo content** (delves and successors, prey, world): guaranteed, fast, no forming, capped
  below Mythic — the backbone of alt gearing.
- **PvP**: own currency/cap; usually PvP-only ilvl; relevant to PvE through the Catalyst and
  season achievements.
- **BoEs / world drops**: the only tradeable gear — gold-to-gear for alts and non-Mythic
  players (S2: 22.5% of top M+ players wear a Myth-level raid BoE).

## 5. The deterministic valves (where the decisions live)

- **Great Vault** (since SL): rows per content type, slots unlocked by activity counts, ilvl
  from the difficulty reached. One pick a week; its ilvl rule is re-tuned every season (S2 raid
  row pays one track above the drop). Taking nothing gives a consolation currency.
- **Bonus rolls**: MoP–BfA had a coin for a second chance at boss loot or gold. **Midnight's is a
  different mechanic under a similar name**: a currency that always yields an item from your
  loot spec's table **without replacement** (per character/encounter/difficulty), at
  vault-equivalent ilvl. Loot spec and target boss become decisions; it can beat both the drop
  and the vault.
- **Tier Catalyst** (since SL 9.2): converts off-pieces in tier slots, charges on a timer.
  Since Midnight S2 the converted piece keeps its secondaries — a tier slot is now also a
  stat-pair choice (§1).
- **Crafting**: deterministic ilvl, chosen secondaries, the only source of embellishments
  (2 max), gated by a weekly spark reagent; raised later by recrafting. Best used in
  low-budget, non-tier slots (§1) — crafted armor can't be catalysed.
- **Targeted vendors** (TWW D.I.N.A.R.). Pattern: each valve launches generous, then is
  throttled when gearing outpaces Blizzard's plan (Midnight S1 → S2 Voidcores, stated in a
  blue post).

## 6. Slot logic — what a high-end player fills where

Combines §1 with what top S2 players were measured wearing (track F):
- **Weapon**: highest budget per crest for casters (§1), plus special ceilings and roll targets.
  Week-1 weapon is often crafted, later replaced by a top-boss weapon.
- **Trinkets**: chosen by effect; ilvl second.
- **Tier slots** (head/shoulder/chest/hands/legs): 4pc mandatory, the fifth a flex — the
  skipped slot is usually the one with the best alternative (S2: legs or hands).
- **Crafted slots**: low-budget or contested, non-tier — wrist, back, belt, boots, off-hand —
  carrying the two embellishments.
- **Jewelry**: a stat-balance lever, not an ilvl race; Hero-track rings are normal at the top.

## 7. The season arc

| Phase | What binds | Typical moves |
|---|---|---|
| Pre-season / week 0–1 | Access | Spend sparks on the right slots; old-season stopgaps; fill vault rows |
| Weeks 1–~9 | **Weekly caps** (crests, sparks, vault, roll currency) | Hit every cap; crest only keepers, in budget order; vault/rolls on BiS |
| ~Week 10 | Caps lift; special-ceiling stones | Dump banked crests; upgrade weapon → trinket/neck |
| Late season | Luck on the last BiS items; stat polish | Targeted valves on remaining slots; re-balance secondaries; gear alts cheaply |

**Lost weeks are lost** for vault picks, weekly bonus-roll eligibility and timer-based catalyst
charges on an offline character, even when crest caps carry forward. Consistency beats bursts.

## 8. Alts — the fast ramp is a different problem

"Maximise ilvl per hour from zero", not "chase BiS":
- **Cumulative caps** give a late alt huge crest headroom — supply binds, not the cap.
- **Warband-wide**: alt crest discounts, warbound/BoE gear via the warband bank, renown.
  **Per character**: vault, bonus-roll lists, catalyst charges (usually), sparks.
- **Daily/solo sources first**, then the cheapest vault-row fillers, then the targeted valve.
- Spend the alt's crests in budget order too (§1) — weapon and slot-0 pieces first.
- Look for a **catch-up ledger** (Midnight's Spark Dust, S1's cumulative Voidcore purchase).

## 9. Failure modes to avoid

1. Assuming a previous expansion's system still exists or works the same (bonus rolls).
2. **Treating ilvl as the item's value.** It is a budget scaled by slot, split by allocation,
   and shaped by category multipliers — a +3 ilvl ring and a +3 ilvl weapon are different gains.
3. Ranking trinkets or effect items by ilvl.
4. Quoting a guide's number without its date; guides lag hotfixes and carry stale sentences.
5. Confusing vault ilvl with drop ilvl, or PvP ilvl with PvE ilvl.
6. Missing the time dimension: the best source depends on the week and the player's caps.
7. Calling odd gear "tech" from one log — it's tech only if common among top players *and*
   persistent past the first weeks ([itemization-staying-current.md](itemization-staying-current.md)).
