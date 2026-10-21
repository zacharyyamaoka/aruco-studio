// The app's state (zustand): the document, the tool, the selection, the
// camera, the panel, the modals, and what the core last answered. The
// document's edits are the pure functions of model/doc.ts and sketch/model.ts.
//
// Undo / redo (Ctrl+Z, Ctrl+Shift+Z / Ctrl+Y) walk the document's history:
// snapshots, since a Doc is never mutated (a step is the document before
// it). Every action that changes the document notes it; what the planner
// writes back (auto id's ids and ledger) is not a step. One gesture (a drag,
// A) is one step, and so is a burst of edits to one value (typing, live)
// while each comes within IDLE_MS of the last. The selection, the camera and
// the panel are not in the history.
//
// WHY (Zach, 2026-10-20): "You should support Ctrl Z to undo any changes that are done."
import { create } from "zustand";
import type { CoreInfo, IdResult, Issue, LabelParams, MarkerPlan, Preset, Suggestion } from "./core/contract";
import { core, coreStatus } from "./coreSource";
import {
  addFeature, addShape, applyIds, deleteShape, emptyDoc, featureOfProfile, featureOfRect, getFeature, keyOwner, newFeature, newId, nextTurn, pickSuggestion,
  rectProfile, removeFeature, resetField, setField, setShape, updateFeature, type Doc, type Feature, type Holes,
} from "./model/doc";
import { boxOf, fitBox, rectCorners, type Camera } from "./model/geom";
import { touchRecent } from "./presets/local";
import { example } from "./model/examples";
import type { Vec2 } from "./core/contract";
import { dimsAmong, lockedAxes, refusal, renameDim, solve, type SketchDim } from "./sketch/constraints";
import { moveShape, profileLoops, sketchBox, type ProfileRef, type Selection, type Shape } from "./sketch/model";

/** dim: Sketch Dimension (D), Fusion's */
export type Tool = "select" | "rect" | "circle" | "dim";
export type Modal = null | "presets" | "print" | "examples" | "verify" | "reid";
/** the panel's tabs (Zach, 2026-10-20 night, V1 Command Dialog): Make holds the
 *  profile, the preset, trim and the heights; then Marker; then Label */
export type Tab = "make" | "marker" | "label";
/** What loadCoreFacts has got: nothing asked yet, asking (its tries), the
 *  dictionaries and presets, or the last try's error. */
export interface Facts { state: "idle" | "asking" | "ok" | "error"; error?: string }

export interface PanelState {
  open: boolean;
  /** the feature the panel edits */
  featureId: string | null;
  tab: Tab;
  collapsed: boolean;
  /** the selection row waiting for a click on the sketch (Profile: the only one) */
  selector: "profile" | null;
  /** the document before the panel opened: Cancel puts it back */
  backup: Doc | null;
}

export interface Studio {
  doc: Doc;
  tool: Tool;
  sel: Selection;
  camera: Camera;
  view: { w: number; h: number };
  /** the canvas shows the 3D model (barrier 10b; the 2D | 3D toggle, V3) -- a view
   *  state, not in the document or its history */
  view3d: boolean;
  panel: PanelState;
  modal: Modal;
  /** each feature's last plan, by feature id (kept drawn while the next computes) */
  plans: Record<string, MarkerPlan>;
  planErrors: Record<string, string>;
  /** auto id's last warnings (core.assign_ids): each names its feature by Issue.key */
  idIssues: Issue[];
  /** for the feature the panel edits */
  suggestions: Suggestion[];
  info: CoreInfo | null;
  builtins: Preset[];
  facts: Facts;
  note: string | null;
  /** the history has a step to undo / to redo */
  canUndo: boolean;
  canRedo: boolean;
  /** every selected shape (a right-drag box, Shift+click): a drag, the arrows,
   *  Del, Ctrl+C and A act on them all. `sel` stays the primary selection, which
   *  the panel reads: the first of them, or the feature A opened */
  multi: string[];
  /** the selected sketch dimension: Del deletes it */
  dimSel: string | null;

