// The canvas3 lane (Zach's 2026-10-21 feedback; docs/design/panel_skeleton.md,
// "On the model / canvas"), on the real core:
// a · a label is drawn in the colour it prints in (white knocked out of the
//     black, black on the quiet zone or outside), never the selection's;
// b · the turn arc only on the feature in focus: none with nothing selected;
// c · the focused grid's marker and separation dims, and its outer W × H as
//     driven, read-only dims;
// d · View › Marker info: the sheet's caption under every marker, kept per browser;
// e · Home: the examples' thumbnails draw their markers once the core has
//     planned them; New (the card and the header's button) makes an empty document.
// Colours are compared as the browser computes them; positions are measured.
// CANVAS3_SHOTS=<dir> saves the review screenshots there (else the test's output dir).
import { expect, test, type Page } from "@playwright/test";
import { clickAt, CORE, coreReady, idle, loadExample, openMenu, openStudio, pickSkin, state, toggleTheme } from "./helpers";

const SHOTS = process.env.CANVAS3_SHOTS;
const shot = (page: Page, name: string) => page.screenshot({ path: SHOTS ? `${SHOTS}/${name}.png` : test.info().outputPath(`${name}.png`) });

/** A CSS colour (a var() too) as the browser computes an SVG fill. */
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

/** Every label's computed fill (its text lines, or its pixel ink), by feature id. */
async function labelFills(page: Page): Promise<Record<string, string[]>> {
  return page.locator('[data-testid="label-text"]').evaluateAll((gs) => Object.fromEntries(gs.map((g) => [
    g.getAttribute("data-feature")!,
    [...g.querySelectorAll("text, [data-label-ink]")].map((e) => getComputedStyle(e).fill),
  ])));
}

/** Nothing selected, no panel: Esc until the probe says so. */
async function deselect(page: Page): Promise<void> {
  for (let i = 0; i < 3; i++) await page.keyboard.press("Escape");
  await expect.poll(async () => { const s = await state(page); return !s.sel && !s.panel.open; }).toBe(true);
}

