// The document: one sketch (closed shapes, ../sketch/model.ts) and any number
// of ArUco Extrude features, each with the preset it is made by. Pure: the
// store (../store.ts) calls these; vitest covers them. Saved as
// `.arucostudio-web.json` (format "arucostudio-web", version 4; a version 1
// file, which held one feature, a version 2 file, whose features filled a
// rectangle, and a version 3 file, whose one preset was the document's, are
// migrated on open).
//
// WHY a preset per feature (Zach, 2026-10-20 night): "Preset shouldn't be on
// the file because it's applied on a per marker basis!" The document keeps
// only the preset a NEW marker starts with: the last one picked.
//
// WHY a feature references a PROFILE (Zach, 2026-10-20 evening: "if we just
// have the idea of a profile, and you want a custom location, then you draw a
// rectangle profile … it's just going to be a profile"): the core places the
// marker in the profile, like an extrude; a rectangle profile is used exactly
// (contract.ts PlanRequest, barrier 9).
import type { ExtrudeParams, IdItem, IdRequest, IdResult, LabelParams, MarkerParams, MarkerType, PlanRequest, Preset, RangeNeed, Suggestion, Trim, Turn } from "../core/contract";
import { dimShapes, type SketchDim } from "../sketch/constraints";
import { plainRect, profileLoops, sameProfile, type ProfileRef, type RectShape, type Shape } from "../sketch/model";
import { cleanPreset } from "../presets/local";

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
  /** legacy (a version 2 file's `rectId` with trim profile): the rectangle
   *  the marker is placed in while the sticker is cut to `profile`; absent for
   *  every feature made since (the core places the marker in the profile) */
  rect?: string;
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
  /** how it is made (inkjet or 3D print, and the numbers); null only while
   *  the core's presets have not arrived (loadCoreFacts fills it) */
  preset: Preset | null;
  /** the fields typed by hand among those the contract has no driven
   *  encoding for ("marker.cols", "label.gap_mm", ...). The rest say it in
   *  their own value: see isSet(). */
  set: string[];
  /** Verify's required viewing distance (contract barrier 13 RangeNeed, Zach
   *  2026-10-21: "batch set minimum and maximum viewing distance"): what the
   *  marker's reading range must cover to PASS. Absent, or an end absent:
   *  nothing required there. Never sent to plan (it changes no geometry);
   *  set through setField("verify.min_mm" | "verify.max_mm") like any row. */
  verify?: RangeNeed;
}

export interface Doc {
  format: "arucostudio-web";
  version: 4;
  name: string;
  shapes: Shape[];
  /** the sketch's driving dimensions (D; ../sketch/constraints.ts): a file
   *  from before them has none */
  dims: SketchDim[];
  features: Feature[];
  /** auto id: key -> the first id already given out (IdRequest.ledger) */
  id_ledger: Record<string, number>;
  /** the preset a new marker starts with: the last one picked (a version 3
   *  file's one preset) */
  default_preset: Preset | null;
}

export const DOC_VERSION = 4;

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
  on: false, text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0],
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

export function newFeature(profile: ProfileRef | null, id = newId("f"), preset: Preset | null = null): Feature {
  return {
    id, key: id, profile, holes: "avoid", trim: DEFAULT_TRIM, marker: { ...DEFAULT_MARKER }, label: { ...DEFAULT_LABEL, offset_mm: [0, 0] }, extrude: {},
    preset, set: [],
  };
}

export function emptyDoc(name = "Untitled", shapes: Shape[] = [], defaultPreset: Preset | null = null): Doc {
  return { format: "arucostudio-web", version: 4, name, shapes, dims: [], features: [], id_ledger: {}, default_preset: defaultPreset };
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
    f.profile?.holes.includes(id) ? { ...f, profile: { ...f.profile, holes: f.profile.holes.filter((h) => h !== id) } } : f)
    // a legacy placement rectangle deleted: the core places the marker in the profile
    .map((f) => (f.rect === id ? withoutRect(f) : f));
  return { ...doc, shapes: doc.shapes.filter((x) => x.id !== id), dims: doc.dims.filter((d) => !dimShapes(d).includes(id)), features };
}

