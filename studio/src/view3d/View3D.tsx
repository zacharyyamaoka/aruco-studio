// The 3D view: the design file's bodies (each Extrude a prism, drawn here
// from its shape), every tag's solids from its plan (/api/scene?mesh=1; the
// app never triangulates a tag) standing on its face by its full pose, z up.
// Orbit (left drag), pan (right drag), zoom (wheel); click a tag or a body
// to select it; with ArUco Extrude, click a face (Shift for more). A
// selected shape's sketch gets the gizmo (TransformControls) and its body
// the extrude arrow. The toggle keeps the view's centre and scale.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { SceneTag } from "../api/types";
import { planZ, tagBox, unionBox } from "../model/geom";
import { dump, parse } from "../model/json";
import { extrude as setHeight, shapesOf, snap, type Doc, type ShapeInfo } from "../model/design";
import { applyXf, edges, faceNames, holeLoops, inside as insidePt, invert, kindOf, outline, RECT_SIDES, xfOf, type Xf } from "../model/shapes";
import { idsText } from "../model/scene";
import { filtered, patternIn3d, useStudio } from "../store";
import { token, useTheme } from "@bam/ui";
import { extrudeArrow, SketchGizmo, zOnAxis } from "./Gizmo";

const FOV = 35;
const TILT = (50 * Math.PI) / 180;
const COLOURS: Record<string, number> = { body: 0xb9c0ca, white: 0xf3f3f0, black: 0x17191d };
const SEL = 0x38a6e8;
const PICK = 0xff9f1c;

function rowMajor(m: number[]): THREE.Matrix4 {
  const M = new THREE.Matrix4();
  M.set(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12], m[13], m[14], m[15]);
  return M;
}

function xfMatrix(xf: Xf): THREE.Matrix4 {
  const a = (xf[2] * Math.PI) / 180;
  return new THREE.Matrix4().makeRotationZ(a).setPosition(xf[0], xf[1], 0);
}

/** A text sprite (canvas texture), `h` mm tall in the scene. */
export function textSprite(text: string, h: number, colour = "#e8edf3", back = "rgba(20,23,28,0.78)"): THREE.Sprite {
  const px = 48;
  const c = document.createElement("canvas");
  const g = c.getContext("2d")!;
  g.font = `600 ${px}px system-ui, sans-serif`;
  const w = Math.ceil(g.measureText(text).width) + px;
  c.width = w;
  c.height = Math.ceil(px * 1.5);
  g.font = `600 ${px}px system-ui, sans-serif`;
  g.fillStyle = back;
  g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = colour;
  g.textBaseline = "middle";
  g.fillText(text, px / 2, c.height / 2);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sp.scale.set((h * c.width) / c.height, h, 1);
  sp.renderOrder = 10;
  sp.userData.text = text;
  return sp;
}

/** The OpenCV frame's axes of a tag, outside the z-exaggerated root. */
function axesObject(t: SceneTag, zScale: number): THREE.Group | null {
  const p = t.plan;
  const M = patternIn3d(t);
  if (!p || !p.ok || !M || !p.frames) return null;
  const F = p.frames.opencv;
  const W = new THREE.Matrix4().makeScale(1, 1, zScale).multiply(rowMajor(M));
  const len = Math.max(2, Number((p.marker as any)?.marker_length_m || 0.01) * 1000 * 0.42);
  const o = new THREE.Vector3(F[3], F[7], F[11] + 0.05).applyMatrix4(W);
  const R3 = new THREE.Matrix3().setFromMatrix4(rowMajor(M));
  const g = new THREE.Group();
  g.userData.axesOf = t.name;
  const dirs: [number, number, number, number][] = [[F[0], F[4], F[8], 0xff5b4d], [F[1], F[5], F[9], 0x5ad05a], [F[2], F[6], F[10], 0x5b8cff]];
  for (const [x, y, zz, c] of dirs) {
    const d = new THREE.Vector3(x, y, zz).applyMatrix3(R3).normalize();
    const a = new THREE.ArrowHelper(d, o, len, c, len * 0.2, len * 0.12);
    a.userData.axis = true;
    g.add(a);
  }
  return g;
}

/** How deep a tag cuts into its face (mm): its skin, drawn from the plan. */
function skinDepth(t: SceneTag): number {
  const depth = t.spec.target.body_mm ? Math.abs(t.spec.target.body_mm.z1 - t.spec.target.body_mm.z0) : 0;
  let lo = 0;
  for (const L of t.plan?.layers || []) if (L.op === "cut") lo = Math.min(lo, L.z[0]);
  return Math.max(0.05, Math.min(depth - 0.05, Math.max(0.6, -lo + 0.4)));
}

/** A tag's solids, placed by its 3D pose. Its body is drawn only near the
 *  face (a skin `skin` mm deep, clipped), the rest is the prism's. */
