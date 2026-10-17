"""REF aruco_feature.evaluate() as a pure function of numbers.

Ported from REF (cad-exporter c8216ff) `ArucoMarkers/aruco_feature.py`:
`_layout_rect`, `label_for`, `evaluate`, `face_origin`, `trim_notes`,
`_trim_inputs`, `_trim_eval`, line for line. What REF read off a Fusion
entity comes from the `Target` (plan/target.py):

| REF read | Here |
|---|---|
| `profile_rect(target, s)` / `aruco_tags.face_frame` + `keep_x` | the base frame (o, x, y, z, w, h): `base`, default the target's own frame |
| `_profile_loops_m` / `_face_loops_m` | `Target.loops_m()` |
| `label_name(target, s, host)` | the spec's `name` |
| `s["x_ref"]` | `Target.x_ref` (2D, in the base frame) |
| `_trim_face_body`, `aruco_tags.face_loops_2d` | `Target.body_mm`, `Target.trim_face_loops_mm()` |
| `_body_extent_mm`, `_trim_measure` | the body box (and footprint) of the target, measured exactly |

Frames are REF's: cm, in the base frame's space (the host component's in
REF). `host_xform` is the adapter's. The caches are gone (a pure call).
"""
from __future__ import annotations

import dataclasses

from ..core import autosize as _A
from ..core import chamfer as _CH
from ..core import label as _AL
from ..core import markers as _M
from ..core import origin as _OR
from ..core import settings as _S
from ..core import slabs as _SL
from ..core import trim as _TR
from ..core.geometry import _cross, _dot_f as _dot, _is_box, _loops_mm, _rotz

IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def A():
    return _A


def SL():
    return _SL


def CH():
    return _CH


def OR():
    return _OR


def AL():
    return _AL


def TR():
    return _TR


def base_of(target, base=None):
    """(o, x, y, z, w_cm, h_cm): `base` as given (4 or 6 items), else the
    target's own frame at the origin."""
    if base is None:
        o, x, y, z = (list(v) for v in IDENTITY)
        return o, x, y, z, target.w_mm / 10.0, target.h_mm / 10.0
    if len(base) >= 6:
        o, x, y, z, w, h = base[:6]
        return list(o), list(x), list(y), list(z), float(w), float(h)
    o, x, y, z = base[:4]
    return list(o), list(x), list(y), list(z), target.w_mm / 10.0, target.h_mm / 10.0


# ------------------------------------------------------------- evaluate

def _layout_rect(kind, w_m, h_m, s, n):
    """Autosize in a w x h box (m). Size given -> keep it (clamp if needed)."""
    a = A()
    kw = dict(dictionary=s["dictionary"], quiet_modules=float(s["quiet_modules"]),
              cells=_S.cells_of(s))
    L = float(n.get("size") or 0.0) / 1000.0
    S = float(n.get("square") or 0.0) / 1000.0
    if L <= 0.0:                    # the same default as a clicked face (fit_on_loops)
        return a.face_default(kind, w_m, h_m, **kw)
    force = tuple(s["force"]) if s.get("force") and kind != "single" else None
    lay = a.layout_for_size(kind, w_m, h_m, L, S, force=force, **kw)
    # a grid where only one marker fits comes back as a SINGLE (ok, noted):
    # a typed board size must not quietly turn into one marker
    if (not lay.ok or lay.kind != kind) and force:
        lay = a.layout_for_size(kind, w_m, h_m, L, S, **kw)
    if not lay.ok or lay.kind != kind:
        lay = a.clamp_to_fit(kind, w_m, h_m, L, S, **kw)
    return lay


