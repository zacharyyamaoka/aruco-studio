// N-3 (Zach, 2026-10-17): the gallery is the Studio's landing page. Golden
// examples, the inputs drawn for the user; no user-drawn canvas (the
// drawing tools only with ?draw=1). These tests run WITHOUT the dev flag:
// * the landing page lists every example of examples/gallery/gallery.json,
//   each card's thumbnail drawn from the example's real plan;
// * every example opens (a copy), plans with no error-level message, and
//   toggles 2D / 3D; its file in examples/ is never written; no console error;
// * the drawing tools are hidden (buttons, keys, palette); S still works;
// * File › Open's Examples points at the gallery; the Open dialog and the
//   File drawer still open and show files.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, ROOT, idle, probe, shot } from "./helpers";

const GALLERY = path.join(ROOT, "examples", "gallery");
const MANIFEST = JSON.parse(fs.readFileSync(path.join(GALLERY, "gallery.json"), "utf-8"));
const ITEMS: { name: string; file: string; title: string; actions?: string[]; group: string; lint?: number }[] =
  MANIFEST.groups.flatMap((g: any) => g.items.map((it: any) => ({ ...it, group: g.id })));
const DRAWING = [["R", "Rectangle"], ["C", "Circle"], ["P", "Polygon"], ["O", "Slot"], ["H", "Hole"], ["Shift+H", "Rectangular hole"]];

/** docs/STUDIO.md's "Commands and keys" table: the commands' names (read as palette.spec reads it). */
function docCommands(): string[] {
  const md = fs.readFileSync(path.join(ROOT, "docs", "STUDIO.md"), "utf-8");
  const lines = md.split("## Commands and keys")[1].split("\n");
  const start = lines.findIndex((l) => l.startsWith("| Key | Command |"));
  const out: string[] = [];
  for (const l of lines.slice(start + 2)) {
    if (!l.startsWith("|")) break;
    out.push(l.split("|").slice(1, -1).map((c) => c.trim())[1]);
  }
  return out;
}

/** Console errors and page errors, collected from the start. */
function watchErrors(page: Page): string[] {
  const out: string[] = [];
  page.on("console", (m) => { if (m.type() === "error") out.push(m.text()); });
  page.on("pageerror", (e) => out.push(String(e)));
  return out;
}

/** The landing page on a fresh, empty server scene (no flag, no hash). */
async function landing(page: Page) {
  const r = await page.request.post(`${API}/api/scene/new`, { data: { name: "e2e-gallery" } });
  expect(r.ok()).toBeTruthy();
  await page.goto("/");
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await expect(page.locator('.app[data-page="gallery"]')).toBeVisible();
  await expect(page.getByTestId("gallery")).toBeVisible();
}

/** The open scene's messages from the server: the compile's and every tag's plan. */
async function serverErrors(page: Page): Promise<{ tags: number; errors: string[] }> {
  const scene = await (await page.request.get(`${API}/api/scene?plans=1`)).json();
  const design = await (await page.request.get(`${API}/api/design?text=0`)).json();
  const errors: string[] = (design.issues ?? []).filter((i: any) => i.level === "error").map((i: any) => `${i.field}: ${i.text}`);
  for (const t of scene.tags) {
    if (!t.plan) { errors.push(`${t.name}: no plan`); continue; }
    if (!t.plan.ok) errors.push(`${t.name}: not built`);
    for (const e of t.plan.errors ?? []) errors.push(`${t.name}: ${e}`);
    for (const w of t.plan.warnings ?? []) if (w.level === "error") errors.push(`${t.name} ${w.field}: ${w.text}`);
  }
  return { tags: scene.tags.length, errors };
}

function exampleBytes(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const f of fs.readdirSync(GALLERY)) out[f] = fs.readFileSync(path.join(GALLERY, f), "utf-8");
  return out;
}

