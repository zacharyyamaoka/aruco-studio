"""Re-ID through the online Studio's facade (web_api.call -> web_ids ->
core.autoid): IdRequest.mode / start / fresh (contract barrier 8), the
defaults, the ledger round trip and bad requests answered in words. The
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


def page(n=40):
    """Lots of markers on a page: singles and 2 x 2 grids, keys out of order."""
    return [item(f"m{(k * 7) % n:02d}", *(("grid", "DICT_4X4_250", 4) if k % 5 == 4
                                          else ("single", "DICT_4X4_250"))) for k in range(n)]


def test_re_id_a_page_of_hashed_markers_numbers_them_in_document_order():
    items = page()
    hashed = call({"items": items, "mode": "hash"})["result"]
    res = call({"items": items, "ledger": hashed["ledger"], "mode": "sequential", "fresh": True})["result"]
    assert res["warnings"] == []
    nxt = 0
    for it, a in zip(items, res["items"]):
        assert a["key"] == it["key"] and a["ids"] == list(range(nxt, nxt + it["count"]))
        nxt += it["count"]
    assert res["ledger"] == {a["key"]: a["first_id"] for a in res["items"]}
    # the new ledger keeps them there: a hash call with it moves nothing
    again = call({"items": items, "ledger": res["ledger"], "mode": "hash"})["result"]
    assert again["items"] == res["items"]


def test_sequential_from_start_through_json():
    res = call({"items": [item("b", dictionary="DICT_4X4_250"), item("a", "grid", "DICT_4X4_250", 6)],
                "mode": "sequential", "start": 100})["result"]
    assert [a["ids"] for a in res["items"]] == [[100], list(range(101, 107))]


def test_without_fresh_the_ledger_is_honoured():
    res = call({"items": [item("a"), item("b"), item("c")], "ledger": {"b": 30},
                "mode": "sequential"})["result"]
    assert [a["ids"] for a in res["items"]] == [[0], [30], [1]]


def test_omitted_null_and_explicit_defaults_are_the_same_answer():
    base = {"items": page(12), "ledger": {"m03": 5}, "reserved": [0, 1]}
    want = call(base)
    assert call({**base, "mode": "next", "start": 0, "fresh": False}) == want
    assert call({**base, "mode": None, "start": None, "fresh": None}) == want


def test_the_facade_is_the_core():
    from aruco_studio.core import autoid
    items = [item("a"), item("b", "grid", count=6), item("t", first_id=2)]
    req = {"items": items, "ledger": {"a": 9}, "reserved": [0], "mode": "sequential", "start": 1, "fresh": True}
    assert web_ids.assign_ids(req) == autoid.assign(items, {"a": 9}, [0], "sequential", 1, True)


@pytest.mark.parametrize("extra", [
    {"mode": "random"},
    {"mode": 1},
    {"start": -1},
    {"start": 2.5},
    {"start": True},
    {"start": "3"},
    {"fresh": "yes"},
    {"fresh": 1},
])
def test_a_bad_re_id_request_is_answered_in_words(extra):
    out = call({"items": [item("a")], **extra})
    assert set(out) == {"error"} and out["error"].startswith("ValueError: ")


def test_a_start_past_the_dictionary_is_a_warning_keyed_to_no_feature():
    # DICT_4X4_50 stops at 49: start 100 wraps to 0, and says so once, for the request;
    # the family's counter (DICT_4X4_250 is the same 4x4 family) carries on from there
    items = [item("a"), item("g", "grid", count=4), item("b"), item("c", dictionary="DICT_4X4_250")]
    res = call({"items": items, "mode": "sequential", "start": 100, "fresh": True})["result"]
    assert [a["ids"] for a in res["items"]] == [[0], [1, 2, 3, 4], [5], [6]]
    assert res["warnings"] == [{"field": "marker.first_id", "level": "warn",
                                "text": "start 100 is past DICT_4X4_50's last id 49: numbering wraps to 0"}]


@pytest.mark.parametrize("start, warned", [(49, False), (50, True)])
def test_the_wrap_warning_starts_one_past_the_last_id(start, warned):
    res = call({"items": [item("a")], "mode": "sequential", "start": start})["result"]
    assert bool(res["warnings"]) == warned


def test_hash_mode_ignores_start_so_never_warns_of_a_wrap():
    assert call({"items": [item("a"), item("b")], "mode": "hash", "start": 100})["result"]["warnings"] == []
