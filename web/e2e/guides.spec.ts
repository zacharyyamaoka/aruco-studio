// The guides (/guides/, written by docs/build_guides.py) and the label placement board they open:
// /?example=label-placement loads web/public/examples/label-placement.arucostudio-web.json into the
// Studio, and every marker there plans exactly as the guide's Verify run planned it
// (guides/label-placement/verify.json: the same ids, cell, outline and rule warnings). Checks read
// what the server sends and what the probe (window.__aruco) and the page draw, never DOM presence alone.
//
//   E2E_PORT=5464 npx playwright test --project=e2e e2e/guides.spec.ts
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, openMenu, state } from "./helpers";

const GUIDES = ["label-placement", "profile-first", "size-step", "heights", "trim", "auto-id"];
const BOARD = "/examples/label-placement.arucostudio-web.json";
const NAME = "Label placement test board";

/** The board's plans in the Studio, by feature id, once every marker has one. */
async function boardPlans(page: Page, n: number): Promise<Record<string, any>> {
  await expect.poll(async () => Object.values((await state(page)).plans ?? {}).filter((p: any) => p?.ok).length,
    { timeout: 120_000, message: "every marker on the board is planned" }).toBe(n);
  return (await state(page)).plans;
}

test.describe("guides", () => {
  test("1 · /?example=label-placement opens the board, and every marker plans as the guide's Verify planned it", async ({ page, request }) => {
    test.skip(CORE === "mock", "the guide's numbers are the real core's");
    const run = await (await request.get("/guides/label-placement/verify.json")).json();
    const file = await request.get(BOARD);
    expect(file.status()).toBe(200);
    expect(file.headers()["content-type"]).toContain("json");
    const board = await file.json();
    expect(board.features).toHaveLength(run.cases.length);

    await page.goto("/?example=label-placement");
    await expect(page.getByTestId("app")).toBeVisible();
    // WHY before the core: the board opens as soon as the hosted files have started, and its note stays 4 s
    await expect.poll(async () => (await page.evaluate(() => (window as any).__aruco?.state().doc.name)) ?? null,
      { timeout: 30_000, message: "the board is open" }).toBe(NAME);
    await expect(page.getByTestId("note")).toContainText(`Opened the example “${NAME}”`);
    // the parameter is gone, so a reload keeps what was done since
    expect(new URL(page.url()).searchParams.has("example")).toBe(false);
    await coreReady(page);
    const doc = (await state(page)).doc;
    expect(doc.features.map((f: any) => f.id)).toEqual(board.features.map((f: any) => f.id));
    expect(doc.shapes).toEqual(board.shapes);

    const plans = await boardPlans(page, run.cases.length);
    for (const c of run.cases) {
      const p = plans[c.feature];
      expect(p, c.key).toBeTruthy();
      expect(p.ids, `${c.key} ids`).toEqual(c.plan.ids);
      expect(p.cell_mm, `${c.key} cell`).toBeCloseTo(c.plan.cell_mm, 6);
      expect(p.marker_mm, `${c.key} marker`).toBeCloseTo(c.plan.marker_mm, 6);
      expect(p.outer_mm[0], `${c.key} outline w`).toBeCloseTo(c.plan.outer_mm[0], 6);
      expect(p.outer_mm[1], `${c.key} outline h`).toBeCloseTo(c.plan.outer_mm[1], 6);
      // the rule warnings the guide quotes are the ones the Studio's panel gets
      const hits = p.warnings.filter((w: any) => ["warn", "error"].includes(w.level)
        && (w.field.startsWith("label.") || w.field.startsWith("marker.corner_mark"))).map((w: any) => w.text);
      expect(hits, `${c.key} rules`).toEqual(c.rules.hits);
    }
    // and the markers are drawn where the board puts them: the canvas fits them all
    const box = await page.getByTestId("viewport").boundingBox();
    expect(box!.width).toBeGreaterThan(300);
  });

  test("2 · the guide's Open in the Studio link opens the board", async ({ page }) => {
    await page.goto("/guides/label-placement/");
    const open = page.locator('a[data-cta="open-board"]');
    await expect(open).toHaveAttribute("href", "/?example=label-placement");
    await open.click();
    await expect(page.getByTestId("app")).toBeVisible();
    await expect.poll(async () => (await state(page)).doc.name, { timeout: 60_000 }).toBe(NAME);
    expect((await state(page)).doc.features).toHaveLength(28);
  });

  test("3 · a name the site does not serve is said, and the Studio keeps its document", async ({ page }) => {
    await page.goto(CORE === "mock" ? "/?core=mock&example=no-such-board" : "/?example=no-such-board");
    await expect(page.getByTestId("note")).toContainText("Could not open the example “no-such-board”: there is no such example");
    expect((await state(page)).doc.name).toBe("Plate");
    expect(new URL(page.url()).searchParams.has("example")).toBe(false);
  });

  test("4 · /guides/ lists every guide, each page is a real file that fits a phone", async ({ page, request }) => {
    const res = await page.goto("/guides/");
    expect(res!.status()).toBe(200);
    expect(await page.locator("#root").count(), "a real page, not the Studio's SPA shell").toBe(0);
    await expect(page.locator("h1")).toHaveText("Guides");
    expect(await page.locator("a.card").evaluateAll((as) => as.map((a) => a.getAttribute("href"))))
      .toEqual(GUIDES.map((g) => `/guides/${g}/`));
    for (const g of GUIDES) {
      const raw = await request.get(`/guides/${g}/`);
      expect(raw.status(), g).toBe(200);
      expect(raw.headers()["content-type"], g).toContain("text/html");
      expect(await raw.text(), g).toContain("Generated by docs/build_guides.py");
      for (const width of [1280, 375]) {
        await page.setViewportSize({ width, height: 800 });
        await page.goto(`/guides/${g}/`);
        const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth,
          h1: document.querySelector("h1")?.getBoundingClientRect().width ?? 0 }));
        expect(m.sw, `${g} at ${width} px: no sideways scroll`).toBeLessThanOrEqual(m.iw);
        expect(m.h1, `${g} has its title`).toBeGreaterThan(100);
      }
    }
  });

  test("5 · every verdict on the label page is the run's, and its pictures load", async ({ page, request }) => {
    const run = await (await request.get("/guides/label-placement/verify.json")).json();
    await page.goto("/guides/label-placement/");
    const rows = await page.locator(".mk").evaluateAll((els) => els.map((e) => [e.getAttribute("data-key"), e.getAttribute("data-verdict")]));
    expect(rows).toEqual(run.cases.map((c: any) => [c.key, c.verdict]));
    // the stickers are drawn (a <use> of each core-drawn symbol has a size), the views a label lost load
    const drawn = await page.locator(".mk .thumb svg").evaluateAll((els) => els.filter((e) => e.getBoundingClientRect().height > 20).length);
    expect(drawn).toBe(run.cases.length);
    const imgs = page.locator(".views img");
    const n = await imgs.count();
    // one pair per marker a detector lost a view of (the Studio's detector's when it did)
    expect(n).toBe(2 * run.cases.filter((c: any) => Object.values(c.verify).some((v: any) => v.pictures)).length);
    for (let i = 0; i < n; i++) expect(await imgs.nth(i).evaluate((im: HTMLImageElement) => im.complete && im.naturalWidth > 0)).toBe(true);
  });

  test("7 · the Studio's own Verify agrees with the run made with its OpenCV: every marker's angle sweep reads to the same tilt", async ({ page, request }) => {
    test.skip(CORE === "mock", "the browser's OpenCV is the real core's");
    test.setTimeout(600_000);
    const run = await (await request.get("/guides/label-placement/verify.json")).json();
    const studio = run.detectors.find((d: any) => d.studio);
    test.skip(!studio, "the run did not use the Studio's OpenCV");
    await page.goto("/?example=label-placement");
    await expect.poll(async () => (await page.evaluate(() => (window as any).__aruco?.state().doc.name)) ?? null, { timeout: 30_000 }).toBe(NAME);
    await coreReady(page);
    await boardPlans(page, run.cases.length);
    await page.evaluate(() => (window as any).__arucoVerify.open("lp-A1"));
    const legend = page.getByTestId("sweep-legend");
    await expect(legend).toHaveCount(run.cases.length, { timeout: 60_000 });
    // the dialog sweeps every marker, one view at a time: about 0.2 s a view, 18 views a marker
    await expect.poll(async () => (await legend.allInnerTexts()).filter((t) => t.includes("sweeping")).length,
      { timeout: 540_000, intervals: [2000], message: "every marker swept" }).toBe(0);
    const got = Object.fromEntries(await legend.evaluateAll((els) => els.map((e) => [e.getAttribute("data-feature"), e.getAttribute("data-reads-to")])));
    const want = Object.fromEntries(run.cases.map((c: any) => [c.feature, String(c.verify[studio.opencv].sweep_reads_to_deg.marked ?? "")]));
    expect(got, `the browser's sweep (OpenCV ${studio.opencv} in Pyodide) = the run's`).toEqual(want);
  });

  test("6 · Help and account ▸ Guides, and the landing's top bar and footer, link to /guides/", async ({ page }) => {
    await page.goto(CORE === "mock" ? "/?core=mock" : "/");
    await expect(page.getByTestId("app")).toBeVisible();
    await expect((await openMenu(page, "account")).getByTestId("guides-menu")).toHaveAttribute("href", "/guides/");
    await page.goto("/about/");
    await expect(page.locator('nav.top a[href="/guides/"]')).toBeVisible();
    await expect(page.locator('footer a[href="/guides/"]')).toHaveText("Guides");
  });
});
