// The store's pure reducers: selection, local moves, history, placement,
// the inspector's message routing. No I/O here (store.ts does that), so
// vitest covers them (scene.test.ts).
import type { Issue, SceneDoc, SceneTag } from "../api/types";
import { boxesTouch, snap, tagBox, type Box } from "./geom";

export type View = "2d" | "3d";

/** A click on a tag: alone selects it; with shift / ctrl toggles it. */
export function selectClick(sel: string[], name: string | null, additive: boolean): string[] {
  if (name === null) return additive ? sel : [];
  if (!additive) return sel.length === 1 && sel[0] === name ? sel : [name];
  return sel.includes(name) ? sel.filter((n) => n !== name) : [...sel, name];
}

/** Marquee: every visible tag whose box touches the rectangle (scene mm). */
export function marqueeSelect(tags: SceneTag[], box: Box, sel: string[], additive: boolean): string[] {
  const hit = tags.filter((t) => !t.hidden).filter((t) => {
    const b = tagBox(t);
    return b ? boxesTouch(b, box) : false;
  }).map((t) => t.name);
  if (!additive) return hit;
  return [...sel, ...hit.filter((n) => !sel.includes(n))];
}

/** Move tags on the canvas (mm, snapped to `step` after the move). */
export function moveLocal(doc: SceneDoc, names: string[], dx: number, dy: number, step = 0.5,
  from?: Record<string, [number, number]>): SceneDoc {
  return {
    ...doc,
    tags: doc.tags.map((t) => {
      if (!names.includes(t.name)) return t;
      const [x0, y0] = from?.[t.name] ?? [t.x_mm, t.y_mm];
      return { ...t, x_mm: snap(x0 + dx, step), y_mm: snap(y0 + dy, step) };
    }),
  };
}

/** Turn tags on the canvas by `deg` (kept in 0..360). */
export function rotateLocal(doc: SceneDoc, names: string[], deg: number): SceneDoc {
  return {
    ...doc,
    tags: doc.tags.map((t) => names.includes(t.name)
      ? { ...t, rotation_deg: (((t.rotation_deg + deg) % 360) + 360) % 360 } : t),
  };
}

export function setLocked(doc: SceneDoc, names: string[], locked: boolean): SceneDoc {
  return { ...doc, tags: doc.tags.map((t) => names.includes(t.name) ? { ...t, locked } : t) };
}

export function toggleView(v: View): View {
  return v === "2d" ? "3d" : "2d";
}

/** The scene as a file holds it (plans dropped): what undo keeps. */
export function docOf(doc: SceneDoc): SceneDoc {
  return { ...doc, tags: doc.tags.map((t) => ({ ...t, plan: null })) };
}

export interface History { undo: SceneDoc[]; redo: SceneDoc[] }

export const LIMIT = 100;

export function pushHistory(h: History, before: SceneDoc): History {
  return { undo: [...h.undo, docOf(before)].slice(-LIMIT), redo: [] };
}

/** -> [the doc to restore, the new history] or null when there is none. */
export function undoStep(h: History, current: SceneDoc): [SceneDoc, History] | null {
  if (!h.undo.length) return null;
  const prev = h.undo[h.undo.length - 1];
  return [prev, { undo: h.undo.slice(0, -1), redo: [...h.redo, docOf(current)] }];
}

export function redoStep(h: History, current: SceneDoc): [SceneDoc, History] | null {
  if (!h.redo.length) return null;
  const next = h.redo[h.redo.length - 1];
  return [next, { undo: [...h.undo, docOf(current)], redo: h.redo.slice(0, -1) }];
}

/** Where a new tag goes: right of everything on the canvas, 10 mm apart,
 *  its centre on the row of the first tag (the canvas origin when empty). */
export function placeNew(tags: SceneTag[], w: number): [number, number] {
  let x1 = -Infinity, cy = 0, any = false;
  for (const t of tags) {
    const b = tagBox(t);
    if (!b) continue;
    if (!any) cy = (b.y0 + b.y1) / 2;
    any = true;
    x1 = Math.max(x1, b.x1);
  }
  if (!any) return [0, 0];
  return [snap(x1 + 10 + w / 2, 0.5), snap(cy, 0.5)];
}

/** Arrange tags in a row, left to right in scene order, `gap` mm apart,
 *  their tops level with the first one's: -> {name: [x_mm, y_mm]}. */