  /** a new document state; edits sharing a `key` (one value, typed) within
   *  IDLE_MS of each other are one undo step */
  setDoc: (doc: Doc, key?: string) => void;
  loadDoc: (doc: Doc) => void;
  newDoc: (exampleId?: string) => void;
  setTool: (t: Tool) => void;
  select: (s: Selection) => void;
  /** a drawn shape, with the driving dims its typed values made (one undo step) */
  addShape: (s: Shape, dims?: SketchDim[]) => void;
  updateShape: (s: Shape) => void;
  deleteSelection: () => void;
  /** select these shapes (`add`: to what is selected) */
  selectShapes: (ids: string[], add?: boolean) => void;
  /** Shift+click: add the shape to the selection, or take it out */
  toggleShape: (id: string) => void;
  selectDim: (id: string | null) => void;
  /** a new sketch dimension, its value applied (false: refused, with a note) */
  addDim: (d: SketchDim) => boolean;
  /** a dimension's new value (typed): the geometry follows, one undo step */
  setDimValue: (id: string, value: number) => void;
  /** move shapes from where they were (`base`, the shapes at the drag's start)
   *  by (dx, dy) mm: a shape whose position a dimension sets holds on that axis
   *  (with a note), what they dimension follows */
  moveShapes: (base: Shape[], ids: string[], dx: number, dy: number) => void;
  /** the arrows: the selected shapes by (dx, dy) mm, one undo step */
  nudge: (dx: number, dy: number) => void;
  /** the shapes a move, Del, Ctrl+C act on: the selected ones, else the selected feature's or profile's */
  selectedShapeIds: () => string[];
  /** Ctrl+C: the selected shapes, the features whose profile they all are, the dims among them */
  copy: () => void;
  /** Ctrl+X: copy, then delete them (their features with them) */
  cut: () => void;
  /** Ctrl+V: what was copied, centred at `at` (a sketch point), else 10 mm on
   *  from the last paste; new ids and keys, one undo step */
  paste: (at: Vec2 | null) => void;
  setCamera: (c: Camera) => void;
  setView: (w: number, h: number) => void;
  fit: () => void;
  /** fit one feature (its profile, marker and label) into the view between
   *  `topPx` hidden at its top (the toolbar) and `bottomPx` at its bottom
   *  (the docked panel on a phone) */
  fitFeature: (id: string, topPx: number, bottomPx: number) => void;

  extrude: () => Promise<void>;
  /** the panel's feature takes this profile (the Profile row's pick) */
  useProfile: (ref: ProfileRef) => void;
  setSelector: (s: PanelState["selector"]) => void;
  clearProfile: () => void;
  setHoles: (h: Holes) => void;
  /** set a panel field by hand ("marker.cols", "label.gap_mm", ...) */
  setField: (path: string, value: unknown) => void;
  /** a panel field back to driven */
  resetField: (path: string) => void;
  /** the same for a named feature (the 3D view's drag arrows: the feature in
   *  focus, panel open or not); one undo step per value, like typing */
  setFieldFor: (featureId: string, path: string, value: unknown) => void;
  resetFieldFor: (featureId: string, path: string) => void;
  setView3d: (on: boolean) => void;
  /** a label value that has no row (the drag's offset_mm); the panel's feature unless named */
  setLabel: <K extends keyof LabelParams>(key: K, value: LabelParams[K], featureId?: string) => void;
  /** the panel feature's stable key (auto id hashes it); empty = its id again.
   *  Keys are unique: one another feature has is refused with a note. */
  setKey: (key: string) => void;
  pick: (s: Suggestion) => void;
  turn: (featureId?: string) => void;
  setTab: (t: Tab) => void;
  collapse: (c: boolean) => void;
  ok: () => void;
  cancel: () => void;
  editFeature: (id?: string) => void;
  /** a click on a marker (or its rectangle profile): select that feature and open
   *  its panel; a panel open on another feature closes first (OK) */
  inspect: (id: string) => void;
  /** a click on empty canvas: the panel closes (OK) and nothing is selected */
  closePanel: () => void;

  setPreset: (p: Preset) => void;
  /** Edit › ArUco Re-ID…: a core.assign_ids answer for idItems(doc)
   *  (sequential or fresh hash) into the document's ids and ledger, as one undo step */
  reId: (res: IdResult) => void;
  openModal: (m: Modal) => void;
  say: (note: string | null) => void;

  undo: () => void;
  redo: () => void;
  /** a gesture (a drag) starts / ends: its edits are one undo step */
  gesture: (on: boolean) => void;
}

