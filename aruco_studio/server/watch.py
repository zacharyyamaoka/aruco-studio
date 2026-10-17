"""A file watcher: paths -> a signature -> a callback (standard library only).

Every `interval` seconds it stats each path. A changed (mtime, size) pair
that has held still for `quiet` seconds is read and hashed (sha256 of the
bytes); the callback runs only when the hash differs from the last one seen
or written (`remember`). So an editor that only touches the file, a cloud
sync that bumps mtimes, or the server's own write (remembered before it is
written) give no callback. A path that goes away calls back once with
`text=None`; one that comes back is read again.

Why polling and not ReadDirectoryChangesW: no dependency, a few files,
deterministic in tests, and a stat a quarter second costs nothing.

    w = Watcher(lambda: [path], on_change, interval=0.25)
    w.start() ... w.stop()          # or w.poll() once, from a test
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple, Union

PathsArg = Union[Iterable[Union[str, Path]], Callable[[], Iterable[Union[str, Path]]]]
Sig = Optional[Tuple[int, int]]


def text_hash(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def signature(path: Union[str, Path]) -> Sig:
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


class Watcher:
    def __init__(self, paths: PathsArg, on_change: Callable[[str, Optional[str], Optional[str]],
                                                             None],
                 interval: float = 0.25, quiet: float = 0.0, name: str = "watch"):
        self._paths = paths
        self.on_change = on_change
        self.interval = float(interval)
        self.quiet = float(quiet)
        self.name = name
        self._sig: Dict[str, Sig] = {}
        self._hash: Dict[str, Optional[str]] = {}
        self._pending: Dict[str, Tuple[Sig, float]] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        for p in self.paths():                     # the state at start: no callback for it
            self._sig[p] = signature(p)
            self._hash[p] = self._read_hash(p)

    def paths(self):
        ps = self._paths() if callable(self._paths) else self._paths
        return [str(Path(p)) for p in ps]

    @staticmethod
    def _read(p: str) -> Optional[bytes]:
        try:
            with open(p, "rb") as fh:
                return fh.read()
        except OSError:
            return None

    def _read_hash(self, p: str) -> Optional[str]:
        b = self._read(p)
        return text_hash(b) if b is not None else None

    def remember(self, path: Union[str, Path], digest: Optional[str]) -> None:
        """The hash of a text this process is about to write (or has read)
        at `path`: reading it back is not a change."""
        with self._lock:
            self._hash[str(Path(path))] = digest

    def poll(self) -> int:
        """One tick. -> how many callbacks ran."""
        n = 0
        now = time.monotonic()
        for p in self.paths():
            sig = signature(p)
            with self._lock:
                if sig == self._sig.get(p, ()) and p not in self._pending:
                    continue
                if self.quiet > 0 and sig is not None:
                    pend = self._pending.get(p)
                    if pend is None or pend[0] != sig:
                        self._pending[p] = (sig, now)
                        continue
                    if now - pend[1] < self.quiet:
                        continue
                self._pending.pop(p, None)
                self._sig[p] = sig
                if sig is None:
                    if self._hash.get(p, "") is None:
                        continue
                    self._hash[p] = None
                    text, digest = None, None
                else:
                    b = self._read(p)
                    if b is None:
                        continue
                    digest = text_hash(b)
                    if digest == self._hash.get(p):
                        continue
                    self._hash[p] = digest
                    text = b.decode("utf-8", errors="replace")
            try:
                self.on_change(p, text, digest)
            except Exception:                      # noqa: BLE001  a callback never kills the loop
                pass
            n += 1
        return n

    def _run(self):
        while not self._stop.wait(self.interval):
            self.poll()

    def start(self) -> "Watcher":
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2.0)
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
