// `npm run studio`: build the web app, then serve it with the API on
// http://127.0.0.1:5360 (the ROOT venv's python). Ctrl+C stops it.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const studio = path.resolve(here, "..");
const root = path.resolve(studio, "..");
const py = [path.join(root, ".venv", "Scripts", "python.exe"), path.join(root, ".venv", "bin", "python")].find(existsSync);
if (!py) {
  console.error("No ROOT/.venv: make it first (README: Make the venv).");
  process.exit(1);
}
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const b = spawnSync(npm, ["run", "build"], { cwd: studio, stdio: "inherit", shell: process.platform === "win32" });
if (b.status !== 0) process.exit(b.status ?? 1);
console.log("ArUco Studio: http://127.0.0.1:5360  (Ctrl+C stops it)");
const s = spawn(py, ["-m", "aruco_studio.server"], { cwd: root, stdio: "inherit" });
s.on("exit", (code) => process.exit(code ?? 0));
process.on("SIGINT", () => s.kill("SIGINT"));
