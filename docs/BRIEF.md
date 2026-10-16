# ArUco Studio: the brief (Zach, 2026-10-16)

ArUco Studio is the top-level project for managing fiducial markers across Zach's projects. The Fusion add-in (today on branch `claude/aruco-fusion-plugin-0e9bcb` of cad-exporter) becomes one adapter of it.

Goal for the next while: "all that matters here is making the best ArUco library ever".

## What Zach asked for

- **Functional core, as for CADExporter and Cad2Robot.**
  - Most of the behaviour and algorithms live OUTSIDE Fusion, in a plain Python core, and are tested and working in a simple 2D/3D viewer that doesn't depend on Fusion at all.
  - Fusion is only the final step: a thin adapter that turns the core's plan into Fusion bodies, sketches and joint origins.
- **Two views:**
  - 2D: by default like Figma. Several markers can sit on the same canvas.
  - 3D: like Google Maps' 2D/3D toggle. The 3D view shows the heights (black / white layers, recesses, pins, trim).
- **Types supported now:** single marker, grid board, ChArUco board.
- **Two separate things:** the tests, and the actual functionality we want.
- **Logic that belongs in the core, not in Fusion:** labels, corner marks, quiet zones, sizing, rounding, print presets, numbering, trim, validation, and so on. "All of the logic can definitely be done outside."
- **Other adapters later:** build123d and viser are where Zach composes scenes. He'll need to renumber from there, and possibly export STLs or rebuild parametrically. build123d could do that easily. For now it's enough that the core is reusable from other modelling tools and 3D viewers.

## Why

The Fusion-only loop is the bottleneck. On 2026-10-16 the add-in was about 47,000 lines; 40 of its 45 files import `adsk`. The Fusion-free core (`CADExporter/bam_cad_core/aruco_*`) was about 8,300 lines. Every check of add-in logic needed the single shared Fusion window, so Zach was blocked while agents tested, and agents waited for test windows.

## Notes

- The domain arucostudio.com was free on 2026-10-16. Nothing has been registered.
- This repo is local only. No remote has been created yet.