def label_for(target, s, n, spec, plan, mark, tile_mm, base, frame, name=""):
    """REF label_for: the tag's label (aruco_label.plan_label), its white
    from where this mode has it, the corner mark and pins kept clear of."""
    al = AL()
    ls = al.LabelSettings.from_dict(s.get("label") if isinstance(s.get("label"), dict) else None)
    if not ls.on:
        return al.Label(settings=ls)
    mode = s["mode"]
    op = plan.op
    has_body = bool(s.get("has_body"))
    is_profile = target.is_profile
    o, x, y, _z = frame
    sticker = al.sticker_rect(spec)
    tile = None
    if mode == "both" and tile_mm is not None:
        tile = (-tile_mm[0] / 2.0, -tile_mm[1] / 2.0, tile_mm[0] / 2.0, tile_mm[1] / 2.0)
    bigger = (tile is not None and is_profile
              and (tile[2] - sticker[2] > 1e-3 or tile[3] - sticker[3] > 1e-3))
    room = al.white_room(mode, op, has_body, bigger)
    loops = None
    want_bounds = room["bounds"] == "face" and not (is_profile and mode == "both")
    if room["region"] == "face" or want_bounds:
        try:
            lm = target.loops_m()
            loops = _loops_mm(lm, base, o, x, y)
        except Exception:                          # noqa: BLE001
            loops = None
    if room["region"] == "tile":
        region = [al.rect_loop(tile)]
    elif room["region"] == "face":
        region = loops or None
    else:
        region = None
    bounds = loops if want_bounds else None
    pins = None
    if plan.pin is not None and tile is not None:
        pins = {"shape": s.get("pin"), "size": float(n.get("pin_size", SL().PIN_SIZE_MM))}
    slab = tuple(plan.layers.pattern)
    key = s.get("key", "")
    return al.plan_label(spec, ls, mode=mode, op=op, name=name, key=key,
                         region=region, grow=room["grow"], bounds=bounds,
                         tile=tile, mark=mark, pins=pins, slab=slab)


def x_ref_3d(target, base):
    """Target.x_ref (2D, base frame) as the 3D vector REF kept, or None."""
    if target.x_ref is None:
        return None
    u, v = target.x_ref
    bx, by = base[1], base[2]
    return [bx[i] * u + by[i] * v for i in range(3)]


