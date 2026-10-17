# Ported from REF CADExporter/bam_cad_core/print_sheet.py at c8216ff, brought up to f5ebf4e (N-1):
# copied verbatim, only the package-relative imports renamed. ArUco Studio
# M6a (2026-10-16) adds fields to PrintItem and SheetSettings (defaults =
# REF's behaviour) and, below "the sticker sheet", the plan-driven sheet:
# layout_stickers (spaced / tight), render_sticker_pdf / _svg, sticker_summary.
"""Printable marker sheets: exact-size ArUco stickers as a vector PDF.

### The one rule: a marker is never scaled to fit

`marker_length_m` is the BLACK SQUARE's side, border included — the number
estimatePoseSingleMarkers() multiplies by. Print a 30 mm marker at 29 mm and
nothing fails: every range the robot reports is just 3.3 % short, forever. So
`layout_sheet` places each sticker at exactly its size or REJECTS it with a
reason. There is no shrink-to-fit path, here or in the PDF.

### Geometry

    module   = marker_length / (n + 2)            n = dictionary bits
    extent   = the black pattern: marker_length square for a single marker,
               aruco_board.extent_m for a grid / ChArUco board (non-square)
    sticker  = extent + 2 * quiet_modules * module on each axis  (the cut extent)
    cell     = sticker, plus a label box under it when labels are on

A board item is a PrintItem with layout "grid" or "charuco": marker_id is
then the board's FIRST id, and rows / cols / separation_m / square_length_m /
legacy mean what they mean in aruco_board.BoardSpec.

All layout numbers are MILLIMETRES with the origin at the page's TOP-LEFT
corner, y pointing down (the way a sheet is read). The PDF writer converts to
points (1 mm = 72/25.4 pt, bottom-left origin) at the last moment, and draws
each item's black ink as one path of filled rectangles from
`aruco_board.black_rects_m` — vectors, so the printer, not a resampler,
decides where the edges fall.

Every page carries a scale-check ruler (a 100 mm bar and a 4 in bar) because
the last thing between this file and a mis-scaled marker is a print dialog
defaulting to "fit to page". The PDF is hand-written PDF 1.4 with the base-14
Helvetica, stdlib only, so it can be produced inside Fusion. Its catalog says
/PrintScaling /None, which tells the viewer's print dialog to start at
Actual size instead of "fit"; `render_layout_pdf(print_dialog=True)` makes a
copy that opens that dialog itself (document JavaScript, bUI true: nothing
prints until the user presses Print).

### A ChArUco board prints exactly as the CAD has it (2026-10-17)

A board item made from a CAD tag has `marks="cad"`: its sticker carries the
board, the CAD's own label and corner mark (`ink`, pure black or pure white,
from the tag record) and nothing else -- no grey triangle, no grey board
label, no cut line over the board (the line is drawn outside the sticker).
"""
from __future__ import annotations

import datetime
import math
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import board as aruco_board, dictionary as aruco_dict

MM_TO_PT = 72.0 / 25.4

PAGE_SIZES_MM: Dict[str, Tuple[float, float]] = {
    "letter": (215.9, 279.4), "a4": (210, 297), "legal": (215.9, 355.6),
    "a3": (297, 420), "tabloid": (279.4, 431.8), "a5": (148, 210),
}

LABEL_FONT_PT = 6.0
LABEL_MIN_FONT_PT = 4.5      # shrink a long label to the sticker width, not below this
LABEL_LEADING = 1.2          # line pitch / font size
LABEL_GAP_MM = 0.8           # sticker bottom -> label box text
FOOTER_FONT_PT = 6.5
FOOTER_H_MM = 4.0
RULER_H_MM = 19.0
RULER_W_MM = 102.0           # the 4 in bar is 101.6 mm; nothing sits beside the bars
BAND_GAP_MM = 3.0            # sticker area -> ruler block
CUT_GREY = 0.55
CUT_LINE_MM = 0.1
SMALL_MODULE_MM = 0.5
_EPS = 1e-9

# Marks (docs/proposal_aruco_marks.md, measured on 430,260 simulated photos;
# Zach 2026-10-07: "lets just do good defaults ... put it in the black at the
# bottom always", nothing that grows the sticker past what was modelled):
#   id_mark "border"   "#id" knocked out WHITE in each marker's bottom border
#                      row, cap height <= 0.5 module, centred clear of the
#                      corner cells, shrunk to fit: -0.3 pp detection (n.s.)
#   orient_mark "triangle"  a 0.5-grey right triangle, legs 0.6 module, in the
#                      quiet zone's top-left corner = OpenCV corner 0 of a
#                      single marker / the board frame origin: +0.2 pp
#   ChArUco            the board label in light grey in the top-left BLACK
#                      square instead of per-marker ids (free in the study)
# Ink in the 1-module WHITE ring is what costs (grey id there: -11 pp, up to
# -40 with dot gain), so nothing is ever written there.
ID_CAP_MODULES = 0.5
HELVETICA_CAP = 0.718           # cap height / em
TRI_LEG_MODULES = 0.6
TRI_GREY = 0.5
CHARUCO_LABEL_GREY = 0.75
MIN_CAP_MM = 1.0                # below this a label is cut short, not shrunk


@dataclass
class PrintItem:
    key: str
    dictionary: str
    marker_id: int
    marker_length_m: float          # BLACK SQUARE side incl. its black border
    quiet_modules: float = 1.0
    label_lines: List[str] = field(default_factory=list)   # [] -> identity line
    # Boards (aruco_board.BoardSpec); a single marker leaves these alone.
    layout: str = "single"          # "single" | "grid" | "charuco"
    rows: int = 1
    cols: int = 1
    separation_m: float = 0.0       # grid: gap between markers
    square_length_m: float = 0.0    # charuco: square side
    legacy: bool = False            # charuco: OpenCV setLegacyPattern
    # Short part name for the marker's TOP border row (study section 11:
    # "#id" bottom + part name top costs -0.2 pp vs "#id" alone, within
    # noise). "" = nothing in the top row.
    top_label: str = ""
    # What the sticker carries besides the pattern:
    #   "sheet"  the sheet's own marks (SheetSettings id_mark / orient_mark /
    #            top_label; a ChArUco board's grey label)
    #   "cad"    exactly the CAD tag's: `ink`, and nothing else (ChArUco
    #            boards, 2026-10-17: the paper board is the CAD board)
    marks: str = "sheet"
    # marks="cad": the CAD's own label and corner mark, painted over the
    # pattern in order -- [(colour, polygon)], colour "black" | "white",
    # polygon [(x, y), ...] in mm in the pattern's CENTRE frame (+y up)
    ink: List[Tuple[str, List[Tuple[float, float]]]] = field(default_factory=list)
    # marks="cad": the CAD tile's outline when it is not the pattern + quiet
    # zone (a label strip grows it; a cut corner), a polygon in the same
    # frame. The sticker is the box round it, the pattern and the ink.
    outline_mm: Optional[List[Tuple[float, float]]] = None
    # ArUco Studio M6a (not REF's; None / "" = REF's sticker): the sticker as
    # its plan has it, in the sticker's own frame (mm, y up, the pattern's
    # centre at 0): the cut polygon {"outer": [[u, v]...], "holes": [...]}
    # and the black seen from above [[outer, hole, ...], ...]. With ink_mm
    # the sheet draws THIS and none of its own marks. (N-1, 2026-10-17: the
    # cut polygon was `outline_mm`; REF f5ebf4e gave that name to its CAD
    # tile outline, a list polygon, so the Studio's is `cut_mm`.)
    cut_mm: Optional[dict] = None
    ink_mm: Optional[list] = None
    caption: str = ""               # spaced mode: the words under the sticker
    made_by: str = ""               # "sticker" / "print3d" (a paper proof)
    name: str = ""                  # the tag's name
    ids: List[int] = field(default_factory=list)


@dataclass
class SheetSettings:
    page: str = "letter"
    landscape: bool = False
    margin_mm: float = 10
    gap_mm: float = 4
    cut_marks: bool = True
    labels: bool = True
    ruler: bool = True
    title: str = ""
    custom_page_mm: Optional[Tuple[float, float]] = None   # (w, h), overrides page
    id_mark: str = "border"        # "border" | "off"
    top_label: bool = True         # part name in the top border row
    orient_mark: str = "triangle"  # "triangle" | "off"
    mode: str = "spaced"           # M6a, layout_stickers: "spaced" (gaps, captions, crop
                                   # marks) | "tight" (shared cut lines, guillotine shelves)
    sticker_margin_mm: float = 0.0  # 2026-10-17 (Q7): white paper round each sticker, its
                                    # cut line that much out (layout_stickers); 0 = as planned


class RejectedItem(NamedTuple):
    item: PrintItem
    reason: str


@dataclass
class PlacedItem:
    item: PrintItem
    page: int                       # 0-based page index
    x_mm: float                     # sticker (cut extent) top-left, page coords
    y_mm: float
    sticker_mm: float               # sticker WIDTH (== height for a single marker)
    marker_mm: float                # == item.marker_length_m * 1000, always
    module_mm: float
    modules: int                    # n + 2
    marker_x_mm: float              # black pattern (extent) top-left
    marker_y_mm: float
    cell: Tuple[float, float, float, float]               # x, y, w, h reserved
    label_box: Optional[Tuple[float, float, float, float]]
    label_lines: List[str]
    label_font_pt: float
    sticker_w_mm: float = 0.0
    sticker_h_mm: float = 0.0
    extent_w_mm: float = 0.0        # black pattern; == marker_mm for a single
    extent_h_mm: float = 0.0


@dataclass
class SheetLayout:
    settings: SheetSettings
    page_mm: Tuple[float, float]                          # w, h
    printable_mm: Tuple[float, float, float, float]       # sticker area x, y, w, h
    pages: List[List[PlacedItem]]
    rejected: List[RejectedItem]
    ruler: Optional[dict]          # {"mm_bar": (x,y,w,h), "in_bar": (x,y,w,h), "top": y}
    warnings: List[str]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def placed(self) -> List[PlacedItem]:
        return [p for page in self.pages for p in page]


