// Review findings #6 and #8 (2026-10-21): output is made only of a document
// whose ids auto id has settled, and Print / Download only of the sheet the
// controls ask for now. The core's replies are held back with the test-only
// window.__arucoFault (web/src/coreSource.ts) to open the window where both
// went wrong: a copy of #7 exported as #7, a sheet laid out under the old
// controls still printable. On the real core (auto id is the real core's).
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openMenu, openStudio, panelTab, state, toClient } from "./helpers";

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
}

/** A 20 mm square at (-30..-10, -10..10) with its ArUco Extrude, first id typed 7. */
async function marker7(page: Page): Promise<void> {
  await page.keyboard.press("r");
  await dragWorld(page, [-30, -10], [-10, 10]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await panelTab(page, "marker");
  const id = page.locator('input[data-path="marker.first_id"]');
  await id.fill("7");
  await id.press("Enter");
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
}

/** Copy it, hold auto id's answer back `ms`, paste it at (25, 0): the copy starts on the borrowed #7. */
async function pasteWithSlowIds(page: Page, ms: number): Promise<void> {
  const [ex, ey] = await toClient(page, -30, 0);
  await page.mouse.click(ex, ey);
  await page.keyboard.press("Control+c");
  await page.evaluate((hold) => { (window as any).__arucoFault = { delay: { assign_ids: hold } }; }, ms);
  const [px, py] = await toClient(page, 25, 0);
  await page.mouse.move(px, py);
  await page.keyboard.press("Control+v");
}

const firstIds = async (page: Page): Promise<number[] | null> => {
  const raw = await page.getByTestId("sheet-side").getAttribute("data-request");
  return raw ? JSON.parse(raw).items.map((it: any) => it.marker.first_id) : null;
};

test.describe("output waits for settled ids and the current sheet", () => {
  test.skip(CORE === "mock", "auto id is the real core's");

  test("#6 · Export › SVG right after pasting a copy of #7, auto id slow: the file is the copy's own id, #8", async ({ page }) => {
    await blank(page);
    await marker7(page);
    await pasteWithSlowIds(page, 2500);
    await openMenu(page, "export");
    const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 30_000 }), page.getByTestId("cmd-svg").click()]);
    const svg = await (await dl.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
    expect(svg).toMatch(/<title>DICT_4X4_50 #8<\/title>/);
  });

  test("#6 · Print right after pasting, auto id slow: Print and the downloads stay off until the ids are settled, never on [7, 7]", async ({ page }) => {
    await blank(page);
    await marker7(page);
    await pasteWithSlowIds(page, 2500);
    await page.keyboard.press("p");
    await expect(page.getByTestId("print-dialog")).toBeVisible();
    const t0 = Date.now();
    let seenOn = false;
    while (Date.now() - t0 < 15_000) {
      const on = await page.getByTestId("print-go").isEnabled();
      if (on) {
        const ids = await firstIds(page);
        expect(ids, "an enabled Print has the copy's own id").toEqual([7, 8]);
        expect(await page.getByTestId("print-pdf").isEnabled()).toBe(true);
        seenOn = true;
        break;
      }
      expect(await page.getByTestId("print-pdf").isEnabled()).toBe(false);
      expect(await page.getByTestId("print-svg").isEnabled()).toBe(false);
      await page.waitForTimeout(50);
    }
    expect(seenOn, "Print comes on once the ids are in").toBe(true);
  });

  test("#8 · a layout change with the sheet slow: the old sheet is not printable under the new controls", async ({ page }) => {
    await blank(page);
    await marker7(page);
    await page.keyboard.press("p");
    await expect(page.getByTestId("print-go")).toBeEnabled({ timeout: 30_000 });
    const before = (await page.getByTestId("sheet-side").getAttribute("data-request"))!;
    expect(JSON.parse(before).mode).toBe("spaced");
    await page.evaluate(() => { (window as any).__arucoFault = { delay: { sheet: 2500 } }; });
    await page.getByTestId("sheet-mode").locator('[data-value="tight"]').click();
    for (const b of ["print-go", "print-pdf", "print-svg"]) await expect(page.getByTestId(b), b).toBeDisabled();
    // the old sheet stays on screen, marked busy, until the new one lands
    await expect(page.locator(".sheet-body")).toHaveAttribute("data-busy", "1");
    await expect(page.getByTestId("print-go")).toBeEnabled({ timeout: 30_000 });
    expect(JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!).mode).toBe("tight");
  });
});
