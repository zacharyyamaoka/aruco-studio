// Figma UI3's chrome (Zach, 2026-10-20 night: "Figma doesn't have the file
// edit export etc there... it's in a drop down when you press the icon, and
// there is also the button there when you click the icon to go home"; "the 2D
// and 3D are clipping"). help.figma.com's "Explore the navigation bar": the
// Figma menu opens Back to files, then File ›, Edit ›, View › … The main menu
// behind the logo, no inline File / Edit / Export, Home ("Back to files") with
// the browser's Back, and an audit of every chrome control at 1184, 1280, 1440
// and 390 wide, both themes, all four skins: no content overflows its box, no
// control is clipped by a box around it, no two controls meet.
// The two menus are Figma's split (Zach, 2026-10-21: "Please unify these two
// file menus, they are redundant... Copy how figma does it"; simple-hosted-
// files SPEC "v2.9 Menus follow Figma's split"): the logo's is the app's, the
// name's ⌄ is this file's, and no item is in both (f).
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, openMenu, openStudio, state, type MainSub } from "./helpers";

const SUBMENUS: [string, string, string[]][] = [
  ["file", "File", ["cmd-new", "cmd-open", "cmd-save", "cmd-examples"]],
  ["edit", "Edit", ["cmd-undo", "cmd-redo", "cmd-reid", "cmd-presets"]],
  ["export", "Export", ["cmd-print", "cmd-svg", "cmd-pdf"]],
  ["view", "View", ["cmd-view-2d", "cmd-view-3d", "cmd-fit"]],
  ["prefs", "Preferences", ["theme-light", "theme-dark", "skin-studio", "skin-unstyled", "skin-fusion", "skin-onshape"]],
  ["account", "Help and account", ["help-menu", "github-menu", "brand", "shf-action-signin"]],
];

/** The chrome: its boxes, and every control in them. */
const CHROME = ["doc-pill", "actions-pill", "toolbar", "corner", "zoom-indicator"];
const CONTROLS = ["menu-main", "doc-name", "menu-doc", "menu-cad", "act-verify", "act-print",
  "tool-select", "tool-rect", "tool-circle", "tool-dim", "tool-extrude", "tool-fit", "view-toggle", "help", "github", "zoom-menu"];

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

/** Signed in, the hosted API answered here (GET /v1/me, /v1/files, a file's
 *  content: `doc`). */
async function signedIn(page: Page): Promise<{ doc: string }> {
  const cloud = { doc: "" };
  // WHY mocked: the cloud is another repo's server (hosted.spec.ts drives a real one under
  // E2E_HOSTED_SERVER); Home's and the menus' part is what they draw from GET /v1/me and /v1/files
  const now = Date.now(), iso = (minAgo: number) => new Date(now - minAgo * 60_000).toISOString();
  const meta = (id: string, name: string, minAgo: number, trashed = false) => ({
    id, app: "aruco-studio", name, contentType: "application/json", version: 1, size: 900, sha256: "x", createdAt: iso(minAgo + 60), updatedAt: iso(minAgo),
    trashedAt: trashed ? iso(minAgo) : null, purgeAt: trashed ? new Date(now + 29 * 86_400_000).toISOString() : null, locked: false,
  });
  const files = [meta("f-bracket", "Bracket stickers", 5), meta("f-sheet", "Sheet for the arm", 60 * 26)];
  const trash = [meta("f-old", "Old plate", 90, true)];
  await page.addInitScript(() => localStorage.setItem("shf:aruco-studio:token", "e2e-token"));
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
    if (m && m[2]) return route.fulfill({ status: 200, contentType: "application/json", body: cloud.doc, headers: { "x-version": "1" } });
    if (m) return json(files.find((f) => f.id === m[1]) ?? trash[0]);
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: "not_found" }) });
  });
  return cloud;
}

/** One row of a menu: its test id, its label (the words, not the hint), and
 *  whether it is a pick (a radio row: a setting's value, Skin › Fusion 360). */
type Row = { menu: string; id: string; label: string; pick: boolean };

/** Every item of the name's ⌄ and of the main menu with each submenu open in
 *  turn (on a phone the submenus are groups in the menu itself). */
