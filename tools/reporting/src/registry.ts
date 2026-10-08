/**
 * check id -> React component.
 *
 * The key is the `id` field on the Python `Check` subclass, which is also its CLI
 * name. Adding a check to a report is two steps and no wiring: give it an `id` in
 * `tools/warcraftlogs/checks/*.py`, then register a component under the same string here.
 *
 * A check with no component is NOT an error - `mount.tsx` falls back to rendering
 * its raw payload, so a freshly ported check shows up in a report immediately and
 * the component is an upgrade rather than a prerequisite.
 */

import { Abc } from "./checks/abc";
import { Barrage } from "./checks/barrage";
import { Mana } from "./checks/mana";
import type { CheckComponent } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const REGISTRY = new Map<string, CheckComponent<any>>([
  ["abc", Abc],
  ["mana", Mana],
  ["barrage", Barrage],
]);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function register(id: string, component: CheckComponent<any>): void {
  REGISTRY.set(id, component);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function lookup(id: string): CheckComponent<any> | undefined {
  return REGISTRY.get(id);
}

export function registered(): string[] {
  return [...REGISTRY.keys()];
}
