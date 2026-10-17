// The UI fixes after the M3 audit (docs/status/AUDIT.md): each bar reads the
// DOM, the store (window.__studio) or the 3D view's own numbers
// (window.__studio3d), never a picture.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import { API, add, fresh, freshFile, idle, palette, probe, readFile, shot, tab } from "./helpers";

async function ids(page: any, name: string): Promise<number[]> {
  return (await probe(page)).tags.find((t: any) => t.name === name).ids;
}

async function typeFirst(page: any, name: string, v: string) {
  const inp = page.locator(`input[data-path="override:${name}"]`);
  await inp.fill(v);
  await inp.press("Enter");
  await idle(page);
}

test("F1 F5 F15: new tags get free ids; a typed first id is used at once or refused on its row", async ({ page }) => {
  await fresh(page, "e2e-audit-ids");
  await add(page, "single");
  await add(page, "grid");
  await add(page, "charuco");
  const all = [...(await ids(page, "tag1")), ...(await ids(page, "board1")), ...(await ids(page, "charuco1"))];
  expect(new Set(all).size).toBe(all.length);                        // F5: no duplicates out of the box
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");

  await typeFirst(page, "tag1", "20");                                // F1: used at once
  expect(await ids(page, "tag1")).toEqual([20]);
  await expect(page.getByTestId("status")).toContainText("tag1: first id 20, ids 20");

  const before = await ids(page, "board1");
  await typeFirst(page, "board1", "500");                             // past the dictionary
  expect(await ids(page, "board1")).toEqual(before);
  const msg = page.locator('[data-ids-msg="board1"] .issue[data-level="error"]');
  await expect(msg).toContainText("not in DICT_");
  await expect(msg).not.toContainText("|");                           // F15: no field marker
  await expect(page.locator('[data-ids-row="board1"] td.first')).toHaveClass(/bad/);
  await expect(page.getByTestId("status")).not.toContainText("typed");
  await typeFirst(page, "board1", "-3");
  await expect(msg).toContainText("0 or more");
  await typeFirst(page, "board1", "30");
  await expect(page.locator('[data-ids-msg="board1"]')).toHaveCount(0);
  expect((await ids(page, "board1"))[0]).toBe(30);
  await shot(page, "audit_ids_first");
});

test("F3 F18: Escape closes an open dropdown only; Tab on a focused button moves focus", async ({ page }) => {
  await fresh(page, "e2e-audit-keys");
  await add(page, "single");
  expect((await probe(page)).sel).toEqual(["tag1"]);
  await page.locator('.dd[data-path="preset"] .dd-btn').click();
  await expect(page.locator('.dd[data-path="preset"].open')).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(page.locator('.dd[data-path="preset"].open')).toHaveCount(0);
  expect((await probe(page)).sel).toEqual(["tag1"]);                 // still selected
  await page.keyboard.press("Escape");                               // a second Escape: select none
  expect((await probe(page)).sel).toEqual([]);

  await page.getByTestId("fit").focus();
  await page.keyboard.press("Tab");
  await idle(page);
  expect((await probe(page)).view).toBe("2d");
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.keyboard.press("Tab");
  await idle(page);
  expect((await probe(page)).view).toBe("3d");
});

test("F4 F6: a verify row goes stale on a change; a locked tag's ink fields take no input", async ({ page }) => {
  await fresh(page, "e2e-audit-verify");
  await add(page, "single");
  await palette(page, "Verify");                                     // V is the Select tool since M8b1
  const row = page.locator('[data-verify-row="tag1"]');
  await expect(row).toHaveAttribute("data-stale", "0");
  await expect(row.locator("td[data-ok]")).toHaveAttribute("data-ok", "1");
  const id = page.locator('input[data-path="numbers.marker_id"]');
  await id.fill("21");
  await id.press("Enter");
  await idle(page);
  await expect(row).toHaveAttribute("data-stale", "1");
  await expect(row.locator("td[data-ok]")).toHaveText("not verified since the change");
  await expect(page.getByTestId("verify-stale")).toBeVisible();
  await page.getByTestId("reverify").click();
  await idle(page);
  await expect(row).toHaveAttribute("data-stale", "0");
  await expect(row.locator("td[data-ids-read]")).toHaveAttribute("data-ids-read", "21");

  await page.getByTestId("lock").click();
  await idle(page);
  await expect(page.getByTestId("locked-note")).toBeVisible();
  await expect(id).toBeDisabled();
  await expect(page.locator('.dd[data-path="settings.dictionary"] .dd-btn')).toBeDisabled();
  await tab(page, "label");
  await expect(page.locator('input[data-path="settings.label.on"]')).toBeDisabled();
  await expect(page.locator('.insp-head input[data-path="name"]')).toBeEnabled();
  await expect(page.locator('input[data-path="override:tag1"]')).toBeDisabled();
  await shot(page, "audit_locked");
});