# ------------------------------------------------------------------ text metrics

# Helvetica advance widths (AFM, 1/1000 em) for WinAnsi 32..126.
_ASCII_W = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584)
_WIDTHS = {32 + i: w for i, w in enumerate(_ASCII_W)}
_WIDTHS.update({0x85: 1000, 0x91: 222, 0x92: 222, 0x93: 333, 0x94: 333,
                0x95: 350, 0x96: 556, 0x97: 1000, 0xA0: 278, 0xB0: 400,
                0xB1: 584, 0xB5: 556, 0xB7: 278, 0xD7: 584})


def _encode(text: str) -> bytes:
    return str(text).encode("cp1252", errors="replace")


def text_width_mm(text: str, font_pt: float) -> float:
    """Advance width of `text` in Helvetica at `font_pt`, in mm."""
    units = sum(_WIDTHS.get(b, 556) for b in _encode(text))
    return units / 1000.0 * font_pt / MM_TO_PT


def _fit_text(text: str, font_pt: float, max_mm: float) -> str:
    if text_width_mm(text, font_pt) <= max_mm:
        return text
    while len(text) > 1 and text_width_mm(text + "…", font_pt) > max_mm:
        text = text[:-1]
    return text + "…"


def _fmt_mm(v: float) -> str:
    s = "%.2f" % v
    return s[:-1] if s.endswith("0") else s


def board_spec(item: PrintItem) -> "aruco_board.BoardSpec":
    """The aruco_board.BoardSpec a PrintItem describes (marker_id = first id)."""
    return aruco_board.BoardSpec(
        layout=item.layout, dictionary=item.dictionary, first_id=item.marker_id,
        marker_length_m=item.marker_length_m, rows=item.rows, cols=item.cols,
        separation_m=item.separation_m, square_length_m=item.square_length_m,
        legacy=item.legacy)


def identity_label(item: PrintItem) -> str:
    """The default label line: what a person needs to match sticker to CAD."""
    size = _fmt_mm(item.marker_length_m * 1000.0)
    if item.layout == "single":
        return "%s #%s · %s mm" % (item.dictionary, item.marker_id, size)
    try:
        last = item.marker_id + aruco_board.marker_count(board_spec(item)) - 1
    except (ValueError, TypeError):
        last = "?"
    if item.layout == "grid":
        return "%s grid %dx%d #%s–%s · %s mm, gap %s mm" % (
            item.dictionary, item.cols, item.rows, item.marker_id, last, size,
            _fmt_mm(item.separation_m * 1000.0))
    return "%s ChArUco %dx%d #%s–%s · square %s / marker %s mm%s" % (
        item.dictionary, item.cols, item.rows, item.marker_id, last,
        _fmt_mm(item.square_length_m * 1000.0), size,
        " (legacy)" if item.legacy else "")


# ------------------------------------------------------------------ layout


def page_size_mm(settings: SheetSettings) -> Tuple[float, float]:
    if settings.custom_page_mm is not None:
        w, h = (float(v) for v in settings.custom_page_mm)
        if not (w > 0 and h > 0):
            raise ValueError("custom_page_mm must be two positive lengths, got %r"
                             % (settings.custom_page_mm,))
    else:
        key = str(settings.page).lower()
        if key not in PAGE_SIZES_MM:
            raise ValueError("unknown page %r — expected one of %s or custom_page_mm"
                             % (settings.page, ", ".join(PAGE_SIZES_MM)))
        w, h = (float(v) for v in PAGE_SIZES_MM[key])
    if settings.landscape and w < h:
        w, h = h, w
    return w, h


class _Prepared(NamedTuple):
    index: int
    item: PrintItem
    modules: int
    marker_mm: float
    module_mm: float
    sticker_w: float
    sticker_h: float
    extent_w: float
    extent_h: float
    lines: List[str]
    font_pt: float
    label_h: float
    cell_w: float
    cell_h: float
    pad_l: float = 0.0              # sticker's left edge -> the pattern's
    pad_t: float = 0.0              # sticker's top edge -> the pattern's
    note: str = ""                  # placed, but something was left off (a warning)


INK_COLOURS = {"black": 0.0, "white": 1.0}


def _cad_points(item):
    """marks="cad": every point of the outline and the ink (centre frame,
    mm) -> list, or raise ValueError naming what is wrong."""
    pts = []
    if item.outline_mm is not None:
        if len(item.outline_mm) < 3:
            raise ValueError("outline_mm needs 3 or more points")
        pts += [(float(x), float(y)) for x, y in item.outline_mm]
    for k, entry in enumerate(item.ink or ()):
        colour, poly = entry
        if colour not in INK_COLOURS:
            raise ValueError("ink %d: colour %r is not black or white" % (k, colour))
        if len(poly) < 3:
            raise ValueError("ink %d: a polygon needs 3 or more points" % k)
        pts += [(float(x), float(y)) for x, y in poly]
    if not all(math.isfinite(v) for p in pts for v in p):
        raise ValueError("outline / ink points must be finite numbers")
    return pts


def sticker_box_mm(item: PrintItem) -> Tuple[float, float, float, float]:
    """The sticker (what is cut out) as (x0, y0, x1, y1) in mm in the
    pattern's centre frame (+y up): the pattern + quiet zone, and for
    marks="cad" also the CAD's outline and ink. Raises ValueError on a bad
    item (layout_sheet rejects it with that reason)."""
    info = aruco_dict.dictionary_info(item.dictionary)
    w, h = (v * 1000.0 for v in aruco_board.extent_m(board_spec(item)))
    q = float(item.quiet_modules) * float(item.marker_length_m) * 1000.0 / info["modules"]
    x0, y0, x1, y1 = -w / 2.0 - q, -h / 2.0 - q, w / 2.0 + q, h / 2.0 + q
    if item.marks == "cad":
        for x, y in _cad_points(item):
            x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
    return x0, y0, x1, y1


def _prepare(index, item, settings, area_w, area_h):
    """-> (_Prepared, None) or (None, reason)."""
    try:
        info = aruco_dict.dictionary_info(item.dictionary)
    except ValueError as exc:
        return None, str(exc)
    mid = item.marker_id
    if isinstance(mid, bool) or not isinstance(mid, int) or not 0 <= mid < info["capacity"]:
        return None, ("id %r is not in %s (0..%d)"
                      % (mid, info["name"], info["capacity"] - 1))
    try:
        length = float(item.marker_length_m)
        quiet = float(item.quiet_modules)
    except (TypeError, ValueError):
        return None, "marker_length_m and quiet_modules must be numbers"
    if not (math.isfinite(length) and length > 0):
        return None, "marker_length_m must be > 0 (got %r)" % (item.marker_length_m,)
    if not (math.isfinite(quiet) and quiet >= 0):
        return None, "quiet_modules must be >= 0 (got %r)" % (item.quiet_modules,)
    if item.marks not in ("sheet", "cad"):
        return None, "marks must be 'sheet' or 'cad' (got %r)" % (item.marks,)
    try:
        extent_w, extent_h = (v * 1000.0 for v in aruco_board.extent_m(board_spec(item)))
    except (ValueError, TypeError) as exc:
        return None, "%s board: %s" % (item.layout, exc)
    modules = info["modules"]
    marker_mm = length * 1000.0
    module_mm = marker_mm / modules
    sticker_w = extent_w + 2.0 * quiet * module_mm
    sticker_h = extent_h + 2.0 * quiet * module_mm
    pad_l = pad_t = (sticker_w - extent_w) / 2.0
    if item.marks == "cad" and (item.ink or item.outline_mm is not None):
        try:
            x0, y0, x1, y1 = sticker_box_mm(item)
        except (ValueError, TypeError) as exc:
            return None, "the CAD's label / corner mark: %s" % exc
        sticker_w, sticker_h = x1 - x0, y1 - y0
        pad_l, pad_t = -extent_w / 2.0 - x0, y1 - extent_h / 2.0

    lines: List[str] = []
    font_pt = LABEL_FONT_PT
    label_h = 0.0
    label_w = 0.0
    if settings.labels:
        lines = [str(s) for s in item.label_lines] or [identity_label(item)]
        widest = max(text_width_mm(s, font_pt) for s in lines)
        if widest > sticker_w:
            font_pt = max(LABEL_MIN_FONT_PT, LABEL_FONT_PT * sticker_w / widest)
        lines = [_fit_text(s, font_pt, area_w) for s in lines]
        label_w = max(text_width_mm(s, font_pt) for s in lines)
        label_h = LABEL_GAP_MM + len(lines) * font_pt * LABEL_LEADING / MM_TO_PT
    cell_w = max(sticker_w, label_w)
    cell_h = sticker_h + label_h
    note = ""
    if (label_h and cell_h > area_h + _EPS and sticker_w <= area_w + _EPS
            and sticker_h <= area_h + _EPS):
        # the sticker fits, only the text under it does not: print the
        # sticker without it rather than not at all (the label is not part
        # of the target; a CAD label on the board still prints)
        note = ("the label under it was left off: the %.1f mm tall sticker fits the %.1f mm "
                "printable height only without it" % (sticker_h, area_h))
        lines, label_h = [], 0.0
        cell_w, cell_h = sticker_w, sticker_h
    if sticker_w > area_w + _EPS or cell_h > area_h + _EPS:
        what = ("%.1f mm marker" % marker_mm if item.layout == "single" else
                "%.1f x %.1f mm %s board" % (extent_w, extent_h, item.layout))
        return None, (
            "sticker is %.1f x %.1f mm (%s + quiet zone%s) but the "
            "printable area is %.1f x %.1f mm — markers are never scaled to "
            "fit; use a larger page, landscape or smaller margins"
            % (sticker_w, cell_h, what, " + label" if label_h else "",
               area_w, area_h))
    return _Prepared(index, item, modules, marker_mm, module_mm, sticker_w, sticker_h,
                     extent_w, extent_h, lines, font_pt, label_h, cell_w, cell_h,
                     pad_l, pad_t, note), None


