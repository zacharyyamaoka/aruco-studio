# The online Studio v1 (arucostudio.com)

Zach, 2026-10-18 (`PROJECT - Aruco Studio`, Introduction): "lets prove out the interactions and everything within aruco studio online first. and then when we go to CAD its only a matter of doing the things specific to CAD."

This is the spec the v1 lanes build to. The code is the living spec after that; this file records the decisions and the done checks.

## What changed from the local Studio (`studio/`)

| Was (`studio/`, 2026-10-17) | Now (`web/`, arucostudio.com) | Why |
|---|---|---|
| A FastAPI server on 127.0.0.1:5360 plans every tag | The same Python core runs **in the browser** (Pyodide worker); the site is static on Cloudflare | One core for the web, Fusion, build123d and viser; parity proven byte for byte |
| A mini CAD (shapes, extrude, many tags, 3D) | One sketch plane: a face (from examples or a file), rectangles you draw, and the ArUco Extrude feature | "Simple focused tools"; "No, out of scope" for our own CAD |
| The tag finds its own spot on the face (auto placement) | **The marker rectangle** is the entry point: draw one, or pick a face and the core inscribes one; the rectangle stays an editable sketch rectangle | "the marker is represented by a rectangle"; "afterwards you can edit the sketch" |
| A typed size that does not fit is clamped | A typed size is **drawn as typed** and flagged red | "it won't block you, it may just throw a warning" (calib.io's red linter) |
| Separation derived | **Separation is a field** (grid) | Zach's Marker list |
| Inspector panel | A floating, draggable feature panel + a presets modal, neutral styling | Fusion's layout, "unstyled… so it's easy to customise to feel natural in any other program" |

`studio/` stays as it is (not deleted, not developed) until Zach decides.

## The flows

1. **Draw.** `R`, drag on the sketch: a rectangle (snaps to 0.5 mm). It is selected. `A` (ArUco Extrude) opens the panel with *Rectangle: 1 selected*.
2. **From a face.** Click inside the face (not on a rectangle): the face is selected. `A`: the core inscribes the largest clear rectangle (*Holes: Avoid / Ignore*), it is added to the sketch as a normal rectangle and selected in the panel. *Profile: 1 selected* is the reference face.
3. **Nothing selected.** `A` opens the panel with the Rectangle selector active ("Select a rectangle or a face"); clicking one fills it (Fusion's selection rows).
4. **Edit.** Drag the rectangle (move) or its handles (resize): the marker re-plans live. Double-click a timeline item re-opens its panel.
5. **Make.** The marker fills the rectangle (Auto on). Typing a size, picking a suggestion, or dragging turns Auto off; overflow is drawn and flagged red, never refused.
6. **Print.** Export › Print…: the preset's page at true scale with the label, cut line and a 50 mm scale bar; Print (browser dialog at 100 %), Download PDF, Download SVG.

## The screen

- **Top bar:** "ArUco Studio"; File (New, Examples…, Open…, Save); Export (Print…, SVG, PDF); the preset chip (opens the presets modal); the core chip ("Core loading… / Python ready"); theme; GitHub link.
- **Viewport:** the sketch plane, y up, mm grid, pan (middle / right drag, space-drag), zoom at the cursor, `F` fits. Draws the face (grey, holes cut), rectangles (blue sketch lines; hover, select, move, 8 handles), the marker (black on white; overflow outlined red), the Joint Origin triad (x red, y green) with a turn arc, the outer-size dimension, the label text (draggable: sets `label.offset_mm`).
- **Toolbar:** Select `V`, Rectangle `R`, ArUco Extrude `A`, Fit `F`, Print `P`. `Esc` cancels, `Delete` removes.
- **Timeline (bottom):** Sketch → ArUco Extrude → Joint Origin, Fusion-style icons; click selects, double-click edits.
- **ArUco Extrude panel** (floating, draggable, collapsible, ~300 px, starts top-right of the viewport):
  - Profile (optional face) and Rectangle (required): selection rows with a clear button.
  - **Preset** first: method icon + name (+ "(modified)") and a "…" that opens the modal.
  - Tabs **Marker | Label**.
  - Marker: Type (3 icon toggles), Dictionary, ID / First ID (with the range), Marker (mm) + Auto, Checker (ChArUco), Separation (grid), Columns × Rows, Suggest (a list: label + reason), Turn (0 / 90 / 180 / 270), Flip (only with no reference face), Corner mark.
  - Label: On, Text (with placeholders), Height, Side, Gap.
  - Each row shows its own issues underneath (red error, amber warn, grey info).
  - Summary line, then OK / Cancel.
- **Presets modal** (the kit's `LibraryShell`): Recent / My presets / Built-in; search; cards with a thumb and key numbers; Filters (method, paper, nozzle) and Info; New / Duplicate / Edit / Delete; Cancel / Select. My presets live in `localStorage` and export / import as JSON.
- **Examples** (golden faces): a plate with two holes, an L bracket, a disc with three holes, a forearm side, a blank sketch (no face: Flip appears).
- **Styling:** the kit's tokens (`@bam/ui/tokens.css`), light and dark; neutral greys; no Fusion chrome baked in, so a host restyles by overriding the variables.

## Architecture

```
web/src/core/contract.ts      the frozen UI <-> core contract (TypeScript)
web/src/core/worker.ts        Pyodide in a Web Worker: loads /py/aruco_studio.zip, calls web_api
web/src/core/client.ts        CoreApi over the worker (+ useCoreStatus)
aruco_studio/web_api.py       the facade: JSON in, JSON out, stdlib only, the same names as CoreApi
web/scripts/pack-core.mjs     zips aruco_studio/{__init__,web_api,core,plan,scene} into web/public/py/
web/public/pyodide/           Pyodide's files, copied from node_modules at build (self-hosted: works offline, in 10 years)
web/wrangler.jsonc            a static-assets Worker on arucostudio.com + www
```

The UI never computes marker geometry. It draws what `plan` returns, in the sketch frame.

## Lanes and their done checks

**Lane core** (`aruco_studio/web_api.py`, core changes, `web/src/core/` except `contract.ts`, `web/scripts/pack-core.mjs`, `tests/web/`):

1. `web_api` implements every `CoreApi` call against the existing core (`plan_tag`, `autosize.largest_clear_rect`, `autosize.candidates`, `presets`, `exports.to_svg`, `core.sheet`).
2. Core change **typed size is not clamped**: an opt-in rule (the web always sets it; existing tags keep clamping) draws the typed size and returns an `error` issue on `marker.marker_mm` naming the overflow in mm. `overflow_mm` > 0.
3. Core change **separation is a field** for grids (`separation_mm`; 0 = today's rule).
4. CPython tests (`tests/web/`) for each call, including: a 30 mm single in a 20 × 20 rectangle is drawn at 30 mm with `overflow_mm` ≈ 5 and a red issue; the inscribed rectangle in a plate with holes does not overlap a hole; grid separation 5 mm gives a 5 mm gap; suggestions carry reasons; the existing core suites stay green.
5. A Node test runs `web_api` in Pyodide and CPython on the same cases and compares the JSON byte for byte.

**Lane UI** (`web/src/` except `web/src/core/`): the screen above against `CoreApi`; Playwright e2e on the static build (`vite preview`); vitest for pure helpers.

**Orchestrator:** this spec, the contract, `web/package.json` and the lockfile, `wrangler.jsonc`, the deploy, the report.

## Many features, driven vs set, no timeline (lane doc, 2026-10-18)

- **A document holds N ArUco Extrude features** (`web/src/model/doc.ts`, file version 2; a version 1 file migrates on open). Each has a stable `id` (made once, saved) and a `key` (the id by default: what auto id hashes), its own rectangle, marker, label and `set` list; the document has `id_ledger` (key -> first id; wave 2 fills it). A on a rectangle that has a feature opens it; A on a new rectangle or profile makes one. Each feature plans on its own; Print and Export › PDF send every feature as a sheet item. Deleting a feature keeps its rectangle; deleting the rectangle deletes its feature. This replaces "the UI prints one feature" below.
- **No timeline; WYSIWYG** (Zach: "too specific to CAD… just clicking the marker on the screen is what brings up the relevant inspector window"). A click on a marker or its rectangle selects that feature and opens its panel (a panel open on another feature closes with OK); a click on empty canvas closes it; Delete removes the selected feature. The toolbar floats at the viewport's bottom centre (on a phone, above the docked panel, which opens at about 45 % of the height with the marker fitted above it). Suggest is one dropdown whose options show their whole reason. This replaces the timeline in "The screen" and flow 4's double-click.
- **Driven vs set replaces the Auto switch** (Zach: "just show the actual value but make it kinda like grey outed"). Every value row is driven (the actual value, muted, its driver in the tooltip: the plan's size, a core rule, or the default) or set (typed, normal text, ↺ back to driven; red when the core flags it). The contract's encodings carry it: a driven size is `auto: true`; a driven checker, separation or label height is 0; the rest are listed in `Feature.set`. `web/src/ui/DrivenField.tsx`. This replaces "Auto on / turns Auto off" in flow 5.

## Not in v1

DXF import of faces; the live camera verifier (Pyodide ships OpenCV, so it can run in the browser later); 3D view; many markers on one page from many features (the sheet call supports it, the UI prints one feature); PrusaSlicer sync (desktop only).