test("F7: a label message is one short line, the plan's words in its tooltip", async ({ page }) => {
  await fresh(page, "e2e-audit-label");
  await add(page, "single");
  await tab(page, "label");
  await page.locator('.tog:has(input[data-path="settings.label.on"])').click();
  await idle(page);
  const err = page.locator('[data-tab-body="label"] .issue[data-level="error"]');
  await expect(err).toHaveCount(1);
  await expect(err).toHaveText(/^No room for '#\d+', even at [\d.]+ mm letters: a finer label nozzle or a smaller marker makes room$/);
  expect(await err.getAttribute("data-text")).toContain("Label not built");
  expect(await err.getAttribute("title")).toContain("Label not built");
  const texts = await page.locator('[data-tab-body="label"] .issue').evaluateAll((els) => els.map((e) => e.textContent));
  expect(new Set(texts).size).toBe(texts.length);                    // nothing twice
  await expect(page.getByTestId("summary")).toHaveText(/^⚠ [^:]+: No room for/);
  await shot(page, "audit_label_short");
});

test("F12 F13 (M8b1): no unsaved changes, every change is in the file; overlapping tags are a scene issue", async ({ page, request }) => {
  const file = await freshFile(page, "e2e-audit-file");
  await add(page, "single");
  await add(page, "single");
  // nothing waits to be saved: the file on disk has both tags already
  expect(readFile(file).features.filter((f: any) => f.aruco).map((f: any) => f.id)).toEqual(["tag1", "tag2"]);
  await page.keyboard.press("Control+s");
  await expect(page.getByTestId("status")).toContainText("saved as you typed");

  // tag2 moved 2 mm onto tag1
  const t1 = (await probe(page)).tags.find((t: any) => t.name === "tag1");
  await request.patch(`${API}/api/scene/tags/tag2`, { data: { x_mm: t1.x_mm + 38 } });
  await page.evaluate(() => (window as any).__studio.store.getState().refresh());
  await idle(page);
  const banner = page.getByTestId("scene-issues");
  await expect(banner).toContainText("tag2 overlaps tag1");
  await expect(page.locator(".overlapbox")).toHaveCount(2);
  await page.getByTestId("menu-verify").click();
  await page.getByTestId("verify-scene").click();
  await idle(page);
  await expect(page.getByTestId("verify-overlaps")).toContainText("tag2 overlaps tag1");
  await shot(page, "audit_overlap");

  // a change is in the file at once; New asks nothing (the old scene is its file)
  const was = fs.readFileSync(file, "utf-8");
  await page.locator('[data-ids-row="tag1"]').click();
  await page.keyboard.press("ArrowUp");
  await idle(page);
  expect(fs.readFileSync(file, "utf-8")).not.toBe(was);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-new").click();
  await expect(page.getByTestId("dialog-new")).toBeVisible();
  await page.getByTestId("dialog-name").fill(`e2e-audit-empty-${Date.now()}`);
  await page.getByTestId("dialog-ok").click();
  await idle(page);
  expect((await probe(page)).tags.length).toBe(0);
  expect(readFile(file).features.filter((f: any) => f.aruco)).toHaveLength(2);
});

test("F16: the Library's search looks in every collection", async ({ page }) => {
  await fresh(page, "e2e-audit-lib");
  await page.getByTestId("library-btn").first().click();
  const lib = page.getByTestId("library");
  await lib.locator('[data-coll="recent"]').click();
  await lib.getByTestId("lib-search").fill("0.6");
  await expect(lib.getByTestId("lib-count")).toHaveAttribute("data-scope", "all");
  const n = Number((await lib.getByTestId("lib-count").textContent())!.split(" of ")[0]);
  expect(n).toBeGreaterThan(0);
  await lib.getByTestId("lib-cancel").click();
});

test("F17: 3D labels every tag, keeps the axes unstretched by the z scale, sizes the grid to the scene", async ({ page }) => {
  await fresh(page, "e2e-audit-3d");
  await add(page, "single");
  await add(page, "grid");
  await add(page, "charuco");
  await page.getByTestId("view-3d").click();
  await idle(page);
  await page.waitForTimeout(300);
  let v = await page.evaluate(() => (window as any).__studio3d);
  expect(v.labels.length).toBe(3);
  expect(v.labels.some((t: string) => t.startsWith("board1 #"))).toBeTruthy();
  const box = v.box;
  expect(v.gridMm).toBeGreaterThanOrEqual(Math.max(box.x1 - box.x0, box.y1 - box.y0));
  expect(v.scaleBarMm).toBe(10);
  await page.getByTestId("zscale").selectOption("5");
  await idle(page);
  await page.waitForTimeout(200);
  v = await page.evaluate(() => (window as any).__studio3d);
  expect(v.rootScaleZ).toBe(5);
  expect(v.axes).toBe(3);
  for (const s of v.arrowWorldScaleZ) expect(Math.abs(s - 1)).toBeLessThan(1e-9);
  await shot(page, "audit_3d_labels_z5");
});