def layout_sheet(items: List[PrintItem], settings: Optional[SheetSettings] = None) -> SheetLayout:
    """Place every item at its exact size, or reject it with a reason.

    First-fit-decreasing shelf packing: items sorted by sticker height, then
    width (largest first, ties in input order), each goes on the first open shelf on any page
    with room, else opens a shelf on the first page with height left, else a
    new page. Deterministic for a given input."""
    settings = settings or SheetSettings()
    page_w, page_h = page_size_mm(settings)
    m = float(settings.margin_mm)
    gap = float(settings.gap_mm)
    if m < 0 or gap < 0:
        raise ValueError("margin_mm and gap_mm must be >= 0")
    warnings: List[str] = []
    x0, y0 = m, m
    area_w = page_w - 2 * m
    footer_top = page_h - m - FOOTER_H_MM
    ruler = None
    area_bottom = footer_top - BAND_GAP_MM
    if settings.ruler:
        if area_w + _EPS >= RULER_W_MM:
            top = footer_top - RULER_H_MM
            ruler = {"top": top,
                     "mm_bar": (x0, top + 10.5, 100.0, 1.2),
                     "in_bar": (x0, top + 13.3, 101.6, 1.2)}
            area_bottom = top - BAND_GAP_MM
        else:
            warnings.append("page is %.1f mm wide inside the margins; the scale "
                            "ruler needs %.0f mm and was left off — check the "
                            "print scale another way" % (area_w, RULER_W_MM))
    area_h = area_bottom - y0
    if area_w <= 0 or area_h <= 0:
        raise ValueError("margins and ruler leave no printable area on a "
                         "%.1f x %.1f mm page" % (page_w, page_h))

    prepared: List[_Prepared] = []
    rejected: List[RejectedItem] = []
    for index, item in enumerate(items):
        prep, reason = _prepare(index, item, settings, area_w, area_h)
        if prep is None:
            rejected.append(RejectedItem(item, reason))
        else:
            prepared.append(prep)
            if prep.note:
                warnings.append("%s: %s" % (item.key, prep.note))
            if prep.module_mm < SMALL_MODULE_MM:
                warnings.append("%s: module is %.2f mm — below ~%.1f mm many "
                                "printers blur the cells" % (item.key, prep.module_mm,
                                                             SMALL_MODULE_MM))

    prepared.sort(key=lambda p: (-p.sticker_h, -p.sticker_w, -p.cell_h, p.index))
    x1, y1 = x0 + area_w, y0 + area_h
    shelves: List[List[float]] = []          # [page, y, h, next_x]
    next_shelf_y: List[float] = []           # per page
    pages: List[List[PlacedItem]] = []
    for p in prepared:
        spot = None
        for shelf in shelves:
            if p.cell_h <= shelf[2] + _EPS and shelf[3] + p.cell_w <= x1 + _EPS:
                spot = (int(shelf[0]), shelf[3], shelf[1])
                shelf[3] += p.cell_w + gap
                break
        if spot is None:
            for page_index, y in enumerate(next_shelf_y):
                if y + p.cell_h <= y1 + _EPS:
                    spot = (page_index, x0, y)
                    break
            if spot is None:
                pages.append([])
                next_shelf_y.append(y0)
                spot = (len(pages) - 1, x0, y0)
            shelves.append([spot[0], spot[2], p.cell_h, x0 + p.cell_w + gap])
            next_shelf_y[spot[0]] = spot[2] + p.cell_h + gap
        page_index, cx, cy = spot
        sx = cx + (p.cell_w - p.sticker_w) / 2.0
        label_box = ((cx, cy + p.sticker_h, p.cell_w, p.label_h)
                     if p.label_h else None)
        pages[page_index].append(PlacedItem(
            item=p.item, page=page_index, x_mm=sx, y_mm=cy,
            sticker_mm=p.sticker_w, marker_mm=p.marker_mm, module_mm=p.module_mm,
            modules=p.modules, marker_x_mm=sx + p.pad_l, marker_y_mm=cy + p.pad_t,
            cell=(cx, cy, p.cell_w, p.cell_h), label_box=label_box,
            label_lines=list(p.lines), label_font_pt=p.font_pt,
            sticker_w_mm=p.sticker_w, sticker_h_mm=p.sticker_h,
            extent_w_mm=p.extent_w, extent_h_mm=p.extent_h))
    for page in pages:
        page.sort(key=lambda q: (q.y_mm, q.x_mm))
    return SheetLayout(settings=settings, page_mm=(page_w, page_h),
                       printable_mm=(x0, y0, area_w, area_h), pages=pages,
                       rejected=rejected, ruler=ruler, warnings=warnings)


def fit_pages(item: PrintItem, settings: Optional[SheetSettings] = None,
              pages=None) -> List[Tuple[str, bool]]:
    """Every (page, landscape) of `pages` (default PAGE_SIZES_MM, in its
    order) on which `item` is placed with `settings`' margin, ruler and
    labels -- what to suggest when it does not fit the page chosen."""
    import dataclasses
    base = settings or SheetSettings()
    out = []
    for page in (pages or PAGE_SIZES_MM):
        for landscape in (False, True):
            s = dataclasses.replace(base, page=page, landscape=landscape, custom_page_mm=None)
            try:
                lay = layout_sheet([item], s)
            except ValueError:
                continue
            if lay.placed:
                out.append((page, landscape))
    return out


def _r(v: float) -> float:
    return round(v, 4)


def _board_summary(item: PrintItem) -> dict:
    if item.layout == "single":
        return {}
    spec = board_spec(item)
    return {"rows": item.rows, "cols": item.cols, "ids": aruco_board.ids(spec),
            "separation_mm": _r(item.separation_m * 1000.0),
            "square_length_mm": _r(item.square_length_m * 1000.0),
            "legacy": bool(item.legacy),
            "opencv_frame": aruco_board.opencv_frame(spec)}


def layout_summary(layout: SheetLayout) -> dict:
    """JSON-able account of a layout, for reports. page_number is 1-based."""
    s = layout.settings
    x, y, w, h = layout.printable_mm
    return {
        "page": s.page if s.custom_page_mm is None else "custom",
        "page_mm": [_r(layout.page_mm[0]), _r(layout.page_mm[1])],
        "landscape": bool(s.landscape),
        "printable_mm": {"x": _r(x), "y": _r(y), "w": _r(w), "h": _r(h)},
        "origin": "page top-left, y down, millimetres",
        "scale": 1.0,
        "pages": layout.page_count,
        "placed": [{
            "key": p.item.key, "dictionary": p.item.dictionary,
            "marker_id": p.item.marker_id,
            "marker_length_mm": _r(p.marker_mm), "module_mm": _r(p.module_mm),
            "quiet_modules": p.item.quiet_modules, "sticker_mm": _r(p.sticker_mm),
            "sticker_w_mm": _r(p.sticker_w_mm), "sticker_h_mm": _r(p.sticker_h_mm),
            "layout": p.item.layout,
            "extent_mm": [_r(p.extent_w_mm), _r(p.extent_h_mm)],
            "page_number": p.page + 1, "x_mm": _r(p.x_mm), "y_mm": _r(p.y_mm),
            "marker_x_mm": _r(p.marker_x_mm), "marker_y_mm": _r(p.marker_y_mm),
            "label_lines": list(p.label_lines),
            **_board_summary(p.item),
            **({"marks": "cad", "ink_polygons": len(p.item.ink),
                "outline": p.item.outline_mm is not None}
               if p.item.marks == "cad" else {}),
        } for p in layout.placed],
        "rejected": [{
            "key": r.item.key, "dictionary": r.item.dictionary,
            "marker_id": r.item.marker_id, "marker_length_m": r.item.marker_length_m,
            "layout": r.item.layout, "reason": r.reason,
        } for r in layout.rejected],
        "ruler": None if layout.ruler is None else {
            k: ([_r(v) for v in val] if isinstance(val, tuple) else _r(val))
            for k, val in layout.ruler.items()},
        "warnings": list(layout.warnings),
    }


# ------------------------------------------------------------------ PDF


def _n(v: float) -> str:
    text = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def pdf_string(text: str) -> str:
    """A PDF literal string for WinAnsi Helvetica: cp1252 bytes, with ( ) \\
    escaped and everything outside printable ASCII written as octal."""
    out = []
    for b in _encode(text):
        if b in (0x28, 0x29, 0x5C):
            out.append("\\" + chr(b))
        elif 32 <= b < 127:
            out.append(chr(b))
        else:
            out.append("\\%03o" % b)
    return "(" + "".join(out) + ")"


