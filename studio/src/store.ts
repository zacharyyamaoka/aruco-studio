// The one store (zustand). FILE FIRST (M8 §1.6): the open design file is
// the model. The server holds it, compiles and plans it; every Studio
// action writes it (the shapes as a new text, PUT /api/design; a tag's
// settings through the old routes, which write it too) and the scene comes
// back with its plans, so what is drawn is always what the core planned.
// There is no dirty state and no Save: Undo and Redo are a history of
// TEXTS. The server's events (GET /api/events) bring outside changes in.
// Changes run one at a time (a queue).
import { create } from "zustand";
import { api, errorText, ApiError, type GalleryDoc, type GalleryItem, type SheetQuery } from "./api/client";
import { connectEvents, type Events } from "./api/events";
import type {
  DesignInfo, Dictionary, FormDoc, PaletteEntry, PresetCollection, PresetItem, PrusaPrinters, RenumberReport, SceneDoc, SceneTag,
  SendAnswer, SendBody, StaleInfo, VerifyReport, Pt,
} from "./api/types";
import { DRAW } from "./app/flags";
import { landing, type Page } from "./gallery/model";
import { printPdf, type PrintOutcome } from "./app/Print";
import { matMul, poseOf, sceneZ, tagBox, unionBox } from "./model/geom";
import { dump, parse, type Span } from "./model/json";
import {
  addAruco, addHole, addShape, allIds, deleteShapes, deleteTag, duplicateShapes, extrude, findShape, moveShapes, nextFreeId,
  refOfShape, rotateShapes, shapesOf, type Doc,
} from "./model/design";
import { centroid, outline, applyXf, invert } from "./model/shapes";
import { docOf, idsText, patchFor, placeNew, renameSel, selectClick, specKey, toggleView, type View } from "./model/scene";
import { typedNumbers } from "./sketch/handles";

export interface Camera { cx: number; cy: number; zoom: number }   // scene mm, px per mm
export interface Show { quiet: boolean; axes: boolean; outlines: boolean; ids: boolean; grid: boolean }
export type Drawer = null | "verify" | "messages" | "file";
export interface LogLine { t: string; level: "info" | "warn" | "error"; text: string }
export type ToolId = "select" | "rect" | "circle" | "polygon" | "slot" | "hole" | "rhole" | "extrude" | "aruco";
/** the canvas's filter (M6b): every tag, the 3D printed ones, the stickers */
export type KindFilter = "all" | "3d" | "2d";
export type DialogState = null
  | { kind: "save" | "open" | "new" }
  | { kind: "sheet" }
  | { kind: "send" }
  | { kind: "print"; url: string; why: string };

/** How a tag is made: its plan's word, else its settings' (absent = 3D printed). */
export function madeBy(t: SceneTag): "print3d" | "sticker" {
  const p = (t.plan as any)?.made_by;
  if (p === "sticker" || p === "print3d") return p;
  return (t.spec.settings as any)?.make?.by === "sticker" ? "sticker" : "print3d";
}

/** The tags the filter lets through. */
export function filtered(tags: SceneTag[], f: KindFilter): SceneTag[] {
  if (f === "all") return tags;
  return tags.filter((t) => (madeBy(t) === "sticker") === (f === "2d"));
}
/** tools that take typed numbers */
export const TYPED_TOOLS: ToolId[] = ["rect", "circle", "slot", "hole", "rhole", "extrude"];

export type { Page } from "./gallery/model";

export interface StudioState {
  ready: boolean;
  page: Page;
  /** GET /api/gallery (null until read; an empty doc when the server has none) */
  gallery: GalleryDoc | null;
  /** the gallery example open now (its copy): the note's words and buttons */
  example: GalleryItem | null;
  form: FormDoc | null;
  options: Record<string, any> | null;
  dictionaries: Dictionary[];
  targets: PaletteEntry[];
  presets: PresetItem[];
  presetCollections: PresetCollection[];
  recent: string[];
  /** tags whose PrusaSlicer profile changed (GET /api/prusa/stale) */
  stale: StaleInfo[];
  printers: PrusaPrinters | null;
  filter: KindFilter;
  /** the sheet dialog's choices (from the file's `sheet`, then as set) */
  sheet: Required<Pick<SheetQuery, "page" | "landscape" | "mode" | "margin_mm">>;
  lastSend: SendAnswer | null;
  /** the open design file (GET /api/design) */
  design: DesignInfo;
  /** its text parsed (the last text that parsed) */
  doc: Doc | null;
  spans: Map<string, Span>;
  scene: SceneDoc;
  /** bumped whenever the scene drawn changes (the canvas's data-revision) */
  sceneRev: number;
  sel: string[];
  /** selected shapes and holes (model/design keys) */
  shapeSel: string[];
  view: View;
  camera: Camera;
  viewport: { w: number; h: number };
  show: Show;
  zScale: number;
  /** the text history: what the file held before each action */
  hist: { undo: string[]; redo: string[] };
  busy: number;
  status: { text: string; level: "info" | "warn" | "error" };
  log: LogLine[];
  drawer: Drawer;
  verify: Record<string, VerifyReport>;
  verifySpec: Record<string, string>;
  verifyProgress: { done: number; total: number } | null;
  sceneVerify: any | null;
  idErrors: Record<string, string>;
  renumberReport: RenumberReport | null;
  newPreset: string;
  libraryOpen: boolean;
  dialog: DialogState;
  palette: boolean;
  tool: ToolId;
  typed: string;
  /** ArUco Extrude's picks: shape ids and "<body>.<face>" refs */
  picks: string[];
  /** a polygon being drawn (canvas mm) */
  draft: Pt[];
  /** a drag's preview is on screen */
  previewing: boolean;
  /** the last pointer-up to the scene redrawn (ms; M8b1.3) */
  lastLive: number | null;
  /** bumped by Zoom to fit: the 3D view moves its camera to the 2D camera */
  fitRev: number;

