// The Sheet dialog (V1 "Click-to-inspect", 2026-10-18) on the static build:
// eight features of mixed sizes, then Sheet. The core's numbers are checked
// against CPython's web_api.sheet on the dialog's own request (the parity
// test keeps Pyodide and CPython byte-identical); sizes come from what is
// drawn (getBoundingClientRect), never from DOM presence alone.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openStudio, state } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";
const ROOT = path.resolve(import.meta.dirname, "..", "..");
const PY = [path.join(ROOT, ".venv", "bin", "python"), path.join(ROOT, ".venv", "Scripts", "python.exe")].find((p) => fs.existsSync(p));
const MM_PX = 96 / 25.4;

// eight rectangles (mm corners on the sketch), sizes repeated as a real
// document's are: 3 x 40 x 25, 3 x 40 x 30, 2 x 35 x 35. Labelled (the
// default), each sticker is its whole rectangle. On Letter, spaced with a
// 40 mm gap, the core packs them on 1 page in 18 cuts for the fewest sheets,
// on 2 pages in 17 for the fewest cuts
const RECTS: [[number, number], [number, number]][] = [
  [[-100, -45], [-60, -20]], [[-50, -45], [-10, -15]], [[0, -45], [35, -10]], [[45, -45], [85, -20]],
  [[-100, 10], [-60, 40]], [[-50, 5], [-15, 40]], [[-5, 10], [35, 35]], [[45, 10], [85, 40]],
];

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-new").click();
}

/** R, drag a rectangle, A, OK: one more feature. */
async function feature(page: Page, a: [number, number], b: [number, number]): Promise<void> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  expect((await state(page)).sel?.kind, `the rectangle from ${a} to ${b}`).toBe("shape");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
}

async function openSheet(page: Page): Promise<void> {
  await page.locator('[data-testid="tool-sheet"], [data-testid="tool-print"]').first().click();
  await expect(page.getByTestId("print-dialog")).toBeVisible();
  await expect(page.locator('[data-testid="print-page"] svg')).toBeVisible({ timeout: 45_000 });
  await idle(page);
}

interface Shown { pages: number; cuts: number; fill: number; request: Record<string, unknown> }

/** The stats the dialog shows, and the request it laid them out from. */
async function shown(page: Page): Promise<Shown> {
  await idle(page);
  await expect(page.locator(".sheet-body")).toHaveAttribute("data-busy", "0");
  const side = page.getByTestId("sheet-side");
  const num = async (id: string) => Number(await page.getByTestId(id).getAttribute("data-value"));
  return { pages: await num("sheet-pages"), cuts: await num("sheet-cuts"), fill: await num("sheet-fill"),
    request: JSON.parse((await side.getAttribute("data-request"))!) };
}

/** CPython's web_api.sheet on the same request: the core's own numbers. */
function core(request: Record<string, unknown>): { pages: number; cuts: number; fill: number } {
  expect(PY, "the repo's .venv python").toBeTruthy();
  const code = "import json, sys\nfrom aruco_studio import web_api\nsys.stdout.write(web_api.call('sheet', sys.stdin.read()))";
  const r = spawnSync(PY!, ["-c", code], { cwd: ROOT, input: JSON.stringify({ ...request, date: "2026-10-18" }), encoding: "utf8",
    maxBuffer: 1 << 28, env: { ...process.env, PYTHONPATH: ROOT, PYTHONDONTWRITEBYTECODE: "1" } });
  expect(r.status, r.stderr).toBe(0);
  const out = JSON.parse(r.stdout);
  expect(out.error).toBeUndefined();
  return { pages: out.result.pages, cuts: out.result.cuts, fill: out.result.fill };
}