class _Page:
    """Content-stream builder in millimetres, top-left origin."""

    def __init__(self, page_h_mm: float):
        self.h = page_h_mm
        self.ops: List[str] = []

    def rect(self, x, y, w, h) -> str:
        return "%s %s %s %s re" % (_n(x * MM_TO_PT), _n((self.h - y - h) * MM_TO_PT),
                                   _n(w * MM_TO_PT), _n(h * MM_TO_PT))

    def fill_rects(self, rects, grey=0.0):
        if rects:
            self.ops.append("%s g" % _n(grey))
            self.ops.extend(self.rect(*r) for r in rects)
            self.ops.append("f")

    def stroke_rect(self, x, y, w, h, grey, width_mm):
        self.ops.append("%s G %s w %s S" % (_n(grey), _n(width_mm * MM_TO_PT),
                                             self.rect(x, y, w, h)))

    def text(self, x, baseline_y, s, size, align="left", grey=0.0):
        if align != "left":
            width = text_width_mm(s, size)
            x -= width / 2.0 if align == "center" else width
        self.ops.append("BT /F1 %s Tf %s g %s %s Td %s Tj ET"
                        % (_n(size), _n(grey), _n(x * MM_TO_PT),
                           _n((self.h - baseline_y) * MM_TO_PT), pdf_string(s)))

    def triangle(self, x, y, leg, grey):
        """Right triangle, right angle at (x, y) (top-left), legs along +x, +y."""
        yy = self.h - y
        self.ops.append("%s g %s %s m %s %s l %s %s l h f"
                        % (_n(grey), _n(x * MM_TO_PT), _n(yy * MM_TO_PT),
                           _n((x + leg) * MM_TO_PT), _n(yy * MM_TO_PT),
                           _n(x * MM_TO_PT), _n((yy - leg) * MM_TO_PT)))

    def _path(self, pts) -> str:
        """A closed path through page points (mm, y down)."""
        ops = ["%s %s %s" % (_n(x * MM_TO_PT), _n((self.h - y) * MM_TO_PT), "m" if k == 0 else "l")
               for k, (x, y) in enumerate(pts)]
        return " ".join(ops) + " h"

    def fill_poly(self, pts, grey):
        """One polygon filled on its own (overlapping ones never cancel)."""
        self.ops.append("%s g %s f" % (_n(grey), self._path(pts)))

    def stroke_poly(self, pts, grey, width_mm):
        self.ops.append("%s G %s w %s S" % (_n(grey), _n(width_mm * MM_TO_PT), self._path(pts)))


def offset_polygon(pts, d):
    """A simple polygon grown outward by `d` (mitred corners): each edge
    moved out along its normal, consecutive edges met again. Either
    orientation."""
    n = len(pts)
    area = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(n))
    s = 1.0 if area > 0 else -1.0                 # CCW: the outward normal is (dy, -dx)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        L = math.hypot(x1 - x0, y1 - y0) or 1.0
        nx, ny = s * (y1 - y0) / L, -s * (x1 - x0) / L
        lines.append(((x0 + nx * d, y0 + ny * d), (x1 - x0, y1 - y0)))
    out = []
    for i in range(n):
        (p, r), (q, t) = lines[i - 1], lines[i]
        den = r[0] * t[1] - r[1] * t[0]
        if abs(den) < 1e-12:                       # collinear edges: keep the moved point
            out.append(q)
            continue
        u = ((q[0] - p[0]) * t[1] - (q[1] - p[1]) * t[0]) / den
        out.append((p[0] + u * r[0], p[1] + u * r[1]))
    return out


def _border_text(pg, text, left_mm, edge_mm, length_mm, module_mm, row="bottom",
                 min_cap_mm=0.0):
    """White text centred in a marker's border row (page mm, y down).

    `edge_mm` is the marker's bottom edge (row="bottom") or top edge
    (row="top"). The corner cells are left clear and the cap height never
    exceeds ID_CAP_MODULES -- a longer text gets a smaller font, never a
    taller row; below `min_cap_mm` it is cut short with "..." instead."""
    cap = ID_CAP_MODULES * module_mm
    size = cap / HELVETICA_CAP * MM_TO_PT
    room = (length_mm - 2.0 * module_mm) * 0.9
    width = text_width_mm(text, size)
    if width > room > 0:
        floor_size = min_cap_mm / HELVETICA_CAP * MM_TO_PT
        size = max(size * room / width, min(size, floor_size))
        while text_width_mm(text, size) > room and len(text) > 4:
            text = text[:-4].rstrip() + "..."
        cap = size / MM_TO_PT * HELVETICA_CAP
    if row == "top":
        baseline = edge_mm + module_mm - (module_mm - cap) / 2.0
    else:
        baseline = edge_mm - (module_mm - cap) / 2.0
    pg.text(left_mm + length_mm / 2.0, baseline, text, size, "center", grey=1.0)


def _marks(pg, p, settings):
    """Orientation triangle + ids, all inside the sticker the CAD modelled."""
    item = p.item
    module = p.module_mm
    if settings.orient_mark == "triangle":
        pg.triangle(p.x_mm, p.y_mm, TRI_LEG_MODULES * module, TRI_GREY)
    if settings.id_mark != "border":
        return
    spec = board_spec(item)
    cx = p.marker_x_mm + p.extent_w_mm / 2.0
    cy = p.marker_y_mm + p.extent_h_mm / 2.0
    if item.layout == "charuco":
        sq = float(item.square_length_m) * 1000.0
        col = 0 if aruco_board._charuco_black(0, 0, item.rows, item.legacy) else 1
        x0 = p.marker_x_mm + col * sq
        ids = aruco_board.ids(spec)
        lines = ["#%d-%d" % (ids[0], ids[-1]), "%dx%d" % (item.cols, item.rows)]
        if settings.top_label and item.top_label:
            lines.append(item.top_label)
        size = min(0.22 * sq / HELVETICA_CAP * MM_TO_PT,
                   min(0.8 * sq / max(text_width_mm(t, 1.0), 1e-9) for t in lines))
        cap = size / MM_TO_PT * HELVETICA_CAP
        n = len(lines)
        for k, t in enumerate(lines):
            pg.text(x0 + sq / 2.0,
                    p.marker_y_mm + sq / 2.0 + (k - (n - 1) / 2.0) * 1.6 * cap + cap / 2.0,
                    t, size, "center", grey=CHARUCO_LABEL_GREY)
        return
    first = True
    for mid, corners in sorted(aruco_board.marker_corners_m(spec).items()):
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        left = cx + min(xs) * 1000.0
        length = (max(xs) - min(xs)) * 1000.0
        bottom = cy - min(ys) * 1000.0          # +y up in metres -> page y down
        top = cy - max(ys) * 1000.0
        _border_text(pg, "#%d" % mid, left, bottom, length, module)
        # the part name once per target: the single marker, or the board's
        # first (top-left) marker
        if first and settings.top_label and item.top_label:
            _border_text(pg, item.top_label, left, top, length, module, row="top",
                         min_cap_mm=MIN_CAP_MM)
        first = False


