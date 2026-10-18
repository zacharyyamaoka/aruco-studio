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
                the box the marker fills (`Fill.box`); the text's preset
                spot is the band's centre, `offset` moves it from there
    font        "sans" (inkjet: ordinary text the page prints, `Fill.runs`)
                or "pixel" (3D print: core.label's pixel font of 2026-10-10,
                its ink as boxes, `Fill.ink`; one pixel = a whole number of
                the preset's lines on Auto size)

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
LABEL_CAP = (0.12, 2.5, 12.0)       # Auto cap: 0.12 x the short side, within 2.5 .. 12 mm
LINE_GAP = _AL.LINE_GAP_PX / _AL.GLYPH_ROWS     # between lines, x the cap (the pixel font's 2 px of 5)
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
    spot: Pt                         # the preset spot: the band's centre
    at: Pt                           # the text block's centre (spot + offset)
    block: Tuple[float, float]       # the text block's width, height
    runs: List[Run] = field(default_factory=list)     # sans
    ink: List[Rect] = field(default_factory=list)     # pixel
    issues: List[Tuple[str, str, str]] = field(default_factory=list)   # (field, level, text)

    @property
    def box_size(self) -> Tuple[float, float]:
        return self.box[2] - self.box[0], self.box[3] - self.box[1]

    @property
    def box_centre(self) -> Pt:
        return (self.box[0] + self.box[2]) / 2.0, (self.box[1] + self.box[3]) / 2.0


def fill(w: float, h: float, text: str, *, font: str = "sans", cap_mm: float = 0.0,
         side: str = "below", gap_mm: float = 0.0, offset: Pt = (0.0, 0.0),
         line_mm: float = 0.0) -> Fill:
    """Reserve the label's band inside a w x h rectangle; the marker gets the
    rest. `cap_mm` 0 = Auto (LABEL_CAP; "pixel" rounds it down to whole
    lines of `line_mm`). Nothing is refused: a label too wide is flagged, a
    label that leaves no room flags an error and leaves MIN_BOX_MM."""
    w, h = float(w), float(h)
    issues: List[Tuple[str, str, str]] = []
    if side not in SIDES:
        issues.append(("label.side", "warn", f"side {side!r} is not one of {', '.join(SIDES)}: below"))
        side = "below"
    font = font if font in FONTS else "sans"
    lines = lines_of(text)
    typed = float(cap_mm or 0.0) > 0
    cap = float(cap_mm) if typed else auto_cap(w, h)
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
    gap = max(0.0, float(gap_mm or 0.0))
    x0, y0, x1, y1 = -w / 2.0, -h / 2.0, w / 2.0, h / 2.0
    if side == "below":
        band, box = (x0, y0, x1, y0 + bh), (x0, y0 + bh + gap, x1, y1)
    elif side == "above":
        band, box = (x0, y1 - bh, x1, y1), (x0, y0, x1, y1 - bh - gap)
    elif side == "left":
        band, box = (x0, y0, x0 + bw, y1), (x0 + bw + gap, y0, x1, y1)
    else:
        band, box = (x1 - bw, y0, x1, y1), (x0, y0, x1 - bw - gap, y1)
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
    spot = ((band[0] + band[2]) / 2.0, (band[1] + band[3]) / 2.0)
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
