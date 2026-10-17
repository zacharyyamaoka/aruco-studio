"""WYSIWYG still holds for the 2D model (2026-10-17; design note M6 section
g): a mixed sticker scene -- make rule 1 (the ink film) and rule 2 (the
black t/2 inside the paper), single / grid / ChArUco, labels, corner
marks, a Profile disc with holes, a shifted sticker, 2 mm "paper" -- with
the sheet's own Sticker margin and Cut lines (Zach's Q7), rasterised by
pdfium at 600 dpi and compared with each plan (verify/sheet_check.py):
ink XOR <= 2 %, every id read by OpenCV at true scale (the marker side
within 0.15 mm), labels IoU >= 0.9, the (grown) outline within 0.15 mm
with every hole, the bars. A sticker over the page is rejected by the
sheet with its reason (the page lint said so in the plan).
"""
from __future__ import annotations

import json

import pytest

from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec
from aruco_studio.scene import Scene, renumber
from aruco_studio.scene import sheet as SS
from aruco_studio.verify import sheet_check as SC

R1 = {"rule": 1, "by": "sticker"}
R2 = {"rule": 2, "by": "sticker", "thickness_mm": 0.1, "perimeter": "marker", "page": "letter",
      "page_margin_mm": 10.0}


def lab(place, content="id"):
    return {"on": True, "rule": 3, "place": place, "content": content, "nozzle_mm": 0.2}


