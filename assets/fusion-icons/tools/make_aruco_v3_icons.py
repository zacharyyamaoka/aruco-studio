"""The ArUco Extrude panel v3's list-item icons (Zach 2026-10-20: "Fusion-style
icons in the dropdown items", like Fillet's Type list).

    python tools/make_aruco_v3_icons.py        # PNG folders + a preview sheet

The icons the v2 dialog already has are reused (single / grid / charuco,
m-wb / m-black / m-white, cm-none / cm-tri, k-inkjet / k-3d, library); the
ones its lists lacked are drawn here in the same language -- 16 x 16 SVG,
currentColor = Fusion's text grey, the blue #38a6e8 for what the item is
about, a marker as a dark square -- with tools/make_aruco_ui_icons.py's
painter (8x oversampled, box-filtered), into ArucoMarkers/resources/ui/<name>/
(16x16 / 32x32, @2x, -dark). Needs Pillow.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_aruco_ui_icons as U  # noqa: E402

OUT = ROOT / "ArucoMarkers" / "resources" / "ui"
PREVIEW = ROOT / "reports" / "media" / "aruco" / "icons" / "aruco_v3_icons_preview.png"

BLUE = "#38a6e8"
MARK = "#14171c"
PAPER = 'fill="#dfe5ec" stroke="#8b95a3" stroke-width=".8"'


def _sq(x, y, w, h=None):
    h = w if h is None else h
    return f"M{x:.3f} {y:.3f}h{w:.3f}v{h:.3f}h{-w:.3f}z"


def _marker(x, y, s, fill="currentColor"):
    """A small marker (currentColor, like the v2 "single"): a square with a
    cell cut out of it (evenodd: it reads on Fusion's light and dark greys)."""
    c = s * 0.36
    return (f'<path fill-rule="evenodd" fill="{fill}" d="{_sq(x, y, s)}'
            f'{_sq(x + s * 0.32, y + s * 0.32, c)}"/>')


def _cells(n):
    """A marker of n x n bits: its border and a checker of n x n cells cut
    out of it."""
    x0, s = 2.0, 12.0
    cell = s / (n + 2)
    d = _sq(x0, x0, s)
    for i in range(n):
        for j in range(n):
            if (i + j) % 2 == 0:
                d += _sq(x0 + cell * (i + 1), x0 + cell * (j + 1), cell)
    return f'<path fill-rule="evenodd" fill="currentColor" d="{d}"/>'


def _label_bar(x, y, w, h):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{BLUE}" '
            f'stroke-width="1.1"/>')


