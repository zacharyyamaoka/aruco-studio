"""plan.auto.auto_still_fits: REF _check_auto as a pure comparison (audit C5).

On golden cases made with Auto, the number Auto built is "stored" back:
Auto still fits (OK on an unchanged dialog changes nothing). A stored
number Auto would not pick reads Auto OFF with REF's note.
"""
import pytest

from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.plan.auto import auto_still_fits

from _evaluate_golden import cases

AUTO = [c for c in cases("matrix") if c["in"]["settings"].get("size_auto")
        and not float(c["in"]["numbers"].get("size") or 0)][:12]


def _base(case):
    b = case.get("base")
    return tuple(b) if b else None


def _built(spec, base):
    p = plan_tag(spec, base=base)
    assert p.ok, p.data["errors"]
    m = p.data["marker"]
    return m["marker_length_m"] * 1000.0, (m.get("square_length_m") or 0.0) * 1000.0


@pytest.mark.parametrize("case", AUTO, ids=[c["id"] for c in AUTO])
def test_the_number_auto_built_keeps_auto_on(case):
    spec = TagSpec.from_dict(case["in"])
    base = _base(case)
    if not plan_tag(spec, base=base).ok:
        pytest.skip("a refused case")
    size, square = _built(spec, base)
    keep, note = auto_still_fits(spec, size, square, base=base)
    assert keep and note == ""


def test_a_number_auto_would_not_pick_shows_auto_off_with_refs_note():
    case = next(c for c in AUTO if c["in"]["settings"]["layout"] == "single"
                and plan_tag(TagSpec.from_dict(c["in"]), base=_base(c)).ok)
    spec = TagSpec.from_dict(case["in"])
    size, _sq = _built(spec, _base(case))
    keep, note = auto_still_fits(spec, round(size * 0.8, 3), 0.0, base=_base(case))
    assert not keep
    assert note.startswith("Auto size would build ") and "(Auto size at creation)" in note
    assert note.endswith("tick Auto size to re-fit it")


def test_auto_cases_were_found():
    assert len(AUTO) >= 6
