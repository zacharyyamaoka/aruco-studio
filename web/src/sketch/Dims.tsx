// The selected feature's dimensions, drawn CAD-style on the canvas: the
// contract's MarkerPlan.dims (the core measures them on the drawn geometry),
// each with extension lines, a dimension line with arrows and its value on
// it. Driven values are muted grey, set ones solid (white in the dark theme):
// the same isSet() the panel's rows use. A click (or a double-click, as in
// Fusion) on a value types a new one in place; Viewport.tsx owns that editor.
//
// WHY (Zach, 2026-10-18): "just like Fusion they can be in an auto mode where
// they are being driven, or if you set them they turn white". The label's
// offset is left out: "it's not something we need precision positioning of".
//
// WHY only what you set (Zach, 2026-10-18): "do not display measurements here
// that you cannot control". The outer size and the rectangle's W and H are
// left out (W × H stays in ShapeDims' box); a feature shows only the sizes
// its type takes (CONTROLS).
//
// WHY screen-space rings: the core stands each dimension offset_mm outside
// the box it placed the marker in (MarkerPlan.fit_rect: "the rectangle"
// below), rings a few mm apart, which collapse into one line when
// zoomed out. Here the core's order on each side is kept but the rings are
// whole pixels apart, so the values stay legible at any zoom; a value that
// would still overlap one already placed is hidden. Every line stands outside
// the rectangle, so none crosses the marker's ink.
import { useEffect, useRef } from "react";
import type { Dimension, MarkerPlan, Rect, Vec2 } from "../core/contract";
import { isSet, type Feature } from "../model/doc";
import { toLocal } from "../model/geom";

const GAP = 14;               // px from the rectangle's edge to the first ring
const RING = 22;              // px between rings
export const ARROW = 8;       // arrowhead length, px
export const EXT_GAP = 3;     // px between the geometry and its extension line
export const EXT_OVER = 4;    // px an extension line runs past the dimension line
export const TEXT_H = 15;     // the value's chip height, px
export const FONT_PX = 11;
const LIVE_MS = 120;          // a typed value sets this long after the last keystroke, as the label's text does

/** The dims each marker type draws: the sizes typed into it, and only those. */
const CONTROLS: Record<string, string[]> = {
  single: ["marker.marker_mm"],
  grid: ["marker.marker_mm", "marker.separation_mm"],
  charuco: ["marker.checker_mm", "marker.marker_mm"],
};

/** Which dims stay when they would overlap: the first wins. */
const PRIORITY = ["marker.marker_mm", "marker.checker_mm", "marker.separation_mm"];

const NAMES: Record<string, string> = {
  "marker.marker_mm": "Marker", "marker.checker_mm": "Checker", "marker.separation_mm": "Separation",
};

export const fmtDim = (v: number) => String(+v.toFixed(2));

/** A set marker size as typed. The core may draw it a hair off (a whole
 *  number of the preset's cells), so a set dim shows what drives it, as the
 *  panel's row does, and its line measures what is drawn. */
function typed(f: Feature, field: string): number | null {
  if (field === "marker.marker_mm") return f.marker.marker_mm;
  if (field === "marker.checker_mm") return f.marker.checker_mm;
  if (field === "marker.separation_mm") return f.marker.separation_mm;
  return null;
}

export interface LaidDim {
  key: string;
  field: string;
  /** what is drawn: the plan's value_mm, as long as the line between the tips */
  value: number;
  /** what the value shows: the typed value when set, else the drawn one */
  text: string;
  /** set (typed) vs driven */
  set: boolean;
  bad: boolean;
  /** the measured points on the geometry, and the arrow tips (screen px) */
  a: Vec2; b: Vec2; p: Vec2; q: Vec2;
  /** arrows inside the span (else outside, pointing in); the value between them */
  inside: boolean; fits: boolean;
  /** the value's centre, its angle (deg, readable) and its chip size */
  at: Vec2; angle: number; tw: number;
}

let ctx: CanvasRenderingContext2D | null | undefined;
export function textWidth(text: string, bold: boolean): number {
  if (ctx === undefined) ctx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
  if (!ctx) return text.length * 7;
  const family = getComputedStyle(document.documentElement).getPropertyValue("--font").trim() || "sans-serif";
  ctx.font = `${bold ? 600 : 400} ${FONT_PX}px ${family}`;
  return ctx.measureText(text).width;
}

