"""Manufacturing intent: how a tag is made (design notes
docs/design/manufacturing_intent.md and M6_stickers_profiles_print.md).

NEW, not REF's. Standard library only, no file I/O.

The stored setting is versioned like `cells` and `trim`:

    settings["make"] = {"rule": 1, "by": "print3d"}
    settings["make"] = {"rule": 1, "by": "sticker", "thickness_mm": 0.1,
                        "margin_mm": 0.0, "cut_line": true, "perimeter": "marker"}

| Rule | |
|---|---|
| absent | a 3D printed tag, bit for bit as before (`Make.legacy`) |
| an unknown rule, an unknown `by`, junk | read as 3D printed, with a `warn` on its key path |
| `thickness_mm` out of 0.05..2, `margin_mm` out of 0..50 | clamped, with a `warn` |
| `perimeter` | `"marker"` (the sticker is the marker's rectangle) or `"profile"` (the target's outline, holes included); anything else reads as marker with a `warn` |

A sticker plans as a flush inlay on a thin tile: the white stock
[0, t], the black ink [t, t + INK_MM], the tag frame (and OpenCV's) on
the ink top, t + INK_MM over the face.

Rule 2 (2026-10-17, Zach's CF-7: "Black part can be paper thickness/2 and
go into the rectangle"; the 2D pivot CF-13) is what a NEW inkjet sticker
stores:

    settings["make"] = {"rule": 2, "by": "sticker", "thickness_mm": 0.1,
                        "perimeter": "marker", "page": "letter",
                        "page_margin_mm": 10.0}

| | Rule 1 (kept for the tags that have it) | Rule 2 (a new sticker) |
|---|---|---|
| the paper | [0, t] | [0, t]: ONE paper body, the whole sticker outline |
| the black | a film [t, t + INK_MM] on top | the top half of the paper, [t/2, t], inside it: flush, no film |
| the tag frame | t + INK_MM | t: the paper's top |
| margin, cut line | on the tag (`margin_mm`, `cut_line`) | on the sheet (core.sheet.SheetSettings `sticker_margin_mm`, `cut_marks`: Zach's Q7); a rule-2 `margin_mm` / `cut_line` is read as 0 / on, with an info |
| the page | -- | `page` (core.sheet.PAGE_SIZES_MM) and `page_margin_mm`: the printable area the page lint and Auto's cap read (CF-6) |

Which rule a new sticker gets is its preset's (`profile.make_rule`, 2 on
the built-in vinyl presets; a sticker profile without it -- every preset
file and frozen copy made before -- is rule 1), so a file that names an
older sticker preset plans exactly as before. No preset at all: rule 2.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

MAKE_RULE = 1                # the first rule (REF's record readers know it)
INSET_RULE = 2               # the black t/2 inside the paper (CF-7): a NEW sticker's
MAKE_RULES = (MAKE_RULE, INSET_RULE)
BY = ("print3d", "sticker")
PERIMETERS = ("marker", "profile")
STOCK_MM = 0.1               # a paper label (the preset's stock_mm is the default)
INK_MM = 0.01                # rule 1's printed film; never a parameter
THICKNESS_MM = (0.05, 2.0)
MARGIN_MM = (0.0, 50.0)
PAGE_MARGIN_MM = 10.0        # rule 2: the page's margins (the preset's margin_mm)
PAGES = ("letter", "a4", "legal", "a3", "tabloid", "a5")     # core.sheet.PAGE_SIZES_MM
HOLES = ("avoid", "ignore")  # settings.holes; absent = avoid

# vinyl inkjet sticker paper, the sticker as it sits on the part (liner
# peeled off): a 3-4 mil (0.08-0.10 mm) printable vinyl face and its
# adhesive come to about 0.10 mm; the sheet with its liner measures about
# 0.2 mm. A default to MEASURE (a peeled sticker on glass, calipers zeroed
# on the glass): the tag frame sits on the paper's top, t over the face.
VINYL_MM = 0.10
# the suggestions the Paper thickness row offers (Zach liked one-click
# suggestions that fill a value in, 2026-10-17); typical, not measured
PAPER_STOCKS = [
    {"value": 0.10, "label": "Vinyl, liner off (typical: 0.10 mm)"},
    {"value": 0.08, "label": "Paper label, liner off (0.08 mm)"},
    {"value": 0.18, "label": "Vinyl + clear laminate, liner off (0.18 mm)"},
    {"value": 0.20, "label": "A vinyl sheet with its liner (0.20 mm: not what is stuck on)"},
]

# the words (the Made by line under Preset; badges). The stored kind stays
# "sticker" (files); every label says Inkjet printer (2026-10-17, CF-4)
BY_LABELS = [("3D printed", "print3d"), ("Inkjet printer", "sticker")]
BY_BADGE = {"print3d": "3D", "sticker": "2D"}
PERIMETER_LABELS = [("Marker", "marker"), ("Profile", "profile")]
HOLES_LABELS = [("Avoid (the tag keeps clear of them)", "avoid"),
                ("Ignore (the tag may cover them)", "ignore")]

Note = Tuple[str, str, str]         # (key path, level, text)


@dataclass(frozen=True)
class Make:
    by: str = "print3d"
    rule: Optional[int] = None       # the rule stored and read (1 or 2); None = absent / junk
    thickness_mm: float = STOCK_MM
    margin_mm: float = 0.0
    cut_line: bool = True
    perimeter: str = "marker"
    legacy: bool = True              # no `make` key at all: today's 3D tag
    page: str = "letter"             # rule 2: the page the sticker prints on (the lint)
    page_margin_mm: float = PAGE_MARGIN_MM

    @property
    def sticker(self) -> bool:
        return self.by == "sticker"

    @property
    def inset(self) -> bool:
        """Rule 2: the black t/2 inside the paper (CF-7)."""
        return self.by == "sticker" and self.rule == INSET_RULE

    @property
    def ink_mm(self) -> float:
        """How deep the black is: rule 1's film, rule 2's half the paper."""
        return self.thickness_mm / 2.0 if self.inset else INK_MM

    @property
    def paper_z(self) -> Tuple[float, float]:
        """The paper's z range over the face (mm): [0, t]."""
        return (0.0, float(self.thickness_mm))

    @property
    def ink_z(self) -> Tuple[float, float]:
        """The black's z range (mm): rule 1 [t, t + INK], rule 2 [t/2, t]."""
        t = float(self.thickness_mm)
        return (t / 2.0, t) if self.inset else (t, t + INK_MM)

    @property
    def top_mm(self) -> float:
        """The sticker's top over the face: where the frame sits (rule 1:
        the ink film's top; rule 2: the paper's top)."""
        return self.ink_z[1]

    def to_dict(self) -> dict:
        """What a node's record keeps (`fusion.make`) and a new tag stores."""
        if self.by != "sticker":
            return {"rule": self.rule if self.rule in MAKE_RULES else MAKE_RULE, "by": self.by}
        if self.inset:
            return {"rule": INSET_RULE, "by": "sticker", "thickness_mm": float(self.thickness_mm),
                    "perimeter": self.perimeter, "page": self.page,
                    "page_margin_mm": float(self.page_margin_mm)}
        return {"rule": MAKE_RULE, "by": "sticker", "thickness_mm": float(self.thickness_mm),
                "margin_mm": float(self.margin_mm), "cut_line": bool(self.cut_line),
                "perimeter": self.perimeter}


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def make_of(settings) -> Tuple[Make, List[Note]]:
    """A tag's settings -> (Make, [(field, level, text)]). Never raises."""
    s = settings if isinstance(settings, dict) else {}
    if "make" not in s or s.get("make") is None:
        return Make(), []
    m = s["make"]
    notes: List[Note] = []
    if not isinstance(m, dict):
        return Make(legacy=False), [("settings.make", "warn",
                                     f"make {m!r} is not a setting this version knows: read as "
                                     "3D printed")]
    rule = m.get("rule", MAKE_RULE)
    if isinstance(rule, bool) or rule not in MAKE_RULES:
        return Make(legacy=False), [("settings.make", "warn",
                                     f"make rule {rule!r} is not {MAKE_RULE}: read as 3D printed")]
    by = m.get("by", "print3d")
    if by not in BY:
        return Make(legacy=False), [("settings.make.by", "warn",
                                     f"made by {by!r} is not one of {', '.join(BY)}: read as "
                                     "3D printed")]
    t = m.get("thickness_mm", STOCK_MM)
    if not _finite(t):
        notes.append(("settings.make.thickness_mm", "warn",
                      f"sticker thickness {t!r}: a number ({STOCK_MM:g} mm used)"))
        t = STOCK_MM
    lo, hi = THICKNESS_MM
    if not lo <= t <= hi:
        c = min(hi, max(lo, float(t)))
        notes.append(("settings.make.thickness_mm", "warn",
                      f"sticker thickness {t:g} mm: {lo:g} to {hi:g} mm (clamped to {c:g})"))
        t = c
    if rule == INSET_RULE:
        per = m.get("perimeter", "marker")
        if per not in PERIMETERS:
            notes.append(("settings.make.perimeter", "warn",
                          f"perimeter {per!r} is not one of {', '.join(PERIMETERS)}: marker"))
            per = "marker"
        return _rule2(m, by, float(t), per, notes)
    mg = m.get("margin_mm", 0.0)
    if not _finite(mg):
        notes.append(("settings.make.margin_mm", "warn",
                      f"sticker margin {mg!r}: a number (0 mm used)"))
        mg = 0.0
    lo, hi = MARGIN_MM
    if not lo <= mg <= hi:
        c = min(hi, max(lo, float(mg)))
        notes.append(("settings.make.margin_mm", "warn",
                      f"sticker margin {mg:g} mm: {lo:g} to {hi:g} mm (clamped to {c:g})"))
        mg = c
    per = m.get("perimeter", "marker")
    if per not in PERIMETERS:
        notes.append(("settings.make.perimeter", "warn",
                      f"perimeter {per!r} is not one of {', '.join(PERIMETERS)}: marker"))
        per = "marker"
    cut = m.get("cut_line", True)
    if not isinstance(cut, bool):
        notes.append(("settings.make.cut_line", "warn", f"cut line {cut!r}: true or false (on)"))
        cut = True
    if by == "print3d":
        # a 3D tag keeps the sticker's numbers it was given (checked, unused)
        return Make(by="print3d", rule=MAKE_RULE, legacy=False), notes
    return Make(by="sticker", rule=MAKE_RULE, thickness_mm=float(t), margin_mm=float(mg),
                cut_line=cut, perimeter=per, legacy=False), notes


