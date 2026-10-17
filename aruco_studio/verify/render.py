"""Rasterise a TagPlan: what the tag looks like from above (the camera's
side), and as a picture warped into a pinhole camera.

The plan's layers are REF's temporary bodies step by step (plan/layers.py),
so this evaluates them the way Fusion would: per slab of z (between every
layer's z ends), each part is the union of its solids, each solid its
steps in order; then the parts combine as `combines` says (the tile joined
to the body or new, the pins joined to the tile, the pocket and the recess
cut, the trim intersected, the pattern a body of its own). The top view is
the colour of the highest material over each pixel.

numpy and OpenCV (cv2.fillPoly) are used here only. Grey levels: 0 black,
255 white; the body under the tag is white (a Black only tag needs a white
part) unless the tag is White only (its white pattern needs a dark part).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

SHIFT = 8                         # cv2.fillPoly's fixed-point bits (1/256 px)
GREY = {"white": 255, "black": 0}


@dataclass
class Raster:
    """An image of the plan and how its pixels map to the pattern frame."""
    img: np.ndarray               # uint8, H x W
    px_per_mm: float
    u0: float                     # the pattern frame's mm at the image's left edge
    v1: float                     # ... and its top edge

    @property
    def A(self) -> np.ndarray:
        """pixel (col, row, 1) (pixel centres at +0.5) -> pattern (u, v, 1) mm."""
        s = 1.0 / self.px_per_mm
        return np.array([[s, 0.0, self.u0], [0.0, -s, self.v1], [0.0, 0.0, 1.0]])

    def to_px(self, u, v):
        return ((u - self.u0) * self.px_per_mm, (self.v1 - v) * self.px_per_mm)

    def to_mm(self, x, y):
        return (self.u0 + x / self.px_per_mm, self.v1 - y / self.px_per_mm)


def _bounds(plan: dict, margin: float, region: str) -> Tuple[float, float, float, float]:
    g = plan["guides"]
    rects = [g["sticker"], g["quiet_ring"]]
    if g.get("tile"):
        rects.append(g["tile"])
    for L in plan["layers"]:
        if L["op"] == "add" and L["step"] == "add":
            for p in L["polygons"]:
                us = [q[0] for q in p["outer"]]
                vs = [q[1] for q in p["outer"]]
                rects.append((min(us), min(vs), max(us), max(vs)))
    if region == "target" and g.get("target"):
        for lp in g["target"]:
            us = [q[0] for q in lp]
            vs = [q[1] for q in lp]
            rects.append((min(us), min(vs), max(us), max(vs)))
    u0 = min(r[0] for r in rects) - margin
    v0 = min(r[1] for r in rects) - margin
    u1 = max(r[2] for r in rects) + margin
    v1 = max(r[3] for r in rects) + margin
    return u0, v0, u1, v1


class _Canvas:
    def __init__(self, u0, v1, w, h, scale):
        self.u0, self.v1, self.w, self.h, self.s = u0, v1, w, h, scale

    def pts(self, poly):
        a = np.asarray(poly, dtype=np.float64)
        x = (a[:, 0] - self.u0) * self.s - 0.5
        y = (self.v1 - a[:, 1]) * self.s - 0.5
        return np.round(np.stack([x, y], axis=1) * (1 << SHIFT)).astype(np.int32)

    def mask(self, polygons, holes=True):
        """The union of polygons with holes, filled at pixel centres."""
        m = np.zeros((self.h, self.w), np.uint8)
        for p in polygons:
            outer = self.pts(p["outer"])
            hs = [self.pts(h) for h in p.get("holes", [])] if holes else []
            if not hs:
                cv2.fillPoly(m, [outer], 1, lineType=cv2.LINE_8, shift=SHIFT)
                continue
            # a polygon with holes: on a crop of its own box, then OR-ed in
            x0 = max(0, int(outer[:, 0].min() >> SHIFT) - 1)
            y0 = max(0, int(outer[:, 1].min() >> SHIFT) - 1)
            x1 = min(self.w, int(outer[:, 0].max() >> SHIFT) + 2)
            y1 = min(self.h, int(outer[:, 1].max() >> SHIFT) + 2)
            if x1 <= x0 or y1 <= y0:
                continue
            off = np.array([x0 << SHIFT, y0 << SHIFT], np.int32)
            sub = np.zeros((y1 - y0, x1 - x0), np.uint8)
            cv2.fillPoly(sub, [outer - off], 1, lineType=cv2.LINE_8, shift=SHIFT)
            for hl in hs:
                cv2.fillPoly(sub, [hl - off], 0, lineType=cv2.LINE_8, shift=SHIFT)
            m[y0:y1, x0:x1] |= sub
        return m.astype(bool)

    def loops_mask(self, loops):
        """Even-odd over loops (a face: its outer loop and its holes)."""
        m = np.zeros((self.h, self.w), np.uint8)
        cv2.fillPoly(m, [self.pts(lp) for lp in loops], 1, lineType=cv2.LINE_8, shift=SHIFT)
        return m.astype(bool)


def _body(plan: dict, target: Optional[dict] = None):
    """(loops in the pattern frame, z0, z1) of the body under the tag
    (TagPlan.body), or None."""
    b = plan.get("body")
    if not b or not b.get("loops"):
        return None
    return b["loops"], b["z"][0], b["z"][1]


def top_view(plan, px_per_mm: float = 20.0, margin_mm: float = 4.0, ss: int = 4,
             target: Optional[dict] = None, region: str = "tag", body_grey: Optional[int] = None,
             background: Optional[int] = None, grid=None) -> Raster:
    """The tag seen from above (+z), `ss` x `ss` samples a pixel. `target`:
    the TagSpec's target dict (the body under it); `region`: "tag" (the tag
    and a margin) or "target" (the whole target). `grid` (u0, v1, W, H):
    these pixels exactly (the image's left edge at u0 mm, its top at v1,
    W x H pixels) instead of the tag's bounds (verify/sheet_check lays the
    plan on a page's pixels)."""
    d = plan.to_dict() if hasattr(plan, "to_dict") else plan
    if not d.get("ok"):
        raise ValueError("a refused plan has nothing to draw: " + "; ".join(d.get("errors") or []))
    mode = d["marker"] and ("white" if any(L["part"] == "pattern" and L["colour"] == "white"
                                           for L in d["layers"]) else "black")
    if body_grey is None:
        body_grey = 0 if mode == "white" else 255
    if background is None:
        background = 0 if mode == "white" else 255
    if grid is not None:
        u0, v1, W, H = float(grid[0]), float(grid[1]), int(grid[2]), int(grid[3])
    else:
        u0, v0, u1, v1 = _bounds(d, margin_mm, region)
        W = int(math.ceil((u1 - u0) * px_per_mm))
        H = int(math.ceil((v1 - v0) * px_per_mm))
    cv = _Canvas(u0, v1, W * ss, H * ss, px_per_mm * ss)
    layers = d["layers"]
    masks = [cv.mask(L["polygons"]) for L in layers]
    body = _body(d, target)
    body_mask = cv.loops_mask(body[0]) if body else None
    zs = sorted({z for L in layers for z in L["z"]} | ({body[1], body[2]} if body else set()))
    slabs = [(a, b) for a, b in zip(zs, zs[1:]) if b - a > 1e-9]
    comb = {c["part"]: c for c in d["combines"]}
    joined = comb.get("tile", {}).get("op") == "join"
    out = np.full((H * ss, W * ss), -1, np.int16)
    for (a, b) in reversed(slabs):
        zm = (a + b) / 2.0
        parts: Dict[str, np.ndarray] = {}
        solids: Dict[Tuple[str, int], np.ndarray] = {}
        for L, m in zip(layers, masks):
            if not (L["z"][0] < zm < L["z"][1]):
                continue
            k = (L["part"], L["solid"])
            cur = solids.get(k)
            if L["step"] == "add":
                solids[k] = m.copy() if cur is None else (cur | m)
            elif cur is not None:
                solids[k] = cur & ~m
        for (part, _k), m in solids.items():
            parts[part] = m if part not in parts else (parts[part] | m)
        B = body_mask.copy() if body and body[1] < zm < body[2] else np.zeros_like(out, bool)
        Wt = np.zeros_like(B)
        P = np.zeros_like(B)
        for part in d["parts"]:
            r = parts.get(part)
            if r is None:
                continue
            c = comb.get(part, {})
            if part in ("tile", "sticker"):           # sticker / ink: core.make (M6a)
                Wt |= r
            elif part == "pin":
                Wt |= r
            elif part == "pocket":
                Wt &= ~r
                if c.get("into") == "body":
                    B &= ~r
            elif part in ("pattern", "ink"):
                P |= r
            elif part == "recess":
                B &= ~r
                if joined:
                    Wt &= ~r
            elif part == "trim":
                B &= r
                if joined:
                    Wt &= r
        pat_grey = 0 if mode == "black" else 255
        free = out < 0
        out[free & P] = pat_grey
        free = out < 0
        out[free & Wt] = 255
        free = out < 0
        out[free & B] = body_grey
    out[out < 0] = background
    img = out.astype(np.float32).reshape(H, ss, W, ss).mean(axis=(1, 3))
    return Raster(np.round(img).astype(np.uint8), px_per_mm, u0, v1)


