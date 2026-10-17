# ArUco Studio: the roadmap (2026-10-16 night)

The order of the milestones of `M6_stickers_profiles_print.md` (M6a..M7) and `M8_mini_cad_file_first.md` (M8a..M8d). Each milestone is built by ONE agent, in this repo unless it says cad-exporter, with its owner paths and measurable done checks. Milestones in one wave never touch the same files.

| | |
|---|---|
| Written against | `main` at `4cc74be`; REF cad-exporter `aruco-fusion-plugin-0e9bcb` at `9829cd4` |
| Direction (Zach, 2026-10-16 ~21:00) | **Studio first.** The Studio is connected end to end and made accurate: the file -> the plan -> the sticker sheet -> **Print** (M6c), and the file -> the plan -> the 3MF -> **Send to PrusaSlicer** (M8c), each proven by a test (the WYSIWYG raster of M6 §g; the headless slice of M8 §5.7). **Fusion is a downstream adapter**: M7 runs only when no Studio milestone is waiting for an agent and a Fusion test window is free; nothing in M6 or M8 waits on M7 |

## 1. The order

| Wave | Milestones, in parallel | Why this order |
|---|---|---|
| 1 | **M6a** (core: the preset is the machine, stickers, sheet modes, WYSIWYG, server) ∥ **M8a** (the file format, the compile, the watcher, events, the CLI) | both are Python and disjoint (rule 2 below); everything else stands on them |
| 2 | **M8b1** (the mini CAD in the Studio) ∥ **M8c** (PrusaSlicer physical printers, live sync, Send to PrusaSlicer, the slice check) ∥ M7.1-M7.2 (Fusion, when a window is free) | M8b1 is `studio/`, M8c is Python: disjoint. M7 is cad-exporter |
| 3 | **M8b2** (the kit, the form, M6b's rows, multi-select, the sheet dialog, Print = M6c, Send to PrusaSlicer…, the Printers collection) ∥ M7.3-M7.4 | M8b2 needs M6a's rows, M8a's API, M8b1's shell and M8c's routes |
| 4 | **M8d** (the kit into the cockpit and Cad2Robot, cad-exporter) ∥ M7.5 (the v2 dialog from `plan/fields.py`) ∥ later items (section 4) | after the kit exists |

M6b and M6c are folded into M8b2: their rows and dialogs are rebuilt on the kit anyway, so building them twice on the old look is waste. Their done checks (M6b.1-M6b.8, M6c.1-M6c.5) keep their numbers and are part of M8b2's.

## 2. Rules for running milestones side by side

| Rule | |
|---|---|
| Owner paths | a file belongs to one milestone per wave. A milestone that needs a line in a file it does not own puts its code in a new module and asks for ONE include line, added at the end of that file by the orchestrator at merge |
| Wave 1 | M6a's new routes go in `server/sheet_api.py` (its sheet check is `POST /api/scene/verify/sheet`, a route of its own, not a `?sheet=1` flag on the handler M8a rewrites); M8a's in `server/design_api.py`. In `server/app.py` M6a edits only `/api/new` and `/api/presets`; M8a replaces the `/api/scene*` block and `/api/target` (re-implemented over the design document). M6a does not edit `server/newtag.py`: its new-tag rule lives in `core/form.py` (audit C4), which M8a's `plan/newtag.py` keeps calling. M8a touches nothing under `core/` and not `plan/target.py` (it reads the chord tolerance from `core.faces.CHORD_TOL_MM`, the same 0.05 mm, until M6a's `plan.target.CHORD_MM` lands; a one-line follow-up unifies them) |
| Wave 2 | M8b1 owns `studio/**`, `e2e/**`, `docs/STUDIO.md`; M8c owns `core/prusa.py`, `core/presets.py`, `scene/print3d.py`, `plan/mesh.py`, `server/beds_io.py`, `server/store.py`, `server/library.py`, `server/prusa_api.py`, `server/prusa_watch.py`, `verify/slice_check.py`, their tests |
| Wave 3 | M8b2 owns `studio/**`, `e2e/**` and ONE Python file, `plan/fields.py` (with `tests/plan/test_fields_present.py`); M7 is cad-exporter only |
| Goldens | `goldens/**` is never edited by a milestone; a new fixture folder is added, never a changed case |
| The versioned rules | no milestone changes a rule's number or stored key |
| Done | each milestone writes `docs/status/<name>.md` with its numbers, the checks' results and where the build differs from the note; the orchestrator writes `docs/spec.json` |
| Safety | nothing written under `%USERPROFILE%\CADExporter`, `%APPDATA%\PrusaSlicer` or REF; ports 5360 / 5361 only; PrusaSlicer is never launched by a test |

