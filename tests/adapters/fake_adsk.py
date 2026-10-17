"""A recording stand-in for Fusion's `adsk` (tests only; never shipped).

Built for aruco_studio/adapters/fusion from REF's own stand-ins (read, not
copied): tests/test_aruco_restructure_sim.py's timeline (items, a marker,
rollTo before / after, features made AT the marker, a custom feature that
groups a contiguous range), tests/aruco_trim_fixtures.py's faces and bodies,
tests/aruco_ui_stubs.py's casts. What it models, and what it does not:

| Modelled | How |
|---|---|
| TemporaryBRepManager | boxes (OrientedBoundingBox3D), cylinders and booleans as a CSG tree; `contains(p)` answers a point probe exactly |
| the timeline | REF's sim: items in order, the marker, rollTo, insert at the marker, deleteMe refused while rolled back, groups |
| bodies | a base feature's body is its source temp body; combines (join / cut / intersect) are REPLAYED in timeline order by `Design.solids()`, so a probe sees the document as Fusion would after a recompute |
| the custom feature | parameters (`itemById` RAISES for an unknown id, as 2705 does), named values, dependencies, setStartAndEndFeatures ("3 : Didn't roll editing feature back" when the marker is past the start), health |
| Joint Origins | Fusion's measured composition (2026-10-08): x turned by the angle about the UNFLIPPED z, the flip half a turn about the new x, offsets along the FINAL axes -- written here with an explicit rotation matrix, independent of core.geometry; `deleteMe()` can be told to refuse |
| appearances | names on bodies and faces; `add()` / `updateBody()` RESET a base body's appearance (REF quirk) |
| attributes | per component, (group, name) -> value |
| an edit command | `command(design)`: a failure inside takes back every change (Fusion's executeFailed) through an undo log |
| occurrences | path names joined with "+", per-path visibility, a world transform, attributes per occurrence |

Not modelled: B-rep topology (faces are six stand-ins per body), real
Fusion recompute events, sketches beyond points and lines, UI. Every call
the adapter makes is appended to `LOG` as text.

`install()` puts `adsk`, `adsk.core` and `adsk.fusion` in `sys.modules`;
`uninstall()` takes them out. `reset()` gives a fresh application and log.
"""
from __future__ import annotations

import itertools
import json
import math
import sys
import types
from typing import Callable, List, Optional

LOG: List[str] = []
_TOKENS = itertools.count(1)
STATE = types.SimpleNamespace(app=None)


def _fmt(v):
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_fmt(x) for x in v) + "]"
    if isinstance(v, Point3D) or isinstance(v, Vector3D):
        return f"({_fmt(v.x)},{_fmt(v.y)},{_fmt(v.z)})"
    if hasattr(v, "name") and isinstance(getattr(v, "name", None), str):
        return repr(v.name)
    return repr(v) if isinstance(v, str) else type(v).__name__


def log(call: str, *args):
    LOG.append(f"{call}(" + ", ".join(_fmt(a) for a in args) + ")")


def _undo(fn: Callable[[], None]):
    """Remember how to take a change back (the edit command's executeFailed)."""
    app = STATE.app
    if app is not None and app.design is not None:
        app.design._undo.append(fn)


def _setattr(obj, name, value):
    old = obj.__dict__.get(name, _MISSING)

    def back():
        if old is _MISSING:
            obj.__dict__.pop(name, None)
        else:
            obj.__dict__[name] = old
    _undo(back)
    obj.__dict__[name] = value


_MISSING = object()


# ================================================================ adsk.core

class Point3D:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    @staticmethod
    def create(x=0.0, y=0.0, z=0.0):
        return Point3D(x, y, z)

    def asArray(self):
        return [self.x, self.y, self.z]

    def copy(self):
        return Point3D(self.x, self.y, self.z)


class Vector3D(Point3D):
    @staticmethod
    def create(x=0.0, y=0.0, z=0.0):
        return Vector3D(x, y, z)

    @property
    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def copy(self):
        return Vector3D(self.x, self.y, self.z)


def _a(p):
    return [p.x, p.y, p.z] if hasattr(p, "x") else [float(c) for c in p]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return [c / n for c in a]


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


class Matrix3D:
    """Row-major 4x4; `getAsCoordinateSystem` as Fusion's."""

    def __init__(self, m=None):
        self.m = list(m) if m is not None else [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0,
                                                0, 0, 0, 1.0]

    @staticmethod
    def create():
        return Matrix3D()

    def setWithCoordinateSystem(self, o, x, y, z):
        o, x, y, z = _a(o), _a(x), _a(y), _a(z)
        self.m = [x[0], y[0], z[0], o[0], x[1], y[1], z[1], o[1], x[2], y[2], z[2], o[2],
                  0.0, 0.0, 0.0, 1.0]
        return True

    def getAsCoordinateSystem(self):
        m = self.m
        return (Point3D(m[3], m[7], m[11]), Vector3D(m[0], m[4], m[8]),
                Vector3D(m[1], m[5], m[9]), Vector3D(m[2], m[6], m[10]))

    def asArray(self):
        return list(self.m)


class OrientedBoundingBox3D:
    def __init__(self, c, ld, wd, length, width, height):
        self.centerPoint, self.lengthDirection, self.widthDirection = c, ld, wd
        self.length, self.width, self.height = float(length), float(width), float(height)

    @staticmethod
    def create(centerPoint, lengthDirection, widthDirection, length, width, height):
        return OrientedBoundingBox3D(centerPoint, lengthDirection, widthDirection, length, width,
                                     height)


class ObjectCollection:
    def __init__(self):
        self._items = []

    @staticmethod
    def create():
        return ObjectCollection()

    @staticmethod
    def _of(items):
        c = ObjectCollection()
        c._items = list(items)
        return c

    def add(self, x):
        self._items.append(x)
        return True

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]

    def __iter__(self):
        return iter(self._items)


class ValueInput:
    def __init__(self, real=None, text=None):
        self.realValue, self.stringValue = real, text

    @staticmethod
    def createByReal(v):
        return ValueInput(real=float(v))

    @staticmethod
    def createByString(s):
        return ValueInput(text=str(s))

    def value_cm(self):
        """The value Fusion would evaluate: a real, or 'N mm' -> cm."""
        if self.realValue is not None:
            return self.realValue
        t = self.stringValue.strip()
        if t.endswith("mm"):
            return float(t[:-2]) / 10.0
        return float(t)


class Line3D:
    def __init__(self, a, b):
        self.startPoint, self.endPoint = a, b


class Plane:
    def __init__(self, origin, normal, u=None):
        self.origin, self.normal = origin, normal
        self.uDirection = u or Vector3D(1, 0, 0)


class _Selections:
    def clear(self):
        log("ui.activeSelections.clear")
        return True


class Application:
    def __init__(self):
        self.userInterface = types.SimpleNamespace(activeSelections=_Selections(),
                                                   messageBox=lambda *a, **k: 0)
        self.design: Optional[Design] = None
        self.messages: List[str] = []

    @staticmethod
    def get():
        return STATE.app

    @property
    def activeProduct(self):
        return self.design

    def log(self, msg):
        self.messages.append(str(msg))


# ============================================================== adsk.fusion

class BooleanTypes:
    UnionBooleanType = 0
    DifferenceBooleanType = 1
    IntersectionBooleanType = 2


class FeatureOperations:
    JoinFeatureOperation = 0
    CutFeatureOperation = 1
    IntersectFeatureOperation = 2
    NewBodyFeatureOperation = 3
    NAMES = {0: "join", 1: "cut", 2: "intersect", 3: "new"}


