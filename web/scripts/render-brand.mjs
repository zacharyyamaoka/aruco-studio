// Renders public/icon.svg to the square PNGs Google's OAuth branding page takes (headless Chrome, white
// background, 10% margin so a round crop keeps the whole mark): public/brand/logo-120.png (the upload)
// and public/brand/logo-512.png. Also copies the mark to public/brand/logo.svg, which the hosted-files
// /connect page shows when it runs on arucostudio.com (worker/index.ts).
//   node scripts/render-brand.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const svg = fs.readFileSync(path.join(web, "public/icon.svg"), "utf8");
fs.mkdirSync(path.join(web, "public/brand"), { recursive: true });
fs.writeFileSync(path.join(web, "public/brand/logo.svg"), svg);
const browser = await chromium.launch({ channel: "chrome", headless: true });
for (const size of [120, 512]) {
  const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
  const pad = Math.round(size * 0.1);
  await page.setContent(`<html><body style="margin:0;background:#fff;width:${size}px;height:${size}px;display:grid;place-items:center">
    <div style="width:${size - 2 * pad}px;height:${size - 2 * pad}px">${svg.replace("<svg ", '<svg width="100%" height="100%" ')}</div></body></html>`);
  await page.screenshot({ path: path.join(web, `public/brand/logo-${size}.png`) });
  await page.close();
}
await browser.close();
console.log("wrote public/brand/logo.svg, logo-120.png, logo-512.png");
