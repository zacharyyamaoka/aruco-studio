# ArUco Studio: the web app

The Studio shows the core's features on golden examples. **It opens on the gallery** (Zach's N-3, 2026-10-17): the examples, the inputs drawn for you, grouped by feature, markers first. A card opens a copy; change any number in the inspector and watch the plan follow. The Studio is no longer a sketcher (CF-12): the shape-drawing tools (Rectangle, Circle, Polygon, Slot, Hole, Rectangular hole) are hidden, frozen, behind the dev flag `?draw=1`. **The design file is the model** (`arucostudio.scene/2`, docs/FILE_FORMAT.md): the Studio draws it and writes it on every action; a person or an AI can edit the same file in any editor and the Studio follows. Every outline, height, id and message of a tag comes from a `TagPlan`, a `Target` or an `Issue` that the server sent.

## The gallery

| | |
|---|---|
| What it is | the landing page: `examples/gallery/gallery.json` lists the examples by group (Markers by hand, Made two ways, IDs, Auto-placement on profiles, Labels, Corner marks, Trim and Perimeter, Multi-face, The sticker sheet, PrusaSlicer). Each card's thumbnail is the example's real plan (`POST /api/design/preview`, drawn by the 2D canvas's own code), its title and one line |
| A card | opens a fresh copy, `<home>/gallery/<name>.arucostudio.json` (`POST /api/gallery/open`); the example file is never written. The first tag is selected. The note over the canvas says what to look at and has the example's buttons (3D view, Sticker sheet…, Send to PrusaSlicer…, Renumber all), Start over (a fresh copy), the previous / next example and Gallery |
| Back | the top bar's Gallery button, File › Gallery…, S › "Gallery", or Open… › Examples › The gallery |
| Where a window starts | the gallery, unless a file was opened on purpose (`--open`, Open…) or the URL says otherwise: `#gallery`, `#studio`, `#example=<name>` (a reload keeps the example and its note) |
| The dev flag | `?draw=1` (e.g. http://127.0.0.1:5360/?draw=1): the drawing tools, their keys and buttons and palette rows come back, and the window starts on the canvas. The older e2e tests run this way |

## Run it

| Do | Command |
|---|---|
| Run the Studio (one command) | `npm --prefix studio run studio`, then open http://127.0.0.1:5360 |
| Run it on a file | `.venv/Scripts/python -m aruco_studio.server --open <file>.arucostudio.json` |
| Develop (hot reload) | `.venv/Scripts/python -m aruco_studio.server` and, in a second window, `npm --prefix studio run dev`; open http://127.0.0.1:5361 |
| Unit tests (vitest) | `npm --prefix studio test` |
| End-to-end (Playwright) | `npm --prefix e2e test` (starts 5360 and 5361 when free, stops them after) |
| Everything | `.venv/Scripts/python tools/check.py` |
| Types from the server | `.venv/Scripts/python studio/scripts/dump_openapi.py` then `npm --prefix studio run types` |

First time only: `npm --prefix studio ci` and `npm --prefix e2e ci`. The e2e tests use the installed Chrome (no browser download).

## The file is the truth

| | |
|---|---|
| No Save | every action writes the open file at once. Ctrl+S only says so |
| Undo, Redo | a history of the file's texts: Undo puts back the text from before the last action, byte for byte. A change made outside (an editor, an AI) is a step too |
| An outside change | the server sees it (it checks the file 4 times a second) and tells the Studio, which redraws; no reload |
| A file that does not parse | the bar at the bottom left turns red and says "line N col M"; the last good scene stays on the canvas; every write is refused until the file parses again |
| A file that goes away | the bar says so; writes stop; Save as… writes it again |
| New scene | a new file `scenes/<name>.arucostudio.json`, followed at once |
| Open | the gallery, the three older examples (a copy opens in the scenes folder), the recent files, a folder to browse (the scenes folder first), or any file by its path |
| A typed file | opening it freezes the presets its sugar names into the file (`frozen_presets`): a PrusaSlicer profile changed later shows **Apply** under the Preset, never a changed tag |
| Save as | a copy at a name or a path; the Studio follows the copy from then on |
| The File drawer | the file's text, read only, the selection's lines lit, Reveal opens Explorer on it (the status bar's File button) |

## The screen

| Part | What it does |
|---|---|
| Top bar | File (New, Open, Save as, Reveal, the File drawer) and the scene's name · Undo, Redo, Rotate, Duplicate, Delete, Arrange · 2D / 3D, quiet zones, frame axes, layer outlines, zoom to fit · Verify · Export (Sticker sheet…, Print sticker sheet…, Send to PrusaSlicer…, the files) · the light / dark theme · the keys |
| Tools (the canvas's foot) | the tools with their keys on badges; the active one is lit. Above them, while a tool runs: what it waits for and what you typed. The typed box also takes a paste (Ctrl+V of `80 50`) and an input method's text (click the box first, or just type with the IME on); full-width digits and `×` fold to `80 x 50`, any other character is dropped. A tool key typed in the box goes back to the page |
| IDs (left) | one row per tag: type, how it is made (`3D` / `2D`), dictionary, ids, a typed first id, locked and duplicate marks. "Renumber all" makes the ids unique per dictionary family: a sticker #3 and a printed #3 are one duplicate |
| 2D canvas | the shapes (a body's outline is brighter) and every tag drawn from its plan, a `3D` or `2D` badge by its name. A tag on a side face is drawn unfolded about its edge, like the net of a box, with a dashed hinge line (`data-hinge`). A sticker's cut line is dashed grey; a hole that Holes: Ignore leaves out is dashed amber. With both kinds in the scene, "Show All · 3D · 2D" filters the canvas (and the 3D view) |
| 3D view | each Extrude as a prism, each tag standing on its face by its full pose; the gizmo on the selected shape's sketch (move in X and Y, turn about Z) and the extrude arrow on its body |
| Inspector (right) | a shape: its place, turn, size, holes, the Extrude's height, the tags on it. A tag: the Preset first (it is the machine), Made by under it (read only: "Inkjet printer · 600 dpi · Letter · paper 0.1 mm"; 2026-10-17: the stored kind is still "sticker"), what it stands on, then the tabs Marker · Heights · Print · Label · Advanced. The rows, their tabs, icons and when they show all come from `GET /api/form` (`plan/fields.py`): a sticker has no Heights tab and gets Sticker thickness and margin on Print. Each message sits under its row, or under the row it is anchored to while its own row is hidden. Several tags selected: one form, a change goes to all of them (one Undo), "—" where they differ. Nothing selected: the new-tag Preset (3D printers and sticker printers); it starts on "Inkjet · Letter vinyl" (2026-10-17, CF-13: `GET /api/presets`' `new_tag`), and a preset picked there wins |
| Library | presets like Fusion's Machine Library: Recent, This scene, My presets, PrusaSlicer profiles, Built-in, **Printers** (one card per PrusaSlicer physical printer, its fitting print presets to pick, PrusaSlicer's current pair marked; Select makes a preset from the printer's nozzle and the print's line and layers) and Inkjet printers (the vinyl presets; an inkjet card's Edit form: Paper size, Paper thickness, Page margins, Dots per inch) |
| Status bar and drawer | the file's state, the last message; the Verify, Messages (with the keys) and File drawers |

## Commands and keys

S opens the command palette: with `?draw=1` it lists exactly these commands (the e2e test diffs the two lists); without it, these but the six drawing tools (R, C, P, O, H, Shift+H), whose keys then do nothing (`e2e/tests/gallery.spec.ts`). A command without a key runs from the palette.

| Key | Command |
|---|---|
| V | Select / move |
| R | Rectangle |
| C | Circle |
| P | Polygon |
| O | Slot |
| H | Hole |
| Shift+H | Rectangular hole |
| E | Extrude |
| A | ArUco Extrude |
| ] | Rotate 90° clockwise |
| [ | Rotate 90° counter-clockwise |
| S | Search commands |
| Ctrl+D | Duplicate |
| Del | Delete |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+A | Select all |
| Esc | Cancel |
| Enter | Confirm |
| | Arrange in a row |
| F | Zoom to fit |
| Tab | 2D / 3D |
| ? | Keys |
| | Quiet zones |
| | Frame axes |
| | Layer outlines |
| | File drawer |
| | Light / dark theme |
| | Show every tag |
| | Show 3D tags only |
| | Show 2D tags only |
| | Verify |
| | Verify the sheet |
| | Renumber all |
| | ArUco: single |
| | ArUco: grid |
| | ArUco: ChArUco |
| | Preset library |
| | Gallery |
| | New scene |
| Ctrl+O | Open |
| | Save as |
| | Reveal the file |
| | Export: print sheet SVG |
| | Sticker sheet… |
| | Print sticker sheet… |
| | Send to PrusaSlicer… |
| | Export: STL of every tag |

### The tools

| Tool | In 2D | In 3D |
|---|---|---|
| Select / move (V) | click, Shift+click, marquee; drag moves (0.5 mm; Alt no snap); handles on one selected shape | click a body or a tag; the gizmo and the extrude arrow |
| Rectangle (R) | drag a box (Alt from the centre, Shift a square), or type `80 50` Enter (at the view's centre) | |
| Circle (C) | drag a diameter, or type `50` Enter | |
| Polygon (P) | click the points; Enter, or a click on the first point, closes it | |
| Slot (O) | drag the length (the width is a quarter of it), or type `40 12` Enter | |
| Hole (H), Shift+H | click inside a shape: a round hole (type the diameter first; 5 mm), a rectangular one with Shift+H (`10 6`); or type and Enter for the selected shape's centre | |
| Extrude (E) | the selected shape: type the height, Enter (5 mm when nothing is typed); the view goes 3D | drag the arrow on the body's end face (0.5 mm steps) |
| ArUco Extrude (A) | the selected shape is picked already; click a shape (an extruded one: its top), or a face of the net drawn around an extruded shape; Shift+click more; Enter. The tag appears placed (Auto size, the file's preset), the inspector on it | click a face (top, bottom, a flat side); Shift+click more; Enter |

Several faces make one feature with a face list (one tag per face, named `<id>.<face>`); Renumber makes their ids unique.

### The mouse

| Do | Does |
|---|---|
| Click, Shift+click | select, add to the selection |
| Drag on empty canvas | marquee select (Shift adds) |
| Drag a shape or a tag | move it (0.5 mm snap; Alt: no snap). A tag moves with its shape |
| Drag a handle | resize or turn the shape: a rectangle has 8 handles, a circle one on its rim, a polygon its points, a slot its ends and its width; every shape a turn handle past its top (15° steps). The markers re-place live |
| Alt+click a polygon's edge | a new point there; Del removes the point just dragged |
| Drag a selected tag's label | place the label by hand (0.25 mm steps) |
| Arrows (Shift) | nudge the selection 0.5 mm (5 mm) |
| Wheel | zoom at the cursor; Shift+wheel pans |
| Space+drag, middle or right drag | pan |
| Double-click a tag or an IDs row | zoom to it |

## How it works

| Piece | Where |
|---|---|
| The store (zustand): the design file, the scene with its plans, the selection, the tool, the text history | `studio/src/store.ts` |
| The file's text, read and written as the server writes it (sorted keys, indent 1, each number as it was typed) | `studio/src/model/json.ts` |
| The document's edits: shapes, holes, Extrude, ArUco Extrude, moves, turns, deletes | `studio/src/model/design.ts` |
| Shapes drawn (outlines, faces, the net): for drawing only; the loops the planner fits are the server's | `studio/src/model/shapes.ts` |
| Handles and what a drag writes | `studio/src/sketch/handles.ts` |
| Commands (the toolbar, the palette, the keys, this doc's table) | `studio/src/app/commands.ts` |
| The events client (server-sent events) | `studio/src/api/events.ts` |
| The 3D gizmo and the extrude arrow | `studio/src/view3d/Gizmo.ts` |
| The kit (`@bam/ui`: tokens light and dark, Select, NumberField, Switch, Tabs, Dialog, Menu, Form, the palette, the library shell; docs/KIT.md) | `studio/packages/bam-ui/` |
| The inspector's form: the kit's `Form` over `/api/form`, plus the Studio's own controls (Size with Auto, Cells, Origin, Trim / Perimeter, Fit) | `studio/src/inspector/Inspector.tsx`, `PresetRow.tsx` |
| The dialogs: New, Open, Save as, Sticker sheet…, Send to PrusaSlicer…, Print's fallback | `studio/src/app/Dialogs.tsx` |
| Print: the PDF into a hidden iframe, its print() | `studio/src/app/Print.tsx` |
| Live re-placement | while a handle (or the 3D arrow or gizmo) drags, the Studio sends the new text to `POST /api/design/preview?top=1` (15 times a second at most; nothing written): the plans and top views only, the light preview. The 2D view draws it as always; the 3D view stands each tag as a flat slab of its top view. On release the plans of the last preview are drawn at once (in 3D one more request brings the meshes) and the file is written. The forearm: about 75 ms a drag step, 270 ms for the 3D release (`docs/status/speed.md`) |
| Tests' handle | `window.__studio`: `probe()` (the file, the shapes, the tool, the picks, the revision), `idle()`, the store, `theme`, `printHook` (when set, Print hands it the PDF's bytes instead of the print dialog; false = a browser that cannot print it), `sendOpen` (false: Send never opens PrusaSlicer); `window.__studio3d`: the faces' and the gizmo's screen points, the tags' normals |

## Stickers, the sheet, Print and Send

| | |
|---|---|
| A sticker | pick an inkjet printer as the Preset ("Inkjet · Letter vinyl" or "Inkjet · A4 vinyl"; nothing selected: the new-tag Preset; a tag: its Preset row), then A on a shape. The tag is an inkjet sticker, make rule 2 (2026-10-17): one paper body t thick (0.10 mm vinyl by default: measure yours) with the black printed t/2 into it, the frame on the paper's top. Its Manufacture tab reads **Inkjet**: Paper thickness (a Stocks list fills it in), Paper size, Page margins. Perimeter: Marker (a rectangle) or Profile (the shape's outline, holes included); with Marker the label goes on the black only (a new tag has no margin of its own: the sheet's). A tag made before keeps its rule 1 (the ink on top) and its own Sticker margin / Cut line rows |
| Too big for the page | a rule-2 sticker whose outline does not fit its page's printable area (portrait or landscape, either way round) gets a red row under Marker size (Profile: under Perimeter) and a red cut line; it is still built, the sheet will not place it. Auto size never goes over the page: it caps the sticker, turning it if that fits |
| Shift | Shift X / Y (Marker tab) move a sticker off where the fit puts it, along the face's own axes; or drag the selected sticker's crosshair on the canvas (0.5 mm steps, Alt: free); × puts it back. A sticker shifted off its face is warned. 3D tags do not shift (3D is a placeholder) |
| A label cut from the black | label rule 5 (what new tags store): its strokes are at least 1.1 of the tag's cell lines (0.748 mm at 0.68 mm lines, so 3.74 mm letters), measured in the headless slice; at exactly one line the black counters drop out. A label on the white keeps the nozzle's 3.0 mm. A typed cap under it is refused with the reason; a tag that stores rule 1-4 plans as before |
| Holes | shown when the shape has holes: Avoid (the marker keeps clear) or Ignore (it may cover them; the plan says when it crosses one) |
| A ChArUco label | goes in a black square only (Position offers that alone; Auto reads "In a black square"); drag it into any black square. Label rule 4 (and 5, what new tags store): when no square holds the text it is not built, with one message under Label ("No room in a 13 mm square for '#0-3': fewer columns (bigger squares) or Content #id") and the orange preview in the square; it never moves to the white |
| Export › Sticker sheet… | the page, Landscape, Spaced (gaps, a caption and crop marks per sticker) or Tight (shelves that share their cut lines), the page margins, and (2026-10-17) the **Sticker margin** (white round each sticker: its cut line that much out) and **Cut lines** on / off; the preview is the server's own `sheet.svg`; the stickers that do not fit are listed with the reason. Export writes the sheet only (`sheet.pdf`, `sheet.svg`, `sheet.json`, `markers.json`; the 3D parts are Send's) to `exports/<scene>/`, then says the folder, with **Reveal**. It starts from the file's `sheet` key |
| Export › Print sticker sheet… | the sheet's PDF (`/api/scene/print.pdf`) goes to the browser's print dialog through a hidden frame; Chrome and Edge print it at 100 %. Print at Actual size and check the 100 mm bar. Where the browser cannot (Firefox), a dialog offers **Open the PDF** and the Ctrl+P note. Off when the scene has no sticker; on a 3D scene it says "3D tags: Send to PrusaSlicer…" |
| Export › Send to PrusaSlicer… | the physical printer (PrusaSlicer's current one first), a print preset that fits it, the white and black extruders, Open PrusaSlicer. Send writes a 3MF project with the colours on their extruders (`exports/<scene>/prusaslicer/`) and opens it in PrusaSlicer. Off, "nothing to slice", when the scene has no 3D tag. When the tags were planned for another nozzle than the printer's, a line says so and names the printers that match (a click picks one) |
| A changed PrusaSlicer profile | a tag whose preset came from it shows the change under its Preset with **Apply**; nothing changes without the click |
| Light / dark | the moon / sun button of the top bar (or S › "Light / dark theme"); light is the default; the browser remembers the choice |

## Things to know

| | |
|---|---|
| A tag on a shape's top | a click on the shape outside the marker selects the shape (its handles); a click on the marker selects the tag |
| Typed columns × rows | REF's fit on a FACE lays out as many as fit; only a sketch profile takes a typed count (Advanced › Target kind). On a face the row says so: set the Checker (or Marker) size, the count follows |
| A new tag's ids | the next free ids of its dictionary family; a new face list gets a run per face (`marker_ids`), so Renumber is a repair, not a step |
| A split list | its features are named `tag1.front`, `tag1.right`; the next new tag is `tag2` and is selected alone |
| The cell minimum | when Auto's board has cells under the preset's minimum, the warn says the Checker size that passes |
| The palette (S) | finds a command by its name first: the whole name, then its start, then a word of it; Enter runs the first |
| The sugar | a hand-typed tag (`"layout": "charuco", "cols": 5`) stays short until the Studio edits that tag; then it holds the exact settings |
| Colours (Extrude) | changing it keeps the black's step from the white top (REF's dialog does the same) |
| Verify | a row goes grey when its tag changes; Verify again redoes it |
| Overlapping tags | a dashed outline on both, a note on the canvas; the sheet's Verify says "Not as planned" |
