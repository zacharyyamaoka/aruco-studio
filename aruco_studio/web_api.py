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
from .core import presets as _P
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
LABEL_CAP = (0.12, 2.5, 12.0)       # height 0: 0.12 x the short side, within 2.5 .. 12 mm
CAP_EM = _SH.CAP_EM                 # Helvetica's cap height / em (core.sheet prints the label with it)
ND = 6                              # JSON numbers: 1e-6 mm


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
    "ChArUco"). An empty text is LABEL_TEMPLATE."""
    ids = list(ids) or [0]
    first, last = ids[0], ids[-1]
    words = {"id": str(first), "first": str(first), "last": str(last),
             "ids": str(first) if first == last else f"{first}-{last}",
             "dict": _AL.dict_short(dictionary), "type": TYPE_WORDS.get(kind, kind)}
    t = template if (template or "").strip() else LABEL_TEMPLATE
    return re.sub(r"\{(\w+)\}", lambda mt: words.get(mt.group(1), mt.group(0)), t)


def label_height(lab: dict, w: float, h: float) -> float:
    hm = float(lab.get("height_mm") or 0.0)
    if hm > 0:
        return hm
    k, lo, hi = LABEL_CAP
    return min(hi, max(lo, k * min(w, h)))


def text_width(text: str, cap_mm: float) -> float:
    """The label's width (mm) in Helvetica at a cap height (core.sheet's metrics)."""
    font_pt = cap_mm / CAP_EM * _SH.MM_TO_PT
    return _SH.text_width_mm(text, font_pt)


def label_spot(side: str, gap: float, cap: float, width: float, w: float, h: float):
    """The text's centre beside a w x h box centred at 0 (its own frame): the
    middle of `side`, `gap` out from the edge to the text."""
    if side == "above":
        return 0.0, h / 2.0 + gap + cap / 2.0
    if side == "left":
        return -(w / 2.0 + gap + width / 2.0), 0.0
    if side == "right":
        return w / 2.0 + gap + width / 2.0, 0.0
    return 0.0, -(h / 2.0 + gap + cap / 2.0)


def placed_label(req: dict, kind: str, dictionary: str, ids: list):
    lab = req.get("label") or {}
    if not lab.get("on"):
        return None
    rect = req["rect"]
    w, h = float(rect["w"]), float(rect["h"])
    text = label_text(lab.get("text") or "", kind, dictionary, ids)
    cap = label_height(lab, w, h)
    u, v = label_spot(lab.get("side") or "below", float(lab.get("gap_mm") or 0.0), cap,
                      text_width(text, cap), w, h)
    c, s = _cs(float(rect.get("angle_deg") or 0.0))
    off = lab.get("offset_mm") or [0.0, 0.0]
    at = [_r(rect["cx"] + c * u - s * v + float(off[0])),
          _r(rect["cy"] + s * u + c * v + float(off[1]))]
    return {"text": text, "at": at, "height_mm": _r(cap),
            "angle_deg": _r(float(rect.get("angle_deg") or 0.0))}


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


def inscribe(profile: dict, holes: str = "avoid"):
    """The largest clear axis-aligned rectangle in a profile (mm), or None."""
    loops = [lp for lp in (profile or {}).get("loops") or [] if len(lp) >= 3]
    if holes == "ignore":
        loops = loops[:1]
    if not loops:
        return None
    got = _A.largest_clear_rect([[(float(u) / 1000.0, float(v) / 1000.0) for u, v in lp]
                                 for lp in loops])
    if got is None:
        return None
    return {"cx": _r(got["cx"] * 1000.0), "cy": _r(got["cy"] * 1000.0),
            "w": _r(got["w"] * 1000.0), "h": _r(got["h"] * 1000.0),
            "angle_deg": _r(got["angle_deg"])}


def _plan(req: dict):
    """(the core's TagPlan dict, the request's issues) of a PlanRequest."""
    issues = []
    spec = spec_of(req, issues)
    return plan_tag(spec).data, issues


def _summary(kind, dictionary, ids, lay, outer_mm) -> str:
    idw = "#%d" % ids[0] if len(ids) == 1 else "#%d–%d" % (ids[0], ids[-1])
    head = "Single" if kind == "single" else f"{TYPE_WORDS[kind]} {lay['cols']}×{lay['rows']}"
    size = (f"{_mm(lay['square_mm'])} / {_mm(lay['marker_mm'])} mm" if kind == "charuco"
            else f"{_mm(lay['marker_mm'])} mm")
    return (f"{head} {dictionary} {idw} · {size} · outer {outer_mm[0]:.1f} × "
            f"{outer_mm[1]:.1f} mm")


def plan(req: dict) -> dict:
    d, issues = _plan(req)
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
    M = sketch_of_pattern(req["rect"], d, flip)
    black = []
    for poly in _ME.top(d).get("black", []):
        black.append({"outer": _loop(M, poly[0], True), "holes": [_loop(M, hl, False)
                                                                  for hl in poly[1:]]})
    sticker = d["guides"]["sticker"]
    outer_mm = [_r(sticker[2] - sticker[0]), _r(sticker[3] - sticker[1])]
    modules = _D.dictionary_info(mk["dictionary"])["modules"]
    marker_mm = mk["marker_length_m"] * 1000.0
    origin = [_r(v) for v in _mul(M, d["frames"]["opencv"])]
    ids = list(d["ids"])
    return {"ok": True, "ids": ids, "black": black, "outer": _loop(M, _rect_loop(sticker), True),
            "outer_mm": outer_mm, "marker_mm": _r(marker_mm),
            "checker_mm": _r(lay["square_mm"]) if kind == "charuco" else 0.0,
            "separation_mm": _r(lay["separation_mm"]) if kind == "grid" else 0.0,
            "cols": int(lay["cols"]), "rows": int(lay["rows"]), "cell_mm": _r(marker_mm / modules),
            "auto": bool(m.get("auto")), "overflow_mm": _r(max(d.get("overflow_mm") or [0.0])),
            "origin": origin, "label": placed_label(req, kind, mk["dictionary"], ids),
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


def svg(req: dict) -> str:
    """One marker at true size (mm units) in its own frame, the label beside
    its outline on the label's side (the print; the sketch's label is
    plan().label)."""
    d, _issues = _plan(req)
    if not d["ok"]:
        raise ValueError("nothing to draw: " + "; ".join(d["errors"]))
    body = _X.to_svg(d)
    lab = placed_label(req, d["layout"]["kind"], d["marker"]["dictionary"], d["ids"])
    if lab is None:
        return body
    u0, v0, u1, v1 = _X.view_rect(d)
    lb = req["label"]
    cap = lab["height_mm"]
    wd = text_width(lab["text"], cap)
    cu, cv = label_spot(lb.get("side") or "below", float(lb.get("gap_mm") or 0.0), cap, wd,
                        u1 - u0, v1 - v0)
    cu, cv = cu + (u0 + u1) / 2.0, cv + (v0 + v1) / 2.0
    x0, x1 = min(u0, cu - wd / 2.0), max(u1, cu + wd / 2.0)
    y0, y1 = min(v0, cv - cap / 2.0), max(v1, cv + cap / 2.0)
    font_mm = cap / CAP_EM
    f = _f
    text = (f'<text data-label="1" x="{f(cu)}" y="{f(-(cv - cap / 2.0))}" '
            f'font-family="Helvetica, Arial, sans-serif" font-size="{f(font_mm)}" '
            f'text-anchor="middle" fill="#000000">{_xml(lab["text"])}</text>')
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(x1 - x0)}mm" '
            f'height="{f(y1 - y0)}mm" viewBox="{f(x0)} {f(-y1)} {f(x1 - x0)} {f(y1 - y0)}">')
    inner = body[body.index(">") + 1:body.rindex("</svg>")]
    bg = (f'<rect x="{f(x0)}" y="{f(-y1)}" width="{f(x1 - x0)}" height="{f(y1 - y0)}" '
          'fill="#ffffff"/>')
    return head + bg + inner + text + "</svg>"


def _xml(t: str) -> str:
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


_PAGE = re.compile(r'<g data-page="(\d+)" transform="translate\(0 [^)]*\)">(.*?)</g>', re.S)


def sheet(req: dict, date=None) -> dict:
    """Every item on the first item's preset's page (core.sheet's sticker
    sheet: true size, cut lines, the scale bars), each captioned with its
    label's text. -> {"pages", "svg": [one SVG per page, mm], "pdf_base64",
    "warnings"}. `date`: the footer's (ISO); today's by default."""
    items, warnings = [], []
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
        if lab:                                    # WYSIWYG: the sketch label's size and gap
            p.caption_cap_mm = lab["height_mm"]
            p.caption_gap_mm = float((it.get("label") or {}).get("gap_mm") or 0.0)
        items.append(p)
    pr = (first or {}).get("preset") or {}
    page = _page_key(pr, []) if pr.get("method") == "inkjet" else "letter"
    margin = float(pr["margin_mm"]) if pr.get("margin_mm") is not None else _MK.PAGE_MARGIN_MM
    st = _SH.SheetSettings(page=page, landscape=False, mode="spaced", margin_mm=margin,
                           title="ArUco Studio", cut_marks=bool(req.get("cut_lines", True)))
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
    pdf = _SH.render_sticker_pdf(lay, date=date)
    return {"pages": lay.page_count, "svg": pages,
            "pdf_base64": base64.b64encode(pdf).decode("ascii"), "warnings": warnings}


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
