// Shared steps of the Studio's e2e tests. Every bar reads the DOM, the
// store (window.__studio) or the API, never a picture; the screenshots in
// reports/screens/ are for people.
import { expect, type Page, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

export const ROOT = path.resolve(__dirname, "..", "..");
export const SCREENS = path.join(ROOT, "reports", "screens");
export const API = "http://127.0.0.1:5360";
const PY = path.join(ROOT, ".venv", "Scripts", "python.exe");

/** A fresh scene on the server, the app loaded on it. */
export async function fresh(page: Page, name = "e2e") {
  const r = await page.request.post(`${API}/api/scene/new`, { data: { name } });
  expect(r.ok()).toBeTruthy();
  await page.goto("/");
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await idle(page);
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

export async function add(page: Page, layout: "single" | "grid" | "charuco") {
  await page.getByTestId(`add-${layout}`).click();
  await idle(page);
}

/** The scene's tags with their plans, from the server. */
export async function sceneTags(request: APIRequestContext): Promise<any[]> {
  const r = await request.get(`${API}/api/scene?plans=1`);
  return (await r.json()).tags;
}

/** Pick a value of an inspector dropdown by its key path. */
export async function choose(page: Page, path: string, value: string | number) {
  const dd = page.locator(`.dd[data-path="${path}"]`).first();
  await dd.locator(".dd-btn").click();
  await dd.locator(`.dd-opt[data-value="${value}"]`).click();
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
  await page.locator(`.tab[data-tab="${id}"]`).click();
}

/** OpenCV (ROOT/.venv) reads a PNG: the ids it finds. */
export function detect(png: string, dictionary: string, box?: { x: number; y: number; width: number; height: number }): number[] {
  const args = ["-I", "-B", path.join(ROOT, "e2e", "detect.py"), png, dictionary];
  if (box) args.push(String(box.x), String(box.y), String(box.x + box.width), String(box.y + box.height));
  const out = execFileSync(PY, args, { encoding: "utf-8" });
  return JSON.parse(out.trim().split("\n").pop()!).ids;
}
