// The document: one sketch (closed shapes, ../sketch/model.ts) and any number
// of ArUco Extrude features, with the preset they are made by. Pure: the
// store (../store.ts) calls these; vitest covers them. Saved as
// `.arucostudio-web.json` (format "arucostudio-web", version 2; a version 1
// file, which held one feature, is migrated on open).
import type { IdItem, LabelParams, MarkerParams, MarkerType, PlanRequest, Preset, Suggestion, Turn } from "../core/contract";
import { rectOf, type ProfileRef, type RectShape, type Shape } from "../sketch/model";

export type Holes = "avoid" | "ignore";

/** An ArUco Extrude feature: the marker rectangle it fills, the profile it
 *  came from (the reference face: Flip does not apply), the marker's and the
 *  label's numbers, and which of them were set by hand. */
export interface Feature {
  /** made once, never changes, saved in the file */
  id: string;
  /** the stable key auto id hashes (IdItem.key); the id by default */
  key: string;
  rectId: string | null;
  profile: ProfileRef | null;
  holes: Holes;
  marker: MarkerParams;
  label: LabelParams;
  /** the fields typed by hand among those the contract has no driven
   *  encoding for ("marker.cols", "label.gap_mm", ...). The rest say it in
   *  their own value: see isSet(). */
  set: string[];
}

export interface Doc {
  format: "arucostudio-web";
  version: 2;
  name: string;
  shapes: Shape[];
  features: Feature[];
  /** auto id: key -> the first id already given out (IdRequest.ledger) */
  id_ledger: Record<string, number>;
  preset: Preset | null;
}

export const DOC_VERSION = 2;

export const DEFAULT_MARKER: MarkerParams = {
  type: "single", dictionary: "DICT_4X4_50", first_id: 0, auto: true, marker_mm: 30, checker_mm: 0, separation_mm: 0,
  cols: 1, rows: 1, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none",
};

export const DEFAULT_LABEL: LabelParams = {
  on: true, text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0],
};

let seq = 0;
export function newId(prefix = "s"): string {
  seq += 1;
  return `${prefix}${Date.now().toString(36)}${seq}`;
}

export function newFeature(rectId: string | null, profile: ProfileRef | null, id = newId("f")): Feature {
  return {
    id, key: id, rectId, profile, holes: "avoid", marker: { ...DEFAULT_MARKER }, label: { ...DEFAULT_LABEL, offset_mm: [0, 0] }, set: [],
  };
}

export function emptyDoc(name = "Untitled", shapes: Shape[] = [], preset: Preset | null = null): Doc {
  return { format: "arucostudio-web", version: 2, name, shapes, features: [], id_ledger: {}, preset };
}

// ------------------------------------------------------------ shapes

export function addShape(doc: Doc, s: Shape): Doc {
  return { ...doc, shapes: [...doc.shapes, s] };
}

export function setShape(doc: Doc, s: Shape): Doc {
  return { ...doc, shapes: doc.shapes.map((x) => (x.id === s.id ? s : x)) };
}

/** Delete a shape; a feature that fills it goes with it (a feature is
 *  reached by clicking its marker: one without a rectangle could not be),
 *  and a profile that named it is no longer a reference. */
export function deleteShape(doc: Doc, id: string): Doc {
  const features = doc.features.filter((f) => f.rectId !== id).map((f) =>
    f.profile && (f.profile.outer === id || f.profile.holes.includes(id)) ? { ...f, profile: null } : f);
  return { ...doc, shapes: doc.shapes.filter((x) => x.id !== id), features };
}

// ------------------------------------------------------------ features

export function getFeature(doc: Doc, id: string | null | undefined): Feature | null {
  return (id && doc.features.find((f) => f.id === id)) || null;
}

/** The feature that fills a rectangle, if any. */
export function featureOfRect(doc: Doc, rectId: string): Feature | null {
  return doc.features.find((f) => f.rectId === rectId) ?? null;
}

export function addFeature(doc: Doc, f: Feature): Doc {
  return { ...doc, features: [...doc.features, f] };
}

export function setFeature(doc: Doc, f: Feature): Doc {
  return { ...doc, features: doc.features.map((x) => (x.id === f.id ? f : x)) };
}

/** Edit one feature by id (a no-op when it is gone). */
export function updateFeature(doc: Doc, id: string | null | undefined, fn: (f: Feature) => Feature): Doc {
  const f = getFeature(doc, id);
  return f ? setFeature(doc, fn(f)) : doc;
}

/** Remove a feature; its rectangle stays in the sketch. */
export function removeFeature(doc: Doc, id: string): Doc {
  return { ...doc, features: doc.features.filter((f) => f.id !== id) };
}

/** A feature's number: "ArUco Extrude 2" (1-based, in the order made). */
export function featureNumber(doc: Doc, id: string): number {
  return doc.features.findIndex((f) => f.id === id) + 1;
}

