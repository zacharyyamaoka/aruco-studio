"""The digests of every solid and top view the server sends (lane speed).

    .venv/Scripts/python tools/mesh_digests.py --write   # tests/fixtures/mesh_digests.json

The lane made plan/region.py and plan/mesh.py faster. Their results must
stay bit-identical, so this file records, for a corpus of plans, the
sha256 of each output as the code gave it BEFORE the change (written once,
at 46f2bac). tests/plan/test_mesh_digests.py recomputes them and compares.

The corpus: every legacy and matrix golden case that plans, the three
examples' tags (the forearm at 120 and 153 mm), and 120 random specs of
the fuzz test's generator (seed 1017).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "tests" / "plan"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

OUT = ROOT / "tests" / "fixtures" / "mesh_digests.json"
FUZZ_SEED, FUZZ_N = 1017, 120


def _sha(obj) -> str:
    if isinstance(obj, bytes):
        data = obj
    else:
        data = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _traps(ts):
    return [[t.x0, t.x1, t.yb0, t.yb1, t.yt0, t.yt1] for t in ts]


def digests(spec_dict) -> dict:
    """{what: sha256} of one spec's plan, top view, solids, removed volume, STL."""
    from aruco_studio.plan import mesh as ME
    from aruco_studio.plan import plan_tag
    p = plan_tag(spec_dict)
    out = {"plan": _sha(p.to_dict())}
    if not p.ok:
        return out
    bodies = ME.bodies(p)
    out["bodies"] = _sha([{"what": b["what"], "colour": b["colour"], "z": b["z"],
                           "polygons": b["polygons"], "traps": _traps(b["_traps"])}
                          for b in bodies])
    out["top"] = _sha(ME.top(p))
    out["mesh"] = _sha(ME.mesh(p))
    out["removed"] = _sha(ME.removed_mesh(p))
    out["stl"] = _sha(ME.stl(p))
    return out


def _example_specs():
    import os
    import tempfile
    from aruco_studio.scene import design as DS
    from aruco_studio.server import design_api as DA
    # the presets from a temp home and the golden PrusaSlicer folder; the
    # environment is put back after (a test worker shares it)
    keep = {k: os.environ.get(k) for k in ("ARUCO_STUDIO_HOME", "BAM_ARUCO_PRUSASLICER_DIR")}
    os.environ["ARUCO_STUDIO_HOME"] = os.path.join(tempfile.mkdtemp(prefix="aruco_digests_"), "studio")
    os.environ["BAM_ARUCO_PRUSASLICER_DIR"] = str(ROOT / "goldens" / "prusaslicer")
    out = []
    try:
        for name in ("forearm", "plate_charuco", "sticker_sheet"):
            text = (ROOT / "examples" / f"{name}.arucostudio.json").read_text(encoding="utf-8")
            lengths = (120, 153) if name == "forearm" else (None,)
            for L in lengths:
                doc = json.loads(text)
                if L is not None:
                    doc["sketches"][0]["shapes"][0]["rect"] = [L, 40]
                sc, _issues = DS.compile(DA.loads_design(json.dumps(doc)), DA.resolver())
                for t in sc.tags:
                    out.append((f"example:{name}:{L}:{t.name}", t.spec.to_dict()))
    finally:
        for k, v in keep.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return out


def corpus():
    """[(id, spec dict)]: the goldens, the examples, the fuzz sample."""
    import random
    import _evaluate_golden as G
    import test_fuzz as F
    out = []
    for c in G.cases("legacy") + G.cases("matrix"):
        if "error" in c["out"]:
            continue
        out.append((f"golden:{c['id']}", c["in"]))
    out += _example_specs()
    r = random.Random(FUZZ_SEED)
    for i in range(FUZZ_N):
        out.append((f"fuzz:{i}", F._rnd_spec(r)))
    return out


def _one(item):
    cid, spec = item
    try:
        return cid, digests(spec)
    except Exception as exc:                   # noqa: BLE001 -- recorded as it is
        return cid, {"raises": type(exc).__name__}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("-j", type=int, default=8)
    a = ap.parse_args(argv)
    items = corpus()
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(a.j) as ex:
        got = dict(ex.map(_one, items, chunksize=8))
    if a.write:
        OUT.write_text(json.dumps({"made_at": "46f2bac", "cases": got}, indent=0, sort_keys=True)
                       + "\n", encoding="utf-8")
        print(f"wrote {len(got)} cases to {OUT}")
    if a.check:
        want = json.loads(OUT.read_text(encoding="utf-8"))["cases"]
        bad = [k for k in want if want[k] != got.get(k)]
        print(f"{len(want)} cases, {len(bad)} differ", bad[:10])
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