// ------------------------------------------------------------ features

/** A feature without its legacy placement rectangle (Feature.rect). */
export function withoutRect(f: Feature): Feature {
  const { rect: _gone, ...rest } = f;
  return rest;
}

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
  "marker.size_step": (f) => f.marker.size_step != null,           // barrier 11: driven = absent / null, the preset's
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
  if (path === "verify" || path.startsWith("verify.")) return setVerify(f, path, value);
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
  if (path === "verify" || path.startsWith("verify.")) return setVerify(f, path, null);
  if (path === "marker.marker_mm") return { ...f, marker: { ...f.marker, auto: true } };
  if (path === "marker.checker_mm") return { ...f, marker: { ...f.marker, checker_mm: 0 } };
  if (path === "marker.separation_mm") return { ...f, marker: { ...f.marker, separation_mm: 0 } };
  if (path === "label.height_mm") return { ...f, label: { ...f.label, height_mm: 0 } };
  if (path === "marker.origin_square") return { ...f, marker: { ...f.marker, origin_square: null } };
  if (path === "marker.size_step") return { ...f, marker: { ...f.marker, size_step: null } };
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

/** The required viewing distance: "verify.min_mm" / "verify.max_mm" set (a
 *  number) or cleared (null), "verify" as a whole replaced or cleared (null).
 *  A requirement with neither end left is no requirement (the field goes). */
