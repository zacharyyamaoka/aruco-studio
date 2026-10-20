"""The marker rectangle is the whole sticker (the online Studio, Zach,
2026-10-18): "the outer rectangle allows us to efficiently define the
outbounds and then the feature will take care of populating everything
inside of it". Pure, standard library only: the web facade (web_api.plan,
in Pyodide) and the Fusion adapter fill a rectangle the same way.

Frame: the rectangle's own, mm -- origin its centre, u along its width, v
along its height (before the sketch's angle; the caller places it).

    label off   the marker fills the whole w x h (as before)
    label on    a band on `side` holds the text: its depth is the text block
                (lines x cap + the line gaps) across the band, the rectangle's
                whole width / height along it; `gap_mm` separates it from
                the box the marker fills (`Fill.box`); the band also holds
                EDGE x cap of white from the cut line and, for sans,
                DESCENT x cap below the last baseline; the text's preset
                spot is the text block's centre, `offset` moves it from there
    font        "sans" (inkjet: ordinary text the page prints, `Fill.runs`)
                or "pixel" (3D print: core.label's pixel font of 2026-10-10,
                its ink as boxes, `Fill.ink`; one pixel = a whole number of
                the preset's lines on Auto size)
    on_marker   (`on_marker`, Zach 2026-10-20) the marker fills the whole
                rectangle and the text sits ON it, on `side`: on the black
                (knocked out white) or on the white (black text). It reuses
                core.label's rules: a single's / grid's text in a marker's
                border row (_row_rect: a quarter module of black above and
                below, clear of the corner cells; cap 0.5 module, BLACK_CAP);
                a ChArUco board's in a black chessboard square of the edge
                row (label rule 3's charuco_black_squares, the square rule's
                edge and corner keep-outs); on the white, in the quiet zone
                (the white square's own, on a ChArUco board). Left reads
                upward, right downward (core.label.SIDE_ROT). Nothing is
                refused: what breaks a rule is drawn and flagged.

`dimensions` gives the dimensions the canvas draws, each between two points
of the drawn geometry; `square_origin` moves a ChArUco board's Joint Origin
to the centre of one of its squares.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from . import label as _AL
from . import sheet as _SH

Pt = Tuple[float, float]
Rect = Tuple[float, float, float, float]          # (u0, v0, u1, v1), mm

SIDES = ("below", "above", "left", "right")
FONTS = ("sans", "pixel")
PLACES = ("on_marker", "outside")
SURFACES = ("black", "white")
# fill()'s own Auto cap when the caller drives none (the web drives it: one
# module, Zach 2026-10-20: "right now it's way too big")
LABEL_CAP = (0.12, 2.5, 12.0)       # Auto cap: 0.12 x the short side, within 2.5 .. 12 mm
LINE_GAP = _AL.LINE_GAP_PX / _AL.GLYPH_ROWS     # between lines, x the cap (the pixel font's 2 px of 5)
# WHY a margin and descender room (2026-10-18): the band started at the cut
# line, so a sans label's baseline sat ON it and "part" lost its "p" to the
# knife. The text keeps EDGE x cap of white from the rectangle's edge, and a
# sans label keeps DESCENT x cap below its last baseline (Helvetica's
# descender, 0.207 em, is 0.29 of its 0.718 em cap). The pixel font has none.
EDGE = LINE_GAP
DESCENT = 0.3
MIN_BOX_MM = 0.1                    # the marker's box never goes below this (a refusal plans)
DIM_STEP = (0.1, 2.0, 8.0)          # dimension rings: 0.1 x the short side, within 2 .. 8 mm
TOL = 1e-6


def lines_of(text: str) -> List[str]:
    """A label's lines: its text split on "\\n"."""
    return str(text or "").replace("\r\n", "\n").split("\n")


def auto_cap(w: float, h: float) -> float:
    k, lo, hi = LABEL_CAP
    return min(hi, max(lo, k * min(w, h)))


def pixel_cap(cap: float, line_mm: float) -> float:
    """The largest cap <= `cap` whose pixel (cap / GLYPH_ROWS) is a whole
    number of lines, one line at least: every stroke and gap then prints as
    whole beads."""
    unit = _AL.GLYPH_ROWS * float(line_mm)
    return max(1, int(math.floor(float(cap) / unit + 1e-9))) * unit


