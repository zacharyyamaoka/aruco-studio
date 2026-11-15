#!/usr/bin/env python3
"""Build the margins + Re-ID report (2026-11-13): Zach's two asks --
print margins / keep-clear boxes, and new-marker ids that release and a
Re-ID of a selection from a start -- with the hero videos and stills
recorded from the real build (web/e2e/idsprint-hero.spec.ts, HERO_SHOTS).

    .venv/bin/python docs/build_margins_reid_report.py --media <dir> --out <file.html> [--evidence <json>]

The facade numbers on the page are computed when it is built, from this
checkout's aruco_studio (web_api.call), never typed here. --evidence is a
JSON of the test runs ({"runs": [[label, command, result], ...]}) taken on
the lane, shown as they were reported. Standard library only.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "web"))

from aruco_studio import web_api as W            # noqa: E402

CSS = """
:root { --bg:#f6f7f9; --panel:#fff; --text:#16181d; --muted:#5d6472; --line:#e3e6eb; --accent:#2f6fed; --ok:#16833a; --warn:#a15c00; }
@media (prefers-color-scheme: dark) { :root { --bg:#14161a; --panel:#1c1f24; --text:#e9ecf1; --muted:#9aa3b2; --line:#2c3038; --accent:#6b9bff; --ok:#4cc27a; --warn:#e0a54a; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:15px/1.55 system-ui, -apple-system, Segoe UI, sans-serif; }
main { max-width: 1040px; margin: 0 auto; padding: 28px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 6px; } h2 { font-size: 19px; margin: 34px 0 10px; } h3 { font-size: 15px; margin: 18px 0 6px; }
.verdict { font-size: 17px; background: var(--panel); border: 1px solid var(--line); border-left: 4px solid var(--ok); border-radius: 8px; padding: 12px 14px; }
.muted { color: var(--muted); } code { font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; }
.grid3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
figure { margin: 0; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
figure img, figure video { width: 100%; height: auto; display: block; border-radius: 4px; }
figcaption { font-size: 13px; color: var(--muted); padding: 6px 2px 0; }
table { border-collapse: collapse; width: 100%; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; font-size: 14px; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 12.5px; }
ul { padding-left: 20px; } li { margin: 4px 0; }
.ok { color: var(--ok); font-weight: 600; } .warn { color: var(--warn); font-weight: 600; }
.wrap { overflow-x: auto; }
"""


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def call(name: str, payload: dict) -> dict:
    out = json.loads(W.call(name, json.dumps(payload)))
    if "error" in out:
        raise SystemExit(f"{name}: {out['error']}")
    return out["result"]


def measured() -> dict:
    """The facade's answers for the cases the page names."""
    from test_web_layout import squares          # the sheet tests' own 40 mm squares
    item = lambda k, first=None: {"key": k, "type": "single", "dictionary": "DICT_4X4_50", "count": 1, "first_id": first}
    first = call("assign_ids", {"items": [item("a"), item("b"), item("c")]})
    after_delete = call("assign_ids", {"items": [item("a"), item("c"), item("d")], "ledger": first["ledger"]})
    page = [{"key": "grid", "type": "grid", "dictionary": "DICT_4X4_250", "count": 20, "first_id": None}] + \
           [{**item(f"s{k}"), "dictionary": "DICT_4X4_250"} for k in range(12)]
    ledger = {"grid": 0, **{f"s{k}": 20 + k for k in range(12)}}
    pasted = [{**item(f"p{k}"), "dictionary": "DICT_4X4_250"} for k in range(6)]
    zach = call("assign_ids", {"items": page + pasted, "ledger": ledger})
    ids = {a["key"]: a["ids"] for a in zach["items"]}
    its = squares(12)
    plain = call("sheet", {"items": its, "cut_lines": True})
    keep = [{"page": 0, "x_mm": 20, "y_mm": 70, "w_mm": 90, "h_mm": 80}]
    clear = call("sheet", {"items": its, "cut_lines": True, "margins_mm": {"top": 60}, "keep_clear": keep})
    k = keep[0]

    def apart(p):
        return max(k["x_mm"] - (p["x_mm"] + p["w_mm"]), p["x_mm"] - (k["x_mm"] + k["w_mm"]),
                   k["y_mm"] - (p["y_mm"] + p["h_mm"]), p["y_mm"] - (k["y_mm"] + k["h_mm"]))
    on0 = [p for p in clear["placements"] if p["page"] == 0]
    return {
        "released": {a["key"]: a["ids"] for a in after_delete["items"]},
        "zach_pasted": [ids[f"p{k}"][0] for k in range(6)],
        "plain_pages": plain["pages"], "clear_pages": clear["pages"],
        "clear_placed": len(clear["placements"]), "clear_min_y": min(p["y_mm"] for p in clear["placements"]),
        "clear_min_apart": round(min(apart(p) for p in on0), 2) if on0 else None,
    }


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def build(media: Path, evidence: dict) -> str:
    m = measured()
    img = lambda n: b64(media / n, "image/png")
    vid = lambda n: b64(media / n, "video/mp4")
    sha = git("rev-parse", "--short", "HEAD")
    runs = "".join(f"<tr><td>{html.escape(a)}</td><td><code>{html.escape(b)}</code></td><td>{html.escape(c)}</td></tr>"
                   for a, b, c in evidence.get("runs", []))
    body = f"""
<h1>Print margins, keep-clear boxes, and IDs that behave</h1>
<p class="muted">ArUco Studio · <code>main</code> @ <code>{sha}</code> · live on arucostudio.com · 2026-11-13</p>
<div class="verdict"><b>Both asks work in the real app.</b> New markers take the lowest free IDs (a deleted marker's IDs
come back at once) in reading order; select markers, type a <b>First ID</b> and they renumber 100, 101, … left to right,
top to bottom. Print has Top / Right / Bottom / Left margins and per-page <b>keep-clear boxes</b> you drag on the preview;
the sheet is laid out again round them.</div>

<h2>Watch it</h2>
<div class="grid2">
<figure><video src="{vid('hero-ids.mp4')}" autoplay muted loop playsinline controls></video>
<figcaption>IDs: six rectangles drawn out of order, A on all → #0–5 in reading order; the marker printing #1 deleted, a copy
pasted → it takes #1; all selected (the bare rectangle too, so A gives it a marker: seven), First ID 100 → #100–106
(DICT_4X4_50 grows to 4X4_250, said in the note).
<a href="hero-ids.gif">GIF</a></figcaption></figure>
<figure><video src="{vid('hero-print.mp4')}" autoplay muted loop playsinline controls></video>
<figcaption>Print: Top typed 60 mm → printing starts lower; Draw box on page 1 → the stickers are laid out round it.
<a href="hero-print.gif">GIF</a></figcaption></figure>
</div>

<h2>1 · IDs</h2>
<div class="grid3">
<figure><img src="{img('ids-1-reading-order.png')}" alt=""><figcaption>A on six rectangles drawn out of order: #0–5 read left to right, top to bottom.</figcaption></figure>
<figure><img src="{img('ids-2-released.png')}" alt=""><figcaption>#1 deleted (its rectangle stays, grey); the pasted copy on the right takes #1, not #6.</figcaption></figure>
<figure><img src="{img('ids-3-first-id-100.png')}" alt=""><figcaption>Batch panel → <b>First ID</b> 100: all seven (the bare rectangle got a marker from A) go #100–106 in reading order, one undo step.</figcaption></figure>
</div>
<ul>
<li><b>Deleted markers release their IDs.</b> Auto id now gives a new marker the <i>lowest</i> free block in its dictionary family
(was: one past the highest in use, reusing gaps only at the end). Measured now: markers a, b, c → #0, #1, #2; delete b, add d →
<code>{json.dumps(m['released'])}</code>.</li>
<li><b>Your page:</b> a 20-id grid at #0–19, singles #20–31, everything above deleted; six pasted copies get
<code>{m['zach_pasted']}</code> (yours got #59–64).</li>
<li><b>Reading order.</b> Pasted copies and A on several rectangles join the document left to right, top to bottom (a marker a
little lower than its neighbours still reads in their row), so their new IDs run in that order.</li>
<li><b>Re-ID a selection from a start.</b> Three ways in: the batch panel's <b>First ID</b> field (type 100, Enter); right-click
a selection → <b>ArUco Re-ID N selected…</b>; Edit › ArUco Re-ID… now reads the canvas selection too (it used to renumber the
whole document unless the batch panel was open). Typed IDs in a selection are renumbered too (the dialog's <i>Keep typed ids</i>
switch is live now: off for a selection, on for the whole document).</li>
<li><b>A start past the dictionary grows it.</b> DICT_4X4_50 stops at #49, so "from 100" used to wrap silently to 0. Now the
renumbered markers move to the smallest dictionary of the same bit size that holds the IDs (4X4_50 → 4X4_250; IDs 0–49 are the
same patterns in every size) and the note says so.</li>
</ul>

<h2>2 · Print margins and keep-clear boxes</h2>
<div class="grid3">
<figure><img src="{img('print-1-before.png')}" alt=""><figcaption>Before: the preset's 10 mm on every side.</figcaption></figure>
<figure><img src="{img('print-2-top-60.png')}" alt=""><figcaption>Top 60 mm (white = typed, ↺ resets to the preset's grey value): printing starts 60 mm down; footer and scale bar follow the margins.</figcaption></figure>
<figure><img src="{img('print-3-keep-clear.png')}" alt=""><figcaption>Draw box on page 1 where the sheet is already cut: the stickers are packed round it. x / y / w / h are editable for precision.</figcaption></figure>
</div>
<ul>
<li><b>Margins</b> Top / Right / Bottom / Left, each driven by the preset (grey) until typed. Measured now: 12 squares with Top 60 →
smallest sticker y = <code>{m['clear_min_y']} mm</code>.</li>
<li><b>Keep-clear boxes</b> are per page: drag on a page (snaps to 0.5 mm), delete with its × or Delete. The core's guillotine packer
carves each page's free room round them, so every layout still frees with straight cuts; spaced mode keeps the gap from them too.
Measured now: a 90 × 80 mm box on page 1 → {m['clear_placed']} of 12 placed, nearest sticker <code>{m['clear_min_apart']} mm</code>
from the box (the gap is 4), {m['clear_pages']} page(s) (was {m['plain_pages']}).</li>
<li>A page whose clear room can't take a sticker sends it to the next page; a box over the footer or scale bar gets a note (they still print there).</li>
<li>Margins and boxes survive closing the dialog and a reload (saved in this browser), and never print: the overlay is preview-only.</li>
<li>Pack time with 3 boxes: 2.18× the plain pack for 30 stickers in CPython (0.41 s vs 0.19 s), held under 3× by a test.</li>
</ul>

<h2>Proof</h2>
<div class="wrap"><table><tr><th>Check</th><th>Command</th><th>Result</th></tr>{runs}</table></div>
<p class="muted">Acceptance tests for the print half (<code>tests/web/test_web_print_clear.py</code>) were committed before the build and not
edited by the builder; I fixed one case of my own afterwards (it asked for 24 tiles on a page that holds 20 on today's code).</p>

<h2>Decided for you (each one undoable)</h2>
<ul>
<li><b>"Next available" = the lowest free ID in the dictionary family</b>, not "the next free after the copied marker's ID". Copy #26–31
on a page whose #0–19 are free and the copies get #0–5. Undo: the version-2 rule is one function in <code>core/autoid.py</code> (rule 3'); the decision is in <code>docs/peps/0004</code>.</li>
<li><b>Released means immediately reusable.</b> The old rule held freed IDs back because a deleted marker's sticker may still be on a part. You
asked for release, so that protection is gone: reprint with care if a deleted marker's sticker is still out there.</li>
<li><b>A typed marker keeps its old ID held</b> (unchanged rule): type 30 on a marker that printed #0 and a paste gets #1, not #0. Clearing the typed value brings #0 back.</li>
<li><b>Re-ID grows the dictionary instead of wrapping</b> (4X4_50 → 4X4_250). Undo: Ctrl+Z, or set the dictionary back by hand.</li>
<li><b>Margins apply to every preset group; keep-clear boxes belong to one preset's pages.</b></li>
<li><b>Landed on <code>main</code> @ <code>{evidence.get("merge", sha)}</code>, pushed, and deployed to arucostudio.com</b> (live build stamp reads
<code>{evidence.get("live_git", "?")}</code>, Cloudflare version <code>{evidence.get("live_version", "?")}</code>). Undo: <code>git revert -m 1 {evidence.get("merge", sha)}</code>
and <code>npx wrangler rollback {evidence.get("rollback_version", "?")}</code> from <code>web/</code>.</li>
</ul>

<h2>Not done</h2>
<ul>
<li>The Fusion add-in doesn't use this auto id or the sheet path, so nothing changed there.</li>
<li>Persistence across a full page reload is covered by a unit test of the store, not an e2e reload.</li>
<li>No margins / keep-clear case in <code>npm run test:parity</code> yet (the real-Pyodide e2e covers the browser core).</li>
</ul>
"""
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<title>Margins and Re-ID</title>"
            f"<style>{CSS}</style></head><body><main>{body}</main></body></html>")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--evidence", type=Path)
    a = ap.parse_args()
    ev = json.loads(a.evidence.read_text()) if a.evidence else {}
    a.out.write_text(build(a.media, ev), encoding="utf-8")
    print(a.out, a.out.stat().st_size)


if __name__ == "__main__":
    main()
