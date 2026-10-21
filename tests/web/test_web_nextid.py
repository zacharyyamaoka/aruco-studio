"""Next id (aruco_studio/core/autoid.py rule 3', IdRequest.mode "next", the
default since 2026-10-20 night) through the online Studio's facade
(web_api.call -> web_ids -> core.autoid). Zach: "As I copy paste new single
markers, how are the new IDs calculated? It seems like it would be simplest
if they simply increment".

A new driven item takes the first free block after the highest id in use in
its family (ledger, typed, held, reserved, and what this call gave out), in
document order; past the dictionary it wraps to the lowest free block with an
info issue. Rules 1 and 2 are unchanged: ledger ids never move (the property
test below, 200 seeded documents), typed ids are exact. Hash mode is still
there when asked for by name."""
from __future__ import annotations

import json
import random

import pytest

from aruco_studio import web_api as W
from aruco_studio import web_ids
from aruco_studio.core import autoid
from aruco_studio.core import dictionary as D
from aruco_studio.core.numbering import family

TRIALS = 200
DICTS = ["DICT_4X4_50", "DICT_4X4_250", "DICT_5X5_100", "DICT_5X5_250", "DICT_6X6_250"]


def item(key, kind="single", dictionary="DICT_4X4_50", count=1, first_id=None):
    return {"key": key, "type": kind, "dictionary": dictionary, "count": count, "first_id": first_id}


def call(payload):
    return json.loads(W.call("assign_ids", json.dumps(payload)))["result"]


def ids_of(res):
    return {a["key"]: a["ids"] for a in res["items"]}


def capacity(name):
    return int(D.dictionary_info(name)["capacity"])


def paste_three():
    """One marker, then three pastes of it, each its own auto id call with the
    ledger the last one returned (as the planner asks): the four ids."""
    items = [item("a")]
    res = call({"items": items})
    for n in range(3):
        items = items + [item(f"copy{n}")]
        res = call({"items": items, "ledger": res["ledger"]})
    return [ids_of(res)[it["key"]][0] for it in items]


# ------------------------------------------------------------------ hand cases

def test_one_marker_then_three_pastes_are_consecutive():
    assert paste_three() == [0, 1, 2, 3]


def test_pasting_number_five_three_times_in_one_call_gives_six_seven_eight():
    res = call({"items": [item("five"), item("p1"), item("p2"), item("p3")], "ledger": {"five": 5}})
    assert [a["ids"] for a in res["items"]] == [[5], [6], [7], [8]]
    assert res["warnings"] == []
    # document order, not key order
    res = call({"items": [item("five"), item("z"), item("m"), item("a")], "ledger": {"five": 5}})
    assert [a["ids"] for a in res["items"]] == [[5], [6], [7], [8]]


def test_ids_start_at_0_in_an_empty_document():
    res = call({"items": [item("x")]})
    assert ids_of(res) == {"x": [0]} and res["ledger"] == {"x": 0}
    res = call({"items": [item("g", "grid", count=4), item("s")]})
    assert [a["ids"] for a in res["items"]] == [[0, 1, 2, 3], [4]]


def test_a_typed_10_counts_as_in_use_and_is_stepped_over():
    res = call({"items": [item("a"), item("t", first_id=10), item("n")], "ledger": {"a": 7}})
    assert ids_of(res) == {"a": [7], "t": [10], "n": [11]}
    # a reserved id is in use the same way: never handed out, numbered past
    res = call({"items": [item("a"), item("n")], "ledger": {"a": 7}, "reserved": [10]})
    assert ids_of(res)["n"] == [11]


def test_freed_ids_are_not_reused_before_the_wrap():
    first = call({"items": [item("a"), item("b"), item("c")]})
    assert [a["ids"] for a in first["items"]] == [[0], [1], [2]]
    res = call({"items": [item("a"), item("c"), item("d")], "ledger": first["ledger"]})
    assert ids_of(res) == {"a": [0], "c": [2], "d": [3]}


def test_families_are_counted_separately():
    res = call({"items": [item("a4"), item("a5", dictionary="DICT_5X5_100"), item("n4"),
                          item("n5", dictionary="DICT_5X5_100"), item("n4b", dictionary="DICT_4X4_250")],
                "ledger": {"a4": 20, "a5": 3}})
    # DICT_4X4_50 and DICT_4X4_250 are one family (aruco4x4): one count; 5x5 its own
    assert ids_of(res) == {"a4": [20], "a5": [3], "n4": [21], "n5": [4], "n4b": [22]}
    assert family("DICT_4X4_50") == family("DICT_4X4_250") != family("DICT_5X5_100")


def test_a_grids_block_is_contiguous_right_after_the_highest_id():
    res = call({"items": [item("a"), item("g", "grid", count=6), item("s"),
                          item("c", "charuco", "DICT_4X4_250", 10)], "ledger": {"a": 5}})
    assert ids_of(res) == {"a": [5], "g": list(range(6, 12)), "s": [12], "c": list(range(13, 23))}


