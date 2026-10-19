// The review report's stills, taken from a running site (usually the live
// one) for docs/build_v1_report.py (V1, 2026-10-18):
//
//   E2E_BASE_URL=https://arucostudio.com REPORT_SHOTS_DIR=/abs/dir npx playwright test --project=e2e e2e/report.spec.ts
//
// Skipped unless REPORT_SHOTS_DIR is set, so the normal e2e run is unchanged.
// PNGs at 2x pixel density (the builder scales the stills down and keeps
// the close-ups sharp). Each test checks the state it photographs, so a shot
// never shows a half-loaded page, and writes what it measured to facts.json.
// REPORT_PREVIEW_URL (e.g. http://127.0.0.1:5383) adds a shot of the local
// Preview with its Stable / Preview chip.
// WHY rewritten for V1: the timeline is gone (a click on the marker opens
// its panel), Suggest is one dropdown, and Sheet / Verify / auto id / the
// Label tab / the dimensions on the sketch are new.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { coreReady, clickAt, dragWorld, featureRect, idle, loadExample, openStudio, state } from "./helpers";

const DIR = process.env.REPORT_SHOTS_DIR ?? "";
const facts: Record<string, unknown> = {};

test.skip(!DIR, "REPORT_SHOTS_DIR is not set");
test.use({ deviceScaleFactor: 2 });

test.beforeAll(() => { if (DIR) mkdirSync(DIR, { recursive: true }); });
test.afterAll(() => {
  if (!DIR) return;
  // merged, so a partial run (-g) keeps what the other tests measured before
  const file = path.join(DIR, "facts.json");
  const before = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : {};
  writeFileSync(file, JSON.stringify({ ...before, ...facts }, null, 2));
});

type Box = { x: number; y: number; width: number; height: number };
const OVER = '[data-testid="extrude-panel"], [data-testid="shape-dims"], [data-testid="toolbar"]';

async function calm(page: Page): Promise<void> {
  await page.mouse.move(2, 2); // no hover state in the picture
  await page.waitForTimeout(300);
}

async function shot(page: Page, name: string): Promise<void> {
  await calm(page);
  await page.screenshot({ path: path.join(DIR, `${name}.png`) });
}

async function closeUp(loc: Locator, name: string): Promise<void> {
  await loc.scrollIntoViewIfNeeded();
  await loc.screenshot({ path: path.join(DIR, `${name}.png`) });
}

async function boxes(locs: Locator[]): Promise<Box[]> {
  return Promise.all(locs.map(async (l) => (await l.boundingBox())!));
}

/** The union of some elements' boxes as a clipped screenshot; `hide` (a
 *  selector) is hidden for it, e.g. the panel over a sketch close-up. */
async function unionClip(page: Page, name: string, locs: Locator[], pad = 8, hide = ""): Promise<Box> {
  await calm(page);
  const bs = await boxes(locs);
  const vw = page.viewportSize()!;
  const x0 = Math.max(0, Math.min(...bs.map((b) => b.x)) - pad), y0 = Math.max(0, Math.min(...bs.map((b) => b.y)) - pad);
  const x1 = Math.min(vw.width, Math.max(...bs.map((b) => b.x + b.width)) + pad);
  const y1 = Math.min(vw.height, Math.max(...bs.map((b) => b.y + b.height)) + pad);
  if (hide) await page.evaluate((s) => document.querySelectorAll<HTMLElement>(s).forEach((e) => { e.style.visibility = "hidden"; }), hide);
  const clip = { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  await page.screenshot({ path: path.join(DIR, `${name}.png`), clip });
  if (hide) await page.evaluate((s) => document.querySelectorAll<HTMLElement>(s).forEach((e) => { e.style.visibility = ""; }), hide);
  return clip;
}

/** The selected feature on the sketch: its rectangle, marker, label and dimensions. */
async function sketchOf(page: Page, name: string, pad = 14): Promise<Box> {
  const s = await state(page);
  const locs = [page.locator(`[data-shape="${s.feature?.rectId ?? s.doc.features.at(-1).rectId}"]`)];
  if (await page.getByTestId("dims").count()) locs.push(page.getByTestId("dims"));
  return unionClip(page, name, locs, pad, OVER);
}

/** Examples › Plate, click the face between the holes, A: the panel open. */
async function plateWithMarker(page: Page): Promise<void> {
  await openStudio(page);
  const t0 = Date.now();
  await coreReady(page);
  (facts.core_ready_s as number[] | undefined) ?? (facts.core_ready_s = []);
  (facts.core_ready_s as number[]).push(+((Date.now() - t0) / 1000).toFixed(1));
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.locator("[data-marker-black]")).toBeVisible();
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
}

