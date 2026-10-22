// The reading range's runner and numbers (V4 "Range strip", Zach 2026-10-21):
// every marker's near–far on one camera, computed by the core's engine
// (aruco_studio/core/reading_range.py, OpenCV reading the rendered views) in
// the Pyodide worker, a slice at a time.
//
// WHY slices (range_start / range_step), not one call: a range is a few
// hundred renders (≈ 10–40 s in the browser), and the core is ONE worker: a
// plan or a bench view sent meanwhile waits one slice (STEP_MS), never the
// whole range; between slices the runner checks what is still wanted, so a
// closed dialog or a new camera stops it at once. A marker's partial job
// stays in the worker and resumes when it is wanted again.
// WHY cached by what the camera sees: the same marker on the same camera
// gives the same answer (seeded), so a finished range is kept (this visit,
// and in this browser under the core's version and the OpenCV that measured
// it) and an edit re-runs only that marker. The marker is its scene key
// (core scene_keys, web_api.scene_key: its plan and label in its own frame),
// not its request: moving or turning it on the page keeps its range (the
// canvas proposals measured a move and a turn re-running 6-26 s ranges when
// the key was the request, 2026-10-21); its size, ids, label or corner mark
// do not. WHY the OpenCV in the key (docs/peps/0003 decision 3): two OpenCVs
// draw the same view differently, so another one's range is never shown as
// this one's.
import type { CameraPreset, PlanRequest, RangeCamera, RangeNeed, RangeVerdict, ReadingRange } from "../core/contract";
import { core } from "../coreSource";

/** one slice: what a plan call waits at most behind a range */
export const STEP_MS = 250;
/** bump to drop every kept answer (the core's version is in the key too); /2: keyed on the scene, not the request */
const CACHE_TAG = "range-ui/2";
const STORE_KEY = "arucoStudio.verify.ranges";
const STORE_MAX = 240;
const CAMERA_KEY = "aruco-web.verify.rangeCamera";

export interface RangeTask {
  key: string; req: PlanRequest; camera: RangeCamera;
  /** the OpenCV it is for (its key's): an answer another one measured is never kept as this one's */
  opencv?: string;
}

export type RangeState =
  | { state: "queued" }
  | { state: "running"; fraction: number; phase?: string; renders: number; ms: number }
  | { state: "done"; result: ReadingRange; ms: number | null; cached: boolean }
  | { state: "error"; error: string };

/** The cache key of a marker's range: what the camera sees of it (its scene key), the camera, the core that
 *  answers and the OpenCV it runs. The range options beyond the camera (budget, cases, seed) are the core's
 *  defaults, so the core's version stands for them. */
export function rangeKey(scene: string, camera: RangeCamera, coreVersion: string, opencv: string): string {
  return JSON.stringify([CACHE_TAG, coreVersion, camera, scene, opencv]);
}

// ------------------------------------------------------------ the scene keys (what the camera sees of each marker)

/** request JSON -> its scene key (null: it does not plan); this visit's */
const scenes = new Map<string, string | null>();
const asking = new Set<string>();
const sceneListeners = new Set<() => void>();
let sceneTick = 0;

export function onScenes(cb: () => void): () => void { sceneListeners.add(cb); return () => { sceneListeners.delete(cb); }; }
export function scenesVersion(): number { return sceneTick; }

/** The scene key of a request, if known: undefined until the core answers, null when it does not plan. */
export function sceneOf(reqKey: string): string | null | undefined {
  return scenes.has(reqKey) ? scenes.get(reqKey)! : undefined;
}

/** Ask the core for the scene keys it does not have yet, all in one call (the strip's markers). */
export async function askScenes(items: { key: string; req: PlanRequest }[]): Promise<void> {
  const missing = items.filter((it) => !scenes.has(it.key) && !asking.has(it.key));
  if (!missing.length) return;
  for (const it of missing) asking.add(it.key);
  try {
    const keys = await core.scene_keys(missing.map((it) => it.req));
    missing.forEach((it, i) => scenes.set(it.key, keys[i] ?? null));
  } finally {
    for (const it of missing) asking.delete(it.key);
    sceneTick += 1;
    for (const cb of sceneListeners) cb();
  }
}

