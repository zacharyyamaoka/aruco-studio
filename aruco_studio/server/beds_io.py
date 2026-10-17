"""REF print_beds' file I/O (cad-exporter c8216ff), outside the core (audit C7).

The core never opens a file (tests/core/test_purity.py). These are REF's
functions that read PrusaSlicer's own folder (its PrusaSlicer.ini, the
user's preset files, the vendor bundle) or write beds, STLs and projects;
each body is REF's text verbatim (tests/core/test_port_fidelity.py), with
the pure part of print_beds (`aruco_studio.core.beds`) in this module's
namespace, so REF's suites run on this module as they ran on print_beds.

| Function | Reads / writes |
|---|---|
| `prusaslicer_datadir`, `find_vendor_bundle`, `find_prusaslicer_gui` | looks for PrusaSlicer's folders and program |
| `last_selected_presets`, `_resolve_any`, `load_selected_profile` | PrusaSlicer.ini and the user's preset files (read only) |
| `manifest_reader`, `_project_setup` | a parts manifest and its STLs, a profile bundle |
| `write_files`, `write_beds`, `write_part_stls`, `write_selection_project` | the beds, parts and projects |
"""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Callable, Dict, List, Optional, Sequence

from ..core import beds as _core

# the pure part of print_beds, as REF's module had it in one namespace
globals().update({k: v for k, v in vars(_core).items()
                  if not (k.startswith("__") and k.endswith("__"))})


def prusaslicer_datadir() -> Optional[str]:
    """PrusaSlicer's data directory on this machine (PrusaSlicer.ini, the
    user's own presets, the vendor bundles), or None."""
    home = os.path.expanduser("~")
    cands = []
    if os.environ.get("APPDATA"):
        cands.append(os.path.join(os.environ["APPDATA"], "PrusaSlicer"))
    cands += [os.path.join(home, "Library", "Application Support", "PrusaSlicer"),
              os.path.join(home, ".config", "PrusaSlicer"), os.path.join(home, ".PrusaSlicer")]
    for c in cands:
        if os.path.isfile(os.path.join(c, "PrusaSlicer.ini")):
            return c
    return None


def last_selected_presets(datadir: Optional[str] = None) -> Optional[dict]:
    """The presets PrusaSlicer had selected when it last closed ([presets]
    in PrusaSlicer.ini): {"printer", "print", "filaments": [slot 1, slot 2,
    ...], "physical_printer"}; None when there is no such file or no printer."""
    datadir = datadir or prusaslicer_datadir()
    if not datadir:
        return None
    try:
        with open(os.path.join(datadir, "PrusaSlicer.ini"), "r", encoding="utf-8") as f:
            p = parse_ini_sections(f.read()).get("presets") or {}
    except OSError:
        return None
    if not p.get("printer"):
        return None
    fil = [p.get("filament", "")]
    k = 1
    while "filament_%d" % k in p:
        fil.append(p["filament_%d" % k])
        k += 1
    return {"printer": p["printer"], "print": p.get("print", ""), "filaments": fil,
            "physical_printer": p.get("physical_printer", ""), "datadir": datadir}


def _resolve_any(secs: Dict[str, Dict[str, str]], datadir: Optional[str], kind: str,
                 name: str) -> Dict[str, str]:
    """A preset by name, the way PrusaSlicer has it: the user's own file
    (<datadir>/<kind>/<name>.ini) over its `inherits` chain from the vendor
    bundle, else the vendor bundle's preset."""
    if datadir:
        path = os.path.join(datadir, kind, name + ".ini")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                own = _flat_ini(f.read())
            out: Dict[str, str] = {}
            for parent in [x.strip().strip('"') for x in own.get("inherits", "").split(";")
                           if x.strip()]:
                out.update(resolve_preset(secs, kind, parent))
            out.update(own)
            return out
    return resolve_preset(secs, kind, name)


