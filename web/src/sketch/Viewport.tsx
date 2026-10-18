// The sketch viewport: renders the sketch model (./model.ts) and what the
// core planned, and turns pointer events into the store's actions. y up,
// millimetres; pan with the middle or right button or Space-drag, zoom at
// the cursor, F fits. The marker, its outline, the Joint Origin and the
// label are drawn as plan() returned them: no marker geometry is made here.
import { useEffect, useRef, useState, type ReactElement } from "react";
import type { Vec2 } from "../core/contract";
import { featureRect } from "../model/doc";
import {
  boxOf, fromLocal, handlePoint, HANDLES, loopD, niceStep, rectFromCorners, toLocal, toScreen, toWorld, zoomAt,
  type Handle,
} from "../model/geom";
import { useStudio } from "../store";
import {
  circleFrom, hitTest, inShape, moveShape, profileLoops, resizeShape, sameProfile, shapeLoop, type Hit, type Shape,
} from "./model";

type Drag =
  | { kind: "pan"; sx: number; sy: number; cx: number; cy: number }
  | { kind: "move"; id: string; from: Vec2; orig: Shape; moved: boolean }
  | { kind: "resize"; id: string; handle: Handle; orig: Shape }
  | { kind: "label"; from: Vec2; orig: Vec2; at: Vec2 }
  | { kind: "draw"; tool: "rect" | "circle"; a: Vec2; b: Vec2 };

const EDGE_PX = 6;
const RULER = 18;

const fmt = (v: number) => String(+v.toFixed(1));