async function menuRows(page: Page): Promise<{ doc: Row[]; main: Row[] }> {
  const rows = (menu: string, popup: string, item: string, label: string) => page.getByTestId(popup).evaluate((p, [menu, item, label]) =>
    [...p.querySelectorAll(item)].map((e) => ({ menu, id: e.getAttribute("data-testid") ?? "", label: (e.querySelector(label) as HTMLElement | null)?.innerText.trim() ?? (e as HTMLElement).innerText.trim(),
      pick: e.getAttribute("role") === "menuitemradio" })),
  [menu, item, label] as const);
  await page.getByTestId("menu-doc").click();
  await expect(page.getByTestId("doc-menu")).toBeVisible();
  const doc = await rows("⌄", "doc-menu", ".dm-item", ".dm-label");
  await page.getByTestId("menu-doc").click();
  await expect(page.getByTestId("doc-menu")).toHaveCount(0);
  const ITEM = "[role^=menuitem]";
  await page.getByTestId("menu-main").click();
  const main = await rows("main", "main-menu", ITEM, ".kit-menu-label");
  for (const [sub] of SUBMENUS) {
    if (!(await page.getByTestId(`menu-${sub}`).count())) continue;
    const popup = await openMenu(page, sub as MainSub);
    await expect(popup.locator(ITEM).first()).toBeVisible();
    main.push(...(await rows(sub, `menu-${sub}-popup`, ITEM, ".kit-menu-label")));
  }
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("main-menu")).toHaveCount(0);
  return { doc, main };
}

/** The rows that share a test id, or a command's label (empty: none).
 *  WHY picks are out of the labels: a skin is named after the CAD program it
 *  copies, so Preferences › Skin › "Fusion 360" is not the phone's ⌄ ›
 *  Download for CAD › "Fusion 360"; their test ids are still compared. */
function twice(rows: Row[]): string[] {
  const out: string[] = [];
  for (const key of ["id", "label"] as const) {
    const seen = new Map<string, Row>();
    for (const r of key === "label" ? rows.filter((x) => !x.pick) : rows) {
      const was = seen.get(r[key]);
      if (was) out.push(`${key} "${r[key]}": ${was.menu} and ${r.menu}`);
      else seen.set(r[key], r);
    }
  }
  return out;
}

