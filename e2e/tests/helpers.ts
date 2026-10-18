// Shared steps of the Studio's e2e tests. Every bar reads the DOM, the
// store (window.__studio) or the API, never a picture; the screenshots in
// reports/screens/ are for people.
import { expect, type Page, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export const ROOT = path.resolve(__dirname, "..", "..");
export const SCREENS = path.join(ROOT, "reports", "screens");
// the ports: 5360 / 5361, or what tools/check.py was given (ARUCO_STUDIO_API_PORT / _UI_PORT)
export const API = `http://127.0.0.1:${process.env.ARUCO_STUDIO_API_PORT || 5360}`;
const PY = path.join(ROOT, ".venv", "Scripts", "python.exe");

/** The Studio with the dev flag that keeps the drawing tools (R C P O H)
 *  and starts on the canvas, not the gallery: what the tests before the
 *  gallery (N-3, 2026-10-17) drive. gallery.spec.ts runs without it. */
export const STUDIO_URL = "/?draw=1";

/** The preset the tests' new tags are made with. The new-tag form starts
 *  on "Inkjet · Letter vinyl" since 2026-10-17 (CF-13); the tests written
 *  before it drive 3D tags, so `fresh` / `freshFile` name the 3D "Default"
 *  explicitly, as a pick in the form would (newtag.spec.ts: the vinyl
 *  default itself; pass `null` to keep it). */
export const TEST_NEW_PRESET = "Default";

/** The new-tag form's preset, as a pick in it sets it. */
export async function pickNewPreset(page: Page, name: string) {
  await page.evaluate((n) => (window as any).__studio.store.getState().setNew("newPreset", n), name);
  await idle(page);
}

/** A fresh scene on the server, the app loaded on it. */
export async function fresh(page: Page, name = "e2e", preset: string | null = TEST_NEW_PRESET) {
  const r = await page.request.post(`${API}/api/scene/new`, { data: { name } });
  expect(r.ok()).toBeTruthy();
  await page.goto(STUDIO_URL);
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await idle(page);
  if (preset) await pickNewPreset(page, preset);
}

export async function idle(page: Page) {
  await page.evaluate(() => (window as any).__studio.idle());
}

export async function probe(page: Page): Promise<any> {
  return page.evaluate(() => (window as any).__studio.probe());
}

export async function shot(page: Page, name: string) {
  await idle(page);
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(SCREENS, `${name}.png`) });
}

/** The palette's "ArUco: single / grid / ChArUco": a tag on the selected
 *  shapes, else on a new 40 x 40 mm plate 3 mm thick (the old Add). */
export async function add(page: Page, layout: "single" | "grid" | "charuco") {
  await palette(page, { single: "ArUco: single", grid: "ArUco: grid", charuco: "ArUco: ChArUco" }[layout]);
}

/** S, type the command's name, Enter. */
export async function palette(page: Page, name: string) {
  await page.keyboard.press("s");
  const input = page.getByTestId("palette-input");
  await expect(input).toBeVisible();
  await input.fill(name);
  const first = page.locator('[cmdk-item][data-selected="true"]');
  await expect(first).toHaveAttribute("data-command", name);
  await input.press("Enter");
  await expect(page.getByTestId("palette")).toHaveCount(0);
  await page.waitForTimeout(30);
  await idle(page);
}

export const FILES = path.join(ROOT, "e2e", ".tmp", "files");

/** A fresh design file on disk (empty, or `text`), opened in the server,
 *  the app loaded on it: -> its path. */
export async function freshFile(page: Page, name: string, text?: string,
  preset: string | null = TEST_NEW_PRESET): Promise<string> {
  fs.mkdirSync(FILES, { recursive: true });
  const file = path.join(FILES, `${name}-${Date.now()}.arucostudio.json`);
  fs.writeFileSync(file, text ?? JSON.stringify({ schema: "arucostudio.scene/2", name, sketches: [], features: [] }, null, 1) + "\n", "utf-8");
  const r = await page.request.post(`${API}/api/design/open`, { data: { path: file } });
  expect(r.ok()).toBeTruthy();
  await page.goto(STUDIO_URL);
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await idle(page);
  if (preset) await pickNewPreset(page, preset);
  return file;
}

/** An example of ROOT/examples copied to a fresh file and opened. */
export async function openExample(page: Page, name: string, file: string): Promise<string> {
  return freshFile(page, name, fs.readFileSync(path.join(ROOT, "examples", file), "utf-8"));
}

