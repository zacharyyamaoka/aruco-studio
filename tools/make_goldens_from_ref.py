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
       "numbering", "restructure", "jo_maths", "presets", "prusa", "preset_library", "settings", "form"]


# ======================================================== the parent process

def parent(names):
    sys.path.insert(0, str(TOOLS))
    import ref_path
    before = ref_path.status()
    t0 = ref_path.now()
    with tempfile.TemporaryDirectory(prefix="aruco_goldens_") as tmp:
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "USERPROFILE": tmp, "HOME": tmp,
                    "BAM_ARUCO_PRUSASLICER_DIR": str(ref_path.REF / "tests" / "fixtures" / "prusaslicer"),
                    "PYTHONIOENCODING": "utf-8"})
        p = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", str(Path(__file__).resolve()),
                            "--child", str(ref_path.REF), str(TOOLS), str(OUT), *names],
                           cwd=tmp, env=env)
    after = ref_path.status()
    read = ("CADExporter/", "tests/fixtures/", "tools/make_", "ArucoMarkers/aruco_core.py", "ArucoMarkers/aruco_presets.py", "ArucoMarkers/aruco_prusa.py", "ArucoMarkers/aruco_preset_library.py", "ArucoMarkers/aruco_autosize_gallery.py")
    ours = ref_path.new_bytecode(t0, read) + ref_path.status_check(before, after, read=read)
    if ours:
        raise SystemExit("REF's git status changed in files this run read: " + "; ".join(ours))
    if p.returncode:
        raise SystemExit(p.returncode)
    print("REF's git status: unchanged")


# ========================================================= the child process

def child(ref, tools, out, names):
    sys.dont_write_bytecode = True      # never a .pyc in REF (python -B as well)
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

    EXEC_ONLY = {"ArucoMarkers/aruco_feature.py", "ArucoMarkers/aruco_restructure.py",
                 "ArucoMarkers/aruco_extrude_cmd.py", "ArucoMarkers/aruco_extrude_ui.py",
                 "ArucoMarkers/bam_fusion_ui.py",
                 "ArucoMarkers/aruco_tags.py", "tests/test_aruco_numbering.py"}

    def pinned(rel):
        """The file's sha256 at the pinned commit. A file that is IMPORTED
        must also equal the pinned commit in REF's working tree; a file whose
        functions are exec'd from the pinned blob (EXEC_ONLY) need not."""
        if rel in EXEC_ONLY:
            return ref_path.sha256_at(rel)
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
                        + "\n", encoding="utf-8", newline="\n")
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
        elif name == "preset_library":
            preset_library(ref, write, pinned, GC)
        elif name == "settings":
            settings_golden(ref, write, pinned, GC)
        elif name == "form":
            form_golden(ref, write, pinned, GC)
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
                                                      ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
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
    (pdest / "provenance.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n")
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
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            got.append("\n".join(lines[start - 1:node.end_lineno]))
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


NODE_SETTINGS = [
    ({}, {}), ({"mode": "both", "op": "new"}, {"black_offset": 2.3}),
    ({"mode": "black", "corner_mark": "triangle", "pin": "round"}, {"pin_size": 4.0, "pin_tol": 0.2}),
    ({"mode": "both", "chamfer": True, "grow": True, "quiet_modules": 1.5}, {"white_height": 1.6}),
    ({"mode": "white", "dictionary": "DICT_6X6_250",
      "cells": {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0}}, {}),
    ({"mode": "both", "cells": {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 0.0},
      "label": {"on": True, "content": "id_name", "place": "white", "cap_mm": 3.5, "rule": 2}},
     {"black_height": 0.4}),
    ({"cells": {"rule": 1, "of": "cell", "mm": 0.45, "min_mm": 1.35}}, {}),
]


