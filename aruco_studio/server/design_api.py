"""The design file in the server (M8a): the open document, its file, the
watcher and the routes over them. docs/API.md lists the routes.

| Route | Does |
|---|---|
| `GET /api/design` | the open design: `{path, state, text, hash, revision, error, issues}` |
| `PUT /api/design {text, hash?}` | the Studio's write: the whole text (kept verbatim; a `/1` text is migrated). 422 when it does not parse; 409 when the file on disk is broken or missing, or `hash` is not the text the server last saw |
| `POST /api/design/open {path}` | open a design file anywhere (not under `%USERPROFILE%\\CADExporter` or PrusaSlicer's folder) and watch it |
| `POST /api/design/save_as {path}` | write the open design to a new file and follow that one |
| `POST /api/design/preview {text}` | compile without writing: `{scene (with plans), issues, error}` (a drag's preview) |
| `POST /api/design/reveal {open}` | the OS file browser on the file (`open: false`: only say the command) |
| `GET /api/events` | server-sent events (server/events.py); `?max_events=N&timeout=S` end the stream |

**The file is the truth.** Every committed action writes the file
(atomic, store.write_atomic), its hash remembered first, so the watcher
never reads the server's own write back as a change. An external write is
parsed, compiled and pushed as a `scene` event. A file that does not parse
keeps the last good scene, says `line:col`, and every write is refused
(409 "file not parseable") until it parses again; a file that goes away
stops the writes ("file missing"). Before it writes, the server checks the
file still holds what it last saw; if not it reloads, pushes the change
and drops the action (409). Without a file (a new, untitled scene) the
design lives in memory until Save / Save as / open.
"""
from __future__ import annotations

import copy
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..core import presets as _P
from ..scene import Scene
from ..scene import design as _DS
from ..scene.file import (DesignParseError, SceneFileError, dumps_design, loads_design, migrate,
                          parse_v1)
from . import events as _EV
from . import store as S
from .watch import Watcher, text_hash

WATCH_S = 0.25
router = APIRouter()


