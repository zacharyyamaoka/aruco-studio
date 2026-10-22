# 0003 — Verify answers "from how far does each marker read?", per camera

Date: 2026-10-21 · Status: accepted · Merged: lane/os-verifyrange (decisions 1–2); decision 3 from lane/os-onecv

## Context
Zach (2026-10-21): Verify should "feel like a unit test"; "maybe I can just select the camera and
then Verify can tell me what is a suitable range… a view where I can quickly see all the markers
along the top and underneath a line that represents the distance they can be viewed". Proposal V4
of reports/media/verify-unit-test-proposals-2026-10-21.html.

## Decisions
1. **Range first, requirement optional.** Pick a camera from a cited library
   (`aruco_studio/core/cameras.py`); the core (`core/reading_range.py`, `reading-range/1`) sweeps
   distance under glare, blur, noise and tilt and returns each marker's near–far. A required
   distance is stored on the feature (`Feature.verify`), never in the plan request, so planning and
   its pins are untouched; with one set, the band reads PASS/FAIL with the fix.
2. **One worker, sliced.** Ranges run in the core's single Pyodide worker in ~250 ms slices,
   so planning stays responsive (measured: no main-thread long tasks). More workers would cut
   ~90 s per 4-board document at ~300 MB each — not taken yet. A finished range is cached by
   what the camera sees, not by the request (2026-10-21, from the canvas proposals' 8 measured
   edits): `web_api.scene_key` digests the marker's plan and label in its own frame, so moving or
   turning a marker on the page keeps its range, while its size, ids, label, corner mark,
   dictionary or preset measure it again; plus the camera, the core's version and the OpenCV.
3. **OpenCV policy: one detector a run, the newest by default, selectable** (accepted 2026-10-21).
   Zach: "Let's only run one, but you can choose, and by default it should be the most recent
   one." OpenCVs draw the same view differently (warpPerspective, warpAffine, GaussianBlur) and
   disagree near the limits — by up to 2× in a range, and on 6 of the 28 markers of the label
   placement board (B5, B7, B8, C4, D4, E4: the run with 4.11 and 5.0, both kept, the worse
   governing, commit 078f361). That finding is why every result names the OpenCV that made it;
   it is no longer why a run uses two.
   - **Scripts** (`python -m aruco_studio.web_verify`, `range_table(opencv=)`,
     `docs/build_guides.py`): one `--opencv VERSION|PYTHON`, default the newest installed.
     `aruco_studio/opencv_choice.py` finds them — this checkout's and the main checkout's
     `.venv*` (the repo's `.venv`: 5.0; `.venv-cv411`: the stock 4.11) — and runs the choice in
     its own Python when it is not this one. The "run both, the worse governs" path (`--also`,
     a second `--detector`) is gone.
   - **The browser**: Verify › OpenCV lists only the builds this browser can load
     (`web/src/core/opencv.ts`), newest first and chosen by default, remembered per viewer. No
     Pyodide ships OpenCV 5 (314.0.7, the newest stable, ships 4.11.0.86; the 315 alphas none;
     PyPI has no wasm wheel; pyodide-recipes pins 4.11), so `tools/opencv-wasm/build.sh` builds
     opencv-python 5.0.0.93 for Pyodide 314 (the modules the core calls) and the site serves it
     (`web/public/opencv/`). Measured: 4.5 MB against 4.11's 10.7 MB, cv2 loaded in ~0.14 s
     against ~0.44 s (Node), and its reading ranges and rendered views byte-identical to
     CPython's 5.0. So the browser's default is 5.0, the scripts' too; 4.11 stays one click
     away. A worker loads one OpenCV; choosing another restarts it and resends what it had not
     answered (`web/src/core/client.ts`).
   - **Caches key on the OpenCV**: the strip's ranges (`range.ts rangeKey`, with the scene key of 2), the bench's sweeps,
     the calculator's job; the guide's `verify.json` records its OpenCV and `--pages` refuses a
     run made on another than the one asked for.
   - **Tests whose answer is one OpenCV's** run on the default detector and say so
     (`opencv_choice.call`): `test_label_and_corner_mark_do_not_read_as_markers`,
     `test_a_label_run_into_the_corner_cells_moves_the_pose` (both fail on 4.11).
   Neither OpenCV is ground truth: a physical D435 check would settle which reads like a camera.

## Consequences
- `web_verify.reading_range()` / `range_table()` are the scriptable entry points (the Label
  placement guide can switch to them).
- The label placement guide is one OpenCV's (5.0): B7 (a longer text that still fits the border
  row) is now Safe — only 4.11 lost reads there — and the page says other versions can differ,
  linking the run with both.
- The browser's 5.0 is a build this repo owns: a Pyodide upgrade changes the ABI, and
  `web/src/core/opencv.test.ts` fails until `tools/opencv-wasm/build.sh` is rerun for it.
