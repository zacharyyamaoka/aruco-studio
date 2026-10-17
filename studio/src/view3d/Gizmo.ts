// Dragging in 3D (M8 §2.4): three.js TransformControls on a sketch
// (translate in X and Y, 0.5 mm steps; a second one turns it about Z, 15°
// steps), OrbitControls paused while one drags, as the standard pattern
// does; and the extrude arrow: a handle on a body's end face, dragged along
// its normal in 0.5 mm steps (Fusion's Extrude arrow), that writes `height`.
import * as THREE from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { TransformControls } from "three/examples/jsm/controls/TransformControls.js";

export interface SketchDrag {
  /** the sketch's place now (mm, deg), while it is dragged */
  onChange(at: [number, number], rot: number): void;
  /** released: the place to write */
  onCommit(at: [number, number], rot: number): void;
}

const SNAP_MM = 0.5;
const SNAP_DEG = 15;

export class SketchGizmo {
  readonly proxy = new THREE.Object3D();
  readonly move: TransformControls;
  readonly turn: TransformControls;
  private start = { x: 0, y: 0, rot: 0 };
  dragging = false;

  constructor(private camera: THREE.Camera, dom: HTMLElement, scene: THREE.Scene, orbit: OrbitControls, private cb: SketchDrag) {
    scene.add(this.proxy);
    this.move = new TransformControls(camera, dom);
    this.move.setMode("translate");
    this.move.showZ = false;
    this.move.setTranslationSnap(SNAP_MM);
    this.move.setSpace("world");
    this.turn = new TransformControls(camera, dom);
    this.turn.setMode("rotate");
    this.turn.showX = false;
    this.turn.showY = false;
    this.turn.setRotationSnap((SNAP_DEG * Math.PI) / 180);
    this.turn.setSpace("world");
    this.turn.size = 1.6;
    for (const c of [this.move, this.turn]) {
      const helper = c.getHelper();
      helper.userData.gizmo = true;
      scene.add(helper);
      c.addEventListener("dragging-changed", (e: any) => {
        orbit.enabled = !e.value;
        this.dragging = !!e.value;
        if (e.value) this.start = this.place();
      });
      c.addEventListener("objectChange", () => {
        const p = this.place();
        this.cb.onChange([p.x, p.y], p.rot);
      });
      c.addEventListener("mouseUp", () => {
        const p = this.place();
        if (p.x !== this.start.x || p.y !== this.start.y || p.rot !== this.start.rot) this.cb.onCommit([p.x, p.y], p.rot);
      });
    }
    this.detach();
  }

  /** The proxy's place, on the snaps (mm, deg). */
  place() {
    const r = (v: number) => Math.round(v / SNAP_MM) * SNAP_MM + 0;
    const deg = Math.round(((this.proxy.rotation.z * 180) / Math.PI) / SNAP_DEG) * SNAP_DEG;
    let d = ((((deg + 180) % 360) + 360) % 360) - 180;
    if (d === -180) d = 180;
    return { x: Math.round(r(this.proxy.position.x) * 1e6) / 1e6, y: Math.round(r(this.proxy.position.y) * 1e6) / 1e6, rot: d + 0 };
  }

  attach(at: [number, number], rot: number) {
    if (this.dragging) return;
    this.proxy.position.set(at[0], at[1], 0);
    this.proxy.rotation.set(0, 0, (rot * Math.PI) / 180);
    this.proxy.updateMatrixWorld(true);
    this.move.attach(this.proxy);
    this.turn.attach(this.proxy);
  }

  detach() {
    if (this.dragging) return;
    this.move.detach();
    this.turn.detach();
  }

  get attached() { return !!this.move.object; }

  /** Screen points (px, in the canvas) a test can drag: the X and Y arrows,
   *  the Z ring. */
  handles(rect: DOMRect): { x: [number, number]; y: [number, number]; ring: [number, number]; centre: [number, number] } | null {
    if (!this.attached) return null;
    const cam = this.camera as THREE.PerspectiveCamera;
    const o = this.proxy.getWorldPosition(new THREE.Vector3());
    const factor = o.distanceTo(cam.position) * Math.min((1.9 * Math.tan((Math.PI * cam.fov) / 360)) / cam.zoom, 7);
    const sT = (factor * this.move.size) / 4, sR = (factor * this.turn.size) / 4;
    const scr = (v: THREE.Vector3): [number, number] => {
      const p = v.clone().project(cam);
      return [rect.left + ((p.x + 1) / 2) * rect.width, rect.top + ((1 - p.y) / 2) * rect.height];
    };
    // the ring: the point of it nearest the camera's side (towards -y on the screen)
    const ringPts = Array.from({ length: 24 }, (_v, i) => {
      const a = (i / 24) * Math.PI * 2;
      return o.clone().add(new THREE.Vector3(Math.cos(a) * 0.5 * sR, Math.sin(a) * 0.5 * sR, 0));
    });
    const ring = ringPts.map(scr).sort((a, b) => b[1] - a[1])[0];
    return {
      x: scr(o.clone().add(new THREE.Vector3(0.42 * sT, 0, 0))),
      y: scr(o.clone().add(new THREE.Vector3(0, 0.42 * sT, 0))),
      ring,
      centre: scr(o),
    };
  }

  dispose() {
    for (const c of [this.move, this.turn]) {
      c.detach();
      c.getHelper().removeFromParent();
      c.dispose();
    }
    this.proxy.removeFromParent();
  }
}

/** The extrude arrow: a cone on a stem, at a body's end face, along z. */
export function extrudeArrow(len: number): THREE.Group {
  const g = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({ color: 0x38a6e8, depthTest: false, transparent: true, opacity: 0.95 });
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(len * 0.035, len * 0.035, len * 0.7, 10), mat);
  stem.rotation.x = Math.PI / 2;
  stem.position.z = len * 0.35;
  const head = new THREE.Mesh(new THREE.ConeGeometry(len * 0.12, len * 0.3, 16), mat);
  head.rotation.x = Math.PI / 2;
  head.position.z = len * 0.85;
  // a fatter invisible picker along the whole arrow
  const pick = new THREE.Mesh(new THREE.CylinderGeometry(len * 0.16, len * 0.16, len, 8), new THREE.MeshBasicMaterial({ visible: false }));
  pick.rotation.x = Math.PI / 2;
  pick.position.z = len * 0.5;
  for (const m of [stem, head, pick]) { m.userData.arrow = true; m.renderOrder = 20; g.add(m); }
  g.userData.arrow = true;
  return g;
}

/** The z (world) on the vertical line through `base` nearest the ray. */
export function zOnAxis(ray: THREE.Ray, base: THREE.Vector3): number {
  // closest points of two lines: the ray (o + t d) and the axis (base + s z)
  const d = ray.direction, o = ray.origin;
  const w0 = o.clone().sub(base);
  const a = d.dot(d), b = d.z, c = 1, dd = d.dot(w0), e = w0.z;
  const den = a * c - b * b;
  if (Math.abs(den) < 1e-9) return base.z;
  const s = (a * e - b * dd) / den;
  return base.z + s;
}
