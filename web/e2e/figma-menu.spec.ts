// Figma UI3's chrome (Zach, 2026-10-20 night: "Figma doesn't have the file
// edit export etc there... it's in a drop down when you press the icon, and
// there is also the button there when you click the icon to go home"; "the 2D
// and 3D are clipping"). help.figma.com's "Explore the navigation bar": the
// Figma menu opens Back to files, then File ›, Edit ›, View › … The main menu
// behind the logo, no inline File / Edit / Export, Home ("Back to files") with
// the browser's Back, and an audit of every chrome control at 1184, 1280, 1440
// and 390 wide, both themes, all four skins: no content overflows its box, no
// control is clipped by a box around it, no two controls meet.
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, openMenu, openStudio, state } from "./helpers";

const SUBMENUS: [string, string, string[]][] = [
  ["file", "File", ["cmd-new", "cmd-open-cloud", "cmd-open", "cmd-save-cloud", "cmd-save", "cmd-examples"]],
  ["edit", "Edit", ["cmd-undo", "cmd-redo", "cmd-reid", "cmd-presets"]],
  ["export", "Export", ["cmd-print", "cmd-svg", "cmd-pdf"]],
  ["view", "View", ["cmd-view-2d", "cmd-view-3d", "cmd-fit"]],
  ["prefs", "Preferences", ["theme-light", "theme-dark", "skin-studio", "skin-unstyled", "skin-fusion", "skin-onshape"]],
  ["help", "Help", ["help-menu", "github-menu", "brand"]],
];

/** The chrome: its boxes, and every control in them. */
const CHROME = ["doc-pill", "actions-pill", "toolbar", "corner"];
const CONTROLS = ["menu-main", "doc-name", "menu-doc", "menu-cad", "act-verify", "act-print",
  "tool-select", "tool-rect", "tool-circle", "tool-dim", "tool-extrude", "tool-fit", "view-toggle", "help", "github"];

/** Every element in the chrome whose content runs out of its box, or that a
 *  box around it (overflow not visible) cuts; and every pair of chrome boxes
 *  or controls that meet. Measured, never assumed. */
async function audit(page: Page): Promise<{ overflow: string[]; clipped: string[]; overlaps: string[]; shown: string[] }> {
  return page.evaluate(([chrome, controls]) => {
    const name = (e: Element) => e.getAttribute("data-testid") ?? `${e.tagName.toLowerCase()}.${[...e.classList].join(".")}`;
    const seen = (e: Element) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== "hidden"; };
    const overflow: string[] = [], clipped: string[] = [];
    for (const id of chrome) {
      const root = document.querySelector(`[data-testid="${id}"]`);
      if (!root || !seen(root)) continue;
      for (const e of [root, ...root.querySelectorAll("*")]) {
        if (!(e instanceof HTMLElement) || !seen(e)) continue;
        // an ellipsis is its own, declared, truncation (the document's name)
        if (getComputedStyle(e).textOverflow === "ellipsis") continue;
        if (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1) overflow.push(`${name(e)} ${e.scrollWidth}x${e.scrollHeight} in ${e.clientWidth}x${e.clientHeight}`);
      }
      for (const e of [...root.querySelectorAll("*")]) {
        if (!seen(e)) continue;
        const r = e.getBoundingClientRect();
        for (let a = e.parentElement; a && a !== root.parentElement; a = a.parentElement) {
          const cs = getComputedStyle(a);
          if (cs.overflowX === "visible" && cs.overflowY === "visible") continue;
          const b = a.getBoundingClientRect();
          if (r.left < b.left - 0.5 || r.top < b.top - 0.5 || r.right > b.right + 0.5 || r.bottom > b.bottom + 0.5) {
            clipped.push(`${name(e)} cut by ${name(a)}: [${r.left.toFixed(1)},${r.top.toFixed(1)},${r.right.toFixed(1)},${r.bottom.toFixed(1)}] in [${b.left.toFixed(1)},${b.top.toFixed(1)},${b.right.toFixed(1)},${b.bottom.toFixed(1)}]`);
            break;
          }
        }
      }
    }
    const boxes = (ids: string[]) => ids.flatMap((id) => {
      const e = document.querySelector(`[data-testid="${id}"]`);
      return e && seen(e) ? [{ id, r: e.getBoundingClientRect() }] : [];
    });
    const meet = (a: DOMRect, b: DOMRect) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
    const overlaps: string[] = [];
    for (const list of [boxes(chrome), boxes(controls)]) {
      for (let i = 0; i < list.length; i++) for (let j = i + 1; j < list.length; j++) if (meet(list[i].r, list[j].r)) overlaps.push(`${list[i].id} x ${list[j].id}`);
    }
    // on screen: every chrome box inside the window
    for (const b of boxes(chrome)) if (b.r.left < 0 || b.r.right > innerWidth || b.r.top < 0 || b.r.bottom > innerHeight) overlaps.push(`${b.id} off screen`);
    return { overflow, clipped, overlaps, shown: boxes(controls).map((b) => b.id) };
  }, [CHROME, CONTROLS] as const);
}

