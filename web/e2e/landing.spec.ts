// The landing page (/about/, written by docs/build_landing.py) and what
// crawlers read: robots.txt, sitemap.xml, the JSON-LD and the <noscript> on /.
// Every check reads what the server sends (content types, the raw HTML) or
// what is drawn (scrollWidth, getBoundingClientRect), so the SPA fallback
// (index.html for any missing path) can never pass for a real file.
//
//   E2E_PORT=5393 npx playwright test --project=e2e e2e/landing.spec.ts
import { expect, test, type APIRequestContext } from "@playwright/test";

const GITHUB = "https://github.com/zacharyyamaoka/aruco-studio";
const RELEASES = `${GITHUB}/releases`;
const HEADLINE = "ArUco markers at the level of intent";

/** The page's JSON-LD blocks, parsed from the raw HTML the server sends. */
async function jsonLd(request: APIRequestContext, path: string): Promise<any[]> {
  const res = await request.get(path);
  expect(res.status()).toBe(200);
  const body = await res.text();
  const blocks = [...body.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)].map((m) => JSON.parse(m[1]));
  expect(blocks.length, `${path} has a JSON-LD block`).toBeGreaterThan(0);
  return blocks;
}

test.describe("landing page and crawling", () => {
  test.describe("without JavaScript", () => {
    test.use({ javaScriptEnabled: false });

    test("1 · /about/ reads with JS off: the headline, the sections, the Q&A", async ({ page }) => {
      const res = await page.goto("/about/");
      expect(res!.status()).toBe(200);
      await expect(page.locator("h1")).toHaveText(HEADLINE);
      for (const id of ["what", "philosophy", "download", "qa"]) await expect(page.locator(`section#${id} h2`)).toBeVisible();
      expect(await page.locator("#qa .qa").count()).toBeGreaterThanOrEqual(5);
      // the real file, not the Studio's SPA shell
      expect(await page.locator("#root").count()).toBe(0);
    });

  });

  // WHY the raw HTML, not a page with JS off: Playwright turns scripting off
  // after the parser has decided <noscript> is raw text, so it never renders
  // there. A crawler that runs no JS reads exactly these bytes.
  test("2 · / without JS: the <noscript> text and a link to /about/", async ({ request }) => {
    const res = await request.get("/");
    expect(res.headers()["content-type"]).toContain("text/html");
    const body = await res.text();
    const noscript = body.match(/<noscript>([\s\S]*?)<\/noscript>/)?.[1] ?? "";
    expect(noscript).toContain("ArUco and ChArUco marker generator");
    expect(noscript).toContain('<a href="/about/">');
    expect(noscript).toContain(`<a href="${GITHUB}">`);
  });

  test("3 · the two calls to action: Download -> #download (primary), Try Online -> /", async ({ page }) => {
    await page.goto("/about/");
    const download = page.locator('header.hero [data-cta="download"]');
    const online = page.locator('header.hero [data-cta="online"]');
    await expect(download).toHaveAttribute("href", "#download");
    await expect(download).toHaveText("Download");
    await expect(download).toHaveClass(/\bprimary\b/);
    await expect(online).toHaveAttribute("href", "/");
    await expect(online).toHaveText("Try Online");
    // GitHub is no longer a call to action, here or at the bottom
    expect(await page.locator('.ctas a[href*="github.com"], [data-cta="github"]').count()).toBe(0);
    for (const b of [await download.boundingBox(), await online.boundingBox()]) {
      expect(b!.y + b!.height, "the calls to action are above the fold").toBeLessThan(800);
    }
    // the same two at the bottom of the page
    const foot = page.locator("footer .ctas a");
    await expect(foot).toHaveText(["Download", "Try Online"]);
    expect(await foot.evaluateAll((as) => as.map((a) => a.getAttribute("href")))).toEqual(["#download", "/"]);
    await download.click();
    await expect(page).toHaveURL(/#download$/);
    expect((await page.locator("section#download h2").boundingBox())!.y, "Download scrolls to its section").toBeLessThan(200);
  });

  test("3b · GitHub is the mark at the right of the top bar; the footer keeps its text link", async ({ page }) => {
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/about/");
      const gh = page.locator('nav.top a[aria-label="GitHub"]');
      await expect(gh).toHaveAttribute("href", GITHUB);
      await expect(gh).toBeVisible();
      expect(await gh.locator("svg path").count(), "the GitHub mark").toBe(1);
      expect((await gh.textContent())!.trim(), "an icon, not a word").toBe("");
      // the rightmost thing in the bar, flush with its right edge
      const m = await page.evaluate(() => {
        const nav = document.querySelector("nav.top")!.getBoundingClientRect();
        const items = [...document.querySelectorAll("nav.top a")].filter((a) => (a as HTMLElement).offsetParent !== null)
          .map((a) => ({ label: a.getAttribute("aria-label"), right: a.getBoundingClientRect().right }));
        return { navRight: nav.right, last: items.reduce((a, b) => (b.right > a.right ? b : a)) };
      });
      expect(m.last.label, `${width} px`).toBe("GitHub");
      expect(Math.abs(m.navRight - m.last.right), `${width} px`).toBeLessThan(1);
    }
    await expect(page.locator(`footer a[href="${GITHUB}"]`)).toHaveText("GitHub");
  });

  test("3c · #download: one honest card per CAD program, no fake downloads", async ({ page }) => {
    await page.goto("/about/");
    const cards = page.locator("section#download .card");
    await expect(cards.locator("b")).toHaveText(["Fusion 360", "Onshape", "Online"]);
    const fusion = page.locator('#download .card[data-cad="fusion"]');
    await expect(fusion).toContainText("being rebuilt on this core");
    await expect(fusion.locator("button")).toHaveText("Coming soon");
    await expect(fusion.locator("button")).toBeDisabled();
    await expect(fusion.locator(`a[href="${RELEASES}"]`)).toHaveText("Watch for the release");
    await expect(page.locator('#download .card[data-cad="onshape"]')).toContainText("planned");
    await expect(page.locator('#download .card[data-cad="online"] a.btn')).toHaveAttribute("href", "/");
    await expect(page.locator('#download .card[data-cad="online"] a.btn')).toHaveText("Try Online");
    // nothing pretends to be a file
    const hrefs = await page.locator("#download a").evaluateAll((as) => as.map((a) => a.getAttribute("href")!));
    expect(hrefs.sort()).toEqual(["/", RELEASES].sort());
    expect(await page.locator("a[download]").count()).toBe(0);
    for (const b of await page.locator("#download button").all()) await expect(b).toBeDisabled();
  });

  test("3d · Philosophy leads with \"Make markers where you CAD\", the quotes below it", async ({ page }) => {
    await page.goto("/about/");
    const lead = page.locator("section#philosophy h3").first();
    await expect(lead).toHaveText("Make markers where you CAD");
    await expect(page.locator("#where-you-cad p")).toContainText("rest of the assembly");
    const y = async (sel: string) => (await page.locator(sel).first().boundingBox())!.y;
    expect(await y("#where-you-cad")).toBeLessThan(await y("#philosophy .principles"));
    expect(await page.locator("#philosophy .principles blockquote").count()).toBeGreaterThanOrEqual(7);
  });

  test("3e · profile-first copy: no trim to Rectangle, the profile section, the Fusion 360 slot all or nothing", async ({ page, request }) => {
    await page.goto("/about/");
    await expect(page.locator(".sub")).toHaveText(/^Pick a profile, get a printable, CAD-ready ArUco \/ ChArUco marker\./);
    await expect(page.locator("section#profile h3")).toHaveText("The profile");
    await expect(page.locator("section#trim figcaption")).toHaveText(["Profile", "Marker"]);
    const body = await (await request.get("/about/")).text();
    expect(body).not.toMatch(/draw a rectangle, get/i);
    expect(body).not.toContain("trim-rectangle");
    // the CAD video is shown only once its media exists: never an empty box
    const slot = page.locator("#in-fusion");
    if (await slot.count()) {
      const v = slot.locator("video");
      for (const attr of ["autoplay", "muted", "loop", "playsinline"]) expect(await v.getAttribute(attr), attr).not.toBeNull();
      for (const src of [await v.getAttribute("src"), await v.getAttribute("poster")]) {
        const res = await request.get(src!);
        expect(res.headers()["content-type"], src!).toMatch(/^(image|video)\//);
      }
      await expect(slot.locator("figcaption")).toContainText("In Fusion 360");
    } else {
      expect(body).not.toContain("fusion.mp4");
    }
  });

  test("3f · the new sections carry real captures: heights on the model (two stills), the marker maker (a muted looping clip); the tabs named", async ({ page, request }) => {
    await page.goto("/about/");
    await expect(page.locator("section#heights h3")).toHaveText("Heights on the model");
    await expect(page.locator("section#heights p").first()).toContainText("measured from the white's outer face");
    await expect(page.locator("section#heights p").first()).toContainText("driven from the preset's layers");
    await expect(page.locator("section#canvas h3")).toHaveText("A marker maker on a canvas");
    await expect(page.locator("section#profile p")).toContainText("3 tabs: Make, Marker and Label");
    const stills = await page.locator("section#heights img").evaluateAll((is) => is.map((i) => i.getAttribute("src")!));
    expect(stills).toEqual(["/about/media/heights-driven.webp", "/about/media/heights-set.webp"]);
    const v = page.locator("section#canvas video");
    for (const attr of ["autoplay", "muted", "loop", "playsinline"]) expect(await v.getAttribute(attr), attr).not.toBeNull();
    for (const src of [...stills, await v.getAttribute("src"), await v.getAttribute("poster")]) {
      const res = await request.get(src!);
      expect(res.status(), src!).toBe(200);
      expect(res.headers()["content-type"], src!).toMatch(/^(image|video)\//);
    }
    // drawn, not just present: the clip and both stills have a real size on the page
    for (const el of [v, page.locator("section#heights img").first(), page.locator("section#heights img").last()]) {
      await el.scrollIntoViewIfNeeded();
      expect((await el.boundingBox())!.width).toBeGreaterThan(200);
    }
  });

  test("3g · the 404 page offers Try Online, not Open Studio", async ({ request }) => {
    const res = await request.get("/404.html");
    expect(res.headers()["content-type"]).toContain("text/html");
    const body = await res.text();
    expect(body).toContain('<a href="/">Try Online</a>');
    expect(body).not.toContain("Open Studio");
  });

  test("4 · robots.txt and sitemap.xml are served as files, with their own content types", async ({ request }) => {
    const robots = await request.get("/robots.txt");
    expect(robots.status()).toBe(200);
    expect(robots.headers()["content-type"]).toContain("text/plain");
    const rt = await robots.text();
    expect(rt).toMatch(/^User-agent: \*$/m);
    expect(rt).toMatch(/^Allow: \/$/m);
    expect(rt).toMatch(/^Sitemap: https:\/\/arucostudio\.com\/sitemap\.xml$/m);
    expect(rt).not.toMatch(/^Disallow: \/\s*$/m);

    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.status()).toBe(200);
    expect(sitemap.headers()["content-type"]).toMatch(/xml/);
    const sx = await sitemap.text();
    expect(sx).toContain('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">');
    const locs = [...sx.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
    expect(locs).toEqual(["https://arucostudio.com/", "https://arucostudio.com/about/"]);
  });

  test("5 · the JSON-LD parses: a free SoftwareApplication, the same on / and /about/", async ({ request }) => {
    const [about] = await jsonLd(request, "/about/");
    const [home] = await jsonLd(request, "/");
    for (const ld of [about, home]) {
      expect(ld["@context"]).toBe("https://schema.org");
      expect(ld["@type"]).toBe("SoftwareApplication");
      expect(ld.name).toBe("ArUco Studio");
      expect(ld.url).toBe("https://arucostudio.com/");
      expect(ld.applicationCategory).toBe("DesignApplication");
      expect(ld.operatingSystem).toBe("Web");
      expect(ld.offers).toMatchObject({ "@type": "Offer", price: "0" });
      expect(ld.sameAs).toContain(GITHUB);
    }
    expect(home).toEqual(about);
  });

  test("6 · each page has its own title, description, canonical and social tags", async ({ page }) => {
    const heads: Record<string, Record<string, string | null>> = {};
    for (const [path, canonical] of [["/about/", "https://arucostudio.com/about/"], ["/", "https://arucostudio.com/"]]) {
      await page.goto(path);
      const meta = (sel: string) => page.locator(sel).first().getAttribute("content");
      heads[path] = {
        title: await page.title(), description: await meta('meta[name="description"]'),
        canonical: await page.locator('link[rel="canonical"]').getAttribute("href"),
        ogTitle: await meta('meta[property="og:title"]'), ogImage: await meta('meta[property="og:image"]'),
        twitter: await meta('meta[name="twitter:card"]'),
      };
      expect(heads[path].canonical).toBe(canonical);
      expect(heads[path].ogImage).toBe("https://arucostudio.com/og.png");
      expect(heads[path].twitter).toBe("summary_large_image");
      expect(heads[path].description).toMatch(/ArUco marker generator/);
      for (const term of ["ChArUco", "printable", "Fusion 360", "CAD", "OpenCV"]) expect(heads[path].description).toContain(term);
    }
    expect(heads["/"].title).not.toBe(heads["/about/"].title);
    expect(heads["/"].description).not.toBe(heads["/about/"].description);
  });

  test("7 · every image, the video and its poster are served as media (no SPA fallback)", async ({ page, request }) => {
    await page.goto("/about/");
    const srcs = await page.evaluate(() => [
      ...[...document.querySelectorAll("img")].map((i) => i.getAttribute("src")!),
      ...[...document.querySelectorAll("source[srcset]")].map((s) => s.getAttribute("srcset")!),
      document.querySelector("video")!.getAttribute("src")!, document.querySelector("video")!.getAttribute("poster")!,
    ]);
    expect(srcs.length).toBeGreaterThan(15);
    let bytes = 0;
    for (const src of new Set(srcs)) {
      const res = await request.get(src);
      expect(res.status(), src).toBe(200);
      expect(res.headers()["content-type"], src).toMatch(/^(image|video)\//);
      bytes += (await res.body()).length;
    }
    expect(bytes, "the page's media stays under 3 MB").toBeLessThan(3 * 1024 * 1024);
  });

  test("8 · 390 px wide: no horizontal scroll, nothing past the right edge", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/about/");
    await page.waitForLoadState("load");
    await expect(page.locator("h1")).toHaveText(HEADLINE);   // the landing page, not the Studio's shell
    const m = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const over = [...document.querySelectorAll("body *")]
        .map((e) => ({ tag: e.tagName, cls: (e as HTMLElement).className?.toString?.() ?? "", right: e.getBoundingClientRect().right }))
        .filter((e) => e.right > vw + 0.5);
      return { vw, scroll: document.documentElement.scrollWidth, body: document.body.scrollWidth, over: over.slice(0, 5) };
    });
    expect(m.vw).toBe(390);
    expect(m.scroll, JSON.stringify(m)).toBeLessThanOrEqual(m.vw);
    expect(m.body).toBeLessThanOrEqual(m.vw);
    expect(m.over).toEqual([]);
  });
});
