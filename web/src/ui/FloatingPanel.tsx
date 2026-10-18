// A floating command panel (Fusion's feature dialog): a title bar you drag
// it by, a collapse chevron, the body, a footer. It starts at the top-right
// of its container and stays inside it. Narrow screens dock it to the
// bottom (styles.css), where it does not drag. The kit has no floating
// panel, so it is here; it uses only the kit's tokens.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@bam/ui";

export function FloatingPanel({ title, icon, children, footer, collapsed, onCollapse, testid, width = 300 }: {
  title: ReactNode; icon?: ReactNode; children: ReactNode; footer?: ReactNode; collapsed: boolean;
  onCollapse: (c: boolean) => void; testid?: string; width?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // null: the default spot (top-right, by CSS); a drag sets left / top in px
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);

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
      y: Math.max(0, Math.min(y, host.clientHeight - 32)),
    };
  };

  const docked = () => typeof window !== "undefined" && window.matchMedia?.("(max-width: 640px)").matches;

  return (
    <div ref={ref} className={cn("fpanel", collapsed && "collapsed", pos && "moved")} data-testid={testid} data-collapsed={collapsed ? "1" : "0"}
      style={pos ? { left: pos.x, top: pos.y, width } : { width }}>
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
