/// <reference types="vitest/config" />
// The online Studio (arucostudio.com). Dev: 127.0.0.1:5380, preview: 5381
// (ARUCO_WEB_PORT moves dev). Static build in web/dist; the Python core is
// packed into public/py/ by scripts/pack-core.mjs and runs in a Pyodide worker.
// The kit is studio/packages/bam-ui, imported as "@bam/ui" (one kit, no copy).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

const here = import.meta.dirname;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: [
      { find: /^@bam\/ui/, replacement: path.resolve(here, "../studio/packages/bam-ui/src") },
      // the Simple Hosted Files copies (src/hosted, scripts/sync-hosted-files.mjs)
      // import as a shadcn app; these are the names they use
      { find: /^@\/lib\/hosted-files\/(core|react)$/, replacement: path.resolve(here, "src/hosted/$1/index.ts") },
      { find: /^@\/lib\/utils$/, replacement: path.resolve(here, "src/hosted/shims/utils.ts") },
      { find: /^sonner$/, replacement: path.resolve(here, "src/hosted/shims/sonner.ts") },
    ],
    // WHY: the kit's files live outside web/, so its imports must resolve to
    // web/node_modules, or React loads twice.
    dedupe: ["react", "react-dom", "@base-ui/react", "cmdk", "lucide-react"],
  },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.ARUCO_WEB_PORT || 5380),
    strictPort: true,
    fs: { allow: [path.resolve(here, "..")] },
  },
  worker: { format: "es" },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
  // vitest: unit tests only; web/e2e is Playwright's (npm run e2e).
  test: { include: ["src/**/*.test.ts", "worker/**/*.test.ts"] },
});
