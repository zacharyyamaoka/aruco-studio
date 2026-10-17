"""TagPlan.frames.opencv is OpenCV's frame of the tag as built: in the
pattern frame it is markers.detector_frame (core.board.opencv_frame for a
board, lifted by raise) on the plan's surface, and core.origin's
opencv_in_layout says the same for every layout x turn."""
from __future__ import annotations

import pytest

from aruco_studio.core import markers as M
from aruco_studio.core import origin as OR
from aruco_studio.plan import TagSpec, plan_tag
from aruco_studio.plan import target as T

CASES = [("single", {"size": 28.0}, None, 40, 40), ("grid", {"size": 14.0}, [3, 2], 60, 40),
         ("charuco", {"size": 13.5, "square": 18.0}, [5, 4], 100, 80)]


@pytest.mark.parametrize("layout,numbers,force,w,h", CASES)
@pytest.mark.parametrize("turn", [0, 90, 180, 270])
@pytest.mark.parametrize("mode", ["both", "black", "white"])
def test_frames_opencv_is_the_detector_frame(layout, numbers, force, w, h, turn, mode):
    p = plan_tag(TagSpec(settings={"layout": layout, "mode": mode, "turn": turn, "origin_v": 2,
                                   "force": force}, numbers=numbers,
                         target=T.box(w, h, 3)))
    assert p.ok, p.data["errors"]
    sp = M.TagSpec.from_dict(p.data["marker"], lambda m: None, "t")
    D = M.detector_frame(sp)                        # metres, the tag frame (on the surface)
    want = list(D)
    for i in (3, 7, 11):
        want[i] *= 1000.0
    want[11] += p.data["slabs"]["surface"]           # the tag frame sits on the surface
    got = p.data["frames"]["opencv"]
    assert max(abs(a - b) for a, b in zip(got, want)) < 1e-9, (got, want)
    assert abs(p.data["frames"]["detector_z_mm"] - got[11]) < 1e-9
    # core.origin's words for the same corner, as laid out
    W, H = (v * 1000.0 for v in sp.extent_m)
    if turn % 180:
        W, H = H, W
    (ou, ov), xd, yd, zs = OR.opencv_in_layout(layout, turn, W, H)
    pz = p.data["frames"]["pattern_in_target"]
    # the pattern's x in the target frame is the layout's x turned by `turn`
    import math
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    assert abs(pz[0] - c) < 1e-9 and abs(pz[4] - s) < 1e-9
