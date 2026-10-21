// The Figma layout (V2 "Figma · Corner pills", Zach's pick 2026-10-20 night;
// reports/media/studio-layout-proposals-2026-10-20.html) and the preset per
// marker. Every place is measured (getBoundingClientRect), every preset read
// from the probe and the plans the core answered. Screenshots (1280 × 800 and
// 390 × 844) go to LAYOUT_SHOTS (default test-results/layout).
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, dragWorld, idle, openPresets, openStudio, panelTab, pickSkin, state, toClient, toggleTheme, openMenu } from "./helpers";

const SHOTS = process.env.LAYOUT_SHOTS ?? "test-results/layout";
const FIXTURE_V3 = path.join(import.meta.dirname, "fixtures", "v3-a4.arucostudio-web.json");
const GITHUB = "https://github.com/zacharyyamaoka/aruco-studio";
const ZIP = "**/py/aruco_studio.zip";
/** the chrome's own boxes, and the controls in them */
const CHROME = ["doc-pill", "actions-pill", "toolbar", "corner"];
const CONTROLS = ["menu-main", "menu-doc", "menu-cad", "act-verify", "act-print",
  "tool-select", "tool-rect", "tool-circle", "tool-dim", "tool-extrude", "tool-fit", "view-toggle", "help", "github"];

