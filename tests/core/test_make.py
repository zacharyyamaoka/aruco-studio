"""M6a: how a tag is made (core/make.py) and the preset as the machine
(core/presets.py). Checks M6a.2 and M6.7 of the design notes."""
from __future__ import annotations

import copy
import sys
import types
from pathlib import Path

import pytest

from aruco_studio.core import form as F
from aruco_studio.core import make as MK
from aruco_studio.core import presets as P
from aruco_studio.core import prusa as PR
from aruco_studio.core._ref_compat import aruco_core

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ref_path  # noqa: E402


# ------------------------------------------------------------ make_of

def test_absent_is_a_legacy_3d_tag():
    m, notes = MK.make_of({})
    assert m.by == "print3d" and m.legacy and m.rule is None and not notes
    m, notes = MK.make_of({"make": None})
    assert m.legacy and not notes


def test_a_sticker_reads_with_its_defaults():
    m, notes = MK.make_of({"make": {"rule": 1, "by": "sticker"}})
    assert not notes
    assert (m.by, m.rule, m.thickness_mm, m.margin_mm, m.cut_line, m.perimeter) == \
        ("sticker", 1, 0.1, 0.0, True, "marker")
    assert m.top_mm == pytest.approx(0.11)
    assert m.to_dict() == {"rule": 1, "by": "sticker", "thickness_mm": 0.1, "margin_mm": 0.0,
                           "cut_line": True, "perimeter": "marker"}


@pytest.mark.parametrize("make,field", [
    ({"rule": 9}, "settings.make"), ({"rule": 1, "by": "laser"}, "settings.make.by"),
    ("sticker", "settings.make")])
def test_junk_reads_as_3d_with_a_warn(make, field):
    m, notes = MK.make_of({"make": make})
    assert m.by == "print3d" and not m.sticker
    assert [(f, lv) for f, lv, _t in notes] == [(field, "warn")]
    assert "3D printed" in notes[0][2]


@pytest.mark.parametrize("key,bad,good", [("thickness_mm", -1.0, 0.05), ("thickness_mm", 5.0, 2.0),
                                          ("margin_mm", 75.0, 50.0), ("margin_mm", -2.0, 0.0)])
def test_out_of_range_numbers_are_clamped_with_a_warn(key, bad, good):
    m, notes = MK.make_of({"make": {"rule": 1, "by": "sticker", key: bad}})
    assert m.sticker and getattr(m, key) == good
    assert [(f, lv) for f, lv, _t in notes] == [(f"settings.make.{key}", "warn")]


def test_holes_absent_is_avoid_and_junk_warns():
    assert MK.holes_of({}) == ("avoid", [])
    assert MK.holes_of({"holes": "ignore"}) == ("ignore", [])
    h, notes = MK.holes_of({"holes": "maybe"})
    assert h == "avoid" and notes[0][:2] == ("settings.holes", "warn")


def test_the_new_tag_rule_stamps_make_holes_and_the_new_label_rule():
    from aruco_studio.core import label as L
    from aruco_studio.core import settings as S
    s = S.default_settings()
    out = F.new_tag_settings(s, True)
    assert out["make"] == {"rule": 1, "by": "print3d"}
    assert out["holes"] == "avoid" and out["label"]["rule"] == L.NEW_RULE == 4   # rule 4: audit 2026-10-17
    st = F.new_tag_settings(s, True, preset=P.sticker_preset())
    assert st["make"]["by"] == "sticker" and st["make"]["thickness_mm"] == 0.1
    assert (st["mode"], st["op"], st["pin"]) == ("both", "new", "none") and "trim" not in st
    # made_by overrides the preset (scripts)
    assert F.new_tag_settings(s, True, preset=P.default_preset(), made_by="sticker")["make"][
        "by"] == "sticker"
    assert "make" not in s and s["label"]["rule"] == L.RULE == 2      # a copy; REF's default kept


# ------------------------------------------------------------ presets (M6a.2, M6.7)

def test_a_preset_without_a_kind_is_a_3d_printer():
    assert P.kind_of(P.default_preset()) == "print3d"
    assert "kind" not in P.normalise(P.default_preset())["profile"]      # REF's shape kept
    assert P.kind_of({"profile": {"kind": "laser"}}) == "print3d"


def test_the_sticker_built_ins_letter_first():
    a, b = P.sticker_builtins()
    assert a["name"] == "Sticker · Letter · 600 dpi" and b["name"] == "Sticker · A4 · 600 dpi"
    pr = a["profile"]
    assert (pr["kind"], pr["dpi"], pr["page"], pr["stock_mm"], pr["sheet"]) == \
        ("sticker", 600, "letter", 0.1, "spaced")
    assert pr["line_mm"] == round(25.4 / 600, 6) == 0.042333
    assert a["cells"]["min_mm"] == 1.0 and a["label"]["nozzle_mm"] == 0.2


