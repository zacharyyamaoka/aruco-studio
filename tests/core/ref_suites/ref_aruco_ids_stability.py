# REF: tests/test_aruco_ids_stability.py at c8216ff (cad-exporter), ported by tools/port_ref_suites.py:
# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.
"""G0.7 of docs/aruco_ids_acceptance.md: ids survive edits (the ID ledger).

Zach, 2026-10-10: "its very important that as we reid the design that we
don't kinda like override old aruco ID's as much as possible ... We want to
avoid having to like reprint things." Design: docs/proposal_aruco_ids_stability.md.

Every check here is an EDIT a user makes between two runs of ArUco IDs, on
a small simulated design (`Sim`): occurrences with names, places, light
bulbs and the stamps ArUco IDs writes; the node's state; the ledger. The
check is always the same: no copy that existed before the edit prints
another id after it, and a new copy never gets an id another copy printed.
`Sim.ok()` runs what the Fusion side runs (aruco_ids_feature.apply):
aruco_numbering.plan_stable, then the stamps for copies seen for the first
time, then ledger_after.

Run:  python tests/test_aruco_ids_stability.py          (stdlib only)
      python tests/test_aruco_ids_stability.py --json out.json
tools/mutate_aruco_ids.py runs this suite against deliberately wrong
planners: every mutation must turn it red.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
# tools/mutate_aruco_ids.py points this at a mutated copy of the core
pass  # REF: BAM_CORE_ROOT or its CADExporter on sys.path (ported: not needed)

from aruco_studio.core import numbering as N  # noqa: E402
from aruco_studio.core.markers import OccurrenceRef, TagDef, TagSpec  # noqa: E402

PASS = 0
FAIL = []
GATES = {}


def check(label, condition, detail="", gate="G0.7"):
    global PASS
    GATES.setdefault(gate, []).append((label, bool(condition), str(detail)[:300]))
    if condition:
        PASS += 1
        print(f"  ok  {label}")
    else:
        FAIL.append(label)
        print(f"FAIL  {label}  {detail}")


def tagdef(component, key="top", marker_id=0, layout="single", rows=1, cols=1,
           dictionary="DICT_4X4_50"):
    spec = TagSpec(dictionary=dictionary, marker_id=marker_id, marker_length_m=0.02,
                   layout=layout, rows=rows, cols=cols)
    if layout == "grid":
        spec.separation_m = 0.004
    if layout == "charuco":
        spec.square_length_m = 0.03
    return TagDef(key=key, component=component, spec=spec, origin=[0.0, 0.0, 0.3])


# ------------------------------------------------------------- simulator

class Sim:
    """A design as ArUco IDs sees it. Occurrences are NATIVE occurrences
    (one per component they sit in), translation-only, so a copy's place is
    the sum of its natives' offsets."""

    def __init__(self, tags, root="Robot"):
        self.root = root
        self.tags = list(tags)
        self.natives = {}          # nid -> dict(name, comp, owner, t, on, linked, stamp, born)
        self.next_nid = 1
        self.clock = 0.0
        self.state = {}            # the node's stored state ({} = no node)
        self.ledger = None         # the root attribute (None = none)
        self.overrides = {}
        self.stamp_counter = 0
        self.recycle_names = False  # Fusion naming a new copy with a freed ':N'
        self.plan = None

    # ---- edits
    def add(self, comp, owner=None, at=(0.0, 0.0, 0.0), linked=False, on=True, name=None):
        owner = owner or self.root
        if name is None:
            used = {int(n["name"].rsplit(":", 1)[1]) for n in self.natives.values()
                    if n["owner"] == owner and n["comp"] == comp}
            k = (next(i for i in range(1, 999) if i not in used) if self.recycle_names
                 else max(used, default=0) + 1)
            name = f"{comp}:{k}"
        nid = self.next_nid
        self.next_nid += 1
        self.natives[nid] = {"name": name, "comp": comp, "owner": owner, "t": list(at),
                             "on": on, "linked": linked, "stamp": None, "born": None}
        return nid

    def delete(self, nid):
        comp = self.natives[nid]["comp"]
        del self.natives[nid]
        # what sat inside it goes too, when no other copy of its component is left
        if not any(n["comp"] == comp for n in self.natives.values()):
            for k in [k for k, n in self.natives.items() if n["owner"] == comp]:
                self.delete(k)

    def renumber(self, comp, owner=None):
        """':3' becomes ':2' after a delete (if Fusion did that)."""
        owner = owner or self.root
        mine = sorted((k for k, n in self.natives.items() if n["owner"] == owner and n["comp"] == comp),
                      key=lambda k: int(self.natives[k]["name"].rsplit(":", 1)[1]))
        for i, k in enumerate(mine, start=1):
            self.natives[k]["name"] = f"{comp}:{i}"

    def rename_component(self, old, new):
        for n in self.natives.values():
            if n["comp"] == old:
                n["name"] = new + ":" + n["name"].rsplit(":", 1)[1]
                n["comp"] = new
            if n["owner"] == old:
                n["owner"] = new
        for t in self.tags:
            if t.component == old:
                t.component = new

    def reparent(self, nid, into_nid, keep_stamp=True):
        """Into the component of occurrence `into_nid`, keeping its place."""
        n = self.natives[nid]
        world = self.world_of(nid)
        target = self.natives[into_nid]
        tw = self.world_of(into_nid)
        n["owner"] = target["comp"]
        n["t"] = [a - b for a, b in zip(world, tw)]
        used = {int(m["name"].rsplit(":", 1)[1]) for k, m in self.natives.items()
                if k != nid and m["owner"] == n["owner"] and m["comp"] == n["comp"]}
        n["name"] = f"{n['comp']}:{max(used, default=0) + 1}"
        if not keep_stamp:
            n["stamp"] = None

    def move(self, nid, by):
        n = self.natives[nid]
        n["t"] = [a + b for a, b in zip(n["t"], by)]

    def replace_linked_inside(self, comp, new_comp):
        """A linked design replaced / refreshed with one whose part is named
        differently: the natives inside get new names, same places."""
        for n in self.natives.values():
            if n["comp"] == comp:
                n["name"] = new_comp + ":" + n["name"].rsplit(":", 1)[1]
                n["comp"] = new_comp
        for t in self.tags:
            if t.component == comp:
                t.component = new_comp

    def delete_node(self):
        self.state = {}

    # ---- reading, as collect_design does
    def world_of(self, nid):
        n = self.natives[nid]
        if n["owner"] == self.root:
            return list(n["t"])
        parent = next(k for k, m in self.natives.items() if m["comp"] == n["owner"])
        return [a + b for a, b in zip(self.world_of(parent), n["t"])]

    def paths(self):
        """[(path, [nids], world xyz)] for every occurrence path."""
        out = []

        def walk(owner, prefix, nids, off):
            for k, n in sorted(self.natives.items()):
                if n["owner"] != owner:
                    continue
                p = f"{prefix}+{n['name']}" if prefix else n["name"]
                w = [a + b for a, b in zip(off, n["t"])]
                out.append((p, nids + [k], w))
                walk(n["comp"], p, nids + [k], w)
        walk(self.root, "", [], [0.0, 0.0, 0.0])
        return out

    def occs(self):
        out = []
        for p, nids, w in self.paths():
            n = self.natives[nids[-1]]
            T = [1, 0, 0, w[0], 0, 1, 0, w[1], 0, 0, 1, w[2], 0, 0, 0, 1]
            out.append(OccurrenceRef(p, n["comp"], [float(v) for v in T], n["on"], n["linked"]))
        return out

    def losers(self):
        """Natives whose stamp another native also carries and that lose it
        (aruco_numbering.stamp_losers, as collect_design asks it)."""
        items = [(f"{n['owner']}/{n['name']}", n["stamp"], n.get("home", ""))
                 for n in self.natives.values() if n["stamp"]]
        lose = N.stamp_losers(items)
        return {k for k, n in self.natives.items() if f"{n['owner']}/{n['name']}" in lose}

    def chains(self):
        chains, born = {}, {}
        lose = self.losers()
        for p, nids, _w in self.paths():
            segs, b = [], None
            for i, k in enumerate(nids):
                n = self.natives[k]
                inside_linked = any(self.natives[j]["linked"] for j in nids[:i])
                if inside_linked:
                    segs.append("=" + n["name"])
                elif n["stamp"] and k not in lose:
                    segs.append("#" + n["stamp"])
                    b = n["born"] if b is None else max(b, n["born"])
                else:
                    segs.append(None)
            chains[p] = N.chain_key(segs)
            if b is not None:
                born[p] = b
        return chains, born

    def ident(self):
        """path -> the copy's identity for the CHECKS (the natives it is
        made of, never anything ArUco IDs reads)."""
        return {p: tuple(nids) for p, nids, _w in self.paths()}

    # ---- one OK
    def ok(self, overrides=None):
        if overrides is not None:
            self.overrides = dict(overrides)
        chains, born = self.chains()
        plan = N.plan_stable(self.tags, self.occs(), ledger=self.ledger, state=self.state,
                             chains=chains, born=born, overrides=self.overrides,
                             previous=dict(self.state.get("auto") or {}),
                             root_component=self.root)
        assert plan.ok, plan.errors
        # stamp what the plan numbered and is not stamped yet
        self.clock += 1.0
        ident = self.ident()
        lose = self.losers()
        for r in plan.rows:
            for i, k in enumerate(ident.get(r.path, ())):
                n = self.natives[k]
                if any(self.natives[j]["linked"] for j in ident[r.path][:i]):
                    continue
                if not n["stamp"] or k in lose:
                    self.stamp_counter += 1
                    n["stamp"] = f"s{self.stamp_counter}"
                    n["born"] = self.clock
                    n["home"] = f"{n['owner']}/{n['name']}"
                    lose.discard(k)
        chains2, _b = self.chains()
        self.ledger = N.ledger_after(plan, chains2, when=f"t{self.clock}")
        # the root attribute is stored as JSON and read back
        self.ledger = N.Ledger.from_any(self.ledger.to_json())
        self.state = json.loads(json.dumps(N.node_state(plan)))
        self.plan = plan
        return plan

    def ids(self, plan=None):
        """{copy identity: first id} for every visible numbered copy."""
        plan = plan or self.plan
        ident = self.ident()
        return {(ident[r.path], r.key): r.final for r in plan.rows
                if not r.hidden and not r.error and r.path in ident}

    def printed_ever(self):
        return {i for fam in (self.ledger.printed if self.ledger else {}).values() for i in fam}


