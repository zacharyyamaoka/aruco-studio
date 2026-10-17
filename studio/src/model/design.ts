// The design document (arucostudio.scene/2, docs/FILE_FORMAT.md) as the
// Studio edits it: find a shape, add / change / move / delete shapes and
// holes, Extrude, ArUco Extrude. Pure: each edit changes the parsed
// document in place; store.ts writes its text (json.ts) to the server, which
// compiles and plans it. The shapes' loops are never computed here.
import type { Pt } from "../api/types";
import { applyXf, compose, turn, edges, faceNames, kindOf, outline, xfOf, type Xf } from "./shapes";

export type Doc = Record<string, any> & { sketches?: any[]; features?: any[] };

/** One shape (or a hole) of the document, where it is and what it is. */
export interface ShapeInfo {
  key: string;              // its id, or "@i.j"; a hole: "<key>/h<k>"
  id: string | null;
  si: number;
  sj: number;
  hk: number | null;        // the hole's index, or null for a shape
  shape: any;
  sketch: any;
  /** the shape's frame on the canvas (sketch ∘ shape [∘ hole]) */
  xf: Xf;
  /** the frame its own at / rot are in (the sketch's, or the parent shape's) */
  parentXf: Xf;
  path: string;             // its JSON path
  /** its Extrude, when it has one */
  body: { fi: number; id: string; height: number } | null;
  parent: string | null;    // a hole's shape
}

export const SNAP = 0.5;
export const snap = (v: number, step = SNAP) => {
  const r = Math.round(v / step) * step;
  return Object.is(r, -0) ? 0 : Math.round(r * 1e6) / 1e6;
};
export const snapDeg = (v: number, step = 15) => {
  let r = Math.round(v / step) * step;
  r = ((((r + 180) % 360) + 360) % 360) - 180;
  if (r === -180) r = 180;
  return Object.is(r, -0) ? 0 : r;
};

export function emptyDoc(name: string): Doc {
  return { schema: "arucostudio.scene/2", name, sketches: [], features: [] };
}

const sk = (d: Doc) => (Array.isArray(d.sketches) ? d.sketches : (d.sketches = []));
const fs = (d: Doc) => (Array.isArray(d.features) ? d.features : (d.features = []));

/** Every shape and hole of the document. */
export function shapesOf(d: Doc | null): ShapeInfo[] {
  if (!d) return [];
  const bodies = new Map<string, { fi: number; id: string; height: number }>();
  (Array.isArray(d.features) ? d.features : []).forEach((f: any, fi: number) => {
    if (f && typeof f.extrude === "string" && typeof f.height === "number") bodies.set(f.extrude, { fi, id: String(f.id), height: f.height });
  });
  const out: ShapeInfo[] = [];
  (Array.isArray(d.sketches) ? d.sketches : []).forEach((s: any, si: number) => {
    if (!s || typeof s !== "object") return;
    const sxf = xfOf(s);
    (Array.isArray(s.shapes) ? s.shapes : []).forEach((sh: any, sj: number) => {
      if (!sh || typeof sh !== "object") return;
      const id = typeof sh.id === "string" ? sh.id : null;
      const key = id ?? `@${si}.${sj}`;
      const xf = compose(sxf, xfOf(sh));
      const path = `sketches[${si}].shapes[${sj}]`;
      out.push({ key, id, si, sj, hk: null, shape: sh, sketch: s, xf, parentXf: sxf, path, body: id ? bodies.get(id) ?? null : null, parent: null });
      (Array.isArray(sh.holes) ? sh.holes : []).forEach((h: any, hk: number) => {
        if (!h || typeof h !== "object") return;
        out.push({ key: `${key}/h${hk}`, id: null, si, sj, hk, shape: h, sketch: s, xf: compose(xf, xfOf(h)), parentXf: xf,
          path: `${path}.holes[${hk}]`, body: null, parent: key });
      });
    });
  });
  return out;
}

export function findShape(d: Doc | null, key: string): ShapeInfo | null {
  return shapesOf(d).find((s) => s.key === key) ?? null;
}

/** Every id in the document (sketches, shapes, features, tag names). */
export function allIds(d: Doc): Set<string> {
  const out = new Set<string>();
  for (const s of sk(d)) {
    if (s?.id) out.add(String(s.id));
    for (const sh of s?.shapes || []) if (sh?.id) out.add(String(sh.id));
  }
  for (const f of fs(d)) {
    if (f?.id) out.add(String(f.id));
    // a split list names its features <id>.<face>: <id> stays taken, so a
    // new tag never takes the old list's name (audit 2026-10-17)
    if (f?.id && String(f.id).includes(".")) out.add(String(f.id).split(".")[0]);
    if (Array.isArray(f?.aruco)) for (const r of f.aruco) out.add(`${f.id}.${String(r).split(".").pop()}`);
  }
  for (const k of Object.keys(d.overrides || {})) out.add(k);
  return out;
}

