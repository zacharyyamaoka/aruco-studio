// What the presets modal shows and filters, as data: the Info rows of each
// method (every field of the contract's Preset that method uses), the left
// bar's chips and the search. Pure, so the modal stays layout only.
import type { Preset, Vec2 } from "../core/contract";
import { presetNumbers } from "./local";

export const PAGES: Record<string, Vec2> = { Letter: [215.9, 279.4], A4: [210, 297], A3: [297, 420], A5: [148, 210], Legal: [215.9, 355.6] };

export type NumKey = "margin_mm" | "thickness_mm" | "dpi" | "nozzle_mm" | "line_mm" | "first_line_mm" | "layer_mm"
  | "first_layer_mm" | "min_cell_mm" | "cell_step_mm";

/** One Info row: a number, a width × height pair, or the paper's name. */
export type InfoRow =
  | { kind: "num"; key: NumKey; label: string; unit: string; int?: boolean; step: number; hint?: string }
  | { kind: "pair"; key: "page_mm" | "bed_mm"; label: string; unit: string }
  | { kind: "page"; key: "page"; label: string };

const BOTH: InfoRow[] = [
  { kind: "num", key: "min_cell_mm", label: "Min cell", unit: "mm", step: 0.05, hint: "the smallest cell this machine makes well" },
  { kind: "num", key: "cell_step_mm", label: "Cell step", unit: "mm", step: 0.005, hint: "cells snap to multiples of this; 0 = no snap" },
];

/** The Info rows of a method, in the order the panel shows them. */
export function infoRows(method: Preset["method"]): InfoRow[] {
  return method === "inkjet"
    ? [
      { kind: "page", key: "page", label: "Paper" },
      { kind: "pair", key: "page_mm", label: "Page", unit: "mm" },
      { kind: "num", key: "margin_mm", label: "Margin", unit: "mm", step: 0.05, hint: "unprintable margin on every side" },
      { kind: "num", key: "thickness_mm", label: "Thickness", unit: "mm", step: 0.01, hint: "paper / vinyl thickness" },
      { kind: "num", key: "dpi", label: "Resolution", unit: "dpi", int: true, step: 1 },
      ...BOTH,
    ]
    : [
      { kind: "num", key: "nozzle_mm", label: "Nozzle", unit: "mm", step: 0.05 },
      { kind: "num", key: "line_mm", label: "Line width", unit: "mm", step: 0.01, hint: "line (extrusion) width" },
      { kind: "num", key: "first_line_mm", label: "First line", unit: "mm", step: 0.01, hint: "first-layer line width (sizes the cells when printed face down)" },
      { kind: "num", key: "layer_mm", label: "Layer", unit: "mm", step: 0.01 },
      { kind: "num", key: "first_layer_mm", label: "First layer", unit: "mm", step: 0.01 },
      { kind: "pair", key: "bed_mm", label: "Bed", unit: "mm" },
      ...BOTH,
    ];
}

export function methodName(m: Preset["method"]): string {
  return m === "inkjet" ? "Inkjet" : "3D print";
}

export interface Filters { method: string[]; paper: string[]; nozzle: string[] }
export const NO_FILTERS: Filters = { method: [], paper: [], nozzle: [] };

export function nozzleChip(p: Preset): string | undefined {
  return p.nozzle_mm ? `${p.nozzle_mm} mm` : undefined;
}

/** The left bar's chips: each value some preset has, in first-seen order. */
export function chipValues(all: Preset[]): Filters {
  const uniq = (xs: (string | undefined)[]) => [...new Set(xs.filter((x): x is string => !!x))];
  return { method: uniq(all.map((p) => methodName(p.method))), paper: uniq(all.map((p) => p.page)), nozzle: uniq(all.map(nozzleChip)) };
}

/** The cards a search and the chips leave (chips of one kind OR, kinds AND). */
export function filterPresets(list: Preset[], search: string, f: Filters): Preset[] {
  const q = search.trim().toLowerCase();
  return list.filter((p) => {
    if (q && !`${p.name} ${methodName(p.method)} ${presetNumbers(p)}`.toLowerCase().includes(q)) return false;
    if (f.method.length && !f.method.includes(methodName(p.method))) return false;
    if (f.paper.length && !(p.page && f.paper.includes(p.page))) return false;
    if (f.nozzle.length && !f.nozzle.includes(nozzleChip(p) ?? "")) return false;
    return true;
  });
}

/** A preset with one Info row changed: a named paper sets the page size,
 *  a typed page size that is not the named paper's makes it "Custom". */
export function withField(p: Preset, key: keyof Preset, value: unknown): Preset {
  if (key === "page" && typeof value === "string") return { ...p, page: value, page_mm: PAGES[value] ?? p.page_mm };
  if (key === "page_mm" && Array.isArray(value)) {
    const named = p.page ? PAGES[p.page] : undefined;
    const same = !!named && named[0] === value[0] && named[1] === value[1];
    return { ...p, page_mm: value as Vec2, page: same ? p.page : "Custom" };
  }
  return { ...p, [key]: value };
}
