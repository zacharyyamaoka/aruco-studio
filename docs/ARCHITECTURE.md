# ArUco Studio: architecture

A functional core with thin shells. The core plans a tag from numbers. Every shell (the 2D view, the 3D view, Fusion, build123d, SVG / STL / PDF export) consumes the same plan.

| | |
|---|---|
| Written | 2026-10-16, from `docs/BRIEF.md` and `docs/inventory/*.md` |
| REF | `cad-exporter` worktree `aruco-fusion-plugin-0e9bcb` at `c8216ff`, read only |
| Status | the plan. Nothing in `aruco_studio/` or `studio/` exists yet. |

## 1. The idea in one picture

```
  settings + numbers + a target (2D outline in mm)
                 |
                 v
        aruco_studio.plan.plan_tag()          pure, never raises, stdlib only
                 |
                 v
              TagPlan                          layers of 2D polygons with holes + a z range,
                 |                             the OpenCV frame, the ids, per-field warnings
     +-----------+-----------+-----------+-----------+
     v           v           v           v           v
  2D view     3D view     Fusion      build123d   SVG / PNG / PDF / STL / 3MF
  (SVG)      (three.js)   adapter     adapter      exports
```

The shells never compute geometry. They draw, extrude or write what the plan says.

## 2. Repository layout

```
aruco-studio/
  aruco_studio/              the Python package (stdlib core; numpy + cv2 only in verify/)
    core/                    pure. No adsk, no file I/O, no network.
    plan/                    the adapter contract: TagSpec in, TagPlan out
    scene/                   many tags on one canvas; the .arucostudio.json file
    verify/                  render a plan, detect with OpenCV, check the frame by PnP
    server/                  FastAPI on 127.0.0.1:5360; the only place that reads/writes files
    adapters/fusion/         thin: TagPlan -> Fusion calls (not installed in this run)
  studio/                    the web app: Vite + React + TypeScript (dev server 5361)
  goldens/                   JSON made by running REF's code read-only (never by the new code)
  tests/                     pytest (core, plan, scene, verify, server, adapters) + Playwright e2e
  tools/                     check.py (ONE command), make_goldens_from_ref.py, ref_path.py
  docs/                      BRIEF, ARCHITECTURE, PLAN, spec.json, inventory/, status/
  .venv/                     Python (C:\Users\BAM\miniconda3\python.exe -m venv .venv)
  .data/                     the Studio's own store (presets, remembered options); git-ignored
```

Rules that hold everywhere:

| Rule | Why |
|---|---|
| `core/` and `plan/` import only the standard library and each other. | Fusion's Python has no numpy or cv2. The same files must run inside Fusion later. |
| `core/` and `plan/` never read or write a file. | So every function is a pure function of its arguments and can be tested with plain values. |
| Lengths in the plan are millimetres in the tag's own frame. | One unit for every shell. The core modules keep their own units inside (see 4.1); the plan converts at its boundary. |
| Every versioned rule keeps its number and its stored key, bit for bit. | Existing tags never change on their own. A Fusion adapter rebuilds today's tags identically. |
| The Studio never writes under `%USERPROFILE%\CADExporter`. Its own store is `ROOT/.data/` (env `ARUCO_STUDIO_HOME` overrides). | Zach's remembered options, presets and ledgers belong to the live add-in. |

## 3. The Python package

### 3.1 `core/`: pure logic

One module per REF core module, same public names, so the port is a copy and the goldens keep their keys. New modules hold what was trapped in the add-in.

