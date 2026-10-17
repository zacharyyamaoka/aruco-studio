import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initTheme, setTheme, getTheme } from "@bam/ui";
import "@bam/ui/tokens.css";
import "./tw.css";
import "./styles.css";
import { App } from "./app/App";
import { studioProbe, useStudio } from "./store";
import { registerStudioGlyphs } from "./ui/icons";

registerStudioGlyphs();
initTheme();

// What the tests read (ARCHITECTURE 4, PLAN M3.5): the camera centre, the
// scene's z extent, the selection, the store itself. M8b2: the theme, and
// the hooks a test sets so nothing leaves the browser (printHook: called
// with the PDF's bytes instead of the print dialog; it returns false to act
// as a browser that cannot print a PDF; sendOpen: false keeps PrusaSlicer
// closed on Send).
declare global {
  interface Window { __studio: any }
}
window.__studio = {
  get center() { return studioProbe().center; },
  get zRange() { return studioProbe().zRange; },
  probe: studioProbe,
  store: useStudio,
  idle: () => useStudio.getState().idle(),
  theme: { get: getTheme, set: setTheme },
  printHook: null as null | ((bytes: Uint8Array, url: string) => boolean | Promise<boolean>),
  sendOpen: true,
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
