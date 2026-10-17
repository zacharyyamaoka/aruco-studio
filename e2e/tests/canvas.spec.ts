// M3.3 / ST-T-UI-1: a single marker, a 4 x 3 grid and a 5 x 7 ChArUco, each
// on its own target. Three tag groups with a pattern layer each; their ids
// equal /api/plan's for the same specs; and OpenCV reads each tag's ids off
// a screenshot of the 2D canvas (what you see is what the core planned).
import { expect, test } from "@playwright/test";
import path from "node:path";
import { API, SCREENS, add, choose, detect, fresh, idle, probe, shot, tab, type } from "./helpers";

test("three types on the canvas, ids as planned, read by OpenCV", async ({ page, request }) => {
  await fresh(page, "e2e-canvas");
  await add(page, "single");

  // a typed cols x rows needs a sketch profile (on a face REF's fit lays
  // out as many as fit): Advanced > Kind
  await add(page, "grid");
  await tab(page, "advanced");
  await choose(page, "target.kind", "profile");
  await tab(page, "marker");
  await choose(page, "target", "box");
  await type(page, "target.w_mm", "100");
  await type(page, "target.h_mm", "80");
  await page.locator('.tog:has(input[data-path="numbers.size:auto"])').click();
  await idle(page);
  await type(page, "numbers.size", "14");
  await type(page, "settings.force[0]", "4");
  await type(page, "settings.force[1]", "3");

  await add(page, "charuco");
  await tab(page, "advanced");
  await choose(page, "target.kind", "profile");
  await tab(page, "marker");
  await choose(page, "target", "box");
  await type(page, "target.w_mm", "120");
  await type(page, "target.h_mm", "160");
  await page.locator('.tog:has(input[data-path="numbers.size:auto"])').click();
  await idle(page);
  await type(page, "numbers.size", "12");
  await type(page, "numbers.square", "16");
  await type(page, "settings.force[0]", "5");
  await type(page, "settings.force[1]", "7");

  await page.keyboard.press("Escape");
  await page.getByTestId("arrange").click();          // the targets grew: a row again
  await idle(page);
  const groups = page.locator("g[data-tag]");
  await expect(groups).toHaveCount(3);
  for (const name of ["tag1", "board1", "charuco1"]) {
    await expect(page.locator(`g[data-tag="${name}"] [data-layer="pattern"]`)).toHaveCount(1);
    await expect(page.locator(`g[data-tag="${name}"]`)).toHaveAttribute("data-ok", "1");
  }
  await shot(page, "2d_three_types");

  const st = await probe(page);
  const tags = st.doc.tags;
  const byName: Record<string, any> = Object.fromEntries(st.tags.map((t: any) => [t.name, t]));
  for (const t of tags) {
    const r = await request.post(`${API}/api/plan`, { data: t.spec });
    const p = await r.json();
    expect(p.ok).toBeTruthy();
    expect(byName[t.name].ids).toEqual(p.ids);
    await expect(page.locator(`[data-ids-row="${t.name}"] td.idc`)).toHaveAttribute("data-ids", p.ids.join(","));
    if (t.name === "board1") expect([p.marker.cols, p.marker.rows]).toEqual([4, 3]);
    if (t.name === "charuco1") expect([p.marker.cols, p.marker.rows]).toEqual([5, 7]);
  }

  // OpenCV reads each tag off the canvas (axes and quiet zones hidden)
  await page.keyboard.press("a");
  await page.keyboard.press("q");
  for (const t of tags) {
    await page.locator(`[data-ids-row="${t.name}"]`).dblclick();
    await page.keyboard.press("Escape");
    await idle(page);
    const png = path.join(SCREENS, `2d_read_${t.name}.png`);
    await page.screenshot({ path: png });
    const box = (await page.locator(`g[data-tag="${t.name}"]`).boundingBox())!;
    const ids = detect(png, byName[t.name] ? (await (await request.post(`${API}/api/plan`, { data: t.spec })).json()).marker.dictionary : "DICT_4X4_50", box);
    expect(ids).toEqual([...byName[t.name].ids].sort((a: number, b: number) => a - b));
  }
});
