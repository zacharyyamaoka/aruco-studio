# ArUco Studio: architecture

A functional core with thin shells. The core plans a tag from numbers. Every shell (the 2D view, the 3D view, Fusion, build123d, SVG / STL / PDF export) consumes the same plan.

| | |
|---|---|
| Written | 2026-10-16, from `docs/BRIEF.md` and `docs/inventory/*.md` |
| REF | `cad-exporter` worktree `aruco-fusion-plugin-0e9bcb` at `c8216ff`, read only |
| Status | M1 (core), M2 (plan, scene, verify, exports, server) and M3 (the Studio web app, with the Library) are built. Where the built contract differs from this text (Target fields, Layer steps, combines, frames, levels): `docs/PLAN.md` section 8 and `docs/API.md`; the web app: `docs/STUDIO.md` and `docs/status/M3.md` |

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
  tools/                     check.py (ONE command, groups discovered), make_goldens_from_ref.py,
                             make_evaluate_goldens.py, ref_sections.py, ref_path.py, spec_status.py
  docs/                      BRIEF, ARCHITECTURE, PLAN, spec.json, inventory/, status/
  .venv/                     Python (C:\Users\BAM\miniconda3\python.exe -m venv .venv)
  .data/                     the Studio's own store (presets, remembered options); git-ignored