def mixed(oversize=False) -> Scene:
    sc = Scene(name="wysiwyg-2d")
    rows = [
        ("single", T.box(40, 40, 0), {"label": lab("black"), "corner_mark": "triangle"}, R2, {}),
        ("single", T.box(40, 40, 0), {"label": lab("black")}, R1, {}),
        ("single", T.box(50, 50, 0), {"corner_mark": "cut"}, R2, {}),
        ("grid", T.box(90, 60, 0), {"label": lab("black")}, R2, {}),
        ("grid", T.box(80, 50, 0), {"corner_mark": "triangle"}, R1, {}),
        ("charuco", T.box(90, 70, 0), {"label": lab("black")}, R2, {}),
        ("charuco", T.box(100, 80, 0), {}, dict(R2, thickness_mm=2.0), {}),
        ("single", T.from_face("disc4"), {}, dict(R2, perimeter="profile"), {}),
        ("single", T.from_face("dshape"), {"label": lab("white")}, dict(R2, perimeter="profile"), {}),
        ("single", T.box(60, 45, 0), {"shift": {"rule": 1, "x_mm": 9.0, "y_mm": 4.0}}, R2,
         {"size": 24.0}),
        ("single", T.box(35, 35, 0), {"dictionary": "DICT_6X6_250", "label": lab("black"),
                                      "corner_mark": "triangle"}, R2, {}),
    ]
    if oversize:
        rows.append(("single", T.box(280, 280, 0), {}, R2, {"size": 200.0}))
    for k, (layout, tgt, extra, make, nums) in enumerate(rows):
        s = {"layout": layout, "make": dict(make), **extra}
        sc.add(TagSpec(settings=s, numbers=dict(nums), target=tgt, name=f"s{k}"), x_mm=120 * (k % 4),
               y_mm=120 * (k // 4), name=f"s{k}")
    renumber(sc)
    return sc


SC_ = mixed()
PLANS = SC_.plans()


def test_the_scene_mixes_both_rules():
    rules = [PLANS[t.name].data["rules"]["make"] for t in SC_.tags]
    assert sorted(set(rules)) == [1, 2] and rules.count(2) >= 8
    assert all(PLANS[t.name].ok and PLANS[t.name].data["made_by"] == "sticker" for t in SC_.tags)
    assert {PLANS[t.name].data["marker"]["layout"] for t in SC_.tags} == {"single", "grid", "charuco"}
    assert any(PLANS[t.name].data["placement"].get("shift_mm") for t in SC_.tags)


@pytest.mark.parametrize("margin", [0.0, 2.5])
@pytest.mark.parametrize("mode", ["spaced", "tight"])
def test_the_page_equals_the_plan(mode, margin):
    rep = SC.check_scene_sheet(SC_, PLANS, page="letter", mode=mode, date="2026-10-17",
                               sticker_margin_mm=margin)
    assert not rep["rejected"], rep["rejected"]
    assert len(rep["stickers"]) == len(SC_.tags)
    bad = [r for r in rep["stickers"] if not r["ok"]]
    assert not bad, json.dumps(bad, indent=1)[:3000]
    w = rep["worst"]
    assert w["ink_xor"] <= SC.INK_XOR_MAX
    assert w["side_err_mm"] <= SC.SIDE_MAX_MM
    assert w["label_iou_min"] >= SC.LABEL_IOU_MIN
    assert w["outline_mm"] <= SC.OUTLINE_MAX_MM
    assert rep["pages"] and all(b["ok"] for b in rep["pages"])
    for r in rep["stickers"]:
        assert not r["ids"]["missing"], r
        if r["key"] == "s7":                         # the disc's four holes, cut
            assert r["outline"]["holes"] == r["outline"]["holes_found"] == 4
    print(f"\n2d-core WYSIWYG {mode} margin {margin}: " + json.dumps(w))


def test_the_margin_is_what_is_cut():
    got = SS.sticker_files(SC_, PLANS, mode="tight", date="2026-10-17", sticker_margin_mm=2.5)
    plain = SS.sticker_files(SC_, PLANS, mode="tight", date="2026-10-17")
    a = {s["key"]: s for s in json.loads(got["sheet.json"])["stickers"]}
    b = {s["key"]: s for s in json.loads(plain["sheet.json"])["stickers"]}
    for k in a:
        wa, ha = (a[k]["w_mm"], a[k]["h_mm"]) if a[k]["rotation"] == b[k]["rotation"] else \
            (a[k]["h_mm"], a[k]["w_mm"])
        assert (wa, ha) == pytest.approx((b[k]["w_mm"] + 5.0, b[k]["h_mm"] + 5.0), abs=0.02), k


def test_cut_lines_off_print_the_stickers_alone():
    rep = SC.check_scene_sheet(SC_, PLANS, page="letter", mode="spaced", date="2026-10-17",
                               cut_lines=False)
    assert rep["ok"], json.dumps([r for r in rep["stickers"] if not r["ok"]])[:2000]
    assert all(r["outline"].get("off") for r in rep["stickers"])
    # the raster really has no cut line: no grey pixels away from the ink in a sticker's box
    import numpy as np
    got = SS.sticker_files(SC_, PLANS, mode="spaced", date="2026-10-17", cut_lines=False)
    summ = json.loads(got["sheet.json"])
    pages = SC.rasterise(got["sheet.pdf"])
    s = SC.DPI / 25.4
    for st in summ["stickers"]:
        x0, y0, x1, y1 = SC._box_px(st, s, 0.6)
        crop = pages[st["page"] - 1][y0:y1, x0:x1]
        grey = (crop >= SC.GREY_LO) & (crop <= SC.GREY_HI)
        ink = crop < SC.BLACK
        import cv2
        near = cv2.dilate(ink.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        assert int(np.count_nonzero(grey & ~near)) == 0, st["key"]


def test_a_sticker_over_the_page_is_rejected_with_its_reason():
    sc = mixed(oversize=True)
    plans = sc.plans()
    big = sc.tags[-1].name
    assert any(w["level"] == "error" and w["text"].startswith("Over the page")
               for w in plans[big].data["warnings"])
    rep = SC.check_scene_sheet(sc, plans, page="letter", mode="tight", date="2026-10-17")
    assert [r["key"] for r in rep["rejected"]] == [big]
    assert "printable area" in rep["rejected"][0]["reason"]
    assert rep["ok"] and len(rep["stickers"]) == len(sc.tags) - 1
