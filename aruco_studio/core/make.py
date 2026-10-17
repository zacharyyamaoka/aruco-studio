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
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

MAKE_RULE = 1
BY = ("print3d", "sticker")
PERIMETERS = ("marker", "profile")
STOCK_MM = 0.1               # a paper label (the preset's stock_mm is the default)
INK_MM = 0.01                # the printed film; never a parameter
THICKNESS_MM = (0.05, 2.0)
MARGIN_MM = (0.0, 50.0)
HOLES = ("avoid", "ignore")  # settings.holes; absent = avoid

# the words (the Made by line under Preset; badges)
BY_LABELS = [("3D printed", "print3d"), ("Printed sticker", "sticker")]
BY_BADGE = {"print3d": "3D", "sticker": "2D"}
PERIMETER_LABELS = [("Marker", "marker"), ("Profile", "profile")]
HOLES_LABELS = [("Avoid (the tag keeps clear of them)", "avoid"),
                ("Ignore (the tag may cover them)", "ignore")]

Note = Tuple[str, str, str]         # (key path, level, text)


@dataclass(frozen=True)
class Make:
    by: str = "print3d"
    rule: Optional[int] = None       # MAKE_RULE when the key was stored and read; None = absent / junk
    thickness_mm: float = STOCK_MM
    margin_mm: float = 0.0
    cut_line: bool = True
    perimeter: str = "marker"
    legacy: bool = True              # no `make` key at all: today's 3D tag

    @property
    def sticker(self) -> bool:
        return self.by == "sticker"

    @property
    def top_mm(self) -> float:
        """The ink top over the face: where the frame sits (a sticker)."""
        return self.thickness_mm + INK_MM

    def to_dict(self) -> dict:
        """What a node's record keeps (`fusion.make`) and a new tag stores."""
        if self.by != "sticker":
            return {"rule": MAKE_RULE, "by": self.by}
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
    if rule != MAKE_RULE or isinstance(rule, bool):
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


def new_make(kind: str = "print3d", profile: Optional[dict] = None) -> dict:
    """The `make` a NEW tag stores under a preset of `kind` (its profile's
    stock thickness for a sticker)."""
    if kind != "sticker":
        return {"rule": MAKE_RULE, "by": "print3d"}
    stock = (profile or {}).get("stock_mm", STOCK_MM)
    t = float(stock) if _finite(stock) and THICKNESS_MM[0] <= stock <= THICKNESS_MM[1] \
        else STOCK_MM
    return Make(by="sticker", rule=MAKE_RULE, thickness_mm=t, legacy=False).to_dict()


def twin_numbers(make: Make, numbers: dict) -> dict:
    """The numbers of the sticker's 3D twin: White + black, the white stock
    0..t + INK, the black a flush INK inlay from the top (core.slabs gives
    white [0, t + INK], pattern [t, t + INK], surface t + INK)."""
    n = dict(numbers)
    top = make.thickness_mm + INK_MM
    n.update(white_offset=0.0, white_height=top, black_offset=top, black_height=-INK_MM)
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
    """The read-only line under Preset: "Made by: Printed sticker · 600 dpi · Letter"."""
    lab = dict((v, t) for t, v in BY_LABELS)[make.by]
    bits = [f"Made by: {lab}"]
    if make.sticker:
        if dpi:
            bits.append(f"{dpi} dpi")
        if page:
            bits.append(page[:1].upper() + page[1:] if page != "a4" else "A4")
    return " · ".join(bits)
