"""Make the goldens under goldens/ by running REF's OWN code, read only.

    .venv/Scripts/python tools/make_goldens_from_ref.py            # every golden
    .venv/Scripts/python tools/make_goldens_from_ref.py board trim # some

A golden can never come from the new code:

* the work runs in a child process started with `python -I` (no script
  directory, no PYTHONPATH, no user site) from a temp directory, with REF's
  `CADExporter` as sys.path[0];
* the child refuses to run (exit 2) when `aruco_studio` is importable, is
  already imported, or sys.path[0] is not inside REF;
* REF's files are imported only when they equal the pinned commit, and REF's
  `git status --porcelain` must be the same before and after.

REF modules that import `adsk` at the top are NEVER imported. Their pure
functions (aruco_restructure.restructure_plan, aruco_tags._place_joint_origin's
maths) are taken from the pinned blob with `ast` and exec'd alone, with plain
stand-ins for the one Fusion call (`_jo_probe` returns a frame). That is
REF's code, unchanged, without Fusion.

Every file holds `ref_commit`, `maker` (the REF file whose code made the
numbers, as a path under REF), `made_by`, the REF files' sha256, the maker's
arguments and the date. tests/core/test_golden_provenance.py checks them.

"Copied" goldens (cells, label rule 1, trim, the GIM43 disc) are REF's own
fixture files, wrapped: `golden` is the file's JSON unchanged, `sha256` the
file's bytes at c8216ff, `code` the commit their own maker ran at.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
OUT = ROOT / "goldens"

ALL = ["copies", "dictionary", "board", "origin", "slabs", "chamfer", "autosize", "label", "trim",
       "numbering", "restructure", "jo_maths", "presets", "prusa"]


# ======================================================== the parent process

def parent(names):
    sys.path.insert(0, str(TOOLS))
    import ref_path
    before = ref_path.status()
    with tempfile.TemporaryDirectory(prefix="aruco_goldens_") as tmp:
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "USERPROFILE": tmp, "HOME": tmp,
                    "BAM_ARUCO_PRUSASLICER_DIR": str(ref_path.REF / "tests" / "fixtures" / "prusaslicer"),
                    "PYTHONIOENCODING": "utf-8"})
        p = subprocess.run([sys.executable, "-I", "-X", "utf8", str(Path(__file__).resolve()),
                            "--child", str(ref_path.REF), str(TOOLS), str(OUT), *names],
                           cwd=tmp, env=env)
    after = ref_path.status()
    if before != after:
        raise SystemExit(f"REF's git status changed: before {before!r}, after {after!r}")
    if p.returncode:
        raise SystemExit(p.returncode)
    print("REF's git status: unchanged")


# ========================================================= the child process

def child(ref, tools, out, names):
    if "aruco_studio" in sys.modules:
        print("REFUSED: aruco_studio is already imported", file=sys.stderr)
        sys.exit(2)
    import importlib.util
    if importlib.util.find_spec("aruco_studio") is not None:
        print("REFUSED: aruco_studio is importable here; a golden must come from REF",
              file=sys.stderr)
        sys.exit(2)
    ref = Path(ref).resolve()
    sys.path.insert(0, str(ref / "CADExporter"))
    sys.path.insert(1, str(ref / "ArucoMarkers"))
    sys.path.append(str(tools))
    if not Path(sys.path[0]).resolve().is_relative_to(ref):
        print("REFUSED: sys.path[0] is not inside REF", file=sys.stderr)
        sys.exit(2)
    import golden_cases as GC
    import ref_path

    def pinned(rel):
        if not ref_path.same_as_pinned(rel):
            raise SystemExit(f"{rel}: REF's working tree differs from {ref_path.REF_COMMIT}")
        return ref_path.sha256_at(rel)

    def write(name, maker_rel, modules, args, cases, extra=None):
        doc = {"schema": "arucostudio.golden/1", "name": name, "ref": str(ref),
               "ref_commit": ref_path.REF_COMMIT, "maker": str(ref / maker_rel),
               "made_by": "tools/make_goldens_from_ref.py", "args": args,
               "sha256": {m: pinned(m) for m in modules}, "date": date.today().isoformat(),
               "cases": cases}
        if extra:
            doc.update(extra)
        path = Path(out) / f"{name}.json"
        path.write_text(json.dumps(doc, indent=None, separators=(",", ":"), allow_nan=False)
                        + "\n", encoding="utf-8")
        print(f"{name}: {len(cases)} cases -> goldens/{name}.json "
              f"({path.stat().st_size // 1024} KB)", flush=True)

    core = "CADExporter/bam_cad_core/"

    def mods(*names_):
        return [core + n + ".py" for n in names_]

    for m in mods("aruco_dict", "aruco_board", "aruco_origin", "aruco_slabs", "aruco_chamfer",
                  "aruco_autosize", "aruco_label", "aruco_trim", "aruco_numbering", "markers",
                  "fiducials", "print_sheet"):
        pinned(m)
    from bam_cad_core import (aruco_autosize as A, aruco_board as B, aruco_chamfer as C,  # noqa
                              aruco_dict as D, aruco_label as L, aruco_numbering as N,
                              aruco_origin as OR, aruco_slabs as S, aruco_trim as T, markers as M)

    for name in names:
        if name == "copies":
            copies(ref, out, ref_path, pinned)
        elif name == "dictionary":
            write("dictionary", core + "aruco_dict.py", mods("aruco_dict", "fiducials") +
                  [core + "aruco_dictionaries.json"], {"ids": "every id of every dictionary"},
                  [{"in": c, "out": GC.norm(GC.dictionary_run(c, D))} for c in GC.dictionary_cases(D)])
        elif name == "board":
            write("board", core + "aruco_board.py", mods("aruco_board", "aruco_dict"),
                  {"table": "golden_cases.board_cases"},
                  [{"in": c, "out": GC.norm(GC.board_run(c, B))} for c in GC.board_cases(B)])
        elif name == "origin":
            write("origin", core + "aruco_origin.py", mods("aruco_origin"),
                  {"table": "golden_cases.origin_cases"},
                  [{"in": c, "out": GC.norm(GC.origin_run(c, OR))} for c in GC.origin_cases(OR)])
        elif name == "slabs":
            write("slabs", core + "aruco_slabs.py", mods("aruco_slabs"),
                  {"table": "golden_cases.slabs_cases"},
                  [{"in": c, "out": GC.norm(GC.slabs_run(c, S))} for c in GC.slabs_cases(S)])
        elif name == "chamfer":
            cases = [{"in": c, "out": GC.norm(GC.chamfer_run(c, C))} for c in GC.chamfer_cases(C)]
            cases += [{"in": {"fn": "choice_of", "settings": s}, "out": GC.norm(GC.guarded(C.choice_of, s))}
                      for s in GC.CHOICE_SETTINGS]
            write("chamfer", core + "aruco_chamfer.py", mods("aruco_chamfer"),
                  {"table": "golden_cases.chamfer_cases + CHOICE_SETTINGS"}, cases)
        elif name == "autosize":
            pinned("ArucoMarkers/aruco_autosize_gallery.py")
            import aruco_autosize_gallery as G       # REF: lazy adsk only inside its Fusion half
            write("autosize", core + "aruco_autosize.py",
                  mods("aruco_autosize", "aruco_board", "markers") + ["ArucoMarkers/aruco_autosize_gallery.py"],
                  {"table": "golden_cases.autosize_cases", "cells": GC.CELLS},
                  [{"in": c, "out": GC.norm(GC.autosize_run(c, A, G))} for c in GC.autosize_cases(G)])
        elif name == "label":
            write("label", core + "aruco_label.py", mods("aruco_label", "aruco_chamfer", "markers"),
                  {"table": "golden_cases.label_cases (seed 20261016)"},
                  [{"in": c, "out": GC.norm(GC.label_run(c, L, M, C))} for c in GC.label_cases(L)])
        elif name == "trim":
            cases = [{"in": c, "out": GC.norm(GC.trim_run(c, T))} for c in GC.trim_cases(T)]
            cases += [{"in": {"fn": "trim_of", "raw": r}, "out": GC.norm(GC.guarded(T.trim_of, r))}
                      for r in GC.TRIM_OF]
            write("trim", core + "aruco_trim.py", mods("aruco_trim"),
                  {"table": "golden_cases.trim_cases (seed 16102026) + TRIM_OF"}, cases)
        elif name == "numbering":
            numbering(ref, write, pinned, GC, N, M)
        elif name == "restructure":
            restructure(ref, write, pinned, GC, S)
        elif name == "jo_maths":
            jo_maths(ref, write, pinned, GC)
        elif name == "presets":
            presets(ref, write, pinned, GC)
        elif name == "prusa":
            prusa(ref, write, pinned, GC)
        else:
            raise SystemExit(f"unknown golden {name!r}; known: {', '.join(ALL)}")


def copies(ref, out, ref_path, pinned):
    """REF's own golden fixtures, unchanged inside a provenance wrapper."""
    dest = Path(out) / "ref"
    dest.mkdir(parents=True, exist_ok=True)
    items = [("tests/fixtures/aruco_cells_legacy_golden.json", "tools/make_cells_legacy_golden.py", "196454c"),
             ("tests/fixtures/aruco_label_rule1_golden.json", "tools/make_label_rule1_golden.py", "8473e14"),
             ("tests/fixtures/aruco_trim_legacy_golden.json", "tools/make_trim_legacy_golden.py", "5cf71bd"),
             ("tests/fixtures/aruco_label_gim43_disc.json", "tests/aruco_label_fixtures.py", "measured")]
    for rel, maker, code in items:
        pinned(rel)
        raw = ref_path.show(rel)
        doc = {"schema": "arucostudio.golden/1", "name": Path(rel).stem, "ref": str(ref),
               "ref_commit": ref_path.REF_COMMIT, "maker": str(ref / maker), "code": code,
               "made_by": "tools/make_goldens_from_ref.py (copied verbatim)", "source": rel,
               "sha256": ref_path.sha256_at(rel), "date": date.today().isoformat(),
               "golden": json.loads(raw.decode("utf-8"))}
        (dest / Path(rel).name).write_text(json.dumps(doc, indent=None, separators=(",", ":"),
                                                      ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"copied {rel} -> goldens/ref/{Path(rel).name}")
    # PrusaSlicer's profiles: text files, copied byte for byte, with a manifest
    pdest = Path(out) / "prusaslicer"
    files = [l for l in ref_path.git("ls-tree", "-r", "--name-only", ref_path.REF_COMMIT,
                                     "tests/fixtures/prusaslicer").splitlines() if l.strip()]
    manifest = {"schema": "arucostudio.golden/1", "name": "prusaslicer", "ref": str(ref),
                "ref_commit": ref_path.REF_COMMIT, "maker": str(ref / "tests/fixtures/prusaslicer"),
                "made_by": "tools/make_goldens_from_ref.py (copied verbatim)",
                "date": date.today().isoformat(), "sha256": {}}
    for rel in files:
        raw = ref_path.show(rel)
        p = pdest / Path(rel).relative_to("tests/fixtures/prusaslicer")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        manifest["sha256"][Path(rel).relative_to("tests/fixtures/prusaslicer").as_posix()] = \
            ref_path.sha256_at(rel)
    (pdest / "provenance.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"copied {len(files)} PrusaSlicer fixture files -> goldens/prusaslicer/")


def extract(ref_path, rel, names):
    """The source of these top-level defs / assignments of a REF file at the
    pinned commit (ast), in file order."""
    import ast
    src = ref_path.show(rel).decode("utf-8")
    lines = src.split("\n")
    tree = ast.parse(src)
    got, found = [], set()
    for node in tree.body:
        nm = []
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            nm = [node.name]
        elif isinstance(node, ast.Assign):
            nm = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if set(nm) & set(names):
            found |= set(nm) & set(names)
            got.append("\n".join(lines[node.lineno - 1:node.end_lineno]))
    missing = set(names) - found
    if missing:
        raise SystemExit(f"{rel}: not found: {sorted(missing)}")
    return "\n\n\n".join(got) + "\n"


def numbering(ref, write, pinned, GC, N, M):
    import ref_path
    rel = "tests/test_aruco_numbering.py"
    pinned(rel)
    ns = {"math": __import__("math"), "TagSpec": M.TagSpec, "TagDef": M.TagDef,
          "OccurrenceRef": M.OccurrenceRef}
    exec(compile(extract(ref_path, rel, ["T", "tag", "occ", "fixtures"]), rel, "exec"), ns)
    cases = []
    for name, (tags, occs) in ns["fixtures"]().items():
        inp = {"fixture": name, "tags": [t.to_dict() for t in tags],
               "occurrences": [{"path": o.path, "component": o.component, "transform": o.transform,
                                "visible": o.visible, "linked": o.linked} for o in occs]}
        cases.append({"in": inp, "out": GC.norm(GC.numbering_run(name, (tags, occs), N))})
    write("numbering", "CADExporter/bam_cad_core/aruco_numbering.py",
          ["CADExporter/bam_cad_core/aruco_numbering.py", "CADExporter/bam_cad_core/markers.py", rel],
          {"fixtures": "REF tests/test_aruco_numbering.py fixtures() F1..F11, exec'd from the blob"},
          cases)


def restructure(ref, write, pinned, GC, S):
    import itertools
    import ref_path
    rel = "ArucoMarkers/aruco_restructure.py"
    pinned(rel)
    ns = {}
    exec(compile(extract(ref_path, rel, ["ROLE_ORDER", "has_combine", "restructure_plan"]), rel,
                 "exec"), ns)
    R = type("R", (), {"has_combine": staticmethod(ns["has_combine"]),
                       "restructure_plan": staticmethod(ns["restructure_plan"])})
    sts = GC.structures(S)
    cases = [{"in": {"old": [op_o, list(p_o)], "new": [op_n, list(p_n)]},
              "out": GC.norm(GC.restructure_run(((op_o, p_o), (op_n, p_n)), R))}
             for (op_o, p_o), (op_n, p_n) in itertools.product(sts, sts)]
    write("restructure", rel, [rel, "CADExporter/bam_cad_core/aruco_slabs.py"],
          {"how": "has_combine / restructure_plan exec'd from the pinned blob (the module imports "
                  "adsk, never imported); every pair of golden_cases.structures(aruco_slabs)",
           "role_order": list(ns["ROLE_ORDER"])}, cases)


def jo_maths(ref, write, pinned, GC):
    import math
    import ref_path
    rel = "ArucoMarkers/aruco_tags.py"
    pinned(rel)
    ns = {"math": math}
    exec(compile(extract(ref_path, rel, ["_sub", "_dot", "_cross", "_unit", "_rot", "_frame_error",
                                         "_solve3", "_place_joint_origin"]), rel, "exec"), ns)
    cases = []
    for c in GC.jo_cases():
        base = c["base"]
        added = []
        ns["_jo_probe"] = lambda comp, geo, *p: base
        ns["_jo_add"] = lambda comp, geo, *params: added.append(params) or ("jo", params)
        ns["_jo_read"] = lambda jo: c["target"]        # Fusion agrees: the first solve stands
        ns["_delete_quietly"] = lambda jo: True
        jo, err, params = ns["_place_joint_origin"](None, None, c["target"], 1e-6, 1e-6)
        rot = [ns["_rot"](base[1], base[3], d) for d in (0.0, 33.0, -90.0)]
        cases.append({"in": c, "out": GC.norm({"angle": params[0], "offsets": params[1],
                                               "flip": params[2], "added": added,
                                               "frame_error": ns["_frame_error"](base, c["target"]),
                                               "solve3": ns["_solve3"](base[1:], c["target"][0]),
                                               "rot": rot})})
    write("jo_maths", rel, [rel],
          {"how": "_place_joint_origin and its vector helpers exec'd from the pinned blob (the "
                  "module imports adsk, never imported); _jo_probe returns the base frame, "
                  "_jo_read the target (the first solve stands)", "frames": "golden_cases.jo_cases"},
          cases)


PRESET_ODD = [{}, {"name": "x", "tag": {"mode": "sideways", "white_height_mm": "tall",
                                        "quiet_modules": 9, "pin_size_mm": 0.1,
                                        "dictionary": "DICT_5X5_100", "grow": 1},
                   "cells": {"of": "cell", "step": "line", "mm": -1, "min_lines": 2.5},
                   "label": {"place": "white", "cap_mm": 3.5, "content": 7}, "extra": 1},
              {"profile": {"name": "p", "nozzle_mm": 0.4, "line_mm": 0.45, "layer_mm": 0.2},
               "cells": {"of": "cell", "step": "line", "mm": 0.5, "min_lines": 3}},
              {"tag": {"black_step_mm": 0.3, "pin": "round", "pin_tol_mm": 0.2, "corner_mark": "cut"}},
              "not a dict", None, {"label": {"on": True, "row": "square", "nozzle_mm": 0.25}}]
MIN_TEXTS = ["2", "2.0 mm", "3 lines", "1 line", "", " 2,5mm ", "abc", "-1 mm", "2.5 lines", "nan",
             "0", "12 line"]
LAYER = [(d, lay, first) for d in (-0.6, 0.1, 0.2, 0.52, 0.84, 1.0, 2.0) for lay in (0.32, 0.2, 0.0)
         for first in (0.2, 0.0)]
NAMES = ["", "  ", "This tag", "x (modified)", "y" * 81, "Update 'Default'", "Delete 'x'", "Fine",
         "Default"]


def presets(ref, write, pinned, GC):
    for m in ("ArucoMarkers/aruco_presets.py", "ArucoMarkers/aruco_prusa.py", "ArucoMarkers/aruco_core.py"):
        pinned(m)
    import aruco_presets as P   # no adsk (it says so; tests drive it directly)
    import aruco_prusa as R
    fix = os.environ["BAM_ARUCO_PRUSASLICER_DIR"]
    profs = [R.profile(u["name"], fix) for u in R.user_prints(fix)]
    d = P.default_preset()
    cases = [{"in": {"fn": "default_preset"}, "out": GC.norm(d)}]
    for i, p in enumerate(PRESET_ODD):
        cases.append({"in": {"fn": "normalise", "p": p}, "out": GC.norm(P.normalise(p))})
        n = P.normalise(p)
        cases.append({"in": {"fn": "cell_setting", "p": n}, "out": GC.norm(P.cell_setting(n))})
        cases.append({"in": {"fn": "changes", "a": d, "b": n},
                      "out": GC.norm({"changes": P.changes(d, n), "same": P.same(d, n),
                                      "words": P.describe_changes(d, n),
                                      "words2": P.describe_changes(n, d, limit=2)})})
    for pr in profs:
        fp = P.from_profile(pr)
        cases.append({"in": {"fn": "from_profile", "profile": pr}, "out": GC.norm(fp)})
        cases.append({"in": {"fn": "cell_setting", "p": fp}, "out": GC.norm(P.cell_setting(fp))})
        cases.append({"in": {"fn": "changes", "a": d, "b": fp},
                      "out": GC.norm({"changes": P.changes(d, fp), "same": P.same(d, fp),
                                      "words": P.describe_changes(d, fp),
                                      "words2": P.describe_changes(fp, d, limit=2)})})
    for t in MIN_TEXTS:
        cases.append({"in": {"fn": "parse_min", "text": t}, "out": GC.norm(P.parse_min(t))})
    for c in ({"min_mm": 2.0, "min_lines": 0}, {"min_mm": 0.0, "min_lines": 3},
              {"min_mm": 0.0, "min_lines": 1}, {}):
        cases.append({"in": {"fn": "min_text", "c": c}, "out": P.min_text(c)})
    for args in LAYER:
        cases.append({"in": {"fn": "layer_note", "args": list(args)},
                      "out": P.layer_note(*args)})
    for nm in NAMES:
        cases.append({"in": {"fn": "valid_name", "name": nm},
                      "out": [P.valid_name(nm), P.unique_name(nm, {"Default", "Fine", "Fine (2)"})]})
    write("presets", "ArucoMarkers/aruco_presets.py",
          ["ArucoMarkers/aruco_presets.py", "ArucoMarkers/aruco_prusa.py", "ArucoMarkers/aruco_core.py",
           "CADExporter/bam_cad_core/aruco_slabs.py", "CADExporter/bam_cad_core/aruco_label.py"],
          {"profiles": "REF tests/fixtures/prusaslicer (BAM_ARUCO_PRUSASLICER_DIR)"}, cases)


WIDTHS = [({"extrusion_width": "0"}, "extrusion_width", 0.6, 0.2, 0.2),
          ({"extrusion_width": "250%"}, "extrusion_width", 0.6, 0.2, 0.2),
          ({"extrusion_width": "0.45"}, "extrusion_width", 0.4, 0.2, 0.2),
          ({"first_layer_extrusion_width": "150%"}, "first_layer_extrusion_width", 0.4, 0.2, 0.3),
          ({"top_infill_extrusion_width": "0", "extrusion_width": "0.5"}, "top_infill_extrusion_width",
           0.4, 0.2, 0.2), ({}, "perimeter_extrusion_width", None, 0.2, 0.2),
          ({"extrusion_width": "x"}, "extrusion_width", 0.4, 0.2, 0.2)]
NOZZLES = [({}, "0.30mm QUALITY @0.6 nozzle - GEARS"), ({}, "0.32mm ERGO @COREONE 0.6"),
           ({"output_filename_format": "{x}_0.25n_{y}"}, "x"), ({}, "plain"),
           ({"compatible_printers_condition": "nozzle_diameter[0]==0.4 and x"}, "")]
LENGTHS = [("0.68", None), ("105%", 0.2), ("", 0.2), ("0", 0.3), ("abc", None), ("50%", None),
           (None, 0.2), ("inf", None)]


def prusa(ref, write, pinned, GC):
    pinned("ArucoMarkers/aruco_prusa.py")
    import aruco_prusa as R
    fix = os.environ["BAM_ARUCO_PRUSASLICER_DIR"]
    cases = []
    for u in R.user_prints(fix):
        pr = R.profile(u["name"], fix)
        cases.append({"in": {"fn": "profile", "name": u["name"]},
                      "out": GC.norm({"profile": pr, "describe": R.describe(pr),
                                      "resolve": R.resolve(u["name"], fix)})})
    for nm in ("0.32mm SPEED @MK4IS 0.6", "0.20mm SPEED @MK4IS 0.4", "nope"):
        cases.append({"in": {"fn": "resolve", "name": nm}, "out": GC.norm(R.resolve(nm, fix))})
    cases.append({"in": {"fn": "aruco_profiles"},
                  "out": GC.norm([p["name"] for p in R.aruco_profiles(fix)])})
    cases.append({"in": {"fn": "user_prints"}, "out": [u["name"] for u in R.user_prints(fix)]})
    for w in WIDTHS:
        cases.append({"in": {"fn": "width_of", "args": list(w)}, "out": R.width_of(*w)})
    for n in NOZZLES:
        cases.append({"in": {"fn": "nozzle_of", "args": list(n)}, "out": R.nozzle_of(*n)})
    for ln in LENGTHS:
        cases.append({"in": {"fn": "length", "args": list(ln)}, "out": GC.norm(R.length(*ln))})
    cases.append({"in": {"fn": "describe", "p": None}, "out": R.describe(None)})
    write("prusa", "ArucoMarkers/aruco_prusa.py",
          ["ArucoMarkers/aruco_prusa.py"] + [f"tests/fixtures/prusaslicer/{p}" for p in
                                             ("print/0.32mm SPEED @MK4IS 0.6 - Aruco.ini",)],
          {"profiles": "REF tests/fixtures/prusaslicer (BAM_ARUCO_PRUSASLICER_DIR)"}, cases)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:] or ALL)
    else:
        parent(sys.argv[1:] or ALL)
