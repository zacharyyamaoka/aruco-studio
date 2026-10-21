"""A camera looks at a plan: the online Studio's "Verify accuracy"
(web_verify.verify / readable, contract.ts ViewConditions).

The camera is a pinhole: `resolution` (W, H) px, `hfov_deg` across W, so

    f_px = (W / 2) / tan(hfov / 2)          the focal length in px
    px_per_mm = f_px / distance_mm          on a face head on at that distance
    px_per_cell = cell_mm * f_px / distance_mm

The marker's centre (its sticker's) sits on the optical axis at
`distance_mm`; `tilt_deg` turns the marker about its own x, `yaw_deg` about
its own y. The plan's top view (render.top_view, the layers as built: labels,
corner marks, grids, ChArUco) is warped into the sensor by the homography of
that pose, rendered `ss` x `ss` finer and box-filtered down (INTER_AREA) the
way a pixel integrates light. Only the sensor's crop round the marker is
drawn (white beyond it, as the sticker's surround); OpenCV's perimeter
limits are scaled to the crop so it reads exactly as on the whole sensor.

Then, all seeded by `seed`: dirt / finger blobs on the marker (`occlusion`,
the share of the marker's area covered), a specular patch (`glare`), a
Gaussian blur (`blur_px`, sigma in sensor px) and sensor grain (`noise`,
NOISE_SIGMA grey levels at 1). OpenCV's own ArucoDetector / CharucoDetector
reads it (detect.detect) and solvePnP poses it (pnp.solve) against the
plan's OpenCV frame (TagPlan.frames.opencv).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from . import detect as _det
from . import pnp as _pnp
from .render import Raster, _Canvas, top_view

CROP_MARGIN_PX = 32           # sensor px of white round the marker (> the 23 px threshold window)
SS_MAX = 4                    # supersampling of the crop, per axis
SS_BUDGET = 6_000_000         # supersampled crop pixels at most
RASTER_OVER = 1.5             # the top view this much finer than the supersampled sensor
RASTER_MAX_PX = 3000          # the top view's longest side at most
NOISE_SIGMA = 50.0            # grey levels of sensor grain at noise = 1
GLARE_SIZE = 0.3              # the specular patch's sigma, x the marker's size on the sensor
DIRT_GREY = (60, 170)         # a blob's grey level, uniform in this range
DIRT_SIZE = (0.08, 0.25)      # a blob's semi-axes, x the marker area's side
MAX_TILT = 85.0
PERIMETER_RATE = 0.03         # OpenCV's default minMarkerPerimeterRate (x the image's longest side)


@dataclass
class Cam:
    """A pinhole camera: OpenCV's (x right, y down, z forward)."""
    distance_mm: float
    width: int
    height: int
    hfov_deg: float

    @classmethod
    def of(cls, d: dict) -> "Cam":
        w, h = d["resolution"]
        return cls(float(d["distance_mm"]), int(w), int(h), float(d["hfov_deg"]))

    @property
    def f_px(self) -> float:
        return (self.width / 2.0) / math.tan(math.radians(self.hfov_deg) / 2.0)

    @property
    def px_per_mm(self) -> float:
        """Sensor px per mm on a face head on at the distance."""
        return self.f_px / self.distance_mm

    @property
    def K(self) -> np.ndarray:
        f = self.f_px
        # pixel centres at integers (OpenCV): the sensor's centre is (W-1)/2
        return np.array([[f, 0.0, (self.width - 1) / 2.0], [0.0, f, (self.height - 1) / 2.0],
                         [0.0, 0.0, 1.0]])


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]])


