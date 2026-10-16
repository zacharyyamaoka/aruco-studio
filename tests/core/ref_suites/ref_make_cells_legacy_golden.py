# REF: tools/make_cells_legacy_golden.py at c8216ff: its cases and how a case is run,
# for the ported suite. Never writes a golden (no main, no stand-in adsk).
"""Golden sizes of the LEGACY size rule (before 2026-10-14: the marker and
the checker in 0.5 mm steps, a typed size used as typed), made by the code
of that time, for tests/test_aruco_cells_legacy.py.

A tag whose settings carry no "cells" (every tag made before cell multiples)
must recompute to the IDENTICAL layout under today's code -- Zach may have
printed it. This writes each case's inputs and what the old code gave
(every Layout field, the placement on a face, and for evaluate() the board
as built) to a JSON fixture.

    git archive 196454c CADExporter/bam_cad_core ArucoMarkers | tar -x -C <dir>
    python tools/make_cells_legacy_golden.py --root <dir>

(196454c is the last commit before cell multiples; its tree is what this
was first run on.)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# OUT (REF only) = ROOT / "tests" / "fixtures" / "aruco_cells_legacy_golden.json"


def mm(v):
    return None if v is None else v / 1000.0


def circle(cx, cy, r, n=48, cw=False):
    pts = [(round(cx + r * math.cos(2 * math.pi * k / n), 9),
            round(cy + r * math.sin(2 * math.pi * k / n), 9)) for k in range(n)]
    return pts[::-1] if cw else pts


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


def m_loops(loops_mm):
    return [[(x / 1000.0, y / 1000.0) for x, y in lp] for lp in loops_mm]


# faces as boxes (mm)
BOXES = {"tile": (40, 40), "plate": (100, 60), "plate2": (100, 80), "tube15": (15, 200),
         "tube20": (20, 200), "small": (10, 10), "tiny": (8, 8), "strip": (25, 90),
         "big": (300, 300), "disc_sq": (37.5, 37.5), "gim": (47.5, 47.5), "odd": (33.3, 71.7)}
# faces as loops (mm)
SHAPES = {
    "gim43": [circle(2.09, 0.0, 26.5, n=96)] + [circle(x, y, 1.425, n=48, cw=True)
                                                for x, y in ((25.84, 0.0), (2.09, 23.75),
                                                             (-21.66, 0.0), (2.09, -23.75))],
    "plate_holes": [rect(-60, -20, 60, 20), circle(-50, 0, 4, cw=True),
                    circle(50, 0, 4, cw=True)],
    "ell": [[(0, 0), (60, 0), (60, 20), (20, 20), (20, 60), (0, 60)]],
    "ring": [rect(-30, -30, 30, 30), rect(-8, -8, 8, 8)[::-1]],
    "disc53": [circle(0, 0, 26.5, n=64)],
}
DICTS = ("DICT_4X4_50", "DICT_5X5_100", "DICT_6X6_250", "DICT_7X7_50", "DICT_APRILTAG_36h11")
KINDS = ("single", "grid", "charuco")


def cases():
    out = []

    def add(fn, **kw):
        out.append({"fn": fn, "kw": kw})

    for kind in KINDS:
        for face, (w, h) in BOXES.items():
            for d in DICTS[:3]:
                add("default_layout", kind=kind, w=w, h=h, dictionary=d, quiet=1.0)
                add("face_default", kind=kind, w=w, h=h, dictionary=d, quiet=1.0)
            for q in (0.0, 0.5, 2.0):
                add("default_layout", kind=kind, w=w, h=h, dictionary="DICT_4X4_50", quiet=q)
        for d in DICTS[3:]:
            add("default_layout", kind=kind, w=100, h=60, dictionary=d, quiet=1.0)
            add("face_default", kind=kind, w=40, h=40, dictionary=d, quiet=1.0)
    for kind in KINDS:
        for face in ("tile", "plate", "plate2", "tube15", "strip", "odd"):
            w, h = BOXES[face]
            add("candidates", kind=kind, w=w, h=h, dictionary="DICT_4X4_50", quiet=1.0)
        add("candidates", kind=kind, w=100, h=60, dictionary="DICT_5X5_100", quiet=1.0)
    typed = [("single", 40, 40, 35, None), ("single", 10, 10, 6, None), ("single", 8, 8, 20, None),
             ("single", 40, 40, 27.1, None), ("single", 47.5, 47.5, 28.0, None),
             ("single", 100, 60, 12.3, None),
             ("grid", 40, 40, 30, None), ("grid", 100, 60, 22.5, None), ("grid", 15, 200, 27.1, None),
             ("grid", 20, 200, 36, None), ("grid", 15, 200, 40.1, None), ("grid", 300, 300, 8, None),
             ("grid", 100, 60, 13.7, None), ("grid", 33.3, 71.7, 9.9, None),
             ("charuco", 40, 40, 22.5, 30), ("charuco", 100, 100, 18, 20),
             ("charuco", 100, 60, None, 23), ("charuco", 15, 200, 14, None),
             ("charuco", 100, 60, 15, 19.3), ("charuco", 100, 80, 19.5, 26.5),
             ("charuco", 33.3, 71.7, 7.1, 10.3)]
    for kind, w, h, L, S in typed:
        for d in ("DICT_4X4_50", "DICT_5X5_100"):
            add("clamp_to_fit", kind=kind, w=w, h=h, L=L, S=S, dictionary=d, quiet=1.0)
            add("layout_for_size", kind=kind, w=w, h=h, L=L, S=S, dictionary=d, quiet=1.0)
    add("layout_for_size", kind="grid", w=100, h=60, L=22.5, S=None, dictionary="DICT_4X4_50",
        quiet=1.0, force=[3, 2])
    add("layout_for_size", kind="grid", w=100, h=60, L=22.5, S=None, dictionary="DICT_4X4_50",
        quiet=1.0, force=[5, 2])
    add("layout_for_size", kind="charuco", w=100, h=60, L=15, S=20, dictionary="DICT_4X4_50",
        quiet=1.0, force=[4, 3])
    for shape in SHAPES:
        for kind in KINDS:
            add("fit_on_loops", kind=kind, shape=shape, L=None, S=None, dictionary="DICT_4X4_50",
                quiet=1.0, angles=[0.0, 90.0])
        add("fit_on_loops", kind="single", shape=shape, L=None, S=None,
            dictionary="DICT_6X6_250", quiet=1.0, angles=[0.0])
        for L in (12.0, 20.5, 33.3):
            add("fit_on_loops", kind="single", shape=shape, L=L, S=None,
                dictionary="DICT_4X4_50", quiet=1.0, angles=[0.0])
            add("fit_on_loops", kind="grid", shape=shape, L=L / 2.0, S=None,
                dictionary="DICT_4X4_50", quiet=1.0, angles=[0.0, 90.0])
        add("fit_on_loops", kind="charuco", shape=shape, L=None, S=9.7, dictionary="DICT_4X4_50",
            quiet=1.0, angles=[0.0, 90.0])
        add("fit_on_loops", kind="charuco", shape=shape, L=6.2, S=9.0, dictionary="DICT_4X4_50",
            quiet=1.0, angles=[0.0, 90.0])
    for shape in ("plate_holes", "ell", "ring"):
        for kind in ("grid", "charuco"):
            add("candidates_on_loops", kind=kind, shape=shape, dictionary="DICT_4X4_50",
                quiet=1.0, angles=[0.0, 90.0])
    add("candidates_on_loops", kind="single", shape="gim43", dictionary="DICT_4X4_50",
        quiet=1.0, angles=[0.0])
    return out


def lay_dict(lay):
    return {"kind": lay.kind, "marker_m": lay.marker_m, "square_m": lay.square_m,
            "cols": lay.cols, "rows": lay.rows, "separation_m": lay.separation_m,
            "margins_m": list(lay.margins_m), "ok": lay.ok, "notes": list(lay.notes),
            "badges": list(lay.badges), "fill": lay.fill, "dictionary": lay.dictionary,
            "quiet_modules": lay.quiet_modules}


def run(case, A):
    kw = case["kw"]
    common = dict(dictionary=kw["dictionary"], quiet_modules=kw["quiet"])
    fn = case["fn"]
    if fn in ("default_layout", "face_default"):
        return lay_dict(getattr(A, fn)(kw["kind"], mm(kw["w"]), mm(kw["h"]), **common))
    if fn == "candidates":
        return [lay_dict(l) for l in A.candidates(kw["kind"], mm(kw["w"]), mm(kw["h"]),
                                                   limit=None, **common)]
    if fn == "clamp_to_fit":
        return lay_dict(A.clamp_to_fit(kw["kind"], mm(kw["w"]), mm(kw["h"]), mm(kw["L"]),
                                       mm(kw["S"]) or 0.0, **common))
    if fn == "layout_for_size":
        force = tuple(kw["force"]) if kw.get("force") else None
        return lay_dict(A.layout_for_size(kw["kind"], mm(kw["w"]), mm(kw["h"]), mm(kw["L"]),
                                          mm(kw["S"]) or 0.0, force=force, **common))
    loops = m_loops(SHAPES[kw["shape"]])
    if fn == "fit_on_loops":
        lay, pl = A.fit_on_loops(kw["kind"], loops, marker_m=mm(kw["L"]),
                                 square_m=mm(kw["S"]) or 0.0, angles_deg=kw["angles"], **common)
        return {"layout": lay_dict(lay), "placement": pl}
    if fn == "candidates_on_loops":
        return [lay_dict(l) for l in A.candidates_on_loops(kw["kind"], loops,
                                                           angles_deg=kw["angles"], **common)]
    raise ValueError(fn)


# ------------------------------------------------- evaluate() on stand-ins

EVAL_CASES = [
    # (settings over the defaults, numbers over the defaults, the area (w, h mm), loops?)
    ({"layout": "single", "mode": "both"}, {}, (60.0, 40.0), None),
    ({"layout": "single", "mode": "both"}, {"size": 27.3}, (60.0, 40.0), None),
    ({"layout": "grid", "mode": "both"}, {}, (100.0, 60.0), None),
    ({"layout": "grid", "mode": "both"}, {"size": 13.7}, (100.0, 60.0), None),
    ({"layout": "grid", "mode": "both", "force": [3, 2]}, {"size": 13.0}, (100.0, 60.0), None),
    ({"layout": "charuco", "mode": "both"}, {}, (100.0, 80.0), None),
    ({"layout": "charuco", "mode": "both"}, {"size": 9.3, "square": 13.1}, (100.0, 80.0), None),
    ({"layout": "single", "mode": "black", "dictionary": "DICT_6X6_250"}, {}, (47.5, 47.5),
     "gim43"),
    ({"layout": "grid", "mode": "black"}, {}, (120.0, 40.0), "plate_holes"),
    ({"layout": "charuco", "mode": "black"}, {}, (60.0, 60.0), "ell"),
    ({"layout": "single", "mode": "black"}, {"size": 21.7}, (60.0, 60.0), "ring"),
    ({"layout": "charuco", "mode": "black"}, {"size": 6.1, "square": 9.2}, (120.0, 40.0),
     "plate_holes"),
]