  init(): Promise<void>;
  loadGallery(): Promise<GalleryDoc | null>;
  showGallery(): void;
  showStudio(): void;
  openGallery(name: string): Promise<void>;
  refresh(): Promise<void>;
  say(text: string, level?: "info" | "warn" | "error"): void;
  setView(v: View): Promise<void>;
  toggleView(): Promise<void>;
  setCamera(c: Partial<Camera>): void;
  setViewport(w: number, h: number): void;
  setShow(k: keyof Show, v: boolean): void;
  setZScale(v: number): void;
  zoomToFit(names?: string[], insetRight?: number, fill?: number): void;
  select(name: string | null, additive?: boolean): void;
  setSel(names: string[]): void;
  selectShape(key: string | null, additive?: boolean): void;
  setShapeSel(keys: string[]): void;
  selectAll(): void;
  setTool(t: ToolId): void;
  typeKey(k: string): void;
  setTyped(t: string): void;
  confirm(): Promise<void>;
  cancel(): void;
  togglePick(ref: string, additive: boolean): void;
  setDraft(pts: Pt[]): void;
  editDoc(label: string, fn: (d: Doc) => unknown, opts?: { select?: (out: any) => void }): Promise<boolean>;
  writeText(label: string, text: string): Promise<boolean>;
  preview(text: string): void;
  commitLive(text: string, label: string, t0?: number): Promise<void>;
  createShape(shape: any, at: Pt, rot?: number): Promise<void>;
  holeAt(p: Pt, rect: boolean): Promise<void>;
  arucoOn(refs: string[], extra?: Record<string, unknown>, base?: string): Promise<void>;
  addTag(layout: "single" | "grid" | "charuco"): Promise<void>;
  moveSel(dx: number, dy: number, keys?: string[]): Promise<void>;
  nudge(dx: number, dy: number): Promise<void>;
  rotateSel(deg: number): Promise<void>;
  arrange(): Promise<void>;
  duplicateSel(): Promise<void>;
  deleteSel(): Promise<void>;
  edit(path: string, value: unknown, extra?: Record<string, unknown>): Promise<void>;
  moveLabel(name: string, x_mm: number, y_mm: number): Promise<void>;
  setMode(mode: string): Promise<void>;
  rename(from: string, to: string): Promise<void>;
  setFlag(name: string, flag: "locked" | "hidden", v: boolean): Promise<void>;
  applyPreset(name: string, preset?: any): Promise<void>;
  renumber(): Promise<void>;
  override(name: string, id: number | null): Promise<void>;
  undo(): Promise<void>;
  redo(): Promise<void>;
  newScene(name: string): Promise<void>;
  saveAs(nameOrPath: string): Promise<void>;
  openScene(name: string): Promise<void>;
  openPath(path: string): Promise<void>;
  openExample(name: string): Promise<void>;
  reveal(): Promise<void>;
  verifySel(): Promise<void>;
  verifyScene(): Promise<void>;
  exportScene(fmt: string): Promise<string[]>;
  exportTag(fmt: string): Promise<void>;
  loadPresets(): Promise<void>;
  setNew(k: "newPreset", v: string): void;
  setDrawer(d: Drawer): void;
  setLibrary(open: boolean): void;
  setDialog(d: StudioState["dialog"]): void;
  setPalette(open: boolean): void;
  setFilter(f: KindFilter): void;
  setSheet(q: Partial<StudioState["sheet"]>): void;
  loadStale(): Promise<void>;
  loadPrinters(): Promise<PrusaPrinters | null>;
  printSheet(q?: SheetQuery): Promise<PrintOutcome>;
  exportSheet(q?: SheetQuery): Promise<{ dir: string; files: string[] } | null>;
  sendPrusa(b: SendBody): Promise<SendAnswer | null>;
  idle(): Promise<void>;
}

/** A verify report made from another spec than the tag has now (audit F4). */
export function isStale(s: Pick<StudioState, "scene" | "verifySpec">, name: string): boolean {
  const t = s.scene.tags.find((x) => x.name === name);
  return !t || s.verifySpec[name] !== specKey(t.spec);
}

/** Can the Studio write the file now? (a broken or missing file: no) */
export function writeBlock(d: DesignInfo): string | null {
  if (d.state === "broken") {
    const e = d.error || ({} as any);
    return `the file does not parse${e.line ? ` (line ${e.line} col ${e.col}: ${e.message})` : ""}: fix it first; nothing was written`;
  }
  if (d.state === "missing") return "the file is gone: Save as… writes it again; nothing was written";
  return null;
}

const EMPTY: SceneDoc = { schema: "arucostudio.scene/1", units: "mm", name: "untitled", tags: [], ledger: null, overrides: {}, presets_used: [] };
const NO_DESIGN: DesignInfo = { path: null, state: "memory", text: "", hash: null, revision: 0, error: null, issues: [], schema: "arucostudio.scene/2" };

let queue: Promise<unknown> = Promise.resolve();
let events: Events | null = null;
let previewSeq = 0;
let previewBusy = false;
let previewNext: string | null = null;
const previews = new Map<string, SceneDoc>();
const inflight = new Map<string, Promise<SceneDoc | null>>();
let liveBusy = 0;
const HIST = 200;
/** the example's note over the canvas's right side (px, with its margin) */
const NOTE_W = 350;
/** a fit to do when the canvas first measures itself (it mounts with the page) */
let fitPending = false;

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

function parsed(text: string): { doc: Doc | null; spans: Map<string, Span> } {
  try {
    const p = parse(text);
    return { doc: p.value && typeof p.value === "object" ? p.value : null, spans: p.spans };
  } catch {
    return { doc: null, spans: new Map() };
  }
}

/** The page in the URL's hash (#gallery, #studio, #example=<name>), so a
 *  reload comes back where it was. */
