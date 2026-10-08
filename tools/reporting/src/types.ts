/**
 * The wire format between `tools/warcraftlogs` and this package.
 *
 * These types mirror `tools/warcraftlogs/lib/check.py` exactly - `Check.envelope()` builds
 * `Envelope`, `run.py --json` builds `Payload`. Nothing here is inferred from a
 * sample file: when the Python side changes shape, change it here in the same
 * commit or the component silently renders `undefined`.
 */

import type { FC } from "react";

export interface FightRef {
  id: number;
  name: string | null;
  encounterId: number | null;
  keystoneLevel: number | null;
  kill: boolean | null;
  /** Exact, unrounded. Round at render time. */
  seconds: number;
  startTime: number;
}

export interface Context {
  report: string;
  actor: string | null;
  actorId: number;
  selector: string | null;
  fights: FightRef[];
}

export interface Envelope<T = unknown> {
  schema: number;
  /** The pairing key: same string as the CLI name and the registry key. */
  id: string;
  title: string;
  group: string;
  summary: string;
  context: Context | null;
  data: T;
}

export interface Payload {
  schema: number;
  generated: string;
  context: Context;
  checks: Envelope[];
  /** Checks that still print directly and have no data yet. */
  unported: string[];
}

export interface CheckProps<T> {
  data: T;
  env: Envelope<T>;
}

export type CheckComponent<T = never> = FC<CheckProps<T>>;

/** The four grades `lib/format.py` assigns, worst last. */
export type Verdict = "PERFECT" | "GOOD" | "OK" | "FAIL";

/** One graded instance, as emitted by `format.instance()`. */
export interface Instance {
  when: string;
  verdict: Verdict;
  why: string;
  facts: Record<string, number | string | null>;
  timestamp?: number;
  fightId?: number;
  gate?: string;
}

export type Tally = Record<Verdict, number>;

/* --- per-fight payload shape -------------------------------------------------
 * Mirrors `Check._assemble()`. The fight is the unit: a check computes one pull
 * at a time and the base class maps it, so `fights` is always present and
 * `overall` is the roll-up (or null where a roll-up would be meaningless).
 */

export interface FightPart<T> {
  fight: FightRef;
  data: T;
}

export interface Scoped<TFight, TOverall = TFight, TParams = Record<string, unknown>> {
  scope: "fight";
  params: TParams;
  fights: FightPart<TFight>[];
  overall: TOverall | null;
}

/** A per-fight inference rolled up by `check.consensus()`. */
export interface Consensus<T> {
  value: T | null;
  evidence: string | null;
  /** True when the fights disagreed - the UI must say so, not hide it. */
  varies: boolean;
  byValue: Record<string, number>;
}
