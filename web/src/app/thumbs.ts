// The pictures on Home's cards (and File › Examples…'s): a document's shapes
// and, as the core planned them, each marker's outline and its black.
// WHY (Zach, 2026-10-21): "It would be nice if the aruco stickers showed up in
// the thumbnail"; then, every file and not only the open one: "Make sure
// thumbnail previews are showing".
// - The document in the editor: its plans are the store's (the editor stays
//   mounted under Home); openHome() keeps a copy in this browser, so a page
//   opened straight on Home draws its markers before the core is up.
// - A cloud file: drawn from its own bytes. Simple Hosted Files has no place
//   for a picture ("The server stores your bytes, so only your app can draw
//   them": its preview contract, skill/references/react-shadcn.md), and
//   writing one into the file would add a version and move it up Recents for
//   a look at Home. So the picture is kept in this browser (IndexedDB) by the
//   bytes' sha256 (FileMeta.sha256): a copy (Duplicate) or a restored version
//   has the same bytes, so the same picture, at once. Every save keeps the
//   picture of what it wrote (keepSaved); a file with none here (saved before
//   pictures were kept, on another device, by an agent) is read once its card
//   is on screen, its shapes drawn at once and its markers planned in the
//   background.
// - An example: no plans until planned. Once Home shows it and the core is
//   ready, its features are planned one after another, in the background (no
//   call while Home is closed), and kept in this browser by the core's
//   version: a later visit draws them at once and asks the core nothing.
// - Every plan this page gets, the editor's or a card's, is kept by its
//   request: the core's answer depends on the request alone, so the file the
//   editor just saved, and its copy, are drawn without asking the core again.
// Keep it cheap: the shapes draw first; the markers join when they are known.
import { useEffect, useSyncExternalStore } from "react";
import { createStore, delMany, entries, set as idbSet, type UseStore } from "idb-keyval";
import type { MarkerPlan, PlanRequest, Polygon, Vec2 } from "../core/contract";
import { core, coreStatus, onCoreStatus } from "../coreSource";
import type { FileMeta } from "../hosted/core";
import { emptyDoc, fillPresets, parseDoc, planRequest, type Doc } from "../model/doc";
import { example } from "../model/examples";
import type { Shape } from "../sketch/model";
import { useStudio } from "../store";
import { isHome } from "./home";

/** One marker as a thumbnail draws it: its outline (the quiet-zone edge, white) and its black. */
export interface Mark { outer: Vec2[]; black: Polygon[] }

const DOC_KEY = "arucoStudio.thumb.doc";
const EX_KEY = "arucoStudio.thumb.examples";

// a thumbnail is a few hundred px across: 0.01 mm is plenty and keeps the copies small
const r2 = (p: Vec2): Vec2 => [Math.round(p[0] * 100) / 100, Math.round(p[1] * 100) / 100];
const markOf = (p: MarkerPlan): Mark => ({ outer: p.outer.map(r2), black: p.black.map((b) => ({ outer: b.outer.map(r2), holes: b.holes.map((h) => h.map(r2)) })) });

/** A short stable hash of a string (FNV-1a), for the cache keys. */
function hash(s: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(36);
}

/** A 53-bit hash of a string (cyrb53) and its length: a request's key. WHY
 *  wider than hash(): a key that met another request's would draw a wrong marker. */
function hash53(s: string): string {
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < s.length; i++) {
    const ch = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return `${s.length.toString(36)}.${(4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36)}`;
}

/** JSON with every object's keys in order: one request is one text, however
 *  its objects were built (a file read back, the editor's own). */
function canonical(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map((x) => (x === undefined ? "null" : canonical(x))).join(",")}]`;
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    return `{${Object.keys(o).sort().filter((k) => o[k] !== undefined).map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`).join(",")}}`;
  }
  return JSON.stringify(v) ?? "null";
}

function readJson<T>(key: string): T | null {
  try { return JSON.parse(window.localStorage.getItem(key) ?? "null") as T | null; } catch { return null; }
}
function writeJson(key: string, v: unknown): void {
  try { window.localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage blocked or full: kept for this visit only */ }
}

