// The store's document transitions, on a fake core (no Pyodide in vitest).
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./coreSource", () => ({
  core: new Proxy({}, { get: () => () => new Promise(() => {}) }),
  coreStatus: () => ({ state: "ready" }),
}));

const { useStudio } = await import("./store");
const { emptyDoc, parseDoc } = await import("./model/doc");
const { rectShape } = await import("./sketch/model");
const { idsReady, settledDoc, settledOutput } = await import("./app/output");
const { addFeature, idRequest, newFeature, rectProfile } = await import("./model/doc");

const st = () => useStudio.getState();

beforeEach(() => {
  st().loadDoc(emptyDoc("Start", [rectShape("p", 0, 0, 120, 80)]));
});

describe("a failed open (review finding #4)", () => {
  // a poly without pts passed parseDoc, and loadDoc threw only in fit(),
  // after the document and its history had been replaced
  const BAD = JSON.stringify({ format: "arucostudio-web", version: 4, name: "Bad", shapes: [{ kind: "poly", id: "bad" }], features: [] });

  it("parseDoc refuses malformed geometry, naming the shape", () => {
    expect(() => parseDoc(BAD)).toThrow(/shape 1 \("bad"\): a poly needs pts/);
  });

  it("loadDoc of an unchecked bad document leaves the store as it was: document, history, panel", () => {
    st().addShape(rectShape("r1", 10, 10, 40, 30));
    const before = st();
    expect(before.canUndo).toBe(true);
    const raw = { ...emptyDoc("Bad"), shapes: [{ kind: "poly", id: "bad" }] } as never;
    expect(() => st().loadDoc(raw)).toThrow(/shape 1 \("bad"\)/);
    expect(st().doc).toBe(before.doc);
    expect(st().canUndo).toBe(true);
    st().undo();
    expect(st().doc.shapes.map((s) => s.id)).toEqual(["p"]);
  });

  it("refuses duplicate ids, duplicate keys and a profile naming a missing shape, each by name", () => {
    const r = (id: string) => ({ kind: "rect", id, cx: 0, cy: 0, w: 10, h: 10, angle_deg: 0 });
    const f = (id: string, key: string, outer: string) => ({ id, key, profile: { outer, holes: [] } });
    const doc = (shapes: unknown[], features: unknown[]) => JSON.stringify({ format: "arucostudio-web", version: 4, shapes, features });
    expect(() => parseDoc(doc([r("a"), r("a")], []))).toThrow(/shape 2 \("a"\): the id "a" is used twice/);
    expect(() => parseDoc(doc([r("a"), r("b")], [f("f1", "k", "a"), f("f1", "k2", "b")]))).toThrow(/feature 2 \("f1"\): the id "f1" is used twice/);
    expect(() => parseDoc(doc([r("a"), r("b")], [f("f1", "k", "a"), f("f2", "k", "b")]))).toThrow(/feature 2 \("f2"\): the key "k" is used twice/);
    expect(() => parseDoc(doc([r("a")], [f("f1", "k", "zz")]))).toThrow(/feature 1 \("f1"\): its profile names shape "zz"/);
    expect(() => parseDoc(doc([{ ...r("a"), w: "wide" }], []))).toThrow(/shape 1 \("a"\): a rect needs a number w/);
    expect(() => parseDoc(doc([{ kind: "circle", id: "c", cx: 0, cy: 0, r: -1 }], []))).toThrow(/circle's r/);
    expect(() => parseDoc(doc([r("a")], [{ ...f("f1", "k", "a"), marker: { first_id: "7" } }]))).toThrow(/marker.first_id/);
  });
});

describe("output from a settled revision (review finding #6)", () => {
  const settle = () => useStudio.setState({ idSettledKey: JSON.stringify(idRequest(st().doc)) });

  it("waits for the ids of the document as it is now, through edits meanwhile", async () => {
    useStudio.setState({ idSettledKey: "" });
    let got: unknown = null;
    void settledDoc().then((d) => { got = d; });
    await Promise.resolve();
    expect(got).toBeNull();
    st().addShape(rectShape("r1", 0, 0, 10, 10));       // an edit while waiting
    await Promise.resolve();
    expect(got).toBeNull();
    settle();
    await Promise.resolve();
    expect(got).toBe(st().doc);
    expect(idsReady(st())).toBe(true);
  });

  it("starts again when the document's request moved on while the core worked", async () => {
    settle();
    const built: string[] = [];
    const out = await settledOutput((doc) => doc.name, async (name) => {
      built.push(name);
      if (built.length === 1) { st().setName("Moved"); settle(); }
      return name.toUpperCase();
    });
    expect(built).toEqual(["Start", "Moved"]);
    expect(out!.out).toBe("MOVED");
  });
});

describe("Cancel takes back the panel's own steps, nothing else (review finding #7)", () => {
  // a document with one marker (its rectangle a profile) and a fresh history
  const withMarker = () => {
    const d = emptyDoc("Start", [rectShape("p", 0, 0, 120, 80), rectShape("m", 10, 10, 40, 40)]);
    st().loadDoc(addFeature(d, newFeature(rectProfile("m"), "f1")));
  };
  const ids = () => st().doc.shapes.map((s) => s.id);

  it("add a rectangle, open the marker, undo the rectangle, Cancel: the rectangle stays gone and redo still has it", () => {
    withMarker();
    st().addShape(rectShape("r1", 50, 10, 70, 30));
    st().editFeature("f1");
    expect(st().panel.open).toBe(true);
    st().undo();
    expect(ids()).toEqual(["p", "m"]);
    st().cancel();
    expect(st().panel.open).toBe(false);
    expect(ids()).toEqual(["p", "m"]);
    expect(st().canRedo).toBe(true);
    st().redo();
    expect(ids()).toEqual(["p", "m", "r1"]);
  });

  it("an edit in the panel, then Cancel: the edit is taken back as one, the history as before the panel", () => {
    withMarker();
    st().addShape(rectShape("r1", 50, 10, 70, 30));
    st().editFeature("f1");
    st().setField("marker.first_id", 9);
    st().setField("label.on", true);
    st().cancel();
    expect(st().doc.features[0].marker.first_id).toBe(0);
    expect(st().doc.features[0].label.on).toBe(false);
    expect(ids()).toEqual(["p", "m", "r1"]);
    st().undo();
    expect(ids()).toEqual(["p", "m"]);
  });

  it("a rename while the panel is open survives Cancel", () => {
    withMarker();
    st().editFeature("f1");
    st().setField("marker.first_id", 9);
    st().setName("Renamed");
    st().cancel();
    expect(st().doc.name).toBe("Renamed");
    expect(st().doc.features[0].marker.first_id).toBe(0);
  });

  it("undo inside the panel's own steps, then Cancel: back to the document the panel opened on", () => {
    withMarker();
    st().editFeature("f1");
    st().setField("marker.first_id", 9);
    st().setField("label.on", true);
    st().undo();
    st().cancel();
    expect(st().doc.features[0].marker.first_id).toBe(0);
    expect(st().doc.features[0].label.on).toBe(false);
    expect(st().canUndo).toBe(false);
  });

  it("a new marker (A on a rectangle), Cancel: it is gone, and so is its step", () => {
    withMarker();
    st().addShape(rectShape("r1", 50, 10, 70, 30));
    st().select({ kind: "shape", id: "r1" });
    void st().extrude();
    expect(st().doc.features).toHaveLength(2);
    st().cancel();
    expect(st().doc.features).toHaveLength(1);
    st().undo();
    expect(ids()).toEqual(["p", "m"]);
  });
});
