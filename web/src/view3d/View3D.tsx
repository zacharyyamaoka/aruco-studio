// The 3D view (V3 "3D Toggle", Zach 2026-10-20 night): the canvas shows
// every feature's planned layers as solids at true scale (MarkerPlan.layers:
// white, black, the inkjet paper; z along the face normal, 0 = the face), a
// face profile's face as a thin neutral body under them, the sketch's edges
// on z 0. Orbit (left drag), pan (right drag), zoom (wheel), as the old
// Studio's View3D (studio/src/view3d/View3D.tsx, which this ports). It fits
// on open and on F. A click on a marker inspects it, as in 2D.
//
// On the feature in focus, Fusion's Extrude manipulator (./heights.ts
// arrowsOf): a blue arrow per height on the face it moves, a thin dimension
// line beside the solid, and a value box at the arrow ("1.80 mm": grey
// driven, normal set, ↺ back to driven). Dragging an arrow along its normal
// and typing in its box (Enter commits, Esc cancels) both write
// setFieldFor(feature, "extrude.<key>"); a drag is one undo step. The view
// re-renders from the plan whenever it changes.
//
// WHY on the model (Zach, 2026-10-20 night): "Show the extrusion dimensions
// directly on it! I like as we had it before with a drag arrow on the black
// and white part. Important though is to have the option to drag and also
// put in a custom value."
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { token, useTheme } from "@bam/ui";
import type { Vec2 } from "../core/contract";
import { featurePreset, getFeature, referenceFace } from "../model/doc";
import { profileLoops, shapeLoop, sketchBox } from "../sketch/model";
import { activeFeatureId, useStudio } from "../store";
import { dimLine, extrudeArrow, zOnAxis } from "./Gizmo";
import { carved, solid, type Cut } from "./carve";
import { arrowsOf, fmtMm, heightsOf, snapHeight, type ArrowSpec } from "./heights";
import { view3d, type Arrow3D } from "./probe3d";
import "./view3d.css";

const FOV = 35;
/** the near plane's floor, mm (it moves out to half the way to the model: loop) */
const NEAR = 0.1;
const TILT = (50 * Math.PI) / 180;
const COLOURS = { face: 0xb9c0ca, white: 0xf3f3f0, black: 0x17191d };
/** the arrows' length on screen, px (Fusion's manipulators keep their size as you zoom) */
const ARROW_PX = 64;
/** how deep a face profile's body is drawn under it, mm: context only */
const FACE_MM = 3;
/** a press on an arrow moves this far before it drags (a click sets nothing) */
const DRAG_PX = 3;

interface Placed { spec: ArrowSpec; obj: THREE.Group }

interface Three {
  renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls;
  root: THREE.Group; marks: THREE.Group; ground: THREE.Group; raf: number;
  /** what is drawn (the solids, the sketch, the grid): the near plane keeps clear of it */
  bounds: THREE.Box3;
  /** how long the last rebuild of the solids took, ms */
  buildMs: number;
  arrows: Placed[];
  drag: { spec: ArrowSpec; fid: string; base: THREE.Vector3; grab: number; sx: number; sy: number; moved: boolean } | null;
}

/** A solid's mesh and its edges (`outline`: the body's outline, its edges drawn
 *  without the pockets'). No polygonOffset: carved() leaves nothing flush. */
function body(geo: THREE.BufferGeometry, colour: keyof typeof COLOURS, fid: string | null, outline = geo): THREE.Group {
  const g = new THREE.Group();
  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: COLOURS[colour], roughness: colour === "black" ? 0.55 : 0.8, metalness: 0, flatShading: true,
  }));
  mesh.userData.feature = fid;
  mesh.userData.colour = colour;
  g.add(mesh);
  if (colour !== "black") {
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(outline, 25),
      new THREE.LineBasicMaterial({ color: 0x6d7682, transparent: true, opacity: 0.55 })));
  }
  if (outline !== geo) outline.dispose();
  return g;
}

