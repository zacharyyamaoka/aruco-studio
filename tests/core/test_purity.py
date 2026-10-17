"""The core is the standard library only (PLAN M1.1, M1.2; ARCHITECTURE 2; D5).

* importing every core module loads no numpy, no cv2 and no adsk (in a fresh
  process, so nothing the test runner loaded counts);
* no core file IMPORTS adsk, numpy or cv2 (by `ast`, so REF's docstrings,
  which name cv2 where they say what was measured with it, do not count);
* every import inside core/ is the standard library or core/ itself;
* no core function opens, lists, writes or deletes a file, or reads the
  environment (audit C7; spec ST-T-PURE-1): the server does the files.
  One read is allowed: `dictionary._load` reads the dictionary table that
  ships inside the package (REF's text verbatim; package data, never a
  user's file).
"""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "aruco_studio" / "core"
MODULES = sorted(p.stem for p in CORE.glob("*.py") if p.stem != "__init__")
FORBIDDEN = ("adsk", "numpy", "cv2")


def test_import_loads_only_the_standard_library():
    code = ("import sys, importlib\nimport aruco_studio.core\n"
            f"for m in {MODULES!r}:\n    importlib.import_module('aruco_studio.core.' + m)\n"
            "bad = sorted(k for k in sys.modules if k.split('.')[0] in ('numpy', 'cv2', 'adsk'))\n"
            "print(','.join(bad))\n")
    p = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "", p.stdout


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0], node.lineno, 0
        elif isinstance(node, ast.ImportFrom):
            yield (node.module or "").split(".")[0], node.lineno, node.level


def test_no_core_file_imports_fusion_numpy_or_cv2():
    hits = [f"{p.name}:{line} {mod}" for p in CORE.glob("*.py") for mod, line, lvl in _imports(p)
            if lvl == 0 and mod in FORBIDDEN]
    assert not hits, hits


def test_core_imports_only_stdlib_and_itself():
    std = set(sys.stdlib_module_names) | {"__future__"}
    bad = [f"{p.name}:{line} {mod}" for p in CORE.glob("*.py") for mod, line, lvl in _imports(p)
           if lvl == 0 and mod not in std and mod != "aruco_studio"]
    assert not bad, bad


def test_every_module_of_the_module_map_exists():
    """PLAN 1.1 / 1.2: the core's new homes."""
    want = {"dictionary", "board", "origin", "slabs", "chamfer", "autosize", "label", "trim",
            "numbering", "markers", "sheet", "beds", "settings", "edits", "geometry", "form",
            "validate", "presets", "prusa", "restructure", "faces", "export_rows", "marker_table",
            "ids_design"}
    assert want <= set(MODULES), sorted(want - set(MODULES))


FILE_CALLS = {"open", "read_text", "write_text", "read_bytes", "write_bytes", "unlink", "mkdir",
              "makedirs", "listdir", "remove", "rmtree", "isfile", "isdir", "exists",
              "expanduser", "which", "scandir", "glob", "iterdir", "rename"}
PACKAGE_DATA = {("dictionary.py", "_load")}           # the table inside the package


def test_no_file_io_in_core():
    bad = []
    for p in sorted(CORE.glob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        owner = {}
        for top in tree.body:
            for node in ast.walk(top):
                owner[id(node)] = getattr(top, "name", "<module>")
        for node in ast.walk(tree):
            hit = None
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute)
                                                             else "")
                if name in FILE_CALLS:
                    hit = f"{name}()"
                if (name == "replace" and isinstance(f, ast.Attribute)
                        and isinstance(f.value, ast.Name) and f.value.id == "os"):
                    hit = "os.replace()"
            elif isinstance(node, ast.Attribute) and node.attr == "environ":
                hit = "os.environ"
            if hit and (p.name, owner.get(id(node))) not in PACKAGE_DATA:
                bad.append(f"{p.name}:{node.lineno} {owner.get(id(node))}: {hit}")
    assert not bad, bad
