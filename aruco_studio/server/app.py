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
from collections import OrderedDict
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
from ..core import origin as _O
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
from ..scene import Scene, SceneFileError, number_one, renumber, set_first_id
from ..scene import checks as _checks
from ..scene import sheet as _sheet
from . import library as _LIB
from . import models as M
from . import newtag as _NEW
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


def _plan_dict(p, mesh: bool = False, top: bool = False) -> dict:
    d = p.to_dict()
    if mesh and p.ok:
        d["mesh"] = _ME.mesh(p)
    if top and p.ok:
        d["top"] = _ME.top(p)          # {colour: polygons}: what is seen from above
    return d


# ------------------------------------------------------------- the plan cache
#
# plan_tag is a pure function of the TagSpec, so the scene's plans (and their
# top views and meshes) are kept by the spec's canonical JSON: a change
# re-plans only the tags it changed (audit F14). Never stored in a file.

CACHE_MAX = 1024
_CACHE: "OrderedDict[str, dict]" = OrderedDict()


def _key(spec: TagSpec) -> str:
    return json.dumps(spec.to_dict(), sort_keys=True, separators=(",", ":"), default=str)


def _entry(spec: TagSpec) -> dict:
    k = _key(spec)
    e = _CACHE.get(k)
    if e is None:
        e = {"plan": plan_tag(spec)}
        _CACHE[k] = e
        while len(_CACHE) > CACHE_MAX:
            _CACHE.popitem(last=False)
    else:
        _CACHE.move_to_end(k)
    return e


def cached_plan(spec: TagSpec):
    """plan_tag(spec), kept by the spec's canonical JSON."""
    return _entry(spec)["plan"]


def cached_plan_dict(spec: TagSpec, mesh: bool = False, top: bool = False) -> dict:
    """_plan_dict of the cached plan; its JSON, top view and mesh are kept too."""
    e = _entry(spec)
    p = e["plan"]
    if "dict" not in e:
        e["dict"] = p.to_dict()
    d = dict(e["dict"])
    if mesh and p.ok:
        if "mesh" not in e:
            e["mesh"] = _ME.mesh(p)
        d["mesh"] = e["mesh"]
    if top and p.ok:
        if "top" not in e:
            e["top"] = _ME.top(p)
        d["top"] = e["top"]
    return d


def _scene_plans(sc: Scene) -> dict:
    return {t.name: cached_plan(t.spec) for t in sc.tags}


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
            # the Origin row: REF's words per layout, in the dialog's clockwise order
            "origin": {lay: [{"value": t, "label": _O.label(lay, t)} for t in _O.TURNS_CW]
                       for lay in ("single", "grid", "charuco")},
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
def plan(spec: M.TagSpecIn, mesh: int = Query(0), top: int = Query(0)) -> dict:
    """TagSpec -> TagPlan. ?mesh=1 fills `mesh` (per body, for the 3D view);
    ?top=1 adds `top` ({colour: polygons}, the top view the 2D view fills)."""
    return _plan_dict(plan_tag(_spec(spec)), mesh=bool(mesh), top=bool(top))


@app.post("/api/validate", response_model=List[M.IssueOut])
def validate(spec: M.TagSpecIn) -> List[dict]:
    return plan_tag(_spec(spec)).data["warnings"]


