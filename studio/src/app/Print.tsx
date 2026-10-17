// Print (M6c, M6 note i): the sticker sheet's PDF (GET /api/scene/print.pdf,
// the bytes Export writes as sheet.pdf) is loaded into a hidden iframe from
// a blob URL and its own print() opens the browser's print dialog on the
// PDF: Chrome and Edge print it at Scale: Default = 100 %. The page says
// "Print at 100 % / Actual size" above its bars, which catch a wrong scale.
// Firefox prints the host page instead of the PDF, so there (or when the
// iframe refuses) the Studio offers "Open the PDF" and the Ctrl+P note.
//
// Tests: the OS dialog cannot be driven, so window.__studio.printHook, when
// set, is called with the PDF's bytes instead; a hook that returns false
// acts as a browser that cannot print the PDF (the fallback).
import { api, type SheetQuery } from "../api/client";

export type PrintOutcome = "printed" | "hooked" | "fallback";

const FRAME = "studio-print-frame";

function firefox(): boolean {
  return typeof navigator !== "undefined" && /firefox/i.test(navigator.userAgent);
}

/** The sheet to the print dialog: -> what happened. */
export async function printPdf(q: SheetQuery): Promise<PrintOutcome> {
  const url = api.printUrl(q);
  const bytes = await api.printBytes(q);
  const hook = (window as any).__studio?.printHook as null | ((b: Uint8Array, u: string) => boolean | Promise<boolean>);
  if (typeof hook === "function") {
    const ok = await hook(bytes, url);
    return ok === false ? "fallback" : "hooked";
  }
  if (firefox()) return "fallback";
  document.getElementById(FRAME)?.remove();
  const blobUrl = URL.createObjectURL(new Blob([bytes as BlobPart], { type: "application/pdf" }));
  const frame = document.createElement("iframe");
  frame.id = FRAME;
  frame.title = "the sticker sheet, for the print dialog";
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none";
  frame.src = blobUrl;
  const loaded = new Promise<boolean>((res) => {
    frame.onload = () => res(true);
    setTimeout(() => res(false), 8000);
  });
  document.body.appendChild(frame);
  if (!(await loaded)) return "fallback";
  try {
    frame.contentWindow?.focus();
    frame.contentWindow?.print();
  } catch {
    return "fallback";
  }
  // the blob stays alive while the dialog is up; a minute is plenty
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
  return "printed";
}

/** Why Print is off for this scene (null: it can print). */
export function printBlock(stickers: number): string | null {
  return stickers ? null : "no stickers in this scene (3D tags print on beds)";
}

/** Why Send to PrusaSlicer is off for this scene (null: it can send). */
export function sendBlock(printed3d: number, stickers: number): string | null {
  if (printed3d) return null;
  return stickers ? "nothing to slice: stickers print on paper" : "nothing to slice: the scene has no 3D tag";
}