test.describe(`the Sheet dialog (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core has no packer: the numbers are the real core's");

  test("eight features: Optimize, Tight / Spaced, the gap, the page in mm, page tabs", async ({ page }) => {
    await blank(page);
    for (const [a, b] of RECTS) await feature(page, a, b);
    expect((await state(page)).doc.features).toHaveLength(8);
    await openSheet(page);

    // the defaults: Spaced, Fewest sheets, the core's gap
    await expect(page.getByTestId("sheet-mode")).toHaveAttribute("data-value", "spaced");
    await expect(page.getByTestId("sheet-objective")).toHaveAttribute("data-value", "fewest_sheets");
    await expect(page.getByTestId("sheet-gap")).toBeVisible();
    const spacedSheets = await shown(page);
    expect(spacedSheets.request).toMatchObject({ mode: "spaced", objective: "fewest_sheets", gap_mm: 4 });
    expect(spacedSheets.request.items as unknown[]).toHaveLength(8);
    expect(spacedSheets).toMatchObject(core(spacedSheets.request));

    // Optimize: each objective shows the core's cuts for it; Fewest cuts never more
    const results: Record<string, Record<string, Shown>> = {};
    for (const mode of ["spaced", "tight"] as const) {
      await page.getByTestId("sheet-mode").locator(`[data-value="${mode}"]`).click();
      results[mode] = {};
      for (const objective of ["fewest_cuts", "fewest_sheets"] as const) {
        await page.getByTestId("sheet-objective").locator(`[data-value="${objective}"]`).click();
        await expect(page.getByTestId("sheet-objective")).toHaveAttribute("data-value", objective);
        const got = await shown(page);
        expect(got.request).toMatchObject({ mode, objective });
        const want = core(got.request);
        expect(got.cuts, `${mode} ${objective}: the cuts stat is the core's`).toBe(want.cuts);
        expect(got.pages).toBe(want.pages);
        expect(got.fill).toBeCloseTo(want.fill, 4);
        expect(await page.getByTestId("sheet-cuts").locator("b").textContent()).toBe(String(want.cuts));
        results[mode][objective] = got;
      }
      expect(results[mode].fewest_cuts.cuts).toBeLessThanOrEqual(results[mode].fewest_sheets.cuts);
      expect(results[mode].fewest_sheets.pages).toBeLessThanOrEqual(results[mode].fewest_cuts.pages);
    }
    console.log("sheet stats", JSON.stringify(Object.fromEntries(Object.entries(results).map(([m, r]) =>
      [m, Object.fromEntries(Object.entries(r).map(([o, s]) => [o, { pages: s.pages, cuts: s.cuts, fill: s.fill }]))]))));

    // Tight hides the gap; Spaced shows it again
    await page.getByTestId("sheet-mode").locator('[data-value="tight"]').click();
    await expect(page.getByTestId("sheet-gap")).toHaveCount(0);
    expect((await shown(page)).request.gap_mm).toBeUndefined();
    await page.getByTestId("sheet-mode").locator('[data-value="spaced"]').click();
    await expect(page.getByTestId("sheet-gap")).toBeVisible();

    // the page's SVG is sized in mm, and drawn at true size (Actual size)
    const svg = page.locator('[data-testid="print-page"] svg');
    const [w, h] = [await svg.getAttribute("width"), await svg.getAttribute("height")];
    expect(w).toMatch(/^[\d.]+mm$/);
    expect(h).toMatch(/^[\d.]+mm$/);
    const box = (await svg.boundingBox())!;
    expect(box.width).toBeCloseTo(parseFloat(w!) * MM_PX, 0);
    expect(box.height).toBeCloseTo(parseFloat(h!) * MM_PX, 0);
    await expect(page.getByTestId("sheet-page-tabs")).toHaveCount((await shown(page)).pages > 1 ? 1 : 0);
    await page.getByTestId("print-mode").locator('[data-value="fit"]').click();

    // a 40 mm gap: Fewest sheets keeps one page; Fewest cuts saves a cut on
    // a second page, and a tab per page appears
    const gap = page.locator('[data-testid="sheet-gap"] input');
    await page.getByTestId("sheet-objective").locator('[data-value="fewest_sheets"]').click();
    await gap.fill("40");
    await gap.press("Enter");
    const compact = await shown(page);
    expect(compact.request).toMatchObject({ mode: "spaced", objective: "fewest_sheets", gap_mm: 40 });
    expect(compact).toMatchObject(core(compact.request));
    await expect(page.getByTestId("sheet-page-tabs")).toHaveCount(compact.pages > 1 ? 1 : 0);
    fs.mkdirSync(SHOTS, { recursive: true });
    await page.screenshot({ path: path.join(SHOTS, "sheet-dialog.png") });
    await page.getByTestId("sheet-objective").locator('[data-value="fewest_cuts"]').click();
    const wide = await shown(page);
    expect(wide.request).toMatchObject({ mode: "spaced", objective: "fewest_cuts", gap_mm: 40 });
    expect(wide).toMatchObject(core(wide.request));
    expect(wide.cuts, "switching Optimize changes the cuts").toBeLessThan(compact.cuts);
    expect(compact.pages).toBeLessThanOrEqual(wide.pages);
    expect(wide.pages).toBeGreaterThan(1);
    const tabs = page.getByTestId("sheet-page-tab");
    await expect(tabs).toHaveCount(wide.pages);
    const first = await page.getByTestId("print-page").innerHTML();
    await tabs.nth(1).click();
    await expect(page.getByTestId("print-page")).toHaveAttribute("data-page", "2");
    expect(await page.getByTestId("print-page").innerHTML()).not.toBe(first);
    await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
    await page.screenshot({ path: path.join(SHOTS, "sheet-dialog-pages.png") });

    // back to one page: the tabs go
    await gap.fill("4");
    await gap.press("Enter");
    const back = await shown(page);
    await expect(page.getByTestId("sheet-page-tabs")).toHaveCount(back.pages > 1 ? 1 : 0);
  });
});
