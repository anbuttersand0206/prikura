#include <emscripten/emscripten.h>
#include <cmath>
#include <cstdint>
#include <vector>
#include <algorithm>

extern "C" {

// ネオン発光エフェクト。
// 描き込み済みのストロークピクセルを中心に、距離に応じた輝度を周囲に拡散する。
// CSS の filter:blur() と異なり、Wasm 上でピクセル単位に操作するため
// 透明ピクセルの向こう側の合成レイヤーに影響を与えず、より正確なグロー表現が可能。
EMSCRIPTEN_KEEPALIVE
void apply_neon_glow(
    uint8_t* pixels,  // RGBA の順で格納されたピクセルバッファ
    int width, int height,
    uint8_t r, uint8_t g, uint8_t b,
    int radius,
    float intensity
) {
    // グロー合成先を一時バッファに書き出す。
    // 直接 pixels に書き込むと処理中のグローが次のピクセルの計算に混入してしまう。
    std::vector<uint8_t> tmp(width * height * 4, 0);

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            int idx = (y * width + x) * 4;
            if (pixels[idx + 3] == 0) continue; // 透明ピクセルはグロー源にしない

            for (int dy = -radius; dy <= radius; ++dy) {
                for (int dx = -radius; dx <= radius; ++dx) {
                    float dist = std::sqrt((float)(dx * dx + dy * dy));
                    if (dist > radius) continue;
                    // 中心に近いほど強く光る（線形減衰）
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

    // グローをストロークの下に合成（ストローク本体が上になるよう加算）
    for (int i = 0; i < width * height * 4; ++i) {
        if (i % 4 == 3) continue; // アルファチャンネルは別途加算済みのためスキップ
        pixels[i] = std::min(255, (int)pixels[i] + (int)tmp[i]);
    }
}

} // extern "C"
