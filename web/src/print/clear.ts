// The Print dialog's margins and keep-clear boxes (Zach, 2026-11-13: "custom
// spacing margins, top bottom left right, when I go to print ... or perhaps I
// can just draw boxes on the pages that you need to keep clear ... helpful as
// I try to reprint on the same page I have already cut ... it's on a per page
// basis"). The core lays the sheet out round them (web_api.sheet margins_mm,
// keep_clear); this is what the dialog asks for.
//
// Margins: a side typed here replaces the preset's margin_mm on that side (a
// side left out is driven by the preset). Boxes: on one page of one preset's
// sheet (the group's preset id and its 0-based page), in mm from the page's
// top-left, y down -- the core's placements' frame.
//
// Per viewer, never in the document: this browser's localStorage, read and
// written in try/catch (a blocked storage keeps them for the visit), so they
// survive closing the dialog and a reload.
import { create } from "zustand";
import type { KeepClear, SheetRequest } from "../core/contract";

export type Side = "top" | "right" | "bottom" | "left";
export const SIDES: readonly Side[] = ["top", "right", "bottom", "left"];
export type Margins = Partial<Record<Side, number>>;

export interface ClearBox extends KeepClear {
  id: string;
  /** the group's preset id: whose sheet the box is on */
  preset: string;
}

export interface ClearState {
  margins: Margins;
  boxes: ClearBox[];
  /** a side typed (a number) or back to driven (null) */
  setMargin: (side: Side, v: number | null) => void;
  /** -> the new box's id */
  addBox: (b: Omit<ClearBox, "id">) => string;
  updateBox: (id: string, patch: Partial<KeepClear>) => void;
  removeBox: (id: string) => void;
  /** every box on this preset's sheet */
  clearBoxes: (preset: string) => void;
}

/** Where they are kept (this browser only). */
export const CLEAR_KEY = "aruco-studio.print-clear.v1";

const fin = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** What a stored value says, every field checked: junk or a bad box is dropped. */
export function parseClear(raw: string | null | undefined): Pick<ClearState, "margins" | "boxes"> {
  const out: Pick<ClearState, "margins" | "boxes"> = { margins: {}, boxes: [] };
  if (!raw) return out;
  let v: unknown;
  try { v = JSON.parse(raw); } catch { return out; }
  if (!v || typeof v !== "object") return out;
  const o = v as { margins?: Record<string, unknown>; boxes?: unknown };
  for (const s of SIDES) { const m = o.margins?.[s]; if (fin(m) && m >= 0) out.margins[s] = m; }
  if (Array.isArray(o.boxes)) {
    for (const b of o.boxes as Record<string, unknown>[]) {
      if (b && typeof b.id === "string" && typeof b.preset === "string" && Number.isInteger(b.page) && (b.page as number) >= 0
        && fin(b.x_mm) && fin(b.y_mm) && fin(b.w_mm) && fin(b.h_mm) && b.w_mm > 0 && b.h_mm > 0)
        out.boxes.push({ id: b.id, preset: b.preset, page: b.page as number, x_mm: b.x_mm, y_mm: b.y_mm, w_mm: b.w_mm, h_mm: b.h_mm });
    }
  }
  return out;
}

function storage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; }
}

function read(): Pick<ClearState, "margins" | "boxes"> {
  try { return parseClear(storage()?.getItem(CLEAR_KEY)); } catch { return { margins: {}, boxes: [] }; }
}

function write(s: Pick<ClearState, "margins" | "boxes">): void {
  try { storage()?.setItem(CLEAR_KEY, JSON.stringify({ v: 1, margins: s.margins, boxes: s.boxes })); } catch { /* kept for the visit */ }
}

let made = 0;
const newId = () => `k${Date.now().toString(36)}${(made++).toString(36)}`;

export const useClear = create<ClearState>((set) => ({
  ...read(),
  setMargin: (side, v) => set((s) => {
    const margins = { ...s.margins };
    if (v === null) delete margins[side]; else margins[side] = v;
    return { margins };
  }),
  addBox: (b) => {
    const id = newId();
    set((s) => ({ boxes: [...s.boxes, { ...b, id }] }));
    return id;
  },
  updateBox: (id, patch) => set((s) => ({ boxes: s.boxes.map((b) => (b.id === id ? { ...b, ...patch } : b)) })),
  removeBox: (id) => set((s) => ({ boxes: s.boxes.filter((b) => b.id !== id) })),
  clearBoxes: (preset) => set((s) => ({ boxes: s.boxes.filter((b) => b.preset !== preset) })),
}));
useClear.subscribe((s) => write(s));

/** What the sheet request carries for one group: the typed sides only, this
 *  preset's boxes only; nothing when there is nothing (the request stays
 *  what it was before margins and boxes). */
export function clearRequest(margins: Margins, boxes: ClearBox[], preset: string): Pick<SheetRequest, "margins_mm" | "keep_clear"> {
  const out: Pick<SheetRequest, "margins_mm" | "keep_clear"> = {};
  const typed = SIDES.filter((s) => margins[s] !== undefined);
  if (typed.length) out.margins_mm = Object.fromEntries(typed.map((s) => [s, margins[s]]));
  const mine = boxes.filter((b) => b.preset === preset);
  if (mine.length) out.keep_clear = mine.map(({ page, x_mm, y_mm, w_mm, h_mm }) => ({ page, x_mm, y_mm, w_mm, h_mm }));
  return out;
}

/** 0.5 mm steps (a drawn box snaps to them). */
export const snap = (v: number) => Math.round(v * 2) / 2;
