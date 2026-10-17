"""How long one live edit takes on the server (audit B1, lane speed).

    .venv/Scripts/python tools/bench_preview.py              # the medians
    .venv/Scripts/python tools/bench_preview.py --profile    # and cProfile's top lines
    .venv/Scripts/python tools/bench_preview.py --code ..\\aruco-studio   # another tree's code

It drives the server in a TestClient (a temp home and scenes folder, the
fixture PrusaSlicer folder) and posts the text of a drag to
`/api/design/preview`: the forearm example's box 150, 151, ... mm long, a
new length each time, so every edit re-plans its four tags as a real drag
does (the long faces change size, the short ones their body's depth).

| Row | How | Query |
|---|---|---|
| bare 2d / bare 3d | the audit's way: the example's own text, nothing open | `top=1` / `top=1&mesh=1` |
| open 2d / open 3d | as the Studio does: the example opened (File > Open > Examples), the drag's text from the open file (its frozen presets in it) | `top=1` / `top=1&mesh=1` |

What the Studio asks (after lane speed): a drag step in 2D or 3D is `top=1`
(the light preview); the release in 3D is `top=1&mesh=1` once. Each row is
the median of n edits, after one warm-up edit.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODES = {"2d": "top=1", "3d": "top=1&mesh=1"}


def setup_env():
    home = tempfile.mkdtemp(prefix="aruco_bench_")
    os.environ["ARUCO_STUDIO_HOME"] = os.path.join(home, "studio")
    os.environ["ARUCO_STUDIO_SCENES"] = os.path.join(home, "scenes")
    os.environ["BAM_ARUCO_PRUSASLICER_DIR"] = str(ROOT / "goldens" / "prusaslicer")
    os.environ["USERPROFILE"] = os.environ["HOME"] = home


def with_length(text: str, length: float) -> str:
    doc = json.loads(text)
    doc["sketches"][0]["shapes"][0]["rect"] = [length, 40]
    return json.dumps(doc, indent=1) + "\n"


def forearm_text(length: float) -> str:
    return with_length((ROOT / "examples" / "forearm.arucostudio.json").read_text(encoding="utf-8"),
                       length)


def edit(c, text: str, query: str) -> float:
    t0 = time.perf_counter()
    r = c.post(f"/api/design/preview?{query}", json={"text": text})
    ms = (time.perf_counter() - t0) * 1000.0
    r.raise_for_status()
    body = r.json()
    assert body["scene"] is not None and len(body["scene"]["tags"]) == 4, body.get("error")
    return ms


def stats(ms) -> dict:
    return {"median": round(statistics.median(ms), 1), "min": round(min(ms), 1),
            "max": round(max(ms), 1), "n": len(ms)}


def bench(n: int = 8, profile: bool = False) -> dict:
    """{row: {median, min, max, n}} in ms (the rows of the table above)."""
    from fastapi.testclient import TestClient
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    from aruco_studio.scene import Scene
    A.STATE["scene"] = Scene(name="untitled")
    c = TestClient(A.app)
    res = {}
    length = 150.0
    try:
        edit(c, forearm_text(120), MODES["3d"])            # imports, the catalog, a warm-up
        for mode, q in MODES.items():
            ms = []
            for _ in range(n):
                ms.append(edit(c, forearm_text(length), q))
                length += 1
            res[f"bare {mode}"] = stats(ms)
        r = c.post("/api/design/open_example", json={"name": "forearm"})
        r.raise_for_status()
        text = c.get("/api/design").json()["text"]
        edit(c, with_length(text, 121), MODES["3d"])
        for mode, q in MODES.items():
            ms = []
            for _ in range(n):
                ms.append(edit(c, with_length(text, length), q))
                length += 1
            res[f"open {mode}"] = stats(ms)
        if profile:
            import cProfile
            import pstats
            pr = cProfile.Profile()
            pr.enable()
            edit(c, with_length(text, length + 0.5), MODES["3d"])
            pr.disable()
            pstats.Stats(pr).sort_stats("cumulative").print_stats(40)
    finally:
        DA.D.unbind()
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-n", type=int, default=8, help="edits per row (default 8)")
    ap.add_argument("--profile", action="store_true", help="cProfile one 3D edit (the route "
                    "runs in a worker thread: profile design_api.design_preview directly for its insides)")
    ap.add_argument("--json", action="store_true", help="the numbers as JSON")
    ap.add_argument("--code", help="import aruco_studio from this tree (the 'before' numbers)")
    a = ap.parse_args(argv)
    code = Path(a.code).resolve() if a.code else ROOT
    sys.path.insert(0, str(code))
    setup_env()
    res = bench(a.n, a.profile)
    import aruco_studio
    if a.json:
        print(json.dumps({"code": str(Path(aruco_studio.__file__).parent.parent), "rows": res},
                         indent=1))
    else:
        print(f"code: {Path(aruco_studio.__file__).parent.parent}")
        for row, r in res.items():
            print(f"{row:8s} median {r['median']:7.1f} ms   min {r['min']:7.1f}   "
                  f"max {r['max']:7.1f}   (n {r['n']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
