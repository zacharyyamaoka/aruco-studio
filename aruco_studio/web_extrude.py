"""ArUco Extrude's heights for the online Studio's facade (contract barrier 10,
Zach 2026-10-20 night: "for inkjet you just get to set paper thickness (but
its autofilled from the preset). For 3D printer you get to set the white
height and black height. Black height is always measured from the outer face
of the white"). web_api imports it: standard library only, the same in
Pyodide and CPython.

| `PlanRequest.extrude` | core |
|---|---|
| `mode` unset / "auto" (driven) | `settings.mode` "auto" (core.form.resolve_mode: Black only on a reference face, White + black in open space) |
| `mode` "both" / "black" / "white" | `settings.mode` as given |
| `white_mm` W, White + black | `numbers.white_offset` 0, `white_height` W: the tile [0, W] |
| `black_mm` B, White + black | `numbers.black_offset` W, `black_height` -B: [W - B, W], flush from the white's outer face |
| `black_mm` B, Black only | `black_offset` 0, `black_height` -B: [-B, 0], from the face into the body |
| `white_mm` W, White only | `white_offset` 0, `white_height` -W: the white pattern [-W, 0], from the face into the body (core.slabs: Black only's mirror) |
| `paper_mm` (inkjet) | `settings.make`'s stock (core.make.new_make's `stock_mm`) |
| a height left unset | core.presets.driven_heights (rule HEIGHTS_RULE); White only's pattern is driven as the black is (core.slabs.PATTERN_HEIGHT: both are an inlay) |
| `paper_mm` left unset | `preset.thickness_mm` (core.make.VINYL_MM when it has none) |

A set value is used exactly, 0 and negative too (never clamped here); what
will print badly is said on "extrude.<field>". The core itself refuses a
colour with no height (core.slabs.layers, plan.spec.check) and keeps the
paper in core.make.THICKNESS_MM (its warn is said on "extrude.paper_mm").
"""
from __future__ import annotations

import math

from .core import make as _MK
from .core import presets as _P

MODES = ("auto", "both", "black", "white")
KEYS = ("mode", "white_mm", "black_mm", "paper_mm")
HEIGHT_KEYS = ("white_mm", "black_mm")
ND = 6


def _r(v) -> float:
    return round(float(v), ND) + 0.0


