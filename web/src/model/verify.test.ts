// Verify's required viewing distance on a feature (Feature.verify, contract
// barrier 13): set and cleared end by end, saved and read back, refused when
// malformed, never part of the plan request; and batch-set on several
// features as ONE undo step (store setFieldMany, model/batch.ts's pattern).
import { describe, expect, it, vi } from "vitest";

vi.mock("../coreSource", () => ({
  core: new Proxy({}, { get: () => () => new Promise(() => {}) }),
  coreStatus: () => ({ state: "ready" }),
}));

const { useStudio } = await import("../store");
const { MIXED, common } = await import("./batch");
const { addFeature, emptyDoc, newFeature, parseDoc, planRequest, rectProfile, resetField, serialise, setField, validateDoc } = await import("./doc");
const { rectShape } = await import("../sketch/model");

const preset = { id: "builtin:x", name: "X", method: "inkjet" as const, builtin: true, page: "A4", page_mm: [210, 297] as [number, number] };

describe("the requirement on a feature", () => {
  it("is set and cleared one end at a time; with neither end it is gone", () => {
    const f0 = newFeature(rectProfile("r"), "f1", preset);
    const f1 = setField(f0, "verify.min_mm", 300);
    expect(f1.verify).toEqual({ min_mm: 300 });
    const f2 = setField(f1, "verify.max_mm", 2000);
    expect(f2.verify).toEqual({ min_mm: 300, max_mm: 2000 });
    expect(resetField(f2, "verify.min_mm").verify).toEqual({ max_mm: 2000 });
    expect("verify" in resetField(resetField(f2, "verify.min_mm"), "verify.max_mm")).toBe(false);
    expect("verify" in setField(f2, "verify", null)).toBe(false);
    expect(setField(f0, "verify", { min_mm: 100, max_mm: 900 }).verify).toEqual({ min_mm: 100, max_mm: 900 });
    expect(f0.verify).toBeUndefined();                       // nothing mutated
  });

  it("never reaches the plan request (it changes no geometry, so nothing re-plans)", () => {
    const doc = addFeature(emptyDoc("D", [rectShape("r", 0, 0, 40, 40)], preset), setField(newFeature(rectProfile("r"), "f1", preset), "verify.max_mm", 1500));
    const req = planRequest(doc, doc.features[0]);
    expect(JSON.stringify(req)).not.toContain("verify");
    expect(JSON.stringify(req)).toBe(JSON.stringify(planRequest(doc, { ...doc.features[0], verify: undefined })));
  });

  it("is saved and read back; a garbled one reads as none; a bad one in memory is refused", () => {
    const doc = addFeature(emptyDoc("D", [rectShape("r", 0, 0, 40, 40)], preset), setField(newFeature(rectProfile("r"), "f1", preset), "verify.max_mm", 1500));
    expect(parseDoc(serialise(doc)).features[0].verify).toEqual({ max_mm: 1500 });
    const raw = JSON.parse(serialise(doc));
    raw.features[0].verify = { min_mm: "near", max_mm: -4 };
    expect(parseDoc(JSON.stringify(raw)).features[0].verify).toBeUndefined();
    raw.features[0].verify = [1, 2];
    expect(parseDoc(JSON.stringify(raw)).features[0].verify).toBeUndefined();
    const bad = { ...doc, features: [{ ...doc.features[0], verify: { min_mm: Number.NaN } }] };
    expect(() => validateDoc(bad)).toThrow(/verify\.min_mm must be a number/);
  });
});

describe("batch-set on a selection", () => {
  const twoDoc = () => {
    let d = emptyDoc("D", [rectShape("r1", 0, 0, 40, 40), rectShape("r2", 50, 0, 90, 40)], preset);
    d = addFeature(d, newFeature(rectProfile("r1"), "f1", preset));
    return addFeature(d, setField(newFeature(rectProfile("r2"), "f2", preset), "verify.min_mm", 200));
  };

  it("shows Mixed where the selected markers differ, one value where they agree", () => {
    const d = twoDoc();
    expect(common(d.features.map((f) => f.verify?.min_mm ?? null))).toBe(MIXED);
    expect(common(d.features.map((f) => f.verify?.max_mm ?? null))).toBeNull();
  });

  it("sets every selected marker at once, as one undo step", () => {
    const st = () => useStudio.getState();
    st().loadDoc(twoDoc());
    st().setFieldMany(["f1", "f2"], "verify.max_mm", 1800);
    expect(st().doc.features.map((f) => f.verify)).toEqual([{ max_mm: 1800 }, { min_mm: 200, max_mm: 1800 }]);
    st().undo();
    expect(st().doc.features.map((f) => f.verify)).toEqual([undefined, { min_mm: 200 }]);
    st().redo();
    st().setFieldMany(["f1", "f2"], "verify", null);         // Clear
    expect(st().doc.features.map((f) => f.verify)).toEqual([undefined, undefined]);
    st().undo();
    expect(st().doc.features.map((f) => f.verify)).toEqual([{ max_mm: 1800 }, { min_mm: 200, max_mm: 1800 }]);
  });
});
