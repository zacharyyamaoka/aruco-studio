// The range strip's runner and numbers (./range.ts) on a fake core: one
// marker at a time in slices, the wanted order followed, a part-done marker
// resumed where it was, the dialog's close cancelling, answers kept; and the
// shared log axis, its ticks, the camera search and the kept camera.
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CameraPreset, PlanRequest, RangeStep, ReadingRange } from "../core/contract";

/** each job takes STEPS slices; every call is logged */
const STEPS = 3;
const log: string[] = [];
const jobs = new Map<string, { key: string; left: number }>();
let seq = 0;
let failNextStart: string | null = null;
let failScenes = false;

const result = (far: number): ReadingRange => ({ version: "reading-range/1", near_mm: 100, far_mm: far, band_mm: [far * 0.9, far * 1.1], pm: 0.1,
  near_by: "frame", near_checked: true, far_limit: "cells", far_px_per_cell: 3, far_outline_px: 80, min_outline_px: 57.6, weakest_id: null,
  rows: [], renders: 300, cases: 48, seed: 1, p_read: 0.95,
  budget: { name: "Field", tilt_max_deg: 45, blur_px: [0.3, 1.5], noise: [0.02, 0.2], glare: [0, 0.5], occlusion: 0 },
  camera: { id: "d435", name: "RealSense D435", resolution: [1920, 1080], hfov_deg: 69, focus_mm: null },
  geometry: { bounds_mm: [-20, -20, 20, 20], cell_mm: 5, marker_mm: 30, ids: [0] }, measured: true, opencv: "4.11.0" });

/** a worker round trip: the answer comes back on a later task, as a postMessage's does */
const trip = () => new Promise((r) => setTimeout(r, 0));

vi.mock("../coreSource", () => ({
  core: {
    range_start: async (req: PlanRequest): Promise<RangeStep> => {
      await trip();
      const key = String(req.marker.first_id);
      log.push(`start ${key}`);
      if (failNextStart === key) { failNextStart = null; throw new Error("OpenCV did not load"); }
      const job = `range-${++seq}`;
      jobs.set(job, { key, left: STEPS });
      return { job, done: false, phase: "bracket", fraction: 0.02, renders: 0 };
    },
    range_step: async (job: string): Promise<RangeStep> => {
      await trip();
      const j = jobs.get(job);
      if (!j) throw new Error(`no reading-range job '${job}': finished, cancelled or dropped`);
      log.push(`step ${j.key}`);
      j.left -= 1;
      if (j.left > 0) return { job, done: false, phase: "fit", fraction: (STEPS - j.left) / STEPS, renders: 100 * (STEPS - j.left), ms: 10 };
      jobs.delete(job);
      return { job, done: true, renders: 300, ms: 30, result: result(1000 + Number(j.key)) };
    },
    range_cancel: async (job: string) => { log.push(`cancel ${jobs.get(job)?.key}`); return { job, cancelled: jobs.delete(job) }; },
    range_judge: async (r: ReadingRange, need: { max_mm?: number }) =>
      ({ verdict: (r.far_mm ?? 0) >= (need.max_mm ?? 0) ? "pass" : "fail", checks: [], hints: [], size_mm: null }),
    // the scene a marker shows the camera: its first id and size, never where it sits (a fake web_api.scene_key)
    scene_keys: async (reqs: PlanRequest[]) => {
      await trip();
      log.push(`scenes ${reqs.length}`);
      if (failScenes) { failScenes = false; throw new Error("core: not loaded"); }
      return reqs.map((r) => (r.marker.first_id < 0 ? null : `scene-${r.marker.first_id}-${r.marker.marker_mm ?? 0}`));
    },
  },
}));

const R = await import("./range");
const req = (id: number) => ({ marker: { first_id: id } }) as unknown as PlanRequest;
const task = (id: number) => ({ key: `k${id}`, req: req(id), camera: "d435" as const });
const settle = async () => { for (let i = 0; i < 80; i++) await new Promise((r) => setTimeout(r, 0)); };
/** wait until the log has this line */
const until = async (line: string) => { for (let i = 0; i < 200 && !log.includes(line); i++) await new Promise((r) => setTimeout(r, 0)); };

beforeEach(() => { log.length = 0; R.forgetRanges(); });

