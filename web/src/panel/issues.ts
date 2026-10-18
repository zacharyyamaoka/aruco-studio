// Per-line validation: each plan warning goes under the row its field names.
// A field whose row is not drawn goes to the row that owns it (rows → the
// Columns × Rows row, checker → Marker, a hidden label field → On); what has
// no row at all goes to the summary line. Pure: vitest covers it.
import type { Issue, IssueLevel, MarkerParams } from "../core/contract";

const OWNER: Record<string, string> = {
  "marker.rows": "marker.cols",
  "marker.auto": "marker.marker_mm",
  "marker.checker_mm": "marker.marker_mm",
  "marker.separation_mm": "marker.marker_mm",
  "marker.cols": "marker.marker_mm",
  "marker.id": "marker.first_id",
  "marker.ids": "marker.first_id",
  "marker.flip": "marker.turn",
  "marker.origin_square": "marker.type",
  "label.text": "label.on",
  "label.height_mm": "label.on",
  "label.side": "label.on",
  "label.gap_mm": "label.on",
  "label.offset_mm": "label.on",
};

/** The rows drawn for these numbers, by field path. */
export function shownRows(m: MarkerParams, labelOn: boolean, referenceFace: boolean): string[] {
  const rows = ["profile", "rect", "preset", "marker.type", "marker.dictionary", "marker.first_id", "marker.marker_mm"];
  if (m.type === "charuco") rows.push("marker.checker_mm", "marker.origin_square");
  if (m.type === "grid") rows.push("marker.separation_mm");
  if (m.type !== "single") rows.push("marker.cols");
  rows.push("marker.suggest", "marker.turn");
  if (!referenceFace) rows.push("marker.flip");
  rows.push("marker.corner_mark", "label.on");
  if (labelOn) rows.push("label.text", "label.height_mm", "label.side", "label.gap_mm", "label.offset_mm");
  return rows;
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

/** The worst level among the rows of one tab ("marker." or "label."). */
export function tabLevel(routed: Record<string, Issue[]>, prefix: string): IssueLevel | null {
  return worstLevel(Object.entries(routed).filter(([k]) => k.startsWith(prefix)).flatMap(([, v]) => v));
}
