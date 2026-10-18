import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initTheme } from "@bam/ui";
import "@bam/ui/tokens.css";
import "./styles.css";
import { App } from "./App";
import { installProbe } from "./probe";
import { registerWebGlyphs } from "./ui/icons";

initTheme();
registerWebGlyphs();
installProbe();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
