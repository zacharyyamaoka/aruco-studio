"""Shapes of the design file (docs/FILE_FORMAT.md) to loops, and the faces of
an extruded shape to Targets. Standard library only.

| Function | Gives |
|---|---|
| `stroke(shape)` | the shape's loops in its own frame (mm): the outer loop counter-clockwise, then each hole clockwise, a circle and a slot's arcs at the chord tolerance (`CHORD_MM`, `core.faces._arc_pts`) |
| `edges(shape)` | the outer loop's edges: `[(p0, p1, straight)]`; the straight ones are the side faces `side0`, `side1`, ... |
| `face_names(shape)` | the faces of the shape's extrude: `top`, `bottom`, `side<i>`, and `front` / `right` / `back` / `left` on a rectangle |
| `bare_target(shape)` | the Target of a tag on the shape itself (no body) |
| `face_target(shape, height, face)` | `FaceTarget`: the Target of a tag on one face of the shape's extrude, its 3D frame and its place in the 2D net, both in the shape's frame |

A shape is a dict with exactly one of `rect: [w, h]`, `circle: d`,
`polygon: [[x, y], ...]`, `slot: [length, width]`, `loops: [[[x, y], ...], ...]`,
and optionally `holes: [shape]` placed by their own `at` / `rot` inside it.
Its own `at` / `rot` place it in its sketch; they are not applied here.

The Targets are made by `plan/target.py`'s own calls, in the cases POST
/api/target makes them (a rectangle without holes through `box`, every
other shape through `from_loops(..., centre=False)`), so a tag typed in a
file plans exactly as the target editor's.

Errors raise `ShapeError(path, message)`; `path` is relative to the shape
("holes[1]", "rect").
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..core import faces as _faces
from . import target as _T
from .target import Target

CHORD_MM = _T.CHORD_MM                  # 0.05 mm, plan.target's (M6a; unified at Merge 1)
KINDS = ("rect", "circle", "polygon", "slot", "loops")
RECT_SIDES = ("front", "right", "back", "left")   # -y, +x, +y, -x: edges 0..3 of the rectangle
Pt = Tuple[float, float]


class ShapeError(ValueError):
    def __init__(self, path: str, message: str):
        super().__init__(f"{path}: {message}" if path else message)
        self.path = path
        self.message = message


# ------------------------------------------------------------ small maths

def _num(v, path, positive=False) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ShapeError(path, f"a number, not {v!r}")
    if positive and v <= 0:
        raise ShapeError(path, f"must be more than 0, not {v:g}")
    return float(v)


def _pt(v, path) -> Pt:
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise ShapeError(path, "a point: [x, y]")
    return (_num(v[0], f"{path}[0]"), _num(v[1], f"{path}[1]"))


def area2(pts: Sequence[Pt]) -> float:
    """Twice the signed area (counter-clockwise > 0)."""
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def _ccw(pts, ccw=True):
    pts = [(float(x), float(y)) for x, y in pts]
    if (area2(pts) > 0) != ccw:
        pts.reverse()
    return pts


def _cos_sin(deg: float):
    """cos, sin of an angle in degrees, exact at quarter turns (scene.pose_of's rule)."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if abs(deg % 90.0) < 1e-12:
        c, s = float(round(c)), float(round(s))
    return c, s


def place(pts: Sequence[Pt], at: Pt = (0.0, 0.0), rot: float = 0.0) -> List[Pt]:
    """Points turned by `rot` (deg, CCW) then moved by `at`."""
    if not rot and not at[0] and not at[1]:
        return [(float(x), float(y)) for x, y in pts]
    c, s = _cos_sin(rot)
    return [(at[0] + c * x - s * y, at[1] + s * x + c * y) for x, y in pts]


def inside(loop: Sequence[Pt], p: Pt) -> bool:
    """Point in polygon (even-odd)."""
    x, y = p
    n = len(loop)
    hit = False
    for i in range(n):
        x0, y0 = loop[i - 1]
        x1, y1 = loop[i]
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if xc > x:
                hit = not hit
    return hit


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_cross(p, q, r, s) -> bool:
    d1, d2 = _cross(r, s, p), _cross(r, s, q)
    d3, d4 = _cross(p, q, r), _cross(p, q, s)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 and d2 and d3 and d4


def loop_inside(inner: Sequence[Pt], outer: Sequence[Pt]) -> bool:
    """Is `inner` wholly inside `outer` (every vertex inside, no edges crossing)?"""
    if not all(inside(outer, p) for p in inner):
        return False
    xs = [x for x, _ in inner]
    ys = [y for _, y in inner]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    near = [(outer[j - 1], outer[j]) for j in range(len(outer))       # only what can touch it
            if not (max(outer[j - 1][0], outer[j][0]) < x0 or min(outer[j - 1][0], outer[j][0]) > x1
                    or max(outer[j - 1][1], outer[j][1]) < y0
                    or min(outer[j - 1][1], outer[j][1]) > y1)]
    for i in range(len(inner)):
        a, b = inner[i - 1], inner[i]
        for c, d in near:
            if _segments_cross(a, b, c, d):
                return False
    return True


# ------------------------------------------------------------ one shape

def kind_of(shape, path: str = "") -> str:
    if not isinstance(shape, dict):
        raise ShapeError(path, "a shape: an object with one of " + ", ".join(KINDS))
    ks = [k for k in KINDS if k in shape]
    if len(ks) != 1:
        raise ShapeError(path, ("one of " if not ks else "only one of ") + ", ".join(KINDS)
                         + (f" (it has {', '.join(ks)})" if ks else ""))
    return ks[0]


def at_of(shape, path: str = "") -> Pt:
    return _pt(shape["at"], f"{path}.at" if path else "at") if shape.get("at") is not None \
        else (0.0, 0.0)


def rot_of(shape, path: str = "") -> float:
    v = shape.get("rot")
    return 0.0 if v is None else _num(v, f"{path}.rot" if path else "rot")


def _slot_parts(shape):
    length = _num(shape["slot"][0], "slot[0]", positive=True)
    width = _num(shape["slot"][1], "slot[1]", positive=True)
    if length <= width:
        raise ShapeError("slot", f"a slot's length ({length:g}) must be more than its width "
                                 f"({width:g}): the length is the overall length")
    return length, width


def outline(shape, path: str = "") -> List[Pt]:
    """The outer loop, counter-clockwise, in the shape's frame (no holes)."""
    k = kind_of(shape, path)
    v = shape[k]
    if k == "rect":
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ShapeError("rect", "[w, h]")
        w, h = _num(v[0], "rect[0]", positive=True), _num(v[1], "rect[1]", positive=True)
        return [(-w / 2.0, -h / 2.0), (w / 2.0, -h / 2.0), (w / 2.0, h / 2.0), (-w / 2.0, h / 2.0)]
    if k == "circle":
        d = _num(v, "circle", positive=True)
        return _faces.shape_pts(("circle", 0.0, 0.0, d / 2.0), CHORD_MM)
    if k == "polygon":
        if not isinstance(v, (list, tuple)) or len(v) < 3:
            raise ShapeError("polygon", "three points or more: [[x, y], ...]")
        pts = [_pt(p, f"polygon[{i}]") for i, p in enumerate(v)]
        if abs(area2(pts)) < 1e-12:
            raise ShapeError("polygon", "its points enclose no area")
        if area2(pts) < 0:                     # made counter-clockwise, from the first point
            pts = [pts[0]] + pts[1:][::-1]
        return pts
    if k == "slot":
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            raise ShapeError("slot", "[length, width]")
        length, width = _slot_parts(shape)
        return _faces.shape_pts(("stadium", 0.0, 0.0, length - width, width / 2.0), CHORD_MM)
    # loops: verbatim, the outer first
    if not isinstance(v, (list, tuple)) or not v:
        raise ShapeError("loops", "a list of loops, the outer first")
    lp = v[0]
    if not isinstance(lp, (list, tuple)) or len(lp) < 3:
        raise ShapeError("loops[0]", "a loop of three points or more")
    pts = [_pt(p, f"loops[0][{j}]") for j, p in enumerate(lp)]
    if abs(area2(pts)) < 1e-12:
        raise ShapeError("loops[0]", "the outer loop encloses no area")
    return pts if area2(pts) > 0 else pts[::-1]


def _hole_loops(shape) -> List[Tuple[str, List[Pt]]]:
    """(path, loop) of every hole in the shape's frame, clockwise."""
    out = []
    k = kind_of(shape)
    if k == "loops":
        for i, lp in enumerate(shape["loops"][1:], start=1):
            if not isinstance(lp, (list, tuple)) or len(lp) < 3:
                raise ShapeError(f"loops[{i}]", "a hole: a loop of three points or more")
            pts = [_pt(p, f"loops[{i}][{j}]") for j, p in enumerate(lp)]
            out.append((f"loops[{i}]", _ccw(pts, ccw=False)))
    holes = shape.get("holes") or []
    if not isinstance(holes, list):
        raise ShapeError("holes", "a list of shapes")
    for i, h in enumerate(holes):
        hp = f"holes[{i}]"
        try:
            if isinstance(h, dict) and h.get("holes"):
                raise ShapeError("holes", "a hole never has holes")
            if isinstance(h, dict) and kind_of(h) == "loops" and len(h["loops"]) > 1:
                raise ShapeError("loops", "a hole is one loop")
            pts = place(outline(h), at_of(h), rot_of(h))
        except ShapeError as exc:
            raise ShapeError(f"{hp}.{exc.path}" if exc.path else hp, exc.message) from None
        out.append((hp, pts[::-1] if area2(pts) > 0 else pts))
    return out


def stroke(shape) -> List[List[Pt]]:
    """The shape's loops in its own frame: the outer loop (counter-clockwise),
    then its holes (clockwise). A hole outside its parent raises on its path."""
    outer = outline(shape)
    loops = [outer]
    for hp, lp in _hole_loops(shape):
        if not loop_inside(lp, outer):
            raise ShapeError(hp, "a hole must lie inside its shape")
        loops.append(lp)
    return loops


def has_holes(shape) -> bool:
    return bool(shape.get("holes")) or (kind_of(shape) == "loops" and len(shape["loops"]) > 1)


def edges(shape) -> List[Tuple[Pt, Pt, bool]]:
    """The outer loop's edges (p0, p1, straight), counter-clockwise."""
    k = kind_of(shape)
    if k == "circle":
        return []
    pts = outline(shape)
    if k == "slot":
        length, width = _slot_parts(shape)
        h, r = (length - width) / 2.0, width / 2.0
        return [((-h, -r), (h, -r), True), ((h, r), (-h, r), True)]
    return [(pts[i], pts[(i + 1) % len(pts)], True) for i in range(len(pts))]


def face_names(shape) -> List[str]:
    k = kind_of(shape)
    names = ["top", "bottom"] + [f"side{i}" for i in range(len(edges(shape)))]
    if k == "rect":
        names += list(RECT_SIDES)
    return names


def _name(shape) -> str:
    n = shape.get("name", "")
    return n if isinstance(n, str) else ""


def bare_target(shape) -> Target:
    """A tag on the shape itself, with nothing under it: POST /api/target's
    thickness-0 target (kind "face", no body)."""
    return extruded_top(shape, 0.0)


def extruded_top(shape, thickness_mm: float) -> Target:
    """The shape's top as POST /api/target makes it: a rectangle without
    holes through `box`, everything else through `from_loops(centre=False)`."""
    loops = stroke(shape)
    th = abs(float(thickness_mm))
    if kind_of(shape) == "rect" and not has_holes(shape):
        w, h = shape["rect"]
        t = _T.box(float(w), float(h), th)
    else:
        t = _T.from_loops(loops, th, centre=False)
    t.name = _name(shape)
    return t


@dataclass
class FaceTarget:
    target: Target
    frame: List[float]                 # the face frame in the shape's frame: a row-major 4x4 (mm)
    net: Tuple[float, float, float]    # where the target's 2D frame lies in the plan view: (x, y, deg)
    hinge: Optional[Tuple[Pt, Pt]]     # the edge a side face unfolds about (the shape's frame)
    face: str                          # top, bottom or side<i>
    normal: Tuple[float, float, float]


def _side_index(shape, face: str) -> int:
    k = kind_of(shape)
    if face in RECT_SIDES:
        if k != "rect":
            if k == "circle":
                raise ShapeError("", f"{face!r}: a circle's side is curved and has no flat face")
            raise ShapeError("", f"{face!r} names a rectangle's side: this shape has "
                                 f"side0..side{len(edges(shape)) - 1}")
        return RECT_SIDES.index(face)
    if not face.startswith("side") or not face[4:].isdigit():
        raise ShapeError("", f"no face {face!r}: top, bottom, side<i>"
                             + (", front, right, back, left" if k == "rect" else ""))
    i = int(face[4:])
    es = edges(shape)
    if k == "circle":
        raise ShapeError("", f"{face!r}: a circle's side is curved and has no flat face")
    if i >= len(es):
        extra = " (its ends are curved)" if k == "slot" else ""
        raise ShapeError("", f"no {face}: this {k} has {len(es)} flat sides, side0..side"
                             f"{len(es) - 1}{extra}")
    return i


def face_target(shape, height: float, face: str) -> FaceTarget:
    """The Target of a tag on `face` of the shape's extrude (z 0 .. height;
    negative: downwards), with its frame. Right-handed frames, z = the
    face's outward normal; every length mm, in the shape's frame."""
    h = _num(height, "height")
    if h == 0:
        raise ShapeError("height", "an extrude needs a height other than 0")
    th = abs(h)
    z_top, z_bot = max(0.0, h), min(0.0, h)
    if face == "top":
        t = extruded_top(shape, th)
        fr = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, z_top, 0.0, 0.0, 0.0, 1.0]
        return FaceTarget(t, fr, (0.0, 0.0, 0.0), None, "top", (0.0, 0.0, 1.0))
    if face == "bottom":
        loops = stroke(shape)
        if kind_of(shape) == "rect" and not has_holes(shape):
            w, hh = shape["rect"]
            t = _T.box(float(w), float(hh), th)
        else:
            t = _T.from_loops([[(-x, y) for x, y in lp] for lp in loops], th, centre=False)
        t.z_sign = -1
        t.name = _name(shape)
        fr = [-1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, -1.0, z_bot, 0.0, 0.0, 0.0, 1.0]
        y0 = min(y for _x, y in loops[0])
        # the net: unfolded through the front, below the front side's flap
        return FaceTarget(t, fr, (0.0, 2.0 * y0 - th, 180.0), None, "bottom", (0.0, 0.0, -1.0))
    i = _side_index(shape, face)
    (x0, y0), (x1, y1), _straight = edges(shape)[i]
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 1e-9:
        raise ShapeError("", f"side{i} has no length")
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    nx, ny = dy, -dx                                  # outward: right of a counter-clockwise edge
    depth = max((x0 - x) * nx + (y0 - y) * ny for x, y in outline(shape))
    t = Target(kind="face", w_mm=length, h_mm=th, loops_mm=[], has_body=True,
               body_mm={"u0": -length / 2.0, "v0": -th / 2.0, "u1": length / 2.0, "v1": th / 2.0,
                        "z0": -depth, "z1": 0.0, "depth": depth, "measured": True},
               body_loops_mm=None, name=_name(shape))
    mx, my, mz = (x0 + x1) / 2.0, (y0 + y1) / 2.0, (z_top + z_bot) / 2.0
    fr = [dx, 0.0, nx, mx, dy, 0.0, ny, my, 0.0, 1.0, 0.0, mz, 0.0, 0.0, 0.0, 1.0]
    ang = math.degrees(math.atan2(dy, dx))
    if abs(ang - round(ang)) < 1e-9:
        ang = float(round(ang))
    net = (mx + nx * th / 2.0, my + ny * th / 2.0, ang)
    return FaceTarget(t, fr, net, ((x0, y0), (x1, y1)), f"side{i}", (nx, ny, 0.0))
