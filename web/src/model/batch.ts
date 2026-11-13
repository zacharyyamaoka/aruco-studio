// Batch editing: one panel over several ArUco Extrude features (2 or more
// selected). Which rows it may set for them all is ONE rule, here, pure
// (vitest covers it): a row is batchable when its value is the marker's own
// and does not depend on the profile's geometry or the marker's identity;
// it then applies to every selected feature that has that row (a Label row
// to the markers whose label shows it, a 3D-print height to the 3D-printed
// ones). The rest are shown read-only, "—", with the reason as their tooltip.
// Setting a batch row goes through doc.ts's setField / resetField per
// feature; each feature then plans on its own, as one marker does.
//
// WHY (Zach, 2026-10-21): "add the ability to do batch editing of multiple
// markers ... I want to be able to turn the triangle on on many of them ...
// You need to do simple logic to see what properties are allowed to be batch
// edited ... the backend is still just pure functions".
import type { IdItem, IdResult, MarkerPlan, MarkerType } from "../core/contract";
import { tabRows } from "../panel/issues";
import { presetStep, stepKey } from "../presets/fields";
import { profileLoops } from "../sketch/model";
import { DEFAULT_MARKER, applyIds, idCount, idItems, isSet, presetKey, resetField, setField, type Doc, type Feature } from "./doc";
import { boxOf, readingOrder, type Box } from "./geom";

/** Several selected features' values differ. */
export const MIXED = "mixed" as const;

export interface BatchRow {
  path: string;
  /** set for every feature in `ids` at once */
  editable: boolean;
  /** the value every feature in `ids` shows, or MIXED */
  value: unknown;
  /** every one driven, every one set, or some of each */
  driven: boolean | typeof MIXED;
  /** the features the row applies to: those that have it */
  ids: string[];
  /** why it is read-only (the tooltip) */
  reason?: string;
}

/** The rows a batch sets for them all. */
export const BATCHABLE: readonly string[] = [
  "preset", "holes", "marker.dictionary", "marker.marker_mm", "marker.turn", "marker.quiet_modules",
  "label.on", "label.text", "label.place", "label.surface", "label.side", "label.height_mm", "label.gap_mm", "marker.corner_mark",
  "marker.size_step", "trim", "extrude.mode", "extrude.white_mm", "extrude.black_mm", "extrude.paper_mm", "marker.flip",
];

/** The rows shown read-only in a batch, and why. */
export const NOT_BATCHABLE: Readonly<Record<string, string>> = {
  "profile": "Each marker has its own profile",
  "marker.type": "Type changes which rows a marker has: set it on one marker at a time",
  "marker.first_id": "Ids stay unique: type a First ID to Re-ID the selection from it, left to right, top to bottom",
  "feature.key": "Keys stay unique: set one marker's key at a time",
  "marker.cols": "A board's columns and rows fit its own profile: set them on one marker at a time",
  "marker.separation_mm": "A grid's separation fits its own profile: set it on one marker at a time",
  "marker.checker_mm": "A board's checker fits its own profile: set it on one marker at a time",
  "marker.origin_square": "A board's origin square is its own: set it on one marker at a time",
  "marker.suggest": "Suggestions are worked out for one profile: open one marker",
  "profile.angle_deg": "Rotation turns a rectangle profile (geometry): set it on one marker at a time",
  "label.offset_mm": "An offset places one label: drag the text on the sketch",
};

/** Rows only a board has: shown (read-only) only when every selected feature is that one type. */
const TYPE_ROWS = ["marker.cols", "marker.separation_mm", "marker.checker_mm", "marker.origin_square"];

/** The Size step of an inkjet and of a 3D print differ in kind (dots vs line widths). */
const SIZE_STEP_METHODS = "Inkjet and 3D print presets step sizes differently: select one kind";

export interface BatchContext {
  /** each feature's last plan (the driven values: the size, the label's height, the heights) */
  plans?: Record<string, MarkerPlan>;
  /** the feature's profile is a rectangle on its own (it has Rotation) */
  rect?: (f: Feature) => boolean;
}

/** The rows a feature has, by path (the panel's, ../panel/issues.ts tabRows,
 *  plus Holes and Rotation, which depend on its profile). */
