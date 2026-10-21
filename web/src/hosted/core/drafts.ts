// The local draft queue (SPEC §7 "Save behaviour" 1-2): IndexedDB via idb-keyval,
// database "shf-drafts", object store "drafts", key "<app>:<fileId>" for an existing
// file and "<app>:new:<draftId>" for an untitled one. Two side namespaces live in the same
// store and are never uploaded: "<app>:stash:<id>" (redirect sign-in) and "<app>:local:<tab>"
// (the working copy every markDirty keeps, SPEC v2.4).

import { createStore, entries, get, promisifyRequest, set, type UseStore } from "idb-keyval";
import { randomId } from "./format.js";
import type { Draft } from "./types.js";

const DB_NAME = "shf-drafts";
const LEGACY_DB_NAME = "cloudsave-drafts";

let store: UseStore | null = null;
function drafts(): UseStore {
  store ??= createStore(DB_NAME, "drafts");
  return store;
}

// Every access waits for the one-time move out of the legacy database, so nothing reads
// or writes the new store before the old records are in it.
async function db(): Promise<UseStore> {
  await migrateLegacyDatabase();
  return drafts();
}

// ---- legacy database (SPEC v2.1) -------------------------------------------------------

let migration: Promise<void> | null = null;
export function migrateLegacyDatabase(): Promise<void> {
  migration ??= moveLegacyDatabase().catch((err) => {
    console.warn("Simple Hosted Files: could not move drafts out of the old database (they stay there)", err);
  });
  return migration;
}

// Opens a database only if it already exists: aborting the upgrade of a new one rolls its
// creation back, so probing never leaves an empty legacy database behind.
function openExisting(name: string): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    const req = indexedDB.open(name);
    req.onupgradeneeded = () => req.transaction?.abort();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(null);
    req.onblocked = () => resolve(null);
  });
}

function isNewer(a: Draft | undefined, b: Draft | undefined): boolean {
  return !b || new Date(a?.savedAt ?? 0).getTime() > new Date(b.savedAt ?? 0).getTime();
}

// WHY move, never drop: a legacy draft can be the only copy of an edit. Each record is
// copied into "shf-drafts" first; only once that transaction has committed is the legacy
// record deleted, and only if it is still the value we copied.
async function moveLegacyDatabase(): Promise<void> {
  if (typeof indexedDB === "undefined") return;
  const legacy = await openExisting(LEGACY_DB_NAME);
  if (!legacy) return;
  try {
    if (!legacy.objectStoreNames.contains("drafts")) return;
    const read = legacy.transaction("drafts", "readonly").objectStore("drafts");
    const [keys, values] = await Promise.all([promisifyRequest(read.getAllKeys()), promisifyRequest(read.getAll())]);
    if (!keys.length) return;
    const records = keys.map((key, i) => [key, values[i] as Draft] as const);
    await drafts()("readwrite", (s) => {
      for (const [key, draft] of records) {
        const req = s.get(key);
        req.onsuccess = () => {
          if (isNewer(draft, req.result as Draft | undefined)) s.put(draft, key);
        };
      }
      return promisifyRequest(s.transaction);
    });
    const write = legacy.transaction("drafts", "readwrite");
    const legacyStore = write.objectStore("drafts");
    for (const [key, draft] of records) {
      const req = legacyStore.get(key);
      req.onsuccess = () => {
        const now = req.result as Draft | undefined;
        if (now && now.savedAt === draft.savedAt && now.id === draft.id) legacyStore.delete(key);
      };
    }
    await promisifyRequest(write);
    // WHY the emptied database is left in place: deleting it would wait on any tab still
    // running the old SDK and could take a draft that tab writes meanwhile.
  } finally {
    legacy.close();
  }
}

// ---- tabs ------------------------------------------------------------------------------

// Each page load is a tab with its own id, held as a Web Lock for the page's lifetime.
// WHY: a draft whose owner tab is still open is that tab's to retry; only a draft whose
// owner is gone (closed, crashed, reloaded) is adopted at start. Two tabs racing the same
// "new" draft would otherwise create the file twice.
export const tabId = randomId();
const locks: LockManager | undefined = typeof navigator !== "undefined" ? navigator.locks : undefined;
locks?.request(`shf-tab:${tabId}`, () => new Promise<never>(() => {})).catch(() => {});

// WHY the draft id in an untitled key: two untitled documents saved while offline must
// never overwrite each other's draft (SPEC §7.1).
export function draftKey(app: string, fileId: string | null, draftId: string): string {
  return fileId ? `${app}:${fileId}` : `${app}:new:${draftId}`;
}

