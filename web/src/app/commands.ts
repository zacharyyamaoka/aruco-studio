// The commands the top bar, the toolbar and the keys share.
import { core } from "../coreSource";
import { downloadBase64, downloadText, pickFile, slug } from "../io/files";
import { getFeature, parseDoc, planRequest, serialise, sheetItems, withFeatures, type Doc } from "../model/doc";
import { idLines, idsReady, settledOutput } from "./output";
import { activeFeatureId, selectedMarkerIds, useStudio } from "../store";
import { leaveFile } from "../hosted/hosted";
import { growForStart, grownWords, reIdDoc, reIdItems } from "../model/batch";

const st = () => useStudio.getState();

/** Download .arucostudio-web.json: the document as a file on this computer
 *  (signed in or not; the cloud's Save is in the document menu). */
export function saveDoc(): void {
  const { doc } = st();
  downloadText(`${slug(doc.name)}.arucostudio-web.json`, serialise(doc), "application/json");
}

/** Open from this computer: a file picked from disk becomes an unsaved
 *  document (a cloud file open is left first, its changes saved). */
export async function openDoc(): Promise<void> {
  const f = await pickFile(".json,application/json");
  if (!f) return;
  try {
    const doc = parseDoc(f.text);
    if (!(await leaveFile())) return;
    st().loadDoc(doc);
    st().say(`Opened ${f.name}`);
  } catch (e) {
    st().say(`Could not open ${f.name}: ${(e as Error).message}`);
  }
}

/** Before an export waits for auto id: a note, so the wait is not silent
 *  (true when it said one). */
function waitNote(what: string): boolean {
  if (idsReady(st())) return false;
  st().say(`${what}: waiting for auto id to number the markers…`);
  return true;
}

/** Export › SVG: the marker in focus (the panel's, the selected one, else the
 *  last made), from a revision whose ids are settled (app/output.ts). */
export async function exportSvg(): Promise<void> {
  const fid = activeFeatureId(st());
  if (!planRequest(st().doc, getFeature(st().doc, fid))) { st().say("Nothing to export yet: make an ArUco Extrude (A) first."); return; }
  const waited = waitNote("SVG export");
  try {
    let refused: string | null = null;
    const got = await settledOutput((doc) => {
      const f = getFeature(doc, fid);
      refused = f && st().idRefused.includes(f.key) ? f.key : null;
      return refused ? null : planRequest(doc, f);
    }, (req) => core.svg(req));
    if (refused) { st().say(`Not exported: ${idLines(st().doc, st().idIssues, [refused])[0].text}`); return; }
    if (!got) { st().say("Nothing to export: the marker is gone."); return; }
    downloadText(`${slug(got.doc.name)}-marker.svg`, got.out, "image/svg+xml");
    if (waited) st().say(null);
  } catch (e) {
    st().say(`SVG export failed: ${(e as Error).message}`);
  }
}

/** Export › PDF: the page of the marker in focus's preset (its inkjet
 *  markers, as Print lays them out); the first preset's when it is 3D printed.
 *  From a revision whose ids are settled; a refused marker is left out.
 *  Several markers selected: only those, as Print opens on them (printSelection). */
export async function exportPdf(): Promise<void> {
  const fid = activeFeatureId(st());
  const only = printSelection();
  const pick = (doc: Doc) => (only ? withFeatures(doc, only) : doc);
  if (!sheetItems(pick(st().doc), fid).length) {
    st().say(st().doc.features.length ? "Nothing on paper: 3D-print markers aren't printed on a sheet." : "Nothing to export yet: make an ArUco Extrude (A) first.");
    return;
  }
  const waited = waitNote("PDF export");
  try {
    const got = await settledOutput((doc) => {
      const items = sheetItems(pick(doc), fid, st().idRefused);
      return items.length ? { items, cut_lines: true } : null;
    }, (req) => core.sheet(req));
    // the refused markers among the ones exported
    const refused = st().idRefused.filter((k) => pick(st().doc).features.some((f) => f.key === k));
    if (!got) { st().say(`Not exported: ${idLines(st().doc, st().idIssues, refused)[0]?.text ?? "nothing on paper"}`); return; }
    downloadBase64(`${slug(got.doc.name)}.pdf`, got.out.pdf_base64, "application/pdf");
    if (refused.length) st().say(`PDF saved without ${refused.length} marker${refused.length === 1 ? "" : "s"}: ${idLines(st().doc, st().idIssues, refused)[0].text}`);
    else if (waited) st().say(null);
  } catch (e) {
    st().say(`PDF export failed: ${(e as Error).message}`);
  }
}

/** The markers Print and Export › PDF start from: the selected ones when the
 *  selection names 2+ (a right-drag box, Shift+click), else null (all).
 *  WHY 2+ (Zach, 2026-10-21: "if I only want to print a subset of markers I
 *  will right-click-drag select them and maybe shift-click a couple more"):
 *  the marker just made stays selected after OK, and is not a subset choice;
 *  the batch panel and Re-ID read a selection the same way. */
export function printSelection(): string[] | null {
  const { doc, sel, multi } = st();
  const only = selectedMarkerIds(doc, sel, multi);
  return only.length > 1 ? only : null;
}

/** Verify (the simulated camera bench): its dialog is web/src/verify's. */
export function openVerify(): void {
  st().openModal("verify");
}

/** Print: the sheet dialog, which says itself when nothing is on paper (3D-print markers only). */
export function openPrint(): void {
  if (!st().doc.features.length) { st().say("Nothing to print yet: make an ArUco Extrude (A) first."); return; }
  st().openModal("print");
}

/** The markers ArUco Re-ID numbers: the batch panel's (2+), else the canvas
 *  selection's when it names 2+ (as Print reads it: printSelection), else
 *  null (every marker).
 *  WHY the canvas selection too (Zach, 2026-11-13: "batch select a bunch of
 *  ids and then set the starting ID"): a right-drag box then Edit › ArUco
 *  Re-ID… renumbered the whole document. */
export function reIdScope(): string[] | null {
  const { panel } = st();
  if (panel.open && panel.featureIds.length > 1) return panel.featureIds;
  return printSelection();
}

/** Number `only` (feature ids; null: every marker) from `start`, left to right,
 *  top to bottom (model/batch.ts reIdItems), one undo step: the batch panel's
 *  First ID. `keepTyped` false renumbers typed ids too (they become driven).
 *  WHY (Zach, 2026-11-13): "set the starting ID to like 100 and then all of
 *  them would go 100, 101, etc." */
export async function reIdFrom(only: string[] | null, start: number, keepTyped = false): Promise<boolean> {
  const doc = st().doc;
  // a dictionary too small for ids from `start` grows to one of its bit size that holds them
  const { doc: base, grown } = growForStart(doc, only, start);
  try {
    const res = await core.assign_ids({ items: reIdItems(base, only, keepTyped), mode: "sequential", start, fresh: true });
    if (st().doc !== doc) { st().say("Re-ID not applied: the document changed while it was worked out. Try again."); return false; }
    const out = reIdDoc(base, only, res, keepTyped);
    st().reId(out.doc, out.res);
    const n = only ? only.length : doc.features.length;
    st().say(`Re-ID: ${n} marker${n === 1 ? "" : "s"} numbered from #${start}, left to right, top to bottom`
      + (grown.length ? `; dictionary ${grownWords(grown)}.` : "."));
    return true;
  } catch (e) {
    st().say(`Re-ID failed: ${(e as Error).message}`);
    return false;
  }
}
