"""Next id (aruco_studio/core/autoid.py rule 3', IdRequest.mode "next", the
default) through the online Studio's facade (web_api.call -> web_ids ->
core.autoid).

Version 3 (Zach, 2026-11-13): "when you copy paste markers they should
increment to the next available IDs in order left to right ... from actually
the available IDs, deleted markers need to release". A new driven item takes
the LOWEST free block of its count in its family -- ledger, typed, held and
reserved ids and what this call gave out are in use; an id a removed feature
had is free again at once -- in request order (the Studio sends new markers
in reading order: web/src/model/geom.ts readingOrder). Leaving a gap is
Re-ID's job (mode "sequential" from a start).

Version 2 (2026-10-20 night: "simplest if they simply increment") numbered
after the HIGHEST id in use and reused freed ids only at the wrap; Zach's
version 3 replaces it. Rules 1 and 2 are unchanged: ledger ids never move
(the property test below, 200 seeded documents), typed ids are exact. Hash
mode is still there when asked for by name."""
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


def test_new_markers_fill_the_lowest_free_ids_in_request_order():
    res = call({"items": [item("five"), item("p1"), item("p2"), item("p3")], "ledger": {"five": 5}})
    assert [a["ids"] for a in res["items"]] == [[5], [0], [1], [2]]
    assert res["warnings"] == []
    # request (reading) order, not key order
    res = call({"items": [item("five"), item("z"), item("m"), item("a")], "ledger": {"five": 5}})
    assert [a["ids"] for a in res["items"]] == [[5], [0], [1], [2]]


def test_ids_start_at_0_in_an_empty_document():
    res = call({"items": [item("x")]})
    assert ids_of(res) == {"x": [0]} and res["ledger"] == {"x": 0}
    res = call({"items": [item("g", "grid", count=4), item("s")]})
    assert [a["ids"] for a in res["items"]] == [[0, 1, 2, 3], [4]]


def test_typed_and_reserved_ids_are_in_use_and_stepped_over():
    res = call({"items": [item("a"), item("t", first_id=1), item("n"), item("m")], "ledger": {"a": 0}})
    assert ids_of(res) == {"a": [0], "t": [1], "n": [2], "m": [3]}
    # a reserved id is in use the same way: never handed out
    res = call({"items": [item("a"), item("n")], "ledger": {"a": 0}, "reserved": [1, 2]})
    assert ids_of(res)["n"] == [3]


def test_a_deleted_markers_ids_are_released_at_once():
    first = call({"items": [item("a"), item("b"), item("c")]})
    assert [a["ids"] for a in first["items"]] == [[0], [1], [2]]
    # b deleted, d pasted: d takes b's id
    res = call({"items": [item("a"), item("c"), item("d")], "ledger": first["ledger"]})
    assert ids_of(res) == {"a": [0], "c": [2], "d": [1]}
    # the ledger the Studio keeps after a delete still names b (until the next answer):
    # an id is in use only while its feature is in the request
    res = call({"items": [item("a"), item("c"), item("d")], "ledger": {**first["ledger"], "zz": 1}})
    assert ids_of(res)["d"] == [1]


def test_zachs_page_twelve_singles_a_grid_and_a_gap_pasted_six_fill_it():
    """The 2026-11-13 screenshot: a 5 x 4 grid at #0-19, singles #20-31, the
    #32-58 markers deleted; six pasted copies take #32-37, not #59-64."""
    items = [item("grid", "grid", count=20)] + [item(f"s{k}") for k in range(12)]
    ledger = {"grid": 0, **{f"s{k}": 20 + k for k in range(12)}}
    pasted = [item(f"p{k}") for k in range(6)]
    res = call({"items": items + pasted, "ledger": ledger})
    assert [ids_of(res)[f"p{k}"] for k in range(6)] == [[32], [33], [34], [35], [36], [37]]


def test_families_are_counted_separately():
    res = call({"items": [item("a4"), item("a5", dictionary="DICT_5X5_100"), item("n4"),
                          item("n5", dictionary="DICT_5X5_100"), item("n4b", dictionary="DICT_4X4_250")],
                "ledger": {"a4": 0, "a5": 0}})
    # DICT_4X4_50 and DICT_4X4_250 are one family (aruco4x4): one pool; 5x5 its own
    assert ids_of(res) == {"a4": [0], "a5": [0], "n4": [1], "n5": [1], "n4b": [2]}
    assert family("DICT_4X4_50") == family("DICT_4X4_250") != family("DICT_5X5_100")


def test_a_grids_block_is_the_lowest_free_run_long_enough():
    res = call({"items": [item("a"), item("g", "grid", count=6), item("s"),
                          item("c", "charuco", "DICT_4X4_250", 10)], "ledger": {"a": 5}})
    # 0-4 is too short for six: the grid takes 6-11; the single fills 0; the board 12-21
    assert ids_of(res) == {"a": [5], "g": list(range(6, 12)), "s": [0], "c": list(range(12, 22))}


def test_a_full_dictionary_is_the_same_error_as_before():
    full = call({"items": [item(f"s{k:02d}") for k in range(51)]})
    assert [ids_of(full)[f"s{k:02d}"] for k in range(50)] == [[k] for k in range(50)]
    assert ids_of(full)["s50"] == []
    assert any(w["key"] == "s50" and w["level"] == "error" and "is full" in w["text"] for w in full["warnings"])
    # a typed item's held id is handed out only when nothing else is free
    res = call({"items": [item("t", first_id=40)] + [item(f"s{k:02d}") for k in range(49)],
                "ledger": {"t": 3}})
    assert ids_of(res)["s48"] == [3]
    assert any(w["key"] == "s48" and "held for t" in w["text"] for w in res["warnings"])


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
    # the same items by default: the lowest free, round the typed 2
    assert ids_of(call({"items": items})) == {"a": [0], "b": list(range(3, 9)), "t": [2]}


def test_the_paste_test_goes_red_with_the_default_switched_back_to_hash(monkeypatch):
    monkeypatch.setattr(autoid, "DEFAULT_MODE", "hash")
    assert paste_three() != [0, 1, 2, 3]


def test_the_release_test_goes_red_with_version_2s_after_the_highest(monkeypatch):
    """The ruler can fail: numbering after the highest id in use (version 2)
    would give the pasted copy #3, never the released #1."""
    real = autoid.assign

    def after_highest(items, ledger=None, reserved=None, mode="hash", start=0, fresh=False):
        out = real(items, ledger, reserved, mode, start, fresh)
        if mode == "next":
            top = max((i for a in out["items"] if a["key"] in (ledger or {}) for i in a["ids"]), default=-1)
            for a in out["items"]:
                if a["key"] not in (ledger or {}) and a["ids"]:
                    top += 1
                    a["ids"], a["first_id"] = [top], top
        return out
    monkeypatch.setattr(autoid, "assign", after_highest)
    first = call({"items": [item("a"), item("b"), item("c")]})
    res = call({"items": [item("a"), item("c"), item("d")], "ledger": first["ledger"]})
    assert ids_of(res)["d"] != [1]


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