def evaluate(target, s, n, base=None, name=""):
    """Everything the geometry needs (REF evaluate(): cm frames in the base
    frame's space). Raises ValueError("no marker fits here: ...") as REF.

    -> {"spec", "tag", "tile", "base", "layout", "notes", "lift_cm", "plan",
        "pins", "pin_frame", "turn", "x_fit", "pin_tol", "mode", "mark",
        "label", "label_white", "trim", "placement": the fit (cx, cy m,
        angle_deg) or None}
    """
    markers = _M
    kind = s["layout"]
    notes = []
    rot = float(s.get("rotate_deg", 0))
    L = float(n.get("size") or 0.0) / 1000.0
    S = float(n.get("square") or 0.0) / 1000.0
    angles = (0.0,) if (kind == "single" or rot) else (0.0, 90.0)
    tile_frame, pl = None, None
    cells = _S.cells_of(s)

    def fit(loops):
        return A().fit_on_loops(
            kind, loops, marker_m=(L if L > 0 else None), square_m=S,
            dictionary=s["dictionary"], quiet_modules=float(s["quiet_modules"]),
            angles_deg=angles, cells=cells)

    o, x, y, z, w, h = base_of(target, base)
    if target.is_profile:
        # like Extrude: the closed area, holes included. White + black: the
        # white tile is the profile's box (holes filled), so the whole box is
        # the marker's.
        tile_frame = (o, x, y, z, w, h)
        loops = None if s.get("mode") == "both" else target.loops_m()
        if loops is None or _is_box(loops, w, h):
            lay = _layout_rect(kind, w / 100.0, h / 100.0, s, n)     # honours the Layout pick
        else:
            lay, pl = fit(loops)
    else:
        # face_frame + keep_x happened in the adapter: `base` is their frame
        lay, pl = fit(target.loops_m())
    base = (o, x, y, z, w, h)
    if pl:
        o = [o[i] + x[i] * pl["cx"] * 100.0 + y[i] * pl["cy"] * 100.0 for i in range(3)]
        x = _rotz(x, z, float(pl.get("angle_deg", 0.0)))
        y = _cross(z, x)
    xr = x_ref_3d(target, base)
    if xr and not target.is_profile and _dot(x, xr) < -1e-6:
        x = [-c for c in x]                         # the same, after the fit (and for
        y = _cross(z, x)                            # nodes that only have x_ref)
    x_fit = list(x)
    notes += list(getattr(lay, "notes", []) or [])
    if not getattr(lay, "ok", False):
        raise ValueError("no marker fits here: " + ("; ".join(notes) or "the target is too small"))
    spec = markers.TagSpec(dictionary=s["dictionary"], marker_id=int(round(n["marker_id"])),
                           quiet_modules=float(s["quiet_modules"]), layout=kind,
                           grow_m=markers.CELL_OVERLAP_M if s.get("grow") else 0.0,
                           legacy=bool(s.get("legacy")))
    spec = lay.apply(spec)
    pl_ = _S.plan_of(s, n)
    L_ = pl_.layers
    spec.depth_m, spec.raise_m, spec.recess_m = (L_.depth / 1000.0, L_.raise_ / 1000.0,
                                                 L_.recess / 1000.0)
    if tile_frame is None:
        tile_frame = (o, x, y, z, spec.tile_size_m[0] * 100.0, spec.tile_size_m[1] * 100.0)
    # Origin (aruco_origin): the pattern turned on its own footprint
    turn, turn_note = OR().effective(s.get("turn"), spec.layout, spec.cols, spec.rows,
                                     s.get("origin_v"))
    if turn_note:
        notes.append(turn_note)
    if OR().transposes(spec.layout, turn):
        spec = dataclasses.replace(spec, cols=spec.rows, rows=spec.cols)
    if turn:
        x = _rotz(x, z, float(turn))
        y = _cross(z, x)
    lift = L_.surface / 10.0                                            # mm -> cm
    tag_o = [o[i] + z[i] * lift for i in range(3)]
    tile = tile_frame if s["mode"] == "both" else None
    tile_mm = None
    if tile is not None:
        tw, th = (tile[4], tile[5]) if turn % 180 == 0 else (tile[5], tile[4])
        tile_mm = (tw * 10.0, th * 10.0)
    mark = None
    want = CH().choice_of(_S.normalise(s, partial=True))     # the old "chamfer" too
    if want != "none":
        mk = CH().mark_for_spec(spec, s["mode"], pl_.op, tile_mm, want=want)
        if mk.instead:
            notes.append(mk.instead)
        if mk.kind == "none":
            if mk.note and mk.note != mk.instead:
                notes.append(mk.note)
        else:
            mark = mk
    label, label_white = None, None
    ls = s.get("label")
    if isinstance(ls, dict) and ls.get("on"):
        label = label_for(target, s, n, spec, pl_, mark, tile_mm, base, (o, x, y, z), name)
        notes += [t for t in label.notes if t not in notes]
        if label.kind == "none" and label.preview is not None:
            notes.append("label warning: not built -- " + "; ".join(label.preview.violations)
                         + " (Build anyway in the Label group builds it)")
        elif label.violations:
            notes.append("label warning: built anyway although: "
                         + "; ".join(label.violations))
        if label.kind != "none" and label.white is not None:
            u0, v0, u1, v1 = label.white
            if tile is not None:
                cu, cv = (u0 + u1) / 20.0, (v0 + v1) / 20.0
                tile = ([o[i] + x[i] * cu + y[i] * cv for i in range(3)], list(x), list(y),
                        list(z), (u1 - u0) / 10.0, (v1 - v0) / 10.0)
                tile_mm = (u1 - u0, v1 - v0)
                if mark is not None and mark.kind == "tile_cut":
                    grown = AL().mark_on_tile(spec, s["mode"], pl_.op, tuple(label.white))
                    if grown.kind == "tile_cut":
                        mark = grown
            else:
                label_white = tuple(label.white)          # White only's white pattern
    pins, pin_frame = [], None
    if pl_.pin is not None and tile is not None:
        pin_frame = (tile[0], x, y, z)
        pins = SL().pin_outlines(s.get("pin"), float(n.get("pin_size", SL().PIN_SIZE_MM)),
                                 tile_mm[0], tile_mm[1],
                                 cut=mark.leg if mark is not None and mark.kind == "tile_cut"
                                 else 0.0)
    trim_in, trim_err = None, None
    if "trim" in pl_.parts:
        try:
            trim_in = _trim_inputs(target, s, spec, base, (o, x, y, z), tile, tile_mm, label,
                                   mark, pins)
        except Exception as exc:                   # noqa: BLE001
            trim_err = f"the trim could not be read ({type(exc).__name__}: {exc})"[:200]
    ev = {"spec": spec, "tag": (tag_o, x, y, z), "tile": tile, "base": base,
          "layout": lay, "notes": notes, "lift_cm": lift, "plan": pl_, "pins": pins,
          "pin_frame": pin_frame, "turn": turn, "x_fit": x_fit,
          "pin_tol": float(n.get("pin_tol", SL().PIN_TOL_MM)), "mode": s["mode"],
          "mark": mark, "label": label, "label_white": label_white, "placement": pl,
          "tile_mm": tile_mm}
    ev["trim"] = None
    if trim_in is not None or trim_err is not None:
        try:
            if trim_err is not None:
                raise ValueError(trim_err)
            ev["trim"] = _trim_eval(ev, trim_in, target)
        except Exception as exc:                   # noqa: BLE001
            t = _S.trim_setting(s) or {"axes": "both"}
            ev["trim"] = TR().failed(t["axes"], None, str(exc)[:200])
        ev["notes"].extend(trim_notes(ev["trim"]))
    return ev


