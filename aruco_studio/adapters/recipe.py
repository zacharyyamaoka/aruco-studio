"""A TagPlan as a build recipe: what a CAD shell makes, in order (pure).

Standard library only. No sizing, no label, no cells, no validation: every
number comes from the TagPlan. This module only re-shapes the plan for a
shell that builds solids:

| Recipe field | From the plan | What a shell does with it |
|---|---|---|
| `parts` | `parts` (timeline order) + `layers` grouped by part, then solid | one base-feature body per part |
| a part's `solids` | `Layer.solid` | a part = the UNION of its solids |
| a solid's `steps` | the layers of that solid, in plan order | `add`: unite with the solid so far; `sub`: take it away |
| a step's `polygons` | `Layer.polygons` / `Layer.circles` | each polygon as a `box`, `cylinder`, convex `prism` or `triangles` (a concave one), minus its `holes` |
| `combines` | `combines` | join / cut / intersect into the body under or the tile |
| `paint` | the part's colour | REF `paint`: the pattern body black (White only: white); a new tile's body and faces white; a joined tile's faces only; the pins' faces white |
| `frames.pattern_cm` | `frames.pattern_in_target` and the host's base frame | where (u, v, z) mm of the pattern frame lands in the host (cm) |
| `frames.opencv_cm` | `frames.opencv_target` and the base frame | where the tag's Joint Origin must read back |
| `frame_sketch` | `frames.opencv_target` | REF `frame_points`: OpenCV's origin, a 0.5 cm line along x, one along z |
| `timeline` | REF create()'s order | `create`: each combine right after its base feature; `wrap_first`: every base feature, then the combines |

Body names and the frame sketch's name are REF's (`aruco_feature.TILE_BODY`
.. `TRIM_BODY`, `aruco_tags.FRAME_SKETCH`), so a rebuilt node reads as
today's. Lengths: the shapes are mm in the pattern frame (as the plan); the
frames are in the host's unit (cm, Fusion's internal unit).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

SCHEMA = "arucostudio.recipe/1"

# REF ArucoMarkers/aruco_feature.py (c8216ff) L171-177; aruco_tags L1288-1289
WHITE_BODY = "aruco white"
CELLS_BODY = "aruco cells"
TILE_BODY = "tag tile"
PIN_BODY = "aruco pin"
POCKET_BODY = "aruco pocket"
RECESS_BODY = "aruco recess"
TRIM_BODY = "aruco trim"
FRAME_SKETCH = "aruco frame"
FRAME_LEN_CM = 0.5
NAMES = {"tile": TILE_BODY, "pin": PIN_BODY, "pocket": POCKET_BODY, "recess": RECESS_BODY,
         "trim": TRIM_BODY}

EPS = 1e-9
Pt = Tuple[float, float]
Vec = List[float]
Frame = Tuple[Vec, Vec, Vec, Vec]
IDENTITY: Frame = ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])


# ------------------------------------------------------------------ frames

def frame_of_matrix(m: Sequence[float]) -> Frame:
    """A row-major 4x4 (16 numbers) -> (origin, x, y, z): its columns."""
    return ([m[3], m[7], m[11]], [m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]])


def host_frame(base: Frame, m_mm: Sequence[float]) -> Frame:
    """A frame the plan gives in the TARGET frame (mm, 16 numbers) in the
    host's space: `base` = the target frame there (origin in cm, unit
    axes). -> (o cm, x, y, z)."""
    bo, bx, by, bz = base
    o, x, y, z = frame_of_matrix(m_mm)

    def P(p):
        return [bo[i] + (bx[i] * p[0] + by[i] * p[1] + bz[i] * p[2]) / 10.0 for i in range(3)]

    def V(v):
        return [bx[i] * v[0] + by[i] * v[1] + bz[i] * v[2] for i in range(3)]
    return P(o), V(x), V(y), V(z)


def to_host(frame: Frame, u_mm: float, v_mm: float, z_mm: float = 0.0) -> Vec:
    """A pattern-frame point (mm) in the host (cm)."""
    o, x, y, z = frame
    return [o[i] + (x[i] * u_mm + y[i] * v_mm + z[i] * z_mm) / 10.0 for i in range(3)]


def frame_points(frame: Frame, length_cm: float = FRAME_LEN_CM):
    """REF aruco_tags.frame_points: (origin, x end, z end) of a frame (cm)."""
    o, x, _y, z = frame
    return ([float(c) for c in o], [o[i] + x[i] * length_cm for i in range(3)],
            [o[i] + z[i] * length_cm for i in range(3)])


# ------------------------------------------------------------------ shapes

def _area2(pts: Sequence[Pt]) -> float:
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def _clean(pts) -> List[Pt]:
    out = [(float(u), float(v)) for u, v in pts]
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < EPS and abs(out[0][1] - out[-1][1]) < EPS:
        out = out[:-1]
    if _area2(out) < 0:
        out = out[::-1]
    return out


def _cross_z(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def is_convex(pts: Sequence[Pt]) -> bool:
    n = len(pts)
    scale = max(max(abs(u), abs(v)) for u, v in pts) or 1.0
    tol = 1e-12 * scale * scale
    return n >= 3 and all(_cross_z(pts[i - 1], pts[i], pts[(i + 1) % n]) >= -tol
                          for i in range(n))


def _rect(pts: Sequence[Pt]) -> Optional[dict]:
    """A 4-corner polygon with right angles -> a box (centre, x axis, w, h)."""
    if len(pts) != 4:
        return None
    e = [(pts[(i + 1) % 4][0] - pts[i][0], pts[(i + 1) % 4][1] - pts[i][1]) for i in range(4)]
    ln = [math.hypot(*d) for d in e]
    if min(ln) < EPS:
        return None
    for i in range(4):
        a, b = e[i], e[(i + 1) % 4]
        if abs(a[0] * b[0] + a[1] * b[1]) > 1e-9 * ln[i] * ln[(i + 1) % 4]:
            return None
    cu = sum(p[0] for p in pts) / 4.0
    cv = sum(p[1] for p in pts) / 4.0
    ux = [e[0][0] / ln[0], e[0][1] / ln[0]]
    return {"kind": "box", "c": [cu, cv], "x": ux, "w": ln[0], "h": ln[1]}


def triangulate(pts: Sequence[Pt]) -> List[List[Pt]]:
    """Ear clipping of a simple counter-clockwise polygon."""
    idx = list(range(len(pts)))
    tris = []

    def inside(p, a, b, c):
        return (_cross_z(a, b, p) >= 0 and _cross_z(b, c, p) >= 0 and _cross_z(c, a, p) >= 0)
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if _cross_z(a, b, c) <= 0:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append([a, b, c])
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append([pts[i] for i in idx])
    return tris


def shape_of(pts, circle: Optional[dict] = None) -> dict:
    """One outline as the shape a shell builds it with."""
    if circle is not None:
        return {"kind": "cylinder", "c": [float(circle["c"][0]), float(circle["c"][1])],
                "r": float(circle["r"])}
    p = _clean(pts)
    box = _rect(p)
    if box is not None:
        return box
    if is_convex(p):
        return {"kind": "prism", "pts": [list(q) for q in p]}
    return {"kind": "triangles", "tris": [[list(q) for q in t] for t in triangulate(p)]}


def polygon_of(poly: dict, circle: Optional[dict] = None) -> dict:
    return {"outer": shape_of(poly["outer"], circle),
            "holes": [shape_of(h) for h in poly.get("holes") or []]}


# ------------------------------------------------------------------ recipe

def _data(plan) -> dict:
    return plan.data if hasattr(plan, "data") else plan


def body_name(role: str, pattern_white: bool, key: str) -> str:
    if role == "pattern":
        return f"{WHITE_BODY if pattern_white else CELLS_BODY} {key}"
    return f"{NAMES[role]} {key}"


def _paint(parts: List[dict], joined: bool) -> List[dict]:
    """REF aruco_feature.paint / _update's appearances, as data."""
    out = []
    for p in parts:
        r = p["role"]
        if r == "pattern":
            out.append({"role": r, "colour": p["colour"], "body": True, "faces": False})
        elif r == "tile":
            out.append({"role": r, "colour": "white", "body": not joined, "faces": True})
        elif r == "pin":
            out.append({"role": r, "colour": "white", "body": False, "faces": True})
    return out


