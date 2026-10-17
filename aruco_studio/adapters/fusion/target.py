"""A clicked face or sketch profile -> `plan.Target` + the base frame.

The plan never sees an entity (ARCHITECTURE 5.1). This module reads the
entity once and hands over numbers:

| Read | REF (cad-exporter c8216ff) | Into |
|---|---|---|
| the face's normal, its longest straight edge, its extents | `aruco_tags.face_frame` | the base frame (o, x, y, z, w, h) in cm |
| a face tag's x as made (an upstream edit can reverse the longest edge) | `aruco_feature.keep_x` | the base frame's x; `Target.x_ref` |
| a profile's sketch axes, `x_sketch`, `z_sign`, the legacy `rotate_deg` | `profile_rect`, `sketch_axes` | the base frame |
| every loop, stroked as Fusion strokes an edge | `face_loops_2d`, `_profile_points` | `Target.loops_mm` (mm, base frame) |
| the body under, boxed in the base frame, and whether it was measured | `_trim_face_body`, `_body_extent_mm`, `_trim_inputs` | `Target.body_mm`, `has_body` |

`keep_x` is pure maths kept here verbatim; docs/FUSION_ADAPTER.md asks the
core for it (Core requests).
"""
from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from ...plan.target import Target
from .api import cross, dot, sub, unit, vec

STROKE_TOL_CM = 0.005                     # REF face_loops_2d's chord tolerance


def _rot(v, axis, deg):
    """Rodrigues (REF aruco_tags._rot)."""
    k = unit(axis)
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    kxv = cross(k, v)
    kd = dot(k, v)
    return [v[i] * c + kxv[i] * s + k[i] * kd * (1 - c) for i in range(3)]


def keep_x(x, y, z, w, h, x_base, square_tol=1e-6):
    """REF aruco_feature.keep_x, verbatim: the creation's direction wins (a
    flip, or on a square face any quarter turn). -> (x, y, w, h)."""
    if not x_base:
        return x, y, w, h
    if abs(w - h) <= square_tol * max(w, h, 1e-9):
        cands = [(x, y, w, h), (y, [-c for c in x], h, w),
                 ([-c for c in x], [-c for c in y], w, h), ([-c for c in y], x, h, w)]
        return max(cands, key=lambda c: dot(c[0], x_base))
    if dot(x, x_base) < -1e-6:
        x = [-c for c in x]
        return x, cross(z, x), w, h
    return x, y, w, h


def native_of(ent):
    try:
        if ent is not None and ent.assemblyContext is not None:
            return ent.nativeObject
    except Exception:                              # noqa: BLE001
        pass
    return ent


