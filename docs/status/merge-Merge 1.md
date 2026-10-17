# Merge 1: wave 1 (M6a, then M8a)

2026-10-16, about 22:30 to 23:15. Both lanes merged into main with `git merge --no-ff`, in this order:

| Lane | Merge commit | What it brings | Its record |
|---|---|---|---|
| lane/M6a (f0e7cfb, 15f2979) | 9772447 | stickers, the preset as the machine, the sticker sheet, the print bundle, label rule 3 | docs/status/M6a.md, docs/API_sheet.md |
| lane/M8a (92fa734) | 30cfa6d | the design file `arucostudio.scene/2`, the watcher, `/api/events`, the CLI | docs/status/M8a.md, docs/FILE_FORMAT.md |

Git found no conflicts. `docs/API.md` and `server/app.py` were edited by both lanes, but in different places.

## Include lines added

| File | Line (at the end) |
|---|---|
| `aruco_studio/server/app.py` | `from . import sheet_api  # noqa: E402,F401  (M6a: the sticker sheet routes)` |
| `docs/API.md` | `The sticker sheet, the print bundle and the presets as machines (M6a): docs/API_sheet.md.` |

M8a asked for none.

## What the merge broke, and the fixes

| # | Found | Fix | Test |
|---|---|---|---|
| 1 | The design file's preset names did not reach the sticker printers. `design_api.resolver` read REF's catalog, so "Sticker · Letter · 600 dpi" fell back to Default. | `resolver` reads `presets.catalog_all` | `tests/scene/test_merge1_wiring.py` |
| 2 | `plan/newtag.new_spec` did not pass its preset to `core.form.new_tag_settings`. A design-file tag under a sticker preset was stamped "3D printed". | `new_spec` passes `preset=`. A 3D tag gets the same `make` as before. | `test_merge1_wiring.py` |
| 3 | **A ChArUco sticker on a disc hung the plan for ever.** A sticker's cell is one dot, 25.4 / 600 = 0.042333 mm. Sizes are kept to 0.1 um, and a dot is not a whole number of 0.1 um, so a rounded size sits up to 0.05 um off its grid. `_Grid.S_next` then gave back the same square, and `_cap_down` looped. M6a's tests had no ChArUco sticker on a shape with loops. Once fix 1 made the example's t4 a sticker, the scene tests hung. | `core/autosize._Grid` snaps with half of 0.1 um too, but only when the step is not a whole number of 0.1 um (new `_snap`). Every REF step is a whole number, so for them the old constants are used, bit for bit. `test_port_fidelity.py` lists `_Grid` as changed on purpose. | `tests/core/test_autosize_dot_grid.py` (the steps always move; the disc case runs in a child process, so a regression fails instead of hanging) |
| 4 | The sticker example's t4 (a ChArUco on a 50 mm disc with a 6 mm hole in the centre) did not plan, under either preset: with Holes avoid, the clear rectangle around a centre hole is too small. | The hole moved to (0, 18) in `examples/sticker_sheet.arucostudio.json`. `check --strict` on all three examples now exits 0. | `tests/server/test_cli.py` now expects exit 0; `test_design_api.py` compares the stickers with the old routes under the sticker preset |
| 5 | M8a's `test_design.py` expected label rule 2. M6a's new tags store rule 3 (`label.NEW_RULE`). | The test expects `NEW_RULE`, plus the `make` and `holes` stamps. | itself |
| 6 | `test_design_api.py` sent `make: {perimeter}` in a PATCH. A PATCH replaces `make` whole, so the sticker stamps were lost. | The test sends the sticker `make` with the perimeter. | itself |
| 7 | e2e `export.spec.ts` expected the exported file to be `/1` with `tags`. | It expects `/2`, and the tag names as the ArUco Extrude features' ids. M8b1 rewrites this spec anyway. | itself |
| 8 | M6a.10 (a 96-point disc in under 50 ms) read 64.6 ms once under the full check's load. Alone, it reads 21.7 ms. | Up to six rounds of best-of-twenty, stopping when one is under 50 ms. The bar is unchanged. | itself |
| 9 | `plan/shapes.CHORD_MM` read `core.faces` until M6a's constant landed. | It now reads `plan.target.CHORD_MM`. The same 0.05 mm. | the plan group |

Nothing was reverted.

## The full check

`.venv/Scripts/python tools/check.py`, every group, from ROOT after the fixes:

| Group | Result | Before the merge (RUN.md) |
|---|---|---|
| adapters | 97 passed in 39 s | 97 |
| core | 7,308 passed, 4 skipped in 36 s | 7,245 + 4 skipped |
| plan | 513 passed in 84 s | 193 |
| scene | 36 passed in 13 s | 7 |
| server | 59 passed in 18 s | 35 |
| verify | 111 passed in 97 s | 104 |
| studio | build + vitest passed in 5 s | |
| e2e | 19 passed (1.5 m) in 91 s | 19 |
| **all** | **OK in 384 s**, exit 0 | |

`tools/check.py --trace`: `missing: 0`. After the run, nothing listens on 5360 or 5361. Port 5370 (Zach's preview) was left alone.

## Worktrees and branches

`lane/M6a` and `lane/M8a` are deleted, and their worktrees removed. `git worktree list` shows only ROOT and `aruco-studio-preview` (left alone).

## Still open (from the lane reports)

- `/api/preset/apply`, `/api/preset/of` and `server/library.py` still read REF's catalog. The Library has no Sticker printers collection yet, and a sticker tag's Preset row reads "custom". `library.py` belongs to M8c in wave 2; the two app.py routes can follow in the same change.
- M6c.1 (now in M8b2) should compare the print bytes with `/api/scene/print.pdf`, not `/api/scene/export/pdf` (REF's sheet).
- `GET /api/health` still reports scene `/1`.
- The sticker's "cells not whole dots" info and "label stroke under one dot" warn are not built.
- The print3d 3MF has no PrusaSlicer config (M8c).
- The e2e group still only checks today's Studio. The new sticker presets show in its New-tag dropdown; the e2e preset tests still pass.
- The screenshots under `reports/screens/` were rewritten by this e2e run.
