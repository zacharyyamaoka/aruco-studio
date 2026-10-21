"""The ArUco Extrude icon (our own drawing; Fusion's is Autodesk's Extrude): a box extruded from a thin
sketch slab, its top face an ArUco marker. Plan-oblique: the top face is a
true square (so the marker's cells land on whole pixels), the verticals go
down-left. Writes extrude-16.svg (pixel-tuned, a 3x3 pattern of 2 px cells)
and extrude-32.svg (DICT_4X4_50 #7, 3 px cells; drawn at 64 px too)."""
import sys, pathlib

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).parent)
# DICT_4X4_50 id 7, 1 = white (cv2.aruco.generateImageMarker, inner 4x4)
ID7 = [[1, 1, 0, 0], [0, 1, 0, 0], [1, 1, 1, 1], [0, 0, 1, 0]]
# 16 px: an irregular 3x3 (#7's own cells read as a "1" at this size)
P3 = [[1, 1, 0], [0, 1, 1], [1, 0, 0]]

SLAB_TOP, SLAB_SIDE, SLAB_EDGE = "#a9cff5", "#5d9fe2", "#2a7fd4"
RIM, LEFT, FRONT, EDGE, BLACK, WHITE = "#eef1f4", "#b3bbc6", "#838c99", "#4a5262", "#15181c", "#ffffff"


def poly(pts, fill, stroke=None, sw=0):
    p = " ".join(f"{x:g},{y:g}" for x, y in pts)
    s = f' stroke="{stroke}" stroke-width="{sw:g}" stroke-linejoin="round"' if stroke and sw else ""
    return f'<polygon points="{p}" fill="{fill}"{s}/>'


def rect(x, y, w, h, fill):
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}" shape-rendering="crispEdges"/>'


def icon(top, shear, slab, thick, cells, rim, border, cell, sw):
    """top = (x0, y0, side) of the top face (rim included); shear = the box
    height as a down-left offset; slab = (x0, y0, x1, y1) of the slab's plan;
    cells = the white (1) / black pattern inside the marker's black border."""
    x0, y0, s = top
    d = shear
    sx0, sy0, sx1, sy1 = slab
    out = [
        # the slab: its thickness along the bottom and the left, then its top
        poly([(sx0, sy1), (sx1, sy1), (sx1 - thick, sy1 + thick), (sx0 - thick, sy1 + thick)], SLAB_SIDE),
        poly([(sx0, sy0), (sx0, sy1), (sx0 - thick, sy1 + thick), (sx0 - thick, sy0 + thick)], SLAB_SIDE),
        poly([(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)], SLAB_TOP, SLAB_EDGE, sw),
        # the box: the left face, the front face, then the top face
        poly([(x0, y0), (x0, y0 + s), (x0 - d, y0 + s + d), (x0 - d, y0 + d)], LEFT, EDGE, sw),
        poly([(x0, y0 + s), (x0 + s, y0 + s), (x0 + s - d, y0 + s + d), (x0 - d, y0 + s + d)], FRONT, EDGE, sw),
        rect(x0, y0, s, s, RIM),
    ]
    # the marker: black, a border, the pattern
    mx, my, side = x0 + rim, y0 + rim, s - 2 * rim
    out.append(rect(mx, my, side, side, BLACK))
    for r, row in enumerate(cells):
        for k, v in enumerate(row):
            if v:
                out.append(rect(mx + border + cell * k, my + border + cell * r, cell, cell, WHITE))
    return out


def svg(size, body):
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
    return head + "".join(body) + "</svg>\n"


# 16 px: top face 10 px (a 1 px rim, black 8 = border 1 + 3 x 2 px cells + 1), box 3 px tall
b16 = icon((5, 0, 10), 3, (1, 2, 15, 15), 1, P3, 1, 1, 2, 0)
# 32 px: top face 20 px (a 1 px rim, black 18 = 6 x 3 px cells), box 6 px tall
b32 = icon((11, 0, 20), 6, (2, 4, 30, 30), 2, ID7, 1, 3, 3, 0.75)
(OUT / "extrude-16.svg").write_text(svg(16, b16))
(OUT / "extrude-32.svg").write_text(svg(32, b32))
print("ok")
