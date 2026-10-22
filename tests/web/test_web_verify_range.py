"""The reading range with the real OpenCV (V4 "Range strip", 2026-10-21):
web_verify's reader on core/reading_range.py's engine, under CPython.

The reader is held to _view (the bench's own read) view by view, the top
view cache to the uncached pixels, and the measured range to an independent
oracle: fresh cases, rendered by verify.camera and read by OpenCV's detector
directly -- not through the engine -- must read inside the far end and stop
reading past it (and the same check rejects a far end that is wrong). Then
the slices the browser runs, the facade calls, the camera library, and the
table a script prints: on ONE OpenCV, the newest installed unless asked
(the browser's 4.11 when that Python is there:
tools/requirements-browser-opencv.txt; docs/peps/0003 decision 3)."""
from __future__ import annotations

import copy
import json
import math

import pytest

cv2 = pytest.importorskip("cv2")

from aruco_studio import opencv_choice as OC              # noqa: E402
from aruco_studio import web_api as W                      # noqa: E402
from aruco_studio import web_verify as V                   # noqa: E402
from aruco_studio.core import cameras as CAMS              # noqa: E402
from aruco_studio.core import reading_range as RR          # noqa: E402
from aruco_studio.verify import camera as C                # noqa: E402

INK = dict(copy.deepcopy(next(p for p in W.presets() if p["name"] == "Inkjet · Letter vinyl")), cell_step_mm=0.0)
# the browser's OpenCV, beside the main checkout's .venv (tools/requirements-browser-opencv.txt);
# found as a run finds it (opencv_choice: this checkout's venvs, then the main one's)
CV411 = next((c["python"] for c in OC.installed() if c["opencv"].startswith("4.11.")), None)