# ------------------------------------------------------------ CSG and TBM

class Csg:
    """box: (c, axes, half lengths); cyl: (p0, p1, r); union: [children];
    op: (kind, a, b) for a difference / an intersection. Each node keeps its
    axis-aligned box, so a probe skips what is far away."""

    def __init__(self, kind, *a):
        self.kind, self.a = kind, a
        self._bb = None

    def bbox(self):
        if self._bb is None:
            k = self.kind
            if k == "box":
                c, axes, half = self.a
                ext = [sum(abs(axes[j][i]) * half[j] for j in range(3)) for i in range(3)]
                self._bb = ([c[i] - ext[i] for i in range(3)], [c[i] + ext[i] for i in range(3)])
            elif k == "cyl":
                p0, p1, r = self.a
                self._bb = ([min(p0[i], p1[i]) - r for i in range(3)],
                            [max(p0[i], p1[i]) + r for i in range(3)])
            elif k == "prism":
                o, x, y, z, pts, lo, hi = self.a
                cs = [[o[i] + x[i] * u + y[i] * v + z[i] * w for i in range(3)]
                      for (u, v) in pts for w in (lo, hi)]
                self._bb = ([min(c[i] for c in cs) for i in range(3)],
                            [max(c[i] for c in cs) for i in range(3)])
            elif k == "union":
                bbs = [c.bbox() for c in self.a[0]]
                self._bb = ([min(b[0][i] for b in bbs) for i in range(3)],
                            [max(b[1][i] for b in bbs) for i in range(3)])
            else:
                self._bb = self.a[1].bbox()
        return self._bb

    def contains(self, p, eps=1e-9):
        lo, hi = self.bbox()
        if any(p[i] < lo[i] - abs(eps) or p[i] > hi[i] + abs(eps) for i in range(3)):
            return False
        k = self.kind
        if k == "box":
            c, axes, half = self.a
            d = _sub(p, c)
            return all(abs(_dot(d, axes[i])) <= half[i] + eps for i in range(3))
        if k == "cyl":
            p0, p1, r = self.a
            ax = _sub(p1, p0)
            L = math.sqrt(_dot(ax, ax))
            u = [c / L for c in ax]
            d = _sub(p, p0)
            t = _dot(d, u)
            if t < -eps or t > L + eps:
                return False
            q = [d[i] - u[i] * t for i in range(3)]
            return _dot(q, q) <= (r + eps) ** 2
        if k == "union":
            return any(c.contains(p, eps) for c in self.a[0])
        if k == "prism":
            o, x, y, z, pts, lo, hi = self.a
            d = _sub(p, o)
            w = _dot(d, z)
            if w < lo - eps or w > hi + eps:
                return False
            u, v = _dot(d, x), _dot(d, y)
            inside = False
            for i in range(len(pts)):
                (x0, y0), (x1, y1) = pts[i - 1], pts[i]
                if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
                    inside = not inside
            return inside
        op, a, b = self.a
        if op == BooleanTypes.DifferenceBooleanType:
            return a.contains(p, eps) and not b.contains(p, -eps)
        return a.contains(p, eps) and b.contains(p, eps)

    @staticmethod
    def combine(kind, a, b):
        if kind == BooleanTypes.UnionBooleanType:
            kids = (a.a[0] if a.kind == "union" else [a]) + (b.a[0] if b.kind == "union" else [b])
            return Csg("union", kids)
        return Csg("op", kind, a, b)


class TempBody:
    """A BRepBody returned by TemporaryBRepManager (transient)."""

    def __init__(self, csg):
        self.csg = csg
        self.isTemporary = True

    def contains(self, p):
        return self.csg.contains(_a(p))


class TemporaryBRepManager:
    _the = None

    @staticmethod
    def get():
        if TemporaryBRepManager._the is None:
            TemporaryBRepManager._the = TemporaryBRepManager()
        return TemporaryBRepManager._the

    def createBox(self, obb):
        x = _unit(_a(obb.lengthDirection))
        y = _unit(_a(obb.widthDirection))
        z = _cross(x, y)
        log("tbm.createBox")
        return TempBody(Csg("box", _a(obb.centerPoint), (x, y, z),
                            (obb.length / 2.0, obb.width / 2.0, obb.height / 2.0)))

    def createCylinderOrCone(self, p0, r0, p1, r1):
        log("tbm.createCylinderOrCone")
        if abs(r0 - r1) > 1e-12:
            raise RuntimeError("the fake models cylinders only")
        return TempBody(Csg("cyl", _a(p0), _a(p1), float(r0)))

    def booleanOperation(self, target, tool, kind):
        log("tbm.booleanOperation", {0: "union", 1: "difference", 2: "intersection"}[kind])
        target.csg = Csg.combine(kind, target.csg, tool.csg)
        return True

    def copy(self, body):
        log("tbm.copy")
        return TempBody(body.csg if hasattr(body, "csg") else body.own)


# ----------------------------------------------------------- the timeline

class TimelineObject:
    def __init__(self, tl, entity):
        self.tl, self.entity = tl, entity
        self.isSuppressed = False

    @property
    def index(self):
        return self.tl.items.index(self)

    @property
    def isRolledBack(self):
        return self.index >= self.tl.markerPosition

    def rollTo(self, rollBefore):
        log("timeline.rollTo", self.entity.name, "before" if rollBefore else "after")
        _setattr(self.tl, "markerPosition", self.index if rollBefore else self.index + 1)
        return True


class TimelineGroup:
    def __init__(self, tl, lo, hi, token):
        self.tl, self.lo, self.hi = tl, lo, hi
        self.name = ""
        self.entityToken = token


class TimelineGroups:
    def __init__(self, tl):
        self.tl, self._items = tl, []

    def add(self, lo, hi):
        log("timeline.timelineGroups.add", lo, hi)
        g = TimelineGroup(self.tl, lo, hi, f"group-{next(_TOKENS)}")
        self._items.append(g)
        _undo(lambda: self._items.remove(g))
        return g

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class Timeline:
    def __init__(self):
        self.__dict__["items"] = []
        self.__dict__["markerPosition"] = 0
        self.timelineGroups = TimelineGroups(self)

    def insert(self, ent):
        it = TimelineObject(self, ent)
        at = self.markerPosition
        items = self.items
        items.insert(at, it)
        self.__dict__["markerPosition"] = at + 1
        ent.__dict__["timelineObject"] = it

        def back():
            if it in items:
                items.remove(it)
                self.__dict__["markerPosition"] = min(self.markerPosition, len(items))
        _undo(back)
        return ent

    @property
    def count(self):
        return len(self.items)

    def item(self, i):
        return self.items[i]

    def moveToEnd(self):
        log("timeline.moveToEnd")
        _setattr(self, "markerPosition", len(self.items))
        return True


