// A crude stand-in for the Python core (?core=mock), so the screen can be
// built and tested before the Pyodide worker lands. It implements CoreApi
// with toy geometry: black squares with a few cells, plausible issues and
// suggestions. Never the default: web/src/coreSource.ts picks the real core.
import type {
  CoreApi, CoreInfo, Issue, Loop, MarkerPlan, PlanRequest, Polygon, Preset, Profile, Rect, Sheet, SheetRequest, Suggestion, Vec2,
} from "../core/contract";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const DICTS = [
  ["DICT_4X4_50", 50, 4], ["DICT_4X4_100", 100, 4], ["DICT_4X4_250", 250, 4], ["DICT_4X4_1000", 1000, 4],
  ["DICT_5X5_50", 50, 5], ["DICT_5X5_100", 100, 5], ["DICT_5X5_250", 250, 5], ["DICT_5X5_1000", 1000, 5],
  ["DICT_6X6_50", 50, 6], ["DICT_6X6_250", 250, 6], ["DICT_7X7_50", 50, 7], ["DICT_APRILTAG_36h11", 587, 6],
] as const;

const PRESETS: Preset[] = [
  { id: "builtin:inkjet-letter", name: "Inkjet · Letter vinyl", method: "inkjet", builtin: true, page: "Letter", page_mm: [215.9, 279.4],
    margin_mm: 6.35, thickness_mm: 0.1, dpi: 600, min_cell_mm: 1, cell_step_mm: 0 },
  { id: "builtin:inkjet-a4", name: "Inkjet · A4 vinyl", method: "inkjet", builtin: true, page: "A4", page_mm: [210, 297],
    margin_mm: 5, thickness_mm: 0.1, dpi: 600, min_cell_mm: 1, cell_step_mm: 0 },
  { id: "builtin:print3d-04", name: "3D print · 0.4 nozzle", method: "print3d", builtin: true, nozzle_mm: 0.4, line_mm: 0.45,
    first_line_mm: 0.5, layer_mm: 0.2, first_layer_mm: 0.2, bed_mm: [250, 210], min_cell_mm: 1.8, cell_step_mm: 0.45 },
  { id: "builtin:print3d-06", name: "3D print · 0.6 nozzle", method: "print3d", builtin: true, nozzle_mm: 0.6, line_mm: 0.675,
    first_line_mm: 0.675, layer_mm: 0.32, first_layer_mm: 0.32, bed_mm: [250, 210], min_cell_mm: 2.7, cell_step_mm: 0.675 },
];

function bitsOf(dict: string): number {
  return (DICTS.find((d) => d[0] === dict)?.[2] as number) ?? 4;
}
function capacityOf(dict: string): number {
  return (DICTS.find((d) => d[0] === dict)?.[1] as number) ?? 50;
}

const r2 = (v: number) => Math.round(v * 100) / 100;

/** The sizes in the marker's own frame: marker, checker, separation, outer. */
function sizes(req: PlanRequest) {
  const m = req.marker;
  const n = bitsOf(m.dictionary) + 2;
  const q = m.quiet_modules / n;          // quiet zone per marker side, in markers
  const cols = m.type === "single" ? 1 : m.cols, rows = m.type === "single" ? 1 : m.rows;
  const W = req.rect.w, H = req.rect.h;
  const turned = m.turn === 90 || m.turn === 270;
  const [fw, fh] = turned ? [H, W] : [W, H];
  let marker = m.marker_mm, checker = 0, sep = 0;
  if (m.type === "charuco") {
    checker = m.auto ? Math.min(fw / (cols + 2 * q), fh / (rows + 2 * q)) : m.checker_mm || m.marker_mm / 0.75;
    marker = m.auto || !m.marker_mm ? checker * 0.75 : m.marker_mm;
    const cell = marker / n;
    return { marker, checker, sep, cell, outer: [cols * checker + 2 * cell * m.quiet_modules, rows * checker + 2 * cell * m.quiet_modules] as Vec2, cols, rows };
  }
  const sepRatio = m.separation_mm > 0 ? 0 : 0.25;
  if (m.auto) {
    const fit = (len: number, k: number) => (len - (k - 1) * (m.separation_mm || 0)) / (k + (k - 1) * sepRatio + 2 * q);
    marker = Math.min(fit(fw, cols), fit(fh, rows));
  }
  sep = m.type === "grid" ? (m.separation_mm > 0 ? m.separation_mm : marker * sepRatio) : 0;
  const cell = marker / n;
  const outer: Vec2 = [cols * marker + (cols - 1) * sep + 2 * cell * m.quiet_modules, rows * marker + (rows - 1) * sep + 2 * cell * m.quiet_modules];
  return { marker, checker, sep, cell, outer, cols, rows };
}

