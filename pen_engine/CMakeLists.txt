cmake_minimum_required(VERSION 3.15)
project(pen_engine)

set(CMAKE_CXX_STANDARD 17)

add_executable(pen_engine
    src/stroke_interpolator.cpp
    src/effects/neon.cpp
    src/effects/jitter.cpp
)

set_target_properties(pen_engine PROPERTIES
    SUFFIX ".js"
    LINK_FLAGS "-s EXPORTED_FUNCTIONS='[\"_catmull_rom_interpolate\",\"_apply_neon_glow\",\"_apply_jitter\",\"_malloc\",\"_free\"]' -s EXPORTED_RUNTIME_METHODS='[\"cwrap\",\"ccall\",\"HEAPU8\",\"HEAPF32\"]' -s MODULARIZE=1 -s EXPORT_NAME='PenEngine' -O3 --no-entry"
)
