# ArUco Studio

Zach's fiducial-marker project: one pure core plans every tag, and thin shells (a 2D / 3D web app, Fusion, build123d, exports) draw what the plan says.

Local only. Read `docs/BRIEF.md`, then `docs/ARCHITECTURE.md` and `docs/PLAN.md`.

| Do | Command |
|---|---|
| Make the venv | `C:\Users\BAM\miniconda3\python.exe -m venv .venv` then `.venv/Scripts/python -m pip install -r requirements.txt` |
| Run every test | `.venv/Scripts/python -m pytest -q` |
| Run by group | `.venv/Scripts/python tools/check.py` (or `tools/check.py core`) |
| Rebuild the REF trace | `.venv/Scripts/python tools/check.py --trace` |

| Folder | Holds |
|---|---|
| `aruco_studio/core/` | the pure core (stdlib only), ported from cad-exporter at `c8216ff` |
| `goldens/` | JSON made by REF's own code, read only; never made by the new code |
| `tests/` | pytest; `tests/core/` holds the ported REF suites and the golden replays |
| `tools/` | the golden makers, `check.py`, `ref_sections.py`, `spec_status.py` |
