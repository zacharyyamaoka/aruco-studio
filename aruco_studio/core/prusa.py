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

# M8c (not REF's): the privacy rule (M8 note 5.6). A physical printer is read
# through an ALLOW-LIST; every other preset drops its private keys on read, so
# a host, a key or a password never leaves this module.
PHYSICAL_KEYS = ("preset_names", "preset_name", "printer_technology", "host_type")
PRIVATE_PREFIXES = ("printhost_", "print_host", "octoprint_")   # octoprint_*: the old names
_PRIVATE_WORDS = ("apikey", "api_key", "password", "passwd", "secret", "token")
BUNDLE_KINDS = ("print", "printer", "printer_model", "vendor")
_SUSPECT_WORDS = ("host", "apikey", "api_key", "password", "passwd", "secret", "token")
_HEAD = re.compile(r"^[ \t]*\[([^\n]*)\][ \t]*\r?$", re.M)


_PRIVATE_RE = re.compile("^(?:" + "|".join(PRIVATE_PREFIXES) + ")|_host$|"
                         + "|".join(_PRIVATE_WORDS))


def private_key(key):
    """A key that may hold a host, a key or a password: never read
    (`host_type`, a word naming the kind of host, is not one)."""
    return _PRIVATE_RE.search((key or "").strip().lower()) is not None


def drop_private(text):
    """`text` without the lines whose key is private (private_key): the
    lines holding a suspect word are found with str.find (a 2 MB bundle in
    a few ms), each checked by its key."""
    text = text or ""
    low = text.lower()
    drop = set()
    for w in _SUSPECT_WORDS:
        i = low.find(w)
        while i >= 0:
            a = text.rfind("\n", 0, i) + 1
            b = text.find("\n", i)
            b = len(text) if b < 0 else b + 1
            key, sep, _v = text[a:b].partition("=")
            if sep and len(key) >= i - a and private_key(key):
                drop.add((a, b))
            i = low.find(w, b)
    if not drop:
        return text
    out, at = [], 0
    for a, b in sorted(drop):
        out.append(text[at:a])
        at = b
    out.append(text[at:])
    return "".join(out)


def _kv_lines(text):
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s[0] in "#;[" or "=" not in s:
            continue
        k, v = s.split("=", 1)
        yield k.strip(), v.strip()


def parse_private_free(text):
    """A flat .ini (a user printer preset) with every private key dropped."""
    return {k: v for k, v in _kv_lines(text) if not private_key(k)}


def split_names(value):
    """PrusaSlicer's list of strings ('"a";"b"' or 'a;b') -> [str]."""
    out = []
    for tok in re.findall(r'"(?:[^"\\]|\\.)*"|[^;]+', value or ""):
        tok = tok.strip()
        if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
            tok = tok[1:-1].replace('\\"', '"')
        if tok:
            out.append(tok)
    return out


def parse_physical(text):
    """A physical printer's .ini through the allow-list: {"preset_names":
    [str], "preset_name", "printer_technology", "host_type"} and NOTHING
    else (a missing key is absent; preset_names falls back to preset_name)."""
    out = {}
    for k, v in _kv_lines(text):
        if k in PHYSICAL_KEYS and not private_key(k):
            out[k] = split_names(v) if k == "preset_names" else v.strip().strip('"')
    if not out.get("preset_names") and out.get("preset_name"):
        out["preset_names"] = [out["preset_name"]]
    if out.get("preset_names") and not out.get("preset_name"):
        out["preset_name"] = out["preset_names"][0]
    return out


def _complete(text, newline=True):
    if not text or (newline and not text.endswith("\n")):
        return False
    for line in text.split("\n"):
        if "=" not in line:
            s = line.strip()
            if s and s[0] not in "#;[":
                return False
    return True