def sans_width(text: str, cap: float) -> float:
    """A line's width (mm) in Helvetica at a cap height (core.sheet's metrics,
    the font the page prints the label in)."""
    return _SH.text_width_mm(text, cap / _SH.CAP_EM * _SH.MM_TO_PT)


@dataclass(frozen=True)
class Run:
    """One line of sans text: `at` its cap box's centre (baseline at
    at[1] - cap / 2), centred on it."""
    text: str
    at: Pt
    cap: float


@dataclass
class Fill:
    w: float
    h: float
    side: str
    font: str
    lines: List[str]                 # as given (split on "\n")
    drawn: List[str]                 # as the font draws them (pixel: upper-case, "?")
    cap: float
    stroke: float                    # pixel: one pixel; sans: 0
    band: Rect                       # the label's band
    box: Rect                        # what the marker fills
    spot: Pt                         # the preset spot: the text block's centre in the band
    at: Pt                           # the text block's centre (spot + offset)
    block: Tuple[float, float]       # the text block's width, height
    runs: List[Run] = field(default_factory=list)     # sans
    ink: List[Rect] = field(default_factory=list)     # pixel
    issues: List[Tuple[str, str, str]] = field(default_factory=list)   # (field, level, text)
    place: str = "outside"           # PLACES
    surface: str = ""                # on_marker: "black" (knocked out) / "white"
    rot: int = 0                     # the text's turn: 0, 90 (reads upward), -90 (downward)

    @property
    def knockout(self) -> bool:
        """The text is white paper cut out of the black (no ink there)."""
        return self.place == "on_marker" and self.surface == "black"

    @property
    def box_size(self) -> Tuple[float, float]:
        return self.box[2] - self.box[0], self.box[3] - self.box[1]

    @property
    def box_centre(self) -> Pt:
        return (self.box[0] + self.box[2]) / 2.0, (self.box[1] + self.box[3]) / 2.0


