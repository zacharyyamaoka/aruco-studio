// The markers on Home's cards (and File › Examples…'s): each marker's outline
// and its black, as the core planned them, beside the shapes ShapesThumb
// draws. WHY (Zach, 2026-10-21): "It would be nice if the aruco stickers
// showed up in the thumbnail".
// - The document in the editor: its plans are the store's (the editor stays
//   mounted under Home); openHome() keeps a copy in this browser, so a page
//   opened straight on Home draws its markers before the core is up.
// - An example: no plans until planned. Once Home shows it and the core is
//   ready, its features are planned one after another, in the background (no
//   call while Home is closed), and kept in this browser by the core's
//   version: a later visit draws them at once and asks the core nothing.
// Keep it cheap: the shapes draw first; the markers join when they are known.
import { useSyncExternalStore } from "react";
import type { MarkerPlan, Polygon, Vec2 } from "../core/contract";
import { core, coreStatus, onCoreStatus } from "../coreSource";
import { emptyDoc, fillPresets, planRequest, type Doc } from "../model/doc";
import { example } from "../model/examples";
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

function readJson<T>(key: string): T | null {
  try { return JSON.parse(window.localStorage.getItem(key) ?? "null") as T | null; } catch { return null; }
}
function writeJson(key: string, v: unknown): void {
  try { window.localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage blocked or full: kept for this visit only */ }
}

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

// ------------------------------------------------------------ the examples

interface ExCache { core: string; marks: Record<string, { key: string; marks: Mark[] }> }

const exMarks = new Map<string, Mark[]>();
const listeners = new Set<() => void>();
const changed = () => { for (const fn of listeners) fn(); };
/** what this visit has asked the core about: an example is planned once */
const asked = new Set<string>();
let queue: string[] = [];
let running = false;

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
let kept: ExCache | null | undefined;
/** The kept copy for the core that runs now (any core's before it is up: a thumbnail, not a drawing). */
function cached(id: string): Mark[] | null {
  if (kept === undefined) kept = readJson<ExCache>(EX_KEY);
  const v = kept?.marks[id];
  const ver = useStudio.getState().info?.core_version;
  if (!v || v.key !== exampleKey(id) || (ver && kept!.core !== ver)) return null;
  return v.marks;
}

async function drain(): Promise<void> {
  if (running) return;
  running = true;
  try {
    while (queue.length) {
      // WHY only while Home shows: the editor's own calls never wait behind a thumbnail
      if (!isHome() || coreStatus().state !== "ready" || useStudio.getState().facts.state !== "ok") return;
      const id = queue.shift()!;
      const doc = exampleDoc(id);
      if (!doc) continue;
      const marks: Mark[] = [];
      for (const f of doc.features) {
        // Home closed: this example starts again when it shows
        if (!isHome()) { queue.unshift(id); return; }
        const req = planRequest(doc, f);
        if (!req) continue;
        try { marks.push(markOf(await core.plan(req))); } catch { /* a marker that does not plan is left out of the picture */ }
      }
      exMarks.set(id, marks);
      const ver = useStudio.getState().info?.core_version ?? "";
      if (kept === undefined) kept = readJson<ExCache>(EX_KEY);
      kept = { core: ver, marks: { ...(kept && kept.core === ver ? kept.marks : {}), [id]: { key: exampleKey(id), marks } } };
      writeJson(EX_KEY, kept);
      changed();
    }
  } finally {
    running = false;
  }
}

/** Plan the examples asked for, when the core and its presets are ready. */
function kick(): void {
  if (queue.length) void drain();
}
onCoreStatus(kick);
useStudio.subscribe((s, prev) => { if (s.facts.state !== prev.facts.state) kick(); });

const subscribe = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };

/** An example's marks: none for a face (it has no marker), the kept copy, else
 *  planned in the background once Home shows it (the shapes draw meanwhile). */
export function useExampleMarks(id: string): Mark[] {
  const marks = useSyncExternalStore(subscribe, () => exMarks.get(id));
  if (marks) return marks;
  if (!example(id)?.features?.length) return [];
  const copy = cached(id);
  if (copy) return copy;
  if (isHome()) {
    if (!asked.has(id)) { asked.add(id); queue.push(id); }
    // after this render (planning never runs inside one); a Home shown again goes on
    queueMicrotask(kick);
  }
  return [];
}

/** For the e2e (probe): the examples' marks known now, by id. */
export function exampleMarksKnown(): Record<string, number> {
  return Object.fromEntries([...exMarks].map(([k, v]) => [k, v.length]));
}
