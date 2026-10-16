"""Copy REF's Fusion-free test suites into tests/core/ref_suites/, pointed at
aruco_studio.core instead of bam_cad_core. Run once; the copies are committed.

    .venv/Scripts/python tools/port_ref_suites.py

Every copy is REF's file at the pinned commit with ONLY these changes:

| Change | Why |
|---|---|
| `from bam_cad_core import aruco_x as X` -> `from aruco_studio.core import x as X` | the new core |
| `sys.path.insert(... "CADExporter" / "tools" / "ArucoMarkers")` -> a no-op | nothing is imported from REF |
| `HERE / "fixtures" / "<golden>.json"` -> the copy under goldens/ref/ (its "golden" field) | goldens live in ROOT |
| the golden makers' pure halves -> `ref_make_*.py` copies (no `main`, no stand-in adsk) | the suites call `G.run(...)` / `G.shape(...)` |
| per-suite patches listed in PATCHES below (each an exact string, asserted present) | the few lines that loaded the add-in |

tests/core/test_ref_*.py runs each copy in its own process and compares its
checks, section by section, with REF's own run (tests/ref_sections.json).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ref_path  # noqa: E402

OUT = ref_path.ROOT / "tests" / "core" / "ref_suites"

MOD = {"aruco_dict": "dictionary", "aruco_board": "board", "aruco_origin": "origin",
       "aruco_slabs": "slabs", "aruco_chamfer": "chamfer", "aruco_autosize": "autosize",
       "aruco_label": "label", "aruco_trim": "trim", "aruco_numbering": "numbering",
       "markers": "markers", "print_sheet": "sheet", "print_beds": "beds",
       "fiducials": "dictionary"}

SUITES = ["test_aruco_autosize", "test_aruco_board", "test_aruco_cells", "test_aruco_cells_legacy",
          "test_aruco_chamfer", "test_aruco_label", "test_aruco_label_position",
          "test_aruco_label_preview", "test_aruco_label_rule1", "test_aruco_numbering",
          "test_aruco_ids_stability", "test_aruco_output", "test_aruco_slabs", "test_aruco_trim",
          "test_aruco_trim_legacy", "test_aruco_presets", "test_aruco_frame"]

GOLD = 'Path(__file__).resolve().parents[3] / "goldens" / "ref"'
PRELUDE = ("# REF: tests/{name}.py at {commit} (cad-exporter), ported by tools/port_ref_suites.py:\n"
           "# REF's checks verbatim, run against aruco_studio.core. Do not edit by hand.\n")


def golden_loader(var, fname):
    return f'{var} = json.loads(({GOLD} / "{fname}").read_text(encoding="utf-8"))["golden"]'


PATCHES = {
    "test_aruco_autosize": [
        ('    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ArucoMarkers"))\n'
         '    import aruco_autosize_gallery as G\n',
         '    from aruco_studio.core import faces as G   # REF: ArucoMarkers/aruco_autosize_gallery\n'),
    ],
    "test_aruco_board": [
        ("from test_aruco_output import overlaps, pdf_pages, read_png  # noqa: E402",
         "from ref_aruco_output import overlaps, pdf_pages, read_png  # noqa: E402"),
    ],
    "test_aruco_label_position": [
        ("import aruco_label_fixtures as FX  # noqa: E402",
         "import ref_aruco_label_fixtures as FX  # noqa: E402"),
    ],
    "test_aruco_label_rule1": [
        ("import make_label_rule1_golden as G  # noqa: E402",
         "import ref_make_label_rule1_golden as G  # noqa: E402"),
        ('data = json.loads((HERE / "fixtures" / "aruco_label_rule1_golden.json").read_text(\n'
         '    encoding="utf-8"))',
         golden_loader("data", "aruco_label_rule1_golden.json")),
    ],
    "test_aruco_cells_legacy": [
        ("import make_cells_legacy_golden as G  # noqa: E402",
         "import ref_make_cells_legacy_golden as G  # noqa: E402"),
        ('data = json.loads((HERE / "fixtures" / "aruco_cells_legacy_golden.json").read_text(\n'
         '    encoding="utf-8"))',
         golden_loader("data", "aruco_cells_legacy_golden.json")),
        # the 12 evaluate() cases need REF's aruco_feature.evaluate(): M2's plan_tag
        ('got_eval = G.run_eval(ROOT)\nfor want, got in zip(data["evaluate"], got_eval):',
         'print("  skip  parked for M2: evaluate() is plan/plan.py\'s plan_tag "\n'
         '      f"({len(data[\'evaluate\'])} cases, tests/plan/test_golden_evaluate.py)")\n'
         'for want, got in []:'),
    ],
    "test_aruco_trim_legacy": [
        ("import make_trim_legacy_golden as G  # noqa: E402",
         "import ref_make_trim_legacy_golden as G  # noqa: E402\n"
         "from aruco_studio.core import settings as F, slabs as SL, edits as _E  # noqa: E402\n"
         "F._trim_not_in_place = _E.trim_not_in_place   # REF aruco_feature._trim_not_in_place"),
        ('gold = json.loads((HERE / "fixtures" / "aruco_trim_legacy_golden.json").read_text(\n'
         '    encoding="utf-8"))\nF, SL, Profile = G.load(ROOT)',
         golden_loader("gold", "aruco_trim_legacy_golden.json")),
        # sections 2-4 run REF's aruco_feature.evaluate() (26 cases, junk trims, JO_AFTER):
        # that is M2's plan_tag, so they are parked; their headers stay for the trace
        (lambda src: park_between(
            src,
            'print(f"== {len(gold[\'evaluate\'])} tags evaluated with no \'trim\': identical")',
            'print(f"== {len(gold[\'plans\'])} aruco_slabs plans: identical, and trim=False is the same")',
            ['print(f"== {len(gold[\'evaluate\'])} tags evaluated with no \'trim\': identical")',
             'print("== the same tags with a \'trim\' that reads as off: identical")',
             'print("== the shipped defaults (4babc4b: the Joint Origin after the node): '
             'no \'trim\' = junk \'trim\'")'])),
    ],
    "test_aruco_presets": [
        # the fixture lives in goldens/prusaslicer (byte for byte)
        ('FIX = str(HERE / "fixtures" / "prusaslicer")',
         'FIX = str(Path(__file__).resolve().parents[3] / "goldens" / "prusaslicer")'),
        # REF's file API (path= / prusa_dir=) over core.presets / core.prusa: ref_store_shim
        ("import aruco_core  # noqa: E402\nimport aruco_presets as P  # noqa: E402\n"
         "import aruco_prusa as R  # noqa: E402",
         "from ref_store_shim import P, R  # noqa: E402   REF: aruco_presets, aruco_prusa (files)"),
        ('S = aruco_core.module("aruco_slabs")', "from aruco_studio.core import slabs as S"),
    ],
    "test_aruco_frame": [
        ('    OR = importlib.import_module("bam_cad_core.aruco_origin")',
         '    OR = importlib.import_module("aruco_studio.core.origin")'),
    ],
}


def park_between(src, start, end, headers):
    """Replace src[start:end] by its section headers, each followed by a
    'skip  parked for M2' line (evaluate() is plan_tag, M2)."""
    a, b = src.index(start), src.index(end)
    skip = ('print("  skip  parked for M2: REF ran aruco_feature.evaluate() here '
            '(plan/plan.py plan_tag, tests/plan/test_golden_evaluate.py)")\n')
    body = "".join(h + "\n" + skip for h in headers)
    # a later section still uses the junk list defined in the parked part: keep it
    gone = src[a:b]
    keep = ""
    if "\nJUNK = [" in gone:
        j = gone.index("\nJUNK = [") + 1
        keep = gone[j:gone.index("]\n", j) + 2]
    return src[:a] + body + keep + "\n" + src[b:]


def fix_imports(src):
    def from_pkg(m):
        names = []
        for part in m.group(2).split(","):
            part = part.strip()
            bits = part.split(" as ")
            src_name = bits[0].strip()
            alias = bits[1].strip() if len(bits) > 1 else src_name
            new = MOD.get(src_name, src_name)
            names.append(new if new == alias else f"{new} as {alias}")
        return f"{m.group(1)}from aruco_studio.core import {', '.join(names)}"
    src = re.sub(r"^(\s*)from bam_cad_core import ([^\n#(]+?)(?=\s*(#|$))", from_pkg, src,
                 flags=re.M)
    src = re.sub(r"^(\s*)from bam_cad_core\.(\w+) import",
                 lambda m: f"{m.group(1)}from aruco_studio.core.{MOD.get(m.group(2), m.group(2))} import",
                 src, flags=re.M)
    return src


def no_ref_paths(src):
    out = []
    for line in src.split("\n"):
        if re.match(r"^\s*sys\.path\.insert\(0, .*(\"CADExporter\"|\"tools\"|\"ArucoMarkers\")\)\)?\s*$",
                    line):
            ind = line[:len(line) - len(line.lstrip())]
            out.append(f"{ind}pass  # REF put its own tree on sys.path here (ported: not needed)")
        else:
            out.append(line)
    src = "\n".join(out)
    # test_aruco_ids_stability: BAM_CORE_ROOT or REF's CADExporter (two lines)
    src = src.replace('sys.path.insert(0, os.environ.get("BAM_CORE_ROOT")\n'
                      '                or str(Path(__file__).resolve().parents[1] / "CADExporter"))',
                      'pass  # REF: BAM_CORE_ROOT or its CADExporter on sys.path (ported: not needed)')
    return src


def port_suite(name):
    src = ref_path.show(f"tests/{name}.py").decode("utf-8")
    src = fix_imports(src)
    for patch in PATCHES.get(name, []):
        if callable(patch):
            src = patch(src)
            continue
        old, new = patch
        if old not in src:
            raise SystemExit(f"{name}: patch target not found:\n{old}")
        src = src.replace(old, new)
    src = no_ref_paths(src)
    # test_aruco_frame: only test_origin_math runs (tests/ref_sections.json "entry"); its
    # URDF half keeps REF's lazy CAD Exporter imports, never executed here
    if name != "test_aruco_frame":
        assert "bam_cad_core" not in "\n".join(l for l in src.split("\n")
                                                if l.lstrip().startswith(("from", "import"))), name
    head = PRELUDE.format(name=name, commit=ref_path.REF_COMMIT)
    (OUT / f"ref_{name[5:]}.py").write_text(head + src, encoding="utf-8", newline="\n")


def until(src, marker):
    i = src.index(marker)
    return src[:i]


def port_helpers():
    # tests/aruco_label_fixtures.py: the GIM43 disc from goldens/ref
    src = ref_path.show("tests/aruco_label_fixtures.py").decode("utf-8")
    src = src.replace('GIM43 = HERE / "fixtures" / "aruco_label_gim43_disc.json"',
                      'GIM43 = HERE.parents[2] / "goldens" / "ref" / "aruco_label_gim43_disc.json"')
    src = src.replace('d = json.loads(Path(path).read_text(encoding="utf-8"))',
                      'd = json.loads(Path(path).read_text(encoding="utf-8"))["golden"]')
    src = fix_imports(src)
    (OUT / "ref_aruco_label_fixtures.py").write_text(
        PRELUDE.format(name="aruco_label_fixtures", commit=ref_path.REF_COMMIT) + src,
        encoding="utf-8", newline="\n")
    # the golden makers: their pure halves only (cases and how a case is run)
    for tool, cut in (("make_label_rule1_golden", "def main("),
                      ("make_cells_legacy_golden", "def stand_in_adsk("),
                      ("make_trim_legacy_golden", "def stand_in_adsk(")):
        src = ref_path.show(f"tools/{tool}.py").decode("utf-8")
        body = until(src, cut)
        if tool == "make_trim_legacy_golden":
            rest = src[src.index("def _r(v, nd=9):"):src.index("def load(root):")]
            # run_eval needs aruco_feature on a stand-in adsk (M2); everything else is pure
            body += rest
        body = body.replace('OUT = ROOT / "tests" / "fixtures"', '# OUT (REF only) = ROOT / "tests" / "fixtures"')
        head = (f"# REF: tools/{tool}.py at {ref_path.REF_COMMIT}: its cases and how a case is run,\n"
                "# for the ported suite. Never writes a golden (no main, no stand-in adsk).\n")
        (OUT / f"ref_{tool}.py").write_text(head + fix_imports(body), encoding="utf-8", newline="\n")


def port_mutations():
    """REF's mutation tables (tools/mutate_aruco_ids.py, mutate_aruco_label.py),
    the rows that break a CORE file and are caught by a core suite, as data."""
    import ast
    rows = []
    for tool, default_file in (("tools/mutate_aruco_ids.py", "CADExporter/bam_cad_core/aruco_numbering.py"),
                               ("tools/mutate_aruco_label.py", None)):
        tree = ast.parse(ref_path.show(tool).decode("utf-8"))
        env = {"ROOT": "", "CORE": "CADExporter/bam_cad_core/aruco_label.py"}
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in ("PREVIEW", "BODIES", "DIALOG", "RULE1", "MUTATIONS")):
                env[node.targets[0].id] = eval(compile(ast.Expression(node.value), tool, "eval"), {}, env)
        for m in env["MUTATIONS"]:
            if default_file:
                mid, rule, old, new, must = m
                path, suites = default_file, ["tests/test_aruco_ids_stability.py"]
            else:
                mid, rule, path, old, new, suites, must = m
            if not path.startswith("CADExporter/bam_cad_core/"):
                continue                         # an add-in file: the Fusion adapter's (M4)
            rows.append({"id": mid, "tool": tool, "rule": rule, "file": path, "old": old, "new": new,
                         "suites": suites, "must": must})
    import json
    text = ("# REF: the mutation tables of tools/mutate_aruco_ids.py and mutate_aruco_label.py at "
            f"{ref_path.REF_COMMIT}\n# (rows on a core file only). Data; tests/core/test_ref_mutations.py "
            "runs them. Do not edit by hand.\nMUTATIONS = " + json.dumps(rows, indent=1, ensure_ascii=False)
            + "\n")
    (OUT / "ref_mutations.py").write_text(text, encoding="utf-8", newline="\n")
    return len(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in SUITES:
        port_suite(name)
    port_helpers()
    print(f"{port_mutations()} mutations -> tests/core/ref_suites/ref_mutations.py")
    print(f"{len(SUITES)} suites -> {OUT.relative_to(ref_path.ROOT)}")


if __name__ == "__main__":
    main()
