// The contract between the online Studio (web/) and the Python core running in
// the browser (aruco_studio/web_api.py inside a Pyodide worker).
//
// FROZEN for the v1 lanes (docs/design/online_studio_v1.md). Change it only in
// its own commit, never inside a lane: the UI and the core both import it.
//
// WHY one Python core in the browser instead of a TypeScript port: the Fusion
// add-in, build123d and viser are Python, so the same plan_tag must draw the
// marker everywhere (WYSIWYG between the page and the CAD). Pyodide runs the
// stdlib-only core unchanged, byte-identical to CPython (spike, 2026-10-18).
//
// Frame: the sketch plane. x right, y up, millimetres, origin = the sketch's.

export type Vec2 = [number, number];
/** closed implicitly; outer loops counter-clockwise, holes clockwise */
export type Loop = Vec2[];
export interface Polygon { outer: Loop; holes: Loop[] }

/** A sketch rectangle: the marker rectangle. The marker is drawn inside it. */
export interface Rect { cx: number; cy: number; w: number; h: number; angle_deg: number }

/** A face or closed sketch region: the outer loop first, then its holes. */
export interface Profile { loops: Loop[] }

export type MarkerType = "single" | "grid" | "charuco";
export type Turn = 0 | 90 | 180 | 270;
export type CornerMark = "none" | "triangle";

/** The marker's own numbers (Zach's "Marker" section). Manual always works;
 *  auto only fills in what was not typed. */
export interface MarkerParams {
  type: MarkerType;
  dictionary: string;        // a name from CoreInfo.dictionaries, e.g. "DICT_4X4_50"
  first_id: number;          // the id (single) or the first id of the range
  /** true: the core sizes the marker (and checker) to fill the rectangle for
   *  the given cols / rows. false: marker_mm is used as typed, even when it
   *  does not fit; the plan then reports overflow_mm and a red warning. */
  auto: boolean;
  marker_mm: number;         // the black marker's side (auto = false)
  checker_mm: number;        // ChArUco square side; 0 = the core's default for marker_mm
  separation_mm: number;     // grid gap between markers; 0 = the core's default rule
  cols: number;              // grid / ChArUco; 1 for single
  rows: number;
  turn: Turn;                // which way is up: turns the marker in 90 degree steps
  flip: boolean;             // mirror Z when there is no reference face (ignored with one)
  quiet_modules: number;     // white border in modules (cells); 1 by default
  corner_mark: CornerMark;   // a triangle in the quiet zone's top-left corner
}

export type LabelSide = "below" | "above" | "left" | "right";

/** The label is plain sketch text beside the rectangle, as a CAD text entity
 *  would be; the core only resolves the text and its default spot. */
export interface LabelParams {
  on: boolean;
  /** placeholders: {id} {first} {last} {ids} (e.g. "0-5") {dict} {type} */
  text: string;
  height_mm: number;         // 0 = the core picks from the rectangle's size
  side: LabelSide;
  gap_mm: number;            // from the rectangle's edge to the text
  offset_mm: Vec2;           // a drag on the canvas adds this to the default spot
}

export type Method = "inkjet" | "print3d";

/** How it is made (Zach: "the first thing you need to decide"). A flat record;
 *  the core maps it onto its own presets (settings.make, settings.cells). */
export interface Preset {
  id: string;                // built-ins start with "builtin:"
  name: string;
  method: Method;
  builtin: boolean;
  // Inkjet printer
  page?: string;             // "Letter", "A4", ...
  page_mm?: Vec2;            // the paper's width, height
  margin_mm?: number;        // unprintable margin on every side
  thickness_mm?: number;     // paper / vinyl thickness
  dpi?: number;
  // 3D printer
  nozzle_mm?: number;
  line_mm?: number;          // line (extrusion) width
  first_line_mm?: number;    // first-layer line width (sizes the cells when printed face down)
  layer_mm?: number;
  first_layer_mm?: number;
  bed_mm?: Vec2;
  // both
  min_cell_mm?: number;      // the smallest cell this machine makes well
  cell_step_mm?: number;     // cells snap to multiples of this (3D: the line width); 0 = no snap
}

