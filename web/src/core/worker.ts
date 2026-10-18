// The Python core in a module Web Worker (docs/design/online_studio_v1.md):
// Pyodide self-hosted under <base>pyodide/ (copied there by
// scripts/pack-core.mjs), the core unpacked from <base>py/aruco_studio.zip,
// and every CoreApi call answered by aruco_studio.web_api.call(name, json).
//
// In:  {id, name, payload}             name: a CoreApi call, payload: its JSON arguments
// Out: {kind: "ready", ms, version}    once, when the core imported
//      {kind: "error", detail}         once, when it could not load
//      {id, result} | {id, error}      per call

interface WebApi { call(name: string, payload: string): string }
interface Pyodide {
  version: string;
  unpackArchive(buffer: ArrayBuffer, format: string, options?: { extractDir?: string }): void;
  runPython(code: string): unknown;
  pyimport(name: string): WebApi;
}
type LoadPyodide = (options: { indexURL: string }) => Promise<Pyodide>;

const ctx = self as unknown as DedicatedWorkerGlobalScope;
const LIB = "/lib/aruco_studio";
const url = (p: string) => new URL(`${import.meta.env.BASE_URL}${p}`, ctx.location.href).href;

async function boot(): Promise<WebApi> {
  const t0 = performance.now();
  // WHY a runtime import of the copied file, not `import "pyodide"`: the
  // runtime stays one self-hosted folder (pyodide.mjs next to its wasm and
  // stdlib), and Vite never bundles Pyodide's Node branches.
  const { loadPyodide } = (await import(/* @vite-ignore */ url("pyodide/pyodide.mjs"))) as { loadPyodide: LoadPyodide };
  const py = await loadPyodide({ indexURL: url("pyodide/") });
  const res = await fetch(url("py/aruco_studio.zip"));
  if (!res.ok) throw new Error(`py/aruco_studio.zip: HTTP ${res.status}`);
  py.unpackArchive(await res.arrayBuffer(), "zip", { extractDir: LIB });
  py.runPython(`import sys\nif ${JSON.stringify(LIB)} not in sys.path:\n    sys.path.insert(0, ${JSON.stringify(LIB)})`);
  const api = py.pyimport("aruco_studio.web_api");
  ctx.postMessage({ kind: "ready", ms: Math.round(performance.now() - t0), version: py.version });
  return api;
}

const ready = boot();
ready.catch((e: unknown) => ctx.postMessage({ kind: "error", detail: e instanceof Error ? e.message : String(e) }));

ctx.onmessage = async (e: MessageEvent<{ id: number; name: string; payload: unknown }>) => {
  const { id, name, payload } = e.data;
  try {
    const api = await ready;
    const out = JSON.parse(api.call(name, JSON.stringify(payload ?? {}))) as { result?: unknown; error?: string };
    if (out.error !== undefined) ctx.postMessage({ id, error: out.error });
    else ctx.postMessage({ id, result: out.result ?? null });
  } catch (err) {
    ctx.postMessage({ id, error: err instanceof Error ? err.message : String(err) });
  }
};
