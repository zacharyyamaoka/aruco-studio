"""Render docs/spec.json to reports/status.html: a static page with no
scripts. Two sections, "Functionality" and "Tests", each with its statuses,
then the hand-over screenshots (reports/screens/final_*.png).

    .venv/Scripts/python tools/status_page.py

The page is for Zach to open from disk; the images are relative links.
"""
from __future__ import annotations

import html
import json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "spec.json"
OUT = ROOT / "reports" / "status.html"
SCREENS = ROOT / "reports" / "screens"

CSS = """
:root { --bg:#ffffff; --fg:#1d1d1f; --muted:#6e6e73; --line:#d9d9de; --head:#f4f4f6;
        --ok:#1f7a3a; --warn:#8a6d00; --bad:#b3261e; --grey:#6e6e73; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#161618; --fg:#ececf0; --muted:#a1a1a8; --line:#34343a; --head:#202024;
  --ok:#6fd28f; --warn:#e8c45a; --bad:#ff8a80; --grey:#a1a1a8; } }
:root[data-theme="dark"] { --bg:#161618; --fg:#ececf0; --muted:#a1a1a8; --line:#34343a;
  --head:#202024; --ok:#6fd28f; --warn:#e8c45a; --bad:#ff8a80; --grey:#a1a1a8; }
body { background:var(--bg); color:var(--fg); font:14px/1.45 system-ui, sans-serif;
       margin:0 auto; max-width:1180px; padding:16px; }
h1 { font-size:22px; margin:8px 0 4px; } h2 { font-size:18px; margin:28px 0 8px; }
h3 { font-size:15px; margin:18px 0 6px; }
p.about { color:var(--muted); margin:2px 0; }
.wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; }
th, td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
th { background:var(--head); position:sticky; top:0; }
td.id { white-space:nowrap; font-family:ui-monospace, monospace; font-size:12.5px; }
.s-built, .s-passing { color:var(--ok); font-weight:600; }
.s-planned { color:var(--warn); font-weight:600; }
.s-failing { color:var(--bad); font-weight:600; }
.s-partial, .s-deferred, .s-skipped { color:var(--grey); font-weight:600; }
.counts span { margin-right:14px; }
.shots { display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; }
.shots figure { margin:0; }
.shots img { width:100%; height:auto; border:1px solid var(--line); border-radius:4px; }
.shots figcaption { color:var(--muted); font-size:12.5px; margin-top:4px; }
"""

# The hand-over screenshots, in the order the task named them, with a caption.
SHOTS = [
    ("final_2d_three_types.png", "2D canvas: a single marker, a 4 x 3 grid board and a 5 x 7 ChArUco board"),
    ("final_3d_view.png", "3D view (z x5): the raised single marker's white and black layers"),
    ("final_inspector_validation_error.png", "Inspector: two validation errors, each under its field, one summary line"),
    ("final_preset_library.png", "The preset Library window"),
]


def esc(x):
    return html.escape(str(x if x is not None else ""))


def counts_line(items):
    c = Counter(x["status"] for x in items)
    return "".join(f"<span class='s-{esc(k)}'>{esc(k)} {v}</span>" for k, v in sorted(c.items()))


def section(title, items, cols):
    out = [f"<h2>{esc(title)}</h2>", f"<p class='counts'>{counts_line(items)}</p>",
           "<div class='wrap'><table><tr>" + "".join(f"<th>{esc(h)}</th>" for h, _ in cols) + "</tr>"]
    for x in items:
        cells = []
        for h, key in cols:
            v = x.get(key, "")
            if key == "status":
                cells.append(f"<td class='s-{esc(v)}'>{esc(v)}</td>")
            elif key == "id":
                cells.append(f"<td class='id'>{esc(v)}</td>")
            elif key == "result":
                reason = x.get("reason")
                text = esc(v)
                if reason:
                    text = (text + " " if text else "") + f"<i>{esc(reason)}</i>"
                cells.append(f"<td>{text}</td>")
            else:
                cells.append(f"<td>{esc(v)}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table></div>")
    return out


def render(spec):
    out = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width, initial-scale=1'>",
           "<title>ArUco Studio status</title><style>", CSS, "</style></head><body>",
           "<h1>ArUco Studio: status</h1>",
           f"<p class='about'>Rendered {date.today().isoformat()} from docs/spec.json by tools/status_page.py. "
           "The Definition of Done, what is open and how to run are in docs/STATUS.md.</p>",
           f"<p class='about'>Spec updated: {esc(spec.get('updated'))}.</p>"]
    out += section("Functionality", spec["features"],
                   [("Id", "id"), ("Name", "name"), ("Area", "area"), ("Milestone", "milestone"),
                    ("Status", "status"), ("What", "description"), ("Result", "result")])
    out += section("Tests", spec["tests"],
                   [("Id", "id"), ("Kind", "kind"), ("Milestone", "milestone"), ("Status", "status"),
                    ("How", "how"), ("Result", "result")])
    out.append("<h2>Screenshots</h2><p class='about'>Taken from the served build "
               "(<code>npm --prefix studio run studio</code>, http://127.0.0.1:5360) at hand-over.</p>")
    out.append("<div class='shots'>")
    for name, caption in SHOTS:
        if (SCREENS / name).exists():
            out.append(f"<figure><a href='screens/{esc(name)}'><img src='screens/{esc(name)}' alt='{esc(caption)}'></a>"
                       f"<figcaption>{esc(caption)}</figcaption></figure>")
        else:
            out.append(f"<figure><figcaption>{esc(name)}: missing</figcaption></figure>")
    out.append("</div></body></html>")
    return "\n".join(out)


def main():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(spec), encoding="utf-8", newline="\n")
    print(f"-> {OUT.relative_to(ROOT)}: features {len(spec['features'])}, tests {len(spec['tests'])}, "
          f"screenshots {sum((SCREENS / n).exists() for n, _ in SHOTS)} of {len(SHOTS)}")


if __name__ == "__main__":
    main()
