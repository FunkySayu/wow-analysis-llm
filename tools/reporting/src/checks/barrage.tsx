/**
 * `barrage` - every Arcane Barrage graded against the Sunfury APL's spend gates.
 * Payload: checks/mage_arcane.py :: BarrageCheck.json().
 *
 * Form: the headline is one ratio (how many casts were clean), so that is a stat
 * tile. The grade mix is part-to-whole over four ordered states, so one stacked
 * bar on the reserved STATUS palette. The instances that carry an action are the
 * faults, so those get the table - and, unlike the terminal, the "which gate did
 * it satisfy" breakdown is worth showing for the clean ones too: it is the part
 * that disagrees with WoWAnalyzer.
 *
 * `heroTree` and `aoeCount` are resolved PER PULL and rolled up by
 * `check.consensus()`. When the pulls disagree the card says so rather than
 * showing the majority answer as fact - the previous version took fight[0]'s
 * reading and applied it to every pull in the selection.
 */

import { useMemo, useState } from "react";
import {
  Card,
  ConsensusValue,
  Facts,
  Note,
  PullPicker,
  StackedBar,
  Stats,
  Table,
  VERDICTS,
  VERDICT_COLOR,
  VerdictChip,
  consensusNote,
  fightLabels,
  pct,
} from "../primitives";
import type { CheckComponent, Consensus, Instance, Scoped, Tally, Verdict } from "../types";

interface GateCount {
  gate: string;
  casts: number;
}

interface BarrageFight {
  heroTree: { value: string | null; evidence: string };
  aoeCount: { value: number; evidence: string };
  instances: Instance[];
  tally: Tally;
  gates: GateCount[];
}

interface BarrageOverall {
  heroTree: Consensus<string>;
  aoeCount: Consensus<number>;
  instances: Instance[];
  tally: Tally;
  gates: GateCount[];
}

export type BarrageData = Scoped<
  BarrageFight,
  BarrageOverall,
  { maxCharges: number; apl: string }
>;

const FAULTS: Verdict[] = ["OK", "FAIL"];

/** Worst-first faults shown before the reader has to ask for more. Ninety-five
 *  rows of table is not a finding; the first twenty are. */
const PREVIEW = 20;

type Mode = "preview" | "faults" | "all";

/** Both shapes carry the same fields; only the context entries differ. */
const asConsensus = <T,>(v: Consensus<T> | { value: T | null; evidence: string }): Consensus<T> =>
  "varies" in v ? v : { ...v, varies: false, byValue: {} };