/** ... then OK: one feature, the panel closed. Returns its id. */
async function plateFeature(page: Page): Promise<string> {
  await plateWithMarker(page);
  const fid = (await state(page)).panel.featureId as string;
  await page.getByTestId("panel-ok").click();
  await idle(page);
  await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
  return fid;
}

async function clickMarker(page: Page, fid: string): Promise<void> {
  const b = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
  await page.mouse.click(b.x + b.width / 2, b.y + b.height / 2);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
}

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("menu-file").click();
  await page.getByTestId("cmd-new").click();
}

/** R-drag a rectangle (mm corners), A, OK. Returns the feature's id. */
async function rectFeature(page: Page, a: [number, number], b: [number, number]): Promise<string> {
  await page.keyboard.press("r");
  await dragWorld(page, a, b);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  const fid = (await state(page)).panel.featureId as string;
  await page.getByTestId("panel-ok").click();
  await idle(page);
  return fid;
}

const seg = (page: Page, p: string, v: string) => page.locator(`[data-path="${p}"] [data-value="${v}"]`);
const colour = (page: Page, p: string) => page.locator(`input[data-path="${p}"]`).evaluate((e) => getComputedStyle(e).color);
const overlap = (a: Box, b: Box) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

/** Every drawn dimension: field, value, set, text and its text colour. */
async function dims(page: Page) {
  return page.evaluate(() => [...document.querySelectorAll('[data-testid="dims"] [data-dim]')].map((g) => {
    const t = g.querySelector("text");
    return { field: g.getAttribute("data-dim"), value: Number(g.getAttribute("data-value")), set: g.getAttribute("data-set") === "1",
      text: t?.textContent ?? null, fill: t ? getComputedStyle(t).fill : null };
  }));
}

async function choosePreset(page: Page, name: RegExp): Promise<string> {
  await page.getByTestId("preset-chip").click();
  const modal = page.getByTestId("presets-modal");
  await expect(modal).toBeVisible();
  await modal.locator('[data-coll="builtin"]').click();
  const card = modal.locator(".card[data-card]").filter({ has: page.locator(".name", { hasText: name }) }).first();
  await card.click();
  const got = (await card.locator(".name").textContent())!;
  await page.getByTestId("presets-select").click();
  await expect(modal).toHaveCount(0);
  await idle(page);
  return got;
}

test("1 · click-to-inspect: the panel opens beside the clicked marker; toolbar at the bottom centre; no timeline", async ({ page }) => {
  const fid = await plateFeature(page);
  await expect(page.getByTestId("timeline")).toHaveCount(0);
  await clickMarker(page, fid);
  const vp = (await page.getByTestId("viewport").boundingBox())!;
  const mk = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
  const pb = (await page.getByTestId("extrude-panel").boundingBox())!;
  const tb = (await page.getByTestId("toolbar").boundingBox())!;
  expect(overlap(pb, mk)).toBe(false);
  const gap = pb.x >= mk.x + mk.width ? pb.x - (mk.x + mk.width) : mk.x - (pb.x + pb.width);
  const r = await featureRect(page);
  const s = await state(page);
  facts.inspect = {
    panel: pb, marker: mk, gap_px: +gap.toFixed(1), side: pb.x >= mk.x + mk.width ? "right" : "left",
    toolbar_centre_off_px: +Math.abs(tb.x + tb.width / 2 - (vp.x + vp.width / 2)).toFixed(1),
    toolbar_bottom_gap_px: +(vp.y + vp.height - (tb.y + tb.height)).toFixed(1),
    timeline: 0, rect: { w: r.w, h: r.h, cx: r.cx, cy: r.cy }, summary: s.plan.summary, ids: s.plan.ids,
    tabs: await page.locator('[data-testid="extrude-panel"] [role=tab]').allTextContents(),
  };
  await shot(page, "01-inspect");
  await closeUp(page.getByTestId("extrude-panel"), "01b-panel");
  await closeUp(page.getByTestId("toolbar"), "01c-toolbar");
  await unionClip(page, "01d-topbar-left", [page.getByTestId("topbar").locator("> *").first()], 6);
  await closeUp(page.getByTestId("topbar"), "01e-topbar");
});

