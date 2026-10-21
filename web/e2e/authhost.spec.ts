// ArUco Studio's own sign-in host (simple-hosted-files SPEC v2.9): with the
// Studio's per-app Google client set, the sign-in pop-up opens on the
// Studio's OWN origin and runs there through worker/index.ts, so Google's
// consent screen is for ArUco Studio's client and comes back to this domain.
// Runs against the Studio served by `wrangler dev` (assets + the proxy) and a
// local hosted-files bound to it, with fake per-app secrets:
//   hosted-files: DEMOS=0 SERVER_PORT=8878 DEV_AUTH_HOSTS='{"aruco-studio":"http://localhost:8879"}'
//                 GOOGLE_CLIENT_ID_ARUCO_STUDIO=<fake> GOOGLE_CLIENT_SECRET_ARUCO_STUDIO=<fake> node scripts/dev.mjs
//   Studio:       VITE_HOSTED_FILES_SERVER=http://localhost:8878 npm run build, then
//                 wrangler dev --port 8879 --local-upstream localhost:8879 --upstream-protocol http
//   E2E_AUTH_HOST=1 E2E_BASE_URL=http://localhost:8879 E2E_HOSTED_SERVER=http://localhost:8878 E2E_AUTH_CLIENT_ID=<fake> npx playwright test e2e/authhost.spec.ts --project e2e
// Google itself is stubbed: the test stops at its authorize URL.
import { expect, test } from "@playwright/test";

const HOSTED = process.env.E2E_HOSTED_SERVER ?? "";
const CLIENT_ID = process.env.E2E_AUTH_CLIENT_ID ?? ""; // the fake GOOGLE_CLIENT_ID_ARUCO_STUDIO given to hosted-files
test.skip(!process.env.E2E_AUTH_HOST || !HOSTED || !CLIENT_ID, "needs the Studio under wrangler dev with its sign-in proxy: E2E_AUTH_HOST=1, E2E_BASE_URL, E2E_HOSTED_SERVER, E2E_AUTH_CLIENT_ID");

test("Continue with Google opens the sign-in pop-up on the Studio's own origin, with its own client", async ({ page, context }) => {
  const google: string[] = [];
  const connects: string[] = [];
  context.on("request", (request) => {
    if (new URL(request.url()).pathname === "/connect") connects.push(request.url());
  });
  await context.route("https://accounts.google.com/**", (route) => {
    google.push(route.request().url());
    return route.fulfill({ contentType: "text/html", body: "<title>Google (stub)</title>stub" });
  });
  await page.goto("/?core=mock");
  await expect(page.getByTestId("app")).toBeVisible();
  const studio = new URL(page.url()).origin;
  expect(studio).not.toBe(new URL(HOSTED).origin);

  if (!(await page.getByTestId("doc-menu").count())) await page.getByTestId("menu-doc").click();
  await page.getByTestId("doc-menu").getByTestId("shf-signin").click();
  const dialog = page.getByTestId("shf-signin-dialog");
  await expect(dialog.getByTestId("shf-signin-google")).toBeVisible();
  await Promise.all([page.waitForEvent("popup"), dialog.getByTestId("shf-signin-google").click()]);

  await expect.poll(() => google.length, { message: "the pop-up reached Google" }).toBeGreaterThan(0);
  // The pop-up's /connect is this site's (through the proxy), never the hosted-files server's.
  expect(connects.length).toBeGreaterThan(0);
  for (const url of connects) expect(new URL(url).origin, url).toBe(studio);
  expect(new URL(connects[0]).searchParams.get("app")).toBe("aruco-studio");
  // Google is asked for ArUco Studio's own client, and comes back to this site.
  const authorize = new URL(google[0]);
  expect(authorize.origin + authorize.pathname).toBe("https://accounts.google.com/o/oauth2/v2/auth");
  expect(authorize.searchParams.get("client_id")).toBe(CLIENT_ID);
  expect(authorize.searchParams.get("redirect_uri")).toBe(`${studio}/api/auth/callback/google`);
});
