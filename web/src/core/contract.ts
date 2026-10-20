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
   *  does not fit; the plan then reports overflow_mm and a red warning.
   *  A SET value is always honoured, Auto or not (Zach, 2026-10-20: "we should
   *  always have complete control… even if it wouldn't print properly or would
   *  go outside the rectangle"): with auto true and checker_mm or separation_mm
   *  set, those are drawn as typed and only the unset numbers are derived. */
  auto: boolean;
  marker_mm: number;         // the black marker's side (auto = false)
  checker_mm: number;        // ChArUco square side; 0 = the core's default for marker_mm
  separation_mm: number;     // grid gap between markers; 0 = the core's default rule
  cols: number;              // grid / ChArUco; 1 for single
  rows: number;
  turn: Turn;                // which way is up: turns the marker in 90 degree steps
  /** turn the marker over: the outward side (Z) becomes the other one. Barrier 10
   *  (Zach, 2026-10-20 night): it ALWAYS applies, on a reference face too -- the
   *  reference face is only the background helper that picks the starting side. */
  flip: boolean;
  quiet_modules: number;     // white border in modules (cells); 1 by default
  corner_mark: CornerMark;   // a triangle in the quiet zone's top-left corner
  /** ChArUco only (Zach, 2026-10-18): put the Joint Origin at the centre of
   *  board square [col, row] (0-based from OpenCV's origin corner) instead of
   *  OpenCV's board corner. null / absent = the corner. */
  origin_square?: [number, number] | null;
}

export type LabelSide = "below" | "above" | "left" | "right";
/** Where the label goes (Zach, 2026-10-20): ON the marker (in its black border
 *  row, the text knocked out white, or in its white quiet zone, black text), or
 *  OUTSIDE it (the band inside the rectangle, as before). `side` picks the edge
 *  in both cases. Default "on_marker". */
export type LabelPlace = "on_marker" | "outside";
export type LabelSurface = "black" | "white";

/** The label lives INSIDE the marker rectangle (Zach, 2026-10-18: "the outer
 *  rectangle … efficiently define[s] the outbounds and then the feature will
 *  take care of populating everything inside of it"). The core reserves a band
 *  on `side` for the text and fills the rest with the marker. */
