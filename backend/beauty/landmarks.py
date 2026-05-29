"""landmarks.py — MediaPipe FaceMesh ラッパー"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple
import numpy as np

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
    _mp_face_mesh = mp.solutions.face_mesh
except ImportError:
    _MP_AVAILABLE = False
    _mp_face_mesh = None


@dataclass
class FaceLandmarks:
    """1 顔分のランドマーク情報をまとめたデータクラス。"""
    raw: object          # mediapipe NormalizedLandmarkList
    h: int               # 画像の高さ (px)
    w: int               # 画像の幅  (px)

    def pt(self, idx: int) -> Tuple[int, int]:
        """ランドマーク idx の整数ピクセル座標 (x, y) を返す。"""
        p = self.raw.landmark[idx]
        return (int(p.x * self.w), int(p.y * self.h))

    def ptf(self, idx: int) -> Tuple[float, float]:
        """ランドマーク idx の浮動小数点ピクセル座標 (x, y) を返す。"""
        p = self.raw.landmark[idx]
        return (p.x * self.w, p.y * self.h)

    def pts(self, indices: List[int]) -> np.ndarray:
        """複数ランドマークの整数座標を shape (N, 2) の ndarray で返す。"""
        return np.array([self.pt(i) for i in indices], dtype=np.int32)


class FaceMeshDetector:
    """
    MediaPipe FaceMesh のシングルトンラッパー。
    refine_landmarks=True で虹彩 (468/473) も取得する。
    """

    def __init__(self, max_num_faces: int = 1) -> None:
        self._mesh = None
        if _MP_AVAILABLE:
            self._mesh = _mp_face_mesh.FaceMesh(
                max_num_faces=max_num_faces,
                # refine_landmarks=True にすると通常の 468 点に加えて
                # 虹彩ランドマーク（468/473 = 左右の虹彩中心）が使えるようになる。
                # 目の拡大・黒目サイズ変更・目の反射処理で必要なため有効化している。
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

    @property
    def available(self) -> bool:
        return self._mesh is not None

    def detect(self, bgr: np.ndarray) -> Optional[FaceLandmarks]:
        """
        BGR 画像から最初の顔のランドマークを返す。
        顔が検出されない場合は None。
        """
        if not self.available:
            return None
        h, w = bgr.shape[:2]
        rgb = bgr[:, :, ::-1].copy()  # BGR → RGB (MediaPipe は RGB を受け取る)
        result = self._mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None
        return FaceLandmarks(raw=result.multi_face_landmarks[0], h=h, w=w)