def ini_complete(text, kind):
    """Does a file of `kind` parse? ("physical", "print", "printer", "ini"
    (PrusaSlicer.ini: a [presets] section), "vendor" (a [vendor] section)).
    A half-written file gives False: every line a `key = value`, a comment
    or a section head, a newline at the end (not a bundle's: PrusaSlicer
    writes its last line without one), and for a physical printer its
    printer preset named, for PrusaSlicer.ini its [presets], for a bundle
    its [vendor]. A print or printer preset needs no key of its own (a
    partial preset file is still one)."""
    if not _complete(text, newline=kind != "vendor"):
        return False
    if kind == "physical":
        return bool(parse_physical(text).get("preset_names"))
    if kind == "ini":
        return "[presets]" in text
    if kind == "vendor":
        return "[vendor]" in text
    return True


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


def parse_bundle(text, kinds="print"):
    """REF read_bundle on the file's text: a vendor bundle's PRINT
    sections: {name: {key: value}}.

    M8c: `kinds` a tuple of section kinds ("print", "printer",
    "printer_model", "vendor", "filament", ...) -> {kind: {name: {key:
    value}}} in one pass ("vendor" has one section, named ""); the other
    sections are skipped unread (a bundle holds 7,620 filaments). A
    private key (`private_key`) is dropped on read in every kind."""
    many = not isinstance(kinds, str)
    want = tuple(kinds) if many else (kinds,)
    out = {k: {} for k in want}
    text = text or ""
    heads = list(_HEAD.finditer(text))
    for i, m in enumerate(heads):
        kind, _sep, name = m.group(1).strip().partition(":")
        if kind not in out:
            continue                                # a section of another kind: not read
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        cur = out[kind].setdefault(name, {})
        for line in text[m.end():end].splitlines():
            s = line.strip()
            if not s or s[0] in "#;" or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            if not private_key(k):
                cur[k] = v.strip()
    return out if many else out[want[0]]


@dataclass
class PrusaSources:
    """What PrusaSlicer's config folder holds, read: the user's print
    presets ({name: config}, `<config>/print/<name>.ini`, sorted by file
    name as REF's glob did) and the vendor bundles' print sections (one dict
    per `<config>/vendor/*.ini`, sorted by path)."""
    user: Dict[str, dict] = field(default_factory=dict)
    bundles: List[dict] = field(default_factory=list)
    # M8c (not REF's): the printers. Every private key is dropped before here.
    printers: Dict[str, dict] = field(default_factory=dict)     # <config>/printer/<name>.ini
    physical: Dict[str, dict] = field(default_factory=dict)     # through PHYSICAL_KEYS
    printer_bundles: List[dict] = field(default_factory=list)   # [printer:] per bundle
    models: List[dict] = field(default_factory=list)            # [printer_model:] per bundle
    vendors: List[dict] = field(default_factory=list)           # [vendor] per bundle
    selection: Optional[dict] = None                            # selected(PrusaSlicer.ini)
    installed: Dict[str, List[str]] = field(default_factory=dict)


def sources_from_texts(user_texts, bundle_texts, printer_texts=None, physical_texts=None,
                       ini_text=None):
    """{name: .ini text} and [bundle text] -> PrusaSources. M8c: the user's
    printer presets {name: text}, the physical printers {name: text} (read
    through PHYSICAL_KEYS) and PrusaSlicer.ini's text, each optional."""
    bundles, printers, models, vendors = [], [], [], []
    for t in bundle_texts or []:
        got = parse_bundle(t, kinds=BUNDLE_KINDS)
        bundles.append(got["print"])
        printers.append(got["printer"])
        models.append(got["printer_model"])
        vendors.append(got["vendor"].get("", {}))
    return PrusaSources(
        user={k: {a: b for a, b in parse_ini(v).items() if not private_key(a)}
              for k, v in sorted((user_texts or {}).items())},
        bundles=bundles, printer_bundles=printers, models=models, vendors=vendors,
        printers={k: parse_private_free(v) for k, v in sorted((printer_texts or {}).items())},
        physical={k: parse_physical(v) for k, v in sorted((physical_texts or {}).items())},
        selection=selected(ini_text) if ini_text is not None else None,
        installed=installed_models(ini_text) if ini_text is not None else {})


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


# ======================================================= the printers (M8c, not REF's)
# The physical printers resolved to their printer preset's numbers, the print
# presets that fit them, and the pair PrusaSlicer has selected now (M8 note
# 5.2). Read only, on texts; every private key was dropped on read.

