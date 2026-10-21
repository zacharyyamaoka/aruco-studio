"""Verify's camera library (V4 "Range strip", Zach 2026-10-21): "instead of me
having to read out the camera specs... some standard ones for RealSense etc.
so I could search for them and just click it".

Each entry is the stream an ArUco pipeline reads -- its resolution (W, H px)
and its horizontal field of view across W (`hfov_deg`) -- with the maker's
own document as its source (SOURCES, accessed 2026-10-21; every number was
re-read from the source, the tables named in `note`). `focus_mm` is the
nearest distance the maker says the lens focuses at (None: not stated, or a
fixed focus with no figure). `derived` names an HFOV worked out from what the
maker states (a diagonal FOV, a 35 mm equivalent, a focal length in pixels)
rather than stated as such.

WHY these numbers and not the depth streams': Verify reads the marker in the
colour image, so a RealSense's depth FOV (87 deg on a D435) never applies.
The D405's colour comes from its left depth imager through the ISP, and its
colour HFOV is 84 deg (datasheet table 3-20), not the 87 deg of the D430 /
D450 depth stream a first lookup carried.

Standard library only (core/): the UI asks for it through web_api
("cameras"), the reading range resolves a camera id with get().
"""
from __future__ import annotations

import copy
import math

ACCESSED = "2026-10-21"

# number -> (title, url); `sources` in an entry lists these numbers
SOURCES = {
    1: ("RealSense D400 Series datasheet, March 2026 (tables 3-18 D415 colour, 3-19 D450 colour, "
        "3-20 D401/D405 colour, 3-49 FOV per model, 4-2..4-4 streams)",
        "https://www.realsenseai.com/wp-content/uploads/2026/03/RealSense-D400-Series-Datasheet-Mar-2026.pdf"),
    2: ("Luxonis OAK-D datasheet, section 5.1 (colour camera: IMX378, 4056 x 3040, DFOV 81 / HFOV 69 / "
        "VFOV 55, auto focus 8 cm to infinity)",
        "https://raw.githubusercontent.com/luxonis/depthai-hardware/master/BW1098OAK_USB3C/Datasheet/OAK-D_Datasheet.pdf"),
    3: ("Luxonis docs: ColorCamera node (video and preview are at most 4K, 3840 x 2160, cropped from isp)",
        "https://docs.luxonis.com/software/depthai-components/nodes/color_camera"),
    4: ("Stereolabs support: camera focal length and field of view (HD1080 and HD2K: 1066 px, "
        "fov = 2 atan(pixels / (2 f)))",
        "https://support.stereolabs.com/hc/en-us/articles/360007395634-What-is-the-camera-focal-length-and-field-of-view"),
    5: ("Logitech C920 HD Pro product page (1080p, a diagonal, fixed 78 deg field of view)",
        "https://www.logitech.com/en-us/products/webcams/c920-pro-hd-webcam.960-001055.html"),
    6: ("Raspberry Pi camera documentation (Camera Module 3 and 3 Wide: 4608 x 2592, HFOV 66 / 102 deg, "
        "focus from about 10 / 5 cm)",
        "https://www.raspberrypi.com/documentation/accessories/camera.html"),
    7: ("Apple Support: iPhone 16 Pro technical specifications (48 MP Fusion: 24 mm, f/1.78; 4K video)",
        "https://support.apple.com/121031"),
}


def _hfov_from_diagonal(dfov_deg: float, w: int, h: int) -> float:
    """The horizontal FOV of a rectilinear lens whose diagonal FOV is given."""
    t = math.tan(math.radians(dfov_deg) / 2.0) * w / math.hypot(w, h)
    return math.degrees(2.0 * math.atan(t))


def _hfov_from_focal_px(width_px: int, f_px: float) -> float:
    return math.degrees(2.0 * math.atan(width_px / (2.0 * f_px)))


def _hfov_cropped(hfov_deg: float, full_w: int, crop_w: int) -> float:
    """The HFOV of a centred crop `crop_w` of a frame `full_w` wide."""
    return math.degrees(2.0 * math.atan(math.tan(math.radians(hfov_deg) / 2.0) * crop_w / full_w))


def _r1(v: float) -> float:
    return round(v, 1)


