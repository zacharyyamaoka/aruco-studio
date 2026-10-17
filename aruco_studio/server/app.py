"""The Studio's API: FastAPI on 127.0.0.1:5360 (docs/API.md lists it).

    .venv/Scripts/python -m aruco_studio.server        # serve on 127.0.0.1:5360

It serves `studio/dist/` at `/` when it is built, and allows CORS from the
Vite dev server (127.0.0.1:5361 / localhost:5361). Every file it touches
goes through server/store.py. The open scene lives in memory; New / Open /
Save move it to and from `scenes/`.
"""
from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError

from ..core import autosize as _A
from ..core import board as _B
from ..core import chamfer as _CH
from ..core import dictionary as _D
from ..core import form as _F
from ..core import label as _L
from ..core import numbering as _N
from ..core import presets as _P
from ..core import prusa as _PR
from ..core import slabs as _SL
from ..plan import exports as _X
from ..plan import mesh as _ME
from ..plan import plan_tag
from ..plan import target as _T
from ..plan.fields import form as _form
from ..plan.spec import TagSpec
from ..plan.target import SpecTypeError
from ..scene import Scene, SceneFileError, dumps, loads, renumber
from ..scene import sheet as _sheet
from . import models as M
from . import store as S

VERSION = "0.2.0"
REF_COMMIT = "c8216ff"
PORT = 5360
DEV_ORIGINS = ["http://127.0.0.1:5361", "http://localhost:5361"]
DIST = S.ROOT / "studio" / "dist"

app = FastAPI(title="ArUco Studio", version=VERSION,
              description="Fiducial markers planned outside any CAD program: the TagPlan "
                          "contract, scenes, exports and OpenCV's own check.")
app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"],
                   allow_headers=["*"])

STATE: Dict[str, Any] = {"scene": Scene(name="untitled")}


# ------------------------------------------------------------- errors

def _422(path: str, msg: str):
    loc = ["body"] + [p for p in path.replace("]", "").replace("[", ".").split(".") if p]
    return HTTPException(status_code=422, detail=[{"loc": loc, "msg": msg, "type": "type_error",
                                                   "path": path}])


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    """FastAPI's 422, each error with its key path ("numbers.size")."""
    out = []
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", ())]
        path = ".".join(x for x in loc[1:] if not x.isdigit() or True) if loc[:1] == ["body"] \
            else ".".join(loc)
        out.append({"loc": loc, "msg": e.get("msg"), "type": e.get("type"), "path": path})
    return JSONResponse(status_code=422, content={"detail": out})


def _spec(spec_in) -> TagSpec:
    d = spec_in.plain() if hasattr(spec_in, "plain") else spec_in
    try:
        return TagSpec.from_dict(d)
    except SpecTypeError as exc:
        raise _422(exc.path, exc.message) from None


def _plan_dict(p, mesh: bool = False) -> dict:
    d = p.to_dict()
    if mesh and p.ok:
        d["mesh"] = _ME.mesh(p)
    return d


# ------------------------------------------------------------- reference

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": VERSION, "ref_commit": REF_COMMIT,
            "schemas": {"tagspec": "arucostudio.tagspec/1", "tagplan": "arucostudio.tagplan/1",
                        "scene": "arucostudio.scene/1"},
            "home": str(S.home()), "scenes": str(S.scenes_dir())}


@app.get("/api/dictionaries")
def dictionaries() -> List[dict]:
    out = []
    for n in _D.DICTIONARY_NAMES:
        i = _D.dictionary_info(n)
        out.append({"name": n, "bits": i["bits"], "capacity": i["capacity"],
                    "family": _N.family(n), "modules": i["modules"]})
    return out


@app.get("/api/options")
def options() -> dict:
    """Every choice the inspector offers, with the dialog's words."""
    pairs = lambda ps: [{"value": v, "label": t} for t, v in ps]
    return {"layouts": pairs(_F.LAYOUT_LABELS), "modes": pairs(_F.MODE_LABELS),
            "ops": pairs(_F.OP_LABELS), "pins": pairs(_F.PIN_LABELS),
            "corner_marks": [{"value": v, "label": _CH.CHOICE_LABELS[v]} for v in _CH.CHOICES],
            "turns": [0, 90, 180, 270],
            "label": {"content": pairs(_F.LABEL_CONTENT), "place": pairs(_F.LABEL_PLACE),
                      "row": pairs(_F.LABEL_ROW), "side": pairs(_F.LABEL_SIDE),
                      "scope": pairs(_F.LABEL_SCOPE), "rule": _L.RULE,
                      "nozzle_mm": _L.NOZZLE_MM},
            "trim": pairs(_F.TRIM_LABELS),
            "cells": {"rule": _A.CELL_RULE, "of": list(_A.CELL_OF)},
            "limits": {"height_mm": _SL.LIMIT_MM, "white_min_mm": _SL.WHITE_MIN_MM,
                       "black_min_mm": _SL.BLACK_MIN_MM, "pins": _SL.PIN_LIMITS},
            "dictionaries": [d["name"] for d in dictionaries()]}


