---
name: wow-talent-data
description: Pull the full talent tree (class, spec, hero subtrees, apex talent) for any class/spec on live or PTR, straight from Raidbots' static data feed — the same data their talent calculator and simc use. Use whenever the user needs a structured list of talents/spells for a spec, not just a written-up summary.
---

# WoW Talent Tree Data

Raidbots publishes the exact talent-tree data its talent calculator (and the
simc talent-string encoder) runs on, as one static JSON file per game version —
no auth needed.

**Check `data/classes/<class>/<spec>/<patch>_talents.json` first.** Validated trees
(Balance, Feral, Fire, Frost for 12.1) are already built there by
`tools/raidbots/talent_tree_sync.py --class <id> --spec <id> --out <path>` (`--list`
prints the ids; class/spec ids and folder names are in `data/classes/specs.json`). That
tool fetches this same feed, merges tooltip text, splits the hero trees and validates
against `data/classes/talents.schema.json` — use it to add a spec rather than the manual
steps below, which remain the reference for what the feed contains.

**Live or PTR is a per-patch decision, not a default.** Use the `/ptr/` feed and tooltip
path only while the patch you are studying is on the PTR; once it ships, the plain
endpoints are correct and `/ptr/` describes a *future* build.

## The source

```
https://www.raidbots.com/static/data/live/talents.json   — current live patch
https://www.raidbots.com/static/data/ptr/talents.json    — current PTR patch
```

Each is a single ~3.2MB JSON **array of 40 entries**, one per class/spec
combo (`classId`/`specId`/`className`/`specName`/`traitTreeId`), covering
every class and spec in the game — filter to the one you want.

```bash
curl -sL "https://www.raidbots.com/static/data/ptr/talents.json" -o talents_ptr.json
```

Cross-check `meta`/patch banner against [[wow-ptr-research]] before trusting a
PTR pull — this file updates whenever Raidbots re-syncs to a new build, so
re-fetch rather than reuse an old copy if it's been more than a few days.

## Structure of one spec entry

```
classId, classNodes, className, specId, specNodes, specName,
heroNodes, subTreeNodes, pointLevels, fullNodeOrder, traitTreeId
```

- **`classNodes`** — the shared class tree (e.g. all Mage talents regardless
  of spec).
- **`specNodes`** — the spec tree (e.g. Arcane-only talents). The **apex
  talent** (the new 12.1 capstone, one per spec, up to 4 ranks) lives here: it's
  the node with the highest `reqPoints` in the tree, `type: "tiered"`, and its
  entries' `icon` contains `"apextalent"` (a leftover naming convention — the
  icon string doesn't change per-spec even when the talent itself gets
  redesigned, e.g. Arcane's apex icon still reads
  `..._apextalent_mage_touchofthearchmage` even though the talent is now
  "Prismatic Bolt").
- **`heroNodes`** — talents from **both** hero subtrees combined, undifferentiated.
- **`subTreeNodes`** — a single "selector" node whose `entries[]` (one per
  hero subtree, e.g. Spellslinger / Sunfury for Mage) each list which
  `heroNodes` IDs belong to that subtree, via `entries[].nodes[]`. Use this to
  split `heroNodes` back into per-subtree lists.

### Node shape (applies to class/spec/hero nodes alike)

```
id, name, type (single | choice | tiered | subtree), posX, posY,
maxRanks, reqPoints (points needed to unlock, null if none),
entryNode, next[], prev[] (node-id graph edges), entries[]
```

`entries[]` holds the actual talent(s) selectable at that node — one for
`single`/`tiered` nodes, two+ for `choice` nodes (pick-one), one per rank
tier for `tiered` nodes:

```
id, definitionId, spellId, name, icon, type (active|passive|tierrank), maxRanks
```

`spellId` is the real WoW spell ID but this feed carries **no description
text** — only name/icon. For the actual tooltip (damage %, resolved scaling,
flavor text), fetch it separately:

```
https://nether.wowhead.com/ptr/tooltip/spell/<spellId>
```

Returns small JSON: `{"name", "icon", "tooltip": "<html>", ...}`. Strip the
HTML (`<br>` → newline, then drop remaining tags) for plain text.

**Trap:** the same endpoint *without* `/ptr/`
(`nether.wowhead.com/tooltip/spell/<id>`) silently returns the **live**
description instead — for talents that were redesigned on PTR this is just
wrong, not merely outdated. Verified on Orb Mastery (spellId 1243435): the
plain endpoint returns the old live text ("fire 2 additional Arcane Orbs at
**100%** effectiveness... now consumes Clearcasting"), the `/ptr/` endpoint
returns the actual 12.1 PTR text ("fire 2 additional Arcane Orbs at **50%**
effectiveness"). Always use the `/ptr/` path when describing PTR data. One
request per spell ID — for ~130 talent entries that's ~130 sequential curl
calls, a few seconds total, no batching endpoint found.

**Trap — the feed's spell id is not always the id the combat log uses.** The tree's
Incarnation (394013) and Celestial Alignment (395022) are not the cast ids in a log
(102560 / 194223), and an apex's ranks are separate entry ids. Filtering a log on a tree id
can match nothing with no error; resolve log abilities by name.

## Worked example — Arcane Mage, 12.1 PTR (classId 8, specId 62)

The only Arcane tree in the repo is this older raw-format dump (not yet rebuilt with
`talent_tree_sync.py`), saved at
[data/classes/mage/arcane/12_1_ptr_talents_raidbots.json](../../../data/classes/mage/arcane/12_1_ptr_talents_raidbots.json):
43 class-tree nodes, 38 spec-tree nodes (apex talent flagged as `isApex: true`
— currently "Prismatic Bolt"), and both hero subtrees split out
(`heroTrees.Spellslinger`, `heroTrees.Sunfury`, 14 nodes each). Every entry
also has a `description` field (plain text, PTR-correct) merged in from the
tooltip endpoint above — no extra fetching needed to read this file. Re-run
the extraction below any time the PTR build moves and the dump needs
refreshing.

```powershell
$json = Get-Content talents_ptr.json -Raw | ConvertFrom-Json
$spec = $json | Where-Object { $_.classId -eq 8 -and $_.specId -eq 62 }  # Mage/Arcane
# $spec.classNodes / $spec.specNodes / $spec.heroNodes / $spec.subTreeNodes[0].entries
```

To find another class/spec's IDs, list all 40 entries:

```powershell
$json | ForEach-Object { "$($_.classId)/$($_.specId) $($_.className) - $($_.specName)" }
```