def single(mm=30.0, first=0, label=None):
    lb = {"on": False, "text": "#{id}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0, "offset_mm": [0.0, 0.0]}
    lb.update(label or {})
    m = {"type": "single", "dictionary": "DICT_4X4_50", "first_id": first, "auto": False, "marker_mm": mm,
         "checker_mm": 0.0, "separation_mm": 0.0, "cols": 1, "rows": 1, "turn": 0, "flip": False,
         "quiet_modules": 1.0, "corner_mark": "none"}
    return {"rect": {"cx": 0.0, "cy": 0.0, "w": mm + 10.0, "h": mm + 10.0, "angle_deg": 0.0}, "marker": m,
            "label": lb, "preset": INK, "reference_face": False}


def grid3(first=19, mm=30.0):
    """Zach's document's board B (docs/build_verify_test_proposals.py's req)."""
    sep = round(mm / 3.0, 1)
    m = {"type": "grid", "dictionary": "DICT_4X4_50", "first_id": first, "auto": False, "marker_mm": mm,
         "checker_mm": 0.0, "separation_mm": sep, "cols": 3, "rows": 1, "turn": 0, "flip": False,
         "quiet_modules": 1.0, "corner_mark": "none"}
    lb = {"on": True, "text": "#{ids}", "height_mm": 0.0, "side": "below", "gap_mm": 2.0, "offset_mm": [0.0, 0.0],
          "place": "on_marker"}
    return {"rect": {"cx": 0.0, "cy": 0.0, "w": 3 * mm + 2 * sep + 3.5, "h": mm + 10.0, "angle_deg": 0.0},
            "marker": m, "label": lb, "preset": INK, "reference_face": False}


def scene_of(req):
    r = V.placed(req)
    d = V._plan(r)
    return d, C.scene_of(d, V._label(r, d))


# ------------------------------------------------------------------ the reader and the cache

@pytest.mark.parametrize("make", [single, grid3])
def test_the_reader_agrees_with_the_bench_view_by_view(make):
    d, scene = scene_of(make())
    cam = CAMS.camera_of("d435")
    read = V._cv_reader(d, scene, cam)
    seen = set()
    for dist in (300.0, 900.0, 1600.0, 2600.0):
        for v in RR.cases(6, 5):
            ok, missing = read(dist, v)
            out = V._view(d, scene, C.Cam(dist, 1920, 1080, 69.0), v, picture=False)
            assert (ok, missing) == (out["ok"], out["missing"]), (dist, v)
            seen.add(ok)
    assert seen == {True, False}          # both kinds of answer were compared


def test_the_top_view_cache_draws_the_same_pixels():
    d, scene = scene_of(grid3())
    cache = {}
    for dist in (110.0, 140.0, 300.0, 900.0):
        for v in RR.cases(4, 9) + [dict(RR.cases(1, 3)[0], occlusion=0.02)]:
            cam = C.Cam(dist, 1920, 1080, 69.0)
            a = C.simulate(scene, cam, v, cache=cache).img
            b = C.simulate(scene, cam, v).img
            assert a.tobytes() == b.tobytes(), (dist, v)
    assert 0 < len(cache) <= 8
    # near the camera the raster is capped: one picture serves every case there
    assert any(k[1] * k[2] > 1_000_000 for k in cache)


# ------------------------------------------------------------------ a measured range, and its oracle

def test_a_measured_board_range():
    rr = V.reading_range(grid3(), "d435")
    assert rr["measured"] and rr["opencv"] == cv2.__version__ and rr["version"] == RR.VERSION
    assert 50.0 < rr["near_mm"] < rr["far_mm"] < 5000.0
    assert rr["band_mm"][0] <= rr["far_mm"] <= rr["band_mm"][1]
    assert rr["geometry"]["ids"] == [19, 20, 21] and rr["weakest_id"] in (19, 20, 21)
    assert rr["camera"]["id"] == "d435" and rr["camera"]["resolution"] == [1920, 1080]
    assert len(rr["rows"]) >= RR.FIT_DISTANCES and all(r["n"] == RR.N_CASES for r in rr["rows"])
    assert json.dumps(V.reading_range(grid3(), "d435"), sort_keys=True) == json.dumps(rr, sort_keys=True)


def _direct_rate(req, distance, n=96, seed=777):
    """The share of fresh cases that read every id at `distance`, rendered and
    read here, not through the engine (its own seeds, its own jitter)."""
    d, scene = scene_of(req)
    want = set(d["ids"])
    oks = 0
    for v, j in zip(RR.cases(n, seed), RR.jitters(n, seed + 1)):
        sim = C.simulate(scene, C.Cam(distance * j, 1920, 1080, 69.0), v)
        got = set(C._det.detect(sim.img, d, params=C.parameters_for(sim))["ids"])
        oks += got == want
    return oks / n


def _separates(req, far):
    """The far end separates reading from not: inside it nearly every fresh
    case reads, well past it clearly fewer than P_READ do."""
    return _direct_rate(req, 0.75 * far) >= 0.92 and _direct_rate(req, 1.4 * far) < RR.P_READ


def test_the_far_end_agrees_with_opencv_read_directly():
    req = single(30.0, first=3)
    rr = V.reading_range(req, "d435")
    assert _separates(req, rr["far_mm"])
    # the ruler can fail: far ends half or 2.5 x the measured one are rejected
    assert not _separates(req, 0.5 * rr["far_mm"])
    assert not _separates(req, 2.5 * rr["far_mm"])
    # and the analytic sense check: a cell spans a few pixels at the far end (blur
    # up to 1.5 px and tilt up to 45 deg need more than the 3.1 px head-on limit)
    f = RR.focal_px(1920, 69.0)
    assert 2.0 <= rr["geometry"]["cell_mm"] * f / rr["far_mm"] <= 8.0
    # the near end: no nearer than the board filling 90 % of the frame
    u0, v0, u1, v1 = rr["geometry"]["bounds_mm"]
    assert rr["near_mm"] >= max((u1 - u0) * f / (0.9 * 1920), (v1 - v0) * f / (0.9 * 1080)) - 0.1


def test_twice_the_size_reads_about_twice_as_far():
    """judge()'s size hint: a pinhole sees a board k x bigger from k x farther
    the same; the fit's fixed start (300 mm) and the seeds keep it from exact."""
    a = V.reading_range(single(30.0), "d435")
    b = V.reading_range(single(60.0), "d435")
    assert 1.7 <= b["far_mm"] / a["far_mm"] <= 2.3, (a["far_mm"], b["far_mm"])


def test_without_opencv_it_is_the_pinhole_model(monkeypatch):
    monkeypatch.setattr(V, "cv2", None)
    rr = V.reading_range(single(30.0), "d435")
    assert rr["measured"] is False and rr["opencv"] is None and rr["far_mm"] > rr["near_mm"]
    with pytest.raises(ImportError, match="numpy and OpenCV"):
        V.reading_range(single(30.0), "d435", reader="opencv")


# ------------------------------------------------------------------ the browser's slices, the facade

def test_slices_give_the_one_call_answer_and_cancel_frees_the_job():
    req = single(25.0, first=4)
    whole = V.reading_range(req, "d455")
    st = V.range_start(req, "d455")
    assert st["done"] is False and st["renders"] == 0
    steps = 0
    while True:
        out = V.range_step(st["job"], 30.0)
        steps += 1
        if out["done"]:
            break
        assert 0.0 <= out["fraction"] <= 1.0 and out["phase"] in ("bracket", "fit", "near")
    assert steps > 3 and json.dumps(out["result"], sort_keys=True) == json.dumps(whole, sort_keys=True)
    with pytest.raises(ValueError, match="no reading-range job"):
        V.range_step(st["job"])
    st2 = V.range_start(req, "d455")
    assert V.range_step(st2["job"], 0)["renders"] == 1          # one view at least, even with no time
    assert V.range_cancel(st2["job"]) == {"job": st2["job"], "cancelled": True}
    assert V.range_cancel(st2["job"])["cancelled"] is False


def test_the_worker_calls():
    lib = json.loads(W.call("cameras", "{}"))["result"]
    assert [c["id"] for c in lib] == [c["id"] for c in CAMS.CAMERAS]
    out = json.loads(W.call("reading_range", json.dumps({"req": single(30.0), "camera": "d435", "reader": "analytic"})))["result"]
    assert out["measured"] is False and out["far_mm"]
    j = json.loads(W.call("range_judge", json.dumps({"range": out, "need": {"max_mm": out["far_mm"] * 2}})))["result"]
    assert j["verdict"] == "fail" and j["size_mm"] == pytest.approx(math.ceil(60.0 / 0.5) * 0.5, abs=0.5)
    st = json.loads(W.call("range_start", json.dumps({"req": single(30.0), "camera": {"resolution": [1280, 720], "hfov_deg": 60}})))["result"]
    assert json.loads(W.call("range_cancel", json.dumps({"job": st["job"]})))["result"]["cancelled"] is True
    bad = json.loads(W.call("reading_range", json.dumps({"req": single(30.0), "camera": "nope"})))
    assert "no camera 'nope'" in bad["error"]


# ------------------------------------------------------------------ the camera library

def test_every_camera_cites_its_maker():
    for c in CAMS.library():
        assert c["sources"] and all(s["url"].startswith("https://") and s["accessed"] for s in c["sources"]), c["id"]
        w, h = c["resolution"]
        assert 640 <= w <= 8000 and 360 <= h <= 6000 and 30 <= c["hfov_deg"] <= 120, c["id"]
        assert c["shutter"] in ("global", "rolling") and c["note"]
    ids = [c["id"] for c in CAMS.CAMERAS]
    assert len(ids) == len(set(ids)) and CAMS.DEFAULT in ids
    for want in ("d405", "d415", "d435", "d455", "oakd", "oakd12", "zed2", "c920", "picam3", "iphone"):
        assert want in ids


def test_the_numbers_the_makers_state_and_the_ones_worked_out():
    get = {c["id"]: c for c in CAMS.CAMERAS}
    # WHY pinned: the first lookup carried the D430/D450 depth FOV (87°) for the D405's colour
    assert get["d405"]["hfov_deg"] == 84.0 and get["d405"]["resolution"] == [1280, 720]
    assert get["d435"]["hfov_deg"] == 69.0 and get["d455"]["hfov_deg"] == 90.0
    assert get["c920"]["hfov_deg"] == 70.4          # 78° diagonal on 16:9
    # 1066 px focal length: 84.0 / 92.0 (Stereolabs states 84 / 92; a draft carried 84.8 / 92.2)
    assert get["zed2"]["hfov_deg"] == 84.0 and get["zed2k"]["hfov_deg"] == 92.0
    assert get["oakd"]["hfov_deg"] == 66.1          # the 4K crop of the 69° 12 MP frame
    assert get["iphone"]["hfov_deg"] == 71.6        # 24 mm equivalent on 4:3
    assert get["picam3"]["focus_mm"] == 100.0 and get["picam3w"]["focus_mm"] == 50.0 and get["oakd12"]["focus_mm"] == 80.0


def test_a_custom_camera_is_checked_in_words():
    assert CAMS.camera_of({"resolution": [800, 600], "hfov_deg": 60})["focus_mm"] is None
    for bad in ({"resolution": [8, 8], "hfov_deg": 60}, {"resolution": [800, 600], "hfov_deg": 0}, {"hfov_deg": 60}, 42):
        with pytest.raises(ValueError):
            CAMS.camera_of(bad)


# ------------------------------------------------------------------ the table a script prints

def test_the_range_table_and_the_command_line(tmp_path, capsys):
    items = [{"name": "Single #3", "req": single(30.0, first=3)}, {"name": "Single #5", "req": single(20.0, first=5),
                                                                  "need": {"min_mm": 200.0, "max_mm": 10000.0}}]
    rows = V.range_table(items, "d435", need={"max_mm": 500.0}, reader="analytic")
    assert [r["name"] for r in rows] == ["Single #3", "Single #5"]
    assert rows[0]["verdict"] == "pass" and rows[1]["verdict"] == "fail"      # the item's own need wins
    text = V.table_text(rows)
    assert "| Single #3 | #3 |" in text and "PASS" in text and "FAIL: Short by" in text and "pinhole model" in text
    f = tmp_path / "reqs.json"
    f.write_text(json.dumps(items))
    assert V.main([str(f), "--camera", "d435", "--need", ":500", "--analytic"]) == 0
    assert "| Single #5 | #5 |" in capsys.readouterr().out


def test_a_table_is_one_opencv_the_newest_installed_by_default(tmp_path, capsys):
    """Zach (2026-10-21): "Let's only run one, but you can choose, and by
    default it should be the most recent one". Every row's views are drawn
    and read by the one OpenCV the table names, the newest installed."""
    newest = max((c["opencv"] for c in OC.installed()), key=OC.version_key)
    items = [{"name": "Single", "req": single(30.0, first=3)}]
    rows = V.range_table(items, "d435", need={"max_mm": 900.0})
    assert {r["range"]["opencv"] for r in rows} == {newest} and rows[0]["range"]["measured"]
    assert not any(k in r for r in rows for k in ("by_opencv", "differs"))        # no second OpenCV, no "worse of two"
    text = V.table_text(rows)
    assert text.splitlines()[0].endswith(f"· OpenCV {newest}") and "worse" not in text
    # the command line: the same, and --opencv for one that is not installed is refused in words
    f = tmp_path / "reqs.json"
    f.write_text(json.dumps(items))
    assert V.main([str(f), "--camera", "d435", "--need", ":900", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["range"]["opencv"] == newest
    assert V.main([str(f), "--opencv", "3.4"]) == 2
    assert "--opencv 3.4: not installed here" in capsys.readouterr().err


@pytest.mark.skipif(CV411 is None, reason="no .venv-cv411 (the browser's OpenCV): tools/requirements-browser-opencv.txt")
def test_the_table_on_another_opencv_is_that_ones_alone(tmp_path, capsys):
    """--opencv 4.11: the table is the browser's OpenCV's (run in its Python),
    each range exactly what that Python's reading_range answers."""
    items = [{"name": "Single", "req": single(30.0, first=3)}]
    rows = V.range_table(items, "d435", opencv="4.11")
    assert [r["range"]["opencv"] for r in rows] == ["4.11.0"]
    theirs = OC.call(OC.choose("4.11"), "aruco_studio.web_verify", "reading_range", single(30.0, first=3), "d435")
    assert json.dumps(rows[0]["range"], sort_keys=True) == json.dumps(theirs, sort_keys=True)
    assert V.table_text(rows).splitlines()[0].endswith("· OpenCV 4.11.0")
    f = tmp_path / "reqs.json"
    f.write_text(json.dumps(items))
    assert V.main([str(f), "--opencv", str(CV411), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["range"]["opencv"] == "4.11.0"
