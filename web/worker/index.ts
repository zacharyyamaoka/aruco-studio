// arucostudio.com's Worker: the static site (assets), plus ArUco Studio's sign-in, which is the Simple Hosted
// Files Worker reached through a service binding (simple-hosted-files SPEC v2.9).
// WHY sign-in runs on this domain: Google's consent screen names the app only once its brand is verified, and
// that needs every redirect domain to be ours; on the shared workers.dev host it shows the raw domain instead
// (Zach 2026-10-21: "I want it to say ArUco Studio with the logo").
// WHY a proxy and not a copy: the hosted-files Worker stays the one sign-in implementation. It picks ArUco
// Studio's own Google client from the request's host, so the request must reach it with arucostudio.com as its
// host. assets.run_worker_first (wrangler.jsonc) sends only these paths here; everything else is a static
// file, exactly as before.

export interface Fetcher {
  fetch(request: Request): Promise<Response>;
}

export interface Env {
  ASSETS: Fetcher;
  HOSTED_FILES: Fetcher;
}

/** What the hosted /connect pop-up uses on its own origin: Better Auth (incl. Google's callback), the page, its /v1/me checks. */
export const SIGN_IN_PATHS: RegExp[] = [/^\/api\/auth\//, /^\/connect(\/|$)/, /^\/v1\/me(\/keep)?$/];

export const isSignInPath = (pathname: string): boolean => SIGN_IN_PATHS.some((path) => path.test(pathname));

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    if (!isSignInPath(new URL(request.url).pathname)) return env.ASSETS.fetch(request);
    // The request as it came: same URL (so the same host), method, body, cookies and Origin.
    // WHY redirect manual: Better Auth answers with redirects (to Google, back to /connect) that are the browser's to follow.
    return env.HOSTED_FILES.fetch(new Request(request, { redirect: "manual" }));
  },
};
