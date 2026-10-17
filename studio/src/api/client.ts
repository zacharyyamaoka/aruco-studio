// The Studio's API (docs/API.md). Relative URLs: in dev Vite proxies /api to
// 127.0.0.1:5360; built, the server itself serves this app on 5360.
import type {
  Dictionary, FormDoc, LibraryState, PaletteEntry, Preset, PresetItem, RenumberReport,
  SceneDoc, SceneTag, TagPlan, TagSpec, Target, VerifyReport,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/** A readable line for any error the server gives (422 names the key path). */
export function errorText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: any) => (d && d.path ? `${d.path}: ${d.msg}` : JSON.stringify(d))).join("; ");
  }
  if (detail && typeof detail === "object") {
    const d = detail as any;
    if (Array.isArray(d.issues)) return d.issues.map((i: any) => i.text).join("; ");
    if (Array.isArray(d.errors)) return d.errors.join("; ");
    if (d.detail !== undefined) return errorText(d.detail);
  }
  return String(detail);
}

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!r.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? data.detail : data;
    throw new ApiError(r.status, data, `${r.status}: ${errorText(detail)}`);
  }
  return data as T;
}

const get = <T,>(u: string) => call<T>("GET", u);
const post = <T,>(u: string, b?: unknown) => call<T>("POST", u, b ?? {});
const put = <T,>(u: string, b: unknown) => call<T>("PUT", u, b);
const patch = <T,>(u: string, b: unknown) => call<T>("PATCH", u, b);
const del = <T,>(u: string) => call<T>("DELETE", u);
const q = encodeURIComponent;

export const api = {
  health: () => get<{ ok: boolean; version: string; ref_commit: string; home: string; scenes: string }>("/api/health"),
  form: () => get<FormDoc>("/api/form"),
  options: () => get<Record<string, any>>("/api/options"),
  dictionaries: () => get<Dictionary[]>("/api/dictionaries"),
  targets: (thickness = 3) => get<PaletteEntry[]>(`/api/targets?thickness_mm=${thickness}`),
  makeTarget: (b: { shape: "box" | "disc" | "face"; key?: string; w_mm?: number; h_mm?: number; r_mm?: number; holes?: [number, number, number][]; thickness_mm?: number }) =>
    post<Target>("/api/target", b),
  plan: (spec: TagSpec, opts = "top=1") => post<TagPlan>(`/api/plan?${opts}`, spec),
  validate: (spec: TagSpec) => post<{ field: string; level: string; text: string }[]>("/api/validate", spec),
  candidates: (b: unknown) => post<any[]>("/api/candidates", b),
  newSpec: (b: { layout: string; target_key?: string; thickness_mm?: number; target?: Target; preset?: string; marker_id?: number }) =>
    post<TagSpec>("/api/new", b),
  verify: (spec: TagSpec, image = true) => post<VerifyReport>("/api/verify", { spec, px_per_mm: 20.0, pose: true, image }),
  exportTag: async (fmt: string, spec: TagSpec): Promise<Blob> => {
    const r = await fetch(`/api/export/${fmt}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(spec),
    });
    if (!r.ok) throw new ApiError(r.status, await r.text(), `${r.status}: export ${fmt} refused`);
    return r.blob();
  },
  // presets and the library
  presets: () => get<{ items: PresetItem[]; last: string | null; notes: string[]; file: string }>("/api/presets"),
  presetSaveAs: (name: string, preset: Preset) => post<{ name: string }>("/api/presets", { name, preset }),
  presetDelete: (name: string) => del<{ deleted: string }>(`/api/presets/${q(name)}`),
  presetApply: (spec: TagSpec, name: string, preset?: Preset) =>
    post<TagSpec>("/api/preset/apply", preset ? { spec, preset } : { spec, name }),
  presetOf: (spec: TagSpec) => post<{ preset: Preset; matches: string | null }>("/api/preset/of", { spec }),
  library: (tag?: string) => get<LibraryState>(`/api/library${tag ? `?tag=${q(tag)}` : ""}`),
  librarySelect: (id: string) => post<{ name: string; preset: Preset }>("/api/library/select", { id }),
  librarySave: (id: string, name: string, values: Record<string, unknown>) =>
    post<{ name: string }>("/api/library/save", { id, name, values }),
  recent: () => get<{ recent: string[] }>("/api/library/recent"),
  addRecent: (name: string) => post<{ recent: string[] }>("/api/library/recent", { name }),
  // the scene
  scene: (mesh: boolean) => get<SceneDoc>(`/api/scene?plans=1&top=1${mesh ? "&mesh=1" : ""}`),
  sceneDoc: () => get<SceneDoc>("/api/scene"),
  scenePut: (doc: SceneDoc) => put<SceneDoc>("/api/scene", doc),
  sceneNew: (name: string) => post<SceneDoc>("/api/scene/new", { name }),
  addTag: (spec: TagSpec, x_mm: number, y_mm: number, rotation_deg = 0, name?: string) =>
    post<SceneTag>("/api/scene/tags", { spec, x_mm, y_mm, rotation_deg, ...(name ? { name } : {}) }),
  patchTag: (name: string, b: Record<string, unknown>) => patch<SceneTag>(`/api/scene/tags/${q(name)}`, b),
  deleteTag: (name: string) => del<{ deleted: string }>(`/api/scene/tags/${q(name)}`),
  duplicateTag: (name: string, dx: number, dy: number) =>
    post<SceneTag>(`/api/scene/tags/${q(name)}/duplicate?dx_mm=${dx}&dy_mm=${dy}`),
  override: (name: string, id: number | null) => put<{ overrides: Record<string, number> }>(`/api/scene/overrides/${q(name)}`, { id }),
  renumber: () => post<RenumberReport>("/api/scene/renumber"),
  scenes: () => get<{ name: string; file: string; bytes: number; modified: string }[]>("/api/scenes"),
  save: (name: string) => post<{ saved: string; name: string }>("/api/scene/save", { name }),
  open: (name: string) => post<SceneDoc>("/api/scene/open", { name }),
  sceneVerify: () => post<any>("/api/scene/verify?px_per_mm=10"),
  sceneExport: (fmt: string) =>
    post<{ dir: string; files: string[]; inline: Record<string, string> | null }>(`/api/scene/export/${fmt}?save=1&inline=1`),
};
