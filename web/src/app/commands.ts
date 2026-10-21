// The commands the top bar, the toolbar and the keys share.
import { core } from "../coreSource";
import { downloadBase64, downloadText, pickFile, slug } from "../io/files";
import { getFeature, parseDoc, planRequest, serialise, sheetItems, withFeatures } from "../model/doc";
import { activeFeatureId, selectedMarkerIds, useStudio } from "../store";
import { leaveFile } from "../hosted/hosted";

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

/** Export › SVG: the marker in focus (the panel's, the selected one, else the last made). */
export async function exportSvg(): Promise<void> {
  const req = planRequest(st().doc, getFeature(st().doc, activeFeatureId(st())));
  if (!req) { st().say("Nothing to export yet: make an ArUco Extrude (A) first."); return; }
  try {
    downloadText(`${slug(st().doc.name)}-marker.svg`, await core.svg(req), "image/svg+xml");
  } catch (e) {
    st().say(`SVG export failed: ${(e as Error).message}`);
  }
}

/** Export › PDF: the page of the marker in focus's preset (its inkjet
 *  markers, as Print lays them out); the first preset's when it is 3D printed.
 *  Several markers selected: only those, as Print opens on them (printSelection). */
export async function exportPdf(): Promise<void> {
  const only = printSelection();
  const items = sheetItems(only ? withFeatures(st().doc, only) : st().doc, activeFeatureId(st()));
  if (!items.length) {
    st().say(st().doc.features.length ? "Nothing on paper: 3D-print markers aren't printed on a sheet." : "Nothing to export yet: make an ArUco Extrude (A) first.");
    return;
  }
  try {
    const sheet = await core.sheet({ items, cut_lines: true });
    downloadBase64(`${slug(st().doc.name)}.pdf`, sheet.pdf_base64, "application/pdf");
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
