// Review finding #4 (2026-10-21): a file that is not a drawable document is
// refused before anything is replaced; the note says what is wrong and where.
import path from "node:path";
import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { coreReady, dragWorld, idle, openMenu, openStudio, state } from "./helpers";

test("opening a malformed file leaves the document and its history as they were, with a precise note", async ({ page }) => {
  await openStudio(page);
  await coreReady(page);
  // an edit, so there is history to keep
  await page.keyboard.press("r");
  await dragWorld(page, [10, 10], [40, 30]);
  await idle(page);
  const before = await state(page);
  expect(before.canUndo).toBe(true);
  const bad = path.join(test.info().outputDir, "bad.arucostudio-web.json");
  mkdirSync(test.info().outputDir, { recursive: true });
  writeFileSync(bad, JSON.stringify({ format: "arucostudio-web", version: 4, name: "Bad", shapes: [{ kind: "poly", id: "bad" }], features: [] }));
  await openMenu(page, "file");
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
  await chooser.setFiles(bad);
  await expect(page.getByTestId("note")).toContainText('Could not open bad.arucostudio-web.json: shape 1 ("bad"): a poly needs pts');
  const after = await state(page);
  expect(after.doc).toEqual(before.doc);
  expect(after.canUndo).toBe(true);
  // and the history is the one before the failed open: Ctrl+Z takes the rectangle back out
  await page.keyboard.press("Escape");
  await page.keyboard.press("Control+z");
  await idle(page);
  expect((await state(page)).doc.shapes).toHaveLength(before.doc.shapes.length - 1);
});
