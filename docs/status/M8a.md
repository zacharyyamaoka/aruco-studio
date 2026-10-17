# M8a: the file format, the compile, the watcher, events, the CLI

Built on branch `lane/M8a` (worktree `aruco-studio-wt/M8a`), from `main` at `8cbc8be`, beside M6a. The design is `docs/design/M8_mini_cad_file_first.md` section 1 and `ROADMAP.md` section 3; the reference for the format is the new `docs/FILE_FORMAT.md`.

## What was built

| Piece | Where |
|---|---|
| Shapes to loops (rect, circle, polygon, slot, loops, holes) at the 0.05 mm chord tolerance; the faces of an extrude (top, bottom, side<i>, front / right / back / left) as Targets with right-handed frames | `aruco_studio/plan/shapes.py` |
| The new-tag rule, pure, so the compile can call it (`server/newtag.py` now imports it) | `aruco_studio/plan/newtag.py` |
| The design document: compile to today's Scene with sugar, the edits (add, delete, rename, move), `write_back` (a Scene changed through the Scene API, back into the document; a multi-face list splits when a face differs) | `aruco_studio/scene/design.py` |
| The file: `/2` read and write, the `/1` migration, parse errors with line and column | `aruco_studio/scene/file.py` |
| `SceneTag.pose_3d` (stored when a tag is not z-up at z 0) and `source` (not stored) | `aruco_studio/scene/model.py` |
| The open design in the server, its file, the routes `/api/design*`, `/api/events` | `aruco_studio/server/design_api.py` |
| The watcher (paths, signature, the hash rule, a quiet time for M8c) | `aruco_studio/server/watch.py` |
| The SSE hub | `aruco_studio/server/events.py` |
| Design paths anywhere but CADExporter and PrusaSlicer's folder; `write_atomic` records its hash | `aruco_studio/server/store.py` |
| `/api/scene*` and `/api/target` over the design document | `aruco_studio/server/app.py` (that block only) |
| `--open <file>` | `aruco_studio/server/__main__.py` |
| The CLI: `check`, `render`, `plan` | `aruco_studio/__main__.py` |
| The three example files, verbatim from the note | `examples/` |
| Tests | `tests/plan/test_shapes.py` (14), `tests/scene/test_design.py` (11), `tests/scene/test_file_v2.py` (7), `tests/server/test_design_api.py` (6), `tests/server/test_events.py` (6), `tests/server/test_cli.py` (4); the e2e suite's saved `/1` scenes in `tests/scene/fixtures_v1/` |
| Docs | `docs/FILE_FORMAT.md` (new), `docs/API.md` (the scene section, the design routes, the 409s), `README.md` (two rows) |

## Numbers

| What | Measured |
|---|---|
| An outside write to the open file -> the `scene` event | 228 to 255 ms (the watcher stats every 250 ms); bar 500 ms |
| Compile of a 25-tag design | 8.4 ms (34 ms before the hole check skipped far edges) |
| Compile of the examples (with the preset catalog) | forearm 5.7 ms, plate 5.0 ms, stickers 8.2 ms |
| `PATCH /api/scene/tags/{name}` on a 25-tag design with a file (compile, Scene API, write back, write) | about 95 ms (a move or a settings edit) |
| `PUT /api/design` (the whole text, 25 tags) | 38 ms |
| `POST /api/design/preview` (25 tags, plans cached) | 148 ms |
| pytest groups (`tools/check.py`) | adapters 97 passed; core 7,245 passed, 4 skipped; plan 207 passed (193 on main); scene 25 passed (7); verify 104 passed; server 49 passed + main's uvicorn test (see below) (35 on main) |

## The done checks