const listeners = new Set<() => void>();
const notify = () => { for (const fn of listeners) fn(); };
const subscribe = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };
const coreVersion = (): string => useStudio.getState().info?.core_version ?? "";

// ------------------------------------------------------------ the document in the editor

const docKey = (doc: Doc) => hash(JSON.stringify([doc.shapes, doc.features]));

/** The document's marks from its plans; null while a feature with a profile has none yet. */
export function marksOf(doc: Doc, plans: Record<string, MarkerPlan>): Mark[] | null {
  const fs = doc.features.filter((f) => f.profile);
  if (fs.some((f) => !plans[f.id])) return null;
  return fs.map((f) => markOf(plans[f.id]));
}

/** Leaving the editor (openHome): the document's marks into this browser. */
export function saveDocMarks(): void {
  const { doc, plans } = useStudio.getState();
  const marks = marksOf(doc, plans);
  if (marks) writeJson(DOC_KEY, { key: docKey(doc), marks });
}

/** The editor's document's marks: its plans when all are in, else the copy
 *  openHome() kept when it is of this document, else none yet. */
export function useDocMarks(): Mark[] {
  const doc = useStudio((s) => s.doc);
  const plans = useStudio((s) => s.plans);
  const live = marksOf(doc, plans);
  if (live) return live;
  const kept = readJson<{ key: string; marks: Mark[] }>(DOC_KEY);
  return kept && kept.key === docKey(doc) ? kept.marks : [];
}

// ------------------------------------------------------------ the core's marks, by request

const MARKS_MAX = 600;
/** a request's key -> its mark; null: the core refused it (the marker is left
 *  out of the picture, as the editor draws none). This page's core only. */
const marksByReq = new Map<string, Mark | null>();

export const requestKey = (req: PlanRequest): string => hash53(canonical(req));

function noteMark(key: string, mark: Mark | null): void {
  marksByReq.delete(key);
  marksByReq.set(key, mark);
  if (marksByReq.size > MARKS_MAX) marksByReq.delete(marksByReq.keys().next().value!);
  settleSaves();
}

/** The planner's answer to a request (planner.ts), `plan` null when the core
 *  refused it: every plan the editor gets is a card's mark too. A refusal
 *  counts only from a core that is up (one that is down refuses everything,
 *  which says nothing of the request). */
export function notePlan(req: PlanRequest, plan: MarkerPlan | null): void {
  if (!plan && coreStatus().state !== "ready") return;
  // WHY never a throw: this runs inside the planner's own call; a picture must never cost the editor its plan
  try { noteMark(requestKey(req), plan ? markOf(plan) : null); } catch { /* a plan without its geometry: no picture of it */ }
}

/** A document as its picture plans it: its features' requests, each with its key. */
interface Planned { doc: Doc; reqs: { req: PlanRequest; key: string }[] }

function planned(doc: Doc): Planned {
  return { doc, reqs: doc.features.flatMap((f) => { const req = planRequest(doc, f); return req ? [{ req, key: requestKey(req) }] : []; }) };
}

/** Its marks known now, in the features' order (an unanswered one left out until it is). */
const knownMarks = (p: Planned): Mark[] => p.reqs.flatMap((r) => { const m = marksByReq.get(r.key); return m ? [m] : []; });

// ------------------------------------------------------------ the cloud files (Home's cards)

/** A file's picture: its shapes and its markers, as core `core` planned them. */
export interface Picture { shapes: Shape[]; marks: Mark[]; core: string }
/** What a card draws: nothing yet (its bytes on their way), its picture (the
 *  markers join as the core plans them), or the file icon: its bytes are not a
 *  document this Studio reads (or could not be read just now). */
export type FileThumb = { kind: "wait" } | { kind: "drawn"; shapes: Shape[]; marks: Mark[] } | { kind: "broken" };

