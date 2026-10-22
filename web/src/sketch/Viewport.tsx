// The sketch viewport: renders the sketch model (./model.ts) and what the
// core planned, and turns pointer events into the store's actions. y up,
// millimetres; pan with the middle button or Space-drag, zoom at the cursor,
// F fits. A right-button drag is a selection box (a window left to right, a
// crossing right to left), and so is a left-button drag on empty canvas or
// on a fill no marker owns (Figma's marquee); a right-click that does not
// move (./click.ts) opens the canvas menu there (./CanvasMenu.tsx: what is
// under the pointer, then the zoom: fit, selection, Actual size, 100 %);
// Shift+click (Ctrl, Cmd too)
// adds or removes a shape, pressed on its edge, its fill or its marker; a
// drag on a selected shape moves every selected one; several selected get
// their bounds and an "N selected" chip. D dimensions (./constraints.ts):
// pick an edge, a circle, or two references, drag (or click) to place, type
// the value. Drawing a rectangle or a circle shows Fusion's value boxes on
// the rubber band; a typed value is a driving dimension. Every feature's marker, outline, Joint Origin and
// label are drawn as its plan() returned them: no marker geometry is made
// here. The sticker's white is the plan's cut_shape (the trim: the profile
// with its holes, or the quiet zone), under the marker; when the cut is not
// the quiet zone's edge, that edge is a dashed guide and a selected marker
// outlines its cut, the edge that prints. A label is drawn in
// the colour it prints in, selected or not. View › Marker info puts the
// sheet's caption under every marker (a view overlay, never printed). The
// turn arc belongs to the feature in focus (the panel's, else the selected
// one; none when nothing is): a click turns the marker 90°; on a rectangle
// profile it is also Fusion's rotate manipulator -- a drag turns the
// rectangle about its centre (15° steps, Shift free) and the marker follows,
// its angle in a value box you can type into (one undo step per rotation).
// The selected feature's dimensions (./Dims.tsx)
// stand outside the box the core placed its marker in (MarkerPlan.fit_rect)
// and are typed into in place, the marker following as you type. A drag
// (move, resize, the label) is one undo step; moving or resizing a profile's
// shapes re-plans its marker (a rectangle profile: the marker follows it).
// The calm canvas (V1 "Turn it down", Zach's pick 2026-10-21): every layer is
// still drawn, but at rest a marker's chrome is thin and grey -- its sketch
// dims, its info line, its Joint Origin, its profile edge -- and the marker
// that is selected, or that the pointer is on (what a click there opens), has
// today's. The dock's Layers menu (../overlays/) turns each layer off, and
// sets the background: Dots | Grid | Blank.
import { useEffect, useRef, useState, type ReactElement } from "react";
import type { MarkerPlan, Polygon, Rect, Vec2 } from "../core/contract";
import {
  featureOfProfile, featureOfRect, featureRect, getFeature, isSet, newId, rectProfile, resetField, setField, updateFeature, type Doc, type Feature,
} from "../model/doc";
import {
  boxOf, fromLocal, handlePoint, HANDLES, loopD, niceStep, rectCorners, rectFromCorners, toLocal, toScreen, toWorld, zoomAt,
  type Handle,
} from "../model/geom";
import { useOverlays } from "../overlays/overlays";
import { selectedFeatureId, useStudio } from "../store";
import { DimEditor, Dims, layoutDims, type LaidDim } from "./Dims";
import { diameterLocked, dimFromPicks, dimShapes, refusal, resizable, typedValue, type DimRef, type SketchDim } from "./constraints";
import {
  boxPick, circleFrom, hitTest, inShape, profileLoops, rectAt, rectOf, resizeShape, sameProfile, shapeLoop, shapeUnder, sketchBox,
  type Hit, type ProfileRef, type RectShape, type Selection, type Shape,
} from "./model";
import { CanvasMenu, type MenuAt, type MenuTarget } from "./CanvasMenu";
import { isDrag } from "./click";
import { pointer } from "./pointer";
import { SketchDims, ValueBox, laySketchDim, visibleSketchDims, type LaidSketchDim } from "./SketchDims";

type Drag =
  | { kind: "pan"; sx: number; sy: number; cx: number; cy: number }
  /** every shape in `ids` from where it was (`base`); `click`: what a press that does not move does */
  | { kind: "move"; ids: string[]; from: Vec2; base: Shape[]; moved: boolean; click?: () => void }
  | { kind: "resize"; id: string; handle: Handle; orig: Shape }
  | { kind: "label"; fid: string; from: Vec2; orig: Vec2; at: Vec2 }
  /** `clicked`: the first corner was a click: the band follows the pointer until the next click (Fusion) */
  | { kind: "draw"; tool: "rect" | "circle"; a: Vec2; b: Vec2; clicked: boolean }
  /** the selection box, in view px (the right button, or the left on empty canvas); `click`: what a press that does not move does */
  | { kind: "box"; a: Vec2; b: Vec2; add: boolean; moved: boolean; click?: () => void }
  /** D: pressed on a pick; a drag from it places the dimension */
  | { kind: "dim"; press: Vec2 }
  /** the turn arc of a rectangle profile: `orig` as it was, `a0` the pointer's angle about its centre at the press */
  | { kind: "rotate"; fid: string; orig: RectShape; a0: number; press: Vec2; moved: boolean };

/** The draw boxes' typed values (a key absent: it follows the pointer) and the one keys go to. */
interface DrawVals { w?: string; h?: string; d?: string; active: "w" | "h" | "d" }

const num = (t: string | undefined): number | null => {
  const v = Number((t ?? "").trim().replace(",", "."));
  return t !== undefined && t.trim() !== "" && Number.isFinite(v) && v > 0 ? v : null;
};
const sameRef = (a: DimRef, b: DimRef) => JSON.stringify(a) === JSON.stringify(b);
/** A handle's sides: -1 / +1 along x and y (0: it does not move that way). */
const handleSides = (h: Handle): [-1 | 0 | 1, -1 | 0 | 1] => [h.includes("e") ? 1 : h.includes("w") ? -1 : 0, h.includes("n") ? 1 : h.includes("s") ? -1 : 0];

const EDGE_PX = 6;
/** the selection boxes: a window solid blue, a crossing dashed green (Fusion's) */
// WHY inline (the stylesheet is not this lane's): D's centre crosses, the pick under the pointer, the picks
const PICK_CSS = `
.vp-svg .pick-centre { fill: none; stroke: var(--muted); stroke-width: 1.2; }
.vp-svg .pick-hover { fill: none; stroke: var(--accent); stroke-width: 3; opacity: 0.6; }
.vp-svg .pick-on { fill: none; stroke: var(--pick); stroke-width: 3; }
`;
const WINDOW_BOX = { fill: "rgba(59, 130, 246, 0.10)", stroke: "rgb(59, 130, 246)", strokeWidth: 1 };
const CROSSING_BOX = { fill: "rgba(34, 197, 94, 0.10)", stroke: "rgb(34, 160, 80)", strokeWidth: 1, strokeDasharray: "6 4" };
// WHY: the core stacks a label's lines (1 + LINE_GAP) caps apart
// (aruco_studio/core/rect_fill.py LINE_GAP, the pixel font's 2 px of 5)
const LINE_GAP = 0.4;
const RULER = 18;

const fmt = (v: number) => String(+v.toFixed(1));
// WHY inline (the stylesheet is not this lane's): the white is the paper's,
// the outline only draws the quiet-zone edge over it (and still takes a click)
const WHITE = { fill: "var(--t-white)", stroke: "none" };
const OUTLINE = { fill: "transparent" };
// WHY (Zach, 2026-10-21: a 123.5 mm profile whose plate read 112 on the canvas,
// "I am expecting 123.5"): when the sticker is cut elsewhere (Trim Profile, the
// marker not filling it) the quiet zone's edge prints nothing, so it is drawn
// as a guide (dashed, faint: the fit box's construction look) and the
// selection outlines the cut, the edge that prints. Overflow keeps its red.
const OUTLINE_GUIDE = { fill: "transparent", stroke: "var(--muted)", strokeWidth: 1, strokeDasharray: "5 4", opacity: 0.7 };
/** Layers › Quiet-zone guides off: the guide is not drawn, its path still takes a click. */
const OUTLINE_GUIDE_OFF = { ...OUTLINE_GUIDE, stroke: "none" };
const CUT_SEL = { fill: "none", stroke: "var(--pick)", strokeWidth: 2.5, strokeLinejoin: "round" as const };
// View › Marker info's line, V1 "Turn it down": thin and grey at rest; on the
// marker that is selected or pointed at, a bit more bold (Zach, 2026-10-21:
// "dim the labels to be thin and grey, and only when selected would they
// become a bit more bold"). --quiet-text is styles.css's (.vp-svg).
const INFO_QUIET = { fill: "var(--quiet-text)", font: "400 9px var(--font)", pointerEvents: "none" as const };
const INFO_HOT = { fill: "var(--muted)", font: "600 10px var(--font)", pointerEvents: "none" as const };
/** Two loops with the same bounding box (to 1e-6 mm): the cut IS the outline. */
const sameBox = (a: Vec2[], b: Vec2[]) => {
  const p = boxOf(a), q = boxOf(b);
  return Math.abs(p.x0 - q.x0) < 1e-6 && Math.abs(p.y0 - q.y0) < 1e-6 && Math.abs(p.x1 - q.x1) < 1e-6 && Math.abs(p.y1 - q.y1) < 1e-6;
};

