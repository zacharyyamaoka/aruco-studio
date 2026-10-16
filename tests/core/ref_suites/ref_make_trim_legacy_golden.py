# REF: tools/make_trim_legacy_golden.py at c8216ff: its cases and how a case is run,
# for the ported suite. Never writes a golden (no main, no stand-in adsk).
"""Golden ArUco Extrude results for tags WITHOUT Trim excess, made by the code
of the time, for tests/test_aruco_trim_legacy.py.

Every tag made before 2026-10-16 has no "trim" in its settings, and the
coordinator's rule is that existing tags never change on their own. This writes
evaluate() on stand-in targets (every layout, mode, operation, pins, corner
mark, label, Origin, heights, a cell rule), the plan (aruco_slabs.plan for a
grid of modes / numbers / pins), what a node is made of (structure,
params_for, settle) and default_settings() to a JSON fixture; the test
replays it against today's code and compares every float exactly.

    git archive <commit> CADExporter/bam_cad_core ArucoMarkers | tar -x -C <dir>
    python tools/make_trim_legacy_golden.py --root <dir>

(first made from 5cf71bd, the last commit before Trim excess.)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# OUT (REF only) = ROOT / "tests" / "fixtures" / "aruco_trim_legacy_golden.json"


def circle(cx, cy, r, n=48, cw=False):
    pts = [(round(cx + r * math.cos(2 * math.pi * k / n), 9),
            round(cy + r * math.sin(2 * math.pi * k / n), 9)) for k in range(n)]
    return pts[::-1] if cw else pts


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


SHAPES = {
    "plate_holes": [rect(-60, -20, 60, 20), circle(-50, 0, 4, cw=True),
                    circle(50, 0, 4, cw=True)],
    "disc53": [circle(0, 0, 26.5, n=64)],
}

LABEL_ON = {"on": True}

# (settings over the defaults, numbers over the defaults, area (w, h mm), loops?)
EVAL_CASES = [
    ({"layout": "single", "mode": "both", "op": "join"}, {}, (60.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "new", "pin": "triangle"}, {}, (60.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "new", "pin": "round"}, {}, (60.0, 60.0), None),
    ({"layout": "single", "mode": "both", "op": "new", "has_body": False}, {}, (40.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "join", "corner_mark": "triangle"}, {},
     (60.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "new", "corner_mark": "cut", "pin": "triangle"},
     {}, (60.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "join", "turn": 90}, {"size": 21.5},
     (60.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "join"},
     {"white_offset": -1.0, "white_height": 3.0, "black_offset": 2.0, "black_height": -0.4},
     (50.0, 50.0), None),
    ({"layout": "single", "mode": "both", "op": "new"},
     {"white_offset": -1.0, "white_height": 2.0, "black_offset": 1.4, "black_height": 0.5},
     (50.0, 50.0), None),
    ({"layout": "grid", "mode": "both", "op": "join"}, {}, (100.0, 60.0), None),
    ({"layout": "grid", "mode": "both", "op": "new", "pin": "round", "turn": 180}, {},
     (100.0, 60.0), None),
    ({"layout": "charuco", "mode": "both", "op": "join"}, {}, (100.0, 80.0), None),
    ({"layout": "charuco", "mode": "both", "op": "join", "corner_mark": "cut", "turn": 270},
     {"size": 9.3, "square": 13.1}, (100.0, 80.0), None),
    ({"layout": "single", "mode": "black"}, {}, (47.5, 47.5), "disc53"),
    ({"layout": "single", "mode": "black", "corner_mark": "triangle"}, {"size": 18.0},
     (47.5, 47.5), "disc53"),
    ({"layout": "grid", "mode": "black"}, {}, (120.0, 40.0), "plate_holes"),
    ({"layout": "charuco", "mode": "black"}, {}, (120.0, 40.0), "plate_holes"),
    ({"layout": "single", "mode": "black"}, {"black_offset": 0.0, "black_height": 0.8},
     (60.0, 40.0), None),
    ({"layout": "single", "mode": "white"}, {}, (60.0, 40.0), None),
    ({"layout": "grid", "mode": "white", "has_body": False}, {}, (100.0, 60.0), None),
    ({"layout": "single", "mode": "both", "op": "join", "label": LABEL_ON}, {}, (60.0, 40.0),
     None),
    ({"layout": "single", "mode": "both", "op": "new", "label": LABEL_ON, "pin": "triangle"},
     {}, (60.0, 40.0), None),
    ({"layout": "single", "mode": "black", "label": LABEL_ON}, {}, (120.0, 40.0),
     "plate_holes"),
    ({"layout": "single", "mode": "white", "label": LABEL_ON}, {}, (60.0, 40.0), None),
    ({"layout": "single", "mode": "both", "op": "join",
      "cells": {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0}}, {}, (60.0, 40.0), None),
    ({"layout": "charuco", "mode": "black",
      "cells": {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0}}, {}, (120.0, 40.0),
     "plate_holes"),
]

PLAN_MODES = ("both", "black", "white")
PLAN_NUMBERS = [
    {},
    {"white_offset": -1.0, "white_height": 2.0},
    {"black_offset": 0.0, "black_height": -0.6},
    {"black_offset": 2.6, "black_height": 0.4},
    {"black_offset": 1.5, "black_height": -2.5},
    {"white_offset": 0.5, "white_height": 1.5},
    {"white_offset": 0.0, "white_height": -0.6, "black_offset": -0.6, "black_height": 0.3},
    {"pin_length": 3.0, "pin_tol": 0.4},
]


def _r(v, nd=9):
    """JSON-able, rounded far below any change that matters (and exact
    enough to see one): floats to 9 decimals, tuples to lists."""
    if isinstance(v, float):
        return round(v, nd)
    if isinstance(v, (list, tuple)):
        return [_r(c, nd) for c in v]
    if isinstance(v, dict):
        return {str(k): _r(c, nd) for k, c in v.items()}
    return v


def plan_dict(p):
    L = p.layers
    return {"mode": p.mode, "op": p.op, "parts": list(p.parts), "pocket": p.pocket,
            "recess": [[w, list(s)] for w, s in p.recess], "pin": p.pin, "notes": list(p.notes),
            "structure": list(p.structure),
            "layers": {"white": L.white, "black": L.black, "pattern": L.pattern,
                       "surface": L.surface, "depth": L.depth, "raise": L.raise_,
                       "recess": L.recess, "gap": L.gap}}


def ev_dict(F, ev):
    lab = ev.get("label")
    mark = ev.get("mark")
    return {"spec": ev["spec"].to_dict(), "tag": ev["tag"], "tile": ev["tile"],
            "base": ev["base"], "notes": list(ev["notes"]), "lift_cm": ev["lift_cm"],
            "plan": plan_dict(ev["plan"]), "pins": ev["pins"], "pin_frame": ev["pin_frame"],
            "turn": ev["turn"], "x_fit": ev["x_fit"], "pin_tol": ev["pin_tol"],
            "mode": ev["mode"], "mark": mark.to_dict(6) if mark is not None else None,
            "label": lab.to_dict(6) if lab is not None else None,
            "label_white": ev.get("label_white"),
            "node_warning": F.node_warning(ev), "record_mark": F.mark_record(ev),
            "record_label": F.label_record(ev)}


def run_eval(F, Profile):
    out = []
    for s_over, n_over, (w, h), shape in EVAL_CASES:
        F.profile_rect = (lambda W, H: lambda t, s: ([0.0, 0.0, 0.5], [1.0, 0.0, 0.0],
                                                     [0.0, 1.0, 0.0], [0.0, 0.0, 1.0],
                                                     W / 10.0, H / 10.0))(w, h)
        loops_mm = SHAPES[shape] if shape else [rect(-w / 2, -h / 2, w / 2, h / 2)]
        loops = [[(x / 1000.0, y / 1000.0) for x, y in lp] for lp in loops_mm]
        F._profile_loops_m = (lambda lp: lambda t, o, x, y: lp)(loops)
        s = dict(F.default_settings(), source="profile", z_sign=1, x_sketch=[1.0, 0.0],
                 has_body=True, key="tg")
        s.update({k: v for k, v in s_over.items() if k != "label"})
        if "label" in s_over:
            s["label"] = dict(s["label"], **s_over["label"])
        s = F.normalise(s)
        n = dict(F.default_numbers(s["mode"]), **n_over)
        got = {}
        try:
            ev = F.evaluate(Profile(), s, n)
            got["ev"] = ev_dict(F, ev)
            s2, n2 = F.settle(s, n, ev)
            got["settled"] = {"settings": s2, "numbers": n2}
            got["params_for"] = F.params_for(s2)
            got["structure"] = list(F.structure(s2, n2))
            got["node_structure"] = list(F.node_structure(s2))
            got["plan_of"] = plan_dict(F.plan_of(s2, n2))
        except Exception as exc:                   # noqa: BLE001
            got["error"] = f"{type(exc).__name__}: {exc}"
        out.append({"settings": s_over, "numbers": n_over, "area": [w, h], "shape": shape,
                    "got": _r(got)})
    return out


def run_plans(SL):
    out = []
    for mode in PLAN_MODES:
        for op in ("join", "new"):
            for has_body in (True, False):
                for pin in ("none", "triangle", "round"):
                    for k, over in enumerate(PLAN_NUMBERS):
                        n = dict(SL.default_numbers(mode), **SL.pin_defaults())
                        n.update(over)
                        try:
                            got = plan_dict(SL.plan(mode, op, has_body, n, pin))
                        except Exception as exc:   # noqa: BLE001
                            got = {"error": f"{type(exc).__name__}: {exc}"}
                        out.append({"mode": mode, "op": op, "has_body": has_body, "pin": pin,
                                    "numbers": k, "got": _r(got)})
    return out


