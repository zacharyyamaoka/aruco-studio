// Shared steps for the online Studio's e2e. Numbers come from the page's
// probe (window.__aruco, web/src/probe.ts) and from what is drawn
// (getBoundingClientRect), never from DOM presence alone.
import { expect, type Locator, type Page } from "@playwright/test";

/** E2E_CORE=mock runs on the mock core; the default is the real one. */
export const CORE: "real" | "mock" = process.env.E2E_CORE === "mock" ? "mock" : "real";

export interface Rect { cx: number; cy: number; w: number; h: number; angle_deg: number }
export interface Shape { kind: "rect" | "circle" | "poly"; id: string; cx?: number; cy?: number; w?: number; h?: number; r?: number }

export async function openStudio(page: Page): Promise<void> {
  await page.goto(CORE === "mock" ? "/?core=mock" : "/");
  await expect(page.getByTestId("app")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).__aruco?.kind)).toBe(CORE);
}

/** The core is up (the probe's status: the chrome has no core chip since the
 *  Figma layout, Zach 2026-10-20 night), and nothing is in flight. */
// WHY ?.: after a page Reload the probe is installed a moment after the
// document; polling must wait for it, not throw (seen on the live site)
export async function coreReady(page: Page): Promise<void> {
  await expect.poll(() => page.evaluate(() => (window as any).__aruco?.state().core.state ?? null), { timeout: 60_000, message: "the core is ready" }).toBe("ready");
  await idle(page);
}

/** The presets dialog: from the panel's Preset row when the panel is open
 *  (this marker's preset), else Edit › Presets… (the one new markers start with). */
export async function openPresets(page: Page): Promise<Locator> {
  if (await page.getByTestId("extrude-panel").count()) {
    // the Preset row is on Make (a reopened panel keeps the tab it last had)
    if (!(await page.getByTestId("panel-preset").count())) await panelTab(page, "make");
    await page.getByTestId("panel-preset").click();
  } else {
    await openMenu(page, "edit");
    await page.getByTestId("cmd-presets").click();
  }
  const modal = page.getByTestId("presets-modal");
  await expect(modal).toBeVisible();
  return modal;
}

/** The main menu (the logo with ⌄, top left, Figma UI3's): open it, then its
 *  `sub` submenu (File, Edit, Export, View, Preferences, Help), the pointer
 *  moved onto it as a hand moves it. WHY the mouse, not locator.hover(): the
 *  open submenu marks its parent inert for Playwright's actionability check,
 *  while a real pointer moves from one submenu to the next. */
export async function openMenu(page: Page, sub: "file" | "edit" | "export" | "view" | "prefs" | "help"): Promise<Locator> {
  if (!(await page.getByTestId("main-menu").isVisible())) await page.getByTestId("menu-main").click();
  await expect(page.getByTestId("main-menu")).toBeVisible();
  // on a phone the submenus are groups in the menu itself: no trigger to move onto
  const trigger = page.getByTestId(`menu-${sub}`);
  if (await trigger.count()) {
    const r = (await trigger.boundingBox())!;
    await page.mouse.move(r.x + r.width / 2, r.y + r.height / 2, { steps: 3 });
  }
  const popup = page.getByTestId(`menu-${sub}-popup`);
  await expect(popup).toBeVisible();
  return popup;
}

/** Open the document's ⌄ menu (the cloud file and the account; on a phone also Download for CAD), run `fn`, close it. */
export async function inDocMenu(page: Page, fn: (menu: Locator) => Promise<void>): Promise<void> {
  const menu = page.getByTestId("doc-menu");
  if (!(await menu.count())) await page.getByTestId("menu-doc").click();
  await expect(menu).toBeVisible();
  await fn(menu);
  if (await menu.count()) await page.getByTestId("menu-doc").click();
  await expect(menu).toHaveCount(0);
}

/** Preferences › Theme: the other one (it was a toggle in the old top bar). */
export async function toggleTheme(page: Page): Promise<void> {
  const dark = (await page.locator("html").getAttribute("data-theme")) === "dark";
  await openMenu(page, "prefs");
  await page.getByTestId(dark ? "theme-light" : "theme-dark").click();
  await expect(page.getByTestId("main-menu")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("data-theme", dark ? "light" : "dark");
}

/** Preferences › Skin. */
export async function pickSkin(page: Page, id: "studio" | "unstyled" | "fusion" | "onshape"): Promise<void> {
  await openMenu(page, "prefs");
  await page.getByTestId(`skin-${id}`).click();
  await expect(page.getByTestId("main-menu")).toHaveCount(0);
  await expect(page.locator("html")).toHaveAttribute("data-skin", id);
}

export async function idle(page: Page): Promise<void> {
  await page.evaluate(() => (window as any).__aruco.idle(45_000));
}

export async function state(page: Page): Promise<any> {
  return page.evaluate(() => JSON.parse(JSON.stringify((window as any).__aruco.state())));
}

export async function loadExample(page: Page, id: string): Promise<void> {
  await openMenu(page, "file");
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