| # | Result | How |
|---|---|---|
| M8a.1 | PASS | `test_design_api.py::test_the_plate_equals_the_target_editors` (the plate: POST /api/target box 80 x 50, hole Ø18, 5 mm; POST /api/new ChArUco; the PATCH the sugar stands for: equal spec, equal record digest), `::test_the_forearm_and_the_stickers_equal_the_old_routes`; `test_cli.py::test_check_the_examples_exits_0` (`check examples/*.json` exits 0) |
| M8a.2 | PASS | `test_file_v2.py::test_v1_migrates_and_replans_byte_for_byte`: the three `/1` files the e2e suite saved in its last run on main and a 25-tag scene (every palette face, the old 48-point holes, discs, a sketch profile, a free area, a flipped face with `x_ref`, a measured body, locked, hidden, an override, a renamed tag, the ledger) replan byte for byte (each plan's canonical JSON); names, uids, places, locks, ledger and overrides kept; `loads_design(dumps_design(d)) == d` and `dumps(loads(t)) == t` |
| M8a.3 | PASS | every pytest group green (above); the 824 evaluate goldens are in the plan group; `tests/plan/test_adapter_keys.py` passes |
| M8a.4 | PASS | `test_design.py::test_the_forearm_four_faces` (four Targets 120 x 40 / 40 x 40, bodies 40 / 120 deep, poses right-handed and orthonormal with z the outward normal, OpenCV's frame on each face: its origin on the face, its z along the normal, into the face for a board as OpenCV has it), `::test_one_edit_splits_the_list_and_renumber_does_not` (one mark: four features named `tag.front` .. `tag.left`; Renumber alone keeps one feature with `marker_ids`) |
| M8a.5 | PASS | `test_shapes.py`: a Ø50 circle equals core.faces's stroke at 0.05 mm; a slot closed and counter-clockwise; holes clockwise and inside; a hole outside (or across) is an error on `holes[k]`, in a file on `sketches[i].shapes[j].holes[k]` (`test_design.py`); a tag on a circle's side says "curved" |
| M8a.6 | PASS | `test_events.py`: the push under 500 ms (TestClient stream); a broken write keeps the scene, says line:col, a PATCH answers 409 "file not parseable" and the file is unchanged; own writes and a same-text rewrite give no event; a deleted file stops writes ("file missing"); two writers: 409 and a reload |
| M8a.7 | PASS | `test_design_api.py::test_old_routes_write_the_design` (POST /api/scene/tags makes a sketch, an Extrude, an ArUco Extrude; PATCH settings lands exactly in the feature and the file), `::test_the_old_answers_replayed_on_a_scene_by_hand` (add, duplicate, overrides, renumber rows and ledger, the SVG sheet, the JSON export, verify, Undo by PUT /api/scene, delete, rename: equal to the Scene API on main). Main's own server tests (35) pass unchanged |
| M8a.8 | PASS | `test_design.py::test_sugar_expands_to_what_api_new_stores` (`origin_v`, the label's rule, `cells` from the preset; after one write: exact settings / numbers, no sugar), `::test_sugar_keys_one_by_one` |
| M8a.9 | PASS | `test_cli.py`: `render`'s `data-layer` paths, tag by tag, equal POST /api/export/svg's; `plan --json` equals GET /api/scene?plans=1's plans; a bad feature exits 1 and prints `features[1].aruco[1]`; a broken file prints `file:line:col` |
| M8a.10 | PASS, with one note | the groups green; nothing listens on 5360 / 5361 after; the tests write only under pytest's temp folders and the Studio's temp home. The note: main's `tests/server/test_api.py::test_uvicorn_serves_on_5360_and_stops` binds 5360 for a second and stops. It ran twice in this lane before I saw the wave-1 port rule; every later server run deselected it (`--deselect tests/server/test_api.py::test_uvicorn_serves_on_5360_and_stops`). It passed both times and left nothing on the port |

Not run here, by the rules: the `e2e` group (it binds 5360 / 5361; only the lane that owns `studio/` and `e2e/` runs it). `studio/` is untouched, so the `studio` group is as on main.

## Where the build differs from the note

| Note | Built | Why |
|---|---|---|
| a typed first id is the ArUco Extrude's key `id` | `first_id` | the feature's `id` is its own id |
| a tag on a bare shape is `kind: "free"` | `kind: "face"`, no body | what POST /api/target makes; `free` changes REF's fit; M8a.1's bar is the target editor's tag |
| `settings` / `numbers` laid "over everything above" | when present they are the dict as it stands; the sugar for it is unused (`info`) | a merge would add a later default into an exact record and change its plan (the `/1` scenes need it exact) |
| `SceneTag.pose` stored when not z-up | `pose` stays the canvas place; `pose_3d` holds the full pose | the sheet, the overlap check and the numbering read `pose` as 2D (`scene/sheet.py` is M6a's); a side tag's canvas place is its face unfolded about its top edge (the box net) |
| the `/1` migration writes `over` for a profile over a body | it writes the exact `target` whenever the shape cannot say the Target (profile, free, flipped, measured body); `over` is read by the compile | byte-for-byte replans with no special cases |
| an extrude goes from z 0 up | so it does; the `/1` migration and the old routes write a negative height | their tags keep their face at z 0, as before; a typed file's top sits at its height |
| (not in the note) | the exact keys `target`, `key`, `uid`, `locked`, `hidden`, `marker_ids`, `presets_used`; the event `file {state}`; `POST /api/design/save_as`; `?max_events` / `?timeout` on `/api/events` | what a `/1` tag carries; a list's ids after Renumber; the broken / missing bar; Save as; a TestClient reads a whole response, so a test stream must end |
| GET /api/scene says `/2` | it says `arucostudio.scene/1`: the compiled scene keeps the `/1` shape (tags with specs); the file is `/2` (GET /api/design) | today's Studio reads and PUTs that shape (Undo) |
| `check` exits 1 on an error | compile errors exit 1; a tag that does not plan is a `warn` (`--strict` makes it an error) | the sticker example's t4 (a ChArUco 4 x 4 on a Ø50 disc with a Ø6 hole) does not plan under Default; it needs M6a's "Sticker · Letter · 600 dpi" preset, which is not on this branch (a `warn` says Default was used). With `--strict`, check exits 1 on it |
| `tests/test_cli.py` | `tests/server/test_cli.py` | `tools/check.py` runs folders only; at the top level it would never run |
| the server's own write gives no event | so it is; there is also no event for the Studio's own writes to other tabs | the bar asks for none |

## Changes outside the owner paths

| File | Change | Why |
|---|---|---|
| `tests/scene/test_scene.py` | two lines of `test_file_round_trip_100_random_scenes`: the written schema is now `/2`, and a `/2` file has no `tags` | writers write `/2`; the round trip itself (100 scenes) is unchanged and passes |
| `aruco_studio/server/__main__.py` | `--open <file>`; 5370 added to the refused ports | the roadmap's `--open` lives in the entry point; 5370 is Zach's preview |
| `README.md` | a row for the CLI, the folder `examples/` | |
| `aruco_studio/server/newtag.py` | now a re-export of `plan/newtag.py` (git sees a rename) | the roadmap's "the pure half of server/newtag.py, which then imports it" |

## Include lines for the merge

None needed. Watch two files at merge: `docs/API.md` (M6a edits it too; M8a's edits are the Errors table, "The scene" section, the new "The design file (M8a)" section, the `/api/target` row and the shapes table) and `aruco_studio/server/app.py` (M8a replaced only the block from `# ---- the scene` to before `# ---- the Studio (M3)`, and `target_make`; it also dropped `dumps, loads` from the scene import line).

## Follow-ups

| Item | Note |
|---|---|
| `GET /api/health` still says `"scene": "arucostudio.scene/1"` | outside the scene block; one line once M6a has merged |
| `CHORD_MM` | `plan/shapes.py` reads `core.faces.CHORD_TOL_MM` (0.05 mm) until M6a's `plan.target.CHORD_MM` lands; then one line |
| e2e on `main` that this changes | `export.spec.ts` expects the exported scene file to be `arucostudio.scene/1` with `tags`: it is now `/2` (M8b1 rewrites it). `target.spec.ts`'s holes are now stroked at 0.05 mm instead of 48 points: the counts it checks (loops) stay; not run here |
| The watcher's signature | (mtime, size), as the note says: a rewrite of the same size inside one mtime tick is seen only on the next real change. NTFS stamps are fine-grained; noted for M8c |
| The old Studio's dirty dot | GET /api/scene tags now carry `source`; an Undo after a structure change can mark a scene dirty that is not. M8b1 drops the dirty state |