@app.post("/api/auto_check")
def auto_check(spec: M.TagSpecIn) -> dict:
    """Auto size at creation (plan.auto.auto_still_fits, REF _check_auto):
    a tag stored with Auto and a number (made before 2026-10-13) shows Auto
    ON only if Auto builds that same tag; else `note` says what it would build."""
    from ..plan.auto import auto_still_fits
    sp = _spec(spec)
    n = sp.numbers or {}
    size = float(n.get("size") or 0.0)
    if not (sp.settings or {}).get("size_auto", True) or size <= 0.0:
        return {"auto": size <= 0.0, "note": ""}
    keep, note = auto_still_fits(sp, size, float(n.get("square") or 0.0))
    return {"auto": keep, "note": note}


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
    rep = verify_plan(p, px_per_mm=float(req.px_per_mm), pose=req.pose)
    if req.image and p.ok:
        import cv2
        from ..verify.render import top_view
        r = top_view(p, px_per_mm=float(req.px_per_mm))
        rep["image_png"] = base64.b64encode(cv2.imencode(".png", r.img)[1].tobytes()).decode(
            "ascii")
    return rep


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
def presets(made_by: Optional[str] = None) -> dict:
    """Built-in presets (read only: Default, PrusaSlicer's "Aruco" profiles
    and the sticker printers) and the user's (their file under the Studio's
    home). Each says what it makes (`made_by`: its profile's kind, M6a);
    `collections`: 3D printers and Sticker printers; `?made_by=` keeps one."""
    cat = _P.catalog_all(S.presets_store(), _prusa())
    items = [(n, p, k) for n, p, k in cat["items"]
             if made_by in (None, "") or _P.kind_of(p) == made_by]
    return {"items": [{"name": n, "kind": k, "made_by": _P.kind_of(p), "preset": p}
                      for n, p, k in items],
            "collections": _P.collections(items), "last": cat["last"], "notes": cat["notes"],
            "file": str(S.presets_path())}


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
    _LIB.forget_recent(name)
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
#
# M8a: the open scene is a design document (server/design_api.py: the file,
# its watcher, /api/design, /api/events). These routes keep their answers;
# each change goes through the Scene API on the compiled scene, is written
# back into the document and committed: the file is written when there is one.

from . import design_api as _DA  # noqa: E402

app.include_router(_DA.router)
app.router.on_shutdown.append(_DA.shutdown)


def _scene() -> Scene:
    return _DA.D.current()


def _scene_out(plans: bool = False, mesh: bool = False, top: bool = False) -> dict:
    return _DA.scene_dict(_scene(), plans=plans, mesh=mesh, top=top, plan_dict=cached_plan_dict)


def _conflict(fn):
    """Run a change; the design's 409s (file not parseable / missing /
    changed under us) as answers."""
    try:
        return fn()
    except _DA.Conflict as exc:
        return _DA.conflict_response(exc)


def _tag_out(name: str, plan: bool = True) -> dict:
    t = _scene().get(name)
    out = _DA.tag_dict(t)
    out["plan"] = cached_plan_dict(t.spec) if plan else None
    return out


@app.get("/api/scene")
def scene_get(plans: int = Query(0), mesh: int = Query(0), top: int = Query(0)):
    """The open scene, compiled from the design file (the `/1` shape: tags
    with their TagSpec); ?plans=1 adds each tag's TagPlan (?mesh=1 its mesh,
    ?top=1 its top view). Written straight out (audit F14)."""
    body = json.dumps(_scene_out(bool(plans), bool(mesh), bool(top)), separators=(",", ":"),
                      allow_nan=False)
    return Response(body, media_type="application/json",
                    headers={"X-Scene-Revision": str(_DA.D.revision),
                             "X-Design-State": _DA.D.state})


@app.put("/api/scene")
def scene_put(doc: Dict[str, Any] = Body(...)):
    """A whole scene: a design document (`/2`), or a compiled scene (the
    `/1` shape GET gives, e.g. the Studio's Undo), written back onto the
    open design."""
    doc = json.loads(json.dumps(doc))
    try:
        if doc.get("schema") == "arucostudio.scene/1" and "sketches" not in doc:
            sc = _DA.parse_v1(doc)
            return _conflict(lambda: (_DA.replace_scene(sc), _scene_out())[1])
        d = _DA.migrate(doc)
    except SceneFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _DA.D.current()
    return _conflict(lambda: (_DA.D.commit(d), _scene_out())[1])


@app.post("/api/scene/new")
def scene_new(req: M.SceneNewIn) -> dict:
    """An empty design in memory (Save or Save as gives it a file)."""
    _DA.new_design(req.name)
    return _scene_out()


@app.post("/api/scene/tags")
def scene_add(req: M.SceneTagIn):
    """A tag: a sketch at (x, y, rotation) holding its target's shape, an
    Extrude when it has a body, an ArUco Extrude with its exact settings."""
    spec = _spec(req.spec)

    def fn(doc, sc):
        t = sc.add(spec, float(req.x_mm), float(req.y_mm), float(req.rotation_deg),
                   name=req.name, locked=req.locked)
        if req.number:
            number_one(sc, t.name, _scene_plans(sc))
        return t.name
    return _conflict(lambda: _tag_out(_DA.mutate(fn)[0]))


