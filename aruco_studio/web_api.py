"""The online Studio's facade (arucostudio.com, docs/design/online_studio_v1.md):
one function per `CoreApi` call of web/src/core/contract.ts, plain dicts in
and out, and `call(name, payload_json)` for the Pyodide worker.

Standard library only: the same file runs in the browser (Pyodide) and in
CPython (tests/web/), and web/scripts/parity.mjs proves the two give the
same JSON byte for byte.

Frame: the sketch plane, x right, y up, mm. The core plans the marker in
its rectangle (a box `Target` the rectangle's size; `settings.as_typed`, so
a typed size is drawn as typed and flagged, never clamped); this module only
places the plan's pattern frame in the sketch -- the rectangle's centre and
angle, the plan's own turn, and Flip (half a turn about the pattern's x, as
Fusion composes a Joint Origin: core.geometry.jo_compose).

| contract | core |
|---|---|
| `marker.type`, `dictionary`, `first_id` | `settings.layout`, `settings.dictionary`, `numbers.marker_id` |
| `marker.auto` true | `numbers.size` 0 (a ChArUco checker 0 too); a grid / ChArUco keeps its typed count (`settings.force`), which Auto fills the rectangle with (autosize.fill_count) |
| `marker.marker_mm`, `checker_mm`, `separation_mm` (auto false) | `numbers.size`, `numbers.square`, `numbers.separation` (grid; 0 = the gap rule) |
| `marker.cols`, `rows` | `settings.force`: the counts along the rectangle's x / y, before the turn (a board turned 90 builds rows x cols, `MarkerPlan.outer_mm` is in its own frame) |
| `marker.turn`, `quiet_modules`, `corner_mark` | `settings.turn` (+ `origin_v` 2), `settings.quiet_modules`, `settings.corner_mark` |
| `preset` (method inkjet) | `settings.make` = core.make.new_make("sticker", profile): rule 2, its page, margins and paper thickness |
| `preset` (method print3d) | `settings.make` = new_make("print3d") |
| `preset.cell_step_mm`, `min_cell_mm` | `settings.cells` {"of": "cell", "mm": step} (0 = no snap: {"of": "marker", "mm": 0.5}, the legacy step) |
| `reference_face` | the target is a "profile" with a body (Flip does not apply) else "free" |
| `label` on (2026-10-18) | core.rect_fill.fill: a band inside the rectangle on `label.side`; the marker is planned in the box it leaves (the target), centred there; "sans" text for an inkjet preset, the pixel font's ink for 3D |
| `marker.origin_square` | core.rect_fill.square_origin on OpenCV's board frame |
| `MarkerPlan.layers`, `cells`, `pattern_to_sketch`, `origin_z_mm` (CAD shells, N-6) | the TagPlan's `layers` placed like `black`; core.markers.cell_boxes; the matrix `black` is placed with; `origin`'s z (the printed surface: inkjet t, 3D the tile's top, on a face 0; Flip negates) |

Issue fields: the core's key paths renamed (FIELDS); the page lint ("Over
the page ...") and the cell / make rows -> "preset"; target -> "rect".
"""
from __future__ import annotations

import base64
import datetime
import json
import math
import platform
import re
from types import SimpleNamespace

from . import __version__
from .core import autosize as _A
from .core import dictionary as _D
from .core import label as _AL
from .core import make as _MK
from .core import markers as _M
from .core import presets as _P
from .core import rect_fill as _RF
from .core import sheet as _SH
from .plan import TagSpec, Target, plan_tag
from .plan import exports as _X
from .plan import mesh as _ME
from .scene import sheet as _SS

API = ("info", "presets", "inscribe", "plan", "suggest", "svg", "sheet", "verify", "readable", "assign_ids")

# core key path -> the contract's field (contract.ts Issue.field)
FIELDS = {"numbers.size": "marker.marker_mm", "numbers.square": "marker.checker_mm",
          "numbers.separation": "marker.separation_mm", "numbers.marker_id": "marker.first_id",
          "settings.dictionary": "marker.dictionary", "settings.layout": "marker.type",
          "settings.force": "marker.cols", "settings.turn": "marker.turn",
          "settings.flip": "marker.flip", "settings.quiet_modules": "marker.quiet_modules",
          "settings.corner_mark": "marker.corner_mark", "settings.label": "label",
          "settings.holes": "rect"}
PRESET_FIELDS = ("settings.cells", "settings.make")
TYPE_WORDS = {"single": "ArUco", "grid": "Grid", "charuco": "ChArUco"}
LABEL_TEMPLATE = "#{ids}"           # an empty label text
LABEL_CAP = _RF.LABEL_CAP          # height 0: 0.12 x the short side, within 2.5 .. 12 mm
CAP_EM = _SH.CAP_EM                 # Helvetica's cap height / em (core.sheet prints the label with it)
ND = 6                              # JSON numbers: 1e-6 mm
ND_DIM = 9                          # a dimension's endpoints (plan_dims)
SNAP_TOL_MM = 1e-6                  # inscribe: an edge this near a 0.1 mm grid line is on it


def _r(v) -> float:
    return round(float(v), ND) + 0.0


def _f(v) -> str:
    """An SVG number (plan.exports' style)."""
    t = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if t in ("-0", "") else t


def _mm(v: float) -> str:
    """28.0, 27.25, 29.97 -- one or two decimals (autosize's words)."""
    s = "%.2f" % v
    return s[:-1] if s.endswith("0") else s


# ------------------------------------------------------------------ presets

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _builtins():
    """The core's presets the web offers: Default (3D) and the rule-2 vinyl
    inkjet printers. The rule-1 stickers (core.presets.LEGACY_STICKERS) are
    kept for old files only, and a flat Preset cannot say which rule."""
    return [_P.default_preset(), _P.vinyl_preset("letter"), _P.vinyl_preset("a4")]


