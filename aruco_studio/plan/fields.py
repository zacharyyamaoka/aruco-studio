"""Every field of a TagSpec: its key path, type, default, limits and
choices (ARCHITECTURE 5.6). GET /api/form serves this list and the Studio's
inspector is built from it, never from a hand-written copy. Every limit is
the core's named constant.

`bad` is a value out of range, and `level` what `plan.spec.check` (or the
plan) says about it: tests/plan/test_validate.py runs one case per row and
checks the Issue's `field` is the row's key path.

M6a (manufacturing intent): every row says where it applies, `intent`
"3d" (3D printed only), "2d" (a printed sticker only) or "both", and may
carry `label_2d` (its words on a sticker). New rows: Holes, the sticker's
Perimeter / thickness / margin / cut line, Made by (read only: the preset
decides) and the Make rule. A ChArUco board's label offers "In a black
square" only (`choices_by_layout`, `hidden_layouts`); a Marker sticker
with no margin offers "On the black" only (`choices_when`).
"""
from __future__ import annotations

from typing import List

from ..core import autosize as _A
from ..core import board as _B
from ..core import chamfer as _CH
from ..core import dictionary as _D
from ..core import form as _F
from ..core import label as _L
from ..core import make as _MK
from ..core import settings as _S
from ..core import slabs as _SL
from ..core import trim as _TR
from .spec import QUIET_LOW, QUIET_MAX, QUIET_MIN
from .target import KINDS


def _choices(pairs):
    return [{"value": v, "label": t} for t, v in pairs]


def _plain(values):
    return [{"value": v, "label": str(v)} for v in values]


