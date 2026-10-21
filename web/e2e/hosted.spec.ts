// Simple Hosted Files in the Studio (the title bar in the document pill, the
// file and account items in the main menu: Figma's split, SPEC v2.9),
// against a LOCAL hosted-files server in dev mode: E2E_HOSTED_SERVER, which
// playwright.config.ts also builds in as the Studio's cloud. Sign-in is the
// real email-code flow, the code read from the server's dev mailbox. Bytes
// are compared with what the server holds, read over its API with the
// page's own bearer.
import fs from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { clickAt, dragWorld, idle, openMenu, state } from "./helpers";

const HOSTED = process.env.E2E_HOSTED_SERVER ?? "";
test.skip(!HOSTED, "needs a local Simple Hosted Files: E2E_HOSTED_SERVER=http://localhost:<port>");

const TOKEN_KEY = "shf:aruco-studio:token";
/** the file the Studio saves: serialise() in model/doc.ts */
const fileText = (doc: unknown) => JSON.stringify(doc, null, 2);

async function open(page: Page): Promise<void> {
  await page.goto("/?core=mock");
  await expect(page.getByTestId("app")).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).__aruco?.kind)).toBe("mock");
  // the core's presets have filled the document's (store.ts loadCoreFacts):
  // that is an edit of its own, which would otherwise land as a version
  await expect.poll(async () => (await state(page)).doc.default_preset).not.toBeNull();
}

/** The name's ⌄ menu, this file's (open it if it is not). */
async function docMenu(page: Page) {
  const menu = page.getByTestId("doc-menu");
  if (!(await menu.count())) await page.getByTestId("menu-doc").click();
  await expect(menu).toBeVisible();
  return menu;
}

async function signIn(page: Page, email: string): Promise<void> {
  await (await openMenu(page, "account")).getByTestId("shf-action-signin").click();
  const dialog = page.getByTestId("shf-signin-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByTestId("shf-signin-email-input").fill(email);
  await dialog.getByTestId("shf-signin-email-continue").click();
  await expect(dialog.getByTestId("shf-signin-code-input")).toBeVisible();
  const { otp } = await (await fetch(`${HOSTED}/dev/mailbox?email=${encodeURIComponent(email)}`)).json();
  await dialog.getByTestId("shf-signin-code-input").fill(otp);
  await dialog.getByTestId("shf-signin-code-verify").click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("shf-status")).toBeVisible();
}

/** The status dot says Saved (its words are for screen readers and tests). */
async function saved(page: Page): Promise<void> {
  await expect(page.getByTestId("shf-status")).toHaveAttribute("data-kind", "saved", { timeout: 15_000 });
  await expect(page.getByTestId("shf-status")).toHaveText(/^Saved/);
}

/** Save an untitled document: File › Save, the name prompt (the document's name), OK. */
async function saveAs(page: Page, name: string): Promise<string> {
  await (await openMenu(page, "file")).getByTestId("shf-action-save").click();
  const input = page.getByTestId("shf-name-input");
  await expect(input).toBeVisible();
  await input.fill(name);
  await page.getByTestId("shf-name-ok").click();
  await saved(page);
  return page.evaluate(() => (window as any).__aruco.state().doc.name);
}

async function api(page: Page, path: string): Promise<Response> {
  const token = await page.evaluate((k) => localStorage.getItem(k), TOKEN_KEY);
  return fetch(HOSTED + path, { headers: { Authorization: `Bearer ${token}` } });
}

/** The open cloud file's id: the one Open… marks Open. */
async function openFileId(page: Page): Promise<string> {
  const files = (await (await api(page, "/v1/files?app=aruco-studio")).json()).files as { id: string; name: string }[];
  const name = (await state(page)).doc.name;
  return files.find((f) => f.name === name)!.id;
}

/** One more rectangle, drawn on the plate (where Custom placement draws its
 *  own, clear of the holes): an edit of the document. */
async function edit(page: Page, from: [number, number] = [58, 45], to: [number, number] = [82, 69]): Promise<void> {
  const before = (await state(page)).doc.shapes.length;
  await page.keyboard.press("r");
  await dragWorld(page, from, to);
  await page.keyboard.press("Escape");
  await expect.poll(async () => (await state(page)).doc.shapes.length).toBe(before + 1);
  await idle(page);
}

let n = 0;
const newEmail = () => `studio-${Date.now()}-${n++}@example.com`;