function dispose(o: THREE.Object3D) {
  o.traverse((x) => {
    (x as THREE.Mesh).geometry?.dispose();
    const m = (x as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
    if (Array.isArray(m)) m.forEach((mm) => mm.dispose()); else m?.dispose();
  });
}

function clear(g: THREE.Group) {
  for (const c of [...g.children]) { g.remove(c); dispose(c); }
}

/** World mm per screen px at a point (a perspective camera). */
function mmPerPx(camera: THREE.PerspectiveCamera, p: THREE.Vector3, heightPx: number): number {
  const fwd = camera.getWorldDirection(new THREE.Vector3());
  const d = Math.max(1e-3, p.clone().sub(camera.position).dot(fwd));
  return (2 * d * Math.tan((camera.fov * Math.PI) / 360)) / Math.max(1, heightPx);
}

export function View3D() {
  const host = useRef<HTMLDivElement>(null);
  const three = useRef<Three | null>(null);
  const boxes = useRef(new Map<string, HTMLDivElement>());
  const doc = useStudio((s) => s.doc);
  const plans = useStudio((s) => s.plans);
  const active = useStudio((s) => activeFeatureId(s));
  const [theme] = useTheme();

  // the feature in focus: its heights and its arrows
  const focus = useMemo(() => {
    const f = getFeature(doc, active);
    const plan = f ? plans[f.id] : null;
    const preset = featurePreset(doc, f);
    const h = plan && preset ? heightsOf(plan, preset.method) : null;
    return { fid: f?.id ?? null, specs: f && plan && h ? arrowsOf(f, plan, h) : [] };
  }, [doc, plans, active]);

  // set up once: the renderer, the camera (fitted), the controls, the drags
  useEffect(() => {
    const el = host.current!;
    const r0 = el.getBoundingClientRect();
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(Math.max(1, r0.width), Math.max(1, r0.height));
    el.prepend(renderer.domElement);
    renderer.domElement.dataset.canvas3d = "1";
    renderer.domElement.dataset.testid = "canvas3d";
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(FOV, r0.width / Math.max(1, r0.height), NEAR, 20000);
    camera.up.set(0, 0, 1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.screenSpacePanning = true;
    controls.zoomToCursor = true;                   // the wheel zooms at the cursor, as the 2D canvas does
    scene.add(new THREE.HemisphereLight(0xffffff, 0x445066, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(-0.6, -1.0, 1.6);
    scene.add(sun);
    const ground = new THREE.Group(), root = new THREE.Group(), marks = new THREE.Group();
    scene.add(ground, root, marks);

    /** Fit the document (the sketch and every marker) into the view, tilted. */
    const fit = () => {
      const s = useStudio.getState();
      let b = sketchBox(s.doc.shapes);
      for (const p of Object.values(s.plans)) {
        for (const [x, y] of p.outer) b = b ? { x0: Math.min(b.x0, x), y0: Math.min(b.y0, y), x1: Math.max(b.x1, x), y1: Math.max(b.y1, y) } : { x0: x, y0: y, x1: x, y1: y };
      }
      const box = b ?? { x0: -50, y0: -50, x1: 50, y1: 50 };
      const w = Math.max(10, box.x1 - box.x0), h = Math.max(10, box.y1 - box.y0);
      const vf = (FOV * Math.PI) / 360, hf = Math.atan(Math.tan(vf) * camera.aspect);
      const dist = 1.2 * Math.max(h / 2 / Math.tan(vf), w / 2 / Math.tan(hf));
      const cx = (box.x0 + box.x1) / 2, cy = (box.y0 + box.y1) / 2;
      camera.position.set(cx, cy - dist * Math.sin(TILT), dist * Math.cos(TILT));
      controls.target.set(cx, cy, 0);
      controls.update();
    };
    const state: Three = { renderer, scene, camera, controls, root, marks, ground, raf: 0, arrows: [], drag: null, bounds: new THREE.Box3(), buildMs: 0 };
    three.current = state;
    fit();

    const client = (p: THREE.Vector3): Vec2 => {
      const q = p.clone().project(camera);
      const r = renderer.domElement.getBoundingClientRect();
      return [r.left + ((q.x + 1) / 2) * r.width, r.top + ((1 - q.y) / 2) * r.height];
    };
    // the arrows keep their size on screen; the value box sits beside the arrow's head
    const loop = () => {
      const hpx = renderer.domElement.clientHeight;
      const hr = el.getBoundingClientRect();
      for (const a of state.arrows) {
        const k = mmPerPx(camera, a.obj.position, hpx) * ARROW_PX;
        a.obj.scale.setScalar(k);
        const b = boxes.current.get(a.spec.key);
        if (b) {
          const [tx, ty] = client(a.obj.position.clone().add(new THREE.Vector3(0, 0, a.spec.dir * k * 0.85)));
          b.style.transform = `translate(${Math.round(tx - hr.left + 14)}px, ${Math.round(ty - hr.top - b.offsetHeight / 2)}px)`;
        }
      }
      // WHY the near plane at half the way to the model: the ink lies 0.05 mm
      // under the paper's underside, and a depth buffer from 0.1 mm cannot tell
      // 0.05 mm apart at a Letter sheet's fitted distance (~0.5 m), so the ink
      // fought through from below even with the pocket carved (measured
      // 2026-10-20). Depth precision goes with the near plane; the model never
      // comes nearer than it. (A logarithmic depth buffer fixes it too, but
      // writes depth per pixel: no early depth test, no per-sample MSAA depth.)
      const near = state.bounds.isEmpty() ? NEAR : Math.max(NEAR, state.bounds.distanceToPoint(camera.position) / 2);
      if (Math.abs(near - camera.near) > camera.near * 0.02) {
        camera.near = near;
        camera.updateProjectionMatrix();
      }
      renderer.render(scene, camera);
      state.raf = requestAnimationFrame(loop);
    };
    loop();
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      renderer.setSize(r.width, r.height);
      camera.aspect = r.width / r.height;
      camera.updateProjectionMatrix();
    });
    ro.observe(el);
    // F (the store's fit sets the 2D camera): fit here too
    const unFit = useStudio.subscribe((s, prev) => { if (s.camera !== prev.camera) fit(); });

    const rayAt = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      const ray = new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      return ray;
    };
    // an arrow takes the press before OrbitControls does (capture), as the old Studio's did
    let press: Vec2 | null = null;
    const onDown = (e: PointerEvent) => {
      press = e.button === 0 ? [e.clientX, e.clientY] : null;
      if (e.button !== 0 || !state.arrows.length) return;
      const hit = rayAt(e).intersectObjects(state.arrows.map((a) => a.obj), true)[0];
      if (!hit) return;
      let o: THREE.Object3D | null = hit.object;
      while (o && !o.userData.key) o = o.parent;
      const a = state.arrows.find((x) => x.obj === o);
      const fid = activeFeatureId(useStudio.getState());
      if (!a || !fid) return;
      e.stopImmediatePropagation();
      e.preventDefault();
      controls.enabled = false;
      renderer.domElement.setPointerCapture(e.pointerId);
      const base = new THREE.Vector3(a.spec.at[0], a.spec.at[1], a.spec.z);
      state.drag = { spec: a.spec, fid, base, grab: zOnAxis(rayAt(e).ray, base), sx: e.clientX, sy: e.clientY, moved: false };
      // the drag's edits are one undo step
      useStudio.getState().gesture(true);
    };
    const onMove = (e: PointerEvent) => {
      const d = state.drag;
      if (!d) return;
      if (!d.moved && Math.hypot(e.clientX - d.sx, e.clientY - d.sy) < DRAG_PX) return;
      d.moved = true;
      const st = useStudio.getState();
      const f = getFeature(st.doc, d.fid);
      const v = snapHeight(d.spec.value + d.spec.dir * (zOnAxis(rayAt(e).ray, d.base) - d.grab), featurePreset(st.doc, f), e.shiftKey);
      if (f && f.extrude[d.spec.key] !== v) st.setFieldFor(d.fid, d.spec.field, v);
    };
    const onUp = (e: PointerEvent) => {
      if (state.drag) {
        state.drag = null;
        controls.enabled = true;
        useStudio.getState().gesture(false);
        press = null;
        return;
      }
      // a click (not an orbit) on a marker inspects it
      if (!press || e.button !== 0 || Math.hypot(e.clientX - press[0], e.clientY - press[1]) > 4) { press = null; return; }
      press = null;
      const hit = rayAt(e).intersectObjects(root.children, true).find((i) => i.object instanceof THREE.Mesh && i.object.userData.feature);
      if (hit) useStudio.getState().inspect(hit.object.userData.feature as string);
    };
    const dom = renderer.domElement;
    dom.addEventListener("pointerdown", onDown, true);
    dom.addEventListener("pointermove", onMove);
    dom.addEventListener("pointerup", onUp);
    dom.addEventListener("pointercancel", onUp);

    view3d.probe = () => {
      const st = useStudio.getState();
      const solids: Record<string, number> = {};
      const whites: Record<string, [number, number, number, number]> = {};
      let faces = 0;
      root.traverse((o) => {
        if (!(o instanceof THREE.Mesh)) return;
        if (o.userData.feature) solids[o.userData.feature] = (solids[o.userData.feature] ?? 0) + 1;
        else if (o.userData.colour === "face") faces += 1;
        if (o.userData.feature && o.userData.colour === "white") {
          // the drawn white as three.js has it (its geometry's box, sketch frame mm), not the plan's polygons
          const b = new THREE.Box3().setFromObject(o), w = whites[o.userData.feature];
          whites[o.userData.feature] = w ? [Math.min(w[0], b.min.x), Math.min(w[1], b.min.y), Math.max(w[2], b.max.x), Math.max(w[3], b.max.y)]
            : [b.min.x, b.min.y, b.max.x, b.max.y];
        }
      });
      const arrows: Arrow3D[] = state.arrows.map(({ spec, obj }) => {
        const b = boxes.current.get(spec.key)?.getBoundingClientRect();
        return {
          key: spec.key, field: spec.field, value: spec.value, driven: spec.driven, base3d: [spec.at[0], spec.at[1], spec.z], dir: spec.dir,
          base: client(obj.position), tip: client(obj.position.clone().add(new THREE.Vector3(0, 0, spec.dir * obj.scale.z))),
          box: b ? { x: b.left, y: b.top, w: b.width, h: b.height } : null,
        };
      });
      const f = getFeature(st.doc, activeFeatureId(st));
      const plan = f ? st.plans[f.id] : null;
      /** the camera on the feature in focus, its outline filling the view (or
       *  `far` mm off): straight down (side 1; a hair off vertical, so screen up
       *  stays +y, as in 2D) or up from under the face (side -1, the picture
       *  mirrored), `tilt` degrees off the normal towards -y */
      const square = (side: number, showMarks: boolean, tilt = 0, far?: number) => {
        const b = plan ? plan.outer : [];
        const xs = b.map((q) => q[0]), ys = b.map((q) => q[1]);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const span = Math.max(10, Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
        const dist = far ?? (1.15 * span) / 2 / Math.tan((FOV * Math.PI) / 360);
        const t = (tilt * Math.PI) / 180;
        camera.position.set(cx, cy - dist * Math.max(1e-4, Math.sin(t)), side * dist * Math.cos(t));
        controls.target.set(cx, cy, 0);
        controls.update();
        marks.visible = showMarks;
        for (const el of boxes.current.values()) el.style.visibility = showMarks ? "" : "hidden";
      };
      return {
        feature: state.arrows.length ? activeFeatureId(st) : null,
        heights: plan && featurePreset(st.doc, f) ? heightsOf(plan, featurePreset(st.doc, f)!.method) : null,
        arrows, solids, whites, faces, buildMs: state.buildMs, project: (x: number, y: number, z: number) => client(new THREE.Vector3(x, y, z)),
        frame: () => {
          const t = performance.now();
          renderer.render(scene, camera);
          const gl = renderer.getContext();
          gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array(4));   // waits for the frame
          return performance.now() - t;
        },
        top: (showMarks = true, tilt = 0) => square(1, showMarks, tilt),
        sheet: (showMarks = true) => {
          fit();
          marks.visible = showMarks;
          for (const el of boxes.current.values()) el.style.visibility = showMarks ? "" : "hidden";
        },
        bottom: (showMarks = true, tilt = 0, far?: number) => square(-1, showMarks, tilt, far),
      };
    };

    return () => {
      view3d.probe = null;
      cancelAnimationFrame(state.raf);
      ro.disconnect();
      unFit();
      dom.removeEventListener("pointerdown", onDown, true);
      dom.removeEventListener("pointermove", onMove);
      dom.removeEventListener("pointerup", onUp);
      dom.removeEventListener("pointercancel", onUp);
      if (state.drag) useStudio.getState().gesture(false);
      for (const g of [root, marks, ground]) clear(g);
      controls.dispose();
      renderer.dispose();
      dom.remove();
      three.current = null;
    };
  }, []);

  // the solids, the face bodies and the sketch: rebuilt from the plans
  useEffect(() => {
    const st = three.current;
    if (!st) return;
    const t0 = performance.now();
    st.renderer.setClearColor(new THREE.Color(token("--canvas-3d", "#e4e7ec")));
    clear(st.root);
    clear(st.ground);
    let zMin = 0;
    // a face profile: the face under its markers, a thin neutral body, so a
    // Black-only inlay reads; every recess cut into it ("face") carved out
    const faces = new Map<string, { loops: Vec2[][]; cuts: Cut[] }>();
    for (const f of doc.features) {
      const plan = plans[f.id];
      if (!plan?.layers || !f.profile) continue;
      const key = JSON.stringify(f.profile);
      const pr = referenceFace(doc, f) ? profileLoops(doc.shapes, f.profile) : null;
      if (pr && !faces.has(key)) faces.set(key, { loops: pr.loops, cuts: [] });
      const cuts = (into: string) => plan.layers!.filter((L) => L.op === "cut" && L.into === into);
      faces.get(key)?.cuts.push(...cuts("face"));
      // WHY the ink too (Zach, 2026-10-21: "you need to properly cut away the
      // black shape from the white"): the black is always taken out of the
      // white it sits in -- the cells, the corner mark, a label's ink -- over
      // the depth they share, pocket layer or not, so nothing is drawn flush
      const ink = plan.layers.filter((L) => L.op === "add" && L.colour === "black" && L.polygons.length);
      for (const L of plan.layers) {
        if (L.op !== "add" || L.colour === "none" || !L.polygons.length) continue;
        const own = L.colour === "white" ? [...cuts(L.name), ...ink] : cuts(L.name);
        const g = body(carved(L.polygons, L.z[0], L.z[1], own), L.colour, f.id, solid(L.polygons, L.z[0], L.z[1]));
        g.userData.layer = L.name;
        st.root.add(g);
        zMin = Math.min(zMin, L.z[0]);
      }
    }
    for (const { loops: [outer, ...holes], cuts } of faces.values()) {
      const face = [{ outer, holes }];
      st.root.add(body(carved(face, -FACE_MM, 0, cuts), "face", null, solid(face, -FACE_MM, 0)));
      zMin = Math.min(zMin, -FACE_MM);
    }
    // the sketch's edges on the face plane
    const dark = theme === "dark";
    for (const s of doc.shapes) {
      const pts = shapeLoop(s).map((p) => new THREE.Vector3(p[0], p[1], 0));
      st.ground.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: dark ? 0x9aa4b2 : 0x6d7682, transparent: true, opacity: 0.8 })));
    }
    // the ground grid, 10 mm cells, under everything
    const b = sketchBox(doc.shapes) ?? { x0: -50, y0: -50, x1: 50, y1: 50 };
    const step = 10;
    const size = Math.max(100, Math.ceil((Math.max(b.x1 - b.x0, b.y1 - b.y0) + 80) / (2 * step)) * 2 * step);
    const grid = new THREE.GridHelper(size, size / step, dark ? 0x55606e : 0x9aa3ae, dark ? 0x3a4250 : 0xc4cad2);
    grid.rotation.x = Math.PI / 2;
    grid.position.set(Math.round((b.x0 + b.x1) / 2 / step) * step, Math.round((b.y0 + b.y1) / 2 / step) * step, zMin - 0.02);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.5;
    st.ground.add(grid);
    st.bounds.setFromObject(st.root).union(new THREE.Box3().setFromObject(st.ground));
    st.buildMs = performance.now() - t0;
  }, [doc, plans, theme]);

  // the feature in focus: its arrows and dimension lines
  useEffect(() => {
    const st = three.current;
    if (!st) return;
    clear(st.marks);
    const blue = new THREE.Color(token("--accent", "#2f6fed"));
    const ink = new THREE.Color(theme === "dark" ? "#e8edf3" : "#1c222b");
    st.arrows = focus.specs.map((spec) => {
      const obj = extrudeArrow(blue);
      obj.userData.key = spec.key;
      obj.position.set(spec.at[0], spec.at[1], spec.z);
      if (spec.dir < 0) obj.rotation.x = Math.PI;
      const tick = mmPerPx(st.camera, obj.position, st.renderer.domElement.clientHeight) * 4;
      st.marks.add(obj, dimLine(spec.dim.at[0], spec.dim.at[1], spec.dim.edge[0], spec.dim.z0, spec.dim.z1, tick, ink));
      return { spec, obj };
    });
  }, [focus, theme]);

  return (
    <div ref={host} className="view3d" data-testid="view3d" data-feature={focus.fid ?? ""} onContextMenu={(e) => e.preventDefault()}>
      {focus.fid && focus.specs.map((spec) => (
        <ValueBox key={spec.key} spec={spec} fid={focus.fid!}
          bind={(el) => { if (el) boxes.current.set(spec.key, el); else boxes.current.delete(spec.key); }} />
      ))}
    </div>
  );
}