/** The range key of a marker: by its scene once known; one that does not plan by its request (its error shows). */
export function markerRangeKey(reqKey: string, camera: RangeCamera, coreVersion: string, opencv: string): string | null {
  const sc = sceneOf(reqKey);
  if (sc === undefined) return null;
  return rangeKey(sc ?? `request:${reqKey}`, camera, coreVersion, opencv);
}

/** A short stable hash (FNV-1a), for the stored copies' names. */
export function fnv(s: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(36);
}

// ------------------------------------------------------------ the kept answers

interface Stored { k: string; r: ReadingRange; ms: number | null }

function readStore(): Stored[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(STORE_KEY) ?? "[]") as unknown;
    return Array.isArray(v) ? (v as Stored[]).filter((x) => x && typeof x.k === "string" && x.r) : [];
  } catch { return []; }
}

function writeStore(xs: Stored[]): void {
  try { window.localStorage.setItem(STORE_KEY, JSON.stringify(xs.slice(-STORE_MAX))); } catch { /* storage blocked or full: kept for this visit only */ }
}

const memory = new Map<string, { result: ReadingRange; ms: number | null }>();

export function cached(key: string): { result: ReadingRange; ms: number | null } | null {
  const m = memory.get(key);
  if (m) return m;
  const s = readStore().find((x) => x.k === key);
  if (!s) return null;
  memory.set(key, { result: s.r, ms: s.ms });
  return memory.get(key)!;
}

function keep(key: string, result: ReadingRange, ms: number | null): void {
  memory.set(key, { result, ms });
  writeStore([...readStore().filter((x) => x.k !== key), { k: key, r: result, ms }]);
}

/** Forget every kept range (tests; a "measure again"). */
export function forgetRanges(): void {
  memory.clear();
  writeStore([]);
}

// ------------------------------------------------------------ the runner

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

class Runner {
  private states = new Map<string, RangeState>();
  private wanted: RangeTask[] = [];
  /** every task asked for, by key: what finished() reports a range was measured for */
  private tasks = new Map<string, RangeTask>();
  /** marker key -> the worker's job, while it is part done */
  private jobs = new Map<string, string>();
  private pumping = false;
  /** the marker whose slice is out now (never cancelled under itself) */
  private inFlight: string | null = null;
  private listeners = new Set<() => void>();
  private tick = 0;
  /** steps sent, for the e2e (a cached open sends none) */
  steps = 0;

  subscribe = (cb: () => void) => { this.listeners.add(cb); return () => { this.listeners.delete(cb); }; };
  version = () => this.tick;

  private set(key: string, s: RangeState) {
    this.states.set(key, s);
    this.tick += 1;
    for (const cb of this.listeners) cb();
  }

  state(key: string): RangeState {
    const s = this.states.get(key);
    if (s) return s;
    const c = cached(key);
    return c ? { state: "done", result: c.result, ms: c.ms, cached: true } : { state: "queued" };
  }

  /** What to measure, in order (the first unfinished one runs next). [] pauses
   *  (the bench is one click away: part-done jobs wait in the worker); a new
   *  list cancels the part-done jobs it no longer has (another camera, an
   *  edited marker: they would only hold the worker's memory). */
  want(tasks: RangeTask[]): void {
    if (tasks.length) {
      const keep = new Set(tasks.map((t) => t.key));
      for (const [key, job] of [...this.jobs]) {
        if (keep.has(key) || this.inFlight === key) continue;
        this.jobs.delete(key);
        void core.range_cancel(job).catch(() => undefined);
        if (this.states.get(key)?.state === "running") this.set(key, { state: "queued" });
      }
    }
    this.wanted = tasks;
    for (const t of tasks) this.tasks.set(t.key, t);
    for (const t of tasks) {
      const s = this.states.get(t.key);
      if (!s || s.state === "error") {
        const c = cached(t.key);
        this.set(t.key, c ? { state: "done", result: c.result, ms: c.ms, cached: true } : { state: "queued" });
      }
    }
    void this.pump();
  }

