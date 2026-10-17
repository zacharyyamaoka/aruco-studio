"""After a recompute: an out-of-date record (and Joint Origin) refreshed.

Compute may not write the record or move a Joint Origin, so REF's
`aruco_extrude_sync.after_compute` compares, at the end of every compute,
the stored record's digest with the plan's, and when they differ asks the
policy what to do. The policy is the core's (`core.edits.verdict` ->
`core.numbering.auto_decision`); this module only:

| Step | Fusion part |
|---|---|
| read the record, compare digests (cheap, read only, never raises, gives up past `core.edits.BUDGET_MS`) | `records.read_tag_records`, `plan.record.record_digest` |
| queue the refresh, keyed by the TAG (component, key): a node's entity token changes across recomputes | a dict per document |
| run the queue when Fusion is idle (REF: a hidden auto-execute command fired by a custom event, retried on a worker thread) | `run_pending` here; the idle detection and the custom event are Fusion-gated |
"""
from __future__ import annotations

import time
import types

from ...core import edits as E
from ...plan import record as R
from . import records as REC

STATE = types.SimpleNamespace(pending={}, sync=E.SyncState(), done=[])


def after_compute(cf, s, plan, now=None):
    """-> a short note for the compute log, or None. Never raises."""
    t0 = time.perf_counter()
    try:
        comp = cf.parentComponent
        key = (s or {}).get("key")
        old = REC.find_record(comp, key)
        if old is None:
            return None                            # inside create(): no record yet
        digest = plan.data["digest"]
        if R.record_digest(old) == digest:
            return None
        if (time.perf_counter() - t0) * 1000.0 > E.BUDGET_MS:
            return "skipped: over budget"
        action, why = E.verdict(STATE.sync, digest, time.time() if now is None else now)
        if action != "schedule":
            return f"record out of date: {action}" + (f" ({why})" if why else "")
        STATE.pending[f"{comp.name}|{key}"] = {"digest": digest, "key": key, "node": cf}
        return "record out of date: refresh scheduled"
    except BaseException as exc:                   # noqa: BLE001
        return f"check failed: {type(exc).__name__}: {exc}"[:200]


def run_pending():
    """The idle-time refresh: every queued tag's record and Joint Origin.
    -> the keys refreshed."""
    from . import feature as FT
    done = []
    for qk, item in list(STATE.pending.items()):
        STATE.pending.pop(qk, None)
        FT.refresh_record(item["node"])
        STATE.sync = E.SyncState(**dict(vars(STATE.sync),
                                        done=tuple(STATE.sync.done) + (item["digest"],)))
        done.append(item["key"])
    return done