| Module | From REF | What it holds | Units inside |
|---|---|---|---|
| `core/dictionary.py` + `core/aruco_dictionaries.json` | `bam_cad_core/aruco_dict.py`, `fiducials.ARUCO_DICTS` | OpenCV's 21 dictionaries without OpenCV; `marker_grid`, `black_rects`, `marker_png`, `marker_svg`; the sha256 check of the table | modules, y down |
| `core/board.py` | `aruco_board.py` | `BoardSpec`, counts, ids, extents, `object_points`, `charuco_corners`, `black_rects_m`, `opencv_frame`, PNG / SVG | metres, centre frame, y up |
| `core/markers.py` | the tag-model half of `markers.py` | `TagSpec` (the marker record in metres), `TagDef`, `OccurrenceRef`, `OverrideRecord`, `TagInstance`, `Resolution`, `resolve`, `plan_serials`, `board_spec`, `detector_frame`, `cell_boxes`, `split_path`, `slot_key`, `UNIT_TO_M`, `suggest` | metres |
| `core/origin.py` | `aruco_origin.py` | `ORIGIN_RULE = 2`, `TURNS_CW`, `effective`, `transposes`, `built`, `opencv_in_layout`, the dialog's words | degrees |
| `core/slabs.py` | `aruco_slabs.py` | Offset / Height slabs, `layers`, `plan` (the parts), `from_legacy`, pins and their grown holes | mm along the normal |
| `core/chamfer.py` | `aruco_chamfer.py` | the corner mark: `valid_marks`, `choice_of`, `plan_mark`, `mark_for_spec`, `Mark` | mm, pattern frame |
| `core/autosize.py` | `aruco_autosize.py` | `CELL_RULE = 1`, `cells_of`, `Layout`, `layout_for_size`, `default_layout`, `clamp_to_fit`, `face_default`, `candidates`, `candidates_on_loops`, `auto_dictionary`, `largest_clear_rect`, `fit_on_loops` | metres, face frame |
| `core/label.py` | `aruco_label.py` | `RULES {1, 2}`, `RULE = 2`, the pixel font, `LabelSettings`, `plan_label`, `label_violations`, `relabel`, `copy_regions`, `check_label`, `loops_to_pattern` | mm, pattern frame |
| `core/trim.py` | `aruco_trim.py` | `RULE = 1`, `trim_of`, `plan_trim`, `TrimPlan`, the refusals | mm, pattern frame |
| `core/numbering.py` | `aruco_numbering.py` | `plan_ids`, `plan_stable`, the ledger, `node_state`, `decode`, `auto_decision`, the digests | design units, ids |
| `core/sheet.py` | `print_sheet.py` | the true-size PDF sheet | mm |
| `core/beds.py` | `print_beds.py` | STL / 3MF, bed packing, PrusaSlicer project files | mm |
| `core/settings.py` | NEW, from `ArucoMarkers/aruco_feature.py` (pure part) | `SPEC_VERSION = 2`, `default_settings`, `normalise` (old `chamfer`, `frame`, `rotate_deg`), `size_is_auto`, `is_legacy`, `trim_setting`, `cells_of`, `plan_of`, `structure`, `default_numbers`, `resolve_follow`; the five generations of a tag's settings | |
| `core/edits.py` | NEW, from `aruco_feature.py` | the edit model: `settle`, `keep_black_step`, `merged`, `structural_change`, `edit_kind`, `edit_changes`, `rebuild_reason` | mm |
| `core/form.py` | NEW, from `aruco_extrude_cmd.py` and `aruco_extrude_ui.py` | the tag form's pure model: defaults and limits, `values` (fields -> settings + numbers), `label_values`, `trim_values`, `preset_values`, `snap_size`, `round_line`, `size_line`, `cells_line`, `layer_lines`, `info_rows`, `same_build`, `check_auto` | mm |
| `core/validate.py` | NEW, from `bam_fusion_ui.py` (Issue, Validator) and `aruco_extrude_ui.py` (`classify`, `label_issues`, `trim_issues`) | per-field messages: `Issue(field, level, text)`, `worst`, `summary_text`, `validate(spec, plan) -> [Issue]` | |
| `core/presets.py` | `ArucoMarkers/aruco_presets.py` (minus load / save), `aruco_preset_library.py` (words, cards, `Library`) | `default_preset`, `from_profile`, `normalise`, `line_mm`, `cell_setting`, `builtins`, `catalog`, `find`, `unique_name`, `changes`, `describe_changes`, `layer_note`; the cards' words and `thumb_svg` | mm |
| `core/prusa.py` | `ArucoMarkers/aruco_prusa.py` (minus the directory walk) | `read_ini(text)`, `read_bundle(text)`, `resolve`, `nozzle_of`, `width_of`, `profile`, `describe` | mm |
| `core/geometry.py` | NEW, from `aruco_feature.py` (`_v`..`_rotz`, `_xf_frame`), `aruco_tags.py` (Rodrigues, `_frame_error`, `_solve3`), `aruco_preview.py` (boxes, prisms) | vectors, 4x4 frames, box / prism polygons, polygon area and clipping helpers shared by plan/ | mm |
| `core/export_rows.py` | NEW, from `aruco_commands.py`, `aruco_export.py`, `aruco_export_preview.py` | the Export table's rows and words: `slug`, `labels` (" <1>", " <2>"), `body_role`, `print_rows`, `tag_parts`, `KINDS`, which files each type writes, `eta_text`, `progress_message` | |
| `core/marker_table.py` | NEW, from `aruco_marker_table.py` (pure half), `aruco_ids_cmd.py` | one row per tag copy: `MarkerRow`, `name_of`, `natural_key`, `family`, `order`, `duplicates`, `spec_info`, the Status words (`how`, `tone`) | |
| `core/ids_design.py` | NEW, from `aruco_ids_feature.py` (pure part) | `plan_design(snapshot, ledger)`, `Labels`, `stamp_chains`, `resolve_hidden`, `staleness`, `drift`, `auto_verdict`, `warning_text`, `export_overrides` over an **assembly snapshot** (section 5.4) | |