def fill(w: float, h: float, text: str, *, font: str = "sans", cap_mm: float = 0.0,
         side: str = "below", gap_mm: float = 0.0, offset: Pt = (0.0, 0.0),
         line_mm: float = 0.0, band_cap_mm: float = 0.0, driven: bool = False) -> Fill:
    """Reserve the label's band inside a w x h rectangle; the marker gets the
    rest. `cap_mm` 0 = Auto (LABEL_CAP; "pixel" rounds it down to whole
    lines of `line_mm`). `driven`: `cap_mm` is the caller's driven cap (one
    module), not a typed one: "pixel" rounds it as Auto's. `band_cap_mm`: the
    band is as deep as text of this cap needs when that is deeper (a driven
    cap's search reserves the band it settled on). A typed `gap_mm` is kept
    as typed, below 0 too (the band then overlaps the marker's box, said).
    Nothing is refused: a label too wide is flagged, a label that leaves no
    room flags an error and leaves MIN_BOX_MM."""
    w, h = float(w), float(h)
    issues: List[Tuple[str, str, str]] = []
    if side not in SIDES:
        issues.append(("label.side", "warn", f"side {side!r} is not one of {', '.join(SIDES)}: below"))
        side = "below"
    font = font if font in FONTS else "sans"
    lines = lines_of(text)
    typed = float(cap_mm or 0.0) > 0 and not driven
    cap = float(cap_mm) if float(cap_mm or 0.0) > 0 else auto_cap(w, h)
    stroke = 0.0
    if font == "pixel":
        line = float(line_mm) if line_mm and line_mm > 0 else _AL.NOZZLE_MM
        if not typed:
            cap = pixel_cap(cap, line)
        stroke = cap / _AL.GLYPH_ROWS
        if stroke < line - TOL:
            issues.append(("label.height_mm", "warn",
                           f"the 3D font's strokes are {stroke:.2f} mm, thinner than the "
                           f"{line:g} mm line: a {_AL.GLYPH_ROWS * line:.2f} mm cap or more prints"))
        drawn, missing = [], []
        for t in lines:
            d, miss = _AL.normalize(t)
            drawn.append(d)
            missing += [c for c in miss if c not in missing]
        if missing:
            issues.append(("label.text", "info",
                           f"the 3D font has no {' '.join(missing)}: printed as {_AL.UNKNOWN}"))
        M = _AL.Metrics(cap, stroke)
        bw, bh = _AL.block_size(drawn, M)
    else:
        drawn = list(lines)
        bw = max(sans_width(t, cap) for t in lines)
        bh = len(lines) * cap + (len(lines) - 1) * LINE_GAP * cap
    # WHY as typed, below 0 too (Zach, 2026-10-20: "we should always have
    # complete control"): it was clamped to 0 without a word
    gap = float(gap_mm or 0.0)
    if gap < 0:
        issues.append(("label.gap_mm", "warn",
                       f"a gap of {gap:g} mm: the label's band overlaps the marker's box by "
                       f"{-gap:g} mm"))
    pad = EDGE * cap                                # white between the text and the cut line
    desc = DESCENT * cap if font == "sans" else 0.0  # below the last baseline
    x0, y0, x1, y1 = -w / 2.0, -h / 2.0, w / 2.0, h / 2.0
    deep, wide = bh + desc + pad, bw + pad          # the band across the rectangle's side
    if band_cap_mm and band_cap_mm > cap:            # every term is in proportion to the cap
        deep, wide = deep * band_cap_mm / cap, wide * band_cap_mm / cap
    if side == "below":
        band, box = (x0, y0, x1, y0 + deep), (x0, y0 + deep + gap, x1, y1)
        mid = (0.0, y0 + pad + desc + bh / 2.0)
    elif side == "above":
        band, box = (x0, y1 - deep, x1, y1), (x0, y0, x1, y1 - deep - gap)
        mid = (0.0, y1 - pad - bh / 2.0)
    elif side == "left":
        band, box = (x0, y0, x0 + wide, y1), (x0 + wide + gap, y0, x1, y1)
        mid = (x0 + pad + bw / 2.0, desc / 2.0)
    else:
        band, box = (x1 - wide, y0, x1, y1), (x0, y0, x1 - wide - gap, y1)
        mid = (x1 - pad - bw / 2.0, desc / 2.0)
    along, room, word = (bw, w, "wider") if side in ("below", "above") else (bh, h, "taller")
    if along > room + TOL:
        issues.append(("label.text", "warn",
                       f"the label is {along - room:.1f} mm {word} than the rectangle"))
    if box[2] - box[0] < MIN_BOX_MM or box[3] - box[1] < MIN_BOX_MM:
        issues.append(("label.height_mm", "error",
                       f"the label and its gap leave no room for the marker in the {w:g} × {h:g} mm "
                       "rectangle (a smaller label or gap, or a bigger rectangle)"))
        box = {"below": (x0, y1 - MIN_BOX_MM, x1, y1), "above": (x0, y0, x1, y0 + MIN_BOX_MM),
               "left": (x1 - MIN_BOX_MM, y0, x1, y1), "right": (x0, y0, x0 + MIN_BOX_MM, y1)}[side]
    spot = mid                                      # the text block's centre, inside the band
    off = offset or (0.0, 0.0)
    at = (spot[0] + float(off[0]), spot[1] + float(off[1]))
    runs: List[Run] = []
    ink: List[Rect] = []
    if font == "pixel":
        ink = [b.bounds() for b in _AL.block_boxes(drawn, _AL.Metrics(cap, stroke), centre=at)]
    else:
        top = at[1] + bh / 2.0
        for k, t in enumerate(lines):
            runs.append(Run(t, (at[0], top - cap / 2.0 - k * (1.0 + LINE_GAP) * cap), cap))
    return Fill(w=w, h=h, side=side, font=font, lines=lines, drawn=drawn, cap=cap, stroke=stroke,
                band=band, box=box, spot=spot, at=at, block=(bw, bh), runs=runs, ink=ink,
                issues=issues)


# ------------------------------------------------------------------ on the marker

ROT = {"below": 0, "above": 0, "left": 90, "right": -90}    # core.label.SIDE_ROT


