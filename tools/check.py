"""ONE command for every check (PLAN 3.4). Groups are discovered, so no
milestone edits this file after M1.

    .venv/Scripts/python tools/check.py            # every group
    .venv/Scripts/python tools/check.py core plan  # some groups
    .venv/Scripts/python tools/check.py --trace    # rewrite docs/test_trace.md
    .venv/Scripts/python tools/check.py --list     # the groups it found

| Group | Exists when | Runs |
|---|---|---|
| core, plan, scene, verify, server, adapters, ... | `tests/<name>/` holds a `test_*.py` | pytest on that folder (pytest-xdist) |
| studio | `studio/package.json` | `npm run build`, then `npm run test` (vitest) |
| e2e | `e2e/package.json` (or `studio/e2e/`) | uvicorn on 127.0.0.1:5360 + Vite on 5361, `npx playwright test` in `e2e/`; the server's home, scenes and PrusaSlicer folder are a temp dir and the fixture; both stopped in `finally`; refused when a port is already bound |

One line per group ("core: 2,311 passed in 38 s"); exit 1 on any failure.
`--trace` writes docs/test_trace.md: one row per section of
tests/ref_sections.json with the pytest node ids that carry its
`ref(suite, section)` marker, or the reason in tests/ref_trace_notes.json;
it prints `missing: N` and exits 1 when N > 0.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
STUDIO = ROOT / "studio"
E2E = ROOT / "e2e"
PORTS = (5360, 5361)


# --------------------------------------------------------------- discovery

def groups():
    out = []
    tests = ROOT / "tests"
    for d in sorted(p for p in tests.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        if any(d.glob("test_*.py")):
            out.append(d.name)
    if (STUDIO / "package.json").exists():
        out.append("studio")
    if (E2E / "package.json").exists() or (STUDIO / "e2e").is_dir():
        out.append("e2e")
    return out


# ------------------------------------------------------------------ runners

def _env():
    env = dict(os.environ)
    home = tempfile.mkdtemp(prefix="aruco_check_")
    env.update({"USERPROFILE": home, "HOME": home, "ARUCO_STUDIO_HOME": os.path.join(home, "studio"),
                "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
    return env


def run_pytest(name):
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="aruco_check_xml_") as tmp:
        xml = Path(tmp) / "junit.xml"
        cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"tests/{name}",
               f"--junitxml={xml}"]
        try:
            import xdist  # noqa: F401
            cmd += ["-n", "auto"]
        except ImportError:
            pass
        p = subprocess.run(cmd, cwd=str(ROOT), env=_env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
        if xml.exists():
            root = ET.parse(xml).getroot()
            for suite in ([root] if root.tag == "testsuite" else root.iter("testsuite")):
                for k in counts:
                    counts[k] += int(suite.get(k, 0))
    dt = time.time() - t0
    passed = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    ok = p.returncode == 0
    words = f"{passed:,} passed"
    if counts["skipped"]:
        words += f", {counts['skipped']:,} skipped"
    if counts["failures"] or counts["errors"]:
        words += f", {counts['failures'] + counts['errors']:,} failed"
    line = f"{name}: {words} in {dt:.0f} s"
    if not ok:
        tail = "\n".join(p.stdout.strip().splitlines()[-25:])
        line += "\n" + tail
    return ok, line


def _npm():
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def _npm_install(folder):
    """node_modules from the lock file when they are missing (npm only)."""
    if (folder / "package.json").exists() and not (folder / "node_modules").is_dir():
        subprocess.run([_npm(), "ci", "--no-audit", "--no-fund"], cwd=str(folder), capture_output=True)


def run_studio():
    t0 = time.time()
    _npm_install(STUDIO)
    for script in ("build", "test"):
        p = subprocess.run([_npm(), "run", script], cwd=str(STUDIO), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode:
            return False, f"studio: npm run {script} failed\n" + "\n".join(
                (p.stdout + p.stderr).strip().splitlines()[-25:])
    return True, f"studio: build + vitest passed in {time.time() - t0:.0f} s"


def _bound(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait(port, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        if _bound(port):
            return True
        time.sleep(0.5)
    return False


def _stop(proc):
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":                            # the whole tree (npm -> node)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_e2e():
    busy = [p for p in PORTS if _bound(p)]
    if busy:
        return False, f"e2e: refused, port(s) {busy} already bound (stop what holds them first)"
    t0 = time.time()
    api = ui = None
    env = _env()
    env.update({"ARUCO_STUDIO_SCENES": os.path.join(env["ARUCO_STUDIO_HOME"], "scenes"),
                "BAM_ARUCO_PRUSASLICER_DIR": str(ROOT / "tests" / "fixtures" / "prusaslicer_m8c")})  # M8b2: the physical printers too
    where = E2E if (E2E / "package.json").exists() else STUDIO
    _npm_install(STUDIO)
    _npm_install(where)
    try:
        api = subprocess.Popen([PY, "-m", "uvicorn", "aruco_studio.server.app:app", "--host",
                                "127.0.0.1", "--port", "5360"], cwd=str(ROOT), env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ui = subprocess.Popen([_npm(), "run", "dev", "--", "--host", "127.0.0.1", "--port", "5361",
                               "--strictPort"], cwd=str(STUDIO), env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not (_wait(5360) and _wait(5361)):
            return False, "e2e: the servers did not come up on 5360 / 5361"
        npx = shutil.which("npx.cmd") or shutil.which("npx") or "npx"
        # the browser keeps the real profile folder (Chrome refuses a temp
        # USERPROFILE); only the servers run on the temp home
        penv = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        p = subprocess.run([npx, "playwright", "test"], cwd=str(where), env=penv, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        ok = p.returncode == 0
        lines = (p.stdout + p.stderr).strip().splitlines()
        tail = "\n".join(lines[-25:])
        summary = " ".join(x.strip() for x in lines if x.strip().endswith(("passed", "skipped"))
                           or " passed (" in x or " skipped" in x)[-120:]
        return ok, f"e2e: {summary or ('passed' if ok else 'FAILED')} in {time.time() - t0:.0f} s" + (
            "" if ok else "\n" + tail)
    finally:
        _stop(ui)
        _stop(api)


# -------------------------------------------------------------------- trace

def trace():
    sections = json.loads((ROOT / "tests" / "ref_sections.json").read_text(encoding="utf-8"))
    notes_doc = json.loads((ROOT / "tests" / "ref_trace_notes.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="aruco_trace_") as tmp:
        out = Path(tmp) / "markers.json"
        env = _env()
        env["ARUCO_TRACE_OUT"] = str(out)
        p = subprocess.run([PY, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
                            "tests"], cwd=str(ROOT), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if p.returncode not in (0, 5) or not out.exists():
            print(p.stdout[-3000:], p.stderr[-3000:])
            return 2
        marks = json.loads(out.read_text(encoding="utf-8"))
    by = {}
    for m in marks:
        by.setdefault((m["suite"], m["section"]), []).append(m["nodeid"])
    rows, counts = [], {}
    for s in sections["suites"]:
        notes = notes_doc.get(s["suite"], {})
        for r in s["sections"]:
            nodes = by.get((s["suite"], r["text"]), [])
            note = notes.get(r["text"]) or (notes.get("*") if not nodes else None)
            if nodes and note and note.startswith("parked"):
                status = note
            elif nodes:
                status = "ported"
            elif note:
                status = note
            else:
                status = "MISSING"
            kind = status.split(":")[0].split(" (")[0]
            counts[kind] = counts.get(kind, 0) + 1
            rows.append((s["suite"], r, nodes, status))
    missing = counts.get("MISSING", 0)
    lines = ["# Test trace: REF's sections -> pytest", "",
             "Generated by `tools/check.py --trace`; do not edit. One row per section of a REF suite "
             "(`tests/ref_sections.json`: every `print(\"...\")` header of the suite at "
             f"`{sections['ref_commit']}`). A row is ported when a pytest test carries its "
             "`@pytest.mark.ref(suite, section)`; otherwise `tests/ref_trace_notes.json` says why.", "",
             "| Status | Rows |", "|---|---:|"]
    for k in sorted(counts):
        lines.append(f"| {k} | {counts[k]} |")
    lines += [f"| total | {len(rows)} |", "", f"missing: {missing}", ""]
    cur = None
    for suite, r, nodes, status in rows:
        if suite != cur:
            cur = suite
            lines += ["", f"## `{suite}`", "", "| # | Section (REF line) | REF spec tests | pytest | Status |",
                      "|---:|---|---|---|---|"]
        text = r["text"].replace("|", "\\|")
        ids = ", ".join(r.get("spec_ids") or [])
        nd = "<br>".join(f"`{n}`" for n in nodes) if nodes else ""
        lines.append(f"| {r['line']} | {text} | {ids} | {nd} | {status} |")
    (ROOT / "docs" / "test_trace.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(" · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    print(f"missing: {missing}")
    print("docs/test_trace.md written")
    return 1 if missing else 0


# --------------------------------------------------------------------- main

def main(argv):
    if "--trace" in argv:
        return trace()
    found = groups()
    if "--list" in argv:
        print(" ".join(found))
        return 0
    want = [a for a in argv if not a.startswith("-")] or found
    unknown = [g for g in want if g not in found]
    if unknown:
        print(f"unknown group(s) {unknown}; found: {' '.join(found)}")
        return 2
    t0 = time.time()
    ok_all = True
    for g in want:
        if g == "studio":
            ok, line = run_studio()
        elif g == "e2e":
            ok, line = run_e2e()
        else:
            ok, line = run_pytest(g)
        ok_all &= ok
        print(line.encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8"), flush=True)
    print(f"{'OK' if ok_all else 'FAILED'} in {time.time() - t0:.0f} s")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