```

Rules that hold everywhere:

| Rule | Why |
|---|---|
| `core/` and `plan/` import only the standard library and each other. | Fusion's Python has no numpy or cv2. The same files must run inside Fusion later. |
| `core/` and `plan/` never read or write a file. | So every function is a pure function of its arguments and can be tested with plain values. |
| `plan/` and `scene/` never import `adapters/`, `server/` or `verify/`. | build123d and viser reuse `plan/` and `scene/` alone (section 6). A test greps for it. |
| The plan reads `x_ref`, `z_sign`, `has_body` and the loops from `Target` only, never from `settings`. | Stripping every adapter-only key from `settings` (5.2) gives the same `TagPlan`. A test does exactly that. |
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
| `core/presets.py` | `ArucoMarkers/aruco_presets.py` (minus load / save), `aruco_preset_library.py` (words, cards, `Library`, the pure half of `preset_of_node`) | `default_preset`, `from_profile`, `preset_of(settings, numbers)` (a tag's print settings as a preset; the adapter reads the node, the core maps), `normalise`, `line_mm`, `cell_setting`, `builtins`, `catalog`, `find`, `unique_name`, `changes`, `describe_changes`, `layer_note`; the cards' words and `thumb_svg` | mm |
| `core/prusa.py` | `ArucoMarkers/aruco_prusa.py` (minus the directory walk) | `read_ini(text)`, `read_bundle(text)`, `resolve`, `nozzle_of`, `width_of`, `profile`, `describe`; M8c (not REF's): the allow-list (`PHYSICAL_KEYS`, `private_key`, `drop_private`), `parse_physical`, `physical_printers`, `printer_of`, `condition` / `fits` (which print presets fit a printer), `prints_for`, `pair_profile`, `selected` | mm |
| `core/geometry.py` | NEW, from `aruco_feature.py` (`_v`..`_rotz`, `_xf_frame`), `aruco_tags.py` (Rodrigues, `_frame_error`, `_solve3`, the composition maths of `_place_joint_origin`), `aruco_preview.py` (boxes, prisms) | vectors, 4x4 frames, box / prism polygons, polygon area and clipping helpers shared by plan/; `jo_decompose(frame) -> (angle_deg, offsets, flip)` and `jo_compose(...) -> frame` (how Fusion composes a Joint Origin: x turned by `angle` about the UNFLIPPED z, the flip half a turn about x', offsets along the FINAL axes). Pure maths; the adapter only passes the three numbers to Fusion | mm |
| `core/restructure.py` | `ArucoMarkers/aruco_restructure.py` (pure half) | `has_combine`, `restructure_plan(parts_old, op_old, parts_new, op_new)`, `new_parts`, `needed_params`, `refusal` (the words), `lost_after`, `what_goes`; with `core.edits.structural_change` this is the whole "what a structural edit does" model. The in-place `restructure()` itself stays in the adapter | |
| `core/faces.py` | `ArucoMarkers/aruco_autosize_gallery.py` (`FACES`, `TYPED`, `shape_pts`, `loops_mm`, `bbox_mm`, `summary`) | the ten non-box faces plus a box and a disc as loops in mm (chord tolerance 0.05 mm, the way Fusion strokes an edge). Product data: the Studio's target palette serves them (`GET /api/targets`); the tests use the same list | mm |
| `core/export_rows.py` | NEW, from `aruco_commands.py`, `aruco_export.py`, `aruco_export_preview.py` | the Export table's rows and words: `slug`, `labels` (" <1>", " <2>"), `print_rows`, `tag_parts`, `KINDS`, which files each type writes, `eta_text`, `progress_message`. NOT `body_role`: it parses Fusion's body names ("tag tile <key>"), so it is the adapter's | |
| `core/marker_table.py` | NEW, from `aruco_marker_table.py` (pure half), `aruco_ids_cmd.py` | one row per tag copy: `MarkerRow`, `name_of`, `natural_key`, `family`, `order`, `duplicates`, `spec_info`, the Status words (`how`, `tone`) | |
| `core/ids_design.py` | NEW, from `aruco_ids_feature.py` (pure part) | `plan_design(snapshot, ledger)`, `Labels`, `stamp_chains`, `resolve_hidden`, `staleness`, `drift`, `auto_verdict`, `warning_text`, `export_overrides` over an **assembly snapshot** (section 5.4) | |

Not ported, on purpose: `markers.fit_square`, `fit_board`, `largest_rect` (superseded by `autosize`); the decal-era half of `fiducials.py`; `aruco_feature`'s Fusion expressions (`follow_expression`, `params_for`, `_mm_expr`) which belong to the adapter.

### 3.2 `plan/`: the adapter contract

| Module | Holds |
|---|---|
| `plan/target.py` | `Target`: the face or profile as plain numbers (section 5.1); `box(w, h)`, `disc(r, holes)`, `from_face(name)` (the `core.faces` list); `prism_volumes(target)`: the trim's `volumes_mm3` for a Studio target, which is always a prism (the outline extruded from `body_mm.z0` to `z1`), so `body = box area x depth` and `under_face = face area x depth` are exact, not estimates. Fusion measures real bodies instead. |
| `plan/spec.py` | `TagSpec`: the request (section 5.2); `from_record()` reads a REF node's settings + numbers; `check(spec) -> [Issue]`: the per-field checks of section 5.6, run first by `plan_tag` and by `/api/validate` |
| `plan/plan.py` | `plan_tag(spec) -> TagPlan`: the port of `aruco_feature.evaluate()` as a pure function. Order kept: fit on loops, the Origin turn, the mark, the label (a strip grows the tile; the cut and the pins follow), the pins, the trim, the slabs. Never raises: a refusal is `errors`. |
| `plan/layers.py` | `TagPlan`, `Layer`, `Polygon` (section 5.3); the polygons from `cell_boxes`, `Mark`, `Label.boxes()`, `pin_outlines`, `TrimPlan.column()`; the `guides` (quiet ring, clear zones, keep-outs, a refused label's preview) from `label.quiet_ring`, `clear_zones`, `mark_keepouts`, `pin_keepouts`, `Label.preview` |
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
| `GET /api/form` | the inspector's field list from `core.form` + section 5.6: for every field its key path, type, default, limits, choices and which `settings` / `numbers` key it writes. The web app builds the inspector from this, never from a hand-written copy |
| `GET /api/targets` | the target palette: box, disc, the ten `core.faces` as `Target`s |
| `POST /api/plan` | `TagSpec` -> `TagPlan` (JSON, section 5.3); `?mesh=1` fills `mesh`. A wrong TYPE (a string for a number, a missing required key) is 422 with the field's key path; a wrong VALUE goes through `plan_tag` and comes back as an `Issue` (5.6) |
| `POST /api/validate` | `TagSpec` -> `[Issue]` |
| `POST /api/candidates` | the ranked Layout list for a target |
| `GET/PUT /api/scene` | the open scene; `POST /api/scene/renumber` |
| `POST /api/scene/open`, `/api/scene/save` | the `.arucostudio.json` file (paths under `ROOT/.data/scenes/` or given) |
| `POST /api/export/{svg,png,pdf,stl,3mf}` | files into `ROOT/.data/exports/<scene>/` |
| `POST /api/verify` | `TagPlan` -> the verify report |
| `GET/POST /api/presets`, `GET /api/prusa/profiles` | `core.presets` over `server/store.py` |
| `GET /api/prusa/printers`, `/api/prusa/stale`, `/api/prusa/watch`, `POST /api/scene/send/prusaslicer` | M8c, in `server/prusa_api.py` (the folder's watcher in `server/prusa_watch.py`): docs/API_prusa.md |

`server/store.py` owns every file: presets (`bam_aruco_presets/1`, same shape as REF so a preset file can be copied over), remembered options, the recent list, PrusaSlicer's config directory (read only; `BAM_ARUCO_PRUSASLICER_DIR` points at a fixture).

`server/app.py` serves `studio/dist/` at `/` when it exists and allows CORS from `http://127.0.0.1:5361` and `http://localhost:5361` from the start, so the web app's builder never edits the server.