def fields() -> List[dict]:
    """The inspector's rows, in the dialog's order."""
    ls = _L.LabelSettings()
    rows = [
        # -- marker
        {"path": "settings.layout", "group": "Marker", "type": "choice", "label": "Type",
         "default": "single", "choices": _choices(_F.LAYOUT_LABELS), "bad": "hexagon",
         "level": "error"},
        {"path": "settings.dictionary", "group": "Marker", "type": "choice",
         "label": "Dictionary", "default": "DICT_4X4_50", "choices": _plain(_D.DICTIONARY_NAMES),
         "bad": "DICT_9X9_7", "level": "error"},
        {"path": "numbers.marker_id", "group": "Marker", "type": "int",
         "label": _S.PARAM_LABELS["marker_id"], "default": 0, "min": 0,
         "max_note": "the dictionary's capacity less the board's count", "bad": 50,
         "level": "error"},
        {"path": "settings.quiet_modules", "group": "Marker", "type": "number",
         "label": "Quiet zone (modules)", "default": 1.0, "min": QUIET_MIN, "max": QUIET_MAX,
         "warn_below": QUIET_LOW, "bad": 0.2, "level": "error"},
        {"path": "settings.grow", "group": "Marker", "type": "bool",
         "label": "Grow cells (fuse corners)", "default": False},
        # -- size
        {"path": "numbers.size", "group": "Size", "type": "mm",
         "label": _S.PARAM_LABELS["size"], "default": 0.0, "min": 0.0, "auto": 0.0, "bad": -3.0,
         "level": "error"},
        {"path": "numbers.square", "group": "Size", "type": "mm",
         "label": _S.PARAM_LABELS["square"], "default": 0.0, "min": 0.0, "auto": 0.0,
         "layouts": ["charuco"], "bad": -1.0, "level": "error"},
        {"path": "settings.force", "group": "Size", "type": "pair",
         "label": "Columns x rows (a typed size)", "default": None, "min": 1,
         "min_charuco": 2, "layouts": ["grid", "charuco"], "bad": [0, 3], "level": "error"},
        {"path": "settings.cells", "group": "Size", "type": "object", "label": "Cells",
         "default": None, "rule": _A.CELL_RULE, "of": list(_A.CELL_OF),
         "min_mm": _A.MIN_STEP_M * 1000.0, "max_mm": _A.MAX_STEP_M * 1000.0,
         "bad": {"rule": 9, "of": "cell", "mm": 0.68}, "level": "warn"},
        # -- layers
        {"path": "settings.mode", "group": "Layers", "type": "choice", "label": "Colours",
         "default": "auto", "choices": _choices(_F.MODE_LABELS), "bad": "purple",
         "level": "error"},
        {"path": "settings.op", "group": "Layers", "type": "choice", "label": "Operation",
         "default": "join", "choices": _choices(_F.OP_LABELS), "bad": "glue", "level": "error"},
    ]
    for k in _SL.NUMBER_KEYS:
        rows.append({"path": f"numbers.{k}", "group": "Layers", "type": "mm",
                     "label": _S.PARAM_LABELS[k], "default": _SL.default_numbers("both")[k],
                     "min": -_SL.LIMIT_MM, "max": _SL.LIMIT_MM,
                     "min_abs": (_SL.WHITE_MIN_MM if k == "white_height" else
                                 _SL.BLACK_MIN_MM if k == "black_height" else None),
                     "bad": 80.0, "level": "error"})
    rows += [
        # -- origin
        {"path": "settings.turn", "group": "Origin", "type": "choice", "label": "Origin",
         "default": 0, "choices": _plain((0, 90, 180, 270)), "bad": 45, "level": "warn"},
        {"path": "settings.origin_v", "group": "Origin", "type": "rule", "label": "Origin rule",
         "default": 2, "read_only": True, "bad": 7, "level": "warn"},
        # -- corner mark
        {"path": "settings.corner_mark", "group": "Corner mark", "type": "choice",
         "label": "Corner mark", "default": "none",
         "choices": [{"value": v, "label": _CH.CHOICE_LABELS[v]} for v in _CH.CHOICES],
         "bad": "star", "level": "warn"},
        # -- pins
        {"path": "settings.pin", "group": "Pins", "type": "choice", "label": "Locating pins",
         "default": "none", "choices": _choices(_F.PIN_LABELS), "bad": "hexagon",
         "level": "error"},
    ]
    for k in _SL.PIN_KEYS:
        lo, hi = _SL.PIN_LIMITS[k]
        rows.append({"path": f"numbers.{k}", "group": "Pins", "type": "mm",
                     "label": _S.PARAM_LABELS[k], "default": _SL.pin_defaults()[k], "min": lo,
                     "max": hi, "bad": hi + 5.0, "level": "error"})
    # -- how it is made (M6a): the preset decides; Made by is a read-only line
    rows += [
        {"path": "settings.make", "group": "Make", "type": "object", "label": "Make rule",
         "default": None, "rule": _MK.MAKE_RULE, "read_only": True, "intent": "both",
         "bad": {"rule": 9}, "level": "warn"},
        {"path": "settings.make.by", "group": "Make", "type": "choice", "label": "Made by",
         "default": "print3d", "choices": _choices(_MK.BY_LABELS), "read_only": True,
         "intent": "both", "badges": dict(_MK.BY_BADGE), "bad": "laser", "level": "warn"},
        {"path": "settings.make.perimeter", "group": "Marker", "type": "choice",
         "label": "Perimeter", "default": "marker", "choices": _choices(_MK.PERIMETER_LABELS),
         "intent": "2d", "on_3d": "settings.trim", "bad": "circle", "level": "warn"},
        {"path": "settings.make.thickness_mm", "group": "Make", "type": "mm",
         "label": "Sticker thickness", "default": _MK.STOCK_MM, "min": _MK.THICKNESS_MM[0],
         "max": _MK.THICKNESS_MM[1], "intent": "2d", "bad": -1.0, "level": "warn"},
        {"path": "settings.make.margin_mm", "group": "Make", "type": "mm",
         "label": "Sticker margin", "default": 0.0, "min": _MK.MARGIN_MM[0],
         "max": _MK.MARGIN_MM[1], "intent": "2d", "bad": 75.0, "level": "warn"},
        {"path": "settings.make.cut_line", "group": "Make", "type": "bool", "label": "Cut line",
         "default": True, "intent": "2d", "bad": "yes", "level": "warn"},
        {"path": "settings.holes", "group": "Marker", "type": "choice", "label": "Holes",
         "default": "avoid", "choices": _choices(_MK.HOLES_LABELS), "intent": "both",
         "show_when": "target has holes", "bad": "maybe", "level": "warn"},
    ]
    # -- label
    lab = [("on", "bool", "Label", None, None),
           ("content", "choice", "Content", _choices(_F.LABEL_CONTENT), "poem"),
           ("text", "text", "Custom text", None, None),
           ("place", "choice", "Position", _choices(_F.LABEL_PLACE), "moon"),
           ("row", "choice", "Row (on the black)", _choices(_F.LABEL_ROW), "middle"),
           ("side", "choice", "Side (on the white)", _choices(_F.LABEL_SIDE), "inside"),
           ("scope", "choice", "Markers (a board)", _choices(_F.LABEL_SCOPE), "some"),
           ("cap_mm", "mm", "Letter height (0 = auto)", None, -2.0),
           ("nozzle_mm", "mm", "Nozzle", None, -0.4),
           ("stroke_mm", "mm", "Stroke (0 = auto)", None, -1.0),
           ("position", "choice", "Placed", _plain(_L.POSITIONS), "floating"),
           ("x_mm", "mm", "X (manual)", None, None),
           ("y_mm", "mm", "Y (manual)", None, None),
           ("offset_x_mm", "mm", "Legacy nudge X", None, None),
           ("offset_y_mm", "mm", "Legacy nudge Y", None, None),
           ("build_anyway", "bool", "Build anyway", None, None),
           ("rule", "rule", "Label rule", _plain(sorted(_L.RULES)), 9)]
    square_only = [{"value": "black", "label": "In a black square"}]
    for key, typ, label, choices, bad in lab:
        row = {"path": f"settings.label.{key}", "group": "Label", "type": typ, "label": label,
               "default": getattr(ls, key)}
        if choices:
            row["choices"] = choices
        if key == "place":
            # FB-13: a ChArUco label goes in a black square only; FB-11: a
            # Marker sticker without a margin has no white for it
            row["choices_by_layout"] = {"charuco": square_only}
            row["choices_when"] = [{"when": {"settings.make.by": "sticker",
                                             "settings.make.perimeter": "marker",
                                             "settings.make.margin_mm": 0.0},
                                    "choices": [c for c in choices if c["value"] == "black"]}]
        if key in ("row", "side"):
            row["hidden_layouts"] = ["charuco"]
        if key == "nozzle_mm":
            row["label_2d"] = "Stroke"
        if key == "stroke_mm":
            row["intent"] = "3d"                    # a sticker's Stroke is the row above
        if key == "rule":
            row["new"] = _L.NEW_RULE
        if key == "cap_mm":
            row.update(min=0.0, min_cap=_L.min_cap(_L.NOZZLE_MM))
        if bad is not None:
            row.update(bad=bad, level="warn")
        rows.append(row)
    rows += [
        # -- trim
        {"path": "settings.trim", "group": "Trim", "type": "object", "label": "Trim excess",
         "default": None, "rule": _TR.RULE, "axes": list(_TR.AXES),
         "bad": {"rule": 1, "axes": "diagonal"}, "level": "warn"},
        {"path": "settings.trim.margin_mm", "group": "Trim", "type": "mm", "label": "Margin",
         "default": 0.0, "min": 0.0, "max": _TR.MARGIN_MAX_MM, "bad": 75.0, "level": "warn"},
        # -- the target
        {"path": "target.kind", "group": "Target", "type": "choice", "label": "Target",
         "default": "face", "choices": _plain(KINDS), "bad": "cloud", "level": "error"},
        {"path": "target.z_sign", "group": "Target", "type": "choice", "label": "Side",
         "default": 1, "choices": _plain((1, -1)), "bad": 3, "level": "error"},
        {"path": "target.w_mm", "group": "Target", "type": "mm", "label": "Width",
         "default": 40.0, "min_exclusive": 0.0, "bad": 0.0, "level": "error"},
        {"path": "target.h_mm", "group": "Target", "type": "mm", "label": "Height",
         "default": 40.0, "min_exclusive": 0.0, "bad": -5.0, "level": "error"},
        {"path": "target.loops_mm", "group": "Target", "type": "loops", "label": "Outline",
         "default": [], "bad": [[[0, 0], [1, 1]]], "level": "error"},
        {"path": "target.body_mm", "group": "Target", "type": "box", "label": "Body under it",
         "default": None, "bad": {"u0": -1, "v0": -1, "u1": 1, "v1": 1, "z0": 0, "z1": -3},
         "level": "error"},
        {"path": "name", "group": "Tag", "type": "text", "label": "Name ({name})", "default": ""},
        {"path": "key", "group": "Tag", "type": "text", "label": "Key ({key})", "default": "",
         "unique": "scene"},
    ]
    three_d = {"settings.mode", "settings.op", "settings.grow", "settings.pin", "settings.trim",
               "settings.trim.margin_mm"} | {f"numbers.{k}" for k in _SL.NUMBER_KEYS} | \
        {f"numbers.{k}" for k in _SL.PIN_KEYS}
    for r in rows:
        r.setdefault("intent", "3d" if r["path"] in three_d else "both")
        if r["path"] == "settings.cells":
            r["label_2d"] = "Cells (whole dots)"
        if r["path"] == "settings.trim":
            r["label_perimeter"] = "Perimeter"        # on a 3D tag Perimeter IS Trim excess
    for r in rows:
        _present(r)
    return rows


