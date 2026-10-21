# 0003 — Verify answers "from how far does each marker read?", per camera

Date: 2026-10-21 · Status: accepted (OpenCV policy: provisional) · Merged: lane/os-verifyrange

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
   cached per plan hash, so planning stays responsive (measured: no main-thread long tasks). More
   workers would cut ~90 s per 4-board document at ~300 MB each — not taken yet.
3. **OpenCV policy (provisional).** The browser runs OpenCV 4.11 (Pyodide); repo CPython has 5.0.
   They draw (warp/blur) differently and disagree by up to 2× near the limits. Until Zach picks a
   reference: every result names its OpenCV, script tables run both (`--also .venv-cv411`) and the
   worse decides. Neither is ground truth; a physical D435 check would settle it.

## Consequences
- `web_verify.reading_range()` / `range_table()` are the scriptable entry points (the Label
  placement guide can switch to them).
