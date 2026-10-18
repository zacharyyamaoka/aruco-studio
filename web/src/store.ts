// The app's state (zustand): the document, the tool, the selection, the
// camera, the panel, the modals, and what the core last answered. The
// document's edits are the pure functions of model/doc.ts and sketch/model.ts.
import { create } from "zustand";
import type { CoreInfo, LabelParams, MarkerPlan, Preset, Suggestion } from "./core/contract";
import { core } from "./coreSource";
import {
  addFeature, addShape, deleteShape, emptyDoc, featureOfRect, featureRect, getFeature, newFeature, newId, nextTurn, pickSuggestion,
  removeFeature, resetField, setField, setShape, updateFeature, type Doc, type Feature, type Holes,
} from "./model/doc";
import { fitBox, type Camera } from "./model/geom";
import { touchRecent } from "./presets/local";
import { example } from "./sketch/examples";
import { plainRect, profileLoops, shapeBox, sketchBox, type ProfileRef, type Selection, type Shape } from "./sketch/model";

export type Tool = "select" | "rect" | "circle";
export type Modal = null | "presets" | "print" | "examples" | "verify";
export type Tab = "marker" | "label";

export interface PanelState {
  open: boolean;
  /** the feature the panel edits */
  featureId: string | null;
  tab: Tab;
  collapsed: boolean;
  /** the selection row waiting for a click on the sketch */
  selector: "rect" | "profile" | null;
  /** the document before the panel opened: Cancel puts it back */
  backup: Doc | null;
}

export interface Studio {
  doc: Doc;
  tool: Tool;
  sel: Selection;
  camera: Camera;
  view: { w: number; h: number };
  panel: PanelState;
  modal: Modal;
  /** each feature's last plan, by feature id (kept drawn while the next computes) */
  plans: Record<string, MarkerPlan>;
  planErrors: Record<string, string>;
  /** for the feature the panel edits */
  suggestions: Suggestion[];
  info: CoreInfo | null;
  builtins: Preset[];
  /** a profile is being inscribed */
  inscribing: boolean;
  note: string | null;

  setDoc: (doc: Doc) => void;
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
  /** fit one feature (its rectangle, marker and label) into the view between
   *  `topPx` hidden at its top (the toolbar) and `bottomPx` at its bottom
   *  (the docked panel on a phone) */
  fitFeature: (id: string, topPx: number, bottomPx: number) => void;

  extrude: () => Promise<void>;
  useRect: (id: string) => void;
  useProfile: (ref: ProfileRef) => Promise<void>;
  setProfile: (ref: ProfileRef) => void;
  setSelector: (s: PanelState["selector"]) => void;
  clearRect: () => void;
  clearProfile: () => void;
  setHoles: (h: Holes) => Promise<void>;
  /** set a panel field by hand ("marker.cols", "label.gap_mm", ...) */
  setField: (path: string, value: unknown) => void;
  /** a panel field back to driven */
  resetField: (path: string) => void;
  /** a label value that has no row (the drag's offset_mm); the panel's feature unless named */
  setLabel: <K extends keyof LabelParams>(key: K, value: LabelParams[K], featureId?: string) => void;
  pick: (s: Suggestion) => void;
  turn: (featureId?: string) => void;
  setTab: (t: Tab) => void;
  collapse: (c: boolean) => void;
  ok: () => void;
  cancel: () => void;
  editFeature: (id?: string) => void;
  /** a click on a marker (or its rectangle): select that feature and open
   *  its panel; a panel open on another feature closes first (OK) */
  inspect: (id: string) => void;
  /** a click on empty canvas: the panel closes (OK) and nothing is selected */
  closePanel: () => void;

  setPreset: (p: Preset) => void;
  openModal: (m: Modal) => void;
  say: (note: string | null) => void;
}

const PANEL0: PanelState = { open: false, featureId: null, tab: "marker", collapsed: false, selector: null, backup: null };

/** The feature the selection names: a feature, its Joint Origin or its label,
 *  or the rectangle it fills. */
export function selectedFeatureId(doc: Doc, sel: Selection): string | null {
  if (sel?.kind === "feature" || sel?.kind === "origin" || sel?.kind === "text") return getFeature(doc, sel.id)?.id ?? null;
  if (sel?.kind === "shape") return featureOfRect(doc, sel.id)?.id ?? null;
  if (sel?.kind === "profile") {
    const plain = plainRect(doc.shapes, sel.ref);
    return plain ? featureOfRect(doc, plain.id)?.id ?? null : null;
  }
  return null;
}

