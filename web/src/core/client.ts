// The CoreApi the UI imports, over the Pyodide worker (./worker.ts). The
// exported names are part of the contract:
//   core: CoreApi, coreStatus(): CoreStatus, onCoreStatus(cb), useCoreStatus()
// The worker starts when this module loads; calls made before the core is
// ready wait in a queue and go out in order once it is; if it fails to
// load, they (and every later call) reject with the reason.
import { useSyncExternalStore } from "react";
import type { CoreApi, CoreStatus } from "./contract";

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
const pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
const queue: Call[] = [];
let nextId = 1;
let worker: Worker | null = null;
const t0 = performance.now();

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
  worker.onmessage = (e: MessageEvent) => {
    const m = e.data as { kind?: string; ms?: number; detail?: string; id?: number; result?: unknown; error?: string };
    if (m.kind === "ready") {
      setStatus({ state: "ready", ms: Math.round(performance.now() - t0) });
      for (const c of queue.splice(0)) worker!.postMessage(c);
    } else if (m.kind === "error") {
      fail(m.detail ?? "the core did not load");
    } else if (m.id !== undefined) {
      const p = pending.get(m.id);
      if (!p) return;
      pending.delete(m.id);
      if (m.error !== undefined) p.reject(new Error(m.error));
      else p.resolve(m.result);
    }
  };
  worker.onerror = (e: ErrorEvent) => fail(e.message || "the core's worker failed");
}

function send<T>(name: keyof CoreApi, payload: unknown): Promise<T> {
  if (status.state === "error") return Promise.reject(new Error(`core: ${status.detail ?? "not loaded"}`));
  return new Promise<T>((resolve, reject) => {
    const c: Call = { id: nextId++, name, payload };
    pending.set(c.id, { resolve: resolve as (v: unknown) => void, reject });
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
};
