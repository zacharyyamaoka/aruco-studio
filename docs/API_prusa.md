# ArUco Studio: PrusaSlicer (M8c)

The physical printers, the folder's watcher, Send to PrusaSlicer. The rest of the API is in `docs/API.md`.

| | |
|---|---|
| Code | `aruco_studio/server/prusa_api.py` (routes), `server/prusa_watch.py` (the watcher), `server/store.py` (what is read, and how), `core/prusa.py` (the printers, the condition evaluator, the allow-list), `scene/print3d.py` (the 3MF), `server/beds_io.py` (the chain, the opener), `verify/slice_check.py` (the headless slice, tests only) |
| Included by | one line at the end of `server/app.py`: `from . import prusa_api  # noqa: E402,F401`. The routes are put first; the watcher starts with the server and stops with it |
| Tests | `tests/server/test_prusa_api.py`, `tests/server/test_prusa_watch.py` (TestClient; no port is bound), `tests/core/test_prusa_physical.py`, `tests/core/test_prusa_fits.py`, `tests/scene/test_print3d.py`, `tests/plan/test_mesh_removed.py`, `tests/verify/test_slice_check.py` |
| Fixture | `tests/fixtures/prusaslicer_m8c/` (Zach's five physical printers, his two printer presets and ten print presets, the bundle sections they inherit from; every host key a placeholder). Made by `tests/fixtures/make_prusaslicer_m8c.py` |

## What is read, and never written

PrusaSlicer's folder is `%APPDATA%\PrusaSlicer`, or `BAM_ARUCO_PRUSASLICER_DIR`. The Studio refuses to write under either.

| File | Read |
|---|---|
| `physical_printer/*.ini` | only `preset_names`, `preset_name`, `printer_technology`, `host_type` (`core.prusa.PHYSICAL_KEYS`). Every other line is dropped as the file is read |
| `printer/*.ini`, `print/*.ini`, `vendor/*.ini` | every key but the private ones (`print_host`, `printhost_*`, `octoprint_*`, any key ending in `_host` or holding `apikey`, `password`, `secret`, `token`) |
| `PrusaSlicer.ini` | `[presets]` (what is selected) and `[vendor:...]` (the installed models) only |

So no host, key or password is in any answer, log line, Library card or 3MF.

## Routes

| Route | Gives |
|---|---|
| `GET /api/prusa/printers` (`?system=1`) | `{dir, found, printers, current, notes, revision}`. Each printer: `{name, technology, host_kind, presets, preset, printer, prints, current, current_print}`. `printer`: `{preset, source (user / system), inherits, nozzle_mm, extruders, model, variant, notes, technology, family, bed_mm, bed_shape, max_height_mm, layer_mm [min, max], default_print, default_filaments}`. `prints`: the print presets that fit (`fits`: yes / maybe), "Aruco" ones first: `{name, fits, user, aruco, line_mm, layer_mm, first_layer_mm, nozzle_mm, current}`. `system=1` adds the bundle's print presets that fit. `current`: `{physical, printer, print}` as PrusaSlicer has them selected. No folder: `found: false`, a note |
| `POST /api/scene/send/prusaslicer` | body `{printer, print, filament, white_slot (1), black_slot (2), open (true), bed_w_mm, bed_d_mm, margin_mm (5), spacing_mm (5)}`, every key optional. `printer` is a physical printer's name or a printer preset's; absent: the one PrusaSlicer has selected. `print` absent: the selected one when it fits, else the first fitting "Aruco" print. Answer `{project, parts, beds, skipped, rejected, warnings, opened, printer: {physical, preset}, print, filament, bed_mm, schema}`. The project is written to `exports/<scene>/prusaslicer/<scene>.3mf`; PrusaSlicer is opened only when `open` is true (`--single-instance`, the project as a project) |
| `GET /api/prusa/stale` | `{stale: [{tag, preset, field: "preset", level: "info", text, was, now, apply}]}`: tags whose preset came from a PrusaSlicer profile that changed. Text: "the profile changed: line 0.68 -> 0.65 mm; Apply?". Nothing is applied; `apply` names the route a click calls (`POST /api/preset/apply`) |
| `GET /api/prusa/watch` | `{running, dir, revision, last_ms, broken}` |

| Status | When |
|---|---|
| 400 | `nothing to slice: stickers print on paper` (only sticker tags), `nothing to slice: the scene has no 3D tag`, or nothing fits the bed |
| 404 | no such printer, print preset or filament |
| 422 | a bad body, or the black and the white on one slot |

## The library

`GET /api/library` gains two collections:

| Collection | Cards |
|---|---|
| `printers` (Printers) | one per physical printer, `kind: "printer"`: `printer` (as above), `choices` (its fitting prints, each with its own `id` = `printer:<name>|<print>`), `default`, `current`. `POST /api/library/select` with a choice's id (or the card's id for its default) makes a preset from the pair, the printer's nozzle and the print's line and layers, saves it as yours (`"<printer> · <print>"`) and answers `{name, preset}`. The preset carries `profile.printer = {physical, preset, model, variant}` |
| `stickers` (Sticker printers) | M6a's sticker built-ins and your sticker presets |

## Events

`prusa` on `GET /api/events`: `{revision, added, removed, changed, files, ms, stale}`. Keys are `physical_printer/<name>`, `printer/<name>`, `print/<name>`, `vendor/<name>`, `selection`. `ms` is the re-read (read, resolve, diff). A file that does not parse is kept at its last good read with no event; after three ticks still broken, one `prusa {broken: [file], message}`.

## The 3MF

One object per part: an extruded body with every 3D tag on it (the forearm is one part), or a 3D tag on a bare shape. Stickers are left out. Volumes, in order: the body (`ModelPart`, the white slot), then per tag its white (`ModelPart`, white slot), its black (`ModelPart`, black slot) and what it removes from the body (`NegativeVolume`). Empty ones are left out. The config (`Metadata/Slic3r_PE.config`) is the chosen printer's whole chain, the print's and the filament's, with the white and black colours on their slots. The bed is the printer preset's `bed_shape`; the MMU's wipe tower keeps its hole.