def _draw_ruler(pg: _Page, ruler: dict):
    top = ruler["top"]
    x0 = ruler["mm_bar"][0]
    pg.text(x0, top + 2.5, "Print at 100% / Actual size — this bar must "
            "measure 100 mm", 7)
    pg.text(x0, top + 5.0, "Sizes are the black square's side (the length a "
            "detector multiplies by). Cut on the grey lines.", 5.5)
    tick_w = 0.25
    # 100 mm bar, ticks up every 10 mm (long) and 5 mm (short), labels above.
    # Nothing is drawn on the bars' own rows, so a scanline through a bar
    # measures exactly the bar (tools/verify_aruco_output.py does).
    bx, by, bw, bh = ruler["mm_bar"]
    rects = [(bx, by, bw, bh)]
    for k in range(0, 21):
        pos = bx + 5.0 * k
        length = 1.6 if k % 2 == 0 else 0.8
        tx = min(max(pos - tick_w / 2, bx), bx + bw - tick_w)
        rects.append((tx, by - length, tick_w, length))
        if k % 2 == 0:
            label = "100 mm" if k == 20 else str(5 * k)
            align = "left" if k == 0 else ("right" if k == 20 else "center")
            pg.text(pos, by - 2.2, label, 5, align)
    # 4 in bar, ticks down every 1 in / 1/2 in / 1/4 in, labels below.
    ix, iy, iw, ih = ruler["in_bar"]
    rects.append((ix, iy, iw, ih))
    for k in range(0, 17):
        pos = ix + 25.4 * k / 4.0
        length = 1.6 if k % 4 == 0 else (1.1 if k % 2 == 0 else 0.6)
        tx = min(max(pos - tick_w / 2, ix), ix + iw - tick_w)
        rects.append((tx, iy + ih, tick_w, length))
        if k % 4 == 0:
            label = "4 in" if k == 16 else str(k // 4)
            align = "left" if k == 0 else ("right" if k == 16 else "center")
            pg.text(pos, iy + ih + 3.7, label, 5, align)
    pg.fill_rects(rects)


def _page_content(layout: SheetLayout, page_index: int, page_total: int,
                  date: str) -> bytes:
    s = layout.settings
    page_w, page_h = layout.page_mm
    pg = _Page(page_h)
    items = layout.pages[page_index] if page_index < len(layout.pages) else []
    for p in items:
        # Black ink: one path of disjoint rectangles, filled once (no seams).
        # black_rects_m is centre-origin, +y up, metres -> page mm, y down.
        cx = p.marker_x_mm + p.extent_w_mm / 2.0
        cy = p.marker_y_mm + p.extent_h_mm / 2.0
        cells = [(cx + x0 * 1000.0, cy - y1 * 1000.0, (x1 - x0) * 1000.0, (y1 - y0) * 1000.0)
                 for x0, y0, x1, y1 in aruco_board.black_rects_m(board_spec(p.item))]
        pg.fill_rects(cells)
        if p.item.marks == "cad":
            # the CAD's own label and corner mark, pure black / white, in
            # order; nothing of the sheet's own on the sticker
            for colour, poly in p.item.ink:
                pg.fill_poly([(cx + float(x), cy - float(y)) for x, y in poly],
                             INK_COLOURS[colour])
            if s.cut_marks:
                # the line OUTSIDE the sticker: its inner edge is the cut, so
                # no grey lands on a board drawn to its edge (quiet zone 0)
                if p.item.outline_mm is not None:
                    edge = [(cx + float(x), cy - float(y)) for x, y in p.item.outline_mm]
                else:
                    x0, y0 = p.x_mm, p.y_mm
                    x1, y1 = x0 + p.sticker_w_mm, y0 + p.sticker_h_mm
                    edge = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                pg.stroke_poly(offset_polygon(edge, CUT_LINE_MM / 2.0), CUT_GREY, CUT_LINE_MM)
        else:
            _marks(pg, p, s)
            if s.cut_marks:
                pg.stroke_rect(p.x_mm, p.y_mm, p.sticker_w_mm, p.sticker_h_mm,
                               CUT_GREY, CUT_LINE_MM)
        if p.label_box is not None:
            bx, by, bw, _ = p.label_box
            line_mm = p.label_font_pt * LABEL_LEADING / MM_TO_PT
            for k, line in enumerate(p.label_lines):
                baseline = (by + LABEL_GAP_MM + k * line_mm
                            + 0.9 * p.label_font_pt / MM_TO_PT)
                pg.text(bx + bw / 2.0, baseline, line, p.label_font_pt, "center")
    if layout.ruler is not None:
        _draw_ruler(pg, layout.ruler)
    m = float(s.margin_mm)
    base = page_h - m - 1.0
    title = s.title or "ArUco marker sheet"
    pg.text(m, base, "%s · %s" % (title, date), FOOTER_FONT_PT)
    pg.text(page_w - m, base, "page %d/%d" % (page_index + 1, page_total),
            FOOTER_FONT_PT, "right")
    if layout.rejected:
        pg.text(page_w / 2.0, base, "%d marker(s) NOT printed — see the "
                "layout report" % len(layout.rejected), FOOTER_FONT_PT, "center")
    if not layout.pages:
        pg.text(m, m + 5, "No markers placed.", 9)
    return "\n".join(pg.ops).encode("ascii")


def _utf16_hex(text: str) -> str:
    return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


# The print copy's document JavaScript (Acrobat's Doc.print; Chrome's and
# Edge's viewers, pdf.js and Acrobat run it when the file opens): the print
# dialog with its own UI, never silent, never shrunk to fit.
PRINT_DIALOG_JS = "this.print({bUI: true, bSilent: false, bShrinkToFit: false});"


def render_layout_pdf(layout: SheetLayout, date: Optional[str] = None,
                      print_dialog: bool = False) -> bytes:
    """PDF 1.4 bytes for an existing layout (one page per layout page, and a
    single page when nothing was placed).

    The catalog asks for /PrintScaling /None (the viewer's print dialog
    starts at Actual size, not "fit"). `print_dialog`: the copy that opens
    the print dialog when it is opened (PRINT_DIALOG_JS) -- the dialog
    shows, nothing prints until the user presses Print; a viewer without
    PDF JavaScript only shows the sheet."""
    date = date or datetime.date.today().isoformat()
    page_w, page_h = layout.page_mm
    total = max(1, layout.page_count)
    objects: List[bytes] = []          # objects[i] is object number i + 1

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add(b"")                                                    # 1: Catalog, below
    add(b"")                                                    # 2: Pages, below
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               b"/Encoding /WinAnsiEncoding >>")
    title = layout.settings.title or "ArUco marker sheet"
    info = add(("<< /Title %s /Producer (bam_cad_core.print_sheet) >>"
                % _utf16_hex(title)).encode("ascii"))
    media = "[0 0 %s %s]" % (_n(page_w * MM_TO_PT), _n(page_h * MM_TO_PT))
    kids = []
    for i in range(total):
        stream = zlib.compress(_page_content(layout, i, total, date), 9)
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n"
                      % len(stream) + stream + b"\nendstream")
        kids.append(add(("<< /Type /Page /Parent 2 0 R /MediaBox %s "
                         "/Resources << /Font << /F1 %d 0 R >> >> "
                         "/Contents %d 0 R >>" % (media, font, content)).encode("ascii")))
    objects[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                  % (" ".join("%d 0 R" % k for k in kids), len(kids))).encode("ascii")
    names = b""
    if print_dialog:
        js = add(("<< /Type /Action /S /JavaScript /JS %s >>"
                  % pdf_string(PRINT_DIALOG_JS)).encode("ascii"))
        names = b" /Names << /JavaScript << /Names [(print) %d 0 R] >> >>" % js
    # /Version: PrintScaling is PDF 1.6; the catalog's version overrides the
    # header's (PDF 1.4 section 3.6.1), and nothing else here is past 1.4
    objects[0] = (b"<< /Type /Catalog /Version /1.6 /Pages 2 0 R "
                  b"/ViewerPreferences << /PrintScaling /None >>" + names + b" >>")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, info, xref))
    return bytes(out)


def render_pdf(items: List[PrintItem], settings: Optional[SheetSettings] = None) -> bytes:
    """Lay out `items` (see layout_sheet) and return the sheet as PDF bytes.
    Rejected items are not drawn; the footer says how many, and
    layout_sheet / layout_summary say which and why."""
    return render_layout_pdf(layout_sheet(items, settings or SheetSettings()))


# =================================================================== the sticker sheet
#
# ArUco Studio M6a (not REF's; docs/design/M6_stickers_profiles_print.md f):
# the sheet drawn from the PLAN. Each item is a sticker with its cut polygon
# (`outline_mm`) and its black (`ink_mm`), both in its own frame (mm, y up);
# the sheet draws exactly that ink, the cut lines (the outline and every
# hole, grey CUT_GREY, CUT_LINE_MM), and none of REF's own marks. Two modes:
#
#   spaced  gap_mm between cells, the caption under each sticker, crop marks
#           at each sticker's corners (outside it); first-fit-decreasing
#           shelves (layout_sheet's rule)
#   tight   gap 0: guillotine shelves -- items sorted by (height, width),
#           identical sizes adjacent; one shelf per height; a shelf is a
#           full-width straight cut and its columns are straight cuts. No
#           captions; one line per shelf in the left margin
#
# An item is packed by the box of its outline, turned 90 degrees when only
# that fits, never scaled: too big for the page is REJECTED with a reason.
# Never mirrored: the sheet shows the sticker as seen from above.
# The PDF and the SVG are drawn from ONE list of page operations, so their
# numbers are the same.

CROP_MM = 2.0                  # a crop mark's length (spaced), outside the corner
CROP_OFF_MM = 0.5              # its gap from the corner
PUNCH_MM = 3.0                 # a hole under this gets a cross (a punch, not scissors)
SHELF_FONT_PT = 5.0
MODES = ("spaced", "tight")


@dataclass
class StickerPlace:
    item: PrintItem
    page: int                       # 0-based
    x_mm: float                     # the box's top-left on the page (y down)
    y_mm: float
    w_mm: float                     # the box as placed (after the turn)
    h_mm: float
    rotation: int                   # 0 or 90 (counter-clockwise, seen from above)
    box: Tuple[float, float, float, float]       # the box in the sticker's frame, unturned
    shelf: int = -1
    caption_lines: List[str] = field(default_factory=list)
    caption_pt: float = LABEL_FONT_PT

    @property
    def origin(self) -> Tuple[float, float]:
        """Where the sticker frame's (0, 0) lands on the page (mm, y down)."""
        u0, _v0, _u1, v1 = _turn_box(self.box, self.rotation)
        return (self.x_mm - u0, self.y_mm + v1)

    def to_page(self, u: float, v: float) -> Tuple[float, float]:
        """A point of the sticker's frame (mm, y up) on the page (mm, y down)."""
        ru, rv = _turn(u, v, self.rotation)
        ox, oy = self.origin
        return (ox + ru, oy - rv)


@dataclass
class StickerLayout:
    settings: SheetSettings
    page_mm: Tuple[float, float]
    printable_mm: Tuple[float, float, float, float]
    pages: List[List[StickerPlace]]
    rejected: List[RejectedItem]
    ruler: Optional[dict]
    warnings: List[str]
    shelves: List[dict]             # tight and spaced: {page, y, h, x0, x1, keys}

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def placed(self) -> List[StickerPlace]:
        return [p for page in self.pages for p in page]

    def cuts(self) -> int:
        """Straight cuts to free every sticker (tight: shelves stacked, so a
        page of k shelves has k + 1 long cuts; a shelf of c stickers c + 1
        short ones). Spaced (audit nit A6, 2026-10-17): a guillotine count on
        each page -- every straight cut that crosses no sticker, across the
        piece it is made in, so stickers in line share one (four 30 mm
        stickers in a row: 10, not 4 per sticker = 16)."""
        if self.settings.mode != "tight":
            n = 0
            for pi, page in enumerate(self.pages):
                rects = [(p.x_mm, p.y_mm, p.x_mm + p.w_mm, p.y_mm + p.h_mm) for p in page]
                page_box = (0.0, 0.0) + tuple(self.page_mm)
                n += min(_guillotine(rects, page_box, 0), _guillotine(rects, page_box, 1))
            return n
        n = 0
        for pi in range(len(self.pages)):
            sh = [s for s in self.shelves if s["page"] == pi]
            if sh:
                n += len(sh) + 1 + sum(len(s["keys"]) + 1 for s in sh)
        return n


_CUT_TOL = 1e-6


def _guillotine(rects, region, axis) -> int:
    """The straight cuts that free each rect of `rects` (page mm, x0 y0 x1
    y1) from `region`: along `axis` (0: cuts across y, 1: across x) every
    edge line that crosses no rect is one cut through the region; each
    piece is then cut along the other axis. A rect alone takes a cut per
    side not already on the piece's edge. When neither axis has a cut
    (stickers that interlock), four per sticker, as before."""
    if not rects:
        return 0
    if len(rects) == 1:
        r = rects[0]
        return sum(1 for a, b in zip(r, region) if abs(a - b) > _CUT_TOL)
    for ax in (axis, 1 - axis):
        lo, hi = (1, 3) if ax == 0 else (0, 2)
        cs = sorted({c for r in rects for c in (r[lo], r[hi])
                     if region[lo] + _CUT_TOL < c < region[hi] - _CUT_TOL})
        cs = [c for c in cs if not any(r[lo] + _CUT_TOL < c < r[hi] - _CUT_TOL for r in rects)]
        if not cs:
            continue
        n = len(cs)
        bounds = [region[lo]] + cs + [region[hi]]
        for a, b in zip(bounds, bounds[1:]):
            sub = [r for r in rects if r[lo] >= a - _CUT_TOL and r[hi] <= b + _CUT_TOL]
            piece = list(region)
            piece[lo], piece[hi] = a, b
            n += _guillotine(sub, tuple(piece), 1 - ax)
        return n
    return 4 * len(rects)


