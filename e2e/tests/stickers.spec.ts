// M6b (folded into M8b2): the preset first, the per-kind form, Holes,
// Perimeter, the ChArUco label's square, the 2D / 3D badges, the filter and
// the IDs table's Made-by column. Every bar is read from the DOM, the store
// (window.__studio) or the API; the screenshots are for people.
import { expect, test, type Page } from "@playwright/test";
import {
  API, add, backToTag, choose, freshFile, idle, issueTexts, options, probe, sceneTags, shapeOfTag, shot, tab, toggle,
} from "./helpers";

const STICKER = "Sticker · Letter · 600 dpi";

async function tagOf(page: Page, name: string): Promise<any> {
  const tags = await sceneTags(page.request);
  return tags.find((t) => t.name === name);
}

/** The new-tag preset (nothing selected): the inspector's first row. */
async function newPreset(page: Page, name: string) {
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page.locator('.kit-select[data-path="new.preset"]')).toBeVisible();
  await choose(page, "new.preset", name);
  await expect(page.locator('.kit-select[data-path="new.preset"]')).toHaveAttribute("data-value", name);
}

test("M6b.1-3 a sticker on the disc: Made by, its four tabs, Holes, Perimeter", async ({ page }) => {
  await freshFile(page, "e2e-sticker");
  // M6b.1: the preset first; it makes the tag a sticker
  await newPreset(page, STICKER);
  await expect(page.getByTestId("made-by")).toHaveAttribute("data-made-by", "sticker");
  await shot(page, "m8b2_sticker_new_preset");
  await page.keyboard.press("c");
  await page.keyboard.type("40");
  await page.keyboard.press("Enter");
  await idle(page);
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await idle(page);
  const name = (await probe(page)).sel[0];
  expect(name).toBeTruthy();
  const head = page.getByTestId("inspector");
  await expect(head).toHaveAttribute("data-made-by", "sticker");
  await expect(page.getByTestId("made-by")).toContainText("Printed sticker");
  await expect(page.locator('[data-row="settings.make.by"] .row-label')).toHaveText("Made by");
  const tabs = await page.locator('[role="tab"][data-tab]').evaluateAll((els) => els.map((e) => e.getAttribute("data-tab")));
  expect(tabs).toEqual(["marker", "print", "label", "advanced"]);                       // four tabs, no Heights
  for (const p of ["settings.mode", "numbers.white_height", "numbers.black_height", "settings.pin"]) {
    for (const t of tabs) {
      await tab(page, t!);
      await expect(page.locator(`[data-row="${p}"]`)).toHaveCount(0);
    }
  }
  await tab(page, "print");
  await expect(page.locator('[data-row="settings.make.thickness_mm"] .row-label')).toHaveText("Sticker thickness");
  await expect(page.locator('[data-row="settings.make.margin_mm"] .row-label')).toHaveText("Sticker margin");
  await expect(page.locator(`[data-badge-for="${name}"]`)).toHaveAttribute("data-badge", "2D");
  const z = await page.evaluate(() => (window as any).__studio.zRange);
  expect(z[1]).toBeCloseTo(0.11, 6);
  await shot(page, "m8b2_sticker_print_tab");

  // M6b.2: a hole in the disc (H, 8, Enter at the shape's centre); Holes: Ignore grows the marker
  await shapeOfTag(page);
  await page.keyboard.press("h");
  await page.keyboard.type("8");
  await page.keyboard.press("Enter");
  await idle(page);
  await backToTag(page, name);
  await tab(page, "marker");
  await expect(page.locator('[data-row="settings.holes"]')).toBeVisible();
  const avoid = Number((await tagOf(page, name)).plan.marker.marker_length_m);
  await choose(page, "settings.holes", "ignore");
  const ignore = Number((await tagOf(page, name)).plan.marker.marker_length_m);
  expect(ignore).toBeGreaterThan(avoid);
  await expect(page.locator(`[data-tag="${name}"] [data-guide="target_ignored"]`)).toHaveCount(1);          // the hole, dashed
  const holesMsgs = await issueTexts(page, "settings.holes");
  expect(holesMsgs.some((t) => /crosses hole/.test(t))).toBeTruthy();
  await expect(page.locator('[data-issues-for="settings.holes"] .issue[data-level="warn"]')).toHaveCount(1);
  await shot(page, "m8b2_sticker_holes_ignore");

  // M6b.3: Perimeter = Profile: the disc's outline (and its hole) is the cut line; Marker: a rectangle
  await choose(page, "settings.make.perimeter", "profile");
  const cut = page.locator(`[data-tag="${name}"] [data-guide="cut_line"]`);
  await expect(cut).toHaveAttribute("data-kind", "profile");
  expect(Number(await cut.getAttribute("data-points"))).toBeGreaterThan(40);
  await expect(cut).toHaveAttribute("data-holes", "1");
  await shot(page, "m8b2_sticker_perimeter_profile");
  await choose(page, "settings.make.perimeter", "marker");
  await expect(cut).toHaveAttribute("data-kind", "marker");
  expect(Number(await cut.getAttribute("data-points"))).toBeLessThanOrEqual(5);
  // Marker with no margin: the label's Position has no "On the white"
  await tab(page, "label");
  await toggle(page, "settings.label.on");
  const places = await options(page, "settings.label.place");
  expect(places).toContain("black");
  expect(places).not.toContain("white");
  // a margin gives the white back
  await tab(page, "print");
  const m = page.locator('input[data-path="settings.make.margin_mm"]');
  await m.fill("4");
  await m.press("Enter");
  await idle(page);
  await tab(page, "label");
  expect(await options(page, "settings.label.place")).toContain("white");
  await shot(page, "m8b2_sticker_label");
});