def test_the_sticker_letter_built_in_applied():
    """M6a.2 / M6.7: cells {rule 1, of cell, mm 0.042333} and make {by sticker,
    thickness 0.1, perimeter marker}."""
    from aruco_studio.server import newtag as N
    from aruco_studio.plan import target as T
    p = P.sticker_preset("letter")
    assert P.cell_setting(p) == {"rule": 1, "of": "cell", "mm": 0.042333, "min_mm": 1.0}
    sp = N.new_spec("single", T.box(40, 40, 0).to_dict(), p)
    s = F.new_tag_settings(sp["settings"], False, preset=p)
    assert s["cells"] == {"rule": 1, "of": "cell", "mm": 0.042333, "min_mm": 1.0}
    mk = MK.make_of(s)[0]
    assert (mk.by, mk.thickness_mm, mk.perimeter) == ("sticker", 0.1, "marker")
    back = P.preset_of(s, sp["numbers"])
    assert P.kind_of(back) == "sticker" and P.same_print(back, p)
    assert P.cell_setting(back) == P.cell_setting(p)


def test_catalog_all_lists_both_kinds_and_collections():
    st = P.MemoryStore()
    st.text = None
    cat = P.catalog_all(st, None)
    names = [n for n, _p, _k in cat["items"]]
    assert names[:3] == ["Default", "Sticker · Letter · 600 dpi", "Sticker · A4 · 600 dpi"]
    cols = {c["id"]: c["names"] for c in P.collections(cat["items"])}
    assert cols["print3d"] == ["Default"]
    assert cols["sticker"] == ["Sticker · Letter · 600 dpi", "Sticker · A4 · 600 dpi"]
    # REF's own catalog is untouched (its suites pin it)
    assert [n for n, _p, _k in P.catalog(st, None)["items"]] == ["Default"]


def test_normalise_keeps_the_machine_keys():
    p = P.sticker_preset("a4")
    q = P.normalise(copy.deepcopy(p))
    assert q == p
    bad = copy.deepcopy(p)
    bad["profile"].update(dpi="lots", page="napkin", sheet="loose", stock_mm=9.0)
    q = P.normalise(bad)
    assert (q["profile"]["dpi"], q["profile"]["page"], q["profile"]["sheet"],
            q["profile"]["stock_mm"]) == (600, "letter", "spaced", 0.1)


def _ref_normalise():
    """REF's pinned aruco_presets.normalise, exec'd from the blob (read only)."""
    src = ref_path.show("ArucoMarkers/aruco_presets.py").decode("utf-8")
    saved = {k: sys.modules.get(k) for k in ("aruco_core", "aruco_prusa")}
    core = types.ModuleType("aruco_core")
    core.module = aruco_core.module
    sys.modules["aruco_core"], sys.modules["aruco_prusa"] = core, PR
    try:
        g = {"__name__": "ref_aruco_presets"}
        exec(compile(src, "REF:ArucoMarkers/aruco_presets.py", "exec"), g)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return g["normalise"]


@pytest.mark.skipif(not (ref_path.REF / ".git").exists(), reason="REF is not here")
def test_a_studio_file_loads_in_ref_and_a_ref_file_here():
    """M6.7 / M6a.2: REF's normalise drops the machine keys and keeps the rest;
    a REF file (no kind) reads here as all 3D, its keys intact."""
    ref_norm = _ref_normalise()
    for p in [P.default_preset()] + P.sticker_builtins():
        theirs = ref_norm(copy.deepcopy(p))
        mine = copy.deepcopy(p)
        for k in P.KIND_KEYS:
            mine["profile"].pop(k, None)
        for sect in ("cells", "tag", "label"):
            assert theirs[sect] == mine[sect], sect
        assert "kind" not in theirs["profile"]
        # the round trip: REF's output read here is REF's output
        assert P.normalise(theirs) == ref_norm(theirs)
        assert P.kind_of(P.normalise(theirs)) == "print3d"


def test_the_words():
    m = MK.make_of({"make": {"rule": 1, "by": "sticker"}})[0]
    assert MK.words(m, 600, "letter") == "Made by: Printed sticker · 600 dpi · Letter"
    assert MK.words(MK.Make()) == "Made by: 3D printed"
    assert MK.badge("sticker") == "2D" and MK.badge("print3d") == "3D"