const sub = (a: Vec2, b: Vec2): Vec2 => [a[0] - b[0], a[1] - b[1]];
const add = (a: Vec2, b: Vec2, k = 1): Vec2 => [a[0] + b[0] * k, a[1] + b[1] * k];
const unit = (v: Vec2): Vec2 => { const n = Math.hypot(v[0], v[1]) || 1; return [v[0] / n, v[1] / n]; };

type Side = "top" | "bottom" | "left" | "right";

/** Lay out the plan's dims for one feature in screen px (scr: sketch -> screen),
 *  standing outside `rect`: the box the core placed the marker in. */
export function layoutDims(f: Feature, rect: Rect, plan: MarkerPlan, scr: (p: Vec2) => Vec2, z: number): LaidDim[] {
  const fields = CONTROLS[f.marker.type] ?? [];
  const dims = (plan.dims ?? []).filter((d) => fields.includes(d.field) && Math.hypot(d.b[0] - d.a[0], d.b[1] - d.a[1]) > 1e-6);
  // each dim's side of the rectangle (its offset normal in the rectangle's frame) and how far its geometry is inside that edge
  const placed = dims.map((d, i) => {
    const u = unit(sub(d.b, d.a));
    const nw: Vec2 = [-u[1], u[0]];                  // left of a->b: where the core stands it
    const o = toLocal(rect, [0, 0]), e = toLocal(rect, nw);
    const nl: Vec2 = [e[0] - o[0], e[1] - o[1]];
    const side: Side = Math.abs(nl[0]) > Math.abs(nl[1]) ? (nl[0] > 0 ? "right" : "left") : (nl[1] > 0 ? "top" : "bottom");
    const inset = (p: Vec2) => {
      const [x, y] = toLocal(rect, p);
      return side === "top" ? rect.h / 2 - y : side === "bottom" ? y + rect.h / 2 : side === "right" ? rect.w / 2 - x : x + rect.w / 2;
    };
    return { d, i, nw, side, edge: Math.max(0, inset(d.a), inset(d.b)) };
  });
  const rings = new Map<number, number>();
  for (const side of ["top", "bottom", "left", "right"] as Side[]) {
    placed.filter((x) => x.side === side).sort((x, y) => x.d.offset_mm - y.d.offset_mm || x.i - y.i).forEach((x, r) => rings.set(x.i, r));
  }
  const errors = new Set(plan.warnings.filter((w) => w.level === "error").map((w) => w.field));
  const out = placed.map(({ d, i, nw, edge }) => laidOne(f, d, i, nw, edge * z + GAP + (rings.get(i) ?? 0) * RING, scr, errors));
  return hideOverlaps(out);
}

function laidOne(f: Feature, d: Dimension, i: number, nw: Vec2, off: number, scr: (p: Vec2) => Vec2, errors: Set<string>): LaidDim {
  const A = scr(d.a), B = scr(d.b);
  const n = unit(sub(scr(add(d.a, nw)), A));
  const p = add(A, n, off), q = add(B, n, off);
  const dir = unit(sub(q, p));
  const span = Math.hypot(q[0] - p[0], q[1] - p[1]);
  const set = isSet(f, d.field);
  const text = fmtDim((set ? typed(f, d.field) : null) ?? d.value_mm);
  const tw = textWidth(text, set) + 10;
  const inside = span >= 2 * ARROW + 4;
  // the value on the line when it fits between the arrows, else past the b end
  const fits = span >= tw + 2 * ARROW + 4;
  const at: Vec2 = fits ? [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2] : add(q, dir, ARROW + 6 + tw / 2);
  let angle = (Math.atan2(dir[1], dir[0]) * 180) / Math.PI;
  // readable from below or from the right, as a drawing's dimensions are
  if (angle >= 90) angle -= 180;
  if (angle < -90) angle += 180;
  const bad = set && errors.has(d.field);
  return {
    key: `${d.field}:${i}`, field: d.field, value: d.value_mm, text, set, bad,
    a: A, b: B, p, q, inside, fits, at, angle, tw,
  };
}

