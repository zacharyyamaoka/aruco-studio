"""A plain build: each layer as a sketch and an extrude (no custom feature).

For a design that should hold ordinary, editable features instead of the
ArUco Extrude node (the 2026-10-07 tag was built this way: REF
`aruco_tags.add_tag` / `aruco_extrude`). It is not today's tag, so it does
not have to rebuild today's bodies; the custom feature (feature.py, with
bodies.py) does. Same recipe, other calls:

| Recipe | Fusion calls |
|---|---|
| a step | a sketch on the target's plane (the face itself, or the profile's sketch plane) with every outline drawn: lines for a box / prism / triangle, a circle for a cylinder |
| its z | an extrude of every profile of that sketch: start offset `z[0]`, distance `z[1] - z[0]` (signs flipped when the sketch's normal points against the pattern's z) |
| the first step of a part | operation New body |
| a later `add` / `sub` step | Join / Cut with the part's body as the only participant |
| a polygon's holes | one more Cut of the holes (a sketch region inside another is its own profile in Fusion; drawing them apart keeps the profile choice trivial) |
| `combines` | combine features, as feature.py |

Every number is the recipe's; nothing is sized here.
"""
from __future__ import annotations

import adsk.core
import adsk.fusion

from .. import recipe as RC
from .api import P, dot, op, unit, vec


def _corners(shape):
    k = shape["kind"]
    if k == "box":
        (cu, cv), (ax, ay), w, h = shape["c"], shape["x"], shape["w"], shape["h"]
        bx, by = -ay, ax
        return [[(cu + sx * ax * w / 2 + sy * bx * h / 2, cv + sx * ay * w / 2 + sy * by * h / 2)
                 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]]
    if k == "prism":
        return [[tuple(p) for p in shape["pts"]]]
    if k == "triangles":
        return [[tuple(p) for p in t] for t in shape["tris"]]
    return []


def _polyline(sk, pts_model):
    lines = sk.sketchCurves.sketchLines
    q = [sk.modelToSketchSpace(P(p)) for p in pts_model]
    first = lines.addByTwoPoints(q[0], q[1])
    prev = first
    for p in q[2:]:
        prev = lines.addByTwoPoints(prev.endSketchPoint, p)
    lines.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)


def draw(sk, pf, shapes):
    """Every shape on the pattern plane (z = 0), in the sketch."""
    for s in shapes:
        if s["kind"] == "cylinder":
            c = sk.modelToSketchSpace(P(RC.to_host(pf, s["c"][0], s["c"][1], 0.0)))
            sk.sketchCurves.sketchCircles.addByCenterRadius(c, s["r"] / 10.0)
            continue
        for loop in _corners(s):
            _polyline(sk, [RC.to_host(pf, u, v, 0.0) for u, v in loop])


def _sign(sk, pf):
    """+1 when the sketch's normal is the pattern's z, -1 when opposed."""
    o = vec(sk.sketchToModelSpace(adsk.core.Point3D.create(0, 0, 0)))
    zt = vec(sk.sketchToModelSpace(adsk.core.Point3D.create(0, 0, 1)))
    n = unit([zt[i] - o[i] for i in range(3)])
    return 1.0 if dot(n, pf[3]) >= 0 else -1.0


def extrude(comp, plane, pf, shapes, lo_mm, hi_mm, operation, body=None, name=""):
    """One sketch of `shapes`, every profile extruded lo..hi mm."""
    sk = comp.sketches.add(plane)
    if name:
        sk.name = name
    draw(sk, pf, shapes)
    sign = _sign(sk, pf)
    profs = adsk.core.ObjectCollection.create()
    for i in range(sk.profiles.count):
        profs.add(sk.profiles.item(i))
    ext = comp.features.extrudeFeatures
    inp = ext.createInput(profs, op(operation))
    VI = adsk.core.ValueInput.createByReal
    inp.startExtent = adsk.fusion.OffsetStartDefinition.create(VI(sign * lo_mm / 10.0))
    inp.setDistanceExtent(False, VI(sign * (hi_mm - lo_mm) / 10.0))
    if body is not None:
        inp.participantBodies = [body]
    return ext.add(inp)


def plane_of(entity):
    """The plane a target's sketches go on: the face itself, or the profile's
    own sketch plane."""
    prof = adsk.fusion.Profile.cast(entity)
    return prof.parentSketch.referencePlane if prof is not None else entity


def build_part(comp, plane, rec, part):
    """One part as extrudes. -> (its body, its features)."""
    pf = rec["frames"]["pattern_cm"]
    body, feats = None, []
    for s in part["solids"]:
        for st in s["steps"]:
            outers = [q["outer"] for q in st["polygons"]]
            holes = [h for q in st["polygons"] for h in q.get("holes") or []]
            lo, hi = st["z"]
            if body is None:
                if st["step"] == "sub":
                    continue
                f = extrude(comp, plane, pf, outers, lo, hi, "new", name=st["layer"])
                body = f.bodies.item(0)
                body.name = part["name"]
            else:
                f = extrude(comp, plane, pf, outers, lo, hi,
                            "join" if st["step"] == "add" else "cut", body, st["layer"])
            feats.append(f)
            if holes:
                feats.append(extrude(comp, plane, pf, holes, lo - 0.1, hi + 0.1, "cut", body,
                                     st["layer"] + " holes"))
    return body, feats


def build(comp, entity, rec, body_under=None):
    """Every part, then the combines (as feature.py makes them).
    -> {role: body}, [features in order]."""
    from .feature import combine
    plane = plane_of(entity)
    bodies, feats = {}, []
    for part in rec["parts"]:
        b, fs = build_part(comp, plane, rec, part)
        bodies[part["role"]] = b
        feats += fs
        for c in rec["combines"]:
            if c["part"] != part["role"] or c["op"] == "new":
                continue
            target = body_under if c["into"] == "body" else bodies["tile"]
            feats.append(combine(comp, target, b, c["op"]))
    return bodies, feats
