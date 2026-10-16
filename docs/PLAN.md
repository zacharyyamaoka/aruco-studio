# ArUco Studio: the build plan

Read `docs/BRIEF.md` and `docs/ARCHITECTURE.md` first. This file says who builds what, where, and how we know it is done.

| | |
|---|---|
| Written | 2026-10-16 |
| REF | `C:\Users\BAM\Documents\cad-exporter\.claude\worktrees\aruco-fusion-plugin-0e9bcb` at `c8216ff`, READ ONLY |
| ROOT | `C:\Users\BAM\Documents\aruco-studio`, branch `main`, local only |
| Toolchain | `C:\Users\BAM\miniconda3\python.exe` 3.11.5 -> `ROOT/.venv`; Node 26.8 / npm 11.19; PyPI and npm only, versions pinned |
| Ports | 5360 (API + built UI), 5361 (Vite dev). Never 5322, 5331, 5340, 5350, 8080. |

## 1. Module map

Every REF core module and every (C) responsibility of the add-in inventory, with its new home. Class: C = core logic, F = Fusion adapter, U = UI, T = test harness.

### 1.1 REF core (`CADExporter/bam_cad_core/`)

| REF | Lines | New home | Note |
|---|---:|---|---|
| `aruco_dict.py` + `aruco_dictionaries.json` | 237 + 44 | `aruco_studio/core/dictionary.py` + json | copied; the sha256 check kept |
| `aruco_board.py` | 343 | `core/board.py` | copied |
| `aruco_origin.py` | 166 | `core/origin.py` | copied; `ORIGIN_RULE = 2` |
| `aruco_slabs.py` | 442 | `core/slabs.py` | copied; `from_legacy` kept |
| `aruco_chamfer.py` | 374 | `core/chamfer.py` | copied; `choice_of` kept |
| `aruco_autosize.py` | 1,862 | `core/autosize.py` | copied; `CELL_RULE = 1`, `cells_of` |
| `aruco_label.py` | 3,149 | `core/label.py` | copied as ONE module; `RULES`, `RULE = 2` |
| `aruco_trim.py` | 470 | `core/trim.py` | copied; `RULE = 1` |
| `aruco_numbering.py` | 1,292 | `core/numbering.py` | copied; both schemas |
| `markers.py` (tag model half) | ~900 of 1,428 | `core/markers.py` | `TagSpec`, `TagDef`, `OccurrenceRef`, `OverrideRecord`, `TagInstance`, `Resolution`, `resolve`, `plan_serials`, `board_spec`, `detector_frame`, `cell_boxes`, `split_path`, `slot_key`, constants, `suggest` |
| `markers.py` (`fit_square`, `fit_board`, `largest_rect`, sidecar helpers) | ~500 | not ported | superseded by `autosize`; the sidecar is CAD Exporter's |
| `fiducials.py` (`ARUCO_DICTS`, `board_for_tube`) | ~80 of 617 | `core/dictionary.py` | the table and the tube rule only |
| `fiducials.py` (decal era) | ~540 | not ported | deferred with the decal path |
| `print_sheet.py` | 734 | `core/sheet.py` | copied |
| `print_beds.py` | 2,289 | `core/beds.py` | copied |

### 1.2 Pure (C) responsibilities of the add-in (`ArucoMarkers/`)