def flat_preset(p: dict, builtin: bool = True) -> dict:
    """A core preset as the contract's flat `Preset`."""
    pr = p["profile"]
    cs = _P.cell_setting(p)
    out = {"id": ("builtin:" if builtin else "") + _slug(p["name"]), "name": p["name"],
           "builtin": builtin, "min_cell_mm": _r(cs["min_mm"]),
           "cell_step_mm": _r(cs["mm"]) if cs["of"] == "cell" else 0.0}
    if _P.kind_of(p) == "sticker":
        page = pr.get("page", "letter")
        out.update(method="inkjet", page=_MK.page_words(page),
                   page_mm=[_r(v) for v in _SH.PAGE_SIZES_MM[page]],
                   margin_mm=_r(pr.get("margin_mm", _MK.PAGE_MARGIN_MM)),
                   thickness_mm=_r(pr.get("stock_mm", _MK.VINYL_MM)), dpi=int(pr.get("dpi", 600)))
    else:
        out.update(method="print3d", nozzle_mm=_r(pr.get("nozzle_mm") or 0.0),
                   line_mm=_r(pr.get("line_mm") or 0.0), layer_mm=_r(pr.get("layer_mm") or 0.0),
                   first_layer_mm=_r(pr.get("first_layer_mm") or 0.0))
    return out


def _page_key(preset: dict, issues: list) -> str:
    """The core's page name for a flat preset: its `page` ("Letter", "A4"),
    else the page whose size `page_mm` is, else Letter (said)."""
    page = str(preset.get("page") or "").strip().lower()
    if page in _MK.PAGES:
        return page
    pm = preset.get("page_mm")
    if isinstance(pm, (list, tuple)) and len(pm) == 2:
        for k, (a, b) in _SH.PAGE_SIZES_MM.items():
            if {round(float(pm[0]), 1), round(float(pm[1]), 1)} == {round(a, 1), round(b, 1)}:
                return k
    issues.append({"field": "preset", "level": "warn",
                   "text": f"page {preset.get('page') or pm!r} is not one the sheet prints: Letter"})
    return "letter"


def make_of(preset: dict, issues: list) -> dict:
    """`settings.make` for a flat preset."""
    if preset.get("method") != "inkjet":
        return _MK.new_make("print3d")
    profile = {"kind": "sticker", "make_rule": _MK.INSET_RULE, "page": _page_key(preset, issues),
               "stock_mm": float(preset.get("thickness_mm") or _MK.VINYL_MM),
               "margin_mm": float(preset["margin_mm"]) if preset.get("margin_mm") is not None
               else _MK.PAGE_MARGIN_MM}
    return _MK.new_make("sticker", profile)


def cells_of(preset: dict) -> dict:
    """`settings.cells` for a flat preset: cells a whole number of
    `cell_step_mm` (the line, the dot), or the marker in the legacy 0.5 mm
    steps when it is 0; `min_cell_mm` the minimum either way."""
    step = float(preset.get("cell_step_mm") or 0.0)
    mn = float(preset.get("min_cell_mm") or 0.0)
    if step > 0:
        return {"rule": _A.CELL_RULE, "of": "cell", "mm": round(step, 6), "min_mm": round(mn, 6)}
    return {"rule": _A.CELL_RULE, "of": "marker", "mm": 0.5, "min_mm": round(mn, 6)}


# ------------------------------------------------------------------ the request

def spec_of(req: dict, issues: list) -> TagSpec:
    """A PlanRequest as the core's TagSpec (the rectangle's own frame)."""
    rect, m = req["rect"], req["marker"]
    kind = m["type"]
    auto = bool(m.get("auto"))
    s = {"layout": kind, "dictionary": m["dictionary"], "origin_v": 2, "as_typed": True,
         "mode": "auto", "turn": int(m.get("turn") or 0),
         "quiet_modules": float(m.get("quiet_modules") or 1.0),
         "corner_mark": m.get("corner_mark") or "none",
         "make": make_of(req.get("preset") or {}, issues),
         "cells": cells_of(req.get("preset") or {})}
    if kind != "single":
        s["force"] = [int(m.get("cols") or 1), int(m.get("rows") or 1)]
    n = {"marker_id": int(m.get("first_id") or 0)}
    if not auto:
        n["size"] = float(m.get("marker_mm") or 0.0)
        if kind == "charuco":
            n["square"] = float(m.get("checker_mm") or 0.0)
    if kind == "grid" and float(m.get("separation_mm") or 0.0) > 0:
        n["separation"] = float(m["separation_mm"])
    face = bool(req.get("reference_face"))
    t = Target(kind="profile" if face else "free", w_mm=float(rect["w"]), h_mm=float(rect["h"]),
               has_body=face)
    return TagSpec(settings=s, numbers=n, target=t, name="", key="marker")


def field_of(f: str, text: str) -> str:
    if text.startswith("Over the page"):
        return "preset"                            # the page lint (core.make.lint_text)
    if f in FIELDS:
        return FIELDS[f]
    if f.startswith(PRESET_FIELDS):
        return "preset"
    if f.startswith("settings.label"):
        return "label"
    if f.startswith("target"):
        return "rect"
    return "tag"


def issues_of(plan_d: dict) -> list:
    out = []
    for w in plan_d["warnings"]:
        out.append({"field": field_of(w["field"], w["text"]), "level": w["level"], "text": w["text"]})
    return out


# ------------------------------------------------------------------ frames

def _cs(deg: float):
    """cos, sin of an angle: exact at the quarter turns."""
    q = (deg / 90.0) % 4.0
    if abs(q - round(q)) < 1e-12:
        return ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[int(round(q)) % 4]
    a = math.radians(deg)
    return math.cos(a), math.sin(a)


def _mul(A, B):
    return [sum(A[4 * i + k] * B[4 * k + j] for k in range(4)) for i in range(4) for j in range(4)]


