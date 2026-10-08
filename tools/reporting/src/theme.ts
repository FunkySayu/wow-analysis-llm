/**
 * All styling for the bundle, as a string this module injects once.
 *
 * Why a string and not a .css file: Vite's library build emits CSS as a separate
 * asset, and a report has to be ONE file (the Artifact CSP blocks every external
 * host, and build_report.py inlines a single bundle). A stylesheet the page never
 * loads fails silently - an unstyled report, no error - so the styles travel
 * inside the JS.
 *
 * Token names and roles follow this project's existing report templates
 * (reports/_audit_template.html, _s2_utility_template.html): ground / surface /
 * ink / rule / accent, a per-subject accent hue, and the Fraunces + Source Sans 3
 * + IBM Plex Mono pairing. The report template loads those faces from Google
 * Fonts - the one font host the Artifact CSP admits - and every family here
 * declares a real fallback so the page degrades rather than silently reflows.
 *
 * Three colour families, three jobs, never mixed:
 *
 *   --ground/--surface/--ink/--rule   page chrome
 *   --accent                          one hue, spent on chrome accents only
 *   --ramp-1..5                       ORDERED magnitude (the mana bands). A
 *                                     single violet hue drawn from the accent,
 *                                     light -> dark; passes
 *                                     `validate_palette.js --ordinal` against
 *                                     both surfaces (light end 2.03:1 on #FFFFFF,
 *                                     2.75:1 on #171622; hue spread 8deg / 7deg).
 *   --status-good/-warning/-critical  reserved for verdicts, never for a series.
 *                                     `--status-warning` sits under 3:1 on the
 *                                     light surface by design; every use pairs it
 *                                     with a glyph AND the word, and every chart
 *                                     has a table beside it, which is the
 *                                     documented mitigation.
 *
 * Dark values are declared under both the OS media query and the `[data-theme]`
 * scope so a viewer's explicit toggle wins in either direction, and every token
 * is defined in the bare `:root`-equivalent block first.
 */

const LIGHT = `
  color-scheme: light;
  --ground: #f4f2f9;
  --surface: #ffffff;
  --surface-2: #faf9fd;
  --ink: #17142a;
  --ink-2: #3e3956;
  --muted: #6e6889;
  --rule: #e5e1ef;
  --rule-strong: #cfc9e2;
  --accent: #5b3fb5;
  --accent-soft: #ede9fb;
  --track: #eae6f4;
  --series: #5a45bd;
  --ramp-1: #b8aef0;
  --ramp-2: #9d90e6;
  --ramp-3: #7c6ad6;
  --ramp-4: #5a45bd;
  --ramp-5: #3b2d8f;
  --status-good: #0ca30c;
  --status-warning: #fab219;
  --status-critical: #d03b3b;
`;

const DARK = `
  color-scheme: dark;
  --ground: #0e0d14;
  --surface: #171622;
  --surface-2: #1d1b2a;
  --ink: #dfddea;
  --ink-2: #bab7cc;
  --muted: #918ea6;
  --rule: #292739;
  --rule-strong: #3a3750;
  --accent: #a896f2;
  --accent-soft: #241f3a;
  --track: #242235;
  --series: #8271dd;
  --ramp-1: #ded8fb;
  --ramp-2: #c3b9f5;
  --ramp-3: #a394ec;
  --ramp-4: #8271dd;
  --ramp-5: #5f4cba;
  --status-good: #0ca30c;
  --status-warning: #fab219;
  --status-critical: #d03b3b;
`;

const SANS = '"Source Sans 3", system-ui, -apple-system, "Segoe UI", sans-serif';
const DISPLAY = '"Fraunces", Georgia, "Times New Roman", serif';
const MONO = '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace';

