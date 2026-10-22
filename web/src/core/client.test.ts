// The core client (./client.ts) over a fake Worker, with two OpenCV builds
// (./opencv.ts's list replaced): the choice reaches the worker before any
// call; choosing another before OpenCV has loaded only tells the worker;
// once one has loaded, another starts a new worker, and the calls the old
// one had not answered go to the new one, in the order they were asked,
// while the old one's late answers are dropped.
import { describe, expect, it, vi } from "vitest";

class FakeWorker {
  static all: FakeWorker[] = [];
  sent: Record<string, unknown>[] = [];
  terminated = false;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: ErrorEvent) => void) | null = null;
  constructor() { FakeWorker.all.push(this); }
  postMessage(m: Record<string, unknown>) { this.sent.push(m); }
  terminate() { this.terminated = true; }
  reply(m: unknown) { this.onmessage?.({ data: m } as MessageEvent); }
  calls() { return this.sent.filter((m) => "id" in m).map((m) => `${m.id}:${m.name}`); }
}

const store = new Map<string, string>();
vi.stubGlobal("Worker", FakeWorker);
vi.stubGlobal("window", { localStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => { store.set(k, v); } } });

vi.mock("./opencv", async (importOriginal) => {
  const m = await importOriginal<typeof import("./opencv")>();
  const builds = [
    { version: "4.11.0", load: "opencv-python", mb: 13, source: "the lock's" },
    { version: "5.0.0", load: "opencv/opencv_python-5.0.0.whl", mb: 14, source: "the site's" },
  ];
  return { ...m, OPENCV_BUILDS: builds, opencvBuild: (v: string | null) => m.opencvBuild(v, builds), loadOpenCv: () => m.loadOpenCv(builds) };
});

const C = await import("./client");

describe("the core client's OpenCV", () => {
  it("tells the first worker the newest build before any call", () => {
    expect(FakeWorker.all).toHaveLength(1);
    expect(FakeWorker.all[0].sent[0]).toEqual({ kind: "opencv", version: "5.0.0" });
    expect(C.opencvState()).toEqual({ wanted: "5.0.0", loaded: null });
  });

  it("before OpenCV has loaded, another build is only told to the worker (and remembered)", () => {
    const w = FakeWorker.all[0];
    C.chooseOpencv("4.11.0");
    expect(FakeWorker.all).toHaveLength(1);
    expect(w.sent.at(-1)).toEqual({ kind: "opencv", version: "4.11.0" });
    expect(store.get("aruco-web.verify.opencv")).toBe("4.11.0");
    C.chooseOpencv("5.0.0");
    expect(w.sent.at(-1)).toEqual({ kind: "opencv", version: "5.0.0" });
    // a build this browser does not list is the newest
    C.chooseOpencv("3.4.0");
    expect(C.opencvState().wanted).toBe("5.0.0");
  });

  it("once one has loaded, another starts a new worker; the unanswered calls go to it in order, the old one's late answers are dropped", async () => {
    const w1 = FakeWorker.all[0];
    const plan = C.core.plan({} as never);                 // queued: the core is not up
    w1.reply({ kind: "ready", ms: 1 });
    expect(w1.calls()).toEqual(["1:plan"]);
    const v1 = C.core.verify({} as never, {} as never);
    const v2 = C.core.verify({} as never, {} as never);
    expect(w1.calls()).toEqual(["1:plan", "2:verify", "3:verify"]);
    w1.reply({ kind: "opencv", version: "5.0.0" });
    expect(C.opencvState()).toEqual({ wanted: "5.0.0", loaded: "5.0.0" });
    w1.reply({ id: 1, result: { ok: true } });
    await expect(plan).resolves.toEqual({ ok: true });
    w1.reply({ id: 2, result: { opencv: "5.0.0" } });
    await expect(v1).resolves.toEqual({ opencv: "5.0.0" });

    C.chooseOpencv("4.11.0");
    expect(w1.terminated).toBe(true);
    expect(FakeWorker.all).toHaveLength(2);
    const w2 = FakeWorker.all[1];
    expect(w2.sent[0]).toEqual({ kind: "opencv", version: "4.11.0" });
    expect(C.coreStatus().state).toBe("loading");
    expect(C.opencvState()).toEqual({ wanted: "4.11.0", loaded: null });
    const p4 = C.core.plan({} as never);                   // asked while the new one starts
    w1.reply({ id: 3, result: { opencv: "5.0.0" } });      // the old worker's last word: not this call's answer
    w2.reply({ kind: "ready", ms: 1 });
    expect(w2.calls()).toEqual(["3:verify", "4:plan"]);
    w2.reply({ kind: "opencv", version: "4.11.0" });
    w2.reply({ id: 3, result: { opencv: "4.11.0" } });
    await expect(v2).resolves.toEqual({ opencv: "4.11.0" });
    w2.reply({ id: 4, result: { ok: true } });
    await expect(p4).resolves.toEqual({ ok: true });
    expect(C.opencvState()).toEqual({ wanted: "4.11.0", loaded: "4.11.0" });
    // the same build again: nothing restarts
    C.chooseOpencv("4.11.0");
    expect(FakeWorker.all).toHaveLength(2);
  });
});
