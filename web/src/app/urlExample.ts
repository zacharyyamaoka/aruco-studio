// ?example=<name>: open a document the site serves, web/public/examples/<name>.arucostudio-web.json
// (/examples/<name>.arucostudio-web.json), the way File › Examples opens one: the cloud file open is
// left first (its changes saved), then the document replaces the one in the editor.
// WHY (Zach, 2026-10-21): the guides link straight to a board you open yourself -- "an example
// board you can open up yourself and see all the boards there, and then you run the built-in
// Verify" (docs/build_guides.py writes the label placement board and the link to it).
// WHY a file the site serves, not one in the bundle: the guide's builder writes it, and the same
// file is the page's "Download the board file".
// WHY after the hosted files start (HostedFiles.ready): that start brings back the working copy a
// closed tab left (SPEC v2.4) through the same loadDoc; opened before it, the example would be
// replaced by that copy a moment later.
// WHY the parameter is taken off the address at once: a reload keeps the edits made since, instead
// of opening the example over them.
import { parseDoc } from "../model/doc";
import { useStudio } from "../store";
import { hostedFiles, leaveFile } from "../hosted/hosted";
import { leaveHome } from "./home";

export const EXAMPLE_PARAM = "example";
/** A served example's name: lower-case letters, digits and dashes (no path, no dots). */
const NAME = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;

/** The example the address asks for: its name when it is a valid one, "" when the parameter is
 *  there but is not a name, null when there is none. */
export function exampleName(search: string): string | null {
  const v = new URLSearchParams(search).get(EXAMPLE_PARAM);
  if (v === null) return null;
  return NAME.test(v) ? v : "";
}

/** Where the site serves an example. */
export function exampleUrl(name: string, base = "/"): string {
  return `${base}examples/${name}.arucostudio-web.json`;
}

/** The address without ?example= (the rest of the query and the hash kept). */
export function withoutExample(href: string): string {
  const url = new URL(href);
  url.searchParams.delete(EXAMPLE_PARAM);
  return url.pathname + url.search + url.hash;
}

/** Open the example the address names, if any (main.tsx, once, at start). */
export async function openExampleFromUrl(): Promise<void> {
  if (typeof window === "undefined") return;
  const name = exampleName(location.search);
  if (name === null) return;
  history.replaceState(history.state, "", withoutExample(location.href));
  const say = (text: string) => useStudio.getState().say(text);
  if (!name) { say("That example link is not a valid example name."); return; }
  try {
    const res = await fetch(exampleUrl(name, import.meta.env.BASE_URL));
    // WHY the type too: a dev server answers a missing file with the app's own page (200, HTML)
    if (res.status === 404 || (res.ok && !(res.headers.get("content-type") ?? "").includes("json"))) {
      throw new Error("there is no such example");
    }
    if (!res.ok) throw new Error(`the site answered ${res.status}`);
    const doc = parseDoc(await res.text());
    await hostedFiles().ready;
    if (!(await leaveFile())) return;
    useStudio.getState().loadDoc(doc);
    leaveHome();
    say(`Opened the example “${doc.name}”`);
  } catch (e) {
    say(`Could not open the example “${name}”: ${(e as Error).message}`);
  }
}
