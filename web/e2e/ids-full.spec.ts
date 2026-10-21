// Review finding #5 (2026-10-21): 51 singles in DICT_4X4_50 (50 ids). Auto id
// refuses the 51st; Re-ID by fresh hash, twice, must never make it a duplicate,
// and Print lays out 50 stickers with 50 different ids, saying why one is missing.
import path from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, idle, openMenu, openStudio, state } from "./helpers";

const N = 51;

async function openFull(page: Page): Promise<void> {
  const shapes = Array.from({ length: N }, (_, i) => ({ kind: "rect", id: `r${i}`, cx: (i % 10) * 40, cy: Math.floor(i / 10) * 40, w: 30, h: 30, angle_deg: 0 }));
  const features = Array.from({ length: N }, (_, i) => ({ id: `f${i}`, key: `f${i}`, profile: { outer: `r${i}`, holes: [] } }));
  const file = path.join(test.info().outputDir, "full.arucostudio-web.json");
  mkdirSync(test.info().outputDir, { recursive: true });
  writeFileSync(file, JSON.stringify({ format: "arucostudio-web", version: 4, name: "Full", shapes, features, dims: [], id_ledger: {} }));
  await openMenu(page, "file");
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
  await chooser.setFiles(file);
  await idle(page);
}

async function sheetItems(page: Page): Promise<number[]> {
  await page.keyboard.press("p");
  const dialog = page.getByTestId("print-dialog");
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId("print-go")).toBeEnabled({ timeout: 60_000 });
  const req = JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!);
  return req.items.map((it: any) => it.marker.first_id);
}

test.describe("a full dictionary", () => {
  test.skip(CORE === "mock", "auto id is the real core's");

  test("51 singles in 4X4_50: one is refused, never a duplicate; Re-ID fresh hash twice keeps it so; Print has 50 different ids and says why", async ({ page }) => {
    test.setTimeout(240_000);
    await openStudio(page);
    await coreReady(page);
    await openFull(page);
    for (let round = 0; round < 2; round++) {
      await openMenu(page, "edit");
      await page.getByTestId("cmd-reid").click();
      await page.getByTestId("reid-mode").locator('[data-value="hash"]').click();
      await expect(page.getByTestId("reid-apply")).toBeEnabled({ timeout: 60_000 });
      await page.getByTestId("reid-apply").click();
      await idle(page);
      expect((await state(page)).doc.features).toHaveLength(N);
    }
    const items = await sheetItems(page);
    expect(items).toHaveLength(50);
    expect(new Set(items).size).toBe(50);
    await expect(page.getByTestId("print-dialog").locator('[data-issues-for="sheet.ids"] [data-level="error"]').first())
      .toContainText(/ArUco Extrude \d+ has no ids, so it isn't printed: .*full/);
  });
});
