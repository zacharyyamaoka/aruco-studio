// Review finding #2 (2026-10-21): every document replacement goes through
// the SDK's document transition (hosted/hosted.ts leaveFile), untitled
// documents included. Untitled document A's first autosave is creating its
// file (the create held back) when an example (B) is opened: B must never get
// A's cloud file, nor autosave into it.
// The cloud is faked in the page (page.route): every request to the built-in
// Simple Hosted Files is answered here and none leaves the browser; the
// bearer is a fake one only this fake server reads.
import { expect, test, type Page, type Route } from "@playwright/test";
import { coreReady, dragWorld, loadExample, openStudio, state } from "./helpers";

const SERVER = "https://simple-hosted-files.zach-yamaoka.workers.dev";
const CREATE_HOLD_MS = 4000;

/** a write the fake cloud got: where, and whether its bytes are B (the sticker sheet: its "sheet" rectangle) */
interface Write { method: string; path: string; isB: boolean }

function fakeCloud(page: Page): { writes: Write[]; creates: () => number } {
  const writes: Write[] = [];
  const files = new Map<string, { id: string; name: string; version: number }>();
  let n = 0;
  const meta = (f: { id: string; name: string; version: number }) => ({
    id: f.id, app: "aruco-studio", name: f.name, contentType: "application/json", version: f.version, size: 1, sha256: "x",
    createdAt: "2026-10-21T00:00:00Z", updatedAt: new Date().toISOString(), trashedAt: null, purgeAt: null, locked: false,
  });
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify(body) });
  void page.route(`${SERVER}/**`, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method();
    if (method === "OPTIONS") {
      return route.fulfill({ status: 204, headers: { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" } });
    }
    const isB = (): boolean => { try { return JSON.parse(req.postData() ?? "").shapes.some((x: { id: string }) => x.id === "sheet"); } catch { return false; } };
    if (url.pathname === "/v1/me") {
      return json(route, {
        user: { id: "u-e2e", email: "e2e@example.test", name: null, image: null }, plan: "free",
        limits: { filesPerApp: 10, maxFileBytes: 1e7, totalBytes: 1e8 }, usage: { totalBytes: 0, apps: {} },
        app: { id: "aruco-studio", name: "ArUco Studio", extension: ".arucostudio-web.json", files: files.size, limit: 10, remaining: 10 - files.size, autosave: "all" },
        billing: { provider: "dev", priceLabel: "", canUpgrade: false, canManage: false }, accountUrl: "", deletionScheduledAt: null,
      });
    }
    if (url.pathname === "/v1/files" && method === "GET") return json(route, { files: [...files.values()].map(meta) });
    if (url.pathname === "/v1/files" && method === "POST") {
      writes.push({ method, path: url.pathname, isB: isB() });
      const f = { id: `file-${++n}`, name: url.searchParams.get("name") ?? "Untitled", version: 1 };
      // the first file's creation is slow: the window the bug lived in
      if (n === 1) await new Promise((r) => setTimeout(r, CREATE_HOLD_MS));
      files.set(f.id, f);
      return json(route, meta(f), 201);
    }
    const m = /^\/v1\/files\/([^/]+)(\/content)?$/.exec(url.pathname);
    const f = m ? files.get(m[1]) : undefined;
    if (f && m![2] && method === "PUT") {
      writes.push({ method, path: url.pathname, isB: isB() });
      f.version += 1;
      return json(route, meta(f));
    }
    if (f && method === "GET" && !m![2]) return json(route, meta(f));
    if (f && method === "PATCH") { f.name = JSON.parse(req.postData() ?? "{}").name ?? f.name; return json(route, meta(f)); }
    return json(route, { error: { code: "not_found", message: `fake cloud: no ${method} ${url.pathname}` } }, 404);
  });
  return { writes, creates: () => n };
}

test("an example opened while the untitled document's first file is being created never gets that file", async ({ page }) => {
  test.setTimeout(120_000);
  const cloud = fakeCloud(page);
  await page.addInitScript(() => { try { localStorage.setItem("shf:aruco-studio:token", "fake-e2e-bearer"); } catch { /* blocked */ } });
  await openStudio(page);
  await coreReady(page);
  await expect(page.getByTestId("shf-status")).toBeVisible();

  // A: an edit; its autosave starts creating A's file (held back)
  await page.keyboard.press("r");
  await dragWorld(page, [10, 10], [40, 30]);
  await expect.poll(() => cloud.creates(), { timeout: 15_000, message: "A's first autosave creates its file" }).toBe(1);

  // B: an example, while A's create is still out
  await loadExample(page, "sticker-sheet");
  await expect.poll(async () => (await state(page)).doc.name).toMatch(/Sticker sheet/);

  // A's create lands; then B is edited and autosaves
  await page.waitForTimeout(CREATE_HOLD_MS + 500);
  await page.keyboard.press("Escape");
  await page.keyboard.press("r");
  await dragWorld(page, [250, 10], [270, 30]);
  await expect.poll(() => cloud.writes.filter((w) => w.isB).length, { timeout: 20_000, message: "B autosaves" }).toBeGreaterThan(0);

  // B's bytes went into a file of its own, never A's (file-1); A's file holds only A
  expect(cloud.writes.filter((w) => w.isB && w.path.startsWith("/v1/files/file-1/")), "B written into A's file").toEqual([]);
  expect(cloud.writes.find((w) => w.isB)).toMatchObject({ method: "POST", path: "/v1/files" });
  // and B is not named after A's file (oneName follows the file B must not have)
  expect((await state(page)).doc.name).toMatch(/Sticker sheet/);
});
