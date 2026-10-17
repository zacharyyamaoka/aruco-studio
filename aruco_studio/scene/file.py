"""The scene file: .arucostudio.json ("schema": "arucostudio.scene/1").

The file is the scene as JSON with every tag's `plan` dropped (it is
recomputed on load). A file of another schema number goes through its
migration first; a schema this code does not know is refused, with a
message that names it.
"""
from __future__ import annotations

import json
from typing import Callable, Dict

from .model import SCHEMA, Scene, SceneTag

EXT = ".arucostudio.json"

# schema -> a function from that version's dict to the next one's
MIGRATIONS: Dict[str, Callable[[dict], dict]] = {}
KNOWN = (SCHEMA,)


class SceneFileError(ValueError):
    pass


def dumps(scene: Scene) -> str:
    d = scene.to_dict()
    for t in d["tags"]:
        t.pop("plan", None)
    return json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def loads(text: str) -> Scene:
    try:
        d = json.loads(text)
    except ValueError as exc:
        raise SceneFileError(f"not a scene file: {exc}") from None
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
                             f"({', '.join(KNOWN)}): saved by a newer ArUco Studio?")
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
                 overrides=dict(ov), presets_used=list(d.get("presets_used") or []),
                 units="mm", schema=SCHEMA)
