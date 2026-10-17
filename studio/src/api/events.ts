// The server's events (GET /api/events, server-sent events): `scene` when
// the open file changed on disk, `file` when it breaks, goes or parses
// again. The browser reconnects by itself; a reconnect says `hello`, and
// the Studio reads the file again then (it may have missed a change).
export type EventKind = "hello" | "scene" | "file" | "prusa" | "presets";

export interface Events { close(): void; readonly connected: boolean }

export function connectEvents(on: (kind: EventKind, data: any) => void, url = "/api/events"): Events {
  if (typeof EventSource === "undefined") return { close() { /* no SSE (vitest) */ }, connected: false };
  const es = new EventSource(url);
  let connected = false;
  const handle = (kind: EventKind) => (e: MessageEvent) => {
    let data: any = null;
    try { data = e.data ? JSON.parse(e.data) : null; } catch { data = e.data; }
    on(kind, data);
  };
  for (const k of ["hello", "scene", "file", "prusa", "presets"] as EventKind[]) es.addEventListener(k, handle(k) as EventListener);
  es.onopen = () => { connected = true; };
  es.onerror = () => { connected = false; };
  return {
    close() { es.close(); },
    get connected() { return connected; },
  };
}