@app.get("/api/form")
def form() -> dict:
    return _form()


@app.get("/api/targets")
def targets(thickness_mm: float = 3.0) -> List[dict]:
    return _T.palette(thickness_mm)


# ------------------------------------------------------------- one tag

@app.post("/api/plan", response_model=M.TagPlanOut, response_model_exclude_none=False,
          response_model_by_alias=True)
def plan(spec: M.TagSpecIn, mesh: int = Query(0)) -> dict:
    """TagSpec -> TagPlan. ?mesh=1 fills `mesh` (per body, for the 3D view)."""
    return _plan_dict(plan_tag(_spec(spec)), mesh=bool(mesh))


@app.post("/api/validate", response_model=List[M.IssueOut])
def validate(spec: M.TagSpecIn) -> List[dict]:
    return plan_tag(_spec(spec)).data["warnings"]


@app.post("/api/candidates")
def candidates(req: M.CandidatesIn) -> List[dict]:
    """The ranked Layout list for a target (core.autosize)."""
    t = _T.Target.from_dict(req.target.model_dump())
    cells = _A.cells_of(req.cells)
    kw = dict(dictionary=req.dictionary, quiet_modules=float(req.quiet_modules), cells=cells,
              limit=req.limit)
    if t.loops_mm:
        lays = _A.candidates_on_loops(req.layout, t.loops_m(), **kw)
    else:
        lays = _A.candidates(req.layout, t.w_mm / 1000.0, t.h_mm / 1000.0, **kw)
    return [{"kind": l.kind, "marker_mm": l.marker_m * 1000.0, "square_mm": l.square_m * 1000.0,
             "cols": l.cols, "rows": l.rows, "fill": l.fill, "badges": list(l.badges),
             "notes": list(l.notes), "ok": l.ok} for l in lays]


@app.post("/api/verify")
def verify(req: M.VerifyIn) -> dict:
    """The tag rendered and read by OpenCV (frontal), and its pose 25 deg off."""
    from ..verify.report import verify_plan
    p = plan_tag(_spec(req.spec))
    return verify_plan(p, px_per_mm=float(req.px_per_mm), pose=req.pose)


def png_true_size(png: bytes, px_per_mm: float) -> bytes:
    """A PNG with its pHYs chunk (pixels per metre): it prints at true size."""
    import struct
    import zlib
    ppm = int(round(px_per_mm * 1000.0))
    data = struct.pack(">IIB", ppm, ppm, 1)
    chunk = struct.pack(">I", len(data)) + b"pHYs" + data +         struct.pack(">I", zlib.crc32(b"pHYs" + data) & 0xFFFFFFFF)
    # after IHDR: 8 (signature) + 4 + 4 + 13 + 4
    cut = 8 + 25
    return png[:cut] + chunk + png[cut:]