test("2 · driven vs set: the marker dimension typed on the sketch turns from grey to solid; ↺ in the panel", async ({ page }) => {
  await plateWithMarker(page);
  await seg(page, "marker.type", "grid").click();
  await idle(page);
  const before = await dims(page);
  expect(before.length).toBeGreaterThan(0);
  const marker0 = before.find((d) => d.field === "marker.marker_mm")!;
  expect(marker0.set).toBe(false);
  await sketchOf(page, "02-dims-driven");
  await page.locator('[data-row="marker.marker_mm"]').scrollIntoViewIfNeeded();
  await unionClip(page, "02c-rows-driven", [page.locator('[data-row="marker.type"]'), page.locator('[data-row="marker.cols"]')], 6);
  // type a size into the dimension on the sketch
  const typed = process.env.REPORT_DIM_MM ?? "16";
  await page.locator('[data-dim-label="marker.marker_mm"]').click();
  const input = page.getByTestId("dim-input");
  await expect(input).toBeVisible();
  await input.fill(typed);
  await page.waitForTimeout(150);
  await sketchOf(page, "02a-dims-typing");
  await input.press("Enter");
  await expect(input).toHaveCount(0);
  await idle(page);
  const after = await dims(page);
  const marker1 = after.find((d) => d.field === "marker.marker_mm")!;
  expect(marker1.set).toBe(true);
  expect(marker1.fill).not.toBe(marker0.fill);
  await expect(page.locator('[data-drv="marker.marker_mm"]')).toHaveAttribute("data-driven", "0");
  const s = await state(page);
  facts.dims = {
    typed_mm: Number(typed), before, after, plan_marker_mm: s.plan.marker_mm, auto: s.feature.marker.auto,
    auto_switch: await page.locator('[data-path="marker.auto"]').count(),
    driven_title: await page.locator('[data-drv="marker.cols"]').getAttribute("title"),
  };
  await sketchOf(page, "02b-dims-set");
  await unionClip(page, "02d-rows-set", [page.locator('[data-row="marker.type"]'), page.locator('[data-row="marker.cols"]')], 6);
  await shot(page, "02e-dims-full");
});

test("3 · Label: inside the rectangle, two lines, a typed X offset (no offset dimension); 3D print draws it in the pixel font", async ({ page }) => {
  await plateWithMarker(page);
  const at0 = (await state(page)).plan.label.at as [number, number];
  await page.locator('[role=tab][data-tab="label"]').click();
  const text = page.locator('textarea[data-path="label.text"]');
  await text.fill("PLATE\n#{ids}");
  await text.blur();
  await idle(page);
  const x = page.locator('input[data-path="label.offset_mm.x"]');
  await x.fill("3");
  await x.press("Enter");
  await idle(page);
  let s = await state(page);
  expect(s.plan.label.lines).toHaveLength(2);
  expect(s.feature.label.offset_mm).toEqual([3, 0]);
  const svgText = await page.locator('[data-testid="viewport"] svg text').allTextContents();
  expect(svgText.some((t) => /offset/i.test(t))).toBe(false);
  const r = await featureRect(page);
  facts.label = {
    text: s.feature.label.text, lines: s.plan.label.lines, font: s.plan.label.font, at0, at: s.plan.label.at,
    dx_mm: +(s.plan.label.at[0] - at0[0]).toFixed(4), height_mm: s.plan.label.height_mm, side: s.feature.label.side,
    rect: { x0: r.cx! - r.w! / 2, x1: r.cx! + r.w! / 2, y0: r.cy! - r.h! / 2, y1: r.cy! + r.h! / 2 },
    offset_dim: await page.locator('[data-dim="label.offset_mm"]').count(),
    preset: (await page.getByTestId("preset-chip").textContent())?.trim(),
  };
  await unionClip(page, "03-label-tab", [page.locator('[data-tab-body="label"]')], 6);
  await shot(page, "03a-label-full");
  await sketchOf(page, "03b-label-inkjet");
  // 3D print: the label as blocky pixel ink
  const preset = await choosePreset(page, /^Default$/);
  s = await state(page);
  facts.label_pixel = { preset, font: s.plan.label.font, polygons: (s.plan.label.polygons ?? []).length, method: s.doc.preset.method };
  expect(s.plan.label.font).toBe("pixel");
  await sketchOf(page, "03c-label-pixel");
});