@dataclass(frozen=True)
class Geo:
    """The marker as drawn, in the rectangle's frame (mm): what a label ON it
    is fitted to. `markers` each marker's black square; ChArUco: `squares`
    the black chessboard squares, `square_mm` their side, `corners` the
    inner chessboard corners; `outline` the quiet-zone edge (the sticker)."""
    kind: str
    module: float
    outline: Rect
    markers: Tuple[Rect, ...]
    squares: Tuple[Rect, ...] = ()
    square_mm: float = 0.0
    corners: Tuple[Pt, ...] = ()


def _t(r):
    """A rect (or point) with u and v swapped."""
    return (r[1], r[0], r[3], r[2]) if len(r) == 4 else (r[1], r[0])


def border_row(sq: Rect, m: float, side: str) -> Tuple[Rect, Rect]:
    """(the text's band, the row's black) in a marker's border row on `side`:
    core.label's _row_rect (BLACK_EDGE of black each side of the text,
    CORNER_CLEAR beyond the corner cells), left and right by symmetry."""
    if side in ("below", "above"):
        return _AL._row_rect(sq, m, "bottom" if side == "below" else "top")
    band, bound = _AL._row_rect(_t(sq), m, "bottom" if side == "left" else "top")
    return _t(band), _t(bound)


def _strip(outer: Rect, black: Rect, side: str) -> Rect:
    """The white between `black` and `outer`'s edge on `side`, as long as `black`."""
    x0, y0, x1, y1 = black
    return {"below": (x0, outer[1], x1, y0), "above": (x0, y1, x1, outer[3]),
            "left": (outer[0], y0, x0, y1), "right": (x1, y0, outer[2], y1)}[side]


def _edge_one(rects: Sequence[Rect], side: str, centre: Pt) -> Optional[Rect]:
    """Of the rects on the outermost row on `side`, the one nearest `centre`
    along that side (equally near: the lower / the left one)."""
    if not rects:
        return None
    k = {"below": 1, "above": 3, "left": 0, "right": 2}[side]
    edge = (min if side in ("below", "left") else max)(r[k] for r in rects)
    row = [r for r in rects if abs(r[k] - edge) < TOL]
    a = 0 if side in ("below", "above") else 1
    return min(row, key=lambda r: (round(abs((r[a] + r[a + 2]) / 2.0 - centre[a]), 6), r[a]))


def _across(r: Rect, side: str) -> float:
    return (r[3] - r[1]) if side in ("below", "above") else (r[2] - r[0])


def _shrunk(r: Rect, side: str, d: float) -> Rect:
    """`r` less d on both edges across `side`."""
    if side in ("below", "above"):
        return (r[0], r[1] + d, r[2], r[3] - d)
    return (r[0] + d, r[1], r[2] - d, r[3])


def _rect_pt(r: Rect, p: Pt) -> float:
    dx = max(r[0] - p[0], 0.0, p[0] - r[2])
    dy = max(r[1] - p[1], 0.0, p[1] - r[3])
    return math.hypot(dx, dy)


