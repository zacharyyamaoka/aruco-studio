// Hero videos for lane/os-margins-reid (2026-11-13), recorded from the real
// build (the "hero" project records 1280 × 800 video; a drawn cursor follows
// the mouse, since a headless recording has none):
//   a · ids: six rectangles drawn out of order, A on them all (0–5 in reading
//       order), the marker printing #1 deleted and a copy pasted (it takes the
//       released #1), then all six selected and First ID 100 (100–105).
//   b · print: Top margin typed, a keep-clear box drawn on page 1: the sheet
//       is laid out again round it.
//   E2E_PORT=5390 npx playwright test --project=hero idsprint-hero.spec.ts
// Playwright saves each video under test-results/<test>/video.webm; HERO_SHOTS=<dir>
// also saves the stills the report compares.
import { expect, test, type Locator, type Page } from "@playwright/test";
import { coreReady, dragWorld, idle, openMenu, openStudio, state, toClient } from "./helpers";

const BEAT = 700;
const SHOTS = process.env.HERO_SHOTS;
const DRAW: [number, number][] = [[20, -10], [-40, 20], [-10, -10], [20, 20], [-40, -10], [-10, 20]];
const SIDE = 16;

async function cursor(page: Page): Promise<void> {
  await page.addInitScript(() => {
    addEventListener("DOMContentLoaded", () => {
      const dot = document.createElement("div");
      dot.style.cssText = "position:fixed;z-index:99999;width:18px;height:18px;margin:-3px 0 0 -3px;pointer-events:none;left:-40px;top:-40px;"
        + "background:no-repeat url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M2 1l11 6-5 1.4 3 5-2 1.1-3-5L2 13z' fill='%23111' stroke='%23fff' stroke-width='1'/%3E%3C/svg%3E\");";
      document.body.appendChild(dot);
      addEventListener("mousemove", (e) => { dot.style.left = `${e.clientX}px`; dot.style.top = `${e.clientY}px`; }, true);
    });
  });
}

