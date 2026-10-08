/**
 * The shared vocabulary every check component is built from.
 *
 * Checks get their own component (keyed by check id) so each can say what its
 * own numbers mean, but they are assembled from these pieces so thirty checks
 * end up looking like one report rather than thirty. Mark geometry, the 2px
 * surface gap between fills, the hairline grid and tabular figures live here
 * once - a check component should not be setting colors or radii itself.
 */

import type { ReactNode } from "react";
import { tipProps, useTooltip } from "./Tooltip";
import type { Consensus, FightRef, Verdict } from "../types";

export { TooltipLayer, useTooltip, tipProps } from "./Tooltip";

/* ------------------------------------------------------------------ numbers */

export const round = (v: number, dp = 1): string =>
  v.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const pct = (v: number, dp = 1): string => `${round(v, dp)}%`;

/** 312.4 -> "5:12". Durations read as time, not as a four-digit number. */
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * fight id -> a label you can tell apart from its neighbours.
 *
 * A raid night has four pulls on the same boss and the log names all four
 * identically. That is fine in a terminal read top to bottom and useless on a
 * chart, where a bar has to be findable, or in a ledger, where `when` is
 * fight-relative and so repeats. Repeats get numbered; unique names are left
 * alone rather than gaining a pointless "pull 1".
 */
export function fightLabelParts(
  fights: readonly FightRef[],
): Map<number, { base: string; pull: number | null }> {
  const name = (f: FightRef) =>
    `${f.name ?? `fight ${f.id}`}${f.keystoneLevel ? ` +${f.keystoneLevel}` : ""}`;
  const counts = new Map<string, number>();
  for (const f of fights) counts.set(name(f), (counts.get(name(f)) ?? 0) + 1);
  const seen = new Map<string, number>();
  const out = new Map<number, { base: string; pull: number | null }>();
  for (const f of fights) {
    const n = name(f);
    if ((counts.get(n) ?? 0) < 2) {
      out.set(f.id, { base: n, pull: null });
      continue;
    }
    const k = (seen.get(n) ?? 0) + 1;
    seen.set(n, k);
    out.set(f.id, { base: n, pull: k });
  }
  return out;
}

export function fightLabels(fights: readonly FightRef[]): Map<number, string> {
  const out = new Map<number, string>();
  for (const [id, p] of fightLabelParts(fights)) {
    out.set(id, p.pull === null ? p.base : `${p.base} · pull ${p.pull}`);
  }
  return out;
}

/* ------------------------------------------------------------- pull picker */

/**
 * Aggregate first, one pull on demand.
 *
 * The roll-up is the resting state because it is how you find the outlier; the
 * per-pull view is how you then read it. Both come from the same payload - the
 * check computed every fight separately and the aggregate is derived from those,
 * not the other way round.
 *
 * Returns `null` for "all pulls", otherwise the selected fight id.
 */
