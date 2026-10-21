// The 3D view's white is the sticker as it is cut (Zach, 2026-10-21; the
// printdims lane found it): with Trim = Marker the 2D white and the print
// cut follow the marker's quiet-zone box -- a 123.5 x 40 rectangle profile
// holding a 3 x 1 grid of 30 mm markers cuts 112 x 40 -- but the 3D white
// tile stayed at the full profile, 123.5 wide, and a label outside the
// marker floated off it. In the real app with the real core: for both trims,
// on a 3D-print preset (a white tile) and on an inkjet one (the paper), the
// white's bounding box as three.js has it (the probe's `whites`, read off the
// meshes) is the 2D cut's box (the plan's cut_shape, which is what the canvas
// fills white), and on an inkjet preset the PDF's cut loop is that size.
// Screenshots (1280 x 800) go to TRIM3D_SHOTS (default test-results/trim3d).
import fs from "node:fs";
import zlib from "node:zlib";
import { expect, test, type Page } from "@playwright/test";
import { CORE, coreReady, idle, openMenu, openStudio, state } from "./helpers";

const SHOTS = process.env.TRIM3D_SHOTS ?? "test-results/trim3d";
const TOL_MM = 0.05;
const PT_MM = 25.4 / 72;
const CUT_GREY = 0.55;           // core/sheet.py CUT_GREY: the cut line's stroke

const PRINT3D = { id: "builtin:default", name: "Default", builtin: true, min_cell_mm: 2.0, cell_step_mm: 0.0, method: "print3d", nozzle_mm: 0.6, line_mm: 0.675, layer_mm: 0.0, first_layer_mm: 0.0 };
const INKJET = {
  id: "builtin:inkjet-letter-vinyl", name: "Inkjet · Letter vinyl", builtin: true, min_cell_mm: 1.0, cell_step_mm: 0.0,
  method: "inkjet", page: "Letter", page_mm: [215.9, 279.4], margin_mm: 10.0, thickness_mm: 0.1, dpi: 600,
  size_step: { of: "mm", mm: 0.5 },
};

type Marker = { name: string; w: number; h: number; marker: Record<string, unknown> };
const MARKERS: Marker[] = [
  { name: "single", w: 60, h: 45, marker: { type: "single", first_id: 0, marker_mm: 0, cols: 1, rows: 1 } },
  { name: "grid 3x1 in 123.5 x 40", w: 123.5, h: 40, marker: { type: "grid", first_id: 19, marker_mm: 30, cols: 3, rows: 1 } },
  { name: "charuco 4x3", w: 80, h: 60, marker: { type: "charuco", first_id: 0, marker_mm: 0, cols: 4, rows: 3 } },
];
type Label = { name: string; label: Record<string, unknown> };
const LABELS: Label[] = [
  { name: "no label", label: { on: false } },
  { name: "label outside (below)", label: { on: true, place: "outside", side: "below" } },
];

function doc(m: Marker, label: Label, trim: "profile" | "marker", preset: object) {
  return {
    format: "arucostudio-web", version: 4, name: `Trim3d ${m.name} ${trim}`,
    shapes: [{ kind: "rect", id: "r1", cx: 0, cy: 0, w: m.w, h: m.h, angle_deg: 0 }],
    dims: [{ id: "d1", kind: "w", shape: "r1", value: m.w, at: [0, -m.h / 2 - 6] }, { id: "d2", kind: "h", shape: "r1", value: m.h, at: [m.w / 2 + 10, 0] }],
    features: [{
      id: "f1", key: "f1", profile: { outer: "r1", holes: [] }, holes: "avoid", trim,
      marker: { dictionary: "DICT_4X4_50", auto: true, checker_mm: 0, separation_mm: 0, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none", ...m.marker },
      label: { text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0], ...label.label },
      extrude: {}, preset, set: ["marker.type", "marker.cols", "marker.first_id", ...(trim === "marker" ? ["trim"] : [])],
    }],
    id_ledger: { f1: Number(m.marker.first_id) }, default_preset: preset,
  };
}

async function openDoc(page: Page, d: object, name: string): Promise<void> {
  const file = test.info().outputPath(`${name}.arucostudio-web.json`);
  fs.mkdirSync(test.info().outputDir, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(d));
  await openMenu(page, "file");
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
  await chooser.setFiles(file);
  await idle(page);
}

type Box = [number, number, number, number];
const boxOf = (pts: number[][]): Box => [Math.min(...pts.map((p) => p[0])), Math.min(...pts.map((p) => p[1])), Math.max(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[1]))];

/** The 3D white's box as three.js has it (the probe), once the solids are drawn. */
async function white3d(page: Page): Promise<Box> {
  await expect.poll(async () => page.evaluate(() => (window as any).__aruco.view3d()?.whites?.f1 ?? null), { message: "the 3D white is drawn" }).not.toBeNull();
  return page.evaluate(() => (window as any).__aruco.view3d().whites.f1);
}

