# ArUco Studio: status

The morning hand-over of 2026-10-17. `main` of `C:\Users\BAM\Documents\aruco-studio`, local only, no remote. Everything since the 2026-10-16 evening hand-over was built while Zach slept, each open question taking the recommended default. The same facts as a page: `reports/status.html` (from `docs/spec.json`, with the morning screenshots).

## 1. Start here (Zach)

| Try | How |
|---|---|
| Open the Studio | `npm --prefix studio run studio`, then http://127.0.0.1:5360 |
| Open an example | File › Open… › Examples › `forearm` (four ChArUco tags on the sides of a box), `plate_charuco` (a plate with a hole), `sticker_sheet` (four stickers). The example opens as a copy in `scenes/`; the example file itself is never written |
| Draw your own | R, type `80 50`, Enter (a rectangle). H, `18`, Enter (a hole). E, `5`, Enter (extrude: the view goes 3D). A, Enter (an ArUco Extrude on the top face). S opens the command palette; `?` lists the keys |
| Edit the file by hand | the Studio writes `scenes/<name>.arucostudio.json` on every action and redraws when you edit it in any editor (`docs/FILE_FORMAT.md`). Undo is a history of the file's texts |
| Print stickers | open `sticker_sheet`, Export › Sticker sheet… (Spaced / Tight, Letter / A4), then Export › Print sticker sheet… (M6c.5 below: measure the 100 mm bar once with a ruler) |
| Send to PrusaSlicer | open `forearm`, Export › Send to PrusaSlicer…. The dialog starts on PrusaSlicer's current physical printer; tick Open PrusaSlicer to launch it. With your own PrusaSlicer folder the Library's Printers collection shows your printers |

Two questions wait for you (section 4): a sticker's ChArUco Auto size, and the forearm's labels on three faces. The third, the cut-from-black label stroke (Q1), took its recommended default while you slept: label rule 5 (lane polish, `docs/status/polish.md`).

After the morning hand-over, two lanes were built and merged (`docs/status/merge-polish.md`): lane polish (label rule 5, a paste and an input method in the tool box, the final audit's nits A5-A7, A10 and C2's server half) and lane speed (live re-placement on the forearm about 3x faster on the server, bit-identical results, the light drag preview in 3D). A fresh session then verified `main` independently: the full check, the drag medians through the served Studio, the label goldens and rule 5, the paste (`docs/status/verify-2026-10-17.md`).

## 2. The check run

