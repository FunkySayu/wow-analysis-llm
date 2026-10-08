---
name: wow-ptr-research
description: Find out what changed for a class/spec on the current WoW PTR — exact ability tooltips/values, official dev commentary, and whether simulationcraft (and therefore Raidbots) has actually caught up to the current PTR build yet. Use when explaining a benchmark gap or looking up current PTR tuning.
---

# WoW PTR Class/Ability Research

As of 2026-10-08, live is **patch 12.1.0** (expansion "Midnight", Season 2, live since
2026-08-11) and **12.1.5** is on the PTR, shipping 2026-10-13. Patch numbers move fast —
always confirm the current patch banner on the source before trusting a cached number.

## Confirm which PTR build you're looking at

Wowhead runs two PTR environments, `/ptr` and `/ptr-2`, and **which one holds the newest
build is not fixed** — check each banner. During the 12.0.7 → 12.1 cycle `/ptr` was the
newer one; on 2026-10-07 the 12.1.5 data was on **`/ptr-2`** while `/ptr` still served
12.1.0 (`nether.wowhead.com/ptr-2/tooltip/item/<id>` returned 12.1.5 items). The tooltip
API follows the same split: a request to the wrong environment returns a plausible tooltip
for the wrong build, with no error.

## Sources, roughly in the order to reach for them

0. **Structured talent/spell data** — see [[wow-talent-data]] for pulling a
   full class/spec talent tree (including hero and apex talents) as JSON
   directly from Raidbots' static data feed, rather than reading it off a
   calculator page by hand.
1. **Wowhead PTR database** — https://www.wowhead.com/ptr/database — exact,
   datamined tooltip text and coefficients from the current build. First stop
   for "what does this ability actually do right now".
2. **Wowhead PTR news** — https://www.wowhead.com/ptr/news — digested
   changelogs, tuning-pass roundups, and class tier lists
   (https://www.wowhead.com/ptr/guides/classes/tier-lists) for community power
   ranking.
3. **Blue Tracker, PTR category** — https://www.bluetracker.gg/wow/category/4-ptr/
   — verbatim official Blizzard developer posts. This is the source for *why*
   a number changed (intentional early-pass under-tuning vs. an acknowledged
   bug), not just *that* it changed.
4. **wago.tools build diff** — https://wago.tools/builds-diff — raw DB2/spell
   data diff between two specific build numbers. Use this when a change hasn't
   been written up anywhere yet, or you need the precise before/after values.
5. **simulationcraft on GitHub** — https://github.com/simulationcraft/simc —
   issues, commits, and the wiki (e.g. `wiki/Mages`) tell you whether **the
   simulator itself** has implemented a given PTR change yet. This step is the
   one most specific to benchmarking: if simc hasn't picked up a recent PTR
   spell-data change, a Raidbots number ([[raidbots-reports]]) is silently
   simulating the *old* mechanics, and a "bad benchmark" may just be a stale
   sim rather than a rotation problem. Cross-check `build_date`/`git_revision`
   from a Raidbots `data.json` against recent simc commits for your spec.
6. **http://ptr.simulationcraft.org/** — a standalone SimC build pointed at
   PTR data, useful for running your own sim independent of Raidbots if you
   suspect the Raidbots-side build is lagging.
7. **Icy Veins guides** (e.g. https://www.icy-veins.com/wow/arcane-mage-pve-dps-guide)
   — good for baseline live rotation logic, but guides are usually still
   written for the live patch while a PTR is active — don't treat them as
   PTR-current.

For official commentary beyond the PTR category, [[wowhead-blueposts]] dumps full post
text locally. For gearing systems specifically (loot, crests, bonus rolls, crafting),
`.claude/knowledge/game/itemization-staying-current.md` lists the sources and their traps.

## Suggested workflow when a benchmark looks off

1. Pull `build_date`/`git_revision` from the Raidbots `data.json`
   ([[raidbots-reports]]) and check simc's recent commit history (source 5) for
   your spec — is the sim actually current for this PTR build?
2. Look up the exact ability values on the Wowhead PTR database (1) or a
   wago.tools diff (4) to confirm what the current numbers really are.
3. Check Blue Tracker (3) for developer commentary — sometimes a spec is
   deliberately under-tuned early in a PTR cycle and the "gap" is expected.
