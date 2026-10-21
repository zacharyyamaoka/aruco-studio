// The sketch's own dimensions (./constraints.ts), drawn as the marker's are
// (./Dims.tsx: extension lines, a dimension line with arrows, the value on
// it), solid: every one drives. A click on a value selects it (Del deletes
// it), a double-click types a new one in place (ValueBox); the D tool's
// preview of the dimension it is about to place is drawn the same way, faint.
import { useRef } from "react";
import type { Vec2 } from "../core/contract";
import { ARROW, DIM_CSS, EXT_GAP, EXT_OVER, FONT_PX, TEXT_H, arrow, fmtDim, textWidth } from "./Dims";
import { dimShapes, measure, refCoord, type DimRef, type SketchDim } from "./constraints";
import type { ProfileRef, Shape } from "./model";

export interface LaidSketchDim {
  dim: SketchDim;
  /** what it measures now (a distance unsigned) */
  value: number;
  text: string;
  /** the measured points on the geometry, and the arrow tips (screen px) */
  a: Vec2; b: Vec2; p: Vec2; q: Vec2;
  inside: boolean; fits: boolean;
  at: Vec2; angle: number; tw: number;
}

const sub = (a: Vec2, b: Vec2): Vec2 => [a[0] - b[0], a[1] - b[1]];
const add = (a: Vec2, b: Vec2, k = 1): Vec2 => [a[0] + b[0] * k, a[1] + b[1] * k];
const unit = (v: Vec2): Vec2 => { const n = Math.hypot(v[0], v[1]) || 1; return [v[0] / n, v[1] / n]; };
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** A reference's point nearest the dimension line (sketch mm): an edge's end
 *  (or where the line crosses it), a centre, or the axis where the line meets it. */
function refPoint(shapes: Shape[], ref: DimRef, axis: "x" | "y", line: number): Vec2 | null {
  const c = refCoord(shapes, ref, axis);
  if (c === null) return null;
  let along = line;
  if ("shape" in ref) {
    const s = shapes.find((x) => x.id === ref.shape);
    if (!s || s.kind === "poly") return null;
    if (ref.at === "c") along = axis === "x" ? s.cy : s.cx;
    else if (s.kind === "rect") along = axis === "x" ? clamp(line, s.cy - s.h / 2, s.cy + s.h / 2) : clamp(line, s.cx - s.w / 2, s.cx + s.w / 2);
  }
  return axis === "x" ? [c, along] : [along, c];
}

/** Lay out one sketch dimension in screen px. null: a shape it names is gone. */
export function laySketchDim(shapes: Shape[], d: SketchDim, scr: (p: Vec2) => Vec2, z: number): LaidSketchDim | null {
  const v = measure(shapes, d);
  const dep = shapes.find((s) => s.id === (d.shape ?? (d.b && "shape" in d.b ? d.b.shape : "")));
  if (v === null || !dep || dep.kind === "poly") return null;
  const C: Vec2 = [dep.cx, dep.cy];
  let A: Vec2, B: Vec2, P: Vec2, Q: Vec2;
  let textAt: Vec2 | null = null;
  if (d.kind === "w" && dep.kind === "rect") {
    const y = C[1] + d.at[1], e = d.at[1] >= 0 ? dep.cy + dep.h / 2 : dep.cy - dep.h / 2;
    A = [dep.cx - dep.w / 2, e]; B = [dep.cx + dep.w / 2, e]; P = [A[0], y]; Q = [B[0], y];
  } else if (d.kind === "h" && dep.kind === "rect") {
    const x = C[0] + d.at[0], e = d.at[0] >= 0 ? dep.cx + dep.w / 2 : dep.cx - dep.w / 2;
    A = [e, dep.cy - dep.h / 2]; B = [e, dep.cy + dep.h / 2]; P = [x, A[1]]; Q = [x, B[1]];
  } else if (d.kind === "d" && dep.kind === "circle") {
    const u = Math.hypot(d.at[0], d.at[1]) > 1e-9 ? unit(d.at) : [1, 0] as Vec2;
    A = add(C, u, -dep.r); B = add(C, u, dep.r); P = A; Q = B;
    textAt = scr(add(C, u, Math.max(Math.hypot(d.at[0], d.at[1]), dep.r + 18 / z)));
  } else if (d.kind === "x" || d.kind === "y") {
    const axis = d.kind;
    const line = axis === "x" ? C[1] + d.at[1] : C[0] + d.at[0];
    const a = refPoint(shapes, d.a!, axis, line), b = refPoint(shapes, d.b!, axis, line);
    if (!a || !b) return null;
    A = a; B = b;
    P = axis === "x" ? [a[0], line] : [line, a[1]];
    Q = axis === "x" ? [b[0], line] : [line, b[1]];
  } else return null;
  const a = scr(A), b = scr(B), p = scr(P), q = scr(Q);
  const dir = unit(sub(q, p));
  const span = Math.hypot(q[0] - p[0], q[1] - p[1]);
  const text = (d.kind === "d" ? "Ø" : "") + fmtDim(Math.abs(v));
  const tw = textWidth(text, true) + 10;
  const inside = span >= 2 * ARROW + 4;
  const fits = !textAt && span >= tw + 2 * ARROW + 4;
  const at: Vec2 = textAt ?? (fits ? [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2] : add(q, dir, ARROW + 6 + tw / 2));
  let angle = textAt ? 0 : (Math.atan2(dir[1], dir[0]) * 180) / Math.PI;
  if (angle >= 90) angle -= 180;
  if (angle < -90) angle += 180;
  return { dim: d, value: Math.abs(v), text, a, b, p, q, inside, fits, at, angle, tw };
}

