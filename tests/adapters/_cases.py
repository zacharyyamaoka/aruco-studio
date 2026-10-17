"""The evaluate() golden cases (goldens/evaluate/*.json, made by REF's own
evaluate() at c8216ff) as TagPlans, and a 2D evaluation of a recipe's
CSG that knows nothing of Fusion (the probes' expected answer)."""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from aruco_studio.plan import plan_tag
from aruco_studio.plan.spec import TagSpec

ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "goldens" / "evaluate"
GROUPS = ("legacy", "matrix")


@lru_cache(maxsize=None)
def cases(group):
    return json.loads((GOLD / f"{group}.json").read_text(encoding="utf-8"))["cases"]


@lru_cache(maxsize=None)
def plans(group):
    """[(case id, TagPlan)] of every case REF built (no "error" out)."""
    out = []
    for c in cases(group):
        if "error" in c["out"]:
            continue
        p = plan_tag(TagSpec.from_dict(c["in"]))
        out.append((c["id"], p))
    return out


def all_plans():
    for g in GROUPS:
        for cid, p in plans(g):
            yield f"{g}:{cid}", p


# ------------------------------------------------------------ 2D CSG

def _in_poly(pts, u, v):
    inside = False
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def layer_has(layer, u, v):
    """Is (u, v) inside one of the plan layer's outlines (its circles when it
    has them)?"""
    circles = layer.get("circles") or []
    if circles and len(circles) == len(layer["polygons"]):
        return any(math.hypot(u - c["c"][0], v - c["c"][1]) <= c["r"] for c in circles)
    for q in layer["polygons"]:
        if _in_poly(q["outer"], u, v) and not any(_in_poly(h, u, v) for h in q["holes"]):
            return True
    return False


def _segments(layers):
    """Every edge of the layers as (x0, y0, x1, y1, min x, max x, min y,
    max y); circles as (cx, cy, r)."""
    segs, circs = [], []
    for L in layers:
        circles = L.get("circles") or []
        if circles and len(circles) == len(L["polygons"]):
            circs += [(c["c"][0], c["c"][1], c["r"]) for c in circles]
            continue
        for q in L["polygons"]:
            for lp in [q["outer"]] + list(q["holes"]):
                for i in range(len(lp)):
                    (a, b), (c, d) = lp[i - 1], lp[i]
                    segs.append((a, b, c, d, min(a, c), max(a, c), min(b, d), max(b, d)))
    return segs, circs


def near_edge(segments, u, v, tol=1e-4):
    segs, circs = segments
    for cx, cy, r in circs:
        if abs(math.hypot(u - cx, v - cy) - r) < 1e-3:
            return True
    for a, b, c, d, x0, x1, y0, y1 in segs:
        if u < x0 - tol or u > x1 + tol or v < y0 - tol or v > y1 + tol:
            continue
        if _seg_dist((u, v), (a, b), (c, d)) < tol:
            return True
    return False


def part_has(layers, part, u, v, z):
    """The plan's own answer: is (u, v, z) mm inside the part? A part is the
    union of its solids; a solid its steps in order."""
    solids = {}
    for L in layers:
        if L["part"] == part:
            solids.setdefault(L["solid"], []).append(L)
    for steps in solids.values():
        state = False
        for L in steps:
            hit = L["z"][0] <= z <= L["z"][1] and layer_has(L, u, v)
            state = (state or hit) if L["step"] == "add" else (state and not hit)
        if state:
            return True
    return False


def probe_points(layers, part):
    """One interior point per outline of the part (its centroid), at the mid
    height of its layer; points near an edge or a z bound of the part are
    skipped (a probe there would ask about the boundary)."""
    mine = [L for L in layers if L["part"] == part]
    segs = _segments(mine)
    zs = sorted({z for L in mine for z in L["z"]})
    out = []
    for L in mine:
        zm = (L["z"][0] + L["z"][1]) / 2.0
        if any(abs(zm - z) < 1e-4 for z in zs):
            continue
        circles = L.get("circles") or []
        use_c = circles and len(circles) == len(L["polygons"])
        for i, q in enumerate(L["polygons"]):
            if use_c:
                u, v = circles[i]["c"]
            else:
                pts = q["outer"]
                u = sum(p[0] for p in pts) / len(pts)
                v = sum(p[1] for p in pts) / len(pts)
            if near_edge(segs, u, v):
                continue
            out.append((L["name"], u, v, zm))
    return out