def load_selected_profile(bundle_text: str, selected: dict, source: str = "") -> PrusaProfile:
    """PrusaSlicer's last selection (last_selected_presets) as a profile to
    MIRROR: every key as PrusaSlicer has it, so a project carrying it changes
    nothing when it is opened. A slot holding a project's temporary preset
    takes the first real one. Raises ValueError naming what is missing."""
    secs = parse_ini_sections(bundle_text)
    vendor = secs.get("vendor", {})
    datadir = selected.get("datadir")
    real = [f for f in selected.get("filaments") or () if not _temporary(f)]
    if not real:
        raise ValueError("PrusaSlicer has no filament preset selected")
    for kind in ("printer", "print"):
        if _temporary(selected.get(kind, "")):
            raise ValueError("PrusaSlicer's %s preset is a project's temporary one (%r)"
                             % (kind, selected.get(kind)))
    names = [f if not _temporary(f) else real[0] for f in selected["filaments"]]
    values: Dict[str, str] = {}
    for kind, name in (("printer", selected["printer"]), ("print", selected["print"]),
                       ("filament", real[0])):
        for k, v in _resolve_any(secs, datadir, kind, name).items():
            if k not in _META_KEYS:
                values[k] = v
    phys = (selected.get("physical_printer") or "").split(" * ")[0].strip()
    return PrusaProfile(selected["printer"], selected["print"], real[0],
                        "%s %s" % (vendor.get("name", "?"), vendor.get("config_version", "?")),
                        values, source, filaments=names, physical_printer=phys, mirrored=True)


def find_vendor_bundle(vendor: str = "PrusaResearch") -> Optional[str]:
    """The vendor bundle PrusaSlicer itself uses on this machine: the data
    directory's (kept current by its updater) before the installed copy."""
    home = os.path.expanduser("~")
    cands = []
    if os.environ.get("APPDATA"):
        cands.append(os.path.join(os.environ["APPDATA"], "PrusaSlicer", "vendor", vendor + ".ini"))
    cands += [os.path.join(home, "Library", "Application Support", "PrusaSlicer", "vendor",
                           vendor + ".ini"),
              os.path.join(home, ".config", "PrusaSlicer", "vendor", vendor + ".ini"),
              os.path.join(home, ".PrusaSlicer", "vendor", vendor + ".ini")]
    for pf in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles")):
        if pf:
            cands.append(os.path.join(pf, "Prusa3D", "PrusaSlicer", "resources", "profiles",
                                      vendor + ".ini"))
    cands.append(os.path.join("/Applications", "PrusaSlicer.app", "Contents", "Resources",
                              "profiles", vendor + ".ini"))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def manifest_reader(manifest_path: str) -> Callable[[str], bytes]:
    """Read a manifest's `stl` strings: they are relative to the export root
    (aruco/print3d/x.stl), so try the manifest's folder and its parents,
    then the bare file name beside the manifest."""
    here = os.path.dirname(os.path.abspath(manifest_path))

    def read(rel: str) -> bytes:
        rel_os = os.path.join(*[p for p in re.split(r"[\\/]+", rel) if p]) if rel else ""
        tried = []
        base = here
        for _ in range(4):
            cand = os.path.join(base, rel_os)
            tried.append(cand)
            if rel_os and os.path.isfile(cand):
                with open(cand, "rb") as f:
                    return f.read()
            base = os.path.dirname(base)
        cand = os.path.join(here, os.path.basename(rel_os))
        tried.append(cand)
        if rel_os and os.path.isfile(cand):
            with open(cand, "rb") as f:
                return f.read()
        raise OSError("not found; tried %s" % ", ".join(tried))
    return read


def write_files(out_dir: str, files: Dict[str, bytes], clean: bool = True) -> List[str]:
    """Write {relpath: bytes} under out_dir; with `clean`, remove earlier
    files of OUR naming (aruco_tags*.3mf, beds/bed_NN.*, parts/...) that
    this run did not write, so a bed that no longer exists cannot be
    printed by mistake."""
    written = []
    for rel in sorted(files):
        path = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(files[rel])
        written.append(path)
    if clean:
        for sub in ("", "beds", "parts"):
            folder = os.path.join(out_dir, sub) if sub else out_dir
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                rel = "%s/%s" % (sub, name) if sub else name
                if (rel not in files and any(p.match(rel) for p in _OWN_FILES)
                        and os.path.isfile(os.path.join(folder, name))):
                    os.remove(os.path.join(folder, name))
    return written


