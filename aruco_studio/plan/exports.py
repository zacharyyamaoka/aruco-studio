"""Exports of one plan: JSON, SVG (1:1 mm), STL. Standard library only.

| Function | Gives |
|---|---|
| `to_json(plan)` | the TagPlan as canonical JSON (sorted keys) |
| `to_svg(plan)` | the top view as vectors (plan/mesh.top), 1 unit = 1 mm, `width` / `height` in mm: prints at true size; the viewBox is the tile (White + black) or the sticker |
| `svg_paths(plan)` | the same as `<path>`s in the pattern frame, for a sheet or a scene |
| `to_stl(plan)` | binary STL of the plan's bodies (plan/mesh.stl) |

PNG is the server's (it rasterises with verify/render, numpy + OpenCV).
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from . import mesh as _ME

COLOURS = {"white": "#ffffff", "black": "#000000", "body": "#d9d9d9"}


def _d(plan):
    return plan.to_dict() if hasattr(plan, "to_dict") else plan


def to_json(plan) -> str:
    return json.dumps(_d(plan), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _f(v):
    t = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if t in ("-0", "") else t


def path_d(polygons, tx=lambda u, v: (u, -v)) -> str:
    """An SVG path (every loop of every polygon; fill-rule evenodd)."""
    out = []
    for poly in polygons:
        for lp in poly:
            if len(lp) < 3:
                continue
            pts = [tx(u, v) for u, v in lp]
            out.append("M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts) + " Z")
    return " ".join(out)


def view_rect(plan) -> List[float]:
    """The rect an SVG of the tag shows: its tile, else its sticker (mm,
    pattern frame), grown to the label's white when a strip grew it."""
    d = _d(plan)
    g = d["guides"]
    r = list(g["tile"] or g["sticker"])
    lab = d.get("label") or {}
    if lab.get("white"):
        w = lab["white"]
        r = [min(r[0], w[0]), min(r[1], w[1]), max(r[2], w[2]), max(r[3], w[3])]
    return r


def svg_paths(plan, colours: Optional[Dict[str, str]] = None, body: bool = False) -> List[str]:
    """`<path>`s of the top view in the pattern frame with y flipped (SVG's
    y down): one per colour, data-layer = its colour."""
    colours = dict(COLOURS, **(colours or {}))
    out = []
    for c, polys in sorted(_ME.top(plan).items(), key=lambda kv: ("body", "white", "black").index(kv[0])):
        if c == "body" and not body:
            continue
        out.append(f'<path data-layer="{c}" fill="{colours[c]}" fill-rule="evenodd" '
                   f'd="{path_d(polys)}"/>')
    return out


def to_svg(plan, margin_mm: float = 0.0, background: Optional[str] = "#ffffff",
           guides: bool = False) -> str:
    """One tag at true size."""
    d = _d(plan)
    if not d.get("ok"):
        raise ValueError("a refused plan has nothing to draw: " + "; ".join(d.get("errors") or []))
    u0, v0, u1, v1 = view_rect(d)
    u0, v0, u1, v1 = u0 - margin_mm, v0 - margin_mm, u1 + margin_mm, v1 + margin_mm
    w, h = u1 - u0, v1 - v0
    body = []
    if background:
        body.append(f'<rect x="{_f(u0)}" y="{_f(-v1)}" width="{_f(w)}" height="{_f(h)}" '
                    f'fill="{background}"/>')
    body += svg_paths(d)
    if guides:
        g = d["guides"]
        for k, col in (("quiet_ring", "#3a86ff"), ("clear_hard", "#ff006e")):
            r = g[k]
            body.append(f'<rect data-guide="{k}" x="{_f(r[0])}" y="{_f(-r[3])}" '
                        f'width="{_f(r[2] - r[0])}" height="{_f(r[3] - r[1])}" fill="none" '
                        f'stroke="{col}" stroke-width="0.1"/>')
    title = f"{d['marker']['dictionary']} #{d['ids'][0]}" if d.get("ids") else "tag"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{_f(w)}mm" height="{_f(h)}mm" '
            f'viewBox="{_f(u0)} {_f(-v1)} {_f(w)} {_f(h)}">'
            f'<title>{title}</title>' + "".join(body) + "</svg>")


def to_stl(plan, what=None) -> bytes:
    d = _d(plan)
    name = f"arucostudio {d.get('key') or ''} {d['marker']['dictionary']} {d['ids'][:1]}"
    return _ME.stl(d, what=what, name=name)
