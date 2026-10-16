# REF: tests/test_aruco_numbering.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""G0 of docs/aruco_ids_acceptance.md: the ArUco IDs planner, offline.

Every gate runs over abstract models of the fixture matrix F1-F11 (the same
shapes the Fusion fixtures build): occurrence trees with transforms,
visibility and linked flags, tags of every layout and dictionary family.

Run:  python tests/test_aruco_numbering.py      (stdlib only)
      python tests/test_aruco_numbering.py --json out.json   (gate summary)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
pass  # REF put its own tree on sys.path here (ported: not needed)

from aruco_studio.core import numbering as N  # noqa: E402
from aruco_studio.core import markers as M  # noqa: E402
from aruco_studio.core.markers import OccurrenceRef, OverrideRecord, TagDef, TagSpec  # noqa: E402

PASS = 0
FAIL = []
GATES = {}          # gate -> [ok, ...]


def check(label, condition, detail="", gate=None):
    global PASS
    if gate:
        GATES.setdefault(gate, []).append((label, bool(condition), str(detail)[:200]))
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def T(x=0.0, y=0.0, z=0.0, deg=0.0, axis="z"):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "z":
        R = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    elif axis == "x":
        R = [[1, 0, 0], [0, c, -s], [0, s, c]]
    else:
        R = [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [R[0][0], R[0][1], R[0][2], x, R[1][0], R[1][1], R[1][2], y,
            R[2][0], R[2][1], R[2][2], z, 0, 0, 0, 1]


def tag(component="Tag", key="top", marker_id=0, dictionary="DICT_4X4_50", layout="single",
        rows=1, cols=1, **kw):
    spec = TagSpec(dictionary=dictionary, marker_id=marker_id, marker_length_m=0.03,
                   layout=layout, rows=rows, cols=cols, **kw)
    if layout == "grid":
        spec.separation_m = 0.006
    if layout == "charuco":
        spec.square_length_m = 0.04
    return TagDef(key=key, component=component, spec=spec, origin=[0.0, 0.0, 0.1])


def occ(path, comp, t=None, visible=True, linked=False):
    return OccurrenceRef(path, comp, t or T(), visible, linked)


# ------------------------------------------------------------ the fixtures

def fixtures():
    F = {}
    F["F1"] = ([tag()], [occ("Tag:1", "Tag", T(1, 2, 3))])
    F["F2"] = ([tag()], [occ(f"Tag:{k}", "Tag", T(10 * k)) for k in (1, 2, 3)])
    o3 = [occ("A:1", "A", T(0, 0, 0, 30)), occ("A:1+Tag:1", "Tag", T(5, 0, 0, 30)),
          occ("A:1+B:1", "B", T(0, 5, 0, 30)), occ("A:1+B:1+Tag:1", "Tag", T(0, 5, 2, 75, "x")),
          occ("A:2", "A", T(50, 0, 0, -20)), occ("A:2+B:1", "B", T(50, 5, 0, -20)),
          occ("A:2+B:1+Tag:1", "Tag", T(50, 5, 2, 12, "y")),
          occ("A:2+B:1+Tag:2", "Tag", T(50, 9, 2, 12, "y"))]
    F["F3"] = ([tag()], o3)
    o4 = []
    for s in (1, 2):
        o4.append(occ(f"Sub:{s}", "Sub", T(100 * s)))
        for k in (1, 2):
            o4.append(occ(f"Sub:{s}+Tag:{k}", "Tag", T(100 * s, 10 * k)))
    F["F4"] = ([tag()], o4)
    # a linked actuator: its disc carries the tag; once at the root, once in
    # each of two (local) arms -- 1 and 2 levels deep, twice
    o5 = []
    for a in (1, 2):
        o5.append(occ(f"GIM v1:{a}", "GIM", T(0, 30 * a), linked=True))
        o5.append(occ(f"GIM v1:{a}+Disc:1", "Disc", T(0, 30 * a, 4)))
        o5.append(occ(f"Arm:{a}", "Arm", T(200 * a)))
        o5.append(occ(f"Arm:{a}+GIM v1:1", "GIM", T(200 * a, 0, 10), linked=True))
        o5.append(occ(f"Arm:{a}+GIM v1:1+Disc:1", "Disc", T(200 * a, 0, 14)))
    F["F5"] = ([tag("Disc", marker_id=3)], o5)
    # a linked arm that itself holds a linked actuator (xref in an xref)
    o6 = []
    for a in (1, 2):
        o6 += [occ(f"Arm v2:{a}", "ArmL", T(300 * a), linked=True),
               occ(f"Arm v2:{a}+GIM v1:1", "GIM", T(300 * a, 0, 5), linked=True),
               occ(f"Arm v2:{a}+GIM v1:1+Disc:1", "Disc", T(300 * a, 0, 9)),
               occ(f"Arm v2:{a}+Strip:1", "Strip", T(300 * a, 9, 0))]
    F["F6"] = ([tag("Disc", marker_id=3),
                tag("Strip", "strip", 10, layout="charuco", rows=2, cols=8)], o6)
    lay = [tag("Single", "top", 0), tag("Grid", "board", 0, layout="grid", rows=1, cols=3),
           tag("ChSq", "ch", 0, layout="charuco", rows=3, cols=3),
           tag("Ch42", "ch", 0, layout="charuco", rows=2, cols=4),
           tag("Ch28", "ch", 0, layout="charuco", rows=8, cols=2)]
    F["F7"] = (lay, [occ(f"{t.component}:{k}", t.component, T(20 * i, 20 * k))
                     for i, t in enumerate(lay) for k in (1, 2)])
    modes = [tag("Inlay", "top", 0), tag("Raised", "top", 0, raise_m=0.0004),
             tag("Recess", "top", 0, recess_m=0.0002, depth_m=0.0008),
             tag("Thick", "top", 0, depth_m=0.002)]
    F["F8"] = (modes, [occ(f"{t.component}:{k}", t.component) for t in modes for k in (1, 2)])
    # Origin turns: a rectangular board at 90 deg is OpenCV's board transposed
    turned = [tag("G31", "board", 0, layout="grid", rows=1, cols=3),
              tag("G13", "board", 0, layout="grid", rows=3, cols=1),
              tag("C42", "ch", 0, layout="charuco", rows=2, cols=4),
              tag("C24", "ch", 0, layout="charuco", rows=4, cols=2)]
    F["F9"] = (turned, [occ(f"{t.component}:{k}", t.component, T(0, 0, 0, 90 * k))
                        for t in turned for k in (1, 2)])
    dicts = [tag("D50", "top", 3, "DICT_4X4_50"), tag("D100", "top", 3, "DICT_4X4_100"),
             tag("D5", "top", 3, "DICT_5X5_50")]
    F["F10"] = (dicts, [occ(f"{t.component}:{k}", t.component) for t in dicts for k in (1, 2)])
    o11 = [occ("Tag:1", "Tag"), occ("Tag:2", "Tag", visible=False), occ("Tag:3", "Tag"),
           occ("Box:1", "Box", visible=False), occ("Box:1+Tag:1", "Tag"),
           occ("Box:2", "Box"), occ("Box:2+Tag:1", "Tag", visible=False)]
    F["F11"] = ([tag()], o11)
    return F


FX = fixtures()


def plan(name, **kw):
    tags, occs = FX[name]
    return N.plan_ids(tags, occs, root_component="Robot", **kw)


# ---------------------------------------------------------------- helpers
print("helpers")
check("parse_id: '' and blanks are auto", N.parse_id("") is None and N.parse_id("   ") is None)
check("parse_id: numbers, '#7', ' 12 '", N.parse_id("7") == 7 and N.parse_id("#7") == 7
      and N.parse_id(" 12 ") == 12 and N.parse_id(5) == 5)
try:
    N.parse_id("abc")
    check("parse_id: words raise a readable ValueError", False)
except ValueError as exc:
    check("parse_id: words raise a readable ValueError", "whole number" in str(exc), exc)
check("natural order: Plate:2 before Plate:10",
      sorted(["Plate:10", "Plate:2", "Plate:1"], key=N.natural_key) == ["Plate:1", "Plate:2", "Plate:10"])
check("families: 4X4_50 ~ 4X4_1000, 5X5 apart", N.family("DICT_4X4_50") == N.family("DICT_4X4_1000")
      and N.family("DICT_4X4_50") != N.family("DICT_5X5_50")
      and N.family("DICT_ARUCO_ORIGINAL") != N.family("DICT_5X5_50"))
check("instance names round-trip", N.split_name(N.instance_name("A:1+B:2", "top")) == ("A:1+B:2", "top")
      and N.split_name(N.instance_name("", "top")) == ("", "top"))

# --------------------------------------------------------------- G0.1
print("G0.1 every visible instance its own marker, every fixture")
for name in sorted(FX, key=N.natural_key):
    p = plan(name)
    vis = p.visible()
    check(f"{name}: no duplicates among {len(vis)} visible", not p.duplicates(), p.duplicates(),
          gate="G0.1")
    check(f"{name}: nothing refused", p.ok, p.errors, gate="G0.1")
    check(f"{name}: one row per instance", len(p.rows) == len(p.resolution.instances), gate="G0.1")

p10 = plan("F10")
fams = {}
for r in p10.visible():
    fams.setdefault(r.family, set()).update(r.ids)
check("F10: 4X4_50 and 4X4_100 share ids (one family, 4 copies, 4 ids)",
      len(fams.get("aruco4x4", ())) == 4, fams, gate="G0.1")
check("F10: 5X5 copies may reuse a 4x4 id (another family)",
      any(i in fams["aruco4x4"] for i in fams["aruco5x5"]), fams, gate="G0.1")

# --------------------------------------------------------------- G0.2
print("G0.2 board blocks contiguous, never overlapping")
for name in ("F6", "F7", "F9"):
    p = plan(name)
    taken = {}
    overlap = []
    for r in p.visible():
        ids = r.ids
        check(f"{name} {r.name}: block {ids[0]}..{ids[-1]} contiguous ({r.count})",
              ids == list(range(r.final, r.final + r.count)) and len(ids) == r.count, gate="G0.2")
        for i in ids:
            key = (r.family, i)
            if key in taken:
                overlap.append((r.name, taken[key], i))
            taken[key] = r.name
    check(f"{name}: no id in two blocks", not overlap, overlap, gate="G0.2")
p = N.plan_ids([tag("G", "board", 0, layout="grid", rows=2, cols=3), tag("S", "top", 2)],
               [occ("G:1", "G"), occ("G:2", "G"), occ("S:1", "S"), occ("S:2", "S")])
blocks = sorted((r.final, r.final + r.count - 1, r.name) for r in p.visible())
check("2x3 grid copies + singles inside: blocks and singles interleave cleanly",
      not p.duplicates() and all(b[0] > a[1] for a, b in zip(blocks, blocks[1:])), blocks, gate="G0.2")

# --------------------------------------------------------------- G0.3
print("G0.3 ids stay inside the dictionary; refusals name the tag")
many = [occ(f"Tag:{k}", "Tag") for k in range(1, 56)]
p = N.plan_ids([tag()], many)
inside = all(0 <= i < 50 for r in p.visible() if not r.error for i in r.ids)
check("55 copies in DICT_4X4_50: every numbered one inside 0..49", inside, gate="G0.3")
check("... 5 refused, each naming its tag", len(p.errors) == 5
      and all("Tag:" in e and "DICT_4X4_50 is full" in e for e in p.errors), p.errors[:2], gate="G0.3")
check("... the refused rows print what they did (no part)", all(not r.needs_part for r in p.rows if r.error),
      gate="G0.3")
p = N.plan_ids([tag("G", "board", 46, layout="grid", rows=1, cols=3)], [occ("G:1", "G"), occ("G:2", "G")])
check("a 3-marker board never runs off the end (46..48 kept, the copy gets a block below)",
      all(r.final + r.count <= 50 for r in p.visible()) and not p.errors, [r.ids for r in p.rows],
      gate="G0.3")
p = plan("F2", overrides={"Tag:2|top": 77})
check("an override outside the dictionary is refused, naming the tag",
      not p.ok and any("Tag:2|top" in e and "0..49" in e for e in p.errors), p.errors, gate="G0.3")
p = plan("F2", overrides={"Tag:2|top": "seven"})
check("an override that is not a number is refused, naming the tag",
      not p.ok and any("Tag:2|top" in e for e in p.errors), p.errors, gate="G0.3")

# --------------------------------------------------------------- G0.4
print("G0.4 stable: an already-unique design changes nothing; one new copy, one new id")
uniq = [tag("A", "top", 0), tag("B", "top", 1), tag("C", "board", 2, layout="grid", rows=1, cols=3)]
p = N.plan_ids(uniq, [occ("A:1", "A"), occ("B:1", "B"), occ("C:1", "C")])
check("already unique: every final == what it prints, no parts",
      all(r.final == r.base for r in p.rows) and not p.parts(), [r.to_dict() for r in p.rows],
      gate="G0.4")
for name in sorted(FX, key=N.natural_key):
    p1 = plan(name)
    p2 = plan(name, previous=p1.auto_state(), overrides=p1.overrides())
    same = all(a.final == b.final for a, b in zip(p1.rows, p2.rows))
    check(f"{name}: re-planning its own result changes nothing", same and not p2.duplicates(),
          gate="G0.4")
p1 = plan("F4")
tags4, occs4 = FX["F4"]
occs4b = occs4 + [occ("Sub:2+Tag:3", "Tag", T(200, 30))]
p2 = N.plan_ids(tags4, occs4b, previous=p1.auto_state(), root_component="Robot")
moved = [r.name for r in p2.rows if p1.row(r.name) and p1.row(r.name).final != r.final]
new = p2.row("Sub:2+Tag:3|top")
check("F4 + one copy: no existing copy renumbered", not moved, moved, gate="G0.4")
check("... the new copy gets a fresh id", new is not None and not p2.duplicates()
      and new.final not in [r.final for r in p1.rows], new and new.to_dict(), gate="G0.4")
p3 = N.plan_ids(tags4, [o for o in occs4 if o.path != "Sub:1+Tag:2"], previous=p1.auto_state(),
                root_component="Robot")
moved = [r.name for r in p3.rows if p1.row(r.name).final != r.final]
check("F4 - one copy: nobody else renumbered", not moved, moved, gate="G0.4")
p = plan("F2", overrides={"Tag:1|top": 1})
check("an override is never moved by auto (Tag:1 = 1; the others go around it)",
      p.row("Tag:1|top").final == 1 and not p.duplicates()
      and all(r.final != 1 for r in p.rows if r.name != "Tag:1|top"), [r.ids for r in p.rows],
      gate="G0.4")
p0 = plan("F2")
p = plan("F2", previous=p0.auto_state(), overrides={"Tag:3|top": p0.row("Tag:2|top").final})
check("an override taking another copy's auto id: the override keeps it, that copy moves",
      p.row("Tag:3|top").final == p0.row("Tag:2|top").final and not p.duplicates(),
      [r.ids for r in p.rows], gate="G0.4")

# --------------------------------------------------------------- G0.5
print("G0.5 overrides: set, clear to auto, conflicts flagged")
p = plan("F2", overrides={"Tag:2|top": 9})
r = p.row("Tag:2|top")
check("set: the copy prints the override", r.final == 9 and r.source == "override" and r.needs_part,
      r.to_dict(), gate="G0.5")
q = plan("F2", previous=p.auto_state(), overrides={})
check("clear (empty field = no override): back to auto, unique",
      q.row("Tag:2|top").source in ("auto", "model") and q.row("Tag:2|top").override is None
      and not q.duplicates(), q.row("Tag:2|top").to_dict(), gate="G0.5")
q2 = plan("F2", overrides={"Tag:2|top": N.parse_id("")} if N.parse_id("") is not None else {})
check("an empty field parses to auto, never an error", q2.ok, q2.errors, gate="G0.5")
p = plan("F2", overrides={"Tag:2|top": 9, "Tag:3|top": 9})
a, b = p.row("Tag:2|top"), p.row("Tag:3|top")
check("two overrides on one id: both kept (never silently changed)", a.final == 9 and b.final == 9,
      gate="G0.5")
check("... and both flagged", bool(a.conflict) and bool(b.conflict) and p.warnings,
      (a.conflict, b.conflict), gate="G0.5")
check("... auto keeps clear of them", p.row("Tag:1|top").final != 9, gate="G0.5")
p = plan("F2", overrides={"Tag:2|top": 1, "Tag:3|top": 2})
check("two overrides on adjacent ids: no conflict", not any(r.conflict for r in p.rows), gate="G0.5")
p = N.plan_ids([tag("G", "board", 0, layout="grid", rows=1, cols=3)],
               [occ("G:1", "G"), occ("G:2", "G")], overrides={"G:2|board": 2})
check("a board override over another board's AUTO block: the auto one moves, no conflict",
      not p.duplicates() and p.row("G:2|board").final == 2 and not p.row("G:2|board").conflict,
      [r.ids for r in p.rows], gate="G0.5")
p = N.plan_ids([tag("G", "board", 0, layout="grid", rows=1, cols=3)],
               [occ("G:1", "G"), occ("G:2", "G")], overrides={"G:1|board": 0, "G:2|board": 2})
check("two board overrides whose blocks overlap (0-2, 2-4) are both flagged, both kept",
      bool(p.row("G:2|board").conflict) and bool(p.row("G:1|board").conflict)
      and p.row("G:1|board").final == 0 and p.row("G:2|board").final == 2,
      [r.to_dict() for r in p.rows], gate="G0.5")
p = plan("F11", overrides={"Tag:2|top": 5})
check("a hidden copy keeps its override (stored), unnumbered",
      p.overrides().get("Tag:2|top") == 5 and p.row("Tag:2|top").source == "hidden", gate="G0.5")
p = plan("F2", overrides={"Gone:1|top": 4})
check("an override for a copy that is gone is reported stale and dropped",
      "Gone:1|top" in p.stale_overrides and "Gone:1|top" not in p.overrides(), gate="G0.5")

# --------------------------------------------------------------- G0.6
print("G0.6 owners: never inside a linked design")
for name in ("F5", "F6"):
    p = plan(name)
    lk = [r for r in p.rows if r.linked]
    check(f"{name}: the tags inside the linked design are listed ({len(lk)})", len(lk) >= 4,
          [r.name for r in p.rows], gate="G0.6")
    check(f"{name}: every row's id is stored in the root (owner '')",
          all(r.owner == "" for r in p.rows), gate="G0.6")
    recs = p.export_records()
    check(f"{name}: the export records are root-level (owner '') and cover every renumbered copy",
          all(o.owner == "" for o in recs)
          and sum(len(o.values) for o in recs) == len([r for r in p.rows if r.final != r.base
                                                      and not r.hidden]), gate="G0.6")
    check(f"{name}: linked copies are renumbered like any other (no duplicates)",
          not p.duplicates(), gate="G0.6")

# ------------------------------------------------- export path consistency
print("export: resolve() of the records = the plan")
for name in sorted(FX, key=N.natural_key):
    tags, occs = FX[name]
    p = plan(name, overrides={} if name != "F2" else {"Tag:3|top": 20})
    res = M.resolve(tags, p.export_records(), occs, "Robot")
    got = {N.instance_name(i.path, i.tag.key): i.spec.marker_id for i in res.instances}
    bad = [r.name for r in p.rows if not r.hidden and not r.error and got.get(r.name) != r.final]
    check(f"{name}: markers.resolve over export_records gives every final id", not bad, bad,
          gate="G5.2")
    st = N.read_state(json.dumps(N.node_state(p)))
    base = {r.name: r.base for r in p.rows}
    res2 = M.resolve(tags, N.state_records(st, base), occs, "Robot")
    got2 = {N.instance_name(i.path, i.tag.key): i.spec.marker_id for i in res2.instances}
    bad2 = [r.name for r in p.rows if not r.hidden and not r.error and got2.get(r.name) != r.final]
    check(f"{name}: the node's stored state reads back to the same ids", not bad2, bad2, gate="G5.2")

# --------------------------------------------------------------- hidden
print("G1.2 (offline): hidden copies are listed, not numbered")
p = plan("F11")
hid = sorted(r.name for r in p.rows if r.hidden)
check("F11: the hidden copies (own bulb or a hidden parent) are exactly 3",
      hid == ["Box:1+Tag:1|top", "Box:2+Tag:1|top", "Tag:2|top"], hid, gate="G1.2")
check("... and need no part", not any(r.needs_part for r in p.rows if r.hidden), gate="G1.2")

# ------------------------------------------------- inherited (old records)
print("inherited per-copy ids (old records inside a linked design)")
tags6, occs6 = FX["F5"]
inh = [OverrideRecord("Arm", "GIM v1:1", {"Disc:1|top": {"marker_id": 30}})]
p = N.plan_ids(tags6, occs6, inherited=inh, root_component="Robot")
r = p.row("Arm:1+GIM v1:1+Disc:1|top")
check("an inherited id is what the copy prints without the node (base 30)", r.base == 30, r.to_dict())
check("... kept when free (no part needed)", r.final == 30 and not r.needs_part, r.to_dict())

# --------------------------------------------------------------- fixed
print("tags in the root component")
p = N.plan_ids([tag("Robot", "top", 0), tag("Tag", "top", 0)], [occ("Tag:1", "Tag"), occ("Tag:2", "Tag")],
               root_component="Robot")
check("a root tag keeps its id; the copies go around it",
      p.row("(root)|top").final == 0 and p.row("(root)|top").fixed and not p.duplicates(),
      [r.to_dict() for r in p.rows])
check("... and never needs a part", not p.row("(root)|top").needs_part)

print("fixed copies (a linked design's stale record): they keep what they print")
p = plan("F5", fixed={"GIM v1:1+Disc:1|top": "stale record"})
r = p.row("GIM v1:1+Disc:1|top")
check("a fixed linked copy keeps its id and needs no part, the others go around it",
      r.fixed and r.final == r.base and not r.needs_part and not p.duplicates() and p.ok,
      [x.to_dict() for x in p.rows])
check("... and says why", r.note == "stale record" and r.source == "fixed")
p = plan("F5", fixed={"GIM v1:1+Disc:1|top": "stale record"}, overrides={"GIM v1:1+Disc:1|top": 9})
check("an override on a fixed copy is flagged, not built", bool(p.row("GIM v1:1+Disc:1|top").conflict)
      and not p.row("GIM v1:1+Disc:1|top").needs_part)

print("the node's dependencies: one kept copy per component (G8.3)")
p = plan("F2")
hosts = set(p.parts())
dep = N.dependency_copies({r.component for r in p.rows if r.needs_part}, FX["F2"][1], hosts)
check("F2: the node depends on the copy that keeps its id, not on a renumbered one",
      dep == {"Tag": "Tag:1"} and "Tag:1" not in hosts, (dep, hosts))
tags5, occs5 = FX["F5"]
p5 = N.plan_ids(tags5, occs5)
dep5 = N.dependency_copies({r.component for r in p5.rows if r.needs_part}, occs5, set(p5.parts()))
check("F5 (linked): one dependency for the Disc, on a kept copy",
      list(dep5) == ["Disc"] and dep5["Disc"] not in p5.parts(), dep5)
occs_all = [occ("Tag:1", "Tag"), occ("Tag:2", "Tag")]
dep_all = N.dependency_copies({"Tag"}, occs_all, {"Tag:1", "Tag:2"})
check("every copy renumbered: the first host", dep_all == {"Tag": "Tag:1"}, dep_all)
dep_h = N.dependency_copies({"Tag"}, [occ("Tag:1", "Tag", visible=False), occ("Tag:2", "Tag"),
                                      occ("Tag:3", "Tag")], {"Tag:3"})
check("a hidden kept copy is not chosen", dep_h == {"Tag": "Tag:2"}, dep_h)

# --------------------------------------------------------- decoding helpers
print("decoding built patterns (the geometry checks' reader)")
for spec in (TagSpec(dictionary="DICT_4X4_50", marker_id=7, marker_length_m=0.03),
             TagSpec(dictionary="DICT_5X5_100", marker_id=41, marker_length_m=0.03),
             TagSpec(dictionary="DICT_4X4_50", marker_id=10, marker_length_m=0.02, layout="grid",
                     rows=1, cols=3, separation_m=0.004),
             TagSpec(dictionary="DICT_4X4_50", marker_id=4, marker_length_m=0.03, layout="charuco",
                     rows=2, cols=4, square_length_m=0.04)):
    boxes = M.cell_boxes(spec)

    def black(x, y, boxes=boxes):
        return any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes)
    got = N.decode(spec, black)
    check(f"decode {spec.layout} {spec.dictionary} #{spec.ids[0]}..: every marker reads as itself",
          got == {i: i for i in spec.ids}, got)
    other = TagSpec(**{**spec.__dict__, "marker_id": spec.marker_id + 1})
    got2 = N.decode(other, black)
    check(f"... read as #{other.marker_id}.. it does not match", got2 != {i: i for i in other.ids})
check("identify: 4X4_50 #3 is 4X4_1000 #3",
      N.identify("DICT_4X4_1000", N.expected_grid("DICT_4X4_50", 3)) == 3)

print()
print(f"{PASS} passed, {len(FAIL)} failed")
if "--json" in sys.argv:
    out = Path(sys.argv[sys.argv.index("--json") + 1])
    out.write_text(json.dumps({g: {"ok": all(c[1] for c in v), "checks": len(v),
                                   "failed": [c[0] for c in v if not c[1]]}
                               for g, v in sorted(GATES.items())}, indent=1), encoding="utf-8")
sys.exit(1 if FAIL else 0)