export function featureRect(doc: Doc, f: Feature | null): RectShape | null {
  const id = f?.rectId;
  const s = id ? doc.shapes.find((r) => r.id === id) : null;
  return s && s.kind === "rect" ? s : null;
}

// ------------------------------------------------------------ driven vs set
//
// WHY (Zach, 2026-10-18): "instead of showing like auto, just show the actual
// value but make it kinda like grey outed that indicates that its like being
// driven as supposed to having been set" -- the driven / driving pattern of
// Fusion's and SolidWorks' driven dimensions. Every row is either driven
// (the core computes it, or it is the default) or set (typed). The contract
// already encodes four of them; the rest are listed in Feature.set.

/** The fields whose driven state the contract's own value encodes. */
const ENCODED: Record<string, (f: Feature) => boolean> = {
  "marker.marker_mm": (f) => !f.marker.auto,           // driven = auto: true
  "marker.checker_mm": (f) => f.marker.checker_mm > 0,  // driven = 0
  "marker.separation_mm": (f) => f.marker.separation_mm > 0,
  "label.height_mm": (f) => f.label.height_mm > 0,
};

/** The fields a row can set that the contract has no driven encoding for. */
export const LISTED = [
  "marker.type", "marker.dictionary", "marker.first_id", "marker.cols", "marker.rows", "marker.turn", "marker.flip",
  "marker.corner_mark", "label.on", "label.side", "label.gap_mm",
] as const;

export function isSet(f: Feature, path: string): boolean {
  const enc = ENCODED[path];
  return enc ? enc(f) : f.set.includes(path);
}

/** The driven value of a listed field: the default (cols / rows: the type's). */
export function drivenValue(m: MarkerParams, path: string): unknown {
  if (path === "marker.cols") return typeCounts(m.type)[0];
  if (path === "marker.rows") return typeCounts(m.type)[1];
  const [part, key] = path.split(".") as ["marker" | "label", string];
  return part === "marker" ? DEFAULT_MARKER[key as keyof MarkerParams] : DEFAULT_LABEL[key as keyof LabelParams];
}

/** A grid starts 2 × 2, ChArUco 5 × 4 squares, a single marker is 1 × 1. */
export function typeCounts(type: MarkerType): [number, number] {
  return type === "grid" ? [2, 2] : type === "charuco" ? [5, 4] : [1, 1];
}

const mark = (set: string[], path: string) => (set.includes(path) ? set : [...set, path]);
const unmark = (set: string[], paths: string[]) => set.filter((p) => !paths.includes(p));

/** Set one field by hand (typed, picked, or a suggestion). Typing a size
 *  turns auto off; the typed size is drawn as typed, never clamped (the plan
 *  flags overflow). */
export function setField(f: Feature, path: string, value: unknown): Feature {
  const [part, key] = path.split(".") as ["marker" | "label", string];
  if (part === "label") {
    return { ...f, label: { ...f.label, [key]: value }, set: (LISTED as readonly string[]).includes(path) ? mark(f.set, path) : f.set };
  }
  if (key === "type") {
    // a new type starts over: its size, counts, checker and separation are driven again
    const marker = setType(f.marker, value as MarkerType);
    return { ...f, marker, set: marker === f.marker ? mark(f.set, path) : mark(unmark(f.set, ["marker.cols", "marker.rows"]), path) };
  }
  const marker = setMarker(f.marker, key as keyof MarkerParams, value);
  return { ...f, marker, set: (LISTED as readonly string[]).includes(path) ? mark(f.set, path) : f.set };
}

/** Back to driven: auto on / 0 for the encoded fields, the default for the rest. */
export function resetField(f: Feature, path: string): Feature {
  if (path === "marker.marker_mm") return { ...f, marker: { ...f.marker, auto: true } };
  if (path === "marker.checker_mm") return { ...f, marker: { ...f.marker, checker_mm: 0 } };
  if (path === "marker.separation_mm") return { ...f, marker: { ...f.marker, separation_mm: 0 } };
  if (path === "label.height_mm") return { ...f, label: { ...f.label, height_mm: 0 } };
  const [part, key] = path.split(".") as ["marker" | "label", string];
  const set = unmark(f.set, [path]);
  if (part === "label") return { ...f, label: { ...f.label, [key]: drivenValue(f.marker, path) }, set };
  if (key === "type") {
    const marker = setType(f.marker, DEFAULT_MARKER.type);
    return { ...f, marker, set: marker === f.marker ? set : unmark(set, ["marker.cols", "marker.rows"]) };
  }
  return { ...f, marker: { ...f.marker, [key]: drivenValue(f.marker, path) }, set };
}

/** A picked suggestion sets its numbers (the size, and the counts of a grid
 *  or a board; a checker or separation of 0 stays driven). */
