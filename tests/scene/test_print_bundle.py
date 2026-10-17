"""M6.5 / M6.6 (M6a.1): both kinds in one scene, one ledger, one print bundle.

* a mixed 40-tag scene (20 stickers / 20 printed, two dictionary families)
  renumbers unique per family across kinds; a sticker #3 and a printed #3
  are one duplicate; a second renumber changes nothing; the ledger keeps its
  shape;
* its print bundle (scene/export.py): the PDF holds exactly the sticker
  tags, each at true size within 0.15 mm at 600 dpi, the 100 mm bar 100.0 +/-
  0.1 mm, a labelled sticker's letters where the plan's label boxes are;
  print3d/ holds exactly the 3D tags' bodies, parts.json loads through
  core.beds.load_parts, aruco_tags.3mf has one object per part with the cells
  on the black slot; markers.json names every tag with its kind and file;
  every exported id is marked printed.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

import pytest

from aruco_studio.core import beds as BD
from aruco_studio.core import numbering as N
from aruco_studio.plan import target as T
from aruco_studio.plan.spec import TagSpec
from aruco_studio.scene import Scene, renumber
from aruco_studio.scene import export as EX
from aruco_studio.scene import ids as SI

STK = {"rule": 1, "by": "sticker"}
LAB = {"on": True, "rule": 3, "place": "black", "content": "id", "nozzle_mm": 0.2}


def mixed(n=40):
    sc = Scene(name="mixed")
    for k in range(n):
        sticker = k % 2 == 0
        d = "DICT_4X4_50" if (k // 2) % 2 == 0 else "DICT_5X5_100"
        s = {"layout": "single", "dictionary": d}
        if sticker:
            s["make"] = dict(STK)
            if k % 4 == 0:
                s["label"] = dict(LAB)
            tgt = T.box(30, 30, 0)
        else:
            s.update(mode="both", op="new")
            tgt = T.box(30, 30, 3)
        sc.add(TagSpec(settings=s, target=tgt), x_mm=(k % 8) * 60.0, y_mm=(k // 8) * 60.0)
    return sc


def kinds(sc):
    plans = sc.plans()
    return {t.name: plans[t.name].data["made_by"] for t in sc.tags}


def test_forty_tags_both_kinds_one_ledger():
    sc = mixed()
    k = kinds(sc)
    assert sum(v == "sticker" for v in k.values()) == 20
    # a sticker #3 and a printed #3 of one family: ONE duplicate, across kinds
    a = next(t for t in sc.tags if k[t.name] == "sticker"
             and t.spec.settings["dictionary"] == "DICT_4X4_50")
    b = next(t for t in sc.tags if k[t.name] == "print3d"
             and t.spec.settings["dictionary"] == "DICT_4X4_50")
    for t in sc.tags:
        t.spec.numbers = dict(t.spec.numbers, marker_id=sc.tags.index(t) + 10)
    a.spec.numbers["marker_id"] = b.spec.numbers["marker_id"] = 3
    dup = SI.duplicates(sc)
    fam = N.family("DICT_4X4_50")
    assert dup == {f"{fam}#3": sorted([a.name, b.name], key=[t.name for t in sc.tags].index)}
    rep = renumber(sc)
    assert rep["ok"] and rep["changed"]
    assert SI.duplicates(sc) == {}
    rep2 = renumber(sc)
    assert rep2["changed"] == []
    assert sc.ledger["schema"] == N.LEDGER_SCHEMA == "bam_aruco_ids_ledger/1"
    assert kinds(sc) == k                                  # numbering never changes the kind


@pytest.fixture(scope="module")
def bundle():
    sc = mixed()
    renumber(sc)
    plans = sc.plans()
    got = EX.print_bundle(sc, plans, page="letter", date="2026-10-16", when="2026-10-16T21:00")
    return sc, plans, got


def test_the_sheet_holds_exactly_the_stickers_at_true_size(bundle):
    from aruco_studio.verify import sheet_check as SC
    sc, plans, got = bundle
    f = got["files"]
    summ = json.loads(f["sheet.json"])
    stickers = {t.name for t in sc.tags if plans[t.name].data["made_by"] == "sticker"}
    assert {s["key"] for s in summ["stickers"]} == stickers
    rep = SC.check_sheet(f["sheet.pdf"], summ, {k: p.to_dict() for k, p in plans.items()})
    assert rep["ok"], [r for r in rep["stickers"] if not r["ok"]][:2]
    assert rep["worst"]["side_err_mm"] <= 0.15
    for b in rep["pages"]:
        assert abs(b["mm_bar"] - 100.0) <= 0.1 and abs(b["in_bar"] - 101.6) <= 0.1
    labelled = [r for r in rep["stickers"] if r["label"]["boxes"]]
    assert labelled and all(r["label"]["iou_min"] >= 0.9 for r in labelled)
    # every id of every sticker read off the pages
    read = sorted(i for r in rep["stickers"] for i in r["ids"]["ids_read"])
    want = sorted(i for k in stickers for i in plans[k].data["ids"])
    assert read == want
    assert f["sheet.pdf"].startswith(b"%PDF-") and f["sheet.svg"].startswith(b"<svg")
    singles = [k for k in f if re.match(r"images/DICT_\w+_\d+\.(png|svg)$", k)]
    assert len(singles) == 2 * len(stickers)


def test_print3d_holds_exactly_the_3d_tags(bundle):
    sc, plans, got = bundle
    f = got["files"]
    solid = {t.name for t in sc.tags if plans[t.name].data["made_by"] == "print3d"}
    man = json.loads(f["print3d/parts.json"])
    assert man["schema"] == BD.MANIFEST_SCHEMA
    assert {p["component"] for p in man["parts"]} == solid
    for p in man["parts"]:
        roles = sorted(b["role"] for b in p["bodies"])
        assert "cells" in roles and "tile" in roles and "other" not in roles   # New body tags
    parts, failures, warnings = BD.load_parts(man, f.__getitem__)
    assert not failures and len(parts) == len(solid)
    for prt in parts:
        assert {b.role for b in prt.bodies} == {"tile", "cells"} and prt.tags
    z = zipfile.ZipFile(io.BytesIO(f["print3d/aruco_tags.3mf"]))
    model = z.read("3D/3dmodel.model").decode("utf-8")
    assert len(re.findall(r'<object id="\d+" type="model">', model)) == len(solid)
    cfg = z.read("Metadata/Slic3r_PE_model.config").decode("utf-8")
    # every object's cells volume on the black slot (2), its tile on the white (1)
    ex = re.findall(r'<metadata type="volume" key="extruder" value="(\d)"/>', cfg)
    names = re.findall(r'<metadata type="volume" key="name" value="([^"]+)"/>', cfg)
    assert len(ex) == len(names) and ex
    for nm, e in zip(names, ex):
        assert e == ("2" if "cells" in nm else "1"), (nm, e)


def test_markers_json_and_the_ledger(bundle):
    sc, plans, got = bundle
    m = json.loads(got["files"]["markers.json"])
    assert m["schema"] == "arucostudio.markers/1"
    rows = {r["name"]: r for r in m["tags"]}
    assert set(rows) == {t.name for t in sc.tags}
    for t in sc.tags:
        r = rows[t.name]
        d = plans[t.name].data
        assert r["made_by"] == d["made_by"] and r["ids"] == d["ids"]
        assert r["file"] == ("sheet.pdf" if d["made_by"] == "sticker" else
                             "print3d/aruco_tags.3mf")
        assert len(r["frame_mm"]) == 16
    led = N.Ledger.from_any(got["ledger"])
    for t in sc.tags:
        d = plans[t.name].data
        fam = N.family(d["marker"]["dictionary"])
        for i in d["ids"]:
            assert i in led.printed.get(fam, {}), (t.name, i)
    assert got["report"]["rows"] == ["20 stickers -> sheet.pdf (1 page, Letter)",
                                     "20 parts -> aruco_tags.3mf (%d bed%s)"
                                     % (got["report"]["beds"],
                                        "s" if got["report"]["beds"] != 1 else "")]


def test_proofs_put_the_3d_tags_on_paper_too():
    sc = mixed(8)
    renumber(sc)
    got = EX.print_bundle(sc, proofs=True, date="2026-10-16")
    summ = json.loads(got["files"]["sheet.json"])
    assert len(summ["stickers"]) == 8
    assert {s["made_by"] for s in summ["stickers"]} == {"sticker", "print3d"}


def test_hidden_and_refused_tags_are_left_out():
    sc = mixed(6)
    renumber(sc)
    sc.tags[0].hidden = True
    sc.add(TagSpec(settings={"layout": "single", "make": dict(STK)}, target=T.box(2, 2, 0)))
    got = EX.print_bundle(sc, date="2026-10-16")
    rows = {r["name"]: r for r in json.loads(got["files"]["markers.json"])["tags"]}
    assert rows[sc.tags[0].name]["file"] is None
    assert rows[sc.tags[-1].name]["file"] is None
    summ = json.loads(got["files"]["sheet.json"])
    assert sc.tags[0].name not in {s["key"] for s in summ["stickers"]}
