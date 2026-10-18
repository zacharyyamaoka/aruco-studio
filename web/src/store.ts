// The app's state (zustand): the document, the tool, the selection, the
// camera, the panel, the modals, and what the core last answered. The
// document's edits are the pure functions of model/doc.ts and sketch/model.ts.
import { create } from "zustand";
import type { CoreInfo, LabelParams, MarkerParams, MarkerPlan, Preset, Suggestion } from "./core/contract";
import { core } from "./coreSource";
import {
  addShape, deleteShape, emptyDoc, featureRect, newFeature, newId, nextTurn, pickSuggestion, setMarker, setShape,
  type Doc, type Holes,
} from "./model/doc";
import { fitBox, type Camera } from "./model/geom";
import { touchRecent } from "./presets/local";
import { example } from "./sketch/examples";
import { plainRect, profileLoops, sketchBox, type ProfileRef, type Selection, type Shape } from "./sketch/model";

export type Tool = "select" | "rect" | "circle";
export type Modal = null | "presets" | "print" | "examples";
export type Tab = "marker" | "label";

export interface PanelState {
  open: boolean;
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
  plan: MarkerPlan | null;
  planError: string | null;
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

  extrude: () => Promise<void>;
  useRect: (id: string) => void;
  useProfile: (ref: ProfileRef) => Promise<void>;
  setSelector: (s: PanelState["selector"]) => void;
  clearRect: () => void;
  clearProfile: () => void;
  setHoles: (h: Holes) => Promise<void>;
  setMarker: <K extends keyof MarkerParams>(key: K, value: MarkerParams[K]) => void;
  setLabel: <K extends keyof LabelParams>(key: K, value: LabelParams[K]) => void;
  pick: (s: Suggestion) => void;
  turn: () => void;
  setTab: (t: Tab) => void;
  collapse: (c: boolean) => void;
  ok: () => void;
  cancel: () => void;
  editFeature: () => void;

  setPreset: (p: Preset) => void;
  openModal: (m: Modal) => void;
  say: (note: string | null) => void;
}

const PANEL0: PanelState = { open: false, tab: "marker", collapsed: false, selector: null, backup: null };

function withFeature(doc: Doc, f: (feature: NonNullable<Doc["feature"]>) => NonNullable<Doc["feature"]>): Doc {
  return doc.feature ? { ...doc, feature: f(doc.feature) } : doc;
}

