// Which core the UI talks to: the real one (web/src/core/client.ts, the
// Pyodide worker) by default, the mock (web/src/dev/mockCore.ts) with
// ?core=mock. Every call is counted, so the test probe's idle() can wait
// until nothing is in flight. The UI imports `core` and `useCoreStatus`
// from here and nothing else of the core's.
import { useSyncExternalStore } from "react";
import type { CoreApi, CoreStatus } from "./core/contract";

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

// WHY a dynamic import per kind: the mock must not boot Pyodide, and the
// real build must not ship the mock in its main chunk.
const source: Promise<CoreApi> = coreKind === "mock"
  ? import("./dev/mockCore").then((m) => m.createMockCore(() => setStatus({ state: "ready", detail: "mock core", ms: Math.round(performance.now() - t0) })))
  : import("./core/client").then((m) => {
    const sync = () => setStatus(m.coreStatus());
    m.onCoreStatus(sync);
    sync();
    return m.core;
  });

let inflight = 0;
const idleWaiters = new Set<() => void>();
export function callsInFlight(): number { return inflight; }
export function onCallsSettled(cb: () => void): () => void { idleWaiters.add(cb); return () => { idleWaiters.delete(cb); }; }

function counted<K extends keyof CoreApi>(name: K): CoreApi[K] {
  return (async (...args: unknown[]) => {
    inflight += 1;
    try {
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
};