test("4 · ChArUco: the Joint Origin at the board corner, then in square [1, 1]", async ({ page }) => {
  await plateWithMarker(page);
  await seg(page, "marker.type", "charuco").click();
  await idle(page);
  const fid = (await state(page)).panel.featureId;
  const origin = page.locator(`.triad[data-feature="${fid}"]`);
  const o0 = (await origin.getAttribute("data-origin"))!;
  await sketchOf(page, "04a-charuco-corner");
  await seg(page, "marker.origin_square", "square").click();
  await idle(page);
  for (const k of ["col", "row"]) {
    const f = page.locator(`input[data-path="marker.origin_square.${k}"]`);
    await f.fill("1");
    await f.press("Enter");
    await idle(page);
  }
  await expect.poll(async () => origin.getAttribute("data-origin")).not.toBe(o0);
  const s = await state(page);
  facts.charuco = { origin_corner: o0, origin_square: await origin.getAttribute("data-origin"), square: s.feature.marker.origin_square,
    checker_mm: s.plan.checker_mm, cols: s.plan.cols, rows: s.plan.rows };
  await sketchOf(page, "04b-charuco-square");
  await unionClip(page, "04c-origin-rows", [page.locator('[data-row="marker.origin_square"]'), page.locator('[data-row="marker.origin_square.at"]')], 6);
});

test("5 · Suggest: one dropdown, each option with its whole reason", async ({ page }) => {
  await plateWithMarker(page);
  await seg(page, "marker.type", "grid").click();
  await idle(page);
  await expect(page.getByTestId("suggestion")).toHaveCount(0);
  const trigger = page.getByTestId("suggest-trigger");
  facts.suggest_trigger_h = (await trigger.boundingBox())!.height;
  await unionClip(page, "05a-suggest-closed", [page.locator('[data-row="marker.suggest"]')], 6);
  await trigger.click();
  await expect(page.getByTestId("suggestion").first()).toBeVisible();
  await page.waitForTimeout(250);
  const s = await state(page);
  facts.suggestions = s.suggestions.map((x: any) => `${x.label} · ${x.reason}`);
  const popup = page.getByTestId("suggestion").first().locator("xpath=..");
  // the open list and its trigger
  const bs = await boxes([trigger, page.getByTestId("suggestion").last(), page.getByTestId("suggestion").first()]);
  const x0 = Math.min(...bs.map((b) => b.x)) - 8, y0 = Math.min(...bs.map((b) => b.y)) - 8;
  const x1 = Math.max(...bs.map((b) => b.x + b.width)) + 8, y1 = Math.max(...bs.map((b) => b.y + b.height)) + 8;
  await page.screenshot({ path: path.join(DIR, "05-suggest-open.png"), clip: { x: x0, y: y0, width: x1 - x0, height: y1 - y0 } });
  void popup;
});

