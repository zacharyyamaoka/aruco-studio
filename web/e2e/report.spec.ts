// The review report's stills, taken from a running site (usually the live
// one) for docs/build_online_studio_report.py:
//
//   E2E_BASE_URL=https://arucostudio.com REPORT_SHOTS_DIR=/abs/dir npx playwright test --project=e2e e2e/report.spec.ts
//
// Skipped unless REPORT_SHOTS_DIR is set, so the normal e2e run is unchanged.
// PNGs at 2x pixel density (the builder scales the stills down and keeps
// the close-ups sharp). Each test checks the state it photographs, so a shot
// never shows a half-loaded page, and writes what it measured to facts.json.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { coreReady, clickAt, dragWorld, featureRect, idle, loadExample, openStudio, state, toClient } from "./helpers";

const DIR = process.env.REPORT_SHOTS_DIR ?? "";
const facts: Record<string, unknown> = {};

test.skip(!DIR, "REPORT_SHOTS_DIR is not set");
test.use({ deviceScaleFactor: 2 });

test.beforeAll(() => { if (DIR) mkdirSync(DIR, { recursive: true }); });
test.afterAll(() => {
  if (!DIR) return;
  // merged, so a partial run (-g) keeps what the other tests measured before
  const file = path.join(DIR, "facts.json");
  const before = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : {};
  writeFileSync(file, JSON.stringify({ ...before, ...facts }, null, 2));
});

async function calm(page: Page): Promise<void> {
  await page.mouse.move(2, 2); // no hover state in the picture
  await page.waitForTimeout(250);
}

async function shot(page: Page, name: string): Promise<void> {
  await calm(page);
  await page.screenshot({ path: path.join(DIR, `${name}.png`) });
}

async function closeUp(loc: Locator, name: string): Promise<void> {
  await loc.scrollIntoViewIfNeeded();
  await loc.screenshot({ path: path.join(DIR, `${name}.png`) });
}

/** A region of the sketch (mm, y up) as a clipped screenshot. The floating
 *  panel and the size box are hidden for it: the close-up is of the sketch. */
async function sketchClip(page: Page, name: string, x0: number, y0: number, x1: number, y1: number): Promise<void> {
  await calm(page);
  const over = '[data-testid="extrude-panel"], [data-testid="shape-dims"], [data-testid="toolbar"]';
  await page.evaluate((sel) => document.querySelectorAll<HTMLElement>(sel).forEach((e) => { e.style.visibility = "hidden"; }), over);
  const [ax, ay] = await toClient(page, x0, y1);
  const [bx, by] = await toClient(page, x1, y0);
  await page.screenshot({ path: path.join(DIR, `${name}.png`), clip: { x: ax, y: ay, width: bx - ax, height: by - ay } });
  await page.evaluate((sel) => document.querySelectorAll<HTMLElement>(sel).forEach((e) => { e.style.visibility = ""; }), over);
}

/** The union of some elements' boxes as a clipped screenshot. */
async function unionClip(page: Page, name: string, locs: Locator[], pad = 6): Promise<void> {
  await calm(page);
  const boxes = await Promise.all(locs.map(async (l) => (await l.boundingBox())!));
  const x0 = Math.min(...boxes.map((b) => b.x)) - pad, y0 = Math.min(...boxes.map((b) => b.y)) - pad;
  const x1 = Math.max(...boxes.map((b) => b.x + b.width)) + pad, y1 = Math.max(...boxes.map((b) => b.y + b.height)) + pad;
  await page.screenshot({ path: path.join(DIR, `${name}.png`), clip: { x: x0, y: y0, width: x1 - x0, height: y1 - y0 } });
}

/** Examples › Plate, click the face between the holes, A. */
async function plateWithMarker(page: Page): Promise<void> {
  await openStudio(page);
  const t0 = Date.now();
  await coreReady(page);
  (facts.core_ready_s as number[] | undefined) ?? (facts.core_ready_s = []);
  (facts.core_ready_s as number[]).push(+((Date.now() - t0) / 1000).toFixed(1));
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.locator("[data-marker-black]")).toBeVisible();
}