export function pickSuggestion(f: Feature, s: Suggestion): Feature {
  const marker = { ...f.marker, ...s.params, auto: false };
  const set = f.marker.type === "single" ? f.set : mark(mark(f.set, "marker.cols"), "marker.rows");
  return { ...f, marker, set };
}

// ------------------------------------------------------------ the marker's numbers

/** One marker value. A typed size turns auto off (the size is set). */
export function setMarker(m: MarkerParams, key: keyof MarkerParams, value: unknown): MarkerParams {
  if (key === "type") return setType(m, value as MarkerType);
  const next = { ...m, [key]: value } as MarkerParams;
  if (key === "marker_mm") next.auto = false;
  return next;
}

/** Switching the type starts the new type over: its counts (a grid 2 × 2,
 *  ChArUco 5 × 4 squares, a single 1 × 1), the size, checker and separation
 *  are driven again. */
export function setType(m: MarkerParams, type: MarkerType): MarkerParams {
  if (type === m.type) return m;
  const [cols, rows] = typeCounts(type);
  return { ...m, type, cols, rows, auto: true, checker_mm: 0, separation_mm: 0 };
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

// ------------------------------------------------------------ the requests

export function planRequest(doc: Doc, f: Feature | null): PlanRequest | null {
  const r = featureRect(doc, f);
  if (!f || !r || !doc.preset) return null;
  return {
    rect: rectOf(r), marker: f.marker, label: f.label, preset: doc.preset,
    reference_face: !!f.profile,
  };
}

/** Print's sheet: one item per feature that plans, in the order made. */
export function sheetItems(doc: Doc): PlanRequest[] {
  return doc.features.map((f) => planRequest(doc, f)).filter((r): r is PlanRequest => !!r);
}

/** Auto id's input (core.assign_ids): a typed first id is kept, a driven one is null. */
export function idItems(doc: Doc): IdItem[] {
  return doc.features.map((f) => ({
    key: f.key, type: f.marker.type, dictionary: f.marker.dictionary, count: idCount(f.marker),
    first_id: isSet(f, "marker.first_id") ? f.marker.first_id : null,
  }));
}

// ------------------------------------------------------------ the file

export function serialise(doc: Doc): string {
  return JSON.stringify(doc, null, 2);
}

/** A saved feature with what it lacks filled in from the defaults. */
function readFeature(raw: Record<string, unknown>): Feature {
  const base = newFeature(null, null, typeof raw.id === "string" && raw.id ? raw.id : undefined);
  const f: Feature = {
    ...base, ...raw,
    marker: { ...DEFAULT_MARKER, ...(raw.marker as object) }, label: { ...DEFAULT_LABEL, ...(raw.label as object) },
  } as Feature;
  if (typeof f.key !== "string" || !f.key) f.key = f.id;
  if (!Array.isArray(f.set)) f.set = [];
  return f;
}

/** Version 1 held at most one feature, and no set / driven record: a listed
 *  field that differs from its driven value was typed, so it is set. */
export function migrateV1(d: Record<string, unknown>): Record<string, unknown> {
  const old = d.feature as Record<string, unknown> | null | undefined;
  let features: Feature[] = [];
  if (old) {
    const f = readFeature(old);
    f.set = LISTED.filter((p) => {
      const [part, key] = p.split(".") as ["marker" | "label", string];
      const v = part === "marker" ? f.marker[key as keyof MarkerParams] : f.label[key as keyof LabelParams];
      return JSON.stringify(v) !== JSON.stringify(drivenValue(f.marker, p));
    });
    features = [f];
  }
  const { feature: _gone, ...rest } = d;
  return { ...rest, version: 2, features, id_ledger: {} };
}

/** Read a saved file; throws with a readable reason when it is not one. */
export function parseDoc(text: string): Doc {
  let d = JSON.parse(text);
  if (!d || d.format !== "arucostudio-web") throw new Error("not an .arucostudio-web.json file");
  if (d.version === 1) d = migrateV1(d);
  if (d.version !== DOC_VERSION) throw new Error(`file version ${d.version}: this Studio reads versions 1 and ${DOC_VERSION}`);
  const shapes: Shape[] = Array.isArray(d.shapes) ? d.shapes.filter((s: Shape) => s && ["rect", "circle", "poly"].includes(s.kind)) : [];
  const features: Feature[] = Array.isArray(d.features) ? d.features.filter((f: unknown) => f && typeof f === "object").map(readFeature) : [];
  const ledger = d.id_ledger && typeof d.id_ledger === "object" ? d.id_ledger as Record<string, number> : {};
  return {
    format: "arucostudio-web", version: 2, name: String(d.name ?? "Untitled"), shapes, features, id_ledger: ledger, preset: d.preset ?? null,
  };
}
