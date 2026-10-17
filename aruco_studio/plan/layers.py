"""TagPlan: what every shell builds, draws or writes (ARCHITECTURE 5.3).

Lengths are mm in the PATTERN frame: origin at the pattern's centre ON THE
FACE PLANE, u = image right, v = image up, AFTER the Origin turn; z along
the face normal, 0 at the face, + out of it. The frame core.chamfer,
core.label and core.trim already use.

Layers are REF's temporary bodies, step by step (ArucoMarkers/aruco_feature
`part_body` and aruco_tags `cells_temp_body`, `mark_cells`, `mark_white`,
`mark_tile`, `mark_label`, `poly_prism_temp_body`), so an adapter that
builds them in order rebuilds today's bodies exactly:

| Field | Meaning |
|---|---|
| `part` | the `parts` entry it belongs to (tile, pin, pocket, pattern, recess, trim) |
| `solid` | which solid of its part (a part is the UNION of its solids: the recess is the tile's, the pattern's and the holes') |
| `step` | "add": unite with the solid so far; "sub": take it away (a cut tool, MARK_PAD / SOLID_PAD past the slab, as REF) |
| `op` | what the PART does to the assembly: "add" material, "cut" what is under, "keep" only this column (trim) |
| `colour` | what an "add" step prints as ("white" / "black"); "none" for a cut tool and the trim column |
| `z` | [lo, hi] mm along the normal |
| `polygons` | [{outer, holes}] (outer counter-clockwise) |
| `circles` | the round pins / holes as [{c, r}] when the polygons approximate circles |

`combines` says where each part goes (REF `_combines`): the tile joined to
the body under (Join) or new, the pins joined to the tile, the pocket cut
from the tile / the joined body, the pattern a body of its own, the recess
cut from the body under, the trim intersected with it.

A printed sticker (core.make, M6a) has two parts: `sticker` (the white
stock, z [0, t], its cut polygon) and `ink` (black, z [t, t + INK]: the
cells, the corner triangle and the label exactly as the pattern's
footprint makes them), each a body of its own.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..core import label as _AL
from ..core import markers as _M
from ..core import slabs as _SL
from ..core import trim as _TR
from ..core.geometry import _dot_f as _dot

SCHEMA = "arucostudio.tagplan/1"
MARK_PAD_MM = 0.1                 # aruco_tags.MARK_PAD_CM: a cut tool past the slab
CELLS_PAD_MM = 0.1                # white_temp_body's slightly taller black cells (0.01 cm)
PIN_JOIN_OVERLAP_MM = 0.01        # aruco_feature.PIN_JOIN_OVERLAP_CM
CIRCLE_SEGMENTS = 64

Pt = Tuple[float, float]
Rect = Tuple[float, float, float, float]


def _r(v, nd=9):
    """JSON numbers: rounded far below any print (1e-9 mm), no -0.0."""
    return round(float(v), nd) + 0.0


def _pts(pts):
    return [[_r(u), _r(v)] for u, v in pts]


def _area2(pts):
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def ccw(pts):
    pts = [(float(u), float(v)) for u, v in pts]
    return pts if _area2(pts) >= 0 else pts[::-1]


def rect_pts(r: Rect) -> List[Pt]:
    u0, v0, u1, v1 = r
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


@dataclass
class Layer:
    name: str
    part: str
    solid: int
    step: str
    op: str
    colour: str
    z: Tuple[float, float]
    polygons: List[dict]
    circles: Optional[List[dict]] = None

    def to_dict(self) -> dict:
        d = {"name": self.name, "part": self.part, "solid": self.solid, "step": self.step,
             "op": self.op, "colour": self.colour, "z": [_r(self.z[0]), _r(self.z[1])],
             "polygons": [{"outer": _pts(p["outer"]), "holes": [_pts(h) for h in p.get("holes", [])]}
                          for p in self.polygons]}
        if self.circles:
            d["circles"] = [{"c": [_r(c["c"][0]), _r(c["c"][1])], "r": _r(c["r"])}
                            for c in self.circles]
        return d


def poly(pts, holes=()) -> dict:
    return {"outer": ccw(pts), "holes": [list(reversed(ccw(h))) for h in holes]}


PART_OP = {"tile": "add", "pin": "add", "pocket": "cut", "pattern": "add", "recess": "cut",
           "trim": "keep", "sticker": "add", "ink": "add"}
STICKER_PARTS = ["sticker", "ink"]


class LayerBuilder:
    """REF's part_body, as layers (mm, the pattern frame)."""

    def __init__(self, ev, n, frames):
        self.ev = ev
        self.n = n
        self.fr = frames
        self.out: List[Layer] = []
        self.solid = {}

    # -- helpers
    def _next_solid(self, part):
        k = self.solid.get(part, -1) + 1
        self.solid[part] = k
        return k

    def add(self, name, part, solid, step, colour, lo, hi, polygons, circles=None):
        if not polygons:
            return
        self.out.append(Layer(name=name, part=part, solid=solid, step=step, op=PART_OP[part],
                              colour=colour if step == "add" and PART_OP[part] == "add"
                              else "none",
                              z=(float(min(lo, hi)), float(max(lo, hi))), polygons=polygons,
                              circles=circles))

    # -- the pieces
    def cells(self):
        spec = self.ev["spec"]
        return [poly(rect_pts((x0 * 1000.0, y0 * 1000.0, x1 * 1000.0, y1 * 1000.0)))
                for (x0, y0, x1, y1) in _M.cell_boxes(spec)]

    def tile_rect(self):
        return self.fr["tile_rect"]

    def footprint(self, part, name, lo, hi):
        """REF _footprint: the pattern's footprint lo..hi mm over the face,
        with the corner mark and the label (one solid)."""
        ev = self.ev
        mark = ev.get("mark")
        kind = mark.kind if mark is not None else "none"
        k = self._next_solid(part)
        lab = _label_of(ev.get("label"))
        colour = "white" if ev.get("mode") == "white" else "black"
        if ev.get("mode") == "white":
            rect = ev.get("label_white")
            if rect is None:
                tw, th = (v * 1000.0 for v in ev["spec"].tile_size_m)
                rect = (-tw / 2.0, -th / 2.0, tw / 2.0, th / 2.0)
            self.add("white_strip" if ev.get("label_white") is not None else name, part, k,
                     "add", colour, lo, hi, [poly(rect_pts(rect))])
            self.add("cells", part, k, "sub", "none", lo - CELLS_PAD_MM, hi + CELLS_PAD_MM,
                     self.cells())
            if kind == "black_cut" and mark.tool:
                # box - (cells - tool) = (box - cells) + (box & tool)
                kept = _TR.clip(list(mark.tool), tuple(rect))
                if len(kept) >= 3:
                    self.add("mark_keep", part, k, "add", colour, lo, hi, [poly(kept)])
            if kind == "triangle" and mark.solid:
                self.add("mark_triangle", part, k, "sub", "none", lo - MARK_PAD_MM,
                         hi + MARK_PAD_MM, [poly(mark.solid)])
            if lab is not None:
                self._label(part, k, lab, lo, hi, white=True, colour=colour)
            return
        self.add(name, part, k, "add", colour, lo, hi, self.cells())
        if kind == "black_cut" and mark.tool:
            self.add("mark_cut", part, k, "sub", "none", lo - MARK_PAD_MM, hi + MARK_PAD_MM,
                     [poly(mark.tool)])
        elif kind == "triangle" and mark.solid:
            self.add("mark_triangle", part, k, "add", colour, lo, hi, [poly(mark.solid)])
        if lab is not None:
            self._label(part, k, lab, lo, hi, white=False, colour=colour)

    def _label(self, part, k, lab, lo, hi, white, colour):
        joins = (lab.role == "add") == (not white)            # aruco_tags.label_joins
        polys = [poly(b.corners()) for b in lab.boxes()]
        if joins:
            self.add("label_join", part, k, "add", colour, lo, hi, polys)
        else:
            self.add("label_cut", part, k, "sub", "none", lo - MARK_PAD_MM, hi + MARK_PAD_MM,
                     polys)

    def tile(self, part, name, lo, hi):
        """REF _tile: the tile lo..hi over the face, its corner cut."""
        k = self._next_solid(part)
        self.add(name, part, k, "add", "white", lo, hi, [poly(rect_pts(self.tile_rect()))])
        mark = self.ev.get("mark")
        if mark is not None and mark.kind == "tile_cut" and mark.tool:
            self.add("mark_cut", part, k, "sub", "none", lo - MARK_PAD_MM, hi + MARK_PAD_MM,
                     [poly(mark.tool)])

    def pins(self, part, name, lo, hi, grow=0.0):
        """REF pins_temp_body: each pin its own solid (a union)."""
        cu, cv = self.fr["pin_centre"]
        for p in self.ev["pins"]:
            q = _SL.grow(p, grow) if grow else p
            k = self._next_solid(part)
            if q["kind"] == "circle":
                (u, v), r = q["c"], q["r"]
                pts = [(cu + u + r * math.cos(2 * math.pi * i / CIRCLE_SEGMENTS),
                        cv + v + r * math.sin(2 * math.pi * i / CIRCLE_SEGMENTS))
                       for i in range(CIRCLE_SEGMENTS)]
                self.add(name, part, k, "add", "white" if part == "pin" else "none", lo, hi,
                         [poly(pts)], circles=[{"c": (cu + u, cv + v), "r": r}])
            else:
                self.add(name, part, k, "add", "white" if part == "pin" else "none", lo, hi,
                         [poly([(cu + a, cv + b) for a, b in q["pts"]])])

    def build(self):
        ev = self.ev
        plan = ev["plan"]
        for role in plan.parts:
            if role == "tile":
                lo, hi = plan.layers.white
                self.tile("tile", "tile", lo, hi)
            elif role == "pin":
                lo, hi = plan.pin
                self.pins("pin", "pin", lo, hi + PIN_JOIN_OVERLAP_MM)
            elif role == "pocket":
                lo, hi = plan.pocket
                self.footprint("pocket", "pocket", lo, hi)
            elif role == "pattern":
                lo, hi = plan.layers.pattern
                self.footprint("pattern", "pattern", lo, hi)
            elif role == "recess":
                for what, (lo, hi) in plan.recess:
                    if what == "tile":
                        self.tile("recess", "recess_tile", lo, hi)
                    elif what == "pattern":
                        self.footprint("recess", "recess_pattern", lo, hi)
                    elif what == "hole":
                        self.pins("recess", "hole", lo, hi,
                                  grow=float(self.n.get("pin_tol", _SL.PIN_TOL_MM)))
            elif role == "trim":
                tp = ev.get("trim")
                if tp is None:
                    tp = _TR.failed("both", None, "not evaluated")
                zr = tp.z if tp.z is not None else (0.0, 0.0)
                k = self._next_solid("trim")
                self.add("trim_keep", "trim", k, "add", "none", zr[0] - tp.pad, zr[1] + tp.pad,
                         [poly(rect_pts(tp.column()))])
        return self.out


