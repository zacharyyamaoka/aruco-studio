// The document: one sketch (closed shapes, ../sketch/model.ts) and any number
// of ArUco Extrude features, with the preset they are made by. Pure: the
// store (../store.ts) calls these; vitest covers them. Saved as
// `.arucostudio-web.json` (format "arucostudio-web", version 3; a version 1
// file, which held one feature, and a version 2 file, whose features filled
// a rectangle, are migrated on open).
//
// WHY a feature references a PROFILE (Zach, 2026-10-20 evening: "if we just
// have the idea of a profile, and you want a custom location, then you draw a
// rectangle profile … it's just going to be a profile"): the core places the
// marker in the profile, like an extrude; a rectangle profile is used exactly
// (contract.ts PlanRequest, barrier 9).
import type { ExtrudeParams, IdItem, IdRequest, IdResult, LabelParams, MarkerParams, MarkerType, PlanRequest, Preset, Suggestion, Trim, Turn } from "../core/contract";
import { dimShapes, type SketchDim } from "../sketch/constraints";
import { plainRect, profileLoops, sameProfile, type ProfileRef, type RectShape, type Shape } from "../sketch/model";

export type Holes = "avoid" | "ignore";

/** An ArUco Extrude feature: the profile the core places its marker in (a
 *  region's outer shape and its holes, or a rectangle alone: the custom
 *  placement), the marker's and the label's numbers, and which of them were
 *  set by hand. */
export interface Feature {
  /** made once, never changes, saved in the file */
  id: string;
  /** the stable key auto id hashes (IdItem.key); the id by default */
  key: string;
  /** null only while the panel waits for one: OK without a profile makes nothing */
  profile: ProfileRef | null;
  /** the profile's holes: the marker keeps off them ("avoid") or not */
  holes: Holes;
  /** what the sticker is cut to (contract Trim): the profile by default,
   *  driven until set ("trim" in `set`) */
  trim: Trim;
  marker: MarkerParams;
  label: LabelParams;
  /** the heights (contract barrier 10): ONLY the fields set by hand are present;
   *  an absent one is driven from the preset (the plan's MarkerPlan.extrude says
   *  its value). The Make tab's rows and the 3D view's drag arrows both write it
   *  through setField("extrude.<key>") / resetField. */
  extrude: ExtrudeParams;
  /** the fields typed by hand among those the contract has no driven
   *  encoding for ("marker.cols", "label.gap_mm", ...). The rest say it in
   *  their own value: see isSet(). */
  set: string[];
}

export interface Doc {
  format: "arucostudio-web";
  version: 3;
  name: string;
  shapes: Shape[];
  /** the sketch's driving dimensions (D; ../sketch/constraints.ts): a file
   *  from before them has none */
  dims: SketchDim[];
  features: Feature[];
  /** auto id: key -> the first id already given out (IdRequest.ledger) */
  id_ledger: Record<string, number>;
  preset: Preset | null;
}

export const DOC_VERSION = 3;

export const TRIMS: readonly Trim[] = ["profile", "marker"];
// WHY profile (Zach, 2026-10-20 evening): "there is no longer trim to rectangle.
// If you want trim to rectangle then just make your profile a rectangle and trim
// to profile!" An old "rectangle" reads as "profile" (readFeature).
export const DEFAULT_TRIM: Trim = "profile";

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

/** A rectangle on its own as a profile: its outer edges, whatever is inside it. */
export function rectProfile(rectId: string): ProfileRef {
  return { outer: rectId, holes: [] };
}

export function newFeature(profile: ProfileRef | null, id = newId("f")): Feature {
  return {
    id, key: id, profile, holes: "avoid", trim: DEFAULT_TRIM, marker: { ...DEFAULT_MARKER }, label: { ...DEFAULT_LABEL, offset_mm: [0, 0] }, extrude: {}, set: [],
  };
}

export function emptyDoc(name = "Untitled", shapes: Shape[] = [], preset: Preset | null = null): Doc {
  return { format: "arucostudio-web", version: 3, name, shapes, dims: [], features: [], id_ledger: {}, preset };
}

// ------------------------------------------------------------ shapes

export function addShape(doc: Doc, s: Shape): Doc {
  return { ...doc, shapes: [...doc.shapes, s] };
}

export function setShape(doc: Doc, s: Shape): Doc {
  return { ...doc, shapes: doc.shapes.map((x) => (x.id === s.id ? s : x)) };
}