test.describe("Simple Hosted Files", () => {
  test("a · sign in: the account, its plan and usage are in Help and account ›, Autosave in File ›; signed out the Studio works as before", async ({ page }) => {
    await open(page);
    // signed out: no status, the name is the document's, Help and account › offers sign-in
    await expect(page.getByTestId("shf-status")).toHaveCount(0);
    await expect(page.getByTestId("doc-name")).toHaveText("Plate");
    const email = newEmail();
    await signIn(page, email);
    const account = await openMenu(page, "account");
    await expect(account.getByTestId("shf-account-card")).toContainText(email);
    await expect(account.getByTestId("shf-usage")).toHaveText(/^\d+ of \d+ free files in /);
    await expect(account.getByTestId("shf-action-signout")).toBeVisible();
    await expect((await openMenu(page, "file")).getByTestId("shf-autosave-toggle")).toHaveAttribute("aria-checked", "true");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    // ⌄ is this file's: its status and items, never the account, Theme or Skin (Preferences ›)
    const menu = await docMenu(page);
    await expect(menu.getByTestId("shf-menu-status")).toBeVisible();
    await expect(menu.getByTestId("shf-action-rename")).toBeVisible();
    for (const id of ["shf-account-card", "shf-action-signout", "shf-autosave-toggle", "shf-action-save", "theme-dark"]) await expect(menu.getByTestId(id), id).toHaveCount(0);
    await expect(page.getByTestId("doc-name")).toHaveText("Plate");
  });

  test("b · Save: the name prompt is the document's name, and the file is in Open…", async ({ page }) => {
    await open(page);
    await signIn(page, newEmail());
    await (await openMenu(page, "file")).getByTestId("shf-action-save").click();
    await expect(page.getByTestId("shf-name-input")).toHaveValue("Plate");
    await page.getByTestId("shf-name-input").fill("Forearm plate");
    await page.getByTestId("shf-name-ok").click();
    await saved(page);
    // one name: the document took the file's
    await expect(page.getByTestId("doc-name")).toHaveText("Forearm plate");
    expect((await state(page)).doc.name).toBe("Forearm plate");
    await (await openMenu(page, "file")).getByTestId("shf-action-files").click();
    const dialog = page.getByTestId("shf-files-dialog");
    await expect(dialog.getByTestId("shf-file-row")).toHaveCount(1);
    await expect(dialog.getByTestId("shf-file-row")).toContainText("Forearm plate");
    // the bytes on the server are the Studio's file
    const id = await dialog.getByTestId("shf-file-row").getAttribute("data-file-id");
    expect(await (await api(page, `/v1/files/${id}/content`)).text()).toBe(fileText((await state(page)).doc));
  });

  test("c · an edit autosaves; after a reload, Open brings back the same document; a rename renames both", async ({ page }) => {
    await open(page);
    await signIn(page, newEmail());
    await saveAs(page, "Autosaved");
    const id = await openFileId(page);
    await edit(page);
    await saved(page);
    const edited = (await state(page)).doc;
    expect(await (await api(page, `/v1/files/${id}/content`)).text()).toBe(fileText(edited));
    // rename in place: the document and the file
    await page.getByTestId("shf-filename").click();
    await page.getByTestId("doc-name-input").fill("Autosaved, renamed");
    await page.getByTestId("doc-name-input").press("Enter");
    await expect(page.getByTestId("doc-name")).toHaveText("Autosaved, renamed");
    await expect.poll(async () => (await (await api(page, `/v1/files/${id}`)).json()).name).toBe("Autosaved, renamed");
    await saved(page);
    const renamed = (await state(page)).doc;
    expect(renamed.name).toBe("Autosaved, renamed");
    await expect.poll(async () => (await api(page, `/v1/files/${id}/content`)).text()).toBe(fileText(renamed));
    // undo is the drawing's, never the name's
    await page.keyboard.press("Control+z");
    await expect.poll(async () => (await state(page)).doc.shapes.length).toBe(edited.shapes.length - 1);
    expect((await state(page)).doc.name).toBe("Autosaved, renamed");
    await saved(page);
    const undone = (await state(page)).doc;

    await page.reload();
    await expect(page.getByTestId("app")).toBeVisible();
    await expect(page.getByTestId("shf-status")).toBeVisible();
    await (await openMenu(page, "file")).getByTestId("shf-action-files").click();
    await page.getByTestId("shf-files-dialog").locator(`[data-file-id="${id}"]`).click();
    await saved(page);
    expect(fileText((await state(page)).doc)).toBe(fileText(undone));
    await expect(page.getByTestId("doc-name")).toHaveText("Autosaved, renamed");
  });

  test("d · History shows the versions (Save, then autosaves), and restores one", async ({ page }) => {
    await open(page);
    await signIn(page, newEmail());
    await saveAs(page, "With history");
    const id = await openFileId(page);
    const first = await (await api(page, `/v1/files/${id}/content?version=1`)).text();
    const shapes = (await state(page)).doc.shapes.length;
    await edit(page);
    await saved(page);
    await page.getByTestId("shf-status").click();
    const dialog = page.getByTestId("shf-history-dialog");
    await expect(dialog).toBeVisible();
    const rows = dialog.getByTestId("shf-version-row");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toHaveAttribute("data-kind", "auto");
    await expect(rows.nth(1)).toHaveAttribute("data-kind", "manual");
    await expect(rows.nth(1)).toHaveAttribute("data-version", "1");
    // restoring version 1 adds version 3, with version 1's bytes, and puts it in the Studio
    await rows.nth(1).getByTestId("shf-version-restore").click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId("shf-status")).toHaveAttribute("title", /version 3/);
    await saved(page);
    expect((await state(page)).doc.shapes.length).toBe(shapes);
    const versions = (await (await api(page, `/v1/files/${id}/versions`)).json()).versions;
    expect(versions.map((v: { version: number }) => v.version)).toEqual([3, 2, 1]);
    expect(await (await api(page, `/v1/files/${id}/content`)).text()).toBe(first);
    expect(fileText((await state(page)).doc)).toBe(first);
  });

  test("e · Download gives the exact bytes the server holds", async ({ page }) => {
    await open(page);
    await signIn(page, newEmail());
    await saveAs(page, "Downloaded");
    await edit(page);
    await saved(page);
    const id = await openFileId(page);
    const [download] = await Promise.all([page.waitForEvent("download"), (await openMenu(page, "file")).getByTestId("shf-action-download").click()]);
    expect(download.suggestedFilename()).toBe("Downloaded.arucostudio-web.json");
    const got = fs.readFileSync((await download.path())!);
    const held = Buffer.from(await (await api(page, `/v1/files/${id}/content`)).arrayBuffer());
    expect(got.equals(held)).toBe(true);
    expect(got.toString("utf8")).toBe(fileText((await state(page)).doc));
  });

  test("f · a stale tab's save goes through If-Match: refused, written on top, both versions kept", async ({ page, context }) => {
    await open(page);
    await signIn(page, newEmail());
    await saveAs(page, "Two tabs");
    const id = await openFileId(page);
    // the second tab (same browser: same account) opens the same file at version 1
    const other = await context.newPage();
    await open(other);
    await expect(other.getByTestId("shf-status")).toBeVisible();
    await (await openMenu(other, "file")).getByTestId("shf-action-files").click();
    await other.getByTestId("shf-files-dialog").locator(`[data-file-id="${id}"]`).click();
    await saved(other);
    // this tab moves the file to version 2
    await page.bringToFront();
    await edit(page);
    await saved(page);
    const ours = (await state(page)).doc;
    // the other tab, still on version 1, edits: its autosave is refused (409) and lands on top
    await other.bringToFront();
    await edit(other, [60, 48], [75, 63]);
    await expect(other.getByTestId("shf-status")).toHaveAttribute("data-kind", "conflict", { timeout: 15_000 });
    await expect(other.getByTestId("shf-status")).toHaveText("Both versions kept");
    const theirs = (await state(other)).doc;
    const versions = (await (await api(page, `/v1/files/${id}/versions`)).json()).versions as { version: number }[];
    expect(versions.map((v) => v.version)).toEqual([3, 2, 1]);
    expect(await (await api(page, `/v1/files/${id}/content?version=2`)).text()).toBe(fileText(ours));
    expect(await (await api(page, `/v1/files/${id}/content?version=3`)).text()).toBe(fileText(theirs));
    await other.close();
  });

  test("h · autosave is the default (apps.json \"all\"): New, a rectangle and A, and the file is in Open with no Save pressed; Ctrl+S is a checkpoint; Autosave off creates nothing", async ({ page }) => {
    await open(page);
    await signIn(page, newEmail());
    const files = async () => (await (await api(page, "/v1/files?app=aruco-studio")).json()).files as { id: string; name: string }[];
    await (await openMenu(page, "file")).getByTestId("cmd-new").click();
    await expect(page.getByTestId("doc-name")).toHaveText("Untitled");
    // a blank New is not an edit: nothing is created
    await page.waitForTimeout(3_000);
    expect(await files()).toEqual([]);
    // a rectangle, its face, A: the ArUco Extrude
    await page.keyboard.press("r");
    await dragWorld(page, [-30, -20], [30, 20]);
    await page.keyboard.press("Escape");
    await clickAt(page, 0, 0);
    await expect.poll(async () => (await state(page)).sel?.kind).toBe("profile");
    await page.keyboard.press("a");
    await idle(page);
    await expect.poll(async () => (await state(page)).doc.features.length).toBe(1);
    await saved(page);
    await expect.poll(async () => (await files()).map((f) => f.name)).toEqual(["Untitled"]);
    const [{ id }] = await files();
    await expect.poll(async () => (await api(page, `/v1/files/${id}/content`)).text()).toBe(fileText((await state(page)).doc));
    // Open… lists it
    await (await openMenu(page, "file")).getByTestId("shf-action-files").click();
    const dialog = page.getByTestId("shf-files-dialog");
    await expect(dialog.getByTestId("shf-file-row")).toHaveCount(1);
    await expect(dialog.getByTestId("shf-file-row")).toHaveAttribute("data-file-id", id);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    // the name's ⌄: saved, though nobody saved
    const menu = await docMenu(page);
    await expect(menu.getByTestId("shf-menu-status")).toHaveText("Saved · just now");
    await page.screenshot({ path: test.info().outputPath("name-menu-autosaved.png") });
    await page.keyboard.press("Escape");
    // Ctrl+S still saves now: a manual version, the checkpoint thinning never removes
    await page.keyboard.press("r");
    await dragWorld(page, [40, -10], [55, 10]);
    await page.keyboard.press("Escape");
    await page.keyboard.press("Control+s");
    await saved(page);
    const versions = async () => (await (await api(page, `/v1/files/${id}/versions`)).json()).versions as { version: number; kind: string }[];
    await expect.poll(async () => (await versions())[0]?.kind).toBe("manual");
    const kept = (await versions()).length;

    // Autosave off (the user's choice, File ›): a new document's edit creates nothing
    const toggle = (await openMenu(page, "file")).getByTestId("shf-autosave-toggle");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await (await openMenu(page, "file")).getByTestId("cmd-new").click();
    await expect(page.getByTestId("doc-name")).toHaveText("Untitled");
    await page.keyboard.press("r");
    await dragWorld(page, [-30, -20], [30, 20]);
    await page.keyboard.press("Escape");
    await expect.poll(async () => (await state(page)).doc.shapes.length).toBe(1);
    await page.waitForTimeout(4_000);
    expect((await files()).map((f) => f.id)).toEqual([id]);
    expect((await versions()).length).toBe(kept);
    await expect(page.getByTestId("shf-status")).not.toHaveAttribute("data-kind", "saved");
  });

  test("g · ⌄ is this file: its status line, Duplicate makes a copy on the server, Move to trash puts it in File › Trash…", async ({ page }) => {
    await open(page);
    await signIn(page, newEmail());
    await saveAs(page, "Kept");
    const id = await openFileId(page);
    let menu = await docMenu(page);
    await expect(menu.getByTestId("shf-menu-status")).toHaveText(/^Saved · /);
    await page.screenshot({ path: test.info().outputPath("name-menu-saved.png") });
    await menu.getByTestId("shf-action-duplicate").click();
    await expect(menu).toHaveCount(0);
    const names = async () => ((await (await api(page, "/v1/files?app=aruco-studio")).json()).files as { name: string }[]).map((f) => f.name).sort();
    await expect.poll(names).toEqual(["Kept", "Kept (copy)"]);
    // the open file is still the one it was
    expect(await openFileId(page)).toBe(id);
    menu = await docMenu(page);
    await menu.getByTestId("shf-action-trash").click();
    await expect.poll(names).toEqual(["Kept (copy)"]);
    await (await openMenu(page, "file")).getByTestId("shf-action-trash-view").click();
    const dialog = page.getByTestId("shf-files-dialog");
    await expect(dialog.getByTestId("shf-file-row")).toHaveCount(1);
    await expect(dialog.getByTestId("shf-file-row")).toContainText("Kept");
    await expect(dialog.getByTestId("shf-file-row")).toHaveAttribute("data-file-id", id);
  });
});
