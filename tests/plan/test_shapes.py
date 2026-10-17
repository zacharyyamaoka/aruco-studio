"""M8a.5: shapes to loops, and the faces of an extrude as Targets
(plan/shapes.py).

* a circle Ø50 strokes to the points core.faces strokes a Ø50 circle at
  0.05 mm (Fusion's chord tolerance); a slot's loop is closed and
  counter-clockwise; a hole is clockwise and inside; a hole outside its
  parent is an error on its path;
* a tag on a circle's side is an error naming "curved";
* the faces of a box: sizes, depth, right-handed frames whose z is the
  outward normal; the top's Target is POST /api/target's.
"""
from __future__ import annotations

import math

import pytest

from aruco_studio.core import faces as F
from aruco_studio.plan import shapes as SH
from aruco_studio.plan import target as T


def area(pts):
    return SH.area2(pts) / 2.0


def test_the_chord_tolerance_is_core_faces():
    assert SH.CHORD_MM == F.CHORD_TOL_MM == 0.05


def test_a_circle_strokes_as_core_faces_does():
    got = SH.stroke({"circle": 50})
    want = F.shape_pts(("circle", 0.0, 0.0, 25.0), 0.05)
    assert got == [want]
    # every chord within the tolerance, counter-clockwise
    r = 25.0
    for (x0, y0), (x1, y1) in zip(want, want[1:] + want[:1]):
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        assert r - math.hypot(mx, my) <= 0.05 + 1e-12
    assert area(want) > 0


def test_a_slot_is_closed_and_counter_clockwise():
    loop = SH.stroke({"slot": [74, 24]})[0]
    assert loop == F.shape_pts(("stadium", 0.0, 0.0, 50.0, 12.0), 0.05)    # the gallery's slot
    assert area(loop) > 0
    xs = [x for x, _ in loop]
    ys = [y for _, y in loop]
    assert abs(max(xs) - min(xs) - 74.0) < 1e-9 and abs(max(ys) - min(ys) - 24.0) < 1e-9
    # closed: the last point runs back to the first along the bottom line
    (xa, ya), (xb, yb) = loop[-1], loop[0]
    assert abs(ya + 12.0) < 1e-9 and abs(yb + 12.0) < 1e-9 and xa < xb
    es = SH.edges({"slot": [74, 24]})
    assert [e[2] for e in es] == [True, True] and es[0][0] == (-25.0, -12.0)
    with pytest.raises(SH.ShapeError, match="more than its width"):
        SH.stroke({"slot": [20, 24]})


def test_rect_polygon_loops():
    assert SH.stroke({"rect": [80, 50]}) == [[(-40.0, -25.0), (40.0, -25.0), (40.0, 25.0),
                                               (-40.0, 25.0)]]
    cw = [[0, 0], [0, 10], [10, 10], [10, 0]]
    got = SH.stroke({"polygon": cw})[0]
    assert area(got) > 0 and got[0] == (0.0, 0.0)            # made counter-clockwise, first kept
    assert SH.stroke({"loops": [cw]})[0] == [tuple(map(float, p)) for p in cw][::-1]


def test_a_hole_is_clockwise_and_inside():
    loops = SH.stroke({"rect": [80, 50], "holes": [{"circle": 18}, {"rect": [6, 4], "at": [30, 0],
                                                                   "rot": 90}]})
    assert len(loops) == 3
    assert area(loops[0]) > 0 and area(loops[1]) < 0 and area(loops[2]) < 0
    assert loops[1] == F.shape_pts(("circle", 0.0, 0.0, 9.0), 0.05)[::-1]
    xs = [x for x, _ in loops[2]]
    assert abs(min(xs) - 28.0) < 1e-9 and abs(max(xs) - 32.0) < 1e-9   # turned 90 degrees
    for lp in loops[1:]:
        assert SH.loop_inside(lp, loops[0])


@pytest.mark.parametrize("hole, why", [
    ({"circle": 18, "at": [60, 0]}, "inside"),            # wholly outside
    ({"circle": 18, "at": [36, 0]}, "inside"),            # across the edge
    ({"circle": 4, "holes": [{"circle": 1}]}, "never has holes"),
    ({"triangle": 3}, "one of"),
])
def test_a_bad_hole_is_an_error_on_its_path(hole, why):
    with pytest.raises(SH.ShapeError) as e:
        SH.stroke({"rect": [80, 50], "holes": [{"circle": 6}, hole]})
    assert e.value.path.startswith("holes[1]") and why in e.value.message


