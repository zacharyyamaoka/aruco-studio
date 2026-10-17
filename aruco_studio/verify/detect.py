"""OpenCV reads a plan: the ids, every marker's corners against the plan's,
a ChArUco board's interpolated corners.

The boards are OpenCV's OWN objects built from the plan's board as built
(`TagPlan.marker`): cv2.aruco.GridBoard / CharucoBoard((cols, rows), ...)
with its ids and legacy flag -- REF tools/verify_aruco_jo_pnp.board_of.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np

from ..core import board as _B
from ..core import markers as _M

DICTS = {n: getattr(cv2.aruco, n) for n in dir(cv2.aruco) if n.startswith("DICT_")}


def dictionary(name: str):
    return cv2.aruco.getPredefinedDictionary(DICTS[name])


def parameters(subpix: bool = True):
    p = cv2.aruco.DetectorParameters()
    if subpix:
        p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return p


def board_of(spec: dict, d=None):
    """OpenCV's board for a TagPlan.marker (core.markers.TagSpec.to_dict)."""
    d = d if d is not None else dictionary(spec["dictionary"])
    layout = spec.get("layout", "single")
    cols, rows, first = int(spec["cols"]), int(spec["rows"]), int(spec["marker_id"])
    if layout == "grid":
        ids = np.arange(first, first + cols * rows, dtype=np.int32)
        return cv2.aruco.GridBoard((cols, rows), spec["marker_length_m"], spec["separation_m"],
                                   d, ids)
    n = (cols * rows) // 2
    ids = np.arange(first, first + n, dtype=np.int32)
    b = cv2.aruco.CharucoBoard((cols, rows), spec["square_length_m"], spec["marker_length_m"],
                               d, ids)
    b.setLegacyPattern(bool(spec.get("legacy")))
    return b


def spec_of(plan: dict):
    return _M.TagSpec.from_dict(plan["marker"], lambda m: None, "plan")


def expected_corners_mm(plan: dict) -> Dict[int, List[tuple]]:
    """{id: TL, TR, BR, BL} (mm, the pattern frame) as the plan builds them."""
    sp = spec_of(plan)
    return {mid: [(x * 1000.0, y * 1000.0) for (x, y) in cs]
            for mid, cs in _B.marker_corners_m(_M.board_spec(sp)).items()}


def expected_charuco_mm(plan: dict) -> List[tuple]:
    """A ChArUco board's inner corners (mm, pattern frame), OpenCV's id order."""
    from ..core import label as _L
    return list(_L.charuco_corners_mm(spec_of(plan)))


def detect(img: np.ndarray, plan: dict) -> dict:
    """{ids, corners {id: [[x, y] x 4]} px, charuco_ids, charuco_corners px}."""
    spec = plan["marker"]
    d = dictionary(spec["dictionary"])
    out = {"ids": [], "corners": {}, "charuco_ids": [], "charuco_corners": []}
    if spec["layout"] == "charuco":
        board = board_of(spec, d)
        cd = cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), parameters())
        ch_c, ch_ids, m_c, m_ids = cd.detectBoard(img)
        if m_ids is not None:
            for c, i in zip(m_c, np.asarray(m_ids).ravel()):
                out["corners"][int(i)] = np.asarray(c).reshape(4, 2).tolist()
        if ch_ids is not None:
            out["charuco_ids"] = [int(i) for i in np.asarray(ch_ids).ravel()]
            out["charuco_corners"] = np.asarray(ch_c).reshape(-1, 2).tolist()
    else:
        det = cv2.aruco.ArucoDetector(d, parameters())
        corners, ids, _rej = det.detectMarkers(img)
        if ids is not None:
            for c, i in zip(corners, np.asarray(ids).ravel()):
                out["corners"][int(i)] = np.asarray(c).reshape(4, 2).tolist()
    out["ids"] = sorted(out["corners"])
    return out


def check(raster, plan: dict) -> dict:
    """The plan read back from its own top view: ids expected / read, the
    worst corner error (px and mm), ChArUco corners interpolated."""
    got = detect(raster.img, plan)
    want = expected_corners_mm(plan)
    errs = []
    for mid, cs in got["corners"].items():
        if mid not in want:
            continue
        for (x, y), (u, v) in zip(cs, want[mid]):
            px = raster.to_px(u, v)
            # detector corners: pixel CENTRES at integers (the raster's at +0.5)
            errs.append(float(np.hypot(x + 0.5 - px[0], y + 0.5 - px[1])))
    rep = {"ids_expected": list(plan["ids"]), "ids_read": got["ids"],
           "missing": sorted(set(plan["ids"]) - set(got["ids"])),
           "extra": sorted(set(got["ids"]) - set(plan["ids"])),
           "corner_err_px": max(errs) if errs else None,
           "corner_err_mm": (max(errs) / raster.px_per_mm) if errs else None}
    if plan["marker"]["layout"] == "charuco":
        exp = expected_charuco_mm(plan)
        rep["charuco_expected"] = len(exp)
        rep["charuco_read"] = len(got["charuco_ids"])
        cerr = []
        for i, (x, y) in zip(got["charuco_ids"], got["charuco_corners"]):
            if 0 <= i < len(exp):
                px = raster.to_px(*exp[i])
                cerr.append(float(np.hypot(x + 0.5 - px[0], y + 0.5 - px[1])))
        rep["charuco_err_px"] = max(cerr) if cerr else None
        rep["charuco_err_mm"] = (max(cerr) / raster.px_per_mm) if cerr else None
    rep["ok"] = (not rep["missing"] and not rep["extra"]
                 and (plan["marker"]["layout"] != "charuco"
                      or rep["charuco_read"] == rep["charuco_expected"]))
    return rep
