// The sketch viewport: renders the sketch model (./model.ts) and what the
// core planned, and turns pointer events into the store's actions. y up,
// millimetres; pan with the middle or right button or Space-drag, zoom at
// the cursor, F fits. Every feature's marker, outline, Joint Origin and
// label are drawn as its plan() returned them: no marker geometry is made
// here. The turn arc belongs to the feature in focus; the selected feature's
// dimensions (./Dims.tsx) are typed into in place.
import { useEffect, useRef, useState, type ReactElement } from "react";
import type { MarkerPlan, Vec2 } from "../core/contract";
import {
  featureOfRect, featureRect, getFeature, isSet, resetField, setField, updateFeature, type Feature,
} from "../model/doc";
import {
  boxOf, fromLocal, handlePoint, HANDLES, loopD, niceStep, rectFromCorners, toLocal, toScreen, toWorld, zoomAt,
  type Handle,
} from "../model/geom";
import { activeFeatureId, selectedFeatureId, useStudio } from "../store";
import { DimEditor, Dims, isRectDim, layoutDims, type LaidDim } from "./Dims";
import {
  circleFrom, hitTest, inShape, moveShape, plainRect, profileLoops, resizeShape, sameProfile, shapeLoop, type Hit, type Shape,
} from "./model";

type Drag =
  | { kind: "pan"; sx: number; sy: number; cx: number; cy: number }
  | { kind: "move"; id: string; from: Vec2; orig: Shape; moved: boolean }
  | { kind: "resize"; id: string; handle: Handle; orig: Shape }
  | { kind: "label"; fid: string; from: Vec2; orig: Vec2; at: Vec2 }
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
  const plans = useStudio((s) => s.plans);
  const panel = useStudio((s) => s.panel);
  const [hover, setHover] = useState<Hit>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [labelAt, setLabelAt] = useState<{ fid: string; at: Vec2 } | null>(null);
  const [dimEdit, setDimEdit] = useState<{ fid: string; field: string } | null>(null);
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

  // WHY (2026-10-18 review): on a phone the panel (and the toolbar above it)
  // docks over the bottom of the canvas, so when it opens on a feature (and again once that feature first
  // plans) the canvas fits the marker into the part above the panel
  const editId = panel.open ? panel.featureId : null;
  const editRect = editId ? doc.features.find((f) => f.id === editId)?.rectId ?? null : null;
  const editPlanned = !!(editId && plans[editId]);
  useEffect(() => {
    if (!editId || !editRect || !window.matchMedia?.("(max-width: 640px)").matches) return;
    const raf = requestAnimationFrame(() => {
      const vp = host.current?.getBoundingClientRect();
      if (!vp) return;
      // what covers the canvas from below: the panel and the toolbar above it
      const tops = ['[data-testid="extrude-panel"]', '[data-testid="toolbar"]']
        .map((q) => document.querySelector(q)?.getBoundingClientRect().top ?? vp.bottom);
      useStudio.getState().fitFeature(editId, RULER, Math.max(0, vp.bottom - Math.min(...tops)));
    });
    return () => cancelAnimationFrame(raf);
  }, [editId, editRect, editPlanned]);

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

  /** The shape the handles and a drag inside act on: the selected shape, or
   *  the selected feature's rectangle. */
  const selectedShape = (): Shape | undefined => {
    const st = useStudio.getState();
    const s = st.sel;
    if (s?.kind === "shape") return st.doc.shapes.find((x) => x.id === s.id);
    if (s?.kind === "feature" || s?.kind === "origin" || s?.kind === "text") return featureRect(st.doc, getFeature(st.doc, s.id)) ?? undefined;
    return undefined;
  };

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
    if (hEl) {
      const orig = selectedShape();
      if (orig) setDrag({ kind: "resize", id: orig.id, handle: hEl.getAttribute("data-handle") as Handle, orig });
      return;
    }
    const turnEl = target.closest("[data-turn]");
    if (turnEl) { st.turn(turnEl.getAttribute("data-feature") ?? undefined); return; }
    const labelEl = target.closest("[data-label]");
    const lf = labelEl ? getFeature(st.doc, labelEl.getAttribute("data-feature")) : null;
    const lp = lf ? st.plans[lf.id]?.label : null;
    if (lf && lp) {
      setDrag({ kind: "label", fid: lf.id, from: p, orig: lf.label.offset_mm, at: lp.at });
      st.select({ kind: "text", id: lf.id });
      return;
    }
    if (tool === "rect" || tool === "circle") {
      setDrag({ kind: "draw", tool, a: p, b: p });
      return;
    }
    const hit = hitTest(st.doc.shapes, p, EDGE_PX / z);
    const selShape = selectedShape();
    const move = (sh: Shape) => setDrag({ kind: "move", id: sh.id, from: p, orig: sh, moved: false });
    // WHY WYSIWYG (Zach, 2026-10-18): "just clicking the marker on the screen is
    // what brings up the relevant inspector window". A click on a marker, on
    // its rectangle's edge or inside that rectangle selects the feature and
    // opens its panel; a press-drag moves the rectangle. Empty canvas closes it.
    const markerId = st.panel.selector ? null : target.closest("[data-marker]")?.getAttribute("data-marker");
    const markerRect = markerId ? featureRect(st.doc, getFeature(st.doc, markerId)) : null;
    if (markerId && markerRect) {
      st.inspect(markerId);
      move(markerRect);
      return;
    }
    if (hit?.kind === "edge") {
      const s = st.doc.shapes.find((x) => x.id === hit.id)!;
      if (st.panel.selector === "rect" && s.kind === "rect") st.useRect(s.id);
      else if (st.panel.selector) return;
      else {
        const owner = featureOfRect(st.doc, s.id);
        if (owner) st.inspect(owner.id);
        else { if (st.panel.open) st.ok(); st.select({ kind: "shape", id: s.id }); }
      }
      move(s);
      return;
    }
    // inside the selected shape: drag it (as after picking it in a CAD)
    if (selShape && inShape(selShape, p)) {
      move(selShape);
      return;
    }
    if (hit?.kind === "region") {
      if (st.panel.open && st.panel.selector === "profile" && getFeature(st.doc, st.panel.featureId)?.rectId) st.setProfile(hit.ref);
      else if (st.panel.open && st.panel.selector) void st.useProfile(hit.ref);
      else {
        const plain = plainRect(st.doc.shapes, hit.ref);
        const owner = plain ? featureOfRect(st.doc, plain.id) : null;
        if (owner && plain) { st.inspect(owner.id); move(plain); return; }
        if (st.panel.open) st.ok();
        st.select({ kind: "profile", ref: hit.ref });
      }
      return;
    }
    st.closePanel();
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
      setLabelAt({ fid: drag.fid, at: [drag.at[0] + dx, drag.at[1] + dy] });
      st.setLabel("offset_mm", [+(drag.orig[0] + dx).toFixed(1), +(drag.orig[1] + dy).toFixed(1)], drag.fid);
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
  const selShape = selectedShape();
  const selId = selShape?.id ?? null;
  // every feature that has a rectangle and a plan; the one in focus gets the
  // outer dimension and the turn arc
  const drawn = doc.features
    .map((f) => ({ f, rect: featureRect(doc, f), plan: plans[f.id] as MarkerPlan | undefined }))
    .filter((d): d is { f: Feature; rect: NonNullable<ReturnType<typeof featureRect>>; plan: MarkerPlan } => !!d.rect && !!d.plan);
  const activeId = activeFeatureId({ doc, sel, panel });
  const featureRects = new Set(doc.features.map((f) => f.rectId));

  // the selected feature's dimensions (the panel's feature, or the one the selection names)
  const dimFid = panel.open ? panel.featureId : selectedFeatureId(doc, sel);
  const dimOf = drawn.find((d) => d.f.id === dimFid);
  const laid: LaidDim[] = dimOf ? layoutDims(dimOf.f, dimOf.rect, dimOf.plan, scr, z) : [];
  const editDim = dimEdit && dimEdit.fid === dimFid ? laid.find((d) => d.field === dimEdit.field) ?? null : null;

  /** A value typed into a dimension: the marker's sizes through the same
   *  setField / resetField as the panel's rows (the panel's feature through the
   *  store's actions, so its row and the dimension agree), the rectangle's W / H
   *  about its centre as ShapeDims does. An empty value returns it to driven. */
  const commitDim = (fid: string, field: string, text: string) => {
    setDimEdit(null);
    const st = useStudio.getState();
    const f = getFeature(st.doc, fid);
    const t = text.trim().replace(",", ".");
    if (!f) return;
    if (isRectDim(field)) {
      const r = featureRect(st.doc, f);
      const v = Number(t);
      if (r && t !== "" && Number.isFinite(v) && v >= 0.5) st.updateShape({ ...r, [field === "rect.w" ? "w" : "h"]: v });
      return;
    }
    const mine = st.panel.open && st.panel.featureId === fid;
    if (t === "") {
      if (!isSet(f, field)) return;
      if (mine) st.resetField(field);
      else st.setDoc(updateFeature(st.doc, fid, (g) => resetField(g, field)));
      return;
    }
    const v = Number(t);
    if (!Number.isFinite(v) || v < (field === "marker.marker_mm" ? 0.1 : 0)) return;
    if (mine) st.setField(field, v);
    else st.setDoc(updateFeature(st.doc, fid, (g) => setField(g, field, v)));
  };

  let arc: ReactElement | null = null;
  const triads: ReactElement[] = [];
  const labels: ReactElement[] = [];
  for (const { f, rect: fRect, plan } of drawn) {
    // the outline in the rectangle's frame: for the turn arc and the Joint Origin's size
    const lp = plan.outer.map((p) => toLocal(fRect, p));
    const b = boxOf(lp);
    const ow = plan.outer_mm[0], oh = plan.outer_mm[1];
    const turned = f.marker.turn === 90 || f.marker.turn === 270;
    const [dw, dh] = turned ? [oh, ow] : [ow, oh];
    if (f.id === activeId) {
      // the turn arc: over the top of the marker, a handle in its middle
      const mc = fromLocal(fRect, [(b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2]);
      const rr = Math.min(b.x1 - b.x0, b.y1 - b.y0) * 0.42;
      const ang = (fRect.angle_deg * Math.PI) / 180;
      const pt = (a: number) => scr([mc[0] + rr * Math.cos(a + ang), mc[1] + rr * Math.sin(a + ang)]);
      const a0 = pt((55 * Math.PI) / 180), a1 = pt((125 * Math.PI) / 180), hp = pt(Math.PI / 2);
      const R = rr * z;
      if (R > 14) {
        arc = (
          <g className="turn" data-turn="1" data-feature={f.id} data-testid="turn-arc">
            <title>Turn 90° (now {f.marker.turn}°)</title>
            <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-path" />
            <path d={`M${a0[0]} ${a0[1]}A${R} ${R} 0 0 0 ${a1[0]} ${a1[1]}`} className="turn-hit" />
            <circle cx={hp[0]} cy={hp[1]} r={7} className="turn-knob" />
            <circle cx={hp[0]} cy={hp[1]} r={2.5} className="turn-dot" />
          </g>
        );
      }
    }
    const fr = plan.origin.length === 16 ? { o: [plan.origin[3], plan.origin[7]] as Vec2, x: [plan.origin[0], plan.origin[4]] as Vec2, y: [plan.origin[1], plan.origin[5]] as Vec2 } : null;
    if (fr) {
      const L = Math.max(14, Math.min(60, Math.min(dw, dh) * 0.3 * z));
      const o = scr(fr.o);
      const nx = Math.hypot(fr.x[0], fr.x[1]) || 1, ny = Math.hypot(fr.y[0], fr.y[1]) || 1;
      const X: Vec2 = [o[0] + (fr.x[0] / nx) * L, o[1] - (fr.x[1] / nx) * L];
      const Y: Vec2 = [o[0] + (fr.y[0] / ny) * L, o[1] - (fr.y[1] / ny) * L];
      triads.push(
        <g key={f.id} className={`triad${sel?.kind === "origin" && sel.id === f.id ? " on" : ""}`} data-origin={`${fr.o[0]},${fr.o[1]}`} data-feature={f.id}>
          <line x1={o[0]} y1={o[1]} x2={X[0]} y2={X[1]} className="ax-x" />
          <line x1={o[0]} y1={o[1]} x2={Y[0]} y2={Y[1]} className="ax-y" />
          <circle cx={o[0]} cy={o[1]} r={3.5} className="ax-o" />
        </g>,
      );
    }
    // the label: sketch text, its centre where the core put it (or where it is being dragged)
    if (plan.label && plan.label.text) {
      const at = scr(labelAt?.fid === f.id ? labelAt.at : plan.label.at);
      const fs = Math.max(6, (plan.label.height_mm / 0.7) * z);
      labels.push(
        <text key={f.id} className={`label${sel?.kind === "text" && sel.id === f.id ? " on" : ""}`} data-label="1" data-feature={f.id} data-testid="label-text"
          x={at[0]} y={at[1]} fontSize={fs} textAnchor="middle" dominantBaseline="central"
          transform={plan.label.angle_deg ? `rotate(${-plan.label.angle_deg} ${at[0]} ${at[1]})` : undefined}>{plan.label.text}</text>,
      );
    }
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
          {drawn.map(({ f, plan }) => (
            <g key={f.id} className={`marker${sel?.kind === "feature" && sel.id === f.id ? " on" : ""}`} data-marker={f.id}>
              <path d={sl(plan.outer)} className={`outline${plan.overflow_mm > 0 ? " bad" : ""}`} data-marker-outline="1"
                data-overflow={plan.overflow_mm} />
              <path d={plan.black.map((p) => sl(p.outer) + p.holes.map(sl).join("")).join("")} fillRule="evenodd" className="black" data-marker-black="1" />
            </g>
          ))}
          {shapes.map((s) => (
            <path key={s.id} d={sl(shapeLoop(s))} data-shape={s.id} data-kind={s.kind}
              className={[
                "edge",
                s.id === selId && "on",
                hover?.kind === "edge" && hover.id === s.id && "hover",
                featureRects.has(s.id) && "marker-rect",
              ].filter(Boolean).join(" ")} />
          ))}
        </g>
        {draft}
        {dimOf && <Dims fid={dimOf.f.id} dims={laid} editing={editDim?.field ?? null} onEdit={(field) => setDimEdit({ fid: dimOf.f.id, field })} />}
        {triads}
        {arc}
        {labels}
        <g className="handles">{handles}</g>
        <g className="ruler">
          <rect x={0} y={0} width={w} height={RULER} className="ruler-bg" />
          {ticks}
        </g>
      </svg>
      {editDim && dimFid && (
        <DimEditor key={`${dimFid}:${editDim.field}`} dim={editDim}
          onCommit={(t) => commitDim(dimFid, editDim.field, t)} onCancel={() => setDimEdit(null)} />
      )}
      {panel.selector && (
        <div className="vp-hint" data-testid="selector-hint">
          {panel.selector === "rect" ? "Select a rectangle (its edge) or a profile (inside a region)" : "Select a profile (click inside a region)"}
        </div>
      )}
    </div>
  );
}