test("6 · auto id: two markers get different driven ids; a typed clash is red under ID", async ({ page }) => {
  await blank(page);
  const f1 = await rectFeature(page, [-60, -20], [-20, 20]);
  const f2 = await rectFeature(page, [20, -20], [60, 20]);
  let s = await state(page);
  const id1 = s.plans[f1].ids[0], id2 = s.plans[f2].ids[0];
  expect(id1).not.toBe(id2);
  await clickMarker(page, f2);
  await expect(page.locator('[data-drv="marker.first_id"]')).toHaveAttribute("data-driven", "1");
  // a marker near the viewport's right edge: does the panel still stay off it?
  const pb = (await page.getByTestId("extrude-panel").boundingBox())!;
  const mk2 = (await page.locator(`[data-marker="${f2}"]`).boundingBox())!;
  const rc2 = (await page.locator(`[data-shape="${s.doc.features[1].rectId}"]`).boundingBox())!;
  const bk2 = (await page.locator(`[data-marker="${f2}"] [data-marker-black]`).boundingBox())!;
  facts.autoid_panel = { panel: pb, marker: mk2, black: bk2, rect: rc2, zoom: s.camera.zoom,
    marker_covered_px: +Math.max(0, mk2.x + mk2.width - pb.x).toFixed(1), black_covered_px: +Math.max(0, bk2.x + bk2.width - pb.x).toFixed(1),
    rect_covered_px: +Math.max(0, rc2.x + rc2.width - pb.x).toFixed(1) };
  await shot(page, "06-two-markers");
  await unionClip(page, "06a-id-driven", [page.locator('[data-row="marker.dictionary"]'), page.locator('[data-row="marker.first_id"]')], 6);
  await page.locator('[data-testid="panel-advanced"] summary').click();
  const key = await page.locator('input[data-path="feature.key"]').inputValue();
  await unionClip(page, "06c-key", [page.locator('[data-testid="panel-advanced"]')], 6);
  const idIn = page.locator('input[data-path="marker.first_id"]');
  await idIn.fill(String(id1));
  await idIn.press("Enter");
  await idle(page);
  const err = page.locator('[data-issues-for="marker.first_id"] [data-level="error"]');
  await expect(err.first()).toBeVisible();
  s = await state(page);
  facts.autoid = { ids: [id1, id2], ledger: s.doc.id_ledger, key2: key, clash: await err.first().textContent(),
    keys: s.doc.features.map((f: any) => f.key) };
  await page.locator('[data-row="marker.first_id"]').scrollIntoViewIfNeeded();
  await unionClip(page, "06b-id-clash", [page.locator('[data-row="marker.dictionary"]'), page.locator('[data-row="marker.first_id"]')], 6);
});

test("7 · the presets modal: a click shows the preset's Info on the right; a copy is editable there", async ({ page }) => {
  await openStudio(page);
  await coreReady(page);
  await page.getByTestId("preset-chip").click();
  const modal = page.getByTestId("presets-modal");
  await expect(modal).toBeVisible();
  await modal.locator('[data-coll="builtin"]').click();
  const cards = modal.locator(".card[data-card]");
  await expect(cards.first()).toBeVisible();
  facts.builtin_presets = await cards.locator(".name").allTextContents();
  const a4 = cards.filter({ hasText: "A4" }).first();
  await a4.click();
  await expect(modal.getByTestId("preset-info")).toHaveAttribute("data-readonly", "1");
  await shot(page, "07-presets");
  await modal.getByTestId("preset-info").getByTestId("preset-dup-edit").click();
  const info = modal.getByTestId("preset-info");
  await expect(info).not.toHaveAttribute("data-readonly", "1");
  const m = info.locator('input[data-path="preset.margin_mm"]');
  await m.fill("8");
  await m.press("Enter");
  facts.preset_copy = { name: await info.getByTestId("preset-name").inputValue(), margin_mm: await m.inputValue() };
  await shot(page, "07b-presets-mine");
});

test("8 · Download for CAD: Fusion 360 and Onshape, coming soon", async ({ page }) => {
  await openStudio(page);
  await page.getByTestId("menu-cad").click();
  await expect(page.getByTestId("cad-fusion")).toBeVisible();
  facts.cad_menu = await page.locator('[data-kit-popup="menu"] [role=menuitem]').allTextContents();
  await unionClip(page, "08-cad-menu", [page.getByTestId("menu-cad"), page.locator('[data-kit-popup="menu"]')], 8);
});

// eight rectangles (mm corners on a blank sketch): 3 x 40 x 25, 3 x 40 x 30,
// 2 x 35 x 35, as web/e2e/sheet.spec.ts lays them out
const RECTS: [[number, number], [number, number]][] = [
  [[-100, -45], [-60, -20]], [[-50, -45], [-10, -15]], [[0, -45], [35, -10]], [[45, -45], [85, -20]],
  [[-100, 10], [-60, 40]], [[-50, 5], [-15, 40]], [[-5, 10], [35, 35]], [[45, 10], [85, 40]],
];