def find_prusaslicer_gui() -> Optional[str]:
    """The PrusaSlicer GUI executable on this machine, or None -- for an
    add-in that opens a written project (`[exe, path]`)."""
    cands = []
    for env in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(env):
            cands.append(os.path.join(os.environ[env], "Prusa3D", "PrusaSlicer", "prusa-slicer.exe"))
    cands.append("/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer")
    for name in ("prusa-slicer", "PrusaSlicer"):
        found = shutil.which(name)
        if found:
            cands.append(found)
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def _project_setup(bed_w_mm, bed_d_mm, margin_mm, spacing_mm, options: dict):
    """Shared by write_beds / write_selection_project: pops the preset
    options, resolves the PrusaSlicer profile, settles the bed. ->
    (settings, profile, (tile_colour, cells_colour), warnings); the rest of
    `options` become BedSettings fields."""
    bundle = options.pop("vendor_bundle", "auto")
    printer = options.pop("printer_preset", DEFAULT_PRINTER)
    print_ = options.pop("print_preset", DEFAULT_PRINT)
    filament = options.pop("filament_preset", DEFAULT_FILAMENT)
    # "vendor": the named system presets (above); "slicer": a COPY of what
    # PrusaSlicer itself had selected last (nothing of ours is set)
    presets = options.pop("presets", "vendor")
    colours = (options.pop("tile_colour", TILE_COLOUR), options.pop("cells_colour", CELLS_COLOUR))
    warn: List[str] = []
    profile: Optional[PrusaProfile] = None
    if bundle and presets == "slicer":
        selected = last_selected_presets()
        path = find_vendor_bundle() if bundle == "auto" else bundle
        if selected is None or path is None:
            warn.append("PrusaSlicer's last-used presets were not found, so the files carry no "
                        "project config: PrusaSlicer keeps whatever it has selected, and each "
                        "bed is its own file (no all-beds project)")
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profile = load_selected_profile(f.read(), selected, path)
            except (OSError, ValueError) as exc:
                warn.append("PrusaSlicer's last-used presets could not be read (%s), so the "
                            "files carry no project config and each bed is its own file" % exc)
            if profile is not None and len(set(profile.filaments)) > 1:
                warn.append("PrusaSlicer's filament slots hold different presets (%s); the "
                            "project carries %s's settings for every slot, so PrusaSlicer may "
                            "show the others as modified"
                            % (", ".join(profile.filaments), profile.filament))
    elif bundle:
        path = find_vendor_bundle() if bundle == "auto" else bundle
        if path is None:
            warn.append("no PrusaSlicer vendor bundle found on this machine, so the files carry "
                        "no project config (PrusaSlicer keeps its current presets) and no "
                        "multi-bed project is written")
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profile = load_prusa_profile(f.read(), printer, print_, filament, path)
            except (OSError, ValueError) as exc:
                warn.append("PrusaSlicer presets unavailable (%s), so the files carry no project "
                            "config and no multi-bed project is written" % exc)
    if bed_w_mm is None or bed_d_mm is None:
        pw, pd = profile.bed_mm if profile is not None else MK4_BED_MM
        bed_w_mm = pw if bed_w_mm is None else bed_w_mm
        bed_d_mm = pd if bed_d_mm is None else bed_d_mm
    if profile is not None:
        if "bed_h_mm" not in options and profile.max_height_mm:
            options["bed_h_mm"] = profile.max_height_mm
        pw, pd = profile.bed_mm
        if abs(pw - float(bed_w_mm)) > 1e-6 or abs(pd - float(bed_d_mm)) > 1e-6:
            if profile.mirrored:
                warn.append("the beds are laid out %s x %s mm but PrusaSlicer's printer %s has "
                            "%s x %s mm; its bed is kept, so check the beds in PrusaSlicer"
                            % (_f(float(bed_w_mm)), _f(float(bed_d_mm)), profile.printer,
                               _f(pw), _f(pd)))
            else:
                warn.append("the bed %s x %s mm differs from %s's %s x %s mm; the project uses "
                            "%s x %s (its bed_shape is overridden)"
                            % (_f(float(bed_w_mm)), _f(float(bed_d_mm)), profile.printer,
                               _f(pw), _f(pd), _f(float(bed_w_mm)), _f(float(bed_d_mm))))
        for what, slot in (("black", options.get("cells_extruder", 2)),
                           ("white", options.get("tile_extruder", 1))):
            if profile.extruders < int(slot):
                warn.append("%s has %d extruder(s); the %s is on filament %d, so PrusaSlicer "
                            "prints it in filament 1" % (profile.printer, profile.extruders,
                                                         what, int(slot)))
    settings = BedSettings(bed_w_mm=float(bed_w_mm), bed_d_mm=float(bed_d_mm),
                           margin_mm=float(margin_mm), spacing_mm=float(spacing_mm), **options)
    settings.check()
    return settings, profile, colours, warn


