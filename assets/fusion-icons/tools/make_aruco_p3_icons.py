"""The P3 ArUco Extrude dialog's new icons (2026-10-17), drawn with the same
painter and the same look as tools/make_aruco_ui_icons.py; only the folders
below are written (the v2 set is left as it is).

    python tools/make_aruco_p3_icons.py

- t-3d       the "3D print" tab: v2's printer icon (t-print)
- t-make     the single "Make" tab (P3_MAKE_TABS = "one"): the same
- t-inkjet   the "Inkjet" tab: a sheet with a printed marker and dots
- k-3d       a 3D printer preset in the Preset list: the report's cube
- k-inkjet   an Inkjet (sticker) preset: the sheet
- r-dots     Cells = whole printer dots
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("make_aruco_ui_icons",
                                               ROOT / "tools" / "make_aruco_ui_icons.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

SHEET = ('<path d="M3 1.5h7l3 3v10H3z" fill="#dfe5ec" stroke="currentColor"/>'
         '<path d="M10 1.5v3h3" fill="none" stroke="currentColor"/>'
         '<rect x="5" y="6" width="5" height="5" fill="#14171c"/>'
         '<rect x="6.2" y="7.2" width="1.3" height="1.3" fill="#dfe5ec"/>'
         '<rect x="7.6" y="8.6" width="1.3" height="1.3" fill="#dfe5ec"/>'
         '<path d="M5 13h1M7 13h1M9 13h1" stroke="#38a6e8" stroke-width="1"/>')
DOTS = "".join(f'<circle cx="{x}" cy="{y}" r="0.9" fill="currentColor"/>'
               for x in (3.5, 6.5, 9.5, 12.5) for y in (3.5, 6.5, 9.5, 12.5)) + \
    '<rect x="5" y="5" width="6" height="6" fill="none" stroke="#38a6e8" stroke-width="1"/>'


def main():
    syms = B.symbols()
    want = {"t-3d": syms["t-print"], "t-make": syms["t-print"], "t-inkjet": SHEET,
            "k-3d": syms["cube"], "k-inkjet": SHEET, "r-dots": DOTS}
    for name, body in want.items():
        d = B.OUT / name
        d.mkdir(parents=True, exist_ok=True)
        for suffix, fg in B.THEMES.items():
            for stem, px in B.FILES:
                base, _, x2 = stem.partition("@")
                fname = f"{base}{suffix}{'@' + x2 if x2 else ''}.png"
                B.render(body, px, fg).save(d / fname)
    print(f"{len(want)} icon folders in {B.OUT}: {', '.join(want)}")


if __name__ == "__main__":
    main()
