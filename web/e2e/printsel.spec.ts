// The Print dialog's pages in one scroll and Print's "Markers: All |
// Selected" (Zach, 2026-10-21: "make it just scroll down all in the main
// window, just like a normal PDF preview" and "add support for printing only
// the markers which are selected"). Nine 25 mm rectangles, one ArUco Extrude
// each; three of them selected by a right-drag box and a Shift+click. The
// stickers are counted from what the core drew (the SVG's cut paths, the
// PDF's stroked loops) and its placements, checked against CPython's
// web_api.sheet on the dialog's own request; sizes and scrolling are
// measured (getBoundingClientRect), never DOM presence alone.
// PRINTSEL_SHOTS=<dir> saves screenshots of the scrolling preview and Selected.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openMenu, openStudio, state, toClient } from "./helpers";

const ROOT = path.resolve(import.meta.dirname, "..", "..");
const PY = [path.join(ROOT, ".venv", "bin", "python"), path.join(ROOT, ".venv", "Scripts", "python.exe")].find((p) => fs.existsSync(p));
const SHOTS = process.env.PRINTSEL_SHOTS;
async function shot(page: Page, name: string): Promise<void> {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

/** A close-up of the side's bottom: the hint, Print and Download (and an open menu under them). */
async function closeShot(page: Page, name: string): Promise<void> {
  if (!SHOTS) return;
  const side = (await page.getByTestId("sheet-side").boundingBox())!;
  const top = (await page.getByTestId("sheet-stats").boundingBox())!;
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), clip: { x: side.x - 20, y: top.y - 8, width: side.width + 40, height: 230 } });
}

// a 3 x 3 grid of 25 mm squares, 10 mm apart (mm, y up)
const SIDE = 25;
const CELLS = [-50, -15, 20];
const GRID: [[number, number], [number, number]][] = CELLS.flatMap((y) => CELLS.map((x) => [[x, y], [x + SIDE, y + SIDE]] as [[number, number], [number, number]]));

/** Nine rectangles, every one selected by a right-drag box, A (one ArUco Extrude in each), OK. */
async function nine(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
  for (const [i, [a, b]] of GRID.entries()) {
    await page.keyboard.press("r");
    await dragWorld(page, a, b);
    expect((await state(page)).doc.shapes, `the rectangle from ${a} to ${b}`).toHaveLength(i + 1);
  }
  await page.keyboard.press("Escape");
  // fitted, then zoomed out: empty canvas all round the grid (multiselect.spec.ts)
  await page.keyboard.press("f");
  const [cx, cy] = await toClient(page, 0, 0);
  await page.mouse.move(cx, cy);
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(100);
  await rightDrag(page, [-65, -65], [60, 60]);
  expect((await state(page)).selection).toHaveLength(9);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
  const s = await state(page);
  expect(s.doc.features).toHaveLength(9);
  for (const f of s.doc.features) expect(s.plans[f.id]?.ids?.length, `${f.id} is planned`).toBeGreaterThan(0);
}

async function rightDrag(page: Page, from: [number, number], to: [number, number]): Promise<void> {
  const [ax, ay] = await toClient(page, ...from);
  const [bx, by] = await toClient(page, ...to);
  await page.mouse.move(ax, ay);
  await page.mouse.down({ button: "right" });
  for (let i = 1; i <= 10; i++) await page.mouse.move(ax + ((bx - ax) * i) / 10, ay + ((by - ay) * i) / 10);
  await page.mouse.up({ button: "right" });
}

/** The feature whose profile is the rectangle at grid cell `i`. */
async function featureAt(page: Page, i: number): Promise<{ id: string; rect: string; first_id: number }> {
  const s = await state(page);
  const [[x0, y0]] = GRID[i];
  const f = s.doc.features.find((f: any) => {
    const sh = s.doc.shapes.find((r: any) => r.id === f.profile.outer);
    return sh && Math.abs(sh.cx - (x0 + SIDE / 2)) < 1e-6 && Math.abs(sh.cy - (y0 + SIDE / 2)) < 1e-6;
  });
  expect(f, `a feature in cell ${i}`).toBeTruthy();
  return { id: f.id, rect: f.profile.outer, first_id: f.marker.first_id };
}

/** Select cells 0 and 1 with a right-drag box from empty canvas, then Shift+click cell 8's marker. */
async function selectThree(page: Page): Promise<{ id: string; rect: string; first_id: number }[]> {
  await page.keyboard.press("Escape");
  await rightDrag(page, [-60, -60], [15, -20]);
  const f8 = await featureAt(page, 8);
  const ink = (await page.locator(`[data-marker="${f8.id}"] [data-marker-black]`).first().boundingBox())!;
  await page.keyboard.down("Shift");
  await page.mouse.click(ink.x + ink.width / 2, ink.y + ink.height / 2);
  await page.keyboard.up("Shift");
  const three = [await featureAt(page, 0), await featureAt(page, 1), f8];
  expect([...(await state(page)).selection].sort()).toEqual(three.map((f) => f.rect).sort());
  return three;
}

