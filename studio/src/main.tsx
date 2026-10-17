import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { studioProbe, useStudio } from "./store";
import "./styles.css";

// What the tests read (ARCHITECTURE 4, PLAN M3.5): the camera centre, the
// scene's z extent, the selection, the store itself.
declare global {
  interface Window { __studio: any }
}
window.__studio = {
  get center() { return studioProbe().center; },
  get zRange() { return studioProbe().zRange; },
  probe: studioProbe,
  store: useStudio,
  idle: () => useStudio.getState().idle(),
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
