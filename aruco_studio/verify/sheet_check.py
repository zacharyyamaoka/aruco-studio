"""WYSIWYG: the printed page equals the plan (design note M6 section g).

The sticker sheet's PDF (core.sheet.render_sticker_pdf) is rasterised by
pdfium at 600 dpi; for every sticker `sheet.json` placed (page, x, y,
rotation), its box on the page is compared with the plan's own top view
laid on the SAME pixels (verify/render.top_view on the page's grid, turned
as the sticker was), and read by OpenCV:

| Step | Check | Bar |
|---|---|---|
| ink | XOR of the two black masks over their union, inside the box | <= 2 % |
| ids | OpenCV reads the crop: every id; a ChArUco board's every corner; the marker side against the plan's marker length | side within 0.15 mm |
| label | inside each of the plan's label boxes the ink matches the render | IoU >= 0.9 per box |
| outline | the grey cut line (CUT_GREY, by threshold, away from the ink) traced against the outline: every point of the outline has the line within the bar, and every line pixel inside the box is that near the outline; every hole found | Hausdorff <= 0.15 mm |
| scale | the 100 mm and the 4 in bar measured along their own rows | 100.0 / 101.6 +/- 0.1 mm |

numpy, OpenCV and pypdfium2 are used here only.
"""
from __future__ import annotations

import copy
import math
from typing import Dict, List, Optional

import cv2
import numpy as np

from ..core import sheet as _SH
from . import detect as _D
from .render import top_view

DPI = 600
INK_XOR_MAX = 0.02
SIDE_MAX_MM = 0.15
LABEL_IOU_MIN = 0.9
OUTLINE_MAX_MM = 0.15
BAR_TOL_MM = 0.1
BLACK = 128                      # a pixel darker than this is ink
GREY_LO, GREY_HI = 60, 225       # the cut line's grey (0.55 = 140) and its soft edges
INK_SS = 2                       # the render's samples per pixel side: cv2.fillPoly takes a
LABEL_SS = 8                     # pixel its edge touches, so 1 sample grows the black a pixel


