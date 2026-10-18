"""Auto id (aruco_studio/core/autoid.py): hand cases, then properties over
seeded random documents -- determinism, uniqueness, stability with the
ledger, reproducibility without it, typed ids, capacity, grids -- and one
mutant that proves the uniqueness gate can fail."""
from __future__ import annotations

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