`.venv/Scripts/python tools/check.py` from a clean shell, 2026-10-17 04:50-05:00, on `main` after the merge of lane/polish and lane/speed: the independent verification (`docs/status/verify-2026-10-17.md`; the raw lines: `reports/verify_check_2026-10-17.log`). Ports 5360 / 5361 were free before and nothing listened on them after (5371 is Zach's preview and was left alone). The morning column is the hand-over run of 03:11-03:20, before the two lanes (`reports/morning_check_2026-10-17.log`).

| Group | Verified (after the merge) | The morning run (before) |
|---|---|---|
| adapters | 97 passed in 40 s | 97 in 39 s |
| core | 7,387 passed, 4 skipped in 36 s | 7,354 + 4 skipped |
| plan | 544 passed in 100 s | 529 |
| scene | 43 passed in 12 s | 42 |
| server | 97 passed in 17 s | 91 |
| verify | 120 passed in 88 s | 117 + 1 skipped (the strict xfail) |
| studio | build (the app and the kit) + vitest passed in 9 s | passed (vitest 44) |
| e2e | 52 Playwright passed (4.0 m) in 244 s | 47 in 236 s |
| **all** | **OK in 546 s**, exit 0 | OK in 523 s |

The new tests: plan +12 (lane speed's digests) +2 (lane polish) +1 (the merge's overlay test); server +6 (lane speed); verify: the xfail is a pass and +2 slice tests; e2e +3 (the typed box) +2 (speed). The merge's own run was OK in 562 s (`docs/status/merge-polish.md`).

`tools/check.py --trace`: 233 REF sections, ported 212, not ported (Fusion / UI) 17, skipped (other venvs) 4, **missing 0**. The 4 core skips are the parked `evaluate()` sections of two legacy goldens (`tests/plan/test_golden_evaluate.py` covers them). `tools/spec_status.py --check`: 92 tests passing, 4 planned, 0 failing. `tools/mesh_digests.py --check`: 947 cases, 0 differ.

### The morning screenshots

Taken after the check from the served build (`python -m aruco_studio.server` on 5360 with `studio/dist`, a temp home, the fixture printers), then looked at: `reports/screens/morning_*.png`, and on `reports/status.html`.

| File | Shows |
|---|---|
| `morning_01_mini_cad_sketch.png` | R `80 50`, H `18`: the rectangle selected with its eight handles and the turn handle, the hole, the shape rows (At, Turn, W x H, Holes, Extrude) |
| `morning_02_body_charuco_3d.png`, `_02b_..._2d.png` | E `5`, A, Type ChArUco: a 3 x 5 board in the plate's clear 31 x 50 mm rectangle beside the hole, ids 0-6; the cell-minimum warn under Marker size |
| `morning_03_forearm_3d.png`, `_03b_..._2d_net.png` | `examples/forearm`: four tags on the box's sides, `#0-5` on the front; in 2D the box net with the hinge lines, the three refused labels drawn orange in their squares (Q3) |
| `morning_04_sheet_dialog_tight.png`, `_04a_stickers_2d.png` | `examples/sticker_sheet`: Letter, Tight: 4 stickers, 1 page, 11 cuts, 3 shelves, the 100 mm bar on the page; the four stickers with their `2D` badges and cut lines |
| `morning_05_printers_collection.png` | the Library's Printers: five cards (aburi, Haribo, kappa, Le Mis, ontario) by name and nozzle, `current` on ontario, the Info panel with the printer preset, model, nozzle, bed, extruders and the five fitting prints; no host, key or password anywhere (checked in the page's text too) |
| `morning_06_kit_light_inspector.png`, `_06b_..._label_tab.png` | the light kit: Preset first, Made by read only, On, the tabs, the rows from `/api/form`; the Label tab with the Marker-size warn anchored under it |