def unchanged(before, after):
    """Copies in both whose id changed: [(copy, before, after)]."""
    return [(k, before[k], after[k]) for k in before if k in after and before[k] != after[k]]


def fresh(before_all, after, before_keys):
    """New copies' ids that some copy printed before."""
    return [(k, after[k]) for k in after if k not in before_keys and after[k] in before_all]


def tag_sim(n=4, recycle=False):
    s = Sim([tagdef("Tag")])
    s.recycle_names = recycle
    nids = [s.add("Tag", at=(10.0 * k, 0, 0)) for k in range(n)]
    return s, nids


# ===================================================================== rules
print("0. backward compatible: no ledger = the 2026-10-09 numbering")
s, _ = tag_sim(3)
p_old = N.plan_ids(s.tags, s.occs(), root_component="Robot")
p_new = N.plan_stable(s.tags, s.occs(), root_component="Robot")
check("an empty ledger plans exactly what plan_ids(ledger=None) plans",
      [r.final for r in p_old.rows] == [r.final for r in p_new.rows], [r.final for r in p_new.rows])

print("1. delete the ArUco IDs node and run it again")
s, nids = tag_sim(4)
s.ok()
s.delete(nids[1])
s.ok()                                    # Tag:2 gone, its id retired
s.add("Tag", at=(50.0, 0, 0))
p = s.ok()
before = s.ids()
s.delete_node()                           # node state gone; the ledger is a root attribute
after = s.ids(s.ok())
check("1a after delete + re-run, every copy prints what it printed", not unchanged(before, after),
      unchanged(before, after))
