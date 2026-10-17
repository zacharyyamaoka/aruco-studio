"""A scene's print bundle: ONE action for a mixed scene (design notes
manufacturing_intent.md 5.3 and M6_stickers_profiles_print.md f).

Standard library only, and no file I/O: `print_bundle` returns every file
as bytes under its path inside `exports/<scene>/`; the server writes them.

| Writes | From |
|---|---|
| `sheet.pdf`, `sheet.svg`, `sheet.json` | every visible sticker tag (plus the 3D tags as paper proofs with `proofs`): the plan-driven sheet (core.sheet.layout_stickers) |
| `images/<dict>_<id>.png / .svg` | one per distinct sticker (a board: `<dict>_<first>-<last>`) |
| `print3d/stl/<tag>__tile.stl`, `__cells.stl`, `__other.stl` | every visible 3D tag's bodies (plan/mesh), mm, the pattern frame |
| `print3d/parts.json` | `bam_aruco_print3d/1`: per tag its bodies with `role` tile / cells and its frame -- what `core.beds.load_parts` reads |
| `print3d/aruco_tags.3mf`, `print3d/beds/`, `print3d/parts/` | `core.beds.layout_beds` + `render_beds` (MK4 250 x 210 by default; the cells on the black slot) |
| `markers.json` | every tag: name, made by, dictionary, ids, its OpenCV frame in the scene, which file it went to |

The ledger: every tag exported (either kind) has its ids marked printed, so
a printed id never moves (`ledger` in the result; the caller stores it).
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from ..core import beds as _BD
from ..core import board as _B
from ..core import dictionary as _D
from ..core import numbering as _N
from ..plan import mesh as _ME
from . import sheet as _SS
from .ids import instance
from .model import Scene, mat_mul

ROLE_OF = {"white": "tile", "pattern": "cells", "body": "other"}
MARKERS_SCHEMA = "arucostudio.markers/1"


def _slug(name: str) -> str:
    return _BD.slug(name)


def _json(d) -> bytes:
    return (json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def images(items) -> Dict[str, bytes]:
    """images/<dict>_<id>.png / .svg per distinct sticker (a board: its first
    to last id)."""
    out: Dict[str, bytes] = {}
    for it in items:
        if it.layout == "single":
            stem = f"images/{it.dictionary}_{it.marker_id}"
            if stem + ".png" in out:
                continue
            out[stem + ".png"] = _D.marker_png(it.dictionary, it.marker_id, module_px=20,
                                               quiet_modules=it.quiet_modules)
            out[stem + ".svg"] = _D.marker_svg(it.dictionary, it.marker_id,
                                               quiet_modules=it.quiet_modules).encode("utf-8")
            continue
        ids = it.ids or [it.marker_id]
        stem = f"images/{it.dictionary}_{ids[0]}-{ids[-1]}"
        if stem + ".png" in out:
            continue
        spec = _SS._SH.board_spec(it)
        info = _D.dictionary_info(it.dictionary)
        quiet_m = it.quiet_modules * it.marker_length_m / info["modules"]
        out[stem + ".png"] = _B.board_png(spec, quiet_m=quiet_m)
        out[stem + ".svg"] = _B.board_svg(spec, quiet_m=quiet_m).encode("utf-8")
    return out


def print3d(scene: Scene, plans: dict, tags, bed: Optional["_BD.BedSettings"] = None,
            profile=None) -> Dict[str, bytes]:
    """The 3D tags' files under print3d/: STLs, parts.json, the beds."""
    files: Dict[str, bytes] = {}
    parts = []
    for t in tags:
        d = plans[t.name].data
        joined = any(c.get("part") == "tile" and c.get("op") == "join"
                     for c in d.get("combines") or [])
        # the body under the tag is the user's part: printed only when the
        # tile is joined to it (a New-body tag prints on its own)
        meshes = [m for m in _ME.mesh(d) if m["what"] != "body" or joined]
        bodies = []
        seen = {}
        for m in meshes:
            role = ROLE_OF.get(m["what"], "other")
            k = seen.get(role, 0)
            seen[role] = k + 1
            rel = f"print3d/stl/{_slug(t.name)}__{role}{'' if not k else '_%d' % (k + 1)}.stl"
            files[rel] = _ME.stl(d, what=[m["what"]], name=f"{t.name} {role}")
            bodies.append({"name": f"{t.name} {role}", "role": role,
                           "colour": "black" if role == "cells" else "white", "stl": rel})
        top = float(d["frames"]["surface_mm"])
        parts.append({"component": t.name, "copies": 1, "variant": False,
                      "tags": [{"key": t.name, "origin": [0.0, 0.0, top],
                                "x_axis": [1.0, 0.0, 0.0], "y_axis": [0.0, 1.0, 0.0],
                                "z_axis": [0.0, 0.0, 1.0], "units": "mm",
                                "spec": d["marker"]}],
                      "bodies": bodies})
    manifest = {"schema": _BD.MANIFEST_SCHEMA, "design": scene.name, "stl_units": "mm",
                "frame_units": "mm", "parts": parts}
    files["print3d/parts.json"] = _json(manifest)
    if not parts:
        return files
    st = bed or _BD.BedSettings()
    layout = _BD.layout_beds(manifest, files.__getitem__, st)
    for rel, data in _BD.render_beds(layout, profile).items():
        files["print3d/" + rel] = data
    if "print3d/aruco_tags.3mf" not in files:
        # no PrusaSlicer profile: the project without a config
        for rel, data in _BD.render_projects(layout, None).items():
            files["print3d/" + rel] = data
    return files


