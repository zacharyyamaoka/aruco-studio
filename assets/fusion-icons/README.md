# Fusion add-in icons (ArUco Tags), for the online Studio

These are copied from the cad-exporter branch `claude/aruco-fusion-plugin-0e9bcb` (`ArucoMarkers/resources/`) on 2026-10-21, so the online Studio can match the Fusion add-in. Every file here is drawn by our own scripts, which are in `tools/`. They need Pillow and numpy.

## Not included: the ArUco Extrude command icon

`ArucoMarkers/resources/bamArucoExtrude/` is Fusion's own Extrude icon (Autodesk's PNGs from the local Fusion install) with only the box's top face replaced by a marker. See `tools/make_aruco_icons.py` in cad-exporter. It is Autodesk's artwork, so it must not be published here or on arucostudio.com. The online Studio needs its own drawing of the same idea: a box extruded from a sketch slab, its top face an ArUco marker (DICT_4X4_50 id 7 at 32/64 px, a 3x3 pattern with 2 px cells at 16 px).

## Layout

Each folder follows Fusion's resource convention:

- light theme: `16x16.png`, `16x16@2x.png`, `32x32.png`, `32x32@2x.png`, `64x64.png`;
- dark theme: the same names with `-dark`;
- `NxN@2x` is the 2N design.

### `commands/` (toolbar and timeline)

| Folder | Command |
|---|---|
| bamArucoEdit | ArUco Edit |
| bamArucoExport | ArUco Export |
| bamArucoExportPdf | the PDF type |
| bamArucoExportStl | the STL type |
| bamArucoIds | ArUco Re-ID (was "ArUco IDs") |
| bamArucoIdsLocate | the "show this copy" button |
| bamArucoSendPrusa | Send to PrusaSlicer |
| bamArucoTag | the tag mark |

### `panel/` (dialog rows and dropdown items)

| Prefix | Meaning |
|---|---|
| `single` `grid` `charuco` | marker type |
| `d-*` | dictionary family |
| `k-inkjet` `k-3d` | preset kind: inkjet printer / 3D printer |
| `t-*` | tabs: make, marker, label, inkjet, print, 3d, heights |
| `tr-*` | trim: profile / marker |
| `m-*` | extrude mode: black / white / both / auto |
| `r-*` | size step: dots / mm / lines / custom |
| `cm-*` | corner mark |
| `ls-*` `lsf-*` `lp-*` | label side, surface, place |
| `up-*` `o-*` | turn / origin corner |
| `h-*` | holes: avoid / ignore |
| `newbody` `newcomp` `join` | the Operation row |
| `reset` `warn` `library` `gear` `pin` `start-*` `blank` | misc |

`k-3d` is our own drawing in the style of a 3D printer. It is not Fusion's MAKE icon.