test("N-3.1 the gallery is the landing page: every example, its thumbnail from its plan", async ({ page }) => {
  const errs = watchErrors(page);
  await landing(page);
  expect(ITEMS.length).toBeGreaterThanOrEqual(15);
  await expect(page.locator(".gal-card")).toHaveCount(ITEMS.length);
  await expect(page.getByTestId("gallery")).toHaveAttribute("data-examples", String(ITEMS.length));
  for (const g of MANIFEST.groups) await expect(page.locator(`section[data-group="${g.id}"] .gal-card`)).toHaveCount(g.items.length);
  // markers first: the basics lead
  expect(await page.locator("section[data-group]").first().getAttribute("data-group")).toBe("basics");
  for (const it of ITEMS) {
    const card = page.locator(`.gal-card[data-example="${it.name}"]`);
    await expect(card).toContainText(it.title);
    const th = card.locator(`[data-thumb="${it.name}"]`);
    await expect(th, it.name).toHaveAttribute("data-state", "ready", { timeout: 30_000 });
    expect(Number(await th.getAttribute("data-tags")), it.name).toBeGreaterThan(0);
    // the page lint (2026-10-17) is red on purpose where the manifest says so (`lint`)
    await expect(th, it.name).toHaveAttribute("data-errors", String(it.lint ?? 0));
    // the thumbnail is the plan drawn: each tag's top view, black cells in it
    await expect(th.locator('g[data-tag] [data-top="black"]').first()).toBeAttached();
    expect(await th.locator("g[data-tag]").count(), it.name).toBe(Number(await th.getAttribute("data-tags")));
  }
  // the studio's keys sleep on the gallery: R draws nothing, S opens nothing
  await page.keyboard.press("s");
  await expect(page.getByTestId("palette")).toHaveCount(0);
  await shot(page, "gallery_landing");
  expect(errs).toEqual([]);
});

test("N-3.2 every example opens as a copy, plans with no error, toggles 2D / 3D", async ({ page }) => {
  test.setTimeout(300_000);
  const errs = watchErrors(page);
  const before = exampleBytes();
  await landing(page);
  await page.locator(`.gal-card[data-example="${ITEMS[0].name}"]`).click();
  for (const [i, it] of ITEMS.entries()) {
    await idle(page);
    await expect(page.locator('.app[data-page="studio"]')).toBeVisible();
    const note = page.getByTestId("example-note");
    await expect(note, it.name).toHaveAttribute("data-example", it.name);
    await expect(note).toContainText(it.title);
    await expect(page.getByTestId("example-look")).not.toBeEmpty();
    const st = await probe(page);
    // a copy in the Studio's home, never the example itself
    expect(st.design.path, it.name).toBeTruthy();
    expect(path.resolve(st.design.path).startsWith(GALLERY), it.name).toBe(false);
    expect(path.basename(st.design.path)).toBe(`${it.name}.arucostudio.json`);
    expect(st.design.state).toBe("ok");
    expect(page.url()).toContain(`#example=${it.name}`);
    // the server's plans: every tag built, no error-level message
    const got = await serverErrors(page);
    expect(got.errors.filter((e) => !/: Over the page by /.test(e)), it.name).toEqual([]);
    expect(got.errors.length, it.name).toBe(it.lint ?? 0);
    expect(got.tags, it.name).toBeGreaterThan(0);
    await expect(page.locator(".canvas2d g[data-tag]")).toHaveCount(got.tags);
    await expect(page.locator('.canvas2d g[data-tag][data-ok="0"]')).toHaveCount(0);
    // 2D -> 3D -> 2D
    await page.getByTestId("view-3d").click();
    await idle(page);
    await expect(page.locator('canvas[data-canvas3d="1"]'), it.name).toBeVisible();
    expect((await probe(page)).view).toBe("3d");
    await page.getByTestId("view-2d").click();
    await idle(page);
    await expect(page.locator(".canvas2d")).toBeVisible();
    // the next one (the note's arrow); the last stops there
    if (i < ITEMS.length - 1) await page.getByTestId("example-next").click();
    else await expect(page.getByTestId("example-next")).toBeDisabled();
  }
  expect(exampleBytes()).toEqual(before);
  expect(errs).toEqual([]);
});

