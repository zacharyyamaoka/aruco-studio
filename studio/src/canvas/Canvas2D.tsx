// The 2D canvas, like Figma: an infinite mm canvas (x right, y up), wheel to
// zoom at the cursor, space-drag / middle-drag / right-drag to pan, click
// and shift-click to select, marquee, drag to move (0.5 mm snap), rulers.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import type { SceneDoc, SceneTag } from "../api/types";
import { tagBox, type Box } from "../model/geom";
import { idsText, marqueeSelect } from "../model/scene";
import { patternToScene, useStudio } from "../store";
import { TagSvg } from "./TagSvg";

const RULER = 20;
const STEPS = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];

function niceStep(zoom: number, px = 70): number {
  for (const s of STEPS) if (s * zoom >= px) return s;
  return STEPS[STEPS.length - 1];
}

type Drag =
  | { kind: "pan"; sx: number; sy: number; cx: number; cy: number }
  | { kind: "move"; wx: number; wy: number; names: string[]; from: Record<string, [number, number]>; before: SceneDoc; moved: boolean }
  | { kind: "marquee"; sx: number; sy: number; ex: number; ey: number; additive: boolean }
  | { kind: "label"; tag: string; wx: number; wy: number; inv: number[]; cx: number; cy: number; dx: number; dy: number; moved: boolean };

/** Where a tag's label block is now (its centre, pattern frame mm): the
 *  typed position, else the plan's label parts, else the refused preview. */
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

