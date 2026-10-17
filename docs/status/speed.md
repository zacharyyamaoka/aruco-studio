# Lane speed: live re-placement (audit B1)

Built on branch `lane/speed` (worktree `C:\Users\BAM\Documents\aruco-studio-wt\speed`), on top of `46f2bac`. Not merged. The task: make a drag on the forearm feel instant (target under 100 ms per edit) with plans that stay bit-identical.

## What a drag costs now

| Step | Before | After |
|---|---|---|
| A drag step in 2D (`?top=1`) | 245-265 ms | about 75 ms |
| A drag step in 3D | 715-920 ms (the meshes on every step) | about 75 ms (the light preview, no meshes) |
| The release in 3D (`?top=1&mesh=1`, once) | 715-920 ms | about 210-280 ms |

"About" because the box was busy. The quiet runs are in the first table below; the busy ones in the second.

## Numbers

`tools/bench_preview.py` posts the forearm's text to `/api/design/preview` in a TestClient. The box is 150, 151, ... mm long, a new length each edit, so all four tags re-plan (the long faces change size, the short faces their body depth). "bare" is the audit's way (the example's own text). "open" is the Studio's way (the example opened, its frozen presets in the text). Median of 8 edits, ms.

Quiet runs, taken while the box was idle:

| Row | Before (`46f2bac`) | After | How measured |
|---|---|---|---|
| bare 2d | 245 | 72 | TestClient |
| bare 3d | 826 | 208 | TestClient |
| open 2d | 264 | 93 | TestClient |
| open 3d | 922 | 210 | TestClient |
| open 2d over real HTTP (uvicorn) | (not measured quiet) | 73 | httpx to 127.0.0.1:5360 |
| open 3d over real HTTP (uvicorn) | (not measured quiet) | 270 | httpx |

Interleaved before / after runs (main, lane, main, lane, main, lane), with another lane's full check on all twelve cores (CPU at 65-75 %). This is the median of the three medians:

| Row | Before | After | Ratio |
|---|---|---|---|
| bare 2d | 261 | 142 | 1.8x |
| bare 3d | 800 | 414 | 1.9x |
| open 2d | 359 | 155 | 2.3x |
| open 3d | 1,222 | 528 | 2.3x |

In the browser (e2e `speed.spec.ts`, through Vite's proxy, the box busy): a 2D drag step's round trip was 124 ms median, a 3D drag step's 127 ms, and the 3D release took 617-820 ms to show the meshes. In the served Studio there is no proxy hop.

So the drag step is under 100 ms on a quiet box and over it on a busy one. The 3D drag step gained the most: it no longer waits for meshes.

## Where the time went (profile of one 3D edit, before)

| Part | Share |
|---|---|
| `mesh()`: the region sweeps, `prism()`, `_split_pinches()` | about 60 % |
| `top()`: three full sweeps, one per colour | about 30 % |
| `plan_tag()` | about 5 % |
| FastAPI's `jsonable_encoder` over 540 KB of numbers | 120-140 ms |
| Full GC collections (gen 2) in the middle of an edit | 100-170 ms each, about one edit in three |

## What changed

| Change | Where | Same results because |
|---|---|---|
| `booleans(groups, exprs)`: one sweep for several expressions. `top()` runs its three colours over one sweep. `bodies()` runs body, white and pattern over one sweep per slab | `plan/region.py`, `plan/mesh.py` | The slabs, the edge order and the crossings do not depend on the expression. Each expression still makes its own trapezoids and its own snap |
| Each expression is memoised by its flags. `materials()` and `_Model.top()` run once per set of flags | `plan/region.py`, `plan/mesh.py` | They are pure functions of the flags |
| Each edge's heights are computed once per slab. The inside flags are kept as the counts change | `region._slab` | The same `Edge.y` calls, so the same floats. The same stable sort |
| `_simplify` resumes after a drop instead of starting again at 0. It was quadratic on long straight runs | `region._simplify` | After a drop at i, only i - 1 and i have new neighbours (and 0 when the last point went). So it drops the same points in the same order |
| Slab-line lookups take a slice of the sorted ys (bisect) instead of filtering | `region.boundary`, `region.faces` | The ys are sorted, so the slice is the same list |
| `_split_pinches` first walks round a vertex's triangles. If they form one cycle through edges of exactly two triangles, the union-find is skipped there | `mesh._split_pinches`, `mesh._one_cycle` | Then the union-find finds one fan and does nothing. Any doubt (a renamed vertex, a shared edge, a broken walk) goes to the old union-find |
| `mesh()` and `stl()` skip the body polygons they never used | `mesh.bodies(polygons=False)` | They use only the trapezoids |
| `mesh()` and `top()` in the cache read the kept plan dict, not a second deep copy | `server/app.cached_plan_dict` | `to_dict()` is a deep copy of the same data. Neither function changes it |
| The preview answers through `plain_json` (no `jsonable_encoder` walk) | `server/design_api.plain_json` | The data is plain JSON already, so the bytes are the same. A `TypeError` falls back to the encoder |
| The cache keeps mesh numbers as tuples | `server/app._kept_mesh` | JSON writes a tuple as a list |
| `no_gc()` holds Python's cyclic GC while a preview or `/api/scene` plans and writes. It gives it back when the last request in flight ends, or on an error | `server/app.no_gc` | The short-lived lists hold no cycles. Reference counting frees them as before |
| The light drag preview: a drag asks `?top=1` only. In 3D each tag stands as a slab of its top view until the release. The release asks once with `mesh=1` | `studio/src/store.ts` (`fetchPreview(text, mesh)`), `studio/src/view3d/View3D.tsx` (`lightSlab`, probe `drawn`) | The server's answer to `?top=1` did not change. The 2D view asked exactly this before |

Not done: a process pool that plans independent tags side by side. A quick try gave about 2.5x on an idle box (top views 94 -> 38 ms, meshes 308 -> 139 ms). It was not needed for the target on a quiet box. It would add worker processes that must die with the server (`check.py` stops uvicorn with a hard kill on Windows). It is the next step if a bigger scene needs it.

## Bit-identical: how it is checked

| Check | What |
|---|---|
| `tests/fixtures/mesh_digests.json` (new) | Written by `tools/mesh_digests.py --write` BEFORE any change (`made_at: 46f2bac`). For 947 plans (every legacy and matrix golden that plans, the three examples, the forearm at 153 mm, 120 fuzz specs) it holds the sha256 of the plan, the bodies (polygons and trapezoids), the top view, the mesh, the removed volume and the STL |
| `tests/plan/test_mesh_digests.py` (12) | Recomputes all 947 and compares. Runs the old `_simplify` and the old `_split_pinches` beside the new ones (3,000 random loops; checkerboards whose corners pinch, 48 -> 60 vertices). Checks `booleans()` against `boolean()` per expression |
| `tests/server/test_preview_speed.py` (6) | The benchmark under a generous bound (drag step < 400 ms, 3D release < 1,500 ms). The light preview equals the release minus its meshes. `plain_json`'s bytes equal the encoder's. The kept mesh is written as `mesh()` gives it. The GC hold is nested, safe on errors, and leaves a disabled GC disabled |
| The preview's bytes | The SHA-256 of 13 preview answers (three examples, 2D / 3D / no top, the forearm at 150 and 157 mm) were recorded before the change and compared after: identical |
| goldens | Not edited. The whole check passes |

## e2e

`e2e/tests/speed.spec.ts` (2 tests, new):

* A 2D handle drag on the forearm: every preview is `top=1`, the median round trip is under 400 ms (recorded in `e2e/.tmp/speed_numbers.json`), the file's width grows.
* A 3D arrow drag: while the pointer is down the four tags are drawn as light slabs (`__studio3d.drawn` all `"light"`) and no request asks for meshes. The release sends one `mesh=1` request and the four meshes come back. Screenshots: `reports/screens/speed_3d_light_drag.png`, `speed_3d_after_release.png`, `speed_2d_after_drag.png`.

## The check run

`.venv/Scripts/python tools/check.py` in the worktree, 2026-10-17 (the `.venv` is a junction to ROOT's). Another lane's check ran at the same time.

| Group | Result |
|---|---|
| adapters | 97 passed in 55 s |
| core | 7,354 passed, 4 skipped in 61 s |
| plan | 541 passed in 155 s (529 + the 12 new) |
| scene | 42 passed in 22 s |
| server | 97 passed in 34 s (91 + the 6 new) |
| verify | 117 passed, 1 skipped in 101 s |
| studio | build + vitest passed in 46 s |
| e2e | 49 passed in 335 s (47 + the 2 new) |
| **all** | **OK in 811 s** |

Ports 5360 / 5361 were free before and after. 5370 / 5371 (Zach's preview) were not touched.

## How to measure again

| Do | Command |
|---|---|
| The medians | `.venv/Scripts/python tools/bench_preview.py` |
| The same for another tree (the "before") | `.venv/Scripts/python tools/bench_preview.py --code C:\Users\BAM\Documents\aruco-studio` |
| One profiled edit | `.venv/Scripts/python tools/bench_preview.py --profile` |
| The digests | `.venv/Scripts/python tools/mesh_digests.py --check` |

## Where the build differs from the task

| Note | Built | Why |
|---|---|---|
| "under 100 ms" | about 75 ms per drag step on a quiet box. 120-155 ms while another check uses every core | Pure-Python planning. The process pool is the next step (above) |
| "meshes on release" | the 3D release is one request of about 210-280 ms (quiet) | The meshes are still built in one process |
| `docs/STUDIO.md` | the "Live re-placement" row now names the light preview | The behaviour it described changed |
| STATUS.md's "Known and not fixed" row (B1) | left as it is | The orchestrator updates STATUS.md at merge |
