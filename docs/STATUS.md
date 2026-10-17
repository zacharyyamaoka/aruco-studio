# ArUco Studio: status

## Now: 2026-10-17, after the audit fixes

`main` of `C:\Users\BAM\Documents\aruco-studio` (local only, no remote). Since the hand-over below, these milestones were built and merged, each with its record:

| Step | What | Record |
|---|---|---|
| M6a | stickers, the preset as the machine, Holes avoid / ignore, Perimeter, label rule 3, the sheet (spaced / tight, SVG and JSON), the print bundle, WYSIWYG | `docs/status/M6a.md` |
| M8a | the design file `arucostudio.scene/2`, its compile, the watcher, `/api/events`, the CLI, the three examples | `docs/status/M8a.md` |
| Merge 1 | wave 1 merged | `docs/status/merge-Merge 1.md` |
| M8c | PrusaSlicer's physical printers, live sync, Send to PrusaSlicer, the headless slice check | `docs/status/M8c.md`, `docs/API_prusa.md` |
| M8b1 | the bare-bones mini CAD in the Studio, file first | `docs/status/M8b1.md` |
| Merge 2 | wave 2 merged | `docs/status/merge-Merge 2.md` |
| M8b2 | the kit (`@bam/ui`), the form from `plan/fields.py`, M6b's rows, multi-select, the sheet dialog, Print, Send to PrusaSlicer…, the Printers collection | `docs/status/M8b2.md`, `docs/KIT.md` |
| Audit fixes | frozen presets for typed files, label rule 4 (a ChArUco label stays in a black square), the palette by name, ids after a split list, Open's examples / recent / folders, Send's nozzle line, the sheet-only Export, hermetic port tests | `docs/status/audit-2026-10-17.md` |

The check, 2026-10-17 02:59-03:08 (`tools/check.py`, every group): adapters 97, core 7,354 + 4 skipped, plan 529, scene 42, server 86 (91 with the port tests added after), verify 117 + 1 strict xfail, studio build + vitest 44, e2e 47; **OK in 518 s**. `--trace`: missing 0.

Open, for Zach: the cut-from-black label stroke (a new label rule 5 or a finer black nozzle); a sticker's ChArUco Auto (a new rule); the forearm's live preview speed; M6c.5 (measure a printed 100 mm bar); M8c.2's dropdowns checked once in PrusaSlicer. The list with reasons: `docs/status/audit-2026-10-17.md`. `docs/spec.json` lists every milestone's features and tests (updated 2026-10-17).

Everything below is the 2026-10-16 ~21:00 hand-over, kept as it was.

# The hand-over of 2026-10-16

Final verification on 2026-10-16, about 21:00, on `main` of `C:\Users\BAM\Documents\aruco-studio` (local only, no remote). REF is cad-exporter's worktree `aruco-fusion-plugin-0e9bcb`, read at commit `c8216ff`.

What exists, in one paragraph: a pure Python core (`aruco_studio/core`, 16,266 lines, stdlib only) holds every versioned rule of the Fusion add-in bit for bit; `plan_tag(TagSpec) -> TagPlan` is REF's `evaluate()` as a pure function; a scene of many tags renumbers, saves and exports (SVG, PNG, PDF sticker sheet, STL, JSON); OpenCV reads every plan back; a FastAPI server on 127.0.0.1:5360 is the only I/O; a Vite + React Studio draws the 2D canvas and the 3D view; a Fusion adapter skeleton builds every golden case on a stand-in `adsk`. Nothing ran in Fusion.

The same facts as a page: `reports/status.html` (from `docs/spec.json`, with the screenshots).

## 1. The check run

`.venv/Scripts/python tools/check.py` from a clean shell, 2026-10-16 about 20:55. Ports 5360 / 5361 were free before, and nothing listened on them after.

| Group | Result |
|---|---|
| adapters | 97 passed in 40 s |
| core | 7,245 passed, 4 skipped in 42 s |
| plan | 193 passed in 65 s |
| scene | 7 passed in 5 s |
| server | 35 passed in 14 s |
| verify | 104 passed in 92 s |
| studio | build + vitest (19) passed in 6 s |
| e2e | 19 Playwright passed (1.6 m) in 98 s |
| **all** | **OK in 362 s**, exit 0 |

