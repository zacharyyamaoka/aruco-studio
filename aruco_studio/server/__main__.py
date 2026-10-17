"""python -m aruco_studio.server [--port 5360]: the API (and the built web
app) on 127.0.0.1 only."""
from __future__ import annotations

import argparse

import uvicorn

from .app import PORT, app


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    if a.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("the Studio serves on 127.0.0.1 only")
    if a.port in (5322, 5331, 5340, 5350, 8080):
        raise SystemExit(f"port {a.port} belongs to another tool")
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
