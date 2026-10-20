// Trim (Zach, 2026-10-18): the sticker is cut to the profile, the marker
// rectangle (default) or the marker, and everything inside the cut is white
// -- on the canvas (the plan's cut_shape under the marker) and in Export SVG.
// On the plate's inscribed rectangle; every check measures the white path's
// box on screen (getBoundingClientRect), its fill at a point (isPointInFill)
// or the exported file's numbers. Screenshots (1280 × 800) go to TRIM_SHOTS
// (default test-results/trim).
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, dragWorld, idle, loadExample, openStudio, state, toClient } from "./helpers";

const SHOTS = process.env.TRIM_SHOTS ?? "test-results/trim";
type Box = { x0: number; y0: number; x1: number; y1: number };

/** Examples › Plate, click the face, A: the panel stays open on the feature. */
async function plateFeature(page: Page): Promise<string> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await idle(page);
  const s = await state(page);
  expect(s.feature.profile, "the feature keeps the face it was inscribed from").toBeTruthy();
  return s.panel.featureId as string;
}

async function pickTrim(page: Page, trim: string): Promise<void> {
  await page.locator(`[data-row="trim"] .kit-seg-btn[data-value="${trim}"]`).click();
  await idle(page);
  await expect.poll(async () => (await state(page)).feature.trim).toBe(trim);
}

async function screenBox(page: Page, sel: string): Promise<Box> {
  return page.locator(sel).first().evaluate((e) => {
    const r = e.getBoundingClientRect();
    return { x0: r.left, y0: r.top, x1: r.right, y1: r.bottom };
  });
}

function near(a: Box, b: Box, tol: number, what: string): void {
  for (const k of ["x0", "y0", "x1", "y1"] as const) expect(Math.abs(a[k] - b[k]), `${what} ${k}: ${a[k]} vs ${b[k]}`).toBeLessThanOrEqual(tol);
}

/** Is the sketch point (mm) inside the feature's white (its fill, even-odd)? */
async function white(page: Page, fid: string, x: number, y: number): Promise<boolean> {
  const [cx, cy] = await toClient(page, x, y);
  return page.locator(`[data-cut-white="${fid}"]`).evaluate((e, [px, py]) => {
    const svg = (e as SVGPathElement).ownerSVGElement!.getBoundingClientRect();
    return (e as SVGPathElement).isPointInFill(new DOMPoint(px - svg.left, py - svg.top));
  }, [cx, cy]);
}

const boxOf = (pts: number[][]): Box => ({
  x0: Math.min(...pts.map((p) => p[0])), y0: Math.min(...pts.map((p) => p[1])),
  x1: Math.max(...pts.map((p) => p[0])), y1: Math.max(...pts.map((p) => p[1])),
});