s2 = copy.deepcopy(s)
s2.ledger = None
s2.delete_node()
scratch = s2.ids(s2.ok())
check("1b (the test bites: from scratch the same design numbers differently)",
      bool(unchanged(before, scratch)), (before, scratch))

print("2. a deleted copy's id is never handed to a new copy")
s, nids = tag_sim(4)
p1 = s.ok()
dead = s.ids()[((nids[2],), "top")]
s.delete(nids[2])
s.ok()
new = s.add("Tag", at=(70.0, 0, 0))
p3 = s.ok()
got = s.ids()[((new,), "top")]
check("2a the new copy does not get the deleted copy's id", got != dead, (dead, got))
check("2b it gets an id no copy ever printed", got not in {r.final for r in p1.rows},
      (got, [r.final for r in p1.rows]))
check("2b' the dialog's list of retired ids names the deleted copy's", p3.retired() == {"aruco4x4": [dead]},
      p3.retired())
check("2c and nobody else moved", not unchanged({k: v for k, v in s.ids(p1).items() if k[0][0] != nids[2]},
                                                s.ids()), s.ids())
s, nids = tag_sim(3)
s.ok()                                    # Tag:1 prints 0 with its own geometry (no part)
s.delete(nids[0])
s.ok()
new = s.add("Tag", at=(70.0, 0, 0))       # a new copy's geometry prints 0 too
got = s.ids(s.ok())[((new,), "top")]
check("2d the first copy (the one printing its own 0) deleted: a new copy does not print 0",
      got != 0, got)
s, nids = tag_sim(3)
s.ok()
dead = s.ids()[((nids[1],), "top")]
s.delete(nids[1])
s.ok()
new = s.add("Tag", at=(10.2, 0, 0))       # 2 mm from where the deleted copy was
got = s.ids(s.ok())[((new,), "top")]
check("2e a new copy 2 mm from a deleted one's place is a NEW copy (0.5 mm is 'put back')",
      got != dead, (dead, got))