const NAMES: Record<string, string> = { white_mm: "White height", black_mm: "Black height", paper_mm: "Paper thickness" };

/** Fusion's value box at an arrow: the height, grey while driven. A click
 *  types into it at the value's full precision; Enter or leaving it sets a
 *  changed value, Esc puts it back; ↺ returns it to driven.
 *  WHY (review finding #12, 2026-10-21): it opened at toFixed(2) and Enter
 *  committed that, so focus + Enter rounded 0.123456 to 0.12; a blur dropped
 *  what was typed. */
function ValueBox({ spec, fid, bind }: { spec: ArrowSpec; fid: string; bind: (el: HTMLDivElement | null) => void }) {
  const [text, setText] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  /** the text the edit opened with: only a different one is set */
  const seed = useRef<string | null>(null);
  const finish = (keep: boolean) => {
    const from = seed.current;
    seed.current = null;
    const typed = input.current?.value ?? "";
    const v = Number(typed.replace(",", ".").replace(/mm\s*$/i, "").trim());
    if (keep && from !== null && typed !== from && Number.isFinite(v) && v > 0) {
      useStudio.getState().setFieldFor(fid, spec.field, Math.round(v * 1e6) / 1e6);
    }
    setText(null);
  };
  return (
    <div ref={bind} className={`v3-box${spec.driven ? " driven" : ""}`} data-testid="v3-box" data-key={spec.key} data-driven={spec.driven}
      title={`${NAMES[spec.key]}: ${spec.driven ? "driven by the preset. Type or drag the arrow to set it." : "set. ↺ back to driven."}`}>
      <input ref={input} className="v3-input" aria-label={NAMES[spec.key]} data-path={spec.field}
        value={text ?? fmtMm(spec.value)} spellCheck={false}
        onFocus={() => { seed.current = String(spec.value); setText(seed.current); requestAnimationFrame(() => input.current?.select()); }}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => finish(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); finish(true); input.current?.blur(); }
          else if (e.key === "Escape") { e.preventDefault(); finish(false); input.current?.blur(); }
        }} />
      {!spec.driven && (
        <button type="button" className="v3-reset" data-reset={spec.field} aria-label={`Reset ${NAMES[spec.key]} to driven`}
          onClick={() => useStudio.getState().resetFieldFor(fid, spec.field)}>↺</button>
      )}
    </div>
  );
}
