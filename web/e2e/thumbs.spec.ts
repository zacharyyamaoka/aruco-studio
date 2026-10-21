// Home's cards draw every cloud file from its own bytes (Zach, 2026-10-21:
// "Make sure thumbnail previews are showing" -- only the open file had a
// picture; every other card was the file icon, a copy included). Simple Hosted
// Files' preview contract: "The server stores your bytes, so only your app can
// draw them" (its skill, react-shadcn.md "Home: the preview contract").
// The cloud is answered here (context.route: the new tab Duplicate opens gets
// it too), a small faithful server: real sha256 of the bytes, versions that
// move on a write, Duplicate's copy with the same bytes. hosted.spec.ts drives
// the real one (E2E_HOSTED_SERVER).
// Measured, not assumed: each card's picture is an <svg> with its shapes, one
// black path per marker with an area (getBBox), and no file icon; the reads of
// each file's bytes are counted.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { expect, test, type BrowserContext, type Locator, type Page } from "@playwright/test";
import { coreReady, dragWorld, idle, loadExample, openStudio, state } from "./helpers";

const fixture = (name: string) => fs.readFileSync(path.join(import.meta.dirname, "fixtures", name), "utf8");
/** the file the Studio saves: serialise() in model/doc.ts */
const fileText = (doc: unknown) => JSON.stringify(doc, null, 2);
const sha = (text: string) => crypto.createHash("sha256").update(text).digest("hex");

interface CloudFile { id: string; name: string; text: string; version: number; updatedAt: number }

/** A signed-in account whose files live here: GET /v1/me, the list, a file,
 *  its bytes; PUT (a save: version + 1), PATCH (rename), POST duplicate. */
async function cloud(context: BrowserContext) {
  const files = new Map<string, CloudFile>();
  /** every read of a file's bytes, as "<id>@<version>" */
  const reads: string[] = [];
  /** every save, as "<id>@<version it made>" */
  const writes: string[] = [];
  let made = 0;
  const meta = (f: CloudFile) => ({
    id: f.id, app: "aruco-studio", name: f.name, contentType: "application/json", version: f.version, size: Buffer.byteLength(f.text), sha256: sha(f.text),
    createdAt: new Date(f.updatedAt - 3_600_000).toISOString(), updatedAt: new Date(f.updatedAt).toISOString(), trashedAt: null, purgeAt: null, locked: false,
  });
  const add = (id: string, name: string, text: string, minutesAgo = 0) => {
    files.set(id, { id, name, text, version: 1, updatedAt: Date.now() - minutesAgo * 60_000 });
  };
  await context.addInitScript(() => localStorage.setItem("shf:aruco-studio:token", "e2e-token"));
  await context.route(/\/v1\//, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const cors = { "access-control-allow-origin": req.headers()["origin"] ?? "*", "access-control-expose-headers": "ETag, X-Version", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body), headers: cors });
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers: cors });
    if (url.pathname === "/v1/me") {
      return json({
        user: { id: "u1", email: "zach@example.com", name: "Zach", image: null }, plan: "free",
        limits: { filesPerApp: 100, maxFileBytes: 1e6, totalBytes: 1e8 }, usage: { totalBytes: 2000, apps: { "aruco-studio": { files: files.size, trashed: 0 } } },
        app: { id: "aruco-studio", name: "ArUco Studio", extension: ".arucostudio-web.json", files: files.size, limit: 100, remaining: 100 - files.size },
        billing: { provider: "dev", priceLabel: "$4/month", canUpgrade: false, canManage: false }, accountUrl: "", deletionScheduledAt: null,
      });
    }
    if (url.pathname === "/v1/files" && req.method() === "GET") {
      return json({ files: url.searchParams.get("trashed") ? [] : [...files.values()].sort((a, b) => b.updatedAt - a.updatedAt).map(meta) });
    }
    const m = url.pathname.match(/^\/v1\/files\/([^/]+)(\/content|\/duplicate)?$/);
    const f = m ? files.get(m[1]) : undefined;
    if (!m || !f) return json({ error: { code: "not_found", message: "Not found" } }, 404);
    if (m[2] === "/content" && req.method() === "GET") {
      reads.push(`${f.id}@${f.version}`);
      return route.fulfill({ status: 200, contentType: "application/json", body: f.text, headers: { ...cors, etag: `"${f.version}"`, "x-version": String(f.version) } });
    }
    if (m[2] === "/content" && req.method() === "PUT") {
      const text = req.postData() ?? "";
      if (text === f.text) return json({ ...meta(f), unchanged: true });
      f.text = text;
      f.version += 1;
      f.updatedAt = Date.now();
      writes.push(`${f.id}@${f.version}`);
      return json(meta(f));
    }
    if (m[2] === "/duplicate") {
      const body = JSON.parse(req.postData() || "{}") as { name?: string };
      const copy: CloudFile = { id: `f-copy-${++made}`, name: body.name ?? `${f.name} (copy)`, text: f.text, version: 1, updatedAt: Date.now() };
      files.set(copy.id, copy);
      return json(meta(copy), 201);
    }
    if (req.method() === "PATCH") {
      f.name = (JSON.parse(req.postData() || "{}") as { name: string }).name;
      return json(meta(f));
    }
    return json(meta(f));
  });
  return { files, reads, writes, add };
}

