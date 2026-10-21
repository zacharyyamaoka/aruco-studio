// HostedFiles: the document session, sign-in, autosave and the browser half of the
// reliability promises (SPEC §7 "Save behaviour", v2.4). Framework-free: a UI (the Lit bar,
// a React layout) plugs in through UiHost. WHY no framework import here: this folder is
// copied verbatim into React apps by the shadcn registry (SPEC v2.2, v2.5).

import { Api, FilesApi, filenameFrom, saveBlob, toBlob, type SaveKind } from "./api.js";
import {
  claimLocal,
  claimOrphans,
  deleteDraft,
  deleteDraftIfMine,
  deleteLocal,
  draftKey,
  getDraft,
  listDrafts,
  localKey,
  migrateLegacyDraft,
  putDraft,
  putLocal,
  putStash,
  stashKey,
  tabId,
} from "./drafts.js";
import { HostedFilesError } from "./errors.js";
import { randomId, withExtension } from "./format.js";
import type { Draft, EventName, FileMeta, HostedFilesOptions, Me, State, Status, User } from "./types.js";

export const MSG_OFFLINE = "Not saved online yet — kept on this device";
export const MSG_CONFLICT = "Changed somewhere else — both versions are in History";
export const MSG_EMPTY = "Didn't save an empty document over your file";
export const MSG_UPDATED = "Updated elsewhere";
export const MSG_RESTORED = "Restored your unsaved text";

// SPEC §7.2: retry after 2 s, 5 s, 15 s, 30 s, then every 60 s.
const BACKOFF_MS = [2_000, 5_000, 15_000, 30_000, 60_000];
const CHECKOUT_POLL_MS = 3_000;
const CHECKOUT_POLL_MAX_MS = 10 * 60_000;
// SPEC v2.4: autosave defaults, the working-copy debounce and the keepalive body cap
// (browsers allow 64 KB of keepalive bodies in flight in total).
const AUTOSAVE_IDLE_MS = 1_500;
const AUTOSAVE_MAX_INTERVAL_MS = 20_000;
const LOCAL_DRAFT_MS = 500;
const KEEPALIVE_MAX_BYTES = 60 * 1024;

export const DISCARD = Symbol("discard");

// What the drop-in bar provides. Without a mounted bar the SDK falls back to window.prompt.
export interface UiHost {
  promptName(opts: { title: string; value: string; okLabel?: string; discard?: boolean }): Promise<string | null | typeof DISCARD>;
  showLimit(variant: "files" | "locked"): void;
  closeLimit(): void;
  showOpen(): void;
  showHistory(): void;
  showSignInWaiting(cancel: () => void): () => void;
}

type Listener = (state: State) => void;

export class HostedFiles {
  readonly server: string;
  readonly app: string;
  readonly files: FilesApi;
  readonly ready: Promise<void>;
  ui: UiHost | null = null;

  private api: Api;
  private opts: HostedFilesOptions & { contentType: string; untitledName: string };
  private current: State = { user: null, plan: null, me: null, file: null, status: "signed-out", message: null, lastSavedAt: null, autosave: true };
  private listeners = new Set<Listener>();
  private handlers = new Map<EventName, Set<(payload: unknown) => void>>();
  private dirty = false;
  private saving = 0;
  private docSeq = 0; // bumps on New / Open: a save that lands later must not re-point the editor
  private draftSeq = new Map<string, number>();
  private parked = new Set<string>(); // draft ids refused for good (413, 404 …): not auto-retried
  private limitParked = new Set<string>(); // draft ids refused by the plan (402/423): retried once it is pro
  private untitled: { seq: number; key: string; name: string } | null = null; // the current untitled doc's unacked draft
  private lastFile: FileMeta | null = null; // file context kept across a lost session, for the redirect stash
  private chain: Promise<unknown> = Promise.resolve();
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryIndex = 0;
  private blocked: { key: string; draftId: string; name: string; variant: "files" | "locked" } | null = null;
  private checkoutTimer: ReturnType<typeof setInterval> | null = null;
  private checkoutUntil = 0;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private maxTimer: ReturnType<typeof setTimeout> | null = null;
  private localTimer: ReturnType<typeof setTimeout> | null = null;
  private localChain: Promise<unknown> = Promise.resolve();
  private autosaveTiming: { idleMs: number; maxIntervalMs: number };
  private leaving = false;
  private _initialized = false;
  staleHead: FileMeta | null = null;

  constructor(options: HostedFilesOptions) {
    if (!options?.server || !options.app) throw new HostedFilesError("bad_request", "HostedFiles needs { server, app }");
    this.server = options.server.replace(/\/+$/, "");
    this.app = options.app;
    this.opts = { contentType: "application/json", untitledName: "Untitled", ...options };
    this.api = new Api(this.server, this.app, () => this.token, () => this.dropSession());
    this.files = new FilesApi(this.api, this.opts.contentType);
    const autosave = options.autosave;
    this.autosaveTiming = {
      idleMs: (typeof autosave === "object" && autosave.idleMs) || AUTOSAVE_IDLE_MS,
      maxIntervalMs: (typeof autosave === "object" && autosave.maxIntervalMs) || AUTOSAVE_MAX_INTERVAL_MS,
    };
    this.current.autosave = this.storedAutosave() ?? autosave !== false;
    this.migrateLegacyToken();

    // WHY retry on `online`: an offline save sits in IndexedDB; the moment the network is
    // back it should land without the user doing anything.
    window.addEventListener("online", () => this.retryNow());
    window.addEventListener("focus", () => this.onFocus());
    document.addEventListener("visibilitychange", () => (document.visibilityState === "visible" ? this.onFocus() : this.onHide()));
    window.addEventListener("pagehide", () => this.onHide());
    window.addEventListener("storage", (e) => this.onStorage(e));
    if (this.opts.shortcuts !== false) window.addEventListener("keydown", (e) => this.onKeydown(e));
    if (this.opts.warnOnUnsavedClose !== false) window.addEventListener("beforeunload", (e) => this.onBeforeUnload(e));

    this.ready = this.start().finally(() => {
      this._initialized = true;
      this.notify();
    });
  }