/** A toy bit pattern: the same id always gives the same cells. */
function bits(id: number, n: number): boolean[] {
  let s = (id + 1) * 2654435761 >>> 0;
  const out: boolean[] = [];
  for (let i = 0; i < n * n; i++) {
    s = (s * 1103515245 + 12345) >>> 0;
    out.push(((s >> 16) & 1) === 1);
  }
  return out;
}

function sq(x0: number, y0: number, s: number): Loop {
  return [[x0, y0], [x0 + s, y0], [x0 + s, y0 + s], [x0, y0 + s]];
}

function markerPolys(id: number, x0: number, y0: number, size: number, b: number): Polygon {
  const n = b + 2, c = size / n;
  const pat = bits(id, b);
  const holes: Loop[] = [];
  for (let i = 0; i < b; i++) for (let j = 0; j < b; j++) {
    if (!pat[i * b + j]) continue;
    holes.push([...sq(x0 + (j + 1) * c, y0 + (b - i) * c, c)].reverse());
  }
  return { outer: sq(x0, y0, size), holes };
}

function place(req: PlanRequest, p: Vec2): Vec2 {
  const m = req.marker, r = req.rect;
  let [u, v] = p;
  if (m.flip && !req.reference_face) u = -u;
  const t = (m.turn * Math.PI) / 180;
  [u, v] = [u * Math.cos(t) - v * Math.sin(t), u * Math.sin(t) + v * Math.cos(t)];
  const a = (r.angle_deg * Math.PI) / 180;
  return [r2(r.cx + u * Math.cos(a) - v * Math.sin(a)) , r2(r.cy + u * Math.sin(a) + v * Math.cos(a))];
}

function resolveText(t: string, ids: number[], req: PlanRequest): string {
  const range = ids.length > 1 ? `${ids[0]}-${ids[ids.length - 1]}` : String(ids[0]);
  return t.replace(/\{id\}/g, String(ids[0])).replace(/\{first\}/g, String(ids[0])).replace(/\{last\}/g, String(ids[ids.length - 1]))
    .replace(/\{ids\}/g, range).replace(/\{dict\}/g, req.marker.dictionary.replace("DICT_", "")).replace(/\{type\}/g, req.marker.type);
}

