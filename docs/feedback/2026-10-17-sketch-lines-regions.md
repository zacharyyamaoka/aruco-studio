# Zach's feedback, 2026-10-17 ~07:30-07:55: sketch lines, closed regions, an off-the-shelf sketcher

These are from his daily note (Daily Note - Oct 17 2026, from line 53). The vault backup at 07:26 has only the note's opening lines. His three screenshots (Pasted image 20261017075332/075448/075513.png) are not in it, and he said not to worry about them.

## What he wants

| ID | Requirement | His words, condensed |
|---|---|---|
| SK-1 | **Lines.** The sketch must support plain lines. Today's shapes are only rect / circle / polygon / slot / loops. | "We don't support lines, which is not good we should" |
| SK-2 | **The 2D view is one CAD sketch.** What we draw are sketch entities (lines, arcs, circles...). | "the 2D is almost like the equivalent of 1 cad sketch... yes that is the right way to think about this" |
| SK-3 | **Live closed regions.** In the background, the closed regions (and which strokes don't close) are worked out live. | "in the background be live calculating what are closed regions and not" |
| SK-4 | **Select a region = the profile.** Click a closed region to make it the profile a tag goes on. | "Select the region... how do you select a profile?" |
| SK-5 | **Snapping while drawing**, the way his arrows snap. Draw, and the ends snap together. | "I like with the arrows how I can draw it and then they snap" |
| SK-6 | **Don't hand-roll CAD interactions.** Find a simple off-the-shelf 2D sketching canvas (AutoCAD-like). It may be 2D only: 3D can stay a separate step (our three.js view and Extrude). | "instead of us hand rolling and having to get reasonable interactions... Is there a simple off the shelf sketching thing... even if it doesn't do 3D we could do the 3D as a separate step" |
| PP-1 | **The paper size in a printer preset caps the marker size.** Sticker presets already carry `page` (letter / a4 / ...), but nothing caps a marker at the printable area (the page minus its margins). | "Add paper size to printer preset determines maximum size of marker" (the note's first line) |

## Dispatched

- **SK-6 survey** (2026-10-17): a survey of open-source tools, reported in `docs/design/sketch_tools_survey.md`.
- **SK-1, SK-3, SK-4** are waiting on the survey's answer, because the tool we pick may supply the drawing and the region picking.
  - Either way, the core must find regions itself (MC-9, file first): an AI can write lines into a scene file with no browser open.
- **PP-1** is a small core rule, not yet built.

## Superseded (2026-10-17, later that morning)

Zach: "I am also moving away from aruco studio having its own like sketch platform no point in maintaining that... simply if you want to bring in sketches I could just like export DXF from fusion... 100% we don't need to maintain yet another cad program."
- SK-1..SK-6 are dropped, and the survey's SK-a..e plan is not built.
- Bringing sketches in from other programs (e.g. DXF) is the direction.
- See `2026-10-17-markers-core-first.md` (CF-12).
- PP-1 lives on as part of CF-6.
