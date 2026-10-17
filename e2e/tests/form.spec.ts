// M8b2.2: the inspector's form comes from /api/form alone (plan/fields.py,
// bam.form/1): its tabs, the icons of its choices, which rows show
// (show_when) and where a hidden row's message goes (anchor). layout.ts is
// gone. The expected rows are worked out here from the server's field list
// with the kit's own pure rules (formModel.ts), then read off the DOM.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { visibleRows, type FormCtx, type FormRow } from "../../studio/packages/bam-ui/src/formModel";
import { API, ROOT, add, choose, freshFile, idle, issueTexts, probe, sceneTags, shot, tab } from "./helpers";

const getPath = (o: any, p: string) => p.split(".").reduce((x, k) => (x == null ? undefined : x[k]), o);

function ctxOf(t: any): FormCtx {
  const tg = t.spec.target;
  const flags = [tg.kind, tg.has_body ? "body" : "free", ...((tg.loops_mm ?? []).length > 1 ? ["holes"] : [])];
  return { get: (p) => getPath(t.spec, p), layout: t.spec.settings.layout ?? "single", made_by: t.plan?.made_by ?? "print3d", target: flags };
}

/** The rows of each tab on screen (the Studio's own rows left out). */
async function domRows(page: Page): Promise<string[]> {
  return page.locator("[data-tab-body] [data-row]").evaluateAll((els) => els.map((e) => e.getAttribute("data-row") || "")
    .filter((p) => p !== "fit" && !p.startsWith("printinfo.")));
}

test("M8b2.2 tabs, icons, visibility and anchors from /api/form", async ({ page }) => {
  expect(fs.existsSync(path.join(ROOT, "studio", "src", "inspector", "layout.ts"))).toBeFalsy();
  for (const f of ["Inspector.tsx", "PresetRow.tsx"]) {
    const src = fs.readFileSync(path.join(ROOT, "studio", "src", "inspector", f), "utf-8");
    expect(src).not.toMatch(/BY_GROUP|BY_PATH|ICONS_OF|TABS\s*[:=]/);
  }
  const form = await (await page.request.get(`${API}/api/form`)).json();
  expect(form.contract).toBe("bam.form/1");
  const rows: FormRow[] = form.fields.filter((f: any) => f.path !== "settings.make.by");
  await freshFile(page, "e2e-form");
  await add(page, "grid");
  const name = (await probe(page)).sel[0];
  let t = (await sceneTags(page.request)).find((x) => x.name === name);
  const vis = visibleRows(rows, ctxOf(t));
  // the tabs: the server's, in its order, those with a row to show; each its icon and name
  const want = form.tabs.filter((x: any) => vis.some((r) => r.tab === x.id));
  const got = await page.locator('[role="tab"][data-tab]').evaluateAll((els) => els.map((e) => ({
    id: e.getAttribute("data-tab"), icon: e.querySelector("[data-icon]")?.getAttribute("data-icon"), name: e.textContent?.trim() })));
  expect(got).toEqual(want.map((x: any) => ({ id: x.id, icon: x.icon, name: x.name })));
  // each tab's rows: exactly the shown rows of that tab, in the list's order
  for (const x of want) {
    await tab(page, x.id);
    expect(await domRows(page), x.id).toEqual(vis.filter((r) => r.tab === x.id).map((r) => r.path));
  }
  // the root rows (above the tabs) come from the list too
  const rootRows = vis.filter((r) => r.tab === "root").map((r) => r.path);
  for (const p of rootRows) await expect(page.locator(`.kit-form-root [data-row="${p}"]`)).toHaveCount(1);
  // a choice's icon is the field's: the Type row shows the grid glyph
  const layoutRow = form.fields.find((f: any) => f.path === "settings.layout");
  const gridIcon = layoutRow.choices.find((c: any) => c.value === "grid").icon;
  await tab(page, "marker");
  await expect(page.locator('.kit-select[data-path="settings.layout"] .kit-select-trigger [data-icon]')).toHaveAttribute("data-icon", gridIcon);
  // the Origin row's glyphs are the field's icons_by_layout for a grid
  const turn = form.fields.find((f: any) => f.path === "settings.turn");
  const icons = await page.locator('.kit-seg[data-path="settings.turn"] [data-icon]').evaluateAll((els) => els.map((e) => e.getAttribute("data-icon")));
  expect(icons.sort()).toEqual(Object.values(turn.icons_by_layout.grid).sort());

  // show_when.made_by = ["sticker"]: hidden on this 3D tag
  const stickerOnly = form.fields.filter((f: any) => (f.show_when?.made_by ?? []).join() === "sticker").map((f: any) => f.path);
  expect(stickerOnly).toContain("settings.make.thickness_mm");
  for (const x of want) {
    await tab(page, x.id);
    for (const p of stickerOnly) await expect(page.locator(`[data-row="${p}"]`)).toHaveCount(0);
  }
  // show_when.values: Operation shows only with Colours = White + black
  await tab(page, "heights");
  await expect(page.locator('[data-row="settings.op"]')).toHaveCount(vis.some((r) => r.path === "settings.op") ? 1 : 0);
  await choose(page, "settings.mode", "both");
  await expect(page.locator('[data-row="settings.op"]')).toHaveCount(1);
  await shot(page, "m8b2_form_heights");

  // a hidden row's message goes under its anchor: Holes is hidden (no hole
  // in this plate) and its junk value's warning shows under the anchor's row
  const holes = form.fields.find((f: any) => f.path === "settings.holes");
  expect(holes.show_when.target).toEqual(["holes"]);
  const r = await page.request.patch(`${API}/api/scene/tags/${encodeURIComponent(name)}`, { data: { settings: { holes: "maybe" } } });
  expect(r.ok()).toBeTruthy();
  await page.evaluate(() => (window as any).__studio.store.getState().refresh());
  await idle(page);
  t = (await sceneTags(page.request)).find((x) => x.name === name);
  expect(t.plan.warnings.some((w: any) => w.field === "settings.holes" && w.level === "warn")).toBeTruthy();
  await tab(page, "marker");
  await expect(page.locator('[data-row="settings.holes"]')).toHaveCount(0);
  const anchor = holes.anchor;
  await expect(page.locator(`[data-issues-for="${anchor}"] .issue[data-field="settings.holes"]`)).toHaveCount(1);
  expect((await issueTexts(page, anchor)).some((x) => /holes 'maybe'/.test(x))).toBeTruthy();
  await shot(page, "m8b2_form_anchor");
});