describe("the runner", () => {
  it("measures the wanted markers one at a time, in order, a slice per call", async () => {
    R.ranges.want([task(1), task(2)]);
    await settle();
    expect(log).toEqual(["start 1", "step 1", "step 1", "step 1", "start 2", "step 2", "step 2", "step 2"]);
    const s = R.ranges.state("k1");
    expect(s.state).toBe("done");
    expect(s.state === "done" && s.result.far_mm).toBe(1001);
    expect(R.ranges.busy()).toBe(false);
  });

  it("keeps a finished range: asked again, it is there with no call", async () => {
    R.ranges.want([task(3)]);
    await settle();
    log.length = 0;
    R.ranges.want([task(3)]);
    await settle();
    expect(log).toEqual([]);
    expect(R.cached("k3")?.result.far_mm).toBe(1003);
  });

  it("follows a new order between slices and resumes the part-done marker where it was", async () => {
    R.ranges.want([task(10), task(11)]);
    await until("step 10");
    // after a slice of #10, #11 is wanted first
    R.ranges.want([task(11), task(10)]);
    await settle();
    expect(log.filter((x) => x.startsWith("start"))).toEqual(["start 10", "start 11"]);
    expect(log.filter((x) => x === "step 10")).toHaveLength(STEPS);          // resumed, not started over
    expect(log.indexOf("step 11")).toBeLessThan(log.lastIndexOf("step 10"));
    expect(R.ranges.state("k10").state).toBe("done");
  });

  it("pauses on want([]), and the dialog's close cancels the part-done job", async () => {
    R.ranges.want([task(20)]);
    await until("step 20");
    R.ranges.want([]);
    await settle();
    const before = log.filter((x) => x === "step 20").length;
    expect(before).toBeLessThan(STEPS);
    expect(R.ranges.state("k20").state).toBe("running");
    R.ranges.cancelAll();
    await settle();
    expect(log).toContain("cancel 20");
    expect(R.ranges.state("k20").state).toBe("queued");
  });

  it("a new list (another camera) cancels the part-done job it no longer has", async () => {
    R.ranges.want([task(50)]);
    await until("step 50");
    R.ranges.want([task(51)]);
    await settle();
    expect(log).toContain("cancel 50");
    expect(log.filter((x) => x === "step 50").length).toBeLessThan(STEPS);
    expect(R.ranges.state("k51").state).toBe("done");
    expect(R.ranges.state("k50").state).toBe("queued");
  });

  it("a slice that comes back after the dialog closed leaves the marker queued, to start over", async () => {
    R.ranges.want([task(60)]);
    await until("step 60");
    const steps = log.filter((x) => x === "step 60").length;
    R.ranges.cancelAll();                      // while the next slice may be out
    await settle();
    expect(R.ranges.state("k60").state).toBe("queued");
    expect(log.filter((x) => x === "step 60").length).toBeLessThanOrEqual(steps + 1);
    log.length = 0;
    R.ranges.want([task(60)]);
    await settle();
    expect(log[0]).toBe("start 60");           // a new job, not the cancelled one
    expect(R.ranges.state("k60").state).toBe("done");
  });

  it("shows an error, and Retry measures again", async () => {
    failNextStart = "30";
    R.ranges.want([task(30)]);
    await settle();
    const s = R.ranges.state("k30");
    expect(s.state === "error" && s.error).toBe("OpenCV did not load");
    R.ranges.retry("k30");
    await settle();
    expect(R.ranges.state("k30").state).toBe("done");
  });

  it("judges through the core, once per range and requirement", async () => {
    R.ranges.want([task(40)]);
    await settle();
    const s = R.ranges.state("k40");
    if (s.state !== "done") throw new Error("not done");
    const k = R.verdictKey("k40", { max_mm: 2000 });
    expect(R.knownVerdict(k)).toBeNull();
    expect((await R.judge(k, s.result, { max_mm: 2000 })).verdict).toBe("fail");
    expect(R.knownVerdict(k)?.verdict).toBe("fail");
    expect((await R.judge(R.verdictKey("k40", { max_mm: 900 }), s.result, { max_mm: 900 })).verdict).toBe("pass");
  });
});

