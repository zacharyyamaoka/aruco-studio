// What prints is what the canvas says (Zach, 2026-10-21, on arucostudio.com: a
// rectangle profile dimensioned 123.5 × 40 holding a 3 × 1 grid of 30 mm
// DICT_4X4_50, inkjet; "I am expecting 123.5 but it seems actually wider than
// that"). In the real app with the real core: the canvas's driven Outer W × H,
// the panel's summary and its Marker row say the sticker's size, and the
// Download PDF -- decoded here, its grey cut loop measured in points -- cuts
// exactly that, to 0.1 mm; under Trim Profile that is the profile. The quiet
// zone's edge, which prints nothing there, is a dashed guide, and the
// selection outlines the cut. Before the fix Outer read 112 × 40 (the
// marker's quiet-zone box) while the PDF cut 123.5 × 40.
import fs from "node:fs";
import zlib from "node:zlib";
import { expect, test, type Page } from "@playwright/test";
import { CORE, clickAt, coreReady, idle, openMenu, openStudio, panelTab, state } from "./helpers";

const SHOTS = process.env.E2E_SHOTS ?? "test-results/shots";
const PT_MM = 25.4 / 72;
const CUT_GREY = 0.55;           // core/sheet.py CUT_GREY: the cut line's stroke

const INKJET = {
  id: "builtin:inkjet-letter-vinyl", name: "Inkjet · Letter vinyl", builtin: true, min_cell_mm: 1.0, cell_step_mm: 0.0,
  method: "inkjet", page: "Letter", page_mm: [215.9, 279.4], margin_mm: 10.0, thickness_mm: 0.1, dpi: 600,
  size_step: { of: "mm", mm: 0.5 },
};

/** Zach's document: one 123.5 × 40 rectangle (its W and H typed), a 3 × 1 grid of DICT_4X4_50 from #19, Auto. */
function zachsDoc(trim: "profile" | "marker") {
  return {
    format: "arucostudio-web", version: 4, name: `Printdims ${trim}`,
    shapes: [{ kind: "rect", id: "r1", cx: 0, cy: 0, w: 123.5, h: 40, angle_deg: 0 }],
    dims: [{ id: "d1", kind: "w", shape: "r1", value: 123.5, at: [0, -26] }, { id: "d2", kind: "h", shape: "r1", value: 40, at: [70, 0] }],
    features: [{
      id: "f1", key: "f1", profile: { outer: "r1", holes: [] }, holes: "avoid", trim,
      marker: { type: "grid", dictionary: "DICT_4X4_50", first_id: 19, auto: true, marker_mm: 30, checker_mm: 0, separation_mm: 0,
        cols: 3, rows: 1, turn: 0, flip: false, quiet_modules: 1, corner_mark: "none" },
      label: { on: false, text: "#{ids}", height_mm: 0, side: "below", gap_mm: 2, offset_mm: [0, 0] },
      extrude: {}, preset: INKJET, set: ["marker.type", "marker.cols", "marker.first_id", ...(trim === "marker" ? ["trim"] : [])],
    }],
    id_ledger: { f1: 19 }, default_preset: INKJET,
  };
}

async function openDoc(page: Page, doc: object, name: string): Promise<void> {
  const file = test.info().outputPath(`${name}.arucostudio-web.json`);
  fs.mkdirSync(test.info().outputDir, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(doc));
  await openMenu(page, "file");
  const [chooser] = await Promise.all([page.waitForEvent("filechooser"), page.getByTestId("cmd-open").click()]);
  await chooser.setFiles(file);
  await idle(page);
}

/** The drawn read-only Outer dims: each one's value and its arrow-tip-to-tip length (client px). */
async function outerDims(page: Page): Promise<{ value: number; text: string; px: number; dx: number; dy: number }[]> {
  return page.locator('[data-testid="dims"] [data-dim="outer"]').evaluateAll((gs) => gs.map((g) => {
    const tip = (k: string): [number, number] => {
      const p = g.querySelector(`[data-tip="${k}"]`) as SVGPathElement;
      const pt = p.getPointAtLength(0), m = p.getScreenCTM()!;
      return [m.a * pt.x + m.c * pt.y + m.e, m.b * pt.x + m.d * pt.y + m.f];
    };
    const a = tip("a"), b = tip("b");
    return { value: Number(g.getAttribute("data-value")), text: g.querySelector("text")?.textContent ?? "",
      px: Math.hypot(b[0] - a[0], b[1] - a[1]), dx: Math.abs(b[0] - a[0]), dy: Math.abs(b[1] - a[1]) };
  }));
}

async function clientBox(page: Page, sel: string): Promise<{ w: number; h: number }> {
  const b = (await page.locator(sel).boundingBox())!;
  return { w: b.width, h: b.height };
}

/** The cut loops in a PDF, decoded from its bytes: each page's FlateDecode
 *  content stream, the grey stroked closed paths (core/sheet.py _pdf_ops:
 *  "<grey> G <width> w", then "x y m", "x y l", ..., "h", "S"), in mm. */
