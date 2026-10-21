// Shared steps for the online Studio's e2e. Numbers come from the page's
// probe (window.__aruco, web/src/probe.ts) and from what is drawn
// (getBoundingClientRect), never from DOM presence alone.
import { expect, type Page } from "@playwright/test";

/** E2E_CORE=mock runs on the mock core; the default is the real one. */
export const CORE: "real" | "mock" = process.env.E2E_CORE === "mock" ? "mock" : "real";

export interface Rect { cx: number; cy: number; w: number; h: number; angle_deg: number }
export interface Shape { kind: "rect" | "circle" | "poly"; id: string; cx?: number; cy?: number; w?: number; h?: number; r?: number }

export async function openStudio(page: Page): Promise<void> {
  await page.goto(CORE === "mock" ? "/?core=mock" : "/");
  await expect(page.getByTestId("app")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).__aruco?.kind)).toBe(CORE);
}

export async function coreReady(page: Page): Promise<void> {
  await expect(page.getByTestId("core-chip")).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await idle(page);
}

export async function idle(page: Page): Promise<void> {
  await page.evaluate(() => (window as any).__aruco.idle(45_000));
}

export async function state(page: Page): Promise<any> {
  return page.evaluate(() => JSON.parse(JSON.stringify((window as any).__aruco.state())));
}

export async function loadExample(page: Page, id: string): Promise<void> {
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-examples").click();
  await page.locator(`[data-example="${id}"]`).click();
  await expect(page.getByTestId("examples-dialog")).toHaveCount(0);
}

export async function toClient(page: Page, x: number, y: number): Promise<[number, number]> {
  return page.evaluate(([a, b]) => (window as any).__aruco.toClient(a, b), [x, y]);
}

export async function clickAt(page: Page, x: number, y: number): Promise<void> {
  const [cx, cy] = await toClient(page, x, y);
  await page.mouse.click(cx, cy);
}

/** Drag on the sketch from one point to another (mm), in small steps. */
export async function dragWorld(page: Page, from: [number, number], to: [number, number], steps = 12, pause = 0): Promise<void> {
  const [ax, ay] = await toClient(page, ...from);
  const [bx, by] = await toClient(page, ...to);
  await page.mouse.move(ax, ay);
  await page.mouse.down();
  for (let i = 1; i <= steps; i++) {
    await page.mouse.move(ax + ((bx - ax) * i) / steps, ay + ((by - ay) * i) / steps);
    if (pause) await page.waitForTimeout(pause);
  }
  await page.mouse.up();
}

/** The box (mm) the core placed the marker of the feature in focus in (the
 *  probe's `plan.fit_rect`): the profile is the input, this is the answer. */
export async function fitRect(page: Page): Promise<Rect> {
  await expect.poll(async () => !!(await state(page)).plan?.fit_rect, { message: "the plan has a fit_rect" }).toBe(true);
  return (await state(page)).plan.fit_rect;
}

/** The rectangle shape (mm) that is the profile of the feature in focus (a
 *  rectangle profile: the custom placement). */
export async function profileRect(page: Page): Promise<Shape> {
  const s = await state(page);
  const ref = s.feature?.profile;
  expect(ref?.holes, "the feature's profile is a rectangle on its own").toEqual([]);
  const r = s.doc.shapes.find((x: Shape) => x.id === ref.outer);
  expect(r?.kind, "the feature's profile is a rectangle").toBe("rect");
  return r;
}

/** Double-click a sketch point (mm). */
export async function dblClickAt(page: Page, x: number, y: number): Promise<void> {
  const [cx, cy] = await toClient(page, x, y);
  await page.mouse.dblclick(cx, cy);
}

/** The plan's outline centre and size (mm), from its loop. */
export async function planOutline(page: Page): Promise<{ cx: number; cy: number; w: number; h: number }> {
  const s = await state(page);
  expect(s.plan, "a plan is drawn").toBeTruthy();
  const xs = s.plan.outer.map((p: number[]) => p[0]), ys = s.plan.outer.map((p: number[]) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: x1 - x0, h: y1 - y0 };
}

/** How far a circle's disc is from an axis-aligned rectangle (mm; 0 = touching or overlapping). */
export function circleGap(c: { cx: number; cy: number; r: number }, r: Rect): number {
  const dx = Math.max(Math.abs(c.cx - r.cx) - r.w / 2, 0), dy = Math.max(Math.abs(c.cy - r.cy) - r.h / 2, 0);
  return Math.hypot(dx, dy) - c.r;
}

/** A circle drawn as a disc (r) vs a rectangle: true when their areas overlap
 *  by more than a hair (tangent is fine: the core may place an edge on the rim). */
export function overlaps(c: { cx: number; cy: number; r: number }, r: Rect, eps = 1e-3): boolean {
  return circleGap(c, r) < -eps;
}

/** Open one of the ArUco Extrude panel's tabs (V1 Command Dialog, 2026-10-20
 *  night: Make | Marker | Label). A new feature opens on Make; a reopened one
 *  keeps the tab the panel last had. */
export async function panelTab(page: Page, tab: "make" | "marker" | "label"): Promise<void> {
  const t = page.locator(`[data-testid="extrude-panel"] [role=tab][data-tab="${tab}"]`);
  await t.click();
  await expect(page.locator(`[data-testid="extrude-panel"] [data-tab-body="${tab}"]`)).toBeVisible();
}

/** Turn the label of the feature in the panel on: the Label tab's On switch
 *  (a new feature's label is off since 2026-10-20 night: Zach, "Label by
 *  default should be off"). Leaves the panel on the Label tab. */
export async function labelOn(page: Page): Promise<void> {
  await panelTab(page, "label");
  if (!(await state(page)).feature.label.on) await page.locator('[data-testid="extrude-panel"] [data-path="label.on"]').click();
  await expect.poll(async () => (await state(page)).feature.label.on).toBe(true);
  await idle(page);
}
