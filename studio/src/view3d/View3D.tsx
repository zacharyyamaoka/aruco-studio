// The 3D view: every tag's solids from /api/plan?mesh=1 (the app never
// triangulates), placed by its pose and its plan's pattern frame; z up out
// of the faces. Orbit to look around (left drag), pan (right drag), zoom
// (wheel); click a tag to select it. The toggle keeps the view's centre and
// scale, like Google Maps' 2D / 3D.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { SceneTag } from "../api/types";
import { planZ, tagBox, unionBox } from "../model/geom";
import { idsText } from "../model/scene";
import { patternToScene, useStudio } from "../store";

const FOV = 35;
const TILT = (50 * Math.PI) / 180;
const COLOURS: Record<string, number> = { body: 0xb9c0ca, white: 0xf3f3f0, black: 0x17191d };
const SEL = 0x38a6e8;

function rowMajor(m: number[]): THREE.Matrix4 {
  const M = new THREE.Matrix4();
  M.set(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12], m[13], m[14], m[15]);
  return M;
}

/** A text sprite (canvas texture), `h` mm tall in the scene: a tag's name
 *  and ids, or a size cue (audit F17; Google Maps keeps its labels in 3D). */
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

/** The OpenCV frame's axes of a tag, OUTSIDE the z-exaggerated root: a
 *  height exaggeration moves the origin up with the tag's top but never
 *  stretches the arrows (audit F17). */
