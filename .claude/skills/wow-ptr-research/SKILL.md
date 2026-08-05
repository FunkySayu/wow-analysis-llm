---
name: wow-ptr-research
description: Find out what changed for a class/spec on the current WoW PTR — exact ability tooltips/values, official dev commentary, and whether simulationcraft (and therefore Raidbots) has actually caught up to the current PTR build yet. Use when explaining a benchmark gap or looking up current PTR tuning.
---

# WoW PTR Class/Ability Research

As of writing, live is patch 12.0.7 and the active PTR is **patch 12.1**
(expansion "Midnight"). Patch numbers move fast during a PTR cycle — always
confirm the current patch banner on the source before trusting a cached number.

## Confirm which PTR build you're looking at

Wowhead reuses the `/ptr` subdomain for whichever cycle is *currently* active
and demotes the previous one to `/ptr-2` (e.g. right now `wowhead.com/ptr` =
12.1, `wowhead.com/ptr-2` = the older 12.0.7 PTR). Check
https://www.wowhead.com/ptr for the current patch banner before using either
domain.

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
   written for the previous patch (currently 12.0.7) while PTR (12.1) is
   active — don't treat them as PTR-current.

## Suggested workflow when a benchmark looks off

1. Pull `build_date`/`git_revision` from the Raidbots `data.json`
   ([[raidbots-reports]]) and check simc's recent commit history (source 5) for
   your spec — is the sim actually current for this PTR build?
2. Look up the exact ability values on the Wowhead PTR database (1) or a
   wago.tools diff (4) to confirm what the current numbers really are.
3. Check Blue Tracker (3) for developer commentary — sometimes a spec is
   deliberately under-tuned early in a PTR cycle and the "gap" is expected.
