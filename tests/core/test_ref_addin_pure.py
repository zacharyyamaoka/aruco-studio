"""Pure sections of three REF add-in suites, ported by hand.

These suites load a stand-in adsk, so they are not run as copies; the
sections below test only pure functions, and every check is REF's, as an
assert. The other sections of the same suites drive Fusion objects (they
belong to the Fusion adapter, M4) or the table's UI (studio, M3).
"""
import itertools

import pytest

from aruco_studio.core import export_rows as C, marker_table as T, markers as M
from aruco_studio.core import numbering as N, restructure as R, slabs as SL

SYNC = "tests/test_aruco_extrude_sync.py"
TABLE = "tests/test_aruco_marker_table.py"
EXPORT = "tests/test_aruco_export_dialog.py"


# --------------------------------------------- REF tests/test_aruco_extrude_sync.py


@pytest.mark.ref(SYNC, "== 4. restructure_plan: every pair of node structures")
def test_extrude_sync__s04__restructure_plan_every_pair_of_node_structures():
    structures = set()
    NUMS = []
    for wo, wh, bo, bh in ((0, 2, 2, -0.6), (0, 2, 2, 0.6), (-1, 2, 1, -0.6), (0, 2, 2.5, 0.5),
                           (0, 2, -0.5, 1.0), (0, 0.6, 0, -0.6), (0, 2, 0, 0.6)):
        NUMS.append({"white_offset": wo, "white_height": wh, "black_offset": bo, "black_height": bh,
                     "pin_length": 1.5, "pin_tol": 0.15, "pin_size": 3.0})
    for mode, op, has_body, pin, n in itertools.product(("both", "black", "white"), ("join", "new"),
                                                        (True, False), ("none", "triangle"), NUMS):
        p = SL.plan(mode, op, has_body, n, pin)
        structures.add((p.op, tuple(p.parts)))
    structures = sorted(structures, key=str)
    bad = []
    for (op_old, old), (op_new, new) in itertools.product(structures, structures):
        rp = R.restructure_plan(list(old), op_old, list(new), op_new)
        bf = set(old)
        cb = {r for r in old if R.has_combine(r, op_old)}
        made_cb = set()
        for r in rp["delete_roles"]:
            bf.discard(r)
            cb.discard(r)
        for r in rp["delete_combines"]:
            cb.discard(r)
        for r in rp["create_roles"]:
            bf.add(r)
            if R.has_combine(r, op_new):
                cb.add(r)
                made_cb.add(r)
        for r in rp["create_combines"]:
            cb.add(r)
            made_cb.add(r)
        want_cb = {r for r in new if R.has_combine(r, op_new)}
        retarget_ok = all(r in made_cb for r in ("tile", "pocket")
                          if op_old != op_new and r in want_cb)
        keep_ok = set(rp["keep"]) == set(old) & set(new)
        if bf != set(new) or cb != want_cb or not retarget_ok or not keep_ok:
            bad.append(((op_old, old), (op_new, new), rp))
    # REF: "the plan turns each old node into exactly the new one, retargets what
    # the op changes, keeps what stays"
    assert not bad, bad[:3]
    rp = R.restructure_plan(["pattern", "recess"], None, ["tile", "pocket", "pattern"], "join")
    # REF: "Black only -> White + black joined: tile and pocket made, the recess goes"
    assert rp == {"delete_roles": ["recess"], "delete_combines": [], "create_roles": ["tile", "pocket"],
                  "create_combines": [], "keep": ["pattern"]}, rp
    rp = R.restructure_plan(["tile", "pocket", "pattern"], "join", ["tile", "pocket", "pattern"], "new")
    # REF: "Join -> New body: the tile's join goes, the pocket's cut is made again"
    assert rp == {"delete_roles": [], "delete_combines": ["tile", "pocket"], "create_roles": [],
                  "create_combines": ["pocket"], "keep": ["tile", "pocket", "pattern"]}, rp


# --------------------------------------------- REF tests/test_aruco_marker_table.py


@pytest.mark.ref(TABLE, "names: the same string as the IDs node")
def test_marker_table__s01__names_the_same_string_as_the_ids_node():
    for path, key in (("Arm:1+Plate:2", "top"), ("", "front"), ("A:1+B:1+C:3+D:2", "k")):
        assert T.name_of(path, key) == N.instance_name(path, key), T.name_of(path, key)
        assert T.split_name(T.name_of(path, key)) == (path, key)
    assert T.SEP == M.KEY_SEP
    words = ["Plate:10|a", "Plate:2|a", "plate:3|b", "Arm:1+Plate:1|x"]
    assert all(T.natural_key(w) == N.natural_key(w) for w in words)
    for d in ("DICT_4X4_50", "DICT_4X4_1000", "DICT_5X5_100", "DICT_ARUCO_ORIGINAL",
              "DICT_APRILTAG_36h11", ""):
        assert T.family(d) == N.family(d), d
    assert T.where("A:1+B:1+C:3+D:2", "top") == "… › B:1 › C:3 › D:2 · top"
    assert T.where("Arm:1+Plate:2", "top") == "Arm:1 › Plate:2 · top"
    assert T.where("", "front") == "(root) · front"
    assert T.kind_text("single") == "single"
    assert T.kind_text("grid", 3, 1) == "grid 3×1"
    assert T.kind_text("charuco", 4, 2) == "ChArUco 4×2"
    assert T.dict_text("DICT_4X4_50") == "4X4_50" and T.dict_text("DICT_APRILTAG_36h11") == "APRILTAG_36h11"
    assert T.ids_text([3]) == "#3"
    assert T.ids_text([13, 14, 15, 16]) == "#13-16"
    assert T.ids_text([]) == "—"
    assert T.status_html("prints · Aruco Marker <2>") == "prints · Aruco Marker &lt;2&gt;"
    assert T.status_html("hidden", "muted") == "<span style='color:#808080'>hidden</span>"
    assert "#a06800" in T.status_html("x", "warn") and "#c00000" in T.status_html("x", "error")