class Entity:
    """Anything with a token, a name and deleteMe."""
    kind = "entity"

    def __init__(self, name=""):
        self.__dict__["name"] = name
        self.__dict__["isValid"] = True
        self.__dict__["entityToken"] = f"{type(self).__name__}-{next(_TOKENS)}"
        self.__dict__["refuse_delete"] = False

    def __setattr__(self, k, v):
        if k in ("name", "appearance", "isVisible", "isLightBulbOn"):
            log(f"{type(self).__name__}.{k}=", v)
            _setattr(self, k, v)
        else:
            self.__dict__[k] = v

    def _design(self):
        return STATE.app.design

    def deleteMe(self):
        log(f"{type(self).__name__}.deleteMe", self.name)
        if self.refuse_delete:
            return False
        it = self.__dict__.get("timelineObject")
        if it is not None:
            tl = it.tl
            if tl.markerPosition <= it.index:
                raise RuntimeError(f"deleted '{self.name}' while it is rolled back")
            i = it.index
            tl.items.remove(it)
            old_marker = tl.markerPosition
            if tl.markerPosition > i:
                tl.__dict__["markerPosition"] -= 1

            def back():
                tl.items.insert(i, it)
                tl.__dict__["markerPosition"] = old_marker
                self.__dict__["isValid"] = True
            _undo(back)
        else:
            _undo(lambda: self.__dict__.__setitem__("isValid", True))
        self.__dict__["isValid"] = False
        self._deleted()
        return True

    def _deleted(self):
        pass


# ------------------------------------------------------------- bodies

class Appearance:
    def __init__(self, name):
        self.name = name


class Appearances:
    def __init__(self):
        self._items = {}

    def itemByName(self, name):
        return self._items.get(name)

    def add(self, name):
        self._items[name] = Appearance(name)
        return self._items[name]

    @property
    def count(self):
        return len(self._items)


class BRepFace(Entity):
    """One of a body's six stand-in faces (colour only)."""

    def __init__(self, body, i):
        super().__init__(f"face {i}")
        self.__dict__["body"] = body
        self.__dict__["appearance"] = None


class BRepBody(Entity):
    def __init__(self, comp, own, name="Body"):
        super().__init__(name)
        self.__dict__["parentComponent"] = comp
        self.__dict__["own"] = own                # the source csg (a base body's temp body)
        self.__dict__["appearance"] = None
        self.__dict__["isVisible"] = True
        self.__dict__["faces"] = [BRepFace(self, i) for i in range(6)]
        self.__dict__["base"] = None              # the base feature that owns it
        self.__dict__["physicalProperties"] = types.SimpleNamespace(volume=0.0)

    def contains(self, p):
        """The body as the timeline makes it now (combines replayed)."""
        csg = self._design().solids().get(self)
        return csg is not None and csg.contains(_a(p))

    @staticmethod
    def cast(x):
        return x if isinstance(x, BRepBody) else None


class _BodyList:
    def __init__(self, bodies):
        self._b = bodies

    @property
    def count(self):
        return len([b for b in self._b if b.isValid])

    def item(self, i):
        return [b for b in self._b if b.isValid][i]

    def __iter__(self):
        return iter([b for b in self._b if b.isValid])


class BRepBodies:
    def __init__(self, comp):
        self.comp = comp
        self._items: List[BRepBody] = []

    def add(self, temp, baseFeature=None):
        log("bRepBodies.add", baseFeature.name if baseFeature is not None else None)
        if baseFeature is not None and not baseFeature._editing:
            raise RuntimeError("3 : the base feature is not in edit mode")
        b = BRepBody(self.comp, temp.csg, "Body")
        self._items.append(b)
        _undo(lambda: self._items.remove(b))
        if baseFeature is not None:
            b.__dict__["base"] = baseFeature
            baseFeature._bodies.append(b)
            _undo(lambda: baseFeature._bodies.remove(b))
        return b

    def add_user(self, csg, name):
        """A body the user modelled (a plate): not a base feature's."""
        b = BRepBody(self.comp, csg, name)
        self._items.append(b)
        return b

    @property
    def count(self):
        return len([b for b in self._items if b.isValid])

    def item(self, i):
        return [b for b in self._items if b.isValid][i]

    def itemByName(self, name):
        if name == "":
            raise RuntimeError("2 : InternalValidationError : name")   # 2705
        return next((b for b in self._items if b.isValid and b.name == name), None)

    def __iter__(self):
        return iter([b for b in self._items if b.isValid])


# ------------------------------------------------------------- features

class Feature(Entity):
    def __init__(self, comp, name):
        super().__init__(name)
        self.__dict__["parentComponent"] = comp


class BaseFeature(Feature):
    def __init__(self, comp, name):
        super().__init__(comp, name)
        self.__dict__["_bodies"] = []
        self.__dict__["_editing"] = False

    @staticmethod
    def cast(x):
        return x if isinstance(x, BaseFeature) else None

    @property
    def bodies(self):
        return _BodyList(self._bodies)

    @property
    def sourceBodies(self):
        return list(self._bodies)

    def startEdit(self):
        log("BaseFeature.startEdit", self.name)
        self.__dict__["_editing"] = True
        return True

    def finishEdit(self):
        log("BaseFeature.finishEdit", self.name)
        self.__dict__["_editing"] = False
        return True

    def updateBody(self, src, temp):
        log("BaseFeature.updateBody", self.name)
        if not self._editing:
            raise RuntimeError("3 : updateBody outside startEdit / finishEdit")
        _setattr(src, "own", temp.csg)
        # 2705: updateBody drops the body's appearance (REF _update)
        _setattr(src, "appearance", None)
        for f in src.faces:
            _setattr(f, "appearance", None)
        return True

    def _deleted(self):
        for b in self._bodies:
            b.__dict__["isValid"] = False

        def back():
            for b in self._bodies:
                b.__dict__["isValid"] = True
        _undo(back)


class BaseFeatures:
    def __init__(self, comp):
        self.comp = comp

    def add(self):
        log("baseFeatures.add")
        bf = BaseFeature(self.comp, "Base Feature")
        return self.comp._design().timeline.insert(bf)


class CombineFeatureInput:
    def __init__(self, target, tools):
        self.targetBody, self.toolBodies = target, tools
        self.operation = FeatureOperations.JoinFeatureOperation
        self.isKeepToolBodies = False
        self.isNewComponent = False


class CombineFeature(Feature):
    @staticmethod
    def cast(x):
        return x if isinstance(x, CombineFeature) else None


class CombineFeatures:
    def __init__(self, comp):
        self.comp = comp

    def createInput(self, targetBody, toolBodies):
        log("combineFeatures.createInput", targetBody, [t for t in toolBodies])
        return CombineFeatureInput(targetBody, toolBodies)

    def add(self, inp):
        op = FeatureOperations.NAMES[inp.operation]
        log("combineFeatures.add", op, inp.targetBody, [t for t in inp.toolBodies])
        if inp.targetBody is None:
            raise RuntimeError("3 : Invalid argument targetBody")
        design = self.comp._design()
        design.n_combines += 1
        cb = CombineFeature(self.comp, f"Combine{design.n_combines}")
        cb.__dict__.update(targetBody=inp.targetBody, toolBodies=list(inp.toolBodies),
                           operation=inp.operation, isKeepToolBodies=inp.isKeepToolBodies)
        return design.timeline.insert(cb)


class Sketch(Feature):
    """A sketch on a plane or a planar face: its frame is the plane's (the
    component's XY plane: the identity)."""

    def __init__(self, comp, plane, name="Sketch"):
        super().__init__(comp, name)
        self.__dict__["referencePlane"] = plane
        self.__dict__["isVisible"] = True
        self.__dict__["sketchCurves"] = types.SimpleNamespace(
            sketchLines=SketchLines(self), sketchCircles=SketchCircles(self))
        self.__dict__["sketchPoints"] = SketchPoints(self)
        self.__dict__["_profiles"] = []
        f = getattr(plane, "frame", None)
        self.__dict__["frame"] = f if f is not None else (
            [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])

    @staticmethod
    def cast(x):
        return x if isinstance(x, Sketch) else None

    def modelToSketchSpace(self, p):
        o, x, y, z = self.frame
        d = _sub(_a(p), o)
        return Point3D(_dot(d, x), _dot(d, y), _dot(d, z))

    def sketchToModelSpace(self, p):
        o, x, y, z = self.frame
        q = _a(p)
        return Point3D(*[o[i] + x[i] * q[0] + y[i] * q[1] + z[i] * q[2] for i in range(3)])

    @property
    def profiles(self):
        return ObjectCollection._of(self._profiles)