/** The sketch dims to draw while a feature is in focus and its own marker dims
 *  show: those that measure only the feature's PROFILE shapes are left out, so
 *  the two sets are not drawn on top of each other. Display only: the dims stay
 *  in the document. WHY (Zach, 2026-10-21: "hide the exterior dimensions on the
 *  profile if they are set; it's confusing seeing both sets"); `profile` is
 *  null when the profile shape itself is being edited (an edge click, the D
 *  tool), when its dims come back. A dim that names a shape outside the
 *  profile stays. */
export function visibleSketchDims(dims: LaidSketchDim[], profile: ProfileRef | null): LaidSketchDim[] {
  if (!profile) return dims;
  const own = new Set([profile.outer, ...profile.holes]);
  return dims.filter((d) => {
    const named = dimShapes(d.dim);
    return !(named.length > 0 && named.every((id) => own.has(id)));
  });
}

const CSS = `
.sk-dims .cad-dim.sel line { stroke: var(--pick); }
.sk-dims .cad-dim.sel path.arw { fill: var(--pick); }
.sk-dims .cad-dim.sel .chip { stroke: var(--pick); stroke-width: 1.5; }
.sk-dims .cad-dim.preview { opacity: 0.6; }
.sk-dims .cad-dim.preview .val { pointer-events: none; }
`;

export function SketchDims({ dims, selected, editing, preview, onSelect, onEdit }: {
  dims: LaidSketchDim[];
  selected: string | null;
  /** the dim being typed into (and the D tool's new one): its value is hidden under the box */
  editing: string | null;
  /** the D tool's dim, before it is placed */
  preview: LaidSketchDim | null;
  onSelect: (id: string) => void;
  onEdit: (id: string) => void;
}) {
  const one = (d: LaidSketchDim, faint: boolean) => {
    const dir = unit(sub(d.q, d.p));
    const n = unit(sub(d.p, d.a)), m = unit(sub(d.q, d.b));
    const e0 = add(d.a, n, EXT_GAP), e1 = add(d.p, n, EXT_OVER);
    const f0 = add(d.b, m, EXT_GAP), f1 = add(d.q, m, EXT_OVER);
    const l0 = d.inside ? d.p : add(d.p, dir, -(ARROW + 6));
    const l1 = d.fits || d.dim.kind === "d" ? d.q : add(d.at, dir, -d.tw / 2);
    const id = d.dim.id;
    const cls = ["cad-dim", "set", faint && "preview", !faint && selected === id && "sel"].filter(Boolean).join(" ");
    return (
      <g key={faint ? "preview" : id} className={cls} data-sketch-dim={faint ? undefined : id} data-preview={faint ? "1" : undefined}
        data-kind={d.dim.kind} data-value={d.value}>
        {d.dim.kind !== "d" && <line className="ext" x1={e0[0]} y1={e0[1]} x2={e1[0]} y2={e1[1]} />}
        {d.dim.kind !== "d" && <line className="ext" x1={f0[0]} y1={f0[1]} x2={f1[0]} y2={f1[1]} />}
        <line className="dl" x1={l0[0]} y1={l0[1]} x2={l1[0]} y2={l1[1]} />
        {d.dim.kind === "d" && <line className="ext" x1={d.q[0]} y1={d.q[1]} x2={d.at[0]} y2={d.at[1]} />}
        <path className="arw" data-tip="a" d={arrow(d.p, d.inside ? d.q : add(d.p, dir, -1))} />
        <path className="arw" data-tip="b" d={arrow(d.q, d.inside ? d.p : add(d.q, dir, 1))} />
        {editing !== id && (
          <g className="val" data-sdim-label={faint ? undefined : id} transform={`rotate(${d.angle} ${d.at[0]} ${d.at[1]})`}
            // WHY the left button only: a right-drag (the selection box) may start on a label
            onPointerDown={(e) => { if (e.button !== 0) return; e.stopPropagation(); onSelect(id); }}
            onDoubleClick={(e) => { e.stopPropagation(); onEdit(id); }}>
            <title>{`${d.text} mm, driving: double-click to change it, Del deletes it`}</title>
            <rect className="chip" x={d.at[0] - d.tw / 2} y={d.at[1] - TEXT_H / 2} width={d.tw} height={TEXT_H} rx={3} />
            <text x={d.at[0]} y={d.at[1]} textAnchor="middle" dominantBaseline="central">{d.text}</text>
          </g>
        )}
      </g>
    );
  };
  return (
    <g className="cad-dims sk-dims" data-testid="sketch-dims">
      <style>{DIM_CSS + CSS}</style>
      {dims.map((d) => one(d, false))}
      {preview && one(preview, true)}
    </g>
  );
}

