// V1 "Click-to-inspect" (Zach's pick, 2026-10-18; the gallery is
// reports/media/ui-proposals-2026-10-18.html): the ArUco Extrude panel opens
// beside the clicked marker, words instead of icons, the Label tab per the
// contract (inside the rectangle, no offset readout on the canvas), the
// ChArUco origin square, auto id with its ledger, the Download for CAD menu,
// and Verify | Print (on the top-right pill since the Figma layout, V2
// 2026-10-20 night; they were Sheet and Verify on the toolbar). On the static build; every check
// measures the probe's numbers, the drawn boxes or the computed colours.
// Screenshots (1280 × 800) go to V1_SHOTS (default test-results/v1).
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, dragWorld, idle, labelOn, loadExample, openStudio, panelTab, state, openMenu } from "./helpers";

const SHOTS = process.env.V1_SHOTS ?? "test-results/v1";

type Box = { x: number; y: number; width: number; height: number };

/** Examples › Plate, click the face, A, OK: one feature. Returns its id. */
async function plateFeature(page: Page): Promise<string> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await idle(page);
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
  await openMenu(page, "file");
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

const colour = (page: Page, p: string) => page.locator(`input[data-path="${p}"]`).evaluate((e) => getComputedStyle(e).color);
const overlap = (a: Box, b: Box) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;

