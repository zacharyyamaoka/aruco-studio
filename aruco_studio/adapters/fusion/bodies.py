"""The recipe's shapes as temporary bodies (TemporaryBRepManager).

REF builds every tag body from boxes (`cells_temp_body`, `label_temp_body`,
`_box`), cylinders (`_prism` for a round pin) and convex prisms made as a
box minus one big box per slanted side (`poly_prism_temp_body`, `_prism`).
This module does the same, shape by shape, step by step, so a node rebuilt
from a TagPlan has the bodies today's node has:

| Recipe | TBM calls |
|---|---|
| `box` | `createBox(OrientedBoundingBox3D(centre, x, y, w, h, z extent))` |
| `cylinder` | `createCylinderOrCone(p0, r, p1, r)` |
| `prism` (convex) | the polygon's box, then `booleanOperation(Difference)` with one big box per side that is not on the box (REF's construction, no coplanar cut) |
| `triangles` (concave) | one convex prism per triangle, united |
| a polygon's `holes` | each hole as a prism, taken away |
| a step | its polygons united (REF unites cell after cell) |
| a solid | its first step, then each step united (`add`) or taken away (`sub`) |
| a part | its solids united (REF `_union`) |

Everything is placed by the recipe's `frames.pattern_cm`; lengths go in as
mm / 10 (Fusion's cm). No number is made here.
"""
from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from .. import recipe as RC
from .api import P, V, tbm

UNION = "UnionBooleanType"
DIFF = "DifferenceBooleanType"


def _bool(target, tool, kind):
    tbm().booleanOperation(target, tool, getattr(adsk.fusion.BooleanTypes, kind))
    return target


def _axes(pf, ux):
    """The pattern frame's in-plane direction (ux, uy) in the host."""
    _o, x, y, _z = pf
    xd = [x[i] * ux[0] + y[i] * ux[1] for i in range(3)]
    yd = [-x[i] * ux[1] + y[i] * ux[0] for i in range(3)]
    return xd, yd


def box(pf, c, ux, w_mm, h_mm, lo_mm, hi_mm):
    xd, yd = _axes(pf, ux)
    ctr = RC.to_host(pf, c[0], c[1], (lo_mm + hi_mm) / 2.0)
    return tbm().createBox(adsk.core.OrientedBoundingBox3D.create(
        P(ctr), V(xd), V(yd), w_mm / 10.0, h_mm / 10.0, (hi_mm - lo_mm) / 10.0))


def cylinder(pf, c, r_mm, lo_mm, hi_mm):
    return tbm().createCylinderOrCone(P(RC.to_host(pf, c[0], c[1], lo_mm)), r_mm / 10.0,
                                      P(RC.to_host(pf, c[0], c[1], hi_mm)), r_mm / 10.0)


def prism(pf, pts_mm, lo_mm, hi_mm):
    """REF poly_prism_temp_body: a CONVEX polygon's box minus one big box
    per side that does not lie on the box (mm in, cm out)."""
    pts = [(float(u), float(v)) for u, v in pts_mm]
    if RC._area2(pts) < 0:
        pts = pts[::-1]
    us, vs = [p[0] for p in pts], [p[1] for p in pts]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    body = box(pf, ((u0 + u1) / 2.0, (v0 + v1) / 2.0), (1.0, 0.0), u1 - u0, v1 - v0,
               lo_mm, hi_mm)
    big = 4.0 * max(u1 - u0, v1 - v0)
    eps = 1e-8
    for i in range(len(pts)):
        (a, b), (p, q) = pts[i], pts[(i + 1) % len(pts)]
        if (abs(a - p) < eps and (abs(a - u0) < eps or abs(a - u1) < eps)) or \
                (abs(b - q) < eps and (abs(b - v0) < eps or abs(b - v1) < eps)):
            continue
        du, dv = p - a, q - b
        ln = math.hypot(du, dv)
        tu, tv = du / ln, dv / ln
        nu, nv = tv, -tu                                  # outward (CCW polygon)
        mu, mv = (a + p) / 2.0 + nu * big / 2.0, (b + q) / 2.0 + nv * big / 2.0
        cut = box(pf, (mu, mv), (tu, tv), big * 2.0, big, lo_mm - 1.0, hi_mm + 1.0)
        _bool(body, cut, DIFF)
    return body


def shape(pf, s, lo_mm, hi_mm):
    k = s["kind"]
    if k == "box":
        return box(pf, s["c"], s["x"], s["w"], s["h"], lo_mm, hi_mm)
    if k == "cylinder":
        return cylinder(pf, s["c"], s["r"], lo_mm, hi_mm)
    if k == "prism":
        return prism(pf, s["pts"], lo_mm, hi_mm)
    if k == "triangles":
        body = None
        for t in s["tris"]:
            b = prism(pf, t, lo_mm, hi_mm)
            body = b if body is None else _bool(body, b, UNION)
        return body
    raise ValueError(f"unknown shape {k!r}")


def polygon(pf, poly, lo_mm, hi_mm):
    body = shape(pf, poly["outer"], lo_mm, hi_mm)
    for h in poly.get("holes") or []:
        _bool(body, shape(pf, h, lo_mm - 0.1, hi_mm + 0.1), DIFF)
    return body


def step_body(pf, step):
    lo, hi = step["z"]
    body = None
    for poly in step["polygons"]:
        b = polygon(pf, poly, lo, hi)
        body = b if body is None else _bool(body, b, UNION)
    return body


def solid_body(pf, solid):
    body = None
    for st in solid["steps"]:
        b = step_body(pf, st)
        if b is None:
            continue
        if body is None:
            if st["step"] == "sub":
                continue                    # nothing to take it from (never in a plan)
            body = b
        else:
            _bool(body, b, UNION if st["step"] == "add" else DIFF)
    return body


def part_body(rec, part):
    """One part's temporary body, placed in the host (REF `part_body`)."""
    pf = rec["frames"]["pattern_cm"]
    body = None
    for s in part["solids"]:
        b = solid_body(pf, s)
        if b is None:
            continue
        body = b if body is None else _bool(body, b, UNION)
    return body


def part_bodies(rec):
    """{role: temporary body} in the recipe's part order."""
    return {p["role"]: part_body(rec, p) for p in rec["parts"]}