def _rule2(m: dict, by: str, t: float, per: str, notes: List[Note]) -> Tuple[Make, List[Note]]:
    """Rule 2's keys: the page and its margins (the lint); the sticker's own
    margin and cut line are the sheet's now (Q7), read as 0 / on."""
    if by == "print3d":
        # rule 2 changes the sticker only: a 3D tag under it is rule 1's
        return Make(by="print3d", rule=INSET_RULE, legacy=False), notes
    pg = m.get("page", "letter")
    if not isinstance(pg, str) or pg.lower() not in PAGES:
        notes.append(("settings.make.page", "warn",
                      f"page {pg!r} is not one of {', '.join(PAGES)}: letter"))
        pg = "letter"
    pg = pg.lower()
    pm = m.get("page_margin_mm", PAGE_MARGIN_MM)
    if not _finite(pm):
        notes.append(("settings.make.page_margin_mm", "warn",
                      f"page margins {pm!r}: a number ({PAGE_MARGIN_MM:g} mm used)"))
        pm = PAGE_MARGIN_MM
    lo, hi = MARGIN_MM
    if not lo <= pm <= hi:
        c = min(hi, max(lo, float(pm)))
        notes.append(("settings.make.page_margin_mm", "warn",
                      f"page margins {pm:g} mm: {lo:g} to {hi:g} mm (clamped to {c:g})"))
        pm = c
    mg = m.get("margin_mm")
    if mg not in (None, 0, 0.0):
        notes.append(("settings.make.margin_mm", "info",
                      "a sticker's white margin is the sheet's now (Print: Sticker margin); "
                      "this tag's is not used"))
    if m.get("cut_line") not in (None, True):
        notes.append(("settings.make.cut_line", "info",
                      "cut lines are the sheet's now (Print: Cut lines); this tag's is not used"))
    return Make(by="sticker", rule=INSET_RULE, thickness_mm=t, perimeter=per, legacy=False,
                page=pg, page_margin_mm=float(pm)), notes