# A 24 mm (35 mm equivalent) lens on a 4:3 frame: the equivalent's diagonal
# (43.27 mm) with the frame's 4:3 width, 34.6 mm (Apple states no FOV).
_IPHONE_HFOV = math.degrees(2.0 * math.atan((math.hypot(36.0, 24.0) * 0.8 / 2.0) / 24.0))

# id, name, maker, stream, (W, H), hfov, focus_mm, shutter, sources, note, derived
CAMERAS = [
    {"id": "d405", "name": "RealSense D405", "maker": "Intel RealSense", "stream": "colour 1280×720",
     "resolution": [1280, 720], "hfov_deg": 84.0, "focus_mm": None, "shutter": "global", "sources": [1],
     "note": "colour from the left imager (OV9782) through the ISP, table 4-4; HFOV 84 ± 1°, table 3-20. "
             "No colour focus distance is stated (100 mm is the depth Min-Z at 1280×720, table 4-12)",
     "derived": ""},
    {"id": "d415", "name": "RealSense D415", "maker": "Intel RealSense", "stream": "colour 1920×1080",
     "resolution": [1920, 1080], "hfov_deg": 69.4, "focus_mm": None, "shutter": "rolling", "sources": [1],
     "note": "colour sensor HFOV 69.4°, fixed focus, table 3-18", "derived": ""},
    {"id": "d435", "name": "RealSense D435", "maker": "Intel RealSense", "stream": "colour 1920×1080",
     "resolution": [1920, 1080], "hfov_deg": 69.0, "focus_mm": None, "shutter": "rolling", "sources": [1],
     "note": "colour camera FOV H 69 / V 42 / D 77, table 3-49 (OV2740); the camera BAM owns", "derived": ""},
    {"id": "d455", "name": "RealSense D455", "maker": "Intel RealSense", "stream": "colour 1280×800",
     "resolution": [1280, 800], "hfov_deg": 90.0, "focus_mm": None, "shutter": "global", "sources": [1],
     "note": "colour sensor HFOV 90°, global shutter, table 3-19", "derived": ""},
    {"id": "oakd12", "name": "Luxonis OAK-D", "maker": "Luxonis", "stream": "colour 12 MP",
     "resolution": [4056, 3040], "hfov_deg": 69.0, "focus_mm": 80.0, "shutter": "rolling", "sources": [2],
     "note": "IMX378 at its full 4056×3040 (the isp output); auto focus 8 cm to ∞ (the fixed-focus variant: 50 cm)",
     "derived": ""},
    {"id": "oakd", "name": "Luxonis OAK-D", "maker": "Luxonis", "stream": "colour 1080p",
     "resolution": [1920, 1080], "hfov_deg": _r1(_hfov_cropped(69.0, 4056, 3840)), "focus_mm": 80.0,
     "shutter": "rolling", "sources": [2, 3],
     "note": "Luxonis states no FOV per mode: 1080p is taken as the 4K video crop (3840 of the sensor's 4056 px "
             "across) binned, so narrower than the 12 MP frame's 69°",
     "derived": "2·atan(3840/4056 · tan 34.5°)"},
    {"id": "zed2", "name": "Stereolabs ZED 2", "maker": "Stereolabs", "stream": "left eye 1080p",
     "resolution": [1920, 1080], "hfov_deg": _r1(_hfov_from_focal_px(1920, 1066.0)), "focus_mm": None,
     "shutter": "rolling", "sources": [4],
     "note": "HD1080 focal length 1066 px (2.1 mm lens); 110° is the raw sensor's maximum, not this mode's",
     "derived": "2·atan(1920 / (2 · 1066))"},
    {"id": "zed2k", "name": "Stereolabs ZED 2", "maker": "Stereolabs", "stream": "left eye 2.2K",
     "resolution": [2208, 1242], "hfov_deg": _r1(_hfov_from_focal_px(2208, 1066.0)), "focus_mm": None,
     "shutter": "rolling", "sources": [4], "note": "HD2K focal length 1066 px (2.1 mm lens)",
     "derived": "2·atan(2208 / (2 · 1066))"},
    {"id": "c920", "name": "Logitech C920", "maker": "Logitech", "stream": "1080p",
     "resolution": [1920, 1080], "hfov_deg": _r1(_hfov_from_diagonal(78.0, 16, 9)), "focus_mm": None,
     "shutter": "rolling", "sources": [5],
     "note": "Logitech gives a 78° diagonal (taken on the 16:9 frame); no focus distance is stated",
     "derived": "78° diagonal on 16:9"},
    {"id": "picam3", "name": "Raspberry Pi Camera Module 3", "maker": "Raspberry Pi", "stream": "full sensor",
     "resolution": [4608, 2592], "hfov_deg": 66.0, "focus_mm": 100.0, "shutter": "rolling", "sources": [6],
     "note": "IMX708, motorised focus from about 10 cm", "derived": ""},
    {"id": "picam3w", "name": "Raspberry Pi Camera Module 3 Wide", "maker": "Raspberry Pi",
     "stream": "full sensor", "resolution": [4608, 2592], "hfov_deg": 102.0, "focus_mm": 50.0,
     "shutter": "rolling", "sources": [6], "note": "IMX708, motorised focus from about 5 cm", "derived": ""},
    {"id": "iphone", "name": "iPhone 16 Pro · Main", "maker": "Apple", "stream": "4K video",
     "resolution": [3840, 2160], "hfov_deg": _r1(_IPHONE_HFOV), "focus_mm": None, "shutter": "rolling",
     "sources": [7],
     "note": "48 MP Fusion, 24 mm: Apple states no field of view or focus distance; 4K is taken to keep the "
             "4:3 frame's width",
     "derived": "24 mm (35 mm equiv.) on 4:3"},
]

