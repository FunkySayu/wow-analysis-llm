---
name: keystoneloot-favorites
description: Decode a KeystoneLoot addon (in-game WoW gear favorites tracker) export string into structured item data — item names, icons, tooltips, drop sources — and turn it into a self-contained JS data module an HTML Artifact can embed directly. Covers both a flat favorites list and a full per-dungeon/raid loot table (every item a spec can use, favorites marked by tier). Use whenever the user pastes a "KeystoneLoot:v3,..." export string, or wants to build a report/artifact around their favorited gear list.
---

# KeystoneLoot Favorites Pipeline

[KeystoneLoot](https://www.curseforge.com/wow/addons/keystoneloot) is a WoW addon
(installed at `E:\World of Warcraft\_retail_\Interface\AddOns\KeystoneLoot`) for tracking
which Mythic+/raid items are worth grabbing per spec, tiered Nice-to-have / Must-have /
Best-in-Slot / Transmog / Catalyst. It can export a character's favorites as one compact
string. This skill covers turning that string into real item data (name, icon, tooltip,
drop source) and packaging it as something an HTML Artifact can embed with zero external
fetches — either a flat favorites list, or a full "here's everything this spec can get from
each dungeon/raid boss, with my picks marked" table.

Four scripts in `scripts/`. The first two are shared; then pick a branch depending on
whether you want a flat list or a full per-zone table:

```
export string --[parse_export.pl]--> favorites.json (spec/tier/itemId)
item IDs ------[fetch_item_info.pl]--> data/items/12_1/items.json (cached, durable)

  flat list:  favorites.json + items.json --[build_favorites_js.pl]--> KEYSTONE_LOOT_FAVORITES
  full table: [extract_source_data.pl]--> data/classes/<class>/<spec>/12_1_loot_sources.json (zone -> item pool)
              sources.json + favorites.json + items.json
                --[build_zone_table_js.pl]--> KEYSTONE_LOOT_ZONES
```

All four are plain Perl using only core modules plus `Compress::Zlib`, `MIME::Base64`,
`JSON::PP` — all present in the Perl bundled with Git for Windows, the same interpreter
`.claude/skills/wowhead-blueposts` already relies on. **They shell out to `curl` for HTTP,
not `LWP::UserAgent`** — this environment's Perl has no `LWP::Protocol::https`, so any
`https://` GET through LWP fails with "protocol scheme not supported"; curl handles TLS
natively and is already this project's standard fetch tool.

The worked example behind both branches is the "Arcane Loot Ledger" artifact — a
per-dungeon/raid loot table (`extract_source_data.pl` → `build_zone_table_js.pl` branch),
built from Funkysayu's real Arcane Mage export. An earlier flat-list revision of the same
artifact (`build_favorites_js.pl` branch, tier-grouped cards instead of a table) is what
first exercised the shared steps — both are legitimate outputs; pick based on whether the
user wants "my favorites" or "everything, with my favorites marked."

## Step 1 — decode the export string

```bash
perl tools/keystoneloot/parse_export.pl "KeystoneLoot:v3,<data>" \
  > scratch/keystoneloot_favorites.json
```

**Format** (from the addon's own `modules/favorites.lua`, function `Export`):

```
KeystoneLoot:v3,<base64( zlib( json ) )>
json = { "<specId>": [ {itemId, tier, bonusIds?, gems?, enchant?}, ... ], ... }
```

`tier` is 1-5: **1=Nice to have, 2=Must have, 3=Best in Slot, 4=Transmog, 5=Catalyst**
(`Favorites.TIER_NAME` in the addon source — don't guess this mapping, it's not the
obvious ascending-priority order you'd assume: BiS is 3, not the max value 5, because
Transmog/Catalyst were tacked on later). The addon also has v1 and v2 export formats
(colon-delimited, no compression) still recognized by the addon for backward compatibility,
but every current export is v3; `parse_export.pl` only handles v3 and errors clearly on the
others rather than guessing.

**The export string does NOT say which dungeon/raid/boss an item drops from.**
`Favorites:Export()` flattens across `sourceId` entirely — it only keeps `specId` and
`itemId`. If a report needs "which zone is this item from," that has to come from a
separate lookup (`extract_source_data.pl`, step 3 below), not from anything in this string.

Only Perl's `Compress::Zlib::uncompress()` was verified against a real export string here —
it expects zlib-wrapped data (2-byte header + deflate + Adler32 trailer), which is exactly
what WoW's `C_EncodingUtil.CompressString(..., Enum.CompressionMethod.Zlib)` produces. A
plain `zlib.decompress()` in Python or Node's `zlib.inflateSync()` would also work if Perl
isn't available; raw `DeflateStream` (as in .NET Framework, which has no `ZLibStream`)
needs the 2-byte header and 4-byte trailer stripped first — confirmed working via
PowerShell during this skill's development, kept here as a fallback:

```powershell
$bytes = [Convert]::FromBase64String($b64Payload)
$raw = $bytes[2..($bytes.Length-5)]   # strip zlib header + Adler32 trailer
$ds = New-Object System.IO.Compression.DeflateStream(
  (New-Object System.IO.MemoryStream(,$raw)), [System.IO.Compression.CompressionMode]::Decompress)
(New-Object System.IO.StreamReader($ds)).ReadToEnd()
```

Output is grouped by specId with a friendly `specName` (spec-ID table is hardcoded in the
script — WoW spec IDs are stable across expansions) and items sorted tier-then-itemId.

## Step 2 — fetch item info from Wowhead

```bash
perl tools/keystoneloot/fetch_item_info.pl 251190 193763 250224
# or pull every itemId out of step 1's output and pipe them in:
grep -o '"itemId" *: *[0-9]*' scratch/keystoneloot_favorites.json | grep -o '[0-9]*' \
  | perl tools/keystoneloot/fetch_item_info.pl
```

Hits the same tooltip-JSON endpoint family documented in `wow-talent-data`'s SKILL.md for
spells, but for items:

```
https://nether.wowhead.com/tooltip/item/<itemId>
```

Returns `{"name", "quality", "icon", "tooltip": "<html>", "spells":[...]}`. The script
regex-extracts item level, slot, a difficulty tag (Mythic/Mythic+), and every
`whtt-extra whtt-<kind>` line from the tooltip HTML (`droppedby`, `dropchance`, `soldby`,
`containedin`, whichever apply — collected generically rather than special-cased per kind,
since which ones appear depends entirely on the item's source). It also fetches the icon
image itself (`.../icons/medium/<icon>.jpg`, ~1-2 KB) and stores it **base64-encoded as a
`data:` URI** — an HTML Artifact's CSP blocks every external image host, so a plain
`iconUrl` is useless inside one; only `iconDataUri` will actually render there (see
`.claude/knowledge/method/building-reports.md`, "Icons and tooltips", for why this project always
inlines icons rather than linking them).

Results upsert into **`data/items/12_1/items.json`** (durable, itemId-keyed, shared across every
future report — not `scratch/`, since an item's tooltip doesn't change per-report the way a
parsed favorites list does). Already-cached items are skipped on re-run; pass `--force` to
refetch. Fetching one dungeon+raid tier's worth of items for one spec (137 Mage-usable
items in the Season 2 pool, ~460 KB of cached JSON incl. icons) took under two minutes of
sequential curl calls — fine to just run and wait, no need to background it. No PTR variant
of this endpoint was found/tested for items (unlike the confirmed `/ptr/tooltip/spell/<id>`
split for spells) — current Mythic+ season gear is live-only anyway, so this hasn't
mattered yet; if a future PTR-only item is needed, verify content before trusting it, same
rule as everywhere else in this project.

## Branch A — flat favorites list

```bash
perl tools/keystoneloot/build_favorites_js.pl \
  scratch/keystoneloot_favorites.json > data/classes/<class>/<spec>/12_1_keystoneloot_favorites.js
```

Merges favorites (spec/tier/itemId) with item info (name/icon/source/tooltip) into one
`const KEYSTONE_LOOT_FAVORITES = {...};` line: `{"<specId>": {specId, specName, items:[...]}}`,
items sorted tier-then-slot. Only ever lists items the user actually favorited.

## Branch B — full per-zone loot table

Use this when the ask is "show me everything, with my picks marked" rather than just "show
me my picks" — e.g. a table with one row per dungeon/raid boss.

### Step 3 — resolve which zone each item belongs to

```bash
perl tools/keystoneloot/extract_source_data.pl 8 62   # classId, specId
```

Parses the addon's own bundled loot databases directly — `data/dungeons.lua`
(`challengeModeId` + flat `lootTable`), `data/raids.lua` (nested `journalInstanceId` →
`bossList[].bossId` + per-difficulty `lootTable`), and `data/items.lua`
(`ItemDatabase[itemId].classes[classId] = [specId, ...]`, plus `slotId`) — reproducing
exactly what the addon's own `Query:GetItemSource()` does at runtime (check catalyst DB,
then scan every dungeon's loot table, then every raid boss's), but offline and for every
item in the pool at once rather than one itemId at a time.

Filters to only the items the given class **and spec** can equip (`classes[8]` containing
`62`, not just `classes[8]` existing — some items are usable by only 1-2 of a class's 3
specs, e.g. `{62, 63}` without 64). Writes `data/classes/<class>/<spec>/12_1_loot_sources.json` (directory from `data/classes/specs.json`):

```
{ classId, specId,
  zones: [ { type: "dungeon"|"raid", key, zoneName, bossName?,
             items: [ {itemId, slotId}, ... ] }, ... ] }
```

`slotId` is the addon's own numeric equip-slot code (0=Head..13=Trinket,14=Other — see
`favorites.lua`'s `EQUIP_LOC_SLOT`), carried through so a later sort can use canonical
in-game slot order instead of alphabetizing Wowhead's English slot text.

**Zone/boss display names are not in the addon's data files.** `dungeons.lua`/`raids.lua`
only carry a `--[[name = "..."]]` Lua *comment*, auto-generated in whatever locale the
addon author's client happened to be running (German, in the copy this was built against —
e.g. `"Rubinlebensbecken"` for Ruby Life Pools). The script instead hardcodes English names
in `%DUNGEON_NAME`/`%RAID_ZONE_NAME`/`%BOSS_NAME`, verified by translating each German
comment and cross-checking against this project's own prior research: the 8-dungeon Season
2 pool in `.claude/knowledge/dungeons/12_1/midnight-s2-dungeons.md` and the 8-boss Venomous Abyss roster
(plus the Tidebound Grotto Lair boss, Nymrissa Wavecaller) in
`.claude/knowledge/raid/12_1/venomous_abyss/venomous-abyss-12.1.md`. **If KeystoneLoot ships a new season, this table
goes stale silently** — it will resolve to "Unknown dungeon/boss/raid `<id>`" rather than
erroring, which is your signal to re-verify and update the hardcoded names by hand.