def _num(v):
    """A finite number as a float, else None (a bool is not a number)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def method_of(req: dict) -> str:
    return "inkjet" if (req.get("preset") or {}).get("method") == "inkjet" else "print3d"


def asked(req: dict, issues=None) -> dict:
    """The request's `extrude` ({} when absent); anything not an object is
    read as {} (said)."""
    ex = req.get("extrude")
    if ex is None:
        return {}
    if not isinstance(ex, dict):
        if issues is not None:
            issues.append({"field": "extrude", "level": "warn",
                           "text": f"extrude {ex!r} is not an object: every height is driven"})
        return {}
    return ex


def driven_paper(preset: dict) -> float:
    """The inkjet paper the preset drives (web_api.make_of's stock before
    barrier 10, unchanged): its thickness_mm, else core.make.VINYL_MM."""
    return float((preset or {}).get("thickness_mm") or _MK.VINYL_MM)


def heights(req: dict, issues=None) -> dict:
    """The heights a request is planned with: {"method", "mode" (resolved:
    "both" | "black" | "white"; "both" for inkjet), "auto" (the mode was
    driven), "white_mm", "black_mm", "paper_mm", "set" (the fields given),
    "driven" (the contract's: the fields left unset, in KEYS order),
    "rule" (core.presets.driven_heights')}. Appends to `issues` what a set
    value will print badly as (a 3D print), and the fields the method does
    not use (info)."""
    say = issues.append if issues is not None else (lambda _i: None)
    ex = asked(req, issues)
    pr = req.get("preset") or {}
    method = method_of(req)
    face = bool(req.get("reference_face"))
    rule = _P.driven_heights(pr.get("layer_mm"), pr.get("first_layer_mm"))
    got = {}
    for k in HEIGHT_KEYS + ("paper_mm",):
        if ex.get(k) is None:
            continue
        v = _num(ex[k])
        if v is None:
            say({"field": f"extrude.{k}", "level": "warn",
                 "text": f"{k} {ex[k]!r} is not a number: driven"})
            continue
        got[k] = v
    m = ex.get("mode")
    if m is not None and m not in MODES:
        say({"field": "extrude.mode", "level": "warn",
             "text": f"mode {m!r} is not one of {', '.join(MODES)}: auto"})
        m = None
    auto = m in (None, "auto")
    mode = ("black" if face else "both") if auto else m
    if method == "inkjet":
        mode = "both"                              # the paper and the ink (core.make.twin_settings)
    # WHY White only's white is driven as the black (not the 1.8 mm tile):
    # it is the pattern inlaid from the face, core.slabs' PATTERN_HEIGHT for
    # Black only and White only alike
    white = got.get("white_mm", rule["black_mm"] if mode == "white" else rule["white_mm"])
    black = got.get("black_mm", rule["black_mm"])
    paper = got.get("paper_mm", driven_paper(pr) if method == "inkjet"
                    else _num(pr.get("thickness_mm")) or 0.0)    # a 3D printer has no paper
    out = {"method": method, "mode": mode, "auto": auto, "white_mm": white, "black_mm": black,
           "paper_mm": paper, "set": sorted(got) + ([] if auto else ["mode"]), "rule": rule}
    out["driven"] = [k for k in KEYS if k not in out["set"]]
    if issues is not None:
        issues += lint(out, ex, pr)
    return out


def numbers(h: dict) -> dict:
    """The core's `numbers` of a 3D print's heights (the module's table)."""
    W, B = h["white_mm"], h["black_mm"]
    if h["mode"] == "both":
        return {"white_offset": 0.0, "white_height": W, "black_offset": W, "black_height": -B}
    if h["mode"] == "black":
        return {"black_offset": 0.0, "black_height": -B}
    return {"white_offset": 0.0, "white_height": -W}


def _mm(v: float) -> str:
    return f"{v:.2f} mm"


def lint(h: dict, ex: dict, preset: dict) -> list:
    """What the SET heights will print badly as, one issue per thing, on its
    field: never a change to them. A driven height is whole layers and at
    least the rule's minimum, so it is never said."""
    out = []
    add = lambda k, lv, t: out.append({"field": f"extrude.{k}", "level": lv, "text": t})
    s = set(h["set"])
    if h["method"] == "inkjet":
        for k in ("mode",) + HEIGHT_KEYS:
            if ex.get(k) is not None:
                add(k, "info", f"{k} is a 3D print's: an inkjet sticker is its paper (paper_mm)")
        return out
    if "paper_mm" in s:
        add("paper_mm", "info", "paper_mm is an inkjet sticker's: a 3D print has no paper")
    mode, W, B = h["mode"], h["white_mm"], h["black_mm"]
    lay, first = float(preset.get("layer_mm") or 0.0), float(preset.get("first_layer_mm") or 0.0)
    # the colours made, each with its field, its word and the depth it needs
    made = {"both": (("white_mm", "white", W, _P.WHITE_PRINT_MM),
                     ("black_mm", "black", B, _P.BLACK_PRINT_MM)),
            "black": (("black_mm", "black", B, _P.BLACK_PRINT_MM),),
            "white": (("white_mm", "white", W, _P.BLACK_PRINT_MM),)}[mode]
    for k, what, v, least in made:
        if k not in s:
            continue
        if v == 0:
            continue                               # the core refuses it, on this field (web_api.FIELDS)
        if v < 0:
            where = ("below the face (z 0): the tile is on the other side"
                     if (mode, k) == ("both", "white_mm") else
                     "proud of the white's outer face, not flush" if mode == "both" else
                     "out of the face, not flush")
            add(k, "warn", f"{what} {_mm(v)} is negative: it extrudes {_mm(-v)} {where}")
            continue
        if v < least - 1e-9:
            why = ("a thin tile is weak and lets the black show through"
                   if (mode, k) == ("both", "white_mm") else "the colour under it shows through")
            add(k, "warn", f"{what} {_mm(v)} is under the {least:g} mm the preset drives: {why}")
        note = _P.layer_note(v, lay, first, what)
        if note:
            add(k, "info", note)
    if mode == "both" and B > W + 1e-9 and W >= 0 and ({"white_mm", "black_mm"} & s):
        k = "black_mm" if "black_mm" in s else "white_mm"
        add(k, "warn", f"the black ({_mm(B)}) is deeper than the white ({_mm(W)}): it pokes "
                       f"{_mm(B - W)} out under the tile")
    return out


def report(h: dict, d: dict, flipped: bool) -> dict:
    """The contract's MarkerPlan.extrude: the heights as planned. A 3D
    print's are the request's (used exactly); an inkjet sticker's are the
    core's paper (the white) and its ink's depth (the black: t/2, make rule
    2), as the layers have them."""
    W, B, P = h["white_mm"], h["black_mm"], h["paper_mm"]
    st = d.get("sticker")
    if h["method"] == "inkjet" and st:
        P = W = st["thickness_mm"]
        B = st["ink_z_mm"][1] - st["ink_z_mm"][0]
    return {"method": h["method"], "mode": h["mode"], "white_mm": _r(W), "black_mm": _r(B),
            "paper_mm": _r(P), "flipped": bool(flipped), "driven": list(h["driven"])}
