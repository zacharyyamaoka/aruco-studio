"""The scene file: .arucostudio.json, `"schema": "arucostudio.scene/2"` (the
design document, docs/FILE_FORMAT.md; scene/design.py compiles it).

| Function | Does |
|---|---|
| `loads_design(text)` | the text -> the design document (a dict), every older schema migrated; a parse error is a `DesignParseError` with its line and column |
| `dumps_design(doc)` | the document as the file's text: `indent=1, sort_keys`, so diffs stay small |
| `loads(text)` | the text -> today's `Scene` (compiled; a compile error raises) |
| `dumps(scene)` | a `Scene` as a `/2` file (each tag a sketch, a shape, an Extrude when it has a body, an ArUco Extrude with the exact settings) |

`MIGRATIONS["arucostudio.scene/1"]`: a `/1` file (tags with their whole
TagSpec) becomes a `/2` document whose compile gives the same tags byte
for byte (their ledger, overrides and uids kept). A schema this code does
not know is refused, with a message that names it.
"""
from __future__ import annotations

import json
from typing import Callable, Dict

from . import design as _DS
from .model import Scene, SceneTag

EXT = ".arucostudio.json"
SCHEMA = _DS.SCHEMA
V1 = "arucostudio.scene/1"


class SceneFileError(ValueError):
    pass


class DesignParseError(SceneFileError):
    """The text is not JSON: where and why (`line`, `col`, `msg`)."""

    def __init__(self, line: int, col: int, msg: str):
        super().__init__(f"line {line} col {col}: {msg}")
        self.line, self.col, self.msg = line, col, msg

    def to_dict(self) -> dict:
        return {"line": self.line, "col": self.col, "message": self.msg, "text": str(self)}


def parse_v1(d: dict) -> Scene:
    """A `/1` document -> its Scene (the `/1` reader as it was)."""
    if d.get("units", "mm") != "mm":
        raise SceneFileError(f"scene units {d.get('units')!r}: only mm")
    tags = []
    for i, t in enumerate(d.get("tags") or []):
        try:
            tags.append(SceneTag.from_dict(t))
        except Exception as exc:                   # noqa: BLE001
            raise SceneFileError(f"tag {i}: {exc}") from None
    names = [t.name for t in tags]
    if len(set(names)) != len(names):
        raise SceneFileError("two tags share a name: " + ", ".join(
            sorted({n for n in names if names.count(n) > 1})))
    ov = d.get("overrides") or {}
    if not isinstance(ov, dict) or not all(isinstance(v, int) and not isinstance(v, bool)
                                           for v in ov.values()):
        raise SceneFileError("overrides must be {tag name: id}")
    return Scene(name=str(d.get("name") or "scene"), tags=tags, ledger=d.get("ledger"),
                 overrides=dict(ov), presets_used=list(d.get("presets_used") or []))


def _from_v1(d: dict) -> dict:
    return _DS.doc_from_scene(parse_v1(d))


# schema -> a function from that version's dict to the next one's
MIGRATIONS: Dict[str, Callable[[dict], dict]] = {V1: _from_v1}
KNOWN = (SCHEMA,)


def migrate(d) -> dict:
    """A parsed document of any known schema -> a `/2` document."""
    if not isinstance(d, dict):
        raise SceneFileError("not a scene file: the JSON is not an object")
    schema = d.get("schema")
    seen = set()
    while schema in MIGRATIONS and schema not in seen:
        seen.add(schema)
        d = MIGRATIONS[schema](d)
        schema = d.get("schema")
    if schema not in KNOWN:
        raise SceneFileError(f"scene schema {schema!r} is not one this version reads "
                             f"({', '.join((V1,) + KNOWN)}): saved by a newer ArUco Studio?")
    if d.get("units", "mm") != "mm":
        raise SceneFileError(f"scene units {d.get('units')!r}: only mm")
    return d


def loads_design(text: str) -> dict:
    try:
        d = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DesignParseError(exc.lineno, exc.colno, exc.msg) from None
    except ValueError as exc:
        raise SceneFileError(f"not a scene file: {exc}") from None
    return migrate(d)


def dumps_design(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def dumps(scene: Scene) -> str:
    return dumps_design(_DS.doc_from_scene(scene))


def loads(text: str, presets=None) -> Scene:
    """The file -> today's Scene. A compile error raises SceneFileError
    (the server keeps a broken design instead: server/design_api.py)."""
    doc = loads_design(text)
    try:
        sc, issues = _DS.compile(doc, presets)
    except _DS.DesignError as exc:
        raise SceneFileError(str(exc)) from None
    errs = [i for i in issues if i.level == "error"]
    if errs:
        raise SceneFileError("; ".join(f"{i.field}: {i.text}" for i in errs[:5]))
    return sc
