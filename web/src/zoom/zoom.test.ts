// The zoom commands: an exact zoom about a point, the selection's box, and
// Actual size following a scale that changes under it.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../coreSource", () => ({
  core: new Proxy({}, { get: () => () => new Promise(() => {}) }),
  coreStatus: () => ({ state: "ready" }),
}));

const { useStudio } = await import("../store");
const { emptyDoc, newFeature, rectProfile, addFeature } = await import("../model/doc");
const { rectShape } = await import("../sketch/model");
const { toScreen } = await import("../model/geom");
const { actualSize, followScale, selectionBox, setZoom, zoom100, zoomTo, zoomToSelection } = await import("./zoom");
const { CSS_PX_PER_MM, useScale } = await import("./scale");

const st = () => useStudio.getState();
const plan = (outer: [number, number][]) => ({ outer, black: [], ids: [7], marker_mm: 30, outer_mm: [30, 30], overflow_mm: 0, origin: [] }) as never;

beforeEach(() => {
  // corners: the plate 200 x 100 about the origin, a and b 40 x 40 either side
  st().loadDoc(emptyDoc("Z", [rectShape("p", -100, -50, 100, 50), rectShape("a", -80, -20, -40, 20), rectShape("b", 40, -20, 80, 20)]));
  st().setView(1000, 600);
  st().setCamera({ cx: 0, cy: 0, zoom: 2 });
});

describe("zoomTo", () => {
  it("sets the zoom exactly and keeps the world point under the view point", () => {
    const cam = { cx: 10, cy: -5, zoom: 2 };
    const s: [number, number] = [700, 150];
    const before = (p: [number, number]) => toScreen(cam, 1000, 600, p);
    // the world point under s before, under s after
    const w0: [number, number] = [10 + (700 - 500) / 2, -5 - (150 - 300) / 2];
    expect(before(w0)).toEqual(s);
    const z = zoomTo(cam, 1000, 600, s, 5.123);
    expect(z.zoom).toBe(5.123);
    const back = toScreen(z, 1000, 600, w0);
    expect(back[0]).toBeCloseTo(s[0], 9);
    expect(back[1]).toBeCloseTo(s[1], 9);
  });

  it("Zoom 100 % and Actual size set the zoom to the scale, about the view's centre by default", () => {
    zoom100();
    expect(st().camera).toEqual({ cx: 0, cy: 0, zoom: CSS_PX_PER_MM });
    useScale.setState({ scale: { ...useScale.getState().scale, pxPerMm: 5.25 } });
    actualSize([500, 300]);
    expect(st().camera.zoom).toBe(5.25);
    setZoom(3, [0, 0]);
    expect(st().camera.zoom).toBe(3);
  });
});

describe("the selection's box", () => {
  it("nothing selected: none, and Zoom to selection does nothing", () => {
    expect(selectionBox(st().doc, {}, null, [])).toBeNull();
    const cam = st().camera;
    expect(zoomToSelection()).toBe(false);
    expect(st().camera).toBe(cam);
  });

  it("shapes: their outlines (several: the box of all); a profile: its outer shape", () => {
    expect(selectionBox(st().doc, {}, { kind: "shape", id: "a" }, ["a"])).toEqual({ x0: -80, y0: -20, x1: -40, y1: 20 });
    expect(selectionBox(st().doc, {}, { kind: "shape", id: "a" }, ["a", "b"])).toEqual({ x0: -80, y0: -20, x1: 80, y1: 20 });
    expect(selectionBox(st().doc, {}, { kind: "profile", ref: { outer: "p", holes: ["a"] } }, [])).toEqual({ x0: -100, y0: -50, x1: 100, y1: 50 });
  });

  it("a marker: its plan, not the face it stands on; shapes take in the markers on them", () => {
    const f = { ...newFeature(rectProfile("p")), id: "f1", key: "f1" };
    const doc = addFeature(st().doc, f);
    const plans = { f1: plan([[10, 10], [40, 10], [40, 40], [10, 40]]) };
    expect(selectionBox(doc, plans, { kind: "feature", id: "f1" }, [])).toEqual({ x0: 10, y0: 10, x1: 40, y1: 40 });
    const wide = { f1: plan([[150, 10], [180, 10], [180, 40], [150, 40]]) };
    expect(selectionBox(doc, wide, { kind: "shape", id: "p" }, ["p"])).toEqual({ x0: -100, y0: -50, x1: 180, y1: 50 });
  });

  it("Zoom to selection frames it with the fit's margin", () => {
    st().selectShapes(["b"]);
    expect(zoomToSelection()).toBe(true);
    const c = st().camera;
    expect(c.cx).toBeCloseTo(60, 9);
    expect(c.cy).toBeCloseTo(0, 9);
    expect(c.zoom).toBeCloseTo(Math.min((1000 - 168) / 40, (600 - 168) / 40), 9);
  });
});

describe("Actual size follows its scale", () => {
  it("at the old scale, the camera moves to the new one; anywhere else it stays; in 3D it waits for 2D", () => {
    const off = followScale();
    const scale = (pxPerMm: number) => useScale.setState({ scale: { ...useScale.getState().scale, pxPerMm } });
    scale(4);
    actualSize();
    scale(5);
    expect(st().camera.zoom).toBe(5);
    // not at the scale: a new scale leaves it
    setZoom(2.5);
    scale(6);
    expect(st().camera.zoom).toBe(2.5);
    // at it, in 3D: the 2D camera follows on the way back
    actualSize();
    st().setView3d(true);
    scale(7);
    expect(st().camera.zoom).toBe(6);
    st().setView3d(false);
    expect(st().camera.zoom).toBe(7);
    off();
    scale(8);
    expect(st().camera.zoom).toBe(7);
  });
});
