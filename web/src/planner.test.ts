// The planner on a slow fake core: backpressure (review finding #10).
import { afterAll, describe, expect, it, vi } from "vitest";

const SLOW_MS = 400;
let lastPlan: unknown = null;
const calls = { plan: 0, suggest: 0, planLive: 0, planMax: 0, suggestLive: 0, suggestMax: 0 };
const slow = <T>(kind: "plan" | "suggest", value: T) => {
  calls[kind] += 1;
  const live = `${kind}Live` as const, max = `${kind}Max` as const;
  calls[live] += 1;
  calls[max] = Math.max(calls[max], calls[live]);
  return new Promise<T>((r) => setTimeout(() => { calls[live] -= 1; r(value); }, SLOW_MS));
};

vi.mock("./coreSource", () => ({
  core: {
    plan: (req: unknown) => { lastPlan = req; return slow("plan", { ok: true, ids: [0], outer: [], black: [], warnings: [] }); },
    suggest: () => slow("suggest", []),
    assign_ids: () => Promise.reject(new Error("fake core: no auto id")),
  },
  coreStatus: () => ({ state: "ready" }),
  onCoreStatus: () => () => {},
}));

const { useStudio } = await import("./store");
const { startPlanner, plannerBusy } = await import("./planner");
const { addFeature, emptyDoc, getFeature, newFeature, planRequest, rectProfile } = await import("./model/doc");
const { rectShape } = await import("./sketch/model");

const st = () => useStudio.getState();
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));
const preset = { id: "builtin:x", name: "X", method: "inkjet" as const, builtin: true, page: "A4", page_mm: [210, 297] as [number, number] };
const stop = startPlanner();
afterAll(() => stop());

describe("planner backpressure", () => {
  it("six edits 45 ms apart on one feature, the core 400 ms a plan: one running and one latest, never a queue", async () => {
    st().loadDoc(addFeature(emptyDoc("D", [rectShape("r", 0, 0, 40, 40)], preset), newFeature(rectProfile("r"), "f1", preset)));
    st().editFeature("f1");
    await pause(100);                      // the first plan and suggestion are out
    const base = { plan: calls.plan, suggest: calls.suggest };
    for (let i = 1; i <= 6; i++) {
      st().setField("label.gap_mm", i);     // a plan input
      st().setField("marker.dictionary", i % 2 ? "DICT_5X5_50" : "DICT_4X4_50");   // a suggestion input too
      await pause(45);
    }
    while (plannerBusy()) await pause(20);
    expect(calls.planMax, "plans in flight at once for the feature").toBe(1);
    expect(calls.suggestMax, "suggestions in flight at once").toBe(1);
    // the one running when the edits came, then only the latest
    expect(calls.plan - base.plan).toBeLessThanOrEqual(2);
    expect(calls.suggest - base.suggest).toBeLessThanOrEqual(2);
    // and the latest was planned: the last request is the document as it is now
    expect(st().plans.f1).toBeTruthy();
    expect(lastPlan).toEqual(planRequest(st().doc, getFeature(st().doc, "f1")));
  });
});