export function readFile(file: string): any {
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

/** Screen point (page px) of a canvas point (mm) in the 2D view. */
export async function screenOf(page: Page, x: number, y: number): Promise<[number, number]> {
  const st = await probe(page);
  const box = (await page.locator(".canvas2d").boundingBox())!;
  const w = box.width, h = box.height;
  return [box.x + (x - st.center_mm[0]) * st.zoom + w / 2, box.y - (y - st.center_mm[1]) * st.zoom + h / 2];
}

/** The centre of an element's box on the page. */
export async function centre(page: Page, selector: string): Promise<[number, number]> {
  const b = (await page.locator(selector).first().boundingBox())!;
  return [b.x + b.width / 2, b.y + b.height / 2];
}

/** Drag from a to b in a few steps (left button). */
export async function dragPx(page: Page, a: [number, number], b: [number, number], steps = 6) {
  await page.mouse.move(a[0], a[1]);
  await page.mouse.down();
  await page.mouse.move(b[0], b[1], { steps });
  await page.mouse.up();
  await idle(page);
}

/** The scene's tags with their plans, from the server. */
export async function sceneTags(request: APIRequestContext): Promise<any[]> {
  const r = await request.get(`${API}/api/scene?plans=1`);
  return (await r.json()).tags;
}

/** Pick a value of a kit Select by its key path (the list is a popup:
 *  `.kit-select-popup[data-for=<path>]`). */
export async function choose(page: Page, path: string, value: string | number) {
  const dd = page.locator(`.kit-select[data-path="${path}"]`).first();
  await dd.locator(".kit-select-trigger").click();
  await page.locator(`.kit-select-popup[data-for="${path}"][data-open] [role="option"][data-value="${value}"]`).click();
  await expect(page.locator(`.kit-select-popup[data-for="${path}"][data-open]`)).toHaveCount(0);
  await idle(page);
}

/** The options a kit Select offers now (opens it, reads, closes it). */
export async function options(page: Page, path: string): Promise<string[]> {
  const dd = page.locator(`.kit-select[data-path="${path}"]`).first();
  await dd.locator(".kit-select-trigger").click();
  const pop = page.locator(`.kit-select-popup[data-for="${path}"][data-open]`);
  await expect(pop).toBeVisible();
  const vals = await pop.locator('[role="option"]').evaluateAll((els) => els.map((e) => e.getAttribute("data-value") || ""));
  await page.keyboard.press("Escape");
  await expect(pop).toHaveCount(0);
  return vals;
}

/** Click a kit Switch by its key path. */
export async function toggle(page: Page, path: string) {
  await page.locator(`[role="switch"][data-path="${path}"]`).first().click();
  await idle(page);
}

/** Pick one button of a kit SegmentedRow by its key path. */
export async function segment(page: Page, path: string, value: string | number) {
  await page.locator(`.kit-seg[data-path="${path}"] [data-value="${value}"]`).first().click();
  await idle(page);
}

/** Type into a number / text field by its key path, then Enter. */
export async function type(page: Page, path: string, value: string) {
  const inp = page.locator(`input[data-path="${path}"]`).first();
  await inp.click();
  await inp.fill(value);
  await inp.press("Enter");
  await idle(page);
}

export async function tab(page: Page, id: string) {
  await page.locator(`[role="tab"][data-tab="${id}"]`).click();
}

/** OpenCV (ROOT/.venv) reads a PNG: the ids it finds. */
export function detect(png: string, dictionary: string, box?: { x: number; y: number; width: number; height: number }): number[] {
  const args = ["-I", "-B", path.join(ROOT, "e2e", "detect.py"), png, dictionary];
  if (box) args.push(String(box.x), String(box.y), String(box.x + box.width), String(box.y + box.height));
  const out = execFileSync(PY, args, { encoding: "utf-8" });
  return JSON.parse(out.trim().split("\n").pop()!).ids;
}

/** The whole texts of a row's messages (data-text: the line shown is the
 *  short form, its tooltip the plan's words). */
export async function issueTexts(page: Page, path: string): Promise<string[]> {
  return page.locator(`[data-issues-for="${path}"] .issue`).evaluateAll((els) => els.map((e) => e.getAttribute("data-text") || ""));
}

/** Wait until a row's messages are exactly `want` (the plan's words). */
export async function expectIssues(page: Page, path: string, want: string[]) {
  await expect.poll(() => issueTexts(page, path)).toEqual(want);
}

/** Draw a shape by its key and typed numbers (R "40 40", C "40") right of
 *  everything on the canvas, extrude it when `height` is given (back to 2D
 *  after), and put a tag on it (A, Enter): -> the tag's name. */
export async function tagOn(page: Page, key: string, typed: string, height?: number): Promise<string> {
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.evaluate((w) => {
    const st = (window as any).__studio.store.getState();
    const xs: number[] = [];
    for (const t of st.scene.tags) xs.push(t.x_mm + Math.max(t.spec.target.w_mm, t.spec.target.h_mm) / 2);
    for (const s of (window as any).__studio.probe().shapes) xs.push(s.xf[0] + 60);
    const x = xs.length ? Math.max(...xs) + 15 + w / 2 : 0;
    st.setCamera({ cx: Math.round(x), cy: 0 });
  }, Number(typed.split(/\s+/)[0]) || 40);
  await page.keyboard.press(key);
  await page.keyboard.type(typed);
  await page.keyboard.press("Enter");
  await idle(page);
  if (height !== undefined) {
    await page.keyboard.press("e");
    await page.keyboard.type(String(height));
    await page.keyboard.press("Enter");
    await idle(page);
    await page.getByTestId("view-2d").click();
    await idle(page);
  }
  await page.keyboard.press("a");
  await page.keyboard.press("Enter");
  await idle(page);
  const sel = (await probe(page)).sel;
  expect(sel.length).toBe(1);
  return sel[0];
}

/** Select the shape under the selected tag (the inspector's link). */
export async function shapeOfTag(page: Page) {
  await page.getByTestId("aruco-shape").click();
  await idle(page);
}

/** Back to a tag from its shape's inspector. */
export async function backToTag(page: Page, name: string) {
  await page.locator(`[data-tag-link="${name}"]`).click();
  await idle(page);
}
