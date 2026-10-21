"""assign_ids through the online Studio's facade (web_api.call -> web_ids ->
core.autoid): the contract's shapes (contract.ts IdRequest / IdResult), the
ledger round trip through JSON, and bad requests answered in words. The
rules themselves: tests/core/test_autoid.py."""
from __future__ import annotations

import json

import pytest

from aruco_studio import web_api as W
from aruco_studio import web_ids


def item(key, kind="single", dictionary="DICT_4X4_50", count=1, first_id=None):
    return {"key": key, "type": kind, "dictionary": dictionary, "count": count, "first_id": first_id}


def call(payload):
    return json.loads(W.call("assign_ids", json.dumps(payload)))


def test_the_answer_has_the_contracts_shape():
    out = call({"items": [item("a"), item("g", "grid", count=6), item("c", "charuco", "DICT_5X5_100", 10),
                          item("t", first_id=7)]})
    res = out["result"]
    assert set(res) == {"items", "ledger", "warnings"}
    assert [a["key"] for a in res["items"]] == ["a", "g", "c", "t"]
    for a in res["items"]:
        assert set(a) == {"key", "first_id", "ids", "driven"}
        assert isinstance(a["first_id"], int) and all(isinstance(i, int) for i in a["ids"])
    assert [a["driven"] for a in res["items"]] == [True, True, True, False]
    assert set(res["ledger"]) == {"a", "g", "c"}
    assert res["warnings"] == []


def test_the_ledger_round_trips_through_the_document():
    first = call({"items": [item("a"), item("b")]})["result"]
    stored = json.loads(json.dumps(first["ledger"]))
    second = call({"items": [item("n1"), item("b"), item("n2", "grid", count=4)], "ledger": stored})["result"]
    ids = {a["key"]: a["ids"] for a in second["items"]}
    assert ids["b"] == next(a["ids"] for a in first["items"] if a["key"] == "b")
    assert "a" not in second["ledger"] and {"b", "n1", "n2"} <= set(second["ledger"])


def test_a_collision_is_an_issue_on_the_id_row_with_the_items_key():
    res = call({"items": [item("x", first_id=3), item("y", first_id=3)]})["result"]
    assert sorted(w["key"] for w in res["warnings"]) == ["x", "y"]
    assert {(w["field"], w["level"]) for w in res["warnings"]} == {("marker.first_id", "error")}


@pytest.mark.parametrize("payload", [
    {},
    {"items": "a"},
    {"items": [item("a")], "ledger": [1]},
    {"items": [item("a"), item("a")]},
    {"items": [item("a", dictionary="DICT_NOPE")]},
    {"items": [item("a", count=2)]},
])
def test_a_bad_request_is_answered_in_words(payload):
    out = call(payload)
    assert set(out) == {"error"} and out["error"].startswith("ValueError: ")


def test_the_facade_is_the_core():
    from aruco_studio.core import autoid
    items = [item("a"), item("b", "grid", count=6)]
    assert web_ids.assign_ids({"items": items, "ledger": {"a": 3}}) == autoid.assign(items, {"a": 3},
                                                                                   mode=autoid.DEFAULT_MODE)