def sticker_layers(ev, n, frames, make, cut) -> List[Layer]:
    """A sticker's layers: the white stock (its cut polygon) and the ink."""
    from ..core import make as _MK
    t = float(make.thickness_mm)
    lb = LayerBuilder(ev, n, frames)
    lb.add("sticker", "sticker", lb._next_solid("sticker"), "add", "white", 0.0, t,
           [poly(cut["outer"], cut["holes"])])
    lb.footprint("ink", "ink", t, t + _MK.INK_MM)
    return lb.out


def sticker_combines():
    return [{"part": "sticker", "op": "new", "into": None},
            {"part": "ink", "op": "new", "into": None}]


def _minus(outer, tool):
    """`outer` (ccw) less the polygon `tool`, as one ccw loop (plan/region)."""
    from . import region as RG
    traps = RG.boolean([[[list(outer)]], [[list(tool)]]], lambda f: f[0] and not f[1])
    polys = RG.polygons(traps) if traps else []
    if not polys:
        return list(outer)
    best = max(polys, key=lambda p: abs(_area2(p[0])))
    return ccw(best[0])


def cut_line(ev, fr, target, make) -> dict:
    """guides.cut_line: the sticker's cut polygon (mm, pattern frame).
    Marker: the sticker grown by its margin (`rect`), a corner cut when the
    mark is one; Profile: the target's outline with every hole."""
    if make.perimeter == "profile":
        loops = guides_target(ev, fr, target)
        return {"kind": "profile", "outer": loops[0] if loops else [],
                "holes": [list(h) for h in loops[1:]]}
    r = fr["tile_rect"] or tuple(_AL.sticker_rect(ev["spec"]))
    outer = rect_pts(r)
    mark = ev.get("mark")
    if mark is not None and mark.kind == "tile_cut" and mark.tool:
        outer = _minus(outer, mark.tool)
    return {"kind": "marker", "rect": [_r(v) for v in r], "outer": _pts(ccw(outer)), "holes": []}