What I saw that is not right, none new: the forearm's name sprites overlap in 3D (audit nit C4); "Holes: Avoid (the tag keeps cl…" is cut short at 1500 px (C2); the warn row's short line reads "it may print poorly" while the full text (its tooltip, `data-text`) goes on "; a Checker size of 16 mm or more passes" (B9's fix is there, the short form drops it).

## 3. The milestones and their done checks

Each milestone's own record has the numbers and the evidence per check: `docs/status/<name>.md`. This table is the summary; PASS means the check's bar is met by the test named.

### M6a: the preset is the machine, stickers, the sheet, WYSIWYG (`docs/status/M6a.md`)

| # | Check | Result |
|---|---|---|
| M6a.1 / M6.1 | legacy = 3D: 824 evaluate goldens replay; `plan_tag(spec)` = `plan_tag(spec + make 3D)` | PASS, 824 / 824 (`tests/plan/test_make_plan.py`, `test_golden_evaluate.py`) |
| M6.2, M6.3 | a sticker plans as its 3D twin on thin stock; OpenCV reads every case, PnP within 0.1 mm / 0.1 deg | PASS, 72 / 72, 0 pixels differ |
| M6.4 | junk `make` plans as 3D with a warn; `plan_tag` never raises | PASS, 2,000 random specs |
| M6.5, M6.6 | 40 tags of both kinds, one ledger; the bundle: the PDF holds exactly the stickers at true size, print3d/ exactly the 3D tags, a 3MF with the cells on slot 2 | PASS (`tests/scene/test_print_bundle.py`) |
| M6.7 / M6a.2, M6.8 | presets carry kind, dpi, page, stock; Letter and A4 built-ins; `/api/new`, `/api/form`, `/api/presets` | PASS (`tests/core/test_make.py`, `tests/server/test_make_api.py`) |
| M6a.3 | Holes: avoid / ignore; avoid = today byte for byte; the crossing warn | PASS; the plate with a hole: 23.0 -> 37.0 mm (`tests/plan/test_holes.py`, 45) |
| M6a.4 | Perimeter Marker / Profile on 12 faces x labels | PASS, 72 cases |
| M6a.5 | label rule 3 builds in each of 18 black squares; rules 1 and 2 unchanged | PASS, 18 / 18 (`tests/core/test_label_rule3.py`) |
| M6a.6, M6a.7 | tight: four 30 mm stickers, one shelf, 7 cuts (spaced: 16 in the note, 10 counted since lane polish); odd shapes packed by their boxes with every cut line | PASS (`tests/core/test_sheet_modes.py`) |
| M6a.8 | WYSIWYG: the PDF's raster at 600 dpi equals each sticker's plan | PASS: worst ink XOR 0.82 %, side 0.012 mm, label IoU 0.959, outline 0.072 mm, bars 0.034 mm (`tests/verify/test_sheet_wysiwyg.py`) |
| M6a.9 | sheet.svg = sheet.json within 0.01 mm | PASS |
| M6a.10 | a 96-point disc with 3 holes plans under 50 ms | PASS, 21.9 ms |
| M6a.11 | check green; nothing on 5360 / 5361; nothing written outside the repo | PASS (this run) |

### M8a: the design file, the compile, the watcher, events, the CLI (`docs/status/M8a.md`)

| # | Check | Result |
|---|---|---|
| M8a.1 | the three examples compile; each tag equals the same tag made through `/api/new` + `/api/target`; `check examples/*.json` exits 0 | PASS (`tests/server/test_design_api.py`, `test_cli.py`) |
| M8a.2 | every `/1` scene (three from e2e, a 25-tag scene) migrates to `/2` and replans byte for byte; round-trips | PASS (`tests/scene/test_file_v2.py`) |
| M8a.3 | 824 evaluate goldens and every group green; `test_adapter_keys` passes | PASS (this run) |
| M8a.4 | the forearm: four Targets with right-handed frames, z the outward normal; one edit splits the list; Renumber does not | PASS (`tests/scene/test_design.py`) |
| M8a.5 | shapes: the circle equals core.faces' stroke; slot ccw; holes cw and inside; a hole outside is an error on its path; a curved side says "curved" | PASS (`tests/plan/test_shapes.py`) |
| M8a.6 | the watcher: an outside write pushed within 500 ms; a broken write keeps the scene and answers 409; no echo; a deleted file stops writes | PASS, 228-255 ms (`tests/server/test_events.py`) |
| M8a.7 | the old routes over the design give main's answers | PASS (main's 35 server tests unchanged) |
| M8a.8 | sugar expands to what `/api/new` stores; exact after one PATCH | PASS |
| M8a.9 | the CLI: `render` = `/api/export/svg`; `plan --json` = `GET /api/scene?plans=1`; `check` exits 1 on a bad feature and prints its path | PASS (`tests/server/test_cli.py`) |
| M8a.10 | check green; nothing on the ports; nothing written outside | PASS (this run) |

### M8b1: the mini CAD in the Studio (`docs/status/M8b1.md`)

| # | Check | Result |
|---|---|---|
| M8b1.1 | R `80 50`, H `18`, E `5`, A on the top: the file holds the plate; the example's digests | PASS (`e2e/tests/sketch.spec.ts`) |
| M8b1.2 | handles write their numbers (0.5 mm / 15° snapped); a wider rectangle gives a larger marker | PASS |
| M8b1.3 | live re-placement: pointer-up to the canvas's `data-revision` change under 100 ms | PASS: 21.4 / 16.4 / 15.8 / 7.2 / 18.5 ms (`live.spec.ts`) |
| M8b1.4 | the forearm written over the open file is drawn within 500 ms; a broken write shows "line N col M" and refuses writes; Undo restores the texts byte for byte | PASS, 133 ms (432 ms cold) |
| M8b1.5 | every tool has a key badge; the palette lists exactly STUDIO.md's table; S "verify" Enter runs Verify; `?` shows the map | PASS (`palette.spec.ts`) |
| M8b1.6 | the gizmo moves `at` by 0.5 mm; the arrow sets `height`; forearm.right's normal is +x; the 2D flap has a hinge | PASS (`drag3d.spec.ts`) |
| M8b1.7 | A with four faces: one feature, four tags; unique ids | PASS |
| M8b1.8 | `TargetEditor.tsx` gone; build, vitest, every e2e green; servers stopped | PASS (this run) |

