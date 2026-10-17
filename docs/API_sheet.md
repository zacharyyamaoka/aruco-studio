# ArUco Studio: stickers, the sheet and the print bundle (M6a)

The routes and shapes M6a added. The rest of the API is in `docs/API.md`.

| | |
|---|---|
| Code | `aruco_studio/server/sheet_api.py` (routes), `scene/sheet.py` and `scene/export.py` (what they write), `core/sheet.py` (the layout and the files), `verify/sheet_check.py` (the WYSIWYG check) |
| Included by | one line in `server/app.py`: `from . import sheet_api` (the routes are put first, before `/api/scene/export/{fmt}` and the web app) |
| Tests | `tests/server/test_make_api.py` (TestClient; no port is bound) |

## How a tag is made

| Key | Values | Absent |
|---|---|---|
| `settings.make` | `{"rule": 1, "by": "print3d"}` or `{"rule": 1, "by": "sticker", "thickness_mm": 0.1, "margin_mm": 0, "cut_line": true, "perimeter": "marker" / "profile"}` | a 3D printed tag, exactly as before |
| `settings.holes` | `"avoid"` / `"ignore"` | avoid |
| `settings.label.rule` | 1, 2, or 3 (3: a ChArUco label by hand in any black square) | 1 |

Junk in any of them reads as the default with a `warn` on its key path. A new tag (`/api/new`) always stores `make`, `holes: "avoid"` and label rule 3.

### Make rule 2 and Shift (2026-10-17, the 2D pivot)

