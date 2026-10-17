"""M8a.6: the watcher and /api/events.

* an external write is seen and `scene` pushed within 500 ms (measured
  from the write to the event, read off a TestClient stream);
* a broken write keeps the scene, reports line:col, and a PATCH answers
  409 "file not parseable" without writing;
* the server's own write gives no event; an unchanged rewrite (the same
  text, a new mtime) gives no event;
* a deleted file stops writes with a message;
* two writers: a change on disk the server has not read yet drops the
  action (409) and reloads;
* server/watch.py on its own: the hash rule, `remember`, the quiet time.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aruco_studio.server import events as EV
from aruco_studio.server.watch import Watcher, text_hash

ROOT = Path(__file__).resolve().parents[2]
LATENCY = []


@pytest.fixture()
def opened(tmp_path, monkeypatch):
    monkeypatch.setenv("ARUCO_STUDIO_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ARUCO_STUDIO_SCENES", str(tmp_path / "scenes"))
    monkeypatch.setenv("BAM_ARUCO_PRUSASLICER_DIR", str(ROOT / "goldens" / "prusaslicer"))
    from aruco_studio.scene import Scene
    from aruco_studio.server import app as A
    from aruco_studio.server import design_api as DA
    A.STATE["scene"] = Scene(name="untitled")
    c = TestClient(A.app)
    p = tmp_path / "plate.arucostudio.json"
    shutil.copy(ROOT / "examples" / "plate_charuco.arucostudio.json", p)
    assert c.post("/api/design/open", json={"path": str(p)}).status_code == 200
    yield c, p, DA
    DA.D.unbind()


def listen(client, n, timeout):
    """A stream of at most n events (hello included) or `timeout` s, in a thread."""
    out = []
    before = EV.HUB.listeners
    th = threading.Thread(target=lambda: out.append(
        client.get(f"/api/events?max_events={n}&timeout={timeout}")), daemon=True)
    th.start()
    t_end = time.time() + 2.0
    while EV.HUB.listeners <= before and time.time() < t_end:
        time.sleep(0.005)
    assert EV.HUB.listeners > before, "the stream did not start"
    return th, out


def events_of(th, out, wait=5.0):
    th.join(wait)
    assert out, "the stream did not end"
    r = out[0]
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return EV.parse(r.text)


def edit_file(p: Path, fn):
    doc = json.loads(p.read_text(encoding="utf-8"))
    fn(doc)
    text = json.dumps(doc, indent=2) + "\n"
    t0 = time.time()
    p.write_text(text, encoding="utf-8")
    return t0, text


def test_an_external_write_is_pushed_within_500_ms(opened):
    c, p, DA = opened
    for k in range(3):
        th, out = listen(c, 2, 4.0)
        t0, _ = edit_file(p, lambda d: d["sketches"][0]["shapes"][0].__setitem__("rect",
                                                                                [90 + k, 50]))
        evs = events_of(th, out)
        assert [e["event"] for e in evs] == ["hello", "scene"]
        dt = evs[1]["data"]["t"] - t0
        LATENCY.append(dt)
        assert 0 <= dt < 0.5, dt
        tag = c.get("/api/scene").json()["tags"][0]
        assert tag["spec"]["target"]["w_mm"] == 90.0 + k
    print(f"\nwatcher latency: {', '.join(f'{x * 1000:.0f} ms' for x in LATENCY)}")


def test_a_broken_write_keeps_the_scene_and_blocks_writes(opened):
    c, p, DA = opened
    before = c.get("/api/scene").json()
    th, out = listen(c, 2, 4.0)
    good = p.read_text(encoding="utf-8")
    broken = good.replace('"height": 5}', '"height": 5,}')
    assert broken != good
    line = next(k for k, ln in enumerate(broken.splitlines(), 1) if '"height": 5,}' in ln)
    p.write_text(broken, encoding="utf-8")
    evs = events_of(th, out)
    assert [e["event"] for e in evs] == ["hello", "file"]
    err = evs[1]["data"]["error"]
    assert evs[1]["data"]["state"] == "broken" and err["line"] == line and err["col"] > 1
    assert c.get("/api/scene").json() == before                 # the last good scene
    d = c.get("/api/design").json()
    assert d["state"] == "broken" and d["error"]["line"] == line
    r = c.patch("/api/scene/tags/tag", json={"settings": {"corner_mark": "none"}})
    assert r.status_code == 409 and "file not parseable" in r.json()["detail"]
    assert f"line {line} col" in r.json()["detail"]
    assert p.read_text(encoding="utf-8") == broken              # nothing written
    assert c.put("/api/design", json={"text": good}).status_code == 409
    assert c.post("/api/scene/renumber").status_code == 409
    # fixed by hand: back to normal, the scene pushed
    th, out = listen(c, 3, 4.0)
    p.write_text(good, encoding="utf-8")
    evs = events_of(th, out)
    assert [e["event"] for e in evs] == ["hello", "file", "scene"]
    assert evs[1]["data"]["state"] == "ok"
    assert c.patch("/api/scene/tags/tag", json={"settings": {"corner_mark": "none"}}) \
        .status_code == 200


def test_own_writes_and_unchanged_rewrites_give_no_event(opened):
    c, p, DA = opened
    th, out = listen(c, 5, 1.5)
    r = c.patch("/api/scene/tags/tag", json={"settings": {"corner_mark": "none"}})
    assert r.status_code == 200
    mine = p.read_bytes()
    assert b'"corner_mark": "none"' in mine
    time.sleep(0.4)
    p.write_bytes(mine)                                          # the same text again
    st = os.stat(p)
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))   # a sync bumps the mtime
    evs = events_of(th, out)
    assert [e["event"] for e in evs] == ["hello"]
    assert c.get("/api/design").json()["state"] == "ok"


def test_a_deleted_file_stops_writes(opened):
    c, p, DA = opened
    th, out = listen(c, 2, 4.0)
    p.unlink()
    evs = events_of(th, out)
    assert [e["event"] for e in evs] == ["hello", "file"] and evs[1]["data"]["state"] == "missing"
    r = c.patch("/api/scene/tags/tag", json={"x_mm": 3.0})
    assert r.status_code == 409 and "file missing" in r.json()["detail"]
    assert not p.exists()                                        # nothing written
    assert c.get("/api/scene").json()["tags"][0]["name"] == "tag"
    s = c.post("/api/design/save_as", json={"path": str(p)}).json()   # Save as writes it again
    assert s["state"] == "ok" and p.exists()
    assert c.patch("/api/scene/tags/tag", json={"x_mm": 3.0}).status_code == 200


def test_two_writers_the_action_is_dropped_and_the_file_reloaded(opened):
    c, p, DA = opened
    DA.D.watcher.stop()                     # the change is on disk; the server has not read it
    t0, text = edit_file(p, lambda d: d.__setitem__("name", "theirs"))
    r = c.patch("/api/scene/tags/tag", json={"settings": {"corner_mark": "none"}})
    assert r.status_code == 409 and "changed on disk" in r.json()["detail"]
    assert p.read_text(encoding="utf-8") == text                 # theirs kept
    assert c.get("/api/scene").json()["name"] == "theirs"        # and read
    assert c.patch("/api/scene/tags/tag", json={"settings": {"corner_mark": "none"}}) \
        .status_code == 200


def test_the_watcher_alone(tmp_path):
    # each text a new length, so a coarse mtime can never hide a change
    p = tmp_path / "a.txt"
    p.write_text("1", encoding="utf-8")
    seen = []
    w = Watcher([p], lambda path, text, h: seen.append((text, h)), interval=0.05)
    assert w.poll() == 0
    p.write_text("22", encoding="utf-8")
    assert w.poll() == 1 and seen[-1] == ("22", text_hash("22"))
    w.remember(p, text_hash("333"))
    p.write_text("333", encoding="utf-8")
    assert w.poll() == 0                                         # our own write
    st = os.stat(p)
    p.write_text("333", encoding="utf-8")
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))
    assert w.poll() == 0                                         # same text, a new mtime
    p.unlink()
    assert w.poll() == 1 and seen[-1] == (None, None)
    assert w.poll() == 0
    p.write_text("4444", encoding="utf-8")
    assert w.poll() == 1 and seen[-1][0] == "4444"
    # a quiet time: a file still being written is not read until it holds still
    q = Watcher([p], lambda path, text, h: seen.append((text, h)), interval=0.05, quiet=0.2)
    n0 = len(seen)
    p.write_text("55555", encoding="utf-8")
    assert q.poll() == 0
    time.sleep(0.25)
    assert q.poll() == 1 and seen[n0][0] == "55555"
    q.start()
    assert q.running
    q.stop()
    assert not q.running
