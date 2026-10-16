"""List the sections of REF's ArUco test suites, and count REF's own checks.

    .venv/Scripts/python tools/ref_sections.py            # -> tests/ref_sections.json

A SECTION of a REF suite is each header the suite prints: a statement
`print("<plain string>")` with one literal argument (REF writes them as
`print("== ...")`, `print("§4 ...")` or `print("G0.1 ...")`). They are found
with `ast` in the file AT THE PINNED COMMIT, never imported.

Then every suite that needs no `adsk` (not even a stand-in) is RUN, from its
own place in REF, in a subprocess whose `print` is a recorder: each header
switches the current section, each `  ok  ` / `FAIL` line counts towards it.
Those per-section counts are the yardstick the ported pytest copies must
match exactly (tests/core/_ref_runner.py).

Read only: PYTHONDONTWRITEBYTECODE=1, USERPROFILE / HOME = a temp dir,
BAM_ARUCO_PRUSASLICER_DIR = REF's fixture, cwd = a temp dir, and REF's
`git status --porcelain` must be identical before and after.
"""
from __future__ import annotations

import ast
import json
import re
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ref_path  # noqa: E402

OUT = ref_path.ROOT / "tests" / "ref_sections.json"

# suite -> how it is used. "run": REF's suite is run to count its checks.
# "list": only its sections are listed (it loads a stand-in adsk, or needs
# another venv). "entry": run only these functions of the suite (the rest of
# the file loads a stand-in adsk).
SUITES = {
    # the 17 Fusion-free suites (inventory core_and_tests.md 2.1 / 2.3)
    "tests/test_aruco_autosize.py": {"run": True},
    "tests/test_aruco_board.py": {"run": True},
    "tests/test_aruco_cells.py": {"run": True},
    "tests/test_aruco_cells_legacy.py": {"run": False, "why": "its golden maker installs a stand-in adsk for the 12 evaluate() cases"},
    "tests/test_aruco_chamfer.py": {"run": True},
    "tests/test_aruco_label.py": {"run": True},
    "tests/test_aruco_label_position.py": {"run": True},
    "tests/test_aruco_label_preview.py": {"run": True},
    "tests/test_aruco_label_rule1.py": {"run": True},
    "tests/test_aruco_numbering.py": {"run": True},
    "tests/test_aruco_ids_stability.py": {"run": True},
    "tests/test_aruco_output.py": {"run": True},
    "tests/test_aruco_slabs.py": {"run": True},
    "tests/test_aruco_trim.py": {"run": True},
    "tests/test_aruco_trim_legacy.py": {"run": False, "why": "its golden maker installs a stand-in adsk for the 26 evaluate() cases"},
    "tests/test_aruco_settings.py": {"run": True},
    "tests/test_aruco_presets.py": {"run": True},
    # listed for the trace only
    "tests/test_aruco_frame.py": {"run": True, "entry": ["test_origin_math"],
                                  "why": "only test_origin_math is core; the rest loads a stand-in adsk or needs yourdfpy"},
    "tests/test_aruco_frame_pnp.py": {"run": False, "why": "stand-in adsk + cv2"},
    "tests/test_aruco_label_print.py": {"run": False, "why": "the slicing oracle's venv"},
}


