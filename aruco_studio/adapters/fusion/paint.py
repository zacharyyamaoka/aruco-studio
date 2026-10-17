"""Appearances: the black is black and the white is white (Zach, 2026-10-08).

What gets which colour is the recipe's `paint` (from the plan's colours).
This module only knows Fusion's appearance names and the measured rules for
WHEN to paint (REF `aruco_feature.paint`, `_update`):

| Quirk (Fusion 2705) | What this module does |
|---|---|
| `customFeatures.add()` resets its base-feature bodies to the default appearance | `paint_node` runs LAST in create(), after the node exists |
| `updateBody()` in compute drops the appearance | `repaint_source` paints the swapped source body inside the same startEdit / finishEdit (allowed in compute, and it sticks) |
| face-level appearance survives a join and the pieces a pocket cuts a tile into | a tile's and the pins' FACES are painted (a joined tile: faces only, so the user's body keeps its own colour) |
| a boolean result carries no colour of its own (20 of 36 IDs part bodies came back "Steel - Satin") | not handled in this skeleton: the IDs parts' repaint hook is Fusion-gated work (docs/FUSION_ADAPTER.md) |
"""
from __future__ import annotations

WHITE = "Plastic - Matte (White)"           # REF aruco_tags.WHITE
BLACK = "Plastic - Matte (Black)"           # REF aruco_tags.BLACK
NAMES = {"white": WHITE, "black": BLACK}


def appearance(des, colour):
    """The design's appearance for a plan colour ("white" / "black"), or None
    (REF also copies it in from the material library; Fusion-gated)."""
    name = NAMES.get(colour)
    if name is None:
        return None
    try:
        return des.appearances.itemByName(name)
    except Exception:                              # noqa: BLE001
        return None


def _put(ent, app, done, label):
    if app is None or ent is None:
        return
    try:
        cur = ent.appearance
        if cur is None or cur.name != app.name:
            ent.appearance = app
            done[label] = done.get(label, 0) + 1
    except Exception as exc:                       # noqa: BLE001
        done[label + " error"] = str(exc)[:120]


def paint_body(des, body, entry, done=None):
    """One part's body by its recipe paint entry. -> what was painted."""
    done = {} if done is None else done
    app = appearance(des, entry["colour"])
    if entry.get("body"):
        _put(body, app, done, entry["role"])
    if entry.get("faces"):
        for f in list(body.faces):
            _put(f, app, done, entry["role"] + " faces")
    return done


def paint_node(des, rec, bodies):
    """Every part the recipe paints. `bodies`: {role: the base body}. Idempotent."""
    done = {}
    for entry in rec["paint"]:
        b = bodies.get(entry["role"])
        if b is not None:
            paint_body(des, b, entry, done)
    return done


def repaint_source(des, bf, entry):
    """Inside a base feature's edit, after updateBody: its source body again."""
    try:
        src = list(bf.sourceBodies)[0]
    except Exception:                              # noqa: BLE001
        src = bf.bodies.item(0)
    return paint_body(des, src, entry)
