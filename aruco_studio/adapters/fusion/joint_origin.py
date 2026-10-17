"""One Joint Origin per tag, where the plan's OpenCV frame is.

The maths is the core's: `core.geometry.jo_decompose(base, target)` gives
the (angle, offsets, flip) Fusion composes a Joint Origin from (measured
2026-10-08). This module only:

| Step | REF (aruco_tags, c8216ff) |
|---|---|
| reads the geometry's own frame with a probe Joint Origin, deleted whatever happens | `_jo_probe` |
| adds the Joint Origin with the numbers going in through the INPUT (editing them later needs the timeline rolled to it) | `_jo_add` |
| reads it back (`transform.getAsCoordinateSystem`) and, when Fusion disagrees, finds angle and flip by read-back and the offsets from three unit probes | `_place_joint_origin` |
| keeps ONE per tag: every Joint Origin a call makes is tracked; what it does not keep is deleted on the way out, an exception included; an old one whose `deleteMe()` refuses (a joint uses it) is kept and the new one goes | `ensure_joint_origin`, `_MADE`, `_delete_quietly` |

Two anchors (the caller says which):

| Anchor | How | REF |
|---|---|---|
| the node's frame sketch (jo_v 2, AFTER the node; compute moves the sketch) | the origin point with the x line and the z line as axis entities, no angle, no offset; the first of `SKETCH_METHODS` that reads back exact | `_jo_on_sketch`, `_ensure_jo_after` |
| a planar face or point (jo_v 1, BEFORE the node) | `place`: angle, offsets, flip from `core.geometry.jo_decompose` | `_place_joint_origin` |
"""
from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from ...core import geometry as G
from .api import clear_selections, delete_quietly, unit, valid, vec

JO_PREFIX = "aruco"                      # REF aruco_tags.JO_PREFIX
SKETCH_METHODS = ("point_axes", "zline_x", "xline_z")    # REF JO_SKETCH_METHODS
TOL_CM = 1e-5
TOL_RAD = 1e-6
_MADE = []                               # one list per ensure() running: what it made


def name_of(key):
    return f"{JO_PREFIX} {key}"


def frame_of(jo):
    o, x, y, z = jo.transform.getAsCoordinateSystem()
    return vec(o), unit(vec(x)), unit(vec(y)), unit(vec(z))


def add(comp, geo, angle=0.0, off=(0.0, 0.0, 0.0), flip=False):
    joi = comp.jointOrigins.createInput(geo)
    VI = adsk.core.ValueInput.createByReal
    joi.angle = VI(angle)
    joi.offsetX, joi.offsetY, joi.offsetZ = (VI(float(v)) for v in off)
    joi.isFlipped = bool(flip)
    jo = comp.jointOrigins.add(joi)
    if _MADE and jo is not None:
        _MADE[-1].append(jo)
    return jo


def read(jo):
    """A Joint Origin's frame; one that cannot be read is deleted first."""
    try:
        return frame_of(jo)
    except Exception:
        delete_quietly(jo)
        raise


def probe(comp, geo, *params):
    """A probe Joint Origin's frame; the probe is deleted whatever happens."""
    j = add(comp, geo, *params)
    try:
        return frame_of(j)
    finally:
        delete_quietly(j)


def place(comp, geo, target, tol_cm=TOL_CM, tol_rad=TOL_RAD):
    """A Joint Origin on `geo` whose read-back is `target` (o, x, y, z; cm).
    -> (jo, (pos err cm, angle err rad), (angle, offsets, flip))."""
    base = probe(comp, geo)
    params = G.jo_decompose(base, target)
    jo = add(comp, geo, *params)
    err = G._frame_error(read(jo), target)
    if err[0] < tol_cm and err[1] < tol_rad:
        return jo, err, params
    delete_quietly(jo)
    a, _off, flip = params
    best = None
    for fl in (flip, not flip):
        for ang in (a, -a, a + math.pi, math.pi - a):
            f0 = probe(comp, geo, ang, (0.0, 0.0, 0.0), fl)
            e = G._frame_error(f0, target)[1]
            if best is None or e < best[0]:
                best = (e, ang, fl, f0[0])
    _e, ang, fl, o0 = best
    cols = []
    for k in range(3):
        off = [0.0, 0.0, 0.0]
        off[k] = 1.0
        cols.append(G._sub(probe(comp, geo, ang, off, fl)[0], o0))
    off = G._solve3(cols, G._sub(target[0], o0)) or [0.0, 0.0, 0.0]
    params = (ang, tuple(off), fl)
    jo = add(comp, geo, *params)
    return jo, G._frame_error(read(jo), target), params


