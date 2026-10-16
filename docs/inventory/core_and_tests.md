# Inventory: the Fusion-free core, its tests and its spec

What exists today in REF, the Fusion add-in branch, so planners and builders of ArUco Studio know exactly what they can lift and what they must keep bit for bit.

| | |
|---|---|
| REF | `C:\Users\BAM\Documents\cad-exporter\.claude\worktrees\aruco-fusion-plugin-0e9bcb`, read only |
| Pinned at | commit `c8216ff` (2026-10-16). The working tree's core, tests and docs equal it; only `docs/design_aruco_ui_v2.md` moved after. |
| Made by | reading every `CADExporter/bam_cad_core/aruco_*.py`, every `tests/test_aruco_*.py`, `docs/aruco_spec.json` and the design / proposal / research docs; then running the 17 Fusion-free suites with `C:\Users\BAM\miniconda3\python.exe` (3.11.5), a scratch `USERPROFILE` and `PYTHONDONTWRITEBYTECODE=1`. Nothing was written into REF. |
| Companion file | `docs/inventory/spec_tests.md`: every one of the spec's 290 tests, one line each, generated from the JSON. |

## 0. The picture in numbers

| What | Where | Size | Imports `adsk`? |
|---|---|---|---|
| The ArUco core | `CADExporter/bam_cad_core/aruco_*.py` (9 modules) + `aruco_dictionaries.json` | 8,335 lines + 44 lines of JSON | no |
| Core modules the ArUco core depends on | `markers.py` (1,428), `fiducials.py` (617), `print_sheet.py` (734), `print_beds.py` (2,289) | 5,068 lines | no |
| The Fusion add-in | `ArucoMarkers/*.py` (45 files) | about 47,000 lines | 40 of 45 yes |
| Fusion-free add-in modules (pure logic that lives in the add-in, not the core) | `aruco_presets.py` (570), `aruco_settings.py` (326), `aruco_prusa.py` (273), `aruco_ui_config.py` (61), `aruco_core.py` (52) | 1,282 lines | no |
| Tests | `tests/test_aruco_*.py`, 43 suites + 3 helpers (`aruco_label_fixtures.py`, `aruco_trim_fixtures.py`, `aruco_ui_stubs.py`) | 20,523 + 1,108 lines | 27 suites load a stand-in `adsk` (2 of them only for their golden's `evaluate()` cases); 16 need none |
| Spec | `docs/aruco_spec.json` | 9 areas, 71 features, 290 tests | |

Stdlib only, everywhere in the core: no numpy, no cv2. Fusion's Python has neither, so the core was written without them. The OpenCV checks live in `tools/` and run in another venv.

### Units and frames (the conventions the Studio must keep)

| Module | Units | Frame |
|---|---|---|
| `aruco_dict` | modules (whole numbers) | origin = top-left of the black border, y DOWN (the image), `1 = black` |
| `aruco_board` | metres | CENTRE frame: origin the pattern's centre, +x right, +y UP, +z out of the board. `opencv_frame()` gives OpenCV's reported frame in it (boards: top-left outer corner, y down, z INTO the board; single: identity). |
| `markers.TagSpec` | metres | the tag record; `extent_m`, `tile_size_m`, `module_m` |
| `aruco_autosize` | metres | a face's box (w x h) or its loops in the face's own 2D frame; placement `{cx, cy, angle_deg, w, h, clear}` in that frame |
| `aruco_origin` | degrees | quarter turns CCW about the face normal, in the frame the tag was laid out in; `TURNS_CW = (0, 270, 180, 90)` is the dialog's "Rotate" order |
| `aruco_slabs` | mm along the face normal | 0 = the face / sketch plane, + = out of it; a slab is `(low, high)` |
| `aruco_chamfer`, `aruco_label`, `aruco_trim` | mm | the PATTERN frame: origin the pattern's centre, u = image right, v = image up, AFTER the Origin turn; `Rect = (u0, v0, u1, v1)`; polygons CCW |
| `aruco_numbering` | design units (`markers.UNIT_TO_M`), ids | occurrence paths `A:1+B:2`, instance names `<path>\|<key>`; world poses as row-major 4x4 |

## 1. The core, module by module

In dependency order. "Public" = not underscored. Signatures are copied from the source.

### 1.1 `aruco_dict.py`: 237 lines

Purpose: OpenCV's 21 predefined ArUco / AprilTag dictionaries without OpenCV. Reads `aruco_dictionaries.json` (made once by `tools/gen_aruco_dictionaries.py` from cv2 5.0.0, checked id by id by `tools/verify_aruco_output.py`), re-checks its sha256 on load, and draws a marker as a grid, as merged black rectangles, as PNG and as SVG. Nothing here scales a marker.

Dependencies: stdlib (`hashlib`, `json`, `struct`, `zlib`); `.fiducials.ARUCO_DICTS` (the name list and capacities).

| Public | Signature | Returns |
|---|---|---|
| `TABLE_SCHEMA` | `"bam_aruco_dictionaries/1"` | the JSON's schema string |
| `DICTIONARY_NAMES` | `tuple(ARUCO_DICTS)` | 21 names, OpenCV's order |
| `dictionary_info(name)` | | `{name, bits, capacity, family, max_correction_bits, modules}` (`modules = bits + 2`) |
| `marker_grid(name, marker_id: int)` | | `(n+2) x (n+2)` list, row 0 = top, `1 = black`, border included |
| `black_rects(name, marker_id: int)` | | `[(x, y, w, h)]` in modules, disjoint, sorted, covering exactly the black |
| `marker_png(name, marker_id, module_px=20, quiet_modules=1)` | | 8-bit greyscale PNG bytes, whole pixels per module |
| `marker_svg(name, marker_id, size=None, quiet_modules=1)` | | SVG text, viewBox in modules, one black path |

Table facts: `DICT_<n>X<n>_50/100/250` are prefixes of `DICT_<n>X<n>_1000` (`prefix_check` in the JSON); per marker the inner bits are packed MSB-first as hex. Unknown names raise `ValueError`; a case-folded name is accepted.

Versioned: the table schema only. No rule versions.

### 1.2 `aruco_board.py`: 343 lines

Purpose: grid boards and ChArUco boards as OpenCV makes them: counts, ids, extents, object points, chessboard corners, the black ink as rectangles, the frame OpenCV reports, PNG and SVG. Every convention was measured on cv2 5.0.0 and is written in the module docstring (grid / ChArUco origin top-left, y down, z into the board since OpenCV 4.7; single marker = IPPE_SQUARE points).

Dependencies: stdlib; `aruco_dict`.

| Public | Signature |
|---|---|
| `LAYOUTS` | `("single", "grid", "charuco")` |
| `BoardSpec` (dataclass) | `layout, dictionary, first_id, marker_length_m, rows=1, cols=1, separation_m=0.0, square_length_m=0.0, legacy=False` |
| `check_spec(spec) -> dict` | raises `ValueError` for what cv2 refuses (grid gap <= 0, ChArUco < 2x2 or square <= marker, ids past the capacity); returns `dictionary_info` |
| `marker_count(spec) -> int`, `ids(spec) -> List[int]` | row-major from the top-left, as OpenCV |
| `extent_m(spec) -> (w, h)` | the black pattern, no quiet zone |
| `object_points(spec) -> {id: [(x, y, z) x4]}` | OpenCV's reported frame, corners TL, TR, BR, BL |
| `charuco_corners(spec) -> [(x, y, z)]` | inner chessboard corners, OpenCV's order |
| `marker_corners_m(spec) -> {id: [(x, y) x4]}` | centre frame, y up |
| `black_rects_m(spec) -> [(x0, y0, x1, y1)]` | the ink, centre frame, metres |
| `opencv_frame(spec) -> [16 floats]` | the reported frame's pose in the centre frame |
| `board_png(spec, px_per_m=10000.0, quiet_m=0.0) -> bytes` | with a pHYs chunk |
| `board_svg(spec, quiet_m=0.0) -> str` | viewBox in mm, true size |

The ChArUco colour rule `_charuco_black(x, y, rows, legacy)` (black unless `legacy` AND an even row count) is private but used by `aruco_chamfer`, `aruco_label` and `print_sheet`.

Versioned: nothing. The `legacy` flag mirrors OpenCV's `setLegacyPattern`.

### 1.3 `aruco_origin.py`: 166 lines

Purpose: the "Origin" choice. The tag's frame is always OpenCV's; the only freedom is how the pattern lies on the face: a quarter turn. Names the four choices per layout, steps them clockwise, says which boards swap cols / rows at 90 / 270, and works out OpenCV's frame for each turn from OpenCV's conventions alone.

Dependencies: stdlib (`math`).

| Public | Signature |
|---|---|
| `TURNS_CW` | `(0, 270, 180, 90)` |
| `ORIGIN_RULE` | `2` (settings `"origin_v"` of a node made since 2026-10-09) |
| `raw_turn(turn) -> int`, `norm(turn) -> int` | whole degrees in [0, 360); a quarter turn or 0 |
| `effective(turn, layout, cols=1, rows=1, rule=ORIGIN_RULE) -> (int, str)` | the turn a node gets and a note; `rule=None` is the pre-2026-10-09 rule |
| `transposes(layout, turn) -> bool`, `built(layout, turn, cols, rows) -> (cols, rows)` | which boards swap, and the board as built |
| `rotate_cw(turn) -> int`, `corner(turn) -> str`, `up(turn) -> str`, `label(layout, turn) -> str`, `items(layout)`, `turn_of(layout, name)`, `corners_of(layout)` | the dialog's words |
| `opencv_in_layout(layout, turn, w, h) -> (origin, x, y, z_sign)` | OpenCV's frame in the laid-out frame; the tests' yardstick |
| `describe(layout, turn, cols=1, rows=1) -> str` | the dialog's Joint Origin line |

Versioned rule: `ORIGIN_RULE`. See the table in 1.10.

### 1.4 `aruco_slabs.py`: 442 lines

Purpose: heights in Extrude's words. Each colour is an extrude from an Offset, Height further (either sign). From where the two slabs sit it derives the node's parts (tile, pin, pocket, pattern, recess, trim), the record's surface / depth / raise / recess, the dialog's notes, and the locating pins' outlines with their tolerance growth.

Dependencies: stdlib (`math`).

| Public | Signature |
|---|---|
| constants | `MODES=("both","black","white")`, `OPS=("join","new")`, `WHITE_HEIGHT=2.0`, `BLACK_HEIGHT=-0.6`, `PATTERN_HEIGHT=-0.6`, `WHITE_MIN_MM=0.1`, `BLACK_MIN_MM=0.05`, `LIMIT_MM=50`, `PIN_SHAPES=("none","triangle","round")`, `PIN_SIZE_MM=3`, `PIN_LENGTH_MM=2`, `PIN_TOL_MM=0.15`, `PIN_MARGIN_MM=1`, `PIN_GAP_MM=1`, `PIN_LIMITS`, `HOLE_OVERSHOOT_MM=0.01`, `NUMBER_KEYS`, `PIN_KEYS` |
| `slab(offset, height) -> (low, high)` | |
| `snap_height(h, minimum, prev=None) -> float`, `clamp_offset(v) -> float` | the dialog's write-back |
| `white_top(mode, n) -> float`, `default_numbers(mode="both") -> dict`, `pin_defaults() -> dict` | |
| `from_legacy(mode, height, thickness, above) -> dict` | a node made before 2026-10-08 (parameters height / thickness / above) as Offset / Height pairs, same geometry |
| `Layers` (dataclass) | `mode, white, black, pattern, surface, depth, raise_, recess, gap`; `.detector`, `.thickness` |
| `layers(mode, n, has_body=True) -> Layers` | raises `ValueError` for a colour with no height |
| `Plan` (dataclass) | `mode, op, layers, parts, pocket=None, recess=[], pin=None, notes=[]`; `.structure = (mode, op, parts)` |
| `effective_op(mode, op, has_body) -> Optional[str]`, `pin_applies(mode, op, has_body) -> bool` | |
| `plan(mode, op, has_body, n, pin_shape="none", trim=False) -> Plan` | the parts in timeline order and the one-line notes |
| `describe(p) -> List[str]` | |
| `pin_outlines(shape, size, tile_w, tile_h, margin=1.0, cut=0.0) -> List[dict]` | `{"kind": "poly", "pts"}` or `{"kind": "circle", "c", "r"}`; raises when they do not fit |
| `grow(outline, d) -> dict`, `outline_points(outline, segments=32)`, `edge_gap(a, b) -> float` | the hole = the pin grown by the tolerance |

Versioned: `from_legacy` is the migration for nodes before 2026-10-08. The version signal is the add-in's (which parameters the node has), not a number in the core.

### 1.5 `aruco_chamfer.py`: 374 lines

Purpose: the corner mark that says which way is up, by shape: "cut" (the white tile's top-left corner cut at 45 degrees, legs 0.7 module; a ChArUco board's top-left BLACK square's outer corner, legs 2 modules), "triangle" (a black triangle, legs 0.6 module, in the quiet zone's corner) or "none". Never a marker's black square (the study: a 0.5-module black cut costs 2.5 points, 1.0 module costs 32). Decides which form a tag can have, what it gets when asked for one it cannot have, and the polygons (the cut, the cut tool, the triangle, the outline) in the pattern frame.

Dependencies: stdlib (`math`).

| Public | Signature |
|---|---|
| constants | `KINDS=("none","tile_cut","black_cut","triangle")`, `CHOICES=("none","cut","triangle")`, `CHOICE_LABELS`, `CUT_LABEL_CHARUCO`, `INSTEAD`, `TILE_LEG=0.7`, `TILE_LEG_MAX=1.0`, `TILE_LEG_MIN=0.5`, `TILE_ROOM=1.0`, `CHARUCO_LEG=2.0`, `CHARUCO_LEG_SQUARE=0.25`, `TRI_LEG=0.6`, `TRI_CLEAR=0.9` (modules) |
| `charuco_black_tl(rows, legacy) -> bool`, `charuco_cut(layout, rows=1, legacy=False) -> bool` | |
| `Mark` (dataclass) | `kind, leg, module, cut, tool, solid, outline, corner, black, clear, note, instead`; `.is_cut`, `.to_dict(nd=4)` |
| `area2`, `corner_triangle(c, leg)`, `corner_tool(c, leg, over)`, `cut_rect(rect, leg)`, `is_top_left(rect, c, tol)` | geometry helpers |
| `valid_marks(layout, mode, op, rows=1, legacy=False) -> List[str]` | what this tag can have |
| `choice_of(settings) -> str` | reads `"corner_mark"`, else the old checkbox `"chamfer": true` = `"cut"` |
| `choose(want, valid) -> (form, note)` | the other form when the asked one cannot be had |
| `plan_mark(layout, mode, op, extent_mm, module_mm, quiet_modules=1.0, tile_mm=None, square_mm=0.0, marker_mm=0.0, rows=1, legacy=False, want="cut") -> Mark` | THE rule |
| `mark_for_spec(spec, mode, op, tile_mm=None, want="cut") -> Mark` | `plan_mark` for a `TagSpec` |
| `pin_inset(cut, margin, half=0.0) -> float` | how far a pin moves in from a cut corner |
| `from_dict(d) -> Optional[Mark]`, `same(a, b, tol=1e-3) -> bool` | the record |

Versioned: the checkbox migration in `choice_of` (no number). The leg sizes are the study's and are not versioned: a tag's mark is stored in its record (`Mark.to_dict`) and a copy is rebuilt from the record, not re-planned.

### 1.6 `aruco_autosize.py`: 1,862 lines

Purpose: size first. Given a face (a w x h box, or its real outline as loops with holes) and a marker size (typed or auto), lay out as many markers as fit, centred, and say whether that is valid; the smart default (Zach's 70 % tube rule generalised, nearest 0.5 mm); the clamp for a typed size that overhangs; the ranked list of every cols x rows that fits; the dictionary that grows with the ids in use; and, for faces that are not rectangles, the largest clear rectangle by a proven branch and bound (polylabel in the box norm). Since 2026-10-14 every function takes `cells=`: the print grid (0.5 mm steps, or every cell a whole number of the printer's line width).

Dependencies: stdlib (`heapq`, `math`, `re`); `aruco_board.check_spec` (the OpenCV-validity gate); `.fiducials.ARUCO_DICTS`; `.markers` (`DEFAULT_DICTIONARY`, `DEFAULT_GRID_SEPARATION_RATIO`, `LAYOUTS`, `TagSpec`, `dictionary_bits`).

| Public | Signature |
|---|---|
| constants | `STEP_M=0.0005`, `GAP_RATIO=0.2`, `FILL=0.7`, `MIN_MODULE_M=0.0012`, `STRIP_ASPECT=3.0`, `CHARUCO_MIN_CORNERS=4`, `CAPACITIES=(50,100,250,1000)`, `FILL_CLEARANCE_M=5e-6`, `CELL_RULE=1`, `CELL_OF=("cell","marker")`, `MIN_STEP_M=1e-5`, `MAX_STEP_M=0.02`, `CLEAR_EPS_M=2e-5`, `TOUCH_M=5e-8`, `ASPECTS` |
| `cells_of(cells) -> Optional[(of, step_m, min_m)]` | the `"cells"` setting; `None` = the legacy 0.5 mm rule |
| `Layout` (dataclass) | `kind, marker_m, square_m=0.0, cols=1, rows=1, separation_m=0.0, margins_m=(0,0), ok=True, notes=[], badges=[], fill=0.0, dictionary=DEFAULT_DICTIONARY, quiet_modules=1.0`; `.n`, `.module_m`, `.quiet_m`, `.count`, `.corners`, `.extent_m`, `.tile_m`, `.label()`, `.apply(spec) -> TagSpec` |
| `layout_for_size(kind, w_m, h_m, marker_m, square_m=0.0, *, dictionary, quiet_modules=1.0, gap_ratio=GAP_RATIO, force=None, cells=None) -> Layout` | sizes in, counts out; never raises |
| `default_layout(kind, w_m, h_m, *, dictionary, quiet_modules, gap_ratio, cells) -> Layout` | the smart default |
| `clamp_to_fit(kind, w_m, h_m, marker_m, square_m=0.0, *, ...) -> Layout` | a typed size that overhangs, noted |
| `face_default(kind, w_m, h_m, *, ...) -> Layout` | a clicked face's default (single: the sticker fills the clear square, never flush) |
| `candidates(kind, w_m, h_m, *, ..., limit=8, cells=None) -> List[Layout]` | the ranked list, badged |
| `candidates_on_loops(kind, loops_m, *, ..., angles_deg=(0, 90), limit=8, cells=None) -> List[Layout]` | the same on a real outline |
| `auto_dictionary(dictionary_or_family, need, in_use_ids=()) -> str` | keep the family, grow the capacity with headroom `max(2 x total, total + 10)` |
| `largest_clear_rect(loops_m, aspect=None, angle_deg=0.0) -> Optional[dict]` | `{cx, cy, w, h, angle_deg}`, proven within `CLEAR_EPS_M` |
| `fit_on_loops(kind, loops_m, *, marker_m=None, square_m=0.0, dictionary, quiet_modules=1.0, gap_ratio, angles_deg=(0, 90), cells=None) -> (Layout, Optional[placement])` | size and place on a face with holes and notches |

`aruco_label` imports three private helpers from here: `_clean` (a loop without repeats or collinear points), `_inside` (even-odd point test), `_rect_inside` (an exact box-in-region test).

Versioned rule: `CELL_RULE` (the `"cells"` setting). See 1.10.

### 1.7 `aruco_label.py`: 3,149 lines

Purpose: the optional label. ONE content template (`#{id}`, `#{id}|{name}`, `{name}`, `{dict} #{id}`, or custom with `{id} {ids} {name} {key} {dict} {size}`), placed on the black (a marker's border rows, each marker or the first; a ChArUco board's top-left black square) or on the white (fitted into the white around the tag, or a strip the tile grows), auto-sized in a 5-pixel block font that a 0.6 mm nozzle prints, every detection rule checked, a refused label still laid out as a preview with its violations in words, and every copy re-labelled with its own id from the template's slots.

Dependencies: stdlib (`math`, `re`); `aruco_board`; `aruco_autosize` (`_clean`, `_inside`, `_rect_inside`); `.fiducials.ARUCO_DICTS`; `.markers` (`TagSpec`, `board_spec`, `split_path`); lazily `aruco_chamfer` (a tile cut re-made on a grown tile) and `aruco_slabs` (the pattern slab, the pins).

| Public | Signature |
|---|---|
| options | `PRESETS`, `CONTENTS`, `PLACES=("auto","black","white")`, `ROWS=("auto","bottom","top","both","square")`, `SIDES=("auto","below","above","left","right")`, `SCOPES=("auto","each","first")`, `POSITIONS=("auto","manual")`, `TOKENS`, `LINE_BREAK="\|"`, `SIDE_ORDER`, `SIDE_ROT` |
| rule constants (modules unless mm) | `BLACK_CAP=0.5`, `BLACK_EDGE=0.25`, `CORNER_CLEAR=0.25`, `WHITE_GAP_MIN=0.0`, `WHITE_GAP_PREF=0.25`, `POS_TOL_MM=0.01`, `WHITE_CAP=1.5`, `ONE_LINE=0.5`, `WHITE_LIMIT=4.0`, `WHITE_EDGE=0.25`, `EDGE_MIN_MM=1.0`, `KEEPOUT_MM=1.0`, `KEEPOUT=0.25`, `SQUARE_CAP=0.22`, `SQUARE_EDGE=0.1`, `SQUARE_CORNER=0.35`, `SQUARE_CORNER_HARD=0.3`, `MAX_LINES=3`, `NOZZLE_MM=0.6`, `STROKE_NOZZLE=1.0`, `GLYPH_ROWS=5`, `LINE_GAP_PX=2`, `CAP_STEP_MM=0.1`, `REACH=3.0`, `SIDE_SLACK=0.8`, `FAR_STEPS=64`, `SOLID_PAD_MM=0.1` |
| `Rule` (frozen dataclass), `RULES = {1: ..., 2: ...}`, `RULE = 2`, `RULE_NOTE`, `rule_of(settings) -> Rule` | the clearance rule a label was made under |
| the font | `GLYPHS` (digits, A-Z, `# - _ : . / + = ( ) ? …`), `normalize(text) -> (text, missing)`, `Metrics(cap, stroke)`, `min_stroke(nozzle=0.6, stroke=0.0)`, `stroke_for(cap, nozzle, stroke)` (= cap / 5), `metrics(cap, nozzle, stroke)`, `min_cap(nozzle, stroke)` (3.0 mm at 0.6), `glyph_width`, `line_width`, `block_size(lines, M) -> (w, h)` |
| boxes | `Box(cx, cy, length, width, angle=0.0)` with `.corners()`, `.bounds()`, `.to_list(nd)`; `glyph_rects(ch)`, `glyph_boxes`, `line_boxes`, `block_boxes(lines, M, centre, rot) -> List[Box]`, `ink_rect(boxes)` |
| content | `dict_short`, `part_name(path, depth=2)`, `name_variants`, `instance_name(inst)`, `name_cuts(name)`, `text_cuts(text)`, `template_lines`, `part_template(template, part)`, `resolve_text(template, spec, *, marker_id=None, name="", key="", sizing=False) -> str`, `unknown_tokens`, `wraps(text, max_lines=1) -> List[List[str]]` |
| `LabelSettings` (dataclass) | `on=False, content="id", text="", place="auto", row="auto", side="auto", scope="auto", cap_mm=0.0, nozzle_mm=0.6, stroke_mm=0.0, offset_x_mm=0.0, offset_y_mm=0.0, build_anyway=False, position="auto", x_mm=0.0, y_mm=0.0, rule=2`; `.manual`, `.nudged`, `.template()`, `.black_row(layout)`, `.to_dict()`, `from_dict(d, notes=None)` (tolerant; `"scope": "square"` from phase 1 becomes `row`) |
| `positions(layout) -> [(place, row or side)]` | |
| results | `Slot(where, rect, rot=0, cap=0.0, lines=1, marker=None, bound=None, part="all", square=None, shift=(0,0))`, `Part(slot, text, lines, cap, stroke, min_feature, rect, boxes, short="", full="")`, `Label(kind="none", role="", side="", settings, slots, parts, white=None, strip=None, notes, mode="", slab=None, violations, forced=False, preview=None, reason="")` with `.ok`, `.shown`, `.cap`, `.stroke`, `.min_feature`, `.boxes()`, `.polygons()`, `.texts()`, `.solids(slab=None, mode=None, pad=0.1) -> {"op", "lo", "hi", "boxes"}`, `.footprint_rects()`, `.to_dict(nd)`; `from_dict(d) -> Label`; `same(a, b, tol=1e-3)` |
| the tag in mm | `sticker_rect(spec)`, `quiet_ring(spec)`, `keepout_rect(spec, gap=0.0)`, `clear_zones(spec, rule=2) -> {"hard", "preferred"}`, `marker_squares(spec)`, `charuco_square(spec)`, `charuco_corners_mm(spec)` |
| keep-outs | `mark_keepouts(mark)`, `pin_keepouts(outlines, centre, segments=24)`, `mark_on_tile(spec, mode, op, tile) -> Mark`, `rect_loop`, `loops_to_pattern(loops_m, cx, cy, angle_deg, turn_deg)` |
| 2D helpers | `rect_poly`, `grow_rect`, `poly_dist`, `pt_poly_dist`, `rect_point_dist` |
| `label_violations(spec, lab, *, loops=(), bounds=(), keep=(), strip=False) -> List[str]` | the rules a laid-out label breaks, in words, with how much |
| `pattern_slab(mode, numbers, has_body=True) -> (lo, hi)` | the slab the label is built in |
| `white_room(mode, op, has_body, tile_bigger=False) -> dict` | where the white comes from per mode |
| `plan_label(spec, settings=None, *, mode="both", op="new", name="", key="", region=None, grow=False, bounds=None, tile=None, mark=None, pins=None, keepouts=(), slab=None) -> Label` | THE entry point; never raises |
| `position_of(label) -> Optional[(u, v)]` | where a label is (the dialog's Offset X / Y under Auto) |
| `relabel(label, spec, *, name="", key="") -> Label`, `label_for_instance(label, inst)`, `copy_regions(label, spec, *, name="", key="") -> dict`, `RECORD_FIELD="label"` | a copy's own text in the template's slots |
| words | `where_words(lab)`, `describe(label, mode="both") -> [(level, text)]`, `check_label(spec, label, tol=1e-6) -> List[str]` (the safety check from the spec alone) |

Versioned rule: `RULE` / `RULES` (the `"rule"` field of `LabelSettings`). See 1.10. Also kept for old records: `offset_x_mm` / `offset_y_mm` (a nudge after the automatic placement, before 2026-10-13) and `"scope": "square"` (phase 1).

### 1.8 `aruco_trim.py`: 470 lines

Purpose: Trim excess. The tag's outline (the white it owns plus the label, pins, corner mark and a margin), the column the node keeps when the body under the tag is cut back to it along the tag's x / y / both, the sides it cuts, and the safety rules that refuse (the face is not a rectangle in the tag's axes; a hole removed or cut through; the part loses much more volume than the face loses area; nothing measured). "Cut anyway" overrides every one.

Dependencies: stdlib (`math`).

| Public | Signature |
|---|---|
| constants | `RULE=1`, `AXES=("x","y","both")`, `CHOICES=("off",)+AXES`, `MARGIN_MAX_MM=50`, `TOL_MM=0.01`, `REACH_NOTE_MM=0.05`, `RECT_FILL=0.98`, `EXTRA_SHARE=0.15`, `PAD_MIN_MM=10`, `SIDES` |
| `trim_of(raw) -> Optional[dict]` | the stored setting; anything but `{"rule": 1, "axes": x\|y\|both, ...}` reads as off |
| `setting(axes, margin_mm=0.0, force=False) -> Optional[dict]`, `cut_axes(axes) -> (bool, bool)` | |
| rects | `box_of`, `union`, `grow`, `inside`, `disjoint`, `outline(base, extras=(), margin=0.0) -> Rect` |
| polygons | `area`, `clip(poly, r)` (Sutherland-Hodgman), `split_loops(loops) -> (outer, holes)`, `face_area`, `kept_area` |
| `pad_for(body, z=None)`, `keep_and_cut(axes, out, body, pad=None) -> (keep, {side: mm})`, `noop_keep(body, pad=None)` | the kept column |
| `TrimPlan` (dataclass) | `axes, margin, outline, body, keep, pad, cut={}, refusals=[], notes=[], forced=False, face=None, face_share=None, body_share=None, removed_mm3=None, body_mm3=None, holes=(0,0), z=None`; `.active`, `.refused`, `.cuts`, `.column()`, `.regions()`, `.size_after()` |
| `plan_trim(axes, out, body, face_loops=None, *, margin=0.0, force=False, volumes=None, z=None, need_face=True) -> TrimPlan` | THE rule; the caller supplies the face loops and the measured volumes |
| `failed(axes, body, why, force=False) -> TrimPlan`, `summary(p, body_name="the part") -> str` | |

Versioned rule: `RULE`. See 1.10.

### 1.9 `aruco_numbering.py`: 1,292 lines

Purpose: ArUco IDs. One table of every tag instance in the design (linked designs included), numbered so no two visible instances print the same marker per dictionary FAMILY (4X4_50 is the first 50 of 4X4_1000), boards as contiguous blocks, overrides kept exactly (collisions flagged, never moved), and printed ids that never move: the id LEDGER (every copy ever numbered, every id ever printed), copies matched by stamp chain, then place (0.5 mm), then path. Plus the node's stored state, the decoder that reads a built pattern back to an id, and the pure halves of "rebuild after an upstream change" (digests, diffs, the auto-rebuild decision).

Dependencies: stdlib (`json`, `math`, `re`, `hashlib`); `.fiducials.ARUCO_DICTS`; `.markers` (`KEY_SEP`, `UNIT_TO_M`, `OccurrenceRef`, `OverrideRecord`, `Resolution`, `TagDef`, `TagSpec`, `resolve`, `slot_key`, `split_path`); lazily `aruco_board` and `aruco_dict`.

| Public | Signature |
|---|---|
| constants | `SCHEMA="bam_aruco_ids/1"`, `SOURCES`, `BASES`, `LEDGER_SCHEMA="bam_aruco_ids_ledger/1"`, `LEDGER_STATES`, `PLACE_TOL_M=0.0005`, `ROOT_CHAIN`, `INPUTS_SCHEMA=1`, `VOLATILE_FUSION`, `AUTO_MODES=("all","mine","off")`, `AUTO_BURST=(3, 30.0)` |
| helpers | `family(dictionary)`, `capacity(dictionary)`, `natural_key(s)`, `instance_name(path, key)`, `split_name(name)`, `parse_id(text) -> Optional[int]` (blank = auto, words raise a readable `ValueError`) |
| `IdsRow` (dataclass) | `name, path, key, component, layout, dictionary, count, modelled, base, final=0, override=None, source="auto", hidden=False, linked=False, fixed=False, note="", previous=None, conflict="", error="", owner="", world=None, uid="", basis="", entry=None`; `.at`, `.family`, `.ids`, `.needs_part`, `.label()`, `.to_dict()` |
| `IdsPlan` (dataclass) | `rows, warnings, errors, stale_overrides, resolution=None, ledger=None, matches`; `.ok`, `.row(name)`, `.visible()`, `.duplicates()`, `.parts()`, `.retired()`, `.overrides()`, `.auto_state()`, `.export_records()`, `.summary()`, `.to_dict()` |
| the ledger | `chain_key(segments)`, `copy_uid(path, key, chains)`, `LedgerEntry(uid, name, family, count=1, id=None, state="active", at=None, born=0, seen=0)` with `.block()`, `.to_dict()`, `from_dict`; `Ledger(seq=0, entries, printed, updated="")` with `.mark_printed`, `.held(fam)`, `.retired(fam)`, `.summary()`, `.to_dict()`, `.to_json()`, `from_any(data)`; `match_ledger(rows, ledger, tol) -> {name: index}`; `ledger_after(plan, chains=None, when="") -> Ledger`; `seed_ledger(state, rows=()) -> Ledger`; `stamp_losers(items) -> set` |
| `plan_ids(tags, occurrences, overrides=None, previous=None, inherited=(), root_component="", design_units="cm", fixed=None, ledger=None, chains=None, born=None) -> IdsPlan` | THE planner, pure; `ledger=None` is the 2026-10-09 numbering |
| `plan_stable(tags, occurrences, ledger=None, state=None, chains=None, born=None, **kw) -> IdsPlan` | what ArUco IDs runs; seeds a ledger from an old node's state |
| `dependency_copies(components, occurrences, hosts) -> {component: path}` | |
| the node's state | `node_state(plan, extra=None) -> dict`, `read_state(text_or_dict) -> dict`, `state_records(state, base=None) -> List[OverrideRecord]` |
| reading geometry | `module_samples(spec)`, `expected_grid(dictionary, marker_id)`, `identify(dictionary, grid) -> Optional[int]`, `decode(spec, is_black) -> {id: read id}` |
| upstream changes | `record_digest(records)`, `body_changes(old, new)`, `inputs_diff(old, new)`, `plan_drift(state, plan)`, `inputs_digest(inputs, plan_final=None)`, `auto_decision(mode, doc_is_mine, undoing, digest, done=(), failed=None, recent=(), now=0.0) -> (action, why)` |

The seven numbering rules (root tags keep what they print; overrides exact; own ledger id; the last OK's id by path; what the geometry prints, oldest copy first; the lowest never-printed block; then the block retired longest ago, then a hidden copy's, else a refusal) are in the module docstring and are mutation-tested (`tools/mutate_aruco_ids.py`, 17 mutations).

Versioned: schemas only (`bam_aruco_ids/1`, `bam_aruco_ids_ledger/1`, `INPUTS_SCHEMA`). The ledger-less plan is the older numbering and still runs when `ledger=None`.

### 1.10 Versioned rules: the table

Zach's rule: existing tags never change on their own. Every rule change is versioned in the tag's stored settings and pinned by a golden. A Fusion adapter must read these keys and call the core with the same version to rebuild today's tags identically.

| Rule | Module and constant | Stored where | Versions | Pinned by |
|---|---|---|---|---|
| Label clearance | `aruco_label.RULES`, `RULE = 2` | `settings["label"]["rule"]`; a stored label WITHOUT it is rule 1 | 1 (before 2026-10-13): one line, 2 modules from the black (quiet ring + 1 module), within `REACH` only, the biggest text's side, square margins, `exact=False`. 2: the quiet ring is the hard line (`gap_min 0`), 0.25 module preferred, the far search as far as the face goes, Side auto keeps an earlier side at >= 80 % of the biggest, crow-flies measure with `POS_TOL_MM`. Any label setting change makes it 2. | `tests/test_aruco_label_rule1.py`: 36 labels laid out by the code of 8473e14 (`tests/fixtures/aruco_label_rule1_golden.json`, made by `tools/make_label_rule1_golden.py`) come out identical to 1e-6 mm; the same settings under rule 2 move |
| Cell multiple (the size grid) | `aruco_autosize.CELL_RULE = 1`, `cells_of` | `settings["cells"] = {"rule": 1, "of": "cell" \| "marker", "mm", "min_mm"}`; a tag WITHOUT it (before 2026-10-14) is the legacy rule, and `default_settings()` never holds it | legacy (`cells=None`): marker and checker in 0.5 mm steps, typed sizes as typed, every helper the old expression bit for bit. `"marker", m`: the same rule on step m. `"cell", m`: module = k m, marker = n k m, ChArUco square = j m with whole white around the marker, grid gap rounded UP to whole m, a typed size snapped DOWN (noted), a module under `min_mm` noted. | `tests/test_aruco_cells_legacy.py`: 511 sizings (222 `default_layout`, 114 `face_default`, 60 `fit_on_loops`, 45 `layout_for_size`, 42 `clamp_to_fit`, 21 `candidates`, 7 `candidates_on_loops`) and 12 `aruco_feature.evaluate()` results made by the code of 196454c (`tests/fixtures/aruco_cells_legacy_golden.json`, `tools/make_cells_legacy_golden.py`) recompute EXACTLY (floats too); the same under `{"of": "marker", "mm": 0.5}` |
| Origin on a rectangular board | `aruco_origin.ORIGIN_RULE = 2`, `effective(..., rule=)` | `settings["origin_v"]`; a node WITHOUT it was made before 2026-10-09 | none (before): 90 / 270 degrees on a rectangular board refused, kept as laid out with a note. 2: 90 / 270 lay the board on its side (cols / rows swapped, OpenCV's own board). | `tests/test_aruco_frame.py` (origin section: "the rule a node made before 2026-10-09 keeps"); `tests/test_aruco_extrude_dialog.py` (EX-MIGRATE-3). Unit tests, no golden of real records. |
| Trim excess | `aruco_trim.RULE = 1`, `trim_of` | `settings["trim"] = {"rule": 1, "axes", "margin_mm", "force"}`; missing, `None`, another rule, unknown axes or junk = off; never in `default_settings()` | 1 (2026-10-16): the only rule. Off = `plan()` without `trim=` and an `evaluate()` identical to before. | `tests/test_aruco_trim_legacy.py`: 26 `evaluate()` results, what their nodes store, 288 `aruco_slabs.plan` results and `default_settings()` made by the code of 5cf71bd (`tests/fixtures/aruco_trim_legacy_golden.json`, `tools/make_trim_legacy_golden.py`) compare EXACTLY, also with a `"trim"` that reads as off |
| Heights (Offset / Height) | `aruco_slabs.from_legacy(mode, height, thickness, above)` | the node's parameters: a node made before 2026-10-08 has height / thickness / above | old parameters mapped to Offset / Height pairs with the same geometry; migrated on the next edit | `tests/test_aruco_slabs.py` (EX-MIGRATE-1); in Fusion `live_test` (EX-MIGRATE-4) |
| Corner mark | `aruco_chamfer.choice_of` | `settings["corner_mark"]`; the old checkbox `settings["chamfer"]: true` reads as `"cut"` | the checkbox made exactly what "cut" makes | `tests/test_aruco_chamfer.py` (EX-MARK-1); `tests/test_aruco_extrude_dialog.py` (EX-MIGRATE-3) |
| Label position | `aruco_label.LabelSettings` | `position` `"auto"` / `"manual"` + `x_mm`, `y_mm`; older records carry `offset_x_mm` / `offset_y_mm` (a nudge after the automatic placement) and are still honoured | before 2026-10-13: a relative nudge. After: an absolute spot. | `tests/test_aruco_label_position.py`, the rule-1 golden (it holds Zach's old Offset record) |
| Label row `"square"` | `aruco_label.LabelSettings.from_dict` | phase 1 stored `"scope": "square"`; read as `row = "square"` | | `tests/test_aruco_label.py` |
| Numbering | `aruco_numbering.plan_ids(ledger=None)` vs `plan_stable` | the design's root attribute `idsLedger` (JSON, `bam_aruco_ids_ledger/1`) and the node's `ids` state (`bam_aruco_ids/1`); a node from before the ledger is seeded from its `final` / `auto` / `overrides` | 2026-10-09: the lowest free id. 2026-10-10: the ledger (a printed id is never handed to another copy while the dictionary has unused ids). | `tests/test_aruco_ids_stability.py` (G0.7), `tests/test_aruco_numbering.py` (G0.1-G0.6), `tests/test_aruco_ids_ledger_fusion.py`; `tools/mutate_aruco_ids.py` (17 mutations) |
| Joint Origin layout | add-in only (`ArucoMarkers/aruco_feature.py`) | `settings["jo_v"]`: 1 = the Joint Origin before the node on its target; 2 = after the node on a frame sketch | not in the core | `tests/test_aruco_edit_roundtrip.py`, `tests/test_aruco_jo_one_per_tag.py` |
| Schemas | `aruco_dict.TABLE_SCHEMA`, `markers.SCHEMA = "bam_aruco/1"`, `aruco_numbering.SCHEMA`, `LEDGER_SCHEMA`, `INPUTS_SCHEMA`; add-in: `bam_aruco_settings/1`, `bam_aruco_presets/1`, `bam_aruco_preset_library/1` | the files / attributes | all at /1 | the suites that read them |

Not versioned (worth knowing): the label FONT changed on 2026-10-10 from a stroke font to the pixel font. A label record made between 2026-10-09 and 2026-10-10 (if any exists) would re-lay out differently; the rule-1 golden was made after the font change (8473e14), so it does not cover that. The corner mark's leg sizes and the slab defaults are not versioned either, but a tag stores its mark and its numbers, so recomputes do not re-derive them.

### 1.11 The core modules the ArUco core depends on

| Module | Lines | What the ArUco core takes from it | Note |
|---|---|---|---|
| `markers.py` | 1,428 | `TagSpec` (metres: `dictionary, marker_id, marker_length_m, quiet_modules, depth_m, layout, raise_m, recess_m, grow_m, rows, cols, separation_m, square_length_m, legacy`; `.bits`, `.module_m`, `.marker_count`, `.ids`, `.extent_m`, `.tile_size_m`, `.to_dict()`, `from_dict(data, warn, where)`), `TagDef`, `OverrideRecord`, `OccurrenceRef`, `TagInstance`, `Resolution`, `resolve()`, `plan_serials()`, `board_spec()`, `detector_frame()`, `cell_boxes()`, `split_path`, `slot_key`, `KEY_SEP="\|"`, `PATH_SEP="+"`, `UNIT_TO_M`, `DEFAULT_DICTIONARY="DICT_4X4_50"`, `DEFAULT_GRID_SEPARATION_RATIO=0.2`, `LAYOUTS`, `dictionary_bits` | The CAD Exporter's tag model: per-copy overrides, world poses, the export records. Also holds OLDER sizing helpers superseded by `aruco_autosize`: `suggest()` (a dictionary and a size for a camera range), `fit_square`, `fit_board`, `largest_rect` (a sampled largest rectangle; `aruco_autosize.largest_clear_rect` is the proven one). |
| `fiducials.py` | 617 | `ARUCO_DICTS` (the 21 names and capacities), `board_for_tube()` (Zach's tube rule: separation = margin = (tube - marker) / 2) | Also `Fiducial`, `parse_board_filename`, `validate_fiducials`, `assign_id_ranges`, `load_marker_library`, `fiducials_from_decals`: the decal-era path; `docs/aruco_marker_library.example.json` (`bam_aruco_library/1`) is its input. |
| `print_sheet.py` | 734 | `PrintItem`, `SheetSettings` (`id_mark "border"\|"off"`, `top_label`, `orient_mark "triangle"\|"off"`), `layout_sheet`, `layout_summary`, `render_pdf`, `identity_label`, `page_size_mm` | The true-size PDF sheet (hand-written PDF 1.4, never scales a marker, ruler bars). Draws the border "#id" and the grey triangle (legs 0.6 module). |
| `print_beds.py` | 2,289 | the 3MF / STL / bed packing for the PrusaSlicer export | Not read in detail here; it is Fusion-free and tested by `tests/test_print_beds*.py` (not ArUco-named). |

What the core does NOT do: it has no single "plan a tag" function. The orchestration that turns a face plus settings into a tag (fit the size, apply the Origin, plan the mark, plan the label, plan the pins, plan the trim, plan the slabs, write the record) is `ArucoMarkers/aruco_feature.evaluate()`, which imports `adsk`. Two goldens (12 and 26 `evaluate()` results) therefore run the add-in on a stand-in `adsk`.

## 2. The test suites

All 43 suites are plain scripts: `python tests/<file>.py` from REF's root; each prints `N passed, M failed` and exits non-zero on a failure. No pytest, no runner. "Stand-in adsk" means the test builds a fake `adsk` module (`types.ModuleType`, or `tests/aruco_ui_stubs.py`, or `tests/aruco_trim_fixtures.py`) and runs the add-in's own code on it: no Fusion, no bridge. None of the 43 suites uses `tools/aruco_bridge.py`; the in-Fusion checks are the bridge scenarios listed in the spec (section 3), not test files.

Columns: "Fusion" = none (only `bam_cad_core`), add-in pure (an `ArucoMarkers` module that never imports `adsk`), stand-in (a fake `adsk`). "Today" = the result of running it here with Python 3.11.5 and a scratch home.

### 2.1 Suites that need only the core

| Suite | Lines | What it checks | Fusion | Run | Goldens / fixtures | Today |
|---|---|---|---|---|---|---|
| `test_aruco_autosize.py` | 936 | P1 defaults and P3 ranked lists against the proposal's tables (five faces); typed sizes kept or clamped with a note; `force`; `Layout.apply`; `auto_dictionary`; 780 random boxes (every default fits); faces with holes: ten non-box faces x every layout, the tile inside the face, the same default under 90 / 180 / 270 turns, equal to a 0.1 mm brute-force raster; `largest_clear_rect` | none | `python tests/test_aruco_autosize.py` (the README says numpy; it imports none) | expected numbers inline from `docs/proposal_aruco_autosize.md` sections 4 and 6 | 110 passed, 16 s |
| `test_aruco_board.py` | 366 | counts, ids, extents, object points and chessboard corners pinned from cv2 5.0.0; bitmaps pixel for pixel; refusals as cv2 asserts; PNG (pHYs) and SVG; boards on print sheets | none (imports helpers from `test_aruco_output.py`) | `python tests/test_aruco_board.py` | pinned values inline | 51 passed |
| `test_aruco_cells.py` | 274 | the cell rule: the spec's example, Auto = the largest k whose sticker fits (brute force over 300 random faces, 6 multiples, 4 dictionaries, 3 quiet zones), boards, ChArUco whole white (odd n too), grid gaps, `"marker"` cells, the minimum, faces with holes | none | `python tests/test_aruco_cells.py` | none | 40 passed |
| `test_aruco_cells_legacy.py` | 145 | GOLDEN: a tag without `"cells"` never changes: 511 sizings + 12 `evaluate()` results of 196454c recompute exactly; `"marker", 0.5` is the same rule | stand-in for the 12 `evaluate()` cases (`tools/make_cells_legacy_golden.py` installs a fake `adsk` and imports `aruco_feature`); the 511 sizings are core only | `python tests/test_aruco_cells_legacy.py` (sets `USERPROFILE` to a temp dir) | `tests/fixtures/aruco_cells_legacy_golden.json` (271 KB) | 22 passed, 7 s |
| `test_aruco_chamfer.py` | 488 | which mark each layout x mode x op gets; the choice (None / Cut / Triangle; the old checkbox = cut); the mark at OpenCV's corner 0 / the board origin for every Origin turn; legs in modules, 45 degree cut, the tool; clearance from every black cell; ChArUco only the black square's outer corner; tiles bigger than the sticker; too narrow a border = no mark with a note; pins clear of a cut corner | none | `python tests/test_aruco_chamfer.py` | none | 579 passed |
| `test_aruco_label.py` | 1,179 | the font (every glyph's ink in its cell, no corner-touching pixels, strokes >= the nozzle); content tokens, per-marker and per-copy ids and names through `markers.resolve` / `plan_serials`, sizing for the widest id; on the black (band, 0.25 module of black, corner cells clear, grids each / first, the ChArUco square, the name in the top row); on the white (beyond the quiet zone, auto side and size, strips, a face with holes); corner marks and pins kept clear; a text too long (shrink, tail, cut); batch ids in two rows; the label as tall as the black; the old offsets; the safety check catches every rule broken on purpose; deterministic records; `relabel`; a 0.6 mm nozzle section | none | `python tests/test_aruco_label.py` | none | 295 passed |
| `test_aruco_label_position.py` | 334 | rule 2: the hard line and the preferred margin; Zach's GIM43 disc (auto finds a spot below, beside the hole; his own spot refused only for the hole; 1 mm right it builds); Auto position: `position_of` is auto's spot, a manual spot there is the same label, elsewhere as big as fits; old `offset_x_mm` / `offset_y_mm`; no room = three lines; copies at a manual spot; the far search | none | `python tests/test_aruco_label_position.py` | `tests/fixtures/aruco_label_gim43_disc.json` via `tests/aruco_label_fixtures.py` | 39 passed |
| `test_aruco_label_preview.py` | 263 | a refused label comes back kind "none" with a preview and its violations with how much; a nudge that breaks a rule is shown where nudged; Build anyway builds that preview, forced, copies relabel it; records keep the preview; `copy_regions` warns instead of dropping; the GIM43 disc above / 40 mm disc / on the black | none | `python tests/test_aruco_label_preview.py` | none | 29 passed |
| `test_aruco_label_rule1.py` | 130 | GOLDEN: 36 labels of 8473e14 identical under rule 1 (kind, side, every slot, part and stroke to 1e-6 mm, the grown white, the preview); the same settings under rule 2 do move | none (`tools/make_label_rule1_golden.py` is core only) | `python tests/test_aruco_label_rule1.py` | `tests/fixtures/aruco_label_rule1_golden.json` (309 KB) | 45 passed |
| `test_aruco_label_print.py` | 145 | the slicing oracle of `tools/slice_aruco_label.py` without PrusaSlicer: toolpaths made from the label's own pixels pass; a dropped glyph, a bridge, a lost counter are each caught; the meshes it slices are watertight and tile the layer | none (tools + core) | `python tests/test_aruco_label_print.py` | none | not run here |
| `test_aruco_numbering.py` | 413 | G0.1-G0.6 over abstract models of fixtures F1-F11: unique per family, contiguous blocks, inside the dictionary or a refusal naming the tag, stable, overrides set / cleared / flagged, owners; export consistency; helpers; inherited ids; fixed copies; the decoder; dependency copies; F11's hidden copies | none | `python tests/test_aruco_numbering.py [--json out.json]` | none | 153 passed |
| `test_aruco_ids_stability.py` | 772 | G0.7: every edit between two OKs on a simulated design (`Sim`): added, deleted, renamed, re-parented, hidden and shown, `:3` to `:2`, a tag deleted and made again, the node deleted, a linked part renamed; the rack replayed; a new copy never gets a printed id | none | `python tests/test_aruco_ids_stability.py [--json out.json]`; `BAM_CORE_ROOT` points it at a mutated core | none | 64 passed |
| `test_aruco_output.py` | 429 | the dictionary table (sha256, names = `ARUCO_DICTS` order), grids pinned from cv2 5.0.0, merged black rects cover exactly the black cells (9,596 markers), PNG / SVG sizes and cells, `print_sheet` layout on letter and A4 (never scales, spills pages), the PDF file | none | `python tests/test_aruco_output.py` | pinned grids inline | 109 passed |
| `test_aruco_slabs.py` | 260 | slabs from Offset / Height either sign, `snap_height`, defaults per mode, layers (surface, depth, raise, recess, the detector plane) and the `TagSpec` round trip, the plan's parts per mode, pins (outlines, grown holes, the hole deeper by the tolerance), `from_legacy`, stdlib only | none | `python tests/test_aruco_slabs.py` | none | 106 passed |
| `test_aruco_trim.py` | 297 | `trim_of` (junk reads as off), `outline`, `keep_and_cut`, the refusals (not a rectangle, holes, a boss, nothing measured), Cut anyway, the words, 400 random plates | none | `python tests/test_aruco_trim.py` | none | 52 passed |
| `test_aruco_trim_legacy.py` | 166 | GOLDEN: 26 `evaluate()` results, their nodes' stored settings, 288 `aruco_slabs.plan` results and `default_settings()` of 5cf71bd compare exactly; the same with a `"trim"` that reads as off | stand-in (`tools/make_trim_legacy_golden.py` installs a fake `adsk`, imports `aruco_feature`) | `python tests/test_aruco_trim_legacy.py` (`ARUCO_ROOT=<tree>` to test another tree) | `tests/fixtures/aruco_trim_legacy_golden.json` (228 KB) | 21 passed, 4 s |
| `test_aruco_frame.py` | 745 | `aruco_origin`: the words, Rotate's order, which boards swap, the old rule, `opencv_in_layout` == `markers.detector_frame` for every layout x Origin; the add-in's `evaluate()` x every Origin (the Joint Origin IS OpenCV's frame, the footprint unchanged, a node made before keeps its orientation, records with the removed Frame read as OpenCV's); the URDF and markers.json goldens byte for byte, every target checked by yourdfpy FK | stand-in for the `evaluate()` part; the origin math is core only | `python tests/test_aruco_frame.py` (needs numpy + yourdfpy for the URDF half: the clank venv); `--write-goldens <dir>` | `tests/golden/aruco_frame_default.urdf`, `tests/golden/aruco_frame_default_markers.json` (made by f9bba97) | not run here (needs the venv) |
| `test_aruco_frame_pnp.py` | 461 | OpenCV's own detector against every layout x Origin: `evaluate()` and `part_body("pattern")` on a stand-in, rasterised, warped into a pinhole camera 25 degrees off, detected with OpenCV's own board object, `solvePnP` against the record, the Joint Origin, the ghost's triad and `opencv_in_layout` (~0.1 mm / 0.1 deg); again with the corner mark on | stand-in; needs cv2 + numpy (else prints SKIP and exits 0) | `<opencv venv> python tests/test_aruco_frame_pnp.py` | none | not run here |

### 2.2 Suites that run the add-in on a stand-in `adsk` (no Fusion)

| Suite | Lines | What it checks | Run | Fixtures |
|---|---|---|---|---|
| `test_aruco_chamfer_bodies.py` | 448 | the Fusion side of the corner mark: a CSG stand-in `TemporaryBRepManager`; `aruco_feature.evaluate()` on a sketch profile turned 30 degrees, `part_body()` for every part, `aruco_tags._slab()` for a copy, the ghost; bodies probed at the mark for every layout x mode x four Origins x the choice; pins clear of the cut | `python tests/test_aruco_chamfer_bodies.py` | none |
| `test_aruco_disc_fit.py` | 105 | Zach's GIM43 discs pinned: 47.5 mm disc typed 28 -> 25.0, Auto 25.0; 53 mm disc with four holes 28.0 (any change of the fitter or `evaluate` fails it) | `python tests/test_aruco_disc_fit.py` | none |
| `test_aruco_edit_roundtrip.py` | 1,120 | Edit -> OK unchanged writes nothing; Auto size stays Auto (size 0 IS Auto); the dialog shows the node's state; the timeline marker's way back; the frame sketch compute (jo_v 2); the orphan Joint Origin prune; "what a structural edit does, and to whom" | `python tests/test_aruco_edit_roundtrip.py` (`ARUCO_TEST_OVERRIDE_DIR`) | `tests/fixtures/prusaslicer/` |
| `test_aruco_export_dialog.py` | 777 | the ArUco Export dialog: the type list, each type's inputs, the info line, OK's validity, Reset, what OK passes, old settings, the shared marker table's rows and ticks, the highlight lifecycle, the progress text | `python tests/test_aruco_export_dialog.py` | temp home |
| `test_aruco_extrude_dialog.py` | 763 | the ArUco Extrude dialog: build / refresh / values, Origin and Rotate, the Corner mark list, the Label group, Auto position, the edit dialog's fill, what is remembered, a hot reload | `python tests/test_aruco_extrude_dialog.py` | `tests/fixtures/prusaslicer/` |
| `test_aruco_extrude_fixes.py` | 442 | regressions of the 2026-10-09 run: a mode change keeps the black's step and the tile one body; `paint()` paints every piece; a square face never turns the tag on an edge tie; a variant part never stands in for its template | `python tests/test_aruco_extrude_fixes.py` | none |
| `test_aruco_extrude_sync.py` | 343 | compute's outcome never depends on the after-compute check (digest only, a budget, never raises); `maybe_refresh` after Undo / busy / already refreshed; `aruco_restructure.restructure_plan` over every pair of node structures | `python tests/test_aruco_extrude_sync.py` | none |
| `test_aruco_ids_dialog.py` | 386 | the ArUco IDs dialog on the shared marker table with the REAL planner over a small design (hidden plate, a linked grid, a ChArUco strip): rows, Tag button, Find, zoom, typing an id, OK, an older module's dialog | `python tests/test_aruco_ids_dialog.py` | temp home |
| `test_aruco_ids_label_warning.py` | 108 | an IDs part never drops its copy's label silently: `label_warning` -> `copy_regions["warning"]` | `python tests/test_aruco_ids_label_warning.py` | none |
| `test_aruco_ids_ledger_fusion.py` | 341 | G0.7's Fusion half on fake objects: `read_stamps`, `stamp_chains`, `record_ledger`, `read_ledger` / `write_ledger`, `plan_design`; a pasted stamp; a node from before the ledger; an unreadable ledger | `python tests/test_aruco_ids_ledger_fusion.py [--json out.json]` | none |
| `test_aruco_ids_upstream.py` | 1,121 | G8.5 offline: the pure halves (digests, diffs, drift, `auto_decision`), the control flow on fake Fusion objects (schedule / warn, never an error; once per digest; 3 in 30 s; a failed rebuild taken back), `inputs_of`, and the mutation (the 2026-10-10 compute errors) | `python tests/test_aruco_ids_upstream.py [--module-dir DIR] [--json out.json]` | none |
| `test_aruco_jo_one_per_tag.py` | 1,058 | ONE Joint Origin per tag through a 12-edit run on a stand-in design (a delete that does not happen, an exception after the new one exists, an old one not found) | `python tests/test_aruco_jo_one_per_tag.py` (`ARUCO_TEST_OVERRIDE_DIR`) | `tests/fixtures/prusaslicer/` |
| `test_aruco_label_bodies.py` | 628 | the label as geometry (CSG stand-in): white text cut out of the black, black text joined, White only the other way, a strip that grows the tile and moves the cut and pins; `check_label` everywhere; the ghost's guides; always shown, built only with Build anyway, the node warning | `python tests/test_aruco_label_bodies.py` | none |
| `test_aruco_marker_table.py` | 413 | the shared marker table: names = `aruco_numbering.instance_name`, `natural_key`, rows from a spec, the viewport pick, the double-click timing, the zoom camera, the navigation state machine (the module guards its `adsk` import: the pure half runs as is) | `python tests/test_aruco_marker_table.py` | none |
| `test_aruco_presets_dialog.py` | 811 | print presets and the cell multiple in the dialog: Default IS the old defaults, the Aruco 0.6 preset puts every cell on 0.68 mm lines, Save as / Update / Delete / Import in the list, Cells by hand, hot reloads of older dialogs | `python tests/test_aruco_presets_dialog.py` | `tests/fixtures/prusaslicer/`, temp home |
| `test_aruco_restructure_sim.py` | 459 | `aruco_restructure.restructure` on a stand-in timeline for every pair of node structures x 2 layouts x sketch / none: the same node, roles in order, combines where they should be, nothing deleted while rolled back, a failure at each step leaves it grouped | `python tests/test_aruco_restructure_sim.py` (`ARUCO_TEST_OVERRIDE_DIR`) | temp home |
| `test_aruco_trim_feature.py` | 561 | Trim excess in the node: the plan's last part, `evaluate()` trims to the outline along the tag's axes (Origin turn too), refuses without raising, the kept column, the intersect, compute, the edit's routes (pins `JO_AFTER` / `RESTRUCTURE_IN_PLACE` to False for its stand-in) | `python tests/test_aruco_trim_feature.py` | `tests/aruco_trim_fixtures.py` (a 60 x 40 mm sketch area on an 80 x 50 x 5 mm plate) |
| `test_aruco_trim_dialog.py` | 410 | Trim excess in the dialog: rows under Advanced, what a tag stores (nothing when Off), OK blocked while refused, Cut anyway, the ghost, Reset, never remembered, presets leave it alone, hot reload | `python tests/test_aruco_trim_dialog.py` (`ARUCO_ROOT`) | `tests/aruco_trim_fixtures.py` |
| `test_aruco_arrow_typing.py` | 325 | typing a value at a canvas arrow (two switches in `aruco_ui_config`): the hit test, the expression handling, OFF = unchanged, a typed arrow value == the dialog field | `python tests/test_aruco_arrow_typing.py` | `tests/aruco_ui_stubs.py`, prusaslicer fixture |
| `test_aruco_refresh_hook.py` | 282 | the UI v2 hook in `refresh()`: hooks None = today's dialog exactly; build resets hooks; before / after translation; a reloaded v2 module; a failing hook is logged | `python tests/test_aruco_refresh_hook.py` | `tests/aruco_ui_stubs.py` |
| `test_aruco_ui_v2.py` | 659 | the v2 dialog: tabs and rows, translations to today's inputs, per-line validation (Size, ID, a snapped height, a refused label, Min cell, Trim), the Size arrow and write-back, reload survival | `python tests/test_aruco_ui_v2.py` | `tests/aruco_ui_stubs.py` |
| `test_aruco_preset_library.py` | 372 | the Print Presets library window: collections and SVG cards, Select / New / Duplicate / Edit / Delete / Import, the recent list, the window's messages to a real v2 dialog; `node --check` on `library.js` / `bam_channel.js` when node is there | `python tests/test_aruco_preset_library.py` | `tests/aruco_ui_stubs.py`, prusaslicer fixture |
| `test_aruco_collect.py` | 213 | the CAD Exporter's `bam_fusion_export._collect_aruco` on fake objects, then `markers.resolve()` reads the payload (uses `test_fusion_export_v3.stub_adsk`) | `python tests/test_aruco_collect.py` | none |

### 2.3 Suites of Fusion-free add-in modules

| Suite | Lines | What it checks | Run | Fixtures | Today |
|---|---|---|---|---|---|
| `test_aruco_settings.py` | 318 | `ArucoMarkers/aruco_settings.py`: the file's location, missing / corrupt files, remember and recall (global and per design), merge, pruning, finding PrusaSlicer | `python tests/test_aruco_settings.py` | temp home | 61 passed |
| `test_aruco_presets.py` | 257 | `aruco_presets` (the store: built-ins, save as / update / delete, last, a broken file, Import, Min cell) and `aruco_prusa` (profiles read from the fixture: 0.6 / 0.68 / 0.32 / 0.2 mm, the vendor chain) | `python tests/test_aruco_presets.py` | `tests/fixtures/prusaslicer/`, temp home | 62 passed |

### 2.4 Helpers and fixtures

| File | Lines | Role |
|---|---|---|
| `tests/aruco_label_fixtures.py` | 67 | loads `tests/fixtures/aruco_label_gim43_disc.json` (Zach's GIM43 disc, measured read-only 2026-10-13: an r 26.5 mm disc 2.09 mm off the marker's centre, four r 1.425 mm holes; loops as circles drawn AROUND holes and INSIDE the outer edge) into a `TagSpec`, a region in mm and the label settings |
| `tests/aruco_trim_fixtures.py` | 412 | a stand-in `adsk`, the dialog's command inputs, and a plate whose face loops, extents and volumes replace Fusion's B-Rep reads |
| `tests/aruco_ui_stubs.py` | 629 | a stand-in `adsk` for the dialog tests of 2026-10-16: tabs, button rows, icon dropdowns, expressions with units, a viewport, mouse events, palettes |
| `tests/fixtures/aruco_cells_legacy_golden.json` | 271 KB | the cell-rule golden (511 + 12), code 196454c |
| `tests/fixtures/aruco_label_rule1_golden.json` | 309 KB | the label rule-1 golden (36), code 8473e14 |
| `tests/fixtures/aruco_trim_legacy_golden.json` | 228 KB | the trim golden (26 + 288 + defaults), code 5cf71bd |
| `tests/fixtures/aruco_label_gim43_disc.json` | 2 KB | Zach's disc |
| `tests/fixtures/prusaslicer/print/*.ini` | | his two Aruco print presets verbatim plus the vendor sections they inherit (`BAM_ARUCO_PRUSASLICER_DIR` points the add-in at them) |
| `tests/golden/aruco_frame_default.urdf`, `..._markers.json` | | the URDF / markers.json goldens of f9bba97 |
| `tools/make_cells_legacy_golden.py`, `tools/make_label_rule1_golden.py`, `tools/make_trim_legacy_golden.py` | 265 / 178 / 257 | the golden makers; the cells and trim ones install a stand-in `adsk` |
| `tools/mutate_aruco_ids.py`, `tools/mutate_aruco_label.py` | 157 / 185 | mutation tests: break each rule on purpose in a temp copy, the suite must go red |

Not run here: `test_aruco_frame` (needs numpy + yourdfpy), `test_aruco_frame_pnp` (needs cv2), `test_aruco_label_print`, and the 23 stand-in suites. The commit log at c8216ff says all 44 suites were green on 2026-10-16.

## 3. The spec: `docs/aruco_spec.json`

Hand-maintained, updated 2026-10-16. `tools/aruco_spec_status.py` runs the offline tests, reads the recorded Fusion result files and renders it to `reports/aruco/spec.html`. 9 areas, 71 features, 290 tests. Every test with its `checks`, `how` and `pass` is in `docs/inventory/spec_tests.md`.

Test kinds: 146 offline-unit, 23 offline-opencv, 101 fusion-bridge, 12 fusion-dialog, 2 fusion-readonly, 6 manual. Feature statuses: 63 built, 4 built-offline-only (EX-PRESETS, EX-CELLS, JO-ORPHAN, SAFE-PACING), 3 built-switched-off (EX-SYNC, EX-RESTRUCTURE, JO-AFTER), 1 proposed (PUB-README). 21 features declare a gap. Test statuses PASS / FAIL / NOT RUN / STALE come from the rendered report, not the JSON.

Note: the spec's switch table expects `RESTRUCTURE_IN_PLACE = False`, `JO_AFTER = False`, `AUTO_REFRESH = "mine"`, `JO_UPDATE_IN_PLACE = False`. At c8216ff the files already say `True`, `True`, `"all"`, `True` (Zach asked for them on 2026-10-16); the three "built-switched-off" statuses are stale.

### 3.1 The bars: what success looks like

| Bar | Zach's words | Measured by | Tests |
|---|---|---|---|
| Truthful tags you can print | "I cannot use a decal." | OpenCV reads every tag's id off the add-in's own bodies and the exported print files; the ink equals cv2's `generateImage` cell for cell | EX-LAYOUT-6, EX-ORIGIN-4, EXP-CHECK-1, E2E.2 |
| Every copy unique, two clicks | "all the ArUco markers basically need to be unique" | open ArUco IDs, OK: no two visible copies print the same marker, read from the built geometry and by OpenCV from renders | E2E.1, E2E.2, G2.1 |
| Printed ids never move | "avoid having to like reprint things" | every edit keeps every printed id; a new copy never gets an id another copy printed | G0.7, IDS-LEDGER-4 |
| The frame is OpenCV's, exactly | "I always want the frame to match perfectly OpenCV" | the Joint Origin is OpenCV's frame of the tag as built (0.000 mm / 0.000 deg); PnP on renders within 0.1 mm / 0.1 deg | JO-OPTICAL-1, G5.1, EX-ORIGIN-4 |
| It works like Extrude | "please use same language as extrude" | one node; Offset / Height per colour; the ghost is what OK builds; Edit -> OK unchanged writes nothing | EX-HGT-5, EX-PREVIEW-1, EX-NODE-3, EX-EDIT-RT-3 |
| It just rebuilds correctly | "ideally it just rebuilds correctly" | after any upstream edit the IDs node stays healthy and rebuilds its parts, one undo step, ids unchanged | G8.5, IDS-UP-1 |
| The pattern is visible after URDF export, on the right link | | OpenCV reads every id off renders of the exported URDF; every part lands on its copy's link | CADX-URDF-4, IDS-FOLLOW-2, IDS-FOLLOW-3 |
| A part keeps everything its original has | | symmetric difference <= 0.01 mm^3 | G4.5 |
| Labels that print | "very blocky letters and support 0.6 mm nozzle" | PrusaSlicer, headless with his preset chain, gives every glyph, gap and counter its filament | EX-LABEL-FONT-3 |

Safety principles (the spec's words, shortened): existing tags never change by themselves (versioned rules + goldens); tests never touch Zach's documents; Fusion is closed to agents unless he opens a window; pace the tests (after the 2026-10-13 crash); live code is his code (atomic patches).

### 3.2 Features, with how success is measured

Kinds: U = offline-unit, O = offline-opencv, B = fusion-bridge, D = fusion-dialog, R = fusion-readonly, M = manual. "Core" = the feature's sources in `bam_cad_core`.

Area `extrude` (ArUco Extrude):

| Feature | Status | Core | Tests | Success is measured by |
|---|---|---|---|---|
| EX-TGT Targets | built | | EX-TGT-1..5 (B) | every `live_test` step builds a live, healthy node (faces, sketches, root sketches over a child, split faces) |
| EX-MODE Modes | built | `aruco_slabs` | EX-MODE-1, -4 (U); -2, -3 (B) | the parts follow the slabs (`test_aruco_slabs`); every mode builds in Fusion; a mode change rebuilds |
| EX-HGT Heights (Offset / Height) | built | `aruco_slabs` | EX-HGT-1..4 (U); -5, -6 (B); -7 (D) | slabs, defaults, layers and the TagSpec round trip (`test_aruco_slabs`, `test_markers`); measured z ranges on bodies in Fusion; the black follows the white top by expression |
| EX-SIZE Auto size | built | `aruco_autosize` | EX-SIZE-1..8, -10 (U); -9 (B) | P1 / P3 tables, clamping, dictionary growth, 780 random boxes, faces with holes (`test_aruco_autosize`); the GIM43 discs pinned (`test_aruco_disc_fit`); the Fusion gallery's label == the offline label on ten faces x three layouts |
| EX-LAYOUT Layouts and dictionaries | built | `aruco_board`, `aruco_dict`, `markers`, `fiducials` | EX-LAYOUT-1..5 (U); -6, -7 (O) | counts / ids / extents / ink pinned from cv2 (`test_aruco_board`, `test_aruco_output`); every id of every dictionary (9,596) == `generateImageMarker` and read back by `ArucoDetector`; boards detected and posed |
| EX-ORIGIN Origin (OpenCV's frame only) | built | `aruco_origin`, `markers` | EX-ORIGIN-1..3, -5..7 (U); -4 (O); -8..10 (B); -11 (D) | the words / order / swaps; `opencv_in_layout` == `detector_frame`; `evaluate()` x every Origin; OpenCV's PnP equals the record; live turns in Fusion; `origin_test` verdict PASS (1 um) |
| EX-MARK Corner mark | built | `aruco_chamfer` | EX-MARK-1..8, -18 (U); -9, -16, -17 (O); -10..14 (B); -15 (D) | which mark per layout x mode, at corner 0 for every turn, never a black cell; bodies probed at the mark; the studies (a white-tile cut within 0.6 pts; a ChArUco black-square cut changes no corner); Fusion single / grid / ChArUco / edits / variants |
| EX-PINS Locating pins | built | `aruco_slabs`, `aruco_chamfer` | EX-PINS-1..4 (U); -5, -6 (B) | plan, outlines, >= 1 mm clear of a cut corner, follow OpenCV's origin; holes measured in Fusion against the tolerance |
| EX-LABEL Label | built | `aruco_label` | EX-LABEL-1..11, -13, -14, -18 (U); -12, -17 (O); -15, -16 (B) | `test_aruco_label` sections (font, content, black, white, keepouts, one object, too long, batch ids, slab, safety check, records); bodies probed at the strokes; the study (#id + name costs < 1 pt on 4X4, nothing on 6X6); OpenCV reads every label line in the Fusion captures |
| EX-LABEL-FONT Font that prints | built | `aruco_label` | EX-LABEL-FONT-1, -2 (U); -3 (U, artifact) | the pixel font's glyphs; the slicing oracle's three failure modes caught; PrusaSlicer slices cases A-C clean and flags 0.3 mm strokes |
| EX-LABEL-RULE Clearance rule 2 (versioned) | built | `aruco_label` | EX-LABEL-RULE-1 (O); -2, -3 (U); -4 (B) | the gap study (0.5 module <= -5 pts, >= 1.0 within 0.5); the hard line and preferred margin; the rule-1 golden identical; in Fusion an older label shows the grey line, OK unchanged writes nothing |
| EX-LABEL-POS Auto position | built | `aruco_label` | EX-LABEL-POS-1, -2 (U); -3 (B) | the disc, settings, no room, copies, the far search; the dialog's fields show auto's spot; Fusion builds '#0' below the marker |
| EX-LABEL-GHOST The clear zone drawn | built | `aruco_label` | EX-LABEL-GHOST-1 (U); -2 (B) | guides from `clear_zones`; 3 guides and a 14-row info box in Fusion. Gap: the preferred margin draws solid, not dashed (OI-DASH) |
| EX-LABEL-SHOWN Build anyway | built | `aruco_label` | EX-LABEL-SHOWN-1..3 (U); -4 (U, mutations); -5 (B) | previews of refused labels; the node and dialog; every label mutation killed; Fusion 1/4 on 2026-10-13 (OI-LABEL-WARN) |
| EX-PREVIEW Ghost | built | | EX-PREVIEW-1 (O); -2 (D); -3 (M) | the ghost's frame == the record's; timings and cleanup; Zach's hand check |
| EX-NODE Timeline node and edits | built | | EX-NODE-1..5 (B); -6 (U); -7, -8 (M) | recompute in place, upstream edits, Fusion's edit route, structural rebuild, one group on failure; a variant never stands in for its template; Zach's double-click |
| EX-EDIT-RT Edit round trip | built | `aruco_autosize` | EX-EDIT-RT-1, -2 (U); -3 (B, 59 steps) | every Type x Auto x Extrude round trip; the timeline marker; Fusion edits through the real dialog. Gap: the Joint Origin duplicate escaped it (OI-JO-DUP) |
| EX-NODE-WARN A node's warning in its name | built | | EX-NODE-WARN-1 (B) | Fusion shows the words in the node's name. Gap: no offline test pins the words |
| EX-SYNC Refresh after an upstream change | built-switched-off (stale: on at c8216ff) | | EX-SYNC-1 (U); -2, -3 (B) | compute never depends on the check; Fusion thicker / longer / Compute All / Undo (8 steps); the combined hooks ran once, unpaced |
| EX-RESTRUCTURE Restructure in place | built-switched-off (stale: on) | `aruco_slabs` (the structures) | EX-RESTRUCTURE-1..3 (U); -4..6 (B) | 72 settings x 2 layouts on a timeline model; every pair of structures; 13 edit kinds in Fusion; atomic on failure. Gap: a fillet on the plate dies (OI-FILLET) |
| EX-MIGRATE Older nodes keep working | built | `aruco_slabs`, `aruco_origin` | EX-MIGRATE-1..3 (U); -4, -5 (B) | `from_legacy` gives the same slabs; the old Origin rule; the old checkbox; Fusion recomputes old nodes as before |
| EX-COLOUR Colours | built | | EX-COLOUR-1..4 (B); -5 (U) | every ArUco body black / white after create, compute, edit, undo, computeAll; `paint()` paints every piece |
| EX-DIALOG Dialogs remember | built | | EX-DIALOG-1..4 (U) | the settings file and the round trip (`test_aruco_settings`). Gap: no Fusion test opens the real dialog twice |
| EX-PRESETS Print presets | built-offline-only | | EX-PRESETS-1, -2 (U); -3 (M) | the store and PrusaSlicer reads; the dialog; eight Fusion checks pending |
| EX-CELLS Cell multiple | built-offline-only | `aruco_autosize` | EX-CELLS-1..3 (U); -4 (M) | the cell rule by brute force; the legacy golden; the dialog; Fusion pending (an Auto 28.56 mm on a 40 mm face read by OpenCV) |
| EX-EDIT ArUco Edit (older command) | built | | none | Gap: no test since ArUco Extrude became the live node |

Area `ids` (ArUco IDs):

| Feature | Status | Core | Tests | Success is measured by |
|---|---|---|---|---|
| IDS-PLAN Planner (G0) | built | `aruco_numbering`, `markers` | G0.1..G0.6, IDS-PLAN-7..9 (U) | `test_aruco_numbering`: unique per family, contiguous blocks, inside the dictionary or a named refusal, stable, overrides, owners, export consistency, helpers, dependencies |
| IDS-LEDGER Printed ids stay put | built | `aruco_numbering` | G0.7, IDS-LEDGER-2 (U); -3 (U, mutations); -4 (B) | every edit on the simulated design; the Fusion wiring on fakes; 17 mutations caught; test document S1 (10 steps). Gap: no "forget retired ids" |
| IDS-COLLECT Collection (G1) | built | `aruco_numbering` | G1.1..1.3 (B), G1.2-offline (U) | every instance listed once with its path, linked designs included; hidden excluded; the rack in < 10 s |
| IDS-NUMBER Numbering (G2) | built | `aruco_numbering` | G2.1, G2.2 (B) | no duplicate decoded from the BUILT geometry; OK again changes nothing |
| IDS-OVERRIDE Overrides (G3) | built | `aruco_numbering` | G3.1 (D), G3.2 (B) | typed id overrides, cleared text is auto, never an error; survives save / reopen |
| IDS-GEOM Per-copy geometry (G4) | built | `aruco_numbering` | G4.1..4.4 (B) | every pattern matches its id (sampled cells); parts on their copies < 1e-6 m / 1e-4 deg; the inventory delta exact; originals hidden only where overridden |
| IDS-FOLLOW Parts follow their copy | built | `aruco_numbering` | IDS-FOLLOW-1 (B); -2, -3 (O) | a part is its own component rigidly jointed to its copy; E2E gates (i)-(iv) on F13 / F14 / F14U / F15. Gap: the URDF mass counts a hidden original (OI-MASS) |
| IDS-GENERATED One sub-assembly | built | | IDS-GEN-1, -2 (B) | G4.3 rows; Fusion's Delete of a copy, Undo, Redo |
| IDS-FIDELITY A part keeps every feature | built | | G4.5, G4.6, IDS-FID-3 (B) | symmetric difference <= 0.01 mm^3; the label prints its own id; the `recut` mutation goes red |
| IDS-FRAMES Frames and export (G5) | built | `markers` | G5.1..5.3 (B) | Joint Origin = OpenCV's frame (0.000); export unique ids, one target; PnP <= 0.1 mm / 0.1 deg (G5.3 reads FAIL on F15 for a harness reason, OI-G53) |
| IDS-NODE One timeline node (G6) | built | | G6.1..6.4, IDS-NODE-5 (B) | one node with its icon; double-click edits; delete restores the pre-IDs inventory; undo / redo one step |
| IDS-DIALOG Dialog (G7) | built | | G7.1..7.4 (D) | the Tag button outlines a copy; preview == build (0.000 mm); Cancel leaves nothing; no level picker |
| IDS-ROBUST Robustness (G8) | built | `aruco_numbering` | G8.1..8.4 (B) | upstream edits, Deep Refresh, add / remove a copy, no crash, the user's documents untouched |
| IDS-UPSTREAM Rebuilds by itself (G8.5) | built | `aruco_numbering` | IDS-UP-1 (U); G8.5, IDS-UP-3..5 (B) | the pure halves and control flow on fakes; F16 run B2 10/10; the 2026-10-10 compute must fail; the dependency and copy probes |
| IDS-PERF Performance (G9) | built | | G9.1 (D) | open < 5 s, preview < 0.5 s, OK < 60 s on a rack-sized fixture |
| IDS-E2E Zach's bar | built | `aruco_numbering` | E2E.1 (D); E2E.2..4, .6, .7 (B); E2E.5, E2E-PER-FIXTURE (O) | two clicks; unique by geometry and OpenCV; parts on copies; two exports identical; PnP <= 0.1 mm / 0.1 deg; frames where Fusion draws; no phantom records |
| IDS-RACK Zach's rack (G10) | built | | G10.1..10.3 (B), G10-TABLE (R) | dry run, OK with no manual fixes, the tag -> id table cross-checked with the rebuilt URDF |

Areas `table`, `frames`, `export`, `beds`, `cadx`, `safety`, `public`:

| Feature | Status | Core | Tests | Success is measured by |
|---|---|---|---|---|
| MT-ROWS One marker table | built | (`aruco_numbering.instance_name`) | MT-ROWS-1, -2 (U); -3 (B) | names equal the IDs node's; the IDs dialog on the shared table; `marker_table_test` in Fusion |
| MT-ZOOM Click again = zoom | built | | MT-ZOOM-1 (U); -2 (B) | the timing, the camera, the state machine; Fusion click / click again |
| JO-OPTICAL Joint Origin = OpenCV's frame | built | `aruco_origin`, `markers` | JO-OPTICAL-1, -5 (B); -2 (U); -3, -4 (O) | 1 um in Fusion; the core attaches optical frames; PnP on Fusion renders 0.000; viewport vs URDF vs CAD truth within 3 mm / 3 deg |
| JO-AFTER Joint Origin after the node | built-switched-off (stale: on) | | JO-AFTER-1 (U); -2, -3 (B) | the frame sketch compute; jo=2 through the sync and restructure gates |
| JO-ORPHAN One Joint Origin per tag | built-offline-only | | JO-ORPHAN-1, -2 (U); -3 (B) | 66 checks through 12 edits on a stand-in; Fusion gates not run yet |
| JO-LEAK Exports skip a leaked Joint Origin | built | (`bam_joint_origins.py`) | JO-LEAK-1 (U); -2 (R) | the leak signature only; the rack's two leaks are exact duplicates |
| EXP-TYPES Export dialog | built | | EXP-TYPES-1..3 (U); -4 (B); -5 (D) | the type list, validity, Reset, old settings; refresh live tags first |
| EXP-PDF PDF sheet and images | built | `print_sheet`, `aruco_dict`, `aruco_board`, `markers` | EXP-PDF-1..4 (U); -5, -6, -8, -9 (O); -7 (B) | images and layouts; 600 dpi rasters find every id within 0.15 mm; the studies. Gap: no unit test pins the PDF's id / triangle / top-label geometry |
| EXP-STL STL files | built | `print_beds` | EXP-STL-1 (U); -2 (B) | one STL per body, stale ones removed |
| EXP-PRUSA PrusaSlicer project | built | `print_beds` | EXP-PRUSA-1 (B); -2..4 (U) | the project, beds, parts; finding PrusaSlicer. Gap: Send to PrusaSlicer has no recorded run |
| EXP-HIGHLIGHT The viewport shows what prints | built | | EXP-HIGHLIGHT-1 (U); -2 (B); -3 (M) | drawn from `executePreview` only; Cancel leaves no group |
| EXP-SLICER His own presets and MMU slots | built | `print_beds` | EXP-SLICER-1 (U) | the mirrored profile, nothing of ours in the project. Gap: the rack's slicing check is in a commit only |
| EXP-PROGRESS Progress bar | built | | EXP-PROGRESS-1 (U) | `eta_text` / `progress_message`. Gap: captures in a commit only |
| EXP-CHECK The 3MF oracle | built | `print_beds` | EXP-CHECK-1 (O) | every object of `aruco_tags.3mf` decodes to exactly its ids, squares within 0.25 mm |
| BEDS-PACK Packing | built | `print_beds` | BEDS-PACK-1..4 (U) | STL round trip, 41 tags -> 3 beds, PrusaSlicer 2.9 bed grid, one object per copy |
| BEDS-ORIENT Orientation | built | `print_beds` | BEDS-ORIENT-1, -2 (U) | face down when nothing is proud; `cad` keeps the modelled orientation |
| BEDS-PROJECT Project files and presets | built | `print_beds` | BEDS-PROJECT-1..4 (U) | the vendor chain resolved; 3MF members; PrusaSlicer reads every 3MF back. Gap: no printed-and-measured bed |
| CADX-COLLECT The exporter collects the tags | built | `markers` | CADX-COLLECT-1 (U) | the payload carries every record and the IDs node as root-level overrides |
| CADX-RESOLVE Per-copy ids and poses | built | `markers` | CADX-RESOLVE-1..4 (U) | `resolve`: inheritance, outermost wins, world poses, serials, two components with one name |
| CADX-URDF URDF target frames | built | `markers`, `urdf_writer`, `link_tree` | CADX-URDF-1, -2 (U); -3, -4 (O); -5 (M) | goldens byte for byte; yourdfpy FK; OpenCV reads every id off URDF renders; the CLI oracle |
| SAFE-BRIDGE Dev bridge gating | built | | none (partly `test_fusion_presence.py`) | Gap: ENABLED, FUSION_OPEN and the open-command wait have no test |
| SAFE-DOCS Tests never touch the user's documents | built | | SAFE-DOCS-1..4 (B) | fingerprints before / after. Gap: no test switches documents mid-run on purpose |
| SAFE-PRESENCE Agents stop while Zach uses Fusion | built | | SAFE-PRESENCE-1 (U) | `test_fusion_presence.py` |
| SAFE-CRASH Crash forensics | built | | none | Gap: no test of `tools/fusion_minidump.py` |
| SAFE-LIVE Live code is his code | built | | SAFE-LIVE-1..4 (U) | hot reloads under older dialogs; the after-compute hook never raises. Gap: no tool enforces the atomic patch |
| SAFE-PACING Test pacing | built-offline-only | | none | Gap: the IDs gates do not pace yet; no offline test of the helper |
| PUB-SYNC The public copy | built | | PUB-SYNC-1, -2 (U) | a dry-run sync has no WARNING; the public tests pass. Gap: the managed set lags (`aruco_numbering`, goldens, fixtures: OI-PUBLIC-SYNC) |
| PUB-README Public README draft | proposed | | none | Gap: the public README still describes the superseded per-level IDs |

### 3.3 Open items that touch the core

From the spec's `open_items` (17 in all; the rest are Fusion-side): OI-PDF-LABEL (the PDF sheet prints its own '#id' and part name, not the tag's label template); OI-PUBLIC-SYNC (`aruco_numbering`, the golden makers, `tests/aruco_label_fixtures.py` and `tests/fixtures/` are missing from the public repo's managed set); OI-DEFAULT (closed: Default keeps 0.5 mm marker steps, decided by Zach 2026-10-16); OI-T1 and OI-R1 (relief tags' and the rack's grid boards' absolute PnP bias: a geometry / render matter, no change planned).

## 4. Gaps: rules in the docs that the core does not implement

| # | Rule, where it is written | What the core has | Gap |
|---|---|---|---|
| 1 | Screws and holes in a ChArUco board (`proposal_aruco_chamfer.md` section 7): a head centred in a black square at most 0.35 of the square is safe, up to 0.5 still fine; a BRIGHT head closer than 0.3 square to an inner corner pulls it; never a screw in a white square; a centred head can read as phantom id 17, so keep id 17 off other tags | nothing. `aruco_label` and `aruco_trim` treat holes only as keep-outs for text and as a trim refusal | no check of a hole against the pattern (no "a hole under a marker breaks it", no "bright head too near a corner", no id-17 advice) |
| 2 | The sheet's option set (`proposal_aruco_marks.md` section 7): `id_mark off / border / strip / quiet`, `id_text` template, `orient_mark off / triangle / chamfer`, `orient_corner origin / tl / tr / br / bl`, `emboss_id off / back / edge`, `key_corner`; the triangle only when `q >= 0.7` module, else skip and warn | `print_sheet.SheetSettings`: `id_mark "border" \| "off"`, `top_label`, `orient_mark "triangle" \| "off"`. The triangle is drawn whatever the quiet zone. `strip` and `quiet` were dropped by Zach (section 11.1); `key_corner` became the 3D corner mark | `id_text`, `orient_corner`, `emboss_id` and the `chamfer` cut line are not built; no quiet-zone guard on the sheet's triangle |
| 3 | The PDF prints what the 3D label resolves (`proposal_aruco_label.md` section 5, "print_sheet (optional)"); `markers.print_items` passes `short_part_name`, which drops the path's last element, "worth fixing" | the sheet prints its own '#id' and `top_label` | OI-PDF-LABEL; the `short_part_name` note is not verified either way |
| 4 | `stroke_mm` "0 = auto: max(nozzle, 0.13 cap)" (`proposal_aruco_label.md` section 2 table; the `LabelSettings` field comment) | the pixel font fixes the stroke at cap / 5 (`stroke_for` ignores nozzle and stroke); a typed `stroke_mm` only raises `min_cap` | stale doc; the setting does not do what it says |
| 5 | Existing labels never change (the safety principle) | the rule-1 golden (8473e14) covers the clearance rule | the 2026-10-10 font change (stroke font -> pixel font) is not versioned; a label record from before it, if any exists, would re-lay out |
| 6 | Smart suggestions (`proposal_charuco_studio_in_fusion.md` section 10): capacity with headroom; the largest bit size that still reads at the camera's range (Z_max from `f_px`, `p` px per module, the view angle); the family table; the minimum Hamming distance among the ids IN USE; border bits `b = 2` for blurry prints; print-density snapping | `aruco_autosize.auto_dictionary` (capacity); `markers.suggest` (a dictionary and a size for a camera range, not surfaced by the add-in); the cell rule (replaces density snapping) | no Hamming-distance check among the ids in use; border bits are fixed at 1 everywhere (`aruco_dict.marker_grid`, `aruco_board`); no "range first" choice |
| 7 | The ledger: "forget retired ids" (`proposal_aruco_ids_stability.md`, "still open"; spec gap under IDS-LEDGER) | the ledger only grows; retired ids come back only when the dictionary is full | not built |
| 8 | A size or count change on a template with serialled copies re-runs the serial plan in the same command and says "block 5 -> 6, 2 copies renumbered" (`proposal_aruco_autosize.md` section 7) | `markers.plan_serials` and `aruco_numbering.plan_ids`; the re-run is the IDs node's (add-in) | no core function reports the block change in words |
| 9 | A quiet zone that is not a whole number of lines under "Each cell" is warned (`design_aruco_print_presets.md`, "Quiet zone") | the warning is `aruco_extrude_cmd` (add-in) | not in `aruco_autosize` |
| 10 | Print presets, PrusaSlicer profiles, the "heights in layers" note, the dialog's memory (`design_aruco_print_presets.md`) | `ArucoMarkers/aruco_presets.py`, `aruco_prusa.py`, `aruco_settings.py`: Fusion-free, but in the add-in and importing `aruco_core` | the core has no notion of a preset or a printer profile |
| 11 | "Plan a tag" (every design doc describes `evaluate()`'s order: fit, Origin, mark, label, pins, trim, slabs, record) | only `ArucoMarkers/aruco_feature.evaluate()` (imports `adsk`); the cells and trim goldens depend on it | the core has no single pure entry point that composes its modules; the record format (`rec["fusion"]`, `spec`, `mark`, `label`, `trim`) is written only there |
| 12 | Trim refusals need the face's loops and the measured volumes (`design_aruco_trim.md` section 3) | `plan_trim(face_loops=, volumes=)` takes them from the caller; Fusion measures them | a Studio adapter must measure volumes itself (a polygon-extrusion estimate is not in the core) |
| 13 | Existing tags never change: the Origin's old rule and the slab migration | unit tests only (`test_aruco_frame`, `test_aruco_slabs`) | no golden of real pre-2026-10-09 records (unlike cells, labels and trim) |
| 14 | The study's clean-white rule for the SHEET: 0.7 module along an edge, 0.5 off a corner (`proposal_aruco_marks.md` section 5.3) | the 3D label uses the quiet ring (>= 1 module) as the hard line | the sheet draws no other ink in the quiet zone, so nothing is needed; noted so nobody adds one |

Two older implementations sit beside the current ones and should not be ported twice: `markers.largest_rect` (sampled) next to `aruco_autosize.largest_clear_rect` (proven); `markers.fit_square` / `fit_board` next to `aruco_autosize`.

## 5. Findings for the planners

1. The core is real and green: 9 modules, 8,335 lines, stdlib only, and the 17 Fusion-free suites (1,838 checks) pass in 40 s on a plain Python 3.11. They can be copied into ArUco Studio as they are, with `markers.py` and `fiducials.py` (and `print_sheet.py` / `print_beds.py` for the sheet and the beds).
2. Three goldens pin the versioned rules bit for bit: cells (511 + 12), label rule 1 (36), trim (26 + 288). Two of them (cells, trim) include `aruco_feature.evaluate()` results, so they need the add-in on a stand-in `adsk` until the Studio has its own pure "plan a tag". Keep the golden JSON files and their makers.
3. The missing piece is the orchestration. `evaluate()` in `ArucoMarkers/aruco_feature.py` (3,769 lines, with `aruco_tags.py` 3,550 and `aruco_extrude_cmd.py` 2,860) is where the core's modules are composed and the record is written. That is the function the Studio core must own, as a pure function of (face loops, settings) -> (TagSpec, mark, label, pins, trim, slabs, record), with the three goldens replayed against it.
4. Four pure modules are trapped in the add-in: `aruco_presets.py`, `aruco_prusa.py`, `aruco_settings.py`, `aruco_ui_config.py` (1,230 lines, no `adsk`). The marker table's naming half, `aruco_restructure.restructure_plan` and `aruco_extrude_sync.after_compute` are pure too.
5. Frames and units differ by module (section 0). The pattern frame in mm (label, chamfer, trim) vs the centre frame in metres (board, autosize) is the seam a 2D / 3D viewer must draw correctly; `aruco_label.loops_to_pattern` is the converter.
6. `aruco_numbering` is pure but shaped by Fusion's occurrence model (`TagDef`, `OccurrenceRef`, paths `A:1+B:2`, stamps, `design_units`). A build123d or viser adapter must present its scene in those terms to reuse it.
7. The spec's switch table is stale: all four Extrude switches are already on at c8216ff.