/** Export › SVG of the feature in focus: the white path's box (the file's mm, y down). */
async function exportedWhite(page: Page): Promise<{ box: Box; loops: number }> {
  await page.getByTestId("menu-export").click();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("cmd-svg").click()]);
  const text = readFileSync((await dl.path())!, "utf8");
  const d = /<path data-layer="white"[^>]* d="([^"]*)"/.exec(text);
  expect(d, "the exported SVG has the white").toBeTruthy();
  const subs = d![1].split("M").slice(1);
  const pts = [...d![1].matchAll(/(-?[\d.]+) (-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
  return { box: boxOf(pts), loops: subs.length };
}

/** The plan's cut_shape in the rectangle's own frame, as the SVG has it (y down). */
function cutInFile(plan: any, r: any): Box {
  const a = (r.angle_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const pts = plan.cut_shape.outer.map(([x, y]: number[]) => {
    const u = c * (x - r.cx) + s * (y - r.cy), v = -s * (x - r.cx) + c * (y - r.cy);
    return [u, -v];
  });
  return boxOf(pts);
}

test.describe(`trim (${CORE} core)`, () => {
  test.skip(CORE === "mock", "trim is the real core's (the mock has no cut_shape)");

  test("the sticker's white is the rectangle, the face with its holes, or the quiet zone; Export SVG carries it", async ({ page }) => {
    const fid = await plateFeature(page);
    const s0 = await state(page);
    const r = s0.doc.shapes.find((x: any) => x.id === s0.feature.rectId);
    const holes = s0.doc.shapes.filter((x: any) => x.kind === "circle");
    expect(holes).toHaveLength(2);

    // Rectangle is the default, driven (grey) until set
    expect(s0.feature.trim).toBe("rectangle");
    await expect(page.locator('[data-drv="trim"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-row="trim"] .kit-seg-btn[data-value="profile"]')).toBeEnabled();

    const shots: Record<string, string> = {};
    for (const trim of ["rectangle", "profile", "marker"]) {
      await pickTrim(page, trim);
      const s = await state(page);
      const w = await screenBox(page, `[data-cut-white="${fid}"]`);
      if (trim === "rectangle") {
        near(w, await screenBox(page, `[data-shape="${r.id}"]`), 1, "white vs the rectangle");
        expect(await white(page, fid, 5, 5), "the plate outside the rectangle").toBe(false);
      } else if (trim === "profile") {
        near(w, await screenBox(page, '[data-shape="plate"]'), 1, "white vs the plate face");
        for (const h of holes) expect(await white(page, fid, h.cx, h.cy), `hole ${h.id}'s centre`).toBe(false);
        expect(await white(page, fid, 5, 5), "the plate outside the rectangle").toBe(true);
      } else {
        near(w, await screenBox(page, `[data-marker="${fid}"] [data-marker-outline]`), 1, "white vs the marker's outline");
        expect(await white(page, fid, r.cx, r.cy - r.h / 2 + 0.2), "the label band, outside the quiet zone").toBe(false);
      }
      // the marker's black sits on the white, inside it
      const black = await screenBox(page, `[data-marker="${fid}"] [data-marker-black]`);
      expect(black.x0 >= w.x0 - 1 && black.x1 <= w.x1 + 1 && black.y0 >= w.y0 - 1 && black.y1 <= w.y1 + 1).toBe(true);
      // set by hand now: normal text with ↺
      await expect(page.locator('[data-drv="trim"]')).toHaveAttribute("data-driven", "0");

      // Export SVG: the white path's box in mm is the cut's
      const file = await exportedWhite(page);
      const want = cutInFile(s.plan, r);
      for (const k of ["x0", "y0", "x1", "y1"] as const) expect(Math.abs(file.box[k] - want[k]), `svg ${trim} ${k}`).toBeLessThan(1e-3);
      expect(file.loops).toBe(trim === "profile" ? 3 : 1);

      shots[trim] = path.join(SHOTS, `trim-${trim}.png`);
      await page.screenshot({ path: shots[trim] });
    }

    // ↺: back to the driven rectangle
    await page.locator('[data-reset="trim"]').click();
    await idle(page);
    expect((await state(page)).feature.trim).toBe("rectangle");
    await expect(page.locator('[data-drv="trim"]')).toHaveAttribute("data-driven", "1");
  });

  // WHY changed (2026-10-20): labels go ON the marker by default now (Zach: "the
  // text should be sized ... to fit inside that black cell row"), so a
  // marker-trimmed sticker keeps its label and nothing warns. The outside case
  // (warned) is covered in the core's tests (tests/web/test_web_trim.py) until
  // the Label tab gets its Place row.
  test("trim Marker with the label on the marker (the default): no warning, the label is on the sticker", async ({ page }) => {
    await plateFeature(page);
    const s0 = await state(page);
    expect(s0.feature.label.on).toBe(true);
    await pickTrim(page, "marker");
    await page.locator('[role=tab][data-tab="label"]').click();
    await idle(page);
    const warn = page.locator('[data-issues-for="label.on"] [data-level="warn"]');
    await expect(warn).toHaveCount(0);
    const s = await state(page);
    const plan = s.plans[s.feature.id];
    const xs = plan.cut_shape.outer.map((p: number[]) => p[0]), ys = plan.cut_shape.outer.map((p: number[]) => p[1]);
    const [lx, ly] = plan.label.at;
    expect(lx > Math.min(...xs) && lx < Math.max(...xs) && ly > Math.min(...ys) && ly < Math.max(...ys),
      `label ${plan.label.at} inside the marker-trimmed cut`).toBe(true);
    await page.screenshot({ path: path.join(SHOTS, "trim-marker-label-on-marker.png") });
  });

  test("Profile needs a profile: a drawn rectangle's feature has it disabled, with why", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await page.getByTestId("menu-file").click();
    await page.getByTestId("cmd-new").click();
    await page.keyboard.press("r");
    await dragWorld(page, [-20, -15], [20, 15]);
    await page.keyboard.press("a");
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await idle(page);
    const btn = page.locator('[data-row="trim"] .kit-seg-btn[data-value="profile"]');
    await expect(btn).toBeDisabled();
    await expect(btn).toHaveAttribute("title", /Needs a profile/);
    expect((await state(page)).feature.trim).toBe("rectangle");
  });
});
