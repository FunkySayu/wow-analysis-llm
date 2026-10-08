/**
 * Dev harness - `npm run dev`, then open the printed URL.
 *
 * Loads a payload written by `run.py --json`. Point it at any file with
 * `?p=<url>`; the default is ./payload.json, which is gitignored so you can drop
 * a working extract in beside this package without dirtying the tree:
 *
 *   run.py common -r <REPORT> -a <ACTOR> -f raid --json -o tools/reporting/payload.json
 *
 * This file is NOT part of the library build (vite.config.ts builds src/mount.tsx),
 * so nothing here ships inside a report.
 */

import { render } from "../mount";
import type { Payload } from "../types";

const url = new URLSearchParams(location.search).get("p") ?? "/payload.json";
const root = document.getElementById("root")!;
const err = document.getElementById("err")!;

fetch(url)
  .then((r) => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json() as Promise<Payload>;
  })
  .then((payload) => render(root, payload))
  .catch((e: Error) => {
    err.textContent =
      `Could not load ${url}: ${e.message}\n\n` +
      "Generate one with:  python3 tools/warcraftlogs/run.py common -r <REPORT> -a <ACTOR> " +
      "-f raid --json -o tools/reporting/payload.json";
    err.style.whiteSpace = "pre-wrap";
  });
