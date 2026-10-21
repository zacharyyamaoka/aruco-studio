// Review finding #3 (2026-10-21): a version 2 file's sticker is cut where it
// was cut before migration, for every legacy trim mode, and its marker stays
// in the rectangle it filled. On the real core: the cut is the core's answer.
import path from "node:path";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { CORE, coreReady, idle, openMenu, openStudio, state } from "./helpers";

const FIXTURE = path.join(import.meta.dirname, "fixtures", "v2-rect.arucostudio-web.json");
type Cut = { outer: number[][]; holes: number[][][] };
const box = (pts: number[][]) => {
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)].map((v) => Math.round(v * 1000) / 1000);
};

// f2 filled r2 (x 35..85, y 0..80) inscribed in the plate (0..120 × 0..80, two Ø20 holes);
// the cut each v2 trim made: the rectangle, the face with its holes, or the marker
const BEFORE: Record<string, { box?: number[]; holes: number; inside?: number[] }> = {
  rectangle: { box: [35, 0, 85, 80], holes: 0 },
  profile: { box: [0, 0, 120, 80], holes: 2 },
  marker: { inside: [35, 0, 85, 80], holes: 0 },
};

test.describe("version 2 trim modes after migration", () => {
  test.skip(CORE === "mock", "the cut is the real core's");
  for (const trim of Object.keys(BEFORE)) {
    test(`trim ${trim}: the cut and the placement are what the v2 file had`, async ({ page }) => {
      await openStudio(page);
      await coreReady(page);
      const raw = JSON.parse(readFileSync(FIXTURE, "utf8"));
      raw.features[1].trim = trim;
      const file = path.join(test.info().outputDir, `v2-${trim}.arucostudio-web.json`);
      mkdirSync(test.info().outputDir, { recursive: true });
      writeFileSync(file, JSON.stringify(raw));
      await openMenu(page, "file");
      const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
      await chooser.setFiles(file);
      await idle(page);
      await expect.poll(async () => !!(await state(page)).plans.f2?.cut_shape, { message: "f2 is planned" }).toBe(true);
      const plan = (await state(page)).plans.f2;
      const cut = plan.cut_shape as Cut;
      const want = BEFORE[trim];
      if (want.box) expect(box(cut.outer)).toEqual(want.box);
      if (want.inside) {
        const [x0, y0, x1, y1] = box(cut.outer);
        expect(x0).toBeGreaterThanOrEqual(want.inside[0] - 1e-6);
        expect(y0).toBeGreaterThanOrEqual(want.inside[1] - 1e-6);
        expect(x1).toBeLessThanOrEqual(want.inside[2] + 1e-6);
        expect(y1).toBeLessThanOrEqual(want.inside[3] + 1e-6);
      }
      expect(cut.holes).toHaveLength(want.holes);
      // the marker is still placed in r2, whatever the cut
      expect(plan.fit_rect).toEqual({ cx: 60, cy: 40, w: 50, h: 80, angle_deg: 0 });
    });
  }
});