function planOf(req: PlanRequest): MarkerPlan {
  const m = req.marker, r = req.rect;
  const z = sizes(req);
  const b = bitsOf(m.dictionary);
  const black: Polygon[] = [];
  const ids: number[] = [];
  const [ow, oh] = z.outer;
  const quiet = z.cell * m.quiet_modules;
  const x0 = -ow / 2 + quiet, y0 = -oh / 2 + quiet;
  const local: Polygon[] = [];
  if (m.type === "charuco") {
    let id = m.first_id;
    for (let row = 0; row < z.rows; row++) for (let col = 0; col < z.cols; col++) {
      const sx = x0 + col * z.checker, sy = y0 + (z.rows - 1 - row) * z.checker;
      if ((row + col) % 2 === 0) local.push({ outer: sq(sx, sy, z.checker), holes: [] });
      else {
        const off = (z.checker - z.marker) / 2;
        ids.push(id);
        local.push(markerPolys(id++, sx + off, sy + off, z.marker, b));
      }
    }
  } else {
    let id = m.first_id;
    for (let row = 0; row < z.rows; row++) for (let col = 0; col < z.cols; col++) {
      ids.push(id);
      local.push(markerPolys(id++, x0 + col * (z.marker + z.sep), y0 + (z.rows - 1 - row) * (z.marker + z.sep), z.marker, b));
    }
  }
  if (m.corner_mark === "triangle") local.push({ outer: [[-ow / 2, oh / 2 - quiet], [-ow / 2 + quiet, oh / 2], [-ow / 2, oh / 2]], holes: [] });
  for (const p of local) black.push({ outer: p.outer.map((q) => place(req, q)), holes: p.holes.map((h) => h.map((q) => place(req, q))) });
  const outer = ([[-ow / 2, -oh / 2], [ow / 2, -oh / 2], [ow / 2, oh / 2], [-ow / 2, oh / 2]] as Vec2[]).map((q) => place(req, q));
  const turned = m.turn === 90 || m.turn === 270;
  const [dw, dh] = turned ? [oh, ow] : [ow, oh];
  const overflow = Math.max(0, r2((dw - r.w) / 2), r2((dh - r.h) / 2));
  const warnings: Issue[] = [];
  if (overflow > 0) warnings.push({ field: "marker.marker_mm", level: "error",
    text: `The marker is ${r2(overflow)} mm past the rectangle on each side (outer ${r2(ow)} × ${r2(oh)} mm in ${r2(r.w)} × ${r2(r.h)} mm)` });
  if (req.preset.min_cell_mm && z.cell < req.preset.min_cell_mm) warnings.push({ field: "marker.marker_mm", level: "warn",
    text: `cells ${r2(z.cell)} mm: under this preset's ${req.preset.min_cell_mm} mm` });
  if (ids[ids.length - 1] >= capacityOf(m.dictionary)) warnings.push({ field: "marker.first_id", level: "error",
    text: `ids up to ${ids[ids.length - 1]}: ${m.dictionary} has ${capacityOf(m.dictionary)}` });
  if (m.type === "grid" && m.separation_mm > 0 && m.separation_mm < z.cell) warnings.push({ field: "marker.separation_mm", level: "warn",
    text: `a gap under one cell (${r2(z.cell)} mm) can merge markers` });
  if (req.label.on && req.label.height_mm > 0 && req.label.height_mm < 2) warnings.push({ field: "label.height_mm", level: "warn",
    text: "text under 2 mm is hard to read" });
  let label: MarkerPlan["label"] = null;
  if (req.label.on) {
    const h = req.label.height_mm || Math.max(2.5, Math.min(8, Math.min(r.w, r.h) * 0.1));
    const g = req.label.gap_mm + h / 2;
    const at: Vec2 = req.label.side === "below" ? [r.cx, r.cy - r.h / 2 - g] : req.label.side === "above" ? [r.cx, r.cy + r.h / 2 + g]
      : req.label.side === "left" ? [r.cx - r.w / 2 - g - h, r.cy] : [r.cx + r.w / 2 + g + h, r.cy];
    label = { text: resolveText(req.label.text, ids, req), at: [r2(at[0] + req.label.offset_mm[0]), r2(at[1] + req.label.offset_mm[1])], height_mm: r2(h), angle_deg: r.angle_deg };
  }
  // the Joint Origin: x along the marker's turned u, y along v; the centre
  // of a single marker, the bottom-left of a board's black
  const t = ((m.turn + r.angle_deg) * Math.PI) / 180, fl = m.flip && !req.reference_face ? -1 : 1;
  const c = Math.cos(t), s = Math.sin(t);
  const o = m.type === "single" ? [r.cx, r.cy] : place(req, [x0, y0]);
  const origin = [fl * c, -s, 0, o[0], fl * s, c, 0, o[1], 0, 0, fl, 0, 0, 0, 0, 1];
  const kind = m.type === "single" ? "Single" : m.type === "grid" ? `Grid ${z.cols}×${z.rows}` : `ChArUco ${z.cols}×${z.rows}`;
  const idTxt = ids.length > 1 ? `#${ids[0]}–${ids[ids.length - 1]}` : `#${ids[0]}`;
  return {
    ok: !warnings.some((w) => w.level === "error"), ids, black, outer, outer_mm: [r2(ow), r2(oh)], marker_mm: r2(z.marker),
    checker_mm: r2(z.checker), separation_mm: r2(z.sep), cols: z.cols, rows: z.rows, cell_mm: r2(z.cell), auto: m.auto,
    overflow_mm: overflow, origin, label, warnings,
    summary: `${kind} ${m.dictionary} ${idTxt} · ${r2(z.marker)} mm · outer ${r2(ow)} × ${r2(oh)} mm (mock core)`,
  };
}

