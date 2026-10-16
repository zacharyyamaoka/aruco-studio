# Ported from REF ArucoMarkers/aruco_prusa.py at c8216ff. The numbers half
# (length, nozzle_of, width_of, _system, _parents, describe) is copied verbatim;
# reading is done on TEXT here (parse_ini / parse_bundle), and resolve /
# profile / aruco_profiles take a PrusaSources (what a config folder holds)
# instead of a folder. The folder walk (config_dir, user_prints) is the
# server's (server/store.py, M2b); tests build PrusaSources from the fixture.
"""PrusaSlicer's print profiles, READ ONLY: what an ArUco print preset needs
from one -- its nozzle, line width and layer heights (aruco_presets;
docs/design_aruco_print_presets.md).

Zach, 2026-10-14, after research on printing ArUco tags: "make each cell a
clean multiple of the line width". His own profiles (measured that day):

    print/0.32mm SPEED @MK4IS 0.6 - Aruco.ini     inherits 0.32mm SPEED @MK4IS 0.6
        layer 0.32, first layer 0.2, extrusion_width 0.68 (top infill 0.55),
        arachne; nozzle 0.6 (compatible_printers_condition)
    print/0.15mm SPEED @MK4IS 0.25 - Aruco Black.ini   inherits 0.15mm SPEED @MK4IS 0.25
        layer 0.15, first layer 0.2, widths 0.27 (first layer 0.32)

Where PrusaSlicer keeps them (never written here):

    <config>/print/<name>.ini     a user print preset: a full config dump,
                                  "inherits" naming the system preset it came from
    <config>/vendor/<Vendor>.ini  the system bundles: [print:<name>] sections,
                                  "inherits = a; b" (later parents win, own keys last)
    <config> = %APPDATA%/PrusaSlicer (Windows), ~/Library/Application Support/
               PrusaSlicer (macOS), ~/.config/PrusaSlicer (Linux), or the
               env var BAM_ARUCO_PRUSASLICER_DIR (tests: a fixture copy)

Widths as PrusaSlicer reads them: a number is mm; 0 (or empty) is auto --
another width that is set, else 1.125 x the nozzle; "105%" is a percentage
of the LAYER height (the first layer's: of the first layer height). The
nozzle is not in a print profile: it comes from its
compatible_printers_condition ("nozzle_diameter[0]==0.6"), else its name
("@MK4IS 0.6", "0.6 nozzle"), else its output file name ("_0.6n_").

Standard library only; nothing here raises on a bad file (a profile that
cannot be read is skipped, with a note).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CONFIG_ENV = "BAM_ARUCO_PRUSASLICER_DIR"
AUTO_WIDTH = 1.125            # PrusaSlicer's auto extrusion width: 1.125 x the nozzle
ARUCO_WORD = "aruco"          # a print profile with this in its name is a built-in preset
WIDTH_KEYS = ("extrusion_width", "perimeter_extrusion_width",
              "external_perimeter_extrusion_width", "solid_infill_extrusion_width",
              "top_infill_extrusion_width", "infill_extrusion_width",
              "first_layer_extrusion_width")


# ------------------------------------------------------------------ reading

def parse_ini(text):
    """REF read_ini on the file's text: a flat PrusaSlicer .ini (a user
    preset): {key: value}, comments skipped."""
    out = {}
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s[0] in "#;" or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_bundle(text):
    """REF read_bundle on the file's text: a vendor bundle's PRINT
    sections: {name: {key: value}}."""
    out, cur = {}, None
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s[0] in "#;":
            continue
        if s[0] == "[" and s.endswith("]"):
            head = s[1:-1]
            cur = out.setdefault(head[6:], {}) if head.startswith("print:") else None
            continue
        if cur is not None and "=" in s:
            k, v = s.split("=", 1)
            cur[k.strip()] = v.strip()
    return out


@dataclass
class PrusaSources:
    """What PrusaSlicer's config folder holds, read: the user's print
    presets ({name: config}, `<config>/print/<name>.ini`, sorted by file
    name as REF's glob did) and the vendor bundles' print sections (one dict
    per `<config>/vendor/*.ini`, sorted by path)."""
    user: Dict[str, dict] = field(default_factory=dict)
    bundles: List[dict] = field(default_factory=list)


def sources_from_texts(user_texts, bundle_texts):
    """{name: .ini text} and [bundle text] -> PrusaSources."""
    return PrusaSources(user={k: parse_ini(v) for k, v in sorted((user_texts or {}).items())},
                        bundles=[parse_bundle(t) for t in (bundle_texts or [])])


def user_prints(src):
    """The user's print presets: [{"name"}], by name (REF also gave the path)."""
    return [{"name": n} for n in sorted((src or PrusaSources()).user)]


def _parents(cfg):
    return [p.strip() for p in (cfg.get("inherits") or "").split(";") if p.strip()]


def _system(name, bundles, seen):
    """A system print preset with every parent applied (later parents win,
    its own keys last), or None when no bundle has it."""
    for b in bundles:
        sec = b.get(name)
        if sec is None:
            continue
        out = {}
        for p in _parents(sec):
            if p in seen:
                continue
            got = _system(p, [b] + [x for x in bundles if x is not b], seen | {p})
            if got:
                out.update(got)
        out.update({k: v for k, v in sec.items() if k != "inherits"})
        return out
    return None


def resolve(name, src):
    """A print preset by name -- the user's (its system parent under it) or
    a system one -- as one config: (config, chain), chain = the names it
    came from, the preset first. (None, []) when nothing has that name."""
    src = src or PrusaSources()
    bundles = src.bundles
    if name in src.user:
        own = src.user[name]
        out, chain = {}, [name]
        for p in _parents(own):
            got = _system(p, bundles, {p})
            if got:
                out.update(got)
                chain.append(p)
        out.update({k: v for k, v in own.items() if k != "inherits"})
        return out, chain
    got = _system(name, bundles, {name})
    return (got, [name]) if got else (None, [])


# ------------------------------------------------------------------ numbers

def _float(v):
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def length(value, of):
    """A PrusaSlicer length: "0.68" mm, "105%" of `of`, "0" / "" -> 0.0;
    None when unreadable (or a percentage of an unknown length)."""
    s = str(value if value is not None else "").strip()
    if not s:
        return 0.0
    if s.endswith("%"):
        p = _float(s[:-1])
        return None if p is None or of is None else p / 100.0 * of
    return _float(s)


def nozzle_of(cfg, name=""):
    """The nozzle (mm) a print profile is for, or None."""
    cond = (cfg or {}).get("compatible_printers_condition") or ""
    m = re.search(r"nozzle_diameter\[0\]\s*==\s*([0-9]*\.?[0-9]+)", cond)
    if m:
        return float(m.group(1))
    for pat in (r"([0-9]*\.[0-9]+)\s*nozzle", r"@\S+\s+([0-9]*\.[0-9]+)\b"):
        m = re.search(pat, name or "")
        if m:
            return float(m.group(1))
    m = re.search(r"_([0-9]*\.[0-9]+)n_", (cfg or {}).get("output_filename_format") or "")
    return float(m.group(1)) if m else None


def width_of(cfg, key, nozzle, layer, first_layer):
    """One extrusion width (mm) as PrusaSlicer uses it: its own value, else
    extrusion_width, else 1.125 x the nozzle; None when unknown."""
    of = first_layer if key.startswith("first_layer") else layer
    w = length(cfg.get(key), of)
    if w:
        return w
    if key != "extrusion_width":
        w = length(cfg.get("extrusion_width"), layer)
        if w:
            return w
    return AUTO_WIDTH * nozzle if nozzle else None


def _r(x, nd=4):
    return None if x is None else round(float(x), nd)


def profile(name, src=None):
    """What an ArUco preset keeps of a print profile, or None:
    {"name", "nozzle_mm", "line_mm" (extrusion_width, resolved), "layer_mm",
     "first_layer_mm", "widths": {key: mm}, "perimeter_generator", "ironing",
     "source": "prusaslicer", "inherits": [chain]}."""
    cfg, chain = resolve(name, src)
    if not cfg:
        return None
    nozzle = nozzle_of(cfg, name)
    layer = length(cfg.get("layer_height"), None)
    first = length(cfg.get("first_layer_height"), layer)
    widths = {k: _r(width_of(cfg, k, nozzle, layer, first)) for k in WIDTH_KEYS}
    return {"name": name, "nozzle_mm": _r(nozzle), "line_mm": widths["extrusion_width"],
            "layer_mm": _r(layer), "first_layer_mm": _r(first), "widths": widths,
            "perimeter_generator": cfg.get("perimeter_generator") or "",
            "ironing": (cfg.get("ironing") or "0") not in ("0", ""),
            "source": "prusaslicer", "inherits": chain[1:]}


def aruco_profiles(src=None):
    """The user's print profiles with "Aruco" in their name, read: [profile]."""
    out = []
    for up in user_prints(src):
        if ARUCO_WORD in up["name"].lower():
            try:
                p = profile(up["name"], src)
            except Exception:                      # noqa: BLE001
                p = None
            if p is not None and p.get("line_mm"):
                out.append(p)
    return out


def describe(p):
    """One line for the dialog: "0.32mm SPEED @MK4IS 0.6 - Aruco: nozzle 0.6,
    lines 0.68, layers 0.32 (first 0.2), arachne"."""
    if not p:
        return "no printer profile"
    bits = []
    for label, key in (("nozzle", "nozzle_mm"), ("lines", "line_mm"), ("layers", "layer_mm")):
        if p.get(key):
            bits.append(f"{label} {p[key]:g}")
    if p.get("first_layer_mm") and p.get("layer_mm"):
        bits[-1] += f" (first {p['first_layer_mm']:g})"
    if p.get("perimeter_generator"):
        bits.append(p["perimeter_generator"])
    head = p.get("name") or "no printer profile"
    return head + (": " + ", ".join(bits) if bits else "")