print("3. copies added in the middle (natural order and creation order)")
s = Sim([tagdef("Tag")])
sub1 = s.add("Sub", at=(0, 0, 0))
for k in range(3):
    s.add("Tag", owner="Sub", at=(10.0 * k, 0, 0))
s.add("Sub", at=(0, 50.0, 0))             # a second copy of the sub-assembly
s.ok()
s.delete(next(k for k, n in s.natives.items() if n["name"] == "Tag:2" and n["owner"] == "Sub"))
s.ok()
before = s.ids()
s.add("Tag", owner="Sub", at=(15.0, 0, 0))    # Sub:1+Tag:4 and Sub:2+Tag:4: in the middle
s.add("Tag", at=(0, -30.0, 0), name="Tag:1")  # a root copy that sorts FIRST
after = s.ids(s.ok())
check("3a no existing copy renumbered", not unchanged(before, after), unchanged(before, after))
check("3b the new copies get never-printed ids", not fresh(set(s.plan.ledger.printed.get("aruco4x4", {})),
                                                            after, set(before)),
      fresh(set(s.plan.ledger.printed.get("aruco4x4", {})), after, set(before)))

print("4. a component renamed (every path changes, the stamps stay)")
s, nids = tag_sim(4)
s.ok()
s.delete(nids[0])                         # so ids are not just 0..n in path order
s.ok()
before = s.ids()
s.rename_component("Tag", "Bracket")
after = s.ids(s.ok())
check("4a renamed: nothing renumbered", not unchanged(before, after), unchanged(before, after))
check("4b ... found by the stamp chain", all(r.basis == "ledger" for r in s.plan.visible()),
      [(r.name, r.basis) for r in s.plan.rows])

print("5. renamed with NO stamps (a ledger seeded from an old node): found by place")
s, nids = tag_sim(4)
s.ok()
for n in s.natives.values():
    n["stamp"] = None                     # as if the stamps were never written
s.ledger = N.Ledger.from_any(s.ledger.to_json())
for e in s.ledger.entries:
    e.uid = ""
before = s.ids()
s.rename_component("Tag", "Bracket")
after = s.ids(s.ok())
check("5 renamed, unstamped: nothing renumbered", not unchanged(before, after), unchanged(before, after))

print("6. a copy re-parented (moved into a sub-assembly, same place)")
s = Sim([tagdef("Tag")])
box = s.add("Box", at=(0, 100.0, 0))
nids = [s.add("Tag", at=(10.0 * k, 0, 0)) for k in range(4)]
s.ok()
s.delete(nids[0])
s.ok()
before = s.ids()
s.reparent(nids[2], box)
after = s.ids(s.ok())
check("6a re-parented with its stamp: nothing renumbered", not unchanged(before, after),
      unchanged(before, after))
s, nids = tag_sim(4)
box = s.add("Box", at=(0, 100.0, 0))
s.ok()
s.delete(nids[0])
s.ok()
before = s.ids()
s.reparent(nids[2], box, keep_stamp=False)
after = s.ids(s.ok())
check("6b re-parented and the stamp lost: found by its place", not unchanged(before, after),
      unchanged(before, after))

print("7. ':3' becomes ':2' after a delete")
s, nids = tag_sim(4)
s.ok()
before = s.ids()
s.delete(nids[1])
s.renumber("Tag")
after = s.ids(s.ok())
check("7a stamped: every survivor keeps its id", not unchanged(before, after), unchanged(before, after))
s, nids = tag_sim(4)
s.ok()
for n in s.natives.values():
    n["stamp"] = None
for e in s.ledger.entries:
    e.uid = ""
before = s.ids()
s.delete(nids[1])
s.renumber("Tag")
after = s.ids(s.ok())
check("7b unstamped (path + place): every survivor keeps its id", not unchanged(before, after),
      unchanged(before, after))
# today's planner (by path only) on the same edit swaps ids
s, nids = tag_sim(4)
p0 = N.plan_ids(s.tags, s.occs(), root_component="Robot")
b0 = s.ids(p0)
s.delete(nids[1])
s.renumber("Tag")
p1 = N.plan_ids(s.tags, s.occs(), previous=p0.auto_state(), root_component="Robot")
check("7c (the test bites: by path alone the renumbered copy takes the deleted one's id)",
      bool(unchanged(b0, s.ids(p1))), unchanged(b0, s.ids(p1)))

