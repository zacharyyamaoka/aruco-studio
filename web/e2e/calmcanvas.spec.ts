// The calm canvas (Zach's pick, 2026-10-21, from the babble
// reports/media/studio-ui-cleanup-proposals-2026-10-21.html), on the real core:
// a · V1 "Turn it down" with his rule ("it's important for me to still see
//     things at a glance like the axes location etc. ... dim the labels to be
//     thin and grey, and only when selected would they become a bit more
//     bold"): every layer is still drawn -- the same count of chrome as today
//     -- thin and grey at rest; the marker pointed at and the selected one are
//     today's, read in computed styles;
// b · the same on the 24-marker sheet;
// c · the dock's Layers menu (V8, Miro's View menu): Grid › Dots | Grid |
//     Blank and one switch per layer, each hiding and showing its own, kept
//     per browser across a reload; the marker being edited keeps its own;
// d · the zoom pill (Miro's): bottom right with ?, a hover lights it, its
//     menu's rows work, and a 30 mm marker at Actual size is 30 × px/mm CSS
//     px (±1);
// e · nothing at the bottom right meets anything at 1440, 1280, 940, 700
//     and 390 wide.
// The documents are the proposal's own (docs/build_ui_cleanup_proposals.py
// documents()): A, Zach's screenshot rebuilt (eight 37.48 mm squares and a
// 2 × 8 ChArUco, View › Marker info on), and B, 24 markers. Measured, never
// assumed: getComputedStyle and getBoundingClientRect. Screenshots go to
// CALM_SHOTS (default test-results/calmcanvas).
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, dragWorld, idle, openMenu, openStudio, panelTab, state, toClient } from "./helpers";

const SHOTS = process.env.CALM_SHOTS ?? "test-results/calmcanvas";
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
const CSS_MM = 96 / 25.4;

// ------------------------------------------------------------ the proposal's documents
const SQ = 37.48;
const rect = (id: string, cx: number, cy: number, w: number, h: number) => ({ kind: "rect", id, cx, cy, w, h, angle_deg: 0 });
const dims = (id: string, w: number, h: number, off = 3.0, hoff = off) => [
  { id: `dw-${id}`, kind: "w", shape: id, value: w, at: [0, h / 2 + off] },
  { id: `dh-${id}`, kind: "h", shape: id, value: h, at: [-(w / 2 + hoff), 0] },
];
const feature = (k: number, type = "single", cols = 1, rows = 1) => ({
  id: `f${k}`, key: `f${k}`, profile: { outer: `r${k}`, holes: [] }, holes: "avoid", trim: "profile",
  marker: { type, dictionary: "DICT_4X4_50", first_id: k, auto: true, marker_mm: 30, checker_mm: 0, separation_mm: 0, cols, rows,
    turn: 0, flip: false, quiet_modules: 1, corner_mark: "triangle" },
  label: { on: false, text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0] },
  extrude: {}, preset: null, set: ["marker.corner_mark", ...(type !== "single" ? ["marker.type", "marker.cols", "marker.rows"] : [])],
});
const doc = (name: string, shapes: object[], ds: object[], feats: ReturnType<typeof feature>[]) => ({
  format: "arucostudio-web", version: 4, name, shapes, dims: ds, features: feats,
  id_ledger: Object.fromEntries(feats.map((f) => [f.key, f.marker.first_id])), default_preset: null,
});
function docA() {
  const shapes: object[] = [], ds: object[] = [], feats = [];
  for (let k = 0; k < 8; k++) {
    const row = Math.floor(k / 4), col = k % 4;
    shapes.push(rect(`r${k}`, col * 43.5, -row * 51.0, SQ, SQ));
    ds.push(...dims(`r${k}`, SQ, SQ));
    feats.push(feature(k));
  }
  shapes.push(rect("r8", 206.0, -21.0, 50.8, 200.0));
  ds.push(...dims("r8", 50.8, 200.0, 3.0, 19.0));
  feats.push(feature(8, "charuco", 2, 8));
  return doc("Marker set", shapes, ds, feats);
}
function docB() {
  const shapes: object[] = [], ds: object[] = [], feats = [];
  for (let k = 0; k < 24; k++) {
    const row = Math.floor(k / 6), col = k % 6;
    shapes.push(rect(`r${k}`, col * 40.0, -row * 46.0, 30.0, 30.0));
    ds.push(...dims(`r${k}`, 30.0, 30.0));
    feats.push(feature(k));
  }
  return doc("Sticker sheet", shapes, ds, feats);
}

