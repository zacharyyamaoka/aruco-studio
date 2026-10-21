"""The ArUco Extrude v2 dialog's small icons, from the report's own SVG set.

    python tools/make_aruco_ui_icons.py          # PNG folders + icons.js + a preview sheet

Zach saw (and chose from) the mock-ups in reports/aruco/fusion-ui-language.html;
their icons are inline SVG <symbol>s there (viewBox 0 0 16 16). This script
reads those symbols, so the dialog's icons ARE the mock-ups' icons:

- ArucoMarkers/resources/ui/<name>/ : Fusion's resource-folder PNGs for list
  items, button rows and tabs -- 16x16.png 16x16@2x.png 32x32.png
  32x32@2x.png and the same with -dark (currentColor = Fusion's light / dark
  UI text grey; NxN@2x is the 2N design, as in Fusion's own folders);
- ArucoMarkers/resources/preset_library/icons.js : window.BAM_ICONS = {name:
  inner svg}, currentColor kept (the library page colours them by CSS);
- reports/media/aruco/icons/aruco_ui_icons_preview.png : every icon at 1x and
  4x on Fusion's light and dark greys.

A few icons are adjusted or added here (EXTRA, ADJUST): the white tile of
the Extrude icons gets a grey outline so it reads on a light theme, and
Start (From face / Offset) is new.

How: a tiny SVG painter (path M/L/H/V/C/S/Z absolute and relative, rect,
circle; fill, stroke, stroke-width, fill-opacity, opacity, fill-rule) drawn
8x oversize with Pillow and box-filtered down (exact area coverage). Needs
Pillow (the clank-viser venv).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "aruco" / "fusion-ui-language.html"
OUT = ROOT / "ArucoMarkers" / "resources" / "ui"
JS = ROOT / "ArucoMarkers" / "resources" / "preset_library" / "icons.js"
PREVIEW = ROOT / "reports" / "media" / "aruco" / "icons" / "aruco_ui_icons_preview.png"

# the icons the dialog uses (resource folders) -- names as in the report, no "i-"
DIALOG = ["single", "grid", "charuco", "m-auto", "m-wb", "m-black", "m-white", "join", "newbody",
          "cm-none", "cm-cut", "cm-tri", "o-tl", "o-tr", "o-br", "o-bl", "up-t", "up-r", "up-b",
          "up-l", "r-lines", "r-mm", "r-custom", "t-marker", "t-heights", "t-print", "t-label",
          "gear", "library", "pin", "start-face", "start-offset", "warn", "blank"]
# the library page's (inline SVG only)
PAGE = ["plus", "dup", "pencil", "import", "export", "trash", "search", "filter", "close",
        "check", "warn", "clock", "doc", "folder", "star", "cube", "library", "nozzle",
        "layers", "single", "grid", "charuco"]

TILE = 'stroke="#8b95a3" stroke-width=".8"'
ADJUST = {
    # the white tile outlined, so it shows on Fusion's light grey too
    "m-wb": ('<rect x="1.5" y="6" width="13" height="7.5" fill="#dfe5ec"/>',
             f'<rect x="1.5" y="6" width="13" height="7.5" fill="#dfe5ec" {TILE}/>'),
    "m-white": ('<rect x="4" y="6" width="8" height="2.6" fill="#dfe5ec"/>',
                f'<rect x="4" y="6" width="8" height="2.6" fill="#dfe5ec" {TILE}/>'),
    "t-heights": ('<rect x="1.5" y="9" width="13" height="5" fill="#dfe5ec"/>',
                  f'<rect x="1.5" y="9" width="13" height="5" fill="#dfe5ec" {TILE}/>'),
    "pin": ('fill="#dfe5ec" stroke="currentColor"', 'fill="#dfe5ec" stroke="currentColor"'),
}
EXTRA = {
    # transparent: an item with no icon of its own in a list whose others
    # have one (Fusion refuses icon-less items among icon ones)
    "blank": "",
    # Start, like Extrude's: the slabs start at the face / at an offset from it
    "start-face": ('<path d="M1.5 12.5h13" stroke="#38a6e8" stroke-width="1.6"/>'
                   f'<rect x="3.5" y="6.5" width="9" height="5.5" fill="#dfe5ec" {TILE}/>'
                   '<rect x="5.5" y="6.5" width="5" height="2" fill="#14171c"/>'),
    "start-offset": ('<path d="M1.5 13.5h13" stroke="#38a6e8" stroke-width="1.6"/>'
                     '<path d="M2.5 13V9.5M1.2 10.8 2.5 9.5l1.3 1.3" fill="none" '
                     'stroke="currentColor" stroke-width="1"/>'
                     f'<rect x="5" y="3.5" width="8.5" height="5" fill="#dfe5ec" {TILE}/>'
                     '<rect x="7" y="3.5" width="4.5" height="1.8" fill="#14171c"/>'),
}

THEMES = {"": (61, 65, 72), "-dark": (214, 218, 224)}       # currentColor per theme
BG = {"": (242, 242, 242), "-dark": (55, 59, 66)}            # the preview's backgrounds
SS = 8                                                       # oversampling


def symbols():
    t = REPORT.read_text(encoding="utf-8")
    out = {}
    for sid, vb, body in re.findall(r'<symbol id="i-([^"]+)" viewBox="([^"]+)">(.*?)</symbol>',
                                    t, re.S):
        if vb.strip() != "0 0 16 16":
            continue
        out[sid] = body
    for name, (old, new) in ADJUST.items():
        if name in out:
            out[name] = out[name].replace(old, new)
    out.update(EXTRA)
    return out


# ------------------------------------------------------------ the SVG painter

TOK = re.compile(r"[MmLlHhVvCcSsZz]|-?(?:\d+\.\d*|\.\d+|\d+)(?:[eE]-?\d+)?")


def _bez(p0, p1, p2, p3, n=12):
    return [tuple((1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * p1[k] + 3 * (1 - t) * t * t * p2[k]
                  + t ** 3 * p3[k] for k in range(2)) for t in (i / n for i in range(1, n + 1))]


def parse_path(d):
    """-> [(points, closed)] subpaths in user units."""
    toks = TOK.findall(d)
    i, cmd = 0, None
    cur, start, last_c2 = (0.0, 0.0), (0.0, 0.0), None
    subs, pts = [], []

    def num():
        nonlocal i
        v = float(toks[i])
        i += 1
        return v
    while i < len(toks):
        if re.fullmatch(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if pts:
                    subs.append((pts, True))
                pts, cur, last_c2 = [], start, None
                continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            x, y = num(), num()
            if rel:
                x, y = cur[0] + x, cur[1] + y
            if pts:
                subs.append((pts, False))
            cur = start = (x, y)
            pts = [cur]
            cmd = "l" if rel else "L"                # further pairs are lines
            last_c2 = None
        elif c == "L":
            x, y = num(), num()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            pts.append(cur)
            last_c2 = None
        elif c == "H":
            x = num()
            cur = (cur[0] + x if rel else x, cur[1])
            pts.append(cur)
            last_c2 = None
        elif c == "V":
            y = num()
            cur = (cur[0], cur[1] + y if rel else y)
            pts.append(cur)
            last_c2 = None
        elif c in "CS":
            if c == "C":
                c1 = (num(), num())
                if rel:
                    c1 = (cur[0] + c1[0], cur[1] + c1[1])
            else:
                c1 = (2 * cur[0] - last_c2[0], 2 * cur[1] - last_c2[1]) if last_c2 else cur
            c2, p = (num(), num()), (num(), num())
            if rel:
                c2 = (cur[0] + c2[0], cur[1] + c2[1])
                p = (cur[0] + p[0], cur[1] + p[1])
            pts += _bez(cur, c1, c2, p)
            cur, last_c2 = p, c2
        else:
            raise ValueError(f"path command {cmd} not supported")
    if pts:
        subs.append((pts, False))
    return subs


def _colour(v, fg):
    if v in (None, "none"):
        return None
    if v == "currentColor":
        return fg
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))
    return {"black": (0, 0, 0), "white": (255, 255, 255)}.get(v, (0, 0, 0))


def _attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))


def render(body, size, fg):
    """One icon (inner SVG, viewBox 16) -> an RGBA image size x size."""
    big = size * SS
    k = big / 16.0
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    for tag in re.findall(r"<(?:path|rect|circle)\b[^>]*/?>", body):
        a = _attrs(tag)
        kind = re.match(r"<(\w+)", tag).group(1)
        fill = _colour(a.get("fill", "#000"), fg)
        stroke = _colour(a.get("stroke"), fg)
        sw = float(a.get("stroke-width", "1")) * k
        op = float(a.get("opacity", "1"))
        fop = float(a.get("fill-opacity", "1")) * op
        sop = float(a.get("stroke-opacity", "1")) * op
        if kind == "rect":
            x, y = float(a.get("x", 0)), float(a.get("y", 0))
            w, h = float(a["width"]), float(a["height"])
            subs = [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)]
        elif kind == "circle":
            cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
            n = 64
            subs = [([(cx + r * math.cos(2 * math.pi * j / n), cy + r * math.sin(2 * math.pi * j / n))
                      for j in range(n)], True)]
        else:
            subs = parse_path(a["d"])
        if fill is not None:
            mask = Image.new("L", (big, big), 0)
            for pts, _closed in subs:
                if len(pts) < 3:
                    continue
                m = Image.new("L", (big, big), 0)
                ImageDraw.Draw(m).polygon([(p[0] * k, p[1] * k) for p in pts], fill=255)
                mask = (ImageChops.difference(mask, m) if a.get("fill-rule") == "evenodd"
                        else ImageChops.lighter(mask, m))
            _paint(img, mask, fill, fop)
        if stroke is not None and sw > 0:
            mask = Image.new("L", (big, big), 0)
            dr = ImageDraw.Draw(mask)
            for pts, closed in subs:
                q = [(p[0] * k, p[1] * k) for p in pts]
                if closed:
                    q = q + [q[0], q[1] if len(q) > 1 else q[0]]
                if len(q) >= 2:
                    dr.line(q, fill=255, width=max(1, int(round(sw))), joint="curve")
            _paint(img, mask, stroke, sop)
    return img.resize((size, size), Image.BOX)


def _paint(img, mask, rgb, alpha):
    if alpha < 1.0:
        mask = mask.point(lambda v: int(v * alpha))
    layer = Image.new("RGBA", img.size, rgb + (255,))
    layer.putalpha(mask)
    img.alpha_composite(layer)


FILES = [("16x16", 16), ("16x16@2x", 32), ("32x32", 32), ("32x32@2x", 64)]


def main():
    syms = symbols()
    missing = [n for n in set(DIALOG + PAGE) if n not in syms]
    if missing:
        raise SystemExit(f"icons missing from the report: {missing}")
    for name in DIALOG:
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        for suffix, fg in THEMES.items():
            for stem, px in FILES:
                base, _, x2 = stem.partition("@")          # 16x16@2x -> 16x16-dark@2x
                fname = f"{base}{suffix}{'@' + x2 if x2 else ''}.png"
                render(syms[name], px, fg).save(d / fname)
    JS.parent.mkdir(parents=True, exist_ok=True)
    page = {n: syms[n] for n in sorted(set(PAGE + DIALOG))}
    JS.write_text("// generated by tools/make_aruco_ui_icons.py from the report's icon set\n"
                  "window.BAM_ICONS = " + json.dumps(page, indent=0) + ";\n", encoding="utf-8")
    # the preview: every dialog icon at 1x and 4x, light then dark
    cols = 6
    rows = -(-len(DIALOG) // cols)
    cell = 120
    sheet = Image.new("RGB", (cols * cell * 2, rows * cell), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    for t, (suffix, fg) in enumerate(THEMES.items()):
        for i, name in enumerate(DIALOG):
            x0 = t * cols * cell + (i % cols) * cell
            y0 = (i // cols) * cell
            dr.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=BG[suffix])
            small = render(syms[name], 16, fg)
            sheet.paste(small, (x0 + 8, y0 + 8), small)
            big = render(syms[name], 64, fg)
            sheet.paste(big, (x0 + 40, y0 + 8), big)
            dr.text((x0 + 6, y0 + cell - 22), name, fill=fg)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(PREVIEW)
    print(f"{len(DIALOG)} icon folders in {OUT}; {len(page)} page icons in {JS}; preview {PREVIEW}")


if __name__ == "__main__":
    main()
