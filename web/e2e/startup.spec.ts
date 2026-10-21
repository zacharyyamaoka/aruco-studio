// The Studio while the core starts, fails or is slow (Zach, 2026-10-20 night:
// "BUG: seems to be stuck loading?"): click the face and press A before the
// core is up. The panel says what it waits for -- "Starting up… N s",
// "Couldn't start" with Reload (the reason behind Details), the presets'
// error with Retry, "Still planning…" with Retry -- never a bare "Loading…"
// or "Planning…", and recovers by itself where it can. No core chip in the
// chrome (Zach, 2026-10-20 night: "back end details ... it shouldn't clutter
// the main viewer"): ?'s popover holds the status line. The faults are Playwright routes on the core's zip and
// the test-only window.__arucoFault (web/src/coreSource.ts). Screenshots
// (1280 × 800) go to STARTUP_SHOTS (default test-results/startup).
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, openPresets, openStudio, state } from "./helpers";

const SHOTS = process.env.STARTUP_SHOTS ?? "test-results/startup";
const ZIP = "**/py/aruco_studio.zip";
const panel = (page: Page) => page.getByTestId("extrude-panel");
const wait = (page: Page) => page.getByTestId("plan-wait");

/** Click the plate's face and press A (the default document is the plate). */
async function faceAndA(page: Page): Promise<void> {
  await clickAt(page, 60, 40);
  await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
  await page.keyboard.press("a");
  await expect(panel(page)).toBeVisible();
}

/** The panel's words never wait vaguely: no bare "Loading…" or "Planning…". */
async function noVagueWait(page: Page): Promise<void> {
  const text = await panel(page).innerText();
  expect(text, "the panel says what it waits for").not.toMatch(/(^|\s)(Loading|Planning)…/);
}

/** The marker's preset is set and the plan is drawn, with its summary in the footer. */
async function recovered(page: Page): Promise<void> {
  await expect.poll(async () => !!(await state(page)).feature?.preset, { timeout: 60_000, message: "the marker's preset is set" }).toBe(true);
  expect((await state(page)).doc.default_preset, "and a new marker's").toBeTruthy();
  await expect.poll(async () => !!(await state(page)).plan?.outer?.length, { timeout: 60_000, message: "the plan is ok" }).toBe(true);
  await expect(wait(page)).toHaveCount(0);
  await expect(page.getByTestId("panel-preset")).not.toContainText("Starting");
  await noVagueWait(page);
}

