# Ported from REF ArucoMarkers/aruco_autosize_gallery.py at c8216ff: the pure part
# (FACES, TYPED, the tessellation, summary) copied verbatim; build_face / run_fusion stay in Fusion.
"""The auto-size verification gallery: ten faces that are not plain boxes.

Zach, 2026-10-08: "please set up a couple of examples with holes,
non-rectangular shapes, etc. to verify that the algorithm works properly."

FACES describes each face with primitives in MILLIMETRES (circles, arcs,
polygons), so the same face can be
  * tessellated offline the way Fusion strokes an edge (loops_m: polygons in
    METRES, chord tolerance 0.05 mm like aruco_tags.face_loops_2d), for
    tests/test_aruco_autosize.py and tools/render_autosize_gallery.py;
  * drawn and extruded in Fusion (build_face), then given an ArUco Extrude
    by the face-click path (run_fusion, bridge action "autosize_gallery").

The pure part (FACES, TYPED, loops_mm, loops_m) is standard library only;
everything that touches Fusion imports adsk inside the function.
"""
from __future__ import annotations

import math

KINDS = ("single", "grid", "charuco")
CHORD_TOL_MM = 0.05                 # aruco_tags.face_loops_2d strokes edges at 0.005 cm


def _rect(x0, y0, w, h):
    return ("poly", [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)])


# outer shape, holes; mm, face frame = sketch XY
FACES = [
    {"key": "disc4", "title": "Zach's disc: Ø53, four Ø2.85 holes",
     "outer": ("circle", 0.0, 0.0, 26.5),
     "holes": [("circle", 23.75 * c, 23.75 * s, 1.425)
               for c, s in ((1, 0), (0, 1), (-1, 0), (0, -1))]},
    {"key": "dshape", "title": "D-shape: Ø50 disc, flat 11 mm off centre",
     "outer": ("dshape", 0.0, 0.0, 25.0, 11.0), "holes": []},
    {"key": "lshape", "title": "L-shape: 60 × 60, 20 mm legs",
     "outer": ("poly", [(0, 0), (60, 0), (60, 20), (20, 20), (20, 60), (0, 60)]), "holes": []},
    {"key": "plate_hole", "title": "Plate 80 × 50, Ø18 hole in the middle",
     "outer": _rect(0, 0, 80, 50), "holes": [("circle", 40.0, 25.0, 9.0)]},
    {"key": "ring", "title": "Ring: Ø60 outside, Ø30 inside",
     "outer": ("circle", 0.0, 0.0, 30.0), "holes": [("circle", 0.0, 0.0, 15.0)]},
    {"key": "hexagon", "title": "Hexagon: 60 across corners",
     "outer": ("ngon", 0.0, 0.0, 30.0, 6, 0.0), "holes": []},
    {"key": "stadium", "title": "Stadium slot: 74 × 24",
     "outer": ("stadium", 0.0, 0.0, 50.0, 12.0), "holes": []},
    {"key": "notch", "title": "Plate 70 × 45 with a 20 × 18 edge notch",
     "outer": ("poly", [(0, 0), (70, 0), (70, 45), (45, 45), (45, 27), (25, 27), (25, 45), (0, 45)]),
     "holes": []},
    {"key": "strip", "title": "Long thin strip: 150 × 14",
     "outer": _rect(0, 0, 150, 14), "holes": []},
    {"key": "triangle", "title": "Equilateral triangle: 70 mm sides",
     "outer": ("ngon", 0.0, 0.0, 70.0 / math.sqrt(3.0), 3, 90.0), "holes": []},
]

# typed sizes tried on every face: (layout, marker mm, square mm)
TYPED = [("single", 30.0, 0.0), ("grid", 8.0, 0.0)]
TYPED_EXTRA = {"disc4": [("single", 37.0, 0.0)]}      # what Zach typed on his disc


def face(key):
    return next(f for f in FACES if f["key"] == key)


def typed_for(key):
    return TYPED_EXTRA.get(key, []) + TYPED


# ------------------------------------------------------------- tessellation

