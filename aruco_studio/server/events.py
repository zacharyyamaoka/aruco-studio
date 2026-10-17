"""The server's push: one hub of events, served as server-sent events on
GET /api/events (`text/event-stream`; a browser's EventSource reconnects by
itself; the app writes over HTTP, so one direction is all it needs).

| Event | Data | When |
|---|---|---|
| `hello` | `{revisions, file}` | on connect: what the client should have |
| `scene` | `{revision, path, why}` | the design file changed on disk and the scene was replaced |
| `file` | `{state, path, error}` | the open file is `broken` (does not parse: `error.line`, `error.col`), `missing`, or `ok` again |
| `prusa` | `{added, removed, changed}` | PrusaSlicer's folder changed (M8c) |
| `presets` | `{}` | the presets changed |

Each event's data carries `t` (time.time() when it was published), so a
test can measure the delay. Thread-safe: the file watcher publishes from
its thread; each stream reads its own queue.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from typing import Callable, Dict, List, Optional

KEEPALIVE_S = 15.0


def frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


class Hub:
    def __init__(self):
        self._subs: List[queue.Queue] = []
        self._lock = threading.Lock()
        self.revisions: Dict[str, int] = {"scene": 0, "prusa": 0, "presets": 0}

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    @property
    def listeners(self) -> int:
        with self._lock:
            return len(self._subs)

    def publish(self, event: str, data: Optional[dict] = None) -> dict:
        d = dict(data or {})
        d.setdefault("t", time.time())
        if event in self.revisions and "revision" in d:
            self.revisions[event] = int(d["revision"])
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            q.put((event, d))
        return d

    async def stream(self, hello: Callable[[], dict], max_events: Optional[int] = None,
                     timeout: Optional[float] = None, is_disconnected=None):
        """The SSE body: `hello`, then every event published. Ends after
        `max_events` events (hello counts) or `timeout` seconds (both for
        tests and one-shot pollers); else when the client goes."""
        q = self.subscribe()
        t_end = time.monotonic() + timeout if timeout else None
        sent = 0
        last = time.monotonic()
        try:
            yield frame("hello", dict(hello(), t=time.time()))
            sent += 1
            while max_events is None or sent < max_events:
                if t_end is not None and time.monotonic() >= t_end:
                    break
                try:
                    event, data = q.get_nowait()
                except queue.Empty:
                    if is_disconnected is not None and await is_disconnected():
                        break
                    if time.monotonic() - last > KEEPALIVE_S:
                        last = time.monotonic()
                        yield ": keep-alive\n\n"
                    await asyncio.sleep(0.02)
                    continue
                yield frame(event, data)
                sent += 1
                last = time.monotonic()
        finally:
            self.unsubscribe(q)


def parse(text: str) -> List[dict]:
    """An SSE body -> [{event, data}] (for tests and the CLI)."""
    out = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        ev, data = None, []
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if ev:
            out.append({"event": ev, "data": json.loads("\n".join(data)) if data else {}})
    return out


HUB = Hub()