type R = { x: number; y: number; w: number; h: number };
const box = async (l: Locator): Promise<R> => l.evaluate((e) => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; });
const meet = (a: R, b: R) => a.x < b.x + b.w - 0.5 && b.x < a.x + a.w - 0.5 && a.y < b.y + b.h - 0.5 && b.y < a.y + a.h - 0.5;
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`) });

/** The visible ones of these test ids, with their boxes. */
async function visible(page: Page, ids: string[]): Promise<{ id: string; r: R }[]> {
  return page.evaluate((list) => list.flatMap((id) => {
    const e = document.querySelector(`[data-testid="${id}"]`);
    if (!e) return [];
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden" ? [{ id, r: { x: r.x, y: r.y, w: r.width, h: r.height } }] : [];
  }), ids);
}

/** Every pair of boxes that meet (none may). */
function overlaps(items: { id: string; r: R }[]): string[] {
  const out: string[] = [];
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) if (meet(items[i].r, items[j].r)) out.push(`${items[i].id} × ${items[j].id}`);
  return out;
}

/** The text of the chrome (the pills, the dock, the corner). */
const chromeText = (page: Page) => page.evaluate((ids) => ids.map((id) => (document.querySelector(`[data-testid="${id}"]`) as HTMLElement | null)?.innerText ?? "").join(" | "), CHROME);

/** A marker's panel: a click on its marker. */
async function inspect(page: Page, fid: string): Promise<void> {
  const b = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await expect.poll(async () => (await state(page)).panel.featureId).toBe(fid);
  await idle(page);
}

/** The open marker's preset, by the card's name: the panel's Preset row, Use, OK. */
async function presetOf(page: Page, name: RegExp): Promise<string> {
  const modal = await openPresets(page);
  await expect(page.getByTestId("presets-target")).not.toHaveAttribute("data-target", "new");
  await modal.locator('[data-coll="builtin"]').click();
  const card = modal.locator(".card[data-card]").filter({ has: page.locator(".name", { hasText: name }) }).first();
  const id = (await card.getAttribute("data-card"))!;
  await card.click();
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
  return id;
}

/** A rectangle (mm corners) and A in it: a new marker, its panel open. Returns its id. */
async function markerIn(page: Page, a: [number, number], b: [number, number]): Promise<string> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  return (await state(page)).panel.featureId;
}

const ok = async (page: Page) => {
  await page.getByTestId("panel-ok").click();
  await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
  await idle(page);
};

/** File › Open the v3 fixture (two markers on the A4 inkjet preset). */
async function openV3(page: Page): Promise<void> {
  await openMenu(page, "file");
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
  await chooser.setFiles(FIXTURE_V3);
  await expect(page.getByTestId("note")).toContainText("Opened v3-a4");
  await idle(page);
  await expect.poll(async () => Object.keys((await state(page)).plans).sort()).toEqual(["f1", "f2"]);
}

test.describe(`the Figma layout (${CORE} core)`, () => {
  test("a · Verify sits directly left of Print at the top right, neither with a key badge; the tooltips name K and S, and the keys work", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const verify = page.getByTestId("act-verify"), print = page.getByTestId("act-print");
    const v = await box(verify), p = await box(print);
    const vw = page.viewportSize()!.width;
    // top right: Print ends the row, Verify just before it, on one line
    expect(vw - (p.x + p.w), "Print at the right edge").toBeLessThanOrEqual(32);
    expect(p.y, "at the top").toBeLessThan(80);
    expect(v.x + v.w, "Verify ends before Print starts").toBeLessThanOrEqual(p.x + 0.5);
    expect(p.x - (v.x + v.w), "and right beside it").toBeLessThanOrEqual(12);
    expect(Math.abs(v.y + v.h / 2 - (p.y + p.h / 2)), "one row").toBeLessThanOrEqual(1);
    // nothing else in the pill sits between them
    const between = await page.getByTestId("actions-pill").evaluate((pill, [vr, pr]) => [...pill.querySelectorAll("button, a")]
      .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.x >= vr && r.x + r.width <= pr; }).length, [v.x + v.w, p.x]);
    expect(between).toBe(0);
    // the words only: no key badge
    await expect(verify).toHaveText("Verify");
    await expect(print).toHaveText("Print");
    for (const b of [verify, print]) await expect(b.locator(".kit-kbd, kbd, .tb-key, [data-badge], .lp-kbd")).toHaveCount(0);
    await expect(verify).toHaveAttribute("title", /\(K\)$/);
    await expect(print).toHaveAttribute("title", /\(S\)$/);
    // the keys still open them (a marker first, so Print has something to print)
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await ok(page);
    await page.mouse.move(640, 790);
    await page.keyboard.press("k");
    await expect.poll(async () => (await state(page)).modal).toBe("verify");
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await state(page)).modal).toBeNull();
    await page.keyboard.press("s");
    await expect.poll(async () => (await state(page)).modal).toBe("print");
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await state(page)).modal).toBeNull();
  });

  test("b · no core-status chip in the chrome, while the core loads and when it is ready", async ({ page }) => {
    let release: () => void = () => {};
    if (CORE === "real") {
      const held = new Promise<void>((r) => { release = r; });
      await page.route(ZIP, async (route) => { await held; await route.continue(); });
    }
    await openStudio(page);
    const noChip = async (when: string) => {
      await expect(page.getByTestId("core-chip"), when).toHaveCount(0);
      expect(await chromeText(page), `${when}: the chrome names no backend`).not.toMatch(/python|core|pyodide|loading|starting|ready/i);
      expect(await page.locator(".chip-core, [data-testid=core-status]").count(), `${when}: no status in the chrome`).toBe(0);
    };
    if (CORE === "real") {
      await expect.poll(async () => (await state(page)).core.state).toBe("loading");
      await page.waitForTimeout(3500);   // past the seconds' threshold
      await noChip("loading");
      await shot(page, "b-loading");
      release();
    }
    await coreReady(page);
    await noChip("ready");
  });

  test("c · ? and GitHub sit in the bottom corner; GitHub links to the repo; ? lists the keys", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const { width: W, height: H } = page.viewportSize()!;
    const help = await box(page.getByTestId("help")), gh = await box(page.getByTestId("github"));
    for (const [name, r] of [["?", help], ["GitHub", gh]] as const) {
      expect(H - (r.y + r.h), `${name}: at the bottom`).toBeLessThanOrEqual(24);
      expect(Math.min(r.x, W - (r.x + r.w)), `${name}: in a corner`).toBeLessThanOrEqual(64);
    }
    expect(Math.abs(help.y - gh.y), "side by side").toBeLessThanOrEqual(1);
    expect(meet(help, gh)).toBe(false);
    // clear of the dock
    expect(meet(help, await box(page.getByTestId("toolbar")))).toBe(false);
    await expect(page.getByTestId("github")).toHaveAttribute("href", GITHUB);
    await expect(page.getByTestId("github")).toHaveAttribute("target", "_blank");
    await expect(page.getByTestId("github").locator(".kit-kbd, kbd")).toHaveCount(0);
    // ?: the keys, one row each, and the status at its foot
    await page.getByTestId("help").click();
    const pop = page.getByTestId("help-popover");
    await expect(pop).toBeVisible();
    for (const k of ["V", "R", "C", "D", "A", "S", "K", "F", "3", "Ctrl+Z", "Ctrl+Shift+Z", "Ctrl+C", "Ctrl+X", "Ctrl+V", "Del", "Esc"]) {
      await expect(pop.locator(`[data-key="${k}"]`).first(), `the key ${k}`).toBeVisible();
    }
    await expect(page.getByTestId("core-status")).toHaveText(/^Ready in \d+\.\d s$/);
    await shot(page, "c-help");
    await page.getByTestId("help").click();
    await expect(pop).toHaveCount(0);
  });

  test("d · the document pill: the logo (the main menu), the name with ⌄ -- and no preset", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const pill = page.getByTestId("doc-pill");
    const s = await state(page);
    const text = await pill.innerText();
    expect(text.replace(/\s+/g, " ").trim()).toBe(s.doc.name);
    expect(text).not.toContain(s.doc.default_preset.name);
    expect(text).not.toMatch(/inkjet|vinyl|letter|a4|preset|print3d|3d print/i);
    await expect(pill.locator("[data-testid=preset-chip], .chip-preset")).toHaveCount(0);
    await expect((await openMenu(page, "account")).getByTestId("brand")).toHaveAttribute("href", /\/about\/$/);
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("main-menu")).toHaveCount(0);
    // the top-left corner, under the rulers
    const r = await box(pill);
    expect(r.x).toBeLessThanOrEqual(16);
    expect(r.y).toBeGreaterThanOrEqual(18);
    expect(r.y).toBeLessThan(40);
    // Theme and Skin are Preferences ›; ⌄ is the file's, no preset there either
    const prefs = await openMenu(page, "prefs");
    await expect(prefs.getByTestId("theme-dark")).toBeVisible();
    await expect(prefs.getByTestId("skin-fusion")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await page.getByTestId("menu-doc").click();
    const menu = page.getByTestId("doc-menu");
    await expect(menu.getByTestId("theme-dark")).toHaveCount(0);
    expect(await menu.innerText()).not.toMatch(/preset|inkjet|vinyl/i);
    await page.getByTestId("menu-doc").click();
    await expect(menu).toHaveCount(0);
  });

  test("e · two markers, two presets: each plans with its own, the Make tab shows its own, a new marker starts with the last picked", async ({ page }) => {
    test.skip(CORE === "mock", "the method comes from the real core's MarkerPlan.extrude");
    await openStudio(page);
    await coreReady(page);
    await openMenu(page, "file");
    await page.getByTestId("cmd-new").click();
    const ink = (await state(page)).doc.default_preset;
    expect(ink.method).toBe("inkjet");
    // marker 1: the default (inkjet)
    const f1 = await markerIn(page, [0, 10], [30, 40]);
    expect((await state(page)).feature.preset.id).toBe(ink.id);
    await ok(page);
    // marker 2: starts inkjet, then the 3D Default on it
    const f2 = await markerIn(page, [45, 10], [75, 40]);
    expect((await state(page)).feature.preset.id, "a new marker starts with the last picked").toBe(ink.id);
    const fdm = await presetOf(page, /^Default$/);
    await expect(page.getByTestId("panel-preset")).toContainText("Default");
    await ok(page);
    let s = await state(page);
    expect(s.doc.features.find((f: any) => f.id === f1).preset.id).toBe(ink.id);
    expect(s.doc.features.find((f: any) => f.id === f2).preset.id).toBe(fdm);
    // each plans with its own: the core's answer says the method
    await expect.poll(async () => (await state(page)).plans[f2]?.extrude?.method).toBe("print3d");
    s = await state(page);
    expect(s.plans[f1].extrude.method).toBe("inkjet");
    expect(s.plans[f2].extrude.method).toBe("print3d");
    // the Make tab shows each one's own
    await inspect(page, f1);
    await expect(page.getByTestId("panel-preset")).toContainText(ink.name);
    await expect(page.getByTestId("preset-lines")).toContainText("Inkjet");
    await expect(page.locator('[data-row="extrude.paper_mm"]')).toBeVisible();
    await ok(page);
    await inspect(page, f2);
    await expect(page.getByTestId("panel-preset")).toContainText("Default");
    await expect(page.getByTestId("preset-lines")).toContainText("3D print");
    await expect(page.locator('[data-row="extrude.white_mm"]')).toBeVisible();
    await ok(page);
    // a new marker starts with the last picked: the 3D Default
    expect((await state(page)).doc.default_preset.id).toBe(fdm);
    const f3 = await markerIn(page, [90, 10], [120, 40]);
    expect((await state(page)).feature.preset.id).toBe(fdm);
    await expect(page.getByTestId("panel-preset")).toContainText("Default");
    await expect.poll(async () => (await state(page)).plans[f3]?.extrude?.method).toBe("print3d");
    // Cancel puts the document back, the default with it
    await page.getByTestId("panel-cancel").click();
    expect((await state(page)).doc.features.map((f: any) => f.id)).toEqual([f1, f2]);
    // copy / paste carries the preset
    await inspect(page, f2);
    await ok(page);
    await page.keyboard.press("Control+c");
    await page.keyboard.press("Control+v");
    await idle(page);
    s = await state(page);
    expect(s.doc.features).toHaveLength(3);
    expect(s.doc.features[2].preset.id, "the pasted marker keeps its preset").toBe(fdm);
  });

  test("f · an old v3 file opens with the file's preset on every marker", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await openV3(page);
    const s = await state(page);
    expect(s.doc.version).toBe(4);
    expect(s.doc.preset).toBeUndefined();
    expect(s.doc.features.map((f: any) => f.preset.id)).toEqual(["builtin:inkjet-a4-vinyl", "builtin:inkjet-a4-vinyl"]);
    expect(s.doc.default_preset.id).toBe("builtin:inkjet-a4-vinyl");
    await inspect(page, "f2");
    await panelTab(page, "make");
    await expect(page.getByTestId("panel-preset")).toContainText("A4 vinyl");
    const req = await page.evaluate(() => (window as any).__aruco.state().feature.preset.page_mm);
    expect(req).toEqual([210, 297]);
  });

  test("g · Print with two inkjet presets shows two groups, each on its own page; a 3D marker is not on paper", async ({ page }) => {
    test.skip(CORE === "mock", "the pages are the real core's");
    await openStudio(page);
    await coreReady(page);
    await openV3(page);
    // f2 on Letter: two inkjet presets
    await inspect(page, "f2");
    const letter = await presetOf(page, /Letter/);
    await ok(page);
    // and one 3D-printed marker
    await markerIn(page, [124, 4], [136, 16]);
    await presetOf(page, /^Default$/);
    await ok(page);
    await page.mouse.move(640, 790);
    await page.keyboard.press("s");
    const dlg = page.getByTestId("print-dialog");
    await expect(dlg).toBeVisible();
    const groups = page.getByTestId("sheet-group");
    await expect(groups).toHaveCount(2);
    expect(await groups.evaluateAll((els) => els.map((e) => e.getAttribute("data-sheet-group")))).toEqual(["builtin:inkjet-a4-vinyl", letter]);
    await expect(page.getByTestId("sheet-3d-note")).toHaveText("1 marker is 3D printed: it isn't on the paper sheet.");
    // each group on its preset's page: A4, then Letter
    const pageMm = () => page.getByTestId("print-page").getAttribute("data-page-mm");
    await groups.nth(0).click();
    await expect(page.getByTestId("print-page")).toBeVisible({ timeout: 45_000 });
    await expect.poll(pageMm).toBe("210x297");
    await expect(dlg).toContainText("Sheet · Inkjet · A4 vinyl");
    const a4req = JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!);
    expect(a4req.items.map((i: any) => i.preset.id)).toEqual(["builtin:inkjet-a4-vinyl"]);
    await shot(page, "g-print-two-groups");
    await groups.nth(1).click();
    await expect.poll(pageMm).toBe("215.9x279.4");
    await expect(groups.nth(1)).toHaveAttribute("aria-selected", "true");
    const lreq = JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!);
    expect(lreq.items.map((i: any) => i.preset.id)).toEqual([letter]);
  });

  test("h · 390 px wide: no chrome control meets another, no horizontal scroll; the dock rides above the docked panel", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openStudio(page);
    await coreReady(page);
    const noScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.body.scrollWidth <= window.innerWidth);
    const check = async (when: string) => {
      const boxes = await visible(page, CHROME);
      expect(boxes.map((b) => b.id).sort(), `${when}: the pills and the dock show`).toEqual(["actions-pill", "doc-pill", "toolbar"]);
      expect(overlaps(boxes), `${when}: the chrome's boxes`).toEqual([]);
      const controls = await visible(page, CONTROLS);
      expect(controls.length, `${when}: the controls left on screen`).toBeGreaterThanOrEqual(10);
      expect(overlaps(controls), `${when}: the controls`).toEqual([]);
      for (const c of [...boxes, ...controls]) {
        expect(c.r.x, `${when}: ${c.id} on screen`).toBeGreaterThanOrEqual(0);
        expect(c.r.x + c.r.w, `${when}: ${c.id} on screen`).toBeLessThanOrEqual(390);
      }
      expect(await noScroll(), `${when}: no horizontal scroll`).toBe(true);
    };
    await check("no panel");
    await shot(page, "h-390");
    // the panel docked: the dock above it
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await check("panel docked");
    const panel = await box(page.getByTestId("extrude-panel")), dock = await box(page.getByTestId("toolbar"));
    expect(dock.y + dock.h).toBeLessThanOrEqual(panel.y);
    await shot(page, "h-390-panel");
    // what folded away: Download for CAD in ⌄; the rest is the main menu's, as on a desk
    await page.getByTestId("menu-doc").click();
    const menu = page.getByTestId("doc-menu");
    await expect(menu.getByTestId("cad-fusion")).toBeVisible();
    const m = await box(menu);
    expect(m.x + m.w).toBeLessThanOrEqual(390);
    await shot(page, "h-390-menu");
    await page.getByTestId("menu-doc").click();
    await expect(menu).toHaveCount(0);
    for (const [sub, ids] of [["file", ["cmd-examples"]], ["edit", ["cmd-reid", "cmd-presets"]], ["export", ["cmd-print"]], ["prefs", ["theme-dark", "skin-studio"]], ["account", ["github-menu", "help-menu"]]] as const) {
      const popup = await openMenu(page, sub);
      for (const id of ids) await expect(popup.getByTestId(id), id).toBeVisible();
      const r = await box(popup);
      expect(r.x + r.w, `${sub} on screen`).toBeLessThanOrEqual(390);
      expect(r.x, `${sub} on screen`).toBeGreaterThanOrEqual(0);
    }
    await expect(page.getByTestId("github-menu")).toHaveAttribute("href", GITHUB);
    await page.getByTestId("help-menu").click();
    await expect(page.getByTestId("help-dialog")).toBeVisible();
    await expect(page.getByTestId("core-status")).toHaveText(/^Ready in/);
  });

  test("i · the screenshots: the whole app (Studio light, Studio dark), with a marker's panel open", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await page.mouse.move(640, 400);
    await page.waitForTimeout(200);
    await shot(page, "i-desk-light");
    await toggleTheme(page);
    await pickSkin(page, "studio");
    await page.mouse.move(640, 400);
    await page.waitForTimeout(200);
    await shot(page, "i-desk-dark");
    // the chrome measured in both: nothing meets at 1280 either
    expect(overlaps(await visible(page, CHROME))).toEqual([]);
    expect(overlaps(await visible(page, CONTROLS))).toEqual([]);
    const top = await box(page.getByTestId("actions-pill"));
    const pnl = await box(page.getByTestId("extrude-panel"));
    expect(meet(top, pnl), "the panel opens clear of the top-right pill").toBe(false);
    await toggleTheme(page);
  });

  // WHY (2026-10-20 night): the panel used to keep only the ruler's 26 px
  // clear, so a marker at the very top opened its panel under the Figma pills
  test("j · a marker at the very top opens its panel below the top pills, and a drag can't push it under them", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await openMenu(page, "file");
    await page.getByTestId("cmd-new").click();
    // the world y at client y 40 (just under the window's top edge): two samples of the linear map
    const [, ya] = await toClient(page, 0, 0), [, yb] = await toClient(page, 0, 10);
    const yTop = (40 - ya) / ((yb - ya) / 10);
    await page.keyboard.press("r");
    await dragWorld(page, [-15, yTop], [15, yTop - 20]);
    await page.keyboard.press("a");
    const panel = page.getByTestId("extrude-panel");
    await expect(panel).toBeVisible();
    await idle(page);
    const box = async (l: Locator) => l.evaluate((e) => { const r = e.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right }; });
    const pills = [await box(page.getByTestId("doc-pill")), await box(page.getByTestId("actions-pill"))];
    const lowest = Math.max(...pills.map((r) => r.bottom));
    await expect.poll(async () => (await box(panel)).top, { message: "the panel's top clears both pills" }).toBeGreaterThanOrEqual(lowest);
    // drag its title bar to the very top: it stops below the pills
    const head = panel.locator(".fpanel-head").first();
    const h = await box(head);
    await page.mouse.move((h.left + h.right) / 2, (h.top + h.bottom) / 2);
    await page.mouse.down();
    await page.mouse.move((h.left + h.right) / 2, 2, { steps: 8 });
    await page.mouse.up();
    expect((await box(panel)).top).toBeGreaterThanOrEqual(lowest);
  });
});