@pytest.mark.ref(TABLE, "rows from a tag spec (TagSpec or its dict)")
def test_marker_table__s02__rows_from_a_tag_spec_tagspec_or_its_dict():
    single = M.TagSpec(dictionary="DICT_4X4_50", marker_id=7, marker_length_m=0.02)
    grid = M.TagSpec(dictionary="DICT_4X4_50", marker_id=3, marker_length_m=0.014, layout="grid",
                     cols=3, rows=1, separation_m=0.004)
    charuco = M.TagSpec(dictionary="DICT_5X5_100", marker_id=10, marker_length_m=0.009,
                        layout="charuco", cols=4, rows=2, square_length_m=0.012, raise_m=0.0006)
    frame = ([1.0, 2.0, 3.0], [1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0])
    r1 = T.make_row("Arm:1+Plate:2", "top", single, frame=frame)
    assert (r1.name == "Arm:1+Plate:2|top" and r1.marker == "single · 4X4_50" and r1.ids == [7]
            and abs(r1.size_cm[0] - single.tile_size_m[0] * 100) < 1e-9)
    assert r1.pick_paths == ("Arm:1+Plate:2",)
    r2 = T.make_row("Rig:1", "strip", grid.to_dict(), frame=frame)
    assert r2.ids == [3, 4, 5] and r2.marker == "grid 3×1 · 4X4_50", (r2.ids, r2.marker)
    r3 = T.make_row("Rig:1", "board", charuco, ids=[20, 21, 22, 23], frame=frame)
    assert (r3.ids == [20, 21, 22, 23] and r3.marker == "ChArUco 4×2 · 5X5_100"
            and abs(r3.top_cm - 0.06) < 1e-9), (r3.ids, r3.marker, r3.top_cm)
    m16 = [1, 0, 0, 5.0, 0, 1, 0, 6.0, 0, 0, 1, 7.0, 0, 0, 0, 1]
    r4 = T.make_row("", "front", single, frame=m16)
    assert (r4.frame[0] == [5.0, 6.0, 7.0] and r4.frame[1] == [1, 0, 0] and r4.path == ""
            and r4.where == "(root) · front")
    hidden = T.make_row("Box:1+Plate:1", "top", single, hidden=True)
    rows = T.order([hidden, T.make_row("Plate:10", "top", single), T.make_row("Plate:2", "top", single),
                    T.make_row("Arm:1+Plate:1", "top", single)])
    assert [r.name for r in rows] == ["Arm:1+Plate:1|top", "Plate:2|top", "Plate:10|top",
                                      "Box:1+Plate:1|top"]
    dup = T.duplicates([T.make_row("A:1", "t", single), T.make_row("A:2", "t", single),
                        T.make_row("A:3", "t", single, hidden=True),
                        T.make_row("B:1", "t", M.TagSpec(dictionary="DICT_4X4_1000", marker_id=7))])
    assert dup == {"aruco4x4#7": ["A:1|t", "A:2|t", "B:1|t"]}, dup
    assert T.COLUMNS == ("tag", "ids", "marker", "status")
    assert T.ratio() == "6:2:3:5" and T.ratio(lead=True) == "1:6:2:3:5"
    assert T.column("status") == 3 and T.column("status", True) == 4
    assert [T.cell_id(c, 2, 5) for c in T.COLUMNS] == ["l2_5", "i2_5", "m2_5", "s2_5"]


# --------------------------------------------- REF tests/test_aruco_export_dialog.py


@pytest.mark.ref(EXPORT, "the progress bar (Zach 2026-10-10: estimated time, what it is working on)")
def test_export_dialog__s03__the_progress_bar():
    assert C.eta_text(1, 10, 2.0).startswith("estimating")
    assert C.eta_text(2, 10, 4.0) == "about 15 s left", C.eta_text(2, 10, 4.0)
    assert C.eta_text(5, 100, 10.0) == "about 3 min left", C.eta_text(5, 100, 10.0)
    m = C.progress_message(4, 10, "ArUco id 12 . Body6", 8.0)
    assert "Part 5 of 10" in m and "s left" in m and "Writing: ArUco id 12 . Body6" in m, m
    assert C.progress_message(0, 36, "x", 0.1).startswith("Part 1 of 36")
    assert "50%" not in C.progress_message(1, 2, "Gear 50% . Body1", 1.0)
