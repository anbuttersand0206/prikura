"""color.py — 色補正・目の反射・クマ消し・歯ホワイトニング"""

from __future__ import annotations
from typing import Optional
import cv2
import numpy as np

from .landmarks import FaceLandmarks

# YCrCb 肌色域
_SKIN_LOWER = (0,   133,  77)
_SKIN_UPPER = (255, 173, 127)

# ── ランドマーク定数（color.py 内で使う最小限） ──────────────
_L_EYE_OUTER, _L_EYE_INNER = 33,  133
_L_EYE_BOT                  = 145
_R_EYE_OUTER, _R_EYE_INNER = 263, 362
_R_EYE_BOT                  = 374
_L_IRIS                      = 468
_R_IRIS                      = 473
_L_IRIS_TOP, _R_IRIS_TOP     = 469, 474
_L_IRIS_BOT, _R_IRIS_BOT     = 471, 476
_MOUTH_L, _MOUTH_R           = 61,  291
_UPPER_LIP_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308]
_LOWER_LIP_INNER = [95, 88, 178, 87, 14, 317, 402, 318, 324]


# ── ユーティリティ ────────────────────────────────────────────

def _skin_mask_float(bgr: np.ndarray, blur: int = 15) -> np.ndarray:
    """YCrCb 肌マスク（float32, shape (H,W,1)）。"""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    mask  = cv2.inRange(ycrcb, _SKIN_LOWER, _SKIN_UPPER).astype(np.float32) / 255.0
    mask  = cv2.GaussianBlur(mask, (blur, blur), blur / 3.0)
    return mask[:, :, np.newaxis]


def _landmark_mask(h: int, w: int, pts: np.ndarray, blur: int) -> np.ndarray:
    """ランドマーク群の凸包を塗りつぶしてぼかしたマスク（float32 2D）。"""
    mask = np.zeros((h, w), np.uint8)
    hull = cv2.convexHull(pts)
    cv2.fillConvexPoly(mask, hull, 255)
    blur_k = blur | 1
    mask = cv2.GaussianBlur(mask.astype(np.float32), (blur_k, blur_k), blur_k / 3.0)
    return mask / 255.0


# ── 美白（LAB L チャンネル） ──────────────────────────────────

def whiten_skin(bgr: np.ndarray, strength: float,
                person_mask: Optional[np.ndarray] = None) -> np.ndarray:
    """
    肌領域の LAB L チャンネルを上げて美白する。
    person_mask（人体セグメンテーション, float32 H×W）を渡すと
    YCrCb 肌色マスクと AND して背景への影響を防ぐ。
    strength: 0–1。
    """
    if strength <= 0.0:
        return bgr
    alpha = float(np.clip(strength, 0.0, 1.0))
    boost = alpha * 22.0
    lab   = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    mask  = _skin_mask_float(bgr)
    if person_mask is not None:
        mask = mask * person_mask[:, :, np.newaxis]
    lab[:, :, 0] = np.clip(lab[:, :, 0] + boost * mask[:, :, 0], 0, 255)
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


# ── トーンカーブ（色温度） ────────────────────────────────────

def apply_tone(bgr: np.ndarray, warmth: float) -> np.ndarray:
    """LUT で色温度を調整する。warmth: -1（クール）〜+1（ウォーム）。"""
    if warmth == 0.0:
        return bgr
    shift_r = int(np.clip(warmth,  -1.0, 1.0) * 18)
    shift_b = int(np.clip(warmth,  -1.0, 1.0) * -12)
    x = np.arange(256, dtype=np.float32)
    lut_r = np.clip(x + shift_r, 0, 255).astype(np.uint8)
    lut_g = x.astype(np.uint8)
    lut_b = np.clip(x + shift_b, 0, 255).astype(np.uint8)
    b, g, r = cv2.split(bgr)
    return cv2.merge([cv2.LUT(b, lut_b), cv2.LUT(g, lut_g), cv2.LUT(r, lut_r)])


# ── 肌の明るさ（HSV V チャンネル） ───────────────────────────

def adjust_skin_brightness(bgr: np.ndarray, value: float) -> np.ndarray:
    """スクリーン（明るく）/ 乗算（暗く）ブレンドで明るさを調整する。value: -1–+1。"""
    if value == 0.0:
        return bgr
    alpha = abs(float(value)) * 0.6
    src   = bgr.astype(np.float32)
    if value > 0:
        out = src + alpha * (255.0 - src)  # スクリーン合成
    else:
        out = src * (1.0 - alpha)           # 乗算合成
    return np.clip(out, 0, 255).astype(np.uint8)


# ── 目の反射・キラキラ ────────────────────────────────────────

