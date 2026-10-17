# The post-M3 audit: what was fixed

Fixed 2026-10-16 on `main` in ROOT. 26 findings: 5 "must" (C1, F1, F2, F3, F4), all fixed, and 21 "should": 17 fixed, 3 in part, 1 open. Each row says what changed and the test that shows it.

## Fixed

| Id | Finding | What changed | Shown by |
|---|---|---|---|
| C1 | the PDF sheet of DoD D6 was not built | `scene/sheet.to_pdf`: every visible tag as a sticker on REF's print sheet (`core.sheet`: A4, cut marks, `#id`, the ruler); `POST /api/scene/export/pdf`; Export > Sticker sheet (PDF) | `tests/verify/test_pdf_sheet.py` (pdfium 300 dpi: OpenCV reads every id of 12 tags in 3 dictionaries; a sticker within 0.13 mm of its size); `e2e/tests/export.spec.ts` reads the exported PDF |
| C2 | a stray Studio server held 5360 | it was gone when this run started; `tools/check.py` ran on free ports and stopped its own servers | `docs/status/RUN.md` |
| C4 | the "mode auto" rule was written five times | `core.form.new_tag_settings` (origin_v + Auto) and `core.form.mode_for`; plan/spec, server/newtag, core/edits and the Fusion adapter call them | `tests/core/test_new_tag_settings.py` (the rule is written once) |
| C5 | REF `_check_auto` had no home | `plan.auto.auto_still_fits(spec, size, square)`: two `plan_tag` calls and `same_build`; the adapter's `edit_open`, `POST /api/auto_check` and a note under Size call it | `tests/plan/test_auto_check.py` (golden Auto cases), `tests/adapters/test_feature.py`, `tests/server/test_audit_fixes.py` |
| C6 | Fusion features "planned", no M4 report, the map not at MIGRATION.md | the five ST-FUSION features `partial` with their reason (skeleton on the fake; gates F1-F8), ST-T-FUSION-1..6 `passing` on the fake; `docs/status/M4.md`; PLAN D10 names `docs/FUSION_ADAPTER.md` | `tools/spec_status.py` |
| C7 | the core opened files | print_beds' 12 file-I/O functions are REF's text in `server/beds_io.py`; the core opens nothing (the dictionary table inside the package is the one allowed read) | `tests/core/test_purity.py::test_no_file_io_in_core`; REF's print_beds suites run on `beds_io`; ST-T-PURE-1 passing |
| C8 | `keep_x` copied into the adapter | `core.geometry.keep_x` (REF's text, port-fidelity pinned); `target.py` imports it | `tests/core/test_port_fidelity.py`, `tests/adapters/test_target.py` |
| F1 | a typed first id did nothing until Renumber; bad ids accepted | `scene.set_first_id`: checked (0 or more, every id of the board in the dictionary, not on a locked tag) and used at once; a refusal is a 409 shown under the row, the field red | `tests/server/test_audit_fixes.py`, `e2e/tests/audit.spec.ts` |
| F2 | a typed cols x rows was dropped silently | a warning under Columns x rows: "5 × 2 does not fit the 40 × 40 mm target at 13.0 mm checkers: using 3 × 3"; on a face, an info line | `tests/plan/test_audit_messages.py` |
| F3 | Escape on an open dropdown also deselected | the open list or menu takes the Escape (capture phase); the app ignores a taken key | `e2e/tests/audit.spec.ts` |
| F4 | verify rows stayed green after an edit | each report keeps the spec it was made from; a changed tag's row reads "not verified since the change", with Verify again | `e2e/tests/audit.spec.ts` |
| F5 | every new tag and copy got id 0 | `scene.number_one`: the stable numbering with every other tag fixed; Add (`number: true`) and Duplicate use it | `tests/server/test_audit_fixes.py`, `e2e/tests/audit.spec.ts`, `ids.spec.ts` |
| F6 | a locked tag's ink fields stayed editable; "Error: " twice | the ink fields are disabled with one line why (name, place, lock, visibility still change); the IDs First field too; no "Error: " prefix | `e2e/tests/audit.spec.ts` |
| F7 | label messages were walls of text, repeated, on the wrong row | the plan routes a label message to the row its words name (cap, place, nozzle) and drops a note that repeats it; the inspector shows one short line (the plan's words in the tooltip); the summary is the field and the first clause | `tests/plan/test_audit_messages.py`, vitest, `e2e/tests/audit.spec.ts` |
| F8 | a bad Cells value printed a Python dict | "cell 0 mm: 0.01 to 20 mm (read as the legacy 0.5 mm steps)" under Cells > mm; the inspector refuses such a value before sending it | `tests/plan/test_audit_messages.py` |
| F9 | the cell-multiple line sat in the general box | routed to `numbers.size` | `tests/plan/test_audit_messages.py` |
| F12 | New / Open dropped unsaved changes silently | a dot after the scene name; New and Open ask "Save changes?" (Save, Don't save, Cancel); closing the tab asks | `e2e/tests/audit.spec.ts` |
| F13 | overlapping tags raised nothing | `scene/checks.py`: overlapping targets are a scene issue (`GET /api/scene?plans=1` `issues`), outlined on the canvas with a note; the sheet's Verify says "Not as planned" (`ok` false, `markers_ok` kept) | `tests/server/test_audit_fixes.py`, `e2e/tests/audit.spec.ts` |
| F15 | Renumber errors leaked `|tag` and sat away from the row | each message on its tag's row, the marker dropped (the old strip regex had a backspace byte in place of `\b`) | vitest, `e2e/tests/audit.spec.ts` |
| F16 | the Library's Edit had no checks; search per collection; HTTP codes | the Edit form checks each number against the range a preset keeps (the server refuses too: a 422 per field); typing searches every collection; messages without status codes; an empty name refused; icon dropdowns | `tests/server/test_audit_fixes.py` (the ranges = `normalise`'s), `e2e/tests/library.spec.ts`, `audit.spec.ts` |
| F17 | 3D had no labels or scale; the z scale stretched the axes; the grid ended | a name and ids sprite per tag; the axes outside the z-scaled root; the grid sized to the scene (10 mm cells) with a 10 mm bar | `e2e/tests/audit.spec.ts` (reads `window.__studio3d`) |
| F18 | Tab on a focused button toggled 2D / 3D | Tab toggles only from the canvas or the page; elsewhere focus moves | `e2e/tests/audit.spec.ts`, `served.spec.ts` |

## Fixed in part, or open

| Id | State | Why |
|---|---|---|
| C3 | open | REF moved past `c8216ff` in 10 add-in files the core's ports came from. Re-pinning means new goldens from REF's newer code and re-porting `summary_text` / `fit_text` / `label_issues`: a step of its own before the Fusion-gated switch (it changes what the goldens pin while other agents still commit to REF). Nothing is wrong today: every golden and port reads the pinned blob |
| F10 | in part | a preset that changes the dictionary now says so: the Library's Info warns, Select asks first, and the Preset row's status says which tags changed. Whether print presets should hold the dictionary at all is Zach's call (the finding says "decide with Zach") |
| F11 | in part | Label on: the message now says in one line what makes room ("a finer label nozzle or a smaller marker"). A fresh ChArUco on the 40 mm box still warns under the cell minimum: Auto's choice is a versioned rule (CELL_RULE / autosize), and changing it would move every existing Auto tag. It needs a new rule version and Zach's OK |
| F14 | in part | plans, top views and meshes are cached by their spec; `GET /api/scene` is written straight out (25 tags: 0.27 s -> 0.02 s warm, 0.05 s with meshes); Verify shows progress per tag. Not done: a client-side plan cache and one request for a multi-select edit |
