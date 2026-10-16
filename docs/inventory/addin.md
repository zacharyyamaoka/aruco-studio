# Inventory: the Fusion add-in (ArucoMarkers/*.py)

Read at commit `c8216ff` of cad-exporter, branch `claude/aruco-fusion-plugin-0e9bcb`, on 2026-10-16. Line counts are `wc -l`. Function line ranges come from the file at that commit.

The question this answers: how much of the add-in can leave Fusion.

## Classes

| class | meaning |
|---|---|
| C | pure logic for a Fusion-free core: sizing, rounding, labels, marks, presets, Prusa profiles, validation messages and their rules, numbering, ID ledgers, trim and restructure plans, marker tables, anything computable from numbers |
| F | Fusion adapter work: selections, sketches, extrudes and combines, the timeline, custom-feature compute and edit, Joint Origins, joints, occurrences, appearances, documents |
| U | UI: dialog rows and layout, manipulators, palettes, the HTML preset library, menus, viewport ghosts and highlights (custom graphics) |
| T | test harness: labs, gates, the bridge, probes, fixtures, read-only diagnostics |

The ghosts and highlights are drawn with Fusion custom graphics, so they talk to `adsk`. They are counted as U because they are presentation only: the Studio's 2D/3D viewer replaces them. The box and prism maths that feeds them is C.

## The short answer

| class | lines | share |
|---|---|---|
| C, pure logic still inside the add-in | about 5,100 | 11 % |
| F, Fusion adapter | about 11,100 | 23 % |
| U, UI | about 7,300 | 15 % |
| T, test harness | about 23,800 | 50 % |
| total | 47,410 | 100 % |

- Half of the add-in is test harness. It never ships. Most of it drives Fusion and stays with the adapter.
- The production code is about 23,600 lines. About 5,100 of them are pure and can move to the core now.
- The Fusion-free core already holds about 9,800 lines: `CADExporter/bam_cad_core/aruco_*.py` (8,335) and `markers.py` (1,428). After the move the core would be about 15,000 lines and the adapter about 11,000 plus its UI.
- 36 of 45 files import `adsk` at the top level. One more guards the import with `try`. Three import it lazily inside functions. Five never import it.

## Per-file table

Estimates. A file's four numbers add up to its line count.

| file | lines | adsk at top | C | F | U | T | what it is |
|---|---:|---|---:|---:|---:|---:|---|
| ArucoMarkers.py | 77 | yes | 0 | 77 | 0 | 0 | add-in entry: run/stop wiring |
| aruco_actions.py | 1882 | yes | 0 | 0 | 0 | 1882 | the dev bridge's allow-list of actions |
| aruco_autosize_gallery.py | 373 | lazy | 115 | 0 | 0 | 258 | ten non-box faces, offline shapes and Fusion build |
| aruco_bridge.py | 252 | yes | 0 | 0 | 0 | 252 | the file bridge (thread, custom event, dispatch) |
| aruco_cf_probe.py | 1388 | yes | 0 | 0 | 0 | 1388 | the custom-feature research probe (superseded by aruco_feature) |
| aruco_chamfer_lab.py | 679 | yes | 0 | 0 | 0 | 679 | corner-mark bridge checks |
| aruco_commands.py | 1498 | yes | 150 | 250 | 1000 | 98 | toolbar panel; ArUco Tag / Edit / IDs / Export / Send dialogs |
| aruco_core.py | 52 | no | 0 | 52 | 0 | 0 | loads bam_cad_core under a private alias |
| aruco_demo.py | 284 | yes | 0 | 0 | 0 | 284 | demo design and UI fixtures |
| aruco_edit_gates.py | 1727 | yes | 0 | 0 | 0 | 1727 | edit gates round 2 (sync, restructure, deps, jo, menu) |
| aruco_edit_test.py | 870 | yes | 0 | 0 | 0 | 870 | edit round-trip, orphans, methods |
| aruco_export.py | 680 | yes | 120 | 560 | 0 | 0 | export: sidecar, STLs, PrusaSlicer project, rows |
| aruco_export_lab.py | 373 | yes | 0 | 0 | 0 | 373 | export type checks |
| aruco_export_preview.py | 260 | yes | 20 | 0 | 240 | 0 | the Export viewport highlight |
| aruco_extrude_cmd.py | 2860 | yes | 450 | 250 | 2050 | 110 | the ArUco Extrude dialog (create and edit) |
| aruco_extrude_lab.py | 1300 | yes | 0 | 0 | 0 | 1300 | extrude labs: colours, cross, preview bench, UI fixture |
| aruco_extrude_sync.py | 571 | yes | 30 | 541 | 0 | 0 | record / Joint Origin refresh after a recompute |
| aruco_extrude_ui.py | 1369 | yes | 230 | 0 | 1139 | 0 | dialog v2: tabs, icons, arrows, per-line validation |
| aruco_feature.py | 3769 | yes | 900 | 2709 | 70 | 90 | ArUco Extrude as ONE custom feature: evaluate, create, compute, edit |
| aruco_heights_lab.py | 1284 | yes | 0 | 0 | 0 | 1284 | heights, pins, migration, turns, split, flip labs |
| aruco_ids_accept.py | 5661 | yes | 0 | 0 | 0 | 5661 | IDs gates G1-G9, fixtures F1-F17, probes, E2E renders |
| aruco_ids_cmd.py | 535 | yes | 46 | 40 | 449 | 0 | the ArUco IDs dialog |
| aruco_ids_feature.py | 3721 | yes | 300 | 3291 | 0 | 130 | ArUco IDs as ONE custom feature: collect, parts, hooks |
| aruco_ids_follow_probe.py | 1237 | yes | 0 | 0 | 0 | 1237 | M1-M6 and delete probes for per-copy parts |
| aruco_ids_preview.py | 260 | yes | 35 | 0 | 225 | 0 | the IDs ghost and highlight |
| aruco_ids_rack.py | 203 | yes | 0 | 0 | 0 | 203 | G10 / E2E on Zach's rack, read only |
| aruco_ids_stability.py | 428 | yes | 0 | 0 | 0 | 428 | G0.7 id stability scenario |
| aruco_ids_test.py | 826 | yes | 0 | 0 | 0 | 826 | per-copy variant inspection (retired flow) |
| aruco_label_lab.py | 993 | yes | 0 | 0 | 0 | 993 | label labs |
| aruco_live_test.py | 795 | yes | 0 | 0 | 0 | 795 | live feature scenario, Joint Origin probes |
| aruco_marker_table.py | 986 | guarded | 540 | 0 | 300 | 146 | one marker table for IDs and Export |
| aruco_marker_table_lab.py | 581 | yes | 0 | 0 | 0 | 581 | marker table Fusion check |
| aruco_origin_lab.py | 456 | yes | 0 | 0 | 0 | 456 | Origin labs |
| aruco_preset_library.py | 825 | lazy | 470 | 45 | 310 | 0 | preset library: recent list, model, palette window |
| aruco_presets.py | 570 | no | 570 | 0 | 0 | 0 | print presets (JSON file, built-ins, catalog) |
| aruco_preview.py | 542 | yes | 245 | 0 | 297 | 0 | the ArUco Extrude ghost |
| aruco_probe.py | 243 | yes | 0 | 0 | 0 | 243 | one-shot API probe (2026-10-07) |
| aruco_prusa.py | 273 | no | 273 | 0 | 0 | 0 | PrusaSlicer print profiles, read only |
| aruco_restructure.py | 565 | yes | 80 | 475 | 0 | 10 | restructure a node in place; dependents |
| aruco_settings.py | 326 | no | 269 | 0 | 57 | 0 | remembered dialog options; where PrusaSlicer is |
| aruco_tags.py | 3550 | yes | 300 | 2850 | 0 | 400 | Fusion side of tags: frames, bodies, records, Joint Origins, variants |
| aruco_trim_lab.py | 623 | yes | 0 | 0 | 0 | 623 | Trim excess gate |
| aruco_ui_config.py | 61 | no | 0 | 0 | 61 | 0 | UI switches |
| aruco_ui_lab.py | 506 | yes | 0 | 0 | 0 | 506 | UI v2 Fusion checks |
| bam_fusion_ui.py | 1096 | lazy | 0 | 0 | 1096 | 0 | the dialog kit (routing, tabs, icons, validation, palette, arrows) |
| **total** | **47410** | | **5143** | **11140** | **7294** | **23833** | |

Notes on the table:

- `bam_fusion_ui.py` is all U, but about 400 of its lines are Fusion-free and tested offline (the Issue / Validator model, the Layout routing stand-ins, HtmlChannel, the arrow maths). They are UI framework, not marker logic, so they stay with the UI.
- The HTML preset library is not a `.py` file. `ArucoMarkers/resources/preset_library/` holds 2,279 lines (index.html 61, library.js 305, library.css 173, bam_channel.js 60, icons.js 54, demo_state.js 1,626). The page is host-agnostic by design: `bam_channel.js` is the only Fusion-aware part. It is a candidate for the Studio's own preset UI.
- The core already outside Fusion: `aruco_autosize` 1862, `aruco_board` 343, `aruco_chamfer` 374, `aruco_dict` 237, `aruco_label` 3149, `aruco_numbering` 1292, `aruco_origin` 166, `aruco_slabs` 442, `aruco_trim` 470, plus `markers.py` 1428 (TagSpec, TagDef, resolve, plan_serials, cell_boxes, sidecar files).

