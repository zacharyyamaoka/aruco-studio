// The online Studio's e2e (docs/design/online_studio_v1.md): the static build
// served by `vite preview` on 5381, driven in Chrome, one worker.
// E2E_CORE=mock runs the specs on the mock core (?core=mock); the default
// is the real Python core in its Pyodide worker. hero.spec.ts records a
// video of the primary flow (its project only). E2E_BASE_URL runs the specs
// against a deployed site instead (e.g. https://arucostudio.com): no server.
// E2E_HOSTED_SERVER (a local Simple Hosted Files, e.g. http://localhost:8797)
// is built in as the Studio's cloud and runs hosted.spec.ts; without it that
// spec skips.
import { defineConfig } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT || 5381);   // a lane in a worktree takes its own
const LIVE = process.env.E2E_BASE_URL;
const HOSTED = process.env.E2E_HOSTED_SERVER;

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  fullyParallel: false,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  use: {
    baseURL: LIVE ?? `http://127.0.0.1:${PORT}`,
    channel: "chrome",
    viewport: { width: 1280, height: 800 },
    acceptDownloads: true,
    trace: "retain-on-failure",
  },
  webServer: LIVE ? undefined : {
    command: process.env.E2E_SERVER ?? `npm run build && npx vite preview --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 300_000,
    stdout: "ignore",
    stderr: "pipe",
    env: { ...process.env as Record<string, string>, ...(HOSTED ? { VITE_HOSTED_FILES_SERVER: HOSTED } : {}) },
  },
  projects: [
    { name: "e2e", testIgnore: /hero\.spec\.ts/ },
    {
      name: "hero",
      testMatch: /hero\.spec\.ts/,
      use: { viewport: { width: 1280, height: 800 }, video: { mode: "on", size: { width: 1280, height: 800 } } },
    },
  ],
});
