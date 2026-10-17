"""plan/ and scene/ are the standard library only and never import
adapters/, server/ or verify/ (ARCHITECTURE 2; D5; spec ST-T-PURE-1): build123d,
viser and Fusion reuse them as they are. And they never open a file."""
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "aruco_studio"
DIRS = ("plan", "scene")
FORBIDDEN_PKGS = ("adapters", "server", "verify")


def _files():
    for d in DIRS:
        yield from sorted((PKG / d).glob("*.py"))


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, node.lineno, 0
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", node.lineno, node.level


def test_import_loads_no_numpy_cv2_fastapi_or_adsk():
    mods = [f"aruco_studio.{d}.{p.stem}" for d in DIRS for p in sorted((PKG / d).glob("*.py"))
            if p.stem != "__init__"]
    code = ("import sys, importlib\n"
            f"for m in {mods!r}:\n    importlib.import_module(m)\n"
            "bad = sorted(k for k in sys.modules if k.split('.')[0] in "
            "('numpy', 'cv2', 'adsk', 'fastapi', 'pydantic', 'uvicorn'))\n"
            "bad += sorted(k for k in sys.modules if k.startswith(('aruco_studio.server', "
            "'aruco_studio.verify', 'aruco_studio.adapters')))\n"
            "print(','.join(bad))\n")
    p = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "", p.stdout


def test_only_stdlib_core_plan_scene():
    std = set(sys.stdlib_module_names) | {"__future__"}
    bad = []
    for p in _files():
        for mod, line, lvl in _imports(p):
            top = mod.split(".")[0]
            if lvl == 0 and top not in std and top != "aruco_studio":
                bad.append(f"{p.parent.name}/{p.name}:{line} {mod}")
            parts = mod.split(".")
            if any(x in FORBIDDEN_PKGS for x in parts):
                bad.append(f"{p.parent.name}/{p.name}:{line} {'.' * lvl}{mod}")
    assert not bad, bad


def test_no_file_io_in_plan_or_scene():
    """No open(), no Path reads or writes: the server does the files."""
    bad = []
    for p in _files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute)
                                                             else "")
                if name in ("open", "read_text", "write_text", "read_bytes", "write_bytes",
                            "unlink", "mkdir"):
                    bad.append(f"{p.parent.name}/{p.name}:{node.lineno} {name}()")
    assert not bad, bad
