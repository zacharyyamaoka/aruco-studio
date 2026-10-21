// The ArUco Extrude panel as V1 "Command Dialog" (Zach's pick, 2026-10-20
// night; the gallery is reports/media/panel-proposals-2026-10-20.html), in the
// skeleton's order (docs/design/panel_skeleton.md, 2026-10-21): three flat tabs
// Marker | Label | Make and nothing above them but the title bar; Marker opens
// with the Profile, then the Preset; Make holds Trim, the heights of the
// preset's method (contract barrier 10) and Flip; Corner mark is on Label; the
// presets are a three-pane library dialog. Every check measures the probe's numbers, what
// the core was sent, the drawn boxes (getBoundingClientRect) or the computed
// colours. Screenshots (1280 × 800) go to PANEL_SHOTS (default test-results/panel).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, dragWorld, idle, labelOn, loadExample, openStudio, pickSkin, state } from "./helpers";

const SHOTS = process.env.PANEL_SHOTS ?? "test-results/panel";

/** Every plan request the UI sent, newest last: the real core's from its
 *  worker's messages, the mock's from its own log. */
async function watchRequests(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const w = window as unknown as { __planReqs: unknown[] };
    w.__planReqs = [];
    const post = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (this: Worker, msg: unknown, ...rest: unknown[]) {
      const m = msg as { name?: string; payload?: unknown } | null;
      if (m && m.name === "plan") w.__planReqs.push(JSON.parse(JSON.stringify(m.payload)));
      return (post as (...a: unknown[]) => void).call(this, msg, ...rest);
    } as typeof Worker.prototype.postMessage;
  });
}

async function lastRequest(page: Page): Promise<any> {
  return page.evaluate(() => {
    const w = window as unknown as { __planReqs?: any[]; __mockPlanRequests?: any[] };
    const xs = (w.__mockPlanRequests?.length ? w.__mockPlanRequests : w.__planReqs) ?? [];
    return JSON.parse(JSON.stringify(xs[xs.length - 1] ?? null));
  });
}

/** Examples › Plate, click the face, A: a new feature, its panel open. */
async function platePanel(page: Page): Promise<string> {
  await watchRequests(page);
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  return (await state(page)).panel.featureId as string;
}

const tab = async (page: Page, t: string) => { await page.locator(`[role=tab][data-tab="${t}"]`).click(); await idle(page); };
const top = (page: Page, sel: string) => page.locator(sel).evaluate((e) => e.getBoundingClientRect().top);
const colour = (page: Page, p: string) => page.locator(`input[data-path="${p}"]`).evaluate((e) => getComputedStyle(e).color);

/** The presets dialog from the Preset row (on Marker): pick the first preset of a method, Select. */
async function usePreset(page: Page, method: "inkjet" | "print3d"): Promise<any> {
  await tab(page, "marker");
  await page.getByTestId("panel-preset").click();
  const modal = page.getByTestId("presets-modal");
  await modal.locator('[data-coll="builtin"]').click();
  const card = modal.locator(`[data-group="${method}"] .card[data-card]`).first();
  const id = await card.getAttribute("data-card");
  await card.click();
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
  const s = await state(page);
  // the marker the panel is open on is made by it, and a new marker starts with it
  expect(s.feature.preset.id).toBe(id);
  expect(s.doc.default_preset.id).toBe(id);
  return s.feature.preset;
}

/** Barrier 10's driven rule (the core's rule 1): whole layers of the preset,
 *  the white >= 1.8 mm and the black >= 0.5 mm; 2.0 / 0.6 without layers. */
function wholeLayers(p: any, min: number, none: number): number {
  const lay = p.layer_mm, first = p.first_layer_mm;
  return lay && first ? first + Math.max(0, Math.ceil((min - first) / lay - 1e-9)) * lay : none;
}