ICONS = {
    # Trim: what the sticker is cut to
    "tr-profile": (f'<path d="M1.5 3.5h9l4 4v6h-13z" {PAPER}/>'
                   f'<path d="M1.5 3.5h9l4 4v6h-13z" fill="none" stroke="{BLUE}" stroke-width="1.2" '
                   '/>' + _marker(4, 6.5, 5, MARK)),
    "tr-marker": (f'<path d="M1.5 3.5h9l4 4v6h-13z" fill="none" stroke="currentColor" opacity=".45"/>'
                  f'<rect x="3" y="5" width="8" height="8" {PAPER}/>'
                  f'<rect x="3" y="5" width="8" height="8" fill="none" stroke="{BLUE}" '
                  'stroke-width="1.2"/>' + _marker(4.5, 6.5, 5, MARK)),
    # Holes: keep the marker clear of a hole, or not
    "h-avoid": (f'<rect x="1.5" y="3" width="13" height="10" {PAPER}/>'
                '<circle cx="11" cy="8" r="2.2" fill="none" stroke="currentColor"/>'
                + _marker(3, 5, 5.5, MARK)),
    "h-ignore": (f'<rect x="1.5" y="3" width="13" height="10" {PAPER}/>'
                 + _marker(5, 4.5, 7, MARK) +
                 f'<circle cx="8.5" cy="8" r="2.2" fill="none" stroke="{BLUE}" stroke-width="1.1"/>'),
    # Dictionary: the marker's bits
    "d-4": _cells(4),
    "d-5": _cells(5),
    "d-6": _cells(6),
    "d-7": _cells(7),
    "d-april": (f'<path fill-rule="evenodd" fill="currentColor" d="{_sq(2, 2, 12)}{_sq(4, 4, 8)}"/>'
                f'<path fill-rule="evenodd" fill="currentColor" d="{_sq(5.6, 5.6, 4.8)}'
                f'{_sq(7.2, 7.2, 1.6)}"/>'),
    # Label side: where the label sits beside the marker
    "ls-below": _marker(4.5, 1.5, 7) + _label_bar(3, 10.5, 10, 3.5),
    "ls-above": _label_bar(3, 1.5, 10, 3.5) + _marker(4.5, 7.5, 7),
    "ls-left": _label_bar(1.2, 6.2, 5, 3.6) + _marker(7.5, 4.5, 7),
    "ls-right": _marker(1.5, 4.5, 7) + _label_bar(9.8, 6.2, 5, 3.6),
    # Operation: New Component (a component box holding the marker) -- New Body is v2's
    "newcomp": ('<path d="M2 5.2 8 2l6 3.2v6.6L8 15l-6-3.2z" fill="none" stroke="currentColor"/>'
                '<path d="M2 5.2 8 8.4l6-3.2M8 8.4V15" fill="none" stroke="currentColor" '
                'opacity=".55"/>'
                f'<path fill-rule="evenodd" fill="{BLUE}" d="{_sq(3.6, 7.4, 3.4)}{_sq(4.8, 8.6, 1.1)}"/>'),
    # Label place: on the marker (its border / quiet zone) or outside it
    "lp-on": (f'<path fill-rule="evenodd" fill="currentColor" d="{_sq(2, 2, 12)}{_sq(4.5, 4.5, 4)}"/>'
              f'<path d="M4 12.2h8" stroke="{BLUE}" stroke-width="1.4"/>'),
    "lp-out": _marker(3.5, 1.5, 9) + _label_bar(3, 12, 10, 2.8),
    # Label surface on the marker: knocked out of the black, or on the white
    "lsf-black": (f'<rect x="1.5" y="4" width="13" height="8" fill="{MARK}" stroke="#8b95a3" '
                  'stroke-width=".8"/>'
                  '<path d="M4 10 5.8 6h.8L8.4 10M4.6 8.8h3.2M9.6 6v4h2.4" fill="none" '
                  'stroke="#f4f6f8" stroke-width="1.1"/>'),
    "lsf-white": (f'<rect x="1.5" y="4" width="13" height="8" {PAPER}/>'
                  '<path d="M4 10 5.8 6h.8L8.4 10M4.6 8.8h3.2M9.6 6v4h2.4" fill="none" '
                  f'stroke="{MARK}" stroke-width="1.1"/>'),
}


def main():
    for name, body in ICONS.items():
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        for suffix, fg in U.THEMES.items():
            for stem, px in U.FILES:
                base, _, x2 = stem.partition("@")
                fname = f"{base}{suffix}{'@' + x2 if x2 else ''}.png"
                U.render(body, px, fg).save(d / fname)
    cols, cell = 6, 120
    names = list(ICONS)
    rows = -(-len(names) // cols)
    sheet = Image.new("RGB", (cols * cell * 2, rows * cell), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    for t, (suffix, fg) in enumerate(U.THEMES.items()):
        for i, name in enumerate(names):
            x0 = t * cols * cell + (i % cols) * cell
            y0 = (i // cols) * cell
            dr.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=U.BG[suffix])
            small = U.render(ICONS[name], 16, fg)
            sheet.paste(small, (x0 + 8, y0 + 8), small)
            big = U.render(ICONS[name], 64, fg)
            sheet.paste(big, (x0 + 40, y0 + 8), big)
            dr.text((x0 + 6, y0 + cell - 22), name, fill=fg)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(PREVIEW)
    print(f"{len(ICONS)} icon folders in {OUT}; preview {PREVIEW}")


if __name__ == "__main__":
    main()