def preset_library(ref, write, pinned, GC):
    for m in ("ArucoMarkers/aruco_preset_library.py", "ArucoMarkers/aruco_presets.py",
              "ArucoMarkers/aruco_prusa.py", "ArucoMarkers/aruco_core.py"):
        pinned(m)
    import aruco_preset_library as PL   # no adsk at the top (only inside its palette half)
    import aruco_presets as P
    import aruco_prusa as R
    fix = os.environ["BAM_ARUCO_PRUSASLICER_DIR"]
    profs = [R.profile(u["name"], fix) for u in R.user_prints(fix)]
    presets = [P.default_preset()] + [P.from_profile(pr) for pr in profs] + \
        [P.normalise(p) for p in PRESET_ODD]
    cases = []
    for i, p in enumerate(presets):
        cases.append({"in": {"fn": "cards", "p": p},
                      "out": GC.norm({"subtitle": PL.subtitle(p), "lines": PL.lines_per_cell(p),
                                      "words": PL.cells_words(p), "info": PL.info(p),
                                      "thumb": PL.thumb_svg(p), "thumb7": PL.thumb_svg(p, 7)})})
    base = [(None, {}), (profs[-1], {})]
    for s, n in NODE_SETTINGS:
        from bam_cad_core import aruco_slabs as SL  # noqa: E402
        nn = dict({"marker_id": 0, "size": 0.0, "square": 0.0}, **SL.default_numbers(
            s.get("mode") if s.get("mode") in ("both", "black", "white") else "both"))
        nn.update(SL.pin_defaults())
        nn.update(n)
        for prof, _x in base:
            got = PL.preset_of_node(dict(s), dict(nn), prof)
            cases.append({"in": {"fn": "preset_of_node", "s": s, "n": nn, "profile": prof},
                          "out": GC.norm(got)})
    for a in presets[:4]:
        for b in presets[:4]:
            cases.append({"in": {"fn": "same_print", "a": a, "b": b}, "out": PL.same_print(a, b)})
    nodes = [(f"k{i}", PL.preset_of_node(dict(s), dict(n), None)) for i, (s, n) in
             enumerate(NODE_SETTINGS)]
    cat = [(p["name"], p, "builtin") for p in presets[:3]]
    cases.append({"in": {"fn": "group_nodes", "nodes": nodes, "catalog": cat},
                  "out": GC.norm(PL.group_nodes(nodes, cat))})
    cases.append({"in": {"fn": "edit_schema"}, "out": GC.norm(PL.edit_schema())})
    write("preset_library", "ArucoMarkers/aruco_preset_library.py",
          ["ArucoMarkers/aruco_preset_library.py", "ArucoMarkers/aruco_presets.py",
           "ArucoMarkers/aruco_prusa.py", "ArucoMarkers/aruco_core.py",
           "CADExporter/bam_cad_core/aruco_slabs.py", "CADExporter/bam_cad_core/aruco_chamfer.py"],
          {"profiles": "REF tests/fixtures/prusaslicer", "node_settings": "NODE_SETTINGS"}, cases)


def feature_namespace(ref_path, GC):
    """REF aruco_feature's pure functions, exec'd from the pinned blob with
    REF's own aruco_core (no adsk anywhere): the edit model on a fake node."""
    import types
    import aruco_core
    rel = "ArucoMarkers/aruco_feature.py"
    names = ["SPEC_VERSION", "MODES", "OPS", "HEIGHT_PARAMS", "PIN_PARAMS", "PARAMS",
             "LEGACY_PARAMS", "INFO_NOTES", "INFO_IN", "TARGET_KEYS", "JO_AFTER",
             "RESTRUCTURE_IN_PLACE", "M", "A", "SL", "CH", "OR", "AL", "TR", "is_info",
             "default_settings", "size_is_auto", "has_frame_sketch", "trim_setting", "normalise",
             "default_numbers", "effective_op", "resolve_follow", "plan_of", "structure",
             "rebuild_reason", "node_structure", "cells_of", "_param", "is_legacy", "black_follows",
             "follow_expression", "_norm_expr", "settings_of", "numbers_of", "settle",
             "keep_black_step", "_merged", "structural_change", "edit_kind", "_settings_key",
             "_edit_changes", "_trim_not_in_place", "params_for"]
    ns = {"json": json, "math": __import__("math"), "aruco_core": aruco_core,
          "aruco_tags": types.SimpleNamespace(frame_sketch_of=lambda cf: cf._frame_sketch)}
    exec(compile(extract(ref_path, rel, names), rel, "exec"), ns)

    class FeatureView:                      # REF's `aruco_feature` module, as F() sees it
        def __getattr__(self, k):
            return ns[k]

    rrel = "ArucoMarkers/aruco_restructure.py"
    rns = {"F": lambda: FeatureView()}
    exec(compile(extract(ref_path, rrel, ["ROLE_ORDER", "has_combine", "restructure_plan",
                                          "new_parts", "needed_params", "refusal", "what_goes"]),
                 rrel, "exec"), rns)

    def node_roles(cf, s):                  # the one Fusion read refusal() does
        if cf._roles_error:
            raise ValueError(cf._roles_error)
        return {}
    rns["node_roles"] = node_roles
    stub = types.ModuleType("aruco_restructure")
    stub.__dict__.update(rns)
    sys.modules["aruco_restructure"] = stub   # edit_kind / _trim_not_in_place import it
    return ns


