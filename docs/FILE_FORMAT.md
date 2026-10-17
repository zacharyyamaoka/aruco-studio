# The design file: `arucostudio.scene/2`

A scene is one JSON text file. A person or an AI types it; the Studio opens it, draws it, and writes it back on every action. It holds sketches of shapes, features (Extrude and ArUco Extrude) and the ids. This is the reference; the design is `docs/design/M8_mini_cad_file_first.md` section 1. Built in M8a.

| | |
|---|---|
| Extension | `.arucostudio.json` (the same as `/1`) |
| Schema | `"schema": "arucostudio.scene/2"` |
| Code | `scene/design.py` (the model, the compile, the edits), `scene/file.py` (read, write, the `/1` migration), `plan/shapes.py` (shapes to loops, faces to Targets) |
| Examples | `examples/plate_charuco.arucostudio.json`, `examples/forearm.arucostudio.json`, `examples/sticker_sheet.arucostudio.json` |
| Check one | `python -m aruco_studio check <file>` |

## 1. Units and ids

Lengths are mm. Angles are degrees, counter-clockwise. A sketch's frame is x right, y up, z out of the sketch plane.

Every `id` is a short string without dots or spaces, unique in the whole file: sketches, shapes and features share one namespace. A reference is a bare id (`"plate"`) or a body's face (`"body.top"`).

A `"note"` key is allowed anywhere and kept. Any other key the Studio does not know is kept too, and reported as an `info`.

## 2. The file

| Key | Holds |
|---|---|
| `schema` | `"arucostudio.scene/2"` |
| `name` | the scene's name |
| `preset` | the print preset of every tag that names none (a Library name) |
| `sheet` | the sticker sheet's defaults, e.g. `{"page": "letter", "mode": "tight"}` (kept for M6) |
| `sketches` | `[sketch]` |
| `features` | `[feature]`, in order |
| `overrides` | `{tag name: first id}`: typed ids (as `/1`) |
| `ledger` | the numbering's ledger: printed ids never move (as `/1`) |
| `presets_used` | the presets named, as `/1` kept them (written only when it is not what the file names) |

## 3. Sketches and shapes

A sketch: `{"id", "at": [x, y], "rot": deg, "shapes": [shape]}`. `at` and `rot` place it on the canvas (default `[0, 0]` and `0`).

A shape is one of the five below, with `"id"`, `"at": [x, y]` (its centre in the sketch), `"rot"`, `"name"` and `"holes": [shape]`. A hole sits in its shape's frame, by its own `at` and `rot`. A hole never has holes.

| Shape | Written as | Its loops |
|---|---|---|
| rectangle | `"rect": [w, h]` | 4 points, counter-clockwise from the bottom-left corner. A rectangle without holes plans as a box (`loops_mm = []`, today's convention) |
| circle | `"circle": d` (the diameter) | stroked at the chord tolerance, 0.05 mm, the way Fusion strokes an edge (`core.faces`) |
| polygon | `"polygon": [[x, y], ...]` | as typed, made counter-clockwise (the first point kept first) |
| slot | `"slot": [length, width]` | two lines and two half circles; `length` is the overall length |
| loops | `"loops": [[[x, y], ...], ...]` | verbatim: the outer loop first, then holes. What a `/1` file, a Fusion face or a build123d face brings in |

The outer loop is counter-clockwise. Each hole is clockwise and must lie inside it; a hole outside (or across the edge) is an `error` on `sketches[i].shapes[j].holes[k]`.

## 4. Features

| Feature | Written as | Does |
|---|---|---|
| Extrude | `{"id", "extrude": "<shape>", "height": h}` | the shape's prism from z 0 to `h` (negative: downwards): a body |
| ArUco Extrude | `{"id", "aruco": "<shape>" or "<body>.<face>" or a list of them, ...}` | a tag on that profile or face. A list makes one tag per face with the same settings |

### The faces of a body

| Face | Is | Its frame (right-handed) |
|---|---|---|
| `<body>.top` | the shape at the top of the prism | the shape's frame, at the top's height |
| `<body>.bottom` | the shape seen from below: its loops mirrored (u -> -u), `z_sign = -1` | u = -x, v = y, z = down |
| `<body>.side<i>` | the flat side on straight edge `i` of the outer loop, counted counter-clockwise | u along the edge, v = up, z = the outward normal |
| `front`, `right`, `back`, `left` | a rectangle's sides 0..3 (-y, +x, +y, -x) | as `side<i>` |

A circle's side is curved: a tag on it is an `error` that says "curved". A slot has two flat sides (`side0` at the bottom, `side1` at the top); its ends are curved.

A side face plans as a box: its width is the edge's length, its height the body's height, and the body under it is as deep as the body reaches along the inward normal (exact for a rectangle's extrude, an upper bound for a polygon's).

### Tag names

A tag on one reference is named by its feature's id. A list names its tags `<id>.<face>`: the forearm's feature `tag` gives `tag.front`, `tag.right`, `tag.back`, `tag.left`. A tag's uid (the ledger's stamp) is its name, or `<uid>.<face>` when the feature keeps an old `uid`.

