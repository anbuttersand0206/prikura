"""smoothing.py — 肌なめらか（bilateral + ハイパス）とシャープネス"""

from __future__ import annotations
from typing import Optional
import cv2
import numpy as np

_SKIN_LOWER = (0,   133,  77)
_SKIN_UPPER = (255, 173, 127)

_BILATERAL_D       = 9
_BILATERAL_SIGMA_C = 80
_BILATERAL_SIGMA_S = 80


def _skin_mask(bgr: np.ndarray, blur_ksize: int = 21) -> np.ndarray:
    """YCrCb 肌マスク（float32, shape (H,W,1)）。"""
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    mask  = cv2.inRange(ycrcb, _SKIN_LOWER, _SKIN_UPPER).astype(np.float32) / 255.0
    mask  = cv2.GaussianBlur(mask, (blur_ksize, blur_ksize), blur_ksize / 3.0)
    return mask[:, :, np.newaxis]


def smooth_skin(bgr: np.ndarray, strength: float,
                person_mask: Optional[np.ndarray] = None) -> np.ndarray:
    """
    bilateral フィルタ + ハイパスブレンドで肌をなめらかにする。
    person_mask（人体セグメンテーション, float32 H×W）を渡すと
    YCrCb 肌色マスクと AND して背景への影響を防ぐ。
    strength: 0–1。
    """
    if strength <= 0.0:
        return bgr
    alpha = float(np.clip(strength, 0.0, 1.0))
    mask  = _skin_mask(bgr)
    if person_mask is not None:
        mask = mask * person_mask[:, :, np.newaxis]

    smoothed = cv2.bilateralFilter(bgr, _BILATERAL_D,
                                   _BILATERAL_SIGMA_C, _BILATERAL_SIGMA_S)

    blur_hp   = cv2.GaussianBlur(bgr, (0, 0), 3.0)
    high_pass = np.clip(bgr.astype(np.float32) - blur_hp.astype(np.float32) + 128, 0, 255)
    tx = 0.28
    blended = (smoothed.astype(np.float32) * (1.0 - tx) + high_pass * tx)

    result = bgr.astype(np.float32) * (1.0 - mask * alpha) + blended * (mask * alpha)
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_sharpness(bgr: np.ndarray, strength: float,
                    person_mask: Optional[np.ndarray] = None) -> np.ndarray:
    """
    アンシャープマスクで輪郭を強調する（シャープネス）。
    person_mask を渡すと人体外への影響を防ぐ。
    strength: 0–1。
    """
    if strength <= 0.0:
        return bgr
    alpha = float(np.clip(strength, 0.0, 1.0))

    blurred = cv2.GaussianBlur(bgr, (0, 0), 1.5)
    amount  = alpha * 1.2
    sharp   = np.clip(bgr.astype(np.float32) * (1 + amount)
                      - blurred.astype(np.float32) * amount, 0, 255).astype(np.uint8)

    mask = _skin_mask(bgr, blur_ksize=15)
    if person_mask is not None:
        mask = mask * person_mask[:, :, np.newaxis]
    result = bgr.astype(np.float32) * (1.0 - mask * alpha) + sharp.astype(np.float32) * (mask * alpha)
    return np.clip(result, 0, 255).astype(np.uint8)
