// Playwright e2e for the Studio, on the real server (uvicorn, 127.0.0.1:5360)
// and the Vite UI (127.0.0.1:5361). `npm test` here starts both (and stops
// them after); tools/check.py starts them itself and these are reused.
// The server's files go to e2e/.tmp (never ROOT/.studio_data, never
// %USERPROFILE%\CADExporter). Chrome is the installed one (channel), so no
// browser is downloaded.
import { defineConfig } from "@playwright/test";
import path from "node:path";

const ROOT = path.resolve(__dirname, "..");
const TMP = path.join(__dirname, ".tmp");
const PY = path.join(ROOT, ".venv", "Scripts", "python.exe");

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,                       // one server, one open scene
  retries: 0,
  reporter: [["list"]],
  outputDir: path.join(TMP, "results"),
  use: {
    baseURL: "http://127.0.0.1:5361",
    channel: "chrome",
    viewport: { width: 1500, height: 900 },
    launchOptions: { args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"] },
    acceptDownloads: true,
    trace: "off",
  },
  webServer: [
    {
      command: `"${PY}" -B -m uvicorn aruco_studio.server.app:app --host 127.0.0.1 --port 5360`,
      cwd: ROOT,
      url: "http://127.0.0.1:5360/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        ARUCO_STUDIO_HOME: path.join(TMP, "home"),
        ARUCO_STUDIO_SCENES: path.join(TMP, "scenes"),
        BAM_ARUCO_PRUSASLICER_DIR: path.join(ROOT, "goldens", "prusaslicer"),
        PYTHONDONTWRITEBYTECODE: "1",
      },
    },
    {
      command: "npm run dev",
      cwd: path.join(ROOT, "studio"),
      url: "http://127.0.0.1:5361/",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