/** The largest clear axis-aligned rectangle, on a sampled grid (crude). */
function inscribeOf(profile: Profile, holes: "avoid" | "ignore"): Rect | null {
  const [outer, ...hs] = profile.loops;
  if (!outer || outer.length < 3) return null;
  const inLoop = (loop: Loop, x: number, y: number) => {
    let ins = false;
    for (let i = 0, j = loop.length - 1; i < loop.length; j = i++) {
      const [xi, yi] = loop[i], [xj, yj] = loop[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) ins = !ins;
    }
    return ins;
  };
  const xs = outer.map((p) => p[0]), ys = outer.map((p) => p[1]);
  const X0 = Math.min(...xs), X1 = Math.max(...xs), Y0 = Math.min(...ys), Y1 = Math.max(...ys);
  const N = 60, dx = (X1 - X0) / N, dy = (Y1 - Y0) / N;
  const free = (i: number, j: number) => {
    for (const [fx, fy] of [[0, 0], [1, 0], [0, 1], [1, 1], [0.5, 0.5]]) {
      const x = X0 + (i + fx) * dx, y = Y0 + (j + fy) * dy;
      if (!inLoop(outer, x, y)) return false;
      if (holes === "avoid" && hs.some((h) => inLoop(h, x, y))) return false;
    }
    return true;
  };
  const height = new Array(N).fill(0);
  let best = { a: 0, i0: 0, i1: 0, j0: 0, j1: 0 };
  for (let j = 0; j < N; j++) {
    for (let i = 0; i < N; i++) height[i] = free(i, j) ? height[i] + 1 : 0;
    for (let i = 0; i < N; i++) {
      let h = Infinity;
      for (let k = i; k < N && height[k] > 0; k++) {
        h = Math.min(h, height[k]);
        const a = (k - i + 1) * dx * h * dy;
        if (a > best.a) best = { a, i0: i, i1: k + 1, j0: j - h + 1, j1: j + 1 };
      }
    }
  }
  if (!best.a) return null;
  const m = Math.min(dx, dy) * 0.5;
  const x0 = X0 + best.i0 * dx + m, x1 = X0 + best.i1 * dx - m, y0 = Y0 + best.j0 * dy + m, y1 = Y0 + best.j1 * dy - m;
  return { cx: r2((x0 + x1) / 2), cy: r2((y0 + y1) / 2), w: r2(x1 - x0), h: r2(y1 - y0), angle_deg: 0 };
}

function suggestOf(req: PlanRequest): Suggestion[] {
  const m = req.marker;
  const out: Suggestion[] = [];
  if (m.type === "single") {
    const z = sizes({ ...req, marker: { ...m, auto: true } });
    out.push({ label: `1×1 @ ${r2(z.marker)} mm`, reason: "fills the rectangle", params: { cols: 1, rows: 1, marker_mm: r2(z.marker), checker_mm: 0, separation_mm: 0 } });
    if (req.preset.cell_step_mm) {
      const n = bitsOf(m.dictionary) + 2, step = req.preset.cell_step_mm;
      const lines = Math.floor(z.marker / n / step);
      if (lines > 0) out.push({ label: `1×1 @ ${r2(lines * step * n)} mm`, reason: `cells = ${lines} lines of ${step} mm`,
        params: { cols: 1, rows: 1, marker_mm: r2(lines * step * n), checker_mm: 0, separation_mm: 0 } });
    }
    return out;
  }
  const cands: Suggestion[] = [];
  for (let c = 1; c <= 6; c++) for (let r = 1; r <= 5; r++) {
    if (m.type === "charuco" && c * r < 4) continue;
    const z = sizes({ ...req, marker: { ...m, cols: c, rows: r, auto: true } });
    if (z.marker <= 0) continue;
    cands.push({ label: `${c}×${r} @ ${r2(z.marker)} mm`, reason: "",
      params: { cols: c, rows: r, marker_mm: r2(z.marker), checker_mm: r2(z.checker), separation_mm: r2(m.separation_mm) } });
  }
  cands.sort((a, b) => b.params.marker_mm - a.params.marker_mm);
  if (cands[0]) out.push({ ...cands[0], reason: "largest marker" });
  const fill = [...cands].sort((a, b) => b.params.marker_mm ** 2 * b.params.cols * b.params.rows - a.params.marker_mm ** 2 * a.params.cols * a.params.rows)[0];
  if (fill && fill !== cands[0]) out.push({ ...fill, reason: "best fill" });
  const many = cands.filter((s) => s.params.marker_mm / (bitsOf(m.dictionary) + 2) >= (req.preset.min_cell_mm || 1))
    .sort((a, b) => b.params.cols * b.params.rows - a.params.cols * a.params.rows)[0];
  if (many && !out.includes(many)) out.push({ ...many, reason: "most markers with readable cells" });
  for (const s of cands.slice(1, 4)) if (!out.some((o) => o.label === s.label)) out.push({ ...s, reason: "fits" });
  return out;
}