print("8. a deleted copy's NAME given to a new copy (Fusion reusing ':2')")
s, nids = tag_sim(3, recycle=True)
s.ok()
dead = s.ids()[((nids[1],), "top")]
s.delete(nids[1])
s.ok()
new = s.add("Tag", at=(99.0, 0, 0))       # named Tag:2 again, elsewhere
check("8 (setup) the new copy got the old name", s.natives[new]["name"] == "Tag:2", s.natives[new])
got = s.ids(s.ok())[((new,), "top")]
check("8 the new 'Tag:2' does not inherit the deleted Tag:2's id", got != dead, (dead, got))

print("9. hide a copy, OK, show it again")
s, nids = tag_sim(4)
s.ok()
before = s.ids()
s.natives[nids[2]]["on"] = False
s.ok()
held = before[((nids[2],), "top")]
check("9c while hidden the ledger holds its id for it (not retired)",
      held in s.ledger.held("aruco4x4") and held not in s.ledger.retired("aruco4x4")
      and s.ledger.summary()["copies"]["hidden"] == 1, s.ledger.summary())
s.add("Tag", at=(80.0, 0, 0))             # a new copy while it is hidden
s.ok()
s.natives[nids[2]]["on"] = True
after = s.ids(s.ok())
check("9a shown again: it prints its old id", not unchanged(before, after), unchanged(before, after))
check("9b the copy added meanwhile did not take it",
      len(set(after.values())) == len(after), after)

print("10. a tag deleted and made again")
s, nids = tag_sim(3)
s.ok()
s.delete(nids[0])
s.ok()
before = s.ids()
keep = s.tags
s.tags = []
s.ok()                                    # the tag is gone: every copy retired
s.tags = [tagdef("Tag", key="top")]      # made again (ArUco Extrude names it 'top' again)
after = s.ids(s.ok())
check("10a same key: every copy prints its old id", not unchanged(before, after), unchanged(before, after))
s.tags = []
s.ok()
s.tags = [tagdef("Tag", key="top2")]     # made again under another key, same place
after2 = {(k[0], "top"): v for k, v in s.ids(s.ok()).items()}
check("10b another key, same place: every copy prints its old id", not unchanged(before, after2),
      unchanged(before, after2))

print("11. a linked design refreshed / replaced (its part named differently)")
s = Sim([tagdef("Aruco", key="top2")])
for k in range(3):
    g = s.add("GIM", at=(30.0 * k, 0, 0), linked=True)
s.add("Aruco", owner="GIM", at=(0, 0, 4.0))
s.ok()
before = s.ids()
s.replace_linked_inside("Aruco", "Marker")
after = s.ids(s.ok())
check("11 inside a linked design, renamed: nothing renumbered", not unchanged(before, after),
      unchanged(before, after))

print("12. both the node's state and the ledger lost: best effort")
s, nids = tag_sim(5)
s.ok()
s.add("Tag", at=(90.0, 0, 0), name="Tag:0")   # the youngest copy sorts FIRST by name
s.ok()
before = s.ids()
s2 = copy.deepcopy(s)
s.delete_node()
s.ledger = None
after = s.ids(s.ok())
check("12a nothing deleted since: the stamps' birth order gives every id back",
      not unchanged(before, after), unchanged(before, after))
for n in s2.natives.values():
    n["stamp"] = n["born"] = None
s2.delete_node()
s2.ledger = None
check("12a' (the test bites: without the stamps, natural order renumbers)",
      bool(unchanged(before, s2.ids(s2.ok()))))
s, nids = tag_sim(4)
s.tags = [tagdef("Tag", marker_id=7)]
s.ok()
before = s.ids()
s.delete_node()
s.ledger = None
after = s.ids(s.ok())
check("12b the copy whose geometry prints its id keeps it", after[((nids[0],), "top")] == 7, after)

print("13. overrides: never moved; clearing one gives the copy back its auto id")
s, nids = tag_sim(4)
s.ok()
before = s.ids()
victim = before[((nids[2],), "top")]
s.ok(overrides={f"Tag:4|top": victim})   # Tag:4 takes Tag:3's id by hand
after = s.ids()
check("13a the override prints exactly what was typed", after[((nids[3],), "top")] == victim, after)
moved = after[((nids[2],), "top")]
check("13b the copy it displaced gets a NEVER-printed id (not a retired one)",
      moved not in before.values(), (before, after))
s.ok(overrides={})
cleared = s.ids()
check("13c override cleared: Tag:4 is back on its own auto id", cleared[((nids[3],), "top")]
      == before[((nids[3],), "top")], (before, cleared))
s, nids = tag_sim(3)
s.ok()
s.ok(overrides={"Tag:2|top": 40})
p = s.ok()
check("13d an override is kept through every later OK", p.row("Tag:2|top").final == 40
      and p.row("Tag:2|top").source == "override", p.row("Tag:2|top").to_dict())
