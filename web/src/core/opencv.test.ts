// The browser's OpenCV builds (./opencv.ts): every one named is loadable here
// (a lock package is in node_modules/pyodide's lock at that version), the
// default is the newest, and a remembered choice this browser cannot load
// falls back to it.
import { afterEach, describe, expect, it, vi } from "vitest";
// WHY Vite's ?raw and glob, not node:fs: the app's tsconfig has no Node types
import lockText from "../../node_modules/pyodide/pyodide-lock.json?raw";
import { OPENCV_BUILDS, byNewest, loadOpenCv, opencvBuild, saveOpenCv, shortVersion, versionKey, type OpenCvBuild } from "./opencv";

const lock = JSON.parse(lockText) as { info: { abi_version: string; python: string }; packages: Record<string, { version: string; file_name: string }> };
/** the wheels the site serves (web/public/opencv/) */
const served = Object.keys(import.meta.glob("../../public/opencv/*.whl")).map((k) => k.replace("../../public/", ""));

describe("the browser's OpenCV builds", () => {
  it("names each lock package at the version the lock ships (cv2's three parts of the wheel's four)", () => {
    const fromLock = OPENCV_BUILDS.filter((b) => !b.load.endsWith(".whl"));
    expect(fromLock.length).toBeGreaterThan(0);
    for (const b of fromLock) {
      const pkg = lock.packages[b.load];
      expect(pkg, `${b.load} is in the Pyodide lock`).toBeTruthy();
      expect(pkg.version.split(".").slice(0, 3).join(".")).toBe(b.version);
      expect(b.source).toContain(pkg.version);
    }
  });

  it("serves every wheel it names from web/public, built for this Pyodide (its Python and ABI)", () => {
    // WHY: a Pyodide upgrade changes the ABI; a wheel built for the old one would not load
    const [maj, min] = lock.info.python.split(".");
    for (const b of OPENCV_BUILDS.filter((x) => x.load.endsWith(".whl"))) {
      expect(served, b.load).toContain(b.load);
      expect(b.load, "the wheel's tag").toContain(`-cp${maj}${min}-cp${maj}${min}-pyemscripten_${lock.info.abi_version}_wasm32.whl`);
      expect(b.load.split("/").pop()!.split("-")[1].split(".").slice(0, 3).join("."), "the wheel's version").toBe(b.version);
    }
  });

  it("lists exactly what this browser can load: the lock's opencv-python and the wheels the site serves", () => {
    // docs/build_guides.py's browser_opencvs() reads the same two places, so the guide and the Studio agree
    const three = (v: string) => v.split(".").slice(0, 3).join(".");
    const lockV = lock.packages["opencv-python"] ? [three(lock.packages["opencv-python"].version)] : [];
    const wheelV = served.map((f) => three(f.split("/").pop()!.split("-")[1]));
    expect(new Set(OPENCV_BUILDS.map((b) => b.version))).toEqual(new Set([...lockV, ...wheelV]));
  });

  it("lists each version once", () => {
    expect(new Set(OPENCV_BUILDS.map((b) => b.version)).size).toBe(OPENCV_BUILDS.length);
  });

  it("orders by version, not by text: 4.11 is newer than 4.9, 5.0 than 4.11", () => {
    const builds: OpenCvBuild[] = ["4.9.0", "5.0.0", "4.11.0"].map((version) => ({ version, load: "x", mb: 1, source: "" }));
    expect(byNewest(builds).map((b) => b.version)).toEqual(["5.0.0", "4.11.0", "4.9.0"]);
    expect(versionKey("4.11.0")).toEqual([4, 11, 0]);
    expect(shortVersion("4.11.0")).toBe("4.11");
    // the default is the newest; a version asked for is kept only when it is loadable
    expect(opencvBuild(null, builds).version).toBe("5.0.0");
    expect(opencvBuild("4.9.0", builds).version).toBe("4.9.0");
    expect(opencvBuild("3.4.0", builds).version).toBe("5.0.0");
  });
});

describe("the choice, remembered per viewer", () => {
  const store = new Map<string, string>();
  afterEach(() => { store.clear(); vi.unstubAllGlobals(); });
  const stubStorage = () => vi.stubGlobal("window", {
    localStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => { store.set(k, v); } },
  });

  it("is the newest until one is chosen, then that one", () => {
    stubStorage();
    const builds: OpenCvBuild[] = ["4.11.0", "5.0.0"].map((version) => ({ version, load: "x", mb: 1, source: "" }));
    expect(loadOpenCv(builds)).toBe("5.0.0");
    saveOpenCv("4.11.0");
    expect(loadOpenCv(builds)).toBe("4.11.0");
    // a choice this browser can no longer load (a build dropped): the newest again
    saveOpenCv("4.10.0");
    expect(loadOpenCv(builds)).toBe("5.0.0");
  });

  it("works with storage blocked", () => {
    vi.stubGlobal("window", { localStorage: { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } } });
    expect(loadOpenCv()).toBe(byNewest()[0].version);
    expect(() => saveOpenCv("4.11.0")).not.toThrow();
  });
});