@app.patch("/api/scene/tags/{name}")
def scene_patch(name: str, req: M.SceneTagPatch):
    """A tag's place, flags, settings / numbers (written exactly into its
    feature), target or name."""
    if name not in _scene().names():
        raise HTTPException(status_code=404, detail=f"no tag {name!r}")

    def fn(doc, sc):
        t = sc.get(name)
        if req.locked is not None:
            t.locked = req.locked
        if req.hidden is not None:
            t.hidden = req.hidden
        sc.move(name, req.x_mm, req.y_mm, req.rotation_deg)
        if req.settings is not None or req.numbers is not None or req.target is not None \
                or req.key is not None:
            try:
                issues = sc.edit(name, settings=req.settings, numbers=req.numbers,
                                 target=req.target.model_dump() if req.target else None,
                                 key=req.key)
            except SpecTypeError as exc:
                raise _422(exc.path, exc.message) from None
            if issues:
                return JSONResponse(status_code=409,
                                    content={"issues": [i.to_dict() for i in issues]})
        if req.new_name is not None and req.new_name != name:
            try:
                sc.rename(name, req.new_name)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
            ids = _DA._DS.all_ids(doc)
            if req.new_name in ids and ids[req.new_name] != "tag":
                raise HTTPException(status_code=400, detail=(
                    f"the name {req.new_name!r} is taken by a {ids[req.new_name]} of the file"))
            return req.new_name
        return name

    def run():
        out, _sc = _DA.mutate(fn)
        if isinstance(out, JSONResponse):
            return out
        return _tag_out(out)
    return _conflict(run)


@app.delete("/api/scene/tags/{name}")
def scene_delete(name: str):
    if name not in _scene().names():
        raise HTTPException(status_code=404, detail=f"no tag {name!r}")
    return _conflict(lambda: (_DA.mutate(lambda doc, sc: sc.delete(name)), {"deleted": name})[1])


@app.post("/api/scene/tags/{name}/duplicate")
def scene_duplicate(name: str, dx_mm: float = 10.0, dy_mm: float = 0.0,
                    number: int = Query(1)):
    """A copy, `number`=1 (default): numbered at once with the next free ids
    of its family (a copy of a printed tag is a new tag to print)."""
    if name not in _scene().names():
        raise HTTPException(status_code=404, detail=f"no tag {name!r}")

    def fn(doc, sc):
        t = sc.duplicate(name, dx_mm, dy_mm)
        if number:
            number_one(sc, t.name, _scene_plans(sc))
        return t.name
    return _conflict(lambda: _tag_out(_DA.mutate(fn)[0], plan=False))


@app.put("/api/scene/overrides/{name}")
def scene_override(name: str, req: M.OverrideIn):
    """The IDs table's First field: checked against the tag's dictionary and
    its marker count, kept as the override and used at once (the tag's
    marker_id); a bad one is a 409 with an Issue on "override". id null:
    back to auto."""
    if name not in _scene().names():
        raise HTTPException(status_code=404, detail=f"no tag {name!r}")

    def fn(doc, sc):
        issues = set_first_id(sc, name, req.id)
        if issues:
            return JSONResponse(status_code=409,
                                content={"issues": [i.to_dict() for i in issues]})
        return None

    def run():
        out, sc = _DA.mutate(fn)
        if isinstance(out, JSONResponse):
            return out
        return {"overrides": sc.overrides, "tag": name,
                "ids": cached_plan(sc.get(name).spec).data["ids"]}
    return _conflict(run)


@app.post("/api/scene/renumber")
def scene_renumber():
    """Unique ids across the scene (core.numbering through the scene's ledger)."""
    return _conflict(lambda: _DA.mutate(lambda doc, sc: renumber(sc))[0])


@app.get("/api/scenes")
def scenes() -> List[dict]:
    return S.list_scenes()


@app.post("/api/scene/save")
def scene_save(req: Optional[M.SceneFileIn] = None):
    """The design written to scenes/<name>.arucostudio.json, which the
    server then follows (every later change writes it)."""
    D = _DA.D
    with D.lock:
        sc = _scene()
        name = req.name if req is not None and req.name else sc.name
        if name != sc.name:
            doc = copy.deepcopy(D.doc)
            doc["name"] = name
            D._set_doc(doc, None)
        p = S.scene_path(name)
        D.save_as(p)
    return {"saved": str(p), "name": name}


