"""A new tag's TagSpec, and a print preset put on a tag (the Studio's
stand-in for REF's ArUco Extrude dialog on OK: `values()` + `core.form.new_tag_settings`
for a fresh tag, `apply_preset` for a Preset pick).

Pure functions of plain dicts (moved here from server/newtag.py in M8a, so
the design file's compile in scene/design.py can call them; the server's
module imports these names). A new tag gets what a
tag made by today's dialog stores: settings `v: 2` with `origin_v`
(ORIGIN_RULE), the label's `rule` (label.RULE) and `cells` from the preset
(CELL_RULE), its Extrude resolved against the target (Auto -> Black only on
a body, White + black without one). The adapter-only keys (`jo_v`,
`host_xform`, `key`, ...) are left out: the plan never reads them.

`preset_of(apply_preset(spec, p))` equals `p` (tests/server/test_studio_api.py).
"""
from __future__ import annotations

import copy
from typing import Optional

from ..core import form as _F
from ..core import presets as _P
from ..core import settings as _S
from ..core import slabs as _SL

ADAPTER_KEYS = ("jo_v", "black_follows", "rotate_deg", "host_xform", "x_base", "x_ref",
                "x_sketch", "source", "z_sign", "has_body", "key")
LAYOUTS = ("single", "grid", "charuco")


def _print_into(s: dict, n: dict, p: dict, has_body: bool) -> None:
    """What a preset holds, into settings `s` and numbers `n` (mm), nothing
    else: never the target, ids, Origin, Type or size (REF apply_preset)."""
    p = _P.normalise(p)
    t, lb = p["tag"], p["label"]
    s["dictionary"] = t["dictionary"]
    s["mode"] = _F.mode_for(t["mode"], has_body)
    s["op"] = t["op"]
    s["quiet_modules"] = float(t["quiet_modules"])
    s["grow"] = bool(t["grow"])
    s["corner_mark"] = t["corner_mark"]
    s["pin"] = t["pin"]
    s["cells"] = _P.cell_setting(p)
    lab = dict(s.get("label") or {})
    for k in ("on", "content", "text", "place", "row", "side", "scope", "cap_mm", "nozzle_mm"):
        lab[k] = copy.deepcopy(lb[k])
    s["label"] = lab
    n["white_offset"] = float(t["white_offset_mm"])
    n["white_height"] = float(t["white_height_mm"])
    n["black_height"] = float(t["black_height_mm"])
    n["black_offset"] = round(_SL.white_top(s["mode"], n) + float(t["black_step_mm"]), 6)
    n["pin_size"] = float(t["pin_size_mm"])
    n["pin_length"] = float(t["pin_length_mm"])
    n["pin_tol"] = float(t["pin_tol_mm"])


def new_spec(layout: str, target: dict, preset: Optional[dict] = None, marker_id: int = 0,
             name: str = "", key: str = "") -> dict:
    """A fresh tag of `layout` on `target` (a Target dict) under `preset`
    (Default when None): a TagSpec dict for /api/plan."""
    if layout not in LAYOUTS:
        raise ValueError(f"unknown layout {layout!r}: one of {', '.join(LAYOUTS)}")
    s = _S.default_settings()
    for k in ADAPTER_KEYS:
        s.pop(k, None)
    s.update(layout=layout, turn=0, size_auto=True, force=None)
    n = _S.default_numbers("both")
    n.update(marker_id=int(marker_id), size=0.0, square=0.0)
    has_body = bool(target.get("has_body", False))
    _print_into(s, n, preset or _P.default_preset(), has_body)
    s = _F.new_tag_settings(s, has_body, preset=preset)  # origin_v, Extrude Auto, make from the preset (core.form)
    return {"schema": "arucostudio.tagspec/1", "settings": s, "numbers": n,
            "target": copy.deepcopy(target), "name": name, "key": key}


def apply_preset(spec: dict, preset: dict) -> dict:
    """`spec` with `preset`'s print settings (a Preset pick): the layout,
    ids, size, Origin, target and the label's place on the tag are kept."""
    out = copy.deepcopy(spec)
    s = dict(out.get("settings") or {})
    n = dict(out.get("numbers") or {})
    _print_into(s, n, preset, bool((out.get("target") or {}).get("has_body", False)))
    _make_into(s, preset)
    out["settings"], out["numbers"] = s, n
    return out


def _make_into(s: dict, preset: dict) -> None:
    """2026-10-17 (the inkjet presets, CF-4): an inkjet preset picked for a
    tag makes it that preset's sticker -- its make rule, paper thickness
    and page (core.make.new_make), the Perimeter kept -- and a 3D preset
    picked for a sticker makes it 3D printed. A 3D preset on a 3D tag
    leaves `make` as it is (absent stays absent)."""
    from ..core import make as _MK
    kind = _P.kind_of(preset)
    have, _notes = _MK.make_of(s)
    if kind != "sticker" and not have.sticker:
        return
    mk = _MK.new_make(kind, (preset or {}).get("profile"))
    if kind == "sticker":
        if have.sticker:
            mk["perimeter"] = have.perimeter
            if mk.get("rule") == _MK.MAKE_RULE and not have.inset:
                mk.update(margin_mm=have.margin_mm, cut_line=have.cut_line)    # rule 1's own
        s.update(mode="both", op="new", pin="none", grow=False)
        s.pop("trim", None)
    s["make"] = mk


def preset_of(spec: dict, name: str = "") -> dict:
    """A tag's print settings as a preset (core.presets.preset_of)."""
    p = _P.preset_of(spec.get("settings") or {}, spec.get("numbers") or {})
    if name:
        p["name"] = name
    return p
