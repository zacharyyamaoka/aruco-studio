"""The 2026-10-17 audit (A2): tools/check.py's e2e takes its two ports from
ARUCO_STUDIO_API_PORT / ARUCO_STUDIO_UI_PORT (default 5360 / 5361), so a
check can run beside a lane's own server; another tool's port is refused.
(The port test of the server group binds a free port: test_api.py.)"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _check():
    spec = importlib.util.spec_from_file_location("aruco_check_tool", ROOT / "tools" / "check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_default_ports_and_the_env(monkeypatch):
    monkeypatch.delenv("ARUCO_STUDIO_API_PORT", raising=False)
    monkeypatch.delenv("ARUCO_STUDIO_UI_PORT", raising=False)
    c = _check()
    assert c.ports() == (5360, 5361) and c.PORTS == (5360, 5361)
    monkeypatch.setenv("ARUCO_STUDIO_API_PORT", "5380")
    monkeypatch.setenv("ARUCO_STUDIO_UI_PORT", "5381")
    assert c.ports() == (5380, 5381)


@pytest.mark.parametrize("api,ui", [("5370", "5361"), ("5360", "8080"), ("5362", "5362")])
def test_another_tools_port_or_the_same_twice_is_refused(monkeypatch, api, ui):
    c = _check()
    monkeypatch.setenv("ARUCO_STUDIO_API_PORT", api)
    monkeypatch.setenv("ARUCO_STUDIO_UI_PORT", ui)
    with pytest.raises(SystemExit):
        c.ports()


def test_the_e2e_config_and_helpers_read_the_same_env():
    cfg = (ROOT / "e2e" / "playwright.config.ts").read_text(encoding="utf-8")
    helpers = (ROOT / "e2e" / "tests" / "helpers.ts").read_text(encoding="utf-8")
    vite = (ROOT / "studio" / "vite.config.ts").read_text(encoding="utf-8")
    for text in (cfg, helpers, vite):
        assert "ARUCO_STUDIO_API_PORT" in text
    assert "ARUCO_STUDIO_UI_PORT" in cfg and "ARUCO_STUDIO_UI_PORT" in vite
