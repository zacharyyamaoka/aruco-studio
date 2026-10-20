"""Auto id (aruco_studio/core/autoid.py): hand cases, then properties over
seeded random documents -- determinism, uniqueness, stability with the
ledger, reproducibility without it, typed ids, capacity, grids -- and one
mutant that proves the uniqueness gate can fail."""
from __future__ import annotations

import hashlib
import json
import random
import sys
import types
from pathlib import Path

import pytest

from aruco_studio.core import autoid as AI
from aruco_studio.core import board as B
from aruco_studio.core.numbering import capacity, family

DICTS = ("DICT_4X4_250", "DICT_5X5_100", "DICT_4X4_50")
SEEDS = range(200)


def count_of(kind: str, cols: int = 1, rows: int = 1) -> int:
    """Markers a feature prints, from the core's board code (a ChArUco
    board's are its white squares). Counted against the biggest dictionary
    (marker_count refuses a board its dictionary cannot hold)."""
    return B.marker_count(B.BoardSpec(kind, "DICT_APRILTAG_36h10", 0, 0.01, rows=rows, cols=cols,
                                      separation_m=0.002, square_length_m=0.012))


def item(key, kind="single", dictionary="DICT_4X4_50", cols=1, rows=1, first_id=None):
    return {"key": key, "type": kind, "dictionary": dictionary,
            "count": count_of(kind, cols, rows), "first_id": first_id}


def by_key(res):
    return {a["key"]: a for a in res["items"]}


def errors_of(res, level="error"):
    out = {}
    for w in res["warnings"]:
        if w["level"] == level:
            out.setdefault(w["key"], []).append(w["text"])
    return out


def random_item(rng, key, typed_share=0.15):
    kind = rng.choice(AI.TYPES)
    cols, rows = {"single": (1, 1), "grid": (rng.randint(1, 4), rng.randint(1, 3)),
                  "charuco": (rng.randint(2, 5), rng.randint(2, 4))}[kind]
    dic = rng.choice(DICTS)
    it = item(key, kind, dic, cols, rows)
    if rng.random() < typed_share and capacity(dic) >= it["count"]:
        it["first_id"] = rng.randrange(0, capacity(dic) - it["count"] + 1)
    return it


def random_doc(seed, n=None):
    rng = random.Random(seed)
    n = n if n is not None else rng.randint(1, 30)
    keys = rng.sample(range(10 ** 9), n)
    return rng, [random_item(rng, f"feature-{k:x}") for k in keys]


def violations(res, items):
    """What the uniqueness gate refuses: an assigned range outside its
    dictionary or not contiguous, an item without ids and without an error,
    two ranges of one family that overlap unless a typed id is involved and
    both carry an error."""
    meta = {it["key"]: it for it in items}
    errs = errors_of(res)
    bad, owner = [], {}
    for a in res["items"]:
        it = meta[a["key"]]
        ids = a["ids"]
        if not ids:
            if a["key"] not in errs:
                bad.append(f"{a['key']}: no ids and no error")
            continue
        if ids != list(range(a["first_id"], a["first_id"] + it["count"])):
            bad.append(f"{a['key']}: ids {ids} not {it['count']} contiguous from {a['first_id']}")
        if ids[0] < 0 or ids[-1] >= capacity(it["dictionary"]):
            bad.append(f"{a['key']}: ids {ids[0]}..{ids[-1]} outside {it['dictionary']}")
        for i in ids:
            owner.setdefault((family(it["dictionary"]), i), []).append(a["key"])
    for (_fam, i), keys in owner.items():
        if len(keys) < 2:
            continue
        typed = [k for k in keys if meta[k]["first_id"] is not None]
        flagged = all(k in errs for k in keys)
        if not typed or not flagged:
            bad.append(f"id {i} printed by {keys} (typed {typed}, flagged {flagged})")
    return bad


# ------------------------------------------------------------------ hand cases

def test_the_preferred_id_is_sha256_of_dictionary_and_key_pinned():
    # documents saved without a ledger rebuild with these: never change the recipe
    assert AI.preferred("a", "DICT_4X4_50", 1, 50) == 45
    assert AI.preferred("b", "DICT_4X4_50", 6, 50) == 29
    assert AI.preferred("a", "DICT_4X4_50", 50, 50) == 0
    assert AI.preferred("a", "DICT_4X4_50", 60, 50) == 0


