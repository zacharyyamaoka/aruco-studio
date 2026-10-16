"""Run one ported REF suite (tests/core/ref_suites/ref_*.py) and count its
checks per section. Started by _ref_runner.py in its own process, the way
REF ran each suite as its own script.

    python _ref_child.py <suite copy> <headers json> <entry json>

Prints one JSON line: {"counts": {section: {"ok", "fail", "skip", "fails"}},
"exit", "PASS", "FAIL"}. The same recorder as tools/ref_sections.py, which
counted REF's own run.
"""
import builtins
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "ref_suites"), str(ROOT), str(ROOT / "tools")]
if os.environ.get("ARUCO_STUDIO_CORE_ROOT"):     # a mutated copy of the package (mutation tests)
    sys.path.insert(0, os.environ["ARUCO_STUDIO_CORE_ROOT"])

path, headers, entry = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
counts, seen = {}, {}
current = ["(before the first section)"]
real_print = builtins.print


def rec(*args, sep=" ", end="\n", file=None, flush=False):
    if file is not None and file is not sys.stdout:
        return real_print(*args, sep=sep, end=end, file=file)
    text = sep.join(str(a) for a in args)
    if (len(args) == 1 and isinstance(args[0], str)
            and not args[0].startswith(("  ok  ", "FAIL", "  skip"))):
        hits = [k for k, rx in headers if re.fullmatch(rx, args[0], flags=re.S)]
        if hits:
            key = next((k for k in hits if k not in seen), hits[-1])
            seen[key] = seen.get(key, 0) + 1
            current[0] = key
            return
    c = counts.setdefault(current[0], {"ok": 0, "fail": 0, "skip": 0, "fails": []})
    if text.startswith("  ok  "):
        c["ok"] += 1
    elif text.startswith("FAIL"):
        c["fail"] += 1
        c["fails"].append(text[:400])
    elif text.lstrip().startswith("skip") or text.startswith("SKIP"):
        c["skip"] += 1


g = {"__name__": "__main__" if not entry else "ref_suite", "__file__": path, "print": rec,
     "__builtins__": builtins}
code = 0
sys.argv = [path]
try:
    src = Path(path).read_text(encoding="utf-8")
    exec(compile(src, path, "exec"), g)
    if entry:
        from aruco_studio.core import markers as M
        for fn in entry:
            g[fn](M)
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
except BaseException as e:                         # noqa: BLE001
    import traceback
    code = "raised: " + "".join(traceback.format_exception(type(e), e, e.__traceback__))[-1500:]
real_print(json.dumps({"counts": counts, "exit": code, "PASS": g.get("PASS"),
                       "FAIL": len(g.get("FAIL") or [])}))
