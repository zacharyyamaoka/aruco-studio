"""The port is a copy: every function said to be REF's verbatim IS, line for line.

For each core module, every top-level def / class / constant it shares with
its REF file (at ref_path.REF_HEAD, the add-in the core was last brought
up to: N-1, 2026-10-17) has the same source text, except the
ones listed as ADAPTED (they took a Fusion object or the dialog's state, and
their docstrings say what changed). Skipped when REF_HEAD is not on this
machine, and said so (ref_path.head_missing_note; tools/check.py repeats it).
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "aruco_studio" / "core"
sys.path.insert(0, str(ROOT / "tools"))
import ref_path  # noqa: E402

needs_ref = pytest.mark.skipif(not ref_path.head_reachable(),
                               reason=ref_path.head_missing_note())

# Names that tonight's versioned rules and options changed in place (2026-10-20
# night). name -> (why, the replay test that pins the OLD path). The old path
# is what REF computes, so these still answer as REF did; the text differs.
_CELLS = ("cells rule 2 (autosize.ROUND_RULE) and rule 3 (DOTS_RULE, SizeStep barrier 11): "
          "the rule rides the cells tuple; no rule / rule 1 is REF's path to the bit")
_CELLS_REPLAY = "tests/core/test_ref_cells_legacy.py"      # 511 sizings, 'cells' absent / marker 0.5
_CELLS_REPLAY_WEB = "tests/web/test_web_legacy_presets.py"  # 144 plan+svg == 03594f9, cell_step_mm 0.042333
_SCALE = ("SheetRequest.scale_bar (barrier 12): hide | first | every; "
          "every / absent draws what REF drew, byte for byte")
_SCALE_REPLAY = "tests/core/test_sheet_scalebar.py"         # every / absent == 65164e4 digests
ADAPTED_NIGHT = {
    "autosize": {
        **{n: (_CELLS, _CELLS_REPLAY) for n in (
            "_kw", "_layout", "_region_clamp", "_search_frame", "_typed", "candidates",
            "candidates_on_loops", "clamp_to_fit", "default_layout", "face_default",
            "fit_on_loops", "layout_for_size")},
        "cells_of": (_CELLS + "; cell_step_mm 0.042333 reads as rule 1", _CELLS_REPLAY_WEB),
    },
    "markers": {n: (_SCALE, _SCALE_REPLAY) for n in ("sheet_check", "sheet_layout", "sidecar_files")},
    "sheet": {n: (_SCALE, _SCALE_REPLAY) for n in (
        "SheetLayout", "_page_content", "layout_sheet", "layout_summary")},
}

B = "CADExporter/bam_cad_core/"
A = "ArucoMarkers/"
# core module -> [(REF file, names adapted on purpose)]
PORTS = {
    "dictionary": [(B + "aruco_dict.py", set()), (B + "fiducials.py", set())],
    "board": [(B + "aruco_board.py", set())],
    "origin": [(B + "aruco_origin.py", set())],
    "slabs": [(B + "aruco_slabs.py", set())],
    "chamfer": [(B + "aruco_chamfer.py", set())],
    "autosize": [(B + "aruco_autosize.py", {"_rect_inside",    # M6a: a skip, same answers
                                            "_Grid"})],        # Merge 1: snapping on a dot grid (_snap)
    # M6a: label rule 3 (a ChArUco label by hand in any black square)
    "label": [(B + "aruco_label.py", {"RULES", "_offset_label", "label_violations",
                                      "check_label", "describe",
                                      # audit 2026-10-17: rule 4 (a ChArUco label on auto stays in a black square)
                                      "plan_label", "_describe",
                                      # 2026-10-17: rule 5 (a label cut from the black strokes
                                      # >= 1.1 cell lines; Label carries line_mm)
                                      "Label", "LabelSettings", "from_dict", "relabel"})],
    "trim": [(B + "aruco_trim.py", set())],
    "numbering": [(B + "aruco_numbering.py", set())],
    "markers": [(B + "markers.py", set())],
    "sheet": [(B + "print_sheet.py", {"PrintItem", "SheetSettings"})],    # M6a: new fields
    "beds": [(B + "print_beds.py", set())],
    "faces": [(A + "aruco_autosize_gallery.py", set())],
    "settings": [(A + "aruco_feature.py", {"M", "A", "SL", "CH", "OR", "AL", "TR"})],
    "edits": [(A + "aruco_feature.py", {"settle", "_merged", "structural_change", "edit_kind",
                                        "_edit_changes", "rebuild_reason", "_trim_not_in_place",
                                        "_settings_key"}),
              (A + "aruco_extrude_sync.py", {"verdict"})],
    "restructure": [(A + "aruco_restructure.py", {"F", "refusal", "needed_params"})],
    "geometry": [(A + "aruco_tags.py", {"_dot", "_unit"}),     # same floats: see its docstring
                 (A + "aruco_feature.py", {"_dot", "_unit", "_cross", "_xf_point", "_xf_vector",
                                           "_rotz", "_loops_mm"})],
    "presets": [(A + "aruco_presets.py", {"_SL", "_AL", "_markers", "load", "save", "_empty",
                                          "normalise", "line_mm",          # M6a: the machine's keys
                                          "_broken", "builtins", "catalog", "save_as", "update",
                                          "delete", "set_last", "import_profile",
                                          "_builtin_names"}),
                (A + "aruco_preset_library.py", {"SCHEMA", "MAX_RECENT", "FILE_NAME"})],
    "prusa": [(A + "aruco_prusa.py", {"read_ini", "read_bundle", "user_prints", "resolve",
                                      "profile", "aruco_profiles"})],
    "form": [(A + "aruco_extrude_cmd.py", {"cells_line", "layer_lines", "trim_values",
                                           "trim_issues", "trim_lines"}),
             (A + "aruco_extrude_ui.py", {"trim_issues"})],
    "validate": [(A + "bam_fusion_ui.py", {"_plain"}),      # aruco_extrude_ui's _plain is kept
                 (A + "aruco_extrude_ui.py", {"label_issues", "trim_issues", "X"})],
    "marker_table": [(A + "aruco_marker_table.py", {"spec_info", "T", "MarkerRow"}),   # M6a: made_by
                     (A + "aruco_ids_cmd.py", set()), (A + "aruco_ids_preview.py", {"T"})],
    "export_rows": [(A + "aruco_commands.py", {"T"}), (A + "aruco_export.py", set()),
                    (A + "aruco_export_preview.py", set())],
    "ids_design": [(A + "aruco_ids_feature.py", {"M", "N", "node_state", "auto_verdict"})],
}


RENAME = {"aruco_dict": "dictionary", "aruco_board": "board", "aruco_origin": "origin",
          "aruco_slabs": "slabs", "aruco_chamfer": "chamfer", "aruco_autosize": "autosize",
          "aruco_label": "label", "aruco_trim": "trim", "aruco_numbering": "numbering",
          "print_sheet": "sheet", "print_beds": "beds", "fiducials": "dictionary"}


def renamed(src):
    """REF's text with the core port's ONE change: package-relative imports
    renamed (`from . import aruco_board` -> `from . import board as aruco_board`)."""
    import re

    def one(m):
        ind, names, comment = m.group(1), m.group(2), m.group(3) or ""
        out = []
        for part in names.split(","):
            part = part.strip()
            bits = part.split(" as ")
            src_, alias = bits[0].strip(), (bits[1].strip() if len(bits) > 1 else None)
            new = RENAME.get(src_, src_)
            out.append(part if new == src_ else f"{new} as {alias or src_}")
        return f"{ind}from . import {', '.join(out)}{comment}"
    src = re.sub(r"^(\s*)from \. import (.+?)(\s*#.*)?$", one, src, flags=re.M)
    return re.sub(r"^(\s*)from \.(\w+) import",
                  lambda m: f"{m.group(1)}from .{RENAME.get(m.group(2), m.group(2))} import", src,
                  flags=re.M)


def defs(src):
    lines = src.split("\n")
    out = {}
    for node in ast.parse(src).body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.append(t.id)
                elif isinstance(t, ast.Tuple):
                    names += [e.id for e in t.elts if isinstance(e, ast.Name)]
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        for n in names:
            out[n] = "\n".join(lines[start - 1:node.end_lineno])
    return out


CASES = [(m, ref, skip) for m, refs in PORTS.items() for ref, skip in refs]


@needs_ref
@pytest.mark.parametrize("module,ref,adapted", CASES, ids=[f"{m}<-{Path(r).name}" for m, r, _ in CASES])
def test_shared_names_are_refs_text(module, ref, adapted):
    mine = defs((CORE / f"{module}.py").read_text(encoding="utf-8"))
    theirs = defs(renamed(ref_path.show(ref, ref_path.REF_HEAD).decode("utf-8")))
    adapted = set(adapted) | set(ADAPTED_NIGHT.get(module, {}))
    shared = sorted((set(mine) & set(theirs)) - adapted)
    assert shared, f"{module} shares nothing with {ref}"
    differ = [n for n in shared if mine[n] != theirs[n]]
    assert not differ, f"{module} differs from {ref} in: {differ}"


def test_every_night_adaptation_has_a_reason_and_a_replay():
    """A name may differ from REF only for a stated rule/option, and the test
    that pins the old path must exist and name the same rule's replay."""
    for module, names in ADAPTED_NIGHT.items():
        assert (CORE / f"{module}.py").exists(), module
        mine = defs((CORE / f"{module}.py").read_text(encoding="utf-8"))
        for name, (why, replay) in names.items():
            assert name in mine, (module, name)
            assert why.strip(), (module, name)
            assert (ROOT / replay).is_file(), (module, name, replay)