def rasterise(pdf: bytes, dpi: int = DPI) -> List[np.ndarray]:
    """Every page of a PDF as 8-bit grey at `dpi` (pdfium)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    out = []
    for i in range(len(doc)):
        # pdfium makes the bitmap ceil(page * scale) pixels: 792 pt x 600 / 72
        # is 6600.000000000001 in floats, so 6601 rows, and the page is
        # stretched by one pixel. A hair less scale keeps it 6600 (1:1).
        bmp = doc[i].render(scale=dpi / 72.0 * (1.0 - 1e-9), grayscale=True)
        img = np.asarray(bmp.to_numpy())
        if img.ndim == 3:
            img = img[:, :, 0] if img.shape[2] == 1 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        out.append(np.ascontiguousarray(img))
    return out


def _turn(u, v, rot):
    return (u, v) if not rot else (-v, u)


def turned(plan: dict, rot: int) -> dict:
    """The plan's geometry turned `rot` degrees (0 / 90) about its origin:
    what the sheet does to a sticker that only fits turned."""
    if not rot:
        return plan
    d = copy.deepcopy(plan)
    for L in d["layers"]:
        for p in L["polygons"]:
            p["outer"] = [list(_turn(u, v, rot)) for u, v in p["outer"]]
            p["holes"] = [[list(_turn(u, v, rot)) for u, v in h] for h in p.get("holes", [])]
        for c in L.get("circles") or []:
            c["c"] = list(_turn(c["c"][0], c["c"][1], rot))
    if d.get("body") and d["body"].get("loops"):
        d["body"]["loops"] = [[list(_turn(u, v, rot)) for u, v in lp] for lp in d["body"]["loops"]]
    return d


def _box_px(st: dict, s: float, pad_mm: float = 0.0):
    x0 = int(math.floor((st["x_mm"] - pad_mm) * s))
    y0 = int(math.floor((st["y_mm"] - pad_mm) * s))
    x1 = int(math.ceil((st["x_mm"] + st["w_mm"] + pad_mm) * s))
    y1 = int(math.ceil((st["y_mm"] + st["h_mm"] + pad_mm) * s))
    return x0, y0, x1, y1


def expected_grey(plan: dict, st: dict, s: float, box, ss: int = 1) -> np.ndarray:
    """The plan's top view on the page pixels `box` (x0, y0, x1, y1); `ss`
    x `ss` samples a pixel (1: the pixel centre, which is what a 50 %
    threshold of pdfium's coverage gives on an axis-aligned edge)."""
    x0, y0, x1, y1 = box
    ox, oy = st["origin_mm"]
    rot = int(st.get("rotation") or 0)
    # a page pixel column c has its centre at (c + 0.5) / s mm; in the turned
    # sticker frame u = page x - ox, v = oy - page y
    u0 = x0 / s - ox
    v1 = oy - y0 / s
    r = top_view(turned(plan, rot), px_per_mm=s, ss=ss, grid=(u0, v1, x1 - x0, y1 - y0))
    return r.img


def _page_xy(st: dict, u: float, v: float):
    ru, rv = _turn(u, v, int(st.get("rotation") or 0))
    return st["origin_mm"][0] + ru, st["origin_mm"][1] - rv


def _samples(loop, step_mm: float = 0.05):
    pts = []
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        k = max(1, int(math.ceil(L / step_mm)))
        for j in range(k):
            t = j / k
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return pts


def _outline(img_box: np.ndarray, st: dict, s: float, box) -> dict:
    """The grey cut line against the outline (page mm from sheet.json)."""
    x0, y0, x1, y1 = box
    black = (img_box < BLACK).astype(np.uint8)
    near_ink = cv2.dilate(black, np.ones((7, 7), np.uint8)) > 0
    grey = (img_box >= GREY_LO) & (img_box <= GREY_HI) & ~near_ink
    if not grey.any():
        return {"hausdorff_mm": None, "holes_found": 0, "ok": False, "why": "no cut line"}
    dist_to_grey = cv2.distanceTransform((~grey).astype(np.uint8), cv2.DIST_L2, 5)
    dist_to_ink = cv2.distanceTransform((1 - black).astype(np.uint8), cv2.DIST_L2, 5)
    o = st["outline_page_mm"]
    loops = [o["outer"]] + list(o.get("holes") or [])
    worst = 0.0
    found = 0
    hidden = 0
    H, W = grey.shape
    for k, lp in enumerate(loops):
        d = 0.0
        for (x, y) in _samples(lp):
            c, r = int(x * s) - x0, int(y * s) - y0
            if 0 <= r < H and 0 <= c < W:
                if dist_to_ink[r, c] < 5.0:
                    hidden += 1                # the line runs along the ink: not visible
                    continue
                d = max(d, float(dist_to_grey[r, c]) / s)
        worst = max(worst, d)
        if k and d <= OUTLINE_MAX_MM:
            found += 1
    # every line pixel inside the box (less a hairline) is near the outline
    line = np.zeros_like(black)
    for k, lp in enumerate(loops):
        pts = np.round((np.asarray(lp, np.float64) * s - [x0, y0]) * 16).astype(np.int32)
        cv2.polylines(line, [pts], True, 1, 1, lineType=cv2.LINE_8, shift=4)
        a = np.asarray(lp, np.float64)
        dx, dy = a[:, 0].max() - a[:, 0].min(), a[:, 1].max() - a[:, 1].min()
        if k and max(dx, dy) < _SH.PUNCH_MM:            # a small hole's cross
            cx, cy, h = a[:, 0].mean(), a[:, 1].mean(), max(dx, dy) / 2.0
            for (p0, p1) in (((cx - h, cy), (cx + h, cy)), ((cx, cy - h), (cx, cy + h))):
                q = np.round((np.asarray([p0, p1]) * s - [x0, y0]) * 16).astype(np.int32)
                cv2.polylines(line, [q], False, 1, 1, lineType=cv2.LINE_8, shift=4)
    dist_to_line = cv2.distanceTransform((1 - line).astype(np.uint8), cv2.DIST_L2, 5)
    inner = np.zeros_like(grey)
    m = int(math.ceil(0.1 * s))
    bx0 = int(round(st["x_mm"] * s)) - x0 + m
    by0 = int(round(st["y_mm"] * s)) - y0 + m
    bx1 = int(round((st["x_mm"] + st["w_mm"]) * s)) - x0 - m
    by1 = int(round((st["y_mm"] + st["h_mm"]) * s)) - y0 - m
    inner[max(0, by0):max(0, by1), max(0, bx0):max(0, bx1)] = True
    stray = grey & inner
    if stray.any():
        worst = max(worst, float(dist_to_line[stray].max()) / s - 0.5 / s)
    holes = len(loops) - 1
    return {"hausdorff_mm": round(float(worst), 4), "holes": holes, "holes_found": found,
            "hidden_samples": hidden,
            "ok": bool(worst <= OUTLINE_MAX_MM and found == holes)}


def _ids(img_box: np.ndarray, plan: dict, s: float) -> dict:
    pad = int(round(4.0 * s))
    crop = np.pad(img_box, pad, constant_values=255)
    got = _D.detect(crop, plan)
    want = list(plan["ids"])
    sides = []
    for _i, cs in got["corners"].items():
        c = np.asarray(cs, np.float64)
        sides.append(float(np.mean([np.linalg.norm(c[k] - c[(k + 1) % 4]) for k in range(4)])))
    L = plan["marker"]["marker_length_m"] * 1000.0
    err = max((abs(v / s - L) for v in sides), default=None)
    rep = {"ids_expected": want, "ids_read": got["ids"],
           "missing": sorted(set(want) - set(got["ids"])),
           "side_err_mm": None if err is None else round(err, 4)}
    ok = not rep["missing"] and err is not None and err <= SIDE_MAX_MM
    if plan["marker"]["layout"] == "charuco":
        exp = len(_D.expected_charuco_mm(plan))
        rep["charuco_expected"], rep["charuco_read"] = exp, len(got["charuco_ids"])
        ok = ok and rep["charuco_read"] == exp
    rep["ok"] = ok
    return rep


def _labels(page: np.ndarray, plan: dict, st: dict, s: float) -> dict:
    """Per label box: the letters on the page against the plan's, as each
    pixel's share of letter (the page's grey; the render's 8 x 8 samples a
    pixel): IoU = sum(min) / sum(max). A stroke is a few pixels wide, so a
    50 % threshold on either side would measure the anti-aliasing, not the
    label. The letters are the label's ink: white knocked out of the black
    (a label on the black), black on the white."""
    lab = plan.get("label") or {}
    ious = []
    knocked = lab.get("kind") == "black"
    for part in lab.get("parts") or []:
        u0, v0, u1, v1 = part["rect"]
        pts = [_page_xy(st, u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
        c0 = int(math.floor(min(p[0] for p in pts) * s))
        c1 = int(math.ceil(max(p[0] for p in pts) * s))
        r0 = int(math.floor(min(p[1] for p in pts) * s))
        r1 = int(math.ceil(max(p[1] for p in pts) * s))
        a = page[r0:r1, c0:c1].astype(np.float64) / 255.0           # white's share
        b = expected_grey(plan, st, s, (c0, r0, c1, r1), ss=LABEL_SS).astype(np.float64) / 255.0
        if not knocked:
            a, b = 1.0 - a, 1.0 - b                                  # the black's share
        u = float(np.maximum(a, b).sum())
        ious.append(1.0 if u == 0 else float(np.minimum(a, b).sum()) / u)
    return {"boxes": len(ious), "iou_min": None if not ious else round(min(ious), 4),
            "ok": all(v >= LABEL_IOU_MIN for v in ious)}


def bar_mm(img: np.ndarray, bar, s: float) -> Optional[float]:
    """The length of a ruler bar (x, y, w, h mm) measured along its middle row."""
    x, y, w, h = bar
    r = int(round((y + h / 2.0) * s))
    c0 = max(0, int((x - 3.0) * s))
    c1 = min(img.shape[1], int((x + w + 3.0) * s))
    row = [float(v) for v in img[r, c0:c1]]
    dark = [v < BLACK for v in row]
    best, run, start, bs = 0, 0, 0, 0
    for i, v in enumerate(dark):
        if v:
            if run == 0:
                start = i
            run += 1
            if run > best:
                best, bs = run, start
        else:
            run = 0
    if not best:
        return None
    # the two end pixels' coverage (anti-aliased) refines the length
    left = 1.0 - row[bs - 1] / 255.0 if bs > 0 else 0.0
    right = 1.0 - row[bs + best] / 255.0 if bs + best < len(row) else 0.0
    return (best + left + right) / s


def check_sheet(pdf: bytes, summary: dict, plans: Dict[str, dict], dpi: int = DPI,
                pages: Optional[List[np.ndarray]] = None) -> dict:
    """Steps 1-8 on a sticker sheet. `summary`: its sheet.json; `plans`:
    {key: TagPlan dict}. -> {"stickers": [...], "pages": [...], "worst": {...}, "ok"}."""
    s = dpi / 25.4
    pages = pages if pages is not None else rasterise(pdf, dpi)
    out = []
    for st in summary["stickers"]:
        img = pages[st["page"] - 1]
        box = _box_px(st, s, 0.0)
        x0, y0, x1, y1 = box
        crop = img[max(0, y0):y1, max(0, x0):x1]
        plan = plans[st["key"]]
        want_grey = expected_grey(plan, st, s, box, ss=INK_SS)
        want = want_grey < BLACK
        seen = crop < BLACK
        hh, ww = min(want.shape[0], seen.shape[0]), min(want.shape[1], seen.shape[1])
        want, seen = want[:hh, :ww], seen[:hh, :ww]
        union = np.count_nonzero(want | seen)
        xor = float(np.count_nonzero(want ^ seen)) / float(union) if union else 0.0
        ids = _ids(crop, plan, s)
        lab = _labels(img, plan, st, s)
        ol = _outline(crop, st, s, box)
        row = {"key": st["key"], "page": st["page"], "rotation": st["rotation"],
               "ink_xor": round(xor, 5), "ink_ok": bool(xor <= INK_XOR_MAX), "ids": ids,
               "label": lab, "outline": ol}
        row["ok"] = row["ink_ok"] and ids["ok"] and lab["ok"] and ol["ok"]
        out.append(row)
    bars = []
    ruler = summary.get("ruler")
    for i, img in enumerate(pages):
        if not ruler:
            break
        mm = bar_mm(img, ruler["mm_bar"], s)
        inch = bar_mm(img, ruler["in_bar"], s)
        bars.append({"page": i + 1, "mm_bar": None if mm is None else round(mm, 4),
                     "in_bar": None if inch is None else round(inch, 4),
                     "ok": bool(mm is not None and inch is not None
                                and abs(mm - 100.0) <= BAR_TOL_MM
                                and abs(inch - 101.6) <= BAR_TOL_MM)})
    worst = {
        "ink_xor": max((r["ink_xor"] for r in out), default=None),
        "side_err_mm": max((r["ids"]["side_err_mm"] for r in out
                            if r["ids"]["side_err_mm"] is not None), default=None),
        "label_iou_min": min((r["label"]["iou_min"] for r in out
                              if r["label"]["iou_min"] is not None), default=None),
        "outline_mm": max((r["outline"]["hausdorff_mm"] for r in out
                           if r["outline"]["hausdorff_mm"] is not None), default=None),
        "bar_err_mm": max((max(abs(b["mm_bar"] - 100.0), abs(b["in_bar"] - 101.6))
                           for b in bars if b["mm_bar"] is not None and b["in_bar"] is not None),
                          default=None)}
    return {"dpi": dpi, "stickers": out, "pages": bars, "worst": worst,
            "ok": all(r["ok"] for r in out) and all(b["ok"] for b in bars)}


def check_scene_sheet(scene, plans=None, page: str = "letter", landscape: bool = False,
                      mode: str = "spaced", margin_mm: float = 10.0, proofs: bool = False,
                      dpi: int = DPI, date: Optional[str] = None) -> dict:
    """The scene's own sticker sheet made and checked (POST /api/scene/verify/sheet)."""
    import json
    from ..scene import sheet as _SS
    plans = plans if plans is not None else scene.plans()
    got = _SS.sticker_files(scene, plans, page, landscape, mode, margin_mm, proofs, date)
    summary = json.loads(got["sheet.json"].decode("utf-8"))
    rep = check_sheet(got["sheet.pdf"], summary, {k: plans[k].to_dict() if hasattr(plans[k], "to_dict")
                                                  else plans[k] for k in plans}, dpi)
    rep["mode"], rep["page"] = mode, page
    rep["rejected"] = summary["rejected"]
    return rep
