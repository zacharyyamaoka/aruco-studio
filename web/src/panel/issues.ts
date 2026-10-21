// Per-line validation: each plan warning goes under the row its field names.
// A field whose row is not drawn goes to the row that owns it (rows → the
// Columns × Rows row, checker → Marker, a hidden label field → Place or On,
// the other method's heights → Preset); what has no row at all goes to the
// summary line. The rows are listed per tab (Marker | Label | Manufacture, the
// skeleton: docs/design/panel_skeleton.md), so a tab's dot is the worst of its own rows. Pure: vitest covers it.
import type { Issue, IssueLevel, LabelParams, MarkerParams, Method } from "../core/contract";
import type { Tab } from "../store";

const OWNER: Record<string, string> = {
  // the box the marker is placed in (the legacy rect, or the core's fit_rect) is the profile's
  "rect": "profile",
  "holes": "profile",
  "marker.rows": "marker.cols",
  "marker.auto": "marker.marker_mm",
  "marker.checker_mm": "marker.marker_mm",
  "marker.separation_mm": "marker.marker_mm",
  "marker.cols": "marker.marker_mm",
  "marker.id": "marker.first_id",
  "marker.ids": "marker.first_id",
  // the heights of the other method (and a bare "extrude") are the preset's
  "extrude": "preset",
  "extrude.paper_mm": "preset",
  "extrude.mode": "preset",
  "extrude.white_mm": "preset",
  "extrude.black_mm": "preset",
  "marker.origin_square": "marker.type",
  "label.text": "label.on",
  "label.height_mm": "label.on",
  "label.side": "label.on",
  "label.gap_mm": "label.place",
  "label.surface": "label.place",
  "label.place": "label.on",
  "label.offset_mm": "label.on",
};

/** The rows each tab draws for these numbers, by field path, top to bottom. */
export function tabRows(m: MarkerParams, l: Pick<LabelParams, "on" | "place">, method: Method): Record<Tab, string[]> {
  const marker = ["profile", "preset", "marker.type", "marker.dictionary", "marker.first_id", "marker.marker_mm"];
  if (m.type !== "single") marker.push("marker.cols");
  if (m.type === "grid") marker.push("marker.separation_mm");
  if (m.type === "charuco") marker.push("marker.checker_mm", "marker.origin_square");
  marker.push("marker.suggest", "marker.turn", "marker.quiet_modules", "feature.key");
  const make = ["marker.size_step", "trim"];
  if (method === "print3d") make.push("extrude.mode", "extrude.white_mm", "extrude.black_mm");
  else make.push("extrude.paper_mm");
  make.push("marker.flip");
  const label = ["label.on"];
  if (l.on) {
    const outside = l.place === "outside";
    label.push("label.text", "label.place", ...(outside ? [] : ["label.surface"]), "label.side", "label.height_mm",
      ...(outside ? ["label.gap_mm"] : []), "label.offset_mm");
  }
  label.push("marker.corner_mark");
  return { make, marker, label };
}

/** Every row drawn, in any tab. */
export function shownRows(m: MarkerParams, l: Pick<LabelParams, "on" | "place">, method: Method): string[] {
  const t = tabRows(m, l, method);
  return [...t.make, ...t.marker, ...t.label];
}

/** Issues by the row they show under; "summary" holds the rest. */
export function routeIssues(issues: Issue[], shown: string[]): Record<string, Issue[]> {
  const out: Record<string, Issue[]> = {};
  const put = (k: string, i: Issue) => { (out[k] ??= []).push(i); };
  for (const i of issues) {
    let f = i.field === "preset" || i.field.startsWith("preset.") ? "preset" : i.field;
    for (let n = 0; n < 4 && !shown.includes(f) && OWNER[f]; n++) f = OWNER[f];
    put(shown.includes(f) ? f : "summary", i);
  }
  return out;
}

const RANK: Record<IssueLevel, number> = { info: 1, warn: 2, error: 3 };

export function worstLevel(issues: Issue[] | undefined): IssueLevel | null {
  let w: IssueLevel | null = null;
  for (const i of issues ?? []) if (!w || RANK[i.level] > RANK[w]) w = i.level;
  return w;
}

/** The worst level among the rows of one tab. */
export function tabLevel(routed: Record<string, Issue[]>, rows: string[]): IssueLevel | null {
  return worstLevel(rows.flatMap((r) => routed[r] ?? []));
}