@app.post("/api/scene/open")
def scene_open(req: M.SceneFileIn):
    p = S.scene_path(req.name)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no scene {req.name!r} in {S.scenes_dir()}")
    try:
        _DA.D.open(p)
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
def scene_export(fmt: str, save: int = Query(1), inline: int = Query(0)) -> dict:
    """The scene as a 1:1 sheet (svg, png), a PDF sticker sheet (pdf: REF's
    print sheet), its design file (json), or every tag's plan / STL; written
    under <home>/exports/<scene>/ (save=1)."""
    sc = _scene()
    out_dir = S.exports_dir(sc.name)
    files = []
    if fmt == "svg":
        files.append(("sheet.svg", _sheet.to_svg(sc).encode("utf-8")))
    elif fmt == "json":
        files.append((S.safe_name(sc.name) + S.SCENE_EXT, _DA.D.text.encode("utf-8")))
    elif fmt in ("stl", "plan"):
        for t in sc.tags:
            p = plan_tag(t.spec)
            if not p.ok:
                continue
            if fmt == "stl":
                files.append((f"{S.safe_name(t.name)}.stl", _X.to_stl(p)))
            else:
                files.append((f"{S.safe_name(t.name)}.json", _X.to_json(p).encode("utf-8")))
    elif fmt == "pdf":
        files.append(("sheet.pdf", _sheet.to_pdf(sc)))
    elif fmt == "png":
        import cv2
        from ..verify.scene_check import scene_raster
        r = scene_raster(sc, px_per_mm=10.0)
        files.append(("sheet.png", png_true_size(cv2.imencode(".png", r.img)[1].tobytes(), 10.0)))
    else:
        raise HTTPException(status_code=404,
                            detail=f"no export {fmt!r}: svg, png, pdf, json, stl, plan")
    written = []
    if save:
        for fn, data in files:
            written.append(str(S.write_atomic(out_dir / fn, data, binary=True)))
    return {"dir": str(out_dir), "files": written or [fn for fn, _ in files],
            "inline": {fn: base64.b64encode(data).decode("ascii") for fn, data in files}
            if (inline or not save) else None}


# ------------------------------------------------------------- the Studio (M3)

@app.post("/api/new")
def new_tag(req: M.NewTagIn) -> dict:
    """A fresh tag's TagSpec: `layout` on a palette target (`target_key`,
    `thickness_mm`) or a typed `target`, under a preset (by name)."""
    if req.target is not None:
        tgt = M.TagSpecIn(target=req.target).plain()["target"]
    else:
        key = req.target_key or "box40"
        pal = {x["key"]: x["target"] for x in _T.palette(float(req.thickness_mm))}
        if key not in pal:
            raise HTTPException(status_code=404, detail=f"no target {key!r}: {', '.join(pal)}")
        tgt = pal[key]
    preset = None
    if req.preset:
        preset, _kind = _P.find(_P.catalog_all(S.presets_store(), _prusa()), req.preset)
        if preset is None:
            raise HTTPException(status_code=404, detail=f"no preset {req.preset!r}")
    sp = _NEW.new_spec(req.layout, tgt, preset, marker_id=req.marker_id, name=req.name,
                       key=req.key)
    # M6a: the preset is the machine -- its kind says how the tag is made
    # (`made_by` overrides it, for scripts); core.form keeps the rule
    sp["settings"] = _F.new_tag_settings(sp["settings"], bool(tgt.get("has_body", False)),
                                         preset=preset or _P.default_preset(),
                                         made_by=req.made_by)
    return sp


