// ArUco Studio's web app. Dev: Vite on 127.0.0.1:5361, /api proxied to the
// Studio's server on 127.0.0.1:5360. Build: studio/dist, which the server
// serves at / on 5360. The kit is packages/bam-ui (imported as "@bam/ui").
// ARUCO_STUDIO_UI_PORT / ARUCO_STUDIO_API_PORT move both (tools/check.py
// beside a lane's own server; the default is 5361 / 5360).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

const UI_PORT = Number(process.env.ARUCO_STUDIO_UI_PORT || 5361);
const API_PORT = Number(process.env.ARUCO_STUDIO_API_PORT || 5360);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: [{ find: /^@bam\/ui/, replacement: path.resolve(import.meta.dirname, "packages/bam-ui/src") }] },
  server: {
    host: "127.0.0.1",
    port: UI_PORT,
    strictPort: true,
    proxy: { "/api": { target: `http://127.0.0.1:${API_PORT}`, changeOrigin: false } },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
});