def holes_of(settings) -> Tuple[str, List[Note]]:
    """settings.holes -> ("avoid" | "ignore", notes). Absent = avoid."""
    s = settings if isinstance(settings, dict) else {}
    h = s.get("holes")
    if h is None or h == "avoid":
        return "avoid", []
    if h == "ignore":
        return "ignore", []
    return "avoid", [("settings.holes", "warn",
                      f"holes {h!r} is not one of {', '.join(HOLES)}: read as avoid")]


def rule_of_profile(profile: Optional[dict]) -> int:
    """The make rule a new sticker stores under a printer profile: its
    `make_rule` (2 on the vinyl presets); a sticker profile without one
    (every preset file and frozen copy made before 2026-10-17) is rule 1;
    no profile, or a 3D printer's (a sticker by `made_by`), rule 2."""
    pr = profile if isinstance(profile, dict) else {}
    if pr.get("kind") != "sticker":
        return INSET_RULE
    return INSET_RULE if pr.get("make_rule") == INSET_RULE else MAKE_RULE


def new_make(kind: str = "print3d", profile: Optional[dict] = None) -> dict:
    """The `make` a NEW tag stores under a preset of `kind` (its profile's
    stock thickness for a sticker; rule 2 also its page and margins). A 3D
    tag stores rule 1, as before (3D is a placeholder: CF-13)."""
    if kind != "sticker":
        return {"rule": MAKE_RULE, "by": "print3d"}
    pr = profile if isinstance(profile, dict) else {}
    if rule_of_profile(pr) != INSET_RULE:
        stock = pr.get("stock_mm", STOCK_MM)
        t = float(stock) if _finite(stock) and THICKNESS_MM[0] <= stock <= THICKNESS_MM[1] \
            else STOCK_MM
        return Make(by="sticker", rule=MAKE_RULE, thickness_mm=t, legacy=False).to_dict()
    sticker = pr.get("kind") == "sticker"
    stock = pr.get("stock_mm", VINYL_MM) if sticker else VINYL_MM
    t = float(stock) if _finite(stock) and THICKNESS_MM[0] <= stock <= THICKNESS_MM[1] \
        else VINYL_MM
    pg = pr.get("page") if sticker and pr.get("page") in PAGES else "letter"
    pm = pr.get("margin_mm", PAGE_MARGIN_MM) if sticker else PAGE_MARGIN_MM
    pm = float(pm) if _finite(pm) and MARGIN_MM[0] <= pm <= MARGIN_MM[1] else PAGE_MARGIN_MM
    return Make(by="sticker", rule=INSET_RULE, thickness_mm=t, legacy=False, page=pg,
                page_margin_mm=pm).to_dict()


