// The one store (zustand). The server holds the open scene; every change
// goes through its API and the scene comes back with its plans, so what is
// drawn is always what the core planned. Changes run one at a time (a
// queue), and each keeps the scene as it was for Undo.
import { create } from "zustand";
import { api, errorText, ApiError } from "./api/client";
import type {
  Dictionary, FormDoc, PaletteEntry, PresetItem, RenumberReport, SceneDoc, SceneTag, Target,
  VerifyReport,
} from "./api/types";
import { matMul, poseOf, sceneZ, tagBox, unionBox } from "./model/geom";
import {
  docOf, moveLocal, patchFor, placeNew, pushHistory, redoStep, renameSel, rotateLocal,
  selectClick, toggleView, undoStep, type History, type View,
} from "./model/scene";

export interface Camera { cx: number; cy: number; zoom: number }   // scene mm, px per mm
export interface Show { quiet: boolean; axes: boolean; outlines: boolean; ids: boolean; grid: boolean }
export type Drawer = null | "verify" | "messages" | "export";
export interface LogLine { t: string; level: "info" | "warn" | "error"; text: string }

export interface StudioState {
  ready: boolean;
  form: FormDoc | null;
  options: Record<string, any> | null;
  dictionaries: Dictionary[];
  targets: PaletteEntry[];
  presets: PresetItem[];
  recent: string[];
  scene: SceneDoc;
  sel: string[];
  view: View;
  camera: Camera;
  viewport: { w: number; h: number };
  show: Show;
  zScale: number;
  hist: History;
  busy: number;
  status: { text: string; level: "info" | "warn" | "error" };
  log: LogLine[];
  drawer: Drawer;
  verify: Record<string, VerifyReport>;
  sceneVerify: any | null;
  renumberReport: RenumberReport | null;
  newTarget: string;
  newThickness: number;
  newPreset: string;
  libraryOpen: boolean;
  dialog: null | { kind: "save" | "open" | "new"; };

  init(): Promise<void>;
  refresh(): Promise<void>;
  say(text: string, level?: "info" | "warn" | "error"): void;
  setView(v: View): Promise<void>;
  toggleView(): Promise<void>;
  setCamera(c: Partial<Camera>): void;
  setViewport(w: number, h: number): void;
  setShow(k: keyof Show, v: boolean): void;
  setZScale(v: number): void;
  zoomToFit(names?: string[]): void;
  select(name: string | null, additive?: boolean): void;
  setSel(names: string[]): void;
  selectAll(): void;
  addTag(layout: "single" | "grid" | "charuco"): Promise<void>;
  previewMove(names: string[], dx: number, dy: number, from: Record<string, [number, number]>): void;
  commitMove(names: string[], before: SceneDoc): Promise<void>;
  nudge(dx: number, dy: number): Promise<void>;
  rotateSel(deg: number): Promise<void>;
  duplicateSel(): Promise<void>;
  deleteSel(): Promise<void>;
  edit(path: string, value: unknown, extra?: Record<string, unknown>): Promise<void>;
  editTarget(t: Target): Promise<void>;
  rename(from: string, to: string): Promise<void>;
  setFlag(name: string, flag: "locked" | "hidden", v: boolean): Promise<void>;
  applyPreset(name: string, preset?: any): Promise<void>;
  renumber(): Promise<void>;
  override(name: string, id: number | null): Promise<void>;
  undo(): Promise<void>;
  redo(): Promise<void>;
  newScene(name: string): Promise<void>;
  saveScene(name?: string): Promise<void>;
  openScene(name: string): Promise<void>;
  verifySel(): Promise<void>;
  verifyScene(): Promise<void>;
  exportScene(fmt: string): Promise<string[]>;
  exportTag(fmt: string): Promise<void>;
  loadPresets(): Promise<void>;
  setNew(k: "newTarget" | "newThickness" | "newPreset", v: string | number): void;
  setDrawer(d: Drawer): void;
  setLibrary(open: boolean): void;
  setDialog(d: StudioState["dialog"]): void;
  idle(): Promise<void>;
}

