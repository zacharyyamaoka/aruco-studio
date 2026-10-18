import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initTheme } from "@bam/ui";
import "@bam/ui/tokens.css";
import { App } from "./App";

initTheme();
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
