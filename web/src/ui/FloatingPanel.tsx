// A floating command panel (Fusion's feature dialog): a title bar you drag
// it by, a collapse chevron, the body, a footer. Given an `anchor` (the box
// of what it edits, in its container's pixels) it opens beside that box and
// follows it (./anchor.ts); without one it starts at the top-right of its
// container. A drag takes over until the anchor's key changes. It stays
// inside its container. Narrow screens dock it to the bottom (styles.css),
// where it neither drags nor anchors. The kit has no floating panel, so it
// is here; it uses only the kit's tokens.
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@bam/ui";
import { placeBeside, type Box, type Placement } from "./anchor";

export function FloatingPanel({ title, icon, children, footer, collapsed, onCollapse, testid, width = 300, anchor, anchorKey, avoid, className }: {
  title: ReactNode; icon?: ReactNode; children: ReactNode; footer?: ReactNode; collapsed: boolean;
  onCollapse: (c: boolean) => void; testid?: string; width?: number;
  /** the panel's own class, for its layout (never a skin's) */
  className?: string;
  /** the box to open beside (container px), or null for the default spot */
  anchor?: Box | null;
  /** what the anchor is (the feature's id): a new one forgets a drag */
  anchorKey?: string | null;
  /** boxes it should rather not cover (the other markers) */
  avoid?: Box[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  // null: the anchored or default spot; a drag sets left / top in px
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [auto, setAuto] = useState<Placement | null>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);

  useEffect(() => { setPos(null); }, [anchorKey]);

  /** the space the top chrome takes in the container (the Figma layout's
   *  pills, 2026-10-20 night): measured, so the panel never opens or is
   *  dragged under them; 26 px (the ruler) when there is no pill */
  const topClear = (host: HTMLElement): number => {
    const hostTop = host.getBoundingClientRect().top;
    let bottom = 26;
    for (const pill of document.querySelectorAll<HTMLElement>(".pill.doc-pill, .pill.actions-pill")) {
      const r = pill.getBoundingClientRect();
      if (r.height) bottom = Math.max(bottom, r.bottom - hostTop + 8);
    }
    return bottom;
  };

  // beside the anchor, measured after every render: the panel's own height
  // changes with its tab and rows (set only when it moved, so no loop)
  useLayoutEffect(() => {
    const el = ref.current, host = el?.offsetParent as HTMLElement | null;
    if (!el || !host || !anchor || pos || docked()) { if (auto) setAuto(null); return; }
    const body = el.querySelector<HTMLElement>(".fpanel-body");
    const natural = el.offsetHeight - (body?.clientHeight ?? 0) + (body?.scrollHeight ?? 0);
    const p = placeBeside(anchor, { w: el.offsetWidth, h: natural }, { w: host.clientWidth, h: host.clientHeight }, { top: topClear(host) }, avoid);
    const near = (a: number, b: number | undefined) => b !== undefined && Math.abs(a - b) < 0.5;
    if (!auto || !near(p.x, auto.x) || !near(p.y, auto.y) || !near(p.maxH, auto.maxH) || p.side !== auto.side) setAuto(p);
  });

  // keep a dragged panel inside its container when the window shrinks
  useEffect(() => {
    const onResize = () => setPos((p) => (p ? clamp(p.x, p.y) : p));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  });

  const clamp = (x: number, y: number) => {
    const el = ref.current, host = el?.offsetParent as HTMLElement | null;
    if (!el || !host) return { x, y };
    return {
      x: Math.max(0, Math.min(x, host.clientWidth - el.offsetWidth)),
      y: Math.max(topClear(host), Math.min(y, host.clientHeight - 32)),
    };
  };

  const at = pos ?? (auto ? { x: auto.x, y: auto.y } : null);
  return (
    <div ref={ref} className={cn("fpanel", className, collapsed && "collapsed", at && "moved")} data-testid={testid} data-collapsed={collapsed ? "1" : "0"}
      data-anchored={!pos && auto ? auto.side : undefined}
      style={at ? { left: at.x, top: at.y, width, ...(!pos && auto ? { maxHeight: auto.maxH } : {}) } : { width }}>
      <div className="fpanel-head"
        onPointerDown={(e) => {
          if ((e.target as Element).closest("button") || docked()) return;
          const el = ref.current!;
          (e.currentTarget as Element).setPointerCapture(e.pointerId);
          drag.current = { dx: e.clientX - el.offsetLeft, dy: e.clientY - el.offsetTop };
        }}
        onPointerMove={(e) => {
          if (!drag.current) return;
          setPos(clamp(e.clientX - drag.current.dx, e.clientY - drag.current.dy));
        }}
        onPointerUp={() => { drag.current = null; }}
        onDoubleClick={() => onCollapse(!collapsed)}>
        {icon}<span className="fpanel-title">{title}</span>
        <button type="button" className="kit-ib" title={collapsed ? "Expand" : "Collapse"} aria-label={collapsed ? "Expand" : "Collapse"}
          data-testid="panel-collapse" onClick={() => onCollapse(!collapsed)}>
          {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>
      {!collapsed && <div className="fpanel-body">{children}</div>}
      {footer && <div className="fpanel-foot">{footer}</div>}
    </div>
  );
}

function docked(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(max-width: 640px)").matches;
}