class SketchPoint(Entity):
    def __init__(self, sk, p):
        super().__init__("point")
        self.__dict__["parentSketch"] = sk
        self.__dict__["geometry"] = Point3D(p.x, p.y, p.z)

    def move(self, v):
        log("SketchPoint.move", v)
        g = self.geometry
        _setattr(self, "geometry", Point3D(g.x + v.x, g.y + v.y, g.z + v.z))
        return True

    @property
    def worldGeometry(self):
        return self.geometry


class SketchPoints:
    def __init__(self, sk):
        self.sk, self._items = sk, []

    def add(self, p):
        log("sketchPoints.add", p)
        sp = SketchPoint(self.sk, p)
        self._items.append(sp)
        return sp

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class SketchLine(Entity):
    def __init__(self, sk, a, b):
        super().__init__("line")
        self.__dict__["parentSketch"] = sk
        self.__dict__["startSketchPoint"] = a
        self.__dict__["endSketchPoint"] = b


class SketchProfile:
    """A closed region a sketch made: a polygon (sketch coordinates) or a circle."""

    def __init__(self, sk, kind, pts=None, c=None, r=None):
        self.parentSketch, self.kind, self.pts, self.c, self.r = sk, kind, pts, c, r


class SketchLines:
    def __init__(self, sk):
        self.sk, self._items = sk, []
        self._chain = None                      # [first point, ..., last point]

    def addByTwoPoints(self, a, b):
        log("sketchLines.addByTwoPoints", a if isinstance(a, Point3D) else a.geometry,
            b if isinstance(b, Point3D) else b.geometry)
        pa = a if isinstance(a, SketchPoint) else SketchPoint(self.sk, a)
        pb = b if isinstance(b, SketchPoint) else SketchPoint(self.sk, b)
        ln = SketchLine(self.sk, pa, pb)
        self._items.append(ln)
        ch = self._chain
        if ch is not None and pa is ch[-1]:
            if pb is ch[0]:                     # closed: a profile
                self.sk._profiles.append(SketchProfile(
                    self.sk, "poly", pts=[(q.geometry.x, q.geometry.y) for q in ch]))
                self._chain = None
            else:
                ch.append(pb)
        else:
            self._chain = [pa, pb]
        return ln

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class SketchCircles:
    def __init__(self, sk):
        self.sk = sk

    def addByCenterRadius(self, c, r):
        log("sketchCircles.addByCenterRadius", c, r)
        self.sk._profiles.append(SketchProfile(self.sk, "circle", c=(c.x, c.y), r=float(r)))
        return types.SimpleNamespace(centerSketchPoint=SketchPoint(self.sk, c), radius=r)


class OffsetStartDefinition:
    def __init__(self, offset):
        self.offset = offset

    @staticmethod
    def create(offset):
        return OffsetStartDefinition(offset)


class ExtrudeFeatureInput:
    def __init__(self, profiles, operation):
        self.profiles, self.operation = profiles, operation
        self.startExtent = OffsetStartDefinition(ValueInput.createByReal(0.0))
        self.distance = None
        self.participantBodies = []

    def setDistanceExtent(self, isSymmetric, distance):
        self.distance = distance
        return True


class ExtrudeFeature(Feature):
    @staticmethod
    def cast(x):
        return x if isinstance(x, ExtrudeFeature) else None

    @property
    def bodies(self):
        return _BodyList(self._bodies)


class ExtrudeFeatures:
    def __init__(self, comp):
        self.comp = comp

    def createInput(self, profiles, operation):
        log("extrudeFeatures.createInput", FeatureOperations.NAMES[operation])
        return ExtrudeFeatureInput(profiles, operation)

    def add(self, inp):
        op = FeatureOperations.NAMES[inp.operation]
        s0 = inp.startExtent.offset.realValue
        d = inp.distance.realValue
        lo, hi = min(s0, s0 + d), max(s0, s0 + d)
        log("extrudeFeatures.add", op, inp.profiles.count, lo, hi,
            [b for b in inp.participantBodies])
        kids = []
        for pr in inp.profiles:
            sk = pr.parentSketch
            o, x, y, z = sk.frame
            if pr.kind == "circle":
                p0 = [o[i] + x[i] * pr.c[0] + y[i] * pr.c[1] + z[i] * lo for i in range(3)]
                p1 = [o[i] + x[i] * pr.c[0] + y[i] * pr.c[1] + z[i] * hi for i in range(3)]
                kids.append(Csg("cyl", p0, p1, pr.r))
            else:
                kids.append(Csg("prism", o, x, y, z, pr.pts, lo, hi))
        csg = kids[0] if len(kids) == 1 else Csg("union", kids)
        des = self.comp._design()
        ext = ExtrudeFeature(self.comp, f"Extrude{len(des.timeline.items) + 1}")
        ext.__dict__.update(csg=csg, operation=inp.operation,
                            participants=list(inp.participantBodies), _bodies=[])
        if op == "new":
            b = BRepBody(self.comp, csg, "Body")
            b.__dict__["base"] = ext
            self.comp.bRepBodies._items.append(b)
            ext._bodies.append(b)
        return des.timeline.insert(ext)


class Sketches:
    def __init__(self, comp):
        self.comp = comp

    def add(self, plane):
        log("sketches.add", getattr(plane, "name", "plane"))
        return self.comp._design().timeline.insert(Sketch(self.comp, plane))


# --------------------------------------------------------- the custom feature

class CustomFeatureEventHandler:
    def __init__(self):
        pass


class _Event:
    def __init__(self):
        self.handlers = []

    def add(self, h):
        self.handlers.append(h)
        return True


class CustomFeatureDefinition:
    def __init__(self, id_, name):
        self.id, self.name = id_, name
        self.editCommandId = ""
        self.customFeatureCompute = _Event()

    @staticmethod
    def create(id_, name, resourceFolder=""):
        log("CustomFeatureDefinition.create", id_)
        return CustomFeatureDefinition(id_, name)

    def fire(self, cf):
        """Fusion's compute: every handler, with a fresh status."""
        st = ComputeStatus()
        for h in self.customFeatureCompute.handlers:
            h.notify(types.SimpleNamespace(customFeature=cf, computeStatus=st))
        cf.__dict__["healthState"] = (2 if any(m[0] == "error" for m in st.messages) else
                                      2 if any(m[0] == "warning" for m in st.messages) else 0)
        cf.__dict__["status_messages"] = list(st.messages)
        return st


class CustomFeatureParameter:
    def __init__(self, id_, label, value_cm, units, visible):
        self.id, self.label, self.units, self.isVisible = id_, label, units, visible
        self.__dict__["value"] = value_cm
        self.__dict__["_expr"] = ""
        self.name = id_

    def __setattr__(self, k, v):
        if k == "value":
            log("CustomFeatureParameter.value=", self.id, v)
            _setattr(self, "value", float(v))
        elif k == "expression":
            log("CustomFeatureParameter.expression=", self.id, v)
            _setattr(self, "_expr", v)
            _setattr(self, "value", ValueInput.createByString(v).value_cm())
        else:
            self.__dict__[k] = v

    @property
    def expression(self):
        return self._expr