export const CSS = `
.wclviz { ${LIGHT}
  color: var(--ink);
  font: 400 15px/1.6 ${SANS};
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .wclviz { ${DARK} }
}
:root[data-theme="dark"] .wclviz { ${DARK} }

.wclviz *, .wclviz *::before, .wclviz *::after { box-sizing: border-box; }
.wclviz :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 3px; }

/* --- run header ----------------------------------------------------------
   Provenance, not a title. In a report the page masthead already names the
   subject, so this is deliberately set as a metadata strip - an h1 here reads
   as a competing headline stacked under the real one. */
.wclviz-head {
  margin: 0 0 20px; padding: 0 0 14px; border-bottom: 1px solid var(--rule);
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px;
}
.wclviz-head .wcl-eyebrow {
  font: 600 10.5px/1.6 ${SANS}; text-transform: uppercase; letter-spacing: .12em;
  color: var(--accent); margin: 0; order: 2;
}
.wclviz-head h1 {
  font: 600 16px/1.4 ${SANS}; margin: 0; letter-spacing: 0; color: var(--ink); order: 1;
}
.wclviz-head p { margin: 0; color: var(--muted); font-size: 12.5px; order: 3; flex-basis: 100%; }
.wclviz-head code { font: 500 12px/1 ${MONO}; color: var(--ink-2); }

/* --- card ---------------------------------------------------------------- */
/* The card is the only thing on the page that claims to be a separate object -
   nothing inside it repeats the border+radius, or the hierarchy flattens. */
.wcl-card {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 12px;
  padding: 22px 24px 24px;
  margin: 0 0 18px;
}
.wcl-card > header { margin: 0 0 18px; }
.wcl-card h2 {
  font: 600 18px/1.3 ${DISPLAY}; margin: 0;
  display: flex; align-items: baseline; gap: 9px; text-wrap: balance;
}
.wcl-card h2 .wcl-id {
  font: 500 11.5px/1 ${MONO}; color: var(--accent);
  background: var(--accent-soft); border-radius: 4px; padding: 3px 6px;
  letter-spacing: 0; flex: none;
}
.wcl-card .wcl-summary {
  margin: 7px 0 0; font-size: 14px; color: var(--ink-2); max-width: 68ch;
}
.wcl-note {
  margin: 16px 0 0; font-size: 13.5px; color: var(--ink-2); max-width: 74ch;
  border-left: 2px solid var(--rule-strong); padding-left: 14px;
}
.wcl-note code { font: 500 12.5px/1 ${MONO}; color: var(--ink); }

/* --- stat row ------------------------------------------------------------ */
/* No box per tile: a hairline rail carries the grouping, so the numbers read as
   part of the card rather than as five more cards inside it. */
.wcl-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(146px, 1fr));
  gap: 2px; margin: 0 0 22px; background: var(--rule);
  border-radius: 8px; overflow: hidden;
}
.wcl-stat { background: var(--surface-2); padding: 12px 14px 13px; }
.wcl-stat .wcl-stat-label {
  font: 600 10.5px/1 ${SANS}; text-transform: uppercase; letter-spacing: .09em;
  color: var(--muted);
}
.wcl-stat .wcl-stat-value {
  font: 600 27px/1.1 ${DISPLAY}; margin-top: 7px; color: var(--ink);
}
.wcl-stat .wcl-stat-value .wcl-unit {
  font: 600 14px/1 ${DISPLAY}; color: var(--muted); margin-left: 1px;
}
.wcl-stat .wcl-stat-sub { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.35; }

/* --- bar list ------------------------------------------------------------ */
.wcl-bars { display: grid; gap: 8px; }
.wcl-bar-row { display: grid; grid-template-columns: minmax(96px, 23%) 1fr auto; gap: 12px; align-items: center; }
.wcl-bar-label { font-size: 13px; color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wcl-bar-track { position: relative; height: 11px; background: var(--track); border-radius: 4px; }
.wcl-bar-fill { position: absolute; inset: 0 auto 0 0; border-radius: 4px; background: var(--series); }
.wcl-bar-value {
  font: 500 13px/1 ${MONO}; font-variant-numeric: tabular-nums;
  color: var(--ink); min-width: 54px; text-align: right;
}
.wcl-bar-empty { font-size: 12.5px; color: var(--muted); font-style: italic; }

/* --- stacked bar --------------------------------------------------------- */
.wcl-stack { display: flex; width: 100%; height: 24px; border-radius: 5px; overflow: hidden; background: var(--surface); }
/* 2px surface gap between fills - a gap, never a border (dataviz marks spec). */
.wcl-stack > span + span { margin-left: 2px; }
.wcl-stack > span:first-child { border-radius: 5px 0 0 5px; }
.wcl-stack > span:last-child { border-radius: 0 5px 5px 0; }
.wcl-stack > span:only-child { border-radius: 5px; }
.wcl-legend { display: flex; flex-wrap: wrap; gap: 5px 18px; margin-top: 12px; }
.wcl-legend-item { display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--ink-2); }
.wcl-swatch { width: 10px; height: 10px; border-radius: 2px; flex: none; }
.wcl-legend-value { font: 500 12.5px/1 ${MONO}; font-variant-numeric: tabular-nums; color: var(--ink); }

/* --- table --------------------------------------------------------------- */
.wcl-scroll { overflow-x: auto; margin-top: 6px; }
.wcl-table { border-collapse: collapse; width: 100%; font-size: 13px; }
.wcl-table th, .wcl-table td { text-align: left; padding: 7px 14px 7px 0; white-space: nowrap; }
.wcl-table thead th {
  font: 600 10.5px/1.4 ${SANS}; text-transform: uppercase; letter-spacing: .08em;
  color: var(--muted); border-bottom: 1px solid var(--rule-strong); padding-bottom: 8px;
}
.wcl-table tbody tr + tr td { border-top: 1px solid var(--rule); }
.wcl-table td.num, .wcl-table th.num { text-align: right; }
.wcl-table td.num { font: 500 12.5px/1.5 ${MONO}; font-variant-numeric: tabular-nums; }
.wcl-table td.wrap { white-space: normal; min-width: 24ch; }

/* --- verdict chip -------------------------------------------------------- */
.wcl-verdict {
  display: inline-flex; align-items: center; gap: 5px;
  font: 700 10.5px/1.6 ${SANS}; letter-spacing: .05em;
  padding: 1px 8px 1px 6px; border-radius: 999px; white-space: nowrap;
  border: 1px solid currentColor;
}
.wcl-verdict .wcl-glyph { font-size: 10px; line-height: 1; }
.wcl-v-PERFECT { color: var(--status-good); background: color-mix(in srgb, var(--status-good) 13%, transparent); }
.wcl-v-GOOD    { color: var(--status-good); background: transparent; }
.wcl-v-OK      { color: var(--status-warning); background: color-mix(in srgb, var(--status-warning) 16%, transparent); }
.wcl-v-FAIL    { color: var(--status-critical); background: color-mix(in srgb, var(--status-critical) 13%, transparent); }

/* --- facts --------------------------------------------------------------- */
.wcl-facts { display: flex; flex-wrap: wrap; gap: 4px; }
.wcl-fact {
  font: 500 11px/1.6 ${MONO}; font-variant-numeric: tabular-nums;
  color: var(--ink-2); background: var(--surface-2);
  border: 1px solid var(--rule); border-radius: 4px; padding: 0 6px;
}
.wcl-mono { font: 500 12.5px/1.5 ${MONO}; }
.wcl-pre {
  margin: 0; padding: 12px 14px; background: var(--surface-2); border: 1px solid var(--rule);
  border-radius: 7px; overflow-x: auto; font: 500 12px/1.6 ${MONO};
  color: var(--ink-2); white-space: pre;
}

/* --- tooltip ------------------------------------------------------------- */
/* Anchored to the POINTER, not the element: an inline mark that wraps across two
   lines has a bounding rect spanning both, so an element-anchored tooltip lands
   in the wrong place (see .claude/knowledge/method/building-reports.md). */
.wcl-tip {
  position: fixed; z-index: 40; pointer-events: none;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--rule-strong); border-radius: 7px;
  padding: 8px 11px; font-size: 12.5px; line-height: 1.5; max-width: 320px;
  box-shadow: 0 8px 26px rgba(23, 20, 42, .18);
}
.wcl-tip .wcl-tip-title { font-weight: 600; color: var(--ink); }
.wcl-tip .wcl-tip-row { color: var(--ink-2); font-variant-numeric: tabular-nums; }

/* --- pull picker --------------------------------------------------------- */
/* Aggregate-first with per-pull drill-down: the selected chip is the only one
   that carries the accent, so the current view is never ambiguous. */
.wcl-pulls { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 18px; }
.wcl-pull {
  font: 500 12px/1.5 ${SANS}; padding: 3px 10px; cursor: pointer;
  color: var(--ink-2); background: var(--surface-2);
  border: 1px solid var(--rule); border-radius: 999px;
  display: inline-flex; align-items: baseline; gap: 5px; max-width: 24ch;
}
/* The name may ellipse; the pull number never does. */
.wcl-pull-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.wcl-pull:hover { border-color: var(--rule-strong); color: var(--ink); }
.wcl-pull[aria-pressed="true"] {
  background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600;
}
.wcl-pull .wcl-pull-n {
  font: 600 11px/1 ${MONO}; opacity: .8; flex: none;
}
.wcl-varies {
  color: var(--status-warning); font-weight: 700;
  text-transform: uppercase; letter-spacing: .04em; font-size: 13px;
}
.wcl-varies-detail { display: block; font: 500 11.5px/1.4 ${MONO}; color: var(--muted); }
.wcl-scope-note {
  margin: -6px 0 16px; font-size: 12.5px; color: var(--muted);
}

/* --- inferred context ---------------------------------------------------- */
/* Deliberately not stat tiles: these are readings of what the player brought,
   not measurements of how they played, and either can come back "varies". */
.wcl-context {
  display: flex; flex-wrap: wrap; gap: 10px 28px; margin: 0 0 22px;
  padding: 12px 14px; border: 1px dashed var(--rule-strong); border-radius: 8px;
}
.wcl-context > div { margin: 0; min-width: 150px; }
.wcl-context dt {
  font: 600 10.5px/1 ${SANS}; text-transform: uppercase; letter-spacing: .09em;
  color: var(--muted);
}
.wcl-context dd { margin: 5px 0 0; font: 600 15px/1.3 ${SANS}; color: var(--ink); }
.wcl-context p { margin: 3px 0 0; font-size: 11.5px; color: var(--muted); max-width: 34ch; }

/* --- misc ---------------------------------------------------------------- */
.wcl-toggle {
  background: var(--surface-2); border: 1px solid var(--rule-strong); border-radius: 6px;
  color: var(--ink-2); font: 600 12px/1.5 ${SANS};
  padding: 4px 11px; cursor: pointer;
}
.wcl-toggle:hover { color: var(--accent); border-color: var(--accent); }
.wcl-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.wcl-ledger-title { font: 600 14px/1.4 ${SANS}; color: var(--ink); }
.wcl-unknown { color: var(--muted); font-size: 13px; margin: 0 0 10px; }
.wcl-unknown code { font: 500 12.5px/1 ${MONO}; color: var(--ink-2); }
`;

let injected = false;

/** Idempotent: a report that mounts twice must not stack duplicate <style> tags. */
export function injectStyles(doc: Document = document): void {
  if (injected || doc.getElementById("wclviz-style")) return;
  const el = doc.createElement("style");
  el.id = "wclviz-style";
  el.textContent = CSS;
  doc.head.appendChild(el);
  injected = true;
}