/** Undo steps kept. */
const HISTORY = 200;
/** Edits to one value this close together are one step (ms). */
const IDLE_MS = 500;

const PANEL0: PanelState = { open: false, featureId: null, tab: "marker", collapsed: false, selector: null, backup: null };

/** What Ctrl+C holds: shapes, the features on them and the dims among them. */
export interface Clip { format: "arucostudio-clip"; shapes: Shape[]; features: Feature[]; dims: SketchDim[] }

/** The selection fields for a new primary selection: a shape is the only one selected. */
const only = (sel: Selection): Pick<Studio, "sel" | "multi" | "dimSel"> => ({ sel, multi: sel?.kind === "shape" ? [sel.id] : [], dimSel: null });

/** The feature the selection names: a feature, its Joint Origin or its label,
 *  the rectangle that is its profile, or its profile. */
export function selectedFeatureId(doc: Doc, sel: Selection): string | null {
  if (sel?.kind === "feature" || sel?.kind === "origin" || sel?.kind === "text") return getFeature(doc, sel.id)?.id ?? null;
  if (sel?.kind === "shape") return featureOfRect(doc, sel.id)?.id ?? null;
  if (sel?.kind === "profile") return featureOfProfile(doc, sel.ref)?.id ?? null;
  return null;
}

/** The feature in focus: the one the panel edits, else the selected one,
 *  else the last made (Export SVG, the outer dimension and the turn arc). */
export function activeFeatureId(s: Pick<Studio, "doc" | "sel" | "panel">): string | null {
  if (s.panel.open && s.panel.featureId) return s.panel.featureId;
  return selectedFeatureId(s.doc, s.sel) ?? s.doc.features[s.doc.features.length - 1]?.id ?? null;
}