class Conflict(Exception):
    def __init__(self, message: str, detail: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


def _empty(name: str = "untitled") -> dict:
    return {"schema": _DS.SCHEMA, "name": name, "sketches": [], "features": []}


def resolver():
    """name -> a preset (the catalog: built-ins, yours, PrusaSlicer's Aruco
    profiles), read once per compile."""
    cat = {}

    def get(name):
        if "cat" not in cat:
            try:
                src = S.prusa_sources()
            except Exception:                      # noqa: BLE001
                src = None
            cat["cat"] = _P.catalog_all(S.presets_store(), src)   # the sticker printers too (M6a)
        p, _kind = _P.find(cat["cat"], name)
        return p
    return get


class Design:
    """The open design (one per server)."""

    def __init__(self):
        self.lock = threading.RLock()
        self.path: Optional[Path] = None
        self.watcher: Optional[Watcher] = None
        self.revision = 0
        self.state = "memory"                 # memory / ok / broken / missing
        self.error: Optional[dict] = None
        self.hash: Optional[str] = None
        self._set_doc(_empty(), None)

    # ---------------------------------------------------------- the document

    def _set_doc(self, doc: dict, text: Optional[str]):
        sc, issues = _DS.compile(doc, resolver())
        self.doc = doc
        self.text = text if text is not None else dumps_design(doc)
        self.scene: Scene = sc
        self.issues = issues
        self._publish_scene_to_app()

    def _publish_scene_to_app(self):
        try:
            from . import app as _app
            _app.STATE["scene"] = self.scene
        except Exception:                          # noqa: BLE001  (while app imports)
            pass

    def current(self) -> Scene:
        """The compiled scene. A scene put straight into app.STATE (the
        tests of main do) becomes the design: an untitled one in memory."""
        from . import app as _app
        with self.lock:
            st = _app.STATE.get("scene")
            if st is not self.scene and isinstance(st, Scene):
                self.unbind()
                self._set_doc(_DS.doc_from_scene(st), None)
                self.state = "memory"
                self.error = None
                self.revision += 1
            return self.scene

    # ---------------------------------------------------------- the file

    def unbind(self):
        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None
        self.path = None
        self.hash = None

    def bind(self, path: Path, text: str, digest: str):
        """Follow `path`, whose bytes hash to `digest` and hold `text` (parsed)."""
        self.unbind()
        self.path = Path(path)
        self.hash = digest
        self.watcher = Watcher(lambda: [self.path] if self.path else [], self._on_change,
                               interval=WATCH_S, name="design-watch")
        self.watcher.remember(self.path, digest)
        self.watcher.start()

    def open(self, path: Path) -> None:
        text, digest = S.read_design(path)
        doc = loads_design(text)                   # raises: nothing changes
        with self.lock:
            self._set_doc(doc, text)
            self.state, self.error = "ok", None
            self.revision += 1
            self.bind(path, text, digest)

    def save_as(self, path: Path) -> None:
        with self.lock:
            text = self.text if self.state != "broken" else dumps_design(self.doc)
            if self.watcher is not None:
                self.watcher.remember(path, text_hash(text))
            S.write_atomic(path, text)
            self.bind(path, text, text_hash(text))
            self.state, self.error = "ok", None

    def _on_change(self, path: str, text: Optional[str], digest: Optional[str]):
        with self.lock:
            if self.path is None or str(Path(path)) != str(self.path):
                return
            if text is None:
                self.state = "missing"
                self.hash = None
                self.error = {"message": f"{self.path} is gone: writes stop; Save as… "
                                         "writes it again"}
                _EV.HUB.publish("file", {"state": "missing", "path": str(self.path),
                                         "error": self.error})
                return
            # the file is the truth: read it again now, under the lock (the
            # watcher may have read it before our own write landed)
            try:
                text, digest = S.read_design(self.path)
            except OSError:
                return
            if self.watcher is not None:
                self.watcher.remember(self.path, digest)
            if digest == self.hash:
                return                            # what we wrote or read last: no change
            self.hash = digest
            try:
                doc = loads_design(text)
            except DesignParseError as exc:
                self.state, self.error = "broken", exc.to_dict()
                _EV.HUB.publish("file", {"state": "broken", "path": str(self.path),
                                         "error": self.error})
                return
            except SceneFileError as exc:
                self.state, self.error = "broken", {"line": None, "col": None,
                                                    "message": str(exc), "text": str(exc)}
                _EV.HUB.publish("file", {"state": "broken", "path": str(self.path),
                                         "error": self.error})
                return
            was = self.state
            self._set_doc(doc, text)
            self.state, self.error = "ok", None
            self.revision += 1
            if was in ("broken", "missing"):
                _EV.HUB.publish("file", {"state": "ok", "path": str(self.path), "error": None})
            _EV.HUB.publish("scene", {"revision": self.revision, "path": str(self.path),
                                      "why": "file"})

    def writable(self):
        if self.state == "broken":
            e = self.error or {}
            where = f"line {e.get('line')} col {e.get('col')}: " if e.get("line") else ""
            raise Conflict(f"file not parseable: {where}{e.get('message', '')}; fix the file "
                           "(nothing was written)", {"state": "broken", "error": e})
        if self.state == "missing":
            raise Conflict(f"file missing: {self.path} (Save as… writes it again; nothing was "
                           "written)", {"state": "missing"})

    def commit(self, doc: dict, text: Optional[str] = None) -> None:
        """Make `doc` the design and write it (when there is a file)."""
        with self.lock:
            self.writable()
            text = text if text is not None else dumps_design(doc)
            if self.path is not None:
                try:
                    now, digest = S.read_design(self.path)
                except OSError:
                    if self.watcher is not None:
                        self.watcher.remember(self.path, None)
                    self._on_change(str(self.path), None, None)
                    self.writable()
                    raise
                if digest != self.hash:          # changed under us: read it now, drop the action
                    if self.watcher is not None:
                        self.watcher.remember(self.path, digest)
                    self._on_change(str(self.path), now, digest)
                    raise Conflict("the file changed on disk since the last read: reloaded; "
                                   "your action was dropped", {"state": self.state})
                new_hash = text_hash(text)
                if self.watcher is not None:
                    self.watcher.remember(self.path, new_hash)
                S.write_atomic(self.path, text)
                self.hash = new_hash
            self._set_doc(doc, text)
            self.revision += 1

    def info(self, text: bool = True) -> dict:
        d = {"path": str(self.path) if self.path else None, "state": self.state,
             "hash": self.hash, "revision": self.revision, "error": self.error,
             "schema": _DS.SCHEMA, "issues": [i.to_dict() for i in self.issues]}
        if text:
            d["text"] = self.text
        return d


D = Design()


def conflict_response(exc: Conflict) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message, **exc.detail})


def mutate(fn: Callable[[dict, Scene], Any]):
    """An old route's change: `fn(doc, scene)` on a copy of the document and
    its fresh compile (Scene API calls on `scene`, direct edits on `doc`);
    the scene is written back into the document, which is committed (the
    file written). `fn` may return a JSONResponse to stop without writing.
    -> (fn's result, the new scene)."""
    with D.lock:
        D.current()
        D.writable()
        doc = copy.deepcopy(D.doc)
        res = resolver()
        sc, _issues = _DS.compile(doc, res)
        out = fn(doc, sc)
        if isinstance(out, JSONResponse):
            return out, D.scene
        _DS.write_back(doc, sc, res)
        D.commit(doc)
        return out, D.scene


def replace_scene(scene: Scene) -> None:
    """PUT /api/scene with a compiled (`/1`-shaped) scene: written back onto
    the open design, so its sketches and features stay where they match."""
    def fn(doc, sc):
        sc.tags = scene.tags
        sc.name, sc.ledger = scene.name, scene.ledger
        sc.overrides, sc.presets_used = dict(scene.overrides), list(scene.presets_used)
    mutate(fn)


def new_design(name: str) -> None:
    with D.lock:
        D.unbind()
        D.state, D.error = "memory", None
        D._set_doc(_empty(name), None)
        D.revision += 1


