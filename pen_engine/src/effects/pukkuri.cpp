#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdint>

extern "C" {

/**
 * Render a "pukkuri" (puffy/3D) highlight onto a stroke pixel buffer.
 * pixels: RGBA uint8 buffer
 * cx_norm, cy_norm: stroke center position in [0,1] normalized coords
 * The function adds a bright highlight line offset slightly up-left.
 */
EMSCRIPTEN_KEEPALIVE
void apply_pukkuri_highlight(
    uint8_t* pixels,
    int width, int height,
    float highlight_width_ratio,  // highlight line width relative to stroke width
    float shadow_strength         // 0.0 - 1.0
) {
    // Scan non-transparent pixels and add directional shading
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int idx = (y * width + x) * 4;
            if (pixels[idx + 3] < 10) continue;

            // Find local vertical position within the stroke (estimate)
            // Look up and down to find stroke extent
            int top = y, bot = y;
            while (top > 0 && pixels[((top-1)*width + x)*4 + 3] > 10) --top;
            while (bot < height-1 && pixels[((bot+1)*width + x)*4 + 3] > 10) ++bot;

            int stroke_h = bot - top + 1;
            if (stroke_h < 2) continue;

            float t = (float)(y - top) / stroke_h;  // 0=top, 1=bottom

            // Highlight: upper 20-40% gets brighter
            if (t < highlight_width_ratio) {
                float factor = 1.0f + (1.0f - t / highlight_width_ratio) * 0.6f;
                pixels[idx+0] = (uint8_t)fminf(255.0f, pixels[idx+0] * factor);
                pixels[idx+1] = (uint8_t)fminf(255.0f, pixels[idx+1] * factor);
                pixels[idx+2] = (uint8_t)fminf(255.0f, pixels[idx+2] * factor);
            }
            // Shadow: lower 20% gets darker
            else if (t > (1.0f - highlight_width_ratio)) {
                float factor = 1.0f - ((t - (1.0f - highlight_width_ratio)) / highlight_width_ratio) * shadow_strength * 0.5f;
                pixels[idx+0] = (uint8_t)fmaxf(0.0f, pixels[idx+0] * factor);
                pixels[idx+1] = (uint8_t)fmaxf(0.0f, pixels[idx+1] * factor);
                pixels[idx+2] = (uint8_t)fmaxf(0.0f, pixels[idx+2] * factor);
            }
        }
    }
}

} // extern "C"
