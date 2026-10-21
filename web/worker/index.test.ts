// The arucostudio.com proxy: sign-in paths reach the hosted-files binding unchanged; the rest are static assets.
import { describe, expect, it } from "vitest";
import proxy, { isSignInPath, type Env } from "./index";

function fakeEnv() {
  const seen: { binding: string; request: Request }[] = [];
  const binding = (name: string) => ({
    fetch: async (request: Request) => {
      seen.push({ binding: name, request });
      return new Response(name, { status: 302, headers: { Location: "https://accounts.google.com/o/oauth2/v2/auth", "Set-Cookie": "s=1; Path=/; HttpOnly" } });
    },
  });
  const env: Env = { ASSETS: binding("assets"), HOSTED_FILES: binding("hosted") };
  return { env, seen };
}

describe("worker/index.ts", () => {
  it("routes exactly the sign-in paths to the hosted-files binding", () => {
    for (const path of ["/api/auth/callback/google", "/api/auth/sign-in/social", "/connect", "/connect/", "/v1/me", "/v1/me/keep"]) {
      expect(isSignInPath(path), path).toBe(true);
    }
    for (const path of ["/", "/about/", "/privacy/", "/terms/", "/brand/logo-120.png", "/connected", "/v1/files", "/v1/me/delete", "/api/other"]) {
      expect(isSignInPath(path), path).toBe(false);
    }
  });

  it("forwards method, body, cookies, Origin and the arucostudio.com URL as they came, and hands back the redirect as is", async () => {
    const { env, seen } = fakeEnv();
    const res = await proxy.fetch(
      new Request("https://arucostudio.com/api/auth/sign-in/social", {
        method: "POST",
        headers: { Origin: "https://arucostudio.com", Cookie: "a=b", "Content-Type": "application/json" },
        body: JSON.stringify({ provider: "google" }),
      }),
      env,
    );
    expect(seen.map((s) => s.binding)).toEqual(["hosted"]);
    const sent = seen[0].request;
    expect(sent.url).toBe("https://arucostudio.com/api/auth/sign-in/social");
    expect(sent.method).toBe("POST");
    expect(sent.headers.get("Origin")).toBe("https://arucostudio.com");
    expect(sent.headers.get("Cookie")).toBe("a=b");
    expect(await sent.json()).toEqual({ provider: "google" });
    expect(sent.redirect).toBe("manual");
    expect(res.status).toBe(302);
    expect(res.headers.get("Set-Cookie")).toBe("s=1; Path=/; HttpOnly");
  });

  it("serves everything else from the assets", async () => {
    const { env, seen } = fakeEnv();
    await proxy.fetch(new Request("https://arucostudio.com/about/"), env);
    expect(seen.map((s) => s.binding)).toEqual(["assets"]);
  });
});