function tagObject(t: SceneTag, selected: boolean, clip: THREE.Plane | null): THREE.Group | null {
  const p = t.plan;
  const M = patternIn3d(t);
  if (!p || !p.ok || !M || (!p.mesh && !p.top)) return null;
  const g = new THREE.Group();
  g.name = t.name;
  g.userData.tag = t.name;
  g.matrixAutoUpdate = false;
  g.matrix.copy(rowMajor(M));
  g.userData.drawn = p.mesh ? "mesh" : "light";
  if (!p.mesh) lightSlab(t, g);                   // a drag: the top view as a slab, meshes on release
  for (const b of p.mesh ?? []) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(b.positions, 3));
    geo.setIndex(b.indices);
    const flat = geo.toNonIndexed();
    flat.computeVertexNormals();
    geo.dispose();
    const isBody = b.colour === "body";
    const mat = new THREE.MeshStandardMaterial({
      color: COLOURS[b.colour] ?? 0x999999, roughness: b.colour === "black" ? 0.55 : 0.8, metalness: 0,
      flatShading: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
      clippingPlanes: isBody && clip ? [clip] : null, side: isBody && clip ? THREE.DoubleSide : THREE.FrontSide,
    });
    const mesh = new THREE.Mesh(flat, mat);
    mesh.userData.tag = t.name;
    mesh.userData.what = b.what;
    g.add(mesh);
    if (!(isBody && clip)) {
      const e = new THREE.LineSegments(new THREE.EdgesGeometry(flat, 25),
        new THREE.LineBasicMaterial({ color: b.colour === "black" ? 0x5a6170 : 0x6d7682, transparent: true, opacity: 0.55 }));
      e.userData.tag = t.name;
      g.add(e);
    }
  }
  if (selected) {
    const local = new THREE.Box3();
    g.children.forEach((c) => {
      if (c instanceof THREE.Mesh) {
        c.geometry.computeBoundingBox();
        local.union(c.geometry.boundingBox!);
      }
    });
    local.expandByScalar(0.4);
    const helper = new THREE.Box3Helper(local, SEL);
    helper.userData.sel = true;
    g.add(helper);
  }
  return g;
}

/** The light preview of a tag during a drag (lane speed): its top view
 *  ({colour: polygons}, what the 2D view fills) as a flat slab from its
 *  skin up to its highest z, each colour its own piece. The server sends
 *  no meshes while the pointer is down; the release brings them. */
