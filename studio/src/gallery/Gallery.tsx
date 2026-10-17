// The gallery (Zach's N-3, 2026-10-17): the Studio's landing page. Golden
// examples, the inputs drawn for the user, grouped by feature and ordered
// markers first (examples/gallery/gallery.json). Each card's thumbnail is
// the example's real plan: its text compiled and planned by the server
// (POST /api/design/preview?top=1, nothing written) and drawn by the 2D
// canvas's own TagSvg. A card opens a copy of the example (POST
// /api/gallery/open); the Studio then shows it in 2D and 3D with the
// example's note: what to look at, and its buttons.
import { Button, Glyph as Icon, IconButton } from "@bam/ui";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import { api, type GalleryItem } from "../api/client";
import type { Pt, SceneDoc, SceneTag } from "../api/types";
import { tagBox, unionBox, type Box } from "../model/geom";
import { parse } from "../model/json";
import { canvasLoops, shapesOf, type Doc } from "../model/design";
import { onShapeFace } from "../canvas/Canvas2D";
import { TagSvg } from "../canvas/TagSvg";
import { useStudio, type Show } from "../store";
import { errorCount } from "./model";

const THUMB_SHOW: Show = { quiet: false, axes: false, outlines: false, ids: false, grid: false };

/** A thumbnail's plan: the example's scene from the server, or why not. */
interface ThumbData { scene: SceneDoc | null; doc: Doc | null; error: string | null; errors: number }

const cache = new Map<string, Promise<ThumbData>>();
let running = 0;
const waiting: (() => void)[] = [];

/** Two previews at a time: the forearm's plan is the slow one (~0.1 s). */
async function slot<T>(fn: () => Promise<T>): Promise<T> {
  if (running >= 2) await new Promise<void>((res) => waiting.push(res));
  running++;
  try {
    return await fn();
  } finally {
    running--;
    waiting.shift()?.();
  }
}

function thumbData(item: GalleryItem): Promise<ThumbData> {
  const key = `${item.name}|${item.text ?? ""}`;
  let p = cache.get(key);
  if (!p) {
    p = slot(async () => {
      if (!item.text) return { scene: null, doc: null, error: `no file ${item.file}`, errors: 1 };
      let doc: Doc | null = null;
      try { doc = parse(item.text).value as Doc; } catch { doc = null; }
      try {
        const r = await api.designPreview(item.text, false);
        if (!r.scene) return { scene: null, doc, error: r.error?.message ?? "did not compile", errors: 1 };
        return { scene: r.scene, doc, error: null, errors: errorCount(r.scene, r.issues ?? []) };
      } catch (e) {
        return { scene: null, doc, error: String(e), errors: 1 };
      }
    });
    cache.set(key, p);
  }
  return p;
}

const f4 = (v: number) => String(Math.round(v * 10000) / 10000);
const pathD = (pts: Pt[]) => pts.length ? `M${pts.map((p) => `${f4(p[0])} ${f4(p[1])}`).join("L")}Z` : "";

/** The example drawn as the 2D canvas draws it: the shapes, then every tag
 *  from its plan, the side faces unfolded with their hinges. */
