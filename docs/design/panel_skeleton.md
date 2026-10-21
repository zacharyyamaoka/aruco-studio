# The ArUco Extrude panel skeleton — one order for every shell

Zach, 2026-10-21 (Daily Note, "Aruco studio fusion feedback"): "Conceptually please
align the layout and order of tabs and fields of the aruco studio online to that
which is inside the fusion program … it's fine for the fusion panel and encouraged
for it to look different, but the ordering and layout should be the same, so it's
really kind of like a skeleton change."

This file is that skeleton. The online Studio (`web/src/panel/`) and the Fusion
add-in (`ArucoMarkers/`, cad-exporter) both follow it. Styling, widgets and
spacing may differ per host; the **tabs, their order, the rows in each tab and
their order, and which rows are driven** may not. Change it here first, then in
both shells.

## Tabs (in this order)

| # | Tab | Title shown | Why first / last |
|---|-----|-------------|------------------|
| 1 | **Marker** | "Marker" | "The first thing you do is select the profile, then … decide how to manufacture it. … now I want to be thinking about the marker." |
| 2 | **Label** | "Label" | the text and corner mark |
| 3 | **Make** | always "Make", with the method's icon (inkjet printer / 3D printer) beside it | "if it's a good preset the defaults should be good" — tuned last. WHY a fixed name (Zach 2026-10-21: "keep it just Make so we always know where we should go looking"): tab labels are navigation, they never change with the content |

A new feature opens on **Marker**.

## Rows

Grey = driven (computed or from the preset), with ↺ inside the field once set.
Nothing is an "Auto" checkbox: a driven value is shown grey, typing sets it.

### 1 Marker
1. **Profile** — the selection (a closed region, or a rectangle's outer edges); Fusion adds a Holes pick
2. **Preset** — how it is made (icon: inkjet printer vs 3D printer)
3. **Type** — Single | Grid | ChArUco (icons)
4. **Dictionary**
5. **ID** — driven by auto id ("next"); typed wins
6. **Marker size** — driven; the note under it says how it lands (cells, dots)
7. grid: **Columns × Rows**, **Separation** · ChArUco: **Columns × Rows**, **Checker**, **Origin square**
8. **Suggest** — sets the size rows above it
9. **Turn** (0 / 90 / 180 / 270) · **Rotation** (rectangle profile only)
10. **Quiet zone**
11. **Key** — driven (grey) until typed
(Fusion may fold 10–11 under "Details".)
12. — divider — **Operation** — Fusion only, the LAST row of Marker, where Fusion's own Extrude puts it
    (Zach 2026-10-21: "I have muscle memory expecting it to be there"): New Body | New Component
    (default), with Fusion's own icons (local add-in only, never published). The tag builds in the
    ACTIVE component, root included, like Fusion's Extrude. The online Studio has no components.

### 2 Label
1. **On** — off by default
2. **Text**, **Place**, **Surface**, **Side**, **Height**, **Gap**, **Offset X / Y**
3. — divider —
4. **Corner mark**

### 3 Make
1. **Size step** ("Cells" in Fusion) — Whole printer dots (exact) / 0.1 / 0.5 / 1 mm for
   inkjet; the line width for a 3D print. Never a line-width option on an inkjet preset.
2. **Trim** — Profile (default) | Marker. A driven default still reads as SELECTED.
3. **Heights** — inkjet: Paper thickness · 3D print: Extrude (Black | White | Both),
   White height, Black height (from the white's outer face)
4. **Flip** (outward side)

### Footer (every tab)
The one-line summary ("Single DICT_4X4_50 #3 · 44.0 mm · outer 58.7 × 58.7 mm") and OK / Cancel.

## On the model / canvas

- Dimensions you can drive: marker size; grid separation; ChArUco checker.
- **Outer size: shown as a driven (grey) dimension** — Zach 2026-10-21: "I want to see
  the marker and spacing dimensions here and the outer dimensions as driven."
- The turn / rotate handle shows only on the selected marker.
- Labels drawn on a marker are white (or black on white) like the print; the selection
  colour is the selection's, never the label's.
