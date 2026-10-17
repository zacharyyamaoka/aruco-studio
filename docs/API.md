# ArUco Studio: the API

The Studio's server: FastAPI on `127.0.0.1:5360`. The web app (M3) and any script talk to it. The full typed schema is `GET /openapi.json` (the web app generates its TypeScript types from it).

| | |
|---|---|
| Start | `.venv/Scripts/python -m aruco_studio.server` (127.0.0.1:5360; `--port` to move it, never 5322 / 5331 / 5340 / 5350 / 8080) |
| Stop | Ctrl+C in its window |
| Code | `aruco_studio/server/app.py` (routes), `design_api.py` (the design file, its watcher, the events), `models.py` (shapes), `store.py` (every file it touches) |
| CORS | `http://127.0.0.1:5361`, `http://localhost:5361` (the Vite dev server) |
| Web app | `studio/dist/` is served at `/` once it is built |
| Tests | `tests/server/` (TestClient for every route; one test starts uvicorn on 5360 and stops it) |

## Where files go

| What | Where | Override |
|---|---|---|
| user presets | `ROOT/.studio_data/aruco_presets.json` (REF's `bam_aruco_presets/1`) | `ARUCO_STUDIO_HOME` |
| remembered options | `ROOT/.studio_data/remembered.json` | `ARUCO_STUDIO_HOME` |
| exports | `ROOT/.studio_data/exports/<scene>/` | `ARUCO_STUDIO_HOME` |
| scenes | `ROOT/scenes/<name>.arucostudio.json` | `ARUCO_STUDIO_SCENES` |
| an open design file | anywhere (`POST /api/design/open`, `--open`); never under `%USERPROFILE%\CADExporter` or PrusaSlicer's folder | |
| PrusaSlicer profiles | read only: `%APPDATA%/PrusaSlicer` | `BAM_ARUCO_PRUSASLICER_DIR` |

A path under `%USERPROFILE%\CADExporter` is refused, even when a variable points there. `.studio_data/` and `scenes/` are git-ignored.

## Errors

| Status | When | Body |
|---|---|---|
| 422 | a wrong TYPE: a string where a number goes, a missing required key, an unknown `schema` | `{"detail": [{"loc", "msg", "type", "path"}]}`; `path` is the key path, e.g. `numbers.size`, `settings.quiet_modules` |
| 200 with `ok: false` | a wrong VALUE that stops the tag (nothing fits, ids past the dictionary, pins that do not fit) | the TagPlan: `errors`, and an `error` Issue on the field |
| 200 with Issues | a wrong value the plan can live with (a refused label, junk trim read as off) | `warnings`: `[{field, level, text}]` |
| 400 | a refused export (a refused plan), a bad preset name, a scene file of an unknown schema | `{"detail": "..."}` |
| 404 | an unknown tag, scene or export format | `{"detail": "..."}` |
| 409 | an edit of a locked (printed) tag that would change its ink | `{"issues": [{field, level, text}]}` |
| 409 | a change while the open design file does not parse ("file not parseable: line N col M ..."), is gone ("file missing ...") or changed on disk since the server read it (reloaded; the action dropped) | `{"detail": "...", "state", "error"}`; nothing is written |

## Routes

### Reference

| Route | Does |
|---|---|
| `GET /api/health` | `{ok, version, ref_commit, schemas, home, scenes}`. `schemas.scene` is the shape `GET /api/scene` answers (`/1`); `schemas.file` is the design file's (`arucostudio.scene/2`) |
| `GET /api/dictionaries` | the 21 dictionaries: `name, bits, capacity, family, modules` |
| `GET /api/options` | every choice the inspector offers, with the Fusion dialog's words (layouts, modes, ops, pins, corner marks, turns, label choices, trim, cells, limits) |
| `GET /api/form` | the inspector's field list (`plan/fields.py`): per field its key path, type, default, limits, choices; one row per row of ARCHITECTURE 5.6 |
| `GET /api/targets?thickness_mm=3` | the target palette: a box, a disc and REF's ten gallery faces, as Targets |

### One tag

| Route | Body | Gives |
|---|---|---|
| `POST /api/plan` (`?mesh=1`) | TagSpec | TagPlan; `mesh` per body (white / pattern / body) for the 3D view |
| `POST /api/validate` | TagSpec | `[Issue]` |
| `POST /api/candidates` | `{layout, dictionary, quiet_modules, cells, target, limit}` | the ranked Layout list (cols, rows, marker, square, badges) |
| `POST /api/auto_check` | TagSpec | `{auto, note}`: a tag stored with Auto and a number (made before 2026-10-13) keeps Auto only if Auto builds that same tag (`plan.auto`, REF `_check_auto`) |
| `POST /api/verify` | `{spec, px_per_mm, pose}` | OpenCV's read: `ids_expected`, `ids_read`, `missing`, `extra`, `corner_err_px` / `_mm`, ChArUco corners read, `pnp_err_mm` / `_deg`, `ok` |
| `POST /api/export/{svg,png,stl,json}` | TagSpec | the file: SVG 1:1 mm, PNG at 20 px / mm with pHYs, binary STL (mm), the TagPlan JSON |

### Presets and memory

| Route | Does |
|---|---|
| `GET /api/presets` | `{items: [{name, kind: builtin / user, preset}], last, notes, file}`: Default, PrusaSlicer's "Aruco" profiles (read only), then the user's |
| `POST /api/presets` | `{name, preset}`: save as a new user preset (`" (2)"` when taken) |
| `PUT /api/presets/{name}` | overwrite a user preset (a built-in: 400) |
| `DELETE /api/presets/{name}` | delete a user preset (a built-in: 400) |
| `GET /api/prusa/profiles` | PrusaSlicer's print profiles and the "Aruco" ones read (nozzle, line width, layers) |
| `GET /api/remembered`, `PUT /api/remembered/{command}` | what a panel remembers between runs (REF aruco_settings' file shape) |

### The scene

Since M8a the open scene is a design file (`arucostudio.scene/2`, docs/FILE_FORMAT.md; the next section). These routes answer as before: each one changes the compiled scene, writes the change back into the design document and writes the file, when there is one. A new scene lives in memory until Save or Save as.

| Route | Does |
|---|---|
| `GET /api/scene` (`?plans=1&mesh=1`) | the scene compiled from the design file, in the `/1` shape (tags with their whole TagSpec; its `"schema": "arucostudio.scene/1"` names that shape, not the file). Each tag also carries `source` (its feature, face, shape, sketch, a side face's hinge) and, when it is not z-up at z 0, `pose_3d`. With `plans=1`: each tag's TagPlan and `issues` (the scene's own messages: overlapping tags, `scene/checks.py`). Plans are cached by their spec: a change re-plans only what it changed. Headers: `X-Scene-Revision`, `X-Design-State` |
| `PUT /api/scene` | replace it: a design document (`/2`), or a compiled scene (the `/1` shape, e.g. the Studio's Undo), written back onto the open design (its sketches stay where its tags match by uid); an unknown schema: 400 |
| `POST /api/scene/new` | `{name}`: an empty design, in memory |
| `POST /api/scene/tags` | `{spec, x_mm, y_mm, rotation_deg, name?, locked?, number?}`: add a tag: a sketch at its place holding its target's shape, an Extrude when it has a body, an ArUco Extrude with the exact settings; gives it and its plan. `number: true` gives it the next free ids of its dictionary family at once (the Studio's Add) |
| `PATCH /api/scene/tags/{name}` | move (`x_mm`, `y_mm`, `rotation_deg`: moves its sketch, or its shape in a shared sketch), edit (`settings`, `numbers`: the exact dicts into its feature, the sugar gone; `target`: new parts of its own; `key`), `new_name` (its uid stays), `locked`, `hidden`; a locked tag's ink change: 409. A tag of a multi-face feature that no longer matches the others splits the list into one feature per face |
| `DELETE /api/scene/tags/{name}` | delete it, and the body, shape and sketch only it used |
| `POST /api/scene/tags/{name}/duplicate?dx_mm=&dy_mm=&number=1` | a copy with its own uid; `number=1` (default): the next free ids of its family |
| `PUT /api/scene/overrides/{name}` | `{id}` a typed first id: checked (0 or more; every id of the board inside the dictionary; not on a locked tag) and used at once: `{overrides, tag, ids}`; refused: 409 `{issues}` on field `override`. `{id: null}` back to auto (the ids stay until Renumber) |
| `POST /api/scene/renumber` | unique ids per dictionary family (core.numbering, the scene's ledger): `{rows, changed, duplicates, warnings, errors, ok}`; each row also has `tag` and `made_by` (`print3d` / `sticker`, the plan's; "" for a tag that does not plan) |
| `GET /api/scenes` | the files in `scenes/` |
| `POST /api/scene/save` | `{name}`: write `scenes/<name>.arucostudio.json` (`/2`) and follow it: every later change writes it |
| `POST /api/scene/open` | `{name}`: read it (a `/1` file is migrated) and follow it |
| `POST /api/scene/verify?px_per_mm=10` | the scene's sheet read back: every marker found, each centre against its place (mm); `overlaps` (tags whose targets overlap); `ok` is false when any overlap, `markers_ok` is the markers alone |
| `POST /api/scene/export/{svg,png,pdf,json,stl,plan}` | into `exports/<scene>/`: the 1:1 sheet (SVG / PNG), the PDF sticker sheet (REF's print sheet: A4, cut marks, `#id`, the ruler), the design file (`/2`), every tag's STL or plan |

### The design file (M8a)

`server/design_api.py`; the watcher is `server/watch.py`, the push `server/events.py`. Open a file at start with `python -m aruco_studio.server --open <path>`.

| Route | Does |
|---|---|
| `GET /api/design` (`?text=0`) | `{path, state, text, hash, revision, error, issues, schema}`. `state`: `memory` (no file yet), `ok`, `broken` (does not parse: `error.line`, `error.col`, `error.message`) or `missing`. `issues`: the compile's, each on its JSON path (`features[1].aruco`) |
| `PUT /api/design` | `{text, hash?}`: the Studio's write, the whole text, written verbatim (a `/1` text is migrated first). 422 when it does not parse (`line`, `col` in the detail); 409 when `hash` is not the file's, or the file is broken or missing |
| `POST /api/design/open` | `{path}`: open a design file anywhere and follow it. 404: no such file; 403: under `%USERPROFILE%\CADExporter` or PrusaSlicer's folder; 400: it does not parse |
| `POST /api/design/save_as` | `{path}`: write the open design there and follow that file |
| `POST /api/design/preview` | `{text}` (`?mesh=1&top=1`): `{scene (with plans), issues, error}`; nothing written or kept (a drag's preview) |
| `POST /api/design/reveal` | `{open: true}`: the OS file browser on the file; `open: false` only answers the command |
| `GET /api/design/files` | the Open dialog's lists: `{examples, recent, scenes, scenes_dir}` (`server/files_api.py`) |
| `POST /api/design/open_example` | `{name}`: the example copied into the scenes folder (a fresh name when taken) and opened; `examples/` is never written |
| `GET /api/design/browse` | `?dir=`: a folder's `*.arucostudio.json` and subfolders, `{dir, parent, folders, files}`; the scenes folder by default. 403 under the two forbidden folders |
| `GET /api/events` | server-sent events (`text/event-stream`): `hello {revisions, file}` on connect; `scene {revision, path, why}` when the file changed on disk; `file {state, path, error}` when it breaks, goes, or parses again. `prusa {revision, added, removed, changed, files, ms, stale}` when PrusaSlicer's folder changed (M8c, docs/API_prusa.md); `presets` is reserved. Each event's data has `t` (the server's clock). `?max_events=N&timeout=S` end the stream (tests, one-shot pollers) |

A typed file is frozen: on open, on an outside change and on every write the server copies the presets its sugar names into `frozen_presets` (scene/design.freeze) and writes that one key at the end of the text, the rest kept as typed. A design file opened or saved goes first in `<home>/recent_designs.json`.

The rules: the server's own writes are atomic, and their sha256 is remembered before they land, so they are never read back as a change. A rewrite of the same text (an editor's touch, a cloud sync) is no change. While the file does not parse, the last good scene stays and every write is refused. Before a write the server checks the file still holds what it last read; if not, it reloads, pushes the change and drops the action (409).

### The Studio (M3)

| Route | Does |
|---|---|
| `POST /api/new` | `{layout, target_key?, thickness_mm?, target?, preset?, marker_id?}`: a fresh tag's TagSpec as today's dialog stores it (`origin_v`, the label's `rule`, `cells` from the preset, Auto Extrude resolved against the target) |
| `POST /api/target` | `{shape: box / disc / face, key?, w_mm, h_mm, r_mm, holes: [[x, y, d]], thickness_mm}`: the target editor's Target. Since M8a it is made as a design shape (`rect`, `circle` or the face's `loops`, with `circle` holes; circles stroked at the 0.05 mm chord tolerance) and compiled as a tag on its top; a hole outside the shape: 422 on `holes[k]` |
| `POST /api/preset/apply` | `{spec, name or preset}`: the spec with the preset's print settings (layout, ids, size, Origin, target kept) |
| `POST /api/preset/of` | `{spec}`: `{preset, matches}`: the tag's print settings as a preset, and the catalog preset it equals |
| `GET /api/library?tag=` | the Library's state: collections with counts, cards (thumb, Info, what Select changes on `tag`), the Edit form |
| `POST /api/library/select` | `{id}`: `{name, preset}` to apply (a PrusaSlicer card is imported as yours first) |
| `POST /api/library/save` | `{id, name, values}`: Edit -> Save of one of yours (a new name renames). A value outside what a preset keeps: 422, one error per field path (the ranges are in `GET /api/library`'s `limits`) |
| `GET / POST /api/library/recent` | the recent presets (`{name}` puts one first) |
| `?top=1` on `/api/plan` and `/api/scene` | `top`: `{body, white, black}` polygons, what is seen from above (plan/mesh.top) |
| `image: true` in `/api/verify` | `image_png`: the raster OpenCV read (base64) |
| `inline=1` on `/api/scene/export/{fmt}` | the files' bytes too (base64), for a download |

## The shapes

| Shape | Schema string | Defined in |
|---|---|---|
| TagSpec | `arucostudio.tagspec/1` | `plan/spec.py`; ARCHITECTURE 5.2 |
| Target | (inside TagSpec) | `plan/target.py`; ARCHITECTURE 5.1 and PLAN section 8 |
| TagPlan | `arucostudio.tagplan/1` | `plan/plan.py`, `plan/layers.py`; ARCHITECTURE 5.3 and PLAN section 8 |
| Issue | `{field, level: error / warn / info, text}` | `plan/spec.py`; ARCHITECTURE 5.6 |
| Scene (compiled) | `arucostudio.scene/1` (the shape `GET /api/scene` gives; a `/1` file is migrated on read) | `scene/model.py`; ARCHITECTURE 5.5 |
| The design file | `arucostudio.scene/2` | `scene/design.py`, `scene/file.py`, `plan/shapes.py`; docs/FILE_FORMAT.md |

The sticker sheet, the print bundle and the presets as machines (M6a): docs/API_sheet.md.

PrusaSlicer's physical printers, the folder's watcher and Send to PrusaSlicer (M8c): docs/API_prusa.md.
