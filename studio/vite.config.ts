// ArUco Studio's web app. Dev: Vite on 127.0.0.1:5361, /api proxied to the
// Studio's server on 127.0.0.1:5360. Build: studio/dist, which the server
// serves at / on 5360. The kit is packages/bam-ui (imported as "@bam/ui").
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: [{ find: /^@bam\/ui/, replacement: path.resolve(import.meta.dirname, "packages/bam-ui/src") }] },
  server: {
    host: "127.0.0.1",
    port: 5361,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:5360", changeOrigin: false } },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
});