def frame_in_scene(t, plan_d: dict) -> List[float]:
    """The tag's OpenCV frame in the scene (mm, row-major 4x4)."""
    m = mat_mul(t.pose, plan_d["frames"]["pattern_in_target"])
    return [round(v, 9) + 0.0 for v in mat_mul(m, plan_d["frames"]["opencv"])]


def print_bundle(scene: Scene, plans: Optional[dict] = None, page: str = "letter",
                 landscape: bool = False, margin_mm: float = 10.0, mode: str = "spaced",
                 proofs: bool = False, bed_w_mm: float = None, bed_d_mm: float = None,
                 black_slot: int = 2, white_slot: int = 1, profile=None, when: str = "",
                 date: Optional[str] = None, sheet_only: bool = False) -> dict:
    """-> {"files": {relpath: bytes}, "report": {...}, "ledger": dict}.
    `sheet_only`: the sticker sheet's files (and markers.json) only, no 3D
    parts (the Sticker sheet dialog's Export; the parts are Send's)."""
    plans = plans if plans is not None else scene.plans()
    files: Dict[str, bytes] = {}
    stickers = [t for t in scene.tags if not t.hidden and plans[t.name].ok
                and plans[t.name].data.get("made_by") == "sticker"]
    solid = [t for t in scene.tags if not t.hidden and plans[t.name].ok
             and plans[t.name].data.get("made_by") != "sticker"]
    report = {"stickers": len(stickers), "parts": len(solid), "rejected": [], "pages": 0,
              "beds": 0, "rows": []}
    sheet_keys = set()
    if stickers or (proofs and solid):
        got = _SS.sticker_files(scene, plans, page, landscape, mode, margin_mm, proofs, date)
        lay = got.pop("layout")
        files.update(got)
        files.update(images([p.item for p in lay.placed]))
        sheet_keys = {p.item.key for p in lay.placed}
        report["pages"] = lay.page_count
        report["rejected"] = [{"tag": r.item.key, "reason": r.reason} for r in lay.rejected]
        report["rows"].append(f"{len(sheet_keys)} sticker{'s' if len(sheet_keys) != 1 else ''} "
                              f"-> sheet.pdf ({lay.page_count} page"
                              f"{'s' if lay.page_count != 1 else ''}, {page.upper() if page == 'a4' else page.capitalize()})")
    solid_keys = set()
    if solid and not sheet_only:
        bed = _BD.BedSettings(tile_extruder=int(white_slot), cells_extruder=int(black_slot))
        if bed_w_mm:
            bed.bed_w_mm = float(bed_w_mm)
        if bed_d_mm:
            bed.bed_d_mm = float(bed_d_mm)
        files.update(print3d(scene, plans, solid, bed, profile))
        solid_keys = {t.name for t in solid}
        nb = len([k for k in files if k.startswith("print3d/beds/bed_") and k.endswith(".3mf")])
        report["beds"] = nb
        report["rows"].append(f"{len(solid)} part{'s' if len(solid) != 1 else ''} -> "
                              f"aruco_tags.3mf ({nb} bed{'s' if nb != 1 else ''})")
    led = _N.Ledger.from_any(scene.ledger) if scene.ledger else _N.Ledger()
    rows = []
    for t in scene.tags:
        p = plans[t.name]
        d = p.data
        went = ("sheet.pdf" if t.name in sheet_keys else
                "print3d/aruco_tags.3mf" if t.name in solid_keys else None)
        row = {"name": t.name, "made_by": d.get("made_by") or "print3d",
               "dictionary": (d.get("marker") or {}).get("dictionary"),
               "ids": list(d.get("ids") or []), "file": went, "hidden": bool(t.hidden),
               "frame_mm": frame_in_scene(t, d) if p.ok else None}
        rows.append(row)
        if went and d.get("ids"):
            led.mark_printed(_N.family(d["marker"]["dictionary"]), d["ids"], led.seq,
                             instance(t.name))
    if when:
        led.updated = when
    files["markers.json"] = _json({"schema": MARKERS_SCHEMA, "scene": scene.name,
                                   "units": "mm", "tags": rows})
    report["files"] = sorted(files)
    return {"files": files, "report": report, "ledger": led.to_dict()}
