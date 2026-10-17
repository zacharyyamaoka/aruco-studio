"""adapters/fusion/bodies.py on the stand-in's TemporaryBRepManager, every
evaluate() golden case (PLAN M4.2, M4.3).

* each layer is built as exactly the TBM calls its shapes need (a box, a
  cylinder, a convex prism = its box + one cut per slanted side), and its
  body spans exactly the layer's z (probed just inside and just outside
  both ends);
* each part's body, probed at every outline of the part (the cells, the
  label strokes, the corner mark, the pins and their holes, the tile, the
  trim column), answers what the plan's own 2D evaluation of the same
  layers answers -- the stand-in's CSG is 3D and knows nothing of the plan.
"""
from __future__ import annotations

import pytest

import _cases as C

MIN_LAYERS = {"legacy": 100, "matrix": 3000}
MIN_PROBES = {"legacy": 2000, "matrix": 30000}
import fake_adsk as FK
from aruco_studio.adapters import recipe as RC
from aruco_studio.adapters.fusion import bodies as B

D = 1e-3          # mm: just inside / outside a z bound


def _calls(shape):
    k = shape["kind"]
    if k in ("box", "cylinder"):
        return 1
    if k == "prism":
        pts = shape["pts"]
        us, vs = [p[0] for p in pts], [p[1] for p in pts]
        u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
        cuts = 0
        for i in range(len(pts)):
            (a, b), (p, q) = pts[i], pts[(i + 1) % len(pts)]
            on = (abs(a - p) < 1e-8 and (abs(a - u0) < 1e-8 or abs(a - u1) < 1e-8)) or \
                (abs(b - q) < 1e-8 and (abs(b - v0) < 1e-8 or abs(b - v1) < 1e-8))
            cuts += 0 if on else 1
        return 1 + cuts
    return sum(_calls({"kind": "prism", "pts": t}) for t in shape["tris"])


def _centre(shape):
    if shape["kind"] in ("box", "cylinder"):
        return shape["c"]
    pts = shape["pts"] if shape["kind"] == "prism" else shape["tris"][0]
    return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]


@pytest.mark.parametrize("group", C.GROUPS)
def test_every_layer_is_its_shapes_over_its_z(group):
    bad, layers = [], 0
    for cid, p in C.plans(group):
        if not p.ok:
            continue
        rec = RC.recipe(p)
        pf = rec["frames"]["pattern_cm"]
        for part, _solid, st in RC.steps(rec):
            FK.LOG.clear()
            body = B.step_body(pf, st)
            made = sum(1 for x in FK.LOG if x.startswith(("tbm.createBox", "tbm.createCyl")))
            want = sum(_calls(q["outer"]) + sum(_calls(h) for h in q["holes"])
                       for q in st["polygons"])
            layers += 1
            if made != want:
                bad.append((cid, st["layer"], "calls", made, want))
                continue
            lo, hi = st["z"]
            for q in st["polygons"]:
                u, v = _centre(q["outer"])
                ins = [body.contains(RC.to_host(pf, u, v, z)) for z in (lo + D, hi - D)]
                outs = [body.contains(RC.to_host(pf, u, v, z)) for z in (lo - D, hi + D)]
                if not all(ins) or any(outs):
                    bad.append((cid, part["role"], st["layer"], "z", ins, outs))
                    break
    assert layers > MIN_LAYERS[group] and not bad, bad[:5]


@pytest.mark.parametrize("group", C.GROUPS)
def test_every_part_probes_as_the_plan_says(group):
    bad, probes = [], 0
    for cid, p in C.plans(group):
        if not p.ok:
            continue
        d = p.data
        rec = RC.recipe(p)
        pf = rec["frames"]["pattern_cm"]
        for part in rec["parts"]:
            body = B.part_body(rec, part)
            for name, u, v, z in C.probe_points(d["layers"], part["role"]):
                want = C.part_has(d["layers"], part["role"], u, v, z)
                got = body.contains(RC.to_host(pf, u, v, z))
                probes += 1
                if got != want:
                    bad.append((cid, part["role"], name, round(u, 4), round(v, 4), got, want))
    assert probes > MIN_PROBES[group] and not bad, bad[:6]


def test_the_probes_cover_marks_labels_pins_and_trim():
    seen = set()
    for _cid, p in C.all_plans():
        if p.ok:
            for L in p.data["layers"]:
                seen.add(L["name"])
    assert {"cells", "pattern", "label_join", "label_cut", "mark_cut", "mark_triangle",
            "mark_keep", "pin", "hole", "tile", "pocket", "trim_keep", "white_strip"} <= seen, seen
