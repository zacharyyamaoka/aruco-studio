// N-3: where a fresh window lands, and the error count a card shows.
import { describe, expect, it } from "vitest";
import type { SceneDoc } from "../api/types";
import { errorCount, landing } from "./model";

const GAL = "C:\\Users\\BAM\\Documents\\aruco-studio\\.studio_data\\gallery";

describe("landing", () => {
  it("is the gallery on a fresh server (no file) and on a gallery copy", () => {
    expect(landing("", null, GAL, false)).toEqual({ page: "gallery", example: null });
    expect(landing("", `${GAL}\\faces.arucostudio.json`, GAL, false).page).toBe("gallery");
    expect(landing("", `${GAL.toLowerCase().replace(/\\/g, "/")}/faces.arucostudio.json`, GAL, false).page).toBe("gallery");
  });
  it("is the Studio on a file opened on purpose, with ?draw=1, or by the hash", () => {
    expect(landing("", "C:\\work\\arm.arucostudio.json", GAL, false).page).toBe("studio");
    expect(landing("", `${GAL}-old\\x.arucostudio.json`, GAL, false).page).toBe("studio");      // a sibling, not inside
    expect(landing("", null, GAL, true).page).toBe("studio");
    expect(landing("#studio", null, GAL, false).page).toBe("studio");
    expect(landing("#gallery", "C:\\work\\arm.arucostudio.json", GAL, true).page).toBe("gallery");
    expect(landing("#example=labels_where", null, GAL, false)).toEqual({ page: "studio", example: "labels_where" });
    expect(landing("#example=a%20b", null, GAL, false).example).toBe("a b");
  });
});

describe("errorCount", () => {
  const tag = (plan: any) => ({ name: "t", plan } as any);
  it("counts the compile's errors, a tag that does not plan, plan errors and error-level warnings", () => {
    const scene = { tags: [
      tag({ ok: true, errors: [], warnings: [{ level: "warn" }, { level: "info" }] }),
      tag({ ok: false, errors: ["nothing fits"], warnings: [{ level: "error" }] }),
      tag(null),
    ] } as unknown as SceneDoc;
    expect(errorCount(scene, [{ level: "error" }, { level: "info" }])).toBe(1 + 2 + 1 + 1);
    expect(errorCount({ tags: [tag({ ok: true, errors: [], warnings: [{ level: "warn" }] })] } as unknown as SceneDoc)).toBe(0);
    expect(errorCount(null)).toBe(0);
  });
});