DEFAULT = "d435"
# what search matches besides the name, the stream and the maker
_KEYWORDS = {"d405": "intel depth", "d415": "intel depth", "d435": "intel depth bam", "d455": "intel depth",
             "oakd12": "oak d depthai imx378", "oakd": "oak d depthai imx378", "zed2": "zed stereo",
             "zed2k": "zed stereo", "c920": "webcam usb", "picam3": "raspberry pi imx708 picamera",
             "picam3w": "raspberry pi imx708 picamera wide", "iphone": "apple phone"}


def library() -> list:
    """Every camera, its sources spelled out ({title, url, accessed}): what
    the UI's picker lists and searches."""
    out = []
    for c in CAMERAS:
        e = copy.deepcopy(c)
        e["sources"] = [{"title": SOURCES[n][0], "url": SOURCES[n][1], "accessed": ACCESSED} for n in c["sources"]]
        e["keywords"] = _KEYWORDS.get(c["id"], "")
        out.append(e)
    return out


def get(camera_id: str) -> dict:
    """One camera by id (a copy); KeyError naming the ids when unknown."""
    for c in CAMERAS:
        if c["id"] == camera_id:
            return copy.deepcopy(c)
    raise KeyError(f"no camera {camera_id!r}: one of {', '.join(c['id'] for c in CAMERAS)}")


def camera_of(cam) -> dict:
    """A camera for the reading range: a library id ("d435"), or a dict with
    `resolution` [W, H] and `hfov_deg` (`focus_mm`, `id`, `name` optional).
    -> {id, name, resolution, hfov_deg, focus_mm}; ValueError in words."""
    if isinstance(cam, str):
        cam = get(cam)
    if not isinstance(cam, dict):
        raise ValueError("a camera is a library id or {resolution, hfov_deg}")
    try:
        w, h = (int(v) for v in cam["resolution"])
        hfov = float(cam["hfov_deg"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("a camera needs resolution [W, H] px and hfov_deg") from None
    if w < 16 or h < 16 or not 1.0 <= hfov < 179.0:
        raise ValueError(f"camera {w}×{h} px, {hfov:g}°: at least 16 px a side and an HFOV of 1 to 179°")
    focus = cam.get("focus_mm")
    focus = float(focus) if focus not in (None, 0, 0.0, "") else None
    if focus is not None and not focus > 0:
        raise ValueError("focus_mm must be above 0, or null")
    return {"id": str(cam.get("id") or "custom"), "name": str(cam.get("name") or "Custom camera"),
            "resolution": [w, h], "hfov_deg": hfov, "focus_mm": focus}
