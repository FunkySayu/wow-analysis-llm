/**
 * `abc` - GCD uptime per fight. Payload: checks/common.py :: AbcCheck.json().
 *
 * Form: the roll-up is one number, so it is a stat tile, not a chart. The
 * comparison across pulls is magnitude over a short ordered list, so it is a
 * horizontal bar list - one series, one color, direct-labelled, no axis.
 *
 * This is the one check with no pull picker: the cross-pull comparison IS the
 * content here, so narrowing to a single fight would leave one bar.
 */

import { BarList, Card, Note, Stats, Table, duration, fightLabels, pct, round } from "../primitives";
import type { CheckComponent, FightPart, FightRef, Scoped } from "../types";

interface AbcFight {
  label: string;
  casts: number;
  downtimeSeconds?: number;
  uptimePct?: number;
  longestGapSeconds?: number;
}

interface AbcOverall {
  fights: number;
  measuredFights: number;
  seconds: number;
  downtimeSeconds: number;
  uptimePct: number;
}

export type AbcData = Scoped<AbcFight, AbcOverall, { gcd: number }>;

export const Abc: CheckComponent<AbcData> = ({ data, env }) => {
  const rows = data.fights;
  const label = fightLabels(rows.map((r) => r.fight));
  const overall = data.overall;

  // Only fights the player actually cast in can be compared or ranked.
  const measured = rows.filter((r) => r.data.casts > 0);
  const pick = (better: (a: FightPart<AbcFight>, b: FightPart<AbcFight>) => boolean) =>
    measured.length ? measured.reduce((a, b) => (better(a, b) ? a : b)) : null;
  const worst = pick((a, b) => (a.data.uptimePct ?? 100) <= (b.data.uptimePct ?? 100));
  const longest = pick((a, b) => (a.data.longestGapSeconds ?? 0) >= (b.data.longestGapSeconds ?? 0));

  const name = (f: FightRef) => label.get(f.id) ?? f.name ?? `fight ${f.id}`;

  return (
    <Card title={env.title} id={env.id} summary={env.summary}>
      <Stats
        items={[
          {
            label: "GCD uptime",
            value: round(overall?.uptimePct ?? 0),
            unit: "%",
            sub: `${overall?.measuredFights ?? 0} of ${overall?.fights ?? 0} pulls · ${duration(
              overall?.seconds ?? 0,
            )} measured`,
          },
          {
            label: "Downtime",
            value: duration(overall?.downtimeSeconds ?? 0),
            sub: `gaps over ${round(data.params.gcd, 1)}s`,
          },
          worst
            ? { label: "Worst pull", value: pct(worst.data.uptimePct ?? 0), sub: name(worst.fight) }
            : { label: "Worst pull", value: "—" },
          longest
            ? {
                label: "Longest gap",
                value: `${round(longest.data.longestGapSeconds ?? 0)}s`,
                sub: name(longest.fight),
              }
            : { label: "Longest gap", value: "—" },
        ]}
      />

      <BarList
        max={100}
        rows={rows.map(({ fight: f, data: r }) => ({
          key: String(f.id),
          label: name(f),
          value: r.uptimePct ?? 0,
          display: r.casts ? pct(r.uptimePct ?? 0) : "",
          empty: r.casts ? undefined : "no casts recorded",
          tooltip: (
            <>
              <div className="wcl-tip-title">{name(f)}</div>
              <div className="wcl-tip-row">{pct(r.uptimePct ?? 0)} uptime</div>
              <div className="wcl-tip-row">
                {r.casts} casts in {duration(f.seconds)}
              </div>
              <div className="wcl-tip-row">
                {round(r.downtimeSeconds ?? 0)}s downtime · longest gap{" "}
                {round(r.longestGapSeconds ?? 0, 2)}s
              </div>
            </>
          ),
        }))}
      />

      <Note>
        A gap longer than {round(data.params.gcd, 1)}s counts as downtime. Off-GCD casts
        (trinkets, utility) still close a gap, so read every figure here as an{" "}
        <em>upper bound</em> on true GCD uptime. A single long gap next to otherwise high uptime
        is usually a phase where the boss was untargetable, not sloppy play — the per-pull
        longest gap is the column that tells the two apart.
      </Note>

      <Table
        rows={rows}
        rowKey={(r) => String(r.fight.id)}
        columns={[
          { key: "fight", header: "Pull", render: (r) => name(r.fight) },
          { key: "dur", header: "Duration", num: true, render: (r) => duration(r.fight.seconds) },
          { key: "casts", header: "Casts", num: true, render: (r) => r.data.casts || "—" },
          {
            key: "down",
            header: "Downtime",
            num: true,
            render: (r) => (r.data.casts ? `${round(r.data.downtimeSeconds ?? 0)}s` : "—"),
          },
          {
            key: "up",
            header: "Uptime",
            num: true,
            render: (r) => (r.data.casts ? pct(r.data.uptimePct ?? 0) : "—"),
          },
          {
            key: "gap",
            header: "Longest gap",
            num: true,
            render: (r) => (r.data.casts ? `${round(r.data.longestGapSeconds ?? 0, 2)}s` : "—"),
          },
        ]}
      />
    </Card>
  );
};