def test_bad_shapes():
    for bad, path in (({"rect": [0, 5]}, "rect[0]"), ({"circle": -2}, "circle"),
                      ({"polygon": [[0, 0], [1, 1]]}, "polygon"), ({}, ""),
                      ({"rect": [1, 1], "circle": 3}, "")):
        with pytest.raises(SH.ShapeError) as e:
            SH.stroke(bad)
        assert e.value.path == path, (bad, e.value.path)


def test_the_top_is_api_targets_target():
    assert SH.extruded_top({"rect": [80, 50]}, 5).to_dict() == T.box(80, 50, 5).to_dict()
    sh = {"rect": [80, 50], "holes": [{"circle": 18}]}
    want = T.from_loops(SH.stroke(sh), 5, centre=False)
    assert SH.face_target(sh, 5, "top").target.to_dict() == want.to_dict()
    assert SH.bare_target(sh).to_dict() == T.from_loops(SH.stroke(sh), 0, centre=False).to_dict()
    assert not SH.bare_target(sh).has_body and SH.bare_target(sh).kind == "face"


def _frame_ok(fr, normal):
    cols = [[fr[r * 4 + c] for r in range(3)] for c in range(3)]
    for i in range(3):
        for j in range(3):
            d = sum(a * b for a, b in zip(cols[i], cols[j]))
            assert abs(d - (1.0 if i == j else 0.0)) < 1e-12
    u, v, n = cols
    cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    assert all(abs(a - b) < 1e-12 for a, b in zip(cross, n))           # right-handed
    assert all(abs(a - b) < 1e-12 for a, b in zip(n, normal))


def test_the_faces_of_a_box():
    sh = {"rect": [120, 40]}
    names = SH.face_names(sh)
    assert {"top", "bottom", "side0", "side3", "front", "right", "back", "left"} <= set(names)
    want = {"front": (120, 40, (0, -1, 0)), "right": (40, 120, (1, 0, 0)),
            "back": (120, 40, (0, 1, 0)), "left": (40, 120, (-1, 0, 0))}
    for face, (w, depth, n) in want.items():
        ft = SH.face_target(sh, 40, face)
        t = ft.target
        assert (t.w_mm, t.h_mm) == (w, 40) and t.has_body and t.loops_mm == []
        assert t.body_mm["depth"] == depth and t.body_mm["z0"] == -depth and t.body_loops_mm is None
        _frame_ok(ft.frame, n)
        assert ft.frame[11] == 20.0                                   # mid height
        assert SH.face_target(sh, 40, f"side{list(want).index(face)}").frame == ft.frame
    top, bot = SH.face_target(sh, 40, "top"), SH.face_target(sh, 40, "bottom")
    _frame_ok(top.frame, (0, 0, 1))
    _frame_ok(bot.frame, (0, 0, -1))
    assert top.frame[11] == 40.0 and bot.frame[11] == 0.0 and bot.target.z_sign == -1
    down = SH.face_target(sh, -10, "top")                            # an extrude downwards
    assert down.frame[11] == 0.0 and down.target.body_mm["z0"] == -10.0


def test_a_mirrored_bottom():
    sh = {"polygon": [[0, 0], [30, 0], [0, 20]]}
    t = SH.face_target(sh, 3, "bottom").target
    assert sorted(t.loops_mm[0]) == sorted([(-x, y) for x, y in SH.stroke(sh)[0]])
    assert area(t.loops_mm[0]) > 0


def test_a_circles_side_is_curved():
    for face in ("side0", "front"):
        with pytest.raises(SH.ShapeError, match="curved"):
            SH.face_target({"circle": 50}, 10, face)
    with pytest.raises(SH.ShapeError, match="ends are curved"):
        SH.face_target({"slot": [40, 12]}, 10, "side2")
    with pytest.raises(SH.ShapeError, match="no face"):
        SH.face_target({"rect": [10, 10]}, 10, "lid")
