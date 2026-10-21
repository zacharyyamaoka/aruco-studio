// Profile-first (Zach, 2026-10-20 evening: "if we just have the idea of a
// profile, and you want a custom location, then you draw a rectangle profile.
// If you want an auto positioned one, just click a regular profile"): the
// feature references a profile, the core places the marker in it and answers
// fit_rect (contract barrier 9). A click inside a region picks that region;
// a double-click on a rectangle picks its outer edges alone; Trim is
// Profile | Marker. Every check measures: the probe's numbers in mm, the
// drawn boxes (getBoundingClientRect), the white's fill at a point
// (isPointInFill). Screenshots (1280 × 800) go to PROFILE_SHOTS (default
// test-results/profile).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, circleGap, clickAt, coreReady, dblClickAt, dragWorld, fitRect, idle, loadExample, openStudio, panelTab, planOutline, state, toClient, type Rect, openMenu } from "./helpers";

const SHOTS = process.env.PROFILE_SHOTS ?? "test-results/profile";
const FIXTURE = path.join(import.meta.dirname, "fixtures", "v2-rect.arucostudio-web.json");
type Box = { x0: number; y0: number; x1: number; y1: number };

async function screenBox(page: Page, sel: string): Promise<Box> {
  return page.locator(sel).first().evaluate((e) => {
    const r = e.getBoundingClientRect();
    return { x0: r.left, y0: r.top, x1: r.right, y1: r.bottom };
  });
}

function near(a: Box, b: Box, tol: number, what: string): void {
  for (const k of ["x0", "y0", "x1", "y1"] as const) expect(Math.abs(a[k] - b[k]), `${what} ${k}: ${a[k]} vs ${b[k]}`).toBeLessThanOrEqual(tol);
}

/** Is the sketch point (mm) inside the feature's white (its fill, even-odd)? */
async function white(page: Page, fid: string, x: number, y: number): Promise<boolean> {
  const [cx, cy] = await toClient(page, x, y);
  return page.locator(`[data-cut-white="${fid}"]`).evaluate((e, [px, py]) => {
    const svg = (e as SVGPathElement).ownerSVGElement!.getBoundingClientRect();
    return (e as SVGPathElement).isPointInFill(new DOMPoint(px - svg.left, py - svg.top));
  }, [cx, cy]);
}

/** A rectangle (mm) equal to the expected one within a micron. */
function sameRect(got: Rect, want: Partial<Rect>, what: string): void {
  for (const [k, v] of Object.entries(want)) expect(Math.abs((got as any)[k] - (v as number)), `${what}.${k}: ${(got as any)[k]} vs ${v}`).toBeLessThan(1e-3);
}

/** A loop with its start at its lowest-then-leftmost corner, rounded to a micron:
 *  the same outline drawn from another corner compares equal. */
function canon(loop: number[][]): number[][] {
  const pts = loop.map(([x, y]) => [Math.round(x * 1000) / 1000, Math.round(y * 1000) / 1000]);
  let k = 0;
  pts.forEach((p, i) => { if (p[1] < pts[k][1] || (p[1] === pts[k][1] && p[0] < pts[k][0])) k = i; });
  return [...pts.slice(k), ...pts.slice(0, k)];
}

/** The plan's outline (the quiet zone's edge) as a box in mm. */
const outlineRect = async (page: Page): Promise<Rect> => ({ ...(await planOutline(page)), angle_deg: 0 });

/** Examples › Plate, click inside the face, A: the panel open on the face's feature. */
async function plateFace(page: Page): Promise<string> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "profile", ref: { outer: "plate", holes: ["plate-h1", "plate-h2"] } });
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  return (await state(page)).panel.featureId as string;
}

