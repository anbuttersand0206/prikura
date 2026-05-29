#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdlib>

extern "C" {

// 点列にランダムなジッター（微小な位置ゆらぎ）を加える。
// クレヨンやゆるペンなど「手書き感」を出したいペンで使う。
// Math.random() ではなく C の rand() を使うのは
// 同じ筆跡を Undo → 再描画しても同じゆらぎになるようにするため。
EMSCRIPTEN_KEEPALIVE
void apply_jitter(float* pts, int n_pts, float amount) {
    for (int i = 0; i < n_pts; ++i) {
        float jx = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * amount;
        float jy = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * amount;
        pts[i * 2]     += jx;
        pts[i * 2 + 1] += jy;
    }
}

} // extern "C"