def write_beds(manifest_path: str, out_dir: Optional[str] = None,
               bed_w_mm: Optional[float] = None, bed_d_mm: Optional[float] = None,
               margin_mm: float = 5.0, spacing_mm: float = 5.0,
               include: Optional[Sequence[str]] = None,
               copies_override: Optional[Dict[str, int]] = None,
               orientation: str = "flat", instances: bool = False, **options) -> dict:
    """Lay out the parts in `manifest_path` (parts.json) and write
    aruco_tags.3mf, beds/ and parts/ under `out_dir` (default: the
    manifest's folder).

    bed_w_mm/_d_mm   default: the printer preset's bed (MK4: 250 x 210);
                     a bed passed here wins and goes into the bed_shape
    include          component names to print (None = all); the others are
                     listed under "skipped"
    copies_override  {component: copies} instead of the manifest's counts
    orientation      "flat" (laid down by the tag, the module rule) or
                     "cad" (as modelled: dropped to z = 0, never turned)
    instances        False: every copy its own object "<part> (2/6)";
                     True: copies on a bed are instances of one object

    options: printer_preset / print_preset / filament_preset (PrusaSlicer
    system preset names; default MK4 MMU3 0.4, 0.20mm STRUCTURAL, Generic
    PLA), vendor_bundle ("auto" = the one PrusaSlicer uses here; a path; or
    None for no project config), tile_colour / cells_colour, bed_h_mm,
    allow_rotate, centre, wipe_tower_mm (None = no tower hole),
    tile_extruder, cells_extruder, clean (default True).
    -> a JSON-able summary: files, beds, utilisation, rejected, skipped,
    warnings, prusaslicer_exe."""
    clean = options.pop("clean", True)
    options.update(orientation=orientation, instances=bool(instances))
    settings, profile, colours, pre_warn = _project_setup(bed_w_mm, bed_d_mm, margin_mm,
                                                          spacing_mm, options)
    with open(manifest_path, "rb") as f:
        manifest = json.loads(f.read().decode("utf-8"))
    out_dir = out_dir or os.path.dirname(os.path.abspath(manifest_path))
    layout = layout_beds(manifest, manifest_reader(manifest_path), settings,
                         include, copies_override)
    layout.warnings[:0] = pre_warn
    files = render_beds(layout, profile, *colours)
    write_files(out_dir, files, clean=clean)
    summary = layout_summary(layout, profile)

    def full(rel):
        return os.path.join(out_dir, *rel.split("/"))
    return {
        "out_dir": out_dir,
        "project": [full(r) for r in summary["project"]["files"] if r in files],
        "beds": layout.bed_count,
        "bed_files": [full(bed_file(b)) for b in range(layout.bed_count)],
        "previews": [full(bed_file(b, "svg")) for b in range(layout.bed_count)],
        "layout": full("beds/layout.json"),
        "parts_dir": full("parts"),
        "bed_mm": [settings.bed_w_mm, settings.bed_d_mm],
        "presets": summary["project"]["presets"],
        "placed": len(layout.placed),
        "copies_requested": summary["totals"]["copies_requested"],
        "utilisation": [b["utilisation"] for b in summary["beds"]],
        "orientation": {op.part.name: op.orientation.rule for op in layout.parts},
        "rejected": summary["rejected"],
        "skipped": summary["skipped"],
        "warnings": summary["warnings"],
        "prusaslicer_exe": find_prusaslicer_gui(),
    }