/** The PDF's cut loops' sizes: each page's FlateDecode content stream, the grey stroked closed paths (core/sheet.py _pdf_ops), mm. */
function pdfCutSizes(file: string): { w: number; h: number }[] {
  const pdf = fs.readFileSync(file);
  const out: { w: number; h: number }[] = [];
  let at = 0;
  for (;;) {
    const s = pdf.indexOf("stream\n", at);
    if (s < 0) break;
    const e = pdf.indexOf("\nendstream", s);
    const body = zlib.inflateSync(pdf.subarray(s + 7, e)).toString("latin1").replace(/\((?:\\.|[^\\)])*\)/g, " ");
    let grey: number | null = null, stack: string[] = [], subs: [number, number][][] = [];
    for (const tok of body.split(/\s+/)) {
      if (tok === "m" || tok === "l") {
        const y = Number(stack.pop()), x = Number(stack.pop());
        if (tok === "m") subs.push([]);
        subs[subs.length - 1].push([x * PT_MM, y * PT_MM]);
        stack = [];
      } else if (tok === "G") { grey = Number(stack.pop()); stack = []; }
      else if (tok === "S" || tok === "f" || tok === "f*") {
        const loops = subs.filter((sp) => sp.length >= 3);
        if (tok === "S" && grey !== null && Math.abs(grey - CUT_GREY) < 1e-9 && loops.length) {
          const sizes = loops.map((lp) => {
            const xs = lp.map((p) => p[0]), ys = lp.map((p) => p[1]);
            return { w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
          });
          out.push(sizes.reduce((p, q) => (q.w * q.h > p.w * p.h ? q : p)));
        }
        subs = []; stack = [];
      } else if (["BT", "ET", "h", "w", "g", "re", "Tf", "Td", "Tm", "Tj"].includes(tok)) stack = [];
      else stack.push(tok);
    }
    at = e + 10;
  }
  return out;
}

async function downloadPdf(page: Page): Promise<string> {
  await page.getByTestId("act-print").click();
  await expect(page.getByTestId("print-dialog")).toBeVisible();
  await expect(page.locator('[data-testid="print-page"] svg path[data-cut]').first()).toBeVisible({ timeout: 60_000 });
  await idle(page);
  if (await page.getByTestId("print-download").count()) await page.getByTestId("print-download").click();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("print-pdf").click()]);
  const file = test.info().outputPath(dl.suggestedFilename());
  await dl.saveAs(file);
  return file;
}

test.describe(`the 3D white is the cut (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core plans no cut");

  for (const [presetName, preset] of [["3D print (the tile)", PRINT3D], ["inkjet (the paper)", INKJET]] as const) {
    for (const m of MARKERS) {
      for (const label of LABELS) {
        test(`${presetName}, ${m.name}, ${label.name}: Trim Profile and Trim Marker, the 3D white is the 2D cut within ${TOL_MM} mm`, async ({ page }) => {
          await openStudio(page);
          await coreReady(page);
          const cuts: Record<string, Box> = {};
          for (const trim of ["profile", "marker"] as const) {
            await openDoc(page, doc(m, label, trim, preset), `${trim}`);
            const s = await state(page);
            expect(s.doc.features[0].trim).toBe(trim);
            const plan = s.plans.f1;
            expect(plan?.ok, "planned").toBe(true);
            // the 2D cut: what the canvas fills white and the sheet cuts
            const cut = boxOf(plan.cut_shape.outer);
            cuts[trim] = cut;
            // a reopened file may keep the 3D view: only press 3 from 2D
            if (!(await page.getByTestId("view3d").count())) await page.keyboard.press("3");
            await expect(page.getByTestId("view3d")).toBeVisible();
            const w3 = await white3d(page);
            // the view top-down on the sticker, the arrows and boxes out: what Zach looks at
            if (!label.label.on && (m.name.startsWith("grid") || m.name === "single") && preset === PRINT3D) {
              await page.evaluate(() => (window as any).__aruco.top3d(false));
              await idle(page);
              await page.screenshot({ path: `${SHOTS}/3d-${m.name.split(" ")[0]}-${trim}.png` });
            }
            for (let k = 0; k < 4; k++) expect(Math.abs(w3[k] - cut[k]), `Trim ${trim}: 3D white ${w3.map((v) => v.toFixed(3))} vs the 2D cut ${cut.map((v) => v.toFixed(3))}`).toBeLessThanOrEqual(TOL_MM);
            // the PDF's cut (an inkjet sticker): the same size, the page may turn it
            if (preset === INKJET) {
              await page.keyboard.press("3");   // the 2D | 3D toggle: back to 2D, where Print is
              await expect(page.getByTestId("view3d")).toHaveCount(0);
              const pdf = pdfCutSizes(await downloadPdf(page));
              expect(pdf, "one sticker, one cut loop").toHaveLength(1);
              const [pw, ph] = [pdf[0].w, pdf[0].h].sort((a, b) => a - b), [cw, ch] = [w3[2] - w3[0], w3[3] - w3[1]].sort((a, b) => a - b);
              expect(Math.abs(pw - cw), `Trim ${trim}: the PDF cuts ${pdf[0].w.toFixed(3)} x ${pdf[0].h.toFixed(3)}, the 3D white is ${(w3[2] - w3[0]).toFixed(3)} x ${(w3[3] - w3[1]).toFixed(3)}`).toBeLessThanOrEqual(TOL_MM);
              expect(Math.abs(ph - ch)).toBeLessThanOrEqual(TOL_MM);
              await page.keyboard.press("Escape");
              await expect(page.getByTestId("print-dialog")).toHaveCount(0);
            }
          }
          // Trim Marker is the narrower: the quiet-zone box sits inside the profile
          expect(cuts.marker[2] - cuts.marker[0], "the marker's cut is not wider than the profile's").toBeLessThanOrEqual(cuts.profile[2] - cuts.profile[0] + TOL_MM);
        });
      }
    }
  }
});
