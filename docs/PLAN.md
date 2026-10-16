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
| `aruco_preset_library.py` | `preset_of_node`'s mapping (settings + numbers -> a preset) | `core/presets.py` as `preset_of(settings, numbers)` |
| `aruco_preset_library.py` | `preset_of_node`'s read of the node, `document_nodes` | stays F: `adapters/fusion/records.py` |
| `aruco_settings.py` | `_normalise`, `load`, `save`, `design_key`, `_merge`, `recall`, `remember`, `snapshot` | `server/store.py` (the Studio's own file under `ROOT/.data/`) |
| `aruco_settings.py` | `find_prusaslicer`, `open_in_prusaslicer` | `server/prusa_launch.py` (Windows; never called by tests) |
| `aruco_ui_config.py` | the UI switches | stays U (the Studio has its own settings in `studio/`) |
| `aruco_commands.py` | `_split_black`, `_export_info`, `eta_text`, `progress_message`, `_export_rows`, `_dup_rows`, `_export_status`, `_tick_part`, `_set_tick`, `_plural`, `_part_tip` | `core/export_rows.py` |
| `aruco_export.py` | `_slug`, `SLOTS`, `_labels`, `print_rows`, `tag_parts`, `KINDS`, the per-kind file rule | `core/export_rows.py` + `plan/exports.py` |
| `aruco_export.py` | `body_role` (cells or tile from a Fusion body's NAME) | stays F: `adapters/fusion/records.py` |
| `aruco_export_preview.py` | `row_for_path`, `_ids_text` | `core/export_rows.py` |
| `aruco_extrude_sync.py` | `verdict` (pure: what the after-compute check concluded), `BUDGET_MS` | `core/edits.py` (next to `core.numbering.auto_decision`, the policy) |
| `aruco_extrude_sync.py` | `doc_key` and the hooks | stays F: `adapters/fusion/sync.py` |
| `aruco_ids_cmd.py` | `_how`, `_tone`, `_status_cell`, `_marker_rows` | `core/marker_table.py` |
| `aruco_ids_feature.py` | `Labels`, `_variant_info`, `read_ledger` (parse), `stamp_chains`, `resolve_hidden`, `plan_design`, `_drift`, `_body_sig`, `staleness`, `auto_verdict`, `_warning_text`, `export_overrides`, `node_state`, `_unique_name` | `core/ids_design.py` over `AssemblySnapshot` |
| `aruco_ids_feature.py` | `part_plan`, `id_regions`, `label_slots`, `label_warning`, `part_paint_plan`, `_part_label` | `plan/variants.py` (the paint plan's region split; the paint itself stays F) |
| `aruco_ids_preview.py` | `_cols`, `_add_box`, `spec_of`, `specs_of`, `marker_row` | `plan/mesh.py`, `core/marker_table.py` |
| `aruco_marker_table.py` | `name_of`, `split_name`, `natural_key`, `family`, `where`, `kind_text`, `dict_text`, `ids_text`, `status_html`, `MarkerRow`, `spec_info`, `make_row`, `_frame`, `frame_of_matrix`, `order`, `duplicates`, `ratio`, `column`, `cell_id` | `core/marker_table.py` |
| `aruco_marker_table.py` | `double_click_s`, `message_ms`, `click`, `busy`, `match_pick`, `view_for`, `inside_box`, the `nav_*` state machine, `handle`, `follow_table`, `pick_path` | U: re-done in TypeScript in `studio/src/table/`; the Python stays with the Fusion adapter's UI |
| `aruco_preview.py` | `boxes`, `label_boxes`, `_label_strokes`, `label_warning`, `label_guides`, `mark_prisms`, `pin_prisms`, `triad`, `trim_boxes`, `_add_box`, `_add_prism`, `_mark_kind`, `_cells_z`, `_top_cm` | `plan/layers.py` (they ARE the layers) + `plan/mesh.py` |
| `aruco_restructure.py` | `has_combine`, `restructure_plan`, `new_parts`, `needed_params`, `refusal`, `lost_after`, `what_goes` | `core/restructure.py` (pure; golden from REF `test_aruco_extrude_sync` section 4, ported in M1) |
| `aruco_restructure.py` | `restructure`, `node_roles`, `_regroup`, `_refs`, `node_bodies`, `dependents_of`, `downstream_snapshot` | stays F: `adapters/fusion/restructure.py` |
| `aruco_tags.py` | `_v`..`_rot` (Rodrigues), `_area2`, `_frame_error`, `_solve3` | `core/geometry.py` |
| `aruco_tags.py` | `mark_parts`, `label_of`, `label_joins`, `label_white_rect`, `label_fill_rects`, `copy_label` | `plan/layers.py`, `plan/variants.py` |
| `aruco_tags.py` | `is_variant_record`, `template_records`, `label_settings_same`, `_in_label`, `_footprint_cm`, `_extents`, `_is_white`, `_body_sig`, `_sources_sig`, `_variant_name`, `summary`, `optical_frame_cm`, `has_old_frame` | `plan/record.py` |
| `aruco_tags.py` | the composition maths of `_place_joint_origin` (frame <-> angle, offsets, flip) | `core/geometry.py` as `jo_decompose` / `jo_compose` (pure; 200 random frames round-trip in `tests/core`) |
| `aruco_tags.py` | `_jo_key`, the placing, read-back and one-per-tag bookkeeping | stays F: `adapters/fusion/joint_origin.py` |
| `aruco_autosize_gallery.py` | `FACES`, `TYPED`, `shape_pts`, `loops_mm`, `loops_m`, `bbox_mm`, `summary` | `core/faces.py` (product data: the Studio's target palette; the tests import the same list) |
| `resources/preset_library/*` (HTML) | the cards, filters, Select / New / Duplicate / Edit / Delete / Import | U: `studio/src/library/` (React); `bam_channel.js` is Fusion's and stays |

### 1.3 What stays where

| Class | Stays in | Examples |
|---|---|---|
| F | `adapters/fusion/` (REF's `aruco_feature`, `aruco_tags`, `aruco_ids_feature`, `aruco_restructure`, `aruco_extrude_sync`, `aruco_export`'s Fusion half, `aruco_core`) | selections, sketches, TBM bodies, combines, the custom feature, Joint Origins, joints, occurrences, appearances, documents, hot reload |
| U | the Fusion dialogs stay with the adapter (`aruco_extrude_cmd`, `aruco_extrude_ui`, `aruco_ids_cmd`, `aruco_commands`, `bam_fusion_ui`, the ghosts); the Studio has its own UI in `studio/` | dialog rows, manipulators, palettes, custom graphics |
| T | REF's labs, gates, bridge, probes and fixtures are NOT copied. They test Fusion, and Fusion is out of scope here. | `aruco_actions`, `aruco_bridge`, `aruco_ids_accept`, `aruco_edit_gates`, every `*_lab.py` |

## 2. Milestones

Each milestone is built by ONE agent. The order:

```
M1 (core port) -> M2 (plan) -> { M2b (scene, verify, exports, server)  |  M4 (Fusion adapter) }  -> M3 (web app) -> M5 (library, polish)
                                        in parallel, disjoint paths
```

M3 needs M2b's server. M4 needs only M2's `plan/`, so it runs beside M2b. No milestone edits another's paths. `docs/spec.json` is the orchestrator's: after each milestone it sets statuses from `docs/status/<M>.md`. `requirements.txt` passes from M1 to M2 to M2b in order. `tools/check.py` is written once by M1 and discovers its groups (section 3.4), so nobody else edits it.

Common rules for every builder:

| Rule | |
|---|---|
| Commit small, in ROOT. Never add a remote, never push. | |
| A milestone that runs beside another (M2b, M4) works in its own git worktree of ROOT (`git worktree add ../aruco-studio-<M> -b <M>` from ROOT) and commits there; the orchestrator fast-forward merges each branch into `main` when it is done, in the order they finish. A milestone that runs alone works on `main` in ROOT. | two agents in one working tree on one branch collide on the index and on each other's untracked files |
| Stage by path: `git add <your paths>`. Never `git add -A`, `git add .` or `git commit -a`. | |
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
| Owner paths | `aruco_studio/__init__.py`, `aruco_studio/core/**`, `goldens/**`, `tools/ref_path.py`, `tools/make_goldens_from_ref.py`, `tools/ref_sections.py`, `tools/check.py`, `tools/spec_status.py`, `tests/conftest.py`, `tests/core/**`, `tests/ref_sections.json`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `docs/status/M1.md`, `docs/test_trace.md` |
| Does not touch | `aruco_studio/plan/**`, `scene/**`, `verify/**`, `server/**`, `adapters/**`, `studio/**`, `docs/spec.json` |

Steps:

1. `.venv` from miniconda's Python; `requirements.txt` pinned (`pytest`, `pytest-xdist`); `pyproject.toml` with `[tool.pytest.ini_options] testpaths = ["tests"]`.
2. Port the modules of table 1.1 and the `core/` rows of table 1.2 (`core/restructure.py`, `core/faces.py` and the Joint Origin maths in `core/geometry.py` included). Copy first, rename imports second, change nothing else. Keep every public name, constant and docstring. `core/settings.py` and `core/edits.py` are lifted from `aruco_feature.py` with their adsk-free bodies only.
3. Goldens, made by `tools/make_goldens_from_ref.py` running REF's code read-only into `goldens/`:
   - copy verbatim: `aruco_cells_legacy_golden.json`, `aruco_label_rule1_golden.json`, `aruco_trim_legacy_golden.json`, `aruco_label_gim43_disc.json`, `prusaslicer/print/*.ini`. These keep their own maker commit (196454c, 8473e14, 5cf71bd) in their `code` field; the wrapper adds `ref_commit: "c8216ff"` as the commit they were copied from;
   - new, from REF's core: `dictionary.json` (every id of every dictionary: grid hash, `black_rects`), `board.json` (counts, ids, extents, object points, `opencv_frame` for every layout x a size table), `origin.json` (every layout x turn x cols / rows, both rules), `slabs.json` (288 plans + `from_legacy` over a grid), `chamfer.json` (every layout x mode x op x want x rows / legacy), `autosize.json` (the ten gallery faces x layouts x cells rules), `label.json` (200 `plan_label` cases, both rules), `trim.json` (400 random plates), `numbering.json` (the F1..F11 models), `restructure.json` (`restructure_plan` over every pair of structures, REF `test_aruco_extrude_sync` section 4), `jo_maths.json` (200 frames -> angle, offsets, flip by REF's `_place_joint_origin` maths), `presets.json` (`normalise`, `from_profile`, `preset_of_node`'s mapping on the fixture);
   - new, from REF's ADD-IN on its stand-in `adsk` (`tests/aruco_ui_stubs.py`, the way `make_cells_legacy_golden.py` does it; these modules import `adsk`): `settings.json` (`default_settings`, `normalise` of every generation's shape, `edit_kind` over 72 settings x 2 layouts), `form.json` (`values` / `snap_size` / `round_line` / `size_line` / `cells_line` / `trim_issues` over a grid of dialog values), `prusa.json` (the fixture profiles);
   - each golden records `ref_commit`, `maker` (the module path, under REF), the maker's arguments, the REF module's sha256 and the date. The makers refuse to run when `aruco_studio` is importable or `sys.path[0]` is not inside REF, so a golden can never come from the new code.
4. Replay every golden through the new core in `tests/core/test_golden_*.py`: exact equality for ints, strings and lists; floats exact where REF's test is exact (cells, trim), else 1e-6.
5. Port the pure assertions of REF's 17 Fusion-free suites to pytest with traceable names (section 3.2). A "section" of a REF suite is each `print("== ...")` header line (and each `section(...)` call where a suite has one); `tools/ref_sections.py` lists them read-only from REF into `tests/ref_sections.json` (suite, section text, line) once, and that file is the yardstick for M1.8. `test_aruco_label_print` and `test_aruco_frame`'s URDF half are out of scope (other venvs); note them in the trace as `skipped: venv`.
6. `tools/check.py` as in section 3.4: group discovery, one line per group, `--trace`. Nobody edits it after M1.
7. `tools/spec_status.py`: renders `docs/spec.json` to `reports/spec.html` and lists every `planned` item; the orchestrator runs it after each milestone.

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
| M1.8 | `docs/test_trace.md` lists every row of `tests/ref_sections.json` (every `print("== ...")` section of the 17 REF suites) with a pytest node id or `skipped: venv` | `tools/check.py --trace` prints `missing: 0`; `skipped` <= 3 rows (label_print, the URDF half, frame_pnp) |
| M1.9 | `git -C <REF> status --porcelain` identical before and after the golden run | identical |
| M1.10 | `tools/check.py` exits 0 in under 120 s | true |
| M1.11 | every file under `goldens/` has `ref_commit`, `maker` and `sha256` fields and `maker` starts with REF's path; `tests/core/test_golden_provenance.py` checks it | every file |
| M1.12 | `restructure.json` and `jo_maths.json` replay exactly (1e-9 on the Joint Origin maths) | 0 mismatches |

### M2: plan (the port of `evaluate()`)

| | |
|---|---|
| Goal | `plan_tag(TagSpec) -> TagPlan` replays REF's `evaluate()` goldens bit for bit; the record, the per-copy variant and the per-field Issues come with it. This is the hardest port (inventory "hardest pieces" 1, 2, 8), so it is a milestone of its own. |
| Owner paths | `aruco_studio/plan/target.py`, `plan/spec.py`, `plan/layers.py`, `plan/plan.py`, `plan/record.py`, `plan/variants.py`, `plan/__init__.py`, `goldens/evaluate/**`, `tools/make_evaluate_goldens.py`, `tests/plan/**` (except `test_mesh.py`, `test_exports.py`, `test_export_3mf.py`), `requirements.txt`, `docs/status/M2.md` |
| May edit | `aruco_studio/core/**` only to fix a port bug, with the golden that caught it, noted in `docs/status/M2.md` |
| Does not touch | `plan/mesh.py`, `plan/exports.py`, `scene/**`, `verify/**`, `server/**`, `studio/**`, `adapters/**`, `tools/check.py`, `docs/spec.json` |

Steps:

1. `plan/target.py` (with `prism_volumes`), `plan/spec.py` (with `check`, the per-field table of ARCHITECTURE 5.6), `plan/layers.py` (layers AND `guides`), `plan/plan.py` as in ARCHITECTURE 3.2 and 5.1-5.3. `plan_tag` follows `evaluate()`'s order exactly: fit on loops, the Origin turn, the mark, the label (a strip grows the tile), the pins, the trim, the slabs.
2. `goldens/evaluate/*.json` by `tools/make_evaluate_goldens.py`: REF's `aruco_feature.evaluate()` on REF's stand-in adsk (the pattern of `tools/make_cells_legacy_golden.py` and `make_trim_legacy_golden.py`, plus `tests/aruco_trim_fixtures.py`), over a matrix: 3 layouts x 3 modes x 2 ops x 4 turns x 3 marks x label off / on-black / on-white x pins none / triangle / round x trim off / both, on the box faces and the loop shapes those makers define, Auto and typed sizes, cells legacy / cell 0.68 / marker 0.5, and every legacy shape of settings (`chamfer: true`, no `origin_v`, `rotate_deg`, `frame`, legacy numbers). At least 600 cases. Each case stores the inputs as a `TagSpec` and the outputs: `spec.to_dict()`, the settings the node writes back, `layout`, `plan.parts`, the slabs, `mark`, `label`, `pins` (mm), `trim`, `notes`, `turn`, `x_fit`, the tile rectangle in mm and the node's warning words. The 12 + 26 existing `evaluate()` golden cases join this set. The maker has the same guard as M1's (never runnable with `aruco_studio` importable).
3. `tests/plan/test_golden_evaluate.py` replays all of it through `plan_tag`; `tests/plan/test_adapter_keys.py` replays it again with every adapter-only key deleted from `settings` (ARCHITECTURE 5.2) and with `settings` round-tripped through `core.settings.normalise`.
4. `plan/record.py` and `plan/variants.py`; `tests/plan/test_validate.py` for the per-field table: one case per row of ARCHITECTURE 5.6, each out-of-range value gives an `Issue` whose `field` is that row's key path.

Done checks:

| # | Check | Bar |
|---|---|---|
| M2.1 | the 12 cells + 26 trim `evaluate()` golden cases replay through `plan_tag` | 38 / 38 exact on `spec`, the written-back settings, `parts`, `mark`, `label`, `trim`, `notes` |
| M2.2 | `goldens/evaluate/` cases replay | >= 600 cases, 0 mismatches at 1e-6 mm; every legacy settings shape present at least 10 times |
| M2.3 | `plan_tag` never raises: 2,000 random `TagSpec`s (fuzz, every field of 5.6 driven out of range) | 0 exceptions; every `ok == False` has an `errors` entry AND an `Issue` of level `error` whose `field` is a 5.6 key path |
| M2.4 | every layer's polygons lie inside the union of the tile rectangle and the target's outer loop (1e-6 mm); `pattern` ink equals `cell_boxes` cell for cell; `guides.quiet_ring` contains `guides.sticker` | every golden case |
| M2.5 | adapter keys ignored: `plan_tag(spec)` == `plan_tag(spec without x_base / x_ref / z_sign / has_body / source / jo_v / host_xform / key / black_follows in settings)` | every golden case, byte-equal JSON |
| M2.6 | per-field validation: every row of ARCHITECTURE 5.6 has a test; the `Issue.field` equals the row's key path | 100 % of rows |
| M2.7 | records: `from_record` on every record inside the cells / trim goldens replans to the same plan; `record_same` is True after an unchanged round trip; `record_digest` changes only when the plan does | every record |
| M2.8 | variants: a copy's plan differs from the template's only in `id_regions` and the label slots | every golden case x 3 ids |
| M2.9 | `tools/check.py plan` exits 0 in under 180 s | true |

### M2b: scene + verify + exports + server

| | |
|---|---|
| Goal | a scene holds many tags and renumbers; OpenCV reads every plan, every export and every mesh; the API serves it all on 5360 with the web app's CORS and static serving already in. Runs beside M4 in its own worktree. |
| Owner paths | `aruco_studio/plan/mesh.py`, `plan/exports.py`, `scene/**`, `verify/**`, `server/**`, `tests/plan/test_mesh.py`, `tests/plan/test_exports.py`, `tests/plan/test_export_3mf.py`, `tests/scene/**`, `tests/verify/**`, `tests/server/**`, `requirements.txt`, `docs/status/M2b.md`, `docs/API.md` |
| May edit | `aruco_studio/core/**` and `plan/**` only to fix a bug, with the golden or test that caught it, noted in `docs/status/M2b.md` |
| Does not touch | `studio/**`, `adapters/**`, `tools/check.py`, `docs/spec.json` |

Steps:

1. `plan/mesh.py`, `plan/exports.py` (SVG, PNG, STL; the PDF through `core.sheet`; 3MF through `core.beds`; a scene's SVG / PNG with every tag at its pose).
2. `scene/` with the file format, the `locked` rule, and renumbering through `core.numbering.plan_stable` on an `AssemblySnapshot` built from the scene; the ledger kept in the file.
3. `verify/` with `numpy`, `opencv-python-headless` and `pymupdf` (the PDF raster) pinned.
4. `server/` with `fastapi`, `uvicorn`, `pydantic` pinned: every route of ARCHITECTURE 3.5 including `/api/form` and `/api/targets`; `studio/dist` served when present; CORS for 5361; `docs/API.md` from the routes.

Done checks:

| # | Check | Bar |
|---|---|---|
| M2b.1 | verify, plans: every layout x 4 turns x mark off / on x label off / on, rendered from the layers at 20 px / mm | every id read; grid / ChArUco detected as a board with every `charuco_corners` corner interpolated; PnP within 0.1 mm / 0.1 deg of `frames.opencv` |
| M2b.2 | verify, the core against OpenCV itself (not REF's table): every id of every dictionary `marker_grid` == `cv2.aruco.generateImageMarker`; every board of the `board.json` size table `black_rects_m` == `cv2.aruco.Board.generateImage` pixel for pixel | 9,596 markers, 0 mismatches; every board |
| M2b.3 | verify, variants: 10 relabelled copies of a labelled template | each copy's render reads as its own id, and only that id |
| M2b.4 | verify, the mesh: a top-down raster of `plan/mesh.py`'s triangles (black / white by layer) | reads the same ids as the layers' raster, every golden case |
| M2b.5 | scene: 40 tags (mixed layouts, two dictionaries) renumbered | no duplicate id per family; boards contiguous; a second renumber changes nothing; a printed id never moves after add / delete / rename (REF G0.7 scenarios on the scene); a locked tag's `record_digest` never changes |
| M2b.6 | `.arucostudio.json` round trip | `loads(dumps(s)) == s` for 100 random scenes; an unknown schema number is refused with a message |
| M2b.7 | exports: SVG parses and its viewBox is the tile in mm; PNG decodes to every id; STL watertight per layer (every edge in two triangles) with volume = area x height within 1e-6; the PDF sheet rasterised at 600 dpi finds every tag at true size within 0.15 mm; a scene PNG of 12 tags at 10 px / mm reads every id with each marker centre within 0.1 mm of its pose | every check |
| M2b.8 | server: `uvicorn` on 127.0.0.1:5360 answers `/api/health`; every route has a test with the request / response schema; `/api/plan` with a wrong type gives 422 naming the key path; `/api/form` lists every row of ARCHITECTURE 5.6 | 200 on every route; schema validated; 422 named |
| M2b.9 | `tools/check.py scene verify server` exits 0; every server started by a test is stopped (`netstat -ano \| findstr 5360` empty after) | true |

### M3: the Studio web app + Playwright e2e

| | |
|---|---|
| Goal | the 2D canvas with several tags on their targets, the inspector with per-field messages, the 3D view with the toggle, scene files, export and verify, all on the real API; screenshots prove it. The preset Library is M5. |
| Owner paths | `studio/**` (its own `package.json`, `vite.config.ts`, `playwright.config.ts`, `src/**`, `e2e/**`), `reports/e2e/**`, `docs/status/M3.md`, `docs/STUDIO.md` |
| May edit | nothing outside its paths. The server already serves `studio/dist` and allows 5361 (M2b); `tools/check.py` discovers the `studio` and `e2e` groups by itself. A server bug is reported in `docs/status/M3.md`, not fixed here |
| Does not touch | `aruco_studio/**`, `tests/**`, `tools/**`, `docs/spec.json` |

Steps:

1. `npm create vite@latest` (React + TS) in `studio/`; dependencies pinned: `react`, `react-dom`, `zustand`, `three`, `@types/three`, `@playwright/test`, `vitest`, `openapi-typescript`. No UI kit beyond plain CSS.
2. Types in `studio/src/api/types.ts` generated from the server's OpenAPI (`/openapi.json`) with `openapi-typescript`, so `TagPlan`, `Target` and `Issue` are the same on both sides.
3. The 2D canvas (SVG): pan, zoom, select, drag with 0.5 mm snap, rulers in mm; each tag drawn as target outline + layers + guides with `data-layer` / `data-state` attributes (ARCHITECTURE 4); multiple tags; add from a palette (single / grid / ChArUco) onto a target from `/api/targets`.
4. The inspector built from `/api/form` (never a hand-written field list), with the target editor (box / disc / face, thickness, holes), `/api/validate` messages under the field each `Issue.field` names, `/api/candidates` as the Layout list.
5. The 3D view (three.js) from `/api/plan?mesh=1`, the 2D / 3D toggle keeping the view centre; the OpenCV frame as a triad; the store's `zRange` and camera centre readable by the tests (`window.__studio` in dev builds).
6. The IDs table and Renumber (select on click; zoom is M5); Export buttons; Verify with the report shown; New / Open / Save / Save as.
7. Playwright e2e against `uvicorn` on 5360 + Vite on 5361, screenshots into `reports/e2e/<test>.png`.
8. `docs/STUDIO.md`: how to run, what each view shows, the keyboard map.

Done checks:

| # | Check | Bar |
|---|---|---|
| M3.1 | `npm run build` in `studio/` | exit 0, no TS errors |
| M3.2 | `npm run test` (vitest) | green; the store's reducers (add, move, select, toggle view, lock) and the SVG path builder for a polygon with holes covered |
| M3.3 | Playwright: open the app, add a single marker, a 4x3 grid and a 5x7 ChArUco, each on its own target | 3 tags on the canvas (`[data-layer="pattern"]` under 3 tag groups); their ids equal `/api/plan`'s for the same specs |
| M3.4 | Playwright: pick the disc target, type size 28 on a 40 mm box target, switch cells to "cell 0.68" | the inspector's size line equals the `Issue` text `/api/validate` returns; the count of `[data-layer="pattern"] path` elements changes between the two cells settings |
| M3.5 | Playwright: toggle 2D -> 3D -> 2D | the camera centre (`window.__studio.center`) is unchanged within 1 px; `window.__studio.zRange[1]` equals the plan's max layer `z[1]` within 0.01 mm; a screenshot of each view |
| M3.6 | Playwright: label on, on the white, below; then drag it into the quiet ring | an `Issue` with `field` starting `settings.label` appears under the Label field; a `[data-state="refused"]` path exists; Build anyway makes it a `label_*` layer |
| M3.7 | Playwright: Renumber with 6 tags of one family | the table shows 6 distinct ids; a second Renumber changes no cell; a typed override is kept |
| M3.8 | Playwright: save the scene, reload the page, open it | the same tag names at the same poses (store equality) |
| M3.9 | Playwright: Export SVG and PDF; Verify | the files exist under `.data/exports/<scene>/`; the verify report lists every tag with its ids read and a PnP error under 0.1 mm |
| M3.10 | screenshots in `reports/e2e/` | >= 10 PNGs named by test |
| M3.11 | every dev server stopped at the end (`netstat -ano \| findstr "5360 5361"` empty) | true |

### M4: the Fusion adapter skeleton + the migration map

| | |
|---|---|
| Goal | `TagPlan` -> Fusion calls, proven against a fake adsk; the map that moves the live add-in to the new core later. Not installed into Fusion. Runs beside M2b in its own worktree; needs only M2's `plan/`. |
| Owner paths | `aruco_studio/adapters/**`, `tests/adapters/**`, `docs/MIGRATION.md`, `docs/status/M4.md` |
| May edit | nothing outside its paths; `tools/check.py` discovers the `adapters` group by itself. A bug in `core/` or `plan/` is reported in `docs/status/M4.md` for M2b (which may edit them) |
| Does not touch | `aruco_studio/core/**`, `plan/**`, `scene/**`, `verify/**`, `server/**`, `studio/**`, `tools/**`, `docs/spec.json` |

Steps:

1. `adapters/fusion/fake_adsk.py`: a recording stand-in built from REF `tests/aruco_trim_fixtures.py` and `tests/aruco_ui_stubs.py` (read, not copied wholesale): `TemporaryBRepManager` boxes and prisms as CSG stand-ins (REF `test_aruco_chamfer_bodies` has one), `customFeatures`, `BaseFeature`, `JointOrigin`, `Sketch`, `Attributes`, a timeline. Every call is appended to a log. It installs itself as `adsk` in `sys.modules` only when a test asks (`fake_adsk.install()`).
2. `adapters/fusion/target.py`: a fake face / profile -> `Target`, with `x_ref` kept across a reversed edge and the trim's measured box and volumes.
3. `adapters/fusion/build.py`: every `Layer` -> a temporary body; `op` -> join / cut / intersect; `parts` order kept.
4. `adapters/fusion/records.py`: `plan/record.py`'s dict + the adapter's handles; `body_role`; `preset_of_node` through `core.presets.preset_of`; a REF record read back gives the same `TagSpec` (`plan/spec.from_record`).
5. `adapters/fusion/joint_origin.py`: place the Joint Origin from `core.geometry.jo_decompose`'s three numbers, read it back, keep one per tag (REF `test_aruco_jo_one_per_tag`'s 12-edit run on the fake).
6. `adapters/fusion/feature.py`: create / compute / edit outlines calling 2-5; `restructure.py`: the in-place `restructure()` on the fake timeline driven by `core.restructure.restructure_plan` (REF `test_aruco_restructure_sim`'s cases: every pair of structures x 2 layouts x sketch / none, a failure injected at each step leaves the fake document identical); `sync.py` around `core.edits.verdict`.
7. `docs/MIGRATION.md`: every (F) responsibility of REF's add-in -> which adapter module and which plan field replaces it; every REF Fusion quirk (inventory "Fusion 2705 behaviours") -> where the adapter honours it; the switch-over steps for the live add-in (a later, Fusion-gated run) with the golden gates that must stay green.

Done checks:

| # | Check | Bar |
|---|---|---|
| M4.1 | `pytest tests/adapters` on the fake adsk | green |
| M4.2 | every `evaluate()` golden case built through `build.py` on the fake | the body log has one body per `Layer`, z ranges equal the layer's `z`, in `parts` order |
| M4.3 | the fake's CSG probe at the mark, the label strokes and the pins (REF `test_aruco_chamfer_bodies`, `test_aruco_label_bodies`) | every probed point in the expected colour |
| M4.4 | `from_record` on the records inside the cells / trim goldens, read through `records.py` from a fake component's attributes | the `TagSpec` replans to the same plan; Edit -> OK unchanged writes no attribute |
| M4.5 | Joint Origin placement: 200 random frames -> `jo_decompose` -> the fake's Joint Origin -> read back | 1e-6 mm / 1e-6 deg; exactly one Joint Origin per tag after the 12-edit run |
| M4.6 | `restructure()` on the fake timeline over every pair of structures x 2 layouts x sketch / none | the same node, roles in order, combines where `restructure_plan` says; a failure at each step leaves the fake document identical |
| M4.7 | `docs/MIGRATION.md` names every (F) bullet of `docs/inventory/addin.md`'s detailed list (one row per file per (F) bullet, keyed by file and first function name) and every row of its quirk tables | `tests/adapters/test_migration_doc.py` counts: missing 0 |
| M4.8 | nothing imports `adsk` for real: `python -c "import aruco_studio.adapters.fusion"` with no `adsk` in `sys.modules` raises `RuntimeError("... fake_adsk.install() ...")` | true |

### M5: the Library, zoom, and what M3 left

| | |
|---|---|
| Goal | the print preset Library (a React port of REF `resources/preset_library`), click-again-to-zoom in the IDs table, the Playwright tests for both, and every M3 follow-up listed in `docs/status/M3.md`. After M3, same owner paths, one agent. |
| Owner paths | `studio/**`, `reports/e2e/**`, `docs/status/M5.md`, `docs/STUDIO.md` |
| Does not touch | everything else |

Done checks:

| # | Check | Bar |
|---|---|---|
| M5.1 | Playwright: open the Library, Select the "Aruco 0.6" preset | the inspector's cells and heights equal the preset's (`/api/presets`); Save as a new preset; it appears in the cards and in `/api/presets` |
| M5.2 | Playwright: click a row in the IDs table, click it again | the first click selects (camera centre unchanged); the second zooms (the tag fills >= 50 % of the viewport width) |
| M5.3 | `npm run build`, `npm run test`, every M3 Playwright test still green; every dev server stopped | true |

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

`docs/test_trace.md` is generated by `tools/check.py --trace`: one row per row of `tests/ref_sections.json` (REF suite, section header, pytest node id or `skipped: <why>`, the REF spec test ids it covers). A section is each `print("== ...")` header of a REF suite (M1 step 5). The REF spec test ids (`EX-MARK-1`, `G0.3`, ...) appear verbatim so `docs/spec.json` can point at them. The command prints `missing: N` (rows with no node id and no `skipped`) and exits non-zero when N > 0.

### 3.3 Goldens

| Rule | |
|---|---|
| A golden is made ONLY by REF's code, run read-only from `tools/make_*_goldens*.py` with `sys.path` inside REF. Never by the new code: every maker asserts `"aruco_studio" not in sys.modules` and that `sys.path[0]` is under REF before it imports anything, and exits 2 otherwise. | |
| The three goldens REF already has (cells, label rule 1, trim) are copied verbatim with their own maker commits; they are older than `c8216ff` on purpose, because REF's tests at `c8216ff` replay them. | |
| Each golden file carries `ref_commit`, `maker` (a path under REF), the REF module sha256, the maker's arguments and the date. `tests/core/test_golden_provenance.py` checks every file. | |
| A golden test compares exactly unless REF's own test used a tolerance; then the same tolerance. | |
| A failing golden is a port bug until proven otherwise. A golden is never regenerated to make a test pass. Changing one needs a note in `docs/status/<M>.md` with the REF line that explains the difference, and the orchestrator's OK. | |

### 3.4 One command

`tools/check.py` (Python, so it runs the same from Git Bash and PowerShell):

```
.venv/Scripts/python tools/check.py            # everything
.venv/Scripts/python tools/check.py core plan  # some groups
.venv/Scripts/python tools/check.py --trace    # rewrite docs/test_trace.md
```

Groups are DISCOVERED, so no milestone edits the file after M1: every directory under `tests/` that holds a `test_*.py` is a pytest group of that name (`core`, `plan`, `scene`, `verify`, `server`, `adapters`); `studio` (vitest + build) exists when `studio/package.json` does; `e2e` (Playwright; starts 5360 and 5361, stops them in `finally`) exists when `studio/e2e/` does. It prints one line per group (`core: 2,311 passed in 38 s`) and exits non-zero on any failure. It refuses to run `e2e` if 5360 or 5361 is already bound.

## 4. Definition of Done for this run

| # | Check | How measured |
|---|---|---|
| D1 | `tools/check.py` exits 0 with every group | the summary lines, pasted into `docs/status/RUN.md` |
| D2 | the four REF goldens replay bit for bit: cells 511 + 12, label 36, trim 26 + 288 | the four golden tests green, counts printed |
| D3 | >= 600 `evaluate()` cases from REF replay through `plan_tag`, with and without the adapter-only settings keys | M2.2, M2.5 |
| D4 | `docs/test_trace.md` covers 100 % of the 17 Fusion-free REF suites' sections | `tools/check.py --trace` prints `missing: 0` |
| D5 | `aruco_studio/core` and `plan` import only the stdlib; `plan` and `scene` never import `adapters`, `server` or `verify` | M1.1, M1.2, `tests/core/test_purity.py` |
| D6 | OpenCV reads every id off every rendered plan, every relabelled copy, every mesh raster, every PNG / PDF export and a 12-tag scene PNG; the dictionary and board tables equal cv2's own output; PnP within 0.1 mm / 0.1 deg | M2b.1-M2b.4, M2b.7 |
| D7 | a scene of 40 tags renumbers uniquely and stably; printed ids never move; a locked tag's ink never changes | M2b.5 |
| D8 | the Studio builds and >= 8 Playwright tests pass with >= 10 screenshots, every bar read from the DOM or the store, not from a picture | M3.1-M3.10 |
| D9 | the Fusion adapter skeleton builds every golden case on the fake, one body per layer | M4.2 |
| D10 | `docs/MIGRATION.md` maps every (F) responsibility and every quirk | M4.7 |
| D11 | `docs/spec.json` statuses updated: every feature and test either `built` / `passing` with its check, or still `planned` with a reason | `tools/spec_status.py` renders `reports/spec.html` and lists the planned ones |
| D12 | nothing written into REF, `%USERPROFILE%\CADExporter`, or Fusion; no server left on 5360 / 5361 | `git -C <REF> status --porcelain` unchanged; `netstat` empty; the orchestrator checks |
| D13 | every commit on ROOT `main`, local only; the M2b and M4 branches merged fast-forward and their worktrees removed | `git remote -v` empty; `git worktree list` shows ROOT only |
| D14 | every field of `TagSpec` has a validation row (ARCHITECTURE 5.6), a test, an `Issue.field` key path and a `/api/form` entry; a wrong type is a 422 naming the key | M2.6, M2b.8 |
| D15 | no golden under `goldens/` was made by the new code | M1.11 (provenance fields; the makers' guard) |

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

## 6. Review changes (plan review)

An adversarial review of `ARCHITECTURE.md`, `PLAN.md` and `spec.json` against `BRIEF.md` and `inventory/*.md` on 2026-10-16. Every change, and why.

### Brief items that were not covered

| # | Change | Why |
|---|---|---|
| R1 | A **target editor** in the Studio (ARCHITECTURE 4; `GET /api/targets`; `core/faces.py`; spec ST-UI-TARGET, ST-FACES, ST-T-UI-11; M3 step 4, M3.4). | The brief's 2D canvas puts markers on something. In Fusion that is a clicked face; the plan had no way for a Studio user to make a face (a box, a disc with holes, a thickness), so Auto size, trim, pins and pockets could not be exercised outside Fusion. The ten gallery faces become product data instead of a test fixture. |
| R2 | `TagPlan.guides` (ARCHITECTURE 5.3; `plan/layers.py`; spec ST-GUIDES). | The brief wants the quiet zones and the label's clear zones drawn. The web app "computes nothing geometric", but the plan carried no quiet ring, clear zones, keep-outs or refused-label preview, so the canvas could not draw them without re-deriving geometry. |
| R3 | `plan/target.prism_volumes` (ARCHITECTURE 3.2, 5.1). | Inventory gap 12: trim refuses when nothing is measured. Every Studio target is a prism, so the volumes are exact from the outline; without this, Trim could never be shown in the 2D / 3D view. |
| R4 | The 3D view's bar is measured: `window.__studio.zRange` equals the plan's max `z[1]` (M3.5); `/api/plan?mesh=1` is the only source of triangles (ARCHITECTURE 4). | "a raised tag shows its height" was not measurable, and ARCHITECTURE allowed client-side extrusion while also saying the app computes nothing geometric. |
| R5 | Rule: `plan/` and `scene/` never import `adapters/`, `server/` or `verify/` (ARCHITECTURE 2; D5; ST-T-PURE-1). | The brief's build123d / viser reuse needs `plan/` and `scene/` to stand alone. It was stated in section 6 but nothing checked it. |
| R6 | The preset Library and click-again-to-zoom move to **M5** (new milestone). | M3 was too big for one agent (canvas, inspector, 3D, IDs, library, export, scene files, 8 e2e tests). The library is the one piece the brief does not ask for; it comes after the two views work. |

### Boundary errors

| # | Change | Why |
|---|---|---|
| R7 | `restructure_plan` and its words move from `adapters/fusion/restructure.py` to `core/restructure.py` (ARCHITECTURE 3.1, 3.6; PLAN 1.2; M1 step 2; golden `restructure.json`, M1.12; spec ST-RESTRUCTURE, ST-T-RESTRUCTURE-1). M4.6 now tests the adapter's in-place `restructure()` on the fake timeline (REF `test_aruco_restructure_sim`), which the old plan never tested. | Pure logic was left in the adapter. The inventory classes it C and REF's own `test_aruco_extrude_sync` section 4 pins it with no `adsk`. |
| R8 | The Joint Origin composition maths move to `core/geometry.py` (`jo_decompose` / `jo_compose`; golden `jo_maths.json`; spec ST-JO-MATHS, ST-T-JO-1). The adapter keeps placing, read-back and one-per-tag. | Same: pure maths in the adapter. A build123d or viser adapter needs the same frame decomposition. |
| R9 | `preset_of_node` splits: the mapping is `core.presets.preset_of(settings, numbers)`, the node read stays in `adapters/fusion/records.py`. | Same pattern as `from_record`; the old row kept the whole function F. |
| R10 | `aruco_extrude_sync.verdict` moves to `core/edits.py`; `doc_key` and the hooks stay F. | Inventory classes `verdict` C. |
| R11 | `body_role` moves OUT of `core/export_rows.py` into the adapter. | It parses Fusion's body names ("tag tile <key>"): a Fusion convention in the core. |
| R12 | The plan reads `x_ref`, `z_sign`, `has_body` from `Target` only; the adapter-only settings keys are declared opaque, and `tests/plan/test_adapter_keys.py` replays every golden with them deleted (ARCHITECTURE 2, 5.2; M2.5; D3; spec ST-T-PLAN-5). | Fusion specifics (`jo_v`, `host_xform`, `x_base`, ...) sit inside the core's `TagSpec.settings` because the dict's shape is versioned. Keeping them is right; nothing proved the plan ignored them. |
| R13 | `/api/form` is a real route of M2b, and the inspector may never use a hand-written field list (ARCHITECTURE 3.5; M3 step 4). | M3 step 4 said "if M2 exposes it, else written by hand": a second copy of the form model in TypeScript, which drifts. |

### Versioned rules and goldens

| # | Change | Why |
|---|---|---|
| R14 | `TagSpec.settings` rows for the old `frame` key, `label.scope = "square"` and the legacy numbers (ARCHITECTURE 5.2); `TagPlan.rules` gains `legacy_numbers` and `font: 1`; M2 step 2's matrix includes every legacy settings shape, M2.2 requires each at least 10 times. | Three migrations of the inventory's rules table (1.10, "The versioned rules") were missing from the contract, and the evaluate goldens had no legacy cases, so a Fusion adapter could rebuild an old node differently. The font change of 2026-10-10 is not versioned in REF (inventory gap 5); recording it in the plan only keeps the stored record byte-identical. |
| R15 | M2.1 compares the written-back settings too. | The cells and trim goldens store "what their nodes store"; the bar compared only spec / parts / mark / label / trim / notes, so a settings write-back bug would pass. |
| R16 | The golden makers refuse to run when `aruco_studio` is importable or `sys.path[0]` is outside REF; every golden carries `maker`; `tests/core/test_golden_provenance.py` checks it (PLAN 3.3; M1 step 3; M1.11; D15; spec ST-T-GOLDEN-1). "A golden is never regenerated to make a test pass." | The rule "never by the new code" had no mechanism. A builder with a failing replay could regenerate a golden from the port in one command. |
| R17 | M1 step 3 says which goldens need REF's ADD-IN on a stand-in `adsk` (`settings.json`, `form.json`, `prusa.json`). | They were listed "from REF's core", but `aruco_feature`, `aruco_extrude_cmd` and `aruco_extrude_ui` import `adsk`; the maker needs `tests/aruco_ui_stubs.py`, as `make_cells_legacy_golden.py` does. |
| R18 | The three copied goldens keep their own maker commits (196454c, 8473e14, 5cf71bd). | PLAN 3.3 said every golden is made at `c8216ff`; those three are older on purpose. |

### Milestones, paths, done checks

| # | Change | Why |
|---|---|---|
| R19 | M2 is split: **M2** = `plan/` (the `evaluate()` port, records, variants, validation); **M2b** = scene, verify, exports, mesh, server. M4 runs beside M2b, not beside M3; M3 follows M2b. | The old M2 held the hardest port in the inventory AND six other modules, three new dependencies and a server: too big for one agent. M4 needs only `plan/`, so it starts earlier. |
| R20 | Parallel milestones (M2b, M4) work in their own git worktree on a branch; the orchestrator fast-forward merges; nobody runs `git add -A` (PLAN 2; D13). | Two agents committing in one working tree on `main` collide on the index and sweep each other's untracked files. |
| R21 | `tools/check.py` discovers its groups from `tests/<dir>/`, `studio/package.json` and `studio/e2e/`; M3 and M4 no longer "append one function" to it; M3 no longer edits `server/app.py` (CORS and static serving are M2b's from the start). | Three owner-path overlaps on two shared files between milestones that run in parallel. |
| R22 | M1.8 defines a "section" (each `print("== ...")` header, listed once by `tools/ref_sections.py` into `tests/ref_sections.json`); `--trace` prints `missing: N` and fails on N > 0; up to 3 `skipped: venv` rows. | "100 % of sections" was not measurable: REF suites have no section API, only printed headers. |
| R23 | M2.4 rephrased: inside the union of the tile and the target's outer loop. | "inside the tile" is false for the trim's keep column, the recess and the holes. |
| R24 | M3 bars read the DOM or the store (`data-layer`, `data-state="refused"`, `window.__studio`), not a picture (M3.3-M3.6, M3.8; D8). | "the preview draws orange" and "the same tags at the same places" could only be judged by eye. |
| R25 | M4.7 defines a "(F) line group" (one row per file per (F) bullet, keyed by file and first function) and names the test that counts. M4.8 says when the import must raise (no `adsk` in `sys.modules`) so it does not contradict M4.1. | Both were ambiguous. |
| R26 | `tools/spec_status.py` has an owner (M1) and `docs/spec.json` has one (the orchestrator, after each milestone). ST-SNAPSHOT moves to M1 (it is `core/ids_design.py`). | D11 named a tool nobody built; the spec file had no writer; a core module was filed under M2. |

### Validation and OpenCV

| # | Change | Why |
|---|---|---|
| R27 | ARCHITECTURE 5.6: a per-field validation table (type, valid range from REF's named constants, what the Issue says and at which level), the two layers (422 for a wrong type, `Issue` for a wrong value), `Issue.field` as a key path; `plan/spec.check`; M2.6, M2b.8, D14; spec ST-SPEC-CHECK, ST-T-PLAN-6. | The plan contract had types but no limits, and `Issue.field` was "a form field or tag": nothing bound an API error, an inspector message and a core note to the same field name. |
| R28 | OpenCV checks the core against cv2 ITSELF (every dictionary id vs `generateImageMarker`, every board vs `Board.generateImage`), not only against REF's table (M2b.2; spec ST-T-VERIFY-3). | REF's EX-LAYOUT-6 / -7 did this; the new plan only replayed REF's JSON table, so a corrupt table would pass. |
| R29 | OpenCV also reads: 10 relabelled copies (each as its own id and only that), a top-down raster of the MESH, and a 12-tag scene PNG with every marker centre within 0.1 mm of its pose (M2b.3, M2b.4, M2b.7; D6; spec ST-T-VERIFY-4). ChArUco detection must interpolate every `charuco_corners` corner (M2b.1). | Variants, the 3D path and the multi-marker canvas had no oracle; a board "detected as a board" said nothing about its corners. |
| R30 | `pymupdf` pinned for the PDF raster (M2b step 3). | M2.8 rasterised the PDF at 600 dpi with no rasteriser in the venv. |
| R31 | A locked tag's rule is defined and tested (ARCHITECTURE 5.5; M2b.5; spec ST-T-SCENE-2). | `locked` was a field with a sentence and no check. |

## 7. Builder notes (M1)

Written by the M1 builder, 2026-10-16. Where PLAN and ARCHITECTURE were silent, or where they and the work order differed, this says what was done and why. The numbers are in `docs/status/M1.md`.

### Names and places

| Work order said | Built as (PLAN's names) | Why |
|---|---|---|
| `tools/make_goldens.py` | `tools/make_goldens_from_ref.py` | PLAN M1 step 3 names it; the work order says to follow PLAN |
| `tests/goldens/*.json` | `goldens/*.json`; REF's own fixtures in `goldens/ref/`, PrusaSlicer's profiles in `goldens/prusaslicer/` | PLAN M1 owner paths, ARCHITECTURE 2 |
| `tests/test_goldens.py` | `tests/core/test_golden_*.py`, one per table | PLAN M1 step 4 |
| port the REF suites' assertions into pytest | `tests/core/ref_suites/ref_*.py` (REF's script, imports renamed) run by `tests/core/test_ref_*.py`: one pytest test per REF section | every REF check runs unchanged, and each section must pass exactly as many checks as REF's own run did (`tests/ref_sections.json` counted them). The copies are made by `tools/port_ref_suites.py`, never edited by hand |
| `docs/spec.json` is the orchestrator's (PLAN 2) | M1 set the statuses of its own items, with a `result` field | the work order asks for it |

### How goldens come from REF without importing adsk

| Golden | REF code that made it | How |
|---|---|---|
| dictionary, board, origin, slabs, chamfer, autosize, label, trim, numbering | `bam_cad_core/*` | imported read-only: `python -I`, cwd a temp dir, REF's `CADExporter` as `sys.path[0]` |
| presets, prusa, preset_library | `ArucoMarkers/aruco_presets.py`, `aruco_prusa.py`, `aruco_preset_library.py` | imported: none imports adsk at the top |
| restructure, jo_maths, settings, form | `aruco_restructure.py`, `aruco_tags.py`, `aruco_feature.py`, `aruco_extrude_cmd.py`, `aruco_extrude_ui.py`, `bam_fusion_ui.py` | these import adsk, so they are NEVER imported. Their pure functions are taken from the pinned blob with `ast` and exec'd alone. The one Fusion read each does gets a plain stand-in: `_jo_probe` returns a frame; a custom feature is `FakeNode` (the spec named value, parameters in cm, frame sketch yes / no, roles match / not) |
| `goldens/ref/*` | REF's own fixture files (196454c, 8473e14, 5cf71bd, the measured GIM43 disc) | copied verbatim inside a provenance wrapper: `golden` is the file's JSON, `sha256` the file's bytes at c8216ff |

The maker refuses to run (exit 2) when `aruco_studio` is importable; `tests/core/test_golden_provenance.py` proves it. REF's `git status` is compared before and after every run. Other sessions commit in REF all day, so only a change in a file the run read (or bytecode) counts as ours.

### Choices where the plan was silent

| Choice | Why |
|---|---|
| A section is any `print("...")` header of a REF suite (plain or f-string), not only `print("== ...")` | 5 suites have no `==` headers (`autosize`, `numbering`, `ids_stability`, `settings`, `markers` print `§4 ...`, `G0.1 ...`). The tallies and indented info lines are left out |
| `markers.py` kept whole except `instance_fiducials` | PLAN 1.1 dropped `fit_square`, `fit_board`, `largest_rect` and the sidecar helpers. They are pure, and keeping them lets REF's `tests/test_markers.py` run unchanged. `instance_fiducials` needs `fiducials.Fiducial` and a CAD Exporter link description, so it is the one left out |
| `fiducials.ARUCO_DICTS`, `DICT_ALIASES`, `board_for_tube` live in `core/dictionary.py` | PLAN 1.1; the decal-era rest of `fiducials.py` is not ported |
| `core/_ref_compat.py` maps REF's module names (`aruco_core.module("aruco_label")`, `aruco_feature.A()`, `aruco_presets.line_mm`) onto the core | copied bodies stay byte for byte REF's; `tests/core/test_port_fidelity.py` checks every shared top-level name against the pinned blob |
| A node is a `core.edits.NodeState`: stored spec, parameters in mm, black linked, frame sketch, roles error | REF's edit model read a Fusion custom feature; these five facts are all it read |
| `geometry._dot` is aruco_tags' (p0 + p1 + p2), `_dot_f` aruco_feature's (a sum from the int 0) | they differ in the sign of a zero, and `atan2` sees it; both are kept so the Joint Origin maths is bit for bit |
| `jo_decompose` returns REF's numbers: the angle in RADIANS (Fusion's `createByReal`), offsets in the frames' unit | ARCHITECTURE 3.1 wrote `angle_deg`; REF hands radians to Fusion |
| `core/presets.py` takes a store (`.text`, `.aside`); `MemoryStore` is the in-memory one | core never touches a file; REF's file rules (a broken file moved aside, missing = empty) run on the text. `tests/core/ref_suites/ref_store_shim.py` puts REF's path API back on top for the ported suite; `server/store.py` (M2b) is the real home |
| `core/prusa.py` reads text (`parse_ini`, `parse_bundle`) into `PrusaSources` | the folder walk is the server's (M2b) |
| `core/validate.py` keeps REF's `Issue(anchor, ...)`; `ANCHOR_FIELD` / `field_of` give each dialog row's TagSpec key path | `validate(spec, plan)` needs the TagPlan, so it is M2's; M1 has the model and the routes |
| `core/form.py` has no `values(inputs)`, `snap_size`, `_size_limit`, `_check_auto` or the refresh state machine | they read and write Fusion command inputs; the Studio's inspector is built from `/api/form` (M2b) |
| `core/ids_design.py`: `AssemblySnapshot` + `collection()` make the dict REF's `collect_design` returned, so `plan_design` runs unchanged | ARCHITECTURE 5.4. `staleness`, `_drift`, `export_overrides` measure Fusion bodies or read the node (adapter, M4); `part_plan`, `id_regions`, `label_slots` are `plan/variants.py` (M2) |
| `core/beds.py` and `core/dictionary.py` still open files (the 3MF / STL writers; the dictionary table, package data) | copied verbatim (PLAN 1.1). M2b should call the writers only from `server/`. `test_purity.py` checks imports, not `open()` |
| The M1.2 grep is measured with `ast`: no IMPORT of adsk, numpy or cv2 | REF's verbatim docstrings say "cv2 5.0.0" where they record what was measured; a literal grep hits them |
| `.gitattributes`: LF everywhere | this machine has `core.autocrlf=true`; goldens and ported files must stay byte-identical |
| `pytest==8.4.2`, `pytest-xdist==3.8.0`, `numpy==2.3.5`, `opencv-contrib-python-headless==5.0.0.93` | PyPI, pinned. cv2 5.0.0 is the version REF's tables were measured on. numpy and cv2 are for M2b's `verify/`; the core never imports them |
| REF's mutation tables (`tools/mutate_aruco_ids.py`, `mutate_aruco_label.py`) run on the new core: `tests/core/test_ref_mutations.py` | ST-T-LEDGER-1 / ST-T-LABEL-4 ask for it; the 32 rows that break a core file are each killed by their aimed check. The 4 rows that break an add-in file are M4's |

### Parked for M2 (the `evaluate()` cases)

`tests/core/test_ref_cells_legacy.py` and `test_ref_trim_legacy.py` skip their `evaluate()` sections with "parked for M2" (12 + 26 cases, and the junk-trim and JO_AFTER re-runs). M2 replays them through `plan_tag` (M2.1) and removes the parked entries from `tests/ref_trace_notes.json`.

### Not ported (Fusion-only)

REF has 43 `tests/test_aruco_*.py` suites at c8216ff. Ported: the 17 Fusion-free suites (16 whole; `test_aruco_settings` is deferred, below), `test_aruco_frame`'s core half, REF's `test_markers`, `test_print_beds` and `test_print_beds_slicer`, and the pure sections of three add-in suites. Not ported:

| Suite | Why | Owner |
|---|---|---|
| `test_aruco_arrow_typing` | typing at a canvas arrow (Fusion custom graphics, the v2 dialog) | M4 (adapter UI) |
| `test_aruco_chamfer_bodies` | the mark on CSG stand-in bodies (`part_body`, TBM) | M4 (M4.3) |
| `test_aruco_collect` | the CAD Exporter's `_collect_aruco` on fake Fusion objects | not planned (CAD Exporter) |
| `test_aruco_disc_fit` | `evaluate()` on the GIM43 discs | M2 (`plan_tag`) |
| `test_aruco_edit_roundtrip` | Edit -> OK on a stand-in node, the timeline marker, the frame sketch, orphan Joint Origins | M4 (the pure edit model is in goldens/settings.json) |
| `test_aruco_export_dialog` | the Export dialog on stand-in inputs (its progress-bar section is ported) | M4 |
| `test_aruco_extrude_dialog` | the Extrude dialog on stand-in inputs | M4 (its words are in goldens/form.json) |
| `test_aruco_extrude_fixes` | `paint()`, a mode change on a stand-in node | M4 |
| `test_aruco_extrude_sync` | after-compute hooks on fake Fusion (section 4, `restructure_plan`, is ported) | M4 |
| `test_aruco_frame` (`evaluate()` and URDF halves) | `evaluate()` x Origin; the URDF needs yourdfpy | M2; skipped: venv |
| `test_aruco_frame_pnp` | `evaluate()` + OpenCV PnP on a stand-in | skipped: venv; M2b `verify/` |
| `test_aruco_ids_dialog` | the IDs dialog on the shared table | M4 |
| `test_aruco_ids_label_warning` | `label_warning` on a stand-in part | M2 (`plan/variants.py`) |
| `test_aruco_ids_ledger_fusion` | stamps and the ledger read / written on fake Fusion objects (`plan_design` itself is in core/ids_design.py) | M4 |
| `test_aruco_ids_upstream` | the rebuild hooks' control flow on fake Fusion (the pure digests are core/numbering's) | M4 |
| `test_aruco_jo_one_per_tag` | one Joint Origin per tag through 12 edits on a stand-in design | M4 (M4.5) |
| `test_aruco_label_bodies` | the label as CSG bodies | M4 (M4.3) |
| `test_aruco_label_print` | the slicing oracle | skipped: venv |
| `test_aruco_marker_table` (clicks, pick, zoom, navigation) | the table's UI (its names and rows are ported) | M3 (studio/src/table) |
| `test_aruco_preset_library` | the palette window and its messages | M5 |
| `test_aruco_presets_dialog` | presets in the Fusion dialog | M4 |
| `test_aruco_refresh_hook` | the v2 dialog's refresh hook | M4 |
| `test_aruco_restructure_sim` | the in-place `restructure()` on a stand-in timeline | M4 (M4.6) |
| `test_aruco_settings` | the remembered dialog options and their file; `snapshot` / `apply` read Fusion inputs | deferred: M2b (`server/store.py`) |
| `test_aruco_trim_dialog` | Trim excess in the Fusion dialog | M4 (`trim_issues` / `trim_lines` are in goldens/form.json) |
| `test_aruco_trim_feature` | Trim excess in `evaluate()` and compute on a stand-in | M2 / M4 |
| `test_aruco_ui_v2` | the v2 dialog on stand-ins (classify and the Issue model are in goldens/form.json) | M4 |