def write_part_stls(manifest_path: str, out_dir: Optional[str] = None,
                    include: Optional[Sequence[str]] = None, orientation: str = "flat",
                    clean: bool = True) -> dict:
    """ArUco Export's "STL files" type: every chosen part's bodies as loose
    STLs, oriented for printing -- no beds, no 3MF, no copies.

    Writes <out_dir>/<part>__<role>[_n].stl (the names write_beds uses
    under parts/): millimetres, the part resting on z = 0 and centred on the
    origin, laid down by its tag (orientation="flat", the module rule) or
    kept as modelled ("cad"). With `clean`, earlier STLs of that naming in
    out_dir that this run did not write are removed.
    -> {"out_dir", "files" (absolute), "orientation" {part: rule},
    "rejected", "skipped", "warnings"}."""
    if orientation not in ("flat", "cad"):
        raise ValueError("orientation must be 'flat' or 'cad', not %r" % (orientation,))
    with open(manifest_path, "rb") as f:
        manifest = json.loads(f.read().decode("utf-8"))
    out_dir = out_dir or os.path.dirname(os.path.abspath(manifest_path))
    chosen, skipped, warnings = select_parts(manifest, include)
    parts, failures, load_warn = load_parts(chosen, manifest_reader(manifest_path))
    warnings = list(warnings) + list(load_warn)
    rejected = list(failures)
    files: Dict[str, bytes] = {}
    rules: Dict[str, str] = {}
    for part in parts:
        try:
            op = orient_part(part, cad_orientation([b.mesh for b in part.bodies])
                             if orientation == "cad" else None)
        except ValueError as exc:
            rejected.append((part.name, "cannot be oriented: %s" % exc))
            continue
        if op.orientation.warning:
            warnings.append("%s: %s orientation (%s) -- %s" % (
                part.name, op.orientation.rule, op.orientation.reason, op.orientation.warning))
        rules[part.name] = op.orientation.rule
        names = part_files(op)
        for body, mesh in zip(op.part.bodies, op.meshes):
            files[names[body.name].split("/", 1)[1]] = write_stl(
                mesh, "%s %s" % (op.part.slug, body.role))
    for name, reason in rejected:
        warnings.append("NOT WRITTEN: %s -- %s" % (name, reason))
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for rel in sorted(files):
        path = os.path.join(out_dir, rel)
        with open(path, "wb") as f:
            f.write(files[rel])
        written.append(path)
    if clean:
        for name in sorted(os.listdir(out_dir)):
            path = os.path.join(out_dir, name)
            if name not in files and _OWN_STLS.match(name) and os.path.isfile(path):
                os.remove(path)
    return {"out_dir": out_dir, "files": written, "orientation": rules,
            "rejected": [{"part": n, "reason": r} for n, r in rejected],
            "skipped": [{"part": n, "reason": r} for n, r in skipped],
            "warnings": warnings}