test.describe(`the panel, V1 Command Dialog (${CORE} core)`, () => {
  test("a · three tabs; a new feature opens on Marker: Profile, Preset first; Make: Trim, the heights, top to bottom; a reopened one keeps its tab", async ({ page }) => {
    const fid = await platePanel(page);
    const panel = page.getByTestId("extrude-panel");
    await expect(panel.locator("[role=tab]")).toHaveText(["Marker", "Label", "Make"]);
    expect(await panel.locator("[role=tab]").evaluateAll((els) => els.map((e) => e.getAttribute("data-tab")))).toEqual(["marker", "label", "make"]);
    expect((await state(page)).panel.tab).toBe("marker");
    await expect(panel.locator('[role=tab][data-tab="marker"]')).toHaveAttribute("aria-selected", "true");
    for (const [t, order] of [["marker", ["profile", "preset", "marker.type"]], ["make", ["trim", "extrude.paper_mm"]]] as const) {
      await tab(page, t);
      const ys: number[] = [];
      for (const r of order) {
        await expect(panel.locator(`[data-tab-body="${t}"] [data-row="${r}"]`), r).toBeVisible();
        ys.push(await top(page, `[data-tab-body="${t}"] [data-row="${r}"]`));
      }
      for (let i = 1; i < ys.length; i++) expect(ys[i], `${order[i]} below ${order[i - 1]}`).toBeGreaterThan(ys[i - 1]);
    }
    await page.screenshot({ path: path.join(SHOTS, "panel-inkjet-make.png") });

    // a reopened feature keeps the tab the panel last had
    await tab(page, "label");
    await page.getByTestId("panel-ok").click();
    await idle(page);
    const b = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
    await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
    await expect(panel).toBeVisible();
    expect((await state(page)).panel.tab).toBe("label");
    await expect(panel.locator('[data-tab-body="label"]')).toBeVisible();
    // and a new feature starts on Marker again
    await clickAt(page, -6, 40);
    await expect(panel).toHaveCount(0);
    await page.keyboard.press("r");
    await dragWorld(page, [130, 10], [160, 40]);
    await page.keyboard.press("a");
    await expect(panel).toBeVisible();
    await idle(page);
    expect((await state(page)).panel.tab).toBe("marker");
    await expect(panel.locator('[data-tab-body="marker"]')).toBeVisible();
  });

  test("b · inkjet shows only Paper thickness (grey, = the preset's); 3D shows Extrude, White and Black height; typed is set and sent, ↺ drives it, Ctrl+Z takes it back in one step", async ({ page }) => {
    await platePanel(page);
    await tab(page, "make");
    const make = page.locator('[data-tab-body="make"]');
    // inkjet: the one height, driven by the preset's thickness
    const ink = (await state(page)).feature.preset;
    expect(ink.method).toBe("inkjet");
    expect(await make.locator('[data-row^="extrude."]').evaluateAll((els) => els.map((e) => e.getAttribute("data-row")))).toEqual(["extrude.paper_mm"]);
    await expect(page.locator('[data-drv="extrude.paper_mm"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-reset="extrude.paper_mm"]')).toBeHidden();
    expect(Number(await page.locator('input[data-path="extrude.paper_mm"]').inputValue())).toBeCloseTo(ink.thickness_mm, 6);
    let s = await state(page);
    expect(s.plan.extrude).toMatchObject({ method: "inkjet", paper_mm: ink.thickness_mm });
    expect(s.plan.extrude.driven).toContain("paper_mm");
    const grey = await colour(page, "extrude.paper_mm");

    // 3D print: Extrude, White height, Black height (the note under it), no paper
    const fdm = await usePreset(page, "print3d");
    await tab(page, "make");
    expect(await make.locator('[data-row^="extrude."]').evaluateAll((els) => els.map((e) => e.getAttribute("data-row"))))
      .toEqual(["extrude.mode", "extrude.white_mm", "extrude.black_mm"]);
    await expect(page.getByTestId("black-from")).toHaveText("from the white's outer face");
    expect(await top(page, '[data-testid="black-from"]')).toBeGreaterThan(await top(page, '[data-row="extrude.black_mm"]'));
    s = await state(page);
    expect(s.plan.extrude.method).toBe("print3d");
    expect(s.plan.extrude.driven).toEqual(expect.arrayContaining(["mode", "white_mm", "black_mm"]));
    // the driven values are the plan's, and the plan's are the preset's whole layers
    const white = page.locator('input[data-path="extrude.white_mm"]'), black = page.locator('input[data-path="extrude.black_mm"]');
    expect(Number(await white.inputValue())).toBeCloseTo(s.plan.extrude.white_mm, 6);
    expect(Number(await black.inputValue())).toBeCloseTo(s.plan.extrude.black_mm, 6);
    expect(s.plan.extrude.white_mm).toBeCloseTo(wholeLayers(fdm, 1.8, 2.0), 6);
    expect(s.plan.extrude.black_mm).toBeCloseTo(wholeLayers(fdm, 0.5, 0.6), 6);
    // the face is a reference face: Auto is black only, lit grey
    await expect(page.locator('[data-drv="extrude.mode"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-path="extrude.mode"]')).toHaveAttribute("data-value", s.plan.extrude.mode);
    expect(s.plan.extrude.mode).toBe("black");
    await page.screenshot({ path: path.join(SHOTS, "panel-print3d-make.png") });

    // type a white height: set (normal text, ↺), in the request and the plan
    await white.fill("2.4");
    await white.press("Enter");
    await idle(page);
    await expect(page.locator('[data-drv="extrude.white_mm"]')).toHaveAttribute("data-driven", "0");
    await expect(page.locator('[data-reset="extrude.white_mm"]')).toBeVisible();
    expect(await colour(page, "extrude.white_mm")).not.toBe(grey);
    s = await state(page);
    expect(s.feature.extrude).toEqual({ white_mm: 2.4 });
    expect((await lastRequest(page)).extrude).toEqual({ white_mm: 2.4 });
    expect(s.plan.extrude.white_mm).toBeCloseTo(2.4, 6);
    expect(s.plan.extrude.driven).not.toContain("white_mm");
    // ↺: driven again, out of the request
    await page.locator('[data-reset="extrude.white_mm"]').click();
    await idle(page);
    await expect(page.locator('[data-drv="extrude.white_mm"]')).toHaveAttribute("data-driven", "1");
    s = await state(page);
    expect(s.feature.extrude).toEqual({});
    expect((await lastRequest(page)).extrude?.white_mm).toBeUndefined();
    expect(s.plan.extrude.driven).toContain("white_mm");
    expect(Number(await white.inputValue())).toBeCloseTo(wholeLayers(fdm, 1.8, 2.0), 6);

    // typed a key at a time (each sent live), Enter: one Ctrl+Z takes it all back
    await black.click();
    await black.press("Control+a");
    await black.pressSequentially("1.25", { delay: 60 });
    await black.press("Enter");
    await idle(page);
    expect((await state(page)).feature.extrude).toEqual({ black_mm: 1.25 });
    expect((await lastRequest(page)).extrude).toEqual({ black_mm: 1.25 });
    await page.keyboard.press("Control+z");
    await idle(page);
    s = await state(page);
    expect(s.feature.extrude).toEqual({});
    await expect(page.locator('[data-drv="extrude.black_mm"]')).toHaveAttribute("data-driven", "1");
    expect(s.plan.extrude.driven).toContain("black_mm");

    // keys: Tab moves White → Black (a driven ↺ is not a stop); Esc in a field reverts it
    await white.focus();
    await page.keyboard.press("Tab");
    await expect(black).toBeFocused();
    await black.fill("9");
    await black.press("Escape");
    await idle(page);
    expect((await state(page)).feature.extrude).toEqual({});
    await expect(black).not.toBeFocused();
    // Esc outside a field cancels the panel: the new feature is gone
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    expect((await state(page)).doc.features).toHaveLength(0);
  });

  test("b2 · inkjet: a typed paper thickness is set and sent; ↺ back to the preset's", async ({ page }) => {
    await platePanel(page);
    await tab(page, "make");
    const paper = page.locator('input[data-path="extrude.paper_mm"]');
    await paper.fill("0.2");
    await paper.press("Enter");
    await idle(page);
    await expect(page.locator('[data-drv="extrude.paper_mm"]')).toHaveAttribute("data-driven", "0");
    let s = await state(page);
    expect(s.feature.extrude).toEqual({ paper_mm: 0.2 });
    expect((await lastRequest(page)).extrude).toEqual({ paper_mm: 0.2 });
    expect(s.plan.extrude.paper_mm).toBeCloseTo(0.2, 6);
    await page.locator('[data-reset="extrude.paper_mm"]').click();
    await idle(page);
    s = await state(page);
    expect(s.feature.extrude).toEqual({});
    expect(Number(await paper.inputValue())).toBeCloseTo(s.feature.preset.thickness_mm, 6);
  });

  test("c · Flip is on Make for a face profile and for a rectangle profile; the note says which side is out", async ({ page }) => {
    await platePanel(page);
    await tab(page, "make");
    const flip = page.locator('[data-tab-body="make"] [data-row="marker.flip"]');
    await expect(flip).toBeVisible();
    await expect(page.getByTestId("flip-out")).toHaveText("Outward side: out of the face");
    await flip.locator('[role=switch][data-path="marker.flip"]').click();
    await idle(page);
    let s = await state(page);
    expect(s.feature.marker.flip).toBe(true);
    expect(s.plan.extrude.flipped).toBe(true);
    await expect(page.getByTestId("flip-out")).toHaveText("Outward side: into the face (flipped)");
    await page.getByTestId("panel-ok").click();
    await idle(page);

    // a rectangle profile (the custom placement): no reference face, up is out
    await page.keyboard.press("r");
    await dragWorld(page, [130, 10], [160, 40]);
    await page.keyboard.press("a");
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await idle(page);
    s = await state(page);
    expect(s.feature.profile.holes).toEqual([]);
    await tab(page, "make");
    await expect(flip).toBeVisible();
    await expect(page.getByTestId("flip-out")).toHaveText("Outward side: up");
  });

  test("d · no disclosure in any tab, and nothing above the tabs but the title bar", async ({ page }) => {
    await platePanel(page);
    const panel = page.getByTestId("extrude-panel");
    // the body's first child is the tab strip; the title bar is the only thing over it
    const first = await panel.locator(".fpanel-body").evaluate((b) => (b.firstElementChild as HTMLElement).className);
    expect(first).toMatch(/kit-tabs/);
    const tabsTop = await top(page, '[data-testid="extrude-panel"] [role=tablist]');
    const headBottom = await panel.locator(".fpanel-head").evaluate((e) => e.getBoundingClientRect().bottom);
    expect(tabsTop - headBottom).toBeLessThanOrEqual(1);
    for (const t of ["make", "marker", "label"]) {
      await tab(page, t);
      // the label's rows too (it is off by default since 2026-10-20 night)
      if (t === "label") await labelOn(page);
      await expect(panel.locator(`[data-tab-body="${t}"]`)).toBeVisible();
      // (a dropdown's trigger has aria-expanded too: it is a choice, not a fold)
      await expect(panel.locator("details, summary, [aria-expanded]:not(.kit-select-trigger)"), `${t}: a disclosure`).toHaveCount(0);
      await expect(panel.getByText("Advanced", { exact: true })).toHaveCount(0);
      // every row of the tab sits below the tabs
      const rows = await panel.locator("[data-row]").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().top));
      expect(rows.length).toBeGreaterThan(2);
      for (const y of rows) expect(y).toBeGreaterThan(tabsTop);
    }
    // the key that was under Advanced is a plain row of Marker
    await tab(page, "marker");
    await expect(panel.locator('[data-tab-body="marker"] input[data-path="feature.key"]')).toBeVisible();
  });

  test("e · Corner mark is on Label, not Marker; Triangle draws it", async ({ page }) => {
    await platePanel(page);
    await tab(page, "marker");
    await expect(page.locator('[data-row="marker.corner_mark"]')).toHaveCount(0);
    await tab(page, "label");
    const row = page.locator('[data-tab-body="label"] [data-row="marker.corner_mark"]');
    await expect(row).toBeVisible();
    const n0 = (await state(page)).plan.black.length;
    await row.locator('[data-value="triangle"]').click();
    await idle(page);
    const s = await state(page);
    expect(s.feature.marker.corner_mark).toBe("triangle");
    expect(s.plan.black.length).toBeGreaterThan(n0);
    await page.screenshot({ path: path.join(SHOTS, "panel-inkjet-label.png") });
    await tab(page, "marker");
    await page.screenshot({ path: path.join(SHOTS, "panel-inkjet-marker.png") });
  });

  test("f · the presets dialog: nav, the list by method, Info -- three panes left to right; Duplicate makes an editable copy", async ({ page }) => {
    await platePanel(page);
    await page.getByTestId("panel-preset").click();
    const modal = page.getByTestId("presets-modal");
    await expect(modal).toBeVisible();
    await modal.locator('[data-coll="builtin"]').click();
    const panes = ["presets-nav", "preset-list", "presets-side"];
    const boxes = [];
    for (const p of panes) {
      await expect(modal.getByTestId(p)).toBeVisible();
      boxes.push((await modal.getByTestId(p).boundingBox())!);
    }
    for (let i = 1; i < boxes.length; i++) expect(boxes[i].x, `${panes[i]} right of ${panes[i - 1]}`).toBeGreaterThanOrEqual(boxes[i - 1].x + boxes[i - 1].width - 1);
    // listed by method: an Inkjet group, then a 3D print group, every card in its own
    const groups = await modal.locator("[data-group]").evaluateAll((els) => els.map((e) => e.getAttribute("data-group")));
    expect(groups).toEqual(["inkjet", "print3d"]);
    for (const g of groups) {
      await expect(modal.locator(`[data-group="${g}"] .pl-group-head`)).toHaveText(g === "inkjet" ? "Inkjet" : "3D print");
      const cards = modal.locator(`[data-group="${g}"] .card[data-card]`);
      for (let i = 0; i < (await cards.count()); i++) {
        await cards.nth(i).click();
        await expect(modal.locator('[data-path="preset.method"]')).toHaveAttribute("data-value", g!);
      }
    }
    // a built-in's Info is read-only; Duplicate to edit makes my editable copy
    await modal.locator('[data-group="inkjet"] .card[data-card]').first().click();
    const info = modal.getByTestId("preset-info");
    await expect(info).toHaveAttribute("data-readonly", "1");
    await expect(info.locator('input[data-path="preset.margin_mm"]')).toBeDisabled();
    await page.screenshot({ path: path.join(SHOTS, "panel-presets.png") });
    const name = await info.getByTestId("preset-name").inputValue();
    await info.getByTestId("preset-dup-edit").click();
    await expect(info).not.toHaveAttribute("data-readonly", "1");
    await expect(info.getByTestId("preset-name")).toHaveValue(`${name} (copy)`);
    expect(await info.getAttribute("data-preset")).toMatch(/^my:/);
    const margin = info.locator('input[data-path="preset.margin_mm"]');
    await expect(margin).toBeEnabled();
    await margin.fill("7.25");
    await margin.press("Enter");
    await expect(margin).toHaveValue("7.25");
    await expect(modal.locator('[data-coll="mine"]')).toHaveClass(/on/);
  });

  test("g · screenshots: each tab with a 3D preset; Make in Fusion 360 and Onshape", async ({ page }) => {
    await platePanel(page);
    await usePreset(page, "print3d");
    for (const t of ["make", "marker", "label"]) {
      await tab(page, t);
      await page.screenshot({ path: path.join(SHOTS, `panel-print3d-${t}.png`) });
    }
    await tab(page, "make");
    for (const skin of ["fusion", "onshape"]) {
      await pickSkin(page, skin as "fusion" | "onshape");
      await idle(page);
      // the same rows, the skin's row height
      const row = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--row")));
      for (const h of await page.locator('[data-tab-body="make"] .kit-row').evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height))) {
        expect(Math.abs(h - row)).toBeLessThan(0.6);
      }
      await page.screenshot({ path: path.join(SHOTS, `panel-print3d-make-${skin}.png`) });
    }
  });
});
