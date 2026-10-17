"""The sticker sheet and the print bundle over HTTP (M6a; docs/API_sheet.md).

| Route | Gives |
|---|---|
| `GET /api/scene/sheet.svg?page=&landscape=&mode=&margin_mm=&proofs=` | the sheet as SVG (the Studio's preview): each sticker an invisible `<rect data-sticker>` with its place |
| `GET /api/scene/sheet.json?...` | the layout (`arucostudio.sheet/1`): per sticker page, x, y, rotation, outline, made by, ids |
| `GET /api/scene/print.pdf?...` | the sheet as `application/pdf`, `Content-Disposition: inline` (the bytes `export/print` writes as sheet.pdf the same day) |
| `POST /api/scene/export/print` | `{page, landscape, margin_mm, mode, proofs, bed_w_mm, bed_d_mm, black_slot, white_slot, inline}`: the print bundle (scene/export.py) into `exports/<scene>/`; the ledger marks every exported tag printed |
| `POST /api/scene/verify/sheet` | `{page, landscape, mode, margin_mm, proofs, dpi}`: the WYSIWYG check (verify/sheet_check.py) on the scene's own sheet, per sticker and the worst numbers |

The routes live here, not in app.py (ROADMAP wave-1 rule): app.py includes
them with ONE line, `from . import sheet_api  # noqa: E402,F401`, anywhere
after `app` is made. `install(app)` is idempotent and keeps the web app's
static mount last, so the routes are reached whatever the line's place.
"""
from __future__ import annotations

import base64
import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.routing import Mount

from ..core import sheet as _SH
from ..scene import export as _EX
from ..scene import sheet as _SS
from . import store as S

router = APIRouter()
MODES = Literal["spaced", "tight"]
PAGES = Literal["letter", "a4", "legal", "a3", "tabloid", "a5"]


def _app():
    from . import app as A
    return A


def _scene():
    A = _app()
    get = getattr(A, "_scene", None)
    return get() if callable(get) else A.STATE["scene"]


def _plans(sc):
    A = _app()
    cp = getattr(A, "cached_plan", None)
    return {t.name: (cp(t.spec) if cp else None) for t in sc.tags} if cp else sc.plans()


def _today() -> str:
    return datetime.date.today().isoformat()


class SheetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: PAGES = "letter"
    landscape: bool = False
    margin_mm: float = Field(10.0, ge=0.0, le=50.0)
    mode: MODES = "spaced"
    proofs: bool = False


class PrintIn(SheetIn):
    bed_w_mm: Optional[float] = Field(None, gt=0.0)
    bed_d_mm: Optional[float] = Field(None, gt=0.0)
    black_slot: int = Field(2, ge=1, le=16)
    white_slot: int = Field(1, ge=1, le=16)
    open: bool = False                   # never used by a test: nothing is launched here
    inline: bool = False


class VerifySheetIn(SheetIn):
    dpi: int = Field(600, ge=150, le=1200)


def _files(page, landscape, margin_mm, mode, proofs):
    sc = _scene()
    try:
        return _SS.sticker_files(sc, _plans(sc), page, landscape, mode, margin_mm, proofs,
                                 date=_today())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/api/scene/sheet.svg")
def sheet_svg(page: PAGES = "letter", landscape: bool = False, mode: MODES = "spaced",
              margin_mm: float = Query(10.0, ge=0.0, le=50.0), proofs: bool = False):
    got = _files(page, landscape, margin_mm, mode, proofs)
    return Response(got["sheet.svg"], media_type="image/svg+xml")


@router.get("/api/scene/sheet.json")
def sheet_json(page: PAGES = "letter", landscape: bool = False, mode: MODES = "spaced",
               margin_mm: float = Query(10.0, ge=0.0, le=50.0), proofs: bool = False):
    got = _files(page, landscape, margin_mm, mode, proofs)
    return Response(got["sheet.json"], media_type="application/json")


@router.get("/api/scene/print.pdf")
def print_pdf(page: PAGES = "letter", landscape: bool = False, mode: MODES = "spaced",
              margin_mm: float = Query(10.0, ge=0.0, le=50.0), proofs: bool = False):
    """The sticker sheet to print: inline, so a browser shows it and its
    print dialog prints it at 100 % (the MediaBox is the page)."""
    got = _files(page, landscape, margin_mm, mode, proofs)
    name = S.safe_name(_scene().name) + "-sheet.pdf"
    return Response(got["sheet.pdf"], media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.post("/api/scene/export/print")
def export_print(req: Optional[PrintIn] = None) -> dict:
    """The print bundle (manufacturing_intent.md 5.3): the sticker sheet and
    the 3D parts of one scene, markers.json, and the ledger."""
    req = req or PrintIn()
    sc = _scene()
    try:
        got = _EX.print_bundle(sc, _plans(sc), page=req.page, landscape=req.landscape,
                               margin_mm=req.margin_mm, mode=req.mode, proofs=req.proofs,
                               bed_w_mm=req.bed_w_mm, bed_d_mm=req.bed_d_mm,
                               black_slot=req.black_slot, white_slot=req.white_slot,
                               when=datetime.datetime.now().isoformat(timespec="seconds"),
                               date=_today())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    out_dir = S.exports_dir(sc.name)
    written = [str(S.write_atomic(out_dir / rel, data, binary=True))
               for rel, data in sorted(got["files"].items())]
    sc.ledger = got["ledger"]
    rep = dict(got["report"])
    rep.update(dir=str(out_dir), written=written)
    if req.inline:
        rep["inline"] = {rel: base64.b64encode(data).decode("ascii")
                         for rel, data in got["files"].items()
                         if rel in ("sheet.pdf", "sheet.svg", "sheet.json", "markers.json")}
    return rep


@router.post("/api/scene/verify/sheet")
def verify_sheet(req: Optional[VerifySheetIn] = None) -> dict:
    """The scene's sticker sheet made, rasterised by pdfium and read back
    (verify/sheet_check.py): per sticker and the worst numbers."""
    from ..verify.sheet_check import check_scene_sheet
    req = req or VerifySheetIn()
    sc = _scene()
    try:
        return check_scene_sheet(sc, _plans(sc), page=req.page, landscape=req.landscape,
                                 mode=req.mode, margin_mm=req.margin_mm, proofs=req.proofs,
                                 dpi=req.dpi, date=_today())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def install(app) -> None:
    """Add the routes once, before the web app's static mount ("/")."""
    if getattr(app.state, "sheet_api", False):
        return
    app.include_router(router)
    app.router.routes.sort(key=lambda r: isinstance(r, Mount))     # stable: mounts last
    app.state.sheet_api = True


def _self_install():
    from .app import app
    install(app)


_self_install()