test.describe(`profile-first (${CORE} core)`, () => {
  test("a · plate: click inside the face, A: the marker sits inside the face, off both holes; fit_rect is drawn", async ({ page }) => {
    const fid = await plateFace(page);
    const s = await state(page);
    expect(s.feature.profile).toEqual({ outer: "plate", holes: ["plate-h1", "plate-h2"] });
    expect(s.doc.shapes.map((x: any) => x.id), "no rectangle is added to the sketch").toEqual(["plate", "plate-h1", "plate-h2"]);
    await expect(page.locator('[data-row="rect"]'), "no Rectangle row").toHaveCount(0);
    await expect(page.getByTestId("sel-profile")).toHaveAttribute("data-count", "1");

    // the marker (its outline: the quiet zone's edge) inside the face, off both holes
    const fit = await fitRect(page);
    const out = await outlineRect(page);
    for (const r of [fit, out]) {
      expect(r.cx - r.w / 2).toBeGreaterThanOrEqual(-1e-6);
      expect(r.cx + r.w / 2).toBeLessThanOrEqual(120 + 1e-6);
      expect(r.cy - r.h / 2).toBeGreaterThanOrEqual(-1e-6);
      expect(r.cy + r.h / 2).toBeLessThanOrEqual(80 + 1e-6);
      for (const hole of s.doc.shapes.filter((x: any) => x.kind === "circle")) {
        expect(circleGap(hole, r), `${JSON.stringify(r)} vs hole ${hole.id}`).toBeGreaterThanOrEqual(-1e-3);
      }
    }
    // the outline sits in the box the core chose (to 0.01 mm: the mock rounds to it)
    expect(out.cx - out.w / 2).toBeGreaterThanOrEqual(fit.cx - fit.w / 2 - 0.01);
    expect(out.cx + out.w / 2).toBeLessThanOrEqual(fit.cx + fit.w / 2 + 0.01);
    expect(out.cy - out.h / 2).toBeGreaterThanOrEqual(fit.cy - fit.h / 2 - 0.01);
    expect(out.cy + out.h / 2).toBeLessThanOrEqual(fit.cy + fit.h / 2 + 0.01);

    // fit_rect drawn, dashed, where the plan says
    const el = page.locator(`[data-fit-rect="${fid}"]`);
    await expect(el).toHaveCount(1);
    expect(await el.evaluate((e) => getComputedStyle(e).strokeDasharray)).not.toBe("none");
    const [x0, y1] = await toClient(page, fit.cx - fit.w / 2, fit.cy - fit.h / 2);
    const [x1, y0] = await toClient(page, fit.cx + fit.w / 2, fit.cy + fit.h / 2);
    near(await screenBox(page, `[data-fit-rect="${fid}"]`), { x0, y0, x1, y1 }, 1.5, "the dashed box vs fit_rect");
    // and the black is drawn inside the face on screen
    const plate = await screenBox(page, '[data-shape="plate"]');
    const black = await screenBox(page, `[data-marker="${fid}"] [data-marker-black]`);
    expect(black.x0 >= plate.x0 && black.x1 <= plate.x1 && black.y0 >= plate.y0 && black.y1 <= plate.y1).toBe(true);
    await page.screenshot({ path: path.join(SHOTS, "profile-a-plate-face.png") });
  });

  test("b · draw a rectangle inside the plate, double-click it, A: the marker fills it; drag it 20 mm and the marker follows", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await loadExample(page, "plate");
    await page.keyboard.press("r");
    await dragWorld(page, [45, 25], [80, 70]);
    let s = await state(page);
    const rid = s.sel.id as string;
    expect(s.doc.shapes.find((x: any) => x.id === rid)).toMatchObject({ kind: "rect", cx: 62.5, cy: 47.5, w: 35, h: 45 });
    await dblClickAt(page, 62.5, 47.5);
    await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "profile", ref: { outer: rid, holes: [] } });
    await page.keyboard.press("a");
    await idle(page);
    s = await state(page);
    expect(s.feature.profile).toEqual({ outer: rid, holes: [] });
    expect(s.feature.trim).toBe("profile");

    // fills it: the core used the rectangle as the box, the outline inside it, as wide as it
    const fit = await fitRect(page);
    sameRect(fit, { cx: 62.5, cy: 47.5, w: 35, h: 45, angle_deg: 0 }, "fit_rect");
    const before = await planOutline(page);
    expect(before.cx - before.w / 2).toBeGreaterThanOrEqual(45 - 1e-3);
    expect(before.cx + before.w / 2).toBeLessThanOrEqual(80 + 1e-3);
    expect(before.cy - before.h / 2).toBeGreaterThanOrEqual(25 - 1e-3);
    expect(before.cy + before.h / 2).toBeLessThanOrEqual(70 + 1e-3);
    expect(before.w, "the marker spans the rectangle's short side").toBeGreaterThan(35 * 0.9);
    // no dashed box over a rectangle profile: its own edges are the box
    await expect(page.locator(`[data-fit-rect="${s.feature.id}"]`)).toHaveCount(0);

    // drag the rectangle by its left edge, 20 mm right: the marker follows, measured
    const px0 = await screenBox(page, `[data-marker="${s.feature.id}"] [data-marker-outline]`);
    await dragWorld(page, [45, 60], [65, 60]);
    await idle(page);
    s = await state(page);
    expect(s.doc.shapes.find((x: any) => x.id === rid)).toMatchObject({ cx: 82.5, cy: 47.5 });
    const after = await planOutline(page);
    expect(Math.abs(after.cx - before.cx - 20)).toBeLessThanOrEqual(0.5);
    expect(Math.abs(after.cy - before.cy)).toBeLessThanOrEqual(0.5);
    expect((await fitRect(page)).cx).toBeCloseTo(82.5, 3);
    const px1 = await screenBox(page, `[data-marker="${s.feature.id}"] [data-marker-outline]`);
    const z = s.camera.zoom;
    expect(Math.abs((px1.x0 + px1.x1) / 2 - (px0.x0 + px0.x1) / 2 - 20 * z)).toBeLessThanOrEqual(0.5 * z + 1);
    // and a press-drag on the marker itself moves the rectangle back
    await dragWorld(page, [after.cx, after.cy], [after.cx - 20, after.cy]);
    await idle(page);
    expect((await state(page)).doc.shapes.find((x: any) => x.id === rid)).toMatchObject({ cx: 62.5, cy: 47.5 });
    expect(Math.abs((await planOutline(page)).cx - before.cx)).toBeLessThanOrEqual(0.5);
    await page.screenshot({ path: path.join(SHOTS, "profile-b-rectangle.png") });
  });

  test("c · Trim offers exactly Profile | Marker; Profile cuts to the face with its holes, Marker to the quiet zone", async ({ page }) => {
    const fid = await plateFace(page);
    // Trim is on Manufacture (the skeleton: a new feature opens on Marker)
    await panelTab(page, "make");
    const btns = page.locator('[data-row="trim"] .kit-seg-btn');
    expect(await btns.evaluateAll((els) => els.map((e) => e.getAttribute("data-value")))).toEqual(["profile", "marker"]);
    expect(await btns.allTextContents()).toEqual(["Profile", "Marker"]);
    let s = await state(page);
    expect(s.feature.trim).toBe("profile");
    await expect(page.locator('[data-drv="trim"]')).toHaveAttribute("data-driven", "1");

    // Profile (the default): the white is the face, its holes open
    near(await screenBox(page, `[data-cut-white="${fid}"]`), await screenBox(page, '[data-shape="plate"]'), 1, "white vs the face");
    for (const h of s.doc.shapes.filter((x: any) => x.kind === "circle")) {
      expect(await white(page, fid, h.cx, h.cy), `hole ${h.id}'s centre`).toBe(false);
    }
    expect(await white(page, fid, 2, 2), "the face's corner").toBe(true);
    await page.screenshot({ path: path.join(SHOTS, "profile-c-trim-profile.png") });

    // Marker: the white is the quiet zone
    await btns.nth(1).click();
    await idle(page);
    await expect.poll(async () => (await state(page)).feature.trim).toBe("marker");
    near(await screenBox(page, `[data-cut-white="${fid}"]`), await screenBox(page, `[data-marker="${fid}"] [data-marker-outline]`), 1,
      "white vs the quiet zone");
    expect(await white(page, fid, 2, 2), "the face's corner").toBe(false);
    s = await state(page);
    expect(s.plan.cut_shape.holes).toEqual([]);
    await page.screenshot({ path: path.join(SHOTS, "profile-c-trim-marker.png") });
  });

  test("d · an old file (rectId, trim rectangle) opens as a rectangle profile trimmed to profile, and plans identically", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await openMenu(page, "file");
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
    await chooser.setFiles(FIXTURE);
    await expect(page.getByTestId("note")).toContainText("Opened v2-rect");
    await idle(page);
    await expect.poll(async () => !!(await state(page)).plans.f1).toBe(true);
    const s = await state(page);
    expect(s.doc.version).toBe(4);
    const f1 = s.doc.features[0];
    expect(f1).not.toHaveProperty("rectId");
    expect(f1.profile).toEqual({ outer: "r1", holes: [] });
    expect(f1.trim).toBe("profile");
    expect(f1.set).not.toContain("trim");

    // the plan the old file got: its rectangle, cut to the rectangle (a request the UI no longer sends)
    const r1 = s.doc.shapes.find((x: any) => x.id === "r1");
    const legacy = {
      trim: "rectangle", rect: { cx: r1.cx, cy: r1.cy, w: r1.w, h: r1.h, angle_deg: r1.angle_deg },
      marker: f1.marker, label: f1.label, preset: f1.preset, reference_face: false,
    };
    const old = JSON.parse(JSON.stringify(await page.evaluate((req) => (window as any).__aruco.plan(req), legacy)));
    // as JSON (what a saved plan is): -0 and 0 are one number there
    const now = JSON.parse(JSON.stringify(s.plans.f1));
    expect(now.ids).toEqual([7]);
    for (const k of ["ok", "ids", "black", "outer", "outer_mm", "marker_mm", "cell_mm", "overflow_mm", "origin", "label", "summary"]) {
      expect(now[k], `plan.${k}`).toEqual(old[k]);
    }
    // the cut: the same outline (from whichever corner each starts)
    expect(canon(now.cut), "plan.cut").toEqual(canon(old.cut));
    expect(canon(now.cut_shape.outer), "plan.cut_shape.outer").toEqual(canon(old.cut_shape.outer));
    expect(now.cut_shape.holes).toEqual([]);
    sameRect(now.fit_rect, legacy.rect, "fit_rect");
    // drawn in its rectangle
    const rect = await screenBox(page, '[data-shape="r1"]');
    const black = await screenBox(page, '[data-marker="f1"] [data-marker-black]');
    expect(black.x0 >= rect.x0 - 1 && black.x1 <= rect.x1 + 1 && black.y0 >= rect.y0 - 1 && black.y1 <= rect.y1 + 1).toBe(true);
    // the face-inscribed feature keeps its spot: its inscribed rectangle is its profile
    expect(s.doc.features[1]).toMatchObject({ profile: { outer: "r2", holes: [] }, trim: "marker" });
  });

  test("e · moving a hole of the face re-plans: the marker moves off it", async ({ page }) => {
    const fid = await plateFace(page);
    await page.getByTestId("panel-ok").click();
    await idle(page);
    const fit0 = await fitRect(page);
    // grab the right hole (Ø20 at 95, 25) by its edge and drag it to the middle
    await dragWorld(page, [105, 25], [70, 40]);
    await idle(page);
    const s = await state(page);
    const hole = s.doc.shapes.find((x: any) => x.id === "plate-h2");
    expect(hole).toMatchObject({ cx: 60, cy: 40 });
    const fit1 = (await state(page)).plans[fid].fit_rect as Rect;
    expect(fit1, "re-planned").not.toEqual(fit0);
    expect(circleGap(hole, fit1), `fit_rect ${JSON.stringify(fit1)} vs the moved hole`).toBeGreaterThanOrEqual(-1e-3);
  });

  test("f · A with nothing selected: the Profile row waits; a double-click on a rectangle with a circle in it picks the rectangle alone", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await openMenu(page, "file");
    await page.getByTestId("cmd-new").click();
    await page.keyboard.press("r");
    await dragWorld(page, [-40, -30], [40, 30]);
    await page.keyboard.press("c");
    await dragWorld(page, [0, 0], [10, 0]);
    let s = await state(page);
    const [rid, cid] = s.doc.shapes.map((x: any) => x.id);
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await state(page)).sel).toBeNull();

    await page.keyboard.press("a");
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    s = await state(page);
    expect(s.panel.selector).toBe("profile");
    await expect(page.getByTestId("sel-profile")).toHaveAttribute("data-active", "1");
    await expect(page.getByTestId("selector-hint")).toContainText("double-click a rectangle");
    await expect(page.getByTestId("panel-ok")).toBeDisabled();

    // a double-click inside the ring picks the rectangle's outer edges alone
    // (its first click picks the ring; the double-click re-picks for the panel)
    await dblClickAt(page, -30, 0);
    await idle(page);
    s = await state(page);
    expect(s.feature.profile).toEqual({ outer: rid, holes: [] });
    expect(s.panel.open).toBe(true);
    expect(s.doc.features).toHaveLength(1);
    sameRect(await fitRect(page), { cx: 0, cy: 0, w: 80, h: 60 }, "fit_rect");

    // cleared, the row waits again; a single click inside picks the ring
    await page.getByTestId("sel-profile-clear").click();
    expect((await state(page)).panel.selector).toBe("profile");
    await clickAt(page, -30, 0);
    await idle(page);
    s = await state(page);
    expect(s.feature.profile).toEqual({ outer: rid, holes: [cid] });
    const ring = await fitRect(page);
    expect(circleGap({ cx: 0, cy: 0, r: 10 }, ring), `fit_rect ${JSON.stringify(ring)} vs the circle`).toBeGreaterThanOrEqual(-1e-3);
    await page.getByTestId("panel-ok").click();
    await idle(page);

    // a single click on an edge still selects the shape for editing: its handles
    await clickAt(page, -40, 25);
    await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "shape", id: rid });
    await expect(page.locator("[data-handle]")).toHaveCount(8);
  });
});
