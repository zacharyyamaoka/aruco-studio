"""Render docs/spec.json to reports/spec.html and list what is still planned.

    .venv/Scripts/python tools/spec_status.py          # writes reports/spec.html
    .venv/Scripts/python tools/spec_status.py --check  # also exit 1 when a status is not a known one

Prints one line per feature / test that is still `planned` (with its
milestone and, when the spec gives one, the reason), then the counts.
The orchestrator runs it after each milestone (PLAN 2, D11).
"""
from __future__ import annotations

import html
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "spec.json"
OUT = ROOT / "reports" / "spec.html"

CSS = """
:root { --bg:#ffffff; --fg:#1d1d1f; --muted:#6e6e73; --line:#d9d9de; --head:#f4f4f6;
        --built:#1f7a3a; --planned:#8a6d00; --failing:#b3261e; --deferred:#6e6e73; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#161618; --fg:#ececf0; --muted:#a1a1a8; --line:#34343a; --head:#202024;
  --built:#6fd28f; --planned:#e8c45a; --failing:#ff8a80; --deferred:#a1a1a8; } }
:root[data-theme="dark"] { --bg:#161618; --fg:#ececf0; --muted:#a1a1a8; --line:#34343a;
  --head:#202024; --built:#6fd28f; --planned:#e8c45a; --failing:#ff8a80; --deferred:#a1a1a8; }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif;
       margin:0 auto; max-width:1180px; padding:16px; }
h1 { font-size:22px; margin:8px 0 4px; } h2 { font-size:17px; margin:24px 0 8px; }
p.about { color:var(--muted); margin:2px 0; }
.wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; }
th, td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
th { background:var(--head); position:sticky; top:0; }
td.id { white-space:nowrap; font-family:ui-monospace, monospace; font-size:12.5px; }
.s-built, .s-passing { color:var(--built); font-weight:600; }
.s-planned { color:var(--planned); font-weight:600; }
.s-failing { color:var(--failing); font-weight:600; }
.s-partial, .s-deferred, .s-skipped { color:var(--deferred); font-weight:600; }
.counts span { margin-right:14px; }
"""


def esc(x):
    return html.escape(str(x if x is not None else ""))


def render(spec):
    f_counts = Counter(f["status"] for f in spec["features"])
    t_counts = Counter(t["status"] for t in spec["tests"])
    out = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width, initial-scale=1'>",
           "<title>ArUco Studio spec</title><style>", CSS, "</style></head><body>",
           f"<h1>{esc(spec['title'])}</h1>",
           f"<p class='about'>Updated {esc(spec.get('updated'))}. Rendered from docs/spec.json "
           "by tools/spec_status.py.</p>"]
    for a in spec.get("about", []):
        out.append(f"<p class='about'>{esc(a)}</p>")
    out.append("<p class='counts'>Features: " + "".join(
        f"<span class='s-{esc(k)}'>{esc(k)} {v}</span>" for k, v in sorted(f_counts.items()))
        + "<br>Tests: " + "".join(f"<span class='s-{esc(k)}'>{esc(k)} {v}</span>"
                                   for k, v in sorted(t_counts.items())) + "</p>")
    out += ["<h2>Features</h2><div class='wrap'><table><tr><th>Id</th><th>Name</th><th>Milestone</th>"
            "<th>Status</th><th>What</th><th>Result</th></tr>"]
    for f in spec["features"]:
        out.append(f"<tr><td class='id'>{esc(f['id'])}</td><td>{esc(f['name'])}</td>"
                   f"<td>{esc(f.get('milestone'))}</td><td class='s-{esc(f['status'])}'>{esc(f['status'])}</td>"
                   f"<td>{esc(f.get('description'))}</td><td>{esc(f.get('result', ''))}</td></tr>")
    out += ["</table></div><h2>Tests</h2><div class='wrap'><table><tr><th>Id</th><th>Kind</th>"
            "<th>Milestone</th><th>Status</th><th>How</th><th>Result</th></tr>"]
    for t in spec["tests"]:
        out.append(f"<tr><td class='id'>{esc(t['id'])}</td><td>{esc(t.get('kind'))}</td>"
                   f"<td>{esc(t.get('milestone'))}</td><td class='s-{esc(t['status'])}'>{esc(t['status'])}</td>"
                   f"<td>{esc(t.get('how'))}</td><td>{esc(t.get('result', ''))}</td></tr>")
    out.append("</table></div></body></html>")
    return "\n".join(out)


def main(argv):
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(spec), encoding="utf-8", newline="\n")
    known_f, known_t = set(spec["statuses"]["feature"]), set(spec["statuses"]["test"])
    bad = [x["id"] for x in spec["features"] if x["status"] not in known_f] + \
          [x["id"] for x in spec["tests"] if x["status"] not in known_t]
    for kind, items in (("feature", spec["features"]), ("test", spec["tests"])):
        for x in items:
            if x["status"] == "planned":
                why = f" -- {x['reason']}" if x.get("reason") else ""
                print(f"planned {kind} {x['id']} ({x.get('milestone') or 'no milestone'}){why}")
    f_counts = Counter(f["status"] for f in spec["features"])
    t_counts = Counter(t["status"] for t in spec["tests"])
    print("features: " + ", ".join(f"{k} {v}" for k, v in sorted(f_counts.items())))
    print("tests: " + ", ".join(f"{k} {v}" for k, v in sorted(t_counts.items())))
    print(f"-> {OUT.relative_to(ROOT)}")
    if bad:
        print("unknown status on: " + ", ".join(bad))
    return 1 if ("--check" in argv and bad) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
