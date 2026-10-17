"""The gallery (Zach's N-3, 2026-10-17): the Studio's landing page shows
golden examples, the inputs drawn for the user, grouped by feature. Files
are read and written by server/store.py only.

| Route | Gives |
|---|---|
| `GET /api/gallery` | `{schema, groups: [{id, title, line, items: [{name, file, title, line, look, actions, text}]}], dir}`: `examples/gallery/gallery.json`, each item with its file's text (the Studio plans it for the card's thumbnail through `POST /api/design/preview`, nothing written) |
| `POST /api/gallery/open {name}` | the example copied to `<home>/gallery/<name>.arucostudio.json` (afresh: opening a card starts from the example) and opened, as `POST /api/design/open` answers, plus `item` (its manifest row). `examples/` is never written. 404: no such example |

app.py includes the routes with ONE line at its end; `install(app)` puts
them first (before the web app's static mount)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import store as S

router = APIRouter()


class GalleryOpenIn(BaseModel):
    name: str


@router.get("/api/gallery")
def gallery() -> dict:
    try:
        doc = S.gallery()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=f"no gallery: {exc}") from None
    doc["dir"] = str(S.gallery_dir())
    return doc


@router.post("/api/gallery/open")
def gallery_open(req: GalleryOpenIn) -> dict:
    from . import design_api as _DA
    try:
        item = S.gallery_item(req.name)
        p = S.copy_gallery_example(req.name)
    except (KeyError, FileNotFoundError):
        raise HTTPException(status_code=404, detail=f"no gallery example {req.name!r}") from None
    except S.StoreError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    out = _DA.open_path(p)
    out["item"] = item
    return out


def install(app) -> None:
    if getattr(app.state, "gallery_api", False):
        return
    n = len(app.router.routes)
    app.include_router(router)
    mine = app.router.routes[n:]
    del app.router.routes[n:]
    app.router.routes[0:0] = mine
    app.state.gallery_api = True


def _self_install():
    from .app import app
    install(app)


_self_install()
