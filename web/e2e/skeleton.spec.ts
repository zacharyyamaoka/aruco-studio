// The ArUco Extrude panel's skeleton (docs/design/panel_skeleton.md, Zach
// 2026-10-21): the tabs Marker | Label | Make in that order, a new feature
// opening on Marker, Profile then Preset first on Marker, Make's rows in the
// skeleton's order, the Key driven (grey) until typed, a driven segmented pick
// that still reads as selected in every skin, two printer icons that tell an
// inkjet preset from a 3D one, and the Fusion skin's uppercase title and green
// "✓ …" summary line. Every check reads the probe, the drawn boxes
// (getBoundingClientRect) or the computed styles. SKELETON_SHOTS=<dir> also
// writes 1280 × 800 shots of each tab in the Studio and Fusion skins, the
// presets dialog, and the Fusion panel at 1.5x (for the side-by-side with
// Fusion's own dialog).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, idle, loadExample, openStudio, panelTab, pickSkin, state, toggleTheme } from "./helpers";

const SHOTS = process.env.SKELETON_SHOTS;
type SkinId = "studio" | "unstyled" | "fusion" | "onshape";

/** Examples › Plate, click the face, A: a new feature, its panel open. */
async function platePanel(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
}

/** The data-row of every row in a tab's body, top to bottom (by y). Holes
 *  (a profile with holes only, as the plate's face) must come right after
 *  Profile, and is left out of the list. */
async function rowsByY(page: Page, tab: string): Promise<string[]> {
  const rows = await page.locator(`[data-testid="extrude-panel"] [data-tab-body="${tab}"] [data-row]`).evaluateAll((els) =>
    els.map((e) => ({ r: e.getAttribute("data-row")!, y: e.getBoundingClientRect().top }))
      .sort((a, b) => a.y - b.y).map((x) => x.r));
  const h = rows.indexOf("holes");
  if (h >= 0) expect(rows[h - 1], "Holes right under Profile").toBe("profile");
  return rows.filter((r) => r !== "holes");
}

/** The presets dialog from the Preset row: the first built-in of a method, Select. */
async function usePreset(page: Page, method: "inkjet" | "print3d"): Promise<void> {
  await panelTab(page, "marker");
  await page.getByTestId("panel-preset").click();
  const modal = page.getByTestId("presets-modal");
  await modal.locator('[data-coll="builtin"]').click();
  await modal.locator(`[data-group="${method}"] .card[data-card]`).first().click();
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
  expect((await state(page)).feature.preset.method).toBe(method);
}

const icon = (page: Page, sel: string) => page.locator(sel).first().evaluate((e) => e.getAttribute("data-icon"));
const svg = (page: Page, sel: string) => page.locator(sel).first().evaluate((e) => e.innerHTML);

/** The computed look of a segmented row's lit segment and an unlit one. */
async function segLook(page: Page, row: string): Promise<{ on: string; off: string; outline: string; driven: string }> {
  return page.locator(`[data-testid="extrude-panel"] [data-drv="${row}"]`).evaluate((box) => {
    const look = (b: Element) => { const c = getComputedStyle(b); return `${c.backgroundColor}|${c.color}|${c.boxShadow}`; };
    const on = box.querySelector(".kit-seg-btn.on")!, off = box.querySelector(".kit-seg-btn:not(.on)")!;
    return { on: look(on), off: look(off), outline: getComputedStyle(on).boxShadow, driven: box.getAttribute("data-driven")! };
  });
}