/** The next free id `<base><n>` (n from 1). */
export function newId(d: Doc, base: string, taken?: Set<string>): string {
  const ids = taken ?? allIds(d);
  for (let n = 1; ; n++) {
    const id = `${base}${n}`;
    if (!ids.has(id)) { ids.add(id); return id; }
  }
}

const BASE: Record<string, string> = { rect: "rect", circle: "circle", polygon: "poly", slot: "slot", loops: "loops" };

/** A new sketch at `at` holding one shape (its own frame at the sketch's
 *  origin): -> the shape's key (its id). */
export function addShape(d: Doc, shape: any, at: Pt, rot = 0): string {
  const taken = allIds(d);
  const k = kindOf(shape) ?? "rect";
  const id = newId(d, BASE[k], taken);
  const s: any = { id: newId(d, "sk", taken), shapes: [{ id, ...shape }] };
  if (at[0] || at[1]) s.at = [snap(at[0], 1e-6), snap(at[1], 1e-6)];
  if (rot) s.rot = rot;
  sk(d).push(s);
  return id;
}

/** A hole in a shape, centred at `at` in the shape's frame. */
export function addHole(d: Doc, key: string, hole: any, at: Pt = [0, 0]): string | null {
  const info = findShape(d, key);
  if (!info || info.hk !== null) return null;
  const h: any = { ...hole };
  if (at[0] || at[1]) h.at = [at[0], at[1]];
  info.shape.holes = [...(Array.isArray(info.shape.holes) ? info.shape.holes : []), h];
  return `${key}/h${info.shape.holes.length - 1}`;
}

/** Set (or make) the shape's Extrude: -> the body's id. */
export function extrude(d: Doc, key: string, height: number): string | null {
  const info = findShape(d, key);
  if (!info || info.hk !== null) return null;
  if (!info.id) {
    info.shape.id = newId(d, BASE[kindOf(info.shape) ?? "rect"]);
    info.id = info.shape.id;
  }
  if (info.body) {
    fs(d)[info.body.fi].height = height;
    return info.body.id;
  }
  const id = newId(d, "body");
  // after the last feature on this shape's sketch, so the order reads well
  fs(d).push({ id, extrude: info.id, height });
  return id;
}

/** The reference an ArUco Extrude takes for a shape clicked in 2D: its
 *  body's top when it is extruded, the shape itself otherwise. */
export function refOfShape(d: Doc, key: string): string | null {
  const info = findShape(d, key);
  if (!info || info.hk !== null) return null;
  if (!info.id) {
    info.shape.id = newId(d, BASE[kindOf(info.shape) ?? "rect"]);
    info.id = info.shape.id;
  }
  return info.body ? `${info.body.id}.top` : info.id;
}

/** An ArUco Extrude on `refs` (one: a string; several: the face list): ->
 *  the feature's id. `extra` are sugar keys ({layout: "grid"}). */
export function addAruco(d: Doc, refs: string[], extra: Record<string, unknown> = {}): string {
  const id = newId(d, "tag");
  fs(d).push({ id, aruco: refs.length === 1 ? refs[0] : [...refs], ...extra });
  return id;
}

/** The faces of a body, with their refs ("body1.front"). */
export function bodyFaces(info: ShapeInfo): { ref: string; face: string }[] {
  if (!info.body) return [];
  return faceNames(info.shape).map((f) => ({ ref: `${info.body!.id}.${f}`, face: f }));
}

/** Move shapes on the canvas by (dx, dy) mm: every shape of a sketch
 *  selected -> the sketch's at; else each shape's own at; a hole's at in
 *  its shape. -> true when something moved. */
export function moveShapes(d: Doc, keys: string[], dx: number, dy: number): boolean {
  if (!dx && !dy) return false;
  const all = shapesOf(d);
  const chosen = all.filter((s) => keys.includes(s.key));
  const whole = new Set<number>();
  for (const s of chosen) {
    if (s.hk !== null) continue;
    const mine = all.filter((x) => x.si === s.si && x.hk === null);
    if (mine.every((x) => keys.includes(x.key))) whole.add(s.si);
  }
  let moved = false;
  for (const si of whole) {
    const s = sk(d)[si];
    const [x, y] = xfOf(s);
    setAt(s, [x + dx, y + dy]);
    moved = true;
  }
  for (const s of chosen) {
    if (s.hk === null && whole.has(s.si)) continue;
    if (s.hk !== null && keys.includes(s.parent!)) continue;     // moves with its shape
    // the move in the frame the shape's at is written in
    const [lx, ly] = turn(-s.parentXf[2], [dx, dy]);
    const [x, y] = xfOf(s.shape);
    setAt(s.shape, [x + lx, y + ly]);
    moved = true;
  }
  return moved;
}

