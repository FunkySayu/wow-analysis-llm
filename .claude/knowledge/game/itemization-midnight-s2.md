# Gearing in Midnight Season 2 (patch 12.1) — the current-season guide

**Valid as of 2026-10-07 (season week 8).** Season 2 opened 2026-08-18 (patch day / pre-season
2026-08-11). **Re-validate after 2026-10-13 (12.1.5) and 2026-10-20 (crest cap lift +
Venomstones)** — both change the answers below. Concepts are in
[itemization-fundamentals.md](itemization-fundamentals.md); crafting in
[crafting-midnight-s2.md](crafting-midnight-s2.md); how to re-check in
[itemization-staying-current.md](itemization-staying-current.md).

The research tracks and saved primary texts behind this file stayed in the local working
area (not in the repo); this file is their reconciled result. Tags: **[blue]** official,
**[db]** game data / wiki, **[guide]** Wowhead/Icy Veins/Method, **[creator]** SignsOfKelani /
Tettles, **[measured]** counted from WarcraftLogs gear of top players, **[inferred]**.
Wowhead returned 403 to scripted fetches during this research, so some Wowhead claims were
read via other sites quoting them.

## 0. The five things that drive S2 gearing decisions

1. **Bonus rolls (Nebulous Voidcores) are the highest-leverage decision.** A roll on a raid boss
   costs 1, yields the *vault-equivalent* ilvl — on Mythic bosses 1–6 that is **Myth 6/6 (334)
   vs a drop's 318–324** — and draws without replacement from your loot-spec table. Supply is
   1–2 per week. See §5.
2. **The raid Great Vault pays one track above the drop** (Heroic vault = Myth 1/6). Only the
   vault and bonus rolls get this; normal drops don't. [blue]
3. **The weekly Myth-crest cap (100) limits progress until week 10** (2026-10-20 lift).
   Items that arrive at 6/6 (Mythic vault, Mythic bonus roll) are pure crest savings — that is
   why top players pass on vault items for Voidcores. [blue]/[creator]
