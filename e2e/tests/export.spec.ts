// M3.9 / ST-T-UI-7: Verify (OpenCV reads every tag; its pose 25 deg off
// within 0.1 mm) and the sheet; Export the 1:1 SVG sheet, the PDF sticker
// sheet (OpenCV reads every id off it), STL, plan JSON and the scene file:
// the files exist where the server says, and download.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { add, detect, fresh, idle, probe, shot } from "./helpers";

async function exportVia(page: any, item: string) {
  const dl = page.waitForEvent("download");
  await page.getByTestId("menu-export").click();
  await page.getByTestId(item).click();
  const d = await dl;
  await idle(page);
  const st = await page.getByTestId("status").textContent();
  const m = /exported (\d+) files? to (.+)$/.exec(st || "");
  expect(m, st || "").not.toBeNull();
  return { dir: m![2].trim(), n: Number(m![1]), download: d };
}

test("verify every tag and the sheet; export SVG, STL, plan JSON, the scene", async ({ page }) => {
  const scene = `e2e-export-${Date.now()}`;
  await fresh(page, scene);
  await add(page, "single");
  await add(page, "grid");
  await add(page, "charuco");
  await page.getByTestId("renumber").click();
  await idle(page);
  const tags = (await probe(page)).tags;

  // Verify every tag (nothing selected = all)
  await page.keyboard.press("Escape");
  await page.getByTestId("menu-verify").click();
  await page.getByTestId("verify-sel").click();
  await idle(page);
  const table = page.getByTestId("verify-table");
  await expect(table).toBeVisible();
  for (const t of tags) {
    const row = page.locator(`[data-verify-row="${t.name}"]`);
    await expect(row.locator("td[data-ok]")).toHaveAttribute("data-ok", "1");
    await expect(row.locator("td[data-ids-read]")).toHaveAttribute("data-ids-read", t.ids.join(","));
    const pnp = Number(await row.locator("td[data-pnp-mm]").getAttribute("data-pnp-mm"));
    expect(pnp).toBeLessThan(0.1);
    await expect(row.locator("img.vimg")).toBeVisible();
  }
  await shot(page, "verify");

  // the sheet: every marker where the scene puts it
  await page.getByTestId("menu-verify").click();
  await page.getByTestId("verify-scene").click();
  await idle(page);
  const sv = page.getByTestId("verify-scene-report");
  await expect(sv).toContainText("every marker found");
  const nMarkers = tags.reduce((a: number, t: any) => a + t.ids.length, 0);
  await expect(sv.locator("[data-found]")).toHaveAttribute("data-found", String(nMarkers));

  // exports: files under the server's exports/<scene>/, and a download
  const svg = await exportVia(page, "export-svg");
  expect(svg.download.suggestedFilename()).toBe("sheet.svg");
  const sheet = fs.readFileSync(path.join(svg.dir, "sheet.svg"), "utf-8");
  expect(sheet.startsWith("<svg")).toBeTruthy();
  expect(sheet).toMatch(/width="[\d.]+mm"/);
  for (const t of tags) expect(sheet).toContain(`data-tag="${t.name}"`);

  const pdf = await exportVia(page, "export-pdf");
  expect(pdf.download.suggestedFilename()).toBe("sheet.pdf");
  const pdfFile = path.join(pdf.dir, "sheet.pdf");
  expect(fs.readFileSync(pdfFile).subarray(0, 5).toString("latin1")).toBe("%PDF-");
  const dict = String((await (await page.request.get("http://127.0.0.1:5360/api/scene?plans=1")).json()).tags[0].plan.marker.dictionary);
  const allIds = tags.flatMap((t: any) => t.ids).sort((a: number, b: number) => a - b);
  expect(detect(pdfFile, dict)).toEqual(allIds);

  const stl = await exportVia(page, "export-stl");
  expect(stl.n).toBe(tags.length);
  for (const t of tags) {
    const buf = fs.readFileSync(path.join(stl.dir, `${t.name}.stl`));
    const n = buf.readUInt32LE(80);
    expect(n).toBeGreaterThan(0);
    expect(buf.length).toBe(84 + 50 * n);
  }
  const plans = await exportVia(page, "export-plan");
  for (const t of tags) {
    const p = JSON.parse(fs.readFileSync(path.join(plans.dir, `${t.name}.json`), "utf-8"));
    expect(p.schema).toBe("arucostudio.tagplan/1");
    expect(p.ids).toEqual(t.ids);
  }
  const file = await exportVia(page, "export-json");
  const doc = JSON.parse(fs.readFileSync(path.join(file.dir, `${scene}.arucostudio.json`), "utf-8"));
  expect(doc.schema).toBe("arucostudio.scene/2");   // M8a: the design file (Merge 1)
  expect(doc.features.filter((f: any) => "aruco" in f).map((f: any) => f.id)).toEqual(tags.map((t: any) => t.name));

  // one tag alone
  await page.locator('[data-ids-row="board1"]').click();
  const dl = page.waitForEvent("download");
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-tag-svg").click();
  expect((await dl).suggestedFilename()).toBe("board1.svg");
});
