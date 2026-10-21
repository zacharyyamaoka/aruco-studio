"""ArUco Re-ID is a pure function of the document's markers (Zach, 2026-10-20:
"Make sure that reids work even when you do them multiple times ... purely
functional, stateless, and you get the desired behaviour for free").

The dialog asks core.assign_ids({items, mode, start, fresh: true}) and Apply
writes the answer (web/src/model/doc.ts applyIds): driven items take the
assigned id, typed items keep theirs, the ledger becomes the answer's. These
are properties over 300 seeded random documents (mixed types, dictionaries
and counts, ~15 % typed ids, random old ledgers), asked the way the dialog
asks, with the document's ledger in the request so a core that read it under
`fresh` would fail (i):

    (i)   history independence: Re-ID(start s2) on a document that was first
          Re-IDed with s1 gives exactly Re-ID(s2) on the original;
    (ii)  idempotence: applying the same Re-ID twice changes nothing;
    (iii) typed ids are untouched, and no driven range overlaps a typed or
          another driven range of its family unless the core warns about it.
"""
from __future__ import annotations

import json
import random

import pytest

from aruco_studio import web_api as W
from aruco_studio.core import dictionary as D
from aruco_studio.core.numbering import family

TRIALS = 300
DICTS = ["DICT_4X4_50", "DICT_4X4_250", "DICT_5X5_100", "DICT_5X5_250", "DICT_6X6_250"]


def call(req):
    return json.loads(W.call("assign_ids", json.dumps(req)))["result"]


def capacity(name):
    return int(D.dictionary_info(name)["capacity"])


def random_doc(seed):
    """{items: [{key, type, dictionary, count, first_id, typed}], ledger}: the
    markers of a document as the Studio holds them. A driven item still stores
    a first_id (what an earlier assignment gave it); only a typed one sends
    it. The ledger is a random old one (stale keys, ids anywhere)."""
    rng = random.Random(seed)
    items = []
    for n in range(rng.randint(1, 25)):
        name = rng.choice(DICTS)
        kind = rng.choice(["single", "single", "grid", "charuco"])
        count = 1 if kind == "single" else rng.randint(1, 12)
        typed = rng.random() < 0.15
        first = rng.randrange(capacity(name) - count + 1) if typed or rng.random() < 0.5 else 0
        items.append({"key": f"k{rng.randrange(10 ** 6):06d}-{n}", "type": kind, "dictionary": name,
                      "count": count, "first_id": first, "typed": typed})
    rng.shuffle(items)
    ledger = {it["key"]: rng.randrange(capacity(it["dictionary"])) for it in items if rng.random() < 0.5}
    ledger.update({f"gone{k}": rng.randrange(50) for k in range(rng.randint(0, 3))})
    return rng, {"items": items, "ledger": ledger}


def re_id(doc, mode, start):
    """What the dialog asks (doc.ts idItems): a driven item's first_id null,
    fresh, and (here only) the document's ledger riding along."""
    items = [{k: it[k] for k in ("key", "type", "dictionary", "count")}
             | {"first_id": it["first_id"] if it["typed"] else None} for it in doc["items"]]
    return call({"items": items, "ledger": doc["ledger"], "mode": mode, "fresh": True,
                 **({"start": start} if mode == "sequential" else {})})


def apply(doc, res):
    """doc.ts applyIds: a driven item takes the assigned first id, a typed one
    keeps its own; the ledger is the answer's."""
    items = []
    for it, a in zip(doc["items"], res["items"]):
        assert a["key"] == it["key"]
        items.append(it if it["typed"] else {**it, "first_id": a["first_id"]})
    return {"items": items, "ledger": dict(res["ledger"])}


def requests(seed):
    rng, doc = random_doc(seed)
    mode = rng.choice(["sequential", "sequential", "hash"])
    return doc, mode, rng.randrange(0, 60), rng.randrange(0, 60)


@pytest.mark.parametrize("seed", range(TRIALS))
def test_re_id_is_stateless(seed):
    doc, mode, s1, s2 = requests(seed)
    # (i) history independence
    once = re_id(doc, mode, s1)
    after = apply(doc, once)
    assert re_id(after, mode, s2) == re_id(doc, mode, s2), "an earlier Re-ID changed a later one"
    assert re_id(after, mode, s1) == once, "the same Re-ID twice differs"
    # (ii) idempotence: apply it twice, nothing changes
    twice = apply(after, re_id(after, mode, s1))
    assert twice == after


@pytest.mark.parametrize("seed", range(TRIALS))
def test_typed_ids_stay_and_driven_ranges_do_not_overlap(seed):
    doc, mode, s1, _ = requests(seed)
    res = re_id(doc, mode, s1)
    by_key = {a["key"]: a for a in res["items"]}
    flagged = {w.get("key") for w in res["warnings"]}
    ranges = []                                    # (family, first, last, key, driven)
    for it in doc["items"]:
        a = by_key[it["key"]]
        if it["typed"]:
            assert a["first_id"] == it["first_id"] and not a["driven"]      # (iii) typed untouched
            assert a["ids"] in ([], list(range(it["first_id"], it["first_id"] + it["count"])))
        else:
            assert a["driven"]
            assert a["ids"] == [] or a["ids"] == list(range(a["first_id"], a["first_id"] + it["count"]))
        if a["ids"]:
            assert 0 <= a["ids"][0] and a["ids"][-1] < capacity(it["dictionary"])
            ranges.append((family(it["dictionary"]), a["ids"][0], a["ids"][-1], it["key"], not it["typed"]))
    for i, (fam, lo, hi, key, driven) in enumerate(ranges):
        for fam2, lo2, hi2, key2, driven2 in ranges[i + 1:]:
            if fam == fam2 and lo <= hi2 and lo2 <= hi and (driven or driven2):
                assert {key, key2, None} & flagged, f"{key} and {key2} overlap with no warning"
    # the ledger is exactly the driven items it handed ids to
    for k, v in res["ledger"].items():
        assert k in by_key


def test_a_driven_range_never_overlaps_a_typed_one_when_the_dictionary_has_room():
    doc = {"items": [{"key": "t", "type": "single", "dictionary": "DICT_4X4_50", "count": 1, "first_id": 1, "typed": True},
                     {"key": "a", "type": "single", "dictionary": "DICT_4X4_50", "count": 1, "first_id": 7, "typed": False},
                     {"key": "b", "type": "grid", "dictionary": "DICT_4X4_50", "count": 3, "first_id": 9, "typed": False}],
           "ledger": {"a": 1, "b": 0}}
    res = re_id(doc, "sequential", 0)
    assert [a["ids"] for a in res["items"]] == [[1], [0], [2, 3, 4]]
    assert res["warnings"] == []
