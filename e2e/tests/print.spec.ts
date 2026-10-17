// M6c (folded into M8b2): Print the sticker sheet from the Studio at 100 %.
// The OS print dialog cannot be driven, so the test sets
// window.__studio.printHook: Print hands it the PDF's bytes instead of the
// hidden iframe's print(). M6c.5 (a ruler on Zach's printed page) is by hand.
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { API, ROOT, add, freshFile, idle, openExample, shot } from "./helpers";

const PY = path.join(ROOT, ".venv", "Scripts", "python.exe");
const TMP = path.join(ROOT, "e2e", ".tmp");
const sha = (b: Buffer | Uint8Array) => crypto.createHash("sha256").update(b).digest("hex");

test("M6c.1-2 Print: the hook gets the print route's bytes once; the 100 mm bar is 100 mm", async ({ page }) => {
  await openExample(page, "e2e-print", "sticker_sheet.arucostudio.json");
  await page.evaluate(() => {
    (window as any).__printed = [];
    (window as any).__studio.printHook = (bytes: Uint8Array, url: string) => {
      let s = "";
      for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
      (window as any).__printed.push({ b64: btoa(s), url });
      return true;
    };
  });
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-print").click();
  await idle(page);
  const got = await page.evaluate(() => (window as any).__printed);
  expect(got.length).toBe(1);                                                             // called once
  const bytes = Buffer.from(got[0].b64, "base64");
  expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
  expect(got[0].url).toContain("/api/scene/print.pdf?");
  // the same bytes as the print route and as the bundle's sheet.pdf
  const q = new URL(got[0].url, "http://x").search;
  const route = Buffer.from(await (await page.request.get(`${API}/api/scene/print.pdf${q}`)).body());
  expect(sha(bytes)).toBe(sha(route));
  const sheet = await (await page.request.get(`${API}/api/scene/sheet.json${q}`)).json();
  // M6c.2: pdfium at 600 dpi, the bars measured on their rows
  fs.mkdirSync(TMP, { recursive: true });
  const pdfPath = path.join(TMP, "m8b2_print.pdf");
  const rulerPath = path.join(TMP, "m8b2_ruler.json");
  fs.writeFileSync(pdfPath, bytes);
  fs.writeFileSync(rulerPath, JSON.stringify(sheet.ruler));
  const out = JSON.parse(execFileSync(PY, ["-I", "-B", path.join(ROOT, "e2e", "bars.py"), pdfPath, rulerPath], { encoding: "utf-8" }).trim().split("\n").pop()!);
  expect(out.pages.length).toBeGreaterThan(0);
  for (const p of out.pages) {
    expect(Math.abs(p.mm_bar - 100.0)).toBeLessThanOrEqual(0.1);
    expect(Math.abs(p.in_bar - 101.6)).toBeLessThanOrEqual(0.1);
  }
  fs.writeFileSync(path.join(TMP, "m8b2_numbers_print.json"), JSON.stringify({ bytes: bytes.length, sha256: sha(bytes), bars: out.pages }, null, 1));
  await shot(page, "m8b2_print_hooked");
  // and the bundle's sheet.pdf (Export) is the same bytes the same day
  const bundle = await (await page.request.post(`${API}/api/scene/export/print`, { data: { inline: true, page: "letter", landscape: false, mode: "tight", margin_mm: 10 } })).json();
  const fromBundle = Buffer.from(bundle.inline["sheet.pdf"], "base64");
  const printTight = Buffer.from(await (await page.request.get(`${API}/api/scene/print.pdf?page=letter&landscape=false&mode=tight&margin_mm=10`)).body());
  expect(sha(fromBundle)).toBe(sha(printTight));
});

test("M6c.3 the fallback: a browser that cannot print the PDF gets Open the PDF and the Ctrl+P note", async ({ page, context }) => {
  await openExample(page, "e2e-print-fallback", "sticker_sheet.arucostudio.json");
  await page.evaluate(() => { (window as any).__studio.printHook = () => false; });
  await page.getByTestId("menu-export").click();
  await page.getByTestId("export-print").click();
  await idle(page);
  const dlg = page.getByTestId("dialog-print");
  await expect(dlg).toBeVisible();
  await expect(page.getByTestId("print-note")).toContainText("Ctrl");
  await expect(page.getByTestId("print-note")).toContainText("Actual size (100 %)");
  await expect(page.getByTestId("print-open")).toHaveText(/Open the PDF/);
  await shot(page, "m8b2_print_fallback");
  const [tabPage] = await Promise.all([context.waitForEvent("page"), page.getByTestId("print-open").click()]);
  await tabPage.waitForLoadState("domcontentloaded").catch(() => undefined);
  expect(tabPage.url()).toContain("/api/scene/print.pdf?");
  await tabPage.close();
});

test("M6c.4 a scene with no sticker: Print is off, and says why", async ({ page }) => {
  await freshFile(page, "e2e-print-none");
  await add(page, "single");                                                              // a 3D tag only
  await page.getByTestId("menu-export").click();
  const item = page.getByTestId("export-print");
  await expect(item).toHaveAttribute("data-disabled", "");
  await expect(item).toContainText("no stickers in this scene (3D tags print on beds)");
  await expect(page.getByTestId("export-sheet")).toHaveAttribute("data-disabled", "");
  await shot(page, "m8b2_print_disabled");
  await page.keyboard.press("Escape");
});