test("N-3.3 a copy takes changes, Start over brings the example back, the buttons work", async ({ page }) => {
  const errs = watchErrors(page);
  const before = exampleBytes();
  await landing(page);
  await page.locator('.gal-card[data-example="basics_single"]').click();
  await idle(page);
  // the first tag is selected: its Marker size, typed, re-plans the copy
  expect((await probe(page)).sel).toEqual(["tag"]);
  const inp = page.locator('input[data-path="numbers.size"]').first();
  await inp.click();
  await inp.fill("40");
  await inp.press("Enter");
  await idle(page);
  const after = (await probe(page)).file;
  expect(after.features[1].numbers.size).toBe(40);
  await expect(page.locator('.canvas2d g[data-tag="tag"]')).toHaveAttribute("data-ok", "1");
  // Start over: a fresh copy, the example's number again
  await page.getByTestId("example-reset").click();
  await idle(page);
  expect((await probe(page)).file.features[1].numbers.size).toBe(30);
  // the note's buttons: 3D, the sticker sheet, Send, Renumber
  await page.getByTestId("example-act-3d").click();
  await idle(page);
  await expect(page.locator('canvas[data-canvas3d="1"]')).toBeVisible();
  await page.getByTestId("example-gallery").click();
  await expect(page.getByTestId("gallery")).toBeVisible();
  await expect(page.getByTestId("gallery-back")).toBeVisible();
  await page.locator('.gal-card[data-example="sheet_tight"]').click();
  await idle(page);
  await page.getByTestId("example-act-sheet").click();
  await expect(page.getByTestId("dialog-sheet")).toBeVisible();
  await expect(page.getByTestId("sheet-preview")).toHaveAttribute("data-mode", "tight");
  await expect(page.getByTestId("sheet-stats")).toHaveAttribute("data-stickers", "5");
  await page.getByTestId("sheet-close").click();
  await page.getByTestId("example-gallery").click();
  await page.locator('.gal-card[data-example="ids"]').click();
  await idle(page);
  // made without ids: every 4X4 tag starts at #0 (#0-5 for the boards)
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "6");
  await page.getByTestId("example-act-ids").click();
  await idle(page);
  await expect(page.getByTestId("dup-count")).toHaveAttribute("data-dups", "0");
  const ids = (await probe(page)).tags.filter((t: any) => t.name !== "other").flatMap((t: any) => t.ids);
  expect(new Set(ids).size).toBe(ids.length);                       // one numbering for 3D and 2D
  expect((await probe(page)).tags.find((t: any) => t.name === "other").ids).toEqual([0]);   // 6X6: its own family
  await page.getByTestId("example-gallery").click();
  await page.locator('.gal-card[data-example="send"]').click();
  await idle(page);
  await page.evaluate(() => { (window as any).__studio.sendOpen = false; });
  await page.getByTestId("example-act-send").click();
  await expect(page.getByTestId("dialog-send")).toBeVisible();
  await page.getByTestId("send-close").click();
  // a reload comes back to the example and its note
  await page.reload();
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await expect(page.getByTestId("example-note")).toHaveAttribute("data-example", "send");
  expect(exampleBytes()).toEqual(before);
  expect(errs).toEqual([]);
});

test("N-3.4 the drawing tools are hidden without ?draw=1; S still works", async ({ page }) => {
  const errs = watchErrors(page);
  await landing(page);
  await page.locator('.gal-card[data-example="faces"]').click();
  await idle(page);
  const tools = page.locator('.bottombar .kit-tool[data-testid^="tool-"]');
  expect(await tools.evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")))).toEqual(
    ["tool-select", "tool-extrude", "tool-aruco", "tool-search"]);
  for (const id of ["rect", "circle", "polygon", "slot", "hole", "rhole"]) await expect(page.getByTestId(`tool-${id}`)).toHaveCount(0);
  await page.locator(".canvas2d").click({ position: { x: 40, y: 600 } });
  for (const k of ["r", "c", "p", "o", "h", "Shift+H"]) {
    await page.keyboard.press(k);
    expect((await probe(page)).tool, k).toBe("select");
  }
  // the palette: every command of docs/STUDIO.md's table but the drawing tools
  await page.keyboard.press("s");
  await expect(page.getByTestId("palette")).toBeVisible();
  const names = await page.locator("[cmdk-item]").evaluateAll((els) => els.map((e) => e.getAttribute("data-command") ?? ""));
  for (const [, n] of DRAWING) expect(names).not.toContain(n);
  for (const n of ["Select / move", "Extrude", "ArUco Extrude", "Gallery", "Zoom to fit", "Verify", "Renumber all", "Sticker sheet…"]) expect(names).toContain(n);
  const doc = docCommands().filter((n) => !DRAWING.some(([, d]) => d === n));
  expect([...names].sort()).toEqual([...doc].sort());
  await page.getByTestId("palette-input").fill("quiet zones");
  await expect(page.locator('[cmdk-item][data-selected="true"]')).toHaveAttribute("data-command", "Quiet zones");
  const quiet = (await page.evaluate(() => (window as any).__studio.store.getState().show.quiet)) as boolean;
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("palette")).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).__studio.store.getState().show.quiet)).toBe(!quiet);
  // S, "Gallery", Enter: back to the landing page
  await page.keyboard.press("s");
  await page.getByTestId("palette-input").fill("Gallery");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("gallery")).toBeVisible();
  expect(errs).toEqual([]);
});

