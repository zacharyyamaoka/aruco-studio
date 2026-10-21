// Review finding #12 (2026-10-21): the 3D view's height box edits the value
// at its full stored precision, commits only a changed text, on Enter and on
// blur alike, and Escape puts it back. The inkjet tile's paper box, real core.
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, idle, loadExample, openStudio, state } from "./helpers";

const box = (page: Page) => page.locator('[data-testid="v3-box"][data-key="paper_mm"] input');
const paper = async (page: Page) => (await state(page)).feature.extrude.paper_mm as number | undefined;

async function focusBox(page: Page): Promise<void> {
  await box(page).click();
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
}

test.describe("the 3D height box", () => {
  test.skip(CORE === "mock", "the heights are the real core's");

  test.beforeEach(async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "custom-placement");
    await idle(page);
    await page.keyboard.press("3");
    await expect(page.getByTestId("view3d")).toBeVisible();
    await expect(box(page)).toBeVisible();
    // a stored height with more digits than the box shows
    await focusBox(page);
    await page.keyboard.press("Control+a");
    await page.keyboard.type("0.123456");
    await page.keyboard.press("Enter");
    await idle(page);
    expect(await paper(page)).toBe(0.123456);
  });

  test("focus shows the full value; Enter without a change keeps it exactly", async ({ page }) => {
    await focusBox(page);
    await expect(box(page)).toHaveValue("0.123456");
    await page.keyboard.press("Enter");
    await idle(page);
    expect(await paper(page)).toBe(0.123456);
    // and a blur without a change, too
    await focusBox(page);
    await page.keyboard.press("Tab");
    await idle(page);
    expect(await paper(page)).toBe(0.123456);
  });

  test("a typed value commits on blur as on Enter; Escape puts it back", async ({ page }) => {
    await focusBox(page);
    await page.keyboard.press("Control+a");
    await page.keyboard.type("0.2");
    await page.keyboard.press("Tab");
    await idle(page);
    expect(await paper(page)).toBe(0.2);
    await focusBox(page);
    await page.keyboard.press("Control+a");
    await page.keyboard.type("0.3");
    await page.keyboard.press("Escape");
    await idle(page);
    expect(await paper(page)).toBe(0.2);
    await expect(box(page)).not.toBeFocused();
  });
});