export const useStudio = create<Studio>((set, get) => ({
  doc: emptyDoc("Plate", example("plate")!.shapes),
  tool: "select",
  sel: null,
  camera: { cx: 60, cy: 40, zoom: 4 },
  view: { w: 800, h: 600 },
  panel: PANEL0,
  modal: null,
  plan: null,
  planError: null,
  suggestions: [],
  info: null,
  builtins: [],
  inscribing: false,
  note: null,

  setDoc: (doc) => set({ doc }),
  loadDoc: (doc) => {
    const preset = doc.preset ?? get().doc.preset;
    set({ doc: { ...doc, preset }, sel: null, panel: PANEL0, plan: null, suggestions: [], tool: "select" });
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
    const { sel, doc } = get();
    if (sel?.kind === "shape") set({ doc: deleteShape(doc, sel.id), sel: null });
    else if (sel?.kind === "feature" || sel?.kind === "origin") set({ doc: { ...doc, feature: null }, sel: null, panel: PANEL0, plan: null });
  },
  setCamera: (camera) => set({ camera }),
  setView: (w, h) => set({ view: { w, h } }),
  fit: () => {
    const { doc, view, plan } = get();
    let b = sketchBox(doc.shapes);
    if (plan) for (const [x, y] of plan.outer) b = b ? { x0: Math.min(b.x0, x), y0: Math.min(b.y0, y), x1: Math.max(b.x1, x), y1: Math.max(b.y1, y) } : { x0: x, y0: y, x1: x, y1: y };
    set({ camera: fitBox(b ?? { x0: -50, y0: -50, x1: 50, y1: 50 }, view.w, view.h, view.w < 640 ? 28 : 84) });
  },

  // ---------------------------------------------------------------- ArUco Extrude
  extrude: async () => {
    const { panel, sel, doc } = get();
    if (panel.open) return;
    const backup = doc;
    const feature = doc.feature ?? newFeature(null, null);
    set({ doc: { ...doc, feature }, panel: { ...PANEL0, open: true, backup, tab: get().panel.tab }, tool: "select" });
    if (sel?.kind === "shape" && doc.shapes.find((s) => s.id === sel.id)?.kind === "rect") get().useRect(sel.id);
    else if (sel?.kind === "profile") await get().useProfile(sel.ref);
    else if (!feature.rectId) set({ panel: { ...get().panel, selector: "rect" } });
  },
  useRect: (id) => {
    set({ doc: withFeature(get().doc, (f) => ({ ...f, rectId: id })), sel: { kind: "shape", id }, panel: { ...get().panel, selector: null } });
  },
  useProfile: async (ref) => {
    const { doc } = get();
    const plain = plainRect(doc.shapes, ref);
    if (plain) {
      set({ doc: withFeature(doc, (f) => ({ ...f, rectId: plain.id, profile: null })), sel: { kind: "shape", id: plain.id }, panel: { ...get().panel, selector: null } });
      return;
    }
    const loops = profileLoops(doc.shapes, ref);
    if (!loops || !doc.feature) return;
    set({ inscribing: true, panel: { ...get().panel, selector: null }, sel: { kind: "profile", ref } });
    try {
      const rect = await core.inscribe(loops, doc.feature.holes);
      if (!rect) { set({ note: "Nothing fits in that profile." }); return; }
      const cur = get().doc;
      // re-inscribing the same profile moves the rectangle it made before
      const prev = cur.feature?.profile && cur.feature.rectId && cur.feature.profile.outer === ref.outer ? featureRect(cur) : null;
      const shape: Shape = { kind: "rect", id: prev?.id ?? newId("r"), ...rect };
      const next = prev ? setShape(cur, shape) : addShape(cur, shape);
      set({ doc: withFeature(next, (f) => ({ ...f, rectId: shape.id, profile: ref })), sel: { kind: "shape", id: shape.id } });
    } catch (e) {
      set({ note: `Inscribe failed: ${(e as Error).message}` });
    } finally {
      set({ inscribing: false });
    }
  },
  setSelector: (selector) => set({ panel: { ...get().panel, selector } }),
  clearRect: () => set({ doc: withFeature(get().doc, (f) => ({ ...f, rectId: null })), panel: { ...get().panel, selector: "rect" }, plan: null }),
  clearProfile: () => set({ doc: withFeature(get().doc, (f) => ({ ...f, profile: null })) }),
  setHoles: async (holes) => {
    set({ doc: withFeature(get().doc, (f) => ({ ...f, holes })) });
    const ref = get().doc.feature?.profile;
    if (ref) await get().useProfile(ref);
  },
  setMarker: (key, value) => set({ doc: withFeature(get().doc, (f) => ({ ...f, marker: setMarker(f.marker, key, value) })) }),
  setLabel: (key, value) => set({ doc: withFeature(get().doc, (f) => ({ ...f, label: { ...f.label, [key]: value } })) }),
  pick: (s) => set({ doc: withFeature(get().doc, (f) => ({ ...f, marker: pickSuggestion(f.marker, s) })) }),
  turn: () => set({ doc: withFeature(get().doc, (f) => ({ ...f, marker: { ...f.marker, turn: nextTurn(f.marker.turn) } })) }),
  setTab: (tab) => set({ panel: { ...get().panel, tab } }),
  collapse: (collapsed) => set({ panel: { ...get().panel, collapsed } }),
  ok: () => {
    const { doc } = get();
    // OK without a rectangle makes nothing
    set({ panel: { ...get().panel, open: false, backup: null, selector: null }, doc: doc.feature && !doc.feature.rectId ? { ...doc, feature: null } : doc });
  },
  cancel: () => {
    const { panel } = get();
    set({ panel: { ...panel, open: false, backup: null, selector: null }, doc: panel.backup ?? get().doc, sel: null });
  },
  editFeature: () => {
    const { doc, panel } = get();
    if (!doc.feature || panel.open) return;
    set({ panel: { ...panel, open: true, backup: doc, selector: null }, sel: { kind: "feature" } });
  },

  setPreset: (p) => {
    touchRecent(p.id);
    set({ doc: { ...get().doc, preset: p } });
  },
  openModal: (modal) => set({ modal }),
  say: (note) => set({ note }),
}));

/** Load what the core knows once it answers: the dictionaries and the
 *  built-in presets (the first is the document's preset until one is picked). */
export async function loadCoreFacts(): Promise<void> {
  const [info, builtins] = await Promise.all([core.info(), core.presets()]);
  const s = useStudio.getState();
  useStudio.setState({ info, builtins });
  if (!s.doc.preset && builtins.length) useStudio.setState({ doc: { ...useStudio.getState().doc, preset: builtins[0] } });
}
