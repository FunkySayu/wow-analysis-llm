# Crafting for gear in Midnight Season 2 (patch 12.1)

**Valid as of 2026-10-07.** Companion to [itemization-midnight-s2.md](itemization-midnight-s2.md);
concepts in [itemization-fundamentals.md](itemization-fundamentals.md). Source research:
`scratch/itemization/D_crafting.md` (+ measured adoption in `F_wcl_gear.md`, creator notes in
`transcripts/distilled_kelani_2.md`). Tags as in the S2 file. **Re-validate on 2026-10-20**
(Venomstones make max-quality crafts upgradeable; crest cap lifts).

## Why craft at all

Crafting is the only source of **embellishments** (2 max equipped), lets you **choose
secondaries** (Missives), and gives a **deterministic ilvl** independent of loot luck. For a
Mythic raider it fills slots that drops serve badly — not tier slots, since crafted armor
**cannot be catalysed**. Measured on top players (week 6–8): 2.46 crafted pieces each, almost
all in wrist (77%), off-hand (48%), belt (29%), ring (24%), feet (21%). [measured]

## The ilvl ladder — one reagent tier + quality

| Reagent "Infuse with Power" | Crafted ilvl by quality (q1→q5) | Cost |
|---|---|---|
| Adventurer Mistcrest | 266–279 | 80 crests |
| Veteran Mistcrest | 279–292 | 80 crests |
| Spark of Tides alone | 292–305 | sparks |
| Spark + Hero Mistcrest | 305–318 | sparks + 80 Hero |
| **Spark + Myth Mistcrest** | **318–331** | sparks + 80 Myth |

[db] crest/spark tooltips; Champion crests have no crafting use. q4 is 3 below q5 (Myth q4 =
328). **Max craft 331 = Myth 5/6**, 3 below Myth 6/6 (334) and 13 below the Myth 9 (344)
last-boss loot. [db]/[blue]

