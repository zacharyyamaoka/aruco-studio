// Skins (web/src/skins/): the main menu's Preferences › Skin switches Studio, Unstyled,
// Fusion 360 and Onshape. A skin changes the panel's look (its computed
// background, accent and font), is remembered across a reload, pins the theme
// of a one-theme CAD program, and never moves the layout beyond its own row
// height. Numbers come from getComputedStyle and getBoundingClientRect.
// SKINS_SHOTS=<dir> also writes a 1280x800 shot of the plate in every skin.
import { expect, test, type Page } from "@playwright/test";
import { clickAt, coreReady, idle, loadExample, openMenu, openStudio, pickSkin, toggleTheme } from "./helpers";

type SkinId = "studio" | "unstyled" | "fusion" | "onshape";
const SKINS: SkinId[] = ["studio", "unstyled", "fusion", "onshape"];

/** Preferences › Theme: enabled (both themes) or greyed out (a one-theme skin). */
async function themeEnabled(page: Page, on: boolean): Promise<void> {
  const m = await openMenu(page, "prefs");
  for (const t of ["theme-light", "theme-dark"]) {
    if (on) await expect(m.getByTestId(t)).not.toHaveAttribute("data-disabled");
    else await expect(m.getByTestId(t)).toHaveAttribute("data-disabled", "");
  }
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("main-menu")).toHaveCount(0);
}

/** The plate with the ArUco Extrude panel open on its face (the profile). */
async function platePanel(page: Page): Promise<void> {
  await openStudio(page);
  await coreReady(page);
  await loadExample(page, "plate");
  await clickAt(page, 60, 40);
  await page.keyboard.press("a");
  await idle(page);
  await expect(page.getByTestId("extrude-panel")).toBeVisible();
  await expect(page.getByTestId("panel-ok")).toBeEnabled();
}

interface Look { bg: string; accent: string; font: string; row: number; width: number;
  rows: { h: number; n: number }[]; kitRows: number[]; head: number; transform: string }

async function look(page: Page): Promise<Look> {
  return page.evaluate(() => {
    const panel = document.querySelector<HTMLElement>("[data-testid=extrude-panel]")!;
    const ok = document.querySelector<HTMLElement>("[data-testid=panel-ok]")!;
    const cs = getComputedStyle(panel);
    const body = panel.querySelector(".fpanel-body")!;
    return {
      bg: cs.backgroundColor,
      accent: getComputedStyle(ok).backgroundColor,
      font: cs.fontFamily,
      row: parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--row")),
      width: panel.getBoundingClientRect().width,
      // the panel's top-level rows: their height and how many 1-row lines they hold
      rows: [...body.children].map((c) => ({
        h: c.getBoundingClientRect().height,
        n: (c.matches(".kit-row") ? 1 : 0) + c.querySelectorAll(".kit-row").length,
      })),
      kitRows: [...body.querySelectorAll(".kit-row")].map((r) => r.getBoundingClientRect().height),
      head: panel.querySelector(".fpanel-head")!.getBoundingClientRect().height,
      transform: getComputedStyle(panel.querySelector(".fpanel-title")!).textTransform,
    };
  });
}