def _arc_pts(cx, cy, r, a0, a1, tol=CHORD_TOL_MM, closed=False):
    """Points on an arc from angle a0 to a1 (radians, a1 > a0), chord error
    <= tol: both ends included unless closed (a full circle)."""
    span = a1 - a0
    step = 2.0 * math.acos(max(-1.0, 1.0 - tol / r)) if r > tol else math.pi / 2.0
    n = max(8 if closed else 1, int(math.ceil(span / step - 1e-9)))
    k = range(n) if closed else range(n + 1)
    return [(cx + r * math.cos(a0 + span * i / n), cy + r * math.sin(a0 + span * i / n)) for i in k]


def shape_pts(shape, tol=CHORD_TOL_MM):
    """One shape -> a closed polygon (mm, last point != first)."""
    kind = shape[0]
    if kind == "circle":
        _k, cx, cy, r = shape
        return _arc_pts(cx, cy, r, 0.0, 2.0 * math.pi, tol, closed=True)
    if kind == "poly":
        return [(float(x), float(y)) for x, y in shape[1]]
    if kind == "ngon":
        _k, cx, cy, r, n, rot = shape
        return [(cx + r * math.cos(math.radians(rot) + 2 * math.pi * i / n),
                 cy + r * math.sin(math.radians(rot) + 2 * math.pi * i / n)) for i in range(n)]
    if kind == "stadium":
        _k, cx, cy, length, r = shape
        h = length / 2.0
        right = _arc_pts(cx + h, cy, r, -math.pi / 2.0, math.pi / 2.0, tol)
        left = _arc_pts(cx - h, cy, r, math.pi / 2.0, 1.5 * math.pi, tol)
        return right + left
    if kind == "dshape":                 # the disc below the chord y = cy + flat
        _k, cx, cy, r, flat = shape
        t = math.asin(flat / r)          # the chord meets the circle at angles t and pi - t
        return _arc_pts(cx, cy, r, math.pi - t, 2.0 * math.pi + t, tol)
    raise ValueError(f"unknown shape {kind!r}")


def loops_mm(f, tol=CHORD_TOL_MM):
    return [shape_pts(f["outer"], tol)] + [shape_pts(h, tol)[::-1] for h in f.get("holes", [])]


def loops_m(f, tol=CHORD_TOL_MM):
    return [[(x / 1000.0, y / 1000.0) for x, y in lp] for lp in loops_mm(f, tol)]


def bbox_mm(f):
    pts = [p for lp in loops_mm(f) for p in lp]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def summary(lay, pl):
    """A Layout + placement as plain numbers (mm) for the gallery's JSON."""
    out = {"label": lay.label(), "ok": bool(lay.ok), "kind": lay.kind, "notes": list(lay.notes),
           "marker_mm": round(lay.marker_m * 1000.0, 4), "square_mm": round(lay.square_m * 1000.0, 4),
           "cols": lay.cols, "rows": lay.rows, "count": lay.count,
           "separation_mm": round(lay.separation_m * 1000.0, 4),
           "quiet_mm": round(lay.quiet_m * 1000.0, 4),
           "tile_mm": [round(v * 1000.0, 4) for v in lay.tile_m] if lay.marker_m > 0 else None,
           "margins_mm": [round(v * 1000.0, 4) for v in lay.margins_m], "fill": round(lay.fill, 4)}
    if pl:
        out["placement_mm"] = {k: round(pl[k] * 1000.0, 4) for k in ("cx", "cy", "w", "h")}
        out["placement_mm"]["angle_deg"] = pl.get("angle_deg", 0.0)
        if pl.get("clear"):
            out["clear_mm"] = {k: round(v * 1000.0, 4) for k, v in pl["clear"].items()}
    return out


# ------------------------------------------------- the Studio's target palette
# (ArUco Studio, not REF: a plain box and a plain disc beside the ten faces,
# so the target editor has the two shapes people start from. FACES above is
# REF's list unchanged; the tests iterate FACES.)
BOX = {"key": "box40", "title": "Box 40 x 40", "outer": _rect(-20, -20, 40, 40), "holes": []}
DISC = {"key": "disc40", "title": "Disc: Ø40", "outer": ("circle", 0.0, 0.0, 20.0), "holes": []}
PALETTE = [BOX, DISC] + FACES