## 3. The milestones

### M6a: core, plan, scene, sheet, verify, server

As written in `M6_stickers_profiles_print.md` §k (owner paths, checks M6a.1-M6a.11), with the wave-1 route rule above. Unchanged otherwise.

### M8a: the file format, the compile, the watcher, events, the CLI

| | |
|---|---|
| Goal | a scene is one text file (`arucostudio.scene/2`) a person or an AI types; it compiles to today's `Scene`; the server watches it and pushes changes; every Studio action writes it; the old routes keep working over it; a CLI checks and renders a file without a browser |
| Owner paths | `aruco_studio/plan/shapes.py` (new: `stroke(shape) -> loops` for rect / circle / polygon / slot / loops at the chord tolerance; `face_target(body, face) -> Target` for top / bottom / side faces with their frames), `plan/newtag.py` (new: the pure half of `server/newtag.py`, which then imports it), `scene/design.py` (new: the document model, `compile(doc, presets) -> (Scene, [Issue])` with sugar expansion, the edit operations the routes need: shapes, sketches, features, a tag's settings / numbers, the multi-face list and its split), `scene/file.py` (`/2`, the `/1` migration, `dumps` of a design document), `scene/model.py` (`SceneTag.pose` stored when it is not z-up; `uid` kept), `server/design_api.py` (new: `GET / PUT /api/design` (the text), `POST /api/design/open {path}`, `/api/design/preview`, `/api/design/reveal`, `GET /api/events`), `server/watch.py` (new, generic: paths -> signature -> callback, the hash rule), `server/events.py` (new: the SSE hub), `server/store.py` (a design path anywhere but the forbidden folder; `write_atomic` records the hash), `server/app.py` (the `/api/scene*` and `/api/target` handlers over the design document; `--open`), `aruco_studio/__main__.py` (new: `check`, `render`, `plan`), `examples/plate_charuco.arucostudio.json`, `examples/forearm.arucostudio.json`, `examples/sticker_sheet.arucostudio.json` (M8 §1.3 verbatim), `tests/plan/test_shapes.py`, `tests/scene/test_design.py`, `tests/scene/test_file_v2.py`, `tests/server/test_design_api.py`, `tests/server/test_events.py`, `tests/test_cli.py`, `docs/FILE_FORMAT.md` (new: §1 of the M8 note as the reference), `docs/API.md`, `docs/status/M8a.md` |
| Does not touch | `goldens/**`, `studio/**`, `core/**`, `plan/target.py`, `plan/plan.py`, `plan/evaluate.py`, M6a's files |

Done checks:

| # | Check | Bar |
|---|---|---|
| M8a.1 | the three example files compile; each tag's `record_digest` equals the digest of the same tag made through `/api/new` + `/api/target` (the plate: a box 80 x 50 with a Ø18 hole, 5 mm thick, ChArUco 5 x 3); `python -m aruco_studio check examples/*.json` exits 0 | equal; 0 |
| M8a.2 | every `/1` scene the e2e suite saves (and a 25-tag scene) migrates to `/2` and replans byte for byte; the migrated file round-trips (`loads(dumps(x))` equal); its ledger and overrides survive | all |
| M8a.3 | 824 evaluate goldens and every pytest group green after the change; `tests/plan/test_adapter_keys.py` still passes | all |
| M8a.4 | the forearm: four Targets (120 x 40, 40 x 40, 120 x 40, 40 x 40), each `has_body` with `depth` 40 or 120, each pose a right-handed orthonormal 4x4 whose z is the face's outward normal (±x, ±y), each tag's OpenCV frame on its face; `tag.front` .. `tag.left` named; an edit of one tag's `mark` splits the list into four features and the file shows it | all |
| M8a.5 | shapes: a circle Ø50 strokes to the same points as `core.faces` strokes a Ø50 circle at 0.05 mm; a slot's loop is closed and counter-clockwise; a hole is clockwise and inside; a hole outside its parent is an `error` on `sketches[i].shapes[j].holes[k]`; a tag on a circle's side is an `error` naming "curved" | all |
| M8a.6 | the watcher: an external write is seen and `scene` pushed within 500 ms (measured in the test with a `TestClient` stream); a broken write keeps the scene, reports `line:col`, and a `PATCH` answers 409 "file not parseable" without writing; the server's own write produces no event; an unchanged rewrite (same text) produces no event; a deleted file stops writes with a message | all |
| M8a.7 | the old routes over the design: `POST /api/scene/tags` adds a sketch + feature; `PATCH .../tags/{name}` with settings writes the exact dict into the feature and the file; `duplicate`, `renumber`, `overrides`, `export/*`, `verify` give the same answers as on `main` for the same scene (the server tests of `main` replayed) | all |
| M8a.8 | sugar: `{"aruco": "a", "layout": "charuco", "cols": 5, "rows": 3, "label": "#id"}` expands to what `/api/new` stores (`origin_v`, the label's rule, `cells` from the preset); after one `PATCH` the feature holds exact `settings` / `numbers` and no sugar | equal |
| M8a.9 | the CLI: `render` writes an SVG whose `data-layer` paths match `/api/export/svg`'s; `plan --json` equals `GET /api/scene?plans=1`'s plans; `check` on a file with a bad feature exits 1 and prints the path | all |
| M8a.10 | `tools/check.py` exits 0; nothing on 5360 / 5361 after; nothing written outside the repo and the temp folders | true |

### M8b1: the mini CAD in the Studio

| | |
|---|---|
| Goal | draw, select, move, rotate and edit shapes; holes; Extrude; ArUco Extrude on a shape or a face replaces the target editor; markers re-place live; the bottom toolbar with hotkeys; S opens the palette; drag in 3D; the Studio follows the file and writes it on every action; the File drawer. The kit's primitives are born here (`studio/src/kit/`) and every new control uses them |
| Owner paths | `studio/src/**` (new: `sketch/` tools and handles, `app/BottomBar.tsx`, `app/Palette.tsx` (cmdk), `app/FileDrawer.tsx`, `view3d/Gizmo.ts` (TransformControls, the extrude arrow), `api/events.ts` (the SSE client), `kit/` primitives; changed: `store.ts` (file first: no dirty state, Undo as text history, the preview during a drag), `canvas/` (shapes, handles, the net view of side-face tags), `inspector/` (the shape's fields; ArUco Extrude's first rows); deleted: `inspector/TargetEditor.tsx`), `studio/package.json` (Tailwind 4, `@base-ui/react`, `lucide-react`, `cmdk`), `e2e/tests/**` (new: `sketch.spec.ts`, `palette.spec.ts`, `live.spec.ts`, `drag3d.spec.ts`; `target.spec.ts` rewritten for shapes), `reports/screens/**`, `docs/STUDIO.md` (the new keys and tools), `docs/status/M8b1.md` |
| Does not touch | `aruco_studio/**`, `tests/**`, `docs/spec.json`, `goldens/**` |

Done checks (Playwright; every bar read from the DOM, `window.__studio` or the file on disk):

| # | Check | Bar |
|---|---|---|
| M8b1.1 | R, type `80 50`, Enter: the file on disk holds `{"rect": [80, 50]}` under a new sketch; the canvas has one `data-shape` path with four points; H inside it, `18`: `"holes": [{"circle": 18}]`; E, `5`: an Extrude feature and the view is 3D; A on the top face, Enter: a tag; the file compiles to the same digests as `examples/plate_charuco.arucostudio.json` (after sugar) | all |
| M8b1.2 | handles: dragging the rectangle's right edge 10 mm writes `rect [90, 50]`; the tag's plan from `/api/scene` has a larger `numbers.size`; a polygon vertex drag, a circle rim drag, a slot end drag and a rotation handle each write their numbers (0.5 mm / 15° snapped) | all |
| M8b1.3 | live re-placement: ten tags on ten rectangles; one edit; `performance.now()` from the pointer-up to the canvas's `data-revision` change | < 100 ms, printed in the status file |
| M8b1.4 | the file: the test writes the forearm example over the open file: the canvas shows four tags within 500 ms, no reload; a broken write shows "line N col M" in the bar, keeps the old canvas, and a key press that would write is refused (the file on disk unchanged); Undo after three edits restores the text of the first (byte equal) | all |
| M8b1.5 | the toolbar: every tool has a key badge; the active tool is lit; S then "verify" Enter runs Verify; S lists every command of the keys table in STUDIO.md (the test diffs the two lists); Esc cancels a tool; `?` shows the map | all |
| M8b1.6 | 3D: the gizmo drag moves the sketch's `at` by a 0.5 mm multiple; the extrude arrow changes `height`; a tag on `forearm.right` has its mesh's normal along +x in the scene; the 2D view draws it as a flap with a `data-hinge` line | all |
| M8b1.7 | A with four Shift-clicked faces then Enter: one feature with a four-face list; four tags on the canvas; Renumber gives four unique ids | all |
| M8b1.8 | `TargetEditor.tsx` is gone; `npm run build` no TS errors; vitest green; every M3 / audit e2e that still applies green (the status file lists the ones rewritten and why); servers stopped | true |

### M8c: PrusaSlicer physical printers, live sync, Send to PrusaSlicer, the slice check

| | |
|---|---|
| Goal | the physical printers resolved to their printer preset's nozzle and the print presets that fit; PrusaSlicer's folder watched and pushed; a 3MF project with the colours on their extruders and the physical printer's presets, opened in PrusaSlicer; the slice checked headless against the plan, in the tests only |
| Owner paths | `aruco_studio/core/prusa.py` (`PHYSICAL_KEYS`, `parse_physical`, `parse_bundle(kinds=...)`, `printer_of`, `fits` with the condition evaluator, `selected`), `core/presets.py` (the `printer` block; `normalise` keeps it), `scene/print3d.py` (new: parts, volumes, negative volumes, the manifest), `plan/mesh.py` (`removed(plan)`: the material a tag removes from the body, per slab), `server/beds_io.py` (`_project_setup` from a printer chain; `volume_type` per volume), `server/store.py` (physical / printer / `PrusaSlicer.ini` texts), `server/library.py` (the Printers collection), `server/prusa_api.py` (new: `GET /api/prusa/printers`, `POST /api/scene/send/prusaslicer`), `server/prusa_watch.py` (new, on M8a's `watch.py`), `verify/slice_check.py` (new: the G-code oracle), `goldens/prusaslicer/{physical_printer,printer}/*.ini` and `PrusaSlicer.ini` (a fixture typed with placeholder hosts, `provenance.json` says so), `tests/core/test_prusa_physical.py`, `tests/core/test_prusa_fits.py`, `tests/scene/test_print3d.py`, `tests/server/test_prusa_api.py`, `tests/server/test_prusa_watch.py`, `tests/verify/test_slice_check.py`, `docs/API.md`, `docs/status/M8c.md` |
| Does not touch | `studio/**`, `core/beds.py` (REF's text), `core/sheet.py`, M8b1's files |

Done checks:

| # | Check | Bar |
|---|---|---|
| M8c.1 | the fixture's physical printers resolve: name -> printer preset -> nozzle (0.4 / 0.6), model, variant, bed; one through a user `printer/*.ini` with `inherits`, one bundle-only through a three-deep `inherits` chain | all |
| M8c.2 | `fits`: every `compatible_printers_condition` in Zach's ten print files parses (no `maybe`); the yes / no per (print, printer) equals the list PrusaSlicer shows in its print dropdown for the MK4 MMU3 0.4 and 0.6 printers (read once by hand from PrusaSlicer, written in the status file) | exact |
| M8c.3 | the allow-list: a fixture physical printer with every `printhost_*` key set to a marker string: the marker appears in no parsed dict, no API answer, no Library JSON, no 3MF, no log line | none |
| M8c.4 | `GET /api/prusa/printers` lists the fixture's five with their fitting prints; `current` marks the selected pair; the Library's Printers collection has one card each; Select makes a preset with that printer's nozzle and that print's line and layers | all |
| M8c.5 | the watcher: editing a fixture physical printer's `preset_names` gives a `prusa` event within 3 s; a bundle swap re-reads under 200 ms (measured); a half-written file gives no event until it parses; a tag made from a changed profile is unchanged and carries the `info` under Preset; a hash of the folder before and after shows nothing written | all |
| M8c.6 | Send: the forearm example gives one object with 1 + 4 x (white, black, negative) volumes; the 3MF read back without our code (zipfile + ElementTree, as REF's `verify_print_beds.py`): every volume closed and two-manifold, `volume_type` right, black on extruder 2, the config equal to the chosen printer's chain, the bed from its `bed_shape`; the plate example: the body and one tag's volumes; the sticker example: 400 with "nothing to slice: stickers print on paper" | all |
| M8c.7 | the slice (M8 §5.7 steps 2-7) on the plate and the forearm with the fixture chain (MK4 0.6, `0.32mm SPEED @MK4IS 0.6 - Aruco`): layers ±1; the black's first and last layer within one layer height of the plan's pattern z; the line count across one cell exact; ink IoU >= 0.9, label pixels >= 60 %; no extrusion outside the footprint + 0.5 mm; the four side tags each pass | all; skipped with the reason when the console is absent |
| M8c.8 | `open: false` in every test: PrusaSlicer is never launched; the GUI exe's path is found on this box and written in the status file; `--single-instance` accepted or not, recorded | recorded |
| M8c.9 | `tools/check.py` exits 0; nothing written under `%APPDATA%\PrusaSlicer`, `%USERPROFILE%\CADExporter` or REF; `tests/core/test_purity.py` still passes (the core opens no file) | true |

### M8b2: the kit, the form, M6b's rows, the sheet dialog, Print, Send to PrusaSlicer…, the Printers collection

| | |
|---|---|
| Goal | every panel on the compact kit, light and dark; the inspector's form rendered from `plan/fields.py` alone (tab, icon, show_when, anchor from the API; `layout.ts` deleted); the kit extracted as `studio/packages/bam-ui/`; M6b's rows (Preset first, Made by read only, Holes, Perimeter, the ChArUco label choices, the `2D` / `3D` badges and filter, the IDs table's Made-by column), multi-select edit, the sheet dialog with its SVG preview; Print (M6c); Send to PrusaSlicer…; the Printers collection cards |
| Owner paths | `studio/packages/bam-ui/**` (new: the kit), `studio/src/**` (every panel on the kit; `inspector/Form.tsx` from the fields; `library/` with Printers; `app/Dialogs.tsx`: the sheet dialog, Send to PrusaSlicer…; `app/Print.tsx`; `styles` -> tokens), `aruco_studio/plan/fields.py` (the presentation keys of M8 §4.3) and `tests/plan/test_fields_present.py` (the only Python), `e2e/tests/**` (new: `kit.spec.ts`, `form.spec.ts`, `sheet.spec.ts`, `print.spec.ts`, `send.spec.ts`, `multi.spec.ts`), `reports/screens/**`, `docs/STUDIO.md`, `docs/KIT.md` (new: the tokens, the components, `bam.form/1`), `docs/status/M8b2.md` |
| Does not touch | the rest of `aruco_studio/**`, `tests/**` beyond the one file, `goldens/**` |

Done checks: M6b.1-M6b.8 and M6c.1-M6c.5 as written in the M6 note, and:

| # | Check | Bar |
|---|---|---|
| M8b2.1 | no Fusion token left (`grep -r "#0696d7\|Artifakt" studio/src` empty); every panel screenshotted in light and in dark; every row 24 px tall at the default density | all |
| M8b2.2 | the form: `layout.ts` is gone; the inspector's tabs, icons, visibility and message anchors all come from `/api/form`; a field with `show_when.made_by = ["sticker"]` is hidden on a 3D tag; a hidden field's message appears under its `anchor` | all |
| M8b2.3 | Send to PrusaSlicer…: the dialog opens on the current physical printer; Send calls `POST /api/scene/send/prusaslicer` once with `open: false` under the test and the answer's project path exists; a scene without a 3D tag disables the item with "nothing to slice" | all |
| M8b2.4 | the Printers collection shows one card per fixture physical printer with its fitting prints; Select makes a preset with that printer's nozzle; the current pair is marked | all |
| M8b2.5 | `npm run build` (the app and the package) no TS errors; vitest; every e2e green; servers stopped | true |

### M8d: the kit into the cockpit and Cad2Robot (cad-exporter)

| | |
|---|---|
| Goal | the other tools use the same kit and the same `Form`; no Fusion window needed |
| Owner paths (cad-exporter) | `tools/sync_from_aruco_studio.py` (the kit part, pinned to a Studio commit), `app/src/kit/**` (the copy), one cockpit panel on `Form` with a `bam.form/1` field list, the datasheet editor's dataclass fields as `bam.form/1` rows, `app/src/**` for the theme tokens |
| Done checks | the copied kit builds in `app/` (`tsc -b`, vitest, oxlint green); the chosen panel renders its rows with per-row messages from a field list, screenshotted; the datasheet editor's rows render from the same `Form`; the sync tool reports the pinned commit |

### M7: Fusion, downstream

As written in the M6 note §k (M7.1-M7.4, gated, in the cad-exporter worktree, test documents only), plus:

| Step | What | Gate |
|---|---|---|
| M7.5 | the v2 dialog built from the vendored `plan/fields.py` rows: `bam_fusion_ui.Layout` and `Validator` read `tab`, `icon`, `show_when`, `anchor`; a test asserts the derived tables equal today's `ROUTE` / `MSG_ROWS` / `FALLBACK` before those are deleted | REF `test_aruco_ui_v2` green; the v2 dialog checks of `design_aruco_ui_v2.md` §9 pass in a Hybrid test document |
| M7.6 (later) | the design file as the exchange with Fusion: a clicked face or profile exported as a `loops` shape into a design file; a design file imported as bodies and ArUco Extrude nodes (MC-12: "easier to move to CAD later") | round trip: a Fusion face -> file -> Studio plan equals the node's record |

Priority: M7 runs only when no Studio milestone is waiting for an agent and a Fusion test window is free (the idle check and peer rules of the memory notes). Nothing in M6 or M8 waits on it.

## 4. Later, explicitly

| Item | Id | After |
|---|---|---|
| True nesting of odd stickers | ST-SHEET-NEST | M8b2 |
| Fit at any angle | ST-FIT-ANGLES | when a face asks for it |
| replicad in the browser for B-rep display and picking (M8 §3's fallback) | ST-REPLICAD | only if a need appears |
| build123d adapter: a script's faces -> a design file; a design file -> solids / STEP | ST-B123D | M8a |
| The size arrow and the label drag in 3D | ST-UI-3D-HANDLES | M8b1 |
| Tight beds (the guillotine idea on the printer bed) | ST-BEDS-TIGHT | M8c |
| The Fusion exchange (M7.6) | ST-FUSION-FILE | M7.5 |

## 5. What "done end to end" means

| Chain | Proven by |
|---|---|
| a typed file -> the plan -> the canvas | M8a.1, M8b1.4 (the file is what is drawn) |
| the plan -> the sticker sheet -> the printed page | M6a.8 (the raster of the PDF equals the plan), M6c.2 and M6c.5 (100 mm is 100 mm) |
| the plan -> the 3MF -> PrusaSlicer's layers | M8c.6 (the project read back), M8c.7 (the slice equals the plan: layers, heights, line counts, ink) |
| the printer Zach uses -> the numbers in the preset | M8c.1, M8c.2, M8c.4 |
| a change in PrusaSlicer -> the Studio | M8c.5 |