test.describe(`the panel skeleton (${CORE} core)`, () => {
  test("a · tabs Marker | Label | Make, a new feature opens on Marker; Make keeps its name, its icon is the method's printer", async ({ page }) => {
    await platePanel(page);
    const panel = page.getByTestId("extrude-panel");
    await expect(panel.locator("[role=tab]")).toHaveText(["Marker", "Label", "Make"]);
    expect(await panel.locator("[role=tab]").evaluateAll((els) => els.map((e) => e.getAttribute("data-tab")))).toEqual(["marker", "label", "make"]);
    // the order is drawn left to right, too
    const xs = await panel.locator("[role=tab]").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().left));
    expect(xs[0]).toBeLessThan(xs[1]);
    expect(xs[1]).toBeLessThan(xs[2]);
    expect((await state(page)).panel.tab).toBe("marker");
    await expect(panel.locator('[role=tab][data-tab="marker"]')).toHaveAttribute("aria-selected", "true");
    await expect(panel.locator('[data-tab-body="marker"]')).toBeVisible();
    // Make: always "Make"; its icon is the preset's method (inkjet first, then a 3D print preset)
    expect((await state(page)).feature.preset.method).toBe("inkjet");
    expect(await icon(page, '[role=tab][data-tab="make"] svg')).toBe("tab-inkjet");
    const inkjetTab = await svg(page, '[role=tab][data-tab="make"] svg');
    await usePreset(page, "print3d");
    await expect(panel.locator('[role=tab][data-tab="make"]')).toHaveText("Make");
    expect(await icon(page, '[role=tab][data-tab="make"] svg')).toBe("tab-print3d");
    expect(await svg(page, '[role=tab][data-tab="make"] svg'), "a 3D printer, not the inkjet's drawing").not.toBe(inkjetTab);
    expect(await icon(page, '[role=tab][data-tab="marker"] svg')).toBe("tab-marker");
    expect(await icon(page, '[role=tab][data-tab="label"] svg')).toBe("tab-label");
  });

  test("b · Marker: Profile then Preset first, then Type, Dictionary, ID, Marker size, (grid: Columns × Rows, Separation), Suggest, Turn, Quiet zone, Key", async ({ page }) => {
    await platePanel(page);
    // a face profile: no Rotation (the skeleton: a rectangle profile only)
    expect(await rowsByY(page, "marker")).toEqual(["profile", "preset", "marker.type", "marker.dictionary", "marker.first_id",
      "marker.marker_mm", "marker.suggest", "marker.turn", "marker.quiet_modules", "feature.key"]);
    const ys = await page.locator('[data-tab-body="marker"] [data-row]').evaluateAll((els) =>
      Object.fromEntries(els.map((e) => [e.getAttribute("data-row"), e.getBoundingClientRect().top])));
    expect(ys["profile"]).toBeLessThan(ys["preset"]);
    expect(ys["preset"]).toBeLessThan(ys["marker.type"]);
    // a grid: its counts and separation after the marker size, Suggest after them
    await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
    await idle(page);
    expect(await rowsByY(page, "marker")).toEqual(["profile", "preset", "marker.type", "marker.dictionary", "marker.first_id",
      "marker.marker_mm", "marker.cols", "marker.separation_mm", "marker.suggest", "marker.turn", "marker.quiet_modules", "feature.key"]);
    // a ChArUco board: counts, checker, origin
    await page.locator('[data-path="marker.type"] [data-value="charuco"]').click();
    await idle(page);
    expect((await rowsByY(page, "marker")).slice(5, 10)).toEqual(["marker.marker_mm", "marker.cols", "marker.checker_mm", "marker.origin_square", "marker.suggest"]);
    // nothing of Make's on Marker
    for (const r of ["trim", "marker.size_step", "extrude.paper_mm", "marker.flip"]) {
      await expect(page.locator(`[data-tab-body="marker"] [data-row="${r}"]`), r).toHaveCount(0);
    }
  });

  test("c · Make: Size step, Trim, the heights, Flip, in that order (inkjet: Paper thickness; 3D print: Extrude, White, Black height)", async ({ page }) => {
    await platePanel(page);
    await panelTab(page, "make");
    expect(await rowsByY(page, "make")).toEqual(["marker.size_step", "trim", "extrude.paper_mm", "marker.flip"]);
    await usePreset(page, "print3d");
    await panelTab(page, "make");
    expect(await rowsByY(page, "make")).toEqual(["marker.size_step", "trim", "extrude.mode", "extrude.white_mm", "extrude.black_mm", "marker.flip"]);
    await expect(page.locator('[data-tab-body="make"] [data-row="profile"], [data-tab-body="make"] [data-row="preset"]')).toHaveCount(0);
  });

  test("d · Key is driven: grey until typed, then normal text with ↺ inside the field; ↺ drives it again", async ({ page }) => {
    await platePanel(page);
    const field = page.locator('[data-drv="feature.key"]');
    const input = page.locator('input[data-path="feature.key"]');
    const id = (await state(page)).feature.id;
    await expect(field).toHaveAttribute("data-driven", "1");
    await expect(input).toHaveValue(id);
    await expect(page.locator('[data-reset="feature.key"]')).toHaveCount(0);
    const muted = await page.evaluate(() => {
      const probe = document.createElement("span");
      probe.style.color = "var(--muted)";
      document.querySelector("[data-testid=extrude-panel]")!.appendChild(probe);
      const c = getComputedStyle(probe).color;
      probe.remove();
      return c;
    });
    const grey = await input.evaluate((e) => getComputedStyle(e).color);
    expect(grey, "a driven key is in the muted grey").toBe(muted);
    // typed: set, normal text, ↺ inside the field at its right end
    await input.fill("door-left");
    await input.press("Enter");
    await idle(page);
    expect((await state(page)).feature.key).toBe("door-left");
    await expect(field).toHaveAttribute("data-driven", "0");
    expect(await input.evaluate((e) => getComputedStyle(e).color)).not.toBe(grey);
    const reset = page.locator('[data-reset="feature.key"]');
    await expect(reset).toBeVisible();
    const [fb, rb] = [(await field.boundingBox())!, (await reset.boundingBox())!];
    expect(rb.x).toBeGreaterThanOrEqual(fb.x);
    expect(rb.x + rb.width).toBeLessThanOrEqual(fb.x + fb.width + 0.5);
    expect(rb.y).toBeGreaterThanOrEqual(fb.y - 0.5);
    expect(rb.y + rb.height).toBeLessThanOrEqual(fb.y + fb.height + 0.5);
    await reset.click();
    await idle(page);
    expect((await state(page)).feature.key).toBe(id);
    await expect(field).toHaveAttribute("data-driven", "1");
  });

  test("e · a driven segmented pick still reads as SELECTED (fill and outline unlike an unpicked one) in every skin and theme", async ({ page }) => {
    await platePanel(page);
    const cases: [SkinId, "light" | "dark"][] = [
      ["studio", "light"], ["studio", "dark"], ["unstyled", "light"], ["unstyled", "dark"], ["fusion", "dark"], ["onshape", "light"],
    ];
    for (const [skin, theme] of cases) {
      if ((await page.locator("html").getAttribute("data-skin")) !== skin) await pickSkin(page, skin);
      if ((await page.locator("html").getAttribute("data-theme")) !== theme) await toggleTheme(page);
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      await panelTab(page, "make");
      const trim = await segLook(page, "trim");
      expect(trim.driven, `${skin}/${theme}: Trim is driven`).toBe("1");
      expect((await state(page)).feature.trim).toBe("profile");
      expect(trim.on, `${skin}/${theme}: the driven pick (Profile) looks unlike Marker`).not.toBe(trim.off);
      expect(trim.outline, `${skin}/${theme}: the driven pick keeps the selected outline`).not.toBe("none");
      await panelTab(page, "marker");
      const turn = await segLook(page, "marker.turn");
      expect(turn.driven).toBe("1");
      expect(turn.on, `${skin}/${theme}: Turn's driven 0°`).not.toBe(turn.off);
      expect(turn.outline).not.toBe("none");
    }
  });

  test("f · inkjet and 3D presets show different printer icons: the Preset row, the presets dialog, the Make tab", async ({ page }) => {
    await platePanel(page);
    expect(await icon(page, '[data-testid="panel-preset"] svg')).toBe("inkjet");
    await page.getByTestId("panel-preset").click();
    const modal = page.getByTestId("presets-modal");
    await modal.locator('[data-coll="builtin"]').click();
    expect(await icon(page, '[data-group="inkjet"] .pl-group-head svg')).toBe("inkjet");
    expect(await icon(page, '[data-group="print3d"] .pl-group-head svg')).toBe("print3d");
    expect(await icon(page, '[data-group="inkjet"] .card .name svg')).toBe("inkjet");
    expect(await icon(page, '[data-group="print3d"] .card .name svg')).toBe("print3d");
    // two drawings, not one under two names
    expect(await svg(page, '[data-group="inkjet"] .pl-group-head svg')).not.toBe(await svg(page, '[data-group="print3d"] .pl-group-head svg'));
    if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "presets-dialog.png") });
    await page.getByTestId("presets-cancel").click();
    await expect(modal).toHaveCount(0);
    const inkjetRow = await svg(page, '[data-testid="panel-preset"] svg');
    await usePreset(page, "print3d");
    expect(await icon(page, '[data-testid="panel-preset"] svg')).toBe("print3d");
    expect(await svg(page, '[data-testid="panel-preset"] svg')).not.toBe(inkjetRow);
    expect(await icon(page, '[role=tab][data-tab="make"] svg')).toBe("tab-print3d");
    // each is drawn: one of its images is shown, and it has loaded
    const shown = await page.locator('[data-testid="panel-preset"] svg image').evaluateAll((els) =>
      els.filter((e) => getComputedStyle(e).display !== "none").map((e) => (e as SVGImageElement).getBBox().width));
    expect(shown, "one image of four shown, 16 wide").toEqual([16]);
  });

  test("g · Fusion skin: the title in uppercase (EDIT ARUCO EXTRUDE when reopened), Type as icon buttons, the green ✓ summary line", async ({ page }) => {
    await platePanel(page);
    await pickSkin(page, "fusion");
    const title = page.locator('[data-testid="extrude-panel"] .fpanel-title');
    expect(await title.evaluate((e) => getComputedStyle(e).textTransform)).toBe("uppercase");
    // as drawn (innerText follows text-transform and leaves the hidden number out)
    await expect.poll(() => title.evaluate((e) => (e as HTMLElement).innerText.trim())).toBe("ARUCO EXTRUDE");
    // Type: three icon buttons, no words
    expect(await page.locator('[data-path="marker.type"] .kit-seg-btn svg').count()).toBe(3);
    await expect(page.locator('[data-path="marker.type"] .kit-seg-btn.words')).toHaveCount(0);
    // the summary: green, "✓ " before it
    const ok = page.getByTestId("plan-ok");
    await expect(ok).toBeVisible();
    const look = await ok.evaluate((e) => ({ color: getComputedStyle(e).color, before: getComputedStyle(e, "::before").content }));
    const [r, g, b] = look.color.match(/\d+/g)!.map(Number);
    expect(g, `green: ${look.color}`).toBeGreaterThan(r + 30);
    expect(g).toBeGreaterThan(b + 20);
    expect(look.before).toContain("✓");
    // OK, then reopen: "EDIT ARUCO EXTRUDE"
    await page.getByTestId("panel-ok").click();
    await idle(page);
    const fid = (await state(page)).doc.features[0].id;
    const box = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await expect.poll(() => title.evaluate((e) => (e as HTMLElement).innerText.trim())).toBe("EDIT ARUCO EXTRUDE");
  });

  test("h · screenshots (SKELETON_SHOTS): each tab in Studio and Fusion (dark), and the Fusion panel at 1.5x", async ({ browser }) => {
    test.skip(!SHOTS, "SKELETON_SHOTS is not set");
    for (const [skin, scale] of [["studio", 1], ["fusion", 1], ["fusion", 1.5]] as const) {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: scale });
      const page = await ctx.newPage();
      await platePanel(page);
      if (skin !== "studio") await pickSkin(page, skin);
      if ((await page.locator("html").getAttribute("data-theme")) !== "dark") await toggleTheme(page);
      await page.locator('[data-path="marker.type"] [data-value="grid"]').click();
      await idle(page);
      for (const t of ["marker", "label", "make"]) {
        await panelTab(page, t as "marker");
        await page.mouse.move(0, 799);
        const name = `${skin}${scale !== 1 ? "-1.5x" : ""}-${t}`;
        if (scale === 1) await page.screenshot({ path: path.join(SHOTS!, `${name}.png`) });
        else await page.getByTestId("extrude-panel").screenshot({ path: path.join(SHOTS!, `${name}-panel.png`) });
        if (scale !== 1 && t === "marker") {
          // the boxes the numeric check samples (CSS px, the panel's own origin)
          const boxes = await page.evaluate(() => {
            const p = document.querySelector("[data-testid=extrude-panel]")!.getBoundingClientRect();
            const r = (sel: string) => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return [b.x - p.x, b.y - p.y, b.width, b.height]; };
            const rows = [...document.querySelectorAll("[data-testid=extrude-panel] .tab-body .kit-row")].map((e) => { const b = e.getBoundingClientRect(); return [b.y - p.y, b.height]; });
            return { panel: [p.x, p.y, p.width, p.height], title: r(".fpanel-title"), head: r(".fpanel-head"), tabs: r(".kit-tab-list"), tabOn: r(".kit-tab.on"),
              label: r('[data-row="marker.dictionary"] .row-text'), field: r('[data-row="marker.dictionary"] .kit-select-trigger'),
              ok: r("[data-testid=panel-ok]"), status: r("[data-testid=plan-ok]"), rows, typeOn: r('[data-path="marker.type"] .kit-seg-btn.on'),
              markerLabel: r('[data-row="marker.marker_mm"] .row-text'),
              fontSize: parseFloat(getComputedStyle(document.querySelector('[data-row="marker.marker_mm"] .row-label')!).fontSize) };
          });
          (await import("node:fs")).writeFileSync(path.join(SHOTS!, `${name}-boxes.json`), JSON.stringify(boxes, null, 1));
        }
      }
      await ctx.close();
    }
  });
});