async function openSheet(page: Page): Promise<void> {
  await page.keyboard.press("s");
  await expect(page.getByTestId("print-dialog")).toBeVisible();
  await expect(page.locator('[data-testid="print-page"] svg').first()).toBeVisible({ timeout: 45_000 });
  await settled(page);
}

async function settled(page: Page): Promise<Record<string, any>> {
  await idle(page);
  await expect(page.locator(".sheet-body")).toHaveAttribute("data-busy", "0");
  return JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!);
}

/** CPython's web_api.sheet on the same request: the core's own answer. */
function core(request: Record<string, unknown>): { pages: number; placements: unknown[] } {
  expect(PY, "the repo's .venv python").toBeTruthy();
  const code = "import json, sys\nfrom aruco_studio import web_api\nsys.stdout.write(web_api.call('sheet', sys.stdin.read()))";
  const r = spawnSync(PY!, ["-c", code], { cwd: ROOT, input: JSON.stringify({ ...request, date: "2026-10-21" }), encoding: "utf8",
    maxBuffer: 1 << 28, env: { ...process.env, PYTHONPATH: ROOT, PYTHONDONTWRITEBYTECODE: "1" } });
  expect(r.status, r.stderr).toBe(0);
  const out = JSON.parse(r.stdout);
  expect(out.error).toBeUndefined();
  return out.result;
}

/** The stickers on the sheet on screen: its placements, and the distinct cut outlines drawn on its pages. */
async function stickers(page: Page): Promise<{ placed: number; cut: number }> {
  const placed = Number(await page.getByTestId("sheet-stats").getAttribute("data-placed"));
  const cut = await page.locator('[data-testid="print-page"] svg').evaluateAll((svgs) =>
    new Set(svgs.flatMap((s) => [...s.querySelectorAll("path[data-cut]")].map((p) => p.getAttribute("data-cut")))).size);
  return { placed, cut };
}

/** The stickers in a PDF: one stroked cut loop each ("<grey> G <width> w" opens one, core/sheet.py _pdf_ops). */
function pdfStickers(file: string): { pages: number; loops: number } {
  const pdf = fs.readFileSync(file);
  let loops = 0, at = 0;
  for (;;) {
    const s = pdf.indexOf("stream\n", at);
    if (s < 0) break;
    const e = pdf.indexOf("\nendstream", s);
    const body = zlib.inflateSync(pdf.subarray(s + 7, e)).toString("latin1");
    loops += body.split("\n").filter((l) => /^[\d.]+ G [\d.]+ w$/.test(l)).length;
    at = e + 10;
  }
  const pages = Number(/\/Type \/Pages \/Kids \[[^\]]*\] \/Count (\d+)/.exec(pdf.toString("latin1"))![1]);
  return { pages, loops };
}

/** The dialog's Download menu, then its `item` (print-pdf / print-svg). */
async function fromMenu(page: Page, item: string): Promise<void> {
  await page.getByTestId("print-download").click();
  await page.getByTestId(item).click();
}

async function download(page: Page, click: () => Promise<void>): Promise<string> {
  const [dl] = await Promise.all([page.waitForEvent("download"), click()]);
  const file = test.info().outputPath(dl.suggestedFilename());
  await dl.saveAs(file);
  return file;
}

