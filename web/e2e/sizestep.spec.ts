// The size step (contract barrier 11, Zach 2026-10-20 night: "round to the
// DPI of the printer... or to use a normal number? ... maybe that's a preset
// you then put in the vinyl printer preset"): the Make tab's Size step row is
// driven grey by the marker's preset (0.5 mm on the inkjet built-ins), set per
// marker (Whole printer dots: the marker dot-exact, the Marker note says
// "exact"), ↺ back to the preset's; the presets dialog's Size step drives the
// markers made by that preset. Numbers from the probe's plan, the colour from
// getComputedStyle.
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openPresets, openStudio, panelTab, state } from "./helpers";

const DOT = 25.4 / 600;
const N = 6;                                       // DICT_4X4_50: cells per marker side

async function blankMarker(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-new").click();
  await page.keyboard.press("r");
  await dragWorld(page, [-20, -20], [20, 20]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
}

/** Whole 600 dpi dots per cell, to the core's 0.1 um. */
function dotExact(marker_mm: number): boolean {
  const k = marker_mm / N / DOT;
  return k >= 1 && Math.abs(k - Math.round(k)) < 1e-6;
}

const onHalf = (v: number) => Math.abs(v * 2 - Math.round(v * 2)) < 1e-9;

async function pick(page: Page, path: string, value: string): Promise<void> {
  await page.getByTestId(`dd:${path}`).click();
  await page.locator(`.kit-select-item[data-value="${value}"]`).click();
  await idle(page);
}

const row = (page: Page) => page.locator('[data-drv="marker.size_step"]');
const trigger = (page: Page) => page.getByTestId("dd:marker.size_step");
/** the colour of the value's text (grey while driven: styles.css .drv-choice.driven .kit-select-label) */
const valueColour = (page: Page) => trigger(page).locator(".kit-select-label").evaluate((e) => getComputedStyle(e).color);

test.describe("the size step", () => {
  test.skip(CORE === "mock", "the size step is the real core's");

  test("1 · Make: 0.5 mm driven grey on Letter vinyl; Whole printer dots sets it dot-exact; ↺ back", async ({ page }) => {
    await blankMarker(page);
    let s = await state(page);
    expect(s.feature.preset?.id ?? s.doc.default_preset.id).toBe("builtin:inkjet-letter-vinyl");
    await panelTab(page, "make");
    await expect(row(page)).toHaveAttribute("data-driven", "1");
    await expect(trigger(page)).toHaveText("0.5 mm");
    await expect(row(page)).toHaveAttribute("title", /Driven: the preset \(0\.5 mm\)/);
    const grey = await valueColour(page);
    const v0 = s.plan.marker_mm;
    expect(onHalf(v0), `driven ${v0} on 0.5 mm`).toBe(true);
    expect(dotExact(v0)).toBe(false);

    await pick(page, "marker.size_step", "dots");
    await expect(row(page)).toHaveAttribute("data-driven", "0");
    await expect(trigger(page)).toHaveText("Whole printer dots (exact)");
    expect(await valueColour(page)).not.toBe(grey);
    s = await state(page);
    expect(s.feature.marker.size_step).toEqual({ of: "dots" });
    const v1 = s.plan.marker_mm;
    expect(dotExact(v1), `dots ${v1}`).toBe(true);
    // 40 mm holds a 30 mm marker and its borders: 6 cells x 118 dots = 29.972 mm
    expect(v1).toBeCloseTo(29.972, 4);
    const note = `${v1} mm = 6 cells × 118 dots at 600 dpi, exact`;
    expect(s.plan.warnings.map((w: { text: string }) => w.text)).toContain(note);
    await panelTab(page, "marker");
    await expect(page.getByTestId("extrude-panel").getByText(note)).toBeVisible();
    expect(Number(await page.locator('input[data-path="marker.marker_mm"]').inputValue())).toBeCloseTo(v1, 2);

    await panelTab(page, "make");
    await page.locator('[data-reset="marker.size_step"]').click();
    await idle(page);
    await expect(row(page)).toHaveAttribute("data-driven", "1");
    await expect(trigger(page)).toHaveText("0.5 mm");
    expect(await valueColour(page)).toBe(grey);
    s = await state(page);
    expect(s.feature.marker.size_step ?? null).toBeNull();
    expect(s.plan.marker_mm).toBe(v0);
  });

  test("2 · the preset's Size step in the presets dialog drives the marker made by it", async ({ page }) => {
    await blankMarker(page);
    const v0 = (await state(page)).plan.marker_mm;
    // a copy of Letter vinyl in My presets, used for this marker
    let modal = await openPresets(page);
    await modal.locator('[data-coll="builtin"]').click();
    await modal.locator('[data-card="builtin:inkjet-letter-vinyl"]').click();
    const info = modal.getByTestId("preset-info");
    await expect(info.getByTestId("dd:preset.size_step")).toHaveText("0.5 mm");
    await modal.getByTestId("preset-dup-edit").click();
    await modal.getByTestId("presets-select").click();
    await idle(page);
    let s = await state(page);
    expect(s.feature.preset.builtin).toBe(false);
    expect(s.plan.marker_mm).toBe(v0);

    // its step to whole dots, in Info: the marker's driven size follows
    modal = await openPresets(page);
    await expect(modal.getByTestId("preset-info")).toHaveAttribute("data-preset", s.feature.preset.id);
    await pick(page, "preset.size_step", "dots");
    await modal.getByTestId("presets-cancel").click();
    await idle(page);
    s = await state(page);
    expect(s.feature.preset.size_step).toEqual({ of: "dots" });
    expect(dotExact(s.plan.marker_mm), `dots ${s.plan.marker_mm}`).toBe(true);
    expect(s.plan.marker_mm).not.toBe(v0);
    // still driven: the marker has no step of its own
    await panelTab(page, "make");
    await expect(row(page)).toHaveAttribute("data-driven", "1");
    await expect(trigger(page)).toHaveText("Whole printer dots (exact)");

    // a 3D preset shows its step read-only
    modal = await openPresets(page);
    await modal.locator('[data-coll="builtin"]').click();
    await modal.locator('[data-card="builtin:default"]').click();
    await expect(modal.getByTestId("preset-info").getByTestId("preset-size-step")).toHaveText("0.5 mm");
    await expect(modal.getByTestId("preset-info").getByTestId("dd:preset.size_step")).toHaveCount(0);
  });
});
