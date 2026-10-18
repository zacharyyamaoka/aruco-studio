// The document: one sketch (closed shapes, ../sketch/model.ts) and at most
// one ArUco Extrude feature, with the preset it is made by. Pure: the store
// (../store.ts) calls these; vitest covers them. Saved as
// `.arucostudio-web.json` (format "arucostudio-web", version 1).
import type { LabelParams, MarkerParams, MarkerType, PlanRequest, Preset, Suggestion, Turn } from "../core/contract";
import { rectOf, type ProfileRef, type RectShape, type Shape } from "../sketch/model";

export type Holes = "avoid" | "ignore";

/** The ArUco Extrude feature: the marker rectangle it fills, the profile it
 *  came from (the reference face: Flip does not apply), the marker's and the
 *  label's numbers. */
export interface Feature {
  rectId: string | null;
  profile: ProfileRef | null;
  holes: Holes;
  marker: MarkerParams;
  label: LabelParams;
}

export interface Doc {
  format: "arucostudio-web";
  version: 1;
  name: string;
  shapes: Shape[];
  feature: Feature | null;
  preset: Preset | null;
}

export const DEFAULT_MARKER: MarkerParams = {
  type: "single", dictionary: "DICT_4X4_50", first_id: 0, auto: true, marker_mm: 30, checker_mm: 0, separation_mm: 0,
  cols: 1, rows: 1, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none",
};

export const DEFAULT_LABEL: LabelParams = {
  on: true, text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0],
};

export function newFeature(rectId: string | null, profile: ProfileRef | null): Feature {
  return { rectId, profile, holes: "avoid", marker: { ...DEFAULT_MARKER }, label: { ...DEFAULT_LABEL, offset_mm: [0, 0] } };
}

export function emptyDoc(name = "Untitled", shapes: Shape[] = [], preset: Preset | null = null): Doc {
  return { format: "arucostudio-web", version: 1, name, shapes, feature: null, preset };
}

let seq = 0;
export function newId(prefix = "s"): string {
  seq += 1;
  return `${prefix}${Date.now().toString(36)}${seq}`;
}

// ------------------------------------------------------------ shapes

export function addShape(doc: Doc, s: Shape): Doc {
  return { ...doc, shapes: [...doc.shapes, s] };
}

export function setShape(doc: Doc, s: Shape): Doc {
  return { ...doc, shapes: doc.shapes.map((x) => (x.id === s.id ? s : x)) };
}

/** Delete a shape; the feature that fills it loses its rectangle, and a
 *  profile that named it is no longer its reference. */
export function deleteShape(doc: Doc, id: string): Doc {
  let feature = doc.feature;
  if (feature && feature.rectId === id) feature = { ...feature, rectId: null };
  if (feature?.profile && (feature.profile.outer === id || feature.profile.holes.includes(id))) feature = { ...feature, profile: null };
  return { ...doc, shapes: doc.shapes.filter((x) => x.id !== id), feature };
}

export function featureRect(doc: Doc): RectShape | null {
  const id = doc.feature?.rectId;
  const s = id ? doc.shapes.find((r) => r.id === id) : null;
  return s && s.kind === "rect" ? s : null;
}

// ------------------------------------------------------------ the marker's numbers

/** One marker field set from the panel. Typing a size turns Auto off (the
 *  typed size is drawn as typed, never clamped: the plan flags overflow). */
export function setMarker(m: MarkerParams, key: keyof MarkerParams, value: unknown): MarkerParams {
  if (key === "type") return setType(m, value as MarkerType);
  const next = { ...m, [key]: value } as MarkerParams;
  if (key === "marker_mm" || key === "checker_mm") next.auto = false;
  return next;
}

/** Switching the type keeps what still makes sense: a grid starts 2 × 2,
 *  ChArUco 5 × 4 squares, a single marker is 1 × 1; the size goes back to Auto. */
export function setType(m: MarkerParams, type: MarkerType): MarkerParams {
  if (type === m.type) return m;
  const grid = type === "grid" ? [Math.max(m.cols, 2), Math.max(m.rows, 2)] : type === "charuco" ? [5, 4] : [1, 1];
  return { ...m, type, cols: grid[0], rows: grid[1], auto: true, checker_mm: 0, separation_mm: type === "grid" ? m.separation_mm : 0 };
}

/** A picked suggestion sets its numbers and turns Auto off. */
export function pickSuggestion(m: MarkerParams, s: Suggestion): MarkerParams {
  return { ...m, ...s.params, auto: false };
}

export function nextTurn(t: Turn): Turn {
  return ((t + 90) % 360) as Turn;
}

/** How many ids the feature uses (single 1, grid cols × rows, ChArUco the
 *  white squares: half the squares, rounded down). */
export function idCount(m: MarkerParams): number {
  if (m.type === "single") return 1;
  if (m.type === "grid") return m.cols * m.rows;
  return Math.floor((m.cols * m.rows) / 2);
}

/** "#0" or "#0–5": the plan's ids when there is one, else the count's. */
export function idRange(m: MarkerParams, ids?: number[]): string {
  if (ids && ids.length) return ids.length === 1 ? `#${ids[0]}` : `#${ids[0]}–${ids[ids.length - 1]}`;
  const n = idCount(m);
  return n <= 1 ? `#${m.first_id}` : `#${m.first_id}–${m.first_id + n - 1}`;
}

// ------------------------------------------------------------ the request

export function planRequest(doc: Doc): PlanRequest | null {
  const r = featureRect(doc);
  if (!doc.feature || !r || !doc.preset) return null;
  return {
    rect: rectOf(r), marker: doc.feature.marker, label: doc.feature.label, preset: doc.preset,
    reference_face: !!doc.feature.profile,
  };
}

// ------------------------------------------------------------ the file

export function serialise(doc: Doc): string {
  return JSON.stringify(doc, null, 2);
}

/** Read a saved file; throws with a readable reason when it is not one. */
export function parseDoc(text: string): Doc {
  const d = JSON.parse(text);
  if (!d || d.format !== "arucostudio-web") throw new Error("not an .arucostudio-web.json file");
  if (d.version !== 1) throw new Error(`file version ${d.version}: this Studio reads version 1`);
  const shapes: Shape[] = Array.isArray(d.shapes) ? d.shapes.filter((s: Shape) => s && ["rect", "circle", "poly"].includes(s.kind)) : [];
  return {
    format: "arucostudio-web", version: 1, name: String(d.name ?? "Untitled"), shapes, preset: d.preset ?? null,
    feature: d.feature ? {
      ...newFeature(null, null), ...d.feature,
      marker: { ...DEFAULT_MARKER, ...d.feature.marker }, label: { ...DEFAULT_LABEL, ...d.feature.label },
    } : null,
  };
}
