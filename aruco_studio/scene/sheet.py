"""A scene as one 1:1 print sheet (SVG, mm), as polygons in scene mm, and
as a PDF print sheet of stickers. Standard library only.

The PDF (`to_pdf`, Definition of Done D6) is REF's print sheet
(core.sheet, REF print_sheet): every visible, planned tag as one sticker,
its board as built (TagPlan.marker), laid out on pages with cut marks, the
id in the border row and the ruler. It is a sheet of printed stickers, not
the canvas: the tags are packed, not placed where the scene puts them.

Each tag's top view (plan/mesh.top: what is seen from above) is moved to
its place: scene <- the tag's target frame (its pose) <- the pattern frame
(TagPlan.frames.pattern_in_target). The sheet's viewBox is the scene's
extent plus a margin, y up in the scene and down on paper.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..core import sheet as _SH
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


def print_items(scene: Scene, plans: Optional[dict] = None) -> List["_SH.PrintItem"]:
    """One sticker per visible, planned tag (REF markers.print_items' fields):
    its board as built, the identity line and where it goes."""
    plans = plans if plans is not None else scene.plans()
    out = []
    for t in scene.tags:
        p = plans[t.name]
        if t.hidden or not p.ok:
            continue
        sp = p.ev["spec"]
        kw = {}
        if sp.layout != "single":
            kw = dict(layout=sp.layout, rows=sp.rows, cols=sp.cols, separation_m=sp.separation_m,
                      square_length_m=sp.square_length_m, legacy=sp.legacy)
        out.append(_SH.PrintItem(key=t.name, dictionary=sp.dictionary, marker_id=sp.marker_id,
                                 marker_length_m=sp.marker_length_m,
                                 quiet_modules=sp.quiet_modules,
                                 label_lines=[sp.label(), f"{scene.name} · {t.name}"],
                                 top_label=t.name, **kw))
    return out


def pdf_layout(scene: Scene, plans: Optional[dict] = None, page: str = "a4",
               landscape: bool = False) -> "_SH.SheetLayout":
    """The sticker sheet's layout (core.sheet.layout_sheet): pages, places,
    the rejected tags with why."""
    st = _SH.SheetSettings(page=page, landscape=landscape, title=scene.name)
    return _SH.layout_sheet(print_items(scene, plans), st)


def to_pdf(scene: Scene, plans: Optional[dict] = None, page: str = "a4",
           landscape: bool = False, date: Optional[str] = None) -> bytes:
    """The scene's stickers as a PDF at true size (core.sheet.render_layout_pdf)."""
    return _SH.render_layout_pdf(pdf_layout(scene, plans, page, landscape), date=date)


# ------------------------------------------------------------- the sticker sheet (M6a)
#
# The sheet drawn from the PLAN (core.sheet.layout_stickers): every visible,
# planned sticker tag (and, with `proofs`, the 3D tags as paper proofs) as
# one item whose outline is the plan's cut line (guides.cut_line; a 3D
# proof: its sticker rectangle) and whose black is the plan's top view
# (plan/mesh.top(plan)["black"]): what the canvas and the Fusion body show.

def caption_of(plan_d: dict, name: str) -> str:
    """`#12 · forearm_left · 4X4_50 · 28.0 mm` (the words for a spaced gap)."""
    from ..core import label as _L
    ids = plan_d.get("ids") or [0]
    idw = f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}-{ids[-1]}"
    mk = plan_d["marker"]
    size = mk["marker_length_m"] * 1000.0
    return f"{idw} · {name} · {_L.dict_short(mk['dictionary'])} · {size:.1f} mm"


def sticker_item(t, p) -> "_SH.PrintItem":
    """One scene tag's plan as a sticker sheet item (its own frame: the
    pattern frame, mm, y up)."""
    d = p.data if hasattr(p, "data") else p
    g = d["guides"]
    cut = g.get("cut_line")
    if cut:
        outline = {"outer": [list(q) for q in cut["outer"]],
                   "holes": [[list(q) for q in h] for h in cut.get("holes", [])]}
    else:
        u0, v0, u1, v1 = g["sticker"]
        outline = {"outer": [[u0, v0], [u1, v0], [u1, v1], [u0, v1]], "holes": []}
    ink = _ME.top(d).get("black", [])
    sp = d["marker"]
    kw = {}
    if sp["layout"] != "single":
        kw = dict(layout=sp["layout"], rows=int(sp["rows"]), cols=int(sp["cols"]),
                  separation_m=float(sp.get("separation_m") or 0.0),
                  square_length_m=float(sp.get("square_length_m") or 0.0),
                  legacy=bool(sp.get("legacy")))
    return _SH.PrintItem(key=t.name, dictionary=sp["dictionary"], marker_id=int(sp["marker_id"]),
                         marker_length_m=float(sp["marker_length_m"]),
                         quiet_modules=float(sp.get("quiet_modules", 1.0)),
                         cut_mm=outline, ink_mm=ink, caption=caption_of(d, t.name),
                         made_by=d.get("made_by") or "print3d", name=t.name,
                         ids=list(d.get("ids") or []), **kw)


def sticker_items(scene: Scene, plans: Optional[dict] = None, proofs: bool = False
                  ) -> List["_SH.PrintItem"]:
    """The visible, planned sticker tags (with `proofs`, the 3D tags too)."""
    plans = plans if plans is not None else scene.plans()
    out = []
    for t in scene.tags:
        p = plans[t.name]
        if t.hidden or not p.ok:
            continue
        if p.data.get("made_by") != "sticker" and not proofs:
            continue
        out.append(sticker_item(t, p))
    return out


def sheet_settings(scene: Scene, page: str = "letter", landscape: bool = False,
                   mode: str = "spaced", margin_mm: float = 10.0) -> "_SH.SheetSettings":
    return _SH.SheetSettings(page=page, landscape=bool(landscape), mode=mode,
                             margin_mm=float(margin_mm), title=scene.name)


def sticker_layout(scene: Scene, plans: Optional[dict] = None, page: str = "letter",
                   landscape: bool = False, mode: str = "spaced", margin_mm: float = 10.0,
                   proofs: bool = False) -> "_SH.StickerLayout":
    return _SH.layout_stickers(sticker_items(scene, plans, proofs),
                               sheet_settings(scene, page, landscape, mode, margin_mm))


def sticker_files(scene: Scene, plans: Optional[dict] = None, page: str = "letter",
                  landscape: bool = False, mode: str = "spaced", margin_mm: float = 10.0,
                  proofs: bool = False, date: Optional[str] = None) -> dict:
    """{"sheet.pdf", "sheet.svg", "sheet.json"} (bytes) of one layout, and
    the layout itself under "layout"."""
    import json as _json
    lay = sticker_layout(scene, plans, page, landscape, mode, margin_mm, proofs)
    summary = _SH.sticker_summary(lay)
    return {"layout": lay,
            "sheet.pdf": _SH.render_sticker_pdf(lay, date=date),
            "sheet.svg": _SH.render_sticker_svg(lay, date=date).encode("utf-8"),
            "sheet.json": (_json.dumps(summary, indent=1, sort_keys=True, ensure_ascii=False)
                           + "\n").encode("utf-8")}
