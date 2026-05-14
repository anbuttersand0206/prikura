#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdint>
#include <algorithm>

extern "C" {

// Apply glow blur to a 32-bit RGBA pixel buffer (RGBA order)
// Simple box blur approximation for neon glow
EMSCRIPTEN_KEEPALIVE
void apply_neon_glow(
    uint8_t* pixels,
    int width, int height,
    uint8_t r, uint8_t g, uint8_t b,
    int radius,
    float intensity
) {
    std::vector<uint8_t> tmp(width * height * 4, 0);

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int idx = (y * width + x) * 4;
            if (pixels[idx + 3] == 0) continue;

            for (int dy = -radius; dy <= radius; ++dy) {
                for (int dx = -radius; dx <= radius; ++dx) {
                    float dist = std::sqrt((float)(dx * dx + dy * dy));
                    if (dist > radius) continue;
                    float alpha = (1.0f - dist / radius) * intensity;
                    int nx = x + dx, ny = y + dy;
                    if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
                    int nidx = (ny * width + nx) * 4;
                    tmp[nidx + 0] = std::min(255, (int)tmp[nidx + 0] + (int)(r * alpha));
                    tmp[nidx + 1] = std::min(255, (int)tmp[nidx + 1] + (int)(g * alpha));
                    tmp[nidx + 2] = std::min(255, (int)tmp[nidx + 2] + (int)(b * alpha));
                    tmp[nidx + 3] = std::min(255, (int)tmp[nidx + 3] + (int)(255 * alpha));
                }
            }
        }
    }

    // Composite glow under original
    for (int i = 0; i < width * height * 4; ++i) {
        if (i % 4 == 3) continue;
        pixels[i] = std::min(255, (int)pixels[i] + (int)tmp[i]);
    }
}

} // extern "C"