const PIC_MAX = 300;
const RETRY_MS = 15_000;
const WAIT: FileThumb = { kind: "wait" };
const BROKEN: FileThumb = { kind: "broken" };

/** the pictures this browser keeps, by the bytes' key (sha256) */
const kept = new Map<string, Picture & { at: number }>();
let keptRead: Promise<void> | null = null;
let picStore: UseStore | null | undefined;
/** files read this visit, by key: the document, its presets filled as the editor would */
const parsed = new Map<string, Planned>();
/** saves of the editor's document waiting for a marker the planner has not answered yet, by sha256 */
const saves = new Map<string, Planned>();
/** bytes that are not a document this Studio reads */
const broken = new Set<string>();
/** a read that failed (offline, the server down): when, to try again later */
const unread = new Map<string, number>();
const reading = new Set<string>();
const planning = new Set<string>();
/** what each card draws, by key: one object per change (useSyncExternalStore) */
const thumbs = new Map<string, FileThumb>();

/** A file's bytes' key: their sha256, else (a server without it) the file's version. */
export const thumbKey = (file: Pick<FileMeta, "id" | "version" | "sha256">): string =>
  /^[0-9a-f]{64}$/.test(file.sha256) ? file.sha256 : `${file.id}@${file.version}`;

function picStoreOf(): UseStore | null {
  if (picStore === undefined) {
    try { picStore = typeof indexedDB === "undefined" ? null : createStore("aruco-studio-thumbs", "pictures"); } catch { picStore = null; }
  }
  return picStore;
}

/** This browser's pictures, read once; the oldest beyond PIC_MAX go. */
function readKept(): Promise<void> {
  keptRead ??= (async () => {
    const store = picStoreOf();
    if (!store) return;
    try {
      const all = await entries<string, Picture & { at: number }>(store);
      for (const [k, v] of all) if (!kept.has(k) && v && Array.isArray(v.shapes) && Array.isArray(v.marks)) kept.set(k, v);
      if (all.length > PIC_MAX) await delMany(all.sort((a, b) => (a[1]?.at ?? 0) - (b[1]?.at ?? 0)).slice(0, all.length - PIC_MAX).map(([k]) => k), store);
    } catch { /* storage blocked: drawn from the bytes this visit */ }
  })().finally(() => changed());
  return keptRead;
}

function keep(key: string, p: Planned): void {
  const pic = { shapes: p.doc.shapes, marks: knownMarks(p), core: coreVersion(), at: Date.now() };
  kept.set(key, pic);
  const store = picStoreOf();
  if (store) idbSet(key, pic, store).catch(() => { /* storage blocked or full: kept for this visit only */ });
  changed(key);
}

function thumbOf(key: string): FileThumb {
  const pic = kept.get(key);
  if (pic) return { kind: "drawn", shapes: pic.shapes, marks: pic.marks };
  const p = parsed.get(key) ?? saves.get(key);
  if (p) return { kind: "drawn", shapes: p.doc.shapes, marks: knownMarks(p) };
  return broken.has(key) || unread.has(key) ? BROKEN : WAIT;
}

/** Something changed for these cards (all: undefined): their pictures again. */
function changed(...keys: string[]): void {
  for (const k of keys.length ? keys : [...thumbs.keys()]) if (thumbs.has(k)) thumbs.set(k, thumbOf(k));
  notify();
}

const snapshot = (key: string): FileThumb => {
  let t = thumbs.get(key);
  if (!t) thumbs.set(key, (t = thumbOf(key)));
  return t;
};

/** A save landed (hosted/hosted.ts: every save, autosave included). When its
 *  bytes are the editor's document -- `text` is that document serialised now,
 *  checked against the sha256 the server answered -- the picture of them is
 *  kept, as soon as the planner has answered its markers. Bytes the editor has
 *  moved on from are drawn from the file when Home needs them. */
export function keepSaved(meta: Pick<FileMeta, "sha256">, text: string, doc: Doc): void {
  void sha256Hex(text).then((sha) => {
    if (sha !== meta.sha256 || kept.get(sha)?.core === coreVersion()) return;
    saves.set(sha, planned(doc));
    if (saves.size > 8) saves.delete(saves.keys().next().value!);
    settleSaves();
  }, () => { /* no WebCrypto: drawn from the file when Home needs it */ });
}