check("13e the ledger does not call a live override's id retired",
      40 in s.ledger.held("aruco4x4") and 40 not in s.ledger.retired("aruco4x4"),
      s.ledger.summary())

print("14. a full dictionary: the oldest retired id first, a hidden copy's last")
s = Sim([tagdef("Tag")])
nids = [s.add("Tag", at=(5.0 * k, 0, 0)) for k in range(50)]
s.ok()                                    # 0..49, all printed
s.natives[nids[5]]["on"] = False
s.ok()                                    # 5 hidden (reserved), last printed at OK #1
s.delete(nids[10])
s.ok()                                    # 10 retired, last printed at OK #2
s.delete(nids[20])
s.ok()                                    # 20 retired, last printed at OK #3
a = s.add("Tag", at=(0, 99.0, 0))
p = s.ok()
check("14a the first new copy reuses the id retired the LONGEST ago (10)",
      s.ids()[((a,), "top")] == 10, s.ids()[((a,), "top")])
check("14b ... with a warning that names it", any("reuses #10" in w and "Tag:11" in w
                                                    for w in p.warnings), p.warnings[-2:])
b = s.add("Tag", at=(0, 98.0, 0))
c = s.add("Tag", at=(0, 97.0, 0))
p = s.ok()
check("14c then 20; the hidden copy's 5 (older still) only when nothing else is left",
      s.ids()[((b,), "top")] == 20 and s.ids()[((c,), "top")] == 5, s.ids())
check("14c' ... and the hidden copy's ledger entry gives that id up",
      next(e for e in s.ledger.entries if e.name == "Tag:6|top").id is None,
      [e.to_dict() for e in s.ledger.entries if e.name == "Tag:6|top"])
d = s.add("Tag", at=(0, 96.0, 0))
try:
    s.ok()
    refused = False
except AssertionError as exc:
    refused = "is full" in str(exc)
check("14d truly full: a refusal that names the copy", refused)

print("15. a pasted copy carrying its original's stamp")
check("15a stamp_losers: the copy still where it was stamped keeps the stamp",
      N.stamp_losers([("Robot/Tag:1", "u1", "Robot/Tag:1"), ("Robot/Tag:5", "u1", "Robot/Tag:1"),
                      ("Robot/Tag:2", "u2", "Robot/Tag:2")]) == {"Robot/Tag:5"})
check("15b ... when neither is where it was, the first in natural order",
      N.stamp_losers([("Robot/Tag:10", "u1", "X"), ("Robot/Tag:9", "u1", "Y")]) == {"Robot/Tag:10"})
s, nids = tag_sim(3)
s.ok()
before = s.ids()
dup = s.add("Tag", at=(60.0, 0, 0))
for k in ("stamp", "born", "home"):                    # pasted with its original's stamp
    s.natives[dup][k] = s.natives[nids[1]][k]
after = s.ids(s.ok())
check("15c the original keeps its id, the pasted copy gets a new one",
      not unchanged(before, after) and after[((dup,), "top")] not in before.values(), after)
check("15d ... and a stamp of its own (the next OK finds both by stamp)",
      s.natives[dup]["stamp"] != s.natives[nids[1]]["stamp"]
      and all(r.basis == "ledger" for r in s.ok().visible()), s.natives[dup])
# the planner alone, handed one uid on two rows and ONE entry, gives it to one
s, nids = tag_sim(2)
led = N.Ledger(seq=1, entries=[N.LedgerEntry(uid="#same|top", name="Tag:1|top", family="aruco4x4",
                                             id=0, seen=1)])
led.mark_printed("aruco4x4", [0], 1, "Tag:1|top")
p = N.plan_ids(s.tags, s.occs(), ledger=led, chains={"Tag:1": "#same", "Tag:2": "#same"},
               root_component="Robot")
check("15e two rows with one uid: the entry is taken once (by the copy at its path)",
      p.matches == {"Tag:1|top": 0} and not p.duplicates(), p.matches)

print("23. a copy MOVED and its component renamed: only the stamp knows it")
s, nids = tag_sim(4)
s.ok()
s.delete(nids[0])
s.ok()
before = s.ids()
s.move(nids[2], (0, 5.0, 0))
s.rename_component("Tag", "Bracket")
after = s.ids(s.ok())
check("23 moved + renamed: nothing renumbered", not unchanged(before, after), unchanged(before, after))

print("24. the tag's own id edited in ArUco Extrude (5 -> 9)")
s = Sim([tagdef("Tag", marker_id=5)])
nids = [s.add("Tag", at=(10.0 * k, 0, 0)) for k in range(3)]
s.ok()                                    # Tag:1 prints 5 itself, Tag:2 0, Tag:3 1
before = s.ids()
s.tags = [tagdef("Tag", marker_id=9)]
s.delete_node()                           # and the node deleted: only the ledger remembers
after = s.ids(s.ok())
check("24 every copy keeps the id it prints (Tag:1 stays 5, now through a part)",
      not unchanged(before, after) and s.plan.row("Tag:1|top").needs_part, (before, after))

