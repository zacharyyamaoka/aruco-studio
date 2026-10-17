"""A whole scene, read back: its sheet rasterised (numpy / OpenCV), every
marker found, each where the scene put it."""
from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from ..scene import ids as _ids
from ..scene import sheet as _sheet
from .detect import dictionary, parameters
from .render import SHIFT, Raster

GREY = {"white": 255, "black": 0, "body": 217}


def scene_raster(scene, plans: Optional[dict] = None, px_per_mm: float = 10.0,
                 margin_mm: float = 5.0, ss: int = 2) -> Raster:
    """The scene's sheet as an image (white paper, each tag's top view)."""
    plans = plans if plans is not None else scene.plans()
    its = _sheet.items(scene, plans)
    x0, y0, x1, y1 = _sheet.bounds(its, margin_mm)
    W, H = int(np.ceil((x1 - x0) * px_per_mm)), int(np.ceil((y1 - y0) * px_per_mm))
    s = px_per_mm * ss
    img = np.full((H * ss, W * ss), 255, np.uint8)

    def pts(lp):
        a = np.asarray(lp, np.float64)
        x = (a[:, 0] - x0) * s - 0.5
        y = (y1 - a[:, 1]) * s - 0.5
        return np.round(np.stack([x, y], 1) * (1 << SHIFT)).astype(np.int32)
    order = ("body", "white", "black")
    for it in sorted(its, key=lambda i: order.index(i["colour"])):
        for poly in it["polygons"]:
            # one polygon with its holes: even-odd, on a crop of its box
            loops = [pts(lp) for lp in poly]
            o = loops[0]
            xa = max(0, int(o[:, 0].min() >> SHIFT) - 1)
            ya = max(0, int(o[:, 1].min() >> SHIFT) - 1)
            xb = min(img.shape[1], int(o[:, 0].max() >> SHIFT) + 2)
            yb = min(img.shape[0], int(o[:, 1].max() >> SHIFT) + 2)
            if xb <= xa or yb <= ya:
                continue
            off = np.array([xa << SHIFT, ya << SHIFT], np.int32)
            m = np.zeros((yb - ya, xb - xa), np.uint8)
            cv2.fillPoly(m, [lp - off for lp in loops], 1, lineType=cv2.LINE_8, shift=SHIFT)
            img[ya:yb, xa:xb][m.astype(bool)] = GREY[it["colour"]]
    out = img.astype(np.float32).reshape(H, ss, W, ss).mean(axis=(1, 3))
    return Raster(np.round(out).astype(np.uint8), px_per_mm, x0, y1)


def check_scene(r: Raster, scene, plans: Optional[dict] = None) -> dict:
    """Every marker of every visible tag found, each centre within reach of
    where the scene puts it (mm)."""
    plans = plans if plans is not None else scene.plans()
    want = _ids.marker_centres(scene, plans)
    by_dict = {}
    for w in want:
        by_dict.setdefault(w["dictionary"], []).append(w)
    rows, worst = [], 0.0
    for name, ws in by_dict.items():
        det = cv2.aruco.ArucoDetector(dictionary(name), parameters())
        corners, ids, _ = det.detectMarkers(r.img)
        found = {}
        if ids is not None:
            for c, i in zip(corners, np.asarray(ids).ravel()):
                cx, cy = np.asarray(c).reshape(4, 2).mean(axis=0)
                found.setdefault(int(i), []).append(r.to_mm(cx + 0.5, cy + 0.5))
        for w in ws:
            cands = found.get(w["id"], [])
            if not cands:
                rows.append(dict(w, found=False))
                continue
            d = min(float(np.hypot(x - w["x"], y - w["y"])) for x, y in cands)
            worst = max(worst, d)
            rows.append(dict(w, found=True, err_mm=d))
    missing = [r_ for r_ in rows if not r_["found"]]
    return {"markers": len(rows), "found": len(rows) - len(missing),
            "missing": [(m["tag"], m["id"]) for m in missing], "worst_err_mm": worst,
            "ok": not missing, "rows": rows}