def _turn(u, v, rot):
    return (u, v) if not rot else (-v, u)


def _turn_box(box, rot):
    u0, v0, u1, v1 = box
    if not rot:
        return box
    pts = [_turn(u, v, rot) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    us = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    return (min(us), min(vs), max(us), max(vs))


def _loop_box(lp):
    us = [float(p[0]) for p in lp]
    vs = [float(p[1]) for p in lp]
    return (min(us), min(vs), max(us), max(vs))


def default_outline(item: PrintItem) -> dict:
    """REF's sticker as a cut polygon: the pattern + its quiet zone."""
    info = aruco_dict.dictionary_info(item.dictionary)
    ew, eh = (v * 1000.0 for v in aruco_board.extent_m(board_spec(item)))
    q = float(item.quiet_modules) * float(item.marker_length_m) * 1000.0 / info["modules"]
    w, h = ew / 2.0 + q, eh / 2.0 + q
    return {"outer": [[-w, -h], [w, -h], [w, h], [-w, h]], "holes": []}


def default_ink(item: PrintItem) -> list:
    """REF's black (aruco_board.black_rects_m) as polygons, mm, y up."""
    out = []
    for x0, y0, x1, y1 in aruco_board.black_rects_m(board_spec(item)):
        a, b, c, d = x0 * 1000.0, y0 * 1000.0, x1 * 1000.0, y1 * 1000.0
        out.append([[[a, b], [c, b], [c, d], [a, d]]])
    return out


def outline_of(item: PrintItem) -> dict:
    return item.cut_mm if item.cut_mm else default_outline(item)


def ink_of(item: PrintItem) -> list:
    return item.ink_mm if item.ink_mm is not None else default_ink(item)


def _caption(item: PrintItem, width: float, settings: SheetSettings):
    if settings.mode == "tight" or not settings.labels:
        return [], LABEL_FONT_PT, 0.0
    text = item.caption or (identity_label(item) + (f" · {item.name}" if item.name else ""))
    lines = [text]
    font = LABEL_FONT_PT
    wd = text_width_mm(text, font)
    if wd > width:
        font = max(LABEL_MIN_FONT_PT, LABEL_FONT_PT * width / wd)
    lines = [_fit_text(t, font, max(width, 20.0)) for t in lines]
    return lines, font, LABEL_GAP_MM + len(lines) * font * LABEL_LEADING / MM_TO_PT


def _area(settings: SheetSettings):
    """(page w, h, x0, y0, area w, area h, ruler, warnings): layout_sheet's."""
    page_w, page_h = page_size_mm(settings)
    m = float(settings.margin_mm)
    gap = float(settings.gap_mm)
    if m < 0 or gap < 0:
        raise ValueError("margin_mm and gap_mm must be >= 0")
    warnings: List[str] = []
    x0, y0 = m, m
    area_w = page_w - 2 * m
    footer_top = page_h - m - FOOTER_H_MM
    ruler = None
    area_bottom = footer_top - BAND_GAP_MM
    if settings.ruler:
        if area_w + _EPS >= RULER_W_MM:
            top = footer_top - RULER_H_MM
            ruler = {"top": top, "mm_bar": (x0, top + 10.5, 100.0, 1.2),
                     "in_bar": (x0, top + 13.3, 101.6, 1.2)}
            area_bottom = top - BAND_GAP_MM
        else:
            warnings.append("page is %.1f mm wide inside the margins; the scale ruler needs "
                            "%.0f mm and was left off -- check the print scale another way"
                            % (area_w, RULER_W_MM))
    area_h = area_bottom - y0
    if area_w <= 0 or area_h <= 0:
        raise ValueError("margins and ruler leave no printable area on a %.1f x %.1f mm page"
                         % (page_w, page_h))
    return page_w, page_h, x0, y0, area_w, area_h, ruler, warnings


def printable_options(page: str = "letter", margin_mm: float = 10.0) -> dict:
    """The printable area of `page` less `margin_mm` (and the footer and the
    scale bars' band): what layout_stickers places stickers in, on a
    portrait and on a landscape sheet. -> {"portrait": (w, h), "landscape":
    (w, h)} mm (an orientation with no room: absent). ArUco Studio, not
    REF's: the page lint of a rule-2 sticker (core.make.page_fit, CF-6)."""
    out = {}
    for name, land in (("portrait", False), ("landscape", True)):
        try:
            _pw, _ph, _x0, _y0, aw, ah, _r_, _w = _area(SheetSettings(
                page=page, landscape=land, margin_mm=float(margin_mm)))
        except ValueError:
            continue
        out[name] = (float(aw), float(ah))
    return out


def fit_area(w_mm: float, h_mm: float, opts: dict, page: str = "letter",
             margin_mm: float = 10.0) -> dict:
    """Does a w x h sticker fit one of `opts` (printable_options), as it is
    or turned? -> {"fits", "how" ("portrait" / "portrait, turned" /
    "landscape" / "landscape, turned" / None), "over_mm" [dw, dh] (the
    least over, for the best way round), "worst_mm", "area_mm" (the
    portrait area, the words'), "page", "margin_mm"}."""
    best = None
    for name in ("portrait", "landscape"):
        if name not in opts:
            continue
        aw, ah = opts[name]
        for turned, (a, b) in ((False, (w_mm, h_mm)), (True, (h_mm, w_mm))):
            over = (max(0.0, a - aw), max(0.0, b - ah))
            worst = max(over)
            how = name + (", turned" if turned else "")
            if best is None or worst < best[0] - 1e-9:
                best = (worst, how, over, (aw, ah))
    if best is None:
        return {"fits": False, "how": None, "over_mm": [w_mm, h_mm], "worst_mm": max(w_mm, h_mm),
                "area_mm": [0.0, 0.0], "page": page, "margin_mm": float(margin_mm)}
    worst, how, over, _area_used = best
    area = opts.get("portrait") or opts.get("landscape")
    fits = worst <= _EPS
    return {"fits": fits, "how": how if fits else None,
            "over_mm": [round(over[0], 4), round(over[1], 4)], "worst_mm": round(worst, 4),
            "area_mm": [round(area[0], 4), round(area[1], 4)], "page": page,
            "margin_mm": float(margin_mm)}


def grown_outline(outline: dict, d: float) -> dict:
    """A sticker's cut polygon with `d` mm of white paper round it (the
    sheet's Sticker margin, Zach's Q7): the outer loop grown by d (mitred,
    offset_polygon), the holes as they are (they sit over the part's own)."""
    if not d or d <= 0:
        return outline
    outer = [list(p) for p in offset_polygon([tuple(map(float, q)) for q in outline["outer"]],
                                             float(d))]
    return {"outer": outer, "holes": [[list(q) for q in h] for h in outline.get("holes", [])]}


def layout_stickers(items: List[PrintItem], settings: Optional[SheetSettings] = None
                    ) -> StickerLayout:
    """Place every sticker at its exact size (spaced or tight), or reject it
    with a reason. Deterministic for a given input. A Sticker margin
    (`sticker_margin_mm`) grows each sticker's cut outline first, so what is
    placed, drawn and written to sheet.json is the sticker as it is cut."""
    settings = settings or SheetSettings()
    sm = float(getattr(settings, "sticker_margin_mm", 0.0) or 0.0)
    if sm > 0:
        import dataclasses
        items = [dataclasses.replace(it, cut_mm=grown_outline(outline_of(it), sm))
                 for it in items]
    mode = settings.mode if settings.mode in MODES else "spaced"
    tight = mode == "tight"
    page_w, page_h, x0, y0, area_w, area_h, ruler, warnings = _area(settings)
    if settings.mode not in MODES:
        warnings.append("sheet mode %r: spaced" % (settings.mode,))
    gap = 0.0 if tight else float(settings.gap_mm)
    prepared, rejected = [], []
    for index, item in enumerate(items):
        try:
            info = aruco_dict.dictionary_info(item.dictionary)
            if not (isinstance(item.marker_length_m, (int, float)) and item.marker_length_m > 0):
                raise ValueError("marker_length_m must be > 0 (got %r)" % (item.marker_length_m,))
            box = _loop_box(outline_of(item)["outer"])
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            rejected.append(RejectedItem(item, str(exc)))
            continue
        w, h = box[2] - box[0], box[3] - box[1]
        rot = 0
        if (w > area_w + _EPS or h > area_h + _EPS) and h <= area_w + _EPS and w <= area_h + _EPS:
            rot = 90                                  # longer than the page: it turns
        bw, bh = (h, w) if rot else (w, h)
        lines, font, cap_h = _caption(item, bw, settings)
        if bw > area_w + _EPS or bh + cap_h > area_h + _EPS:
            rejected.append(RejectedItem(item, (
                "sticker is %.1f x %.1f mm but the printable area is %.1f x %.1f mm -- markers "
                "are never scaled to fit; use a larger page, landscape or smaller margins"
                % (w, h, area_w, area_h))))
            continue
        module = float(item.marker_length_m) * 1000.0 / info["modules"]
        if module < SMALL_MODULE_MM:
            warnings.append("%s: module is %.2f mm -- below ~%.1f mm many printers blur the "
                            "cells" % (item.key, module, SMALL_MODULE_MM))
        prepared.append({"index": index, "item": item, "box": box, "rot": rot, "w": bw,
                         "h": bh, "cell_w": max(bw, max([text_width_mm(t, font) for t in lines],
                                                        default=0.0) if lines else bw),
                         "cell_h": bh + cap_h, "lines": lines, "font": font})
    if tight:
        prepared.sort(key=lambda p: (-round(p["h"], 6), -round(p["w"], 6), p["index"]))
    else:
        prepared.sort(key=lambda p: (-p["h"], -p["w"], -p["cell_h"], p["index"]))
    x1, y1 = x0 + area_w, y0 + area_h
    shelves: List[dict] = []
    next_y: List[float] = []
    pages: List[List[StickerPlace]] = []
    for p in prepared:
        spot = None
        for sh in shelves:
            same_h = abs(sh["h"] - p["cell_h"]) <= 1e-6 if tight else p["cell_h"] <= sh["h"] + _EPS
            if same_h and sh["x1"] + p["cell_w"] <= x1 + _EPS:
                spot = (sh["page"], sh["x1"], sh["y"], sh)
                break
        if spot is None:
            for pi, y in enumerate(next_y):
                if y + p["cell_h"] <= y1 + _EPS:
                    spot = (pi, x0, y, None)
                    break
            if spot is None:
                pages.append([])
                next_y.append(y0)
                spot = (len(pages) - 1, x0, y0, None)
            sh = {"page": spot[0], "y": spot[2], "h": p["cell_h"], "x0": x0, "x1": x0,
                  "keys": [], "index": len(shelves)}
            shelves.append(sh)
            next_y[spot[0]] = spot[2] + p["cell_h"] + gap
            spot = (spot[0], x0, spot[2], sh)
        pi, cx, cy, sh = spot
        sx = cx + (p["cell_w"] - p["w"]) / 2.0
        sh["x1"] = cx + p["cell_w"] + gap
        sh["keys"].append(p["item"].key)
        pages[pi].append(StickerPlace(item=p["item"], page=pi, x_mm=sx, y_mm=cy, w_mm=p["w"],
                                      h_mm=p["h"], rotation=p["rot"], box=p["box"],
                                      shelf=sh["index"], caption_lines=p["lines"],
                                      caption_pt=p["font"]))
    for page in pages:
        page.sort(key=lambda q: (q.y_mm, q.x_mm))
    for sh in shelves:
        sh["x1"] = sh["x1"] - gap if sh["keys"] else sh["x1"]
    return StickerLayout(settings=settings, page_mm=(page_w, page_h),
                         printable_mm=(x0, y0, area_w, area_h), pages=pages, rejected=rejected,
                         ruler=ruler, warnings=warnings, shelves=shelves)


def _r4(v):
    return round(float(v), 4) + 0.0


def place_outline(p: StickerPlace) -> dict:
    """The cut polygon of a placed sticker on the page (mm, y down)."""
    o = outline_of(p.item)
    return {"outer": [list(map(_r4, p.to_page(u, v))) for u, v in o["outer"]],
            "holes": [[list(map(_r4, p.to_page(u, v))) for u, v in h] for h in o.get("holes", [])]}


def sticker_summary(layout: StickerLayout) -> dict:
    """sheet.json: the layout, and per sticker its page, place, turn, outline,
    made by, name and ids -- the WYSIWYG test's oracle (page mm, y down,
    page numbers 1-based)."""
    s = layout.settings
    x, y, w, h = layout.printable_mm
    extra = {}
    if float(getattr(s, "sticker_margin_mm", 0.0) or 0.0) > 0:
        extra["sticker_margin_mm"] = _r4(s.sticker_margin_mm)     # outline_mm is the grown one
    if not s.cut_marks:
        extra["cut_lines"] = False
    return {
        **extra,
        "schema": "arucostudio.sheet/1", "mode": s.mode, "page": s.page,
        "page_mm": [_r4(layout.page_mm[0]), _r4(layout.page_mm[1])],
        "landscape": bool(s.landscape), "margin_mm": _r4(s.margin_mm),
        "printable_mm": {"x": _r4(x), "y": _r4(y), "w": _r4(w), "h": _r4(h)},
        "origin": "page top-left, y down, millimetres", "scale": 1.0,
        "pages": layout.page_count, "cuts": layout.cuts(),
        "stickers": [{
            "key": p.item.key, "name": p.item.name, "made_by": p.item.made_by or "sticker",
            "dictionary": p.item.dictionary, "layout": p.item.layout,
            "ids": list(p.item.ids) or [p.item.marker_id],
            "marker_length_mm": _r4(p.item.marker_length_m * 1000.0),
            "page": p.page + 1, "x_mm": _r4(p.x_mm), "y_mm": _r4(p.y_mm), "w_mm": _r4(p.w_mm),
            "h_mm": _r4(p.h_mm), "rotation": p.rotation, "box_mm": [_r4(v) for v in p.box],
            "origin_mm": [_r4(v) for v in p.origin], "shelf": p.shelf,
            "outline_mm": outline_of(p.item), "outline_page_mm": place_outline(p),
            "caption": list(p.caption_lines)} for p in layout.placed],
        "shelves": [{"page": sh["page"] + 1, "y_mm": _r4(sh["y"]), "h_mm": _r4(sh["h"]),
                     "x0_mm": _r4(sh["x0"]), "x1_mm": _r4(sh["x1"]), "keys": list(sh["keys"])}
                    for sh in layout.shelves],
        "rejected": [{"key": r.item.key, "name": r.item.name, "reason": r.reason}
                     for r in layout.rejected],
        "ruler": None if layout.ruler is None else {
            k: ([_r4(v) for v in val] if isinstance(val, tuple) else _r4(val))
            for k, val in layout.ruler.items()},
        "warnings": list(layout.warnings),
    }


class _Ops:
    """A page as a list of drawing operations (mm, top-left origin, y down):
    the PDF and the SVG are both written from it. It has _Page's methods, so
    REF's _draw_ruler draws into it."""

    def __init__(self, page_h_mm: float):
        self.h = page_h_mm
        self.ops: List[tuple] = []

    def fill_rects(self, rects, grey=0.0):
        if rects:
            self.ops.append(("rects", [tuple(map(float, r)) for r in rects], float(grey)))

    def text(self, x, baseline_y, s, size, align="left", grey=0.0):
        self.ops.append(("text", float(x), float(baseline_y), str(s), float(size), align,
                         float(grey), 0))

    def text_up(self, x, baseline_y, s, size, grey=0.0):
        """Text reading upwards (turned 90 degrees), starting at (x, y)."""
        self.ops.append(("text", float(x), float(baseline_y), str(s), float(size), "left",
                         float(grey), 90))

    def fill_polys(self, polys, grey=0.0):
        """Polygons with holes (lists of loops), even-odd, filled."""
        if polys:
            self.ops.append(("fill", [[[tuple(map(float, q)) for q in lp] for lp in poly]
                                      for poly in polys], float(grey)))

    def stroke_loops(self, loops, grey, width_mm, key=""):
        if loops:
            self.ops.append(("loops", [[tuple(map(float, q)) for q in lp] for lp in loops],
                             float(grey), float(width_mm), key))

    def line(self, x0, y0, x1, y1, grey, width_mm):
        self.ops.append(("line", float(x0), float(y0), float(x1), float(y1), float(grey),
                         float(width_mm)))

    def sticker(self, p: StickerPlace):
        self.ops.append(("sticker", p))


def _draw_sticker(pg: _Ops, p: StickerPlace, s: SheetSettings):
    item = p.item
    pg.sticker(p)
    ink = [[[p.to_page(u, v) for u, v in lp] for lp in poly] for poly in ink_of(item)]
    pg.fill_polys(ink, 0.0)
    o = outline_of(item)
    loops = [[p.to_page(u, v) for u, v in o["outer"]]]
    loops += [[p.to_page(u, v) for u, v in hl] for hl in o.get("holes", [])]
    if s.cut_marks:
        pg.stroke_loops(loops, CUT_GREY, CUT_LINE_MM, key=item.key)
        for hl in loops[1:]:
            b = _loop_box(hl)
            d = max(b[2] - b[0], b[3] - b[1])
            if d < PUNCH_MM:
                cx, cy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
                pg.line(cx - d / 2.0, cy, cx + d / 2.0, cy, CUT_GREY, CUT_LINE_MM)
                pg.line(cx, cy - d / 2.0, cx, cy + d / 2.0, CUT_GREY, CUT_LINE_MM)
    if s.mode != "tight":
        if s.cut_marks:
            L = min(CROP_MM, max(0.0, float(s.gap_mm) / 2.0 - CROP_OFF_MM))
            if L > 0:
                x0, y0, x1, y1 = p.x_mm, p.y_mm, p.x_mm + p.w_mm, p.y_mm + p.h_mm
                for cx, cy, sx, sy in ((x0, y0, -1, -1), (x1, y0, 1, -1), (x1, y1, 1, 1),
                                       (x0, y1, -1, 1)):
                    pg.line(cx + sx * CROP_OFF_MM, cy, cx + sx * (CROP_OFF_MM + L), cy,
                            CUT_GREY, CUT_LINE_MM)
                    pg.line(cx, cy + sy * CROP_OFF_MM, cx, cy + sy * (CROP_OFF_MM + L),
                            CUT_GREY, CUT_LINE_MM)
        line_mm = p.caption_pt * LABEL_LEADING / MM_TO_PT
        for k, t in enumerate(p.caption_lines):
            base = p.y_mm + p.h_mm + LABEL_GAP_MM + k * line_mm + 0.9 * p.caption_pt / MM_TO_PT
            pg.text(p.x_mm + p.w_mm / 2.0, base, t, p.caption_pt, "center")


def _shelf_words(layout: StickerLayout, sh: dict) -> str:
    by = {p.item.key: p.item for p in layout.placed}
    ids = []
    names = []
    for k in sh["keys"]:
        it = by[k]
        ids += list(it.ids) or [it.marker_id]
        if it.name and it.name not in names:
            names.append(it.name)
    idw = ("#%d" % ids[0]) if len(ids) == 1 else ("#%d-%d" % (min(ids), max(ids)))
    return "row %d: %s %s" % (sh["index"] + 1, idw, " ".join(names[:3])
                              + (" ..." if len(names) > 3 else ""))


def sticker_page_ops(layout: StickerLayout, page_index: int, date: str) -> _Ops:
    s = layout.settings
    page_w, page_h = layout.page_mm
    total = max(1, layout.page_count)
    pg = _Ops(page_h)
    items = layout.pages[page_index] if page_index < len(layout.pages) else []
    for p in items:
        _draw_sticker(pg, p, s)
    if s.mode == "tight":
        for sh in layout.shelves:
            if sh["page"] != page_index:
                continue
            words = _fit_text(_shelf_words(layout, sh), SHELF_FONT_PT, max(sh["h"] - 1.0, 3.0))
            x = max(1.5, float(s.margin_mm) - 2.0)
            pg.text_up(x, sh["y"] + sh["h"] - 0.5, words, SHELF_FONT_PT, grey=0.3)
    if layout.ruler is not None:
        _draw_ruler(pg, layout.ruler)
    m = float(s.margin_mm)
    base = page_h - m - 1.0
    title = s.title or "ArUco sticker sheet"
    pg.text(m, base, "%s · %s · %s" % (title, s.mode, date), FOOTER_FONT_PT)
    pg.text(page_w - m, base, "page %d/%d" % (page_index + 1, total), FOOTER_FONT_PT, "right")
    if layout.rejected:
        pg.text(page_w / 2.0, base, "%d sticker(s) NOT printed -- see sheet.json"
                % len(layout.rejected), FOOTER_FONT_PT, "center")
    if not layout.pages:
        pg.text(m, m + 5, "No stickers placed.", 9)
    return pg


def _pdf_ops(pg: _Ops) -> bytes:
    """_Ops -> a PDF content stream (points, bottom-left origin)."""
    H = pg.h
    out: List[str] = []

    def P(x, y):
        return "%s %s" % (_n(x * MM_TO_PT), _n((H - y) * MM_TO_PT))
    for op in pg.ops:
        kind = op[0]
        if kind == "rects":
            out.append("%s g" % _n(op[2]))
            for x, y, w, h in op[1]:
                out.append("%s %s %s %s re" % (_n(x * MM_TO_PT), _n((H - y - h) * MM_TO_PT),
                                               _n(w * MM_TO_PT), _n(h * MM_TO_PT)))
            out.append("f")
        elif kind == "fill":
            out.append("%s g" % _n(op[2]))
            for poly in op[1]:
                for lp in poly:
                    if len(lp) < 3:
                        continue
                    out.append("%s m" % P(*lp[0]))
                    out.extend("%s l" % P(*q) for q in lp[1:])
                    out.append("h")
            out.append("f*")
        elif kind == "loops":
            out.append("%s G %s w" % (_n(op[2]), _n(op[3] * MM_TO_PT)))
            for lp in op[1]:
                if len(lp) < 2:
                    continue
                out.append("%s m" % P(*lp[0]))
                out.extend("%s l" % P(*q) for q in lp[1:])
                out.append("h")
            out.append("S")
        elif kind == "line":
            out.append("%s G %s w %s m %s l S" % (_n(op[5]), _n(op[6] * MM_TO_PT), P(op[1], op[2]),
                                                 P(op[3], op[4])))
        elif kind == "text":
            _k, x, y, txt, size, align, grey, rot = op
            if rot:
                out.append("BT /F1 %s Tf %s g 0 1 -1 0 %s Tm %s Tj ET"
                           % (_n(size), _n(grey), P(x, y), pdf_string(txt)))
                continue
            if align != "left":
                wd = text_width_mm(txt, size)
                x -= wd / 2.0 if align == "center" else wd
            out.append("BT /F1 %s Tf %s g %s Td %s Tj ET" % (_n(size), _n(grey), P(x, y),
                                                            pdf_string(txt)))
    return "\n".join(out).encode("ascii")


def _pdf_doc(pages: List[bytes], page_mm, title: str) -> bytes:
    """PDF 1.4 bytes from page content streams (render_layout_pdf's file)."""
    page_w, page_h = page_mm
    objects: List[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)
    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               b"/Encoding /WinAnsiEncoding >>")
    info = add(("<< /Title %s /Producer (aruco_studio.core.sheet) >>"
                % _utf16_hex(title)).encode("ascii"))
    media = "[0 0 %s %s]" % (_n(page_w * MM_TO_PT), _n(page_h * MM_TO_PT))
    kids = []
    for body in pages:
        stream = zlib.compress(body, 9)
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream
                      + b"\nendstream")
        kids.append(add(("<< /Type /Page /Parent 2 0 R /MediaBox %s "
                         "/Resources << /Font << /F1 %d 0 R >> >> "
                         "/Contents %d 0 R >>" % (media, font, content)).encode("ascii")))
    objects[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>"
                  % (" ".join("%d 0 R" % k for k in kids), len(kids))).encode("ascii")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, info, xref))
    return bytes(out)


