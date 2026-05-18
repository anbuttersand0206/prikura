#!/usr/bin/env bash
set -e

# Check for emscripten
if ! command -v emcc &>/dev/null; then
    echo "Emscripten not found. Installing via brew..."
    brew install emscripten
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR/../frontend/src/wasm"
mkdir -p "$OUT_DIR"

echo "Building Wasm pen engine..."

emcc -O3 \
    "$SCRIPT_DIR/src/stroke_interpolator.cpp" \
    "$SCRIPT_DIR/src/effects/neon.cpp" \
    "$SCRIPT_DIR/src/effects/jitter.cpp" \
    "$SCRIPT_DIR/src/effects/crayon.cpp" \
    "$SCRIPT_DIR/src/effects/pukkuri.cpp" \
    -s EXPORTED_FUNCTIONS='["_catmull_rom_interpolate","_apply_neon_glow","_apply_jitter","_apply_crayon_noise","_apply_pukkuri_highlight","_malloc","_free"]' \
    -s EXPORTED_RUNTIME_METHODS='["cwrap","ccall","HEAPU8","HEAPF32"]' \
    -s MODULARIZE=1 \
    -s EXPORT_NAME='PenEngine' \
    -s EXPORT_ES6=1 \
    -s ALLOW_MEMORY_GROWTH=1 \
    --no-entry \
    -o "$OUT_DIR/pen_engine.js"

echo "Done. Output: $OUT_DIR/pen_engine.js + pen_engine.wasm"
