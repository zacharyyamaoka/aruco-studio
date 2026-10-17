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

A sticker's TagPlan: `made_by: "sticker"`, `parts: ["sticker", "ink"]`, layers `sticker` (white, z 0..t) and `ink` (black, z t..t + 0.01), the frame on the ink top (`frames.detector_z_mm` = t + 0.01), `guides.cut_line` (`{kind, outer, holes}`, Marker also `rect`), `record.fusion.make`. Every plan has `made_by` and `rules.make` (1, or null without the key), and `guides.target_ignored` (the holes Holes: ignore leaves out).

## Presets: the machine

| Route | Change |
|---|---|
| `GET /api/presets` | the sticker printers too ("Sticker · Letter · 600 dpi", "Sticker · A4 · 600 dpi"); each item has `made_by` (its profile's kind); `collections`: `[{id: "print3d", title: "3D printers", names}, {id: "sticker", title: "Sticker printers", names}]`; `?made_by=sticker` keeps one kind |
| `POST /api/new` | `preset` may be a sticker printer: the tag is a sticker (`make`, whole-dot `cells`, label stroke 0.2 mm, no trim, no pins); `made_by` (`"print3d"` / `"sticker"`) overrides the preset's kind |

A preset's `profile` may carry `kind` (`"print3d"` / `"sticker"`), `dpi`, `page`, `landscape`, `margin_mm`, `stock_mm`, `sheet` (`"spaced"` / `"tight"`). Without `kind` it is a 3D printer; the file stays `bam_aruco_presets/1`.

## The sticker sheet

Common query / body fields: `page` (`letter` default, `a4`, `legal`, `a3`, `tabloid`, `a5`), `landscape`, `margin_mm` (10), `mode` (`spaced` default / `tight`), `proofs` (false: the 3D tags stay off the paper).

| Route | Gives |
|---|---|
| `GET /api/scene/sheet.svg` | the sheet as SVG, mm, y down, pages stacked; each sticker an invisible `<rect data-sticker data-page data-x data-y data-w data-h data-rotation>` |
| `GET /api/scene/sheet.json` | `arucostudio.sheet/1`: per sticker `key, name, made_by, ids, page, x_mm, y_mm, w_mm, h_mm, rotation, box_mm, origin_mm, outline_mm, outline_page_mm, caption`; `shelves`, `cuts`, `rejected` (with the reason), `ruler` |
| `GET /api/scene/print.pdf` | the sheet as `application/pdf`, `Content-Disposition: inline`: the bytes `export/print` writes as `sheet.pdf` the same day; the MediaBox is the page, so 100 % is the viewer's default |
| `POST /api/scene/export/print` | `{..., bed_w_mm, bed_d_mm, black_slot (2), white_slot (1), inline}`: writes `exports/<scene>/sheet.pdf`, `sheet.svg`, `sheet.json`, `images/`, `print3d/` (STLs, `parts.json`, `aruco_tags.3mf`, `beds/`, `parts/`) and `markers.json`; marks every exported tag's ids printed in the scene's ledger. Answers `{stickers, parts, pages, beds, rows, rejected, files, dir, written}` (`inline`: the sheet's and markers.json's bytes, base64) |
| `POST /api/scene/verify/sheet` | `{..., dpi (600)}`: the scene's sheet rasterised by pdfium and checked against each plan: per sticker `ink_xor`, `ids` (read, `side_err_mm`, ChArUco corners), `label` (`iou_min`), `outline` (`hausdorff_mm`, holes found); per page the two bars; `worst`; `ok` |

| Mode | Layout |
|---|---|
| spaced | 4 mm between stickers, the caption under each (`#12 · forearm_left · 4X4_50 · 28.0 mm`), crop marks outside each corner |
| tight | no gap: stickers of one height in one shelf, shelves stacked; every shelf line and column line a straight cut (`cuts`); no captions, one grey line per shelf in the left margin |

Every sticker is drawn from its plan: the black is the plan's top view, the grey hairline (0.55 grey, 0.1 mm) is its cut line with every hole (a hole under 3 mm also gets a cross). A sticker is turned 90 degrees when only that fits; one bigger than the page is rejected with a reason, never scaled.