export function setVerify(f: Feature, path: string, value: unknown): Feature {
  let need: RangeNeed;
  if (path === "verify") need = value && typeof value === "object" ? { ...(value as RangeNeed) } : {};
  else {
    const key = path.slice("verify.".length) as keyof RangeNeed;
    need = { ...f.verify };
    if (typeof value === "number" && Number.isFinite(value)) need[key] = value;
    else delete need[key];
  }
  for (const k of ["min_mm", "max_mm"] as const) if (need[k] == null) delete need[k];
  const { verify: _old, ...rest } = f;
  return Object.keys(need).length ? { ...rest, verify: need } : rest;
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

/** The preset a feature is made by: its own; the new-marker default for one
 *  made before the core's presets arrived (a step back in the history). */
export function featurePreset(doc: Doc, f: Feature | null | undefined): Preset | null {
  return f?.preset ?? doc.default_preset;
}

/** Every feature without a preset given `p` (the core's presets arrived, or a
 *  file or an example came without one); the same document when none lacks it. */
export function fillPresets(doc: Doc, p: Preset | null): Doc {
  if (!p || doc.features.every((f) => f.preset)) return doc;
  return { ...doc, features: doc.features.map((f) => (f.preset ? f : { ...f, preset: p })) };
}

/** The feature's plan request: the profile's loops (the outer counter-
 *  clockwise, the holes clockwise), what to do with its holes, and its own
 *  preset. No `rect`: the core places the marker and answers MarkerPlan.fit_rect
 *  -- except a legacy feature's placement rectangle (Feature.rect), sent as
 *  the facade's `rect` beside the profile it is cut to. */
export function planRequest(doc: Doc, f: Feature | null): PlanRequest | null {
  const profile = f?.profile ? profileLoops(doc.shapes, f.profile) : null;
  const preset = featurePreset(doc, f);
  if (!f || !profile || !preset) return null;
  const place = f.rect ? doc.shapes.find((s): s is RectShape => s.id === f.rect && s.kind === "rect") : undefined;
  return {
    trim: f.trim, profile, holes: f.holes, marker: f.marker, label: f.label, preset,
    ...(place ? { rect: { cx: place.cx, cy: place.cy, w: place.w, h: place.h, angle_deg: place.angle_deg } } : {}),
    reference_face: referenceFace(doc, f),
    // always, even {}: the core answers MarkerPlan.extrude (the driven heights the
    // Make tab and the 3D view show grey) only when the request asks
    extrude: f.extrude,
  };
}

/** One paper sheet: the inkjet features made by one preset, in the order made. */
export interface SheetGroup { key: string; preset: Preset; items: PlanRequest[] }

/** Print's sheets: the inkjet features that plan, one group per preset (its
 *  page size can differ), in the order the presets first appear. A 3D-print
 *  feature is not printed on paper, nor one whose ids auto id refused
 *  (`refused`: their keys, refusedKeys). Two presets are one group when every
 *  field is the same (the id alone is not enough: a modified copy shares it). */
export function sheetGroups(doc: Doc, refused: readonly string[] = []): SheetGroup[] {
  const groups = new Map<string, SheetGroup>();
  for (const f of doc.features) {
    if (refused.includes(f.key)) continue;
    const req = planRequest(doc, f);
    if (!req || req.preset.method !== "inkjet") continue;
    const key = presetKey(req.preset);
    const g = groups.get(key) ?? { key, preset: req.preset, items: [] };
    g.items.push(req);
    groups.set(key, g);
  }
  return [...groups.values()];
}

/** A preset's identity for grouping: its fields, in key order. */
export function presetKey(p: Preset): string {
  return JSON.stringify(Object.keys(p).sort().map((k) => [k, (p as unknown as Record<string, unknown>)[k]]));
}

/** Print's sheet for one feature's preset (`featureId`'s, else the first
 *  group's): the items core.sheet lays out on that preset's page. */
export function sheetItems(doc: Doc, featureId?: string | null, refused: readonly string[] = []): PlanRequest[] {
  const groups = sheetGroups(doc, refused);
  const f = getFeature(doc, featureId);
  const own = f ? featurePreset(doc, f) : null;
  return (own && groups.find((g) => g.key === presetKey(own)))?.items ?? groups[0]?.items ?? [];
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
 *  when nothing changed. `res.items` is in the order of idItems(doc).
 *  WHY a refused item (ids []) keeps its first id (review finding #5,
 *  2026-10-21): its first_id is only the block the core wanted, already
 *  someone else's; taken, a full dictionary printed a duplicate. */
export function applyIds(doc: Doc, res: IdResult): Doc {
  let changed = false;
  const features = doc.features.map((f, i) => {
    const a = res.items[i];
    if (!a || a.key !== f.key || !a.ids.length || isSet(f, "marker.first_id") || a.first_id === f.marker.first_id) return f;
    changed = true;
    return { ...f, marker: { ...f.marker, first_id: a.first_id } };
  });
  const same = JSON.stringify(sortedLedger(doc.id_ledger)) === JSON.stringify(sortedLedger(res.ledger));
  if (!changed && same) return doc;
  return { ...doc, features, id_ledger: same ? doc.id_ledger : { ...res.ledger } };
}

const sortedLedger = (l: Record<string, number>) => Object.keys(l).sort().map((k) => [k, l[k]]);

/** The keys auto id gave no ids (ids []: out of its dictionary, or the
 *  dictionary is full; the answer's warnings say why): never printed or exported. */
export function refusedKeys(res: IdResult): string[] {
  return res.items.filter((a) => !a.ids.length).map((a) => a.key);
}

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
  // a file from before version 4 has no preset per feature: parseDoc gives it the file's
  if (!f.preset || typeof f.preset !== "object" || Array.isArray(f.preset)) f.preset = null;
  // before barrier 10 (2026-10-20 night) there were no heights: all driven
  if (!f.extrude || typeof f.extrude !== "object" || Array.isArray(f.extrude)) f.extrude = {};
  // version 2 (2026-10-18 .. 20): the marker filled the rectangle `rectId` (drawn,
  // or inscribed in the face `profile`); that rectangle on its own is the profile
  // now, so the marker stays where it was. WHY not for trim profile with a face
  // (review finding #3, 2026-10-21): that sticker was cut to the face, holes and
  // all; the face stays the profile and rectId the placement (Feature.rect)
  const face = rest.profile as ProfileRef | null | undefined;
  if (typeof rectId === "string" && rectId) {
    if (f.trim === "profile" && face && typeof face === "object" && face.outer !== rectId) f.rect = rectId;
    else f.profile = rectProfile(rectId);
  } else if ("rectId" in raw) f.profile = null;
  if (f.rect !== undefined && typeof f.rect !== "string") delete f.rect;
  // barrier 13: a requirement is {min_mm?, max_mm?}; anything else, or an empty one, is none
  if (f.verify !== undefined) {
    const v = f.verify as unknown;
    const num = (x: unknown) => typeof x === "number" && Number.isFinite(x) && x >= 0;
    if (!v || typeof v !== "object" || Array.isArray(v)) delete f.verify;
    else {
      const o = v as Record<string, unknown>;
      const need: RangeNeed = {};
      if (num(o.min_mm)) need.min_mm = o.min_mm as number;
      if (num(o.max_mm)) need.max_mm = o.max_mm as number;
      if (Object.keys(need).length) f.verify = need;
      else delete f.verify;
    }
  }
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

/** Version 3 had one preset, the document's: every feature is made by it,
 *  and it is the one a new marker starts with. */
export function migrateV3(d: Record<string, unknown>): Record<string, unknown> {
  const { preset, ...rest } = d;
  const p = preset && typeof preset === "object" ? preset : null;
  const features = Array.isArray(d.features)
    ? d.features.map((f) => (f && typeof f === "object" ? { ...(f as object), preset: p } : f)) : d.features;
  return { ...rest, version: 4, features, default_preset: p };
}

/** Read a saved file; throws with a readable reason when it is not one. */
export function parseDoc(text: string): Doc {
  let d = JSON.parse(text);
  if (!d || d.format !== "arucostudio-web") throw new Error("not an .arucostudio-web.json file");
  if (d.version === 1) d = migrateV1(d);
  if (d.version === 2) d = migrateV2(d);
  if (d.version === 3) d = migrateV3(d);
  if (d.version !== DOC_VERSION) throw new Error(`file version ${d.version}: this Studio reads versions 1 to ${DOC_VERSION}`);
  const shapes: Shape[] = Array.isArray(d.shapes) ? d.shapes.filter((s: Shape) => s && ["rect", "circle", "poly"].includes(s.kind)) : [];
  const features: Feature[] = Array.isArray(d.features) ? d.features.filter((f: unknown) => f && typeof f === "object").map(readFeature) : [];
  const ledger = d.id_ledger && typeof d.id_ledger === "object" ? d.id_ledger as Record<string, number> : {};
  const ids = new Set(shapes.map((s) => s.id));
  const dims: SketchDim[] = Array.isArray(d.dims)
    ? d.dims.filter((x: SketchDim) => x && typeof x.id === "string" && dimShapes(x).every((id) => ids.has(id))) : [];
  const defaultPreset: Preset | null = d.default_preset && typeof d.default_preset === "object" ? d.default_preset : null;
  const doc = fillPresets({
    format: "arucostudio-web", version: 4, name: String(d.name ?? "Untitled"), shapes, dims, features, id_ledger: ledger, default_preset: defaultPreset,
  }, defaultPreset);
  validateDoc(doc);
  return doc;
}

// ------------------------------------------------------------ checking a whole document

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const pair = (v: unknown): boolean => Array.isArray(v) && v.length === 2 && v.every(finite);
const nonEmpty = (v: unknown): v is string => typeof v === "string" && v.length > 0;

/** Every field the editor, the sketch and the requests read, checked: a
 *  shape's geometry, ids and keys unique, a profile's shapes in the sketch, a
 *  dimension's numbers, the ledger, each preset. Throws the first problem,
 *  naming where it is ("shape 3 (\"bad\"): ...").
 *  WHY before anything is replaced (review finding #4, 2026-10-21): a file
 *  that only failed once loadDoc drew it had already swapped the document and
 *  cleared the history; parseDoc and loadDoc both call this first. */
export function validateDoc(doc: Doc): void {
  if (typeof doc.name !== "string") throw new Error("the name is not text");
  if (!Array.isArray(doc.shapes) || !Array.isArray(doc.features) || !Array.isArray(doc.dims)) throw new Error("shapes, features and dims must be lists");
  const shapeIds = new Set<string>();
  doc.shapes.forEach((sh, i) => {
    const at = `shape ${i + 1}${nonEmpty(sh?.id) ? ` ("${sh.id}")` : ""}`;
    if (!sh || typeof sh !== "object") throw new Error(`${at} is not a shape`);
    if (!nonEmpty(sh.id)) throw new Error(`${at}: its id must be text`);
    if (shapeIds.has(sh.id)) throw new Error(`${at}: the id "${sh.id}" is used twice`);
    shapeIds.add(sh.id);
    if (sh.kind === "rect") {
      for (const k of ["cx", "cy", "w", "h", "angle_deg"] as const) if (!finite(sh[k])) throw new Error(`${at}: a rect needs a number ${k}`);
      if (sh.w <= 0 || sh.h <= 0) throw new Error(`${at}: a rect's w and h must be above 0`);
    } else if (sh.kind === "circle") {
      for (const k of ["cx", "cy", "r"] as const) if (!finite(sh[k])) throw new Error(`${at}: a circle needs a number ${k}`);
      if (sh.r <= 0) throw new Error(`${at}: a circle's r must be above 0`);
    } else if (sh.kind === "poly") {
      if (!Array.isArray(sh.pts) || sh.pts.length < 3 || !sh.pts.every(pair)) throw new Error(`${at}: a poly needs pts, 3 or more [x, y] points`);
    } else throw new Error(`${at}: unknown kind ${JSON.stringify((sh as { kind?: unknown }).kind)}`);
  });
  const dimIds = new Set<string>();
  doc.dims.forEach((dm, i) => {
    const at = `dimension ${i + 1}${nonEmpty(dm?.id) ? ` ("${dm.id}")` : ""}`;
    if (!dm || !nonEmpty(dm.id)) throw new Error(`${at}: its id must be text`);
    if (dimIds.has(dm.id)) throw new Error(`${at}: the id "${dm.id}" is used twice`);
    dimIds.add(dm.id);
    if (!["w", "h", "d", "x", "y"].includes(dm.kind)) throw new Error(`${at}: unknown kind ${JSON.stringify(dm.kind)}`);
    if (!finite(dm.value)) throw new Error(`${at}: its value must be a number`);
    if (!pair(dm.at)) throw new Error(`${at}: at must be [x, y]`);
    for (const id of dimShapes(dm)) if (!shapeIds.has(id)) throw new Error(`${at}: names shape "${id}", which is not in the sketch`);
  });
  const featureIds = new Set<string>(), keys = new Set<string>();
  doc.features.forEach((f, i) => {
    const at = `feature ${i + 1}${nonEmpty(f?.id) ? ` ("${f.id}")` : ""}`;
    if (!f || typeof f !== "object") throw new Error(`${at} is not a feature`);
    if (!nonEmpty(f.id)) throw new Error(`${at}: its id must be text`);
    if (featureIds.has(f.id)) throw new Error(`${at}: the id "${f.id}" is used twice`);
    featureIds.add(f.id);
    if (!nonEmpty(f.key)) throw new Error(`${at}: its key must be text`);
    if (keys.has(f.key)) throw new Error(`${at}: the key "${f.key}" is used twice (keys are unique)`);
    keys.add(f.key);
    if (f.profile !== null) {
      const pr = f.profile as Partial<ProfileRef> | undefined;
      if (!pr || !nonEmpty(pr.outer) || !Array.isArray(pr.holes) || !pr.holes.every(nonEmpty)) throw new Error(`${at}: its profile must be {outer, holes} or null`);
      for (const id of [pr.outer, ...pr.holes]) if (!shapeIds.has(id)) throw new Error(`${at}: its profile names shape "${id}", which is not in the sketch`);
    }
    if (f.holes !== "avoid" && f.holes !== "ignore") throw new Error(`${at}: holes must be "avoid" or "ignore"`);
    if (f.rect !== undefined && !doc.shapes.some((x) => x.id === f.rect && x.kind === "rect")) {
      throw new Error(`${at}: its placement names rect "${f.rect}", which is not in the sketch`);
    }
    if (!TRIMS.includes(f.trim)) throw new Error(`${at}: unknown trim ${JSON.stringify(f.trim)}`);
    if (!Array.isArray(f.set) || !f.set.every((x) => typeof x === "string")) throw new Error(`${at}: set must be a list of field names`);
    const m = f.marker;
    if (!m || typeof m !== "object") throw new Error(`${at}: its marker is missing`);
    if (!["single", "grid", "charuco"].includes(m.type)) throw new Error(`${at}: unknown marker type ${JSON.stringify(m.type)}`);
    if (!nonEmpty(m.dictionary)) throw new Error(`${at}: marker.dictionary must be text`);
    if (!Number.isInteger(m.first_id) || m.first_id < 0) throw new Error(`${at}: marker.first_id must be a whole number of 0 or more`);
    for (const k of ["cols", "rows"] as const) if (!Number.isInteger(m[k]) || m[k] < 1) throw new Error(`${at}: marker.${k} must be a whole number of 1 or more`);
    for (const k of ["marker_mm", "checker_mm", "separation_mm", "quiet_modules"] as const) {
      if (!finite(m[k]) || m[k] < 0) throw new Error(`${at}: marker.${k} must be a number of 0 or more`);
    }
    if (![0, 90, 180, 270].includes(m.turn)) throw new Error(`${at}: marker.turn must be 0, 90, 180 or 270`);
    if (typeof m.auto !== "boolean" || typeof m.flip !== "boolean") throw new Error(`${at}: marker.auto and marker.flip must be true or false`);
    if (m.origin_square != null && !pair(m.origin_square)) throw new Error(`${at}: marker.origin_square must be [col, row] or null`);
    const l = f.label;
    if (!l || typeof l !== "object") throw new Error(`${at}: its label is missing`);
    if (typeof l.on !== "boolean" || typeof l.text !== "string") throw new Error(`${at}: label.on must be true or false, label.text text`);
    if (!["below", "above", "left", "right"].includes(l.side)) throw new Error(`${at}: unknown label.side ${JSON.stringify(l.side)}`);
    if (!finite(l.height_mm) || l.height_mm < 0 || !finite(l.gap_mm)) throw new Error(`${at}: label.height_mm and label.gap_mm must be numbers`);
    if (!pair(l.offset_mm)) throw new Error(`${at}: label.offset_mm must be [x, y]`);
    for (const k of ["white_mm", "black_mm", "paper_mm"] as const) {
      if (f.extrude[k] !== undefined && !finite(f.extrude[k])) throw new Error(`${at}: extrude.${k} must be a number`);
    }
    if (f.verify !== undefined) {
      if (!f.verify || typeof f.verify !== "object" || Array.isArray(f.verify)) throw new Error(`${at}: verify must be {min_mm, max_mm}`);
      for (const k of ["min_mm", "max_mm"] as const) {
        const v = f.verify[k];
        if (v != null && (!finite(v) || v < 0)) throw new Error(`${at}: verify.${k} must be a number of 0 or more`);
      }
    }
    if (f.preset) cleanPreset(f.preset, `${at}: its preset`);
  });
  if (!doc.id_ledger || typeof doc.id_ledger !== "object" || Array.isArray(doc.id_ledger)) throw new Error("id_ledger must be {key: first id}");
  for (const [k, v] of Object.entries(doc.id_ledger)) if (!Number.isInteger(v) || v < 0) throw new Error(`id_ledger "${k}": must be a whole number of 0 or more`);
  if (doc.default_preset) cleanPreset(doc.default_preset, "the new markers' preset");
}
