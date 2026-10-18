// The presets modal after Zach's 2026-10-18 review: filters in the left bar,
// Info always on the right, a click shows a preset's Info, my presets are
// edited in Info and kept in this browser, Select sets the document's preset.
// On the real core: the built-ins are the core's, read through the cards.
import { expect, test, type Locator, type Page } from "@playwright/test";
import { coreReady, openStudio, state } from "./helpers";

async function openPresets(page: Page): Promise<Locator> {
  await page.getByTestId("preset-chip").click();
  const modal = page.getByTestId("presets-modal");
  await expect(modal).toBeVisible();
  return modal;
}

const num = (info: Locator, path: string) => info.locator(`input[data-path="${path}"]`);

test.describe("the presets modal", () => {
  test.beforeEach(async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
  });

  test("1 · no Filters on the right: the chips sit in the left bar, under the search", async ({ page }) => {
    const modal = await openPresets(page);
    const side = modal.getByTestId("presets-side");
    const nav = modal.getByTestId("presets-nav");
    await expect(side).toBeVisible();
    await expect(side.getByText("Filters", { exact: true })).toHaveCount(0);
    await expect(side.getByRole("button", { name: /filters/i })).toHaveCount(0);
    await expect(side.locator("[data-chip]")).toHaveCount(0);
    await expect(side.getByText("Info", { exact: true })).toBeVisible();
    // the method chips are drawn inside the left bar, below the search, above the collections
    const navBox = (await nav.boundingBox())!;
    const search = (await nav.getByTestId("lib-search").boundingBox())!;
    const colls = (await nav.locator('[data-coll="recent"]').boundingBox())!;
    for (const chip of ["Inkjet", "3D print"]) {
      const b = (await nav.locator(`[data-chip="${chip}"]`).boundingBox())!;
      expect(b.x).toBeGreaterThanOrEqual(navBox.x);
      expect(b.x + b.width).toBeLessThanOrEqual(navBox.x + navBox.width);
      expect(b.y).toBeGreaterThan(search.y + search.height - 1);
      expect(b.y + b.height).toBeLessThan(colls.y + 1);
    }
    // the current preset's Info is open from the start
    const cur = (await state(page)).doc.preset;
    await expect(side.getByTestId("preset-info")).toHaveAttribute("data-preset", cur.id);
  });

  test("2 · a click on a card shows that preset's name and values in Info", async ({ page }) => {
    const modal = await openPresets(page);
    await modal.locator('[data-coll="builtin"]').click();
    const info = modal.getByTestId("preset-info");
    const cards = modal.locator(".card[data-card]");
    const n = await cards.count();
    expect(n).toBeGreaterThan(1);
    for (let i = 0; i < n; i++) {
      const card = cards.nth(i);
      await card.click();
      await expect(card).toHaveAttribute("aria-selected", "true");
      const id = (await card.getAttribute("data-card"))!;
      const name = (await card.locator(".name").textContent())!;
      const sub = (await card.locator(".sub").textContent())!;
      await expect(info).toHaveAttribute("data-preset", id);
      await expect(info.getByTestId("preset-name")).toHaveValue(name);
      // the card's numbers ("A4 · 600 dpi · 0.1 mm" / "nozzle 0.6 · lines 0.675 · …") are Info's values
      if (/dpi/.test(sub)) {
        const [paper, dpi, thick] = sub.split(" · ");
        await expect(info.locator('[data-path="preset.method"]')).toHaveAttribute("data-value", "inkjet");
        await expect(info.locator('[data-path="preset.page"]')).toHaveAttribute("data-value", paper);
        await expect(num(info, "preset.dpi")).toHaveValue(dpi.replace(" dpi", ""));
        await expect(num(info, "preset.thickness_mm")).toHaveValue(thick.replace(" mm", ""));
        for (const k of ["page_mm.0", "page_mm.1", "margin_mm", "min_cell_mm", "cell_step_mm"]) await expect(num(info, `preset.${k}`)).not.toHaveValue("");
        if (paper === "A4") {
          await expect(num(info, "preset.page_mm.0")).toHaveValue("210");
          await expect(num(info, "preset.page_mm.1")).toHaveValue("297");
        }
      } else {
        const nozzle = /nozzle ([\d.]+)/.exec(sub)![1], line = /lines ([\d.]+)/.exec(sub)![1];
        await expect(info.locator('[data-path="preset.method"]')).toHaveAttribute("data-value", "print3d");
        await expect(num(info, "preset.nozzle_mm")).toHaveValue(nozzle);
        await expect(num(info, "preset.line_mm")).toHaveValue(line);
        for (const k of ["layer_mm", "first_layer_mm", "min_cell_mm", "cell_step_mm"]) await expect(num(info, `preset.${k}`)).not.toHaveValue("");
        // every 3D field has its row; the core's flat 3D preset leaves first line and bed unset (shown empty, not invented)
        for (const k of ["first_line_mm", "bed_mm.0", "bed_mm.1"]) await expect(num(info, `preset.${k}`)).toHaveCount(1);
      }
      // a built-in is read-only, with Duplicate to edit
      await expect(info).toHaveAttribute("data-readonly", "1");
      await expect(num(info, "preset.min_cell_mm")).toBeDisabled();
      await expect(info.getByTestId("preset-dup-edit")).toBeVisible();
    }
    // Select uses the picked card: the document's preset has Info's numbers
    const a4 = cards.filter({ hasText: "A4" }).first();
    await a4.click();
    const a4Id = (await a4.getAttribute("data-card"))!;
    const margin = Number(await num(info, "preset.margin_mm").inputValue());
    await page.getByTestId("presets-select").click();
    await expect(modal).toHaveCount(0);
    const s = await state(page);
    expect(s.doc.preset.id).toBe(a4Id);
    expect(s.doc.preset).toMatchObject({ page: "A4", margin_mm: margin, page_mm: [210, 297] });
  });

  test("3 · Duplicate a built-in, type a margin in Info: it persists; Select puts the new name on the chip", async ({ page }) => {
    let modal = await openPresets(page);
    await modal.locator('[data-coll="builtin"]').click();
    const a4 = modal.locator(".card[data-card]").filter({ hasText: "A4" }).first();
    const baseName = (await a4.locator(".name").textContent())!;
    await a4.click();
    let info = modal.getByTestId("preset-info");
    const before = await num(info, "preset.margin_mm").inputValue();
    await info.getByTestId("preset-dup-edit").click();
    // the copy is mine, picked, and editable
    await expect(modal.locator('[data-coll="mine"]')).toHaveClass(/on/);
    const copyName = `${baseName} (copy)`;
    await expect(info.getByTestId("preset-name")).toHaveValue(copyName);
    await expect(info).not.toHaveAttribute("data-readonly", "1");
    const copyId = (await info.getAttribute("data-preset"))!;
    expect(copyId).toMatch(/^my:/);
    const typed = Number(before) === 7.5 ? "8.25" : "7.5";
    await num(info, "preset.margin_mm").fill(typed);
    await num(info, "preset.margin_mm").press("Enter");
    await expect(num(info, "preset.margin_mm")).toHaveValue(typed);
    // saved in this browser
    const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("aruco-web.presets.mine") ?? "[]"));
    expect(stored.find((p: { id: string }) => p.id === copyId)).toMatchObject({ margin_mm: Number(typed), builtin: false });

    // close and reopen: the value is there
    await page.getByTestId("presets-cancel").click();
    await expect(modal).toHaveCount(0);
    modal = await openPresets(page);
    await modal.locator('[data-coll="mine"]').click();
    await modal.locator(`.card[data-card="${copyId}"]`).click();
    info = modal.getByTestId("preset-info");
    await expect(num(info, "preset.margin_mm")).toHaveValue(typed);

    // and after a reload of the page
    await page.reload();
    await coreReady(page);
    modal = await openPresets(page);
    await modal.locator('[data-coll="mine"]').click();
    await modal.locator(`.card[data-card="${copyId}"]`).click();
    info = modal.getByTestId("preset-info");
    await expect(num(info, "preset.margin_mm")).toHaveValue(typed);

    // rename it in Info, then Select: the top bar's chip shows the new name
    const newName = "My A4 vinyl, wide margin";
    await info.getByTestId("preset-name").fill(newName);
    await info.getByTestId("preset-name").press("Enter");
    await expect(modal.locator(`.card[data-card="${copyId}"] .name`)).toHaveText(newName);
    await page.getByTestId("presets-select").click();
    await expect(modal).toHaveCount(0);
    await expect(page.getByTestId("preset-chip")).toContainText(newName);
    const s = await state(page);
    expect(s.doc.preset).toMatchObject({ id: copyId, name: newName, margin_mm: Number(typed), page: "A4" });
  });

  test("4 · the Method chip in the left bar filters the cards", async ({ page }) => {
    const modal = await openPresets(page);
    await modal.locator('[data-coll="builtin"]').click();
    const cards = modal.locator(".card[data-card]");
    const info = modal.getByTestId("preset-info");
    const total = await cards.count();
    const methodsOf = async (): Promise<string[]> => {
      const out: string[] = [];
      for (let i = 0; i < (await cards.count()); i++) {
        await cards.nth(i).click();
        out.push((await info.locator('[data-path="preset.method"]').getAttribute("data-value"))!);
      }
      return out;
    };
    const nav = modal.getByTestId("presets-nav");
    await nav.locator('[data-chip="3D print"]').click();
    await expect(nav.locator('[data-chip="3D print"]')).toHaveAttribute("aria-pressed", "true");
    const fdm = await methodsOf();
    expect(fdm.length).toBeGreaterThan(0);
    expect(new Set(fdm)).toEqual(new Set(["print3d"]));
    await nav.locator('[data-chip="3D print"]').click();
    await nav.locator('[data-chip="Inkjet"]').click();
    const ink = await methodsOf();
    expect(ink.length).toBeGreaterThan(0);
    expect(new Set(ink)).toEqual(new Set(["inkjet"]));
    expect(fdm.length + ink.length).toBe(total);
    await nav.getByTestId("preset-clear-filters").click();
    await expect(cards).toHaveCount(total);
  });
});