export interface PlanRequest {
  rect: Rect;
  marker: MarkerParams;
  label: LabelParams;
  preset: Preset;
  /** a face (body) under the rectangle: it sets Z, so Flip does not apply */
  reference_face: boolean;
}

export type IssueLevel = "info" | "warn" | "error";
/** field: "marker.<key>", "label.<key>", "rect", "preset" or "tag" (the whole
 *  marker). The panel shows each issue under its row (per-line validation).
 *  Nothing is refused: an over-size marker is drawn and flagged "error" (red). */
export interface Issue { field: string; level: IssueLevel; text: string }

export interface PlacedLabel {
  text: string;
  at: Vec2;                  // the text's centre, sketch frame
  height_mm: number;         // cap height
  angle_deg: number;
}

export interface MarkerPlan {
  ok: boolean;
  ids: number[];
  // geometry, already placed in the sketch frame (rect centre, angle, turn, flip)
  black: Polygon[];          // the ink
  outer: Loop;               // the white outline (quiet-zone edge): what is cut
  outer_mm: Vec2;            // its width and height in the marker's own frame
  marker_mm: number;
  checker_mm: number;        // 0 unless ChArUco
  separation_mm: number;     // 0 unless grid
  cols: number;
  rows: number;
  cell_mm: number;           // one module (bit) of the marker
  auto: boolean;             // the size came from auto
  overflow_mm: number;       // how far the outline pokes past the rectangle; 0 = fits
  /** OpenCV's frame of the marker / board as built, in the sketch frame:
   *  16 numbers, row-major 4x4, mm (the Joint Origin) */
  origin: number[];
  label: PlacedLabel | null;
  summary: string;           // one line: "Grid 2×3 DICT_4X4_50 #0–5 · 16.2 mm · outer 41.0 × 60.5 mm"
  warnings: Issue[];
}

/** A good value set with a short reason (Zach: "give me some options and
 *  perhaps short reason as to why it's suggested"). Picking one sets auto false. */
export interface Suggestion {
  label: string;             // "2×1 @ 28.0 mm"
  reason: string;            // "largest marker", "best fill", "cells = 4 lines of 0.675 mm", ...
  params: Pick<MarkerParams, "cols" | "rows" | "marker_mm" | "checker_mm" | "separation_mm">;
}

export interface SheetRequest {
  items: PlanRequest[];      // every marker to print, each with its own label
  cut_lines: boolean;
}

/** True-scale pages for the preset's paper. svg pages use mm units. */
export interface Sheet {
  pages: number;
  svg: string[];
  pdf_base64: string;
  warnings: Issue[];
}

export interface DictionaryInfo { name: string; capacity: number; bits: number }

export interface CoreInfo {
  core_version: string;      // aruco_studio version + git describe when packed
  python: string;
  pyodide: string;
  dictionaries: DictionaryInfo[];
}

export interface CoreApi {
  info(): Promise<CoreInfo>;
  presets(): Promise<Preset[]>;
  /** the largest clear axis-aligned rectangle in a profile; holes "avoid" keeps
   *  it off the holes, "ignore" treats the outer loop only. null = nothing fits */
  inscribe(profile: Profile, holes: "avoid" | "ignore"): Promise<Rect | null>;
  plan(req: PlanRequest): Promise<MarkerPlan>;
  suggest(req: PlanRequest): Promise<Suggestion[]>;
  /** one marker at true size (mm units), with its label */
  svg(req: PlanRequest): Promise<string>;
  sheet(req: SheetRequest): Promise<Sheet>;
}

export type CoreState = "loading" | "ready" | "error";
export interface CoreStatus { state: CoreState; detail?: string; ms?: number }