print("16. boards: a block that grows keeps its start when the extra id was never printed")
s = Sim([tagdef("Board", "board", 0, "grid", 1, 3), tagdef("Tag", marker_id=20)])
b1 = s.add("Board", at=(0, 0, 0))
t1 = s.add("Tag", at=(50.0, 0, 0))
s.ok()                                    # board 0-2, tag 20
s.tags[0] = tagdef("Board", "board", 0, "grid", 1, 4)   # the board edited: 4 markers
p = s.ok()
check("16a a grown board keeps its start (3 was never printed)",
      p.row("Board:1|board").ids == [0, 1, 2, 3], p.row("Board:1|board").to_dict())
s = Sim([tagdef("Board", "board", 0, "grid", 1, 3), tagdef("Tag")])
bs = [s.add("Board", at=(0, 20.0 * k, 0)) for k in range(2)]
ts = [s.add("Tag", at=(50.0, 10.0 * k, 0)) for k in range(2)]
s.ok()
before = s.ids()
printed = set(s.ledger.printed["aruco4x4"])
s.tags[0] = tagdef("Board", "board", 0, "grid", 1, 4)
after = s.ids(s.ok())
moved = [r for r in s.plan.visible() if r.key == "board" and r.basis != "ledger"]
check("16b ... where it cannot, the board gets a never-printed block; the tags stay",
      not [k for k, a, b in unchanged(before, after) if k[1] == "top"]
      and all(not (set(r.ids) & printed) for r in moved) and not s.plan.duplicates(),
      (before, after))

print("17. G0.4 with the ledger: re-planning its own result changes nothing (every edit above)")
s, nids = tag_sim(6)
for step in range(3):
    p1 = s.ok()
    p2 = s.ok()
    check(f"17.{step} OK twice: identical", [r.final for r in p1.rows] == [r.final for r in p2.rows])
    s.delete(nids[step])

print("18. the ledger is data: unreadable parts are dropped, never fatal")
check("18a garbage -> an empty ledger", N.Ledger.from_any("{not json").entries == []
      and N.Ledger.from_any(None).seq == 0 and N.Ledger.from_any([1, 2]).entries == [])
bad = {"seq": "x", "entries": [{"uid": "u", "family": "aruco4x4", "id": "nine"}, 5,
                               {"name": "Tag:1|top", "family": "aruco4x4", "id": 3}],
       "printed": {"aruco4x4": {"3": [1, "Tag:1|top"], "x": [1, ""], "4": "bad"}}}
L = N.Ledger.from_any(bad)
check("18b a half-broken ledger keeps what it can", len(L.entries) == 1 and L.entries[0].id == 3
      and 3 in L.printed["aruco4x4"] and L.seq == 0, L.to_dict())
s, _ = tag_sim(3)
s.ok()
rt = N.Ledger.from_any(s.ledger.to_json())
check("18c round trip", rt.to_dict() == s.ledger.to_dict())

print("19. migration: a node from before the ledger keeps every id it printed")
s, nids = tag_sim(4)
p0 = N.plan_ids(s.tags, s.occs(), root_component="Robot")           # the old node's OK
s.state = json.loads(json.dumps(N.node_state(p0)))
before = s.ids(p0)
gone_id = before[((nids[1],), "top")]
s.delete(nids[1])                         # then a copy deleted, old style (no ledger yet)
nw = s.add("Tag", at=(70.0, 0, 0))
after = s.ids(s.ok())
check("19a the first ledger OK keeps every surviving id", not unchanged(before, after),
      unchanged(before, after))
check("19b ... and the copy deleted before the switch keeps its id retired",
      after[((nw,), "top")] != gone_id and after[((nw,), "top")] not in before.values(), after)
legacy = {"schema": N.SCHEMA, "overrides": {}, "auto": {"Tag:1|top": 0, "Tag:2|top": 1},
          "final": {"Tag:1|top": 0, "Tag:2|top": 1, "Box:1+Tag:1|top": 5},
          "parts": [{"host": "Box:1+Tag:1", "tags": [{"name": "Box:1+Tag:1|top", "final": 5,
                                                     "rec": {"spec": tagdef("Tag").spec.to_dict()}}]}]}
L = N.seed_ledger(legacy, [])
check("19c a 2026-10-09 state (no 'families'): a vanished copy's family from its part record",
      5 in L.printed.get("aruco4x4", {}) and len(L.entries) == 3
      and all(e.state == "gone" for e in L.entries), L.to_dict())