def render_sticker_pdf(layout: StickerLayout, date: Optional[str] = None) -> bytes:
    """The sticker sheet as PDF 1.4 (vectors; the MediaBox is the page, so a
    viewer's default scale is 1:1)."""
    date = date or datetime.date.today().isoformat()
    total = max(1, layout.page_count)
    pages = [_pdf_ops(sticker_page_ops(layout, i, date)) for i in range(total)]
    return _pdf_doc(pages, layout.page_mm, layout.settings.title or "ArUco sticker sheet")


def _xml(t: str) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _svg_n(v: float) -> str:
    t = "%.4f" % v
    t = t.rstrip("0").rstrip(".")
    return "0" if t in ("", "-0") else t


def _grey_hex(g: float) -> str:
    c = int(round(max(0.0, min(1.0, g)) * 255))
    return "#%02x%02x%02x" % (c, c, c)


def _svg_ops(pg: _Ops) -> List[str]:
    out: List[str] = []
    for op in pg.ops:
        kind = op[0]
        if kind == "rects":
            d = " ".join("M%s %sh%sv%sh%sz" % (_svg_n(x), _svg_n(y), _svg_n(w), _svg_n(h),
                                               _svg_n(-w)) for x, y, w, h in op[1])
            out.append('<path fill="%s" d="%s"/>' % (_grey_hex(op[2]), d))
        elif kind == "fill":
            d = " ".join("M" + " L".join("%s %s" % (_svg_n(x), _svg_n(y)) for x, y in lp) + " Z"
                         for poly in op[1] for lp in poly if len(lp) >= 3)
            out.append('<path data-ink="1" fill="%s" fill-rule="evenodd" d="%s"/>'
                       % (_grey_hex(op[2]), d))
        elif kind == "loops":
            d = " ".join("M" + " L".join("%s %s" % (_svg_n(x), _svg_n(y)) for x, y in lp) + " Z"
                         for lp in op[1] if len(lp) >= 2)
            out.append('<path data-cut="%s" fill="none" stroke="%s" stroke-width="%s" d="%s"/>'
                       % (_xml(op[4]), _grey_hex(op[2]), _svg_n(op[3]), d))
        elif kind == "line":
            out.append('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>'
                       % (_svg_n(op[1]), _svg_n(op[2]), _svg_n(op[3]), _svg_n(op[4]),
                          _grey_hex(op[5]), _svg_n(op[6])))
        elif kind == "text":
            _k, x, y, txt, size, align, grey, rot = op
            anchor = {"left": "start", "center": "middle", "right": "end"}[align]
            fs = size / MM_TO_PT
            tr = ' transform="rotate(-90 %s %s)"' % (_svg_n(x), _svg_n(y)) if rot else ""
            out.append('<text x="%s" y="%s" font-family="Helvetica, Arial, sans-serif" '
                       'font-size="%s" text-anchor="%s" fill="%s"%s>%s</text>'
                       % (_svg_n(x), _svg_n(y), _svg_n(fs), anchor, _grey_hex(grey), tr,
                          _xml(txt)))
        elif kind == "sticker":
            p = op[1]
            it = p.item
            out.append('<rect data-sticker="%s" data-name="%s" data-made-by="%s" data-page="%d" '
                       'data-x="%s" data-y="%s" data-w="%s" data-h="%s" data-rotation="%d" '
                       'x="%s" y="%s" width="%s" height="%s" fill="none" stroke="none"/>'
                       % (_xml(it.key), _xml(it.name), _xml(it.made_by or "sticker"), p.page + 1,
                          _svg_n(p.x_mm), _svg_n(p.y_mm), _svg_n(p.w_mm), _svg_n(p.h_mm),
                          p.rotation, _svg_n(p.x_mm), _svg_n(p.y_mm), _svg_n(p.w_mm),
                          _svg_n(p.h_mm)))
    return out