def _header(arg):
    """(text, regex) of a print() argument that is a header, else None. A
    plain string is matched exactly; an f-string's {fields} match anything."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.strip():
        return arg.value, re.escape(arg.value)
    if isinstance(arg, ast.JoinedStr):
        text, rx = "", ""
        for v in arg.values:
            if isinstance(v, ast.Constant):
                text += str(v.value)
                rx += re.escape(str(v.value))
            else:
                text += "{" + ast.unparse(v.value) + "}"
                rx += ".*?"
        if text.strip() and any(isinstance(v, ast.Constant) and str(v.value).strip()
                                for v in arg.values):
            return text, rx
    return None


def sections_of(src: str):
    """[{text, key, regex, line, func}] in source order; repeats get '#2'."""
    tree = ast.parse(src)
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def func_of(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "print"
                and len(node.value.args) == 1 and not node.value.keywords):
            h = _header(node.value.args[0])
            if h is None:
                continue
            text, rx = h
            # a check's own output line is not a header
            if text.startswith(("  ok  ", "FAIL", "  skip", "SKIP")) or text.strip() == "":
                continue
            # the suites' final tally ("{PASS} passed, ...") is not a section
            if re.match(r"\s*\{PASS\}", text) or text[:1].isspace():
                continue
            out.append((text, rx, node.lineno, func_of(node)))
    out.sort(key=lambda t: t[2])
    seen = {}
    rows = []
    for text, rx, line, fn in out:
        seen[text] = seen.get(text, 0) + 1
        rows.append({"text": text, "key": text if seen[text] == 1 else f"{text}#{seen[text]}",
                     "regex": rx, "line": line, "func": fn})
    return rows


# The recorder that runs inside the subprocess (also used, in-process, by the
# pytest runner for the ported copies: tests/core/_ref_runner.py has the same
# logic). Kept as source text so the child imports nothing of ours.
CHILD = r'''
import json, sys, runpy, builtins
import re
path, headers, entry, core_dir = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3]), sys.argv[4]
# headers: [[key, regex], ...] in source order
assert "aruco_studio" not in sys.modules
try:
    import aruco_studio  # noqa
    print("REFUSED: aruco_studio is importable", file=sys.stderr); sys.exit(2)
except ImportError:
    pass
counts = {}
order = []
current = ["(before the first section)"]
seen = {}
real_print = builtins.print
def rec(*args, sep=" ", end="\n", file=None, flush=False):
    if file is not None and file is not sys.stdout:
        return real_print(*args, sep=sep, end=end, file=file)
    text = sep.join(str(a) for a in args)
    if len(args) == 1 and isinstance(args[0], str) and not args[0].startswith(("  ok  ", "FAIL", "  skip")):
        hits = [k for k, rx in headers if re.fullmatch(rx, args[0], flags=re.S)]
        if hits:
            # a repeated header: the first of its keys not seen yet, else the last
            key = next((k for k in hits if k not in seen), hits[-1])
            seen[key] = seen.get(key, 0) + 1
            current[0] = key
            return
    c = counts.setdefault(current[0], {"ok": 0, "fail": 0, "skip": 0, "fails": []})
    if text.startswith("  ok  "):
        c["ok"] += 1
    elif text.startswith("FAIL"):
        c["fail"] += 1
        c["fails"].append(text[:200])
    elif text.lstrip().startswith("skip") or text.startswith("SKIP"):
        c["skip"] += 1
g = {"__name__": "__main__" if not entry else "ref_suite", "__file__": path, "print": rec,
     "__builtins__": builtins}
code = 0
sys.argv = [path]
try:
    src = open(path, encoding="utf-8").read()
    exec(compile(src, path, "exec"), g)
    if entry:
        sys.path.insert(0, core_dir)
        from bam_cad_core import markers as M
        for fn in entry:
            g[fn](M)
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
except BaseException as e:
    import traceback
    code = "raised: " + "".join(traceback.format_exception_only(type(e), e)).strip()[:300]
real_print(json.dumps({"counts": counts, "exit": code, "PASS": g.get("PASS"),
                       "FAIL": len(g.get("FAIL") or [])}))
'''


def run_ref(rel: str, rows, entry):
    headers = [[r["key"], r["regex"]] for r in rows]
    with tempfile.TemporaryDirectory(prefix="aruco_ref_run_") as tmp:
        env = dict(os.environ)
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "USERPROFILE": tmp, "HOME": tmp,
                    "BAM_ARUCO_PRUSASLICER_DIR": str(ref_path.REF / "tests" / "fixtures" / "prusaslicer"),
                    "PYTHONIOENCODING": "utf-8"})
        env.pop("PYTHONPATH", None)
        child = Path(tmp) / "child.py"
        child.write_text(CHILD, encoding="utf-8", newline="\n")
        p = subprocess.run([sys.executable, "-I", "-X", "utf8", str(child), str(ref_path.REF / rel),
                            json.dumps(headers), json.dumps(entry or []),
                            str(ref_path.REF / "CADExporter")],
                           cwd=tmp, env=env, capture_output=True, timeout=900)
        out = p.stdout.decode("utf-8", "replace").strip().splitlines()
        if p.returncode != 0 or not out:
            raise SystemExit(f"{rel}: the recorder failed ({p.returncode}): "
                             + p.stderr.decode("utf-8", "replace")[-2000:])
        return json.loads(out[-1])


def main():
    before = ref_path.status()
    suites = []
    for rel, how in SUITES.items():
        src = ref_path.show(rel).decode("utf-8")
        if not ref_path.same_as_pinned(rel):
            raise SystemExit(f"{rel}: REF's working tree differs from {ref_path.REF_COMMIT}")
        rows = sections_of(src)
        entry = {"suite": rel, "sha256": ref_path.sha256_at(rel), "run": bool(how.get("run")),
                 "entry": how.get("entry"), "why": how.get("why", ""), "sections": rows}
        if how.get("run"):
            print(f"running {rel} ...", flush=True)
            res = run_ref(rel, rows, how.get("entry"))
            entry["ref_exit"] = res["exit"]
            entry["ref_pass"] = res["PASS"]
            entry["ref_fail"] = res["FAIL"]
            entry["ref_counts"] = res["counts"]
            print(f"   {res['PASS']} passed, {res['FAIL']} failed, exit {res['exit']}", flush=True)
        suites.append(entry)
    after = ref_path.status()
    if before != after:
        raise SystemExit("REF's git status changed during the run: "
                         f"before {before!r} after {after!r}")
    doc = {"schema": "arucostudio.ref_sections/1", "ref": str(ref_path.REF),
           "ref_commit": ref_path.REF_COMMIT, "made_by": "tools/ref_sections.py",
           "date": date.today().isoformat(),
           "about": "A section = a print('<literal>') header of a REF suite. ref_counts = the "
                    "checks REF's own suite passed under each header, run read-only.",
           "suites": suites}
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    n = sum(len(s["sections"]) for s in suites)
    print(f"{len(suites)} suites, {n} sections -> {OUT.relative_to(ref_path.ROOT)}")


if __name__ == "__main__":
    main()
