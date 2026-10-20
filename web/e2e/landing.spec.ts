// The landing page (/about/, written by docs/build_landing.py) and what
// crawlers read: robots.txt, sitemap.xml, the JSON-LD and the <noscript> on /.
// Every check reads what the server sends (content types, the raw HTML) or
// what is drawn (scrollWidth, getBoundingClientRect), so the SPA fallback
// (index.html for any missing path) can never pass for a real file.
//
//   E2E_PORT=5393 npx playwright test --project=e2e e2e/landing.spec.ts
import { expect, test, type APIRequestContext } from "@playwright/test";

const GITHUB = "https://github.com/zacharyyamaoka/aruco-studio";
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
      for (const id of ["what", "philosophy", "cad", "qa"]) await expect(page.locator(`section#${id} h2`)).toBeVisible();
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

  test("3 · the two calls to action: Open Studio -> /, GitHub -> the repo", async ({ page }) => {
    await page.goto("/about/");
    await expect(page.locator('[data-cta="studio"]')).toHaveAttribute("href", "/");
    await expect(page.locator('[data-cta="studio"]')).toHaveText("Open Studio");
    await expect(page.locator('[data-cta="github"]')).toHaveAttribute("href", GITHUB);
    await expect(page.locator('[data-cta="github"]')).toHaveText("GitHub");
    for (const cta of ["studio", "github"]) {
      const b = (await page.locator(`[data-cta="${cta}"]`).boundingBox())!;
      expect(b.y + b.height, `${cta} is above the fold`).toBeLessThan(800);
    }
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
