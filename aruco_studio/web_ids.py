"""Auto id for the online Studio (CoreApi.assign_ids): a stable key per marker
feature, hashed to a preferred first id, unique across the document by default,
a typed id wins. Lane "ids" of the 2026-10-18 dispatch implements it (stdlib
only). Stub until then."""
from __future__ import annotations


def assign_ids(req: dict) -> dict:
    raise NotImplementedError("assign_ids: not built yet")