@app.post("/api/target")
def target_make(req: M.TargetMakeIn) -> dict:
    """The target editor: a box (w x h), a disc (r) or a palette face
    (`key`), round holes (x, y, diameter), a thickness (0 = no body), as a
    Target. M8a: made as a design shape (a `rect`, a `circle`, the face's
    `loops`, with `circle` holes) and compiled as the design file compiles
    a tag on its top (plan/shapes.py: circles stroked at the chord
    tolerance), so the editor and a typed file give the same Target."""
    from ..plan import shapes as _SHP
    th = float(req.thickness_mm)
    for k, (_x, _y, d) in enumerate(req.holes):
        if float(d) <= 0:
            raise _422("holes", "a hole's diameter must be > 0")
    holes = [{"circle": float(d), "at": [float(x), float(y)]} for x, y, d in req.holes]
    if req.shape == "face":
        try:
            f = _T.from_face(req.key or "", th)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"no target {req.key!r}") from None
        if not holes:
            return f.to_dict()
        shape = {"loops": [[list(p) for p in lp] for lp in f.outline_mm()], "holes": holes,
                 "name": f.name}
    elif req.shape == "disc":
        if req.r_mm <= 0:
            raise _422("r_mm", "the disc's radius must be > 0")
        shape = {"circle": 2.0 * float(req.r_mm), "holes": holes,
                 "name": f"Disc ⌀{2 * req.r_mm:g}"}
    else:
        if req.w_mm <= 0 or req.h_mm <= 0:
            raise _422("w_mm" if req.w_mm <= 0 else "h_mm", "the box's sides must be > 0")
        shape = {"rect": [float(req.w_mm), float(req.h_mm)], "holes": holes,
                 "name": f"Box {req.w_mm:g} x {req.h_mm:g}"}
    if not shape["holes"]:
        shape.pop("holes")
    try:
        t = _SHP.extruded_top(shape, th)
    except _SHP.ShapeError as exc:
        raise _422(exc.path or "shape", exc.message) from None
    return t.to_dict()


@app.post("/api/preset/apply")
def preset_apply(req: M.PresetApplyIn) -> dict:
    """`spec` with a preset's print settings (by `name`, or a `preset`)."""
    p = req.preset
    if p is None:
        p, _kind = _P.find(_P.catalog_all(S.presets_store(), _prusa()), req.name)
        if p is None:
            raise HTTPException(status_code=404, detail=f"no preset {req.name!r}")
    _spec(req.spec)
    return _NEW.apply_preset(req.spec.plain(), p)


@app.post("/api/preset/of")
def preset_of(req: M.PresetOfIn) -> dict:
    """A tag's print settings as a preset, and the catalog preset it equals."""
    _spec(req.spec)
    p = _NEW.preset_of(req.spec.plain(), req.name)
    match = None
    for n, cp, _k in _P.catalog_all(S.presets_store(), _prusa())["items"]:
        if _P.same_print(p, cp):
            match = n
            break
    return {"preset": p, "matches": match}


def _nodes():
    return [(t.name, _NEW.preset_of(t.spec.to_dict())) for t in _scene().tags]


@app.get("/api/library")
def library(tag: Optional[str] = None, selected: Optional[str] = None) -> dict:
    """The preset Library's state (REF aruco_preset_library.Library.state):
    collections, cards with thumbs, the Edit form. `tag`: the scene tag the
    Library opened for (its print settings are the dialog's)."""
    dialog = None
    if tag:
        try:
            dialog = _NEW.preset_of(_scene().get(tag).spec.to_dict())
        except KeyError:
            raise HTTPException(status_code=404, detail=f"no tag {tag!r}") from None
    return _LIB.state(_nodes(), dialog, selected)


@app.post("/api/library/select")
def library_select(req: M.LibraryCardIn) -> dict:
    """Select a card: {name, preset} to apply (a PrusaSlicer profile is
    imported as one of yours first)."""
    try:
        name, p = _LIB.select(req.id, _nodes())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no preset card {req.id!r}") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"name": name, "preset": p}


@app.post("/api/library/save")
def library_save(req: M.LibrarySaveIn) -> dict:
    """Edit -> Save of one of your presets (its fields by path; a new name renames)."""
    try:
        got = _LIB.save_edit(req.id, req.name, req.values, _nodes())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no preset card {req.id!r}") from None
    except _LIB.EditError as exc:
        raise HTTPException(status_code=422, detail=[
            {"loc": ["body", "values", e["path"]], "msg": e["msg"], "type": "value_error",
             "path": e["path"]} for e in exc.errors]) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"name": got}


@app.get("/api/library/recent")
def library_recent() -> dict:
    return {"recent": _LIB.recent()}


@app.post("/api/library/recent")
def library_recent_add(req: M.RecentIn) -> dict:
    return {"recent": _LIB.add_recent(req.name)}


# ------------------------------------------------------------- the web app

if DIST.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="studio")

from . import sheet_api  # noqa: E402,F401  (M6a: the sticker sheet routes)
from . import prusa_api  # noqa: E402,F401  (M8c: PrusaSlicer printers, Send, the folder's watcher)