def test_a_lone_driven_item_takes_its_preferred_block():
    res = AI.assign([item("b", "grid", cols=3, rows=2)])
    assert res["items"] == [{"key": "b", "first_id": 29, "ids": list(range(29, 35)), "driven": True}]
    assert res["ledger"] == {"b": 29}
    assert res["warnings"] == []


def test_a_typed_id_is_honoured_exactly_and_driven_ones_route_around_it():
    pref = AI.preferred("a", "DICT_4X4_50", 1, 50)                     # 45
    res = AI.assign([item("a"), item("t", first_id=pref)])
    got = by_key(res)
    assert got["t"] == {"key": "t", "first_id": pref, "ids": [pref], "driven": False}
    assert got["a"]["first_id"] == pref + 1 and got["a"]["driven"]
    assert res["ledger"] == {"a": pref + 1}                             # typed ids are not ledgered
    assert res["warnings"] == []


def test_a_probe_wraps_round_the_end_of_the_dictionary():
    # a 6-block whose preferred start is 29 in a dictionary whose 29..49 is typed away
    res = AI.assign([item("b", "grid", cols=3, rows=2), item("t", "grid", cols=7, rows=3, first_id=29)])
    got = by_key(res)
    assert got["t"]["ids"] == list(range(29, 50))
    assert got["b"]["ids"] == list(range(0, 6))


def test_two_typed_ranges_that_overlap_both_keep_their_ids_and_both_are_flagged():
    res = AI.assign([item("x", "grid", cols=2, rows=2, first_id=10), item("y", first_id=12)])
    got = by_key(res)
    assert got["x"]["ids"] == [10, 11, 12, 13] and got["y"]["ids"] == [12]
    errs = errors_of(res)
    assert set(errs) == {"x", "y"}
    assert any("y" in t for t in errs["x"])
    assert any("x" in t for t in errs["y"])
    assert all(w["field"] == "marker.first_id" for w in res["warnings"])


def test_families_share_ids_and_different_bit_sizes_do_not():
    res = AI.assign([item("p", dictionary="DICT_4X4_50", first_id=7),
                     item("q", dictionary="DICT_4X4_1000", first_id=7),
                     item("r", dictionary="DICT_5X5_50", first_id=7)])
    assert set(errors_of(res)) == {"p", "q"}


def test_the_ledger_keeps_an_id_that_is_not_the_preferred_one():
    res = AI.assign([item("a")], ledger={"a": 3})
    assert by_key(res)["a"]["ids"] == [3] and res["ledger"] == {"a": 3}


def test_a_new_typed_id_over_a_ledger_id_is_flagged_and_the_ledger_id_stays():
    res = AI.assign([item("a"), item("t", first_id=3)], ledger={"a": 3})
    got = by_key(res)
    assert got["a"]["ids"] == [3] and got["t"]["ids"] == [3]
    assert set(errors_of(res)) == {"a", "t"}
    assert res["ledger"] == {"a": 3}


def test_a_ledger_id_that_no_longer_fits_its_dictionary_moves_with_a_warning():
    res = AI.assign([item("a", dictionary="DICT_4X4_50")], ledger={"a": 120})
    got = by_key(res)["a"]
    assert got["ids"] == [45] and res["ledger"] == {"a": 45}
    assert "a" in errors_of(res, "warn")


def test_a_typed_items_old_ledger_id_is_held_for_it_and_comes_back():
    first = AI.assign([item("a"), item("b")])
    a_id = by_key(first)["a"]["first_id"]
    # a new key that hashes onto a's old id routes round it
    c = next(f"c{i}" for i in range(10 ** 4) if AI.preferred(f"c{i}", "DICT_4X4_50", 1, 50) == a_id)
    typed = AI.assign([item("a", first_id=20), item(c)], ledger=first["ledger"])
    assert typed["ledger"]["a"] == a_id                        # still remembered
    assert by_key(typed)["a"]["ids"] == [20]
    assert by_key(typed)[c]["ids"] == [a_id + 1]
    back = AI.assign([item("a"), item(c)], ledger=typed["ledger"])
    assert by_key(back)["a"]["ids"] == [a_id]