async function openDoc(page: Page, d: object, name: string): Promise<void> {
  const file = test.info().outputPath(`${name}.arucostudio-web.json`);
  fs.mkdirSync(test.info().outputDir, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(d));
  await openMenu(page, "file");
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
  await chooser.setFiles(file);
  await idle(page);
  await expect.poll(async () => Object.keys((await state(page)).plans).length, { message: "every marker planned" }).toBe((d as { features: unknown[] }).features.length);
  await idle(page);
  // the toast over the dock is not the canvas
  await page.addStyleTag({ content: ".toast{display:none!important}" });
}

/** The studio at the proposal's window (1440 × 900), View › Marker info on as in Zach's screenshot. */
async function studio(page: Page, markerInfo = true): Promise<void> {
  await page.setViewportSize({ width: 1440, height: 900 });
  // set once: a reload keeps what the test switched since
  if (markerInfo) await page.addInitScript(() => { try { if (localStorage.getItem("arucoStudio.markerInfo") === null) localStorage.setItem("arucoStudio.markerInfo", "1"); } catch { /* blocked */ } });
  await openStudio(page);
  await coreReady(page);
}

/** The pointer off every marker (the empty canvas at the right edge). */
async function park(page: Page): Promise<void> {
  const v = page.viewportSize()!;
  await page.mouse.move(v.width - 4, v.height / 2);
  await page.waitForTimeout(120);
}

/** A marker's outline centre, client px. */
async function centre(page: Page, fid: string): Promise<[number, number]> {
  const p = (await state(page)).plans[fid];
  const xs = p.outer.map((q: number[]) => q[0]), ys = p.outer.map((q: number[]) => q[1]);
  return toClient(page, (Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2);
}

interface Look { stroke: string; width: number; opacity: number; fill: string; size: number; weight: number }
/** The computed look of the first element a selector finds (its stroke, width, opacity, fill, font). */
async function look(page: Page, sel: string): Promise<Look> {
  return page.locator(sel).first().evaluate((e) => {
    const c = getComputedStyle(e);
    return { stroke: c.stroke, width: parseFloat(c.strokeWidth), opacity: parseFloat(c.strokeOpacity), fill: c.fill,
      size: parseFloat(c.fontSize), weight: Number(c.fontWeight) };
  });
}

/** A CSS colour (a var() or a mix too) as the browser computes an SVG fill. */
async function resolved(page: Page, css: string): Promise<string> {
  return page.evaluate((c) => {
    const svg = document.querySelector(".vp-svg")!;
    const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    r.setAttribute("style", `fill: ${c}`);
    svg.appendChild(r);
    const v = getComputedStyle(r).fill;
    r.remove();
    return v;
  }, css);
}

/** A computed colour's channels 0..255 and alpha ("rgb(...)", "rgba(...)" or "color(srgb ...)"). */
function rgba(c: string): [number, number, number, number] {
  const n = c.match(/-?[\d.]+/g)!.map(Number);
  if (c.startsWith("color(")) return [n[0] * 255, n[1] * 255, n[2] * 255, n.length > 3 ? n[3] : 1];
  return [n[0], n[1], n[2], n.length > 3 ? n[3] : 1];
}
const lum = (c: string) => { const [r, g, b] = rgba(c); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };

/** The chrome drawn on the canvas, by kind: only what is painted (display, visibility, opacity and stroke
 *  looked at), as docs/build_ui_cleanup_proposals.py counted it -- a selected profile's own edge is the
 *  selection's outline there, not a profile box. */
async function chrome(page: Page): Promise<Record<string, number>> {
  return page.evaluate(() => {
    const svg = document.querySelector(".vp-svg")!;
    const shown = (e: Element) => {
      for (let x: Element | null = e; x && x !== svg; x = x.parentElement) {
        const c = getComputedStyle(x);
        if (c.display === "none" || c.visibility === "hidden" || Number(c.opacity) === 0) return false;
      }
      return true;
    };
    const stroked = (e: Element) => { const c = getComputedStyle(e); return c.stroke !== "none" && Number(c.strokeOpacity) > 0 && !/,\s*0\)$|\/\s*0\)$/.test(c.stroke); };
    const n = (sel: string, also: (e: Element) => boolean = () => true) => [...svg.querySelectorAll(sel)].filter((e) => shown(e) && also(e)).length;
    const out = {
      sketchDims: n('[data-testid="sketch-dims"] [data-sketch-dim]'),
      origins: n(".triad"),
      profileEdges: n("path[data-shape].marker-rect:not(.on)", stroked),
      infos: n('[data-testid="marker-info"]'),
      markerDims: n('[data-testid="dims"] [data-dim]'),
      arc: n('[data-testid="turn-arc"]'),
      handles: svg.querySelectorAll(".handles [data-handle]").length ? 1 : 0,
      guides: n('[data-marker-outline][data-guide="1"]', stroked),
    };
    return { ...out, total: out.sketchDims + out.origins + out.profileEdges + out.infos + out.markerDims + out.arc + out.handles };
  });
}

