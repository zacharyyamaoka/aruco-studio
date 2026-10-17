"""Make goldens/evaluate/*.json by running REF's OWN aruco_feature.evaluate()
on stand-in targets, read only (PLAN M2 step 2).

    .venv/Scripts/python tools/make_evaluate_goldens.py

The same guard as tools/make_goldens_from_ref.py: the work runs in a child
started with `python -I -B` from a temp directory; it exits 2 when
`aruco_studio` is importable or already imported. REF's `git status` is
compared before and after.

REF's add-in modules import `adsk`, so they are loaded here from the PINNED
blobs (`git show c8216ff:<path>`, compiled from memory: no bytecode, no
working-tree drift) with REF's own stand-in adsk from
tests/aruco_trim_fixtures.py, the way REF's makers
(tools/make_cells_legacy_golden.py, make_trim_legacy_golden.py) do it. The
core (bam_cad_core) is loaded the same way under the add-in's alias
`arucocore`.

What is stubbed, and nothing else (the entity reads an adapter does):

| REF function | Stand-in |
|---|---|
| `profile_rect`, `_profile_loops_m` | a sketch area: its frame and its loops (exact mm / 1000 on an axis-aligned frame) |
| `aruco_tags.face_frame`, `_face_loops_m` | a planar face: the frame its longest edge gives (maybe reversed), its loops |
| `label_name` | the component's name the label's {name} prints |
| `_trim_face_body`, `aruco_tags.face_loops_2d`, `_body_extent_mm`, `_trim_measure` | REF's plate (aruco_trim_fixtures.install_plate) |

Each case stores the request as a Studio TagSpec dict (the settings as the
node stores them, the numbers as REF's numbers_of read them, the target in
the base frame), the base frame evaluate() used, and REF's outputs: the
board as built, every frame, the layout, the plan, the mark, the label, the
pins, the trim, the notes, the settings a node writes back (settle), its
record pieces and digest, the node's warning words.
"""
from __future__ import annotations

import json
import math
import os
import random
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
OUT = ROOT / "goldens" / "evaluate"
SEED = 20261016


# ======================================================== the parent process

def parent():
    sys.path.insert(0, str(TOOLS))
    import ref_path
    before = ref_path.status()
    t0 = ref_path.now()
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aruco_eval_goldens_") as tmp:
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "USERPROFILE": tmp, "HOME": tmp,
                    "BAM_ARUCO_PRUSASLICER_DIR": str(ref_path.REF / "tests" / "fixtures" / "prusaslicer"),
                    "PYTHONIOENCODING": "utf-8"})
        p = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", str(Path(__file__).resolve()),
                            "--child", str(ref_path.REF), str(TOOLS), str(OUT)], cwd=tmp, env=env)
    after = ref_path.status()
    read = ("CADExporter/bam_cad_core/", "ArucoMarkers/", "tests/aruco_trim_fixtures.py")
    ours = ref_path.new_bytecode(t0, read) + ref_path.status_check(before, after, read=read)
    if ours:
        raise SystemExit("REF's git status changed in files this run read: " + "; ".join(ours))
    if p.returncode:
        raise SystemExit(p.returncode)
    print("REF's git status: unchanged")


# ========================================================= the child process

class PinnedFinder:
    """Serves REF's modules from the pinned commit's blobs (never the
    working tree): ArucoMarkers/<name>.py and tests/<name>.py as top-level
    modules, CADExporter/bam_cad_core as the package `arucocore`."""

    def __init__(self, ref, ref_path):
        self.ref, self.rp = Path(ref), ref_path
        tree = ref_path.git("ls-tree", "-r", "--name-only", ref_path.REF_COMMIT).splitlines()
        self.files = set(tree)
        self.served = {}

    def _rel(self, name):
        if name == "arucocore":
            return "CADExporter/bam_cad_core/__init__.py", True
        if name.startswith("arucocore."):
            return "CADExporter/bam_cad_core/" + name.split(".", 1)[1] + ".py", False
        if "." in name:
            return None, False
        for d in ("ArucoMarkers", "tests"):
            rel = f"{d}/{name}.py"
            if rel in self.files:
                return rel, False
        return None, False

    def find_spec(self, name, path=None, target=None):
        import importlib.util
        rel, pkg = self._rel(name)
        if rel is None or rel not in self.files:
            return None
        spec = importlib.util.spec_from_loader(name, self, origin=str(self.ref / rel),
                                               is_package=pkg)
        spec.has_location = True
        if pkg:
            spec.submodule_search_locations = [str(self.ref / "CADExporter" / "bam_cad_core")]
        self.served[name] = rel
        return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        rel = self.served[module.__name__]
        src = self.rp.show(rel).decode("utf-8")
        module.__file__ = str(self.ref / rel)
        exec(compile(src, str(self.ref / rel), "exec"), module.__dict__)