const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`) });

/** ?'s status line (open the popover, read it, close it). */
async function status(page: Page, check: (line: ReturnType<Page["getByTestId"]>) => Promise<void>): Promise<void> {
  await page.getByTestId("help").click();
  const line = page.getByTestId("core-status");
  await expect(line).toBeVisible();
  await check(line);
  await page.getByTestId("help").click();
  await expect(page.getByTestId("help-popover")).toHaveCount(0);
}

test.describe(`startup waits (${CORE} core)`, () => {
  test("a · A while the core starts: 'Starting up…' (with its seconds), then the preset and the plan, no reload", async ({ page }) => {
    test.skip(CORE === "mock", "the zip is the real core's");
    let release!: () => void;
    const held = new Promise<void>((r) => { release = r; });
    let asked = 0, askedAt = 0;
    await page.route(ZIP, async (route) => { asked += 1; askedAt = Date.now(); await held; await route.continue(); });
    await openStudio(page);
    await faceAndA(page);
    await expect(wait(page)).toHaveAttribute("data-wait", "core-loading");
    await expect(wait(page)).toContainText("Starting up…");
    await expect(page.getByTestId("preset-wait")).toHaveText("Starting up…");
    // no core chip in the chrome while it loads
    await expect(page.getByTestId("core-chip")).toHaveCount(0);
    await expect.poll(() => asked, { message: "the worker asked for the zip (and is held)" }).toBe(1);
    // sample the wait: always "Starting up…", never the vague words
    for (let i = 0; i < 8; i++) {
      await noVagueWait(page);
      await expect(wait(page)).toContainText("Starting up…");
      await page.waitForTimeout(250);
    }
    // after 3 s the seconds show, in the panel and in ?'s status line
    await expect(wait(page)).toHaveText(/^Starting up… \d+ s$/, { timeout: 10_000 });
    await status(page, (line) => expect(line).toHaveText(/^Starting up… \d+ s$/));
    // the zip held 6 s in all
    await page.waitForTimeout(Math.max(0, 6000 - (Date.now() - askedAt)));
    await shot(page, "a-waiting");
    release();
    await coreReady(page);
    await recovered(page);
    await status(page, (line) => expect(line).toHaveText(/^Ready in \d+\.\d s$/));
    await expect(page.getByTestId("core-chip")).toHaveCount(0);
    await shot(page, "a-recovered");
  });

  test("b · the first presets call fails: the retry recovers by itself", async ({ page }) => {
    await page.addInitScript(() => { (window as any).__arucoFault = { presets: 1 }; });
    await openStudio(page);
    await faceAndA(page);
    await recovered(page);
    // the fault fired (it is spent), and nothing asks for a Retry
    expect(await page.evaluate(() => (window as any).__arucoFault.presets)).toBe(0);
    await expect(page.getByTestId("plan-wait-action")).toHaveCount(0);
  });

  test("c · every presets call fails: a lasting error with Retry; cleared, Retry recovers", async ({ page }) => {
    await page.addInitScript(() => { (window as any).__arucoFault = { presets: Infinity }; });
    await openStudio(page);
    await faceAndA(page);
    await expect(wait(page)).toHaveAttribute("data-wait", "facts-error", { timeout: 60_000 });
    await expect(wait(page).locator(".wait-text")).toHaveText("Couldn't load the presets");
    await expect(page.getByTestId("plan-wait-action")).toHaveText("Retry");
    // the reason is behind Details
    await expect(page.getByTestId("plan-wait-detail")).toBeHidden();
    await page.getByTestId("plan-wait-details").locator("summary").click();
    await expect(page.getByTestId("plan-wait-detail")).toHaveText("The core didn't answer: presets: injected fault");
    await expect(page.getByTestId("preset-wait")).toHaveText("Couldn't load the presets");
    await noVagueWait(page);
    // it lasts: no toast that goes away
    await page.waitForTimeout(5000);
    await expect(wait(page)).toHaveAttribute("data-wait", "facts-error");
    await expect(page.getByTestId("plan-wait-action")).toHaveText("Retry");
    await shot(page, "c-presets-error");
    // the presets dialog says the same, with its own Retry
    await page.getByTestId("panel-preset").click();
    await expect(page.getByTestId("presets-wait")).toHaveAttribute("data-wait", "facts-error");
    await expect(page.getByTestId("presets-wait-action")).toHaveText("Retry");
    await page.locator('[data-testid="presets-modal"] .close').click();
    await expect(page.getByTestId("presets-modal")).toHaveCount(0);
    await page.evaluate(() => { (window as any).__arucoFault = undefined; });
    await page.getByTestId("plan-wait-action").click();
    await recovered(page);
    await shot(page, "c-recovered");
  });

  test("d · the core's zip is aborted: ?'s status and the panel say 'Couldn't start' with Reload (the reason behind Details), not 'Loading…'", async ({ page }) => {
    test.skip(CORE === "mock", "the zip is the real core's");
    await page.route(ZIP, (route) => route.abort());
    await openStudio(page);
    await expect.poll(async () => (await state(page)).core.state, { timeout: 60_000 }).toBe("error");
    await expect(page.getByTestId("core-chip")).toHaveCount(0);
    await status(page, async (line) => {
      await expect(line).toHaveAttribute("data-state", "error");
      await expect(line.locator(".wait-text")).toHaveText("Couldn't start");
      await expect(page.getByTestId("core-status-wait-action")).toHaveText("Reload");
      await page.getByTestId("core-status-wait-details").locator("summary").click();
      await expect(page.getByTestId("core-status-wait-detail")).toHaveText(/^The Python core failed to start: could not download py\/aruco_studio\.zip/);
    });
    await faceAndA(page);
    await expect(wait(page)).toHaveAttribute("data-wait", "core-error");
    await expect(wait(page).locator(".wait-text")).toHaveText("Couldn't start");
    await expect(page.getByTestId("plan-wait-detail")).toBeHidden();
    await page.getByTestId("plan-wait-details").locator("summary").click();
    await expect(page.getByTestId("plan-wait-detail")).toHaveText(/^The Python core failed to start: could not download py\/aruco_studio\.zip/);
    await expect(page.getByTestId("plan-wait-action")).toHaveText("Reload");
    await expect(page.getByTestId("preset-wait")).toHaveText("Couldn't start");
    await noVagueWait(page);
    await shot(page, "d-core-error");
    // Reload, with the zip let through: the core starts and plans
    await page.unroute(ZIP);
    await page.getByTestId("plan-wait-action").click();
    await coreReady(page);
    await faceAndA(page);
    await recovered(page);
  });

  test("f · the dialogs that ask the core say 'Starting up…' too (Verify, Re-ID, the presets)", async ({ page }) => {
    test.skip(CORE === "mock", "the zip is the real core's");
    let release!: () => void;
    const held = new Promise<void>((r) => { release = r; });
    await page.route(ZIP, async (route) => { await held; await route.continue(); });
    await openStudio(page);
    await faceAndA(page);
    await page.getByTestId("panel-ok").click();
    await expect(panel(page)).toHaveCount(0);
    await page.keyboard.press("k");
    await expect(page.getByTestId("verify-wait")).toHaveAttribute("data-wait", "core-loading");
    await expect(page.getByTestId("verify-wait")).toContainText("Starting up…");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("verify-dialog")).toHaveCount(0);
    await page.getByTestId("menu-edit").click();
    await page.getByTestId("cmd-reid").click();
    await expect(page.getByTestId("reid-wait")).toHaveAttribute("data-wait", "core-loading");
    await page.getByTestId("reid-cancel").click();
    await openPresets(page);
    await expect(page.getByTestId("presets-wait")).toHaveAttribute("data-wait", "core-loading");
    await expect(page.getByTestId("presets-wait")).toContainText("Starting up…");
    release();
    // the presets arrive in the open dialog
    await expect(page.locator('[data-testid="preset-list"] [data-card]').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("presets-wait")).toHaveCount(0);
  });

  test("e · a plan held over 8 s: 'Still planning… the core is busy' with Retry", async ({ page }) => {
    await page.addInitScript(() => { (window as any).__arucoFault = { delay: { plan: 60_000 } }; });
    await openStudio(page);
    await coreReady(page);
    await faceAndA(page);
    await expect(wait(page)).toHaveAttribute("data-wait", "planning");
    await expect(wait(page)).toHaveText("Planning the marker…");
    const t0 = Date.now();
    await expect(wait(page)).toHaveAttribute("data-wait", "plan-slow", { timeout: 15_000 });
    expect(Date.now() - t0, "not before 8 s").toBeGreaterThan(6_000);
    await expect(wait(page)).toContainText("Still planning… the core is busy");
    await expect(page.getByTestId("plan-wait-action")).toHaveText("Retry");
    await shot(page, "e-still-planning");
    await page.evaluate(() => { (window as any).__arucoFault = undefined; });
    await page.getByTestId("plan-wait-action").click();
    await expect.poll(async () => !!(await state(page)).plan?.outer?.length, { timeout: 30_000, message: "the retried plan is ok" }).toBe(true);
    await expect(wait(page)).toHaveCount(0);
  });
});