def _label_of(label):
    """aruco_tags.label_of: a Label with something to build, or None."""
    if label is None or label.kind == "none" or not label.parts:
        return None
    return label


def combines(plan):
    """REF _combines, as data: where each part goes."""
    out = []
    for role in plan.parts:
        if role == "tile":
            out.append({"part": "tile", "op": "join" if plan.op == "join" else "new",
                        "into": "body" if plan.op == "join" else None})
        elif role == "pin":
            out.append({"part": "pin", "op": "join", "into": "tile"})
        elif role == "pocket":
            out.append({"part": "pocket", "op": "cut",
                        "into": "body" if plan.op == "join" else "tile"})
        elif role == "pattern":
            out.append({"part": "pattern", "op": "new", "into": None})
        elif role == "recess":
            out.append({"part": "recess", "op": "cut", "into": "body"})
        elif role == "trim":
            out.append({"part": "trim", "op": "intersect", "into": "body"})
    return out


# ---------------------------------------------------------------- frames

def pattern_frames(ev, target):
    """The pattern frame (face origin, turned axes) and the projections an
    adapter-free plan needs, from evaluate()'s cm frames in the base space."""
    from .evaluate import face_origin
    base = ev["base"]
    bo, bx, by, bz = base[0], base[1], base[2], base[3]
    fo = face_origin(ev)
    _o, x, y, z = ev["tag"]

    def P(p):                                   # base space cm -> pattern mm
        d = [p[i] - fo[i] for i in range(3)]
        return (_dot(d, x) * 10.0, _dot(d, y) * 10.0, _dot(d, z) * 10.0)

    def T(p):                                   # base space cm -> target mm
        d = [p[i] - bo[i] for i in range(3)]
        return (_dot(d, bx) * 10.0, _dot(d, by) * 10.0, _dot(d, bz) * 10.0)

    def Tv(v):
        return (_dot(v, bx), _dot(v, by), _dot(v, bz))
    tile_rect = None
    tile = ev.get("tile")
    if tile is not None:
        to, tx, ty, _tz, tw, th = tile
        cs = [[to[i] + tx[i] * a * tw / 2.0 + ty[i] * b * th / 2.0 for i in range(3)]
              for a in (-1.0, 1.0) for b in (-1.0, 1.0)]
        pr = [P(c) for c in cs]
        tile_rect = (min(p[0] for p in pr), min(p[1] for p in pr), max(p[0] for p in pr),
                     max(p[1] for p in pr))
    pin_centre = (0.0, 0.0)
    if ev.get("pin_frame") is not None:
        pc = P(ev["pin_frame"][0])
        pin_centre = (pc[0], pc[1])
    o_t = T(fo)
    xt, yt, zt = Tv(x), Tv(y), Tv(z)
    pattern_in_target = [xt[0], yt[0], zt[0], o_t[0], xt[1], yt[1], zt[1], o_t[1],
                         xt[2], yt[2], zt[2], o_t[2], 0.0, 0.0, 0.0, 1.0]
    return {"P": P, "T": T, "Tv": Tv, "fo": fo, "tile_rect": tile_rect,
            "pin_centre": pin_centre, "pattern_in_target": pattern_in_target}