### Step 4 — build the zone-table JS module

```bash
perl tools/keystoneloot/build_zone_table_js.pl \
  scratch/keystoneloot_favorites.json > data/classes/<class>/<spec>/12_1_keystoneloot_zones.js
```

Merges `data/classes/<class>/<spec>/12_1_loot_sources.json` (zone → item pool, for the favorites' spec; override with `LOOT_SOURCES=<path>`) with `data/items/12_1/items.json` (item
info) and the parsed favorites (item → tier), into `const KEYSTONE_LOOT_ZONES = {...};`.
Every item in every zone appears — favorited or not — with an `importance` field
(`"bis"|"must"|"nice"|"none"`) and `importanceRank` (0-3) resolved from tier the same way
`build_favorites_js.pl` does, and each zone's `items` array is **pre-sorted
importance-first, then by canonical slot order** — the exact read order a "what matters
here" table wants, computed once at build time rather than by a renderer that has to know
the tier-number gotcha below.

Both branches produce **compact single-line JSON** (this project's convention for large
generated payloads per `building-reports.md`: keeps a `^const\s+NAME\s*=` regex trivially
matchable and avoids a multi-hundred-line indented blob in a file nothing hand-edits), and
both flag an item present upstream but missing from `data/items/12_1/items.json` (fetch step skipped
or failed) rather than silently dropping it — a forgotten fetch should be visible in the
rendered output, not swallowed.

