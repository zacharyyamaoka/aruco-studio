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


def _random_frames(n, seed):
    """n random (base, target) pairs a Joint Origin can reach: the target on
    the base's plane (z parallel or flipped), any angle, any in-plane offset,
    plus a lift along z."""
    import math
    import random
    rnd = random.Random(seed)

    def unit(v):
        s = math.sqrt(sum(c * c for c in v))
        return [c / s for c in v]
    out = []
    for _ in range(n):
        z = unit([rnd.gauss(0, 1) for _ in range(3)])
        a = unit([rnd.gauss(0, 1) for _ in range(3)])
        x = unit([a[i] - sum(a[j] * z[j] for j in range(3)) * z[i] for i in range(3)])
        y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
        o = [rnd.uniform(-50, 50) for _ in range(3)]
        t = rnd.uniform(-math.pi, math.pi)
        s = rnd.choice((1.0, -1.0))
        tx = [math.cos(t) * x[k] + math.sin(t) * y[k] for k in range(3)]
        ty = [s * (-math.sin(t) * x[k] + math.cos(t) * y[k]) for k in range(3)]
        tz = [s * c for c in z]
        u, v, w = rnd.uniform(-30, 30), rnd.uniform(-30, 30), rnd.uniform(-5, 5)
        to = [o[k] + u * x[k] + v * y[k] + w * z[k] for k in range(3)]
        out.append(([o, x, y, z], [to, tx, ty, tz]))
    return out


def test_jo_compose_inverts_jo_decompose_on_2000_random_frames():
    """ST-T-JO-1: jo_compose(jo_decompose(f)) == f within 1e-9, flipped frames included."""
    worst = (0.0, 0.0)
    flips = 0
    for base, target in _random_frames(2000, 20261016):
        a, off, flip = GEO.jo_decompose(base, target)
        flips += flip
        pos, ang = GEO._frame_error(GEO.jo_compose(base, a, off, flip), target)
        worst = (max(worst[0], pos), max(worst[1], ang))
    assert worst[0] < 1e-9 and worst[1] < 1e-7, worst
    assert 800 < flips < 1200
