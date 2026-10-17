"""The Open dialog's lists (the 2026-10-17 audit: Open showed "No saved
scenes yet." and wanted a typed path; the README's examples were not
offered). Files are read and written by server/store.py only.

| Route | Gives |
|---|---|
| `GET /api/design/files` | `{examples: [{name, file, title}], recent: [{path, name, exists, modified}], scenes: [...], scenes_dir}` |
| `POST /api/design/open_example {name}` | the example copied into the scenes folder (a fresh name when taken) and opened: the repo's examples are never written |
| `GET /api/design/browse?dir=` | a folder's `*.arucostudio.json` and subfolders (the scenes folder by default): `{dir, parent, folders, files}` |

A design file opened or saved (server/design_api.Design.bind) goes first in
`<home>/recent_designs.json`.

app.py includes the routes with ONE line at its end; `install(app)` puts
them first (before the web app's static mount)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from . import store as S

router = APIRouter()


class ExampleIn(BaseModel):
    name: str


@router.get("/api/design/files")
def design_files() -> dict:
    return {"examples": S.examples(), "recent": S.recent_designs(), "scenes": S.list_scenes(),
            "scenes_dir": str(S.scenes_dir())}


@router.post("/api/design/open_example")
def design_open_example(req: ExampleIn) -> dict:
    from . import design_api as _DA
    try:
        p = S.copy_example(req.name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"no example {req.name!r}") from None
    except S.StoreError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    return _DA.open_path(p)


@router.get("/api/design/browse")
def design_browse(dir: Optional[str] = Query(None)) -> dict:   # noqa: A002  (the query's name)
    try:
        return S.browse(dir)
    except S.StoreError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"no folder {dir!r}") from None


def install(app) -> None:
    if getattr(app.state, "files_api", False):
        return
    n = len(app.router.routes)
    app.include_router(router)
    mine = app.router.routes[n:]
    del app.router.routes[n:]
    app.router.routes[0:0] = mine
    app.state.files_api = True


def _self_install():
    from .app import app
    install(app)


_self_install()
