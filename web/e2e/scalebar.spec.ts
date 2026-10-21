// The Print dialog's "Scale bar" row (barrier 12, Zach 2026-10-20 night:
// "Hide, show on first page, show on every page"): eight features laid out on
// several pages (a wide gap), then Hide | First page | Every page. Every
// preview page is read for the bar the core drew into it (its caption is an
// SVG <text>, the 4 in label another), never for the row's own state alone;
// the core's page count comes from CPython's web_api.sheet on the dialog's
// own request.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, labelOn, openStudio, state } from "./helpers";

const ROOT = path.resolve(import.meta.dirname, "..", "..");
const PY = [path.join(ROOT, ".venv", "bin", "python"), path.join(ROOT, ".venv", "Scripts", "python.exe")].find((p) => fs.existsSync(p));
const GAP = 60;                     // mm: eight stickers cannot share one page
const NOTE = "No scale bar: measure a marker to check the print is at 100 %";

// the eight rectangles of sheet.spec.ts
const RECTS: [[number, number], [number, number]][] = [
  [[-100, -45], [-60, -20]], [[-50, -45], [-10, -15]], [[0, -45], [35, -10]], [[45, -45], [85, -20]],
  [[-100, 10], [-60, 40]], [[-50, 5], [-15, 40]], [[-5, 10], [35, 35]], [[45, 10], [85, 40]],
];

async function feature(page: Page, a: [number, number], b: [number, number]): Promise<void> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  expect((await state(page)).sel?.kind, `the rectangle from ${a} to ${b}`).toBe("shape");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await labelOn(page);
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
}

/** CPython's web_api.sheet on the same request: the core's own page count. */
function corePages(request: Record<string, unknown>): number {
  expect(PY, "the repo's .venv python").toBeTruthy();
  const code = "import json, sys\nfrom aruco_studio import web_api\nsys.stdout.write(web_api.call('sheet', sys.stdin.read()))";
  const r = spawnSync(PY!, ["-c", code], { cwd: ROOT, input: JSON.stringify({ ...request, date: "2026-10-20" }), encoding: "utf8",
    maxBuffer: 1 << 28, env: { ...process.env, PYTHONPATH: ROOT, PYTHONDONTWRITEBYTECODE: "1" } });
  expect(r.status, r.stderr).toBe(0);
  const out = JSON.parse(r.stdout);
  expect(out.error).toBeUndefined();
  return out.result.pages;
}

async function settled(page: Page): Promise<Record<string, unknown>> {
  await idle(page);
  await expect(page.locator(".sheet-body")).toHaveAttribute("data-busy", "0");
  return JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!);
}

/** What the page on screen carries: the bar's caption and the 4 in label as SVG text (the core's), and the screen's 50 mm bar. */
async function bar(page: Page): Promise<{ page: number; core: boolean; inch: boolean; screen: boolean }> {
  const stage = page.getByTestId("print-page");
  return {
    page: Number(await stage.getAttribute("data-page")),
    core: (await stage.locator("svg text", { hasText: "must measure 100 mm" }).count()) > 0,
    inch: (await stage.locator("svg text", { hasText: /^4 in$/ }).count()) > 0,
    screen: (await page.getByTestId("scale-bar").count()) > 0,
  };
}

test.describe(`the Scale bar row (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core draws no page: the bar is the real core's");

  test("Hide | First page | Every page on a multi-page sheet: the bar is on the pages it says, and only those", async ({ page }) => {
    test.setTimeout(240_000);
    await openStudio(page);
    await coreReady(page);
    await page.getByTestId("menu-file").click();
    await page.getByTestId("cmd-new").click();
    for (const [a, b] of RECTS) await feature(page, a, b);
    expect((await state(page)).doc.features).toHaveLength(8);
    await page.getByTestId("act-print").click();
    await expect(page.getByTestId("print-dialog")).toBeVisible();
    await expect(page.locator('[data-testid="print-page"] svg')).toBeVisible({ timeout: 45_000 });
    const gap = page.locator('[data-testid="sheet-gap"] input');
    await gap.fill(String(GAP));
    await gap.press("Enter");

    // the default is First page, next to the other layout options
    const row = page.getByTestId("sheet-scale-bar");
    await expect(row).toHaveAttribute("data-value", "first");
    await expect(row.locator("[data-value]")).toHaveText(["Hide", "First page", "Every page"]);
    await expect(page.getByTestId("sheet-layout").getByTestId("sheet-scale-bar")).toBeVisible();

    const want = { hide: () => false, first: (i: number) => i === 1, every: () => true } as const;
    for (const option of ["every", "first", "hide"] as const) {
      await row.locator(`[data-value="${option}"]`).click();
      await expect(row).toHaveAttribute("data-value", option);
      const request = await settled(page);
      expect(request.scale_bar, "the request says so").toBe(option);
      const pages = Number(await page.getByTestId("sheet-pages").getAttribute("data-value"));
      expect(pages, `${option}: the core's page count`).toBe(corePages(request));
      expect(pages, `${option}: a multi-page sheet`).toBeGreaterThan(1);
      await expect(page.getByTestId("sheet-page-tab")).toHaveCount(pages);
      for (let i = 1; i <= pages; i++) {
        await page.getByTestId("sheet-page-tab").nth(i - 1).click();
        await expect(page.getByTestId("print-page")).toHaveAttribute("data-page", String(i));
        const got = await bar(page);
        const on = want[option](i);
        expect(got, `${option}: page ${i} of ${pages}`).toEqual({ page: i, core: on, inch: on, screen: on });
      }
      // the info issue only under Hide
      await expect(page.getByText(NOTE)).toHaveCount(option === "hide" ? 1 : 0);
    }

    // back to Every page: the page tabs and the request follow
    await row.locator('[data-value="every"]').click();
    expect((await settled(page)).scale_bar).toBe("every");
  });
});
