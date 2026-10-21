// ?example=<name> (./urlExample.ts): the name read from the address, the served file's URL, the
// address cleaned, and the open itself against fakes of the store, the hosted files and the site.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { emptyDoc, serialise } from "../model/doc";

const calls = vi.hoisted(() => ({ loaded: [] as unknown[], said: [] as string[], left: 0, ready: 0, home: 0 }));

vi.mock("../store", () => ({
  useStudio: { getState: () => ({ loadDoc: (d: unknown) => calls.loaded.push(d), say: (t: string) => calls.said.push(t) }) },
}));
vi.mock("../hosted/hosted", () => ({
  hostedFiles: () => ({ ready: Promise.resolve().then(() => { calls.ready += 1; }) }),
  leaveFile: () => { calls.left += 1; return Promise.resolve(true); },
}));
vi.mock("./home", () => ({ leaveHome: () => { calls.home += 1; } }));

import { exampleName, exampleUrl, openExampleFromUrl, withoutExample } from "./urlExample";

describe("the example's name", () => {
  it("is read from ?example=, and only a plain name is one", () => {
    expect(exampleName("")).toBeNull();
    expect(exampleName("?core=mock")).toBeNull();
    expect(exampleName("?example=label-placement")).toBe("label-placement");
    expect(exampleName("?core=mock&example=a1")).toBe("a1");
    for (const bad of ["../index", "a.b", "A", "-a", "a-", "a/b", "", "x".repeat(65)]) {
      expect(exampleName(`?example=${encodeURIComponent(bad)}`), bad).toBe("");
    }
  });

  it("names the file the site serves, under its base", () => {
    expect(exampleUrl("label-placement")).toBe("/examples/label-placement.arucostudio-web.json");
    expect(exampleUrl("a", "/studio/")).toBe("/studio/examples/a.arucostudio-web.json");
  });

  it("is taken off the address, the rest kept", () => {
    expect(withoutExample("https://arucostudio.com/?example=label-placement")).toBe("/");
    expect(withoutExample("https://arucostudio.com/?core=mock&example=x#shf=1")).toBe("/?core=mock#shf=1");
  });
});

describe("opening it", () => {
  const replaced: string[] = [];
  const page = (search: string, answer: () => Response) => {
    vi.stubGlobal("window", {});
    vi.stubGlobal("location", { search, href: `https://arucostudio.com/${search}` });
    vi.stubGlobal("history", { state: null, replaceState: (_s: unknown, _t: string, url: string) => replaced.push(url) });
    vi.stubGlobal("fetch", vi.fn(async () => answer()));
  };
  beforeEach(() => { calls.loaded.length = 0; calls.said.length = 0; calls.left = calls.ready = calls.home = 0; replaced.length = 0; });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("loads the served document after the hosted files start, as File › Examples does, and cleans the address", async () => {
    const doc = { ...emptyDoc("Label placement test board") };
    page("?example=label-placement", () => new Response(serialise(doc), { headers: { "content-type": "application/json" } }));
    await openExampleFromUrl();
    expect(fetch).toHaveBeenCalledWith("/examples/label-placement.arucostudio-web.json");
    expect(replaced).toEqual(["/"]);
    expect([calls.ready, calls.left, calls.home]).toEqual([1, 1, 1]);
    expect(calls.loaded).toHaveLength(1);
    expect((calls.loaded[0] as { name: string }).name).toBe("Label placement test board");
    expect(calls.said).toEqual(["Opened the example “Label placement test board”"]);
  });

  it("says so when there is no such example (a 404, or a dev server's page in its place)", async () => {
    for (const answer of [() => new Response("not found", { status: 404 }),
      () => new Response("<!doctype html>", { headers: { "content-type": "text/html" } })]) {
      calls.said.length = 0;
      page("?example=nope", answer);
      await openExampleFromUrl();
      expect(calls.loaded).toHaveLength(0);
      expect(calls.said).toEqual(["Could not open the example “nope”: there is no such example"]);
    }
  });

  it("refuses a name that is not one without asking the site, and does nothing without the parameter", async () => {
    page("?example=..%2Fsecret", () => new Response("{}"));
    await openExampleFromUrl();
    expect(fetch).not.toHaveBeenCalled();
    expect(calls.said).toEqual(["That example link is not a valid example name."]);
    calls.said.length = 0;
    page("", () => new Response("{}"));
    await openExampleFromUrl();
    expect(fetch).not.toHaveBeenCalled();
    expect(calls.said).toEqual([]);
  });
});
