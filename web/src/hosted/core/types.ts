// Shapes shared with the server (SPEC §5) and the SDK's public surface (SPEC §7).

export interface User {
  id: string;
  email: string;
  name: string | null;
  image: string | null;
}

export interface FileMeta {
  id: string;
  app: string;
  name: string;
  contentType: string;
  version: number;
  size: number;
  sha256: string;
  createdAt: string;
  updatedAt: string;
  trashedAt: string | null;
  purgeAt: string | null;
  locked: boolean;
  unchanged?: boolean;
  // SPEC v2.8: the head version's kind; optional so an older server's answer still reads.
  headKind?: VersionKind;
}

export type VersionKind = "manual" | "auto" | "agent";

export interface VersionMeta {
  version: number;
  size: number;
  sha256: string;
  createdAt: string;
  // SPEC v2.3 (v2.8 adds "agent"); optional so an older server's answer still reads as all-manual.
  kind?: VersionKind;
  superseded?: boolean;
}

export interface Me {
  user: User;
  plan: "free" | "pro";
  limits: { filesPerApp: number | null; maxFileBytes: number; totalBytes: number };
  usage: { totalBytes: number; apps: Record<string, { files: number; trashed: number }> };
  app?: { id: string; name: string; extension: string; files: number; limit: number | null; remaining: number | null };
  billing: { provider: "dev" | "stripe"; priceLabel: string; canUpgrade: boolean; canManage: boolean };
  accountUrl: string;
  deletionScheduledAt: string | null;
}

export type Status = "signed-out" | "idle" | "dirty" | "saving" | "saved" | "offline" | "conflict" | "error";

export interface State {
  user: User | null;
  plan: "free" | "pro" | null;
  me: Me | null;
  file: FileMeta | null;
  status: Status;
  message: string | null;
  lastSavedAt: string | null;
  autosave: boolean;
}

export type Content = string | Blob | ArrayBuffer | Uint8Array | object;

export interface AutosaveOptions {
  idleMs?: number;
  maxIntervalMs?: number;
}

export interface LiveUpdateOptions {
  intervalMs?: number;
}

// Per-file agent links (SPEC v2.8). The token is never listed again after it is created.
export type AgentLinkMode = "edit" | "read";

export interface AgentLink {
  id: string;
  mode: AgentLinkMode;
  createdAt: string;
  expiresAt: string;
  lastUsedAt: string | null;
  revoked: boolean;
}

// POST /v1/files/:id/agent-links: `prompt` is the line the user pastes into their agent.
export interface CreatedAgentLink {
  id: string;
  url: string;
  token: string;
  mode: AgentLinkMode;
  expiresAt: string;
  prompt: string;
}

// GET /v1/agent-links (the account page): every live link of the user, with its file.
export interface AccountAgentLink extends AgentLink {
  fileId: string;
  fileName: string;
  app: string;
}

export interface HostedFilesOptions {
  server: string;
  app: string;
  getContent: () => Content | Promise<Content>;
  // `file` is null only when unsaved text of an untitled document comes back after a
  // redirect sign-in.
  setContent: (blob: Blob, file: FileMeta | null) => void | Promise<void>;
  newDocument?: () => void | Promise<void>;
  contentType?: string;
  untitledName?: string;
  // Default on, { idleMs: 1500, maxIntervalMs: 20000 } (SPEC v2.4). The user's setAutosave()
  // choice, kept in localStorage, overrides it.
  autosave?: boolean | AutosaveOptions;
  // Default on, every 5000 ms while a file is open and the page visible, and on focus (SPEC v2.8):
  // a newer head written elsewhere (an agent, another device) loads when nothing is unsaved here.
  liveUpdates?: boolean | LiveUpdateOptions;
  signInMode?: "popup" | "redirect";
  // The sign-in dialog's header (SPEC v2.7). Default: the server's name for the app and the
  // Simple Hosted Files mark at <server>/brand/logo.svg. `appIcon` is an image URL.
  appName?: string;
  appIcon?: string;
  shortcuts?: boolean;
  warnOnUnsavedClose?: boolean;
}

// GET /v1/session/methods?app=<id> (SPEC v2.7): what the sign-in dialog may offer.
export interface SignInMethods {
  serviceName: string;
  google: boolean;
  email: boolean;
  termsUrl: string;
  privacyUrl: string;
  logoUrl: string;
  appName?: string;
  // SPEC v2.9: the origin the /connect pop-up opens on (an app's own sign-in host, else the server).
  // Absent from an older server: the pop-up opens on the server.
  authOrigin?: string;
}

export type EventName = "signin" | "signout" | "open" | "save" | "conflict" | "limit" | "error";

// The IndexedDB draft record (SPEC §7 "Save behaviour" 1, v2.4 local drafts). `tab` and `id` are ours:
// `tab` names the live tab that owns the draft, `id` makes "delete only my draft" exact.
export interface Draft {
  app: string;
  fileId: string | null;
  baseVersion: number | null;
  name: string;
  contentType: string;
  content: Blob;
  savedAt: string;
  tab?: string;
  id?: string;
  kind?: "manual" | "auto"; // sent as X-Save-Kind when the draft is retried
}
