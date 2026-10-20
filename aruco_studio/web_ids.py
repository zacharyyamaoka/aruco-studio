"""Auto id for the online Studio (CoreApi.assign_ids): a stable key per marker
feature, hashed to a preferred first id, unique across the document by default,
a typed id wins. The rules and what is guaranteed: aruco_studio/core/autoid.py.
Standard library only (it runs in Pyodide)."""
from __future__ import annotations

from .core import autoid as _AI


def assign_ids(req: dict) -> dict:
    """IdRequest {items, ledger?, reserved?, mode?, start?, fresh?} -> IdResult
    {items, ledger, warnings}. `reserved`: a list (every family) or a map
    {family: [id, ...]}; `mode` "hash" (default) | "sequential", `start`
    (default 0), `fresh` (default false): Re-ID (autoid)."""
    if not isinstance(req, dict) or not isinstance(req.get("items"), list):
        raise ValueError("assign_ids needs {items: [...], ledger?: {key: first id}, "
                         "reserved?: [id, ...] or {family: [id, ...]}, "
                         "mode?: \"hash\" | \"sequential\", start?: id, fresh?: bool}")
    ledger = req.get("ledger")
    if ledger is not None and not isinstance(ledger, dict):
        raise ValueError(f"ledger: an object {{key: first id}}, got {ledger!r}")
    reserved = req.get("reserved")
    if reserved is not None and not isinstance(reserved, (list, dict)):
        raise ValueError(f"reserved: a list of ids or a map {{family: [id, ...]}}, got {reserved!r}")
    mode, start, fresh = req.get("mode"), req.get("start"), req.get("fresh")
    return _AI.assign(req["items"], ledger, reserved,
                      "hash" if mode is None else mode,
                      0 if start is None else start,
                      False if fresh is None else fresh)