SVG_PAGE_GAP_MM = 10.0


def render_sticker_svg(layout: StickerLayout, date: Optional[str] = None) -> str:
    """The same sheet as SVG (mm, y down): one <g data-page> per page,
    stacked with a gap; each sticker's box as an invisible <rect
    data-sticker> (its numbers are sheet.json's)."""
    date = date or datetime.date.today().isoformat()
    page_w, page_h = layout.page_mm
    total = max(1, layout.page_count)
    H = total * page_h + (total - 1) * SVG_PAGE_GAP_MM
    body = []
    for i in range(total):
        oy = i * (page_h + SVG_PAGE_GAP_MM)
        ops = _svg_ops(sticker_page_ops(layout, i, date))
        body.append('<g data-page="%d" transform="translate(0 %s)"><rect width="%s" height="%s" '
                    'fill="#ffffff" stroke="#cccccc" stroke-width="0.2"/>%s</g>'
                    % (i + 1, _svg_n(oy), _svg_n(page_w), _svg_n(page_h), "".join(ops)))
    title = layout.settings.title or "ArUco sticker sheet"
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%smm" height="%smm" '
            'viewBox="0 0 %s %s" data-mode="%s" data-pages="%d"><title>%s</title>%s</svg>'
            % (_svg_n(page_w), _svg_n(H), _svg_n(page_w), _svg_n(H), layout.settings.mode,
               total, _xml(title), "".join(body)))