def _export_tag(fmt: str, p) -> Response:
    if not p.ok:
        raise HTTPException(status_code=400, detail={"errors": p.data["errors"]})
    stem = S.safe_name(f"{p.data.get('key') or 'tag'}-{p.data['marker']['dictionary']}-"
                       f"{p.data['ids'][0]}")
    if fmt == "svg":
        return Response(_X.to_svg(p), media_type="image/svg+xml",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.svg"'})
    if fmt == "json":
        return Response(_X.to_json(p), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.json"'})
    if fmt == "stl":
        return Response(_X.to_stl(p), media_type="model/stl",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.stl"'})
    if fmt == "png":
        import cv2
        from ..verify.render import top_view
        r = top_view(p, px_per_mm=20.0)
        ok, buf = cv2.imencode(".png", r.img)
        return Response(png_true_size(buf.tobytes(), 20.0), media_type="image/png",
                        headers={"Content-Disposition": f'attachment; filename="{stem}.png"'})
    raise HTTPException(status_code=404, detail=f"no export {fmt!r}: svg, png, stl or json")


@app.post("/api/export/{fmt}")
def export_tag(fmt: str, spec: M.TagSpecIn) -> Response:
    """One tag as SVG (1:1 mm), PNG (20 px / mm), STL or plan JSON."""
    return _export_tag(fmt, plan_tag(_spec(spec)))


# ------------------------------------------------------------- presets

def _prusa():
    try:
        return S.prusa_sources()
    except Exception:                              # noqa: BLE001
        return None


@app.get("/api/presets")
def presets() -> dict:
    """Built-in presets (read only: Default and PrusaSlicer's "Aruco"
    profiles) and the user's (their file under the Studio's home)."""
    cat = _P.catalog(S.presets_store(), _prusa())
    return {"items": [{"name": n, "kind": k, "preset": p} for n, p, k in cat["items"]],
            "last": cat["last"], "notes": cat["notes"], "file": str(S.presets_path())}


@app.post("/api/presets")
def preset_save_as(req: M.PresetIn) -> dict:
    st = S.presets_store()
    try:
        got = _P.save_as(req.name, req.preset, st, _prusa())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    st.flush()
    return {"name": got}


@app.put("/api/presets/{name}")
def preset_update(name: str, preset: Dict[str, Any] = Body(...)) -> dict:
    st = S.presets_store()
    try:
        _P.update(name, preset, st, _prusa())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    st.flush()
    return {"name": name}


@app.delete("/api/presets/{name}")
def preset_delete(name: str) -> dict:
    st = S.presets_store()
    try:
        _P.delete(name, st, _prusa())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    st.flush()
    return {"deleted": name}


@app.get("/api/prusa/profiles")
def prusa_profiles() -> dict:
    src = _prusa()
    if src is None:
        return {"dir": None, "profiles": [], "aruco": []}
    return {"dir": str(S.prusa_dir()), "profiles": [p["name"] for p in _PR.user_prints(src)],
            "aruco": [dict(p, describe=_PR.describe(p)) for p in _PR.aruco_profiles(src)]}


@app.get("/api/remembered")
def remembered_get() -> dict:
    from . import remembered as R
    return R.load(str(S.remembered_path()))


@app.put("/api/remembered/{command}")
def remembered_put(command: str, values: Dict[str, Any] = Body(...)) -> dict:
    from . import remembered as R
    R.remember(command, values, path=str(S.remembered_path()))
    return R.recall(command, path=str(S.remembered_path()))


# ------------------------------------------------------------- the scene

def _scene() -> Scene:
    return STATE["scene"]


def _scene_out(plans: bool = False, mesh: bool = False) -> dict:
    sc = _scene()
    d = sc.to_dict()
    if plans:
        ps = sc.plans()
        for t in d["tags"]:
            t["plan"] = _plan_dict(ps[t["name"]], mesh=mesh)
    return d


@app.get("/api/scene")
def scene_get(plans: int = Query(0), mesh: int = Query(0)) -> dict:
    """The open scene; ?plans=1 adds each tag's TagPlan (?mesh=1 its mesh)."""
    return _scene_out(bool(plans), bool(mesh))


@app.put("/api/scene")
def scene_put(doc: Dict[str, Any] = Body(...)) -> dict:
    try:
        STATE["scene"] = loads(json.dumps(doc))
    except SceneFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _scene_out()


@app.post("/api/scene/new")
def scene_new(req: M.SceneNewIn) -> dict:
    STATE["scene"] = Scene(name=req.name)
    return _scene_out()


@app.post("/api/scene/tags")
def scene_add(req: M.SceneTagIn) -> dict:
    t = _scene().add(_spec(req.spec), float(req.x_mm), float(req.y_mm), float(req.rotation_deg),
                     name=req.name, locked=req.locked)
    out = t.to_dict()
    out["plan"] = _plan_dict(plan_tag(t.spec))
    return out


@app.patch("/api/scene/tags/{name}")
def scene_patch(name: str, req: M.SceneTagPatch) -> dict:
    sc = _scene()
    try:
        t = sc.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no tag {name!r}") from None
    if req.locked is not None:
        t.locked = req.locked
    if req.hidden is not None:
        t.hidden = req.hidden
    sc.move(name, req.x_mm, req.y_mm, req.rotation_deg)
    issues = []
    if req.settings is not None or req.numbers is not None or req.target is not None \
            or req.key is not None:
        try:
            issues = sc.edit(name, settings=req.settings, numbers=req.numbers,
                             target=req.target.model_dump() if req.target else None, key=req.key)
        except SpecTypeError as exc:
            raise _422(exc.path, exc.message) from None
    if issues:
        return JSONResponse(status_code=409, content={"issues": [i.to_dict() for i in issues]})
    if req.new_name is not None and req.new_name != name:
        try:
            sc.rename(name, req.new_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        name = req.new_name
    t = sc.get(name)
    out = t.to_dict()
    out["plan"] = _plan_dict(plan_tag(t.spec))
    return out


@app.delete("/api/scene/tags/{name}")
def scene_delete(name: str) -> dict:
    try:
        _scene().delete(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no tag {name!r}") from None
    return {"deleted": name}


@app.post("/api/scene/tags/{name}/duplicate")
def scene_duplicate(name: str, dx_mm: float = 10.0, dy_mm: float = 0.0) -> dict:
    try:
        t = _scene().duplicate(name, dx_mm, dy_mm)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no tag {name!r}") from None
    return t.to_dict()


@app.put("/api/scene/overrides/{name}")
def scene_override(name: str, req: M.OverrideIn) -> dict:
    sc = _scene()
    if name not in sc.names():
        raise HTTPException(status_code=404, detail=f"no tag {name!r}")
    if req.id is None:
        sc.overrides.pop(name, None)
    else:
        sc.overrides[name] = int(req.id)
    return {"overrides": sc.overrides}


@app.post("/api/scene/renumber")
def scene_renumber() -> dict:
    """Unique ids across the scene (core.numbering through the scene's ledger)."""
    return renumber(_scene())


@app.get("/api/scenes")
def scenes() -> List[dict]:
    return S.list_scenes()


@app.post("/api/scene/save")
def scene_save(req: Optional[M.SceneFileIn] = None) -> dict:
    sc = _scene()
    if req is not None and req.name:
        sc.name = req.name
    p = S.write_atomic(S.scene_path(sc.name), dumps(sc))
    return {"saved": str(p), "name": sc.name}


@app.post("/api/scene/open")
def scene_open(req: M.SceneFileIn) -> dict:
    p = S.scene_path(req.name)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no scene {req.name!r} in {S.scenes_dir()}")
    try:
        STATE["scene"] = loads(p.read_text(encoding="utf-8"))
    except SceneFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return _scene_out()


@app.post("/api/scene/verify")
def scene_verify(px_per_mm: float = 10.0) -> dict:
    from ..verify.report import verify_scene
    rep = verify_scene(_scene(), px_per_mm=px_per_mm)
    rep.pop("rows", None)
    return rep


@app.post("/api/scene/export/{fmt}")
def scene_export(fmt: str, save: int = Query(1)) -> dict:
    """The scene as a 1:1 sheet (svg), its file (json), or every tag's
    plan / STL; written under <home>/exports/<scene>/ (save=1)."""
    sc = _scene()
    out_dir = S.exports_dir(sc.name)
    files = []
    if fmt == "svg":
        files.append(("sheet.svg", _sheet.to_svg(sc).encode("utf-8")))
    elif fmt == "json":
        files.append((S.safe_name(sc.name) + S.SCENE_EXT, dumps(sc).encode("utf-8")))
    elif fmt in ("stl", "plan"):
        for t in sc.tags:
            p = plan_tag(t.spec)
            if not p.ok:
                continue
            if fmt == "stl":
                files.append((f"{S.safe_name(t.name)}.stl", _X.to_stl(p)))
            else:
                files.append((f"{S.safe_name(t.name)}.json", _X.to_json(p).encode("utf-8")))
    elif fmt == "png":
        import cv2
        from ..verify.scene_check import scene_raster
        r = scene_raster(sc, px_per_mm=10.0)
        files.append(("sheet.png", png_true_size(cv2.imencode(".png", r.img)[1].tobytes(), 10.0)))
    else:
        raise HTTPException(status_code=404, detail=f"no export {fmt!r}: svg, png, json, stl, plan")
    written = []
    if save:
        for fn, data in files:
            written.append(str(S.write_atomic(out_dir / fn, data, binary=True)))
    return {"dir": str(out_dir), "files": written or [fn for fn, _ in files],
            "inline": {fn: base64.b64encode(data).decode("ascii") for fn, data in files}
            if not save else None}


# ------------------------------------------------------------- the web app

if DIST.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="studio")
