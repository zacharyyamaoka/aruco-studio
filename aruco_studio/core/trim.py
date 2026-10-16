# Ported from REF CADExporter/bam_cad_core/aruco_trim.py at c8216ff:
# copied verbatim, only the package-relative imports renamed.
"""ArUco Extrude: Trim excess -- the pure model (stdlib only).

Zach, 2026-10-16: "please add feature to trim margins ... I like the idea
'trim X'. This is useful like if I put the charuco marker for example on
like a board ... perhaps if I set the width to be like a multiple of the 3d
printer nozzle, then so it's perfectly sized I may want to like trim excess
on the outside... which basically does like an extrude delete of the bodies
outside... It's something by default is off, but in the advanced settings
perhaps I can toggle it on." (docs/design_aruco_trim.md)

A tag sits centred on its face and, with its cells rounded to whole line
widths, usually leaves a margin around it. Trim excess cuts the body the tag
sits on (the target body: its face's body -- never another) back to the
tag's OUTLINE, through the whole body, in the trimmed directions:

    "x"     Width:  the tag's x (image right), both sides
    "y"     Height: the tag's y (image up / down), both sides
    "both"  all four sides

Everything here is in the PATTERN frame, mm: the origin is the pattern's
centre on the face plane, x / y the tag's own axes after the Origin turn --
the axes the ghost's triad shows (a board's OpenCV y points down: the same
line). Rect = (u0, v0, u1, v1).

The outline (`outline`): the white the tag owns -- the white tile (White +
black; a label strip grows it), else the sticker (the pattern + its quiet
zone: a single marker's white border, a grid board's outer quiet zone, a
ChArUco board's outer squares) -- and everything that sticks out of it: a
label's text blocks and strip, the locating pins, the corner mark (today
they all sit inside, so they never move it), then the margin all round.

What is kept (`keep_and_cut`): a column over the face, the outline on each
side that is trimmed and past the body everywhere else (through the whole
body along the face normal). A side whose excess is under TOL_MM is not
cut: no sliver, no face of the cut lying on a face of the body. The node
INTERSECTS the target body with that column (a combine), so "nothing to
trim" is the column containing the whole body: the same body, never an
empty result.

When it refuses (`plan_trim`; refusals in plain words; "Cut anyway"
overrides every one). Trimming a body that is not a plate under this face
could remove most of the part:

    the face is not a rectangle in the tag's axes   (a disc, an L, a turned
                                                     plate: it would change
                                                     the part's outline)
    a hole of the face is removed or cut through    (a mounting hole)
    the part loses much more than the face does     (a boss on a bigger
                                                     plate: the tag's face
                                                     is not the part's outer
                                                     extent)
    no face to measure, or the volumes could not be measured

The volume rule: the share of the part's volume the trim removes may exceed
the share of the FACE's area it removes by at most EXTRA_SHARE. A plate
under its face loses the same share of both (a fillet or a chamfer on its
edges changes little); a boss on a bigger plate loses the plate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

RULE = 1                    # settings "trim": {"rule": 1, ...}; another rule reads as off
AXES = ("x", "y", "both")
CHOICES = ("off",) + AXES
MARGIN_MAX_MM = 50.0
TOL_MM = 0.01               # an excess under this is not cut (no sliver, no coplanar cut)
REACH_NOTE_MM = 0.05        # the part reaching past the face by more than this is said
RECT_FILL = 0.98            # the face's outer loop fills its box at least this much
EXTRA_SHARE = 0.15          # the part may lose this much more (of 1) than the face does
PAD_MIN_MM = 10.0           # the kept column reaches this far past the body (at least)
SIDES = ("left", "right", "bottom", "top")       # -x, +x, -y, +y

Rect = Tuple[float, float, float, float]
Pt = Tuple[float, float]


# ----------------------------------------------------------------- settings

def trim_of(raw) -> Optional[dict]:
    """The stored setting as this code keeps it, or None (off): a missing
    key -- every tag made before Trim excess --, None, an unknown rule or
    axes, anything unreadable. {"rule", "axes", "margin_mm", "force"}."""
    if not isinstance(raw, dict):
        return None
    try:
        rule = int(raw.get("rule", RULE))
    except (TypeError, ValueError):
        return None
    if rule != RULE:
        return None
    axes = raw.get("axes")
    if axes not in AXES:
        return None
    try:
        margin = float(raw.get("margin_mm") or 0.0)
    except (TypeError, ValueError):
        margin = 0.0
    if not math.isfinite(margin):
        margin = 0.0
    margin = max(0.0, min(MARGIN_MAX_MM, margin))
    return {"rule": RULE, "axes": axes, "margin_mm": round(margin, 6),
            "force": bool(raw.get("force"))}


def setting(axes: str, margin_mm: float = 0.0, force: bool = False) -> Optional[dict]:
    """What a tag stores for the dialog's choice ("off": None)."""
    if axes not in AXES:
        return None
    return trim_of({"rule": RULE, "axes": axes, "margin_mm": margin_mm, "force": force})