# --------------------------------------------------------------- presentation
# M8b2 (M8 note 4.3): the keys a renderer needs, so no shell keeps a second
# copy (the Studio's old layout.ts; REF aruco_extrude_ui's ROUTE / TABS /
# MSG_ROWS / FALLBACK / *_ICONS / _show_*). Only words about where and how a
# row is drawn: nothing here changes a value, a limit or a message.
#
# | Key | Meaning |
# |---|---|
# | `tab` | `root` (above the tabs), `header` (the inspector's head), `none` (drawn elsewhere: the shape's rows), or a tab of TABS |
# | `icon` | on each choice: the glyph's name (the Studio's icon set) |
# | `icons_by_layout` | the Origin row's glyphs per layout (REF UP_ICONS / CORNER_ICONS) |
# | `show_when` | `{layouts, made_by, target, values: {path: [..]}, truthy: [path], any_truthy: [path]}`: every key given must hold; absent = always |
# | `anchor` | the row (or `target`, `preset`, `name`: the inspector's own rows) that shows this row's messages while it is hidden |
# | `unit`, `step`, `drag` | mm / modules / deg; the step of a scrub or an arrow key (never a rounding of what is typed); a handle kind |
# | `preset` | true when a print preset writes the field (core.presets WORDS) |

TABS = [{"id": "marker", "name": "Marker", "icon": "t-marker"},
        {"id": "heights", "name": "Heights", "icon": "t-heights"},
        {"id": "print", "name": "Print", "icon": "t-print"},
        {"id": "label", "name": "Label", "icon": "t-label"},
        {"id": "advanced", "name": "Advanced", "icon": "gear"}]
