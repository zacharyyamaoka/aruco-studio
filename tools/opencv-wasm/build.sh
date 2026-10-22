#!/usr/bin/env bash
# The browser's OpenCV 5.0: opencv-python 5.0.0.93 built as a Pyodide 314.0.7
# wheel (cp314-cp314-pyemscripten_2026_0_wasm32) from the PyPI sdist, then
# copied to web/public/opencv/, where the online Studio serves it and its
# core's worker loads it (web/src/core/opencv.ts lists it).
#
#   bash tools/opencv-wasm/build.sh
#
# WHY (2026-10-21, docs/peps/0003 decision 3): Zach's "by default it should be
# the most recent one" -- and no Pyodide ships OpenCV 5 (314.0.7 ships 4.11,
# the 315 alphas none; PyPI has no wasm wheel; pyodide-recipes pins 4.11), so
# this builds one: the pyodide-recipes 4.11 recipe retargeted to the 5.0 sdist
# and cut to the modules the core calls (recipes/opencv-python/meta.yaml says
# what changed). Measured then: the wheel 4.5 MB (4.11's: 10.7 MB), and its
# reading ranges byte-identical to CPython's OpenCV 5.0 (requirements.txt).
#
# Needs uv and cmake; it fetches pyodide-build, Pyodide 314.0.7's cross-build
# env and emscripten 5.0.3 (~2 GB) into $ARUCO_CVWASM_DIR (default
# ~/.cache/aruco-studio/opencv-wasm), outside the repo. ~4 min on 16 cores.
# A Pyodide upgrade changes the ABI: bump PYODIDE_VERSION to the lock's
# (web/node_modules/pyodide/pyodide-lock.json) and rebuild; web/src/core/
# opencv.test.ts fails until the served wheel's tag matches the lock.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RECIPES="$REPO/tools/opencv-wasm/recipes"
WORK="${ARUCO_CVWASM_DIR:-$HOME/.cache/aruco-studio/opencv-wasm}"
JOBS="${JOBS:-16}"
PYODIDE_VERSION=314.0.7
PYODIDE_BUILD_VERSION=0.39.1
WHEEL=opencv_python-5.0.0.93-cp314-cp314-pyemscripten_2026_0_wasm32.whl

mkdir -p "$WORK/logs" "$WORK/recipes"
cd "$WORK"

# 1. the build tool
if [ ! -x .venv/bin/pyodide ]; then
  uv venv --python 3.14 .venv
  uv pip install --python .venv/bin/python "pyodide-build==${PYODIDE_BUILD_VERSION}"
fi
export PATH="$WORK/.venv/bin:$PATH"

# 2. the cross-build env (Python 3.14.2, emscripten 5.0.3, ABI 2026_0) and emscripten itself
export PYODIDE_XBUILDENV_PATH="$WORK/xbuildenv"
if [ ! -e "xbuildenv/${PYODIDE_VERSION}/.installed" ]; then
  pyodide xbuildenv install "${PYODIDE_VERSION}" --path "$PYODIDE_XBUILDENV_PATH"
fi
pyodide xbuildenv install-emscripten --path "$PYODIDE_XBUILDENV_PATH"
abi="$(pyodide config get pyodide_abi_version)"
[ "$abi" = "2026_0" ] || { echo "the cross-build env's ABI is $abi, not 2026_0" >&2; exit 1; }

# 3. the recipe (a copy: pyodide-build writes its build tree beside it), sdist -> cmake/emcc -> wheel
rm -rf "$WORK/recipes/opencv-python"
cp -r "$RECIPES/opencv-python" "$WORK/recipes/"
export MAKEFLAGS="-j${JOBS}" CMAKE_BUILD_PARALLEL_LEVEL="${JOBS}"
LOG="$WORK/logs/build-$(date +%Y%m%d-%H%M%S).log"
echo "build log: $LOG"
# WHY a capped scope: the compile and the wasm link must not take a shared machine's memory down
run=(pyodide build-recipes-no-deps opencv-python --recipe-dir "$WORK/recipes" --force-rebuild)
if command -v systemd-run >/dev/null 2>&1; then
  run=(systemd-run --user --scope -p MemoryMax=40G -p OOMPolicy=continue -- "${run[@]}")
fi
"${run[@]}" 2>&1 | tee "$LOG"

# 4. the wheel, where the site serves it (ARUCO_CVWASM_OUT: elsewhere, to compare a rebuild first)
OUT="${ARUCO_CVWASM_OUT:-$REPO/web/public/opencv}"
mkdir -p "$OUT"
cp -v "$WORK/recipes/opencv-python/dist/$WHEEL" "$OUT/$WHEEL"
sha256sum "$OUT/$WHEEL"
