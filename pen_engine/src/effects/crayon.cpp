#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdlib>
#include <cstdint>

extern "C" {

/**
 * Generate crayon noise texture into a pixel buffer.
 * pixels: RGBA uint8 buffer of width*height*4 bytes
 * Each call adds layered random noise to simulate crayon texture.
 */
EMSCRIPTEN_KEEPALIVE
void apply_crayon_noise(
    uint8_t* pixels,
    int width, int height,
    uint8_t r, uint8_t g, uint8_t b,
    float density,     // 0.0 - 1.0
    float roughness    // 0.0 - 1.0
) {
    int total = width * height;
    int noise_count = (int)(total * density * 0.3f);

    for (int n = 0; n < noise_count; ++n) {
        int px = rand() % width;
        int py = rand() % height;
        int idx = (py * width + px) * 4;
        if (pixels[idx + 3] < 10) continue;

        // Random brightness variation for crayon texture
        float var = 0.7f + ((float)rand() / RAND_MAX) * 0.6f * roughness;
        pixels[idx + 0] = (uint8_t)fminf(255.0f, r * var);
        pixels[idx + 1] = (uint8_t)fminf(255.0f, g * var);
        pixels[idx + 2] = (uint8_t)fminf(255.0f, b * var);
    }

    // Add white specular flecks
    int fleck_count = (int)(total * density * 0.05f);
    for (int n = 0; n < fleck_count; ++n) {
        int px = rand() % width;
        int py = rand() % height;
        int idx = (py * width + px) * 4;
        if (pixels[idx + 3] < 10) continue;
        pixels[idx + 0] = 255;
        pixels[idx + 1] = 255;
        pixels[idx + 2] = 255;
        pixels[idx + 3] = (uint8_t)(60 + rand() % 60);
    }
}

} // extern "C"