export const useStudio = create<Studio>((set, get) => {
  // ---------------------------------------------------------------- the history
  const past: Doc[] = [];
  let future: Doc[] = [];
  /** the last step's key and when it last grew: the next edit with that key, soon, joins it */
  let last: { key: string; at: number } | null = null;
  /** an open gesture: its first change is a step, the rest join it */
  let held: { stepped: boolean } | null = null;
  /** past's length when the panel opened: Cancel rewinds the history to it */
  let openAt = -1;
  const same = (a: Doc, b: Doc) => a === b || JSON.stringify(a) === JSON.stringify(b);
  const flags = () => ({ canUndo: past.length > 0, canRedo: future.length > 0 });
  /** Note a change of the document from `prev` to `next`. */
  const remember = (prev: Doc, next: Doc, key: string) => {
    const now = performance.now();
    if (held?.stepped) return;
    if (!held && key && last?.key === key) {
      // edits to one value that end where they began (Esc) are no step
      if (past.length && same(next, past[past.length - 1])) { past.pop(); last = null; return; }
      if (now - last.at < IDLE_MS) { last.at = now; return; }
    }
    if (same(prev, next)) return;
    past.push(prev);
    if (past.length > HISTORY) { past.shift(); if (openAt > 0) openAt -= 1; }
    future = [];
    last = key ? { key, at: now } : null;
    if (held) held.stepped = true;
  };
  /** set(), noting a change of the document in the history. */
  const put = (next: Partial<Studio>, key = "") => {
    if (next.doc && next.doc !== get().doc) remember(get().doc, next.doc, key);
    set({ ...next, ...flags() });
  };
  /** What an undone / redone document keeps of the selection and the panel:
   *  only what is still in it. */
  const still = (doc: Doc): Partial<Studio> => {
    const { sel, panel } = get();
    const out: Partial<Studio> = {};
    if (panel.open && !getFeature(doc, panel.featureId)) { out.panel = { ...PANEL0, tab: panel.tab, collapsed: panel.collapsed }; openAt = -1; }
    const there = !sel || sel.kind === "sketch" ? true
      : sel.kind === "shape" ? doc.shapes.some((x) => x.id === sel.id)
      : sel.kind === "profile" ? !!profileLoops(doc.shapes, sel.ref)
      : !!getFeature(doc, sel.id);
    if (!there) out.sel = null;
    const multi = get().multi.filter((id) => doc.shapes.some((x) => x.id === id));
    if (multi.length !== get().multi.length) out.multi = multi;
    if (get().dimSel && !doc.dims.some((d) => d.id === get().dimSel)) out.dimSel = null;
    return out;
  };

  /** the clipboard (in memory; the system's too when the page may write it) and the pastes made from it */
  let clip: Clip | null = null;
  let pastes = 0;

  /** Edit the feature the panel edits (`key`: see setDoc). */
  const edit = (fn: (f: Feature) => Feature, key = "") => put({ doc: updateFeature(get().doc, get().panel.featureId, fn) }, key);
  const editing = () => getFeature(get().doc, get().panel.featureId);
  /** Open the panel on a feature (made new when `fresh`), keeping the
   *  document before it for Cancel. */
  const open = (doc: Doc, f: Feature, fresh: boolean) => {
    const backup = get().doc;
    openAt = past.length;
    put({
      doc: fresh ? addFeature(doc, f) : doc,
      panel: { ...PANEL0, open: true, featureId: f.id, backup, tab: get().panel.tab, collapsed: get().panel.collapsed },
      tool: "select",
    });
  };

  return {
    doc: emptyDoc("Plate", example("plate")!.shapes),
    tool: "select",
    sel: null,
    camera: { cx: 60, cy: 40, zoom: 4 },
    view: { w: 800, h: 600 },
    view3d: false,
    panel: PANEL0,
    modal: null,
    plans: {},
    planErrors: {},
    idIssues: [],
    suggestions: [],
    info: null,
    builtins: [],
    facts: { state: "idle" },
    note: null,
    canUndo: false,
    canRedo: false,
    multi: [],
    dimSel: null,

    setDoc: (doc, key) => put({ doc }, key),
    loadDoc: (doc) => {
      const preset = doc.preset ?? get().doc.preset;
      openAt = -1;
      put({ doc: { ...doc, dims: doc.dims ?? [], preset }, ...only(null), panel: PANEL0, plans: {}, planErrors: {}, idIssues: [], suggestions: [], tool: "select" });
      get().fit();
    },
    newDoc: (exampleId) => {
      const ex = exampleId ? example(exampleId) : undefined;
      const doc = emptyDoc(ex?.name ?? "Untitled", ex ? structuredClone(ex.shapes) : [], get().doc.preset);
      get().loadDoc(ex?.features ? { ...doc, features: structuredClone(ex.features) } : doc);
    },
    setTool: (tool) => set({ tool }),
    select: (sel) => set(only(sel)),
    addShape: (s, dims = []) => {
      const doc = addShape(get().doc, s);
      put({ doc: dims.length ? { ...doc, dims: [...doc.dims, ...dims], shapes: solve(doc.shapes, [...doc.dims, ...dims]) } : doc, ...only({ kind: "shape", id: s.id }) });
    },
    // what the shape dimensions follows it (solve)
    updateShape: (s) => {
      const doc = setShape(get().doc, s);
      put({ doc: { ...doc, shapes: solve(doc.shapes, doc.dims) } }, `shape:${s.id}`);
    },
    deleteSelection: () => {
      const { sel, doc, panel, multi, dimSel } = get();
      if (dimSel) {
        put({ doc: { ...doc, dims: doc.dims.filter((d) => d.id !== dimSel) }, dimSel: null });
      } else if (sel?.kind === "shape" || multi.length > 1) {
        // every selected shape; a feature whose profile it bounds goes with it
        const ids = [...new Set([...multi, ...(sel?.kind === "shape" ? [sel.id] : [])])];
        const next = ids.reduce(deleteShape, doc);
        const gone = panel.open && !getFeature(next, panel.featureId);
        openAt = gone ? -1 : openAt;
        put({ doc: next, ...only(null), ...(gone ? { panel: PANEL0 } : {}) });
      } else if (sel?.kind === "feature" || sel?.kind === "origin") {
        // the feature goes; its profile's shapes stay in the sketch
        put({ doc: removeFeature(doc, sel.id), sel: null, ...(panel.featureId === sel.id ? { panel: PANEL0 } : {}) });
      }
    },
    selectShapes: (ids, add = false) => {
      const multi = add ? [...new Set([...get().multi, ...ids])] : [...new Set(ids)];
      if (get().panel.open && multi.length) get().ok();
      set({ multi, sel: multi.length ? { kind: "shape", id: multi[0] } : null, dimSel: null });
    },
    toggleShape: (id) => {
      const { multi, sel } = get();
      const base = multi.length ? multi : sel?.kind === "shape" ? [sel.id] : [];
      const next = base.includes(id) ? base.filter((x) => x !== id) : [...base, id];
      if (get().panel.open) get().ok();
      set({ multi: next, sel: next.length ? { kind: "shape", id: next.includes(id) ? id : next[0] } : null, dimSel: null });
    },
    selectDim: (dimSel) => set(dimSel ? { sel: null, multi: [], dimSel } : { dimSel }),
    addDim: (d) => {
      const { doc } = get();
      const why = refusal(doc.shapes, doc.dims, d);
      if (why) { set({ note: why }); return false; }
      const dims = [...doc.dims, d];
      put({ doc: { ...doc, dims, shapes: solve(doc.shapes, dims) } });
      return true;
    },
    setDimValue: (id, value) => {
      const { doc } = get();
      const dims = doc.dims.map((d) => (d.id === id ? { ...d, value } : d));
      put({ doc: { ...doc, dims, shapes: solve(doc.shapes, dims) } });
    },
    moveShapes: (base, ids, dx, dy) => {
      const { doc } = get();
      // WHY held (Fusion): a dimensioned position does not move by hand; what
      // it is measured from does, and solve() brings it along
      const moved = base.map((s) => {
        if (!ids.includes(s.id)) return s;
        const lock = lockedAxes(base, doc.dims, s.id);
        return moveShape(s, lock.x ? 0 : dx, lock.y ? 0 : dy);
      });
      const shapes = solve(moved, doc.dims);
      const want = moveShape({ kind: "circle", id: "", cx: 0, cy: 0, r: 1 }, dx, dy) as { cx: number; cy: number };
      const held = { x: false, y: false };
      for (const id of ids) {
        const a = base.find((s) => s.id === id), b = shapes.find((s) => s.id === id);
        if (!a || !b || a.kind === "poly" || b.kind === "poly") continue;
        if (Math.abs(b.cx - a.cx - want.cx) > 1e-6) held.x = true;
        if (Math.abs(b.cy - a.cy - want.cy) > 1e-6) held.y = true;
      }
      const axes = [held.x && "x", held.y && "y"].filter(Boolean).join(" and ");
      put({ doc: { ...doc, shapes }, ...(axes ? { note: `Held on ${axes}: a dimension places it there.` } : {}) });
    },
    nudge: (dx, dy) => {
      const ids = get().selectedShapeIds();
      if (ids.length) get().moveShapes(get().doc.shapes, ids, dx, dy);
    },
    selectedShapeIds: () => {
      const { multi, sel, doc } = get();
      if (multi.length) return multi;
      if (sel?.kind === "shape") return [sel.id];
      const ref = sel?.kind === "profile" ? sel.ref
        : sel?.kind === "feature" || sel?.kind === "origin" || sel?.kind === "text" ? getFeature(doc, sel.id)?.profile : null;
      return ref ? [ref.outer, ...ref.holes].filter((id) => doc.shapes.some((s) => s.id === id)) : [];
    },
    copy: () => {
      const { doc } = get();
      const ids = get().selectedShapeIds();
      if (!ids.length) return;
      const shapes = doc.shapes.filter((s) => ids.includes(s.id));
      const features = doc.features.filter((f) => f.profile && [f.profile.outer, ...f.profile.holes].every((id) => ids.includes(id)));
      clip = structuredClone({ format: "arucostudio-clip", shapes, features, dims: dimsAmong(doc.dims, ids) });
      pastes = 0;
      // the system clipboard too, when the page may write it (the paste reads the copy in memory)
      try { void navigator.clipboard?.writeText(JSON.stringify(clip)).catch(() => {}); } catch { /* not allowed: memory only */ }
      set({ note: `Copied ${shapes.length} shape${shapes.length === 1 ? "" : "s"}${features.length ? ` and ${features.length} ArUco Extrude${features.length === 1 ? "" : "s"}` : ""}.` });
    },
    cut: () => {
      const ids = get().selectedShapeIds();
      if (!ids.length) return;
      get().copy();
      const { doc, panel } = get();
      const next = ids.reduce(deleteShape, doc);
      const gone = panel.open && !getFeature(next, panel.featureId);
      if (gone) openAt = -1;
      put({ doc: next, ...only(null), ...(gone ? { panel: PANEL0 } : {}) });
    },
    paste: (at) => {
      if (!clip || !clip.shapes.length) return;
      if (get().panel.open) get().ok();
      const { doc } = get();
      const b = sketchBox(clip.shapes)!;
      pastes += 1;
      // at the cursor (the copy's middle there), else 10 mm on (right, down) per paste
      const [dx, dy] = at ? [at[0] - (b.x0 + b.x1) / 2, at[1] - (b.y0 + b.y1) / 2] : [10 * pastes, -10 * pastes];
      const map: Record<string, string> = {};
      const shapes = clip.shapes.map((s) => {
        map[s.id] = newId(s.kind === "rect" ? "r" : s.kind === "circle" ? "c" : "p");
        return { ...moveShape(structuredClone(s), dx, dy), id: map[s.id] };
      });
      // new ids and keys: auto id hands each pasted feature new marker ids; every setting is kept
      const features = clip.features.map((f) => {
        const id = newId("f");
        return { ...structuredClone(f), id, key: id, profile: { outer: map[f.profile!.outer], holes: f.profile!.holes.map((h) => map[h]) } };
      });
      const dims = clip.dims.map((d) => renameDim(d, newId("d"), map));
      const allDims = [...doc.dims, ...dims];
      const next = { ...doc, shapes: solve([...doc.shapes, ...shapes], allDims), features: [...doc.features, ...features], dims: allDims };
      put({ doc: next, multi: shapes.map((s) => s.id), sel: { kind: "shape", id: shapes[0].id }, dimSel: null, tool: "select" });
    },
    setCamera: (camera) => set({ camera }),
    setView: (w, h) => set({ view: { w, h } }),
    fit: () => {
      const { doc, view, plans } = get();
      let b = sketchBox(doc.shapes);
      for (const plan of Object.values(plans)) {
        // the outline and the label's centre a cap height either side
        const lab = plan.label ? [[plan.label.at[0], plan.label.at[1] - plan.label.height_mm], [plan.label.at[0], plan.label.at[1] + plan.label.height_mm]] : [];
        for (const [x, y] of [...plan.outer, ...lab]) b = b ? { x0: Math.min(b.x0, x), y0: Math.min(b.y0, y), x1: Math.max(b.x1, x), y1: Math.max(b.y1, y) } : { x0: x, y0: y, x1: x, y1: y };
      }
      set({ camera: fitBox(b ?? { x0: -50, y0: -50, x1: 50, y1: 50 }, view.w, view.h, view.w < 640 ? 28 : 84) });
    },

    fitFeature: (id, topPx, bottomPx) => {
      const { doc, view, plans } = get();
      const ref = getFeature(doc, id)?.profile;
      const pr = ref ? profileLoops(doc.shapes, ref) : null;
      if (!pr) return;
      // the marker, the box it was placed in and its label (the profile until it plans)
      const plan = plans[id];
      const b = boxOf(plan ? [...(plan.fit_rect ? rectCorners(plan.fit_rect) : []), ...plan.outer, ...(plan.label ? [plan.label.at] : [])] : pr.loops[0]);
      const visible = Math.max(80, view.h - topPx - bottomPx);
      const cam = fitBox(b, view.w, visible, 20);
      // fitBox centres it in a view `visible` tall; the real one has topPx more
      // above and bottomPx more below, so its middle sits (bottomPx - topPx) / 2 lower
      set({ camera: { ...cam, cy: cam.cy - (bottomPx - topPx) / 2 / cam.zoom } });
    },

    // ---------------------------------------------------------------- ArUco Extrude
    // A on a profile (or a rectangle) that already has a feature opens that
    // feature; A on a new profile makes a new one; A on a selected feature
    // opens it; A on nothing makes a new one whose Profile row waits for a
    // click. A panel open on another feature closes first (OK).
    // WHY a selected rectangle counts (2026-10-20 evening): drawing a rectangle
    // leaves it selected, and R, drag, A was the custom placement's happy path;
    // A takes its outer edges, as a double-click on it would.
    extrude: async () => {
      // WHY (Zach, 2026-10-20 night: "an Aruco marker maker, however on a
      // canvas"): A on several selected rectangles makes one feature in each
      // (a rectangle profile, the defaults, its own auto id) as one step; the
      // panel opens on the first, the rectangles stay selected
      const many = get().multi.length > 1
        ? get().multi.map((id) => get().doc.shapes.find((s) => s.id === id)).filter((s): s is Shape => s?.kind === "rect") : [];
      if (many.length > 1) {
        if (get().panel.open) get().ok();
        const { doc, panel, multi } = get();
        const fresh = many.filter((r) => !featureOfRect(doc, r.id)).map((r) => newFeature(rectProfile(r.id)));
        if (!fresh.length) { set({ note: "Those rectangles already have ArUco Extrudes: click a marker to edit it." }); return; }
        openAt = past.length;
        put({
          doc: fresh.reduce(addFeature, doc),
          panel: { ...PANEL0, open: true, featureId: fresh[0].id, backup: doc, tab: panel.tab, collapsed: panel.collapsed },
          tool: "select", sel: { kind: "feature", id: fresh[0].id }, multi, dimSel: null,
          note: `${fresh.length} ArUco Extrudes, one in each rectangle.`,
        });
        return;
      }
      if (get().panel.open) {
        if (get().panel.selector || selectedFeatureId(get().doc, get().sel) === get().panel.featureId) return;
        get().ok();
      }
      const { sel, doc } = get();
      const owner = selectedFeatureId(doc, sel);
      if (owner) { get().editFeature(owner); return; }
      // the new feature and the rectangle (or profile) it takes are one step
      held = { stepped: false };
      try {
        const f = newFeature(null);
        open(doc, f, true);
        const ref = sel?.kind === "profile" ? sel.ref
          : sel?.kind === "shape" && doc.shapes.find((s) => s.id === sel.id)?.kind === "rect" ? rectProfile(sel.id) : null;
        if (ref) get().useProfile(ref);
        else set({ panel: { ...get().panel, selector: "profile" } });
      } finally {
        held = null;
        last = null;
      }
    },
    useProfile: (ref) => {
      const { doc, panel } = get();
      const other = featureOfProfile(doc, ref);
      if (other && other.id !== panel.featureId) { set({ note: "That profile already has an ArUco Extrude: click its marker to edit it." }); return; }
      if (!profileLoops(doc.shapes, ref) || !editing()) return;
      edit((f) => ({ ...f, profile: ref }));
      set({ ...only({ kind: "feature", id: panel.featureId! }), panel: { ...get().panel, selector: null } });
    },
    setSelector: (selector) => set({ panel: { ...get().panel, selector } }),
    clearProfile: () => {
      edit((f) => ({ ...f, profile: null }));
      set({ panel: { ...get().panel, selector: "profile" } });
    },
    // the plan request carries the choice: the core places the marker anew
    setHoles: (holes) => edit((f) => ({ ...f, holes })),
    setField: (path, value) => edit((f) => setField(f, path, value), `field:${get().panel.featureId}:${path}`),
    resetField: (path) => edit((f) => resetField(f, path), `field:${get().panel.featureId}:${path}`),
    setFieldFor: (fid, path, value) => put({ doc: updateFeature(get().doc, fid, (f) => setField(f, path, value)) }, `field:${fid}:${path}`),
    resetFieldFor: (fid, path) => put({ doc: updateFeature(get().doc, fid, (f) => resetField(f, path)) }, `field:${fid}:${path}`),
    setView3d: (view3d) => set({ view3d }),
    setLabel: (key, value, featureId) => {
      const fid = featureId ?? get().panel.featureId;
      put({ doc: updateFeature(get().doc, fid, (f) => ({ ...f, label: { ...f.label, [key]: value } })) }, `label:${fid}:${key}`);
    },
    setKey: (key) => {
      const f = editing();
      if (!f) return;
      const k = key.trim() || f.id;
      const other = keyOwner(get().doc, f.id, k);
      if (other) { set({ note: `Key "${k}" is taken by another marker: keys are unique.` }); return; }
      edit((g) => ({ ...g, key: k }), `key:${f.id}`);
    },
    pick: (s) => edit((f) => pickSuggestion(f, s)),
    turn: (featureId) => put({
      doc: updateFeature(get().doc, featureId ?? activeFeatureId(get()), (f) => setField(f, "marker.turn", nextTurn(f.marker.turn))),
    }),
    setTab: (tab) => set({ panel: { ...get().panel, tab } }),
    collapse: (collapsed) => set({ panel: { ...get().panel, collapsed } }),
    ok: () => {
      const { doc, panel } = get();
      const f = getFeature(doc, panel.featureId);
      // OK without a profile makes nothing
      openAt = -1;
      put({ panel: { ...PANEL0, tab: panel.tab }, doc: f && !f.profile ? removeFeature(doc, f.id) : doc });
    },
    cancel: () => {
      const { panel } = get();
      const next = { panel: { ...PANEL0, tab: panel.tab }, doc: panel.backup ?? get().doc, ...only(null) };
      // Cancel takes the panel's steps back out of the history: as if it never opened
      if (openAt >= 0 && past.length >= openAt && panel.backup) {
        past.length = openAt;
        future = [];
        last = null;
        set({ ...next, ...flags() });
      } else put(next);
      openAt = -1;
    },
    editFeature: (id) => {
      const { doc, panel, sel } = get();
      const f = getFeature(doc, id ?? selectedFeatureId(doc, sel));
      if (!f || panel.open) return;
      open(doc, f, false);
      set(only({ kind: "feature", id: f.id }));
    },

    inspect: (id) => {
      const { panel } = get();
      if (panel.open && panel.featureId === id) { set(only({ kind: "feature", id })); return; }
      if (panel.open) get().ok();
      get().editFeature(id);
    },
    closePanel: () => {
      if (get().panel.open) get().ok();
      set(only(null));
    },

    setPreset: (p) => {
      touchRecent(p.id);
      put({ doc: { ...get().doc, preset: p } });
    },
    // the planner's next auto id call (hash, with this ledger) keeps these ids
    reId: (res) => put({ doc: applyIds(get().doc, res) }),
    openModal: (modal) => set({ modal }),
    say: (note) => set({ note }),

    undo: () => {
      const doc = past.pop();
      if (!doc) return;
      future.push(get().doc);
      last = null;
      held = null;
      set({ doc, ...still(doc), ...flags() });
    },
    redo: () => {
      const doc = future.pop();
      if (!doc) return;
      past.push(get().doc);
      last = null;
      held = null;
      set({ doc, ...still(doc), ...flags() });
    },
    gesture: (on) => {
      held = on ? { stepped: false } : null;
      last = null;
    },
  };
});