def face_frame(face, rotate_deg=0.0):
    """REF aruco_tags.face_frame: (origin, x, y, z, w_cm, h_cm)."""
    face = native_of(face)
    _ok, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
    z = unit(vec(normal))
    best, best_len = None, -1.0
    for e in face.edges:
        g = e.geometry
        if isinstance(g, adsk.core.Line3D):
            d = sub(vec(g.endPoint), vec(g.startPoint))
            ln = math.sqrt(dot(d, d))
            if ln > best_len:
                best, best_len = d, ln
    if best is None:
        best = vec(face.geometry.uDirection)
    x = unit(sub(best, [z[i] * dot(best, z) for i in range(3)]))
    if rotate_deg:
        x = unit(_rot(x, z, rotate_deg))
    y = cross(z, x)
    pts = [vec(v.geometry) for v in face.vertices] or [vec(face.pointOnFace)]
    p0 = vec(face.pointOnFace)
    xs = [dot(sub(p, p0), x) for p in pts]
    ys = [dot(sub(p, p0), y) for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
    o = [p0[i] + x[i] * cx + y[i] * cy for i in range(3)]
    return o, x, y, z, max(xs) - min(xs), max(ys) - min(ys)


def face_loops_mm(face, o, x, y, tol_cm=STROKE_TOL_CM):
    """REF face_loops_2d, in mm: every loop as a 2D polygon in (o, x, y)."""
    loops = []
    for loop in native_of(face).loops:
        pts = []
        for co in loop.coEdges:
            ev = co.edge.evaluator
            _ok, p0, p1 = ev.getParameterExtents()
            ok, strokes = ev.getStrokes(p0, p1, tol_cm)
            seg = [vec(p) for p in strokes] if ok else []
            if co.isOpposedToEdge:
                seg.reverse()
            for p in seg[:-1] if seg else []:
                d = sub(p, o)
                pts.append((dot(d, x) * 10.0, dot(d, y) * 10.0))
        if len(pts) >= 3:
            loops.append(pts)
    return loops


def body_box_mm(body, o, x, y, z):
    """The body under, boxed in the base frame (mm), from its bounding box
    corners. REF measures oriented boxes and volumes (`_trim_measure`); that
    is Fusion-gated, so `measured` says whether a volume was read."""
    try:
        bb = body.boundingBox
        lo, hi = vec(bb.minPoint), vec(bb.maxPoint)
    except Exception:                              # noqa: BLE001
        return None
    corners = [[(lo, hi)[i][0], (lo, hi)[j][1], (lo, hi)[k][2]]
               for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    us = [dot(sub(c, o), x) * 10.0 for c in corners]
    vs = [dot(sub(c, o), y) * 10.0 for c in corners]
    zs = [dot(sub(c, o), z) * 10.0 for c in corners]
    try:
        vol = float(body.physicalProperties.volume)
    except Exception:                              # noqa: BLE001
        vol = 0.0
    return {"u0": min(us), "v0": min(vs), "u1": max(us), "v1": max(vs), "z0": min(zs),
            "z1": max(zs), "measured": vol > 0.0}


def of_face(face, s):
    """A planar face -> (Target, base (o, x, y, z, w_cm, h_cm), keys to store
    at creation {"x_base"})."""
    o, x, y, z, w, h = face_frame(face, float(s.get("rotate_deg", 0) or 0))
    x_base = s.get("x_base")
    keys = {} if x_base else {"x_base": [round(c, 12) for c in x]}
    x, y, w, h = keep_x(x, y, z, w, h, x_base)
    loops = face_loops_mm(face, o, x, y)
    body = getattr(native_of(face), "body", None)
    box = body_box_mm(body, o, x, y, z) if body is not None else None
    xr = s.get("x_ref")
    x_ref = (dot(xr, x), dot(xr, y)) if xr else None
    t = Target(kind="face", w_mm=w * 10.0, h_mm=h * 10.0, loops_mm=loops,
               has_body=body is not None, z_sign=1, x_ref=x_ref, body_mm=box)
    return t, (o, x, y, z, w, h), keys


def sketch_axes(sk):
    P = adsk.core.Point3D.create
    o0 = vec(sk.sketchToModelSpace(P(0, 0, 0)))
    ex = sub(vec(sk.sketchToModelSpace(P(1, 0, 0))), o0)
    ey = sub(vec(sk.sketchToModelSpace(P(0, 1, 0))), o0)
    return o0, unit(ex), unit(ey), unit(cross(ex, ey))


def _profile_loops(profile):
    sk = profile.parentSketch
    loops = []
    for loop in profile.profileLoops:
        pts = []
        for pc in loop.profileCurves:
            ev = pc.geometry.evaluator
            _ok, p0, p1 = ev.getParameterExtents()
            ok, strokes = ev.getStrokes(p0, p1, 0.01)
            seg = [vec(sk.sketchToModelSpace(q)) for q in (strokes if ok else [])]
            pts += seg[:-1]
        loops.append(pts)
    return loops


def of_profile(profile, s, body_under=None):
    """A sketch profile -> (Target, base, keys). REF profile_rect: x along
    s["x_sketch"], the side by s["z_sign"] (and the old "flip"), the legacy
    rotate_deg; the plane through the sketch."""
    profile = native_of(profile)
    o0, ex, ey, ez = sketch_axes(profile.parentSketch)
    xs = s.get("x_sketch") or [1.0, 0.0]
    x = unit([ex[i] * xs[0] + ey[i] * xs[1] for i in range(3)])
    sign = float(s.get("z_sign", 1)) * (-1.0 if s.get("flip") else 1.0)
    z = [c * sign for c in ez]
    rd = float(s.get("rotate_deg", 0) or 0)
    if rd:
        x = unit(_rot(x, z, rd))
    y = cross(z, x)
    loops3 = _profile_loops(profile)
    pts = [p for lp in loops3 for p in lp]
    if not pts:
        raise ValueError("the profile has no curves")
    p0 = pts[0]
    us = [dot(sub(p, p0), x) for p in pts]
    vs = [dot(sub(p, p0), y) for p in pts]
    cu, cv = (min(us) + max(us)) / 2.0, (min(vs) + max(vs)) / 2.0
    o = [p0[i] + x[i] * cu + y[i] * cv for i in range(3)]
    off = dot(sub(o, o0), ez)
    o = [o[i] - ez[i] * off for i in range(3)]
    w, h = max(us) - min(us), max(vs) - min(vs)
    loops = [[(dot(sub(p, o), x) * 10.0, dot(sub(p, o), y) * 10.0) for p in lp] for lp in loops3]
    box = body_box_mm(body_under, o, x, y, z) if body_under is not None else None
    t = Target(kind="profile" if body_under is not None else "free", w_mm=w * 10.0,
               h_mm=h * 10.0, loops_mm=loops, has_body=body_under is not None,
               z_sign=int(s.get("z_sign", 1)), x_ref=None, body_mm=box)
    return t, (o, x, y, z, w, h), {}


def read(entity, s, body_under=None):
    """Either kind. -> (Target, base, creation keys)."""
    if adsk.fusion.Profile.cast(entity) is not None:
        return of_profile(entity, s, body_under)
    return of_face(entity, s)