ROWS_OUTSIDE = ["target", "preset", "name"]       # the inspector's own rows an anchor may name

_TAB_OF_GROUP = {"Target": "root", "Marker": "marker", "Size": "marker", "Origin": "marker",
                 "Corner mark": "marker", "Layers": "heights", "Pins": "heights", "Label": "label",
                 "Trim": "advanced", "Tag": "advanced", "Make": "print"}
_TAB_OF_PATH = {"settings.quiet_modules": "print", "settings.grow": "print", "settings.cells": "print",
                "settings.origin_v": "advanced", "target.kind": "advanced",
                "target.z_sign": "advanced", "settings.label.rule": "advanced",
                "settings.make": "advanced", "settings.make.by": "root", "name": "header",
                "target.w_mm": "none", "target.h_mm": "none", "target.loops_mm": "none",
                "target.body_mm": "none"}
_ICONS = {"settings.layout": {"single": "single", "grid": "grid", "charuco": "charuco"},
          "settings.mode": {"auto": "m-auto", "both": "m-wb", "black": "m-black", "white": "m-white"},
          "settings.op": {"join": "join", "new": "newbody"},
          "settings.corner_mark": {"none": "cm-none", "cut": "cm-cut", "triangle": "cm-tri"},
          "settings.pin": {"none": "blank", "triangle": "pin", "round": "pin"}}