## Detailed responsibility list

Per file. Function names and line ranges, grouped by class.

### ArucoMarkers.py (77)

- (F) `run` L20-51: register the feature definitions, the commands, the sync hooks, arm the bridge. `stop` L54-77: the reverse.

### aruco_actions.py (1882)

All (T). One name, one function, `ACTIONS` L1702. Groups:

- Document guards: `_mine` L47, `_require_mine` L55, `_quiet_or_raise` L578, `_on_demo` L587, `_pick_doc` L1125, `_close_mine` L1570, `_open_user_doc` L1587.
- Read-only inspection: `_user_tags` L240, `_user_refs` L324, `_user_material` L364, `_inspect_records` L675, `_list_documents` L741, `_live_status` L876, `_diag_modules` L915, `_inspect_design` L976-1104, `_jo_report` L1107, `_jo_census` L1144, `_jo_extras` L1160, `_extrude_edit_diag` L1211-1302, `_extrude_node_detail` L1305-1388, `_api_doc` L1391, `_api_names` L1402, `_doc_ident` L1437, `_face_report` L1502, `_list_commands` L1554, `_ids_status` L1650, `_ids_node_check` L1656.
- Scripted writes on Zach's documents, each with a confirm guard: `_user_serials` L106, `_user_ids` L175, `_user_show` L420, `_export_preview_cleanup` L273, `_jo_cleanup` L1177.
- Lab launchers: `_lab` L966, `_live_test` L960, `_modes_fixture` L707, `_camera_capture` L616, `_demo_send` L763, `_register_commands` L1547, `_menu_hooks` L1428, `_start_addin` L894, `_restart_addin` L928 (disabled).
- Recovery: `_finish_edit` L506, `_finish_base_feature_cmd` L532, `_close_stray_fixture` L723.

### aruco_autosize_gallery.py (373)

- (C) `FACES` L30, `TYPED` L57, `_arc_pts` L71, `shape_pts` L81-103, `loops_mm` L106, `loops_m` L110, `bbox_mm` L114, `summary` L120-134: ten faces (holes, slots, D-shapes) as millimetre primitives, tessellated the way Fusion strokes an edge (chord tolerance 0.05 mm). Shared with `tests/test_aruco_autosize.py`.
- (T) `_draw` L144, `build_face` L182-213, `_top_shot` L239, `run_fusion` L257-373: draw and extrude each face, tag it by the face-click path, capture it.

### aruco_bridge.py (252)

All (T): `_state` L41, `_write_json` L55, `_reload` L66, `_user_dialog` L75-96 (refuse while the user has a dialog open), `_dispatch` L107-165, `_worker` L176, `arm` L195-233, `disarm` L236.

### aruco_cf_probe.py (1388)

All (T). The 2026-10-07 research probe that proved a tag can be one custom feature. `register` L135, `host` L256, `make_tag` L455-556, `rebuild` L402, `run` L848-1146, `matrix` L1182, `demo` L1240, `fallback` L1272. Two small pure pieces (`split_black` L328, `spec_of` L347) were re-done in aruco_feature. Nothing here ships.

### aruco_chamfer_lab.py (679)

All (T): `verify` L167-268 (a marked tag measured on its bodies), `layout_case` L308, `edit_case` L351, `dialog_case` L444, `variant_case` L551, `chamfer_test` L626.

### aruco_commands.py (1498)

- (C) `_split_black` L88, `_export_info` L669-719 (the info line: exactly what OK writes and where), `eta_text` L780, `progress_message` L793, `_export_rows` L996-1023, `_dup_rows` L1026, `_export_status` L1031, `_tick_part` L1060, `_set_tick` L1068, `_plural` L665, `_part_tip` L1052. Rules for the Export dialog's words and rows.
- (F) `_TagExecute` L416-437, `_EditExecute` L542-560, `_tag_owner` L442, `_tile_mode` L320, `_target_size_cm` L348, `_open_project` L1287, `export_execute` L1166-1212, `_legacy_export_execute` L1319.
- (U) `register` L1438-1475 and `unregister` L1478 (panel, buttons, icons), `_TagCreated` L265-305 and `_TagChanged` L365-413 (the old ArUco Tag dialog), `_EditCreated` L485, `_EditChanged` L516, `_IdsCreated` L569, `export_created` L860-993, `_export_refresh` L722, `_export_changed` L1114, `export_valid` L1155, `_progress_dialog` L805-854, `_SendCreated` L1347, `_SendExecute` L1374, remembered values `_recall` L177, `_restore` L186, `_remember` L197, `_dropdown` L227.
- (T) `_survives_reload` L62, `_rescue_export_parts` L1232, the dead pre-types dialog L1304-1339.

### aruco_core.py (52)

- (F) `load` L22-40, `module` L43: load `bam_cad_core` under the alias `arucocore`, because Fusion runs every add-in in one CPython and the CAD Exporter purges every `bam_` module on each press. Packaging, not logic.

### aruco_demo.py (284)

All (T): `build` L45-152 (the Arm demo, 12 tags), `capture` L155, `build_ui_fixture` L175, `modes_fixture` L197, `_one_mode` L216.

### aruco_edit_gates.py (1727)

All (T). Groups: `sync_group` L151, `restructure_group` L276, `deps_group` L386, `atomic_group` L445, `warnings_group` L483, `combined_group` L576-679, `jo_one_group` L893, `jo_joint_group` L929, `jo_probes_group` L959-1054, `edit_route_group` L1122, `dialog_made_group` L1200, `edit_menu_group` L1278-1359, `deps_each_group` L1410, `park_probe_group` L1496. Pacing: `quiet` L737, `_recovery_sig` L706, `unsaved_user_docs` L763, `in_new_doc_safe` L1536-1579. Driver `edit_gates` L1611-1727.

### aruco_edit_test.py (870)