# ------------------------------------------------------------ the camera

def look_at_R(eye, target, up):
    """World -> camera rotation, OpenCV camera (+x right, +y down, +z
    forward). REF tools/verify_aruco_jo_pnp.look_at_R."""
    z = np.asarray(target, float) - np.asarray(eye, float)
    z /= np.linalg.norm(z)
    u = np.asarray(up, float)
    y = -(u - (u @ z) * z)
    y /= np.linalg.norm(y)
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=0)


def camera_view(r: Raster, z_mm: float = 0.0, size=(2000, 1500), fov_deg=30.0, tilt_deg=25.0,
                azimuth_deg=35.0, roll_deg=10.0, centre=(0.0, 0.0), extent_mm=None):
    """The top view as a camera 25 deg off the face's normal sees it (REF
    test_aruco_frame_pnp.render: from 35 deg round, rolled 10 deg). The
    raster lies on the plane z = z_mm of the pattern frame. -> (image, K,
    T_cam_pattern: 4x4, mm)."""
    w, h = size
    fov = math.radians(fov_deg)
    f = (h / 2.0) / math.tan(fov / 2.0)
    K = np.array([[f, 0, w / 2.0], [0, f, h / 2.0], [0, 0, 1.0]])
    if extent_mm is None:
        hh, ww = r.img.shape
        extent_mm = max(ww, hh) / r.px_per_mm
    dist = extent_mm / (0.7 * 2.0 * math.tan(fov / 2.0))
    XB, YB, ZB = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])
    t, a, rr = (math.radians(v) for v in (tilt_deg, azimuth_deg, roll_deg))
    c = np.array([centre[0], centre[1], z_mm])
    side = math.cos(a) * YB + math.sin(a) * XB
    eye = c + dist * (math.cos(t) * ZB - math.sin(t) * side)
    R = look_at_R(eye, c, math.cos(rr) * YB + math.sin(rr) * XB)
    p0 = np.array([0.0, 0.0, z_mm])
    Hp = K @ np.column_stack([R @ XB, R @ YB, R @ (p0 - eye)])
    # the raster's pixel centres: (col + 0.5, row + 0.5) -> A
    A = r.A @ np.array([[1.0, 0, 0.5], [0, 1.0, 0.5], [0, 0, 1.0]])
    img = cv2.warpPerspective(r.img, Hp @ A, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, -R @ eye
    return img, K, T