class CustomFeatureParameters:
    def __init__(self):
        self._items = []

    def itemById(self, id_):
        p = next((p for p in self._items if p.id == id_), None)
        if p is None:
            raise RuntimeError("3 : Invalid argument id")      # 2705: not None
        return p

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]

    def __iter__(self):
        return iter(self._items)


class NamedValues:
    def __init__(self):
        self._v = {}

    def addOrSetValue(self, k, v):
        log("customNamedValues.addOrSetValue", k)
        old = self._v.get(k, _MISSING)

        def back():
            if old is _MISSING:
                self._v.pop(k, None)
            else:
                self._v[k] = old
        _undo(back)
        self._v[k] = str(v)
        return True

    def isExistingValue(self, k):
        return k in self._v

    def value(self, k):
        return self._v[k]


class Dependency:
    def __init__(self, id_, entity):
        self.id, self.entity = id_, entity


class Dependencies:
    def __init__(self):
        self._items = []

    def add(self, id_, entity):
        self._items.append(Dependency(id_, entity))

    def itemById(self, id_):
        return next((d for d in self._items if d.id == id_), None)


class CustomFeatureInput:
    def __init__(self, definition):
        self.definition = definition
        self.params = []
        self.deps = []
        self.start = self.end = None

    def addCustomParameter(self, id_, label, value, units, isVisible):
        log("CustomFeatureInput.addCustomParameter", id_, units, isVisible)
        self.params.append((id_, label, value, units, isVisible))

    def addDependency(self, id_, entity):
        log("CustomFeatureInput.addDependency", id_)
        self.deps.append((id_, entity))

    def setStartAndEndFeatures(self, a, b):
        log("CustomFeatureInput.setStartAndEndFeatures", a, b)
        self.start, self.end = a, b


class _NodeItem:
    """The custom feature's own place in the timeline: before its first
    feature (REF's sim). A released node has none."""

    def __init__(self, cf):
        self.cf = cf
        self.isSuppressed = False

    @property
    def index(self):
        if self.cf.start is None:
            raise RuntimeError("2 : InternalValidationError : res >= 0")
        return self.cf.start.timelineObject.index

    @property
    def isRolledBack(self):
        return self.index >= self.cf.start.timelineObject.tl.markerPosition

    def rollTo(self, rollBefore):
        if self.cf.start is None:
            raise RuntimeError("a released node has no place to roll to (modelled)")
        if rollBefore:
            return self.cf.start.timelineObject.rollTo(True)
        return self.cf.end.timelineObject.rollTo(False)


class CustomFeature(Entity):
    def __init__(self, comp, definition):
        super().__init__("ArUco Extrude")
        d = self.__dict__
        d["parentComponent"] = comp
        d["definition"] = definition
        d["parameters"] = CustomFeatureParameters()
        d["dependencies"] = Dependencies()
        d["customNamedValues"] = NamedValues()
        d["start"] = d["end"] = None
        d["timelineObject"] = _NodeItem(self)
        d["healthState"] = 0
        d["errorOrWarningMessage"] = ""

    @staticmethod
    def cast(x):
        return x if isinstance(x, CustomFeature) else None

    @property
    def features(self):
        if self.start is None:
            return []
        tl = self.start.timelineObject.tl
        a, b = self.start.timelineObject.index, self.end.timelineObject.index
        return [it.entity for it in tl.items[a:b + 1]]

    def setStartAndEndFeatures(self, a, b):
        log("CustomFeature.setStartAndEndFeatures", a, b)
        if a is not None and self.start is None and a.timelineObject.tl.markerPosition > \
                a.timelineObject.index:
            raise RuntimeError("3 : Didn't roll editing feature back")
        old = (self.start, self.end)

        def back():
            self.__dict__["start"], self.__dict__["end"] = old
        _undo(back)
        self.__dict__["start"], self.__dict__["end"] = a, b
        return True

    def deleteMe(self):
        log("CustomFeature.deleteMe", self.name)
        old = (self.start, self.end)
        for f in reversed(self.features):
            f.timelineObject.tl.__dict__["markerPosition"] = len(f.timelineObject.tl.items)
            f.deleteMe()

        def back():
            self.__dict__["start"], self.__dict__["end"] = old
            self.__dict__["isValid"] = True
        _undo(back)
        self.__dict__["start"] = self.__dict__["end"] = None
        self.__dict__["isValid"] = False
        return True


class ComputeStatus:
    """The compute's status messages (2705: a warning makes the node an ERROR)."""
    def __init__(self):
        self.messages = []
        self.statusMessages = types.SimpleNamespace(
            addWarning=lambda code, text: self.messages.append(("warning", code, text)),
            addError=lambda code, text: self.messages.append(("error", code, text)))


class CustomFeatures:
    def __init__(self, comp):
        self.comp = comp
        self._items: List[CustomFeature] = []

    def createInput(self, definition):
        log("customFeatures.createInput", definition.id)
        return CustomFeatureInput(definition)

    def add(self, inp):
        log("customFeatures.add", inp.definition.id)
        design = self.comp._design()
        for id_, ent in inp.deps:
            if ent is design.split_face_on_cut and design.face_is_split():
                raise RuntimeError("2 : InternalValidationError : face")
        cf = CustomFeature(self.comp, inp.definition)
        for id_, label, value, units, vis in inp.params:
            v = value.value_cm() if units else value.realValue
            cf.parameters._items.append(CustomFeatureParameter(id_, label, v, units, vis))
        for id_, ent in inp.deps:
            cf.dependencies.add(id_, ent)
        if inp.start is not None:
            tl = design.timeline
            if tl.markerPosition <= inp.end.timelineObject.index:
                raise RuntimeError("3 : the range is rolled back")
        cf.__dict__["start"], cf.__dict__["end"] = inp.start, inp.end
        self._items.append(cf)
        _undo(lambda: self._items.remove(cf))
        # 2705: add() resets its base-feature bodies to the default appearance
        for f in cf.features:
            if isinstance(f, BaseFeature):
                for b in f._bodies:
                    _setattr(b, "appearance", None)
                    for fc in b.faces:
                        _setattr(fc, "appearance", None)
        # compute runs inside add(), before the add-in wrote its spec
        inp.definition.fire(cf)
        return cf

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]

    def __iter__(self):
        return iter(self._items)


# ------------------------------------------------------------- Joint Origins

class JointGeometry:
    """A point's frame: origin = the point, axes = the sketch's (the XY
    plane's), as Fusion takes a sketch point."""

    def __init__(self, entity, frame):
        self.entityOne = entity
        self.frame = frame

    @staticmethod
    def createByPoint(point):
        g = point.geometry if hasattr(point, "geometry") else point
        log("JointGeometry.createByPoint", g)
        return JointGeometry(point, ([g.x, g.y, g.z], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                     [0.0, 0.0, 1.0]))

    @staticmethod
    def createByPlanarFace(face, edge, keyPointType):
        log("JointGeometry.createByPlanarFace", face)
        return JointGeometry(face, face.frame)

    @staticmethod
    def createByCurve(line, keyPointType):
        """A line's start; z along the line (x any perpendicular)."""
        log("JointGeometry.createByCurve", line)
        a, b = _a(line.startSketchPoint.geometry), _a(line.endSketchPoint.geometry)
        z = _unit(_sub(b, a))
        t = [1.0, 0.0, 0.0] if abs(z[0]) < 0.9 else [0.0, 1.0, 0.0]
        x = _unit(_cross(_cross(z, t), z))
        return JointGeometry(line, (a, x, _cross(z, x), z))