def test_a_held_id_is_handed_out_only_when_nothing_else_is_free():
    led = {"a": 0}
    items = [item("a", first_id=49)] + [item(f"s{i:02d}") for i in range(48)]
    res = AI.assign(items, ledger=led)
    got = by_key(res)
    taken = sorted(i for a in res["items"] for i in a["ids"])
    assert taken == list(range(1, 50))                          # 0 stays held for "a"
    res = AI.assign(items + [item("s48")], ledger=led)
    assert by_key(res)["s48"]["ids"] == [0]
    assert "s48" in errors_of(res, "warn")
    assert got["a"]["ids"] == [49]


def test_sixty_singles_in_dict_4x4_50_name_a_bigger_dictionary():
    res = AI.assign([item(f"s{i:02d}") for i in range(60)])
    errs = errors_of(res)
    placed = [a for a in res["items"] if a["ids"]]
    assert len(placed) == 50 and len(errs) == 10
    assert all(len(t) == 1 and "DICT_4X4_100" in t[0] for t in errs.values())
    assert all(by_key(res)[k]["ids"] == [] and k not in res["ledger"] for k in errs)
    assert sorted(i for a in placed for i in a["ids"]) == list(range(50))


def test_a_full_family_names_the_smallest_bigger_dictionary_that_fits():
    # 4X4_100's 50..99 typed away: a 6-block needs 4X4_250
    res = AI.assign([item("t", "grid", "DICT_4X4_100", cols=10, rows=10, first_id=0),
                     item("b", "grid", "DICT_4X4_100", cols=3, rows=2)])
    assert "DICT_4X4_250" in errors_of(res)["b"][0]
    res = AI.assign([item("big", "grid", "DICT_4X4_50", cols=10, rows=6)])     # 60 > 50
    assert "DICT_4X4_100" in errors_of(res)["big"][0]
    res = AI.assign([item("o", "grid", "DICT_ARUCO_ORIGINAL", cols=40, rows=30)])
    assert "no bigger dictionary" in errors_of(res)["o"][0]


def test_a_typed_range_outside_its_dictionary_is_an_error_with_no_ids():
    res = AI.assign([item("g", "grid", cols=3, rows=2, first_id=47)])
    assert by_key(res)["g"] == {"key": "g", "first_id": 47, "ids": [], "driven": False}
    assert "44 is the last first id" in errors_of(res)["g"][0]


def test_a_charuco_board_takes_its_board_code_count_contiguously():
    n = count_of("charuco", 5, 4)
    assert n == 10                                              # white squares of 5 x 4
    res = AI.assign([item("c", "charuco", "DICT_5X5_100", cols=5, rows=4)])
    a = by_key(res)["c"]
    assert a["ids"] == list(range(a["first_id"], a["first_id"] + n)) and a["ids"][-1] < 100


@pytest.mark.parametrize("bad", [
    {"key": "", "type": "single", "dictionary": "DICT_4X4_50", "count": 1, "first_id": None},
    {"key": "a", "type": "board", "dictionary": "DICT_4X4_50", "count": 1, "first_id": None},
    {"key": "a", "type": "single", "dictionary": "DICT_9X9_1", "count": 1, "first_id": None},
    {"key": "a", "type": "single", "dictionary": "DICT_4X4_50", "count": 2, "first_id": None},
    {"key": "a", "type": "grid", "dictionary": "DICT_4X4_50", "count": 0, "first_id": None},
    {"key": "a", "type": "single", "dictionary": "DICT_4X4_50", "count": 1, "first_id": 2.5},
    {"key": "a", "type": "single", "dictionary": "DICT_4X4_50", "count": 1, "first_id": True},
])
def test_a_malformed_item_raises(bad):
    with pytest.raises(ValueError):
        AI.assign([bad])


def test_duplicate_keys_raise():
    with pytest.raises(ValueError, match="twice"):
        AI.assign([item("a"), item("a")])


def test_unreadable_ledger_entries_are_ignored():
    res = AI.assign([item("a")], ledger={"a": "3", "b": -1, "c": True})
    assert by_key(res)["a"]["ids"] == [45]


# ------------------------------------------------------------------ properties

@pytest.mark.parametrize("seed", SEEDS)
def test_uniqueness(seed):
    _rng, items = random_doc(seed)
    res = AI.assign(items)
    assert violations(res, items) == []
    assert [a["key"] for a in res["items"]] == [it["key"] for it in items]