export interface LabelParams {
  on: boolean;
  /** placeholders: {id} {first} {last} {ids} (e.g. "0-5") {dict} {type};
   *  "\n" breaks lines (multi-line labels) */
  text: string;
  height_mm: number;         // cap height; 0 = driven: one cell (module) of the marker, so it fits a border row
  place?: LabelPlace;        // default "on_marker"
  surface?: LabelSurface;    // on_marker only: the black border row (default) or the white quiet zone
  side: LabelSide;           // the preset spot: the band inside the rectangle on that side
  gap_mm: number;            // between the label band and the marker
  offset_mm: Vec2;           // x, y from the preset spot (typed, or a drag on the canvas)
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

/** What the sticker is cut to (Zach, 2026-10-18): the whole profile, the
 *  marker rectangle (default: "we draw the outer allowed shape, and expect a
 *  sticker that is that shape"), or just the marker (its quiet zone). Everything
 *  inside the cut is white; exports always carry that white. */
export type Trim = "profile" | "marker"
  /** deprecated (2026-10-20 evening): reads as "profile"; old files and shells only */
  | "rectangle";

/** THE MODEL (Zach, 2026-10-20 evening: "go back to just profile… behaving more
 *  like an extrude"): the input is a PROFILE. The core places the marker in it
 *  (the largest clear box, holes avoided or ignored). To place a marker by hand,
 *  draw a rectangle and use it as the profile: a rectangle profile (rotated too)
 *  is used exactly. Trim: the profile (default) or just the marker; a rectangle
 *  sticker is a rectangle profile trimmed to profile. */
export interface PlanRequest {
  trim?: Trim;               // default "profile"
  /** the profile the marker goes in (outer loop first, then holes) */
  profile?: Profile;
  holes?: "avoid" | "ignore";  // default "avoid"
  /** legacy: the box to place in. The core fits one in `profile` when this is
   *  absent (and returns it as MarkerPlan.fit_rect); the UI stops sending it in
   *  the profile-first lane, which also makes this field optional. */
  rect?: Rect;
  marker: MarkerParams;
  label: LabelParams;
  preset: Preset;
  /** a face (body) under the profile: it picks which side is out (Z) -- a helper
   *  only; marker.flip turns it over (barrier 10) */
  reference_face: boolean;
  /** the heights (barrier 10). Absent or partial = driven from the preset. */
  extrude?: ExtrudeParams;
}

/** The heights of an ArUco Extrude (contract barrier 10, Zach 2026-10-20 night:
 *  "for inkjet you just get to set paper thickness (but its autofilled from the
 *  preset); for 3D printer you get to set the white height and black height.
 *  black height is always measured from the outer face of the white").
 *  Every field is optional: unset = DRIVEN (from the preset; the plan returns
 *  the value it used in MarkerPlan.extrude, the UI shows it grey); a set value
 *  is always honoured, even one that prints badly (an issue says so). Heights
 *  are along the outward side, mm. Flush (the black inlaid into the white from
 *  its outer face) is the only placement in v1 (CF-8). */
export interface ExtrudeParams {
  /** 3D print: which colours are made. "auto" (driven): black only on a
   *  reference face (the body is the white), both in open space */
  mode?: "auto" | "both" | "black" | "white";
  /** 3D print: the white tile, from the face (z 0) to its OUTER face (z white_mm) */
  white_mm?: number;
  /** 3D print: the black's height, measured from the white's outer face into it
   *  (black only: from the face itself, into the body) */
  black_mm?: number;
  /** inkjet: the paper / vinyl thickness (driven: preset.thickness_mm) */
  paper_mm?: number;
}

export type IssueLevel = "info" | "warn" | "error";
/** field: "marker.<key>", "label.<key>", "rect", "preset" or "tag" (the whole
 *  marker). The panel shows each issue under its row (per-line validation).
 *  Nothing is refused: an over-size marker is drawn and flagged "error" (red). */
export interface Issue { field: string; level: IssueLevel; text: string; key?: string /* which item, in multi-item calls */ }

export interface PlacedLabel {
  text: string;
  at: Vec2;                  // the text's centre, sketch frame
  height_mm: number;         // cap height
  angle_deg: number;
  lines?: string[];          // the text split on "\n"
  lines_at?: Vec2[];         // each line's centre, sketch frame (a CAD shell places one text per line)
  /** inkjet: "sans" (ordinary text); 3D print: "pixel" (blocky strokes a
   *  nozzle can print, given as `polygons`) */
  font?: "sans" | "pixel";
  polygons?: Polygon[];      // the pixel font's ink, sketch frame (empty for sans)
  box?: Loop;                // the label's band inside the rectangle, sketch frame
}

/** A dimension the canvas draws (and lets you type into): what it measures,
 *  between two points in the sketch frame, drawn offset_mm to the left of a->b. */
export interface Dimension {
  field: string;             // what typing into it sets: "marker.marker_mm", "rect.w", ...
  value_mm: number;
  a: Vec2;
  b: Vec2;
  offset_mm: number;
}

export interface MarkerPlan {
  ok: boolean;
  ids: number[];
  // geometry, already placed in the sketch frame (rect centre, angle, turn, flip)
  black: Polygon[];          // the ink
  outer: Loop;               // the white outline (quiet-zone edge)
  cut?: Loop;                // the sticker's cut line (outer loop), per `trim`: rectangle, profile or marker
  cut_shape?: Polygon;       // the same with holes (a profile's holes are cut out); white fills it
  outer_mm: Vec2;            // its width and height in the marker's own frame
  marker_mm: number;
  checker_mm: number;        // 0 unless ChArUco
  separation_mm: number;     // 0 unless grid
  cols: number;
  rows: number;
  cell_mm: number;           // one module (bit) of the marker
  auto: boolean;             // the size came from auto
  overflow_mm: number;       // how far the outline pokes past the rectangle; 0 = fits
  /** the box the core placed the marker in (fitted in the profile, or the
   *  request's rect); dims, the label band and overflow are measured against it */
  fit_rect?: Rect;
  /** barrier 10: the heights as planned, driven or set (`layers` z follows
   *  them); `driven` names the fields the request left unset */
  extrude?: { method: Method; mode: "both" | "black" | "white"; white_mm: number;
              black_mm: number; paper_mm: number; flipped: boolean;
              driven: ("mode" | "white_mm" | "black_mm" | "paper_mm")[] };
  /** OpenCV's frame of the marker / board as built, in the sketch frame:
   *  16 numbers, row-major 4x4, mm (the Joint Origin) */
  origin: number[];
  label: PlacedLabel | null;
  dims?: Dimension[];        // marker size, checker, separation, outer, rectangle, label offset
  // ---- for CAD shells (the Fusion adapter, 2026-10-18 N-6 report) ----
  /** the bodies as built: z along the face normal (mm, 0 = the face plane,
   *  + out of it), op "add" | "cut" | "keep", polygons in the sketch frame.
   *  Inkjet rule 2: paper [0, t], ink pocketed into it; 3D print: the recess. */
  layers?: { name: string; part: string; colour: "white" | "black" | "none"; op: "add" | "cut" | "keep";
             z: [number, number]; polygons: Polygon[];
             /** a cut / keep layer: the `name` of the layer it cuts into ("face" = the host body) */
             into?: string }[];
  /** the black as axis-aligned boxes [u0, v0, u1, v1] in the PATTERN frame
   *  (convex pieces a B-rep kernel can extrude), and the 16-number row-major
   *  4x4 taking that frame to the sketch (rect centre, angle, turn, flip) */
  cells?: [number, number, number, number][];
  pattern_to_sketch?: number[];
  /** where the Joint Origin (`origin`) sits along z, mm (the detector's plane:
   *  the printed surface) */
  origin_z_mm?: number;
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

/** Auto layout (Zach, 2026-10-18): "tight" packs the stickers edge to edge so
 *  neighbours share cut lines (the fewest cuts); "spaced" is the same packing
 *  with gap_mm of padding round every sticker. */
export type SheetMode = "tight" | "spaced";

export interface SheetRequest {
  items: PlanRequest[];      // every marker to print, each with its own label
  cut_lines: boolean;
  mode?: SheetMode;          // default "spaced"
  /** the PDF asks the viewer to open the print dialog when it opens */
  print_dialog?: boolean;
  gap_mm?: number;           // spaced only; default the core's
  /** what the packer optimizes first (Zach, 2026-10-18: "fewest cut lines"
   *  or "most compact (fewest number of sheets)"); default "fewest_sheets" */
  objective?: "fewest_cuts" | "fewest_sheets";
}

/** True-scale pages for the preset's paper. svg pages use mm units. */
export interface Sheet {
  pages: number;
  svg: string[];
  pdf_base64: string;
  warnings: Issue[];
  cuts?: number;             // straight cuts to free every sticker (a shared edge counts once)
  fill?: number;             // 0..1: sticker area / printable area, over all pages
  /** where each request item landed: page (0-based), its sticker box on the
   *  page (mm, y down, from the page's top-left), and its turn */
  placements?: { item: number; page: number; x_mm: number; y_mm: number; w_mm: number; h_mm: number;
                 rotation: 0 | 90 }[];
}

/** Verify accuracy: a simulated camera looks at the marker as planned. */
export interface Camera {
  distance_mm: number;       // marker to camera
  resolution: Vec2;          // sensor width, height in px
  hfov_deg: number;          // horizontal field of view
}

/** One simulated view. Every knob 0 = a perfect view. */
export interface ViewConditions {
  camera: Camera;
  tilt_deg: number;          // rotation about the marker's x axis (perspective)
  yaw_deg: number;           // rotation about the marker's y axis
  blur_px: number;           // Gaussian blur sigma, sensor px
  noise: number;             // 0..1 sensor grain
  glare: number;             // 0..1 a specular patch's strength
  occlusion: number;         // 0..1 share of the marker covered by dirt / a finger
  seed: number;              // makes noise, glare and occlusion repeatable
}

export interface VerifyResult {
  ok: boolean;               // every printed id found and no wrong id
  found: number[];
  missing: number[];
  wrong: number[];           // detected ids the marker does not print
  px_per_cell: number;       // one module's size on the sensor
  pose_error_mm: number | null;   // board / marker pose vs truth (null = not estimated)
  pose_error_deg: number | null;
  image_png_base64: string;  // the simulated view with the detections drawn
  notes: string[];
}

/** The calculator: will this camera read this marker at this distance? */
export interface Readability {
  px_per_cell: number;
  max_distance_mm: number;   // the farthest the camera still reads it (head on)
  verdict: "good" | "marginal" | "poor";
  text: string;              // one plain line: why
  /** true: max_distance_mm measured with the OpenCV simulator; false: the
   *  analytic fallback (no OpenCV, e.g. inside a CAD's Python) */
  measured?: boolean;
}

/** Auto id (Zach, 2026-10-18): a stable key per marker feature, hashed to a
 *  preferred first id; unique across the document by default; a typed id wins. */
export interface IdItem {
  key: string;               // stable: never changes for this marker (the feature's id by default)
  type: MarkerType;
  dictionary: string;
  count: number;             // markers this feature prints (cols × rows for a grid; ChArUco's count)
  first_id: number | null;   // null = driven (auto); a number = set by hand
}

export interface IdAssignment {
  key: string;
  first_id: number;
  ids: number[];
  driven: boolean;           // true = chosen by the core, false = as typed
}

export interface IdRequest {
  items: IdItem[];
  ledger?: Record<string, number>;   // key -> first id already given out: those never move
  /** ids that must never be handed out (e.g. markers already printed by an
   *  older tool). A plain list reserves the ids in EVERY family; a map
   *  reserves them per dictionary family ("4x4", "5x5", ...: core.numbering.family) */
  reserved?: number[] | Record<string, number[]>;
  /** Re-ID (Zach, 2026-10-20: "lots of markers on a page and then re-id them"):
   *  "hash" (default) keeps today's stable hashed ids; "sequential" numbers the
   *  driven markers in document order from `start`, each grid / board a
   *  contiguous range. `fresh` ignores the ledger so every driven id is given
   *  out anew (the returned ledger replaces the old one). Typed ids always win. */
  mode?: "hash" | "sequential";
  start?: number;
  fresh?: boolean;
}

export interface IdResult {
  items: IdAssignment[];
  ledger: Record<string, number>;    // the updated ledger to store in the document
  warnings: Issue[];         // e.g. a typed id that collides; Issue.key names the item
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
  /** render the plan as a camera would see it and run OpenCV's detector on it
   *  (OpenCV loads on the first call) */
  verify(req: PlanRequest, view: ViewConditions): Promise<VerifyResult>;
  readable(req: PlanRequest, camera: Camera): Promise<Readability>;
  assign_ids(req: IdRequest): Promise<IdResult>;
}

export type CoreState = "loading" | "ready" | "error";
export interface CoreStatus { state: CoreState; detail?: string; ms?: number }