/** The feature in focus: the one the panel edits, else the selected one,
 *  else the last made (Export SVG, the outer dimension and the turn arc). */
export function activeFeatureId(s: Pick<Studio, "doc" | "sel" | "panel">): string | null {
  if (s.panel.open && s.panel.featureId) return s.panel.featureId;
  return selectedFeatureId(s.doc, s.sel) ?? s.doc.features[s.doc.features.length - 1]?.id ?? null;
}

export const useStudio = create<Studio>((set, get) => {
  /** Edit the feature the panel edits. */
  const edit = (fn: (f: Feature) => Feature) => set({ doc: updateFeature(get().doc, get().panel.featureId, fn) });
  const editing = () => getFeature(get().doc, get().panel.featureId);
  /** Open the panel on a feature (made new when `fresh`), keeping the
   *  document before it for Cancel. */
  const open = (doc: Doc, f: Feature, fresh: boolean) => {
    const backup = get().doc;
    set({
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
    panel: PANEL0,
    modal: null,
    plans: {},
    planErrors: {},
    suggestions: [],
    info: null,
    builtins: [],
    inscribing: false,
    note: null,

    setDoc: (doc) => set({ doc }),
    loadDoc: (doc) => {
      const preset = doc.preset ?? get().doc.preset;
      set({ doc: { ...doc, preset }, sel: null, panel: PANEL0, plans: {}, planErrors: {}, suggestions: [], tool: "select" });
      get().fit();
    },
    newDoc: (exampleId) => {
      const ex = exampleId ? example(exampleId) : undefined;
      get().loadDoc(emptyDoc(ex?.name ?? "Untitled", ex ? structuredClone(ex.shapes) : [], get().doc.preset));
    },
    setTool: (tool) => set({ tool }),
    select: (sel) => set({ sel }),
    addShape: (s) => set({ doc: addShape(get().doc, s), sel: { kind: "shape", id: s.id } }),
    updateShape: (s) => set({ doc: setShape(get().doc, s) }),
    deleteSelection: () => {
      const { sel, doc, panel } = get();
      if (sel?.kind === "shape") {
        // a feature filling it goes with it
        const gone = featureOfRect(doc, sel.id)?.id;
        set({ doc: deleteShape(doc, sel.id), sel: null, ...(gone && panel.featureId === gone ? { panel: PANEL0 } : {}) });
      } else if (sel?.kind === "feature" || sel?.kind === "origin") {
        // the feature goes; its rectangle stays in the sketch
        set({ doc: removeFeature(doc, sel.id), sel: null, ...(panel.featureId === sel.id ? { panel: PANEL0 } : {}) });
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
      const r = featureRect(doc, getFeature(doc, id));
      if (!r) return;
      const b = shapeBox(r);
      const plan = plans[id];
      const pts = plan ? [...plan.outer, ...(plan.label ? [plan.label.at] : [])] : [];
      for (const [x, y] of pts) { b.x0 = Math.min(b.x0, x); b.y0 = Math.min(b.y0, y); b.x1 = Math.max(b.x1, x); b.y1 = Math.max(b.y1, y); }
      const visible = Math.max(80, view.h - topPx - bottomPx);
      const cam = fitBox(b, view.w, visible, 20);
      // fitBox centres it in a view `visible` tall; the real one has topPx more
      // above and bottomPx more below, so its middle sits (bottomPx - topPx) / 2 lower
      set({ camera: { ...cam, cy: cam.cy - (bottomPx - topPx) / 2 / cam.zoom } });
    },

    // ---------------------------------------------------------------- ArUco Extrude
    // A on a rectangle (or a plain rectangle's profile) that already has a
    // feature opens that feature; A on a new rectangle or profile makes a new
    // one; A on a selected feature opens it; A on nothing makes a new one that
    // waits for a rectangle. A panel open on another feature closes first (OK).
    extrude: async () => {
      if (get().panel.open) {
        if (get().panel.selector || selectedFeatureId(get().doc, get().sel) === get().panel.featureId) return;
        get().ok();
      }
      const { sel, doc } = get();
      const owner = selectedFeatureId(doc, sel);
      if (owner) { get().editFeature(owner); return; }
      const f = newFeature(null, null);
      open(doc, f, true);
      if (sel?.kind === "shape" && doc.shapes.find((s) => s.id === sel.id)?.kind === "rect") get().useRect(sel.id);
      else if (sel?.kind === "profile") await get().useProfile(sel.ref);
      else set({ panel: { ...get().panel, selector: "rect" } });
    },
    useRect: (id) => {
      const other = featureOfRect(get().doc, id);
      if (other && other.id !== get().panel.featureId) { set({ note: "That rectangle already has an ArUco Extrude: double-click it to edit." }); return; }
      edit((f) => ({ ...f, rectId: id }));
      set({ sel: { kind: "feature", id: get().panel.featureId! }, panel: { ...get().panel, selector: null } });
    },
    useProfile: async (ref) => {
      const { doc } = get();
      const plain = plainRect(doc.shapes, ref);
      if (plain) {
        const other = featureOfRect(doc, plain.id);
        if (other && other.id !== get().panel.featureId) { set({ note: "That rectangle already has an ArUco Extrude: double-click it to edit." }); return; }
        edit((f) => ({ ...f, rectId: plain.id, profile: null }));
        set({ sel: { kind: "feature", id: get().panel.featureId! }, panel: { ...get().panel, selector: null } });
        return;
      }
      const loops = profileLoops(doc.shapes, ref);
      const f0 = editing();
      if (!loops || !f0) return;
      const fid = f0.id;
      set({ inscribing: true, panel: { ...get().panel, selector: null }, sel: { kind: "profile", ref } });
      try {
        const rect = await core.inscribe(loops, f0.holes);
        if (!rect) { set({ note: "Nothing fits in that profile." }); return; }
        const cur = get().doc;
        const f = getFeature(cur, fid);
        if (!f) return;
        // re-inscribing the same profile moves the rectangle it made before
        const prev = f.profile && f.rectId && f.profile.outer === ref.outer ? featureRect(cur, f) : null;
        const shape: Shape = { kind: "rect", id: prev?.id ?? newId("r"), ...rect };
        const next = prev ? setShape(cur, shape) : addShape(cur, shape);
        set({ doc: updateFeature(next, fid, (g) => ({ ...g, rectId: shape.id, profile: ref })), sel: { kind: "feature", id: fid } });
      } catch (e) {
        set({ note: `Inscribe failed: ${(e as Error).message}` });
      } finally {
        set({ inscribing: false });
      }
    },
    setProfile: (ref) => {
      edit((f) => ({ ...f, profile: ref }));
      set({ panel: { ...get().panel, selector: null }, sel: { kind: "feature", id: get().panel.featureId! } });
    },
    setSelector: (selector) => set({ panel: { ...get().panel, selector } }),
    clearRect: () => {
      edit((f) => ({ ...f, rectId: null }));
      set({ panel: { ...get().panel, selector: "rect" } });
    },
    clearProfile: () => edit((f) => ({ ...f, profile: null })),
    setHoles: async (holes) => {
      edit((f) => ({ ...f, holes }));
      const ref = editing()?.profile;
      if (ref) await get().useProfile(ref);
    },
    setField: (path, value) => edit((f) => setField(f, path, value)),
    resetField: (path) => edit((f) => resetField(f, path)),
    setLabel: (key, value, featureId) => set({
      doc: updateFeature(get().doc, featureId ?? get().panel.featureId, (f) => ({ ...f, label: { ...f.label, [key]: value } })),
    }),
    pick: (s) => edit((f) => pickSuggestion(f, s)),
    turn: (featureId) => set({
      doc: updateFeature(get().doc, featureId ?? activeFeatureId(get()), (f) => setField(f, "marker.turn", nextTurn(f.marker.turn))),
    }),
    setTab: (tab) => set({ panel: { ...get().panel, tab } }),
    collapse: (collapsed) => set({ panel: { ...get().panel, collapsed } }),
    ok: () => {
      const { doc, panel } = get();
      const f = getFeature(doc, panel.featureId);
      // OK without a rectangle makes nothing
      set({ panel: { ...PANEL0, tab: panel.tab }, doc: f && !f.rectId ? removeFeature(doc, f.id) : doc });
    },
    cancel: () => {
      const { panel } = get();
      set({ panel: { ...PANEL0, tab: panel.tab }, doc: panel.backup ?? get().doc, sel: null });
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
      set({ doc: { ...get().doc, preset: p } });
    },
    openModal: (modal) => set({ modal }),
    say: (note) => set({ note }),
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