function rowsOf(f: Feature, ctx: BatchContext): string[] {
  const t = tabRows(f.marker, f.label, f.preset?.method ?? "inkjet");
  const out = [...t.marker, ...t.label, ...t.make];
  if (f.profile?.holes.length) out.push("holes");
  if (ctx.rect?.(f)) out.push("profile.angle_deg");
  return out;
}

/** What a feature's row shows (the panel's value: a driven size is the plan's) and whether it is driven. */
export function rowValue(f: Feature, path: string, plan?: MarkerPlan | null): { value: unknown; driven: boolean } {
  const m = f.marker, l = f.label;
  const set = isSet(f, path);
  switch (path) {
    case "preset": return { value: f.preset ? presetKey(f.preset) : null, driven: false };
    case "holes": return { value: f.holes, driven: false };
    case "trim": return { value: f.trim, driven: !set };
    case "marker.marker_mm": return { value: set ? m.marker_mm : plan?.marker_mm ?? null, driven: !set };
    case "marker.quiet_modules": return { value: m.quiet_modules, driven: m.quiet_modules === DEFAULT_MARKER.quiet_modules };
    case "marker.size_step": {
      const step = m.size_step ?? (f.preset ? presetStep(f.preset) : null);
      return { value: step ? stepKey(step) : null, driven: !set };
    }
    case "label.text": return { value: l.text, driven: false };
    case "label.place": return { value: l.place ?? "on_marker", driven: l.place === undefined };
    case "label.surface": return { value: l.surface ?? "black", driven: l.surface === undefined };
    case "label.height_mm": return { value: set ? l.height_mm : plan?.label?.height_mm ?? null, driven: !set };
    case "extrude.mode": return { value: set && f.extrude.mode !== "auto" ? f.extrude.mode : plan?.extrude?.mode ?? null, driven: !set };
    case "extrude.white_mm": case "extrude.black_mm": case "extrude.paper_mm": {
      const k = path.slice("extrude.".length) as "white_mm" | "black_mm" | "paper_mm";
      const fallback = k === "paper_mm" ? f.preset?.thickness_mm ?? null : null;
      return { value: set ? f.extrude[k] : plan?.extrude?.[k] ?? fallback, driven: !set };
    }
  }
  const [part, key] = path.split(".") as [string, string];
  if (part === "marker") return { value: (m as unknown as Record<string, unknown>)[key], driven: !set };
  if (part === "label") return { value: (l as unknown as Record<string, unknown>)[key], driven: !set };
  return { value: null, driven: true };
}

/** One value for them all, or MIXED. */
export function common(xs: unknown[]): unknown {
  const first = JSON.stringify(xs[0]);
  return xs.every((x) => JSON.stringify(x) === first) ? xs[0] : MIXED;
}

/** Every row the batch panel shows for these features, in the order they are
 *  first met (the skeleton's, tab by tab): editable or not, its common value
 *  or MIXED, and the features it applies to. A row no selected feature has is
 *  not listed; a board's own rows only when every feature is that one type. */
export function batchRows(features: Feature[], ctx: BatchContext = {}): BatchRow[] {
  const order: string[] = [];
  const has = new Map<string, Feature[]>();
  for (const f of features) {
    for (const p of rowsOf(f, ctx)) {
      if (!has.has(p)) { has.set(p, []); order.push(p); }
      has.get(p)!.push(f);
    }
  }
  const types = new Set<MarkerType>(features.map((f) => f.marker.type));
  const methods = new Set(features.map((f) => f.preset?.method ?? "inkjet"));
  const out: BatchRow[] = [];
  for (const path of order) {
    const fs = has.get(path)!;
    if (TYPE_ROWS.includes(path) && (types.size > 1 || fs.length !== features.length)) continue;
    const shown = fs.map((f) => rowValue(f, path, ctx.plans?.[f.id]));
    const drv = common(shown.map((s) => s.driven));
    const row: BatchRow = { path, editable: BATCHABLE.includes(path), value: common(shown.map((s) => s.value)), driven: drv as boolean | typeof MIXED, ids: fs.map((f) => f.id) };
    if (path === "marker.size_step" && methods.size > 1) { row.editable = false; row.reason = SIZE_STEP_METHODS; }
    else if (!row.editable) row.reason = NOT_BATCHABLE[path] ?? "Set it on one marker at a time";
    out.push(row);
  }
  return out;
}

