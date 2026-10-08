/**
 * Bundle entry point. Exposes `window.WCLViz` and nothing else.
 *
 *     WCLViz.render(document.getElementById("root"), PAYLOAD)
 *
 * where PAYLOAD is exactly what `run.py --json` wrote. A report HTML inlines this
 * bundle and its payload in two <script> blocks and calls render once - see
 * tools/reporting/build_report.py and reports/_checks_template.html.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { Card, TooltipLayer } from "./primitives";
import { lookup, register, registered } from "./registry";
import { injectStyles } from "./theme";
import type { Envelope, Payload } from "./types";

function Unknown({ env }: { env: Envelope }) {
  return (
    <Card title={env.title || env.id} id={env.id} summary={env.summary}>
      <p className="wcl-unknown">
        No component is registered for <code>{env.id}</code> yet — showing its raw payload.
      </p>
      <pre className="wcl-pre">{JSON.stringify(env.data, null, 2)}</pre>
    </Card>
  );
}

function Report({ payload }: { payload: Payload }) {
  const { context: ctx } = payload;
  const fights = ctx?.fights?.length ?? 0;
  return (
    <TooltipLayer>
      <div className="wclviz">
        <header className="wclviz-head">
          <p className="wcl-eyebrow">
            {payload.checks.length} check{payload.checks.length === 1 ? "" : "s"} ·{" "}
            {fights} fight{fights === 1 ? "" : "s"}
          </p>
          <h1>{ctx?.actor ?? "unknown actor"}</h1>
          <p>
            report <code>{ctx?.report}</code> · selector <code>{ctx?.selector}</code> ·
            generated {payload.generated}
          </p>
        </header>

        {payload.checks.map((env) => {
          const Component = lookup(env.id);
          return Component ? (
            <Component key={env.id} data={env.data} env={env} />
          ) : (
            <Unknown key={env.id} env={env} />
          );
        })}

        {payload.unported?.length > 0 && (
          <p className="wcl-unknown">
            Text-only checks in this run (no payload yet): {payload.unported.join(", ")}
          </p>
        )}
      </div>
    </TooltipLayer>
  );
}

const roots = new WeakMap<Element, Root>();

export function render(el: Element, payload: Payload): void {
  injectStyles(el.ownerDocument ?? document);
  // Reuse the root on a re-render: createRoot twice on one element warns and
  // leaks, and the dev harness re-renders on every payload switch.
  let root = roots.get(el);
  if (!root) {
    root = createRoot(el);
    roots.set(el, root);
  }
  root.render(
    <StrictMode>
      <Report payload={payload} />
    </StrictMode>,
  );
}

export { register, registered };
