// The commands the top bar, the toolbar and the keys share.
import { core } from "../coreSource";
import { downloadBase64, downloadText, pickFile, slug } from "../io/files";
import { getFeature, parseDoc, planRequest, serialise, sheetItems } from "../model/doc";
import { activeFeatureId, useStudio } from "../store";

const st = () => useStudio.getState();

export function saveDoc(): void {
  const { doc } = st();
  downloadText(`${slug(doc.name)}.arucostudio-web.json`, serialise(doc), "application/json");
}

export async function openDoc(): Promise<void> {
  const f = await pickFile(".json,application/json");
  if (!f) return;
  try {
    const doc = parseDoc(f.text);
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

/** Export › PDF: the preset's page with every feature, as Print lays it out. */
export async function exportPdf(): Promise<void> {
  const items = sheetItems(st().doc);
  if (!items.length) { st().say("Nothing to export yet: make an ArUco Extrude (A) first."); return; }
  try {
    const sheet = await core.sheet({ items, cut_lines: true });
    downloadBase64(`${slug(st().doc.name)}.pdf`, sheet.pdf_base64, "application/pdf");
  } catch (e) {
    st().say(`PDF export failed: ${(e as Error).message}`);
  }
}

/** Verify (the simulated camera bench): its dialog is web/src/verify's. */
export function openVerify(): void {
  st().openModal("verify");
}

export function openPrint(): void {
  if (!sheetItems(st().doc).length) { st().say("Nothing to print yet: make an ArUco Extrude (A) first."); return; }
  st().openModal("print");
}