def twin_numbers(make: Make, numbers: dict) -> dict:
    """The numbers of the sticker's 3D twin: White + black, the black a
    flush inlay from the top. Rule 1: the white stock 0..t + INK, the black
    INK deep (core.slabs gives white [0, t + INK], pattern [t, t + INK],
    surface t + INK). Rule 2: the white 0..t, the black t/2 deep (white
    [0, t], pattern [t/2, t], surface t)."""
    n = dict(numbers)
    top = make.top_mm
    n.update(white_offset=0.0, white_height=top, black_offset=top, black_height=-make.ink_mm)
    return n


def twin_settings(make: Make, settings: dict) -> Tuple[dict, List[Note]]:
    """The settings the sticker plans with: White + black, New body, no pins,
    no trim, no fused corners (a sticker is one ink path). -> (s, notes)."""
    s = dict(settings)
    notes: List[Note] = []
    s.update(mode="both", op="new", pin="none", grow=False)
    if s.pop("trim", None):
        notes.append(("settings.trim", "info", "a sticker has nothing to trim: Trim excess off"))
    return s, notes


def cut_rect(sticker_rect, make: Make):
    """The Marker perimeter's cut line: the sticker (pattern + quiet zone)
    grown by the margin, (u0, v0, u1, v1) mm, pattern frame."""
    u0, v0, u1, v1 = sticker_rect
    m = make.margin_mm
    return (u0 - m, v0 - m, u1 + m, v1 + m)


def has_white(make: Make) -> bool:
    """Is there white outside the quiet zone for a label? (FB-11)"""
    return make.perimeter == "profile" or make.margin_mm > 0.0


def badge(by: str) -> str:
    return BY_BADGE.get(by, "3D")