@pytest.mark.parametrize("seed", SEEDS)
def test_determinism_shuffled_items_give_the_same_answer(seed):
    rng, items = random_doc(seed)
    ledger = AI.assign(items[: len(items) // 2])["ledger"] if seed % 2 else None
    a = AI.assign(items, ledger)
    shuffled = items[:]
    rng.shuffle(shuffled)
    b = AI.assign(shuffled, ledger)
    assert by_key(a) == by_key(b)
    assert a["ledger"] == b["ledger"] and a["warnings"] == b["warnings"]


@pytest.mark.parametrize("seed", SEEDS)
def test_reproducibility_same_keys_no_ledger_same_ids(seed):
    _rng, items = random_doc(seed)
    assert AI.assign(items) == AI.assign([dict(it) for it in items])


@pytest.mark.parametrize("seed", SEEDS)
def test_stability_with_the_ledger_survivors_keep_their_ids(seed):
    rng, items = random_doc(seed)
    first = AI.assign(items)
    keep = items[:]
    for _ in range(min(rng.randint(1, 3), len(keep))):
        keep.pop(rng.randrange(len(keep)))
    added = [random_item(rng, f"new-{seed}-{k}") for k in range(rng.randint(1, 5))]
    doc = keep + added
    rng.shuffle(doc)
    second = AI.assign(doc, first["ledger"])
    before, after = by_key(first), by_key(second)
    for it in keep:
        if before[it["key"]]["ids"]:
            assert after[it["key"]]["ids"] == before[it["key"]]["ids"], it["key"]
    assert violations(second, doc) == []
    again = AI.assign(doc, second["ledger"])                    # and it settles
    assert by_key(again) == after


# --------------------------------------------------------------------- mutant

PROBE = "start = next((s for s in starts if not clash(it, s, True)), None)"


def test_the_uniqueness_gate_catches_a_probe_that_skips_the_overlap_check(monkeypatch):
    src = Path(AI.__file__).read_text(encoding="utf-8")
    assert src.count(PROBE) == 1, "the probe line moved: update this mutant"
    mutant = types.ModuleType("aruco_studio.core._autoid_mutant")
    mutant.__package__ = "aruco_studio.core"
    monkeypatch.setitem(sys.modules, mutant.__name__, mutant)
    exec(compile(src.replace(PROBE, "start = want"), AI.__file__, "exec"), mutant.__dict__)
    red = sum(1 for seed in SEEDS if violations(mutant.assign(random_doc(seed)[1]),
                                                random_doc(seed)[1]))
    assert red > 0


# ------------------------------------------------------------------ Re-ID

def hash_request(seed):
    """One random request in today's terms (no mode, start or fresh): a
    document, a ledger on a third of the seeds, reserved ids (a list or a
    map per family) on half."""
    rng, items = random_doc(seed)
    ledger = AI.assign(items[: len(items) // 2])["ledger"] if seed % 3 == 1 else None
    reserved = None
    if seed % 4 == 2:
        reserved = rng.sample(range(60), rng.randint(1, 8))
    elif seed % 4 == 3:
        reserved = {"4x4": rng.sample(range(60), rng.randint(1, 5)), "aruco5x5": [rng.randrange(100)]}
    return items, ledger, reserved


def hash_digest(**re_id):
    """sha256 over the JSON of 200 random requests' answers, in order."""
    h = hashlib.sha256()
    for seed in SEEDS:
        items, ledger, reserved = hash_request(seed)
        res = AI.assign(items, ledger, reserved, **re_id)
        h.update(json.dumps(res, ensure_ascii=False).encode("utf-8") + b"\n")
    return h.hexdigest()


# the digest of hash_digest() taken on main @ 51f39de, before Re-ID existed
HASH_DIGEST = "aeb0e284fe570bbd64d48a5c752329302978c3ab1ccfeb1a8028502f281cc731"


def seq(items, ledger=None, reserved=None, start=0, fresh=False):
    return AI.assign(items, ledger, reserved, mode="sequential", start=start, fresh=fresh)


def blocks(res):
    return [(a["key"], a["ids"]) for a in res["items"]]


def test_hash_mode_is_byte_identical_to_before_re_id():
    assert hash_digest() == HASH_DIGEST
    assert hash_digest(mode="hash", start=0, fresh=False) == HASH_DIGEST
    assert hash_digest(mode="hash", start=37) == HASH_DIGEST            # start is sequential's


def test_sequential_numbers_twelve_mixed_items_contiguously_in_document_order():
    shapes = [("single",), ("grid", 3, 2), ("single",), ("grid", 2, 2), ("grid", 4, 1), ("single",),
              ("single",), ("grid", 1, 3), ("grid", 2, 1), ("single",), ("grid", 3, 3), ("single",)]
    items = [item(f"m{11 - k:02d}", s[0], "DICT_4X4_250" if k % 3 else "DICT_4X4_50", *s[1:])
             for k, s in enumerate(shapes)]                 # keys sort against document order
    res = seq(items)
    assert res["warnings"] == []
    nxt = 0
    for it, a in zip(items, res["items"]):
        assert a["key"] == it["key"] and a["driven"]
        assert a["ids"] == list(range(nxt, nxt + it["count"])), a
        nxt += it["count"]
    assert nxt == 34
    assert res["ledger"] == {a["key"]: a["first_id"] for a in res["items"]}
    assert violations(res, items) == []


def test_sequential_starts_at_start():
    res = seq([item("b", dictionary="DICT_4X4_250"), item("a", "grid", "DICT_4X4_250", cols=3, rows=2),
               item("c", dictionary="DICT_4X4_250")], start=100)
    assert blocks(res) == [("b", [100]), ("a", list(range(101, 107))), ("c", [107])]
    assert res["warnings"] == []


def test_each_family_has_its_own_counter_from_start():
    items = [item("a"), item("p", dictionary="DICT_5X5_100"), item("g", "grid", "DICT_4X4_1000", cols=2, rows=1),
             item("q", "grid", "DICT_5X5_50", cols=3, rows=1), item("b", dictionary="DICT_4X4_250")]
    assert blocks(seq(items, start=5)) == [("a", [5]), ("p", [5]), ("g", [6, 7]), ("q", [6, 7, 8]), ("b", [8])]


def test_sequential_skips_typed_ids():
    items = [item("a"), item("t1", first_id=2), item("g", "grid", cols=2, rows=2), item("b"),
             item("t2", "grid", cols=2, rows=1, first_id=5), item("c")]
    res = seq(items)
    assert res["warnings"] == []
    assert blocks(res) == [("a", [0]), ("t1", [2]), ("g", [7, 8, 9, 10]), ("b", [11]), ("t2", [5, 6]), ("c", [12])]
    assert res["ledger"] == {"a": 0, "g": 7, "b": 11, "c": 12}


def test_sequential_skips_reserved_ids():
    items = [item("a"), item("b"), item("g", "grid", cols=2, rows=1), item("p", dictionary="DICT_5X5_50")]
    assert blocks(seq(items, reserved=[0, 2, 5])) == [("a", [1]), ("b", [3]), ("g", [6, 7]), ("p", [1])]
    assert blocks(seq(items, reserved={"4x4": [0, 2, 5]})) == [("a", [1]), ("b", [3]), ("g", [6, 7]), ("p", [0])]


def test_without_fresh_ledgered_items_keep_their_ids_and_only_new_ones_are_numbered():
    items = [item("a"), item("b"), item("c"), item("d"), item("e")]
    res = seq(items, ledger={"b": 1, "d": 40, "gone": 2})
    assert blocks(res) == [("a", [0]), ("b", [1]), ("c", [2]), ("d", [40]), ("e", [3])]
    assert res["ledger"] == {"a": 0, "b": 1, "c": 2, "d": 40, "e": 3}
    again = seq(list(reversed(items)) + [item("f")], ledger=res["ledger"])
    assert {k: v["ids"] for k, v in by_key(again).items()} == {**{k: i for k, i in blocks(res)}, "f": [4]}


def test_fresh_discards_the_ledger_in_either_mode():
    items = [item("a"), item("b"), item("c")]
    led = {"a": 30, "b": 0, "gone": 9}
    res = seq(items, ledger=led, fresh=True)
    assert blocks(res) == [("a", [0]), ("b", [1]), ("c", [2])]
    assert res["ledger"] == {"a": 0, "b": 1, "c": 2}
    assert AI.assign(items, led, mode="hash", fresh=True) == AI.assign(items)
    # a typed item's old ledger id is not held nor kept any more
    held = AI.assign([item("t", first_id=20), item("x")], {"t": 5})
    assert held["ledger"]["t"] == 5
    fresh = seq([item("t", first_id=20), item("x")], ledger={"t": 5}, fresh=True)
    assert fresh["ledger"] == {"x": 0}


def test_fresh_typed_ids_still_win_and_collisions_are_flagged():
    items = [item("a"), item("x", first_id=0), item("y", first_id=0)]
    res = seq(items, ledger={"a": 0}, fresh=True)
    assert blocks(res) == [("a", [1]), ("x", [0]), ("y", [0])]
    assert set(errors_of(res)) == {"x", "y"}


def test_sequential_full_dictionary_is_todays_error():
    items = [item(f"s{59 - i:02d}") for i in range(60)]
    res = seq(items)
    assert [a["ids"] for a in res["items"][:50]] == [[i] for i in range(50)]
    errs = errors_of(res)
    assert set(errs) == {a["key"] for a in res["items"][50:]}
    assert all(len(t) == 1 and "DICT_4X4_100" in t[0] for t in errs.values())


def test_a_start_past_the_dictionary_wraps_round_as_the_hash_probe_does():
    # DICT_4X4_50 stops at 49: its family's counter wraps to 0; a 5x5 family is its own
    res = seq([item("a"), item("g", "grid", cols=3, rows=1), item("b", dictionary="DICT_5X5_250")], start=100)
    assert blocks(res) == [("a", [0]), ("g", [1, 2, 3]), ("b", [100])]
    # ... no longer silently: one warning for DICT_4X4_50, keyed to no item (test_web_reid.py)
    assert [(w["level"], "key" in w) for w in res["warnings"]] == [("warn", False)]


@pytest.mark.parametrize("kw", [{"mode": "random"}, {"mode": None}, {"start": -1}, {"start": 1.5},
                                {"start": True}, {"start": "3"}, {"fresh": "yes"}, {"fresh": 1}])
def test_bad_re_id_arguments_raise(kw):
    with pytest.raises(ValueError):
        AI.assign([item("a")], **kw)


@pytest.mark.parametrize("seed", SEEDS)
def test_sequential_uniqueness_with_and_without_fresh(seed):
    items, ledger, reserved = hash_request(seed)
    start = seed % 7 * 9
    for fresh in (False, True):
        res = seq(items, ledger, reserved, start=start, fresh=fresh)
        assert violations(res, items) == []
        assert [a["key"] for a in res["items"]] == [it["key"] for it in items]
        if fresh:                                   # the old ledger is gone: only what was given out now
            assert res["ledger"] == {a["key"]: a["first_id"] for a in res["items"] if a["driven"] and a["ids"]}


@pytest.mark.parametrize("seed", SEEDS)
def test_sequential_stability_without_fresh_survivors_keep_their_ids(seed):
    rng, items = random_doc(seed)
    first = seq(items)
    keep = items[:]
    for _ in range(min(rng.randint(1, 3), len(keep))):
        keep.pop(rng.randrange(len(keep)))
    doc = keep + [random_item(rng, f"new-{seed}-{k}") for k in range(rng.randint(1, 5))]
    rng.shuffle(doc)
    second = seq(doc, first["ledger"])
    before, after = by_key(first), by_key(second)
    for it in keep:
        if before[it["key"]]["ids"]:
            assert after[it["key"]]["ids"] == before[it["key"]]["ids"], it["key"]
    assert violations(second, doc) == []
    # and it settles (a refused item's first_id is only where its probe began)
    assert blocks(seq(doc, second["ledger"])) == blocks(second)


# the sequential probe with the typed-id check taken out of clash()
SEQ_MUTANT = ("start = next((s for s in starts if not [k for k in clash(it, s, True) if not "
              "(sequential and k in {x.key for x in its if x.first_id is not None})]), None)")


def test_the_uniqueness_gate_catches_sequential_skipping_the_typed_id_check(monkeypatch):
    src = Path(AI.__file__).read_text(encoding="utf-8")
    assert src.count(PROBE) == 1, "the probe line moved: update this mutant"
    mutant = types.ModuleType("aruco_studio.core._autoid_seq_mutant")
    mutant.__package__ = "aruco_studio.core"
    monkeypatch.setitem(sys.modules, mutant.__name__, mutant)
    exec(compile(src.replace(PROBE, SEQ_MUTANT), AI.__file__, "exec"), mutant.__dict__)
    docs = [random_doc(seed)[1] for seed in SEEDS]
    red = sum(1 for items in docs if violations(mutant.assign(items, mode="sequential"), items))
    assert red > 0
    # the same mutant leaves hash mode alone: it is the sequential gate that goes red
    assert all(mutant.assign(items) == AI.assign(items) for items in docs)
