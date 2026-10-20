// Packs the Python core for the browser (docs/design/online_studio_v1.md):
//   web/public/py/aruco_studio.zip   aruco_studio/{__init__.py, web_api.py, web_extrude.py, web_ids.py, web_verify.py, core/, plan/, scene/, verify/}
//                                    + aruco_studio/_build.json (the version info() reports);
//                                    verify/ needs numpy + OpenCV, which the worker loads on the
//                                    first verify / readable call
//   web/public/pyodide/              Pyodide's runtime, copied from node_modules (self-hosted:
//                                    no CDN, works offline, and in 10 years)
// Dependency-free Node: a stored-or-deflated zip written by hand (node:zlib),
// deterministic (sorted names, a fixed date) so the same tree packs the same bytes.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const root = path.resolve(web, "..");
const pkg = path.join(root, "aruco_studio");
const PACKAGES = ["core", "plan", "scene", "verify"];
const FILES = ["__init__.py", "web_api.py", "web_extrude.py", "web_ids.py", "web_verify.py"];
const PYODIDE = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"];

function walk(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === "__pycache__" || e.name.endsWith(".pyc")) continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(full));
    else if (e.isFile()) out.push(full);
  }
  return out;
}

const CRC = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** entries: [{name, data: Buffer}] -> a zip (deflate, or stored when that is smaller). */
export function zip(entries) {
  const DOS_TIME = 0, DOS_DATE = (1 << 5) | 1; // 1980-01-01 00:00
  const locals = [], central = [];
  let offset = 0;
  for (const { name, data } of entries) {
    const nameBuf = Buffer.from(name, "utf8");
    const deflated = zlib.deflateRawSync(data, { level: 9 });
    const method = deflated.length < data.length ? 8 : 0;
    const body = method ? deflated : data;
    const crc = crc32(data);
    const head = Buffer.alloc(30);
    head.writeUInt32LE(0x04034b50, 0);
    head.writeUInt16LE(20, 4);
    head.writeUInt16LE(0x0800, 6); // UTF-8 names
    head.writeUInt16LE(method, 8);
    head.writeUInt16LE(DOS_TIME, 10);
    head.writeUInt16LE(DOS_DATE, 12);
    head.writeUInt32LE(crc, 14);
    head.writeUInt32LE(body.length, 18);
    head.writeUInt32LE(data.length, 22);
    head.writeUInt16LE(nameBuf.length, 26);
    head.writeUInt16LE(0, 28);
    locals.push(head, nameBuf, body);
    const cen = Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50, 0);
    cen.writeUInt16LE(20, 4);
    cen.writeUInt16LE(20, 6);
    cen.writeUInt16LE(0x0800, 8);
    cen.writeUInt16LE(method, 10);
    cen.writeUInt16LE(DOS_TIME, 12);
    cen.writeUInt16LE(DOS_DATE, 14);
    cen.writeUInt32LE(crc, 16);
    cen.writeUInt32LE(body.length, 20);
    cen.writeUInt32LE(data.length, 24);
    cen.writeUInt16LE(nameBuf.length, 28);
    cen.writeUInt32LE(0, 38);
    cen.writeUInt32LE(offset, 42);
    central.push(cen, nameBuf);
    offset += head.length + nameBuf.length + body.length;
  }
  const cenBuf = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(cenBuf.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, cenBuf, end]);
}

function gitDescribe() {
  try {
    return execFileSync("git", ["describe", "--always", "--dirty"], { cwd: root, encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

export function packCore(outFile = path.join(web, "public", "py", "aruco_studio.zip")) {
  const files = [...FILES.map((f) => path.join(pkg, f)), ...PACKAGES.flatMap((p) => walk(path.join(pkg, p)))];
  const entries = files
    .map((full) => ({ name: path.relative(root, full).split(path.sep).join("/"), data: fs.readFileSync(full) }))
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  const version = /__version__\s*=\s*"([^"]+)"/.exec(fs.readFileSync(path.join(pkg, "__init__.py"), "utf8"))?.[1] ?? "";
  const build = { version, git: gitDescribe() };
  entries.push({ name: "aruco_studio/_build.json", data: Buffer.from(JSON.stringify(build) + "\n") });
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  const bytes = zip(entries);
  fs.writeFileSync(outFile, bytes);
  return { outFile, files: entries.length, bytes: bytes.length, build };
}

export function copyPyodide(outDir = path.join(web, "public", "pyodide")) {
  const src = path.join(web, "node_modules", "pyodide");
  fs.mkdirSync(outDir, { recursive: true });
  let bytes = 0;
  for (const f of PYODIDE) {
    fs.copyFileSync(path.join(src, f), path.join(outDir, f));
    bytes += fs.statSync(path.join(outDir, f)).size;
  }
  const version = JSON.parse(fs.readFileSync(path.join(src, "package.json"), "utf8")).version;
  return { outDir, files: PYODIDE.length, bytes, version };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const core = packCore();
  const py = copyPyodide();
  const kb = (n) => `${(n / 1024).toFixed(0)} KB`;
  console.log(`pack-core: ${path.relative(web, core.outFile)} ${core.files} files, ${kb(core.bytes)} (${core.build.version}+${core.build.git || "?"})`);
  console.log(`pack-core: ${path.relative(web, py.outDir)}/ Pyodide ${py.version}, ${py.files} files, ${kb(py.bytes)}`);
}