test.describe(`Print: one scroll of pages, and the selected markers (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the pages and stickers are the real core's");

  test("a · a multi-page sheet: every page in one scroll, a label each, no tabs; scrolling reaches the last page", async ({ page }) => {
    test.setTimeout(240_000);
    await nine(page);
    await page.keyboard.press("Escape");
    await openSheet(page);
    await expect(page.getByTestId("sheet-which")).toHaveAttribute("data-value", "all");
    // a wide gap: a few stickers a page
    const gap = page.locator('[data-testid="sheet-gap"] input');
    await gap.fill("100");
    await gap.press("Enter");
    const request = await settled(page);
    const pages = Number(await page.getByTestId("sheet-pages").getAttribute("data-value"));
    expect(pages, "the core's page count").toBe(core(request).pages);
    expect(pages, "a long sheet").toBeGreaterThanOrEqual(3);

    // every page, no tab buttons
    const dlg = page.getByTestId("print-dialog");
    await expect(page.getByTestId("sheet-page")).toHaveCount(pages);
    await expect(page.getByTestId("print-page")).toHaveCount(pages);
    await expect(dlg.getByRole("tab")).toHaveCount(0);
    await expect(page.getByTestId("sheet-page-tab")).toHaveCount(0);
    await expect(page.getByTestId("sheet-page-label")).toHaveText(Array.from({ length: pages }, (_, i) => `Page ${i + 1} of ${pages}`));
    // all in one scroll container: the stage, which scrolls
    const scrollers = await page.getByTestId("print-page").evaluateAll((els) => els.map((el) => {
      let p = el.parentElement;
      while (p && !(getComputedStyle(p).overflowY === "auto" || getComputedStyle(p).overflowY === "scroll")) p = p.parentElement;
      return p?.getAttribute("data-testid") ?? null;
    }));
    expect(scrollers).toEqual(Array(pages).fill("print-stage"));
    const stage = page.getByTestId("print-stage");
    const dims = await stage.evaluate((el) => ({ sh: el.scrollHeight, ch: el.clientHeight, top: el.scrollTop }));
    expect(dims.sh, "the pages overflow the stage").toBeGreaterThan(dims.ch * 2);
    expect(dims.top).toBe(0);
    // the pages stack: each one under the last, at true size (Actual size)
    const boxes = await page.getByTestId("print-page").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().toJSON()));
    for (let i = 1; i < boxes.length; i++) expect(boxes[i].top, `page ${i + 1} is under page ${i}`).toBeGreaterThan(boxes[i - 1].bottom);
    const mm = (await page.getByTestId("print-page").first().getAttribute("data-page-mm"))!.split("x").map(Number);
    expect(boxes[0].width).toBeCloseTo(mm[0] * 96 / 25.4, 0);
    // a far page is not drawn until it nears the view
    const last = page.getByTestId("print-page").last();
    await expect(last).toHaveAttribute("data-drawn", "0");
    await shot(page, "printsel-scroll-top");

    // halfway: the gap between pages 1 and 2, and page 2's label
    await stage.evaluate((el) => {
      const two = el.querySelectorAll<HTMLElement>('[data-testid="sheet-page"]')[1];
      el.scrollTop += two.getBoundingClientRect().top - el.getBoundingClientRect().top - el.clientHeight / 2;
    });
    await expect(page.getByTestId("sheet-page-label").nth(1)).toBeInViewport();
    await shot(page, "printsel-scroll-between");
    await stage.evaluate((el) => { el.scrollTop = 0; });

    // scroll by wheel to the end: the last page comes into view, drawn
    const sb = (await stage.boundingBox())!;
    await page.mouse.move(sb.x + sb.width / 2, sb.y + sb.height / 2);
    for (let i = 0; i < 60; i++) {
      const at = await stage.evaluate((el) => el.scrollTop + el.clientHeight >= el.scrollHeight - 1);
      if (at) break;
      await page.mouse.wheel(0, 600);
      await page.waitForTimeout(30);
    }
    const end = await stage.evaluate((el) => ({ top: el.scrollTop, max: el.scrollHeight - el.clientHeight }));
    expect(end.top).toBeGreaterThan(0);
    expect(end.top).toBeCloseTo(end.max, 0);
    await expect(last).toHaveAttribute("data-drawn", "1");
    await expect(last.locator("svg")).toBeVisible();
    const lb = (await last.boundingBox())!, view = (await stage.boundingBox())!;
    expect(lb.y + lb.height, "the last page's bottom is in the stage").toBeLessThanOrEqual(view.y + view.height + 1);
    expect(lb.y + lb.height).toBeGreaterThan(view.y);
    // and it is the core's last page
    expect(await last.locator("svg text", { hasText: `page ${pages}/${pages}` }).count()).toBe(1);
    await shot(page, "printsel-scroll-end");
  });

  test("b · 3 of 9 selected (right-drag + Shift+click), S: Selected (3) is on, the sheet has 3 stickers; All gives 9", async ({ page }) => {
    test.setTimeout(240_000);
    await nine(page);
    const three = await selectThree(page);
    await openSheet(page);
    const which = page.getByTestId("sheet-which");
    await expect(which).toHaveAttribute("data-value", "selected");
    await expect(which.locator('[data-value="selected"]')).toHaveText("Selected (3)");
    await expect(which.locator('[data-value="selected"]')).toHaveAttribute("aria-checked", "true");
    await expect(which.locator('[data-value="all"]')).toHaveText("All (9)");
    const sel = await settled(page);
    expect(sel.items).toHaveLength(3);
    // the selection keeps its assigned ids
    expect(sel.items.map((i: any) => i.marker.first_id).sort()).toEqual(three.map((f) => f.first_id).sort());
    expect(await stickers(page)).toEqual({ placed: 3, cut: 3 });
    expect(core(sel).placements).toHaveLength(3);
    await shot(page, "printsel-selected");

    await which.locator('[data-value="all"]').click();
    await expect(which).toHaveAttribute("data-value", "all");
    const all = await settled(page);
    expect(all.items).toHaveLength(9);
    expect(core(all).placements).toHaveLength(9);
    expect(await stickers(page)).toEqual({ placed: 9, cut: 9 });
    await shot(page, "printsel-all");
    // and back
    await which.locator('[data-value="selected"]').click();
    expect((await settled(page)).items).toHaveLength(3);
    // the document's ids are as they were
    const s = await state(page);
    for (const f of three) expect(s.doc.features.find((x: any) => x.id === f.id).marker.first_id).toBe(f.first_id);
  });

  test("c · Download PDF with Selected: 3 stickers; with All: 9; Export › PDF with the 3 selected: 3", async ({ page }) => {
    test.setTimeout(240_000);
    await nine(page);
    await selectThree(page);
    await openSheet(page);
    await expect(page.getByTestId("sheet-which")).toHaveAttribute("data-value", "selected");
    const selPdf = pdfStickers(await download(page, () => fromMenu(page, "print-pdf")));
    expect(selPdf.loops, "the selected PDF's stickers").toBe(3);
    await page.getByTestId("sheet-which").locator('[data-value="all"]').click();
    await settled(page);
    const allPdf = pdfStickers(await download(page, () => fromMenu(page, "print-pdf")));
    expect(allPdf.loops, "every marker's sticker").toBe(9);
    // Download SVG: the page in view, of the choice
    await page.getByTestId("sheet-which").locator('[data-value="selected"]').click();
    await settled(page);
    const svg = fs.readFileSync(await download(page, () => fromMenu(page, "print-svg")), "utf8");
    expect(new Set([...svg.matchAll(/data-cut="([^"]+)"/g)].map((m) => m[1])).size).toBe(3);

    // the menu's Export › PDF, the 3 still selected
    await expect(page.getByTestId("print-svg")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("print-dialog")).toHaveCount(0);
    expect((await state(page)).selection).toHaveLength(3);
    const menu = await openMenu(page, "export");
    const exported = pdfStickers(await download(page, () => menu.getByTestId("cmd-pdf").click()));
    expect(exported.loops, "Export › PDF prints the selection").toBe(3);
  });

  test("e · Print and Download sit on one row, one height, at the side's width (1280 and 900 px wide)", async ({ page }) => {
    test.setTimeout(240_000);
    await nine(page);
    for (const width of [1280, 900]) {
      await page.setViewportSize({ width, height: 800 });
      await openSheet(page);
      const side = (await page.getByTestId("sheet-side").boundingBox())!;
      const boxes = await page.locator(".sheet-actions > *").evaluateAll((els) => els.map((e) => {
        const r = e.getBoundingClientRect();
        return { id: e.getAttribute("data-testid"), x: r.x, y: r.y, w: r.width, h: r.height, text: e.textContent };
      }));
      expect(boxes.map((b) => b.id), `${width}: Print, then Download`).toEqual(["print-go", "print-download"]);
      const [go, dl] = boxes;
      expect(dl.y, `${width}: one row`).toBeCloseTo(go.y, 0);
      expect(dl.h, `${width}: one height`).toBeCloseTo(go.h, 0);
      expect(dl.x, `${width}: Download after Print, a gap between`).toBeGreaterThanOrEqual(go.x + go.w + 4);
      expect(dl.x + dl.w, `${width}: inside the side`).toBeLessThanOrEqual(side.x + side.width - 8);
      expect(go.text).toBe("Print");
      // the hint above them stays
      await expect(page.getByTestId("sheet-side").getByText("Print at 100 %")).toBeVisible();
      // Download opens on PDF and SVG
      await page.getByTestId("print-download").click();
      await expect(page.getByTestId("print-pdf")).toBeVisible();
      await expect(page.getByTestId("print-svg")).toBeVisible();
      if (width === 1280) {
        await closeShot(page, "printsel-actions-menu");
        await page.keyboard.press("Escape");
        await closeShot(page, "printsel-actions");
      } else await page.keyboard.press("Escape");
      await expect(page.getByTestId("print-pdf")).toHaveCount(0);
      await page.getByTestId("print-dialog").press("Escape");
      await expect(page.getByTestId("print-dialog")).toHaveCount(0);
    }
  });

  test("d · nothing selected: Selected is disabled and All is on", async ({ page }) => {
    test.setTimeout(240_000);
    await nine(page);
    await page.keyboard.press("Escape");
    expect((await state(page)).selection).toHaveLength(0);
    expect((await state(page)).sel).toBeNull();
    await openSheet(page);
    const which = page.getByTestId("sheet-which");
    await expect(which).toHaveAttribute("data-value", "all");
    await expect(which.locator('[data-value="selected"]')).toBeDisabled();
    await expect(which.locator('[data-value="selected"]')).toHaveText("Selected (0)");
    expect((await settled(page)).items).toHaveLength(9);
  });
});
