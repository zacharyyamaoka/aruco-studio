// The 2D canvas, a bare-bones sketcher (M8 §2): an infinite mm canvas (x
// right, y up), wheel to zoom at the cursor, space / middle / right drag to
// pan. The design file's shapes are drawn under the tags; the tags are drawn
// from their plans. The tools (bottom bar) draw shapes, cut holes and pick
// faces; a selected shape shows its handles. A drag previews (the server
// compiles the new text, nothing written) and the release writes the file.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import type { Pt, SceneTag } from "../api/types";
import { tagBox, type Box } from "../model/geom";
import { dump, parse } from "../model/json";
import { bodyFaces, canvasLoops, findShape, moveShapes, setShape, shapesOf, snap, type Doc, type ShapeInfo } from "../model/design";
import { applyXf, compose, faceNet, inside, outline, rectAt, sizeText } from "../model/shapes";
import { idsText, marqueeSelect } from "../model/scene";
import { addVertex, dragHandle, handlesOf, removeVertex, shapeFromDrag } from "../sketch/handles";
import { patternToScene, TYPED_TOOLS, useStudio } from "../store";
import { TagSvg } from "./TagSvg";

const RULER = 20;
const STEPS = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];

function niceStep(zoom: number, px = 70): number {
  for (const s of STEPS) if (s * zoom >= px) return s;
  return STEPS[STEPS.length - 1];
}

type Drag =
  | { kind: "pan"; sx: number; sy: number; cx: number; cy: number }
  | { kind: "move"; wx: number; wy: number; keys: string[]; dx: number; dy: number; moved: boolean; free: boolean }
  | { kind: "marquee"; sx: number; sy: number; ex: number; ey: number; additive: boolean }
  | { kind: "label"; tag: string; wx: number; wy: number; inv: number[]; cx: number; cy: number; dx: number; dy: number; moved: boolean }
  | { kind: "handle"; key: string; id: string; moved: boolean; text: string | null }
  | { kind: "draw"; tool: "rect" | "circle" | "slot"; a: Pt; b: Pt; centre: boolean; square: boolean };

