# M8: a mini CAD, file first (design note, 2026-10-16 night)

A plan, nothing built. It turns `docs/feedback/2026-10-16-mini-cad-file-first.md` (MC-1..MC-12) and Zach's ~21:00 addition (the Studio connected end to end: "Send to PrusaSlicer", the Print button, accuracy proven) into work for ArUco Studio. It sits on `M6_stickers_profiles_print.md` (M6a..M7) and orders itself with it in `docs/design/ROADMAP.md`.

| | |
|---|---|
| Written against | ArUco Studio `main` at `4cc74be` (M1-M4 built, the audit fixes in); REF = cad-exporter `aruco-fusion-plugin-0e9bcb` at `9829cd4`, read only; PrusaSlicer 2.9.6's config folder on this box, read only |
| Keeps | every versioned rule as it is: `SPEC_VERSION 2`, `CELL_RULE 1`, label `RULE 2` (+ 3 from M6), `ORIGIN_RULE 2`, trim `RULE 1`, `MAKE_RULE 1`, `bam_aruco_presets/1`, `arucostudio.tagspec/1`, `arucostudio.tagplan/1`. The scene file goes to `arucostudio.scene/2` with a migration from `/1` |
| Zach's direction | Studio first. "Nothing great or robust was ever built Fusion native." Fusion is a downstream adapter (M7), lower priority than every Studio milestone |
| What the Studio is for | a way for a person or an AI to make tests of the algorithms, and to prove the interaction before it goes into CAD (MC-8, MC-12) |

## 0. The plan in one paragraph