async function toGrid(page: Page): Promise<void> {
  await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
  await idle(page);
  await expect(page.getByTestId("suggestion").first()).toBeVisible();
}

test("1 · plate → face → A: the inscribed rectangle and the marker, panel open; holes Avoid vs Ignore", async ({ page }) => {
  await plateWithMarker(page);
  const r = await featureRect(page);
  const s = await state(page);
  facts.inscribed_avoid = { w: r.w, h: r.h, cx: r.cx, cy: r.cy };
  facts.plan_single = { summary: s.plan.summary, label: s.plan.label, origin: s.plan.origin };
  await shot(page, "01-plate-inscribed");
  await closeUp(page.getByTestId("extrude-panel"), "01b-panel");
  // the marker, its Joint Origin (x red, y green), the turn arc and the label
  await sketchClip(page, "01c-sketch-marker", 28, -14, 92, 86);
  await closeUp(page.getByTestId("timeline"), "01d-timeline");
  // Holes: Avoid (as inscribed) vs Ignore (the outer loop only)
  await sketchClip(page, "01e-holes-avoid", -6, -13, 126, 86);
  await page.locator('[data-path="holes"] [data-value="ignore"]').click();
  await idle(page);
  const ri = await featureRect(page);
  facts.inscribed_ignore = { w: ri.w, h: ri.h, cx: ri.cx, cy: ri.cy };
  expect(ri.w! * ri.h!).toBeGreaterThan(r.w! * r.h!);
  await sketchClip(page, "01f-holes-ignore", -6, -13, 126, 86);
});

test("2 · Grid, a typed big marker: drawn as typed, flagged red under the Marker row", async ({ page }) => {
  await plateWithMarker(page);
  await toGrid(page);
  const input = page.locator('input[data-path="marker.marker_mm"]');
  const typed = process.env.REPORT_TYPED_MM ?? "34";
  await input.fill(typed);
  await input.press("Enter");
  await idle(page);
  const issue = page.locator('[data-issues-for="marker.marker_mm"] [data-level="error"]');
  await expect(issue.first()).toBeVisible();
  const s = await state(page);
  expect(s.plan.overflow_mm).toBeGreaterThan(0);
  // the red outline is on screen, left of the panel
  const outline = (await page.locator("[data-marker-outline]").boundingBox())!;
  const vp = (await page.getByTestId("viewport").boundingBox())!;
  const panel = (await page.getByTestId("extrude-panel").boundingBox())!;
  expect(outline.x).toBeGreaterThan(vp.x);
  expect(outline.y).toBeGreaterThan(vp.y);
  expect(outline.x + outline.width).toBeLessThan(panel.x);
  facts.typed = {
    marker_mm: Number(typed), drawn_marker_mm: s.plan.marker_mm, overflow_mm: s.plan.overflow_mm,
    outer_mm: s.plan.outer_mm, issue: await issue.first().textContent(), summary: s.plan.summary,
  };
  await page.locator('[data-row="marker.marker_mm"]').scrollIntoViewIfNeeded();
  await shot(page, "02-typed-overflow");
  await closeUp(page.locator('[data-row="marker.marker_mm"]'), "02b-marker-row-issue");
  // the Marker fields of a grid: Type .. Columns × Rows (Separation is new)
  await page.locator('[data-row="marker.type"]').scrollIntoViewIfNeeded();
  await unionClip(page, "02c-grid-fields", [page.locator('[data-row="marker.type"]'), page.locator('[data-row="marker.cols"]')]);
});

