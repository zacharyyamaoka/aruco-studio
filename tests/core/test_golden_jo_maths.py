"""Golden replay (M1.12): the Joint Origin maths (goldens/jo_maths.json).

The golden ran REF aruco_tags._place_joint_origin's first solve on 202
frames (exec'd from the pinned blob; _jo_probe gave the base frame). The
replay is exact, so within 1e-9 too.
"""
import golden_cases as GC
import pytest
from _golden import diff, load

from aruco_studio.core import geometry as GEO

DOC = load("jo_maths")
IDS = [f"{i:03d}" for i in range(len(DOC["cases"]))]


@pytest.mark.parametrize("case", DOC["cases"], ids=IDS)
def test_jo_maths_golden(case):
    base, target = case["in"]["base"], case["in"]["target"]
    a, off, flip = GEO.jo_decompose(base, target)
    got = GC.norm({"angle": a, "offsets": off, "flip": flip, "added": [[a, off, flip]],
                   "frame_error": GEO._frame_error(base, target),
                   "solve3": GEO._solve3(base[1:], target[0]),
                   "rot": [GEO._rot(base[1], base[3], d) for d in (0.0, 33.0, -90.0)]})
    d = diff(case["out"], got)
    assert not d, d


def _on_base(c):
    """A target a Joint Origin on this geometry can reach: z parallel."""
    return abs(abs(sum(p * q for p, q in zip(c["in"]["base"][3], c["in"]["target"][3]))) - 1) < 1e-12


ON_BASE = [c for c in DOC["cases"] if _on_base(c)]


def test_jo_cases_include_reachable_targets():
    assert len(ON_BASE) >= 50


@pytest.mark.parametrize("case", ON_BASE, ids=[f"{i:03d}" for i in range(len(ON_BASE))])
def test_jo_compose_round_trip(case):
    """jo_compose(jo_decompose(t)) == t when the target can sit on the base
    (z parallel): position 1e-9, axes 1e-6 rad."""
    base, target = case["in"]["base"], case["in"]["target"]
    a, off, flip = GEO.jo_decompose(base, target)
    pos, ang = GEO._frame_error(GEO.jo_compose(base, a, off, flip), target)
    assert pos < 1e-9 and ang < 1e-6, (pos, ang)
