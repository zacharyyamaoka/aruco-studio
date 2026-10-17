// M8b2.3 Send to PrusaSlicer… and M8b2.4 the Printers collection. The
// server reads the M8c fixture (tests/fixtures/prusaslicer_m8c: Zach's five
// physical printers with placeholder hosts), never PrusaSlicer's folder.
// PrusaSlicer is never opened: window.__studio.sendOpen = false, and the
// test refuses any Send whose body asks to open it.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import { API, choose, freshFile, idle, openExample, shot } from "./helpers";

test("M8b2.3 Send to PrusaSlicer…: the current printer first, one POST with open: false, the project written", async ({ page }) => {
  const printers = await (await page.request.get(`${API}/api/prusa/printers`)).json();
  expect(printers.found).toBeTruthy();
  const current = printers.current.physical;
  expect(current).toBeTruthy();
  await openExample(page, "e2e-send", "forearm.arucostudio.json");
  await page.evaluate(() => { (window as any).__studio.sendOpen = false; });
  const posts: any[] = [];
  await page.route("**/api/scene/send/prusaslicer", async (route) => {
    const body = route.request().postDataJSON();
    posts.push(body);
    if (body.open !== false) { await route.abort(); return; }          // never launch PrusaSlicer from a test
    await route.continue();
  });
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-send").click();
  const dlg = page.getByTestId("dialog-send");
  await expect(dlg).toBeVisible();
  await expect(page.locator('.kit-select[data-path="send.printer"]')).toHaveAttribute("data-value", current);
  await expect(page.locator('.kit-select[data-path="send.print"]')).not.toHaveAttribute("data-value", "");
  await shot(page, "m8b2_send_dialog");
  await page.getByTestId("send-go").click();
  await expect(page.getByTestId("send-answer")).toBeVisible({ timeout: 60_000 });
  await idle(page);
  expect(posts.length).toBe(1);
  expect(posts[0].open).toBe(false);
  expect(posts[0].printer).toBe(current);
  const project = await page.getByTestId("send-answer").getAttribute("data-project");
  expect(project).toBeTruthy();
  expect(fs.existsSync(project!)).toBeTruthy();
  expect(project!.toLowerCase().endsWith(".3mf")).toBeTruthy();
  await shot(page, "m8b2_send_done");
  await page.getByTestId("send-close").click();
  await page.unroute("**/api/scene/send/prusaslicer");

  // a scene without a 3D tag: the item is off, "nothing to slice"
  await openExample(page, "e2e-send-stickers", "sticker_sheet.arucostudio.json");
  await page.getByTestId("menu-export").click();
  const item = page.getByTestId("export-send");
  await expect(item).toHaveAttribute("data-disabled", "");
  await expect(item).toContainText("nothing to slice");
  await shot(page, "m8b2_send_disabled");
  await page.keyboard.press("Escape");
});

test("M8b2.4 the Printers collection: a card per physical printer, its fitting prints, Select makes the preset", async ({ page }) => {
  const printers = await (await page.request.get(`${API}/api/prusa/printers`)).json();
  await freshFile(page, "e2e-printers");
  await page.getByTestId("library-btn").first().click();
  const lib = page.getByTestId("library");
  await expect(lib).toBeVisible();
  await lib.locator('[data-coll="printers"]').click();
  const cards = lib.locator('.card[data-card^="printer:"]');
  await expect(cards).toHaveCount(printers.printers.length);
  for (const p of printers.printers) await expect(lib.locator(`.card[data-card="printer:${p.name}"]`)).toHaveCount(1);
  // the current pair is marked: its card, and its print among the choices
  const cur = printers.current.physical;
  await expect(lib.locator(`.card[data-card="printer:${cur}"]`)).toHaveAttribute("data-mark", "current");
  await lib.locator(`.card[data-card="printer:${cur}"]`).click();
  const curP = printers.printers.find((p: any) => p.name === cur);
  await expect(lib.locator("[data-choice]")).toHaveCount(curP.prints.length);
  if (curP.prints.some((x: any) => x.current)) await expect(lib.locator('[data-choice][data-current="1"]')).toHaveCount(1);
  await shot(page, "m8b2_printers_current");
  // a 0.6 printer with a print that fits: its prints are the card's choices; Select
  const p6 = printers.printers.find((p: any) => p.printer.nozzle_mm === 0.6 && p.prints.length > 0);
  expect(p6).toBeTruthy();
  await lib.locator(`.card[data-card="printer:${p6.name}"]`).click();
  await expect(lib.getByTestId("printer-info")).toHaveAttribute("data-printer", p6.name);
  await expect(lib.locator("[data-choice]")).toHaveCount(p6.prints.length);
  const pick = p6.prints[p6.prints.length - 1];
  await lib.locator(`[data-choice="printer:${p6.name}|${pick.name}"]`).click();
  await shot(page, "m8b2_printers_choice");
  await lib.getByTestId("lib-select").click();
  await idle(page);
  await expect(lib).toHaveCount(0);
  const made = await page.evaluate(() => (window as any).__studio.store.getState().newPreset);
  const presets = (await (await page.request.get(`${API}/api/presets`)).json()).items;
  const preset = presets.find((x: any) => x.name === made);
  expect(preset, made).toBeTruthy();
  expect(preset.preset.profile.nozzle_mm).toBe(0.6);                                       // the printer's nozzle
  expect(preset.preset.profile.layer_mm).toBeCloseTo(pick.layer_mm, 6);                    // the print's layers
  expect(preset.preset.profile.printer?.physical).toBe(p6.name);
  await expect(page.locator('.kit-select[data-path="new.preset"]')).toHaveAttribute("data-value", made);
  await choose(page, "new.preset", "Default");
});