4. **The last two Mythic bosses (Coiled Altar, Ula'tek) are their own ilvl tier**: all their
   loot is "Myth 9" = 344, drop or vault. Most BiS lives there. [blue]
5. **Embellishments only come from crafting**, and the field has settled on the same pair
   (Arcanoweave Lining + Arcanoweave / Hunter's Ritual Stone). [measured]

## 1. Season calendar (NA resets) [blue unless noted]

| Date | Week | What opens |
|---|---|---|
| Aug 11 | pre-season | Patch 12.1. Heroic + M0 (weekly lockout that week, 292). Delves (no Bountiful). Lair at World difficulty. Sparks begin (cap 2). Catalyst usable. |
| Aug 18 | 1 | **All raid difficulties incl. Mythic** + LFR wing 1; M+ S2; rated PvP; Bountiful Delves; Nightmare Prey; Lair N/H/M. Spark cap 4. No Voidcore in this vault. |
| Aug 25 | 2 | **Voidcore option in the Great Vault** (≥3 slots). LFR wing 2. Spark cap 5. |
| Sep 1 | 3 | **Bonus rolls only where loot-eligible** (1 roll per boss per difficulty per week; hotfixed live ~Aug 28). |
| Sep 8 | 4 | LFR complete. |
| Oct 6 | 8 | **Orin Straylight's weekly Voidcore** (2nd source). |
| Oct 13 | 9 | **12.1.5**: Kith'ix single-boss raid, Labyrinth of Kindo'jan mega-delve, Venomstone research quest. |
| Oct 20 | 10 | **Ascendant Venomstones** + **crest cap lifted**. |

Mythic opened in week 1 alongside Normal/Heroic — unlike DF/TWW's one-week delay; 12.1 used a
pre-season week instead.

## 2. Item levels

| Rank | Adventurer | Veteran | Champion | Hero | Myth |
|---|---|---|---|---|---|
| 1/6 | 266 | 279 | 292 | 305 | 318 |
| 2/6 | 269 | 282 | 295 | 308 | 321 |
| 3/6 | 272 | 285 | 298 | 311 | 324 |
| 4/6 | 276 | 289 | 302 | 315 | 328 |
| 5/6 | 279 | 292 | 305 | 318 | 331 |
| 6/6 | 282 | 295 | 308 | 321 | 334 |

[blue]/[db]/[guide], decoded against item bonus IDs in [measured] data. Rank 5–6 of a track =
rank 1–2 of the next (Hero 6/6 = Myth 2/6 = 321). Warcraft Wiki prints some 6/6 values one
higher (335/322) — an off-by-one in the wiki, not the game (bonus-ID decode gives 334/321).

Above the track:
- **Myth 9 = 344**: Mythic Coiled Altar + Ula'tek loot and Mythic Very Rare items, from drop
  *or* vault. Not upgradeable. [blue]
- **Myth 8 = 341**: Venomstone ceiling for necklaces [blue]; for weapons/trinkets the stated
  bump is "six to seven item levels… another two upgrade bumps" [creator], i.e. most likely 341
  too. The wiki's 344 for weapons/trinkets is unconfirmed. **Check after Oct 20.**
- Crafted max: 331 (q5 with Myth crests). See the crafting file.

### Drop / vault / bonus-roll ilvl by source

| Source | Drop | Vault & bonus roll | Notes |
|---|---|---|---|
| LFR | 279–289 Veteran 1–4/6 | 292 Champion 1/6 | LFR roll ilvl: Method 1/6 vs Icy Veins "1/8" — unverified |
| Normal raid | 292–302 Champion | 305 Hero 1/6 | |
| Heroic raid | 305–315 Hero 1–4/6 | **318 Myth 1/6** | Heroic is a Myth-track source via vault/roll |
| Mythic bosses 1–6 | 318 / 321 / 324 by boss position | **334 Myth 6/6** | Nek'zali 318; Sentinels, Lost Explorers 321; Vashnik, Sszorak, Twin Fangs 324 |
| Mythic Coiled Altar, Ula'tek, Very Rare | **344 Myth 9** | 344 | |
| M+ +10 and up (chest) | **311 Hero 3/6 (cap)** | **318 Myth 1/6** | chest never gives Myth track |
| M+ +6..+9 | 305–308 | 311–315 Hero | |
| M0 | 292 Champion 1/6 | 302 | daily per dungeon (8) |
| Bountiful Delve T8–T11 | 295 Champion 2/6 | 305 Hero 1/6 | bounty map also 305 |
| Nightmare Prey | 292 | 305 | 2 items/week/difficulty |
| Lair (Nymrissa) W/N/H/M | 279 / 292 / 305 / 318 | raid-row rule presumably | counts for raid vault row |
| Kith'ix (12.1.5) | Myth 3/6 on Mythic (cut from 9/6 on PTR) [creator] | **unstated** — see §10 Q4 | single boss; quest gives a Hero neck/ring |

Raid boss order is branching; see [venomous-abyss-12.1.md](../raid/12_1/venomous_abyss/venomous-abyss-12.1.md). Only
Coiled Altar (7) and Ula'tek (8) are fixed.

## 3. Crests (Mistcrests) and upgrades

- One crest per track; **flat 20 per rank** (100 for 1/6→6/6) + nominal gold. [blue]
- Sources: Adventurer — outdoor, Delves T1–4; Veteran — LFR, Heroic dungeons, Delves T5–6;
  Champion — Normal raid, M0, +2/+3, Delves T7–10; **Hero — Heroic raid, +4..+8, Delves T11**;
  **Myth — Mythic raid, +9 and up, T11 Gilded Stash, Ritual Sites T6**. Lairs give their
  difficulty's crest. [db]/[guide]
- Amounts: M+ +9/+10/+11/+12+ = 10/12/14/16 Myth (+4..+8 Hero amounts disputed between sources);
  raid 10–20 per boss by position, Ula'tek +10 of the next tier up; T11 Gilded Stash 20 Myth per
  week (4 × 5, [db] + [creator]; Icy Veins says 3 × 7). [guide]/[db]
- One-time crest windfalls (don't count against cap): delve Nemesis first kill — Hero + Myth
  crests (Kelani: 30 + 30; Icy Veins: 60 Hero + 30 Myth; unresolved); T11 "Cracked Keystone"
  quest 20 Hero + 20 Myth. [creator]/[guide]
- **Cap: 100 per type per week, cumulative** (unspent allowance carries); over-cap earnings spill
  to the next lower crest. **Lifted the week of Oct 20** (S1 was lifted at its own week 10 too). [blue]
- Trade **down** 10→10 one tier (free, not cap-counted). Trade **up** 30→10, unlocked per track by
  the "<Track> of the Mist" achievement (every slot ≥ 282/295/308/321/331), and counts against
  the higher cap. [db]/[guide]
- **Discounts**: free re-upgrade up to an ilvl the character already reached in that slot
  (per character); **50% warband alt discount** per track once any character earns that track's
  "of the Mist" achievement [guide: Wowhead news 380668; no blue found]. The achievement
  checks *ilvl*, not track.
- **Achievement tech** [creator]: guilds pass farm-boss loot around so more members trip "Myth
  of the Mist" (unlocking the warband discount for their alts); in S1, players deliberately
  traded crests down on an alt to earn "Hero of the Dawn" by week 3 and halve their main's
  Hero-crest cost. Plan for it if you maintain alts.
- Cost to max: Mythic early/mid/late drop 100/80/60 Myth crests; Mythic vault/roll 0; Heroic
  vault/roll or +10 vault 100 Myth. Under the cap that is **≈ one Myth item maxed per week** —
  the binding constraint for a Mythic raider through week 9. [inferred]

## 4. Acquisition vectors at a glance

| Vector | Repeatability | Per-attempt odds (per player) | Real time | Best output |
|---|---|---|---|---|
| Raid boss | weekly per boss per difficulty | group loot: 2 items per 10 players, +20%/extra player → **~20%/boss**; tier tokens 1 per 10 players | guild Heroic clear 3–4 h; pug +1 h forming | 344 (Mythic last two) |
| Raid vault row | 3 choices at 2/4/6 kills; pool = every boss killed this season; Lair counts | deterministic pick | — | 334/344 |
| M+ chest | unlimited | 2 items per run per party → **~40%/run**, spec-filtered dungeon table | +10: 25–35 min in instance, **40–50 min pug wall-clock** | 311 |
| M+ vault | 1/4/8 runs | pick | — | 318 |
| M0 | daily × 8 dungeons | ~40%/run | 20–25 min | 292 |
| Bountiful Delve | per Restored Coffer Key (~6/week from shards [creator]) | guaranteed coffer item | 10–15 min solo | 295 (+305 map) |
| World vault row | 2/4/8 delves/prey/ritual sites | pick | — | 305 |
| Prey | 2 items/week/difficulty + soul bonus once/week | guaranteed | ~15–20 min | 292 (+Hero via souls) |
| Lair | weekly per difficulty (4) | raid-like; count unknown | ~6-min fight + forming | 318 |
| Raid BoEs | trash drops, tradeable / AH | random | gold | Myth 6/6 seen in logs [measured] |
| Labyrinth (12.1.5) | weekly | Hero via fragments; "Mythical soul fragments" quest 1/week × 6 → **2 Myth pieces of your chosen slot** [creator] | 9 chambers | Myth |

PvP gear's PvE ilvl is not confirmed (PvP-only scaling); PvP matters to PvE via catalyst
(PvP pieces are catalyst-eligible), the Serpent Scion charge (1600 rating) and rated-PvP crests.
The S2 vault has three rows (raid / dungeons / world), no PvP row. [guide]

## 5. Bonus rolls — Nebulous Voidcores (the mechanic that drives priority)

**Not the MoP–BfA coin.** Introduced in **12.0.5 (2026-04-21)**, mid-Season 1 — not at 12.0
launch — as the Voidforge system; reworked for 12.1. [blue]

### Rules (current)
- **Supply** [blue]: (a) the Great Vault offers one Voidcore *instead of* an item if ≥3 slots are
  unlocked (from the Aug 25 vault); (b) from week 8 (Oct 6), Orin Straylight (by the Catalyst,
  Silvermoon) sells +1/week for 5,000 gold / 2,000 Voidlight Marl / 80 Veteran Mistcrests,
  after a quest chain ("In the Catalyst's Shadow" → "Prismatic Potential" → research timer).
  → **max 1/week in weeks 2–7, max 2/week from week 8.** The S1 sources (Decimus 2/week
  cumulative purchase, Token-of-Merit exchange) are gone; S1 Voidcores became gold.
- **Use**: after a raid boss (any difficulty), a completed M+ key, a Bountiful Delve, Nightmare
  Prey, or a Lair (once/week). **Cost 1 everywhere** (raid was 2 in S1). [blue]
- **Outcome**: always an item, from **your current loot specialization's** table for that
  encounter and difficulty. Tooltip: "Items may be received once per difficulty level until all
  potential items for your current specialization have been transmuted." → **without
  replacement, per character, per encounter, per difficulty**, resetting when exhausted. [db]/[blue]
- **Item level = Great Vault equivalent** for that content (§2 table). [blue]
- **Raid lockout**: only on encounters you are still loot-eligible for → **one roll per boss per
  difficulty per week**. Mythic and Heroic are separate, so one boss can be rolled twice a
  week (Heroic roll = 318, Mythic = 334/344). M+ appears unaffected. [blue]/[community]
- Rolled raid armor can be catalysed (fixed Aug 26) and keeps its stats.

### Strategy
- **Spend on raid bosses, not dungeons.** One spec's raid-boss table is ~4–7 entries, a dungeon's
  8–13 (`data/classes/druid/balance/12_1_loot_sources.json`, Balance), and the M+ roll is only Myth 1/6. A raid roll
  hits a target ~2× faster at the same cost.
- **Default sink: the boss holding your BiS trinket/weapon/neck**, usually Coiled Altar /
  Ula'tek (344) or a mid boss whose table is small (Tettles rolls Lost Explorers for Gebbo's
  Bottomless Bag + tier shoulders). [creator]
- **Roll every week.** Since the lockout, an unrolled week on your key boss is lost; banking
  Voidcores only helps to cover several key bosses/difficulties in one week.
- **Loot-spec tech**: switch to the spec of your class whose table on that boss contains your
  target but fewer other items; set it **before** the prompt. Worked example [creator, Tettles
  2026-09-08]: a Balance druid rolls Lost Explorers as **Feral** loot spec to remove a
  one-handed caster mace from the table (he already has a 331 crafted staff); the week he
  forgot to switch, the roll landed on the mace — a wasted Voidcore.
  Also check you don't already own the item from another source; drops and vault picks
  don't seem to remove it from your roll table [guide/community, unconfirmed].
- **Vault: item or Voidcore?** Take the item only if it's a real, lasting upgrade *and* you
  couldn't get it from a roll. Otherwise take the Voidcore. Reasoning from top players:
  a Mythic roll arrives at 6/6, so each one saves 60–100 Myth crests while the cap binds.
  Tettles declined a BiS Myth 1/6 vault trinket three weeks running to keep rolling, using a
  Hero version meanwhile ("bonus rolling to save infinite crests is far superior"). [creator]
  Community view is split; some call it absurd that a Voidcore beats a BiS vault item.
- **Expected value** (without replacement): with *n* items in the table, one specific item
  takes on average (n+1)/2 rolls, at most n. Two wanted items take on average 2(n+1)/3.
  On Ula'tek (n≈5) that's 3 weeks on average, 5 at worst, matching Wowhead's "3 (or 4) weeks".
  Season supply ≈ 44 Voidcores at most over 26 weeks, ~19 of them free (Orin). [inferred]

## 6. Catalyst

- Charges (Crystallized Venomblight Manaflux): 1 at season start, +1 every 2 weeks, max 8, **no
  catch-up for offline weeks** — log alts in. +1 from "Serpent Scion" (Heroic/Mythic Ula'tek,
  2000 M+, or 1600 PvP). After a 4-piece, "Catalyst Unbound" lets charges drop from raid, M+,
  Bountiful Delves and rated PvP. [guide]
- **12.1: converted pieces keep their secondaries, tertiaries and cantrips** (e.g. Ula'tek
  "Venomcursed"). Tier slots are now stat choices; farm the off-piece with the stats you want
  and convert it. Crafted armor cannot be catalysed. [blue]/[guide]
- Tier tokens are armor-type shared (Idol/Remnant/Icon/Relic/Effigy for hands/shoulders/chest/
  legs/helm from Sentinels/Lost Explorers/Vashnik/Sszorak/Twin Fangs); Ula'tek drops an omni
  token (Slumbering Coil Curio). [guide]
- Creators put 4-piece first, worth a large DPS jump (Tettles quotes ~20% for his spec;
  spec-dependent). Get 4pc with suboptimal stats early to unlock Catalyst Unbound. [creator]

## 7. Ascendant Venomstones (from Oct 20) [blue]

10 stones upgrade a **fully upgraded** Hero 6/6, Myth 6/6 or **max-quality Tidal-crafted**
weapon, trinket or (new) necklace by two steps (to Myth 8 = 341 for necks; weapons/trinkets
most likely the same, see §2). One stone per Heroic/Mythic raid boss, +10 key, T11 Bountiful
Delve, Nightmare Prey Champion chest → ~1 upgrade per week of Mythic raiding. Unlock quest
"Ancient Depths, Ancient Venom" from Oct 13 at Orin. Implication: **max out the weapon,
trinkets and neck to 6/6 before Oct 20**; Hero 6/6 trinkets you plan to keep become eligible too.

## 8. What top players actually wear (measured, week 6–8)

From 1,879 top-100 Mythic raiders and 1,343 high-key (18–23) M+ players across six specs
(Balance, Arcane, Fury, BM, Shadow, Resto Shaman), WarcraftLogs rankings with combatant gear,
2026-09-22 → 10-06. Method in [itemization-staying-current.md](itemization-staying-current.md)
("Grounding in logs").

- **Median ilvl 327.9**; best 337.6. Item mix: Myth 6/6 38.5%, Hero 6/6 36.8%, crafted 15.7%,
  Myth 9 1.2%. Partial ranks are rare — **the lever is the track, not the rank**.
- **Lagging slots**: rings (62–64% Hero 6/6, mostly M+ rings), back, hands, legs.
- **Crafted** 2.46 pieces per player: wrist 77%, off-hand 48% (casters' Aln'hara Lantern), belt
  29%, ring 24%, feet 21%. **Embellishments**: exactly 2 for 90%; Arcanoweave Lining on 92%,
  Hunter's Ritual Stone 42% (casters put it on the off-hand).
- **Tier**: 4pc 62%, 5pc 37%. The skipped tier slot is usually legs (31%) or hands (24%),
  filled by Hero 6/6 or a craft.
- **Deliberate non-obvious picks** (common and persistent → real tech):
  - Hero 6/6 M+ trinkets over Myth raid ones — Freightrunner's Flask on 92% of Arcane, 241 of
    325 copies at Hero 6/6; Vile Vial of Volatile Venom likewise. Trinket effect beats −13 ilvl.
  - **Bite of Zul'jan**: a non-tier weapon + trinket 2-piece set (Zul'jin's Guillotine Technique
    + Maze-roa) — 95%/89% of Fury.
  - Myth 6/6 **raid BoEs** (boots/belts/neck) — 12% of raiders, 22.5% of M+ players.
  - Ula'tek "Venomcursed" cantrip items — 96% wear ≥1; the Aqirbane Reliquary neck always.
- **Lucky Keychain** ("+1 Sparkle", the embellishment *remover*) on 7–12% as a third effect —
  almost certainly a stripped earlier craft that freed an embellishment slot, not tech. [inferred]
- **Early season (weeks 1–2)**: median 314; 39–43% of items sat exactly at Hero 3/6 (311) —
  that is the **M+ +10 chest cap** and the Heroic late-boss drop ilvl, i.e. the week-1
  firehose [inferred]. 39% still wore a previous-season item (1% now). First crafts were
  **weapons** (46% crafted main hand early → 11% now, replaced by Ula'tek's Jan'thrazet); the
  wrist craft grew 45% → 77% and stayed. Early players ran one embellishment (37%) and added the
  second later.

## 9. Priorities

### Mythic raider, each week (until Oct 20)
1. Fill all three raid-vault slots (6 bosses); add M+ (8 runs at +10) and world row if time
   allows — more vault choices *and* the ≥3-slot Voidcore option.
2. Vault: Voidcore unless an item is a lasting BiS you can't roll for.
3. Roll on your BiS boss, on both Heroic and Mythic where useful; set loot spec first.
4. Spend the 100 Myth crests on keepers, never on stopgaps, in **stat-budget order**
   ([fundamentals §1](itemization-fundamentals.md)): a rank (331→334) is +15 Int on a caster
   main hand, +6 on head/chest/legs, +3 on wrist/back, 0 on a ring. Weapon/trinket/neck also
   need 6/6 to take Venomstones on Oct 20. Over-cap spills to Hero crests — use them on Hero 6/6 trinkets/rings
   you'll keep.
5. Sparks: craft in a non-tier slot that won't see a better drop (crafting file).
6. Catalyst charges toward 4pc, then to swap a better-stat off-piece into a tier slot.

### After Oct 20
Crest cap gone → max every item you'll keep; trade surplus down/up; Venomstone the weapon, then
trinkets/neck (~1 upgrade per raid week).

### High M+ player (no Mythic raid)
M+ chest caps at 311; Myth only via the +10 vault (318) and Voidcores. Heroic raid now gives
Myth 1/6 via vault/roll — Blizzard aimed this at Heroic; worth doing. Raid BoEs at Myth 6/6 are
a gold-for-gear option. Rings at Hero 6/6 are normal even at the top.

### Alt ramp (fresh 90, week 8+)
1. Equip warbound pieces/BoEs from the warband bank; claim renown quest gear.
2. **M0 × 8 daily** (292) — fastest jump, fills the dungeon vault row.
3. Bountiful T8 delves with keys (295), the weekly bounty map (305), Nemesis first kill +
   Cracked Keystone quest (uncapped Hero/Myth crests).
4. **Crest cap is cumulative since Aug 18** → a week-8 alt has ~800 headroom per tier; from Oct 20
   no cap. Supply binds, not the cap. With a warband "of the Mist" achievement, upgrades cost half.
5. Lair (N/H) + LFR fill raid-vault slots cheaply; a Normal/Heroic clear puts Hero/Myth in the vault.
6. Vault → Voidcore → roll a Heroic boss (318). Start Orin's quest chain on the alt (whether an alt
   must wait out its own 8-week timer is unconfirmed).
7. Catalyst charges only accrue while the alt logs in — log in every two weeks even if idle.
8. Crafting: a Spark + Myth-crest craft is 331 deterministic; the alt's spark ledger (Spark
   Dust) catches up.

