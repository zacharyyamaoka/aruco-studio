"""The golden cases: their inputs, and how one case is run.

Stdlib only, and it imports NOTHING of either core: every runner takes the
modules it needs as arguments. The maker (tools/make_goldens_from_ref.py)
calls them with REF's modules, read-only, and stores the outputs; the
replays (tests/core/test_golden_*.py) call the SAME runner with
aruco_studio.core's modules and compare. So a golden's numbers can only come
from REF's code, and a replay tests exactly what the golden recorded.

Outputs pass through `ser` (dataclasses -> dicts, tuples -> lists, bytes and
long tables -> sha256) and a JSON round trip on both sides.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random

# ------------------------------------------------------------------ helpers


def sha(obj) -> str:
    if isinstance(obj, (bytes, bytearray)):
        data = bytes(obj)
    elif isinstance(obj, str):
        data = obj.encode("utf-8")
    else:
        data = json.dumps(ser(obj), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def ser(x):
    """Plain JSON data of a result (exact floats; dataclasses by field)."""
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return {f.name: ser(getattr(x, f.name)) for f in dataclasses.fields(x)}
    if isinstance(x, dict):
        return {str(k): ser(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [ser(v) for v in x]
    if isinstance(x, (bytes, bytearray)):
        return {"sha256": hashlib.sha256(bytes(x)).hexdigest(), "len": len(x)}
    if isinstance(x, float) and not math.isfinite(x):
        return {"float": repr(x)}
    return x


def norm(x):
    """The JSON view of a result, as the golden file holds it."""
    return json.loads(json.dumps(ser(x)))


def guarded(fn, *a, **k):
    """A result, or the exception REF raised (type and words): a refusal is
    an answer too."""
    try:
        return {"ok": ser(fn(*a, **k))}
    except Exception as exc:                       # noqa: BLE001
        return {"raises": type(exc).__name__, "text": str(exc)}


def circle(cx, cy, r, n=48, cw=False):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n))
           for k in range(n)]
    return pts[::-1] if cw else pts


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


LAYOUTS = ("single", "grid", "charuco")
MODES = ("both", "black", "white")
OPS = ("join", "new")


# --------------------------------------------------------------- dictionary

def dictionary_cases(D):
    return [{"name": n} for n in D.DICTIONARY_NAMES]


def dictionary_run(case, D):
    name = case["name"]
    info = D.dictionary_info(name)
    grids, rects = [], []
    for i in range(info["capacity"]):
        grids.append(sha(D.marker_grid(name, i)))
        rects.append(sha(D.black_rects(name, i)))
    full = {str(i): {"grid": D.marker_grid(name, i), "rects": D.black_rects(name, i),
                     "png": sha(D.marker_png(name, i)), "svg": sha(D.marker_svg(name, i)),
                     "png_q2": sha(D.marker_png(name, i, module_px=7, quiet_modules=2)),
                     "svg_sized": sha(D.marker_svg(name, i, size=30, quiet_modules=0.5))}
            for i in range(min(3, info["capacity"]))}
    folded = guarded(D.dictionary_info, name.lower())
    return {"info": info, "grid_sha": sha(grids), "rects_sha": sha(rects), "first": full,
            "folded": folded, "bad_id": guarded(D.marker_grid, name, info["capacity"])}


# -------------------------------------------------------------------- board

def board_cases(B):
    out = []
    for layout in LAYOUTS:
        for cols, rows in ((1, 1), (3, 1), (1, 3), (4, 3), (5, 7), (2, 2), (6, 2), (8, 2)):
            if layout == "single" and (cols, rows) != (1, 1):
                continue
            for dictionary in ("DICT_4X4_50", "DICT_6X6_250", "DICT_APRILTAG_36h11"):
                for first in (0, 7):
                    for legacy in ((False, True) if layout == "charuco" else (False,)):
                        out.append({"layout": layout, "dictionary": dictionary, "first_id": first,
                                    "marker_length_m": 0.03 if layout != "charuco" else 0.0225,
                                    "rows": rows, "cols": cols,
                                    "separation_m": 0.006 if layout == "grid" else 0.0,
                                    "square_length_m": 0.03 if layout == "charuco" else 0.0,
                                    "legacy": legacy})
    # what cv2 refuses
    out += [{"layout": "grid", "dictionary": "DICT_4X4_50", "first_id": 0, "marker_length_m": 0.03,
             "rows": 2, "cols": 2, "separation_m": 0.0, "square_length_m": 0.0, "legacy": False},
            {"layout": "charuco", "dictionary": "DICT_4X4_50", "first_id": 0,
             "marker_length_m": 0.03, "rows": 1, "cols": 4, "separation_m": 0.0,
             "square_length_m": 0.04, "legacy": False},
            {"layout": "charuco", "dictionary": "DICT_4X4_50", "first_id": 0,
             "marker_length_m": 0.04, "rows": 3, "cols": 3, "separation_m": 0.0,
             "square_length_m": 0.04, "legacy": False},
            {"layout": "grid", "dictionary": "DICT_4X4_50", "first_id": 45, "marker_length_m": 0.03,
             "rows": 2, "cols": 4, "separation_m": 0.006, "square_length_m": 0.0, "legacy": False}]
    return out


def board_run(case, B):
    spec = B.BoardSpec(**case)
    chk = guarded(B.check_spec, spec)
    if "raises" in chk:
        return {"check": chk}
    rects = B.black_rects_m(spec)
    return {"check": chk, "count": B.marker_count(spec), "ids": B.ids(spec),
            "extent_m": B.extent_m(spec), "object_points": ser(B.object_points(spec)),
            "charuco_corners": ser(B.charuco_corners(spec)) if spec.layout == "charuco" else None,
            "marker_corners_m": ser(B.marker_corners_m(spec)),
            "black_rects_n": len(rects), "black_rects_sha": sha(rects),
            "black_rects_head": ser(rects[:6]),
            "opencv_frame": B.opencv_frame(spec),
            "svg": sha(B.board_svg(spec, quiet_m=0.003)),
            "png": sha(B.board_png(spec, px_per_m=4000.0, quiet_m=0.003))}


# ------------------------------------------------------------------- origin

def origin_cases(OR):
    out = []
    for layout in LAYOUTS:
        for cols, rows in ((1, 1), (3, 1), (2, 4), (3, 3), (5, 2)):
            if layout == "single" and (cols, rows) != (1, 1):
                continue
            for turn in (0, 90, 180, 270, 360, -90, 45, 450, 89.6, "90", None):
                for rule in (2, None):
                    out.append({"layout": layout, "cols": cols, "rows": rows, "turn": turn,
                                "rule": rule})
    return out


def origin_run(case, OR):
    layout, cols, rows, turn, rule = (case[k] for k in ("layout", "cols", "rows", "turn", "rule"))
    t = turn if not isinstance(turn, float) else turn
    out = {"effective": guarded(OR.effective, t, layout, cols, rows, rule=rule),
           "raw": guarded(OR.raw_turn, t), "norm": guarded(OR.norm, t)}
    if turn in (0, 90, 180, 270):
        out.update({"transposes": OR.transposes(layout, turn),
                    "built": OR.built(layout, turn, cols, rows),
                    "rotate_cw": OR.rotate_cw(turn), "corner": OR.corner(turn), "up": OR.up(turn),
                    "label": OR.label(layout, turn), "describe": OR.describe(layout, turn, cols, rows),
                    "opencv_in_layout": ser(OR.opencv_in_layout(layout, turn, 40.0 * cols, 30.0 * rows))})
    if turn == 0 and rule == 2:
        out["items"] = ser(OR.items(layout))
        out["corners_of"] = ser(OR.corners_of(layout))
        out["turn_of"] = [OR.turn_of(layout, name) for name, _t in OR.items(layout)] + \
            [OR.turn_of(layout, "nonsense")]
    return out


# -------------------------------------------------------------------- slabs

SLAB_NUMBERS = [(0, 2, 2, -0.6), (0, 2, 2, 0.6), (-1, 2, 1, -0.6), (0, 2, 2.5, 0.5),
                (0, 2, -0.5, 1.0), (0, 0.6, 0, -0.6), (0, 2, 0, 0.6), (0.5, -1.5, -1, -0.4),
                (0, 0, 2, -0.6), (0, 2, 2, 0.0)]


def slabs_cases(S):
    out = []
    for mode in MODES:
        for op in OPS:
            for has_body in (True, False):
                for pin in ("none", "triangle", "round"):
                    for k, (wo, wh, bo, bh) in enumerate(SLAB_NUMBERS):
                        for trim in (False, True):
                            out.append({"fn": "plan", "mode": mode, "op": op, "has_body": has_body,
                                        "pin": pin, "numbers": [wo, wh, bo, bh], "trim": trim})
    for mode in MODES:
        for h in (0.5, 2.0, 3.0):
            for th in (0.3, 0.6, 1.0):
                for ab in (-0.4, 0.0, 0.6):
                    out.append({"fn": "from_legacy", "mode": mode, "height": h, "thickness": th,
                                "above": ab})
    for shape in ("triangle", "round", "none", "square"):
        for size in (1.0, 3.0, 6.0, 20.0):
            for w, h in ((40, 40), (12, 12), (80, 20)):
                for cut in (0.0, 2.1):
                    out.append({"fn": "pin_outlines", "shape": shape, "size": size, "w": w,
                                "h": h, "cut": cut})
    for v in (0, 0.01, -0.01, 0.04, -0.3, 80, -80, 2.0):
        for prev in (None, -0.3, 0.3):
            out.append({"fn": "snap_height", "h": v, "prev": prev})
    return out


def slabs_run(case, S):
    fn = case["fn"]
    if fn == "plan":
        wo, wh, bo, bh = case["numbers"]
        n = dict(S.default_numbers(case["mode"]), **S.pin_defaults())
        n.update(white_offset=wo, white_height=wh, black_offset=bo, black_height=bh)
        kw = {"trim": True} if case["trim"] else {}
        p = guarded(S.plan, case["mode"], case["op"], case["has_body"], n, case["pin"], **kw)
        lay = guarded(S.layers, case["mode"], n, case["has_body"])
        out = {"plan": p, "layers": lay}
        if "ok" in p:
            plan = S.plan(case["mode"], case["op"], case["has_body"], n, case["pin"], **kw)
            out["describe"] = S.describe(plan)
            out["structure"] = ser(plan.structure)
            out["effective_op"] = S.effective_op(case["mode"], case["op"], case["has_body"])
            out["pin_applies"] = S.pin_applies(case["mode"], case["op"], case["has_body"])
            out["white_top"] = S.white_top(case["mode"], n)
        return out
    if fn == "from_legacy":
        return guarded(S.from_legacy, case["mode"], case["height"], case["thickness"], case["above"])
    if fn == "pin_outlines":
        got = guarded(S.pin_outlines, case["shape"], case["size"], case["w"], case["h"], cut=case["cut"])
        if "ok" in got:
            outs = S.pin_outlines(case["shape"], case["size"], case["w"], case["h"], cut=case["cut"])
            got["grown"] = [ser(S.grow(o, 0.15)) for o in outs]
            got["points"] = [ser(S.outline_points(o, 16)) for o in outs]
            if len(outs) > 1:
                got["gap"] = S.edge_gap(outs[0], outs[1])
        return got
    if fn == "snap_height":
        return guarded(S.snap_height, case["h"], 0.05, case["prev"])
    raise ValueError(fn)


# ------------------------------------------------------------------ chamfer

def chamfer_cases(C):
    out = []
    for layout in LAYOUTS:
        for mode in MODES:
            for op in ("join", "new", None):
                for want in ("none", "cut", "triangle"):
                    for rows, cols in ((1, 1), (2, 3), (3, 3), (4, 4)):
                        if layout == "single" and (rows, cols) != (1, 1):
                            continue
                        for legacy in ((False, True) if layout == "charuco" else (False,)):
                            for quiet in (1.0, 0.5, 2.0):
                                for tile in (None, "big"):
                                    out.append({"layout": layout, "mode": mode, "op": op,
                                                "want": want, "rows": rows, "cols": cols,
                                                "legacy": legacy, "quiet": quiet, "tile": tile})
    return out


def chamfer_run(case, C):
    layout, rows, cols = case["layout"], case["rows"], case["cols"]
    module = 5.0                                    # mm: a 30 mm 4x4 marker
    marker = 30.0 if layout != "charuco" else 22.5
    square = 30.0 if layout == "charuco" else 0.0
    if layout == "single":
        ext = (marker, marker)
    elif layout == "grid":
        ext = (cols * marker + (cols - 1) * 6.0, rows * marker + (rows - 1) * 6.0)
    else:
        ext = (cols * square, rows * square)
    module = marker / 6.0
    q = case["quiet"] * module
    tile = None if case["tile"] is None else (ext[0] + 2 * q + 8.0, ext[1] + 2 * q + 4.0)
    m = guarded(C.plan_mark, layout, case["mode"], case["op"], ext, module, case["quiet"],
                tile_mm=tile, square_mm=square, marker_mm=marker, rows=rows,
                legacy=case["legacy"], want=case["want"])
    if "ok" in m:
        mk = C.plan_mark(layout, case["mode"], case["op"], ext, module, case["quiet"], tile_mm=tile,
                         square_mm=square, marker_mm=marker, rows=rows, legacy=case["legacy"],
                         want=case["want"])
        back = C.from_dict(mk.to_dict())
        m = {"to_dict": mk.to_dict(), "is_cut": mk.is_cut, "full": ser(mk),
             "back": back.to_dict() if back is not None else None,
             "same": C.same(mk.to_dict(), back.to_dict() if back is not None else None),
             "pin_inset": [C.pin_inset(c, 1.0, h) for c in (0.0, 2.1, 5.0) for h in (0.0, 1.5)]}
    return {"valid": C.valid_marks(layout, case["mode"], case["op"], rows, case["legacy"]),
            "choose": ser(C.choose(case["want"], C.valid_marks(layout, case["mode"], case["op"],
                                                                rows, case["legacy"]))),
            "charuco_cut": C.charuco_cut(layout, rows, case["legacy"]),
            "mark": m}


CHOICE_SETTINGS = [{}, {"chamfer": True}, {"chamfer": False}, {"corner_mark": "cut"},
                   {"corner_mark": "triangle"}, {"corner_mark": "none", "chamfer": True},
                   {"corner_mark": "bogus"}, {"corner_mark": None, "chamfer": True},
                   {"corner_mark": "triangle", "chamfer": True}]


# ----------------------------------------------------------------- autosize

CELLS = [None, {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 0.0},
         {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0},
         {"rule": 1, "of": "cell", "mm": 0.45, "min_mm": 0.0}]


def autosize_cases(G):
    out = []
    for f in G.FACES:
        for kind in LAYOUTS:
            for ci, cells in enumerate(CELLS):
                out.append({"fn": "fit_on_loops", "face": f["key"], "kind": kind, "cells": ci,
                            "marker_mm": None})
                for (k2, L, S) in G.typed_for(f["key"]):
                    if k2 == kind:
                        out.append({"fn": "fit_on_loops", "face": f["key"], "kind": kind,
                                    "cells": ci, "marker_mm": L, "square_mm": S})
                out.append({"fn": "candidates_on_loops", "face": f["key"], "kind": kind,
                            "cells": ci})
        out.append({"fn": "largest_clear_rect", "face": f["key"]})
        out.append({"fn": "largest_clear_rect", "face": f["key"], "aspect": 2.0, "angle": 30.0})
    for kind in LAYOUTS:
        for w, h in ((40, 40), (15, 200), (100, 60), (12, 9), (300, 25)):
            for ci in range(len(CELLS)):
                for d in ("DICT_4X4_50", "DICT_6X6_250"):
                    out.append({"fn": "face_default", "kind": kind, "w": w, "h": h, "cells": ci,
                                "dictionary": d})
                    out.append({"fn": "candidates", "kind": kind, "w": w, "h": h, "cells": ci,
                                "dictionary": d})
    for fam in ("DICT_4X4_50", "DICT_5X5_100", "DICT_APRILTAG_36h11", "DICT_ARUCO_ORIGINAL"):
        for need in (1, 20, 45, 120, 600):
            out.append({"fn": "auto_dictionary", "dictionary": fam, "need": need, "used": [3, 7]})
    return out


def autosize_run(case, A, G):
    fn = case["fn"]
    cells = CELLS[case.get("cells", 0)] if "cells" in case else None
    if fn in ("fit_on_loops", "candidates_on_loops", "largest_clear_rect"):
        loops = G.loops_m(G.face(case["face"]))
    if fn == "fit_on_loops":
        mm = case.get("marker_mm")
        lay, pl = A.fit_on_loops(case["kind"], loops, marker_m=None if mm is None else mm / 1000.0,
                                 square_m=(case.get("square_mm") or 0.0) / 1000.0, cells=cells)
        return {"layout": ser(lay), "placement": ser(pl), "summary": G.summary(lay, pl),
                "label": lay.label()}
    if fn == "candidates_on_loops":
        return [ser(l) for l in A.candidates_on_loops(case["kind"], loops, cells=cells)]
    if fn == "largest_clear_rect":
        return ser(A.largest_clear_rect(loops, aspect=case.get("aspect"),
                                        angle_deg=case.get("angle", 0.0)))
    if fn == "face_default":
        lay = A.face_default(case["kind"], case["w"] / 1000.0, case["h"] / 1000.0,
                             dictionary=case["dictionary"], cells=cells)
        return {"layout": ser(lay), "label": lay.label(), "tile_m": ser(lay.tile_m),
                "extent_m": ser(lay.extent_m)}
    if fn == "candidates":
        return [ser(l) for l in A.candidates(case["kind"], case["w"] / 1000.0, case["h"] / 1000.0,
                                             dictionary=case["dictionary"], limit=None, cells=cells)]
    if fn == "auto_dictionary":
        return guarded(A.auto_dictionary, case["dictionary"], case["need"], case["used"])
    raise ValueError(fn)


# -------------------------------------------------------------------- label

def label_cases(L):
    rnd = random.Random(20261016)
    specs = [{"marker_id": 12, "marker_length_m": 0.03},
             {"marker_id": 3, "marker_length_m": 0.02, "dictionary": "DICT_6X6_250"},
             {"marker_id": 0, "marker_length_m": 0.03, "layout": "grid", "rows": 2, "cols": 3,
              "separation_m": 0.006},
             {"marker_id": 5, "marker_length_m": 0.0225, "layout": "charuco", "rows": 3,
              "cols": 4, "square_length_m": 0.03},
             {"marker_id": 40, "marker_length_m": 0.05, "quiet_modules": 2.0}]
    regions = [None, "roomy", "plate", "narrow", "disc"]
    out = []
    for i in range(200):
        sp = rnd.choice(specs)
        st = {"on": True, "content": rnd.choice(["id", "id_name", "name", "dict_id", "custom"]),
              "text": rnd.choice(["", "{dict} #{id}|{name}", "#{ids} {key}", "A-1 {size}"]),
              "place": rnd.choice(["auto", "black", "white"]),
              "row": rnd.choice(["auto", "bottom", "top", "both", "square"]),
              "side": rnd.choice(["auto", "below", "above", "left", "right"]),
              "scope": rnd.choice(["auto", "each", "first"]),
              "cap_mm": rnd.choice([0.0, 0.0, 2.5, 4.0, 8.0]),
              "nozzle_mm": rnd.choice([0.6, 0.4, 0.25]),
              "build_anyway": rnd.random() < 0.2}
        if rnd.random() < 0.25:
            st.update(position="manual", x_mm=rnd.choice([0.0, 6.0, -12.5]),
                      y_mm=rnd.choice([-22.0, 20.0, 0.0]))
        if rnd.random() < 0.15:
            st.update(offset_x_mm=rnd.choice([2.0, -1.5]), offset_y_mm=rnd.choice([1.0, -3.0]))
        rule = rnd.choice([1, 2, 2])
        if rule == 2:
            st["rule"] = 2
        out.append({"spec": sp, "settings": st, "mode": rnd.choice(MODES),
                    "op": rnd.choice(["join", "new"]), "region": rnd.choice(regions),
                    "grow": rnd.random() < 0.3, "mark": rnd.choice([None, "triangle", "cut"]),
                    "name": rnd.choice(["", "Arm:2+Plate:1", "GIM43"]), "key": "k1"})
    return out


REGIONS = {"roomy": [rect(-80, -80, 80, 80)],
           "plate": [rect(-25, -60, 25, 25), circle(0, -30, 5, cw=True)],
           "narrow": [rect(-25, -80, 25, 25)],
           "disc": [circle(2.09, 0, 26.5, n=96), circle(25.84, 0, 1.425, n=24, cw=True),
                    circle(2.09, 23.75, 1.425, n=24, cw=True)]}


def label_run(case, L, M, C):
    spec = M.TagSpec.from_dict(dict(case["spec"]), lambda m: None, "golden")
    mark = None
    if case["mark"]:
        mark = C.mark_for_spec(spec, case["mode"], case["op"] if case["mode"] == "both" else None,
                               want=case["mark"])
        if mark.kind == "none":
            mark = None
    region = REGIONS.get(case["region"]) if case["region"] else None
    lab = L.plan_label(spec, dict(case["settings"]), mode=case["mode"],
                       op=case["op"] if case["mode"] == "both" else None, name=case["name"],
                       key=case["key"], region=region, grow=case["grow"], mark=mark)
    d = lab.to_dict()
    return {"record": d, "kind": lab.kind, "side": lab.side, "ok": lab.ok, "texts": ser(lab.texts()),
            "notes": list(lab.notes), "violations": list(lab.violations),
            "describe": ser(L.describe(lab, case["mode"])),
            "check": L.check_label(spec, lab),
            "preview": lab.preview.to_dict() if lab.preview is not None else None,
            "position": ser(L.position_of(lab)),
            "relabel": L.relabel(json.loads(json.dumps(d)), M.TagSpec.from_dict(
                dict(case["spec"], marker_id=case["spec"]["marker_id"] + 1), lambda m: None, "g"),
                name="Copy:2").to_dict(),
            "zones": ser(L.clear_zones(spec, rule=lab.settings.rule))}


# --------------------------------------------------------------------- trim

def trim_cases(T):
    rnd = random.Random(16102026)
    out = []
    for i in range(400):
        w, h = rnd.uniform(20, 120), rnd.uniform(20, 120)
        cx, cy = rnd.uniform(-w / 4, w / 4), rnd.uniform(-h / 4, h / 4)
        tw, th = rnd.uniform(8, w * 0.9), rnd.uniform(8, h * 0.9)
        body = [-w / 2, -h / 2, w / 2, h / 2]
        tag = [cx - tw / 2, cy - th / 2, cx + tw / 2, cy + th / 2]
        shape = rnd.choice(["box", "box", "holes", "disc", "notch", "none"])
        depth = rnd.choice([2.0, 5.0, 10.0])
        out.append({"axes": rnd.choice(["x", "y", "both"]), "tag": tag, "body": body, "shape": shape,
                    "margin": rnd.choice([0.0, 0.0, 1.5, 4.0]), "force": rnd.random() < 0.15,
                    "depth": depth, "measured": rnd.random() < 0.9,
                    "extra": rnd.random() < 0.3})
    return out


def trim_run(case, T):
    body = tuple(case["body"])
    tag = tuple(case["tag"])
    extras = [(tag[0] - 3, tag[1] - 3, tag[0] + 2, tag[1] + 2)] if case["extra"] else []
    out = T.outline(tag, extras, margin=case["margin"])
    u0, v0, u1, v1 = body
    shape = case["shape"]
    if shape == "box":
        face = [rect(*body)]
    elif shape == "holes":
        face = [rect(*body), circle(u0 + 3, v0 + 3, 1.5, n=24, cw=True),
                circle((u0 + u1) / 2, (v0 + v1) / 2, 1.0, n=24, cw=True)]
    elif shape == "disc":
        face = [circle((u0 + u1) / 2, (v0 + v1) / 2, min(u1 - u0, v1 - v0) / 2, n=64)]
    elif shape == "notch":
        face = [[(u0, v0), (u1, v0), (u1, v1), ((u0 + u1) / 2, v1), ((u0 + u1) / 2, (v0 + v1) / 2),
                 (u0, (v0 + v1) / 2)]]
    else:
        face = None
    d = case["depth"]
    vol = None
    if case["measured"] and face is not None:
        keep, _c = T.keep_and_cut(case["axes"], out, body)
        outer, holes = T.split_loops(face)
        fa = T.face_area(outer, holes)
        vol = (fa * d, (fa - T.kept_area(outer, holes, keep)) * d)
    p = T.plan_trim(case["axes"], out, body, face, margin=case["margin"], force=case["force"],
                    volumes=vol, z=(-d, 0.0))
    return {"plan": ser(p), "active": p.active, "refused": p.refused, "cuts": p.cuts,
            "column": ser(p.column()), "regions": ser(p.regions()), "size_after": ser(p.size_after()),
            "summary": T.summary(p, "plate"), "outline": ser(out)}


TRIM_OF = [None, {}, {"rule": 1, "axes": "x"}, {"rule": 1, "axes": "both", "margin_mm": 2.5,
                                                 "force": True},
           {"rule": 2, "axes": "x"}, {"axes": "sideways"}, {"rule": "one", "axes": "x"}, "x", 3, [],
           {"rule": 1}, {"rule": 1, "axes": "y", "margin_mm": 80}, {"rule": 1, "axes": "y",
                                                                     "margin_mm": -1}]


# ---------------------------------------------------------------- numbering

def numbering_run(name, fixture, N):
    tags, occs = fixture
    plan = N.plan_ids(tags, occs, root_component="Robot")
    stable = N.plan_stable(tags, occs, root_component="Robot")
    led = N.ledger_after(stable, when="2026-10-16T00:00:00")
    again = N.plan_stable(tags, occs, ledger=led, root_component="Robot")
    return {"plan": plan.to_dict(), "summary": plan.summary(), "stable": stable.to_dict(),
            "state": N.node_state(stable), "ledger": led.to_dict(), "again": again.to_dict(),
            "dups": ser(plan.duplicates()), "parts": ser(plan.parts())}


# -------------------------------------------------------------- restructure

RESTRUCTURE_NUMS = [(0, 2, 2, -0.6), (0, 2, 2, 0.6), (-1, 2, 1, -0.6), (0, 2, 2.5, 0.5),
                    (0, 2, -0.5, 1.0), (0, 0.6, 0, -0.6), (0, 2, 0, 0.6)]


def structures(SL):
    """Every (op, parts) a node can have: REF test_aruco_extrude_sync section 4."""
    import itertools
    out = set()
    nums = [{"white_offset": wo, "white_height": wh, "black_offset": bo, "black_height": bh,
             "pin_length": 1.5, "pin_tol": 0.15, "pin_size": 3.0}
            for wo, wh, bo, bh in RESTRUCTURE_NUMS]
    for mode, op, has_body, pin, n in itertools.product(MODES, OPS, (True, False),
                                                        ("none", "triangle"), nums):
        p = SL.plan(mode, op, has_body, n, pin)
        out.add((p.op, tuple(p.parts)))
        p = SL.plan(mode, op, has_body, n, pin, trim=True)
        out.add((p.op, tuple(p.parts)))
    return sorted(out, key=str)


def restructure_run(pair, R):
    (op_old, old), (op_new, new) = pair
    return {"plan": R.restructure_plan(list(old), op_old, list(new), op_new),
            "combines_old": [R.has_combine(r, op_old) for r in old],
            "combines_new": [R.has_combine(r, op_new) for r in new]}


# ----------------------------------------------------------- Joint Origins

def jo_cases():
    rnd = random.Random(1172)

    def unit(v):
        n = math.sqrt(sum(c * c for c in v))
        return [c / n for c in v]

    def frame():
        z = unit([rnd.gauss(0, 1) for _ in range(3)])
        a = unit([rnd.gauss(0, 1) for _ in range(3)])
        x = unit([a[i] - sum(a[j] * z[j] for j in range(3)) * z[i] for i in range(3)])
        y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
        o = [rnd.uniform(-20, 20) for _ in range(3)]
        return [o, x, y, z]

    out = []
    for i in range(200):
        base = frame()
        if i % 4 == 0:
            # a target in the base's own plane (the usual case: a tag on its face)
            ang = rnd.choice([0.0, 90.0, 180.0, 270.0, rnd.uniform(-180, 180)])
            t = math.radians(ang)
            bo, bx, by, bz = base
            s = -1.0 if i % 8 == 0 else 1.0
            tx = [math.cos(t) * bx[k] + math.sin(t) * by[k] for k in range(3)]
            ty = [s * (-math.sin(t) * bx[k] + math.cos(t) * by[k]) for k in range(3)]
            tz = [s * c for c in bz]
            to = [bo[k] + rnd.uniform(-3, 3) * bx[k] + rnd.uniform(-3, 3) * by[k] for k in range(3)]
            target = [to, tx, ty, tz]
        else:
            target = frame()
        out.append({"base": base, "target": target})
    # exact axis cases (signed zeros, flips)
    I = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    out.append({"base": I, "target": [[1.0, 2.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                      [0.0, 0.0, -1.0]]})
    out.append({"base": I, "target": [[0.0, 0.0, 0.0], [-1.0, -0.0, 0.0], [0.0, -1.0, 0.0],
                                      [0.0, 0.0, 1.0]]})
    return out
