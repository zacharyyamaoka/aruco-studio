"""The core is the standard library only (PLAN M1.1, M1.2; ARCHITECTURE 2; D5).

* importing every core module loads no numpy, no cv2 and no adsk (in a fresh
  process, so nothing the test runner loaded counts);
* no core file IMPORTS adsk, numpy or cv2 (by `ast`, so REF's docstrings,
  which name cv2 where they say what was measured with it, do not count);
* every import inside core/ is the standard library or core/ itself.
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