class _Param:
    def __init__(self, name, value_cm, expression):
        self.name, self.value, self.expression = name, value_cm, expression


class FakeNode:
    """A custom feature as aruco_feature reads it: the "spec" named value,
    parameters by id (cm; itemById RAISES for an unknown id, as in 2705), a
    frame sketch or not, its features matching its parts or not."""

    def __init__(self, stored, params_cm, key="k", follow=False, frame_sketch=True,
                 roles_error=None):
        spec = json.dumps(stored)
        self.customNamedValues = type("NV", (), {
            "isExistingValue": staticmethod(lambda k: k == "spec"),
            "value": staticmethod(lambda k: spec)})()
        names = {pid: f"aruco_{key}_{pid}" for pid in params_cm}
        ps = {}
        for pid, v in params_cm.items():
            expr = f"{round(v * 10.0, 6):g} mm"
            ps[pid] = _Param(names[pid], v, expr)
        if follow and "white_offset" in ps and "white_height" in ps and "black_offset" in ps:
            wo, wh = names["white_offset"], names["white_height"]
            ps["black_offset"].expression = f"max({wo}; {wo} + {wh})"

        def item(pid):
            if pid not in ps:
                raise RuntimeError(f"no parameter {pid}")
            return ps[pid]
        self.parameters = type("P", (), {"itemById": staticmethod(item)})()
        self._frame_sketch = object() if frame_sketch else None
        self._roles_error = roles_error