def recipe(plan, base: Optional[Frame] = None, layout: str = "create",
           frame_sketch: bool = True) -> dict:
    """TagPlan (or its dict) -> the recipe. `base`: the target frame in the
    host (origin cm, unit axes); default the target's own frame at the
    host's origin. `layout`: REF create()'s two timeline orders.
    `frame_sketch`: the node leads with its Joint Origin's frame sketch
    (REF jo_v 2, an adapter key the plan never reads)."""
    d = _data(plan)
    base = tuple(list(map(float, v)) for v in (base or IDENTITY))
    if not d.get("ok"):
        return {"schema": SCHEMA, "ok": False, "errors": list(d.get("errors") or []),
                "key": d.get("key") or "tag"}
    if layout not in ("create", "wrap_first"):
        raise ValueError(f"layout {layout!r}: create or wrap_first")
    key = d.get("key") or "tag"
    fr = d["frames"]
    pattern = host_frame(base, fr["pattern_in_target"])
    opencv = host_frame(base, fr["opencv_target"])
    by_part: Dict[str, Dict[int, List[dict]]] = {}
    for L in d["layers"]:
        circles = L.get("circles") or []
        polys = L["polygons"]
        use_c = len(circles) == len(polys)
        step = {"layer": L["name"], "step": L["step"], "colour": L["colour"],
                "z": [float(L["z"][0]), float(L["z"][1])],
                "polygons": [polygon_of(q, circles[i] if use_c else None)
                             for i, q in enumerate(polys)]}
        by_part.setdefault(L["part"], {}).setdefault(int(L["solid"]), []).append(step)
    pattern_white = any(L["part"] == "pattern" and L["step"] == "add" and L["colour"] == "white"
                        for L in d["layers"])
    joined = any(c["part"] == "tile" and c["op"] == "join" for c in d["combines"])
    parts = []
    for role in d["parts"]:
        solids = by_part.get(role, {})
        colours = [s["colour"] for st in solids.values() for s in st if s["step"] == "add"]
        part_op = next((L["op"] for L in d["layers"] if L["part"] == role), None)
        parts.append({"role": role, "name": body_name(role, pattern_white, key), "op": part_op,
                      "colour": colours[0] if colours else "none",
                      "solids": [{"index": k, "steps": solids[k]} for k in sorted(solids)]})
    combines = [dict(c) for c in d["combines"]]
    has_cb = {c["part"] for c in combines if c["op"] != "new"}
    timeline: List[list] = [["sketch", FRAME_SKETCH]] if frame_sketch else []
    if layout == "create":
        for p in parts:
            timeline.append(["base", p["role"]])
            if p["role"] in has_cb:
                timeline.append(["combine", p["role"]])
    else:
        timeline += [["base", p["role"]] for p in parts]
        timeline += [["combine", p["role"]] for p in parts if p["role"] in has_cb]
    return {"schema": SCHEMA, "ok": True, "errors": [], "key": key, "layout": layout,
            "parts": parts, "combines": combines, "paint": _paint(parts, joined),
            "joined": joined, "pattern_white": pattern_white,
            "frames": {"base_cm": [list(v) for v in base],
                       "pattern_cm": [list(v) for v in pattern],
                       "opencv_cm": [list(v) for v in opencv]},
            "frame_sketch": {"name": f"{FRAME_SKETCH} {key}",
                             "points_cm": [list(p) for p in frame_points(opencv)]},
            "timeline": timeline}


def steps(rec: dict):
    """Every step of a recipe in build order: (part, solid index, step)."""
    for p in rec.get("parts", []):
        for s in p["solids"]:
            for st in s["steps"]:
                yield p, s["index"], st