test.describe("skins", () => {
  test("1 · every switch changes the panel's background, accent and font; the layout keeps its boxes", async ({ page }) => {
    await platePanel(page);
    await expect(page.locator("html")).toHaveAttribute("data-skin", "studio");
    // the landing page is Help › About ArUco Studio
    expect(await (await openMenu(page, "help")).getByTestId("brand").getAttribute("href")).toMatch(/\/about\/$/);
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    const looks = new Map<SkinId, Look>([["studio", await look(page)]]);
    // the order makes every switch a real change: Studio and Onshape are both white panels
    for (const id of ["fusion", "onshape", "unstyled", "studio"] as SkinId[]) {
      const before = await look(page);
      await pickSkin(page, id);
      const after = await look(page);
      expect(after.bg, `${id}: background`).not.toBe(before.bg);
      expect(after.accent, `${id}: accent`).not.toBe(before.accent);
      expect(after.font, `${id}: font`).not.toBe(before.font);
      // the logo (the main menu's button): the document pill's own text colour, no underline
      const brand = await page.evaluate(() => {
        const a = document.querySelector("[data-testid=menu-main]")!, bar = document.querySelector("[data-testid=doc-pill]")!;
        return { deco: getComputedStyle(a).textDecorationLine, color: getComputedStyle(a).color, bar: getComputedStyle(bar).color };
      });
      expect(brand.deco, `${id}: brand underline`).toBe("none");
      expect(brand.color, `${id}: brand colour`).toBe(brand.bar);
      looks.set(id, after);
    }
    // no two skins share an accent or a font
    expect(new Set(SKINS.map((s) => looks.get(s)!.accent)).size).toBe(4);
    expect(new Set(SKINS.map((s) => looks.get(s)!.font)).size).toBe(4);
    // Fusion: its sampled panel grey and blue, the uppercase title
    expect(looks.get("fusion")!.bg).toBe("rgb(59, 68, 84)");
    expect(looks.get("fusion")!.accent).toBe("rgb(10, 146, 210)");
    expect(looks.get("fusion")!.transform).toBe("uppercase");
    expect(looks.get("onshape")!.accent).toBe("rgb(6, 69, 170)");
    expect(looks.get("onshape")!.transform).toBe("none");

    const base = looks.get("studio")!;
    for (const id of SKINS) {
      const l = looks.get(id)!;
      const dRow = Math.abs(l.row - base.row);
      // each row is the skin's row height, and the panel keeps its width
      for (const h of l.kitRows) expect(Math.abs(h - l.row), `${id}: a row is --row`).toBeLessThan(0.6);
      expect(l.width, `${id}: width`).toBe(base.width);
      // the same top-level rows, each off by no more than its rows' height change
      expect(l.rows.length, `${id}: rows`).toBe(base.rows.length);
      l.rows.forEach((r, i) => {
        const allowed = r.n * dRow + 4;
        expect(Math.abs(r.h - base.rows[i].h), `${id}: top-level row ${i} (${r.n} rows)`).toBeLessThanOrEqual(allowed);
      });
      expect(Math.abs(l.head - base.head), `${id}: title bar`).toBeLessThanOrEqual(5);
    }
  });

  test("2 · the choice survives a reload; Fusion pins dark, Onshape light, Studio gets the viewer's theme back", async ({ page }) => {
    await openStudio(page);
    const html = page.locator("html");
    // the viewer's own theme: dark
    await toggleTheme(page);
    await expect(html).toHaveAttribute("data-theme", "dark");

    await pickSkin(page, "onshape");
    await expect(html).toHaveAttribute("data-theme", "light");
    await themeEnabled(page, false);
    await page.reload();
    await expect(page.getByTestId("app")).toBeVisible();
    await expect(html).toHaveAttribute("data-skin", "onshape");
    await expect(html).toHaveAttribute("data-theme", "light");
    await themeEnabled(page, false);
    // --panel as a colour (the build minifies the token's text)
    const panelBg = () => page.evaluate(() => {
      const probe = document.body.appendChild(document.createElement("i"));
      probe.style.color = "var(--panel)";
      const c = getComputedStyle(probe).color;
      probe.remove();
      return c;
    });
    expect(await panelBg()).toBe("rgb(255, 255, 255)");

    await pickSkin(page, "fusion");
    await expect(html).toHaveAttribute("data-theme", "dark");
    await page.reload();
    await expect(html).toHaveAttribute("data-skin", "fusion");
    await expect(html).toHaveAttribute("data-theme", "dark");
    expect(await panelBg()).toBe("rgb(59, 68, 84)");

    // Unstyled has both themes: the viewer's dark comes back, and the toggle works
    await pickSkin(page, "unstyled");
    await expect(html).toHaveAttribute("data-theme", "dark");
    await themeEnabled(page, true);
    expect(await panelBg()).toBe("rgb(30, 30, 30)");
    await toggleTheme(page);
    await expect(html).toHaveAttribute("data-theme", "light");
    expect(await panelBg()).toBe("rgb(240, 240, 240)");
    await page.reload();
    await expect(html).toHaveAttribute("data-skin", "unstyled");
    await expect(html).toHaveAttribute("data-theme", "light");

    await pickSkin(page, "studio");
    await page.reload();
    await expect(html).toHaveAttribute("data-skin", "studio");
    await expect(html).toHaveAttribute("data-theme", "light");
    expect(await panelBg()).toBe("rgb(255, 255, 255)");
  });

  test("3 · 390 px wide: no horizontal scroll in any skin, with the panel docked", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openStudio(page);
    await coreReady(page);
    await clickAt(page, 60, 40);
    await page.keyboard.press("a");
    await idle(page);
    await expect(page.getByTestId("extrude-panel")).toBeVisible();
    const noScroll = () => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth && document.body.scrollWidth <= window.innerWidth);
    for (const id of ["unstyled", "fusion", "onshape", "studio"] as SkinId[]) {
      await pickSkin(page, id);
      expect(await noScroll(), `${id}: no horizontal scroll`).toBe(true);
      // the corner pills fit side by side (V2 at 390); GitHub and ? fold into the ⌄ menu
      const left = (await page.getByTestId("doc-pill").boundingBox())!;
      const right = (await page.getByTestId("actions-pill").boundingBox())!;
      expect(left.x, `${id}: the document pill is on screen`).toBeGreaterThanOrEqual(0);
      expect(left.x + left.width, `${id}: the pills do not meet`).toBeLessThan(right.x);
      const print = (await page.getByTestId("act-print").boundingBox())!;
      expect(print.x + print.width, `${id}: the last top button is on screen`).toBeLessThanOrEqual(390);
      const panel = (await page.getByTestId("extrude-panel").boundingBox())!;
      expect(panel.x).toBeLessThanOrEqual(1);
      expect(panel.width).toBeGreaterThanOrEqual(388);
    }
  });

  test("4 · screenshots of the plate in every skin (SKINS_SHOTS)", async ({ page }) => {
    const dir = process.env.SKINS_SHOTS;
    test.skip(!dir, "set SKINS_SHOTS=<dir> to write them");
    await platePanel(page);
    for (const id of SKINS) {
      await pickSkin(page, id);
      await page.mouse.move(640, 790);
      await page.waitForTimeout(150);
      await page.screenshot({ path: `${dir}/skin-${id}.png` });
    }
    await pickSkin(page, "studio");
  });
});
