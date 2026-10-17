"""The print test's ruler (M6c.2): pdfium rasterises a sticker sheet's PDF
at 600 dpi and the 100 mm and 4 in bars are measured along their own rows,
with the same code as the WYSIWYG check (aruco_studio.verify.sheet_check).

    python -I -B e2e/bars.py <sheet.pdf> <ruler.json>

`ruler.json` is GET /api/scene/sheet.json's `ruler` ({"mm_bar": [x, y, w, h],
"in_bar": [...]}, mm). Prints JSON: {"pages": [{"mm_bar": 100.0, "in_bar":
101.6}, ...], "dpi": 600}."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from aruco_studio.verify import sheet_check as SC  # noqa: E402


def main(argv):
    pdf = open(argv[0], "rb").read()
    ruler = json.load(open(argv[1], encoding="utf-8"))
    s = SC.DPI / 25.4
    pages = []
    for img in SC.rasterise(pdf, SC.DPI):
        mm = SC.bar_mm(img, ruler["mm_bar"], s)
        inch = SC.bar_mm(img, ruler["in_bar"], s)
        pages.append({"mm_bar": None if mm is None else round(mm, 4), "in_bar": None if inch is None else round(inch, 4)})
    print(json.dumps({"pages": pages, "dpi": SC.DPI}))


if __name__ == "__main__":
    main(sys.argv[1:])
