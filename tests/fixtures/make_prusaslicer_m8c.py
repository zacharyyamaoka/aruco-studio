"""Make tests/fixtures/prusaslicer_m8c/: a PrusaSlicer config folder for the
M8c tests (physical printers, printer presets, the fitting prints, the
selected pair, the headless slice).

    .venv/Scripts/python tests/fixtures/make_prusaslicer_m8c.py [<PrusaSlicer folder>]

READS PrusaSlicer's folder (default %APPDATA%/PrusaSlicer) and never writes
there. What it writes, under tests/fixtures/prusaslicer_m8c/:

| File | How |
|---|---|
| `physical_printer/<name>.ini` | TYPED: the allow-listed keys (core.prusa.PHYSICAL_KEYS) of each physical printer, and every host key as a placeholder (`print_host = <host>`). No host, key or password is ever read: the source is read through the allow-list |
| `printer/<name>.ini` | the user's printer presets, line for line, every private key (core.prusa.private_key) replaced by a placeholder |
| `print/<name>.ini` | the user's print presets, verbatim (they hold no private key; checked) |
| `vendor/PrusaResearch.ini` | the sections those presets inherit from (printer, print, filament chains, the printer models, [vendor]), verbatim, private keys dropped |
| `PrusaSlicer.ini` | TYPED: its [presets] and [vendor:...] sections only |
| `provenance.json` | this table, the date, and the sha256 of every file |

Not a golden (goldens/ is REF's numbers only, tests/core/test_golden_provenance.py):
a fixture of the M8c lane, made once on 2026-10-16.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aruco_studio.core import prusa as PR  # noqa: E402

OUT = Path(__file__).resolve().parent / "prusaslicer_m8c"
HOST_PLACEHOLDERS = {"print_host": "<host>", "printhost_apikey": "<apikey>",
                     "printhost_authorization_type": "key", "printhost_cafile": "",
                     "printhost_password": "<password>", "printhost_port": "",
                     "printhost_ssl_ignore_revoke": "0", "printhost_user": "<user>"}


def placeholder(key):
    return HOST_PLACEHOLDERS.get(key, "<private>")


def _quote(v):
    return '"%s"' % v


def physical_text(parsed):
    rows = dict(HOST_PLACEHOLDERS)
    rows["preset_names"] = ";".join(_quote(n) for n in parsed.get("preset_names") or [])
    for k in ("preset_name", "printer_technology", "host_type"):
        if parsed.get(k):
            rows[k] = parsed[k]
    head = "# ArUco Studio fixture (M8c): typed from the allow-listed keys; every host key a placeholder\n"
    return head + "".join(f"{k} = {rows[k]}\n" for k in sorted(rows))


def scrub(text):
    """A preset file line for line, each private key's value a placeholder."""
    out = []
    for line in text.splitlines():
        k, sep, _v = line.partition("=")
        if sep and PR.private_key(k.strip()):
            out.append(f"{k.strip()} = {placeholder(k.strip())}")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def sections(text):
    """[(head, [raw lines])] of a bundle, in order (head None: the preamble)."""
    out, cur = [], (None, [])
    for line in text.splitlines():
        m = re.match(r"^\[(.+)\]\s*$", line)
        if m:
            out.append(cur)
            cur = (m.group(1), [line])
            continue
        cur[1].append(line)
    out.append(cur)
    return out