/** Back to files (the main menu's first item). */
async function home(page: Page): Promise<Locator> {
  await page.getByTestId("menu-main").click();
  await page.getByTestId("cmd-home").click();
  const h = page.getByTestId("home");
  await expect(h).toBeVisible();
  await expect(h).toHaveAttribute("data-signed-in", "1");
  return h;
}

const card = (h: Locator, id: string) => h.locator(`[data-testid=home-file][data-id="${id}"]`);

/** A card's picture, measured: no file icon, an <svg> with its shapes (the
 *  number of outlines in the fill path), its markers (black paths with an
 *  area) -- or the empty canvas. */
async function picture(c: Locator) {
  return c.evaluate((el) => {
    const svg = el.querySelector(".home-pic svg.ex-thumb") as SVGSVGElement | null;
    const fill = svg?.querySelector(".ex-fill") as SVGPathElement | null;
    const blacks = [...(svg?.querySelectorAll("[data-thumb-black]") ?? [])] as SVGPathElement[];
    return {
      icon: !!el.querySelector(".home-file-ic"),
      svg: !!svg,
      empty: svg?.getAttribute("data-thumb") === "empty",
      outlines: (fill?.getAttribute("d")?.match(/M/g) ?? []).length,
      marks: blacks.length,
      inked: blacks.filter((b) => { const r = b.getBBox(); return r.width * r.height > 0; }).length,
    };
  });
}

/** The card draws `outlines` shapes and `marks` markers, every one inked. */
async function drawn(h: Locator, id: string, outlines: number, marks: number): Promise<void> {
  await expect.poll(() => picture(card(h, id)), { timeout: 60_000, message: `${id}: its shapes and markers` })
    .toEqual({ icon: false, svg: true, empty: false, outlines, marks, inked: marks });
}

