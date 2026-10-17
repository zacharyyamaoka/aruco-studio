"""adapters/fusion/records.py (PLAN M4.4).

* every evaluate() golden case as a NODE on the stand-in (its settings as
  the "spec" named value, its numbers as parameters in cm, legacy ones too)
  reads back through records.py as a TagSpec that plans to the same
  TagPlan (floats to 1e-9: Fusion keeps cm, the plan mm);
* a record written to a component reads back the same, and a write that
  changes nothing is not made;
* Edit -> OK with nothing changed writes no attribute, no named value and
  no parameter;
* preset_of_node is core.presets.preset_of on what the node holds;
* body_role answers REF aruco_export.body_role's cases.
"""
from __future__ import annotations

import json

import pytest

import _cases as C
import fake_adsk as FK
from aruco_studio.adapters.fusion import feature as FT
from aruco_studio.adapters.fusion import records as REC
from aruco_studio.core import presets as PR
from aruco_studio.core import settings as S
from aruco_studio.plan import plan_tag
from aruco_studio.plan.spec import TagSpec
from aruco_studio.plan.target import Target


def _node(stored, numbers):
    comp = FK.design().rootComponent
    cf = FK.CustomFeature(comp, FK.CustomFeatureDefinition(FT.DEF_ID, FT.DEF_NAME))
    cf.customNamedValues.addOrSetValue("spec", json.dumps(stored, sort_keys=True))
    for pid, v in numbers.items():
        if pid in S.PARAMS + S.LEGACY_PARAMS:
            val = float(v) if pid == "marker_id" else float(v) / 10.0      # Fusion keeps cm
            cf.parameters._items.append(FK.CustomFeatureParameter(pid, pid, val,
                                                                  "" if pid == "marker_id"
                                                                  else "mm", True))
    return cf


def _close(a, b, path="", tol=1e-9):
    if isinstance(a, float) or isinstance(b, float):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            return [path]
        return [] if abs(a - b) <= tol * max(1.0, abs(a), abs(b)) else [path]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [path + " keys"]
        out = []
        for k in a:
            out += _close(a[k], b[k], f"{path}.{k}", tol)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [path + " len"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _close(x, y, f"{path}[{i}]", tol)
        return out
    return [] if a == b else [path]


IGNORE = ("digest",)          # a digest of the frame to 1e-6: rounding may land either side


@pytest.mark.parametrize("group", C.GROUPS)
def test_a_node_reads_back_as_the_same_tagspec(group):
    bad, n = [], 0
    for c in C.cases(group):
        if "error" in c["out"]:
            continue
        spec = TagSpec.from_dict(c["in"])
        # a node stores its spec as JSON with sorted keys (REF _wrap): the
        # plan of what it holds (a junk trim's words print its dict)
        spec.settings = json.loads(json.dumps(spec.settings, sort_keys=True))
        want = plan_tag(spec)
        cf = _node(spec.settings, spec.numbers)
        got_spec = REC.spec_of_node(cf, Target.from_dict(c["in"]["target"]),
                                    record={"key": spec.key}, name=spec.name)
        got = plan_tag(got_spec)
        n += 1
        a = {k: v for k, v in want.data.items() if k not in IGNORE}
        b = {k: v for k, v in got.data.items() if k not in IGNORE}
        diff = _close(a, b)
        if diff:
            bad.append((c["id"], diff[:4]))
    assert n > 30 and not bad, bad[:4]


def test_legacy_parameters_come_back_as_legacy_numbers():
    rows = [c for g in C.GROUPS for c in C.cases(g) if "height" in c["in"]["numbers"]
            and "error" not in c["out"]]
    assert rows
    for c in rows:
        spec = TagSpec.from_dict(c["in"])
        cf = _node(spec.settings, spec.numbers)
        got = REC.spec_of_node(cf, Target.from_dict(c["in"]["target"]))
        assert {"height", "thickness", "above"} <= set(got.numbers)
        assert plan_tag(got).data["rules"]["legacy_numbers"] is True


def test_records_round_trip_and_no_write_without_a_change():
    comp = FK.design().rootComponent
    _cid, p = next((cid, p) for cid, p in C.plans("matrix") if p.ok)
    rec = REC.record_of_plan(p, "", {"custom_feature": "tok", "mode": "both"})
    assert REC.write_record(comp, rec) is True
    assert REC.read_tag_records(comp) == [json.loads(json.dumps(rec))]
    writes = comp.attributes.writes
    assert REC.write_record(comp, json.loads(json.dumps(rec))) is False
    assert comp.attributes.writes == writes
    other = dict(rec, key="other")
    REC.write_record(comp, other)
    assert [r["key"] for r in REC.read_tag_records(comp)] == [rec["key"], "other"]
    REC.write_record(comp, dict(rec, name="renamed"), live_keys={rec["key"]})
    assert [r["key"] for r in REC.read_tag_records(comp)] == [rec["key"]]


def test_edit_ok_unchanged_writes_nothing():
    FT.register()
    _body, face = FK.plate()
    out = FT.create(face, {"layout": "single", "dictionary": "DICT_4X4_50", "mode": "both",
                           "op": "join"}, S.default_numbers("both"), key="t1")
    cf = out["node"]
    comp = FK.design().rootComponent
    FK.LOG.clear()
    res = FT.edit(cf, {}, {})
    assert res["record"] is None and res["wrote"] is False
    assert not [x for x in FK.LOG if x.startswith(("attributes.add", "customNamedValues",
                                                   "CustomFeatureParameter.", "jointOrigins"))]
    # and with the node's own values typed in again (the dialog sends them)
    s_now = REC.settings_of(cf)
    res = FT.edit(cf, {k: s_now[k] for k in ("layout", "dictionary", "mode", "op", "turn")},
                  dict(REC.numbers_of(cf)))
    assert res["record"] is None
    assert not [x for x in FK.LOG if x.startswith(("attributes.add", "customNamedValues",
                                                   "CustomFeatureParameter."))]
    assert comp.attributes.itemByName("bam_aruco", "tags") is not None


def test_preset_of_node_is_the_cores_mapping():
    for _gid, c in [(0, c) for c in C.cases("matrix")[:60] if "error" not in c["out"]]:
        spec = TagSpec.from_dict(c["in"])
        cf = _node(spec.settings, spec.numbers)
        s = S.settings_from_stored(spec.settings)
        n = S.numbers_from_params(s, REC.params_mm(cf))
        assert REC.preset_of_node(cf) == PR.preset_of(s, n)


@pytest.mark.parametrize("name,black,role", [
    ("aruco cells t1", (), "cells"), ("aruco white t1", (), "tile"), ("tag tile t1", (), "tile"),
    ("Plate", ("Plate",), "cells"), ("aruco id Arm:2 . aruco cells t1", (), "cells"),
    ("aruco id Arm:2 . tag tile t1", (), "tile"), ("Body1", (), "tile")])
def test_body_role(name, black, role):
    assert REC.body_role(FK.BRepBody(None, None, name), black) == role