**The file is the model.** A scene is one JSON text file holding sketches (rectangles, circles, polygons, slots, with holes), features (Extrude, ArUco Extrude) and the ids. A person or an AI types it; the Studio watches it, draws it and edits it; every Studio action writes it back. Shapes compile straight into `Target.loops_mm`, extrudes into the body under a face, ArUco Extrudes into today's `TagSpec`, so `plan_tag`, the numbering, the sheet, the exports and all 824 goldens run unchanged. **The Studio is a bare-bones mini CAD:** draw, select, move, rotate and edit shapes in 2D; Extrude; ArUco Extrude on a shape or a face is the one way to add a tag (the target editor goes); markers re-place live as a shape changes; a bottom toolbar with hotkeys; S opens a command palette; drag in 3D with one gizmo. Nothing else: no constraints, no fillets, no booleans beyond holes, no assemblies. **The library:** our own sketcher on `plan/region.py` + SVG + three.js; the browser never computes loops; replicad is the fallback for the day we need B-rep on screen. **The UI kit:** Fusion's look goes; a compact modern kit (the cockpit's stack) renders the FIELDS from one definition (`plan/fields.py`) that the Fusion dialog reads too. **PrusaSlicer:** the physical printers, resolved to the printer preset's nozzle and the print presets that fit, watched live; and **Send to PrusaSlicer**: a 3MF project with the colours on their extruders, opened in PrusaSlicer, sliced headless in the tests and checked against the plan.

## 1. The file (MC-1, MC-2, MC-9)

### 1.1 JSON, not a DSL

| | JSON (chosen) | A terse DSL |
|---|---|---|
| Typed by an AI | reliably; every model knows it | needs the grammar in its context every time |
| Typed by a person | fine for a file of 20 lines, which is what these are | nicer, at the price of a parser |
| Parser, errors, line numbers | the standard library; `json.JSONDecodeError` gives line and column | ours to write and keep |
| Today's file | `.arucostudio.json` is JSON already (`scene/file.py`, migrations by schema number) | a second format beside it |
| Types from the server | the OpenAPI types the Studio generates (`npm run types`) cover it | hand-written |
| Comments | none (a `"note"` key is allowed anywhere and kept) | yes |

So: **JSON, kept short by a small vocabulary** (a rectangle is `"rect": [80, 50]`, not forty coordinates) and by **sugar keys** on a tag (`"layout": "charuco", "cols": 5`) that expand to the exact `settings` / `numbers` on load. Strict JSON, read by the standard library, the same extension `.arucostudio.json`, schema `arucostudio.scene/2`.

### 1.2 The vocabulary

Units are mm; angles degrees, counter-clockwise; frames x right, y up; z out of the sketch plane. Every `id` is a short string, unique in the whole file (sketches, shapes and features share one namespace); references are bare ids.

**The file**

| Key | Holds |
|---|---|
| `schema` | `"arucostudio.scene/2"` |
| `name` | the scene's name |
| `preset` | the default print preset of every tag that names none (a Library name) |
| `sheet` | the sticker sheet's defaults: `{"page": "letter", "mode": "spaced"}` (M6 §f) |
| `sketches` | `[sketch]` |
| `features` | `[feature]` in order |
| `overrides`, `ledger` | as `/1`: typed ids per tag name, and the ledger (printed ids never move) |
| `note` | free text, anywhere, kept |

**A sketch**: `{"id", "at": [x, y], "rot": deg, "shapes": [shape]}`. `at` and `rot` place it on the canvas (default `[0, 0]`, `0`).

**A shape**: one of the five below, with `"id"`, `"at": [x, y]` (its centre, in the sketch), `"rot"`, `"name"`, and `"holes": [shape]` (inner shapes, cut out; a hole never has holes).

| Shape | Written as | Loops it becomes |
|---|---|---|
| rectangle | `"rect": [w, h]` | the box: stored as `loops_mm = []` when it has no holes (today's convention, `plan/target.box`), else 4 points counter-clockwise from the bottom-left corner plus the holes |
| circle | `"circle": d` (diameter) | stroked at the chord tolerance `CHORD_MM` (0.05 mm, M6 §b), the way Fusion strokes an edge (`core.faces._arc_pts`) |
| polygon | `"polygon": [[x, y], ...]` | as typed, made counter-clockwise |
| slot | `"slot": [length, width]` | two lines and two half circles; `length` is the overall length |
| loops | `"loops": [[[x, y], ...], ...]` | verbatim (the outer first, then holes): what a `/1` file, a Fusion face or a build123d face carries in |

**A feature**: one of two.

| Feature | Written as | Does |
|---|---|---|
| Extrude | `{"id", "extrude": "<shape>", "height": h}` | the shape's prism from z 0 to `h` (negative: downwards): a body. Its faces are `<id>.top`, `<id>.bottom`, and `<id>.side<i>` for each straight edge `i` of the outer loop; a `rect` also names them `front` (-y), `right` (+x), `back` (+y), `left` (-x). A circle's side is curved and has no face |
| ArUco Extrude | `{"id", "aruco": "<shape> or <body>.<face>" or a list of them, ...}` | a tag on that profile or face: today's `TagSpec`. A list makes one tag per face with the same settings (FB-14, the forearm), named `<id>.<face>` |

The keys of an ArUco Extrude:

| Key | Writes | Note |
|---|---|---|
| `preset` | the print settings a preset carries (cells, mode, op, heights, label nozzle, make) | a Library name; absent = the file's `preset`, else Default |
| `layout`, `dictionary` | `settings.layout`, `settings.dictionary` | |
| `id` | `overrides[<name>]` | a typed first id is an override (fixed); absent = auto-numbered |
| `size`, `square` | `numbers.size`, `numbers.square` | 0 or absent = Auto |
| `cols`, `rows` | `settings.force` | |
| `turn`, `mark`, `pins`, `holes`, `perimeter`, `mode`, `op` | the settings key of the same meaning (`turn`, `corner_mark`, `pin`, `holes`, `make.perimeter` / `trim`, `mode`, `op`) | the M6 rows included |
| `label` | `settings.label` | a string is the content (`"#id"`, `"#id + name"`, `"name"`, or custom text); an object is `LabelSettings` keys |
| `name` | `name` (the label's `{name}`) | |
| `over` | `target.kind = "profile"` with that body under it | a sketch area over a body, Fusion's case; the `/1` migration writes it |
| `settings`, `numbers` | the exact dicts, over everything above | what the Studio writes |

Sugar expands through `server/newtag.new_spec` (what today's dialog stores for a fresh tag: `origin_v`, the label's `rule`, `cells` from the preset, Auto Extrude resolved against the target), so a typed file gets exactly what a Fusion dialog would store. **On its first write the Studio replaces the sugar with the exact `settings` and `numbers`**: a hand-typed file stays short until the Studio touches it; after that it is exact and round-trips bit for bit. Unknown keys are kept and reported as `info`.

### 1.3 Three complete files

**A plate with a hole and a ChArUco on it**

```json
{
  "schema": "arucostudio.scene/2",
  "name": "plate with a ChArUco",
  "preset": "0.32mm SPEED @MK4IS 0.6 - Aruco",
  "sketches": [
    {"id": "sk", "shapes": [
      {"id": "plate", "rect": [80, 50], "holes": [{"circle": 18}]}
    ]}
  ],
  "features": [
    {"id": "body", "extrude": "plate", "height": 5},
    {"id": "tag", "aruco": "body.top", "layout": "charuco", "cols": 5, "rows": 3,
     "mark": "triangle", "label": "#id + name", "name": "plate"}
  ]
}
```

**The 1-DoF forearm: a box with tags on four faces**

```json
{
  "schema": "arucostudio.scene/2",
  "name": "forearm, 1-DoF arm",
  "preset": "0.32mm SPEED @MK4IS 0.6 - Aruco",
  "sketches": [
    {"id": "sk", "shapes": [{"id": "outline", "rect": [120, 40]}]}
  ],
  "features": [
    {"id": "forearm", "extrude": "outline", "height": 40},
    {"id": "tag", "aruco": ["forearm.front", "forearm.right", "forearm.back", "forearm.left"],
     "layout": "charuco", "cols": 5, "rows": 2, "mark": "triangle",
     "label": "#id + name", "name": "forearm"}
  ]
}
```

Four tags: `tag.front`, `tag.right`, `tag.back`, `tag.left`; the front and back faces are 120 x 40, the ends 40 x 40; each gets its own largest clear rectangle; Renumber makes the ids unique. The Studio's multi-select edit writes them back as one feature while they stay the same, and splits the list into four features the moment one differs.

**A sticker sheet**

```json
{
  "schema": "arucostudio.scene/2",
  "name": "stickers for the rack",
  "preset": "Sticker · Letter · 600 dpi",
  "sheet": {"page": "letter", "mode": "tight"},
  "sketches": [
    {"id": "sk", "shapes": [
      {"id": "a", "rect": [30, 30], "at": [0, 0]},
      {"id": "b", "rect": [30, 30], "at": [40, 0]},
      {"id": "c", "rect": [60, 40], "at": [0, 50]},
      {"id": "d", "circle": 50, "at": [80, 50], "holes": [{"circle": 6}]}
    ]}
  ],
  "features": [
    {"id": "t1", "aruco": "a", "layout": "single", "label": "#id"},
    {"id": "t2", "aruco": "b", "layout": "single", "label": "#id"},
    {"id": "t3", "aruco": "c", "layout": "grid", "cols": 2, "rows": 1},
    {"id": "t4", "aruco": "d", "layout": "charuco", "cols": 4, "rows": 4,
     "perimeter": "profile", "holes": "avoid"}
  ]
}
```

A tag on a bare shape with a sticker preset is a sticker (M6 §a: the preset is the machine); `t4` keeps the disc's outline as its cut line.

### 1.4 How it maps onto Target / TagSpec / Scene

`scene/design.py` compiles the file: `compile(doc) -> (Scene, [Issue])`. The result is **today's `Scene`** (`scene/model.py`), so nothing after it changes.

| File | Becomes | Through |
|---|---|---|
| a shape | `Target.loops_mm`: the outer loop, then its holes (MC-2) | `plan/shapes.py` `stroke(shape) -> loops` (new; the circle and slot arcs by `core.faces._arc_pts` at `CHORD_MM`), then `plan/target.from_loops` |
| an ArUco Extrude on a bare shape | `Target(kind="free")`: w, h from the loops' box, no body | `from_loops(loops, 0)` |
| on `<body>.top` | `Target(kind="face")` with the body under it: the outline extruded down `height` | a `rect` without holes through `plan/target.box(w, h, height)`, everything else through `from_loops(loops, height, centre=False)`: **the same calls, in the same cases, as today's `POST /api/target`**, so the Target and every M3 / e2e plan are byte for byte what the target editor made |
| on `<body>.bottom` | the same loops mirrored (u -> -u), `z_sign = -1`, the body above | `from_loops` + the flip |
| on `<body>.side<i>` | a box: `w_mm` = the edge's length, `h_mm` = `height`, loops `[]`, `has_body`, `body_mm = {u0 -w/2, u1 w/2, v0 -h/2, v1 h/2, z0 -depth, z1 0, depth, measured true}` where `depth` is the body's extent along the inward normal; `body_loops_mm` null | the face frame: u along the edge (the outer loop runs counter-clockwise, so the outward normal is to its right), v = +z (up), n outward; the frame is right-handed |
| the tag's sugar + `settings` / `numbers` | `TagSpec.settings`, `.numbers`, `.name`, `.key = <id>` | `server/newtag.new_spec`, then the exact dicts laid over |
| the feature's `id` | `SceneTag.name` (the numbering path) and its `uid` (the ledger's stamp) | a `/1` file's random `uid` is kept under `"uid"` so its ledger survives |
| the sketch's `at` / `rot` and the face frame | `SceneTag.pose` (a 4x4, mm) | the sketch pose times the face frame; a z-up tag still fills `x_mm`, `y_mm`, `rotation_deg` as `/1` does |
| `id` (typed) | `Scene.overrides[name]` | |
| `preset` | `presets_used` | |

What `prism_volumes` gives a side face: body = w x h x depth, exact for a rectangle's extrude, an upper bound for a polygon's (the trim may then refuse with an `info` saying so).

Issues of the compile carry a `where`: the JSON path (`features[1].aruco`), and for a parse error the line and column. The compiled scene's own messages (overlaps, `scene/checks.py`) stay as they are.

**Views.** The 2D canvas draws the sketches in plan view and every z-up tag in place (today's drawing, from the plan). A tag on a side face is drawn **unfolded about its edge**, like the net of a box, with a dashed hinge line: the 2D view stays what prints and what is cut. The 3D view places every tag by its full pose, standing on its face.

### 1.5 Versioning

| Rule | |
|---|---|
| The schema string | `arucostudio.scene/2`; `scene/file.py` `KNOWN` lists it; `MIGRATIONS["arucostudio.scene/1"]` turns a `/1` document into `/2` (each tag: a sketch at the tag's pose holding one `loops` shape (its target's loops; a box target writes `rect`), an Extrude when the target had a thickness, an ArUco Extrude with the exact `settings` / `numbers`, `over` for a profile over a body, `uid` kept). A `/1` file replans identically after migration: a test replays the e2e's saved scenes |
| Writers | always write `/2`, `indent=1, sort_keys` as today, so diffs are small |
| A newer schema | refused with today's message ("saved by a newer ArUco Studio?") |
| Unknown keys | kept and written back; `info` on the key's path |
| An unknown feature kind | `error` on that feature; the rest compiles |
| The versioned rules | untouched. A tag's `settings` / `numbers` are the record; `record_digest` of a compiled tag equals the digest of the same tag made through `/api/new` + `/api/target` (M8a.1) |

### 1.6 Live reload: the file is the truth

| | |
|---|---|
| The watcher | `server/watch.py` (new, standard library): every 250 ms it stats the open file; a changed (mtime, size) pair is read, hashed (sha256 of the text) and compared with the last text the server wrote or read. The same hash is ignored (an editor that touches the file; a cloud sync that bumps mtimes). Why polling and not `ReadDirectoryChangesW`: no dependency, one file, deterministic in tests, and a stat a quarter second costs nothing |
| A change | parse, compile, replace the scene in memory, bump `revision`, push an event. The Studio refetches `GET /api/scene?plans=1` (the plan cache keyed by the spec's JSON replans only what changed) |
| The push | **Server-sent events**: `GET /api/events` (`text/event-stream`, FastAPI `StreamingResponse`; browsers reconnect by themselves; no websocket dependency; one direction is all we need since the app already writes over HTTP). Events: `hello` (the revisions on connect), `scene {revision}`, `prusa {what changed}` (section 5), `presets` |
| The Studio's own writes | every committed action writes the file (atomic: a temp file beside it, then `os.replace`, as `store.write_atomic`), then records the new hash, so its own write is never read back as an external change. There is no dirty state and no Save: Undo and Redo are a history of texts; "Save as…" copies the file; Ctrl+S is a no-op that says "saved as you typed" |
| A broken file | a half-typed edit that does not parse: the Studio keeps the last good scene, a bar reads "line 12 col 7: expecting ']'", and **the Studio refuses to write** until the file parses again, so it never clobbers a half edit. A file that parses but compiles with errors: drawn as far as it goes, the errors on their features |
| The file goes away | deleted or renamed: the bar says so; writes stop; "Save as…" rewrites it |
| Two writers | the Studio writes only after a read whose hash matches the one it last saw; a mismatch (the file changed under it since the last event) reloads first and drops the action with a message. Debounce: an editor that writes twice (a temp, then a rename) gives two events; the second is a no-op by hash |
| Where the file lives | anywhere Zach says (`POST /api/design/open {path}`; `python -m aruco_studio.server --open <path>`), not only `scenes/`; a path under `%USERPROFILE%\CADExporter` is refused as today |
| The text in the Studio | a drawer tab **File**: the raw text, read only, the selection's JSON path highlighted, the parse error's line marked, a **Reveal** button (the OS file browser). Editing stays in the editor of Zach's choice; the AI writes the file directly |
| A CLI for an AI loop without a browser | `python -m aruco_studio check <file>` (compile, print every Issue with its path, exit 1 on an error), `... render <file> --svg out.svg` (the 2D top view of every tag), `... plan <file> --json` (every tag's TagPlan) |

## 2. The mini CAD (MC-1, MC-3..MC-8)

### 2.1 Tools

| Tool | Key | In 2D | In 3D |
|---|---|---|---|
| Select / move | V | click, Shift+click, marquee; drag moves (0.5 mm snap); handles on the selection | click a body or a tag; drag with the gizmo (2.4) |
| Rectangle | R | drag a box (Alt from the centre, Shift square); or press R and type `80 50` Enter | — |
| Circle | C | drag a diameter; or type `50` Enter | — |
| Polygon | P | click the points; Enter or the first point closes | — |
| Slot | O | drag the length, then the width; or type `40 12` | — |
| Hole | H | click inside a shape: a round hole (type the diameter; Shift+H a rectangular one) | — |
| Extrude | E | the selected shape; type the height or drag the arrow in 3D; the view goes 3D | the arrow on the top face |
| ArUco Extrude | A | click a shape; Shift+click more; Enter. The tag appears placed (Auto size, the file's preset) and the inspector opens on it | click a face (top, bottom, a side); Shift+click more; Enter |
| Rotate 90° | `]` / `[` | the selection, clockwise / counter-clockwise | the same |
| Search | S | the command palette: every command and tool by name, with its key; Enter runs it | the same |
| Duplicate, Delete, Undo, Redo, Select all, Fit, 2D / 3D | Ctrl+D, Del, Ctrl+Z / Ctrl+Y, Ctrl+A, F, Tab | as today | |
| Cancel / confirm | Esc / Enter | | |
| Keys | ? | the map | |

The single-letter toggles of today (quiet zones Q, axes A, outlines L, verify V) move into the palette and the View menu; the letters go to the tools. `S / G / C` no longer add tags: A does, and the layout is a row of the inspector (or the palette's "ArUco: single / grid / ChArUco").

### 2.2 Editing a shape

| | |
|---|---|
| Handles | a rectangle: 8 (corners resize both sides, edges one); a circle: one on its rim; a polygon: its vertices (drag; Alt+click adds a vertex on an edge, Del removes one); a slot: its two ends and one on the width; every shape: a rotation handle past its top edge; a hole: the same handles inside its parent |
| Typing | the inspector shows the shape's fields in the kit's form (section 4): `at`, `rot`, `w`, `h`, `d`, `length`, `width`, the holes as rows; Enter commits, Esc reverts |
| Snap | the 0.5 mm grid (today's), plus shape centres and edges when within 6 px; Alt turns snapping off |
| Moving a sketch | moving every selected shape of one sketch moves the sketch's `at`; otherwise the shapes' own `at` |
| What writes the file | the release of a drag, Enter in a field, a tool's commit. During a drag the Studio asks the server for a **preview** compile (`POST /api/design/preview`: the text in, the scene with plans out, nothing written), throttled to 15 Hz |

### 2.3 Live re-placement (MC-5)

Every tag on an edited shape or body replans at once: the compile gives it a new `Target`, `plan_tag` runs (the fit, the label, the trim), the canvas redraws the plan. Budget: an edit to a redraw under 100 ms for ten tags on simple shapes, measured in M8b1 (the fit of a 96-point disc with three holes is under 50 ms, M6a.10). A tag whose shape no longer fits anything shows the plan's refusal in orange on the shape and the message under Size, as today.

### 2.4 Dragging in 3D (MC-7)

| | |
|---|---|
| The gizmo | three.js `TransformControls` (ships in `three/examples/jsm`, no new dependency): translate in X and Y (`showZ = false`), rotate about Z; `setTranslationSnap(0.5)`, `setRotationSnap(15°)`; OrbitControls paused during a drag, as the standard pattern does |
| What moves | a sketch (its bodies and tags go with it): the gizmo writes the sketch's `at` / `rot`. A tag cannot be dragged off its face: its place is the fit's |
| The extrude arrow | a second small handle on a body's top face, dragged along the normal in 0.5 mm steps, like Fusion's Extrude: writes `height`; the tags on its sides grow with it |
| The size arrow and the label | the v2 dialog's arrow (REF `design_aruco_ui_v2.md` §4.1) and the label drag of today's 2D canvas come to 3D later; not in M8 |

### 2.5 Out, on purpose (MC-8)

| Out | Why not now |
|---|---|
| Constraints (a solver) | shapes are numbers; a person types them, an AI types them. A solver is iterative, hard to keep bit-stable against goldens, and the one thing that makes a sketcher big. The file has no place for a constraint, so there is nothing to draw |
| Fillets | a rounded corner changes no tag placement worth having; a rounded profile can be typed as a polygon or carried in as `loops` from Fusion / build123d |
| Booleans beyond holes | a profile = one outer loop + holes is exactly `Target.loops_mm`; a union would need `region.py` at edit time and a second idea of what a shape is. The Fusion adapter never needs it: Fusion gives faces |
| Assemblies, several parts posed to each other | one file is one part's worth of sketches on one canvas. The relative poses of tags are what a marker calibration measures anyway (Zach, FB); Cad2Robot and build123d own assemblies |
| Arcs and splines as sketch primitives | a circle and a slot cover the cases; anything else comes in as `loops` |
| A sketch on a face (pockets, a tag on a sketch area over a body) | `over` carries the Fusion case in a file; drawing it is not needed to test the algorithms |
| Revolve, sweep, several bodies in one boolean | not what a tag needs |
| True nesting, fit at any angle | M6's `ST-SHEET-NEST`, `ST-FIT-ANGLES`, later |

## 3. The library question (MC-1, Zach's "super simple CAD modeller")

The rule that decides it: **our algorithms keep running in the Python core; the browser draws and edits the file.** The browser never computes a loop, so the loops the fit sees are the same in the tests, the Studio and Fusion.

| Option | Size in the browser | Determinism against our goldens | Exact loops for our algorithms | Live re-placement | Licence | Windows dev | Effort |
|---|---|---|---|---|---|---|---|
| **Our own sketcher**: shapes in the file, loops by `plan/shapes.py` on the server, SVG in 2D, three.js in 3D | nothing new (three.js is in) | exact: the server strokes, as today | yes: `Target.loops_mm` is the data | ms: one compile + the plan cache | ours | yes | M8a + M8b1 |
| replicad (Apache-2.0) on OpenCascade.js (LGPL-2.1) in the browser | a wasm kernel of tens of MB, seconds to load | OCC's tessellation is not our 0.05 mm stroking: a second truth | no; the browser would send a sketch anyway | an OCC boolean per edit, 10-100 ms, plus the load | OK | npm | medium; two geometry truths to keep equal |
| JSCAD (`@jscad/modeling`, MIT) | about a MB | its own float arithmetic, not `region.py`'s | no | OK | OK | npm | medium; a code-CAD model, not a sketcher |
| A constraint solver (planegcs LGPL-2.1, a wasm port exists; SolveSpace's `slvs` GPLv3) | small to medium | iterative; a solution can move by an epsilon between versions | no (it gives positions, not loops) | fine | GPL for SolveSpace | wasm | only for constraints, which are out |
| CadQuery / build123d (Apache-2.0) on OCP (LGPL) on the server | nothing in the browser | OCC again, in Python | yes via a B-rep face's wires | an OCC rebuild per edit | OK | a 100+ MB wheel, historically conda; **not standard library**, so it cannot run inside Fusion | an adapter later (BRIEF: build123d is where Zach composes scenes), not the Studio's engine |
| An existing web sketcher (jsketcher / web-cad, CADmium, Chili3D, ...) | each is an app with its own kernel | its own model | no | OK | varies (Chili3D is AGPL-3.0; check each before use) | npm | adopting their data model; nothing gives our loops |

**Recommendation: our own minimal sketcher.** It is the smallest thing that satisfies MC-2 (the shapes ARE the inputs) and the determinism rule, and most of it exists: the stroking (`core.faces`), the booleans and solids (`plan/region.py`, `plan/mesh.py`), the 2D canvas with select, drag, snap and rulers, the 3D view with OrbitControls. What is new is the five shape tools, the handles, the toolbar, the palette and the gizmo.

**Fallback: replicad.** If a later need is real B-rep on screen (fillets, STEP import, a face picked on a model that was not made here), replicad loads in the browser for display and picking only; a picked face comes to the server as a `loops` shape, stroked by replicad at `CHORD_MM`, and the Python core still plans it. That keeps the rule. build123d is not a fallback; it is an adapter (section 1.2's `loops` is its input and output).

## 4. The UI kit (MC-10)

### 4.1 The look

Fusion's dark blue goes. The kit is **compact and modern**, and shared with the other tools from the start by using what the CAD Exporter cockpit already builds on (`cad-exporter/app/package.json`): React 19, Tailwind 4, `@base-ui/react` (headless, accessible controls), `lucide-react` icons plus our own CAD glyphs (today's `studio/src/ui/icons.ts`), `cmdk` for the command palette, `react-resizable-panels`. zustand stays the app's, not the kit's.

| Token | Default |
|---|---|
| Theme | light by default, dark as a toggle; colours as CSS variables (`--bg`, `--panel`, `--field`, `--line`, `--text`, `--muted`, `--accent`, `--ok`, `--warn`, `--bad`); no product blue |
| Density | 12 px text, 24 px rows, 6 px gaps; a panel 280-320 px wide |
| Type | Inter when installed, else the system font |
| Icons | 16 px, one set for every tool (`lucide` + our glyphs: marker, grid, ChArUco, extrude, aruco extrude, hole, slot) |

### 4.2 What carries over: the FIELDS

| Today | In the kit |
|---|---|
| `GET /api/form`: one row per field (`plan/fields.py`): path, type, label, default, limits, choices, group | the same rows feed the kit's `Form`; the contract is named `bam.form/1` when the kit is extracted (today's `arucostudio.form/1` rows, with the `rules` block optional) |
| per-row validation: each message under the row its key path names, one short line, the full words in the tooltip, one summary line (`routeIssues`, the audit's rule, REF `design_aruco_ui_v2.md` §3) | `FieldRow` has a message slot; `Form` routes `Issue`s by path and by `anchor` |
| `layout.ts`: which tab a field goes on, the icons of its choices | moves into the field definition (4.3), so the app holds no second copy |
| the Library: collections, cards with a thumb, Filters, Info, Edit form (`GET /api/library`) | `Library` renders any `{collections, cards, form}` the server gives: print presets today, physical printers (section 5) and target palettes next |
| hand-made controls (`Dropdown`, `NumberInput`, `Toggle`, `ButtonRow`, `IconButton`) | `Select` (icons), `NumberField` (unit, step, Enter commits, Esc reverts, drag to scrub, an Auto state), `Switch`, `SegmentedRow`, `TextField`, `IconButton` |
| the toolbar, the drawers, the status bar | `Toolbar` (bottom, tools with a key badge, the active one lit), `CommandPalette`, `Drawer`, `StatusBar`, `Tabs`, `Badge`, `Tooltip` |

### 4.3 One field definition, every shell renders it

`plan/fields.py` is the one source (ARCHITECTURE 5.6 already says so for the Studio). It gains the keys a renderer needs and the Fusion dialog keeps in hand-written tables today:

| Key | Meaning | Replaces |
|---|---|---|
| `tab` | Marker / Heights / Print / Label / Advanced, or `root` | `layout.ts` `BY_GROUP` / `BY_PATH`; REF `aruco_extrude_ui.ROUTE`, `TABS`, `GROUPS` |
| `icon` per choice | the glyph name | `layout.ts` `ICONS_OF`; REF `LAYOUT_ICONS`, `MODE_ICONS`, `OP_ICONS`, `MARK_ICONS` |
| `show_when` | `{layouts: [...], made_by: [...], target: [...]}` | the per-kind rows of M6 §a; REF's `_show_*` functions |
| `anchor` | the row that shows this field's message when this one is hidden | REF `MSG_ROWS`, `FALLBACK` |
| `unit`, `step`, `drag` | mm / deg / modules; the snap; a handle kind (`size-arrow`, `height-arrow`, `label-xy`) | REF's `_place_arrows` list |
| `preset` | true when a print preset writes the field | `core.presets` WORDS |
| `read_only`, `summary` | | |

The web `Form` renders the rows. Fusion's `bam_fusion_ui.Layout` and `Validator` (REF) build their tabs, rows and message anchors from the same rows, vendored by M7.1's sync; the hand-written `ROUTE` / `MSG_ROWS` / `FALLBACK` become derived, with a test that they equal the old tables until they are deleted (M7.5). Each shell only renders; `core.form` and `core.validate` stay the one model of values and messages.

Cad2Robot's datasheet editor adopts the same `Form` by turning its dataclass fields into `bam.form/1` rows (the dataclass-view work of August is exactly that list); the cockpit's panels the same. The kit is born as `studio/src/kit/` in M8b1, extracted to `studio/packages/bam-ui/` in M8b2, and copied into cad-exporter by a sync tool like `fusion-aruco`'s (`tools/sync_from_aruco_studio.py`) in M8d.

## 5. PrusaSlicer: the physical printers, live (MC-11), and Send to PrusaSlicer

Everything here is **read only** on PrusaSlicer's folder (`%APPDATA%\PrusaSlicer`; `BAM_ARUCO_PRUSASLICER_DIR` points the tests at a fixture). Nothing below copies a host, a key or a password anywhere: the loader drops them before any value leaves `core/prusa.py` (5.6).

### 5.1 What the folder holds

| File | Format | Keys that matter |
|---|---|---|
| `PrusaSlicer.ini` | sections `[presets]`, `[recent]`, `[vendor:PrusaResearch]`, ... | `[presets]`: `print`, `printer`, `filament` (+ `filament_1`..`_4` for an MMU), `physical_printer = "<name> * <printer preset>"`: what PrusaSlicer has selected now. `[vendor:PrusaResearch]`: `model:<MODEL> = <variants>`: the installed models and nozzles |
| `physical_printer/<name>.ini` | flat `key = value` | `preset_names` (quoted, `;`-separated: the printer preset(s) this machine uses), `preset_name` (the first), `printer_technology` (FFF / SLA), `host_type` (a word: the kind of host). **Ignored, never read into memory:** `print_host`, `printhost_apikey`, `printhost_password`, `printhost_user`, `printhost_port`, `printhost_cafile`, `printhost_authorization_type`, `printhost_ssl_ignore_revoke` |
| `printer/<name>.ini` | a user printer preset: a full dump | `inherits` (the system printer), `nozzle_diameter` (one per extruder, `0.6,0.6,...`: take `[0]`), `printer_model`, `printer_variant`, `printer_notes` (the keywords the print presets' conditions test, e.g. `MK4IS`), `bed_shape`, `max_print_height`, `min_layer_height`, `max_layer_height`, `default_print_profile`, `default_filament_profile` |
| `print/<name>.ini` | a user print preset: a full dump | `inherits`, `layer_height`, `first_layer_height`, `extrusion_width` and the per-feature widths, `perimeter_generator`, `compatible_printers` (names) or `compatible_printers_condition` (an expression: `printer_notes=~/.*MK4IS.*/ and nozzle_diameter[0]==0.6 and ! nozzle_high_flow[0]`) |
| `vendor/PrusaResearch.ini` | the system bundle: `[printer_model:X]` (name, variants, technology, family, bed_model), `[printer:<name>]` and `[print:<name>]` with `inherits` chains, `[filament:...]` | this box: 40 printer models, 280 printer sections, 707 print, 7,620 filament. `PrusaResearch.idx` lists the bundle's versions |
| `filament/*.ini`, `shapes/`, `cache/`, `snapshots/`, `*.bak` | | not read |

Zach's five physical printers on 2026-10-16 point at: two at the CORE One 0.6 (system presets straight from the bundle), one at the MK3 0.6, one at the MK3.5 0.6, and one made that evening at the MK4 MMU3 0.4 "(Black, Clear, White)" (a user printer preset). PrusaSlicer's selection was that last one with the print preset "0.20mm SPEED @MK4IS 0.4". Only two user printer presets exist (the MK4 MMU3 0.4 and 0.6); the rest resolve through the bundle. So "what Zach actually uses" is: a physical printer, its printer preset (user or system), and the print presets that fit it.

### 5.2 Resolving a physical printer to its numbers

| Step | Does | Code |
|---|---|---|
| 1 | read `physical_printer/*.ini` through an **allow-list** (`preset_names`, `preset_name`, `printer_technology`, `host_type`); every other key is dropped on read | `core/prusa.parse_physical(text)` (new) |
| 2 | each printer preset name: `printer/<name>.ini` when it exists (its `inherits` is the system parent), else `[printer:<name>]` in the bundles; parents applied as `_system` does for prints (later parents win, own keys last). `parse_bundle` gains a `kinds` argument so it keeps `printer:` and `printer_model:` sections too (filament sections are skipped: 7,620 of them) | `core/prusa.printer_of(name, src)` -> `{nozzle_mm, model, variant, notes, bed_mm, max_height_mm, layer_mm range, default_print, default_filaments}` |
| 3 | the print presets that fit: a user `print/*.ini` (and a system one on request) fits when `compatible_printers` names the printer, else when `compatible_printers_condition` holds. A **small evaluator** for the subset Zach's files use: `and`, `or`, `!`, `==`, `!=`, `=~/regex/`, `!~/regex/`, `[0]`, strings, numbers, brackets; anything else gives **maybe**, never a silent no. Fallback for a `maybe`: the nozzle alone (`nozzle_of`, exists) | `core/prusa.fits(print_cfg, printer) -> yes / maybe / no` |
| 4 | per (physical printer, print preset): nozzle from the printer, line width and layers from the print preset exactly as today (`profile`: `extrusion_width` resolved, auto = 1.125 x the nozzle) | `core/prusa.profile` (exists) + `core/presets.from_profile` with a `printer` block: `{physical, model, variant}` |
| 5 | the pair PrusaSlicer has selected now (`[presets]`): marked **current** | `core/prusa.selected(ini_text)` (the pure half of `beds_io.last_selected_presets`) |

Goldens: the fixture folder (`goldens/prusaslicer/`) gains `physical_printer/`, `printer/` and a `PrusaSlicer.ini` with placeholder hosts (`print_host = <host>`), and `goldens/prusa.json` the new cases.

### 5.3 What the Studio reads today, what changes

| Today | After M8c |
|---|---|
| `print/*.ini` + the bundles' `print:` sections; the "Aruco" profiles become built-in presets | the same, plus physical printers, printer presets, the fitting prints and the selected pair |
| `GET /api/prusa/profiles` | kept; new `GET /api/prusa/printers`: `[{name, technology, host_kind, printer: {preset, nozzle_mm, model, variant, bed_mm}, prints: [{name, fits, line_mm, layer_mm, first_layer_mm}], current}]` |
| the Library: one PrusaSlicer card per "Aruco" print profile | a **Printers** collection: one card per physical printer, its fitting print presets as the card's choices (the "Aruco" ones first, the current one marked); Select makes the ArUco preset from the pair (`from_profile`, imported as yours, as PrusaSlicer cards are today). The old cards stay |
| `server/store.prusa_sources`: `print/` and `vendor/` texts | also `physical_printer/`, `printer/` and `PrusaSlicer.ini` texts; the forbidden-path rule unchanged |
| `beds_io.last_selected_presets` for the 3MF's config | the physical printer's chain when one is chosen (5.5), else the selected pair |

### 5.4 Live updating

| | |
|---|---|
| What is watched | `PrusaSlicer.ini`, `physical_printer/*.ini`, `printer/*.ini`, `print/*.ini`, `vendor/*.ini`: about twenty stats every 2 s by the same `server/watch.py` as the scene file (1.6), with a 500 ms quiet time before a re-read (PrusaSlicer writes a preset file the moment it is saved: the physical printer made on 2026-10-16 is stamped 22:33:02, the minute it was made; `PrusaSlicer.ini` is written on changes and at exit) |
| On a change | re-read the changed files, re-resolve, diff the printers and profiles, push `prusa {added, removed, changed}` over `/api/events`; the Library refreshes its Printers cards |
| A tag whose preset came from a changed profile | **never changes by itself**: its `cells` and heights were copied at creation (the versioned rule). The inspector shows an `info` under Preset: "the profile changed: line 0.68 -> 0.65 mm; Apply?" and a button; nothing is applied without the click |
| PrusaSlicer not installed, or the folder appears later | no watcher, the Library says "PrusaSlicer's folder not found"; the parent is tried once a minute |
| A half-written file | parse failure: keep the last good read, try again next tick, no message until three ticks fail |
| The bundle updated by PrusaSlicer's wizard | `PrusaResearch.ini` replaced: a full re-read; parsing only the printer / print / model sections keeps it under 200 ms (measured in M8c) |
| A physical printer deleted or renamed | its card goes (a rename is a delete and an add); an ArUco preset made from it stays as one of yours |
| Roaming / cloud sync touching mtimes | the text's hash decides, not the mtime |
| Tests | a temp fixture folder; the test edits a file and waits for the event (under 3 s); a test asserts the Studio never writes under the folder |

### 5.5 Send to PrusaSlicer (Zach, ~21:00)

The Studio does what the add-in's `bamArucoSendPrusa` does: a 3MF project with the colours on their extruders, opened in PrusaSlicer, with the physical printer's presets.

| Piece | Does | Code |
|---|---|---|
| The parts | one part per extruded body with its tags (the forearm is ONE part with four tags); a 3D tag on a bare shape is a part of its own; stickers are left out (they print on paper) | `scene/print3d.py` (new) |
| The volumes | the body's solid (extruder 1, white); per tag, from `plan/mesh.bodies(plan)` in the tag's own frame: the white adds (tile, pins, strip) on extruder 1, the black (pattern, label ink) on extruder 2, and the material the tag removes from the body (pocket, recess, holes, mark cut, the trim's complement) as a **negative volume**, computed per slab with `plan/region.py` as the cut region minus what is added back there, so no negative volume overlaps a black. Each volume's mesh is placed by the tag's 4x4 pose. **PrusaSlicer does the 3D booleans** (its parts are unioned per extruder, its negative volumes subtracted, in its integer 2D clipper per layer); our code does exact 2D per slab in each tag's frame and never a 3D boolean. Why: `plan/mesh.py` is exact along one normal; four tags on four faces have four normals |
| The project | `beds_io.write_beds` (REF's text, verbatim): beds packed, the complete preset chain in `Metadata/Slic3r_PE.config` (a partial config would reset the printer to defaults, REF's finding), the MMU slots (white / black filaments, Zach 2026-10-10), the wipe-tower hole, `volume_type` per volume (`ModelPart` / `NegativeVolume`) in `Slic3r_PE_model.config` | `beds_io._project_setup` takes the chain of the chosen physical printer (5.2) instead of `last_selected_presets`; the bed from the printer preset's `bed_shape` |
| Opening PrusaSlicer | `beds_io.find_prusaslicer_gui()` (exists) then the GUI exe with the project path (opened as a project, so the beds and the config are kept; "import geometry only" would scramble them, REF's finding); `--single-instance` when 2.9.6 accepts it, so a running PrusaSlicer takes the file instead of a second window (M8c checks) | `POST /api/scene/send/prusaslicer {printer, print, open: true}` -> `{project, parts, beds, warnings, opened}` |
| The Studio | the Export menu and the palette: **Send to PrusaSlicer…**: a dialog with the physical printer (the current one first), its print preset, the white and black slots, Spaced beds or Tight (later), **Send** | M8b2 |
| STL stays | `/api/export/stl` and `/api/scene/export/stl` keep giving plain STLs (one colour); the 3MF is the send because it carries the colours and the config |

### 5.6 The privacy rule, as code

| | |
|---|---|
| The allow-list | `core/prusa.PHYSICAL_KEYS = ("preset_names", "preset_name", "printer_technology", "host_type")`; `parse_physical` returns these and nothing else |
| The test | `tests/core/test_prusa_physical.py`: a fixture physical printer with every `printhost_*` key filled with a marker string; the parsed dict, `GET /api/prusa/printers`, the Library's JSON, the 3MF's config and every log line are searched for the marker: none may hold it |
| Documents | this note and the status files name printers and models, never a host |

### 5.7 Accuracy: slice headless, in the tests only

| Step | Check | Bar |
|---|---|---|
| 1 | `prusa-slicer-console.exe --datadir <scratch> --export-gcode --dont-arrange --output <gcode> <project.3mf>` (REF's `tools/verify_print_beds.py` and `slice_aruco_label.py` do this), the console found at REF's known paths or on PATH, the user's own config never read; ASCII G-code (`binary_gcode` overridden) | skipped, not failed, when the console is absent; the status file says so |
| 2 | **layers**: `;LAYER_CHANGE` count = the part's height per the preset (first layer, then layers) | +/- 1 layer |
| 3 | **the black's heights**: the first and last layer where extruder 2 extrudes, against the plan's pattern `z` range | within one layer height each |
| 4 | **line counts**: in a mid-height layer of the black, the parallel extrusion lines across one cell at their `;WIDTH` = the cell's line count when `cells = {of: cell, step: line}` (Zach 2026-10-14: a cell is a clean multiple of the line width) | exact |
| 5 | **ink**: the extruder-2 toolpaths of that layer drawn at their widths on a 0.04 mm raster against the plan's black top view (`plan/mesh.top`), as REF's `label_coverage` does | IoU >= 0.9; every label pixel covered over 60 % of its central half |
| 6 | **footprint**: no extrusion outside the part's footprint + 0.5 mm, none inside the bed margin | none |
| 7 | **the forearm**: four side tags on one part slice as one object; the negative volumes cut nothing of the black | steps 3-5 on each of the four |

This runs on the three example files of 1.3 (the sticker sheet has nothing to slice: the route says so).

## 6. Milestones

The milestones, their owner paths, done checks and the order with M6 and M7 are in `docs/design/ROADMAP.md` (M8a, M8b1, M8b2, M8c, M8d). In one line each:

| Milestone | Gives |
|---|---|
| M8a | the file format, the compile, the migration, the watcher, `/api/events`, `/api/design/*`, the CLI, the three example files |
| M8b1 | the mini CAD in the Studio: tools, handles, the bottom toolbar, the palette, the 3D gizmo, live reload, ArUco Extrude in place of the target editor; the kit's primitives born |
| M8b2 | the kit and the form on every panel; M6b's rows and multi-select; the sheet dialog; Print (M6c); Send to PrusaSlicer; the Printers collection |
| M8c | PrusaSlicer physical printers, the live watcher, Send to PrusaSlicer's server side, the headless accuracy test |
| M8d | the kit extracted and carried into the cockpit and Cad2Robot (cad-exporter `app/`) |

## 7. New `docs/spec.json` entries (the orchestrator writes them)

| Id | Area | Name | Milestone |
|---|---|---|---|
| ST-FILE-V2 | scene | The design file `arucostudio.scene/2`: sketches, features, sugar, the `/1` migration | M8a |
| ST-SHAPES | plan | Shapes to loops at `CHORD_MM`; faces of an extrude as Targets | M8a |
| ST-WATCH | server | The file watcher, `/api/events`, the no-echo rule, the broken-file rule | M8a |
| ST-CLI | server | `check` / `render` / `plan` from the command line | M8a |
| ST-UI-SKETCH | studio | The five shape tools, handles, holes, Extrude, ArUco Extrude in place of the target editor | M8b1 |
| ST-UI-TOOLBAR | studio | The bottom toolbar, hotkeys, the command palette (S) | M8b1 |
| ST-UI-3D-DRAG | studio | TransformControls on sketches, the extrude arrow | M8b1 |
| ST-UI-LIVE | studio | Live reload from the file; the File drawer | M8b1 |
| ST-KIT | studio | The compact kit; `Form` from `bam.form/1`; light and dark | M8b2 |
| ST-UI-SEND | studio | Send to PrusaSlicer…; the Printers collection | M8b2 |
| ST-FIELDS-PRESENT | plan | `plan/fields.py` carries tab, icon, show_when, anchor, unit, drag | M8b2 |
| ST-PRUSA-PHYSICAL | core | Physical printers resolved to nozzle, prints that fit, the selected pair; the allow-list | M8c |
| ST-PRUSA-LIVE | server | PrusaSlicer's folder watched; `prusa` events | M8c |
| ST-SEND-PRUSA | export | The 3MF project with volumes per extruder and negative volumes; opened in PrusaSlicer | M8c |
| ST-SLICE-CHECK | verify | Headless slicing against the plan: layers, heights, line counts, ink, footprint | M8c |
| ST-KIT-SHARED | adapter | The kit in the cockpit and Cad2Robot | M8d |
| ST-FUSION-FIELDS | adapter | The v2 dialog built from `plan/fields.py` | M7.5 |

## 8. Open questions for Zach

| # | Question | Recommended default |
|---|---|---|
| 1 | The file: JSON with a small vocabulary and sugar keys (1.2), or a terse DSL? | **JSON.** An AI writes it without a grammar in hand; the parser and the types exist |
| 2 | No Save: every Studio action writes the file at once; Undo is a history of texts; "Save as…" copies. OK? | **Yes.** It is what "the file is the truth" means; a broken file blocks writes, so nothing is lost |
| 3 | A tag on a side face in the 2D view: unfolded about its edge like a box net, or shown in 3D only? | **The net.** The 2D view stays "what prints"; the hinge line says where it folds |
| 4 | The kit's base: the cockpit's stack (Tailwind 4, base-ui, lucide, cmdk) and a light theme by default? | **Yes**, dark as a toggle; one stack for every tool |
| 5 | Printers in the Library: one card per physical printer with its fitting print presets (Select makes the preset), or presets made for every pair up front? | **Cards, made on Select.** Five printers x ten prints would be fifty presets nobody asked for |