def _unescape(v):
    """A PrusaSlicer string value as it is in memory: "\\n" a newline."""
    return (v or "").replace("\\n", "\n").replace("\\r", "\r")


def resolve_printer(name, src):
    """A printer preset by name -- the user's (`printers`, its system parent
    under it) or a bundle's -- as one config: (config, chain, "user" |
    "system"); (None, [], "") when nothing has that name."""
    src = src or PrusaSources()
    bundles = src.printer_bundles
    if name in src.printers:
        own = src.printers[name]
        out, chain = {}, [name]
        for p in [x.strip().strip('"') for x in _parents(own)]:
            got = _system(p, bundles, {p})
            if got:
                out.update(got)
                chain.append(p)
                chain += _chain_names(p, bundles)
        out.update({k: v for k, v in own.items() if k != "inherits"})
        return out, chain, "user"
    got = _system(name, bundles, {name})
    if not got:
        return None, [], ""
    return got, [name] + _chain_names(name, bundles), "system"


def _chain_names(name, bundles, seen=None):
    """The names a system preset inherits from, nearest first (for
    `compatible_printers`, which may name a parent)."""
    seen = set(seen or ()) | {name}
    for b in bundles:
        sec = b.get(name)
        if sec is None:
            continue
        out = []
        for p in [x.strip().strip('"') for x in _parents(sec)]:
            if p in seen:
                continue
            out.append(p)
            out += _chain_names(p, bundles, seen | {p})
        return out
    return []


def _first(value):
    """The first of a vector option ("0.6,0.6" -> "0.6")."""
    return (value or "").split(",")[0].strip()


def _bed(shape):
    try:
        pts = [tuple(float(c) for c in p.split("x")) for p in (shape or "").split(",") if p]
        return [round(max(p[0] for p in pts) - min(p[0] for p in pts), 4),
                round(max(p[1] for p in pts) - min(p[1] for p in pts), 4)]
    except (ValueError, IndexError):
        return None


def printer_of(name, src):
    """A printer preset's numbers, or None: {"preset", "source" (user /
    system), "inherits", "nozzle_mm", "extruders", "model", "variant",
    "notes", "technology", "bed_mm" [w, d], "bed_shape", "max_height_mm",
    "layer_mm" [min, max], "default_print", "default_filaments", "family",
    "config" (the resolved config, private keys dropped)}."""
    cfg, chain, kind = resolve_printer(name, src)
    if cfg is None:
        return None
    model = cfg.get("printer_model") or ""
    fam = ""
    for m in (src.models if src else []):
        if model in m:
            fam = m[model].get("family", "")
            break
    noz = _float(_first(cfg.get("nozzle_diameter")))
    return {"preset": name, "source": kind, "inherits": chain[1:],
            "nozzle_mm": _r(noz),
            "extruders": len([v for v in (cfg.get("nozzle_diameter") or "").split(",")
                              if v.strip()]) or 1,
            "model": model, "variant": cfg.get("printer_variant") or "",
            "notes": _unescape(cfg.get("printer_notes")),
            "technology": cfg.get("printer_technology") or "FFF", "family": fam,
            "bed_mm": _bed(cfg.get("bed_shape")), "bed_shape": cfg.get("bed_shape") or "",
            "max_height_mm": _float(cfg.get("max_print_height")),
            "layer_mm": [_r(_float(_first(cfg.get("min_layer_height")))),
                         _r(_float(_first(cfg.get("max_layer_height"))))],
            "default_print": (cfg.get("default_print_profile") or "").strip('"'),
            "default_filaments": split_names(cfg.get("default_filament_profile") or ""),
            "config": cfg}


# ------------------------------------------------------------------ the condition

class ConditionError(ValueError):
    """A condition outside the evaluator's subset: the answer is "maybe"."""


