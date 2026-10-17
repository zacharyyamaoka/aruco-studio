"""The page lint and Auto's cap (2026-10-17, Zach's CF-6, Q2, Q3): a rule-2
inkjet sticker's printable area is its page less its margins (and the
footer and the scale bars' band: what core.sheet.layout_stickers places
in), on a portrait or a landscape sheet, the sticker as it is or turned 90
degrees. Over it: allowed, flagged red (an error Issue with the plan still
built). Auto size never picks a sticker over it, turning 90 degrees when
that fits. New behaviour, no REF: tested by its properties.
"""
from __future__ import annotations

import random

import pytest

from aruco_studio.core import faces as FA
from aruco_studio.core import make as MK
from aruco_studio.core import sheet as SH
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T
from aruco_studio.plan.plan import sticker_size_mm

R2 = {"rule": 2, "by": "sticker", "thickness_mm": 0.1, "perimeter": "marker", "page": "letter",
      "page_margin_mm": 10.0}


def plan(layout, target, size=0.0, make=None, **s):
    return plan_tag({"settings": dict({"layout": layout, "make": dict(make or R2)}, **s),
                     "numbers": {"size": size}, "target": target})


def lints(p):
    return [w for w in p.data["warnings"] if w["level"] == "error"]


def test_the_printable_area_is_the_sheets():
    o = SH.printable_options("letter", 10.0)
    assert o["portrait"] == pytest.approx((195.9, 233.4))       # 279.4 - 20 - footer 4 - bars 19 - 3
    assert o["landscape"] == pytest.approx((259.4, 169.9))
    assert SH.printable_options("a4", 10.0)["portrait"] == pytest.approx((190.0, 251.0))
    # what the sheet places: a sticker just inside each way fits, just over does not
    for page in SH.PAGE_SIZES_MM:
        for name, (aw, ah) in SH.printable_options(page, 10.0).items():
            st = SH.SheetSettings(page=page, landscape=name == "landscape", mode="tight")
            for w, h, ok in ((aw - 0.01, ah - 0.01, True), (aw + 0.5, 10.0, None)):
                f = SH.fit_area(w, h, {name: (aw, ah)}, page, 10.0)
                if ok:
                    assert f["fits"] and f["how"] == name, (page, name)
                    item = SH.PrintItem(key="k", dictionary="DICT_4X4_50", marker_id=0,
                                        marker_length_m=0.01,
                                        cut_mm={"outer": [[-w / 2, -h / 2], [w / 2, -h / 2],
                                                          [w / 2, h / 2], [-w / 2, h / 2]],
                                                "holes": []})
                    assert SH.layout_stickers([item], st).placed, (page, name, w, h)


def test_turned_and_landscape():
    o = SH.printable_options("letter", 10.0)
    assert SH.fit_area(100, 100, o)["how"] == "portrait"
    assert SH.fit_area(230, 100, o)["how"] == "portrait, turned"      # 230 > 195.9 wide: turned
    assert SH.fit_area(250, 150, o)["how"] == "landscape"            # 250 > 233.4: landscape only
    f = SH.fit_area(300, 300, o)
    assert not f["fits"] and f["how"] is None and f["worst_mm"] == pytest.approx(300 - 195.9)


def test_a_typed_size_over_the_page_is_red_and_still_built():
    p = plan("single", T.box(280, 280, 0).to_dict(), size=200)
    assert p.ok and p.data["layers"]
    bad = lints(p)
    assert len(bad) == 1 and bad[0]["field"] == "numbers.size"
    assert bad[0]["text"].startswith("Over the page by ")
    assert p.data["sticker"]["page"]["fits"] is False
    # the same 200 mm fits A3 (its printable 277 x 354 mm): no lint
    a3 = plan("single", T.box(280, 280, 0).to_dict(), size=200, make=dict(R2, page="a3"))
    assert a3.ok and not lints(a3) and a3.data["sticker"]["page"]["fits"]


def test_a_profile_over_the_page_is_red_on_the_perimeter():
    p = plan("single", T.box(300, 300, 0).to_dict(), size=40, make=dict(R2, perimeter="profile"))
    bad = lints(p)
    assert p.ok and len(bad) == 1 and bad[0]["field"] == "settings.make.perimeter"
    m = plan("single", T.box(300, 300, 0).to_dict(), size=40)
    assert m.ok and not lints(m)                                  # Marker: the 53 mm sticker fits