def child(ref, tools, out):
    sys.dont_write_bytecode = True
    if "aruco_studio" in sys.modules:
        print("REFUSED: aruco_studio is already imported", file=sys.stderr)
        sys.exit(2)
    import importlib
    import importlib.util
    if importlib.util.find_spec("aruco_studio") is not None:
        print("REFUSED: aruco_studio is importable here; a golden must come from REF",
              file=sys.stderr)
        sys.exit(2)
    sys.path.append(str(tools))
    import ref_path
    finder = PinnedFinder(ref, ref_path)
    sys.meta_path.insert(0, finder)
    # data files the pinned modules open by path must equal the pinned blobs
    for rel in ("CADExporter/bam_cad_core/aruco_dictionaries.json",):
        if not ref_path.same_as_pinned(rel):
            raise SystemExit(f"{rel}: REF's working tree differs from {ref_path.REF_COMMIT}")

    FX = importlib.import_module("aruco_trim_fixtures")
    sys.modules.update({"adsk": FX.adsk, "adsk.core": FX.core, "adsk.fusion": FX.fusion})
    import aruco_core                                  # noqa: F401  (drops any arucocore)
    importlib.import_module("arucocore")              # pinned, so aruco_core.load() finds it
    F = importlib.import_module("aruco_feature")
    T = F.aruco_tags
    T.design = lambda: None
    A = aruco_core.module("aruco_autosize")
    SL = aruco_core.module("aruco_slabs")
    M = aruco_core.module("markers")

    cases = build_cases(F)
    rows = [run_case(c, F, T, FX, A, SL, M) for c in cases]
    legacy = run_legacy_goldens(ref, F, T, FX, A, SL, M)
    modules = sorted(set(finder.served.values()))
    shas = {m: ref_path.sha256_at(m) for m in modules}
    doc = {"schema": "arucostudio.golden/1", "name": "evaluate", "ref": str(ref),
           "ref_commit": ref_path.REF_COMMIT, "maker": str(Path(ref) / "ArucoMarkers/aruco_feature.py"),
           "made_by": "tools/make_evaluate_goldens.py",
           "args": {"seed": SEED, "stand_ins": "profile_rect, _profile_loops_m, "
                    "aruco_tags.face_frame, _face_loops_m, label_name; the trim plate of "
                    "tests/aruco_trim_fixtures.py"},
           "sha256": shas, "date": date.today().isoformat()}
    Path(out).mkdir(parents=True, exist_ok=True)
    for name, data in (("matrix", rows), ("legacy", legacy)):
        d = dict(doc, name=f"evaluate_{name}", cases=data)
        p = Path(out) / f"{name}.json"
        p.write_text(json.dumps(d, indent=None, separators=(",", ":"), allow_nan=False) + "\n",
                     encoding="utf-8", newline="\n")
        bad = sum(1 for c in data if "error" in c["out"])
        print(f"evaluate_{name}: {len(data)} cases ({bad} refused) -> {p.relative_to(ROOT)} "
              f"({p.stat().st_size // 1024} KB)", flush=True)


# ================================================================ the cases

def circle(cx, cy, r, n=48, cw=False):
    pts = [(round(cx + r * math.cos(2 * math.pi * k / n), 9),
            round(cy + r * math.sin(2 * math.pi * k / n), 9)) for k in range(n)]
    return pts[::-1] if cw else pts


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


# loop shapes (mm, in the target frame), from REF's makers
SHAPES = {
    "gim43": [circle(2.09, 0.0, 26.5, n=96)] + [circle(x, y, 1.425, n=48, cw=True)
                                                for x, y in ((25.84, 0.0), (2.09, 23.75),
                                                             (-21.66, 0.0), (2.09, -23.75))],
    "plate_holes": [rect(-60, -20, 60, 20), circle(-50, 0, 4, cw=True),
                    circle(50, 0, 4, cw=True)],
    "ell": [[(0, 0), (60, 0), (60, 20), (20, 20), (20, 60), (0, 60)]],
    "ring": [rect(-30, -30, 30, 30), rect(-8, -8, 8, 8)[::-1]],
    "disc53": [circle(0, 0, 26.5, n=64)],
}
SHAPE_AREA = {"gim43": (47.5, 47.5), "plate_holes": (120.0, 40.0), "ell": (60.0, 60.0),
              "ring": (60.0, 60.0), "disc53": (53.0, 53.0)}
BOXES = [(60.0, 40.0), (100.0, 60.0), (100.0, 80.0), (40.0, 40.0), (50.0, 50.0), (80.0, 30.0),
         (33.3, 71.7), (120.0, 90.0), (25.0, 25.0)]
TINY = [(6.0, 6.0), (3.0, 40.0)]
DICTS = ["DICT_4X4_50"] * 6 + ["DICT_5X5_100", "DICT_6X6_250", "DICT_APRILTAG_36h11",
                               "DICT_4X4_1000"]
CELLS = [None, None, {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0},
         {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 0.0}]
TRIMS = [{"rule": 1, "axes": "both", "margin_mm": 0.0, "force": False},
         {"rule": 1, "axes": "x", "margin_mm": 1.5, "force": False},
         {"rule": 1, "axes": "y", "margin_mm": 0.0, "force": True},
         {"rule": 1, "axes": "both", "margin_mm": 2.0, "force": True}]
