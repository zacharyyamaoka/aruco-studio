# N-3: the gallery of golden examples (lane/gallery, 2026-10-17)

Zach's ask N-3 (`docs/feedback/2026-10-17-markers-core-first.md`): the Studio shows golden examples that demonstrate every feature, the inputs drawn for the user; it stops being a place where users draw their own geometry (CF-12).

## What was built

| Part | Where |
|---|---|
| The gallery, the landing page: cards grouped by feature, markers first; each card a thumbnail drawn from the example's real plan (`POST /api/design/preview`, the 2D canvas's own `TagSvg`), a title, one line | `studio/src/gallery/Gallery.tsx`, `model.ts` |
| A card opens a fresh copy in `<home>/gallery/` and the Studio shows it, the first tag selected; the note over the canvas: what to look at, the example's buttons (3D view, Sticker sheet…, Send…, Renumber all), Start over, previous / next, Gallery. The inspector stays: change a number, the copy re-plans. The example file is never written | `studio/src/store.ts` (`openGallery`, `showGallery`), `Gallery.tsx` (`ExampleNote`) |
| The examples: 18 design files and their manifest (group, title, line, what to look at, buttons) | `examples/gallery/*.arucostudio.json`, `examples/gallery/gallery.json` |
| Two routes, listing and opening only | `GET /api/gallery`, `POST /api/gallery/open` (`aruco_studio/server/gallery_api.py`; files through `server/store.py`; one import line in `app.py`) |
| The way back | the top bar's Gallery button, File › Gallery…, S › "Gallery", Open… › Examples › The gallery (first in the list); `#gallery`, `#studio`, `#example=<name>` in the URL (a reload keeps the example and its note) |

## The examples