### M8c: PrusaSlicer physical printers, live sync, Send, the slice check (`docs/status/M8c.md`)

| # | Check | Result |
|---|---|---|
| M8c.1 | the fixture's five physical printers resolve to nozzle, model, variant, bed; one through a user `printer/*.ini`, one bundle-only three deep | PASS (`tests/core/test_prusa_physical.py`) |
| M8c.2 | every `compatible_printers_condition` parses; the yes / no table for the MK4 MMU3 0.4 and 0.6 | PASS from the conditions; **not yet read off PrusaSlicer's dropdown** (section 4, Q4) |
| M8c.3 | the allow-list: a marker in every host key appears nowhere | PASS (`test_prusa_api.py::test_the_marker_is_nowhere`) |
| M8c.4 | `/api/prusa/printers`, the Printers collection, Select makes a preset | PASS |
| M8c.5 | the watcher: a `prusa` event within 3 s (0.55-0.63 s); a bundle swap under 200 ms CPU (94 ms); a tag never changes by itself, "Apply?" instead | PASS (`tests/server/test_prusa_watch.py`) |
| M8c.6 | Send: the forearm one object, volumes closed and two-manifold, black on extruder 2, the config = the printer's chain; stickers 400 | PASS (`tests/scene/test_print3d.py`) |
| M8c.7 | the headless slice: layers, the black's heights, lines per cell, ink IoU >= 0.9, footprint, the four side tags | PASS. The label-pixel bar passes for new tags since label rule 5 (lane polish): the forearm's '#0-5' cut from the black at the floor stroke, 0.748 mm, prints 85 of 85 pixels. A rule-4 tag still loses 37 of 216 at 0.64 mm, kept as its own test (`tests/verify/test_slice_check.py`, no xfail left) |
| M8c.8 | `open: false` in every test; the GUI path and `--single-instance` recorded | recorded: `C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe`, 2.9.6, `--single-instance` accepted |
| M8c.9 | check green; nothing under `%APPDATA%\PrusaSlicer`, CADExporter or REF; `test_purity` passes | PASS |

### M8b2: the kit, the form, M6b's rows, the sheet dialog, Print (M6c), Send…, the Printers collection (`docs/status/M8b2.md`)

| # | Check | Result |
|---|---|---|
| M6b.1 | a sticker tag: Made by "Printed sticker", no Heights tab, thickness and margin on Print, the `2D` badge | PASS (`e2e/tests/stickers.spec.ts`) |
| M6b.2 | Holes: Ignore grows the marker, the hole dashed, the warn under Holes | PASS |
| M6b.3 | Perimeter Profile / Marker; a 3D tag's Perimeter = Trim excess | PASS |
| M6b.4 | a sticker ChArUco label: black squares only; dragged two squares along x, built there (rule 3) | PASS |
| M6b.5 | multi-select: "—" where tags differ; one change to all; one Undo | PASS (`multi.spec.ts`) |
| M6b.6 | the sheet dialog: Tight / Spaced previews equal sheet.json within 0.01 mm; A4; Export lists the sheet files | PASS (`sheet.spec.ts`) |
| M6b.7 | a 3D #3 and a sticker #3 are one duplicate; the 2D / 3D filter; the Made-by column; Renumber | PASS |
| M6b.8 | build, vitest, every older e2e green | PASS |
| M6c.1 | Print's bytes are `GET /api/scene/print.pdf`'s and the bundle's `sheet.pdf` | PASS (`print.spec.ts`; see deviations) |
| M6c.2 | the bars at 600 dpi | PASS: 100.009 mm and 101.609 mm |
| M6c.3 | the fallback: "Open the PDF" with the Ctrl+P note | PASS |
| M6c.4 | no stickers: Print off with a reason | PASS ("3D tags: Send to PrusaSlicer…" on a 3D scene) |
| M6c.5 | a printed 100 mm bar measured with a ruler | **by hand, for Zach**: write the number in `docs/status/M8b2.md` |
| M8b2.1 | no Fusion token; 16 panels screenshotted light and dark; every row 24 px | PASS (`kit.spec.ts`, `reports/screens/m8b2_kit_*`) |
| M8b2.2 | the form from `/api/form` alone; `layout.ts` gone; show_when and anchor | PASS (`form.spec.ts`) |
| M8b2.3 | Send… opens on the current printer; one POST with `open: false`; "nothing to slice" without a 3D tag | PASS (`send.spec.ts`) |
| M8b2.4 | the Printers collection: a card per fixture printer, the current pair marked, Select makes the preset | PASS |
| M8b2.5 | build, vitest, every e2e green; servers stopped | PASS (this run) |