def _mat(o, x, y, z):
    return [x[0], y[0], z[0], o[0], x[1], y[1], z[1], o[1], x[2], y[2], z[2], o[2],
            0.0, 0.0, 0.0, 1.0]


def frames_dict(ev, fr, optical_cm):
    """frames.opencv (pattern frame), frames.opencv_target and
    frames.pattern_in_target (target frame), all mm, row-major 4x4."""
    o, x, y, z = optical_cm
    P, Tv, T = fr["P"], fr["Tv"], fr["T"]
    fo = fr["fo"]
    _o, px, py, pz = ev["tag"]

    def Pv(v):
        return (_dot(v, px), _dot(v, py), _dot(v, pz))
    opencv = _mat(P(o), Pv(x), Pv(y), Pv(z))
    opencv_t = _mat(T(o), Tv(x), Tv(y), Tv(z))
    plan = ev["plan"]
    return {"opencv": [_r(v) for v in opencv], "opencv_target": [_r(v) for v in opencv_t],
            "pattern_in_target": [_r(v) for v in fr["pattern_in_target"]],
            "detector_z_mm": _r(plan.layers.detector), "surface_mm": _r(plan.layers.surface)}


# ---------------------------------------------------------------- guides

def guides(ev, fr, target, base):
    """The lines the 2D view draws and nothing prints (pattern frame mm)."""
    from ..core.geometry import _loops_mm
    spec = ev["spec"]
    lab = ev.get("label")
    rule = lab.settings.rule if lab is not None else _AL.RULE
    clear = _AL.clear_zones(spec, rule)
    keep = list(_AL.mark_keepouts(ev.get("mark")))
    if ev.get("pins"):
        keep += _AL.pin_keepouts(ev["pins"], centre=fr["pin_centre"])
    out = {"sticker": [_r(v) for v in _AL.sticker_rect(spec)],
           "quiet_ring": [_r(v) for v in _AL.keepout_rect(spec, 0.0)],
           "clear_hard": [_r(v) for v in clear["hard"]],
           "clear_preferred": [_r(v) for v in clear["preferred"]],
           "keepouts": [_pts(p) for p in keep],
           "label_preview": [], "tile": None, "target": [], "trim": None}
    if lab is not None and lab.kind == "none" and lab.preview is not None:
        out["label_preview"] = [_pts(b.corners()) for b in lab.preview.boxes()]
    if fr["tile_rect"] is not None:
        out["tile"] = [_r(v) for v in fr["tile_rect"]]
    out["target"] = guides_target(ev, fr, target)
    tp = ev.get("trim")
    if tp is not None:
        out["trim"] = {"outline": [_r(v) for v in tp.outline], "body": [_r(v) for v in tp.body],
                       "keep": [_r(v) for v in tp.column()],
                       "removed": [[_r(v) for v in r] for r in tp.regions()] if tp.cuts else []}
    return out


def guides_target(ev, fr, target):
    """The target's loops in the pattern frame (mm)."""
    from ..core.geometry import _loops_mm
    _o, x, y, _z = ev["tag"]
    return [_pts(lp) for lp in _loops_mm(target.loops_m(), ev["base"], fr["fo"], x, y)]