  // ---- state & events ----------------------------------------------------------------

  get state(): State {
    return { ...this.current };
  }

  get user(): User | null {
    return this.current.user;
  }

  get initialized(): boolean {
    return this._initialized;
  }

  get accountUrl(): string {
    return this.current.me?.accountUrl ?? `${this.server}/account/`;
  }

  get hasUnsavedChanges(): boolean {
    return this.dirty;
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    fn(this.state);
    return () => this.listeners.delete(fn);
  }

  on(event: EventName, fn: (payload: any) => void): () => void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(fn);
    return () => this.handlers.get(event)?.delete(fn);
  }

  private emit(event: EventName, payload?: unknown): void {
    for (const fn of this.handlers.get(event) ?? []) {
      try {
        fn(payload);
      } catch (err) {
        console.error(err);
      }
    }
  }

  private set(patch: Partial<State>): void {
    this.current = { ...this.current, ...patch };
    this.notify();
  }

  private notify(): void {
    const snapshot = this.state;
    for (const fn of this.listeners) fn(snapshot);
  }

  private setStatus(status: Status, message: string | null = null): void {
    this.set({ status, message });
  }

  private settledStatus(): void {
    if (!this.current.user) this.setStatus("signed-out");
    else if (this.dirty) this.setStatus("dirty");
    else this.setStatus(this.current.file ? "saved" : "idle");
  }

  // ---- start-up ----------------------------------------------------------------------

  private get tokenKey(): string {
    return `shf:${this.app}:token`;
  }

  // SPEC v2.1: a bearer kept by the Cloud Save SDK moves to the new key; the legacy copy goes
  // only once the new one is written.
  private migrateLegacyToken(): void {
    try {
      const legacyKey = `cloudsave:${this.app}:token`;
      const legacy = localStorage.getItem(legacyKey);
      if (legacy === null) return;
      if (localStorage.getItem(this.tokenKey) === null) localStorage.setItem(this.tokenKey, legacy);
      if (localStorage.getItem(this.tokenKey) !== null) localStorage.removeItem(legacyKey);
    } catch {}
  }

  private get token(): string | null {
    try {
      return localStorage.getItem(this.tokenKey);
    } catch {
      return null;
    }
  }

  private async start(): Promise<void> {
    await this.finishRedirectSignIn();
    const fromCheckout = new URL(location.href).searchParams.get("shf_checkout") === "success";
    try {
      if (this.token && !this.current.user) {
        try {
          await this.loadMe();
        } catch (err) {
          if (err instanceof HostedFilesError && err.retryable) this.scheduleRetry();
        }
      }
      await this.restoreStash();
      await this.restoreLocal();
      // WHY on start: a save that never reached the server (offline, crash, closed tab)
      // is still in IndexedDB; it lands now. Returning from checkout, it also opens.
      if (this.current.user) await this.enqueue(() => this.flushDrafts({ open: fromCheckout }));
    } finally {
      // Stripped last, once the fresh plan is loaded, so a reload doesn't repeat it.
      this.stripCheckoutParam();
    }
  }

  private stripCheckoutParam(): void {
    const url = new URL(location.href);
    if (!url.searchParams.has("shf_checkout")) return;
    url.searchParams.delete("shf_checkout");
    history.replaceState(history.state, "", url.toString());
  }

  async me(): Promise<Me> {
    return this.loadMe();
  }

  private async loadMe(): Promise<Me> {
    const me = await this.api.me();
    const wasSignedOut = !this.current.user;
    this.set({ user: me.user, me, plan: me.plan });
    if (wasSignedOut) this.settledStatus();
    return me;
  }

  private refreshMeQuietly(): void {
    this.loadMe().catch(() => {});
  }

  // ---- auth (SPEC §4) ----------------------------------------------------------------

  async signIn(): Promise<User> {
    if (this.current.user) return this.current.user;
    const state = randomId();
    const connect = `${this.server}/connect?app=${encodeURIComponent(this.app)}&origin=${encodeURIComponent(location.origin)}&state=${state}`;
    if (this.opts.signInMode === "redirect") return this.redirectSignIn(connect, state);
    const width = 440;
    const height = 640;
    const left = Math.max(0, window.screenX + (window.outerWidth - width) / 2);
    const top = Math.max(0, window.screenY + (window.outerHeight - height) / 3);
    const popup = window.open(`${connect}&mode=popup`, "shf-signin", `popup,width=${width},height=${height},left=${left},top=${top}`);
    // WHY the redirect fallback: a blocked popup must not leave the user unable to sign in.
    if (!popup) return this.redirectSignIn(connect, state);

    const serverOrigin = new URL(this.server).origin;
    return new Promise<User>((resolve, reject) => {
      let done = false;
      let closedSince = 0;
      const cleanup = () => {
        done = true;
        window.removeEventListener("message", onMessage);
        clearInterval(watch);
        closeOverlay?.();
      };
      const fail = (err: HostedFilesError) => {
        if (done) return;
        cleanup();
        try {
          popup.close();
        } catch {}
        reject(err);
      };
      const onMessage = async (event: MessageEvent) => {
        if (event.origin !== serverOrigin) return;
        const data = event.data as { type?: string; token?: string; state?: string } | null;
        if (!data || data.type !== "shf:token" || data.state !== state || !data.token) return;
        cleanup();
        try {
          resolve(await this.exchange(data.token));
        } catch (err) {
          reject(err);
        }
      };
      // The popup posts its message right before closing itself; give that message a moment
      // to arrive before treating a closed popup as "closed by the user".
      const watch = setInterval(() => {
        if (!popup.closed) return;
        closedSince ||= Date.now();
        if (Date.now() - closedSince > 1_500) fail(new HostedFilesError("popup_closed", "The sign-in window was closed"));
      }, 300);
      window.addEventListener("message", onMessage);
      const closeOverlay = this.ui?.showSignInWaiting(() => fail(new HostedFilesError("popup_closed", "Sign-in cancelled")));
    });
  }

  private get stashMarker(): string {
    return `shf:${this.app}:stash`;
  }

  private async redirectSignIn(connect: string, state: string): Promise<never> {
    sessionStorage.setItem(`shf:${this.app}:state`, state);
    try {
      await this.stashForRedirect();
    } catch (err) {
      console.warn("Simple Hosted Files: could not keep the unsaved text for the sign-in round trip", err);
    }
    const back = new URL(location.href);
    back.hash = "";
    this.leaving = true;
    location.assign(`${connect}&mode=redirect&return=${encodeURIComponent(back.toString())}`);
    return new Promise<never>(() => {});
  }

  // WHY stash before leaving: the redirect sign-in navigates this page away, and the app's
  // unsaved text would go with it (SPEC §7.1). The stash is a draft outside the save queue,
  // so it comes back into the editor rather than being uploaded behind the user's back.
  private async stashForRedirect(): Promise<void> {
    const content = await this.snapshot();
    if (content.size === 0) return;
    const file = this.current.file ?? this.lastFile;
    const id = randomId();
    const key = stashKey(this.app, id);
    await putStash(key, {
      app: this.app,
      fileId: file?.id ?? null,
      baseVersion: file?.version ?? null,
      name: file?.name ?? this.opts.untitledName,
      contentType: content.type || this.opts.contentType,
      content,
      savedAt: new Date().toISOString(),
      tab: tabId,
      id,
    });
    sessionStorage.setItem(this.stashMarker, key);
  }

  // Back from a redirect sign-in (this tab's sessionStorage names the stash): put the text
  // back into the app, marked unsaved, with its file context if it had one.
  private async restoreStash(): Promise<void> {
    let key: string | null = null;
    try {
      key = sessionStorage.getItem(this.stashMarker);
    } catch {}
    if (!key) return;
    const stash = await getDraft(key).catch(() => undefined);
    if (!stash) {
      sessionStorage.removeItem(this.stashMarker);
      return;
    }
    let file: FileMeta | null = null;
    if (stash.fileId && this.current.user) {
      try {
        const head = await this.files.get(stash.fileId);
        // WHY keep the stashed base version: if the file moved on meanwhile, the next save
        // is refused as stale and lands "ours on top" instead of hiding the other edit.
        file = { ...head, version: stash.baseVersion ?? head.version };
      } catch {}
    }
    this.nextDoc();
    this.staleHead = null;
    await this.opts.setContent(stash.content, file);
    this.set({ file });
    this.dirty = true;
    this.set({ status: this.current.user ? "dirty" : "signed-out", message: MSG_RESTORED });
    // WHY delete only now: until the text is back in the app, the stash is its only copy.
    // The leaving page's working copy holds the same text, so it goes too.
    this.flushLocal();
    await this.localChain;
    if (stash.tab && stash.tab !== tabId) await deleteLocal(this.app, stash.tab).catch(() => {});
    await deleteDraft(key).catch(() => {});
    sessionStorage.removeItem(this.stashMarker);
  }

  // SPEC v2.4: the working copy a closed or reloaded tab left behind comes back into the app,
  // marked unsaved. An untitled one always; one of an existing file only when signed in (its
  // file context needs the server) and only if the server does not already have that text.
  private async restoreLocal(): Promise<void> {
    if (this.dirty) return; // a redirect stash came back instead
    const signedIn = !!this.current.user;
    let draft: Draft | null;
    try {
      draft = await claimLocal(this.app, (d) => !d.fileId || signedIn);
    } catch (err) {
      console.warn("Simple Hosted Files: could not read the local working copy", err);
      return;
    }
    if (!draft) return;
    let file: FileMeta | null = null;
    if (draft.fileId) {
      try {
        const head = await this.files.get(draft.fileId);
        if (head.sha256 === (await sha256Hex(draft.content))) {
          await deleteLocal(this.app).catch(() => {}); // it landed (a keepalive autosave)
          return;
        }
        // WHY keep the draft's base version: if the file moved on meanwhile, the next save is
        // refused as stale and lands "ours on top" instead of hiding the other edit.
        if (!head.trashedAt) file = { ...head, version: draft.baseVersion ?? head.version };
      } catch (err) {
        if (err instanceof HostedFilesError && err.retryable) {
          // Can't tell yet whether it landed: hand it back for a later load, never drop it.
          await putDraft(localKey(this.app, randomId()), { ...draft, tab: undefined }).catch(() => {});
          await deleteLocal(this.app).catch(() => {});
          return;
        }
        // Gone or not ours any more: the text comes back as an untitled document.
      }
    }
    this.nextDoc();
    this.staleHead = null;
    await this.opts.setContent(draft.content, file);
    this.set({ file });
    this.dirty = true;
    this.set({ status: signedIn ? "dirty" : "signed-out", message: MSG_RESTORED });
    this.flushLocal();
    this.scheduleAutosave();
  }

  private async finishRedirectSignIn(): Promise<void> {
    if (!location.hash.includes("shf_token=")) return;
    const params = new URLSearchParams(location.hash.slice(1));
    const oneTime = params.get("shf_token");
    const state = params.get("shf_state");
    const stateKey = `shf:${this.app}:state`;
    const expected = sessionStorage.getItem(stateKey);
    sessionStorage.removeItem(stateKey);
    params.delete("shf_token");
    params.delete("shf_state");
    const rest = params.toString();
    history.replaceState(history.state, "", location.pathname + location.search + (rest ? `#${rest}` : ""));
    if (!oneTime || !state || state !== expected) return;
    try {
      await this.exchange(oneTime);
    } catch (err) {
      console.warn("Simple Hosted Files: sign-in hand-off failed", err);
    }
  }

  private async exchange(oneTimeToken: string): Promise<User> {
    const { token } = await this.api.json<{ token: string; user: User }>("POST", "/v1/session/exchange", { body: { token: oneTimeToken } });
    localStorage.setItem(this.tokenKey, token);
    const me = await this.loadMe();
    this.emit("signin", me.user);
    // Drafts left by an earlier signed-in session land now.
    void this.enqueue(() => this.flushDrafts({}));
    return me.user;
  }

  async signOut(): Promise<void> {
    const token = this.token;
    if (token) {
      try {
        await fetch(`${this.server}/api/auth/sign-out`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: "{}",
          credentials: "omit",
        });
      } catch {}
    }
    this.dropSession();
    this.emit("signout");
  }

  // Forget the session locally. Drafts stay in IndexedDB and land after the next sign-in.
  private dropSession(): void {
    try {
      localStorage.removeItem(this.tokenKey);
    } catch {}
    this.stopCheckoutPoll();
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    this.blocked = null;
    this.staleHead = null;
    this.untitled = null;
    this.lastFile = this.current.file ?? this.lastFile;
    this.nextDoc();
    this.set({ user: null, me: null, plan: null, file: null, status: "signed-out", message: null });
  }

  private onStorage(event: StorageEvent): void {
    if (event.key === this.autosaveKey) {
      const on = this.storedAutosave();
      if (on !== null && on !== this.current.autosave) this.applyAutosave(on);
      return;
    }
    if (event.key !== this.tokenKey) return;
    if (!event.newValue && this.current.user) this.dropSession();
    else if (event.newValue && !this.current.user) this.refreshMeQuietly();
  }

  // ---- document session --------------------------------------------------------------

  markDirty(): void {
    this.dirty = true;
    this.staleHead = null;
    if (this.current.user && !this.saving) this.setStatus("dirty");
    this.scheduleLocal();
    this.scheduleAutosave();
  }

  // A different document is now in the app: saves still in flight must not re-point the
  // editor, and the previous document's autosave timers are void.
  private nextDoc(): void {
    this.docSeq++;
    this.clearAutosaveTimers();
  }

  // ---- autosave (SPEC v2.4) --------------------------------------------------------------

  private get autosaveKey(): string {
    return `shf:${this.app}:autosave`;
  }

  private storedAutosave(): boolean | null {
    try {
      const value = localStorage.getItem(this.autosaveKey);
      return value === null ? null : value === "true";
    } catch {
      return null;
    }
  }

  // The user's choice; it outlives the page and overrides the `autosave` option.
  setAutosave(on: boolean): void {
    try {
      localStorage.setItem(this.autosaveKey, String(on));
    } catch {}
    this.applyAutosave(on);
  }

  private applyAutosave(on: boolean): void {
    this.set({ autosave: on });
    if (!on) this.clearAutosaveTimers();
    else if (this.dirty) this.scheduleAutosave();
  }

  // WHY only existing, unlocked files: the free plan has 3 files, so autosave never creates
  // one the user didn't ask for; a view-only file would only be refused.
  private get canAutosave(): boolean {
    const file = this.current.file;
    return this.current.autosave && !!this.current.user && !!file && !file.locked && !file.trashedAt && !this.blocked;
  }

  // Fires idleMs after the last change, or maxIntervalMs after the first unsaved one while
  // typing never pauses.
  private scheduleAutosave(): void {
    if (!this.canAutosave) return;
    const seq = this.docSeq;
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => this.autosave(seq), this.autosaveTiming.idleMs);
    this.maxTimer ??= setTimeout(() => this.autosave(seq), this.autosaveTiming.maxIntervalMs);
  }

  private clearAutosaveTimers(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    if (this.maxTimer) clearTimeout(this.maxTimer);
    this.idleTimer = null;
    this.maxTimer = null;
  }

  private autosave(seq: number, keepalive = false): void {
    this.clearAutosaveTimers();
    if (seq !== this.docSeq) return;
    this.enqueue(async () => {
      if (seq !== this.docSeq || !this.dirty || !this.canAutosave) return null;
      return this.saveNow({ kind: "auto", keepalive });
    }).catch(() => {});
  }

  // The page is being hidden or unloaded: keep the working copy now and send the autosave
  // with fetch keepalive so it can outlive the page (SPEC v2.4).
  private onHide(): void {
    if (this.localTimer) this.flushLocal();
    if (this.dirty && this.canAutosave) this.autosave(this.docSeq, true);
  }

  // ---- the local working copy (SPEC v2.4) ----------------------------------------------

  private scheduleLocal(): void {
    if (this.localTimer) clearTimeout(this.localTimer);
    this.localTimer = setTimeout(() => this.flushLocal(), LOCAL_DRAFT_MS);
  }

  // Brings the working copy in line with the app: the current text while it is unsaved,
  // nothing once it is saved or handed to the save queue (whose draft then covers it).
  private flushLocal(): void {
    if (this.localTimer) clearTimeout(this.localTimer);
    this.localTimer = null;
    this.localChain = this.localChain
      .then(async () => {
        if (!this.dirty) return deleteLocal(this.app);
        const content = await this.snapshot();
        const file = this.current.file;
        await putLocal(this.app, {
          app: this.app,
          fileId: file?.id ?? null,
          baseVersion: file?.version ?? null,
          name: file?.name ?? this.opts.untitledName,
          contentType: content.type || this.opts.contentType,
          content,
          savedAt: new Date().toISOString(),
          tab: tabId,
          id: randomId(),
        });
      })
      .catch((err) => console.warn("Simple Hosted Files: could not keep the local working copy", err));
  }

  private enqueue<T>(task: () => Promise<T>): Promise<T> {
    // WHY one queue: saves, retries and opens never interleave, so a base version is
    // always the one the previous step left behind.
    const run = this.chain.then(task, task);
    this.chain = run.catch(() => {});
    return run;
  }

  private async snapshot(): Promise<Blob> {
    return toBlob(await this.opts.getContent(), this.opts.contentType);
  }

  private async askName(title: string, value: string, okLabel = "Save"): Promise<string | null> {
    if (this.ui) {
      const answer = await this.ui.promptName({ title, value, okLabel });
      return typeof answer === "string" ? answer : null;
    }
    const answer = window.prompt(title, value);
    return answer?.trim() ? answer.trim() : null;
  }

  save(opts: { allowEmpty?: boolean } = {}): Promise<FileMeta | null> {
    return this.enqueue(() => this.saveNow(opts));
  }

  private async saveNow(opts: { allowEmpty?: boolean; kind?: SaveKind; keepalive?: boolean } = {}): Promise<FileMeta | null> {
    if (!this.current.user) await this.signIn();
    const file = this.current.file;
    if (!file) {
      // An untitled doc already saved once (offline, or blocked by the plan) keeps its name and
      // its draft key: saving it again replaces that draft instead of making a second file.
      const pending = this.untitled?.seq === this.docSeq ? this.untitled : null;
      const name = pending?.name ?? (await this.askName("Save", this.opts.untitledName));
      if (name === null) return null;
      return this.commit(null, null, name, await this.snapshot(), pending?.key);
    }
    const content = await this.snapshot();
    // WHY the empty guard: "blank editor saved over the file" is the commonest way to lose
    // a document; versions would recover it, but refusing is kinder (SPEC §7.6).
    if (content.size === 0 && file.size > 0 && !opts.allowEmpty) {
      this.setStatus("error", MSG_EMPTY);
      const err = new HostedFilesError("empty", MSG_EMPTY);
      err.reported = true;
      this.emit("error", err);
      throw err;
    }
    return this.commit(file.id, file.version, file.name, content, undefined, opts);
  }

  saveAs(name?: string): Promise<FileMeta | null> {
    return this.enqueue(async () => {
      if (!this.current.user) await this.signIn();
      const chosen = name ?? (await this.askName("Save as", this.current.file?.name ?? this.opts.untitledName));
      if (chosen === null) return null;
      return this.commit(null, null, chosen, await this.snapshot());
    });
  }

  // One save: draft to IndexedDB, send, then drop the draft once the server has it.
  private async commit(
    fileId: string | null,
    baseVersion: number | null,
    name: string,
    content: Blob,
    reuseKey?: string,
    opts: { kind?: SaveKind; keepalive?: boolean } = {},
  ): Promise<FileMeta> {
    const draft: Draft = {
      app: this.app,
      fileId,
      baseVersion,
      name,
      contentType: content.type || this.opts.contentType,
      content,
      savedAt: new Date().toISOString(),
      tab: tabId,
      id: randomId(),
      kind: opts.kind ?? "manual",
    };
    this.dirty = false;
    this.clearAutosaveTimers();
    this.flushLocal(); // the queue draft below now holds this text
    this.draftSeq.set(draft.id!, this.docSeq);
    const key = reuseKey ?? draftKey(this.app, fileId, draft.id!);
    if (!fileId && !this.current.file) this.untitled = { seq: this.docSeq, key, name };
    return this.send(key, draft, opts.keepalive);
  }

  private async send(key: string, draft: Draft, keepalive = false): Promise<FileMeta> {
    const seq = this.draftSeq.get(draft.id!) ?? -1;
    this.saving++;
    this.setStatus("saving");
    // WHY the draft goes to IndexedDB before the network: a crash, a closed tab or an
    // offline save must never lose the edit (SPEC promise 7). On the way out of the page
    // (keepalive) the write is issued first but not awaited, so the request still starts
    // before the page is gone.
    const kept = putDraft(key, draft).catch((err) => {
      console.warn("Simple Hosted Files: could not keep a local draft (saving online anyway)", err);
    });
    if (!keepalive) await kept;
    try {
      const { meta, conflicted } = await this.upload(draft, keepalive);
      await kept;
      // WHY delete the draft only after the ack: until the server has the bytes, the
      // draft is the only copy of the edit.
      await deleteDraftIfMine(key, draft.id).catch(() => {});
      this.saving--;
      if (this.untitled?.key === key) this.untitled = null;
      this.landed(draft, meta, seq, conflicted);
      return meta;
    } catch (err) {
      this.saving--;
      const error = err instanceof HostedFilesError ? err : new HostedFilesError("error", String(err));
      await kept;
      this.failed(error, key, draft, seq);
      throw error;
    }
  }

  private async upload(draft: Draft, keepalive = false): Promise<{ meta: FileMeta; conflicted: boolean }> {
    if (!draft.fileId) return { meta: await this.files.create(draft.name, draft.content), conflicted: false };
    const opts = { kind: draft.kind, keepalive: keepalive && draft.content.size <= KEEPALIVE_MAX_BYTES };
    try {
      return { meta: await this.files.write(draft.fileId, draft.content, draft.baseVersion ?? 0, opts), conflicted: false };
    } catch (err) {
      if (!(err instanceof HostedFilesError) || err.code !== "conflict") throw err;
      // WHY "ours on top": a stale save is refused (409), so we write ours as the new head.
      // Theirs stays in history as the version below — neither side is dropped (SPEC §7.3).
      let head = (err.details.head as FileMeta | undefined) ?? (await this.files.get(draft.fileId));
      for (let attempt = 0; ; attempt++) {
        try {
          const meta = await this.files.write(draft.fileId, draft.content, head.version, opts);
          return { meta, conflicted: !meta.unchanged };
        } catch (again) {
          if (attempt >= 3 || !(again instanceof HostedFilesError) || again.code !== "conflict") throw again;
          head = (again.details.head as FileMeta | undefined) ?? (await this.files.get(draft.fileId));
        }
      }
    }
  }

  private landed(draft: Draft, meta: FileMeta, seq: number, conflicted: boolean): void {
    this.retryIndex = 0;
    this.draftSeq.delete(draft.id!);
    if (this.blocked?.draftId === draft.id) this.blocked = null;
    const isCurrent = seq === this.docSeq && (draft.fileId === null || this.current.file?.id === draft.fileId);
    if (isCurrent) this.set({ file: meta });
    this.set({ lastSavedAt: new Date().toISOString() });
    if (conflicted) {
      this.setStatus("conflict", MSG_CONFLICT);
      this.emit("conflict", meta);
    } else if (!this.saving) {
      this.settledStatus();
    }
    if (!draft.fileId) this.refreshMeQuietly();
    this.emit("save", meta);
  }

  private failed(err: HostedFilesError, key: string, draft: Draft, seq: number): void {
    err.reported = true;
    if (seq !== this.docSeq && !err.retryable) {
      // A recovered or earlier document the user is not looking at: keep its draft quietly
      // (it is retried at the next start) rather than popping a dialog about another file.
      if (err.code === "file_limit" || err.code === "locked") this.limitParked.add(draft.id!);
      else if (err.code !== "unauthorized") this.parked.add(draft.id!);
      console.warn(`Simple Hosted Files: kept the local draft of "${draft.name}" (${err.code})`);
      if (!this.saving) this.settledStatus();
      return;
    }
    if (err.retryable) {
      // The draft stays in IndexedDB; the retry loop and the `online` event land it.
      this.setStatus("offline", MSG_OFFLINE);
      this.scheduleRetry();
      return;
    }
    if (err.code === "file_limit" || err.code === "locked") {
      // WHY keep the draft: hitting the plan limit must never cost the edit. It is retried
      // as soon as the plan allows it (SPEC §7.4).
      const variant = err.code === "locked" ? "locked" : "files";
      this.blocked = { key, draftId: draft.id!, name: draft.name, variant };
      // The server says view-only: mark it so autosave stops sending what it will refuse.
      const file = this.current.file;
      if (variant === "locked" && file && file.id === draft.fileId) this.set({ file: { ...file, locked: true } });
      this.limitParked.add(draft.id!);
      this.setStatus("error", variant === "locked" ? "View-only on the free plan — not saved" : "Not saved online — free file limit reached");
      this.ui?.showLimit(variant);
      this.emit("limit", { variant, error: err });
      return;
    }
    if (err.code === "unauthorized") return; // signed out; the draft lands after the next sign-in
    this.parked.add(draft.id!);
    if (seq === this.docSeq) this.dirty = true;
    this.setStatus("error", err.message);
    this.emit("error", err);
  }

  private scheduleRetry(): void {
    if (this.retryTimer) return;
    const delay = BACKOFF_MS[Math.min(this.retryIndex, BACKOFF_MS.length - 1)];
    this.retryIndex++;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.retryNow();
    }, delay);
  }

  private retryNow(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    void this.enqueue(async () => {
      if (!this.current.user) {
        if (!this.token) return;
        try {
          await this.loadMe();
        } catch (err) {
          if (err instanceof HostedFilesError && err.retryable) this.scheduleRetry();
          return;
        }
      }
      await this.flushDrafts({});
    });
  }

  // Sends every pending draft this tab owns, plus orphans from tabs that are gone.
  private async flushDrafts(opts: { open?: boolean }): Promise<void> {
    if (!this.current.user) return;
    let pending: [string, Draft][];
    let orphans: [string, Draft][];
    try {
      await migrateLegacyDraft(this.app);
      pending = (await listDrafts(this.app)).filter(([, d]) => d.tab === tabId);
      orphans = await claimOrphans(this.app);
    } catch (err) {
      console.warn("Simple Hosted Files: could not read local drafts", err);
      return;
    }
    const all = [...pending, ...orphans].filter(([, d]) => !this.parked.has(d.id!) && !this.limitParked.has(d.id!));
    for (const [key, draft] of all) {
      try {
        const meta = await this.send(key, draft);
        if (opts.open && !this.current.file && !this.dirty) await this.load(meta);
      } catch (err) {
        if (err instanceof HostedFilesError && err.retryable) return; // backoff is scheduled
      }
    }
  }

  // ---- New / Open / History ------------------------------------------------------------

  // SPEC §8: New / Open with unsaved changes save the current file first; an untitled,
  // non-empty document asks "Save this first?". Returns false when the user cancels.
  private async settleBeforeLeaving(): Promise<boolean> {
    if (!this.dirty || !this.current.user) return true;
    // An untitled doc that already has a pending draft saves silently, like a file does.
    if (this.current.file || this.untitled?.seq === this.docSeq) {
      try {
        await this.saveNow();
        return true;
      } catch (err) {
        // Offline is fine to leave: the draft is on this device and will land.
        return err instanceof HostedFilesError && err.retryable;
      }
    }
    const content = await this.snapshot();
    if (content.size === 0) return true;
    const answer = this.ui
      ? await this.ui.promptName({ title: "Save this first?", value: this.opts.untitledName, okLabel: "Save", discard: true })
      : window.confirm("Save this document first?")
        ? this.opts.untitledName
        : DISCARD;
    if (answer === DISCARD) return true;
    if (answer === null) return false;
    try {
      await this.commit(null, null, answer, content);
      return true;
    } catch (err) {
      return err instanceof HostedFilesError && err.retryable;
    }
  }

  newFile(): Promise<void> {
    return this.enqueue(async () => {
      if (!(await this.settleBeforeLeaving())) return;
      this.nextDoc();
      this.dirty = false;
      this.staleHead = null;
      this.set({ file: null });
      await this.opts.newDocument?.();
      this.dirty = false;
      this.flushLocal();
      this.settledStatus();
    });
  }

  open(id: string): Promise<FileMeta | null> {
    return this.enqueue(async () => {
      if (!(await this.settleBeforeLeaving())) return null;
      const meta = await this.files.get(id);
      await this.load(meta);
      return meta;
    });
  }

  // Loads a file's head into the app via setContent and makes it the current file.
  private async load(meta: FileMeta): Promise<void> {
    const blob = await this.files.read(meta.id, { version: meta.version });
    this.nextDoc();
    this.staleHead = null;
    await this.opts.setContent(blob, meta);
    this.dirty = false; // WHY after setContent: some editors fire change events while loading
    this.flushLocal();
    this.set({ file: meta, lastSavedAt: meta.updatedAt });
    this.settledStatus();
    this.emit("open", meta);
  }

  openPicker(): void {
    this.ui?.showOpen();
  }

  showHistory(): void {
    if (this.current.file) this.ui?.showHistory();
  }

  restoreVersion(n: number): Promise<FileMeta | null> {
    return this.enqueue(async () => {
      const file = this.current.file;
      if (!file) return null;
      if (!(await this.settleBeforeLeaving())) return null;
      const meta = await this.files.restoreVersion(file.id, n);
      await this.load(meta);
      return meta;
    });
  }

  // "Move to trash" on the current file: unsaved changes are saved first, then the app
  // gets a new document. The file stays restorable from the trash for 30 days.
  trashCurrent(): Promise<void> {
    return this.enqueue(async () => {
      const file = this.current.file;
      if (!file) return;
      if (!(await this.settleBeforeLeaving())) return;
      await this.files.trash(file.id);
      this.nextDoc();
      this.staleHead = null;
      this.set({ file: null });
      await this.opts.newDocument?.();
      this.dirty = false;
      this.flushLocal();
      this.settledStatus();
      this.refreshMeQuietly();
    });
  }

  // Shows an error from a UI action in the status line.
  report(err: unknown): void {
    const error = err instanceof HostedFilesError ? err : new HostedFilesError("error", err instanceof Error ? err.message : String(err));
    if (error.code === "network") this.setStatus("error", "Can't reach Simple Hosted Files — try again");
    else this.setStatus("error", error.message);
    this.emit("error", error);
  }

  rename(name: string): Promise<FileMeta | null> {
    return this.enqueue(async () => {
      const file = this.current.file;
      if (!file) return null;
      const meta = await this.files.rename(file.id, name);
      this.patchFile(meta);
      return this.current.file;
    });
  }

  // Applies name / trash / lock changes of the current file from a server answer.
  // WHY keep our version: the base of our next save must stay the version we last loaded
  // or saved, or a newer head written elsewhere would be overwritten without a conflict.
  patchFile(meta: FileMeta): void {
    const file = this.current.file;
    if (!file || file.id !== meta.id) return;
    this.set({ file: { ...file, name: meta.name, locked: meta.locked, trashedAt: meta.trashedAt, purgeAt: meta.purgeAt } });
  }

  // The bar's "Reload" after "Updated elsewhere" (SPEC §7.7).
  reload(): Promise<void> {
    return this.enqueue(async () => {
      const head = this.staleHead;
      if (!head || this.dirty) return;
      await this.load(head);
    });
  }

  private onFocus(): void {
    if (this.blocked || this.limitParked.size || this.checkoutTimer) void this.checkPlan();
    void this.checkHead();
  }

  private async checkHead(): Promise<void> {
    const file = this.current.file;
    if (!file || this.dirty || this.saving || !this.current.user) return;
    const seq = this.docSeq;
    let head: FileMeta;
    try {
      head = await this.files.get(file.id);
    } catch {
      return;
    }
    if (seq !== this.docSeq || this.dirty || this.saving || this.current.file?.id !== head.id) return;
    this.patchFile(head);
    if (head.version > file.version) {
      this.staleHead = head;
      this.set({ message: `${MSG_UPDATED} — Reload` });
    }
  }

  // ---- limit, checkout ------------------------------------------------------------------

  get blockedSave(): { name: string; variant: "files" | "locked" } | null {
    return this.blocked ? { name: this.blocked.name, variant: this.blocked.variant } : null;
  }

  private returnUrl(): string {
    const url = new URL(location.href);
    url.hash = "";
    url.searchParams.delete("shf_checkout");
    return url.toString();
  }

  // Opens checkout in a new tab and watches for the plan to turn pro.
  async upgrade(): Promise<void> {
    // WHY open the tab before the request: a window opened after an await is a popup the
    // browser may block; one opened inside the click is not.
    const tab = window.open("", "_blank");
    try {
      const { url } = await this.api.json<{ url: string }>("POST", "/v1/billing/checkout", { body: { returnUrl: this.returnUrl() } });
      if (tab) {
        tab.opener = null;
        tab.location.href = url;
      } else {
        this.leaving = true;
        location.assign(url); // the draft is on disk; it lands when checkout returns here
        return;
      }
    } catch (err) {
      tab?.close();
      throw err;
    }
    this.startCheckoutPoll();
  }

  async manageBilling(): Promise<void> {
    const tab = window.open("", "_blank");
    try {
      const { url } = await this.api.json<{ url: string }>("POST", "/v1/billing/portal", { body: { returnUrl: this.returnUrl() } });
      if (tab) {
        tab.opener = null;
        tab.location.href = url;
      } else location.assign(url);
    } catch (err) {
      tab?.close();
      throw err;
    }
    this.startCheckoutPoll();
  }

  private startCheckoutPoll(): void {
    this.stopCheckoutPoll();
    this.checkoutUntil = Date.now() + CHECKOUT_POLL_MAX_MS;
    this.checkoutTimer = setInterval(() => {
      if (Date.now() > this.checkoutUntil) this.stopCheckoutPoll();
      else void this.checkPlan();
    }, CHECKOUT_POLL_MS);
  }

  private stopCheckoutPoll(): void {
    if (this.checkoutTimer) clearInterval(this.checkoutTimer);
    this.checkoutTimer = null;
  }

  private async checkPlan(): Promise<void> {
    const before = this.current.plan;
    let me: Me;
    try {
      me = await this.loadMe();
    } catch {
      return;
    }
    if (me.plan !== "pro") return;
    this.stopCheckoutPoll();
    if (before === "pro" && !this.blocked && !this.limitParked.size) return;
    this.ui?.closeLimit();
    this.blocked = null;
    this.limitParked.clear();
    // WHY retry here: the user upgraded to save these; every draft the plan refused lands
    // now, and the blocked document becomes the open file without pressing Save again (SPEC §7.4).
    await this.enqueue(() => this.flushDrafts({}));
  }

  // "Don't save" on a blocked document: the user chose to let it go.
  async discardBlocked(): Promise<void> {
    const blocked = this.blocked;
    this.blocked = null;
    if (blocked) await deleteDraft(blocked.key).catch(() => {});
  }

  // ---- downloads, export -----------------------------------------------------------------

  private filename(name: string): string {
    return withExtension(name, this.current.me?.app?.extension);
  }

  // Saves what the app shows right now to disk (the limit dialog's "Download instead").
  async downloadLocal(): Promise<void> {
    const name = this.blocked?.name ?? this.current.file?.name ?? this.opts.untitledName;
    saveBlob(await this.snapshot(), this.filename(name));
  }

  async downloadCurrent(): Promise<void> {
    const file = this.current.file;
    if (file && !this.dirty) await this.files.download(file.id);
    else await this.downloadLocal();
  }

  async exportAll(): Promise<void> {
    const res = await this.api.request("GET", "/v1/export");
    saveBlob(await res.blob(), filenameFrom(res) ?? "simple-hosted-files-export.zip");
  }

  // ---- browser hooks ---------------------------------------------------------------------

  private onKeydown(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      this.save().catch(() => {});
    }
  }

  private onBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.leaving) return;
    if (this.dirty || this.saving > 0) {
      event.preventDefault();
      event.returnValue = "";
    }
  }

  // ---- UI -------------------------------------------------------------------------------

  mount(target: string | HTMLElement): void {
    const host = typeof target === "string" ? document.querySelector(target) : target;
    if (!host) throw new HostedFilesError("bad_request", `HostedFiles.mount: ${String(target)} not found`);
    // By tag name, so this file needs no UI import; the element exists once the bar is loaded.
    const bar = document.createElement("hosted-files-bar") as HTMLElement & { cloud: HostedFiles };
    bar.cloud = this;
    host.append(bar);
  }

  // Used by the bar to drive the low-level file actions it shows.
  get untitledName(): string {
    return this.opts.untitledName;
  }
}

async function sha256Hex(blob: Blob): Promise<string | null> {
  try {
    const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return null; // no WebCrypto (insecure origin): treat it as not landed
  }
}
