# Building analysis reports

Learnings from producing the Balance Druid 12.1 audit — a published HTML Artifact with
inline spell icons, hover tooltips, Wowhead links and copy-to-clipboard blocks. These are
the things that were *not* obvious and cost real time to discover.

## Build it as template + payload, never by hand

Do not paste generated data into the HTML. Write a template with comment placeholders and
a build script that substitutes them:

```
reports/_audit_template.html      # hand-written, checked in, no data
scratch/<topic>/icons.json        # generated payload
scratch/<topic>/builds_payload.json
scratch/<topic>/apl_payload.json
scratch/.../build_report.ps1      # template + payloads -> reports/<name>.html
```

Placeholders as `/*ICONDATA*/`, `/*APLDATA*/`, `/*BUILDDATA*/` inside a `<script>` block,
replaced with `.Replace()` (a literal replace — **not** `-replace`, which treats the payload
as a regex and mangles `$` and `\`).

This matters because payloads get big (250 KB of base64 icons) and because you will rebuild
the report a dozen times as numbers land. Editing prose in a file that also contains a
250 KB single line is miserable and error-prone.

**Emit payloads with `ConvertTo-Json -Compress`.** Pretty-printed JSON spans many lines,
which breaks line-based validation and inflates the file. Compressed also means each payload
is exactly one line, so `const NAME = {...};` can be validated by reading that one line.

### Always validate after building

Cheap checks that caught real bugs:

- every `data-s="slug"` in the template resolves to a key in the icon map;
- every embedded `const X = …` line parses as JSON;
- no placeholder survives into the output.

Match the const line with a **whitespace-tolerant** regex (`^const\s+NAME\s*=`). Aligning
`const APLS   =` for readability silently broke an exact-match validator.

## Icons and tooltips

**The Artifact CSP blocks every external host**, so icons must be inlined as data URIs.
Source them from `https://wow.zamimg.com/images/wow/icons/medium/<icon>.jpg` — the `icon`
field in the Raidbots talent JSON is exactly this filename. `medium` is 36 px and ~1–2 KB;
147 icons came to 252 KB, comfortably inside the 16 MB page budget.

Cache the fetched bytes to a JSON file on disk. Rebuilds then cost nothing, and you can add
one missing icon without re-fetching 146.

Not every icon name resolves (`inv_misc_astralrune` 404s). Probe candidates with a quick
loop before committing to a name, and give non-talent concepts (a resource, a spell
referenced only in prose) an explicit hand-written entry with its own description.

### Tooltip positioning: anchor to the pointer, not the element

This was a real bug worth remembering. Anchoring a tooltip with
`element.getBoundingClientRect()` fails for inline elements: when an inline element **wraps
across a line break**, its bounding box spans both fragments and is mostly empty space, so
the tooltip appears offset from the text the user is actually hovering.

Track `pointermove` coordinates and position from those, clamped to the viewport, flipping
to the other side when it would overflow. Use `transform: translate(x,y)` rather than
`left/top` so positioning stays on the compositor. Keyboard `focusin` has no pointer, so
fall back to the element rect there — that path does not wrap.

### Make the reference do two jobs

`<a class="sp" data-s="slug">Name</a>` — hover gives the tooltip, click opens Wowhead
(`https://www.wowhead.com/spell=<id>/<slug>`). Build the slug from the name: lowercase,
strip apostrophes, non-alphanumerics to hyphens. Wowhead only needs the ID to be right, so
the slug is cosmetic.

## Copy-to-clipboard

`navigator.clipboard.writeText` can be blocked in a sandboxed frame. Always keep the
fallback: a temporary off-screen `<textarea>`, `select()`, `document.execCommand('copy')`.
Report the outcome on the button itself ("Copied" / "Press ⌘/Ctrl+C") rather than assuming
success.

Anything a reader will paste elsewhere — import strings, action lists, profile snippets —
should have a copy button rather than being something they select by hand.

## Toolchain traps that cost time

**PowerShell + native executables**

- Never `2>&1` a native exe. Windows PowerShell wraps each stderr line in an ErrorRecord,
  raising `NativeCommandError` and setting a failure exit code even when the program
  returned 0. simc writes routine "Trivial:" notices to stderr, so this fired constantly.
  Just don't redirect; stderr is captured for you.
- **Keep non-ASCII out of PowerShell string literals.** Minus signs (`−`), em dashes and
  typographic apostrophes in prose broke the parser after an encoding round-trip, producing
  a cascade of misleading "The '<' operator is reserved" errors. Fix: put prose in a JSON
  file written with the `Write` tool, and let PowerShell merge only numbers into it. This
  also makes the narrative diffable.

**Shell**

- `grep -c` exits 1 when it finds nothing, so `cmd && grep -c ...` reports failure for a
  command that succeeded. A background task was flagged failed this way when the sim was
  fine.
- **Appending a UTF-8-with-BOM file to another file injects a BOM mid-stream.** simc
  silently skipped the profileset whose line began with the BOM — no error, just a missing
  result. Strip with `sed '1s/^\xef\xbb\xbf//'` or write with `-Encoding ascii`.

## Structure the report around the reader's decision

Organise by the axis the reader chooses on, not by the order the experiments ran. The
Balance report only became useful when it was split into **Patchwerk (1 target)** and
**Council (3–5 targets)** sections, because the answer genuinely inverts between them — the
same build is 1st of 20 in one and 20th of 20 in the other. A single merged ranking hid
that completely.

Other things that earned their place:

- **Give retracted results their own visible section.** Four results in this audit flipped
  sign once loadout legality was enforced. Deleting them quietly would have destroyed the
  reader's ability to check the work; a "Retracted" table with the bad value, the true
  value, and the rule violated is more trustworthy than a clean report.
- **Status chips encode something true.** Verified / Retracted / No-change-warranted worked
  because the report's spine genuinely *was* evidential status. Don't add numbered markers
  or eyebrows that merely decorate.
- **Every number carries its uncertainty.** Report a 95% CI on the *difference* of two
  means, `1.96·√(σ²₁+σ²₂)`, and say "not significant" rather than presenting a small
  in-noise delta as a gain.
- **Verify implausibly large deltas before writing them down.** A −91% result was an actor
  idling 97% of the fight, not a talent value. One cheap diagnostic run separated the two.
  Anything above roughly 10% deserves a sanity check aimed at *how* it happened.
- **Benchmark cards beat prose for comparable options.** Name, icon row, per-scenario
  numbers, then Core focus / Key synergy / Rotation note in fixed slots. Fixed slots make
  five options genuinely comparable in a way five paragraphs never are.

## Theme and layout (Artifact specifics)

Define the complete light palette on bare `:root`; redefine only the tokens under
`@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and
again under `:root[data-theme="dark"]`. Never let a colour's only definition live inside a
media or `[data-theme]` block. Give `body` an explicit token background — a transparent body
borrows the host's ground and produces the classic unreadable page.

Wide content (tables, action lists) goes in its own `overflow-x: auto` container so the page
body never scrolls sideways. Use `font-variant-numeric: tabular-nums` on every column of
digits.

## Republishing

Publishing the same `file_path` again in the same conversation updates in place and keeps
the URL. From a different conversation, pass the artifact's `url` explicitly — publishing
without it creates a second artifact instead. Keep the `<title>` and favicon stable across
redeploys; readers find the tab by its icon.

## Boss abilities, not just talents (added 2026-08-19)

The talent JSON only covers your own spec. For a raid report you also need **boss**
abilities, and there is a much better source than typing spell IDs out of a guide:

- **Get IDs and icon filenames from the logs.** WCL's `raidDamageTakenByAbility` entries
  carry `name`, `guid` and `abilityIcon` for exactly the abilities you are quoting numbers
  for. Several IDs in written guides were stale — the log IDs are what actually fired.
  Watch the regex: `Environment` abilities have `"actor":-1`, so a `[0-9]+` pattern
  silently drops them (that is how the largest intake on one boss went missing).
- **`nether.wowhead.com/tooltip/spell/<id>` serves fully tuned damage values.** The
  *database* page (`/spell=<id>`) does not, and two independent research passes concluded
  from that that no damage numbers existed for the tier at all. They do — on the tooltip
  endpoint. Description text is the last `<div class="q">…</div>`; unescape `\/`, `\"`,
  `&nbsp;` and turn `<br />` into newlines.

### Two payloads beat one merged map

Keying everything by slug forces you to resolve name collisions (two different
`Corpse Blight` IDs). Instead keep them separate and let the page resolve:
`DRUID` (slug-keyed, data-URI icons already inlined) and `BOSS` (id-keyed) plus `BICONS`
(icon-name → base64). A `resolve(key)` helper tries slug then id, so markup reads
`data-s="fury-of-elune"` or `data-s="1307367"` interchangeably. Add an `OVERRIDE` map for
the handful whose live tooltip is wrong for your context — Barkskin's tooltip leads with
the *Guardian* version.

### Let the markup carry only the key

Write `<a class="sp" data-s="1289855"></a>` with **no text** and let JS fill in icon + name
from the payload. Names then cannot drift from the data, and a missing key is visible
(render it in the error colour and `console.warn` a count) instead of silently showing a
name with no tooltip. Validate in the build script too: extract every `data-s` and assert
it exists in one of the payloads — that caught real typos.

### Injecting per-section blocks

When each card needs its own generated block, keep the blocks in one file delimited by
`@@key` and inject with awk tracking the current `data-b`. Print an `UNUSED PLAN: <key>`
warning at END — a typo'd key otherwise just silently produces a card with no block.