test("3 · Suggest: the list with its reasons (Grid)", async ({ page }) => {
  await plateWithMarker(page);
  await toGrid(page);
  facts.suggestions = await page.evaluate(() => (window as any).__aruco.state().suggestions.map((x: any) => `${x.label} · ${x.reason}`));
  await page.locator('[data-row="marker.suggest"]').scrollIntoViewIfNeeded();
  await shot(page, "03-suggest");
  await closeUp(page.locator('[data-row="marker.suggest"]'), "03b-suggest-list");
  // the Marker fields of a grid on Auto: Type .. Columns × Rows (Separation is new)
  await page.locator('[data-row="marker.type"]').scrollIntoViewIfNeeded();
  await unionClip(page, "03c-grid-fields", [page.locator('[data-row="marker.type"]'), page.locator('[data-row="marker.cols"]')]);
});

test("4 · the presets modal", async ({ page }) => {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("preset-chip").click();
  const modal = page.getByTestId("presets-modal");
  await expect(modal).toBeVisible();
  await modal.locator('[data-coll="builtin"]').click();
  await expect(modal.locator(".card[data-card]").first()).toBeVisible();
  facts.builtin_presets = await modal.locator(".card[data-card] .name").allTextContents();
  await shot(page, "04-presets");
});

test("5 · the Print dialog: the preset's page at true scale, the label at the sketch's size", async ({ page }) => {
  await plateWithMarker(page);
  const label = (await state(page)).plan.label;
  await page.getByTestId("panel-ok").click();
  await page.getByTestId("menu-export").click();
  await page.getByTestId("cmd-print").click();
  const pg = page.getByTestId("print-page");
  await expect(pg).toBeVisible();
  await expect(pg.locator("svg").first()).toBeVisible();
  await idle(page);
  // the printed label's font size (mm, the page's own units) next to the sketch label's cap height
  const printed = await pg.locator("svg text").evaluateAll((ts, want) => ts
    .filter((t) => t.textContent === want).map((t) => Number(t.getAttribute("font-size"))), label?.text);
  facts.print = { page_mm: await pg.getAttribute("data-page-mm"), sketch_label_cap_mm: label?.height_mm, printed_label_font_mm: printed };
  await shot(page, "05-print");
  // the page's top-left 85 × 85 mm: the marker, its cut line and the label
  await calm(page);
  const b = (await pg.boundingBox())!;
  const [pw] = (await pg.getAttribute("data-page-mm"))!.split("x").map(Number);
  const k = b.width / pw;
  await page.screenshot({ path: path.join(DIR, "05b-print-label.png"), clip: { x: b.x, y: b.y, width: 85 * k, height: 85 * k } });
  await closeUp(page.getByTestId("scale-bar"), "05c-scale-bar");
});

test("6 · dark theme", async ({ page }) => {
  await plateWithMarker(page);
  await page.getByTestId("theme-toggle").click();
  await page.waitForTimeout(300);
  await shot(page, "06-dark");
});

test("7 · 390 × 844: the panel docks to the bottom; collapsed, the marker shows", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await plateWithMarker(page);
  const panel = (await page.getByTestId("extrude-panel").boundingBox())!;
  facts.mobile = {
    panel,
    no_hscroll: await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.body.scrollWidth <= window.innerWidth),
  };
  await shot(page, "07-mobile");
  await page.getByTestId("panel-collapse").click();
  await page.waitForTimeout(300);
  await shot(page, "07b-mobile-collapsed");
});

test("8 · draw a rectangle (R), A: no face, so Flip shows", async ({ page }) => {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-new").click();
  await page.keyboard.press("r");
  await dragWorld(page, [-30, -20], [30, 20]);
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.locator("[data-marker-black]")).toBeVisible();
  await expect(page.locator('[data-row="marker.flip"]')).toBeVisible();
  const s = await state(page);
  facts.drawn = { shapes: s.doc.shapes.map((x: any) => ({ kind: x.kind, w: x.w, h: x.h })), summary: s.plan.summary };
  await shot(page, "08-drawn");
});