Not ported, on purpose: `markers.fit_square`, `fit_board`, `largest_rect` (superseded by `autosize`); the decal-era half of `fiducials.py`; `aruco_feature`'s Fusion expressions (`follow_expression`, `params_for`, `_mm_expr`) which belong to the adapter.

### 3.2 `plan/`: the adapter contract

| Module | Holds |
|---|---|
| `plan/target.py` | `Target`: the face or profile as plain numbers (section 5.1) |
| `plan/spec.py` | `TagSpec`: the request (section 5.2); `from_record()` reads a REF node's settings + numbers |
| `plan/plan.py` | `plan_tag(spec) -> TagPlan`: the port of `aruco_feature.evaluate()` as a pure function. Order kept: fit on loops, the Origin turn, the mark, the label (a strip grows the tile; the cut and the pins follow), the pins, the trim, the slabs. Never raises: a refusal is `errors`. |
| `plan/layers.py` | `TagPlan`, `Layer`, `Polygon` (section 5.3); the polygons from `cell_boxes`, `Mark`, `Label.boxes()`, `pin_outlines`, `TrimPlan.column()` |
| `plan/record.py` | the record a tag stores: `spec.to_dict()`, `mark`, `label`, `trim`, the rule versions; `record_digest`, `record_same`, `frame_digest`; the node's warning words |
| `plan/variants.py` | a copy's plan from the template's: `relabel` by id and name, `id_regions`, `label_slots` (which cells flip colour) |
| `plan/mesh.py` | a layer as triangles (boxes and extruded polygons with holes, ear clipping) for the 3D view and STL |
| `plan/exports.py` | `to_svg(plan)`, `to_png(plan, px_per_mm)`, `to_stl(plan)`, `to_sheet_items(scene)` |

### 3.3 `scene/`: many tags on one canvas

| Module | Holds |
|---|---|
| `scene/model.py` | `Scene`, `SceneTag` (section 5.5); add, move, duplicate, delete |
| `scene/ids.py` | unique ids and renumbering through `core.numbering.plan_stable`: every scene tag is one `TagDef` with one `OccurrenceRef` whose path is the tag's own name; overrides and the scene's ledger kept |
| `scene/file.py` | `.arucostudio.json` (`"schema": "arucostudio.scene/1"`): `dumps`, `loads`, migrations by schema number |

