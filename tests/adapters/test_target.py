"""adapters/fusion/target.py: a stand-in face or profile -> plan.Target and
the base frame (PLAN M4 step 2).

* a plate's top face: its box, its loop in mm, the body under boxed in the
  base frame and measured;
* the face's longest edge reversed upstream (measured 2026-10-08: the tag
  turned 180 degrees): with the x it was made with (x_base) the frame, the
  Target and so the TagPlan are the same;
* x_ref (3D, as REF stores it) becomes the Target's 2D x_ref;
* a sketch profile with no body under it is a "free" target, its x along
  x_sketch, its side by z_sign;
* the Target plans: a face tag through it equals the same tag planned from
  a hand-made Target of the same box.
"""
from __future__ import annotations

import fake_adsk as FK
from aruco_studio.adapters.fusion import target as TG
from aruco_studio.plan import plan_tag
from aruco_studio.plan.spec import TagSpec
from aruco_studio.plan.target import box


def test_a_plate_face():
    _body, face = FK.plate(w_cm=6.0, h_cm=4.0, t_cm=0.3)
    t, base, keys = TG.of_face(face, {})
    o, x, y, z, w, h = base
    assert (round(t.w_mm, 9), round(t.h_mm, 9)) == (60.0, 40.0) and (w, h) == (6.0, 4.0)
    assert x == [1.0, 0.0, 0.0] and z == [0.0, 0.0, 1.0] and o == [0.0, 0.0, 0.0]
    assert sorted(tuple(round(c, 9) for c in p) for p in t.loops_mm[0]) == \
        [(-30.0, -20.0), (-30.0, 20.0), (30.0, -20.0), (30.0, 20.0)]
    assert t.has_body and t.body_mm["z0"] == -3.0 and t.body_mm["z1"] == 0.0
    assert t.body_mm["measured"] is True
    assert keys == {"x_base": [1.0, 0.0, 0.0]}


def test_a_reversed_edge_keeps_the_x_it_was_made_with():
    _b1, face = FK.plate()
    t1, base1, keys = TG.of_face(face, {})
    FK.reset()
    _b2, rev = FK.plate(reverse_edges=True)
    t_raw, base_raw, _k = TG.of_face(rev, {})
    assert base_raw[1] == [-1.0, 0.0, 0.0]                 # the longest edge runs the other way
    t2, base2, _k = TG.of_face(rev, keys)
    assert base2[:4] == base1[:4]
    s = {"layout": "grid", "dictionary": "DICT_4X4_50", "mode": "both", "op": "join"}
    n = {"marker_id": 0, "size": 0.0, "white_offset": 0.0, "white_height": 2.0,
         "black_offset": 2.0, "black_height": -0.6}
    a = plan_tag(TagSpec(settings=dict(s), numbers=dict(n), target=t1, key="k"), base=base1)
    b = plan_tag(TagSpec(settings=dict(s), numbers=dict(n), target=t2, key="k"), base=base2)
    assert a.data["record"] == b.data["record"]


def test_x_ref_goes_2d_in_the_base_frame():
    _b, face = FK.plate()
    t, _base, _k = TG.of_face(face, {"x_base": [1.0, 0.0, 0.0], "x_ref": [0.0, 1.0, 0.0]})
    assert t.x_ref == (0.0, 1.0)


def test_a_free_profile():
    comp = FK.design().rootComponent
    sk = FK.Sketch(comp, comp.xYConstructionPlane)
    prof = FK.Profile(sk, [[(-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)]])
    t, base, _k = TG.read(prof, {"x_sketch": [0.0, 1.0], "z_sign": -1})
    o, x, y, z, w, h = base
    assert t.kind == "free" and not t.has_body
    assert x == [0.0, 1.0, 0.0] and z == [0.0, 0.0, -1.0]
    assert (round(w, 12), round(h, 12)) == (2.0, 4.0)       # along the turned x / y


def test_the_target_plans_as_a_hand_made_box():
    _b, face = FK.plate(w_cm=6.0, h_cm=4.0, t_cm=0.3)
    t, base, _k = TG.of_face(face, {})
    hand = box(60.0, 40.0, thickness_mm=3.0)
    s = {"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both", "op": "join"}
    n = {"marker_id": 0, "size": 0.0, "white_offset": 0.0, "white_height": 2.0,
         "black_offset": 2.0, "black_height": -0.6}
    a = plan_tag(TagSpec(settings=dict(s), numbers=dict(n), target=t, key="k"))
    b = plan_tag(TagSpec(settings=dict(s), numbers=dict(n), target=hand, key="k"))
    assert a.ok and b.ok
    assert a.data["layers"] == b.data["layers"] and a.data["marker"] == b.data["marker"]