test("9 · Sheet: eight stickers, Tight | Spaced and Fewest cuts | Fewest sheets", async ({ page }) => {
  test.setTimeout(240_000);
  await blank(page);
  for (const [a, b] of RECTS) await rectFeature(page, a, b);
  expect((await state(page)).doc.features).toHaveLength(8);
  await shot(page, "09-eight");
  await page.getByTestId("tool-sheet").click();
  await expect(page.getByTestId("print-dialog")).toBeVisible();
  await expect(page.locator('[data-testid="print-page"] svg')).toBeVisible({ timeout: 45_000 });
  await page.getByTestId("print-mode").locator('[data-value="fit"]').click();
  const stats = async () => {
    await idle(page);
    await expect(page.locator(".sheet-body")).toHaveAttribute("data-busy", "0");
    const num = async (id: string) => Number(await page.getByTestId(id).getAttribute("data-value"));
    return { pages: await num("sheet-pages"), cuts: await num("sheet-cuts"), fill: await num("sheet-fill") };
  };
  const pick = async (id: string, v: string) => {
    await page.getByTestId(id).locator(`[data-value="${v}"]`).click();
    await expect(page.getByTestId(id)).toHaveAttribute("data-value", v);
  };
  const out: Record<string, unknown> = {};
  for (const mode of ["spaced", "tight"]) {
    await pick("sheet-mode", mode);
    for (const objective of ["fewest_sheets", "fewest_cuts"]) {
      await pick("sheet-objective", objective);
      out[`${mode}/${objective}`] = await stats();
    }
  }
  // a 40 mm gap: the two objectives part ways
  await pick("sheet-mode", "spaced");
  const gap = page.locator('[data-testid="sheet-gap"] input');
  await gap.fill("40");
  await gap.press("Enter");
  await pick("sheet-objective", "fewest_sheets");
  out["spaced40/fewest_sheets"] = await stats();
  await shot(page, "09a-sheet-fewest-sheets");
  await pick("sheet-objective", "fewest_cuts");
  out["spaced40/fewest_cuts"] = await stats();
  await shot(page, "09b-sheet-fewest-cuts");
  await page.getByTestId("sheet-page-tab").nth(1).click();
  await expect(page.getByTestId("print-page")).toHaveAttribute("data-page", "2");
  await shot(page, "09c-sheet-fewest-cuts-p2");
  await page.getByTestId("sheet-page-tab").nth(0).click();
  await closeUp(page.getByTestId("sheet-side"), "09d-sheet-side");
  await gap.fill("4");
  await gap.press("Enter");
  await pick("sheet-mode", "tight");
  await pick("sheet-objective", "fewest_sheets");
  out["tight/shot"] = await stats();
  await shot(page, "09e-sheet-tight");
  facts.sheet = out;
});

test("10 · the plate's sticker on the page: the whole rectangle, the label inside with white from the cut", async ({ page }) => {
  await plateWithMarker(page);
  await page.locator('[role=tab][data-tab="label"]').click();
  const text = page.locator('textarea[data-path="label.text"]');
  await text.fill("plate #{ids}");
  await text.blur();
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
  await page.getByTestId("tool-sheet").click();
  const pg = page.getByTestId("print-page");
  await expect(pg.locator("svg").first()).toBeVisible({ timeout: 45_000 });
  await idle(page);
  await expect(page.locator(".sheet-body")).toHaveAttribute("data-busy", "0");
  const req = JSON.parse((await page.getByTestId("sheet-side").getAttribute("data-request"))!);
  writeFileSync(path.join(DIR, "sheet-request-plate.json"), JSON.stringify(req, null, 2));
  writeFileSync(path.join(DIR, "sheet-page-plate.svg"), await pg.locator("svg").first().evaluate((e) => e.outerHTML));
  // the label's text box vs the sticker's cut line, in page mm (the SVG's user units)
  const m = await pg.locator("svg").first().evaluate((svg) => {
    const texts = [...svg.querySelectorAll("text")].filter((t) => /plate/.test(t.textContent ?? ""));
    const tb = texts.map((t) => (t as SVGGraphicsElement).getBBox());
    return { texts: texts.map((t) => t.textContent), boxes: tb.map((b) => [b.x, b.y, b.width, b.height]) };
  });
  facts.sticker = { request_items: req.items.length, ...m };
  await shot(page, "10-sheet-plate");
  await calm(page);
  const b = (await pg.boundingBox())!;
  const [pw] = (await pg.getAttribute("data-page-mm"))!.split("x").map(Number);
  const k = b.width / pw;
  await page.screenshot({ path: path.join(DIR, "10b-sticker.png"), clip: { x: b.x, y: b.y, width: 80 * k, height: 105 * k } });
});

