# ArUco Studio

Zach's fiducial-marker project: one pure core plans every tag, and thin shells (a 2D / 3D web app, Fusion, build123d, exports) draw what the plan says.

Public at https://github.com/zacharyyamaoka/aruco-studio (no licence chosen yet). Read `docs/BRIEF.md`, then `docs/ARCHITECTURE.md` and `docs/PLAN.md`. Since 2026-10-17 the focus is 2D: inkjet stickers on vinyl (`docs/feedback/2026-10-17-markers-core-first.md`, CF-13); the Studio opens on a gallery of golden examples, and the Fusion add-in runs on this core (vendored).

**The online Studio (since 2026-10-18): https://arucostudio.com.** A static site in `web/`; the same Python core runs in the browser (Pyodide), so there is no server. The marker rectangle is the entry point: draw one, or pick a face and the core inscribes one. Spec: `docs/design/online_studio_v1.md`; the UI <-> core contract: `web/src/core/contract.ts`; the facade: `aruco_studio/web_api.py`.

| Do (online Studio) | Command |
|---|---|
| Dev (hot reload) | `npm --prefix web run dev`, open http://127.0.0.1:5380 (first time: `npm --prefix web ci`) |
| Tests | `npm --prefix web test` (vitest); `npm --prefix web run test:parity` (Pyodide = CPython, byte for byte); `npm --prefix web run e2e` (Playwright on the static build); `.venv/bin/python -m pytest tests/web` |
| Check the live site | `E2E_BASE_URL=https://arucostudio.com npm --prefix web run e2e -- --project=e2e` |
| Reading ranges from a script (Verify's range strip) | `.venv/bin/python -m aruco_studio.web_verify requests.json --camera d435 --need 300:2000` (requests: PlanRequests or `{name, req, need}`); add `--also .venv-cv411/bin/python` for the browser's OpenCV too (both where they differ, the worse governs: `tools/requirements-browser-opencv.txt`); `npm --prefix web run bench:verify-range` times it (vt-kpi, `~/.local/share/aruco_studio_bench/verify_range`) |
| Deploy | `npm --prefix web run deploy` (build + `wrangler deploy`; wrangler is logged in per machine) |
| Run it locally, Stable + Preview | `sps open` (Stable, http://127.0.0.1:5382), `sps open --preview` (live `main`, http://127.0.0.1:5383), `sps promote` (Make Stable), `sps rollback`, `sps stop --all`; from a worktree `sps dev` (a lane on 5400-5499). Needs the main checkout on `main`. WHY and how: `docs/STABLE_PREVIEW.md` |

**The local Studio (`studio/`, kept as it is):** `npm --prefix studio run studio`, then open http://127.0.0.1:5360 (it builds the web app and serves it with the API; Ctrl+C stops it). How to use it: `docs/STUDIO.md`.

| Do | Command |
|---|---|
| Run the Studio | `npm --prefix studio run studio` (first time: `npm --prefix studio ci`) |
| Studio dev (hot reload) | the API (below) + `npm --prefix studio run dev`, open http://127.0.0.1:5361 |
| Studio tests | `npm --prefix studio test` (vitest); `npm --prefix e2e test` (Playwright, first time `npm --prefix e2e ci`) |
| Make the venv | `C:\Users\BAM\miniconda3\python.exe -m venv .venv` then `.venv/Scripts/python -m pip install -r requirements.txt` |
| Run every test | `.venv/Scripts/python -m pytest -q` |
| Run by group | `.venv/Scripts/python tools/check.py` (or `tools/check.py core`) |
| Rebuild the REF trace | `.venv/Scripts/python tools/check.py --trace` |
| Status pages | `.venv/Scripts/python tools/status_page.py` (reports/status.html, with the hand-over screenshots); `tools/spec_status.py` (reports/spec.html); the record: `docs/STATUS.md` |
| Run the API | `.venv/Scripts/python -m aruco_studio.server` (127.0.0.1:5360; Ctrl+C stops it; docs/API.md); `--open <file>` follows a design file |
| Check a design file | `.venv/Scripts/python -m aruco_studio check examples/*.json` (also `render <file> --svg out.svg`, `plan <file> --json`); the format: `docs/FILE_FORMAT.md` |

| Folder | Holds |
|---|---|
| `aruco_studio/core/` | the pure core (stdlib only), ported from cad-exporter at `c8216ff` |
| `aruco_studio/plan/` | `plan_tag(TagSpec) -> TagPlan` (REF's evaluate() as a pure function), the exact solids, SVG / STL / JSON exports (stdlib only) |
| `aruco_studio/scene/` | many tags on one canvas, renumbering, the `.arucostudio.json` design file (`arucostudio.scene/2`: sketches, Extrude, ArUco Extrude) and its compile, the 1:1 sheet (stdlib only) |
| `examples/` | three design files to start from: a plate with a ChArUco, the forearm (four sides), a sticker sheet |
| `aruco_studio/verify/` | OpenCV reads a plan: render, detect, PnP (numpy + cv2) |
| `aruco_studio/server/` | FastAPI on 127.0.0.1:5360; the only module that touches files |
| `studio/` | the web app: 2D / 3D views, inspector, Library, IDs (Vite + React + TypeScript) |
| `e2e/` | Playwright end-to-end tests of the Studio; screenshots go to `reports/screens/` |
| `goldens/` | JSON made by REF's own code, read only; never made by the new code |
| `tests/` | pytest; `tests/core/` holds the ported REF suites and the golden replays |
| `tools/` | the golden makers, `check.py`, `ref_sections.py`, `spec_status.py` |
