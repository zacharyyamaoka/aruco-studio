# Spec tests, one line each (docs/aruco_spec.json at c8216ff)

Generated from REF's `docs/aruco_spec.json` (updated 2026-10-16) by the inventory task. One row per test. `kind`: offline-unit = a plain script, no Fusion; offline-opencv = a tool with cv2 / numpy; fusion-bridge = runs inside Zach's Fusion through tools/aruco_bridge.py; fusion-dialog = the real dialog in Fusion; fusion-readonly = a read of Zach's document; manual = Zach by hand. `how`: the test file, the bridge scenario (`source`), or the artifact / gate the result is read from. `pass` is the spec's own pass bar, shortened.

## Area `extrude`: ArUco Extrude

### EX-TGT: Targets (status: built)

Pick a planar face or a closed sketch profile: on a body, on a free sketch with nothing under it, or a ROOT sketch drawn over a face inside a child component (also on an offset plane); the tag is built in the component that owns the body.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-TGT-1 | fusion-bridge | A tag on a clicked face of a plate builds as a live, healthy node (live_test A, C, D, H). | fusion live_test (^A: face; ^C: face; ^D: face …) | every step ok: the node is live, no compute errors, the timeline healthy |
| EX-TGT-2 | fusion-bridge | Sketch profiles build live: a sketch on a body (B) and free sketches with no body under them (F, G, W). | fusion live_test (^B: sketch; ^F: free sketch; ^G: free sketch …) | every step ok |
| EX-TGT-3 | fusion-bridge | A ROOT sketch over a child component's disc (Zach's tag, Z) and a face of a body inside that child (K) build in the child, through its rotated occurrence. | fusion live_test (^Z: root sketch; ^K: face of a body in the child) | every step ok |
| EX-TGT-4 | fusion-bridge | Zach's GIM4305 structure: a click inside the sketch rectangle means the rectangle; a root sketch on a tilted child disc with projected holes; a root sketch on an offset plane. | fusion live_test (^GIM: a click on the face; ^GIM: root sketch on a tilted; ^OFF: root sketch on an offset plane) | every step ok (the body found through the occurrence, built in the child) |
| EX-TGT-5 | fusion-bridge | A board whose pocket reaches the face's edge (it splits the face) stays one live node. | fusion live_test (\[split\] split ) | every split case ok: live node, healthy |

### EX-MODE: Modes (status: built)

White + black (Join into the body, or a New body), Black only (inlaid or raised) and White only; each builds the bodies its mode promises.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-MODE-1 | offline-unit | The parts each mode needs (tile, pocket, pattern, recess) follow from where its slabs sit. | offline tests/test_aruco_slabs.py (plan: the parts follow from where the slabs are) | every check ok |
| EX-MODE-2 | fusion-bridge | Every mode in one document: white + black joined (A) / new body (F, Z), black only inlaid (B, K) / raised (D) / with no body (G), white only raised (C) / free (W). | fusion live_test (^[ABCDFGHWZK]: ) | every create step ok |
| EX-MODE-3 | fusion-bridge | Changing the mode of an existing node rebuilds it: black only -> white + black, white + black -> black only (no tile left). | fusion live_test (^structural edit: ) | both steps ok |
| EX-MODE-4 | offline-unit | A black only -> white + black rebuild keeps the black's step: the pocket stops above the tile's underside, the tile stays ONE body (the 05:2x Fusion failure, fixed in 48e8ca7). | offline tests/test_aruco_extrude_fixes.py (A1: a structural edit keeps the black's step) | every check ok |

### EX-HGT: Heights (Offset / Height) (status: built)

Each colour is an extrude from an Offset, Height further (either sign), measured from the face like Extrude: flush by default, raised or recessed; the black's offset follows the white top by an expression until a value is typed.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-HGT-1 | offline-unit | A slab is an extrude from Offset, Height further, in either direction. | offline tests/test_aruco_slabs.py (slabs: an extrude from Offset) | every check ok |
| EX-HGT-2 | offline-unit | Defaults per mode: white 0 / +2 with the black at the white top (-0.6); black only and white only flush at the face. | offline tests/test_aruco_slabs.py (defaults) | every check ok |
| EX-HGT-3 | offline-unit | The record's surface, depth / raise / recess and the detector plane follow from the slabs, and the TagSpec round-trips them (the module imports only the stdlib). | offline tests/test_aruco_slabs.py (layers: the record's surface; the record (TagSpec) agrees with the slabs; stdlib only) | every check ok |
| EX-HGT-4 | offline-unit | The black layer's depth into the face and raise above it (thickness = depth + raise) in the pure core. | offline tests/test_markers.py (black layer: depth into the face) | every check ok |
| EX-HGT-5 | fusion-bridge | Every height combination on its own plate, measured on the bodies: flush, raised, recessed, a negative white height, Black only inlaid / on top, White only inlaid / raised. | fusion live_test (\[heights\] heights h[a-z]+:; \[heights\] height shots) | every case ok (measured z ranges as specified) |
| EX-HGT-6 | fusion-bridge | The black offset follows the white top as a parameter expression: Change Parameters keeps the black level; a typed offset unlinks; a change that adds / drops the pocket says 'rebuild' and the edit rebuilds. | fusion live_test (\[follow\] ) | every step ok |
| EX-HGT-7 | fusion-dialog | A fresh dialog starts flush in every mode (black top at the white top; Black only at the face; White only's top at the face). | fusion lab_preview (fresh_defaults) | fresh_defaults ok in every mode |

### EX-SIZE: Auto size (status: built)

Click a face and the default size comes from its largest clear rectangle (holes and notches avoided); typed sizes are clamped to fit; the Layout list ranks what fits; the dictionary grows with the ids in use.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-SIZE-1 | offline-unit | Size-first defaults on the proposal's five faces match its table (P1). | offline tests/test_aruco_autosize.py (§4 P1 defaults) | every check ok |
| EX-SIZE-2 | offline-unit | The ranked Layout lists match the proposal (P3). | offline tests/test_aruco_autosize.py (§6 P3 ranked lists) | every check ok |
| EX-SIZE-3 | offline-unit | A typed size that does not fit is clamped with a note; one that fits is kept; a forced count keeps it or refuses; the chosen Layout writes the TagSpec. | offline tests/test_aruco_autosize.py (clamp_to_fit; layout_for_size; Layout.apply) | every check ok |
| EX-SIZE-4 | offline-unit | The dictionary grows with the ids in use (5 markers, 40 in use -> DICT_4X4_100; 60 tags -> a 4x4 with headroom). | offline tests/test_aruco_autosize.py (auto_dictionary) | every check ok |
| EX-SIZE-5 | offline-unit | 780 random boxes: every default fits; clamping and the unprintable path are exercised. | offline tests/test_aruco_autosize.py (invariant sweep) | every check ok |
| EX-SIZE-6 | offline-unit | A clicked face is sized from its own outline (largest clear rectangle); the Layout list respects holes. | offline tests/test_aruco_autosize.py (fit_on_loops; candidates_on_loops) | every check ok |
| EX-SIZE-7 | offline-unit | Ten faces that are not boxes x every layout: every tile inside the face, the same default under 90 / 180 / 270 turns, equal to a 0.1 mm brute-force raster. | offline tests/test_aruco_autosize.py (gallery: ten faces) | every check ok |
| EX-SIZE-8 | offline-unit | The pure core's largest uninterrupted rectangle on a face (square face, disc, never over a hole) and the dictionary suggestions. | offline tests/test_markers.py (largest uninterrupted rectangle; suggestions) | every check ok |
| EX-SIZE-9 | fusion-bridge | The real add-in in Fusion (face-click path, live nodes) builds the same default as offline on the ten gallery faces x single / grid / ChArUco. | gallery autosize_gallery | every face x layout: Fusion's label == the offline label (or both refuse); how many nodes came out live is reported beside it |
| EX-SIZE-10 | offline-unit | Zach's GIM43 discs pinned: the 47.5 mm disc fits 25.0 mm (typed 28 clamped, and Auto), the 53 mm disc 28.0 mm. | offline tests/test_aruco_disc_fit.py (the GIM43 discs) | every check ok |

### EX-LAYOUT: Layouts and dictionaries (status: built)

A single marker, a GridBoard or a ChArUco board in any of OpenCV's 21 predefined dictionaries; the black cells are OpenCV's own ink, cell for cell, and OpenCV's board frame.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LAYOUT-1 | offline-unit | Board counts, ids (row-major blocks) and extents agree with OpenCV's for grids and ChArUco. | offline tests/test_aruco_board.py (counts, ids, extents) | every check ok |
| EX-LAYOUT-2 | offline-unit | Invalid boards are refused the way OpenCV asserts (separation 0, square <= marker, unknown layout). | offline tests/test_aruco_board.py (validation) | every check ok |
| EX-LAYOUT-3 | offline-unit | Board ink equals cv2 generateImage pixel for pixel, and object points / chessboard corners equal cv2 5.0's (pinned). | offline tests/test_aruco_board.py (ink == generateImage; OpenCV's frame (pinned) | every check ok |
| EX-LAYOUT-4 | offline-unit | The dictionary table (sha256, names == fiducials order), marker grids pinned against cv2, merged black rects cover exactly the black cells (9596 markers). | offline tests/test_aruco_output.py (the table; marker_grid; black_rects) | every check ok |
| EX-LAYOUT-5 | offline-unit | Cell geometry: boxes stay inside the black square, area = black cells x module^2, corner growth off by default. | offline tests/test_markers.py (geometry) | every check ok |
| EX-LAYOUT-6 | offline-opencv | Every id of every dictionary (9596 markers): the grid == cv2.aruco.generateImageMarker, and its PNG is read back as that id by ArucoDetector. | artifact verify_output | grids.pass and roundtrip.pass, 9596 markers compared, 0 mismatches |
| EX-LAYOUT-7 | offline-opencv | Grid and ChArUco boards: ink == cv2 generateImage, every id (and ChArUco corner) detected, the pose solvePnP recovers == the board's OpenCV frame. | artifact verify_boards | every ink, detection and frame row passes (tolerances in the file) |

### EX-ORIGIN: Origin (OpenCV's frame only) (status: built)

The tag's frame is always OpenCV's: an Origin dropdown (four corners for boards, 'Up' for single markers) and a Rotate button; a rectangular board at 90 / 270 is OpenCV's board on its side (cols / rows swapped). Nodes made before 2026-10-09 keep their orientation.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-ORIGIN-1 | offline-unit | The Origin's words per layout, Rotate's clockwise order, which boards swap, the old rule. | offline tests/test_aruco_frame.py (aruco_origin: the words, Rotate) | every check ok |
| EX-ORIGIN-2 | offline-unit | aruco_origin.opencv_in_layout (worked out from OpenCV's conventions alone) == markers.detector_frame of the board as built, every layout x Origin. | offline tests/test_aruco_frame.py (opencv_in_layout = markers.detector_frame) | every check ok |
| EX-ORIGIN-3 | offline-unit | The add-in's evaluate() x every Origin: the Joint Origin IS OpenCV's frame, on the corner / 'up' the Origin names, same footprint on the face. | offline tests/test_aruco_frame.py (the add-in: evaluate() x every Origin) | every check ok |
| EX-ORIGIN-4 | offline-opencv | OpenCV reads the record's ids off the add-in's own pattern bodies and its PnP pose equals the record (every layout x Origin), using OpenCV's own board object. | offline tests/test_aruco_frame_pnp.py (every layout x every Origin; the Origin's words and order) | every check ok (the file prints SKIP without cv2: that counts as NOT RUN here) |
| EX-ORIGIN-5 | offline-unit | The dialog: Rotate steps clockwise through the corners (a 3 x 2 grid swaps), the dropdown jumps, the ghost follows; the info line names the corner. | offline tests/test_aruco_extrude_dialog.py (Origin: Rotate steps clockwise) | every check ok |
| EX-ORIGIN-6 | offline-unit | The dialog's Origin words, Rotate order and info line (frame suite). | offline tests/test_aruco_frame.py (the dialog: Origin words) | every check ok |
| EX-ORIGIN-7 | offline-unit | A square face never turns the tag on an edge-length tie (keep_x: the creation's x wins); turned 180 = the un-turned x reversed. | offline tests/test_aruco_extrude_fixes.py (A2: a square plate's x; A2: keep_x) | every check ok |
| EX-ORIGIN-8 | fusion-bridge | Origin turns on live nodes: a single at 0 / 90 / 180 / 270, a grid at 0 / 180 / 90 (a rectangular grid at 90 laid out on its side). | fusion live_test (\[turns\] origin o) | every turn ok; the Joint Origin checked against OpenCV's frame by the run's _jo_check |
| EX-ORIGIN-9 | fusion-bridge | An upstream edit that reverses the face's longest edge does not turn the tag (a new node, and an older one whose x_ref comes from its record). | fusion live_test (\[flip\] ) | every step ok |
| EX-ORIGIN-10 | fusion-bridge | Every layout (single, 2 x 2, 3 x 2, 3 x 3 ChArUco, Zach's 4 x 2 ChArUco, legacy 5 x 4) x all four Origins on identical plates; Rotate four times by the edit route; a turned variant copy re-numbered. | fusion origin_test (.) | verdict PASS: board as built, footprint unchanged, record_drift empty, Joint Origin on OpenCV's frame (1 um) |
| EX-ORIGIN-11 | fusion-dialog | The real dialog: the Origin dropdown's words per Type, Rotate steps clockwise, the ghost's axes are OpenCV's frame of what OK makes; Cancel leaves nothing. | fusion origin_dialog (.) | every dialog step ok |

### EX-MARK: Corner mark (status: built)

Corner mark None / Cut white corner / Black triangle, offered only where it is valid: the tile's own corner is cut, a joined tile gets a black triangle, ChArUco cuts the top-left black square's outer corner; never a marker's black square.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-MARK-1 | offline-unit | Which mark each layout x mode gets, and the corner-mark choice (None / Cut white corner / Black triangle; the old checkbox is 'cut'). | offline tests/test_aruco_chamfer.py (which mark each layout x mode gets; Corner mark: None / Cut white corner) | every check ok |
| EX-MARK-2 | offline-unit | The mark sits at OpenCV's corner 0 / the board origin for every Origin turn. | offline tests/test_aruco_chamfer.py (at OpenCV's corner 0) | every check ok |
| EX-MARK-3 | offline-unit | Legs in module units, a 45 degree cut, and the cut tool (long side IS the cut line, pokes past both edges). | offline tests/test_aruco_chamfer.py (legs, in module units; the cut tool; stdlib only) | every check ok |
| EX-MARK-4 | offline-unit | Single and grid: the mark never touches a black cell (clearance >= its minimum); ChArUco: only the outer corner of the top-left black square. | offline tests/test_aruco_chamfer.py (never touches a black cell; ChArUco: only the outer corner) | every check ok |
| EX-MARK-5 | offline-unit | Tiles bigger than the sticker, rectangles, turns; too narrow a white border gives no mark and says why; a copy with another id carries the same mark. | offline tests/test_aruco_chamfer.py (tiles bigger than the sticker; too narrow a white border; a copy (another id) carries the same mark) | every check ok |
| EX-MARK-6 | offline-unit | evaluate() -> every part's body, probed at the mark (corner gone / triangle black / notch), every layout x mode x Origin; off changes nothing; too narrow a border is a node warning. | offline tests/test_aruco_chamfer_bodies.py (evaluate() -> every part's body; off: nothing changes; too narrow a white border) | every check ok |
| EX-MARK-7 | offline-unit | The record keeps the mark; the dialog offers only what the tag can have and keeps the pick across mode changes; the ghost shows the mark. | offline tests/test_aruco_chamfer_bodies.py (the record and the dialog) | every check ok |
| EX-MARK-8 | offline-unit | The Extrude dialog's Corner mark list per mode / op; the pick survives a mode change. | offline tests/test_aruco_extrude_dialog.py (Corner mark: only what the tag can have) | every check ok |
| EX-MARK-18 | offline-unit | The dialog's Corner mark in the frame suite: a tile of its own offers None / Cut / Triangle; joined: no cut, the triangle shown, the pick kept; the old checkbox's echo is not a pick. | offline tests/test_aruco_frame.py (the dialog: Corner mark) | every check ok |
| EX-MARK-9 | offline-opencv | With the mark on, OpenCV still reads every id off the add-in's bodies, the pose is unchanged, the triangle sits at OpenCV's origin corner. | offline tests/test_aruco_frame_pnp.py (the same with Corner mark 'cut') | every check ok |
| EX-MARK-10 | fusion-bridge | Single markers in Fusion: one tag per mode with the mark, measured on its bodies by point containment at the record's mark; the timeline healthy. | fusion chamfer_test (^\[single\]) | every step ok |
| EX-MARK-11 | fusion-bridge | Grid boards in Fusion, same checks. | fusion chamfer_test (^\[grid\]) | every step ok |
| EX-MARK-12 | fusion-bridge | ChArUco boards in Fusion, same checks (the black square's corner cut). | fusion chamfer_test (^\[charuco\]) | every step ok |
| EX-MARK-13 | fusion-bridge | Edits by the edit route: mark on -> Origin turned -> back (APIFeatureEditCommand) -> off; a compute each, never a rebuild; tile volume changes by leg^2 / 2 x height; the record's mark follows. | fusion chamfer_test (^\[edit\]) | every step ok |
| EX-MARK-14 | fusion-bridge | Per-copy variants (ArUco IDs) of marked parts: copy 2 re-numbered, every copy's bodies carry the template's mark, a second apply_variants keeps them. | fusion chamfer_test (^\[variant\]) | every step ok |
| EX-MARK-15 | fusion-dialog | The real create dialog: the Corner mark list per mode / layout, the info line, the ghost's mark prisms; Cancel leaves nothing; OK makes a marked node; the edit dialog shows its mark. | fusion chamfer_dialog (.) | every dialog step ok |
| EX-MARK-16 | offline-opencv | Study: cutting the WHITE tile's corner costs no detection on a dark, mid-grey or light part (within 0.6 pts, paired). | artifact chamfer_study | \|delta\| <= 0.006 for every tile-cut design on every part colour |
| EX-MARK-17 | offline-opencv | Study: cutting a ChArUco board's top-left black square at its outer corner changes no chessboard corner in any trial. | artifact chamfer_study | corners_delta 0 and no trial with fewer corners, every black-cut ChArUco design |

### EX-PINS: Locating pins (status: built)

A tag printed on its own (White + black, New body) can carry a triangle or two round pins, with matching holes in the plate under it at a set tolerance; pins keep clear of a cut corner and follow OpenCV's origin.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-PINS-1 | offline-unit | The plan adds pin, pocket and recess (the hole) only with a body under a new tile; the pin hangs 2 mm; the hole is deeper by the tolerance. | offline tests/test_aruco_slabs.py (plan: locating pins) | every check ok |
| EX-PINS-2 | offline-unit | Pin outlines: one triangle / two rounds, counter-clockwise, in the top-left corner 1 mm in. | offline tests/test_aruco_slabs.py (pin outlines) | every check ok |
| EX-PINS-3 | offline-unit | Pins keep >= 1 mm clear of a cut corner and the tile's edges, and follow OpenCV's origin on rectangular boards at every Origin. | offline tests/test_aruco_chamfer.py (locating pins keep clear of a cut corner) | every check ok |
| EX-PINS-4 | offline-unit | Built bodies: pins under a cut tile 1 mm clear and present; a pin at the board origin's corner at every Origin (swapped at 90 / 270). | offline tests/test_aruco_chamfer_bodies.py (pins under a cut tile; pins follow OpenCV's origin) | every check ok |
| EX-PINS-5 | fusion-bridge | In Fusion: triangle and round pins on a tag printed on its own, the holes in the plate measured against the tolerance (wall gaps, depths). | fusion live_test (\[pins\] pins p[a-z]:; \[pins\] pin shots) | every step ok |
| EX-PINS-6 | fusion-bridge | In Fusion: tolerance 0.15 -> 0.3 mm (a compute); triangle -> no pin and -> round pins (rebuilds); switching to Join drops the pins; a triangle pin follows corner 0 when turned 90. | fusion live_test (\[pins\] pins: edit; \[pins\] pins: switching; \[turns\] origin: a triangle pin) | every step ok |

