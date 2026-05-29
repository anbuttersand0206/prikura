#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdint>

extern "C" {

// ぷっくりペンのハイライト・シャドウをピクセルバッファに適用する。
// Canvas の JavaScript 側でも同様の効果は出せるが、
// ストロークの垂直方向位置（上端・下端からの距離）を
// ピクセル単位で走査する方が精度が高いため Wasm で実装している。
EMSCRIPTEN_KEEPALIVE
void apply_pukkuri_highlight(
    uint8_t* pixels,
    int width, int height,
    float highlight_width_ratio,  // ハイライトが上端から何割の範囲に入るか（0.2〜0.4 が目安）
    float shadow_strength         // 下端の影の強さ 0.0〜1.0
) {
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int idx = (y * width + x) * 4;
            if (pixels[idx + 3] < 10) continue;

            // ストロークの上端・下端を上下に走査して縦方向の範囲を求める。
            // 各列ごとに独立して計算するため、曲線ストロークにも対応できる。
            int top = y, bot = y;
            while (top > 0 && pixels[((top-1)*width + x)*4 + 3] > 10) --top;
            while (bot < height-1 && pixels[((bot+1)*width + x)*4 + 3] > 10) ++bot;

            int stroke_h = bot - top + 1;
            if (stroke_h < 2) continue;

            float t = (float)(y - top) / stroke_h; // 0=上端, 1=下端

            // 上部 highlight_width_ratio の範囲を明るく（光が上から当たる表現）
            if (t < highlight_width_ratio) {
                float factor = 1.0f + (1.0f - t / highlight_width_ratio) * 0.6f;
                pixels[idx+0] = (uint8_t)fminf(255.0f, pixels[idx+0] * factor);
                pixels[idx+1] = (uint8_t)fminf(255.0f, pixels[idx+1] * factor);
                pixels[idx+2] = (uint8_t)fminf(255.0f, pixels[idx+2] * factor);
            }
            // 下部 highlight_width_ratio の範囲を暗く（丸みによる影）
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