class JointKeyPointTypes:
    StartKeyPoint = 0
    MiddleKeyPoint = 1
    EndKeyPoint = 2
    CenterKeyPoint = 3


def _rodrigues(v, axis, ang):
    k = _unit(axis)
    c, s = math.cos(ang), math.sin(ang)
    kxv = _cross(k, v)
    kd = _dot(k, v)
    return [v[i] * c + kxv[i] * s + k[i] * kd * (1 - c) for i in range(3)]


class JointOriginInput:
    def __init__(self, geometry):
        self.geometry = geometry
        self.xAxisEntity = self.zAxisEntity = None
        self.angle = ValueInput.createByReal(0.0)
        self.offsetX = self.offsetY = self.offsetZ = ValueInput.createByReal(0.0)
        self.isFlipped = False


class JointOrigin(Entity):
    # "measured": Fusion 2705 (2026-10-08). "flipped_z": what the old solve
    # assumed (the angle about the FLIPPED z) -- a stand-in for a Fusion
    # update that changes the convention, so the read-back fallback runs.
    CONVENTION = "measured"

    @staticmethod
    def cast(x):
        return x if isinstance(x, JointOrigin) else None

    @property
    def transform(self):
        """Fusion's measured composition (2026-10-08)."""
        o, x, y, z = self.geometry.frame
        a = self.angle
        if self.isFlipped and JointOrigin.CONVENTION == "flipped_z":
            zf = [-c for c in z]
            x1 = _rodrigues(x, zf, a)
            y1 = [-c for c in _rodrigues(y, zf, a)]
            z1 = zf
        else:
            x1 = _rodrigues(x, z, a)
            y1 = _rodrigues(y, z, a)
            z1 = list(z)
            if self.isFlipped:                   # half a turn about the new x
                y1 = _rodrigues(y1, x1, math.pi)
                z1 = _rodrigues(z1, x1, math.pi)
        oo = [o[i] + self.offsets[0] * x1[i] + self.offsets[1] * y1[i] + self.offsets[2] * z1[i]
              for i in range(3)]
        m = Matrix3D()
        m.setWithCoordinateSystem(oo, x1, y1, z1)
        return m


class JointOrigins:
    def __init__(self, comp):
        self.comp = comp
        self._items: List[JointOrigin] = []

    def createInput(self, geometry):
        log("jointOrigins.createInput")
        return JointOriginInput(geometry)

    def add(self, inp):
        log("jointOrigins.add", inp.angle.realValue, [inp.offsetX.realValue,
                                                       inp.offsetY.realValue,
                                                       inp.offsetZ.realValue], inp.isFlipped)
        geo = inp.geometry
        if inp.xAxisEntity is not None or inp.zAxisEntity is not None:
            # axis entities: the frame's x / z along those lines
            o, x, y, z = geo.frame

            def along(line):
                return _unit(_sub(_a(line.endSketchPoint.geometry),
                                  _a(line.startSketchPoint.geometry)))
            if inp.zAxisEntity is not None:
                z = along(inp.zAxisEntity)
            if inp.xAxisEntity is not None:
                x = along(inp.xAxisEntity)
            x = _unit(_sub(x, [z[i] * _dot(x, z) for i in range(3)]))
            geo = JointGeometry(geo.entityOne, (o, x, _cross(z, x), z))
        jo = JointOrigin(f"Joint Origin{len(self._items) + 1}")
        jo.__dict__.update(geometry=geo, angle=inp.angle.realValue,
                           offsets=(inp.offsetX.realValue, inp.offsetY.realValue,
                                    inp.offsetZ.realValue),
                           isFlipped=bool(inp.isFlipped), parentComponent=self.comp)
        self._items.append(jo)
        _undo(lambda: self._items.remove(jo))
        self.comp._design().timeline.insert(jo)
        return jo

    @property
    def count(self):
        return len([j for j in self._items if j.isValid])

    def item(self, i):
        return [j for j in self._items if j.isValid][i]

    def __iter__(self):
        return iter([j for j in self._items if j.isValid])


# ------------------------------------------------------------- attributes

class Attribute:
    def __init__(self, group, name, value):
        self.groupName, self.name, self.value = group, name, value


class Attributes:
    def __init__(self):
        self._items = {}
        self.writes = 0

    def add(self, group, name, value):
        log("attributes.add", group, name)
        self.writes += 1
        old = self._items.get((group, name), _MISSING)

        def back():
            if old is _MISSING:
                self._items.pop((group, name), None)
            else:
                self._items[(group, name)] = old
        _undo(back)
        self._items[(group, name)] = Attribute(group, name, value)
        return self._items[(group, name)]

    def itemByName(self, group, name):
        return self._items.get((group, name))

    @property
    def count(self):
        return len(self._items)


# ---------------------------------------------------- components, occurrences

class Occurrence(Entity):
    def __init__(self, parent, comp, name, transform):
        super().__init__(name)
        d = self.__dict__
        d["component"] = comp
        d["parent"] = parent                      # the occurrence above, or None
        d["transform2"] = transform
        d["isLightBulbOn"] = True
        d["isReferencedComponent"] = False
        d["attributes"] = Attributes()

    @property
    def fullPathName(self):
        names = []
        o = self
        while o is not None:
            names.append(o.name)
            o = o.parent
        return "+".join(reversed(names))

    @property
    def childOccurrences(self):
        return [o for o in STATE.app.design._occurrences if o.parent is self]

    @property
    def isVisible(self):
        o = self
        while o is not None:
            if not o.isLightBulbOn:
                return False
            o = o.parent
        return True

    def world(self):
        """The world transform (row-major): parents first."""
        chain = []
        o = self
        while o is not None:
            chain.append(o.transform2.asArray())
            o = o.parent
        m = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        for t in reversed(chain):
            m = [sum(m[r * 4 + k] * t[k * 4 + c] for k in range(4)) for r in range(4)
                 for c in range(4)]
        return m


class Occurrences:
    def __init__(self, comp):
        self.comp = comp

    def addNewComponent(self, transform):
        log("occurrences.addNewComponent")
        des = self.comp._design()
        comp = des._new_component(f"Component{len(des.allComponents)}")
        occ = Occurrence(None, comp, f"{comp.name}:1", transform)
        des._occurrences.append(occ)
        _undo(lambda: des._occurrences.remove(occ))
        return occ

    def addExistingComponent(self, comp, transform, parent=None):
        des = self.comp._design()
        n = 1 + sum(1 for o in des._occurrences if o.component is comp)
        occ = Occurrence(parent, comp, f"{comp.name}:{n}", transform)
        des._occurrences.append(occ)
        return occ

    @property
    def count(self):
        return len([o for o in STATE.app.design._occurrences if o.parent is None
                    and o.isValid])


class ConstructionPlane:
    def __init__(self, name):
        self.name = name


class Component(Entity):
    def __init__(self, name):
        super().__init__(name)
        d = self.__dict__
        d["bRepBodies"] = BRepBodies(self)
        d["features"] = types.SimpleNamespace(baseFeatures=BaseFeatures(self),
                                              combineFeatures=CombineFeatures(self),
                                              customFeatures=CustomFeatures(self),
                                              extrudeFeatures=ExtrudeFeatures(self))
        d["sketches"] = Sketches(self)
        d["jointOrigins"] = JointOrigins(self)
        d["attributes"] = Attributes()
        d["occurrences"] = Occurrences(self)
        d["xYConstructionPlane"] = ConstructionPlane("xY")

    @property
    def parentDesign(self):
        return STATE.app.design

    @property
    def allOccurrences(self):
        """Root only: proxies whose transform2 is the WORLD transform."""
        return [_OccProxy(o) for o in STATE.app.design._occurrences if o.isValid]


