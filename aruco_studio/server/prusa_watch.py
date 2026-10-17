"""PrusaSlicer's folder, watched (M8 note 5.4): READ ONLY, on M8a's
server/watch.py (paths -> a signature -> a callback, the hash rule).

| | |
|---|---|
| What | PrusaSlicer.ini, physical_printer/, printer/, print/ and vendor/ *.ini (store.prusa_paths): about twenty stats every `interval` (2 s) |
| A change | held still for `quiet` (0.5 s), read through store.read_prusa_file (the allow-list; private keys dropped as it is read), re-resolved, diffed; `prusa {revision, added, removed, changed, files, ms, stale}` pushed on /api/events |
| A half-written file | it does not parse (store's `complete`): the last good text of that file is kept, no event; after three ticks still broken, one `prusa {broken: [file]}` |
| A tag | never changes by itself: its cells were copied when it was made. `stale(...)` lists the tags whose preset's line or nozzle now differs, as an `info` under Preset ("the profile changed: line 0.68 -> 0.65 mm; Apply?") |
| No folder | no watch; the folder is looked for again every `retry` (60 s) |
| The hash | decides, not the mtime (roaming / cloud sync) |

    W = PrusaWatch(publish).start() ... W.stop()       # or W.tick() from a test
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ..core import presets as _P
from ..core import prusa as _PR
from . import store as S
from .watch import Watcher

INTERVAL_S = 2.0
QUIET_S = 0.5
RETRY_S = 60.0
BROKEN_TICKS = 3
_BROKEN = "\x00broken"


class KeptWatcher(Watcher):
    """watch.Watcher reading each file through store.read_prusa_file: its
    hash and its callback's text are of what is KEPT (the allow-list, the
    private keys dropped), so a host never reaches the watcher's state and
    a change of a host alone is no change. A file that does not parse ends
    with a marker (`_BROKEN`)."""

    def __init__(self, folder: Path, *a, **kw):
        self.folder = Path(folder)
        super().__init__(*a, **kw)

    def _read(self, p: str):
        try:
            rel = S.prusa_rel(self.folder, Path(p))
        except ValueError:
            return None
        text, ok = S.read_prusa_file(Path(p), S.prusa_kind(rel))
        if text is None:
            return None
        return (text + ("" if ok else _BROKEN)).encode("utf-8")


def summary(src) -> Dict[str, dict]:
    """{key: comparable value} of what a Studio shows: each physical
    printer resolved, each print profile read, the selection."""
    out: Dict[str, dict] = {}
    if src is None:
        return out
    for e in _PR.physical_printers(src):
        out[f"physical_printer/{e['name']}"] = {
            "preset": e["preset"], "presets": e["presets"], "current": e["current"],
            "printer": e["printer"], "prints": [(p["name"], p["fits"], p["line_mm"],
                                                 p["layer_mm"]) for p in e["prints"]]}
    for n in sorted(src.user):
        try:
            out[f"print/{n}"] = _PR.profile(n, src)
        except Exception:                          # noqa: BLE001
            out[f"print/{n}"] = None
    for n in sorted(src.printers):
        pr = _PR.printer_of(n, src)
        out[f"printer/{n}"] = None if pr is None else {k: v for k, v in pr.items()
                                                       if k != "config"}
    out["selection"] = src.selection
    for i, v in enumerate(src.vendors):            # a bundle: its version and its size
        out[f"vendor/{v.get('name') or i}"] = {
            "config_version": v.get("config_version"),
            "printers": len(src.printer_bundles[i]), "prints": len(src.bundles[i]),
            "models": len(src.models[i])}
    return out


def diff(old: Dict[str, dict], new: Dict[str, dict]) -> dict:
    return {"added": sorted(k for k in new if k not in old),
            "removed": sorted(k for k in old if k not in new),
            "changed": sorted(k for k in new if k in old and new[k] != old[k])}


class PrusaWatch:
    def __init__(self, publish: Callable[[str, dict], object], interval: float = INTERVAL_S,
                 quiet: float = QUIET_S, retry: float = RETRY_S):
        self.publish = publish
        self.interval, self.quiet, self.retry = float(interval), float(quiet), float(retry)
        self.lock = threading.RLock()
        self.dir: Optional[Path] = None
        self.files: Dict[str, str] = {}            # relpath -> the last good (kept) text
        self.broken: Dict[str, int] = {}           # relpath -> ticks it has failed
        self.reported: set = set()
        self.src = None
        self.state: Dict[str, dict] = {}
        self.revision = 0
        self.last_ms: Optional[float] = None         # the last re-read, wall clock
        self.last_cpu_ms: Optional[float] = None     # ... and this process's CPU time
        self.watcher: Optional[Watcher] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._changed: List[str] = []
        self.ticks = 0

    # ------------------------------------------------------------ reading

    def _bind(self) -> bool:
        d = S.prusa_dir()
        if d is None or not Path(d).is_dir():
            self.dir, self.watcher, self.src, self.files = None, None, None, {}
            return False
        if self.dir is not None and Path(d) == self.dir and self.watcher is not None:
            return True
        self.dir = Path(d)
        self.files = {}
        for rel, (text, ok) in S.prusa_read(self.dir).items():
            if ok:
                self.files[rel] = text
        self.src = S.prusa_sources(self.files)
        self.state = summary(self.src)
        self.watcher = KeptWatcher(self.dir, lambda: S.prusa_paths(self.dir) + self._gone(),
                                   self._on_change, interval=self.interval, quiet=self.quiet,
                                   name="prusa-watch")
        return True

    def _gone(self) -> List[Path]:
        """Files read before and gone now: still polled, so a delete calls back."""
        here = {S.prusa_rel(self.dir, p) for p in S.prusa_paths(self.dir)}
        return [self.dir / rel for rel in self.files if rel not in here]

    def _on_change(self, path: str, text, digest) -> None:
        rel = S.prusa_rel(self.dir, Path(path))
        if text is None:
            self.files.pop(rel, None)
            self.broken.pop(rel, None)
            self._changed.append(rel)
            return
        ok = not text.endswith(_BROKEN)
        kept = text if ok else text[:-len(_BROKEN)]
        if not ok:
            self.broken[rel] = self.broken.get(rel, 0)
            return
        self.broken.pop(rel, None)
        self.reported.discard(rel)
        if self.files.get(rel) != kept:
            self.files[rel] = kept
            self._changed.append(rel)

    # ------------------------------------------------------------ one tick

    def tick(self) -> Optional[dict]:
        """One poll: -> the event published, or None."""
        with self.lock:
            self.ticks += 1
            if not self._bind():
                return None
            t0, c0 = time.perf_counter(), time.process_time()   # the re-read: read, resolve, diff
            self.watcher.poll()
            for rel in list(self.broken):
                self.broken[rel] += 1
                if self.broken[rel] >= BROKEN_TICKS and rel not in self.reported:
                    self.reported.add(rel)
                    return self._publish({"broken": [rel], "added": [], "removed": [],
                                          "changed": [], "files": [],
                                          "message": f"{rel} does not parse: the last good read "
                                                     "is kept"})
            if not self._changed:
                return None
            files = sorted(set(self._changed))
            self._changed = []
            self.src = S.prusa_sources(self.files)
            new = summary(self.src)
            self.last_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            self.last_cpu_ms = round((time.process_time() - c0) * 1000.0, 1)
            d = diff(self.state, new)
            self.state = new
            if not (d["added"] or d["removed"] or d["changed"]):
                return None
            return self._publish(dict(d, files=files, ms=self.last_ms, cpu_ms=self.last_cpu_ms))

    def _publish(self, data: dict) -> dict:
        self.revision += 1
        data = dict(data, revision=self.revision)
        try:
            data["stale"] = len(stale_now(self.src))
        except Exception:                          # noqa: BLE001
            data["stale"] = None
        self.publish("prusa", data)
        return data

    # ------------------------------------------------------------ the loop

    def _run(self):
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:                      # noqa: BLE001  the loop never dies
                pass
            if self.dir is None:
                wait = self.retry
            elif self.watcher is not None and (self.watcher._pending or self.broken):
                wait = self.quiet
            else:
                wait = self.interval
            self._stop.wait(wait)

    def start(self) -> "PrusaWatch":
        if self._thread is None:
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="prusa-watch", daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=5.0)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# ------------------------------------------------------------ the tags' info

def _preset_name(doc: dict, t) -> Optional[str]:
    src = t.source or {}
    i = src.get("feature")
    feats = doc.get("features") or []
    f = feats[i] if isinstance(i, int) and 0 <= i < len(feats) else {}
    name = f.get("preset") if isinstance(f, dict) else None
    if not isinstance(name, str):
        name = doc.get("preset")
    return name if isinstance(name, str) else None


def stale(doc: dict, scene, catalog: dict) -> List[dict]:
    """[{tag, preset, field, level, text, was, now, apply}] each tag whose
    preset (its feature's, else the file's) came from a PrusaSlicer profile
    that now has another line width or nozzle than the tag was made with.
    Nothing is applied: `apply` names the route a click would call."""
    out = []
    for t in scene.tags:
        name = _preset_name(doc, t)
        if not name:
            continue
        p, _kind = _P.find(catalog, name)
        if p is None or (p.get("profile") or {}).get("source") != "prusaslicer":
            continue
        s = t.spec.settings or {}
        bits = []
        cells = s.get("cells") if isinstance(s.get("cells"), dict) else {}
        now = _P.line_mm(p)
        was = cells.get("mm") if cells.get("of") == "cell" else None
        if isinstance(was, (int, float)) and now and abs(float(was) - float(now)) > 1e-6:
            bits.append(("line", float(was), float(now)))
        lab = s.get("label") if isinstance(s.get("label"), dict) else {}
        noz = (p.get("label") or {}).get("nozzle_mm")
        if isinstance(lab.get("nozzle_mm"), (int, float)) and noz and \
                abs(float(lab["nozzle_mm"]) - float(noz)) > 1e-6:
            bits.append(("nozzle", float(lab["nozzle_mm"]), float(noz)))
        if not bits:
            continue
        words = ", ".join(f"{w} {a:g} -> {b:g} mm" for w, a, b in bits)
        out.append({"tag": t.name, "preset": name, "field": "preset", "level": "info",
                    "text": f"the profile changed: {words}; Apply?",
                    "was": {w: a for w, a, _b in bits}, "now": {w: b for w, _a, b in bits},
                    "apply": {"route": "/api/preset/apply", "name": name}})
    return out


def stale_now(src=None) -> List[dict]:
    """stale() on the open design, with the catalog as it is now (`src`:
    the sources already read; else the folder is read)."""
    from . import design_api as _DA
    with _DA.D.lock:
        sc = _DA.D.current()
        doc = _DA.D.doc
    cat = _P.catalog_all(S.presets_store(), src if src is not None else S.prusa_sources())
    return stale(doc, sc, cat)


WATCH: Optional[PrusaWatch] = None


def ensure(publish=None) -> PrusaWatch:
    """The server's one watch, started (idempotent)."""
    global WATCH
    if WATCH is None:
        from . import events as _EV
        WATCH = PrusaWatch(publish or _EV.HUB.publish)
    if not WATCH.running:
        WATCH.start()
    return WATCH


def shutdown() -> None:
    global WATCH
    if WATCH is not None:
        WATCH.stop()
    WATCH = None
