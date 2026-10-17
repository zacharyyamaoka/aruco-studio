"""OpenCV's pose of a plan's tag against the plan's own frame
(TagPlan.frames.opencv): REF tests/test_aruco_frame_pnp.py on plan_tag.

The tag's top view is warped into a pinhole camera 25 deg off its normal
(verify.render.camera_view), OpenCV detects it with its own board and
solvePnP gives the pose (REF tools/verify_aruco_jo_pnp.solve: a single
marker by IPPE_SQUARE on its standard corners; a ChArUco board on its
interpolated corners, or its markers' when it has under 4). The pose must
be the plan's OpenCV frame within 0.1 mm / 0.1 deg.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .detect import board_of, dictionary, parameters
from .render import camera_view, top_view

TOL_MM, TOL_DEG = 0.1, 0.1


def marker_points(board, corners, ids):
    """(object points, image points) of a board's detected markers."""
    known = [int(i) for i in np.asarray(board.getIds()).ravel()]
    objs = board.getObjPoints()
    obj, imgp = [], []
    for c, i in zip(corners, np.asarray(ids).ravel()):
        if int(i) in known:
            obj.append(np.asarray(objs[known.index(int(i))], np.float64).reshape(4, 3))
            imgp.append(np.asarray(c, np.float64).reshape(4, 2))
    if not obj:
        return None, None
    return np.concatenate(obj), np.concatenate(imgp)


def solve(img, spec: dict, K):
    """-> (T_cam_target 4x4 in metres, info) or (None, info). REF
    tools/verify_aruco_jo_pnp.solve."""
    layout = spec.get("layout", "single")
    d, p = dictionary(spec["dictionary"]), parameters()
    info = {"layout": layout}
    if layout == "charuco":
        board = board_of(spec, d)
        cd = cv2.aruco.CharucoDetector(board, cv2.aruco.CharucoParameters(), p)
        ch_c, ch_ids, m_c, m_ids = cd.detectBoard(img)
        info["markers"] = 0 if m_ids is None else len(m_ids)
        info["charuco_corners"] = 0 if ch_ids is None else len(ch_ids)
        if ch_ids is not None and len(ch_ids) >= 4:
            obj, imgp = board.matchImagePoints(ch_c, ch_ids)
        elif m_ids is not None and len(m_ids):
            obj, imgp = marker_points(board, m_c, m_ids)
            info["points_from"] = "marker corners"
        else:
            return None, info
    else:
        det = cv2.aruco.ArucoDetector(d, p)
        corners, ids, _ = det.detectMarkers(img)
        info["markers"] = 0 if ids is None else len(ids)
        if ids is None:
            return None, info
        if layout == "grid":
            board = board_of(spec, d)
            obj, imgp = board.matchImagePoints(corners, ids)
        else:
            want = int(spec["marker_id"])
            hit = [c for c, i in zip(corners, ids.ravel()) if int(i) == want]
            if not hit:
                return None, info
            L = spec["marker_length_m"]
            obj = np.array([[-L / 2, L / 2, 0], [L / 2, L / 2, 0], [L / 2, -L / 2, 0],
                            [-L / 2, -L / 2, 0]], dtype=np.float64)
            imgp = hit[0].reshape(4, 2).astype(np.float64)
            n, rvecs, tvecs, errs = cv2.solvePnPGeneric(obj, imgp, K, None,
                                                        flags=cv2.SOLVEPNP_IPPE_SQUARE)
            errs = np.array(errs).ravel()
            k = int(np.argmin(errs))
            T = np.eye(4)
            T[:3, :3] = cv2.Rodrigues(rvecs[k])[0]
            T[:3, 3] = np.asarray(tvecs[k]).ravel()
            info["points"] = 4
            return T, info
    if obj is None or len(obj) < 4:
        return None, info
    obj = obj.reshape(-1, 3).astype(np.float64)
    imgp = imgp.reshape(-1, 2).astype(np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj, imgp, K, None, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None, info
    proj, _ = cv2.projectPoints(obj, rvec, tvec, K, None)
    info["points"] = len(obj)
    info["reprojection_rms_px"] = round(float(np.sqrt(np.mean(np.sum(
        (proj.reshape(-1, 2) - imgp) ** 2, axis=1)))), 3)
    T = np.eye(4)
    T[:3, :3] = cv2.Rodrigues(rvec)[0]
    T[:3, 3] = tvec.ravel()
    return T, info


def err(A, B):
    """(translation mm, rotation deg) between two 4x4 poses in metres."""
    D = np.linalg.inv(A) @ B
    t = float(np.linalg.norm(A[:3, 3] - B[:3, 3])) * 1000.0
    ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(D[:3, :3]) - 1) / 2))))
    return t, ang


def frame_m(m16):
    """A row-major 4x4 in mm -> numpy, metres."""
    T = np.array(m16, dtype=np.float64).reshape(4, 4)
    T[:3, 3] /= 1000.0
    return T


def pose_check(plan, target=None, px_per_mm: float = None, size=(2000, 1500), **view) -> dict:
    """Render, warp into the camera, solve, compare with frames.opencv."""
    d = plan.to_dict() if hasattr(plan, "to_dict") else plan
    spec = d["marker"]
    ext = max(spec.get("marker_length_m", 0.01), 0.0)
    from .detect import spec_of
    sp = spec_of(d)
    ext_mm = max(sp.extent_m) * 1000.0
    if px_per_mm is None:
        px_per_mm = max(10.0, 0.7 * size[1] / ext_mm)
    r = top_view(d, px_per_mm=px_per_mm, target=target, ss=4)
    o = d["frames"]["opencv"]
    z_mm = o[11]
    img, K, T_cp = camera_view(r, z_mm=z_mm, size=size, extent_mm=ext_mm, **view)
    T_ct, info = solve(img, spec, K)
    rep = {"info": info, "px_per_mm": px_per_mm}
    if T_ct is None:
        rep.update(ok=False, err_mm=None, err_deg=None)
        return rep
    T_cp_m = T_cp.copy()
    T_cp_m[:3, 3] /= 1000.0
    want = T_cp_m @ frame_m(o)
    t_mm, deg = err(want, T_ct)
    rep.update(ok=t_mm < TOL_MM and deg < TOL_DEG, err_mm=t_mm, err_deg=deg)
    return rep
