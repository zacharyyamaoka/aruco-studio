import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initTheme } from "@bam/ui";
import "@bam/ui/tokens.css";
import "./styles.css";
import { App } from "./App";
import { initSkin } from "./skins/skins";
import { installProbe } from "./probe";
import { registerWebGlyphs } from "./ui/icons";
import { openExampleFromUrl } from "./app/urlExample";

initTheme();
initSkin();
registerWebGlyphs();
installProbe();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
// ?example=<name> (the guides' "Open the board in the Studio"): after the first render, once the hosted files have started
void openExampleFromUrl();