def shutdown():
    D.unbind()


def open_path(path) -> dict:
    """`python -m aruco_studio.server --open <path>`, POST /api/design/open."""
    p = S.design_path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    D.open(p)
    return D.info()


# ------------------------------------------------------------- routes

class DesignTextIn(BaseModel):
    text: str
    hash: Optional[str] = None


class PathIn(BaseModel):
    path: str


class RevealIn(BaseModel):
    open: bool = True


def _design_doc(text: str) -> dict:
    try:
        return loads_design(text)
    except DesignParseError as exc:
        raise HTTPException(status_code=422, detail=[{
            "loc": ["body", "text"], "msg": str(exc), "type": "value_error", "path": "text",
            "line": exc.line, "col": exc.col}]) from None
    except SceneFileError as exc:
        raise HTTPException(status_code=422, detail=[{
            "loc": ["body", "text"], "msg": str(exc), "type": "value_error",
            "path": "text"}]) from None


@router.get("/api/design")
def design_get(text: int = Query(1)) -> dict:
    with D.lock:
        D.current()
        return D.info(text=bool(text))


@router.put("/api/design")
def design_put(req: DesignTextIn):
    doc = _design_doc(req.text)
    with D.lock:
        D.current()
        if req.hash is not None and D.path is not None and req.hash != D.hash:
            return JSONResponse(status_code=409, content={
                "detail": "the file changed since you read it: reload first", "hash": D.hash})
        import json as _json
        verbatim = _json.loads(req.text).get("schema") == _DS.SCHEMA
        try:
            D.commit(doc, req.text if verbatim else None)
        except Conflict as exc:
            return conflict_response(exc)
        return D.info()


@router.post("/api/design/open")
def design_open(req: PathIn):
    try:
        return open_path(req.path)
    except S.StoreError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"no file {req.path!r}") from None
    except DesignParseError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc), **exc.to_dict()}) \
            from None
    except SceneFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/api/design/save_as")
def design_save_as(req: PathIn):
    try:
        p = S.design_path(req.path)
    except S.StoreError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    with D.lock:
        D.current()
        D.save_as(p)
        return D.info()


@router.post("/api/design/preview")
def design_preview(req: DesignTextIn, mesh: int = Query(0), top: int = Query(0)):
    """Compile `text` and plan it; nothing written, nothing kept."""
    from .app import cached_plan_dict
    try:
        doc = loads_design(req.text)
    except DesignParseError as exc:
        return {"scene": None, "issues": [], "error": exc.to_dict()}
    except SceneFileError as exc:
        return {"scene": None, "issues": [], "error": {"line": None, "col": None,
                                                       "message": str(exc), "text": str(exc)}}
    sc, issues = _DS.compile(doc, resolver())
    return {"scene": scene_dict(sc, plans=True, mesh=bool(mesh), top=bool(top),
                                plan_dict=cached_plan_dict),
            "issues": [i.to_dict() for i in issues], "error": None}


def reveal_command(path: Path) -> List[str]:
    if sys.platform.startswith("win"):
        return ["explorer", f"/select,{path}"]
    if sys.platform == "darwin":
        return ["open", "-R", str(path)]
    return ["xdg-open", str(path.parent)]


@router.post("/api/design/reveal")
def design_reveal(req: Optional[RevealIn] = None):
    with D.lock:
        if D.path is None:
            raise HTTPException(status_code=404, detail="no file: the design is in memory "
                                                        "(Save as… first)")
        cmd = reveal_command(D.path)
    opened = False
    if req is None or req.open:
        try:
            subprocess.Popen(cmd, close_fds=True)
            opened = True
        except OSError:
            opened = False
    return {"path": str(D.path), "command": cmd, "opened": opened}


@router.get("/api/events")
async def events(request: Request, max_events: Optional[int] = Query(None),
                 timeout: Optional[float] = Query(None)):
    def hello():
        with D.lock:
            return {"revisions": dict(_EV.HUB.revisions, scene=D.revision),
                    "file": {"path": str(D.path) if D.path else None, "state": D.state,
                             "error": D.error}}
    return StreamingResponse(_EV.HUB.stream(hello, max_events=max_events, timeout=timeout,
                                            is_disconnected=request.is_disconnected),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------- the scene as JSON

def tag_dict(t, plan_dict=None, mesh=False, top=False) -> dict:
    d = t.to_dict()
    if t.source is not None:
        s = {k: v for k, v in t.source.items() if k != "local"}
        d["source"] = s
    if plan_dict is not None:
        d["plan"] = plan_dict(t.spec, mesh=mesh, top=top)
    return d


def scene_dict(sc: Scene, plans=False, mesh=False, top=False, plan_dict=None) -> dict:
    from ..scene import checks as _checks
    d = sc.to_dict()
    d["tags"] = [tag_dict(t, plan_dict if plans else None, mesh, top) for t in sc.tags]
    if plans:
        d["issues"] = _checks.scene_issues(sc)
    return d