_TURN_ICONS = {"single": {"0": "up-t", "270": "up-r", "180": "up-b", "90": "up-l"},
               "grid": {"0": "o-tl", "270": "o-tr", "180": "o-br", "90": "o-bl"},
               "charuco": {"0": "o-tl", "270": "o-tr", "180": "o-br", "90": "o-bl"}}
_LABEL_SUB = "settings.label."
_ANCHOR = {"numbers.square": "numbers.size", "settings.force": "numbers.size",
           "settings.holes": "numbers.size", "settings.cells": "numbers.size",
           "settings.op": "settings.mode", "settings.trim.margin_mm": "settings.trim",
           "settings.make.perimeter": "settings.trim", "settings.origin_v": "settings.turn",
           "settings.make": "preset", "settings.make.by": "preset",
           "settings.make.thickness_mm": "preset", "settings.make.margin_mm": "preset",
           "settings.make.cut_line": "preset", "settings.mode": "preset", "settings.grow": "preset",
           "settings.pin": "preset", "settings.trim": "preset", "name": "name"}
_DRAG = {"numbers.size": "size-arrow", "numbers.white_height": "height-arrow",
         "numbers.black_height": "height-arrow", "settings.label.x_mm": "label-xy",
         "settings.label.y_mm": "label-xy"}
_STEP = {"numbers.size": 0.5, "numbers.square": 0.5, "settings.quiet_modules": 0.25,
         "settings.label.x_mm": 0.25, "settings.label.y_mm": 0.25,
         "settings.label.offset_x_mm": 0.25, "settings.label.offset_y_mm": 0.25,
         "settings.label.cap_mm": 0.1, "settings.make.margin_mm": 0.5,
         "settings.make.thickness_mm": 0.01}
# core.presets WORDS: what a print preset writes (tag.*, label.*, cells.*)
_PRESET = {"settings.dictionary", "settings.mode", "settings.op", "settings.quiet_modules",
           "settings.grow", "settings.corner_mark", "settings.pin", "settings.cells",
           "settings.make", "numbers.white_offset", "numbers.white_height", "numbers.black_offset",
           "numbers.black_height", "numbers.pin_size", "numbers.pin_length", "numbers.pin_tol"} | {
    _LABEL_SUB + k for k in ("on", "content", "text", "place", "row", "side", "scope", "cap_mm",
                             "nozzle_mm")}
_MADE_BY = {"3d": ["print3d"], "2d": ["sticker"], "both": None}