## 10. Open questions (check before quoting)

1. Venomstone result for weapons/trinkets (341 vs 344) and for a 331 craft — after Oct 20.
2. Whether drops/vault picks remove items from your bonus-roll table; one player report of a
   duplicate S2 roll (2026-09-24).
3. Orin's weekly Voidcore: catch-up for missed weeks? Does a fresh alt wait 8 weeks?
4. LFR vault/roll ilvl; Lair drops per kill and Lair vault ilvl; Kith'ix bonus-roll eligibility.
   **Kith'ix Mythic roll ilvl (checked 2026-10-07):**
   - **Not stated anywhere official.** Checked the 12.1.5 content notes (full article, news
     24304162), the 12.1.5 PTR dev notes, the raid-testing thread (2346119) and the Oct 6
     hotfix thread.
   - **The governing blue rule** (curse-of-ulatek-endgame-reward-changes): Mythic vault =
     Myth 6/6, *except* Very Rare and "penultimate and final bosses" = Myth 9. Voidcore
     items = the vault equivalent. Whether a standalone one-boss raid counts as a "final
     boss" is unaddressed.
   - **12.1.5 PTR data** (`nether.wowhead.com/ptr-2/tooltip/item/<id>`; the PTR-2
     environment, not `/ptr/`, which is still 12.1.0) shows Band of the Swarmcaller 281029,
     Chestwrap of Palpable Terror 281236 and Twisted Horror's Tendril 281215 at **Mythic
     334, Myth 6/6** by default.
   - **Most likely:** Mythic drop 324 (Myth 3/6), Mythic roll 334 (Myth 6/6). Confirm after
     Oct 14 from live tooltips or a WCL gear census of Kith'ix Mythic kills (bonus id 12854
     + Mythic tag 13335).
   - **Also:** the full 12.1.5 article says Orin's Voidcore trades for gold, Voidlight Marl
     **or** Veteran crests. §5 reads all three.
5. M+ crests at +4..+8; Nemesis first-kill crest amount (30+30 vs 60+30); Gilded Stash 4×5 vs 3×7.
6. Catalyst charges per character vs warband (Icy Veins: per character). **Unit of currency
   3465 (seen 2026-10-07):** one Catalyst conversion took Funkitty's addon-export value from
   7 to 6, so 3465 counts whole charges, not fifths. One data point.
7. PvP gear's PvE item level.
8. Live bugs reported but not acknowledged: bonus-roll window not appearing; Voidcore consumed
   with no loot; vault Voidcore option erroring.