export function Canvas2D() {
  const host = useRef<HTMLDivElement>(null);
  const scene = useStudio((s) => s.scene);
  const sel = useStudio((s) => s.sel);
  const camera = useStudio((s) => s.camera);
  const viewport = useStudio((s) => s.viewport);
  const show = useStudio((s) => s.show);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [space, setSpace] = useState(false);

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
      if (e.code === "Space" && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
        setSpace(true);
        if (e.target === document.body) e.preventDefault();
      }
    };
    const up = (e: KeyboardEvent) => { if (e.code === "Space") setSpace(false); };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
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

  // wheel: zoom about the cursor (ctrl-wheel, a pinch, the same); shift-wheel pans
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
    const tagEl = (e.target as Element).closest("[data-tag]");
    const additive = e.shiftKey || e.ctrlKey || e.metaKey;
    const labelEl = (e.target as Element).closest("[data-label-drag]");
    if (tagEl && labelEl && !additive) {
      const t = st.scene.tags.find((x) => x.name === tagEl.getAttribute("data-tag"));
      const M = t ? patternToScene(t) : null;
      const c = t ? labelCentre(t) : null;
      if (t && M && c) {
        const [wx, wy] = toWorld(sx, sy);
        setDrag({ kind: "label", tag: t.name, wx, wy, inv: invRigid(M), cx: c[0], cy: c[1], dx: 0, dy: 0, moved: false });
        return;
      }
    }
    if (tagEl) {
      const name = tagEl.getAttribute("data-tag")!;
      let names = st.sel;
      if (additive) {
        st.select(name, true);
        names = useStudio.getState().sel;
        if (!names.includes(name)) return;           // toggled off: no drag
      } else if (!st.sel.includes(name)) {
        st.select(name, false);
        names = [name];
      }
      const [wx, wy] = toWorld(sx, sy);
      const from: Record<string, [number, number]> = {};
      for (const t of st.scene.tags) if (names.includes(t.name)) from[t.name] = [t.x_mm, t.y_mm];
      setDrag({ kind: "move", wx, wy, names, from, before: st.scene, moved: false });
      return;
    }
    if (!additive) st.select(null);
    setDrag({ kind: "marquee", sx, sy, ex: sx, ey: sy, additive });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const [sx, sy] = local(e);
    const st = useStudio.getState();
    if (drag.kind === "pan") {
      st.setCamera({ cx: drag.cx - (sx - drag.sx) / z, cy: drag.cy + (sy - drag.sy) / z });
    } else if (drag.kind === "move") {
      const [wx, wy] = toWorld(sx, sy);
      const dx = wx - drag.wx, dy = wy - drag.wy;
      if (!drag.moved && Math.hypot(dx * z, dy * z) < 3) return;
      st.previewMove(drag.names, dx, dy, drag.from);
      if (!drag.moved) setDrag({ ...drag, moved: true });
    } else if (drag.kind === "label") {
      const [wx, wy] = toWorld(sx, sy);
      const i = drag.inv;
      // the pointer's move in the tag's pattern frame
      const dx = i[0] * (wx - drag.wx) + i[1] * (wy - drag.wy), dy = i[3] * (wx - drag.wx) + i[4] * (wy - drag.wy);
      if (!drag.moved && Math.hypot(dx * z, dy * z) < 3) return;
      setDrag({ ...drag, dx, dy, moved: true });
    } else {
      setDrag({ ...drag, ex: sx, ey: sy });
    }
  };

  const onPointerUp = () => {
    if (!drag) return;
    const st = useStudio.getState();
    if (drag.kind === "move" && drag.moved) {
      st.commitMove(drag.names, drag.before);
    } else if (drag.kind === "label" && drag.moved) {
      const r = (v: number) => Math.round(v * 4) / 4;           // 0.25 mm steps
      st.moveLabel(drag.tag, r(drag.cx + drag.dx), r(drag.cy + drag.dy));
    } else if (drag.kind === "marquee") {
      const [ax, ay] = toWorld(Math.min(drag.sx, drag.ex), Math.max(drag.sy, drag.ey));
      const [bx, by] = toWorld(Math.max(drag.sx, drag.ex), Math.min(drag.sy, drag.ey));
      if (Math.abs(drag.ex - drag.sx) > 3 || Math.abs(drag.ey - drag.sy) > 3) {
        st.setSel(marqueeSelect(st.scene.tags, { x0: ax, y0: ay, x1: bx, y1: by }, st.sel, drag.additive));
      }
    }
    setDrag(null);
  };

  const onDoubleClick = (e: React.MouseEvent) => {
    const tagEl = (e.target as Element).closest("[data-tag]");
    if (tagEl) useStudio.getState().zoomToFit([tagEl.getAttribute("data-tag")!]);
  };

  const world = `translate(${w / 2 - camera.cx * z} ${h / 2 + camera.cy * z}) scale(${z} ${-z})`;
  const visible = scene.tags.filter((t) => !t.hidden);
  const boxes = useMemo(() => Object.fromEntries(visible.map((t) => [t.name, tagBox(t)])), [visible]);

  // the grid and the rulers, in screen space
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

  const selBox = (b: Box | null, k: string, cls: string) => {
    if (!b) return null;
    const [x0, y0] = toScreen(b.x0, b.y1);
    const [x1, y1] = toScreen(b.x1, b.y0);
    return <rect key={k} x={x0 - 3} y={y0 - 3} width={x1 - x0 + 6} height={y1 - y0 + 6} className={cls} />;
  };

  return (
    <div ref={host} className={`canvas2d${space || drag?.kind === "pan" ? " panning" : ""}`} data-view="2d"
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
      onDoubleClick={onDoubleClick} onContextMenu={(e) => e.preventDefault()}>
      <svg width={w} height={h} className="stage" data-zoom={z.toFixed(4)}>
        <g className="gridlines">{gridLines}</g>
        <g data-world="1" transform={world}>
          {visible.map((t) => <TagSvg key={t.uid} tag={t} show={show} selected={sel.includes(t.name)}
            labelShift={drag?.kind === "label" && drag.tag === t.name ? [drag.dx, drag.dy] : undefined} />)}
        </g>
        <g className="overlay">
          {visible.map((t) => sel.includes(t.name) ? selBox(boxes[t.name], `s${t.uid}`, "selbox") : null)}
          {show.ids && visible.map((t) => {
            const b = boxes[t.name];
            if (!b) return null;
            const [x0, y0] = toScreen(b.x0, b.y1);
            const ids = t.plan?.ids ?? [];
            return (
              <text key={`l${t.uid}`} data-label-for={t.name} x={x0} y={y0 - 7} className={`taglabel${t.plan && !t.plan.ok ? " bad" : ""}`}>
                {t.locked ? "🔒 " : ""}{t.name}
                <tspan className="ids"> {t.plan?.ok ? `#${idsText(ids)}` : "not built"}</tspan>
              </text>
            );
          })}
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
      {!visible.length && (
        <div className="empty-hint">Add a tag: <b>Single</b>, <b>Grid</b> or <b>ChArUco</b> in the toolbar (keys S, G, C).</div>
      )}
    </div>
  );
}
