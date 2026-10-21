// The floating panel settles where it opens, and a crash is never a blank page
// (arucostudio.com went blank, 2026-10-21: React #185, "Maximum update depth
// exceeded", thrown from <FloatingPanel>'s layout effect). At 150 % or a page
// zoom (Zach's Windows) the panel is a fraction of a px tall. It placed itself
// from whole-px offsetHeight / scrollHeight, rounded down while it was free and
// up while its own max-height clipped it, so lifted off the floor it moved 1 px
// up and back on every render until React unmounted the app.
// This machine's fonts at 100 % lay the panel out in whole px, so the fraction
// is put on its foot; the markers are on the sticker sheet's bottom row, so
// the panel lifts off the floor; every tab is opened, one marker and a batch.
// The mock core: the loop is the panel's layout, whatever the core answers.
import { expect, test, type Page } from "@playwright/test";
import { idle, loadExample, state } from "./helpers";

// Windows' classic scrollbars, which Playwright hides by default: one takes 15 px
// of a clipped body and re-wraps a line (the Label tab measured 17 px taller),
// a second way for the panel's measure to depend on its own max-height
test.use({ launchOptions: { ignoreDefaultArgs: ["--hide-scrollbars"] } });

/** the sheet's bottom row (model/examples.ts sticker-sheet) */
const BOTTOM = ["sheet-f10", "sheet-f11", "sheet-f12"];
/** fractions of a px on the panel (1/16 and 1/10 looped the old placement) */
const FRACTIONS = [0.0625, 0.1, 0.1875];

/** What must never happen: an uncaught error, React's own report of one, the
 *  crash screen's log, or the panel's cap on a placement that did not settle. */
function watch(page: Page): string[] {
  const bad: string[] = [];
  page.on("pageerror", (e) => bad.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (/Maximum update depth|did not settle|stopped on an error|error occurred in the/.test(m.text())) bad.push(`${m.type()}: ${m.text()}`);
  });
  return bad;
}

async function sheet(page: Page, skin: string): Promise<void> {
  await page.addInitScript((s) => { try { localStorage.setItem("aruco-studio.skin", s); } catch { /* storage blocked */ } }, skin);
  await page.goto("/?core=mock");
  await expect(page.getByTestId("app")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).__aruco?.kind)).toBe("mock");
  await loadExample(page, "sticker-sheet");
  await idle(page);
}

/** The panel's foot a fraction of a px taller, as a 150 % or zoomed screen makes it. */
async function fraction(page: Page, px: number): Promise<void> {
  await page.evaluate((v) => {
    const tag = document.getElementById("e2e-fraction") ?? document.head.appendChild(Object.assign(document.createElement("style"), { id: "e2e-fraction" }));
    tag.textContent = `.xpanel .fpanel-foot { padding-bottom: ${v}px !important; }`;
  }, px);
}

async function clickMarker(page: Page, fid: string, shift = false): Promise<void> {
  const ink = (await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().boundingBox())!;
  if (shift) await page.keyboard.down("Shift");
  await page.mouse.click(ink.x + ink.width / 2, ink.y + ink.height / 2);
  if (shift) await page.keyboard.up("Shift");
}

/** One of the panel's tabs (no waiting on a panel that is gone: settled() says why). */
async function openTab(page: Page, tab: "label" | "make" | "marker"): Promise<void> {
  await page.locator(`[data-testid="extrude-panel"] [role=tab][data-tab="${tab}"]`).click({ timeout: 5_000 });
}

/** The panel is up, still, lifted off the floor, and not clipped by its own max-height. */
async function settled(page: Page, bad: string[], what: string): Promise<void> {
  // a frame first, so an error the last step raised has been reported
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
  expect(bad, what).toEqual([]);
  await expect(page.getByTestId("crash"), what).toHaveCount(0);
  await expect(page.getByTestId("app"), what).toBeVisible();
  const panel = page.getByTestId("extrude-panel");
  await expect(panel, what).toBeVisible();
  // its style the same over five frames: it settled
  const styles = await panel.evaluate((el) => new Promise<string[]>((done) => {
    const seen: string[] = [];
    const tick = () => { seen.push(el.getAttribute("style") ?? ""); if (seen.length < 5) requestAnimationFrame(tick); else done(seen); };
    tick();
  }));
  expect(new Set(styles).size, `${what}: the panel moved between frames: ${styles.join(" | ")}`).toBe(1);
  const g = await panel.evaluate((el) => {
    const body = el.querySelector(".fpanel-body") as HTMLElement;
    const host = (el as HTMLElement).offsetParent as HTMLElement;
    const r = el.getBoundingClientRect(), h = host.getBoundingClientRect();
    return { anchored: (el as HTMLElement).dataset.anchored ?? null, bottom: r.bottom - h.top, floor: h.height - 60,
      clip: body.scrollHeight - body.clientHeight, maxH: parseFloat((el as HTMLElement).style.maxHeight), height: r.height };
  });
  expect(g.anchored, `${what}: opened beside its markers`).not.toBeNull();
  // lifted: its bottom on the floor (the toolbar's strip), give or take the px rounded up
  expect(g.bottom, `${what}: lifted off the floor`).toBeGreaterThan(g.floor - 4);
  expect(g.bottom, `${what}: lifted off the floor`).toBeLessThanOrEqual(g.floor + 0.5);
  // a panel that fits is never clipped by its own max-height (the loop's first step)
  expect(g.maxH, `${what}: room for the panel`).toBeGreaterThanOrEqual(g.height);
  expect(g.clip, `${what}: the body is not clipped`).toBeLessThanOrEqual(0);
}