  /** Measure a marker again (after an error). */
  retry(key: string): void {
    if (this.states.get(key)?.state === "error") this.set(key, { state: "queued" });
    void this.pump();
  }

  /** The dialog closed: stop, and free the worker's part-done jobs. */
  cancelAll(): void {
    this.wanted = [];
    for (const job of this.jobs.values()) void core.range_cancel(job).catch(() => undefined);
    this.jobs.clear();
    for (const [k, s] of this.states) if (s.state === "running") this.set(k, { state: "queued" });
  }

  /** Something the strip shows changed outside the runner (a verdict came in). */
  touch(): void {
    this.tick += 1;
    for (const cb of this.listeners) cb();
  }

  /** Every finished range this visit, with the request and camera it was measured for (the e2e compares them with CPython). */
  finished(): { key: string; req: PlanRequest | null; camera: RangeCamera | null; result: ReadingRange; ms: number | null }[] {
    const out = [];
    for (const [key, st] of this.states) {
      if (st.state !== "done") continue;
      const t = this.tasks.get(key);
      out.push({ key, req: t?.req ?? null, camera: t?.camera ?? null, result: st.result, ms: st.ms });
    }
    return out;
  }

  busy(): boolean {
    return this.wanted.some((t) => { const s = this.state(t.key).state; return s === "queued" || s === "running"; });
  }

  private next(): RangeTask | undefined {
    return this.wanted.find((t) => { const s = this.state(t.key).state; return s === "queued" || s === "running"; });
  }

  private async pump(): Promise<void> {
    if (this.pumping) return;
    this.pumping = true;
    try {
      for (let t = this.next(); t; t = this.next()) {
        const task = t;
        this.inFlight = task.key;
        try {
          let job = this.jobs.get(task.key);
          if (!job) {
            const st = await core.range_start(task.req, { camera: task.camera });
            job = st.job;
            this.jobs.set(task.key, job);
            this.set(task.key, { state: "running", fraction: st.fraction ?? 0, phase: st.phase, renders: 0, ms: 0 });
          }
          this.steps += 1;
          const st = await core.range_step(job, STEP_MS);
          if (st.done && st.result && task.opencv && st.result.measured && st.result.opencv !== task.opencv) {
            // WHY (docs/peps/0003): a slice sent before another OpenCV was chosen is answered by the new
            // worker; that answer is the other OpenCV's, so it is not kept under this one's key
            this.jobs.delete(task.key);
            this.set(task.key, { state: "error", error: `measured on OpenCV ${st.result.opencv}, not ${task.opencv}: measure again` });
          } else if (st.done && st.result) {
            this.jobs.delete(task.key);
            keep(task.key, st.result, st.ms ?? null);
            this.set(task.key, { state: "done", result: st.result, ms: st.ms ?? null, cached: false });
          } else if (this.jobs.get(task.key) !== job) {
            // cancelled while this slice was out (the dialog closed, another camera): it starts over when wanted
            this.set(task.key, { state: "queued" });
          } else {
            this.set(task.key, { state: "running", fraction: st.fraction ?? 0, phase: st.phase, renders: st.renders, ms: st.ms ?? 0 });
          }
        } catch (e) {
          const msg = errText(e);
          this.jobs.delete(task.key);
          // the worker dropped a job (too many part done): start it over
          if (/no reading-range job/.test(msg)) this.set(task.key, { state: "queued" });
          else this.set(task.key, { state: "error", error: msg });
        } finally {
          this.inFlight = null;
        }
        // a marker no longer wanted while its slice was out: free its job now
        if (!this.wanted.some((w) => w.key === task.key) && this.wanted.length && this.jobs.has(task.key)) {
          const job = this.jobs.get(task.key)!;
          this.jobs.delete(task.key);
          void core.range_cancel(job).catch(() => undefined);
          if (this.states.get(task.key)?.state === "running") this.set(task.key, { state: "queued" });
        }
      }
    } finally {
      this.pumping = false;
    }
  }
}

