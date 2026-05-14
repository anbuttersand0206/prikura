#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdlib>

extern "C" {

EMSCRIPTEN_KEEPALIVE
void apply_jitter(float* pts, int n_pts, float amount) {
    for (int i = 0; i < n_pts; ++i) {
        float jx = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * amount;
        float jy = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * amount;
        pts[i * 2] += jx;
        pts[i * 2 + 1] += jy;
    }
}

} // extern "C"