| Key | Values | Absent |
|---|---|---|
| `settings.make` (rule 2) | `{"rule": 2, "by": "sticker", "thickness_mm": 0.1, "perimeter": "marker" / "profile", "page": "letter", "page_margin_mm": 10}`: what a new inkjet sticker stores under a vinyl preset (`profile.make_rule: 2`) or with no sticker preset. A `margin_mm` / `cut_line` on it is read as 0 / on with an `info` (they are the sheet's: below) | -- |
| `settings.shift` | `{"rule": 1, "x_mm": 8.0, "y_mm": -6.0}`: a sticker moved off where the fit puts it, along its target's own u / v (±500 mm). A 3D tag reads it and does not move (an `info`) | centred, as before |

A rule-2 plan: `parts: ["sticker", "pocket", "ink"]`; layers `sticker` (white, z 0..t, the cut outline), `pocket` (the black's footprint, t/2..t, cut from the sticker) and `ink` (black, t/2..t); `combines` sticker new, pocket cut into sticker, ink new; the frame on the paper's top (`frames.detector_z_mm` = `surface_mm` = t); `marker.depth_m` = t/2; and `sticker`: `{rule, thickness_mm, paper_z_mm, ink_z_mm, frame_z_mm, perimeter, page: {page, margin_mm, size_mm, fits, how, over_mm, printable_mm}}`. The page lint: a sticker whose cut outline does not fit the printable area (`core.sheet.printable_options`: the page less its margins, the footer and the scale bars, portrait or landscape, either way round) gets an `error` Issue on `numbers.size` (Profile: on `settings.make.perimeter`) and stays `ok: true`. On Auto size a rule-2 Marker sticker is capped to the page (an `info` on `numbers.size`). A shifted plan has `placement.shift_mm`.

A sticker's TagPlan: `made_by: "sticker"`, `parts: ["sticker", "ink"]`, layers `sticker` (white, z 0..t) and `ink` (black, z t..t + 0.01), the frame on the ink top (`frames.detector_z_mm` = t + 0.01), `guides.cut_line` (`{kind, outer, holes}`, Marker also `rect`), `record.fusion.make`. Every plan has `made_by` and `rules.make` (1, or null without the key), and `guides.target_ignored` (the holes Holes: ignore leaves out).

## Presets: the machine

| Route | Change |
|---|---|
| `GET /api/presets` | the sticker printers too ("Sticker · Letter · 600 dpi", "Sticker · A4 · 600 dpi"); each item has `made_by` (its profile's kind); `collections`: `[{id: "print3d", title: "3D printers", names}, {id: "sticker", title: "Sticker printers", names}]`; `?made_by=sticker` keeps one kind |
| `POST /api/new` | `preset` may be a sticker printer: the tag is a sticker (`make`, whole-dot `cells`, label stroke 0.2 mm, no trim, no pins); `made_by` (`"print3d"` / `"sticker"`) overrides the preset's kind |

A preset's `profile` may carry `kind` (`"print3d"` / `"sticker"`), `dpi`, `page`, `landscape`, `margin_mm`, `stock_mm`, `sheet` (`"spaced"` / `"tight"`), and (2026-10-17) `make_rule` (2 on the vinyl presets; absent = 1). Without `kind` it is a 3D printer; the file stays `bam_aruco_presets/1`.

2026-10-17: every label says **Inkjet printer** (the stored kind stays `"sticker"`); the collection is "Inkjet printers". The built-ins new tags get are "Inkjet · Letter vinyl" and "Inkjet · A4 vinyl" (make rule 2, paper 0.10 mm, page margins 10 mm, 600 dpi). "Sticker · Letter · 600 dpi" and "Sticker · A4 · 600 dpi" stay for the files that name them, `legacy: true` in `GET /api/presets` (the Studio lists them only for a tag that has one; the Library keeps them in Built-in). `POST /api/preset/apply` with an inkjet preset makes the tag that preset's sticker (its rule, paper, page; the Perimeter kept). `GET /api/library`: an inkjet card has `edit: "2d"` and the state `schema_2d` (Inkjet printer, Paper size, Paper thickness, Page margins, Dots per inch, then the cells, tag and label rows).

## The sticker sheet

Common query / body fields: `page` (`letter` default, `a4`, `legal`, `a3`, `tabloid`, `a5`), `landscape`, `margin_mm` (10: the page's margins), `mode` (`spaced` default / `tight`), `proofs` (false: the 3D tags stay off the paper), and (2026-10-17, Zach's Q7: "Only in export sheet") `sticker_margin_mm` (0 to 20, default 0: white paper round each sticker, its cut outline grown that much, the holes as they are; sheet.json's `outline_mm` is the grown one and it carries `sticker_margin_mm`) and `cut_lines` (default true: false draws no cut line and no crop mark; sheet.json says `cut_lines: false`; the WYSIWYG check then skips the outline step).

| Route | Gives |
|---|---|
| `GET /api/scene/sheet.svg` | the sheet as SVG, mm, y down, pages stacked; each sticker an invisible `<rect data-sticker data-page data-x data-y data-w data-h data-rotation>` |
| `GET /api/scene/sheet.json` | `arucostudio.sheet/1`: per sticker `key, name, made_by, ids, page, x_mm, y_mm, w_mm, h_mm, rotation, box_mm, origin_mm, outline_mm, outline_page_mm, caption`; `shelves`, `cuts`, `rejected` (with the reason), `ruler` |
| `GET /api/scene/print.pdf` | the sheet as `application/pdf`, `Content-Disposition: inline`: the bytes `export/print` writes as `sheet.pdf` the same day; the MediaBox is the page, so 100 % is the viewer's default |
| `POST /api/scene/export/print` | `{..., bed_w_mm, bed_d_mm, black_slot (2), white_slot (1), inline}`: writes `exports/<scene>/sheet.pdf`, `sheet.svg`, `sheet.json`, `images/`, `print3d/` (STLs, `parts.json`, `aruco_tags.3mf`, `beds/`, `parts/`) and `markers.json`; marks every exported tag's ids printed in the scene's ledger. Answers `{stickers, parts, pages, beds, rows, rejected, files, dir, written}` (`inline`: the sheet's and markers.json's bytes, base64) |
| `POST /api/scene/export/print` with `sheet_only: true` | the Sticker sheet dialog's Export: the sheet's files, `images/` and `markers.json` only, no `print3d/` (the 3D parts are Send's); only the stickers' ids are marked printed (audit 2026-10-17) |
| `POST /api/scene/export/reveal` | `{open}`: the OS file browser on `exports/<scene>/`; `open: false` answers the command only (`{dir, command, opened}`) |
| `POST /api/scene/verify/sheet` | `{..., dpi (600)}`: the scene's sheet rasterised by pdfium and checked against each plan: per sticker `ink_xor`, `ids` (read, `side_err_mm`, ChArUco corners), `label` (`iou_min`), `outline` (`hausdorff_mm`, holes found); per page the two bars; `worst`; `ok` |

| Mode | Layout |
|---|---|
| spaced | 4 mm between stickers, the caption under each (`#12 · forearm_left · 4X4_50 · 28.0 mm`), crop marks outside each corner |
| tight | no gap: stickers of one height in one shelf, shelves stacked; every shelf line and column line a straight cut (`cuts`); no captions, one grey line per shelf in the left margin |

Every sticker is drawn from its plan: the black is the plan's top view, the grey hairline (0.55 grey, 0.1 mm) is its cut line with every hole (a hole under 3 mm also gets a cross). A sticker is turned 90 degrees when only that fits; one bigger than the page is rejected with a reason, never scaled.