test.describe("Home's thumbnails", () => {
  // the state each test ends in (on a failure: the Home it failed on)
  test.afterEach(async ({ page }, info) => {
    await page.screenshot({ path: info.outputPath("end.png") }).catch(() => {});
  });

  test("a · every file draws its own markers from its bytes: files from before thumbnails (v1, v3), a copy, a face, an empty one; a broken one is the icon; a reload draws them from this browser", async ({ page, context }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const c = await cloud(context);
    await openStudio(page);
    await coreReady(page);
    // two documents the Studio writes today: the face it opens on, and the sticker sheet (12 markers)
    const plate = fileText((await state(page)).doc);
    await loadExample(page, "sticker-sheet");
    await idle(page);
    const stickers = fileText({ ...(await state(page)).doc, name: "Stickers" });
    // files saved before any picture was kept: a version 3 file, a version 1 file
    c.add("f-a4", "Two on A4", fixture("v3-a4.arucostudio-web.json"), 5);
    c.add("f-old", "Old plate", fixture("v1-plate.arucostudio-web.json"), 10);
    c.add("f-stickers", "Stickers", stickers, 15);
    // a copy (Duplicate): the same bytes under another file
    c.add("f-copy", "Copy of Stickers", stickers, 1);
    c.add("f-plate", "Plate", plate, 20);
    c.add("f-empty", "sss", fileText({ format: "arucostudio-web", version: 4, name: "sss", shapes: [], dims: [], features: [], id_ledger: {}, default_preset: null }), 25);
    c.add("f-broken", "ssasdad", "{ this is not a studio file", 30);

    const h = await home(page);
    await expect(h.getByTestId("home-file")).toHaveCount(7);
    await drawn(h, "f-a4", 3, 2);
    await drawn(h, "f-old", 4, 1);
    await drawn(h, "f-stickers", JSON.parse(stickers).shapes.length, 12);
    await drawn(h, "f-copy", JSON.parse(stickers).shapes.length, 12);
    await drawn(h, "f-plate", JSON.parse(plate).shapes.length, 0);
    // empty: a calm empty canvas, not the icon
    await expect.poll(() => picture(card(h, "f-empty"))).toMatchObject({ icon: false, svg: true, empty: true, marks: 0 });
    // broken: the icon, and nothing thrown
    await expect.poll(() => picture(card(h, "f-broken"))).toMatchObject({ icon: true, svg: false });
    expect(errors).toEqual([]);
    await page.screenshot({ path: test.info().outputPath("home-thumbs.png") });
    // read once per bytes: the copy shares the sticker sheet's read
    expect(c.reads.filter((r) => r.startsWith("f-stickers@") || r.startsWith("f-copy@"))).toHaveLength(1);
    expect(c.reads.filter((r) => r.startsWith("f-a4@"))).toHaveLength(1);

    // a reload straight on Home: the pictures are this browser's, no file is read again (the broken one is)
    const before = c.reads.length;
    await page.reload();
    const again = page.getByTestId("home");
    await expect(again).toBeVisible();
    await drawn(again, "f-a4", 3, 2);
    await drawn(again, "f-old", 4, 1);
    await drawn(again, "f-copy", JSON.parse(stickers).shapes.length, 12);
    await drawn(again, "f-stickers", JSON.parse(stickers).shapes.length, 12);
    await drawn(again, "f-plate", JSON.parse(plate).shapes.length, 0);
    await expect.poll(() => picture(card(again, "f-empty"))).toMatchObject({ icon: false, empty: true });
    await expect.poll(() => picture(card(again, "f-broken"))).toMatchObject({ icon: true });
    expect(c.reads.slice(before).filter((r) => !r.startsWith("f-broken@"))).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("b · a save keeps its picture: an edit autosaves, and Home draws the saved file without reading it back", async ({ page, context }) => {
    const c = await cloud(context);
    c.add("f-a4", "Two on A4", fixture("v3-a4.arucostudio-web.json"), 5);
    c.add("f-old", "Old plate", fixture("v1-plate.arucostudio-web.json"), 10);
    await openStudio(page);
    await coreReady(page);
    let h = await home(page);
    await card(h, "f-a4").click();
    await expect(page.getByTestId("home")).toHaveCount(0);
    await expect(page.getByTestId("doc-name")).toHaveText("Two on A4");
    await idle(page);
    // an edit: one more rectangle on the plate; autosave writes it
    await page.keyboard.press("r");
    await dragWorld(page, [52, 62], [68, 74]);
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await state(page)).doc.shapes.length).toBe(4);
    await idle(page);
    await expect.poll(() => (JSON.parse(c.files.get("f-a4")!.text) as { shapes: unknown[] }).shapes.length, { timeout: 15_000 }).toBe(4);
    await expect(page.getByTestId("shf-status")).toHaveAttribute("data-kind", "saved", { timeout: 15_000 });
    expect(c.writes.length, "autosave wrote it").toBeGreaterThan(0);
    // another file in the editor: "Two on A4" is a card like any other now
    h = await home(page);
    await card(h, "f-old").click();
    await expect(page.getByTestId("doc-name")).toHaveText("Old plate");
    h = await home(page);
    await drawn(h, "f-a4", 4, 2);
    // drawn from what the saves kept: the bytes it holds now were never read back
    const now = c.files.get("f-a4")!;
    expect(now.version).toBeGreaterThan(1);
    expect(c.reads).not.toContain(`f-a4@${now.version}`);
    await page.screenshot({ path: test.info().outputPath("home-after-save.png") });
  });

  test("c · Duplicate opens \"Copy of <name>\" in a new tab, and that tab opens the copy (not an empty editor); this tab keeps the original", async ({ page, context }) => {
    const c = await cloud(context);
    c.add("f-a4", "Two on A4", fixture("v3-a4.arucostudio-web.json"), 5);
    await openStudio(page);
    await coreReady(page);
    const h = await home(page);
    await card(h, "f-a4").click();
    await expect(page.getByTestId("doc-name")).toHaveText("Two on A4");
    const original = (await state(page)).doc;
    await page.getByTestId("menu-doc").click();
    const [tab] = await Promise.all([context.waitForEvent("page"), page.getByTestId("doc-menu").getByTestId("shf-action-duplicate").click()]);
    await tab.waitForLoadState();
    await expect(tab.getByTestId("app")).toBeVisible();
    // the copy, in the new tab: its name, its drawing
    await expect(tab.getByTestId("doc-name")).toHaveText("Copy of Two on A4", { timeout: 30_000 });
    const copy = [...c.files.values()].find((f) => f.name === "Copy of Two on A4")!;
    expect(copy, "the server made the copy").toBeTruthy();
    expect(copy.text).toBe(c.files.get("f-a4")!.text);
    await expect.poll(async () => (await state(tab)).doc.shapes).toEqual(original.shapes);
    expect((await state(tab)).doc.features.map((f: { id: string }) => f.id)).toEqual(original.features.map((f: { id: string }) => f.id));
    // the address no longer names the file (a reload or New does not reopen it)
    expect(new URL(tab.url()).searchParams.get("file")).toBeNull();
    // this tab: still the original
    await expect(page.getByTestId("doc-name")).toHaveText("Two on A4");
    await tab.close();
  });
});