function lightSlab(t: SceneTag, g: THREE.Group) {
  const top = t.plan?.top;
  if (!top) return;
  const zr = planZ(t.plan) ?? [0, 0];
  const lo = -skinDepth(t), hi = Math.max(zr[1], 0.05);
  const loop = (pts: number[][]) => pts.map(([x, y]) => new THREE.Vector2(x, y));
  for (const colour of ["body", "white", "black"] as const) {
    const polys = top[colour];
    if (!polys?.length) continue;
    const shapes = polys.map((poly) => {
      const sh = new THREE.Shape(loop(poly[0] as unknown as number[][]));
      for (const h of poly.slice(1)) sh.holes.push(new THREE.Path(loop(h as unknown as number[][])));
      return sh;
    });
    const geo = new THREE.ExtrudeGeometry(shapes, { depth: hi - lo, bevelEnabled: false });
    geo.translate(0, 0, lo);
    const mat = new THREE.MeshStandardMaterial({
      color: COLOURS[colour], roughness: colour === "black" ? 0.55 : 0.8, metalness: 0,
      flatShading: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.tag = t.name;
    mesh.userData.what = `light:${colour}`;
    g.add(mesh);
  }
}

/** The outer loop moved in on the sides that carry a tag (their skins
 *  fill the rest): side i inset by inset[i] mm. */
function insetLoop(pts: [number, number][], inset: number[]): [number, number][] {
  if (!inset.some((v) => v > 0)) return pts;
  const n = pts.length;
  const lines = pts.map((p, i) => {
    const q = pts[(i + 1) % n];
    const dx = q[0] - p[0], dy = q[1] - p[1];
    const L = Math.hypot(dx, dy) || 1;
    const nx = -dy / L, ny = dx / L;                 // inward (left of a counter-clockwise edge)
    const d = inset[i] || 0;
    return { p: [p[0] + nx * d, p[1] + ny * d], d: [dx / L, dy / L] };
  });
  return pts.map((_p, j) => {
    const a = lines[(j + n - 1) % n], b = lines[j];
    const den = a.d[0] * b.d[1] - a.d[1] * b.d[0];
    if (Math.abs(den) < 1e-9) return [b.p[0], b.p[1]] as [number, number];
    const t = ((b.p[0] - a.p[0]) * b.d[1] - (b.p[1] - a.p[1]) * b.d[0]) / den;
    return [a.p[0] + a.d[0] * t, a.p[1] + a.d[1] * t] as [number, number];
  });
}

/** A body's prism (z from its bottom to its top), its faces moved in where
 *  tags stand (skins), its edges as they really are. */
function bodyObject(s: ShapeInfo, height: number, skins: Map<string, number>, selected: boolean, picks: string[]): THREE.Group | null {
  const pts = outline(s.shape) as [number, number][];
  if (pts.length < 3) return null;
  const holes = holeLoops(s.shape);
  const k = kindOf(s.shape);
  const zTop = Math.max(0, height), zBot = Math.min(0, height);
  const sides = k === "rect" ? RECT_SIDES : edges(s.shape).map((_e, i) => `side${i}`);
  const sideInset = k === "slot" || k === "circle" ? [] : pts.map((_p, i) => skins.get(sides[i]) ?? skins.get(`side${i}`) ?? 0);
  const sTop = skins.get("top") ?? 0, sBot = skins.get("bottom") ?? 0;
  const make = (loop: [number, number][], z0: number, z1: number) => {
    const sh = new THREE.Shape(loop.map((p) => new THREE.Vector2(p[0], p[1])));
    for (const h of holes) sh.holes.push(new THREE.Path(h.map((p) => new THREE.Vector2(p[0], p[1]))));
    const geo = new THREE.ExtrudeGeometry(sh, { depth: Math.max(0.01, z1 - z0), bevelEnabled: false, curveSegments: 1 });
    geo.translate(0, 0, z0);
    return geo;
  };
  const g = new THREE.Group();
  g.matrixAutoUpdate = false;
  g.matrix.copy(xfMatrix(s.xf));
  g.userData.body = s.body?.id;
  g.userData.shape = s.key;
  const inner = make(insetLoop(pts, sideInset), zBot + sBot, zTop - sTop);
  const mesh = new THREE.Mesh(inner, new THREE.MeshStandardMaterial({ color: COLOURS.body, roughness: 0.85, metalness: 0, flatShading: true }));
  mesh.userData.shape = s.key;
  mesh.userData.body = s.body?.id;
  g.add(mesh);
  const full = make(pts, zBot, zTop);
  const e = new THREE.LineSegments(new THREE.EdgesGeometry(full, 25), new THREE.LineBasicMaterial({ color: selected ? SEL : 0x6d7682, transparent: true, opacity: selected ? 1 : 0.6 }));
  g.add(e);
  // the picked faces (ArUco Extrude), outlined
  for (const ref of picks) {
    if (!s.body || !ref.startsWith(s.body.id + ".")) continue;
    const face = ref.slice(s.body.id.length + 1);
    const outlinePts: THREE.Vector3[] = [];
    if (face === "top" || face === "bottom") {
      const z = face === "top" ? zTop + 0.05 : zBot - 0.05;
      for (const p of [...pts, pts[0]]) outlinePts.push(new THREE.Vector3(p[0], p[1], z));
    } else {
      const i = k === "rect" ? RECT_SIDES.indexOf(face) : Number(face.replace("side", ""));
      const es = edges(s.shape);
      if (es[i]) {
        const [[x0, y0], [x1, y1]] = es[i];
        for (const [x, y, z] of [[x0, y0, zBot], [x1, y1, zBot], [x1, y1, zTop], [x0, y0, zTop], [x0, y0, zBot]]) outlinePts.push(new THREE.Vector3(x, y, z));
      }
    }
    if (outlinePts.length) {
      const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(outlinePts), new THREE.LineBasicMaterial({ color: PICK, depthTest: false }));
      l.renderOrder = 15;
      l.userData.pick = ref;
      g.add(l);
    }
  }
  full.dispose();
  return g;
}

/** A shape that is not extruded: flat on z 0. */
function flatObject(s: ShapeInfo, selected: boolean): THREE.Group | null {
  const pts = outline(s.shape);
  if (pts.length < 3) return null;
  const g = new THREE.Group();
  g.matrixAutoUpdate = false;
  g.matrix.copy(xfMatrix(s.xf));
  g.userData.shape = s.key;
  const sh = new THREE.Shape(pts.map((p) => new THREE.Vector2(p[0], p[1])));
  for (const h of holeLoops(s.shape)) sh.holes.push(new THREE.Path(h.map((p) => new THREE.Vector2(p[0], p[1]))));
  const m = new THREE.Mesh(new THREE.ShapeGeometry(sh), new THREE.MeshBasicMaterial({ color: 0x8e98a6, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false }));
  m.userData.shape = s.key;
  m.position.z = -0.02;
  g.add(m);
  const l = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts.map((p) => new THREE.Vector3(p[0], p[1], 0))),
    new THREE.LineBasicMaterial({ color: selected ? SEL : 0x9aa4b2 }));
  g.add(l);
  return g;
}

