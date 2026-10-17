"""A scene as one 1:1 print sheet (SVG, mm) and as polygons in scene mm.
Standard library only.

Each tag's top view (plan/mesh.top: what is seen from above) is moved to
its place: scene <- the tag's target frame (its pose) <- the pattern frame
(TagPlan.frames.pattern_in_target). The sheet's viewBox is the scene's
extent plus a margin, y up in the scene and down on paper.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..plan import exports as _X
from ..plan import mesh as _ME
from .model import Scene, mat_mul

COLOURS = dict(_X.COLOURS)


def _xf(M):
    return lambda u, v: (M[0] * u + M[1] * v + M[3], M[4] * u + M[5] * v + M[7])


def items(scene: Scene, plans: Optional[dict] = None, body: bool = False) -> List[dict]:
    """[{tag, colour, polygons (scene mm)}] of every visible, planned tag."""
    plans = plans if plans is not None else scene.plans()
    out = []
    for t in scene.tags:
        p = plans[t.name]
        if t.hidden or not p.ok:
            continue
        M = mat_mul(t.pose, p.data["frames"]["pattern_in_target"])
        f = _xf(M)
        for c, polys in _ME.top(p).items():
            if c == "body" and not body:
                continue
            out.append({"tag": t.name, "colour": c,
                        "polygons": [[[f(u, v) for u, v in lp] for lp in poly] for poly in polys]})
    return out


def bounds(its: List[dict], margin: float = 5.0):
    xs = [x for it in its for poly in it["polygons"] for lp in poly for x, _y in lp]
    ys = [y for it in its for poly in it["polygons"] for lp in poly for _x, y in lp]
    if not xs:
        return (-margin, -margin, margin, margin)
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def to_svg(scene: Scene, plans: Optional[dict] = None, margin_mm: float = 5.0,
           background: str = "#ffffff") -> str:
    """The scene at true size: every tag where the canvas puts it."""
    its = items(scene, plans)
    x0, y0, x1, y1 = bounds(its, margin_mm)
    w, h = x1 - x0, y1 - y0
    f = _X._f
    body = [f'<rect x="{f(x0)}" y="{f(-y1)}" width="{f(w)}" height="{f(h)}" fill="{background}"/>']
    by_tag: Dict[str, list] = {}
    for it in its:
        by_tag.setdefault(it["tag"], []).append(it)
    order = ("body", "white", "black")
    for tag, lst in by_tag.items():
        paths = []
        for it in sorted(lst, key=lambda i: order.index(i["colour"])):
            d = _X.path_d(it["polygons"], tx=lambda u, v: (u, -v))
            paths.append(f'<path data-layer="{it["colour"]}" fill="{COLOURS[it["colour"]]}" '
                         f'fill-rule="evenodd" d="{d}"/>')
        body.append(f'<g data-tag="{tag}">' + "".join(paths) + "</g>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}mm" height="{f(h)}mm" '
            f'viewBox="{f(x0)} {f(-y1)} {f(w)} {f(h)}"><title>{scene.name}</title>'
            + "".join(body) + "</svg>")
