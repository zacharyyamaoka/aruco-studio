"""The plan's messages fixed after the M3 audit (F2, F7, F8, F9): each on the
field its words name, said once, never a Python repr."""
from __future__ import annotations

import copy

from aruco_studio.plan import plan_tag
from aruco_studio.plan import target as T
from aruco_studio.server import newtag as N

PAL = {x["key"]: x["target"] for x in T.palette(3.0)}


def _new(layout, key="box40"):
    return N.new_spec(layout, copy.deepcopy(PAL[key]))


def _on(p, field):
    return [w for w in p.data["warnings"] if w["field"] == field]


def test_f2_a_typed_count_that_does_not_fit_says_so_under_its_row():
    sp = _new("charuco")
    sp["target"]["kind"] = "profile"
    sp["settings"].update(size_auto=False, force=[5, 2])
    sp["numbers"].update(size=10.0, square=13.0)
    p = plan_tag(sp)
    assert p.ok and (p.data["layout"]["cols"], p.data["layout"]["rows"]) == (3, 3)
    (w,) = _on(p, "settings.force")
    assert w["level"] == "warn"
    assert w["text"] == "5 × 2 does not fit the 40 × 40 mm target at 13.0 mm checkers: using 3 × 3"


def test_f2_a_count_that_fits_says_nothing():
    sp = _new("grid", "box40")
    sp["target"]["kind"] = "profile"
    built = plan_tag(sp).data["layout"]
    sp["settings"].update(size_auto=False, force=[built["cols"], built["rows"]])
    sp["numbers"].update(size=built["marker_mm"])
    assert _on(plan_tag(sp), "settings.force") == []


def test_f2_on_a_face_the_typed_count_is_an_info_line():
    sp = _new("grid", "box40")
    sp["settings"].update(size_auto=False, force=[1, 7])
    sp["numbers"].update(size=8.0)
    (w,) = _on(plan_tag(sp), "settings.force")
    assert w["level"] == "info" and "a face lays out as many as fit" in w["text"]


def test_f7_label_messages_go_under_the_row_they_name_and_once():
    sp = _new("single", "plate_hole")
    sp["settings"]["label"]["on"] = True
    p = plan_tag(sp)
    lab = [w for w in p.data["warnings"] if w["field"].startswith("settings.label")]
    texts = [w["text"].removeprefix("label: ") for w in lab]
    assert any(w["field"] == "settings.label.place" and w["text"].startswith("not on the black")
               for w in lab), lab
    firsts = [t[:48].lower() for t in texts]
    assert len(firsts) == len(set(firsts)), texts          # nothing said twice
    sp = _new("single")
    sp["settings"]["label"].update(on=True, cap_mm=20.0)
    p = plan_tag(sp)
    cap = [w for w in p.data["warnings"] if "cap 20 mm" in w["text"]]
    assert cap and all(w["field"] == "settings.label.cap_mm" for w in cap), cap
    refused = [w for w in p.data["warnings"] if w["text"].startswith("Label not built")]
    assert refused and all(w["field"] == "settings.label.cap_mm" for w in refused), refused


def test_f8_a_bad_cell_is_under_its_mm_field_without_the_dict():
    for mm in (0, -1, 25):
        sp = _new("single")
        sp["settings"]["cells"] = {"rule": 1, "of": "cell", "mm": mm, "min_mm": 2}
        p = plan_tag(sp)
        (w,) = _on(p, "settings.cells.mm")
        assert w["text"] == f"cell {mm:g} mm: 0.01 to 20 mm (read as the legacy 0.5 mm steps)"
        assert "{" not in " ".join(x["text"] for x in p.data["warnings"])
    sp = _new("single")
    sp["settings"]["cells"] = {"rule": 9, "of": "cell", "mm": 0.68}
    ws = [w for w in _on(plan_tag(sp), "settings.cells") if w["level"] == "warn"]
    assert len(ws) == 1 and ws[0]["text"].startswith("cells: rule 9 is not a size grid this version knows")


def test_f9_the_cell_multiple_round_is_under_size():
    sp = _new("single")
    sp["settings"]["cells"] = {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0}
    sp["settings"]["size_auto"] = False
    sp["numbers"]["size"] = 32.0
    p = plan_tag(sp)
    hits = [w for w in p.data["warnings"] if w["text"].startswith("cell multiple: ")]
    assert hits and all(w["field"] == "numbers.size" for w in hits), p.data["warnings"]