### 3.6 `adapters/fusion/`: thin

| Module | Holds |
|---|---|
| `adapters/fusion/target.py` | a Fusion face or profile -> `Target` (from REF `profile_rect`, `face_frame`, `keep_x`, `_face_loops_m`, `_trim_inputs`) |
| `adapters/fusion/build.py` | `TagPlan` -> temporary bodies per layer (`TemporaryBRepManager` boxes and polygon prisms), the combines, the base features |
| `adapters/fusion/feature.py` | the custom feature: create, compute, edit; parameters and expressions (`follow_expression`, `params_for`) |
| `adapters/fusion/joint_origin.py` | one Joint Origin per tag: `core.geometry.jo_decompose` gives (angle, offsets, flip); this module only places it, reads it back and keeps the one-per-tag rule |
| `adapters/fusion/paint.py` | appearances and the repaint hooks |
| `adapters/fusion/records.py` | the record on the component: `plan/record.py`'s dict plus the adapter's handles (tokens, body names, group); `body_role` (cells or tile from a body's NAME); `preset_of_node` = read the node, then `core.presets.preset_of` |
| `adapters/fusion/restructure.py` | the in-place rebuild only (release, delete, create, regroup, atomic). What to delete and create comes from `core.restructure.restructure_plan` |
| `adapters/fusion/sync.py` | the after-compute hooks (idle detection, the hidden refresh command, the retry); the policy is `core.numbering.auto_decision` and `core.edits.verdict` |
| `adapters/fusion/fake_adsk.py` | the stand-in used by the tests (from REF `tests/aruco_trim_fixtures.py`, `aruco_ui_stubs.py`) |

In this run the adapter is a skeleton tested against the fake. It is not installed into Fusion.

## 4. The web app: `studio/`

Stack: Vite + React + TypeScript. State in one store (zustand). Built as planned; the few choices where this text was silent (the 2D view fills the plan's top view and outlines each layer, one path per layer, the installed Chrome for Playwright, e2e in `ROOT/e2e`) are in `docs/status/M3.md`.

| Part | What it does |
|---|---|
| 2D canvas | an SVG canvas like Figma: pan, zoom, select, drag, snap, rulers in mm; many tags on one canvas, each on its own target. Each tag draws its target's outline and holes, then its `TagPlan` layers as `<path>` elements (polygons with holes, `fill-rule="evenodd"`), then its `guides` (the quiet ring, the clear zones, a refused label's preview in orange); white, black, cut, keep-column colours from a theme table. Every `<path>` carries `data-layer="<name>"` and a refused label's preview `data-state="refused"`, so a test can count and find them. |
| Sketch and shapes (M8b1) | the target editor is gone. The Studio edits the design file (`arucostudio.scene/2`): shape tools (rectangle, circle, polygon, slot, holes), Extrude, and ArUco Extrude on a shape or on faces picked in 2D or 3D. A face of an Extrude is the tag's target. See docs/STUDIO.md. |
| 3D view | three.js; the same layers extruded between `z[0]` and `z[1]`, from `/api/plan?mesh=1` only (the app never triangulates); a Google-Maps-style 2D / 3D toggle that keeps the camera's centre and zoom; the OpenCV frame as a triad. The store exposes the scene's z extent (`zRange`) and the camera centre for the tests. |
| Inspector | the tag form from `/api/form`'s field list: layout, dictionary, id, size (Auto), cells, mode, op, Offset / Height per colour, Origin, corner mark, label, pins, trim, the Layout candidates; per-field messages from `/api/validate` under the field each `Issue.field` names |
| IDs table | one row per scene tag (`core.marker_table` rows), renumber, overrides; click a row to select |
| Export | SVG / PNG / PDF sheet / STL / 3MF / verify, with the verify report shown |
| Library (M5) | print presets (a React port of REF `resources/preset_library`'s cards), click-again-to-zoom in the IDs table |

The app computes nothing geometric. Every number on screen comes from a `TagPlan`, a `Target` or an `Issue`.

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
| `volumes_mm3` | `{body, under_face} \| null` | measured volumes for the trim rules; null = "nothing measured" (a refusal unless `trim.force`). The Studio fills it with `plan/target.prism_volumes` (exact for its prism targets); Fusion measures the real body |

The adapter fills this. The core never sees an entity. In the Studio the design file's shapes and Extrudes fill it (`plan/shapes.face_target`, section 4), so a Studio tag with a thickness behaves like a tag on a plate: pocket, recess, pins and trim all plan.

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
| `frame` | legacy (settings or record) | the removed "Frame" choice; read as OpenCV's frame and dropped on the next write (REF `aruco_tags.has_old_frame`, `test_aruco_frame` EX-MIGRATE-2) |
| `label.scope` = `"square"` | legacy (phase 1) | read as `row = "square"` by `LabelSettings.from_dict` |
| `numbers.height`, `thickness`, `above` | legacy (before 2026-10-08) | `core.slabs.from_legacy` maps them to Offset / Height pairs; a plan from the legacy numbers equals the plan from the mapped pairs, and `TagPlan.rules.legacy_numbers` says it happened |
| `x_base`, `x_ref`, `z_sign`, `has_body`, `source` | from the target at creation | the adapter's; mirrored in `Target`. The plan reads them from `Target`, never from here |
| `jo_v`, `host_xform`, `key`, `black_follows` | adapter only | carried through untouched, never read by the plan |

The last two rows are the adapter's keys and they stay in `settings` only because the settings dict's shape (`v: 2`) is what a REF record stores and what `record_same` compares. `plan_tag` must give the same `TagPlan` with every one of them deleted; `tests/plan/test_adapter_keys.py` checks that on every golden case.

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
| `guides` | object | the lines the 2D view draws and nothing prints, all in the pattern frame: `sticker` (rect), `quiet_ring` (rect), `clear_hard` and `clear_preferred` (`label.clear_zones` under the label's rule), `keepouts` (`[polygon]`: the mark's and the pins'), `label_preview` (`[Box]`, only when the label was refused: where it was asked for, drawn in orange), `target` (the target's loops turned into the pattern frame by `label.loops_to_pattern`) |
| `warnings` | `[Issue]` | `{field, level: "info"\|"warn"\|"error", text}`; `field` is a key path of section 5.6 (`numbers.size`, `settings.label.cap_mm`, ...) or `"tag"` |
| `rules` | object | `{spec: 2, origin: 2\|null, cells: {...}\|null, label: 1\|2, trim: 1\|null, legacy_numbers: bool, font: 1}`: the versions this plan was made under. `font: 1` is the pixel font of 2026-10-10 (REF never versioned the font change; the Studio records it here, in the plan only, so a stored label record keeps REF's exact shape) |
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

A `locked` tag: `scene.model.edit(scene, name, change)` refuses any change whose plan has a different `record_digest` (ink, size, ids, label text) and returns an `Issue(field, "error", "locked: printed tag")`; a move or a rename is allowed.

### 5.6 Validation, per field

Two layers, never mixed:

| Layer | Catches | Answer |
|---|---|---|
| the schema (pydantic in `server/`, the `TagSpec` dataclass in `plan/spec.py`) | a wrong TYPE: a string where a number goes, a missing required key, an unknown `schema` string | HTTP 422 / `TypeError` naming the key path. Never reaches `plan_tag` |
| `plan/spec.check(spec)` then `plan_tag` | a wrong VALUE: out of range, not a choice, does not fit | an `Issue(field, level, text)` in `TagPlan.warnings`; `ok` is false only for `error`. `plan_tag` never raises |

`Issue.field` is the key path into `TagSpec`. The table is the contract for `/api/form`, the inspector and the tests; limits are REF's constants, named so a builder copies the number from the core, not from here.

| Field | Type | Valid | Out of range says (level) |
|---|---|---|---|
| `settings.layout` | choice | `single` / `grid` / `charuco` (`board.LAYOUTS`) | error: unknown layout |
| `settings.dictionary` | choice | one of `dictionary.DICTIONARY_NAMES` (case-folded accepted) | error: unknown dictionary |
| `numbers.marker_id` | int | `0 <= id`, `id + count <= capacity` | error: outside the dictionary (names the capacity) |
| `numbers.size` | mm | `0` = Auto; else `> 0`; snapped / clamped by the fit | info: snapped or clamped, with the number (`autosize` notes) |
| `numbers.square` | mm | ChArUco only; `0` = Auto; else `> marker` (`board.check_spec`) | error: square must be larger than the marker |
| `settings.cols`, `rows` | int | `>= 1`; ChArUco `>= 2 x 2` (`board.check_spec`) | error: cv2 refuses it |
| `settings.quiet_modules` | modules | `>= 0.5`, `<= 3` | warn: below 1 reads worse; error above 3 |
| `settings.cells` | object or absent | `rule == 1`, `of` in `autosize.CELL_OF`, `MIN_STEP_M <= mm/1000 <= MAX_STEP_M`, `min_mm >= 0` | error: unknown cells rule (absent = legacy, no message) |
| `settings.mode`, `op` | choice | `slabs.MODES`, `slabs.OPS` | error |
| `numbers.white_offset`, `white_height`, `black_offset`, `black_height` | mm | `abs(v) <= slabs.LIMIT_MM`; a colour that is built has `abs(height) >= WHITE_MIN_MM` / `BLACK_MIN_MM` | error: a colour with no height; info: snapped (`slabs.snap_height`) |
| `settings.turn` | choice | `0 / 90 / 180 / 270` | error |
| `settings.origin_v` | `2` or absent | | info: a node made before 2026-10-09 keeps its orientation (`origin.effective` note) |
| `settings.corner_mark` | choice | `chamfer.CHOICES`; valid for the tag per `chamfer.valid_marks` | info: the other form instead (`Mark.instead`); warn: no mark, the border is too narrow |
| `settings.pin` | choice | `slabs.PIN_SHAPES`; only with a body under a New tile | info: pins need a body / a new tile (`slabs.pin_applies`) |
| `numbers.pin_size`, `pin_length`, `pin_tol` | mm | inside `slabs.PIN_LIMITS` | error: outside the limits; error: the pins do not fit (`pin_outlines` raises -> an Issue) |
| `settings.label.on` ... (every `LabelSettings` field) | per `LabelSettings` | `content` in `label.CONTENTS`, `place` / `row` / `side` / `scope` / `position` in their tuples, `cap_mm` `0` or `>= min_cap(nozzle)`, `nozzle_mm > 0`, `rule` in `label.RULES` | error / warn: each `label_violations` line with how much, on `settings.label`; info: the label was laid out as a preview (`build_anyway` builds it) |
| `settings.trim` | object or absent | `rule == 1`, `axes` in `trim.AXES`, `0 <= margin_mm <= MARGIN_MAX_MM` | error: each `TrimPlan.refusals` line (`force` overrides) |
| `target.w_mm`, `h_mm` | mm | `> 0` | error |
| `target.loops_mm` | polygons | each loop `>= 3` points, the first loop the outer, holes inside it; empty = the box | error: a loop with under 3 points; error: nothing fits (`autosize` refusal) |
| `target.body_mm` | box or null | `z1 > z0` when present | error |
| `name`, `key` | string | any; `key` unique in a scene | error (scene level): duplicate key |

Everything in `TagPlan.warnings` that REF's dialog said as an info line (`round_line`, `size_line`, `cells_line`, `layer_lines`, the Origin line) is an `Issue` of level `info` on its field. `core.validate.validate(spec, plan)` is the one function that turns the plan's notes into these Issues; the Fusion dialog and the Studio's inspector both call it.

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