_TOKEN = re.compile(r"""\s*(?:
    (?P<num>[0-9]+\.?[0-9]*(?:[eE][-+]?[0-9]+)?|\.[0-9]+)
  | (?P<str>"(?:[^"\\]|\\.)*")
  | (?P<re>/(?:[^/\\]|\\.)*/)
  | (?P<op>==|!=|<>|<=|>=|=~|!~|&&|\|\||[()\[\]!<>])
  | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
)""", re.X)
# the options a print condition reads, with PrusaSlicer's default when a
# printer preset does not set them (anything else unset: "maybe")
_DEFAULTS = {"nozzle_high_flow": "0", "printer_notes": "", "printer_model": "",
             "printer_variant": "", "printer_vendor": "", "printer_settings_id": "",
             "single_extruder_multi_material": "0", "printer_technology": "FFF"}
_VECTORS = {"nozzle_diameter", "nozzle_high_flow", "max_layer_height", "min_layer_height",
            "extruder_colour", "retract_length", "extruder_offset"}


def _tokens(text):
    out, i, s = [], 0, text or ""
    while i < len(s):
        if s[i:].strip() == "":
            break
        m = _TOKEN.match(s, i)
        if not m or m.end() == i:
            raise ConditionError(f"cannot read {s[i:i + 12]!r}")
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
        i = m.end()
    return out


class _Eval:
    """PrusaSlicer's condition language, the subset Zach's files use: and,
    or, !, not, ==, !=, <, >, <=, >=, =~ /re/, !~ /re/ (a FULL match, as
    boost::regex_match), [i], strings, numbers, brackets. Three-valued: an
    unknown option or a type it cannot compare gives None ("maybe")."""

    def __init__(self, tokens, cfg):
        self.t, self.i, self.cfg = tokens, 0, cfg

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, kind=None, val=None):
        k, v = self.peek()
        if k is None or (kind and k != kind) or (val is not None and v != val):
            raise ConditionError(f"expected {val or kind}, got {v!r}")
        self.i += 1
        return v

    def word(self, w):
        k, v = self.peek()
        return k == "name" and v == w

    def expr(self):
        a = self.and_()
        while self.word("or") or self.peek() == ("op", "||"):
            self.i += 1
            b = self.and_()
            a = True if (a is True or b is True) else (None if None in (a, b) else False)
        return a

    def and_(self):
        a = self.not_()
        while self.word("and") or self.peek() == ("op", "&&"):
            self.i += 1
            b = self.not_()
            a = False if (a is False or b is False) else (None if None in (a, b) else True)
        return a

    def not_(self):
        if self.peek() == ("op", "!") or self.word("not"):
            self.i += 1
            v = self.not_()
            return None if v is None else (not v)
        return self.cmp()

    def cmp(self):
        a = self.atom()
        k, v = self.peek()
        if k == "op" and v in ("=~", "!~"):
            self.i += 1
            pat = self.take("re")[1:-1]
            if a is None:
                return None
            if not isinstance(a, str):
                a = _num_text(a)
            try:
                hit = re.fullmatch(pat, a, re.S) is not None
            except re.error as exc:
                raise ConditionError(f"a regex Python cannot read: {exc}") from None
            return hit if v == "=~" else not hit
        if k == "op" and v in ("==", "!=", "<>", "<", ">", "<=", ">="):
            self.i += 1
            b = self.atom()
            return _compare(a, b, v)
        return _truth(a)

    def atom(self):
        k, v = self.peek()
        if k == "op" and v == "(":
            self.i += 1
            got = self.expr()
            self.take("op", ")")
            return got
        if k == "num":
            self.i += 1
            return float(v)
        if k == "str":
            self.i += 1
            return bytes(v[1:-1], "utf-8").decode("unicode_escape")
        if k == "name":
            self.i += 1
            if v in ("true", "false"):
                return v == "true"
            idx = None
            if self.peek() == ("op", "["):
                self.i += 1
                idx = int(float(self.take("num")))
                self.take("op", "]")
            return self.lookup(v, idx)
        raise ConditionError(f"unexpected {v!r}")

    def lookup(self, name, idx):
        if name in self.cfg:
            raw = self.cfg[name]
        elif name in _DEFAULTS:
            raw = _DEFAULTS[name]
        else:
            return None                              # an option we do not know: maybe
        if idx is not None or name in _VECTORS:
            parts = [p.strip() for p in (raw or "").split(",")]
            if idx is None or idx >= len(parts):
                return None
            raw = parts[idx]
        else:
            raw = _unescape(raw)
            if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
                raw = raw[1:-1]
        x = _float(raw)
        if x is not None and name not in ("printer_notes", "printer_model", "printer_variant"):
            return x
        return raw


