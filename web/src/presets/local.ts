// My presets and the recent list live in this browser's localStorage, every
// read and write wrapped: blocked storage (a private window, a preview)
// leaves the page working with the built-ins only.
import type { Preset } from "../core/contract";

const MINE = "aruco-web.presets.mine";
const RECENT = "aruco-web.presets.recent";
// cleanPreset's fields (declared before `mine` is read, below)
const NUMS = ["margin_mm", "thickness_mm", "dpi", "nozzle_mm", "line_mm", "first_line_mm", "layer_mm", "first_layer_mm",
  "min_cell_mm", "cell_step_mm"] as const;
const PAIRS = ["page_mm", "bed_mm"] as const;
const PAGE_NAME = /^[A-Za-z0-9 ._()-]{1,32}$/;

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

// WHY cleaned on read too: a preset kept here before import was validated
// (review finding #1, 2026-10-21) can hold anything; one that fails is dropped.
const kept = read<unknown>(MINE, []);
let mine: Preset[] = (Array.isArray(kept) ? kept : []).flatMap((p, i) => {
  try {
    const id = (p as Preset)?.id;
    return typeof id === "string" ? [{ ...cleanPreset(p, `preset ${i + 1}`), id }] : [];
  } catch {
    return [];
  }
});
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

/** Presets from a file (this format, or a bare list); new ids, never builtin.
 *  Every field is checked (cleanPreset): one bad preset refuses the file. */
export function importJson(text: string): Preset[] {
  const d = JSON.parse(text);
  const list: unknown[] = Array.isArray(d) ? d : Array.isArray(d?.presets) ? d.presets : [];
  if (!list.length) throw new Error("no presets in this file");
  return list.map((p, i) => ({ ...cleanPreset(p, `preset ${i + 1}`), id: `my:${Math.random().toString(36).slice(2, 10)}`, builtin: false }));
}

/** A preset from untrusted data (a file, this browser's storage): only the
 *  contract's fields, each of its type, or an Error naming `where` and the
 *  field. The id is "" (the caller gives one); null is an unset field. */
export function cleanPreset(raw: unknown, where: string): Preset {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error(`${where} is not a preset`);
  const r = raw as Record<string, unknown>;
  const bad = (field: string, want: string) => new Error(`${where}${typeof r.name === "string" ? ` ("${r.name.slice(0, 40)}")` : ""}: ${field} must be ${want}`);
  if (typeof r.name !== "string" || !r.name.trim() || r.name.length > 120) throw bad("name", "text of 1-120 characters");
  if (r.method !== "inkjet" && r.method !== "print3d") throw bad("method", "\"inkjet\" or \"print3d\"");
  const out: Preset = { id: "", name: r.name, method: r.method, builtin: false };
  const num = (v: unknown) => typeof v === "number" && Number.isFinite(v) && v >= 0 && v < 1e5;
  if (r.page != null) {
    if (typeof r.page !== "string" || !PAGE_NAME.test(r.page)) throw bad("page", "a paper name (letters, digits, spaces)");
    out.page = r.page;
  }
  for (const k of NUMS) {
    if (r[k] == null) continue;
    if (!num(r[k])) throw bad(k, "a number of 0 or more");
    out[k] = r[k] as number;
  }
  for (const k of PAIRS) {
    if (r[k] == null) continue;
    const v = r[k];
    if (!Array.isArray(v) || v.length !== 2 || !v.every((x) => num(x) && x > 0)) throw bad(k, "two numbers above 0 (width, height)");
    out[k] = [v[0], v[1]];
  }
  if (r.size_step != null) {
    const st = r.size_step as Record<string, unknown>;
    if (st?.of === "dots" || st?.of === "line") out.size_step = { of: st.of };
    else if (st?.of === "mm" && num(st.mm) && (st.mm as number) > 0) out.size_step = { of: "mm", mm: st.mm as number };
    else throw bad("size_step", "{of: \"dots\"}, {of: \"line\"} or {of: \"mm\", mm: a number above 0}");
  }
  return out;
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
