// My presets and the recent list live in this browser's localStorage, every
// read and write wrapped: blocked storage (a private window, a preview)
// leaves the page working with the built-ins only.
import type { Preset } from "../core/contract";

const MINE = "aruco-web.presets.mine";
const RECENT = "aruco-web.presets.recent";

function read<T>(key: string, fallback: T): T {
  try {
    const v = window.localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, v: unknown): void {
  try { window.localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage blocked: kept for this visit only */ }
}

let mine: Preset[] = read<Preset[]>(MINE, []).filter((p) => p && typeof p.id === "string");
let recent: string[] = read<string[]>(RECENT, []);

export function myPresets(): Preset[] { return mine; }
export function recentIds(): string[] { return recent; }

export function saveMine(list: Preset[]): void {
  mine = list.map((p) => ({ ...p, builtin: false }));
  write(MINE, mine);
}

export function touchRecent(id: string): void {
  recent = [id, ...recent.filter((x) => x !== id)].slice(0, 8);
  write(RECENT, recent);
}

/** My presets as a downloadable JSON file. */
export function exportJson(list: Preset[]): string {
  return JSON.stringify({ format: "arucostudio-web-presets", version: 1, presets: list }, null, 2);
}

/** Presets from a file (this format, or a bare list); new ids, never builtin. */
export function importJson(text: string): Preset[] {
  const d = JSON.parse(text);
  const list: unknown[] = Array.isArray(d) ? d : Array.isArray(d?.presets) ? d.presets : [];
  const ok = list.filter((p): p is Preset => !!p && typeof (p as Preset).name === "string"
    && ((p as Preset).method === "inkjet" || (p as Preset).method === "print3d"));
  if (!ok.length) throw new Error("no presets in this file");
  return ok.map((p) => ({ ...p, id: `my:${Math.random().toString(36).slice(2, 10)}`, builtin: false }));
}

/** A new preset of a method, from a built-in of that method when there is one. */
export function blankPreset(method: Preset["method"], base?: Preset): Preset {
  const id = `my:${Math.random().toString(36).slice(2, 10)}`;
  if (base) return { ...base, id, name: `${base.name} (copy)`, builtin: false };
  return method === "inkjet"
    ? { id, name: "My inkjet", method, builtin: false, page: "Letter", page_mm: [215.9, 279.4], margin_mm: 6.35, thickness_mm: 0.1, dpi: 600, min_cell_mm: 1, cell_step_mm: 0 }
    : { id, name: "My 3D printer", method, builtin: false, nozzle_mm: 0.4, line_mm: 0.45, first_line_mm: 0.5, layer_mm: 0.2, first_layer_mm: 0.2,
      bed_mm: [250, 210], min_cell_mm: 1.8, cell_step_mm: 0.45 };
}

/** The numbers a card shows for a preset. */
export function presetNumbers(p: Preset): string {
  if (p.method === "inkjet") {
    return [p.page, p.dpi ? `${p.dpi} dpi` : null, p.thickness_mm ? `${p.thickness_mm} mm` : null].filter(Boolean).join(" · ");
  }
  return [p.nozzle_mm ? `nozzle ${p.nozzle_mm}` : null, p.line_mm ? `lines ${p.line_mm}` : null, p.layer_mm ? `layer ${p.layer_mm}` : null]
    .filter(Boolean).join(" · ");
}

/** Equal as presets go (the fields, not the object). */
export function samePreset(a: Preset | null | undefined, b: Preset | null | undefined): boolean {
  if (!a || !b) return false;
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) if (JSON.stringify((a as never)[k]) !== JSON.stringify((b as never)[k])) return false;
  return true;
}