def marker_pose(cam: Cam, tilt_deg: float, yaw_deg: float, centre) -> np.ndarray:
    """T_cam_pattern (4x4, mm): the pattern frame (x right, y up, z out of the
    face, toward the camera) with `centre` (u, v, z mm) on the optical axis
    at the distance, turned by tilt about its x, then yaw about its y."""
    t = math.radians(max(-MAX_TILT, min(MAX_TILT, float(tilt_deg))))
    y = math.radians(max(-MAX_TILT, min(MAX_TILT, float(yaw_deg))))
    R = np.diag([1.0, -1.0, -1.0]) @ _rx(t) @ _ry(y)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.array([0.0, 0.0, cam.distance_mm]) - R @ np.asarray(centre, float)
    return T


def plane_h(K: np.ndarray, T: np.ndarray, z_mm: float) -> np.ndarray:
    """The homography pattern (u, v, 1) on the plane z = z_mm -> sensor px."""
    R, t = T[:3, :3], T[:3, 3]
    return K @ np.column_stack([R[:, 0], R[:, 1], R[:, 2] * z_mm + t])


def _project(H: np.ndarray, pts) -> np.ndarray:
    a = np.asarray(pts, np.float64).reshape(-1, 2)
    p = H @ np.vstack([a.T, np.ones(len(a))])
    return (p[:2] / p[2]).T


# ------------------------------------------------------------ the scene

@dataclass
class Scene:
    """What the plan puts in front of the camera, in the pattern frame (mm)."""
    plan: dict
    bounds: Tuple[float, float, float, float]      # u0, v0, u1, v1: sticker + label
    centre: Tuple[float, float, float]             # on the optical axis
    area: Tuple[float, float, float, float]        # the marker area (the ink's box): occlusion
    label: Optional[dict] = None                   # {text, at (u, v), height_mm, dir (du, dv), ...}


def _ink_box(d: dict):
    us, vs = [], []
    for L in d["layers"]:
        if L["step"] == "add" and L.get("colour") == "black":
            for p in L["polygons"]:
                for q in p["outer"]:
                    us.append(q[0])
                    vs.append(q[1])
    if not us:
        return tuple(d["guides"]["sticker"])
    return min(us), min(vs), max(us), max(vs)


def scene_of(d: dict, label: Optional[dict] = None) -> Scene:
    """`label`: {text, at (u, v) mm in the pattern frame, height_mm (cap),
    dir (du, dv) the text's baseline} -- plain text beside the marker or on
    it; optional: "colour" "white" (knocked out of the black: the letters
    are paper), "widths" each line's width (mm: Helvetica's, the page's),
    "polygons" the pixel font's ink [{outer, holes}] in the pattern frame
    (drawn as they are instead of the text)."""
    s = d["guides"]["sticker"]
    u0, v0, u1, v1 = s
    z0 = float(d["frames"]["opencv"][11])
    if label:
        for (x, y) in label_corners(label):
            u0, v0, u1, v1 = min(u0, x), min(v0, y), max(u1, x), max(v1, y)
    return Scene(d, (u0, v0, u1, v1), ((s[0] + s[2]) / 2.0, (s[1] + s[3]) / 2.0, z0),
                 _ink_box(d), label)


