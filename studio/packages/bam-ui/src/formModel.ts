// bam.form/1, the pure half: which rows show, where each message goes, the
// one summary line. No React here, so vitest covers it (form.test.ts).
//
// A field list is the server's (ArUco Studio: plan/fields.py via GET
// /api/form). Each row: path, type, label, default, choices (with icons),
// and the presentation keys `tab`, `show_when`, `anchor`, `unit`, `step`,
// `drag`, `read_only` (docs/KIT.md). The renderer holds no second copy.

export interface Choice { value: string | number; label: string; icon?: string }

export interface ShowWhen {
  /** settings.layout is one of these */
  layouts?: string[];
  /** how the thing is made (the tool says: ArUco Studio's plan.made_by) */
  made_by?: string[];
  /** facts about the target the tool gives (e.g. "holes") */
  target?: string[];
  /** the value at each path (its row's default when absent) is one of these */
  values?: Record<string, unknown[]>;
  /** each path holds a truthy value (non-zero, non-empty) */
  truthy?: string[];
  /** at least one of these paths holds a truthy value */
  any_truthy?: string[];
}

export interface FormRow {
  path: string;
  type: string;
  label: string;
  group?: string;
  default?: unknown;
  choices?: Choice[];
  tab?: string;
  show_when?: ShowWhen;
  anchor?: string;
  unit?: string;
  step?: number;
  drag?: string;
  read_only?: boolean;
  min?: number;
  max?: number;
  [k: string]: unknown;
}

export interface FormTab { id: string; name: string; icon?: string }

export interface FormDoc { contract?: string; fields: FormRow[]; tabs?: FormTab[]; outside?: string[]; [k: string]: unknown }

export interface Issue { field: string; level: "error" | "warn" | "info" | string; text: string; [k: string]: unknown }

export interface FormCtx {
  /** the value at a key path (undefined when absent) */
  get: (path: string) => unknown;
  layout?: string;
  made_by?: string;
  target?: string[];
}

/** A value at a key path of an object ("settings.label.cap_mm"). */
export function getPath(obj: any, path: string): unknown {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

const truthy = (v: unknown) => !!v && v !== "0";

/** Is this row drawn for this thing? Every key of show_when must hold. */
export function shows(row: FormRow, ctx: FormCtx, byPath: Record<string, FormRow> = {}): boolean {
  if (row.tab === "none") return false;
  const w = row.show_when;
  if (!w) return true;
  const val = (p: string) => {
    const v = ctx.get(p);
    return v === undefined ? byPath[p]?.default : v;
  };
  if (w.layouts && !w.layouts.includes(ctx.layout ?? String(val("settings.layout") ?? "single"))) return false;
  if (w.made_by && !w.made_by.includes(ctx.made_by ?? "print3d")) return false;
  if (w.target && !w.target.every((t) => (ctx.target ?? []).includes(t))) return false;
  if (w.values) {
    for (const [p, allowed] of Object.entries(w.values)) {
      const v = val(p);
      if (!allowed.some((a) => String(a) === String(v))) return false;
    }
  }
  if (w.truthy && !w.truthy.every((p) => truthy(val(p)))) return false;
  if (w.any_truthy && !w.any_truthy.some((p) => truthy(val(p)))) return false;
  return true;
}

/** The rows drawn, in the list's order. */
export function visibleRows(rows: FormRow[], ctx: FormCtx): FormRow[] {
  const byPath = Object.fromEntries(rows.map((r) => [r.path, r]));
  return rows.filter((r) => shows(r, ctx, byPath));
}

/** Each Issue's home: the deepest row its key path names; when that row is
 *  hidden, its anchor (and the anchor's anchor); `outside` names rows the
 *  tool draws itself (always shown). Nothing found: "tag" (the summary's own
 *  line). A parent path (an Issue on "settings.label") goes to its first
 *  shown child. */
export function routeIssues(issues: Issue[], rows: FormRow[], shown: Iterable<string>, outside: string[] = []): Record<string, Issue[]> {
  const out: Record<string, Issue[]> = {};
  const vis = new Set([...shown, ...outside]);
  const byPath = Object.fromEntries(rows.map((r) => [r.path, r]));
  const known = [...rows.map((r) => r.path), ...outside].sort((a, b) => b.length - a.length);
  for (const i of issues) {
    let home: string | undefined = known.find((p) => i.field === p || i.field.startsWith(p + "."));
    if (home === undefined) {
      home = [...vis].find((p) => p.startsWith(i.field + ".")) ?? "tag";
    } else {
      const seen = new Set<string>();
      while (home !== undefined && !vis.has(home) && !seen.has(home)) {
        seen.add(home);
        home = byPath[home]?.anchor;
      }
      if (home === undefined || !vis.has(home)) home = "tag";
    }
    (out[home] ||= []).push(i);
  }
  return out;
}

/** One short line for an Issue: what is wrong and, when the words say it,
 *  what to change. The whole text stays in the line's tooltip. */
export function shortText(text: string): string {
  let t = text.replace(/^label: /, "").trim();
  const sq = /^Label not built: no room in a ([\d.]+) mm ChArUco square for (.+?), even at /.exec(t);
  if (sq) return `No room in a ${Number(sq[1]).toFixed(0)} mm square for ${sq[2]}: fewer columns (bigger squares) or Content #id`;
  const room = /^Label not built: no room for (.+?) on the black or on the white, even at ([\d.]+) mm letters/.exec(t);
  if (room) return `No room for ${room[1]}, even at ${room[2]} mm letters: a finer label nozzle or a smaller marker makes room`;
  const cut = t.search(/ \(|\. |; /);
  if (cut > 0) t = t.slice(0, cut);
  t = t.replace(/…$/, "").trim();
  if (t.length > 150) t = t.slice(0, 147).replace(/\s+\S*$/, "") + "…";
  return t;
}

const RANK: Record<string, number> = { error: 0, warn: 1, info: 2 };

export function worst(issues: Issue[]): "error" | "warn" | "info" | null {
  if (!issues.length) return null;
  return [...issues].sort((a, b) => (RANK[a.level] ?? 3) - (RANK[b.level] ?? 3))[0].level as "error" | "warn" | "info";
}

/** The summary line: the worst issue first with where it is, or `okText`
 *  when only info lines remain. */
export function summaryLine(issues: Issue[], where: (field: string) => string, okText = "Ready"): { level: "error" | "warn" | "ok"; text: string } {
  const counted = issues.filter((i) => i.level !== "info").sort((a, b) => (RANK[a.level] ?? 3) - (RANK[b.level] ?? 3));
  if (!counted.length) return { level: "ok", text: okText };
  const first = counted[0];
  const w = where(first.field);
  if (counted.length === 1) return { level: first.level as "error" | "warn", text: `⚠ ${w ? w + ": " : ""}${shortText(first.text)}` };
  const names = [...new Set(counted.map((i) => where(i.field)).filter(Boolean))];
  return {
    level: first.level as "error" | "warn",
    text: `⚠ ${counted.length} issues: ${names.slice(0, 3).join(" · ")}${names.length > 3 ? " …" : ""}`,
  };
}

/** Of several things' values at one path: the one value, or mixed. */
export function common(values: unknown[]): { value: unknown; mixed: boolean } {
  if (!values.length) return { value: undefined, mixed: false };
  const k = JSON.stringify(values[0] ?? null);
  const mixed = values.some((v) => JSON.stringify(v ?? null) !== k);
  return { value: mixed ? undefined : values[0], mixed };
}