def cut_axes(axes: str) -> Tuple[bool, bool]:
    """(trims along x, trims along y)."""
    return axes in ("x", "both"), axes in ("y", "both")


# -------------------------------------------------------------------- rects

def box_of(pts: Sequence[Pt]) -> Rect:
    us = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    return (min(us), min(vs), max(us), max(vs))


def union(rects: Sequence[Optional[Rect]]) -> Optional[Rect]:
    rs = [r for r in rects if r is not None]
    if not rs:
        return None
    return (min(r[0] for r in rs), min(r[1] for r in rs),
            max(r[2] for r in rs), max(r[3] for r in rs))


def grow(r: Rect, d: float) -> Rect:
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)


def inside(a: Rect, b: Rect, tol: float = 1e-6) -> bool:
    """Is rect a inside rect b?"""
    return (a[0] >= b[0] - tol and a[1] >= b[1] - tol
            and a[2] <= b[2] + tol and a[3] <= b[3] + tol)


def disjoint(a: Rect, b: Rect, tol: float = 1e-6) -> bool:
    return a[2] <= b[0] + tol or a[0] >= b[2] - tol or a[3] <= b[1] + tol or a[1] >= b[3] - tol


def outline(base: Rect, extras: Sequence[Optional[Rect]] = (), margin: float = 0.0) -> Rect:
    """The tag's extent: `base` (the white tile; else the sticker) with
    everything that sticks out of it (label blocks and strip, pins, the
    corner mark), grown by `margin` all round."""
    return grow(union([tuple(base)] + [tuple(e) for e in extras if e is not None]),
                max(0.0, float(margin)))


# ----------------------------------------------------------------- polygons

def area(poly: Sequence[Pt]) -> float:
    """Signed area (CCW +)."""
    n = len(poly)
    return 0.5 * sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(n))


def clip(poly: Sequence[Pt], r: Rect) -> List[Pt]:
    """Sutherland-Hodgman: the polygon clipped to the rectangle (any
    polygon, its winding kept)."""
    out = list(poly)
    for k, (axis, bound, keep_lo) in enumerate(((0, r[0], False), (0, r[2], True),
                                                (1, r[1], False), (1, r[3], True))):
        src, out = out, []
        if not src:
            break

        def ins(p):
            return p[axis] <= bound if keep_lo else p[axis] >= bound

        def cut(p, q):
            t = (bound - p[axis]) / (q[axis] - p[axis])
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
        for i in range(len(src)):
            p, q = src[i - 1], src[i]
            if ins(q):
                if not ins(p):
                    out.append(cut(p, q))
                out.append(q)
            elif ins(p):
                out.append(cut(p, q))
    return out


def split_loops(loops: Sequence[Sequence[Pt]]) -> Tuple[List[Pt], List[List[Pt]]]:
    """(outer loop, holes): the outer loop of a planar face is the one with
    the largest area (a face's loops come in any order)."""
    lps = [list(lp) for lp in loops if lp and len(lp) >= 3]
    if not lps:
        return [], []
    i = max(range(len(lps)), key=lambda k: abs(area(lps[k])))
    return lps[i], [lp for k, lp in enumerate(lps) if k != i]