def words(make: Make, dpi: int = 0, page: str = "") -> str:
    """The read-only line under Preset: "Made by: Inkjet printer · 600 dpi · Letter"."""
    lab = dict((v, t) for t, v in BY_LABELS)[make.by]
    bits = [f"Made by: {lab}"]
    if make.sticker:
        if dpi:
            bits.append(f"{dpi} dpi")
        if page:
            bits.append(page[:1].upper() + page[1:] if page != "a4" else "A4")
    return " · ".join(bits)


def page_words(page: str) -> str:
    return "A4" if page == "a4" else "A3" if page == "a3" else "A5" if page == "a5" \
        else page[:1].upper() + page[1:]


# ------------------------------------------------------------- Shift (CF-2, P3)
#
# settings.shift = {"rule": 1, "x_mm": 8.0, "y_mm": -6.0}: the tag moved by
# hand off the place the fit gives it (the centre of its clear rectangle; on
# a plain profile, the profile's centre), along the TARGET's own u (x) and v
# (y), mm. Absent = centred, bit for bit as before. A sticker's (3D tags are
# a placeholder, CF-13: a 3D tag reads it and does not move, with an info).

SHIFT_RULE = 1
SHIFT_MAX_MM = 500.0


def shift_of(settings) -> Tuple[Tuple[float, float], List[Note]]:
    """settings.shift -> ((x_mm, y_mm), notes). Absent / junk = (0, 0)."""
    s = settings if isinstance(settings, dict) else {}
    v = s.get("shift")
    if v is None:
        return (0.0, 0.0), []
    if not isinstance(v, dict) or v.get("rule", SHIFT_RULE) != SHIFT_RULE \
            or isinstance(v.get("rule"), bool):
        return (0.0, 0.0), [("settings.shift", "warn",
                             f"shift {v!r} is not a shift this version knows (rule {SHIFT_RULE}, "
                             "x_mm, y_mm): centred")]
    out, notes = [], []
    for k in ("x_mm", "y_mm"):
        x = v.get(k, 0.0)
        if not _finite(x):
            notes.append((f"settings.shift.{k}", "warn", f"shift {k} {x!r}: a number (0 used)"))
            x = 0.0
        if abs(x) > SHIFT_MAX_MM:
            c = max(-SHIFT_MAX_MM, min(SHIFT_MAX_MM, float(x)))
            notes.append((f"settings.shift.{k}", "warn",
                          f"shift {k} {x:g} mm: within ±{SHIFT_MAX_MM:g} mm (clamped)"))
            x = c
        out.append(float(x))
    return (out[0], out[1]), notes


# ------------------------------------------------------------- the page lint (CF-6)

def printable_mm(make: Make) -> Optional[dict]:
    """A rule-2 sticker's page: what core.sheet.layout_stickers places in
    (the page less its margins, the footer and the scale bars' band),
    portrait and landscape. None for a tag that is not a rule-2 sticker
    (rule 1 never stored a page)."""
    if not make.inset:
        return None
    from . import sheet as _SHT
    return _SHT.printable_options(make.page, make.page_margin_mm)


def page_fit(w_mm: float, h_mm: float, make: Make) -> Optional[dict]:
    """Does a w x h sticker (its cut outline's box) fit the printable area
    of the tag's page, on a portrait or a landscape sheet, as it is or
    turned 90 degrees (the sheet turns a sticker that only fits turned)?
    -> {"fits", "how", "over_mm", "worst_mm", "area_mm", "page", "margin_mm"}
    or None (not a rule-2 sticker)."""
    opts = printable_mm(make)
    if opts is None:
        return None
    from . import sheet as _SHT
    return _SHT.fit_area(w_mm, h_mm, opts, make.page, make.page_margin_mm)


def lint_text(fit: dict, w_mm: float, h_mm: float) -> str:
    """The red row's words (CF-6: allowed, flagged like a linter)."""
    aw, ah = fit["area_mm"]
    dw, dh = fit["over_mm"]
    which = (" (width)" if dw > 0 and dh <= 0 else " (height)" if dh > 0 and dw <= 0 else "")
    return (f"Over the page by {fit['worst_mm']:.1f} mm{which}: the sticker is "
            f"{w_mm:.1f} × {h_mm:.1f} mm, {page_words(fit['page'])} less "
            f"{fit['margin_mm']:g} mm margins prints {aw:.1f} × {ah:.1f} mm (either way round, "
            "portrait or landscape). It still builds; the sheet will not place it. "
            "A smaller Marker size, Auto size, or a bigger page fits it")