### 3.4 `verify/`: the oracle

| Module | Holds |
|---|---|
| `verify/render.py` | rasterise a plan's top view (black / white per layer, label ink included) at N px / mm into a numpy array |
| `verify/detect.py` | `cv2.aruco.ArucoDetector` with the plan's dictionary; grid / ChArUco through OpenCV's own `Board` objects |
| `verify/pnp.py` | the plan's `object_points` warped into a pinhole camera 25 degrees off (REF `test_aruco_frame_pnp`), `solvePnP`, compared with `TagPlan.frames.opencv`; the bar is 0.1 mm / 0.1 deg |
| `verify/report.py` | one dict per check: ids expected / read, the pose error, the PNG path |

numpy and opencv-python-headless are pinned in `requirements.txt` and imported only here.

### 3.5 `server/`: the one place with I/O

FastAPI + uvicorn on `127.0.0.1:5360`. Serves `studio/dist/` at `/` when it exists.

| Route | Does |
|---|---|
| `GET /api/health` | `{ok, version, ref_commit}` |
| `GET /api/dictionaries` | names, bits, capacity |
| `POST /api/plan` | `TagSpec` -> `TagPlan` (JSON, section 5.3) |
| `POST /api/validate` | `TagSpec` -> `[Issue]` |
| `POST /api/candidates` | the ranked Layout list for a target |
| `GET/PUT /api/scene` | the open scene; `POST /api/scene/renumber` |
| `POST /api/scene/open`, `/api/scene/save` | the `.arucostudio.json` file (paths under `ROOT/.data/scenes/` or given) |
| `POST /api/export/{svg,png,pdf,stl,3mf}` | files into `ROOT/.data/exports/<scene>/` |
| `POST /api/verify` | `TagPlan` -> the verify report |
| `GET/POST /api/presets`, `GET /api/prusa/profiles` | `core.presets` over `server/store.py` |

`server/store.py` owns every file: presets (`bam_aruco_presets/1`, same shape as REF so a preset file can be copied over), remembered options, the recent list, PrusaSlicer's config directory (read only; `BAM_ARUCO_PRUSASLICER_DIR` points at a fixture).

### 3.6 `adapters/fusion/`: thin

| Module | Holds |
|---|---|
| `adapters/fusion/target.py` | a Fusion face or profile -> `Target` (from REF `profile_rect`, `face_frame`, `keep_x`, `_face_loops_m`, `_trim_inputs`) |
| `adapters/fusion/build.py` | `TagPlan` -> temporary bodies per layer (`TemporaryBRepManager` boxes and polygon prisms), the combines, the base features |
| `adapters/fusion/feature.py` | the custom feature: create, compute, edit; parameters and expressions (`follow_expression`, `params_for`) |
| `adapters/fusion/joint_origin.py` | OpenCV's frame -> a Joint Origin (angle, offsets, flip); one per tag |
| `adapters/fusion/paint.py` | appearances and the repaint hooks |
| `adapters/fusion/records.py` | the record on the component: `plan/record.py`'s dict plus the adapter's handles (tokens, body names, group) |
| `adapters/fusion/restructure.py` | `restructure_plan` (pure) and the in-place rebuild |
| `adapters/fusion/fake_adsk.py` | the stand-in used by the tests (from REF `tests/aruco_trim_fixtures.py`, `aruco_ui_stubs.py`) |

In this run the adapter is a skeleton tested against the fake. It is not installed into Fusion.

## 4. The web app: `studio/`

Stack: Vite + React + TypeScript. State in one store (zustand). No deviation planned; a deviation needs a written reason in `docs/status/M3.md`.