class _OccProxy:
    def __init__(self, occ):
        self.native = occ
        self.fullPathName = occ.fullPathName
        self.component = occ.component
        self.isVisible = occ.isVisible
        self.isReferencedComponent = occ.isReferencedComponent
        self.attributes = occ.attributes
        self.transform2 = Matrix3D(occ.world())


class Design:
    def __init__(self):
        self.timeline = Timeline()
        self.appearances = Appearances()
        self.materialLibraries = []
        self.designIntent = 2                    # Hybrid
        self._undo: List[Callable[[], None]] = []
        self._occurrences: List[Occurrence] = []
        self.allComponents: List[Component] = []
        self.rootComponent = self._new_component("Root")
        self.split_face_on_cut = None            # a face a CUT combine splits (the quirk)
        self.n_combines = 0
        self.attributes = Attributes()

    @staticmethod
    def cast(x):
        return x if isinstance(x, Design) else None

    def face_is_split(self):
        """The quirk's model: a valid CUT combine before the marker splits
        `split_face_on_cut` (a pocket that reaches the face's edge)."""
        tl = self.timeline
        return any(isinstance(it.entity, CombineFeature) and it.entity.isValid
                   and it.entity.operation == FeatureOperations.CutFeatureOperation
                   for it in tl.items[:tl.markerPosition])

    def recompute(self):
        """Compute All: every live custom feature's compute, in order."""
        out = []
        for c in self.allComponents:
            for cf in list(c.features.customFeatures._items):
                if cf.isValid:
                    out.append((cf, cf.definition.fire(cf)))
        return out

    def _new_component(self, name):
        c = Component(name)
        self.allComponents.append(c)
        return c

    def findEntityByToken(self, token):
        for it in self.timeline.items:
            if getattr(it.entity, "entityToken", None) == token:
                return [it.entity]
        for c in self.allComponents:
            for b in c.bRepBodies._items:
                if b.entityToken == token:
                    return [b]
            for cf in c.features.customFeatures:
                if cf.entityToken == token:
                    return [cf]
        return []

    # -- the document as Fusion would show it after a recompute
    def solids(self):
        """{body: csg}: every body's own solid, then the combines in timeline
        order up to the marker (tools consumed unless kept)."""
        out = {}
        tl = self.timeline
        alive = set()
        for c in self.allComponents:
            for b in c.bRepBodies._items:
                if b.isValid and b.base is None:
                    out[b] = b.own
                    alive.add(b)
        for it in tl.items[:tl.markerPosition]:
            e = it.entity
            if isinstance(e, BaseFeature) and e.isValid:
                for b in e._bodies:
                    if b.isValid:
                        out[b] = b.own
                        alive.add(b)
            elif isinstance(e, ExtrudeFeature) and e.isValid:
                if e._bodies:
                    for b in e._bodies:
                        out[b] = e.csg
                        alive.add(b)
                else:
                    kind = {0: BooleanTypes.UnionBooleanType,
                            1: BooleanTypes.DifferenceBooleanType,
                            2: BooleanTypes.IntersectionBooleanType}[e.operation]
                    for t in e.participants:
                        if t in out:
                            out[t] = Csg.combine(kind, out[t], e.csg)
            elif isinstance(e, CombineFeature) and e.isValid:
                t = e.targetBody
                if t not in out:
                    continue
                kind = {0: BooleanTypes.UnionBooleanType, 1: BooleanTypes.DifferenceBooleanType,
                        2: BooleanTypes.IntersectionBooleanType}[e.operation]
                for tool in e.toolBodies:
                    if tool in out:
                        out[t] = Csg.combine(kind, out[t], out[tool])
                        if not e.isKeepToolBodies:
                            out.pop(tool)
        return out

    def signature(self):
        """What the document IS, for 'left identical' checks."""
        tl = self.timeline
        items = [(type(it.entity).__name__, it.entity.name, it.entity.isValid)
                 for it in tl.items]
        nodes = []
        for c in self.allComponents:
            for cf in c.features.customFeatures._items:
                nodes.append((cf.name, cf.isValid, cf.start.name if cf.start else None,
                              cf.end.name if cf.end else None,
                              sorted(cf.customNamedValues._v.items())))
        attrs = sorted((c.name, k, a.value) for c in self.allComponents
                       for k, a in c.attributes._items.items())
        jos = sorted((c.name, j.name) for c in self.allComponents for j in c.jointOrigins)
        bodies = sorted((c.name, b.name, id(b.own)) for c in self.allComponents
                        for b in c.bRepBodies)
        return json.dumps([items, tl.markerPosition, nodes, attrs, jos, bodies], default=str)


class _Command:
    """An edit command's execute: a failure inside takes everything back."""

    def __init__(self, design):
        self.design = design

    def __enter__(self):
        self.mark = len(self.design._undo)
        return self

    def __exit__(self, et, ev, tb):
        if et is not None:
            log("command.executeFailed")
            while len(self.design._undo) > self.mark:
                self.design._undo.pop()()
        return False


def command(design):
    return _Command(design)


# ------------------------------------------------------- faces and profiles

class _Strokes:
    def __init__(self, pts):
        self.pts = pts

    def getParameterExtents(self):
        return True, 0.0, 1.0

    def getStrokes(self, p0, p1, tol):
        return True, [Point3D(*p) for p in self.pts]


class BRepEdge(Entity):
    def __init__(self, a, b):
        super().__init__("edge")
        self.__dict__["geometry"] = Line3D(Point3D(*a), Point3D(*b))
        self.__dict__["evaluator"] = _Strokes([a, b])


class BRepCoEdge:
    def __init__(self, edge, opposed=False):
        self.edge, self.isOpposedToEdge = edge, opposed


class BRepLoop:
    def __init__(self, coedges, outer):
        self.coEdges, self.isOuter = coedges, outer

    @property
    def edges(self):
        return [c.edge for c in self.coEdges]


class PlanarFace(Entity):
    """A planar face of a body: loops of 3D points (cm)."""

    def __init__(self, loops3d, normal, body=None, reverse_edges=False):
        super().__init__("face")
        d = self.__dict__
        n = _unit(normal)
        d["geometry"] = Plane(Point3D(*loops3d[0][0]), Vector3D(*n))
        d["evaluator"] = types.SimpleNamespace(
            getNormalAtPoint=lambda p: (True, Vector3D(*n)))
        lps = []
        for k, lp in enumerate(loops3d):
            ces = []
            for i in range(len(lp)):
                a, b = lp[i], lp[(i + 1) % len(lp)]
                if reverse_edges:
                    ces.append(BRepCoEdge(BRepEdge(b, a), True))
                else:
                    ces.append(BRepCoEdge(BRepEdge(a, b), False))
            lps.append(BRepLoop(ces, k == 0))
        d["loops"] = lps
        d["body"] = body
        d["assemblyContext"] = None
        d["split"] = False
        cx = sum(p[0] for p in loops3d[0]) / len(loops3d[0])
        cy = sum(p[1] for p in loops3d[0]) / len(loops3d[0])
        cz = sum(p[2] for p in loops3d[0]) / len(loops3d[0])
        d["pointOnFace"] = Point3D(cx, cy, cz)
        d["frame"] = ([cx, cy, cz], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], n)

    @property
    def edges(self):
        return [e for lp in self.loops for e in lp.edges]

    @property
    def vertices(self):
        return [types.SimpleNamespace(geometry=e.geometry.startPoint) for e in self.edges]

    @property
    def nativeObject(self):
        return self

    @staticmethod
    def cast(x):
        return x if isinstance(x, PlanarFace) else None