/** Tries at the core's facts, and the pause before each try after the first (ms). */
const FACT_TRIES = 3;
const FACT_BACKOFF_MS = [600, 1800];
let asking: Promise<void> | null = null;

/** Load what the core knows once it answers: the dictionaries and the
 *  built-in presets (the first is the document's preset until one is picked).
 *  A rejected call is tried again (FACT_TRIES, backing off); after the last,
 *  `facts` holds the error until a Retry (the panel's) or the core's next
 *  ready asks again. One ask at a time: a second call joins the first.
 *  WHY (Zach, 2026-10-20 night, "BUG: seems to be stuck loading?"): it ran
 *  once, and one failed call left the preset null and the panel on "Loading…"
 *  for good, with only a 4 s toast to say why. */
export function loadCoreFacts(): Promise<void> {
  asking ??= askFacts().finally(() => { asking = null; });
  return asking;
}

async function askFacts(): Promise<void> {
  useStudio.setState({ facts: { state: "asking" } });
  let why = "no answer";
  for (let i = 0; i < FACT_TRIES; i++) {
    if (i) await new Promise((r) => setTimeout(r, FACT_BACKOFF_MS[i - 1] ?? FACT_BACKOFF_MS[FACT_BACKOFF_MS.length - 1]));
    // a core that failed to load rejects every call: its own error says why
    if (coreStatus().state === "error") { why = coreStatus().detail ?? "the core failed to load"; break; }
    try {
      const [info, builtins] = await Promise.all([core.info(), core.presets()]);
      const s = useStudio.getState();
      useStudio.setState({ info, builtins, facts: { state: "ok" } });
      // WHY inkjet first: Zach moved to inkjet stickers on vinyl (2026-10-17, CF-13);
      // 3D-printed markers stay a placeholder, so a new document starts on paper.
      const first = builtins.find((p) => p.method === "inkjet") ?? builtins[0];
      if (!s.doc.preset && first) useStudio.setState({ doc: { ...useStudio.getState().doc, preset: first } });
      return;
    } catch (e) {
      why = e instanceof Error ? e.message : String(e);
    }
  }
  useStudio.setState({ facts: { state: "error", error: why } });
}