def _show_when(r: dict) -> dict:
    p = r["path"]
    out: dict = {}
    if r.get("layouts"):
        out["layouts"] = list(r["layouts"])
    if r.get("hidden_layouts"):
        out["layouts"] = [x for x in _B.LAYOUTS if x not in r["hidden_layouts"]]
    by = _MADE_BY.get(r.get("intent", "both"))
    if by and p != "settings.make.perimeter":       # Perimeter IS Trim excess on a 3D tag
        out["made_by"] = by
    if p == "settings.holes":
        out["target"] = ["holes"]
    if p in ("numbers.white_offset", "numbers.white_height"):
        out["values"] = {"settings.mode": ["both", "white", "auto"]}
    if p in ("numbers.black_offset", "numbers.black_height"):
        out["values"] = {"settings.mode": ["both", "black", "auto"]}
    if p == "settings.op":
        out["values"] = {"settings.mode": ["both"]}
    if p.startswith("numbers.pin_"):
        out["values"] = {"settings.pin": ["triangle", "round"]}
    if p == "settings.force":
        out["truthy"] = ["numbers.size"]
    if p.startswith(_LABEL_SUB) and p not in (_LABEL_SUB + "on", _LABEL_SUB + "rule"):
        out["truthy"] = [_LABEL_SUB + "on"]
        if p == _LABEL_SUB + "text":
            out["values"] = {_LABEL_SUB + "content": ["custom"]}
        if p in (_LABEL_SUB + "x_mm", _LABEL_SUB + "y_mm"):
            out["values"] = {_LABEL_SUB + "position": ["manual"]}
        if p in (_LABEL_SUB + "offset_x_mm", _LABEL_SUB + "offset_y_mm"):
            # the legacy nudge (before 2026-10-13): shown only on a tag that has one
            out["any_truthy"] = [_LABEL_SUB + "offset_x_mm", _LABEL_SUB + "offset_y_mm"]
    if p == "settings.trim.margin_mm":
        out["values"] = {"settings.trim.rule": [1]}
    return out


def _present(r: dict) -> None:
    p = r["path"]
    if p == "settings.holes" and isinstance(r.get("show_when"), str):
        r["show_when_words"] = r.pop("show_when")
    r["tab"] = _TAB_OF_PATH.get(p) or _TAB_OF_GROUP.get(r["group"], "advanced")
    r["show_when"] = _show_when(r)
    if p in _ANCHOR:
        r["anchor"] = _ANCHOR[p]
    elif p.startswith(_LABEL_SUB) and p not in (_LABEL_SUB + "on", _LABEL_SUB + "rule"):
        r["anchor"] = _LABEL_SUB + "on"
    elif p.startswith("numbers.pin_"):
        r["anchor"] = "settings.pin"
    elif p in ("numbers.white_offset", "numbers.white_height", "numbers.black_offset",
               "numbers.black_height"):
        r["anchor"] = "settings.mode"
    elif p.startswith("target."):
        r["anchor"] = "target"
    if r["type"] == "mm":
        r["unit"] = "mm"
    elif p == "settings.quiet_modules":
        r["unit"] = "modules"
    elif p == "settings.turn":
        r["unit"] = "deg"
    if r["type"] in ("mm", "number"):
        r["step"] = _STEP.get(p, 0.1)
    if p in _DRAG:
        r["drag"] = _DRAG[p]
    r["preset"] = p in _PRESET
    icons = _ICONS.get(p)
    if icons:
        for c in r.get("choices", []):
            c["icon"] = icons.get(str(c["value"]), "")
    if p == "settings.turn":
        r["icons_by_layout"] = _TURN_ICONS


def form() -> dict:
    """GET /api/form (the `bam.form/1` contract: `fields` with their
    presentation keys, `tabs`, `outside`)."""
    return {"schema": "arucostudio.form/1", "contract": "bam.form/1", "fields": fields(),
            "tabs": [dict(t) for t in TABS], "outside": list(ROWS_OUTSIDE),
            "groups": ["Target", "Marker", "Size", "Layers", "Origin", "Corner mark", "Pins",
                       "Make", "Label", "Trim", "Tag"],
            "intents": ["3d", "2d", "both"],
            "layouts": list(_B.LAYOUTS), "rules": {"spec": _S.SPEC_VERSION,
                                                   "cells": _A.CELL_RULE, "label": _L.RULE,
                                                   "label_new": _L.NEW_RULE,
                                                   "make": _MK.MAKE_RULE, "trim": _TR.RULE}}
