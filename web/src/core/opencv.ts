// The OpenCVs the browser's Verify can run, and which one it does: ONE per
// run, the newest unless this viewer chose another (docs/peps/0003, decision
// 3; Zach, 2026-10-21: "Let's only run one, but you can choose, and by
// default it should be the most recent one").
// ONLY builds this browser can load are listed: a package of the Pyodide lock
// (loaded from Pyodide's CDN, its hashes checked by the lock) or a wheel the
// site serves. The core's worker loads the chosen one on its first OpenCV
// call (./worker.ts); a compiled module stays once imported, so choosing
// another after that restarts the worker (./client.ts).
// opencv.test.ts holds the lock's entry to node_modules/pyodide's lock, so a
// Pyodide upgrade cannot leave a stale version named here.

export interface OpenCvBuild {
  /** cv2.__version__ of the build: what every answer's `opencv` says */
  version: string;
  /** Pyodide's loadPackage name for it (a package of the lock), or a wheel path under the site's base */
  load: string;
  /** what the first OpenCV call downloads (numpy + the wheel), MB, for "Loading OpenCV 4.11 (13 MB)…" */
  mb: number;
  /** where it comes from, in words (the choice's hint) */
  source: string;
}

// WHY these two (measured 2026-10-21): Pyodide 314.0.7, the newest stable,
// ships opencv-python 4.11.0.86 (10.7 MB wheel + numpy 3.0 MB); its 315
// alphas ship no OpenCV, PyPI has no wasm wheel of any OpenCV, and
// pyodide-recipes pins 4.11.0.86. So 5.0, the scripts' OpenCV
// (requirements.txt), is built here for Pyodide 314 by tools/opencv-wasm/
// (4.5 MB: the modules the core calls) and served by the site; its reading
// ranges came out byte-identical to CPython's 5.0, and it loads faster than
// 4.11 (cv2 in ~0.14 s against ~0.44 s, Node, warm disk).
export const OPENCV_BUILDS: readonly OpenCvBuild[] = [
  { version: "5.0.0", load: "opencv/opencv_python-5.0.0.93-cp314-cp314-pyemscripten_2026_0_wasm32.whl", mb: 7,
    source: "opencv-python 5.0.0.93 built for Pyodide 314.0.7 (tools/opencv-wasm)" },
  { version: "4.11.0", load: "opencv-python", mb: 13, source: "Pyodide 314.0.7's opencv-python 4.11.0.86" },
];

/** "4.11.0" -> [4, 11, 0]: the newest compares largest. */
export function versionKey(v: string): number[] {
  return v.split(".").map((p) => (/^\d+/.test(p) ? Number(/^\d+/.exec(p)![0]) : 0));
}

function newer(a: string, b: string): number {
  const x = versionKey(a), y = versionKey(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (x[i] ?? 0) - (y[i] ?? 0);
    if (d) return d;
  }
  return 0;
}

/** The builds, newest first. */
export function byNewest(builds: readonly OpenCvBuild[] = OPENCV_BUILDS): OpenCvBuild[] {
  return [...builds].sort((a, b) => newer(b.version, a.version));
}

/** "4.11.0" -> "4.11": what the UI prints. */
export function shortVersion(v: string): string {
  return v.split(".").slice(0, 2).join(".");
}

/** The build to run: the one asked for when this browser can load it, else the newest. */
export function opencvBuild(version: string | null | undefined, builds: readonly OpenCvBuild[] = OPENCV_BUILDS): OpenCvBuild {
  return builds.find((b) => b.version === version) ?? byNewest(builds)[0];
}

// ------------------------------------------------------------ the choice, remembered per viewer

const KEY = "aruco-web.verify.opencv";

/** The remembered choice when it is still loadable here, else the newest. */
export function loadOpenCv(builds: readonly OpenCvBuild[] = OPENCV_BUILDS): string {
  let v: string | null = null;
  try { v = window.localStorage.getItem(KEY); } catch { /* storage blocked: the default */ }
  return opencvBuild(v, builds).version;
}

export function saveOpenCv(version: string): void {
  try { window.localStorage.setItem(KEY, version); } catch { /* kept for this visit only */ }
}