export function arrangeRow(tags: SceneTag[], gap = 10): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  let x = 0, top: number | null = null;
  for (const t of tags) {
    const b = tagBox(t);
    if (!b) continue;
    if (top === null) { top = b.y1; x = b.x0; }
    out[t.name] = [snap(t.x_mm + (x - b.x0)), snap(t.y_mm + (top - b.y1))];
    x += b.x1 - b.x0 + gap;
  }
  return out;
}

/** Rename in a selection. */
export function renameSel(sel: string[], from: string, to: string): string[] {
  return sel.map((n) => (n === from ? to : n));
}

// ------------------------------------------------------------- messages

/** The Issues a field shows: those on its key path or below it. */
export function issuesFor(path: string, issues: Issue[]): Issue[] {
  return issues.filter((i) => i.field === path || i.field.startsWith(path + "."));
}

/** Each Issue's home field: the deepest shown field it names (or "tag"). */
export function routeIssues(issues: Issue[], paths: string[]): Record<string, Issue[]> {
  const out: Record<string, Issue[]> = {};
  const sorted = [...paths].sort((a, b) => b.length - a.length);
  for (const i of issues) {
    const home = sorted.find((p) => i.field === p || i.field.startsWith(p + ".")) ??
      paths.find((p) => p.startsWith(i.field + ".")) ?? "tag";      // a parent: its first row
    (out[home] ||= []).push(i);
  }
  return out;
}

const RANK: Record<string, number> = { error: 0, warn: 1, info: 2 };

export function worst(issues: Issue[]): "error" | "warn" | "info" | null {
  if (!issues.length) return null;
  return [...issues].sort((a, b) => RANK[a.level] - RANK[b.level])[0].level;
}

/** The summary line (REF bam_fusion_ui.summary_text's words): the worst
 *  issue first with where it is, or "OK" when only info lines remain. */
export function summaryLine(issues: Issue[], where: (field: string) => string, okText = "Ready"): { level: "error" | "warn" | "ok"; text: string } {
  const counted = issues.filter((i) => i.level !== "info").sort((a, b) => RANK[a.level] - RANK[b.level]);
  if (!counted.length) return { level: "ok", text: okText };
  const first = counted[0];
  const w = where(first.field);
  if (counted.length === 1) return { level: first.level as "error" | "warn", text: `⚠ ${w ? w + ": " : ""}${first.text}` };
  const names = [...new Set(counted.map((i) => where(i.field)).filter(Boolean))];
  return {
    level: first.level as "error" | "warn",
    text: `⚠ ${counted.length} issues: ${names.slice(0, 3).join(" · ")}${names.length > 3 ? " …" : ""}`,
  };
}

/** '<family>#<id>' -> the visible tags printing it, two or more. */
export function duplicates(tags: SceneTag[], familyOf: (dict: string) => string): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const t of tags) {
    if (t.hidden || !t.plan?.ok) continue;
    const dict = (t.plan.marker as any)?.dictionary ?? "";
    for (const id of t.plan.ids) (out[`${familyOf(dict)}#${id}`] ||= []).push(t.name);
  }
  return Object.fromEntries(Object.entries(out).filter(([, v]) => v.length > 1));
}

/** "0", "0–7" or "0, 3, 5" for a tag's ids. */
export function idsText(ids: number[]): string {
  if (!ids.length) return "–";
  const run = ids.every((v, i) => i === 0 || v === ids[i - 1] + 1);
  if (ids.length === 1) return String(ids[0]);
  return run ? `${ids[0]}–${ids[ids.length - 1]}` : ids.join(", ");
}

// ------------------------------------------------------------- key paths

/** A value at a key path of an object ("settings.label.cap_mm"). */
export function getPath(obj: any, path: string): unknown {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

/** The PATCH body for setting one key path of a tag's request. */
export function patchFor(path: string, value: unknown, spec: { target: any; settings?: any }): Record<string, unknown> {
  const [head, ...rest] = path.split(".");
  if (head === "numbers") return { numbers: { [rest[0]]: value } };
  if (head === "settings") {
    if (rest.length === 1) return { settings: { [rest[0]]: value } };
    if (rest[0] === "label") return { settings: { label: { [rest[1]]: value } } };
    // any other object setting is replaced whole by the server: send it all
    const cur = (spec.settings && typeof spec.settings[rest[0]] === "object" && spec.settings[rest[0]]) || {};
    return { settings: { [rest[0]]: { ...cur, [rest[1]]: value } } };
  }
  if (head === "target") return { target: { ...spec.target, [rest[0]]: value } };
  if (head === "key") return { key: value };
  if (head === "name") return { new_name: value };
  return {};
}