def face_origin(ev):
    """The pattern's centre on the face / sketch plane (the slabs' 0)."""
    o, _x, _y, z = ev["tag"]
    return [o[i] - z[i] * ev["lift_cm"] for i in range(3)]


# ---------------------------------------------------------- Trim excess

def trim_notes(tp):
    """The node's notes for a TrimPlan: "trim refused: ..." (a warning: the
    node keeps the body whole), "trim: ..." (info)."""
    if tp is None:
        return []
    out = []
    if tp.refused:
        out.append("trim refused: " + "; ".join(tp.refusals)
                   + " (Cut anyway in Advanced trims it)")
    elif tp.refusals and tp.active:
        out.append("trim: cut anyway although " + "; ".join(tp.refusals))
    out += ["trim: " + t for t in tp.notes]
    return out


def _proj(p, o, x, y, z=None):
    """REF's plate fixture's projection (sum() from the int 0)."""
    d = [p[i] - o[i] for i in range(3)]
    out = (sum(a * b for a, b in zip(d, x)), sum(a * b for a, b in zip(d, y)))
    if z is not None:
        out += (sum(a * b for a, b in zip(d, z)),)
    return out


def _model(base, u_mm, v_mm, z_mm=None):
    """A base-frame point (mm) in the base frame's space (cm)."""
    bo, bx, by, bz = base[0], base[1], base[2], base[3]
    if z_mm is None:
        return [bo[i] + bx[i] * (u_mm / 10.0) + by[i] * (v_mm / 10.0) for i in range(3)]
    return [bo[i] + bx[i] * (u_mm / 10.0) + by[i] * (v_mm / 10.0) + bz[i] * (z_mm / 10.0)
            for i in range(3)]


def _face_loops_2d(target, base, o, x, y):
    """The face under a sketch area, in (o, x, y) cm (REF face_loops_2d)."""
    return [[_proj(_model(base, u, v), o, x, y) for (u, v) in lp]
            for lp in target.face_loops_mm]


def _trim_inputs(target, s, spec, base, frame, tile, tile_mm, label, mark, pins):
    """Trim excess in the TARGET's frame: {"t": the setting, "outline": mm,
    "loops": the face's loops (mm) or None, "body": the target body} -- all
    in the pattern frame (the pattern's centre on the face plane)."""
    TRm, al = TR(), AL()
    t = _S.trim_setting(s)
    o, x, y, _z = frame

    def uv(p):
        d = [p[i] - o[i] for i in range(3)]
        return _dot(d, x) * 10.0, _dot(d, y) * 10.0
    extras = []
    if s["mode"] == "both" and tile is not None and tile_mm is not None:
        cu, cv = uv(tile[0])
        base_r = (cu - tile_mm[0] / 2.0, cv - tile_mm[1] / 2.0,
                  cu + tile_mm[0] / 2.0, cv + tile_mm[1] / 2.0)
        for p in pins or []:
            b = TRm.box_of(SL().outline_points(p, 32))
            extras.append((b[0] + cu, b[1] + cv, b[2] + cu, b[3] + cv))
    else:
        base_r = tuple(al.sticker_rect(spec))          # the pattern + its quiet zone
    if label is not None and label.kind != "none":
        extras += [tuple(p.rect) for p in label.parts]
        if label.white is not None:
            extras.append(tuple(label.white))
    if mark is not None:
        for pts in (mark.outline, mark.solid):
            if pts:
                extras.append(TRm.box_of(pts))
    body = target.body_mm
    loops = None
    if target.is_profile:
        if target.face_loops_mm:
            loops = [[(u * 10.0, v * 10.0) for (u, v) in lp]
                     for lp in _face_loops_2d(target, base, o, x, y)]
    else:
        loops = _loops_mm(target.loops_m(), base, o, x, y)
    return {"t": t, "outline": TRm.outline(base_r, extras, t["margin_mm"]), "loops": loops,
            "body": body}