describe("the shared axis", () => {
  it("spans nice values round every end and requirement", () => {
    const [lo, hi] = R.axisOf([result(1520), { ...result(400), near_mm: 112, band_mm: [380, 450] }], [{ min_mm: 300, max_mm: 2000 }]);
    expect(lo).toBe(50);          // 112 / 1.25 = 89.6 -> 50
    expect(hi).toBe(5000);        // the requirement's 2000 x 1.25 = 2500 -> 5000
    expect(R.axisOf([], [])).toEqual([50, 5000]);
  });
  it("ticks 1-2-5 inside it, the last with its unit", () => {
    expect(R.ticksOf(50, 5000)).toEqual([50, 100, 200, 500, 1000, 2000, 5000]);
    expect(R.tickText(200, false)).toBe("0.2");
    expect(R.tickText(5000, true)).toBe("5 m");
  });
  it("puts a distance on a log scale, clamped", () => {
    expect(R.xOf(100, 100, 10000, 0, 200)).toBe(0);
    expect(R.xOf(1000, 100, 10000, 0, 200)).toBeCloseTo(100, 9);
    expect(R.xOf(1e6, 100, 10000, 0, 200)).toBe(200);
  });
  it("words a distance as the strip does", () => {
    expect(R.fmtMm(446.2)).toBe("446 mm");
    expect(R.fmtMm(1519.8)).toBe("1.52 m");
    expect(R.fmtMm(null)).toBe("—");
  });
});

