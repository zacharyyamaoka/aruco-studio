"""M2.6: per-field validation (ARCHITECTURE 5.6). One case per row of the
field table (plan/fields.py, the same list GET /api/form serves): a value
out of range gives an Issue whose `field` is that row's key path; a wrong
TYPE is a SpecTypeError naming the key path (the server's 422)."""
from __future__ import annotations

import copy

import pytest

from aruco_studio.plan import SpecTypeError, TagSpec, check, plan_tag
from aruco_studio.plan.fields import fields, form
from aruco_studio.plan import target as T

ROWS = [r for r in fields() if "bad" in r]


def base_spec(layout="single"):
    return {"schema": "arucostudio.tagspec/1",
            "settings": {"layout": layout, "mode": "both", "op": "new",
                         "label": {"on": True, "place": "white"},
                         "trim": {"rule": 1, "axes": "both", "margin_mm": 0.0}},
            "numbers": {}, "target": T.box(80, 60, 3).to_dict(), "name": "", "key": "k"}


def put(d, path, value):
    keys = path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = copy.deepcopy(value)


def test_every_row_of_the_table_has_a_bad_value_or_is_free():
    """Every field has a row; rows without a bad value are free (bool, text)."""
    for r in fields():
        assert r["path"] and r["type"]
        if "bad" not in r:
            assert r["type"] in ("bool", "text", "mm") and r["path"].startswith(
                ("settings.grow", "settings.label", "name", "key")), r["path"]
    paths = {r["path"] for r in fields()}
    for p in ("settings.layout", "settings.dictionary", "numbers.marker_id", "numbers.size",
              "numbers.square", "settings.force", "settings.quiet_modules", "settings.cells",
              "settings.mode", "settings.op", "numbers.white_offset", "numbers.white_height",
              "numbers.black_offset", "numbers.black_height", "settings.turn",
              "settings.origin_v", "settings.corner_mark", "settings.pin", "numbers.pin_size",
              "numbers.pin_length", "numbers.pin_tol", "settings.label.on",
              "settings.label.cap_mm", "settings.label.nozzle_mm", "settings.label.rule",
              "settings.trim", "target.w_mm", "target.h_mm", "target.loops_mm",
              "target.body_mm", "name", "key"):
        assert p in paths, p


@pytest.mark.parametrize("row", ROWS, ids=[r["path"] for r in ROWS])
def test_a_bad_value_is_an_issue_on_its_own_field(row):
    layout = (row.get("layouts") or ["single"])[0]
    if row["path"] == "settings.force":
        layout = "grid"
    d = base_spec(layout)
    if row["path"] == "settings.trim.margin_mm":
        d["settings"]["trim"] = {"rule": 1, "axes": "both", "margin_mm": row["bad"]}
    else:
        put(d, row["path"], row["bad"])
    spec = TagSpec.from_dict(d)
    p = plan_tag(spec)
    got = [w for w in p.data["warnings"] if w["field"] == row["path"]]
    assert got, (row["path"], p.data["warnings"])
    levels = {w["level"] for w in got}
    assert row["level"] in levels, (row["path"], got)
    if row["level"] == "error":
        assert not p.ok and p.data["errors"]
    # check() alone says the same (the plan runs it first)
    assert any(i.field == row["path"] for i in check(spec)) or row["path"] == "numbers.marker_id"


@pytest.mark.parametrize("path,value", [
    ("settings.layout", 3), ("settings.quiet_modules", "1.0"), ("settings.turn", "90"),
    ("settings.grow", 1), ("settings.label", "on"), ("numbers.size", "28"),
    ("numbers.marker_id", True), ("target.w_mm", "40"), ("target.loops_mm", [[[0, "a"]]]),
    ("target.has_body", "yes"), ("target.body_mm", {"u0": 0}), ("name", 7),
    ("schema", "arucostudio.tagspec/9")])
def test_a_wrong_type_names_its_key_path(path, value):
    d = base_spec()
    put(d, path, value)
    with pytest.raises(SpecTypeError) as e:
        TagSpec.from_dict(d)
    assert e.value.path.startswith(path.split("[")[0]), (e.value.path, path)
    p = plan_tag(d)                                 # never raises: a refusal on that path
    assert not p.ok and p.data["warnings"][0]["field"].startswith(path)


def test_a_good_spec_has_no_error():
    for layout in ("single", "grid", "charuco"):
        p = plan_tag(base_spec(layout))
        assert p.ok, p.data["errors"]
        assert all(w["field"] for w in p.data["warnings"])


def test_form_lists_every_row():
    f = form()
    assert f["schema"] == "arucostudio.form/1"
    assert {r["path"] for r in f["fields"]} == {r["path"] for r in fields()}
    assert set(f["groups"]) >= {r["group"] for r in f["fields"]}
