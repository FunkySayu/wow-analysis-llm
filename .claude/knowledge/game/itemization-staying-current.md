# Keeping itemization knowledge current — sources, triggers, verification

Method, not data. How to re-validate [itemization-fundamentals.md](itemization-fundamentals.md),
[itemization-midnight-s2.md](itemization-midnight-s2.md) and
[crafting-midnight-s2.md](crafting-midnight-s2.md) — and how to build the next season's
version — without inheriting stale numbers. Written 2026-10-07 after the first full research
pass (`scratch/itemization/PLAN.md` records how that pass ran and what it got wrong first).

## The rule

**A gearing number without a date and a source is wrong until re-checked.** Itemization changes
on four clocks, and each has bitten this research at least once:

| Clock | Example from Midnight S2 |
|---|---|
| Expansion | Midnight's bonus roll is a different mechanic from the MoP–BfA one sharing the name |
| Season | S1 → S2 changed the vault ilvl rule, crest names, Voidcore supply and cost |
| Mid-season patch / scheduled unlock | Orin's Voidcore (week 8), crest cap lift + Venomstones (week 10) |
| Hotfix | Bonus-roll lockout (week 3), spark cap 4 → 5, Ritual Stone nerf the night before launch |

## Sources, by what they're good for

| Source | Good for | Traps |
|---|---|---|
| **Blizzard blue posts** (forums; Wowhead Blue Tracker — skill [`wowhead-blueposts`](../../skills/wowhead-blueposts/SKILL.md)) | *Rules* and *intent*: the season's reward-change dev notes, "Season N ending / Season N+1 information", the running **Hotfixes thread** (one per season, appended daily), patch content notes with week-by-week unlock calendars | Rarely give full tables; the hotfix thread is long — grep it, don't skim |
| **Warcraft Wiki** (warcraft.wiki.gg `Midnight_Season_N`, currency/item pages) | Complete tables in one place: tracks, crest sources and amounts, crafted ilvls, vault rows, patch-change history per item | Off-by-one ilvls seen (335/322 vs real 334/321); copy-paste leftovers ("Dawncrest" in an S2 table) |
| **Wowhead** guides/news + tooltip API (`nether.wowhead.com/tooltip/item/<id>`, `/currency/`, `/spell/`) | Datamined tooltips (exact current text), news on hotfixes | **Scripted fetches of www.wowhead.com get 403** after ~hundreds of requests; the `nether` tooltip API kept working. Use `/ptr/` for PTR text (see CLAUDE.md trap 1) |
| **Icy Veins / Method** guides | Readable per-feature guides, vault and ilvl charts | Lag hotfixes; Icy Veins S2 guides contained S1 sentences; two sources disagreeing on a number is common — record both |
| **Creators** (SignsOfKelani weekly news; Tettles' Mythic-raider vlogs; Maximum) | What changed this week; how a top raider *decides* (vault vs Voidcore, loot-spec tricks, which slot to craft) — things no database states | Auto-captions mangle names; "I think it's 33%" is not a source. Tag [creator] and cross-check numbers |
| **WarcraftLogs gear of top players** | What the field *actually wears* — the empirical check on every recommendation, and the only way to see hidden tech | A ranking may carry no gear (15.6% of M+ rows); a choice seen early may be a stopgap |
| **Boost-site blogs** (expcarry, wowcarry, altgearer…) | Sometimes the only text stating a number (sparks per item) | Low authority; accept only when corroborated |

## Triggers — when to re-validate what

- **Every weekly reset during a season's first ~10 weeks**: scan the Hotfixes thread and Blue
  Tracker for loot, crest, spark, vault, catalyst, bonus-roll, embellishment changes. Update
  the season file's calendar and open questions.
- **Scheduled unlock dates** listed in the season file's calendar (e.g. 2026-10-13, 2026-10-20):
  after each, resolve the open questions it answers (Venomstone ilvl, crest cap behaviour).
- **Mid-season patch (x.y.5)**: new content often brings a new vector (S2: Kith'ix, Labyrinths)
  — add rows to the acquisition table with ilvl/repeatability/access.
- **New season**: write a **new** season file (`itemization-<expansion>-s<N>.md`); never edit the
  old one into the new — the old file is the record of what changed. Re-read the fundamentals
  file's "patterns" against the new season and update the patterns if one broke.
- **New expansion**: assume every system name may be reused for a different mechanic.
  Re-derive the fundamentals from scratch and diff.

## Verification checklist for any gearing claim

1. **Is it dated, and is the date after the last relevant hotfix?** If the source predates a
   hotfix that touched the system, it's stale.
2. **Rule from a blue, number from data.** Prefer a blue for *what the rule is*, a tooltip or
   wiki table for *the number*, and check the two agree.
3. **Two independent sources for any number used in a recommendation**; if they disagree, put
   both in "open questions" with their sources instead of picking one silently.
4. **Cross-check against measured gear.** If the field doesn't do what a guide recommends,
   one of them is wrong — find out which. And check your *explanation* of a measured pattern
   against the ilvl tables: in this pass the week-1 pile-up of items at exactly Hero 3/6 (311)
   was first attributed to the crest cap, but 311 is precisely the M+ +10 chest cap and the
   Heroic late-boss drop — a source effect, not a cap effect.
5. **Watch for "vault vs drop" and "PvP vs PvE" ilvl confusion** — they differ by design.
6. **When summarising creator transcripts with a small model, spot-check every number against
   the raw transcript.** In this pass, Haiku compressed "each week I bonus roll the turtles I
   effectively save myself 100 crests" into "saves ~100 crests/week" — correct here, but the same
   compression dropped a loot-spec example's key detail (rolling *as Feral* to remove a mace
   from the table). The raw text is the source; the summary is an index into it.

## Grounding in logs — the recipe (measured gear of top players)

WCL `worldData.encounter(id).characterRankings(..., includeCombatantInfo: true)` returns each
ranked player's full gear (item id, ilvl, bonusIDs, gems, enchants) — no per-report calls
needed. `filter: "date.<startMs>.<endMs>"` (undocumented, verified) restricts to a time window,
which makes "week 1–2 vs now" comparisons cheap. ~1 rate-limit point per 100 rankings.

- Decode upgrade track/rank from bonus IDs via wago.tools `ItemBonus` (type 34 = track group,
  52 = crafting quality → crafted, 23 = ItemEffect → embellishment/proc, 16 = bind type,
  37 = season tag). Spot-check each decoded track against a Wowhead tooltip with that bonus.
- Tier set membership is not returned; use `ItemSet`.
- Drop rankings whose gear array is all zeros.
- Sample size: top 100 per (boss/dungeon, spec), several specs, de-duplicated by player — see
  memory note "sample many top logs".
- **Tech vs mistake**: an unusual pick is *tech* if it's common across top players **and**
  persists past the first weeks (Hero-track M+ trinkets on 92% of Arcane mages in week 7); a
  *stopgap* if common early and gone later (previous-season items: 39% → 1%); *noise* if rare.
- Current scripts: `scratch/itemization/wcl_gear/` (`fetch.py`, `flatten.py`, `a_*.py`; dates and
  encounter ids hard-coded, written for WSL paths). **Follow-up worth doing:** promote them into
  `tools/` as a parameterised "gear census" tool (season, encounters, specs, date windows), so
  each re-validation is one command.

## How the first pass was run (reuse the shape)

Six parallel research tracks, each writing a tagged file with an open-questions section:
acquisition vectors, upgrade systems + history, bonus rolls, crafting, creator transcripts,
WCL gear census. Then a reconciliation pass across tracks, resolving conflicts from the
saved primary text rather than from either track's summary (e.g. "does the raid one-track-up
rule apply to drops?" — the blue text says vault only; one track had overstated it). Raw
blues in `scratch/itemization/blueposts/`, guide pages in `scratch/itemization/raw/`,
transcripts in `scratch/itemization/transcripts/`.

Transcripts: `py -m yt_dlp --skip-download --write-auto-subs --sub-langs en --sub-format vtt`
works, but YouTube returns 429 after a burst — pace requests (`--sleep-subtitles`, retries a
minute or more apart). Channel RSS (`youtube.com/feeds/videos.xml?channel_id=…`) lists the latest
15 uploads with dates. Maximum's channel is mostly multi-hour streams; his shorter edited uploads
(blue-post reactions, interview reactions, tier retrospectives) are the podcast-like material.
