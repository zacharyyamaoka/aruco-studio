# REF: tools/make_label_rule1_golden.py at c8216ff: its cases and how a case is run,
# for the ported suite. Never writes a golden (no main, no stand-in adsk).
"""Golden labels of the label RULE 1 (before 2026-10-13: one line, 2 modules
from the black), made by the code of that time, for tests/test_aruco_label_rule1.py.

A record without "rule" in its label settings is rule 1 and must recompute
to the IDENTICAL label under today's code (Zach may have printed it). This
writes each case's inputs and what the old code laid out (every slot, part
and stroke, a refused label's preview) to a JSON fixture.

    git archive 8473e14 CADExporter/bam_cad_core | tar -x -C <dir>
    python tools/make_label_rule1_golden.py --core <dir>/CADExporter

The inputs are plain data: a spec dict, a settings dict WITHOUT "rule" (as
an old record has it), and plan_label's keywords (region / bounds loops,
grow, tile, pins, keepouts, slab; a corner mark as (mode, op, want), made by
aruco_chamfer, which did not change).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# OUT (REF only) = ROOT / "tests" / "fixtures" / "aruco_label_rule1_golden.json"


def circle(cx, cy, r, n=48, cw=False, around=False):
    rr = r / math.cos(math.pi / n) if around else r
    pts = [(round(cx + rr * math.cos(2 * math.pi * k / n), 9),
            round(cy + rr * math.sin(2 * math.pi * k / n), 9)) for k in range(n)]
    return pts[::-1] if cw else pts


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


SINGLE = {"marker_id": 12, "marker_length_m": 0.03}
BIG = {"marker_id": 12, "marker_length_m": 0.04}
SMALL = {"marker_id": 12, "marker_length_m": 0.02}
GIM = {"marker_id": 0, "marker_length_m": 0.028}
GRID31 = {"marker_id": 9, "marker_length_m": 0.04, "layout": "grid", "rows": 1, "cols": 3,
          "separation_m": 0.008}
DISC80 = [circle(0, 0, 40), circle(0, -26, 4, cw=True), circle(26, 0, 4, cw=True),
          circle(-26, 0, 4, cw=True), circle(0, 26, 4, cw=True)]
PLATE = [rect(-25, -60, 25, 25), circle(0, -30, 5, cw=True)]
WIDE = [rect(-25, -25, 70, 25)]
ROOMY = [rect(-80, -80, 80, 80)]
NARROW = [rect(-25, -80, 25, 25)]
BLOCK = [rect(-30.0, -36.0, 30.0, -24.0)]
DEEP = [rect(-30.0, -60.0, 30.0, -24.0)]
DISC120 = [circle(0, 0, 60, n=96), circle(18, -32, 3, cw=True)]
# Zach's GIM43 disc, as measured (tests/fixtures/aruco_label_gim43_disc.json)
GIM43 = ([circle(2.09, 0.0, 26.5, n=96)]
         + [circle(x, y, 1.425, n=96, cw=True, around=True)
            for x, y in ((25.84, 0.0), (2.09, 23.75), (-21.66, 0.0), (2.09, -23.75))])
DISC47 = [circle(0, 0, 23.75, n=96)]


def cases():
    out = []

    def add(title, spec, settings, **kw):
        out.append({"name": title, "spec": spec, "settings": settings, "kw": kw})
    n45 = {"nozzle_mm": 0.45}
    for side in ("auto", "below", "above", "left", "right"):
        add(f"strip {side}", SINGLE, dict(n45, on=True, place="white", side=side,
                                         content="id_name"), name="Actuator:3", grow=True)
        add(f"disc80 {side}", SINGLE, dict(n45, on=True, place="white", side=side),
            mode="black", op=None, region=DISC80)
    add("strip auto 0.6", SINGLE, {"on": True, "place": "white"}, grow=True)
    add("grid31 strip", GRID31, dict(n45, on=True, place="white"), grow=True)
    add("strip tight face", SINGLE, dict(n45, on=True, place="white"), grow=True,
        bounds=[rect(-25.0, -30.0, 25.0, 25.0)])
    add("strip no room", SINGLE, dict(n45, on=True, place="white", side="below"), grow=True,
        bounds=[rect(-25.0, -25.5, 25.0, 25.0)])
    add("strip cut + pins above", SINGLE, dict(n45, on=True, place="white", side="above",
                                               content="custom", text="#{id} ACTUATOR:3 LEFT"),
        grow=True, mark=("both", "new", "cut"), pins={"shape": "triangle", "size": 3.0})
    add("strip cut + pins left", SINGLE, dict(n45, on=True, place="white", side="left",
                                              content="custom", text="#{id} ACTUATOR:3 LEFT"),
        grow=True, mark=("both", "new", "cut"), pins={"shape": "triangle", "size": 3.0})
    add("white only strip above", SINGLE, dict(n45, on=True, place="white", side="above"),
        mode="white", op=None, grow=True)
    add("plate hole under", SINGLE, dict(n45, on=True, place="white"), mode="black", op=None,
        region=PLATE)
    add("wide plate auto", SINGLE, dict(n45, on=True, place="white"), mode="black", op=None,
        region=WIDE)
    add("keep-out below", SINGLE, dict(n45, on=True, place="white", side="below"),
        mode="black", op=None, region=ROOMY, keepouts=BLOCK)
    add("narrow, out below the keep-out", SINGLE, dict(n45, on=True, place="white",
                                                       side="below"),
        mode="black", op=None, region=NARROW, keepouts=BLOCK)
    add("narrow, deep keep-out: refused", SINGLE, dict(n45, on=True, place="white",
                                                       side="below"),
        mode="black", op=None, region=NARROW, keepouts=DEEP)
    add("sketch-area tile", SINGLE, dict(n45, on=True, place="white"),
        region=[rect(-35.0, -35.0, 35.0, 30.0)], tile=[-35.0, -35.0, 35.0, 30.0])
    add("typed cap 9", SINGLE, dict(n45, on=True, place="white", cap_mm=9.0), grow=True)
    add("typed cap 2.5 at 0.6: refused", SINGLE, {"on": True, "place": "white", "cap_mm": 2.5},
        grow=True)
    add("place auto, 20 mm: the white", SMALL, dict(n45, on=True), grow=True)
    add("black rows", BIG, {"on": True, "place": "black", "content": "id_name"}, name="Arm")
    for dx, dy in ((-10.0, -6.0), (10.0, 0.0), (0.0, 4.0)):
        add(f"disc120 offset ({dx:g}, {dy:g})", SINGLE,
            {"on": True, "place": "white", "side": "below", "content": "id_name", "cap_mm": 4.0,
             "offset_x_mm": dx, "offset_y_mm": dy}, mode="black", op=None, region=DISC120,
            name="Actuator")
    add("strip offset (+2, -1.5)", SINGLE, dict(n45, on=True, place="white", offset_x_mm=2.0,
                                               offset_y_mm=-1.5), grow=True)
    add("black offset (+3, +2)", BIG, {"on": True, "place": "black", "content": "id_name",
                                       "offset_x_mm": 3.0, "offset_y_mm": 2.0}, name="Arm")
    add("47.5 disc above at 0.4: refused", GIM, {"on": True, "place": "white", "side": "above",
                                                "nozzle_mm": 0.4},
        mode="black", op=None, region=DISC47, slab=[-1.6, -1.0])
    add("GIM43 auto", GIM, {"on": True, "content": "id", "place": "white", "side": "auto",
                            "nozzle_mm": 0.6}, mode="black", op=None, region=GIM43,
        mark=("black", None, "triangle"))
    add("GIM43 Zach's offset (6, 4)", GIM, {"on": True, "content": "id", "place": "white",
                                           "side": "auto", "nozzle_mm": 0.6,
                                           "offset_x_mm": 6.0, "offset_y_mm": 4.0},
        mode="black", op=None, region=GIM43, mark=("black", None, "triangle"))
    add("GIM43 build anyway", GIM, {"on": True, "content": "id", "place": "white",
                                    "side": "below", "nozzle_mm": 0.6, "build_anyway": True},
        mode="black", op=None, region=GIM43, mark=("black", None, "triangle"))
    return out


def run(case, L, M, C):
    spec = M.TagSpec.from_dict(dict(case["spec"]), lambda m: None, "golden")
    kw = dict(case["kw"])
    if kw.get("mark") is not None:
        mode, op, want = kw["mark"]
        kw["mark"] = C.mark_for_spec(spec, mode, op, want=want)
    for k in ("tile", "slab"):
        if kw.get(k) is not None:
            kw[k] = tuple(kw[k])
    return L.plan_label(spec, dict(case["settings"]), **kw)


def shape(lab):
    """What must not move: kind, side, each slot's rect, each part's rect and
    strokes, the grown white, a refused label's preview (the same)."""
    def one(lb):
        return {"kind": lb.kind, "side": lb.side, "forced": bool(lb.forced),
                "slots": [list(s.rect) for s in lb.slots],
                "parts": [{"rect": list(p.rect), "cap": p.cap, "lines": list(p.lines),
                           "boxes": [b.to_list(9) for b in p.boxes]} for p in lb.parts],
                "white": list(lb.white) if lb.white else None,
                "strip": list(lb.strip) if lb.strip else None}
    d = one(lab)
    d["preview"] = one(lab.preview) if lab.preview is not None else None
    return d