### The audit of 2026-10-17 (`docs/status/audit-2026-10-17.md`)

Musts fixed: frozen presets for typed files (P1), ids after a split list (A1), the palette by name (A2), label rule 4 (A3: a ChArUco label on Auto stays in a black square). Shoulds fixed: the free-port tests (P2), spec.json and STATUS (P4), Send's nozzle line (B2), one message for a refused label (B4), Open's examples / recent / folder (B5), the sheet-only Export (B6), the Print entry's words (B7), "In a black square" (B8), the cell-minimum warn names a size that passes (B9), unique ids in the examples (B11), a rect hole's W x H (B12). Not fixed, with reasons: P3, B1, B3 and parts of B2, B4, B10 (section 4).

### Earlier (2026-10-16): M1 to M4, the first audit

The 15-point Definition of Done of `docs/PLAN.md` section 4 was verified on 2026-10-16 about 21:00: 14 of 15 PASS (D13 failed only because another session's preview worktree exists). The record is in git history (`docs/STATUS.md` at `35fea4e`) and in `docs/status/M1.md` to `M4.md` and `AUDIT.md`. Every number there still holds in this run: the four REF goldens replay bit for bit, 824 evaluate cases, `--trace` missing 0, the core stdlib only.

## 4. What is open

### For Zach to decide

| # | Question | Where it stands |
|---|---|---|
| Q1 | **Resolved with label rule 5**, the recommended default, taken while Zach slept (lane polish, 2026-10-17). A label cut out of the black now strokes at least one line of the tag's cell rule. The slice showed exactly one line is not quite enough: at 0.68-0.72 mm the white prints but the one-pixel black counters drop out (10 of 85 pixels). From 0.74 mm every pixel prints. So the floor is 1.1 lines: 0.748 mm, 3.74 mm letters at 0.68 mm lines. Only new tags store rule 5; rules 1-4 plan exactly as before (the goldens hold). Change `label.LINE_STROKE` before any tag is printed if you want another margin | `tests/verify/test_slice_check.py` passes (no xfail); `tests/core/test_label_rule5.py`. A finer black nozzle is still the other road |
| Q2 | **A sticker's ChArUco Auto** uses the 3D tube rule (k squares across, raised to the printable minimum), not the largest board that fits | Changing it changes Auto for every stored sticker: a new versioned rule, and your word on what "fills" means (2 x 2 of 13.5 mm or 3 x 3 of 9 mm) |
| Q3 | **The forearm's labels** fit only on the front: a 19 mm square holds four characters at a 0.6 mm nozzle; the other faces' `#6-9`, `#10-15`, `#16-19` are refused (one message each) | 2 x 2 squares would fit the text but give one inner corner, weak for a pose. Or Content `#id` on each face. The example ships with `#id` |
| Q4 | **M8c.2's yes / no table** for the MK4 MMU3 0.4 and 0.6 printers was read from the conditions by hand, never off PrusaSlicer's dropdown (no test may open the GUI) | Open PrusaSlicer once, compare the print dropdown for the two printers with the table in `docs/status/M8c.md`, write the answer there |
| Q5 | **M6c.5**: print the sticker sheet once and measure the 100 mm bar with a ruler | Write the number in `docs/status/M8b2.md` |

### Known and not fixed

| What | State |
|---|---|
| Live re-placement on the forearm (audit B1) | mostly fixed by lane speed (`docs/status/speed.md`): the server answers a drag step in about 75 ms in 2D and 3D on a quiet box (was 245 ms and 715 ms), the 3D release in 215-230 ms; the results are bit-identical (947 digests). Verified again on `main` through the served Studio in Chrome (`docs/status/verify-2026-10-17.md`, every step a new plan): a 2D drag step's round trip is 131 ms median, a 3D step's 135 ms, the 3D release 270 ms (395 ms to the meshes on screen); a re-drag over widths the server has seen is 13-19 ms (its cache). So the 100 ms target is met by the server, not yet by the browser round trip: the page's own work between a fetch's start and end is the other 55 ms. Next steps: a process pool on the server (about 2.5x in a trial, not built); less main-thread work per response on the page. In 3D the drag shows flat slabs; the relief comes on release |
| A typed Columns x rows on a face is explained, not honoured | a new fit rule (audit B10) |
| Send… does not preselect the printer the tags were planned for; it names the matching printers and a click picks one | as M8b2.3 requires (audit B2) |
| The nits of the final audit (A5-A10, C1-C4) | lane polish fixed A5 (`/api/health` names the file's `/2`), A6 (spaced `cuts()` is a guillotine count: 10, not 16), A7 (the trivially true assertion is gone; the watcher's event and route are scanned), A10 (renumber rows carry `made_by`) and the server's half of C2 (the size error and the cell-minimum warn read whole in the short line). Left, with reasons in `docs/status/polish.md`: A9 (the "Old sticker sheet" entry), C1 (key paths in the status bar), the Studio half of C2, C3 (floats and exact keys), C4 (drawing slips): all in `studio/`, which the drag-preview lane owned this run. Both lanes are merged now (`docs/status/merge-polish.md`), so these can be done next |
| The e2e suite's screenshots are rewritten on every full check (`reports/screens/`) | committed as they come |
| Another session's worktree `C:\Users\BAM\Documents\aruco-studio-preview` (detached) | left alone; `git worktree remove` it when it is not needed |

### Planned, later (ROADMAP section 4 and the spec)

M8d (the kit into the cockpit and Cad2Robot, in cad-exporter), M7 (Fusion, downstream: M7.1-M7.6, when a Fusion test window is free), ST-SHEET-NEST, ST-FIT-ANGLES, ST-UI-3D-HANDLES (the size arrow and the label drag in 3D; snap to shape centres and edges), ST-BEDS-TIGHT, ST-B123D, ST-REPLICAD, ST-FUSION-FILE, and the older M1-M4 leftovers (REF re-pin C3, the Fusion gates F1-F8, the live switch). `docs/spec.json` carries every feature and test with its status and a reason for each planned, partial or deferred one (`tools/spec_status.py --check`).

## 5. How to run

| Do | Command |
|---|---|
| First time | `C:\Users\BAM\miniconda3\python.exe -m venv .venv`, `.venv/Scripts/python -m pip install -r requirements.txt`, `npm --prefix studio ci`, `npm --prefix e2e ci` |
| Run the Studio | `npm --prefix studio run studio`, open http://127.0.0.1:5360 (Ctrl+C stops it) |
| Run it on a file | `.venv/Scripts/python -m aruco_studio.server --open <file>.arucostudio.json` |
| Develop with hot reload | `.venv/Scripts/python -m aruco_studio.server` and `npm --prefix studio run dev`, open http://127.0.0.1:5361 |
| Your own PrusaSlicer printers | the server reads `%APPDATA%\PrusaSlicer` (read only, four keys per physical printer, every host and key dropped). `BAM_ARUCO_PRUSASLICER_DIR` points it elsewhere; the tests use `tests/fixtures/prusaslicer_m8c` |
| A file without a browser | `.venv/Scripts/python -m aruco_studio check examples/*.json` (`--strict`), `render`, `plan --json` |
| Every check, one command | `.venv/Scripts/python tools/check.py` (about 9 minutes; starts and stops its own servers on 5360 / 5361; the e2e PrusaSlicer folder is the fixture) |
| One group | `.venv/Scripts/python tools/check.py core` (groups: adapters, core, plan, scene, server, verify, studio, e2e) |
| The REF trace | `.venv/Scripts/python tools/check.py --trace` |
| The spec pages | `.venv/Scripts/python tools/spec_status.py` (reports/spec.html), `.venv/Scripts/python tools/status_page.py` (reports/status.html) |

The server's files go under `ROOT/.studio_data/` and scenes under `ROOT/scenes/`; it refuses any path under `%USERPROFILE%\CADExporter`. How to use the app: `docs/STUDIO.md`. The kit: `docs/KIT.md`. The file format: `docs/FILE_FORMAT.md`. The routes: `docs/API.md`, `docs/API_sheet.md`, `docs/API_prusa.md`.

## 6. Where the build differs from the notes

| Note said | Built | Why |
|---|---|---|
| M6: a new tag stores label rule 3 | rule 5 (rule 4: a ChArUco label on Auto stays in a black square; rule 5: a label cut from the black strokes at least 1.1 cell lines); rules 3 and 4 are unchanged; `label.RULE` stays 2 because REF's suites pin it | the audit's FB-13 fix; Q1's default (lane polish) |
| M6: the sticker built-ins in the catalog | in `catalog_all()`, not REF's `catalog` (REF's suites pin it); the server reads `catalog_all` everywhere since Merge 2 | port fidelity |
| M6: tight-mode cuts | counted so that the design's own example gives 7; spaced `cuts()` is a guillotine count since lane polish (four 30 mm stickers: 10; the note said 16) | audit nit A6 |
| M6c.1: compare with `/api/scene/export/pdf` | compared with `/api/scene/print.pdf` and the bundle's `sheet.pdf`; `export/pdf` is still REF's old A4 sheet | the old route was kept for M7 |
| M6b.6: the sheet dialog's Export writes the print bundle | it writes the sheet only; `POST /api/scene/export/print` without `sheet_only` still writes the bundle | audit B6 |
| M6c.4's words | "3D tags: Send to PrusaSlicer…" on a 3D scene | audit B7 |
| M8 §1.3: the examples verbatim | the forearm without `cols` / `rows`, label `#id`, `marker_ids` [0, 6, 10, 16]; the stickers with `first_id` 0, 1, 2, 8 and t4's hole at (0, 18) | audit B4, B10, B11; the centred hole left no room for a ChArUco |
| M8a: the typed first id is `id` | `first_id` (a feature's `id` is its name); a tag on a bare shape is kind "face" with no body; exact `settings` / `numbers` replace the sugar; `pose` stays 2D and `pose_3d` holds the full pose; `GET /api/scene` keeps the `/1` shape | listed in `docs/status/M8a.md` |
| M8c: the fixture under `goldens/prusaslicer` | `tests/fixtures/prusaslicer_m8c` (goldens must come from REF); the forearm is 1 + 4 volumes with the example's own preset, 1 + 4 x 3 with New-body tiles; lines per cell on flat tags only; arc fitting off in the slice | `docs/status/M8c.md` |
| M8b1: the gizmo | two TransformControls (move in X / Y, a ring about Z); the File drawer shows the error's line and column above the last text that parsed | `docs/status/M8b1.md` |
| M8b2: the Send dialog's beds choice | none yet (the note says later); multi-select shows the last tag's messages | `docs/status/M8b2.md` |
| ROADMAP: the orchestrator writes `docs/spec.json` at each merge | written by the audit fix-up and this hand-over for every milestone since 2026-10-16 | |
| ROADMAP: `tools/check.py` is never edited by a milestone | one line changed by M8b2 (the e2e PrusaSlicer folder is the fixture) and the port variables by the audit | |
| Lanes in worktrees | M6a, M8a, M8b1, M8c in worktrees and merged `--no-ff`; M8b2 and the audit fixes on `main` directly | wave 3 had one lane |

## 7. Sizes

| Part | Lines |
|---|---|
| `aruco_studio/core` (stdlib only) | 18,008 |
| `aruco_studio/plan` | 4,362 |
| `aruco_studio/scene` | 2,481 |
| `aruco_studio/verify` | 1,488 |
| `aruco_studio/server` | 4,522 |
| `aruco_studio/adapters` | 2,412 |
| `studio/src` + `studio/packages/bam-ui/src` | 10,244 + 1,478 |
| `tests` + `e2e/tests` | 23,914 + 2,825 |

72 commits on `main`, 27 of them since the 2026-10-16 evening hand-over (9 since the morning hand-over: the two lanes, their merges, the merge's fix and the verification). Fable 5.1 planned, audited and verified; Opus built the milestones and the fixes (each commit's `Co-Authored-By` line says which).
