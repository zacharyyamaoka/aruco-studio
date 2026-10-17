"""adapters/recipe.py: a TagPlan as build steps, on every evaluate() golden
case (PLAN M4.2, the data half): one step per Layer, the layer's z, in
`parts` order; shapes a CAD shell can build; the frames composed with the
host's base frame; the timeline orders create() makes."""
from __future__ import annotations

import math
import random

import pytest

import _cases as C
from aruco_studio.adapters import recipe as RC


@pytest.mark.parametrize("group", C.GROUPS)
def test_one_step_per_layer_with_its_z_in_parts_order(group):
    bad, n = [], 0
    for cid, p in C.plans(group):
        if not p.ok:
            continue
        d = p.data
        rec = RC.recipe(p)
        steps = list(RC.steps(rec))
        n += 1
        if len(steps) != len(d["layers"]):
            bad.append((cid, "count", len(steps), len(d["layers"])))
            continue
        if [x["role"] for x in rec["parts"]] != d["parts"]:
            bad.append((cid, "parts", [x["role"] for x in rec["parts"]], d["parts"]))
        # the steps, read back in build order, are the layers grouped by part
        # then solid, each keeping its own order
        want = sorted(range(len(d["layers"])),
                      key=lambda i: (d["parts"].index(d["layers"][i]["part"]),
                                     d["layers"][i]["solid"], i))
        for (part, solid, st), i in zip(steps, want):
            L = d["layers"][i]
            if (part["role"], solid, st["layer"], st["step"], st["z"]) != \
                    (L["part"], L["solid"], L["name"], L["step"], L["z"]):
                bad.append((cid, "step", st["layer"], L["name"]))
                break
            if len(st["polygons"]) != len(L["polygons"]):
                bad.append((cid, "polygons", L["name"]))
    assert n > 30 and not bad, bad[:5]


def test_shapes_are_boxes_cylinders_or_convex_prisms():
    kinds = {}
    for cid, p in C.all_plans():
        if not p.ok:
            continue
        for _part, _s, st in RC.steps(RC.recipe(p)):
            for q in st["polygons"]:
                kinds[q["outer"]["kind"]] = kinds.get(q["outer"]["kind"], 0) + 1
    assert set(kinds) <= {"box", "cylinder", "prism"}, kinds
    assert kinds["box"] > 1000 and kinds["cylinder"] > 10 and kinds["prism"] > 100, kinds


def test_box_of_a_rotated_rectangle_and_a_concave_outline():
    c, s = math.cos(0.3), math.sin(0.3)
    pts = [(x * c - y * s + 5, x * s + y * c - 2) for x, y in ((-2, -1), (2, -1), (2, 1), (-2, 1))]
    b = RC.shape_of(pts)
    assert b["kind"] == "box" and abs(b["w"] - 4) < 1e-12 and abs(b["h"] - 2) < 1e-12
    assert abs(b["c"][0] - 5) < 1e-12 and abs(math.atan2(b["x"][1], b["x"][0]) - 0.3) < 1e-12
    ell = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
    t = RC.shape_of(ell)
    assert t["kind"] == "triangles" and len(t["tris"]) == 4
    area = sum(abs(RC._area2(tr)) / 2 for tr in t["tris"])
    assert abs(area - 7.0) < 1e-12


def test_frames_compose_with_the_host_base_frame():
    rnd = random.Random(4)
    _cid, p = next((cid, p) for cid, p in C.plans("matrix") if p.ok)
    d = p.data
    ident = RC.recipe(p)
    o, x, y, z = RC.frame_of_matrix(d["frames"]["pattern_in_target"])
    assert all(abs(ident["frames"]["pattern_cm"][0][i] - o[i] / 10.0) < 1e-12 for i in range(3))
    for _ in range(20):
        a = rnd.uniform(-3, 3)
        base = ([rnd.uniform(-9, 9) for _ in range(3)], [math.cos(a), math.sin(a), 0.0],
                [-math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0])
        r = RC.recipe(p, base)
        pf = r["frames"]["pattern_cm"]
        for u, v, w in ((0, 0, 0), (3, -2, 1.5)):
            got = RC.to_host(pf, u, v, w)
            t = [ident["frames"]["pattern_cm"][0][i] * 10 + (x[i] * u + y[i] * v + z[i] * w)
                 for i in range(3)]                     # target frame, mm
            want = [base[0][i] + (base[1][i] * t[0] + base[2][i] * t[1] + base[3][i] * t[2]) / 10
                    for i in range(3)]
            assert all(abs(got[i] - want[i]) < 1e-12 for i in range(3))


def test_timeline_orders_and_names():
    for _cid, p in C.plans("legacy"):
        if not p.ok:
            continue
        a = RC.recipe(p, layout="create")
        b = RC.recipe(p, layout="wrap_first", frame_sketch=False)
        roles = [x["role"] for x in a["parts"]]
        assert a["timeline"][0] == ["sketch", RC.FRAME_SKETCH]
        assert [t[1] for t in a["timeline"] if t[0] == "base"] == roles
        for i, t in enumerate(a["timeline"]):
            if t[0] == "combine":
                assert a["timeline"][i - 1] == ["base", t[1]]
        kinds = [t[0] for t in b["timeline"]]
        assert kinds == sorted(kinds, key=lambda k: k != "base")      # every base first
        names = {x["role"]: x["name"] for x in a["parts"]}
        key = p.data["key"] or "tag"
        assert names["pattern"] in (f"aruco cells {key}", f"aruco white {key}")
        if "tile" in names:
            assert names["tile"] == f"tag tile {key}"


def test_a_refused_plan_is_a_refused_recipe():
    from aruco_studio.plan import plan_tag
    p = plan_tag({"schema": "arucostudio.tagspec/1", "settings": {"layout": "nope"},
                  "numbers": {}, "target": {"kind": "face", "w_mm": 40, "h_mm": 40}})
    r = RC.recipe(p)
    assert not r["ok"] and r["errors"]