All (T): `bar` L100, `snapshot` L210, `diff` L250, `jo_state` L265, `census_ok` L287, `unhealthy` L305, `edit` L329-380 (Fusion's edit route as a double-click), `roundtrip_case` L421-565, `old_node` L568, `orphans` L711, `methods` L752, `edit_test` L812.

### aruco_export.py (680)

- (C) `_slug` L31, `SLOTS` L41, `_labels` L75-87 (components that share a name get " <1>", " <2>"), `body_role` L123-135 (cells or tile by body name), `print_rows` L309-334 (the Export table's rows), `tag_parts` L406, `KINDS` L449, the per-kind rule inside `export` L542-566 (which files each type writes).
- (F) `_comp_key` L53, `_copies_by_component` L63, `_print_records` L90, `_black_bases` L112, `ids_parts` L138-187, `_bodies_of` L190, `part_body_counts` L219, `print_targets` L228-306, `send_selection` L337-386, `_harvest_joint_origins` L389, `_project_file` L424, `_write_body_stls` L453-539 (Fusion's STL exporter, oriented for printing), `export` L542-680 (refresh_live, collect, aruco.json, joint_origins.json, print beds).

### aruco_export_lab.py (373)

All (T): `_dialog` L82-186, `preview_lifecycle` L189, `_rules` L258 (what each type may and must write), `run` L290.

### aruco_export_preview.py (260)

- (C) `row_for_path` L123-137, `_ids_text` L177.
- (U) `clear` L71, `row_for` L114, `_bbox` L140, `_box` L158, `_label` L182, `show` L203-260: orange boxes on ticked parts, grey on unticked, the shared magenta highlight. Drawn from `executePreview` only.

### aruco_extrude_cmd.py (2860)

- (C) Defaults and limits: `defaults` L286-299, `_base_from` L302, `_limits` L317, `label_defaults` L1172. Presets in the dialog: `_catalog` L599, `_cell_line_mm` L614, `_cells_labels` L619, `_choice_of_cells` L627, `_cells_remembered` L671, `preset_values` L692-748, `_same_value` L788, `_after_dictionary` L934, `cells_values` L1037, `_size_sig` L1045, `_cells_for` L1059. Info lines and warnings: `cells_line` L1128-1143, `layer_lines` L1146, `_cell_warnings` L1159, `label_entries` L1425, `label_lines` L1442, `info_rows` L1447, `_edit_kind_line` L2209-2245, `_preset_lines` L2470, `_mark_line` L2483, `_pin_line` L2493, `_mm_text` L2507, `size_line` L2513-2528, `_origin_line` L2053, `trim_lines` L2669-2699, `trim_issues` L2650-2666 (the one source of Trim's validation messages). Value mapping: `values` L1675-1723 (inputs to settings and numbers in mm), `resolve_mode` L1726, `label_values` L1284-1327, `trim_values` L2591, `_stored_label` L1258, `_same_label_settings` L1269, `same_build` L2156, `_check_auto` L2169-2202.
- (F) `_target` L1732-1758, `_body_name` L1761, `_target_info` L1774, `_candidate_source` L1953, `_prefer_profile` L1919-1950 (a face click inside a sketch's closed area means the profile, like Extrude), `_host` L2133, `_evaluate` L2145 (cached `aruco_feature.evaluate`), `_white_top_now` L1835, `_toolbar_edit` L2558-2572, `_CreateExecute` L2830-2851, `_confirm` L823.
- (U) `build` L333-529, `_build_presets` L542, `_build_cells` L569, `_build_print` L587, `_build_label` L1183-1255, `build_trim` L2575, `_show_cells` L634, `_cells_tip` L647, `_take_cells` L660, `apply_preset` L751, `_apply_cells_of` L796, `_ask_name` L811, `_take_preset` L835-931, `_import_items` L944, `_show_presets` L957-999, `_set_preset_items` L1002, `_show_print` L1025, `_fill_print_from` L1071, `_fill_cells` L1095, `_fill_label` L1330, `_row_items` L1365, `_take_label` L1378, `_set_info` L1459, `_typed` L1475, `_show_label_position` L1483, `_set` L1510, `_restore` L1529, `_restore_preset` L1553, `remember` L1574, `_fill_from` L1611-1652, `_fresh_id` L1655, `_visibility` L1789, `_sync_fields` L1815, `_take_change` L1841, `_manip` L1876 and `_place_handles` L1884-1916 (the arrows), `_set_fit_items` L1973, `_set_items` L1984, `_origin_items` L1998, `_take_origin` L2006, `_show_mark` L2024, `_take_mark` L2035, `_mark_items` L2045, `_fill_candidates` L2060-2097, `refresh` L2119, `_refresh` L2248-2467 (the 220-line state machine), `fill_trim` L2606, `reset_trim` L2620, `show_trim_rows` L2631, `validate` L2702, `preview` L2711, `_Changed` L2732, `_Preview` L2748, `_hud_focus` L2766, `type_at_arrow` L2775, `_ArrowType` L2798, `_Destroy`, `_Validate`, `_Activate`, `_Created` L2811-2860.
- (T) `_X` carry-over across reloads L192-253, `_ui_hook` L2100.

### aruco_extrude_lab.py (1300)

All (T): `gim_fixture` L78, `appearances` L149, `cross_case` L233-364, `guard` L381, `in_new_doc` L423, `colour_stages` L442-592, `colour_probe` L600, `_open_dialog` L739, `_drive` L759, `fresh_defaults` L802, `dialog_checks` L826-930, `preview_bench` L933-1080, `ui_fixture` L1097, `ui_open` L1131, `ui_state` L1169, `ui_close` L1235, `probe_doc` L1264.

### aruco_extrude_sync.py (571)

- (C) `doc_key` L97, `verdict` L115, `BUDGET_MS` L125. The decision policy itself is already in the core (`aruco_numbering.auto_decision`).
- (F) `after_compute` L128-195, `idle_reason` L200-220, `still_stale` L223, `prune_closed` L252, `maybe_refresh` L266, `_on_refresh_execute` L310-362, `_on_starting` L365, `_on_terminated` L384, `_on_document` L406, `_retry_later` L419, `_on_sync` L440, `install_hooks` L490-526, `uninstall_hooks` L529, `status` L565.

### aruco_extrude_ui.py (1369)

- (C) `round_line` L794-815 ("= 28.56 mm · 7 cells × 4.08 mm · 6 lines of 0.68"), `snap_size` L949-974, `_fit_key` L980, `json_key` L992, `_size_limit` L997-1025, `_level_of` L1034, `info_lines` L1048, `classify` L1055-1090 (info lines to Issues), `_short_note` L1096, `label_issues` L1114-1150, `trim_issues` L1153, `collect` L1167, `_visible_anchor` L1191, `ok_text` L1209.
- (U) `build` L224-276, `_make_containers` L279, `_extras` L313-379, `_make_preset_row` L382, `_make_library_group` L433, `_after_build` L447, `_tabs_of` L482, `before_refresh` L522-608, `after_refresh` L611, `_decorate` L641, `_show_up_row` L666, `_show_start` L687, `_show_pins` L706, `_show_label_rows` L724, `_show_preset_row` L738, `_show_round` L769, `_show_layers` L818, `_place_arrows` L845-909, `_active_tab` L916, `type_at_arrow` L931, `size_drag_end` L941, `show_issues` L1221, `validate` L1231, `open_library` L1246, `apply_preset` L1259, `_apply_now` L1287, handlers L1316-1369.

### aruco_feature.py (3769)

- (C) Settings and their rules: `default_settings` L408-450, `size_is_auto` L453-465, `has_frame_sketch` L468, `trim_setting` L476, `normalise` L490-510 (the old `chamfer` checkbox reads as `cut`), `default_numbers` L513, `effective_op` L521, `resolve_follow` L528, `plan_of` L536, `structure` L545, `node_structure` L575, `is_legacy` L1854, `follow_expression` L1860, `_norm_expr` L1894, `params_for` L2561, `_mm_expr` L2577, `is_info` L265. Geometry from numbers: `_v` to `_rotz` L585-605, `_xf_frame` L684, `cells_of` L799, `_layout_rect` L804-821, `_chain` L824-839, `_inside_loops` L867, `_is_box` L975, `_loops_mm` L1026, `_label_key` L1042, the body of `evaluate` L1118-1309 once its inputs are numbers (fit on loops, the Origin turn, the mark, the label, the pins, the trim), `turns` L1312, `keep_x` L1318-1334, `face_origin` L1368, `mark_frame` L1379, `_footprint` L1415, `_trim_column` L1648, `_trim_eval` L1687-1731, `_trim_not_in_place` L1747, `trim_notes` L1538, `optical_of_ev` L2673. The edit model: `settle` L2323-2350, `keep_black_step` L2879-2899, `_merged` L2902-2939, `structural_change` L2942, `edit_kind` L2952-2963, `_settings_key` L3038, `_edit_changes` L3044, `rebuild_reason` L550-572 (the words). Records: `record_same` L3153, `frame_digest` L3176, `ev_digest`, `record_digest` L3190, `_same_label` L3198, `x_ref_from_record` L3213, `origin_of` L3235, `mark_record` L2725, `label_record` L2733, `record_extras` L2745, `_label` L2092 (the node's name), `node_warning` L2102.
- (F) Registration and handlers: `register` L315-359, `unregister` L362, `_Compute`, `_Starting`, `_EditCreated`, `_AutoCreated`, `_CmdEvent` L279-305. Reading Fusion: `native_of` L608, `_profile_points` L617, `sketch_axes` L632, `profile_rect` L639-663, `_matrix`, `_xf_point`, `_xf_vector` L666-681, `to_root_matrix` L690, `ev_in_root` L709, `host_of` L722, `body_under` L738, `creation_settings` L759-794, `profile_loops_2d` L842, `profile_at` L879-942, `_doc_key_of` L945, `_face_loops_m` L990, `label_name` L1004, `label_for` L1054-1115, `_trim_face_body` L1553, `_trim_inputs` L1570-1610, `_body_extent_mm` L1613, `_trim_measure` L1657, `settings_of` L1909, `numbers_of` L1929, `target_of` L1951, `is_ours` L1959, `design_of` L2136, `is_active` L2160, `find_feature` L2794, `component_of`, `record_of` L2800-2808. Bodies: `_tbm`, `_box`, `_union` L1339-1361, `tile_temp_body` L1374, `_tile` L1386, `white_temp_body` L1394, `pattern_temp_body` L1432, `_prism` L1438, `pins_temp_body` L1476, `pin_body` L1484, `pocket_body` L1489, `recess_body` L1495, `part_body` L1510, `trim_body` L1734, `_base_body` L1766, `_update` L1779-1809, `_combine` L1812, `_base_feats` L1821, `parts_of` L1826, `base_features` L1838, `_param` L1846, `white_top_of` L1874, `link_black` L1878, `black_follows` L1898. The node: `_on_compute` L1966-2046, `_sync_hook` L2049, `_dependency` L2073, `_nudge` L2116, `_new_key` L2125, `clear_selections` L2168, `create` L2178-2320, `_combines` L2353, `_wrap_first` L2379-2411, `_tile_faces` L2414, `is_piece_of` L2437, `tile_pieces` L2447, `paint` L2470-2501, `paint_all` L2504, `joined_body` L2533, `paint_node` L2546, `_group` L2581 (the fallback timeline group), `_release` L2614, `_wrap` L2629-2668, `_sketch_pt` L2682, `make_frame_sketch` L2686, `move_frame_sketch` L2704, `_write_record` L2756, `_roll_to` L2813, `_roll_back` L2841-2876, `apply_edit` L2966-3035, `edit` L3059, `_forget` L3066, `_finish_edit` L3084, `refresh_one` L3120, `_adopt_x_ref` L3246, `refresh_live` L3256-3324, `_node_of_entity` L3329, `_selected_ours` L3345, `node_for_toolbar` L3442, `_on_starting` L3458, `_target_cf` L3486, `_on_edit_created` L3515, `_edit_activate` L3545, `_edit_execute` L3573-3652, `_edit_destroy` L3655, `_on_auto_created` L3671, `_auto_execute` L3680, `in_command` L3701.
- (U) The right-click entry: `_menu_commands` L3368, `_on_menu` L3389-3423, `_Menu` L3426, `install_menu_hook` L3431.
- (T) `_edit_log` L3500, `_pump` L3693, `scripted_edit` L3719-3753, `computes_since` L3756, `status` L3764, `KEEP_COMMANDS_ON_STOP` L189.

### aruco_heights_lab.py (1284)

All (T): `heights_case` L149, `follow_case` L211-304, `measure_pins` L320, `pins_case` L371-475, `_Isolate` L483, `pin_shots` L515, `frame_shot` L545, `legacy_tag` L601-660, `migration_case` L673, `turns_case` L742-842, `split_case` L862, `flip_case` L1016, `wrap_first_probe` L1083, `fallback_case` L1146, `heights_test` L1185, `expr_probe` L1261.

### aruco_ids_accept.py (5661)

All (T). Guard and documents: `_assert_mine` L71, `_pump` L81, `_new_doc` L109, `_close` L120, `clean_extra` L169, `_give_back` L207. Fixtures: `plate` L255, `new_part` L283, `make_tag` L298, `ensure_saved` L372, `build_disc` L413, `build_arm` L434, `Fx` L1088, `f1`-`f17` L1125-3501, `drill` L1593, `holed_board` L1662. Measures: `inventory` L460, `world_of` L646, `truth` L699, `parts_timeline` L731, `rendered` L826, `decode_rendered` L865, `probe` L904-995. Gates: `fixture_gates` L2031-2177, `dialog_gates` L2241-2371, `robustness_gates` L2435, `refresh_gate` L2505, `upstream_gates` L3055-3165, `byhand_gates` L3581-3703, `colour_gates` L4140, `persistence_gate` L4323, `run` L4402, `_run` L4487. Probes: `deps_probe` L3168, `copy_probe` L3242, `node_probe` L3336-3470, `tl_probe` L3719-3813, `rack_check` L3816, `paint_probe` L3899-4036, `repaint_user` L4039, `paint_store_probe` L4173-4300, `delete_probe` L4631, `nested_move_probe` L4680. E2E: `_world_frames` L4783, `_part_vs_copy` L4878-4978, `material_check` L5036, `label_check` L5095, `_export_stl` L5180, `_renders` L5341, `wide_render` L5424, `e2e` L5505-5661.

### aruco_ids_cmd.py (535)

- (C) `_how` L206-231 (the Status words), `_tone` L234, `_status_cell` L246, `_marker_rows` L252.
- (F) `_part_paths` L197, `_activate` L474 (refresh lagging records once), `_execute` L508 (apply).
- (U) `created` L143-194, `fill_table` L260, `_nav` L294, `status` L315, `_refresh_rows` L354, `replan` L382, `_redraw` L397, `_changed` L412-457, `select` L460, `valid` L470, `_preview` L496, `_destroy` L523, handlers L107-138.

### aruco_ids_feature.py (3721)

- (C) `Labels` L946-978 (component labels, duplicates numbered), `_variant_info` L981, `read_ledger` L1194 (parse), `stamp_chains` L1242, `resolve_hidden` L877, `plan_design` L1377-1409, `part_plan` L1431, `id_regions` L1626, `label_slots` L1641, `label_warning` L1660, `part_paint_plan` L2309-2360, `_part_label` L2438, `_unique_name` L2448, `_drift` L2919, `_body_sig` L3044, `staleness` L3098-3166 (the reasons and the digest, once inputs are numbers), `auto_verdict` L3248, `_warning_text` L3257, `export_overrides` L3700, `node_state` L847.
- (F) Everything else. Registration and hooks: `register` L616, `_register` L630, `unregister` L674, `install_hooks` L571-613, `_selected_nodes` L327, `_on_starting` L352-399, `copies_delete_plan` L409-467, `delete_copies` L470, the delete / rebuild / repaint / warn commands L498-568 and L3579-3687. Reading: `_design` L725, `is_ours` L734, `find_node` L748, `_health_states` L761, `_ids_group` L774, `node_status` L787-838, `node_live` L841, `node_hidden` L859, `remember_hidden` L897, `part_features` L909, `occ_at` L929, `_record_live` L993, `collect_design` L1005-1181, `_native` L1186, `write_ledger` L1204, `read_stamps` L1209, `record_ledger` L1267, `_freshen` L1310-1374, `inputs_of` L3062. Parts: `part_bodies` L1457-1524, `pattern_pieces` L1527, `union_extents` L1544, `tile_pieces_of` L1553, `_op` L1587, `_copy_union` L1606, `_rect_prism` L1614, `_recolour` L1675-1763, `_recut` L1766, `_appearance` L1808, `_resolve_app` L1820, `_paint` L1842, `_paint_durable` L1858, `_copy_face_colours` L1887-1969, `_target_body` L1977, `_dependency_entity` L1994, `build_node` L2038-2145, `generated_occurrence` L2148, `generated_for` L2173, `_free` L2214, `_make_part_occurrence` L2227-2288, `_add_part_bodies` L2291, `parts_paint_report` L2375, `repaint_parts` L2403, `part_occurrences` L2460, `part_body_proxies` L2488, `part_joints` L2499, `remove_parts` L2521, `_group` L2560, `_release` L2592, `migrate` L2605, `apply` L2658-2729, `apply_hidden` L2732, `after_tag_change` L2761, `rebuild_parts` L2776, `delete_node` L2789, `sync` L2805, `_on_terminated` L2830, `_on_document` L2845, `_on_sync` L2852-2914, `_on_compute` L3265-3349, `maybe_rebuild` L3357-3452, `_note_blocked` L3455, `paint_drift` L3478, `maybe_repaint` L3527, `parts_by_hand` L3169-3231, `_doc_is_mine` L3234, `_auto_here` L3243, `nudge` L3690.
- (T) `_on_compute_v1` L2943-3039 (kept for the mutation test), `status` L3711, `_rebuild_log` L3352, `_repaint_log` L3522.

### aruco_ids_follow_probe.py (1237)

All (T): `make_part` L46, `probe` L102-332 (M1-M6), `drive_check` L335, `joints_of_fixture` L373, `suppress_check` L409, `nested_probe` L561-723, `copy_probe` L762, `delete_probe` L846-964, `deltest_probe` L967, `deltest2_probe` L1109.

### aruco_ids_preview.py (260)

- (C) `_cols` L112, `_add_box` L121 (a box as 12 triangles), `spec_of` L156, `specs_of` L163, `marker_row` L171.
- (U) `clear` L76, `reset` L95, `_mesh` L134, `_label` L151, `show` L183-255, `look_at` L258.

### aruco_ids_rack.py (203)

All (T): `inv_hash` L52, `_records` L60, `_renders_plain` L67, `stage` L124-203.

### aruco_ids_stability.py (428)

All (T): `Copies` L53, `census` L126, `persist_check` L153, `run` L196-428.

### aruco_ids_test.py (826)

All (T). The retired per-level flow plus read-only inspection: `build` L215, `placements` L272, `measure` L469-587, `shot` L597, `inspect` L679-777, `joints_of` L780.

### aruco_label_lab.py (993)

All (T): `verify` L150, `capture_tag` L207, `node_case` L300, `edit_case` L362, `dialog_case` L415, `variants_case` L488, `ids_case` L543, `warn_case` L593-704, `position_case` L707-907, `label_test` L958.

### aruco_live_test.py (795)

All (T): `_jo_check` L190-263, `capture_tags` L271, `run` L353, `_run_main` L385-657, `jo_probe` L660, `jo_probe_profile` L720.

### aruco_marker_table.py (986)

- (C) Names and rows: `name_of` L85, `split_name` L90, `natural_key` L95, `family` L101, `where` L107, `kind_text` L117, `dict_text` L125, `ids_text` L130, `status_html` L137, `MarkerRow` L147-179, `spec_info` L182, `make_row` L208, `_frame` L225, `frame_of_matrix` L233, `order` L238, `duplicates` L243, `ratio` L254, `column` L259, `cell_id` L263. Clicks: `double_click_s` L270, `message_ms` L282, `click` L293-322, `busy` L325-348, `_win_times` L460. Picking and camera: `_dist2` L353, `match_pick` L357-404, `view_for` L409, `inside_box` L423. Navigation state: `nav_new` L480, `nav_update_rows` L490, `selected_row` L497, `select` L503, `_zoom` L510, `_choose` L524, `_show_in_table` L531, `handle` L551-625, `follow_table` L628, `_pick` L644, `_point` L674, `pick_path` L682. Tested offline by `tests/test_aruco_marker_table.py`.
- (U) `_cast` L694, `icon_dir` L703, `add_table` L709, `add_row` L719-755, `add_navigation` L758, `set_cell` L772, `clear_pick` L784, `recall_zoom` L800, `remember_zoom` L811, `outline` L826, `text_label` L848, `draw_highlight` L871, `tag_group` L892, `clear_groups` L899, `zoom_to` L914, `zoom_frame` L921.
- (T) `_st` L439, `events` L451, `_log` L471, `_MouseProbe` L957, `probe_mouse` L973.

### aruco_marker_table_lab.py (581)

All (T): `build` L103, `ids_checks` L142, `_nav_checks` L203-280, `export_checks` L323-399, `run` L404, stages L418-577.

### aruco_origin_lab.py (456)

All (T): `origin_check` L124-174, `create_case` L177, `edit_case` L211, `variant_case` L278, `dialog_case` L335, `origin_test` L397.

### aruco_preset_library.py (825)

- (C) The recent list: `library_path` L59, `_load` L63, `_save` L79, `recent` L94, `add_recent` L99, `forget_recent` L109. Words and cards: `subtitle` L133, `lines_per_cell` L143, `cells_words` L155, `info` L165-189, `edit_schema` L193-225, `set_path` L228, `thumb_svg` L236-282, `_cells_from` L287, `same_print` L347, `group_nodes` L357-377, `Library` L382-575 (cards, filters, select, new, duplicate, save, delete, import; every source injectable).
- (F) `preset_of_node` L300-335 (reads a node's settings and numbers), `document_nodes` L796-825 (rolls the timeline).
- (U) `LibraryWindow` L583-725, `_ui` L728, `_over_canvas` L733, `theme` L745, `_log` L756, `_apply` L764, `_catalog_changed` L769, `_pending` L781, `open_for_dialog` L789.

### aruco_presets.py (570)

All (C): `default_preset` L116-137, `from_profile` L140, `normalise` L184-227, `line_mm` L230, `cell_setting` L236, `min_text` L248, `parse_min` L256-275, `changes` L291, `same` L310, `describe_changes` L326, `load` L342, `save` L382-414 (atomic), `builtins` L419, `catalog` L431, `find` L446, `valid_name` L454, `unique_name` L464, `save_as` L474, `update` L489, `delete` L500, `set_last` L512, `import_profile` L525, `layer_note` L543-570. It reads and writes `%USERPROFILE%/CADExporter/aruco_presets.json`; only the path is Fusion-flavoured.

### aruco_preview.py (542)

- (C) `_add_box` L71, `_add_prism` L97-120, `_mark_kind` L123, `_cells_z` L128, `boxes` L137-180 (white and black boxes from evaluate()), `label_boxes` L183, `_top_cm` L203, `_label_strokes` L214, `label_warning` L234, `label_guides` L258, `mark_prisms` L307, `pin_prisms` L332, `triad` L356, `trim_boxes` L400. This is the 3D view's mesh list.
- (U) `clear` L42, `leftover_groups` L57, `_mesh` L84, `_add_outline` L285, `_add_triad` L369, `show_trim` L419-464, `show` L467-542.

### aruco_probe.py (243)

All (T): `run` L24-243, the 2026-10-07 one-shot API probe (TBM corner contacts, updateBody, per-path visibility, where occurrence attributes live).

### aruco_prusa.py (273)

All (C): `config_dir` L52, `read_ini` L74, `read_bundle` L86, `_system` L120, `user_prints` L139, `resolve` L148-169, `length` L182, `nozzle_of` L194, `width_of` L208, `profile` L226-242, `aruco_profiles` L245, `describe` L259.

### aruco_restructure.py (565)

- (C) `has_combine` L64, `restructure_plan` L72-93 (delete roles, create roles, changed combines), `new_parts` L122, `needed_params` L126, `refusal` L130-149 (the words), `lost_after` L536, `what_goes` L558.
- (F) `node_roles` L96, `_regroup` L166, `restructure` L186-329 (release, delete, create, regroup, atomic), `_body_of` L334, `_refs` L353-442 (what a downstream item references), `node_bodies` L445, `dependents_of` L472, `downstream_snapshot` L513.
- (T) `FAIL_AT` L43, `_inject` L59.

### aruco_settings.py (326)

- (C) `_normalise` L58, `load` L79, `save` L90-115, `design_key` L118, `_merge` L126, `recall` L135, `remember` L146-164, `snapshot` L177, `_registry_exe` L267, `find_prusaslicer` L291, `open_in_prusaslicer` L313 (Windows, not Fusion). The file is `%USERPROFILE%/CADExporter/_aruco_settings.json`.
- (U) `_select` L204, `apply` L224-262 (remembered values into dialog inputs).

### aruco_tags.py (3550)

- (C) Vectors: `_v` to `_rot` L78-107 (Rodrigues). Marks and labels as numbers: `_area2` L373, `mark_parts` L382, `label_of` L448, `label_joins` L489, `label_white_rect` L522, `label_fill_rects` L529, `copy_label` L566. Records: `is_variant_record` L612, `template_records` L618, `label_settings_same` L2827, `_in_label` L2817, `_footprint_cm` L2791-2814, `_extents` L2771, `_is_white` L2784, `_body_sig` L3163, `_sources_sig` L3170, `_variant_name` L3100, `summary` L3540. Frames: `optical_frame_cm` L911-924 (OpenCV's frame from a record), `has_old_frame` L927, `_frame_error` L939, `_solve3` L1161, `_jo_key` L1997, and the composition maths in `_place_joint_origin` L1172-1221 (how Fusion builds a Joint Origin from angle, offsets and flip).
- (F) Frames from Fusion: `face_frame` L112-148, `face_loops_2d` L151, `face_best_rect` L171, `candidate_bodies` L194, `external_owner` L209, `profile_frame` L223-300. Temporary bodies: `cells_temp_body` L305-333, `poly_prism_temp_body` L336, `mark_cells` L393, `mark_white` L412, `mark_tile` L424, `label_temp_body` L462, `mark_label` L498, `label_fill` L544, `square_temp_body` L584, `_slab` L3105, `_fill_box` L3149. Records on components: `read_tag_records` L597, `write_tag_records` L608, `find_record` L629, `record_is_live` L641, `live_tag_records` L669, `next_free_id` L699, `read_overrides` L2612, `write_override` L2638, `collect` L2664-2717, `occurrence_refs` L2720, `resolve_live` L2734, `_node` L2839, `pattern_body` L2857, `record_drift` L2877-2934, `evaluated_record` L2937, `fresh_collect` L2974-3026. The 2026-10-07 tag: `add_tag` L708-788, `_pocket` L791, `aruco_extrude` L804, `set_tag_spec` L847-903. Joint Origins: `_tag_face` L963-1014, `_jo_add` L1061, `_delete_quietly` L1072, `_jo_read` L1091, `_jo_probe` L1103, `_jo_tokens` L1112, `_sweep_new` L1127, `_place_joint_origin` L1172-1221 (the Fusion half), `_feature_of` L1233, `_roll_before` L1242, `_roll_restore` L1252, `_roll_after` L1266, `frame_sketch_of` L1296, `frame_entities` L1316, `frame_points` L1328, `frame_sketch_frame` L1335, `_on_sketch` L1347, `_jo_on_sketch` L1359, `_ensure_jo_after` L1385-1464, `_anchors` L1467-1499, `_face_under` L1502, `_solve_on` L1527, `ensure_joint_origin` L1547-1584, `_same_anchor` L1587, `_move_in_place` L1598-1665, `_tag_jo_lookup` L1668, `_adoptable` L1678, `_ensure_joint_origin` L1715-1859, `joint_origin_of` L1862, `joint_origin_matches` L1871, `ensure_frames` L1970, `node_gone` L2007, `prune_tag_joint_origins` L2019, `_node_by_key` L2396, `_live_record` L2411, `fix_tag_jos` L2423-2495, `remove_tag_jo_extras` L2580, `_tl_index` L2387. Variants (the pre-IDs-node per-copy parts): `_occ_at` L3034, `_rel_transform` L3050, `place` L3076, `_copy_face_colours` L3187, `_joint_geometry` L3216, `_build_variant` L3248-3352, `_existing_variants` L3355, `_variant_current` L3368, `apply_variants` L3391-3537.
- (T) Read-only census and diagnostics: `joint_origin_report` L1891-1967, `_jo_detail` L2050, `joint_origin_census` L2097-2202, `_joint_users` L2213, `_to_tag_frame` L2238, `_record_jo_fields` L2258, `_extras_in` L2273-2384, `tag_jo_extras` L2510, `_own_design` L2540, `_jo_inventory_all` L2550, `_doc_name` L2573.

### aruco_trim_lab.py (623)

All (T): `plan_now` L147, `extent` L164, `trimmed_err` L172, `make_by_dialog` L220, `after_trim` L249, `colours` L272, the groups L290-561, `trim_test` L569.

### aruco_ui_config.py (61)

All (U): `UI_V2`, `HUD_FOCUS`, `ARROW_TYPE_BOX`, `ARROW_PICK_PX`, `ROOT_ROWS`, `PRESET_ROW`, `TAB_ICONS`, `HANDLES_BY_TAB`, `SIZE_SNAP`, `LIBRARY_HOST`.

### aruco_ui_lab.py (506)

All (T): `v2_fixture` L85, `v2_view` L117, `v2_expand` L140, `v2_tips` L154, `v2_ok` L168, `v2_arm` L201, `v2_open` L208, `v2_state` L256-347, `v2_tab` L350, `v2_script` L368-458, `v2_close` L461.

### bam_fusion_ui.py (1096)

All (U), a reusable dialog kit. Routing: `FlatGroup` L74, `GroupProxy` L96, `Layout` L111-183, `RoutedInputs` L186, `_Swallowed` L207, `RoutedCommand` L222. Tabs and icons: `add_tab` L253, `icon_dropdown` L261, `ensure_icons` L275-303, `button_row` L306, `row_index` L315, `select_index` L322, `set_row` L332, `checkbox_group` L350-382. Validation: `set_theme` L400, `Issue` L414, `worst` L430, `head_of` L435, `summary_text` L442-473, `Validator` L480-631. Pages: `HtmlChannel` L658-725, `PaletteWindow` L760-831, `BrowserHost` L834-887. Arrows: `Arrows` L893-931, `dist_point_segment` L947, `nearest_arrow` L957, `tip_cm` L974, `release_selection_focus` L980, `arrow_of` L997, `arrow_at` L1012, `type_into` L1034, `ask_text` L1056, `ArrowTyping` L1066-1096.

## The versioned rules

These must stay bit-for-bit in the core, with their numbers, so a Fusion adapter can rebuild today's tags identically. Every existing tag carries the rule it was made under; a tag never changes on its own.

| rule | value | where today | what the number means | pinned by |
|---|---|---|---|---|
| spec version | `SPEC_VERSION = 2`, settings `"v"` | aruco_feature.py L138 | the settings dict's shape; `normalise` L490 maps older shapes | test_aruco_edit_roundtrip.py |
| size grid | `CELL_RULE = 1`, settings `"cells": {"rule": 1, "of": "cell" or "marker", "mm", "min_mm"}` | bam_cad_core/aruco_autosize.py L187; mirrored aruco_presets.py L71 | no `"cells"` on a tag = the legacy rule: marker and checker in 0.5 mm steps, a typed size as typed | test_aruco_cells.py, test_aruco_cells_legacy.py |
| label rule | `RULE = 2`, `RULES = {1, 2}`, label `"rule"` | bam_cad_core/aruco_label.py L270-286 | rule 1: 2 modules clear of the black (labels stored before 2026-10-13, no `"rule"` key); rule 2: the quiet ring is the hard line, 0.25 module preferred | test_aruco_label_rule1.py, test_aruco_label.py |
| origin rule | `ORIGIN_RULE = 2`, settings `"origin_v"` | bam_cad_core/aruco_origin.py L46 | a node without `origin_v` keeps a rectangular board's 90 / 270 as laid out; with it, cols / rows are swapped | test_aruco_frame.py |
| trim rule | `RULE = 1`, settings `"trim": {"rule": 1, "axes", "margin_mm", "force"}` | bam_cad_core/aruco_trim.py L65 | another rule number reads as off | test_aruco_trim_legacy.py, test_aruco_trim.py |
| Joint Origin layout | settings `"jo_v"` 1 or 2 | aruco_feature.py L196-202, L408-450 | 1: before the node, on its target; 2: after the node, on a frame sketch compute moves | test_aruco_jo_one_per_tag.py |
| legacy numbers | parameters `height`, `thickness`, `above` | aruco_feature.py L144; aruco_slabs.from_legacy | nodes made before 2026-10-08; mapped to Offset / Height on read, rebuilt on the next edit | test_aruco_slabs.py |
| old corner mark | `"chamfer": true` | aruco_feature.normalise L490 | reads as `corner_mark: "cut"` | test_aruco_chamfer.py |
| old Frame | record / settings `"frame"` | aruco_feature.py docstring; aruco_tags.has_old_frame L927 | read as OpenCV's frame, dropped on the next write | test_aruco_frame.py |
| old rotation | settings `"rotate_deg"` | aruco_feature.evaluate L1118 | turned the frame BEFORE the fit; kept on nodes that have it, never set by the dialog | test_aruco_edit_roundtrip.py |
| Auto size | size parameter 0 (ChArUco: square 0 too) | aruco_feature.size_is_auto L453 | Auto re-fits on every compute; a stored number re-fits as typed, which moved tags (measured) | test_aruco_edit_roundtrip.py |
| label cap step | `CAP_STEP_MM = 0.1` | aruco_label.py L247 | auto cap heights round down to 0.1 mm | test_aruco_label.py |
| record schema | `markers.SCHEMA` in `aruco.json` | bam_cad_core/markers.py | the export block CADExporter reads | test_aruco_collect.py, test_aruco_output.py |
| ID ledger | root attribute `idsLedger`; stamps `{"uid", "born", "home"}` | aruco_ids_feature.py L136-137; aruco_numbering.Ledger | a printed id is never handed to another copy while the dictionary has unused ids | test_aruco_numbering.py, test_aruco_ids_stability.py |
| IDs node state | named value `"ids"`: `overrides`, `auto`, `final`, `parts`, `hidden`, `inputs` | aruco_numbering.node_state / read_state | what the node printed and what it was built from | test_aruco_ids_upstream.py |
| presets file | `"schema": "bam_aruco_presets/1"` | aruco_presets.py L58 | the user's presets; built-ins are never stored | test_aruco_presets.py |
| settings file | `"schema": "bam_aruco_settings/1"` | aruco_settings.py L39 | the last OK of each dialog, per design | test_aruco_settings.py |
| dictionaries | `aruco_dict.TABLE_SCHEMA`, `aruco_dictionaries.json` | bam_cad_core/aruco_dict.py | the bit tables exported from OpenCV once | test_aruco_board.py |

## The hardest pieces to extract, and why

1. **`aruco_feature.evaluate` (L1118-1309) and its inputs.** The function is 80 % pure: fit on loops, the Origin turn, the mark, the label, the pins, the trim. But it takes a Fusion entity. The face frame, the profile rectangle, the loops in metres, `x_base` / `x_ref` (a face tag's x fixed at creation), `host_xform` and the body under the target all come from `adsk` calls scattered through `profile_rect`, `face_frame`, `keep_x`, `creation_settings` and `_trim_inputs`. The Studio needs a plain "target" record (frame, w, h, loops, is_profile, has_body, z_sign, x_ref, host_xform) that the adapter fills and the core consumes. The trim is the worst: `_trim_inputs` measures oriented bounding boxes and volumes of real bodies in Fusion (L1570-1684).

2. **The settings and numbers of a node, with their history.** `settings_of`, `numbers_of`, `normalise`, `is_legacy`, `size_is_auto`, `settle`, `_merged`, `keep_black_step`, `structural_change`, `edit_kind` encode five generations of tags (the rules table above). Each reads a Fusion custom feature today. The logic is pure, but any slip changes what an old tag rebuilds to. It needs golden records for every generation before it moves.

3. **The dialog's refresh state machine** (`aruco_extrude_cmd._refresh` L2248-2467 and `_X` L192-245). Who touched which field, the black offset following the white top with a kept delta, Auto size against a typed size, the Layout candidates, the fresh id after a dictionary change, the preset "(modified)" state. It is one 220-line function wired to Fusion input ids, and it is re-entered by Fusion's own echoes. The pure model exists in pieces (`values`, `defaults`, the info lines); the state machine itself has to be rewritten as a Studio "dialog model" with the same transitions, and the 43 offline suites pin only parts of it.

4. **`aruco_ids_feature.collect_design` (L1005-1181).** It reads every occurrence's path, light bulb, linked flag and transform, every component's records, the stamps and the ledger, then applies rules about which copies count as hidden by the node, "born off" copies, legacy variants and linked designs. The planner (`aruco_numbering.plan_stable`) is already pure. The hard part is that the rules depend on Fusion's visibility model (per-path light bulbs, proxies, linked designs whose tokens cannot be resolved from the parent). The Studio needs an "assembly snapshot" schema that carries exactly this.

5. **Per-copy part geometry** (`part_bodies` L1457, `_recolour` L1675-1763, `_copy_face_colours` L1887-1969). A renumbered copy's part is the original's material re-split by the new id with TBM booleans, then painted body by body and face by face. The idea (which regions flip colour: `id_regions`, `label_slots`) is pure; the booleans and the paint are Fusion, and the paint only survives because of a repaint hook.

6. **Joint Origin placement** (`aruco_tags._place_joint_origin` L1172, `_ensure_joint_origin` L1715-1859, `_move_in_place` L1598, `_ensure_jo_after` L1385). Half is maths (OpenCV frame to angle, offsets and flip, by read-back when the composition disagrees), half is anchors on faces, sketch keypoints and the frame sketch, with roll rules that were measured in Fusion. The maths can move; the anchors cannot. The one-per-tag guarantee (`_MADE`, `_sweep_new`) exists only because `deleteMe()` can refuse.

7. **Restructure and dependents** (`aruco_restructure`). `restructure_plan` and `refusal` are pure. `restructure` itself (release, delete, create, regroup, atomic) and `_refs` (what a downstream fillet, joint or sketch references) are entirely about Fusion's timeline.

8. **The record schema mixes identity and geometry.** `TagDef.to_dict()["fusion"]` holds entity tokens, body names, the group token, `host_xform`, `mark`, `label`, `mode`. `collect`, `record_is_live`, `record_drift` and `fresh_collect` decide liveness by tokens. The Studio record must separate the geometric truth (spec, frame, mark, label, trim) from the adapter's handles.

9. **The hooks after a recompute** (`aruco_extrude_sync`, the rebuild and repaint hooks in `aruco_ids_feature`). The policy (`auto_decision`) is in the core. Idle detection, hidden auto-execute commands and the retry on a worker thread are Fusion, and were tuned against crashes.

10. **Colour.** Nothing in the core knows about appearances. In Fusion the colour of a base-feature body is lost on `add()`, on `updateBody()` and on every replay, so `paint`, `paint_all`, `paint_node`, `_paint_durable`, `repaint_parts` and `paint_drift` exist. The Studio viewer just colours black and white; the adapter keeps all of this.

## Fusion 2705 behaviours and quirks on record

Every item below is written in a code comment or a REF doc as measured in Fusion 2705.1.15. "Where" names the file and line, or the doc.

### Custom Features (the ArUco Extrude and ArUco IDs nodes)

| behaviour | where |
|---|---|
| Custom Features are still a preview API; `Command.beginStep`, `editingFeature` and `DesignIntentTypes` too | docs/research_aruco_timeline_feature.md 1 |
| The definition must be created inside an add-in's `run()`; from an event handler `customFeatures.add` fails `InternalValidationError : scriptInfoFound`. A definition id stays bound to the first add-in folder for the session, so switching worktrees needs a Fusion restart | aruco_cf_probe.py L19-26; research_aruco_timeline_feature.md "two traps" |
| The add-in's manifest needs an `"id"` GUID, else `add()` fails `3 : make params invalid` | same |
| The definition's `editCommandId` must name a command that exists when the definition is made | aruco_ids_feature.py L80-85; research_aruco_ids_feature.md |
| Compute may change only base-feature bodies, sketch contents and the node's parameters: no attribute writes, no Joint Origin moves, no occurrences, no joints | aruco_feature.py docstring; aruco_extrude_sync.py docstring; aruco_restructure.py docstring |
| A custom feature's range cannot hold a joint ("Not a valid feature type") | design_aruco_ids_parts_follow.md M1 |
| A face in a non-root component must be given as its root-context proxy, else `addDependency` fails `3 : Invalid argument value` | aruco_feature.py `_dependency` L2073; research_aruco_timeline_feature.md 4 |
| A root custom feature may depend on a face proxy inside a linked design | research_aruco_ids_feature.md |
| `CustomFeatureParameters.itemById(unknown)` raises `3 : Invalid argument id`; the docs say null | aruco_feature.py L1846; aruco_cf_probe.py L338 |
| A compute that reports an error inside `add()` makes `add()` raise | aruco_cf_probe.py L31 |
| `statusMessages.addWarning("API_COMPUTE_WARNING", ...)` makes the node an ERROR (health 2) | research_aruco_timeline_feature.md "more traps" |
| Fusion ignores a custom feature's own status-message text and shows "This feature computed with warnings. Compute Failed <name>"; `addError`'s additionalInfo goes nowhere. So the words go in the node's name | aruco_feature.py L2092-2099; aruco_edit_gates.py L487 |
| A node with a warning must warn at once; a refused label was silent (health 0) until something recomputed it | aruco_edit_gates.py L483 |
| `Command.beginStep()` in an edit command's activate undoes the timeline roll and fires execute | research_aruco_timeline_feature.md |
| A custom parameter can be an expression of its siblings; `max()` takes `;` not `,`; Fusion re-spaces expressions, so compare them without whitespace | aruco_feature.py docstring; aruco_heights_lab.expr_probe L1261 |
| A pocket that splits the face makes the face an invalid dependency (`InternalValidationError : face`); the fix wraps while the face is whole, then `setStartAndEndFeatures` with the marker rolled to the node (`3 : Didn't roll editing feature back` otherwise). Depending on the body instead: the node reads rolled back (health 4) and never computes | aruco_feature.py `_wrap_first` L2379; research_aruco_timeline_feature.md |
| `customNamedValues` showed no write lag (apriltag3D reported one for attributes) | research_aruco_timeline_feature.md 1 |
| `FusionEditFeatureCommand` does not reach the edit command when run programmatically; `APIFeatureEditCommand` does | aruco_feature.py `EDIT_ROUTES` L179; research_aruco_timeline_feature.md |

### Edit Feature in Part designs

| behaviour | where |
|---|---|
| In a PART design (`designIntent` 0) Fusion shows no "Edit Feature" and a double-click opens nothing for an add-in's custom feature. Hybrid (2) and Assembly (1) show both. The node, its definition and its edit command are intact; `APIFeatureEditCommand` still reaches the dialog from the API | aruco_feature.py L3359-3366; aruco_edit_gates.py L1255; docs/aruco_edit_in_part_designs.md |
| The fix: a `markingMenuDisplaying` entry "Edit ArUco Extrude" / "Edit ArUco IDs" at the top of the menu, and the toolbar's ArUco Extrude with a node selected opens that node's edit dialog | aruco_feature.py `install_menu_hook` L3431, `node_for_toolbar` L3442; aruco_extrude_cmd.py `_toolbar_edit` L2558 |
| Nodes a gate made inside a hidden command showed Edit Feature; Zach's, made through the real dialog, did not | aruco_edit_gates.py L1172-1178 |

### The timeline

| behaviour | where |
|---|---|
| `timelineObject.index` raises `InternalValidationError : res >= 0` for an item inside a COLLAPSED group; use the group's index. `Timeline.item` returns the group in place of its items | aruco_tags.py `_tl_index` L2387; aruco_ids_accept.py `_node_count` L1974, `tl_probe` L3719; aruco_actions.py L1378; design_aruco_ids_upstream.md 2026-10-16 |
| A timeline roll recomputes everything after the marker; rolling per node is quadratic (22 minutes on 45 tags, two hangs on 2026-10-08). Evaluate every node in one sweep | research_aruco_timeline_feature.md "more traps"; aruco_feature.refresh_live L3256 |
| A structural edit by delete + create cascade-deletes downstream features that referenced the node (a joint on the tag's face, a fillet, a sketch, the IDs node) | aruco_restructure.py docstring; design_aruco_ids_upstream.md run A |
| A fillet on the plate dies on structural edits, in place or not | spec open item OI-FILLET |
| A sketch-point move recomputes lazily: the first roll after it can read the old face | research_aruco_timeline_feature.md |
| An upstream edit that reverses the face's longest edge turned the pattern 180 degrees; face tags store `x_base` / `x_ref` at creation | aruco_feature.py docstring, `keep_x` L1318 |
| `TimelineGroup` has no `entityToken`; its `healthState` reads 5 (unknown) | research_aruco_timeline_feature.md |
| A Joint Origin on the frame sketch after the node was not re-evaluated when compute moved the sketch (4.000 mm stale until Compute All); compute may not touch the record or the Joint Origin either | aruco_extrude_sync.py docstring |
| Undo is one clean step for a parameter change and for an edit; compute does not run on Undo | research_aruco_timeline_feature.md 3 |
| `reorder(count)` throws "featureAtIndex"; `reorder(count - 1)` lands before the last item | design_aruco_ids_parts_follow.md |
| Moving a sub-assembly without Capture Position: Fusion puts it back at the next recompute. OK captures pending positions first and builds the IDs node last | research_aruco_ids_feature.md |
| A moved copy (`transform2`) does not recompute the IDs node | research_aruco_ids_feature.md |

### Appearances (colour)

| behaviour | where |
|---|---|
| `customFeatures.add()` resets its base-feature bodies to the component's default appearance; so does `updateBody()` in compute, and a timeline roll that replays a base feature | aruco_feature.py docstring and `_update` L1779 |
| Painting the swapped source body inside the same `startEdit` / `finishEdit` is allowed in compute and sticks; face-level appearance on a tile's faces survives the join and the pieces a pocket cuts it into | aruco_feature.py `_update` L1779-1809, `paint` L2470 |
| A tile cut into pieces: Fusion names the second piece "tag tile <key> (1)"; the arm strip's cells came back as nine bodies "(1)".."(8)" | aruco_feature.py docstring; research_aruco_ids_feature.md |
| On the rack, 20 of 36 part bodies came back "Steel - Satin" after a replay of their base features: a boolean result carries no colour of its own, a plain TBM copy keeps it. Painting the source bodies inside the edit changed nothing visible; painting the result body and every face (103 s) did | design_aruco_ids_upstream.md 2026-10-16; aruco_ids_feature.py L146-151, `paint_store_probe` L4173 |
| A joined tile's refilled cell came out in the plate's colour (no source face under it) | research_aruco_ids_feature.md |
| A custom-graphics dashed line is asked for and not drawn | spec open item OI-DASH |

### Joint Origins and joints

| behaviour | where |
|---|---|
| How Fusion composes a Joint Origin: x' = x turned by `angle` about the UNFLIPPED z; `isFlipped` turns half a turn about x'; origin = o + offsets along the FINAL axes. The old solve assumed the flipped z and put every flipped frame up to 180 degrees / 62 mm off | aruco_tags.py `_place_joint_origin` L1172-1190 |
| Offsets and angle must go in through the input; editing a Joint Origin's parameters afterwards needs the timeline rolled to it. Angle / offsets can be set with the marker anywhere; geometry and flip are refused with the marker right behind it ("Cannot be edited before rolling back") | aruco_tags.py `_jo_add` L1061, `_move_in_place` L1598-1612 |
| `deleteMe()` on a Joint Origin can return False or raise and leave it (a joint uses it); each edit then added one more Joint Origin until every one made was tracked | aruco_tags.py L1020-1033, `_delete_quietly` L1072 |
| An as-built rigid joint from a root occurrence to a proxy works, local-nested and xref-in-xref; a driven joint moves the copy and the part follows (0.000 mm); a joint to a copy whose light bulb is off works; a joint lives in the lowest component holding both occurrences | design_aruco_ids_parts_follow.md M2-M5 |
| `addNewComponent` made the first part pinned to its parent (`isGroundToParent` True), the second not; `isGrounded` raises on a nested occurrence | design_aruco_ids_parts_follow.md |
| A root joint on a copy inside a linked rig moved it, then it went back after the position capture | research_aruco_ids_feature.md |
| Fusion's physical properties count hidden bodies (the hidden original tag is weighed) | design_aruco_ids_parts_follow.md; spec OI-MASS |

### Occurrences, attributes, delete, linked designs

| behaviour | where |
|---|---|
| Per-path light bulbs are independent, even across two copies of the same arm; light bulbs ARE transacted (one Undo switches them back) | aruco_tags.py docstring; research_aruco_ids_feature.md |
| Occurrence attributes are stored per assembly path in the target component; attributes on a component are shared by every instance | research_aruco_fusion_architecture.md |
| A parent design cannot find a linked design's feature by token (`findEntityByToken` gives 0 hits) | research_aruco_ids_feature.md; aruco_ids_feature.py `_record_live` L993 |
| A proxy made with `createForAssemblyContext` down a path: its `transform2` is not the world transform below the first level; `root.allOccurrences` proxies are | research_aruco_ids_feature.md |
| An occurrence name may contain "+" ("JMC60 + Gearbox Plate:1"); Fusion joins path names with "+" too | research_aruco_ids_feature.md; markers.split_path |
| Fusion's Delete of a copy that holds a part stops on a modal ("referenced by downstream dependent features") that held the bridge 12 minutes; while any part's rigid joint exists `Occurrence.deleteMe()` returns True and leaves the copy there. The add-in replaces Fusion's Delete for such selections with one command | aruco_ids_feature.py L89-98, `copies_delete_plan` L409; aruco_ids_follow_probe.py L846, L967; design_aruco_ids_parts_follow.md |
| Fusion's Delete on the IDs node leaves the originals off; switched on afterwards they were undo steps of their own. The add-in's own delete does both in one transaction | aruco_ids_feature.py L89-93; research_aruco_ids_feature.md |
| `DataFolders.itemByName` raised `InternalValidationError : status.isOk() && folders`; walking the folders works | research_aruco_ids_feature.md |
| `comp.bRepBodies.itemByName("")` raises in 2705 | aruco_actions.py L694 |
| Closing an edited linked design while its new version was uploading, then `updateAllReferences`: Fusion died in GetLatestRequest (a NULL asset) | design_aruco_ids_upstream.md |
| Fusion's own crash-recovery autosave crashed on a background thread about 81 s after a test document closed (2026-10-13 22:06); the gates now pace closes and refuse while a user document is unsaved | docs/aruco_edit_gates_crash_20261013.md; aruco_edit_gates.py docstring L54-60 |

### Dialog inputs and events

| behaviour | where |
|---|---|
| Fusion echoes every input set by code as an `inputChanged`, synchronously. Outside a refresh the echoes re-entered refresh mid-apply and a list rebuilt there failed `1 : bad allocation` | aruco_extrude_ui.py `apply_preset` L1259-1266; design_aruco_ui_v2.md 10 |
| A `BoolValueCommandInput` button fires `inputChanged` TWICE per click (42 ms apart, under the same Windows message when nothing pumped the queue); the second click of a double-click never arrives; `TableCommandInput` has no activation or click-count event; `Command.mouseClick` / `mouseDoubleClick` fire only over the viewport | aruco_marker_table.py L25-36, `click` L293, `handle` L586-600; design_aruco_marker_table.md 3 |
| A tab switch sends `inputChanged` with the id "APITabBar", not the tab's id; opening or closing a dropdown sends nothing; `TabCommandInput.isActive` reads the tab shown | aruco_extrude_ui.py L47, L604-607; design_aruco_ui_v2.md 10 |
| The command's root inputs show as the first and last rows of EVERY tab | design_aruco_ui_v2.md 10 |
| A list's items are all with an icon or all without: adding an icon-less item to a list that has had icons fails `1 : bad allocation`, even after `clear()` | bam_fusion_ui.py L45-48, `_all_or_none` L52 |
| A list item's icon is drawn only when given to `listItems.add()`; `ListItem.icon` set later reads back but is not drawn | bam_fusion_ui.py `ensure_icons` L275-279 |
| An input's name cannot change after it is made; `validateInputs` carries no reason text | bam_fusion_ui.py docstring L26-29 |
| Fusion's editable value box at an arrow belongs to the input that has focus; the API has no switch for it; the only focus control is `SelectionCommandInput.hasFocus`. A new tag's Profile selection keeps the focus after the pick | aruco_ui_config.py `HUD_FOCUS`; aruco_extrude_cmd.py L2756-2761; bam_fusion_ui.py `release_selection_focus` L980 |
| `mouseDragEnd` fires for a manipulator drag; during a drag Fusion shows a plain value label, no editable box; an outward drag stops at the input's maximum | design_aruco_ui_v2.md 10 |
| Re-placing an arrow under the mouse can fight a drag: `setManipulator` only when its place changed, held during its own drag | bam_fusion_ui.py `Arrows` L893 |
| Fusion showed no dialog tooltip to synthetic hovers | design_aruco_ui_v2.md 10 |
| The first click after a tab switch or a screenshot is sometimes ignored when the dialog lacks focus | design_aruco_ui_v2.md 10 |
| A dropdown inside a table row works but shows no arrow until clicked | design_aruco_ui_v2.md 10 |
| Fusion holds event handlers weakly: drop the last Python reference and a button silently does nothing | aruco_commands.py L52-58; aruco_cf_probe.py docstring |
| The Export highlight drawn from `inputChanged` belonged to the command's own edit: Fusion neither repainted on an untick nor removed it on close, and it came back on the roll-back. Draw from `executePreview` only | aruco_export_preview.py L17-22 |
| Clearing a selection input re-enters `inputChanged` | aruco_marker_table.py L665 |
| Live preview cost: custom graphics 2-5 ms per update, the whole refresh 12-37 ms; building the real features 540-580 ms for a single marker, about 1.5 s for a grid; fitting a 4-loop profile about 35 ms | research_aruco_timeline_feature.md; aruco_feature.py L1149 |

### Palettes and HTML

| behaviour | where |
|---|---|
| A palette works with ArUco Extrude's command open: it opens, cards and filters work, the dialog stays open, Select applies the preset (4 of 4). Fallbacks F1 / F3 were not needed | design_aruco_ui_v2.md 10; aruco_extrude_ui.py `open_library` L1246 |
| Messages sent at creation are lost; `window.adsk` arrives late. Queue until the page says "ready"; `window.fusionJavaScriptHandler.handle` must return a non-empty string | bam_fusion_ui.py docstring L19-21, `HtmlChannel.receive` L701; research_aruco_fusion_architecture.md 6 |
| Palettes die on a workspace switch; docking lost the palette; handlers run on the main thread | research_aruco_fusion_architecture.md 6 |
| One click on a dialog button arrives twice, so opening the library is idempotent | aruco_extrude_ui.py L1246-1248 |
| A window title that gains or loses its " (Team name)" suffix is the same document | design_aruco_ui_v2.md follow-ups |

### Selection, crashes and the bridge

| behaviour | where |
|---|---|
| Never delete a node that is selected: Fusion crashed in `SelectionCommandInput::onEnd -> DcAPIFeature::faces` (2026-10-08). The edit command clears the selection before any delete | aruco_feature.py `clear_selections` L2168; aruco_bridge.py L80-84; aruco_marker_table.py `clear_pick` L784 |
| A pumped request acting under the user's hands crashed Fusion: every test checks the active document before and after each step | aruco_extrude_lab.py `guard` L381; aruco_ids_accept.py docstring |
| Fusion drops an add-in's event registrations when it stops it; a keep-armed restart left the bridge's custom event dead | aruco_actions.py L931-937; aruco_bridge.py L203-205 |
| Every add-in runs in one CPython; the CAD Exporter purges every `bam_` module on each press, so the core is loaded under a private alias | aruco_core.py docstring |
| Fusion moved from Python 3.12 to 3.14 in January 2026; ship `.py` only | research_aruco_fusion_architecture.md 7 |
| Hot reload is live in the user's session: every bridge request reloads the dialog and feature modules from disk | research_aruco_timeline_feature.md "more traps"; aruco_extrude_cmd.py L104-113 |

### Other measured facts worth keeping

| behaviour | where |
|---|---|
| TBM union of boxes that touch only at a corner: grown 10 um they fuse into one lump (9 boxes to 1 solid) | aruco_tags.py docstring; aruco_probe.py |
| `BaseFeatureActivate` on a base feature inside a collapsed group is a no-op | research_aruco_timeline_feature.md 5 |
| A sketch on the pocketed face projects the pocket edges: `profiles.item(0)` was a cell, not the circle | research_aruco_timeline_feature.md risks |
| Decals: PNG/JPEG/TIFF only, no width field, size via `transform`; the API fails in direct-modeling designs and sometimes ignores `transform` | research_aruco_fusion_architecture.md |
| Speed on 20 copies / 600 bodies: IDs dialog open 2.3 s, preview up to 0.25 s, OK 7.7 s; a rack collect 0.17 s; an automatic IDs rebuild 1.3-3.1 s | research_aruco_ids_feature.md; design_aruco_ids_upstream.md |
| Mesh names up to 164 characters pushed a copy under the worktree past Windows' 260-character path limit | research_aruco_ids_feature.md |