def add_on_sketch(comp, sk, method):
    """REF _jo_on_sketch: one Joint Origin on the frame sketch."""
    lines = sk.sketchCurves.sketchLines
    if lines.count < 2:
        raise ValueError("the frame sketch has no point and lines")
    lx, lz = lines.item(0), lines.item(1)
    o_pt = lx.startSketchPoint
    JG = adsk.fusion.JointGeometry
    start = adsk.fusion.JointKeyPointTypes.StartKeyPoint
    if method == "point_axes":
        geo, xa, za = JG.createByPoint(o_pt), lx, lz
    elif method == "zline_x":
        geo, xa, za = JG.createByCurve(lz, start), lx, None
    elif method == "xline_z":
        geo, xa, za = JG.createByCurve(lx, start), None, lz
    else:
        raise ValueError(f"method {method!r}")
    joi = comp.jointOrigins.createInput(geo)
    if xa is not None:
        joi.xAxisEntity = xa
    if za is not None:
        joi.zAxisEntity = za
    jo = comp.jointOrigins.add(joi)
    if _MADE and jo is not None:
        _MADE[-1].append(jo)
    return jo


def place_on_sketch(comp, sk, target, tol_cm=TOL_CM, tol_rad=TOL_RAD):
    """The first sketch method whose read-back is `target`. -> (jo, err,
    method); raises when none holds (the caller falls back to `place`)."""
    errs = []
    for m in SKETCH_METHODS:
        jo = add_on_sketch(comp, sk, m)
        err = G._frame_error(read(jo), target)
        if err[0] < tol_cm and err[1] < tol_rad:
            return jo, err, m
        errs.append(f"{m}: {err[0] * 10:.3g} mm / {math.degrees(err[1]):.3g} deg")
        delete_quietly(jo)
    raise ValueError("no frame-sketch Joint Origin reads back: " + "; ".join(errs))


def find(comp, key, token=None):
    """The tag's Joint Origin: by the record's token, else by its name."""
    jos = [comp.jointOrigins.item(i) for i in range(comp.jointOrigins.count)]
    if token:
        for j in jos:
            if j.entityToken == token:
                return j
    return next((j for j in jos if j.name == name_of(key)), None)


def ensure(comp, key, geo, target, token=None, sketch=None):
    """The tag's ONE Joint Origin at `target`: on `sketch` (the frame
    sketch) when given and one of its methods reads back, else on `geo` by
    `place`. -> {"token", "name", "err_mm", "err_deg", "how", "problem"?}."""
    made = []
    _MADE.append(made)
    keep = None
    try:
        old = find(comp, key, token)
        clear_selections()
        jo = None
        if sketch is not None:
            try:
                jo, err, how = place_on_sketch(comp, sketch, target)
            except ValueError:
                if geo is None:
                    raise
        if jo is None:
            jo, err, params = place(comp, geo, target)
            how = ["place", params[0], list(params[1]), bool(params[2])]
        out = {"err_mm": err[0] * 10.0, "err_deg": math.degrees(err[1]), "how": how}
        if old is not None and not delete_quietly(old):
            # deleteMe refused (a joint uses it): keep the old, drop the new
            keep = old
            out["problem"] = "the old Joint Origin could not be deleted (a joint uses it?)"
            out.update(token=old.entityToken, name=old.name)
            return out
        keep = jo
        jo.name = name_of(key)
        out.update(token=jo.entityToken, name=jo.name)
        return out
    finally:
        if _MADE and _MADE[-1] is made:
            _MADE.pop()
        for j in made:
            if j is not keep:
                delete_quietly(j)


def prune(comp, keys):
    """Delete the Joint Origins named for a tag whose key is not in `keys`
    (a node gone). -> how many went."""
    gone = 0
    for j in [comp.jointOrigins.item(i) for i in range(comp.jointOrigins.count)]:
        if valid(j) and j.name.startswith(JO_PREFIX + " ") and j.name[len(JO_PREFIX) + 1:] \
                not in keys:
            if delete_quietly(j):
                gone += 1
    return gone


def on_point(sketch_point):
    """A Joint Origin anchor on a sketch point (the frame sketch's origin)."""
    return adsk.fusion.JointGeometry.createByPoint(sketch_point)