export const ranges = new Runner();

// ------------------------------------------------------------ verdicts (the core judges)

const verdicts = new Map<string, RangeVerdict>();
const asked = new Map<string, Promise<RangeVerdict>>();

/** The core's verdict on a range against a requirement (cached; null until it answers). */
export function verdictKey(rangeKeyStr: string, need: RangeNeed): string {
  return JSON.stringify([rangeKeyStr, need.min_mm ?? null, need.max_mm ?? null]);
}

export function knownVerdict(k: string): RangeVerdict | null {
  return verdicts.get(k) ?? null;
}

export function judge(k: string, result: ReadingRange, need: RangeNeed): Promise<RangeVerdict> {
  const v = verdicts.get(k);
  if (v) return Promise.resolve(v);
  let p = asked.get(k);
  if (!p) {
    p = core.range_judge(result, need).then((r) => { verdicts.set(k, r); asked.delete(k); ranges.touch(); return r; },
      (e) => { asked.delete(k); throw e; });
    asked.set(k, p);
  }
  return p;
}

/** Nothing is required of a marker. */
export function needless(need: RangeNeed | null | undefined): boolean {
  return need?.min_mm == null && need?.max_mm == null;
}

// ------------------------------------------------------------ the camera, remembered per viewer

export interface CustomCamera { resolution: [number, number]; hfov_deg: number; focus_mm: number | null }
export type CameraPick = { id: string } | { custom: CustomCamera };

export const DEFAULT_CAMERA = "d435";
export const CUSTOM0: CustomCamera = { resolution: [1920, 1080], hfov_deg: 70, focus_mm: null };

export function loadCamera(): CameraPick {
  try {
    const v = JSON.parse(window.localStorage.getItem(CAMERA_KEY) ?? "null") as Partial<{ id: string; custom: CustomCamera }> | null;
    const ok = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x) && x > 0;
    if (v && typeof v.id === "string" && v.id) return { id: v.id };
    const c = v?.custom;
    if (c && Array.isArray(c.resolution) && ok(c.resolution[0]) && ok(c.resolution[1]) && ok(c.hfov_deg)) {
      return { custom: { resolution: [c.resolution[0], c.resolution[1]], hfov_deg: c.hfov_deg, focus_mm: ok(c.focus_mm) ? c.focus_mm : null } };
    }
  } catch { /* storage blocked or garbled: the default */ }
  return { id: DEFAULT_CAMERA };
}

export function saveCamera(p: CameraPick): void {
  try { window.localStorage.setItem(CAMERA_KEY, JSON.stringify(p)); } catch { /* kept for this visit only */ }
}

/** The camera the core is asked for: a library id, or the custom numbers. */
export function rangeCamera(p: CameraPick): RangeCamera {
  return "id" in p ? p.id : { id: "custom", name: "Custom camera", ...p.custom };
}

