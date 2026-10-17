# The kit: @bam/ui

The compact UI kit the Studio is built on, and the one the other tools will use (M8d copies it into cad-exporter's `app/`). It lives in `studio/packages/bam-ui/` and the Studio imports it as `@bam/ui`.

| | |
|---|---|
| Stack | React 19, Tailwind 4, `@base-ui/react` (headless, accessible controls), `lucide-react`, `cmdk`. The same as the CAD Exporter cockpit |
| Look | light by default, dark as a toggle. 12 px text, 24 px rows, 6 px gaps. Inter when installed, else the system font |
| Build | `npm --prefix studio run build` checks the app and the kit (`npm run build:kit` is the kit alone: `tsc -p packages/bam-ui`) |
| Tests | `npm --prefix studio test` runs the kit's `formModel.test.ts` with the app's tests |
| Use it | import `@bam/ui/tokens.css` once, call `initTheme()` at start, register your own glyphs with `registerGlyphs()` |

## Tokens

Every colour is a CSS variable on `<html>`. `data-theme="dark"` swaps them. The kit and the Studio use only these.

| Token | Light | Dark | For |
|---|---|---|---|
| `--bg` | #f3f4f6 | #15181d | the page |
| `--panel`, `--panel-2` | white, #f7f8fa | #1c2026, #21262d | panels, headers and footers |
| `--field` | white | #14171b | inputs |
| `--line`, `--line-soft` | #dadee4, #eceef2 | #323943, #272d35 | borders |
| `--text`, `--muted` | #1c222b, #6b7480 | #e5e8ec, #8d96a3 | words |
| `--accent`, `--accent-soft` | #2f6fed | #5b8ff0 | the lit thing |
| `--ok`, `--warn`, `--bad` | green, amber, red | lighter ones | messages |
| `--canvas`, `--canvas-3d`, `--grid*`, `--shape-*` | | | the Studio's 2D and 3D views |
| `--row`, `--ctl`, `--gap`, `--radius` | 24 px, 22 px, 6 px, 6 px | | the density |

`useTheme()` gives the theme and a setter. The choice is kept in the browser (a convenience: the page works without it). `token("--canvas-3d")` reads a token for code that cannot use CSS, such as three.js.

## Components

| Component | What it is | Test hooks |
|---|---|---|
| `Button`, `IconButton` | text button (default, primary, ghost); icon button | `data-testid` |
| `Select` | a choice on base-ui Select: icons, hints, groups, a placeholder, a mixed state ("—") | root `.kit-select[data-path][data-value][data-open]`; list `.kit-select-popup[data-for=<path>][data-open]`; option `[role=option][data-value]` |
| `NumberField` | typed text, Enter commits, Esc reverts; a unit; arrows step; drag the unit to scrub; mixed | `input[data-path]` |
| `TextField` | Enter or blur commits, Esc reverts | `input[data-path]` |
| `Switch` | on / off on base-ui Switch | `[role=switch][data-path]` |
| `SegmentedRow` | one choice as a row of buttons | `.kit-seg[data-path][data-value]`, each `[data-value]` |
| `Tabs` | icon + name, a dot in the worst message's colour | `[role=tab][data-tab]` |
| `Dialog` | base-ui Dialog: title, body, footer | `data-testid` on the popup |
| `Menu`, `MenuItem`, `MenuSeparator` | base-ui Menu for a toolbar | items: `data-testid`; off: `data-disabled` |
| `Tooltip`, `TooltipProvider` | base-ui Tooltip for icon-only controls | |
| `Badge` | a small pill (2D / 3D, counts) | |
| `Kbd`, `ToolButton` | a key cap; a toolbar tool with its key badge, lit when active | `data-key`, `data-active` |
| `CommandPalette` | cmdk: every command by name and key | `[cmdk-item][data-command]` |
| `FieldRow`, `Field`, `Section`, `Messages` | a 24 px row with its messages under it; a titled section | `[data-row]`, `[data-issues-for]` |
| `LibraryShell` | a library window: collections, search, cards, a side panel, a footer | `[data-coll]`, `.card[data-card][data-mark]` |
| `Form` | renders a `bam.form/1` field list (below) | `[data-tab-body]`, `[data-row]` |
| `Glyph`, `registerGlyphs`, `themed` | 16 px glyphs by name; a tool registers its own; `themed` turns fixed colours into tokens | `[data-icon]` |

An open list, menu or dialog carries `data-kit-popup` and `data-open`. A tool's global keys wait while one is open. A closed `Select` never picks by typing, so a tool's single-letter keys still reach the tool.

## bam.form/1

The contract between a server's field list and any form. ArUco Studio serves it at `GET /api/form` from `aruco_studio/plan/fields.py`. The form draws; it never keeps a second copy of the fields.

The document: `{contract: "bam.form/1", fields: [...], tabs: [{id, name, icon}], outside: [...]}`. `outside` names rows the tool draws itself (ArUco Studio: `target`, `preset`, `name`), so messages can anchor to them.

A field:

| Key | Meaning |
|---|---|
| `path`, `type`, `label`, `default` | the key path, `choice` / `bool` / `int` / `number` / `mm` / `text` / `rule` / `object` / ..., the words, the value when absent |
| `choices` | `[{value, label, icon}]`; the icon is a glyph name |
| `tab` | a tab's id, `root` (above the tabs), `header` (the tool's head), `none` (drawn elsewhere) |
| `show_when` | `{layouts, made_by, target, values: {path: [..]}, truthy: [path], any_truthy: [path]}`. Every key given must hold. Absent: always shown |
| `anchor` | where this row's messages go while it is hidden: another row, or a row of `outside`. Anchors chain |
| `unit`, `step`, `drag` | mm / modules / deg; the step of an arrow key or a scrub (typed values are never rounded); a handle kind (`size-arrow`, `height-arrow`, `label-xy`) |
| `read_only`, `preset` | shown, not edited; true when a print preset writes it |
| `min`, `max`, ... | limits, as the server checks them |

The pure rules are in `formModel.ts`: `shows(row, ctx)`, `visibleRows(rows, ctx)`, `routeIssues(issues, rows, shown, outside)`, `summaryLine`, `common` (one value, or mixed). A message goes to the deepest row its key path names; when that row is hidden, to its anchor, then the anchor's anchor; with none, to the summary's own line.

`Form` props: `rows`, `tabs`, `ctx` (`get(path)`, `layout`, `made_by`, `target`), `issues`, `outside`, `tab`, `onTab`, `value(path) -> {value, mixed}`, `onChange(path, value)`, and optional `control` (a tool's own control for some paths), `labelOf`, `slots` (`root:before`, `<tab>:after`, ...: given the routed messages), `disabled`, `local`. A tab shows only when it has a row (or a slot) to show.
