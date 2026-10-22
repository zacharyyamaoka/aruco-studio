// The CoreApi the UI imports, over the Pyodide worker (./worker.ts). The
// exported names are part of the contract:
//   core: CoreApi, coreStatus(): CoreStatus, onCoreStatus(cb), useCoreStatus()
// The worker starts when this module loads; calls made before the core is
// ready wait in a queue and go out in order once it is; if it fails to
// load, they (and every later call) reject with the reason.
// And the OpenCV Verify runs (./opencv.ts; docs/peps/0003 decision 3): ONE
// a worker, the viewer's choice or the newest. The worker is told before any
// call; choosing another once it has loaded one starts a new worker, and the
// calls the old one had not answered go to the new one, in order.
import { useSyncExternalStore } from "react";
import type { CoreApi, CoreStatus } from "./contract";
import { loadOpenCv, opencvBuild, saveOpenCv } from "./opencv";

let status: CoreStatus = { state: "loading", detail: "loading the Python core" };
const listeners = new Set<() => void>();

function setStatus(s: CoreStatus) {
  status = s;
  for (const cb of listeners) cb();
}

export function coreStatus(): CoreStatus { return status; }
export function onCoreStatus(cb: () => void): () => void { listeners.add(cb); return () => listeners.delete(cb); }
export function useCoreStatus(): CoreStatus { return useSyncExternalStore(onCoreStatus, coreStatus); }

interface Call { id: number; name: string; payload: unknown }
const pending = new Map<number, { call: Call; resolve: (v: unknown) => void; reject: (e: Error) => void }>();
const queue: Call[] = [];
let nextId = 1;
let worker: Worker | null = null;
let t0 = performance.now();

// ------------------------------------------------------------ the OpenCV this worker runs

/** the build asked for (the viewer's, remembered; else the newest) */
let opencvWanted: string = typeof window === "undefined" ? opencvBuild(null).version : loadOpenCv();
/** what the worker loaded (its cv2.__version__), once it has */
let opencvLoaded: string | null = null;
const opencvListeners = new Set<() => void>();
let opencvTick = 0;
function opencvChanged() {
  opencvTick += 1;
  for (const cb of opencvListeners) cb();
}

/** The OpenCV Verify runs: the build chosen, and the one the worker has loaded (null until its first OpenCV call). */
export function opencvState(): { wanted: string; loaded: string | null } { return { wanted: opencvWanted, loaded: opencvLoaded }; }
export function onOpencv(cb: () => void): () => void { opencvListeners.add(cb); return () => opencvListeners.delete(cb); }
export function opencvVersion(): number { return opencvTick; }

/** Run another build (one this browser lists): remembered; a worker that
 *  already loaded another is replaced (a compiled module cannot be swapped). */
export function chooseOpencv(version: string): void {
  const v = opencvBuild(version).version;
  saveOpenCv(v);
  if (v === opencvWanted) return;
  opencvWanted = v;
  if (opencvLoaded !== null && opencvLoaded !== v) restart(`starting the core again for OpenCV ${v}`);
  else worker?.postMessage({ kind: "opencv", version: v });
  opencvChanged();
}

// ------------------------------------------------------------ the worker

function fail(detail: string) {
  setStatus({ state: "error", detail });
  queue.length = 0;
  for (const p of pending.values()) p.reject(new Error(`core: ${detail}`));
  pending.clear();
}

function start() {
  if (typeof Worker === "undefined") return fail("this browser has no Web Workers");
  try {
    worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
  } catch (e) {
    return fail(e instanceof Error ? e.message : String(e));
  }
  const me = worker;
  // before any call: the build its first OpenCV call loads
  me.postMessage({ kind: "opencv", version: opencvWanted });
  me.onmessage = (e: MessageEvent) => {
    if (worker !== me) return;                 // a worker replaced by restart(): its last words are not ours
    const m = e.data as { kind?: string; ms?: number; detail?: string; version?: string; id?: number; result?: unknown; error?: string };
    if (m.kind === "ready") {
      setStatus({ state: "ready", ms: Math.round(performance.now() - t0) });
      for (const c of queue.splice(0)) me.postMessage(c);
    } else if (m.kind === "error") {
      fail(m.detail ?? "the core did not load");
    } else if (m.kind === "opencv") {
      opencvLoaded = m.version ?? null;
      opencvChanged();
    } else if (m.id !== undefined) {
      const p = pending.get(m.id);
      if (!p) return;
      pending.delete(m.id);
      if (m.error !== undefined) p.reject(new Error(m.error));
      else p.resolve(m.result);
    }
  };
  me.onerror = (e: ErrorEvent) => { if (worker === me) fail(e.message || "the core's worker failed"); };
}

/** A new worker (another OpenCV): what the old one had not answered is sent
 *  to the new one, in the order it was asked, then whatever was queued. */
function restart(detail: string) {
  const old = worker;
  worker = null;
  old?.terminate();
  opencvLoaded = null;
  const unanswered = [...pending.values()].map((p) => p.call).sort((a, b) => a.id - b.id);
  queue.unshift(...unanswered);
  t0 = performance.now();
  setStatus({ state: "loading", detail });
  start();
}

function send<T>(name: keyof CoreApi, payload: unknown): Promise<T> {
  if (status.state === "error") return Promise.reject(new Error(`core: ${status.detail ?? "not loaded"}`));
  return new Promise<T>((resolve, reject) => {
    const c: Call = { id: nextId++, name, payload };
    pending.set(c.id, { call: c, resolve: resolve as (v: unknown) => void, reject });
    if (status.state === "ready" && worker) worker.postMessage(c);
    else queue.push(c);
  });
}

start();

export const core: CoreApi = {
  info: () => send("info", {}),
  presets: () => send("presets", {}),
  inscribe: (profile, holes) => send("inscribe", { profile, holes }),
  plan: (req) => send("plan", req),
  suggest: (req) => send("suggest", req),
  svg: (req) => send("svg", req),
  sheet: (req) => send("sheet", req),
  verify: (req, view) => send("verify", { req, view }),
  readable: (req, camera) => send("readable", { req, camera }),
  assign_ids: (req) => send("assign_ids", req),
  cameras: () => send("cameras", {}),
  reading_range: (req, opts) => send("reading_range", { req, ...opts }),
  range_start: (req, opts) => send("range_start", { req, ...opts }),
  range_step: (job, budget_ms) => send("range_step", { job, ...(budget_ms === undefined ? {} : { budget_ms }) }),
  range_cancel: (job) => send("range_cancel", { job }),
  range_judge: (range, need) => send("range_judge", { range, need }),
};