## Building an artifact around it

Follow the general pattern in `.claude/knowledge/method/building-reports.md` (template + payload,
literal `.Replace()`/`index()` substitution — never regex-replace a payload containing `$`
or `\`, and never hand-paste generated data into prose). Concretely, for this pipeline:

1. Hand-write an HTML template with a `/*ZONEDATA*/` (or `/*FAVORITESDATA*/` for Branch A)
   placeholder inside a `<script>` tag, plus a second `<script>` that reads the payload and
   renders. See `scratch/keystoneloot_favorites_demo/template.html`, this skill's own
   worked example (built into the "Arcane Loot Ledger" artifact) for a full reference
   implementation of the Branch B table: a toolbar (a coarse **category** select — All /
   Dungeons / Raid, filtering on `zone.type` rather than listing all 17 individual
   encounters, which reads as noise once there's a raid with one row per boss — plus a slot
   select and search bar, both built from the data itself), one row per zone with a
   wrapping icon strip, a small corner badge per favorited item (heart=Best in Slot,
   star=Must have, thumbs-up=Nice to have — an unfavorited item gets no badge and a
   dimmed/desaturated icon so its lower priority reads at a glance), and a pointer-tracked
   tooltip rendering the item's real `tooltipHtml`. That `scratch/` copy is a working
   extract tied to this one build, not a durable template — copy from it rather than
   pointing future reports at that exact path.
   - **For a raid row, lead with the boss, not the raid.** The boss (and its position in
     the fight) is what a reader scanning the table actually needs; the raid name is
     context. Compute `primary = zone.bossName || zone.zoneName` and
     `secondary = zone.bossName ? zone.zoneName : null`, and render `primary` in the bold
     slot, `secondary` (if any) underneath — a dungeon row has no boss, so it falls back to
     the zone name as primary with nothing underneath.
2. Inject with a literal (non-regex) substitution — a short Perl one-liner using `index()` +
   `substr()` works well and matches this project's Perl toolchain:
   ```perl
   my $idx = index($template, $marker);
   substr($template, $idx, length($marker)) = $payload;
   ```
3. **Validate before publishing**: the placeholder string must not survive into the built
   file, and the `const NAME = ...;` line must parse standalone as JSON (strip the
   `const NAME = ` / trailing `;` and run it through a JSON decoder) — both checks are cheap
   and both have caught real bugs in this project before.
4. Rendering the tooltip: the raw `tooltipHtml` field is genuine Wowhead tooltip markup
   (nested `<table>`s purely for layout, `q0`-`q5` classes for quality-colored text,
   `whtt-sellprice`/`whtt-extra` divs, occasional `<a href="/item=...">` with a
   **root-relative** href that needs `https://www.wowhead.com` prepended before it's
   useful outside Wowhead's own site). Style it as a small fixed-palette component — WoW
   tooltips are always dark regardless of any surrounding page theme, so this is one of the
   rare cases where hardcoding colors instead of theming them is the *correct* call, not a
   theming bug (see `artifact-design` skill's carve-out for a deliberately single-look
   component).

## Gotchas specific to this pipeline

- **`--replace` / `-replace` in PowerShell treats the RHS as a regex** and mangles a
  base64-with-`+`/`/` payload or any `$`-containing generated JS — use literal string
  replace (`.Replace()` in PowerShell, `index()`/`substr()` in Perl) exactly as the general
  report-building notes already say.
- **LWP has no HTTPS here.** Don't reach for `LWP::UserAgent->new->get('https://...')` in
  this environment — it fails silently-ish with a clear but easy-to-miss "protocol scheme
  'https' is not supported" 501. Shell out to `curl -sL` instead (see `http_get()` in
  `fetch_item_info.pl` for the pattern).