/** The value chip's axis-aligned box (px). */
export function chipBox(d: Pick<LaidDim, "at" | "angle" | "tw">): { x0: number; y0: number; x1: number; y1: number } {
  const t = (d.angle * Math.PI) / 180, c = Math.abs(Math.cos(t)), s = Math.abs(Math.sin(t));
  const hx = (c * d.tw + s * TEXT_H) / 2, hy = (s * d.tw + c * TEXT_H) / 2;
  return { x0: d.at[0] - hx, y0: d.at[1] - hy, x1: d.at[0] + hx, y1: d.at[1] + hy };
}

function hideOverlaps(dims: LaidDim[]): LaidDim[] {
  const rank = (d: LaidDim) => { const k = PRIORITY.indexOf(d.field); return k < 0 ? PRIORITY.length : k; };
  const kept: LaidDim[] = [];
  for (const d of [...dims].sort((x, y) => rank(x) - rank(y))) {
    const b = chipBox(d);
    const hits = kept.some((k) => {
      const o = chipBox(k);
      return b.x0 < o.x1 + 2 && o.x0 < b.x1 + 2 && b.y0 < o.y1 + 2 && o.y0 < b.y1 + 2;
    });
    if (!hits) kept.push(d);
  }
  return dims.filter((d) => kept.includes(d));
}

/** The dims' look, shared with the sketch's own dims (SketchDims.tsx). */
export const DIM_CSS = `
.cad-dim .val, .cad-dim .val * { pointer-events: auto; }
.cad-dim line { stroke: var(--muted); stroke-width: 1; }
.cad-dim line.ext { stroke-width: 0.7; }
.cad-dim path.arw { fill: var(--muted); }
.cad-dim .chip { fill: var(--canvas); }
.cad-dim text { fill: var(--muted); font: 400 ${FONT_PX}px var(--font); }
.cad-dim.set line { stroke: var(--text); }
.cad-dim.set path.arw { fill: var(--text); }
.cad-dim.set .chip { fill: var(--panel); stroke: var(--line); stroke-width: 1; }
.cad-dim.set text { fill: var(--text); font-weight: 600; }
.cad-dim.bad line { stroke: var(--bad); }
.cad-dim.bad path.arw { fill: var(--bad); }
.cad-dim.bad text { fill: var(--bad); font-weight: 600; }
.cad-dim .val { cursor: text; }
.cad-dim .val:hover .chip { stroke: var(--accent); stroke-width: 1; }
`;

/** An arrowhead, its tip first (the e2e reads the tip as the path's first point). */
export const arrow = (tip: Vec2, toward: Vec2) => {
  const u = unit(sub(toward, tip)), w: Vec2 = [-u[1], u[0]];
  const base = add(tip, u, ARROW);
  const l = add(base, w, 3), r = add(base, w, -3);
  return `M${tip[0]} ${tip[1]}L${l[0]} ${l[1]}L${r[0]} ${r[1]}Z`;
};