`tools/check.py --trace`: 233 REF sections, ported 212, not ported (Fusion / UI) 17, skipped (other venvs) 4, **missing 0**.

The 4 pytest skips are the parked `evaluate()` sections of the two legacy goldens in `tests/core`; `tests/plan/test_golden_evaluate.py` covers them.

## 2. Definition of Done (PLAN.md section 4)

| # | Check | Result | Evidence |
|---|---|---|---|
| D1 | `tools/check.py` exits 0 with every group | PASS | the table above; exit 0 |
| D2 | the four REF goldens replay bit for bit: cells 511 + 12, label 36, trim 26 + 288 | PASS | `tests/core/test_ref_cells_legacy.py` (511), `tests/plan/test_golden_evaluate.py::test_cells_legacy__12_evaluate_cases_against_196454c`, `tests/core/test_ref_label_rule1.py` (36 cases of `goldens/ref/aruco_label_rule1_golden.json`), `tests/core/test_ref_trim_legacy.py` (288), `::test_trim_legacy__26_evaluate_cases_against_5cf71bd` |
| D3 | >= 600 `evaluate()` cases from REF replay through `plan_tag`, with and without the adapter-only keys | PASS | 824 cases (`goldens/evaluate/matrix.json` 786 + `legacy.json` 38): `tests/plan/test_golden_evaluate.py`, `tests/plan/test_adapter_keys.py` |
| D4 | `docs/test_trace.md` covers 100 % of the 17 Fusion-free REF suites' sections | PASS | `tools/check.py --trace` prints `missing: 0` (233 sections) |
| D5 | `core` and `plan` import only the stdlib; `plan` and `scene` never import `adapters`, `server` or `verify` | PASS | `tests/core/test_purity.py` (5 tests, including no file I/O), `tests/plan/test_purity_plan.py` (3 tests) |
| D6 | OpenCV reads every id off every rendered plan, copy, mesh raster, PNG / PDF export and a 12-tag scene PNG; the tables equal cv2's; PnP within 0.1 mm / 0.1 deg | PASS | `tests/verify/`: `test_cv2_tables.py` (9,596 markers, 85 boards), `test_verify_plans.py` (48 plans + REF frame_pnp; PnP 0.057 mm / 0.023 deg), `test_mesh_and_scene_raster.py`, `test_pdf_sheet.py`; `tests/plan/test_exports.py` (PNG) |
| D7 | 40 tags renumber uniquely and stably; printed ids never move; a locked tag's ink never changes | PASS | `tests/scene/test_scene.py::test_forty_tags_unique_contiguous_and_stable`, `::test_printed_ids_never_move`, `::test_a_locked_tag_keeps_its_ink` |
| D8 | the Studio builds and >= 8 Playwright tests pass with >= 10 screenshots, every bar from the DOM or the store | PASS | build OK; 19 e2e tests in `e2e/tests/`; 42 screenshots in `reports/screens/` (4 of them `final_*.png` from this run); the bars read `data-*` attributes and `window.__studio` (`e2e/tests/helpers.ts`) |
| D9 | the Fusion adapter skeleton builds every golden case on the fake, one body per layer | PASS | `tests/adapters/test_build.py`: 814 cases, 3,785 layers, 69,565 probes |
| D10 | `docs/FUSION_ADAPTER.md` maps every (F) responsibility and every quirk | PASS | `tests/adapters/test_migration_doc.py` (4 tests, missing 0); 45 modules, 91 quirks |
| D11 | every feature and test `built` / `passing` with its check, or `planned` with a reason | PASS | `tools/spec_status.py --check`: features built 43, partial 9, deferred 3, planned 5; tests passing 71, planned 3. Every partial, planned and deferred entry has a `reason` (section 3 below) |
| D12 | nothing written into REF, `%USERPROFILE%\CADExporter` or Fusion; no server left on 5360 / 5361 | PASS | `git -C REF status --porcelain` before and after this run differs only by `tests/test_aruco_skip_unchanged.py` (untracked, 21:09, another session) and two `ArucoMarkers/__pycache__/.install_*.pyc` (21:08 and 21:10, another session's add-in install; this run never imports REF's ArucoMarkers). Under CADExporter only the Fusion bridge's `heartbeat.json` / `FUSION_OPEN.json` changed (other sessions use Fusion). `netstat`: no listener on 5360 / 5361 after the run |
| D13 | every commit on ROOT `main`, local only; parallel worktrees merged and removed | FAIL on the letter | `git remote -v` is empty and all 47 commits are on `main`. But `git worktree list` also shows `C:/Users/BAM/Documents/aruco-studio-preview` (detached at 827b0f5, clean), made by another session for a preview, not by this workflow. Left alone; Zach can `git worktree remove aruco-studio-preview` |
| D14 | every `TagSpec` field has a validation row, a test, an `Issue.field` key path and an `/api/form` entry; a wrong type is a 422 naming the key | PASS | `tests/plan/test_validate.py` (`test_every_row_of_the_table_has_a_bad_value_or_is_free`, `test_a_bad_value_is_an_issue_on_its_own_field`, `test_a_wrong_type_names_its_key_path`, `test_form_lists_every_row`); `tests/server/test_api.py` (422 naming the key path) |
| D15 | no golden under `goldens/` was made by the new code | PASS | `tests/core/test_golden_provenance.py` (provenance on every golden, copies equal REF's files at the pin, the maker refuses to run on the new code); `tests/plan/test_evaluate_provenance.py` |

14 of 15 pass. D13 fails only because of a worktree another session made.

## 3. What is open

### Findings not fully fixed (docs/status/AUDIT.md)

| Id | State | What is left |
|---|---|---|
| C3 | open | REF moved past `c8216ff` in 10 add-in files the ports came from. Re-pin: new goldens from REF's newer code and re-port `summary_text` / `fit_text` / `label_issues`. A step of its own, before the Fusion switch. Nothing is wrong today: every golden and port reads the pinned blob |
| F10 | in part | a preset that changes the dictionary now says so (Info warns, Select asks, the Preset row names the changed tags). Whether print presets should hold the dictionary at all is Zach's decision |
| F11 | in part | "Label on" says what makes room. A fresh ChArUco on Box 40 still warns under the cell minimum: Auto's layout choice is a versioned rule; changing it needs a new rule version and Zach's OK |
| F14 | in part | plans, top views and meshes are cached on the server; `GET /api/scene` is written out directly (25 tags warm 0.02 s). Not done: a client-side plan cache and one batched request for a multi-select edit |

### Nits from the audit (none fixed, except F26)

| Id | Area | Nit |
|---|---|---|
| C9 | tests | `tests/plan/test_record.py` tolerates up to 3 quirk cases; only c0370 is documented. Should assert `quirk == ["c0370"]` |
| C10 | goldens | a made golden's recorded sha256 is checked for length only; recompute it against the pinned blob when REF is present |
| C11 | scene | `scene.renumber` writes new ids to the tags even when the numbering plan is not ok, then skips the ledger. Should leave the tags alone when `not plan.ok` |
| C12 | goldens | no legacy ChArUco case and few label-rule-1 / manual-position cases in `goldens/evaluate`; add a small group to `tools/make_evaluate_goldens.py` and remake from REF |
| C13 | port fidelity | `plan/evaluate.py`, `plan/record.py` and `core/edits.py` are outside `test_port_fidelity.PORTS`; their only check is the goldens |
| C14 | REF hygiene | bytecode caches written into REF's git-ignored `__pycache__` by M1 are still there; delete REF's `__pycache__` folders by hand |
| C15 | docs | `jo_decompose` returns radians where ARCHITECTURE says `angle_deg`; fix the text or add a degree wrapper |
| C16 | store safety | `server/remembered.py settings_path()` (REF verbatim) still names the live `%USERPROFILE%\CADExporter`; unused by the server, which refuses that path. Make it raise or return the Studio path |
| F19 | inspector | row labels clip ("Letter height (0 = auto"); the summary uses raw form labels |
| F20 | target editor | server refusals show with the HTTP code ("422: w_mm: ...") |
| F21 | files | Save as `../x` is saved as `_x` without saying so |
| F22 | inspector | the three-line Origin help text sits under the Origin row on every tag |
| F23 | 2D canvas | tag name labels overlap at low zoom; a refused-label preview can sit on the name or outside the part |
| F24 | toolbar | the Single / Grid / ChArUco buttons keep a focus ring after a click (`:focus-visible`) |
| F25 | selection | a hidden tag stays selected and editable while Ctrl+A skips hidden tags |
| F26 | repo | `.audit/` was not git-ignored. Fixed in this run: it is in `.gitignore` now |

### REF behaviour kept as REF has it, for Zach to decide

| # | What | Where |
|---|---|---|
| 1 | a typed board size that is clamped while cols x rows are forced is stored clamped, and its next compute uses the forced count (a 2 x 5 ChArUco comes back 2 x 2) | golden case c0370; docs/status/M2.md |
| 2 | a plain ArucoDetector reads DICT_4X4_50 id 17 in a ChArUco label's text inside the black square; CharucoDetector ignores it | golden case c0776; docs/status/M2.md |
| 3 | on a FACE target a typed cols x rows is ignored (REF's fit takes no force); only a sketch profile honours it | docs/status/M3.md; the inspector says so |
| 4 | a junk trim's warning prints its dict in insertion order, while a Fusion node stores sorted keys, so the same tag can read differently in the Studio and in Fusion | docs/FUSION_ADAPTER.md R5 |
| 5 | REF's Default preset has triangle pins, so a fresh Black-only tag shows "pins only on a tag printed on its own" | docs/status/M3.md |

### Spec entries still planned or partial

| Id | Status | Why |
|---|---|---|
| ST-EXP-3MF, ST-T-EXP-2 | planned | the scene -> beds -> 3MF step is not built (`core.beds` is ported; the file writers are in `server/beds_io.py`) |
| ST-EXP-STL | partial | one file per printed part, oriented face down, is not built |
| ST-UI-EXPORT | partial | no 3MF in the Export menu |
| ST-UI-SCENE-FILE | partial | no separate recent-scenes list |
| ST-SNAPSHOT | partial | staleness / drift read Fusion bodies: the adapter's, measured at the Fusion gates |
| ST-FUSION-BUILD / RECORD / JO / RESTRUCTURE / MIGRATION | partial | the skeleton runs on the stand-in `adsk` only; gates F1-F8 need Fusion |
| ST-T-UI-12 | planned | click-again-to-zoom in the IDs table (M5); double-click zooms today |
| ST-HOLES, ST-HAMMING, ST-FORGET-RETIRED, ST-SHEET-OPTIONS | planned | new behaviour, not a port; no tests yet |

The Fusion adapter also lists 10 core requests (R1-R10) in `docs/FUSION_ADAPTER.md` section 5; R1 (`keep_x`) is done.

## 4. Deferred (PLAN.md section 5)

| Item | Why not now |
|---|---|
| Switching Zach's live Fusion add-in to the new core (ST-LIVE-SWITCH, ST-T-LIVE-1) | needs Fusion open, REF re-pinned (C3), gates F1-F8 in `docs/FUSION_ADAPTER.md`, and Zach's OK |
| build123d adapter | the plan contract settles first; build123d is in no venv here |
| viser adapter | same; viser lives on the Linux box |
| arucostudio.com, any website, any GitHub repository or remote | local only this run; Zach decides |
| `fiducials.py`'s decal path | superseded by true geometry |
| `test_aruco_label_print` (PrusaSlicer oracle) and `test_aruco_frame`'s URDF half | need the clank / smart_sign venvs and PrusaSlicer |
| forget retired ids, ChArUco screw-hole check, Hamming distance, the sheet's `id_text` / `orient_corner` / `emboss_id` | new behaviour, listed as planned features |

Zach's later feedback (M6: stickers, profiles, print; the mini-CAD direction MC-1..MC-12) is planned in `docs/design/` and `docs/feedback/`, not built.

## 5. How to run

| Do | Command |
|---|---|
| First time | `C:\Users\BAM\miniconda3\python.exe -m venv .venv`, `.venv/Scripts/python -m pip install -r requirements.txt`, `npm --prefix studio ci`, `npm --prefix e2e ci` |
| Run the Studio | `npm --prefix studio run studio`, open http://127.0.0.1:5360 (Ctrl+C stops it) |
| Develop with hot reload | `.venv/Scripts/python -m aruco_studio.server` and `npm --prefix studio run dev`, open http://127.0.0.1:5361 |
| Every check, one command | `.venv/Scripts/python tools/check.py` (about 6 minutes; starts and stops its own servers on 5360 / 5361) |
| One group | `.venv/Scripts/python tools/check.py core` (groups: adapters, core, plan, scene, server, verify, studio, e2e) |
| The REF trace | `.venv/Scripts/python tools/check.py --trace` |
| The spec pages | `.venv/Scripts/python tools/spec_status.py` (reports/spec.html), `.venv/Scripts/python tools/status_page.py` (reports/status.html) |

The server's files go under `ROOT/.studio_data/` and saved scenes under `ROOT/scenes/`; it refuses any path under `%USERPROFILE%\CADExporter`. How to use the app: `docs/STUDIO.md`. The routes: `docs/API.md`.

## 6. Deviations from the plan

| What | How it went |
|---|---|
| Models | Fable 5.1 wrote the inventory, brief, ARCHITECTURE, PLAN, spec, the plan review, the design notes, and ran this verification. Opus 5.5 built M1, M2 (+ M2b), M3, M4 and the audit fixes, and recorded Zach's feedback (37 of the 47 commits; see each commit's `Co-Authored-By` line) |
| M2 and M2b | built in one run, not two |
| M3 and M4 | ran in parallel on `main` with disjoint paths, not in branches and worktrees (D13's branch clause had nothing to merge) |
| The Library | brought forward from M5 into M3 |
| `docs/MIGRATION.md` | written as `docs/FUSION_ADAPTER.md`; PLAN D10 now names it |
| The stand-in `adsk` | `tests/adapters/fake_adsk.py`, not `adapters/fusion/fake_adsk.py` |
| The store | `ROOT/.studio_data/` and `ROOT/scenes/`, not `ROOT/.data/` |
| `docs/status/M4.md` | written during the audit fixes, not by the M4 builder |
| PLAN section 8 | M3's builder notes are in `docs/status/M3.md`, because M4 was editing PLAN beside it |
| Contract differences from ARCHITECTURE 5.1-5.3 | listed in PLAN section 8: extra Target fields, layers as REF's CSG steps plus `combines`, extra frames, warn where REF tolerates, `settings.force`, a `writes` field; `jo_decompose` in radians (C15) |
| M1 bytecode slip | 12 `.pyc` were written into REF's git-ignored caches by `python -I`; the tools now run `-I -B` and fail a run that leaves bytecode (C14) |
| Pins | fastapi 0.115.12 with pydantic 2.11.7 and anyio 4.9.0 (newer ones warn); pypdfium2 4.30.0 for the PDF test |

## 7. Sizes

| Part | Lines |
|---|---|
| `aruco_studio/core` (stdlib only) | 16,266 |
| `aruco_studio/plan` | 3,342 |
| `aruco_studio/scene` | 667 |
| `aruco_studio/verify` | 654 |
| `aruco_studio/server` | 2,421 |
| `aruco_studio/adapters` | 2,412 |
| `studio/src` | 6,620 |
| `tests` + `e2e/tests` | 18,834 + 1,107 |

Against the brief's starting point (47,000 add-in lines, 40 of 45 files on `adsk`): everything above but `adapters/fusion` runs without Fusion.
