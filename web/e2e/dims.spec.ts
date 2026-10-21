// The selected feature's dimensions on the canvas (web/src/sketch/Dims.tsx):
// drawn CAD-style from plan().dims, only the sizes the type takes (single:
// marker; grid: marker, separation; ChArUco: checker, marker), driven grey vs
// set solid (the panel's isSet), typed into in place. Each check measures what is drawn: the arrow
// tips' client positions (each arrowhead path starts at its tip), the value
// chips' boxes, the computed colours, and the probe's numbers. Screenshots
// go to E2E_SHOTS (default test-results/shots).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, dragWorld, idle, labelOn, openPresets, openStudio, panelTab, state, toClient, toggleTheme, openMenu } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";

interface Box { x: number; y: number; w: number; h: number }
interface DrawnDim {
  field: string; value: number; set: boolean; text: string | null;
  a: [number, number]; b: [number, number]; label: Box | null; fill: string | null; stroke: string;
}

async function blank(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();
}

/** A feature of one type in a 60 × 60 rectangle profile about the origin, its panel open. Returns the feature's id. */
async function typedFeature(page: Page, type: "single" | "grid" | "charuco"): Promise<string> {
  await blank(page);
  await page.keyboard.press("r");
  await dragWorld(page, [-30, -30], [30, 30]);
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await panelTab(page, "marker");
  await page.locator(`[data-path="marker.type"] [data-value="${type}"]`).click();
  await idle(page);
  const s = await state(page);
  expect(s.feature.marker.type).toBe(type);
  expect(s.plan.dims?.length, "the core returns dims").toBeGreaterThan(0);
  return s.panel.featureId;
}

/** A 2 × 2 grid in a 60 × 60 rectangle about the origin, its panel open. Returns the feature's id. */
const gridFeature = (page: Page) => typedFeature(page, "grid");

/** The dims each type may draw: the sizes typed into it, and only those. */
const CONTROLS = {
  single: ["marker.marker_mm"],
  grid: ["marker.marker_mm", "marker.separation_mm"],
  charuco: ["marker.checker_mm", "marker.marker_mm"],
} as const;

/** Every drawn dimension you can type into (`all`: the read-only outer W × H too, canvas3), in drawing order, measured in client px. */
async function drawn(page: Page, all = false): Promise<DrawnDim[]> {
  return page.evaluate((all) => [...document.querySelectorAll(`[data-testid="dims"] [data-dim]${all ? "" : ":not([data-driven-only])"}`)].map((g) => {
    const tip = (k: string): [number, number] => {
      const p = g.querySelector(`[data-tip="${k}"]`) as SVGPathElement;
      const pt = p.getPointAtLength(0), m = p.getScreenCTM()!;
      return [m.a * pt.x + m.c * pt.y + m.e, m.b * pt.x + m.d * pt.y + m.f];
    };
    const lab = g.querySelector("[data-dim-label]")?.getBoundingClientRect();
    const text = g.querySelector("text");
    return {
      field: g.getAttribute("data-dim")!, value: Number(g.getAttribute("data-value")), set: g.getAttribute("data-set") === "1",
      text: text?.textContent ?? null, a: tip("a"), b: tip("b"),
      label: lab ? { x: lab.x, y: lab.y, w: lab.width, h: lab.height } : null,
      fill: text ? getComputedStyle(text).fill : null, stroke: getComputedStyle(g.querySelector("line.dl")!).stroke,
    };
  }), all);
}

/** A theme token resolved to the colour the browser paints. */
async function token(page: Page, name: string): Promise<string> {
  return page.evaluate((n) => {
    const el = document.createElement("span");
    el.style.color = `var(${n})`;
    document.body.appendChild(el);
    const c = getComputedStyle(el).color;
    el.remove();
    return c;
  }, name);
}

async function dimOf(page: Page, field: string): Promise<DrawnDim> {
  const d = (await drawn(page)).find((x) => x.field === field);
  expect(d, `a ${field} dimension is drawn`).toBeTruthy();
  return d!;
}

/** Click a dimension's value and type into it (text "" = an empty Enter). */
async function typeDim(page: Page, field: string, text: string): Promise<void> {
  await page.locator(`[data-dim-label="${field}"]`).click();
  const input = page.getByTestId("dim-input");
  await expect(input).toBeVisible();
  await expect(input).toHaveAttribute("data-dim-edit", field);
  await input.fill(text);
  await input.press("Enter");
  await expect(input).toHaveCount(0);
  await idle(page);
}

const overlap = (a: Box, b: Box) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const tipLength = (d: DrawnDim) => Math.hypot(d.b[0] - d.a[0], d.b[1] - d.a[1]);