def label_corners(label: dict):
    (cu, cv), (du, dv) = label["at"], label["dir"]
    n = math.hypot(du, dv) or 1.0
    du, dv = du / n, dv / n
    # room for Hershey's letters, which run wider than the Helvetica width given
    hw = 0.65 * label["width_mm"] + 0.5 * label["height_mm"]
    # a multi-line label is (lines - 1) pitches of 1.4 caps taller (_draw_label)
    lines = max(1, len(str(label["text"]).split("\n")))
    hh = label["height_mm"] + (lines - 1) * 0.7 * label["height_mm"]
    return [(cu + sx * hw * du - sy * hh * dv, cv + sx * hw * dv + sy * hh * du)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _draw_label(r: Raster, label: dict):
    """The label's text (Hershey simplex, black) drawn on the top view at
    its cap height, along its baseline. A multi-line label draws each line
    stacked 1.4 caps apart around the label's centre, first line on top, as
    the core lays it out (rect_fill: (1 + LINE_GAP) x cap). Colour "white":
    the letters are paper knocked out of the black (Zach, 2026-10-20: the
    text in the marker's border row), so they lighten what is under them.
    "widths": each line stretched to the page's width, so the letters cover
    the marker where the print does. "polygons": the pixel font, as drawn."""
    white = label.get("colour") == "white"
    if label.get("polygons"):
        cv = _Canvas(r.u0, r.v1, r.img.shape[1], r.img.shape[0], r.px_per_mm)
        m = cv.mask(label["polygons"])
        r.img[m] = 255 if white else 0
        return
    # WHY one putText per line (2026-10-18): Hershey draws "\n" as "?", so a
    # two-line label rendered as one line with a "?" in the middle.
    lines = [t for t in str(label["text"]).split("\n")]
    cap_mm = float(label["height_mm"])
    if not any(lines) or cap_mm * r.px_per_mm < 1.0:
        return
    widths = label.get("widths") or [None] * len(lines)
    (cu, cv), (du, dv) = label["at"], label["dir"]
    n = math.hypot(du, dv) or 1.0
    du, dv = du / n, dv / n
    upu, upv = -dv, du                               # the baseline's normal, up the text
    pitch = 1.4 * cap_mm
    for k, text in enumerate(lines):
        off = ((len(lines) - 1) / 2.0 - k) * pitch
        if text:
            _draw_line(r, text, cap_mm, (cu + upu * off, cv + upv * off), (du, dv), white,
                       widths[k] if k < len(widths) else None)


def _draw_line(r: Raster, text: str, cap_mm: float, at, d, white: bool = False,
               width_mm: Optional[float] = None):
    cap_px = cap_mm * r.px_per_mm
    (_w1, h1), _b = cv2.getTextSize("H", cv2.FONT_HERSHEY_SIMPLEX, 1.0, 1)
    scale = cap_px / float(h1)
    thick = max(1, int(round(cap_px * 0.12)))
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    pad = thick + 2
    patch = np.full((th + base + 2 * pad, tw + 2 * pad), 255, np.uint8)
    cv2.putText(patch, text, (pad, pad + th), cv2.FONT_HERSHEY_SIMPLEX, scale, 0, thick,
                cv2.LINE_AA)
    (cu, cv), (du, dv) = at, d
    # patch px -> pattern mm: its middle at the line's centre, x along the baseline
    k = 1.0 / r.px_per_mm                          # the patch is drawn at the top view's scale
    kx = k if not width_mm else float(width_mm) / max(1.0, float(tw))   # along the baseline
    px0, py0 = patch.shape[1] / 2.0, (pad + th / 2.0)
    P2M = np.array([[kx * du, k * dv, 0.0], [kx * dv, -k * du, 0.0], [0.0, 0.0, 1.0]])
    P2M[:2, 2] = np.array([cu, cv]) - P2M[:2, :2] @ np.array([px0, py0])
    M2R = np.linalg.inv(r.A) @ np.eye(3)
    M2R[:2, 2] -= 0.5                              # raster centres at +0.5 -> indices
    A = (M2R @ P2M)[:2]
    h, w = r.img.shape
    warped = cv2.warpAffine(patch, A, (w, h), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    if white:
        np.maximum(r.img, 255 - warped, out=r.img)
    else:
        np.minimum(r.img, warped, out=r.img)


def _occlude(r: Raster, area, share: float, rng) -> float:
    """Dirt / finger blobs on the top view until `share` of the marker area
    is covered. -> the share covered."""
    if share <= 0:
        return 0.0
    share = min(1.0, share)
    x0, y0 = r.to_px(area[0], area[3])
    x1, y1 = r.to_px(area[2], area[1])
    x0, y0, x1, y1 = (int(math.floor(x0)), int(math.floor(y0)), int(math.ceil(x1)),
                      int(math.ceil(y1)))
    hh, ww = r.img.shape
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(ww, x1), min(hh, y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
    side = math.sqrt(float((x1 - x0) * (y1 - y0)))
    got = 0.0
    for _ in range(400):
        cx = rng.uniform(0, x1 - x0)
        cy = rng.uniform(0, y1 - y0)
        a = rng.uniform(*DIRT_SIZE) * side
        b = rng.uniform(*DIRT_SIZE) * side
        ang = rng.uniform(0, 180.0)
        grey = int(rng.integers(DIRT_GREY[0], DIRT_GREY[1] + 1))
        c = (int(round(cx)), int(round(cy)))
        ax = (max(1, int(round(a))), max(1, int(round(b))))
        cv2.ellipse(mask, c, ax, ang, 0, 360, 1, -1)
        cv2.ellipse(r.img[y0:y1, x0:x1], c, ax, ang, 0, 360, grey, -1, cv2.LINE_AA)
        got = float(mask.mean())
        if got >= share:
            break
    return got


# ------------------------------------------------------------ the view

@dataclass
class View:
    img: np.ndarray               # the sensor's crop, uint8
    K: np.ndarray                 # the crop's camera matrix
    T_cam_pattern: np.ndarray     # 4x4 mm
    H: np.ndarray                 # pattern mm -> crop px
    offset: Tuple[int, int]       # the crop's top-left on the sensor
    clipped: bool                 # the marker runs off the sensor
    perimeter_scale: float        # the sensor's longest side / the crop's
    occluded: float


def simulate(scene: Scene, cam: Cam, view: dict, cache: Optional[dict] = None) -> View:
    """The view, rendered. `cache` (optional, the caller's dict for ONE
    scene): the plan's top view with its label, kept by its raster size and
    scale and reused when a later view asks for the same one -- the same
    pixels, not a resample. WHY (2026-10-21, the reading range): near the
    camera the raster is capped at RASTER_MAX_PX, so every case at every near
    distance asks for the identical picture, and drawing it was ~65 % of a
    near render."""
    rng = np.random.default_rng(int(view.get("seed") or 0))
    T = marker_pose(cam, float(view.get("tilt_deg") or 0.0), float(view.get("yaw_deg") or 0.0),
                    scene.centre)
    z0 = scene.centre[2]
    K = cam.K
    Hf = plane_h(K, T, z0)
    u0, v0, u1, v1 = scene.bounds
    box = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    pc = _project(Hf, box)
    x0 = int(math.floor(pc[:, 0].min())) - CROP_MARGIN_PX
    y0 = int(math.floor(pc[:, 1].min())) - CROP_MARGIN_PX
    x1 = int(math.ceil(pc[:, 0].max())) + CROP_MARGIN_PX + 1
    y1 = int(math.ceil(pc[:, 1].max())) + CROP_MARGIN_PX + 1
    sb = scene.plan["guides"]["sticker"]
    ps = _project(Hf, [(sb[0], sb[1]), (sb[2], sb[3]), (sb[0], sb[3]), (sb[2], sb[1])])
    clipped = bool(ps[:, 0].min() < 0 or ps[:, 1].min() < 0 or ps[:, 0].max() > cam.width - 1
                   or ps[:, 1].max() > cam.height - 1)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(cam.width, x1), min(cam.height, y1)
    cw, ch = max(1, x1 - x0), max(1, y1 - y0)
    s = int(max(1, min(SS_MAX, math.floor(math.sqrt(SS_BUDGET / float(cw * ch))))))
    # the top view: finer than the supersampled sensor where the face is nearest
    R, t = T[:3, :3], T[:3, 3]
    depth = min(float((R @ np.array([u, v, z0]) + t)[2]) for u, v in box)
    rpm = RASTER_OVER * s * cam.f_px / max(depth, 1e-6)
    rpm = min(rpm, RASTER_MAX_PX / max(u1 - u0, v1 - v0))
    W = max(1, int(math.ceil((u1 - u0) * rpm)))
    Hh = max(1, int(math.ceil((v1 - v0) * rpm)))
    key = (rpm, W, Hh)
    r = cache.get(key) if cache is not None else None
    if r is None:
        r = top_view(scene.plan, px_per_mm=rpm, ss=1, grid=(u0, v1, W, Hh))
        if scene.label:
            _draw_label(r, scene.label)
        if cache is not None:
            if len(cache) >= 8:                    # a few rasters of a scene, never a growing pile
                cache.pop(next(iter(cache)))
            cache[key] = r
    if cache is not None and float(view.get("occlusion") or 0.0) > 0:
        r = Raster(r.img.copy(), r.px_per_mm, r.u0, r.v1)   # the dirt is drawn on a copy
    occ = _occlude(r, scene.area, float(view.get("occlusion") or 0.0), rng)
    S = np.array([[s, 0.0, (s - 1) / 2.0 - s * x0], [0.0, s, (s - 1) / 2.0 - s * y0],
                  [0.0, 0.0, 1.0]])
    A_idx = r.A @ np.array([[1.0, 0, 0.5], [0, 1.0, 0.5], [0, 0, 1.0]])
    big = cv2.warpPerspective(r.img, S @ Hf @ A_idx, (cw * s, ch * s), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    img = (cv2.resize(big, (cw, ch), interpolation=cv2.INTER_AREA) if s > 1 else big)
    img = img.astype(np.float32)
    Kc = K.copy()
    Kc[0, 2] -= x0
    Kc[1, 2] -= y0
    Hc = Kc @ np.column_stack([R[:, 0], R[:, 1], R[:, 2] * z0 + t])
    glare = float(view.get("glare") or 0.0)
    if glare > 0:
        a = scene.area
        pa = _project(Hc, [(a[0], a[1]), (a[2], a[3]), (a[0], a[3]), (a[2], a[1])])
        gx = rng.uniform(pa[:, 0].min(), pa[:, 0].max())
        gy = rng.uniform(pa[:, 1].min(), pa[:, 1].max())
        size = max(pa[:, 0].max() - pa[:, 0].min(), pa[:, 1].max() - pa[:, 1].min())
        sig = max(1.0, GLARE_SIZE * size)
        yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
        g = np.exp(-((xx - gx) ** 2 + (yy - gy) ** 2) / (2.0 * sig * sig)) * min(1.0, glare)
        img = img + (255.0 - img) * g
    blur = float(view.get("blur_px") or 0.0)
    if blur > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur)
    noise = float(view.get("noise") or 0.0)
    if noise > 0:
        img = img + rng.normal(0.0, NOISE_SIGMA * min(1.0, noise), img.shape).astype(np.float32)
    img = np.clip(np.round(img), 0, 255).astype(np.uint8)
    return View(img, Kc, T, Hc, (x0, y0), clipped,
                max(cam.width, cam.height) / float(max(cw, ch)), occ)


def parameters_for(v: View):
    """detect.parameters() with OpenCV's perimeter limits scaled from the
    whole sensor to the crop (the rates are a share of the image's side)."""
    p = _det.parameters()
    p.minMarkerPerimeterRate = p.minMarkerPerimeterRate * v.perimeter_scale
    p.maxMarkerPerimeterRate = p.maxMarkerPerimeterRate * v.perimeter_scale
    return p


def read(v: View, d: dict) -> dict:
    """{ids, corners, pose: T_cam_target (m) or None, info}."""
    p = parameters_for(v)
    got = _det.detect(v.img, d, params=p)
    spec = d["marker"]
    try:
        T, info = _pnp.solve(v.img, spec, v.K, params=p)
    except cv2.error as exc:                     # e.g. 4 collinear ChArUco corners
        T, info = None, {"error": str(exc).strip().splitlines()[-1][:200]}
    want = int(spec["marker_id"])
    if T is not None and spec.get("layout", "single") == "single" and want in got["corners"]:
        # WHY: IPPE_SQUARE degenerates on a marker exactly square on to the
        # camera and centred (only a synthetic view is): both its solutions
        # come back 180 deg off, 20-40 px from the corners. Re-solve then.
        L = spec["marker_length_m"]
        obj = np.array([[-L / 2, L / 2, 0], [L / 2, L / 2, 0], [L / 2, -L / 2, 0],
                        [-L / 2, -L / 2, 0]], dtype=np.float64)
        imgp = np.asarray(got["corners"][want], np.float64).reshape(4, 2)
        if _rms(T, obj, imgp, v.K) > 1.0:
            ok, rvec, tvec = cv2.solvePnP(obj, imgp, v.K, None, flags=cv2.SOLVEPNP_ITERATIVE)
            if ok:
                T = np.eye(4)
                T[:3, :3] = cv2.Rodrigues(rvec)[0]
                T[:3, 3] = tvec.ravel()
                info["refit"] = "iterative"
    got["pose"], got["info"] = T, info
    return got


def _rms(T, obj, imgp, K) -> float:
    rvec = cv2.Rodrigues(np.ascontiguousarray(T[:3, :3]))[0]
    proj, _ = cv2.projectPoints(obj, rvec, T[:3, 3].reshape(3, 1), K, None)
    return float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - imgp) ** 2, axis=1))))


