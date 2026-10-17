// ArUco Studio's web app. Dev: Vite on 127.0.0.1:5361, /api proxied to the
// Studio's server on 127.0.0.1:5360. Build: studio/dist, which the server
// serves at / on 5360.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5361,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:5360", changeOrigin: false } },
  },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
});