test("N-3.4b ?draw=1 brings the drawing tools back (and starts on the canvas)", async ({ page }) => {
  const r = await page.request.post(`${API}/api/scene/new`, { data: { name: "e2e-gallery-draw" } });
  expect(r.ok()).toBeTruthy();
  await page.goto("/?draw=1");
  await expect(page.locator('.app[data-ready="1"]')).toBeVisible();
  await expect(page.locator('.app[data-page="studio"]')).toBeVisible();
  await expect(page.locator('.bottombar .kit-tool[data-testid^="tool-"]')).toHaveCount(10);
  await page.keyboard.press("r");
  expect((await probe(page)).tool).toBe("rect");
  await page.keyboard.press("Escape");
});

test("N-3.5 File › Open › Examples points at the gallery; Open and the File drawer still open files", async ({ page }) => {
  const errs = watchErrors(page);
  await landing(page);
  await page.locator('.gal-card[data-example="two_ways"]').click();
  await idle(page);
  // the File drawer shows the copy's text
  await page.getByTestId("sb-file").click();
  await expect(page.getByTestId("file-drawer")).toBeVisible();
  await expect(page.getByTestId("file-text")).toContainText("One marker, made two ways");
  await page.getByTestId("sb-file").click();
  // File › Gallery…
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-gallery").click();
  await expect(page.getByTestId("gallery")).toBeVisible();
  await page.getByTestId("gallery-back").click();
  await expect(page.getByTestId("example-note")).toHaveAttribute("data-example", "two_ways");
  // File › Open…: the gallery first among the examples
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-open").click();
  const dlg = page.getByTestId("dialog-open");
  await expect(dlg).toBeVisible();
  await expect(dlg.locator('[data-testid="open-examples"] > *').first()).toHaveAttribute("data-testid", "open-gallery");
  await dlg.getByTestId("open-gallery").click();
  await expect(page.getByTestId("dialog-open")).toHaveCount(0);
  await expect(page.getByTestId("gallery")).toBeVisible();
  // the three older examples are not listed any more (2026-10-17, Zach: the
  // gallery covers them); Open still opens a file by its path, and the note goes
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-open").click();
  for (const ex of ["forearm", "plate_charuco", "sticker_sheet"]) {
    await expect(page.getByTestId("dialog-open").locator(`[data-example="${ex}"]`)).toHaveCount(0);
  }
  const dir = path.join(ROOT, "e2e", ".tmp", "files");
  fs.mkdirSync(dir, { recursive: true });
  const copy = path.join(dir, "plate_charuco.arucostudio.json");
  fs.copyFileSync(path.join(ROOT, "examples", "plate_charuco.arucostudio.json"), copy);
  await page.getByTestId("dialog-path").fill(copy);
  await page.getByTestId("dialog-ok").click();
  await idle(page);
  await expect(page.locator('.app[data-page="studio"]')).toBeVisible();
  await expect(page.getByTestId("example-note")).toHaveCount(0);
  expect(path.basename((await probe(page)).design.path)).toMatch(/^plate_charuco(-\d+)?\.arucostudio\.json$/);
  await expect(page.locator(".canvas2d g[data-tag]")).toHaveCount(1);
  // and the recent list opens the gallery's copy again, as a plain file
  await page.getByTestId("menu-file").click();
  await page.getByTestId("file-open").click();
  const recent = page.getByTestId("dialog-open").locator('[data-recent$="two_ways.arucostudio.json"]');
  await expect(recent).toHaveCount(1);
  await recent.click();
  await idle(page);
  expect(path.basename((await probe(page)).design.path)).toBe("two_ways.arucostudio.json");
  await expect(page.locator(".canvas2d g[data-tag]")).toHaveCount(2);
  expect(errs).toEqual([]);
});
