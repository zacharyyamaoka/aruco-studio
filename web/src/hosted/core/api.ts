// The HTTP layer: bearer auth, JSON in/out, every failure as a HostedFilesError.

import { HostedFilesError } from "./errors.js";
import type { Content, FileMeta, Me, VersionMeta } from "./types.js";

export interface RequestOptions {
  body?: BodyInit | object | null;
  headers?: Record<string, string>;
  keepalive?: boolean;
  // WHY: the sign-in calls carry no bearer, and their 401 (a wrong code) is not a lost session.
  anonymous?: boolean;
}

export type SaveKind = "manual" | "auto";

// WHY plain fields, not constructor parameter properties: this file is copied into apps by the
// shadcn registry, and Vite's react-ts template sets "erasableSyntaxOnly", which rejects them (TS1294).
export class Api {
  readonly server: string;
  readonly app: string;
  private getToken: () => string | null;
  private onUnauthorized: () => void;

  constructor(server: string, app: string, getToken: () => string | null, onUnauthorized: () => void) {
    this.server = server;
    this.app = app;
    this.getToken = getToken;
    this.onUnauthorized = onUnauthorized;
  }

  async request(method: string, path: string, opts: RequestOptions = {}): Promise<Response> {
    const headers: Record<string, string> = { ...opts.headers };
    const token = this.getToken();
    if (token && !opts.anonymous) headers.Authorization = `Bearer ${token}`;
    let body: BodyInit | undefined;
    if (opts.body instanceof Blob || typeof opts.body === "string" || opts.body instanceof ArrayBuffer || ArrayBuffer.isView(opts.body)) {
      body = opts.body as BodyInit;
    } else if (opts.body != null) {
      body = JSON.stringify(opts.body);
      headers["Content-Type"] = "application/json";
    }
    let res: Response;
    try {
      res = await fetch(this.server + path, { method, headers, body, credentials: "omit", cache: "no-store", keepalive: opts.keepalive });
    } catch (err) {
      throw new HostedFilesError("network", "Can't reach Simple Hosted Files", 0, { cause: String(err) });
    }
    if (res.ok) return res;
    let payload: { error?: { code?: string; message?: string } & Record<string, unknown> } = {};
    try {
      payload = await res.json();
    } catch {}
    const { code, message, ...details } = payload.error ?? {};
    const error = new HostedFilesError(code ?? (res.status >= 500 ? "server_error" : "bad_request"), message ?? `HTTP ${res.status}`, res.status, details);
    if (res.status === 401 && !opts.anonymous) this.onUnauthorized();
    throw error;
  }

  async json<T>(method: string, path: string, opts?: RequestOptions): Promise<T> {
    const res = await this.request(method, path, opts);
    return (await res.json()) as T;
  }

  me(): Promise<Me> {
    return this.json<Me>("GET", `/v1/me?app=${encodeURIComponent(this.app)}`);
  }
}

export function toBlob(content: Content, contentType: string): Blob {
  if (content instanceof Blob) return content;
  if (typeof content === "string") return new Blob([content], { type: contentType });
  if (content instanceof ArrayBuffer || content instanceof Uint8Array) return new Blob([content as BlobPart], { type: contentType });
  return new Blob([JSON.stringify(content)], { type: contentType });
}

// hosted.files (SPEC §7 "Files (low level)").
export class FilesApi {
  private api: Api;
  private contentType: string;

  constructor(api: Api, contentType: string) {
    this.api = api;
    this.contentType = contentType;
  }

  private q(): string {
    return `app=${encodeURIComponent(this.api.app)}`;
  }

  async list(opts: { trashed?: boolean } = {}): Promise<FileMeta[]> {
    const { files } = await this.api.json<{ files: FileMeta[] }>("GET", `/v1/files?${this.q()}${opts.trashed ? "&trashed=1" : ""}`);
    return files;
  }

  create(name: string, content: Content): Promise<FileMeta> {
    const blob = toBlob(content, this.contentType);
    return this.api.json<FileMeta>("POST", `/v1/files?${this.q()}&name=${encodeURIComponent(name)}`, {
      body: blob,
      headers: { "Content-Type": blob.type || this.contentType },
    });
  }

  get(id: string): Promise<FileMeta> {
    return this.api.json<FileMeta>("GET", `/v1/files/${id}`);
  }

  async read(id: string, opts: { version?: number } = {}): Promise<Blob> {
    const res = await this.api.request("GET", `/v1/files/${id}/content${opts.version ? `?version=${opts.version}` : ""}`);
    return res.blob();
  }

  // `kind: "auto"` marks an autosave (SPEC v2.3); `keepalive` lets the request outlive the page.
  write(id: string, content: Content, baseVersion: number, opts: { kind?: SaveKind; keepalive?: boolean } = {}): Promise<FileMeta> {
    const blob = toBlob(content, this.contentType);
    const headers: Record<string, string> = { "If-Match": `"${baseVersion}"`, "Content-Type": blob.type || this.contentType };
    // WHY only auto sends the header: absent means manual, so a manual save never depends on
    // the server allowing X-Save-Kind in its CORS preflight.
    if (opts.kind === "auto") headers["X-Save-Kind"] = "auto";
    return this.api.json<FileMeta>("PUT", `/v1/files/${id}/content`, { body: blob, headers, keepalive: opts.keepalive });
  }

  rename(id: string, name: string): Promise<FileMeta> {
    return this.api.json<FileMeta>("PATCH", `/v1/files/${id}`, { body: { name } });
  }

  duplicate(id: string, name?: string): Promise<FileMeta> {
    return this.api.json<FileMeta>("POST", `/v1/files/${id}/duplicate`, { body: name ? { name } : {} });
  }

  trash(id: string): Promise<FileMeta> {
    return this.api.json<FileMeta>("DELETE", `/v1/files/${id}`);
  }

  restore(id: string): Promise<FileMeta> {
    return this.api.json<FileMeta>("POST", `/v1/files/${id}/restore`);
  }

  async versions(id: string): Promise<VersionMeta[]> {
    const { versions } = await this.api.json<{ versions: VersionMeta[] }>("GET", `/v1/files/${id}/versions`);
    return versions;
  }

  restoreVersion(id: string, n: number): Promise<FileMeta> {
    return this.api.json<FileMeta>("POST", `/v1/files/${id}/versions/${n}/restore`);
  }

  // A cookie-session URL (works as a link on the server's own origin). Apps on another
  // origin download through the SDK, which sends the bearer.
  downloadUrl(id: string, opts: { version?: number } = {}): string {
    return `${this.api.server}/v1/files/${id}/content?download=1${opts.version ? `&version=${opts.version}` : ""}`;
  }

  // Fetches with the bearer and hands the bytes to the browser as a download.
  async download(id: string, opts: { version?: number } = {}): Promise<void> {
    const res = await this.api.request("GET", `/v1/files/${id}/content?download=1${opts.version ? `&version=${opts.version}` : ""}`);
    saveBlob(await res.blob(), filenameFrom(res) ?? "download");
  }
}

export function filenameFrom(res: Response): string | null {
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (star) return decodeURIComponent(star[1]);
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  return plain ? plain[1] : null;
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
