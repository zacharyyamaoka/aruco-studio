// The extrude arrow (ported from the old Studio's studio/src/view3d/Gizmo.ts):
// a cone on a stem standing on a face, along z, dragged along its normal
// (Fusion's Extrude arrow). Here it is one unit long and the view scales it
// to a fixed size on screen each frame, as Fusion's manipulators are; and
// the dimension line beside the solid: a thin line with an extension line at each end.
import * as THREE from "three";

/** An arrow one unit long along +z from its base; `colour` lit, drawn over the solids. */
export function extrudeArrow(colour: THREE.ColorRepresentation): THREE.Group {
  const g = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({ color: colour, depthTest: false, transparent: true, opacity: 0.95 });
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.7, 10), mat);
  stem.rotation.x = Math.PI / 2;
  stem.position.z = 0.35;
  const head = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.3, 16), mat);
  head.rotation.x = Math.PI / 2;
  head.position.z = 0.85;
  // a fatter invisible picker along the whole arrow
  const pick = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 1, 8), new THREE.MeshBasicMaterial({ visible: false }));
  pick.rotation.x = Math.PI / 2;
  pick.position.z = 0.5;
  for (const m of [stem, head, pick]) { m.userData.arrow = true; m.renderOrder = 20; g.add(m); }
  g.userData.arrow = true;
  return g;
}

/** A dimension line along z at (x, y), from z0 to z1, with an extension line
 *  at each end running from the solid's side (`edgeX`) to `tick` mm past it. */
export function dimLine(x: number, y: number, edgeX: number, z0: number, z1: number, tick: number, colour: THREE.ColorRepresentation): THREE.LineSegments {
  const past = x + Math.sign(x - edgeX) * tick;
  const pts = [
    [x, y, z0, x, y, z1],
    [edgeX, y, z0, past, y, z0],
    [edgeX, y, z1, past, y, z1],
  ].flat();
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  const l = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: colour, depthTest: false, transparent: true, opacity: 0.9 }));
  l.renderOrder = 18;
  return l;
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