/** A batch row's value set on one feature (doc.ts's setField; Holes and Preset are the feature's own fields). */
export function applyBatch(f: Feature, path: string, value: unknown): Feature {
  if (path === "holes") return { ...f, holes: value as Feature["holes"] };
  if (path === "preset") return { ...f, preset: value as Feature["preset"] };
  return setField(f, path, value);
}

/** A batch row back to driven on one feature (doc.ts's resetField). */
export function resetBatch(f: Feature, path: string): Feature {
  return path === "holes" || path === "preset" ? f : resetField(f, path);
}

/** The ids a feature prints: its plan's, else its first id's block. */
function idsOf(f: Feature, plan?: MarkerPlan | null): number[] {
  if (plan?.ids?.length) return plan.ids;
  return Array.from({ length: idCount(f.marker) }, (_, k) => f.marker.first_id + k);
}

/** "#0–7, 9, 12–15": ids, sorted, runs joined. */
export function idRuns(ids: number[]): string {
  const xs = [...new Set(ids)].sort((a, b) => a - b);
  const runs: string[] = [];
  for (let i = 0; i < xs.length; i++) {
    let j = i;
    while (j + 1 < xs.length && xs[j + 1] === xs[j] + 1) j++;
    runs.push(i === j ? `${xs[i]}` : `${xs[i]}–${xs[j]}`);
    i = j;
  }
  return runs.length ? `#${runs.join(", ")}` : "—";
}

/** The batch panel's summary line: "9 markers · 4X4_50 · ids #0–15" ("Mixed" where they differ). */
export function batchSummary(features: Feature[], plans: Record<string, MarkerPlan> = {}): string {
  const dict = common(features.map((f) => f.marker.dictionary));
  const ids = features.flatMap((f) => idsOf(f, plans[f.id]));
  return `${features.length} markers · ${dict === MIXED ? "Mixed" : String(dict).replace("DICT_", "")} · ids ${idRuns(ids)}`;
}

// ------------------------------------------------------------ Re-ID of a selection

/** Where a feature is on the sketch: its profile's outer loop's box. */
export function featureBox(doc: Doc, f: Feature): Box | null {
  const pr = f.profile ? profileLoops(doc.shapes, f.profile) : null;
  return pr?.loops[0]?.length ? boxOf(pr.loops[0]) : null;
}

/** The features in reading order (geom.ts readingOrder: left to right, top to
 *  bottom), only `only`'s when given. */
export function readingFeatures(doc: Doc, only: readonly string[] | null = null): Feature[] {
  const fs = only ? doc.features.filter((f) => only.includes(f.id)) : doc.features;
  return readingOrder(fs, (f) => featureBox(doc, f));
}

/** Re-ID's items: every feature, in READING order (the core numbers driven
 *  items in request order, so Re-ID from 100 gives the top-left marker 100,
 *  its right-hand neighbour 101, ...). When only `only` (feature ids) are
 *  renumbered, every other feature is held at the ids it has, as if typed
 *  (the core steps over typed ids: core/autoid.py rule 2), so only the
 *  selection moves. `keepTyped` false: a typed id among those renumbered is
 *  renumbered too (it becomes driven at its new id: reIdDoc).
 *  WHY (Zach, 2026-11-13): "batch select a bunch of ids and then set the
 *  starting ID and then it will Re-ID all of them, left to right, top to
 *  bottom in priority". */
export function reIdItems(doc: Doc, only: readonly string[] | null, keepTyped = true): IdItem[] {
  const items = idItems(doc);
  const byId = new Map(doc.features.map((f, i) => [f.id, items[i]]));
  return readingFeatures(doc).map((f) => {
    const it = byId.get(f.id)!;
    if (only && !only.includes(f.id)) return { ...it, first_id: f.marker.first_id };
    return keepTyped ? it : { ...it, first_id: null };
  });
}

/** A Re-ID answer (for reIdItems(doc, only, keepTyped)) into the document:
 *  its items back in document order (applyIds reads them by index), each
 *  renumbered feature's new first id, a renumbered typed one driven now (its
 *  new id is in the ledger, so it stays), and the ledger the document's for
 *  the other features and the answer's for the renumbered ones (a fresh
 *  answer knows only what it numbered). -> the document and the whole answer. */