export function Viewport() {
  const host = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  const doc = useStudio((s) => s.doc);
  const camera = useStudio((s) => s.camera);
  const view = useStudio((s) => s.view);
  const sel = useStudio((s) => s.sel);
  const tool = useStudio((s) => s.tool);
  const plan = useStudio((s) => s.plan);
  const panel = useStudio((s) => s.panel);
  const [hover, setHover] = useState<Hit>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [labelAt, setLabelAt] = useState<Vec2 | null>(null);
  const space = useRef(false);
  const fitted = useRef(false);

  const { w, h } = view;
  const z = camera.zoom;

  // the view's size; the first real size fits the sketch
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      useStudio.getState().setView(Math.round(r.width), Math.round(r.height));
      if (!fitted.current) { fitted.current = true; useStudio.getState().fit(); }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const st = useStudio.getState();
      const r = el.getBoundingClientRect();
      const k = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015));
      st.setCamera(zoomAt(st.camera, st.view.w, st.view.h, [e.clientX - r.left, e.clientY - r.top], k));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    const kd = (e: KeyboardEvent) => { if (e.code === "Space" && !(e.target as Element)?.closest?.("input,textarea")) space.current = true; };
    const ku = (e: KeyboardEvent) => { if (e.code === "Space") space.current = false; };
    window.addEventListener("keydown", kd);
    window.addEventListener("keyup", ku);
    return () => {
      el.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", kd);
      window.removeEventListener("keyup", ku);
    };
  }, []);

  // Esc while drawing drops the draft (the app's Esc does the rest)
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") setDrag((d) => (d?.kind === "draw" ? null : d)); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  const local = (e: { clientX: number; clientY: number }): Vec2 => {
    const r = host.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  };
  const world = (e: { clientX: number; clientY: number }): Vec2 => toWorld(camera, w, h, local(e));
  const scr = (p: Vec2): Vec2 => toScreen(camera, w, h, p);

  const onPointerDown = (e: React.PointerEvent) => {
    const st = useStudio.getState();
    const target = e.target as Element;
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
    if (e.button === 1 || e.button === 2 || space.current) {
      setDrag({ kind: "pan", sx: e.clientX, sy: e.clientY, cx: camera.cx, cy: camera.cy });
      return;
    }
    if (e.button !== 0) return;
    const p = world(e);
    const hEl = target.closest("[data-handle]");
    if (hEl && st.sel?.kind === "shape") {
      const orig = st.doc.shapes.find((s) => s.id === (st.sel as { id: string }).id);
      if (orig) setDrag({ kind: "resize", id: orig.id, handle: hEl.getAttribute("data-handle") as Handle, orig });
      return;
    }
    if (target.closest("[data-turn]")) { st.turn(); return; }
    if (target.closest("[data-label]") && st.plan?.label && st.doc.feature) {
      setDrag({ kind: "label", from: p, orig: st.doc.feature.label.offset_mm, at: st.plan.label.at });
      st.select({ kind: "text", id: "label" });
      return;
    }
    if (tool === "rect" || tool === "circle") {
      setDrag({ kind: "draw", tool, a: p, b: p });
      return;
    }
    const hit = hitTest(st.doc.shapes, p, EDGE_PX / z);
    const selShape = st.sel?.kind === "shape" ? st.doc.shapes.find((s) => s.id === (st.sel as { id: string }).id) : undefined;
    if (hit?.kind === "edge") {
      const s = st.doc.shapes.find((x) => x.id === hit.id)!;
      if (st.panel.open && s.kind === "rect" && st.panel.selector !== "profile") st.useRect(s.id);
      else st.select({ kind: "shape", id: s.id });
      setDrag({ kind: "move", id: s.id, from: p, orig: s, moved: false });
      return;
    }
    // inside the selected shape: drag it (as after picking it in a CAD)
    if (selShape && inShape(selShape, p)) {
      setDrag({ kind: "move", id: selShape.id, from: p, orig: selShape, moved: false });
      return;
    }
    if (hit?.kind === "region") {
      if (st.panel.open && st.panel.selector === "profile" && st.doc.feature?.rectId) {
        st.setDoc({ ...st.doc, feature: { ...st.doc.feature, profile: hit.ref } });
        st.setSelector(null);
        st.select({ kind: "profile", ref: hit.ref });
      } else if (st.panel.open && st.panel.selector) void st.useProfile(hit.ref);
      else st.select({ kind: "profile", ref: hit.ref });
      return;
    }
    if (!st.panel.selector) st.select(null);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const st = useStudio.getState();
    if (!drag) {
      if (tool === "select") setHover(hitTest(st.doc.shapes, world(e), EDGE_PX / z));
      else if (hover) setHover(null);
      return;
    }
    if (drag.kind === "pan") {
      st.setCamera({ ...camera, cx: drag.cx - (e.clientX - drag.sx) / z, cy: drag.cy + (e.clientY - drag.sy) / z });
      return;
    }
    const p = world(e);
    if (drag.kind === "draw") setDrag({ ...drag, b: p });
    else if (drag.kind === "move") {
      const dx = p[0] - drag.from[0], dy = p[1] - drag.from[1];
      if (!drag.moved && Math.hypot(dx, dy) * z < 3) return;
      if (!drag.moved) setDrag({ ...drag, moved: true });
      st.updateShape(moveShape(drag.orig, dx, dy));
    } else if (drag.kind === "resize") st.updateShape(resizeShape(drag.orig, drag.handle, p));
    else if (drag.kind === "label") {
      const dx = p[0] - drag.from[0], dy = p[1] - drag.from[1];
      setLabelAt([drag.at[0] + dx, drag.at[1] + dy]);
      st.setLabel("offset_mm", [+(drag.orig[0] + dx).toFixed(1), +(drag.orig[1] + dy).toFixed(1)]);
    }
  };

  const onPointerUp = () => {
    const st = useStudio.getState();
    if (drag?.kind === "draw") {
      const id = `${drag.tool === "rect" ? "r" : "c"}${Date.now().toString(36)}`;
      if (drag.tool === "rect") {
        const r = rectFromCorners(drag.a, drag.b);
        if (r.w >= 1 && r.h >= 1) { st.addShape({ kind: "rect", id, ...r }); st.setTool("select"); }
      } else {
        const c = circleFrom(drag.a, drag.b, id);
        if (c.r >= 0.5) { st.addShape(c); st.setTool("select"); }
      }
    }
    if (drag?.kind === "label") setLabelAt(null);
    setDrag(null);
  };

  // ------------------------------------------------------------ the grid and rulers
  const step = niceStep(z);
  const minor = step / 5;
  const [wx0, wy1] = toWorld(camera, w, h, [0, 0]);
  const [wx1, wy0] = toWorld(camera, w, h, [w, h]);
  const grid: ReactElement[] = [];
  if (minor * z >= 6) {
    for (let x = Math.ceil(wx0 / minor) * minor; x <= wx1; x += minor) {
      const sx = scr([x, 0])[0];
      const major = Math.abs(x / step - Math.round(x / step)) < 1e-6;
      grid.push(<line key={`gx${x.toFixed(3)}`} x1={sx} x2={sx} y1={0} y2={h} className={Math.abs(x) < 1e-9 ? "g axis" : major ? "g major" : "g"} />);
    }
    for (let y = Math.ceil(wy0 / minor) * minor; y <= wy1; y += minor) {
      const sy = scr([0, y])[1];
      const major = Math.abs(y / step - Math.round(y / step)) < 1e-6;
      grid.push(<line key={`gy${y.toFixed(3)}`} y1={sy} y2={sy} x1={0} x2={w} className={Math.abs(y) < 1e-9 ? "g axis" : major ? "g major" : "g"} />);
    }
  }
  const ticks: ReactElement[] = [];
  for (let x = Math.ceil(wx0 / step) * step; x <= wx1; x += step) {
    const sx = scr([x, 0])[0];
    ticks.push(<text key={`tx${x}`} x={sx + 3} y={12}>{+x.toFixed(2)}</text>);
  }
  for (let y = Math.ceil(wy0 / step) * step; y <= wy1; y += step) {
    const sy = scr([0, y])[1];
    ticks.push(<text key={`ty${y}`} x={3} y={sy - 3}>{+y.toFixed(2)}</text>);
  }

  // ------------------------------------------------------------ the sketch
  // WHY screen space: every path is drawn in pixels (not a scaled group), so
  // strokes stay one width at any zoom and a path's box is its geometry's box.
  const sl = (loop: Vec2[]) => loopD(loop.map(scr));
  const shapes = doc.shapes;
  const regionsD = shapes.map((s) => sl(shapeLoop(s))).join("");
  const hoverRef = hover?.kind === "region" ? hover.ref : null;
  const selRef = sel?.kind === "profile" ? sel.ref : null;
  const profD = (ref: typeof hoverRef) => {
    const pr = ref && profileLoops(shapes, ref);
    return pr ? pr.loops.map(sl).join("") : "";
  };
  const selId = sel?.kind === "shape" ? sel.id : null;
  const selShape = selId ? shapes.find((s) => s.id === selId) : undefined;
  const fRect = featureRect(doc);
  const showPlan = plan && fRect;

  // the outline in the rectangle's frame: for the dimension and the turn arc
  let dims: ReactElement | null = null;
  let arc: ReactElement | null = null;
  let triad: ReactElement | null = null;
  if (showPlan && plan) {
    const lp = plan.outer.map((p) => toLocal(fRect, p));
    const b = boxOf(lp);
    const off = 16 / z;
    const A = scr(fromLocal(fRect, [b.x1 + off, b.y0])), B = scr(fromLocal(fRect, [b.x1 + off, b.y1]));
    const C = scr(fromLocal(fRect, [b.x0, b.y1 + off])), D = scr(fromLocal(fRect, [b.x1, b.y1 + off]));
    const e0 = scr(fromLocal(fRect, [b.x1 + 3 / z, b.y0])), e1 = scr(fromLocal(fRect, [b.x1 + 3 / z, b.y1]));
    const f0 = scr(fromLocal(fRect, [b.x0, b.y1 + 3 / z])), f1 = scr(fromLocal(fRect, [b.x1, b.y1 + 3 / z]));
    const ow = plan.outer_mm[0], oh = plan.outer_mm[1];
    const turned = plan && (doc.feature?.marker.turn === 90 || doc.feature?.marker.turn === 270);
    const [dw, dh] = turned ? [oh, ow] : [ow, oh];
    dims = (
      <g className={`dim${plan.overflow_mm > 0 ? " bad" : ""}`} data-dim="outer" data-outer-w={dw} data-outer-h={dh}>
        <line x1={e0[0] + 2} y1={e0[1]} x2={A[0] + 4} y2={A[1]} className="ext" />
        <line x1={e1[0] + 2} y1={e1[1]} x2={B[0] + 4} y2={B[1]} className="ext" />
        <line x1={A[0]} y1={A[1]} x2={B[0]} y2={B[1]} markerStart="url(#arr)" markerEnd="url(#arr)" />
        <text x={(A[0] + B[0]) / 2 + 6} y={(A[1] + B[1]) / 2 + 4}>{fmt(dh)}</text>
        <line x1={f0[0]} y1={f0[1] - 2} x2={C[0]} y2={C[1] - 4} className="ext" />
        <line x1={f1[0]} y1={f1[1] - 2} x2={D[0]} y2={D[1] - 4} className="ext" />
        <line x1={C[0]} y1={C[1]} x2={D[0]} y2={D[1]} markerStart="url(#arr)" markerEnd="url(#arr)" />
        <text x={(C[0] + D[0]) / 2} y={C[1] - 6} textAnchor="middle">outer {fmt(dw)} × {fmt(dh)}</text>
      </g>
    );
    // the turn arc: over the top of the marker, a handle in its middle
    const mc = fromLocal(fRect, [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2]);
    const rr = Math.min(b.x1 - b.x0, b.y1 - b.y0) * 0.42;
    const ang = (fRect.angle_deg * Math.PI) / 180;
    const pt = (a: number) => scr([mc[0] + rr * Math.cos(a + ang), mc[1] + rr * Math.sin(a + ang)]);
    const a0 = pt((55 * Math.PI) / 180), a1 = pt((125 * Math.PI) / 180), hp = pt(Math.PI / 2);
    const R = rr * z;
    if (R > 14) {
      arc = (
        <g className="turn" data-turn="1" data-testid="turn-arc">
          <title>Turn 90° (now {doc.feature?.marker.turn ?? 0}°)</title>
          <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-path" />
          <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-hit" />
          <circle cx={hp[0]} cy={hp[1]} r={7} className="turn-knob" />
          <circle cx={hp[0]} cy={hp[1]} r={2.5} className="turn-dot" />
        </g>
      );
    }
    const fr = plan.origin.length === 16 ? { o: [plan.origin[3], plan.origin[7]] as Vec2, x: [plan.origin[0], plan.origin[4]] as Vec2, y: [plan.origin[1], plan.origin[5]] as Vec2 } : null;
    if (fr) {
      const L = Math.max(14, Math.min(60, Math.min(dw, dh) * 0.3 * z));
      const o = scr(fr.o);
      const nx = Math.hypot(fr.x[0], fr.x[1]) || 1, ny = Math.hypot(fr.y[0], fr.y[1]) || 1;
      const X: Vec2 = [o[0] + (fr.x[0] / nx) * L, o[1] - (fr.x[1] / nx) * L];
      const Y: Vec2 = [o[0] + (fr.y[0] / ny) * L, o[1] - (fr.y[1] / ny) * L];
      triad = (
        <g className={`triad${sel?.kind === "origin" ? " on" : ""}`} data-origin={`${fr.o[0]},${fr.o[1]}`}>
          <line x1={o[0]} y1={o[1]} x2={X[0]} y2={X[1]} className="ax-x" />
          <line x1={o[0]} y1={o[1]} x2={Y[0]} y2={Y[1]} className="ax-y" />
          <circle cx={o[0]} cy={o[1]} r={3.5} className="ax-o" />
        </g>
      );
    }
  }

  // the label: sketch text, its centre where the core put it (or where it is being dragged)
  let label: ReactElement | null = null;
  if (showPlan && plan?.label && plan.label.text) {
    const at = scr(labelAt ?? plan.label.at);
    const fs = Math.max(6, (plan.label.height_mm / 0.7) * z);
    label = (
      <text className={`label${sel?.kind === "text" ? " on" : ""}`} data-label="1" data-testid="label-text"
        x={at[0]} y={at[1]} fontSize={fs} textAnchor="middle" dominantBaseline="central"
        transform={plan.label.angle_deg ? `rotate(${-plan.label.angle_deg} ${at[0]} ${at[1]})` : undefined}>{plan.label.text}</text>
    );
  }

  // the draft being drawn
  let draft: ReactElement | null = null;
  if (drag?.kind === "draw") {
    if (drag.tool === "rect") {
      const r = rectFromCorners(drag.a, drag.b);
      draft = <g><path d={sl(shapeLoop({ kind: "rect", id: "draft", ...r }))} className="edge draft" />
        <text className="draft-dim" x={scr(drag.b)[0] + 10} y={scr(drag.b)[1] - 8}>{fmt(r.w)} × {fmt(r.h)}</text></g>;
    } else {
      const c = circleFrom(drag.a, drag.b, "draft");
      draft = <g><path d={sl(shapeLoop(c))} className="edge draft" />
        <text className="draft-dim" x={scr(drag.b)[0] + 10} y={scr(drag.b)[1] - 8}>Ø {fmt(c.r * 2)}</text></g>;
    }
  }

  // the selected shape's handles
  const handles: ReactElement[] = [];
  if (selShape?.kind === "rect") {
    for (const hn of HANDLES) {
      const [x, y] = scr(handlePoint(selShape, hn));
      handles.push(<rect key={hn} data-handle={hn} x={x - 4} y={y - 4} width={8} height={8} className={`handle h-${hn}`} />);
    }
  } else if (selShape?.kind === "circle") {
    const [x, y] = scr([selShape.cx + selShape.r, selShape.cy]);
    handles.push(<rect key="e" data-handle="e" x={x - 4} y={y - 4} width={8} height={8} className="handle h-e" />);
  }

  const cursor = drag?.kind === "pan" ? "grabbing" : tool !== "select" ? "crosshair" : hover?.kind === "edge" ? "pointer" : "default";

  return (
    <div ref={host} className="viewport" data-testid="viewport" data-tool={tool} style={{ cursor }}
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}
      onPointerLeave={() => !drag && setHover(null)}
      onDoubleClick={(e) => {
        const t = e.target as Element;
        if (t.closest("[data-marker-black],[data-marker-outline]")) useStudio.getState().editFeature();
      }}
      onContextMenu={(e) => e.preventDefault()}>
      <svg ref={svg} width={w} height={h} className="vp-svg" data-zoom={z}>
        <defs>
          <marker id="arr" viewBox="0 0 8 8" refX="4" refY="4" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
            <path d="M0 1L7 4L0 7z" className="arrow" />
          </marker>
        </defs>
        <g className="grid">{grid}</g>
        <g className="sketch">
          <path d={regionsD} fillRule="evenodd" className="regions" data-regions="1" />
          {hoverRef && !sameProfile(hoverRef, selRef) && <path d={profD(hoverRef)} fillRule="evenodd" className="region-hover" data-hover-profile={hoverRef.outer} />}
          {selRef && <path d={profD(selRef)} fillRule="evenodd" className="region-sel" data-sel-profile={selRef.outer} />}
          {showPlan && plan && (
            <g className={`marker${sel?.kind === "feature" ? " on" : ""}`} data-marker="1">
              <path d={sl(plan.outer)} className={`outline${plan.overflow_mm > 0 ? " bad" : ""}`} data-marker-outline="1"
                data-overflow={plan.overflow_mm} />
              <path d={plan.black.map((p) => sl(p.outer) + p.holes.map(sl).join("")).join("")} fillRule="evenodd" className="black" data-marker-black="1" />
            </g>
          )}
          {shapes.map((s) => (
            <path key={s.id} d={sl(shapeLoop(s))} data-shape={s.id} data-kind={s.kind}
              className={[
                "edge",
                s.id === selId && "on",
                hover?.kind === "edge" && hover.id === s.id && "hover",
                fRect?.id === s.id && "marker-rect",
              ].filter(Boolean).join(" ")} />
          ))}
        </g>
        {draft}
        {dims}
        {triad}
        {arc}
        {label}
        <g className="handles">{handles}</g>
        <g className="ruler">
          <rect x={0} y={0} width={w} height={RULER} className="ruler-bg" />
          {ticks}
        </g>
      </svg>
      {panel.selector && (
        <div className="vp-hint" data-testid="selector-hint">
          {panel.selector === "rect" ? "Select a rectangle (its edge) or a profile (inside a region)" : "Select a profile (click inside a region)"}
        </div>
      )}
    </div>
  );
}