function settleSaves(): void {
  for (const [sha, p] of saves) {
    if (!p.reqs.every((r) => marksByReq.has(r.key))) continue;
    saves.delete(sha);
    keep(sha, p);
  }
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** A file read back, as opening it would put it in the editor: a feature
 *  without its own preset takes the file's, else the editor's (store.ts loadDoc). */
function asOpened(doc: Doc): Planned {
  return planned(fillPresets(doc, doc.default_preset ?? useStudio.getState().doc.default_preset));
}

/** A card on screen, Home in front: its picture, its bytes read and its
 *  markers planned when this browser has none (or one of another core). */
function want(file: FileMeta, read: (file: FileMeta) => Promise<Blob>): void {
  const key = thumbKey(file);
  void readKept().then(() => {
    const pic = kept.get(key), ver = coreVersion();
    // drawn by this core, or by any before this core is known
    if (pic && (!ver || pic.core === ver)) return;
    const p = parsed.get(key) ?? saves.get(key);
    if (p) return planFile(key, p);
    if (broken.has(key) || reading.has(key)) return;
    const failed = unread.get(key);
    if (failed !== undefined && Date.now() - failed < RETRY_MS) return;
    reading.add(key);
    read(file).then((blob) => blob.text()).then((text) => {
      unread.delete(key);
      let doc: Doc;
      // WHY the icon only here: bytes that are no document (or one this Studio can't read) have no picture
      try { doc = parseDoc(text); } catch { broken.add(key); return; }
      const p = asOpened(doc);
      parsed.set(key, p);
      planFile(key, p);
    }, () => { unread.set(key, Date.now()); }).finally(() => { reading.delete(key); changed(key); });
  });
}

/** Its markers planned in the background (Home in front, the core up), then the picture kept. */
function planFile(key: string, p: Planned): void {
  if (planning.has(key)) return;
  planning.add(key);
  queue.push({
    run: async () => {
      // its presets now the core's are in (a file read before had features without one)
      const q = p.reqs.length < p.doc.features.filter((f) => f.profile).length ? asOpened(p.doc) : p;
      if (q !== p && parsed.get(key) === p) parsed.set(key, q);
      for (const r of q.reqs) {
        if (marksByReq.has(r.key)) continue;
        if (!isHome()) return false;
        try { noteMark(r.key, markOf(await core.plan(r.req))); } catch { if (coreStatus().state !== "ready") return false; noteMark(r.key, null); }
        changed(key);
      }
      planning.delete(key);
      keep(key, q);
      return true;
    },
  });
  queueMicrotask(kick);
}

/** A cloud file's card: what to draw. Its bytes are read and its markers
 *  planned only once it is `seen` (on screen) with Home in front. */
export function useFileThumb(file: FileMeta, read: (file: FileMeta) => Promise<Blob>, seen: boolean): FileThumb {
  const key = thumbKey(file);
  const ver = useStudio((s) => s.info?.core_version);
  const thumb = useSyncExternalStore(subscribe, () => snapshot(key));
  // WHY by the key, not the FileMeta: each visit's list is new objects, the same bytes the same picture;
  // and again when the core's version is known (a picture another core planned is planned again)
  useEffect(() => {
    if (seen && isHome()) want(file, read);
  }, [key, seen, ver]);
  return thumb;
}

/** For the tests: the picture this page keeps of these bytes. */
export function keptPicture(key: string): Picture | undefined {
  return kept.get(key);
}

// ------------------------------------------------------------ the examples

interface ExCache { core: string; marks: Record<string, { key: string; marks: Mark[] }> }

const exMarks = new Map<string, Mark[]>();
/** what this visit has asked the core about: an example is planned once */
const asked = new Set<string>();

/** The example's features as a document would plan them (the editor's default preset). */
function exampleDoc(id: string): Doc | null {
  const ex = example(id);
  const st = useStudio.getState();
  const preset = st.doc.default_preset ?? st.builtins.find((p) => p.method === "inkjet") ?? st.builtins[0] ?? null;
  if (!ex?.features?.length || !preset) return null;
  return fillPresets({ ...emptyDoc(ex.name, ex.shapes, preset), features: ex.features, id_ledger: { ...ex.id_ledger } }, preset);
}
const exampleKey = (id: string) => { const ex = example(id); return ex ? hash(JSON.stringify([ex.shapes, ex.features])) : ""; };

/** what this browser kept, read once */
let exKept: ExCache | null | undefined;
/** The kept copy for the core that runs now (any core's before it is up: a thumbnail, not a drawing). */
function cached(id: string): Mark[] | null {
  if (exKept === undefined) exKept = readJson<ExCache>(EX_KEY);
  const v = exKept?.marks[id];
  const ver = useStudio.getState().info?.core_version;
  if (!v || v.key !== exampleKey(id) || (ver && exKept!.core !== ver)) return null;
  return v.marks;
}

/** An example's features planned one after another; false when Home closed
 *  meanwhile (it starts again when Home shows). */
async function planExample(id: string): Promise<boolean> {
  const doc = exampleDoc(id);
  if (!doc) return true;
  const p = planned(doc);
  for (const r of p.reqs) {
    if (marksByReq.has(r.key)) continue;
    if (!isHome()) return false;
    // a marker that does not plan is left out of the picture
    try { noteMark(r.key, markOf(await core.plan(r.req))); } catch { if (coreStatus().state !== "ready") return false; noteMark(r.key, null); }
  }
  const marks = knownMarks(p);
  exMarks.set(id, marks);
  const ver = coreVersion();
  if (exKept === undefined) exKept = readJson<ExCache>(EX_KEY);
  exKept = { core: ver, marks: { ...(exKept && exKept.core === ver ? exKept.marks : {}), [id]: { key: exampleKey(id), marks } } };
  writeJson(EX_KEY, exKept);
  notify();
  return true;
}

/** An example's marks: none for a face (it has no marker), the kept copy, else
 *  planned in the background once Home shows it (the shapes draw meanwhile). */
export function useExampleMarks(id: string): Mark[] {
  const marks = useSyncExternalStore(subscribe, () => exMarks.get(id));
  if (marks) return marks;
  if (!example(id)?.features?.length) return [];
  const copy = cached(id);
  if (copy) return copy;
  if (isHome()) {
    if (!asked.has(id)) { asked.add(id); queue.push({ run: () => planExample(id) }); }
    // after this render (planning never runs inside one); a Home shown again goes on
    queueMicrotask(kick);
  }
  return [];
}

/** For the e2e (probe): the examples' marks known now, by id. */
export function exampleMarksKnown(): Record<string, number> {
  return Object.fromEntries([...exMarks].map(([k, v]) => [k, v.length]));
}

// ------------------------------------------------------------ the planning, in the background

/** One picture's planning: false when it stopped (Home closed, the core
 *  went): it runs again, from where it was, when Home shows. */
interface Job { run: () => Promise<boolean> }
let queue: Job[] = [];
let running = false;

async function drain(): Promise<void> {
  if (running) return;
  running = true;
  try {
    while (queue.length) {
      // WHY only while Home shows: the editor's own calls never wait behind a thumbnail
      if (!isHome() || coreStatus().state !== "ready" || useStudio.getState().facts.state !== "ok") return;
      const job = queue.shift()!;
      let done = true;
      try { done = await job.run(); } catch { /* a picture that cannot be made is not made */ }
      if (!done) { queue = [job, ...queue]; return; }
    }
  } finally {
    running = false;
  }
}

/** Plan the pictures asked for, when the core and its presets are ready. */
function kick(): void {
  if (queue.length) void drain();
}
onCoreStatus(kick);
useStudio.subscribe((s, prev) => { if (s.facts.state !== prev.facts.state) kick(); });