test("M6b.3 a 3D tag's Perimeter = Marker trims the body (trim_keep)", async ({ page }) => {
  await freshFile(page, "e2e-perimeter3d");
  await add(page, "single");
  const name = (await probe(page)).sel[0];
  await expect(page.getByTestId("inspector")).toHaveAttribute("data-made-by", "print3d");
  await expect(page.locator('[data-row="settings.make.perimeter"]')).toBeVisible();
  await expect(page.locator('.kit-select[data-path="settings.make.perimeter"]')).toHaveAttribute("data-value", "profile");
  await choose(page, "settings.make.perimeter", "marker");
  const t = await tagOf(page, name);
  expect(t.spec.settings.trim).toMatchObject({ rule: 1, axes: "both" });
  expect(t.plan.layers.map((L: any) => L.name)).toContain("trim_keep");
  // the sticker rows stay hidden on a 3D tag (show_when.made_by)
  await tab(page, "print");
  await expect(page.locator('[data-row="settings.make.thickness_mm"]')).toHaveCount(0);
  await shot(page, "m8b2_3d_perimeter_marker");
});

test("M6b.4 a ChArUco label: In a black square only; dragged into another black square, it builds there", async ({ page }) => {
  await freshFile(page, "e2e-charuco-label");
  await newPreset(page, STICKER);
  await add(page, "charuco");
  const name = (await probe(page)).sel[0];
  await tab(page, "label");
  await toggle(page, "settings.label.on");
  expect(await options(page, "settings.label.place")).toEqual(["black"]);
  await expect(page.locator('[data-row="settings.label.row"]')).toHaveCount(0);           // Row and Side hidden
  await expect(page.locator('[data-row="settings.label.side"]')).toHaveCount(0);
  let t = await tagOf(page, name);
  expect(t.plan.ok).toBeTruthy();
  const parts = t.plan.label.parts as { rect: number[] }[];
  expect(parts.length).toBeGreaterThan(0);
  const sq = Number(t.plan.marker.square_length_m) * 1000;
  const r0 = parts[0].rect;
  const c0 = [(r0[0] + r0[2]) / 2, (r0[1] + r0[3]) / 2];
  // the label, dragged two squares along the board's x: the next black square of its row
  const hit = page.locator(`[data-tag="${name}"] [data-label-hit="0"]`);
  await expect(hit).toHaveCount(1);
  const b = (await hit.boundingBox())!;
  const dir = await page.evaluate((nm) => {
    const st = (window as any).__studio.store.getState();
    const tg = st.scene.tags.find((x: any) => x.name === nm);
    const a = (tg.rotation_deg * Math.PI) / 180;
    const pit = tg.plan.frames.pattern_in_target;
    const ux = Math.cos(a) * pit[0] - Math.sin(a) * pit[4], uy = Math.sin(a) * pit[0] + Math.cos(a) * pit[4];
    return { ux, uy, zoom: st.camera.zoom };
  }, name);
  const dx = 2 * sq * dir.ux * dir.zoom, dy = -2 * sq * dir.uy * dir.zoom;
  const from: [number, number] = [b.x + b.width / 2, b.y + b.height / 2];
  await page.mouse.move(from[0], from[1]);
  await page.mouse.down();
  await page.mouse.move(from[0] + dx / 2, from[1] + dy / 2, { steps: 4 });
  await page.mouse.move(from[0] + dx, from[1] + dy, { steps: 4 });
  await page.mouse.up();
  await idle(page);
  t = await tagOf(page, name);
  const lab = t.spec.settings.label;
  expect(lab.position).toBe("manual");
  expect(lab.rule).toBeGreaterThanOrEqual(3);                        // rule 3 (any black square), kept by rule 4 (audit 2026-10-17)
  expect(Math.abs(lab.x_mm - (c0[0] + 2 * sq))).toBeLessThan(0.6);
  expect(t.plan.label?.parts?.length ?? 0).toBeGreaterThan(0);                            // built there
  expect((t.plan.guides.label_preview ?? []).length).toBe(0);                            // no orange
  await expect(page.locator(`[data-tag="${name}"] .g-refused`)).toHaveCount(0);
  await shot(page, "m8b2_charuco_label_moved");
});