| Part | What it does |
|---|---|
| 2D canvas | an SVG canvas like Figma: pan, zoom, select, drag, snap; many tags on one canvas. Each tag draws its `TagPlan` layers as `<path>` elements (polygons with holes, `fill-rule="evenodd"`); white, black, cut, keep-column colours from a theme table. |
| 3D view | three.js; the same layers extruded between `z[0]` and `z[1]` (via `/api/plan`'s `mesh` or client-side extrusion of the same polygons); a Google-Maps-style 2D / 3D toggle that keeps the camera's centre and zoom |
| Inspector | the tag form from `core.form`'s field list: layout, dictionary, id, size (Auto), cells, mode, op, Offset / Height per colour, Origin, corner mark, label, pins, trim; per-field messages from `/api/validate` |
| Library | print presets (a React port of REF `resources/preset_library`'s cards) |
| IDs table | one row per scene tag (`core.marker_table` rows), renumber, overrides |
| Export | SVG / PNG / PDF sheet / STL / 3MF / verify |

The app computes nothing geometric. Every number on screen comes from a `TagPlan` or an `Issue`.

## 5. The contracts

Types are written like JSON schema. `mm` means millimetres. Polygons are `[[u, v], ...]`, closed implicitly, outer loops counter-clockwise, holes clockwise.

### 5.1 `Target` (the face or profile, as numbers)

| Field | Type | Meaning |
|---|---|---|
| `kind` | `"face" \| "profile" \| "free"` | a face of a body; a sketch profile over a body; a free sketch with nothing under it |
| `w_mm`, `h_mm` | number | the box in the target's own 2D frame (origin at the box centre, u right, v up) |
| `loops_mm` | `[polygon, ...]` | the outline: the outer loop first, then holes. Empty = the box. |
| `has_body` | boolean | a body under the target |
| `z_sign` | `1 \| -1` | which way the target's normal points relative to the host |
| `x_ref` | `[u, v] \| null` | a face tag's x as it was made (REF `keep_x`); null for a profile |
| `body_mm` | `{u0, v0, u1, v1, z0, z1} \| null` | the body under, boxed in the target frame (trim) |
| `volumes_mm3` | `{body, under_face} \| null` | measured volumes for the trim rules; null = "nothing measured" (a refusal unless `trim.force`) |

The adapter fills this. The core never sees an entity.

### 5.2 `TagSpec` (the request)

The name is the task's. It is NOT `core.markers.TagSpec` (the marker record in metres), which is an OUTPUT of the plan (`TagPlan.marker`). Code imports them from their modules and never mixes them.

| Field | Type | Meaning |
|---|---|---|
| `schema` | `"arucostudio.tagspec/1"` | |
| `settings` | object | REF's settings dict, shape `v: 2` (`core.settings.default_settings`), see the table below |
| `numbers` | object | `marker_id`, `size` (mm; 0 = Auto), `square` (mm; ChArUco), `white_offset`, `white_height`, `black_offset`, `black_height`, `pin_size`, `pin_length`, `pin_tol`; legacy: `height`, `thickness`, `above` |
| `target` | `Target` | |
| `name`, `key` | string | the label's `{name}` and `{key}` |

Settings keys and the versioned rules they carry:

| Key | Values | Versioned rule it carries |
|---|---|---|
| `v` | `2` | `SPEC_VERSION`; `normalise` maps older shapes |
| `layout`, `dictionary`, `quiet_modules`, `grow`, `legacy` | REF values | |
| `mode`, `op` | `both\|black\|white`, `join\|new` | |
| `size_auto`, `force` | | Auto size = `numbers.size == 0` (`size_is_auto`) |
| `turn`, `origin_v` | `0\|90\|180\|270`, `2` or absent | `ORIGIN_RULE`: absent = the pre-2026-10-09 rule |
| `cells` | `{rule: 1, of: "cell"\|"marker", mm, min_mm}` or absent | `CELL_RULE`: absent = legacy 0.5 mm steps |
| `corner_mark` | `none\|cut\|triangle` | the old `chamfer: true` reads as `cut` |
| `label` | `LabelSettings.to_dict()` with `rule` | `RULES`: a label without `rule` is rule 1; `offset_x_mm` / `offset_y_mm` honoured |
| `pin` | `none\|triangle\|round` | |
| `trim` | `{rule: 1, axes, margin_mm, force}` or absent | `trim.RULE`: anything else reads as off |
| `rotate_deg` | legacy | turned the frame BEFORE the fit; kept on nodes that have it |
| `x_base`, `x_ref`, `z_sign`, `has_body`, `source` | from the target at creation | the adapter's; mirrored in `Target` |
| `jo_v`, `host_xform`, `key`, `black_follows` | adapter only | carried through untouched, never read by the plan |

### 5.3 `TagPlan` (the result)

All lengths in mm in the PATTERN frame: origin at the pattern's centre, u = image right, v = image up, AFTER the Origin turn; z along the face normal, 0 at the face plane, + out of it. This is the frame `core.chamfer`, `core.label` and `core.trim` already use.

| Field | Type | Meaning |
|---|---|---|
| `schema` | `"arucostudio.tagplan/1"` | |
| `ok` | boolean | false when nothing fits or the plan refused; `errors` says why |
| `errors` | `[string]` | |
| `marker` | object | `core.markers.TagSpec.to_dict()` AS BUILT (a rectangular board at 90 / 270 has cols / rows swapped) |
| `layout` | object | the fit as laid out (`autosize.Layout`: kind, counts, sizes, fill, notes, badges) |
| `placement` | `{cx_mm, cy_mm, angle_deg, turn_deg, lift_mm}` | where the pattern frame sits in the target's frame: centre, the fit's angle plus the Origin turn, and the surface over the face |
| `parts` | `[string]` | `core.slabs.Plan.parts` in timeline order: `tile`, `pin`, `pocket`, `pattern`, `recess`, `trim` |
| `layers` | `[Layer]` | section below |
| `frames.opencv` | 16 numbers | OpenCV's frame of the tag as built, in the pattern frame (`origin.opencv_in_layout`); boards: top-left outer corner, y down, z into the board |
| `frames.detector_z_mm` | number | the plane the detector sees (the pattern's top) |
| `ids` | `[int]` | the ids this tag prints (`marker.ids`) |
| `labels` | `[{slot, text, cap_mm, stroke_mm}]` | the label's resolved texts per slot |
| `mark`, `label`, `trim`, `pins` | objects | `Mark.to_dict()`, `Label.to_dict()`, `TrimPlan` as dict, the pin outlines: the record pieces, unchanged from REF so a Fusion record compares |
| `warnings` | `[Issue]` | `{field, level: "info"\|"warn"\|"error", text}`; `field` names a form field or `"tag"` |
| `rules` | object | `{spec: 2, origin: 2\|null, cells: {...}\|null, label: 1\|2, trim: 1\|null}`: the versions this plan was made under |
| `mesh` | optional | per layer, triangles for the 3D view (filled by `/api/plan?mesh=1`) |

`Layer`:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | `tile`, `pocket`, `pattern`, `label_cut`, `label_join`, `white_strip`, `mark_cut`, `mark_triangle`, `pin`, `hole`, `recess_tile`, `recess_pattern`, `trim_keep` |
| `part` | string | which `parts` entry it belongs to |
| `colour` | `"white" \| "black" \| "none"` | what it prints as; `none` for a cut or a keep column |
| `op` | `"add" \| "cut" \| "keep"` | add material, cut it from what is under, or keep only this column (trim) |
| `z` | `[lo, hi]` | mm along the normal |
| `polygons` | `[{outer: polygon, holes: [polygon]}]` | 2D in the pattern frame |

How a layer is made: `tile` from the tile rectangle (grown by a label strip; the corner cut as a hole-less polygon with one corner removed); `pattern` from `markers.cell_boxes` merged by `dictionary.black_rects` per marker; `label_*` from `Label.boxes()`; `mark_triangle` from `Mark.solid`; `pin` / `hole` from `slabs.pin_outlines` and `grow`; `recess_*` from `slabs.Plan.recess`; `trim_keep` from `TrimPlan.column()`.

### 5.4 `AssemblySnapshot` (what numbering needs)

`core.numbering` is pure but shaped by Fusion's occurrence model. Every adapter presents its scene in these terms.

| Field | Type | Meaning |
|---|---|---|
| `schema` | `"arucostudio.snapshot/1"` | |
| `design_units` | `"mm" \| "cm" \| ...` | `markers.UNIT_TO_M` keys |
| `tags` | `[TagDef.to_dict()]` | one per component that holds a tag |
| `occurrences` | `[{path: "A:1+B:2", component, visible, linked, world: 16 numbers, stamp}]` | every copy, hidden ones included |
| `overrides` | `[OverrideRecord]` | typed ids |
| `ledger` | `Ledger.to_dict()` | `bam_aruco_ids_ledger/1` |
| `state` | `node_state` dict or null | `bam_aruco_ids/1` |

The Studio scene builds one from itself (each tag = a component with one occurrence at the tag's pose). The Fusion adapter builds one from `collect_design`. A build123d adapter walks its assembly.

### 5.5 `Scene` (the canvas and the file)

| Field | Type | Meaning |
|---|---|---|
| `schema` | `"arucostudio.scene/1"` | |
| `units` | `"mm"` | |
| `name` | string | |
| `tags` | `[SceneTag]` | |
| `ledger` | `Ledger.to_dict()` | printed ids never move, here too |
| `overrides` | `{tag_name: id}` | |
| `presets_used` | `[string]` | names, for the Library's "in use" chips |

`SceneTag`:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | unique in the scene; the numbering path |
| `spec` | `TagSpec` | the request |
| `pose` | 16 numbers | the target's frame in the scene (mm, row-major 4x4) |
| `plan` | `TagPlan \| null` | a cache; always recomputed on load |
| `locked` | boolean | a printed tag: the Studio refuses edits that would change its ink |

The file is the scene as JSON with `plan` dropped. `scene/file.py` keeps a migration per schema number.

## 6. Why this split

| Problem today (REF) | What the split does |
|---|---|
| `evaluate()` takes a Fusion entity, so every check of the tag's geometry needs the shared Fusion window. | `plan_tag(TagSpec)` takes numbers. The 12 + 26 `evaluate()` goldens replay in pytest in seconds. |
| 36 of 45 add-in files import `adsk`; about 5,100 production lines of pure logic sit next to Fusion calls. | The pure lines move to `core/` and `plan/`. The adapter keeps about 11,000 lines of Fusion calls and nothing else. |
| The ghost (`aruco_preview`), the Fusion bodies (`aruco_feature.part_body`) and the record each re-derive the geometry. | One `TagPlan`. The ghost is the 2D / 3D view. The bodies are the layers extruded. The record is `plan/record.py`. |
| The dialog's 220-line refresh state machine is wired to Fusion input ids. | `core.form` is the pure model (values, defaults, info lines). The Studio's inspector and the Fusion dialog are two views of it. |
| Numbering reads Fusion's visibility model inside `collect_design`. | `AssemblySnapshot` carries exactly what the planner needs; each adapter fills it. |

### How build123d and viser reuse the plan (later)

| Adapter | Target | Build | Numbering |
|---|---|---|---|
| build123d | a `Face` -> `Target` (its wires as `loops_mm`, its normal, the solid under it as `body_mm` and `volumes_mm3`) | each `Layer` -> `extrude(Polygon with holes, z[1] - z[0])` placed at `z[0]`, then `fuse` / `cut` per `op`; `trim_keep` -> `intersect` | the assembly's parts as `occurrences`; `plan_stable` renumbers; the per-copy plan from `plan/variants.py` |
| viser | none (no geometry to fit) | `TagPlan.mesh` per layer as a `MeshHandle`, coloured by `colour`; the OpenCV frame as a `FrameHandle` | the scene graph's node names as paths |

Neither needs anything from `adapters/fusion/`. Both need only `plan/` and `scene/`, and the STL export already comes from `plan/mesh.py`.
