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
}

export interface VersionMeta {
  version: number;
  size: number;
  sha256: string;
  createdAt: string;
  // SPEC v2.3; optional so an older server's answer still reads as all-manual.
  kind?: "manual" | "auto";
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
  signInMode?: "popup" | "redirect";
  shortcuts?: boolean;
  warnOnUnsavedClose?: boolean;
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