def _num_text(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


def _truth(v):
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, float):
        return v != 0.0
    return None                                      # a string as a condition: maybe


def _compare(a, b, op):
    if a is None or b is None:
        return None
    if isinstance(a, bool) or isinstance(b, bool):
        a, b = _truth(a), _truth(b)
        if a is None or b is None:
            return None
    if isinstance(a, float) != isinstance(b, float):
        x, y = _float(a) if isinstance(a, str) else a, _float(b) if isinstance(b, str) else b
        if x is None or y is None:
            return None
        a, b = x, y
    if op == "==":
        return abs(a - b) < 1e-9 if isinstance(a, float) else a == b
    if op in ("!=", "<>"):
        return not (abs(a - b) < 1e-9) if isinstance(a, float) else a != b
    if isinstance(a, str):
        return None
    return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]


def condition(text, printer_cfg):
    """A compatible_printers_condition on a printer's config -> True,
    False, or None (maybe: outside the subset, or an option unknown)."""
    if not (text or "").strip():
        return True
    try:
        tokens = _tokens(_unescape(text).strip())
        ev = _Eval(tokens, printer_cfg or {})
        got = ev.expr()
        if ev.i != len(tokens):
            raise ConditionError("trailing words")
        return got
    except (ConditionError, ValueError, IndexError):
        return None


def parses(text):
    """Does the evaluator read this condition (no ConditionError)?"""
    try:
        tokens = _tokens(_unescape(text or "").strip())
        ev = _Eval(tokens, {})
        ev.expr()
        return ev.i == len(tokens)
    except (ConditionError, ValueError, IndexError):
        return False


def fits(print_cfg, printer):
    """Does a print preset fit a printer (printer_of's dict)? -> "yes",
    "maybe" or "no". `compatible_printers` naming the printer preset (or
    a parent of it) decides first; else `compatible_printers_condition`;
    neither: yes. A maybe is never a silent no."""
    cps = split_names((print_cfg or {}).get("compatible_printers") or "")
    if cps:
        names = {printer.get("preset")} | set(printer.get("inherits") or [])
        return "yes" if names & set(cps) else "no"
    got = condition((print_cfg or {}).get("compatible_printers_condition") or "",
                    printer.get("config") or {})
    return {True: "yes", False: "no"}.get(got, "maybe")


def pair_profile(print_name, printer, src):
    """profile() of a print preset for one printer: the nozzle from the
    printer (printer_of), the line width and layers from the print preset
    (auto = 1.125 x that nozzle), and the printer block. None: no such print."""
    cfg, chain = resolve(print_name, src)
    if not cfg:
        return None
    nozzle = printer.get("nozzle_mm") or nozzle_of(cfg, print_name)
    layer = length(cfg.get("layer_height"), None)
    first = length(cfg.get("first_layer_height"), layer)
    widths = {k: _r(width_of(cfg, k, nozzle, layer, first)) for k in WIDTH_KEYS}
    return {"name": print_name, "nozzle_mm": _r(nozzle), "line_mm": widths["extrusion_width"],
            "layer_mm": _r(layer), "first_layer_mm": _r(first), "widths": widths,
            "perimeter_generator": cfg.get("perimeter_generator") or "",
            "ironing": (cfg.get("ironing") or "0") not in ("0", ""),
            "source": "prusaslicer", "inherits": chain[1:],
            "printer": {"physical": printer.get("physical") or "",
                        "preset": printer.get("preset") or "",
                        "model": printer.get("model") or "",
                        "variant": printer.get("variant") or ""}}


def print_names(src, system=False):
    """The print presets a printer could take: the user's, by name, then
    (`system`) every bundle's that is not abstract (`*name*`)."""
    src = src or PrusaSources()
    out = sorted(src.user)
    if system:
        seen = set(out)
        for b in src.bundles:
            for n in sorted(b):
                if n not in seen and not (n.startswith("*") and n.endswith("*")):
                    out.append(n)
                    seen.add(n)
    return out


