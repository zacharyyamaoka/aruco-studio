// M8b2.1: the kit. No Fusion token left in the Studio's code; every panel
// screenshotted in light (the default) and in dark; every row 24 px tall at
// the default density. The kit is studio/packages/bam-ui (@bam/ui).
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { ROOT, SCREENS, add, choose, freshFile, idle, palette, probe } from "./helpers";

function files(dir: string): string[] {
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...files(p));
    else if (/\.(tsx?|css|html)$/.test(e.name)) out.push(p);
  }
  return out;
}

/** Every kit row on screen is 24 px tall: -> the ones that are not. */
async function badRows(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const out: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>(".kit-row, tr[data-ids-row]"))) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || getComputedStyle(el).visibility === "hidden") continue;
      if (Math.abs(r.height - 24) > 0.5) out.push(`${el.closest("[data-row]")?.getAttribute("data-row") ?? el.getAttribute("data-ids-row") ?? el.className}: ${r.height}`);
    }
    return out;
  });
}

async function snap(page: Page, theme: string, panel: string, rows: Record<string, number>) {
  await idle(page);
  await page.waitForTimeout(200);
  expect(await badRows(page), `${panel} (${theme})`).toEqual([]);
  rows[panel] = await page.locator(".kit-row:visible").count();
  await page.screenshot({ path: path.join(SCREENS, `m8b2_kit_${panel}_${theme}.png`) });
}

test("M8b2.1 no Fusion token; every panel in light and dark; every row 24 px", async ({ page }) => {
  // the code: no Fusion blue, no Artifakt
  const src = [...files(path.join(ROOT, "studio", "src")), ...files(path.join(ROOT, "studio", "packages", "bam-ui", "src")), path.join(ROOT, "studio", "index.html")];
  const hits = src.filter((f) => /#0696d7|Artifakt/i.test(fs.readFileSync(f, "utf-8")));
  expect(hits).toEqual([]);
  expect(fs.existsSync(path.join(ROOT, "studio", "packages", "bam-ui", "package.json"))).toBeTruthy();
  expect(fs.existsSync(path.join(ROOT, "studio", "src", "kit"))).toBeFalsy();

  // light by default (nothing remembered in a fresh browser)
  await freshFile(page, "e2e-kit");
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
  const lightBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  // a scene with both kinds
  await add(page, "single");
  const t3 = (await probe(page)).sel[0];
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await choose(page, "new.preset", "Sticker · Letter · 600 dpi");
  await add(page, "single");
  await page.locator(`[data-ids-row="${t3}"]`).click();
  await idle(page);

  const rows: Record<string, Record<string, number>> = { light: {}, dark: {} };
  for (const theme of ["light", "dark"]) {
    if (theme === "dark") {
      await page.getByTestId("theme").click();
      expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("dark");
      expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).not.toBe(lightBg);
    }
    const r = rows[theme];
    await page.locator(`[data-ids-row="${t3}"]`).click();
    await page.locator('[role="tab"][data-tab="marker"]').click();
    await snap(page, theme, "inspector_marker", r);
    for (const t of ["heights", "print", "label", "advanced"]) {
      await page.locator(`[role="tab"][data-tab="${t}"]`).click();
      await snap(page, theme, `inspector_${t}`, r);
    }
    await page.getByTestId("aruco-shape").click();
    await snap(page, theme, "shape", r);
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await snap(page, theme, "newtag", r);
    await page.getByTestId("view-3d").click();
    await snap(page, theme, "3d", r);
    await page.getByTestId("view-2d").click();
    await page.getByTestId("menu-export").click();
    await snap(page, theme, "menu_export", r);
    await page.keyboard.press("Escape");
    await page.getByTestId("library-btn").first().click();
    await page.getByTestId("library").locator('[data-coll="printers"]').click();
    await page.getByTestId("library").locator('.card[data-card^="printer:"]').first().click();
    await snap(page, theme, "library_printers", r);
    await page.getByTestId("library").locator('[data-coll="builtin"]').click();
    await snap(page, theme, "library", r);
    await page.getByTestId("lib-cancel").click();
    await page.getByTestId("menu-export").click();
    await page.getByTestId("export-sheet").click();
    await expect(page.getByTestId("dialog-sheet")).toBeVisible();
    await expect(page.locator('[data-testid="sheet-preview"] svg')).toHaveCount(1);
    await snap(page, theme, "sheet", r);
    await page.getByTestId("sheet-close").click();
    await page.getByTestId("menu-export").click();
    await page.getByTestId("export-send").click();
    await expect(page.locator('.kit-select[data-path="send.printer"]')).not.toHaveAttribute("data-value", "");
    await snap(page, theme, "send", r);
    await page.getByTestId("send-close").click();
    await page.keyboard.press("s");
    await expect(page.getByTestId("palette")).toBeVisible();
    await snap(page, theme, "palette", r);
    await page.keyboard.press("Escape");
    await palette(page, "File drawer");
    await snap(page, theme, "drawer_file", r);
    await page.keyboard.press("?");
    await snap(page, theme, "drawer_keys", r);
    await page.keyboard.press("?");
    await page.evaluate(() => (window as any).__studio.store.getState().setDrawer(null));
    await idle(page);
  }
  for (const t of ["light", "dark"]) for (const [k, n] of Object.entries(rows[t])) if (k.startsWith("inspector")) expect(n, `${t} ${k}`).toBeGreaterThan(3);
  fs.writeFileSync(path.join(ROOT, "e2e", ".tmp", "m8b2_numbers_kit.json"), JSON.stringify(rows, null, 1));
  // back to light for the specs after
  await page.getByTestId("theme").click();
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("light");
});