/** Search the library: every word typed must appear in the camera's name, stream, maker, pixels or keywords. */
export function searchCameras(lib: CameraPreset[], query: string): CameraPreset[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return lib;
  return lib.filter((c) => {
    const hay = `${c.name} ${c.stream} ${c.maker} ${c.resolution[0]}×${c.resolution[1]} ${c.resolution[0]}x${c.resolution[1]} ${c.keywords} ${c.id}`.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
}

// ------------------------------------------------------------ the shared axis

/** "446 mm", "1.52 m"; "—" for none. */
export function fmtMm(mm: number | null | undefined): string {
  if (mm === null || mm === undefined || !Number.isFinite(mm)) return "—";
  return mm >= 1000 ? `${(mm / 1000).toFixed(2)} m` : `${Math.round(mm)} mm`;
}

const NICE = [1, 2, 5];

/** The shared log axis (mm) for these ranges and requirements: from a nice
 *  value under the nearest to one over the farthest (the 90 % ends too). */
export function axisOf(results: (ReadingRange | null | undefined)[], needs: (RangeNeed | null | undefined)[] = []): [number, number] {
  const xs: number[] = [];
  for (const r of results) {
    if (!r) continue;
    if (r.near_mm) xs.push(r.near_mm);
    if (r.far_mm) xs.push(r.far_mm);
    if (r.band_mm) xs.push(r.band_mm[1]);
  }
  for (const n of needs) {
    if (n?.min_mm) xs.push(n.min_mm);
    if (n?.max_mm) xs.push(n.max_mm);
  }
  if (!xs.length) return [50, 5000];
  const lo = Math.min(...xs) / 1.25, hi = Math.max(...xs) * 1.25;
  return [niceDown(lo), niceUp(hi)];
}

function niceDown(v: number): number {
  const e = Math.floor(Math.log10(v));
  for (const m of [...NICE].reverse()) if (m * 10 ** e <= v) return m * 10 ** e;
  return 10 ** e;
}

function niceUp(v: number): number {
  const e = Math.floor(Math.log10(v));
  for (const m of [...NICE, 10]) if (m * 10 ** e >= v) return m * 10 ** e;
  return 10 ** (e + 1);
}

/** The 1–2–5 ticks inside the axis. */
export function ticksOf(lo: number, hi: number): number[] {
  const out: number[] = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of NICE) { const v = m * 10 ** e; if (v >= lo - 1e-9 && v <= hi + 1e-9) out.push(v); }
  }
  return out;
}

/** "0.1", "0.5", "1", "2 m": a tick's words (the last one carries the unit). */
export function tickText(mm: number, last: boolean): string {
  const m = mm / 1000;
  const s = m >= 1 ? String(+m.toFixed(1)) : String(+m.toFixed(2));
  return last ? `${s} m` : s;
}

/** A distance on the axis, as x in [x0, x1] (log scale; clamped). */
export function xOf(mm: number, lo: number, hi: number, x0: number, x1: number): number {
  const t = Math.log(Math.min(Math.max(mm, lo), hi) / lo) / Math.log(hi / lo);
  return x0 + t * (x1 - x0);
}

// ------------------------------------------------------------ the e2e's and the bench's hook
// WHY on window: the bench (web/scripts/bench-verify-range.mjs) times one
// marker's range through the real worker, slices and all, from a request it
// built itself; the e2e reads the runner's state and resets the kept answers.
if (typeof window !== "undefined") {
  (window as unknown as { __arucoRange: unknown }).__arucoRange = {
    run: async (req: PlanRequest, camera: RangeCamera, budgetMs = STEP_MS) => {
      const t0 = performance.now();
      const st0 = await core.range_start(req, { camera });
      const firstMs = performance.now() - t0;
      let steps = 0, worst = 0;
      for (;;) {
        const ts = performance.now();
        const st = await core.range_step(st0.job, budgetMs);
        steps += 1;
        worst = Math.max(worst, performance.now() - ts);
        if (st.done && st.result) return { result: st.result, wall_ms: performance.now() - t0, start_ms: firstMs, render_ms: st.ms ?? null, steps, renders: st.renders, worst_step_ms: worst };
      }
    },
    steps: () => ranges.steps,
    finished: () => ranges.finished(),
    forget: () => forgetRanges(),
    state: (key: string) => ranges.state(key),
  };
}