test.describe("Figma UI3 chrome", () => {
  test("a · the logo opens the main menu: Back to files, then File / Edit / Export / View / Preferences / Help; no inline File / Edit / Export", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    // no inline menus: the pill is the logo, the name, its ⌄
    const pill = page.getByTestId("doc-pill");
    expect((await pill.innerText()).replace(/\s+/g, " ").trim()).toBe((await state(page)).doc.name);
    for (const word of ["File", "Edit", "Export"]) await expect(page.getByRole("button", { name: word, exact: true })).toHaveCount(0);
    // the main menu, in Figma's order, a divider under Back to files
    await page.getByTestId("menu-main").click();
    const menu = page.getByTestId("main-menu");
    await expect(menu).toBeVisible();
    const rows = await menu.evaluate((m) => [...m.children].map((e) => (e.getAttribute("role") === "separator" ? "—" : (e as HTMLElement).innerText.trim())));
    expect(rows).toEqual(["Back to files", "—", ...SUBMENUS.map(([, label]) => label)]);
    // the menu hangs under the logo, inside the window
    const logo = (await page.getByTestId("menu-main").boundingBox())!, m = (await menu.boundingBox())!;
    expect(Math.abs(m.x - logo.x)).toBeLessThanOrEqual(2);
    expect(m.y).toBeGreaterThanOrEqual(logo.y + logo.height);
    // every submenu, beside the menu, with its items
    for (const [sub, , ids] of SUBMENUS) {
      const popup = await openMenu(page, sub as "file");
      for (const id of ids) await expect(popup.getByTestId(id), `${sub} › ${id}`).toBeVisible();
      const p = (await popup.boundingBox())!;
      expect(p.x, `${sub}: to the side`).toBeGreaterThanOrEqual(m.x + m.width - 2);
      expect(p.x + p.width, `${sub}: on screen`).toBeLessThanOrEqual(page.viewportSize()!.width);
    }
    await expect(page.getByTestId("github-menu")).toHaveAttribute("href", "https://github.com/zacharyyamaoka/aruco-studio");
    await expect(page.getByTestId("brand")).toHaveAttribute("href", /\/about\/$/);
    // a key does not reach the tools while the menu is open; Esc closes a level at a time
    await page.keyboard.press("r");
    expect((await state(page)).tool).toBe("select");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("menu-help-popup")).toHaveCount(0);
    await expect(menu).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    // the commands run: View › 3D, View › 2D, Edit › Undo
    await openMenu(page, "view");
    await page.getByTestId("cmd-view-3d").click();
    await expect.poll(async () => (await state(page)).view3d).toBe(true);
    await expect(menu).toHaveCount(0);
    await openMenu(page, "view");
    await expect(page.getByTestId("cmd-view-3d")).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("cmd-view-2d").click();
    await expect.poll(async () => (await state(page)).view3d).toBe(false);
    // the keys still work with the menu closed: R, V, 3, F
    await page.keyboard.press("r");
    expect((await state(page)).tool).toBe("rect");
    await page.keyboard.press("v");
    expect((await state(page)).tool).toBe("select");
    await page.keyboard.press("3");
    await expect.poll(async () => (await state(page)).view3d).toBe(true);
    await page.keyboard.press("3");
    await expect.poll(async () => (await state(page)).view3d).toBe(false);
    // Help › Keyboard shortcuts opens the keys
    await openMenu(page, "help");
    await page.getByTestId("help-menu").click();
    await expect(page.getByTestId("help-popover")).toBeVisible();
  });

  test("b · Back to files shows Home (signed out: sign in, this device, the examples); an example opens in the editor; Back returns Home", async ({ page }) => {
    await openStudio(page);
    await coreReady(page);
    const before = (await state(page)).doc.name;
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    const home = page.getByTestId("home");
    await expect(home).toBeVisible();
    await expect(home).toHaveAttribute("data-signed-in", "0");
    await expect(home.getByTestId("home-signin")).toContainText("Sign in to save online");
    await expect(home.getByTestId("home-draft")).toContainText(before);
    const examples = home.getByTestId("home-example");
    expect(await examples.count()).toBeGreaterThanOrEqual(5);
    // Home covers the editor; the keys stay off the canvas
    const r = (await home.boundingBox())!;
    expect(r.width).toBe(page.viewportSize()!.width);
    await page.keyboard.press("r");
    expect((await state(page)).tool).toBe("select");
    // an example: into the editor, its document
    await home.locator('[data-testid=home-example][data-id="disc"]').click();
    await expect(home).toHaveCount(0);
    await expect.poll(async () => (await state(page)).doc.name).toBe("Disc");
    await expect(page.getByTestId("doc-name")).toHaveText("Disc");
    // the browser's Back: Home again; Forward: the editor
    await page.goBack();
    await expect(page.getByTestId("home")).toBeVisible();
    await expect(page.getByTestId("home-draft")).toContainText("Disc");
    await page.goForward();
    await expect(page.getByTestId("home")).toHaveCount(0);
    // the card of the work on this device, and Esc, return to the editor too
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    await page.getByTestId("home-draft").click();
    await expect(page.getByTestId("home")).toHaveCount(0);
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("home")).toHaveCount(0);
    expect((await state(page)).doc.name).toBe("Disc");
    // the editor kept its state under Home
    await page.keyboard.press("r");
    expect((await state(page)).tool).toBe("rect");
  });

  test("c · signed in (the hosted API answered here): Home lists your files with their times, searches, has New and the Trash; a card opens its file in the editor", async ({ page }) => {
    // WHY mocked: the cloud is another repo's server (hosted.spec.ts drives a real one under
    // E2E_HOSTED_SERVER); Home's part is what it draws from GET /v1/me and /v1/files
    const now = Date.now(), iso = (minAgo: number) => new Date(now - minAgo * 60_000).toISOString();
    const meta = (id: string, name: string, minAgo: number, trashed = false) => ({
      id, app: "aruco-studio", name, contentType: "application/json", version: 1, size: 900, sha256: "x", createdAt: iso(minAgo + 60), updatedAt: iso(minAgo),
      trashedAt: trashed ? iso(minAgo) : null, purgeAt: trashed ? new Date(now + 29 * 86_400_000).toISOString() : null, locked: false,
    });
    const files = [meta("f-bracket", "Bracket stickers", 5), meta("f-sheet", "Sheet for the arm", 60 * 26)];
    const trash = [meta("f-old", "Old plate", 90, true)];
    await page.addInitScript(() => localStorage.setItem("shf:aruco-studio:token", "e2e-token"));
    let doc = "";
    await page.route(/\/v1\//, async (route) => {
      const url = new URL(route.request().url());
      const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
      if (url.pathname === "/v1/me") {
        return json({
          user: { id: "u1", email: "zach@example.com", name: "Zach", image: null }, plan: "free",
          limits: { filesPerApp: 100, maxFileBytes: 1e6, totalBytes: 1e8 }, usage: { totalBytes: 2000, apps: { "aruco-studio": { files: 2, trashed: 1 } } },
          app: { id: "aruco-studio", name: "ArUco Studio", extension: ".arucostudio-web.json", files: 2, limit: 100, remaining: 98 },
          billing: { provider: "dev", priceLabel: "$4/month", canUpgrade: false, canManage: false }, accountUrl: "", deletionScheduledAt: null,
        });
      }
      if (url.pathname === "/v1/files") return json({ files: url.searchParams.get("trashed") ? trash : files });
      const m = url.pathname.match(/^\/v1\/files\/([^/]+)(\/content)?$/);
      if (m && m[2]) return route.fulfill({ status: 200, contentType: "application/json", body: doc, headers: { "x-version": "1" } });
      if (m) return json(files.find((f) => f.id === m[1]) ?? trash[0]);
      return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: "not_found" }) });
    });
    await openStudio(page);
    await coreReady(page);
    doc = JSON.stringify({ ...(await state(page)).doc, name: "Bracket stickers" }, null, 2);
    await page.getByTestId("menu-main").click();
    await page.getByTestId("cmd-home").click();
    const home = page.getByTestId("home");
    await expect(home).toHaveAttribute("data-signed-in", "1");
    await expect(home.getByTestId("home-account")).toContainText("Zach");
    const cards = home.getByTestId("home-file");
    await expect(cards).toHaveCount(2);
    await expect(cards.nth(0)).toContainText("Bracket stickers");
    await expect(cards.nth(0)).toContainText(/Edited 5 min/);
    await expect(home.getByTestId("home-new")).toBeVisible();
    // search
    await home.getByTestId("home-search").fill("sheet");
    await expect(cards).toHaveCount(1);
    await expect(cards.first()).toContainText("Sheet for the arm");
    await expect(home.getByTestId("home-new")).toHaveCount(0);
    await home.getByTestId("home-search").fill("");
    // the Trash
    await home.getByTestId("home-tab-trash").click();
    await expect(cards).toHaveCount(1);
    await expect(cards.first()).toContainText("Old plate");
    await expect(cards.first()).toContainText(/Deleted in \d+ days/);
    await expect(home.getByTestId("home-restore")).toBeVisible();
    await home.getByTestId("home-tab-files").click();
    await page.screenshot({ path: test.info().outputPath("home-signed-in.png") });
    // a card: its file, in the editor
    await cards.first().click();
    await expect(home).toHaveCount(0);
    await expect(page.getByTestId("doc-name")).toHaveText("Bracket stickers");
  });

  test("d · the audit: at 1184, 1280, 1440 and 390 wide, light and dark, every skin -- nothing overflows, nothing is clipped, nothing meets", async ({ page }) => {
    test.setTimeout(300_000);
    const report: string[] = [];
    for (const width of [1184, 1280, 1440, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 800 });
      for (const skin of ["studio", "unstyled", "fusion", "onshape"]) {
        for (const theme of ["light", "dark"]) {
          await page.goto(CORE === "mock" ? "/?core=mock" : "/");
          await page.evaluate(([t, s]) => { localStorage.setItem("bam-ui.theme", t); localStorage.setItem("aruco-studio.skin", s); }, [theme, skin]);
          await page.reload();
          await expect(page.getByTestId("toolbar")).toBeVisible();
          await expect(page.locator("html")).toHaveAttribute("data-skin", skin);
          await page.mouse.move(width / 2, 300);
          const a = await audit(page);
          const when = `${width} ${skin} ${theme}`;
          expect(a.overflow, `${when}: content runs out of its box`).toEqual([]);
          expect(a.clipped, `${when}: a control cut by a box around it`).toEqual([]);
          expect(a.overlaps, `${when}: chrome that meets`).toEqual([]);
          expect(a.shown.length, `${when}: the controls on screen`).toBeGreaterThanOrEqual(width === 390 ? 10 : CONTROLS.length);
          report.push(`${when}: ${a.shown.length} controls, 0 overflow, 0 clipped, 0 overlaps`);
        }
      }
      // the menus at this width: the main menu and a submenu inside the window
      const popup = await openMenu(page, "prefs");
      for (const b of [await page.getByTestId("main-menu").boundingBox(), await popup.boundingBox()]) {
        expect(b!.x, `${width}: a menu on screen`).toBeGreaterThanOrEqual(0);
        expect(b!.x + b!.width, `${width}: a menu on screen`).toBeLessThanOrEqual(width + 0.5);
      }
      await page.keyboard.press("Escape");
      await page.keyboard.press("Escape");
    }
    test.info().annotations.push({ type: "audit", description: report.join("\n") });
    console.log(report.join("\n"));
  });

  test("e · the 2D | 3D switch sits inside the dock: its lit half is whole, inside its track and the dock", async ({ page }) => {
    await openStudio(page);
    const dims = () => page.evaluate(() => {
      const r = (q: string) => document.querySelector(q)!.getBoundingClientRect();
      const on = r('[data-testid="view-toggle"] .kit-seg-btn.on'), track = r('[data-testid="view-toggle"] .kit-seg'), dock = r('[data-testid="toolbar"]');
      return { on: [on.top, on.bottom, on.left, on.right], track: [track.top, track.bottom, track.left, track.right], dock: [dock.top, dock.bottom] };
    });
    for (const k of ["2d", "3d"]) {
      if (k === "3d") await page.keyboard.press("3");
      await expect(page.getByTestId("view-toggle")).toHaveAttribute("data-view", k);
      const d = await dims();
      expect(d.on[0], `${k}: top inside the track`).toBeGreaterThanOrEqual(d.track[0]);
      expect(d.on[1], `${k}: bottom inside the track`).toBeLessThanOrEqual(d.track[1]);
      expect(d.on[2]).toBeGreaterThanOrEqual(d.track[2]);
      expect(d.on[3]).toBeLessThanOrEqual(d.track[3]);
      expect(d.track[0]).toBeGreaterThan(d.dock[0]);
      expect(d.track[1]).toBeLessThan(d.dock[1]);
    }
  });
});