test.describe("Figma UI3 chrome", () => {
  test("a · the logo opens the main menu: Back to files, then File / Edit / Export / View / Preferences / Help and account; no inline File / Edit / Export", async ({ page }) => {
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
      const popup = await openMenu(page, sub as MainSub);
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
    await expect(page.getByTestId("menu-account-popup")).toHaveCount(0);
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
    // Help and account › Keyboard shortcuts opens the keys
    await openMenu(page, "account");
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
    const cloud = await signedIn(page);
    await openStudio(page);
    await coreReady(page);
    cloud.doc = JSON.stringify({ ...(await state(page)).doc, name: "Bracket stickers" }, null, 2);
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

  test("f · no item is in both menus: the name's ⌄ is this file (status, Rename, Duplicate, Version history, Move to trash), the logo's File ▸ and Help and account ▸ the rest; signed in and out, desk and phone", async ({ page }) => {
    const shots = (name: string) => page.screenshot({ path: test.info().outputPath(`${name}.png`) });
    const ids = (rows: Row[], menu: string) => rows.filter((r) => r.menu === menu).map((r) => r.id);
    // signed out
    await openStudio(page);
    await coreReady(page);
    let { doc, main } = await menuRows(page);
    expect(twice([...doc, ...main]), "signed out: in two places").toEqual([]);
    expect(ids(doc, "⌄")).toEqual(["shf-action-rename"]);
    expect(ids(main, "file")).toEqual(["cmd-new", "cmd-open", "cmd-save", "cmd-examples"]);
    expect(ids(main, "account")).toEqual(["help-menu", "github-menu", "brand", "shf-action-signin"]);
    await page.getByTestId("menu-doc").click();
    await expect(page.getByTestId("shf-menu-status")).toHaveText("Not saved online");
    await page.getByTestId("menu-doc").click();
    const account = await openMenu(page, "account");
    await expect(account.getByTestId("shf-action-signin")).toHaveText("Sign in to save online");
    await expect(account.getByTestId("shf-account-card")).toHaveCount(0);
    await shots("account-signed-out");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("main-menu")).toHaveCount(0);

    // signed in (the API answered here)
    const context = page.context();
    const signed = await context.newPage();
    await signedIn(signed);
    await openStudio(signed);
    await coreReady(signed);
    await expect(signed.getByTestId("shf-status")).toBeVisible();
    ({ doc, main } = await menuRows(signed));
    expect(twice([...doc, ...main]), "signed in: in two places").toEqual([]);
    expect(ids(doc, "⌄")).toEqual(["shf-action-rename", "shf-action-duplicate", "shf-action-history", "shf-action-trash"]);
    expect(doc.map((r) => r.label)).toEqual(["Rename", "Duplicate", "Version history", "Move to trash"]);
    expect(ids(main, "main")).toEqual(["cmd-home", ...SUBMENUS.map(([sub]) => `menu-${sub}`)]);
    expect(ids(main, "file")).toEqual(["cmd-new", "shf-action-files", "cmd-open", "shf-action-save", "shf-action-saveas", "shf-action-download",
      "shf-action-export", "shf-action-trash-view", "cmd-examples", "shf-autosave-toggle"]);
    expect(main.filter((r) => r.menu === "file").map((r) => r.label)).toEqual(["New", "Open…", "Open from this computer…", "Save", "Save as…", "Download",
      "Export all files", "Trash…", "Examples…", "Autosave"]);
    expect(ids(main, "account")).toEqual(["help-menu", "github-menu", "brand", "shf-action-account", "shf-action-signout"]);
    expect(main.find((r) => r.menu === "main" && r.id === "menu-account")?.label).toBe("Help and account");
    // the status line, then this file's items; a new document is not saved online yet: Duplicate, History and Trash wait for it
    await signed.getByTestId("menu-doc").click();
    const menu = signed.getByTestId("doc-menu");
    await expect(menu.getByTestId("shf-menu-status")).toHaveText("Not saved yet");
    for (const id of ["shf-action-duplicate", "shf-action-history", "shf-action-trash"]) await expect(menu.getByTestId(id)).toBeDisabled();
    await expect(menu.getByTestId("shf-action-rename")).toBeEnabled();
    await signed.screenshot({ path: test.info().outputPath("name-menu-signed-in.png") });
    await signed.getByTestId("menu-doc").click();
    // File ▸: Save with its key, Download with the file's extension, Autosave checked, and it stays open when clicked
    const file = await openMenu(signed, "file");
    await expect(file.getByTestId("shf-action-save")).toContainText("Ctrl+S");
    await expect(file.getByTestId("shf-action-download")).toContainText(".arucostudio-web.json");
    await expect(file.getByTestId("shf-action-export")).toContainText(".zip");
    await expect(file.getByTestId("shf-autosave-toggle")).toHaveAttribute("aria-checked", "true");
    await signed.screenshot({ path: test.info().outputPath("file-signed-in.png") });
    await file.getByTestId("shf-autosave-toggle").click();
    await expect(file.getByTestId("shf-autosave-toggle")).toHaveAttribute("aria-checked", "false");
    await file.getByTestId("shf-autosave-toggle").click();
    await expect(file.getByTestId("shf-autosave-toggle")).toHaveAttribute("aria-checked", "true");
    // Help and account ▸: the card, the usage, Your account, Sign out
    const acct = await openMenu(signed, "account");
    await expect(acct.getByTestId("shf-account-card")).toContainText("Zach");
    await expect(acct.getByTestId("shf-account-card")).toContainText("zach@example.com");
    await expect(acct.getByTestId("shf-usage")).toHaveText(/^2 of 100 free files in ArUco Studio/);
    await signed.screenshot({ path: test.info().outputPath("account-signed-in.png") });
    await signed.keyboard.press("Escape");
    await signed.keyboard.press("Escape");
    await expect(signed.getByTestId("main-menu")).toHaveCount(0);
    // Open… is the files dialog
    await (await openMenu(signed, "file")).getByTestId("shf-action-files").click();
    await expect(signed.getByTestId("shf-files-dialog").getByTestId("shf-file-row")).toHaveCount(2);
    await signed.keyboard.press("Escape");
    await expect(signed.getByTestId("shf-files-dialog")).toHaveCount(0);

    // a phone: the submenus are groups, Download for CAD folds into ⌄; still nothing twice
    await signed.setViewportSize({ width: 390, height: 844 });
    await expect(signed.getByTestId("menu-file")).toHaveCount(0);
    ({ doc, main } = await menuRows(signed));
    expect(twice([...doc, ...main]), "a phone: in two places").toEqual([]);
    expect(ids(doc, "⌄")).toEqual(["shf-action-rename", "shf-action-duplicate", "shf-action-history", "shf-action-trash", "cad-fusion", "cad-onshape"]);
    await signed.close();
  });
});
