// A measurement against an ALREADY RUNNING served
// Studio on 5360 (python -m aruco_studio.server with studio/dist; no Vite,
// no proxy hop). No webServer here: start the server first (docs/status/verify-2026-10-17.md).
import { defineConfig } from "@playwright/test";
import path from "node:path";

export default defineConfig({
  testDir: __dirname,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: path.join(__dirname, "verify-results"),
  use: {
    baseURL: "http://127.0.0.1:5360",
    channel: "chrome",
    viewport: { width: 1500, height: 900 },
    launchOptions: { args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"] },
    acceptDownloads: true,
    trace: "off",
  },
});
