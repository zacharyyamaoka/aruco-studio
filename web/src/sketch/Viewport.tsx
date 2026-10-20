// The sketch viewport: renders the sketch model (./model.ts) and what the
// core planned, and turns pointer events into the store's actions. y up,
// millimetres; pan with the middle or right button or Space-drag, zoom at
// the cursor, F fits. Every feature's marker, outline, Joint Origin and
// label are drawn as its plan() returned them: no marker geometry is made
// here. The sticker's white is the plan's cut_shape (the trim: the profile
// with its holes, or the quiet zone), under the marker. The turn arc belongs
// to the feature in focus; the selected feature's dimensions (./Dims.tsx)
// stand outside the box the core placed its marker in (MarkerPlan.fit_rect)
// and are typed into in place, the marker following as you type. A drag
// (move, resize, the label) is one undo step; moving or resizing a profile's
// shapes re-plans its marker (a rectangle profile: the marker follows it).
import { useEffect, useRef, useState, type ReactElement } from "react";
import type { MarkerPlan, Polygon, Rect, Vec2 } from "../core/contract";
import {
  featureOfProfile, featureOfRect, featureRect, getFeature, isSet, rectProfile, resetField, setField, updateFeature, type Doc, type Feature,
} from "../model/doc";
import {
  boxOf, fromLocal, handlePoint, HANDLES, loopD, niceStep, rectCorners, rectFromCorners, toLocal, toScreen, toWorld, zoomAt,
  type Handle,
} from "../model/geom";
import { activeFeatureId, selectedFeatureId, useStudio } from "../store";
import { DimEditor, Dims, layoutDims, type LaidDim } from "./Dims";
import {
  circleFrom, hitTest, inShape, moveShape, profileLoops, rectAt, rectOf, resizeShape, sameProfile, shapeLoop,
  type Hit, type ProfileRef, type Shape,
} from "./model";

type Drag =
  | { kind: "pan"; sx: number; sy: number; cx: number; cy: number }
  | { kind: "move"; id: string; from: Vec2; orig: Shape; moved: boolean }
  | { kind: "resize"; id: string; handle: Handle; orig: Shape }
  | { kind: "label"; fid: string; from: Vec2; orig: Vec2; at: Vec2 }
  | { kind: "draw"; tool: "rect" | "circle"; a: Vec2; b: Vec2 };

const EDGE_PX = 6;
// WHY: the core stacks a label's lines (1 + LINE_GAP) caps apart
// (aruco_studio/core/rect_fill.py LINE_GAP, the pixel font's 2 px of 5)
const LINE_GAP = 0.4;
const RULER = 18;

const fmt = (v: number) => String(+v.toFixed(1));
// WHY inline (the stylesheet is not this lane's): the white is the paper's,
// the outline only draws the quiet-zone edge over it (and still takes a click)
const WHITE = { fill: "var(--t-white)", stroke: "none" };
const OUTLINE = { fill: "transparent" };

/** What the sticker is cut to: the plan's cut_shape, else (a core without
 *  trim, the mock) its cut, else the marker's outline as before. */
const cutShape = (p: MarkerPlan): Polygon => p.cut_shape ?? { outer: p.cut ?? p.outer, holes: [] };

/** The box the core placed a feature's marker in: the plan's fit_rect, else
 *  (a core from before barrier 9) the rectangle profile, else the outline's box. */
function placeBox(doc: Doc, f: Feature, plan: MarkerPlan): Rect {
  if (plan.fit_rect) return plan.fit_rect;
  const r = featureRect(doc, f);
  if (r) return rectOf(r);
  const b = boxOf(plan.outer);
  return { cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, w: b.x1 - b.x0, h: b.y1 - b.y0, angle_deg: 0 };
}

/** How long after a Profile-row pick a double-click still picks for the panel
 *  (its first click picked the region; the double-click means the rectangle). */
const DBL_MS = 700;

