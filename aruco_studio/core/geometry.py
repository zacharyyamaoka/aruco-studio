"""Vectors, rigid frames, loops and the Joint Origin maths, as plain numbers.

Ported from REF (cad-exporter c8216ff), adsk-free bodies only:

| From | What |
|---|---|
| `ArucoMarkers/aruco_tags.py` | `_v`, `_sub`, `_dot`, `_cross`, `_unit`, `_rot` (Rodrigues), `_area2`, `_frame_error`, `_solve3`, and the composition maths of `_place_joint_origin` as `jo_decompose` / `jo_compose` |
| `ArucoMarkers/aruco_feature.py` | `_rotz`, `_xf_point` / `_xf_vector` / `_xf_frame` (Fusion's `Matrix3D.transformBy` on a row-major 16-number array), `_chain`, `_inside_loops`, `_is_box`, `_loops_mm` |

`aruco_tags._dot` (p0 + p1 + p2) and `aruco_feature._dot` (sum(), which
starts from the int 0) differ in one bit: the sign of a zero (0 + -0.0 is
+0.0), and `atan2` sees that sign. So both are kept: `_dot` is aruco_tags',
`_dot_f` is aruco_feature's and only aruco_feature's functions call it.
`_unit` sums squares (never -0.0), so one copy is exact for both.

How Fusion composes a Joint Origin from (angle, offsets, flip) on a geometry
whose own frame is (o, x, y, z), measured with `jo_probe` on 2026-10-08
(Fusion 2705.1.15), REF `aruco_tags._place_joint_origin`'s docstring:

    x' = x turned by `angle` about the geometry's own (UNFLIPPED) z
    isFlipped: the frame turns half a turn about x' (y and z negate)
    origin = o + offsetX x' + offsetY y' + offsetZ z'  (the FINAL axes)

`jo_decompose(base, target)` is REF's first solve (the numbers it hands to
Fusion); `jo_compose(base, angle, offsets, flip)` is that convention forward.
The read-back fallback (probe Joint Origins when Fusion disagrees) needs
Fusion and stays in the adapter. Angles are RADIANS (Fusion's
`ValueInput.createByReal`), lengths in whatever unit the frames are in.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

Vec = List[float]
Frame = Tuple[Sequence[float], Sequence[float], Sequence[float], Sequence[float]]


# ------------------------------------------------------- vectors (aruco_tags)

def _v(p):
    return [p.x, p.y, p.z]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _dot_f(a, b):
    """aruco_feature._dot (any length)."""
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return [a[0] / n, a[1] / n, a[2] / n]


def _unit_f(a):
    """aruco_feature._unit (any length)."""
    n = math.sqrt(sum(c * c for c in a)) or 1.0
    return [c / n for c in a]


def _rot(v, axis, deg):
    """Rodrigues: v rotated about unit `axis` by `deg`."""
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    k = axis
    kxv = _cross(k, v)
    kdv = _dot(k, v)
    return [v[i] * c + kxv[i] * s + k[i] * kdv * (1 - c) for i in range(3)]


def _area2(pts):
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def _frame_error(a, b):
    """(position error, worst axis angle rad) between two frames."""
    d = _sub(a[0], b[0])
    pos = math.sqrt(_dot(d, d))
    ang = 0.0
    for i in (1, 2, 3):
        c = max(-1.0, min(1.0, _dot(a[i], b[i])))
        ang = max(ang, math.acos(c))
    return pos, ang


def _solve3(cols, b):
    """x with x0*c0 + x1*c1 + x2*c2 = b (Cramer), None when singular."""
    def det(a, b_, c):
        return _dot(a, _cross(b_, c))
    d = det(*cols)
    if abs(d) < 1e-12:
        return None
    return [det(b, cols[1], cols[2]) / d, det(cols[0], b, cols[2]) / d,
            det(cols[0], cols[1], b) / d]


# --------------------------------------------------- frames (aruco_feature)

def _rotz(x, z, deg):
    if not deg:
        return x
    return _unit_f(_rot(x, z, deg))


def _xf_point(m, p):
    """Fusion's Point3D.transformBy with a Matrix3D set from the row-major
    16 numbers `m` (affine: the last row is 0 0 0 1)."""
    x, y, z = (float(c) for c in p)
    return [m[0] * x + m[1] * y + m[2] * z + m[3],
            m[4] * x + m[5] * y + m[6] * z + m[7],
            m[8] * x + m[9] * y + m[10] * z + m[11]]


def _xf_vector(m, v):
    """Fusion's Vector3D.transformBy (no translation), then unit length, as
    aruco_feature._xf_vector does."""
    x, y, z = (float(c) for c in v)
    return _unit_f([m[0] * x + m[1] * y + m[2] * z,
                  m[4] * x + m[5] * y + m[6] * z,
                  m[8] * x + m[9] * y + m[10] * z])


def _xf_frame(m, fr):
    """(o, x, y, z, *rest) through a rigid matrix."""
    o, x, y, z = fr[:4]
    return (_xf_point(m, o), _xf_vector(m, x), _xf_vector(m, y), _xf_vector(m, z)) + tuple(fr[4:])


# ------------------------------------------------------- loops (aruco_feature)

def _chain(segs, tol=1e-4):
    """Stroked curves of one loop (any order, any direction) -> one polygon."""
    if not segs:
        return []
    d = lambda a, b: sum((p - q) ** 2 for p, q in zip(a, b))  # noqa: E731
    out, rest = list(segs[0]), [list(s_) for s_ in segs[1:]]
    while rest:
        end = out[-1]
        i = min(range(len(rest)), key=lambda k: min(d(end, rest[k][0]), d(end, rest[k][-1])))
        seg = rest.pop(i)
        if d(end, seg[-1]) < d(end, seg[0]):
            seg.reverse()
        out += seg[1:]
    if len(out) > 1 and d(out[0], out[-1]) < tol * tol:
        out.pop()
    return out


def _inside_loops(loops, u, v):
    """Even-odd: is (u, v) inside the region these closed polygons bound?"""
    inside = False
    for lp in loops:
        n = len(lp)
        for i in range(n):
            (x0, y0), (x1, y1) = lp[i - 1], lp[i]
            if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


def _is_box(loops_m, w_cm, h_cm):
    """One loop that fills its w x h bounding box: a plain rectangle."""
    if len(loops_m) != 1:
        return False
    lp = loops_m[0]
    area = 0.5 * abs(sum(lp[i][0] * lp[i - 1][1] - lp[i - 1][0] * lp[i][1]
                         for i in range(len(lp))))
    box = (w_cm / 100.0) * (h_cm / 100.0)
    return box > 0 and abs(area - box) <= 1e-3 * box


def _loops_mm(loops_m, base, o, x, y):
    """Loops (metres, in the base frame (o, x, y) they were read in) -> mm in
    the PATTERN frame: centred on `o`, along the fitted, flipped and turned
    x / y (all in the same plane, so a plain re-projection)."""
    bo, bx, by = base[0], base[1], base[2]
    out = []
    for lp in loops_m or ():
        pts = []
        for (u, v) in lp:
            p = [bo[i] + bx[i] * u * 100.0 + by[i] * v * 100.0 - o[i] for i in range(3)]
            pts.append((_dot_f(p, x) * 10.0, _dot_f(p, y) * 10.0))
        if len(pts) >= 3:
            out.append(pts)
    return out


# ------------------------------------------------ the Joint Origin maths

def jo_decompose(base: Frame, target: Frame) -> Tuple[float, Tuple[float, float, float], bool]:
    """The (angle rad, (offsetX, offsetY, offsetZ), isFlipped) that put a
    Joint Origin on a geometry whose frame is `base` = (o, x, y, z) at
    `target` = (o, x, y, z). REF aruco_tags._place_joint_origin's first
    solve, line for line (bo, bx, by, bz = _jo_probe(comp, geo))."""
    to, tx, _ty, tz = target
    bo, bx, by, bz = base
    flip = _dot(bz, tz) < 0
    a = math.atan2(_dot(tx, by), _dot(tx, bx))
    s = -1.0 if flip else 1.0
    fx = [math.cos(a) * bx[i] + math.sin(a) * by[i] for i in range(3)]
    fy = [s * (-math.sin(a) * bx[i] + math.cos(a) * by[i]) for i in range(3)]
    fzv = [s * c for c in bz]
    d = _sub(to, bo)
    return (a, (_dot(d, fx), _dot(d, fy), _dot(d, fzv)), flip)


def jo_compose(base: Frame, angle: float, offsets: Sequence[float] = (0.0, 0.0, 0.0),
               flip: bool = False) -> Tuple[Vec, Vec, Vec, Vec]:
    """The frame Fusion makes from (angle rad, offsets, flip) on a geometry
    whose frame is `base`, by the measured convention above."""
    bo, bx, by, bz = base
    s = -1.0 if flip else 1.0
    c, sn = math.cos(angle), math.sin(angle)
    x1 = [c * bx[i] + sn * by[i] for i in range(3)]
    y1 = [s * (-sn * bx[i] + c * by[i]) for i in range(3)]
    z1 = [s * v for v in bz]
    ox, oy, oz = (float(v) for v in offsets)
    o1 = [bo[i] + ox * x1[i] + oy * y1[i] + oz * z1[i] for i in range(3)]
    return o1, x1, y1, z1


def frame_of_matrix(m: Sequence[float]) -> Tuple[Vec, Vec, Vec, Vec]:
    """A row-major 4x4 (16 numbers) -> (origin, x, y, z): the columns."""
    return ([m[3], m[7], m[11]], [m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]])


def matrix_of_frame(o, x, y, z) -> List[float]:
    """(origin, x, y, z) -> a row-major 4x4 (16 numbers)."""
    return [x[0], y[0], z[0], o[0], x[1], y[1], z[1], o[1], x[2], y[2], z[2], o[2],
            0.0, 0.0, 0.0, 1.0]
