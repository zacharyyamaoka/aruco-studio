# ArUco Studio: the web app

The Studio is the 2D / 3D app on top of the core. It draws what the core planned and nothing else: every outline, height, id and message on screen comes from a `TagPlan`, a `Target` or an `Issue` that the server sent.

## Run it

| Do | Command |
|---|---|
| Run the Studio (one command) | `npm --prefix studio run studio`, then open http://127.0.0.1:5360 |
| Develop (hot reload) | `.venv/Scripts/python -m aruco_studio.server` and, in a second window, `npm --prefix studio run dev`; open http://127.0.0.1:5361 |
| Unit tests (vitest) | `npm --prefix studio test` |
| End-to-end (Playwright) | `npm --prefix e2e test` (starts 5360 and 5361 when free, stops them after) |
| Everything | `.venv/Scripts/python tools/check.py` |
| Types from the server | `.venv/Scripts/python studio/scripts/dump_openapi.py` then `npm --prefix studio run types` |

First time only: `npm --prefix studio ci` and `npm --prefix e2e ci`. The e2e tests use the installed Chrome (no browser download).

## The screen

| Part | What it does |
|---|---|
| Toolbar | File (New, Open, Save, Save as) · add Single / Grid / ChArUco · Undo, Redo, Rotate 90°, Duplicate, Delete, Arrange · 2D / 3D, quiet zones, frame axes, layer outlines, zoom to fit · Verify · Export |
| IDs (left) | one row per tag: type, dictionary, ids, a typed first id, locked and duplicate marks. "Renumber all" makes the ids unique per dictionary family (the core's numbering and the scene's ledger). Click a row to select, double-click to zoom |
| 2D canvas | like Figma. Each tag is drawn from its plan: the target, the top view (body, white, black), every layer as an outline (`data-layer`), the quiet zone, the label's clear zone, keep-outs, a refused label in orange, the trim outline, the OpenCV frame (x red, y green) |
| 3D view | the server's mesh of every tag, placed on the canvas; heights, pockets, pins and the trim show. A height exaggeration (z ×1 to ×10) for thin layers |
| Inspector (right) | the selection. Name, ids, lock, hide; the Preset row with the Library button; the target editor; tabs Marker · Heights · Print · Label · Advanced. Each message sits under the field it is about; one summary line is always at the bottom |
| Library | print presets like Fusion's Machine Library: Recent, This scene, My presets, PrusaSlicer profiles, Built-in; cards with the marker's thumb; Filters and Info; New, Duplicate, Edit, Import, Delete; Select / Cancel |
| Status bar and drawer | the last message; the Verify drawer (OpenCV's read of each tag: ids, corner error, PnP error 25° off, the image it read) and the Messages drawer (every message, the keyboard map) |

The 2D / 3D toggle (bottom right of the canvas, or Tab) keeps the view's centre and scale, like Google Maps.

## Keys

| Key | Does |
|---|---|
| S / G / C | add a single marker / a grid board / a ChArUco board |
| Click, Shift+click | select, add to the selection |
| Drag on empty canvas | marquee select (Shift adds) |
| Drag a tag | move it (0.5 mm snap) |
| Drag a selected tag's label | place the label by hand (0.25 mm steps) |
| Arrows (Shift) | nudge 0.5 mm (5 mm) |
| Wheel | zoom at the cursor; Shift+wheel pans |
| Space+drag, middle or right drag | pan |
| R / Shift+R | rotate 90° clockwise / counter-clockwise |
| Ctrl+D | duplicate |
| Del / Backspace | delete |
| Shift+A | arrange in a row, 10 mm apart |
| Ctrl+Z, Ctrl+Shift+Z or Ctrl+Y | undo, redo |
| Ctrl+A / Esc | select all / none |
| Tab | 2D / 3D |
| F | zoom to fit (the selection, or everything) |
| Q / A / L | quiet zones / frame axes / layer outlines |
| V | verify the selection with OpenCV |
| Ctrl+S / Ctrl+O | save / open |
| ? | the Messages drawer and this map |

## How it works

| Piece | Where |
|---|---|
| The store (zustand): the scene, the selection, the view, undo / redo | `studio/src/store.ts`; the pure reducers in `studio/src/model/scene.ts` |
| Changes | each goes through the API and runs one at a time; the scene comes back with its plans (`GET /api/scene?plans=1&top=1`, `&mesh=1` in 3D). Undo keeps the scene as the file holds it and puts it back (`PUT /api/scene`) |
| The inspector's fields | `GET /api/form` (never a list written in the app); `studio/src/inspector/layout.ts` only says which tab a field goes on and which icons its choices get |
| Messages | the plan's `warnings`; each goes to the deepest field its key path names (`routeIssues`) |
| A new tag | `POST /api/new` (what today's Fusion dialog stores for a fresh tag, under a preset) |
| The target editor | `POST /api/target` makes the outline (box, disc, a palette face, holes, a thickness) |
| Types | `studio/src/api/schema.d.ts`, generated from the server's OpenAPI |
| Tests' handle | `window.__studio`: `center` (px), `zRange` (mm), `probe()`, `idle()`, the store |

## Things to know

| | |
|---|---|
| Typed columns × rows | REF's fit on a FACE lays out as many as fit; only a sketch profile takes a typed count. Set Advanced › Target to `profile` for a typed board |
| Auto size | one Auto for the marker and the ChArUco checker, as in Fusion's dialog |
| Colours (Extrude) | changing it keeps the black's step from the white top (REF's dialog does the same) |
| Targets that grow | a tag's target can grow over its neighbours; Arrange (Shift+A) lays them out again |
| Holes typed in the target editor | kept as the target's loops; the editor lists them only in the session that typed them |
