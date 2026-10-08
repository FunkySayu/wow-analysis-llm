# wcl-viz — the presentation layer for `tools/warcraftlogs` checks

Checks keep their terminal output: that text is what a session actually reads when
analysing a log, and nothing here replaces it. This package is the *second* surface —
the same findings as React components, for when a report is being written for a person
rather than for an agent.

The two never disagree, because they are the same numbers:

```
                    ┌─ json()  ──▶ envelope ──▶ tools/reporting component ──▶ report HTML
Check(report) ──────┤
                    └─ print() ──▶ terminal text   (reads json(), nothing else)
```

## Every payload is per-pull

A check computes `fight_json(fight)` for one pull and the base class maps it, so a
component always receives the same envelope shape:

```ts
{ scope: "fight",
  params:  { gcd: 1.5 },                        // check constants, not measurements
  fights:  [{ fight: FightRef, data: T }, ...], // one entry per pull
  overall: T | null }                           // combine(), or null
```

Render `overall` as the resting state and offer `<PullPicker>` for the drill-down — that
is how the analysis actually goes: aggregate to find the outlier, then open that pull.
`abc` is the exception and has no picker, because its cross-pull comparison *is* its
content.

Where a check infers something per pull that might disagree across the selection (a hero
tree, a target count), Python rolls it up with `check.consensus()` and the component
renders it through `<ConsensusValue>`, which prints "varies" plus the split rather than
showing the majority reading as fact.

## The pairing key

A check's `id` is the CLI name, the key in the JSON envelope, and the key its component
registers under. One string, so the two sides cannot drift:

```python
# tools/warcraftlogs/checks/common.py
class AbcCheck(C.Check):
    id = "abc"
```
```tsx
// tools/reporting/src/registry.ts
["abc", Abc],
```

A check with **no** component is not an error — `mount.tsx` renders its raw payload with
a note. Porting a check to `Check` makes it appear in reports immediately; writing the
component is an upgrade, not a prerequisite.

## Building a report

```bash
# 1. numbers  (a group name works too: common / mage / druid)
wsl.exe -d Ubuntu -e python3 tools/warcraftlogs/run.py mage -r <REPORT> -a <ACTOR> -f raid \
    --json -o scratch/viz/mage.json

# 2. bundle   (only when a component changed)
cd tools/reporting && npm install && npm run build

# 3. page
wsl.exe -d Ubuntu -e python3 tools/reporting/build_report.py scratch/viz/mage.json \
    -o reports/arcane_audit.html --title "Arcane Mage audit"
```

The output is one self-contained file: template (`reports/_checks_template.html`) +
bundle + payload, all inlined. It opens in a browser as-is and is shaped as an Artifact
fragment (no doctype/`<head>`), matching this project's other report templates.

`build_report.py` validates what it wrote — no placeholder survived, the embedded payload
round-trips through `json.loads`, the bundle defines `WCLViz`, and no unescaped
`</script` slipped in. Each of those guards a failure that produces a page which *opens
fine* and is wrong.

## Iterating on a component

```bash
wsl.exe -d Ubuntu -e python3 tools/warcraftlogs/run.py common -r <REPORT> -a <ACTOR> -f raid \
    --json -o tools/reporting/payload.json
cd tools/reporting && npm run dev
```

`payload.json` is gitignored. `?p=<url>` loads a different one.

## Layout

```
tools/reporting/
  src/types.ts          the wire format - mirrors tools/warcraftlogs/lib/check.py
  src/theme.ts          every style in the bundle, as an injected string (see below)
  src/primitives/       Card, Stats, BarList, StackedBar, Table, VerdictChip, Tooltip
  src/checks/<id>.tsx   one component per check id
  src/registry.ts       id -> component
  src/mount.tsx         window.WCLViz.render(el, payload)
  build_report.py       template + bundle + payload -> reports/<name>.html
```

## Things that are the way they are for a reason

**Styles live in `theme.ts` as a string, not in `.css` files.** Vite's library build emits
CSS as a separate asset. A report must be one file, so a stylesheet it never loads would
mean an unstyled page with no error at all.

**React is bundled, not externalised, and nothing is fetched at runtime.** A published
report runs under the Artifact CSP, which blocks every external host *silently*.

**`build_report.py` is Python, not PowerShell.** The PowerShell build scripts it replaces
had to remember `.Replace()` over `-replace`, which treats the payload as a regex and
mangles every `$` and `\` in a 160 KB bundle
([building-reports.md](../../.claude/knowledge/method/building-reports.md)).

**Tooltips anchor to the pointer, not to the element.** An inline element that wraps
across two lines has a bounding rect spanning both, so an element-anchored tooltip lands
nowhere near the mark — a bug this project already paid for once.

**Colour follows the `dataviz` skill and is validated, not eyeballed.** Two families,
never mixed: the violet **ordinal ramp** for the mana bands (ordered magnitude — passes
`validate_palette.js --ordinal` in both light and dark), and the reserved **status**
palette for verdicts. `PERFECT` and `GOOD` share the good hue at different fill weights
because they mean the same state; every verdict carries a glyph *and* the word, so none
of them is ever colour-alone. Every chart has a table beside it.

## Adding a component

1. Port the check to a `Check` subclass with a stable `id` (see
   [tools/warcraftlogs/README.md](../warcraftlogs/README.md) § Adding a check) and confirm `--json` emits
   what you expect.
2. Add `src/checks/<id>.tsx` exporting a `CheckComponent<YourData>`, with the payload's
   TypeScript interface declared in that file. Build it from `../primitives`; a component
   should not be setting colours or radii itself.
3. Register it in `src/registry.ts` under the same id.
4. `npm run build`, rebuild a report, **and open it** — the palette validator checks
   colour, not layout.