export function reIdDoc(doc: Doc, only: readonly string[] | null, res: IdResult, keepTyped = true): { doc: Doc; res: IdResult } {
  const scope = new Set(doc.features.filter((f) => !only || only.includes(f.id)).map((f) => f.key));
  const byKey = new Map(res.items.map((a) => [a.key, a]));
  const items = doc.features.map((f) => byKey.get(f.key) ?? { key: f.key, first_id: f.marker.first_id, ids: [], driven: false });
  const features = doc.features.map((f) => (
    !keepTyped && scope.has(f.key) && isSet(f, "marker.first_id") && byKey.get(f.key)?.ids.length ? resetField(f, "marker.first_id") : f));
  const ledger: Record<string, number> = {};
  if (only) for (const [k, v] of Object.entries(doc.id_ledger)) if (!scope.has(k)) ledger[k] = v;
  for (const [k, v] of Object.entries(res.ledger)) if (scope.has(k)) ledger[k] = v;
  const whole: IdResult = { ...res, items, ledger };
  return { doc: applyIds({ ...doc, features }, whole), res: whole };
}

/** The ArUco dictionary sizes of one bit size, smallest first (core/dictionary.py). */
const SIZES = [50, 100, 250, 1000];

/** Re-ID from `start` (Sequential): a marker whose dictionary is too small for
 *  the ids it would be given moves to the smallest dictionary of its bit size
 *  that holds them -- DICT_4X4_50 ends at #49, so numbered from 100 its
 *  markers become DICT_4X4_250. The patterns of the first ids are the same in
 *  every size (core/numbering.py family), only the range grows. Ids the other
 *  markers hold at or past `start` push the numbering on, so they count.
 *  `keepTyped`: a typed id among them keeps its number, so it only holds one.
 *  -> the document (the same one when nothing grows) and each change [from, to].
 *  WHY (Zach, 2026-11-13: "set a starting ID to like 100 and then all of them
 *  would go 100, 101"): with the default DICT_4X4_50 the core wrapped them to
 *  0 with a warning, which read as Re-ID doing nothing. */
export function growForStart(doc: Doc, only: readonly string[] | null, start: number, keepTyped = false): { doc: Doc; grown: [string, string][] } {
  const bits = (d: string) => /^DICT_(\d)X\1_(\d+)$/.exec(d);
  // a typed id that is kept is not renumbered: it holds its id, as the others do
  const scope = doc.features.filter((f) => (!only || only.includes(f.id)) && !(keepTyped && isSet(f, "marker.first_id")));
  const need = new Map<string, number>();        // bit size -> the last id the numbering reaches
  for (const f of scope) {
    const m = bits(f.marker.dictionary);
    if (m) need.set(m[1], (need.get(m[1]) ?? start - 1) + idCount(f.marker));
  }
  for (const f of doc.features) {
    const m = bits(f.marker.dictionary);
    if (!m || !need.has(m[1]) || scope.includes(f)) continue;
    const held = idsOf(f).filter((i) => i >= start).length;
    need.set(m[1], need.get(m[1])! + held);
  }
  const grown: [string, string][] = [];
  const features = doc.features.map((f) => {
    const m = bits(f.marker.dictionary);
    if (!m || !scope.includes(f)) return f;
    const last = need.get(m[1])!;
    if (Number(m[2]) > last) return f;
    const size = SIZES.find((n) => n > last && n >= Number(m[2]));
    if (!size) return f;                          // past DICT_nXn_1000: the core warns of the wrap
    const to = `DICT_${m[1]}X${m[1]}_${size}`;
    if (!grown.some(([a, b]) => a === f.marker.dictionary && b === to)) grown.push([f.marker.dictionary, to]);
    return setField(f, "marker.dictionary", to);
  });
  return grown.length ? { doc: { ...doc, features }, grown } : { doc, grown };
}

/** "DICT_4X4_50 → DICT_4X4_250 (it ends at #49)" for each growth, in words. */
export function grownWords(grown: [string, string][]): string {
  return grown.map(([a, b]) => `${a.replace("DICT_", "")} → ${b.replace("DICT_", "")} (${a.replace("DICT_", "")} ends at #${Number(a.split("_").pop()) - 1})`).join(", ");
}
