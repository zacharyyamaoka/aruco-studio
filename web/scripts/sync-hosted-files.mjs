// Copies the Simple Hosted Files core (its client/src/core, the folder the
// shadcn registry's hosted-files-core item is) into web/src/hosted/core,
// verbatim, and stamps what it copied in web/src/hosted/core.source.json.
//   node scripts/sync-hosted-files.mjs           copy (SHF_REPO moves the source, default /home/bam/simple-hosted-files)
//   node scripts/sync-hosted-files.mjs --check   exit 1 when the copy no longer matches its stamp or the source
// WHY a copy, never an edit: one source, never forked (simple-hosted-files SPEC v2.5);
// a fix to the core is made there and synced here.
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const repo = path.resolve(process.env.SHF_REPO || "/home/bam/simple-hosted-files");
const src = path.join(repo, "client/src/core");
const dest = path.join(web, "src/hosted/core");
const stamp = path.join(web, "src/hosted/core.source.json");
const check = process.argv.includes("--check");

const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const list = (dir) => fs.readdirSync(dir).filter((n) => /\.ts$/.test(n) && !/\.(test|spec)\.ts$/.test(n)).sort();
const hashes = (dir) => Object.fromEntries(list(dir).map((n) => [n, sha(path.join(dir, n))]));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

if (check) {
  const want = JSON.parse(fs.readFileSync(stamp, "utf8"));
  const problems = [];
  if (!same(hashes(dest), want.files)) problems.push("web/src/hosted/core differs from core.source.json (edited here? fix it upstream, then sync)");
  if (fs.existsSync(src) && !same(hashes(src), want.files)) problems.push(`${src} has moved on since ${want.commit}: run node scripts/sync-hosted-files.mjs`);
  if (!fs.existsSync(src)) console.log(`(no ${src} here: checked the copy against its stamp only)`);
  for (const p of problems) console.error(p);
  if (!problems.length) console.log(`hosted core in sync: ${Object.keys(want.files).length} files from ${want.commit}`);
  process.exit(problems.length ? 1 : 0);
}

const commit = execFileSync("git", ["-C", repo, "log", "-1", "--format=%h", "--", "client/src/core"], { encoding: "utf8" }).trim();
const dirty = execFileSync("git", ["-C", repo, "status", "--porcelain", "--", "client/src/core"], { encoding: "utf8" }).trim();
fs.rmSync(dest, { recursive: true, force: true });
fs.mkdirSync(dest, { recursive: true });
for (const n of list(src)) fs.copyFileSync(path.join(src, n), path.join(dest, n));
const files = hashes(dest);
fs.writeFileSync(stamp, JSON.stringify({ from: "simple-hosted-files/client/src/core", commit: dirty ? `${commit}+dirty` : commit, files }, null, 2) + "\n");
console.log(`copied ${Object.keys(files).length} files from ${src} @ ${commit}${dirty ? " (with uncommitted changes)" : ""}`);