def kv(lines):
    d = {}
    for line in lines[1:]:
        s = line.strip()
        if s and s[0] not in "#;" and "=" in s:
            k, v = s.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def main(argv):
    src = Path(argv[1]) if len(argv) > 1 else Path(os.environ["APPDATA"]) / "PrusaSlicer"
    files = {}
    phys = {}
    for f in sorted((src / "physical_printer").glob("*.ini")):
        # the allow-list: no private value reaches this process's data
        with open(f, encoding="utf-8", errors="replace") as fh:
            keep = "".join(line for line in fh
                           if line.split("=", 1)[0].strip() in PR.PHYSICAL_KEYS)
        phys[f.stem] = PR.parse_physical(keep)
        files[f"physical_printer/{f.name}"] = physical_text(phys[f.stem])
    users_printer = {}
    for f in sorted((src / "printer").glob("*.ini")):
        t = scrub(f.read_text(encoding="utf-8", errors="replace"))
        users_printer[f.stem] = PR.parse_private_free(t)
        files[f"printer/{f.name}"] = t
    users_print = {}
    for f in sorted((src / "print").glob("*.ini")):
        t = f.read_text(encoding="utf-8", errors="replace")
        assert not any(PR.private_key(k) for k, _v in PR._kv_lines(t)), f.name
        users_print[f.stem] = PR.parse_ini(t)
        files[f"print/{f.name}"] = t if t.endswith("\n") else t + "\n"
    ini = (src / "PrusaSlicer.ini").read_text(encoding="utf-8", errors="replace")
    sel = PR._ini_sections(ini, ("presets",)).get("presets") or {}
    vend = PR._ini_sections(ini, ("vendor:",))
    lines = ["# ArUco Studio fixture (M8c): typed; [presets] and [vendor:...] only", "",
             "[presets]"] + [f"{k} = {sel[k]}" for k in sorted(sel)] + [""]
    for head in sorted(vend):
        lines += [f"[{head}]"] + [f"{k} = {v}" for k, v in sorted(vend[head].items())] + [""]
    files["PrusaSlicer.ini"] = "\n".join(lines) + "\n"

    btext = (src / "vendor" / "PrusaResearch.ini").read_text(encoding="utf-8")
    secs = sections(btext)
    by = {h: ls for h, ls in secs if h}
    need = []

    def want(kind, name):
        key = f"{kind}:{name}"
        if key in need or key not in by:
            return
        need.append(key)
        for p in PR.split_names(kv(by[key]).get("inherits", "")):
            want(kind, p)
    printers = set()
    for ph in phys.values():
        printers |= set(ph.get("preset_names") or [])
    for nm, cfg in users_printer.items():
        for p in PR.split_names(cfg.get("inherits", "")):
            printers.add(p)
    printers -= set(users_printer)
    for p in sorted(printers):
        want("printer", p)
    defaults_print, defaults_fil = set(), set()
    for key in list(need):
        d = kv(by[key])
        if d.get("default_print_profile"):
            defaults_print.add(d["default_print_profile"].strip('"'))
        defaults_fil |= set(PR.split_names(d.get("default_filament_profile", "")))
    for cfg in users_printer.values():
        if cfg.get("default_print_profile"):
            defaults_print.add(cfg["default_print_profile"].strip('"'))
        defaults_fil |= set(PR.split_names(cfg.get("default_filament_profile", "")))
    prints = set(defaults_print) | {sel.get("print", "")}
    for cfg in users_print.values():
        prints |= set(PR.split_names(cfg.get("inherits", "")))
    for p in sorted(x for x in prints if x):
        want("print", p)
    fils = set(defaults_fil) | {v for k, v in sel.items() if k.startswith("filament")}
    for p in sorted(x for x in fils if x):
        want("filament", p)
    models = set()
    for key in need:
        if key.startswith("printer:"):
            m = kv(by[key]).get("printer_model")
            if m:
                models.add(m)
    for cfg in users_printer.values():
        if cfg.get("printer_model"):
            models.add(cfg["printer_model"])
    for m in sorted(models):
        if f"printer_model:{m}" in by:
            need.append(f"printer_model:{m}")
    keep = set(need) | {"vendor"}
    out = ["# ArUco Studio fixture (M8c): the sections of PrusaSlicer 2.9.6's PrusaResearch.ini"
           " (Zach's box, 2026-10-16) that the fixture's presets inherit from, verbatim"]
    dropped = 0
    for h, ls in secs:
        if h in keep:
            for line in ls:
                k, sep, _v = line.partition("=")
                if sep and PR.private_key(k.strip()):
                    dropped += 1
                    continue
                out.append(line)
    files["vendor/PrusaResearch.ini"] = "\n".join(out).rstrip("\n") + "\n"

    OUT.mkdir(parents=True, exist_ok=True)
    for rel, text in sorted(files.items()):
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    prov = {"schema": "arucostudio.fixture/1", "name": "prusaslicer_m8c",
            "made_by": "tests/fixtures/make_prusaslicer_m8c.py",
            "from": "PrusaSlicer 2.9.6's config folder on Zach's box, read only",
            "date": datetime.date.today().isoformat(),
            "placeholders": "every host key is a placeholder (print_host = <host>, "
                            "printhost_apikey = <apikey>, ...): no host, key or password",
            "vendor_sections": len(keep), "private_lines_dropped_from_vendor": dropped,
            "sha256": {rel: hashlib.sha256((OUT / rel).read_bytes()).hexdigest()
                       for rel in sorted(files)}}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} files to {OUT} ({len(keep)} vendor sections)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