# print_beds' file I/O lives outside the core (audit C7): REF's text there
BEDS_IO = ROOT / "aruco_studio" / "server" / "beds_io.py"
# M8c: Send to PrusaSlicer's file half, new (not REF's): REF's twelve stay verbatim
BEDS_IO_M8C = {"chain_profile", "filament_for", "write_project", "single_instance_ok",
               "open_in_prusaslicer"}


@needs_ref
def test_beds_io_is_refs_text():
    """server/beds_io.py: each function is print_beds' own text, and the
    core's beds no longer holds any of them."""
    mine = defs(BEDS_IO.read_text(encoding="utf-8"))
    theirs = defs(renamed(ref_path.show(B + "print_beds.py", ref_path.REF_HEAD).decode("utf-8")))
    funcs = {n for n in mine if mine[n].lstrip().startswith("def ")} - BEDS_IO_M8C
    assert BEDS_IO_M8C <= set(mine) and not (BEDS_IO_M8C & set(theirs))
    assert len(funcs) == 12, sorted(funcs)
    assert funcs <= set(theirs), sorted(funcs - set(theirs))
    differ = [n for n in sorted(funcs) if mine[n] != theirs[n]]
    assert not differ, differ
    core = set(defs((CORE / "beds.py").read_text(encoding="utf-8")))
    assert not (funcs & core), sorted(funcs & core)


@needs_ref
def test_whole_core_copies_keep_every_ref_name():
    """A copied bam_cad_core module keeps every one of REF's top-level names
    (markers.py: but instance_fiducials, the CAD Exporter's URDF bridge;
    beds.py: but its file I/O, which is server/beds_io.py)."""
    not_ported = {"instance_fiducials"}
    beds_io = {n for n, t in defs(BEDS_IO.read_text(encoding="utf-8")).items()
               if t.lstrip().startswith("def ")}
    for module, refs in PORTS.items():
        ref = refs[0][0]
        if not ref.startswith(B) or ref.endswith("fiducials.py"):
            continue
        mine = set(defs((CORE / f"{module}.py").read_text(encoding="utf-8")))
        if module == "beds":
            mine |= beds_io
        theirs = set(defs(ref_path.show(ref, ref_path.REF_HEAD).decode("utf-8")))
        missing = theirs - mine - (not_ported if module == "markers" else set())
        assert not missing, (module, sorted(missing))