- **Sparks per item: 2 for one-hand / armor / accessories, 4 for a two-hander** [guide, low
  authority] — corroborated by Kelani ("your fourth spark will let you craft two pieces of gear
  right away or a two-handed weapon") [creator] and by Blizzard's cap steps. A 2H probably costs
  160 crests (S1 value; S2 unverified).
- **No upgrade track on crafted gear.** Raise it by **recrafting** with a higher crest tier —
  the recraft does **not** consume new sparks ("without wasting previously used
  bind-on-pickup materials") [guide]. So the expensive, irreversible decision is the *slot and
  item*, not the ilvl.
- Recrafts are **personal orders only**, and an item made with low-quality reagents is harder to
  push to q5 on recraft. [guide]

## Sparks of Tides — the gate

- Item 274476, BoP, whole items (no fragments). Season-specific: last season's Spark of Radiance
  sets a S1 range and is useless for S2 gear. [db]
- **Cap schedule**: 2 in the pre-season week (Aug 11), 4 on Aug 18, 5 on Aug 25 [blue]; then +1
  per week [creator: Kelani "cap is four in the first week… +1 per week after"]. Everyone
  started the season able to make **two 1H/armor crafts or one 2H**, then one more 1H/armor
  craft every two weeks.
- **Sources** (weekly, several quests can grant *the* week's spark up to the cap) [blue/creator]:
  Silvermoon weeklies ("Unity Against the Void", "Trailing Xal'atath"), "Turn Back the Surge"
  (Curse Surge, Coiled Isle), "Midnight: Vaults of Atal'Utek", and PvP "Sparks of War: <zone>"
  (War Mode). One-time: "Midnight: World Tour" (an extra spark outside the seasonal max).
  The Great Vault's consolation vendor sells a Spark for 6 Thalassian Tokens of Merit,
  reportedly bypassing the seasonal cap [guide].
- **Catch-up ledger: Tidal Spark Dust** (currency 3509) counts sparks earned; if you fall behind,
  max-level content catches you up. On 2026-09-15 Blizzard mailed missing sparks to anyone whose
  Dust exceeded sparks held in bags *or gear*, so spent sparks still count. [db]/[blue]

## Embellishments

- **2 equipped max.** Two forms: an **optional reagent** added to an unembellished crafted
  item of the right slot class, or a **pre-embellished item** (fixed effect; 2-piece
  embellished sets use both slots). Remove one by recrafting with **Lucky Keychain** ("+1
  Sparkle", no power) — this is why ~7–12% of top players show a Keychain as a third effect.
  [db]/[guide]/[measured]
- **What the field runs** [measured, top Mythic raiders, six specs]: Arcanoweave Lining on 92%;
  **Arcanoweave ×2 (42%)** for physical specs; **Arcanoweave + Hunter's Ritual Stone (36%)** for
  casters, the Stone on the crafted Aln'hara Lantern off-hand (Arcane 77%, Balance 74%). Adorned
  Fang 6%, Darkmoon Sigil: Hunt 5%. Treat this as settled, but re-sim per spec.
- 12.1 tuning: Polished Ammolite (−90%), Snakeskin Lining (−90%), Adorned Fang (−70%) were nerfed
  on PTR for being BiS-for-everyone; **Hunter's Ritual Stone was hotfixed on Aug 17 to a flat
  101 secondary that no longer scales with ilvl** (was up to 165). [guide]. A fixed-value proc loses
  relative value as the item's ilvl rises — re-sim after each recraft.
- Ritual Stone is Blacksmithing-weapon-only and its recipe is a Prey-renown unlock. New 12.1
  reagents: Hunter's Ritual Stone, Adorned Fang, Snakeskin Lining, Polished Ammolite, Coiled
  Snake-Eye (Engineering guns). Full reagent list with item ids: `D_crafting.md` §3.2.

## Getting a max-quality craft without the profession

- Place a **Personal** (or Guild) order — only those let you set a **minimum quality**; use q5
  (needed for Venomstone eligibility from Oct 20). Public orders require all reagents and no
  quality floor. [guide]
- **BoP reagents (sparks) and crests always come from the customer.** Add a Missive
  ("Thalassian Missive of the X") to pick the two secondaries. [guide]
- Crafter concentration: 1000 per profession, regenerating ~10/hour — q5 spark crafts are
  concentration-expensive, which is why they carry a real commission. [guide]
- Known risk: in late August failed orders lost sparks and crests (Blizzard CS: not intended);
  S1 had a recraft bug that ate 80 crests with no restoration. Prefer a trusted guild crafter.
  [community]/[blue]

## Strategy

1. **Craft in non-tier slots** that won't see a better drop soon: wrist (the permanent craft —
   only 5% of top raiders have a ≥334 wrist), belt, boots, cloak, off-hand; a ring if the
   raid ring is far off. [measured]/[guide]
2. **Week 1: the weapon.** In weeks 1–2, 46% of top raiders had a crafted main hand (331 was the
   highest ilvl available that week); by week 7 most replaced it with a raid weapon, keeping the
   crafted off-hand. Casters: a crafted 2H covers both weapon slots for one set of crests
   [creator: Kelani]. [measured]
3. **Embellishments first, ilvl later.** Put both embellishments on early crafts — 37% of
   week-1 top raiders ran only one, 3% by week 7 [measured]. Don't burn a spark on an
   unembellished filler slot.
4. **Crest competition**: until Oct 20, an 80-Myth recraft eats most of a week's Myth cap. A
   Spark + Hero craft (318) recrafted later to Myth (331) is fine — no spark is lost.
5. **Craft vs drop for slots with 344 loot**: Tettles crafted legs at 331 although Coiled Altar
   legs are 344 BiS — immediate power over a lottery. For weapon/trinket/neck from Oct 20 a q5
   craft can be Venomstoned like a Myth 6/6, so the craft is no longer a dead end there. [creator]/[blue]
6. **Alts**: sparks are BoP and per character, but the Spark Dust ledger catches a late alt
   up; Adventurer/Veteran-crest crafts (≤292, no spark) are cheap bridges.

## Open questions

- Spark cap after week 3 rests on one creator statement; check the "Tidal Spark Dust x/y"
  currency tab.
- 2H crest cost (160?) for S2; per-quality ilvl steps (q1–q3).
- Venomstone result for a 331 craft (likely +7 → 338, unconfirmed).
- Crafted PvP (Heraldry) item levels: wiki 309/322/335 vs a boost site 318/331/344.
- Warband transfer of Sparks (none found).