def sketch_of_pattern(rect: dict, plan_d: dict, flip: bool):
    """The 4x4 (row-major, mm) taking the plan's pattern frame to the
    sketch: the rectangle's placement x the plan's pattern_in_target x Flip
    (half a turn about the pattern's x: y and z negated)."""
    c, s = _cs(float(rect.get("angle_deg") or 0.0))
    R = [c, -s, 0.0, float(rect["cx"]), s, c, 0.0, float(rect["cy"]),
         0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    M = _mul(R, plan_d["frames"]["pattern_in_target"])
    if flip:
        M = _mul(M, [1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0,
                     0.0, 0.0, 0.0, 1.0])
    return M


def _pt(M, u, v):
    return [_r(M[0] * u + M[1] * v + M[3]), _r(M[4] * u + M[5] * v + M[7])]


def _area2(lp) -> float:
    return sum(lp[i - 1][0] * lp[i][1] - lp[i][0] * lp[i - 1][1] for i in range(len(lp)))


def _loop(M, pts, ccw: bool):
    """A loop in the sketch, wound as the contract says (outer CCW, holes CW)."""
    lp = [_pt(M, u, v) for u, v in pts]
    if (_area2(lp) > 0) != ccw:
        lp.reverse()
    return lp


def _rect_loop(r):
    u0, v0, u1, v1 = r
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


# ------------------------------------------------------------------ the label

def label_text(template: str, kind: str, dictionary: str, ids: list) -> str:
    """The label's text with its placeholders: {id} {first} {last} {ids}
    ("0-5"; a single's "3") {dict} ("4X4_50") {type} ("ArUco", "Grid",
    "ChArUco"). An empty text is LABEL_TEMPLATE. "\\n" breaks lines."""
    ids = list(ids) or [0]
    first, last = ids[0], ids[-1]
    words = {"id": str(first), "first": str(first), "last": str(last),
             "ids": str(first) if first == last else f"{first}-{last}",
             "dict": _AL.dict_short(dictionary), "type": TYPE_WORDS.get(kind, kind)}
    t = template if (template or "").strip() else LABEL_TEMPLATE
    return re.sub(r"\{(\w+)\}", lambda mt: words.get(mt.group(1), mt.group(0)), t)


def label_height(lab: dict, w: float, h: float) -> float:
    hm = float(lab.get("height_mm") or 0.0)
    return hm if hm > 0 else _RF.auto_cap(w, h)


def text_width(text: str, cap_mm: float) -> float:
    """The label's width (mm) in Helvetica at a cap height (core.sheet's metrics)."""
    return _RF.sans_width(text, cap_mm)


def font_of(preset: dict) -> str:
    """How the label is drawn: ordinary text on an inkjet page ("sans"), the
    blocky pixel font a nozzle prints ("pixel", Zach 2026-10-18: "If 3D
    printing the label text should be very blocky")."""
    return "sans" if (preset or {}).get("method") == "inkjet" else "pixel"


def _line_mm(preset: dict) -> float:
    pr = preset or {}
    return float(pr.get("line_mm") or pr.get("nozzle_mm") or 0.0)


def label_fill(req: dict, kind: str, dictionary: str, ids: list):
    """The rectangle filled (core.rect_fill): the label's band, the box the
    marker fills; None when the label is off."""
    lab = req.get("label") or {}
    if not lab.get("on"):
        return None
    rect = req["rect"]
    pr = req.get("preset") or {}
    # WHY offset_mm in the rectangle's own frame (it was the sketch's while the
    # label sat outside): Zach's "you set the origin of the label" -- an offset
    # inside the sticker, so the label stays where it was when the rectangle turns
    return _RF.fill(float(rect["w"]), float(rect["h"]),
                    label_text(lab.get("text") or "", kind, dictionary, ids),
                    font=font_of(pr), cap_mm=float(lab.get("height_mm") or 0.0),
                    side=lab.get("side") or "below", gap_mm=float(lab.get("gap_mm") or 0.0),
                    offset=tuple(float(v) for v in (lab.get("offset_mm") or [0.0, 0.0])),
                    line_mm=_line_mm(pr))


def rect_matrix(rect: dict):
    """The rectangle's own frame (centre 0, unturned) -> the sketch, 4x4."""
    c, s = _cs(float(rect.get("angle_deg") or 0.0))
    return [c, -s, 0.0, float(rect["cx"]), s, c, 0.0, float(rect["cy"]),
            0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def line_centres(fl) -> list:
    """Each line's centre in the rectangle's own frame (its cap box's: the
    baseline at y - cap / 2), as the core stacks the lines: sans as
    rect_fill's runs, pixel as core.label.block_boxes (LINE_GAP_PX pixels
    between lines), every line centred on the block's x."""
    if fl.font != "pixel":
        return [t.at for t in fl.runs]
    top = fl.at[1] + fl.block[1] / 2.0
    pitch = fl.cap + _AL.LINE_GAP_PX * fl.stroke
    return [(fl.at[0], top - fl.cap / 2.0 - k * pitch) for k in range(len(fl.drawn))]


def placed_label(req: dict, kind: str, dictionary: str, ids: list, fl=None):
    """The contract's PlacedLabel: inside the rectangle, its text block's
    centre `at` (the band's centre + offset_mm, both in the rectangle's own
    frame), its band `box`, and the pixel font's ink as `polygons`."""
    fl = fl or label_fill(req, kind, dictionary, ids)
    if fl is None:
        return None
    rect = req["rect"]
    R = rect_matrix(rect)
    return {"text": "\n".join(fl.lines), "at": _pt(R, *fl.at), "height_mm": _r(fl.cap),
            "angle_deg": _r(float(rect.get("angle_deg") or 0.0)), "lines": list(fl.lines),
            "lines_at": [_pt(R, *c) for c in line_centres(fl)],
            "font": fl.font,
            "polygons": [{"outer": _loop(R, _rect_loop(r), True), "holes": []} for r in fl.ink],
            "box": _loop(R, _rect_loop(fl.band), True)}


# ------------------------------------------------------------------ the calls

def info() -> dict:
    try:
        import pyodide                            # noqa: F401 -- only inside Pyodide
        pyo = getattr(pyodide, "__version__", "")
    except ImportError:
        pyo = ""
    return {"core_version": core_version(), "python": platform.python_version(), "pyodide": pyo,
            "dictionaries": [{"name": d, "capacity": _D.dictionary_info(d)["capacity"],
                              "bits": _D.dictionary_info(d)["bits"]}
                             for d in _D.DICTIONARY_NAMES]}


def core_version() -> str:
    """aruco_studio's version, + the commit web/scripts/pack-core.mjs stamped
    into the zip (aruco_studio/_build.json) when there is one."""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_build.json")
    try:
        with open(path, encoding="utf-8") as f:
            b = json.load(f)
        return f"{__version__}+{b['git']}" if b.get("git") else __version__
    except (OSError, ValueError, KeyError, TypeError):
        return __version__


def presets() -> list:
    return [flat_preset(p) for p in _builtins()]


def _plain_rect(loops):
    """(x0, y0, x1, y1) when the profile is ONE loop that is its own
    axis-aligned bounding box (extra points along its edges allowed), else
    None. A simple loop inside its box has the box's area only when it is
    the box."""
    if len(loops) != 1:
        return None
    pts = [(float(u), float(v)) for u, v in loops[0]]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    box = (x1 - x0) * (y1 - y0)
    if not box > 0:
        return None
    on_edge = all(min(abs(u - x0), abs(u - x1)) <= SNAP_TOL_MM
                  or min(abs(v - y0), abs(v - y1)) <= SNAP_TOL_MM for u, v in pts)
    if not on_edge or abs(abs(_area2(pts)) / 2.0 - box) > 1e-9 * box:
        return None
    return x0, y0, x1, y1


def inscribe(profile: dict, holes: str = "avoid"):
    """The largest clear axis-aligned rectangle in a profile (mm), or None."""
    loops = [lp for lp in (profile or {}).get("loops") or [] if len(lp) >= 3]
    if holes == "ignore":
        loops = loops[:1]
    if not loops:
        return None
    box = _plain_rect(loops)
    if box is not None:
        # WHY exact (the Fusion adapter's N-6 report, 2026-10-18): a 50 x 80
        # face came back 50 x 79.9 -- the search is within CLEAR_EPS_M of the
        # optimum, and the inward snap then took a whole 0.1 mm. A profile
        # that is itself the rectangle, nothing in its way, is the answer.
        x0, y0, x1, y1 = box
        return {"cx": _r((x0 + x1) / 2.0), "cy": _r((y0 + y1) / 2.0),
                "w": _r(x1 - x0), "h": _r(y1 - y0), "angle_deg": 0.0}
    got = _A.largest_clear_rect([[(float(u) / 1000.0, float(v) / 1000.0) for u, v in lp]
                                 for lp in loops])
    if got is None:
        return None
    # WHY snap inward to 0.1 mm: the search returns sizes like 49.9646 mm, and
    # the rectangle becomes an ordinary sketch rectangle Zach reads and edits
    # (and a CAD sketch dimension). Moving each edge inward to the 0.1 mm grid
    # keeps it inside the profile and gives numbers a person would type. An
    # edge within SNAP_TOL_MM of a grid line is on it (not pushed one further in).
    cx, cy, w, h = (got[k] * 1000.0 for k in ("cx", "cy", "w", "h"))
    t = SNAP_TOL_MM * 10.0
    x0, x1 = math.ceil((cx - w / 2.0) * 10.0 - t) / 10.0, math.floor((cx + w / 2.0) * 10.0 + t) / 10.0
    y0, y1 = math.ceil((cy - h / 2.0) * 10.0 - t) / 10.0, math.floor((cy + h / 2.0) * 10.0 + t) / 10.0
    if x1 <= x0 or y1 <= y0:
        return None
    return {"cx": _r((x0 + x1) / 2.0), "cy": _r((y0 + y1) / 2.0),
            "w": _r(x1 - x0), "h": _r(y1 - y0), "angle_deg": _r(got["angle_deg"])}


def _ids_guess(m: dict) -> list:
    """The ids a request prints before it is planned (the label's text needs
    them to size its band): the counts are typed (`settings.force`)."""
    first = int(m.get("first_id") or 0)
    cols, rows = int(m.get("cols") or 1), int(m.get("rows") or 1)
    n = {"single": 1, "grid": cols * rows}.get(m.get("type"), (cols * rows) // 2)
    return list(range(first, first + max(1, n)))


def _planned(req: dict):
    """(the core's TagPlan dict, the request's issues, the rectangle's
    core.rect_fill.Fill or None) of a PlanRequest. With the label on the
    marker is planned in the box the label leaves (Fill.box), so Auto sizes
    it to that box; the core's words about "the W × H mm rectangle" then
    name that box."""
    issues = []
    lab = req.get("label") or {}
    if not lab.get("on"):
        return plan_tag(spec_of(req, issues)).data, issues, None
    m = req["marker"]
    ids = _ids_guess(m)
    for _k in range(2):                            # again only when the ids were guessed wrong
        fl = label_fill(req, m["type"], m["dictionary"], ids)
        bw, bh = (_r(v) for v in fl.box_size)
        issues = []
        d = plan_tag(spec_of(dict(req, rect=dict(req["rect"], w=bw, h=bh)), issues)).data
        if not d["ok"] or list(d["ids"]) == ids:
            break
        ids = list(d["ids"])

    def beside(mt):                                # the core's size of its target, any format
        a, b = float(mt.group(1)), float(mt.group(2))
        same = abs(a - bw) < 0.05 + 1e-9 and abs(b - bh) < 0.05 + 1e-9
        return f"{mt.group(1)} × {mt.group(2)} mm beside the label" if same else mt.group(0)
    for w in d["warnings"]:
        w["text"] = re.sub(r"\b(\d+(?:\.\d+)?) × (\d+(?:\.\d+)?) mm (?:rectangle|target|face)\b",
                           beside, w["text"])
    issues += [{"field": f, "level": lv, "text": t} for f, lv, t in fl.issues]
    return d, issues, fl


def _plan(req: dict):
    """(the core's TagPlan dict, the request's issues) of a PlanRequest."""
    d, issues, _fl = _planned(req)
    return d, issues


def _local(d: dict, fl, flip: bool):
    """The plan's pattern frame -> the rectangle's own frame (centre 0,
    unturned): the marker centred on the box the label leaves."""
    su, sv = fl.box_centre if fl is not None else (0.0, 0.0)
    return sketch_of_pattern({"cx": su, "cy": sv, "angle_deg": 0.0}, d, flip)


def _bbox(M, pts):
    q = [(M[0] * u + M[1] * v + M[3], M[4] * u + M[5] * v + M[7]) for u, v in pts]
    return (min(p[0] for p in q), min(p[1] for p in q), max(p[0] for p in q), max(p[1] for p in q))


def _square(r, side: float) -> bool:
    return abs(r[2] - r[0] - side) < 1e-6 and abs(r[3] - r[1] - side) < 1e-6


def origin_square(m: dict, d: dict, frame: list, issues: list) -> list:
    """`marker.origin_square` (ChArUco): OpenCV's board frame moved to that
    square's centre (core.rect_fill.square_origin); out of range = an error
    on its row and the corner kept."""
    sq = m.get("origin_square")
    if sq is None:
        return frame
    if d["layout"]["kind"] != "charuco":
        issues.append({"field": "marker.origin_square", "level": "info",
                       "text": "an origin in a square is for a ChArUco board: the origin stays"})
        return frame
    mk = d["marker"]
    cols, rows = int(mk["cols"]), int(mk["rows"])
    ok = (isinstance(sq, (list, tuple)) and len(sq) == 2
          and all(isinstance(v, int) and not isinstance(v, bool) for v in sq)
          and 0 <= sq[0] < cols and 0 <= sq[1] < rows)
    if not ok:
        issues.append({"field": "marker.origin_square", "level": "error",
                       "text": f"square {sq!r} is not on the {cols} × {rows} board (column 0..{cols - 1}, "
                               f"row 0..{rows - 1} from OpenCV's origin corner): the origin stays at "
                               "the corner"})
        return frame
    return _RF.square_origin(frame, sq[0], sq[1], mk["square_length_m"] * 1000.0)


def plan_dims(req: dict, d: dict, fl, L, lay: dict) -> list:
    """The contract's `dims` (core.rect_fill.dimensions), measured on the
    drawn geometry in the rectangle's frame (L: pattern -> that frame), placed
    in the sketch."""
    rect = req["rect"]
    w, h = float(rect["w"]), float(rect["h"])
    kind = lay["kind"]
    mk = d["marker"]
    boxes = [_bbox(L, poly[0]) for poly in _ME.top(d).get("black", [])]
    L_mm = mk["marker_length_m"] * 1000.0
    S_mm = mk.get("square_length_m", 0.0) * 1000.0 if kind == "charuco" else 0.0
    lab = req.get("label") or {}
    off = [float(v) for v in (lab.get("offset_mm") or [0.0, 0.0])]
    got = _RF.dimensions(
        w, h, _bbox(L, _rect_loop(d["guides"]["sticker"])),
        markers=[b for b in boxes if _square(b, L_mm)], marker_mm=_r(L_mm),
        squares=[b for b in boxes if _square(b, S_mm)] if kind == "charuco" else (),
        checker_mm=_r(lay["square_mm"]) if kind == "charuco" else 0.0,
        separation_mm=_r(lay["separation_mm"]) if kind == "grid" else 0.0,
        spot=fl.spot if fl is not None else None, at=fl.at if fl is not None else None,
        offset_mm=math.hypot(*off) if fl is not None else 0.0)
    R = rect_matrix(rect)
    # WHY 1e-9 for the endpoints (the plan's numbers are 1e-6): a dimension
    # reads |b - a|, and two points each rounded to 1e-6 on a turned
    # rectangle put that distance up to ~1.4e-6 off the value it shows
    pt = lambda u, v: [round(R[0] * u + R[1] * v + R[3], ND_DIM) + 0.0,
                       round(R[4] * u + R[5] * v + R[7], ND_DIM) + 0.0]
    return [{"field": g["field"], "value_mm": _r(g["value_mm"]), "a": pt(*g["a"]),
             "b": pt(*g["b"]), "offset_mm": _r(g["offset_mm"])} for g in got]


def cad_layers(d: dict, M) -> list:
    """The contract's `layers`: the TagPlan's layers (plan/layers.py: REF's
    bodies in build order) placed in the sketch by M -- polygons as `black`,
    z along the sketch normal (Flip turns the marker over: [lo, hi] becomes
    [-hi, -lo]). The web's settings (mode auto, corner mark none / triangle)
    only build "add" steps; a "sub" step (a cut tool inside its part:
    white mode, black_cut marks) has no place in the contract's shape and
    is not sent."""
    out = []
    for L in d["layers"]:
        if L["step"] != "add":
            continue
        z = sorted(_r(M[10] * v + M[11]) for v in L["z"])
        out.append({"name": L["name"], "part": L["part"], "colour": L["colour"], "op": L["op"],
                    "z": z,
                    "polygons": [{"outer": _loop(M, p["outer"], True),
                                  "holes": [_loop(M, hl, False) for hl in p.get("holes", [])]}
                                 for p in L["polygons"]]})
    return out


def pattern_cells(d: dict) -> list:
    """The contract's `cells`: the black as disjoint axis-aligned boxes
    [u0, v0, u1, v1] (mm) in the PATTERN frame -- core.markers.cell_boxes,
    the boxes plan/layers.py extrudes for the cells (a board's squares and
    markers: core.board.black_rects_m). The corner triangle is not a box:
    it is its own layer ("mark_triangle")."""
    spec = _M.TagSpec.from_dict(d["marker"], lambda _t: None, "plan")
    if spec is None:
        return []
    return [[_r(x0 * 1000.0), _r(y0 * 1000.0), _r(x1 * 1000.0), _r(y1 * 1000.0)]
            for x0, y0, x1, y1 in _M.cell_boxes(spec)]


def _summary(kind, dictionary, ids, lay, outer_mm) -> str:
    idw = "#%d" % ids[0] if len(ids) == 1 else "#%d–%d" % (ids[0], ids[-1])
    head = "Single" if kind == "single" else f"{TYPE_WORDS[kind]} {lay['cols']}×{lay['rows']}"
    size = (f"{_mm(lay['square_mm'])} / {_mm(lay['marker_mm'])} mm" if kind == "charuco"
            else f"{_mm(lay['marker_mm'])} mm")
    return (f"{head} {dictionary} {idw} · {size} · outer {outer_mm[0]:.1f} × "
            f"{outer_mm[1]:.1f} mm")


def plan(req: dict) -> dict:
    d, issues, fl = _planned(req)
    m = req["marker"]
    face = bool(req.get("reference_face"))
    flip = bool(m.get("flip")) and not face
    if m.get("flip") and face:
        issues.append({"field": "marker.flip", "level": "info",
                       "text": "the reference face sets Z: Flip does not apply"})
    issues += issues_of(d)
    if not d["ok"]:
        return {"ok": False, "ids": [], "black": [], "outer": [], "outer_mm": [0.0, 0.0],
                "marker_mm": 0.0, "checker_mm": 0.0, "separation_mm": 0.0,
                "cols": int(m.get("cols") or 1), "rows": int(m.get("rows") or 1),
                "cell_mm": 0.0, "auto": bool(m.get("auto")), "overflow_mm": 0.0,
                "origin": [], "label": None,
                "summary": "; ".join(d["errors"]) or "nothing fits", "warnings": issues}
    kind = d["layout"]["kind"]
    lay = d["layout"]
    mk = d["marker"]
    L = _local(d, fl, flip)
    # WHY two ways: with the label off the matrix is exactly today's, so
    # those plans keep every number byte for byte (only cut and dims are new)
    M = sketch_of_pattern(req["rect"], d, flip) if fl is None else _mul(rect_matrix(req["rect"]), L)
    black = []
    for poly in _ME.top(d).get("black", []):
        black.append({"outer": _loop(M, poly[0], True), "holes": [_loop(M, hl, False)
                                                                  for hl in poly[1:]]})
    sticker = d["guides"]["sticker"]
    outer_mm = [_r(sticker[2] - sticker[0]), _r(sticker[3] - sticker[1])]
    modules = _D.dictionary_info(mk["dictionary"])["modules"]
    marker_mm = mk["marker_length_m"] * 1000.0
    origin = [_r(v) for v in _mul(M, origin_square(m, d, d["frames"]["opencv"], issues))]
    ids = list(d["ids"])
    rect = req["rect"]
    w, h = float(rect["w"]), float(rect["h"])
    overflow = _r(max(d.get("overflow_mm") or [0.0]))
    if fl is not None:                             # measured against the rectangle, not the box
        u0, v0, u1, v1 = _bbox(L, _rect_loop(sticker))
        overflow = _r(max(0.0, u1 - w / 2.0, -w / 2.0 - u0, v1 - h / 2.0, -h / 2.0 - v0))
    return {"ok": True, "ids": ids, "black": black, "outer": _loop(M, _rect_loop(sticker), True),
            "cut": _loop(rect_matrix(rect), _rect_loop((-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)), True),
            "outer_mm": outer_mm, "marker_mm": _r(marker_mm),
            "checker_mm": _r(lay["square_mm"]) if kind == "charuco" else 0.0,
            "separation_mm": _r(lay["separation_mm"]) if kind == "grid" else 0.0,
            "cols": int(lay["cols"]), "rows": int(lay["rows"]), "cell_mm": _r(marker_mm / modules),
            "auto": bool(m.get("auto")), "overflow_mm": overflow,
            "origin": origin, "label": placed_label(req, kind, mk["dictionary"], ids, fl),
            "dims": plan_dims(req, d, fl, L, lay),
            "layers": cad_layers(d, M), "cells": pattern_cells(d),
            "pattern_to_sketch": [_r(v) for v in M], "origin_z_mm": origin[11],
            "summary": _summary(kind, mk["dictionary"], ids, lay, outer_mm),
            "warnings": issues}


def _cell_reason(lay, cells: dict, method: str):
    """"cells = 4 lines of 0.675 mm" when the cells are a whole number of the
    preset's step, else None."""
    c = _A.cells_of(cells)
    if c is None or c[0] != "cell" or lay.marker_m <= 0:
        return None
    k = int(round(lay.module_m / c[1]))
    unit = "dots" if method == "inkjet" else "lines"
    return f"cells = {k} {unit if k != 1 else unit[:-1]} of {c[1] * 1000.0:g} mm"


def suggest(req: dict) -> list:
    """Good value sets for the rectangle (autosize.candidates: every count at
    its largest size), each with why: its badges and its cells."""
    issues = []
    spec = spec_of(req, issues)
    s, n = spec.settings, spec.numbers
    kind = s["layout"]
    rect = req["rect"]
    sep = float(n.get("separation") or 0.0)
    got = _A.candidates(kind, float(rect["w"]) / 1000.0, float(rect["h"]) / 1000.0,
                        dictionary=s["dictionary"], quiet_modules=s["quiet_modules"],
                        cells=s["cells"], separation_m=sep / 1000.0 if sep else None)
    method = (req.get("preset") or {}).get("method", "print3d")
    out = []
    for lay in got:
        L, S = lay.marker_m * 1000.0, lay.square_m * 1000.0
        if kind == "single":
            label = f"{_mm(L)} mm"
        elif kind == "charuco":
            label = f"{lay.cols}×{lay.rows} @ {_mm(S)} / {_mm(L)} mm"
        else:
            label = f"{lay.cols}×{lay.rows} @ {_mm(L)} mm"
        why = list(lay.badges) or [f"fill {lay.fill * 100.0:.0f} %"]
        cr = _cell_reason(lay, s["cells"], method)
        if cr:
            why.append(cr)
        out.append({"label": label, "reason": ", ".join(why),
                    "params": {"cols": int(lay.cols), "rows": int(lay.rows), "marker_mm": _r(L),
                               "checker_mm": _r(S) if kind == "charuco" else 0.0,
                               "separation_mm": _r(sep) if kind == "grid" else 0.0}})
    return out


def sticker_parts(req: dict, planned=None):
    """The sticker as the page prints it, in the rectangle's own frame (mm,
    y up, its centre 0, unturned; the marker's turn as the sketch has it,
    never Flip): {"w_mm", "h_mm", "cut": the rectangle {"outer", "holes"},
    "ink": the marker's black [[outer, hole, ...], ...], "label_ink": the
    pixel label's, "texts": the sans label's lines [{"text", "at" (its cap
    box's centre; baseline at - cap / 2), "cap_mm"}], "font"}, or None when
    the plan is refused. core.sheet's PrintItem takes cut / ink as cut_mm /
    ink_mm (the sticker frame is any frame they share). `planned`: _planned(req)
    when the caller has it."""
    d, _issues, fl = planned or _planned(req)
    if not d["ok"]:
        return None
    w, h = float(req["rect"]["w"]), float(req["rect"]["h"])
    L = _local(d, fl, False)
    one = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    ink = [[_loop(L, poly[0], True)] + [_loop(L, hl, False) for hl in poly[1:]]
           for poly in _ME.top(d).get("black", [])]
    return {"w_mm": _r(w), "h_mm": _r(h),
            "cut": {"outer": _loop(one, _rect_loop((-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)), True),
                    "holes": []},
            "ink": ink,
            "label_ink": [[_loop(one, _rect_loop(r), True)] for r in (fl.ink if fl else [])],
            "texts": [{"text": t.text, "at": [_r(t.at[0]), _r(t.at[1])], "cap_mm": _r(t.cap)}
                      for t in (fl.runs if fl else [])],
            "font": fl.font if fl else None}


def svg(req: dict) -> str:
    """One marker at true size (mm units). Label off: the marker in its own
    frame (plan.exports.to_svg). Label on: the whole sticker, the rectangle,
    with the label inside it (sticker_parts; the sketch's label is
    plan().label)."""
    got = _planned(req)
    d = got[0]
    if not d["ok"]:
        raise ValueError("nothing to draw: " + "; ".join(d["errors"]))
    if got[2] is None:
        return _X.to_svg(d)
    sp = sticker_parts(req, got)
    w, h = sp["w_mm"], sp["h_mm"]
    f = _f
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}mm" height="{f(h)}mm" '
           f'viewBox="{f(-w / 2.0)} {f(-h / 2.0)} {f(w)} {f(h)}">',
           f'<title>{d["marker"]["dictionary"]} #{d["ids"][0]}</title>',
           f'<rect x="{f(-w / 2.0)}" y="{f(-h / 2.0)}" width="{f(w)}" height="{f(h)}" fill="#ffffff"/>',
           f'<path data-layer="black" fill="#000000" fill-rule="evenodd" d="{_X.path_d(sp["ink"])}"/>']
    if sp["label_ink"]:
        out.append(f'<path data-label="1" fill="#000000" fill-rule="evenodd" '
                   f'd="{_X.path_d(sp["label_ink"])}"/>')
    for t in sp["texts"]:
        out.append(f'<text data-label="1" x="{f(t["at"][0])}" y="{f(-(t["at"][1] - t["cap_mm"] / 2.0))}" '
                   f'font-family="Helvetica, Arial, sans-serif" font-size="{f(t["cap_mm"] / CAP_EM)}" '
                   f'text-anchor="middle" fill="#000000">{_xml(t["text"])}</text>')
    return "".join(out) + "</svg>"


def _xml(t: str) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


_PAGE = re.compile(r'<g data-page="(\d+)" transform="translate\(0 [^)]*\)">(.*?)</g>', re.S)


def sheet(req: dict, date=None) -> dict:
    """Every item on the first item's preset's page (core.sheet's sticker
    sheet: true size, cut lines, the scale bars), each captioned with its
    label's text. -> {"pages", "svg": [one SVG per page, mm], "pdf_base64",
    "warnings", "cuts", "fill"}. `date`: the footer's (ISO); today's by
    default.

    Auto layout (Zach, 2026-10-18): core.pack's guillotine packer
    (SheetSettings.packer "guillotine"), stickers turned 90 degrees when that
    packs better. `mode` "tight" packs edge to edge (shared cut lines, no
    captions), "spaced" (default) keeps `gap_mm` (default the core's
    SheetSettings.gap_mm) round every sticker and its caption. `cuts`: the
    straight cuts that free every sticker on all pages; `fill`: sticker area
    / printable area over all pages. `objective` (core.pack): "fewest_sheets"
    (default: the fewest pages, then the fewest cuts) or "fewest_cuts" (the
    fewest cuts, then the fewest pages). `placements`: where each printed
    request item landed (its index, page, box from the page's top-left in
    mm, y down, and its turn), in item order. The PDF asks the viewer to
    print at 100 % (core.sheet.render_sticker_pdf print_scaling)."""
    def is_box(cut) -> bool:
        # a sticker's cut outline is its own bounding box (no holes)
        pts = (cut or {}).get("outer") or []
        if not cut or not pts:
            return True
        xs = {round(float(q[0]), ND) for q in pts}
        ys = {round(float(q[1]), ND) for q in pts}
        return not cut.get("holes") and len(pts) == 4 and len(xs) == 2 and len(ys) == 2

    items, warnings = [], []
    index = {}                                     # a PrintItem's key -> its request item
    first = None
    for i, it in enumerate(req.get("items") or []):
        d, issues = _plan(it)
        warnings += issues
        if not d["ok"]:
            warnings.append({"field": "tag", "level": "error",
                             "text": f"item {i + 1} is not printed: " + "; ".join(d["errors"])})
            continue
        first = first or it
        lab = placed_label(it, d["layout"]["kind"], d["marker"]["dictionary"], d["ids"])
        p = _SS.sticker_item(SimpleNamespace(name=""), d)
        ids = d["ids"]
        idw = f"#{ids[0]}" if len(ids) == 1 else f"#{ids[0]}-{ids[-1]}"
        cap = (lab["text"] if lab else
               f"{idw} · {_AL.dict_short(d['marker']['dictionary'])} · "
               f"{_mm(d['marker']['marker_length_m'] * 1000.0)} mm")
        p.key, p.caption = f"m{i + 1}", cap
        index[p.key] = i
        if lab:
            # WYSIWYG (Zach, 2026-10-18): the sticker is the whole marker
            # rectangle, with the label inside it as the sketch has it
            sp = sticker_parts(it)
            p.cut_mm = sp["cut"]
            p.ink_mm = sp["ink"] + sp["label_ink"]
            p.texts_mm = sp["texts"]
        items.append(p)
        if not is_box(p.cut_mm):
            warnings.append({"field": "tag", "level": "info",
                             "text": f"item {i + 1} is packed by its bounding box: its outline "
                                     "is not a rectangle"})
    pr = (first or {}).get("preset") or {}
    page = _page_key(pr, []) if pr.get("method") == "inkjet" else "letter"
    margin = float(pr["margin_mm"]) if pr.get("margin_mm") is not None else _MK.PAGE_MARGIN_MM
    mode = req.get("mode") or "spaced"
    gap = req.get("gap_mm")
    gap = _SH.SheetSettings.gap_mm if gap is None else float(gap)
    st = _SH.SheetSettings(page=page, landscape=False, mode=mode, gap_mm=gap, margin_mm=margin,
                           title="ArUco Studio", cut_marks=bool(req.get("cut_lines", True)),
                           packer="guillotine",
                           objective=req.get("objective") or "fewest_sheets")
    lay = _SH.layout_stickers(items, st)
    date = date or datetime.date.today().isoformat()
    whole = _SH.render_sticker_svg(lay, date=date)
    pw, ph = (_f(v) for v in lay.page_mm)
    pages = []
    for _k, inner in _PAGE.findall(whole):
        pages.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}mm" height="{ph}mm" '
                     f'viewBox="0 0 {pw} {ph}">{inner}</svg>')
    for r in lay.rejected:
        warnings.append({"field": "preset", "level": "error",
                         "text": f"{r.item.caption or r.item.key} is not printed: {r.reason}"})
    for t in lay.warnings:
        warnings.append({"field": "preset", "level": "warn", "text": t})
    pdf = _SH.render_sticker_pdf(lay, date=date, print_scaling=True)
    placements = sorted(({"item": index[p.item.key], "page": p.page, "x_mm": _r(p.x_mm),
                          "y_mm": _r(p.y_mm), "w_mm": _r(p.w_mm), "h_mm": _r(p.h_mm),
                          "rotation": int(p.rotation)} for p in lay.placed),
                        key=lambda q: q["item"])
    return {"pages": lay.page_count, "svg": pages,
            "pdf_base64": base64.b64encode(pdf).decode("ascii"), "warnings": warnings,
            "cuts": lay.cuts(), "fill": _r(lay.fill()), "placements": placements}