test("M6b.7 the 2D / 3D filter, the Made-by column, one duplicate across both kinds, Renumber", async ({ page }) => {
  await freshFile(page, "e2e-kinds");
  await add(page, "single");                                                              // a 3D tag
  const t3 = (await probe(page)).sel[0];
  await newPreset(page, STICKER);
  await add(page, "single");                                                              // a sticker
  const t2 = (await probe(page)).sel[0];
  await expect(page.locator(`[data-ids-row="${t3}"] td.mb`)).toHaveAttribute("data-made-by", "print3d");
  await expect(page.locator(`[data-ids-row="${t2}"] td.mb`)).toHaveAttribute("data-made-by", "sticker");
  await expect(page.locator(`[data-badge-for="${t3}"]`)).toHaveAttribute("data-badge", "3D");
  await expect(page.locator(`[data-badge-for="${t2}"]`)).toHaveAttribute("data-badge", "2D");
  // both #3: one duplicate (ids are per dictionary family, not per kind)
  for (const n of [t3, t2]) {
    const r = await page.request.patch(`${API}/api/scene/tags/${encodeURIComponent(n)}`, { data: { numbers: { marker_id: 3 } } });
    expect(r.ok()).toBeTruthy();
  }
  // the server's own write sends no event (M8a): the Studio reads it again
  await page.evaluate(() => (window as any).__studio.store.getState().refresh());
  await idle(page);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "1");
  await expect(page.locator(`[data-ids-row="${t3}"]`)).toHaveClass(/dup/);
  await expect(page.locator(`[data-ids-row="${t2}"]`)).toHaveClass(/dup/);
  await shot(page, "m8b2_kinds_duplicate");
  // the filter: 2D hides the 3D tags; 3D the stickers
  await page.locator('[data-testid="kind-filter"] [data-value="2d"]').click();
  await expect(page.locator(`.canvas2d [data-tag="${t3}"]`)).toHaveCount(0);
  await expect(page.locator(`.canvas2d [data-tag="${t2}"]`)).toHaveCount(1);
  await shot(page, "m8b2_kinds_filter_2d");
  await page.locator('[data-testid="kind-filter"] [data-value="3d"]').click();
  await expect(page.locator(`.canvas2d [data-tag="${t2}"]`)).toHaveCount(0);
  await expect(page.locator(`.canvas2d [data-tag="${t3}"]`)).toHaveCount(1);
  await page.locator('[data-testid="kind-filter"] [data-value="all"]').click();
  // Renumber fixes it
  await page.getByTestId("renumber").click();
  await idle(page);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");
  const ids = (await sceneTags(page.request)).map((t) => t.plan.ids[0]);
  expect(new Set(ids).size).toBe(ids.length);
});