def _body_extent_mm(target, base, fo, x, y, z):
    """(u0, v0, u1, v1), (z0, z1): the body box's extent along the tag's
    axes, mm from `fo` (its corners, as REF's plate fixture)."""
    b = target.body_mm
    pts = [_model(base, a, bb, c) for a in (b["u0"], b["u1"]) for bb in (b["v0"], b["v1"])
           for c in (b["z0"], b["z1"])]
    pr = [_proj(p, fo, x, y, z) for p in pts]
    us = [p[0] * 10.0 for p in pr]
    vs = [p[1] * 10.0 for p in pr]
    ts = [p[2] * 10.0 for p in pr]
    return (min(us), min(vs), max(us), max(vs)), (min(ts), max(ts))


def _clip(poly, r):
    return TR().clip(poly, r)


def _trim_measure(target, base, fo, x, y, z, keep):
    """(the body's volume, the volume the column removes) mm3, or None when
    it is not measured. A box body: its extent rect along the tag's axes x
    its depth (REF's plate); a prism body (body_loops_mm): its footprint's
    area, exactly."""
    b = target.body_mm
    if not b.get("measured", True):
        return None
    t = b.get("depth", b["z1"] - b["z0"])
    if target.body_loops_mm is None:
        rect, _z = _body_extent_mm(target, base, fo, x, y, z)
        vb = (rect[2] - rect[0]) * (rect[3] - rect[1]) * t
        ku = max(0.0, min(rect[2], keep[2]) - max(rect[0], keep[0]))
        kv = max(0.0, min(rect[3], keep[3]) - max(rect[1], keep[1]))
        return (vb, vb - ku * kv * t)
    loops = [[_proj(_model(base, u, v), fo, x, y) for (u, v) in lp] for lp in target.body_loops_mm]
    loops = [[(u * 10.0, v * 10.0) for (u, v) in lp] for lp in loops]
    outer, holes = loops[0], loops[1:]
    area = TR().face_area(outer, holes)
    kept = TR().kept_area(outer, holes, keep)
    return (area * t, (area - kept) * t)


def _trim_eval(ev, ti, target):
    """The TrimPlan for evaluate()."""
    TRm = TR()
    t = ti["t"]
    body = ti["body"]
    if body is None:
        return TRm.failed(t["axes"], None, "there is no body under the tag to trim")
    fo = face_origin(ev)
    _o, x, y, z = ev["tag"]
    base = ev["base"]
    rect, zr = _body_extent_mm(target, base, fo, x, y, z)
    pl = ev["plan"]
    ends = list(zr)
    for sl in (pl.layers.white, pl.layers.black, pl.layers.pattern, pl.pin):
        if sl:
            ends += list(sl)
    zz = (min(ends), max(ends))
    pad = TRm.pad_for(rect, zz)
    keep, cut = TRm.keep_and_cut(t["axes"], ti["outline"], rect, pad)
    volumes = None
    if cut:
        pad_m = TRm.pad_for(rect, zr)
        keep_m, _cut_m = TRm.keep_and_cut(t["axes"], ti["outline"], rect, pad_m)
        volumes = _trim_measure(target, base, fo, x, y, z, keep_m)
    return TRm.plan_trim(t["axes"], ti["outline"], rect, ti["loops"], margin=t["margin_mm"],
                         force=t["force"], volumes=volumes, z=zz)
