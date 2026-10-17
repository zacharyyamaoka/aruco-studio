"""Checks of the scene as a whole (audit F13). Standard library only.

| Check | Level | Said as |
|---|---|---|
| two visible tags' targets overlap on the canvas | warn | "board1 overlaps tag1 (120.0 mm²)" |

A tag's footprint is its target's outline (its loops, holes included, or
its box) placed by the tag's pose: what is cut or printed. Two footprints
that share more than `MIN_MM2` overlap: the parts would collide, and one
tag can cover the other's markers or quiet zone.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..plan import region as _R
from .model import Scene

MIN_MM2 = 0.01


def footprint(t) -> List[List[tuple]]:
    """The tag's target outline in scene mm: [outer, hole, ...]."""
    P = t.pose
    f = lambda u, v: (P[0] * u + P[1] * v + P[3], P[4] * u + P[5] * v + P[7])
    return [[f(u, v) for u, v in lp] for lp in t.spec.target.outline_mm()]


def _box(poly):
    xs = [x for lp in poly for x, _y in lp]
    ys = [y for lp in poly for _x, y in lp]
    return min(xs), min(ys), max(xs), max(ys)


def overlap_mm2(a, b) -> float:
    """The area two footprints share (mm²)."""
    ba, bb = _box(a), _box(b)
    if ba[2] <= bb[0] or bb[2] <= ba[0] or ba[3] <= bb[1] or bb[3] <= ba[1]:
        return 0.0
    traps = _R.boolean([[a], [b]], lambda s: s[0] and s[1])
    return sum(tr.area for tr in traps)


def overlaps(scene: Scene) -> List[dict]:
    """[{tags: [a, b], mm2}] for every pair of visible tags whose targets overlap."""
    vis = [t for t in scene.tags if not t.hidden]
    fps = {t.name: footprint(t) for t in vis}
    out = []
    for i, a in enumerate(vis):
        for b in vis[i + 1:]:
            mm2 = overlap_mm2(fps[a.name], fps[b.name])
            if mm2 > MIN_MM2:
                out.append({"tags": [a.name, b.name], "mm2": round(mm2, 2)})
    return out


def scene_issues(scene: Scene, plans: Optional[Dict[str, object]] = None) -> List[dict]:
    """The scene's own messages: [{tags, level, text}] (shown on the canvas
    and in the sheet's Verify)."""
    out = []
    for o in overlaps(scene):
        a, b = o["tags"]
        out.append({"tags": [a, b], "level": "warn", "kind": "overlap",
                    "text": f"{b} overlaps {a} ({o['mm2']:.1f} mm²): move one of them"})
    return out
