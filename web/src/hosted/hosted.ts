// The Studio's one HostedFiles instance, made on first use and bound to
// useStudio, and the two things the Studio adds to it: one name, and leaving
// the cloud file before the app replaces the document itself.
// WHY once per page, outside React: the instance owns window listeners
// (Ctrl+S, focus, pagehide) and the session; StrictMode would make two in a
// component (simple-hosted-files web/src/notes.ts does the same).
import { HostedFiles } from "./core";
import { studioAdapter, type StudioAdapter } from "./adapter";
import { HOSTED_APP, hostedServer } from "./config";
import { isFilling, useStudio } from "../store";

export const APP_NAME = "ArUco Studio";

let hosted: HostedFiles | null = null;
let adapter: StudioAdapter | null = null;

export function hostedFiles(): HostedFiles {
  if (hosted) return hosted;
  adapter = studioAdapter(useStudio, isFilling);
  // autosave is the app's policy, "all" (simple-hosted-files server/apps.json,
  // SPEC v2.10): signed in, a new document's first edit creates its file, so
  // nobody has to press Save (Zach, 2026-10-21: "having to manually press
  // ctrl S is so old school!"); File › Autosave turns it off per user.
  // WHY no unsaved-changes prompt on leaving: signed out the Studio works as
  // it did before (no prompt), and every change is kept in the local draft,
  // which the next load brings back (SPEC v2.4).
  hosted = new HostedFiles({ server: hostedServer(), app: HOSTED_APP, appName: APP_NAME, warnOnUnsavedClose: false, ...adapter.options });
  adapter.bind(hosted);
  oneName(hosted, adapter);
  // SPEC v2.11: Duplicate opens "Copy of <name>" in a new tab at ?file=<id>;
  // this opens that file there (and takes the parameter off the address).
  // Once per page, so here, where the one instance is made.
  void hosted.openFromUrl();
  return hosted;
}

/** The cloud file's name IS the document's name (Zach, 2026-10-20 night):
 *  a rename of either renames the other. */
function oneName(h: HostedFiles, adapter: StudioAdapter): void {
  // the file's name moved (Save's name prompt, Save as, a rename in Open…)
  let seen: { id: string; name: string } | null = null;
  h.subscribe(({ file }) => {
    const was = seen;
    seen = file ? { id: file.id, name: file.name } : null;
    if (!file || (was?.id === file.id && was.name === file.name)) return;
    adapter.nameNext(null);
    useStudio.getState().setName(file.name);
  });
  // the document's name moved (the title bar); not while the core puts a
  // document in: its file is still the one being left
  useStudio.subscribe((s, prev) => {
    if (s.doc.name === prev.doc.name || adapter.applying()) return;
    const file = h.state.file;
    if (file && file.name !== s.doc.name) h.rename(s.doc.name).catch((err) => h.report(err));
  });
}

/** Save's and Save as's name prompt answered: the file is written with that
 *  name in it. WHY: else the first version holds the old name and the
 *  document taking the file's name autosaves a second one at once. */
export function nameNextSave(name: string): void {
  adapter?.nameNext(name);
}

/** Before the app replaces the document itself (an example, a file from this
 *  computer): leave the document through the SDK's New, its changes saved, so
 *  autosave never writes the other document into its file. False when it could
 *  not be left (a save that failed, "Save this first?" cancelled).
 *  WHY untitled documents too (review finding #2, 2026-10-21): an untitled
 *  document's first autosave can be creating its file; replaced behind the
 *  SDK's back, that file then landed on the next document, which autosaved
 *  into it. New waits for the save queue and starts a new document generation.
 *  It left when it put a new document in (adapter.applying() during the change). */
export async function leaveFile(): Promise<boolean> {
  const h = hostedFiles();
  let left = false;
  const un = useStudio.subscribe((s, prev) => { if (s.doc !== prev.doc && adapter?.applying()) left = true; });
  try {
    await h.newFile();
  } catch (err) {
    h.report(err);
  } finally {
    un();
  }
  return left;
}

/** File › New: the SDK's New (it saves or asks about the document left). */
export function newDocument(): void {
  const h = hostedFiles();
  h.newFile().catch((err) => h.report(err));
}

/** The title bar's rename: the document's name, and so its cloud file's
 *  (oneName). The server's rule (SPEC §5 PATCH): 1–200 characters after
 *  trimming the ends, no "/" or control characters. */
export function renameDocument(name: string): void {
  const st = useStudio.getState();
  const clean = name.trim();
  if (!clean || clean === st.doc.name) return;
  if (/[/\u0000-\u001f\u007f]/.test(clean)) { st.say("A name can't contain / or control characters."); return; }
  st.setName(clean);
}