export const Barrage: CheckComponent<BarrageData> = ({ data, env }) => {
  const [mode, setMode] = useState<Mode>("preview");
  const [fid, setFid] = useState<number | null>(null);

  const fights = data.fights.map((f) => f.fight);
  const label = fightLabels(fights);
  const selected = fid === null ? null : data.fights.find((f) => f.fight.id === fid);
  const view = fid === null ? data.overall : (selected?.data ?? null);
  const multiFight = fid === null && fights.length > 1;

  const instances = useMemo(() => view?.instances ?? [], [view]);
  const total = instances.length;
  const tally = view?.tally;
  const clean = (tally?.PERFECT ?? 0) + (tally?.GOOD ?? 0);

  const faults = useMemo(
    () =>
      instances
        .filter((i) => FAULTS.includes(i.verdict))
        // Worst first: FAIL before OK, then in fight order.
        .sort((a, b) =>
          a.verdict === b.verdict
            ? (a.timestamp ?? 0) - (b.timestamp ?? 0)
            : a.verdict === "FAIL"
              ? -1
              : 1,
        ),
    [instances],
  );

  const rows = mode === "all" ? instances : mode === "faults" ? faults : faults.slice(0, PREVIEW);
  const heading =
    mode === "all"
      ? `All ${total} Barrages`
      : mode === "faults"
        ? `All ${faults.length} that met no gate cleanly`
        : `Worst ${Math.min(PREVIEW, faults.length)} of ${faults.length} that met no gate cleanly`;

  if (!view) {
    return (
      <Card title={env.title} id={env.id} summary={env.summary}>
        <PullPicker fights={fights} value={fid} onChange={setFid} />
        <Note>No data for this pull.</Note>
      </Card>
    );
  }

  const tree = asConsensus(view.heroTree);
  const aoe = asConsensus(view.aoeCount);

  return (
    <Card title={env.title} id={env.id} summary={env.summary}>
      <PullPicker fights={fights} value={fid} onChange={setFid} />

      {/* Measurements. */}
      <Stats
        items={[
          {
            label: "Cast on an APL gate",
            value: pct(total ? (clean / total) * 100 : 0),
            sub: `${clean} of ${total} Barrages`,
          },
          {
            label: "Below max charges",
            value: String(tally?.FAIL ?? 0),
            sub: `no gate met · ${data.params.maxCharges} charges is the gate`,
          },
        ]}
      />

      {/* Inferred context, kept visually separate from the measurements: these
          are readings of what the player brought, not of how they played, and
          either can come back "varies" across a selection. */}
      <dl className="wcl-context">
        <div>
          <dt>Hero tree</dt>
          <dd>
            <ConsensusValue entry={tree as Consensus<string | number>} />
          </dd>
          <p>{consensusNote(tree as Consensus<string | number>)}</p>
        </div>
        <div>
          <dt>aoe_count</dt>
          <dd>
            <ConsensusValue entry={aoe as Consensus<string | number>} />
          </dd>
          <p>{consensusNote(aoe as Consensus<string | number>)}</p>
        </div>
      </dl>

      <StackedBar
        segments={VERDICTS.map((v) => ({
          key: v,
          label: v,
          value: tally?.[v] ?? 0,
          color: VERDICT_COLOR[v],
          display: String(tally?.[v] ?? 0),
          tooltip: `${tally?.[v] ?? 0} of ${total} Barrages graded ${v}`,
        }))}
      />

      <Note>
        Each cast is scored on the gate it actually satisfied, not on an average. PERFECT and GOOD
        share a colour because they mean the same thing — nothing to fix; the glyph and the label
        carry the difference. Note the deliberate disagreement with WoWAnalyzer: its Sunfury
        evaluator has no branch for <code>salvo&gt;8 &amp; cooldown.touch_of_the_magi.ready</code>,
        so a Barrage fired to set up Touch of the Magi is graded a mistake there and correct here.
        {tree.varies &&
          " The hero-tree evidence is not consistent across this selection, so each pull was graded on its own reading — pick a pull above to see it."}
      </Note>

      <div className="wcl-scroll">
        <table className="wcl-table">
          <thead>
            <tr>
              <th>Gate satisfied</th>
              <th className="num">Casts</th>
              <th className="num">Share</th>
            </tr>
          </thead>
          <tbody>
            {view.gates.map((g) => (
              <tr key={g.gate}>
                <td className="wrap">{g.gate}</td>
                <td className="num">{g.casts}</td>
                <td className="num">{pct(total ? (g.casts / total) * 100 : 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="wcl-row" style={{ margin: "22px 0 8px" }}>
        <span className="wcl-ledger-title">{heading}</span>
        <span style={{ display: "flex", gap: 6 }}>
          {mode === "preview" && faults.length > PREVIEW && (
            <button className="wcl-toggle" onClick={() => setMode("faults")}>
              Show all {faults.length} faults
            </button>
          )}
          {mode !== "preview" && (
            <button className="wcl-toggle" onClick={() => setMode("preview")}>
              Collapse
            </button>
          )}
          <button
            className="wcl-toggle"
            onClick={() => setMode((m) => (m === "all" ? "preview" : "all"))}
          >
            {mode === "all" ? "Faults only" : `Show all ${total} casts`}
          </button>
        </span>
      </div>

      <Table
        rows={rows}
        rowKey={(i, n) => `${i.fightId ?? 0}-${i.timestamp ?? n}`}
        columns={[
          ...(multiFight
            ? [
                {
                  key: "fight",
                  header: "Pull",
                  render: (i: Instance) =>
                    (i.fightId !== undefined && label.get(i.fightId)) || "—",
                },
              ]
            : []),
          { key: "when", header: "When", num: true, render: (i) => i.when },
          { key: "verdict", header: "Verdict", render: (i) => <VerdictChip verdict={i.verdict} /> },
          { key: "gate", header: "Reading", wrap: true, render: (i) => i.gate ?? i.why },
          { key: "facts", header: "State at cast", render: (i) => <Facts facts={i.facts} /> },
        ]}
      />

      <Note>
        The APL line every verdict is measured against:
        <pre className="wcl-pre" style={{ marginTop: 8 }}>
          {data.params.apl}
        </pre>
      </Note>
    </Card>
  );
};