def add_eye_sparkle(bgr: np.ndarray, lm: FaceLandmarks, strength: float) -> np.ndarray:
    """
    虹彩の右上に白い光沢ハイライトを追加する（目の反射）。
    ハイライトはガウシアンぼかしで自然に馴染ませる。
    strength: 0–1。
    """
    if strength <= 0.0:
        return bgr
    alpha = float(np.clip(strength, 0.0, 1.0))
    h, w  = bgr.shape[:2]
    overlay = np.zeros((h, w), np.float32)

    for iris, top, bot in [
        (_L_IRIS, _L_IRIS_TOP, _L_IRIS_BOT),
        (_R_IRIS, _R_IRIS_TOP, _R_IRIS_BOT),
    ]:
        cx, cy   = lm.ptf(iris)
        _, top_y = lm.ptf(top)
        _, bot_y = lm.ptf(bot)
        iris_r   = max((bot_y - top_y) / 2.0, 3.0)

        # メインハイライト（右上）
        sx = int(cx + iris_r * 0.45)
        sy = int(cy - iris_r * 0.50)
        sr = max(int(iris_r * 0.40), 2)
        cv2.circle(overlay, (sx, sy), sr, 1.0, -1)

        # サブハイライト（左上・小）
        sx2 = int(cx - iris_r * 0.25)
        sy2 = int(cy - iris_r * 0.55)
        cv2.circle(overlay, (sx2, sy2), max(sr // 2, 1), 0.6, -1)

    # ぼかして自然に
    ksize = max(int(h * 0.008) | 1, 3)
    overlay = cv2.GaussianBlur(overlay, (ksize, ksize), ksize / 3.0)
    overlay_3ch = np.stack([overlay] * 3, axis=-1)

    result = bgr.astype(np.float32) + overlay_3ch * alpha * 200.0
    return np.clip(result, 0, 255).astype(np.uint8)


# ── クマ消し ──────────────────────────────────────────────────

def remove_dark_circles(bgr: np.ndarray, lm: FaceLandmarks, strength: float) -> np.ndarray:
    """
    目の下の暗い領域を明るくしてクマを軽減する。
    LAB L チャンネルを上げ、a/b を中性方向へ戻す（脱色）。
    strength: 0–1。
    """
    if strength <= 0.0:
        return bgr
    alpha = float(np.clip(strength, 0.0, 1.0))
    h, w  = bgr.shape[:2]

    under_eye_mask = np.zeros((h, w), np.float32)

    for outer, inner, bot, iris in [
        (_L_EYE_OUTER, _L_EYE_INNER, _L_EYE_BOT, _L_IRIS),
        (_R_EYE_OUTER, _R_EYE_INNER, _R_EYE_BOT, _R_IRIS),
    ]:
        ox, oy   = lm.ptf(outer)
        ix, iy   = lm.ptf(inner)
        bot_x, bot_y = lm.ptf(bot)
        icx, icy = lm.ptf(iris)
        drop = int((bot_y - icy) * 2.2)

        # 目の下の楕円領域
        ell_cx = int((ox + ix) / 2)
        ell_cy = int(bot_y + drop * 0.4)
        ell_w  = int(abs(ox - ix) * 0.55)
        ell_h  = max(int(drop * 0.65), 4)
        cv2.ellipse(under_eye_mask, (ell_cx, ell_cy),
                    (ell_w, ell_h), 0, 0, 360, 1.0, -1)

    ksize = max(int(h * 0.025) | 1, 9)
    under_eye_mask = cv2.GaussianBlur(under_eye_mask, (ksize, ksize), ksize / 3.0)

    lab   = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    m     = under_eye_mask * alpha
    lab[:, :, 0] = np.clip(lab[:, :, 0] + 18.0 * m, 0, 255)
    lab[:, :, 1] = lab[:, :, 1] * (1 - m * 0.35) + 128.0 * (m * 0.35)
    lab[:, :, 2] = lab[:, :, 2] * (1 - m * 0.25) + 128.0 * (m * 0.25)
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


# ── 歯ホワイトニング ──────────────────────────────────────────

def whiten_teeth(bgr: np.ndarray, lm: FaceLandmarks, strength: float) -> np.ndarray:
    """
    口の内側（歯）領域を白くする。
    - 輝度が一定以上の部分のみ処理して歯肉・舌の誤白化を防ぐ
    - LAB L チャンネルを上げ、b チャンネル（黄み）を下げる
    strength: 0–1。
    """
    if strength <= 0.0:
        return bgr
    alpha = float(np.clip(strength, 0.0, 1.0))
    h, w  = bgr.shape[:2]

    upper = lm.pts(_UPPER_LIP_INNER)
    lower = lm.pts(_LOWER_LIP_INNER)
    teeth_pts = np.vstack([upper, lower])

    teeth_mask = _landmark_mask(h, w, teeth_pts, blur=7)

    # 輝度フィルタ: 暗い領域（L < 60）はホワイトニングしない
    lab_raw = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    bright  = np.clip((lab_raw[:, :, 0] - 55.0) / 40.0, 0.0, 1.0)
    m       = teeth_mask * bright * alpha

    lab_raw[:, :, 0] = np.clip(lab_raw[:, :, 0] + 20.0 * m, 0, 255)
    lab_raw[:, :, 2] = np.clip(lab_raw[:, :, 2] - 12.0 * m, 0, 255)  # 黄み除去
    return cv2.cvtColor(np.clip(lab_raw, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