### EX-LABEL: Label (optional text) (status: built)

An optional label: one content template (#id, name, dictionary, custom) placed on the black (border rows, ChArUco square) or on the white (a strip beyond the quiet zone), auto-sized and checked against the detection rules, updated per copy by a batch IDs set.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LABEL-1 | offline-unit | The stroke font: every glyph's ink is its cell, cap height exact, strokes at least a nozzle wide. | offline tests/test_aruco_label.py (the font) | every check ok |
| EX-LABEL-2 | offline-unit | Content tokens (#id, a board's id block, name) and per-copy ids / names from markers.resolve and plan_serials. | offline tests/test_aruco_label.py (content; per-copy ids and names) | every check ok |
| EX-LABEL-3 | offline-unit | On the black: the bottom / top rows at cap <= 0.5 module, 0.25 module of black kept, corner cells clear; the name in the top row. | offline tests/test_aruco_label.py (on the black; the name on the black: both rows) | every check ok |
| EX-LABEL-4 | offline-unit | On the white: beyond the quiet zone + 1 module on a strip; on a face with holes, 1.25 mm off every hole. | offline tests/test_aruco_label.py (on the white; a face with holes) | every check ok |
| EX-LABEL-5 | offline-unit | With corner marks and pins: the cut moves to the grown tile's corner, pins and label keep clear. | offline tests/test_aruco_label.py (corner marks and pins) | every check ok |
| EX-LABEL-6 | offline-unit | One label object, its position apart: any content in any position the tag has, or refused with a note. | offline tests/test_aruco_label.py (one label, its position apart) | every check ok |
| EX-LABEL-7 | offline-unit | A text too long for its place shrinks to the floor cap, then is cut short ('AC...:2'), the id kept whole. | offline tests/test_aruco_label.py (a text too long for its place) | every check ok |
| EX-LABEL-8 | offline-unit | A batch IDs set updates every copy's label: its own id at the bottom, its own name at the top, at the template's caps. | offline tests/test_aruco_label.py (batch ids, two rows) | every check ok |
| EX-LABEL-9 | offline-unit | The label is as tall as the black (its slab, per mode); x / y offsets nudge it after the automatic placement and are re-checked. | offline tests/test_aruco_label.py (the label is as tall as the black; offsets: a nudge) | every check ok |
| EX-LABEL-10 | offline-unit | The safety check catches a broken rule (ink in the quiet ring or the 1-module gap is flagged). | offline tests/test_aruco_label.py (the safety check catches a broken rule) | every check ok |
| EX-LABEL-11 | offline-unit | Records are deterministic and round-trip; relabel with the template's data rebuilds exactly; frames; stdlib only. | offline tests/test_aruco_label.py (records and determinism; frames; stdlib only) | every check ok |
| EX-LABEL-12 | offline-opencv | Study: the default label (#id bottom + name top row) costs under 1 pt on DICT_4X4_50 and nothing measurable on DICT_6X6_250 (every design within 0.25 pts); the ChArUco square label changes no corner. | artifact marks_study | the three numbers inside the bounds the doc states (section 11) |
| EX-LABEL-13 | offline-unit | evaluate() → the label, every part's body probed at its strokes (every mode, black / white, strips); the label off builds exactly what it built before; corner mark and pins follow a grown tile; the drift footprint inclu… | offline tests/test_aruco_label_bodies.py (evaluate() -> the label; the label off; the corner mark and the pins follow …) | every check ok |
| EX-LABEL-14 | offline-unit | The dialog's Label group: off by default, every option once it is on; the edit dialog fills the node's label. | offline tests/test_aruco_extrude_dialog.py (the Label group (phase 2); the edit dialog fills the node's label) | every check ok |
| EX-LABEL-15 | fusion-bridge | In Fusion: six placements (white '#12' in a 40 mm border, strips, around a Black only tag, White only, a left strip moving the cut and the pin, an 18 mm marker refused); Fusion's edit route changes the text, the id (the… | fusion label_test_1010 (^\[node\]; ^\[edit\]; ^\[dialog\]) | every step ok |
| EX-LABEL-16 | fusion-bridge | In Fusion: renumbered copies print their own label ('#31 / ACTUATOR:2'), by variants and by an ArUco IDs batch. | fusion label_test_1010 (^\[variants\]; ^\[ids\]) | every step ok |
| EX-LABEL-17 | offline-opencv | OpenCV finds the marker in each label_test capture, warps every label slot flat and reads the id line against every id of the dictionary. | artifact label_read | every capture's lines read right |
| EX-LABEL-18 | offline-unit | An ArUco IDs part reports its label's warning (why a copy prints no label, or that it was built anyway), never drops it. | offline tests/test_aruco_ids_label_warning.py (label_warning) | every check ok |

### EX-LABEL-FONT: Label font that prints (0.6 mm nozzle) (status: built)

A blocky 5-pixel font: one pixel = one stroke = cap / 5, at least the nozzle; every bar, counter and gap whole pixels, every edge axis-aligned, built as boxes like the cells. Nozzle 0.6 mm by default (smallest cap 3.0 mm); the dialog's Nozzle field sets it.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LABEL-FONT-1 | offline-unit | The pixel font: every glyph's ink is its cell, strokes ≥ the nozzle; the 0.6 mm section (smallest cap 3.0 mm, the black row from 36 mm). | offline tests/test_aruco_label.py (the font; a 0.6 mm nozzle) | every check ok |
| EX-LABEL-FONT-2 | offline-unit | The slicing oracle on made-up toolpaths: a dropped glyph, a bridge, a lost counter are each caught. | offline tests/test_aruco_label_print.py | every check ok |
| EX-LABEL-FONT-3 | offline-unit | PrusaSlicer itself: label-bearing tags sliced with his preset chain, every label layer checked on a 0.04 mm raster of the G-code toolpaths. | artifact label_slice | cases A-C print, T (0.3 mm strokes) flagged, nothing failed |

### EX-LABEL-RULE: Label clearance: the quiet ring is the hard line (rule 2, versioned) (status: built)

On the white the label's ink stays outside the detector's quiet ring (the hard line: ink inside is a violation, built only with Build anyway); auto keeps 0.25 module more when the label still fits. The rule is stored with the label: older labels keep rule 1.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LABEL-RULE-1 | offline-opencv | Study: full-black '#id' text below a 4X4 marker at 0.5-2.0 modules from the black, caps 0.5 / 1.0 module, n = 3000 paired trials. | artifact gap_study | 0.5 module ≤ −5 pts; every gap ≥ 1.0 module within ±0.5 pts |
| EX-LABEL-RULE-2 | offline-unit | The rule in the core: the hard line and the preferred margin. | offline tests/test_aruco_label_position.py (the clearance rule) | every check ok |
| EX-LABEL-RULE-3 | offline-unit | Versioning: no 'rule' is rule 1, a new label rule 2; 36 labels laid out by 8473e14 come out identical today; Zach's old Offset record; rule 1 survives a record and a copy. | offline tests/test_aruco_label_rule1.py | every check ok |
| EX-LABEL-RULE-4 | fusion-bridge | In Fusion (our document): an older label shows the grey line, OK unchanged writes nothing (timeline 10 → 10), a nozzle change stores rule 2. | fusion label_test_1013 (^\[position\] position: an older label) | step ok |

### EX-LABEL-POS: Label Auto position; Offset X / Y show the spot (status: built)

An Auto position checkbox (on by default) above Offset X / Y: on, the rules place the label and the fields SHOW its real centre; typing either field unticks it and puts the label exactly there (absolute), every rule checked at that spot. Auto finds the nearest valid spot (outside the clear zone, near the bottom, never on a hole, on the face), searching further out when nothing near fits.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LABEL-POS-1 | offline-unit | Zach's disc, Auto position, the settings (auto \| manual x, y; old offsets kept), no room anywhere (refused in three lines), copies at a manual spot, the far search. | offline tests/test_aruco_label_position.py (Zach's GIM43 disc; Auto position; settings: position …) | every check ok |
| EX-LABEL-POS-2 | offline-unit | The dialog: Offset X / Y show auto's spot; typing one takes over. | offline tests/test_aruco_extrude_dialog.py (Auto position: Offset X / Y show) | every check ok |
| EX-LABEL-POS-3 | fusion-bridge | In Fusion (a GIM43-like disc of ours): auto builds '#0' below the marker clear of zone and holes; the edit dialog round trip of Auto position. | fusion label_test_1013 (^\[position\] position: Auto position; ^\[position\] position: the edit dialog) | both steps ok |

### EX-LABEL-GHOST: The clear zone drawn; problems first in the info box (status: built)

While a label goes on the white the ghost draws the detector's clear zone (red), auto's preferred margin (lighter) and the label's block (green; orange when it breaks a rule). The dialog's info box opens with errors (red), then warnings (orange), then the label, then what the tag is, and grows to its content (4 to 14 rows).

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LABEL-GHOST-1 | offline-unit | The ghost's guides from aruco_label.clear_zones, drawn on a stand-in graphics group. | offline tests/test_aruco_label_bodies.py (the ghost while the label goes on the white) | every check ok |
| EX-LABEL-GHOST-2 | fusion-bridge | In Fusion: guides 3, the info box 14 rows, a zone spot said first in orange (captures position_ghost_auto.png / position_ghost_zone.png). | fusion label_test_1013 (^\[position\] position: the edit dialog) | step ok |

- Gap: The preferred margin is meant to be dashed; in Fusion it draws as a thin solid line (OI-DASH).

### EX-LABEL-SHOWN: A label that breaks a rule is still shown (Build anyway) (status: built)

A label the rules refuse comes back NOT built, with a preview laid out where it was asked for and its violations in plain words with how much; the ghost draws it in orange. 'Build anyway' (per tag, never remembered) builds exactly that preview and the node warns.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-LABEL-SHOWN-1 | offline-unit | Previews of refused labels: Zach's disc above, nothing fits, a nudge that breaks a rule, what each preview says; records, copies, determinism. | offline tests/test_aruco_label_preview.py | every check ok |
| EX-LABEL-SHOWN-2 | offline-unit | The node: always shown, built only with Build anyway, the node warning. | offline tests/test_aruco_label_bodies.py (a label that breaks a rule: always SHOWN) | every check ok |
| EX-LABEL-SHOWN-3 | offline-unit | The dialog: shown anyway, 'Build anyway' to build it. | offline tests/test_aruco_extrude_dialog.py (a label that breaks a rule: shown anyway) | every check ok |
| EX-LABEL-SHOWN-4 | offline-unit | Mutation test: each label rule broken on purpose in a temporary copy of the tree is caught by the check aimed at it. | artifact label_mutations | every mutation killed, none survived |
| EX-LABEL-SHOWN-5 | fusion-bridge | In Fusion: Zach's GIM43-like disc, '#id' On the white Above at 0.4 mm: refused and shown, the edit dialog's orange ghost, Build anyway, On the black fits. | fusion label_test_1013 (^\[warn\]) | every step ok (2026-10-13: 1/4, see OI-LABEL-WARN) |

### EX-PREVIEW: Preview (ghost) (status: built)

The dialog draws a live ghost of what OK will build (cells, tile, mark prisms, the Joint Origin triad) with drag handles for the heights; Cancel leaves nothing.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-PREVIEW-1 | offline-opencv | The ghost's frame equals the record's and OpenCV's by hand, exactly, for every layout x Origin (with and without the corner mark). | offline tests/test_aruco_frame_pnp.py | every 'ghost' check ok |
| EX-PREVIEW-2 | fusion-dialog | In the real dialog: ghost timings, cleanup on Cancel, the edit dialog's ghost; the Layout list (built layout first), Type turning Auto size back on, the Origin corners with the ghost's Joint Origin triad, the pin group … | fusion lab_preview (.) | dialog_checks and the bench report no failure |
| EX-PREVIEW-3 | manual | Zach's hand check on the GIM structure: drag the two arrows, the ghost follows; OK builds what the ghost showed. | manual manual | Zach: the ghost tracks the arrows and OK matches it |

### EX-NODE: Timeline node and edits (status: built)

Each tag is ONE live custom feature: parameter and upstream changes recompute it in place, Fusion's double-click edit route opens our dialog, a structural change rebuilds it, and when the live wrap fails the features fall back to one timeline group.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-NODE-1 | fusion-bridge | A parameter change (marker_id) recomputes the node in place, also through a child component's stored transform. | fusion live_test (^parameter: b marker_id; ^GIM: parameter marker_id) | both steps ok |
| EX-NODE-2 | fusion-bridge | Upstream edits (plates 8 -> 12 / 6 -> 9 mm, the child disc 6 -> 8 mm) recompute the node with no re-solve. | fusion live_test (^upstream: ) | both steps ok |
| EX-NODE-3 | fusion-bridge | Fusion's own edit route (APIFeatureEditCommand -> our edit command) applies new values (f -> DICT_5X5_100 #7). | fusion live_test (^edit route: ) | step ok |
| EX-NODE-4 | fusion-bridge | A structural edit rebuilds the node in place in a child component (GIM: black -> white + black joined). | fusion live_test (^GIM: structural edit) | step ok |
| EX-NODE-5 | fusion-bridge | When the live wrap raises, the features end up in ONE timeline group, never loose. | fusion live_test (\[fallback\] ) | step ok |
| EX-NODE-6 | offline-unit | A copy's variant part never stands in for its template (record lookups by key). | offline tests/test_aruco_extrude_fixes.py (A3: a copy's variant part never stands in) | every check ok |
| EX-NODE-7 | manual | Hybrid design: double-click the ArUco node; the edit dialog opens, and changing the id updates the cells. | manual manual | Zach: the dialog opens with the node's values and OK updates the cells |
| EX-NODE-8 | manual | Part design: does double-click on the node offer Edit, or only Configure? | manual manual | Zach: Edit is offered |

### EX-EDIT-RT: Edit round trip: Auto size stays Auto; OK unchanged writes nothing (status: built)

The size parameter 0 IS Auto size (every compute fits as create did); the edit dialog shows the node's own state; Edit → OK with nothing changed writes nothing; a change writes exactly that; the timeline marker comes back where it was after an edit or a rebuild.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-EDIT-RT-1 | offline-unit | Every Type x Auto size x Extrude round trip; a change; Zach's node; a node made before the fix; a face with holes. | offline tests/test_aruco_edit_roundtrip.py (every Type x Auto size x Extrude; Edit -> a change; Zach's node …) | every check ok |
| EX-EDIT-RT-2 | offline-unit | The timeline marker after an edit (stand-in timeline). | offline tests/test_aruco_edit_roundtrip.py (the timeline marker after an edit) | every check ok |
| EX-EDIT-RT-3 | fusion-bridge | In Fusion (NEW documents of ours): Zach's Auto ChArUco made through the real create dialog on a holed bar, a grid, a typed single, a joined single: each Edit → OK / Cancel / Rotate / Origin / typed size / Auto again, up… | fusion edit_test (^\[roundtrip jo=1\]) | every step ok (59) |

- Gap: Zach's 'each edit adds another Joint Origin' (2026-10-16) escaped these tests; fixed offline in 8fbf035 with its own suite (JO-ORPHAN-2), Fusion re-run pending (OI-JO-DUP).

### EX-NODE-WARN: A node with a warning says so at once, in its name (status: built)

Measured: Fusion shows a custom feature's warning as 'This feature computed with warnings.Compute Failed<name>' (health Healthy 0 / Warning 1 / Error 2) and ignores the message text, so the node's NAME carries the plain words ('… -- label not built -- 0.8 mm from the face's edge (it needs 1.0 mm)'). A refused label or a clamped size warns right after create.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-NODE-WARN-1 | fusion-bridge | In Fusion (our documents, jo 1 and 2): a clamped size on the 47.5 mm disc and a refused label warn right after the node is made, with the words in its name. | result edit_gates_run3 | both groups ok |

- Gap: No offline test pins the node name's warning words.

### EX-SYNC: Refresh after an upstream change (record and Joint Origin) (status: built-switched-off)

After an upstream recompute a tag's record and Joint Origin lag what the node built (measured: 15.0 mm after Auto re-fits a longer bar; 4.000 mm until Compute All with the Joint Origin after the node). Compute only checks (read only, 5 ms budget, never raises); the refresh runs right after, when Fusion is idle in that document, as one undo step.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-SYNC-1 | offline-unit | Compute's outcome never depends on the check; maybe_refresh after Undo, busy, already refreshed. | offline tests/test_aruco_extrude_sync.py (1. compute's outcome; 3. maybe_refresh) | every check ok |
| EX-SYNC-2 | fusion-bridge | In Fusion (our documents, AUTO_REFRESH "mine"): thicker, longer (Auto re-fits), Compute All, Undo -- jo 1 and jo 2. | fusion edit_gates_sync (^\[sync jo=) | every step ok (8) |
| EX-SYNC-3 | fusion-bridge | In Fusion: the combined hooks (Extrude refresh + IDs auto-rebuild) over three copies; thicker, longer, Compute All, one Undo -- jo 1 and jo 2. | fusion edit_gates_combined (^\[combined ) | every step ok (ran once unpaced; jo=1 Compute All FAIL = a counting bug, re-scored, not re-run) |

### EX-RESTRUCTURE: Structural edits keep the same node (restructure in place) (status: built-switched-off)

A structural edit (Black only ↔ White + black, Join ↔ New body, pins, raised / recessed, White only) re-makes the node's parts inside the SAME custom feature instead of deleting and creating it (Fusion cascade-deleted what referenced the old node). Atomic: a failure at any step leaves the document identical. Before OK the dialog says in place or rebuild, why, and which features use what goes.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-RESTRUCTURE-1 | offline-unit | The real restructure() on a timeline model: 72 node settings x the same x 2 layouts x sketch / none; a failure at each step. | offline tests/test_aruco_restructure_sim.py | every check ok |
| EX-RESTRUCTURE-2 | offline-unit | restructure_plan over every pair of node structures. | offline tests/test_aruco_extrude_sync.py (4. restructure_plan) | every check ok |
| EX-RESTRUCTURE-3 | offline-unit | Before OK the dialog says what a structural edit does, and to whom. | offline tests/test_aruco_edit_roundtrip.py (before OK: the dialog says) | every check ok |
| EX-RESTRUCTURE-4 | fusion-bridge | In Fusion (our documents): 13 structural edit kinds through the real dialog, jo 1 and jo 2, with RESTRUCTURE_IN_PLACE on for the run. | result edit_gates_run1 | both groups ok |
| EX-RESTRUCTURE-5 | fusion-bridge | In Fusion: a failure injected at each restructure step leaves the document identical (atomic). | result edit_gates_run2 | both groups ok (2026-10-13: jo=1 timed out at 'regroup', document identical) |
| EX-RESTRUCTURE-6 | fusion-bridge | In Fusion (measured): a Joint Origin, a sketch and a joint on the pattern, a fillet on the plate -- what survives each edit, in place and by rebuild. | result edit_gates_run2 | every dependents group measured (the fillet dies either way: OI-FILLET) |

- Gap: A fillet on the plate is deleted by the first structural edit that deletes a combine on the plate, in place or by rebuild (OI-FILLET).

### EX-MIGRATE: Older nodes keep working (status: built)

Nodes made by earlier versions (height / thickness / above parameters, a chosen Frame, the old chamfer checkbox, pre-2026-10-09 origins, tags made before the live node) compute as before and migrate on their next edit, same geometry.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-MIGRATE-1 | offline-unit | height / thickness / above -> Offset / Height gives the same slabs. | offline tests/test_aruco_slabs.py (migration: height / thickness / above) | every check ok |
| EX-MIGRATE-2 | offline-unit | A node made before 2026-10-09 keeps its orientation; settings and records that still carry the removed Frame normalise to OpenCV's frame. | offline tests/test_aruco_frame.py (a node made before 2026-10-09; the removed Frame) | every check ok |
| EX-MIGRATE-3 | offline-unit | The dialog: an old remembered checkbox restores as 'Cut white corner'; the edit dialog fills from an older node and keeps its Origin. | offline tests/test_aruco_extrude_dialog.py (OK remembers; the next dialog restores; the edit dialog fills from a node) | every check ok |
| EX-MIGRATE-4 | fusion-bridge | In Fusion: nodes built the old way (four mode / parameter mixes) compute as before; their next edit rebuilds them with Offset / Height parameters, same geometry. | fusion live_test (\[migration\] ) | every step ok |
| EX-MIGRATE-5 | fusion-bridge | In Fusion: a tag made by the old add-in is re-solved by refresh_live; an old root tag (no body found) moves into its part on rebuild. | fusion live_test (^migration: ; ^OLD: ) | every step ok |

### EX-COLOUR: Colours (status: built)

Every ArUco body shows its colour (white tile, black cells; a joined tile's top and walls white) after create, a compute, an upstream change, Fusion's edit route, a structural rebuild, undo and computeAll.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-COLOUR-1 | fusion-bridge | After create: every ArUco body black / white (new tile, joined tile, black only, white only). | fusion live_test (^colours after create; ^colours: create) | both steps ok |
| EX-COLOUR-2 | fusion-bridge | After a parameter compute, an upstream compute + refresh_live, and Fusion's edit route. | fusion live_test (^colours: after a parameter; ^colours: after an upstream; ^colours: after Fusion's edit route) | every step ok |
| EX-COLOUR-3 | fusion-bridge | After a structural edit (black only -> white + black new body), after undo, after computeAll, and every ArUco body at the end. | fusion live_test (^colours: after a structural; ^colours: after undo; ^colours: after computeAll …) | every step ok |
| EX-COLOUR-4 | fusion-bridge | Colours on the GIM / offset-plane tags, on every height combination and on the pinned tags. | fusion live_test (^GIM/OFF: colours; \[heights\] heights: colours; \[pins\] pins: colours) | every step ok |
| EX-COLOUR-5 | offline-unit | paint() makes every piece of a tile white (the pieces Fusion splits off it) and only its pieces. | offline tests/test_aruco_extrude_fixes.py (A1: paint() makes every piece) | every check ok |

### EX-DIALOG: Dialogs remember their settings (status: built)

The ArUco Extrude dialog builds its inputs per mode / layout, and every ArUco dialog remembers its last OK (globally and per design) in ~/CADExporter/_aruco_settings.json.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-DIALOG-1 | offline-unit | The Extrude dialog builds Origin, Rotate and Corner mark (no Frame, no checkbox); with no target the info line asks for one. | offline tests/test_aruco_extrude_dialog.py (build() and a first refresh) | every check ok |
| EX-DIALOG-2 | offline-unit | The settings file: location, missing / corrupt / odd files, remember and recall, merge, pruning of old designs. | offline tests/test_aruco_settings.py (file location; missing file; remember / recall …) | every check ok |
| EX-DIALOG-3 | offline-unit | Per design: a design's own values win, falling back to the global ones; design keys stable across versions. | offline tests/test_aruco_settings.py (per design; design keys) | every check ok |
| EX-DIALOG-4 | offline-unit | A dialog snapshots its inputs and a new dialog opens as the last OK left it (round trip through the file). | offline tests/test_aruco_settings.py (snapshot; apply; round trip through the file) | every check ok |

- Gap: No Fusion test opens the real ArUco Extrude dialog twice to check it restores (only the offline stand-in; lab_preview's dialog_checks is not run).

### EX-PRESETS: Print presets (status: built-offline-only)

ArUco Extrude can switch between named print presets and save new ones. A preset holds the print settings only (printer profile, cell multiple, dictionary, mode and operation, heights, quiet zone, fuse corners, corner mark, pins, label style), never the target, size, ids, Origin or name. Built-ins are Default (the dialog as it was) and one per PrusaSlicer print profile whose name contains 'Aruco', read through its inherits chain; Import makes a preset of any profile.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-PRESETS-1 | offline-unit | PrusaSlicer profiles read from the fixture (his two Aruco profiles: 0.6 / 0.68 / 0.32 / 0.2 mm); built-ins; save as / update / delete / last; a broken file; Import; Min cell; heights in layers. | offline tests/test_aruco_presets.py | every check ok |
| EX-PRESETS-2 | offline-unit | The dialog: build() (one Preset control, Cells under Size), Save as new preset / Update / Delete in the same list, Fusion's input echoes, Import, OK remembers the preset and Cells, an edited tag WITH cells, heights in l… | offline tests/test_aruco_presets_dialog.py (build(); Save as new preset; echoes …) | every check ok |
| EX-PRESETS-3 | manual | In Fusion: the compact preset control as Fusion draws it; switching presets with the ghost; Save as / Update / Delete with Fusion's input box; Import; 'This tag' in an edit. | manual manual | every check as the note states |

### EX-CELLS: Cell multiple: cells or marker on a print grid (status: built-offline-only)

A tag's sizes can sit on a print grid, chosen with Cells under Size: the marker size in 0.5 mm steps (Default), every cell a whole number of the printer's line width, or a custom width. 'Each cell' makes every module k x m, a ChArUco square j x m with whole lines of white around its marker, a grid's gap rounded up to whole m, and snaps a typed size down onto the grid with a note. A cell under the minimum (mm or lines) is a note, never a refusal.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EX-CELLS-1 | offline-unit | The cell rule: the spec's example, Auto (brute force), boards, ChArUco whole white (odd module counts too), grid gaps, 'marker' cells, the minimum, faces that are not rectangles, the ranked lists. | offline tests/test_aruco_cells.py | every check ok |
| EX-CELLS-2 | offline-unit | Versioning: the legacy rule replayed against goldens made by 196454c (511 sizings, 12 evaluate()), compared exactly. | offline tests/test_aruco_cells_legacy.py | every check ok |
| EX-CELLS-3 | offline-unit | The dialog: Default IS the old defaults (0.5 mm marker steps); the Aruco 0.6 preset puts every cell on 0.68 mm lines; Cells by hand (Custom shows its width, back to Line width); a typed size snaps down with a note; the … | offline tests/test_aruco_presets_dialog.py (Default IS the dialog's defaults; a target: Default sizes as always; Cells by hand …) | every check ok |
| EX-CELLS-4 | manual | In Fusion: Auto size on a 40 mm face with the Aruco 0.6 preset (n k × 0.68 = 28.56 mm, read by OpenCV); a typed 28 mm 6x6 snaps with its note and no node warning; Edit of an older tag: OK unchanged writes nothing, a typ… | manual manual | every check as the note states |

### EX-EDIT: ArUco Edit (older command) (status: built)

The older toolbar ArUco Edit: black thickness, inlaid or raised, dictionary, id; every copy's tag part rebuilt. Still in the ARUCO panel's dropdown.

- Gap: No test since ArUco Extrude became the live node: no recorded Fusion run of ArUco Edit (the bridge's set_black / set_tag_id actions exist, no result file), no offline test of its dialog.

## Area `ids`: ArUco IDs

### IDS-PLAN: Planner (G0, offline) (status: built)

The pure planner: every visible instance its own marker per dictionary family, board id blocks contiguous, ids inside the dictionary, stable re-planning, overrides set / cleared / flagged, ids stored outside linked designs. Since 2026-10-10 the id ledger keeps printed ids (IDS-LEDGER).

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G0.1 | offline-unit | On every fixture model F1-F11, every visible instance gets a marker no other visible instance prints (per family: 4X4_50 ~ 4X4_1000). | offline tests/test_aruco_numbering.py (G0.1 every visible instance) | every check ok |
| G0.2 | offline-unit | Board blocks are contiguous and never overlap another tag's ids. | offline tests/test_aruco_numbering.py (G0.2 board blocks) | every check ok |
| G0.3 | offline-unit | Ids stay inside the dictionary; when they cannot, a refusal names the tag. | offline tests/test_aruco_numbering.py (G0.3 ids stay inside) | every check ok |
| G0.4 | offline-unit | Stable: an already-unique design changes nothing; one new copy gets one new id; overrides are never moved by auto. | offline tests/test_aruco_numbering.py (G0.4 stable) | every check ok |
| G0.5 | offline-unit | Overrides: set, clear to auto (an empty field is auto, never an error), conflicting overrides flagged and kept. | offline tests/test_aruco_numbering.py (G0.5 overrides) | every check ok |
| G0.6 | offline-unit | Owners: an id for an instance inside a linked design is stored in the root, never inside the linked design. | offline tests/test_aruco_numbering.py (G0.6 owners) | every check ok |
| IDS-PLAN-7 | offline-unit | Export consistency: markers.resolve over the export records gives every final id; the node's stored state reads back to the same ids. | offline tests/test_aruco_numbering.py (export: resolve() of the records) | every check ok |
| IDS-PLAN-8 | offline-unit | Helpers, inherited ids inside linked designs, tags in the root component, fixed copies (a linked design's stale record keeps what it prints), and the decoder the geometry gates read built patterns with. | offline tests/test_aruco_numbering.py (helpers; inherited per-copy ids; tags in the root component …) | every check ok |
| IDS-PLAN-9 | offline-unit | The node's dependencies: one per template, on a copy that keeps its id (a depended-on copy cannot be deleted). | offline tests/test_aruco_numbering.py (the node's dependencies) | every check ok |

### IDS-LEDGER: Printed ids stay put (the id ledger) (status: built)

A ledger (one root attribute that outlives the node) records every copy ever numbered and every id it printed; every occurrence on a tagged copy's path carries a stamp. A copy is found by its stamp chain, else its place (0.5 mm), else its path. A new copy gets the lowest block no copy ever printed; only a full dictionary hands out the oldest retired id, with a warning.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G0.7 | offline-unit | Ids survive edits: every case above on a simulated design, the rack replayed. | offline tests/test_aruco_ids_stability.py | every check ok |
| IDS-LEDGER-2 | offline-unit | The Fusion wiring on fake objects: stamps and ledger at the first OK, OK again, rename + node deleted, a pasted stamp, a node from before the ledger, an unreadable ledger, hidden copies renamed. | offline tests/test_aruco_ids_ledger_fusion.py | every check ok |
| IDS-LEDGER-3 | offline-unit | Mutation test: 17 deliberate rule breaks, each caught by the check aimed at it. | artifact ids_mutations | ok: every mutation caught by its own check |
| IDS-LEDGER-4 | fusion-bridge | In Fusion (test document S1): first OK; a copy added in the middle; one deleted; one added after (8, not the deleted 4); the component renamed; a copy re-parented; a holder hidden / a copy added / shown; the node delete… | fusion ids_stability_fusion (.) | every step ok (10) |

- Gap: A 'forget retired ids' action is not built: the ledger only grows (4X4_50 holds 50).

### IDS-COLLECT: Collection (G1) (status: built)

Every tag instance in the design is listed exactly once with its path, including inside linked designs at any depth; hidden / suppressed copies are listed as excluded.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G1.1 | fusion-bridge | Every tag instance listed exactly once with its path, incl. linked designs (F5, F6). | gate gate | every fixture's row ok |
| G1.2 | fusion-bridge | Hidden / suppressed occurrences listed as excluded, not numbered. | gate gate | every fixture's row ok |
| G1.2-offline | offline-unit | Offline: F11's hidden copies (own bulb off or a hidden parent) are exactly 3 and need no part. | offline tests/test_aruco_numbering.py (G1.2 (offline)) | every check ok |
| G1.3 | fusion-bridge | Collection on Zach's rack (F12, read-only) completes in under 10 s and lists the plates' boards, the actuators' round markers, the ChArUco corner and the arm's strip. | gate gate | the row ok: collect under 10 s and every kind of tag found (plate boards, actuator round markers, ChArUco corner, arm strip) |

### IDS-NUMBER: Numbering (G2) (status: built)

After OK with no overrides, no two visible instances print the same marker anywhere (read from the BUILT geometry); OK again changes nothing.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G2.1 | fusion-bridge | No duplicate marker among visible instances, decoded from the built geometry. | gate gate | every fixture's row ok |
| G2.2 | fusion-bridge | Re-running OK is idempotent: geometry and timeline unchanged. | gate gate | every fixture's row ok |

### IDS-OVERRIDE: Overrides (G3) (status: built)

Typing an id overrides; deleting the text returns to auto (shows the auto value), never an error; overrides survive save / close / reopen.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G3.1 | fusion-dialog | Typed id overrides; cleared text returns to auto; words refused readably (fixture rows + the real dialog). | gate gate | every row ok |
| G3.2 | fusion-bridge | An override survives save / close / reopen (a fixture saved once to 'ArUco Test Fixtures'). | gate gate | row ok |

### IDS-GEOM: Per-copy geometry (G4) (status: built)

Each renumbered copy's part prints its resolved id, sits exactly on its copy (incl. ChArUco and transposed origins), leaves no stray bodies -- every part occurrence in one 'Generated ArUco Markers' sub-assembly -- and the original is hidden only where overridden.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G4.1 | fusion-bridge | Every instance's printed pattern matches its resolved id (sampled cells, all fixtures). | gate gate | every fixture's row ok |
| G4.2 | fusion-bridge | Every per-copy part sits on its copy: < 1e-6 m and < 1e-4 deg (F3-F9, ChArUco, transposed origins). | gate gate | every fixture's row ok |
| G4.3 | fusion-bridge | No stray bodies, floating parts, orphan joints or components: the inventory delta is exactly the expected one. | gate gate | every fixture's row ok |
| G4.4 | fusion-bridge | The original tag is hidden ONLY on overridden paths; everywhere else visible. | gate gate | every fixture's row ok |

### IDS-FOLLOW: Per-copy parts follow their copy (status: built)

Each renumbered copy's part is its own component: one occurrence placed at the copy's drawn pose, held by an as-built RIGID joint to the copy (local, nested, and inside an xref in an xref). A part therefore moves with its copy's joints and lands on its copy's link in any exporter.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| IDS-FOLLOW-1 | fusion-bridge | In Fusion (our documents): the sub-assembly + 2 nested parts + root rigid joints in one command; undo / redo; the arm driven 30 deg, captured, recomputed and back; a later item; OK again; delete everything. | fusion ids_follow_nested (.) | every step ok |
| IDS-FOLLOW-2 | offline-opencv | E2E gates (i)-(iv) on F13 / F14 / F14U / F15: every part on its copy's link; a joint turned in Fusion and in the URDF at q ≠ 0; the URDF's ink read by OpenCV; nothing grounded. | artifact e2e | every (i)-(iv) check ok |
| IDS-FOLLOW-3 | offline-opencv | The tag counted once in the export (the part in, the hidden original out); delete paths leave no orphan. | artifact e2e | every check ok |

- Gap: The URDF mass still includes a hidden original inside its parent occurrence (OI-MASS, the exporter's).

### IDS-GENERATED: One 'Generated ArUco Markers' sub-assembly, one timeline item (status: built)

Every part occurrence lives in ONE root sub-assembly 'Generated ArUco Markers' that holds nothing else, never grounded or pinned (nor its parts), deleted with the node or its last part. The node, the sub-assembly and the parts' items sit in ONE 'ArUco IDs' timeline group, created collapsed. Fusion's Delete of a renumbered copy runs as one command (part, joint and copy removed, OK re-run) without the 'Permanently delete features' modal.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| IDS-GEN-1 | fusion-bridge | G4.3 rows (the generated layout checked in the inventory delta). | gate gate | every fixture's row ok |
| IDS-GEN-2 | fusion-bridge | In Fusion (F2): OK, then Fusion's Delete of a renumbered copy (replaced by ours), Undo, Redo. | fusion ids_delete_copy (.) | every step ok |

### IDS-FIDELITY: A part keeps every feature of its original (recolour) (status: built)

A part's tag bodies are the original's material as it is now (every hole, chamfer or cut applied after the tag), re-split between black and white by the new id: P' + T' = P + T. Relief tags change shape only in the cells that flip.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G4.5 | fusion-bridge | Every per-copy part IS the original's material (holes, chamfers, cuts kept). | gate gate | every fixture's row ok |
| G4.6 | fusion-bridge | Every per-copy part's label prints its own id. | gate gate | row ok |
| IDS-FID-3 | fusion-bridge | Mutation: ids_accept F15 with geometry=recut (in memory): G4.5 must go red. | result ids_recut_mutation | at least one G4.5 row red (the mutation is caught) |

### IDS-FRAMES: Frames and export (G5) (status: built)

Every instance's Joint Origin is its OpenCV frame; the export (aruco.json, URDF) has unique ids and one target frame per instance; OpenCV PnP on renders of the built parts agrees.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G5.1 | fusion-bridge | Every instance's Joint Origin = its OpenCV frame (0.000 mm / 0.000 deg). | gate gate | every fixture's row ok |
| G5.2 | fusion-bridge | Export: unique ids and one target per instance, matching G5.1 (what resolve_live reads). | gate gate | every fixture's row ok |
| G5.3 | fusion-bridge | OpenCV PnP on rendered views of the built parts: <= 0.1 mm / 0.1 deg. | gate gate | every row ok |

### IDS-NODE: One timeline node (G6) (status: built)

ArUco IDs is ONE timeline node with its icon; double-click opens the dialog with the current state; deleting it removes every per-copy part, re-shows every original and clears every id it wrote; undo / redo are one step each.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G6.1 | fusion-bridge | ONE timeline node with the ArUco IDs icon. | gate gate | every fixture's row ok |
| G6.2 | fusion-bridge | Double-click / edit opens the dialog with the current state; OK updates in place. | gate gate | every fixture's row ok |
| G6.3 | fusion-bridge | Deleting the node: the inventory equals the pre-IDs inventory. | gate gate | every fixture's row ok |
| G6.4 | fusion-bridge | Undo / redo of the delete are each one step and exact. | gate gate | every fixture's row ok |
| IDS-NODE-5 | fusion-bridge | Fusion's OWN Delete on the selected node (FusionDeleteCommand), then Undo and Redo: node gone / back / gone, inventory exact each time. | result ids_delete_probe | result.ok |

### IDS-DIALOG: Dialog (G7) (status: built)

One table for the whole design (no level picker) on the shared marker table (MT-ROWS): a row's Tag button outlines that copy, the preview equals the built result, Cancel leaves nothing.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G7.1 | fusion-dialog | Clicking a row's Tag button outlines that copy in the viewport (2026-10-13: the shared table). | gate gate | row ok |
| G7.2 | fusion-dialog | The preview equals the built result (ghost vs build: 0.000 mm). | gate gate | row ok |
| G7.3 | fusion-dialog | Cancel leaves no geometry, no graphics, no stored ids. | gate gate | row ok |
| G7.4 | fusion-dialog | No level picker; the table covers the whole design. | gate gate | row ok |

### IDS-ROBUST: Robustness (G8) (status: built)

Upstream edits, Deep Refresh of linked designs and adding / removing copies keep every gate passing; no crash or hang; the user's documents untouched. Upstream edits with nobody opening ArUco IDs: IDS-UPSTREAM (G8.5).

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G8.1 | fusion-bridge | Upstream edits (move a renumbered copy, a thicker tagged plate, a turned Origin), then OK: G2-G5 still pass. | gate gate | every step row ok |
| G8.2 | fusion-bridge | Deep Refresh of a linked design: no crash; G1-G5 pass. | gate gate | row ok |
| G8.3 | fusion-bridge | Adding / removing a copy: only that copy's id appears / disappears. | gate gate | every fixture's row ok |
| G8.4 | fusion-bridge | No crash or hang across the ladder; every test document closed; the user's documents untouched (fingerprint before / after). | gate gate | row ok |

### IDS-UPSTREAM: After an upstream change the IDs node rebuilds by itself (G8.5) (status: built)

The node stores what its parts were built FROM; compute compares that with the design (read only, never an error) and schedules a rebuild; right after the recompute, when Fusion is idle in that document, the hidden command 'Rebuild ArUco IDs' runs OK's apply(): one undo step, ids kept by the ledger. Nothing re-fires after Undo / Redo; once per inputs; at most 3 in 30 s; a failed rebuild is taken back whole and the node WARNS with what to do.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| IDS-UP-1 | offline-unit | The pure halves, a board growing and shrinking, the control flow on fake Fusion objects (schedule, wait, undo, burst, failure), inputs_of; the 2026-10-10 compute erroring on the same node. | offline tests/test_aruco_ids_upstream.py | every check ok |
| G8.5 | fusion-bridge | Upstream edits rebuild on their own (F16, run B2: 10 steps incl. the linked path). | gate gate | every step row ok |
| IDS-UP-3 | fusion-bridge | Mutation: the 2026-10-10 compute (compute=v1) on the same F16 steps must fail (run A: Zach's error reproduced; a mode change DELETED the node). | result g85_v1 | at least one row red (run A: 7 of 8) |
| IDS-UP-4 | fusion-bridge | Probe: what the node may depend on (F2, auto-rebuild off): a pattern face → the IDs node deleted by an Extrude rebuild; the template's own body → kept. | result g85_deps | pattern_face loses the node, target_body keeps it |
| IDS-UP-5 | fusion-bridge | Probe: a copy added after the node -- compute plans 3 rows, a look from outside 4. | result g85_copy | 3 in compute, 4 outside |

### IDS-PERF: Performance (G9) (status: built)

On a rack-sized fixture (~600 bodies, ~20 tag instances): the dialog opens in under 5 s, a preview update under 0.5 s, OK under 60 s.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G9.1 | fusion-dialog | F9P: open < 5 s, preview round trip < 0.5 s, OK < 60 s. | gate gate | row ok |

### IDS-E2E: Zach's bar, end to end (E2E) (status: built)

Two clicks (open ArUco IDs, accept the defaults, OK) and then: every visible instance prints a unique marker (built geometry and OpenCV on renders), every per-copy part sits exactly on its copy, two exports agree and nothing but the id moves, OpenCV PnP on the renders within 0.1 mm / 0.1 deg.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| E2E.1 | fusion-dialog | Two clicks: open ArUco IDs (the real command), accept the defaults (every tag numbered, no duplicates, nothing typed), OK through the dialog's execute. | gate gate | row ok, every fixture F1-F11 |
| E2E.2 | fusion-bridge | Every visible instance prints a unique marker per family: from the BUILT geometry (every cell decoded) and by OpenCV from a render of each instance. | gate gate | row ok |
| E2E.3 | fusion-bridge | Every per-copy part sits exactly on its copy (outline, top plane, axes; mm and deg per instance); the copy's Joint Origin on the original's optical frame. | gate gate | row ok (1e-6 m, 1e-4 deg) |
| E2E.4 | fusion-bridge | Two exports (the add-in's aruco.json / joint_origins.json / markers.json, the CAD Exporter's rebuilt with rebuild_urdf.py) give identical frames and meshes; before vs after the clicks only the id / pattern changes. | gate gate | row ok |
| E2E.5 | offline-opencv | OpenCV PnP on the renders against the exported frames (markers.json optical_world). | gate gate | <= 0.1 mm / 0.1 deg every instance |
| E2E.6 | fusion-bridge | Every frame is where Fusion DRAWS the copy (its full-path proxy), checked by a second route (bodies, Joint Origin as drawn); copies drawn away from their native transforms proved directly. | gate gate | row ok |
| E2E.7 | fusion-bridge | The export lists exactly the design's tag instances (no phantom on a same-named component); a whole-design view shows every expected id once. | gate gate | row ok |
| E2E-PER-FIXTURE | offline-opencv | The E2E per fixture (F1-F15, F12): every check of each fixture's analysis. | artifact e2e | every fixture PASS |

### IDS-RACK: Zach's rack (G10) (status: built)

The last rung: on Zach's 'One Dof Test Rack', with his OK and the document saved first.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| G10.1 | fusion-bridge | Dry run lists every tag (G1.3) and the plan. | gate gate | acceptance.json G10 PASS |
| G10.2 | fusion-bridge | OK on the rack: G2, G4, G5 pass with no manual fixes; the bad 2026-10-09 parts replaced. | gate gate | acceptance.json G10 PASS (OK one undo step, F12 E2E, the table = the rebuilt URDF links, his CAD Exporter folder restored exactly) |
| G10.3 | fusion-bridge | The tag -> id table is sent to the CAD2Robot session. | gate gate | acceptance.json G10 PASS |
| G10-TABLE | fusion-readonly | The rack's tag -> id table cross-checked with the rebuilt URDF: no tag missing, none extra. | artifact rack_tag_table | urdf_check ok |

## Area `table`: Shared marker table

### MT-ROWS: One row per tag copy, the same in both dialogs (status: built)

ArUco IDs and ArUco Export share one marker table: a row is one tag COPY named '<path>\|<key>' (the same string in the IDs table, the IDs node, the Export table and the viewport label; an IDs part is listed under the copy it stands in for). Columns Tag (a button) · ID(s) · Marker · Status; hidden copies last and greyed; '· linked'; boards as '#13-20'. Find in list: a click on a tag or its part selects its row. The selected copy is outlined in magenta; every outline is gone on OK, Cancel and Esc.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| MT-ROWS-1 | offline-unit | Names equal aruco_numbering's; rows from a tag spec; the viewport pick (two tags on one part, IDs parts, sub-assemblies, root). | offline tests/test_aruco_marker_table.py (names: the same string; rows from a tag spec; the viewport pick) | every check ok |
| MT-ROWS-2 | offline-unit | The IDs dialog on the shared table: rows, columns, navigation, an older module's dialog, OK and closing. | offline tests/test_aruco_ids_dialog.py | every check ok |
| MT-ROWS-3 | fusion-bridge | In Fusion (marker_table_test, a test document): M1 IDs, M3 Export, M4 Export after ArUco IDs -- rows, columns, hidden, linked, boards, ticks, duplicates, same names, own parts, picks, Cancel. | result marker_table_test | every check ok |

### MT-ZOOM: Click the selected tag again = zoom (status: built)

One click on a Tag outlines the copy and never moves the camera; clicking the selected tag again zooms to it (a double-click on the selected tag is such a click); 'Zoom to the selected tag' (one setting for both dialogs) zooms on every NEW selection; nothing zooms on a redraw, a tick or typing.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| MT-ZOOM-1 | offline-unit | Double-click timing, the zoom's camera, the navigation state machine (both dialogs), the events Fusion really sends. | offline tests/test_aruco_marker_table.py (double-click timing; the zoom's camera; navigation (both dialogs) …) | every check ok |
| MT-ZOOM-2 | fusion-bridge | In Fusion: click, click again (zoom), the zoom box, timings. | result marker_table_test | every check ok (the final run, a7823ea) |

## Area `frames`: Joint Origin / frames

### JO-OPTICAL: Joint Origin = OpenCV's optical frame (status: built)

Each tag's Joint Origin 'aruco <key>' sits on OpenCV's frame of the tag as built (boards: z into the board), before the node in the timeline, and follows every upstream change.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| JO-OPTICAL-1 | fusion-bridge | Every tag's Joint Origin read back on its optical frame (the record's and the node's NOW) after create, after upstream edits, after the edits and at the end (1 um), plus the heights / pins document. | fusion live_test | jo_verdict == PASS |
| JO-OPTICAL-2 | offline-unit | Optical frames from Joint Origins in the pure core: attached when matching, world = occurrence x Joint Origin, one away from the pattern warns 'rebuild'. | offline tests/test_markers.py (optical frames from Joint Origins) | every check ok |
| JO-OPTICAL-3 | offline-opencv | OpenCV PnP on live_test's Fusion renders (after create, final, final at 8 deg tilt): the Joint Origin equals the optical frame for every tag; PnP vs optical reported. | pnp live_test (^PnP renders) | joint_origin_vs_optical = 0.000 mm / 0.000 deg for every tag (the tool sets no PnP tolerance; its numbers are the evidence) |
| JO-OPTICAL-4 | offline-opencv | Marker-to-marker transforms agree between Fusion's viewport, the URDF render (viser) and the CAD truth. | artifact frames_acceptance | verdict PASS: every pair within the 3 mm / 3 deg ceiling |
| JO-OPTICAL-5 | fusion-bridge | origin_test pnp: one render per tag of every layout x Origin, OpenCV's own board object against the Joint Origin. | fusion origin_test (pnp) | verify_aruco_jo_pnp: Joint Origin = optical frame for every tag |

### JO-AFTER: Joint Origin after the node (frame sketch) (status: built-switched-off)

jo_v 2: the node holds a hidden frame sketch that compute moves onto OpenCV's frame, and the Joint Origin AFTER the node follows it, so features after the tag can use it. An edit that changes an older node can move its Joint Origin behind it, and the dialog says so before OK.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| JO-AFTER-1 | offline-unit | The frame sketch: compute moves it onto OpenCV's frame (Joint Origin after the node). | offline tests/test_aruco_edit_roundtrip.py (the frame sketch) | every check ok |
| JO-AFTER-2 | fusion-bridge | In Fusion: the jo=2 layout through thicker / longer / Compute All / Undo. | fusion edit_gates_sync (^\[sync jo=2\]) | every step ok |
| JO-AFTER-3 | fusion-bridge | In Fusion: every structural edit in the jo=2 layout (RESTRUCTURE_IN_PLACE on for the run). | result edit_gates_run1 | group ok |

### JO-ORPHAN: One Joint Origin per tag: no orphans, no leftover probes (status: built-offline-only)

A tag has exactly one 'aruco <key>' Joint Origin whatever an edit does. Re-solving makes a new Joint Origin and deletes the old one; every Joint Origin a call makes is tracked and what it does not keep is deleted on the way out (an exception included, never a user's); a delete is checked, and an old one that stays is KEPT while the new one goes (the record says why). A gone tag's Joint Origin goes with its record; a Joint Origin that already reads back exact is kept. Extras an older add-in or the bug left are found read-only (aruco_tags.tag_jo_extras: a second 'aruco <key>' or 'aruco <key> (1)', or a default-named Joint Origin in the run at the tag's own, never one a joint uses); the bridge's jo_cleanup deletes only the extras NAMED to it, in the active document named to it, as one undo step.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| JO-ORPHAN-1 | offline-unit | Orphans: a gone tag's Joint Origin goes with its record. | offline tests/test_aruco_edit_roundtrip.py (orphans) | every check ok |
| JO-ORPHAN-2 | offline-unit | The real edit path (edit → refresh_one → _write_record → ensure_joint_origin, and the rebuild path) on a stand-in design: Fusion as measured; the old Joint Origin that does not go; an exception after the new one exists;… | offline tests/test_aruco_jo_one_per_tag.py | every check ok (66) |
| JO-ORPHAN-3 | fusion-bridge | In Fusion (our documents): Zach's tag through 12 edits of every kind in a row in the real dialog -- ONE Joint Origin after each, 'aruco <key>', the record's, exact (jo=1 with RESTRUCTURE off and on, jo=2); a joint on th… | fusion edit_gates_jo (^\[jo_one; ^\[jo_joint) | every step ok |

- Gap: The fix and the jo_one / jo_joint gates (2026-10-16) have not run in Fusion yet.

### JO-LEAK: Exports skip an older add-in's leaked 'Joint Origin4' (status: built)

bam_joint_origins skips a Joint Origin only on the exact leak signature (default name, in a component with ArUco tag records, the very next timeline item the tag's own 'aruco <key>'), with a warning naming both; anything a person placed or named is exported. jo_census describes every Joint Origin of a design (read only).

| test | kind | checks | how | pass |
|---|---|---|---|---|
| JO-LEAK-1 | offline-unit | The leak signature is not exported; anything else is. | offline tests/test_joint_origins.py (an older ArUco add-in's leaked Joint Origin is not exported) | every check ok |
| JO-LEAK-2 | fusion-readonly | On the rack (read only): both leaked 'Joint Origin4's are exact duplicates of the tag's own and are not exported. | result jo_census_rack | two leaks, both 0.000 mm from the tag's Joint Origin |

## Area `export`: Export

### EXP-TYPES: ArUco Export dialog: one type per run (status: built)

The dialog lists PrusaSlicer project / STL files / PDF print sheet (each with its icon), shows only that type's options, validates OK, remembers per type; export refreshes live tags first. Its parts table is the shared marker table (MT-ROWS).

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-TYPES-1 | offline-unit | First run: the type list is the first input, three types each with its icon, PrusaSlicer project selected. | offline tests/test_aruco_export_dialog.py ((top); first run) | every check ok |
| EXP-TYPES-2 | offline-unit | OK's validity per type (no part ticked: STL disabled, info says so), Reset, OK passes the right args (test hook), reopen restores the last type with its options. | offline tests/test_aruco_export_dialog.py (OK's validity and Reset; OK; reopen) | every check ok |
| EXP-TYPES-3 | offline-unit | Settings saved by the dialog of before the types load cleanly; a running Fusion's old handler still works. | offline tests/test_aruco_export_dialog.py (settings saved by the dialog of before; the dialog of before the types) | every check ok |
| EXP-TYPES-4 | fusion-bridge | Export refreshes live tags first (refresh_live) and resolve() reads them. | fusion live_test (^refresh_live; ^resolve$) | both steps ok |
| EXP-TYPES-5 | fusion-dialog | The real Export dialog: each type picked in turn -> visible inputs, info line, OK enabled, the args OK passes; Reset; OK on STL through the test hook. | fusion export_dialog (.) | every dialog check ok |

### EXP-PDF: PDF print sheet and marker images (status: built)

A true-size PDF on letter or A4 (multi-page, never scaled, ruler bars, a printer-safe margin), '#id' knocked out in the bottom border, an orientation triangle and the part name in the top border; plain PNG / SVG images per marker plus '_marked' variants; markers.json.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-PDF-1 | offline-unit | Marker images: PNG / SVG sized in modules with the quiet zone, 8-bit, cells == the grid. | offline tests/test_aruco_output.py (marker_png; marker_svg) | every check ok |
| EXP-PDF-2 | offline-unit | Layout on letter and A4: every item placed exactly once, spills onto more pages, never scales, the sticker = marker + 2 x quiet. | offline tests/test_aruco_output.py (layout) | every check ok |
| EXP-PDF-3 | offline-unit | The PDF file: %PDF-1.4 ... %%EOF, page count == layout, MediaBox per paper; a 5 / 20 / 35 mm margin holds every sticker, label and ruler. | offline tests/test_aruco_output.py (PDF; page margin) | every check ok |
| EXP-PDF-4 | offline-unit | Board images (PNG with pHYs, white quiet zone; SVG) and boards on a print sheet: grid and ChArUco stickers sized extent + 2 x quiet x module. | offline tests/test_aruco_board.py (boards on a print sheet; board_png / board_svg) | every check ok |
| EXP-PDF-5 | offline-opencv | Rasterised at 600 dpi (letter and A4, 2+ pages): every (dictionary, id) found exactly once where the layout put it, upright, side within +-0.15 mm; the 100 mm / 4 in rulers measured. | artifact verify_output | both sheets pass, worst side error <= 0.15 mm |
| EXP-PDF-6 | offline-opencv | A grid, two ChArUco boards and a single on letter at 600 dpi: every id where placed, marker and square sides within +-0.15 mm. | artifact verify_boards | sheet.pass |
| EXP-PDF-7 | fusion-bridge | In Fusion: the PDF type writes the sheet, the marker images, markers.json and the records, and no STL / 3MF. | result export_types_test | exports.pdf.all_ok |
| EXP-PDF-8 | offline-opencv | Study: '#id' in the black border costs nothing measurable (black_id_white >= -1 pt) and neither does the suggested default (id + triangle, combo_black); zero wrong ids. | artifact marks_study | both deltas >= -0.01, no wrong id in any design |
| EXP-PDF-9 | offline-opencv | Study (why not the white ring): a grey id in the 1-module quiet zone costs more than 5 pts (white_q1_id). | artifact marks_study | delta <= -0.05 (the doc: -11.4 pts) |

- Gap: No unit test pins the PDF's id / orientation-triangle / top-label geometry (cap <= 0.5 module, corner cells clear); the 600 dpi oracle ran before the top label landed (2def70a).

### EXP-STL: STL files (status: built)

One STL per body of the chosen parts in aruco/stl/ (face-down orientation), stale STLs of ours removed, nothing else written.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-STL-1 | offline-unit | write_part_stls: one STL per body of the chosen parts, a stale STL of ours removed, no 3MF / beds; a part with 0 visible copies still written when chosen. | offline tests/test_print_beds.py (write_part_stls) | every check ok |
| EXP-STL-2 | fusion-bridge | In Fusion: the STL type writes one STL per body in aruco/stl/ and the records; no PDF, 3MF, images or print3d/. | result export_types_test | exports.stl.all_ok |

### EXP-PRUSA: PrusaSlicer project and Send to PrusaSlicer (status: built)

The PrusaSlicer type writes a .3mf project with every tag part on as many beds as needed (tile on extruder 1, cells on extruder 2) plus per-bed files; Send to PrusaSlicer makes one project of the selection and opens it.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-PRUSA-1 | fusion-bridge | In Fusion: the PrusaSlicer type writes the project, beds, parts.json, STLs and the records; no PDF, images or markers.json. | result export_types_test | exports.prusaslicer.all_ok |
| EXP-PRUSA-2 | offline-unit | write_beds: the project, one bed, both copies, the bed from the printer preset, oriented parts written. | offline tests/test_print_beds.py (write_beds) | every check ok |
| EXP-PRUSA-3 | offline-unit | Send to PrusaSlicer's project (write_selection_project): one object per selected occurrence, volumes = its bodies, black by role or name. | offline tests/test_print_beds.py (write_selection_project) | every check ok |
| EXP-PRUSA-4 | offline-unit | Finding PrusaSlicer: a hint that exists is used, the settings file's override wins and survives load / save. | offline tests/test_aruco_settings.py (PrusaSlicer) | every check ok |

- Gap: Send to PrusaSlicer has no recorded Fusion run (the bridge's demo_send action exists, no result file).

### EXP-HIGHLIGHT: The Export viewport shows what will print (status: built)

While the Export dialog is open every copy of a ticked part gets an orange box and its ids, an unticked part's copies a grey box, the selected row magenta. Drawn only from executePreview into tagged groups, so it follows every tick and is gone on OK, Cancel and close.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-HIGHLIGHT-1 | offline-unit | The dialog: filament slots and the viewport highlight (an input change draws nothing, the preview event draws; ticks; the PDF type clears). | offline tests/test_aruco_export_dialog.py (filament slots) | every check ok |
| EXP-HIGHLIGHT-2 | fusion-bridge | In Fusion (marker_table_test M3): ticks kept in step and Cancel leaves no group. | result marker_table_test | both ok |
| EXP-HIGHLIGHT-3 | manual | The highlight lifecycle in the real dialog: groups after the preview, after an untick, after Cancel. | manual manual | groups 1 open, a change on untick, 0 after close |

### EXP-SLICER: PrusaSlicer project with his own presets and MMU filament slots (status: built)

The PrusaSlicer type mirrors PrusaSlicer's own last-used presets (printer, print, filament per slot, physical printer): no recolouring, no bed override, no preset of ours. Black and White filament slots (1 / 2 by default, remembered); the same slot for both is refused.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-SLICER-1 | offline-unit | Last-selected presets, the mirrored profile, nothing of ours in the project, slots, no PrusaSlicer settings → no config. | offline tests/test_print_beds_slicer.py | every check ok |

- Gap: The rack's slicing check (2026-10-10) is recorded in commit 35296a4 only; no result file in reports.

### EXP-PROGRESS: A progress bar with time left (status: built)

During an export Fusion's progress dialog reads 'Part 5 of 53 · about 40 s left' / 'Writing: <part> · <body>', then 'Laying the parts out on beds…'; Cancel stops between bodies.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-PROGRESS-1 | offline-unit | eta_text / progress_message, OK through a fake progress dialog. | offline tests/test_aruco_export_dialog.py (the progress bar) | every check ok |

- Gap: The Fusion captures of the bar (export lab, 2026-10-10) are recorded in commit 58f4c3d only.

### EXP-CHECK: What the printer gets decodes per copy (the 3MF oracle) (status: built)

tools/verify_aruco_print3mf.py (no bam_cad_core): every object of aruco_tags.3mf, rendered from below in its extruder colours, is read by OpenCV as exactly its own ids, each once; every black square within 0.25 mm of its size. Copies are counted by component (not name), labels are unique, only live records print.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| EXP-CHECK-1 | offline-opencv | The oracle on the rack's recorded print export (F12 print2). | command command | every object decodes exactly |

## Area `beds`: Print beds

### BEDS-PACK: Packing on beds (status: built)

Tags packed on the printer's bed (MK4: 250 x 210 mm), spilling onto as many PrusaSlicer 2.9 beds as needed (its spiral grid and gap), every copy its own object.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| BEDS-PACK-1 | offline-unit | STL round trip (binary and ASCII) and units measured from the mesh, not trusted from the manifest. | offline tests/test_print_beds.py (STL round trip; units are measured) | every check ok |
| BEDS-PACK-2 | offline-unit | Packing: 41 tags of 40 mm on an MK4 bed -> 20 per bed, 3 beds, footprints kept. | offline tests/test_print_beds.py (packing) | every check ok |
| BEDS-PACK-3 | offline-unit | PrusaSlicer 2.9 multi-bed geometry: the spiral bed grid, the gap = 0.3 x diagonal, capped at 100 mm. | offline tests/test_print_beds.py (PrusaSlicer 2.9 multi-bed geometry) | every check ok |
| BEDS-PACK-4 | offline-unit | Every copy its own object '<part> (k/n)' with both volumes (instances=True keeps one object). | offline tests/test_print_beds.py (every copy its own object) | every check ok |

### BEDS-ORIENT: Print orientation (status: built)

Face down when nothing is proud (the cells on the bed), otherwise face up; 'cad' keeps the modelled orientation with an overhang / supports guard.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| BEDS-ORIENT-1 | offline-unit | The orientation rule: inlaid black and nothing proud -> face down, the cells ON the bed (z min = 0); raised -> face up. | offline tests/test_print_beds.py (orientation rule) | every check ok |
| BEDS-ORIENT-2 | offline-unit | orientation='cad': no rotation, the inlaid black stays on top; a part on a 4 mm stalk is kept with a supports warning. | offline tests/test_print_beds.py (orientation='cad') | every check ok |

### BEDS-PROJECT: Project files and presets (status: built)

The 3MF project and per-bed files carry the printer / print / filament presets resolved from PrusaSlicer's vendor bundle (MK4 MMU3), tile on extruder 1 and cells on extruder 2, only the chosen parts.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| BEDS-PROJECT-1 | offline-unit | Project config from a vendor bundle: the inherits chain resolved (own keys win), meta keys not copied, extruders / bed / height read. | offline tests/test_print_beds.py (project config from a vendor bundle) | every check ok |
| BEDS-PROJECT-2 | offline-unit | 3MF and project files: copies placed (0-copy parts skipped), project + per-bed + parts + layout files, the required 3MF members. | offline tests/test_print_beds.py (3MF and project files) | every check ok |
| BEDS-PROJECT-3 | offline-unit | Part selection: only the named parts placed, the others skipped with a reason, an unknown name warned. | offline tests/test_print_beds.py (part selection) | every check ok |
| BEDS-PROJECT-4 | offline-unit | PrusaSlicer as the judge on a real export: every 3MF read back (closed manifolds, extruder roles, each copy on one bed), presets diffed against the bundle, --info and --export-gcode per bed (tool changes, wipe tower, ma… | artifact verify_print_beds | 0 failed of the checks run |

- Gap: No printed-and-measured bed: the colours and the face-down cells are checked in PrusaSlicer's slices only.

## Area `cadx`: CAD Exporter / URDF integration

### CADX-COLLECT: CAD Exporter collects the tags (status: built)

The exporter's payload carries every tag record (incl. tags inside linked designs) and the overrides; the ArUco IDs node is read as root-level overrides; a suppressed node adds nothing.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| CADX-COLLECT-1 | offline-unit | Schema + units; one modelled tag (variant parts skipped); overrides on native occurrences at both levels; linked tags kept; the IDs node's ids as root-level overrides resolving to distinct markers. | offline tests/test_aruco_collect.py | every check ok |

### CADX-RESOLVE: Per-copy ids and world poses (markers.resolve) (status: built)

markers.resolve gives every copy its id (inheritance, outermost override wins) and its world pose; serials planned at the deepest level that works; boards get an id block per copy.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| CADX-RESOLVE-1 | offline-unit | resolve: one instance per copy, inheritance and outermost-wins; six copies of one tag collide until numbered. | offline tests/test_markers.py (resolve: inheritance) | every check ok |
| CADX-RESOLVE-2 | offline-unit | World poses: occurrence transform x tag frame, design units scaled, rpy. | offline tests/test_markers.py (world poses) | every check ok |
| CADX-RESOLVE-3 | offline-unit | Serials at the deepest level that works; boards: an id block per copy, collisions reported once per pair. | offline tests/test_markers.py (serials: deepest level; boards: an id block per copy) | every check ok |
| CADX-RESOLVE-4 | offline-unit | Two components share a name (the rack, 2026-10-09): each tag record carries its own component's occurrence paths, so no phantom instances or swapped tags. | offline tests/test_markers.py (two components share a name) | every check ok |

### CADX-URDF: URDF target frames (status: built)

The URDF gets one aruco_<id>_target (grid_ / charuco_) link per tag instance on OpenCV's frame (from the Joint Origins, via aruco.json + joint_origins.json and tools/rebuild_urdf.py); today's output equals the goldens byte for byte.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| CADX-URDF-1 | offline-unit | Today's URDF and markers.json equal the goldens byte for byte; no tag-frame link left; 2026-10-08's records (a chosen Frame) come out on OpenCV's frame. | offline tests/test_aruco_frame.py (the URDF: today's output is the goldens'; 2026-10-08's records) | every check ok |
| CADX-URDF-2 | offline-unit | Every target is OpenCV's frame, worked out by hand through an independent URDF reader (yourdfpy FK). | offline tests/test_aruco_frame.py (every target is OpenCV's frame, worked out by hand) | every check ok |
| CADX-URDF-3 | offline-opencv | The URDF's marker frames sit on the marker ink: frame corners FK'd from the URDF vs cv2.aruco on the exported meshes' render (demo export, every facing frame). | render render | the tool prints PASS: worst corner error <= 0.5 mm, right ids |
| CADX-URDF-4 | offline-opencv | OpenCV reads every per-copy id (0-11) off the renders of the exported URDF. | artifact demo_detections | 12 distinct ids across the views |
| CADX-URDF-5 | offline-unit | The CLI oracle on a real export: every aruco_*_target frame at q = 0 vs markers.json's optical_world (1e-6 m / rad), every tag with a target of its own. | manual manual | exit 0 |

## Area `safety`: Safety / bridge

### SAFE-BRIDGE: Dev bridge gating (status: built)

The file bridge is off unless ENABLED; agents' Fusion use is closed unless a FUSION_OPEN window is open (PAUSED_UNTIL pauses it); it refuses nested requests and waits while the user has any command open; an allow-list of actions.

- Gap: Partly covered offline since 2026-10-09: tests/test_fusion_presence.py drives the client against a temporary bridge folder (pause window, presence refusal, busy retry). ENABLED, FUSION_OPEN and the open-command wait have no test of their own.

### SAFE-DOCS: Tests never touch the user's documents (status: built)

Every lab works in a NEW document of its own, checks before each step that it is still the active one (aborts if not), clears selections before deleting / rebuilding, terminates its dialogs, re-activates the user's document BEFORE closing its own (closing the active one could activate a design whose IDs node then rebuilds), and closes only its own documents.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| SAFE-DOCS-1 | fusion-bridge | export_types_test closes its own document and puts the user's back. | result export_types_test | closed == document, reactivated set |
| SAFE-DOCS-2 | fusion-bridge | (= G8.4) Across the IDs ladder the user's open documents are untouched (fingerprint before / after) and no run aborted. | gate gate | row ok |
| SAFE-DOCS-3 | fusion-bridge | marker_table_test: the user's documents untouched. | result marker_table_test | ok |
| SAFE-DOCS-4 | fusion-bridge | The ids stability scenario (S1): the user's documents untouched. | result ids_stability_fusion | true |

- Gap: No test deliberately switches documents mid-run to prove the guard aborts (it has fired for real, 2026-10-08).

### SAFE-PRESENCE: fusion_presence: agents stop while Zach uses Fusion (status: built)

tools/fusion_presence.py reads only (input idle time, Fusion foreground / title / unsaved '*', busy bridges, optionally the add-in's ping) and says active / idle; active = evidence within 120 s. tools/aruco_bridge.py refuses every request but ping (exit 3) while he is active, also while retrying a busy bridge; the guard keeps a pause window of its own and lifts only that.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| SAFE-PRESENCE-1 | offline-unit | Title parsing, verdicts, foreground history, title changes, the ArUco ping, unwatched gaps, wait-idle / watch, shared state, the guard, the bridge client. | offline tests/test_fusion_presence.py | every check ok |

### SAFE-CRASH: Crash forensics: read the dump, write the note (status: built)

tools/fusion_minidump.py reads a Fusion CER minidump without a debugger (the exception and a heuristic stack walk named by the installed DLLs' exports). Each crash under test load gets a note with the timeline from our own files.

- Gap: No test of tools/fusion_minidump.py (used on the 2026-10-09 and 2026-10-13 dumps).

### SAFE-LIVE: Live code is his code (atomic patches, reload-proof dialogs) (status: built)

Every bridge request (ping included) hot-reloads the add-in's modules into Zach's running Fusion. Patches are written to a temp file, py_compile'd, then os.replace'd onto the module; a dialog built by an older module keeps working after a reload (missing inputs tolerated); code inside compute is wrapped so no exception can change the compute result.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| SAFE-LIVE-1 | offline-unit | A hot reload under a dialog built before Auto position. | offline tests/test_aruco_extrude_dialog.py (a hot reload under a dialog built before Auto position) | every check ok |
| SAFE-LIVE-2 | offline-unit | Hot reloads under dialogs built by older code (before presets, before the compact layout). | offline tests/test_aruco_presets_dialog.py (hot reloads under dialogs built by older code) | every check ok |
| SAFE-LIVE-3 | offline-unit | The IDs dialog built by an older copy of the module. | offline tests/test_aruco_ids_dialog.py (a dialog built by an older copy of the module) | every check ok |
| SAFE-LIVE-4 | offline-unit | The after-compute hook: digest only, read only, a budget, never raises. | offline tests/test_aruco_extrude_sync.py (2. after_compute) | every check ok |

- Gap: No tool enforces the atomic patch: it is a rule for whoever edits the live tree.

### SAFE-PACING: Test pacing around Fusion's recovery autosave (status: built-offline-only)

No heavy gate while a user document is modified and unsaved (a distinct exit code); one test document per run; ≥ 3 s pumped settle after every Undo, Redo, save, getLatestVersion and Compute All; ≥ 5 s quiet before closing a test document; watch the CrashRecovery folder (read only); ≥ 5 s after a close, ≥ 60 s between runs; never change Fusion's recovery preferences.

- Gap: aruco_ids_accept (G8.5 and the ladder) does not pace yet; no offline test of the pacing helper.

## Area `public`: Public repo

### PUB-SYNC: fusion-aruco public copy (status: built)

tools/sync_from_cad_exporter.py (in the public checkout) copies the managed file set from a commit of this branch, scrubs Zach's designs / Fusion windows and his user path, and warns on imports outside the set; the public checkout's own tests run standalone.

| test | kind | checks | how | pass |
|---|---|---|---|---|
| PUB-SYNC-1 | offline-unit | A dry-run sync from this branch's HEAD: no WARNING (every imported core module is in the copied set). | command command | no WARNING line; 'nothing written' |
| PUB-SYNC-2 | offline-unit | The public checkout's own offline tests pass there, standalone (the README's loop). | suite suite | every test file exits 0 |

- Gap: The sync's managed set lags the add-in: aruco_numbering, tools/fusion_presence.py, two golden makers, tests/aruco_label_fixtures.py and tests/fixtures/ are not in it (OI-PUBLIC-SYNC).

### PUB-README: Public README (draft for the next sync) (status: proposed)

docs/fusion_aruco_README_draft.md: the public repo's README brought up to date (ArUco IDs as one table, the label, presets, the shared marker table, the spec and acceptance pages). The README is OWNED by the public repo (the sync never writes it), so it is pasted there by hand at the next refresh.

- Gap: The public README still describes the per-level ArUco IDs and 'Number duplicates' (superseded).


Totals: 9 areas, 71 features, 290 tests.