/** What prints, as drawn: every white, black and label path (gate 1 of the proposal: a chrome change never moves it). */
const printed = (page: Page) => page.evaluate(() => [...document.querySelectorAll("[data-cut-white], [data-marker-black], [data-label-ink], [data-label-line]")]
  .map((e) => `${e.tagName}:${e.getAttribute("d") ?? e.textContent}:${getComputedStyle(e).fill}`).join("|"));

test.describe("the calm canvas", () => {
  test.skip(CORE === "mock", "the proposal's documents are measured on the real core's plans");

  test("a · Turn it down on doc A: everything drawn, as many as today; thin and grey at rest; the marker pointed at and the selected one as today", async ({ page }) => {
    await studio(page);
    await openDoc(page, docA(), "calm-A");
    await park(page);
    const s = await state(page);
    expect(s.markerInfo).toBe(true);

    // nothing is hidden: the proposal measured today's doc A at 45 (18 dims, 9 axes, 9 boxes, 9 info lines)
    const rest = await chrome(page);
    expect(rest).toMatchObject({ sketchDims: 18, origins: 9, profileEdges: 9, infos: 9, markerDims: 0, arc: 0, handles: 0, total: 45 });
    const print0 = await printed(page);
    await shot(page, "A-rest");

    // at rest: thin and grey
    const muted = await resolved(page, "var(--muted)"), text = await resolved(page, "var(--text)"), accent = await resolved(page, "var(--accent)");
    const quietLine = await resolved(page, "var(--quiet-line)"), quietText = await resolved(page, "var(--quiet-text)");
    expect(lum(quietLine), "the quiet grey is lighter than muted").toBeGreaterThan(lum(muted) + 20);
    expect(lum(quietText)).toBeGreaterThan(lum(muted) + 5);
    const dimLine = await look(page, '[data-sketch-dim="dw-r0"] line.dl');
    expect(dimLine.width).toBeCloseTo(0.6, 3);
    expect(dimLine.stroke).toBe(quietLine);
    const dimText = await look(page, '[data-sketch-dim="dw-r0"] text');
    expect([dimText.size, dimText.weight, dimText.fill]).toEqual([9.5, 400, quietText]);
    expect((await look(page, '[data-sketch-dim="dw-r0"] .chip')).stroke, "no box round the value").toBe("none");
    const info = await look(page, '[data-testid="marker-info"][data-feature="f0"]');
    expect([info.size, info.weight, info.fill]).toEqual([9, 400, quietText]);
    const axX = await look(page, '.triad[data-feature="f0"] .ax-x'), axY = await look(page, '.triad[data-feature="f0"] .ax-y');
    expect([axX.width, axX.opacity, axY.width, axY.opacity]).toEqual([1.3, 0.6, 1.3, 0.6]);
    // the red and the green are still told apart (Zach: the axes location at a glance)
    const [xr, xg, xb] = rgba(axX.stroke), [yr, yg, yb] = rgba(axY.stroke);
    expect(xr - Math.max(xg, xb), "x is red").toBeGreaterThan(100);
    expect(yg - Math.max(yr, yb), "y is green").toBeGreaterThan(60);
    const edge = await look(page, '[data-shape="r0"]');
    expect(edge.width).toBe(1);
    expect(rgba(edge.stroke)[3], "the profile box at half strength").toBeCloseTo(0.5, 2);

    // pointed at (#5): its dims, its info line, its axes and its box are today's; the others stay quiet
    await page.mouse.move(...(await centre(page, "f5")), { steps: 4 });
    await expect(page.locator('[data-testid="marker-info"][data-hot="1"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="marker-info"][data-hot="1"]')).toHaveAttribute("data-feature", "f5");
    const hotLine = await look(page, '[data-sketch-dim="dw-r5"] line.dl');
    expect([hotLine.width, hotLine.stroke]).toEqual([1, text]);
    const hotText = await look(page, '[data-sketch-dim="dw-r5"] text');
    expect([hotText.size, hotText.weight, hotText.fill]).toEqual([11, 600, text]);
    const hotInfo = await look(page, '[data-testid="marker-info"][data-feature="f5"]');
    expect([hotInfo.size, hotInfo.weight, hotInfo.fill]).toEqual([10, 600, muted]);
    expect((await look(page, '.triad[data-feature="f5"] .ax-x')).width).toBe(2.2);
    expect(await page.locator(".triad:not(.quiet)").count(), "one marker's axes are bold").toBe(1);
    const hotEdge = await look(page, '[data-shape="r5"]');
    expect([hotEdge.width, hotEdge.stroke]).toEqual([1.4, accent]);
    expect((await look(page, '[data-sketch-dim="dw-r0"] line.dl')).width, "#0 still quiet").toBeCloseTo(0.6, 3);
    expect(await page.locator(".sk-dims .cad-dim:not(.quiet)").count(), "#5's two dims only").toBe(2);
    expect(await chrome(page), "a hover hides nothing and adds nothing").toMatchObject({ total: 45 });
    await shot(page, "A-hover");
    await park(page);
    await expect(page.locator('[data-testid="marker-info"][data-hot="1"]')).toHaveCount(0);

    // selected (#3, Zach's screenshot): its own chrome as today -- the outer W × H driven, the marker size,
    // the arc, the handles, its axes and info bold; its profile's sketch dims give way to its own (dimhide)
    await page.mouse.click(...(await centre(page, "f3")));
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    await expect.poll(async () => (await state(page)).panel.featureId).toBe("f3");
    await idle(page);
    await park(page);
    const sel = await chrome(page);
    expect(sel).toMatchObject({ sketchDims: 16, origins: 9, profileEdges: 8, infos: 9, markerDims: 3, arc: 1, handles: 1 });
    expect(sel.total, "today's doc A with #3 open: 47 (the proposal's V3 = today)").toBe(47);
    await expect(page.locator('[data-testid="dims"] [data-dim="outer"][data-driven-only="1"]'), "the outer W × H, driven").toHaveCount(2);
    await expect(page.locator('[data-sketch-dim="dw-r3"], [data-sketch-dim="dh-r3"]'), "dimhide: #3's profile dims give way").toHaveCount(0);
    const selDim = await look(page, '[data-testid="dims"] [data-dim="marker.marker_mm"] line.dl');
    expect(selDim.width, "the marker's own dim: today's 1 px").toBe(1);
    expect((await look(page, '[data-testid="dims"] [data-dim="marker.marker_mm"] text')).size).toBe(11);
    const selInfo = await look(page, '[data-testid="marker-info"][data-feature="f3"]');
    expect([selInfo.size, selInfo.weight, selInfo.fill], "a bit more bold when selected").toEqual([10, 600, muted]);
    expect((await look(page, '.triad[data-feature="f3"] .ax-x')).width).toBe(2.2);
    const selEdge = await look(page, '[data-shape="r3"]');
    expect([selEdge.width, selEdge.stroke]).toEqual([2.4, await resolved(page, "var(--pick)")]);
    // the others stay quiet
    expect((await look(page, '[data-sketch-dim="dw-r0"] line.dl')).width).toBeCloseTo(0.6, 3);
    expect((await look(page, '[data-testid="marker-info"][data-feature="f0"]')).size).toBe(9);
    // the quiet-zone guide (printdims) is unchanged: a dashed guide under Trim Profile, the selection outlines the cut
    const outline = page.locator('[data-marker="f3"] [data-marker-outline]');
    await expect(outline).toHaveAttribute("data-guide", "1");
    expect(await outline.evaluate((e) => getComputedStyle(e).strokeDasharray)).not.toBe("none");
    await expect(page.locator('[data-cut-sel="f3"]')).toHaveCount(1);
    await shot(page, "A-selected");
    // gate 1 of the proposal: what prints never moved or changed colour, at rest, pointed at or selected
    expect(await printed(page)).toBe(print0);
  });

  test("b · doc B, 24 markers at fit: every layer drawn (today's 120), thin at rest, one marker selected as today", async ({ page }) => {
    await studio(page);
    await openDoc(page, docB(), "calm-B");
    await page.keyboard.press("f");
    await park(page);
    const rest = await chrome(page);
    expect(rest).toMatchObject({ sketchDims: 48, origins: 24, profileEdges: 24, infos: 24, total: 120 });
    expect(await page.locator(".sk-dims .cad-dim:not(.quiet)").count(), "every dim quiet at rest").toBe(0);
    expect(await page.locator(".triad:not(.quiet)").count()).toBe(0);
    expect(await page.locator('[data-testid="marker-info"][data-hot="1"]').count()).toBe(0);
    await shot(page, "B-rest");
    await page.mouse.click(...(await centre(page, "f9")));
    await expect.poll(async () => (await state(page)).panel.featureId).toBe("f9");
    await idle(page);
    await park(page);
    const sel = await chrome(page);
    expect(sel).toMatchObject({ sketchDims: 46, origins: 24, profileEdges: 23, infos: 24, markerDims: 3, arc: 1, handles: 1 });
    expect(await page.locator(".triad:not(.quiet)").count(), "the selected one's axes only").toBe(1);
    await expect(page.locator('[data-testid="marker-info"][data-hot="1"]')).toHaveAttribute("data-feature", "f9");
    await shot(page, "B-selected");
  });

  test("c · Layers: Grid › Dots | Grid | Blank and a switch per layer, each hiding and showing its own, kept across a reload", async ({ page }) => {
    await studio(page);
    await openDoc(page, docA(), "calm-A-layers");
    await park(page);
    expect((await state(page)).overlays, "a new browser: everything on, the Grid").toEqual(
      { background: "grid", dims: true, origins: true, edges: true, guides: true, rulers: true });
    const grid = page.getByTestId("grid");
    const lines = () => page.locator('[data-testid="grid"] line:not(.axis)').count();
    expect(await lines()).toBeGreaterThan(20);
    await expect(page.getByTestId("grid-dots")).toHaveCount(0);

    // the button is in the dock, beside Fit, not a group of its own
    const dock = (await page.getByTestId("toolbar").boundingBox())!, btn = (await page.getByTestId("tool-layers").boundingBox())!;
    expect(btn.y >= dock.y && btn.y + btn.height <= dock.y + dock.height, "in the dock").toBe(true);
    const fit = (await page.getByTestId("tool-fit").boundingBox())!;
    expect(btn.x - (fit.x + fit.width), "beside Fit").toBeLessThanOrEqual(6);
    await page.getByTestId("tool-layers").click();
    const menu = page.getByTestId("layers-menu");
    await expect(menu).toBeVisible();
    await expect(menu.locator(".kit-menu-item .kit-menu-label")).toHaveText(["Grid", "Sketch dimensions", "Joint Origins", "Profile edges", "Quiet-zone guides", /^Marker info/, "Rulers"]);
    await shot(page, "layers-menu");

    // the background: Dots, Blank, Grid
    const pick = async (b: "dots" | "grid" | "blank") => {
      if (!(await page.getByTestId("layers-grid-popup").isVisible())) await page.getByTestId("layers-grid").hover();
      await page.getByTestId(`layers-bg-${b}`).click();
      await expect(grid).toHaveAttribute("data-background", b);
    };
    await pick("dots");
    await expect(page.getByTestId("layers-bg-dots")).toHaveAttribute("aria-checked", "true");
    await shot(page, "layers-grid-submenu");
    expect(await lines(), "no grid lines").toBe(0);
    await expect(page.getByTestId("grid-dots")).toHaveCount(1);
    // the dots sit on the grid's points: the pattern's tile is the major step, its first dot on the origin
    const tile = await page.locator("#vp-grid-dots").evaluate((p) => ({ x: +p.getAttribute("x")!, y: +p.getAttribute("y")!, w: +p.getAttribute("width")! }));
    const [ox, oy] = await page.evaluate(() => {
      const vp = document.querySelector('[data-testid="viewport"]')!.getBoundingClientRect();
      const [cx, cy] = (window as any).__aruco.toClient(0, 0);
      return [cx - vp.left, cy - vp.top];
    });
    const minorPx = tile.w / 5;
    expect(Math.abs(tile.x + minorPx / 2 - ox), "a dot on the origin (x)").toBeLessThan(0.01);
    expect(Math.abs(tile.y + minorPx / 2 - oy), "a dot on the origin (y)").toBeLessThan(0.01);
    await pick("blank");
    expect(await lines()).toBe(0);
    await expect(page.getByTestId("grid-dots")).toHaveCount(0);
    await expect(page.locator('[data-testid="grid"] line.axis'), "Blank: no axes either").toHaveCount(0);
    await pick("grid");
    expect(await lines()).toBeGreaterThan(20);

    // each switch hides its layer and shows it again; the menu stays open between them
    const sw = async (id: string, on: boolean) => {
      const row = page.getByTestId(id);
      await row.click();
      await expect(row).toHaveAttribute("aria-checked", on ? "true" : "false");
    };
    await sw("layers-dims", false);
    expect((await chrome(page)).sketchDims).toBe(0);
    await sw("layers-dims", true);
    expect((await chrome(page)).sketchDims).toBe(18);
    await sw("layers-origins", false);
    expect((await chrome(page)).origins).toBe(0);
    await sw("layers-origins", true);
    expect((await chrome(page)).origins).toBe(9);
    await sw("layers-edges", false);
    expect((await chrome(page)).profileEdges).toBe(0);
    await expect(page.locator("[data-shape]"), "the shapes' paths stay, unpainted").toHaveCount(9);
    await sw("layers-edges", true);
    expect((await chrome(page)).profileEdges).toBe(9);
    expect((await chrome(page)).guides, "doc A trims to the profile: a guide on each").toBe(9);
    await sw("layers-guides", false);
    expect((await chrome(page)).guides).toBe(0);
    await sw("layers-guides", true);
    expect((await chrome(page)).guides).toBe(9);
    await sw("layers-marker-info", false);
    expect((await chrome(page)).infos).toBe(0);
    expect((await state(page)).markerInfo, "the same switch as View › Marker info").toBe(false);
    await sw("layers-marker-info", true);
    expect((await chrome(page)).infos).toBe(9);
    await sw("layers-rulers", false);
    await expect(page.getByTestId("rulers")).toHaveCount(0);
    await sw("layers-rulers", true);
    await expect(page.getByTestId("rulers")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);

    // all off: only what prints, and the marker being edited keeps its own
    await page.getByTestId("tool-layers").click();
    for (const id of ["layers-dims", "layers-origins", "layers-edges", "layers-guides", "layers-marker-info"]) await sw(id, false);
    await pick("blank");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await park(page);
    expect(await chrome(page)).toMatchObject({ total: 0, guides: 0 });
    await shot(page, "A-layers-all-off");
    await page.mouse.click(...(await centre(page, "f3")));
    await expect.poll(async () => (await state(page)).panel.featureId).toBe("f3");
    await idle(page);
    await park(page);
    expect(await chrome(page), "#3's own: its axes, its marker dims, the arc, the handles, its guide").toMatchObject(
      { origins: 1, markerDims: 3, arc: 1, handles: 1, guides: 1, sketchDims: 0, infos: 0 });
    await expect(page.locator('[data-shape="r3"].on')).toHaveCount(1);

    // kept across a reload (this browser)
    await page.reload();
    await coreReady(page);
    expect((await state(page)).overlays).toEqual({ background: "blank", dims: false, origins: false, edges: false, guides: false, rulers: true });
    expect((await state(page)).markerInfo).toBe(false);
  });

  test("c2 · the three backgrounds and the menus, as pictures", async ({ page }) => {
    await studio(page);
    await openDoc(page, docA(), "calm-A-bg");
    await park(page);
    for (const b of ["dots", "grid", "blank"] as const) {
      await page.getByTestId("tool-layers").click();
      await page.getByTestId("layers-grid").hover();
      await page.getByTestId(`layers-bg-${b}`).click();
      await page.keyboard.press("Escape");
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("layers-menu")).toHaveCount(0);
      await park(page);
      await shot(page, `A-bg-${b}`);
    }
    await page.getByTestId("zoom-menu").click();
    await expect(page.getByTestId("zoom-menu-popup")).toBeVisible();
    await shot(page, "zoom-menu");
  });
});