/** What the sticker is cut to: the plan's cut_shape, else (a core without
 *  trim, the mock) its cut, else the marker's outline as before. */
const cutShape = (p: MarkerPlan): Polygon => p.cut_shape ?? { outer: p.cut ?? p.outer, holes: [] };

/** What a label prints in: knocked out of the black border row (the paper's
 *  white), else black ink (on the quiet zone, or outside the marker).
 *  WHY (Zach, 2026-10-21): "can label be white if they are not selected?
 *  right now they are always like this selected blue" -- a label is drawn as
 *  it prints; the selection shows by its own outline, never by recolouring it
 *  (docs/design/panel_skeleton.md, "On the model / canvas"). */
export function labelInk(f: Feature): "white" | "black" {
  return (f.label.place ?? "on_marker") === "on_marker" && (f.label.surface ?? "black") === "black" ? "white" : "black";
}
const INK = { white: "var(--t-white)", black: "var(--t-black)" };

/** The spaced sheet's caption under a sticker (web_api.sheet's, with no label:
 *  "#1 · 4X4_50 · 44.0 mm"): the ids, the dictionary without DICT_, the marker
 *  size as the core's _mm writes it (two decimals, a trailing 0 dropped). */
export function markerInfoText(f: Feature, plan: MarkerPlan): string {
  const ids = plan.ids;
  const idw = ids.length === 1 ? `#${ids[0]}` : `#${ids[0]}-${ids[ids.length - 1]}`;
  const mm = plan.marker_mm.toFixed(2);
  return `${idw} · ${f.marker.dictionary.replace("DICT_", "")} · ${mm.endsWith("0") ? mm.slice(0, -1) : mm} mm`;
}

/** The box the core placed a feature's marker in: the plan's fit_rect, else
 *  (a core from before barrier 9) the rectangle profile, else the outline's box. */
function placeBox(doc: Doc, f: Feature, plan: MarkerPlan): Rect {
  if (plan.fit_rect) return plan.fit_rect;
  const r = featureRect(doc, f);
  if (r) return rectOf(r);
  const b = boxOf(plan.outer);
  return { cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, w: b.x1 - b.x0, h: b.y1 - b.y0, angle_deg: 0 };
}