export const Thumb = memo(function Thumb({ item }: { item: GalleryItem }) {
  const [d, setD] = useState<ThumbData | null>(null);
  useEffect(() => {
    let live = true;
    void thumbData(item).then((x) => { if (live) setD(x); });
    return () => { live = false; };
  }, [item.name, item.text]);
  const drawn = useMemo(() => {
    if (!d?.scene) return null;
    const infos = shapesOf(d.doc);
    const tops = infos.filter((x) => x.hk === null);
    const boxes: Box[] = [];
    for (const s of tops) {
      const { outer } = canvasLoops(s);
      if (!outer.length) continue;
      const xs = outer.map((p) => p[0]), ys = outer.map((p) => p[1]);
      boxes.push({ x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) });
    }
    const tags: SceneTag[] = d.scene.tags.filter((t) => !t.hidden);
    for (const t of tags) {
      const b = tagBox(t);
      if (b) boxes.push(b);
    }
    const b = unionBox(boxes);
    if (!b) return null;
    const pad = Math.max(b.x1 - b.x0, b.y1 - b.y0) * 0.05 + 2;
    const vb = [b.x0 - pad, -(b.y1 + pad), b.x1 - b.x0 + 2 * pad, b.y1 - b.y0 + 2 * pad];
    const shapes = tops.map((s) => {
      const { outer, holes: inner } = canvasLoops(s);
      if (!outer.length) return null;
      const holes = infos.filter((x) => x.parent === s.key).map((x) => canvasLoops(x).outer);
      return (
        <g key={s.key} className={`shape${s.body ? " extruded" : ""}`}>
          <path className="shape-fill" fillRule="evenodd" d={pathD(outer) + [...inner, ...holes].map(pathD).join("")} />
        </g>
      );
    });
    const lines = tops.map((s) => {
      const { outer } = canvasLoops(s);
      return outer.length ? <path key={s.key} className={`shape-line${s.body ? " extruded" : ""}`} d={pathD(outer)} /> : null;
    });
    const hinges = tags.filter((t) => t.source?.hinge_xy).map((t) => {
      const [p, q] = t.source!.hinge_xy!;
      return <line key={`h${t.uid}`} className="hinge" x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} />;
    });
    return { vb, shapes, lines, hinges, tags };
  }, [d]);
  const state = !d ? "loading" : d.error ? "error" : "ready";
  return (
    <div className="gal-thumb" data-thumb={item.name} data-state={state} data-tags={drawn?.tags.length ?? 0}
      data-errors={d ? d.errors : ""} title={d?.error ?? undefined}>
      {drawn && (
        <svg viewBox={drawn.vb.map(f4).join(" ")} preserveAspectRatio="xMidYMid meet" role="img" aria-label={item.title}>
          <g transform="scale(1 -1)">
            <g className="shapes">{drawn.shapes}</g>
            {drawn.tags.map((t) => <TagSvg key={t.uid} tag={t} show={THUMB_SHOW} selected={false} passive={onShapeFace(t)} />)}
            <g className="shape-lines">{drawn.lines}</g>
            {drawn.hinges}
          </g>
        </svg>
      )}
      {state === "loading" && <span className="spin" />}
      {state === "error" && <span className="bad">{d?.error}</span>}
    </div>
  );
});

const CARD_MIN = 240;            // px: a card's narrowest
const CARD_GAP = 12;

/** How many cards fit across the page (the groups pack into these columns). */
function useColumns(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [cols, setCols] = useState(4);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const w = el.getBoundingClientRect().width;
      setCols(Math.max(1, Math.floor((w + CARD_GAP) / (CARD_MIN + CARD_GAP))));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, cols];
}