def face_area(outer: Sequence[Pt], holes: Sequence[Sequence[Pt]]) -> float:
    return abs(area(outer)) - sum(abs(area(h)) for h in holes)


def kept_area(outer: Sequence[Pt], holes: Sequence[Sequence[Pt]], r: Rect) -> float:
    a = abs(area(clip(outer, r)))
    for h in holes:
        a -= abs(area(clip(h, r)))
    return max(0.0, a)


# ---------------------------------------------------------------- the plan

def pad_for(body: Rect, z: Optional[Tuple[float, float]] = None) -> float:
    """How far past the body the kept column reaches (mm): the body's
    diagonal, PAD_MIN_MM at least."""
    du, dv = body[2] - body[0], body[3] - body[1]
    dz = (z[1] - z[0]) if z else 0.0
    return max(PAD_MIN_MM, math.sqrt(du * du + dv * dv + dz * dz))


def keep_and_cut(axes: str, out: Rect, body: Rect, pad: Optional[float] = None
                 ) -> Tuple[Rect, Dict[str, float]]:
    """(the kept column (u, v), {side: mm cut past the outline}). A side is
    cut when the body reaches past the outline there by more than TOL_MM;
    every other side of the column lies `pad` past the body."""
    pad = pad_for(body) if pad is None else pad
    tx, ty = cut_axes(axes)
    k = [body[0] - pad, body[1] - pad, body[2] + pad, body[3] + pad]
    cut = {}
    for side, axis_on, i_out, i_body, sign in (("left", tx, 0, 0, -1), ("right", tx, 2, 2, 1),
                                               ("bottom", ty, 1, 1, -1), ("top", ty, 3, 3, 1)):
        if not axis_on:
            continue
        excess = (body[i_body] - out[i_out]) * sign
        if excess > TOL_MM:
            k[i_out] = out[i_out]
            cut[side] = excess
    return (k[0], k[1], k[2], k[3]), cut


def noop_keep(body: Rect, pad: Optional[float] = None) -> Rect:
    """A column that keeps the whole body (the node when it may not cut)."""
    pad = pad_for(body) if pad is None else pad
    return grow(body, pad)


@dataclass
class TrimPlan:
    """What Trim excess does on one tag (mm, pattern frame).

    axes      "x" / "y" / "both"
    outline   the tag's extent, the margin included
    body      the target body's extent along the tag's x / y
    z         the column's range along the face normal (the body and the
              tag's slabs; set by the caller), or None
    keep      the kept column (u, v): the outline on each cut side, `pad`
              past the body elsewhere
    cut       {side: mm cut off past the outline} -- only the sides cut
    refusals  why it may not cut (plain words); "Cut anyway" (force) cuts
    notes     what to know besides (plain words)
    face_share, body_share  the share of the face's area / the part's
              volume the trim removes (None: not measured)
    removed_mm3, body_mm3   the volumes (None: not measured)
    holes     (removed, cut through) holes of the face
    """
    axes: str
    margin: float
    outline: Rect
    body: Rect
    keep: Rect
    pad: float
    cut: Dict[str, float] = field(default_factory=dict)
    refusals: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    forced: bool = False
    face: Optional[Rect] = None
    face_share: Optional[float] = None
    body_share: Optional[float] = None
    removed_mm3: Optional[float] = None
    body_mm3: Optional[float] = None
    holes: Tuple[int, int] = (0, 0)
    z: Optional[Tuple[float, float]] = None

    @property
    def active(self) -> bool:
        """Is there anything to trim?"""
        return bool(self.cut)

    @property
    def refused(self) -> bool:
        """Refused and not forced: the node keeps the body whole."""
        return bool(self.refusals) and not self.forced

    @property
    def cuts(self) -> bool:
        """Does the node cut?"""
        return self.active and not self.refused

    def column(self) -> Rect:
        """The column the node keeps: `keep` when it cuts, else the whole
        body (and more)."""
        return self.keep if self.cuts else noop_keep(self.body, self.pad)

    def regions(self) -> List[Rect]:
        """The removed area as rects within the body's extent (the ghost
        when the exact volume cannot be drawn): the left / right strips the
        whole height of the body, then the bottom / top strips between."""
        b, k = self.body, self.keep
        out = []
        if "left" in self.cut:
            out.append((b[0], b[1], k[0], b[3]))
        if "right" in self.cut:
            out.append((k[2], b[1], b[2], b[3]))
        u0, u1 = max(b[0], k[0]), min(b[2], k[2])
        if "bottom" in self.cut and u1 > u0:
            out.append((u0, b[1], u1, k[1]))
        if "top" in self.cut and u1 > u0:
            out.append((u0, k[3], u1, b[3]))
        return out

    def size_after(self) -> Tuple[float, float]:
        """The body's width x height (tag axes) after the trim."""
        b, k = self.body, self.column()
        return (min(b[2], k[2]) - max(b[0], k[0]), min(b[3], k[3]) - max(b[1], k[1]))