JUNK_TRIMS = [{"rule": 7, "axes": "both"}, {}, "junk", {"rule": 1, "axes": "sideways"}]
NAMES = ["", "", "Arm", "Gripper:2", "Base plate"]
LABELS = {
    "off": None,
    "black": {"on": True, "place": "black"},
    "white": {"on": True, "place": "white"},
    "auto": {"on": True},
    "white_below_name": {"on": True, "place": "white", "side": "below", "content": "id_name"},
    "white_left": {"on": True, "place": "white", "side": "left"},
    "black_top": {"on": True, "place": "black", "row": "top", "content": "name"},
    "custom": {"on": True, "content": "custom", "text": "{key}|{dict}"},
    "typed_cap": {"on": True, "place": "white", "cap_mm": 2.5},
    "anyway": {"on": True, "place": "white", "side": "above", "cap_mm": 6.0,
               "build_anyway": True},
    "refused": {"on": True, "place": "white", "side": "above", "cap_mm": 6.0},
    "rule1": {"on": True, "place": "white", "rule": 1},
    "manual": {"on": True, "place": "white", "position": "manual", "x_mm": 0.0, "y_mm": -14.0},
    "nudge": {"on": True, "place": "white", "offset_x_mm": 1.0, "offset_y_mm": -0.5},
}


