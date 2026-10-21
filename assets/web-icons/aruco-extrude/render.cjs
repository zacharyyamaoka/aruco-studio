// The ArUco Extrude icon's PNGs (16, 32, 64 px) from make_icon.py's SVGs, in
// headless Chrome, transparent: for the Fusion add-in to take up if it wants
// an icon that is not Autodesk's. The web app draws the same markup as glyphs
// (web/src/ui/icons.ts: extrude, extrude-lg).
//   python3 assets/web-icons/aruco-extrude/make_icon.py assets/web-icons/aruco-extrude
//   NODE_PATH=web/node_modules node assets/web-icons/aruco-extrude/render.cjs
const fs = require("fs");
const path = require("path");
const { chromium } = require("@playwright/test");

const here = __dirname;
const jobs = [["extrude-16.svg", 16], ["extrude-32.svg", 32], ["extrude-32.svg", 64]];

(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const [file, size] of jobs) {
    const svg = fs.readFileSync(path.join(here, file), "utf8").replace(/width="\d+" height="\d+"/, `width="${size}" height="${size}"`);
    await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await page.locator("svg").screenshot({ path: path.join(here, `${size}x${size}.png`), omitBackground: true });
  }
  await browser.close();
})();