test.describe(`V1 click-to-inspect (${CORE} core)`, () => {
  // WHY the custom placement (2026-10-20 evening): a marker placed in a face
  // has no rectangle to drag; a rectangle profile is what moves its marker
  test("a · a click on a marker opens the panel beside it, on screen; empty canvas closes it", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "custom-placement");
    await idle(page);
    const fid = "custom-f1";
    await clickMarker(page, fid);
    const panel = page.getByTestId("extrude-panel");
    const vp = (await page.getByTestId("viewport").boundingBox())!;
    const mk = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
    const pb = (await panel.boundingBox())!;
    // beside: not over the marker, a short gap to its side, level with it
    expect(overlap(pb, mk), `panel ${JSON.stringify(pb)} vs marker ${JSON.stringify(mk)}`).toBe(false);
    const gap = pb.x >= mk.x + mk.width ? pb.x - (mk.x + mk.width) : mk.x - (pb.x + pb.width);
    expect(gap).toBeGreaterThanOrEqual(0);
    expect(gap).toBeLessThanOrEqual(80);
    expect(pb.y).toBeLessThan(mk.y + mk.height);
    expect(pb.y + pb.height).toBeGreaterThan(mk.y);
    // inside the viewport
    expect(pb.x).toBeGreaterThanOrEqual(vp.x);
    expect(pb.y).toBeGreaterThanOrEqual(vp.y);
    expect(pb.x + pb.width).toBeLessThanOrEqual(vp.x + vp.width);
    expect(pb.y + pb.height).toBeLessThanOrEqual(vp.y + vp.height);
    // the tabs first, nothing above them (V1 Command Dialog, 2026-10-20 night), in the skeleton's
    // order (2026-10-21: Marker | Label | Manufacture, the Preset a row of Marker under the Profile)
    const rows = await panel.locator("[data-row], [role=tab]").evaluateAll((els) => els.map((e) => e.getAttribute("data-row") ?? `tab:${e.getAttribute("data-tab")}`));
    expect(rows.slice(0, 3)).toEqual(["tab:marker", "tab:label", "tab:make"]);
    expect(rows.slice(3, 5)).toEqual(["profile", "preset"]);
    expect(rows.indexOf("tab:marker")).toBeLessThan(rows.indexOf("marker.type"));
    await page.screenshot({ path: path.join(SHOTS, "v1-panel-beside-marker.png") });

    // it follows the marker when its rectangle profile moves
    const s = await state(page);
    const r = s.doc.shapes.find((x: any) => x.id === s.feature.profile.outer);
    expect(s.feature.profile).toEqual({ outer: "custom", holes: [] });
    const from: [number, number] = [r.cx - r.w / 2, r.cy + r.h * 0.3];
    await dragWorld(page, from, [from[0] - 10, from[1]]);
    await idle(page);
    const mk2 = (await page.locator(`[data-marker="${fid}"]`).boundingBox())!;
    const pb2 = (await panel.boundingBox())!;
    expect(overlap(pb2, mk2)).toBe(false);
    expect(Math.abs((pb2.x - pb.x) - (mk2.x - mk.x))).toBeLessThanOrEqual(2);

    // empty canvas (left of the plate) closes it
    await clickAt(page, -6, 40);
    await expect(panel).toHaveCount(0);
    expect((await state(page)).sel).toBeNull();
  });

  test("b · words, not icons: Type Single | Grid | ChArUco, Turn, Side; Grid makes a grid", async ({ page }) => {
    const fid = await plateFeature(page);
    await clickMarker(page, fid);
    await panelTab(page, "marker");
    const seg = (p: string, v: string) => page.locator(`[data-path="${p}"] [data-value="${v}"]`);
    for (const [v, t] of [["single", "Single"], ["grid", "Grid"], ["charuco", "ChArUco"]]) {
      await expect(seg("marker.type", v)).toHaveText(t);
      await expect(seg("marker.type", v).locator("svg")).toHaveCount(0);
    }
    for (const t of [0, 90, 180, 270]) await expect(seg("marker.turn", String(t))).toHaveText(`${t}°`);
    await expect(page.locator('[data-testid="actions-pill"] [data-testid="act-print"]')).toHaveText("Print");
    await seg("marker.type", "grid").click();
    await idle(page);
    const s = await state(page);
    expect(s.feature.marker.type).toBe("grid");
    expect(s.plan.cols * s.plan.rows).toBeGreaterThan(1);
    expect(s.plan.summary).toMatch(/^Grid/);
    expect(s.plan.ids.length).toBe(s.plan.cols * s.plan.rows);
    await labelOn(page);   // off by default since 2026-10-20 night
    for (const [v, t] of [["below", "Below"], ["above", "Above"], ["left", "Left"], ["right", "Right"]]) await expect(seg("label.side", v)).toHaveText(t);
    // the corner mark is a row of Label since V1 Command Dialog (2026-10-20 night)
    await expect(seg("marker.corner_mark", "triangle")).toHaveText("Triangle");
  });

  test("c · Label: two lines, typed X offset moves it 3 mm, no offset readout on the canvas", async ({ page }) => {
    const fid = await plateFeature(page);
    await clickMarker(page, fid);
    await labelOn(page);   // off by default since 2026-10-20 night
    for (const p of ["label.on", "label.text", "label.place", "label.surface", "label.side", "label.offset_mm", "label.height_mm"]) {
      await expect(page.locator(`[data-row="${p}"]`), p).toHaveCount(1);
    }
    // Gap is the band's, so a row only with the label Outside (V1 Command Dialog); Surface only on the marker
    await expect(page.locator('[data-row="label.gap_mm"]')).toHaveCount(0);
    await page.locator('[data-path="label.place"] [data-value="outside"]').click();
    await idle(page);
    await expect(page.locator('[data-row="label.gap_mm"]')).toHaveCount(1);
    await expect(page.locator('[data-row="label.surface"]')).toHaveCount(0);
    expect((await state(page)).feature.label.place).toBe("outside");
    await page.locator('[data-reset="label.place"]').click();
    await idle(page);
    expect((await state(page)).feature.label.place).toBeUndefined();
    await expect(page.locator('[data-row="label.gap_mm"]')).toHaveCount(0);
    await expect(page.getByTestId("label-placeholders")).toContainText("{id} {first} {last} {ids} {dict} {type}");
    // Height: driven (grey) at 0, showing the core's
    await expect(page.locator('[data-drv="label.height_mm"]')).toHaveAttribute("data-driven", "1");
    let s = await state(page);
    expect(s.feature.label.height_mm).toBe(0);
    expect(Number(await page.locator('input[data-path="label.height_mm"]').inputValue())).toBeCloseTo(s.plan.label.height_mm, 3);

    const text = page.locator('textarea[data-path="label.text"]');
    await text.fill("PLATE\n#{ids}");
    await text.blur();
    await idle(page);
    s = await state(page);
    expect(s.feature.label.text).toBe("PLATE\n#{ids}");
    expect(s.plan.label.lines).toHaveLength(2);
    expect(s.plan.label.lines[0]).toBe("PLATE");
    expect(s.plan.label.lines[1]).toBe(`#${s.plan.ids[0]}`);

    const at0 = s.plan.label.at as [number, number];
    const x = page.locator('input[data-path="label.offset_mm.x"]');
    await expect(page.locator('[data-drv="label.offset_mm.x"]')).toHaveAttribute("data-driven", "1");
    await x.fill("3");
    await x.press("Enter");
    await idle(page);
    s = await state(page);
    expect(s.feature.label.offset_mm).toEqual([3, 0]);
    expect(s.plan.label.at[0] - at0[0]).toBeCloseTo(3, 3);
    expect(s.plan.label.at[1] - at0[1]).toBeCloseTo(0, 3);
    await expect(page.locator('[data-drv="label.offset_mm.x"]')).toHaveAttribute("data-driven", "0");
    // no offset dimension or "offset x, y" readout on the canvas
    await expect(page.getByTestId("viewport")).not.toContainText(/offset/i);
    const svgText = await page.locator('[data-testid="viewport"] svg text').allTextContents();
    expect(svgText.some((t) => /offset/i.test(t))).toBe(false);
    await page.screenshot({ path: path.join(SHOTS, "v1-label-tab.png") });

    // ↺: back to the preset spot
    await page.locator('[data-reset="label.offset_mm.x"]').click();
    await idle(page);
    s = await state(page);
    expect(s.feature.label.offset_mm).toEqual([0, 0]);
    expect(s.plan.label.at[0]).toBeCloseTo(at0[0], 3);
  });

  test("d · ChArUco: Origin Square [1, 1] moves the Joint Origin to that square's centre; ↺ back to the corner", async ({ page }) => {
    const fid = await plateFeature(page);
    await clickMarker(page, fid);
    await panelTab(page, "marker");
    await page.locator('[data-path="marker.type"] [data-value="charuco"]').click();
    await idle(page);
    const origin = page.locator(`.triad[data-feature="${fid}"]`);
    const at = async () => (await origin.getAttribute("data-origin"))!.split(",").map(Number);
    const px = async () => { const b = (await origin.locator("circle").boundingBox())!; return [b.x + b.width / 2, b.y + b.height / 2]; };
    await expect(page.locator('[data-drv="marker.origin_square"]')).toHaveAttribute("data-driven", "1");
    await expect(page.locator('[data-path="marker.origin_square"] [data-value="corner"]')).toHaveText("Board corner");
    const o0 = await at(), p0 = await px();
    const checker = (await state(page)).plan.checker_mm;
    expect(checker).toBeGreaterThan(0);

    await page.locator('[data-path="marker.origin_square"] [data-value="square"]').click();
    await idle(page);
    for (const k of ["col", "row"]) {
      const f = page.locator(`input[data-path="marker.origin_square.${k}"]`);
      await f.fill("1");
      await f.press("Enter");
      await idle(page);
    }
    const s = await state(page);
    expect(s.feature.marker.origin_square).toEqual([1, 1]);
    await expect(page.locator('[data-drv="marker.origin_square"]')).toHaveAttribute("data-driven", "0");
    await expect.poll(async () => (await at()).join(",")).not.toBe(o0.join(","));
    const o1 = await at(), p1 = await px();
    // the centre of square [1, 1]: 1.5 squares along each board axis from the corner
    const mm = Math.hypot(o1[0] - o0[0], o1[1] - o0[1]);
    expect(mm).toBeCloseTo(1.5 * checker * Math.SQRT2, 1);
    const z = s.camera.zoom;
    expect(Math.abs(Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) - mm * z)).toBeLessThanOrEqual(2);
    await expect(page.locator('[data-issues-for="marker.origin_square"] [data-level="error"]')).toHaveCount(0);

    await page.locator('[data-reset="marker.origin_square"]').click();
    await idle(page);
    expect((await state(page)).feature.marker.origin_square).toBeNull();
    await expect.poll(async () => (await at()).join(",")).toBe(o0.join(","));
  });

  test("e · auto id: two features get different driven ids; a typed clash is red under ID; ↺ drives it again; the ledger saves", async ({ page }) => {
    test.skip(CORE === "mock", "the mock core has no assign_ids");
    await blank(page);
    const f1 = await rectFeature(page, [-60, -20], [-20, 20]);
    const f2 = await rectFeature(page, [20, -20], [60, 20]);
    let s = await state(page);
    const id1 = s.plans[f1].ids[0], id2 = s.plans[f2].ids[0];
    expect(id1).not.toBe(id2);
    expect(s.doc.features.map((f: any) => f.marker.first_id)).toEqual([id1, id2]);
    const k1 = s.doc.features[0].key, k2 = s.doc.features[1].key;
    expect(s.doc.id_ledger).toEqual({ [k1]: id1, [k2]: id2 });

    // each shows its own id, driven (grey: the driven colour, as the driven Marker size)
    const idIn = page.locator('input[data-path="marker.first_id"]');
    const idBox = page.locator('[data-drv="marker.first_id"]');
    for (const [f, id] of [[f1, id1], [f2, id2]] as const) {
      await clickMarker(page, f);
      await panelTab(page, "marker");
      await expect(idIn).toHaveValue(String(id));
      await expect(idBox).toHaveAttribute("data-driven", "1");
      expect(await colour(page, "marker.first_id")).toBe(await colour(page, "marker.marker_mm"));
    }
    const driven = await colour(page, "marker.first_id");
    await page.getByTestId("extrude-panel").screenshot({ path: path.join(SHOTS, "v1-id-row-driven.png") });
    // the key: a plain row of Marker (V1 Command Dialog, 2026-10-20 night: no Advanced fold)
    await expect(page.locator('[data-tab-body="marker"] input[data-path="feature.key"]')).toHaveValue(k2);

    // f2 takes f1's id by hand: set (not grey), and red under its ID row
    await idIn.fill(String(id1));
    await idIn.press("Enter");
    await idle(page);
    await expect(idBox).toHaveAttribute("data-driven", "0");
    expect(await colour(page, "marker.first_id")).not.toBe(driven);
    const err = page.locator('[data-issues-for="marker.first_id"] [data-level="error"]');
    await expect(err.first()).toBeVisible();
    await expect(err.first()).toContainText(/overlap/);
    const [R, G, B] = (await err.first().evaluate((e) => getComputedStyle(e).color)).match(/\d+/g)!.map(Number);
    expect(R).toBeGreaterThan(150);
    expect(G + B).toBeLessThan(R);
    await expect(page.locator('[data-row="marker.first_id"]')).toHaveClass(/has-error/);
    s = await state(page);
    expect(s.plans[f2].ids).toEqual([id1]);
    await page.getByTestId("extrude-panel").screenshot({ path: path.join(SHOTS, "v1-id-row-set-clash.png") });
    await page.screenshot({ path: path.join(SHOTS, "v1-id-clash.png") });

    // ↺: driven again, its own id back, no error
    await page.locator('[data-reset="marker.first_id"]').click();
    await idle(page);
    await expect(idBox).toHaveAttribute("data-driven", "1");
    await expect(idIn).toHaveValue(String(id2));
    await expect(err).toHaveCount(0);
    expect((await state(page)).plans[f2].ids).toEqual([id2]);
    await page.getByTestId("panel-ok").click();

    // save, start over, open it: the same ids, from the saved ledger
    await openMenu(page, "file");
    const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("cmd-save").click()]);
    const file = path.join(test.info().outputDir, "ids.arucostudio-web.json");
    await dl.saveAs(file);
    const saved = JSON.parse(readFileSync(file, "utf8"));
    expect(saved.id_ledger).toEqual({ [k1]: id1, [k2]: id2 });
    await openMenu(page, "file");
    await page.getByTestId("cmd-new").click();
    await idle(page);
    expect((await state(page)).doc.features).toHaveLength(0);
    const open = async (p: string) => {
      await openMenu(page, "file");
      const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
      await chooser.setFiles(p);
      await idle(page);
    };
    await open(file);
    s = await state(page);
    expect([s.plans[f1].ids[0], s.plans[f2].ids[0]]).toEqual([id1, id2]);
    expect(s.doc.id_ledger).toEqual({ [k1]: id1, [k2]: id2 });

    // the ledger, not only the hash, holds them: a ledger id the hash would not pick is kept
    const moved = [...Array(50).keys()].find((n) => n !== id1 && n !== id2)!;
    const edited = path.join(test.info().outputDir, "ledger.arucostudio-web.json");
    writeFileSync(edited, JSON.stringify({ ...saved, features: saved.features.map((f: any) => ({ ...f, marker: { ...f.marker, first_id: 0 } })), id_ledger: { [k1]: id1, [k2]: moved } }));
    await open(edited);
    s = await state(page);
    expect([s.plans[f1].ids[0], s.plans[f2].ids[0]]).toEqual([id1, moved]);

    // removing a feature drops its ledger entry
    await clickMarker(page, f1);
    await page.keyboard.press("Delete");
    await idle(page);
    expect((await state(page)).doc.id_ledger).toEqual({ [k2]: moved });
  });

  test("f · Download for CAD: Fusion 360 and Onshape, both disabled, coming soon", async ({ page }) => {
    await openStudio(page);
    await page.getByTestId("menu-cad").click();
    const fusion = page.getByTestId("cad-fusion"), onshape = page.getByTestId("cad-onshape");
    await expect(fusion).toBeVisible();
    await expect(onshape).toBeVisible();
    for (const it of [fusion, onshape]) {
      await expect(it).toHaveAttribute("data-disabled", "");
      await expect(it).toHaveAttribute("aria-disabled", "true");
      await expect(it).toContainText("coming soon");
    }
    await expect(fusion).toContainText("Fusion 360");
    await expect(fusion).toContainText("the add-in is being rebuilt on this core");
    await expect(onshape).toContainText("Onshape");
    const popup = page.locator('[data-kit-popup="menu"]');
    await expect(popup.locator("[role=menuitem]")).toHaveCount(2);
    await expect(popup.locator("a[href]")).toHaveCount(0);
    // a click does nothing: the menu item opens no page, the menu stays
    await fusion.click({ force: true });
    expect(page.context().pages()).toHaveLength(1);
    await page.screenshot({ path: path.join(SHOTS, "v1-download-for-cad.png") });
  });

  test("g · the top-right pill's Verify | Print open their dialogs; the dock stays at the bottom centre", async ({ page }) => {
    await plateFeature(page);
    const tb = page.getByTestId("toolbar");
    const pill = page.getByTestId("actions-pill");
    await expect(pill.getByTestId("act-print")).toHaveText(/Print/);
    await expect(pill.getByTestId("act-verify")).toHaveText(/Verify/);
    await pill.getByTestId("act-print").click();
    await expect.poll(async () => (await state(page)).modal).toBe("print");
    await expect(page.getByTestId("print-page")).toBeVisible({ timeout: 45_000 });
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await state(page)).modal).toBeNull();
    await pill.getByTestId("act-verify").click();
    await expect.poll(async () => (await state(page)).modal).toBe("verify");
    // the dock stays one strip at the bottom centre (V2: 40 px tools in a 52 px dock)
    const vp = (await page.getByTestId("viewport").boundingBox())!;
    const b = (await tb.boundingBox())!;
    expect(Math.abs(b.x + b.width / 2 - (vp.x + vp.width / 2))).toBeLessThanOrEqual(1);
    expect(b.height).toBeLessThanOrEqual(56);
  });
});