function setHash(h: string) {
  try {
    if (window.location.hash !== h) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${h}`);
  } catch { /* a page without history (tests' about:blank) */ }
}

const msgOf = (e: unknown) => e instanceof ApiError ? errorText((e.detail as any)?.detail ?? e.detail)
  : e instanceof Error ? e.message : String(e);

export const useStudio = create<StudioState>((set, get) => {
  /** One change at a time. A change that writes (history) is refused while
   *  the file does not parse; its text before goes on the Undo stack. */
  function run(label: string, fn: () => Promise<void>, opts: { history?: boolean } = {}) {
    const p = queue.then(async () => {
      const writes = opts.history !== false;
      const block = writes ? writeBlock(get().design) : null;
      if (block) {
        get().say(`${label ? label + ": " : ""}${block}`, "error");
        return;
      }
      const before = get().design.text;
      set((s) => ({ busy: s.busy + 1 }));
      try {
        await fn();
        await get().refresh();
        if (writes && get().design.text !== before) {
          set((s) => ({ hist: { undo: [...s.hist.undo, before].slice(-HIST), redo: [] } }));
        }
        if (label) get().say(label);
      } catch (e) {
        get().say(`${label ? label + ": " : ""}${msgOf(e)}`, "error");      // never "Error: ..." (audit F6)
        await get().refresh().catch(() => undefined);
      } finally {
        set((s) => ({ busy: s.busy - 1 }));
      }
    });
    queue = p.catch(() => undefined);
    return p;
  }

  const tagsSel = () => get().scene.tags.filter((t) => get().sel.includes(t.name));

  function setScene(scene: SceneDoc) {
    const names = new Set(scene.tags.map((t) => t.name));
    set((s) => ({ scene, sceneRev: s.sceneRev + 1, sel: s.sel.filter((n) => names.has(n)) }));
  }

  function setDesign(d: DesignInfo) {
    const was = get().design;
    if (d.text !== was.text || !get().doc) {
      const p = parsed(d.text);
      const keys = new Set(shapesOf(p.doc).map((x) => x.key));
      set((s) => ({ design: d, doc: p.doc, spans: p.spans, shapeSel: s.shapeSel.filter((k) => keys.has(k)) }));
    } else set({ design: d });
  }

  /** The shapes a selected tag stands on (their keys). */
  function shapesOfTags(names: string[]): string[] {
    const out: string[] = [];
    for (const t of get().scene.tags) {
      if (!names.includes(t.name)) continue;
      const k = t.source?.shape;
      if (k && !out.includes(k)) out.push(k);
    }
    return out;
  }

  /** The next free first id of a dictionary's family (audit F5). */
  function familyIds(dict: string, except: string[]): number[] {
    const fam = (d: string) => get().dictionaries.find((x) => x.name === d)?.family ?? d;
    const f = fam(dict);
    const out: number[] = [];
    for (const t of get().scene.tags) {
      if (except.includes(t.name) || !t.plan?.ok) continue;
      if (fam(String((t.plan.marker as any)?.dictionary ?? "")) === f) out.push(...t.plan.ids);
    }
    return out;
  }

  /** New tags (names) whose ids clash with another tag's get the next free ids. */
  async function numberNew(names: string[]) {
    for (const name of names) {
      const t = get().scene.tags.find((x) => x.name === name);
      if (!t?.plan?.ok) continue;
      const used = familyIds(String((t.plan.marker as any)?.dictionary ?? ""), names);
      if (!t.plan.ids.some((i) => used.includes(i))) continue;
      await api.patchTag(name, { numbers: { marker_id: nextFreeId(used) } });
      await get().refresh();
    }
  }

  /** A new face list: each face its own run of ids, the next free ones in
   *  the order of the list (marker_ids in the file, so it stays one feature;
   *  Renumber is a repair, not a required step). */
  async function numberList(fid: string, names: string[]) {
    const tags = names.map((n) => get().scene.tags.find((x) => x.name === n));
    if (tags.some((t) => !t?.plan?.ok || !t.plan.ids.length)) return;
    const dict = String((tags[0]!.plan!.marker as any)?.dictionary ?? "");
    const used = familyIds(dict, names);
    let next = nextFreeId(used);
    const ids: number[] = [];
    for (const t of tags) {
      const span = Math.max(...t!.plan!.ids) - Math.min(...t!.plan!.ids) + 1;
      ids.push(next);
      next += span;
    }
    const d = parse(get().design.text).value as Doc;
    const f = (d.features || []).find((x: any) => x?.id === fid);
    if (!f || !Array.isArray(f.aruco) || f.aruco.length !== ids.length) return;
    f.marker_ids = ids;
    await api.designPut(dump(d), get().design.hash);
    await get().refresh();
  }

  function keepInView(names: string[]) {
    const tags = get().scene.tags.filter((x) => names.includes(x.name));
    const b = unionBox(tags.map((t) => tagBox(t)));
    if (!b) return;
    const { camera, viewport } = get();
    const sx0 = viewport.w / 2 + (b.x0 - camera.cx) * camera.zoom, sx1 = viewport.w / 2 + (b.x1 - camera.cx) * camera.zoom;
    const sy0 = viewport.h / 2 - (b.y1 - camera.cy) * camera.zoom, sy1 = viewport.h / 2 - (b.y0 - camera.cy) * camera.zoom;
    if (get().scene.tags.length === tags.length || sx0 < 0 || sy0 < 0 || sx1 > viewport.w || sy1 > viewport.h) get().zoomToFit();
  }

  /** Where a typed shape goes: the view's centre, on the 0.5 mm grid, or the
   *  origin on an empty canvas. */
  function typedAt(): Pt {
    if (!shapesOf(get().doc).length && !get().scene.tags.length) return [0, 0];
    const c = get().camera;
    return [Math.round(c.cx * 2) / 2, Math.round(c.cy * 2) / 2];
  }

  /** The compiled, planned scene of a text (POST /api/design/preview):
   *  cached by text; one request per text at a time. `mesh`: the solids
   *  too (the 3D view's release); a drag asks only the top views (the
   *  light preview, lane speed: the meshes cost 3-4x the rest). */
  function fetchPreview(t: string, mesh: boolean): Promise<SceneDoc | null> {
    const key = (mesh ? "3d|" : "2d|") + t;
    const hit = previews.get(key);
    if (hit) return Promise.resolve(hit);
    let p = inflight.get(key);
    if (!p) {
      p = api.designPreview(t, mesh).then((r) => {
        if (r.scene) {
          previews.set(key, r.scene);
          if (previews.size > 8) previews.delete(previews.keys().next().value as string);
        }
        return r.scene;
      }).catch(() => null).finally(() => inflight.delete(key));
      inflight.set(key, p);
    }
    return p;
  }

  /** An ArUco Extrude on refs, named <base><n> (the old Add's names for
   *  grid / ChArUco): -> its id. */
  function arucoNamed(d: Doc, refs: string[], extra: Record<string, unknown>, base: string): string {
    const taken = allIds(d);                 // before the new one (a split list's <id> included)
    let fid = addAruco(d, refs, extra);
    if (base !== "tag") {
      const f = d.features![d.features!.length - 1];
      for (let n = 1; ; n++) if (!taken.has(`${base}${n}`)) { f.id = `${base}${n}`; break; }
      fid = f.id;
    }
    return fid;
  }

  /** One action that adds an ArUco Extrude: written, numbered (a new tag
   *  takes the next free ids), selected, the inspector on it. */
  function writeAruco(label: string, build: (d: Doc) => string) {
    return run(label, async () => {
      const block = writeBlock(get().design);
      if (block) throw new Error(block);
      const d = parse(get().design.text || dump({ schema: "arucostudio.scene/2", name: get().scene.name, sketches: [], features: [] })).value as Doc;
      const fid = build(d);
      await api.designPut(dump(d), get().design.hash);
      await get().refresh();
      // the new feature's own tags, by its index (never by a name prefix:
      // a split list's features are named <id>.<face>)
      const fi = (d.features || []).findIndex((f: any) => f?.id === fid);
      const names = get().scene.tags.filter((t) => t.source ? t.source.feature === fi : t.name === fid).map((t) => t.name);
      if (names.length === 1) await numberNew(names);
      else if (names.length > 1) await numberList(fid, names);
      set({ sel: names, shapeSel: [], tool: "select", picks: [], typed: "" });
    });
  }

  /** A file opened by hand: it is no gallery example, the Studio shows it. */
  function leftGallery() {
    set({ example: null, page: "studio" });
    setHash("#studio");
  }

  return {
    ready: false,
    page: DRAW ? "studio" : "gallery",
    gallery: null,
    example: null,
    form: null,
    options: null,
    dictionaries: [],
    targets: [],
    presets: [],
    presetCollections: [],
    recent: [],
    stale: [],
    printers: null,
    filter: "all",
    sheet: { page: "letter", landscape: false, mode: "spaced", margin_mm: 10 },
    lastSend: null,
    design: NO_DESIGN,
    doc: null,
    spans: new Map(),
    scene: EMPTY,
    sceneRev: 0,
    sel: [],
    shapeSel: [],
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
    verifySpec: {},
    verifyProgress: null,
    sceneVerify: null,
    idErrors: {},
    renumberReport: null,
    newPreset: "Default",
    libraryOpen: false,
    dialog: null,
    palette: false,
    tool: "select",
    typed: "",
    picks: [],
    draft: [],
    previewing: false,
    lastLive: null,
    fitRev: 0,

    async init() {
      const [form, options, dictionaries, targets] = await Promise.all([
        api.form(), api.options(), api.dictionaries(), api.targets(3),
      ]);
      set({ form, options, dictionaries, targets });
      await get().loadPresets();
      await get().refresh();
      const g = await get().loadGallery();
      const land = landing(window.location.hash, get().design.path, g?.dir ?? null, DRAW);
      const item = land.example ? (g?.groups ?? []).flatMap((x) => x.items).find((x) => x.name === land.example) ?? null : null;
      // an example's note only over its own copy (a reload after Open… is the file)
      const mine = !!item && !!get().design.path && landing("", get().design.path, g?.dir ?? null, false).page === "gallery";
      set({ page: land.page, example: mine ? item : null });
      if (land.page === "studio" && land.example && !mine) setHash("#studio");
      set({ ready: true });
      if (get().scene.tags.length || shapesOf(get().doc).length) get().zoomToFit();
      events?.close();
      void get().loadStale();
      events = connectEvents((kind, data) => {
        if (kind === "prusa") {
          void get().loadStale();
          if (get().printers) void get().loadPrinters();
          return;
        }
        if (kind === "scene" || kind === "file" || kind === "hello") {
          // an outside change: the text before it goes on the Undo stack too
          queue = queue.then(async () => {
            const before = get().design.text;
            await get().refresh().catch(() => undefined);
            const d = get().design;
            if (kind === "file" && d.state === "broken") {
              const e = d.error || ({} as any);
              get().say(`the file does not parse: line ${e.line} col ${e.col}: ${e.message} (the last good scene stays; writes wait)`, "error");
            } else if (kind === "file" && d.state === "missing") {
              get().say("the file is gone: writes stop; Save as… writes it again", "error");
            } else if (kind === "file" && d.state === "ok") {
              get().say("the file parses again");
            } else if (kind === "scene") {
              get().say(`the file changed on disk: redrawn (revision ${data?.revision ?? "?"})`);
            }
            if (d.text !== before && before && kind !== "hello") {
              set((s) => ({ hist: { undo: [...s.hist.undo, before].slice(-HIST), redo: [] } }));
            }
          }).catch(() => undefined);
        }
      });
    },

    async loadGallery() {
      try {
        const g = await api.gallery();
        set({ gallery: g });
        return g;
      } catch {
        const g: GalleryDoc = { schema: "arucostudio.gallery/1", groups: [], dir: "" };
        set({ gallery: g });
        return g;
      }
    },
    showGallery() {
      set({ page: "gallery", tool: "select", typed: "", picks: [], draft: [], palette: false, dialog: null });
      setHash("#gallery");
    },
    showStudio() {
      set({ page: "studio" });
      const ex = get().example;
      setHash(ex ? `#example=${encodeURIComponent(ex.name)}` : "#studio");
    },
    async openGallery(name) {
      const item = (get().gallery?.groups ?? []).flatMap((g) => g.items).find((x) => x.name === name) ?? null;
      let opened = false;
      await run(`opened a copy of '${item?.title ?? name}'`, async () => {
        await api.galleryOpen(name);
        opened = true;
        set({ sel: [], shapeSel: [], hist: { undo: [], redo: [] }, verify: {}, verifySpec: {}, sceneVerify: null, renumberReport: null, idErrors: {},
          tool: "select", typed: "", picks: [], draft: [], filter: "all", view: "2d" });
      }, { history: false });
      if (!opened) return;                            // the status bar says why
      // the first tag selected: its numbers are in the inspector, ready to change
      const first = get().scene.tags.find((t) => !t.hidden);
      const mounted = get().page === "studio";
      set({ example: item, page: "studio", sel: first ? [first.name] : [], shapeSel: [] });
      setHash(`#example=${encodeURIComponent(name)}`);
      // fit clear of the note; a canvas that mounts with the page fits on its first size
      fitPending = !mounted;
      get().zoomToFit(undefined, NOTE_W, 0.85);
    },

    async refresh() {
      ++previewSeq;                                   // the file's scene wins over a preview in flight
      const [d, scene] = await Promise.all([api.design(), api.scene(get().view === "3d")]);
      const fresh = d.path !== get().design.path || !get().doc;
      setDesign(d);
      setScene(scene);
      set({ previewing: false });
      // a newly opened file: the sheet dialog starts from its `sheet` key
      const sh = (get().doc as any)?.sheet;
      if (fresh && sh && typeof sh === "object") {
        set((s) => ({ sheet: { ...s.sheet, ...(typeof sh.page === "string" ? { page: sh.page } : {}),
          ...(sh.mode === "tight" || sh.mode === "spaced" ? { mode: sh.mode } : {}),
          ...(typeof sh.landscape === "boolean" ? { landscape: sh.landscape } : {}) } }));
      }
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
      if (fitPending) {
        fitPending = false;
        get().zoomToFit(undefined, get().example ? NOTE_W : 0, get().example ? 0.85 : 0.7);
      }
    },
    setShow(k, v) {
      set((s) => ({ show: { ...s.show, [k]: v } }));
    },
    setZScale(v) {
      set({ zScale: v });
    },
    zoomToFit(names, insetRight = 0, fill = 0.7) {
      const tags = get().scene.tags.filter((t) => !t.hidden && (!names || names.includes(t.name)));
      const boxes = tags.map((t) => tagBox(t));
      if (!names) {
        for (const s of shapesOf(get().doc)) {
          const pts = outline(s.shape).map((p) => applyXf(s.xf, p));
          if (pts.length) {
            const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
            boxes.push({ x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) });
          }
        }
      }
      const b = unionBox(boxes);
      if (!b) return;
      const { w: vw, h } = get().viewport;
      // insetRight: a panel over the canvas's right side (the example's note)
      const inset = vw - insetRight > vw * 0.45 ? insetRight : 0;
      const w = vw - inset;
      const zoom = Math.max(0.2, Math.min(16, Math.min((w * fill) / Math.max(1, b.x1 - b.x0), (h * fill) / Math.max(1, b.y1 - b.y0))));
      set((s) => ({ camera: { cx: (b.x0 + b.x1) / 2 + inset / 2 / zoom, cy: (b.y0 + b.y1) / 2, zoom }, fitRev: s.fitRev + 1 }));
    },

    select(name, additive = false) {
      set((s) => ({ sel: selectClick(s.sel, name, additive), shapeSel: additive ? s.shapeSel : [] }));
    },
    setSel(names) {
      set({ sel: names });
    },
    selectShape(key, additive = false) {
      set((s) => {
        if (key === null) return additive ? {} : { shapeSel: [], sel: [] };
        const on = s.shapeSel.includes(key);
        if (!additive) return { shapeSel: [key], sel: [] };
        return { shapeSel: on ? s.shapeSel.filter((k) => k !== key) : [...s.shapeSel, key] };
      });
    },
    setShapeSel(keys) {
      set({ shapeSel: keys });
    },
    selectAll() {
      set((s) => ({
        sel: s.scene.tags.filter((t) => !t.hidden).map((t) => t.name),
        shapeSel: shapesOf(s.doc).filter((x) => x.hk === null).map((x) => x.key),
      }));
    },

    setTool(t) {
      let s = get();
      // a tool that works on a shape takes the selected tag's shape
      if ((t === "extrude" || t === "aruco" || t === "hole" || t === "rhole") && !s.shapeSel.length && s.sel.length === 1 && t !== "aruco") {
        const k = s.scene.tags.find((x) => x.name === s.sel[0])?.source?.shape;
        if (k) { set({ shapeSel: [k], sel: [] }); s = get(); }
      }
      let picks: string[] = [];
      if (t === "aruco") {
        // the selection is the first pick: a selected shape (its body's top
        // when extruded) or a selected tag's face
        const d = s.doc ? JSON.parse(JSON.stringify(s.doc)) : null;
        for (const k of s.shapeSel) {
          const r = d ? refOfShape(d, k) : null;
          if (r && !picks.includes(r)) picks.push(r);
        }
      }
      set({ tool: t, typed: "", picks, draft: [] });
      if (t === "extrude" && !s.shapeSel.filter((k) => !k.includes("/")).length) get().say("Extrude: select a shape (click it), then type the height and Enter", "warn");
    },
    typeKey(k) {
      if (k === "Backspace") set((s) => ({ typed: s.typed.slice(0, -1) }));
      else set((s) => ({ typed: (s.typed + k).slice(0, 40) }));
    },
    setTyped(t) {
      set({ typed: t });
    },
    togglePick(ref, additive) {
      set((s) => {
        if (!additive) return { picks: [ref] };
        return { picks: s.picks.includes(ref) ? s.picks.filter((r) => r !== ref) : [...s.picks, ref] };
      });
    },
    setDraft(pts) {
      set({ draft: pts });
    },
    async confirm() {
      const s = get();
      const nums = typedNumbers(s.typed);
      const at = typedAt();
      if (s.tool === "rect" && nums) {
        const [w, h] = [nums[0], nums[1] ?? nums[0]];
        if (w > 0 && h > 0) return get().createShape({ rect: [w, h] }, at);
      }
      if (s.tool === "circle" && nums && nums[0] > 0) return get().createShape({ circle: nums[0] }, at);
      if (s.tool === "slot" && nums && nums.length >= 2 && nums[0] > nums[1] && nums[1] > 0) return get().createShape({ slot: [nums[0], nums[1]] }, at);
      if ((s.tool === "hole" || s.tool === "rhole") && nums) {
        const key = s.shapeSel.find((k) => !k.includes("/"));
        const info = key ? findShape(s.doc, key) : null;
        if (!info) { get().say("Hole: select a shape first, or click inside one", "warn"); return; }
        return get().holeAt([info.xf[0], info.xf[1]], s.tool === "rhole");
      }
      if (s.tool === "extrude") {
        const key = s.shapeSel.find((k) => !k.includes("/"));
        if (!key) { get().say("Extrude: select a shape first", "warn"); return; }
        const h = nums ? nums[0] : 5;
        if (!h) { get().say("Extrude: a height other than 0", "warn"); return; }
        set({ tool: "select", typed: "" });
        let body: string | null = null;
        const ok = await get().editDoc(`extruded ${key} ${h} mm`, (d) => { body = extrude(d, key, h); return body !== null; });
        if (ok && get().view === "2d") await get().setView("3d");
        return;
      }
      if (s.tool === "aruco") {
        if (!s.picks.length) { get().say("ArUco Extrude: click a shape or a face first (Shift+click for more)", "warn"); return; }
        return get().arucoOn(s.picks);
      }
      if (s.tool === "polygon" && s.draft.length >= 3) {
        const pts = s.draft;
        const c = centroid(pts);
        const at2: Pt = [Math.round(c[0] * 2) / 2, Math.round(c[1] * 2) / 2];
        set({ draft: [] });
        return get().createShape({ polygon: pts.map((p) => [Math.round((p[0] - at2[0]) * 1e6) / 1e6, Math.round((p[1] - at2[1]) * 1e6) / 1e6]) }, at2);
      }
      if (s.typed) get().say(`'${s.typed}': not what ${s.tool} takes`, "warn");
    },
    cancel() {
      const s = get();
      if (s.tool !== "select" || s.typed || s.draft.length) {
        set({ tool: "select", typed: "", picks: [], draft: [] });
        return;
      }
      set({ sel: [], shapeSel: [] });
    },

    async editDoc(label, fn, opts = {}) {
      let ok = false;
      await run(label, async () => {
        const block = writeBlock(get().design);
        if (block) throw new Error(block);
        const p = parse(get().design.text || dump({ schema: "arucostudio.scene/2", name: get().scene.name, sketches: [], features: [] }));
        const d = p.value as Doc;
        const out = fn(d);
        if (out === false) return;
        const text = dump(d);
        if (text === get().design.text) return;
        await api.designPut(text, get().design.hash);
        ok = true;
        opts.select?.(out);
      });
      return ok;
    },
    async writeText(label, text) {
      let ok = false;
      await run(label, async () => {
        if (text === get().design.text) return;
        await api.designPut(text, get().design.hash);
        ok = true;
      });
      return ok;
    },

    preview(text) {
      // 15 Hz at most, the newest text wins; nothing is written
      previewNext = text;
      if (previewBusy) return;
      const go = async () => {
        while (previewNext !== null) {
          const t = previewNext;
          previewNext = null;
          previewBusy = true;
          const seq = ++previewSeq;
          const t0 = performance.now();
          const sc = await fetchPreview(t, false);   // the light preview: no meshes
          // drawn only while it is still the newest (a release may have come)
          if (sc && seq === previewSeq) { setScene(sc); set({ previewing: true }); }
          const wait = 1000 / 15 - (performance.now() - t0);
          if (wait > 0) await new Promise((res) => setTimeout(res, wait));
          previewBusy = false;
        }
      };
      void go();
    },
    async commitLive(text, label, t0) {
      // the pointer is up: the plans of the final text on screen first (the
      // preview's: cached, or the one in flight, or asked now), then the file
      // written
      const start = t0 ?? performance.now();
      previewNext = null;
      ++previewSeq;                                   // an older preview in flight is not drawn
      liveBusy++;                                     // idle() waits for the write too
      let sc: SceneDoc | null = null;
      try {
        sc = await fetchPreview(text, get().view === "3d");
        if (sc) {
          setScene(sc);
          set({ lastLive: performance.now() - start });
        }
      } finally {
        liveBusy--;
      }
      await get().writeText(label, text);
      if (!sc) set({ lastLive: performance.now() - start });
    },
    async createShape(shape, at, rot = 0) {
      let key = "";
      const ok = await get().editDoc(`added a ${Object.keys(shape)[0]}`, (d) => { key = addShape(d, shape, at, rot); });
      set({ tool: "select", typed: "" });
      if (ok) set({ shapeSel: [key], sel: [] });
    },
    async holeAt(p, rect) {
      const s = get();
      const nums = typedNumbers(s.typed);
      const infos = shapesOf(s.doc).filter((x) => x.hk === null);
      // the selected shape when p is inside it, else the top-most shape under p
      const hit = [...infos].reverse().filter((x) => {
        const pts = outline(x.shape).map((q) => applyXf(x.xf, q));
        if (!pts.length) return false;
        let inside = false;
        for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
          const [x0, y0] = pts[j], [x1, y1] = pts[i];
          if ((y0 > p[1]) !== (y1 > p[1]) && x0 + ((p[1] - y0) * (x1 - x0)) / (y1 - y0) > p[0]) inside = !inside;
        }
        return inside;
      });
      const info = hit.find((x) => s.shapeSel.includes(x.key)) ?? hit[0];
      if (!info) { get().say("Hole: click inside a shape", "warn"); return; }
      const local = applyXf(invert(info.xf), p);
      const q: Pt = [Math.round(local[0] * 2) / 2 + 0, Math.round(local[1] * 2) / 2 + 0];
      const hole = rect ? { rect: [nums?.[0] ?? 10, nums?.[1] ?? nums?.[0] ?? 6] } : { circle: nums?.[0] ?? 5 };
      let hk: string | null = null;
      await get().editDoc(`hole ${rect ? `${hole.rect![0]} × ${hole.rect![1]}` : `⌀ ${(hole as any).circle}`} in ${info.key}`,
        (d) => { hk = addHole(d, info.key, hole, q); return hk !== null; });
      set({ tool: "select", typed: "", shapeSel: [info.key], sel: [] });
    },
    async arucoOn(refs, extra = {}, base = "tag") {
      // the preset first (M6 a): a new tag is made by the new-tag preset when
      // it is not the file's own
      const np = get().newPreset;
      const filePreset = String((get().doc as any)?.preset ?? "Default");
      const more = !("preset" in extra) && np && np !== filePreset ? { preset: np } : {};
      await writeAruco(`ArUco Extrude on ${refs.join(", ")}`, (d) => arucoNamed(d, refs, { ...more, ...extra }, base));
    },
    async addTag(layout) {
      // the palette's "ArUco: single / grid / ChArUco": on the selected shapes,
      // else on a new 40 x 40 mm plate, 3 mm thick (today's default target)
      const keys = get().shapeSel.filter((k) => !k.includes("/"));
      const base = layout === "single" ? "tag" : layout === "grid" ? "board" : "charuco";
      const extra: Record<string, unknown> = { layout };
      const filePreset = String((get().doc as any)?.preset ?? "Default");
      if (get().newPreset && get().newPreset !== filePreset) extra.preset = get().newPreset;
      if (keys.length) {
        const d = JSON.parse(JSON.stringify(get().doc));
        const refs = keys.map((k) => refOfShape(d, k)).filter(Boolean) as string[];
        await get().arucoOn(refs, extra, base);
        return;
      }
      const words = layout === "single" ? "a single marker" : layout === "grid" ? "a grid board" : "a ChArUco board";
      await writeAruco(`added ${words}`, (d) => {
        const [x, y] = placeNew(get().scene.tags, 40);
        const key = addShape(d, { rect: [40, 40] }, [x, y]);
        const body = extrude(d, key, 3);
        return arucoNamed(d, [`${body}.top`], extra, base);
      });
      const t = get().sel[0];
      if (t) keepInView([t]);
    },

    async moveSel(dx, dy, keys) {
      const shapeKeys = keys ?? [...get().shapeSel, ...shapesOfTags(get().sel)];
      if (!shapeKeys.length || (!dx && !dy)) return;
      await get().editDoc(`moved ${shapeKeys.length === 1 ? shapeKeys[0] : shapeKeys.length + " shapes"} by ${+dx.toFixed(3)}, ${+dy.toFixed(3)} mm`,
        (d) => moveShapes(d, shapeKeys, dx, dy));
    },
    async nudge(dx, dy) {
      await get().moveSel(dx, dy);
    },
    async rotateSel(deg) {
      const keys = [...get().shapeSel, ...shapesOfTags(get().sel)];
      if (!keys.length) return;
      await get().editDoc(`turned ${keys.length === 1 ? keys[0] : keys.length + " shapes"} ${deg > 0 ? "counter-clockwise" : "clockwise"} 90°`,
        (d) => rotateShapes(d, keys, deg));
    },
    async arrange() {
      // every shape that carries tags (the selection's, or all) in a row, 10 mm apart
      const tags = get().scene.tags.filter((t) => !t.hidden && (!get().sel.length || get().sel.includes(t.name)));
      const order: string[] = [];
      for (const t of tags) if (t.source?.shape && !order.includes(t.source.shape)) order.push(t.source.shape);
      if (!order.length) return;
      await get().editDoc("arranged in a row, 10 mm apart", (d) => {
        let x: number | null = null, top = 0;
        for (const k of order) {
          const mine = get().scene.tags.filter((t) => t.source?.shape === k);
          const b = unionBox(mine.map((t) => tagBox(t)));
          const info = findShape(d, k);
          if (!b || !info) continue;
          if (x === null) { x = b.x0; top = b.y1; }
          moveShapes(d, [k], Math.round((x - b.x0) * 2) / 2, Math.round((top - b.y1) * 2) / 2);
          x += b.x1 - b.x0 + 10;
        }
      });
      get().zoomToFit();
    },
    async duplicateSel() {
      const shapes = get().shapeSel.filter((k) => !k.includes("/"));
      const tags = tagsSel();
      if (!shapes.length && !tags.length) return;
      if (shapes.length) {
        let out: string[] = [];
        await get().editDoc(`duplicated ${shapes.length === 1 ? shapes[0] : shapes.length + " shapes"}`, (d) => {
          const b = shapesOf(d).filter((x) => shapes.includes(x.key));
          let dy = -50;
          for (const s of b) {
            const ys = outline(s.shape).map((p) => applyXf(s.xf, p)[1]);
            if (ys.length) dy = Math.min(dy, -(Math.max(...ys) - Math.min(...ys)) - 10);
          }
          out = duplicateShapes(d, shapes, 0, Math.round(dy * 2) / 2);
        });
        set({ shapeSel: out, sel: [] });
        return;
      }
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
      const shapes = get().shapeSel;
      const tags = tagsSel();
      if (!shapes.length && !tags.length) return;
      const what = [...shapes, ...tags.map((t) => t.name)];
      await get().editDoc(`deleted ${what.length === 1 ? what[0] : what.length + " items"}`, (d) => {
        // tags first (their feature indices are the compile's), last feature first
        const byFeature = [...tags].sort((a, b) => (b.source?.feature ?? 0) - (a.source?.feature ?? 0) || (b.source?.entry ?? 0) - (a.source?.entry ?? 0));
        for (const t of byFeature) deleteTag(d, t.source, t.name);
        if (shapes.length) deleteShapes(d, shapes);
      });
      set({ sel: [], shapeSel: [] });
    },

    async edit(path, value, extra) {
      const tags = tagsSel();
      if (!tags.length) return;
      await run(`${path} = ${typeof value === "object" ? JSON.stringify(value) : String(value)}`, async () => {
        const refused: string[] = [];
        for (const t of tags) {
          // the scene's tag now (an earlier one of a face list may have split it)
          const now = get().scene.tags.find((x) => x.name === t.name) ?? t;
          let body = patchFor(path, value, now.spec);
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
    async setMode(mode) {
      // REF's dialog keeps the black's step from the white top when the
      // Extrude changes; the core's preset mapping holds that rule.
      const tags = tagsSel();
      await run(`Colours: ${mode}`, async () => {
        for (const t of tags) {
          const of = await api.presetOf(t.spec as any);
          const p = { ...of.preset, tag: { ...of.preset.tag, mode } };
          const sp = await api.presetApply(t.spec as any, "", p as any);
          await api.patchTag(t.name, { settings: { mode: sp.settings.mode }, numbers: { black_offset: sp.numbers.black_offset } });
        }
      });
    },
    async moveLabel(name, x_mm, y_mm) {
      await run(`${name}: label moved to X ${x_mm.toFixed(2)}, Y ${y_mm.toFixed(2)} mm`, async () => {
        await api.patchTag(name, { settings: { label: { position: "manual", x_mm, y_mm } } });
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
      await run("", async () => {
        const inked: string[] = [];
        for (const t of tags) {
          const sp = await api.presetApply(t.spec as any, name, preset);
          const was = String((t.spec.settings as any).dictionary ?? ""), now = String((sp.settings as any).dictionary ?? "");
          if (was && now && was !== now) inked.push(`${t.name} ${was} → ${now}`);
          await api.patchTag(t.name, { settings: sp.settings, numbers: sp.numbers });
        }
        get().say(inked.length ? `preset '${name}': it also changed the dictionary (${inked.join(", ")})` : `preset '${name}'`,
          inked.length ? "warn" : "info");
        set({ newPreset: name });
        try { set({ recent: (await api.addRecent(name)).recent }); } catch { /* the list is a convenience */ }
      });
    },
    async renumber() {
      await run("", async () => {
        const rep = await api.renumber();
        set({ renumberReport: rep, idErrors: {} });
        const n = rep.changed.length;
        get().say(n ? `Renumber: ${n} tag${n === 1 ? "" : "s"} changed (${rep.changed.map((c) => `${c.tag} ${c.from}→${c.to}`).join(", ")})` : "Renumber: every id already unique, nothing changed",
          rep.ok ? "info" : "warn");
      });
    },
    async override(name, id) {
      await run("", async () => {
        try {
          const r = await api.override(name, id);
          set((s) => { const m = { ...s.idErrors }; delete m[name]; return { idErrors: m }; });
          get().say(id === null ? `${name}: first id back to auto (its ids stay until the next Renumber)`
            : `${name}: first id ${id}, ids ${idsText(r.ids)}`);
        } catch (e) {
          if (e instanceof ApiError && e.status === 409) {
            const text = errorText(e.detail);
            set((s) => ({ idErrors: { ...s.idErrors, [name]: text } }));
            get().say(`${name}: first id ${id} not used: ${text}`, "error");
            return;
          }
          throw e;
        }
      });
    },

    async undo() {
      await queue;
      const block = writeBlock(get().design);
      if (block) return get().say(`Undo: ${block}`, "error");
      const h = get().hist;
      if (!h.undo.length) return get().say("nothing to undo", "warn");
      const text = h.undo[h.undo.length - 1];
      const now = get().design.text;
      await run("undone", async () => {
        await api.designPut(text, get().design.hash);
        set({ hist: { undo: h.undo.slice(0, -1), redo: [...h.redo, now] } });
      }, { history: false });
    },
    async redo() {
      await queue;
      const block = writeBlock(get().design);
      if (block) return get().say(`Redo: ${block}`, "error");
      const h = get().hist;
      if (!h.redo.length) return get().say("nothing to redo", "warn");
      const text = h.redo[h.redo.length - 1];
      const now = get().design.text;
      await run("redone", async () => {
        await api.designPut(text, get().design.hash);
        set({ hist: { undo: [...h.undo, now], redo: h.redo.slice(0, -1) } });
      }, { history: false });
    },

    async newScene(name) {
      // a new scene is a new file in the scenes folder at once (no Save)
      await run(`new scene '${name}'`, async () => {
        const list = await api.scenes();
        if (list.some((x) => x.name === name)) throw new Error(`a scene '${name}' exists: open it, or pick another name`);
        await api.sceneNew(name);
        await api.save(name);
        leftGallery();
        set({ sel: [], shapeSel: [], hist: { undo: [], redo: [] }, verify: {}, verifySpec: {}, sceneVerify: null, renumberReport: null, idErrors: {}, tool: "select", typed: "", picks: [] });
      }, { history: false });
    },
    async saveAs(v) {
      await run("", async () => {
        const r = /[\\/:]/.test(v) ? await api.designSaveAs(v) : await api.save(v);
        leftGallery();
        get().say(`now following ${(r as any).path ?? (r as any).saved}: every change writes it`);
      }, { history: false });
    },
    async openScene(name) {
      await run(`opened '${name}'`, async () => {
        await api.open(name);
        leftGallery();
        set({ sel: [], shapeSel: [], hist: { undo: [], redo: [] }, verify: {}, verifySpec: {}, sceneVerify: null, renumberReport: null, idErrors: {} });
      }, { history: false });
      get().zoomToFit();
    },
    async openPath(path) {
      await run(`opened ${path}`, async () => {
        await api.designOpen(path);
        leftGallery();
        set({ sel: [], shapeSel: [], hist: { undo: [], redo: [] }, verify: {}, verifySpec: {}, sceneVerify: null, renumberReport: null, idErrors: {} });
      }, { history: false });
      get().zoomToFit();
    },
    async openExample(name) {
      await run(`opened a copy of the example '${name}'`, async () => {
        await api.openExample(name);
        leftGallery();
        set({ sel: [], shapeSel: [], hist: { undo: [], redo: [] }, verify: {}, verifySpec: {}, sceneVerify: null, renumberReport: null, idErrors: {} });
      }, { history: false });
      get().zoomToFit();
    },
    async reveal() {
      await run("", async () => {
        const r = await api.designReveal(true);
        get().say(r.opened ? `revealed ${r.path}` : `the file: ${r.path}`);
      }, { history: false });
    },

    async verifySel() {
      const tags = tagsSel().length ? tagsSel() : get().scene.tags.filter((t) => !t.hidden);
      set({ drawer: "verify", verifyProgress: { done: 0, total: tags.length } });
      await run("", async () => {
        const out: Record<string, VerifyReport> = { ...get().verify };
        const specs: Record<string, string> = { ...get().verifySpec };
        try {
          for (const [i, t] of tags.entries()) {
            if (tags.length > 1) get().say(`Verify: ${t.name} (${i + 1} of ${tags.length})…`);
            out[t.name] = await api.verify(t.spec as any);
            specs[t.name] = specKey(t.spec);
            set({ verify: { ...out }, verifySpec: { ...specs }, verifyProgress: { done: i + 1, total: tags.length } });
          }
        } finally {
          set({ verifyProgress: null });
        }
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
        const over = (rep.overlaps || []).length;
        get().say(rep.ok ? "Verify sheet: every marker found where the scene puts it"
          : over ? `Verify sheet: ${over} overlap${over === 1 ? "" : "s"} (${rep.overlaps.map((o: any) => o.tags.join(" / ")).join(", ")})`
          : "Verify sheet: not every marker was found", rep.ok ? "info" : "warn");
      }, { history: false });
    },
    async exportScene(fmt) {
      let files: string[] = [];
      await run("", async () => {
        const r = await api.sceneExport(fmt);
        files = r.files;
        const types: Record<string, string> = { svg: "image/svg+xml", png: "image/png", pdf: "application/pdf", json: "application/json", stl: "model/stl" };
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
      set({ presets: p.items, presetCollections: p.collections ?? [], recent: r.recent });
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
    setPalette(open) {
      set({ palette: open });
    },
    setFilter(f) {
      set((s) => ({ filter: f, sel: s.sel.filter((n) => filtered(s.scene.tags.filter((t) => t.name === n), f).length) }));
    },
    setSheet(q) {
      set((s) => ({ sheet: { ...s.sheet, ...q } }));
    },
    async loadStale() {
      try { set({ stale: (await api.prusaStale()).stale }); } catch { set({ stale: [] }); }
    },
    async loadPrinters() {
      try {
        const p = await api.prusaPrinters();
        set({ printers: p });
        return p;
      } catch (e) {
        get().say(`PrusaSlicer's printers: ${msgOf(e)}`, "error");
        return null;
      }
    },
    async printSheet(q) {
      // M6c: the sheet's PDF printed from the page, at 100 %
      const query = { ...get().sheet, ...(q ?? {}) };
      let out: PrintOutcome = "fallback";
      await run("", async () => {
        out = await printPdf(query);
        if (out === "fallback") set({ dialog: { kind: "print", url: api.printUrl(query), why: "This browser cannot print the PDF from the page." } });
        get().say(out === "fallback" ? "Print: open the PDF, then Ctrl+P at Actual size (100 %)"
          : "Print: the sheet went to the print dialog; print at 100 % (Actual size) and check the 100 mm bar");
      }, { history: false });
      return out;
    },
    async exportSheet(q) {
      const query = { ...get().sheet, ...(q ?? {}) };
      let out: { dir: string; files: string[] } | null = null;
      await run("", async () => {
        // the sheet's files only: the 3D parts are Send's (audit 2026-10-17)
        const r = await api.exportPrint({ ...query, inline: false, sheet_only: true });
        out = { dir: r.dir, files: r.written ?? r.files };
        get().say(`sticker sheet: ${r.stickers} sticker${r.stickers === 1 ? "" : "s"} on ${r.pages} page${r.pages === 1 ? "" : "s"}, written to ${r.dir}`);
      }, { history: false });
      return out;
    },
    async sendPrusa(b) {
      let ans: SendAnswer | null = null;
      await run("", async () => {
        ans = await api.sendPrusa(b);
        set({ lastSend: ans });
        const a = ans as SendAnswer;
        get().say(`Send to PrusaSlicer: ${a.project}${a.opened ? " (opened in PrusaSlicer)" : ""}`);
      }, { history: false });
      return ans;
    },
    async idle() {
      // settled: nothing queued since the last change ended, nothing busy
      for (let i = 0; i < 200; i++) {
        const q = queue;
        await q;
        await new Promise((r) => setTimeout(r, 0));
        if (q === queue && !get().busy && !previewBusy && !liveBusy) return;
        await new Promise((r) => setTimeout(r, 15));
      }
    },
  };
});

/** A tag's frame in the 2D view: its canvas place times its pattern frame. */
export function patternToScene(t: SceneTag): number[] | null {
  const pit = t.plan?.frames?.pattern_in_target;
  if (!pit) return null;
  return matMul(poseOf(t.x_mm, t.y_mm, t.rotation_deg), pit);
}

/** A tag's frame in 3D: its full pose (standing on its face) times its pattern frame. */
export function patternIn3d(t: SceneTag): number[] | null {
  const pit = t.plan?.frames?.pattern_in_target;
  if (!pit) return null;
  return matMul(t.pose_3d ?? poseOf(t.x_mm, t.y_mm, t.rotation_deg), pit);
}

/** What the tests read (ARCHITECTURE 4: the store exposes zRange and the
 *  camera centre; M8b1: the file, the shapes, the tool). */
export function studioProbe() {
  const s = useStudio.getState();
  return {
    center: [s.camera.cx * s.camera.zoom, s.camera.cy * s.camera.zoom],
    center_mm: [s.camera.cx, s.camera.cy],
    zoom: s.camera.zoom,
    zRange: sceneZ(s.scene.tags),
    view: s.view,
    sel: [...s.sel],
    shapeSel: [...s.shapeSel],
    tags: s.scene.tags.map((t) => ({ name: t.name, x_mm: t.x_mm, y_mm: t.y_mm, rotation_deg: t.rotation_deg, ids: t.plan?.ids ?? [], locked: t.locked })),
    doc: docOf(s.scene),
    file: s.doc,
    design: { path: s.design.path, state: s.design.state, hash: s.design.hash, error: s.design.error, revision: s.design.revision },
    text: s.design.text,
    shapes: shapesOf(s.doc).map((x) => ({ key: x.key, id: x.id, kind: Object.keys(x.shape).find((k) => ["rect", "circle", "polygon", "slot", "loops"].includes(k)), xf: x.xf, body: x.body, parent: x.parent })),
    tool: s.tool,
    typed: s.typed,
    picks: [...s.picks],
    rev: s.sceneRev,
    undo: s.hist.undo.length,
    redo: s.hist.redo.length,
    lastLive: s.lastLive,
    idErrors: { ...s.idErrors },
    issues: s.scene.issues ?? [],
  };
}
