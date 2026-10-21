// While a feature is in focus and its marker dims show, the sketch dims that
// measure its PROFILE shapes are not drawn (Zach, 2026-10-21: "hide the exterior
// dimensions on the profile if they are set; it's confusing seeing both sets").
// They are back when the feature loses focus or the profile shape is selected.
// Display only: the dims stay in the document. Screenshots go to E2E_SHOTS.
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { clickAt, coreReady, idle, openMenu, openStudio, panelTab, state, toClient } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: path.join(SHOTS, `dimhide-${name}.png`) });
}

test("a feature's marker dims hide the profile rectangle's sketch dims; Esc and an edge click bring them back", async ({ page }) => {
  await openStudio(page);
  await coreReady(page);
  await openMenu(page, "file");
  await page.getByTestId("cmd-new").click();

  // a rectangle with driving W and H dims (R, click, W 50 Tab H 80 Enter), and a second one that stays a plain shape
  await page.keyboard.press("r");
  const [ax, ay] = await toClient(page, -30, -40);
  await page.mouse.click(ax, ay);
  const [bx, by] = await toClient(page, 20, 40);
  await page.mouse.move(bx, by, { steps: 6 });
  await expect(page.getByTestId("draw-w")).toBeFocused();
  await page.keyboard.type("50");
  await page.keyboard.press("Tab");
  await page.keyboard.type("80");
  await page.keyboard.press("Enter");
  let s = await state(page);
  const profileId: string = s.doc.shapes[0].id;
  expect(s.doc.dims.map((d: any) => [d.kind, d.value]).sort()).toEqual([["h", 80], ["w", 50]]);

  // another rectangle, with a dim of its own: never hidden
  await page.keyboard.press("r");
  const [cx, cy] = await toClient(page, 60, -20);
  await page.mouse.click(cx, cy);
  const [dx, dy] = await toClient(page, 90, 10);
  await page.mouse.move(dx, dy, { steps: 6 });
  await page.keyboard.type("30");
  await page.keyboard.press("Tab");
  await page.keyboard.type("30");
  await page.keyboard.press("Enter");
  s = await state(page);
  expect(s.doc.dims).toHaveLength(4);
  const otherId: string = s.doc.shapes[1].id;
  const profileDims = s.doc.dims.filter((d: any) => d.shape === profileId).map((d: any) => d.id);
  const otherDims = s.doc.dims.filter((d: any) => d.shape === otherId).map((d: any) => d.id);
  expect(profileDims).toHaveLength(2);
  const profileSel = profileDims.map((id: string) => `[data-sketch-dim="${id}"]`).join(",");
  const otherSel = otherDims.map((id: string) => `[data-sketch-dim="${id}"]`).join(",");

  // a feature on the first rectangle: its panel is open, its marker dims show, the rectangle's sketch dims do not
  await page.keyboard.press("Escape");
  await clickAt(page, -30, 0);
  await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "shape", id: profileId });
  // the profile shape itself is selected for editing: its dims show
  await expect(page.locator(profileSel)).toHaveCount(2);
  await shot(page, "before-edge-selected");
  await page.keyboard.press("a");
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await panelTab(page, "marker");
  await idle(page);
  await expect(page.locator('[data-testid="dims"] [data-dim]').first()).toBeVisible();
  await shot(page, "panel-open");
  await expect(page.locator(profileSel), "the profile's sketch dims are not in the DOM").toHaveCount(0);
  await expect(page.locator(otherSel), "another shape's dims stay").toHaveCount(2);
  expect((await state(page)).doc.dims, "the data is untouched").toHaveLength(4);

  // OK closes the panel; Esc leaves nothing in focus: both sets of sketch dims show again
  await page.getByTestId("panel-ok").click();
  await expect(page.getByTestId("extrude-panel")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect.poll(async () => (await state(page)).sel).toBeNull();
  await expect(page.locator('[data-testid="dims"] [data-dim]')).toHaveCount(0);
  await expect(page.locator(profileSel)).toHaveCount(2);
  await expect(page.locator(otherSel)).toHaveCount(2);

  // the marker selected (a click on it): its dims show, the profile's sketch dims go
  const fid: string = (await state(page)).doc.features[0].id;
  await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().click();
  await expect.poll(async () => (await state(page)).sel).toMatchObject({ kind: "feature", id: fid });
  await expect(page.locator('[data-testid="dims"] [data-dim]').first()).toBeVisible();
  await expect(page.locator(profileSel)).toHaveCount(0);
  await expect(page.locator(otherSel)).toHaveCount(2);
  await shot(page, "marker-selected");

  // Esc: they are back
  await page.keyboard.press("Escape");
  await expect(page.locator(profileSel)).toHaveCount(2);

  // the rectangle itself selected for editing (a plain click on its edge opens the feature, as a click on the marker does; Shift+click selects the shape): the sketch dims show, and the D tool shows them too
  await page.keyboard.down("Shift");
  await clickAt(page, -30, 0);
  await page.keyboard.up("Shift");
  await expect.poll(async () => (await state(page)).sel).toEqual({ kind: "shape", id: profileId });
  await expect(page.locator(profileSel)).toHaveCount(2);
  await page.keyboard.press("Escape");
  await page.locator(`[data-marker="${fid}"] [data-marker-black]`).first().click();
  await expect(page.locator(profileSel)).toHaveCount(0);
  await page.keyboard.press("d");
  await expect(page.getByTestId("tool-dim")).toHaveAttribute("data-active", "1");
  await expect(page.locator(profileSel)).toHaveCount(2);
});
