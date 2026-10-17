# M8c: PrusaSlicer physical printers, live sync, Send to PrusaSlicer, the slice check

Built on branch `lane/M8c` (worktree `aruco-studio-wt/M8c`), from `main` at `3b56a22`, beside M8b1. The design is `docs/design/M8_mini_cad_file_first.md` section 5 and `ROADMAP.md` section 3 "M8c". Every open question took its recommended default. The API is in the new `docs/API_prusa.md`.

## Include lines for the merge

| File | Line, at the end |
|---|---|
| `aruco_studio/server/app.py` | `from . import prusa_api  # noqa: E402,F401  (M8c: PrusaSlicer printers, Send, the folder's watcher)` |

The line puts the routes first (as `sheet_api` does) and starts the folder's watcher with the server (`on_startup`), stopping it at shutdown. Until the line is in, the tests import `prusa_api` themselves.

## What was built

| Piece | Where |
|---|---|
| The allow-list (`PHYSICAL_KEYS`, `parse_physical`), `private_key` (every `printhost_*`, `print_host`, `octoprint_*`, any `*_host`, any key holding `apikey`, `password`, `secret`, `token`), `drop_private`, `ini_complete` (a half-written file) | `aruco_studio/core/prusa.py` |
| `parse_bundle(kinds=...)` (one pass; sections of other kinds not read), `PrusaSources` with printers, physical printers, models, vendors, the selection | `core/prusa.py` |
| `resolve_printer`, `printer_of` (nozzle, model, variant, bed, layers, defaults), `condition` (the evaluator), `fits` (yes / maybe / no), `pair_profile`, `prints_for`, `selected`, `installed_models`, `physical_printers` | `core/prusa.py` |
| The printer block `profile.printer = {physical, preset, model, variant}`; `normalise` keeps it; `from_pair` | `core/presets.py` |
| `removed(plan)`, `removed_mesh(plan)`: what a tag removes from the body, per slab | `plan/mesh.py` |
| Parts, volumes, negative volumes, the beds, the 3MF with `volume_type`, the manifest | `scene/print3d.py` (new) |
| `chain_profile` (the chosen printer's chain), `filament_for`, `write_project`, `open_in_prusaslicer`, `single_instance_ok` | `server/beds_io.py` (REF's twelve functions untouched) |
| Reading the folder line by line through the allow-list; `prusa_paths`, `prusa_read`, `read_prusa_file`; writes refused under the folder `BAM_ARUCO_PRUSASLICER_DIR` names | `server/store.py` |
| The Printers and Sticker printers collections; Select on a (printer, print) choice; the catalog is `catalog_all` | `server/library.py` |
| `GET /api/prusa/printers`, `POST /api/scene/send/prusaslicer`, `GET /api/prusa/stale`, `GET /api/prusa/watch` | `server/prusa_api.py` (new) |
| The folder's watcher (on M8a's `watch.py`; it hashes only what is kept), the `prusa` event, the tags' "Apply?" info | `server/prusa_watch.py` (new) |
| The G-code oracle | `verify/slice_check.py` (new) |
| The fixture: Zach's five physical printers (typed, hosts as placeholders), his two printer presets (host keys as placeholders), his ten print presets, the 102 bundle sections they inherit from, `PrusaSlicer.ini` (typed: `[presets]`, `[vendor:...]`); its maker | `tests/fixtures/prusaslicer_m8c/`, `tests/fixtures/make_prusaslicer_m8c.py` |
| Tests | `tests/core/test_prusa_physical.py` (9), `tests/core/test_prusa_fits.py` (32), `tests/plan/test_mesh_removed.py` (5), `tests/scene/test_print3d.py` (6), `tests/server/test_prusa_api.py` (9), `tests/server/test_prusa_watch.py` (7), `tests/verify/test_slice_check.py` (7, one a strict xfail: the label finding) |
| Changed tests | `tests/core/test_port_fidelity.py` (beds_io's five new functions listed as not REF's), `tests/server/test_studio_api.py` (the Library's collections now include `printers` and `stickers`) |
| Docs | `docs/API_prusa.md` (new), `docs/API.md` (a pointer, the `prusa` event) |

## Numbers

| What | Measured |
|---|---|
| An edit of a physical printer's `preset_names` -> the `prusa` event (TestClient stream; the watcher at its own 2 s / 0.5 s) | 0.55 to 0.63 s; bar 3 s |
| A bundle swap (PrusaSlicer's own `PrusaResearch.ini`, 2,123,086 bytes, copied into the temp folder): read, resolve, diff | 82 to 148 ms wall clock alone, 94 ms CPU; bar 200 ms. Under the full check's load the wall clock reached 220 to 760 ms, so the test bars the process's CPU time and records both |
| Reading the whole fixture folder (19 files) | 30 ms |
| Send: the forearm's project built (compile aside) | 356 ms; 91 kB |
| The slice, headless: plate / forearm | 0.45 s / 1.1 s |
| Plate: layers / black's first and last layer / lines across a module / ink IoU | 16 of 16 / 4.68 and 5.00 mm against 4.40 to 5.00 / 2 of 2 (1.36 mm module, 0.68 mm lines) / 0.9946 |
| Forearm: layers; per side tag the black's layers and the face ink IoU | 125 of 125; front and back 1.16 to 38.92 mm against 0.96 to 39.04, IoU 0.9811; right and left 1.80 to 38.28 against 1.64 to 38.36, IoU 0.9807 |
| Forearm: the label on front and back ("#0-5\|FOR…", cut from a black square, cap 3.2 mm, stroke 0.64 mm) | 216 font pixels; 37 under 60 % of their colour; mean 0.88 white on the text, 0.89 black around it; the worst text pixel 0.50, the worst black one 0.00 |
| The same label on a flat face (a 120 x 40 x 4 plate, ChArUco 5 x 2, the same label) | 44 of 216 under 60 %; mean 0.78 white on the text, 1.00 black around it; the worst text pixel 0.31 |
| A single marker's "#id + name" label printed in black on the white (flat) | 228 pixels, all at 100 % |
| Plate with New-body tiles (white, black and the pins' sockets as a negative volume) | 22 layers of 22, black 4.68 to 5.00, IoU 0.9946 |
| Footprint (every case) | 0 extrusions outside the part + 0.5 mm, 0 in the bed margin |
| pytest groups (run as `tools/check.py` runs them: `-n auto`, a temp home; main's uvicorn-on-5360 test deselected) | adapters 97 passed; core 7,349 passed, 4 skipped; plan 518 passed; scene 42 passed; server 74 passed; verify 117 passed, 1 xfailed (the label finding); every group exit 0 |

## The done checks

| # | Result | How |
|---|---|---|
| M8c.1 | PASS | `test_prusa_physical.py`: the five resolve to their printer preset, nozzle, model, variant, bed (Haribo and Le Mis: Prusa CORE One 0.6 nozzle, 0.6, COREONE, 250 x 220; aburi: MK3 0.6; kappa: MK3.5 0.6; ontario: the user's MK4 MMU3 0.4 "(Black, Clear, White)", 0.4, MK4ISMMU3, 5 extruders). ontario goes through a user `printer/*.ini` with `inherits`; Haribo is bundle only, three deep (CORE One 0.6 -> HF0.6 -> HF0.4, the model set only by the deepest) |
| M8c.2 | PASS, read by hand | every condition in Zach's ten print files parses; no `maybe` for either MK4 MMU3 printer; the yes / no below equals the table read by hand from the conditions. PrusaSlicer's window is never opened by this lane, so the list was not read off its dropdown. **Zach: please glance at the two dropdowns once** |
| M8c.3 | PASS | `test_prusa_physical.py::test_the_allow_list_drops_every_host_key` (core: the marker in no field of the sources, the printers, the resolved presets); `test_prusa_api.py::test_the_marker_is_nowhere` (every host key of ontario and of both printer presets set to a marker: not in `/api/prusa/printers` (both forms), `/api/library`, a Select, `/api/presets`, `/api/prusa/stale`, two Send answers, every member of both 3MFs, every file under the Studio's home, any log record) |
| M8c.4 | PASS | `test_prusa_api.py`: five printers with their fitting prints; `current` is ontario with `0.20mm SPEED @MK4IS 0.4`; the Library's Printers collection holds five cards; Select on Haribo's choice makes "Haribo · 0.32mm ERGO @COREONE 0.6": nozzle 0.6, line 0.68, layers 0.32 / 0.2, cells a whole number of lines, the printer block, saved as yours |
| M8c.5 | PASS | `test_prusa_watch.py`: the event within 3 s (0.55 to 0.63 s); the bundle swap under 200 ms (CPU, see Numbers); a half-written file: no event, the last good read kept, the event when it parses; three broken ticks: one `broken` message; a tag made with the Aruco preset keeps its spec when the profile's line goes 0.68 -> 0.65 and `GET /api/prusa/stale` says "the profile changed: line 0.68 -> 0.65 mm; Apply?"; the folder's hash is unchanged by the server; no folder: no watch, and it is found when it appears |
| M8c.6 | PASS, with a note | `test_print3d.py` (read back with zipfile + ElementTree only): the forearm is ONE object; every volume closed, two-manifold and outward; `volume_type` right; black on extruder 2; the config equals the chosen printer's chain (resolved again in the test with a parser of its own) and the bed is its `bed_shape`; the plate is its body and one tag's volumes; the sticker example gives 400 "nothing to slice: stickers print on paper" (`test_prusa_api.py`). The note: see "1 + 4 x 3" below |
| M8c.7 | PASS but one bar: **the label pixels FAIL** | `test_slice_check.py` on the plate and the forearm with the fixture chain (MK4 MMU3 0.6, `0.32mm SPEED @MK4IS 0.6 - Aruco`, Prusament PLA @PGIS 0.6): layers, the black's heights, the lines across one module (plate), ink IoU >= 0.9, the footprint, on each of the four side tags: all pass (numbers above). The label bar ("every label pixel over 60 % of its central half") fails on the forearm's front and back: their label is cut from a black square at a 0.64 mm stroke, under the preset's 0.68 mm line, and PrusaSlicer's black beads close parts of the glyphs (37 of 216 pixels). It fails on a flat face too (44 of 216), so it is the stroke, not the side face. The plan already warns that this label is cut short. A label printed in black on the white passes at 100 %. The test is a strict `xfail` with this reason, so it fails loudly the day it passes. Not fixed here: the label's minimum stroke is core/label's rule (not this lane's), and the fix is a choice for Zach: a stroke of at least one line (0.68 mm) for a label cut from the black, or a finer nozzle for the black |
| M8c.8 | recorded | every test sends `open: false`, and the opener is replaced by one that fails the test; one test checks `open: true` calls a fake opener once. The GUI on this box: `C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe`; the console: `C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe`. `--single-instance` is accepted by 2.9.6 (it is in the console's `--help`, run headless with a scratch `--datadir`); Send passes it |
| M8c.9 | PASS | the groups above green; `tests/core/test_purity.py` passes (the core opens no file); nothing in `%APPDATA%\PrusaSlicer` is newer than 2026-10-16 20:06 (before this lane started); nothing written under `%USERPROFILE%\CADExporter` or REF. Nothing of this lane listened on 5360 / 5361 (the listeners there were M8b1's e2e run) |

### M8c.2: the print dropdown, by hand

| Print preset | MK4 MMU3 0.4 | MK4 MMU3 0.6 | Why |
|---|---|---|---|
| 0.15mm SPEED @MK4IS 0.25 - Aruco Black | no | no | `nozzle_diameter[0]==0.25` |
| 0.20mm DETAIL @0.6 nozzle MK3 - BAM | no | no | needs `PRINTER_VENDOR_PRUSA3D` and `PRINTER_MODEL_MK3` in the notes |
| 0.30mm QUALITY @0.6 nozzle - GEARS | no | no | the same |
| 0.30mm QUALITY @0.6 nozzle MK3 - Ergo Adapter | no | no | the same |
| 0.30mm QUALITY @0.6 nozzle MK3 - No Loops | no | no | the same |
| 0.32mm ERGO @COREONE 0.6 | no | no | `printer_model` must be a CORE One (a full match) |
| 0.32mm SPEED @MK3.5 0.6 - Main | no | no | `.*MK3.5.*` is not in the MK4's notes |
| 0.32mm SPEED @MK4IS 0.6 - Aruco | no | **yes** | MK4IS in the notes, nozzle 0.6, no high-flow nozzle |
| 0.32mm SPEED @MK4IS 0.6 - Main | no | **yes** | MK4IS, 0.6, no `HF_NOZZLE` in the notes |
| 0.40mm DRAFT @0.6 nozzle MK3 - BAM PROTOTYPE | no | no | the MK3 words |

So the 0.4 printer gets none of Zach's own prints (PrusaSlicer has it on the system `0.20mm SPEED @MK4IS 0.4`), and the 0.6 printer gets the two MK4IS 0.6 ones.

## Where the build differs from the note

| Note | Built | Why |
|---|---|---|
| the fixture under `goldens/prusaslicer/{physical_printer,printer}/` and `PrusaSlicer.ini` | `tests/fixtures/prusaslicer_m8c/`, a whole folder of its own, with its maker and `provenance.json` | `goldens/**` is never edited, and every golden must be REF's (`test_golden_provenance.py` checks each file's REF commit and maker). This fixture comes from Zach's PrusaSlicer folder, not from REF |
| the forearm gives "1 + 4 x (white, black, negative)" | with the example's own preset: **1 + 4 x 1**, the body and four blacks | that preset's Extrude is Auto, which on a body is black only, inset into the body: no white tile, and the inset is filled back by the black, so nothing is removed. The same file with New-body tiles (`"mode": "both", "op": "new"`) gives exactly 1 + 4 x 3 (white, black, the pins' sockets as a negative volume); both are tested |
| negative volumes from the pocket, recess, holes, mark cut, the trim's complement | `plan/mesh.removed`: wherever the body was and is no longer, minus what the tag adds back. On the examples only the New-body pins' sockets are left | a recess under an inset black is filled by the black, so it is no negative volume |
| step 4, lines per cell, on each side tag | flat tags only; a side tag reports "does not apply" | a side tag's cells stand across the layers: a layer cuts each cell into a thin strip, so there are no lines across a cell to count |
| the label's pixels >= 60 % | each font pixel of the plan's label (its rect in steps of its stroke) checked on the same raster as the ink: a label cut from the black wants no black on its text and black around it; a label printed in black the other way round | REF's oracle checks glyph pieces, bridges and counters; the M8 note's bar is per pixel, so that is what is barred. The plate's label does not fit its square, and the forearm's right and left tags have none |
| ASCII G-code (`binary_gcode` overridden) | also `arc_fitting = disabled` | the profile emits G2 / G3 arcs; plain lines keep the oracle simple. The geometry is the same |
| the layer count "per the preset" | `1 + round((height - first) / layer)` | PrusaSlicer gives 125 layers for the 40 mm forearm, not 126 |
| parts placed on the bed | as modelled, never laid down or turned (a side tag stays on its side), dropped to z 0, packed by `core.beds.pack_rectangles` with the wipe tower's hole | the note asks for the parts with their tags; laying the forearm down would put a tag on the bed |
| the filament | PrusaSlicer's selected one when that printer is selected, else the printer's default when the bundle has it, else the first Prusament / Generic PLA whose condition fits | the MK4 MMU3 0.6 user preset names `Prusament PLA @MK4IS 0.6`, which the bundle no longer has |
| a tag "never changes by itself" | true for every tag the Studio wrote (exact settings) | a hand-typed file still in sugar re-expands from the CURRENT preset at its next compile (M8a's rule). See the open issues |
| "Apply?" | `GET /api/prusa/stale` and the `stale` count in the `prusa` event; the click is `POST /api/preset/apply` | the inspector row is M8b2's |
| the Library's cards for the pairs | made on Select only, as the recommended default (question 5) | |
| Library | also a Sticker printers collection, and the catalog is `catalog_all` | Merge 1's open item: library.py is this lane's |

## Open issues

* `server/app.py`'s `/api/preset/apply` and `/api/preset/of` still read `_P.catalog`, not `catalog_all` (Merge 1's item; not this lane's file). Two words for the orchestrator.
* A design file in sugar (`"preset": "..."` with no exact settings) re-expands from the current preset whenever it compiles again, so a changed profile changes those tags at the next edit. The fix belongs in `scene/design.py` / `server/design_api.py` (freeze the presets a design was opened with, or write the exact settings once). Not this lane's files.
* `ARCHITECTURE.md`'s rows for `core/prusa.py` and the server's routes are not updated (not this lane's file).
* M8c.2 was read from the conditions, not from PrusaSlicer's dropdown: Zach to confirm once.
* M8c.7's label bar fails for a label cut from the black at a stroke under the line width (above). A decision for Zach: a minimum stroke of one line for cut labels (core/label, a versioned rule: a new rule number), or a finer black nozzle.
* `tests/server/test_api.py::test_uvicorn_serves_on_5360_and_stops` was deselected in every run (the wave-2 port rule: only M8b1 binds 5360 / 5361).
