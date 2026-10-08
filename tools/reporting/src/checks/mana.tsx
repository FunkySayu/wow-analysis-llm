/**
 * `mana` - time spent on the mana curve. Payload: checks/common.py :: ManaCheck.json().
 *
 * Form: five ORDERED bands summing to the measured time - part-to-whole with a
 * natural order, so one stacked bar on an ordinal ramp (one hue, dark at the
 * full end, light at the empty end), not five categorical hues. The ramp passes
 * `validate_palette.js --ordinal` in both modes; see src/theme.ts.
 *
 * The picker matters more here than anywhere else. A curve averaged over a raid
 * night is not any pull's curve - it only answers "how much of the night was
 * spent dry". The per-pull view is where the actual reading happens.
 */

import { useState } from "react";
import {
  Card,
  Note,
  PullPicker,
  StackedBar,
  Stats,
  Table,
  duration,
  fightLabels,
  pct,
  round,
} from "../primitives";
import type { CheckComponent, Scoped } from "../types";

interface Band {
  label: string;
  lo: number;
  hi: number;
  seconds: number;
  sharePct: number;
}

interface ManaView {
  totalSeconds: number;
  bands: Band[];
  lowest: { pct: number; at: string; timestamp: number; fight: string; fightId: number } | null;
  drySeconds: number;
  dryPct: number;
  castsWhileDry: { spellId: number; name: string; count: number }[];
}

export type ManaData = Scoped<ManaView, ManaView, { dryThresholdPct: number; bands: string[] }>;

// Payload order is full -> empty (80-100 first), and so is the ramp: darkest for
// the full band, lightest for the empty one.
const RAMP = ["var(--ramp-5)", "var(--ramp-4)", "var(--ramp-3)", "var(--ramp-2)", "var(--ramp-1)"];

export const Mana: CheckComponent<ManaData> = ({ data, env }) => {
  const [fid, setFid] = useState<number | null>(null);
  const fights = data.fights.map((f) => f.fight);
  const labels = fightLabels(fights);
  const selected = fid === null ? null : data.fights.find((f) => f.fight.id === fid);
  const view: ManaView | null = fid === null ? data.overall : (selected?.data ?? null);
  const dry = data.params.dryThresholdPct;
  const scopeLabel = fid === null ? "all pulls" : (labels.get(fid) ?? "this pull");

  return (
    <Card title={env.title} id={env.id} summary={env.summary}>
      <PullPicker fights={fights} value={fid} onChange={setFid} />

      {!view || !view.totalSeconds ? (
        <Note>
          No mana readings for {scopeLabel} — this actor may not use mana, or the events were
          fetched without resources.
        </Note>
      ) : (
        <>
          <Stats
            items={[
              {
                label: `Under ${round(dry, 0)}% mana`,
                value: pct(view.dryPct),
                sub: `${duration(view.drySeconds)} of ${duration(view.totalSeconds)}`,
              },
              view.lowest
                ? {
                    label: "Lowest reading",
                    value: pct(view.lowest.pct),
                    sub: `${view.lowest.at} into ${view.lowest.fight}`,
                  }
                : { label: "Lowest reading", value: "—" },
              {
                label: "Casts while dry",
                value: String(view.castsWhileDry.reduce((a, c) => a + c.count, 0)),
                sub: view.castsWhileDry.length
                  ? `${view.castsWhileDry.length} distinct abilities`
                  : "none",
              },
            ]}
          />

          <StackedBar
            segments={view.bands.map((b, i) => ({
              key: b.label,
              label: b.label,
              value: b.seconds,
              color: RAMP[i] ?? RAMP[RAMP.length - 1],
              display: pct(b.sharePct),
              tooltip: (
                <>
                  <div className="wcl-tip-title">{b.label} mana</div>
                  <div className="wcl-tip-row">
                    {round(b.seconds)}s · {pct(b.sharePct)} of {scopeLabel}
                  </div>
                </>
              ),
            }))}
          />

          <Note>
            Time is attributed from each cast to the next, so a long gap holds whatever the cast
            before it read — right for downtime, but it slightly over-weights a band the player
            idled in.{" "}
            {fid === null
              ? "This is every pull summed: it answers how much of the night was spent dry, not what any one pull looked like — pick a pull above for that."
              : "Read this before any spender check: running dry puts the player in a different APL branch, which a rotation check reading only buff stacks will score as a mistake."}
          </Note>

          {view.castsWhileDry.length > 0 && (
            <Table
              rows={view.castsWhileDry}
              rowKey={(c) => String(c.spellId)}
              columns={[
                {
                  key: "name",
                  header: `Cast under ${round(dry, 0)}% mana`,
                  render: (c) => c.name,
                },
                {
                  key: "id",
                  header: "Spell ID",
                  num: true,
                  render: (c) => c.spellId,
                },
                { key: "n", header: "Casts", num: true, render: (c) => c.count },
              ]}
            />
          )}
        </>
      )}
    </Card>
  );
};
