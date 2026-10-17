"""The G-code oracle (M8 note 5.7): a Send to PrusaSlicer project sliced
HEADLESS and its toolpaths checked against the plan. Tests only: nothing
here opens PrusaSlicer's window or reads the user's own config.

| Step | Check | Bar |
|---|---|---|
| 1 | `prusa-slicer-console --datadir <scratch> --load <ascii.ini> --dont-arrange --export-gcode --output <gcode> <project.3mf>`: a scratch datadir holding copies of the needed presets with every private key stripped; ASCII G-code (`binary_gcode = 0`) and plain lines (`arc_fitting = disabled`) overridden | skipped, not failed, when the console is absent |
| 2 | layers: `;LAYER_CHANGE` count against the tallest part's height per the preset (the first layer, then layers) | +/- 1 |
| 3 | the black's heights: the first and last layer where extruder 2 extrudes on a tag, against the z range of that tag's black volume | within one layer height each |
| 4 | lines per cell (a tag lying flat): in the middle layer of the black, the extrusion lines crossing one module of a marker's border, parallel to it, against module / line | exact |
| 5 | ink: extruder 2's paths drawn at their `;WIDTH` on a 0.04 mm raster against the plan's black (plan/mesh.top): a flat tag in that layer's plane, a tag on a side face in its face's plane (u along the face, z), each layer a band of its height | IoU >= 0.9; a label's pixels >= 60 % |
| 6 | the footprint: every extrusion inside its part's footprint + 0.5 mm, none in the bed's margin | none |

Numpy for the rasters (verify/ may use it); the slicer is a subprocess.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..plan import mesh as _ME
from ..scene import print3d as _P3
from ..scene.model import mat_mul

RES_MM = 0.04
IOU_MIN = 0.9
LABEL_MIN = 0.6
FOOT_MM = 0.5
OVERRIDES = "binary_gcode = 0\narc_fitting = disabled\n"
NOT_PAINT = ("Wipe tower", "Custom", "")


# ------------------------------------------------------------------ slicing

def find_console() -> Optional[str]:
    """prusa-slicer-console at REF's known paths, else on PATH, else None."""
    cands = []
    for env in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(env):
            cands.append(os.path.join(os.environ[env], "Prusa3D", "PrusaSlicer",
                                      "prusa-slicer-console.exe"))
    cands += [shutil.which("prusa-slicer-console"), shutil.which("prusa-slicer"),
              "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def slice_project(console: str, project: str, workdir: str,
                  presets: Optional[Dict[str, str]] = None, timeout: float = 600.0) -> dict:
    """Slice `project` headless. `workdir` gets the scratch datadir (the
    `presets` {relpath: text} copied into it: already stripped of every
    private key), the overrides and the G-code. -> {exit, gcode, log,
    seconds, datadir}."""
    work = Path(workdir)
    datadir = work / "psdata"
    datadir.mkdir(parents=True, exist_ok=True)
    for rel, text in (presets or {}).items():
        p = datadir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    ini = work / "ascii_gcode.ini"
    ini.write_text(OVERRIDES, encoding="ascii")
    gcode = work / (Path(project).stem + ".gcode")
    t0 = time.perf_counter()
    p = subprocess.run([console, "--datadir", str(datadir), "--load", str(ini), "--dont-arrange",
                        "--export-gcode", "--output", str(gcode), str(project)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return {"exit": p.returncode, "gcode": str(gcode) if gcode.is_file() else None,
            "log": ((p.stdout or "") + (p.stderr or ""))[-2000:],
            "seconds": round(time.perf_counter() - t0, 2), "datadir": str(datadir)}


def parse_gcode(path: str):
    """(;LAYER_CHANGE count, [{"z", "h", "segs": [(tool, type, width, x0, y0,
    x1, y1)]}] per printing layer). REF slice_aruco_label.parse_gcode's rule."""
    layers, cur = [], None
    tool, typ, width, z, h = 1, "", 0.0, 0.0, 0.0
    x = y = None
    changes = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(";LAYER_CHANGE"):
                changes += 1
                continue
            if line.startswith(";Z:"):
                z = float(line[3:])
                continue
            if line.startswith(";HEIGHT:"):
                h = float(line[8:])
                continue
            if line.startswith(";TYPE:"):
                typ = line[6:].strip()
                continue
            if line.startswith(";WIDTH:"):
                width = float(line[7:])
                continue
            mt = re.match(r"^T(\d+)\s*$", line)
            if mt:
                tool = int(mt.group(1)) + 1
                continue
            if not (line.startswith("G1 ") or line.startswith("G0 ")):
                continue
            code = line.split(";")[0]
            nx = re.search(r"X([-\d.]+)", code)
            ny = re.search(r"Y([-\d.]+)", code)
            ne = re.search(r"E([-\d.]+)", code)
            px, py = x, y
            if nx:
                x = float(nx.group(1))
            if ny:
                y = float(ny.group(1))
            if (ne and float(ne.group(1)) > 0 and (nx or ny) and px is not None
                    and py is not None and typ not in NOT_PAINT):
                if cur is None or abs(cur["z"] - z) > 1e-6:
                    cur = {"z": z, "h": h, "segs": []}
                    layers.append(cur)
                cur["segs"].append((tool, typ, width, px, py, x, y))
    return changes, layers


def expected_layers(height: float, layer: float, first: float) -> int:
    if height <= first + 1e-9:
        return 1
    return 1 + int(math.floor((height - first) / layer + 0.5))


# ------------------------------------------------------------------ rasters

class Grid:
    """A 2D raster of RES_MM pixels over (x0, y0)..(x1, y1)."""

    def __init__(self, x0, y0, x1, y1, res=RES_MM):
        self.x0, self.y0, self.res = x0, y0, res
        self.w = max(1, int(math.ceil((x1 - x0) / res)))
        self.h = max(1, int(math.ceil((y1 - y0) / res)))
        self.xc = x0 + (np.arange(self.w) + 0.5) * res
        self.yc = y0 + (np.arange(self.h) + 0.5) * res

    def empty(self):
        return np.zeros((self.h, self.w), dtype=bool)

    def capsule(self, img, ax, ay, bx, by, r):
        """Mark the pixels within r of the segment a-b."""
        i0 = max(0, int((min(ax, bx) - r - self.x0) / self.res) - 1)
        i1 = min(self.w, int((max(ax, bx) + r - self.x0) / self.res) + 2)
        j0 = max(0, int((min(ay, by) - r - self.y0) / self.res) - 1)
        j1 = min(self.h, int((max(ay, by) + r - self.y0) / self.res) + 2)
        if i0 >= i1 or j0 >= j1:
            return
        X, Y = np.meshgrid(self.xc[i0:i1], self.yc[j0:j1])
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = np.zeros_like(X) if L2 < 1e-12 else np.clip(((X - ax) * dx + (Y - ay) * dy) / L2,
                                                        0.0, 1.0)
        qx, qy = ax + t * dx - X, ay + t * dy - Y
        img[j0:j1, i0:i1] |= (qx * qx + qy * qy) <= r * r

    def band(self, img, s0, s1, z0, z1):
        """Mark the box s0..s1 x z0..z1 (pixel centres inside)."""
        i = (self.xc >= s0) & (self.xc <= s1)
        j = (self.yc > z0) & (self.yc <= z1)
        img[np.ix_(j, i)] = True

    def polygons(self, polys) -> np.ndarray:
        """Even-odd fill of [[outer, hole, ...]] (every loop of every polygon)."""
        img = self.empty()
        rows, xs = [], []
        for poly in polys:
            for lp in poly:
                n = len(lp)
                for k in range(n):
                    (xa, ya), (xb, yb) = lp[k], lp[(k + 1) % n]
                    if abs(yb - ya) < 1e-12:
                        continue
                    lo, hi = min(ya, yb), max(ya, yb)
                    j0 = int(math.ceil((lo - self.y0) / self.res - 0.5))
                    j1 = int(math.ceil((hi - self.y0) / self.res - 0.5))
                    j = np.arange(max(0, j0), min(self.h, j1))
                    if not len(j):
                        continue
                    yc = self.yc[j]
                    rows.append(j)
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        if not rows:
            return img
        rows = np.concatenate(rows)
        xs = np.concatenate(xs)
        order = np.lexsort((xs, rows))
        rows, xs = rows[order], xs[order]
        diff = np.zeros((self.h, self.w + 1), dtype=np.int32)
        r0 = 0
        while r0 < len(rows):
            r1 = r0
            while r1 < len(rows) and rows[r1] == rows[r0]:
                r1 += 1
            seg = xs[r0:r1]
            for a, b in zip(seg[0::2], seg[1::2]):
                ia = int(np.clip(math.ceil((a - self.x0) / self.res - 0.5), 0, self.w))
                ib = int(np.clip(math.ceil((b - self.x0) / self.res - 0.5), 0, self.w))
                diff[rows[r0], ia] += 1
                diff[rows[r0], ib] -= 1
            r0 = r1
        return np.cumsum(diff, axis=1)[:, :self.w] > 0


def iou(a: np.ndarray, b: np.ndarray) -> float:
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 1.0


# ------------------------------------------------------------------ geometry

def _apply(M, p):
    x, y, z = p
    return (M[0] * x + M[1] * y + M[2] * z + M[3], M[4] * x + M[5] * y + M[6] * z + M[7],
            M[8] * x + M[9] * y + M[10] * z + M[11])


def _translate(t):
    return [1.0, 0.0, 0.0, t[0], 0.0, 1.0, 0.0, t[1], 0.0, 0.0, 1.0, t[2], 0.0, 0.0, 0.0, 1.0]


def bed_shift(lay: "_P3.Layout", pi: int) -> Tuple[float, float, float]:
    """scene mm -> bed mm for part `pi`: what object_mesh and the instance
    transform of print3d.render do to it."""
    from ..core import beds as _BD
    part = lay.parts[pi]
    lo, hi = part.bbox()
    for k, bed, cx, cy in lay.placed:
        if k == pi:
            ox, oy = _BD.bed_translation(bed, lay.settings.bed_w_mm, lay.settings.bed_d_mm)
            return (cx + ox - (lo[0] + hi[0]) / 2.0, cy + oy - (lo[1] + hi[1]) / 2.0, -lo[2])
    raise KeyError(part.name)


def _seg_cross(p, q, r, s) -> bool:
    def c(a, b, d):
        return (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
    d1, d2, d3, d4 = c(p, q, r), c(p, q, s), c(r, s, p), c(r, s, q)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _module_mm(plan_d) -> Optional[float]:
    from ..core import dictionary as _D
    mk = plan_d.get("marker") or {}
    try:
        return mk["marker_length_m"] * 1000.0 / _D.dictionary_info(mk["dictionary"])["modules"]
    except (KeyError, TypeError, ValueError):
        return None


def _line_of(plan_d, spec) -> Optional[float]:
    cells = (spec.settings or {}).get("cells") or {}
    if cells.get("of") == "cell" and cells.get("mm"):
        return float(cells["mm"])
    return None


# ------------------------------------------------------------------ the checks

def check_tag(t, plan_d, M_bed, black_vol, layers, layer_h) -> dict:
    """Steps 3-5 on one tag (its pattern placed on the bed by M_bed)."""
    lo = [min(p[i] for p in black_vol) for i in range(3)]
    hi = [max(p[i] for p in black_vol) for i in range(3)]
    pad = 1.0
    n = (M_bed[2], M_bed[6], M_bed[10])
    flat = abs(n[2]) > 0.9

    def mine(s):
        return (s[0] == 2 and all(lo[0] - pad <= x <= hi[0] + pad and lo[1] - pad <= y <= hi[1] + pad
                                  for x, y in ((s[3], s[4]), (s[5], s[6]))))
    blk = [(L, [s for s in L["segs"] if mine(s)]) for L in layers]
    blk = [(L, ss) for L, ss in blk if ss]
    out = {"normal": [round(v, 4) for v in n], "flat": flat,
           "black_z_mm": [round(lo[2], 4), round(hi[2], 4)]}
    if not blk:
        out.update(ok=False, why="extruder 2 prints nothing on this tag")
        return out
    first, last = blk[0][0]["z"], blk[-1][0]["z"]
    hz = {"first_mm": round(first, 4), "last_mm": round(last, 4),
          "want_mm": [round(lo[2], 4), round(hi[2], 4)], "layer_mm": layer_h,
          "ok": abs(first - lo[2]) <= layer_h + 1e-6 and abs(last - hi[2]) <= layer_h + 1e-6}
    out["heights"] = hz
    top = _ME.top(plan_d).get("black") or []
    if flat:
        mid = (lo[2] + hi[2]) / 2.0
        L, segs = min(blk, key=lambda b: abs((b[0]["z"] - b[0]["h"] / 2.0) - mid))
        g = Grid(lo[0] - pad, lo[1] - pad, hi[0] + pad, hi[1] + pad)

        def plane(u, v):                           # pattern frame -> the raster's plane
            return _apply(M_bed, (u, v, 0.0))[:2]
        want = g.polygons([[[plane(u, v) for u, v in lp] for lp in poly] for poly in top])
        got = g.empty()
        for s in segs:
            g.capsule(got, s[3], s[4], s[5], s[6], s[2] / 2.0)
        out["ink"] = {"layer_z_mm": L["z"], "iou": round(iou(got, want), 4),
                      "plan_px": int(want.sum()), "gcode_px": int(got.sum())}
        out["ink"]["ok"] = out["ink"]["iou"] >= IOU_MIN
        out["lines"] = lines_per_cell(t, plan_d, M_bed, segs)
    else:
        u = (M_bed[0], M_bed[4], M_bed[8])
        o = (M_bed[3], M_bed[7], M_bed[11])

        def s_of(x, y):
            return (x - o[0]) * u[0] + (y - o[1]) * u[1]
        def plane(a, b):                           # pattern frame -> (u along the face, z)
            p = _apply(M_bed, (a, b, 0.0))
            return s_of(p[0], p[1]), p[2]
        ss = [plane(a, b)[0] for poly in top for lp in poly for a, b in lp]
        g = Grid(min(ss) - pad, lo[2] - pad, max(ss) + pad, hi[2] + pad)
        want = g.polygons([[[plane(a, b) for a, b in lp] for lp in poly] for poly in top])
        got = g.empty()
        for L, segs in blk:
            for s in segs:
                sa, sb = s_of(s[3], s[4]), s_of(s[5], s[6])
                g.band(got, min(sa, sb) - s[2] / 2.0, max(sa, sb) + s[2] / 2.0,
                       L["z"] - L["h"], L["z"])
        out["ink"] = {"plane": "face (u, z)", "iou": round(iou(got, want), 4),
                      "plan_px": int(want.sum()), "gcode_px": int(got.sum())}
        out["ink"]["ok"] = out["ink"]["iou"] >= IOU_MIN
        out["lines"] = {"ok": None, "why": "a tag on a side face: its cells lie across the "
                                           "layers, so step 4 does not apply"}
    lab = plan_d.get("label") or {}
    out["label"] = ({"ok": None, "why": "no label printed"} if lab.get("kind") in (None, "none")
                    else label_cover(lab, g, got, plane))
    out["ok"] = bool(hz["ok"] and out["ink"]["ok"] and out["lines"].get("ok") is not False
                     and out["label"].get("ok") is not False)
    return out


def _in_box(box, x, y) -> bool:
    cx, cy, w, h, rot = (list(box) + [0.0])[:5]
    a = math.radians(-rot)
    dx, dy = x - cx, y - cy
    u, v = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
    return abs(u) <= w / 2.0 + 1e-9 and abs(v) <= h / 2.0 + 1e-9


def label_pixels(lab: dict):
    """[(square (u0, v0, u1, v1) mm in the pattern frame, ink?)]: every font
    pixel of every part of the plan's label (its rect in steps of its
    stroke; ink when the pixel's centre is in one of the part's boxes)."""
    out = []
    for part in lab.get("parts") or []:
        s = float(part.get("stroke_mm") or 0.0)
        r = part.get("rect")
        if not s or not r:
            continue
        nx, ny = int(round((r[2] - r[0]) / s)), int(round((r[3] - r[1]) / s))
        for i in range(nx):
            for j in range(ny):
                sq = (r[0] + i * s, r[1] + j * s, r[0] + (i + 1) * s, r[1] + (j + 1) * s)
                cx, cy = (sq[0] + sq[2]) / 2.0, (sq[1] + sq[3]) / 2.0
                out.append((sq, any(_in_box(b, cx, cy) for b in part.get("boxes") or [])))
    return out


def label_cover(lab: dict, g: "Grid", got, plane) -> dict:
    """Step 5's label half: every font pixel's central half (a quarter of a
    stroke in from each side) has its colour over LABEL_MIN of it on the
    raster `got` (extruder 2's paths). A label cut from the black (role
    `cut`) has its ink pixels free of black and its gaps black; a label
    printed in black, the other way round. `plane` maps the pattern frame
    onto the raster's plane."""
    cut = lab.get("role") == "cut"
    worst = {"ink": 1.0, "gap": 1.0}
    total = {"ink": [0.0, 0], "gap": [0.0, 0]}
    low = 0
    n = 0
    for sq, ink in label_pixels(lab):
        q = (sq[2] - sq[0]) / 4.0
        pts = [plane(u, v) for u, v in ((sq[0] + q, sq[1] + q), (sq[2] - q, sq[3] - q),
                                        (sq[0] + q, sq[3] - q), (sq[2] - q, sq[1] + q))]
        x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
        y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
        i = (g.xc >= x0) & (g.xc <= x1)
        j = (g.yc >= y0) & (g.yc <= y1)
        cells = got[np.ix_(j, i)]
        if not cells.size:
            continue
        black = float(cells.mean())
        want_black = (not ink) if cut else ink
        f = black if want_black else 1.0 - black
        k = "ink" if ink else "gap"
        worst[k] = min(worst[k], f)
        total[k][0] += f
        total[k][1] += 1
        n += 1
        low += f < LABEL_MIN
    return {"pixels": n, "role": lab.get("role"), "worst_ink": round(worst["ink"], 3),
            "worst_gap": round(worst["gap"], 3), "below": int(low),
            "mean_ink": round(total["ink"][0] / max(1, total["ink"][1]), 3),
            "mean_gap": round(total["gap"][0] / max(1, total["gap"][1]), 3),
            "ok": bool(n) and low == 0}


def lines_per_cell(t, plan_d, M_bed, segs) -> dict:
    """Step 4: extrusion lines across one module of the first marker's left
    border (TL-BL), parallel to it, at the middle of that edge."""
    from .detect import expected_corners_mm
    module = _module_mm(plan_d)
    line = _line_of(plan_d, t.spec)
    try:
        corners = expected_corners_mm(plan_d)
    except Exception as exc:                       # noqa: BLE001
        return {"ok": None, "why": f"no marker corners ({type(exc).__name__})"}
    if not corners or not module:
        return {"ok": None, "why": "no marker"}
    if not line:
        return {"ok": None, "why": "cells are not a whole number of lines (cells.of != cell)"}
    mid_id = sorted(corners)[0]
    tl, tr, _br, bl = corners[mid_id]
    m = ((tl[0] + bl[0]) / 2.0, (tl[1] + bl[1]) / 2.0)
    e = (tr[0] - tl[0], tr[1] - tl[1])
    ln = math.hypot(*e)
    e = (e[0] / ln, e[1] / ln)
    a = _apply(M_bed, (m[0] + e[0] * 1e-3, m[1] + e[1] * 1e-3, 0.0))[:2]
    b = _apply(M_bed, (m[0] + e[0] * (module - 1e-3), m[1] + e[1] * (module - 1e-3), 0.0))[:2]
    edge = _apply(M_bed, (bl[0], bl[1], 0.0))[:2], _apply(M_bed, (tl[0], tl[1], 0.0))[:2]
    ed = (edge[1][0] - edge[0][0], edge[1][1] - edge[0][1])
    el = math.hypot(*ed) or 1.0
    crossing = [s for s in segs if _seg_cross(a, b, (s[3], s[4]), (s[5], s[6]))]
    parallel = []
    for s in crossing:
        d = (s[5] - s[3], s[6] - s[4])
        dl = math.hypot(*d) or 1.0
        if abs((d[0] * ed[0] + d[1] * ed[1]) / (dl * el)) > 0.9:
            parallel.append(s)
    want = module / line
    return {"marker": mid_id, "module_mm": round(module, 4), "line_mm": line,
            "want": round(want, 4), "crossing": len(crossing), "parallel": len(parallel),
            "widths": sorted({round(s[2], 3) for s in parallel}),
            "ok": abs(want - round(want)) < 1e-6 and len(parallel) == int(round(want))}


def check_send(lay: "_P3.Layout", ps: Sequence["_P3.Part"], scene, plans: dict,
               gcode: str, layer_mm: float, first_mm: float) -> dict:
    """Steps 2-6 on a sliced Send project (one bed)."""
    changes, layers = parse_gcode(gcode)
    shifts = {}
    for pi, _bed, _x, _y in lay.placed:
        shifts[pi] = bed_shift(lay, pi)
    tallest = max(lay.parts[pi].bbox()[1][2] - lay.parts[pi].bbox()[0][2] for pi in shifts)
    want_n = expected_layers(tallest, layer_mm, first_mm)
    rep = {"layers": {"count": changes, "printing": len(layers), "want": want_n,
                      "height_mm": round(tallest, 4), "ok": abs(changes - want_n) <= 1},
           "tags": {}}
    by_name = {t.name: t for t in scene.tags}
    for pi, T in shifts.items():
        part = lay.parts[pi]
        for v in part.volumes:
            if v.kind != "black" or v.tag not in by_name:
                continue
            t = by_name[v.tag]
            d = plans[t.name].data
            M_bed = mat_mul(_translate(T), mat_mul(t.pose_full, d["frames"]["pattern_in_target"]))
            pts = [(x + T[0], y + T[1], z + T[2]) for x, y, z in v.positions]
            rep["tags"][t.name] = check_tag(t, d, M_bed, pts, layers, layer_mm)
    rep["footprint"] = footprint(lay, shifts, layers)
    rep["ok"] = bool(rep["layers"]["ok"] and rep["footprint"]["ok"] and rep["tags"]
                     and all(x["ok"] for x in rep["tags"].values()))
    return rep


def footprint(lay, shifts, layers) -> dict:
    """Step 6: every extrusion within a part's footprint (its box on the
    bed) + FOOT_MM; none in the bed's margin."""
    st = lay.settings
    boxes = []
    for pi, T in shifts.items():
        lo, hi = lay.parts[pi].bbox()
        boxes.append((lo[0] + T[0] - FOOT_MM, lo[1] + T[1] - FOOT_MM,
                      hi[0] + T[0] + FOOT_MM, hi[1] + T[1] + FOOT_MM))
    outside, margin, n = 0, 0, 0
    m = st.margin_mm
    for L in layers:
        for s in L["segs"]:
            n += 1
            for x, y in ((s[3], s[4]), (s[5], s[6])):
                if not any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes):
                    outside += 1
                    break
            for x, y in ((s[3], s[4]), (s[5], s[6])):
                if not (m <= x <= st.bed_w_mm - m and m <= y <= st.bed_d_mm - m):
                    margin += 1
                    break
    return {"segments": n, "outside": outside, "in_margin": margin, "pad_mm": FOOT_MM,
            "ok": outside == 0 and margin == 0}


def scratch(prefix: str = "aruco_slice_") -> str:
    return tempfile.mkdtemp(prefix=prefix)
