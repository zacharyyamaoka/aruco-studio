# M6a: stickers, holes, perimeter, label rule 3, the sheet, WYSIWYG, the print routes

Built on branch `lane/M6a` (worktree `aruco-studio-wt/M6a`), 2026-10-16 night, from `main` at `8cbc8be`, by Opus 5.5 with Zach asleep: every open question took its recommended default (Letter first, Holes: Avoid, 0 / 90 only, boxes not nesting, no Made-by row, rule 3 in any black square). Not merged into `main`. Design: `docs/design/M6_stickers_profiles_print.md` (M6a) and `manufacturing_intent.md` (M6.1-M6.8); routes: `docs/API_sheet.md`.

## What was built

| Piece | Where |
|---|---|
| How a tag is made: `settings.make` (rule 1; absent = 3D printed, bit for bit), `make_of` with junk read as 3D and numbers clamped, `holes_of`, the sticker's twin numbers, the Marker cut, the no-white rule, the words | `core/make.py` (new) |
| The preset is the machine: `profile.kind / dpi / page / landscape / margin_mm / stock_mm / sheet`, `kind_of`, the two built-ins (Letter first, then A4: whole dots 0.042333 mm, stock 0.1, min cell 1 mm, stroke 0.2, spaced), `catalog_all`, `collections` (3D printers / Sticker printers); a sticker tag's `preset_of` reads as a sticker printer | `core/presets.py` |
| The new-tag rule stamps `make` (made_by, else the preset's kind), `holes: "avoid"` and label rule 3; a sticker is White + black, New body, no pins, no trim | `core/form.py new_tag_settings` |
| Label rule 3: a manual ChArUco label in any black square, checked against THAT square; `RULES = {1, 2, 3}`, `NEW_RULE = 3`; `charuco_black_squares`, `label_square` | `core/label.py` |
| A sticker plans as its 3D twin's fit, mark and label on a thin stock: parts `sticker` (white, 0..t, its cut polygon) and `ink` (black, t..t + 0.01: cells, triangle, label); frame on the ink top; `made_by`, `rules.make`, `guides.cut_line`, `record.fusion.make`; its own warnings | `plan/plan.py`, `plan/evaluate.py` (`sticker=`), `plan/layers.py` |
| Holes: ignore = the fit and the label's white on the outer loop only; the trim still reads every loop; `warn` "the tile covers N holes" / "the marker crosses hole k"; `guides.target_ignored` | `plan/evaluate.py fit_loops`, `plan/plan.py` |
| Perimeter: Marker = the sticker grown by its margin (a corner cut cuts it), Profile = the outline with every hole; `place: white` without white is read as auto with a `warn` | `plan/layers.py cut_line`, `plan/plan.py sticker_inputs` |
| The target: `CHORD_MM = 0.05` (core.faces' tolerance), `chord_segments`, loops normalised on reading (outer counter-clockwise, holes clockwise), a loop outside the outline and an island in a hole are errors | `plan/target.py`, `plan/spec.py` |
| The form: Make rule, Made by (read only), Perimeter, Sticker thickness / margin, Cut line, Holes; every row's `intent` (3d / 2d / both), `label_2d`; a ChArUco label "In a black square" only; a Marker sticker without margin "On the black" only | `plan/fields.py` |
| The plan-driven sheet: `PrintItem.outline_mm / ink_mm / caption / made_by / name / ids`, `SheetSettings.mode`; `layout_stickers` (spaced: FFD shelves, captions, crop marks; tight: guillotine shelves, `cuts()`), cut lines with holes (a cross under 3 mm), turn 90 when only that fits, rejected with a reason past the page; one list of page operations written as PDF and as SVG; `sticker_summary` = sheet.json | `core/sheet.py` (REF's text kept above "the sticker sheet") |
| The scene's stickers as items (the plan's cut line and top-view black, the caption) and their three files | `scene/sheet.py` |
| The print bundle: sheet.pdf / .svg / .json, `images/`, `print3d/` (STLs, `parts.json` that `core.beds.load_parts` reads, `aruco_tags.3mf`, beds, parts), `markers.json`, the ledger marked printed | `scene/export.py` (new) |
| WYSIWYG: pdfium at 600 dpi, each sticker's box against the plan's own top view on the same pixels, OpenCV's ids and side, the letters, the cut line, the two bars | `verify/sheet_check.py` (new) |
| Routes: `GET /api/scene/sheet.svg`, `sheet.json`, `print.pdf`; `POST /api/scene/export/print`, `/api/scene/verify/sheet`; `/api/new` from a preset (and `made_by`), `/api/presets` both kinds with collections | `server/sheet_api.py` (new), `server/app.py` (those two routes only), `server/models.py` |

## Done checks

| # | Check | Result | Test |
|---|---|---|---|
| M6a.1 / M6.1 | legacy = 3D: 824 evaluate() goldens replay (unchanged test); `plan_tag(spec)` = `plan_tag(spec + make print3d)` but for `rules.make` | PASS, 824 / 824 | `tests/plan/test_make_plan.py::test_legacy_is_3d_both_ways`, `tests/plan/test_golden_evaluate.py` |
| M6.2 | a sticker: parts, layer z, frame at t + 0.01, the twin's ids, the ink's top view = the twin's pattern pixel for pixel at 20 px / mm | PASS, 72 cases (3 layouts x 4 turns x 3 marks x label off / on), 0 pixels differ | `test_a_sticker_plans_as_its_3d_twin_on_a_thin_stock` |
| M6.3 | OpenCV reads every case; PnP within 0.1 mm / 0.1 deg | PASS, 72 / 72 | `test_opencv_reads_every_sticker_and_its_frame` |
| M6.4 | junk make plans as 3D / clamped with a warn; plan_tag never raises | PASS, 2,000 random specs, 0 exceptions | `test_junk_make_*`, `test_plan_tag_never_raises_on_2000_specs_with_make` |
| M6.5 | 40 tags (20 / 20, two families): unique per family across kinds; a sticker #3 and a printed #3 are one duplicate; a second renumber changes nothing; ledger `bam_aruco_ids_ledger/1` | PASS | `tests/scene/test_print_bundle.py::test_forty_tags_both_kinds_one_ledger` |
| M6.6 | the bundle: the PDF holds exactly the 20 stickers, each side within 0.15 mm at 600 dpi, the bars within 0.1 mm, the labelled stickers' letters there; print3d/ exactly the 20 3D tags, parts.json loads, the 3MF one object per part, cells on slot 2; markers.json every tag with kind and file; ledger marked | PASS | `test_print_bundle.py` |
| M6.7 / M6a.2 | presets: no kind = 3D; the Letter built-in gives `cells {rule 1, of cell, mm 0.042333, min_mm 1}`, `make {by sticker, thickness 0.1, perimeter marker}`; `preset_of` gives it back (`same_print`); `/api/presets` both collections; REF's pinned `normalise` (exec'd from the blob) keeps the rest and drops the machine keys | PASS | `tests/core/test_make.py`, `tests/server/test_make_api.py` |
| M6.8 | `/api/form` every row has `intent`; `/api/new made_by: sticker` has `make`, no trim; `PUT /api/remembered` round-trips `made_by`; `?made_by=sticker` lists no PrusaSlicer profile; a locked tag's PATCH of `settings.make` is 409 | PASS | `tests/server/test_make_api.py` |
| M6a.3 | Holes: ignore >= avoid on every palette face with holes (disc4, plate_hole, ring; single and ChArUco); avoid = today byte for byte (824 goldens with `holes: avoid`, and the same plan JSON); the crossing `warn`; junk = avoid + `warn` | PASS; the plate: 23.0 -> 37.0 mm | `tests/plan/test_holes.py` (45) |
| M6a.4 | Perimeter on all 12 palette faces x Marker / Profile x label off / black / white: Marker a rectangle, Profile the loops with every hole, the sticker layer = cut_line; white + Marker + margin 0 read as auto with the `warn`; margin 6 mm builds on the white | PASS, 72 cases | `test_the_perimeter_on_every_palette_face`, `test_a_margin_makes_white_for_a_label` |
| M6a.5 | rule 3 builds in each of the 18 black squares of a 5 x 7 ChArUco; rule 2 refuses all but the top-left as today; the label goldens keep rules 1 and 2; the form: "In a black square" only | PASS, 18 / 18 (rule 2: 1 / 18) | `tests/core/test_label_rule3.py`, `test_golden_core.py`, `test_ref_label_rule1.py` |
| M6a.6 | tight: four 30 mm stickers, one shelf, **7 cuts** (16 spaced); three sizes, one shelf per height, no sticker crosses a shelf line; spaced: today's placement, a caption and 8 crop lines per sticker; a 400 mm sticker rejected with a reason in both modes | PASS | `tests/core/test_sheet_modes.py` |
| M6a.7 | the disc, the D-shape, the L (and the plate with a hole, a 210 mm strip that turns) with Profile, packed by their boxes in both modes; the PDF strokes every outline and hole as a 0.1 mm grey hairline; sheet.json has page, x, y, rotation, outline | PASS | `test_odd_shapes_are_packed_by_their_boxes_with_every_cut_line` |
| M6a.8 | WYSIWYG on 12 stickers (single / grid / ChArUco, labels on the black and the white, triangle and cut corners, two Profile outlines, one turned), spaced and tight, Letter and A4 | PASS, numbers below | `tests/verify/test_sheet_wysiwyg.py` |
| M6a.9 | sheet.svg's `data-sticker` boxes = sheet.json within 0.01 mm | PASS, 9 stickers x 2 modes x 2 pages (both written to 0.0001 mm) | `test_the_svg_and_sheet_json_agree` |
| M6a.10 | a 96-point disc with 3 holes: plan_tag under 50 ms, Holes: avoid | PASS, **21.9 ms** (best of 20, other workers running); REF's text took 64 ms here, see deviation 3 | `test_a_96_point_disc_with_3_holes_plans_under_50_ms` |
| M6a.11 | `tools/check.py` exits 0; nothing on 5360 / 5361; nothing written under `%USERPROFILE%\CADExporter` or into REF | PASS for the groups this lane may run (below); no listener on 5360 / 5361 after; the tests run with USERPROFILE in a temp folder; REF was only read (`git show`) | |

### M6a.8 numbers (worst over the 12 stickers)

| Page, mode | Ink XOR (bar 2 %) | Side error (0.15 mm) | Label IoU (0.9) | Outline (0.15 mm) | Bar error (0.1 mm) |
|---|---|---|---|---|---|
| Letter, spaced | 0.28 % | 0.011 mm | 0.978 | 0.072 mm | 0.009 mm |
| Letter, tight | 0.27 % | 0.012 mm | 0.982 | 0.072 mm | 0.009 mm |
| A4, spaced | 0.82 % | 0.008 mm | 0.959 | 0.072 mm | 0.034 mm |
| A4, tight | 0.61 % | 0.009 mm | 0.971 | 0.072 mm | 0.034 mm |

A4 is 4960.6 px wide at 600 dpi; pdfium makes the bitmap 4961 px and fits the page to it (a 0.01 % stretch), which is most of A4's larger numbers. Every hole of the disc was found. The check also fails when it should: two stickers' plans swapped, or the page printed at 97 % (`test_a_wrong_page_fails_the_check`, `test_a_mis_scaled_print_fails_the_bars`).

### The check run

`.venv/Scripts/python tools/check.py adapters core plan scene server verify` from the worktree, 2026-10-16 about 22:25: **OK in 269 s**.

| Group | Result |
|---|---|
| adapters | 97 passed in 40 s |
| core | 7,301 passed, 4 skipped in 36 s |
| plan | 499 passed in 81 s |
| scene | 13 passed in 7 s |
| server | 43 passed in 14 s |
| verify | 111 passed in 90 s |

Not run here: `studio` and `e2e`. Only the lane that owns `studio/` and `e2e/` may bind 5360 / 5361, and this lane changed nothing under them. New tests: 376 (`tests/core/test_make.py` 18, `test_label_rule3.py` 25, `test_sheet_modes.py` 13, `tests/plan/test_make_plan.py` 254, `test_holes.py` 45, `tests/scene/test_print_bundle.py` 6, `tests/verify/test_sheet_wysiwyg.py` 7, `tests/server/test_make_api.py` 8).

## Where the build differs from the note

| # | What | Why |
|---|---|---|
| 1 | Files outside M6a's owner list, each a small change: `tests/core/test_port_fidelity.py` (names now adapted on purpose: label `RULES`, `_offset_label`, `label_violations`, `check_label`, `describe`; presets `normalise`, `line_mm`; sheet `PrintItem`, `SheetSettings`; marker_table `MarkerRow`; autosize `_rect_inside`), `tests/core/test_golden_core.py` (`RULES` is `{1, 2, 3}`), `tests/server/test_studio_api.py` (a new tag stores label rule 3), `plan/mesh.py` and `verify/render.py` (two words each: the parts `sticker` and `ink`; `top_view(grid=)`), `core/autosize.py` (deviation 3) | the design asks for each behaviour; no other wave-1 milestone owns these files |
| 2 | `label.RULE` stays 2; `label.NEW_RULE = 3` is what a new tag stores (through `core.form.new_tag_settings`) | REF's own suites pin `RULE == 2` and `LabelSettings().rule == 2`; rule 3 is otherwise exactly as the note says |
| 3 | `core/autosize._rect_inside` skips a segment that lies more than 1 pm beyond one side of the box before REF's Liang-Barsky, and tests the centre last | REF's text took 64 ms for M6a.10's disc; now 22 ms. Every answer is the same: such a segment gives False in Liang-Barsky exactly, and the three tests are pure. The 824 evaluate() and the autosize goldens replay unchanged |
| 4 | The sticker built-ins are not in REF's `builtins()` / `catalog()`; `catalog_all()` adds them, and `/api/new` and `/api/presets` use it | REF's presets suite pins its catalog. `/api/preset/apply`, `/api/preset/of` and the Library (`server/library.py`) still read REF's catalog: the Library has no Sticker printers collection yet and a sticker tag's Preset row reads "custom". For M8b2 (it owns the UI) or a one-line follow-up in those routes |
| 5 | Tight cuts are counted as (shelves + 1) + the sum of (columns + 1) | the note's formula (shelves + 1 + sum(columns - 1)) gives 5 for its own example; its example and the done check say 7 (2 long + 5 short) |
| 6 | The sheet check is `POST /api/scene/verify/sheet` | ROADMAP's wave-1 rule (not a `?sheet=1` flag on the route M8a rewrites) |
| 7 | `GET /api/scene/print.pdf` gives the bytes `POST /api/scene/export/print` writes as `sheet.pdf`; `/api/scene/export/pdf` keeps REF's sheet | M8a replays `main`'s export routes; M6c.1 (in M8b2) should compare the print hook's bytes with `print.pdf` or `export/print`, not `export/pdf` |
| 8 | A Profile sticker's label white is its outline WITH its holes, under Holes: ignore too | the paper is cut there; for a 3D tag ignore reads the outer loop, as the note says |
| 9 | A Profile sticker gets no corner cut (an `info` says so) | the outline is the cut line; Perimeter = Marker cuts a corner |
| 10 | The sticker's "cells not whole dots" info and "label stroke under one dot" warn are not built | the plan does not know the dpi (the preset does); `cells` from a sticker preset are whole dots by construction |
| 11 | The oracle renders the plan on the page's own pixels with 2 x 2 samples (8 x 8 in a label box); the label IoU is weighted by each pixel's share of letter; cut-line points within 5 px of ink are counted as hidden, not missing; pdfium is asked for a hair less than 600 / 72 | cv2.fillPoly takes every pixel an edge touches (one sample grows the black by a pixel); a 0.2 mm stroke is 5 px, so a 50 % threshold measures the anti-aliasing; a cut line along the ink cannot be seen; 792 pt x 600 / 72 is 6600.000000000001 in floats and pdfium made 6601 rows, stretching the page by a pixel |
| 12 | `print3d/` prints the body under a tag only when the tile joins it; the 3MF has no PrusaSlicer config | a New-body tag prints on its own; the printer chain is M8c's |
| 13 | `MarkerRow.made_by` exists, but the renumber rows (`scene/ids.py`) do not carry it | not M6a's file; every plan carries `made_by` for the IDs table |
| 14 | On a 3D tag the Perimeter row is `settings.trim`: the field rows say so (`on_3d`, `label_perimeter`), nothing new is stored | as the note says; the row itself is M6b's (in M8b2) |
| 15 | `docs/API.md` is not edited; the routes are in `docs/API_sheet.md` | M8a edits `docs/API.md` in the same wave |
| 16 | `sheet_api.py` reads the open scene through `app._scene()` (or `STATE["scene"]`) and `app.cached_plan` | if M8a renames them, those two helpers in `sheet_api.py` follow |

REF's worktree changed during this run in `tests/test_aruco_skip_unchanged.py` (22:27) and the Fusion bridge's files under `%USERPROFILE%\CADExporter\_aruco_bridge` were touched: both are other sessions' live Fusion work; this lane only read REF through `git show`.

## Include lines for the merge

| File | Line | Where |
|---|---|---|
| `aruco_studio/server/app.py` | `from . import sheet_api  # noqa: E402,F401  (M6a: the sticker sheet routes)` | at the end of the file (any place after `app = FastAPI(...)` works: `sheet_api.install` puts its routes first) |
| `docs/API.md` | `The sticker sheet, the print bundle and the presets as machines (M6a): docs/API_sheet.md.` | at the end |

Until the first line is in, `python -m aruco_studio.server` does not serve the M6a routes; the tests import `sheet_api` themselves.

## For the next milestones

| Who | What |
|---|---|
| M8a | `plan/newtag.py` keeps calling `core.form.new_tag_settings`; pass `preset=` (and `made_by=`) so sugar makes the same `make`, `holes` and label rule 3 as `/api/new`. `core.faces.CHORD_TOL_MM` and `plan.target.CHORD_MM` are the same constant now |
| M8b2 (M6b, M6c) | the rows are in `/api/form` (`intent`, `label_2d`, `choices_by_layout`, `hidden_layouts`, `choices_when`, `show_when`); the sheet dialog reads `/api/scene/sheet.svg` and `sheet.json`; Print reads `/api/scene/print.pdf`; `/api/presets` has `collections`; switch `/api/preset/of`, `/api/preset/apply` and the Library to `catalog_all` (deviation 4) |
| M8c | `scene/export.print3d` writes `parts.json` and the beds without a PrusaSlicer config; the physical printer's chain goes there |
