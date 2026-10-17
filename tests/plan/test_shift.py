"""Shift (2026-10-17, Zach's CF-2, P3's Shift X / Y): `settings.shift =
{"rule": 1, "x_mm", "y_mm"}` moves a sticker off where the fit puts it,
along its target's own u / v. Absent = centred, bit for bit. A sticker's
(3D tags are a placeholder, CF-13: they read it and do not move). New
behaviour, no REF: tested by its properties and by OpenCV.
"""
from __future__ import annotations

import copy
import math

import pytest

from aruco_studio.core import make as MK
from aruco_studio.plan import mesh as ME
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T

R2 = {"rule": 2, "by": "sticker", "thickness_mm": 0.1, "perimeter": "marker", "page": "letter",
      "page_margin_mm": 10.0}
R1 = {"rule": 1, "by": "sticker"}


def plan(shift=None, layout="single", size=24.0, make=R2, target=None, **s):
    st = dict({"layout": layout, "make": dict(make)}, **s)
    if shift is not None:
        st["shift"] = shift
    return plan_tag({"settings": st, "numbers": {"size": size},
                     "target": target or T.box(90, 60, 0).to_dict()})


def origin(p, key="pattern_in_target"):
    m = p.data["frames"][key]
    return (m[3], m[7])


CASES = [(lay, turn, x, y, mk) for lay in ("single", "grid", "charuco") for turn in (0, 90, 270)
         for x, y in ((12.0, 0.0), (0.0, -7.5), (9.25, 6.0)) for mk in ("r1", "r2")]


@pytest.mark.parametrize("lay,turn,x,y,mk", CASES, ids=[f"{a}-{b}-{c}-{d}-{e}" for a, b, c, d, e in CASES])
def test_shift_moves_the_tag_by_exactly_x_y_in_the_target_frame(lay, turn, x, y, mk):
    make = R2 if mk == "r2" else R1
    size = 24.0 if lay == "single" else 10.0
    a = plan(None, lay, size, make, turn=turn, origin_v=2)
    b = plan({"rule": 1, "x_mm": x, "y_mm": y}, lay, size, make, turn=turn, origin_v=2)
    assert a.ok and b.ok, (a.data["errors"], b.data["errors"])
    (ax, ay), (bx, by) = origin(a), origin(b)
    assert (bx - ax, by - ay) == pytest.approx((x, y), abs=1e-9)
    (ox, oy), (px, py) = origin(a, "opencv_target"), origin(b, "opencv_target")
    assert (px - ox, py - oy) == pytest.approx((x, y), abs=1e-9)        # OpenCV's frame with it
    # the tag itself is the same: its layers, its top view, its ids (pattern frame)
    assert b.data["layers"] == a.data["layers"]
    assert ME.top(b) == ME.top(a)
    assert b.data["ids"] == a.data["ids"] and b.data["marker"] == a.data["marker"]
    assert b.data["placement"]["shift_mm"] == [x, y] and "shift_mm" not in a.data["placement"]


def test_absent_and_zero_are_centred_bit_for_bit():
    a = plan(None)
    assert plan({"rule": 1, "x_mm": 0.0, "y_mm": 0.0}).data["placement"] == a.data["placement"]
    d0 = plan(None, make=R1).to_dict()
    d1 = plan({"rule": 1, "x_mm": 0, "y_mm": 0}, make=R1).to_dict()
    assert d0 == d1


def test_a_shifted_sticker_reads_and_its_pose_holds():
    from aruco_studio.verify.report import verify_plan
    for lay in ("single", "charuco"):
        p = plan({"rule": 1, "x_mm": 11.0, "y_mm": -4.0}, lay, 24.0 if lay == "single" else 10.0)
        rep = verify_plan(p, px_per_mm=20.0, pose=True)
        assert rep["ok"] and rep["pnp_err_mm"] <= 0.1 and rep["pnp_err_deg"] <= 0.1, rep


def test_a_3d_tag_does_not_move_and_says_so():
    t = T.box(90, 60, 3).to_dict()
    a = plan_tag({"settings": {"layout": "single"}, "numbers": {"size": 24}, "target": t})
    b = plan_tag({"settings": {"layout": "single", "shift": {"rule": 1, "x_mm": 9, "y_mm": 0}},
                  "numbers": {"size": 24}, "target": t})
    assert origin(a) == origin(b) and b.data["layers"] == a.data["layers"]
    assert any(w["field"] == "settings.shift" and w["level"] == "info" for w in b.data["warnings"])


def test_off_the_face_and_over_a_hole_are_warned():
    off = plan({"rule": 1, "x_mm": 40.0, "y_mm": 0.0})
    assert off.ok and any(w["field"] == "settings.shift" and "runs off the face" in w["text"]
                          for w in off.data["warnings"])
    ok = plan({"rule": 1, "x_mm": 20.0, "y_mm": 8.0})
    assert not [w for w in ok.data["warnings"] if w["field"] == "settings.shift"]
    prof = plan({"rule": 1, "x_mm": 0.0, "y_mm": -25.0}, target=T.disc(30).to_dict(), size=20.0,
                make=dict(R2, perimeter="profile"))
    assert any(w["field"] == "settings.shift" and "runs off the outline" in w["text"]
               for w in prof.data["warnings"])
    hole = plan({"rule": 1, "x_mm": 25.0, "y_mm": 0.0}, target=T.disc(40, [(25.0, 0.0, 6.0)]).to_dict(),
                size=12.0, holes="avoid")
    assert any(w["field"] == "settings.shift" and "covers hole 1" in w["text"]
               for w in hole.data["warnings"])


@pytest.mark.parametrize("bad,field", [({"rule": 7}, "settings.shift"), ("left", None),
                                       ({"rule": 1, "x_mm": "far"}, "settings.shift.x_mm"),
                                       ({"rule": 1, "y_mm": 900.0}, "settings.shift.y_mm")])
def test_junk_shift(bad, field):
    if field is None:                       # a wrong TYPE is the 422 layer
        from aruco_studio.plan import SpecTypeError, TagSpec
        with pytest.raises(SpecTypeError):
            TagSpec.from_dict({"settings": {"shift": bad}, "target": T.box(40, 40, 0).to_dict()})
        return
    p = plan(bad)
    assert p.ok and any(w["field"] == field and w["level"] == "warn" for w in p.data["warnings"])
    xy, _n = MK.shift_of({"shift": bad})
    assert all(abs(v) <= MK.SHIFT_MAX_MM for v in xy)
