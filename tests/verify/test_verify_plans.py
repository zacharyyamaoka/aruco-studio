"""M2b.1 / M2b.3 and REF tests/test_aruco_frame_pnp.py on plan_tag.

* every layout x 4 turns x corner mark off / on x label off / on, rendered
  from the layers at 20 px / mm: every id read, every ChArUco corner
  interpolated, the corners where the plan put them, the PnP pose within
  0.1 mm / 0.1 deg of TagPlan.frames.opencv;
* REF's frame_pnp cases (a single, grids 2x2 / 3x2 / 4x1, ChArUco 3x3,
  Zach's 4x2, a 5x4 legacy) x every Origin, marks none and cut;
* 10 relabelled copies of a labelled template: each reads as its own id,
  and only that id.
"""
from __future__ import annotations

import pytest

from aruco_studio.core import origin as OR
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T
from aruco_studio.plan import variants as V
from aruco_studio.plan.spec import TagSpec
from aruco_studio.verify.report import verify_plan

PNP = "tests/test_aruco_frame_pnp.py"
TOL_MM, TOL_DEG = 0.1, 0.1
AREA = {"single": (60.0, 60.0), "grid": (100.0, 70.0), "charuco": (100.0, 80.0)}


def _spec(layout, turn, mark, label, mode="both", op="new", numbers=None, area=None, **s):
    st = {"layout": layout, "mode": mode, "op": op, "turn": turn, "corner_mark": mark,
          "origin_v": 2, **s}
    if label:
        st["label"] = {"on": True, "place": "white" if mode == "both" else "auto"}
    w, h = area or AREA[layout]
    return TagSpec(settings=st, numbers=dict(numbers or {}), target=T.box(w, h, 0),
                   name="Arm", key="t1")


CASES = [(l, t, m, lab) for l in ("single", "grid", "charuco") for t in (0, 90, 180, 270)
         for m in ("none", "cut") for lab in (False, True)]


@pytest.mark.parametrize("layout,turn,mark,label", CASES,
                         ids=[f"{l}-{t}-{m}-{'label' if lab else 'nolabel'}" for l, t, m, lab in CASES])
def test_every_layout_turn_mark_label_reads_and_poses(layout, turn, mark, label):
    sp = _spec(layout, turn, mark, label)
    p = plan_tag(sp)
    assert p.ok, p.data["errors"]
    r = verify_plan(p, target=sp.target.to_dict(), px_per_mm=20.0)
    assert r["ids_read"] == sorted(p.data["ids"]), r
    assert r["corner_err_mm"] < 0.05, r
    if layout == "charuco":
        assert r["charuco_read"] == r["charuco_expected"], r
    assert r["pnp_err_mm"] < TOL_MM and r["pnp_err_deg"] < TOL_DEG, r


# REF tests/test_aruco_frame_pnp.py CASES: key, layout, area w x h, numbers, force, legacy
REF_CASES = (
    ("single", "single", 40.0, 40.0, {"size": 28.0, "marker_id": 7}, None, False),
    ("grid 2x2", "grid", 40.0, 40.0, {"size": 14.0, "marker_id": 10}, (2, 2), False),
    ("grid 3x2", "grid", 60.0, 40.0, {"size": 14.0, "marker_id": 20}, (3, 2), False),
    ("grid 4x1", "grid", 80.0, 25.0, {"size": 14.0, "marker_id": 30}, (4, 1), False),
    ("charuco 3x3", "charuco", 60.0, 60.0, {"size": 13.5, "square": 18.0, "marker_id": 0},
     (3, 3), False),
    ("charuco 4x2 (Zach's)", "charuco", 110.0, 60.0,
     {"size": 18.75, "square": 25.0, "marker_id": 0}, (4, 2), False),
    ("charuco 5x4 legacy", "charuco", 100.0, 80.0,
     {"size": 13.5, "square": 18.0, "marker_id": 20}, (5, 4), True))


def _ref_run(mark):
    worst = 0.0, 0.0
    for name, layout, w, h, nums, force, legacy in REF_CASES:
        p0 = plan_tag(_spec(layout, 0, mark, False, mode="black", op="join", numbers=nums,
                            area=(w, h), force=list(force) if force else None, legacy=legacy))
        assert p0.ok, (name, p0.data["errors"])
        sp0 = p0.data["marker"]
        if force:
            assert (sp0.get("cols", 1), sp0.get("rows", 1)) == tuple(force), name
        for turn in OR.TURNS_CW:
            spec = _spec(layout, turn, mark, False, mode="black", op="join", numbers=nums,
                         area=(w, h), force=list(force) if force else None, legacy=legacy)
            spec.target = T.box(w, h, 3)                # the black inlaid in a white part
            p = plan_tag(spec)
            sp = p.data["marker"]
            assert (sp.get("cols", 1), sp.get("rows", 1)) == OR.built(
                layout, turn, sp0.get("cols", 1), sp0.get("rows", 1))
            assert p.data["ids"] == p0.data["ids"] and p.data["placement"]["turn_deg"] == turn
            r = verify_plan(p, target=spec.target.to_dict(), px_per_mm=20.0)
            assert r["ids_read"] == sorted(p.data["ids"]), (name, turn, r)
            assert r["pnp_err_mm"] < TOL_MM and r["pnp_err_deg"] < TOL_DEG, (name, turn, r)
            worst = max(worst[0], r["pnp_err_mm"]), max(worst[1], r["pnp_err_deg"])
    return worst


@pytest.mark.ref(PNP, "== every layout x every Origin: the add-in's body, OpenCV's own board")
@pytest.mark.ref(PNP, "PnP vs the record / the Joint Origin's target (mm / deg), per Origin:")
def test_ref_frame_pnp__every_layout_every_origin():
    mm, deg = _ref_run("none")
    assert mm < TOL_MM and deg < TOL_DEG


@pytest.mark.ref(PNP, "== the same with Corner mark 'cut' (black square cut / triangle)")
def test_ref_frame_pnp__with_the_corner_mark():
    mm, deg = _ref_run("cut")
    assert mm < TOL_MM and deg < TOL_DEG


@pytest.mark.ref(PNP, "== the Origin's words and order (aruco_origin)")
def test_ref_frame_pnp__the_origins_words():
    assert OR.corners_of("grid") == ["Top left", "Top right", "Bottom right", "Bottom left"]
    assert OR.corners_of("single") == ["Up: top", "Up: right", "Up: bottom", "Up: left"]
    assert [OR.rotate_cw(t) for t in OR.TURNS_CW] == [270, 180, 90, 0]


def test_ten_relabelled_copies_read_as_their_own_ids():
    """M2b.3: a labelled template, 10 copies with other ids: each copy's
    render reads as its own id and only that id."""
    for layout in ("single", "grid"):
        sp = _spec(layout, 0, "none", True)
        t = plan_tag(sp)
        assert t.ok and t.data["label"]["kind"] != "none", t.data["warnings"]
        count = len(t.data["ids"])
        step = max(1, (50 - count - 1) // 10)
        for k in range(10):
            nid = 1 + k * step
            cp = V.copy_plan(t, nid, name=f"Arm:{k + 2}")
            r = verify_plan(cp, target=sp.target.to_dict(), pose=False)
            assert r["ids_read"] == list(range(nid, nid + count)), (layout, nid, r)
            assert cp.data["labels"] and str(nid) in cp.data["labels"][0]["text"]