- **Tier numbers are not priority-ordered.** 3 (Best in Slot) outranks 2 (Must have) which
  outranks 1 (Nice to have); 4 and 5 (Transmog, Catalyst) are unrelated axes bolted on
  after, not "higher than BiS." Both build scripts map tier to an explicit importance
  rank/code rather than sorting on the raw integer — do the same in any new renderer.
- **v3 is base64+zlib+JSON; v1/v2 are plain delimited strings with no compression.** If a
  user pastes an older export (rare, but the addon still round-trips them), `parse_export.pl`
  will report which prefix it saw and refuse rather than mis-decode it as v3.
- **A raid boss's `{ --[[name = ...` comment is indistinguishable from a raid's own, except
  by indentation.** `raids.lua` nests `bossList[].{ --[[name = "Boss",]] ... }` entries
  inside a `{ --[[name = "Raid",]] ... }` block using the *identical* comment shape at both
  levels (4-space indent for the raid, 12-space for each boss inside it) —
  `extract_source_data.pl` anchors its block split to exactly 4 leading spaces
  (`/(?=\n {4}\{\s*--\[\[name = )/`) for this reason; splitting on the comment alone shreds
  every boss out of its parent raid.
- **`classes[classId]` existing is not the same as the item being usable by this spec.**
  Some entries list only a subset of a class's specs, e.g. `[8] = { 62, 63 }` (no 64) — grep
  for the classId key alone and you'll over-include items the target spec can't actually
  equip. `extract_source_data.pl` splits the spec list and checks membership explicitly.