/** Where a tag's label block is now (its centre, pattern frame mm). */
function labelCentre(t: SceneTag): [number, number] | null {
  const lab = (t.spec.settings.label ?? {}) as any;
  if (lab.position === "manual") return [Number(lab.x_mm || 0), Number(lab.y_mm || 0)];
  const parts = ((t.plan?.label as any)?.parts ?? []) as { rect: number[] }[];
  const prev = (t.plan?.guides?.label_preview ?? []) as unknown as [number, number][][];
  const pts: [number, number][] = parts.length
    ? parts.flatMap((p) => [[p.rect[0], p.rect[1]], [p.rect[2], p.rect[3]]] as [number, number][]) : prev.flat();
  if (!pts.length) return null;
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

/** The inverse of a 2D rigid placement (row-major 4x4, its xy part). */
function invRigid(m: number[]): number[] {
  const [a, b, tx, c, d, ty] = [m[0], m[1], m[3], m[4], m[5], m[7]];
  const det = a * d - b * c;
  const ia = d / det, ib = -b / det, ic = -c / det, id = a / det;
  return [ia, ib, -(ia * tx + ib * ty), ic, id, -(ic * tx + id * ty)];
}

const f4 = (v: number) => String(Math.round(v * 10000) / 10000);
const pathD = (pts: Pt[]) => pts.length ? `M${pts.map((p) => `${f4(p[0])} ${f4(p[1])}`).join("L")}Z` : "";

/** A tag on the top of a shape (or on a bare shape) sits on that shape:
 *  a click outside its marker reaches the shape (to select, to resize). */
export function onShapeFace(t: SceneTag): boolean {
  return !!t.source?.shape && (t.source.face === null || t.source.face === "top" || t.source.face === undefined);
}

export function Canvas2D() {
  const host = useRef<HTMLDivElement>(null);
  const scene = useStudio((s) => s.scene);
  const rev = useStudio((s) => s.sceneRev);
  const doc = useStudio((s) => s.doc);
  const sel = useStudio((s) => s.sel);
  const shapeSel = useStudio((s) => s.shapeSel);
  const camera = useStudio((s) => s.camera);
  const viewport = useStudio((s) => s.viewport);
  const show = useStudio((s) => s.show);
  const tool = useStudio((s) => s.tool);
  const picks = useStudio((s) => s.picks);
  const draft = useStudio((s) => s.draft);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [hover, setHover] = useState<Pt | null>(null);
  /** the document during a handle drag (the shapes drawn from it) */
  const [liveDoc, setLiveDoc] = useState<Doc | null>(null);
  const sceneIssues = scene.issues ?? [];
  const overlapping = new Set(sceneIssues.filter((i) => i.kind === "overlap").flatMap((i) => i.tags));
  const [space, setSpace] = useState(false);
  const activeVertex = useRef<{ key: string; i: number } | null>(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      useStudio.getState().setViewport(Math.round(r.width), Math.round(r.height));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !TYPED_TOOLS.includes(useStudio.getState().tool) && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        setSpace(true);
        if (e.target === document.body) e.preventDefault();
      }
      // Del on a polygon vertex just dragged removes it
      if ((e.key === "Delete" || e.key === "Backspace") && activeVertex.current && !(e.target instanceof HTMLInputElement)) {
        const st = useStudio.getState();
        const av = activeVertex.current;
        if (st.shapeSel.length === 1 && st.shapeSel[0] === av.key) {
          const info = findShape(st.doc, av.key);
          const next = info ? removeVertex(info.shape, av.i) : null;
          if (next) {
            e.preventDefault();
            e.stopImmediatePropagation();
            activeVertex.current = null;
            st.editDoc(`removed point ${av.i} of ${av.key}`, (d) => setShape(d, av.key, next));
          }
        }
      }
    };
    const up = (e: KeyboardEvent) => { if (e.code === "Space") setSpace(false); };
    window.addEventListener("keydown", down, true);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down, true); window.removeEventListener("keyup", up); };
  }, []);

  const { w, h } = viewport;
  const z = camera.zoom;
  const toWorld = useCallback((sx: number, sy: number): [number, number] => [
    (sx - w / 2) / z + camera.cx, -(sy - h / 2) / z + camera.cy,
  ], [w, h, z, camera.cx, camera.cy]);
  const toScreen = useCallback((x: number, y: number): [number, number] => [
    (x - camera.cx) * z + w / 2, -(y - camera.cy) * z + h / 2,
  ], [w, h, z, camera.cx, camera.cy]);

  const local = (e: { clientX: number; clientY: number }): [number, number] => {
    const r = host.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const st = useStudio.getState();
      const cam = st.camera;
      const r = el.getBoundingClientRect();
      const sx = e.clientX - r.left, sy = e.clientY - r.top;
      const W = st.viewport.w, H = st.viewport.h;
      if (e.shiftKey) {
        st.setCamera({ cx: cam.cx + e.deltaY / cam.zoom, cy: cam.cy });
        return;
      }
      const k = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015));
      const nz = Math.max(0.1, Math.min(200, cam.zoom * k));
      const wx = (sx - W / 2) / cam.zoom + cam.cx, wy = -(sy - H / 2) / cam.zoom + cam.cy;
      st.setCamera({ zoom: nz, cx: wx - (sx - W / 2) / nz, cy: wy + (sy - H / 2) / nz });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const shown = liveDoc ?? doc;
  const infos = useMemo(() => shapesOf(shown), [shown]);
  const tops = infos.filter((x) => x.hk === null);
  const moving = drag?.kind === "move" && drag.moved ? drag : null;
  const movedKeys = new Set(moving ? moving.keys : []);
  const offsetOf = (key: string | null | undefined): [number, number] | null => {
    if (!moving || !key) return null;
    const base = key.split("/")[0];
    return movedKeys.has(base) ? [moving.dx, moving.dy] : null;
  };

  const shapeAt = (p: Pt): ShapeInfo | null => {
    for (const s of [...tops].reverse()) {
      const { outer } = canvasLoops(s);
      if (outer.length && inside(outer, p)) return s;
    }
    return null;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    const [sx, sy] = local(e);
    if (sx < RULER || sy < RULER) return;
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const st = useStudio.getState();
    if (space || e.button === 1 || e.button === 2) {
      setDrag({ kind: "pan", sx, sy, cx: st.camera.cx, cy: st.camera.cy });
      return;
    }
    if (e.button !== 0) return;
    const [wx, wy] = toWorld(sx, sy);
    const target = e.target as Element;
    const additive = e.shiftKey || e.ctrlKey || e.metaKey;
    const t = st.tool;
    const handleEl = target.closest("[data-handle]");
    if (handleEl && t === "select") {
      const key = handleEl.getAttribute("data-handle-of")!;
      const id = handleEl.getAttribute("data-handle")!;
      if (id.startsWith("v")) activeVertex.current = { key, i: Number(id.slice(1)) };
      setDrag({ kind: "handle", key, id, moved: false, text: null });
      return;
    }
    if (t === "rect" || t === "circle" || t === "slot") {
      setDrag({ kind: "draw", tool: t, a: [wx, wy], b: [wx, wy], centre: e.altKey, square: e.shiftKey });
      return;
    }
    if (t === "polygon") {
      const p: Pt = e.altKey ? [wx, wy] : [snap(wx), snap(wy)];
      const d = st.draft;
      if (d.length >= 3) {
        const [fx, fy] = toScreen(d[0][0], d[0][1]);
        if (Math.hypot(fx - sx, fy - sy) < 8) { st.confirm(); return; }
      }
      st.setDraft([...d, p]);
      return;
    }
    if (t === "hole" || t === "rhole") {
      st.holeAt([wx, wy], t === "rhole");
      return;
    }
    if (t === "aruco") {
      const faceEl = target.closest("[data-face]");
      if (faceEl) { st.togglePick(faceEl.getAttribute("data-face")!, additive); return; }
      const tagEl = target.closest("[data-tag]");
      const tg = tagEl ? st.scene.tags.find((x) => x.name === tagEl.getAttribute("data-tag")) : null;
      const s = tg?.source?.shape ? findShape(st.doc, tg.source.shape) : shapeAt([wx, wy]);
      if (s) {
        const ref = s.body ? `${s.body.id}.top` : s.id;
        if (ref) st.togglePick(ref, additive);
      } else if (!additive) useStudio.setState({ picks: [] });
      return;
    }
    // select / move (and Extrude: pick the shape)
    const labelEl = target.closest("[data-label-drag]");
    const tagEl = target.closest("[data-tag]");
    if (tagEl && labelEl && !additive) {
      const tg = st.scene.tags.find((x) => x.name === tagEl.getAttribute("data-tag"));
      const M = tg ? patternToScene(tg) : null;
      const c = tg ? labelCentre(tg) : null;
      if (tg && M && c) {
        setDrag({ kind: "label", tag: tg.name, wx, wy, inv: invRigid(M), cx: c[0], cy: c[1], dx: 0, dy: 0, moved: false });
        return;
      }
    }
    if (tagEl) {
      const name = tagEl.getAttribute("data-tag")!;
      let names = st.sel;
      if (additive) {
        st.select(name, true);
        names = useStudio.getState().sel;
        if (!names.includes(name)) return;
      } else if (!st.sel.includes(name)) {
        st.select(name, false);
        names = [name];
      }
      const keys = [...new Set(st.scene.tags.filter((x) => names.includes(x.name)).map((x) => x.source?.shape).filter(Boolean) as string[]),
        ...useStudio.getState().shapeSel];
      setDrag({ kind: "move", wx, wy, keys: [...new Set(keys)], dx: 0, dy: 0, moved: false, free: e.altKey });
      return;
    }
    const holeEl = target.closest("[data-hole]");
    const shapeEl = target.closest("[data-shape-hit]");
    const key = holeEl?.getAttribute("data-hole") ?? shapeEl?.getAttribute("data-shape-hit") ?? null;
    if (key) {
      if (e.altKey && !holeEl) {
        // Alt+click on a polygon's edge: a vertex there
        const info = findShape(st.doc, key);
        const next = info ? addVertex(info.shape, info.xf, [wx, wy]) : null;
        if (next && st.shapeSel.includes(key)) { st.editDoc(`a point on ${key}`, (d) => setShape(d, key, next)); return; }
      }
      if (additive) st.selectShape(key, true);
      else if (!st.shapeSel.includes(key)) st.selectShape(key, false);
      const now = useStudio.getState();
      const keys = [...now.shapeSel, ...now.scene.tags.filter((x) => now.sel.includes(x.name)).map((x) => x.source?.shape).filter(Boolean) as string[]];
      if (now.shapeSel.includes(key)) setDrag({ kind: "move", wx, wy, keys: [...new Set(keys)], dx: 0, dy: 0, moved: false, free: e.altKey });
      return;
    }
    if (!additive) { st.select(null); st.selectShape(null); }
    setDrag({ kind: "marquee", sx, sy, ex: sx, ey: sy, additive });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const [sx, sy] = local(e);
    const [wx, wy] = toWorld(sx, sy);
    const st = useStudio.getState();
    if (st.tool === "polygon") setHover([snap(wx), snap(wy)]);
    if (!drag) return;
    if (drag.kind === "pan") {
      st.setCamera({ cx: drag.cx - (sx - drag.sx) / z, cy: drag.cy + (sy - drag.sy) / z });
    } else if (drag.kind === "move") {
      const dx = wx - drag.wx, dy = wy - drag.wy;
      if (!drag.moved && Math.hypot(dx * z, dy * z) < 3) return;
      setDrag({ ...drag, dx: drag.free ? dx : snap(dx), dy: drag.free ? dy : snap(dy), moved: true });
    } else if (drag.kind === "label") {
      const i = drag.inv;
      const dx = i[0] * (wx - drag.wx) + i[1] * (wy - drag.wy), dy = i[3] * (wx - drag.wx) + i[4] * (wy - drag.wy);
      if (!drag.moved && Math.hypot(dx * z, dy * z) < 3) return;
      setDrag({ ...drag, dx, dy, moved: true });
    } else if (drag.kind === "handle") {
      const text = st.design.text;
      if (!text) return;
      const d = parse(text).value as Doc;
      const info = findShape(d, drag.key);
      if (!info) return;
      const next = dragHandle(info.shape, info.xf, info.parentXf, drag.id, [wx, wy], e.altKey);
      if (!next) { if (drag.moved) { setLiveDoc(d); setDrag({ ...drag, text: null }); } return; }
      setShape(d, drag.key, next);
      const nt = dump(d);
      setLiveDoc(d);
      setDrag({ ...drag, moved: true, text: nt });
      st.preview(nt);
    } else if (drag.kind === "draw") {
      setDrag({ ...drag, b: [wx, wy], centre: e.altKey, square: e.shiftKey });
    } else {
      setDrag({ ...drag, ex: sx, ey: sy });
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    if (!drag) return;
    const t0 = performance.now();
    const st = useStudio.getState();
    if (drag.kind === "move" && drag.moved) {
      const keys = drag.keys;
      if (keys.length) {
        const label = `moved ${keys.length === 1 ? keys[0] : keys.length + " shapes"} by ${drag.dx}, ${drag.dy} mm`;
        const d = parse(st.design.text).value as Doc;
        if (moveShapes(d, keys, drag.dx, drag.dy)) {
          // keep the shapes where they were dropped until the new scene is drawn
          setLiveDoc(d);
          st.commitLive(dump(d), label, t0).finally(() => setLiveDoc(null));
        }
      }
    } else if (drag.kind === "label" && drag.moved) {
      const r = (v: number) => Math.round(v * 4) / 4;
      st.moveLabel(drag.tag, r(drag.cx + drag.dx), r(drag.cy + drag.dy));
    } else if (drag.kind === "handle") {
      if (drag.moved && drag.text) {
        const text = drag.text;
        st.commitLive(text, `${drag.key}: ${drag.id === "rot" ? "turned" : "resized"}`, t0).finally(() => setLiveDoc(null));
      } else setLiveDoc(null);
    } else if (drag.kind === "draw") {
      const made = shapeFromDrag(drag.tool, drag.a, drag.b, { centre: drag.centre, square: drag.square });
      if (made) st.createShape(made.shape, made.at, made.rot);
    } else if (drag.kind === "marquee") {
      const [ax, ay] = toWorld(Math.min(drag.sx, drag.ex), Math.max(drag.sy, drag.ey));
      const [bx, by] = toWorld(Math.max(drag.sx, drag.ex), Math.min(drag.sy, drag.ey));
      if (Math.abs(drag.ex - drag.sx) > 3 || Math.abs(drag.ey - drag.sy) > 3) {
        const box = { x0: ax, y0: ay, x1: bx, y1: by };
        st.setSel(marqueeSelect(st.scene.tags, box, st.sel, drag.additive));
        const hit = tops.filter((s) => {
          const { outer } = canvasLoops(s);
          return outer.some((p) => p[0] >= box.x0 && p[0] <= box.x1 && p[1] >= box.y0 && p[1] <= box.y1);
        }).map((s) => s.key);
        st.setShapeSel(drag.additive ? [...new Set([...st.shapeSel, ...hit])] : hit);
      }
    }
    void e;
    setDrag(null);
  };

  const onDoubleClick = (e: React.MouseEvent) => {
    const tagEl = (e.target as Element).closest("[data-tag]");
    if (tagEl) useStudio.getState().zoomToFit([tagEl.getAttribute("data-tag")!]);
  };

  const world = `translate(${w / 2 - camera.cx * z} ${h / 2 + camera.cy * z}) scale(${z} ${-z})`;
  const visible = scene.tags.filter((t) => !t.hidden);
  const boxes = useMemo(() => Object.fromEntries(visible.map((t) => [t.name, tagBox(t)])), [visible]);

  const step = niceStep(z);
  const minor = step / 5;
  const [wx0, wy1] = toWorld(0, 0);
  const [wx1, wy0] = toWorld(w, h);
  const gridLines: ReactElement[] = [];
  if (show.grid) {
    for (let x = Math.ceil(wx0 / minor) * minor; x <= wx1; x += minor) {
      const sx = toScreen(x, 0)[0];
      const major = Math.abs(x / step - Math.round(x / step)) < 1e-6;
      gridLines.push(<line key={`gx${x.toFixed(3)}`} x1={sx} x2={sx} y1={0} y2={h} className={Math.abs(x) < 1e-9 ? "grid axis" : major ? "grid major" : "grid"} />);
    }
    for (let y = Math.ceil(wy0 / minor) * minor; y <= wy1; y += minor) {
      const sy = toScreen(0, y)[1];
      const major = Math.abs(y / step - Math.round(y / step)) < 1e-6;
      gridLines.push(<line key={`gy${y.toFixed(3)}`} y1={sy} y2={sy} x1={0} x2={w} className={Math.abs(y) < 1e-9 ? "grid axis" : major ? "grid major" : "grid"} />);
    }
  }
  const rx: ReactElement[] = [];
  for (let x = Math.ceil(wx0 / step) * step; x <= wx1; x += step) {
    const sx = toScreen(x, 0)[0];
    rx.push(<g key={`rx${x}`}><line x1={sx} x2={sx} y1={RULER - 6} y2={RULER} /><text x={sx + 2} y={11}>{+x.toFixed(2)}</text></g>);
  }
  const ry: ReactElement[] = [];
  for (let y = Math.ceil(wy0 / step) * step; y <= wy1; y += step) {
    const sy = toScreen(0, y)[1];
    ry.push(<g key={`ry${y}`}><line y1={sy} y2={sy} x1={RULER - 6} x2={RULER} /><text x={13} y={sy - 3} transform={`rotate(-90 13 ${sy - 3})`}>{+y.toFixed(2)}</text></g>);
  }

  const selBox = (b: Box | null, k: string, cls: string, off?: [number, number] | null) => {
    if (!b) return null;
    const ox = off ? off[0] : 0, oy = off ? off[1] : 0;
    const [x0, y0] = toScreen(b.x0 + ox, b.y1 + oy);
    const [x1, y1] = toScreen(b.x1 + ox, b.y0 + oy);
    return <rect key={k} x={x0 - 3} y={y0 - 3} width={x1 - x0 + 6} height={y1 - y0 + 6} className={cls} />;
  };

  // the shapes (under the tags)
  const shapeEls = tops.map((s) => {
    const { outer, holes: inner } = canvasLoops(s);
    if (!outer.length) return null;
    const holes = infos.filter((x) => x.parent === s.key);
    const holeLoops = [...inner, ...holes.map((x) => canvasLoops(x).outer)];
    const off = offsetOf(s.key);
    const on = shapeSel.includes(s.key);
    const picked = tool === "aruco" && (picks.includes(s.id ?? "") || (!!s.body && picks.includes(`${s.body.id}.top`)));
    return (
      <g key={s.key} className={`shape${s.body ? " extruded" : ""}${on ? " sel" : ""}${picked ? " picked" : ""}`}
        transform={off ? `translate(${off[0]} ${off[1]})` : undefined} data-shape-of={s.key}>
        <path className="shape-fill" data-shape-hit={s.key} fillRule="evenodd" d={pathD(outer) + holeLoops.map(pathD).join("")} />
        {holes.map((x) => {
          const lp = canvasLoops(x).outer;
          return <path key={x.key} className={`hole-line${shapeSel.includes(x.key) ? " sel" : ""}`} data-hole={x.key} data-points={lp.length} d={pathD(lp)} />;
        })}
      </g>
    );
  });
  // their outlines over the tags (a tag on a shape never hides its edges)
  const lineEls = tops.map((s) => {
    const { outer } = canvasLoops(s);
    if (!outer.length) return null;
    const off = offsetOf(s.key);
    const on = shapeSel.includes(s.key);
    const picked = tool === "aruco" && (picks.includes(s.id ?? "") || (!!s.body && picks.includes(`${s.body.id}.top`)));
    return (
      <path key={s.key} className={`shape-line${s.body ? " extruded" : ""}${on ? " sel" : ""}${picked ? " picked" : ""}`}
        transform={off ? `translate(${off[0]} ${off[1]})` : undefined}
        data-shape={s.key} data-kind={Object.keys(s.shape).find((k) => ["rect", "circle", "polygon", "slot", "loops"].includes(k))}
        data-points={outer.length} d={pathD(outer)} />
    );
  });

  // the net of each extruded shape while ArUco Extrude picks faces
  const netEls = tool === "aruco" ? tops.filter((s) => s.body).flatMap((s) => {
    const off = offsetOf(s.key);
    return bodyFaces(s).filter((f) => f.face !== "top").map((f) => {
      const net = faceNet(s.shape, s.body!.height, f.face);
      if (!net) return null;
      const loop = rectAt(compose(s.xf, net.xf), net.w, net.h);
      const picked = picks.includes(f.ref);
      return (
        <g key={f.ref} transform={off ? `translate(${off[0]} ${off[1]})` : undefined}>
          <path className={`net-face${picked ? " picked" : ""}`} data-face={f.ref} d={pathD(loop)} />
        </g>
      );
    });
  }) : [];

  // a side tag's hinge (the edge its flap unfolds about), dashed
  const hingeEls = visible.filter((t) => t.source?.hinge_xy).map((t) => {
    const [a, b] = t.source!.hinge_xy!;
    const off = offsetOf(t.source?.shape);
    const [x0, y0] = toScreen(a[0] + (off?.[0] ?? 0), a[1] + (off?.[1] ?? 0));
    const [x1, y1] = toScreen(b[0] + (off?.[0] ?? 0), b[1] + (off?.[1] ?? 0));
    return <line key={`hg${t.uid}`} className="hinge" data-hinge={t.name} data-face={t.source?.face ?? ""} x1={x0} y1={y0} x2={x1} y2={y1} />;
  });

  // the selected shape's handles (one shape or hole)
  let handleEls: ReactElement[] = [];
  if (tool === "select" && shapeSel.length === 1 && !(drag?.kind === "move" && drag.moved)) {
    const info = infos.find((x) => x.key === shapeSel[0]);
    if (info) {
      handleEls = handlesOf(info.shape, info.xf, z).map((hd) => {
        const [x, y] = toScreen(hd.at[0], hd.at[1]);
        if (hd.kind === "rot") {
          const top = applyXf(info.xf, [0, Math.max(...outline(info.shape).map((p) => p[1]))]);
          const [tx, ty] = toScreen(top[0], top[1]);
          return (
            <g key={hd.id}>
              <line className="handle-stem" x1={tx} y1={ty} x2={x} y2={y} />
              <circle className="handle rot" data-handle={hd.id} data-handle-of={info.key} cx={x} cy={y} r={5} />
            </g>
          );
        }
        return <rect key={hd.id} className={`handle ${hd.kind}`} data-handle={hd.id} data-handle-of={info.key} x={x - 4} y={y - 4} width={8} height={8} />;
      });
    }
  }

  // the shape being drawn
  let drawEl: ReactElement | null = null;
  if (drag?.kind === "draw") {
    const made = shapeFromDrag(drag.tool, drag.a, drag.b, { centre: drag.centre, square: drag.square });
    if (made) {
      const xf: [number, number, number] = [made.at[0], made.at[1], made.rot];
      const pts = outline(made.shape).map((p) => applyXf(xf, p));
      drawEl = (
        <g className="draft">
          <path d={pathD(pts)} data-draft="1" />
          <text className="draft-size" x={toScreen(made.at[0], made.at[1])[0]} y={toScreen(made.at[0], made.at[1])[1]} transform="" />
        </g>
      );
    }
  }
  const polyEl = tool === "polygon" && draft.length ? (
    <polyline className="draft-poly" data-draft-points={draft.length}
      points={[...draft, ...(hover ? [hover] : [])].map((p) => p.join(" ")).join(" ")} />
  ) : null;
  const drawSize = drag?.kind === "draw" ? shapeFromDrag(drag.tool, drag.a, drag.b, { centre: drag.centre, square: drag.square }) : null;

  // shape labels (screen space): id and size, the height when extruded
  const shapeLabels = show.ids ? tops.map((s) => {
    const { outer } = canvasLoops(s);
    if (!outer.length) return null;
    const off = offsetOf(s.key) ?? [0, 0];
    const xs = outer.map((p) => p[0]), ys = outer.map((p) => p[1]);
    const [x, y] = toScreen(Math.min(...xs) + off[0], Math.min(...ys) + off[1]);
    if (visible.some((t) => t.source?.shape === s.key && onShapeFace(t)) && !shapeSel.includes(s.key)) return null;
    return <text key={`sl${s.key}`} className="shapelabel" x={x} y={y + 13}>{s.id ?? s.key} · {sizeText(s.shape)}{s.body ? ` · h ${s.body.height}` : ""}</text>;
  }) : [];

  void rev;
  return (
    <div ref={host} className={`canvas2d tool-${tool}${space || drag?.kind === "pan" ? " panning" : ""}`} data-view="2d" data-tool={tool}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
      onPointerLeave={() => setHover(null)}
      onDoubleClick={onDoubleClick} onContextMenu={(e) => e.preventDefault()}>
      <svg width={w} height={h} className="stage" data-zoom={z.toFixed(4)} data-revision={rev}>
        <g className="gridlines">{gridLines}</g>
        <g data-world="1" transform={world}>
          <g className="shapes">{shapeEls}</g>
          {visible.map((t) => {
            const off = offsetOf(t.source?.shape);
            const el = <TagSvg key={t.uid} tag={t} show={show} selected={sel.includes(t.name)} passive={onShapeFace(t)}
              labelShift={drag?.kind === "label" && drag.tag === t.name ? [drag.dx, drag.dy] : undefined} />;
            return off ? <g key={t.uid} transform={`translate(${off[0]} ${off[1]})`}>{el}</g> : el;
          })}
          <g className="shape-lines">{lineEls}</g>
          <g className="nets">{netEls}</g>
          {drawEl}
          {polyEl}
        </g>
        <g className="overlay">
          {hingeEls}
          {visible.map((t) => overlapping.has(t.name) ? selBox(boxes[t.name], `o${t.uid}`, "overlapbox") : null)}
          {visible.map((t) => sel.includes(t.name) ? selBox(boxes[t.name], `s${t.uid}`, "selbox", offsetOf(t.source?.shape)) : null)}
          {shapeLabels}
          {show.ids && visible.map((t) => {
            const b = boxes[t.name];
            if (!b) return null;
            const off = offsetOf(t.source?.shape) ?? [0, 0];
            const [x0, y0] = toScreen(b.x0 + off[0], b.y1 + off[1]);
            const ids = t.plan?.ids ?? [];
            return (
              <text key={`l${t.uid}`} data-label-for={t.name} x={x0} y={y0 - 7} className={`taglabel${t.plan && !t.plan.ok ? " bad" : ""}`}>
                {t.locked ? "🔒 " : ""}{t.name}
                <tspan className="ids"> {t.plan?.ok ? `#${idsText(ids)}` : "not built"}</tspan>
              </text>
            );
          })}
          {handleEls}
          {drawSize && drag?.kind === "draw" && (
            <text className="draft-size" x={toScreen(drag.b[0], 0)[0] + 12} y={toScreen(0, drag.b[1])[1] - 8}>
              {sizeText(drawSize.shape)}
            </text>
          )}
          {drag?.kind === "marquee" && (
            <rect className="marquee" x={Math.min(drag.sx, drag.ex)} y={Math.min(drag.sy, drag.ey)}
              width={Math.abs(drag.ex - drag.sx)} height={Math.abs(drag.ey - drag.sy)} />
          )}
        </g>
        <g className="ruler">
          <rect x={0} y={0} width={w} height={RULER} />
          <rect x={0} y={0} width={RULER} height={h} />
          {rx}{ry}
          <rect x={0} y={0} width={RULER} height={RULER} className="corner" />
          <text x={3} y={13} className="unit">mm</text>
        </g>
      </svg>
      {sceneIssues.length > 0 && (
        <div className="scene-issues" data-testid="scene-issues">
          {sceneIssues.map((i, k) => <div key={k} className={`issue lv-${i.level}`} data-kind={i.kind} data-tags={i.tags.join(",")}>{i.text}</div>)}
        </div>
      )}
      {!visible.length && !tops.length && tool === "select" && (
        <div className="empty-hint">Draw a shape: <b>R</b> rectangle, <b>C</b> circle, <b>P</b> polygon, <b>O</b> slot.
          Then <b>A</b> puts a marker on it, <b>E</b> extrudes it. <b>S</b> finds any command.</div>
      )}
    </div>
  );
}
