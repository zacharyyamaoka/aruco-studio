"""The small part of Fusion's API the adapter may call: the protocol.

Every `adsk.core.<Name>` / `adsk.fusion.<Name>` the adapter names is in `SURFACE`, and
every method it calls on a Fusion object is in `METHODS`. The stand-in
(tests/adapters/fake_adsk.py) implements exactly this, and
tests/adapters/test_api_surface.py checks both lists against the adapter's
source and against the stand-in. A call outside the protocol is a test
failure, so the adapter cannot grow a Fusion dependency nobody modelled.

These are real Fusion 2705 names (the ones REF's add-in calls at c8216ff).
"""
from __future__ import annotations

import math
from typing import Protocol, Sequence

import adsk.core
import adsk.fusion

SURFACE = frozenset({
    # adsk.core
    "adsk.core.Application", "adsk.core.Point3D", "adsk.core.Vector3D", "adsk.core.Matrix3D",
    "adsk.core.OrientedBoundingBox3D", "adsk.core.ObjectCollection", "adsk.core.ValueInput",
    "adsk.core.Line3D", "adsk.core.Plane",
    # adsk.fusion
    "adsk.fusion.TemporaryBRepManager", "adsk.fusion.BooleanTypes",
    "adsk.fusion.FeatureOperations", "adsk.fusion.Design", "adsk.fusion.BaseFeature",
    "adsk.fusion.CombineFeature", "adsk.fusion.Sketch", "adsk.fusion.CustomFeature",
    "adsk.fusion.CustomFeatureDefinition", "adsk.fusion.JointOrigin",
    "adsk.fusion.JointGeometry", "adsk.fusion.BRepBody", "adsk.fusion.BRepFace",
    "adsk.fusion.Profile", "adsk.fusion.ExtrudeFeature", "adsk.fusion.JointKeyPointTypes",
    "adsk.fusion.CustomFeatureEventHandler",
    "adsk.fusion.OffsetStartDefinition",
})