test.describe(`canvas dimensions (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core returns no dims");

  test("a · a selected grid: marker and separation only, each as long as its value; b · no label offset", async ({ page }) => {
    const fid = await gridFeature(page);
    await labelOn(page);
    await panelTab(page, "marker");
    // move the label off its preset spot, so the core returns a label.offset_mm dimension
    const lb = (await page.getByTestId("label-text").boundingBox())!;
    await page.mouse.move(lb.x + lb.width / 2, lb.y + lb.height / 2);
    await page.mouse.down();
    for (let i = 1; i <= 8; i++) await page.mouse.move(lb.x + lb.width / 2 + i * 3, lb.y + lb.height / 2 - i);
    await page.mouse.up();
    await idle(page);

    const s = await state(page);
    expect(s.panel.featureId).toBe(fid);
    const planDims = s.plan.dims as { field: string; value_mm: number }[];
    expect(planDims.map((d) => d.field), "the core measures the label offset").toContain("label.offset_mm");
    for (const f of ["outer", "rect.w", "rect.h"]) expect(planDims.map((d) => d.field), `the core still measures ${f}`).toContain(f);
    const want = planDims.filter((d) => (CONTROLS.grid as readonly string[]).includes(d.field));

    const dims = await drawn(page);
    expect(dims.map((d) => d.field).sort()).toEqual([...CONTROLS.grid].sort());
    expect(dims.map((d) => [d.field, d.value])).toEqual(want.map((d) => [d.field, d.value_mm]));

    // each drawn length, arrow tip to arrow tip, over the zoom, is its value
    const zoom = s.camera.zoom;
    for (const d of dims) {
      expect(Math.abs(tipLength(d) / zoom - d.value), `${d.field} ${d.value} drawn ${tipLength(d) / zoom}`).toBeLessThan(0.3);
      expect(Math.abs(Number(d.text) - d.value), `${d.field} shows ${d.text}`).toBeLessThan(0.006);
    }
    // the panel's driven Marker row and the dimension agree
    const markerRow = Number(await page.locator('input[data-path="marker.marker_mm"]').inputValue());
    expect(Math.abs((await dimOf(page, "marker.marker_mm")).value - markerRow)).toBeLessThan(0.006);

    // (b) no dimension or text for the label offset
    await expect(page.locator('[data-dim="label.offset_mm"]')).toHaveCount(0);
    const svgText = await page.locator(".vp-svg").evaluate((e) => e.textContent ?? "");
    expect(svgText).not.toMatch(/offset/i);

    // no value sits on the rectangle (so none on the marker's ink), none on another
    const rect = (await page.locator(`[data-shape="${s.feature.profile.outer}"]`).boundingBox())!;
    const rbox = { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
    for (const d of dims) expect(overlap(d.label!, rbox), `${d.field} value off the rectangle`).toBe(false);
    for (let i = 0; i < dims.length; i++) for (let j = i + 1; j < dims.length; j++) {
      expect(overlap(dims[i].label!, dims[j].label!), `${dims[i].field} vs ${dims[j].field}`).toBe(false);
    }
    // driven grey
    const muted = await token(page, "--muted");
    expect((await dimOf(page, "marker.marker_mm")).fill).toBe(muted);
    expect((await dimOf(page, "marker.separation_mm")).fill).toBe(muted);
    await page.screenshot({ path: path.join(SHOTS, "dims-grid-light.png") });
    await toggleTheme(page);
    await page.screenshot({ path: path.join(SHOTS, "dims-grid-dark.png") });
  });

  test("c · type 12 into the marker dim: set in the panel, the set colour, kept on resize; d · empty Enter: driven, follows again", async ({ page }) => {
    await gridFeature(page);
    const muted = await token(page, "--muted"), text = await token(page, "--text");
    const markerRow = page.locator('[data-drv="marker.marker_mm"]');
    const markerInput = page.locator('input[data-path="marker.marker_mm"]');
    let d = await dimOf(page, "marker.marker_mm");
    expect(d.set).toBe(false);
    expect(d.fill).toBe(muted);
    expect(d.stroke).toBe(muted);
    const driven0 = d.value;

    // Esc cancels
    await page.locator('[data-dim-label="marker.marker_mm"]').click();
    await page.getByTestId("dim-input").fill("9");
    await page.getByTestId("dim-input").press("Escape");
    await expect(page.getByTestId("dim-input")).toHaveCount(0);
    await idle(page);
    expect((await state(page)).feature.marker.auto).toBe(true);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();

    // (c) 12: the panel's row is set to 12, the dim measures 12 in the set colour
    await typeDim(page, "marker.marker_mm", "12");
    await expect(markerRow).toHaveAttribute("data-driven", "0");
    await expect(markerInput).toHaveValue("12");
    let s = await state(page);
    expect(s.feature.marker).toMatchObject({ auto: false, marker_mm: 12 });
    // it shows 12 as the row does; its line measures what is drawn: 12 on the
    // preset's cell grid (a whole number of cells), as features.spec c allows
    d = await dimOf(page, "marker.marker_mm");
    expect(d.set).toBe(true);
    expect(d.text).toBe("12");
    expect(d.value).toBe(s.plan.marker_mm);
    expect(Math.abs(d.value - 12)).toBeLessThan(0.1);
    expect(d.fill).toBe(text);
    expect(d.stroke).toBe(text);
    expect(Math.abs(tipLength(d) / s.camera.zoom - d.value)).toBeLessThan(0.3);
    const planned12 = d.value;
    await page.screenshot({ path: path.join(SHOTS, "dims-marker-set-light.png") });
    await toggleTheme(page);
    await page.screenshot({ path: path.join(SHOTS, "dims-marker-set-dark.png") });
    await toggleTheme(page);

    // resizing the rectangle keeps 12
    await dragWorld(page, [30, 30], [36, 36]);
    await idle(page);
    s = await state(page);
    expect(s.doc.shapes.find((x: any) => x.id === s.feature.profile.outer)).toMatchObject({ w: 66, h: 66 });
    d = await dimOf(page, "marker.marker_mm");
    expect(d.text).toBe("12");
    expect(d.value).toBe(planned12);
    expect(d.set).toBe(true);
    await expect(markerInput).toHaveValue("12");

    // (d) an empty Enter: driven again, grey, and it follows the rectangle
    await typeDim(page, "marker.marker_mm", "");
    await expect(markerRow).toHaveAttribute("data-driven", "1");
    s = await state(page);
    expect(s.feature.marker.auto).toBe(true);
    d = await dimOf(page, "marker.marker_mm");
    expect(d.set).toBe(false);
    expect(d.fill).toBe(muted);
    expect(d.value).toBeCloseTo(s.plan.marker_mm, 4);
    expect(d.value).toBeGreaterThan(driven0);          // the 66 mm rectangle's driven size
    const driven66 = d.value;
    await dragWorld(page, [36, 36], [42, 42]);
    await idle(page);
    s = await state(page);
    d = await dimOf(page, "marker.marker_mm");
    expect(d.value).toBeGreaterThan(driven66);
    expect(d.value).toBeCloseTo(s.plan.marker_mm, 4);
    expect(Math.abs(Number(await markerInput.inputValue()) - d.value)).toBeLessThan(0.006);
  });

  test("e · typing W (a driving sketch dim, D) resizes the rectangle and the marker re-plans; no W or H among the marker's dims", async ({ page }) => {
    await gridFeature(page);
    let s = await state(page);
    const before = { marker: s.plan.marker_mm, outerW: s.plan.outer_mm[0] };
    for (const f of ["rect.w", "rect.h"]) await expect(page.locator(`[data-dim="${f}"]`)).toHaveCount(0);

    // the W × H box is gone (2026-10-20 night): W is a sketch dim, D on the bottom edge dragged down to place it
    await page.keyboard.press("d");
    await dragWorld(page, [0, -30], [0, -40]);
    const w = page.getByTestId("sdim-input");
    await expect(w).toHaveValue("60");
    await w.fill("40");
    await w.press("Enter");
    await idle(page);
    s = await state(page);
    const r = s.doc.shapes.find((x: any) => x.id === s.feature.profile.outer);
    expect(r).toMatchObject({ w: 40, h: 60, cx: 0, cy: 0 });
    expect(s.plan.marker_mm).toBeLessThan(before.marker);
    expect(s.plan.outer_mm[0]).toBeLessThan(before.outerW);
    // the marker dim follows; still no W or H on the canvas (the outer is read-only, canvas3.spec.ts)
    const m = await dimOf(page, "marker.marker_mm");
    expect(m.value).toBeCloseTo(s.plan.marker_mm, 4);
    expect(Math.abs(tipLength(m) / s.camera.zoom - m.value)).toBeLessThan(0.3);
    expect((await drawn(page)).map((d) => d.field).sort()).toEqual([...CONTROLS.grid].sort());
  });

  test("f · zoomed out until the marker is 40 px wide: no two values overlap", async ({ page }) => {
    await gridFeature(page);
    let s = await state(page);
    const [cx, cy] = await toClient(page, 0, 0);
    await page.mouse.move(cx, cy);
    // the viewport zooms by exp(-deltaY * 0.0015) per wheel event
    const target = 40 / s.plan.marker_mm;
    await page.mouse.wheel(0, -Math.log(target / s.camera.zoom) / 0.0015);
    await expect.poll(async () => (await state(page)).camera.zoom).toBeLessThan(s.camera.zoom);
    await idle(page);
    s = await state(page);
    const black = (await page.locator(`[data-marker="${s.feature.id}"] [data-marker-black]`).boundingBox())!;
    const markerPx = s.plan.marker_mm * s.camera.zoom;
    expect(Math.abs(markerPx - 40), `marker ${markerPx} px`).toBeLessThan(1.5);
    expect(black.width).toBeLessThan(2 * 40 + 40);       // two markers and their gap

    const dims = await drawn(page, true);
    expect(dims.filter((d) => d.field !== "outer").map((d) => d.field).sort()).toEqual([...CONTROLS.grid].sort());
    const rect = (await page.locator(`[data-shape="${s.feature.profile.outer}"]`).boundingBox())!;
    const rbox = { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
    for (const d of dims) {
      expect(overlap(d.label!, rbox), `${d.field} value off the rectangle`).toBe(false);
      expect(Math.abs(tipLength(d) / s.camera.zoom - d.value), d.field).toBeLessThan(0.3);
    }
    for (let i = 0; i < dims.length; i++) for (let j = i + 1; j < dims.length; j++) {
      expect(overlap(dims[i].label!, dims[j].label!), `${dims[i].field} ${JSON.stringify(dims[i].label)} vs ${dims[j].field} ${JSON.stringify(dims[j].label)}`).toBe(false);
    }
    await page.screenshot({ path: path.join(SHOTS, "dims-small-light.png") });
    await toggleTheme(page);
    await page.screenshot({ path: path.join(SHOTS, "dims-small-dark.png") });
  });

  for (const type of ["single", "grid", "charuco"] as const) {
    test(`g · a selected ${type}: exactly ${CONTROLS[type].length} dim(s) to type, ${CONTROLS[type].join(" + ")}; no W or H (the outer: read-only)`, async ({ page }) => {
      await typedFeature(page, type);
      const s = await state(page);
      const dims = await drawn(page);
      expect(dims.map((d) => d.field).sort()).toEqual([...CONTROLS[type]].sort());
      expect(await page.locator('[data-testid="dims"] [data-dim]:not([data-driven-only])').count()).toBe(CONTROLS[type].length);
      // each is the plan's measure of that field, as long as its value
      for (const d of dims) {
        const p = (s.plan.dims as { field: string; value_mm: number }[]).find((x) => x.field === d.field)!;
        expect(d.value).toBe(p.value_mm);
        expect(Math.abs(tipLength(d) / s.camera.zoom - d.value), d.field).toBeLessThan(0.3);
      }
      // nothing you type shows the outer size or the rectangle's W or H
      const rect = s.doc.shapes.find((x: any) => x.id === s.feature.profile.outer);
      const hidden = new Set([s.plan.outer_mm[0], s.plan.outer_mm[1], rect.w, rect.h].map((v: number) => String(+v.toFixed(2))));
      expect(dims.filter((d) => hidden.has(d.text!)).map((d) => d.field), "no dim value is the outer size or W / H").toEqual([]);
      const titles = await page.locator('[data-testid="dims"] [data-dim]:not([data-driven-only]) title').allTextContents();
      expect(titles.some((t) => /outer|rectangle/i.test(t))).toBe(false);
      await page.screenshot({ path: path.join(SHOTS, `dims-${type}.png`) });
    });
  }

  test("h · the label follows as you type, a character at a time, without leaving the field; Esc reverts", async ({ page }) => {
    const fid = await typedFeature(page, "single");
    await labelOn(page);
    const text = page.locator('textarea[data-path="label.text"]');
    const before = (await state(page)).plans[fid].label.lines as string[];
    const lines = page.locator(`[data-testid="label-text"][data-feature="${fid}"] [data-label-line]`);
    await expect(lines).toHaveCount(before.length);
    const canvas = () => lines.allTextContents();
    const focused = () => text.evaluate((e) => document.activeElement === e);

    await text.click();
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.press("Backspace");
    // an empty text is the core's template (web_api.label_text), so the canvas keeps it; the document follows
    await expect.poll(async () => (await state(page)).feature.label.text, { timeout: 2000 }).toBe("");
    let typed = "";
    for (const ch of "AB") {
      await page.keyboard.type(ch);
      typed += ch;
      await expect.poll(canvas, { timeout: 2000 }).toEqual([typed]);
      expect(await focused(), "still in the field").toBe(true);
    }
    await page.keyboard.press("Enter");
    await page.keyboard.type("CD");
    await expect.poll(canvas, { timeout: 2000 }).toEqual(["AB", "CD"]);
    await expect(lines).toHaveCount(2);
    expect(await focused(), "still in the field").toBe(true);
    expect((await state(page)).feature.label.text).toBe("AB\nCD");
    await page.screenshot({ path: path.join(SHOTS, "label-live.png") });

    // Esc: back to the text from when the field was focused
    await page.keyboard.press("Escape");
    await expect.poll(canvas, { timeout: 2000 }).toEqual(before);
    expect(await focused()).toBe(false);
    await idle(page);
    expect((await state(page)).feature.label.text).toBe("#{ids}");
    await expect(text).toHaveValue("#{ids}");
  });

  test("label · two lines stacked 1.4 caps apart, as the core stacks them; a 3D print draws the pixel ink", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const doc = {
      format: "arucostudio-web", version: 3, name: "Two lines", id_ledger: {}, preset: null,
      shapes: [{ kind: "rect", id: "r1", cx: 0, cy: 0, w: 60, h: 60, angle_deg: 0 }],
      features: [{ id: "f1", key: "f1", profile: { outer: "r1", holes: [] }, holes: "avoid", marker: { type: "single" }, label: { on: true, text: "PLATE\n#{ids}" }, set: [] }],
    };
    await openMenu(page, "file");
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
    await chooser.setFiles({ name: "two-lines.arucostudio-web.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(doc)) });
    await idle(page);
    // auto id (2026-10-18): an untouched feature gets its hashed id, not 0
    await expect.poll(async () => (await state(page)).plans.f1?.label?.lines?.length).toBe(2);
    let s = await state(page);
    const want2 = ["PLATE", `#${s.plans.f1.ids[0]}`];
    expect(s.plans.f1.label.lines).toEqual(want2);
    const label = s.plans.f1.label;
    expect(label.font).toBe("sans");

    const lines = page.locator('[data-testid="label-text"] [data-label-line]');
    await expect(lines).toHaveCount(2);
    expect(await lines.allTextContents()).toEqual(want2);
    const [b0, b1] = [(await lines.nth(0).boundingBox())!, (await lines.nth(1).boundingBox())!];
    expect(b0.height).toBeCloseTo(b1.height, 3);       // one font size: the boxes' tops are the baselines' pitch apart
    const want = 1.4 * label.height_mm * s.camera.zoom;
    expect(Math.abs(b1.y - b0.y - want), `pitch ${b1.y - b0.y} px vs ${want}`).toBeLessThanOrEqual(1);
    await page.screenshot({ path: path.join(SHOTS, "label-two-lines-light.png") });

    // a 3D-print preset on this marker (a preset is per marker since 2026-10-20 night:
    // its panel's Preset row): the core's pixel font, drawn as its ink (no text)
    await clickAt(page, 0, 0);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    const modal = await openPresets(page);
    await modal.locator('[data-coll="builtin"]').click();
    await modal.getByTestId("presets-nav").locator('[data-chip="3D print"]').click();
    await modal.locator(".card[data-card]").first().click();
    await page.getByTestId("presets-select").click();
    await expect(modal).toHaveCount(0);
    await page.getByTestId("panel-ok").click();
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    await idle(page);
    await expect.poll(async () => (await state(page)).plans.f1?.label?.font).toBe("pixel");
    s = await state(page);
    const polys = s.plans.f1.label.polygons as { outer: number[][] }[];
    expect(polys.length).toBeGreaterThan(0);
    await expect(page.locator('[data-testid="label-text"] text')).toHaveCount(0);
    const ink = (await page.locator('[data-testid="label-text"] [data-label-ink]').boundingBox())!;
    const xs = polys.flatMap((p) => p.outer.map((q) => q[0])), ys = polys.flatMap((p) => p.outer.map((q) => q[1]));
    const [x0, y1] = await toClient(page, Math.min(...xs), Math.max(...ys));
    const [x1, y0] = await toClient(page, Math.max(...xs), Math.min(...ys));
    for (const [got, exp] of [[ink.x, x0], [ink.y, y1], [ink.x + ink.width, x1], [ink.y + ink.height, y0]]) expect(Math.abs(got - exp)).toBeLessThan(1);
    await page.screenshot({ path: path.join(SHOTS, "label-pixel-light.png") });
  });
});