print("20. the rack (One Dof Test Rack, 2026-10-09 22:52 -> 2026-10-10 12:36)")
R = Sim([tagdef("Aruco Marker", "board", 0, "grid", 1, 3),
         tagdef("Rack Corner", "charuco", 9, "charuco", 3, 3),
         tagdef("Strip", "charuco", 0, "charuco", 2, 8), tagdef("Aruco", "top2")], root="Rack")
for k, plate in enumerate(("JMC60 + Gearbox Plate", "JMC60 Plate", "SteadyWin GIM43 Plate")):
    R.add(plate, at=(100.0 * k, 0, 0))
    R.add("Aruco Marker", owner=plate, at=(0, 5.0, 1.0))
corner = R.add("Rack Corner", at=(300.0, 0, 0))
R.add("One Dof Test Rig", at=(0, 300.0, 0), linked=True)
R.add("Strip", owner="One Dof Test Rig", at=(0, 0, 9.0))
gims = {}
for plate, ks in (("JMC60 + Gearbox Plate", (6, 7)), ("JMC60 Plate", (4, 5)),
                  ("SteadyWin GIM43 Plate", (1, 2, 3))):
    for k in ks:                                  # Tag:3-:7 were switched off last night
        gims[k] = R.add("GIM43 Aruco Tag", owner=plate, at=(10.0 * k, 50.0, 2.0), linked=True,
                        name=f"GIM43 Aruco Tag:{k}", on=k in (1, 2))
R.add("Aruco", owner="GIM43 Aruco Tag", at=(0, 0, 1.0))
p_night = R.ok()
night = R.ids(p_night)
check("20 (setup) last night's run: 0-2 kept, 3-5, 6-8, Rack Corner 9-12, strip 13-20, 21, 22",
      sorted(i for r in p_night.visible() for i in r.ids) == list(range(23)),
      [(r.name, r.label()) for r in p_night.visible()])
R.delete(corner)                                  # 12:3x he deleted Rack Corner ...
for k in (3, 4, 5, 6, 7):
    R.natives[gims[k]]["on"] = True               # ... and switched GIM43 Tag:3-:7 on
R.add("Aruco Marker", at=(400.0, 0, 0), name="Aruco Marker:4")
p = R.ok()
day = R.ids(p)
ident = R.ident()
new_ids = {i for r in p.visible() if (ident[r.path], r.key) not in night for i in r.ids}
check("20a every id printed last night is kept", not unchanged(night, day), unchanged(night, day))
check("20b the deleted Rack Corner's 9-12 are NOT handed out again", not (new_ids & set(range(9, 13))),
      sorted(new_ids))
check("20c the new copies get the next never-printed ids (23-30)", sorted(new_ids) == list(range(23, 31)),
      sorted(new_ids))
RACK = {"night": [(r.name, r.label(), r.basis) for r in p_night.visible()],
        "day": [(r.name, r.label(), r.basis) for r in p.visible()]}

print("21. a copy deleted and put back (Undo, or the same occurrence restored)")
s, nids = tag_sim(3)
s.ok()
before = s.ids()
saved = copy.deepcopy(s.natives[nids[1]])
s.delete(nids[1])
s.ok()
s.add("Tag", at=(77.0, 0, 0))
s.ok()
s.natives[nids[1]] = saved                        # back, with its stamp
after = s.ids(s.ok())
check("21 put back: it prints its old id again", not unchanged(before, after), unchanged(before, after))

print("22. one family's ids never leak into another's")
s = Sim([tagdef("A", dictionary="DICT_4X4_50"), tagdef("B", dictionary="DICT_5X5_50")])
a = [s.add("A", at=(10.0 * k, 0, 0)) for k in range(3)]
b = [s.add("B", at=(10.0 * k, 50.0, 0)) for k in range(3)]
s.ok()
s.delete(a[1])
s.ok()
nb = s.add("B", at=(99.0, 50.0, 0))
p = s.ok()
check("22 a 4x4 id retired does not block a 5x5 copy (families apart)",
      not p.duplicates() and "aruco5x5" in p.ledger.printed, p.ledger.summary())

print()
print(f"{PASS} passed, {len(FAIL)} failed")
if "--json" in sys.argv:
    out = Path(sys.argv[sys.argv.index("--json") + 1])
    out.write_text(json.dumps({**{g: {"ok": all(c[1] for c in v), "checks": len(v),
                                      "failed": [c[0] for c in v if not c[1]]}
                                  for g, v in sorted(GATES.items())},
                               "_rack": RACK}, indent=1, default=str), encoding="utf-8")
sys.exit(1 if FAIL else 0)
