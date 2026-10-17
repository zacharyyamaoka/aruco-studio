# Ported from REF CADExporter/bam_cad_core/aruco_label.py at c8216ff:
# copied verbatim, only the package-relative imports renamed.
"""ArUco Extrude's optional LABEL: text printed on the tag (the pure core;
standard library only, it runs inside Fusion).

Zach, 2026-10-09: "Earlier I had said I didn't want a label on the white out
of the quiet space. But actually I can see it can be useful, for example in
this case: I have put it on something that is bigger than just the
rectangle. I would like the option to optionally enable the label, then you
can choose to position it on the black or white. You can choose the size,
although by default it will autocompute it. Then for the label, please have
options to auto-configure it, like put id, put name, etc. Key thing is I
want that label to update! Particularly when we do a batch ArUco id set."

### The rules (docs/proposal_aruco_marks.md, 430,260 simulated photos)

    on the black   white text knocked out of a marker's black border row is
                   free while its cap height is <= 0.5 module, it keeps
                   0.25 module of black to the outer edge and it stays out
                   of the corner cells (`black_id_white` -0.3 pts, n.s.)
    the quiet ring ANY ink in the 1-module white ring costs: -11 pts for a
                   grey id, up to -40 once a printer's dots spread
    on the white   FULL-BLACK text 1.0 module or more from the black is free
                   (2026-10-13, tools/study_aruco_label_gap.py ->
                   reports/media/aruco/marks/gap_black.json, n = 3000 paired
                   trials: 0.5 module -7 pts, 0.7 -1.5 pts, 1.0 and beyond
                   n.s.). So the quiet ring IS the hard rule (WHITE_GAP_MIN
                   beyond it: ink inside is a violation, built only with
                   Build anyway); auto keeps WHITE_GAP_PREF more when it can
                   (print tolerance -- less is no violation, and no note).
                   The 2026-10-07 sweep (`white_q15_id`) used grey text.
    ChArUco        the top-left BLACK square holds a board label for free
                   (`chl_label_more`); bright marks closer than 0.3 square to
                   an inner chessboard corner pull it (the chamfer study)

### ONE label: content, then position (`LabelSettings`)

Zach, 2026-10-09, later: "I want the option to put the name inside the
black strip. Conceptually it's one label object and then the position is a
separate thing." The label is WHAT it says -- one template, "|" between its
lines -- and, apart from that, WHERE it goes (`positions`); any content goes
in any position the tag has. A place that holds one line (a border row)
joins the lines with a space.

### Content (`resolve_text`)

A template with tokens; presets are templates too:

    "id"       "#{id}"            "#12"; a board's own label "#9-12"
    "id_name"  "#{id}|{name}"     "#12" / "ACTUATOR:3" (one row: "#12 ACTUATOR:3")
    "name"     "{name}"
    "dict_id"  "{dict} #{id}"     "4X4_50 #12"
    "custom"   your text          {id} {ids} {name} {key} {dict} {size}; "|" breaks a line

{id} is the marker's own id in a per-marker label (each marker of a grid)
and the target's id block everywhere else; {ids} is always the block.
{name} is the part the geometry belongs to (`instance_name`): a tag's
geometry is shared by every copy of its component, so the template says the
component's name, and a copy rebuilt as its own tag part (an id override,
aruco_tags variants) says its occurrence path below the level that set its
id ("Actuator:3", or "Arm:2/Actuator:3" when the robot set it). Resolution is
a pure function of (spec, name, key): anything that rebuilds a copy rebuilds
its label from the copy's own data -- that is the "label must update" rule
(`relabel`). Text is drawn upper-case; characters the font lacks print "?".

### Position (`plan_label`)

    black   the marker's border rows: "bottom", "top", or "both" (line 1 in
            the bottom row, the rest in the top row: "#12" + "ACTUATOR",
            as the PDF sheet prints them) -- of each marker of a board
            ("each") or of the first one ("first"); a line that reads the
            same on every marker (no {id}: a name) is written once, on the
            first. ChArUco also: the board label in the top-left black
            square ("square"). Row "auto": both rows; a ChArUco board's
            square. Cap <= 0.5 module, 0.25 module of black above and below,
            0.25 module clear of the corner cells, one line per row.
    white   one label for the whole target, outside the detector's clear
            zone (`clear_zones`: the quiet ring + WHITE_GAP_MIN, hard), with
            WHITE_GAP_PREF more when that fits (else the hard line itself),
            on the side asked for, or the side where the biggest text fits
            ("auto"; ties go below, above, right, left). Left reads upward,
            right downward: each side reads upright when it is on top.
            Its white comes from one of two places:
              region  the white around the tag (the user's white body under a
                      Black only tag, or a tile bigger than the sticker), as
                      loops in the pattern frame like fit_on_loops' -- the
                      label is FITTED into it: never over a hole, never off
                      the face, WHITE_EDGE from every edge. It slides along
                      its side to the free spot nearest the tag's axis (an
                      exact scan of the band it needs; equally near: the
                      right / the upper one), and moves out at most REACH
                      modules further -- then, when nothing fits that near
                      (Zach's GIM43 disc, 2026-10-13: a hole right below
                      the marker), as far out as the face goes;
              grow    the tile (or White only's white pattern) grows by a
                      label strip on that side (inside `bounds` when given:
                      the face it sits on).
            Neither collides with a corner mark (aruco_chamfer: the cut
            tile corner, the triangle, the cut ChArUco square) nor with a
            locating pin, KEEPOUT_MM clear. A strip's cut corner and pins
            sit at the GROWN tile's corners, level with the text: the strip
            grows deeper (up to REACH modules) to clear them before the
            text shrinks.
    auto    the whole text on the black; else the whole text on the white;
            else cut short, on the white (more room), else on the black.
    where   `position` "auto": placed by the rules above. "manual": x_mm /
            y_mm, the label block's CENTRE in the pattern frame after the
            Origin turn (+x right, +y up from the pattern's centre; Zach,
            2026-10-13: "Offset X and Offset Y can start at auto?" -- the
            dialog shows auto's spot there, and typing one takes over).
            Every rule is checked at that spot. On the white Auto size
            shrinks the text to fit there, never above auto's cap (so
            taking over never moves or grows it; `position_of` is the spot
            auto chose); in a ChArUco square it moves freely; on the black
            along its row only (y clamped, with a note). A spot that breaks
            a rule is shown there with what it breaks, built only with
            Build anyway. Older records carry offset_x_mm / offset_y_mm, a
            nudge after the automatic placement: they still give the label
            they gave (auto's spot moved by the offset).

### Size, and a text too long for its place

Auto: the largest cap that fits, rounded down to 0.1 mm, at most 0.5 module
on the black, 1.5 modules on the white (0.22 square in a ChArUco square).
On the white one line is kept while it reaches 0.5 module; a longer text
wraps (at spaces and after "/", up to 3 lines) where that is bigger. The
ids are sized at the dictionary's widest ("#9" is fitted as "#09" for
DICT_4X4_50) and a component's name with an occurrence number ("Actuator"
as "Actuator:0"), so every copy of a batch prints at the template's size.
A typed cap is clamped to the rule (on the white: 4 modules) with a note,
and shrunk with a note if it does not fit. A text too long for its place
shrinks, down to the smallest printable cap (5 nozzles: three bars and two
gaps -- never thinner than the nozzle); then a name path drops to its last
element; then it is CUT SHORT with "..." (`name_cuts`: keeping its
occurrence number, "Shoulder_Pi...:2", which tells a batch's copies apart),
with a note. An id is never cut: a text whose id does not fit is refused.

### Geometry

Zach, 2026-10-10: "its important that we try to make it easy to 3D print the
letters. I think we will need to use like very blocky letters and support
0.6 mm nozzle." So the font is a PIXEL font (GLYPHS): every glyph is a
bitmap GLYPH_ROWS = 5 pixels tall (3 wide for most, 4 or 5 for B D K R Z M W #),
one pixel = one stroke = cap / 5. Every bar, every counter, every gap between
glyphs is a whole number of pixels, every stroke axis-aligned with square
corners, and no two pixels touch only at a corner (no 2 x 2 checkerboard:
no zero-width joint, no thin wedge in either colour). A slicer prints such a
bar at full extrusion width. The pixel is at least the nozzle (x
STROKE_NOZZLE; a typed stroke_mm can ask for more), so the smallest cap is
5 pixels: 3.0 mm at the default 0.6 mm nozzle. Each glyph's pixels come out
as a few axis-aligned boxes (horizontal runs, merged down the rows), which
the add-in builds with TemporaryBRepManager.createBox (Box: centre, length
along `angle`, width across it; a label turned a quarter is still axis-
aligned). `min_feature` is one pixel (and the black left around knocked-out
text).

### Colour (`role`, relative to the black footprint)

    black placement  "cut": the text comes OUT of the black cells; the white
                     under (tile or body) shows through. White only: the
                     text is added to the white pattern (same rule: white =
                     box - footprint).
    white placement  "add": the text is part of the black cells (inlaid into
                     the tile / the body, like the cells). White only: a
                     notch in the white pattern, the black body shows.

Height (Zach: "the height of the label itself I think should match the
height of the blackness"): the label is built in the PATTERN layer's own
slab -- the black cells' Offset + Height (`pattern_slab`), the white
pattern's in White only. `Label.solids()` says how: "join" exactly that
slab (black text on the white: more black, flush with the marker's), or
"cut" through it (white text in the black: a hole, the white under shows).

Coordinates: mm in the PATTERN frame -- origin the pattern's centre, u the
pattern's x (image right), v image up -- after the Origin turn, the frame
aruco_chamfer uses (markers.cell_boxes' frame, in mm).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from . import board as aruco_board
from .autosize import _clean, _inside, _rect_inside
from .dictionary import ARUCO_DICTS
from .markers import TagSpec, board_spec, split_path

Pt = Tuple[float, float]
Rect = Tuple[float, float, float, float]          # (u0, v0, u1, v1), mm

# ------------------------------------------------------------------ options

# the label's CONTENT: a template, "|" between its lines
PRESETS = {"id": "#{id}", "id_name": "#{id}|{name}", "name": "{name}",
           "dict_id": "{dict} #{id}"}
CONTENTS = tuple(PRESETS) + ("custom",)
# its POSITION, apart from what it says
PLACES = ("auto", "black", "white")
ROWS = ("auto", "bottom", "top", "both", "square")   # on the black
SIDES = ("auto", "below", "above", "left", "right")  # on the white
SCOPES = ("auto", "each", "first")                    # a board's markers, on the black
POSITIONS = ("auto", "manual")                        # placed by the rules / at x_mm, y_mm
TOKENS = ("id", "ids", "name", "key", "dict", "size")
LINE_BREAK = "|"
ELLIPSIS = "…"
SIDE_ORDER = ("below", "above", "right", "left")      # "auto" ties go to the first
SIDE_ROT = {"below": 0, "above": 0, "left": 90, "right": -90}

# --------------------------------------------------------------- the rules
# module units unless the name says mm

BLACK_CAP = 0.5            # cap in a border row (0.7 costs on crisp prints)
BLACK_EDGE = 0.25          # black kept above and below the text in its row
CORNER_CLEAR = 0.25        # black kept between the text and each corner cell
# On the white, two lines (2026-10-13; tools/study_aruco_label_gap.py ->
# reports/media/aruco/marks/gap_black.json: full-black "#id" text, n = 3000
# paired stressed-camera trials against a plain marker, the gap measured from
# the black edge, caps 0.5 / 1.0 module: 0.5 module -7.3 / -6.6 pts, 0.7
# -1.5 / -1.2 pts, 1.0 -0.1 / +0.03 pts (n.s.), 1.25 to 2.0 no effect). The
# quiet ring itself (>= 1 module from the black) is the hard rule.
WHITE_GAP_MIN = 0.0        # HARD: label ink stays this far beyond the quiet ring (modules);
                           # closer is a violation, built only with Build anyway
WHITE_GAP_PREF = 0.25      # PREFERRED: auto keeps this much more when it fits (print
                           # tolerance; the study shows no gain past 1.0 module). Less is
                           # no violation and no note
WHITE_GAP = WHITE_GAP_PREF  # the name before 2026-10-13 (then 1.0 module, one rule)
POS_TOL_MM = 0.01          # a spot within this of another is the same spot (a dialog's
                           # rounded field), and no rule is broken by less than this
WHITE_CAP = 1.5            # the auto cap's ceiling on the white
ONE_LINE = 0.5             # on the white one line is kept while its cap reaches this
                           # (the border row's size); a longer text wraps (<= MAX_LINES)
WHITE_LIMIT = 4.0          # a typed cap's ceiling on the white
WHITE_EDGE = 0.25          # the label to the edge of its white (and >= EDGE_MIN_MM)
EDGE_MIN_MM = 1.0
KEEPOUT_MM = 1.0           # the label to a corner mark or a pin, at least ...
KEEPOUT = 0.25             # ... and this many modules
SQUARE_CAP = 0.22          # ChArUco square label: cap <= 0.22 square (print_sheet's)
SQUARE_EDGE = 0.1          # ... >= 0.1 square (and 1 module) inside the square
SQUARE_CORNER = 0.35       # ... >= 0.35 square from every ChArUco corner
SQUARE_CORNER_HARD = 0.3   # the safety check's line (the chamfer study's)
MAX_LINES = 3

NOZZLE_MM = 0.6            # Zach's MK4 / MMU3 (2026-10-10)
STROKE_NOZZLE = 1.0        # the pixel (= the stroke, every gap) >= this x the nozzle
GLYPH_ROWS = 5             # the font's cap height in pixels
LINE_GAP_PX = 2            # between lines, in pixels
CAP_STEP_MM = 0.1          # auto caps round down to this
REACH = 3.0                # on the white a label moves out (a strip grows deeper) at
                           # most this much further to clear a hole, a mark or a pin
                           # (a region: then further, as far as the face goes)
SIDE_SLACK = 0.8           # Side auto: an earlier side (below, above, right, left) keeps
                           # the label while its text is at least this much of the biggest
                           # (upright and below when that costs little; Zach, 2026-10-13:
                           # "near the bottom")


@dataclass(frozen=True)
class Rule:
    """How a label on the white keeps from the black: the rule it was MADE
    under (LabelSettings.rule), so a label never moves on its own (2026-10-13:
    Zach may have printed it; a Compute All must not move it)."""
    gap_min: float             # HARD: modules beyond the quiet ring; nearer is a violation
    gap_pref: float            # what auto keeps when the label still fits
    far: bool                  # auto searches past REACH, as far as the face goes
    slack: float               # Side auto: an earlier side keeps it at >= slack x the biggest
    exact: bool                # a moved spot measured as the crow flies, POS_TOL_MM, ties to
                               # the right / up, the scan's last part-stride


RULES = {
    # before 2026-10-13: one line, 2 modules from the black (the quiet ring +
    # 1 module), within REACH only, the biggest text's side -- every record
    # without "rule"
    1: Rule(gap_min=1.0, gap_pref=1.0, far=False, slack=1.0, exact=False),
    # the quiet ring is the hard line, 0.25 module preferred, the far search
    2: Rule(gap_min=WHITE_GAP_MIN, gap_pref=WHITE_GAP_PREF, far=True, slack=SIDE_SLACK,
            exact=True),
    # NOT REF's (ArUco Studio M6a, 2026-10-16, Zach's FB-13): rule 2, and a
    # ChArUco label placed by hand may sit in ANY black square of the board,
    # checked against THAT square (its edges, its corners); Auto still picks
    # the top-left one. Rule 2 refused a spot outside the top-left square.
    3: Rule(gap_min=WHITE_GAP_MIN, gap_pref=WHITE_GAP_PREF, far=True, slack=SIDE_SLACK,
            exact=True),
}
RULE = 2                   # what a NEW label is made under
RULE_NOTE = ("older label rule (2-module gap): change any label setting to use the new one")
NEW_RULE = 3               # what the Studio's new tag stores (core.form.new_tag_settings);
                           # REF's RULE (2) stays the LabelSettings default
ANY_SQUARE_RULE = 3        # from this rule on a ChArUco label by hand takes any black square


def rule_of(settings) -> Rule:
    """The Rule of a LabelSettings (or a Label's settings)."""
    r = getattr(settings, "rule", RULE) if settings is not None else RULE
    return RULES.get(r, RULES[RULE])
EPS = 1e-9
TOL = 1e-6                 # mm: geometric checks
SOLID_PAD_MM = 0.1         # a cut tool stands this far past the slab it cuts (no coplanar faces)


# --------------------------------------------------------------------- font
#
# A PIXEL font (Zach, 2026-10-10: "very blocky letters ... support 0.6 mm
# nozzle"): each glyph is GLYPH_ROWS bitmap rows, top first, "X" = ink. One pixel =
# one stroke = cap / GLYPH_ROWS, so every bar, counter and gap is a whole number of
# strokes and every edge is axis-aligned. No two ink pixels touch only at a
# corner and no two blank ones either (no 2 x 2 checkerboard: a zero-width
# joint or a thin wedge is what a slicer drops). Glyphs sit one pixel apart.
# tests/test_aruco_label.py checks all of it.

GLYPHS: Dict[str, Tuple[int, Tuple[str, ...]]] = {
    " ": (1, (".", ".", ".", ".", ".")),
    "0": (3, ("XXX", "X.X", "X.X", "X.X", "XXX")),
    "1": (3, (".X.", "XX.", ".X.", ".X.", "XXX")),
    "2": (3, ("XXX", "..X", "XXX", "X..", "XXX")),
    "3": (3, ("XXX", "..X", ".XX", "..X", "XXX")),
    "4": (3, ("X.X", "X.X", "XXX", "..X", "..X")),
    "5": (3, ("XXX", "X..", "XXX", "..X", "XXX")),
    "6": (3, ("XXX", "X..", "XXX", "X.X", "XXX")),
    "7": (3, ("XXX", "..X", "..X", "..X", "..X")),
    "8": (3, ("XXX", "X.X", "XXX", "X.X", "XXX")),
    "9": (3, ("XXX", "X.X", "XXX", "..X", "XXX")),
    "A": (3, ("XXX", "X.X", "XXX", "X.X", "X.X")),
    "B": (4, ("XXX.", "X.X.", "XXXX", "X..X", "XXXX")),
    "C": (3, ("XXX", "X..", "X..", "X..", "XXX")),
    "D": (4, ("XXX.", "X.XX", "X..X", "X.XX", "XXX.")),
    "E": (3, ("XXX", "X..", "XX.", "X..", "XXX")),
    "F": (3, ("XXX", "X..", "XX.", "X..", "X..")),
    "G": (3, ("XXX", "X..", "X.X", "X.X", "XXX")),
    "H": (3, ("X.X", "X.X", "XXX", "X.X", "X.X")),
    "I": (3, ("XXX", ".X.", ".X.", ".X.", "XXX")),
    "J": (3, ("..X", "..X", "..X", "X.X", "XXX")),
    "K": (4, ("X.XX", "X.X.", "XXX.", "X.X.", "X.XX")),
    "L": (3, ("X..", "X..", "X..", "X..", "XXX")),
    "M": (5, ("XXXXX", "X.X.X", "X.X.X", "X.X.X", "X.X.X")),
    "N": (3, ("XXX", "X.X", "X.X", "X.X", "X.X")),
    "O": (3, ("XXX", "X.X", "X.X", "X.X", "XXX")),
    "P": (3, ("XXX", "X.X", "XXX", "X..", "X..")),
    "Q": (3, ("XXX", "X.X", "X.X", "XXX", "..X")),
    "R": (4, ("XXX.", "X.X.", "XXXX", "X..X", "X..X")),
    "S": (3, ("XXX", "X..", "XXX", "..X", "XXX")),
    "T": (3, ("XXX", ".X.", ".X.", ".X.", ".X.")),
    "U": (3, ("X.X", "X.X", "X.X", "X.X", "XXX")),
    "V": (3, ("X.X", "X.X", "X.X", "XXX", ".X.")),
    "W": (5, ("X.X.X", "X.X.X", "X.X.X", "X.X.X", "XXXXX")),
    "X": (3, ("X.X", "XXX", ".X.", "XXX", "X.X")),
    "Y": (3, ("X.X", "X.X", "XXX", ".X.", ".X.")),
    "Z": (4, ("XXXX", "..XX", ".XX.", "XX..", "XXXX")),
    "#": (5, (".X.X.", "XXXXX", ".X.X.", "XXXXX", ".X.X.")),
    "-": (3, ("...", "...", "XXX", "...", "...")),
    "_": (3, ("...", "...", "...", "...", "XXX")),
    ":": (1, (".", "X", ".", "X", ".")),
    ".": (1, (".", ".", ".", ".", "X")),
    "/": (3, ("..X", ".XX", ".X.", "XX.", "X..")),
    "+": (3, ("...", ".X.", "XXX", ".X.", "...")),
    "=": (3, ("...", "XXX", "...", "XXX", "...")),
    "(": (2, ("XX", "X.", "X.", "X.", "XX")),
    ")": (2, ("XX", ".X", ".X", ".X", "XX")),
    "?": (3, ("XXX", "..X", ".XX", "...", ".X.")),
    "…": (5, (".....", ".....", ".....", ".....", "X.X.X")),   # a text cut short
}
UNKNOWN = "?"


def normalize(text: str) -> Tuple[str, List[str]]:
    """The text as the font draws it: upper-case, one space between words,
    a character it lacks -> "?" (and the list of them)."""
    out, missing = [], []
    for ch in " ".join(str(text or "").upper().split()):
        if ch in GLYPHS:
            out.append(ch)
        else:
            out.append(UNKNOWN)
            if ch not in missing:
                missing.append(ch)
    return "".join(out), missing


@dataclass(frozen=True)
class Metrics:
    """The font at one cap height (mm): one pixel = one stroke = cap / GLYPH_ROWS;
    every bar, counter and gap between glyphs is a whole number of them."""
    cap: float
    stroke: float

    @property
    def unit(self) -> float:            # one pixel
        return self.stroke

    @property
    def space(self) -> float:           # between two glyphs' ink: one pixel
        return self.stroke

    @property
    def gap(self) -> float:             # the narrowest counter / notch: one pixel
        return self.stroke

    @property
    def line_gap(self) -> float:
        return LINE_GAP_PX * self.stroke

    @property
    def min_feature(self) -> float:
        return self.stroke


def min_stroke(nozzle: float = NOZZLE_MM, stroke: float = 0.0) -> float:
    """The thinnest pixel that prints: the nozzle (x STROKE_NOZZLE), or a
    typed stroke when it asks for more."""
    w = float(nozzle) * STROKE_NOZZLE
    if stroke and stroke > 0:
        w = max(w, float(stroke))
    return w


def stroke_for(cap: float, nozzle: float = NOZZLE_MM, stroke: float = 0.0) -> float:
    """The stroke (one pixel) at a cap: cap / GLYPH_ROWS (the font is a bitmap)."""
    return float(cap) / GLYPH_ROWS


def metrics(cap: float, nozzle: float = NOZZLE_MM, stroke: float = 0.0) -> Metrics:
    return Metrics(float(cap), stroke_for(cap, nozzle, stroke))


def min_cap(nozzle: float = NOZZLE_MM, stroke: float = 0.0) -> float:
    """The smallest cap whose strokes AND gaps are >= the nozzle: GLYPH_ROWS
    pixels (three bars and two gaps), each min_stroke wide -- 3.0 mm at a
    0.6 mm nozzle."""
    return GLYPH_ROWS * min_stroke(nozzle, stroke)


def glyph_width(ch: str, M: Metrics) -> float:
    """A glyph's ink width (a space: its advance)."""
    return GLYPHS.get(ch, GLYPHS[UNKNOWN])[0] * M.unit


def line_width(text: str, M: Metrics) -> float:
    if not text:
        return 0.0
    return sum(glyph_width(c, M) for c in text) + (len(text) - 1) * M.space


def block_size(lines: Sequence[str], M: Metrics) -> Tuple[float, float]:
    """(width, height) of lines stacked, centred."""
    if not lines:
        return 0.0, 0.0
    return (max(line_width(t, M) for t in lines),
            len(lines) * M.cap + (len(lines) - 1) * M.line_gap)


# ---------------------------------------------------------------- boxes

@dataclass(frozen=True)
class Box:
    """One stroke: centre (cx, cy), `length` along the direction `angle`
    (degrees from +u, in (-90, 90]), `width` across it. mm, pattern frame.
    angle 0: an axis-aligned box, length along u, width along v.

    The add-in: TemporaryBRepManager.createBox(OrientedBoundingBox3D(centre,
    x cos a + y sin a, -x sin a + y cos a, length, width, height))."""
    cx: float
    cy: float
    length: float
    width: float
    angle: float = 0.0

    def corners(self) -> List[Pt]:
        """CCW."""
        a = math.radians(self.angle)
        c, s = math.cos(a), math.sin(a)
        hl, hw = self.length / 2.0, self.width / 2.0
        return [(self.cx + du * c - dv * s, self.cy + du * s + dv * c)
                for du, dv in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]

    def bounds(self) -> Rect:
        pts = self.corners()
        return (min(p[0] for p in pts), min(p[1] for p in pts),
                max(p[0] for p in pts), max(p[1] for p in pts))

    def to_list(self, nd: int = 4) -> List[float]:
        return [round(v, nd) + 0.0 for v in (self.cx, self.cy, self.length, self.width,
                                             self.angle)]


def _box_norm(cx, cy, length, width, angle) -> Box:
    """A box with its angle in (-90, 90]; a quarter turn becomes angle 0
    with its sides swapped."""
    a = math.fmod(float(angle), 180.0)
    if a <= -90.0 + 1e-9:
        a += 180.0
    elif a > 90.0 + 1e-9:
        a -= 180.0
    if abs(abs(a) - 90.0) < 1e-9:
        return Box(cx, cy, width, length, 0.0)
    if abs(a) < 1e-9:
        a = 0.0
    return Box(cx, cy, length, width, a)


def glyph_rects(ch: str) -> List[Tuple[int, int, int, int]]:
    """A glyph's ink as pixel rectangles (c0, r0, c1, r1), c to the right,
    r UP from the baseline, end-exclusive: each row's runs, merged with the
    same run on the rows below -- a few boxes per glyph."""
    _w, rows = GLYPHS.get(ch, GLYPHS[UNKNOWN])
    n = len(rows)
    out: List[List[int]] = []
    open_: Dict[Tuple[int, int], List[int]] = {}
    for k, row in enumerate(rows):                      # top first
        r = n - 1 - k                                   # its height over the baseline
        runs, c = [], 0
        while c < len(row):
            if row[c] == "X":
                c0 = c
                while c < len(row) and row[c] == "X":
                    c += 1
                runs.append((c0, c))
            else:
                c += 1
        nxt = {}
        for run in runs:
            rect = open_.get(run)
            if rect is not None:
                rect[1] = r                             # one row further down
            else:
                rect = [run[0], r, run[1], r + 1]
                out.append(rect)
            nxt[run] = rect
        open_ = nxt
    return [tuple(x) for x in out]


def glyph_boxes(ch: str, M: Metrics, x0: float = 0.0, y0: float = 0.0) -> List[Box]:
    """A glyph's ink as axis-aligned boxes, its ink box's bottom-left at
    (x0, y0)."""
    p = M.unit
    return [Box(x0 + (c0 + c1) * p / 2.0, y0 + (r0 + r1) * p / 2.0, (c1 - c0) * p,
                (r1 - r0) * p, 0.0) for c0, r0, c1, r1 in glyph_rects(ch)]


def line_boxes(text: str, M: Metrics, x0: float = 0.0, y0: float = 0.0) -> List[Box]:
    """A line's boxes, its baseline-left at (x0, y0)."""
    out, x = [], x0
    for ch in text:
        out += glyph_boxes(ch, M, x, y0)
        x += glyph_width(ch, M) + M.space
    return out


def block_boxes(lines: Sequence[str], M: Metrics, centre: Pt = (0.0, 0.0),
                rot: int = 0) -> List[Box]:
    """Lines stacked, each centred, the block centred on `centre`, turned by
    `rot` degrees (0, 90 = reads upward, -90 = reads downward)."""
    W, H = block_size(lines, M)
    boxes = []
    for k, t in enumerate(lines):
        base = H / 2.0 - (k + 1) * M.cap - k * M.line_gap
        boxes += line_boxes(t, M, -line_width(t, M) / 2.0, base)
    r = math.radians(rot)
    c, s = round(math.cos(r), 12), round(math.sin(r), 12)
    return [_box_norm(centre[0] + b.cx * c - b.cy * s, centre[1] + b.cx * s + b.cy * c,
                      b.length, b.width, b.angle + rot) for b in boxes]


def ink_rect(boxes: Iterable[Box]) -> Optional[Rect]:
    rs = [b.bounds() for b in boxes]
    if not rs:
        return None
    return (min(r[0] for r in rs), min(r[1] for r in rs),
            max(r[2] for r in rs), max(r[3] for r in rs))


# ------------------------------------------------------------------ content

def dict_short(dictionary: str) -> str:
    return str(dictionary).replace("DICT_", "")


def _fmt_mm(v: float) -> str:
    t = ("%.1f" % v).rstrip("0").rstrip(".")
    return t or "0"


def part_name(path: str, depth: int = 2) -> str:
    """The last `depth` elements of an occurrence path, "/"-joined:
    "Robot:1+Arm:2+Actuator:3" -> "Arm:2/Actuator:3"."""
    parts = split_path(path or "")
    return "/".join(parts[-depth:]) if parts else ""


def name_variants(name: str) -> List[str]:
    """{name} in order of preference: as given, then its last element only
    (a long path that does not fit falls back to the part itself)."""
    out = [str(name or "")]
    tail = out[0].split("/")[-1]
    if tail != out[0]:
        out.append(tail)
    return out


def instance_name(inst) -> str:
    """{name} for the geometry that shows a markers.TagInstance. Geometry is
    shared per component, so: a copy built as its own tag part (its id or
    dictionary overridden -> an aruco_tags variant at the level that set it)
    says its occurrence path below that level, the last two elements; every
    other copy shows its template, which says the component's name."""
    if inst.path and inst.needs_variant:
        parts = split_path(inst.path)
        lvl = inst.winning.level
        depth = len(split_path(lvl)) if lvl else 0
        return "/".join(parts[depth:][-2:])
    return inst.tag.component or ""


_TOKEN = re.compile(r"\{(\w+)\}")
_OCC = re.compile(r":\d+$")              # an occurrence number, "Actuator:3"
_ID_TOKEN = re.compile(r"\{ids?\}")


def name_cuts(name: str) -> List[str]:
    """A name cut short, longest first, for a place it does not fit even at
    the smallest printable cap: its last element, cut with "..." but keeping
    its occurrence number -- the part that tells a batch's copies apart:
    "Shoulder_Actuator:3" -> "Shoulder_Actuat...:3", ..., "S...:3"."""
    tail = str(name or "").split("/")[-1]
    mo = _OCC.search(tail)
    base, occ = (tail[:mo.start()], mo.group()) if mo else (tail, "")
    out = []
    for k in range(len(base) - 1, 0, -1):
        t = base[:k].rstrip() + ELLIPSIS + occ
        if t not in out:
            out.append(t)
    return out


def text_cuts(text: str) -> List[str]:
    """A text cut short from its end, longest first ("ROBOT ARM" -> "ROBOT
    AR...", ...). Only for a text with no id in it: an id is never cut."""
    t = " ".join(str(text or "").replace(LINE_BREAK, " ").split())
    out = []
    for k in range(len(t) - 1, 0, -1):
        c = t[:k].rstrip() + ELLIPSIS
        if c not in out:
            out.append(c)
    return out


def template_lines(template: str) -> List[str]:
    """The content's lines (templates), as written."""
    return str(template or "").split(LINE_BREAK)


def part_template(template: str, part: str) -> str:
    """The share of the content a place shows: "all" of it (a place that
    holds one line joins its lines with a space), its "first" line (the
    bottom row of "both rows") or the "rest" (the top row)."""
    lines = template_lines(template)
    if part == "first":
        return lines[0]
    if part == "rest":
        return LINE_BREAK.join(lines[1:])
    return str(template or "")


def resolve_text(template: str, spec: TagSpec, *, marker_id: Optional[int] = None,
                 name: str = "", key: str = "", sizing: bool = False) -> str:
    """A template's text for one tag: pure (spec, marker, name, key).

    marker_id  a per-marker label's marker ({id} = its id); None = the
               target's own label ({id} = the id block, "9-12" on a board)
    sizing     every id padded with zeros to the dictionary's widest
               ("#9" -> "#09" in DICT_4X4_50), and a component's name
               given an occurrence number ("Actuator" -> "Actuator:0"):
               the text a label is SIZED with, so the copies a batch of ids
               rebuilds ("#10 Actuator:2") print at the template's size
    Unknown tokens are kept as written ({x} prints "?X?")."""
    ids = spec.ids
    cap = ARUCO_DICTS.get(spec.dictionary, 0)
    digits = len(str(max(0, cap - 1))) if sizing else 0

    def num(i):
        return str(int(i)).zfill(digits)
    block = num(ids[0]) if len(ids) == 1 else f"{num(ids[0])}-{num(ids[-1])}"
    nm = str(name or "").replace(LINE_BREAK, "/")
    if sizing and nm and not _OCC.search(nm.split("/")[-1]):
        nm += ":0"
    vals = {"id": block if marker_id is None else num(marker_id), "ids": block,
            "name": nm, "key": str(key or "").replace(LINE_BREAK, "/"),
            "dict": dict_short(spec.dictionary), "size": _fmt_mm(spec.marker_length_m * 1000.0)}
    out = _TOKEN.sub(lambda mo: vals.get(mo.group(1), mo.group(0)), str(template or ""))
    return LINE_BREAK.join(" ".join(p.split()) for p in out.split(LINE_BREAK)).strip(
        LINE_BREAK + " ")


def unknown_tokens(template: str) -> List[str]:
    return [t for t in _TOKEN.findall(str(template or "")) if t not in TOKENS]


_CHUNK = re.compile(r"[^ /]+/?|/")


def _join(chunks: Sequence[str]) -> str:
    """Chunks back into a line: a space between words, none after a "/"."""
    out = ""
    for c in chunks:
        out += c if (not out or out.endswith("/")) else " " + c
    return out


def wraps(text: str, max_lines: int = 1) -> List[List[str]]:
    """Line arrangements of a drawn text, fewest lines first: as written
    ("|" breaks; one line where only one fits), then broken at spaces and
    after each "/" (a path: "ARM:2/" + "ACTUATOR:3") into 2 .. max_lines
    lines of balanced length."""
    parts = [p.strip() for p in text.split(LINE_BREAK) if p.strip()]
    if max_lines <= 1 or not parts:
        return [[" ".join(parts)]] if parts else []
    if len(parts) > max_lines:
        parts = parts[:max_lines - 1] + [" ".join(parts[max_lines - 1:])]
    out = [parts]
    if len(parts) == 1:
        words = _CHUNK.findall(parts[0])
        for k in range(2, min(max_lines, len(words)) + 1):
            best = None
            for cut in _cuts(len(words), k):
                lines = [_join(words[a:b]) for a, b in zip((0,) + cut, cut + (len(words),))]
                score = max(len(t) for t in lines)
                if best is None or score < best[0]:
                    best = (score, lines)
            out.append(best[1])
    return out


def _cuts(n: int, k: int):
    """Every way to cut n words into k non-empty runs (k - 1 cut points)."""
    def rec(start, left):
        if left == 0:
            yield ()
            return
        for c in range(start + 1, n - left + 1):
            for rest in rec(c, left - 1):
                yield (c,) + rest
    return rec(0, k - 1)


# ----------------------------------------------------------------- settings

@dataclass
class LabelSettings:
    """ONE label (stored in the node's spec as "label"): what it says, and,
    apart from that, where it goes and how big. Any content goes in any
    position the tag has (`positions`); a place that holds one line joins
    the content's lines with a space.

    content  what:   content (a preset) / text (custom), "|" between lines
    position where:  place (auto / black / white), then on the black the
                     row (bottom / top / both rows / the ChArUco square) and,
                     on a board, scope (each marker / the first one); on the
                     white the side; then `position`: "auto" (the rules
                     place it) or "manual" -- x_mm / y_mm, the label block's
                     centre (the pattern frame after the Origin turn: +x
                     right, +y up from its centre), checked against every
                     rule there (Zach, 2026-10-13: "Offset X and Offset Y
                     can start at auto?"). offset_x_mm / offset_y_mm: older
                     records' nudge after the automatic placement, still
                     honoured (position "auto" + an offset = auto's spot
                     moved by it)
    size             cap_mm (0 = auto), nozzle_mm, stroke_mm (0 = auto)
    build_anyway     a label that breaks a rule is always SHOWN (Label.preview:
                     where it would go, its violations in plain words) but
                     built only when this is set (Zach, 2026-10-11: "I should
                     always be able to see the label even if the linter is
                     saying its going to cause an error")"""
    on: bool = False
    content: str = "id"            # a PRESETS key or "custom"
    text: str = ""                 # the custom template
    place: str = "auto"            # auto / black / white
    row: str = "auto"              # black: auto (both rows; ChArUco: the square) / bottom /
                                   # top / both (line 1 bottom, the rest top) / square
    side: str = "auto"             # white: auto / below / above / left / right
    scope: str = "auto"            # a board on the black: auto (each) / each / first
    cap_mm: float = 0.0            # 0 = auto
    nozzle_mm: float = NOZZLE_MM
    stroke_mm: float = 0.0         # 0 = auto: max(nozzle, 0.13 cap)
    offset_x_mm: float = 0.0       # LEGACY (before 2026-10-13): a nudge after the automatic
    offset_y_mm: float = 0.0       # placement, +x right, +y up -- kept, so an old record
                                   # gives the label it gave
    build_anyway: bool = False     # build a label that breaks a rule (it is shown anyway)
    position: str = "auto"         # auto: placed by the rules / manual: at (x_mm, y_mm)
    x_mm: float = 0.0              # manual: the label block's centre, +x right of the
    y_mm: float = 0.0              # pattern's centre, +y up (the frame after the Origin turn)
    rule: int = RULE               # the rule it was made under (RULES); a stored label
                                   # without one is rule 1 and keeps its exact layout

    @property
    def manual(self) -> bool:
        return self.position == "manual"

    @property
    def nudged(self) -> bool:
        """An older record's offset, applied after the automatic placement."""
        return not self.manual and (abs(self.offset_x_mm) > TOL or abs(self.offset_y_mm) > TOL)

    def template(self) -> str:
        if self.content == "custom":
            return self.text or ""
        return PRESETS.get(self.content, PRESETS["id"])

    def black_row(self, layout: str) -> str:
        """The row on the black, "auto" resolved: a ChArUco board's label
        goes in its black square, every other tag's in both rows (line 1
        at the bottom: "#12", line 2 at the top: "ACTUATOR")."""
        if self.row == "auto":
            return "square" if layout == "charuco" else "both"
        if self.row == "square" and layout != "charuco":
            return "both"
        return self.row

    def to_dict(self) -> dict:
        return {"on": bool(self.on), "content": self.content, "text": self.text,
                "place": self.place, "row": self.row, "side": self.side,
                "scope": self.scope, "cap_mm": float(self.cap_mm),
                "nozzle_mm": float(self.nozzle_mm), "stroke_mm": float(self.stroke_mm),
                "offset_x_mm": float(self.offset_x_mm), "offset_y_mm": float(self.offset_y_mm),
                "build_anyway": bool(self.build_anyway),
                # auto: no spot (what the dialog shows there is auto's, not a setting)
                "position": self.position,
                "x_mm": float(self.x_mm) if self.manual else 0.0,
                "y_mm": float(self.y_mm) if self.manual else 0.0,
                "rule": int(self.rule)}

    @classmethod
    def from_dict(cls, d: Optional[dict], notes: Optional[List[str]] = None) -> "LabelSettings":
        """Tolerant: an unknown value falls back to the default, with a note."""
        s = cls()
        if not isinstance(d, dict):
            return s
        say = notes.append if notes is not None else (lambda _m: None)
        s.on = bool(d.get("on", False))
        d = dict(d)
        if d.get("scope") == "square":            # phase 1 kept the square under scope
            d["scope"], d["row"] = "auto", "square"
        for key, allowed in (("content", CONTENTS), ("place", PLACES), ("row", ROWS),
                             ("side", SIDES), ("scope", SCOPES), ("position", POSITIONS)):
            v = d.get(key, getattr(s, key))
            if v in allowed:
                setattr(s, key, v)
            else:
                say(f"label: {key} {v!r} is not one of {', '.join(allowed)} -- "
                    f"{getattr(s, key)} used")
        s.text = str(d.get("text") or "")
        for key in ("cap_mm", "nozzle_mm", "stroke_mm"):
            try:
                v = float(d.get(key, getattr(s, key)))
            except (TypeError, ValueError):
                v = getattr(s, key)
            if not math.isfinite(v) or v < 0:
                v = getattr(s, key)
            setattr(s, key, v)
        if s.nozzle_mm <= 0:
            s.nozzle_mm = NOZZLE_MM
        for key in ("offset_x_mm", "offset_y_mm", "x_mm", "y_mm"):        # either sign
            try:
                v = float(d.get(key, 0.0))
            except (TypeError, ValueError):
                v = 0.0
            setattr(s, key, v if math.isfinite(v) else 0.0)
        s.build_anyway = bool(d.get("build_anyway", False))
        if not s.manual:
            s.x_mm = s.y_mm = 0.0
        # no "rule": a label stored before 2026-10-13 -- rule 1, laid out as it was
        try:
            rv = int(d.get("rule", 1))
        except (TypeError, ValueError):
            rv = -1
        if rv not in RULES:
            say(f"label: rule {d.get('rule')!r} is not one of "
                f"{', '.join(str(k) for k in RULES)} -- {RULE} used")
            rv = RULE
        s.rule = rv
        return s


def positions(layout: str) -> List[Tuple[str, str]]:
    """Every position a tag of this layout has, (place, row or side): what
    the dialog's Position + Row lists offer. Any content goes in any of them
    (a long text shrinks, then is cut short with a note)."""
    rows = ["bottom", "top", "both"] + (["square"] if layout == "charuco" else [])
    return [("black", r) for r in rows] + [("white", sd) for sd in SIDES]


# ------------------------------------------------------------------- result

@dataclass
class Slot:
    """Where one block of label text may go, every rule already checked:
    text laid out inside `rect` (centred, turned by `rot`) is safe. A copy
    (`relabel`) lays its own text out in the same slots."""
    where: str                     # "bottom" / "top" row, "square", or the white side
    rect: Rect
    rot: int = 0                   # 0, 90 (reads upward), -90 (reads downward)
    cap: float = 0.0               # the cap the template chose (copies keep it if they fit)
    lines: int = 1                 # the most lines it takes
    marker: Optional[int] = None   # a per-marker slot: index into spec.ids
    bound: Optional[Rect] = None   # the black it sits in (black rows / square)
    part: str = "all"              # the content's share: all / first line / the rest
    square: Optional[int] = None   # the marker whose border it is in (black rows)
    shift: Pt = (0.0, 0.0)         # the text's centre from the rect's (an offset along a
                                   # black row; elsewhere the rect itself is moved)

    def to_dict(self, nd: int = 4) -> dict:
        d = {"where": self.where, "rect": [round(v, nd) + 0.0 for v in self.rect],
             "rot": int(self.rot), "cap_mm": round(self.cap, nd), "lines": int(self.lines),
             "marker": self.marker, "part": self.part}
        if self.bound is not None:
            d["bound"] = [round(v, nd) + 0.0 for v in self.bound]
        if self.square is not None:
            d["square"] = int(self.square)
        if self.shift != (0.0, 0.0):
            d["shift"] = [round(v, nd) + 0.0 for v in self.shift]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Slot":
        b = d.get("bound")
        return cls(where=d["where"], rect=tuple(map(float, d["rect"])), rot=int(d.get("rot", 0)),
                   cap=float(d.get("cap_mm", 0.0)), lines=int(d.get("lines", 1)),
                   marker=d.get("marker"), bound=tuple(map(float, b)) if b else None,
                   part=d.get("part", "all"), square=d.get("square"),
                   shift=tuple(map(float, d.get("shift") or (0.0, 0.0))))


@dataclass
class Part:
    """One slot's text, laid out."""
    slot: int                      # index into Label.slots
    text: str                      # resolved
    lines: List[str]               # as drawn (normalized, wrapped)
    cap: float
    stroke: float
    min_feature: float
    rect: Rect                     # the ink's box
    boxes: List[Box]
    short: str = ""                # "" | "tail" (a path's last element) | "cut" ("...")
    full: str = ""                 # the text before it was shortened

    def to_dict(self, nd: int = 4) -> dict:
        d = {"slot": self.slot, "text": self.text, "lines": list(self.lines),
             "cap_mm": round(self.cap, nd), "stroke_mm": round(self.stroke, nd),
             "min_feature_mm": round(self.min_feature, nd),
             "rect": [round(v, nd) + 0.0 for v in self.rect],
             "boxes": [b.to_list(nd) for b in self.boxes]}
        if self.short:
            d["short"], d["full"] = self.short, self.full
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Part":
        return cls(slot=int(d["slot"]), text=d.get("text", ""), lines=list(d.get("lines") or []),
                   cap=float(d["cap_mm"]), stroke=float(d["stroke_mm"]),
                   min_feature=float(d.get("min_feature_mm", 0.0)),
                   rect=tuple(map(float, d["rect"])),
                   boxes=[Box(*map(float, b)) for b in d.get("boxes") or []],
                   short=d.get("short", ""), full=d.get("full", ""))


@dataclass
class Label:
    """One tag's label (mm, pattern frame).

    kind   "none" | "black" | "white"
    role   "cut": the text comes out of the black footprint (black placement)
           "add": the text joins the black footprint (white placement)
           (White only builds its white as box - footprint: the same rule)
    white  the white grown by a label strip -- the tile (White + black) or the
           white pattern's box (White only) -- or None (unchanged)
    strip  what that added, or None
    mode   ArUco Extrude's mode it was planned for ("both" / "black" / "white")
    slab   (lo, hi) mm along the face normal (aruco_slabs: 0 = the face, + out):
           the PATTERN layer's slab -- the black cells (White + black, Black
           only), the white pattern (White only). The label is as tall as
           the black: `solids` builds it there.
    violations  the rules this label breaks, in plain words ("overlaps the
           detector's clear zone by 1.2 mm", "hangs 0.8 mm off the face"):
           a label laid out where it was asked for although a rule says no
           (`preview`, or what build_anyway builds). [] for a good label.
    forced  built although it has violations (settings.build_anyway)
    preview kind "none" only: the label as it WOULD be -- where the chosen
           place / side puts it, at the smallest printable cap (or the typed
           one), the nudge applied -- with its violations. Always shown (the
           ghost draws it in a warning colour), built only with build_anyway.
    reason  kind "none": why the rules found no place for it, in plain words
           ("no room on the white around it for '#0' at 3.0 mm letters"); ""
           when it was refused only for where it was put by hand
    """
    kind: str = "none"
    role: str = ""
    side: str = ""
    settings: LabelSettings = field(default_factory=LabelSettings)
    slots: List[Slot] = field(default_factory=list)
    parts: List[Part] = field(default_factory=list)
    white: Optional[Rect] = None
    strip: Optional[Rect] = None
    notes: List[str] = field(default_factory=list)
    mode: str = ""
    slab: Optional[Tuple[float, float]] = None
    violations: List[str] = field(default_factory=list)
    forced: bool = False
    preview: Optional["Label"] = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        """Laid out in full and inside every rule."""
        return (self.kind != "none" and bool(self.slots) and len(self.parts) == len(self.slots)
                and not self.violations)

    @property
    def shown(self) -> Optional["Label"]:
        """What the preview draws: this label, or (refused) where it would
        go; None when there is nothing to draw."""
        if self.kind != "none" and self.parts:
            return self
        return self.preview if self.preview is not None and self.preview.parts else None

    @property
    def cap(self) -> float:
        return min((p.cap for p in self.parts), default=0.0)

    @property
    def stroke(self) -> float:
        return min((p.stroke for p in self.parts), default=0.0)

    @property
    def min_feature(self) -> float:
        return min((p.min_feature for p in self.parts), default=0.0)

    def boxes(self) -> List[Box]:
        return [b for p in self.parts for b in p.boxes]

    def polygons(self) -> List[List[Pt]]:
        return [b.corners() for b in self.boxes()]

    def texts(self) -> List[str]:
        """What each slot prints (a copy compares these with its variant's)."""
        by = {p.slot: LINE_BREAK.join(p.lines) for p in self.parts}
        return [by.get(i, "") for i in range(len(self.slots))]

    def solids(self, slab: Optional[Tuple[float, float]] = None, mode: Optional[str] = None,
               pad: float = SOLID_PAD_MM) -> dict:
        """The label in 3D, as the add-in builds it on the PATTERN body (the
        black cells; White only: the white pattern), as tall as that layer:

            op "join"  the boxes from lo to hi, exactly the pattern's slab:
                       black text on the white is more black, flush with
                       the marker's black (White only: white text added in
                       the black border)
            op "cut"   the boxes from lo - pad to hi + pad: a hole through
                       the black layer where the white under shows (White
                       only: a notch in the white where the black shows)

        -> {"op", "lo", "hi", "boxes": [Box]} (z in mm, aruco_slabs' frame).
        slab / mode default to the ones it was planned with."""
        lo, hi = slab if slab is not None else (self.slab or (0.0, 0.0))
        lo, hi = min(lo, hi), max(lo, hi)
        mode = mode or self.mode or "both"
        join = (self.role == "add") == (mode != "white")
        if not join:
            lo, hi = lo - pad, hi + pad
        return {"op": "join" if join else "cut", "lo": lo, "hi": hi, "boxes": self.boxes()}

    def footprint_rects(self) -> List[Rect]:
        """Every slot's rect: what a variant refills before it cuts its own
        text (aruco_tags._fill_box only covers the pattern's extent)."""
        return [s.rect for s in self.slots]

    def to_dict(self, nd: int = 4) -> dict:
        if self.kind == "none":
            d = {"kind": "none", "settings": self.settings.to_dict(), "notes": list(self.notes)}
            if self.preview is not None:
                d["preview"] = self.preview.to_dict(nd)
            if self.reason:
                d["reason"] = self.reason
            return d
        r = (lambda x: [round(v, nd) + 0.0 for v in x] if x is not None else None)
        d = {"kind": self.kind, "role": self.role, "side": self.side,
             "settings": self.settings.to_dict(),
             "slots": [s.to_dict(nd) for s in self.slots],
             "parts": [p.to_dict(nd) for p in self.parts],
             "white": r(self.white), "strip": r(self.strip),
             "mode": self.mode, "slab": r(self.slab),
             "cap_mm": round(self.cap, nd), "stroke_mm": round(self.stroke, nd),
             "min_feature_mm": round(self.min_feature, nd), "notes": list(self.notes)}
        if self.violations:
            d["violations"] = list(self.violations)
        if self.forced:
            d["forced"] = True
        return d


def from_dict(d: Optional[dict]) -> Label:
    """A record's label back (kind "none" for none / absent)."""
    if not isinstance(d, dict):
        return Label()
    s = LabelSettings.from_dict(d.get("settings"))
    if d.get("kind") in (None, "none"):
        pv = d.get("preview")
        return Label(settings=s, notes=list(d.get("notes") or []),
                     preview=from_dict(pv) if isinstance(pv, dict) else None,
                     reason=str(d.get("reason") or ""))
    t = (lambda x: tuple(map(float, x)) if x else None)
    return Label(kind=d["kind"], role=d.get("role", ""), side=d.get("side", ""), settings=s,
                 slots=[Slot.from_dict(x) for x in d.get("slots") or []],
                 parts=[Part.from_dict(x) for x in d.get("parts") or []],
                 white=t(d.get("white")), strip=t(d.get("strip")),
                 mode=d.get("mode", ""), slab=t(d.get("slab")),
                 notes=list(d.get("notes") or []),
                 violations=list(d.get("violations") or []), forced=bool(d.get("forced")))


def same(a: Optional[dict], b: Optional[dict], tol: float = 1e-3) -> bool:
    """Two records' labels (dicts) make the same geometry (to `tol` mm)."""
    la, lb = from_dict(a), from_dict(b)
    if la.kind != lb.kind or la.role != lb.role:
        return False
    if la.kind == "none":
        return True
    if (la.white is None) != (lb.white is None):
        return False
    if la.white is not None and any(abs(x - y) > tol for x, y in zip(la.white, lb.white)):
        return False
    ba, bb = la.boxes(), lb.boxes()
    if len(ba) != len(bb):
        return False
    return all(abs(x - y) <= tol for p, q in zip(ba, bb)
               for x, y in zip(p.to_list(9), q.to_list(9)))


# ------------------------------------------------------------- 2D helpers

def _area2(pts: Sequence[Pt]) -> float:
    """Twice a polygon's signed area (> 0: counter-clockwise)."""
    return sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def rect_poly(r: Rect) -> List[Pt]:
    return [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]


def grow_rect(r: Rect, d: float) -> Rect:
    return (r[0] - d, r[1] - d, r[2] + d, r[3] + d)


def _overlap(P: Sequence[Pt], Q: Sequence[Pt]) -> bool:
    """Convex polygons share area (separating axes; touching = no)."""
    for poly in (P, Q):
        for i in range(len(poly)):
            a, b = poly[i - 1], poly[i]
            n = (b[1] - a[1], a[0] - b[0])
            pa = [n[0] * p[0] + n[1] * p[1] for p in P]
            pb = [n[0] * p[0] + n[1] * p[1] for p in Q]
            if max(pa) <= min(pb) + 1e-12 or max(pb) <= min(pa) + 1e-12:
                return False
    return True


def _seg_pt(p: Pt, a: Pt, b: Pt) -> float:
    ax, ay = b[0] - a[0], b[1] - a[1]
    L = ax * ax + ay * ay
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L))
    return math.hypot(p[0] - a[0] - t * ax, p[1] - a[1] - t * ay)