def on_marker(w: float, h: float, text: str, geo: Geo, *, font: str = "sans",
              cap_mm: float = 0.0, side: str = "below", surface: str = "black",
              offset: Pt = (0.0, 0.0), line_mm: float = 0.0) -> Fill:
    """The label ON the marker (Zach, 2026-10-20: "the text should be sized
    for the grid/single marker to be the height of a single cell, so that it
    would fit inside that black cell row"). The marker keeps the whole w x h
    (`Fill.box`); `Fill.band` is where the text goes, its centre the preset
    spot, `offset` moves it from there:

        black  single / grid: the border row on `side` of the marker on the
               board's edge nearest its middle (core.label._row_rect); the
               cap BLACK_CAP x module (the 1-module row less BLACK_EDGE of
               black above and below: core.label's rule, measured to cost
               the detector nothing). ChArUco: the black chessboard square of
               the edge row nearest its middle (label rule 3's squares),
               inside the square rule's edge (SQUARE_EDGE x square, at least
               a module); the cap one module (under SQUARE_CAP x square)
        white  the quiet zone on `side` (a ChArUco board has none outside:
               the edge row's white square, between its marker and the
               board's edge); the cap that white's depth less BLACK_EDGE
               module each side

    The text is knocked out of the black (white) or black on the white.
    `cap_mm` > 0 is used as typed. Nothing is refused: a cap over the rule,
    a text longer or taller than its place, the white rule (ink in the
    quiet ring costs the detector: core.label) are drawn and flagged."""
    w, h = float(w), float(h)
    issues: List[Tuple[str, str, str]] = []
    if side not in SIDES:
        issues.append(("label.side", "warn", f"side {side!r} is not one of {', '.join(SIDES)}: below"))
        side = "below"
    if surface not in SURFACES:
        issues.append(("label.surface", "warn",
                       f"surface {surface!r} is not black or white: black"))
        surface = "black"
    font = font if font in FONTS else "sans"
    m = float(geo.module)
    o = geo.outline
    centre = ((o[0] + o[2]) / 2.0, (o[1] + o[3]) / 2.0)
    rot = ROT[side]
    where = "border row"
    if geo.kind == "charuco":
        S = float(geo.square_mm)
        if surface == "black":
            sq = _edge_one(geo.squares, side, centre) or o
            e = max(_AL.SQUARE_EDGE * S, m)
            band = (sq[0] + e, sq[1] + e, sq[2] - e, sq[3] - e)
            rule_cap, where = m, "black square"
            limit = _AL.SQUARE_CAP * S
        else:
            whites = [((a[0] + a[2] - S) / 2.0, (a[1] + a[3] - S) / 2.0,
                       (a[0] + a[2] + S) / 2.0, (a[1] + a[3] + S) / 2.0) for a in geo.markers]
            wsq = _edge_one(whites, side, centre)
            if wsq is None:
                strip = _strip(o, o, side)
            else:
                mk = min(geo.markers, key=lambda a: abs(a[0] + a[2] - wsq[0] - wsq[2])
                         + abs(a[1] + a[3] - wsq[1] - wsq[3]))
                strip = _strip(wsq, mk, side)
            where = "white square's margin"
    else:
        if surface == "black":
            sq = _edge_one(geo.markers, side, centre) or o
            band, _bound = border_row(sq, m, side)
            rule_cap = limit = _AL.BLACK_CAP * m
        else:
            ext = (min(r[0] for r in geo.markers), min(r[1] for r in geo.markers),
                   max(r[2] for r in geo.markers), max(r[3] for r in geo.markers))
            strip = _strip(o, ext, side)
            where = "quiet zone"
    if surface == "white":
        depth = max(0.0, _across(strip, side))
        band = _shrunk(strip, side, min(_AL.BLACK_EDGE * m, depth / 4.0))
        rule_cap = limit = _across(band, side)
        if rule_cap <= TOL:
            issues.append(("label.surface", "warn",
                           f"no white on that side to hold the text (a quiet zone of "
                           f"{depth:.2f} mm): it is drawn half a module tall over the edge"))
            rule_cap = limit = _AL.BLACK_CAP * m
        issues.append(("label.surface", "warn",
                       "black text in the quiet zone: any ink in the white ring round the "
                       "black costs the detector (core.label's study: about 11 points of "
                       "reads for a grey id, up to 40 once the dots spread)"))
    typed = float(cap_mm or 0.0) > 0
    cap = float(cap_mm) if typed else rule_cap
    lines = lines_of(text)
    stroke = 0.0
    if font == "pixel":
        line = float(line_mm) if line_mm and line_mm > 0 else _AL.NOZZLE_MM
        # WHY a driven cap never outgrows its place (2026-10-20): whole lines
        # when one fits, else the place's own cap, thin strokes said -- a
        # 5-line letter rounded up over a 1-module row covered the bits and
        # OpenCV lost the marker
        if not typed and pixel_cap(cap, line) <= cap + TOL:
            cap = pixel_cap(cap, line)
        stroke = cap / _AL.GLYPH_ROWS
        if stroke < line - TOL:
            issues.append(("label.height_mm", "warn",
                           f"the 3D font's strokes are {stroke:.2f} mm, thinner than the "
                           f"{line:g} mm line: a {_AL.GLYPH_ROWS * line:.2f} mm cap or more prints"))
        elif surface == "black" and stroke < _AL.LINE_STROKE * line - TOL:
            issues.append(("label.height_mm", "warn",
                           f"letters cut out of the black need strokes of {_AL.LINE_STROKE:g} "
                           f"lines ({_AL.LINE_STROKE * line:.2f} mm) or the black beads close "
                           f"them (label rule 5); these are {stroke:.2f} mm"))
        drawn, missing = [], []
        for t in lines:
            d, miss = _AL.normalize(t)
            drawn.append(d)
            missing += [c for c in miss if c not in missing]
        if missing:
            issues.append(("label.text", "info",
                           f"the 3D font has no {' '.join(missing)}: printed as {_AL.UNKNOWN}"))
        bw, bh = _AL.block_size(drawn, _AL.Metrics(cap, stroke))
    else:
        drawn = list(lines)
        bw = max(sans_width(t, cap) for t in lines)
        bh = len(lines) * cap + (len(lines) - 1) * LINE_GAP * cap
    if cap > limit + TOL and surface == "black":
        why = ("a border row keeps a quarter module of black above and below its text"
               if geo.kind != "charuco" else
               f"a chessboard square's text stays under {_AL.SQUARE_CAP:g} of the square")
        issues.append(("label.height_mm", "warn",
                       f"{cap:.2f} mm letters are over the {limit:.2f} mm the {where} holds "
                       f"({why}, or the detector may miss it)"))
    along, room = bw, (band[2] - band[0]) if rot == 0 else (band[3] - band[1])
    if along > room + TOL:
        issues.append(("label.text", "warn",
                       f"the label is {along - room:.1f} mm longer than the {where} holds"))
    deep = _across(band, side)
    if bh > deep + TOL:
        n = len(lines)
        issues.append(("label.text", "warn",
                       f"the label's {n} line{'s' if n > 1 else ''} stand {bh:.2f} mm, the "
                       f"{where} holds {max(0.0, deep):.2f} mm: the text runs out of it"))
    spot = ((band[0] + band[2]) / 2.0, (band[1] + band[3]) / 2.0)
    off = offset or (0.0, 0.0)
    at = (spot[0] + float(off[0]), spot[1] + float(off[1]))
    fw, fh = (bw, bh) if rot == 0 else (bh, bw)
    tbox = (at[0] - fw / 2.0, at[1] - fh / 2.0, at[0] + fw / 2.0, at[1] + fh / 2.0)
    if geo.kind == "charuco" and surface == "black" and geo.corners:
        near = min(_rect_pt(tbox, p) for p in geo.corners)
        if near < _AL.SQUARE_CORNER_HARD * geo.square_mm - TOL:
            issues.append(("label.text", "warn",
                           f"the label comes within {near:.2f} mm of a chessboard corner (the "
                           f"detector refines them: keep {_AL.SQUARE_CORNER_HARD:g} square, "
                           f"{_AL.SQUARE_CORNER_HARD * geo.square_mm:.2f} mm, clear)"))
    runs: List[Run] = []
    ink: List[Rect] = []
    if font == "pixel":
        ink = [b.bounds() for b in _AL.block_boxes(drawn, _AL.Metrics(cap, stroke), centre=at,
                                                    rot=rot)]
    else:
        r = math.radians(rot)
        c, s = round(math.cos(r), 12), round(math.sin(r), 12)
        for k in range(len(lines)):
            dy = bh / 2.0 - cap / 2.0 - k * (1.0 + LINE_GAP) * cap
            runs.append(Run(lines[k], (at[0] - s * dy, at[1] + c * dy), cap))
    return Fill(w=w, h=h, side=side, font=font, lines=lines, drawn=drawn, cap=cap, stroke=stroke,
                band=band, box=(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0), spot=spot, at=at,
                block=(bw, bh), runs=runs, ink=ink, issues=issues, place="on_marker",
                surface=surface, rot=rot)