def test_past_the_last_id_it_wraps_to_the_lowest_free_block_with_an_info_issue():
    res = call({"items": [item("hi"), item("t", first_id=0), item("n"), item("g", "grid", count=4)],
                "ledger": {"hi": 49}, "reserved": [1]})
    assert ids_of(res) == {"hi": [49], "t": [0], "n": [2], "g": [3, 4, 5, 6]}
    assert res["warnings"] == [
        {"field": "marker.first_id", "level": "info", "key": "n",
         "text": "past DICT_4X4_50's last id 49: it wraps to the lowest free id #2"},
        {"field": "marker.first_id", "level": "info", "key": "g",
         "text": "past DICT_4X4_50's last id 49: it wraps to the lowest free block #3–6"},
    ]
    # a block that no longer fits after the highest wraps too
    res = call({"items": [item("a"), item("g", "grid", count=4)], "ledger": {"a": 47}})
    assert ids_of(res)["g"] == [0, 1, 2, 3]
    assert [w["level"] for w in res["warnings"]] == ["info"]
    # and a full dictionary is the same error as before
    full = call({"items": [item(f"s{k:02d}") for k in range(51)]})
    assert ids_of(full)["s50"] == []
    assert any(w["key"] == "s50" and w["level"] == "error" and "is full" in w["text"] for w in full["warnings"])


def test_next_ignores_start():
    assert call({"items": [item("a"), item("b")], "start": 30}) == call({"items": [item("a"), item("b")]})


def test_hash_mode_still_works_when_asked_for():
    items = [item("a"), item("b", "grid", count=6), item("t", first_id=2)]
    hashed = call({"items": items, "mode": "hash"})
    assert hashed == web_ids.assign_ids({"items": items, "mode": "hash"}) == autoid.assign(items)
    # each driven item at its sha256 preferred id (none of these three collide)
    for it in items[:2]:
        want = autoid.preferred(it["key"], it["dictionary"], it["count"], capacity(it["dictionary"]))
        assert ids_of(hashed)[it["key"]] == list(range(want, want + it["count"]))
    assert ids_of(hashed)["t"] == [2] and hashed["warnings"] == []
    # the same items by default: after the typed 2, in document order
    assert ids_of(call({"items": items})) == {"a": [3], "b": list(range(4, 10)), "t": [2]}


def test_the_paste_test_goes_red_with_the_default_switched_back_to_hash(monkeypatch):
    monkeypatch.setattr(autoid, "DEFAULT_MODE", "hash")
    assert paste_three() != [0, 1, 2, 3]


# ------------------------------------------------------------------ properties

def random_items(rng, prefix, n):
    out = []
    for k in range(n):
        name = rng.choice(DICTS)
        kind = rng.choice(["single", "single", "grid", "charuco"])
        count = 1 if kind == "single" else rng.randint(1, 8)
        typed = rng.random() < 0.15
        out.append(item(f"{prefix}{k}-{rng.randrange(10 ** 6)}", kind, name, count,
                        rng.randrange(capacity(name) - count + 1) if typed else None))
    return out


def overlaps(res, items):
    """Two driven ranges of one family printing one id, unwarned."""
    meta = {it["key"]: it for it in items}
    owner = {}
    for a in res["items"]:
        for i in a["ids"]:
            owner.setdefault((family(meta[a["key"]]["dictionary"]), i), []).append(a["key"])
    warned = {w.get("key") for w in res["warnings"] if w["level"] in ("warn", "error")}
    return [keys for keys in owner.values() if len(keys) > 1 and not set(keys) <= warned]


@pytest.mark.parametrize("seed", range(TRIALS))
def test_ledger_ids_never_move_when_items_are_added_or_removed(seed):
    rng = random.Random(seed)
    items = random_items(rng, "k", rng.randint(1, 20))
    res = call({"items": items})
    assert overlaps(res, items) == []
    ledger = res["ledger"]
    for step in range(3):
        kept = [it for it in items if rng.random() < 0.75]
        added = random_items(rng, f"n{step}-", rng.randint(0, 6))
        nxt = list(kept)
        for it in added:
            nxt.insert(rng.randint(0, len(nxt)), it)
        before = {a["key"]: a["ids"] for a in res["items"]}
        res = call({"items": nxt, "ledger": ledger})
        added_keys = {it["key"] for it in added}
        for it, a in zip(nxt, res["items"]):
            if it["first_id"] is None and it["key"] in ledger and it["key"] not in added_keys:
                # rule 1: the survivor keeps its ledger id, whatever was added or removed
                # (a new typed id over it is flagged as an overlap, never moves it)
                assert a["ids"] == before[it["key"]], (seed, step, it["key"])
        assert overlaps(res, nxt) == []
        ledger = res["ledger"]
        items = nxt
    # and it settles: the same items with their own ledger change nothing (a
    # wrap's info issue is said once, when the id is first given out)
    again = call({"items": items, "ledger": ledger})
    assert (again["items"], again["ledger"]) == (res["items"], res["ledger"])