| Group | Example | Shows |
|---|---|---|
| Markers by hand | `basics_single` | Single, Marker size typed 30 → 28.56 mm (whole 0.68 mm lines); the 38.1 mm tile; the 50 mm plate trimmed to it |
| | `basics_grid` | Grid, 3 × 2 at 12.24 mm typed on a sketch profile (the count kept); board 46.2 × 31.3 mm, the plate trimmed |
| | `basics_charuco` | ChArUco, checker 16.32, marker 12.24, 4 × 3; board 65.3 × 49.0 mm, the plate trimmed |
| Made two ways | `two_ways` | the same 30 mm single: 3D printer (28.56 mm) and Letter 600 dpi sticker (29.97 mm, cut line) |
| IDs | `ids` | seven tags made without ids (all #0, 6 duplicates): Renumber all gives one numbering to 3D tags and stickers; DICT_6X6 keeps its own #0 |
| Auto-placement on profiles | `faces` | Auto on Zach's Ø53 disc with four holes (37.4 mm clear square), a D-shape, an L, a plate with a hole |
| | `faces_boards` | boards on a ring, a hexagon, a slot, a notched plate, a strip, a triangle |
| | `holes` | Avoid vs Ignore: 24.48 → 32.64 mm, 12.24 → 24.48 mm, ChArUco 2 × 4 → 4 × 3; the covered hole dashed |
| | `angles` | the fit at 0° / 90° (4 × 1 on a wide plate, 1 × 4 on a tall one) and Origin 0 / 90 |
| Labels | `labels_where` | on the black (rule 5: 3.74 mm letters need a 7.48 mm module), on the white below / right, stickers on the black and on the white |
| | `labels_place` | Auto (black refused, white, with the reason), Above with `#id + name`, Placed by hand X / Y |
| | `labels_charuco` | a ChArUco label in a black square: Auto, and by hand in another square |
| Corner marks | `marks` | None, Cut white corner, Black triangle; a grid and a ChArUco with the triangle |
| Trim and Perimeter | `trim` | a 3D plate with Trim excess off / on; stickers on the disc with Perimeter Profile / Marker |
| Multi-face | `forearm` | one ArUco Extrude on four faces of a 120 × 40 × 40 box, the 2D net, the 3D view |
| The sticker sheet | `sheet_tight`, `sheet_spaced` | five stickers, the sheet dialog opens Tight or Spaced |
| PrusaSlicer | `send` | four 3D tags; Send to PrusaSlicer… opens from the note |

Every example plans with no error-level message (`tests/server/test_gallery_api.py`, `e2e/tests/gallery.spec.ts`). Warnings shown on purpose: Auto's cell minimum on the small odd faces and the forearm's 40 mm sides, the 3-corner ChArUco on the hexagon and beside the hole, "the tile covers 1 hole" under Ignore, the Auto label's "not on the black".

## Hidden, not deleted

The shape-drawing tools (Rectangle R, Circle C, Polygon P, Slot O, Hole H, Rectangular hole Shift+H): their bottom-bar buttons, keys, palette rows and the empty canvas's hint. The code is unchanged and frozen. **`?draw=1`** (http://127.0.0.1:5360/?draw=1) brings all of it back and starts on the canvas (`studio/src/app/flags.ts`). Select, Extrude (E), ArUco Extrude (A), the handles, the inspector's shape rows (size, holes, height) and the palette's "ArUco: single / grid / ChArUco" stay: they change the inputs drawn for you. The older e2e tests run with `?draw=1` (`e2e/tests/helpers.ts` `STUDIO_URL`).

## Checks

`.venv/Scripts/python tools/check.py` on lane/gallery, 2026-10-17 10:15-10:26, on ports 5384 / 5385 (`ARUCO_STUDIO_API_PORT` / `_UI_PORT`: 5370 is Zach's preview and was left alone; nothing listened on 5384 / 5385 before or after). **OK in 648 s**, exit 0:

| Group | Result |
|---|---|
| adapters | 97 passed in 40 s |
| core | 7,387 passed, 4 skipped in 41 s |
| plan | 544 passed in 116 s |
| scene | 43 passed in 13 s |
| server | 100 passed in 21 s (main's 97 + the gallery's 3) |
| verify | 120 passed in 97 s |
| studio | build + vitest passed in 11 s (vitest 47: main's 44 + 3) |
| e2e | 58 passed, 1 skipped (5.1 m) in 309 s: main's 52 (the older specs now open `/?draw=1`), the gallery's 6; the skip is `gallery_shots.spec.ts` (only with `ARUCO_GALLERY_SHOTS=1`) |

The e2e run rewrote `reports/screens/*.png` as every full check does; those were put back, only `reports/screens/gallery_landing.png` is new.

New tests: `tests/server/test_gallery_api.py` (3), `studio/src/gallery/model.test.ts` (3), `e2e/tests/gallery.spec.ts` (6: the landing page and every thumbnail; every example opened, planned with no error, 2D / 3D, the examples unwritten, no console error; a copy's change, Start over, the note's buttons, a reload; the tools hidden and the palette; `?draw=1`; Open, the File drawer, the recent list). `e2e/tests/gallery_shots.spec.ts` writes the pictures below only with `ARUCO_GALLERY_SHOTS=1`.

## Screenshots

`docs/status/gallery_landing_{light,dark}.png`, `gallery_faces_2d_*`, `gallery_labels_charuco_2d_*`, `gallery_forearm_3d_*` (1500 × 900, the dev servers, the fixture printers).

## Could not be shown (not in today's core)

| Feature | Why |
|---|---|
| CF-4's new preset fields (first-layer width, bed size, face-down cells by the first layer) | not built (N-2 designs them) |
| CF-6, the size lint (oversize flagged red) | not built; the sheet dialog's rejected list is the nearest |
| CF-7, a sticker as paper thickness with the black t/2 inside | not built: a sticker is stock + ink on top |
| CF-8, flush-only and Flip | not built |
| CF-12, a sketch from another program (a DXF from Fusion) | no importer; a `loops` shape is what one would write |
| A typed Columns × rows on a face | REF's fit lays out as many as fit (audit B10); the basics use a sketch profile (`over`), which keeps the count |

## Found on the way (fixed on lane/scene-fixes, 2026-10-17)

1. **Renumber all resets typed ids to 0.** Open `examples/sticker_sheet` (typed `first_id`s), Renumber all: `overrides` keeps `{t1: 0, t2: 1, t3: 2, t4: 8}` but the tags plan as #0, #0, #0-5, #0-3. The write-back drops each `first_id` (it moves into `overrides`) and leaves the feature as sugar without `numbers`, and the compile does not apply `overrides` to `marker_id`. The `ids` example avoids typed ids for this reason. (`aruco_studio/scene/design.py`.) **Fixed:** the write-back writes a feature exact when its `first_id` moves into `overrides`, and a tag whose numbers are still sugar takes its first id from `overrides` (so a file the old write-back left plans its ids again); tests `tests/scene/test_typed_ids.py`, `tests/server/test_scene_fixes_api.py`, e2e `ids.spec.ts`.
2. **`perimeter` sugar on a 3D tag had no effect** (`basics_*` and `trim` carried exact `settings` instead): `_sugar` writes `s["trim"] = "both" if profile else "off"`; the plan reads neither, and the mapping is the M6 note's inverse (Marker = Trim both). **Fixed:** on a 3D printed tag `marker` writes the Inspector's Trim excess `{rule 1, axes both, margin 0, force false}` and `profile` none; a sticker keeps `make.perimeter`. `basics_*` and `trim` type `perimeter` again, their plans unchanged; tests `tests/scene/test_perimeter_sugar.py`, `tests/server/test_scene_fixes_api.py`.

## Questions for Zach

1. A card opens a fresh copy every time (your changes go; Save as… keeps them). Should it reopen your last copy instead?
2. The three older examples (`forearm`, `plate_charuco`, `sticker_sheet`) stay in Open… for the tests that use them; retire them into the gallery?
