// The Studio's half of Simple Hosted Files: what a cloud file is (the
// `.arucostudio-web.json` text, serialise / parseDoc of ../model/doc.ts) and
// when it changed (the document, never the view). The core (./core, a copy of
// simple-hosted-files' client/src/core) does the rest: sign-in, Save / Open,
// History, autosave, the local draft, If-Match.
//
// Pure of the core: it takes the store and, once made, the core's markDirty,
// so vitest runs it with fakes (adapter.test.ts).
import type { StoreApi } from "zustand";
import type { HostedFilesOptions } from "./core/types";
import { parseDoc, serialise } from "../model/doc";
import type { Studio } from "../store";

/** What the adapter needs of useStudio: its state and its changes. */
export type StudioStore = Pick<StoreApi<Pick<Studio, "doc" | "loadDoc" | "newDoc">>, "getState" | "subscribe">;

export type StudioContent = Pick<HostedFilesOptions, "getContent" | "setContent" | "newDocument" | "contentType" | "untitledName">;

export interface StudioAdapter {
  /** spread into new HostedFiles({ server, app, ...options }) */
  options: StudioContent;
  /** markDirty on every change of the document; returns the unsubscribe */
  bind(core: { markDirty(): void }): () => void;
  /** true while the core is putting a document in (setContent, newDocument) */
  applying(): boolean;
  /** the name the next save writes into the file, before the document takes
   *  it from the saved file (null: the document's own) */
  nameNext(name: string | null): void;
}

/** `quiet`: a change of the document that is not an edit (the store's own
 *  fill-ins, store.ts isFilling) */
export function studioAdapter(store: StudioStore, quiet: () => boolean = () => false): StudioAdapter {
  // WHY: a document the core puts in (Open, History, New, a restored draft)
  // is not an edit; marked dirty, an opened file would read "Unsaved changes"
  // and autosave itself straight back.
  let applying = false;
  let naming: string | null = null;
  const apply = (fn: () => void) => {
    applying = true;
    try { fn(); } finally { applying = false; }
  };
  return {
    options: {
      contentType: "application/json",
      untitledName: "Untitled",
      // the file is exactly what Save writes to disk today (commands.ts saveDoc)
      getContent: () => {
        const doc = store.getState().doc;
        return serialise(naming && naming !== doc.name ? { ...doc, name: naming } : doc);
      },
      // WHY the file's name wins (Zach, 2026-10-20 night: "the cloud file's
      // name IS the document's name"): a rename made elsewhere changes only
      // the file's name, not the bytes saved before it
      setContent: async (blob, file) => {
        const doc = parseDoc(await blob.text());
        naming = null;
        apply(() => store.getState().loadDoc(file ? { ...doc, name: file.name } : doc));
      },
      newDocument: () => { naming = null; apply(() => store.getState().newDoc()); },
    },
    // by the document's identity: a Doc is never mutated (store.ts), and the
    // selection, camera, panel and the core's answers live beside it
    bind: (core) => store.subscribe((s, prev) => {
      if (s.doc !== prev.doc && !applying && !quiet()) core.markDirty();
    }),
    applying: () => applying,
    nameNext: (name) => { naming = name; },
  };
}