def settings_cases():
    """Stored shapes (every generation) x edits x layouts x parameter sets."""
    import itertools
    base = {"v": 2, "key": "k", "mode": "both", "op": "join", "layout": "single",
            "dictionary": "DICT_4X4_50", "quiet_modules": 1.0, "grow": False, "rotate_deg": 0,
            "legacy": False, "size_auto": True, "force": None, "flip": False, "pin": "none",
            "turn": 0, "corner_mark": "none", "black_follows": False, "source": "profile",
            "z_sign": 1, "x_sketch": None, "has_body": True, "host_xform": None}
    shapes = {
        "legacy_0810": dict({k: v for k, v in base.items() if k not in ("v",)}),
        "v2_jo1_no_origin_v": dict(base, parts=["tile", "pocket", "pattern"]),
        "v2_chamfer_checkbox": dict(base, parts=["tile", "pocket", "pattern"], chamfer=True, jo_v=1),
        "v2_old_frame": dict(base, parts=["tile", "pocket", "pattern"], frame="opencv", jo_v=2,
                             origin_v=2),
        "v2_now": dict(base, parts=["tile", "pocket", "pattern", "trim"], jo_v=2, origin_v=2,
                       cells={"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0},
                       trim={"rule": 1, "axes": "x", "margin_mm": 1.0, "force": False},
                       label={"on": True, "content": "id", "place": "white", "rule": 2}),
        "v2_label_rule1_square": dict(base, parts=["tile", "pocket", "pattern"], jo_v=2,
                                      label={"on": True, "scope": "square", "place": "black"}),
        "v2_black_new": dict(base, mode="black", op="join", has_body=False, parts=["pattern"],
                             jo_v=2, origin_v=2),
    }
    edits = [({}, {}), ({"mode": "black"}, {}), ({"op": "new"}, {}), ({"turn": 90}, {}),
             ({"layout": "grid", "cols": 3, "rows": 1}, {}), ({"pin": "round"}, {}),
             ({}, {"white_height": 1.0}), ({}, {"black_offset": 1.0}), ({}, {"size": 25.0}),
             ({"black_follows": True}, {}), ({"trim": {"rule": 1, "axes": "both"}}, {}),
             ({"jo_v": 2}, {}), ({"label": {"on": True, "content": "id_name"}}, {}),
             ({"mode": "white", "op": "new"}, {"white_height": -0.6}),
             ({"corner_mark": "triangle"}, {}), ({"mode": "auto"}, {})]
    full = {"marker_id": 3.0, "size": 0.0, "square": 0.0, "white_offset": 0.0, "white_height": 0.2,
            "black_offset": 0.2, "black_height": -0.06, "pin_size": 0.3, "pin_length": 0.2,
            "pin_tol": 0.015}
    no_pins = {k: v for k, v in full.items() if not k.startswith("pin_")}
    legacy = {"marker_id": 3.0, "size": 2.8, "height": 0.2, "thickness": 0.06, "above": 0.0}
    out = []
    for (shape, stored), (s_new, n_new), layout, (pname, params), (fs, roles) in itertools.product(
            shapes.items(), edits, ("single", "charuco"), (("full", full), ("no_pins", no_pins)),
            ((True, None), (False, "1 base features for parts ['tile']"))):
        st = dict(stored, layout=layout)
        if layout == "charuco":
            st.update(cols=4, rows=3)
        if shape == "legacy_0810":
            pname, params = "legacy", legacy
        out.append({"shape": shape, "stored": st, "params_cm": params, "pset": pname,
                    "s_new": s_new, "n_new": n_new, "frame_sketch": fs, "roles_error": roles,
                    "follow": shape in ("v2_now", "v2_jo1_no_origin_v")})
    return out


def settings_golden(ref, write, pinned, GC):
    import ref_path
    for m in ("ArucoMarkers/aruco_feature.py", "ArucoMarkers/aruco_restructure.py",
              "ArucoMarkers/aruco_core.py"):
        pinned(m)
    F = feature_namespace(ref_path, GC)
    from bam_cad_core import aruco_slabs as SL, markers as Mk
    cases = []
    for jo_after in (True, False):
        F["JO_AFTER"] = jo_after
        cases.append({"in": {"fn": "default_settings", "jo_after": jo_after},
                      "out": GC.norm(F["default_settings"]())})
    F["JO_AFTER"] = True
    for shape in ({}, {"chamfer": True}, {"chamfer": False, "corner_mark": "triangle"},
                  {"corner_mark": "bogus"}, {"frame": "opencv", "turn": 90},
                  {"label": {"on": True, "scope": "square"}}, {"label": "junk"},
                  {"label": {"on": True, "rule": 1, "offset_x_mm": 2.0}}):
        for partial in (False, True):
            cases.append({"in": {"fn": "normalise", "s": shape, "partial": partial},
                          "out": GC.norm(F["normalise"](shape, partial=partial))})
    for s in ({"layout": "single"}, {"layout": "charuco"}):
        for n in ({}, {"size": 0}, {"size": 28.0}, {"size": 0, "square": 30.0}, {"size": "x"},
                  None):
            cases.append({"in": {"fn": "size_is_auto", "s": s, "n": n},
                          "out": F["size_is_auto"](s, n)})
    for mode in ("both", "black", "white", "auto"):
        cases.append({"in": {"fn": "default_numbers", "mode": mode},
                      "out": GC.norm(F["default_numbers"](mode))})
        for op in ("join", "new"):
            for has_body in (True, False):
                for trim in (None, {"rule": 1, "axes": "x"}, "junk"):
                    s = {"mode": mode if mode != "auto" else "both", "op": op, "has_body": has_body,
                         "pin": "triangle", "layout": "single", "parts": ["tile", "pocket"]}
                    if trim is not None:
                        s["trim"] = trim
                    n = F["default_numbers"](s["mode"])
                    cases.append({"in": {"fn": "structure", "s": s, "n": n},
                                  "out": GC.norm({"structure": F["structure"](s, n),
                                                  "node_structure": F["node_structure"](s),
                                                  "effective_op": F["effective_op"](s),
                                                  "params_for": F["params_for"](s),
                                                  "trim_setting": F["trim_setting"](s),
                                                  "follow": F["resolve_follow"](dict(s, black_follows=True), n)})})
    for mo in ("both", "black", "white", "x"):
        for m in ("both", "black", "white"):
            for followed in (False, True):
                n_old = dict(F["default_numbers"]("both"), black_offset=2.4)
                n = dict(F["default_numbers"](m), white_height=1.5)
                cases.append({"in": {"fn": "keep_black_step", "args": [mo, n_old, m, n, followed]},
                              "out": GC.norm(F["keep_black_step"](mo, n_old, m, n, followed))})
    for layout in ("single", "charuco"):
        for size in (0.0, 27.3):
            for trim in (None, {"rule": 1, "axes": "y"}, {"rule": 5}):
                s = dict(F["default_settings"](), layout=layout, mode="both", has_body=True, pin="round")
                if trim is not None:
                    s["trim"] = trim
                n = dict(F["default_numbers"]("both"), size=size, square=size * 1.3)
                spec = Mk.TagSpec(marker_length_m=0.0273, square_length_m=0.0355, layout=layout,
                                  cols=4 if layout == "charuco" else 1,
                                  rows=3 if layout == "charuco" else 1)
                plan = SL.plan("both", "join", True, n, "round")
                cases.append({"in": {"fn": "settle", "s": s, "n": n, "spec": spec.to_dict(),
                                     "plan": ["both", "join", True, "round"]},
                              "out": GC.norm(F["settle"](s, n, {"spec": spec, "plan": plan}))})
    for c in settings_cases():
        cf = FakeNode(c["stored"], c["params_cm"], follow=c["follow"], frame_sketch=c["frame_sketch"],
                      roles_error=c["roles_error"])
        out = {"black_follows": F["black_follows"](cf),
               "settings_of": F["settings_of"](cf), "numbers_of": F["numbers_of"](cf),
               "rebuild_reason": F["rebuild_reason"](cf)}
        try:
            out["merged"] = F["_merged"](cf, dict(c["s_new"]), dict(c["n_new"]))
            s_old, _n_old, s, n = out["merged"]
            out["structural"] = F["structural_change"](cf, s_old, s, n)
            out["edit_kind"] = F["edit_kind"](cf, dict(c["s_new"]), dict(c["n_new"]))
        except Exception as exc:                   # noqa: BLE001
            out["raises"] = [type(exc).__name__, str(exc)]
        cases.append({"in": dict(c, fn="node"), "out": GC.norm(out)})
    write("settings", "ArucoMarkers/aruco_feature.py",
          ["ArucoMarkers/aruco_feature.py", "ArucoMarkers/aruco_restructure.py",
           "ArucoMarkers/aruco_core.py", "CADExporter/bam_cad_core/aruco_slabs.py",
           "CADExporter/bam_cad_core/aruco_label.py", "CADExporter/bam_cad_core/aruco_chamfer.py"],
          {"how": "aruco_feature's pure functions and aruco_restructure's refusal exec'd from the "
                  "pinned blobs (both modules import adsk: never imported) on FakeNode, a custom "
                  "feature as plain data (spec named value, parameters in cm, frame sketch, roles)",
           "switches": {"JO_AFTER": True, "RESTRUCTURE_IN_PLACE": True}}, cases)


FORM_SPECS = [
    {"marker_id": 3, "marker_length_m": 0.028},
    {"marker_id": 3, "marker_length_m": 0.02856, "quiet_modules": 2.0},
    {"marker_id": 0, "marker_length_m": 0.03, "quiet_modules": 0.0},
    {"marker_id": 5, "marker_length_m": 0.014, "layout": "grid", "cols": 3, "rows": 1,
     "separation_m": 0.004},
    {"marker_id": 10, "marker_length_m": 0.009, "layout": "charuco", "cols": 4, "rows": 2,
     "square_length_m": 0.012, "dictionary": "DICT_5X5_100"},
    {"marker_id": 1, "marker_length_m": 0.0272, "dictionary": "DICT_6X6_250", "quiet_modules": 1.5},
]
FORM_CELLS = [None, {"rule": 1, "of": "marker", "mm": 0.5, "min_mm": 2.0},
              {"rule": 1, "of": "cell", "mm": 0.68, "min_mm": 2.0},
              {"rule": 1, "of": "cell", "mm": 0.45, "min_mm": 0.0}]
INFO_TEXTS = [
    "no marker fits here: the face is 8.0 x 6.0 mm", "ids 48..53 exceed DICT_4X4_50 (50 ids)",
    "cell minimum: a cell is 1.36 mm, under the preset's 2 mm", "module 1.00 mm < 1.2 mm",
    "nothing printable fits", "default raised to 10 mm", "clamped: 30 -> 20 mm",
    "only one grid marker fits: a single marker would", "ChArUco: 2 inner corners",
    "6 x 2 fit, but DICT_4X4_50 has 50 ids", "White height 0.05 mm is under 0.1 mm",
    "Black height snapped", "offset 60 mm is past the limit", "pin size 9 mm is too big",
    "pin length 0.2 mm", "the pin stops 0.2 mm short", "the white starts below the face",
    "the black floats 0.4 mm over the white", "the black goes through the tile",
    "a pinned tag prints upside down", "white border 4.67 mm = 6.86 × 0.68 mm: not whole lines",
    "Min cell 'x' is not a size", "the white tile is the area's box",
    "Body1 belongs to the external reference", "Auto size would build 25.0 mm",
    "saved as preset 'Mine'", "not saved: the name is taken", "Preset 'Default': a → b, c → d",
    "Imported 'Aruco 0.6': x → y", "This tag's own settings back", "Label too big",
    "Trim refused: the face is not a rectangle", "something else entirely"]
INFO_COLOURS = ["#c00", "#c60", "#06c", "#888", "", "#d45500", "#0a66c2", "#cc0000"]


def form_golden(ref, write, pinned, GC):
    import types
    import ref_path
    import aruco_core
    from bam_cad_core import aruco_label as L, aruco_trim as TRMm, markers as Mk
    rel = "ArucoMarkers/aruco_extrude_cmd.py"
    ui = "ArucoMarkers/aruco_extrude_ui.py"
    kit = "ArucoMarkers/bam_fusion_ui.py"
    F = feature_namespace(ref_path, GC)

    class FeatureView:
        def __getattr__(self, k):
            return F[k]
    import aruco_presets
    X_state = types.SimpleNamespace(profile=None, mode="both")
    ns = {"json": json, "aruco_core": aruco_core, "aruco_feature": FeatureView(),
          "aruco_presets": aruco_presets, "_X": X_state}
    exec(compile(extract(ref_path, rel, [
        "LAYOUT_LABELS", "MODE_LABELS", "OP_LABELS", "PIN_LABELS", "LABEL_CONTENT", "LABEL_PLACE",
        "LABEL_ROW", "LABEL_SIDE", "LABEL_SCOPE", "CELLS", "SL", "OR", "CH", "AL", "_num", "_dd",
        "defaults", "_base_from", "_cell_line_mm", "_choice_of_cells", "_same_value", "cells_line",
        "layer_lines", "_cell_warnings", "label_defaults", "_same_label_settings", "WARN_HTML",
        "LEVEL_HTML", "INFO_ROWS", "INFO_CHARS", "_html", "label_entries", "label_lines",
        "info_rows", "resolve_mode", "_origin_line", "same_build", "ROLE_WORDS", "_mark_line",
        "_pin_line", "_mm_text", "size_line", "TRIM_LABELS", "TRIM_MISSING", "TRM", "trim_values",
        "trim_issues", "trim_lines"]), rel, "exec"), ns)
    kns = {"re": __import__("re")}
    from dataclasses import dataclass as _dc
    kns["dataclass"] = _dc
    exec(compile("from typing import Dict, List\n" + extract(ref_path, kit, [
        "LEVELS", "RANK", "PALETTES", "COLOUR", "set_theme", "SIGN", "MSG_SUFFIX", "html", "Issue",
        "worst", "head_of", "summary_text", "rows_for"]), kit, "exec"), kns)
    K = types.SimpleNamespace(**{k: v for k, v in kns.items() if not k.startswith("__")})
    uns = {"re": __import__("re"), "_h": __import__("html"), "K": K, "aruco_core": aruco_core,
           "X": lambda: types.SimpleNamespace(_X=X_state)}
    exec(compile(extract(ref_path, ui, ["round_line", "json_key", "FALLBACK", "ROUTES", "_plain",
                                        "PRESET_EVENTS", "_short", "_level_of", "classify",
                                        "_short_note", "label_issues"]), ui, "exec"), uns)

    class Inp:                                    # a dialog row, as REF reads it
        def __init__(self, value=None, name=None, visible=True, valid=True):
            self.value = value
            self.selectedItem = types.SimpleNamespace(name=name) if name else None
            self.isVisible = visible
            self.isValidExpression = valid

    def inputs(**rows):
        return types.SimpleNamespace(itemById=lambda cid: rows.get(cid))

    cases = [{"in": {"fn": "defaults"}, "out": GC.norm({"defaults": ns["defaults"](),
                                                        "label": ns["label_defaults"]()})}]
    for vals in ({}, {"white_offset": 0.1, "white_height": 0.15, "black_height": 0.05},
                 {"black_height": -0.04, "white_height": "x"}, {"white_height": True}):
        cases.append({"in": {"fn": "_base_from", "vals": vals}, "out": GC.norm(ns["_base_from"](vals))})
    for sd in FORM_SPECS:
        spec = Mk.TagSpec.from_dict(dict(sd), lambda m: None, "form")
        for ci, cells in enumerate(FORM_CELLS):
            s = {"cells": cells} if cells else {}
            for prof in (None, {"line_mm": 0.68, "layer_mm": 0.32, "first_layer_mm": 0.2},
                         {"line_mm": 0.45}):
                X_state.profile = prof
                cases.append({"in": {"fn": "cells", "spec": sd, "s": s, "profile": prof},
                              "out": GC.norm({"cells_line": ns["cells_line"](spec, s),
                                              "warn": ns["_cell_warnings"](spec, s)})})
        for turn in (0, 90, 180, 270):
            cases.append({"in": {"fn": "_origin_line", "spec": sd, "turn": turn},
                          "out": ns["_origin_line"](spec, turn)})
        cases.append({"in": {"fn": "size_line", "spec": sd}, "out": ns["size_line"](spec)})
        for choice in ("marker", "line", "custom"):
            for line, step, typed in ((0.68, 0.5, None), (0.45, 0.5, 28.0), (None, 0.25, 27.3)):
                cases.append({"in": {"fn": "round_line", "spec": sd, "args": [choice, line, step, typed]},
                              "out": uns["round_line"](spec, choice, line, step, typed)})
    for v in (28.0, 27.25, 37.333, 0.0, 5.0, 12.345):
        cases.append({"in": {"fn": "_mm_text", "v": v}, "out": ns["_mm_text"](v)})
    for mode in ("both", "black", "white"):
        for bh in (-0.6, 0.6, -0.5):
            for prof in (None, {"layer_mm": 0.32, "first_layer_mm": 0.2}, {"layer_mm": 0.2}):
                X_state.profile = prof
                n = {"black_height": bh}
                cases.append({"in": {"fn": "layer_lines", "s": {"mode": mode}, "n": n, "profile": prof},
                              "out": ns["layer_lines"]({"mode": mode}, n)})
    for c in ({"of": "marker"}, {"of": "cell", "step": "line"}, {"of": "cell", "step": "mm"}):
        cases.append({"in": {"fn": "_choice_of_cells", "c": c}, "out": ns["_choice_of_cells"](c)})
    for a, b in ((True, 1), (1, 1.0), (0.1 + 0.2, 0.3), ("a", "a"), (None, 0)):
        cases.append({"in": {"fn": "_same_value", "a": a, "b": b}, "out": ns["_same_value"](a, b)})
    for a, b in (({"on": True, "rule": 1}, {"on": True, "rule": 2}),
                 ({"cap_mm": 3.0}, {"cap_mm": 3.0000001}), ({"cap_mm": 3.0}, {"cap_mm": 3.1}),
                 ({"x": "a"}, {"x": "b"}), ({"cap_mm": "x"}, {"cap_mm": 1.0})):
        cases.append({"in": {"fn": "_same_label_settings", "a": a, "b": b},
                      "out": ns["_same_label_settings"](a, b)})
    lines = [[f"<span style='color:{c}'>{t}</span>" if c else t for t in INFO_TEXTS]
             for c in INFO_COLOURS]
    for ls in lines:
        cases.append({"in": {"fn": "classify", "lines": ls},
                      "out": GC.norm([[i.anchor, i.level, i.text, i.note, i.detail]
                                      for i in uns["classify"](ls, "black_offset")])})
        cases.append({"in": {"fn": "info_rows", "lines": ls}, "out": ns["info_rows"](ls)})
    for t in INFO_TEXTS + ["Preset 'Default': a → b, +3 more"]:
        cases.append({"in": {"fn": "_short_note", "t": t}, "out": uns["_short_note"](t)})
        cases.append({"in": {"fn": "_short", "t": t * 6}, "out": uns["_short"](t * 6)})
    issues = [kns["Issue"]("size", "block", "nothing fits here"), kns["Issue"]("quiet", "warn", "x y"),
              kns["Issue"]("", "error", "a general thing: with words"), kns["Issue"]("pin", "info", "i"),
              kns["Issue"]("label_place", "warn", "Label too big (by 2 mm)", note=True)]
    for k in range(len(issues) + 1):
        sub = issues[k:] + issues[:k][:1]
        cases.append({"in": {"fn": "summary", "issues": [[i.anchor, i.level, i.text, i.note, i.detail]
                                                          for i in sub]},
                      "out": GC.norm({"summary": kns["summary_text"](sub, {"size": "Size", "quiet": "Quiet zone"},
                                                                     {"size": "Marker"}, "✓ ok"),
                                      "worst": kns["worst"](sub),
                                      "heads": [kns["head_of"](i.text) for i in sub]})})
    # labels: the info's words and the issue they make
    for i, case in enumerate(GC.label_cases(L)[:60]):
        lab = GC_label(case, L, Mk)
        X_state.mode = case["mode"]
        on = inputs(label_on=Inp(True))
        cases.append({"in": {"fn": "label", "case": case},
                      "out": GC.norm({"entries": ns["label_entries"](lab, case["mode"]),
                                      "issues": [[x.anchor, x.level, x.text]
                                                 for x in uns["label_issues"](on, {"label": lab})]})})
    # Trim excess in the dialog
    for axes_name in ("Off", "Width (the tag's X)", "Both"):
        for margin, valid, force in ((0.15, True, False), (0.0, False, False), (0.2, True, True)):
            inp = inputs(trim=Inp(name=axes_name), trim_margin=Inp(margin, valid=valid),
                         trim_force=Inp(force))
            body = (-25.0, -20.0, 25.0, 20.0)
            for refuse in (False, True):
                face = [[(-25, -20), (25, -20), (25, 20), (-25, 20)]] if not refuse else \
                    [[(-25, -20), (25, -20), (25, 0), (0, 0), (0, 20), (-25, 20)]]
                tp = TRMm.plan_trim("x", (-10.0, -10.0, 10.0, 10.0), body, face,
                                    volumes=(50 * 40 * 5.0, 30 * 40 * 5.0), z=(-5.0, 0.0),
                                    force=force)
                ev = {"trim": tp}
                s = {"trim": ns["trim_values"](inp), "has_body": True}
                cases.append({"in": {"fn": "trim", "axes": axes_name, "margin_cm": margin,
                                     "valid": valid, "force": force, "refuse": refuse},
                              "out": GC.norm({"values": ns["trim_values"](inp),
                                              "issues": ns["trim_issues"](inp, ev),
                                              "lines": ns["trim_lines"](inp, s, ev, "Plate")})})
    write("form", rel, [rel, ui, kit, "ArucoMarkers/aruco_feature.py", "ArucoMarkers/aruco_presets.py",
                        "ArucoMarkers/aruco_core.py", "CADExporter/bam_cad_core/aruco_label.py"],
          {"how": "the dialog's pure functions exec'd from the pinned blobs (the dialog modules import "
                  "adsk: never imported); the dialog state they read (_X.profile, _X.mode) and the "
                  "Trim / Label rows as plain stand-ins"}, cases)


def GC_label(case, L, Mk):
    """The Label a golden_cases.label_cases case plans (no corner mark)."""
    spec = Mk.TagSpec.from_dict(dict(case["spec"]), lambda m: None, "golden")
    import golden_cases as GC
    region = GC.REGIONS.get(case["region"]) if case["region"] else None
    return L.plan_label(spec, dict(case["settings"]), mode=case["mode"],
                        op=case["op"] if case["mode"] == "both" else None, name=case["name"],
                        key=case["key"], region=region, grow=case["grow"])


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