## 5. The keys of an ArUco Extrude

Two kinds of keys: **sugar**, short to type, and the **exact** dicts the Studio writes.

### Sugar

Sugar expands through the new-tag rule (`plan/newtag.new_spec`: what POST /api/new and the Fusion dialog store for a fresh tag: `origin_v`, the label's `rule`, `cells` from the preset, Auto Extrude resolved against the target), then each key below is laid on top.

| Key | Writes | Note |
|---|---|---|
| `preset` | the print settings the preset carries | a Library name; absent: the file's `preset`, else Default. An unknown name is a `warn` and Default is used |
| `layout` | `settings.layout` | `single`, `grid`, `charuco` |
| `dictionary` | `settings.dictionary` | |
| `first_id` | `overrides[<tag name>]` and `numbers.marker_id` | a typed first id; on a list, a list of them (`null` = auto). See section 9 |
| `size`, `square` | `numbers.size`, `numbers.square` | 0 or absent = Auto; a number turns Auto off |
| `cols`, `rows` | `settings.force` | together. A face lays out as many as fit (REF's fit; an `info` says so); a sketch profile takes the count |
| `turn` | `settings.turn` | |
| `mark` | `settings.corner_mark` | `none`, `cut`, `triangle` |
| `pins` | `settings.pin` | |
| `holes` | `settings.holes` | M6's `avoid` / `ignore` |
| `perimeter` | on a tag with a body, `settings.trim` (`profile` = `both`, `marker` = `off`); else `settings.make.perimeter` | M6's Perimeter |
| `mode`, `op` | `settings.mode` (Auto resolved), `settings.op` | |
| `label` | `settings.label` | `"#id"`, `"#id + name"`, `"name"`, `"Dictionary #id"`, any other text (custom), `false` (off), or an object of label settings |

### Exact

| Key | Is |
|---|---|
| `settings`, `numbers` | the exact dicts. When present, they are the tag's, as they stand: the sugar for that dict is not used (an `info` says so) |
| `name` | the tag's `name` (the label's `{name}`) |
| `key` | the record's key, when it is not the tag's name |
| `marker_ids` | on a list: each face's first id, when they differ |
| `over` | a body's id: the shape is a sketch area over that body (Fusion's profile case: `target.kind = "profile"`) |
| `target` | the exact Target, when the shape cannot say it (a sketch profile, a flipped face, a measured body): what the `/1` migration and the old routes write |
| `uid` | the ledger's stamp, when it is not the tag's name (a renamed tag, a `/1` tag) |
| `locked`, `hidden` | a printed tag; a hidden one |

**On its first write the Studio replaces the sugar with the exact `settings` and `numbers`.** A hand-typed file stays short until the Studio touches that feature; after that it is exact and round-trips bit for bit. A typed `first_id` moves into `overrides`.