def plan_trim(axes: str, out: Rect, body: Rect, face_loops=None, *, margin: float = 0.0,
              force: bool = False, volumes: Optional[Tuple[float, float]] = None,
              z: Optional[Tuple[float, float]] = None, need_face: bool = True) -> TrimPlan:
    """Trim excess on one tag.

    axes        "x" / "y" / "both"
    out         the outline (`outline`: the margin already in it)
    body        the target body's extent (u0, v0, u1, v1)
    face_loops  the face's loops (outer and holes, any order) in the same
                frame, or None when there is no face to measure
    volumes     (the body's volume, the volume the column removes) mm3, or
                None when they could not be measured
    z           the column's z range, kept on the plan
    need_face   False: a missing face is no reason to refuse (tests)
    """
    pad = pad_for(body, z)
    keep, cut = keep_and_cut(axes, out, body, pad)
    p = TrimPlan(axes=axes, margin=float(margin), outline=tuple(out), body=tuple(body),
                 keep=keep, pad=pad, cut=cut, forced=bool(force), z=z)
    words = {"x": "width", "y": "height", "both": "width and height"}[axes]
    if not cut:
        p.notes.append(f"nothing to trim ({words}): the tag already reaches the part's edges")
        if volumes is not None:
            p.body_mm3, p.removed_mm3 = float(volumes[0]), 0.0
            p.body_share = p.face_share = 0.0
        return p
    if face_loops is None:
        if need_face:
            p.refusals.append("there is no face under the tag to measure: the excess "
                              "cannot be told from the part")
    else:
        outer, holes = split_loops(face_loops)
        if outer:
            fb = box_of(outer)
            p.face = fb
            box = (fb[2] - fb[0]) * (fb[3] - fb[1])
            fill = abs(area(outer)) / box if box > 0 else 0.0
            if fill < RECT_FILL:
                p.refusals.append(f"the face is not a rectangle in the tag's axes (it fills "
                                  f"{fill * 100.0:.0f} % of its box: a disc, an L, a turned "
                                  "plate?): trimming would change its outline")
            gone = through = 0
            for h in holes:
                hb = box_of(h)
                if inside(hb, keep, 1e-3):
                    continue
                if disjoint(hb, keep, 1e-3):
                    gone += 1
                else:
                    through += 1
            p.holes = (gone, through)
            if gone or through:
                bits = []
                if gone:
                    bits.append(f"removes {gone} hole{'s' if gone > 1 else ''}")
                if through:
                    bits.append(f"cuts through {through} hole{'s' if through > 1 else ''}")
                p.refusals.append("the trim " + " and ".join(bits) + " of the face")
            fa = face_area(outer, holes)
            if fa > 0:
                p.face_share = max(0.0, min(1.0, 1.0 - kept_area(outer, holes, keep) / fa))
            # the part reaching past the face on a cut side goes with the
            # excess (a fillet, a chamfer): said, the volume rule judges
            reach = {"left": fb[0] - body[0], "right": body[2] - fb[2],
                     "bottom": fb[1] - body[1], "top": body[3] - fb[3]}
            far = [(s, reach[s]) for s in SIDES if s in cut and reach[s] > REACH_NOTE_MM]
            if far:
                p.notes.append("the part reaches past the face " + ", ".join(
                    f"{d:.1f} mm {s}" for s, d in far) + ": trimmed with the excess")
        elif need_face:
            p.refusals.append("the face has no outline to measure")
    if volumes is None:
        p.refusals.append("what the trim removes could not be measured")
    else:
        vb, vr = float(volumes[0]), float(volumes[1])
        p.body_mm3, p.removed_mm3 = vb, vr
        if vb > 0:
            p.body_share = max(0.0, min(1.0, vr / vb))
        if p.body_share is not None and p.face_share is not None \
                and p.body_share - p.face_share > EXTRA_SHARE:
            p.refusals.append(f"the trim takes {p.body_share * 100.0:.0f} % of the part but "
                              f"{p.face_share * 100.0:.0f} % of the face: the part reaches "
                              "beyond this face (a boss on a bigger part?)")
    return p