test("11 · Verify: OpenCV reads the marker; Tilt is the manual sweep; the automatic sweep and the camera calculator", async ({ page }) => {
  test.setTimeout(300_000);
  const fid = await plateFeature(page);
  await clickMarker(page, fid);
  const t0 = Date.now();
  await page.getByTestId("tool-verify").click();
  await expect(page.getByTestId("verify-dialog")).toBeVisible();
  const loading = await page.getByTestId("verify-loading").textContent().catch(() => null);
  const image = page.getByTestId("verify-image");
  await expect(image).toBeVisible({ timeout: 90_000 });
  const firstMs = Date.now() - t0;
  const legend = page.locator(`[data-testid="sweep-legend"][data-feature="${fid}"]`);
  await expect(legend).toHaveText(/reads to \d+°$/, { timeout: 240_000 });
  const sweepMs = Date.now() - t0;
  // Tilt to 50 by keyboard (the hero video drags it)
  const tilt = page.locator('input[data-knob="tilt_deg"]');
  await tilt.focus();
  await page.keyboard.press("Home");
  for (let i = 0; i < 50; i++) await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("knob-tilt_deg")).toHaveText("50°");
  await expect(page.locator('.vf-frame[data-busy="0"]')).toHaveCount(1, { timeout: 60_000 });
  const d = page.locator('input[data-path="verify.distance_mm"]');
  await d.fill("1500");
  await d.press("Enter");
  await expect(page.locator('.vf-out[data-job="current"][data-busy="0"]')).toHaveCount(1, { timeout: 120_000 });
  const s = await state(page);
  facts.verify = {
    loading_text: loading, first_image_ms: firstMs, sweep_done_ms: sweepMs,
    reads_to_deg: Number(await legend.getAttribute("data-reads-to")), legend: await legend.textContent(),
    verdict: await page.getByTestId("verify-verdict").textContent(),
    calc: { verdict: await page.getByTestId("calc-verdict").textContent(), ppc: await page.getByTestId("calc-ppc").textContent(),
      text: await page.getByTestId("calc-text").textContent().catch(() => null) },
    camera: await page.evaluate(() => JSON.parse(localStorage.getItem("aruco-web.verify.camera") ?? "null")),
    ids: s.plans[fid].ids, cell_mm: s.plans[fid].cell_mm,
  };
  await shot(page, "11-verify");
  await closeUp(page.getByTestId("sweep-chart"), "11b-sweep");
  await closeUp(page.getByTestId("verify-calc"), "11c-calc");
});

test("12 · dark theme", async ({ page }) => {
  const fid = await plateFeature(page);
  await clickMarker(page, fid);
  await page.getByTestId("theme-toggle").click();
  await page.waitForTimeout(300);
  await shot(page, "12-dark");
});

test("13 · 390 × 844: the panel docks to the bottom, the toolbar above it, the marker fitted above both", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await plateWithMarker(page);
  await page.waitForTimeout(400);
  const panel = (await page.getByTestId("extrude-panel").boundingBox())!;
  facts.mobile = {
    panel, toolbar: await page.getByTestId("toolbar").boundingBox(),
    no_hscroll: await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.body.scrollWidth <= window.innerWidth),
  };
  await shot(page, "13-mobile");
});

test("14 · the inkjet preset: no FDM nozzle lint anywhere in the panel", async ({ page }) => {
  await plateWithMarker(page);
  const s = await state(page);
  const panelText = (await page.getByTestId("extrude-panel").textContent()) ?? "";
  const issues = await page.locator('[data-testid="extrude-panel"] [data-level]').allTextContents();
  facts.inkjet_lint = { preset: s.doc.preset.name, method: s.doc.preset.method, nozzle_in_panel: /nozzle/i.test(panelText), issues };
  expect(/nozzle/i.test(panelText)).toBe(false);
  await unionClip(page, "14-preset-row", [page.locator('[data-row="preset"]')], 6);
});

test("15 · the local Preview (REPORT_PREVIEW_URL): the app with its Stable / Preview chip", async ({ page }) => {
  const url = process.env.REPORT_PREVIEW_URL;
  test.skip(!url, "REPORT_PREVIEW_URL is not set");
  await page.goto(url!);
  await expect(page.getByTestId("app")).toBeVisible();
  await expect(page.getByTestId("core-chip")).toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  await page.waitForTimeout(1500);
  facts.preview = { url, title: await page.title(), body: (await page.locator("body").innerText()).slice(-400) };
  await shot(page, "15-preview");
});
