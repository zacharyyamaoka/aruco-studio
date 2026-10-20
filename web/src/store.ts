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
import { core } from "./coreSource";
import {
  addFeature, addShape, applyIds, deleteShape, emptyDoc, featureOfProfile, featureOfRect, getFeature, keyOwner, newFeature, nextTurn, pickSuggestion,
  rectProfile, removeFeature, resetField, setField, setShape, updateFeature, type Doc, type Feature, type Holes,
} from "./model/doc";
import { boxOf, fitBox, rectCorners, type Camera } from "./model/geom";
import { touchRecent } from "./presets/local";
import { example } from "./model/examples";
import { profileLoops, sketchBox, type ProfileRef, type Selection, type Shape } from "./sketch/model";

export type Tool = "select" | "rect" | "circle";
export type Modal = null | "presets" | "print" | "examples" | "verify" | "reid";
/** the panel's tabs (Zach, 2026-10-20 night, V1 Command Dialog): Make holds the
 *  profile, the preset, trim and the heights; then Marker; then Label */
export type Tab = "make" | "marker" | "label";

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
  note: string | null;
  /** the history has a step to undo / to redo */
  canUndo: boolean;
  canRedo: boolean;

  /** a new document state; edits sharing a `key` (one value, typed) within
   *  IDLE_MS of each other are one undo step */
  setDoc: (doc: Doc, key?: string) => void;
  loadDoc: (doc: Doc) => void;
  newDoc: (exampleId?: string) => void;
  setTool: (t: Tool) => void;
  select: (s: Selection) => void;
  addShape: (s: Shape) => void;
  updateShape: (s: Shape) => void;
  deleteSelection: () => void;
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
  /** Edit › Re-ID all markers…: a core.assign_ids answer for idItems(doc)
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
    return out;
  };

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
    note: null,
    canUndo: false,
    canRedo: false,

    setDoc: (doc, key) => put({ doc }, key),
    loadDoc: (doc) => {
      const preset = doc.preset ?? get().doc.preset;
      openAt = -1;
      put({ doc: { ...doc, preset }, sel: null, panel: PANEL0, plans: {}, planErrors: {}, idIssues: [], suggestions: [], tool: "select" });
      get().fit();
    },
    newDoc: (exampleId) => {
      const ex = exampleId ? example(exampleId) : undefined;
      const doc = emptyDoc(ex?.name ?? "Untitled", ex ? structuredClone(ex.shapes) : [], get().doc.preset);
      get().loadDoc(ex?.features ? { ...doc, features: structuredClone(ex.features) } : doc);
    },
    setTool: (tool) => set({ tool }),
    select: (sel) => set({ sel }),
    addShape: (s) => put({ doc: addShape(get().doc, s), sel: { kind: "shape", id: s.id } }),
    updateShape: (s) => put({ doc: setShape(get().doc, s) }, `shape:${s.id}`),
    deleteSelection: () => {
      const { sel, doc, panel } = get();
      if (sel?.kind === "shape") {
        // a feature whose profile it bounds goes with it
        const next = deleteShape(doc, sel.id);
        const gone = panel.open && !getFeature(next, panel.featureId);
        put({ doc: next, sel: null, ...(gone ? { panel: PANEL0 } : {}) });
      } else if (sel?.kind === "feature" || sel?.kind === "origin") {
        // the feature goes; its profile's shapes stay in the sketch
        put({ doc: removeFeature(doc, sel.id), sel: null, ...(panel.featureId === sel.id ? { panel: PANEL0 } : {}) });
      }
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
      set({ sel: { kind: "feature", id: panel.featureId! }, panel: { ...get().panel, selector: null } });
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
      const next = { panel: { ...PANEL0, tab: panel.tab }, doc: panel.backup ?? get().doc, sel: null };
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
      set({ sel: { kind: "feature", id: f.id } });
    },

    inspect: (id) => {
      const { panel } = get();
      if (panel.open && panel.featureId === id) { set({ sel: { kind: "feature", id } }); return; }
      if (panel.open) get().ok();
      get().editFeature(id);
    },
    closePanel: () => {
      if (get().panel.open) get().ok();
      set({ sel: null });
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

/** Load what the core knows once it answers: the dictionaries and the
 *  built-in presets (the first is the document's preset until one is picked). */
export async function loadCoreFacts(): Promise<void> {
  const [info, builtins] = await Promise.all([core.info(), core.presets()]);
  const s = useStudio.getState();
  useStudio.setState({ info, builtins });
  // WHY inkjet first: Zach moved to inkjet stickers on vinyl (2026-10-17, CF-13);
  // 3D-printed markers stay a placeholder, so a new document starts on paper.
  const first = builtins.find((p) => p.method === "inkjet") ?? builtins[0];
  if (!s.doc.preset && first) useStudio.setState({ doc: { ...useStudio.getState().doc, preset: first } });
}