class ProfileCurve:
    def __init__(self, a, b):
        self.geometry = types.SimpleNamespace(evaluator=_Strokes([a, b]))


class ProfileLoop:
    def __init__(self, pts, outer):
        self.isOuter = outer
        self.profileCurves = [ProfileCurve(pts[i], pts[(i + 1) % len(pts)])
                              for i in range(len(pts))]


class Profile(Entity):
    def __init__(self, sketch, loops2d):
        super().__init__("profile")
        self.__dict__["parentSketch"] = sketch
        self.__dict__["profileLoops"] = [ProfileLoop([(u, v, 0.0) for u, v in lp], k == 0)
                                         for k, lp in enumerate(loops2d)]
        self.__dict__["assemblyContext"] = None

    @staticmethod
    def cast(x):
        return x if isinstance(x, Profile) else None


# ------------------------------------------------------------ the modules

def _module(name, attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


CORE_NAMES = {"Application": Application, "Point3D": Point3D, "Vector3D": Vector3D,
              "Matrix3D": Matrix3D, "OrientedBoundingBox3D": OrientedBoundingBox3D,
              "ObjectCollection": ObjectCollection, "ValueInput": ValueInput,
              "Line3D": Line3D, "Plane": Plane}
FUSION_NAMES = {"TemporaryBRepManager": TemporaryBRepManager, "BooleanTypes": BooleanTypes,
                "CustomFeatureEventHandler": CustomFeatureEventHandler,
                "FeatureOperations": FeatureOperations, "Design": Design,
                "BaseFeature": BaseFeature, "CombineFeature": CombineFeature, "Sketch": Sketch,
                "CustomFeature": CustomFeature, "CustomFeatureDefinition": CustomFeatureDefinition,
                "JointOrigin": JointOrigin, "JointGeometry": JointGeometry,
                "JointKeyPointTypes": JointKeyPointTypes,
                "BRepBody": BRepBody, "BRepFace": PlanarFace, "Profile": Profile,
                "ExtrudeFeature": ExtrudeFeature, "OffsetStartDefinition": OffsetStartDefinition}


def install():
    """`adsk`, `adsk.core`, `adsk.fusion` in sys.modules (a test asks)."""
    core = _module("adsk.core", CORE_NAMES)
    fusion = _module("adsk.fusion", FUSION_NAMES)
    adsk = _module("adsk", {"core": core, "fusion": fusion, "FAKE": True})
    sys.modules.update({"adsk": adsk, "adsk.core": core, "adsk.fusion": fusion})
    reset()
    return adsk


def uninstall():
    for k in ("adsk", "adsk.core", "adsk.fusion"):
        sys.modules.pop(k, None)


def reset() -> Application:
    """A fresh application with an empty Hybrid design; the log cleared."""
    LOG.clear()
    TemporaryBRepManager._the = None
    app = Application()
    STATE.app = app
    app.design = Design()
    for n in ("Plastic - Matte (White)", "Plastic - Matte (Black)", "Steel - Satin"):
        app.design.appearances.add(n)
    return app


def design() -> Design:
    return STATE.app.design


# ------------------------------------------------------------ fixtures

def plate(w_cm=6.0, h_cm=4.0, t_cm=0.3, comp=None, reverse_edges=False, at=(0.0, 0.0)):
    """A box plate, top face at z = 0 (cm), centred on `at`: (body, top face)."""
    comp = comp or design().rootComponent
    cx, cy = at
    csg = Csg("box", [cx, cy, -t_cm / 2.0], ([1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]),
              (w_cm / 2.0, h_cm / 2.0, t_cm / 2.0))
    body = comp.bRepBodies.add_user(csg, "Plate")
    body.__dict__["physicalProperties"] = types.SimpleNamespace(volume=w_cm * h_cm * t_cm)
    body.__dict__["boundingBox"] = types.SimpleNamespace(
        minPoint=Point3D(cx - w_cm / 2, cy - h_cm / 2, -t_cm),
        maxPoint=Point3D(cx + w_cm / 2, cy + h_cm / 2, 0.0))
    loop = [(cx - w_cm / 2, cy - h_cm / 2, 0.0), (cx + w_cm / 2, cy - h_cm / 2, 0.0),
            (cx + w_cm / 2, cy + h_cm / 2, 0.0), (cx - w_cm / 2, cy + h_cm / 2, 0.0)]
    face = PlanarFace([loop], [0.0, 0.0, 1.0], body=body, reverse_edges=reverse_edges)
    face.__dict__["area"] = w_cm * h_cm
    body.__dict__["faces"] = [face] + body.faces[1:]
    return body, face


KEEP = ("baseFeatures.add", "bRepBodies.add", "BaseFeature.startEdit", "BaseFeature.updateBody",
        "BaseFeature.finishEdit", "combineFeatures.add", "customFeatures.add", "sketches.add",
        "sketchLines.addByTwoPoints", "sketchCircles.addByCenterRadius", "SketchPoint.move",
        "extrudeFeatures.add", "jointOrigins.add", "CustomFeatureInput.addDependency",
        "CustomFeatureInput.setStartAndEndFeatures", "CustomFeature.setStartAndEndFeatures",
        "customNamedValues.addOrSetValue", "attributes.add", "BaseFeature.name=",
        "BRepBody.name=", "CustomFeature.name=", "Sketch.name=", "Sketch.isVisible=",
        "JointOrigin.name=", "BRepBody.appearance=", "BRepFace.appearance=",
        "PlanarFace.appearance=", "timeline.timelineGroups.add", "timeline.rollTo",
        "occurrences.addNewComponent", "Component.name=", "CustomFeatureParameter.expression=",
        "CustomFeatureParameter.value=", "command.executeFailed")


def summary(log_=None, keep=KEEP):
    """The log at feature level: the TemporaryBRepManager calls between two
    feature-level calls folded into one line of counts, runs of face paints
    into one line; every `deleteMe` kept."""
    out, tbm, faces = [], {}, [0, ""]

    def flush():
        if tbm:
            out.append("tbm: " + ", ".join(f"{k} x{v}" for k, v in tbm.items()))
            tbm.clear()
        if faces[0]:
            out.append(f"{faces[1]} x{faces[0]}")
            faces[0] = 0
    for line in (LOG if log_ is None else log_):
        head = line.split("(")[0]
        if head.startswith("tbm."):
            if faces[0]:
                out.append(f"{faces[1]} x{faces[0]}")
                faces[0] = 0
            tbm[head[4:]] = tbm.get(head[4:], 0) + 1
            continue
        if head in ("BRepFace.appearance=", "PlanarFace.appearance="):
            if tbm:
                flush()
            if faces[0] and faces[1] != line:
                out.append(f"{faces[1]} x{faces[0]}")
                faces[0] = 0
            faces[0] += 1
            faces[1] = line
            continue
        if head not in keep and not head.endswith(".deleteMe"):
            continue
        flush()
        out.append(line)
    flush()
    # a run of more than two sketch lines: one line with the count
    runs = []
    for line in out:
        if line.startswith("sketchLines.addByTwoPoints") and runs and \
                runs[-1][0].startswith("sketchLines.addByTwoPoints"):
            runs[-1].append(line)
        else:
            runs.append([line])
    folded = []
    for r in runs:
        if len(r) > 2:
            folded.append(f"sketchLines.addByTwoPoints x{len(r)}")
        else:
            folded += r
    return folded