export function Dims({ fid, dims, editing, onEdit }: {
  fid: string; dims: LaidDim[];
  /** the field being typed into: its value is hidden under the editor */
  editing: string | null;
  onEdit: (field: string) => void;
}) {
  return (
    <g className="cad-dims" data-testid="dims" data-feature={fid}>
      <style>{DIM_CSS}</style>
      {dims.map((d) => {
        const dir = unit(sub(d.q, d.p));
        const n = unit(sub(d.p, d.a));
        const e0 = add(d.a, n, EXT_GAP), e1 = add(d.p, n, EXT_OVER);
        const f0 = add(d.b, n, EXT_GAP), f1 = add(d.q, n, EXT_OVER);
        // arrows inside point out to the tips; outside they point in, on short leaders
        const l0 = d.inside ? d.p : add(d.p, dir, -(ARROW + 6));
        const l1 = d.fits ? d.q : add(d.at, dir, -d.tw / 2);
        const cls = ["cad-dim", d.set ? "set" : "driven", d.bad && "bad"].filter(Boolean).join(" ");
        return (
          <g key={d.key} className={cls} data-dim={d.field} data-value={d.value} data-set={d.set ? "1" : "0"}>
            <line className="ext" x1={e0[0]} y1={e0[1]} x2={e1[0]} y2={e1[1]} />
            <line className="ext" x1={f0[0]} y1={f0[1]} x2={f1[0]} y2={f1[1]} />
            <line className="dl" x1={l0[0]} y1={l0[1]} x2={l1[0]} y2={l1[1]} />
            <path className="arw" data-tip="a" d={arrow(d.p, d.inside ? d.q : add(d.p, dir, -1))} />
            <path className="arw" data-tip="b" d={arrow(d.q, d.inside ? d.p : add(d.q, dir, 1))} />
            {editing !== d.field && (
              <g className="val" data-dim-label={d.field} transform={`rotate(${d.angle} ${d.at[0]} ${d.at[1]})`}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => onEdit(d.field)}
                onDoubleClick={() => onEdit(d.field)}>
                <title>{`${NAMES[d.field] ?? d.field}: ${d.text} mm, ${d.set ? "set" : "driven"}`
                  + (d.text !== fmtDim(d.value) ? ` (drawn ${fmtDim(d.value)} mm: whole cells)` : "")}</title>
                <rect className="chip" x={d.at[0] - d.tw / 2} y={d.at[1] - TEXT_H / 2} width={d.tw} height={TEXT_H} rx={3} />
                <text x={d.at[0]} y={d.at[1]} textAnchor="middle" dominantBaseline="central">{d.text}</text>
              </g>
            )}
          </g>
        );
      })}
    </g>
  );
}

/** The in-place editor over a dim's value: the marker follows as you type
 *  (`onLive`, LIVE_MS after the last keystroke); Enter sets, an empty Enter
 *  returns it to driven, Esc puts back the value from when it opened;
 *  leaving the field commits, as the panel's rows do.
 *
 *  WHY live (Zach, 2026-10-20): "when I manually edit the dimensions, they
 *  should update in real time!" */
export function DimEditor({ dim, onLive, onCommit, onCancel }: {
  dim: LaidDim; onLive: (text: string) => void; onCommit: (text: string) => void; onCancel: () => void;
}) {
  const done = useRef(false);
  const pending = useRef<{ t: ReturnType<typeof setTimeout>; v: string; to: (v: string) => void } | null>(null);
  const live = useRef(onLive);
  live.current = onLive;
  const cancel = () => { if (pending.current) clearTimeout(pending.current.t); pending.current = null; };
  const finish = (fn: () => void) => { cancel(); if (done.current) return; done.current = true; fn(); };
  // closed without Enter, Esc or a blur (another feature selected): what was typed still lands, on its own feature
  useEffect(() => () => { const p = pending.current; cancel(); if (p && !done.current) p.to(p.v); }, []);
  const w = Math.max(56, dim.tw + 16);
  return (
    <input className="kit-input dim-edit" data-testid="dim-input" data-dim-edit={dim.field} type="text" inputMode="decimal"
      defaultValue={dim.text} autoFocus aria-label={`${NAMES[dim.field] ?? dim.field} (mm)`}
      onFocus={(e) => e.currentTarget.select()}
      onPointerDown={(e) => e.stopPropagation()}
      onChange={(e) => {
        const v = e.currentTarget.value;
        cancel();
        // WHY the onLive of THIS render: it names the feature typed into, so a
        // click on another marker within LIVE_MS cannot land the value there
        const to = live.current;
        pending.current = { t: setTimeout(() => { pending.current = null; to(v); }, LIVE_MS), v, to };
      }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") { const t = e.currentTarget.value; finish(() => onCommit(t)); }
        else if (e.key === "Escape") finish(onCancel);
      }}
      onBlur={(e) => { const t = e.currentTarget.value; finish(() => onCommit(t)); }}
      style={{
        position: "absolute", left: dim.at[0] - w / 2, top: dim.at[1] - 11, width: w, height: 22, zIndex: 15,
        textAlign: "center", font: `600 ${FONT_PX + 1}px var(--font)`, color: "var(--text)", background: "var(--panel)",
        border: "1px solid var(--accent)", borderRadius: 4, padding: "0 4px", outline: "none", boxShadow: "var(--shadow-sm)",
      }} />
  );
}
