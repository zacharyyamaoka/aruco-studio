"""Label rule 5 (2026-10-17, M8c.7 / Q1's recommended default, taken while
Zach slept): a label CUT OUT OF THE BLACK strokes at least one line of the
tag's cell rule -- label.LINE_STROKE (1.1) lines, the floor the headless
slice measured (tests/verify/test_slice_check.py) -- so it prints. A label
on the white keeps the nozzle floor. A new tag stores rule 5; a tag that
stores rule 1, 2, 3 or 4 is planned exactly as before (the label goldens
replay in tests/core/test_golden_core.py and test_ref_label_rule1.py).
"""
from __future__ import annotations

import pytest

from aruco_studio.core import form as F
from aruco_studio.core import label as L
from aruco_studio.plan import evaluate as EV
from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T

SQ = 24.0          # the checker square (mm)
MK = 17.0          # the marker in it
LINE = 0.68        # the cell rule's line (the 0.6 mm nozzle's preset)
CELLS = {"rule": 1, "of": "cell", "mm": LINE, "min_mm": 2.0}
FLOOR = round(L.LINE_STROKE * LINE, 6)


def spec(rule, cells=CELLS, layout="charuco", **lab):
    lb = {"on": True, "rule": rule, "content": "id", "nozzle_mm": 0.6}
    lb.update(lab)
    s = {"layout": layout, "mode": "both", "op": "new", "label": lb, "size_auto": False}
    if layout == "charuco":
        s["force"] = [5, 7]
        n = {"size": MK, "square": SQ}
        tgt = T.box(5 * SQ + 40.0, 7 * SQ + 40.0, 0, kind="profile")
    else:
        n = {"size": 40.0}
        tgt = T.box(80.0, 80.0, 0, kind="profile")
    if cells is not None:
        s["cells"] = dict(cells)
    return {"settings": s, "numbers": n, "target": tgt.to_dict()}


def label(rule, **kw):
    p = plan_tag(spec(rule, **kw))
    return p, p.ev["label"]


def test_the_rule_and_the_new_tag():
    assert sorted(L.RULES) == [1, 2, 3, 4, 5] and L.RULE == 2
    assert L.NEW_RULE == L.LINE_RULE == 5 and L.SQUARE_ONLY_RULE == 4
    assert L.RULES[5] == L.RULES[4]                   # the white keeps rule 2's margins
    s = F.new_tag_settings({"layout": "charuco", "label": {"on": True}}, True)
    assert s["label"]["rule"] == 5
    assert EV.cell_line_mm({"cells": CELLS}) == LINE
    assert EV.cell_line_mm({"cells": {"rule": 1, "of": "marker", "mm": 0.5}}) == 0.0
    assert EV.cell_line_mm({}) == 0.0                 # a tag made before the cells


@pytest.mark.parametrize("rule", [1, 2, 3, 4])
@pytest.mark.parametrize("case", [{}, {"cap_mm": 3.0}, {"place": "white"},
                                  {"content": "id_name"}, {"layout": "single"},
                                  {"layout": "single", "cap_mm": 3.0}])
def test_rules_1_to_4_plan_exactly_as_before(rule, case):
    """The cell line is handed to plan_label for every tag; under rules 1-4
    the label is the one it was without it, byte for byte."""
    case = dict(case)
    layout = case.pop("layout", "charuco")
    sp = spec(rule, layout=layout, **case)
    p = plan_tag(sp)
    mk = p.ev["spec"]
    ls = L.LabelSettings.from_dict(sp["settings"]["label"])
    assert ls.rule == rule
    with_line = L.plan_label(mk, ls, line_mm=LINE).to_dict()
    without = L.plan_label(mk, ls).to_dict()
    assert with_line == without
    assert "line_mm" not in p.data["label"]           # the record as before


def test_a_typed_cap_under_the_floor_rule_4_builds_rule_5_refuses():
    _p, lab4 = label(4, cap_mm=3.0)
    assert lab4.kind == "black" and lab4.stroke == pytest.approx(0.6)
    p5, lab5 = label(5, cap_mm=3.0)
    assert lab5.kind == "none" and "rule 5" in lab5.reason, lab5.reason
    assert f"{L.GLYPH_ROWS * FLOOR:.2f} mm letters" in lab5.reason
    assert any(w["field"].startswith("settings.label") for w in p5.data["warnings"])
    _p, at = label(5, cap_mm=round(L.GLYPH_ROWS * FLOOR, 6))
    assert at.kind == "black" and at.stroke == pytest.approx(FLOOR)


def test_auto_never_goes_under_the_floor_on_the_black():
    _p, lab = label(5)
    assert lab.kind == "black" and lab.stroke >= FLOOR - 1e-9
    _p, lab4 = label(4)
    assert lab.texts() == lab4.texts()            # room enough: the same text, its own cap


def test_the_white_keeps_the_nozzle_floor():
    """Black ink on the white printed at 100 % in the slice: no line floor."""
    _p, w5 = label(5, place="white", cap_mm=3.0)
    _p, w4 = label(4, place="white", cap_mm=3.0)
    assert w5.kind == w4.kind == "white" and w5.stroke == pytest.approx(0.6)
    assert [p.rect for p in w5.parts] == [p.rect for p in w4.parts]


def test_a_border_row_too_thin_for_the_floor_moves_the_label_to_the_white():
    """An ArUco marker whose half-module row cannot hold 3.74 mm letters:
    rule 4 cuts the label from the row, rule 5 puts it on the white."""
    _p, lab4 = label(4, layout="single")
    _p, lab5 = label(5, layout="single")
    assert lab4.kind == "black" and lab4.stroke < FLOOR
    assert lab5.kind == "white", (lab5.kind, lab5.notes)


def test_no_cells_no_floor():
    """A tag without a cell rule (or a marker step) has no line: rule 5 is
    rule 4 there."""
    _p, a = label(5, cells=None, cap_mm=3.0)
    _p, b = label(4, cells=None, cap_mm=3.0)
    assert a.kind == b.kind == "black" and [p.rect for p in a.parts] == [p.rect for p in b.parts]


def test_the_record_keeps_the_floor_for_its_copies():
    p, lab = label(5)
    d = lab.to_dict()
    assert d["line_mm"] == LINE and d["settings"]["rule"] == 5
    assert "line_mm" not in d["settings"]          # not a setting: the planner's
    back = L.from_dict(d)
    assert back.settings.line_mm == LINE and L.cut_stroke(back.settings) == FLOOR
    cp = L.relabel(back, p.ev["spec"])
    assert cp.parts and min(q.stroke for q in cp.parts) >= FLOOR - 1e-9
    assert L.check_label(p.ev["spec"], d) == []


def test_the_safety_check_names_a_stroke_under_the_floor():
    p, lab = label(4, cap_mm=3.0)                 # built at 0.6 mm under rule 4
    d = lab.to_dict()
    assert L.check_label(p.ev["spec"], d) == []
    d["settings"]["rule"] = 5
    d["line_mm"] = LINE
    probs = L.check_label(p.ev["spec"], d)
    assert probs and "rule 5" in probs[0], probs