def call(name: str, payload_json: str) -> str:
    """The worker's one entry: `name` a CoreApi call, `payload_json` its
    arguments as JSON ({} for info / presets; {"profile", "holes"} for
    inscribe; the request for plan / suggest / svg / sheet, sheet's may add
    "date"). -> JSON, sorted keys; never raises: {"error": "..."}."""
    try:
        if name not in API:
            raise ValueError(f"unknown call {name!r}: one of {', '.join(API)}")
        p = json.loads(payload_json or "{}")
        if name == "info":
            out = info()
        elif name == "presets":
            out = presets()
        elif name == "inscribe":
            out = inscribe(p.get("profile") or {}, p.get("holes") or "avoid")
        elif name == "sheet":
            out = sheet(p, p.get("date"))
        elif name in ("verify", "readable"):
            from . import web_verify               # numpy + OpenCV: imported on first use only
            out = (web_verify.verify(p["req"], p["view"]) if name == "verify"
                   else web_verify.readable(p["req"], p["camera"]))
        elif name == "assign_ids":
            from . import web_ids
            out = web_ids.assign_ids(p)
        else:
            out = {"plan": plan, "suggest": suggest, "svg": svg}[name](p)
        return json.dumps({"result": out}, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    except Exception as exc:                       # noqa: BLE001 -- the worker gets words
        return json.dumps({"error": f"{type(exc).__name__}: {exc}"[:2000]}, sort_keys=True)
