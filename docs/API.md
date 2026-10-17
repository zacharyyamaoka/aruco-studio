# ArUco Studio: the API

The Studio's server: FastAPI on `127.0.0.1:5360`. The web app (M3) and any script talk to it. The full typed schema is `GET /openapi.json` (the web app generates its TypeScript types from it).

| | |
|---|---|
| Start | `.venv/Scripts/python -m aruco_studio.server` (127.0.0.1:5360; `--port` to move it, never 5322 / 5331 / 5340 / 5350 / 8080) |
| Stop | Ctrl+C in its window |
| Code | `aruco_studio/server/app.py` (routes), `models.py` (shapes), `store.py` (every file it touches) |
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

## Routes

### Reference

| Route | Does |
|---|---|
| `GET /api/health` | `{ok, version, ref_commit, schemas, home, scenes}` |
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

The open scene lives in the server's memory. New / Open / Save move it to and from `scenes/`.

| Route | Does |
|---|---|
| `GET /api/scene` (`?plans=1&mesh=1`) | the scene (`arucostudio.scene/1`); with each tag's TagPlan and `issues` (the scene's own messages: overlapping tags, `scene/checks.py`). Plans are cached by their spec: a change re-plans only what it changed |
| `PUT /api/scene` | replace it (a scene document; an unknown schema: 400) |
| `POST /api/scene/new` | `{name}`: an empty scene |
| `POST /api/scene/tags` | `{spec, x_mm, y_mm, rotation_deg, name?, locked?, number?}`: add a tag; gives it and its plan. `number: true` gives it the next free ids of its dictionary family at once (the Studio's Add) |
| `PATCH /api/scene/tags/{name}` | move (`x_mm`, `y_mm`, `rotation_deg`), edit (`settings`, `numbers`, `target`, `key`), `new_name`, `locked`, `hidden`; a locked tag's ink change: 409 |
| `DELETE /api/scene/tags/{name}` | delete it |
| `POST /api/scene/tags/{name}/duplicate?dx_mm=&dy_mm=&number=1` | a copy with its own uid; `number=1` (default): the next free ids of its family |
| `PUT /api/scene/overrides/{name}` | `{id}` a typed first id: checked (0 or more; every id of the board inside the dictionary; not on a locked tag) and used at once: `{overrides, tag, ids}`; refused: 409 `{issues}` on field `override`. `{id: null}` back to auto (the ids stay until Renumber) |
| `POST /api/scene/renumber` | unique ids per dictionary family (core.numbering, the scene's ledger): `{rows, changed, duplicates, warnings, errors, ok}` |
| `GET /api/scenes` | the files in `scenes/` |
| `POST /api/scene/save` | `{name}`: write `scenes/<name>.arucostudio.json` |
| `POST /api/scene/open` | `{name}`: read it |
| `POST /api/scene/verify?px_per_mm=10` | the scene's sheet read back: every marker found, each centre against its place (mm); `overlaps` (tags whose targets overlap); `ok` is false when any overlap, `markers_ok` is the markers alone |
| `POST /api/scene/export/{svg,png,pdf,json,stl,plan}` | into `exports/<scene>/`: the 1:1 sheet (SVG / PNG), the PDF sticker sheet (REF's print sheet: A4, cut marks, `#id`, the ruler), the scene file, every tag's STL or plan |

### The Studio (M3)

| Route | Does |
|---|---|
| `POST /api/new` | `{layout, target_key?, thickness_mm?, target?, preset?, marker_id?}`: a fresh tag's TagSpec as today's dialog stores it (`origin_v`, the label's `rule`, `cells` from the preset, Auto Extrude resolved against the target) |
| `POST /api/target` | `{shape: box / disc / face, key?, w_mm, h_mm, r_mm, holes: [[x, y, d]], thickness_mm}`: the target editor's Target |
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
| Scene | `arucostudio.scene/1` | `scene/model.py`, `scene/file.py`; ARCHITECTURE 5.5 |