function pdfCutSizes(file: string): { w: number; h: number }[] {
  const pdf = fs.readFileSync(file);
  const out: { w: number; h: number }[] = [];
  let at = 0;
  for (;;) {
    const s = pdf.indexOf("stream\n", at);
    if (s < 0) break;
    const e = pdf.indexOf("\nendstream", s);
    // the text's literal strings out first: a word in a label is no operator
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
  // the Download menu (printsel, 2026-10-21); a build before it had the button alone
  if (await page.getByTestId("print-download").count()) await page.getByTestId("print-download").click();
  const [dl] = await Promise.all([page.waitForEvent("download"), page.getByTestId("print-pdf").click()]);
  const file = test.info().outputPath(dl.suggestedFilename());
  await dl.saveAs(file);
  return file;
}

async function selectMarker(page: Page): Promise<void> {
  const s = await state(page);
  const plan = s.plans[s.doc.features[0].id];
  const lp: number[][] = plan.black[0].outer;
  await clickAt(page, lp.reduce((a, p) => a + p[0], 0) / lp.length, lp.reduce((a, p) => a + p[1], 0) / lp.length);
  await idle(page);
  await expect.poll(async () => (await state(page)).sel).toMatchObject({ kind: "feature", id: s.doc.features[0].id });
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await panelTab(page, "marker");
  await idle(page);
}

test.describe(`printed size = shown size (${CORE} core)`, () => {
  test.skip(CORE === "mock", "the mock core prints no cut");

  for (const [trim, want] of [["profile", [123.5, 40]], ["marker", [112, 40]]] as const) {
    test(`Zach's 123.5 × 40 grid, Trim ${trim}: Outer, the summary, the Marker row and the PDF's cut all say ${want[0]} × ${want[1]}`, async ({ page }) => {
      await openStudio(page);
      await coreReady(page);
      await openDoc(page, zachsDoc(trim), `zach-${trim}`);
      await selectMarker(page);
      const s = await state(page);
      expect(s.plan.ids).toEqual([19, 20, 21]);
      expect([s.plan.marker_mm, s.plan.separation_mm]).toEqual([30, 6]);
      const z = s.camera.zoom;

      // the canvas: Outer W × H, each as long as it reads
      const outer = await outerDims(page);
      expect(outer, "two Outer dims are drawn").toHaveLength(2);
      const w = outer.find((d) => d.dx > d.dy)!, h = outer.find((d) => d.dy > d.dx)!;
      expect([w.value, h.value], "Outer reads the sticker's size").toEqual([...want]);
      expect([Number(w.text), Number(h.text)]).toEqual([...want]);
      expect(Math.abs(w.px / z - want[0]), "Outer W is as long as it reads").toBeLessThan(0.1);
      expect(Math.abs(h.px / z - want[1]), "Outer H is as long as it reads").toBeLessThan(0.1);
      // the white drawn is the sticker too
      const white = await clientBox(page, '[data-cut-white="f1"]');
      expect(Math.abs(white.w / z - want[0])).toBeLessThan(0.1);
      expect(Math.abs(white.h / z - want[1])).toBeLessThan(0.1);
      // the quiet zone's edge: a guide when it is not the cut, and the selection outlines the cut
      const outline = page.locator('[data-marker="f1"] [data-marker-outline]');
      if (trim === "profile") {
        await expect(outline).toHaveAttribute("data-guide", "1");
        expect(await outline.evaluate((e) => getComputedStyle(e).strokeDasharray)).not.toBe("none");
        const sel = await clientBox(page, '[data-cut-sel="f1"]');
        expect(Math.abs(sel.w - white.w)).toBeLessThan(3);
        expect(Math.abs(sel.h - white.h)).toBeLessThan(3);
      } else {
        await expect(outline).toHaveAttribute("data-guide", "0");
        await expect(page.locator('[data-cut-sel="f1"]')).toHaveCount(0);
      }
      // the panel: the summary and the Marker row
      await expect(page.locator(".summary-line")).toContainText(`outer ${want[0].toFixed(1)} × ${want[1].toFixed(1)} mm`);
      await expect(page.locator('[data-issues-for="marker.marker_mm"]')).toContainText(`sticker ${want[0].toFixed(1)} × ${want[1].toFixed(1)} mm`);
      await page.screenshot({ path: `${SHOTS}/printdims-canvas-${trim}.png` });

      // the PDF: one cut, that size
      const cuts = pdfCutSizes(await downloadPdf(page));
      expect(cuts, "one sticker, one cut loop").toHaveLength(1);
      expect(Math.abs(cuts[0].w - want[0]), `the PDF cuts ${cuts[0].w.toFixed(3)} wide`).toBeLessThan(0.1);
      expect(Math.abs(cuts[0].h - want[1]), `the PDF cuts ${cuts[0].h.toFixed(3)} high`).toBeLessThan(0.1);
      expect(Math.abs(cuts[0].w - w.value)).toBeLessThan(0.1);
      expect(Math.abs(cuts[0].h - h.value)).toBeLessThan(0.1);
    });
  }
});