export function PullPicker({
  fights,
  value,
  onChange,
  allLabel = "All pulls",
}: {
  fights: readonly FightRef[];
  value: number | null;
  onChange: (id: number | null) => void;
  allLabel?: string;
}) {
  if (fights.length < 2) return null;
  const parts = fightLabelParts(fights);
  const full = fightLabels(fights);
  return (
    <div className="wcl-pulls" role="group" aria-label="Choose a pull">
      <button
        type="button"
        className="wcl-pull"
        aria-pressed={value === null}
        onClick={() => onChange(null)}
      >
        {allLabel} <span className="wcl-pull-n">{fights.length}</span>
      </button>
      {fights.map((f) => {
        const p = parts.get(f.id);
        return (
          <button
            type="button"
            key={f.id}
            className="wcl-pull"
            aria-pressed={value === f.id}
            onClick={() => onChange(f.id)}
            title={full.get(f.id)}
          >
            {/* Only the boss name truncates. The pull number is the whole reason
                these labels exist, so it never gets ellipsed away - four chips
                reading "The Coiled Altar · p…" tell you nothing. */}
            <span className="wcl-pull-name">{p?.base}</span>
            {p?.pull != null && <span className="wcl-pull-n">{p.pull}</span>}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Says out loud when the fights disagreed about an inferred fact, instead of
 * showing the majority answer as though it were the only one.
 */
export function ConsensusValue({ entry }: { entry: Consensus<string | number> }) {
  if (!entry.varies) {
    return <>{entry.value === null ? "unknown" : String(entry.value)}</>;
  }
  const spread = Object.entries(entry.byValue)
    .map(([v, n]) => `${v === "None" || v === "null" ? "unknown" : v} in ${n}`)
    .join(", ");
  return (
    <>
      <span className="wcl-varies">varies</span>
      <span className="wcl-varies-detail">{spread}</span>
    </>
  );
}

export function consensusNote(entry: Consensus<string | number>): string {
  return entry.varies
    ? "not consistent across the selection — read the per-pull values"
    : (entry.evidence ?? "");
}

/* -------------------------------------------------------------------- card */

export function Card({
  title,
  id,
  summary,
  children,
}: {
  title: string;
  id?: string;
  summary?: string;
  children: ReactNode;
}) {
  return (
    <section className="wcl-card">
      <header>
        <h2>
          {title}
          {id && <span className="wcl-id">{id}</span>}
        </h2>
        {summary && <p className="wcl-summary">{summary}</p>}
      </header>
      {children}
    </section>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="wcl-note">{children}</p>;
}

/* -------------------------------------------------------------- stat tiles */

export interface Stat {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
}

/**
 * A row of headline numbers. This is the "sometimes the answer is not a chart"
 * case: one aggregate does not want a one-bar bar chart.
 */
export function Stats({ items }: { items: Stat[] }) {
  return (
    <div className="wcl-stats">
      {items.map((s) => (
        <div className="wcl-stat" key={s.label}>
          <div className="wcl-stat-label">{s.label}</div>
          <div className="wcl-stat-value">
            {s.value}
            {s.unit && <span className="wcl-unit">{s.unit}</span>}
          </div>
          {s.sub && <div className="wcl-stat-sub">{s.sub}</div>}
        </div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- bar list */

export interface BarRow {
  key: string;
  label: string;
  /** Bar length as a share of `max`. */
  value: number;
  /** Text at the bar end. Direct-labelled: every row carries its own number,
   *  which is what lets this chart skip an axis entirely. */
  display: string;
  tooltip?: ReactNode;
  /** Rendered instead of a bar - "no casts recorded" is not a zero. */
  empty?: string;
}

/**
 * Horizontal bars, one series, one color. Nominal categories never get a
 * value-ramp: bar length already encodes magnitude, and coloring by size would
 * spend the only free channel restating it.
 */
export function BarList({ rows, max }: { rows: BarRow[]; max: number }) {
  const tip = useTooltip();
  const scale = max > 0 ? max : 1;
  return (
    <div className="wcl-bars">
      {rows.map((r) => (
        <div className="wcl-bar-row" key={r.key}>
          <div className="wcl-bar-label" title={r.label}>
            {r.label}
          </div>
          {r.empty ? (
            <div className="wcl-bar-empty">{r.empty}</div>
          ) : (
            <div className="wcl-bar-track" {...tipProps(tip, r.tooltip)}>
              <div
                className="wcl-bar-fill"
                style={{ width: `${Math.max(0, Math.min(100, (r.value / scale) * 100))}%` }}
              />
            </div>
          )}
          <div className="wcl-bar-value">{r.empty ? "" : r.display}</div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- stacked bar */

export interface Segment {
  key: string;
  label: string;
  value: number;
  color: string;
  display?: string;
  tooltip?: ReactNode;
}

/**
 * One part-to-whole bar plus its legend. The legend is not optional: with two or
 * more segments, identity must never rest on color alone.
 *
 * Zero-valued segments are dropped from the bar but kept in the legend, so a
 * band with no time in it reads as "measured, zero" rather than as missing.
 */
export function StackedBar({ segments }: { segments: Segment[] }) {
  const tip = useTooltip();
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  return (
    <>
      <div className="wcl-stack">
        {segments
          .filter((s) => s.value > 0)
          .map((s) => (
            <span
              key={s.key}
              style={{ width: `${(s.value / total) * 100}%`, background: s.color }}
              {...tipProps(tip, s.tooltip ?? `${s.label}: ${s.display ?? s.value}`)}
            />
          ))}
      </div>
      <div className="wcl-legend">
        {segments.map((s) => (
          <span className="wcl-legend-item" key={s.key}>
            <span className="wcl-swatch" style={{ background: s.color }} />
            {s.label}
            {s.display && <span className="wcl-legend-value">{s.display}</span>}
          </span>
        ))}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ table */

export interface Column<R> {
  key: string;
  header: string;
  /** Right-aligned with tabular figures. */
  num?: boolean;
  /** Allowed to wrap; everything else stays on one line and scrolls. */
  wrap?: boolean;
  render: (row: R) => ReactNode;
}

/**
 * The table view. Every chart in this bundle has one available beside it - it is
 * the fallback that makes a sub-3:1 color or a missed tooltip a non-issue.
 * Wide content scrolls inside its own container; the page never scrolls sideways.
 */
export function Table<R>({
  columns,
  rows,
  rowKey,
}: {
  columns: Column<R>[];
  rows: R[];
  rowKey: (row: R, i: number) => string;
}) {
  return (
    <div className="wcl-scroll">
      <table className="wcl-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : undefined}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={rowKey(r, i)}>
              {columns.map((c) => (
                <td key={c.key} className={[c.num && "num", c.wrap && "wrap"].filter(Boolean).join(" ")}>
                  {c.render(r)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------------------------------------------------------- verdicts */

/**
 * Verdict colors are the reserved STATUS palette, never the categorical slots -
 * these mean good/bad, they are not four series.
 *
 * PERFECT and GOOD deliberately share the "good" hue: they mean the same state
 * (nothing to fix) and are separated by fill weight, glyph and label rather than
 * by inventing a fourth hue for a distinction that isn't one. Every chip carries
 * a glyph AND the word, so no verdict is ever color-alone - which is also what
 * licenses `--status-warning` sitting under 3:1 on the light surface.
 */
export const VERDICTS: Verdict[] = ["PERFECT", "GOOD", "OK", "FAIL"];

export const VERDICT_COLOR: Record<Verdict, string> = {
  PERFECT: "var(--status-good)",
  // Same hue at a lighter step - a fill-weight difference within one status
  // colour, matching how the chips separate the two. Not a fifth hue, and the
  // legend carries the count either way.
  GOOD: "color-mix(in srgb, var(--status-good) 45%, var(--surface))",
  OK: "var(--status-warning)",
  FAIL: "var(--status-critical)",
};

const GLYPH: Record<Verdict, string> = { PERFECT: "★", GOOD: "✓", OK: "!", FAIL: "✕" };

export function VerdictChip({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`wcl-verdict wcl-v-${verdict}`}>
      <span className="wcl-glyph" aria-hidden="true">
        {GLYPH[verdict]}
      </span>
      {verdict}
    </span>
  );
}

/** The raw numbers a verdict was decided on, as monospace chips. */
export function Facts({ facts }: { facts: Record<string, number | string | null> }) {
  const entries = Object.entries(facts).filter(([, v]) => v !== null && v !== undefined);
  if (!entries.length) return null;
  return (
    <span className="wcl-facts">
      {entries.map(([k, v]) => (
        <span className="wcl-fact" key={k}>
          {k}={typeof v === "number" ? (Number.isInteger(v) ? v : round(v, 0)) : v}
        </span>
      ))}
    </span>
  );
}