const EMPTY: SceneDoc = { schema: "arucostudio.scene/1", units: "mm", name: "untitled", tags: [], ledger: null, overrides: {}, presets_used: [] };

let queue: Promise<unknown> = Promise.resolve();

function stamp() {
  return new Date().toTimeString().slice(0, 8);
}

function download(name: string, data: Blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(data);
  a.download = name;
  a.dataset.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

function b64Blob(b64: string, type: string): Blob {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return new Blob([out], { type });
}

export const useStudio = create<StudioState>((set, get) => {
  /** One change at a time; `before` goes on the Undo stack when it works. */
  function run(label: string, fn: () => Promise<void>, opts: { history?: boolean; before?: SceneDoc } = {}) {
    const p = queue.then(async () => {
      const before = opts.before ?? get().scene;
      set((s) => ({ busy: s.busy + 1 }));
      try {
        await fn();
        if (opts.history !== false) set((s) => ({ hist: pushHistory(s.hist, before) }));
        await get().refresh();
        if (label) get().say(label);
      } catch (e) {
        const msg = e instanceof ApiError ? errorText((e.detail as any)?.detail ?? e.detail) : String(e);
        get().say(`${label ? label + ": " : ""}${msg}`, "error");
        await get().refresh().catch(() => undefined);
      } finally {
        set((s) => ({ busy: s.busy - 1 }));
      }
    });
    queue = p.catch(() => undefined);
    return p;
  }

  const tagsSel = () => get().scene.tags.filter((t) => get().sel.includes(t.name));

  return {
    ready: false,
    form: null,
    options: null,
    dictionaries: [],
    targets: [],
    presets: [],
    recent: [],
    scene: EMPTY,
    sel: [],
    view: "2d",
    camera: { cx: 0, cy: 0, zoom: 4 },
    viewport: { w: 800, h: 600 },
    show: { quiet: true, axes: true, outlines: false, ids: true, grid: true },
    zScale: 1,
    hist: { undo: [], redo: [] },
    busy: 0,
    status: { text: "", level: "info" },
    log: [],
    drawer: null,
    verify: {},
    sceneVerify: null,
    renumberReport: null,
    newTarget: "box40",
    newThickness: 3,
    newPreset: "Default",
    libraryOpen: false,
    dialog: null,

    async init() {
      const [form, options, dictionaries, targets] = await Promise.all([
        api.form(), api.options(), api.dictionaries(), api.targets(3),
      ]);
      set({ form, options, dictionaries, targets });
      await get().loadPresets();
      await get().refresh();
      set({ ready: true });
      if (get().scene.tags.length) get().zoomToFit();
    },

    async refresh() {
      const scene = await api.scene(get().view === "3d");
      const names = new Set(scene.tags.map((t) => t.name));
      set((s) => ({ scene, sel: s.sel.filter((n) => names.has(n)) }));
    },

    say(text, level = "info") {
      set((s) => ({ status: { text, level }, log: [...s.log, { t: stamp(), level, text }].slice(-200) }));
    },

    async setView(v) {
      if (v === get().view) return;
      set({ view: v });
      await run("", async () => undefined, { history: false });
    },
    async toggleView() {
      await get().setView(toggleView(get().view));
    },
    setCamera(c) {
      set((s) => ({ camera: { ...s.camera, ...c } }));
    },
    setViewport(w, h) {
      set({ viewport: { w, h } });
    },
    setShow(k, v) {
      set((s) => ({ show: { ...s.show, [k]: v } }));
    },
    setZScale(v) {
      set({ zScale: v });
    },
    zoomToFit(names) {
      const tags = get().scene.tags.filter((t) => !t.hidden && (!names || names.includes(t.name)));
      const b = unionBox(tags.map((t) => tagBox(t)));
      if (!b) return;
      const { w, h } = get().viewport;
      const zoom = Math.max(0.2, Math.min(60, Math.min((w - 80) / Math.max(1, b.x1 - b.x0), (h - 80) / Math.max(1, b.y1 - b.y0))));
      set({ camera: { cx: (b.x0 + b.x1) / 2, cy: (b.y0 + b.y1) / 2, zoom } });
    },

    select(name, additive = false) {
      set((s) => ({ sel: selectClick(s.sel, name, additive) }));
    },
    setSel(names) {
      set({ sel: names });
    },
    selectAll() {
      set((s) => ({ sel: s.scene.tags.filter((t) => !t.hidden).map((t) => t.name) }));
    },

    async addTag(layout) {
      await run(`added a ${layout === "single" ? "single marker" : layout === "grid" ? "grid board" : "ChArUco board"}`, async () => {
        const { newTarget, newThickness, newPreset } = get();
        const spec = await api.newSpec({ layout, target_key: newTarget, thickness_mm: newThickness, preset: newPreset === "Default" ? "" : newPreset });
        const [x, y] = placeNew(get().scene.tags, spec.target.w_mm);
        const t = await api.addTag(spec, x, y);
        set({ sel: [t.name] });
      });
      const t = get().scene.tags.find((x) => x.name === get().sel[0]);
      if (t) {
        const b = tagBox(t);
        const { camera, viewport } = get();
        if (b) {
          const sx0 = viewport.w / 2 + (b.x0 - camera.cx) * camera.zoom, sx1 = viewport.w / 2 + (b.x1 - camera.cx) * camera.zoom;
          const sy0 = viewport.h / 2 - (b.y1 - camera.cy) * camera.zoom, sy1 = viewport.h / 2 - (b.y0 - camera.cy) * camera.zoom;
          if (sx0 < 0 || sy0 < 0 || sx1 > viewport.w || sy1 > viewport.h) get().zoomToFit();
        }
      }
    },

    previewMove(names, dx, dy, from) {
      set((s) => ({ scene: moveLocal(s.scene, names, dx, dy, 0.5, from) }));
    },
    async commitMove(names, before) {
      const moved = get().scene.tags.filter((t) => names.includes(t.name));
      const was = Object.fromEntries(before.tags.map((t) => [t.name, t]));
      const changed = moved.filter((t) => was[t.name] && (was[t.name].x_mm !== t.x_mm || was[t.name].y_mm !== t.y_mm || was[t.name].rotation_deg !== t.rotation_deg));
      if (!changed.length) return;
      await run(`moved ${changed.length === 1 ? changed[0].name : changed.length + " tags"}`, async () => {
        for (const t of changed) await api.patchTag(t.name, { x_mm: t.x_mm, y_mm: t.y_mm, rotation_deg: t.rotation_deg });
      }, { before });
    },
    async nudge(dx, dy) {
      const names = get().sel;
      if (!names.length) return;
      const before = get().scene;
      set((s) => ({ scene: moveLocal(s.scene, names, dx, dy, 0.5) }));
      await get().commitMove(names, before);
    },
    async rotateSel(deg) {
      const names = get().sel;
      if (!names.length) return;
      const before = get().scene;
      set((s) => ({ scene: rotateLocal(s.scene, names, deg) }));
      await get().commitMove(names, before);
    },
    async duplicateSel() {
      const tags = tagsSel();
      if (!tags.length) return;
      await run(`duplicated ${tags.length === 1 ? tags[0].name : tags.length + " tags"}`, async () => {
        const out: string[] = [];
        for (const t of tags) {
          const b = tagBox(t);
          const dy = b ? -(b.y1 - b.y0) - 10 : -50;
          out.push((await api.duplicateTag(t.name, 0, dy)).name);
        }
        set({ sel: out });
      });
    },
    async deleteSel() {
      const tags = tagsSel();
      if (!tags.length) return;
      await run(`deleted ${tags.length === 1 ? tags[0].name : tags.length + " tags"}`, async () => {
        for (const t of tags) await api.deleteTag(t.name);
        set({ sel: [] });
      });
    },

    async edit(path, value, extra) {
      const tags = tagsSel();
      if (!tags.length) return;
      await run(`${path} = ${typeof value === "object" ? JSON.stringify(value) : String(value)}`, async () => {
        const refused: string[] = [];
        for (const t of tags) {
          let body = patchFor(path, value, t.spec);
          if (extra) {
            body = { ...body };
            for (const [k, v] of Object.entries(extra)) {
              const [h, r] = k.split(".");
              (body as any)[h] = { ...((body as any)[h] || {}), [r]: v };
            }
          }
          try {
            await api.patchTag(t.name, body);
          } catch (e) {
            if (e instanceof ApiError && e.status === 409) refused.push(`${t.name}: ${errorText(e.detail)}`);
            else throw e;
          }
        }
        if (refused.length) throw new Error(refused.join("; "));
      });
    },
    async editTarget(t) {
      const tags = tagsSel();
      if (!tags.length) return;
      await run(`target: ${t.name || "edited"}`, async () => {
        for (const x of tags) await api.patchTag(x.name, { target: t });
      });
    },
    async rename(from, to) {
      if (!to || to === from) return;
      await run(`renamed ${from} to ${to}`, async () => {
        await api.patchTag(from, { new_name: to });
        set((s) => ({ sel: renameSel(s.sel, from, to) }));
      });
    },
    async setFlag(name, flag, v) {
      await run(`${name}: ${flag === "locked" ? (v ? "locked (printed)" : "unlocked") : (v ? "hidden" : "shown")}`, async () => {
        await api.patchTag(name, { [flag]: v });
      });
    },
    async applyPreset(name, preset) {
      const tags = tagsSel();
      await run(`preset '${name}'`, async () => {
        for (const t of tags) {
          const sp = await api.presetApply(t.spec as any, name, preset);
          await api.patchTag(t.name, { settings: sp.settings, numbers: sp.numbers });
        }
        set({ newPreset: name });
        try { set({ recent: (await api.addRecent(name)).recent }); } catch { /* the list is a convenience */ }
      });
    },
    async renumber() {
      await run("", async () => {
        const rep = await api.renumber();
        set({ renumberReport: rep });
        const n = rep.changed.length;
        get().say(n ? `Renumber: ${n} tag${n === 1 ? "" : "s"} changed (${rep.changed.map((c) => `${c.tag} ${c.from}→${c.to}`).join(", ")})` : "Renumber: every id already unique, nothing changed",
          rep.ok ? "info" : "warn");
      });
    },
    async override(name, id) {
      await run(id === null ? `${name}: id back to auto` : `${name}: first id typed ${id}`, async () => {
        await api.override(name, id);
      });
    },

    async undo() {
      await queue;
      const step = undoStep(get().hist, get().scene);
      if (!step) return get().say("nothing to undo", "warn");
      await run("undone", async () => {
        await api.scenePut(step[0]);
        set({ hist: step[1] });
      }, { history: false });
    },
    async redo() {
      await queue;
      const step = redoStep(get().hist, get().scene);
      if (!step) return get().say("nothing to redo", "warn");
      await run("redone", async () => {
        await api.scenePut(step[0]);
        set({ hist: step[1] });
      }, { history: false });
    },

    async newScene(name) {
      await run(`new scene '${name}'`, async () => {
        await api.sceneNew(name);
        set({ sel: [], hist: { undo: [], redo: [] }, verify: {}, sceneVerify: null, renumberReport: null });
      }, { history: false });
    },
    async saveScene(name) {
      await run("", async () => {
        const r = await api.save(name || get().scene.name);
        get().say(`saved ${r.saved}`);
      }, { history: false });
    },
    async openScene(name) {
      await run(`opened '${name}'`, async () => {
        await api.open(name);
        set({ sel: [], hist: { undo: [], redo: [] }, verify: {}, sceneVerify: null, renumberReport: null });
      }, { history: false });
      get().zoomToFit();
    },

    async verifySel() {
      const tags = tagsSel().length ? tagsSel() : get().scene.tags.filter((t) => !t.hidden);
      set({ drawer: "verify" });
      await run("", async () => {
        const out: Record<string, VerifyReport> = { ...get().verify };
        for (const t of tags) out[t.name] = await api.verify(t.spec as any);
        set({ verify: out });
        const bad = tags.filter((t) => !out[t.name].ok);
        get().say(bad.length ? `Verify: ${bad.length} of ${tags.length} not read as planned (${bad.map((t) => t.name).join(", ")})`
          : `Verify: OpenCV read all ${tags.length} tag${tags.length === 1 ? "" : "s"} as planned`, bad.length ? "warn" : "info");
      }, { history: false });
    },
    async verifyScene() {
      set({ drawer: "verify" });
      await run("", async () => {
        const rep = await api.sceneVerify();
        set({ sceneVerify: rep });
        get().say(rep.ok ? "Verify sheet: every marker found where the scene puts it" : "Verify sheet: not every marker was found", rep.ok ? "info" : "warn");
      }, { history: false });
    },
    async exportScene(fmt) {
      let files: string[] = [];
      await run("", async () => {
        const r = await api.sceneExport(fmt);
        files = r.files;
        const types: Record<string, string> = { svg: "image/svg+xml", png: "image/png", json: "application/json", stl: "model/stl" };
        for (const [fn, b64] of Object.entries(r.inline || {})) {
          const ext = fn.split(".").pop() || "";
          download(fn, b64Blob(b64, types[ext] || "application/octet-stream"));
        }
        get().say(`exported ${r.files.length} file${r.files.length === 1 ? "" : "s"} to ${r.dir}`);
      }, { history: false });
      return files;
    },
    async exportTag(fmt) {
      const t = tagsSel()[0];
      if (!t) return get().say("select a tag to export it alone", "warn");
      await run("", async () => {
        const blob = await api.exportTag(fmt, t.spec as any);
        download(`${t.name}.${fmt}`, blob);
        get().say(`exported ${t.name}.${fmt}`);
      }, { history: false });
    },
    async loadPresets() {
      const [p, r] = await Promise.all([api.presets(), api.recent()]);
      set({ presets: p.items, recent: r.recent });
    },
    setNew(k, v) {
      set({ [k]: v } as any);
    },
    setDrawer(d) {
      set({ drawer: d });
    },
    setLibrary(open) {
      set({ libraryOpen: open });
    },
    setDialog(d) {
      set({ dialog: d });
    },
    async idle() {
      for (let i = 0; i < 50; i++) {
        await queue;
        if (!get().busy) return;
        await new Promise((r) => setTimeout(r, 20));
      }
    },
  };
});

/** A tag's frame in the scene: its pose times its plan's pattern frame. */
export function patternToScene(t: SceneTag): number[] | null {
  const pit = t.plan?.frames?.pattern_in_target;
  if (!pit) return null;
  return matMul(poseOf(t.x_mm, t.y_mm, t.rotation_deg), pit);
}

/** What the tests read (ARCHITECTURE 4: the store exposes zRange and the
 *  camera centre). */
export function studioProbe() {
  const s = useStudio.getState();
  return {
    center: [s.camera.cx * s.camera.zoom, s.camera.cy * s.camera.zoom],
    center_mm: [s.camera.cx, s.camera.cy],
    zoom: s.camera.zoom,
    zRange: sceneZ(s.scene.tags),
    view: s.view,
    sel: [...s.sel],
    tags: s.scene.tags.map((t) => ({ name: t.name, x_mm: t.x_mm, y_mm: t.y_mm, rotation_deg: t.rotation_deg, ids: t.plan?.ids ?? [], locked: t.locked })),
    doc: docOf(s.scene),
  };
}