| REF file | (C) responsibility | New home |
|---|---|---|
| `aruco_feature.py` | `default_settings`, `size_is_auto`, `trim_setting`, `normalise`, `default_numbers`, `effective_op`, `resolve_follow`, `plan_of`, `structure`, `node_structure`, `is_legacy`, `cells_of`, `is_info`, `SPEC_VERSION` | `core/settings.py` |
| `aruco_feature.py` | `settle`, `keep_black_step`, `_merged`, `structural_change`, `edit_kind`, `_settings_key`, `_edit_changes`, `rebuild_reason` | `core/edits.py` |
| `aruco_feature.py` | `_v`..`_rotz`, `_xf_frame`, `_chain`, `_inside_loops`, `_is_box`, `_loops_mm` | `core/geometry.py` |
| `aruco_feature.py` | the numeric body of `evaluate()`, `_layout_rect`, `turns`, `keep_x`, `face_origin`, `mark_frame`, `_footprint`, `_trim_column`, `_trim_eval`, `_trim_not_in_place`, `trim_notes`, `optical_of_ev`, `_label_key` | `plan/plan.py` |
| `aruco_feature.py` | `record_same`, `frame_digest`, `ev_digest`, `record_digest`, `_same_label`, `x_ref_from_record`, `origin_of`, `mark_record`, `label_record`, `record_extras`, `_label` (node name), `node_warning` | `plan/record.py` |
| `aruco_feature.py` | `has_frame_sketch`, `follow_expression`, `_norm_expr`, `params_for`, `_mm_expr` | stays F: `adapters/fusion/feature.py` |
| `aruco_extrude_cmd.py` | `defaults`, `_base_from`, `_limits`, `label_defaults`, `values`, `resolve_mode`, `label_values`, `trim_values`, `_stored_label`, `_same_label_settings`, `same_build`, `_check_auto`, `preset_values`, `cells_values`, `_cells_for`, `_size_sig`, `_after_dictionary`, `_choice_of_cells`, `_cell_line_mm`, `_cells_labels` | `core/form.py` |
| `aruco_extrude_cmd.py` | `cells_line`, `layer_lines`, `_cell_warnings`, `label_entries`, `label_lines`, `info_rows`, `_edit_kind_line`, `_preset_lines`, `_mark_line`, `_pin_line`, `_mm_text`, `size_line`, `_origin_line`, `trim_lines`, `trim_issues` | `core/validate.py` (messages) |
| `aruco_extrude_ui.py` | `round_line`, `snap_size`, `_fit_key`, `json_key`, `_size_limit` | `core/form.py` |
| `aruco_extrude_ui.py` | `_level_of`, `info_lines`, `classify`, `_short_note`, `label_issues`, `trim_issues`, `collect`, `_visible_anchor`, `ok_text` | `core/validate.py` |
| `bam_fusion_ui.py` | `Issue`, `worst`, `head_of`, `summary_text`, `Validator` (the model, not the Fusion wiring) | `core/validate.py` |
| `aruco_presets.py` | everything but `load` / `save` | `core/presets.py` |
| `aruco_presets.py` | `load`, `save` (atomic), the file path | `server/store.py` |
| `aruco_prusa.py` | `read_ini`, `read_bundle`, `_system`, `resolve`, `length`, `nozzle_of`, `width_of`, `profile`, `aruco_profiles`, `describe` | `core/prusa.py` (on text) |
| `aruco_prusa.py` | `config_dir`, `user_prints` (the directory walk) | `server/store.py` |
| `aruco_preset_library.py` | `subtitle`, `lines_per_cell`, `cells_words`, `info`, `edit_schema`, `set_path`, `thumb_svg`, `_cells_from`, `same_print`, `group_nodes`, `Library` | `core/presets.py` |
| `aruco_preset_library.py` | `library_path`, `_load`, `_save`, `recent`, `add_recent`, `forget_recent` | `server/store.py` |
| `aruco_preset_library.py` | `preset_of_node`, `document_nodes` | stays F |
| `aruco_settings.py` | `_normalise`, `load`, `save`, `design_key`, `_merge`, `recall`, `remember`, `snapshot` | `server/store.py` (the Studio's own file under `ROOT/.data/`) |
| `aruco_settings.py` | `find_prusaslicer`, `open_in_prusaslicer` | `server/prusa_launch.py` (Windows; never called by tests) |
| `aruco_ui_config.py` | the UI switches | stays U (the Studio has its own settings in `studio/`) |
| `aruco_commands.py` | `_split_black`, `_export_info`, `eta_text`, `progress_message`, `_export_rows`, `_dup_rows`, `_export_status`, `_tick_part`, `_set_tick`, `_plural`, `_part_tip` | `core/export_rows.py` |
| `aruco_export.py` | `_slug`, `SLOTS`, `_labels`, `body_role`, `print_rows`, `tag_parts`, `KINDS`, the per-kind file rule | `core/export_rows.py` + `plan/exports.py` |
| `aruco_export_preview.py` | `row_for_path`, `_ids_text` | `core/export_rows.py` |
| `aruco_extrude_sync.py` | `doc_key`, `verdict`, `BUDGET_MS` | stays F: `adapters/fusion/sync.py` (the policy is `core.numbering.auto_decision`) |
| `aruco_ids_cmd.py` | `_how`, `_tone`, `_status_cell`, `_marker_rows` | `core/marker_table.py` |
| `aruco_ids_feature.py` | `Labels`, `_variant_info`, `read_ledger` (parse), `stamp_chains`, `resolve_hidden`, `plan_design`, `_drift`, `_body_sig`, `staleness`, `auto_verdict`, `_warning_text`, `export_overrides`, `node_state`, `_unique_name` | `core/ids_design.py` over `AssemblySnapshot` |
| `aruco_ids_feature.py` | `part_plan`, `id_regions`, `label_slots`, `label_warning`, `part_paint_plan`, `_part_label` | `plan/variants.py` (the paint plan's region split; the paint itself stays F) |
| `aruco_ids_preview.py` | `_cols`, `_add_box`, `spec_of`, `specs_of`, `marker_row` | `plan/mesh.py`, `core/marker_table.py` |
| `aruco_marker_table.py` | `name_of`, `split_name`, `natural_key`, `family`, `where`, `kind_text`, `dict_text`, `ids_text`, `status_html`, `MarkerRow`, `spec_info`, `make_row`, `_frame`, `frame_of_matrix`, `order`, `duplicates`, `ratio`, `column`, `cell_id` | `core/marker_table.py` |
| `aruco_marker_table.py` | `double_click_s`, `message_ms`, `click`, `busy`, `match_pick`, `view_for`, `inside_box`, the `nav_*` state machine, `handle`, `follow_table`, `pick_path` | U: re-done in TypeScript in `studio/src/table/`; the Python stays with the Fusion adapter's UI |
| `aruco_preview.py` | `boxes`, `label_boxes`, `_label_strokes`, `label_warning`, `label_guides`, `mark_prisms`, `pin_prisms`, `triad`, `trim_boxes`, `_add_box`, `_add_prism`, `_mark_kind`, `_cells_z`, `_top_cm` | `plan/layers.py` (they ARE the layers) + `plan/mesh.py` |
| `aruco_restructure.py` | `has_combine`, `restructure_plan`, `new_parts`, `needed_params`, `refusal`, `lost_after`, `what_goes` | stays F, pure half: `adapters/fusion/restructure.py` (tested on the fake) |
| `aruco_tags.py` | `_v`..`_rot` (Rodrigues), `_area2`, `_frame_error`, `_solve3` | `core/geometry.py` |
| `aruco_tags.py` | `mark_parts`, `label_of`, `label_joins`, `label_white_rect`, `label_fill_rects`, `copy_label` | `plan/layers.py`, `plan/variants.py` |
| `aruco_tags.py` | `is_variant_record`, `template_records`, `label_settings_same`, `_in_label`, `_footprint_cm`, `_extents`, `_is_white`, `_body_sig`, `_sources_sig`, `_variant_name`, `summary`, `optical_frame_cm`, `has_old_frame` | `plan/record.py` |
| `aruco_tags.py` | `_jo_key`, the composition maths of `_place_joint_origin` | stays F: `adapters/fusion/joint_origin.py` (pure maths tested on the fake) |
| `aruco_autosize_gallery.py` | `FACES`, `TYPED`, `shape_pts`, `loops_mm`, `loops_m`, `bbox_mm`, `summary` | T: `tests/fixtures/faces.py` |
| `resources/preset_library/*` (HTML) | the cards, filters, Select / New / Duplicate / Edit / Delete / Import | U: `studio/src/library/` (React); `bam_channel.js` is Fusion's and stays |

### 1.3 What stays where

| Class | Stays in | Examples |
|---|---|---|
| F | `adapters/fusion/` (REF's `aruco_feature`, `aruco_tags`, `aruco_ids_feature`, `aruco_restructure`, `aruco_extrude_sync`, `aruco_export`'s Fusion half, `aruco_core`) | selections, sketches, TBM bodies, combines, the custom feature, Joint Origins, joints, occurrences, appearances, documents, hot reload |
| U | the Fusion dialogs stay with the adapter (`aruco_extrude_cmd`, `aruco_extrude_ui`, `aruco_ids_cmd`, `aruco_commands`, `bam_fusion_ui`, the ghosts); the Studio has its own UI in `studio/` | dialog rows, manipulators, palettes, custom graphics |
| T | REF's labs, gates, bridge, probes and fixtures are NOT copied. They test Fusion, and Fusion is out of scope here. | `aruco_actions`, `aruco_bridge`, `aruco_ids_accept`, `aruco_edit_gates`, every `*_lab.py` |

## 2. Milestones

Each milestone is built by ONE agent. M1 then M2 run in sequence. M3 and M4 run IN PARALLEL after M2 and own disjoint paths. No milestone edits another's paths. Shared files (`docs/spec.json`, `tools/check.py`, `requirements.txt`) have one owner per milestone, named below; the others ask through `docs/status/<M>.md`.

Common rules for every builder:

| Rule | |
|---|---|
| Commit small, in ROOT, on `main`. Never add a remote, never push. | |
| Never write into REF. Read with the Read tool or `git -C <REF> show c8216ff:<path>`. | |
| Never touch Fusion: no bridge, no `%USERPROFILE%\CADExporter\_aruco_bridge`, no computer use, no starting or stopping Fusion. | |
| Never write under `%USERPROFILE%\CADExporter`. Tests set `USERPROFILE` to a temp dir and `ARUCO_STUDIO_HOME` to a temp dir. | |
| Run REF code only read-only: `PYTHONDONTWRITEBYTECODE=1`, `USERPROFILE=<temp>`, `BAM_ARUCO_PRUSASLICER_DIR=<REF>/tests/fixtures/prusaslicer`, and `sys.path` pointing INTO REF. Check `git -C <REF> status --porcelain` is unchanged before and after. | |
| Stop every server and background process before finishing. | |
| Write `docs/status/<M>.md` at the end: what is done, what is not, the numbers, the exact commands. Short sentences, tables. | |

### M1: core port + golden equivalence

| | |
|---|---|
| Goal | `aruco_studio/core/` runs REF's Fusion-free logic bit for bit, proven by goldens that REF's own code produced. |
| Owner paths | `aruco_studio/__init__.py`, `aruco_studio/core/**`, `goldens/**`, `tools/ref_path.py`, `tools/make_goldens_from_ref.py`, `tools/check.py`, `tests/conftest.py`, `tests/core/**`, `tests/fixtures/**`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `docs/status/M1.md`, `docs/test_trace.md` |
| Does not touch | `aruco_studio/plan/**`, `scene/**`, `verify/**`, `server/**`, `adapters/**`, `studio/**`, `docs/spec.json` |

Steps:

1. `.venv` from miniconda's Python; `requirements.txt` pinned (`pytest`, `pytest-xdist`); `pyproject.toml` with `[tool.pytest.ini_options] testpaths = ["tests"]`.
2. Port the modules of table 1.1 and the `core/` rows of table 1.2. Copy first, rename imports second, change nothing else. Keep every public name, constant and docstring. `core/settings.py` and `core/edits.py` are lifted from `aruco_feature.py` with their adsk-free bodies only.
3. Goldens, made by `tools/make_goldens_from_ref.py` running REF's code read-only into `goldens/`:
   - copy verbatim: `aruco_cells_legacy_golden.json`, `aruco_label_rule1_golden.json`, `aruco_trim_legacy_golden.json`, `aruco_label_gim43_disc.json`, `prusaslicer/print/*.ini`;
   - new, from REF's core: `dictionary.json` (every id of every dictionary: grid hash, `black_rects`), `board.json` (counts, ids, extents, object points, `opencv_frame` for every layout x a size table), `origin.json` (every layout x turn x cols / rows, both rules), `slabs.json` (288 plans + `from_legacy` over a grid), `chamfer.json` (every layout x mode x op x want x rows / legacy), `autosize.json` (the ten gallery faces x layouts x cells rules), `label.json` (200 `plan_label` cases, both rules), `trim.json` (400 random plates), `numbering.json` (the F1..F11 models), `presets.json` (`normalise`, `from_profile` on the fixture), `prusa.json` (the fixture profiles), `settings.json` (`default_settings`, `normalise` of every generation's shape), `form.json` (`values` / `snap_size` / `round_line` over a grid);
   - each golden records `ref_commit: "c8216ff"`, the maker's arguments and the REF module's sha256.
4. Replay every golden through the new core in `tests/core/test_golden_*.py`: exact equality for ints, strings and lists; floats exact where REF's test is exact (cells, trim), else 1e-6.
5. Port the pure assertions of REF's 17 Fusion-free suites to pytest with traceable names (section 3.2). `test_aruco_label_print` and `test_aruco_frame`'s URDF half are out of scope (other venvs); note them.
6. `tools/check.py`: runs pytest and prints one summary line per group. Later milestones add their groups to it (M2 owns the file after M1).

Done checks (measured):

| # | Check | Bar |
|---|---|---|
| M1.1 | `.venv/Scripts/python -c "import aruco_studio.core"` imports with only the stdlib loaded (`sys.modules` has no numpy, cv2, adsk) | true |
| M1.2 | `grep -r "adsk\|numpy\|cv2" aruco_studio/core` | no hits |
| M1.3 | `pytest tests/core` | green; at least 17 ported suites, each with a `REF:` marker |
| M1.4 | cells golden: 511 sizings exact (floats too) + 12 `evaluate()` cases parked for M2 | 511 / 511 |
| M1.5 | label rule-1 golden: 36 labels identical to 1e-6 mm, and the same settings under rule 2 move | 36 / 36 |
| M1.6 | trim golden: 288 `slabs.plan` + `default_settings()` exact; 26 `evaluate()` cases parked for M2 | 288 / 288 |
| M1.7 | the new goldens of step 3 replay exactly | every file, 0 mismatches |
| M1.8 | `docs/test_trace.md` lists every section of the 17 REF suites with its pytest node id | 100 % of sections |
| M1.9 | `git -C <REF> status --porcelain` identical before and after the golden run | identical |
| M1.10 | `tools/check.py` exits 0 in under 120 s | true |

### M2: plan + scene + verify + exports + server

| | |
|---|---|
| Goal | `plan_tag` replays REF's `evaluate()` goldens; a scene holds many tags and renumbers; OpenCV reads every plan; files export; the API serves it all on 5360. |
| Owner paths | `aruco_studio/plan/**`, `scene/**`, `verify/**`, `server/**`, `goldens/evaluate/**`, `tools/make_evaluate_goldens.py`, `tools/check.py`, `tests/plan/**`, `tests/scene/**`, `tests/verify/**`, `tests/server/**`, `requirements.txt`, `docs/status/M2.md`, `docs/API.md` |
| May edit | `aruco_studio/core/**` only to fix a port bug, with the golden that caught it |
| Does not touch | `studio/**`, `adapters/**`, `docs/spec.json` |

Steps:

1. `plan/target.py`, `plan/spec.py`, `plan/layers.py`, `plan/plan.py` as in ARCHITECTURE 3.2 and 5.1-5.3. `plan_tag` follows `evaluate()`'s order exactly.
2. `goldens/evaluate/*.json` by `tools/make_evaluate_goldens.py`: REF's `aruco_feature.evaluate()` on REF's stand-in adsk (the pattern of `tools/make_cells_legacy_golden.py` and `make_trim_legacy_golden.py`, plus `tests/aruco_trim_fixtures.py`), over a matrix: 3 layouts x 3 modes x 2 ops x 4 turns x 3 marks x label off / on-black / on-white x pins none / triangle / round x trim off / both, on the box faces and the loop shapes those makers define, Auto and typed sizes, cells legacy / cell 0.68 / marker 0.5. At least 600 cases. Each case stores the inputs as a `TagSpec` and the outputs: `spec.to_dict()`, `layout`, `plan.parts`, the slabs, `mark`, `label`, `pins` (mm), `trim`, `notes`, `turn`, `x_fit`, and the tile rectangle in mm. The 12 + 26 existing `evaluate()` golden cases join this set.
3. `tests/plan/test_golden_evaluate.py` replays all of it through `plan_tag`.
4. `plan/record.py`, `plan/variants.py`, `plan/mesh.py`, `plan/exports.py` (SVG, PNG, STL; the PDF through `core.sheet`; 3MF through `core.beds`).
5. `scene/` with the file format and renumbering through `core.numbering.plan_stable` on an `AssemblySnapshot` built from the scene; the ledger kept in the file.
6. `verify/` with `numpy` and `opencv-python-headless` pinned.
7. `server/` with `fastapi`, `uvicorn`, `pydantic` pinned; `docs/API.md` from the routes.
8. `tools/check.py` gains `plan`, `scene`, `verify`, `server` groups.

Done checks:

| # | Check | Bar |
|---|---|---|
| M2.1 | the 12 cells + 26 trim `evaluate()` golden cases replay through `plan_tag` | 38 / 38 exact on `spec`, `parts`, `mark`, `label`, `trim`, `notes` |
| M2.2 | `goldens/evaluate/` cases replay | >= 600 cases, 0 mismatches at 1e-6 mm |
| M2.3 | `plan_tag` never raises: 2,000 random `TagSpec`s (fuzz) | 0 exceptions; every `ok == False` has an `errors` entry |
| M2.4 | every layer polygon lies inside the tile (or the target for cuts); `pattern` ink equals `cell_boxes` cell for cell | every case |
| M2.5 | verify: every layout x 4 turns x mark off / on x label off / on, rendered from the plan at 20 px / mm | every id read; grid / ChArUco detected as a board; PnP within 0.1 mm / 0.1 deg of `frames.opencv` |
| M2.6 | scene: 40 tags (mixed layouts, two dictionaries) renumbered | no duplicate id per family; boards contiguous; a second renumber changes nothing; a printed id never moves after add / delete / rename (REF G0.7 scenarios on the scene) |
| M2.7 | `.arucostudio.json` round trip | `loads(dumps(s)) == s` for 100 random scenes |
| M2.8 | exports: SVG parses; PNG decodes to every id; STL is watertight per layer; the PDF sheet places every tag at true size (REF `test_aruco_output` checks) | every check |
| M2.9 | server: `uvicorn` on 127.0.0.1:5360 answers `/api/health`; every route has a test with the request / response schema | 200 on every route; schema validated |
| M2.10 | `tools/check.py` exits 0; every server started by a test is stopped (`netstat -ano \| findstr 5360` empty after) | true |

### M3: the Studio web app + Playwright e2e

| | |
|---|---|
| Goal | the 2D canvas and 3D view on the real API; screenshots prove it. |
| Owner paths | `studio/**` (its own `package.json`, `vite.config.ts`, `playwright.config.ts`, `src/**`, `e2e/**`), `reports/e2e/**`, `docs/status/M3.md`, `docs/STUDIO.md` |
| May edit | `aruco_studio/server/app.py` only to serve `studio/dist` and add CORS for 5361; `tools/check.py` only to add the `studio` group (one function, appended) |
| Does not touch | `aruco_studio/core/**`, `plan/**`, `scene/**`, `verify/**`, `adapters/**`, `tests/**`, `docs/spec.json` |

Steps:

1. `npm create vite@latest` (React + TS) in `studio/`; dependencies pinned: `react`, `react-dom`, `zustand`, `three`, `@types/three`, `@playwright/test`, `vitest`. No UI kit beyond plain CSS.
2. Types in `studio/src/api/types.ts` generated from the server's OpenAPI (`/openapi.json`) with `openapi-typescript` (pinned), so `TagPlan` and `Issue` are the same on both sides.
3. The 2D canvas (SVG): pan, zoom, select, drag with 0.5 mm snap, rulers in mm, a tag drawn from its layers; multiple tags; add from a palette (single / grid / ChArUco).
4. The inspector from `core.form`'s field list (fetched from `/api/form` if M2 exposes it, else written by hand from `docs/ARCHITECTURE.md` 5.2); `/api/validate` messages under each field; `/api/candidates` as the Layout list.
5. The 3D view (three.js) with the 2D / 3D toggle keeping the view centre; layers extruded; the OpenCV frame drawn as a triad.
6. The IDs table and Renumber; the Library (presets); Export buttons; Verify with the report shown.
7. Playwright e2e against `uvicorn` on 5360 + Vite on 5361, screenshots into `reports/e2e/<test>.png`.
8. `docs/STUDIO.md`: how to run, what each view shows, the keyboard map.

Done checks:

| # | Check | Bar |
|---|---|---|
| M3.1 | `npm run build` in `studio/` | exit 0, no TS errors |
| M3.2 | `npm run test` (vitest) | green; the store's reducers covered |
| M3.3 | Playwright: open the app, add a single marker, a 4x3 grid and a 5x7 ChArUco | 3 tags on the canvas; their ids come from `/api/plan` |
| M3.4 | Playwright: type size 28 on a 40 mm target, switch cells to "cell 0.68" | the inspector shows the plan's `round_line`; the SVG path count changes |
| M3.5 | Playwright: toggle 2D -> 3D -> 2D | the canvas centre is unchanged within 1 px; a screenshot of each |
| M3.6 | Playwright: label on, on the white, below; then move it into the quiet ring | an `Issue` appears under the Label field; the preview draws orange |
| M3.7 | Playwright: Renumber with 6 tags of one family | the table shows unique ids; a second Renumber changes nothing |
| M3.8 | Playwright: save the scene, reload the page, open it | the same tags at the same places |
| M3.9 | Playwright: Export SVG and PDF; Verify | files exist; the verify report shows every id read |
| M3.10 | screenshots in `reports/e2e/` | >= 10 PNGs named by test |
| M3.11 | every dev server stopped at the end (`netstat -ano \| findstr "5360 5361"` empty) | true |

### M4: the Fusion adapter skeleton + the migration map

| | |
|---|---|
| Goal | `TagPlan` -> Fusion calls, proven against a fake adsk; the map that moves the live add-in to the new core later. Not installed into Fusion. |
| Owner paths | `aruco_studio/adapters/**`, `tests/adapters/**`, `docs/MIGRATION.md`, `docs/status/M4.md` |
| May edit | `tools/check.py` only to add the `adapters` group (one function, appended) |
| Does not touch | `aruco_studio/core/**`, `plan/**`, `scene/**`, `verify/**`, `server/**`, `studio/**`, `docs/spec.json` |

Steps:

1. `adapters/fusion/fake_adsk.py`: a recording stand-in built from REF `tests/aruco_trim_fixtures.py` and `tests/aruco_ui_stubs.py` (read, not copied wholesale): `TemporaryBRepManager` boxes and prisms as CSG stand-ins (REF `test_aruco_chamfer_bodies` has one), `customFeatures`, `BaseFeature`, `JointOrigin`, `Sketch`, `Attributes`. Every call is appended to a log.
2. `adapters/fusion/target.py`: a fake face / profile -> `Target`.
3. `adapters/fusion/build.py`: every `Layer` -> a temporary body; `op` -> join / cut / intersect; `parts` order kept.
4. `adapters/fusion/records.py`: `plan/record.py`'s dict + the adapter's handles; a REF record read back gives the same `TagSpec` (`plan/spec.from_record`).
5. `adapters/fusion/joint_origin.py`: the composition maths of `_place_joint_origin` (angle, offsets, flip from a frame; read-back check).
6. `adapters/fusion/feature.py`: create / compute / edit outlines calling 2-5; `restructure.py` with `restructure_plan` ported and tested over every pair of structures (REF `test_aruco_extrude_sync`'s cases).
7. `docs/MIGRATION.md`: every (F) responsibility of REF's add-in -> which adapter module and which plan field replaces it; every REF Fusion quirk (inventory "Fusion 2705 behaviours") -> where the adapter honours it; the switch-over steps for the live add-in (a later, Fusion-gated run) with the golden gates that must stay green.

Done checks:

| # | Check | Bar |
|---|---|---|
| M4.1 | `pytest tests/adapters` on the fake adsk | green |
| M4.2 | every `evaluate()` golden case built through `build.py` on the fake | the body log has one body per `Layer`, z ranges equal the layer's `z`, in `parts` order |
| M4.3 | the fake's CSG probe at the mark, the label strokes and the pins (REF `test_aruco_chamfer_bodies`, `test_aruco_label_bodies`) | every probed point in the expected colour |
| M4.4 | `from_record` on the records inside the cells / trim goldens | the `TagSpec` replans to the same plan |
| M4.5 | Joint Origin maths: 200 random frames -> (angle, offsets, flip) -> frame | 1e-6 mm / 1e-6 deg |
| M4.6 | `restructure_plan` over every pair of node structures | the REF cases' delete / create roles equal |
| M4.7 | `docs/MIGRATION.md` maps every (F) line group of `docs/inventory/addin.md` and every quirk table row | 100 % of rows |
| M4.8 | nothing imported `adsk` for real: `python -c "import aruco_studio.adapters.fusion"` outside Fusion raises a clear `RuntimeError` naming the fake | true |

## 3. Test strategy

### 3.1 Layers

| Layer | Tool | Where | What |
|---|---|---|---|
| core / plan / scene / verify / server | pytest 8, `pytest-xdist` | `tests/<layer>/` | unit tests, goldens, fuzz |
| adapters | pytest on `fake_adsk` | `tests/adapters/` | call logs, CSG probes |
| studio | vitest | `studio/src/**/*.test.ts` | store, geometry helpers |
| end to end | Playwright | `studio/e2e/` | the real server + the real UI, screenshots |

### 3.2 Ported assertions with traceable names

Every pytest function ported from a REF suite carries the REF suite and section in its name and a marker:

```python
@pytest.mark.ref("tests/test_aruco_chamfer.py", "EX-MARK-1: which mark each layout x mode x op gets")
def test_chamfer__ex_mark_1__which_mark_per_layout_mode_op(): ...
```

`docs/test_trace.md` is generated by `tools/check.py --trace`: one row per REF suite section (REF suite, section, pytest node id, the REF spec test ids it covers). The REF spec test ids (`EX-MARK-1`, `G0.3`, ...) appear verbatim so `docs/spec.json` can point at them.

### 3.3 Goldens

| Rule | |
|---|---|
| A golden is made ONLY by REF's code at `c8216ff`, run read-only from `tools/make_*_goldens*.py`. Never by the new code. | |
| Each golden file carries `ref_commit`, the REF module sha256, the maker's arguments and the date. | |
| A golden test compares exactly unless REF's own test used a tolerance; then the same tolerance. | |
| A failing golden is a port bug until proven otherwise. Changing a golden needs a note in `docs/status/<M>.md` with the REF line that explains the difference. | |

### 3.4 One command

`tools/check.py` (Python, so it runs the same from Git Bash and PowerShell):

```
.venv/Scripts/python tools/check.py            # everything
.venv/Scripts/python tools/check.py core plan  # some groups
.venv/Scripts/python tools/check.py --trace    # rewrite docs/test_trace.md
```

Groups: `core`, `plan`, `scene`, `verify`, `server`, `adapters`, `studio` (vitest + build), `e2e` (Playwright; starts 5360 and 5361, stops them in `finally`). It prints one line per group (`core: 2,311 passed in 38 s`) and exits non-zero on any failure. It refuses to run `e2e` if 5360 or 5361 is already bound.

## 4. Definition of Done for this run

| # | Check | How measured |
|---|---|---|
| D1 | `tools/check.py` exits 0 with every group | the summary lines, pasted into `docs/status/RUN.md` |
| D2 | the four REF goldens replay bit for bit: cells 511 + 12, label 36, trim 26 + 288 | the four golden tests green, counts printed |
| D3 | >= 600 `evaluate()` cases from REF replay through `plan_tag` | M2.2 |
| D4 | `docs/test_trace.md` covers 100 % of the 17 Fusion-free REF suites' sections | `tools/check.py --trace` prints `missing: 0` |
| D5 | `aruco_studio/core` and `plan` import only the stdlib | M1.1, M1.2 |
| D6 | OpenCV reads every id off every rendered plan; PnP within 0.1 mm / 0.1 deg | M2.5 |
| D7 | a scene of 40 tags renumbers uniquely and stably; printed ids never move | M2.6 |
| D8 | the Studio builds and >= 8 Playwright tests pass with >= 10 screenshots | M3.1-M3.10 |
| D9 | the Fusion adapter skeleton builds every golden case on the fake, one body per layer | M4.2 |
| D10 | `docs/MIGRATION.md` maps every (F) responsibility and every quirk | M4.7 |
| D11 | `docs/spec.json` statuses updated: every feature and test either `built` / `passing` with its check, or still `planned` with a reason | `tools/spec_status.py` renders `reports/spec.html` and lists the planned ones |
| D12 | nothing written into REF, `%USERPROFILE%\CADExporter`, or Fusion; no server left on 5360 / 5361 | `git -C <REF> status --porcelain` unchanged; `netstat` empty; the orchestrator checks |
| D13 | every commit on ROOT `main`, local only | `git remote -v` empty |

## 5. Deferred, explicitly

| Item | Why not now | When |
|---|---|---|
| Switching Zach's live Fusion add-in to the new core | needs Fusion open, the edit gates re-run, and his OK; the live add-in loads from REF | a later, Fusion-gated run, following `docs/MIGRATION.md` |
| build123d adapter | the plan contract must settle first; build123d is not in any venv here | after M2 is stable |
| viser adapter | same; viser lives on the Linux box | after M2 is stable |
| A domain (arucostudio.com) or any website | out of scope; local only | Zach decides |
| A GitHub repository or remote | local only this run | Zach decides |
| `fiducials.py`'s decal path | superseded by true geometry | not planned |
| `test_aruco_label_print` (PrusaSlicer slicing oracle), `test_aruco_frame`'s URDF half | need the clank / smart_sign venvs and PrusaSlicer | after the venv question is settled |
| "forget retired ids", the ChArUco screw-hole check, the Hamming-distance check, the sheet's `id_text` / `orient_corner` / `emboss_id` (inventory gaps 1, 2, 6, 7) | new behaviour, not a port; `docs/spec.json` lists them as `planned` features | after the Studio exists |
