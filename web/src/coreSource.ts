// Which core the UI talks to: the real one (web/src/core/client.ts, the
// Pyodide worker) by default, the mock (web/src/dev/mockCore.ts) with
// ?core=mock. Every call is counted, so the test probe's idle() can wait
// until nothing is in flight. The UI imports `core` and `useCoreStatus`
// from here and nothing else of the core's.
import { useSyncExternalStore } from "react";
import type { CoreApi, CoreStatus } from "./core/contract";
import { loadOpenCv, opencvBuild, saveOpenCv } from "./core/opencv";

export const coreKind: "real" | "mock" =
  typeof location !== "undefined" && new URLSearchParams(location.search).get("core") === "mock" ? "mock" : "real";

let status: CoreStatus = { state: "loading", detail: coreKind === "mock" ? "mock core" : undefined };
const listeners = new Set<() => void>();
function setStatus(s: CoreStatus) {
  status = s;
  for (const f of listeners) f();
}
export function coreStatus(): CoreStatus { return status; }
export function onCoreStatus(cb: () => void): () => void { listeners.add(cb); return () => { listeners.delete(cb); }; }
export function useCoreStatus(): CoreStatus { return useSyncExternalStore(onCoreStatus, coreStatus); }

const t0 = typeof performance !== "undefined" ? performance.now() : 0;
/** How long the core has been starting (ms, from this module's load): the
 *  waits the UI shows count from here. */
export function coreElapsedMs(): number { return performance.now() - t0; }

// The OpenCV Verify runs (./core/opencv.ts): the real core's worker's choice
// (client.ts), mirrored here so the UI reads it at once; the mock never
// verifies, so its choice is only remembered.
export interface OpencvState { wanted: string; loaded: string | null }
let opencv: OpencvState = { wanted: typeof window === "undefined" ? opencvBuild(null).version : loadOpenCv(), loaded: null };
let chooseInCore: ((version: string) => void) | null = null;
const opencvListeners = new Set<() => void>();
function setOpencv(s: OpencvState) {
  opencv = s;
  for (const f of opencvListeners) f();
}
export function opencvState(): OpencvState { return opencv; }
export function onOpencv(cb: () => void): () => void { opencvListeners.add(cb); return () => { opencvListeners.delete(cb); }; }
export function useOpencv(): OpencvState { return useSyncExternalStore(onOpencv, opencvState); }
/** Run another of the browser's OpenCV builds (remembered; the worker restarts if it loaded another). */
export function chooseOpencv(version: string): void {
  if (chooseInCore) { chooseInCore(version); return; }
  saveOpenCv(version);
  setOpencv({ ...opencv, wanted: opencvBuild(version).version });
}

// WHY a dynamic import per kind: the mock must not boot Pyodide, and the
// real build must not ship the mock in its main chunk.
const source: Promise<CoreApi> = coreKind === "mock"
  ? import("./dev/mockCore").then((m) => m.createMockCore(() => setStatus({ state: "ready", detail: "mock core", ms: Math.round(performance.now() - t0) })))
  : import("./core/client").then((m) => {
    const sync = () => setStatus(m.coreStatus());
    m.onCoreStatus(sync);
    sync();
    const syncCv = () => setOpencv(m.opencvState());
    m.onOpencv(syncCv);
    syncCv();
    chooseInCore = m.chooseOpencv;
    return m.core;
  });

let inflight = 0;
const idleWaiters = new Set<() => void>();
export function callsInFlight(): number { return inflight; }
export function onCallsSettled(cb: () => void): () => void { idleWaiters.add(cb); return () => { idleWaiters.delete(cb); }; }

/** A test-only fault hook (web/e2e/startup.spec.ts), inert unless the page
 *  sets window.__arucoFault: `{presets: 1}` rejects the next presets call
 *  (Infinity: every one), `{delay: {plan: 9000}}` holds each plan call 9 s
 *  before it goes out. */
interface Fault { delay?: Partial<Record<keyof CoreApi, number>>; [name: string]: unknown }

async function injected(name: keyof CoreApi): Promise<void> {
  const fault = (globalThis as { __arucoFault?: Fault }).__arucoFault;
  if (!fault) return;
  const hold = fault.delay?.[name];
  if (hold) await new Promise((r) => setTimeout(r, hold));
  const n = fault[name];
  if (typeof n === "number" && n > 0) {
    fault[name] = n - 1;
    throw new Error(`${name}: injected fault`);
  }
}

function counted<K extends keyof CoreApi>(name: K): CoreApi[K] {
  return (async (...args: unknown[]) => {
    inflight += 1;
    try {
      await injected(name);
      const api = await source;
      return await (api[name] as (...a: unknown[]) => Promise<unknown>)(...args);
    } finally {
      inflight -= 1;
      if (!inflight) for (const f of [...idleWaiters]) f();
    }
  }) as CoreApi[K];
}

export const core: CoreApi = {
  info: counted("info"), presets: counted("presets"), inscribe: counted("inscribe"), plan: counted("plan"),
  suggest: counted("suggest"), svg: counted("svg"), sheet: counted("sheet"),
  verify: counted("verify"), readable: counted("readable"), assign_ids: counted("assign_ids"),
  cameras: counted("cameras"), reading_range: counted("reading_range"), range_start: counted("range_start"),
  range_step: counted("range_step"), range_cancel: counted("range_cancel"), range_judge: counted("range_judge"),
  scene_keys: counted("scene_keys"),
};
