/**
 * Pointer-anchored hover tooltip, shared by every mark in the bundle.
 *
 * Anchored to the pointer rather than to the hovered element's bounding rect.
 * That is not a preference: an inline element that wraps across two lines has a
 * rect spanning both lines, so an element-anchored tooltip lands nowhere near
 * the mark - a bug this project already paid for once
 * (.claude/knowledge/method/building-reports.md).
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface TipState {
  content: ReactNode;
  x: number;
  y: number;
}

interface TipApi {
  show: (content: ReactNode, e: { clientX: number; clientY: number }) => void;
  move: (e: { clientX: number; clientY: number }) => void;
  hide: () => void;
}

const NOOP: TipApi = { show: () => {}, move: () => {}, hide: () => {} };
const Ctx = createContext<TipApi>(NOOP);

export function useTooltip(): TipApi {
  return useContext(Ctx);
}

/**
 * Convenience: the three handlers a mark needs, ready to spread.
 * `null` content disables the tooltip for that mark entirely.
 */
export function tipProps(api: TipApi, content: ReactNode) {
  if (content === null || content === undefined) return {};
  return {
    onMouseEnter: (e: React.MouseEvent) => api.show(content, e),
    onMouseMove: (e: React.MouseEvent) => api.move(e),
    onMouseLeave: () => api.hide(),
  };
}

export function TooltipLayer({ children }: { children: ReactNode }) {
  const [tip, setTip] = useState<TipState | null>(null);

  const show = useCallback((content: ReactNode, e: { clientX: number; clientY: number }) => {
    setTip({ content, x: e.clientX, y: e.clientY });
  }, []);
  const move = useCallback((e: { clientX: number; clientY: number }) => {
    setTip((t) => (t ? { ...t, x: e.clientX, y: e.clientY } : t));
  }, []);
  const hide = useCallback(() => setTip(null), []);
  const api = useMemo(() => ({ show, move, hide }), [show, move, hide]);

  // Flip to the other side of the pointer near a viewport edge so the tooltip is
  // never clipped; 16px keeps it clear of the cursor itself.
  let style: React.CSSProperties | undefined;
  if (tip) {
    const vw = typeof window === "undefined" ? 1024 : window.innerWidth;
    const vh = typeof window === "undefined" ? 768 : window.innerHeight;
    const flipX = tip.x > vw - 340;
    const flipY = tip.y > vh - 120;
    style = {
      left: flipX ? undefined : tip.x + 16,
      right: flipX ? vw - tip.x + 16 : undefined,
      top: flipY ? undefined : tip.y + 16,
      bottom: flipY ? vh - tip.y + 16 : undefined,
    };
  }

  return (
    <Ctx.Provider value={api}>
      {children}
      {tip && (
        <div className="wcl-tip" style={style} role="tooltip">
          {tip.content}
        </div>
      )}
    </Ctx.Provider>
  );
}
