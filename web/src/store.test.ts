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
const { idRequest } = await import("./model/doc");

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