def write_selection_project(objects: Sequence[dict], out_path: str,
                            bed_w_mm: Optional[float] = None, bed_d_mm: Optional[float] = None,
                            orientation: str = "cad", **options) -> dict:
    """The "print it integral" path: arbitrary Fusion bodies -> one
    PrusaSlicer project with the black already on extruder 2.

    objects: [{"name": str,
               "bodies": [{"stl": path, "role": "cells" | "tile" | "other",
                           "name": str}, ...],
               "frame": optional tag record (as in parts.json "tags": key,
                        origin, x_axis, y_axis, z_axis, units, spec), used
                        by orientation="flat",
               "copies": optional int (default 1)}]

    Each object becomes ONE PrusaSlicer object whose volumes are its bodies:
    a body with role "cells" or named "aruco cells ..." prints in the black
    filament (extruder 2), every other body in extruder 1. The STLs may
    share one (assembly) coordinate system: each object is kept as modelled
    (orientation="cad", the default: no rotation), dropped to z = 0 and
    packed onto as many beds as needed; "flat" lays it down by its frame.
    Writes `out_path` (out_path's stem + "_2.3mf" ... past 9 beds) with the
    same embedded preset config and white / black colours as
    aruco_tags.3mf. Without PrusaSlicer presets on this machine one bed is
    still written to out_path (no config: PrusaSlicer keeps its presets and
    re-centres it); several beds then go one per file, "<stem>_bed_NN.3mf".

    options: margin_mm, spacing_mm, stl_units (default "mm"), frame_units
    (default "cm"), design, instances, and write_beds' preset / colour /
    tower options.
    -> summary: files, beds, objects, placed, skipped, rejected, warnings,
    prusaslicer_exe, layout (the layout.json dict)."""
    margin = options.pop("margin_mm", 5.0)
    spacing = options.pop("spacing_mm", 5.0)
    stl_units = options.pop("stl_units", "mm")
    frame_units = options.pop("frame_units", "cm")
    design = options.pop("design", os.path.splitext(os.path.basename(out_path))[0])
    options["orientation"] = orientation
    settings, profile, colours, pre_warn = _project_setup(bed_w_mm, bed_d_mm, margin, spacing,
                                                          options)
    manifest = {"schema": MANIFEST_SCHEMA, "stl_units": stl_units, "frame_units": frame_units,
                "design": design, "parts": []}
    for i, o in enumerate(objects):
        frame = o.get("frame")
        manifest["parts"].append({
            "component": str(o.get("name") or "object %d" % (i + 1)),
            "copies": o.get("copies", 1),
            "bodies": [{"name": str(b.get("name") or "body %d" % (j + 1)),
                        "role": b.get("role", "other"), "stl": str(b["stl"])}
                       for j, b in enumerate(o.get("bodies", []))],
            "tags": [frame] if frame else []})

    def read(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()
    layout = layout_beds(manifest, read, settings)
    layout.warnings[:0] = pre_warn
    out_path = os.path.abspath(out_path)
    stem, ext = os.path.splitext(out_path)
    ext = ext or ".3mf"

    def name(g: int) -> str:
        return stem + ext if g == 0 else "%s_%d%s" % (stem, g + 1, ext)
    if profile is not None:
        files = render_projects(layout, project_config_text(profile, settings, *colours), name)
    elif layout.bed_count <= 1:
        t = tower_position(layout, 0) if layout.bed_count else None
        files = {name(0): render_3mf(objects_for_beds(layout, range(layout.bed_count)), design,
                                     None if t is None else [(0, t[0], t[1])])}
    else:
        files = {}
        for b in range(layout.bed_count):
            t = tower_position(layout, b)
            files["%s_bed_%02d%s" % (stem, b + 1, ext)] = render_3mf(
                objects_for_beds(layout, [b]), "%s bed %d" % (design, b + 1),
                None if t is None else [(0, t[0], t[1])])
        layout.warnings.append("no project config, so the %d beds are separate files"
                               % layout.bed_count)
    for path in sorted(files):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(files[path])
    summary = layout_summary(layout, profile, lambda g: os.path.basename(name(g)))
    return {
        "files": sorted(files),
        "beds": layout.bed_count,
        "bed_mm": [settings.bed_w_mm, settings.bed_d_mm],
        "presets": summary["project"]["presets"],
        "placed": len(layout.placed),
        "objects": [copy_name(layout.parts[p.part], p.copy) for p in layout.placed],
        "orientation": {op.part.name: op.orientation.rule for op in layout.parts},
        "rejected": summary["rejected"],
        "skipped": summary["skipped"],
        "warnings": summary["warnings"],
        "prusaslicer_exe": find_prusaslicer_gui(),
        "layout": summary,
    }
