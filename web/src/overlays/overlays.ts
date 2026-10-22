// What the 2D canvas shows besides what prints: the Layers menu in the dock
// (./LayersMenu.tsx), V8 "Overlays menu" of the calm-canvas babble
// (reports/media/studio-ui-cleanup-proposals-2026-10-21.html) with Zach's pick
// of 2026-10-21. One switch per layer -- the sketch's dimensions, the Joint
// Origins, the profile edges, the quiet-zone guides, the rulers -- and the
// background, Miro's View › Grid: Dots | Grid | Blank. Marker info is the
// store's (View › Marker info): the menu switches the same value.
//
// WHY everything on by default, Grid the background (Zach, 2026-10-21: "it's
// important for me to still see things at a glance like the axes location
// etc."): the calm comes from the weights (V1 "Turn it down", Viewport.tsx and
// styles.css), not from hiding; a layer is hidden only when he says so.
// WHY the marker being edited keeps its own (V8: "Its own edit chrome ignores
// the toggles"): its Joint Origin, its profile edge and its guide are where
// the panel's rows act; Viewport.tsx applies that.
//
// Per viewer, never in the document: this browser's localStorage, read and
// written in try/catch (a blocked storage keeps the choice for the visit).
import { create } from "zustand";

/** The canvas behind the sketch (Miro's View › Grid): dots at the grid's points, the grid's lines, or nothing. */
export type Background = "dots" | "grid" | "blank";
export const BACKGROUNDS: readonly Background[] = ["dots", "grid", "blank"];

export interface Overlays {
  background: Background;
  /** the sketch's own dimensions (the marker being edited keeps its own marker dims) */
  dims: boolean;
  /** every marker's Joint Origin: the red / green axes */
  origins: boolean;
  /** the edges of the profiles markers are placed in (a rectangle's dashed box) */
  edges: boolean;
  /** the quiet zone's dashed edge, where the sticker is cut elsewhere (Trim Profile) */
  guides: boolean;
  /** the millimetre rulers along the top and the left */
  rulers: boolean;
}

/** The switches, in the menu's order. */
export type OverlayKey = Exclude<keyof Overlays, "background">;
export const OVERLAY_KEYS: readonly OverlayKey[] = ["dims", "origins", "edges", "guides", "rulers"];

export const OVERLAYS_DEFAULT: Overlays = { background: "grid", dims: true, origins: true, edges: true, guides: true, rulers: true };

/** Where they are kept (this browser only). */
export const OVERLAYS_KEY = "arucoStudio.overlays";

/** What a stored value says, every field checked: junk, a missing field or another version's extra is the default. */
export function parseOverlays(raw: string | null | undefined): Overlays {
  const out: Overlays = { ...OVERLAYS_DEFAULT };
  if (!raw) return out;
  let v: unknown;
  try { v = JSON.parse(raw); } catch { return out; }
  if (!v || typeof v !== "object") return out;
  const o = v as Record<string, unknown>;
  if (BACKGROUNDS.includes(o.background as Background)) out.background = o.background as Background;
  for (const k of OVERLAY_KEYS) if (typeof o[k] === "boolean") out[k] = o[k] as boolean;
  return out;
}

function storage(): Storage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; } catch { return null; }
}

/** This browser's choice (the default when storage is blocked or holds junk). */
export function readOverlays(store: Pick<Storage, "getItem"> | null = storage()): Overlays {
  try { return parseOverlays(store?.getItem(OVERLAYS_KEY)); } catch { return { ...OVERLAYS_DEFAULT }; }
}

/** Keep it; false when this browser will not (the choice then lasts this visit). */
export function writeOverlays(o: Overlays, store: Pick<Storage, "setItem"> | null = storage()): boolean {
  try {
    if (!store) return false;
    store.setItem(OVERLAYS_KEY, JSON.stringify({ v: 1, ...o }));
    return true;
  } catch {
    return false;
  }
}

interface OverlaysStore {
  overlays: Overlays;
  setBackground: (b: Background) => void;
  /** one layer on or off */
  setOverlay: (k: OverlayKey, on: boolean) => void;
}

export const useOverlays = create<OverlaysStore>((set, get) => ({
  overlays: readOverlays(),
  setBackground: (background) => {
    const overlays = { ...get().overlays, background };
    writeOverlays(overlays);
    set({ overlays });
  },
  setOverlay: (k, on) => {
    const overlays = { ...get().overlays, [k]: on };
    writeOverlays(overlays);
    set({ overlays });
  },
}));
