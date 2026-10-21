// Home's pictures of cloud files (./thumbs.ts): kept by the bytes' sha256,
// each marker by its request. On a fake core that is up: the planner's
// answers are what notePlan gets.
import { describe, expect, it, vi } from "vitest";
import v3Fixture from "../../e2e/fixtures/v3-a4.arucostudio-web.json?raw";
import type { MarkerPlan, PlanRequest } from "../core/contract";

vi.mock("../coreSource", () => ({
  core: { plan: () => Promise.reject(new Error("fake core: not asked here")) },
  coreStatus: () => ({ state: "ready" }),
  onCoreStatus: () => () => {},
}));

const { keepSaved, keptPicture, notePlan, requestKey, thumbKey } = await import("./thumbs");
const { parseDoc, planRequest, serialise } = await import("../model/doc");

const sha256 = async (text: string) =>
  Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))), (b) => b.toString(16).padStart(2, "0")).join("");

/** A plan as the core answers one, its geometry placed `at` (only the outline and the black are drawn). */
const planAt = (at: number): MarkerPlan => ({
  ok: true, ids: [at], outer: [[at, 0], [at + 10, 0], [at + 10, 10], [at, 10]], black: [{ outer: [[at + 2, 2], [at + 8, 2], [at + 8, 8], [at + 2, 8]], holes: [] }],
}) as unknown as MarkerPlan;

/** The same object with every key in the reverse order, all the way down. */
function reordered(v: unknown): unknown {
  if (Array.isArray(v)) return v.map(reordered);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).reverse().map(([k, x]) => [k, reordered(x)]));
  return v;
}

const requests = (text: string): PlanRequest[] => {
  const doc = parseDoc(text);
  return doc.features.map((f) => planRequest(doc, f)!);
};

describe("a marker is kept by its request", () => {
  it("one request, one key, however its objects were built; any change, another key", () => {
    const [a, b] = requests(v3Fixture);
    expect(requestKey(reordered(a) as PlanRequest)).toBe(requestKey(a));
    expect(requestKey(a)).not.toBe(requestKey(b));
    expect(requestKey({ ...a, marker: { ...a.marker, first_id: a.marker.first_id + 1 } })).not.toBe(requestKey(a));
    expect(requestKey({ ...a, profile: { loops: [[[0, 0], [1, 0], [1, 1.0001]]] } })).not.toBe(requestKey({ ...a, profile: { loops: [[[0, 0], [1, 0], [1, 1]]] } }));
  });

  it("a file read back asks what the editor asked: its saved bytes give the same keys", () => {
    const doc = parseDoc(v3Fixture);
    const again = parseDoc(serialise(doc));
    expect(again.features.map((f) => requestKey(planRequest(again, f)!))).toEqual(doc.features.map((f) => requestKey(planRequest(doc, f)!)));
  });
});

describe("a file's key is its bytes'", () => {
  it("the sha256 the server answered; a server without one: the file's version", () => {
    const hex = "ab".repeat(32);
    expect(thumbKey({ id: "f1", version: 3, sha256: hex })).toBe(hex);
    expect(thumbKey({ id: "f2", version: 1, sha256: hex })).toBe(hex);   // a copy: the same bytes, the same picture
    expect(thumbKey({ id: "f1", version: 3, sha256: "x" })).toBe("f1@3");
  });
});

describe("a save keeps the picture of what it wrote", () => {
  it("the editor's document, once the planner has answered its markers: its shapes and every marker, by the bytes' sha256", async () => {
    const doc = { ...parseDoc(v3Fixture), name: "Saved here" };
    const text = serialise(doc);
    const sha = await sha256(text);
    keepSaved({ sha256: sha }, text, doc);
    await new Promise((r) => setTimeout(r, 20));
    expect(keptPicture(sha), "a marker not answered yet: no picture").toBeUndefined();
    const reqs = doc.features.map((f) => planRequest(doc, f)!);
    notePlan(reqs[0], planAt(0));
    expect(keptPicture(sha)).toBeUndefined();
    notePlan(reqs[1], planAt(50));
    const pic = keptPicture(sha)!;
    expect(pic.shapes).toEqual(doc.shapes);
    expect(pic.marks.map((m) => m.outer[0])).toEqual([[0, 0], [50, 0]]);
  });

  it("bytes the server holds that are not the editor's document now (it moved on): nothing kept, of either", async () => {
    const doc = { ...parseDoc(v3Fixture), name: "Moved on" };
    const reqs = doc.features.map((f) => planRequest(doc, f)!);
    notePlan(reqs[0], planAt(0));
    notePlan(reqs[1], planAt(50));
    const other = await sha256(serialise({ ...doc, name: "What the server has" }));
    keepSaved({ sha256: other }, serialise(doc), doc);
    await new Promise((r) => setTimeout(r, 20));
    // a picture is kept only of bytes a save wrote
    expect(keptPicture(other)).toBeUndefined();
    expect(keptPicture(await sha256(serialise(doc)))).toBeUndefined();
  });

  it("a marker the core refused is left out, as the editor draws none; the rest are kept", async () => {
    const base = parseDoc(v3Fixture);
    const doc = { ...base, name: "One refused", features: base.features.map((f) => ({ ...f, marker: { ...f.marker, first_id: f.marker.first_id + 20 } })) };
    const reqs = doc.features.map((f) => planRequest(doc, f)!);
    notePlan(reqs[0], null);
    notePlan(reqs[1], planAt(7));
    const text = serialise(doc);
    const sha = await sha256(text);
    keepSaved({ sha256: sha }, text, doc);
    await vi.waitFor(() => expect(keptPicture(sha)).toBeDefined());
    expect(keptPicture(sha)!.marks.map((m) => m.outer[0])).toEqual([[7, 0]]);
  });

  it("a plan without its geometry never throws into the planner", () => {
    const [a] = requests(v3Fixture);
    expect(() => notePlan(a, { ok: true } as unknown as MarkerPlan)).not.toThrow();
  });
});
