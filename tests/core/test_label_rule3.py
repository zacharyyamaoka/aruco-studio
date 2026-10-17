"""M6a.5: label rule 3 -- a ChArUco label placed by hand in ANY black square
builds there, checked against that square; under rule 2 the same spot is
refused as before; nothing stored changes (the label goldens replay in
tests/core/test_golden_core.py and test_ref_label_rule1.py)."""
from __future__ import annotations

import pytest

from aruco_studio.core import label as L
from aruco_studio.plan import fields as FL
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T

SQ = 18.0          # the checker square (mm)
MK = 13.0          # the marker in it


def spec(rule, x=None, y=None):
    lab = {"on": True, "rule": rule, "place": "black", "content": "id", "nozzle_mm": 0.4}
    if x is not None:
        lab.update(position="manual", x_mm=x, y_mm=y)
    return {"settings": {"layout": "charuco", "mode": "both", "op": "new", "force": [5, 7],
                         "label": lab, "size_auto": False},
            "numbers": {"size": MK, "square": SQ},
            "target": T.box(5 * SQ, 7 * SQ, 0, kind="profile").to_dict()}


def board():
    p = plan_tag(spec(3))
    assert p.ok, p.data["errors"]
    mk = p.ev["spec"]
    assert (mk.cols, mk.rows) == (5, 7), (mk.cols, mk.rows)
    return p, mk


def squares():
    _p, mk = board()
    return L.charuco_black_squares(mk)


def test_the_rules():
    assert sorted(L.RULES) == [1, 2, 3, 4, 5] and L.RULE == 2
    assert L.NEW_RULE == 5                            # 2026-10-17: rule 5 (test_label_rule5.py)
    assert L.RULES[3] == L.RULES[2] == L.RULES[4] == L.RULES[5]   # the white's rule is rule 2's


def test_the_black_squares_of_a_5_x_7_board():
    sqs = squares()
    assert len(sqs) == 18                             # 35 squares, 18 black (top-left black)
    _p, mk = board()
    assert sqs[0] == pytest.approx(L.charuco_square(mk))
    for sq in sqs:
        assert sq[2] - sq[0] == pytest.approx(SQ) and sq[3] - sq[1] == pytest.approx(SQ)


@pytest.mark.parametrize("k", range(18))
def test_a_manual_spot_in_each_black_square(k):
    """Rule 3 builds the label in square k; rule 2 builds only the top-left."""
    sq = squares()[k]
    cx, cy = (sq[0] + sq[2]) / 2.0, (sq[1] + sq[3]) / 2.0
    p3 = plan_tag(spec(3, cx, cy))
    lab = p3.data["label"]
    assert p3.ok and lab["kind"] == "black", [w for w in p3.data["warnings"]
                                              if w["field"].startswith("settings.label")]
    for part in lab["parts"]:
        r = part["rect"]
        assert sq[0] < r[0] and r[2] < sq[2] and sq[1] < r[1] and r[3] < sq[3]
    assert not any(w["level"] == "error" for w in p3.data["warnings"])
    p2 = plan_tag(spec(2, cx, cy))
    if k == 0:
        assert p2.data["label"]["kind"] == "black"
        assert p2.data["label"]["parts"][0]["rect"] == lab["parts"][0]["rect"]
    else:
        assert p2.data["label"]["kind"] == "none"     # refused as today: the top-left only
        assert any(w["field"].startswith("settings.label") and w["level"] == "error"
                   for w in p2.data["warnings"])


def test_auto_still_picks_the_top_left_square():
    p3, p2 = plan_tag(spec(3)), plan_tag(spec(2))
    assert p3.data["label"]["parts"][0]["rect"] == p2.data["label"]["parts"][0]["rect"]
    sq = squares()[0]
    r = p3.data["label"]["parts"][0]["rect"]
    assert sq[0] < r[0] < r[2] < sq[2]


def test_rule_3_still_keeps_clear_of_the_corners():
    sq = squares()[5]
    # a spot near the square's corner: the chessboard corner is too near
    p = plan_tag(spec(3, sq[0] + 1.0, sq[3] - 1.0))
    assert p.data["label"]["kind"] == "none"


def test_a_label_off_its_square_warns_on_a_board_row_or_the_white():
    s = spec(3)
    s["settings"]["label"]["row"] = "bottom"
    p = plan_tag(s)
    assert any(w["field"] == "settings.label.row" and w["level"] == "warn"
               and "black square" in w["text"] for w in p.data["warnings"])
    s = spec(3)
    s["settings"]["label"]["place"] = "white"
    p = plan_tag(s)
    assert any(w["field"] == "settings.label.place" and "black square" in w["text"]
               for w in p.data["warnings"])


def test_the_form_offers_a_charuco_board_a_black_square_only():
    rows = {r["path"]: r for r in FL.fields()}
    place = rows["settings.label.place"]
    assert place["choices_by_layout"]["charuco"] == [{"value": "black",
                                                      "label": "In a black square"}]
    assert rows["settings.label.row"]["hidden_layouts"] == ["charuco"]
    assert rows["settings.label.side"]["hidden_layouts"] == ["charuco"]
    assert 3 in [c["value"] for c in rows["settings.label.rule"]["choices"]]
    assert rows["settings.label.rule"]["new"] == L.NEW_RULE == 5


def test_the_label_goldens_keep_their_rules():
    """No stored label changes: the label golden's records are rules 1 and 2."""
    from _golden import load
    assert {c["out"]["record"]["settings"]["rule"] for c in load("label")["cases"]} == {1, 2}