export function Viewport() {
  const host = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const doc = useStudio((s) => s.doc);
  const camera = useStudio((s) => s.camera);
  const view = useStudio((s) => s.view);
  const sel = useStudio((s) => s.sel);
  const tool = useStudio((s) => s.tool);
  const plans = useStudio((s) => s.plans);
  const panel = useStudio((s) => s.panel);
  const [hover, setHover] = useState<Hit>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [labelAt, setLabelAt] = useState<{ fid: string; at: Vec2 } | null>(null);
  /** the dimension being typed into, and its feature as it was when the editor opened (Esc puts it back) */
  const [dimEdit, setDimEdit] = useState<{ fid: string; field: string; start: Feature } | null>(null);
  const lastDim = useRef<LaidDim | null>(null);
  /** the last Profile-row pick: a double-click right after it re-picks for the same feature */
  const picked = useRef<{ fid: string; at: number } | null>(null);
  const space = useRef(false);
  const fitted = useRef(false);

  const { w, h } = view;
  const z = camera.zoom;

  // the view's size; the first real size fits the sketch
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      useStudio.getState().setView(Math.round(r.width), Math.round(r.height));
      if (!fitted.current) { fitted.current = true; useStudio.getState().fit(); }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const st = useStudio.getState();
      const r = el.getBoundingClientRect();
      const k = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015));
      st.setCamera(zoomAt(st.camera, st.view.w, st.view.h, [e.clientX - r.left, e.clientY - r.top], k));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    const kd = (e: KeyboardEvent) => { if (e.code === "Space" && !(e.target as Element)?.closest?.("input,textarea")) space.current = true; };
    const ku = (e: KeyboardEvent) => { if (e.code === "Space") space.current = false; };
    window.addEventListener("keydown", kd);
    window.addEventListener("keyup", ku);
    return () => {
      el.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", kd);
      window.removeEventListener("keyup", ku);
    };
  }, []);

  // WHY (2026-10-18 review): on a phone the panel (and the toolbar above it)
  // docks over the bottom of the canvas, so when it opens on a feature (and again once that feature first
  // plans) the canvas fits the marker into the part above the panel
  const editId = panel.open ? panel.featureId : null;
  const editProfile = editId ? JSON.stringify(doc.features.find((f) => f.id === editId)?.profile ?? null) : null;
  const editPlanned = !!(editId && plans[editId]);
  useEffect(() => {
    if (!editId || !editProfile || editProfile === "null" || !window.matchMedia?.("(max-width: 640px)").matches) return;
    const raf = requestAnimationFrame(() => {
      const vp = host.current?.getBoundingClientRect();
      if (!vp) return;
      // what covers the canvas from below: the panel and the toolbar above it
      const tops = ['[data-testid="extrude-panel"]', '[data-testid="toolbar"]']
        .map((q) => document.querySelector(q)?.getBoundingClientRect().top ?? vp.bottom);
      useStudio.getState().fitFeature(editId, RULER, Math.max(0, vp.bottom - Math.min(...tops)));
    });
    return () => cancelAnimationFrame(raf);
  }, [editId, editProfile, editPlanned]);

  // Esc while drawing drops the draft (the app's Esc does the rest)
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setDrag((d) => (d?.kind === "draw" ? null : d)); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  const local = (e: { clientX: number; clientY: number }): Vec2 => {
    const r = host.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const world = (e: { clientX: number; clientY: number }): Vec2 => toWorld(camera, w, h, local(e));
  const scr = (p: Vec2): Vec2 => toScreen(camera, w, h, p);

  /** The shape the handles and a drag inside act on: the selected shape, or
   *  the selected feature's rectangle profile. */
  const selectedShape = (): Shape | undefined => {
    const st = useStudio.getState();
    const s = st.sel;
    if (s?.kind === "shape") return st.doc.shapes.find((x) => x.id === s.id);
    if (s?.kind === "feature" || s?.kind === "origin" || s?.kind === "text") return featureRect(st.doc, getFeature(st.doc, s.id)) ?? undefined;
    return undefined;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    const st = useStudio.getState();
    const target = e.target as Element;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    if (e.button === 1 || e.button === 2 || space.current) {
      setDrag({ kind: "pan", sx: e.clientX, sy: e.clientY, cx: camera.cx, cy: camera.cy });
      return;
    }
    if (e.button !== 0) return;
    const p = world(e);
    const hEl = target.closest("[data-handle]");
    if (hEl) {
      const orig = selectedShape();
      if (orig) { st.gesture(true); setDrag({ kind: "resize", id: orig.id, handle: hEl.getAttribute("data-handle") as Handle, orig }); }
      return;
    }
    const turnEl = target.closest("[data-turn]");
    if (turnEl) { st.turn(turnEl.getAttribute("data-feature") ?? undefined); return; }
    const labelEl = target.closest("[data-label]");
    const lf = labelEl ? getFeature(st.doc, labelEl.getAttribute("data-feature")) : null;
    const lp = lf ? st.plans[lf.id]?.label : null;
    if (lf && lp) {
      st.gesture(true);
      setDrag({ kind: "label", fid: lf.id, from: p, orig: lf.label.offset_mm, at: lp.at });
      st.select({ kind: "text", id: lf.id });
      return;
    }
    if (tool === "rect" || tool === "circle") {
      setDrag({ kind: "draw", tool, a: p, b: p });
      return;
    }
    const hit = hitTest(st.doc.shapes, p, EDGE_PX / z);
    const selShape = selectedShape();
    const move = (sh: Shape) => { st.gesture(true); setDrag({ kind: "move", id: sh.id, from: p, orig: sh, moved: false }); };
    // WHY WYSIWYG (Zach, 2026-10-18): "just clicking the marker on the screen is
    // what brings up the relevant inspector window". A click on a marker selects
    // the feature and opens its panel; a press-drag on a rectangle profile's
    // marker moves the rectangle, and the marker follows (the custom placement).
    // A marker placed in a face does not drag the face. Empty canvas closes it.
    const markerId = st.panel.selector ? null : target.closest("[data-marker]")?.getAttribute("data-marker");
    const markerOf = markerId ? getFeature(st.doc, markerId) : null;
    if (markerId && markerOf) {
      st.inspect(markerId);
      const r = featureRect(st.doc, markerOf);
      if (r) move(r);
      return;
    }
    if (hit?.kind === "edge") {
      // the Profile row takes a region or a double-clicked rectangle, not an edge
      if (st.panel.selector) return;
      const s = st.doc.shapes.find((x) => x.id === hit.id)!;
      const owner = featureOfRect(st.doc, s.id);
      if (owner) st.inspect(owner.id);
      else { if (st.panel.open) st.ok(); st.select({ kind: "shape", id: s.id }); }
      move(s);
      return;
    }
    // inside the selected shape: drag it (as after picking it in a CAD)
    if (selShape && inShape(selShape, p)) {
      move(selShape);
      return;
    }
    if (hit?.kind === "region") {
      if (st.panel.open && st.panel.selector) { pickProfile(hit.ref); return; }
      const owner = featureOfProfile(st.doc, hit.ref);
      if (owner) {
        st.inspect(owner.id);
        const r = featureRect(st.doc, owner);
        if (r) move(r);
        return;
      }
      if (st.panel.open) st.ok();
      st.select({ kind: "profile", ref: hit.ref });
      return;
    }
    st.closePanel();
  };

  /** The Profile row's pick, noted so a double-click that follows re-picks. */
  const pickProfile = (ref: ProfileRef) => {
    const st = useStudio.getState();
    const fid = st.panel.featureId;
    st.useProfile(ref);
    picked.current = fid ? { fid, at: performance.now() } : null;
  };

  /** A double-click on a rectangle (its edge or inside it): its outer edges
   *  alone are the profile, whatever is inside it (Zach, 2026-10-20 evening:
   *  "you could double click on a rectangle and it would select the outer
   *  edges"). For the Profile row while it waits (or right after its first
   *  click picked the region), else as the selection. */
  const onDoubleClick = (e: React.MouseEvent) => {
    const st = useStudio.getState();
    const target = e.target as Element;
    if (tool !== "select" || e.button !== 0) return;
    if (target.closest("[data-dim-label],[data-label],[data-turn],[data-handle],input")) return;
    const p = world(e);
    const onEdge = hitTest(st.doc.shapes, p, EDGE_PX / z)?.kind === "edge";
    // a marker is its feature's: a double-click on it picks nothing else
    if (!onEdge && target.closest("[data-marker]")) return;
    const r = rectAt(st.doc.shapes, p, EDGE_PX / z);
    if (!r) return;
    const ref = rectProfile(r.id);
    const last = picked.current;
    const forPanel = st.panel.open && (st.panel.selector === "profile"
      || (!!last && last.fid === st.panel.featureId && performance.now() - last.at < DBL_MS));
    if (forPanel) { pickProfile(ref); return; }
    const owner = featureOfProfile(st.doc, ref);
    if (owner) { st.inspect(owner.id); return; }
    if (st.panel.open) st.ok();
    st.select({ kind: "profile", ref });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const st = useStudio.getState();
    if (!drag) {
      if (tool === "select") setHover(hitTest(st.doc.shapes, world(e), EDGE_PX / z));
      else if (hover) setHover(null);
      return;
    }
    if (drag.kind === "pan") {
      st.setCamera({ ...camera, cx: drag.cx - (e.clientX - drag.sx) / z, cy: drag.cy + (e.clientY - drag.sy) / z });
      return;
    }
    const p = world(e);
    if (drag.kind === "draw") setDrag({ ...drag, b: p });
    else if (drag.kind === "move") {
      const dx = p[0] - drag.from[0], dy = p[1] - drag.from[1];
      if (!drag.moved && Math.hypot(dx, dy) * z < 3) return;
      if (!drag.moved) setDrag({ ...drag, moved: true });
      st.updateShape(moveShape(drag.orig, dx, dy));
    } else if (drag.kind === "resize") st.updateShape(resizeShape(drag.orig, drag.handle, p));
    else if (drag.kind === "label") {
      const dx = p[0] - drag.from[0], dy = p[1] - drag.from[1];
      setLabelAt({ fid: drag.fid, at: [drag.at[0] + dx, drag.at[1] + dy] });
      st.setLabel("offset_mm", [+(drag.orig[0] + dx).toFixed(1), +(drag.orig[1] + dy).toFixed(1)], drag.fid);
    }
  };

  const onPointerUp = () => {
    const st = useStudio.getState();
    if (drag?.kind === "draw") {
      const id = `${drag.tool === "rect" ? "r" : "c"}${Date.now().toString(36)}`;
      if (drag.tool === "rect") {
        const r = rectFromCorners(drag.a, drag.b);
        if (r.w >= 1 && r.h >= 1) { st.addShape({ kind: "rect", id, ...r }); st.setTool("select"); }
      } else {
        const c = circleFrom(drag.a, drag.b, id);
        if (c.r >= 0.5) { st.addShape(c); st.setTool("select"); }
      }
    }
    if (drag?.kind === "label") setLabelAt(null);
    if (drag?.kind === "move" || drag?.kind === "resize" || drag?.kind === "label") st.gesture(false);
    setDrag(null);
  };

  // ------------------------------------------------------------ the grid and rulers
  const step = niceStep(z);
  const minor = step / 5;
  const [wx0, wy1] = toWorld(camera, w, h, [0, 0]);
  const [wx1, wy0] = toWorld(camera, w, h, [w, h]);
  const grid: ReactElement[] = [];
  if (minor * z >= 6) {
    for (let x = Math.ceil(wx0 / minor) * minor; x <= wx1; x += minor) {
      const sx = scr([x, 0])[0];
      const major = Math.abs(x / step - Math.round(x / step)) < 1e-6;
      grid.push(<line key={`gx${x.toFixed(3)}`} x1={sx} x2={sx} y1={0} y2={h} className={Math.abs(x) < 1e-9 ? "g axis" : major ? "g major" : "g"} />);
    }
    for (let y = Math.ceil(wy0 / minor) * minor; y <= wy1; y += minor) {
      const sy = scr([0, y])[1];
      const major = Math.abs(y / step - Math.round(y / step)) < 1e-6;
      grid.push(<line key={`gy${y.toFixed(3)}`} y1={sy} y2={sy} x1={0} x2={w} className={Math.abs(y) < 1e-9 ? "g axis" : major ? "g major" : "g"} />);
    }
  }
  const ticks: ReactElement[] = [];
  for (let x = Math.ceil(wx0 / step) * step; x <= wx1; x += step) {
    const sx = scr([x, 0])[0];
    ticks.push(<text key={`tx${x}`} x={sx + 3} y={12}>{+x.toFixed(2)}</text>);
  }
  for (let y = Math.ceil(wy0 / step) * step; y <= wy1; y += step) {
    const sy = scr([0, y])[1];
    ticks.push(<text key={`ty${y}`} x={3} y={sy - 3}>{+y.toFixed(2)}</text>);
  }

  // ------------------------------------------------------------ the sketch
  // WHY screen space: every path is drawn in pixels (not a scaled group), so
  // strokes stay one width at any zoom and a path's box is its geometry's box.
  const sl = (loop: Vec2[]) => loopD(loop.map(scr));
  const shapes = doc.shapes;
  const regionsD = shapes.map((s) => sl(shapeLoop(s))).join("");
  const hoverRef = hover?.kind === "region" ? hover.ref : null;
  const selRef = sel?.kind === "profile" ? sel.ref : null;
  const profD = (ref: typeof hoverRef) => {
    const pr = ref && profileLoops(shapes, ref);
    return pr ? pr.loops.map(sl).join("") : "";
  };
  const selShape = selectedShape();
  const selId = selShape?.id ?? null;
  // every feature that has a profile and a plan, with the box its marker was
  // placed in; the one in focus gets the turn arc
  const drawn = doc.features
    .filter((f) => !!f.profile && !!plans[f.id])
    .map((f) => ({ f, plan: plans[f.id], rect: placeBox(doc, f, plans[f.id]) }));
  const activeId = activeFeatureId({ doc, sel, panel });
  const featureRects = new Set(doc.features.map((f) => featureRect(doc, f)?.id));

  // the selected feature's dimensions (the panel's feature, or the one the selection names)
  const dimFid = panel.open ? panel.featureId : selectedFeatureId(doc, sel);
  const dimOf = drawn.find((d) => d.f.id === dimFid);
  const laid: LaidDim[] = dimOf ? layoutDims(dimOf.f, dimOf.rect, dimOf.plan, scr, z) : [];
  // WHY draw the fit box (dashed, faint, only for the selected feature, only
  // when the profile is not itself a rectangle): with the core placing the
  // marker, the box it chose is what the dims, the label band and overflow are
  // measured against, so it has to be visible; dashed reads as construction
  // geometry (not a shape to pick or a cut line), and drawing it on every
  // marker, or over a rectangle profile's own edges, would only repeat lines.
  const fitBoxOf = dimOf && !featureRect(doc, dimOf.f) && dimOf.plan.fit_rect ? dimOf : null;
  // the editor stays over the value's last place should the value be hidden while it changes
  const editDim = dimEdit && dimEdit.fid === dimFid
    ? laid.find((d) => d.field === dimEdit.field) ?? (lastDim.current?.field === dimEdit.field ? lastDim.current : null) : null;
  lastDim.current = editDim;

  /** A value typed into a dimension: the marker's sizes through the same
   *  setField / resetField as the panel's rows (the panel's feature through the
   *  store's actions, so its row and the dimension agree), one undo step per
   *  burst. While typing (`live`) a valid value sets as it is typed; an empty
   *  value returns it to driven, on Enter only. */
  const applyDim = (fid: string, field: string, text: string, live = false) => {
    const st = useStudio.getState();
    const f = getFeature(st.doc, fid);
    const t = text.trim().replace(",", ".");
    if (!f) return;
    const mine = st.panel.open && st.panel.featureId === fid;
    const key = `field:${fid}:${field}`;
    if (t === "") {
      if (live || !isSet(f, field)) return;
      if (mine) st.resetField(field);
      else st.setDoc(updateFeature(st.doc, fid, (g) => resetField(g, field)), key);
      return;
    }
    const v = Number(t);
    if (!Number.isFinite(v) || v < (field === "marker.marker_mm" ? 0.1 : 0)) return;
    if (mine) st.setField(field, v);
    else st.setDoc(updateFeature(st.doc, fid, (g) => setField(g, field, v)), key);
  };
  const commitDim = (fid: string, field: string, text: string) => {
    setDimEdit(null);
    applyDim(fid, field, text);
  };
  /** Esc: the feature's marker as it was when the editor opened. */
  const revertDim = (fid: string, start: Feature) => {
    setDimEdit(null);
    const st = useStudio.getState();
    st.setDoc(updateFeature(st.doc, fid, (g) => ({ ...g, marker: { ...start.marker, first_id: g.marker.first_id }, set: start.set })), `field:${fid}:${dimEdit?.field}`);
  };

  let arc: ReactElement | null = null;
  const triads: ReactElement[] = [];
  const labels: ReactElement[] = [];
  for (const { f, rect: fRect, plan } of drawn) {
    // the outline in the rectangle's frame: for the turn arc and the Joint Origin's size
    const lp = plan.outer.map((p) => toLocal(fRect, p));
    const b = boxOf(lp);
    const ow = plan.outer_mm[0], oh = plan.outer_mm[1];
    const turned = f.marker.turn === 90 || f.marker.turn === 270;
    const [dw, dh] = turned ? [oh, ow] : [ow, oh];
    if (f.id === activeId) {
      // the turn arc: over the top of the marker, a handle in its middle
      const mc = fromLocal(fRect, [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2]);
      const rr = Math.min(b.x1 - b.x0, b.y1 - b.y0) * 0.42;
      const ang = (fRect.angle_deg * Math.PI) / 180;
      const pt = (a: number) => scr([mc[0] + rr * Math.cos(a + ang), mc[1] + rr * Math.sin(a + ang)]);
      const a0 = pt((55 * Math.PI) / 180), a1 = pt((125 * Math.PI) / 180), hp = pt(Math.PI / 2);
      const R = rr * z;
      if (R > 14) {
        arc = (
          <g className="turn" data-turn="1" data-feature={f.id} data-testid="turn-arc">
            <title>Turn 90° (now {f.marker.turn}°)</title>
            <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-path" />
            <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-hit" />
            <circle cx={hp[0]} cy={hp[1]} r={7} className="turn-knob" />
            <circle cx={hp[0]} cy={hp[1]} r={2.5} className="turn-dot" />
          </g>
        );
      }
    }
    const fr = plan.origin.length === 16 ? { o: [plan.origin[3], plan.origin[7]] as Vec2, x: [plan.origin[0], plan.origin[4]] as Vec2, y: [plan.origin[1], plan.origin[5]] as Vec2 } : null;
    if (fr) {
      const L = Math.max(14, Math.min(60, Math.min(dw, dh) * 0.3 * z));
      const o = scr(fr.o);
      const nx = Math.hypot(fr.x[0], fr.x[1]) || 1, ny = Math.hypot(fr.y[0], fr.y[1]) || 1;
      const X: Vec2 = [o[0] + (fr.x[0] / nx) * L, o[1] - (fr.x[1] / nx) * L];
      const Y: Vec2 = [o[0] + (fr.y[0] / ny) * L, o[1] - (fr.y[1] / ny) * L];
      triads.push(
        <g key={f.id} className={`triad${sel?.kind === "origin" && sel.id === f.id ? " on" : ""}`} data-origin={`${fr.o[0]},${fr.o[1]}`} data-feature={f.id}>
          <line x1={o[0]} y1={o[1]} x2={X[0]} y2={X[1]} className="ax-x" />
          <line x1={o[0]} y1={o[1]} x2={Y[0]} y2={Y[1]} className="ax-y" />
          <circle cx={o[0]} cy={o[1]} r={3.5} className="ax-o" />
        </g>,
      );
    }
    // the label: sketch text, its centre where the core put it (or where it is
    // being dragged); its lines stacked as the core stacks them, or, for a 3D
    // print (the pixel font), the blocky ink the core drew
    const pl = plan.label;
    if (pl && pl.text) {
      const at0 = scr(pl.at);
      const at = scr(labelAt?.fid === f.id ? labelAt.at : pl.at);
      const cls = `label${sel?.kind === "text" && sel.id === f.id ? " on" : ""}`;
      // WHY inline pointer-events: the stylesheet lets only [data-label] itself take a press; here that is the group
      const hit = { pointerEvents: "auto" as const };
      if (pl.font === "pixel" && pl.polygons?.length) {
        labels.push(
          <g key={f.id} className={cls} data-label="1" data-feature={f.id} data-testid="label-text" data-font="pixel"
            transform={`translate(${at[0] - at0[0]} ${at[1] - at0[1]})`}>
            <path d={pl.polygons.map((p) => sl(p.outer) + p.holes.map(sl).join("")).join("")} fillRule="evenodd" data-label-ink="1" style={hit} />
          </g>,
        );
      } else {
        const lines = pl.lines?.length ? pl.lines : pl.text.split("\n");
        const cap = pl.height_mm * z;
        const pitch = (1 + LINE_GAP) * cap;
        const fs = Math.max(6, cap / 0.7);
        labels.push(
          <g key={f.id} className={cls} data-label="1" data-feature={f.id} data-testid="label-text" data-font="sans"
            transform={pl.angle_deg ? `rotate(${-pl.angle_deg} ${at[0]} ${at[1]})` : undefined}>
            {lines.map((t, k) => (
              // line k's cap centre is (n - 1) / 2 - k pitches above the block's centre; its baseline half a cap below that
              <text key={k} data-label-line={k} x={at[0]} y={at[1] - ((lines.length - 1) / 2 - k) * pitch + cap / 2}
                fontSize={fs} textAnchor="middle" style={hit}>{t}</text>
            ))}
          </g>,
        );
      }
    }
  }

  // the draft being drawn
  let draft: ReactElement | null = null;
  if (drag?.kind === "draw") {
    if (drag.tool === "rect") {
      const r = rectFromCorners(drag.a, drag.b);
      draft = <g><path d={sl(shapeLoop({ kind: "rect", id: "draft", ...r }))} className="edge draft" />
        <text className="draft-dim" x={scr(drag.b)[0] + 10} y={scr(drag.b)[1] - 8}>{fmt(r.w)} × {fmt(r.h)}</text></g>;
    } else {
      const c = circleFrom(drag.a, drag.b, "draft");
      draft = <g><path d={sl(shapeLoop(c))} className="edge draft" />
        <text className="draft-dim" x={scr(drag.b)[0] + 10} y={scr(drag.b)[1] - 8}>Ø {fmt(c.r * 2)}</text></g>;
    }
  }

  // the selected shape's handles
  const handles: ReactElement[] = [];
  if (selShape?.kind === "rect") {
    for (const hn of HANDLES) {
      const [x, y] = scr(handlePoint(selShape, hn));
      handles.push(<rect key={hn} data-handle={hn} x={x - 4} y={y - 4} width={8} height={8} className={`handle h-${hn}`} />);
    }
  } else if (selShape?.kind === "circle") {
    const [x, y] = scr([selShape.cx + selShape.r, selShape.cy]);
    handles.push(<rect key="e" data-handle="e" x={x - 4} y={y - 4} width={8} height={8} className="handle h-e" />);
  }

  const cursor = drag?.kind === "pan" ? "grabbing" : tool !== "select" ? "crosshair" : hover?.kind === "edge" ? "pointer" : "default";

  return (
    <div ref={host} className="viewport" data-testid="viewport" data-tool={tool} style={{ cursor }}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
      onPointerLeave={() => !drag && setHover(null)} onDoubleClick={onDoubleClick}
      onContextMenu={(e) => e.preventDefault()}>
      <svg ref={svg} width={w} height={h} className="vp-svg" data-zoom={z}>
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0 1L7 4L0 7z" className="arrow" />
          </marker>
        </defs>
        <g className="grid">{grid}</g>
        <g className="sketch">
          <path d={regionsD} fillRule="evenodd" className="regions" data-regions="1" />
          {hoverRef && !sameProfile(hoverRef, selRef) && <path d={profD(hoverRef)} fillRule="evenodd" className="region-hover" data-hover-profile={hoverRef.outer} />}
          {selRef && <path d={profD(selRef)} fillRule="evenodd" className="region-sel" data-sel-profile={selRef.outer} />}
          <g className="whites">
            {drawn.map(({ f, plan }) => {
              const cs = cutShape(plan);
              return <path key={f.id} d={sl(cs.outer) + cs.holes.map(sl).join("")} fillRule="evenodd" style={WHITE}
                data-cut-white={f.id} data-trim={f.trim} />;
            })}
          </g>
          {drawn.map(({ f, plan }) => (
            <g key={f.id} className={`marker${sel?.kind === "feature" && sel.id === f.id ? " on" : ""}`} data-marker={f.id}>
              <path d={sl(plan.outer)} className={`outline${plan.overflow_mm > 0 ? " bad" : ""}`} data-marker-outline="1" style={OUTLINE}
                data-overflow={plan.overflow_mm} />
              <path d={plan.black.map((p) => sl(p.outer) + p.holes.map(sl).join("")).join("")} fillRule="evenodd" className="black" data-marker-black="1" />
            </g>
          ))}
          {shapes.map((s) => (
            <path key={s.id} d={sl(shapeLoop(s))} data-shape={s.id} data-kind={s.kind}
              className={[
                "edge",
                s.id === selId && "on",
                hover?.kind === "edge" && hover.id === s.id && "hover",
                featureRects.has(s.id) && "marker-rect",
              ].filter(Boolean).join(" ")} />
          ))}
        </g>
        {draft}
        {fitBoxOf && (
          <path d={sl(rectCorners(fitBoxOf.rect))} data-fit-rect={fitBoxOf.f.id} className="fit-rect"
            style={{ fill: "none", stroke: "var(--muted)", strokeWidth: 1, strokeDasharray: "5 4", opacity: 0.7, pointerEvents: "none" }} />
        )}
        {dimOf && <Dims fid={dimOf.f.id} dims={laid} editing={editDim?.field ?? null} onEdit={(field) => setDimEdit({ fid: dimOf.f.id, field, start: dimOf.f })} />}
        {triads}
        {arc}
        {labels}
        <g className="handles">{handles}</g>
        <g className="ruler">
          <rect x={0} y={0} width={w} height={RULER} className="ruler-bg" />
          {ticks}
        </g>
      </svg>
      {editDim && dimEdit && dimFid && (
        <DimEditor key={`${dimFid}:${editDim.field}`} dim={editDim}
          onLive={(t) => applyDim(dimFid, editDim.field, t, true)}
          onCommit={(t) => commitDim(dimFid, editDim.field, t)} onCancel={() => revertDim(dimFid, dimEdit.start)} />
      )}
      {panel.selector && (
        <div className="vp-hint" data-testid="selector-hint">
          Select a profile: click inside a region, or double-click a rectangle
        </div>
      )}
    </div>
  );
}