def truth_m(v: View, d: dict) -> np.ndarray:
    """T_cam_opencv (m): where the plan's OpenCV frame really is."""
    T = v.T_cam_pattern @ np.array(d["frames"]["opencv"], np.float64).reshape(4, 4)
    T[:3, 3] /= 1000.0
    return T


# ------------------------------------------------------------ the picture

def picture(v: View, d: dict, got: dict, missing: List[int], max_w: int = 640) -> np.ndarray:
    """The view (BGR) at most max_w wide: a small crop magnified by whole
    pixels (nearest, so the sensor's pixels show), the detected markers in
    green with their ids, the missing ones' true outlines in red, the pose's
    axes when it was solved."""
    ch, cw = v.img.shape
    k = min(max_w / float(cw), max_w / float(ch))
    if k >= 1.0:
        k = float(int(k))
        img = cv2.resize(v.img, (int(cw * k), int(ch * k)), interpolation=cv2.INTER_NEAREST)
    else:
        img = cv2.resize(v.img, (max(1, int(round(cw * k))), max(1, int(round(ch * k)))),
                         interpolation=cv2.INTER_AREA)
    out = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    def disp(pts):
        return np.asarray(pts, np.float64) * k + (k - 1.0) / 2.0

    lw = max(1, int(round(out.shape[1] / 320.0)))
    want = _det.expected_corners_mm(d)
    for mid in missing:
        if mid in want:
            q = disp(_project(v.H, want[mid])).round().astype(np.int32)
            cv2.polylines(out, [q], True, (40, 40, 230), lw, cv2.LINE_AA)
    for mid, cs in got["corners"].items():
        q = disp(cs).round().astype(np.int32)
        colour = (60, 180, 60) if mid in want else (200, 60, 200)
        cv2.polylines(out, [q], True, colour, lw, cv2.LINE_AA)
        cv2.circle(out, tuple(int(c) for c in q[0]), lw + 2, colour, -1, cv2.LINE_AA)
        c = q.mean(axis=0).astype(int)
        cv2.putText(out, str(mid), (int(c[0]) - 6 * lw, int(c[1]) + 4 * lw),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45 * lw, colour, lw, cv2.LINE_AA)
    T = got.get("pose")
    if T is not None:
        Kd = v.K.copy()
        Kd[:2, :2] *= k
        Kd[:2, 2] = Kd[:2, 2] * k + (k - 1.0) / 2.0
        rvec = cv2.Rodrigues(np.ascontiguousarray(T[:3, :3]))[0]
        L = float(d["marker"]["marker_length_m"]) * 0.5
        cv2.drawFrameAxes(out, Kd, np.zeros(5), rvec, T[:3, 3].reshape(3, 1), L, lw + 1)
    return out