def test_a_rule1_sticker_and_a_3d_tag_have_no_lint():
    for make in ({"rule": 1, "by": "sticker"}, {"rule": 1, "by": "print3d"}):
        p = plan("single", T.box(280, 280, 0).to_dict(), size=200, make=make)
        assert p.ok and not lints(p) and "sticker" not in p.data


def test_auto_is_capped_by_the_page():
    big = T.box(300, 300, 0).to_dict()
    p = plan("single", big)
    w, h = sticker_size_mm(p.data["guides"])
    assert p.ok and not lints(p) and max(w, h) <= 195.9 + 1e-6
    assert any(i["field"] == "numbers.size" and "capped by the page" in i["text"]
               for i in p.data["warnings"])
    # rule 1 is not capped (as before): the face's largest
    r1 = plan("single", big, make={"rule": 1, "by": "sticker"})
    assert r1.data["marker"]["marker_length_m"] > p.data["marker"]["marker_length_m"]


def test_auto_turns_a_board_to_fit():
    """Q3: a long board on a long face prints turned (or landscape) rather
    than shrinking."""
    p = plan("charuco", T.box(400, 150, 0).to_dict())
    assert p.ok and not lints(p)
    f = p.data["sticker"]["page"]
    assert f["fits"] and f["how"] in ("landscape", "portrait, turned", "landscape, turned")
    w, h = sticker_size_mm(p.data["guides"])
    assert max(w, h) > 195.9                       # longer than the portrait width: it turned


def test_auto_leaves_what_fits_alone():
    """When the face's own Auto fits the page, rule 2 picks exactly what
    rule 1 does (the cap only acts over the page)."""
    for key in ("disc4", "dshape", "lshape", "plate_hole"):
        try:
            tgt = T.from_face(key).to_dict()
        except KeyError:
            continue
        for lay in ("single", "grid", "charuco"):
            a = plan(lay, tgt)
            b = plan(lay, tgt, make={"rule": 1, "by": "sticker"})
            assert a.ok == b.ok
            if a.ok:
                assert a.data["marker"]["marker_length_m"] == b.data["marker"]["marker_length_m"]
                assert (a.data["layout"]["cols"], a.data["layout"]["rows"]) == \
                    (b.data["layout"]["cols"], b.data["layout"]["rows"])
                pa, pb = dict(a.data["placement"]), dict(b.data["placement"])
                assert (pa.pop("lift_mm"), pb.pop("lift_mm")) == (0.1, 0.11)    # the frame: t, t + ink
                assert pa == pb


@pytest.mark.parametrize("seed", range(6))
def test_auto_never_picks_a_sticker_over_the_page(seed):
    """A property over random faces, pages, margins and layouts."""
    r = random.Random(1017 + seed)
    for _ in range(12):
        lay = r.choice(["single", "grid", "charuco"])
        w, h = r.uniform(60, 600), r.uniform(60, 600)
        page = r.choice(list(SH.PAGE_SIZES_MM))
        margin = r.choice([0.0, 5.0, 10.0, 20.0])
        tgt = T.box(w, h, 0).to_dict() if r.random() < 0.6 else T.disc(min(w, h) / 2).to_dict()
        p = plan(lay, tgt, make=dict(R2, page=page, page_margin_mm=margin))
        if not p.ok:
            continue
        sw, sh = sticker_size_mm(p.data["guides"])
        fit = MK.page_fit(sw, sh, MK.make_of({"make": dict(R2, page=page,
                                                            page_margin_mm=margin)})[0])
        assert fit["fits"], (lay, w, h, page, margin, sw, sh)
        assert not lints(p)


def test_the_words_and_the_block():
    p = plan("single", T.box(280, 280, 0).to_dict(), size=200)
    blk = p.data["sticker"]
    assert blk["page"]["page"] == "letter" and blk["page"]["margin_mm"] == 10.0
    assert blk["page"]["printable_mm"] == [195.9, 233.4]
    t = lints(p)[0]["text"]
    assert "Letter less 10 mm margins prints 195.9 × 233.4 mm" in t and "still builds" in t