describe("the camera", () => {
  const lib = [
    { id: "d435", name: "RealSense D435", maker: "Intel RealSense", stream: "colour 1920×1080", resolution: [1920, 1080], keywords: "intel depth" },
    { id: "oakd12", name: "Luxonis OAK-D", maker: "Luxonis", stream: "colour 12 MP", resolution: [4056, 3040], keywords: "oak d depthai" },
    { id: "c920", name: "Logitech C920", maker: "Logitech", stream: "1080p", resolution: [1920, 1080], keywords: "webcam usb" },
  ] as unknown as CameraPreset[];
  it("is searched by every word typed", () => {
    expect(R.searchCameras(lib, "").map((c) => c.id)).toEqual(["d435", "oakd12", "c920"]);
    expect(R.searchCameras(lib, "realsense").map((c) => c.id)).toEqual(["d435"]);
    expect(R.searchCameras(lib, "1920x1080").map((c) => c.id)).toEqual(["d435", "c920"]);
    expect(R.searchCameras(lib, "oak 12").map((c) => c.id)).toEqual(["oakd12"]);
    expect(R.searchCameras(lib, "webcam logitech").map((c) => c.id)).toEqual(["c920"]);
    expect(R.searchCameras(lib, "zed")).toEqual([]);
  });
  it("falls back to the D435 without storage, and asks the core for an id or the custom numbers", () => {
    expect(R.loadCamera()).toEqual({ id: "d435" });
    expect(R.rangeCamera({ id: "oakd12" })).toBe("oakd12");
    expect(R.rangeCamera({ custom: { resolution: [800, 600], hfov_deg: 60, focus_mm: null } }))
      .toEqual({ id: "custom", name: "Custom camera", resolution: [800, 600], hfov_deg: 60, focus_mm: null });
  });
  it("keys a range by the scene, the camera, the core and the OpenCV", () => {
    const a = R.rangeKey("scene-1", "d435", "0.1.0+abc", "4.11.0");
    expect(R.rangeKey("scene-1", "d435", "0.1.0+abc", "4.11.0")).toBe(a);
    expect(R.rangeKey("scene-1", "d455", "0.1.0+abc", "4.11.0")).not.toBe(a);
    expect(R.rangeKey("scene-1", "d435", "0.1.0+def", "4.11.0")).not.toBe(a);
    expect(R.rangeKey("scene-2", "d435", "0.1.0+abc", "4.11.0")).not.toBe(a);
    expect(R.rangeKey("scene-1", "d435", "0.1.0+abc", "5.0.0")).not.toBe(a);
    expect(JSON.parse(a).slice(2)).toEqual(["d435", "scene-1", "4.11.0"]);
  });
  it("asks the core for the scene keys it lacks, all in one call, and a moved marker finds its range", async () => {
    // two markers; the second moved on the page: another request, the same scene
    const moved = (id: number, cx: number) => ({ marker: { first_id: id, marker_mm: 30 }, rect: { cx } }) as unknown as PlanRequest;
    const items = [{ key: "r81@0", req: moved(81, 0) }, { key: "r82@0", req: moved(82, 0) }];
    expect(R.markerRangeKey("r81@0", "d435", "v", "5.0.0")).toBeNull();          // not known yet: no task
    await R.askScenes(items);
    expect(log.filter((x) => x.startsWith("scenes"))).toEqual(["scenes 2"]);
    await R.askScenes(items);                                                    // known: no call
    expect(log.filter((x) => x.startsWith("scenes"))).toEqual(["scenes 2"]);
    const k = R.markerRangeKey("r81@0", "d435", "v", "5.0.0")!;
    R.ranges.want([{ key: k, req: items[0].req, camera: "d435" }]);
    await settle();
    expect(R.cached(k)?.result.far_mm).toBe(1081);
    // the marker moved 10 mm: a new request asks its scene once, and keys the same range
    log.length = 0;
    await R.askScenes([{ key: "r81@10", req: moved(81, 10) }]);
    expect(log).toEqual(["scenes 1"]);
    expect(R.markerRangeKey("r81@10", "d435", "v", "5.0.0")).toBe(k);
    R.ranges.want([{ key: k, req: moved(81, 10), camera: "d435" }]);
    await settle();
    expect(log.filter((x) => !x.startsWith("scenes"))).toEqual([]);           // no range run
    // a size change is another scene: measured again
    await R.askScenes([{ key: "r81@10-25", req: { ...moved(81, 10), marker: { first_id: 81, marker_mm: 25 } } as unknown as PlanRequest }]);
    expect(R.markerRangeKey("r81@10-25", "d435", "v", "5.0.0")).not.toBe(k);
    // the core failing to say: each is keyed by its request, so the strip still measures
    failScenes = true;
    await R.askScenes([{ key: "fails", req: moved(83, 0) }]);
    expect(JSON.parse(R.markerRangeKey("fails", "d435", "v", "5.0.0")!)[3]).toBe("request:fails");
    // one that does not plan keys by its request (its error shows); finished() names the request a range was for
    await R.askScenes([{ key: "bad", req: moved(-1, 0) }]);
    expect(JSON.parse(R.markerRangeKey("bad", "d435", "v", "5.0.0")!)[3]).toBe("request:bad");
    expect(R.ranges.finished().find((f) => f.key === k)?.req).toEqual(moved(81, 10));
  });
  it("never keeps an answer another OpenCV measured (a slice resent to a restarted worker) under this one's key", async () => {
    const k50 = R.rangeKey("scene-71", "d435", "0.1.0+abc", "5.0.0");
    R.ranges.want([{ key: k50, req: req(71), camera: "d435", opencv: "5.0.0" }]);
    await settle();
    // the fake core's answers are 4.11's (result()): not 5.0's, so not kept, and said
    expect(R.cached(k50)).toBeNull();
    const s = R.ranges.state(k50);
    expect(s.state).toBe("error");
    expect(s.state === "error" && s.error).toMatch(/measured on OpenCV 4\.11\.0, not 5\.0\.0/);
  });
  it("never shows another OpenCV's range as this one's: kept under the OpenCV that measured it", async () => {
    const k411 = R.rangeKey("scene-70", "d435", "0.1.0+abc", "4.11.0");
    const k50 = R.rangeKey("scene-70", "d435", "0.1.0+abc", "5.0.0");
    R.ranges.want([{ key: k411, req: req(70), camera: "d435" }]);
    await settle();
    expect(R.cached(k411)?.result.far_mm).toBe(1070);
    expect(R.cached(k50)).toBeNull();
    // asked on the other OpenCV it is measured again, not taken from the first
    log.length = 0;
    R.ranges.want([{ key: k50, req: req(70), camera: "d435" }]);
    expect(R.ranges.state(k50).state).not.toBe("done");
    await settle();
    expect(log[0]).toBe("start 70");
    // and back: the first is there at once
    log.length = 0;
    R.ranges.want([{ key: k411, req: req(70), camera: "d435" }]);
    await settle();
    expect(log).toEqual([]);
  });
});