/** The landing page. */
export function Gallery() {
  const g = useStudio((s) => s.gallery);
  const design = useStudio((s) => s.design);
  const name = useStudio((s) => s.scene.name);
  const example = useStudio((s) => s.example);
  const busy = useStudio((s) => s.busy);
  const ready = useStudio((s) => s.ready);
  const status = useStudio((s) => s.status);
  const st = useStudio.getState();
  const [packRef, cols] = useColumns();
  const groups = g?.groups ?? [];
  const n = groups.reduce((a, x) => a + x.items.length, 0);
  // the Studio holds something worth going back to: a file, or a scene with content
  const back = example ? example.title : design.path ? name : null;
  return (
    <div className="gallery" data-testid="gallery" data-examples={n}>
      <div className="gal-inner">
        <header className="gal-head">
          <div className="gal-title">
            <h1>Gallery</h1>
            <p className="muted">Golden examples of every feature, the inputs drawn for you, markers first. A card opens a copy:
              change any number in the inspector and watch the plan follow. The examples themselves are never written.</p>
          </div>
          <div className="gal-head-actions">
            {back && <Button icon="chevron" testid="gallery-back" onClick={() => st.showStudio()} title="Back to the Studio">Back to {back}</Button>}
          </div>
        </header>
        <nav className="gal-toc" aria-label="Groups">
          {groups.map((x) => (
            <a key={x.id} href={`#gallery`} data-toc={x.id}
              onClick={(e) => { e.preventDefault(); document.getElementById(`gal-${x.id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>{x.title}</a>
          ))}
        </nav>
        {!ready && status.level === "error" && <div className="fatal-inline issue lv-error">{status.text}</div>}
        {!g && <div className="muted pad">Reading the gallery…</div>}
        {g && !n && <div className="muted pad" data-testid="gallery-empty">No gallery on this server (examples/gallery/gallery.json).</div>}
        <div className="gal-groups" ref={packRef} style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
        {groups.map((x, gi) => (
          <section key={x.id} className="gal-group" id={`gal-${x.id}`} data-group={x.id}
            style={{ gridColumn: `span ${Math.min(cols, Math.max(1, x.items.length))}` }}>
            <div className="gal-group-head">
              <span className="gal-num">{gi + 1}</span>
              <h2>{x.title}</h2>
              <span className="muted" title={x.line}>{x.line}</span>
            </div>
            <div className="gal-cards" style={{ gridTemplateColumns: `repeat(${Math.min(cols, Math.max(1, x.items.length))}, minmax(0, 1fr))` }}>
              {x.items.map((it) => (
                <button key={it.name} type="button" className="gal-card" data-example={it.name} disabled={busy > 0}
                  onClick={() => void st.openGallery(it.name)} title={`Open a copy of ${it.file}`}>
                  <Thumb item={it} />
                  <span className="gal-card-text">
                    <b>{it.title}</b>
                    <span className="muted">{it.line}</span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        ))}
        </div>
      </div>
    </div>
  );
}

const ACTION_WORDS: Record<string, { label: string; icon: string; hint: string }> = {
  "3d": { label: "3D view", icon: "view3d", hint: "the 3D view (Tab toggles)" },
  sheet: { label: "Sticker sheet…", icon: "sticker", hint: "Export › Sticker sheet…" },
  send: { label: "Send to PrusaSlicer…", icon: "send", hint: "Export › Send to PrusaSlicer…" },
  ids: { label: "Renumber all", icon: "renumber", hint: "the IDs table's Renumber all" },
};

/** Over the opened copy: what to look at, the example's buttons, the way
 *  back, the neighbours. */
export function ExampleNote() {
  const ex = useStudio((s) => s.example);
  const g = useStudio((s) => s.gallery);
  const view = useStudio((s) => s.view);
  const [open, setOpen] = useState(true);
  useEffect(() => setOpen(true), [ex?.name]);
  if (!ex) return null;
  const st = useStudio.getState();
  const all = (g?.groups ?? []).flatMap((x) => x.items.map((it) => ({ ...it, group: x.title })));
  const i = all.findIndex((x) => x.name === ex.name);
  const prev = i > 0 ? all[i - 1] : null;
  const next = i >= 0 && i < all.length - 1 ? all[i + 1] : null;
  const group = i >= 0 ? all[i].group : "";
  const act = (a: string) => {
    if (a === "3d") return st.setView(view === "3d" ? "2d" : "3d");
    if (a === "sheet") return st.setDialog({ kind: "sheet" });
    if (a === "send") return st.setDialog({ kind: "send" });
    if (a === "ids") return st.renumber();
  };
  if (!open) {
    return (
      <button type="button" className="example-chip" data-testid="example-note-open" onClick={() => setOpen(true)} title="What to look at">
        <Icon name="help" /> {ex.title}
      </button>
    );
  }
  return (
    <div className="example-note" data-testid="example-note" data-example={ex.name} onPointerDown={(e) => e.stopPropagation()}>
      <div className="en-head">
        <Icon name="grid" />
        <span className="en-title"><b>{ex.title}</b><span className="muted"> · {group}</span></span>
        <span className="grow" />
        <IconButton icon="close" title="Hide the note" onClick={() => setOpen(false)} testid="example-note-hide" />
      </div>
      <div className="en-look" data-testid="example-look">{ex.look}</div>
      <div className="en-actions">
        {(ex.actions ?? []).map((a) => ACTION_WORDS[a] && (
          <Button key={a} icon={a === "3d" ? (view === "3d" ? "view2d" : "view3d") : ACTION_WORDS[a].icon} testid={`example-act-${a}`}
            title={ACTION_WORDS[a].hint} onClick={() => void act(a)}>{a === "3d" ? (view === "3d" ? "2D view" : "3D view") : ACTION_WORDS[a].label}</Button>
        ))}
      </div>
      <div className="en-foot">
        <Button icon="grid" testid="example-gallery" onClick={() => st.showGallery()}>Gallery</Button>
        <Button icon="undo" testid="example-reset" title="Open a fresh copy of the example: your changes go" onClick={() => void st.openGallery(ex.name)}>Start over</Button>
        <span className="grow" />
        <IconButton icon="chevron" className="flip-left" title={prev ? `Previous: ${prev.title}` : "the first example"} disabled={!prev}
          onClick={() => prev && void st.openGallery(prev.name)} testid="example-prev" />
        <span className="muted en-count">{i + 1} / {all.length}</span>
        <IconButton icon="chevron" className="flip-right" title={next ? `Next: ${next.title}` : "the last example"} disabled={!next}
          onClick={() => next && void st.openGallery(next.name)} testid="example-next" />
      </div>
      <div className="en-copy muted">A copy: change any number in the inspector; Start over brings the example back.</div>
    </div>
  );
}