/** A value box over the canvas (Fusion's): Enter sets, Esc drops it, leaving
 *  it sets; Tab is the caller's (the draw boxes switch). The first key typed
 *  replaces the value shown, as in Fusion. */
export function ValueBox({ at, value, testid, label, focus = true, active = true, onType, onCommit, onCancel, onTab }: {
  at: Vec2; value: string; testid: string; label: string;
  /** take the keyboard when shown */
  focus?: boolean;
  /** the box keys go to (the draw boxes: the other one is dimmer) */
  active?: boolean;
  /** controlled (the draw boxes): each change; else the box keeps its own text */
  onType?: (text: string) => void;
  onCommit: (text: string) => void;
  onCancel: () => void;
  onTab?: () => void;
}) {
  const done = useRef(false);
  const fresh = useRef(true);
  const finish = (fn: () => void) => { if (done.current) return; done.current = true; fn(); };
  const w = Math.max(56, textWidth(value, true) + 26);
  return (
    <input className="kit-input dim-edit" data-testid={testid} data-active={active ? "1" : "0"} type="text" inputMode="decimal"
      aria-label={label} autoFocus={focus} {...(onType ? { value } : { defaultValue: value })}
      ref={(el) => { if (el && focus && active && document.activeElement !== el) el.focus({ preventScroll: true }); }}
      onFocus={(e) => { if (!onType) e.currentTarget.select(); }}
      onPointerDown={(e) => e.stopPropagation()}
      onChange={(e) => { fresh.current = false; onType?.(e.currentTarget.value); }}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") { const t = e.currentTarget.value; if (onType) onCommit(t); else finish(() => onCommit(t)); }
        else if (e.key === "Escape") { if (onType) onCancel(); else finish(onCancel); }
        else if (e.key === "Tab") { e.preventDefault(); fresh.current = true; onTab?.(); }
        else if (onType && fresh.current && (/^[0-9.,-]$/.test(e.key) || e.key === "Backspace")) {
          // the first key replaces the live value
          e.preventDefault();
          fresh.current = false;
          onType(e.key === "Backspace" ? "" : e.key);
        }
      }}
      onBlur={(e) => { if (!onType) { const t = e.currentTarget.value; finish(() => onCommit(t)); } }}
      style={{
        position: "absolute", left: at[0] - w / 2, top: at[1] - 11, width: w, height: 22, zIndex: 15,
        textAlign: "center", font: `600 ${FONT_PX + 1}px var(--font)`, color: "var(--text)", background: "var(--panel)",
        border: `1px solid ${active ? "var(--accent)" : "var(--line)"}`, borderRadius: 4, padding: "0 4px", outline: "none",
        boxShadow: "var(--shadow-sm)", opacity: active ? 1 : 0.85,
      }} />
  );
}
