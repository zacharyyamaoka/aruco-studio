// The tool box at the foot of the canvas ("type W H and Enter") takes more
// than keys (lane polish, 2026-10-17): a paste (Ctrl+V of "80 50"), and text
// from an input method or insertText through its own hidden field, so a
// pasted or IME-entered size works. Full-width digits fold to ASCII.
// Every bar reads the file on disk or the DOM.
import { expect, test } from "@playwright/test";
import { freshFile, idle, readFile } from "./helpers";

/** A paste event at `selector` (the page itself by default), as Ctrl+V
 *  sends it, with `text` on the clipboard. */
async function paste(page: import("@playwright/test").Page, text: string, selector = "body") {
  await page.evaluate(([t, sel]) => {
    const dt = new DataTransfer();
    dt.setData("text/plain", t);
    const el = document.querySelector(sel) as HTMLElement;
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  }, [text, selector] as const);
}

function shapes(file: string): any[] {
  return readFile(file).sketches.flatMap((s: any) => s.shapes);
}

test("a pasted size: R, Ctrl+V of '80 50', Enter writes the rectangle", async ({ page, context }) => {
  const file = await freshFile(page, "e2e-paste");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.evaluate(() => navigator.clipboard.writeText("80 50"));
  await page.keyboard.press("r");
  await expect(page.getByTestId("tool-rect")).toHaveAttribute("data-active", "1");
  expect(await page.evaluate(() => document.activeElement?.tagName)).toBe("BODY");
  await page.keyboard.press("Control+V");                     // a real Ctrl+V, on the page
  await expect(page.getByTestId("typed")).toContainText("80 50");
  await page.keyboard.press("Enter");
  await idle(page);
  expect(shapes(file).map((s) => s.rect)).toEqual([[80, 50]]);

  // full-width digits, a times sign and a line end, pasted after a typed key
  await page.keyboard.press("r");
  await page.keyboard.type("6");
  await paste(page, "０ × ３０\n");
  await expect(page.getByTestId("typed")).toContainText("60 x 30");
  await page.keyboard.press("Enter");
  await idle(page);
  expect(shapes(file).map((s) => s.rect)).toEqual([[80, 50], [60, 30]]);

  // words in the clipboard are dropped, not typed
  await page.keyboard.press("c");
  await paste(page, "diameter: 25 mm");
  await expect(page.getByTestId("typed")).toContainText("25");
  expect((await page.getByTestId("typed").innerText()).trim()).toBe("25");
  await page.keyboard.press("Escape");
});

test("a real Ctrl+V in the typed box, and a paste in another field is that field's", async ({ page, context }) => {
  const file = await freshFile(page, "e2e-ctrlv");
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.evaluate(() => navigator.clipboard.writeText("44 22"));
  await page.keyboard.press("r");
  await page.getByTestId("typed").click();                    // the hidden field takes focus
  await expect(page.getByTestId("typed-input")).toBeFocused();
  await page.keyboard.press("Control+V");
  await expect(page.getByTestId("typed")).toContainText("44 22");
  await page.keyboard.press("Enter");                          // Enter from the field confirms
  await idle(page);
  expect(shapes(file).map((s) => s.rect)).toEqual([[44, 22]]);

  // with the rectangle tool on, the palette's own input keeps its paste
  await page.keyboard.press("r");
  await page.keyboard.press("s");
  const input = page.getByTestId("palette-input");
  await expect(input).toBeVisible();
  await input.focus();
  await page.keyboard.press("Control+V");
  await expect(input).toHaveValue("44 22");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("palette")).toHaveCount(0);
  expect((await page.getByTestId("typed").innerText()).trim()).toBe("");
  await page.keyboard.press("Escape");
});

test("an input method's text: insertText and a composition land in the typed box", async ({ page }) => {
  const file = await freshFile(page, "e2e-ime");
  // insertText (what an IME commit or a dictation sends: input events, no keys)
  await page.keyboard.press("r");
  await page.getByTestId("typed").click();
  await page.keyboard.insertText("７０　４０");                  // full-width, an ideographic space
  await expect(page.getByTestId("typed")).toContainText("70 40");
  await page.keyboard.press("Enter");
  await idle(page);
  expect(shapes(file).map((s) => s.rect)).toEqual([[70, 40]]);

  // a composition: nothing is taken while composing, the committed text at the end
  await page.keyboard.press("c");
  await page.getByTestId("typed").click();
  await page.evaluate(() => {
    const el = document.querySelector('[data-testid="typed-input"]') as HTMLInputElement;
    el.dispatchEvent(new CompositionEvent("compositionstart", { data: "", bubbles: true }));
    el.value = "３";
    el.dispatchEvent(new InputEvent("input", { data: "３", inputType: "insertCompositionText", isComposing: true, bubbles: true }));
    el.value = "３２";
    el.dispatchEvent(new InputEvent("input", { data: "３２", inputType: "insertCompositionText", isComposing: true, bubbles: true }));
  });
  expect((await page.getByTestId("typed").innerText()).trim()).toBe("");
  await page.evaluate(() => {
    const el = document.querySelector('[data-testid="typed-input"]') as HTMLInputElement;
    el.dispatchEvent(new CompositionEvent("compositionend", { data: "３２", bubbles: true }));
  });
  await expect(page.getByTestId("typed")).toContainText("32");
  // a tool key typed in the field goes back to the page: H switches the tool
  await page.keyboard.press("Backspace");
  await page.keyboard.press("Backspace");
  await page.keyboard.type("30");
  await expect(page.getByTestId("typed")).toContainText("30");
  await page.keyboard.press("Enter");
  await idle(page);
  const all = shapes(file);
  expect(all.map((s) => s.circle ?? s.rect)).toEqual([[70, 40], 30]);
  await page.keyboard.press("r");
  await page.getByTestId("typed").click();
  await page.keyboard.press("c");                              // from the field: the circle tool
  await expect(page.getByTestId("tool-circle")).toHaveAttribute("data-active", "1");
  await expect(page.getByTestId("typed-input")).not.toBeFocused();
  await page.keyboard.press("Escape");
});
