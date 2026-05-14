#include <emscripten/emscripten.h>
#include <cmath>
#include <vector>
#include <cstdint>
#include <cstring>

extern "C" {

struct Point { float x, y; };

// Catmull-Rom spline interpolation
// Returns number of output points written
EMSCRIPTEN_KEEPALIVE
int catmull_rom_interpolate(
    const float* pts_in,  // interleaved x,y
    int n_pts,
    float* pts_out,       // output interleaved x,y
    int max_out,
    float tension
) {
    if (n_pts < 2) return 0;

    std::vector<Point> pts(n_pts + 2);
    for (int i = 0; i < n_pts; ++i) {
        pts[i + 1] = { pts_in[i * 2], pts_in[i * 2 + 1] };
    }
    pts[0] = pts[1];
    pts[n_pts + 1] = pts[n_pts];

    int count = 0;
    float step = 0.05f;

    for (int i = 1; i < n_pts; ++i) {
        Point& p0 = pts[i - 1];
        Point& p1 = pts[i];
        Point& p2 = pts[i + 1];
        Point& p3 = pts[i + 2];

        for (float t = 0.0f; t <= 1.0f; t += step) {
            if (count >= max_out - 1) break;
            float t2 = t * t;
            float t3 = t2 * t;
            float x = 0.5f * (
                (2.0f * p1.x) +
                (-p0.x + p2.x) * t +
                (2.0f * p0.x - 5.0f * p1.x + 4.0f * p2.x - p3.x) * t2 +
                (-p0.x + 3.0f * p1.x - 3.0f * p2.x + p3.x) * t3
            );
            float y = 0.5f * (
                (2.0f * p1.y) +
                (-p0.y + p2.y) * t +
                (2.0f * p0.y - 5.0f * p1.y + 4.0f * p2.y - p3.y) * t2 +
                (-p0.y + 3.0f * p1.y - 3.0f * p2.y + p3.y) * t3
            );
            pts_out[count * 2] = x;
            pts_out[count * 2 + 1] = y;
            count++;
        }
    }

    // Add last point
    if (count < max_out) {
        pts_out[count * 2] = pts_in[(n_pts - 1) * 2];
        pts_out[count * 2 + 1] = pts_in[(n_pts - 1) * 2 + 1];
        count++;
    }

    return count;
}

} // extern "C"
