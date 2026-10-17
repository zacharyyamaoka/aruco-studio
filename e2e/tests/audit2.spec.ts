// The 2026-10-17 audit's Studio findings, each on the real server:
// * a split list's <id>.<face> features: the next new tag takes a fresh id
//   and is the only one selected; an edit goes to it alone;
// * Open lists the examples (opened as a copy, the repo's file untouched),
//   the recent files and a folder;
// * Send says when the tags were planned for another nozzle, and offers the
//   printers that match;
// * a rectangular hole's W x H typed in the shape inspector;
// * a ChArUco label on Position auto reads "In a black square".
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, ROOT, choose, freshFile, idle, openExample, probe, readFile, shot, tab } from "./helpers";

const split = JSON.stringify({
  schema: "arucostudio.scene/2", name: "split",
  sketches: [{ id: "sk", shapes: [{ id: "rect1", rect: [60, 40] }] }],
  features: [
    { id: "body1", extrude: "rect1", height: 20 },
    { id: "tag1.front", aruco: "body1.front", layout: "single" },
    { id: "tag1.right", aruco: "body1.right", layout: "single" },
  ],
}, null, 1) + "\n";

test("a new tag after a split list takes a fresh id and is selected alone", async ({ page }) => {
  const file = await freshFile(page, "e2e-audit-split", split);
  await page.keyboard.press("Escape");
  await page.evaluate(() => (window as any).__studio.store.getState().setCamera({ cx: 90, cy: 0 }));
  await page.keyboard.press("c");
  await page.keyboard.type("30");
  await page.keyboard.press("Enter");
  await idle(page);
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await idle(page);
  const st = await probe(page);
  expect(st.sel).toEqual(["tag2"]);                                      // never "tag1" again, never 3 tags
  const mine = st.tags.find((t: any) => t.name === "tag2").ids;
  const others = st.tags.filter((t: any) => t.name !== "tag2").flatMap((t: any) => t.ids);
  expect(mine.filter((i: number) => others.includes(i))).toEqual([]);  // the new tag took the next free id
  await choose(page, "settings.dictionary", "DICT_5X5_50");
  const f = readFile(file);
  const byId = Object.fromEntries(f.features.map((x: any) => [x.id, x]));
  expect(byId["tag2"].settings?.dictionary ?? byId["tag2"].dictionary).toBe("DICT_5X5_50");
  for (const old of ["tag1.front", "tag1.right"]) expect(byId[old].settings?.dictionary ?? byId[old].dictionary ?? null).not.toBe("DICT_5X5_50");
  await shot(page, "audit2_new_tag_after_split");
});

test("Open lists the examples (opened as a copy), the recent files and a folder", async ({ page }) => {
  const repoFile = path.join(ROOT, "examples", "forearm.arucostudio.json");
  const before = fs.readFileSync(repoFile);
  const first = await freshFile(page, "e2e-audit-open");
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-open").click();
  const dlg = page.getByTestId("dialog-open");
  await expect(dlg).toBeVisible();
  for (const ex of ["forearm", "plate_charuco", "sticker_sheet"]) await expect(dlg.locator(`[data-example="${ex}"]`)).toHaveCount(1);
  await expect(dlg.getByTestId("open-recent").locator(`[data-recent]`).first()).toBeVisible();
  await expect(dlg.getByTestId("open-dir")).not.toBeEmpty();
  await shot(page, "audit2_open_dialog");
  await dlg.locator('[data-example="forearm"]').click();
  await idle(page);
  await expect.poll(async () => (await probe(page)).tags.length).toBe(4);
  const opened = (await probe(page)).design.path as string;
  expect(path.resolve(opened)).not.toBe(path.resolve(repoFile));
  expect(opened.endsWith(".arucostudio.json")).toBeTruthy();
  expect(fs.readFileSync(repoFile).equals(before)).toBeTruthy();       // the repo's example untouched
  const files = await (await page.request.get(`${API}/api/design/files`)).json();
  expect(files.recent.map((r: any) => path.resolve(r.path))).toContain(path.resolve(opened));
  expect(files.recent.map((r: any) => path.resolve(r.path))).toContain(path.resolve(first));
});

test("Send says the tags were planned for another nozzle and offers the printers that match", async ({ page }) => {
  const printers = await (await page.request.get(`${API}/api/prusa/printers`)).json();
  const cur = printers.printers.find((p: any) => p.current);
  await openExample(page, "e2e-audit-send", "forearm.arucostudio.json");              // planned for 0.6
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-send").click();
  await expect(page.getByTestId("dialog-send")).toBeVisible();
  await expect(page.locator('.kit-select[data-path="send.printer"]')).toHaveAttribute("data-value", cur.name);   // M8b2.3 kept
  const match = printers.printers.filter((p: any) => Math.abs(p.printer.nozzle_mm - 0.6) < 1e-6);
  if (Math.abs(cur.printer.nozzle_mm - 0.6) < 1e-6) {
    await expect(page.getByTestId("send-mismatch")).toHaveCount(0);
    return;
  }
  const line = page.getByTestId("send-mismatch");
  await expect(line).toBeVisible();
  await expect(line).toContainText("0.6 mm nozzle");
  await expect(line).toContainText(`${cur.printer.nozzle_mm} mm nozzle`);
  await shot(page, "audit2_send_mismatch");
  if (match.length) {
    await page.getByTestId(`send-pick-${match[0].name}`).click();
    await expect(page.locator('.kit-select[data-path="send.printer"]')).toHaveAttribute("data-value", match[0].name);
    await expect(page.getByTestId("send-mismatch")).toHaveCount(0);
  }
  await page.getByTestId("send-close").click();
});

test("a rectangular hole's W x H are typed in the shape inspector", async ({ page }) => {
  const file = await freshFile(page, "e2e-audit-rhole", JSON.stringify({
    schema: "arucostudio.scene/2", name: "rhole",
    sketches: [{ id: "sk", shapes: [{ id: "rect1", rect: [40, 30], holes: [{ rect: [10, 6] }] }] }], features: [],
  }, null, 1) + "\n");
  await page.evaluate(() => (window as any).__studio.store.getState().setShapeSel(["rect1"]));
  await idle(page);
  const w = page.locator('input[data-path="hole.0.w"]');
  await expect(w).toBeVisible();
  await w.click();
  await w.fill("12");
  await w.press("Enter");
  await idle(page);
  const h = page.locator('input[data-path="hole.0.h"]');
  await h.click();
  await h.fill("7");
  await h.press("Enter");
  await idle(page);
  expect(readFile(file).sketches[0].shapes[0].holes[0].rect).toEqual([12, 7]);
  await shot(page, "audit2_rect_hole_size");
});

test("a ChArUco label on Position auto reads In a black square", async ({ page }) => {
  await openExample(page, "e2e-audit-place", "plate_charuco.arucostudio.json");
  await page.evaluate(() => (window as any).__studio.store.getState().select("tag"));
  await idle(page);
  await tab(page, "label");
  await expect(page.locator('.kit-select[data-path="settings.label.place"]').first()).toHaveAttribute("data-value", "black");
  await expect(page.locator('.kit-select[data-path="settings.label.place"] .kit-select-trigger').first()).toContainText("In a black square");
});