/** The centre of a feature's marker outline (mm). */
async function markerCentre(page: Page, fid: string): Promise<[number, number]> {
  const p = (await state(page)).plans[fid];
  const xs = p.outer.map((q: number[]) => q[0]), ys = p.outer.map((q: number[]) => q[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

async function sheet(page: Page): Promise<any> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "sticker-sheet");
  await idle(page);
  const s = await state(page);
  expect(s.doc.features).toHaveLength(12);
  for (const f of s.doc.features) expect(s.plans[f.id], `${f.id} is planned`).toBeTruthy();
  return s;
}

test.describe("canvas3 (real core)", () => {
  test.skip(CORE !== "real", "the real core's plans");

  test("a · labels print white (knocked out) or black, never the selection blue; selecting adds no blue", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    // three labels: on the black border row (white), on the quiet zone (black), outside (black)
    const lab = (extra: object) => ({ on: true, text: "#{ids}", ...extra });
    const doc = {
      format: "arucostudio-web", version: 3, name: "Three labels", id_ledger: {}, preset: null,
      shapes: [0, 1, 2].map((i) => ({ kind: "rect", id: `r${i}`, cx: i * 70, cy: 0, w: 50, h: 50, angle_deg: 0 })),
      features: [
        { id: "f0", key: "f0", profile: { outer: "r0", holes: [] }, holes: "avoid", marker: { type: "single" }, label: lab({}), set: [] },
        { id: "f1", key: "f1", profile: { outer: "r1", holes: [] }, holes: "avoid", marker: { type: "single" }, label: lab({ surface: "white" }), set: [] },
        { id: "f2", key: "f2", profile: { outer: "r2", holes: [] }, holes: "avoid", marker: { type: "single" }, label: lab({ place: "outside" }), set: [] },
      ],
    };
    await openMenu(page, "file");
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
    await chooser.setFiles({ name: "three.arucostudio-web.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(doc)) });
    await idle(page);
    await expect(page.locator('[data-testid="label-text"]')).toHaveCount(3);
    await deselect(page);

    const check = async (where: string) => {
      const white = await resolved(page, "var(--t-white)"), black = await resolved(page, "var(--t-black)");
      const blues = [await resolved(page, "var(--pick)"), await resolved(page, "var(--accent)")];
      // the marker's own paper and ink are those colours (the canvas draws them so)
      expect(await page.locator('[data-marker="f0"] [data-marker-black]').evaluate((e) => getComputedStyle(e).fill), where).toBe(black);
      const fills = await labelFills(page);
      expect(Object.keys(fills).sort(), where).toEqual(["f0", "f1", "f2"]);
      for (const [fid, fs] of Object.entries(fills)) {
        expect(fs.length, `${where} ${fid} has ink`).toBeGreaterThan(0);
        for (const f of fs) {
          expect([white, black], `${where} ${fid}: ${f}`).toContain(f);
          expect(blues, `${where} ${fid} is not the selection's / accent colour`).not.toContain(f);
        }
      }
      expect(fills.f0[0], `${where} on the black row: white`).toBe(white);
      expect(fills.f1[0], `${where} on the quiet zone: black`).toBe(black);
      expect(fills.f2[0], `${where} outside: black`).toBe(black);
      return fills;
    };
    const before = await check("nothing selected");
    await shot(page, "a-labels-light");

    // select the marker: its label keeps its fill
    await clickAt(page, ...(await markerCentre(page, "f0")));
    await expect.poll(async () => (await state(page)).panel.featureId).toBe("f0");
    expect(await labelFills(page)).toEqual(before);
    // select the label itself (the panel closed first: it may cover it): the same fill, and its band's outline shows the selection
    await deselect(page);
    await page.locator('[data-testid="label-text"][data-feature="f1"] text').first().click();
    await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "text", id: "f1" });
    expect(await labelFills(page)).toEqual(before);
    await expect(page.locator("[data-label-sel]")).toHaveCount(1);
    await deselect(page);

    // dark, and every skin
    await toggleTheme(page);
    await check("dark");
    await shot(page, "a-labels-dark");
    for (const skin of ["fusion", "onshape", "unstyled"] as const) {
      await pickSkin(page, skin);
      await check(`skin ${skin}`);
    }
  });

  test("b · the turn arc: none with nothing selected; exactly one on the selected marker", async ({ page }) => {
    const s = await sheet(page);
    await deselect(page);
    await expect(page.getByTestId("turn-arc")).toHaveCount(0);
    await expect(page.locator("[data-turn]")).toHaveCount(0);
    await toggleTheme(page);
    await shot(page, "b-nothing-selected-dark");
    // the 7th (#17, mid-sheet): the panel opens beside it, not over it
    const fid = s.doc.features[6].id;
    await clickAt(page, ...(await markerCentre(page, fid)));
    await expect.poll(async () => (await state(page)).panel.featureId).toBe(fid);
    await expect(page.getByTestId("turn-arc")).toHaveCount(1);
    await expect(page.getByTestId("turn-arc")).toHaveAttribute("data-feature", fid);
    await shot(page, "b-one-selected-dark");
    await deselect(page);
    await expect(page.getByTestId("turn-arc")).toHaveCount(0);
  });

  test("c · the focused grid: marker and separation dims, and the outer W × H driven, grey, with no handle and no input", async ({ page }) => {
    const s = await sheet(page);
    const grid = s.doc.features.find((f: any) => f.marker.type === "grid");
    await clickAt(page, ...(await markerCentre(page, grid.id)));
    await expect.poll(async () => (await state(page)).panel.featureId).toBe(grid.id);
    await idle(page);
    const dims = page.getByTestId("dims");
    await expect(dims.locator('[data-dim="marker.marker_mm"]')).toHaveCount(1);
    await expect(dims.locator('[data-dim="marker.separation_mm"]')).toHaveCount(1);
    const outer = dims.locator('[data-dim="outer"]');
    await expect(outer).toHaveCount(2);
    // WHY the profile, not plan.outer_mm (printdims, Zach 2026-10-21: "I am
    // expecting 123.5"): Outer is the sticker as it prints, and this grid is
    // cut to its 50 x 50 rectangle profile (Trim Profile) while its marker's
    // quiet-zone box (outer_mm) is 49.5 x 49.5
    const st = await state(page);
    const rect = st.doc.shapes.find((x: any) => x.id === grid.profile.outer);
    expect(grid.trim).toBe("profile");
    const want = [rect.w, rect.h].map((v: number) => String(+v.toFixed(2))).sort();
    expect((await outer.locator("text").allTextContents()).sort()).toEqual(want);
    const muted = await resolved(page, "var(--muted)");
    for (let i = 0; i < 2; i++) {
      const d = outer.nth(i);
      await expect(d).toHaveAttribute("data-driven-only", "1");
      await expect(d).toHaveAttribute("data-set", "0");
      expect(await d.locator("text").evaluate((e) => getComputedStyle(e).fill)).toBe(muted);
      await expect(d.locator("[data-handle]")).toHaveCount(0);
      expect(await d.locator(".val").evaluate((e) => getComputedStyle(e).pointerEvents)).toBe("none");
    }
    await shot(page, "c-driven-outer-dims");
    // a click on an outer value types nothing (the marker's does)
    const vb = (await outer.first().locator("text").boundingBox())!;
    await page.mouse.click(vb.x + vb.width / 2, vb.y + vb.height / 2);
    await expect(page.getByTestId("dim-input")).toHaveCount(0);
    await clickAt(page, ...(await markerCentre(page, grid.id)));
    await expect.poll(async () => (await state(page)).panel.featureId).toBe(grid.id);
    await page.locator('[data-dim-label="marker.marker_mm"]').click();
    await expect(page.getByTestId("dim-input")).toHaveCount(1);
    await expect(page.locator('[data-dim-edit="outer"]')).toHaveCount(0);
  });

  test("d · View › Marker info: off by default; the sheet's caption under every marker; it survives a reload", async ({ page }) => {
    const s = await sheet(page);
    await deselect(page);
    await expect(page.getByTestId("marker-info")).toHaveCount(0);
    expect((await state(page)).markerInfo).toBe(false);
    await openMenu(page, "view");
    await expect(page.getByTestId("cmd-marker-info")).toHaveAttribute("aria-checked", "false");
    await page.getByTestId("cmd-marker-info").click();
    const infos = page.getByTestId("marker-info");
    await expect(infos).toHaveCount(12);
    // the text: web_api.sheet's caption with no label, "#1 · 4X4_50 · 44.0 mm"
    const mm = (v: number) => { const t = v.toFixed(2); return t.endsWith("0") ? t.slice(0, -1) : t; };
    for (const f of s.doc.features) {
      const p = s.plans[f.id];
      const ids = p.ids.length === 1 ? `#${p.ids[0]}` : `#${p.ids[0]}-${p.ids[p.ids.length - 1]}`;
      const el = page.locator(`[data-testid="marker-info"][data-feature="${f.id}"]`);
      await expect(el).toHaveText(`${ids} · ${f.marker.dictionary.replace("DICT_", "")} · ${mm(p.marker_mm)} mm`);
      // centred under the outline
      const t = (await el.boundingBox())!, o = (await page.locator(`[data-marker="${f.id}"] [data-marker-outline]`).boundingBox())!;
      expect(Math.abs(t.x + t.width / 2 - (o.x + o.width / 2)), `${f.id} centred`).toBeLessThanOrEqual(1);
      expect(t.y, `${f.id} under the outline`).toBeGreaterThanOrEqual(o.y + o.height - 0.5);
      expect(t.y - (o.y + o.height), `${f.id} just under it`).toBeLessThanOrEqual(12);
    }
    // V1 "Turn it down" (Zach's pick, 2026-10-21; calmcanvas.spec): at rest the line is thin and grey,
    // and a bit more bold on the selected marker and the one pointed at
    await expect(page.locator('[data-testid="marker-info"][data-hot="1"]')).toHaveCount(0);
    expect(await infos.first().evaluate((e) => getComputedStyle(e).fill)).toBe(await resolved(page, "var(--quiet-text)"));
    // never in the document
    expect(JSON.stringify((await state(page)).doc)).not.toContain("markerInfo");
    await toggleTheme(page);
    await shot(page, "d-marker-info-dark");
    // a reload keeps it (this browser), and so does the menu's check
    await page.reload();
    await coreReady(page);
    expect((await state(page)).markerInfo).toBe(true);
    const n = Object.keys((await state(page)).plans).length;
    expect(n).toBeGreaterThan(0);
    await expect(page.getByTestId("marker-info")).toHaveCount(n);
    await openMenu(page, "view");
    await expect(page.getByTestId("cmd-marker-info")).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("cmd-marker-info").click();
    await expect(page.getByTestId("marker-info")).toHaveCount(0);
    await page.reload();
    await coreReady(page);
    expect((await state(page)).markerInfo).toBe(false);
  });

  test("e · Home: example thumbnails draw their markers once planned; New (card, header) makes an empty document", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    await toggleTheme(page);
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    const home = page.getByTestId("home");
    await expect(home).toBeVisible();
    const card = (id: string) => home.locator(`[data-testid=home-example][data-id="${id}"]`);
    // the shapes at once; the markers when the core has planned them
    await expect(card("sticker-sheet").locator(".ex-fill")).toHaveCount(1);
    await expect(card("sticker-sheet").locator("[data-thumb-black]")).toHaveCount(12, { timeout: 60_000 });
    await expect(card("custom-placement").locator("[data-thumb-black]")).toHaveCount(1);
    await expect(card("plate").locator("[data-thumb-black]")).toHaveCount(0);   // a face: no marker
    const ink = await card("sticker-sheet").locator("[data-thumb-black]").first().evaluate((e) => (e as SVGPathElement).getBBox().width * (e as SVGPathElement).getBBox().height);
    expect(ink, "the black has area").toBeGreaterThan(0);
    // New is the first card on this device
    const grid = home.getByTestId("home-new").locator("xpath=..");
    expect(await grid.locator("> *").first().getAttribute("data-testid")).toBe("home-new");
    await expect(home.getByTestId("home-new-top")).toBeVisible();
    await shot(page, "e-home-thumbs-new");

    // the work on this device: a document with markers, its card draws them (kept when leaving the editor)
    await card("sticker-sheet").click();
    await expect(home).toHaveCount(0);
    await idle(page);
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    await expect(home.getByTestId("home-draft").locator("[data-thumb-black]")).toHaveCount(12);
    await shot(page, "e-home-draft-markers-dark");
    // a reload straight on Home: the examples' markers come from this browser, no plan needed
    await page.reload();
    await expect(page.getByTestId("home")).toBeVisible();
    await expect(card("sticker-sheet").locator("[data-thumb-black]")).toHaveCount(12);

    // the New card: a new, empty document in the editor
    await coreReady(page);
    await page.getByTestId("home").getByTestId("home-new").click();
    await expect(page.getByTestId("home")).toHaveCount(0);
    await expect.poll(async () => { const s = await state(page); return [s.doc.shapes.length, s.doc.features.length]; }).toEqual([0, 0]);
    // the header's New, from Home with an example open
    await loadExample(page, "plate");
    await expect.poll(async () => (await state(page)).doc.shapes.length).toBe(3);
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    await page.getByTestId("home-new-top").click();
    await expect(page.getByTestId("home")).toHaveCount(0);
    await expect.poll(async () => { const s = await state(page); return [s.doc.shapes.length, s.doc.features.length]; }).toEqual([0, 0]);
  });
});