/** A bottom-row marker's panel, then the row's batch panel, at each fraction, on every tab. */
async function everyTab(page: Page, skin: string): Promise<void> {
  const bad = watch(page);
  await sheet(page, skin);
  for (const px of FRACTIONS) {
    await fraction(page, px);
    await clickMarker(page, BOTTOM[0]);
    await settled(page, bad, `${skin}, +${px} px, ${BOTTOM[0]} opened`);
    expect((await state(page)).panel.featureId).toBe(BOTTOM[0]);
    for (const tab of ["label", "make", "marker"] as const) {
      await openTab(page, tab);
      await settled(page, bad, `${skin}, +${px} px, ${BOTTOM[0]}, ${tab}`);
    }
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    // the batch panel (BatchPanel.tsx) is the same FloatingPanel, beside the row
    for (const fid of BOTTOM) await clickMarker(page, fid, true);
    await page.keyboard.press("a");
    await settled(page, bad, `${skin}, +${px} px, batch opened`);
    await expect(page.getByTestId("batch-title")).toHaveText(` · ${BOTTOM.length} markers`);
    for (const tab of ["label", "make", "marker"] as const) {
      await openTab(page, tab);
      await settled(page, bad, `${skin}, +${px} px, batch, ${tab}`);
    }
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
    await page.keyboard.press("Escape");
  }
}

test.describe("the floating panel settles (React #185, 2026-10-21)", () => {
  for (const skin of ["fusion", "studio"]) {
    test(`a · ${skin}: a bottom-row marker's panel at a fraction of a px, every tab, settles; so does a batch`, async ({ page }) => {
      await everyTab(page, skin);
    });
  }

  test("b · a crash shows Something went wrong with Reload and Open a blank document, never a blank page", async ({ page }) => {
    const logged: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") logged.push(m.text()); });
    await sheet(page, "studio");
    // a component that throws: the panel's layout effect, made to fail
    const breakPanel = () => page.evaluate(() => {
      const own = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetParent")!;
      (window as any).__offsetParent = own;
      Object.defineProperty(HTMLElement.prototype, "offsetParent", {
        configurable: true,
        get(this: HTMLElement) { if (this.classList.contains("fpanel")) throw new Error("a test crash in the panel"); return own.get!.call(this); },
      });
    });
    const mendPanel = () => page.evaluate(() => Object.defineProperty(HTMLElement.prototype, "offsetParent", (window as any).__offsetParent));
    await breakPanel();
    await clickMarker(page, BOTTOM[0]);
    const crash = page.getByTestId("crash");
    await expect(crash).toBeVisible();
    await expect(crash.getByRole("heading")).toHaveText("Something went wrong");
    await expect(crash.getByTestId("crash-reload")).toHaveText("Reload");
    await expect(crash.getByTestId("crash-blank")).toHaveText("Open a blank document");
    await expect(crash.getByTestId("crash-message")).toHaveText("a test crash in the panel");
    await expect(page.getByTestId("app")).toHaveCount(0);
    expect(logged.some((t) => t.includes("ArUco Studio stopped on an error")), "the crash is logged").toBe(true);
    // Open a blank document: File › New's way, then the Studio again
    await mendPanel();
    await crash.getByTestId("crash-blank").click();
    await expect(crash).toHaveCount(0);
    await expect(page.getByTestId("app")).toBeVisible();
    const s = await state(page);
    expect([s.doc.name, s.doc.shapes.length, s.doc.features.length, s.panel.open]).toEqual(["Untitled", 0, 0, false]);
    // Reload: the page again
    await loadExample(page, "sticker-sheet");
    await idle(page);
    await breakPanel();
    await clickMarker(page, BOTTOM[0]);
    await expect(crash).toBeVisible();
    await crash.getByTestId("crash-reload").click();
    await expect(page.getByTestId("app")).toBeVisible();
    await expect(crash).toHaveCount(0);
  });

  // Zach's screen: Windows at 150 % (the classic scrollbars are on for the whole file)
  test.describe("at 150 %", () => {
    test.use({ deviceScaleFactor: 1.5 });
    test("c · fusion at 150 %: the same, settles", async ({ page }) => {
      await everyTab(page, "fusion");
    });
  });
});
