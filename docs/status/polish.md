# Lane polish (2026-10-17 morning)

Branch `lane/polish`, worktree `C:\Users\BAM\Documents\aruco-studio-wt\polish`, from `main` at `46f2bac`. Not merged. Zach was asleep, so Q1 took its recommended default. A second lane (`lane/speed`, the drag preview and server speed) ran at the same time and owned `studio/`, `e2e/` and the server's speed paths.

## 1. Q1: label rule 5

| | |
|---|---|
| The rule | A label **cut out of the black** (role `cut`) strokes at least one line of the tag's cell rule. The floor is `label.LINE_STROKE` = **1.1 lines**: 0.748 mm at 0.68 mm lines, so 3.74 mm letters. A label on the white (black ink on the white) keeps the nozzle floor, 3.0 mm letters at 0.6 mm |
| Why 1.1, not 1.0 | Measured in the headless slice (the forearm's front and back, `'#0-5'` in a 19 mm ChArUco square, the fixture's MK4 MMU3 0.6 chain). At 0.68, 0.70 and 0.72 mm the white strokes print (every ink pixel 1.0), but 10 of 85 pixels fail: the one-pixel black counters drop out. At 0.74, 0.76, 0.80 and 0.82 mm all 85 pixels print. 1.1 lines is still "at least one line"; it is the first round step that prints |
| Where the line comes from | the tag's `cells` setting: its step when it is of the cell (`plan/evaluate.cell_line_mm`). No cells, or a marker step: no line, and rule 5 plans as rule 4 |
| Who stores it | a NEW tag: `core.form.new_tag_settings` stores `label.NEW_RULE`, now 5. A tag that stores rule 1, 2, 3 or 4 plans exactly as before: the line is handed to `plan_label` for every tag but only rule 5 reads it (tested byte for byte), and the label goldens (rules 1 and 2) replay |
| A typed cap under the floor | refused on the black, with the reason under Label: "a 3 mm cap cut from the black gives strokes under 1.1 of the 0.68 mm lines: 3.74 mm letters at least (label rule 5)" |
| Auto | a ChArUco square too small for the text at 3.74 mm refuses it (rule 4's one message). A border row too thin moves an ArUco label to the white |
| The record | `Label.to_dict()` carries `line_mm` for a rule-5 label only (not a setting: `LabelSettings.to_dict()` is unchanged), so `relabel` and `copy_regions` size a copy with the same floor, and `check_label` names a stroke under it |
| `plan/fields.py` | no change needed: the Label rule row's choices come from `label.RULES` (now 1-5) and its `new` is `label.NEW_RULE` (5); `/api/form`'s `rules.label_new` says 5 |

What a rule-5 label costs on the shipped examples: nothing. The forearm's front still builds `'#0-5'` (at 4.1 mm, its own cap); the other three faces were refused under rule 4 already. The `'#id + name'` label M8c sliced (two lines in a 19 mm square) is refused under rule 5 instead of being built at 0.64 mm and closing up.

| Test | Shows |
|---|---|
| `tests/verify/test_slice_check.py::test_the_forearm_labels_print_their_pixels` | **was the strict xfail; now a pass for rule 5**: `'#0-5'` typed at exactly the floor (3.74 mm, stroke 0.748 mm), sliced headless: every font pixel of front and back prints, the black around it is there |
| `test_rule_5_refuses_what_rule_4_built_under_one_line` | no slicer: the forearm's `'#id + name'` is refused under rule 5 (the reason names 3.7 mm letters); the same spec under rule 4 builds `'#0-5\|FOR…'` at 0.64 mm; a typed 3.2 mm cap is refused saying "rule 5" |
| `test_rule_4_is_unchanged_and_still_loses_pixels` | the M8c.7 finding kept as found: a rule-4 tag is planned as before (0.64 mm) and its slice still loses pixels |
| `tests/core/test_label_rule5.py` (32) | the rule numbers; rules 1-4 identical with and without the line (24 cases: auto, a typed cap, the white, `#id + name`, a single marker, a typed cap on a single marker); the floor on auto, on a typed cap, on the white (unchanged), on a border row (moves to the white), without cells; the record round trip, `relabel`, `check_label` |
| `tests/core/test_golden_core.py`, `test_label_rule3.py`, `test_label_rule4.py`, `test_make.py`, `test_port_fidelity.py`, `tests/server/test_make_api.py` | the pinned numbers moved from 4 to 5 (`RULES` 1-5, `NEW_RULE` 5); rule 3 and rule 4's own tests unchanged. `test_port_fidelity` lists `Label`, `LabelSettings`, `from_dict`, `relabel` as not REF's |

## 2. The tool box takes a paste and an input method

The bottom "type W H and Enter" box listened only to keydown (in `App.tsx`). Now the box itself also takes:

| Input | How |
|---|---|
| Ctrl+V on the page (`80 50`) | a `paste` listener while a typed tool is on; a paste into another field (the palette, the inspector) stays that field's |
| An input method, dictation, `insertText` | a hidden field inside the box. Clicking the box focuses it; an IME key (`Process`, key code 229) moves focus to it so the composition lands there. Its `input` events add the text; during a composition nothing is taken until `compositionend` |
| Full-width digits | folded with NFKC: `７０　４０` reads `70 40`; `×`, `X`, `*` read as the `x` separator; a minus sign reads `-`; lines and tabs are spaces; any other character is dropped (`diameter: 25 mm` gives `25`) |
| Keys in the hidden field | Enter confirms, Esc cancels, Backspace deletes; a tool key (H, C, ...), Tab or Ctrl+Z goes back to the page with the field left |

Files, so the merge can handle overlaps with the drag-preview lane:

| File | Change |
|---|---|
| `studio/src/app/BottomBar.tsx` | the only Studio source file changed: `typedText`, `addTyped`, `useTypedInput`, `sinkKey`, the hidden field in the typed box |
| `e2e/tests/typed_input.spec.ts` | new, the one test file: a real Ctrl+V on the page, a pasted full-width size after a typed key, words dropped; a real Ctrl+V in the box and the palette keeping its own paste; `insertText` of a full-width size, a composition, a tool key from the field |
| `docs/STUDIO.md` | one row (Tools) and the label rows |

Not touched: `App.tsx`, `store.ts`, `styles.css`, the canvas, `View3D.tsx`.

## 3. The final audit's nits (A5-A10, C1-C4)

### Fixed

| Id | Was | Now | Test |
|---|---|---|---|
| A5 | `/api/health` said `"scene": "arucostudio.scene/1"` only | it adds `"file": "arucostudio.scene/2"`; `scene` stays `/1`, the shape `GET /api/scene` answers (`docs/API.md` says so) | `tests/server/test_api.py::test_health_dictionaries_options_form_targets` |
| A6 | spaced `cuts()` was 4 per sticker (16 for four 30 mm stickers) | a guillotine count per page: every straight cut that crosses no sticker counts once; the better of starting across or along. Four 30 mm: 10. Interlocking stickers (a pinwheel) still count 4 each. Tight keeps the design's count (7) and still wins | `tests/core/test_sheet_modes.py` (+1) |
| A7 | `assert any("printhost" not in t for t in out)` was always true | removed; the scan now also covers a real `prusa` event (a watcher tick after an edit of kappa) and `GET /api/prusa/watch` | `tests/server/test_prusa_api.py::test_the_marker_is_nowhere` |
| A10 | the Renumber report's rows had no `made_by` | each row has `made_by` from the tag's plan (`print3d` / `sticker`; "" when it does not plan) | `tests/scene/test_design.py::test_renumber_rows_say_how_each_tag_is_made` |
| C2 (server half) | the size error read "size -5.0: 0" in the short line | "Marker size -5 mm: 0 for Auto, or more than 0 mm" (and "Checker size"), nothing the short line cuts | `tests/plan/test_validate.py::test_a_negative_size_says_so_in_words_the_short_line_keeps` (2) |
| (morning) | the cell-minimum warn's short line dropped the fix (it cut at "; ") | joined with " — ": the short line reads "…it may print poorly — a Checker size of 18 mm passes" | `tests/plan/test_cell_min_fix.py` |

### Not fixed, and why

| Id | Why | The fix, for a later pass |
|---|---|---|
| A8 | not a code nit: M8c.2's yes / no table, for Zach to read off PrusaSlicer once (STATUS Q4) | |
| A9 | the "Old sticker sheet (PDF, A4, cut marks)" entry is in `studio/src/app/Toolbar.tsx` (the other lane's this run). Pointing `/api/scene/export/pdf` at the new sheet is not safe: the new sheet prints stickers only, and `e2e/tests/export.spec.ts` reads every 3D tag's ids off the old one | rename the menu label to "Sheet of every tag (PDF, A4, REF's layout)" (one line in `Toolbar.tsx`), or retire the route once M7 no longer needs REF's sheet |
| C1 | the status bar line is built in `studio/src/store.ts` (`${path} = ${value}`), a file the drag-preview lane edits | look the path up in `/api/form` and say the row's label and the choice's words ("Type: ChArUco board") |
| C2 (Studio half) | "1 layouts fit" (`Inspector.tsx`), "Open PrusaSlicer: the project, as a project" (`Dialogs.tsx`), the Preset row cut at 1500 px (CSS): all in `studio/` | "1 layout fits"; "open the project in PrusaSlicer"; let the Preset row wrap |
| C2 ("sticker" for a 3D tag's tile) | the size line is REF's text (`core.form.size_line`) and "sticker" is Zach's own word for the white square (2026-10-08); REF's suites pin it | say "tile" for a 3D tag, under a rule of the form |
| C3 | floats and 60+ exact keys after the first edit: the write path (`scene/design.py`, `studio/src/model/json.ts`) is a design change and the e2e checks the file byte for byte | write ints as ints; write only the changed keys as exact |
| C4 | drawing slips during a drag, overlapping sprites, a Turn handle on a round hole: the canvas and the 3D view, the drag-preview lane's | draw holes from the preview only while dragging; stack the sprites; no turn for circles |

## 4. The check

`.venv/Scripts/python tools/check.py adapters core plan scene server verify studio` from the worktree (`.venv` is a junction to ROOT's), 2026-10-17 morning: **OK in 296 s**, exit 0.

| Group | Result | main (morning) |
|---|---|---|
| adapters | 97 passed | 97 |
| core | 7,387 passed, 4 skipped | 7,354 (+32 rule 5, +1 cuts) |
| plan | 531 passed | 529 (+2 the size words) |
| scene | 43 passed | 42 (+1 made_by) |
| server | 91 passed | 91 |
| verify | 120 passed, 0 skipped | 117 + 1 strict xfail (+2 rule 5 tests; the xfail is a pass) |
| studio | build (the app and the kit) + vitest (44) passed | 44 |

`tools/check.py --trace`: ported 212, not ported 17, skipped 4, **missing 0**. `tools/spec_status.py --check`: features built 75, partial 7, deferred 4, planned 18; tests passing 89, failing 0, planned 4.

The e2e group is the other lane's (5360 / 5361). It was run here only to see the tool-box change break nothing, on ports 5380 / 5381 (`ARUCO_STUDIO_API_PORT` / `_UI_PORT`): all 50 specs pass (47 of main's + 3 new). The first run failed 3 specs only because the worktree had no `.venv` for the OpenCV helper; with the junction they pass. The screenshots that run rewrote were restored (`reports/screens/` unchanged). Nothing listens on 5380 / 5381 after; 5360 / 5361 / 5370 / 5371 were not used.

PrusaSlicer ran only as the headless console of the slice tests, on a scratch datadir. Fusion, REF, `%APPDATA%\PrusaSlicer` and `%USERPROFILE%\CADExporter` were not touched. `goldens/**` unchanged. No remote, no push, no merge.
