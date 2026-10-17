"""M6a.8 (ST-T-WYSIWYG-1): the printed page equals the plan.

A 12-sticker scene -- single, grid and ChArUco; labels on the black and on
the white; triangle and cut corners; two Profile outlines (one with four
holes), one sticker only fitting turned -- is laid out spaced and tight on
Letter and on A4, rasterised by pdfium at 600 dpi and checked against each
plan (verify/sheet_check.py, M6 note section g steps 1-8):
ink XOR <= 2 %, every id, the side within 0.15 mm, label IoU >= 0.9, the
outline within 0.15 mm with every hole, the bars 100.0 / 101.6 +/- 0.1 mm.
"""
from __future__ import annotations

import json

import pytest

from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec
from aruco_studio.scene import Scene, renumber
from aruco_studio.scene import sheet as SS
from aruco_studio.verify import sheet_check as SC

STK = {"rule": 1, "by": "sticker"}


def lab(place, content="id"):
    return {"on": True, "rule": 3, "place": place, "content": content, "nozzle_mm": 0.2}


def twelve() -> Scene:
    sc = Scene(name="wysiwyg")
    rows = [
        ("single", T.box(40, 40, 0), {"label": lab("black"), "corner_mark": "triangle"}, {}),
        ("single", T.box(40, 40, 0), {"label": lab("white", "id_name")}, {"margin_mm": 6.0}),
        ("single", T.box(50, 50, 0), {"corner_mark": "cut"}, {}),
        ("grid", T.box(90, 60, 0), {"label": lab("black")}, {}),
        ("grid", T.box(80, 50, 0), {"corner_mark": "triangle"}, {}),
        ("charuco", T.box(90, 70, 0), {"label": lab("black")}, {}),
        ("charuco", T.box(100, 80, 0), {}, {}),
        ("single", T.from_face("disc4"), {}, {"perimeter": "profile"}),
        ("single", T.from_face("dshape"), {"label": lab("white")}, {"perimeter": "profile"}),
        ("single", T.box(30, 30, 0), {"dictionary": "DICT_5X5_100"}, {}),
        ("single", T.box(35, 35, 0), {"dictionary": "DICT_6X6_250", "label": lab("black"),
                                      "corner_mark": "triangle"}, {}),
        ("single", T.from_loops([[(0, 0), (210, 0), (210, 22), (0, 22)]]), {},
         {"perimeter": "profile"}),
    ]
    for k, (layout, tgt, extra, make) in enumerate(rows):
        s = {"layout": layout, "make": dict(STK, **make), **extra}
        sc.add(TagSpec(settings=s, target=tgt, name=f"part{k}"), x_mm=120 * (k % 4),
               y_mm=120 * (k // 4), name=f"part{k}")
    renumber(sc)
    return sc


SC12 = twelve()
PLANS = SC12.plans()


def test_the_scene():
    assert len(SC12.tags) == 12
    assert all(PLANS[t.name].ok and PLANS[t.name].data["made_by"] == "sticker" for t in SC12.tags)
    kinds = {PLANS[t.name].data["marker"]["layout"] for t in SC12.tags}
    assert kinds == {"single", "grid", "charuco"}
    labels = {PLANS[t.name].data["label"]["kind"] for t in SC12.tags if PLANS[t.name].data["label"]}
    assert labels == {"black", "white"}
    marks = {(PLANS[t.name].data["mark"] or {}).get("kind") for t in SC12.tags}
    assert {"triangle", "tile_cut"} <= marks
    assert sum(PLANS[t.name].data["guides"]["cut_line"]["kind"] == "profile"
               for t in SC12.tags) >= 2


@pytest.mark.parametrize("mode", ["spaced", "tight"])
@pytest.mark.parametrize("page", ["letter", "a4"])
def test_the_page_equals_the_plan(mode, page):
    rep = SC.check_scene_sheet(SC12, PLANS, page=page, mode=mode, date="2026-10-16")
    assert not rep["rejected"], rep["rejected"]
    assert len(rep["stickers"]) == 12
    bad = [r for r in rep["stickers"] if not r["ok"]]
    assert not bad, json.dumps(bad, indent=1)[:3000]
    w = rep["worst"]
    assert w["ink_xor"] <= SC.INK_XOR_MAX
    assert w["side_err_mm"] <= SC.SIDE_MAX_MM
    assert w["label_iou_min"] >= SC.LABEL_IOU_MIN
    assert w["outline_mm"] <= SC.OUTLINE_MAX_MM
    assert rep["pages"] and all(b["ok"] for b in rep["pages"])
    assert w["bar_err_mm"] <= SC.BAR_TOL_MM
    for r in rep["stickers"]:
        assert not r["ids"]["missing"]
        if r["key"] == "part7":
            assert r["outline"]["holes"] == r["outline"]["holes_found"] == 4
    assert any(r["rotation"] == 90 for r in rep["stickers"])
    print(f"\nM6a.8 {page} {mode}: " + json.dumps(w))


def test_a_wrong_page_fails_the_check():
    """The oracle is not blind: the PDF of one scene against another
    scene's plans fails the ink check."""
    got = SS.sticker_files(SC12, PLANS, date="2026-10-16")
    summ = json.loads(got["sheet.json"])
    plans = {k: p.to_dict() for k, p in PLANS.items()}
    a, b = summ["stickers"][0]["key"], summ["stickers"][1]["key"]
    plans[a], plans[b] = plans[b], plans[a]
    rep = SC.check_sheet(got["sheet.pdf"], summ, plans)
    assert not rep["ok"]


def test_a_mis_scaled_print_fails_the_bars():
    import numpy as np
    import cv2
    got = SS.sticker_files(SC12, PLANS, date="2026-10-16")
    summ = json.loads(got["sheet.json"])
    pages = SC.rasterise(got["sheet.pdf"])
    small = [cv2.resize(p, None, fx=0.97, fy=0.97, interpolation=cv2.INTER_AREA) for p in pages]
    small = [np.pad(p, ((0, a.shape[0] - p.shape[0]), (0, a.shape[1] - p.shape[1])),
                    constant_values=255) for p, a in zip(small, pages)]
    rep = SC.check_sheet(got["sheet.pdf"], summ, {k: p.to_dict() for k, p in PLANS.items()},
                         pages=small)
    assert not any(b["ok"] for b in rep["pages"])
