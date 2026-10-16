"""Golden replay (M1.12): restructure_plan over every pair of node structures.

The golden ran REF ArucoMarkers/aruco_restructure.py's own has_combine /
restructure_plan (exec'd from the pinned blob; the module imports adsk, so
it is never imported).
"""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import restructure as R, slabs as S

DOC = load("restructure")


@pytest.mark.parametrize("case", DOC["cases"], ids=[f"{i:03d}" for i in range(len(DOC["cases"]))])
def test_restructure_golden(case):
    (op_o, p_o), (op_n, p_n) = case["in"]["old"], case["in"]["new"]
    d = diff(case["out"], GC.norm(GC.restructure_run(((op_o, p_o), (op_n, p_n)), R)))
    assert not d, d


def test_restructure_golden_has_every_pair():
    sts = GC.structures(S)
    assert len(DOC["cases"]) == len(sts) ** 2
    assert list(R.ROLE_ORDER) == DOC["args"]["role_order"]