def build_cases(F):
    """The matrix: every factor of PLAN M2 step 2 crossed where it matters,
    sampled (seeded) elsewhere, plus every legacy shape of the settings."""
    rnd = random.Random(SEED)
    out = []

    def add(**kw):
        kw.setdefault("id", f"c{len(out):04d}")
        out.append(kw)

    # 1. layout x mode x op x turn x corner mark, on a box sketch area
    for layout in ("single", "grid", "charuco"):
        for mode in ("both", "black", "white"):
            for op in ("join", "new"):
                for turn in (0, 90, 180, 270):
                    for mark in ("none", "cut", "triangle"):
                        area = {"single": (60.0, 40.0), "grid": (100.0, 60.0),
                                "charuco": (100.0, 80.0)}[layout]
                        add(group="cross", source="profile", area=area, shape=None,
                            s={"layout": layout, "mode": mode, "op": op, "turn": turn,
                               "corner_mark": mark})
    # 2. label x pins x trim x layout x mode (both / black), sampled
    for layout in ("single", "grid", "charuco"):
        for label in ("off", "black", "white"):
            for pin in ("none", "triangle", "round"):
                for trim in (None, 0):
                    mode = rnd.choice(["both", "both", "black", "white"])
                    op = "new" if pin != "none" else rnd.choice(["join", "new"])
                    area = rnd.choice(BOXES[:6])
                    add(group="features", source="profile", area=area, shape=None,
                        plate=trim is not None,
                        s={"layout": layout, "mode": mode, "op": op, "pin": pin,
                           "turn": rnd.choice([0, 90, 180, 270]),
                           "corner_mark": rnd.choice(["none", "cut", "triangle"]),
                           "label": LABELS[label],
                           "trim": TRIMS[0] if trim is not None else None})
    # 3. loop shapes (Black / White only fit on the loops), faces and areas
    for shape in SHAPES:
        for layout in ("single", "grid", "charuco"):
            for mode in ("black", "white", "both"):
                add(group="shapes", source=rnd.choice(["profile", "face"]),
                    area=SHAPE_AREA[shape], shape=shape,
                    s={"layout": layout, "mode": mode, "op": "join",
                       "turn": rnd.choice([0, 90, 180, 270]),
                       "corner_mark": rnd.choice(["none", "cut", "triangle"]),
                       "label": LABELS[rnd.choice(["off", "off", "black", "white", "auto"])],
                       "dictionary": rnd.choice(DICTS), "cells": rnd.choice(CELLS)},
                    n={"size": rnd.choice([0.0, 0.0, 12.0, 20.5])} if layout == "single" else {})
    # 4. typed sizes, cells rules, dictionaries, quiet zones, Auto
    for k in range(120):
        layout = rnd.choice(["single", "grid", "charuco"])
        area = rnd.choice(BOXES)
        n = {}
        if rnd.random() < 0.6:
            n["size"] = round(rnd.uniform(4.0, 40.0), 1)
            if layout == "charuco":
                n["square"] = round(n["size"] * rnd.uniform(1.2, 1.6), 1)
        elif layout == "charuco" and rnd.random() < 0.3:
            n["square"] = round(rnd.uniform(8.0, 25.0), 1)
        s = {"layout": layout, "mode": rnd.choice(["both", "black", "white"]),
             "op": rnd.choice(["join", "new"]), "turn": rnd.choice([0, 90, 180, 270]),
             "corner_mark": rnd.choice(["none", "cut", "triangle"]),
             "dictionary": rnd.choice(DICTS), "cells": rnd.choice(CELLS),
             "quiet_modules": rnd.choice([1.0, 1.0, 0.5, 2.0, 1.5]),
             "label": LABELS[rnd.choice(list(LABELS))] if rnd.random() < 0.4 else None,
             "grow": rnd.random() < 0.2}
        if layout != "single" and n.get("size") and rnd.random() < 0.25:
            s["force"] = [rnd.choice([2, 3, 4]), rnd.choice([2, 3])]
        add(group="sizes", source=rnd.choice(["profile", "profile", "face"]), area=area,
            shape=None, s=s, n=n)
    # 5. heights, pins, has_body, the plate (trim)
    heights = [{}, {"white_offset": -1.0, "white_height": 3.0, "black_offset": 2.0,
                    "black_height": -0.4},
               {"white_offset": -1.0, "white_height": 2.0, "black_offset": 1.4, "black_height": 0.5},
               {"black_offset": 0.0, "black_height": 0.8},
               {"white_offset": 0.5, "white_height": 1.5},
               {"black_offset": 2.6, "black_height": 0.4}, {"black_offset": 1.5, "black_height": -2.5},
               {"white_offset": 0.0, "white_height": -0.6, "black_offset": -0.6,
                "black_height": 0.3},
               {"pin_size": 2.0, "pin_length": 3.0, "pin_tol": 0.4},
               {"pin_size": 4.0, "pin_tol": 0.0}]
    for k in range(110):
        mode = rnd.choice(["both", "both", "black", "white"])
        pin = rnd.choice(["none", "triangle", "round"])
        trim = rnd.random() < 0.45
        s = {"layout": rnd.choice(["single", "grid", "charuco"]), "mode": mode,
             "op": rnd.choice(["join", "new"]), "pin": pin,
             "turn": rnd.choice([0, 90, 180, 270]),
             "corner_mark": rnd.choice(["none", "cut", "triangle"]),
             "label": LABELS[rnd.choice(["off", "black", "white"])] if rnd.random() < 0.4 else None,
             "trim": rnd.choice(TRIMS) if trim else None,
             "has_body": rnd.random() > 0.15}
        add(group="heights", source=rnd.choice(["profile", "profile", "face"]),
            area=rnd.choice(BOXES[:6]), shape=None, plate=trim or rnd.random() < 0.2,
            plate_kw=rnd.choice([{}, {}, {"holes": [(-35.0, 0.0, 3.0)]}, {"w": 60.0, "h": 40.0},
                                 {"face": False}, {"measure": False},
                                 {"loops": [circle(0, 0, 40.0, n=64)]}]),
            s=s, n=dict(rnd.choice(heights)))
    # 6. labels on their own
    for name, lab in LABELS.items():
        if lab is None:
            continue
        for layout in ("single", "grid", "charuco"):
            mode = rnd.choice(["both", "both", "black", "white"])
            add(group="labels", source=rnd.choice(["profile", "face"]),
                area=rnd.choice([(60.0, 40.0), (100.0, 60.0), (100.0, 80.0), (40.0, 40.0)]),
                shape=None, name=rnd.choice(NAMES),
                s={"layout": layout, "mode": mode, "op": rnd.choice(["join", "new"]),
                   "turn": rnd.choice([0, 90, 180, 270]),
                   "corner_mark": rnd.choice(["none", "cut", "triangle"]),
                   "pin": rnd.choice(["none", "triangle"]), "label": lab})
    # 7. faces: x reversed by an upstream edit (keep_x), x_ref, square faces
    for k in range(40):
        area = rnd.choice([(60.0, 40.0), (50.0, 50.0), (100.0, 60.0), (40.0, 40.0)])
        add(group="faces", source="face", area=area, shape=None,
            face={"x0": rnd.choice([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                    [0.0, -1.0, 0.0]]),
                  "x_base": rnd.choice([None, [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
                  "x_ref": rnd.choice([None, "fit", "reversed"])},
            s={"layout": rnd.choice(["single", "grid", "charuco"]),
               "mode": rnd.choice(["both", "black", "white"]),
               "turn": rnd.choice([0, 90, 180, 270]),
               "corner_mark": rnd.choice(["none", "cut", "triangle"])})
    # 8. nothing fits / refused
    for area in TINY:
        for layout in ("single", "grid", "charuco"):
            add(group="refused", source="profile", area=area, shape=None,
                s={"layout": layout, "mode": "both"})
    for layout in ("single", "grid", "charuco"):
        add(group="refused", source="profile", area=(60.0, 40.0), shape=None,
            s={"layout": layout, "mode": "both", "pin": "round", "op": "new"},
            n={"pin_size": 19.0})
        add(group="refused", source="profile", area=(60.0, 40.0), shape=None,
            s={"layout": layout, "mode": "both"}, n={"marker_id": 49})
    # 9. every legacy shape of the settings, at least 12 times each
    legacy = ["chamfer_true", "chamfer_false", "no_origin_v", "rotate_deg", "frame",
              "legacy_numbers", "label_scope_square", "junk_trim", "no_label_rule"]
    for shape_name in legacy:
        for k in range(14):
            layout = ("charuco" if shape_name == "label_scope_square"
                      else rnd.choice(["single", "grid", "charuco"]))
            mode = rnd.choice(["both", "both", "black", "white"])
            add(group="legacy", legacy=shape_name, source=rnd.choice(["profile", "face"]),
                area=rnd.choice(BOXES[:6]), shape=None,
                s={"layout": layout, "mode": mode, "op": rnd.choice(["join", "new"]),
                   "turn": rnd.choice([0, 90, 180, 270]),
                   "corner_mark": rnd.choice(["none", "cut", "triangle"])},
                n={"size": rnd.choice([0.0, 0.0, 15.0])} if layout == "single" else {})
    # 10. z_sign -1, a sketch's x along its y, the base frame turned (exact = False)
    for k in range(24):
        add(group="frames", source="profile", area=rnd.choice(BOXES[:6]), shape=None,
            prof={"z_sign": rnd.choice([1, -1]),
                  "x_sketch": rnd.choice([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])},
            s={"layout": rnd.choice(["single", "grid", "charuco"]),
               "mode": rnd.choice(["both", "black"]), "turn": rnd.choice([0, 90, 180, 270]),
               "corner_mark": rnd.choice(["none", "cut", "triangle"]),
               "label": LABELS[rnd.choice(["off", "white", "black"])]})
    return out


# ============================================================= one case

AXES = ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
O0 = [0.0, 0.0, 0.5]                     # the sketch plane / face, as REF's fixtures


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _surface_loops(case):
    """The target's loops in MODEL mm (the sketch plane / face at z = 5 mm)."""
    if case.get("shape"):
        lp = SHAPES[case["shape"]]
    else:
        w, h = case["area"]
        lp = [rect(-w / 2, -h / 2, w / 2, h / 2)]
    return [[(float(u), float(v)) for u, v in l] for l in lp]


def _project_mm(loops_model, o_cm, x, y):
    """Model mm -> mm in the frame (o, x, y): exact on an axis-aligned frame."""
    o = [c * 10.0 for c in o_cm]
    out = []
    for lp in loops_model:
        pts = []
        for (u, v) in lp:
            d = [u - o[0], v - o[1], 5.0 - o[2]]
            pts.append((_dot(d, x), _dot(d, y)))
        out.append(pts)
    return out


def _extents(loops_model, x, y):
    pts = [p for lp in loops_model for p in lp]
    us = [_dot([u, v, 0.0], x) for u, v in pts]
    vs = [_dot([u, v, 0.0], y) for u, v in pts]
    return (min(us), max(us), min(vs), max(vs))


def _frames(case, s, F, T):
    """The frame profile_rect / face_frame hand evaluate() (cm), from the
    target's loops in model mm: REF's rules on plain points -- x from the
    sketch's x_sketch and z_sign (a profile) or the face's longest edge (a
    face, maybe reversed), turned by the legacy rotate_deg, the box of the
    loops along it (a profile: every loop; a face: its outer loop). An
    unturned frame sits at the plane's origin (as REF's makers' stand-ins)."""
    loops_model = _surface_loops(case)
    W, H = case["area"]
    rot = float(s.get("rotate_deg", 0) or 0)
    if case["source"] == "profile":
        prof = case.get("prof") or {}
        xs = prof.get("x_sketch") or [1.0, 0.0]
        z = [0.0, 0.0, float(prof.get("z_sign", 1))]
        x = F._rotz(F._unit([xs[0], xs[1], 0.0]), z, rot)
        pts = loops_model
    else:
        z = [0.0, 0.0, 1.0]
        x = list((case.get("face") or {}).get("x0") or [1.0, 0.0, 0.0])
        if rot:
            x = F._unit(T._rot(x, z, rot))
        pts = [loops_model[0]]
    y = _cross(z, x)
    if not rot and x == [1.0, 0.0, 0.0] and z == [0.0, 0.0, 1.0]:
        return case["source"], (list(O0), x, y, z, W / 10.0, H / 10.0), loops_model
    u0, u1, v0, v1 = _extents(pts, x, y)
    o = list(O0)
    if rot:
        cu, cv = (u0 + u1) / 2.0, (v0 + v1) / 2.0
        o = [O0[i] + (x[i] * cu + y[i] * cv) / 10.0 for i in range(3)]
    return case["source"], (o, x, y, z, (u1 - u0) / 10.0, (v1 - v0) / 10.0), loops_model


def _stored(case, F):
    """The settings as the node stores them (a JSON value), legacy shapes
    included."""
    s = F.default_settings()
    s.update({"source": case["source"], "z_sign": int((case.get("prof") or {}).get("z_sign", 1)),
              "x_sketch": (case.get("prof") or {}).get("x_sketch") or [1.0, 0.0]
              if case["source"] == "profile" else None,
              "has_body": True, "key": case.get("key") or "tg", "origin_v": 2})
    over = dict(case["s"])
    lab = over.pop("label", None)
    trim = over.pop("trim", None)
    s.update({k: v for k, v in over.items() if v is not None})
    if s.get("cells") is None:
        s.pop("cells", None)
    if lab is not None:
        s["label"] = dict(s["label"], **lab)
    if trim is not None:
        s["trim"] = trim
    lg = case.get("legacy")
    if lg == "chamfer_true":
        s.pop("corner_mark", None)
        s["chamfer"] = True
    elif lg == "chamfer_false":
        s.pop("corner_mark", None)
        s["chamfer"] = False
    elif lg == "no_origin_v":
        s.pop("origin_v", None)
    elif lg == "rotate_deg":
        s["rotate_deg"] = [90, 30, 180, 45, 270, 15][hash(case["id"]) % 6] if False else \
            [90, 30, 180, 45, 270, 15][int(case["id"][1:]) % 6]
    elif lg == "frame":
        s["frame"] = ["opencv", "centre", "top-left"][int(case["id"][1:]) % 3]
    elif lg == "label_scope_square":
        s["label"] = dict(s["label"], on=True, scope="square", place="black")
        s["label"].pop("rule", None)
        s["label"].pop("row", None)
    elif lg == "junk_trim":
        s["trim"] = JUNK_TRIMS[int(case["id"][1:]) % len(JUNK_TRIMS)]
    elif lg == "no_label_rule":
        s["label"] = dict(s["label"], on=True, place="white")
        s["label"].pop("rule", None)
    return json.loads(json.dumps(s))


class _Param:
    def __init__(self, v):
        self.value = v


class _Params:
    def __init__(self, d):
        self.d = d

    def itemById(self, pid):
        if pid not in self.d:
            raise RuntimeError(f"no parameter {pid}")
        return _Param(self.d[pid])


class _NV:
    def __init__(self, stored):
        self.v = json.dumps(stored, sort_keys=True)

    def isExistingValue(self, k):
        return k == "spec"

    def value(self, k):
        return self.v


class FakeNode:
    """What settings_of / numbers_of read off a custom feature."""

    def __init__(self, stored, params_cm):
        self.customNamedValues = _NV(stored)
        self.parameters = _Params(params_cm)


def _params_cm(case, stored, F, SL):
    """The node's parameters (cm; marker_id unitless), as a node of these
    settings carries them; a legacy node: height / thickness / above."""
    mode = stored.get("mode", "both")
    n = F.default_numbers(mode)
    n.update(case.get("n") or {})
    out = {"marker_id": float(n.get("marker_id", 0)), "size": n["size"] / 10.0}
    if stored.get("layout") == "charuco":
        out["square"] = n.get("square", 0.0) / 10.0
    if case.get("legacy") == "legacy_numbers":
        k = int(case["id"][1:])
        h, t, a = [(2.0, 0.6, 0.0), (3.0, 1.0, 0.4), (2.0, 0.4, 0.4), (1.5, 1.2, 0.2)][k % 4]
        out.update(height=h / 10.0, thickness=t / 10.0, above=a / 10.0)
    else:
        for pid in ("white_offset", "white_height", "black_offset", "black_height"):
            out[pid] = n[pid] / 10.0
    if stored.get("pin") not in (None, "none"):
        for pid in ("pin_size", "pin_length", "pin_tol"):
            out[pid] = n[pid] / 10.0
    return out


def _r(v, nd=9):
    if isinstance(v, float):
        return round(v, nd)
    if isinstance(v, (list, tuple)):
        return [_r(c, nd) for c in v]
    if isinstance(v, dict):
        return {str(k): _r(c, nd) for k, c in v.items()}
    return v


def _exact(v):
    """JSON-able, floats exact (repr round-trips)."""
    if isinstance(v, (list, tuple)):
        return [_exact(c) for c in v]
    if isinstance(v, dict):
        return {str(k): _exact(c) for k, c in v.items()}
    return v


def plan_dict(p):
    L = p.layers
    return {"mode": p.mode, "op": p.op, "parts": list(p.parts), "pocket": p.pocket,
            "recess": [[w, list(s)] for w, s in p.recess], "pin": p.pin, "notes": list(p.notes),
            "structure": list(p.structure),
            "layers": {"white": L.white, "black": L.black, "pattern": L.pattern,
                       "surface": L.surface, "depth": L.depth, "raise": L.raise_,
                       "recess": L.recess, "gap": L.gap}}


def lay_dict(lay):
    return {"kind": lay.kind, "marker_m": lay.marker_m, "square_m": lay.square_m,
            "cols": lay.cols, "rows": lay.rows, "separation_m": lay.separation_m,
            "margins_m": list(lay.margins_m), "ok": lay.ok, "notes": list(lay.notes),
            "badges": list(lay.badges), "fill": lay.fill, "dictionary": lay.dictionary,
            "quiet_modules": lay.quiet_modules}


def trim_dict(tp):
    if tp is None:
        return None
    return {"axes": tp.axes, "margin": tp.margin, "outline": list(tp.outline),
            "body": list(tp.body), "keep": list(tp.keep), "pad": tp.pad, "cut": dict(tp.cut),
            "refusals": list(tp.refusals), "notes": list(tp.notes), "forced": tp.forced,
            "face": list(tp.face) if tp.face is not None else None,
            "face_share": tp.face_share, "body_share": tp.body_share,
            "removed_mm3": tp.removed_mm3, "body_mm3": tp.body_mm3, "holes": list(tp.holes),
            "z": list(tp.z) if tp.z is not None else None, "column": list(tp.column())}


def ev_dict(F, ev):
    lab = ev.get("label")
    mark = ev.get("mark")
    return {"spec": ev["spec"].to_dict(), "tag": ev["tag"], "tile": ev["tile"],
            "base": ev["base"], "notes": list(ev["notes"]), "lift_cm": ev["lift_cm"],
            "plan": plan_dict(ev["plan"]), "pins": ev["pins"], "pin_frame": ev["pin_frame"],
            "turn": ev["turn"], "x_fit": ev["x_fit"], "pin_tol": ev["pin_tol"],
            "mode": ev["mode"], "mark": mark.to_dict(6) if mark is not None else None,
            "label": lab.to_dict(6) if lab is not None else None,
            "label_white": ev.get("label_white"),
            "node_warning": F.node_warning(ev), "record_mark": F.mark_record(ev),
            "record_label": F.label_record(ev)}


def _clear(F):
    for c in (F._FIT_CACHE, F._LABEL_CACHE, F._LOOP_CACHE, F._TRIM_CACHE):
        c.clear()


def run_case(case, F, T, FX, A, SL, M):
    _clear(F)
    stored = _stored(case, F)
    params = _params_cm(case, stored, F, SL)
    node = FakeNode(stored, params)
    s = F.settings_of(node)
    n = F.numbers_of(node)
    # what the Studio's TagSpec.numbers holds: what numbers_of READ (mm)
    numbers = {pid: (v if pid == "marker_id" else v * 10.0) for pid, v in params.items()}
    kind, frame, loops_model = _frames(case, s, F, T)
    o, x, y, z, w, h = frame
    name = case.get("name", "")
    if kind == "face" and (case.get("plate_kw") or {}).get("face") is False:
        case["plate_kw"] = {}                      # a face always has itself to measure
    FX.plate(**(case.get("plate_kw") or {}))
    plate = bool(case.get("plate"))
    target = FX.Profile() if kind == "profile" else type("Face", (), {"assemblyContext": None,
                                                                      "body": None})()
    if plate:
        FX.install_plate(F, T)
    else:
        F._trim_face_body = lambda t: (None, None)
    loops_base = _project_mm(loops_model, o, x, y)
    loops_m_cache = {}

    def loops_m(t, o_, x_, y_):
        key = (tuple(o_), tuple(x_), tuple(y_))
        if key not in loops_m_cache:
            lp = _project_mm(loops_model, o_, x_, y_)
            loops_m_cache[key] = [[(u / 1000.0, v / 1000.0) for (u, v) in l] for l in lp]
        return loops_m_cache[key]
    if kind == "profile":
        F.profile_rect = lambda t, s_: (list(o), list(x), list(y), list(z), w, h)
        F._profile_loops_m = loops_m
    else:
        T.face_frame = lambda t, rot=0.0: (list(o), list(x), list(y), list(z), w, h)
        F._face_loops_m = loops_m
        fc = case.get("face") or {}
        if fc.get("x_base"):
            s["x_base"] = list(fc["x_base"])
            stored["x_base"] = list(fc["x_base"])
    F.label_name = lambda t, s_, host=None: name
    # a face's x_ref: the fit's x as made (create() stamps it), maybe reversed
    xr_mode = (case.get("face") or {}).get("x_ref")
    if kind == "face" and xr_mode:
        try:
            ev0 = F.evaluate(target, dict(s), dict(n))
            xr = [round(c, 12) for c in ev0["x_fit"]]
            if xr_mode == "reversed":
                xr = [-c for c in xr]
            s["x_ref"] = xr
            stored["x_ref"] = xr
        except Exception:                          # noqa: BLE001
            pass
        _clear(F)
    # the base frame evaluate() works in: face_frame, then keep_x (a face)
    if kind == "face":
        bx, by, bw, bh = F.keep_x(list(x), list(y), list(z), w, h, s.get("x_base"))
        base = (list(o), list(bx), list(by), list(z), bw, bh)
    else:
        base = (list(o), list(x), list(y), list(z), w, h)
    # the target as an adapter hands it over: the base frame's 2D, mm
    tgt = {"kind": kind, "w_mm": base[4] * 10.0, "h_mm": base[5] * 10.0,
           "loops_mm": _project_mm(loops_model, base[0], base[1], base[2]),
           "has_body": bool(s.get("has_body")), "z_sign": int(s.get("z_sign", 1)),
           "x_ref": ([_dot(s["x_ref"], base[1]), _dot(s["x_ref"], base[2])]
                     if kind == "face" and s.get("x_ref") else None),
           "body_mm": None, "face_loops_mm": None, "body_loops_mm": None}
    if not case.get("shape") and not float(s.get("rotate_deg", 0) or 0):
        tgt["loops_mm"] = []                       # a plain box: the box itself
    if plate:
        if [list(v) for v in base[:4]] != [O0] + [list(a) for a in AXES]:
            raise SystemExit(f"{case['id']}: a plate case needs the plain frame, not {base[:4]}")
        P = FX.PLATE
        u0, v0, z0, u1, v1, z1 = P["box"]
        tgt["body_mm"] = {"u0": u0, "v0": v0, "u1": u1, "v1": v1, "z0": z0, "z1": z1,
                          "measured": bool(P["measure"])}
        if P["volume"] is None and P["box"] != (-P["w"] / 2, -P["h"] / 2, -P["t"], P["w"] / 2,
                                                 P["h"] / 2, 0.0):
            tgt["body_mm"]["depth"] = P["t"]
        if kind == "profile":
            tgt["face_loops_mm"] = ([[list(p) for p in lp] for lp in P["loops"]]
                                    if P["face"] else None)
        else:
            # a face's own loops; the plate stands in for its body only
            tgt["face_loops_mm"] = None
    out = {}
    try:
        ev = F.evaluate(target, s, n)
        out["ev"] = _exact(ev_dict(F, ev))
        out["layout"] = _exact(lay_dict(ev["layout"]))
        out["trim"] = _exact(trim_dict(ev.get("trim")))
        s2, n2 = F.settle(s, n, ev)
        out["settled"] = _exact({"settings": s2, "numbers": n2})
        out["optical"] = _exact(F.optical_of_ev(ev, s.get("key") or "tg"))
        out["digest"] = F.ev_digest(ev)
        tag = M.TagDef(key=s.get("key") or "tg", component="", spec=ev["spec"],
                       origin=list(ev["tag"][0]), x_axis=list(ev["tag"][1]),
                       y_axis=list(ev["tag"][2]), z_axis=list(ev["tag"][3]),
                       name=f"ArUco {s.get('key') or 'tg'}")
        rec = tag.to_dict()
        rec["fusion"] = F.record_extras({}, ev)
        out["record"] = _exact(rec)
        out["record_same"] = F.record_same(rec, ev)
        out["node_name"] = F._label(s.get("key") or "tg", ev["spec"], s["mode"],
                                    F.node_warning(ev))
    except Exception as exc:                       # noqa: BLE001
        out = {"error": f"{type(exc).__name__}: {exc}"}
    spec = {"schema": "arucostudio.tagspec/1", "settings": stored, "numbers": numbers,
            "target": tgt, "name": name, "key": stored.get("key", "")}
    return {"id": case["id"], "group": case["group"], "legacy": case.get("legacy"),
            "base": _exact(base), "plate": bool(plate),
            "plate_kw": case.get("plate_kw") or {}, "in": spec,
            "s": _exact(s), "n": _exact(n), "out": out}


# ======================================== REF's own two evaluate() goldens

def run_legacy_goldens(ref, F, T, FX, A, SL, M):
    """REF's 12 cells + 26 trim evaluate() cases, re-run at c8216ff on the
    same stand-ins their makers used (the expected outputs stay theirs: the
    copied goldens in goldens/ref/). This gives each one a TagSpec and the
    full outputs of today's code, so the replay can compare everything."""
    import ref_path
    out = []
    cells = json.loads(ref_path.show("tests/fixtures/aruco_cells_legacy_golden.json"))
    trim = json.loads(ref_path.show("tests/fixtures/aruco_trim_legacy_golden.json"))
    for k, c in enumerate(cells["evaluate"]):
        out.append(_legacy_case(f"cells{k:02d}", "cells", c, F, T, FX, M, cells_style=True))
    for k, c in enumerate(trim["evaluate"]):
        out.append(_legacy_case(f"trim{k:02d}", "trim", c, F, T, FX, M, cells_style=False))
    return out


def _legacy_case(cid, src, c, F, T, FX, M, cells_style):
    _clear(F)
    w, h = c["area"]
    shape = c.get("shape")
    if shape:
        loops_mm = SHAPES[shape]
        loops = [[(x_ / 1000.0, y_ / 1000.0) for x_, y_ in lp] for lp in loops_mm]
    elif cells_style:
        loops_mm = [rect(-w / 2, -h / 2, w / 2, h / 2)]
        loops = [[(-w / 2000, -h / 2000), (w / 2000, -h / 2000), (w / 2000, h / 2000),
                  (-w / 2000, h / 2000)]]
    else:
        loops_mm = [rect(-w / 2, -h / 2, w / 2, h / 2)]
        loops = [[(x_ / 1000.0, y_ / 1000.0) for x_, y_ in lp] for lp in loops_mm]
    F._trim_face_body = lambda t: (None, None)
    F.label_name = lambda t, s_, host=None: ""
    F.profile_rect = lambda t, s_: ([0.0, 0.0, 0.5], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                    [0.0, 0.0, 1.0], w / 10.0, h / 10.0)
    F._profile_loops_m = lambda t, o, x, y: loops
    s = dict(F.default_settings(), source="profile", z_sign=1, x_sketch=[1.0, 0.0],
             has_body=True)
    if cells_style:
        s.update(c["settings"])
        s["jo_v"] = 1
    else:
        s["key"] = "tg"
        s.update({k: v for k, v in c["settings"].items() if k != "label"})
        if "label" in c["settings"]:
            s["label"] = dict(s["label"], **c["settings"]["label"])
        s = F.normalise(s)
        s["jo_v"] = 1
    n = dict(F.default_numbers(s["mode"]), **c["numbers"])
    out = {}
    try:
        ev = F.evaluate(FX.Profile(), s, n)
        out["ev"] = _exact(ev_dict(F, ev))
        out["layout"] = _exact(lay_dict(ev["layout"]))
        out["trim"] = _exact(trim_dict(ev.get("trim")))
        s2, n2 = F.settle(s, n, ev)
        out["settled"] = _exact({"settings": s2, "numbers": n2})
        out["optical"] = _exact(F.optical_of_ev(ev, s.get("key") or "tg"))
        out["digest"] = F.ev_digest(ev)
    except Exception as exc:                       # noqa: BLE001
        out = {"error": f"{type(exc).__name__}: {exc}"}
    tgt = {"kind": "profile", "w_mm": float(w), "h_mm": float(h),
           "loops_mm": [[list(p) for p in lp] for lp in loops_mm] if shape else [],
           "has_body": bool(s.get("has_body")), "z_sign": 1, "x_ref": None, "body_mm": None,
           "face_loops_mm": None, "body_loops_mm": None,
           "box_m": "w/2000" if cells_style else "(w/2)/1000"}
    spec = {"schema": "arucostudio.tagspec/1", "settings": _exact(s), "numbers": _exact(n),
            "target": tgt, "name": "", "key": s.get("key", "")}
    return {"id": cid, "group": src, "legacy": None,
            "base": [[0.0, 0.0, 0.5], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0],
                     w / 10.0, h / 10.0], "plate": False, "plate_kw": {},
            "in": spec, "s": _exact(s), "n": _exact(n), "out": out, "source": src,
            "ref_case": c}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(*sys.argv[2:5])
    else:
        parent()
