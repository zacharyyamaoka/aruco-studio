# 0002 — Actual size is an estimate first, calibrated per screen

Date: 2026-10-21 · Status: accepted · Merged: lane/os-actualsize

## Context
Zach (2026-10-21): "when actual size it should determine my screen resolution etc and correctly
display it so I can see the things to scale." Browsers do not expose a screen's physical size; CSS
px are nominally 96/in, which is ~31 % off on his 4K monitor (140 px/in).

## Decision
Actual size starts from an estimate (devicePixelRatio, screen size, typical panel densities) and is
labelled "Actual size (estimated — calibrate)" until calibrated with a credit card (ISO/IEC 7810
ID-1, 85.60 × 53.98 mm) or a typed ruler length. A calibration is stored per screen key
(width × height @ DPR) and never scaled across DPR: a 27" 1440p at ×1 and a 27" 5K at ×2 report the
same CSS screen size, so scaling across DPR would be 2× wrong. Code: `web/src/zoom/`.

## Consequences
- A new monitor shows the estimate until calibrated there.
- Safari page zoom may not change DPR, so a stored calibration can drift after one (not handled).
