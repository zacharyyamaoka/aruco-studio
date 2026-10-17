"""The design file from the command line, no browser (an AI's loop):

    python -m aruco_studio check  <file> [<file> ...] [--strict]
    python -m aruco_studio render <file> [--svg out.svg]
    python -m aruco_studio plan   <file> [--json] [--out plans.json]

| Command | Does | Exit |
|---|---|---|
| `check` | parse and compile; print every Issue with its JSON path (`features[1].aruco`), a parse error as `file:line:col`; each tag that does not plan as a `warn` (an `error` with `--strict`) | 1 on an error, else 0 |
| `render` | the 2D top view of every tag (the canvas: side faces unfolded about their edge, hinge dashed), the shapes as outlines; each tag's `data-layer` paths are `/api/export/svg`'s, placed by a transform | 1 on a compile error |
| `plan` | every tag's TagPlan as JSON, `{tag name: plan}`: what `GET /api/scene?plans=1` gives | 1 on a compile error |

Presets are read as the server reads them (your presets under the Studio's
home, PrusaSlicer's "Aruco" print profiles: read only). Nothing is written
but the file you name with `--svg` / `--out`.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional


def _say(line: str) -> None:
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


def _load(path: str):
    """(doc, scene, issues, plans) or a parse error printed; None."""
    from .scene import DesignParseError, SceneFileError, design, loads_design
    from .server.design_api import resolver
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8-sig", errors="replace")
    except OSError as exc:
        _say(f"{path}: error: {exc}")
        return None
    try:
        doc = loads_design(text)
    except DesignParseError as exc:
        _say(f"{path}:{exc.line}:{exc.col}: error: {exc.msg}")
        return None
    except SceneFileError as exc:
        _say(f"{path}: error: {exc}")
        return None
    try:
        sc, issues = design.compile(doc, resolver())
    except design.DesignError as exc:
        _say(f"{path}: error: {exc}")
        return None
    return doc, sc, issues


def _feature_path(t) -> str:
    s = t.source or {}
    if s.get("feature") is None:
        return t.name
    return f"features[{s['feature']}]" + (f".aruco[{s['entry']}]" if s.get("entry") is not None
                                          else "")


def cmd_check(files: List[str], strict: bool = False) -> int:
    from .plan import plan_tag
    bad = 0
    for path in files:
        got = _load(path)
        if got is None:
            bad += 1
            continue
        _doc, sc, issues = got
        errs = warns = 0
        for i in issues:
            _say(f"{path}: {i.field}: {i.level}: {i.text}")
            errs += i.level == "error"
            warns += i.level == "warn"
        for t in sc.tags:
            p = plan_tag(t.spec)
            if not p.ok:
                lv = "error" if strict else "warn"
                _say(f"{path}: {_feature_path(t)}: {lv}: {t.name} not built: "
                     + "; ".join(p.data["errors"])[:300])
                errs += strict
                warns += not strict
        _say(f"{path}: {len(sc.tags)} tag(s), {errs} error(s), {warns} warning(s)")
        bad += errs > 0
    return 1 if bad else 0


def render_svg(doc, sc, plans=None, margin_mm: float = 5.0) -> str:
    """The canvas as SVG (mm, y up in the scene, down on paper)."""
    from .plan import exports as _X
    from .plan import plan_tag
    from .scene import design
    from .scene.model import mat_mul
    f = _X._f
    plans = plans or {t.name: plan_tag(t.spec) for t in sc.tags}
    shapes = design.shapes_2d(doc)
    groups, xs, ys = [], [], []
    for s in shapes:
        d = _X.path_d([s["loops"]])
        for lp in s["loops"]:
            for x, y in lp:
                xs.append(x)
                ys.append(y)
        groups.append(f'<path data-shape="{s["shape"] or ""}" data-path="{s["path"]}" '
                      f'fill="none" stroke="#7a7a7a" stroke-width="0.2" fill-rule="evenodd" '
                      f'd="{d}"/>')
    for t in sc.tags:
        p = plans[t.name]
        if t.hidden or not p.ok:
            continue
        M = mat_mul(t.pose, p.data["frames"]["pattern_in_target"])
        # path coords are (u, -v) of the pattern frame; screen = (x, -y) of the scene
        a, b, c, dd, e, ff = M[0], -M[4], -M[1], M[5], M[3], -M[7]
        r = _X.view_rect(p)
        for u, v in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])):
            xs.append(M[0] * u + M[1] * v + M[3])
            ys.append(M[4] * u + M[5] * v + M[7])
        body = "".join(_X.svg_paths(p))
        groups.append(f'<g data-tag="{t.name}" transform="matrix({f(a)} {f(b)} {f(c)} {f(dd)} '
                      f'{f(e)} {f(ff)})">{body}</g>')
    for t in sc.tags:
        h = (t.source or {}).get("hinge_xy")
        if h:
            (x0, y0), (x1, y1) = h
            groups.append(f'<line data-hinge="{t.name}" x1="{f(x0)}" y1="{f(-y0)}" '
                          f'x2="{f(x1)}" y2="{f(-y1)}" stroke="#3a86ff" stroke-width="0.3" '
                          f'stroke-dasharray="2 1"/>')
    if not xs:
        xs, ys = [0.0], [0.0]
    x0, y0 = min(xs) - margin_mm, min(ys) - margin_mm
    x1, y1 = max(xs) + margin_mm, max(ys) + margin_mm
    w, hh = x1 - x0, y1 - y0
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}mm" height="{f(hh)}mm" '
            f'viewBox="{f(x0)} {f(-y1)} {f(w)} {f(hh)}"><title>{sc.name}</title>'
            f'<rect x="{f(x0)}" y="{f(-y1)}" width="{f(w)}" height="{f(hh)}" fill="#ffffff"/>'
            + "".join(groups) + "</svg>")


def cmd_render(path: str, out: Optional[str]) -> int:
    got = _load(path)
    if got is None:
        return 1
    doc, sc, issues = got
    if any(i.level == "error" for i in issues):
        for i in issues:
            if i.level == "error":
                _say(f"{path}: {i.field}: error: {i.text}")
    svg = render_svg(doc, sc)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        _say(f"{out}: {len(sc.tags)} tag(s)")
    else:
        sys.stdout.write(svg + "\n")
    return 1 if any(i.level == "error" for i in issues) else 0


def plans_of(sc) -> dict:
    from .plan import plan_tag
    return {t.name: plan_tag(t.spec).to_dict() for t in sc.tags}


def cmd_plan(path: str, out: Optional[str]) -> int:
    got = _load(path)
    if got is None:
        return 1
    _doc, sc, issues = got
    text = json.dumps(plans_of(sc), sort_keys=True, allow_nan=False)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 1 if any(i.level == "error" for i in issues) else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aruco_studio",
                                 description="Check, render or plan a design file.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="compile; print every issue with its path")
    c.add_argument("files", nargs="+")
    c.add_argument("--strict", action="store_true", help="a tag that does not plan is an error")
    r = sub.add_parser("render", help="the 2D top view as SVG")
    r.add_argument("file")
    r.add_argument("--svg", default=None, help="write the SVG here (else stdout)")
    p = sub.add_parser("plan", help="every tag's TagPlan as JSON")
    p.add_argument("file")
    p.add_argument("--json", action="store_true", help="JSON (the only format)")
    p.add_argument("--out", default=None, help="write here (else stdout)")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return cmd_check(a.files, a.strict)
    if a.cmd == "render":
        return cmd_render(a.file, a.svg)
    return cmd_plan(a.file, a.out)


if __name__ == "__main__":
    sys.exit(main())