A list stays one feature while its faces agree (their ids aside: `marker_ids`). The moment one face differs (another mark, another size), the list splits into one feature per face, each named as its tag was (`tag.right`).

## 6. Three complete files

They are in `examples/`, as the design note has them.

| File | Holds |
|---|---|
| `plate_charuco.arucostudio.json` | a plate 80 x 50 with a Ø18 hole, 5 mm thick, a ChArUco 5 x 3 on its top |
| `forearm.arucostudio.json` | a box 120 x 40 x 40 with one ChArUco on each of its four sides |
| `sticker_sheet.arucostudio.json` | four stickers on bare shapes: two singles, a grid, a ChArUco on a disc with a hole |

## 7. What it compiles to

`scene/design.compile(doc, presets) -> (Scene, [Issue])`. The result is today's `Scene`, so the plan, the numbering, the sheet and the exports run unchanged.

| File | Becomes |
|---|---|
| a shape | `Target.loops_mm`: its outer loop, then its holes |
| a tag on a bare shape | a Target with no body: a rectangle without holes through `plan/target.box(w, h, 0)`, anything else through `from_loops(loops, 0, centre=False)`: the same calls POST /api/target makes |
| a tag on `<body>.top` | the same, with the body's height: the outline extruded down |
| a tag on `<body>.bottom` / `.side<i>` | as section 4 |
| the sugar, `settings`, `numbers` | `TagSpec.settings`, `.numbers`, `.name`, `.key` |
| the sketch's and shape's place, the face | the tag's canvas place (`x_mm`, `y_mm`, `rotation_deg`) and, when it is not z-up at z 0, `pose_3d` (a 4x4, mm) |

**The 2D view.** A tag on a top (or a bare shape) sits where its shape is. A tag on a side is placed unfolded about its edge, like the net of a box: hinged at the top edge, outside the shape. The bottom hangs below the front side's flap. `source.hinge_xy` is the edge a side folds about. `pose_3d` is where it really stands.

Issues carry their JSON path in `field` (`features[1].aruco[1]`). A parse error carries its line and column. The plan's own messages and the scene's (overlaps) stay where they were.

## 8. Versions

| Rule | |
|---|---|
| Writers | always `/2`, `indent=1, sort_keys` |
| `/1` | migrated on read: each tag a sketch at its place holding one shape (a box target writes `rect`, any other its `loops`), an Extrude downwards when the target had a body (so its face stays at z 0), and an ArUco Extrude with the exact `settings` / `numbers` (and the exact `target` only when the shape cannot say it). Its uid, key, lock, the ledger and the overrides are kept. A migrated tag replans byte for byte |
| A newer schema | refused: "saved by a newer ArUco Studio?" |
| An unknown feature | an `error` on that feature; the rest compiles |
| The versioned rules | untouched: a tag's `settings` / `numbers` are its record |

## 9. Where this differs from the design note

| Note | Built | Why |
|---|---|---|
| a typed first id is the key `id` | `first_id` | a feature's `id` is its own id; one key cannot be both |
| a tag on a bare shape is `kind: "free"` | `kind: "face"` with no body | that is what POST /api/target makes, and `free` changes REF's fit (a sketch area: typed counts, bigger tiles); M8a.1 compares against the target editor |
| an extrude goes from z 0 up | so it does; the `/1` migration and the old routes write a negative height | their tags keep their face at z 0, as before |
| `settings` / `numbers` "over everything above" | when present they ARE the dict, sugar for it unused | a merge would put a later default into an exact record and change its plan |
| (not in the note) | `target`, `key`, `uid`, `locked`, `hidden`, `marker_ids`, `presets_used` | what a `/1` tag carries, and a list's ids after Renumber |

## 10. Live reload

The server follows the open file (`server/watch.py`, every 250 ms): an outside change is parsed, compiled and pushed over `GET /api/events`. Its own writes and a rewrite of the same text are not changes (sha256). A file that does not parse keeps the last good scene and blocks every write until it parses. A deleted file stops the writes. docs/API.md has the routes.