/** The rotate manipulator's snap (Fusion's angle manipulators step by 15°). */
const ROT_SNAP = 15;
/** An angle into [0, 360). */
const deg360 = (a: number) => +((((a % 360) + 360) % 360).toFixed(6));
/** The pointer's angle (degrees, counter-clockwise, y up) about a rectangle's centre. */
const angleAbout = (r: RectShape, p: Vec2) => (Math.atan2(p[1] - r.cy, p[0] - r.cx) * 180) / Math.PI;

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
  const multi = useStudio((s) => s.multi);
  const dimSel = useStudio((s) => s.dimSel);
  const tool = useStudio((s) => s.tool);
  const plans = useStudio((s) => s.plans);
  const panel = useStudio((s) => s.panel);
  const markerInfo = useStudio((s) => s.markerInfo);
  const overlays = useOverlays((s) => s.overlays);
  const [hover, setHover] = useState<Hit>(null);
  /** the marker the pointer is on: what a click there would open; its chrome is drawn as a selected one's */
  const [hoverFid, setHoverFid] = useState<string | null>(null);
  const [drag, setDragState] = useState<Drag | null>(null);
  // WHY a ref beside the state (Zach, 2026-10-20 night: "multi select by right
  // click drag doesn't work"; scripts/real-input-check.mjs reproduced it under
  // real X11 input): the handlers read the gesture from the last render, and a
  // hand that releases right after its last move (a busy page, coalesced
  // moves) got there first: the release saw the box unmoved and selected
  // nothing; a rectangle ended at an older point. The handlers read this ref,
  // which every change writes at once; the state only draws.
  const dragRef = useRef<Drag | null>(null);
  const setDrag = (next: Drag | null | ((d: Drag | null) => Drag | null)) => {
    dragRef.current = typeof next === "function" ? next(dragRef.current) : next;
    setDragState(dragRef.current);
  };
  const [labelAt, setLabelAt] = useState<{ fid: string; at: Vec2 } | null>(null);
  /** the dimension being typed into, and its feature as it was when the editor opened (Esc puts it back) */
  const [dimEdit, setDimEdit] = useState<{ fid: string; field: string; start: Feature } | null>(null);
  const lastDim = useRef<LaidDim | null>(null);
  /** D: the references picked so far, where the pointer is, and the new dim whose value box is open */
  const [picks, setPicks] = useState<DimRef[]>([]);
  const [cursorAt, setCursorAt] = useState<Vec2 | null>(null);
  const [placing, setPlacing] = useState<SketchDim | null>(null);
  /** the sketch dim being typed into */
  const [sdimEdit, setSdimEdit] = useState<string | null>(null);
  const [drawVals, setDrawVals] = useState<DrawVals>({ active: "w" });
  /** the rotate manipulator's angle box: live while dragging, then open to type into (the rotation's gesture ends when it closes) */
  const [rot, setRot] = useState<{ id: string; live: boolean } | null>(null);
  /** the last Profile-row pick: a double-click right after it re-picks for the same feature */
  const picked = useRef<{ fid: string; at: number } | null>(null);
  /** the right-click menu: where it opened and on what */
  const [menu, setMenu] = useState<MenuAt | null>(null);
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

  // Esc while drawing drops the draft, and D's picks (the app's Esc does the rest)
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setDrag((d) => (d?.kind === "draw" || d?.kind === "box" ? null : d));
      setPicks([]);
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  // leaving D drops its picks; leaving a draw tool drops its draft; another tool points at no marker
  useEffect(() => {
    if (tool !== "dim") { setPicks([]); setPlacing(null); }
    if (tool !== "rect" && tool !== "circle") setDrag((d) => (d?.kind === "draw" ? null : d));
    if (tool !== "select") setHoverFid(null);
  }, [tool]);

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
    if (st.multi.length > 1) return undefined;
    if (s?.kind === "shape") return st.doc.shapes.find((x) => x.id === s.id);
    if (s?.kind === "feature" || s?.kind === "origin" || s?.kind === "text") return featureRect(st.doc, getFeature(st.doc, s.id)) ?? undefined;
    return undefined;
  };

  /** The marker a click at p (on `target`) would open, as onPointerDown
   *  picks it: what is drawn for a marker (its ink, its outline, its label,
   *  its Joint Origin), its rectangle's edge, or a region its profile is.
   *  None while the Profile row waits for a pick (a click there picks a
   *  region). WHY the click's own targeting: a hover that lights another
   *  marker than the click opens would say something false. */
  const markerAt = (target: Element | null, p: Vec2): string | null => {
    const st = useStudio.getState();
    if (st.panel.selector) return null;
    const el = target?.closest?.("[data-marker],[data-feature]");
    const fid = el?.getAttribute("data-marker") ?? el?.getAttribute("data-feature");
    if (fid && st.plans[fid] && getFeature(st.doc, fid)) return fid;
    const hit = hitTest(st.doc.shapes, p, EDGE_PX / z);
    const owner = hit?.kind === "edge" ? featureOfRect(st.doc, hit.id) : hit?.kind === "region" ? featureOfProfile(st.doc, hit.ref) : null;
    return owner && st.plans[owner.id] ? owner.id : null;
  };

  /** D's pick at p: a centre, else an edge (a rectangle's side, a circle's
   *  outline), else an origin axis. */
  const pickAt = (p: Vec2): DimRef | null => {
    const shapes = useStudio.getState().doc.shapes;
    const tol = EDGE_PX / z;
    for (const s of shapes) if (s.kind !== "poly" && Math.hypot(p[0] - s.cx, p[1] - s.cy) <= tol * 1.5) return { shape: s.id, at: "c" };
    const hit = hitTest(shapes, p, tol);
    const s = hit?.kind === "edge" ? shapes.find((x) => x.id === hit.id) : undefined;
    if (s?.kind === "circle") return { shape: s.id, at: "o" };
    if (s?.kind === "rect") {
      const [u, v] = toLocal(s, p);
      const sides: [DimRef & { shape: string }, number][] = [
        [{ shape: s.id, at: "l" }, Math.abs(u + s.w / 2)], [{ shape: s.id, at: "r" }, Math.abs(u - s.w / 2)],
        [{ shape: s.id, at: "b" }, Math.abs(v + s.h / 2)], [{ shape: s.id, at: "t" }, Math.abs(v - s.h / 2)],
      ];
      return sides.reduce((a, b) => (b[1] < a[1] ? b : a))[0];
    }
    if (Math.abs(p[0]) <= tol) return { axis: "y" };
    if (Math.abs(p[1]) <= tol) return { axis: "x" };
    return null;
  };

  /** D: the picks make a dimension placed at p: its value box opens (or a note says why not). */
  const placeDim = (p: Vec2, refs = picks) => {
    const st = useStudio.getState();
    const r = dimFromPicks(st.doc.shapes, refs, p, newId("d"));
    if (!r) return;
    setPicks([]);
    if ("error" in r) { st.say(r.error); return; }
    const why = refusal(st.doc.shapes, st.doc.dims, r.dim);
    if (why) { st.say(why); return; }
    setPlacing(r.dim);
  };

  /** The draft as drawn now: the pointer's corner, or a typed size from the first corner (snapped). */
  const draftShape = (d: Extract<Drag, { kind: "draw" }>, vals: DrawVals): Shape => {
    if (d.tool === "circle") {
      const c = circleFrom(d.a, d.b, "draft");
      const dia = num(vals.d);
      return dia ? { ...c, r: dia / 2 } : c;
    }
    const live = rectFromCorners(d.a, d.b);
    const tw = num(vals.w), th = num(vals.h);
    if (!tw && !th) return { kind: "rect", id: "draft", ...live };
    const a = rectFromCorners(d.a, d.a);
    const sx = d.b[0] >= d.a[0] ? 1 : -1, sy = d.b[1] >= d.a[1] ? 1 : -1;
    const W = tw ?? live.w, H = th ?? live.h;
    const x0 = sx > 0 ? a.cx : a.cx - W, y0 = sy > 0 ? a.cy : a.cy - H;
    return { kind: "rect", id: "draft", cx: x0 + W / 2, cy: y0 + H / 2, w: W, h: H, angle_deg: 0 };
  };

  /** The draft into the sketch, its typed values as driving dims (one undo step). */
  const commitDraw = (d: Extract<Drag, { kind: "draw" }>, vals: DrawVals) => {
    const st = useStudio.getState();
    const sh = draftShape(d, vals);
    const sx = d.b[0] >= d.a[0] ? 1 : -1, sy = d.b[1] >= d.a[1] ? 1 : -1;
    setDrag(null);
    const out = 24 / z;   // the dims stand this far outside the edge the box was on
    if (sh.kind === "rect") {
      if (sh.w < 1 || sh.h < 1) return;
      const id = newId("r");
      const dims: SketchDim[] = [];
      if (num(vals.w)) dims.push({ id: newId("d"), kind: "w", shape: id, value: sh.w, at: [0, sy * (sh.h / 2 + out)] });
      if (num(vals.h)) dims.push({ id: newId("d"), kind: "h", shape: id, value: sh.h, at: [sx * (sh.w / 2 + out), 0] });
      st.addShape({ ...sh, id }, dims);
    } else if (sh.kind === "circle") {
      if (sh.r < 0.5) return;
      const id = newId("c");
      const u = Math.hypot(d.b[0] - d.a[0], d.b[1] - d.a[1]) > 1e-9 ? [(d.b[0] - d.a[0]), (d.b[1] - d.a[1])] : [1, 1];
      const k = (sh.r + out) / Math.hypot(u[0], u[1]);
      st.addShape({ ...sh, id }, num(vals.d) ? [{ id: newId("d"), kind: "d", shape: id, value: sh.r * 2, at: [u[0] * k, u[1] * k] }] : []);
    }
    st.setTool("select");
  };

  /** Start moving a shape: every selected one when it is among them. */
  const startMove = (sh: Shape, p: Vec2, click?: () => void) => {
    const st = useStudio.getState();
    const ids = st.multi.length > 1 && st.multi.includes(sh.id) ? st.multi : [sh.id];
    st.gesture(true);
    setDrag({ kind: "move", ids, from: p, base: st.doc.shapes, moved: false, click });
  };
  /** Shift+click: the shape into the selection, or out of it. A selection
   *  that is not shapes yet counts as its shape: a profile its outer one, a
   *  feature (its marker, label or origin) its rectangle. */
  const toggleIn = (id: string) => {
    const st = useStudio.getState();
    const s = st.sel;
    if (!st.multi.length && s && s.kind !== "shape") {
      const base = s.kind === "profile" ? s.ref.outer : s.kind === "sketch" ? undefined : featureRect(st.doc, getFeature(st.doc, s.id))?.id;
      if (base) st.selectShapes([base]);
    }
    st.toggleShape(id);
  };
  /** A left press on empty canvas: a drag is a selection box, a click does `click`. */
  const startBox = (e: React.PointerEvent, click: () => void) => setDrag({ kind: "box", a: local(e), b: local(e), add: false, moved: false, click });

  /** A press on a shape that is one of several selected: it drags them all, and only a click selects it alone. */
  const inGroup = (id: string | undefined) => {
    const m = useStudio.getState().multi;
    return !!id && m.length > 1 && m.includes(id);
  };

  const onPointerDown = (e: React.PointerEvent) => {
    const st = useStudio.getState();
    const drag = dragRef.current;
    const target = e.target as Element;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    // a press starts a gesture (a pan, a box, a drag): no marker is pointed at until the pointer moves free again
    setHoverFid(null);
    if (drag?.kind === "draw" && drag.clicked && e.button === 0) {
      // the second click of a clicked rectangle or circle
      commitDraw({ ...drag, b: world(e) }, drawVals);
      return;
    }
    if (e.button === 2 && !space.current) {
      // a drag is the selection box; a click (no move past DRAG_PX) opens the menu where it was released
      const on = target, at = { client: [e.clientX, e.clientY] as Vec2, local: local(e), world: world(e) };
      setMenu(null);
      setDrag({ kind: "box", a: local(e), b: local(e), add: e.shiftKey || e.ctrlKey || e.metaKey, moved: false, click: () => openMenu(on, at) });
      return;
    }
    if (e.button === 1 || space.current) {
      setDrag({ kind: "pan", sx: e.clientX, sy: e.clientY, cx: camera.cx, cy: camera.cy });
      return;
    }
    if (e.button !== 0) return;
    const p = world(e);
    if (tool === "dim") {
      if (placing) return;   // its value box is open: leaving it sets it
      const ref = pickAt(p);
      if (ref) {
        const again = picks.length === 1 && sameRef(ref, picks[0]);
        if (!again) setPicks(picks.length >= 2 ? [ref] : [...picks, ref]);
        setCursorAt(p);
        setDrag({ kind: "dim", press: local(e) });
      } else if (picks.length) placeDim(p);
      return;
    }
    const hEl = target.closest("[data-handle]");
    if (hEl) {
      const orig = selectedShape();
      if (orig) { st.gesture(true); setDrag({ kind: "resize", id: orig.id, handle: hEl.getAttribute("data-handle") as Handle, orig }); }
      return;
    }
    const turnEl = target.closest("[data-turn]");
    if (turnEl) {
      const fid = turnEl.getAttribute("data-feature") ?? undefined;
      const r = fid ? featureRect(st.doc, getFeature(st.doc, fid)) : null;
      // WHY (Zach, 2026-10-20 night): "I like how previously there was the ability to rotate the marker on the page"
      if (fid && r) { setDrag({ kind: "rotate", fid, orig: r, a0: angleAbout(r, p), press: local(e), moved: false }); return; }
      st.turn(fid);
      return;
    }
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
      setDrawVals({ active: tool === "rect" ? "w" : "d" });
      setDrag({ kind: "draw", tool, a: p, b: p, clicked: false });
      return;
    }
    const hit = hitTest(st.doc.shapes, p, EDGE_PX / z);
    // WHY every part of a shape (Zach, 2026-10-20 night: "multi select ... by
    // shift click doesn't work"): it took an edge or a marker only; a press
    // inside a rectangle (its fill) selected the region instead
    if ((e.shiftKey || e.ctrlKey || e.metaKey) && !st.panel.selector) {
      const mk = target.closest("[data-marker]")?.getAttribute("data-marker");
      const mf = mk ? getFeature(st.doc, mk) : null;
      const sh = (mf ? featureRect(st.doc, mf) : null)
        ?? (hit?.kind === "edge" ? st.doc.shapes.find((x) => x.id === hit.id) : undefined)
        ?? shapeUnder(st.doc.shapes, p);
      if (sh) toggleIn(sh.id);
      else setDrag({ kind: "box", a: local(e), b: local(e), add: true, moved: false });
      return;
    }
    const selShape = selectedShape();
    const move = (sh: Shape, click?: () => void) => startMove(sh, p, click);
    // WHY WYSIWYG (Zach, 2026-10-18): "just clicking the marker on the screen is
    // what brings up the relevant inspector window". A click on a marker selects
    // the feature and opens its panel; a press-drag on a rectangle profile's
    // marker moves the rectangle, and the marker follows (the custom placement).
    // A marker placed in a face does not drag the face. Empty canvas closes it.
    const markerId = st.panel.selector ? null : target.closest("[data-marker]")?.getAttribute("data-marker");
    const markerOf = markerId ? getFeature(st.doc, markerId) : null;
    if (markerId && markerOf) {
      const r = featureRect(st.doc, markerOf);
      if (r && inGroup(r.id)) { move(r, () => st.inspect(markerId)); return; }
      st.inspect(markerId);
      if (r) move(r);
      return;
    }
    if (hit?.kind === "edge") {
      // the Profile row takes a region or a double-clicked rectangle, not an edge
      if (st.panel.selector) return;
      const s = st.doc.shapes.find((x) => x.id === hit.id)!;
      const owner = featureOfRect(st.doc, s.id);
      const pickIt = () => {
        if (owner) st.inspect(owner.id);
        else { if (st.panel.open) st.ok(); st.select({ kind: "shape", id: s.id }); }
      };
      if (inGroup(s.id)) { move(s, pickIt); return; }
      pickIt();
      move(s);
      return;
    }
    // inside a selected shape: drag it, and every other selected one (as after picking them in a CAD)
    const inside = st.multi.length > 1 ? st.doc.shapes.find((x) => st.multi.includes(x.id) && inShape(x, p)) : undefined;
    if (inside) { move(inside); return; }
    if (selShape && inShape(selShape, p)) {
      move(selShape);
      return;
    }
    if (hit?.kind === "region") {
      if (st.panel.open && st.panel.selector) { pickProfile(hit.ref); return; }
      const owner = featureOfProfile(st.doc, hit.ref);
      if (owner) {
        const r = featureRect(st.doc, owner);
        if (r && inGroup(r.id)) { move(r, () => st.inspect(owner.id)); return; }
        st.inspect(owner.id);
        if (r) move(r);
        return;
      }
      // a fill no marker owns (the plate's): a click selects it, a drag is a box (Figma's marquee on a frame)
      const ref = hit.ref;
      const pick = () => { const now = useStudio.getState(); if (now.panel.open) now.ok(); now.select({ kind: "profile", ref }); };
      if (st.panel.selector) pick();
      else startBox(e, pick);
      return;
    }
    if (st.panel.selector) st.closePanel();
    else startBox(e, () => useStudio.getState().closePanel());
  };

  /** The Profile row's pick, noted so a double-click that follows re-picks. */
  const pickProfile = (ref: ProfileRef) => {
    const st = useStudio.getState();
    const fid = st.panel.featureId;
    st.useProfile(ref);
    picked.current = fid ? { fid, at: performance.now() } : null;
  };

  /** A right-click that did not move: what it was on is selected as a left
   *  click selects it -- but a marker's panel is not opened (the menu's Edit
   *  does), only moved off another marker's, so the panel stays on the
   *  selection -- and what is selected already stays selected (Figma's). Then
   *  the menu opens there with what applies to it. */
  const openMenu = (el: Element, at: Omit<MenuAt, "target">) => {
    const st = useStudio.getState();
    const p = at.world;
    const marker = (fid: string): MenuTarget => {
      if (st.panel.open && st.panel.featureId !== fid) st.inspect(fid);
      else if (!st.panel.open) st.select({ kind: "feature", id: fid });
      return { kind: "marker", fid };
    };
    const shapes = (sel: Selection): MenuTarget => {
      if (st.panel.open) st.ok();
      st.select(sel);
      return { kind: "shapes" };
    };
    let target: MenuTarget = { kind: "canvas" };
    // the Profile row waiting for a pick: the selection is the panel's, left as it is
    if (!st.panel.selector) {
      // a marker, or what is drawn for it (its label, its Joint Origin, the turn arc)
      const fid = el.closest("[data-marker]")?.getAttribute("data-marker") ?? el.closest("[data-feature]")?.getAttribute("data-feature");
      const f = fid ? getFeature(st.doc, fid) : null;
      const hit = hitTest(st.doc.shapes, p, EDGE_PX / z);
      const edge = hit?.kind === "edge" ? st.doc.shapes.find((x) => x.id === hit.id) : undefined;
      const selShape = selectedShape();
      if (f) target = inGroup(featureRect(st.doc, f)?.id) ? { kind: "shapes" } : marker(f.id);
      else if (edge) {
        const owner = featureOfRect(st.doc, edge.id);
        target = inGroup(edge.id) ? { kind: "shapes" } : owner ? marker(owner.id) : shapes({ kind: "shape", id: edge.id });
      } else if (st.multi.length > 1 && st.doc.shapes.some((x) => st.multi.includes(x.id) && inShape(x, p))) target = { kind: "shapes" };
      else if (selShape && inShape(selShape, p)) {
        const own = selectedFeatureId(st.doc, st.sel);
        target = own ? { kind: "marker", fid: own } : { kind: "shapes" };
      } else if (hit?.kind === "region") {
        const owner = featureOfProfile(st.doc, hit.ref);
        target = owner ? marker(owner.id) : shapes({ kind: "profile", ref: hit.ref });
      }
    }
    setMenu({ ...at, target });
  };

  /** A double-click on a rectangle (its edge or inside it): its outer edges
   *  alone are the profile, whatever is inside it (Zach, 2026-10-20 evening:
   *  "you could double click on a rectangle and it would select the outer
   *  edges"). For the Profile row while it waits (or right after its first
   *  click picked the region), else as the selection. */
  const onDoubleClick = (e: React.MouseEvent) => {
    const st = useStudio.getState();
    const target = e.target as Element;
    // WHY not with Shift / Ctrl / Cmd: two quick Shift+clicks on one shape add it and take it out (a double-click would select its profile)
    if (tool !== "select" || e.button !== 0 || e.shiftKey || e.ctrlKey || e.metaKey) return;
    if (target.closest("[data-dim-label],[data-sdim-label],[data-label],[data-turn],[data-handle],input")) return;
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
    const drag = dragRef.current;
    pointer.at = world(e);
    if (tool === "dim") setCursorAt(world(e));
    if (!drag) {
      if (tool === "select") {
        const p = world(e);
        setHover(hitTest(st.doc.shapes, p, EDGE_PX / z));
        setHoverFid(markerAt(e.target as Element, p));
      } else {
        if (hover) setHover(null);
        if (hoverFid) setHoverFid(null);
      }
      return;
    }
    if (drag.kind === "pan") {
      st.setCamera({ ...camera, cx: drag.cx - (e.clientX - drag.sx) / z, cy: drag.cy + (e.clientY - drag.sy) / z });
      return;
    }
    if (drag.kind === "box") {
      const b = local(e);
      setDrag({ ...drag, b, moved: drag.moved || isDrag(drag.a, b) });
      return;
    }
    if (drag.kind === "dim") return;
    const p = world(e);
    if (drag.kind === "rotate") {
      const q = local(e);
      if (!drag.moved && !isDrag(drag.press, q)) return;
      let d = drag;
      if (!drag.moved) {
        // the rectangle as it is now (a typed angle may have landed since the press), one undo step from here
        const now = st.doc.shapes.find((x) => x.id === drag.orig.id);
        d = { ...drag, orig: now?.kind === "rect" ? now : drag.orig, moved: true };
        st.gesture(true);
        setDrag(d);
        setRot({ id: d.orig.id, live: true });
      }
      const raw = d.orig.angle_deg + angleAbout(d.orig, p) - d.a0;
      const a = deg360(e.shiftKey ? Math.round(raw * 10) / 10 : Math.round(raw / ROT_SNAP) * ROT_SNAP);
      const cur = st.doc.shapes.find((x) => x.id === d.orig.id);
      if (cur?.kind === "rect" && Math.abs(cur.angle_deg - a) > 1e-9) st.updateShape({ ...cur, angle_deg: a });
      return;
    }
    if (drag.kind === "draw") setDrag({ ...drag, b: p });
    else if (drag.kind === "move") {
      const dx = p[0] - drag.from[0], dy = p[1] - drag.from[1];
      if (!drag.moved && Math.hypot(dx, dy) * z < 3) return;
      if (!drag.moved) setDrag({ ...drag, moved: true });
      st.moveShapes(drag.base, drag.ids, dx, dy);
    } else if (drag.kind === "resize") {
      // WHY (Fusion): a dimensioned size, or a dimensioned edge, holds under a handle
      let next = resizeShape(drag.orig, drag.handle, p);
      const o = drag.orig;
      if (next.kind === "rect" && o.kind === "rect") {
        const [su, sv] = handleSides(drag.handle);
        const xs = !su || resizable(st.doc.shapes, st.doc.dims, o.id, "x", su), ys = !sv || resizable(st.doc.shapes, st.doc.dims, o.id, "y", sv);
        if (!xs) next = { ...next, cx: o.cx, w: o.w };
        if (!ys) next = { ...next, cy: o.cy, h: o.h };
        if ((!xs || !ys) && !st.note) st.say("Held: a dimension sets that size or edge.");
      } else if (o.kind === "circle" && diameterLocked(st.doc.dims, o.id)) {
        next = o;
        if (!st.note) st.say("Held: a dimension sets that Ø.");
      }
      st.updateShape(next);
    } else if (drag.kind === "label") {
      const dx = p[0] - drag.from[0], dy = p[1] - drag.from[1];
      setLabelAt({ fid: drag.fid, at: [drag.at[0] + dx, drag.at[1] + dy] });
      st.setLabel("offset_mm", [+(drag.orig[0] + dx).toFixed(1), +(drag.orig[1] + dy).toFixed(1)], drag.fid);
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const st = useStudio.getState();
    // the gesture as it is now, and it ends where the pointer is released (not at the last move seen)
    let drag = dragRef.current;
    if (drag?.kind === "draw" && !drag.clicked) drag = { ...drag, b: world(e) };
    if (drag?.kind === "box") {
      const b = local(e);
      drag = { ...drag, b, moved: drag.moved || isDrag(drag.a, b) };
    }
    if (drag?.kind === "draw") {
      if (drag.clicked) return;
      // a press without a drag: the first corner (centre) was a click, the band follows the pointer (Fusion)
      const [ax, ay] = scr(drag.a), [bx, by] = scr(drag.b);
      if (!isDrag([ax, ay], [bx, by])) { setDrag({ ...drag, clicked: true }); return; }
      commitDraw(drag, drawVals);
      return;
    }
    if (drag?.kind === "box") {
      if (drag.moved) {
        const [x0, y1] = toWorld(camera, w, h, [Math.min(drag.a[0], drag.b[0]), Math.min(drag.a[1], drag.b[1])]);
        const [x1, y0] = toWorld(camera, w, h, [Math.max(drag.a[0], drag.b[0]), Math.max(drag.a[1], drag.b[1])]);
        st.selectShapes(boxPick(st.doc.shapes, { x0, y0, x1, y1 }, drag.b[0] < drag.a[0]), drag.add);
      } else drag.click?.();
      setDrag(null);
      return;
    }
    if (drag?.kind === "dim") {
      const q = local(e);
      if (isDrag(drag.press, q)) placeDim(world(e));
      setDrag(null);
      return;
    }
    if (drag?.kind === "rotate") {
      setDrag(null);
      // a click turns the marker 90°; after a drag the angle box stays open to type an exact angle
      if (!drag.moved) st.turn(drag.fid);
      else setRot({ id: drag.orig.id, live: false });
      return;
    }
    if (drag?.kind === "label") setLabelAt(null);
    if (drag?.kind === "move" || drag?.kind === "resize" || drag?.kind === "label") st.gesture(false);
    if (drag?.kind === "move" && !drag.moved) drag.click?.();
    setDrag(null);
  };

  // ------------------------------------------------------------ the grid and rulers
  const step = niceStep(z);
  const minor = step / 5;
  const [wx0, wy1] = toWorld(camera, w, h, [0, 0]);
  const [wx1, wy0] = toWorld(camera, w, h, [w, h]);
  // the background (Layers › Grid: Dots | Grid | Blank, Miro's View › Grid):
  // the grid's lines, or a dot at each of its points; the sketch's two axes
  // are lines in both (the origin dims measure from); Blank draws nothing
  const bg = overlays.background;
  const grid: ReactElement[] = [];
  let dots: ReactElement | null = null;
  if (bg !== "blank" && minor * z >= 6) {
    for (let x = Math.ceil(wx0 / minor) * minor; x <= wx1; x += minor) {
      const axis = Math.abs(x) < 1e-9;
      if (bg !== "grid" && !axis) continue;
      const sx = scr([x, 0])[0];
      const major = Math.abs(x / step - Math.round(x / step)) < 1e-6;
      grid.push(<line key={`gx${x.toFixed(3)}`} x1={sx} x2={sx} y1={0} y2={h} className={axis ? "g axis" : major ? "g major" : "g"} />);
    }
    for (let y = Math.ceil(wy0 / minor) * minor; y <= wy1; y += minor) {
      const axis = Math.abs(y) < 1e-9;
      if (bg !== "grid" && !axis) continue;
      const sy = scr([0, y])[1];
      const major = Math.abs(y / step - Math.round(y / step)) < 1e-6;
      grid.push(<line key={`gy${y.toFixed(3)}`} y1={sy} y2={sy} x1={0} x2={w} className={axis ? "g axis" : major ? "g major" : "g"} />);
    }
    if (bg === "dots") {
      // one tile per major step, its dots at the minor points; the tile starts
      // half a minor step before the origin so no dot sits on a tile's edge
      const m = minor * z, o = scr([0, 0]);
      const pts: ReactElement[] = [];
      for (let i = 0; i < 5; i++) for (let j = 0; j < 5; j++) {
        pts.push(<circle key={`${i}-${j}`} cx={m / 2 + i * m} cy={m / 2 + j * m} r={i || j ? 0.9 : 1.3} className={i || j ? "dot" : "dot major"} />);
      }
      dots = (
        <>
          <defs>
            <pattern id="vp-grid-dots" x={o[0] - m / 2} y={o[1] - m / 2} width={5 * m} height={5 * m} patternUnits="userSpaceOnUse">{pts}</pattern>
          </defs>
          <rect width={w} height={h} fill="url(#vp-grid-dots)" data-testid="grid-dots" />
        </>
      );
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
  const selIds = new Set([...multi, ...(selId ? [selId] : [])]);
  // every feature that has a profile and a plan, with the box its marker was
  // placed in
  const drawn = doc.features
    .filter((f) => !!f.profile && !!plans[f.id])
    .map((f) => ({ f, plan: plans[f.id], rect: placeBox(doc, f, plans[f.id]) }));
  const featureRects = new Set(doc.features.map((f) => featureRect(doc, f)?.id));

  // the feature in focus: the panel's feature, or the one the selection names
  // (none when nothing is selected). It gets the dimensions and the turn arc.
  // WHY not the store's activeFeatureId (Zach, 2026-10-21: "when nothing is
  // selected it shouldn't display the rotation dragger"): that falls back to
  // the last marker made, for Export.
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

  // ------------------------------------------------------------ at rest, hot, or off (V1 "Turn it down", the Layers menu)
  // WHY every layer still drawn (Zach, 2026-10-21: "it's important for me to
  // still see things at a glance like the axes location etc."): at rest a
  // marker's chrome is thin and grey; the marker in focus, the selected ones
  // and the one the pointer is on (V1's hover) are "hot" and keep today's.
  /** every planned marker's profile shapes */
  const profileShapes = new Set<string>();
  for (const { f } of drawn) if (f.profile) [f.profile.outer, ...f.profile.holes].forEach((id) => profileShapes.add(id));
  /** the markers drawn as today */
  const hotFids = new Set<string>();
  if (dimOf) hotFids.add(dimOf.f.id);
  if (hoverFid && drawn.some((d) => d.f.id === hoverFid)) hotFids.add(hoverFid);
  for (const { f } of drawn) if (f.profile && selIds.has(f.profile.outer)) hotFids.add(f.id);
  /** the profile of the marker in focus: its own, drawn whatever the Layers say (V8: "Its own edit chrome ignores the toggles") */
  const ownShapes = new Set(dimOf?.f.profile ? [dimOf.f.profile.outer, ...dimOf.f.profile.holes] : []);
  /** the shapes whose edges and sketch dims are today's: the selection, the hot markers' profiles, what the pointer is on */
  const hotShapes = new Set<string>(selIds);
  if (selRef) [selRef.outer, ...selRef.holes].forEach((id) => hotShapes.add(id));
  for (const { f } of drawn) if (f.profile && hotFids.has(f.id)) [f.profile.outer, ...f.profile.holes].forEach((id) => hotShapes.add(id));
  if (hover?.kind === "edge") hotShapes.add(hover.id);
  if (hoverRef) [hoverRef.outer, ...hoverRef.holes].forEach((id) => hotShapes.add(id));
  /** a marker profile's edge: thin at rest ("quiet"), as today when hot (null), not drawn when Layers › Profile edges is off ("off");
   *  plain sketch geometry (no marker on it yet) is the sketch being drawn: always as today */
  const edgeLook = (id: string): "quiet" | "off" | null => {
    if (!profileShapes.has(id)) return null;
    if (!overlays.edges && !selIds.has(id) && !ownShapes.has(id)) return "off";
    return hotShapes.has(id) ? null : "quiet";
  };

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
  /** where the turn arc's knob is (view px): the rotate manipulator's angle box stands over it */
  let knob: Vec2 | null = null;
  const triads: ReactElement[] = [];
  const labels: ReactElement[] = [];
  for (const { f, rect: fRect, plan } of drawn) {
    // the outline in the rectangle's frame: for the turn arc and the Joint Origin's size
    const lp = plan.outer.map((p) => toLocal(fRect, p));
    const b = boxOf(lp);
    const ow = plan.outer_mm[0], oh = plan.outer_mm[1];
    const turned = f.marker.turn === 90 || f.marker.turn === 270;
    const [dw, dh] = turned ? [oh, ow] : [ow, oh];
    if (f.id === dimFid) {
      // the turn arc: over the top of the marker, a handle in its middle
      const mc = fromLocal(fRect, [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2]);
      const rr = Math.min(b.x1 - b.x0, b.y1 - b.y0) * 0.42;
      const ang = (fRect.angle_deg * Math.PI) / 180;
      const pt = (a: number) => scr([mc[0] + rr * Math.cos(a + ang), mc[1] + rr * Math.sin(a + ang)]);
      const a0 = pt((55 * Math.PI) / 180), a1 = pt((125 * Math.PI) / 180), hp = pt(Math.PI / 2);
      const R = rr * z;
      // a rectangle profile's arc also rotates it (a drag): arrowheads at its ends, as Fusion's rotate manipulator
      const rotates = !!featureRect(doc, f);
      const grab = rotates ? { cursor: drag?.kind === "rotate" ? "grabbing" : "grab" } : undefined;
      if (R > 14) {
        knob = hp;
        arc = (
          <g className="turn" data-turn="1" data-feature={f.id} data-testid="turn-arc" data-rotate={rotates ? "1" : undefined}>
            <title>{rotates ? `Drag to rotate the rectangle (${ROT_SNAP}° steps, Shift: free); click: turn the marker 90° (now ${f.marker.turn}°)` : `Turn 90° (now ${f.marker.turn}°)`}</title>
            <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-path"
              markerStart={rotates ? "url(#arr)" : undefined} markerEnd={rotates ? "url(#arr)" : undefined} />
            <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-hit" style={grab} />
            <circle cx={hp[0]} cy={hp[1]} r={7} className="turn-knob" style={grab} />
            <circle cx={hp[0]} cy={hp[1]} r={2.5} className="turn-dot" style={grab} />
          </g>
        );
      }
    }
    const fr = plan.origin.length === 16 ? { o: [plan.origin[3], plan.origin[7]] as Vec2, x: [plan.origin[0], plan.origin[4]] as Vec2, y: [plan.origin[1], plan.origin[5]] as Vec2 } : null;
    // Layers › Joint Origins off: only the marker in focus keeps its own
    if (fr && (overlays.origins || f.id === dimFid)) {
      const L = Math.max(14, Math.min(60, Math.min(dw, dh) * 0.3 * z));
      const originOn = sel?.kind === "origin" && sel.id === f.id;
      // V1: at rest thinner and fainter, the red and the green still told apart; hot, today's
      const quiet = !hotFids.has(f.id) && !originOn;
      const o = scr(fr.o);
      const nx = Math.hypot(fr.x[0], fr.x[1]) || 1, ny = Math.hypot(fr.y[0], fr.y[1]) || 1;
      const X: Vec2 = [o[0] + (fr.x[0] / nx) * L, o[1] - (fr.x[1] / nx) * L];
      const Y: Vec2 = [o[0] + (fr.y[0] / ny) * L, o[1] - (fr.y[1] / ny) * L];
      triads.push(
        <g key={f.id} className={`triad${originOn ? " on" : ""}${quiet ? " quiet" : ""}`} data-origin={`${fr.o[0]},${fr.o[1]}`} data-feature={f.id}>
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
      const on = sel?.kind === "text" && sel.id === f.id;
      const ink = labelInk(f);
      // WHY no "on" class: the stylesheet's .label colours it the accent and
      // .label.on strokes it the selection's (not this lane's to change); the
      // fill is inline, the ink it prints in, selected or not
      const cls = "label";
      // WHY inline pointer-events: the stylesheet lets only [data-label] itself take a press; here that is the group
      const hit = { pointerEvents: "auto" as const, fill: INK[ink], stroke: "none" };
      // a selected label: its band's outline, in the selection's colour (Fusion's text box)
      const band = on && pl.box?.length ? (
        <path d={sl(pl.box)} data-label-sel="1" transform={`translate(${at[0] - at0[0]} ${at[1] - at0[1]})`}
          style={{ fill: "none", stroke: "var(--pick)", strokeWidth: 1.2, strokeDasharray: "4 3", pointerEvents: "none" }} />
      ) : null;
      if (pl.font === "pixel" && pl.polygons?.length) {
        labels.push(
          <g key={f.id} className={cls} data-label="1" data-feature={f.id} data-testid="label-text" data-font="pixel" data-ink={ink} data-on={on ? "1" : undefined}
            transform={`translate(${at[0] - at0[0]} ${at[1] - at0[1]})`}>
            <path d={pl.polygons.map((p) => sl(p.outer) + p.holes.map(sl).join("")).join("")} fillRule="evenodd" data-label-ink="1" style={hit} />
          </g>,
        );
        if (band) labels.push(<g key={`${f.id}-sel`}>{band}</g>);
      } else {
        const lines = pl.lines?.length ? pl.lines : pl.text.split("\n");
        const cap = pl.height_mm * z;
        const pitch = (1 + LINE_GAP) * cap;
        const fs = Math.max(6, cap / 0.7);
        labels.push(
          <g key={f.id} className={cls} data-label="1" data-feature={f.id} data-testid="label-text" data-font="sans" data-ink={ink} data-on={on ? "1" : undefined}
            transform={pl.angle_deg ? `rotate(${-pl.angle_deg} ${at[0]} ${at[1]})` : undefined}>
            {lines.map((t, k) => (
              // line k's cap centre is (n - 1) / 2 - k pitches above the block's centre; its baseline half a cap below that
              <text key={k} data-label-line={k} x={at[0]} y={at[1] - ((lines.length - 1) / 2 - k) * pitch + cap / 2}
                fontSize={fs} textAnchor="middle" style={hit}>{t}</text>
            ))}
          </g>,
        );
        if (band) labels.push(<g key={`${f.id}-sel`}>{band}</g>);
      }
    }
  }

  // View › Marker info: the sheet's caption, small and grey, centred under
  // each marker's outline (as it stands on screen, turned or not); thin at
  // rest, a bit more bold on a hot marker (INFO_QUIET, INFO_HOT)
  // WHY (Zach, 2026-10-21): "give me the option to add a lable under neatht
  // he aruco markers ... look just like this one that appears if it has the
  // spaced layout ... a different label to the actual label"
  const infos: ReactElement[] = [];
  if (markerInfo) {
    for (const { f, plan } of drawn) {
      const pts = plan.outer.map(scr);
      if (!pts.length) continue;
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2, y = Math.max(...ys) + 12;
      const hot = hotFids.has(f.id);
      infos.push(
        <text key={f.id} x={cx} y={y} textAnchor="middle" data-testid="marker-info" data-feature={f.id} data-hot={hot ? "1" : "0"}
          style={hot ? INFO_HOT : INFO_QUIET}>{markerInfoText(f, plan)}</text>,
      );
    }
  }

  // the draft being drawn, and its value boxes on the rubber band (Fusion's):
  // W on the edge the pointer's corner is on, H on its side, Ø by the pointer
  let draft: ReactElement | null = null;
  const drawBoxes: ReactElement[] = [];
  if (drag?.kind === "draw") {
    const sh = draftShape(drag, drawVals);
    draft = <path d={sl(shapeLoop(sh))} className="edge draft" data-draft={sh.kind} />;
    const type = (k: "w" | "h" | "d") => (t: string) => setDrawVals((v) => ({ ...v, [k]: t }));
    const box = (k: "w" | "h" | "d", at: Vec2, live: number, label: string) => (
      <ValueBox key={k} testid={`draw-${k}`} label={label} at={at} active={drawVals.active === k}
        value={drawVals[k] ?? fmt(live)} onType={type(k)}
        onTab={() => setDrawVals((v) => ({ ...v, active: sh.kind === "rect" ? (v.active === "w" ? "h" : "w") : "d" }))}
        onCommit={() => commitDraw(drag, drawVals)}
        onCancel={() => { setDrag(null); useStudio.getState().setTool("select"); }} />
    );
    if (sh.kind === "rect") {
      const sx = drag.b[0] >= drag.a[0] ? 1 : -1, sy = drag.b[1] >= drag.a[1] ? 1 : -1;
      const wAt = scr([sh.cx, sh.cy + (sy * sh.h) / 2]), hAt = scr([sh.cx + (sx * sh.w) / 2, sh.cy]);
      drawBoxes.push(box("w", [wAt[0], wAt[1] - sy * 16], sh.w, "Width (mm)"), box("h", [hAt[0] + sx * 34, hAt[1]], sh.h, "Height (mm)"));
    } else if (sh.kind === "circle") {
      const b = scr(drag.b);
      drawBoxes.push(box("d", [b[0] + 40, b[1] - 18], sh.r * 2, "Diameter (mm)"));
    }
  }

  // the sketch's dims, the D tool's preview and what it has picked
  const sketchDims = doc.dims.map((d) => laySketchDim(shapes, d, scr, z)).filter((d): d is LaidSketchDim => !!d);
  const pendingDim = placing ?? (tool === "dim" && picks.length && cursorAt ? (() => {
    const r = dimFromPicks(shapes, picks, cursorAt, "preview");
    return r && "dim" in r ? r.dim : null;
  })() : null);
  const previewDim = pendingDim ? laySketchDim(shapes, pendingDim, scr, z) : null;
  const editSketchDim = sdimEdit ? sketchDims.find((d) => d.dim.id === sdimEdit) ?? null : null;
  // which are drawn: the dimhide lane's rule (a focused marker's own dims
  // stand for its profile's), then Layers › Sketch dimensions -- off, only the
  // selection's (and the one selected or typed into) stay; the D tool shows
  // them all. Then V1: thin and grey, but those of what is hot.
  const named = (d: LaidSketchDim, set: Set<string>) => dimShapes(d.dim).some((id) => set.has(id));
  const ownDims = new Set<string>(selIds);
  if (selRef) [selRef.outer, ...selRef.holes].forEach((id) => ownDims.add(id));
  const dimhidden = visibleSketchDims(sketchDims, laid.length > 0 && sel?.kind !== "shape" && tool !== "dim" ? dimOf?.f.profile ?? null : null);
  const shownDims = overlays.dims || tool === "dim" ? dimhidden
    : dimhidden.filter((d) => d.dim.id === dimSel || d.dim.id === sdimEdit || named(d, ownDims));
  const quietDims = new Set(shownDims.filter((d) => d.dim.id !== dimSel && d.dim.id !== sdimEdit && !named(d, hotShapes)).map((d) => d.dim.id));
  const hoverPick = tool === "dim" && cursorAt && !drag && !placing ? pickAt(cursorAt) : null;
  const refMark = (ref: DimRef, cls: string): ReactElement | null => {
    if ("axis" in ref) {
      const o = scr([0, 0]);
      return ref.axis === "y" ? <line key={cls + "ay"} x1={o[0]} x2={o[0]} y1={0} y2={h} className={cls} /> : <line key={cls + "ax"} x1={0} x2={w} y1={o[1]} y2={o[1]} className={cls} />;
    }
    const s = shapes.find((x) => x.id === ref.shape);
    if (!s || s.kind === "poly") return null;
    if (ref.at === "c") { const c = scr([s.cx, s.cy]); return <circle key={cls + ref.shape + "c"} cx={c[0]} cy={c[1]} r={4.5} className={cls} />; }
    if (ref.at === "o" || s.kind === "circle") return <path key={cls + ref.shape} d={sl(shapeLoop(s))} className={cls} />;
    const x0 = s.cx - s.w / 2, x1 = s.cx + s.w / 2, y0 = s.cy - s.h / 2, y1 = s.cy + s.h / 2;
    const seg: Record<string, [Vec2, Vec2]> = { l: [[x0, y0], [x0, y1]], r: [[x1, y0], [x1, y1]], b: [[x0, y0], [x1, y0]], t: [[x0, y1], [x1, y1]] };
    const [a, b] = seg[ref.at].map(scr);
    return <line key={cls + ref.shape + ref.at} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} className={cls} />;
  };

  /** A value typed into a sketch dim's box: the geometry follows (one undo step). */
  const commitSketchDim = (d: SketchDim, text: string, fresh: boolean) => {
    const st = useStudio.getState();
    const v = Number(text.trim().replace(",", "."));
    const ok = Number.isFinite(v) && (d.kind === "x" || d.kind === "y" ? v >= 0 : v > 0);
    if (fresh) {
      setPlacing(null);
      if (ok && st.addDim({ ...d, value: typedValue(d, v) })) st.selectDim(d.id);
    } else {
      setSdimEdit(null);
      if (ok && Math.abs(typedValue(d, v) - d.value) > 1e-9) st.setDimValue(d.id, typedValue(d, v));
    }
  };

  // the selected shape's handles
  const handles: ReactElement[] = [];
  if (selShape?.kind === "rect" && tool === "select") {
    for (const hn of HANDLES) {
      const [x, y] = scr(handlePoint(selShape, hn));
      handles.push(<rect key={hn} data-handle={hn} x={x - 4} y={y - 4} width={8} height={8} className={`handle h-${hn}`} />);
    }
  } else if (selShape?.kind === "circle" && tool === "select") {
    const [x, y] = scr([selShape.cx + selShape.r, selShape.cy]);
    handles.push(<rect key="e" data-handle="e" x={x - 4} y={y - 4} width={8} height={8} className="handle h-e" />);
  }

  // several selected: their bounds (Figma's selection box) and the count under them
  const multiShapes = multi.length > 1 ? shapes.filter((s) => multi.includes(s.id)) : [];
  const mb = multiShapes.length > 1 ? sketchBox(multiShapes) : null;
  const bounds = mb ? (() => {
    const [ax, ay] = scr([mb.x0, mb.y1]), [bx, by] = scr([mb.x1, mb.y0]);
    return { x: ax, y: ay, w: bx - ax, h: by - ay };
  })() : null;
  // WHY clamped: the chip stays on the canvas, above the dock, when the bounds run off it
  const chipAt: Vec2 | null = bounds ? [Math.min(Math.max(bounds.x + bounds.w / 2, 60), w - 60), Math.min(Math.max(bounds.y + bounds.h + 8, 28), h - 104)] : null;

  const cursor = drag?.kind === "pan" ? "grabbing" : tool !== "select" ? "crosshair" : hover?.kind === "edge" ? "pointer" : "default";

  // the rotate manipulator's angle box: over the knob (else the rectangle's centre); typing sets the angle
  const rotShape = rot ? shapes.find((x): x is RectShape => x.id === rot.id && x.kind === "rect") ?? null : null;
  const closeRot = () => { setRot(null); useStudio.getState().gesture(false); };
  const commitRot = (text: string) => {
    const st = useStudio.getState();
    const r = st.doc.shapes.find((x) => x.id === rot?.id);
    const t = text.trim().replace(",", ".");
    const v = Number(t);
    if (r?.kind === "rect" && t !== "" && Number.isFinite(v) && Math.abs(deg360(v) - r.angle_deg) > 1e-9) st.updateShape({ ...r, angle_deg: deg360(v) });
    closeRot();
  };
  useEffect(() => { if (rot && !rotShape) closeRot(); });
  const rotAt: Vec2 | null = rotShape ? (knob ? [knob[0], knob[1] - 26] : scr([rotShape.cx, rotShape.cy])) : null;

  return (
    <>
    <div ref={host} className="viewport" data-testid="viewport" data-tool={tool} style={{ cursor }}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
      onPointerLeave={() => { pointer.at = null; if (!drag) { setHover(null); setHoverFid(null); } }} onDoubleClick={onDoubleClick}
      onContextMenu={(e) => e.preventDefault()}>
      <svg ref={svg} width={w} height={h} className="vp-svg" data-zoom={z}>
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0 1L7 4L0 7z" className="arrow" />
          </marker>
        </defs>
        <g className="grid" data-testid="grid" data-background={bg}>{dots}{grid}</g>
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
          {drawn.map(({ f, plan }) => {
            const on = sel?.kind === "feature" && sel.id === f.id;
            const cs = cutShape(plan);
            const guide = !(plan.overflow_mm > 0) && !sameBox(cs.outer, plan.outer);
            // Layers › Quiet-zone guides off: not drawn, but on the marker in focus (its own)
            const guideShown = overlays.guides || f.id === dimFid;
            return (
              <g key={f.id} className={`marker${on ? " on" : ""}`} data-marker={f.id}>
                <path d={sl(plan.outer)} className={`outline${plan.overflow_mm > 0 ? " bad" : ""}`} data-marker-outline="1"
                  style={guide ? (guideShown ? OUTLINE_GUIDE : OUTLINE_GUIDE_OFF) : OUTLINE}
                  data-overflow={plan.overflow_mm} data-guide={guide ? "1" : "0"} />
                {on && guide && <path d={sl(cs.outer) + cs.holes.map(sl).join("")} fillRule="evenodd" data-cut-sel={f.id} style={CUT_SEL} />}
                <path d={plan.black.map((p) => sl(p.outer) + p.holes.map(sl).join("")).join("")} fillRule="evenodd" className="black" data-marker-black="1" />
              </g>
            );
          })}
          {/* WHY an edge that is "off" stays in the DOM, unpainted: its path is the shape's place (what the e2e measures), and a click finds the shape by its geometry, not by this path */}
          {shapes.map((s) => (
            <path key={s.id} d={sl(shapeLoop(s))} data-shape={s.id} data-kind={s.kind}
              className={[
                "edge",
                selIds.has(s.id) && "on",
                hover?.kind === "edge" && hover.id === s.id && "hover",
                featureRects.has(s.id) && "marker-rect",
                edgeLook(s.id),
              ].filter(Boolean).join(" ")} />
          ))}
        </g>
        {draft}
        {tool === "dim" && (
          <g className="dim-picks" data-testid="dim-picks" data-picks={picks.length}>
            <style>{PICK_CSS}</style>
            {shapes.filter((s) => s.kind !== "poly").map((s) => {
              const c = scr([(s as { cx: number }).cx, (s as { cy: number }).cy]);
              return <path key={s.id} d={`M${c[0] - 3} ${c[1]}L${c[0] + 3} ${c[1]}M${c[0]} ${c[1] - 3}L${c[0]} ${c[1] + 3}`} className="pick-centre" />;
            })}
            {hoverPick && refMark(hoverPick, "pick-hover")}
            {picks.map((r) => refMark(r, "pick-on"))}
          </g>
        )}
        <SketchDims dims={shownDims} quiet={quietDims} selected={dimSel} editing={sdimEdit ?? placing?.id ?? null} preview={previewDim}
          onSelect={(id) => useStudio.getState().selectDim(id)} onEdit={(id) => setSdimEdit(id)} />
        {fitBoxOf && (
          <path d={sl(rectCorners(fitBoxOf.rect))} data-fit-rect={fitBoxOf.f.id} className="fit-rect"
            style={{ fill: "none", stroke: "var(--muted)", strokeWidth: 1, strokeDasharray: "5 4", opacity: 0.7, pointerEvents: "none" }} />
        )}
        {dimOf && <Dims fid={dimOf.f.id} dims={laid} editing={editDim?.field ?? null} onEdit={(field) => setDimEdit({ fid: dimOf.f.id, field, start: dimOf.f })} />}
        {triads}
        {arc}
        {labels}
        {infos.length > 0 && <g className="marker-infos" data-testid="marker-infos">{infos}</g>}
        {bounds && <rect className="sel-bounds" data-testid="selection-bounds" x={bounds.x} y={bounds.y} width={bounds.w} height={bounds.h} />}
        <g className="handles">{handles}</g>
        {drag?.kind === "box" && drag.moved && (
          <rect x={Math.min(drag.a[0], drag.b[0])} y={Math.min(drag.a[1], drag.b[1])} width={Math.abs(drag.b[0] - drag.a[0])} height={Math.abs(drag.b[1] - drag.a[1])}
            data-testid="select-box" data-select-box={drag.b[0] < drag.a[0] ? "crossing" : "window"}
            style={drag.b[0] < drag.a[0] ? CROSSING_BOX : WINDOW_BOX} />
        )}
        {overlays.rulers && (
          <g className="ruler" data-testid="rulers">
            <rect x={0} y={0} width={w} height={RULER} className="ruler-bg" />
            {ticks}
          </g>
        )}
      </svg>
      {editDim && dimEdit && dimFid && (
        <DimEditor key={`${dimFid}:${editDim.field}`} dim={editDim}
          onLive={(t) => applyDim(dimFid, editDim.field, t, true)}
          onCommit={(t) => commitDim(dimFid, editDim.field, t)} onCancel={() => revertDim(dimFid, dimEdit.start)} />
      )}
      {chipAt && (
        <div className="sel-count" data-testid="selection-count" data-count={multiShapes.length} style={{ left: chipAt[0], top: chipAt[1] }}>
          {multiShapes.length} selected
        </div>
      )}
      {drawBoxes.length > 0 && <div data-testid="draw-values">{drawBoxes}</div>}
      {rot && rotShape && rotAt && (
        <ValueBox key={rot.live ? `rot-live-${rotShape.angle_deg}` : "rot-edit"} testid="rotate-angle" label="Rotation (°)" at={rotAt}
          value={fmt(rotShape.angle_deg)} focus={!rot.live}
          onCommit={commitRot} onCancel={closeRot} />
      )}
      {placing && previewDim && (
        <ValueBox key={placing.id} testid="sdim-input" label="Dimension (mm)" at={previewDim.at} value={previewDim.text.replace("Ø", "")}
          onCommit={(t) => commitSketchDim(placing, t, true)} onCancel={() => setPlacing(null)} />
      )}
      {editSketchDim && (
        <ValueBox key={editSketchDim.dim.id} testid="sdim-input" label="Dimension (mm)" at={editSketchDim.at} value={editSketchDim.text.replace("Ø", "")}
          onCommit={(t) => commitSketchDim(editSketchDim.dim, t, false)} onCancel={() => setSdimEdit(null)} />
      )}
      {panel.selector && (
        <div className="vp-hint" data-testid="selector-hint">
          Select a profile: click inside a region, or double-click a rectangle
        </div>
      )}
    </div>
    {/* WHY beside the viewport, not in it: React bubbles a portal's events
        through its owner, and the viewport's press handler would take a
        click on a menu row (it captures the pointer) */}
    <CanvasMenu at={menu} onClose={() => setMenu(null)} />
    </>
  );
}
