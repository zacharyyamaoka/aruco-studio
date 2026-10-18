// The CoreApi the UI imports. Lane core replaces this stub with the Pyodide
// worker transport; the exported names are part of the contract:
//   core: CoreApi, coreStatus(): CoreStatus, onCoreStatus(cb), useCoreStatus()
import { useSyncExternalStore } from "react";
import type { CoreApi, CoreStatus } from "./contract";

let status: CoreStatus = { state: "loading", detail: "the core is not wired yet" };
const listeners = new Set<() => void>();

export function coreStatus(): CoreStatus { return status; }
export function onCoreStatus(cb: () => void): () => void { listeners.add(cb); return () => listeners.delete(cb); }
export function useCoreStatus(): CoreStatus { return useSyncExternalStore(onCoreStatus, coreStatus); }

const notYet = () => Promise.reject(new Error("core not wired yet (lane core)"));
export const core: CoreApi = {
  info: notYet, presets: notYet, inscribe: notYet, plan: notYet, suggest: notYet, svg: notYet, sheet: notYet,
};
