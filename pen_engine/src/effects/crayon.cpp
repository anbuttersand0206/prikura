#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdlib>
#include <cstdint>

extern "C" {

// クレヨン質感ノイズをピクセルバッファに重ねる。
// Math.random() を使うと Undo → 再描画のたびに質感が変わってちらつくため、
// C 標準の rand()（固定シード）で決定論的なノイズを生成する。
EMSCRIPTEN_KEEPALIVE
void apply_crayon_noise(
    uint8_t* pixels,   // RGBA の順で格納されたピクセルバッファ
    int width, int height,
    uint8_t r, uint8_t g, uint8_t b,
    float density,     // ノイズの密度 0.0〜1.0
    float roughness    // 明度バラつきの強さ 0.0〜1.0
) {
    int total = width * height;
    // density * 0.3 で過剰なノイズを抑える（0.3 は主観評価で決定）
    int noise_count = (int)(total * density * 0.3f);

    for (int n = 0; n < noise_count; ++n) {
        int px = rand() % width;
        int py = rand() % height;
        int idx = (py * width + px) * 4;
        if (pixels[idx + 3] < 10) continue; // 透明ピクセルには描かない

        // roughness に応じて 0.7〜1.3 倍の明度ゆらぎを加える
        float var = 0.7f + ((float)rand() / RAND_MAX) * 0.6f * roughness;
        pixels[idx + 0] = (uint8_t)fminf(255.0f, r * var);
        pixels[idx + 1] = (uint8_t)fminf(255.0f, g * var);
        pixels[idx + 2] = (uint8_t)fminf(255.0f, b * var);
    }

    // 紙の凹凸に光が当たって生じる白いハイライト（スペキュラ）を点描
    int fleck_count = (int)(total * density * 0.05f);
    for (int n = 0; n < fleck_count; ++n) {
        int px = rand() % width;
        int py = rand() % height;
        int idx = (py * width + px) * 4;
        if (pixels[idx + 3] < 10) continue;
        pixels[idx + 0] = 255;
        pixels[idx + 1] = 255;
        pixels[idx + 2] = 255;
        // アルファをランダムにして「ちらっと光る」感じを出す
        pixels[idx + 3] = (uint8_t)(60 + rand() % 60);
    }
}

} // extern "C"
