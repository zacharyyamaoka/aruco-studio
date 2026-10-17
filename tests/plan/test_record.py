"""M2.7: records. The plan's record is the one REF writes; a REF node read
back (its stored settings and parameters) replans to the same tag;
record_same holds after an unchanged round trip; record_digest changes when
the plan does, and only then."""
from __future__ import annotations

import copy
import json

import pytest

import _evaluate_golden as G
from aruco_studio.plan import plan_tag
from aruco_studio.plan import record as R
from aruco_studio.plan.plan import settle
from aruco_studio.plan.spec import TagSpec, from_record


def _ok_cases(group):
    return [c for c in G.cases(group) if "error" not in c["out"] and "record" in c["out"]]


def test_the_record_is_refs():
    bad = []
    for c in _ok_cases("matrix"):
        p = plan_tag(TagSpec.from_dict(c["in"]), base=c["base"])
        if G.diff(G.norm(p.data["record"]), c["out"]["record"]):
            bad.append((c["id"], G.diff(G.norm(p.data["record"]), c["out"]["record"])))
        if not c["out"]["record_same"]:
            bad.append((c["id"], "REF's record_same was False"))
        if R.record_digest(p.data["record"]) != c["out"]["digest"]:
            bad.append((c["id"], "digest"))
    assert not bad, bad[:3]


def test_a_node_read_back_replans_to_the_same_tag():
    """What a node stores (REF settle: settings + numbers) read back through
    from_record plans the same board, frame, mark and label -- except REF's
    own quirk, kept as REF has it (docs/status/M2.md, "REF findings"): a typed
    board size that was CLAMPED with a forced cols x rows stores the clamped
    size and the force, and its next compute honours the force."""
    bad = []
    quirk = []
    for c in _ok_cases("matrix"):
        spec = TagSpec.from_dict(c["in"])
        p = plan_tag(spec, base=c["base"])
        s2, n2 = settle(c["in"]["settings"], dict(c["in"]["numbers"]), p)
        back = from_record(s2, n2, spec.target, record=p.data["record"], name=spec.name)
        q = plan_tag(back, base=c["base"])
        if not q.ok or not R.record_same(p.data["record"], q.ev):
            if spec.settings.get("force") and any(t.startswith("clamped") for t in p.data["notes"]):
                quirk.append(c["id"])
                continue
            bad.append((c["id"], q.data["errors"]))
        elif R.record_digest(q.data["record"]) != R.record_digest(p.data["record"]):
            bad.append((c["id"], "digest moved"))
    assert not bad, bad[:3]
    assert len(quirk) <= 3, quirk


def test_record_same_and_digest_follow_the_plan():
    cs = _ok_cases("matrix")[:120]
    for c in cs:
        spec = TagSpec.from_dict(c["in"])
        p = plan_tag(spec)
        rec = json.loads(json.dumps(p.data["record"]))
        assert R.record_same(rec, p.ev)
        # an adapter key, the name: the same tag
        s = copy.deepcopy(spec)
        s.settings["jo_v"] = 1
        assert R.record_digest(plan_tag(s).data["record"]) == R.record_digest(rec)
        # another id: another tag
        cap = p.data["marker"]
        s = copy.deepcopy(spec)
        nid = 1 if int(spec.numbers.get("marker_id", 0)) == 0 else 0
        s.numbers["marker_id"] = nid
        q = plan_tag(s)
        if q.ok:
            assert R.record_digest(q.data["record"]) != R.record_digest(rec), c["id"]
            assert not R.record_same(rec, q.ev)


def test_an_old_frame_record_is_not_the_same():
    """REF record_same: a record that still carries 2026-10-08's Frame is
    rewritten (the Joint Origin back to OpenCV's frame)."""
    c = _ok_cases("matrix")[0]
    p = plan_tag(TagSpec.from_dict(c["in"]))
    rec = dict(p.data["record"], frame={"corner": "top_left", "z": "out"})
    assert not R.record_same(rec, p.ev)