export function setAt(o: any, at: Pt) {
  const x = snap(at[0], 1e-6), y = snap(at[1], 1e-6);
  if (!x && !y) delete o.at;
  else o.at = [x, y];
}

export function setRot(o: any, deg: number) {
  let r = ((((deg + 180) % 360) + 360) % 360) - 180;
  if (r === -180) r = 180;
  r = Math.round(r * 1e6) / 1e6;
  if (!r) delete o.rot;
  else o.rot = r;
}

/** Turn shapes by `deg` about their own centres (a whole sketch: the sketch). */
export function rotateShapes(d: Doc, keys: string[], deg: number): boolean {
  const all = shapesOf(d);
  const chosen = all.filter((s) => keys.includes(s.key));
  if (!chosen.length) return false;
  const whole = new Set<number>();
  for (const s of chosen) {
    if (s.hk !== null) continue;
    const mine = all.filter((x) => x.si === s.si && x.hk === null);
    if (mine.length === 1 && !mine[0].shape.at) whole.add(s.si);
  }
  for (const si of whole) setRot(sk(d)[si], (Number(sk(d)[si].rot) || 0) + deg);
  for (const s of chosen) {
    if (s.hk === null && whole.has(s.si)) continue;
    if (s.hk !== null && keys.includes(s.parent!)) continue;
    setRot(s.shape, (Number(s.shape.rot) || 0) + deg);
  }
  return true;
}

/** The refs that point at a shape or at its body's faces. */
function refsOn(info: ShapeInfo): (r: string) => boolean {
  return (r) => r === info.id || (!!info.body && (r === info.body.id || r.startsWith(info.body.id + ".")));
}

/** Delete shapes (and holes); the Extrude of a deleted shape and every
 *  ArUco Extrude reference on it go too. -> the number deleted. */
export function deleteShapes(d: Doc, keys: string[]): number {
  const all = shapesOf(d).filter((s) => keys.includes(s.key));
  let n = 0;
  // holes first, last index first
  const holes = all.filter((s) => s.hk !== null && !keys.includes(s.parent!)).sort((a, b) => b.hk! - a.hk!);
  for (const h of holes) {
    const parent = sk(d)[h.si].shapes[h.sj];
    parent.holes.splice(h.hk!, 1);
    if (!parent.holes.length) delete parent.holes;
    n++;
  }
  const shapes = all.filter((s) => s.hk === null);
  for (const s of shapes) {
    const on = refsOn(s);
    d.features = fs(d).map((f: any) => {
      if (!f) return f;
      if (s.body && f.id === s.body.id) return null;
      if (typeof f.aruco === "string") return on(f.aruco) ? null : f;
      if (Array.isArray(f.aruco)) {
        const keep = f.aruco.map((r: string, i: number) => [r, i] as [string, number]).filter(([r]: [string, number]) => !on(r));
        if (!keep.length) return null;
        if (keep.length !== f.aruco.length) dropEntries(f, keep.map(([, i]: [string, number]) => i));
      }
      return f;
    }).filter((f: any) => f !== null);
  }
  // shapes out of their sketches (last first), then empty sketches
  for (const s of [...shapes].sort((a, b) => b.si - a.si || b.sj - a.sj)) {
    sk(d)[s.si].shapes.splice(s.sj, 1);
    n++;
  }
  d.sketches = sk(d).filter((s: any) => !s || !Array.isArray(s.shapes) || s.shapes.length);
  return n;
}

/** Keep only the entries `keep` (indices) of a face list and its per-face lists. */
function dropEntries(f: any, keep: number[]) {
  f.aruco = keep.map((i) => f.aruco[i]);
  for (const k of ["marker_ids", "first_id"]) if (Array.isArray(f[k])) f[k] = keep.map((i) => f[k][i]);
  if (f.aruco.length === 1) {
    // one face left: it stays a list, so its tag keeps its name (<id>.<face>)
  }
}

/** Delete a tag: its reference out of its ArUco Extrude (the feature when
 *  it was the only one); the shape and body stay. */