# object.method / object.attribute the adapter uses, by the Fusion class
METHODS = {
    "Application": ("get", "activeProduct", "userInterface"),
    "UserInterface": ("activeSelections",),
    "Selections": ("clear",),
    "Point3D / Vector3D": ("create", "x", "y", "z", "length", "asArray"),
    "Matrix3D": ("create", "setWithCoordinateSystem", "getAsCoordinateSystem", "asArray"),
    "OrientedBoundingBox3D": ("create",),
    "ObjectCollection": ("create", "add", "count", "item"),
    "ValueInput": ("createByReal", "createByString"),
    "Line3D": ("startPoint", "endPoint"),
    "Plane": ("uDirection",),
    "BoundingBox3D": ("minPoint", "maxPoint"),
    "TemporaryBRepManager": ("get", "createBox", "createCylinderOrCone", "booleanOperation"),
    "Design": ("cast", "timeline", "rootComponent", "allComponents", "appearances",
               "attributes"),
    "Timeline": ("markerPosition", "count", "item", "timelineGroups", "moveToEnd"),
    "TimelineGroups": ("add",),
    "TimelineObject": ("index", "rollTo"),
    "Component": ("bRepBodies", "features", "sketches", "jointOrigins", "attributes",
                  "occurrences", "xYConstructionPlane", "allOccurrences", "name"),
    "Features": ("baseFeatures", "combineFeatures", "customFeatures", "extrudeFeatures"),
    "BaseFeatures": ("add",),
    "BaseFeature": ("cast", "startEdit", "finishEdit", "updateBody", "bodies",
                    "sourceBodies", "name", "timelineObject", "deleteMe", "isValid",
                    "entityToken"),
    "BRepBodies": ("add", "count", "item", "itemByName"),
    "BRepBody": ("name", "appearance", "faces", "isValid", "parentComponent",
                 "physicalProperties", "boundingBox"),
    "PhysicalProperties": ("volume",),
    "CombineFeatures": ("createInput", "add"),
    "CombineFeatureInput": ("operation", "isKeepToolBodies"),
    "CombineFeature": ("cast", "timelineObject", "deleteMe"),
    "ExtrudeFeatures": ("createInput", "add"),
    "ExtrudeFeatureInput": ("startExtent", "setDistanceExtent", "participantBodies"),
    "ExtrudeFeature": ("bodies",),
    "OffsetStartDefinition": ("create",),
    "Sketches": ("add",),
    "Sketch": ("cast", "name", "isVisible", "sketchCurves", "profiles", "modelToSketchSpace",
               "sketchToModelSpace", "referencePlane"),
    "SketchCurves": ("sketchLines", "sketchCircles"),
    "SketchLines": ("addByTwoPoints", "item", "count"),
    "SketchLine": ("startSketchPoint", "endSketchPoint"),
    "SketchCircles": ("addByCenterRadius",),
    "SketchPoint": ("geometry", "move"),
    "Profiles": ("count", "item"),
    "Profile": ("cast", "parentSketch", "profileLoops"),
    "ProfileLoop": ("profileCurves",),
    "ProfileCurve": ("geometry",),
    "CurveEvaluator3D": ("getParameterExtents", "getStrokes"),
    "CustomFeatureDefinition": ("create", "editCommandId", "customFeatureCompute", "id"),
    "CustomFeatureEventArgs": ("customFeature", "computeStatus"),
    "ComputeStatus": ("statusMessages",),
    "StatusMessages": ("addWarning", "addError"),
    "CustomFeatures": ("createInput", "add"),
    "CustomFeatureInput": ("addCustomParameter", "addDependency", "setStartAndEndFeatures"),
    "CustomFeature": ("parameters", "dependencies", "customNamedValues", "features",
                      "setStartAndEndFeatures", "timelineObject", "name", "definition",
                      "parentComponent", "deleteMe", "isValid", "entityToken"),
    "CustomFeatureParameters": ("itemById",),
    "CustomFeatureParameter": ("value", "expression", "isVisible"),
    "CustomFeatureDependencies": ("itemById",),
    "CustomNamedValues": ("addOrSetValue", "isExistingValue", "value"),
    "JointGeometry": ("createByPoint", "createByCurve", "createByPlanarFace"),
    "JointOrigins": ("createInput", "add", "count", "item"),
    "JointOriginInput": ("angle", "offsetX", "offsetY", "offsetZ", "isFlipped",
                         "xAxisEntity", "zAxisEntity"),
    "JointOrigin": ("transform", "name", "deleteMe", "isValid", "entityToken"),
    "Attributes": ("add", "itemByName"),
    "Attribute": ("value",),
    "Appearances": ("itemByName",),
    "Occurrences": ("addNewComponent",),
    "Occurrence": ("fullPathName", "component", "isVisible", "isReferencedComponent",
                   "transform2", "attributes"),
    "BRepFace": ("evaluator", "pointOnFace", "edges", "vertices", "loops", "body",
                 "geometry", "assemblyContext", "nativeObject", "appearance"),
    "SurfaceEvaluator": ("getNormalAtPoint",),
    "BRepLoop": ("coEdges",),
    "BRepCoEdge": ("edge", "isOpposedToEdge"),
}


class Body(Protocol):
    """What the adapter needs of a body (temporary or in a component)."""
    name: str


class Component(Protocol):
    bRepBodies: object
    features: object
    sketches: object
    jointOrigins: object
    attributes: object


Frame = Sequence[Sequence[float]]


def tbm():
    return adsk.fusion.TemporaryBRepManager.get()


def P(p):
    return adsk.core.Point3D.create(float(p[0]), float(p[1]), float(p[2]))


def V(v):
    return adsk.core.Vector3D.create(float(v[0]), float(v[1]), float(v[2]))


def vec(p):
    """A Fusion point / vector -> [x, y, z]."""
    return [p.x, p.y, p.z]


def unit(a):
    n = math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
    return [c / n for c in a]


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def valid(ent) -> bool:
    try:
        return ent is not None and ent.isValid
    except Exception:                              # noqa: BLE001
        return False


def clear_selections():
    """Never delete a selected node (Fusion crashed, 2026-10-08)."""
    try:
        adsk.core.Application.get().userInterface.activeSelections.clear()
    except Exception:                              # noqa: BLE001
        pass


def delete_quietly(ent) -> bool:
    """Delete `ent`; True when it is GONE. deleteMe() can say no (False) or
    raise -- the entity stays (REF aruco_tags._delete_quietly)."""
    if not valid(ent):
        return True
    try:
        ent.deleteMe()
    except Exception:                              # noqa: BLE001
        pass
    return not valid(ent)


JOIN = "JoinFeatureOperation"
CUT = "CutFeatureOperation"
INTERSECT = "IntersectFeatureOperation"
NEW = "NewBodyFeatureOperation"


def op(name: str):
    """A combine / extrude operation by the plan's word."""
    return getattr(adsk.fusion.FeatureOperations,
                   {"join": JOIN, "cut": CUT, "intersect": INTERSECT, "new": NEW}[name])