// ------------------------------------------------------------ the zoom pill
const KEY = "arucoStudio.actualSize";

/** A 30 mm marker in a 40 mm rectangle about the origin; its feature id. Nothing selected after. */
async function marker30(page: Page): Promise<string> {
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
  await page.keyboard.press("r");
  await dragWorld(page, [-20, -20], [20, 20]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await idle(page);
  await panelTab(page, "marker");
  const size = page.locator('input[data-path="marker.marker_mm"]');
  await size.fill("30");
  await size.press("Enter");
  await idle(page);
  await page.getByTestId("panel-ok").click();
  await idle(page);
  const s = await state(page);
  expect(s.plans[s.doc.features[0].id].marker_mm).toBe(30);
  await page.keyboard.press("Escape");
  return s.doc.features[0].id;
}

test.describe("the zoom pill (Miro's)", () => {
  test("d · bottom right with ?, a hover lights it, no + / −; its rows: Fit to screen, Zoom to selection, Actual size (30 mm is 30 × px/mm ±1), Calibrate, 50 / 100 / 200 / 400 %", async ({ page }) => {
    await page.addInitScript(([key]) => {
      window.localStorage.setItem(key, JSON.stringify({ v: 1, screens: { "1280x800@1": { pxPerMm: 4.37, by: "card", at: "2026-10-21T00:00:00.000Z" } } }));
    }, [KEY] as const);
    await openStudio(page);
    await coreReady(page);
    expect((await state(page)).scale).toMatchObject({ key: "1280x800@1", pxPerMm: 4.37, calibrated: true });
    const fid = await marker30(page);
    // and a rectangle off to the side, so the fit (everything) is not the marker's frame
    await page.keyboard.press("r");
    await dragWorld(page, [60, 30], [100, 55]);
    await page.keyboard.press("Escape");
    await page.keyboard.press("f");
    const fitted = (await state(page)).camera;

    // where: bottom right, the zoom and ? in one pill, GitHub beside it
    const { width: W, height: H } = page.viewportSize()!;
    const pill = (await page.getByTestId("corner-pill").boundingBox())!;
    expect(W - (pill.x + pill.width), "at the right").toBeLessThanOrEqual(64);
    expect(H - (pill.y + pill.height), "at the bottom").toBeLessThanOrEqual(24);
    for (const id of ["zoom-menu", "help"]) {
      const b = (await page.getByTestId(id).boundingBox())!;
      expect(b.x >= pill.x && b.x + b.width <= pill.x + pill.width + 0.5, `${id} in the pill`).toBe(true);
    }
    await expect(page.getByTestId("corner-pill").locator("button")).toHaveCount(2);
    await expect(page.getByTestId("corner-pill"), "no + / − (Miro's zoom without them)").not.toContainText(/[+−-]/);
    const pct = () => `${Math.round(((fitted.zoom) / CSS_MM) * 100)}%`;
    await expect(page.getByTestId("zoom-indicator")).toHaveText(pct());
    // a hover lights it
    const bg = () => page.getByTestId("zoom-menu").evaluate((e) => getComputedStyle(e).backgroundColor);
    const before = await bg();
    await page.getByTestId("zoom-menu").hover();
    await expect.poll(bg).not.toBe(before);

    // the rows, in Miro's order
    await page.getByTestId("zoom-menu").click();
    const menu = page.getByTestId("zoom-menu-popup");
    await expect(menu).toBeVisible();
    await expect(menu.locator(".kit-menu-label")).toHaveText(["Fit to screen", "Zoom to selection", "Actual size", "Recalibrate actual size…", "50%", "100%", "200%", "400%"]);
    await expect(page.getByTestId("zm-zoom-selection"), "nothing selected").toHaveAttribute("data-disabled", "");
    // Actual size: the zoom is this screen's scale, the 30 mm marker 30 × 4.37 px
    await page.getByTestId("zm-actual-size").click();
    expect((await state(page)).camera.zoom).toBe(4.37);
    const ink = (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().boundingBox())!;
    expect(Math.abs(ink.width - 30 * 4.37), `the black is ${ink.width} px wide`).toBeLessThanOrEqual(1);
    expect(Math.abs(ink.height - 30 * 4.37), `the black is ${ink.height} px tall`).toBeLessThanOrEqual(1);
    await expect(page.getByTestId("zoom-indicator")).toHaveText("Actual size");
    // the steps: k % of the browser's millimetre
    for (const p of [50, 100, 200, 400]) {
      await page.getByTestId("zoom-menu").click();
      await page.getByTestId(`zm-zoom-${p}`).click();
      expect((await state(page)).camera.zoom).toBeCloseTo((p / 100) * CSS_MM, 9);
      await expect(page.getByTestId("zoom-indicator")).toHaveText(`${p}%`);
    }
    const b400 = (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().boundingBox())!;
    expect(b400.width / ink.width, "400 % against Actual size").toBeCloseTo((4 * CSS_MM) / 4.37, 2);
    // Fit to screen: F's
    await page.getByTestId("zoom-menu").click();
    await page.getByTestId("zm-zoom-fit").click();
    expect((await state(page)).camera).toEqual(fitted);
    // Zoom to selection: the marker selected, framed
    await page.mouse.click(...(await centre(page, fid)));
    await expect.poll(async () => (await state(page)).sel?.id).toBe(fid);
    await page.getByTestId("zoom-menu").click();
    await expect(page.getByTestId("zm-zoom-selection")).not.toHaveAttribute("data-disabled", "");
    await page.getByTestId("zm-zoom-selection").click();
    expect((await state(page)).camera.zoom).toBeGreaterThan(fitted.zoom);
    // Calibrate opens the dialog
    await page.getByTestId("zoom-menu").click();
    await page.getByTestId("zm-calibrate").click();
    await expect(page.getByTestId("calibrate-dialog")).toBeVisible();
  });

  test("e · bottom right meets nothing: 1440, 1280, 940, 700 and 390 wide, at a percent and at Actual size (its longest words)", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const ids = ["corner-pill", "github", "toolbar", "doc-pill", "actions-pill"];
    const boxes = () => page.evaluate((list) => list.flatMap((id) => {
      const e = document.querySelector(`[data-testid="${id}"]`);
      const r = e?.getBoundingClientRect();
      return r && r.width > 0 && r.height > 0 && getComputedStyle(e!).visibility !== "hidden" ? [{ id, x: r.x, y: r.y, w: r.width, h: r.height }] : [];
    }), ids);
    for (const [w, h] of [[1440, 900], [1280, 800], [940, 800], [700, 800], [390, 844]] as const) {
      await page.setViewportSize({ width: w, height: h });
      for (const actual of [false, true]) {
        await page.keyboard.press(actual ? "Shift+Digit0" : "Shift+Digit1");
        await expect(page.getByTestId("zoom-indicator")).toHaveAttribute("data-actual", actual ? "1" : "0");
        const all = await boxes();
        if (w === 390) {
          // a phone: ? and GitHub are in the ⌄ menu; the zoom only at Actual size, under the document pill
          expect(all.some((b) => b.id === "github")).toBe(false);
          const zp = all.find((b) => b.id === "corner-pill");
          expect(!!zp, `390, ${actual ? "Actual size" : "a percent"}: the zoom pill shown`).toBe(actual);
          if (zp) {
            const doc = all.find((b) => b.id === "doc-pill")!;
            expect(zp.y, "under the document pill").toBeGreaterThanOrEqual(doc.y + doc.h);
          }
        } else {
          expect(all.map((b) => b.id).sort(), `${w}: all shown`).toEqual([...ids].sort());
        }
        for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
          const a = all[i], b = all[j];
          const meet = a.x < b.x + b.w - 0.5 && b.x < a.x + a.w - 0.5 && a.y < b.y + b.h - 0.5 && b.y < a.y + a.h - 0.5;
          expect(meet, `${w}, ${actual ? "Actual size" : "a percent"}: ${a.id} meets ${b.id}`).toBe(false);
        }
        for (const b of all) expect(b.x >= 0 && b.x + b.w <= w && b.y >= 0 && b.y + b.h <= h, `${w}: ${b.id} on screen`).toBe(true);
        // nothing in the pill overflows its box
        const over = await page.getByTestId("corner-pill").evaluate((root) => [root, ...root.querySelectorAll("*")].filter((e) => (e as HTMLElement).scrollWidth > (e as HTMLElement).clientWidth + 1).length);
        expect(over, `${w}: overflow`).toBe(0);
        if (actual) await shot(page, `corner-${w}`);
      }
    }
  });
});