# ------------------------------------------------------------------ dimensions

def dim_step(w: float, h: float) -> float:
    k, lo, hi = DIM_STEP
    return min(hi, max(lo, k * min(w, h)))


def _top_left(rects: Sequence[Rect]) -> Optional[Rect]:
    """The top row's leftmost."""
    if not rects:
        return None
    return min(rects, key=lambda r: (-round(r[3], 6), round(r[0], 6)))


def _neighbour(r: Rect, rects: Sequence[Rect]):
    """(the next rect right of r in its row, "u") or (the next one below r in
    its column, "v") or (None, None)."""
    right = [q for q in rects if abs(q[3] - r[3]) < TOL and q[0] > r[2] - TOL]
    if right:
        return min(right, key=lambda q: q[0]), "u"
    below = [q for q in rects if abs(q[0] - r[0]) < TOL and q[3] < r[1] + TOL]
    if below:
        return max(below, key=lambda q: q[3]), "v"
    return None, None


def dimensions(w: float, h: float, outline: Rect, *, markers: Sequence[Rect] = (),
               marker_mm: float = 0.0, squares: Sequence[Rect] = (), checker_mm: float = 0.0,
               separation_mm: float = 0.0, spot: Optional[Pt] = None, at: Optional[Pt] = None,
               offset_mm: float = 0.0) -> List[dict]:
    """The dimensions of a filled rectangle, each {field, value_mm, a, b,
    offset_mm} in the rectangle's frame, drawn offset_mm to the LEFT of a->b.
    Every endpoint is on the drawn geometry and every line stands outside the
    rectangle (rings DIM_STEP apart), so none crosses the marker:

        top     marker_mm     the top-left marker's black square, its top edge
                separation    that marker to its right neighbour (else, on the
                / checker     left, to the one below); ChArUco: the top-left
                              black square's top edge
                outer         the outline's (quiet-zone edge) top edge
        left    outer         the outline's left edge
        bottom  rect.w        the rectangle
        right   rect.h
        inside  label.offset_mm   the preset spot -> the label (offset != 0)

    `markers` / `squares`: the black squares of the markers / the ChArUco
    board in the rectangle's frame; `outline` the quiet-zone edge."""
    s = dim_step(w, h)
    top, left = h / 2.0, -w / 2.0
    out: List[dict] = []

    def add(fld, value, a, b, off):
        out.append({"field": fld, "value_mm": float(value), "a": a, "b": b, "offset_mm": off})

    m = _top_left(markers)
    if m is not None and marker_mm > 0:
        add("marker.marker_mm", marker_mm, (m[0], m[3]), (m[2], m[3]), top - m[3] + s)
    if m is not None and separation_mm > 0:
        q, axis = _neighbour(m, markers)
        if axis == "u":
            add("marker.separation_mm", separation_mm, (m[2], m[3]), (q[0], m[3]),
                top - m[3] + 2.0 * s)
        elif axis == "v":                               # upward: drawn on the left
            add("marker.separation_mm", separation_mm, (m[0], q[3]), (m[0], m[1]),
                m[0] - left + 2.0 * s)
    sq = _top_left(squares)
    if sq is not None and checker_mm > 0:
        add("marker.checker_mm", checker_mm, (sq[0], sq[3]), (sq[2], sq[3]), top - sq[3] + 2.0 * s)
    ox0, oy0, ox1, oy1 = outline
    add("outer", ox1 - ox0, (ox0, oy1), (ox1, oy1), top - oy1 + 3.0 * s)
    add("outer", oy1 - oy0, (ox0, oy0), (ox0, oy1), ox0 - left + s)
    add("rect.w", w, (w / 2.0, -h / 2.0), (-w / 2.0, -h / 2.0), s)
    add("rect.h", h, (w / 2.0, h / 2.0), (w / 2.0, -h / 2.0), s)
    if spot is not None and at is not None and offset_mm > TOL:
        add("label.offset_mm", offset_mm, spot, at, 0.0)
    return out


# ------------------------------------------------------------------ ChArUco origin

def square_origin(opencv: Sequence[float], col: int, row: int, square_mm: float) -> List[float]:
    """OpenCV's board frame (16 numbers, row-major, mm) moved to the centre of
    board square [col, row] (0-based from its origin corner; x along the
    columns, y along the rows, as OpenCV's object points run), axes kept."""
    tu, tv = (col + 0.5) * square_mm, (row + 0.5) * square_mm
    F = list(opencv)
    for i in range(3):
        F[4 * i + 3] = F[4 * i] * tu + F[4 * i + 1] * tv + F[4 * i + 3]
    return F
