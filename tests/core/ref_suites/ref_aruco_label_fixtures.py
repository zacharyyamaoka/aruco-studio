# REF: tests/aruco_label_fixtures.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""Fixtures for the label suites and renders, loaded from data files only:
swapping in a measured face is a JSON edit, never a code change.

    gim43()  Zach's GIM43 disc (tests/fixtures/aruco_label_gim43_disc.json)
             -> {"spec": TagSpec, "region": [loop mm], "mode", "label": dict,
                 "zach": {"legacy_offset_mm", "position_mm"}, "source": str}

A loop is given either as points ("loops_mm": [[[x, y], ...], ...], the
outer one first, holes after) or as primitives ("face_mm": {"outer": [...],
"holes": [...]}, each {"circle": [cx, cy, r]} or {"poly": [[x, y], ...]}).
Circles become polygons drawn AROUND the circle for the outer loop's
holes (a hole is never smaller than drawn) and INSIDE it for the outer
edge (the face never bigger than drawn).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
GIM43 = HERE.parents[2] / "goldens" / "ref" / "aruco_label_gim43_disc.json"


def _circle(cx, cy, r, n, around, cw):
    rr = r / math.cos(math.pi / n) if around else r
    pts = [(cx + rr * math.cos(2 * math.pi * k / n), cy + rr * math.sin(2 * math.pi * k / n))
           for k in range(n)]
    return pts[::-1] if cw else pts


def _loop(prim, n, hole):
    if "circle" in prim:
        cx, cy, r = (float(v) for v in prim["circle"])
        return _circle(cx, cy, r, n, around=hole, cw=hole)
    return [(float(p[0]), float(p[1])) for p in prim["poly"]]


def region_of(d):
    """The face's loops (mm, pattern frame) from a fixture dict."""
    if d.get("loops_mm"):
        return [[(float(p[0]), float(p[1])) for p in lp] for lp in d["loops_mm"]]
    n = int(d.get("segments", 96))
    face = d["face_mm"]
    return ([_loop(p, n, False) for p in face["outer"]]
            + [_loop(p, n, True) for p in face.get("holes", ())])


def gim43(path=GIM43):
    """... + "mark": the corner mark the tag has (aruco_chamfer.Mark or None),
    "plan": the plan_label keywords (mode, op, region, mark) for it."""
    from aruco_studio.core import chamfer as C
    from aruco_studio.core import markers as M
    d = json.loads(Path(path).read_text(encoding="utf-8"))["golden"]
    spec = M.TagSpec.from_dict(dict(d["spec"]), lambda m: None, "gim43")
    mode = d.get("mode", "black")
    op = d.get("op") if mode == "both" else None
    mark = None
    if d.get("corner_mark") in ("triangle", "cut"):
        mark = C.mark_for_spec(spec, mode, op, want=d["corner_mark"])
        if mark.kind == "none":
            mark = None
    region = region_of(d)
    return {"spec": spec, "region": region, "mode": mode, "mark": mark,
            "label": dict(d["label"]), "zach": dict(d.get("zach") or {}),
            "source": d.get("source", ""),
            "plan": {"mode": mode, "op": op, "region": region, "mark": mark}}