def poly_dist(P: Sequence[Pt], Q: Sequence[Pt]) -> float:
    """Distance between two convex polygons (0 when they overlap)."""
    if _overlap(P, Q):
        return 0.0
    d = math.inf
    for A, B in ((P, Q), (Q, P)):
        for p in A:
            for i in range(len(B)):
                d = min(d, _seg_pt(p, B[i - 1], B[i]))
    return d


def pt_poly_dist(p: Pt, poly: Sequence[Pt]) -> float:
    """A point to a convex polygon (0 inside)."""
    sgn = [(b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
           for a, b in zip(poly, list(poly[1:]) + [poly[0]])]
    if all(v >= -1e-12 for v in sgn) or all(v <= 1e-12 for v in sgn):
        return 0.0
    return min(_seg_pt(p, poly[i - 1], poly[i]) for i in range(len(poly)))


def rect_point_dist(r: Rect, p: Pt) -> float:
    return math.hypot(max(r[0] - p[0], 0.0, p[0] - r[2]), max(r[1] - p[1], 0.0, p[1] - r[3]))


def rect_loop(r: Rect) -> List[Pt]:
    """A rectangle as a loop (CCW): a tile bigger than the sticker as the
    region a label is fitted into."""
    return rect_poly(r)


def loops_to_pattern(loops_m: Sequence[Sequence[Pt]], cx: float = 0.0, cy: float = 0.0,
                     angle_deg: float = 0.0, turn_deg: float = 0.0) -> List[List[Pt]]:
    """A face's loops (METRES, in the face frame aruco_autosize.fit_on_loops
    was given) -> mm in the PATTERN frame: the fit put the pattern's centre
    at (cx, cy), its x at angle_deg; the Origin turn then turned it by
    turn_deg more (evaluate's `pl` and `turn`)."""
    a = math.radians(float(angle_deg) + float(turn_deg))
    c, s = math.cos(a), math.sin(a)
    out = []
    for loop in loops_m or ():
        pts = []
        for p in loop:
            dx, dy = float(p[0]) - cx, float(p[1]) - cy
            pts.append(((dx * c + dy * s) * 1000.0, (-dx * s + dy * c) * 1000.0))
        out.append(pts)
    return out


# --------------------------------------------------------- the tag in mm

def _mm(spec: TagSpec):
    """(module, extent rect, quiet modules) in mm."""
    m = spec.module_m * 1000.0
    w, h = (v * 1000.0 for v in spec.extent_m)
    return m, (-w / 2.0, -h / 2.0, w / 2.0, h / 2.0), max(0.0, float(spec.quiet_modules))


def sticker_rect(spec: TagSpec) -> Rect:
    """The sticker: the pattern + its quiet zone, centred."""
    w, h = (v * 1000.0 for v in spec.tile_size_m)
    return (-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)


def quiet_ring(spec: TagSpec) -> float:
    """The clean white (modules) every edge of the black keeps: the quiet
    zone, never under 1 module on a single marker or a grid (the study's
    ring); a ChArUco board's markers keep theirs inside their own squares."""
    q = max(0.0, float(spec.quiet_modules))
    return q if spec.layout == "charuco" else max(q, 1.0)


def keepout_rect(spec: TagSpec, gap: float = WHITE_GAP_MIN) -> Rect:
    """The black grown by the quiet ring and `gap` modules: by default the
    HARD line white-placement ink never crosses (the detector's clear zone)."""
    m, ext, _q = _mm(spec)
    return grow_rect(ext, (quiet_ring(spec) + gap) * m)


def clear_zones(spec: TagSpec, rule: int = RULE) -> Dict[str, Rect]:
    """The two lines a label on the white keeps from the black (mm, pattern
    frame) -- what the ghost draws while the label is placed:

        hard       the detector's clear zone: the quiet ring + WHITE_GAP_MIN.
                   Label ink inside it is a violation (Build anyway).
        preferred  WHITE_GAP_PREF more: auto keeps it when the label still
                   fits; nearer is fine (no violation, no note).
    `rule`: the label's (RULES); rule 1 has one line, 2 modules out."""
    R = RULES.get(rule, RULES[RULE])
    return {"hard": keepout_rect(spec, R.gap_min),
            "preferred": keepout_rect(spec, max(R.gap_pref, R.gap_min))}


def marker_squares(spec: TagSpec) -> List[Tuple[int, Rect]]:
    """(id, black square in mm) of every marker, OpenCV's order."""
    corners = aruco_board.marker_corners_m(board_spec(spec))
    out = []
    for mid in sorted(corners):
        xs = [c[0] * 1000.0 for c in corners[mid]]
        ys = [c[1] * 1000.0 for c in corners[mid]]
        out.append((mid, (min(xs), min(ys), max(xs), max(ys))))
    return out


def charuco_square(spec: TagSpec) -> Rect:
    """The black square a ChArUco board label goes in: the top-left one, or
    the next in the top row when the top-left is white (legacy, even rows)."""
    S = spec.square_length_m * 1000.0
    _m, ext, _q = _mm(spec)
    col = 0 if aruco_board._charuco_black(0, 0, spec.rows, bool(spec.legacy)) else 1
    u0 = ext[0] + col * S
    return (u0, ext[3] - S, u0 + S, ext[3])


def charuco_black_squares(spec: TagSpec) -> List[Rect]:
    """Every black chessboard square of a ChArUco board (mm, centre frame),
    row by row from the top-left (not REF's: label rule 3)."""
    S = spec.square_length_m * 1000.0
    _m, ext, _q = _mm(spec)
    out = []
    for r in range(int(spec.rows)):
        for c in range(int(spec.cols)):
            if aruco_board._charuco_black(c, r, spec.rows, bool(spec.legacy)):
                u0 = ext[0] + c * S
                out.append((u0, ext[3] - (r + 1) * S, u0 + S, ext[3] - r * S))
    return out


def label_square(spec: TagSpec, r: Optional[Rect], rule: int) -> Rect:
    """The black square a ChArUco label at `r` is checked against: the
    top-left one (charuco_square) under rules 1 and 2; from rule 3 the black
    square holding r's centre, if any (not REF's)."""
    if rule is None or rule < ANY_SQUARE_RULE or r is None:
        return charuco_square(spec)
    cu, cv = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
    for sq in charuco_black_squares(spec):
        if sq[0] - TOL <= cu <= sq[2] + TOL and sq[1] - TOL <= cv <= sq[3] + TOL:
            return sq
    return charuco_square(spec)


def charuco_corners_mm(spec: TagSpec) -> List[Pt]:
    """Inner chessboard corners (the ones the detector refines), mm, centre frame."""
    _m, ext, _q = _mm(spec)
    W, H = ext[2] - ext[0], ext[3] - ext[1]
    return [(x * 1000.0 - W / 2.0, H / 2.0 - y * 1000.0)
            for x, y, _z in aruco_board.charuco_corners(board_spec(spec))]


# ----------------------------------------------------------- keep-outs

def mark_keepouts(mark) -> List[List[Pt]]:
    """The corner mark (aruco_chamfer.Mark or its record dict) as polygons
    a label keeps clear of: the cut corner, or the triangle."""
    if not mark:
        return []
    if isinstance(mark, dict):
        kind, cut, solid = mark.get("kind"), mark.get("cut") or [], mark.get("solid") or []
    else:
        kind, cut, solid = mark.kind, mark.cut, mark.solid
    pts = cut if kind in ("tile_cut", "black_cut") else solid if kind == "triangle" else []
    return [[tuple(map(float, p)) for p in pts]] if len(pts) >= 3 else []


def pin_keepouts(outlines: Sequence[dict], centre: Pt = (0.0, 0.0), segments: int = 24
                 ) -> List[List[Pt]]:
    """aruco_slabs.pin_outlines (tile-centre frame) as polygons in the
    pattern frame, the tile centred at `centre`; a circle as a polygon drawn
    AROUND it (never inside)."""
    out = []
    for o in outlines or ():
        if o.get("kind") == "circle":
            (u, v), r = o["c"], o["r"] / math.cos(math.pi / segments)
            out.append([(centre[0] + u + r * math.cos(2 * math.pi * k / segments),
                         centre[1] + v + r * math.sin(2 * math.pi * k / segments))
                        for k in range(segments)])
        elif o.get("pts"):
            out.append([(centre[0] + p[0], centre[1] + p[1]) for p in o["pts"]])
    return out


def mark_on_tile(spec: TagSpec, mode: str, op: Optional[str], tile: Rect):
    """aruco_chamfer's corner mark for a white tile that is NOT centred on
    the pattern (a tile grown by a label strip): its cut stays at the
    tile's own top-left corner, its legs by the same rule."""
    from . import chamfer as C
    tw, th = -2.0 * tile[0], 2.0 * tile[3]           # a centred tile with that top-left corner
    mk = C.mark_for_spec(spec, mode, op, (tw, th))
    if mk.kind == "tile_cut":
        mk.outline = C.cut_rect(tile, mk.leg)
    return mk


def _pins_on(tile: Rect, pins: Optional[dict], cut: float, notes: List[str]) -> List[List[Pt]]:
    """The locating pins of a tile (pins: {"shape", "size", "margin"}), as
    keep-out polygons, or [] (with a note when they do not fit)."""
    if not pins or pins.get("shape") not in ("triangle", "round"):
        return []
    from . import slabs as SL
    tw, th = tile[2] - tile[0], tile[3] - tile[1]
    try:
        outs = SL.pin_outlines(pins["shape"], float(pins.get("size", SL.PIN_SIZE_MM)), tw, th,
                               float(pins.get("margin", SL.PIN_MARGIN_MM)), cut=cut)
    except ValueError as exc:
        notes.append(f"label: {exc}")
        return []
    return pin_keepouts(outs, ((tile[0] + tile[2]) / 2.0, (tile[1] + tile[3]) / 2.0))


def _clear_of(r: Rect, polys: Sequence[Sequence[Pt]], d: float) -> bool:
    P = rect_poly(r)
    return all(poly_dist(P, q) >= d - TOL for q in polys)


# --------------------------------------------------------------- layout

def _caps(hi: float, lo: float, typed: bool) -> List[float]:
    """Candidate caps, biggest first: `hi` when typed, then the 0.1 mm grid
    down to `lo`, and `lo` itself (the smallest printable: an auto cap never
    rounds away the only one that prints)."""
    if hi < lo - EPS:
        return []
    out = [hi] if typed else []
    k = math.floor(hi / CAP_STEP_MM + 1e-6)
    while k * CAP_STEP_MM >= lo - EPS:
        c = round(k * CAP_STEP_MM, 6)
        if not out or c < out[-1] - EPS:
            out.append(c)
        k -= 1
    if not out or out[-1] > lo + EPS:
        out.append(round(lo, 6))
    return out


def _largest(caps: List[float], ok) -> Optional[float]:
    """The largest cap in `caps` (descending) for which ok(cap) holds;
    ok must be monotone (a smaller block fits wherever a bigger one did)."""
    if not caps or not ok(caps[-1]):
        return None
    lo, hi = len(caps) - 1, 0                     # ok at lo; find the smallest index ok
    if ok(caps[0]):
        return caps[0]
    while lo - hi > 1:
        mid = (lo + hi) // 2
        if ok(caps[mid]):
            lo = mid
        else:
            hi = mid
    return caps[lo]


def _dims(lines, M, rot) -> Tuple[float, float]:
    """The block's (u, v) size once turned."""
    w, h = block_size(lines, M)
    return (w, h) if rot % 180 == 0 else (h, w)


def _fit_in(rect: Rect, rot: int, arrangements: List[List[str]], cap_hi: float,
            s: LabelSettings, typed: bool) -> Optional[Tuple[float, List[str]]]:
    """The largest cap (and the arrangement) whose block fits in `rect`."""
    rw, rh = rect[2] - rect[0], rect[3] - rect[1]
    caps = _caps(cap_hi, min_cap(s.nozzle_mm, s.stroke_mm), typed)
    best = None
    for lines in arrangements:
        def ok(c, lines=lines):
            du, dv = _dims(lines, metrics(c, s.nozzle_mm, s.stroke_mm), rot)
            return du <= rw + TOL and dv <= rh + TOL
        c = _largest(caps, ok)
        if c is not None and (best is None or c > best[0] + EPS):
            best = (c, lines)
    return best


def _part(slot_i: int, slot: Slot, cand: "Cand", lines: List[str], cap: float,
          s: LabelSettings) -> Part:
    M = metrics(cap, s.nozzle_mm, s.stroke_mm)
    du, dv = _dims(lines, M, slot.rot)
    r = slot.rect
    # the shift (an offset along a black row), never past the rect's edge:
    # a copy's wider text stays inside
    hx, hy = max(0.0, r[2] - r[0] - du) / 2.0, max(0.0, r[3] - r[1] - dv) / 2.0
    centre = ((r[0] + r[2]) / 2.0 + max(-hx, min(hx, slot.shift[0])),
              (r[1] + r[3]) / 2.0 + max(-hy, min(hy, slot.shift[1])))
    boxes = block_boxes(lines, M, centre, slot.rot)
    rect = ink_rect(boxes) or (centre[0], centre[1], centre[0], centre[1])
    feats = [M.min_feature] + ([M.line_gap] if len(lines) > 1 else [])
    if slot.bound is not None:          # the black left around knocked-out text
        b = slot.bound
        feats.append(min(rect[0] - b[0], b[2] - rect[2], rect[1] - b[1], b[3] - rect[3]))
    return Part(slot=slot_i, text=cand.text, lines=list(lines), cap=cap, stroke=M.stroke,
                min_feature=min(feats), rect=rect, boxes=boxes, short=cand.short,
                full=cand.full if cand.short else "")


@dataclass(frozen=True)
class Cand:
    """One way to write a place's share of the label: the text, the text it
    is SIZED with (resolve_text sizing), and how it was shortened."""
    text: str
    sizing: str
    short: str = ""                # "" | "tail" | "cut"
    full: str = ""                 # the unshortened text


def _cands(s: LabelSettings, spec: TagSpec, slot: Slot, name: str, key: str,
           cut: bool = True) -> List[Cand]:
    """A place's text, best first: as written; a {name} path's last element
    ("Arm:2/Actuator:3" -> "Actuator:3"); then (cut=True) the name cut short
    with "..." keeping its occurrence number -- or, with no {name} and no
    id in it, the text cut from its end. An id is never cut."""
    tpl = part_template(s.template(), slot.part)
    mid = spec.ids[slot.marker] if slot.marker is not None else None
    out: List[Cand] = []
    seen = set()

    def add(n, short, text=None):
        t = text if text is not None else resolve_text(tpl, spec, marker_id=mid, name=n, key=key)
        z = text if text is not None else resolve_text(tpl, spec, marker_id=mid, name=n, key=key,
                                                       sizing=True)
        if t and t not in seen:
            seen.add(t)
            out.append(Cand(t, z, short, full))
    full = resolve_text(tpl, spec, marker_id=mid, name=name, key=key)
    if "{name}" in tpl:
        for i, n in enumerate(name_variants(name)):
            add(n, "" if i == 0 else "tail")
        if cut:
            for n in name_cuts(name):
                add(n, "cut")
    else:
        add(name, "")
        if cut and full and not _ID_TOKEN.search(tpl):
            for t in text_cuts(full):
                add(name, "cut", t)
    return out


def _first_fit(cands: List[Cand], fits):
    """(index, result) of the first candidate `fits` accepts: the whole and
    tail forms in order, then the LONGEST cut form (a bisection: a shorter
    cut fits wherever a longer one did). None when none does."""
    whole = [i for i, c in enumerate(cands) if c.short != "cut"]
    for i in whole:
        r = fits(cands[i])
        if r is not None:
            return i, r
    cut = [i for i, c in enumerate(cands) if c.short == "cut"]
    if not cut:
        return None
    r_last = fits(cands[cut[-1]])
    if r_last is None:
        return None
    lo, hi, best = 0, len(cut) - 1, (cut[-1], r_last)   # cut[hi] fits
    while lo < hi:
        mid = (lo + hi) // 2
        r = fits(cands[cut[mid]])
        if r is not None:
            hi, best = mid, (cut[mid], r)
        else:
            lo = mid + 1
    return best


def _short_note(part: Part, slot: Slot) -> Optional[str]:
    """One line when a place could not hold its text whole."""
    def shown(t):
        return t.replace(LINE_BREAK, " ") if slot.lines == 1 else t
    where = _where(slot)
    if part.short == "tail":
        return f"label: {shown(part.full)!r} written as {shown(part.text)!r} to fit {where}"
    if part.short == "cut":
        return (f"label: {shown(part.full)!r} cut short to {shown(part.text)!r} -- {where} "
                f"does not hold it whole at the smallest printable size")
    return None


def _where(slot: Slot) -> str:
    return {"bottom": "the bottom row", "top": "the top row", "square": "the black square"
            }.get(slot.where, f"the white ({slot.where})")


def _lay(slot_i: int, slot: Slot, cands: List[Cand], s: LabelSettings,
         notes: List[str]) -> Optional[Part]:
    """A copy's (or the template's) text in a slot that is already sized:
    at the slot's cap when it fits, else shrunk, else cut short (with a
    note); never under the printable cap."""
    def fits(c):
        arr = wraps(_drawn(c.text), slot.lines)
        return _fit_in(slot.rect, slot.rot, arr, slot.cap, s, typed=True) if arr else None
    got = _first_fit(cands, fits)
    if got is None:
        if cands:
            notes.append(f"label: {cands[0].text!r} does not fit {_where(slot)} at the "
                         f"smallest printable size ({min_cap(s.nozzle_mm, s.stroke_mm):.2f} mm "
                         f"cap at a {s.nozzle_mm:g} mm nozzle)")
        return None
    i, (cap, lines) = got
    part = _part(slot_i, slot, cands[i], lines, cap, s)
    note = _short_note(part, slot)
    if note:
        notes.append(note)
    return part


def _drawn(text: str) -> str:
    """normalize() each line, keeping the "|" breaks."""
    return LINE_BREAK.join(normalize(p)[0] for p in text.split(LINE_BREAK))


def _missing_note(text: str) -> Optional[str]:
    miss = []
    for p in text.split(LINE_BREAK):
        for ch in normalize(p)[1]:
            if ch not in miss:
                miss.append(ch)
    if miss:
        return ("label: the font has no " + " ".join(repr(c) for c in miss)
                + " -- printed as '?'")
    return None


# ------------------------------------------------------------ black placement

def _cap_rule(rule: float, s: LabelSettings, where: str, notes: List[str]) -> Tuple[float, bool]:
    """(the cap to start from, typed?) -- a typed cap above the rule is
    clamped, with a note."""
    if s.cap_mm > 0:
        if s.cap_mm > rule + TOL:
            notes.append(f"label: cap {s.cap_mm:g} mm is over the {rule:.2f} mm {where} "
                         f"allows -- clamped")
            return rule, True
        return float(s.cap_mm), True
    return rule, False


def _sized_slot(slot: Slot, cands: List[Cand], cap_hi: float, typed: bool,
                s: LabelSettings) -> Optional[float]:
    """The cap a slot gets: the largest its SIZING text fits at (every
    copy's id fits too), for the first candidate whose own text fits at all;
    its own largest when the sizing text does not."""
    def fits(c):
        arr = wraps(_drawn(c.text), slot.lines)
        return _fit_in(slot.rect, slot.rot, arr, cap_hi, s, typed) if arr else None
    got = _first_fit(cands, fits)
    if got is None:
        return None
    i, (cap, _lines) = got
    sz = _fit_in(slot.rect, slot.rot, wraps(_drawn(cands[i].sizing), slot.lines), cap_hi, s,
                 typed)
    return sz[0] if sz is not None else cap


def _scope(spec: TagSpec, s: LabelSettings) -> str:
    if spec.layout == "single":
        return "first"
    return "each" if s.scope == "auto" else s.scope


def _row_rect(sq: Rect, m: float, where: str) -> Tuple[Rect, Rect]:
    """(the text's band, the black around it) in one marker's border row."""
    x0, y0, x1, y1 = sq
    u0, u1 = x0 + (1.0 + CORNER_CLEAR) * m, x1 - (1.0 + CORNER_CLEAR) * m
    if where == "top":
        return ((u0, y1 - (1.0 - BLACK_EDGE) * m, u1, y1 - BLACK_EDGE * m),
                (x0 + m, y1 - m, x1 - m, y1))
    return ((u0, y0 + BLACK_EDGE * m, u1, y0 + (1.0 - BLACK_EDGE) * m),
            (x0 + m, y0, x1 - m, y0 + m))


ROW_PARTS = {"bottom": (("bottom", "all"),), "top": (("top", "all"),),
             "both": (("bottom", "first"), ("top", "rest"))}


def _plan_black(spec: TagSpec, s: LabelSettings, name: str, key: str, keep: List[List[Pt]],
                notes: List[str], cut: bool = True) -> Label:
    """The label on the black: border rows (bottom / top / both: line 1 at
    the bottom, the rest at the top) of each marker or the first, or a
    ChArUco board's black square. On a board a line that reads the same on
    every marker (no {id} in it: a name) is written once, on the first."""
    m, ext, _q = _mm(spec)
    lab = Label(kind="black", role="cut", settings=s)
    row = s.black_row(spec.layout)
    if s.row == "square" and row != "square":
        notes.append("label: a black square is a ChArUco board's -- both rows used")
    clear = max(KEEPOUT_MM, KEEPOUT * m)
    slots: List[Slot] = []
    lab.side = row
    if row == "square":
        S = spec.square_length_m * 1000.0
        sq = charuco_square(spec)
        e = max(SQUARE_EDGE * S, m)
        inner = (sq[0] + e, sq[1] + e, sq[2] - e, sq[3] - e)
        corners = charuco_corners_mm(spec)
        cap_hi, typed = _cap_rule(SQUARE_CAP * S, s, "a ChArUco square", notes)
        c0 = ((sq[0] + sq[2]) / 2.0, (sq[1] + sq[3]) / 2.0)
        caps = _caps(cap_hi, min_cap(s.nozzle_mm, s.stroke_mm), typed)

        def centred(du, dv):
            return (c0[0] - du / 2.0, c0[1] - dv / 2.0, c0[0] + du / 2.0, c0[1] + dv / 2.0)

        def ok_rect(r):
            return (r[0] >= inner[0] - TOL and r[2] <= inner[2] + TOL and r[1] >= inner[1] - TOL
                    and r[3] <= inner[3] + TOL
                    and all(rect_point_dist(r, p) >= SQUARE_CORNER * S - TOL for p in corners)
                    and _clear_of(r, keep, clear))

        def best_for(text):
            best = None
            for lines in wraps(_drawn(text), MAX_LINES):
                c = _largest(caps, lambda c, lines=lines: ok_rect(centred(*_dims(
                    lines, metrics(c, s.nozzle_mm, s.stroke_mm), 0))))
                if c is not None and (best is None or c > best[0] + EPS):
                    best = (c, lines)
            return best
        probe = Slot("square", sq, 0, 0.0, MAX_LINES, None, sq)
        cands = _cands(s, spec, probe, name, key, cut)
        got = _first_fit(cands, lambda c: best_for(c.text))
        if got is None:
            notes.append(f"label: nothing printable fits the ChArUco square ({S:.1f} mm) clear "
                         f"of its corner -- smallest cap "
                         f"{min_cap(s.nozzle_mm, s.stroke_mm):.2f} mm")
            lab.kind = "none"
            return lab
        i, (c, lines) = got
        sized = best_for(cands[i].sizing)        # room for every copy's id, when there is
        if sized is not None:
            c, lines = sized
        du, dv = _dims(lines, metrics(c, s.nozzle_mm, s.stroke_mm), 0)
        lab.slots = [Slot("square", centred(du, dv), 0, c, MAX_LINES, None, sq)]
        return lab
    squares = marker_squares(spec)
    scope = _scope(spec, s)
    cap_hi, typed = _cap_rule(BLACK_CAP * m, s, "a border row", notes)
    for where, part in ROW_PARTS[row]:
        tpl = part_template(s.template(), part)
        if not resolve_text(tpl, spec, name=name, key=key).replace(LINE_BREAK, ""):
            continue                           # "#id" has no second line for the top row
        per_marker = scope == "each" and len(squares) > 1 and "{id}" in tpl
        for i in (range(len(squares)) if per_marker else [0]):
            rect, bound = _row_rect(squares[i][1], m, where)
            if not _clear_of(rect, keep, clear):
                notes.append(f"label: marker #{spec.ids[i]}'s {where} row meets a corner mark "
                             "or a pin -- skipped")
                continue
            slots.append(Slot(where, rect, 0, 0.0, 1, i if per_marker else None, bound, part, i))
    if not slots:
        lab.kind = "none"
        return lab
    for sl in slots:
        cands = _cands(s, spec, sl, name, key, cut)
        c = _sized_slot(sl, cands, cap_hi, typed, s)
        if c is None:
            lab.kind = "none"
            text = cands[0].text if cands else ""
            notes.append(
                f"label: {text!r} does not print in a {m:.2f} mm module's {sl.where} row -- "
                f"its cap can be {cap_hi:.2f} mm at most, a {s.nozzle_mm:g} mm nozzle needs "
                f"{min_cap(s.nozzle_mm, s.stroke_mm):.2f} mm (and the row is "
                f"{sl.rect[2] - sl.rect[0]:.1f} mm long); put it on the white, use a "
                f"bigger marker or a finer nozzle")
            return lab
        sl.cap = c
        if typed and s.cap_mm > 0 and c < min(cap_hi, s.cap_mm) - EPS:
            notes.append(f"label: cap {s.cap_mm:g} mm does not fit the {sl.where} row -- "
                         f"shrunk to {c:.2f} mm")
    lab.slots = slots
    return lab


# ------------------------------------------------------------ white placement

def _side_box(side: str, R: Rect, du: float, dv: float, along: float, out: float,
              centre: float) -> Rect:
    """A du x dv box just outside the keep-out rect R on `side`, `out` mm
    further out and `along` mm along the side from `centre`."""
    if side == "below":
        c = centre + along
        return (c - du / 2.0, R[1] - out - dv, c + du / 2.0, R[1] - out)
    if side == "above":
        c = centre + along
        return (c - du / 2.0, R[3] + out, c + du / 2.0, R[3] + out + dv)
    if side == "left":
        c = centre + along
        return (R[0] - out - du, c - dv / 2.0, R[0] - out, c + dv / 2.0)
    c = centre + along
    return (R[2] + out, c - dv / 2.0, R[2] + out + du, c + dv / 2.0)


def _free_spans(loops, polys, along_u: bool, lo: float, hi: float) -> List[Tuple[float, float]]:
    """Where a band lies wholly on the region: the band is lo..hi across
    (v when the label slides along u, else u); -> the intervals along it
    that no boundary segment crosses and that are inside (even-odd), and
    that miss every keep-out polygon (already grown). Exact for polygons."""
    blocked = []

    def clip(p, q):
        if along_u:
            (pa, pc), (qa, qc) = (p[0], p[1]), (q[0], q[1])
        else:
            (pa, pc), (qa, qc) = (p[1], p[0]), (q[1], q[0])
        if (pc < lo - TOL and qc < lo - TOL) or (pc > hi + TOL and qc > hi + TOL):
            return None
        if abs(qc - pc) < EPS:
            return (min(pa, qa), max(pa, qa))
        t0, t1 = (lo - pc) / (qc - pc), (hi - pc) / (qc - pc)
        t0, t1 = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
        a0, a1 = pa + (qa - pa) * t0, pa + (qa - pa) * t1
        return (min(a0, a1), max(a0, a1))
    for loop in list(loops) + list(polys):
        for i in range(len(loop)):
            r = clip(loop[i - 1], loop[i])
            if r is not None:
                blocked.append(r)
    for poly in polys:                     # a keep-out spanning the whole band
        cs = [(p[1] if along_u else p[0]) for p in poly]
        if min(cs) <= lo and max(cs) >= hi:
            av = [(p[0] if along_u else p[1]) for p in poly]
            blocked.append((min(av), max(av)))
    blocked.sort()
    merged: List[List[float]] = []
    for a, b in blocked:
        if merged and a <= merged[-1][1] + TOL:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    edges = [-math.inf] + [v for ab in merged for v in ab] + [math.inf]
    out = []
    mid_c = (lo + hi) / 2.0
    for a, b in zip(edges[0::2], edges[1::2]):
        if not (b - a > TOL) or math.isinf(a) or math.isinf(b):
            continue
        m = (a + b) / 2.0
        if _inside(loops, m, mid_c) if along_u else _inside(loops, mid_c, m):
            out.append((a, b))
    return out


FAR_STEPS = 64             # the far search scans at most this many distances, then refines


def _place_on_region(side: str, R: Rect, du: float, dv: float, centre: float, loops, polys,
                     e: float, clear: float, step: float, reach: float, start: float = 0.0,
                     exact: bool = True) -> Optional[Rect]:
    """The du x dv box on `side` of R nearest the tag: for each distance out
    (start, + step, ... up to `reach`), the free spans of its band (grown by
    the edge margin), the spot along it nearest the tag's axis (two equally
    near: the right one, or the upper one on a left / right side). A long
    reach is scanned in at most FAR_STEPS strides, then the stride that
    found room again at `step`. exact=False (rule 1): the first of two
    equally near spots, the grid of steps only."""
    along_u = side in ("below", "above")
    length = du if along_u else dv
    grown = [_grow_poly(p, clear) for p in polys]

    def at(out):
        b0 = _side_box(side, R, du, dv, 0.0, out, centre)
        lo, hi = (b0[1] - e, b0[3] + e) if along_u else (b0[0] - e, b0[2] + e)
        best = None
        for a, b in _free_spans(loops, grown, along_u, lo, hi):
            if b - a < length + 2.0 * e - TOL:
                continue
            c = min(max(centre, a + e + length / 2.0), b - e - length / 2.0)
            if (best is None or abs(c - centre) < abs(best - centre) - EPS
                    or (exact and abs(abs(c - centre) - abs(best - centre)) <= EPS
                        and c > best)):
                best = c
        return None if best is None else _side_box(side, R, du, dv, best - centre, out, centre)

    def scan(a, b, s):
        n = int((b - a) / s + 1e-9)
        for k in range(n + 1):
            got = at(a + k * s)
            if got is not None:
                return got, a + k * s
        if exact and b - (a + n * s) > EPS:
            got = at(b)
            if got is not None:
                return got, b
        return None, None
    if reach < start - EPS:
        return None
    stride = max(step, (reach - start) / FAR_STEPS)
    if stride <= step + EPS:
        return scan(start, reach, step)[0]
    got, out = scan(start, reach, stride)
    if got is None or out <= start + EPS:
        return got
    fine, _o = scan(max(start, out - stride + step), out, step)
    return fine or got


def _clear_on(loops, r: Rect, d: float) -> bool:
    """Exact: the rect r lies on the region (loops, even-odd: never over a
    hole, never off it) and no edge of the region comes nearer than d, as
    the crow flies (what label_violations measures; the band scan's square
    margin is stricter at a curve)."""
    if not _rect_inside(loops, (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0, r[2] - r[0],
                        r[3] - r[1]):
        return False
    corners = rect_poly(r)
    for loop in loops:
        for i in range(len(loop)):
            a, b = loop[i - 1], loop[i]
            if (min(a[0], b[0]) > r[2] + d or max(a[0], b[0]) < r[0] - d
                    or min(a[1], b[1]) > r[3] + d or max(a[1], b[1]) < r[1] - d):
                continue
            if rect_point_dist(r, a) < d - TOL or rect_point_dist(r, b) < d - TOL:
                return False
            if any(_seg_pt(c, a, b) < d - TOL for c in corners):
                return False
    return True


def _grow_poly(poly: Sequence[Pt], d: float) -> List[Pt]:
    """A convex polygon's box grown by d -- a conservative keep-out for the
    band scan (corner marks and pins are small and near-square)."""
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return rect_poly((min(xs) - d, min(ys) - d, max(xs) + d, max(ys) + d))


def _deeper(r: Rect, side: str, d: float) -> Rect:
    """A rect grown by d on one side."""
    if side == "below":
        return (r[0], r[1] - d, r[2], r[3])
    if side == "above":
        return (r[0], r[1], r[2], r[3] + d)
    if side == "left":
        return (r[0] - d, r[1], r[2], r[3])
    return (r[0], r[1], r[2] + d, r[3])


def _grown(tile: Rect, box: Rect, e: float) -> Rect:
    return (min(tile[0], box[0] - e), min(tile[1], box[1] - e),
            max(tile[2], box[2] + e), max(tile[3], box[3] + e))


def _far_reach(side: str, R: Rect, loops) -> float:
    """How far past R the face reaches on `side` (mm): the far search's end."""
    pts = [q for lp in loops for q in lp]
    if not pts:
        return 0.0
    if side == "below":
        return R[1] - min(q[1] for q in pts)
    if side == "above":
        return max(q[1] for q in pts) - R[3]
    if side == "left":
        return R[0] - min(q[0] for q in pts)
    return max(q[0] for q in pts) - R[2]


def _plan_white(spec: TagSpec, s: LabelSettings, name: str, key: str, *, mode: str,
                op: Optional[str], region, grow: bool, bounds, tile: Rect, mark, pins,
                keep: List[List[Pt]], notes: List[str], cut: bool = True) -> Label:
    """The label on the white, placed by the rules. In order, until one
    finds room (Zach, 2026-10-13: "find the closest valid spot: out of the
    quiet zone, near the bottom, not on a hole, still on the face"):

        1  WHITE_GAP_PREF beyond the quiet ring, within REACH modules
        2  the hard line itself (WHITE_GAP_MIN), within REACH modules
        3, 4  the same two, further out -- as far as the face goes
              (a region only: a strip grows where it needs to)

    In each, every side asked for (auto: all four) gets its biggest text
    at its spot nearest the tag; the least shortened text wins, then the
    first side in the order (below, above, right, left) whose text is at
    least SIDE_SLACK of the biggest, then the biggest."""
    m, ext, _q = _mm(spec)
    lab = Label(kind="white", role="add", settings=s)
    e = max(WHITE_EDGE * m, EDGE_MIN_MM)
    clear = max(KEEPOUT_MM, KEEPOUT * m)
    step = max(0.5, 0.25 * m)                # how far a label moves at a time
    cap_hi, typed = _cap_rule(WHITE_LIMIT * m if s.cap_mm > 0 else WHITE_CAP * m, s,
                              "the white", notes)
    caps = _caps(cap_hi, min_cap(s.nozzle_mm, s.stroke_mm), typed)
    cands = _cands(s, spec, Slot("white", tile, 0, 0.0, MAX_LINES), name, key, cut)
    sides = [s.side] if s.side in SIDE_ORDER else list(SIDE_ORDER)
    loops = [lp for lp in (_clean(l) for l in (region or ())) if len(lp) >= 3] if region else []
    bnd = [lp for lp in (_clean(l) for l in (bounds or ())) if len(lp) >= 3] if bounds else []
    if region is not None and not loops:
        notes.append("label: the white around the tag has no outline")
    if not loops and not grow:
        lab.kind = "none"
        notes.append("label: no white to put it on -- the tag has no white of its own around "
                     "it (Black only on a sketch with no body; or allow the tile to grow)")
        return lab
    if not caps:
        lab.kind = "none"
        notes.append(f"label: {s.cap_mm:g} mm letters are under the smallest a "
                     f"{s.nozzle_mm:g} mm nozzle prints "
                     f"({min_cap(s.nozzle_mm, s.stroke_mm):.1f} mm)")
        return lab
    tile_cut = mark is not None and (mark.get("kind") if isinstance(mark, dict)
                                     else mark.kind) == "tile_cut"
    centre_u, centre_v = (ext[0] + ext[2]) / 2.0, (ext[1] + ext[3]) / 2.0
    rl = rule_of(s)                                  # the rule it is made under
    gaps = [rl.gap_pref, rl.gap_min] if rl.gap_pref > rl.gap_min + EPS else [rl.gap_min]
    phases = [(g, False) for g in gaps] + ([(g, True) for g in gaps]
                                           if loops and rl.far else [])
    tries = []          # (candidate, cap, side order index, side, lines, box, white or None)
    for gap, far in phases:
        R = keepout_rect(spec, gap)
        for si, side in enumerate(sides):
            rot = SIDE_ROT[side]
            centre = centre_u if side in ("below", "above") else centre_v
            if loops:
                start, reach = 0.0, REACH * m
                if far:
                    start, reach = REACH * m + step, _far_reach(side, R, loops)
                    if reach < start:
                        continue

                def place(c, lines, side=side, rot=rot, centre=centre, R=R, start=start,
                          reach=reach):
                    du, dv = _dims(lines, metrics(c, s.nozzle_mm, s.stroke_mm), rot)
                    b = _place_on_region(side, R, du, dv, centre, loops, keep, e, clear, step,
                                         reach, start, rl.exact)
                    # re-checked exactly: inside the region with its margin, clear of
                    # every keep-out polygon as drawn
                    if b is None or not _rect_inside(
                            loops, (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0,
                            b[2] - b[0] + 2.0 * e, b[3] - b[1] + 2.0 * e) \
                            or not _clear_of(b, keep, clear):
                        return None
                    return b, None
            else:
                long_ = (tile[2] - tile[0]) if side in ("below", "above") else (tile[3] - tile[1])
                tcentre = ((tile[0] + tile[2]) / 2.0 if side in ("below", "above")
                           else (tile[1] + tile[3]) / 2.0)

                def place(c, lines, side=side, rot=rot, centre=centre, R=R, long_=long_,
                          tcentre=tcentre):
                    du, dv = _dims(lines, metrics(c, s.nozzle_mm, s.stroke_mm), rot)
                    if (du if side in ("below", "above") else dv) > long_ - 2.0 * e + TOL:
                        return None
                    b = _side_box(side, R, du, dv, tcentre - centre, 0.0, centre)
                    base = _grown(tile, b, e)
                    # the cut corner and the pins sit at the grown tile's
                    # corners, level with the text: a deeper strip (up to
                    # REACH more) takes them past it before the text shrinks
                    for k in range(int(REACH * m / step + 1e-9) + 1):
                        white = _deeper(base, side, k * step) if base != tile else base
                        if bnd and not _rect_inside(bnd, (white[0] + white[2]) / 2.0,
                                                    (white[1] + white[3]) / 2.0,
                                                    white[2] - white[0], white[3] - white[1]):
                            return None
                        polys = list(keep)
                        leg = 0.0
                        if tile_cut:
                            mk = mark_on_tile(spec, mode, op, white)
                            polys += mark_keepouts(mk)
                            leg = mk.leg if mk.kind == "tile_cut" else 0.0
                        polys += _pins_on(white, pins, leg, [])
                        if _clear_of(b, polys, clear):
                            return b, white
                        if white == tile:
                            return None
                    return None

            def search(text, place=place):
                """(cap, lines, box, white) for a text on this side, or None."""
                best = None
                for k, lines in enumerate(wraps(_drawn(text), MAX_LINES)):
                    hit = {}

                    def ok(c, lines=lines):
                        r = place(c, lines)
                        if r is not None:
                            hit[c] = r
                        return r is not None
                    # the strip's pins move with the strip: scan, do not bisect
                    c = (next((c for c in caps if ok(c)), None) if not loops
                         else _largest(caps, ok))
                    if c is None:
                        continue
                    if c not in hit:
                        ok(c)
                    res = (c, lines, hit[c][0], hit[c][1])
                    if k == 0 and c >= max(ONE_LINE * m, caps[-1]) - EPS:
                        return res                  # as written (one line) is big enough
                    if best is None or c > best[0] + EPS:
                        best = res
                return best

            def fits(cand, search=search):
                # sized for every copy's id when that fits, else for its own text
                r = search(cand.sizing)
                return r if r is not None or cand.sizing == cand.text else search(cand.text)
            got = _first_fit(cands, fits)
            if got is not None:
                i, (c, lines, box, white) = got
                tries.append((i, c, si, side, lines, box, white))
        if tries:
            break
    if not tries:
        lab.kind = "none"
        where = "the white around it" if loops else "a label strip"
        need = min_cap(s.nozzle_mm, s.stroke_mm)
        zone = ("outside the detector's clear zone" if rl.exact else
                f"{quiet_ring(spec) + rl.gap_min:g} modules clear of the black")
        notes.append(f"label: no room on {where} for {cands[0].text!r} {zone}, even at "
                     f"{need:.1f} mm letters (the smallest a {s.nozzle_mm:g} mm nozzle prints)"
                     if cands else "label: the text is empty")
        return lab
    # the least shortened text first; then the first side in the order whose
    # text is nearly the biggest (SIDE_SLACK), the biggest among equals
    least = min(t[0] for t in tries)
    pool = [t for t in tries if t[0] == least]
    top = max(t[1] for t in pool)
    pool = [t for t in pool if t[1] >= rl.slack * top - EPS]
    pool.sort(key=lambda t: (t[2], -round(t[1], 6)))
    _i, cap, _si, side, lines, box, white = pool[0]
    if typed and s.cap_mm > 0 and cap < min(cap_hi, s.cap_mm) - EPS:
        notes.append(f"label: cap {s.cap_mm:g} mm does not fit {side} -- shrunk to {cap:.2f} mm")
    lab.side = side
    lab.slots = [Slot(side, box, SIDE_ROT[side], cap, MAX_LINES, None, None)]
    if white is not None and white != tile:
        lab.white = white
        lab.strip = _strip(tile, white)
    return lab


def _strip(tile: Rect, white: Rect) -> Rect:
    """The rectangle a grown white added (one side)."""
    if white[1] < tile[1] - EPS:
        return (white[0], white[1], white[2], tile[1])
    if white[3] > tile[3] + EPS:
        return (white[0], tile[3], white[2], white[3])
    if white[0] < tile[0] - EPS:
        return (white[0], white[1], tile[0], white[3])
    return (tile[2], white[1], white[2], white[3])


# ---------------------------------------------- what breaks, and the preview
#
# Zach, 2026-10-11: "It should always show me the preview... but it can show
# a warning type thing... I should always be able to see the label even if
# the linter is saying its going to cause an error." A label that cannot be
# placed inside the rules is still LAID OUT where it was asked for (`_force`)
# with what it breaks in plain words (`label_violations`): plan_label hands
# it back as Label.preview, built only when settings.build_anyway.

def _mm1(v: float) -> str:
    """A distance in a message: one decimal, two under 0.1 mm."""
    return f"{v:.1f}" if v >= 0.095 else f"{v:.2f}"


def _intrusion(r: Rect, R: Rect) -> float:
    """How far rect r reaches into rect R: the shortest move that clears
    it (0 when they do not share area)."""
    if not _overlaps(r, R):
        return 0.0
    return min(r[2] - R[0], R[2] - r[0], r[3] - R[1], R[3] - r[1])


def _rect_samples(r: Rect, n: int = 8) -> List[Pt]:
    out = []
    for k in range(n + 1):
        t = k / float(n)
        u, v = r[0] + (r[2] - r[0]) * t, r[1] + (r[3] - r[1]) * t
        out += [(u, r[1]), (u, r[3]), (r[0], v), (r[2], v)]
    return out


def _loop_dist(p: Pt, loop: Sequence[Pt]) -> float:
    """A point to a closed polygon's boundary (any shape)."""
    return min(_seg_pt(p, loop[i - 1], loop[i]) for i in range(len(loop)))


def _in_rect(r: Rect, p: Pt) -> bool:
    return r[0] - TOL <= p[0] <= r[2] + TOL and r[1] - TOL <= p[1] <= r[3] + TOL


def label_violations(spec: TagSpec, lab: Label, *, loops=(), bounds=(),
                     keep: Sequence[Sequence[Pt]] = (), strip: bool = False) -> List[str]:
    """The rules a laid-out label breaks, in plain words and by how much:
    letters too small for the nozzle; on the black, letters taller than the
    border row allows, past its black margin, into the corner cells, out of
    a ChArUco square or too near its corners; on the white, into the
    detector's clear zone (the HARD line, `clear_zones`: nearer than auto's
    preferred margin is not a violation), off the face, near its edge,
    over or near a hole, on a corner mark or a pin, a strip growing off the
    face. Short, to follow "Label not built: ". [] = inside every rule;
    on the white nothing under POS_TOL_MM counts."""
    out: List[str] = []
    if lab.kind == "none" or not lab.parts:
        return out
    m, ext, _q = _mm(spec)
    s = lab.settings
    need = min_cap(s.nozzle_mm, s.stroke_mm)
    low = min(p.cap for p in lab.parts)
    if low < need - TOL:
        out.append(f"{low:.1f} mm letters at a {s.nozzle_mm:g} mm nozzle won't print cleanly "
                   f"(strokes {low / GLYPH_ROWS:.2f} mm; the nozzle needs {need:.1f} mm letters)")
    clear = max(KEEPOUT_MM, KEEPOUT * m)
    if lab.kind == "black":
        squares = marker_squares(spec)
        for p in lab.parts:
            sl = lab.slots[p.slot]
            r = p.rect
            if sl.where == "square":
                S = spec.square_length_m * 1000.0
                sq = label_square(spec, r, s.rule)
                off = max(sq[0] - r[0], r[2] - sq[2], sq[1] - r[1], r[3] - sq[3], 0.0)
                if off > TOL:
                    out.append(f"{p.text!r} runs {off:.1f} mm out of the black square")
                d = min((rect_point_dist(r, c) for c in charuco_corners_mm(spec)),
                        default=math.inf)
                if d < SQUARE_CORNER * S - TOL:
                    out.append(f"{p.text!r} is {d:.1f} mm from a ChArUco corner (it needs "
                               f"{SQUARE_CORNER * S:.1f} mm)")
            else:
                idx = sl.square if sl.square is not None else (sl.marker or 0)
                if idx >= len(squares):
                    continue
                x0, y0, x1, y1 = squares[idx][1]
                if p.cap > BLACK_CAP * m + TOL:
                    out.append(f"{p.cap:.1f} mm letters are taller than the border row allows "
                               f"({BLACK_CAP * m:.1f} mm, half a module)")
                if sl.where == "top":
                    lo, hi = y1 - (1.0 - BLACK_EDGE) * m, y1 - BLACK_EDGE * m
                else:
                    lo, hi = y0 + BLACK_EDGE * m, y0 + (1.0 - BLACK_EDGE) * m
                over = max(lo - r[1], r[3] - hi, 0.0)
                if over > TOL:
                    out.append(f"{p.text!r} reaches {over:.1f} mm past the black kept around it "
                               f"in the {sl.where} border row")
                into = max((x0 + m) - r[0], r[2] - (x1 - m), 0.0)
                near = max((x0 + (1.0 + CORNER_CLEAR) * m) - r[0],
                           r[2] - (x1 - (1.0 + CORNER_CLEAR) * m), 0.0)
                if into > TOL:
                    out.append(f"{p.text!r} runs {into:.1f} mm into the corner cells")
                elif near > TOL:
                    out.append(f"{p.text!r} is {near:.1f} mm too close to a corner cell")
            if keep and not _clear_of(r, keep, clear):
                out.append(f"{p.text!r} touches the corner mark or a pin")
        return list(dict.fromkeys(out))
    rl = rule_of(s)                                  # the rule it was made under
    tol = POS_TOL_MM if rl.exact else TOL
    ring = grow_rect(ext, quiet_ring(spec) * m)
    hard = keepout_rect(spec, rl.gap_min)
    e = max(WHITE_EDGE * m, EDGE_MIN_MM)
    lps = [lp for lp in (_clean(l) for l in (loops or ())) if len(lp) >= 3]
    outer = max(lps, key=lambda lp: abs(_area2(lp))) if lps else None
    holes = [lp for lp in lps if lp is not outer]
    for p in lab.parts:
        r = p.rect
        # the HARD line only: nearer than auto's preferred margin is no violation
        d = _intrusion(r, ring)
        if d > tol:
            out.append(f"inside the detector's clear zone by {_mm1(d)} mm")
        else:
            d = _intrusion(r, hard)
            if d > tol:
                out.append(f"{_mm1(d)} mm inside the {rl.gap_min:g} module kept around the "
                           "detector's clear zone")
        pts = _rect_samples(r)
        if outer is not None:
            offs = [_loop_dist(q, outer) for q in pts if not _inside([outer], q[0], q[1])]
            hangs = max(offs, default=0.0) > POS_TOL_MM if rl.exact else bool(offs)
            if hangs or any(_in_rect(r, v) for v in outer):
                out.append(f"hangs {_mm1(max(offs, default=0.0))} mm off the face")
            else:
                edge = min(_loop_dist(q, outer) for q in pts)
                if edge < e - tol:
                    out.append(f"{_mm1(edge)} mm from the face's edge (it needs {e:.1f} mm)")
            for h in holes:
                if any(_inside([h], q[0], q[1]) for q in pts) or any(_in_rect(r, v) for v in h):
                    out.append("over a hole in the face")
                    break
                dh = min(min(_loop_dist(q, h) for q in pts),
                         min(rect_point_dist(r, v) for v in h))
                if dh < e - tol:
                    out.append(f"{_mm1(dh)} mm from a hole (it needs {e:.1f} mm)")
                    break
        elif not strip:
            out.append("no white to sit on (nothing around the tag)")
        if keep and not _clear_of(r, keep, clear - (POS_TOL_MM if rl.exact else 0.0)):
            out.append("on the corner mark or a locating pin")
    bl = [lp for lp in (_clean(l) for l in (bounds or ())) if len(lp) >= 3]
    if strip and lab.white is not None and bl:
        ob = max(bl, key=lambda lp: abs(_area2(lp)))
        offs = [_loop_dist(q, ob) for q in _rect_samples(lab.white) if not _inside([ob], q[0], q[1])]
        if offs:
            out.append(f"the tile would grow {max(offs):.1f} mm off the face")
    return list(dict.fromkeys(out))


def _roomiest(spec: TagSpec, loops, rule: int = RULE) -> str:
    """The white side with the most room on the face (measured outward
    from the clear zone along the tag's axes), ties in SIDE_ORDER."""
    lps = [lp for lp in (_clean(l) for l in (loops or ())) if len(lp) >= 3]
    if not lps:
        return SIDE_ORDER[0]
    m, ext, _q = _mm(spec)
    R = keepout_rect(spec, RULES.get(rule, RULES[RULE]).gap_min)
    cu, cv = (ext[0] + ext[2]) / 2.0, (ext[1] + ext[3]) / 2.0
    best, side_best = -1.0, SIDE_ORDER[0]
    for side in SIDE_ORDER:
        t = 0.0
        while t < 500.0:
            q = {"below": (cu, R[1] - t), "above": (cu, R[3] + t),
                 "left": (R[0] - t, cv), "right": (R[2] + t, cv)}[side]
            if not _inside(lps, q[0], q[1]):
                break
            t += 0.25
        if t > best + EPS:
            best, side_best = t, side
    return side_best


def _force(spec: TagSpec, s: LabelSettings, name: str, key: str, place: str, *, mode: str,
           op: Optional[str], loops, grow: bool, bounds, tile: Rect, mark, pins,
           keep, wkeep, at: Optional[Pt] = None, side: str = "") -> Label:
    """The label laid out where it was ASKED for, whatever the rules say:
    the chosen place (on the black: the chosen rows; on the white: `side`,
    else the chosen side, else the roomiest) at the rule's own spot --
    centred in the border row, or just beyond the clear zone and the
    preferred margin -- the whole text at the typed cap or the smallest
    printable one; then moved: its first block centred on `at` (a manual
    position), or by an older record's offset. Its `violations` say what
    that breaks."""
    m, ext, _q = _mm(spec)
    cap = float(s.cap_mm) if s.cap_mm > 0 else min_cap(s.nozzle_mm, s.stroke_mm)
    e = max(WHITE_EDGE * m, EDGE_MIN_MM)
    Mx = metrics(cap, s.nozzle_mm, s.stroke_mm)
    slots: List[Slot] = []
    if place == "black":
        lab = Label(kind="black", role="cut", settings=s)
        row = s.black_row(spec.layout)
        lab.side = row
        if row == "square":
            sq = charuco_square(spec)
            probe = Slot("square", sq, 0, cap, MAX_LINES, None, sq)
            cands = _cands(s, spec, probe, name, key, False)
            if cands:
                du, dv = _dims(wraps(_drawn(cands[0].text), MAX_LINES)[0], Mx, 0)
                c0 = ((sq[0] + sq[2]) / 2.0, (sq[1] + sq[3]) / 2.0)
                probe.rect = (c0[0] - du / 2.0, c0[1] - dv / 2.0, c0[0] + du / 2.0,
                              c0[1] + dv / 2.0)
                slots.append(probe)
        else:
            squares = marker_squares(spec)
            scope = _scope(spec, s)
            for where, part in ROW_PARTS[row]:
                tpl = part_template(s.template(), part)
                if not resolve_text(tpl, spec, name=name, key=key).replace(LINE_BREAK, ""):
                    continue
                per_marker = scope == "each" and len(squares) > 1 and "{id}" in tpl
                for i in (range(len(squares)) if per_marker else [0]):
                    band, bound = _row_rect(squares[i][1], m, where)
                    sl = Slot(where, band, 0, cap, 1, i if per_marker else None, bound, part, i)
                    cands = _cands(s, spec, sl, name, key, False)
                    if not cands:
                        continue
                    du, dv = _dims(wraps(_drawn(cands[0].text), 1)[0], Mx, 0)
                    cx, cy = (band[0] + band[2]) / 2.0, (band[1] + band[3]) / 2.0
                    sl.rect = (cx - du / 2.0, cy - dv / 2.0, cx + du / 2.0, cy + dv / 2.0)
                    slots.append(sl)
        polys = keep
    else:
        lab = Label(kind="white", role="add", settings=s)
        side = side or (s.side if s.side in SIDE_ORDER else _roomiest(spec, loops, s.rule))
        rot = SIDE_ROT[side]
        probe = Slot(side, tile, rot, cap, MAX_LINES)
        cands = _cands(s, spec, probe, name, key, False)
        if cands:
            du, dv = _dims(wraps(_drawn(cands[0].text), MAX_LINES)[0], Mx, rot)
            centre = ((ext[0] + ext[2]) / 2.0 if side in ("below", "above")
                      else (ext[1] + ext[3]) / 2.0)
            probe.rect = _side_box(side, clear_zones(spec, s.rule)["preferred"], du, dv, 0.0,
                                   0.0, centre)
            slots.append(probe)
        lab.side = side
        polys = keep if loops else wkeep
    dx, dy = float(s.offset_x_mm), float(s.offset_y_mm)
    if at is not None:
        dx, dy = 0.0, 0.0
        if slots:
            r = slots[0].rect
            dx, dy = at[0] - (r[0] + r[2]) / 2.0, at[1] - (r[1] + r[3]) / 2.0
    for sl in slots:
        r = sl.rect
        sl.rect = (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
    lab.slots = slots
    for i, sl in enumerate(slots):
        cands = _cands(s, spec, sl, name, key, False)
        if cands:
            lines = wraps(_drawn(cands[0].text), sl.lines)[0]
            lab.parts.append(_part(i, sl, cands[0], lines, sl.cap, s))
    strip = lab.kind == "white" and not loops and bool(grow)
    if strip and lab.parts:
        white = tile
        for p in lab.parts:
            white = _grown(white, p.rect, e)
        if white != tile:
            lab.white, lab.strip = white, _strip(tile, white)
            polys = list(polys)
            leg = 0.0
            if mark is not None and (mark.get("kind") if isinstance(mark, dict)
                                     else mark.kind) == "tile_cut":
                mk = mark_on_tile(spec, mode, op, white)
                polys += mark_keepouts(mk)
                leg = mk.leg if mk.kind == "tile_cut" else 0.0
            polys += _pins_on(white, pins, leg, [])
    lab.violations = label_violations(spec, lab, loops=loops, bounds=bounds, keep=polys,
                                      strip=strip)
    return lab


def _nudged(lab: Label, spec: TagSpec, dx: float, dy: float, *, loops, strip: bool, bounds,
            tile: Rect, keep, mark, pins, mode: str, op: Optional[str]) -> Label:
    """A placed label moved by (dx, dy) as typed, no rule enforced (the
    preview of a refused nudge), its violations listed."""
    m, _ext, _q = _mm(spec)
    e = max(WHITE_EDGE * m, EDGE_MIN_MM)
    def mv(r):
        return (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
    new = Label(kind=lab.kind, role=lab.role, side=lab.side, settings=lab.settings,
                slots=[replace(sl, rect=mv(sl.rect)) for sl in lab.slots], white=lab.white,
                strip=lab.strip, mode=lab.mode, slab=lab.slab)
    for p in lab.parts:                    # the text as it was laid out, moved as typed
        new.parts.append(replace(p, rect=mv(p.rect), boxes=[
            Box(b.cx + dx, b.cy + dy, b.length, b.width, b.angle) for b in p.boxes]))
    polys = keep
    if strip and new.parts:
        white = tile
        for p in new.parts:
            white = _grown(white, p.rect, e)
        new.white = white if white != tile else None
        new.strip = _strip(tile, white) if new.white else None
        polys = list(keep)
        leg = 0.0
        if mark is not None and (mark.get("kind") if isinstance(mark, dict)
                                 else mark.kind) == "tile_cut":
            mk = mark_on_tile(spec, mode, op, white)
            polys += mark_keepouts(mk)
            leg = mk.leg if mk.kind == "tile_cut" else 0.0
        polys += _pins_on(white, pins, leg, [])
    new.violations = label_violations(spec, new, loops=loops, bounds=bounds, keep=polys,
                                      strip=strip)
    return new


# -------------------------------------------------------------------- plan

def pattern_slab(mode: str, numbers: Dict[str, float], has_body: bool = True
                 ) -> Tuple[float, float]:
    """The slab the label is built in: the pattern layer's (lo, hi), mm
    from the face -- aruco_slabs.layers(...).pattern, the black cells (the
    white pattern in White only) where their Offset / Height put them."""
    from . import slabs as SL
    return SL.layers(mode, numbers, has_body).pattern


def _overlaps(a: Rect, b: Rect) -> bool:
    """Rects share area (touching does not count)."""
    return (a[0] < b[2] - TOL and a[2] > b[0] + TOL and a[1] < b[3] - TOL
            and a[3] > b[1] + TOL)


def _offset_label(lab: Label, spec: TagSpec, dx: float, dy: float, notes: List[str], *,
                  loops, strip: bool, bounds, tile: Rect, keep, mark, pins, mode: str,
                  op: Optional[str], what: str = "") -> Tuple[Optional[Label], str]:
    """The label's slots moved by (dx, dy) mm (its parts to be laid out
    again), or (None, why not). Every rule the placement kept is checked
    again for the new spot. `what` names the move in the reason ("X 6,
    Y -17.5 mm"; default "offset (+dx, +dy) mm")."""
    m, _ext, _q = _mm(spec)
    off = what or f"offset ({dx:+g}, {dy:+g}) mm"
    clear = max(KEEPOUT_MM, KEEPOUT * m)
    new = Label(kind=lab.kind, role=lab.role, side=lab.side, settings=lab.settings,
                slots=[replace(sl) for sl in lab.slots], white=lab.white, strip=lab.strip,
                mode=lab.mode, slab=lab.slab)
    if lab.kind == "black" and lab.side != "square":
        # along the row only: as far as the text has black to its corner cells
        lo_x, hi_x, room_y = -math.inf, math.inf, math.inf
        for prt in lab.parts:
            r = lab.slots[prt.slot].rect
            lo_x = max(lo_x, r[0] - prt.rect[0])
            hi_x = min(hi_x, r[2] - prt.rect[2])
            room_y = min(room_y, max(0.0, (r[3] - r[1]) - (prt.rect[3] - prt.rect[1])) / 2.0)
        if not lo_x - TOL <= dx <= hi_x + TOL:
            return None, (f"{off} would run the text into a corner cell: along its row it "
                          f"moves {lo_x:+.1f} to {hi_x:+.1f} mm here")
        dyc = max(-room_y, min(room_y, dy)) + 0.0
        dyc = 0.0 if abs(dyc) < TOL else dyc
        if abs(dyc - dy) > TOL:
            notes.append(f"label: on the black the text moves along its row only -- y offset "
                         f"{dy:+g} mm clamped to {dyc:+.2f} mm")
        for sl in new.slots:
            sl.shift = (dx, dyc)
        return new, ""
    for sl in new.slots:
        r = sl.rect
        sl.rect = (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)
    if lab.kind == "black":                                  # a ChArUco board's square
        S = spec.square_length_m * 1000.0
        sq = charuco_square(spec)
        e = max(SQUARE_EDGE * S, m)
        corners = charuco_corners_mm(spec)
        for sl in new.slots:
            r = sl.rect
            if lab.settings.rule >= ANY_SQUARE_RULE:         # rule 3: the square it moved into
                sq = label_square(spec, r, lab.settings.rule)
                sl.bound = sq
            if r[0] < sq[0] + e - TOL or r[1] < sq[1] + e - TOL or r[2] > sq[2] - e + TOL \
                    or r[3] > sq[3] - e + TOL:
                return None, f"{off} takes it out of the black square ({e:.1f} mm in from its edges)"
            if any(rect_point_dist(r, c) < SQUARE_CORNER * S - TOL for c in corners):
                return None, (f"{off} brings it within {SQUARE_CORNER:g} square of a ChArUco "
                              f"corner")
            if not _clear_of(r, keep, clear):
                return None, f"{off} puts it on the corner mark"
        return new, ""
    rl = rule_of(lab.settings)                            # the rule it was made under
    R = keepout_rect(spec, rl.gap_min)                    # the HARD line only
    e = max(WHITE_EDGE * m, EDGE_MIN_MM)
    r = new.slots[0].rect
    if (_intrusion(r, R) > POS_TOL_MM) if rl.exact else _overlaps(r, R):
        return None, f"{off} puts it inside the detector's clear zone"
    if loops:
        if rl.exact:
            # measured as label_violations measures (straight-line distance), a
            # dialog's rounded spot being the same spot
            eg = e - POS_TOL_MM

            def on(lps):
                return _clear_on(lps, r, eg)
        else:
            g = (r[0] - e, r[1] - e, r[2] + e, r[3] + e)  # rule 1: a square margin

            def on(lps):
                return _rect_inside(lps, (g[0] + g[2]) / 2.0, (g[1] + g[3]) / 2.0,
                                    g[2] - g[0], g[3] - g[1])
        if not on(loops):
            outer = max(loops, key=lambda lp: abs(_area2(lp)))
            gone = not on([outer])
            return None, (f"{off} takes it " + ("off the face" if gone else "over a hole")
                          + f" ({e:.2f} mm kept from every edge)")
        if not _clear_of(r, keep, clear - (POS_TOL_MM if rl.exact else 0.0)):
            return None, f"{off} puts it on a corner mark or a pin"
        return new, ""
    if not strip:
        return None, f"{off} leaves the white it was placed on"
    along_u = lab.side in ("below", "above")
    a0, a1 = (tile[0], tile[2]) if along_u else (tile[1], tile[3])
    b0, b1 = (r[0], r[2]) if along_u else (r[1], r[3])
    if b0 < a0 + e - TOL or b1 > a1 - e + TOL:
        return None, f"{off} runs it past the side of the tile ({e:.2f} mm kept from its edges)"
    white = _grown(tile, r, e)
    if bounds and not _rect_inside(bounds, (white[0] + white[2]) / 2.0, (white[1] + white[3]) / 2.0,
                                   white[2] - white[0], white[3] - white[1]):
        return None, f"{off} would grow the tile off the face"
    polys = list(keep)
    leg = 0.0
    tile_cut = mark is not None and (mark.get("kind") if isinstance(mark, dict)
                                     else mark.kind) == "tile_cut"
    if tile_cut:
        mk = mark_on_tile(spec, mode, op, white)
        polys += mark_keepouts(mk)
        leg = mk.leg if mk.kind == "tile_cut" else 0.0
    polys += _pins_on(white, pins, leg, [])
    if not _clear_of(r, polys, clear):
        return None, f"{off} puts it on the tile's corner mark or a pin"
    new.white = white if white != tile else None
    new.strip = _strip(tile, white) if new.white else None
    return new, ""


def white_room(mode: str, op: Optional[str], has_body: bool, tile_bigger: bool = False) -> dict:
    """Where a label on the white finds its white, per ArUco Extrude mode:

        White + black, a tile bigger than the sticker (a sketch area)
                                   region = that tile (rect_loop)
        White + black, the sticker grow the tile by a strip (inside the
                                   face when there is a body under)
        Black only                 region = the face: the user's white body
        White only                 grow the white pattern by a strip (inside
                                   the face it sits on)
    -> {"grow": bool, "region": "tile" | "face" | None,
        "bounds": "face" | None, "why": str}"""
    if mode == "both":
        if tile_bigger:
            return {"grow": False, "region": "tile", "bounds": None,
                    "why": "the white tile is bigger than the sticker"}
        return {"grow": True, "region": None, "bounds": "face" if has_body else None,
                "why": "the white tile grows by a label strip"}
    if mode == "black":
        if has_body:
            return {"grow": False, "region": "face", "bounds": None,
                    "why": "the label sits on the body around the tag (it must be white)"}
        return {"grow": False, "region": None, "bounds": None,
                "why": "no body under the tag: no white around it"}
    return {"grow": True, "region": None, "bounds": "face" if has_body else None,
            "why": "the white pattern grows by a label strip"}


def plan_label(spec: TagSpec, settings: Optional[LabelSettings] = None, *, mode: str = "both",
               op: Optional[str] = "new", name: str = "", key: str = "",
               region: Optional[Sequence[Sequence[Pt]]] = None, grow: bool = False,
               bounds: Optional[Sequence[Sequence[Pt]]] = None, tile: Optional[Rect] = None,
               mark=None, pins: Optional[dict] = None,
               keepouts: Sequence[Sequence[Pt]] = (),
               slab: Optional[Tuple[float, float]] = None) -> Label:
    """One tag's label (see the module docstring). Never raises.

    spec      markers.TagSpec, the RESOLVED one (a copy's own ids)
    settings  LabelSettings (or its dict); None / off -> kind "none"
    mode, op  ArUco Extrude's mode ("both" / "black" / "white") and the
              effective op ("join" / "new" / None): the corner mark on a
              grown tile follows them
    name, key {name} and {key}
    region    the white the label may sit on, loops in mm in the pattern
              frame (white_room: the face, or a big tile's rect_loop)
    grow      no region: the tile (White only: the white pattern) may grow
              by a label strip; `bounds` (loops) keep the grown white inside
              the face it sits on
    tile      the white tile's rect before growing (default the sticker)
    mark      the corner mark (aruco_chamfer Mark / dict) of the un-grown
              tile; a tile cut is re-made on a grown tile (mark_on_tile)
    pins      {"shape", "size", "margin"}: the locating pins, on the tile
              the label ends up with (aruco_slabs.pin_outlines)
    keepouts  more polygons (mm) to keep KEEPOUT_MM clear of
    slab      the pattern layer's (lo, hi) mm (pattern_slab): the label is
              built there (Label.solids)

    settings.position "manual" puts the label's first block centred on
    (x_mm, y_mm): on the white and in a ChArUco square anywhere, re-checked
    (the detector's clear zone, the face and its holes, the tile, corner
    marks, pins) -- on the white Auto size shrinks it to fit there, never
    above auto's own cap, so a spot taken over from auto keeps auto's label
    exactly; on the black along its row only (y clamped, with a note). An
    older record's offset_x_mm / offset_y_mm (position "auto") moves auto's
    label by that much, as it always did.

    A label that breaks a rule -- no room, letters under the printable cap,
    a spot in the clear zone, off the face, over a hole -- comes back as
    kind "none" with a `preview`: the label laid out where it was asked for
    (`_force` / `_nudged`), its `violations` in plain words, and (no room
    anywhere) the `reason`. The preview is always drawn; it is built
    (returned as the label, forced=True) only with settings.build_anyway.
    """
    notes: List[str] = []
    if isinstance(settings, dict):
        settings = LabelSettings.from_dict(settings, notes)
    s = settings or LabelSettings()
    if not s.on:
        return Label(settings=s)
    if s.stroke_mm and s.stroke_mm < s.nozzle_mm - EPS:
        notes.append(f"label: stroke {s.stroke_mm:g} mm is under the {s.nozzle_mm:g} mm nozzle "
                     "-- the nozzle used")
    bad = unknown_tokens(s.template())
    if bad:
        notes.append("label: unknown " + ", ".join("{%s}" % t for t in bad)
                     + " (known: " + ", ".join("{%s}" % t for t in TOKENS) + ")")
    try:
        aruco_board.check_spec(board_spec(spec))
    except (ValueError, KeyError) as exc:
        return Label(settings=s, notes=notes + [f"label: {exc}"])
    if not resolve_text(s.template(), spec, name=name, key=key).replace(LINE_BREAK, ""):
        return Label(settings=s, notes=notes + ["label: the text is empty"])
    note = _missing_note(resolve_text(s.template(), spec, name=name, key=key))
    if note:
        notes.append(note)
    tile = tuple(tile) if tile else sticker_rect(spec)
    extra = [list(p) for p in keepouts or ()]
    tile_cut = bool(mark) and (mark.get("kind") if isinstance(mark, dict)
                               else mark.kind) == "tile_cut"
    leg = (mark.get("leg_mm", 0.0) if isinstance(mark, dict) else mark.leg) if tile_cut else 0.0
    # the tile as it is: its corner mark and its pins
    keep = extra + mark_keepouts(mark) + _pins_on(tile, pins, leg, [])
    strip = bool(grow) and not region
    # a strip moves the tile's corner (a cut is re-made there) and its
    # pins; a triangle stays in the sticker's corner
    wkeep = (extra + ([] if tile_cut else mark_keepouts(mark))) if strip else keep

    def black(cut, out):
        return _plan_black(spec, s, name, key, keep, out, cut)

    def white(cut, out):
        return _plan_white(spec, s, name, key, mode=mode, op=op, region=region,
                           grow=bool(grow), bounds=bounds, tile=tile,
                           mark=mark if strip else None, pins=pins if strip else None,
                           keep=wkeep, notes=out, cut=cut)
    n0 = len(notes)
    if s.place == "black":
        lab = black(True, notes)
    elif s.place == "white":
        lab = white(True, notes)
    else:
        # auto: the whole text on the black, else the whole text on the
        # white, else cut short -- on the white (more room), else the black
        lab, why = None, []
        for fn, cut in ((black, False), (white, False), (white, True), (black, True)):
            said: List[str] = []
            got = fn(cut, said)
            if got.kind != "none":
                lab = got
                if fn is white and why:
                    notes.append("label: not on the black -- " + "; ".join(
                        w.replace("label: ", "") for w in why[:1]) + ": on the white instead")
                notes += said
                break
            if not why:
                why = said
        if lab is None:
            lab = Label(settings=s)
            notes += why
    reason = ""
    if lab.kind == "none":
        reason = next((n[len("label: "):] if n.startswith("label: ") else n
                       for n in notes[n0:]), "")
        if s.place == "auto":
            first = resolve_text(s.template(), spec, name=name, key=key).split(LINE_BREAK)[0]
            reason = (f"no room for {first!r} on the black or on the white, even at "
                      f"{min_cap(s.nozzle_mm, s.stroke_mm):.1f} mm letters (the smallest a "
                      f"{s.nozzle_mm:g} mm nozzle prints)")
    lab.settings = s
    lab.mode, lab.slab = mode, (tuple(map(float, slab)) if slab else None)
    if lab.kind == "none":
        lab.slots, lab.parts = [], []
    for i, sl in enumerate(lab.slots):
        part = _lay(i, sl, _cands(s, spec, sl, name, key), s, notes)
        if part is not None:
            lab.parts.append(part)
    loops_c = [lp for lp in (_clean(l) for l in (region or ())) if len(lp) >= 3]
    bounds_c = [lp for lp in (_clean(l) for l in (bounds or ())) if len(lp) >= 3]
    where = dict(loops=loops_c, strip=strip, bounds=bounds_c, tile=tile,
                 keep=wkeep if strip else keep, mark=mark if strip else None,
                 pins=pins if strip else None, mode=mode, op=op)
    target = (float(s.x_mm), float(s.y_mm)) if s.manual else None
    spot = f"X {s.x_mm:.2f}, Y {s.y_mm:.2f} mm" if s.manual else ""

    def laid(new, said):
        """`new`'s parts laid out again; (it, why not) -- (None, why) when a
        text no longer fits there or the safety check objects."""
        for i, sl in enumerate(new.slots):
            part = _lay(i, sl, _cands(s, spec, sl, name, key), s, said)
            if part is not None:
                new.parts.append(part)
        probs = check_label(spec, new) if new.ok else ["a text no longer fits"]
        return (None, probs[0]) if probs else (new, "")
    if lab.ok and (target is not None or s.nudged):
        anchor = _centre_of(lab)
        if target is not None:
            dx, dy = target[0] - anchor[0], target[1] - anchor[1]
            moving = abs(dx) > POS_TOL_MM or abs(dy) > POS_TOL_MM   # else: auto's own spot
        else:
            dx, dy = float(s.offset_x_mm), float(s.offset_y_mm)
            moving = True
        if moving:
            said: List[str] = []
            moved, why = _offset_label(lab, spec, dx, dy, said, what=spot, **where)
            if moved is not None:
                moved, bad = laid(moved, said)
                if moved is None:
                    why = f"{spot or f'offset ({dx:+g}, {dy:+g}) mm'} breaks a rule: {bad}"
            if moved is None and target is not None and lab.kind == "white":
                # Auto size: smaller there -- never bigger than auto's, so taking
                # a spot over from auto never grows the label
                said = []
                hit = _white_at(spec, s, name, key, target, lab.side, lab.cap, True, **where)
                if hit is not None:
                    moved, _bad = laid(hit, said)
                    if moved is not None and s.cap_mm > 0 and moved.cap < lab.cap - EPS:
                        said.append(f"label: cap {lab.cap:.2f} mm does not fit there -- "
                                    f"shrunk to {moved.cap:.2f} mm")
            if moved is None:
                # shown where it was put, in a warning colour: not built
                # unless Build anyway (it was "kept where it was placed" before
                # 2026-10-11, which hid the nudge Zach asked for). On the white
                # by hand: as small as Auto size could make it (or the typed
                # cap), the text as written -- the nearest it came to fitting
                if target is not None and lab.kind == "white":
                    pv = _force(spec, s, name, key, "white", mode=mode, op=op, loops=loops_c,
                                grow=bool(grow), bounds=bounds_c, tile=tile,
                                mark=mark if strip else None, pins=pins if strip else None,
                                keep=keep, wkeep=wkeep, at=target, side=lab.side)
                else:
                    pv = _nudged(lab, spec, dx, dy, **where)
                if not pv.violations:
                    pv.violations = [why]
                notes.append(f"label: {why} -- shown where it would go, not built")
                lab = Label(settings=s, preview=pv)
            else:
                lab = moved
                notes += said
    elif lab.kind == "none" and target is not None and s.place != "black" \
            and (loops_c or strip):
        # the rules found no room, but a spot placed by hand may have it
        side = s.side if s.side in SIDE_ORDER else _roomiest(spec, loops_c, s.rule)
        m = _mm(spec)[0]
        said = []
        cap_hi, typed = _cap_rule(WHITE_LIMIT * m if s.cap_mm > 0 else WHITE_CAP * m, s,
                                  "the white", said)
        hit = _white_at(spec, s, name, key, target, side, cap_hi, typed, **where)
        if hit is not None:
            moved, _bad = laid(hit, said)
            if moved is not None:
                lab, reason = moved, ""
                notes = [n for n in notes[:n0]] + said
    if target is not None:
        reason = ""                              # it is where it was put: what it breaks there
    if lab.kind == "none" and lab.preview is None:
        # nothing fits inside the rules: lay it out where it was asked for
        def force(place):
            return _force(spec, s, name, key, place, mode=mode, op=op, loops=loops_c,
                          grow=bool(grow), bounds=bounds_c, tile=tile,
                          mark=mark if strip else None, pins=pins if strip else None,
                          keep=keep, wkeep=wkeep, at=target)
        if s.place in ("black", "white"):
            pv = force(s.place)
        else:
            tried = [force("black"), force("white")]
            pv = min(tried, key=lambda t: (not t.parts, len(t.violations)))
        if pv.parts:
            lab.preview = pv
    if lab.kind == "none":
        lab.reason = reason
    if lab.preview is not None:
        lab.preview.mode = mode
        lab.preview.slab = tuple(map(float, slab)) if slab else None
        if s.build_anyway:
            lab.preview.forced = True
            notes.append("label: built anyway although: "
                         + "; ".join(lab.preview.violations))
            lab = lab.preview
    if lab.parts and lab.min_feature < s.nozzle_mm - TOL:
        notes.append(f"label: smallest feature {lab.min_feature:.2f} mm is under the "
                     f"{s.nozzle_mm:g} mm nozzle")
    lab.notes = list(dict.fromkeys(notes))          # a board's markers say it once
    return lab


def _centre_of(lab: Label) -> Optional[Pt]:
    """A laid-out label's first block centre (mm, pattern frame): its first
    slot's centre, plus the shift along a black row as _part clamps it."""
    if not lab.slots:
        return None
    sl = lab.slots[0]
    r = sl.rect
    c = ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0)
    if sl.shift != (0.0, 0.0):
        part = next((q for q in lab.parts if q.slot == 0), None)
        if part is not None:
            du, dv = _dims(part.lines, metrics(part.cap), sl.rot)
            hx, hy = max(0.0, r[2] - r[0] - du) / 2.0, max(0.0, r[3] - r[1] - dv) / 2.0
            c = (c[0] + max(-hx, min(hx, sl.shift[0])), c[1] + max(-hy, min(hy, sl.shift[1])))
    return c


def position_of(label) -> Optional[Pt]:
    """Where a label IS (mm, pattern frame after the Origin turn: +x right,
    +y up from the pattern's centre): its first block's centre -- on the
    white the whole text block, on the black its first row's text. The
    shown label: this one, or a refused one's preview. What the dialog's
    Offset X / Y show under Auto position, and what a manual position at
    that spot gives back exactly. None when nothing is shown."""
    lab = from_dict(label) if isinstance(label, dict) else label
    sh = lab.shown if lab is not None else None
    return _centre_of(sh) if sh is not None else None


def _white_at(spec: TagSpec, s: LabelSettings, name: str, key: str, at: Pt, side: str,
              cap_hi: float, typed: bool, *, loops, strip: bool, bounds, tile: Rect, keep,
              mark, pins, mode: str, op: Optional[str], cut: bool = True) -> Optional[Label]:
    """The label on the white with its block centred on `at` (a spot put by
    hand), text upright for `side`: the biggest text, cap <= cap_hi, that
    keeps every rule there (the detector's clear zone, the face and its
    holes with their margin, the tile's side, corner marks, pins) -- the
    text shortened only as auto would. None when not even the smallest
    printable text does."""
    m = _mm(spec)[0]
    rot = SIDE_ROT[side]
    caps = _caps(cap_hi, min_cap(s.nozzle_mm, s.stroke_mm), typed)
    cands = _cands(s, spec, Slot("white", tile, 0, 0.0, MAX_LINES), name, key, cut)

    def place(c, lines):
        du, dv = _dims(lines, metrics(c, s.nozzle_mm, s.stroke_mm), rot)
        r = (at[0] - du / 2.0, at[1] - dv / 2.0, at[0] + du / 2.0, at[1] + dv / 2.0)
        probe = Label(kind="white", role="add", side=side, settings=s,
                      slots=[Slot(side, r, rot, c, MAX_LINES)])
        new, _why = _offset_label(probe, spec, 0.0, 0.0, [], loops=loops, strip=strip,
                                  bounds=bounds, tile=tile, keep=keep, mark=mark, pins=pins,
                                  mode=mode, op=op)
        return new

    def search(text):
        best = None
        for k, lines in enumerate(wraps(_drawn(text), MAX_LINES)):
            hit = {}

            def ok(c, lines=lines):
                r = place(c, lines)
                if r is not None:
                    hit[c] = r
                return r is not None
            # a strip's pins move with the strip: scan, do not bisect
            c = next((c for c in caps if ok(c)), None) if strip else _largest(caps, ok)
            if c is None:
                continue
            if c not in hit:
                ok(c)
            res = (c, lines, hit[c])
            if k == 0 and c >= max(ONE_LINE * m, caps[-1]) - EPS:
                return res
            if best is None or c > best[0] + EPS:
                best = res
        return best

    def fits(cand):
        r = search(cand.sizing)
        return r if r is not None or cand.sizing == cand.text else search(cand.text)
    got = _first_fit(cands, fits)
    if got is None:
        return None
    _i, (c, _lines, new) = got
    new.slots[0].cap = c
    return new


def relabel(label, spec: TagSpec, *, name: str = "", key: str = "") -> Label:
    """A copy's label: the template's slots (sized, checked, the strip and
    the tile as built) with the copy's own text -- its resolved ids, its
    name. What a variant builds (aruco_tags._build_variant)."""
    lab = from_dict(label) if isinstance(label, dict) else label
    out = Label(kind=lab.kind, role=lab.role, side=lab.side, settings=lab.settings,
                slots=list(lab.slots), white=lab.white, strip=lab.strip, notes=[],
                mode=lab.mode, slab=lab.slab)
    if out.kind == "none":
        return out
    if lab.forced:
        # built anyway: each copy's own text in the same spots, at the same
        # cap, with the template's warnings
        out.forced, out.violations = True, list(lab.violations)
        for i, sl in enumerate(out.slots):
            cands = _cands(lab.settings, spec, sl, name, key, False)
            if cands:
                out.parts.append(_part(i, sl, cands[0], wraps(_drawn(cands[0].text),
                                                              sl.lines)[0], sl.cap,
                                       lab.settings))
        return out
    for i, sl in enumerate(out.slots):
        part = _lay(i, sl, _cands(lab.settings, spec, sl, name, key), lab.settings,
                    out.notes)
        if part is not None:
            out.parts.append(part)
    out.notes = list(dict.fromkeys(out.notes))
    return out


def label_for_instance(label, inst) -> Label:
    """relabel() for a markers.TagInstance: its resolved spec, the name its
    geometry shows (instance_name), its tag key."""
    return relabel(label, inst.spec, name=instance_name(inst), key=inst.tag.key)


RECORD_FIELD = "label"     # a tag record's rec["fusion"]["label"]: Label.to_dict()


def copy_regions(label, spec: TagSpec, *, name: str = "", key: str = "") -> dict:
    """What a COPY's label changes when the copy prints other ids (a batch
    ArUco IDs set): the id-dependent label geometry, for a part that keeps
    the template's material and only recolours what depends on the id.

    label  the template tag record's rec["fusion"]["label"] (RECORD_FIELD:
           Label.to_dict -- its settings, the slots the template sized and
           checked, the template's own text), or a Label
    spec   the copy's resolved TagSpec (its final ids)
    name   {name} for the copy: part_name(copy's occurrence path) -- the last
           two elements below the level that numbered it ("Arm:2/Actuator:3")
    key    the tag's key (the record's "key")

    -> {"on": bool (False: no label, or the template's was refused),
        "slots": [(u0, v0, u1, v1)]   the template's text lies inside these:
                                      repaint them `background` first
        "background": "black" | "white"
        "text": "white" | "black"     the copy's text colour (role "cut":
                                      white text knocked out of the black;
                                      "add": black text on the white -- in
                                      every mode, White only too)
        "boxes": [[cx, cy, length, width, angle_deg]]   the copy's strokes
                 (Box.to_list; the rectangle Box.corners() gives)
        "polygons": [[(u, v) x4]]     the same strokes as CCW polygons
        "white": (u0, v0, u1, v1) or None   the white a label strip grew
                 (the same for every copy: not id-dependent)
        "slab": (lo, hi) mm from the face, the pattern layer the label is
                built in (aruco_slabs; the record frame sits at the surface)
        "texts": [str] per slot, "notes": [str] (a copy text cut short...),
        "warning": str  "" when the label is fine; else what the copies must
                 say instead of dropping it silently: the template's label is
                 not built (its rule breaks), or built anyway (its warnings)}

    Everything in mm, in the tag record's frame (origin, x_axis, y_axis:
    the pattern frame after the Origin turn -- u right, v up). Pure."""
    lab = from_dict(label) if isinstance(label, dict) else label
    off = {"on": False, "slots": [], "background": "", "text": "", "boxes": [],
           "polygons": [], "white": None, "slab": None, "texts": [], "notes": [],
           "warning": ""}
    if lab is None or lab.kind == "none" or not lab.slots:
        if lab is not None and lab.settings.on and lab.preview is not None:
            off["warning"] = ("the label is not built: " + "; ".join(lab.preview.violations)
                              + " (Edit ArUco Extrude, Build anyway, to build it)")
        elif lab is not None and lab.settings.on:
            off["warning"] = "the label is not built: " + "; ".join(
                n.replace("label: ", "") for n in lab.notes[:1])
        return off
    cp = relabel(lab, spec, name=name, key=key)
    cut = cp.role == "cut"
    return {"on": True, "slots": [tuple(s.rect) for s in cp.slots],
            "background": "black" if cut else "white", "text": "white" if cut else "black",
            "boxes": [b.to_list(6) for b in cp.boxes()], "polygons": cp.polygons(),
            "white": tuple(cp.white) if cp.white else None,
            "slab": tuple(cp.slab) if cp.slab else None,
            "texts": cp.texts(), "notes": list(cp.notes),
            "warning": ("built anyway although: " + "; ".join(cp.violations))
            if cp.violations else ""}


# ------------------------------------------------------------ in words
#
# Zach, 2026-10-13: "It's annoying how I need to scroll to see the linter
# messages." What the dialog says about the label: a few lines, the
# important first, a refused label in at most three.

ERROR, WARN, OK, NOTE = "error", "warn", "ok", "note"
_REFUSAL_WORDS = ("no room on", "no room for", "does not print in", "nothing printable fits",
                  "does not fit", "not on the black", "shown where it would go",
                  "built anyway although", "no white to put it on", "under the smallest")


def _plain(note: str) -> str:
    for pre in ("label warning: ", "label: "):
        if note.startswith(pre):
            return note[len(pre):]
    return note


def where_words(lab: Label) -> str:
    """Where a laid-out label is, in words: "below the marker",
    "on the black, both border rows", "in the top-left black square"."""
    if lab.kind == "black":
        if lab.side == "square":
            return "in the top-left black square"
        rows = {"bottom": "the bottom border row", "top": "the top border row",
                "both": "both border rows"}
        return "on the black, " + rows.get(lab.side, "the border row")
    return {"below": "below the marker", "above": "above the marker",
            "left": "left of the marker", "right": "right of the marker"}.get(
        lab.side, "on the white")


def _texts_words(lab: Label) -> str:
    t = [x.replace(LINE_BREAK, " ") for x in lab.texts() if x]
    return " / ".join(repr(x) for x in t[:3]) + (f" +{len(t) - 3} more" if len(t) > 3 else "")


def describe(label, mode: str = "both") -> List[Tuple[str, str]]:
    """_describe's lines, and -- a label made under rule 1 -- one grey line
    that says so and how to leave it (RULE_NOTE)."""
    lab = from_dict(label) if isinstance(label, dict) else label
    out = _describe(lab, mode)
    if out and lab.settings.rule < RULE:                  # rule 3 is newer, not older
        out.append((NOTE, RULE_NOTE[0].upper() + RULE_NOTE[1:] + "."))
    return out


def _describe(label, mode: str = "both") -> List[Tuple[str, str]]:
    """The label in a few plain lines for the dialog, the important first:
    [(level, text)], level ERROR (not built), WARN (built anyway; a note to
    act on), OK (what is built) or NOTE (grey detail). A refused label
    reads in at most three lines -- what is wrong, with the number; where
    it is shown; what to do -- and the notes that only repeat the refusal
    are left out. [] when the label is off."""
    lab = from_dict(label) if isinstance(label, dict) else label
    if lab is None or not lab.settings.on:
        return []
    s = lab.settings
    pv = lab.preview
    by_hand = s.manual or s.nudged
    if lab.kind == "none":
        notes = [_plain(n) for n in lab.notes
                 if not any(w in n for w in _REFUSAL_WORDS) and _plain(n) != lab.reason]
        if pv is None or not pv.parts:
            why = lab.reason or (_plain(lab.notes[0]) if lab.notes else "nothing to print")
            return [(ERROR, f"Label not made: {why}.")] + [(NOTE, n) for n in notes]
        v = "; ".join(pv.violations) or "it breaks a rule"
        if by_hand and not lab.reason:
            out = [(ERROR, f"Label not built here: {v}."),
                   (WARN, "Move it (Offset X / Y) or tick Auto position -- or tick Build "
                          "anyway to build it here.")]
        else:
            if "under the smallest" in lab.reason:
                fix = (f"Tick Auto size, or type {min_cap(s.nozzle_mm, s.stroke_mm):.1f} mm "
                       "letters or more")
            elif pv.kind == "white":
                fix = ("Try another Side, On the black or a finer nozzle -- or untick Auto "
                       "position and place it")
            else:
                fix = "Try On the white, a finer nozzle or a bigger marker"
            out = [(ERROR, f"Label not built: {lab.reason or v}."),
                   (WARN, f"Shown in orange {where_words(pv)} ({_texts_words(pv)}, "
                          f"{pv.cap:.1f} mm)" + (f": {v}." if lab.reason else ".")),
                   (WARN, fix + "; Build anyway builds it there.")]
        return out + [(NOTE, n) for n in notes]
    if not lab.parts:
        return [(ERROR, "Label not made: " + (_plain(lab.notes[0]) if lab.notes
                                               else "nothing to print") + ".")]
    if lab.violations:
        notes = [_plain(n) for n in lab.notes if not any(w in n for w in _REFUSAL_WORDS)]
        return [(WARN, f"Label built anyway {where_words(lab)} ({_texts_words(lab)}, "
                       f"{lab.cap:.1f} mm): " + "; ".join(lab.violations) + "."),
                (NOTE, "Untick Build anyway to leave it out.")] + [(WARN, n) for n in notes]
    notes = [_plain(n) for n in lab.notes if "built anyway although" not in n]
    parts = []
    for prt in lab.parts:
        sl = lab.slots[prt.slot]
        row = sl.where if sl.where in ("bottom", "top") and len(lab.parts) > 1 else ""
        parts.append(f"{row + ' ' if row else ''}{' / '.join(prt.lines)!r} {prt.cap:.1f} mm")
    shown = parts[:4] + ([f"+{len(parts) - 4} more"] if len(parts) > 4 else [])
    if lab.kind == "black":
        how = ("white text: the white pattern shows through the black" if mode == "white"
               else "white text knocked out of the black")
    else:
        how = ("black text: a notch in the white, the body under shows" if mode == "white"
               else "black text, inlaid like the cells")
    if lab.strip is not None:
        st = lab.strip
        d = (st[2] - st[0]) if lab.side in ("left", "right") else (st[3] - st[1])
        how += (f"; the {'white pattern' if mode == 'white' else 'white tile'} grows "
                f"{d:.1f} mm {lab.side} for it")
    pos = position_of(lab)
    at = f" at X {pos[0]:.1f}, Y {pos[1]:.1f} mm" if pos is not None and by_hand else ""
    return ([(OK, f"Label {where_words(lab)}{at}: " + " · ".join(shown)),
             (NOTE, f"{how}; strokes {lab.stroke:.2f} mm, as tall as the black")]
            + [(WARN, n) for n in notes])


# ------------------------------------------------------------ safety check

def check_label(spec: TagSpec, label, tol: float = 1e-6) -> List[str]:
    """Problems with a label against the detection rules, from the spec
    alone (the slots are not trusted). [] = safe.

    white  no ink inside the quiet ring (the black grown by quiet_ring),
           and none within WHITE_GAP_MIN more of it (the hard line; auto's
           preferred margin is not checked here)
    black  a row's ink inside its border row's band (BLACK_EDGE of black
           above and below), clear of the corner cells, cap <= 0.5 module;
           a ChArUco square's ink inside that black square, >= 0.3 square
           from every ChArUco corner
    both   strokes >= the nozzle"""
    lab = from_dict(label) if isinstance(label, dict) else label
    if lab.kind == "none":
        return []
    out: List[str] = []
    m, ext, _q = _mm(spec)
    noz = lab.settings.nozzle_mm
    for p in lab.parts:
        polys = [b.corners() for b in p.boxes]
        if p.stroke < noz - tol:
            out.append(f"{p.text!r}: stroke {p.stroke:.3f} mm under the {noz:g} mm nozzle")
        if p.min_feature < noz - tol:
            out.append(f"{p.text!r}: a feature of {p.min_feature:.3f} mm under the nozzle")
        sl = lab.slots[p.slot] if p.slot < len(lab.slots) else None
        if lab.kind == "white":
            # the HARD line of the rule it was made under (a stroke on the
            # white is axis-aligned: its bounds; rule 1: as it was checked)
            rl = rule_of(lab.settings)
            ring = grow_rect(ext, quiet_ring(spec) * m)
            hard = keepout_rect(spec, rl.gap_min)
            if rl.exact:
                in_ring = any(_intrusion(b.bounds(), ring) > POS_TOL_MM for b in p.boxes)
                in_hard = any(_intrusion(b.bounds(), hard) > POS_TOL_MM for b in p.boxes)
            else:
                in_ring = any(_overlap(q, rect_poly(ring)) for q in polys)
                in_hard = any(_overlap(q, rect_poly(hard)) for q in polys)
            if in_ring:
                out.append(f"{p.text!r}: ink inside the quiet ring")
            elif in_hard:
                out.append(f"{p.text!r}: ink within {rl.gap_min:g} module of the quiet zone")
            continue
        where = sl.where if sl else ""
        if where == "square":
            S = spec.square_length_m * 1000.0
            sq = label_square(spec, ink_rect(p.boxes), lab.settings.rule)
            if any(not (sq[0] - tol <= x <= sq[2] + tol and sq[1] - tol <= y <= sq[3] + tol)
                   for q in polys for x, y in q):
                out.append(f"{p.text!r}: ink outside the black square")
            d = min((pt_poly_dist(c, q) for q in polys for c in charuco_corners_mm(spec)),
                    default=math.inf)
            if d < SQUARE_CORNER_HARD * S - tol:
                out.append(f"{p.text!r}: {d / S:.2f} square from a ChArUco corner "
                           f"(< {SQUARE_CORNER_HARD:g})")
            continue
        squares = marker_squares(spec)
        idx = (sl.square if sl.square is not None else sl.marker or 0) if sl else 0
        if where not in ROWS or idx >= len(squares):
            out.append(f"{p.text!r}: not in a known place ({where!r})")
            continue
        x0, y0, x1, y1 = squares[idx][1]
        if where == "top":
            band = (x0 + m, y1 - (1.0 - BLACK_EDGE) * m, x1 - m, y1 - BLACK_EDGE * m)
        else:
            band = (x0 + m, y0 + BLACK_EDGE * m, x1 - m, y0 + (1.0 - BLACK_EDGE) * m)
        r = ink_rect(p.boxes)
        if r is None:
            continue
        if r[1] < band[1] - tol or r[3] > band[3] + tol:
            out.append(f"{p.text!r}: ink outside the {where} row's band "
                       f"({BLACK_EDGE:g} module of black kept to its edges)")
        if r[0] < band[0] - tol or r[2] > band[2] + tol:
            out.append(f"{p.text!r}: ink in a corner cell")
        if r[3] - r[1] > BLACK_CAP * m + tol:
            out.append(f"{p.text!r}: cap {r[3] - r[1]:.3f} mm over {BLACK_CAP:g} module")
    return out