def prints_for(printer, src, system=False, also=()):
    """[{name, fits, user, aruco, line_mm, layer_mm, first_layer_mm,
    nozzle_mm}] the print presets that fit (yes or maybe) a printer: the
    "Aruco" ones first, then by name. `also`: names listed whatever they
    fit (the selected print)."""
    out = []
    names = print_names(src, system)
    for n in also:
        if n and n not in names:
            names.append(n)
    for n in names:
        cfg, _chain = resolve(n, src)
        if not cfg:
            continue
        f = fits(cfg, printer)
        if f == "no" and n not in also:
            continue
        pp = pair_profile(n, printer, src)
        out.append({"name": n, "fits": f, "user": n in src.user,
                    "aruco": ARUCO_WORD in n.lower(),
                    "line_mm": pp["line_mm"], "layer_mm": pp["layer_mm"],
                    "first_layer_mm": pp["first_layer_mm"], "nozzle_mm": pp["nozzle_mm"]})
    out.sort(key=lambda p: (not p["aruco"], not p["user"], p["name"].lower()))
    return out


# ------------------------------------------------------------- PrusaSlicer.ini

def _ini_sections(text, want):
    out, cur = {}, None
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s[0] in "#;":
            continue
        if s[0] == "[" and s.endswith("]"):
            head = s[1:-1]
            cur = out.setdefault(head, {}) if any(head == w or head.startswith(w)
                                                  for w in want) else None
            continue
        if cur is not None and "=" in s:
            k, v = s.split("=", 1)
            if not private_key(k):
                cur[k.strip()] = v.strip()
    return out


def selected(ini_text):
    """What PrusaSlicer has selected now (PrusaSlicer.ini's [presets]; the
    pure half of beds_io.last_selected_presets): {"printer", "print",
    "filaments" [slot 1, ...], "physical_printer" (its name), "physical_preset"
    (its printer preset)}, or None without a printer."""
    p = _ini_sections(ini_text, ("presets",)).get("presets") or {}
    if not p.get("printer"):
        return None
    fil = [p.get("filament", "")]
    k = 1
    while f"filament_{k}" in p:
        fil.append(p[f"filament_{k}"])
        k += 1
    name, _sep, preset = (p.get("physical_printer") or "").partition(" * ")
    return {"printer": p["printer"], "print": p.get("print", ""), "filaments": fil,
            "physical_printer": name.strip(), "physical_preset": preset.strip()}


def installed_models(ini_text):
    """[vendor:...] `model:<MODEL> = <variants>`: {model: [variant]}."""
    out = {}
    for head, sec in _ini_sections(ini_text, ("vendor:",)).items():
        for k, v in sec.items():
            if k.startswith("model:"):
                out[k[6:]] = [x.strip() for x in v.split(";") if x.strip()]
    return out


def physical_printers(src, system=False):
    """Every physical printer resolved: [{name, technology, host_kind,
    presets, printer: printer_of(...) without its config (None: its preset
    is not found), prints: prints_for(...), current (PrusaSlicer has it
    selected), current_print}], by name."""
    src = src or PrusaSources()
    sel = src.selection or {}
    out = []
    for name in sorted(src.physical, key=str.lower):
        ph = src.physical[name]
        presets = list(ph.get("preset_names") or [])
        cur = name == sel.get("physical_printer")
        want = sel.get("physical_preset") if cur and sel.get("physical_preset") in presets \
            else (presets[0] if presets else "")
        pr = printer_of(want, src) if want else None
        entry = {"name": name, "technology": ph.get("printer_technology") or "FFF",
                 "host_kind": ph.get("host_type") or "", "presets": presets,
                 "preset": want, "printer": None, "prints": [], "current": cur,
                 "current_print": sel.get("print") if cur else None}
        if pr is not None:
            pr = dict(pr, physical=name)
            entry["prints"] = prints_for(pr, src, system,
                                         also=(sel.get("print"),) if cur else ())
            for p in entry["prints"]:
                p["current"] = bool(cur and p["name"] == sel.get("print"))
            entry["printer"] = {k: v for k, v in pr.items() if k != "config"}
        out.append(entry)
    return out