function svgOf(plan: MarkerPlan, pad = 2): { svg: string; w: number; h: number } {
  const pts = [...plan.outer, ...(plan.label ? [plan.label.at] : [])];
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad - (plan.label?.height_mm ?? 0), y1 = Math.max(...ys) + pad;
  const d = (l: Loop) => "M" + l.map((p) => `${r2(p[0])} ${r2(p[1])}`).join("L") + "Z";
  const body = `<g transform="translate(${r2(-x0)} ${r2(y1)}) scale(1 -1)"><path d="${d(plan.outer)}" fill="#fff" stroke="#999" stroke-width="0.1"/>`
    + `<path fill-rule="evenodd" fill="#000" d="${plan.black.map((p) => d(p.outer) + p.holes.map(d).join("")).join("")}"/></g>`
    + (plan.label ? `<text x="${r2(plan.label.at[0] - x0)}" y="${r2(y1 - plan.label.at[1] + plan.label.height_mm / 2)}" font-size="${r2(plan.label.height_mm / 0.7)}" text-anchor="middle" font-family="sans-serif">${plan.label.text}</text>` : "");
  const w = r2(x1 - x0), h = r2(y1 - y0);
  return { svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${w}mm" height="${h}mm" viewBox="0 0 ${w} ${h}">${body}</svg>`, w, h };
}

/** A one-page PDF with the marker's black (a real, if tiny, PDF). */
function pdfOf(plan: MarkerPlan, page: Vec2): string {
  const k = 72 / 25.4;
  const [pw, ph] = [page[0] * k, page[1] * k];
  const xs = plan.outer.map((p) => p[0]), ys = plan.outer.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const tx = (p: Vec2) => `${((p[0] - cx + page[0] / 2) * k).toFixed(2)} ${((p[1] - cy + page[1] / 2) * k).toFixed(2)}`;
  const ops = plan.black.map((p) => [p.outer, ...p.holes].map((l) => l.map((q, i) => `${tx(q)} ${i ? "l" : "m"}`).join(" ") + " h").join(" ")).join(" ") + " f*";
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pw.toFixed(2)} ${ph.toFixed(2)}] /Contents 4 0 R >>`,
  ];
  const stream = `0 g ${ops}`;
  objs.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  let out = "%PDF-1.4\n";
  const offs: number[] = [];
  objs.forEach((o, i) => { offs.push(out.length); out += `${i + 1} 0 obj\n${o}\nendobj\n`; });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n${offs.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("")}`;
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return btoa(out);
}

function sheetOf(req: SheetRequest): Sheet {
  const first = req.items[0];
  const page: Vec2 = first?.preset.page_mm ?? [215.9, 279.4];
  const margin = first?.preset.margin_mm ?? 6;
  if (!first) return { pages: 0, svg: [], pdf_base64: "", warnings: [] };
  const plan = planOf(first);
  const one = svgOf(plan, 3);
  const x = r2((page[0] - one.w) / 2), y = r2(margin + 10);
  const inner = one.svg.replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "");
  const cut = req.cut_lines ? `<rect x="${x}" y="${y}" width="${one.w}" height="${one.h}" fill="none" stroke="#e0218a" stroke-width="0.2" stroke-dasharray="1 1"/>` : "";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${page[0]}mm" height="${page[1]}mm" viewBox="0 0 ${page[0]} ${page[1]}">`
    + `<rect width="${page[0]}" height="${page[1]}" fill="#fff"/><g transform="translate(${x} ${y})">${inner}</g>${cut}`
    + `<text x="${margin}" y="${page[1] - margin}" font-size="3" font-family="sans-serif" fill="#666">${plan.summary} · print at 100 %</text></svg>`;
  const warnings = one.w > page[0] - 2 * margin || one.h > page[1] - 2 * margin
    ? [{ field: "preset", level: "error" as const, text: "the marker does not fit on the page" }] : [];
  return { pages: 1, svg: [svg], pdf_base64: pdfOf(plan, page), warnings };
}

export function createMockCore(onReady: () => void, delay = 900): CoreApi {
  const ready = wait(delay).then(onReady);
  const call = async <T>(f: () => T): Promise<T> => {
    await ready;
    await wait(15 + Math.random() * 40);
    return f();
  };
  const info: CoreInfo = {
    core_version: "mock", python: "none (mock core)", pyodide: "none",
    dictionaries: DICTS.map(([name, capacity, b]) => ({ name, capacity, bits: b * b })),
  };
  return {
    info: () => call(() => info),
    presets: () => call(() => PRESETS.map((p) => ({ ...p }))),
    inscribe: (profile, holes) => call(() => inscribeOf(profile, holes)),
    plan: (req) => call(() => planOf(req)),
    suggest: (req) => call(() => suggestOf(req)),
    svg: (req) => call(() => svgOf(planOf(req)).svg),
    sheet: (req) => call(() => sheetOf(req)),
    // the dispatch of 2026-10-18 adds these; lanes give the mock real answers if they need them
    verify: () => Promise.reject(new Error("mock core: verify not mocked")),
    readable: () => Promise.reject(new Error("mock core: readable not mocked")),
    assign_ids: () => Promise.reject(new Error("mock core: assign_ids not mocked")),
  };
}