def failed(axes: str, body: Optional[Rect], why: str, force: bool = False) -> TrimPlan:
    """A plan that could not be made (the body or the face could not be
    read): it refuses (Cut anyway cannot cut what is not known: the column
    keeps everything either way)."""
    b = tuple(body) if body is not None else (-1e4, -1e4, 1e4, 1e4)
    pad = pad_for(b)
    return TrimPlan(axes=axes, margin=0.0, outline=b, body=b, keep=noop_keep(b, pad), pad=pad,
                    refusals=[why], forced=False)


# ------------------------------------------------------------------ words

def _mm(v: float) -> str:
    t = f"{v:.2f}"
    t = t.rstrip("0").rstrip(".") if "." in t else t
    return t if "." in t else t + ".0"


def _pair(cut: Dict[str, float], a: str, b: str) -> Optional[str]:
    if a in cut and b in cut:
        if abs(cut[a] - cut[b]) < 0.05:
            return f"{_mm(cut[a])} mm off each side"
        return f"{_mm(cut[a])} mm {a}, {_mm(cut[b])} mm {b}"
    if a in cut:
        return f"{_mm(cut[a])} mm {a}"
    if b in cut:
        return f"{_mm(cut[b])} mm {b}"
    return None


def summary(p: TrimPlan, body_name: str = "the part") -> str:
    """One line for the dialog: "trims 6.2 mm off each side (width): plate
    50.0 → 37.6 mm wide" -- what it cuts (or would cut, when refused)."""
    if not p.active:
        return p.notes[0] if p.notes else "nothing to trim"
    w0, h0 = p.body[2] - p.body[0], p.body[3] - p.body[1]
    k = p.keep
    w1 = min(p.body[2], k[2]) - max(p.body[0], k[0])
    h1 = min(p.body[3], k[3]) - max(p.body[1], k[1])
    x = _pair(p.cut, "left", "right")
    y = _pair(p.cut, "bottom", "top")
    if x and y:
        what = (f"{x} (width), {y} (height)" if x != y or "each" not in x
                else f"{x} (width and height)")
        size = f"{_mm(w0)} × {_mm(h0)} → {_mm(w1)} × {_mm(h1)} mm"
    elif x:
        what, size = f"{x} (width)", f"{_mm(w0)} → {_mm(w1)} mm wide"
    else:
        what, size = f"{y} (height)", f"{_mm(h0)} → {_mm(h1)} mm high"
    text = f"trims {what}: {body_name} {size}"
    if p.removed_mm3 is not None:
        text += f"; removes {p.removed_mm3 / 1000.0:.2f} cm³"
        if p.body_share is not None:
            text += f" ({p.body_share * 100.0:.0f} % of it)"
    return text
