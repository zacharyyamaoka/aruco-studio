// Copies the Simple Hosted Files SDK into web/src/hosted, verbatim, and stamps
// what it copied in web/src/hosted/core.source.json:
//   core   client/src/core                                  -> web/src/hosted/core   (the registry's hosted-files-core)
//   react  web/registry/hosted-files-react/lib/hosted-files/react -> web/src/hosted/react  (hosted-files-react's hooks)
// The copies import "@/lib/hosted-files/core", "@/lib/utils" and "sonner" as
// a shadcn app would; vite.config.ts and tsconfig.app.json point those at
// web/src/hosted (shims/ for the last two: the Studio's kit, no new package).
//   node scripts/sync-hosted-files.mjs           copy (SHF_REPO moves the source, default /home/bam/simple-hosted-files)
//   node scripts/sync-hosted-files.mjs --check   exit 1 when a copy no longer matches its stamp or the source
// WHY a copy, never an edit: one source, never forked (simple-hosted-files SPEC v2.5);
// a fix to the SDK is made there and synced here.
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const repo = path.resolve(process.env.SHF_REPO || "/home/bam/simple-hosted-files");
const PARTS = {
  core: "client/src/core",
  react: "web/registry/hosted-files-react/lib/hosted-files/react",
};
const stamp = path.join(web, "src/hosted/core.source.json");
const check = process.argv.includes("--check");

const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const list = (dir) => fs.readdirSync(dir).filter((n) => /\.tsx?$/.test(n) && !/\.(test|spec)\.tsx?$/.test(n)).sort();
const hashes = (dir) => Object.fromEntries(list(dir).map((n) => [n, sha(path.join(dir, n))]));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const dest = (part) => path.join(web, "src/hosted", part);
const src = (part) => path.join(repo, PARTS[part]);

if (check) {
  const want = JSON.parse(fs.readFileSync(stamp, "utf8"));
  const problems = [];
  for (const part of Object.keys(PARTS)) {
    const files = want.parts?.[part]?.files;
    if (!files || !same(hashes(dest(part)), files)) problems.push(`web/src/hosted/${part} differs from core.source.json (edited here? fix it upstream, then sync)`);
    if (!fs.existsSync(src(part))) console.log(`(no ${src(part)} here: checked the copy against its stamp only)`);
    else if (!same(hashes(src(part)), files)) problems.push(`${src(part)} has moved on since ${want.commit}: run node scripts/sync-hosted-files.mjs`);
  }
  for (const p of problems) console.error(p);
  if (!problems.length) console.log(`hosted SDK in sync: ${Object.keys(PARTS).map((p) => `${p} ${Object.keys(want.parts[p].files).length} files`).join(", ")} from ${want.commit}`);
  process.exit(problems.length ? 1 : 0);
}

const git = (...args) => execFileSync("git", ["-C", repo, ...args], { encoding: "utf8" }).trim();
const paths = Object.values(PARTS);
const commit = git("log", "-1", "--format=%h", "--", ...paths);
const dirty = git("status", "--porcelain", "--", ...paths);
const parts = {};
for (const part of Object.keys(PARTS)) {
  fs.rmSync(dest(part), { recursive: true, force: true });
  fs.mkdirSync(dest(part), { recursive: true });
  for (const n of list(src(part))) fs.copyFileSync(path.join(src(part), n), path.join(dest(part), n));
  parts[part] = { from: `simple-hosted-files/${PARTS[part]}`, files: hashes(dest(part)) };
}
fs.writeFileSync(stamp, JSON.stringify({ commit: dirty ? `${commit}+dirty` : commit, parts }, null, 2) + "\n");
console.log(`copied ${Object.entries(parts).map(([p, v]) => `${p} ${Object.keys(v.files).length} files`).join(", ")} from ${repo} @ ${commit}${dirty ? " (with uncommitted changes)" : ""}`);