async function shot(page: Page, name: string): Promise<void> {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png` });
}

async function glideTo(page: Page, x: number, y: number): Promise<void> {
  await page.mouse.move(x, y, { steps: 14 });
}

async function glideClick(page: Page, loc: Locator): Promise<void> {
  const b = (await loc.boundingBox())!;
  await glideTo(page, b.x + b.width / 2, b.y + b.height / 2);
  await page.waitForTimeout(BEAT / 3);
  await loc.click();
}

async function rightDrag(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const [ax, ay] = await toClient(page, ...from);
  const [bx, by] = await toClient(page, ...to);
  await glideTo(page, ax, ay);
  await page.mouse.down({ button: "right" });
  for (let i = 1; i <= 16; i++) await page.mouse.move(ax + ((bx - ax) * i) / 16, ay + ((by - ay) * i) / 16);
  await page.mouse.up({ button: "right" });
}

async function sixMarkers(page: Page, slow: boolean): Promise<void> {
  for (const [x, y] of DRAW) {
    await page.keyboard.press("r");
    await dragWorld(page, [x - SIDE / 2, y - SIDE / 2], [x + SIDE / 2, y + SIDE / 2], slow ? 10 : 4, slow ? 12 : 0);
  }
  await page.keyboard.press("Escape");
  await rightDrag(page, [-60, 40], [40, -30]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  await page.waitForTimeout(BEAT);
  await glideClick(page, page.getByTestId("panel-ok"));
  await idle(page);
}

async function start(page: Page): Promise<void> {
  await cursor(page);
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
  // View › Marker info on: the ids under every marker, so the video shows them
  if (!(await state(page)).markerInfo) {
    await openMenu(page, "view");
    await page.getByTestId("cmd-marker-info").click();
  }
  await page.keyboard.press("Escape");
}

test("a · ids: reading order, a deleted marker's id released, First ID 100", async ({ page }) => {
  test.setTimeout(240_000);
  await start(page);
  await sixMarkers(page, true);
  await page.waitForTimeout(BEAT);
  await shot(page, "ids-1-reading-order");
  // delete the marker printing #1, paste a copy of #0 to the right: it takes #1
  const [mx, my] = await toClient(page, -10, 20);
  await glideTo(page, mx, my);
  await page.mouse.click(mx, my);
  await page.waitForTimeout(BEAT / 2);
  await page.keyboard.press("Delete");
  await idle(page);
  await page.waitForTimeout(BEAT);
  const [cx, cy] = await toClient(page, -40, 20);
  await glideTo(page, cx, cy);
  await page.mouse.click(cx, cy);
  await page.keyboard.press("Control+c");
  const [px, py] = await toClient(page, 50, 20);
  await glideTo(page, px, py);
  await page.keyboard.press("Control+v");
  await idle(page);
  await page.waitForTimeout(BEAT * 1.5);
  await shot(page, "ids-2-released");
  // all of them, A: the batch panel; First ID 100
  await page.keyboard.press("Escape");
  await rightDrag(page, [-60, 40], [70, -30]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("batch-first-id")).toBeVisible();
  await page.waitForTimeout(BEAT);
  const first = page.getByTestId("batch-first-id").locator("input");
  await glideClick(page, first);
  await first.fill("");
  await page.keyboard.type("100", { delay: 120 });
  await page.waitForTimeout(BEAT / 2);
  await first.press("Enter");
  await idle(page);
  await page.waitForTimeout(BEAT * 2);
  await shot(page, "ids-3-first-id-100");
  await glideClick(page, page.getByTestId("panel-ok"));
  await idle(page);
  await page.waitForTimeout(BEAT * 1.5);
});

test("b · print: Top margin 60, a keep-clear box drawn on page 1, the sheet laid out round it", async ({ page }) => {
  test.setTimeout(240_000);
  await start(page);
  await page.evaluate(() => { try { localStorage.removeItem("aruco-studio.print-clear.v1"); } catch { /* none */ } });
  await sixMarkers(page, false);
  // more stickers: Ctrl+D the six twice
  await page.keyboard.press("Escape");
  await rightDrag(page, [-60, 40], [40, -30]);
  await page.keyboard.press("Control+d");
  await idle(page);
  await page.keyboard.press("Escape");
  await glideClick(page, page.getByTestId("act-print"));
  await expect(page.getByTestId("print-dialog")).toBeVisible();
  await expect(page.locator('[data-testid="print-page"] svg').first()).toBeVisible({ timeout: 45_000 });
  await page.getByTestId("print-mode").locator('[data-value="fit"]').click();
  await idle(page);
  await page.waitForTimeout(BEAT * 1.5);
  await shot(page, "print-1-before");
  // Top 60 mm: printing starts lower, the sheet is laid out again
  const top = page.locator('[data-testid="sheet-margin-top"] input');
  await glideClick(page, top);
  await top.fill("");
  await page.keyboard.type("60", { delay: 140 });
  await top.press("Enter");
  await idle(page);
  await page.waitForTimeout(BEAT * 2);
  await shot(page, "print-2-top-60");
  // Draw box: drag where the sheet is already cut (page mm 20,70 → 110,150)
  await glideClick(page, page.getByTestId("keep-draw"));
  const layer = page.locator('[data-testid="keep-layer"][data-page="1"]').first();
  const r = (await layer.boundingBox())!;
  const [pw, ph] = (await page.getByTestId("print-page").first().getAttribute("data-page-mm"))!.split("x").map(Number);
  const at = (x: number, y: number) => [r.x + (x / pw) * r.width, r.y + (y / ph) * r.height] as const;
  const [ax, ay] = at(20, 70), [bx, by] = at(110, 150);
  await glideTo(page, ax, ay);
  await page.mouse.down();
  for (let i = 1; i <= 24; i++) { await page.mouse.move(ax + ((bx - ax) * i) / 24, ay + ((by - ay) * i) / 24); await page.waitForTimeout(25); }
  await page.mouse.up();
  await idle(page);
  await page.waitForTimeout(BEAT * 2.5);
  await shot(page, "print-3-keep-clear");
});