/** Which face of a body a hit is on: top, bottom, or the nearest straight side. */
function faceOfHit(s: ShapeInfo, pointWorld: THREE.Vector3, normalWorld: THREE.Vector3, zScale: number): string | null {
  if (normalWorld.z > 0.9) return "top";
  if (normalWorld.z < -0.9) return "bottom";
  const p = applyXf(invert(s.xf), [pointWorld.x, pointWorld.y]);
  const es = edges(s.shape);
  let best = -1, bd = Infinity;
  es.forEach(([a, b], i) => {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
    const d = Math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1]);
    if (d < bd) { bd = d; best = i; }
  });
  void zScale;
  if (best < 0 || bd > 1.5) return null;
  return faceNames(s.shape)[2 + best] ?? null;
}

/** A face's centre in the world (for the tests' clicks). */
function faceCentre(s: ShapeInfo, height: number, face: string): THREE.Vector3 | null {
  const pts = outline(s.shape);
  if (!pts.length) return null;
  const zTop = Math.max(0, height), zBot = Math.min(0, height);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const c: [number, number] = [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  if (face === "top" || face === "bottom") {
    // a point of the face itself: the centre, or the nearest one clear of the holes
    const holes = holeLoops(s.shape);
    const w0 = Math.max(...xs) - Math.min(...xs), h0 = Math.max(...ys) - Math.min(...ys);
    const ok = (p: [number, number]) => insidePt(pts, p) && !holes.some((hl) => insidePt(hl, p));
    let best: [number, number] = c;
    search: for (let k = 0; k <= 8; k++) {
      for (const [dx, dy] of [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [-1, -1], [1, -1], [-1, 1]]) {
        const p: [number, number] = [c[0] + (dx * k * w0) / 18, c[1] + (dy * k * h0) / 18];
        if (ok(p)) { best = p; break search; }
      }
    }
    const w = applyXf(s.xf, best);
    return new THREE.Vector3(w[0], w[1], face === "top" ? zTop : zBot);
  }
  const names = faceNames(s.shape);
  const i = names.indexOf(face) - 2;
  const e = edges(s.shape)[i];
  if (!e) return null;
  const [[x0, y0], [x1, y1]] = e;
  const L = Math.hypot(x1 - x0, y1 - y0) || 1;
  const m = applyXf(s.xf, [(x0 + x1) / 2 + ((y1 - y0) / L) * 0.05, (y0 + y1) / 2 - ((x1 - x0) / L) * 0.05]);
  return new THREE.Vector3(m[0], m[1], (zTop + zBot) / 2);
}

function dispose(o: THREE.Object3D) {
  o.traverse((x) => {
    if ((x as THREE.Mesh).geometry) (x as THREE.Mesh).geometry.dispose();
    const m = (x as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
    const one = (mm: any) => { if (mm?.map) mm.map.dispose(); mm?.dispose?.(); };
    if (Array.isArray(m)) m.forEach(one); else one(m);
  });
}

interface Three {
  renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
  controls: OrbitControls; root: THREE.Group; overlay: THREE.Group; ground: THREE.Group; raf: number;
  gizmo: SketchGizmo; arrow: THREE.Group; sketchGroups: Map<string, THREE.Group>;
  arrowDrag: { key: string; base: THREE.Vector3; h0: number; text: string | null } | null;
  gizmoSketch: { si: number; at: [number, number]; rot: number; id: string | null } | null;
}

export function View3D() {
  const host = useRef<HTMLDivElement>(null);
  const three = useRef<Three | null>(null);
  const allTags = useStudio((s) => s.scene.tags);
  const filter = useStudio((s) => s.filter);
  const tags = filtered(allTags, filter);
  const [theme] = useTheme();
  const doc = useStudio((s) => s.doc);
  const sel = useStudio((s) => s.sel);
  const shapeSel = useStudio((s) => s.shapeSel);
  const show = useStudio((s) => s.show);
  const zScale = useStudio((s) => s.zScale);
  const tool = useStudio((s) => s.tool);
  const picks = useStudio((s) => s.picks);
  const liveDoc = useRef<Doc | null>(null);
  const fitRev = useStudio((s) => s.fitRev);

  // Zoom to fit (F) in 3D: the camera to the store's centre and scale, tilted as at the start
  useEffect(() => {
    const st = three.current;
    if (!st || !fitRev) return;
    const { cx, cy, zoom } = useStudio.getState().camera;
    const h = st.renderer.domElement.clientHeight || useStudio.getState().viewport.h;
    const dist = (h / zoom / 2) / Math.tan((FOV * Math.PI) / 360);
    st.camera.position.set(cx, cy - dist * Math.sin(TILT), dist * Math.cos(TILT));
    st.controls.target.set(cx, cy, 0);
    st.controls.update();
  }, [fitRev]);

  // set up once: renderer, camera from the 2D view's centre and scale
  useEffect(() => {
    const el = host.current!;
    const st = useStudio.getState();
    const { w, h } = st.viewport;
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(w, h);
    renderer.setClearColor(new THREE.Color(token("--canvas-3d", "#e4e7ec")));
    renderer.localClippingEnabled = true;
    el.appendChild(renderer.domElement);
    renderer.domElement.dataset.canvas3d = "1";
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(FOV, w / Math.max(1, h), 0.5, 20000);
    camera.up.set(0, 0, 1);
    const { cx, cy, zoom } = st.camera;
    const dist = (h / zoom / 2) / Math.tan((FOV * Math.PI) / 360);
    camera.position.set(cx, cy - dist * Math.sin(TILT), dist * Math.cos(TILT));
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(cx, cy, 0);
    controls.enableDamping = false;
    controls.screenSpacePanning = true;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.update();
    scene.add(new THREE.HemisphereLight(0xffffff, 0x445066, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(-0.6, -1.0, 1.6);
    scene.add(sun);
    const ground = new THREE.Group();
    scene.add(ground);
    const root = new THREE.Group();
    scene.add(root);
    const overlay = new THREE.Group();
    scene.add(overlay);
    const arrow = extrudeArrow(10);
    arrow.visible = false;
    scene.add(arrow);
    const state: Three = {
      renderer, scene, camera, controls, root, overlay, ground, raf: 0, arrow, sketchGroups: new Map(), arrowDrag: null, gizmoSketch: null,
      gizmo: null as unknown as SketchGizmo,
    };
    state.gizmo = new SketchGizmo(camera, renderer.domElement, scene, controls, {
      onChange(at, rot) {
        // the sketch's bodies and tags follow the gizmo at once
        const gs = state.gizmoSketch;
        if (!gs) return;
        const grp = state.sketchGroups.get(String(gs.si));
        if (!grp) return;
        const now = xfMatrix([at[0], at[1], rot]);
        const was = xfMatrix([gs.at[0], gs.at[1], gs.rot]);
        grp.matrix.copy(now.multiply(was.invert()));
        grp.matrixWorldNeedsUpdate = true;
      },
      onCommit(at, rot) {
        const gs = state.gizmoSketch;
        if (!gs) return;
        const s = useStudio.getState();
        const d = parse(s.design.text).value as Doc;
        const skt = d.sketches?.[gs.si];
        if (!skt) return;
        const [x, y] = xfOf(skt);
        const r0 = Number(skt.rot) || 0;
        if (x === at[0] && y === at[1] && r0 === rot) return;
        if (at[0] || at[1]) skt.at = [at[0], at[1]]; else delete skt.at;
        if (rot) skt.rot = rot; else delete skt.rot;
        s.commitLive(dump(d), `moved ${skt.id ?? "the sketch"} to ${at[0]}, ${at[1]} mm${rot ? `, ${rot}°` : ""}`);
      },
    });
    three.current = state;
    controls.addEventListener("end", () => {
      const t = controls.target;
      const d = camera.position.distanceTo(t);
      const H = useStudio.getState().viewport.h;
      useStudio.getState().setCamera({ cx: t.x, cy: t.y, zoom: H / (2 * d * Math.tan((FOV * Math.PI) / 360)) });
    });
    const loop = () => {
      renderer.render(scene, camera);
      state.raf = requestAnimationFrame(loop);
    };
    loop();
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      renderer.setSize(r.width, r.height);
      camera.aspect = r.width / Math.max(1, r.height);
      camera.updateProjectionMatrix();
    });
    ro.observe(el);

    const rayAt = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      const ray = new THREE.Raycaster();
      ray.setFromCamera(ndc, camera);
      return ray;
    };
    // the extrude arrow first: it takes the drag before OrbitControls does
    const onArrowDown = (e: PointerEvent) => {
      if (e.button !== 0 || !arrow.visible) return;
      const hit = rayAt(e).intersectObject(arrow, true)[0];
      if (!hit) return;
      const s = useStudio.getState();
      const key = s.shapeSel[0];
      const info = shapesOf(s.doc).find((x) => x.key === key);
      if (!info?.body) return;
      e.stopImmediatePropagation();
      e.preventDefault();
      controls.enabled = false;
      renderer.domElement.setPointerCapture(e.pointerId);
      state.arrowDrag = { key, base: new THREE.Vector3(arrow.position.x, arrow.position.y, 0), h0: info.body.height, text: null };
    };
    const onArrowMove = (e: PointerEvent) => {
      const ad = state.arrowDrag;
      if (!ad) return;
      const z = zOnAxis(rayAt(e).ray, ad.base) / useStudio.getState().zScale;
      let hgt = ad.h0 >= 0 ? snap(z) : snap(z);
      if (ad.h0 >= 0 && hgt < 0.5) hgt = 0.5;
      if (ad.h0 < 0 && hgt > -0.5) hgt = -0.5;
      const s = useStudio.getState();
      const d = parse(s.design.text).value as Doc;
      setHeight(d, ad.key, hgt);
      const text = dump(d);
      if (text === ad.text) return;
      ad.text = text;
      liveDoc.current = d;
      draw();
      s.preview(text);
    };
    const onArrowUp = () => {
      const ad = state.arrowDrag;
      if (!ad) return;
      state.arrowDrag = null;
      controls.enabled = true;
      if (ad.text) {
        const s = useStudio.getState();
        const info = shapesOf(liveDoc.current).find((x) => x.key === ad.key);
        s.commitLive(ad.text, `${ad.key}: height ${info?.body?.height ?? "?"} mm`).finally(() => { liveDoc.current = null; });
      }
    };
    renderer.domElement.addEventListener("pointerdown", onArrowDown, true);
    renderer.domElement.addEventListener("pointermove", onArrowMove);
    renderer.domElement.addEventListener("pointerup", onArrowUp);

    // click to select or pick (a drag orbits)
    let down: [number, number] | null = null;
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4 || e.button !== 0 || state.gizmo.dragging) { down = null; return; }
      down = null;
      const hits = rayAt(e).intersectObjects(root.children, true).filter((i) => i.object instanceof THREE.Mesh && i.object.visible);
      const hit = hits[0];
      const s = useStudio.getState();
      const additive = e.shiftKey || e.ctrlKey;
      if (s.tool === "aruco") {
        if (!hit) { if (!additive) useStudio.setState({ picks: [] }); return; }
        const tg = hit.object.userData.tag as string | undefined;
        if (tg) {
          const t = s.scene.tags.find((x) => x.name === tg);
          if (t?.source?.ref) s.togglePick(t.source.ref, additive);
          return;
        }
        const key = hit.object.userData.shape as string | undefined;
        const info = key ? shapesOf(s.doc).find((x) => x.key === key) : null;
        if (!info) return;
        if (!info.body) { if (info.id) s.togglePick(info.id, additive); return; }
        const n = hit.face!.normal.clone().transformDirection(hit.object.matrixWorld);
        const face = faceOfHit(info, hit.point.clone().setZ(hit.point.z / s.zScale), n, s.zScale);
        if (!face) { s.say(kindOf(info.shape) === "circle" ? "a circle's side is curved: it has no flat face for a tag" : "no flat face there", "warn"); return; }
        s.togglePick(`${info.body.id}.${face}`, additive);
        return;
      }
      if (!hit) { s.select(null); s.selectShape(null); return; }
      if (hit.object.userData.tag) s.select(hit.object.userData.tag as string, additive);
      else if (hit.object.userData.shape) s.selectShape(hit.object.userData.shape as string, additive);
    };
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);

    // what the tests read and click
    const probe3d = (window as any).__studio3d || {};
    (window as any).__studio3d = probe3d;
    probe3d.screenOf = (ref: string): [number, number] | null => {
      const s = useStudio.getState();
      const [bid, face] = ref.split(".");
      const info = shapesOf(s.doc).find((x) => x.body?.id === bid);
      if (!info?.body) return null;
      const c = faceCentre(info, info.body.height, face);
      if (!c) return null;
      c.z *= s.zScale;
      const p = c.project(camera);
      const r = renderer.domElement.getBoundingClientRect();
      return [r.left + ((p.x + 1) / 2) * r.width, r.top + ((1 - p.y) / 2) * r.height];
    };
    probe3d.gizmo = () => state.gizmo.handles(renderer.domElement.getBoundingClientRect());
    probe3d.project = (x: number, y: number, z: number): [number, number] => {
      const p = new THREE.Vector3(x, y, z * useStudio.getState().zScale).project(camera);
      const r = renderer.domElement.getBoundingClientRect();
      return [r.left + ((p.x + 1) / 2) * r.width, r.top + ((1 - p.y) / 2) * r.height];
    };
    probe3d.arrow = (): [number, number] | null => {
      if (!arrow.visible) return null;
      const p = new THREE.Vector3(0, 0, 6).applyMatrix4(arrow.matrixWorld).project(camera);
      const r = renderer.domElement.getBoundingClientRect();
      return [r.left + ((p.x + 1) / 2) * r.width, r.top + ((1 - p.y) / 2) * r.height];
    };

    function draw() { (state as any).redraw?.(); }

    return () => {
      cancelAnimationFrame(state.raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onArrowDown, true);
      renderer.domElement.removeEventListener("pointermove", onArrowMove);
      renderer.domElement.removeEventListener("pointerup", onArrowUp);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      state.gizmo.dispose();
      controls.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
      three.current = null;
    };
  }, []);

  // everything drawn: rebuilt when the scene, the file, the selection or a toggle changes
  useEffect(() => {
    const st = three.current;
    if (!st) return;
    const redraw = () => {
      const d = liveDoc.current ?? doc;
      // the theme's canvas (light by default)
      st.renderer.setClearColor(new THREE.Color(token("--canvas-3d", "#e4e7ec")));
      const dark = theme === "dark";
      const ink = dark ? "#e8edf3" : "#1c222b";
      for (const c of [...st.root.children]) { st.root.remove(c); dispose(c); }
      for (const c of [...st.overlay.children]) { st.overlay.remove(c); dispose(c); }
      st.sketchGroups.clear();
      st.root.scale.set(1, 1, zScale);
      st.root.updateMatrixWorld(true);
      const infos = shapesOf(d).filter((x) => x.hk === null);
      // one group per sketch: the gizmo moves it as a whole while it drags
      const groupOf = (si: number) => {
        let g = st.sketchGroups.get(String(si));
        if (!g) {
          g = new THREE.Group();
          g.matrixAutoUpdate = false;
          g.userData.sketch = si;
          st.sketchGroups.set(String(si), g);
          st.root.add(g);
        }
        return g;
      };
      // the skins: how deep each tagged face is drawn from the tag's own body
      const skins = new Map<string, Map<string, number>>();
      for (const t of tags) {
        if (t.hidden || !t.plan?.ok || !t.source?.body || !t.source.face) continue;
        const m = skins.get(t.source.body) ?? new Map<string, number>();
        const face = t.source.face;
        const name = face.startsWith("side") && infos.find((x) => x.body?.id === t.source!.body && kindOf(x.shape) === "rect")
          ? RECT_SIDES[Number(face.slice(4))] ?? face : face;
        m.set(name, Math.max(m.get(name) ?? 0, skinDepth(t)));
        skins.set(t.source.body, m);
      }
      for (const s of infos) {
        const g = s.body ? bodyObject(s, s.body.height, skins.get(s.body.id) ?? new Map(), shapeSel.includes(s.key), tool === "aruco" ? picks : [])
          : flatObject(s, shapeSel.includes(s.key));
        if (g) groupOf(s.si).add(g);
      }
      const sketchIdx = new Map<string, number>();
      infos.forEach((s) => { if (s.sketch?.id) sketchIdx.set(String(s.sketch.id), s.si); });
      const drawn: Record<string, string> = {};
      for (const t of tags) {
        if (t.hidden) continue;
        const si = t.source?.sketch ? sketchIdx.get(t.source.sketch) : undefined;
        let clip: THREE.Plane | null = null;
        if (t.source?.body && t.source.face) {                   // a tag on a body's face: its skin
          const P = new THREE.Matrix4().makeScale(1, 1, zScale).multiply(rowMajor(t.pose_3d ?? t.pose));
          clip = new THREE.Plane(new THREE.Vector3(0, 0, 1), skinDepth(t)).applyMatrix4(P);
        }
        const g = tagObject(t, sel.includes(t.name), clip);
        if (g) (si !== undefined ? groupOf(si) : st.root).add(g);
        if (g) drawn[t.name] = g.userData.drawn;
        if (show.axes) {
          const a = axesObject(t, zScale);
          if (a) st.overlay.add(a);
        }
        const b = tagBox(t);
        if (show.ids && b && t.plan) {
          const W = new THREE.Matrix4().makeScale(1, 1, zScale).multiply(rowMajor(t.pose_3d ?? t.pose));
          const zr = planZ(t.plan) ?? [0, 0];
          const hh = Math.max(2.5, Math.min(8, Math.max(t.spec.target.w_mm, t.spec.target.h_mm) * 0.09));
          const sp = textSprite(`${t.name} ${t.plan.ok ? "#" + idsText(t.plan.ids) : "not built"}`, hh);
          const c = new THREE.Vector3(0, t.spec.target.h_mm / 2 + hh * 0.8, Math.max(0, zr[1]) + 1).applyMatrix4(W);
          sp.position.copy(c);
          sp.userData.labelOf = t.name;
          st.overlay.add(sp);
        }
      }
      // the gizmo on the selected shape's sketch, the arrow on its body
      const one = shapeSel.length === 1 ? infos.find((x) => x.key === shapeSel[0]) : sel.length === 1 ? (() => {
        const t = tags.find((x) => x.name === sel[0]);
        return t?.source?.shape ? infos.find((x) => x.key === t.source!.shape) : undefined;
      })() : undefined;
      if (one && tool === "select") {
        const [x, y, r] = xfOf(one.sketch);
        st.gizmoSketch = { si: one.si, at: [x, y], rot: r, id: one.sketch?.id ?? null };
        st.gizmo.attach([x, y], r);
      } else if (!st.gizmo.dragging) {
        st.gizmoSketch = null;
        st.gizmo.detach();
      }
      if (one?.body && shapeSel.includes(one.key) && tool === "select") {
        const pts = outline(one.shape);
        const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
        const c = applyXf(one.xf, [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2]);
        const hgt = one.body.height;
        const len = Math.max(6, Math.min(30, Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) * 0.35));
        for (const c2 of [...st.arrow.children]) { st.arrow.remove(c2); dispose(c2); }
        const fresh = extrudeArrow(len);
        for (const c2 of [...fresh.children]) st.arrow.add(c2);
        st.arrow.position.set(c[0], c[1], hgt * zScale);
        st.arrow.rotation.set(hgt < 0 ? Math.PI : 0, 0, 0);
        st.arrow.visible = true;
        st.arrow.userData.body = one.body.id;
        st.arrow.updateMatrixWorld(true);
      } else if (!st.arrowDrag) st.arrow.visible = false;

      // the ground grid sized to the scene (10 mm cells), and a 10 mm bar
      for (const c of [...st.ground.children]) { st.ground.remove(c); dispose(c); }
      const boxes = tags.filter((t) => !t.hidden).map((t) => tagBox(t));
      for (const s of infos) {
        const pts = outline(s.shape).map((p) => applyXf(s.xf, p));
        if (pts.length) boxes.push({ x0: Math.min(...pts.map((p) => p[0])), y0: Math.min(...pts.map((p) => p[1])), x1: Math.max(...pts.map((p) => p[0])), y1: Math.max(...pts.map((p) => p[1])) });
      }
      const box = unionBox(boxes) ?? { x0: -50, y0: -50, x1: 50, y1: 50 };
      const step = 10;
      const size = Math.max(100, Math.ceil((Math.max(box.x1 - box.x0, box.y1 - box.y0) + 80) / (2 * step)) * 2 * step);
      const gx = Math.round((box.x0 + box.x1) / 2 / step) * step, gy = Math.round((box.y0 + box.y1) / 2 / step) * step;
      const zMin = Math.min(0, ...infos.filter((s) => s.body).map((s) => Math.min(0, s.body!.height)));
      const grid = new THREE.GridHelper(size, size / step, dark ? 0x55606e : 0x9aa3ae, dark ? 0x3a4250 : 0xc4cad2);
      grid.rotation.x = Math.PI / 2;
      grid.position.set(gx, gy, zMin * zScale - 0.01);
      (grid.material as THREE.Material).transparent = true;
      (grid.material as THREE.Material).opacity = 0.5;
      st.ground.add(grid);
      const bx = Math.floor(box.x0 / step) * step, by = Math.floor((box.y0 - 12) / step) * step;
      const bar = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(bx, by, 0.05), new THREE.Vector3(bx + step, by, 0.05)]),
        new THREE.LineBasicMaterial({ color: new THREE.Color(ink) }));
      bar.userData.scaleBarMm = step;
      st.ground.add(bar);
      const cue = textSprite(`${step} mm · grid ${step} mm`, 3.2, ink, dark ? "rgba(20,23,28,0.6)" : "rgba(255,255,255,0.75)");
      cue.position.set(bx + step / 2 + 9, by + 3, 0.1);
      cue.userData.sizeCue = true;
      st.ground.add(cue);

      // what the e2e tests read (never a picture)
      const arrows: number[] = [];
      st.scene.updateMatrixWorld(true);
      st.overlay.traverse((o) => { if (o instanceof THREE.ArrowHelper) arrows.push(new THREE.Vector3().setFromMatrixScale(o.matrixWorld).z); });
      const normals: Record<string, number[]> = {};
      st.root.traverse((o) => {
        if (o.userData.tag && o instanceof THREE.Group) {
          const n = new THREE.Vector3(0, 0, 1).transformDirection(o.matrixWorld);
          normals[o.userData.tag] = [n.x, n.y, n.z].map((v) => Math.round(v * 1e6) / 1e6 + 0);
        }
      });
      const probe3d = (window as any).__studio3d;
      Object.assign(probe3d, {
        labels: st.overlay.children.filter((o) => o.userData.labelOf).map((o) => o.userData.text as string),
        axes: st.overlay.children.filter((o) => o.userData.axesOf).length,
        arrowWorldScaleZ: arrows,
        rootScaleZ: st.root.scale.z,
        gridMm: size, stepMm: step, box,
        scaleBarMm: step,
        normals,
        drawn,                                       // tag -> "mesh" | "light" (a drag's preview)
        bodies: infos.filter((s) => s.body).map((s) => ({ shape: s.key, body: s.body!.id, height: s.body!.height })),
        gizmoOn: st.gizmo.attached ? st.gizmoSketch?.id ?? null : null,
        arrowOn: st.arrow.visible ? st.arrow.userData.body : null,
      });
    };
    (st as any).redraw = redraw;
    redraw();
  }, [allTags, filter, theme, doc, sel, shapeSel, show.axes, show.ids, zScale, tool, picks]);

  return <div ref={host} className="canvas3d" data-view="3d" data-tool={tool} onContextMenu={(e) => e.preventDefault()} />;
}