export function deleteTag(d: Doc, source: { feature?: number; entry?: number | null } | undefined, name: string): boolean {
  const fi = source?.feature;
  const f = typeof fi === "number" ? fs(d)[fi] : null;
  if (!f) return false;
  if (typeof f.aruco === "string" || source?.entry === null || source?.entry === undefined) {
    d.features = fs(d).filter((_x: any, i: number) => i !== fi);
  } else {
    const keep = f.aruco.map((_r: string, i: number) => i).filter((i: number) => i !== source!.entry);
    if (!keep.length) d.features = fs(d).filter((_x: any, i: number) => i !== fi);
    else dropEntries(f, keep);
  }
  if (d.overrides && name in d.overrides) {
    delete d.overrides[name];
  }
  return true;
}

/** Copy shapes (each with its sketch's place, its Extrude and its ArUco
 *  Extrudes) by (dx, dy): -> the new keys. */
export function duplicateShapes(d: Doc, keys: string[], dx: number, dy: number): string[] {
  const all = shapesOf(d).filter((s) => keys.includes(s.key) && s.hk === null);
  const taken = allIds(d);
  const out: string[] = [];
  for (const s of all) {
    const copy = JSON.parse(JSON.stringify(s.shape));
    const k = kindOf(copy) ?? "rect";
    copy.id = newId(d, BASE[k], taken);
    delete copy.at;
    delete copy.rot;
    const sketch: any = { id: newId(d, "sk", taken), shapes: [copy] };
    setAt(sketch, [s.xf[0] + dx, s.xf[1] + dy]);
    setRot(sketch, s.xf[2]);
    sk(d).push(sketch);
    out.push(copy.id);
    if (s.body) {
      const body = newId(d, "body", taken);
      fs(d).push({ ...JSON.parse(JSON.stringify(fs(d)[s.body.fi])), id: body, extrude: copy.id });
      const on = refsOn(s);
      for (const f of [...fs(d)]) {
        if (!f || f.aruco === undefined) continue;
        const refs: string[] = typeof f.aruco === "string" ? [f.aruco] : f.aruco;
        const mine = refs.filter(on);
        if (!mine.length) continue;
        const nf = JSON.parse(JSON.stringify(f));
        nf.id = newId(d, "tag", taken);
        nf.aruco = mine.length === 1 && typeof f.aruco === "string" ? mine[0].replace(s.body.id, body) : mine.map((r) => r.replace(s.body!.id, body));
        delete nf.uid;
        delete nf.marker_ids;
        delete nf.first_id;
        fs(d).push(nf);
      }
    } else if (s.id) {
      for (const f of [...fs(d)]) {
        if (f?.aruco === s.id) {
          const nf = JSON.parse(JSON.stringify(f));
          nf.id = newId(d, "tag", taken);
          nf.aruco = copy.id;
          delete nf.uid;
          delete nf.first_id;
          fs(d).push(nf);
        }
      }
    }
  }
  return out;
}

/** Replace a shape's dict (its handles, its inspector rows). */
export function setShape(d: Doc, key: string, next: any): boolean {
  const info = findShape(d, key);
  if (!info) return false;
  const host = info.hk === null ? sk(d)[info.si].shapes : sk(d)[info.si].shapes[info.sj].holes;
  host[info.hk === null ? info.sj : info.hk] = next;
  return true;
}

/** The canvas outline of a shape (and its holes), for drawing. */
export function canvasLoops(info: ShapeInfo): { outer: Pt[]; holes: Pt[][] } {
  const place = (p: Pt): Pt => applyXf(info.xf, p);
  const outer = outline(info.shape).map(place);
  const holes: Pt[][] = [];
  if (info.hk === null && kindOf(info.shape) === "loops") {
    for (const lp of (info.shape.loops || []).slice(1)) holes.push(lp.map((p: number[]) => place([p[0], p[1]])));
  }
  return { outer, holes };
}

/** The straight edges of a shape on the canvas (side faces). */
export function canvasEdges(info: ShapeInfo): [Pt, Pt][] {
  return edges(info.shape).map(([a, b]) => [applyXf(info.xf, a), applyXf(info.xf, b)] as [Pt, Pt]);
}

/** Next free ids for a new tag of `family` (one past the largest used). */
export function nextFreeId(used: number[]): number {
  return used.length ? Math.max(...used) + 1 : 0;
}

/** The JSON path of what is selected (the File drawer's highlight). */
export function pathOfFeature(fi: number | undefined): string | null {
  return typeof fi === "number" ? `features[${fi}]` : null;
}

export function hasOutline(shape: any): boolean {
  return outline(shape).length >= 3;
}