/** Delete a shape; a feature whose profile it bounds goes with it (a feature
 *  is reached by clicking its marker: one without a profile could not be),
 *  a profile it was a hole of loses that hole, and a dimension naming it goes. */
export function deleteShape(doc: Doc, id: string): Doc {
  const features = doc.features.filter((f) => f.profile?.outer !== id).map((f) =>
    f.profile?.holes.includes(id) ? { ...f, profile: { ...f.profile, holes: f.profile.holes.filter((h) => h !== id) } } : f);
  return { ...doc, shapes: doc.shapes.filter((x) => x.id !== id), dims: doc.dims.filter((d) => !dimShapes(d).includes(id)), features };
}

// ------------------------------------------------------------ features

export function getFeature(doc: Doc, id: string | null | undefined): Feature | null {
  return (id && doc.features.find((f) => f.id === id)) || null;
}

/** The feature whose profile is this one, if any (one marker per profile:
 *  the core would place a second in the same spot). */
export function featureOfProfile(doc: Doc, ref: ProfileRef): Feature | null {
  return doc.features.find((f) => sameProfile(f.profile, ref)) ?? null;
}

/** The feature whose profile is this rectangle on its own, if any. */
export function featureOfRect(doc: Doc, rectId: string): Feature | null {
  return featureOfProfile(doc, rectProfile(rectId));
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

/** The rectangle a feature's profile is, when it is a rectangle with nothing
 *  inside it (the custom placement: the marker fills it, a drag moves both). */
export function featureRect(doc: Doc, f: Feature | null): RectShape | null {
  return f?.profile ? plainRect(doc.shapes, f.profile) : null;
}

/** A face (body) under the marker: it sets Z, so Flip does not apply.
 *  WHY not for a rectangle profile: a rectangle drawn for the custom placement
 *  is sketch geometry, as the old marker rectangle was (no reference face). */
export function referenceFace(doc: Doc, f: Feature): boolean {
  return !!f.profile && !featureRect(doc, f);
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
  "marker.origin_square": (f) => f.marker.origin_square != null,   // driven = null: OpenCV's board corner
  // barrier 10: an extrude field is set when present (absent = driven by the preset)
  "extrude.mode": (f) => f.extrude.mode !== undefined,
  "extrude.white_mm": (f) => f.extrude.white_mm !== undefined,
  "extrude.black_mm": (f) => f.extrude.black_mm !== undefined,
  "extrude.paper_mm": (f) => f.extrude.paper_mm !== undefined,
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
  if (path === "trim") return { ...f, trim: value as Trim, set: mark(f.set, path) };
  const [part, key] = path.split(".") as ["marker" | "label" | "extrude", string];
  if (part === "extrude") return { ...f, extrude: { ...f.extrude, [key]: value } };
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
  if (path === "marker.origin_square") return { ...f, marker: { ...f.marker, origin_square: null } };
  if (path === "trim") return { ...f, trim: DEFAULT_TRIM, set: unmark(f.set, [path]) };
  const [part, key] = path.split(".") as ["marker" | "label" | "extrude", string];
  if (part === "extrude") {
    const extrude = { ...f.extrude };
    delete extrude[key as keyof ExtrudeParams];
    return { ...f, extrude };
  }
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
 *  ChArUco 5 × 4 squares, a single 1 × 1), the size, checker, separation
 *  and a board's origin square are driven again. */
export function setType(m: MarkerParams, type: MarkerType): MarkerParams {
  if (type === m.type) return m;
  const [cols, rows] = typeCounts(type);
  return { ...m, type, cols, rows, auto: true, checker_mm: 0, separation_mm: 0, origin_square: null };
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

/** The feature's plan request: the profile's loops (the outer counter-
 *  clockwise, the holes clockwise) and what to do with its holes. No `rect`:
 *  the core places the marker and answers MarkerPlan.fit_rect. */
export function planRequest(doc: Doc, f: Feature | null): PlanRequest | null {
  const profile = f?.profile ? profileLoops(doc.shapes, f.profile) : null;
  if (!f || !profile || !doc.preset) return null;
  return {
    trim: f.trim, profile, holes: f.holes, marker: f.marker, label: f.label, preset: doc.preset,
    reference_face: referenceFace(doc, f),
    // always, even {}: the core answers MarkerPlan.extrude (the driven heights the
    // Make tab and the 3D view show grey) only when the request asks
    extrude: f.extrude,
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

/** Auto id's request: every feature, and the ids already given out. */
export function idRequest(doc: Doc): IdRequest {
  return { items: idItems(doc), ledger: doc.id_ledger };
}

/** Auto id's answer into the document: each driven feature's first id is
 *  the one assigned (a typed one is left as typed), and the ledger is the
 *  core's (a removed feature's entry is gone from it). The same document
 *  when nothing changed. `res.items` is in the order of idItems(doc). */
export function applyIds(doc: Doc, res: IdResult): Doc {
  let changed = false;
  const features = doc.features.map((f, i) => {
    const a = res.items[i];
    if (!a || a.key !== f.key || isSet(f, "marker.first_id") || a.first_id === f.marker.first_id) return f;
    changed = true;
    return { ...f, marker: { ...f.marker, first_id: a.first_id } };
  });
  const same = JSON.stringify(sortedLedger(doc.id_ledger)) === JSON.stringify(sortedLedger(res.ledger));
  if (!changed && same) return doc;
  return { ...doc, features, id_ledger: same ? doc.id_ledger : { ...res.ledger } };
}

const sortedLedger = (l: Record<string, number>) => Object.keys(l).sort().map((k) => [k, l[k]]);

/** The feature (other than `id`) whose key is already `key`, if any: keys are unique. */
export function keyOwner(doc: Doc, id: string, key: string): Feature | null {
  return doc.features.find((f) => f.id !== id && f.key === key) ?? null;
}

// ------------------------------------------------------------ the file

export function serialise(doc: Doc): string {
  return JSON.stringify(doc, null, 2);
}

/** A saved feature with what it lacks filled in from the defaults. */
function readFeature(raw: Record<string, unknown>): Feature {
  const base = newFeature(null, typeof raw.id === "string" && raw.id ? raw.id : undefined);
  const { rectId, ...rest } = raw;
  const f: Feature = {
    ...base, ...rest,
    marker: { ...DEFAULT_MARKER, ...(rest.marker as object) }, label: { ...DEFAULT_LABEL, ...(rest.label as object) },
  } as Feature;
  if (typeof f.key !== "string" || !f.key) f.key = f.id;
  if (!Array.isArray(f.set)) f.set = [];
  // before barrier 10 (2026-10-20 night) there were no heights: all driven
  if (!f.extrude || typeof f.extrude !== "object" || Array.isArray(f.extrude)) f.extrude = {};
  // version 2 (2026-10-18 .. 20): the marker filled the rectangle `rectId` (drawn,
  // or inscribed in the face `profile`); that rectangle on its own is the profile
  // now, so the marker stays where it was
  if (typeof rectId === "string" && rectId) f.profile = rectProfile(rectId);
  else if ("rectId" in raw) f.profile = null;
  // "rectangle" (deprecated 2026-10-20 evening) is a rectangle profile cut to
  // the profile; a file from before trim (2026-10-18), or an unknown one: the
  // profile, driven
  if (!TRIMS.includes(f.trim)) { f.trim = DEFAULT_TRIM; f.set = f.set.filter((p) => p !== "trim"); }
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

/** Version 2's features filled a rectangle (rectId); readFeature turns each
 *  into that rectangle as its profile. */
export function migrateV2(d: Record<string, unknown>): Record<string, unknown> {
  return { ...d, version: 3 };
}

/** Read a saved file; throws with a readable reason when it is not one. */
export function parseDoc(text: string): Doc {
  let d = JSON.parse(text);
  if (!d || d.format !== "arucostudio-web") throw new Error("not an .arucostudio-web.json file");
  if (d.version === 1) d = migrateV1(d);
  if (d.version === 2) d = migrateV2(d);
  if (d.version !== DOC_VERSION) throw new Error(`file version ${d.version}: this Studio reads versions 1 to ${DOC_VERSION}`);
  const shapes: Shape[] = Array.isArray(d.shapes) ? d.shapes.filter((s: Shape) => s && ["rect", "circle", "poly"].includes(s.kind)) : [];
  const features: Feature[] = Array.isArray(d.features) ? d.features.filter((f: unknown) => f && typeof f === "object").map(readFeature) : [];
  const ledger = d.id_ledger && typeof d.id_ledger === "object" ? d.id_ledger as Record<string, number> : {};
  const ids = new Set(shapes.map((s) => s.id));
  const dims: SketchDim[] = Array.isArray(d.dims)
    ? d.dims.filter((x: SketchDim) => x && typeof x.id === "string" && dimShapes(x).every((id) => ids.has(id))) : [];
  return {
    format: "arucostudio-web", version: 3, name: String(d.name ?? "Untitled"), shapes, dims, features, id_ledger: ledger, preset: d.preset ?? null,
  };
}
