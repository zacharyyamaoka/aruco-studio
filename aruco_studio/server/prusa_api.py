"""PrusaSlicer over HTTP (M8c; docs/API_prusa.md): the physical printers,
Send to PrusaSlicer, the tags a changed profile left behind.

| Route | Gives |
|---|---|
| `GET /api/prusa/printers?system=0` | `{dir, found, printers: [{name, technology, host_kind, presets, preset, printer: {preset, source, nozzle_mm, model, variant, bed_mm, ...}, prints: [{name, fits, line_mm, layer_mm, first_layer_mm, nozzle_mm, aruco, user, current}], current, current_print}], current: {physical, printer, print}, notes, revision}`; `system=1` lists the bundles' print presets that fit too |
| `POST /api/scene/send/prusaslicer` | `{printer, print, filament, white_slot, black_slot, open, bed_w_mm, bed_d_mm, margin_mm, spacing_mm}` -> `{project, parts, beds, skipped, rejected, warnings, opened, printer, print, filament}`: the 3MF project (scene/print3d.py) with the chosen printer's chain, written under `exports/<scene>/prusaslicer/`, opened in PrusaSlicer only when `open` (never in a test). 400 "nothing to slice: stickers print on paper" when no 3D tag |
| `GET /api/prusa/stale` | `{stale: [{tag, preset, field, level, text, was, now, apply}]}`: the `info` under a tag's Preset when its profile changed (nothing is applied) |
| `GET /api/prusa/watch` | the watcher: `{running, dir, revision, last_ms, broken}` |

Privacy (M8 note 5.6): every value here comes through core.prusa, which reads
a physical printer through its allow-list and drops every private key of
the other files as they are read; no answer, file or log line holds a host.

The routes live here (ROADMAP section 2): app.py includes them with ONE
line, `from . import prusa_api  # noqa: E402,F401`. `install(app)` is
idempotent, puts these routes first (before the web app's static mount)
and starts the folder's watcher with the server (stopped at shutdown).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..core import beds as _BD
from ..core import prusa as _PR
from ..scene import print3d as _P3
from . import beds_io as _BI
from . import prusa_watch as _PW
from . import store as S

router = APIRouter()


def _app():
    from . import app as A
    return A


def _sources():
    """The watcher's last good read when it follows this folder (a file
    half written keeps its last good text), else the folder read now."""
    w = _PW.WATCH
    d = S.prusa_dir()
    if w is not None and w.src is not None and d is not None and w.dir == d:
        return w.src
    try:
        return S.prusa_sources()
    except Exception:                              # noqa: BLE001
        return None


@router.get("/api/prusa/printers")
def printers(system: int = Query(0)) -> dict:
    """The physical printers resolved (core.prusa.physical_printers)."""
    src = _sources()
    d = S.prusa_dir()
    if src is None:
        return {"dir": str(d) if d else None, "found": False, "printers": [], "current": None,
                "notes": ["PrusaSlicer's folder not found"], "revision": _rev()}
    sel = src.selection or {}
    out = _PR.physical_printers(src, system=bool(system))
    notes = [f"{e['name']}: its printer preset {e['preset']!r} was not found"
             for e in out if e["printer"] is None]
    if not out:
        notes.append("PrusaSlicer has no physical printer")
    return {"dir": str(d), "found": True, "printers": out,
            "current": {"physical": sel.get("physical_printer") or None,
                        "printer": sel.get("printer") or None,
                        "print": sel.get("print") or None} if sel else None,
            "notes": notes, "revision": _rev()}


def _rev() -> int:
    w = _PW.WATCH
    return w.revision if w is not None else 0


@router.get("/api/prusa/stale")
def stale() -> dict:
    return {"stale": _PW.stale_now(_sources())}


@router.get("/api/prusa/watch")
def watch_state() -> dict:
    w = _PW.WATCH
    if w is None:
        return {"running": False, "dir": None, "revision": 0, "last_ms": None, "broken": []}
    return {"running": w.running, "dir": str(w.dir) if w.dir else None, "revision": w.revision,
            "last_ms": w.last_ms, "broken": sorted(w.broken)}


# ------------------------------------------------------------- Send

class SendIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    printer: Optional[str] = None          # a physical printer's name, or a printer preset's
    print_: Optional[str] = Field(None, alias="print")
    filament: Optional[str] = None
    white_slot: int = Field(1, ge=1, le=16)
    black_slot: int = Field(2, ge=1, le=16)
    open: bool = True
    bed_w_mm: Optional[float] = Field(None, gt=0, le=2000)
    bed_d_mm: Optional[float] = Field(None, gt=0, le=2000)
    margin_mm: float = Field(5.0, ge=0, le=100)
    spacing_mm: float = Field(5.0, ge=0, le=100)


def choose(src, printer: Optional[str], print_: Optional[str]):
    """(physical name or "", printer_of dict, print name): what Send uses.
    No printer: PrusaSlicer's selected physical printer, else its selected
    printer. No print: the selected one when it fits, else the first
    fitting "Aruco" print, else the first that fits, else the printer's
    default. Raises KeyError naming what is not found."""
    sel = src.selection or {}
    name = printer or sel.get("physical_printer") or sel.get("printer")
    if not name:
        raise KeyError("no printer chosen and none selected in PrusaSlicer")
    physical = ""
    if name in src.physical:
        physical = name
        presets = src.physical[name].get("preset_names") or []
        preset = (sel.get("physical_preset") if name == sel.get("physical_printer")
                  and sel.get("physical_preset") in presets else (presets[0] if presets else ""))
    else:
        preset = name
    pr = _PR.printer_of(preset, src) if preset else None
    if pr is None:
        raise KeyError(f"no printer {name!r}: not a physical printer or a printer preset here")
    pr = dict(pr, physical=physical)
    if print_:
        cfg, _chain = _PR.resolve(print_, src)
        if not cfg:
            raise KeyError(f"no print preset {print_!r}")
        return physical, pr, print_
    fitting = _PR.prints_for(pr, src, system=False)
    if sel.get("print") and (sel.get("printer") == pr["preset"]):
        cfg, _c = _PR.resolve(sel["print"], src)
        if cfg and _PR.fits(cfg, pr) != "no":
            return physical, pr, sel["print"]
    for p in fitting:
        if p["fits"] == "yes":
            return physical, pr, p["name"]
    if pr.get("default_print") and _PR.resolve(pr["default_print"], src)[0]:
        return physical, pr, pr["default_print"]
    raise KeyError(f"no print preset fits {pr['preset']!r}")


def build(req: SendIn):
    """(project bytes, answer without the path, scene name): Send's work
    without writing anything."""
    A = _app()
    from . import design_api as _DA
    with _DA.D.lock:
        sc = _DA.D.current()
        doc = _DA.D.doc
    plans = {t.name: A.cached_plan(t.spec) for t in sc.tags}
    ps, skipped = _P3.parts(doc, sc, plans, white=req.white_slot, black=req.black_slot)
    if not ps:
        raise HTTPException(status_code=400, detail=_P3.nothing_reason(sc, plans))
    warnings = []
    src = _sources()
    profile = None
    chosen = {"physical": None, "preset": None}
    print_name = filament = None
    if src is None:
        warnings.append("PrusaSlicer's folder was not found, so the project carries no config "
                        "(PrusaSlicer keeps its own presets)")
    else:
        try:
            physical, pr, print_name = choose(src, req.printer, req.print_)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from None
        bundle = S.prusa_bundle_text() or ""
        filament = req.filament or _BI.filament_for(pr, src, bundle)
        try:
            profile = _BI.chain_profile(src, pr["preset"], print_name, filament, bundle, physical)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        chosen = {"physical": physical or None, "preset": pr["preset"]}
        if _PR.fits(_PR.resolve(print_name, src)[0], pr) == "no":
            warnings.append(f"the print preset {print_name!r} does not fit {pr['preset']!r} "
                            "(its compatible printers condition)")
    bed_w, bed_d = (profile.bed_mm if profile is not None else _BD.MK4_BED_MM)
    st = _BD.BedSettings(bed_w_mm=float(req.bed_w_mm or bed_w), bed_d_mm=float(req.bed_d_mm or bed_d),
                         margin_mm=req.margin_mm, spacing_mm=req.spacing_mm,
                         bed_h_mm=profile.max_height_mm if profile is not None else None,
                         tile_extruder=req.white_slot, cells_extruder=req.black_slot,
                         wipe_tower_mm=(_BD.DEFAULT_WIPE_TOWER_MM if profile is None
                                        or profile.extruders > 1 else None))
    try:
        st.check()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if profile is not None:
        for what, slot in (("black", req.black_slot), ("white", req.white_slot)):
            if profile.extruders < slot:
                warnings.append(f"{profile.printer} has {profile.extruders} extruder(s); the "
                                f"{what} is on filament {slot}, so PrusaSlicer prints it in "
                                "filament 1")
    lay = _P3.layout(ps, st)
    warnings += lay.warnings
    if not lay.placed:
        raise HTTPException(status_code=400, detail="nothing fits the bed: " + "; ".join(
            f"{n}: {r}" for n, r in lay.rejected))
    config = _BD.project_config_text(profile, st) if profile is not None else None
    data = _P3.render(lay, config, sc.name or "ArUco Studio")
    man = _P3.manifest(ps, skipped, lay)
    ans = {"parts": man["parts"], "beds": man["beds"], "skipped": man["skipped"],
           "rejected": man["rejected"], "warnings": warnings, "printer": chosen,
           "print": print_name, "filament": filament,
           "bed_mm": [st.bed_w_mm, st.bed_d_mm], "schema": man["schema"]}
    return data, ans, sc.name, (lay, ps, sc, plans, profile)


@router.post("/api/scene/send/prusaslicer")
def send(req: Optional[SendIn] = None) -> dict:
    """Send to PrusaSlicer: the project written, then opened when `open`."""
    req = req or SendIn()
    data, ans, name, _ctx = build(req)
    path = S.exports_dir(name) / "prusaslicer" / f"{S.safe_name(name or 'scene')}.3mf"
    ans["project"] = _BI.write_project(str(path), data)
    ans["opened"] = False
    if req.open:
        got = _BI.open_in_prusaslicer(ans["project"])
        ans["opened"] = got["opened"]
        if got["error"]:
            ans["warnings"].append(f"PrusaSlicer was not opened: {got['error']}")
    return ans


# ------------------------------------------------------------- install

def install(app) -> None:
    """Add the routes once, FIRST, and the watcher's start / stop."""
    if getattr(app.state, "prusa_api", False):
        return
    n = len(app.router.routes)
    app.include_router(router)
    mine = app.router.routes[n:]
    del app.router.routes[n:]
    app.router.routes[0:0] = mine
    app.router.on_startup.append(_PW.ensure)
    app.router.on_shutdown.append(_PW.shutdown)
    app.state.prusa_api = True


def _self_install():
    from .app import app
    install(app)


_self_install()