// Round-1 SDKs wrote untitled drafts under "<app>:new". Move such a record to a unique key
// (one transaction: the copy is written before the old key goes) — never drop it.
export async function migrateLegacyDraft(app: string): Promise<void> {
  const legacy = `${app}:new`;
  return (await db())("readwrite", (s) => {
    const req = s.get(legacy);
    req.onsuccess = () => {
      const draft = req.result as Draft | undefined;
      if (!draft) return;
      const id = draft.id ?? randomId();
      s.put({ ...draft, id }, draftKey(app, null, id));
      s.delete(legacy);
    };
    return promisifyRequest(s.transaction);
  });
}

export async function putDraft(key: string, draft: Draft): Promise<void> {
  return set(key, draft, await db());
}

// Deletes the draft only if it is still the one we sent. WHY: another save of the same
// file (this tab later, or another tab) may have replaced it with newer content, which
// must survive our ack.
export async function deleteDraftIfMine(key: string, id: string | undefined): Promise<void> {
  return (await db())("readwrite", (s) => {
    const req = s.get(key);
    req.onsuccess = () => {
      if ((req.result as Draft | undefined)?.id === id) s.delete(key);
    };
    return promisifyRequest(s.transaction);
  });
}

export async function deleteDraft(key: string): Promise<void> {
  return (await db())("readwrite", (s) => {
    s.delete(key);
    return promisifyRequest(s.transaction);
  });
}

function isSideKey(app: string, key: string): boolean {
  return key.startsWith(`${app}:stash:`) || key.startsWith(`${app}:local:`);
}

export async function listDrafts(app: string): Promise<[string, Draft][]> {
  const all = await entries<string, Draft>(await db());
  return all.filter(([key, draft]) => key.startsWith(`${app}:`) && !isSideKey(app, key) && draft?.app === app && draft.content instanceof Blob);
}

// The redirect sign-in stash (SPEC §7.1): the unsaved content kept across the trip to
// /connect. It is restored into the editor, never uploaded, so it lives outside the queue.
export function stashKey(app: string, id: string): string {
  return `${app}:stash:${id}`;
}

export function putStash(key: string, draft: Draft): Promise<void> {
  return putDraft(key, draft);
}

export async function getDraft(key: string): Promise<Draft | undefined> {
  return get<Draft>(key, await db());
}

// ---- the working copy (SPEC v2.4) --------------------------------------------------------

// One per tab: what the editor showed at the last markDirty. Restored on the next load, never
// uploaded (WHY: the free plan has 3 files; a reload must not create a file nobody asked for).
export function localKey(app: string, tab = tabId): string {
  return `${app}:local:${tab}`;
}

export function putLocal(app: string, draft: Draft): Promise<void> {
  return putDraft(localKey(app), draft);
}

export function deleteLocal(app: string, tab = tabId): Promise<void> {
  return deleteDraft(localKey(app, tab));
}

async function ownerIsGone(draft: Draft): Promise<boolean> {
  if (!draft.tab) return true;
  if (draft.tab === tabId) return false;
  if (!locks) {
    // No Web Locks (insecure origin): assume a draft untouched for a minute is orphaned.
    return Date.now() - new Date(draft.savedAt).getTime() > 60_000;
  }
  return locks.request(`shf-tab:${draft.tab}`, { ifAvailable: true }, async (lock) => lock !== null);
}

function underAppLock<T>(app: string, run: () => Promise<T>): Promise<T> {
  return locks ? locks.request(`shf-drafts:${app}`, run) : run();
}

// Adopts the newest working copy left by a tab that is gone (and accepted by `accept`):
// it becomes this tab's working copy in one transaction, under the cross-tab lock, so two
// freshly opened tabs never restore the same text. Other orphans wait for a later load.
export function claimLocal(app: string, accept: (draft: Draft) => boolean): Promise<Draft | null> {
  return underAppLock(app, async () => {
    const all = await entries<string, Draft>(await db());
    let best: [string, Draft] | null = null;
    for (const [key, draft] of all) {
      if (!key.startsWith(`${app}:local:`) || draft?.app !== app || !(draft.content instanceof Blob)) continue;
      if (!accept(draft) || !(await ownerIsGone(draft))) continue;
      if (!best || isNewer(draft, best[1])) best = [key, draft];
    }
    if (!best) return null;
    const [oldKey, draft] = best;
    const mine: Draft = { ...draft, tab: tabId };
    await (await db())("readwrite", (s) => {
      s.put(mine, localKey(app));
      if (oldKey !== localKey(app)) s.delete(oldKey);
      return promisifyRequest(s.transaction);
    });
    return mine;
  });
}

// Claims the orphaned drafts of `app` for this tab, under one cross-tab lock so two
// freshly opened tabs never both adopt the same draft.
export function claimOrphans(app: string): Promise<[string, Draft][]> {
  return underAppLock(app, async () => {
    const claimed: [string, Draft][] = [];
    for (const [key, draft] of await listDrafts(app)) {
      if (!(await ownerIsGone(draft))) continue;
      const mine = { ...draft, tab: tabId, id: draft.id ?? randomId() };
      await putDraft(key, mine);
      claimed.push([key, mine]);
    }
    return claimed;
  });
}