function axesObject(t: SceneTag, zScale: number): THREE.Group | null {
  const p = t.plan;
  const M = patternToScene(t);
  if (!p || !p.ok || !M || !p.frames) return null;
  const F = p.frames.opencv;
  const W = rowMajor(M);
  const len = Math.max(2, Number((p.marker as any)?.marker_length_m || 0.01) * 1000 * 0.42);
  const o = new THREE.Vector3(F[3], F[7], F[11] + 0.05).applyMatrix4(W);
  o.z *= zScale;
  const R3 = new THREE.Matrix3().setFromMatrix4(W);
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

function tagObject(t: SceneTag, selected: boolean, axes: boolean): THREE.Group | null {
  const p = t.plan;
  const M = patternToScene(t);
  if (!p || !p.ok || !M || !p.mesh) return null;
  const g = new THREE.Group();
  g.name = t.name;
  g.userData.tag = t.name;
  g.matrixAutoUpdate = false;
  g.matrix.copy(rowMajor(M));
  for (const b of p.mesh) {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(b.positions, 3));
    geo.setIndex(b.indices);
    const flat = geo.toNonIndexed();
    flat.computeVertexNormals();
    geo.dispose();
    const mat = new THREE.MeshStandardMaterial({
      color: COLOURS[b.colour] ?? 0x999999, roughness: b.colour === "black" ? 0.55 : 0.8, metalness: 0,
      flatShading: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
    });
    const mesh = new THREE.Mesh(flat, mat);
    mesh.userData.tag = t.name;
    mesh.userData.what = b.what;
    g.add(mesh);
    const edges = new THREE.LineSegments(new THREE.EdgesGeometry(flat, 25),
      new THREE.LineBasicMaterial({ color: b.colour === "black" ? 0x5a6170 : 0x6d7682, transparent: true, opacity: 0.55 }));
    edges.userData.tag = t.name;
    g.add(edges);
  }
  void axes;                                         // the axes: axesObject, outside the z scale
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

export function View3D() {
  const host = useRef<HTMLDivElement>(null);
  const three = useRef<{
    renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera;
    controls: OrbitControls; root: THREE.Group; overlay: THREE.Group; ground: THREE.Group; moved: boolean; raf: number;
  } | null>(null);
  const tags = useStudio((s) => s.scene.tags);
  const sel = useStudio((s) => s.sel);
  const show = useStudio((s) => s.show);
  const zScale = useStudio((s) => s.zScale);

  // set up once: renderer, camera from the 2D view's centre and scale
  useEffect(() => {
    const el = host.current!;
    const st = useStudio.getState();
    const { w, h } = st.viewport;
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(w, h);
    renderer.setClearColor(0x2b313c);
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
    const ground = new THREE.Group();                 // the grid and its size cue, sized to the scene
    scene.add(ground);
    const root = new THREE.Group();
    scene.add(root);
    const overlay = new THREE.Group();                // axes and labels: never z-scaled
    scene.add(overlay);
    const state = { renderer, scene, camera, controls, root, overlay, ground, moved: false, raf: 0 };
    three.current = state;
    controls.addEventListener("start", () => { state.moved = true; });
    controls.addEventListener("end", () => {
      // the 2D view follows where the 3D view now looks
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
    // click to select (a drag orbits)
    let down: [number, number] | null = null;
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4 || e.button !== 0) { down = null; return; }
      down = null;
      const r = renderer.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      const ray = new THREE.Raycaster();
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(root.children, true).find((i) => i.object instanceof THREE.Mesh);
      useStudio.getState().select(hit ? (hit.object.userData.tag as string) : null, e.shiftKey || e.ctrlKey);
    };
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);
    return () => {
      cancelAnimationFrame(state.raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      controls.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
      three.current = null;
    };
  }, []);

  // the tags: rebuilt when the scene, the selection or a toggle changes
  useEffect(() => {
    const st = three.current;
    if (!st) return;
    for (const c of [...st.root.children]) {
      st.root.remove(c);
      c.traverse((o) => {
        if ((o as THREE.Mesh).geometry) (o as THREE.Mesh).geometry.dispose();
        const m = (o as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(m)) m.forEach((x) => x.dispose()); else m?.dispose();
      });
    }
    for (const c of [...st.overlay.children]) {
      st.overlay.remove(c);
      c.traverse((o) => {
        const m = (o as THREE.Sprite).material as THREE.SpriteMaterial | undefined;
        if (m && (m as any).map) (m as any).map.dispose();
        if ((o as THREE.Mesh).geometry) (o as THREE.Mesh).geometry.dispose();
        m?.dispose();
      });
    }
    st.root.scale.set(1, 1, zScale);
    for (const t of tags) {
      if (t.hidden) continue;
      const g = tagObject(t, sel.includes(t.name), show.axes);
      if (g) st.root.add(g);
      if (show.axes) {
        const a = axesObject(t, zScale);
        if (a) st.overlay.add(a);
      }
      // the tag's name and ids above it, as in the 2D view
      const b = tagBox(t);
      if (show.ids && b && t.plan) {
        const zr = planZ(t.plan) ?? [0, 0];
        const h = Math.max(2.5, Math.min(8, Math.max(b.x1 - b.x0, b.y1 - b.y0) * 0.09));
        const sp = textSprite(`${t.name} ${t.plan.ok ? "#" + idsText(t.plan.ids) : "not built"}`, h);
        sp.position.set((b.x0 + b.x1) / 2, b.y1 + h * 0.8, Math.max(0, zr[1]) * zScale + 1);
        sp.userData.labelOf = t.name;
        st.overlay.add(sp);
      }
    }
    // the ground grid sized to the scene (10 mm cells), and a 10 mm bar with its words
    for (const c of [...st.ground.children]) {
      st.ground.remove(c);
      c.traverse((o) => {
        if ((o as THREE.Mesh).geometry) (o as THREE.Mesh).geometry.dispose();
        const m = (o as any).material;
        if (m) { if (m.map) m.map.dispose(); m.dispose(); }
      });
    }
    const box = unionBox(tags.filter((t) => !t.hidden).map((t) => tagBox(t))) ?? { x0: -50, y0: -50, x1: 50, y1: 50 };
    const step = 10;
    const size = Math.max(100, Math.ceil((Math.max(box.x1 - box.x0, box.y1 - box.y0) + 80) / (2 * step)) * 2 * step);
    const cx = Math.round((box.x0 + box.x1) / 2 / step) * step, cy = Math.round((box.y0 + box.y1) / 2 / step) * step;
    const grid = new THREE.GridHelper(size, size / step, 0x55606e, 0x3a4250);
    grid.rotation.x = Math.PI / 2;
    grid.position.set(cx, cy, -0.01);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.5;
    grid.userData.gridMm = size;
    grid.userData.stepMm = step;
    st.ground.add(grid);
    const bx = Math.floor(box.x0 / step) * step, by = Math.floor((box.y0 - 12) / step) * step;   // just in front of the tags
    const bar = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(bx, by, 0.05), new THREE.Vector3(bx + step, by, 0.05)]),
      new THREE.LineBasicMaterial({ color: 0xe8edf3 }));
    bar.userData.scaleBarMm = step;
    st.ground.add(bar);
    const cue = textSprite(`${step} mm · grid ${step} mm`, 3.2, "#e8edf3", "rgba(20,23,28,0.6)");
    cue.position.set(bx + step / 2 + 9, by + 3, 0.1);
    cue.userData.sizeCue = true;
    st.ground.add(cue);
    // what the e2e tests read (never a picture): the labels, the axes' scale
    // in world z, the grid's size and the bar
    const arrows: number[] = [];
    st.scene.updateMatrixWorld(true);
    st.overlay.traverse((o) => { if (o instanceof THREE.ArrowHelper) arrows.push(new THREE.Vector3().setFromMatrixScale(o.matrixWorld).z); });
    (window as any).__studio3d = {
      labels: st.overlay.children.filter((o) => o.userData.labelOf).map((o) => o.userData.text as string),
      axes: st.overlay.children.filter((o) => o.userData.axesOf).length,
      arrowWorldScaleZ: arrows,
      rootScaleZ: st.root.scale.z,
      gridMm: size, stepMm: step, box,
      scaleBarMm: step,
    };
  }, [tags, sel, show.axes, show.ids, zScale]);

  return <div ref={host} className="canvas3d" data-view="3d" onContextMenu={(e) => e.preventDefault()} />;
}
