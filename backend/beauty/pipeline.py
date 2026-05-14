"""pipeline.py — BeautyParams + BeautyPipeline（全21機能）"""

from __future__ import annotations
import base64
import threading
from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2

# rembg は初回インポート時にモデルをダウンロードするため遅延インポートする
try:
    from rembg import new_session, remove as rembg_remove
    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False

from .landmarks import FaceMeshDetector, FaceLandmarks
from .smoothing import smooth_skin, apply_sharpness
from .warp      import apply_all_warps
from .color     import (
    whiten_skin, apply_tone, adjust_skin_brightness,
    add_eye_sparkle, whiten_teeth,
)

# チーク・リップ・涙袋はここで直接実装（pipeline 内の小関数）
def _hex_to_bgr(hex_color: str):
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)


_FACE_OVAL_IDS = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172,  58, 132,  93, 234, 127, 162,  21,  54, 103,  67, 109,
]


def _apply_cheek(img: np.ndarray, lm: FaceLandmarks, params: 'BeautyParams') -> np.ndarray:
    h, w  = img.shape[:2]
    out   = img.copy().astype(np.float32)
    bgr   = _hex_to_bgr(params.cheek_color)
    alpha = float(params.cheek_strength)

    # 顔の輪郭マスク — 顔の外にはみ出さないようにする
    oval_pts  = lm.pts(_FACE_OVAL_IDS)
    face_mask = np.zeros((h, w), np.float32)
    cv2.fillPoly(face_mask, [oval_pts], 1.0)
    face_mask = cv2.GaussianBlur(face_mask, (21, 21), 7)

    # (目下端idx, 口角idx, 鼻翼idx, 顔外側idx)
    for eye_bot_i, mouth_i, nose_i, outer_i in [
        (145,  61, 129, 234),   # 左頬
        (374, 291, 358, 454),   # 右頬
    ]:
        _, ey  = lm.pt(eye_bot_i)   # 目下端 Y
        nx, _  = lm.pt(nose_i)      # 鼻翼 X
        ox, _  = lm.pt(outer_i)     # 顔外側 X
        mx, my = lm.pt(mouth_i)     # 口角

        # 頬の中心: 鼻翼〜顔外側の中間、目下端〜口角の中間
        cx_c = (nx + ox) // 2
        cy_c = (ey + my) // 2

        # 半径: 目下端〜口角距離の35%（顔サイズに自動追従）
        r = max(10, int((my - ey) * 0.35))
        ksize = (r * 2 + 1) | 1

        circle = np.zeros((h, w), np.float32)
        cv2.circle(circle, (cx_c, cy_c), r, 1.0, -1)
        circle = cv2.GaussianBlur(circle, (ksize, ksize), r / 2.5)

        # 目より上・口角より下をゼロにクリップ
        circle[:ey, :] = 0
        circle[my:, :] = 0

        combined = circle * face_mask * alpha
        for c, v in enumerate(bgr):
            out[:, :, c] = out[:, :, c] * (1 - combined) + v * combined

    return np.clip(out, 0, 255).astype(np.uint8)


def _apply_lip(img: np.ndarray, lm: FaceLandmarks, params: 'BeautyParams') -> np.ndarray:
    h, w  = img.shape[:2]
    out   = img.copy().astype(np.float32)
    bgr   = _hex_to_bgr(params.lip_color)
    alpha = float(params.lip_strength) * 0.5
    ids   = [61,185,40,39,37,0,267,269,270,409,291,375,321,405,314,17,84,181,91,146]
    pts   = lm.pts(ids)
    mask  = np.zeros((h, w), np.float32)
    cv2.fillPoly(mask, [pts], 1.0)
    mask = cv2.GaussianBlur(mask, (15, 15), 5)
    for c, v in enumerate(bgr):
        out[:, :, c] = out[:, :, c] * (1 - mask * alpha) + v * mask * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _apply_dark_circle(img: np.ndarray, lm: FaceLandmarks, params: 'BeautyParams') -> np.ndarray:
    """クマとり: 目の下を広めに明るく補正する（旧涙袋コードを移植）。"""
    h, w  = img.shape[:2]
    out   = img.copy().astype(np.float32)
    alpha = float(params.dark_circle_strength) * 0.67
    for a, b_idx in [(374, 380), (145, 153)]:
        cx = (lm.pt(a)[0] + lm.pt(b_idx)[0]) // 2
        cy = (lm.pt(a)[1] + lm.pt(b_idx)[1]) // 2
        cy += int(h * 0.018)
        r  = int(w * 0.028)
        mask = np.zeros((h, w), np.float32)
        cv2.ellipse(mask, (cx, cy), (r, r // 2), 0, 0, 180, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (r | 1, r | 1), r / 3.0)
        for c, v in enumerate((225, 215, 230)):
            out[:, :, c] = out[:, :, c] * (1 - mask * alpha) + v * mask * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _apply_tear_bag(img: np.ndarray, lm: FaceLandmarks, params: 'BeautyParams') -> np.ndarray:
    """涙袋: 下まぶた直下にライン状のパールハイライトを入れる。"""
    h, w  = img.shape[:2]
    out   = img.copy().astype(np.float32)
    alpha = float(params.tear_bag_strength) * 0.65

    # (外目尻idx, 内目尻idx, 下まぶた最下点idx)
    for outer_i, inner_i, bot_i in [(33, 133, 145), (263, 362, 374)]:
        ox, _  = lm.pt(outer_i)
        ix, _  = lm.pt(inner_i)
        _, by  = lm.pt(bot_i)

        cx     = (ox + ix) // 2
        cy     = by + int(h * 0.005)        # 下まぶた直下
        eye_w  = abs(ox - ix)
        half_w = max(int(eye_w * 0.43), 4)  # 目幅に沿った横幅
        half_h = max(int(h * 0.009), 2)     # ごく薄いライン

        mask = np.zeros((h, w), np.float32)
        cv2.ellipse(mask, (cx, cy), (half_w, half_h), 0, 0, 360, 1.0, -1)
        k = max((half_h * 2 + 1) | 1, 5)
        mask = cv2.GaussianBlur(mask, (k, k), half_h * 0.8)

        for c, v in enumerate((232, 222, 236)):   # BGR: パールハイライト
            out[:, :, c] = out[:, :, c] * (1 - mask * alpha) + v * mask * alpha

    return np.clip(out, 0, 255).astype(np.uint8)


# ── BeautyParams ─────────────────────────────────────────────

@dataclass
class BeautyParams:
    """
    顔加工パイプラインの全パラメータ。
    デフォルトはすべて 0.0 = 加工なし。

    strength の符号:
      ・0–1 範囲のもの: 0 = なし, 1 = 最大
      ・-1–+1 範囲のもの: 0 = なし, 正/負で方向が変わる
        例) face_slim_strength  > 0 = 細く, < 0 = 太く
            eye_tilt_strength   > 0 = つり目, < 0 = タレ目
    """

    # ── 肌・テクスチャ ─────────────────────────────────────
    smoothing_strength:  float = 0.0   # 美肌           0–1
    sharpness_strength:  float = 0.0   # シャープネス   0–1
    skin_brightness:     float = 0.0   # 肌の明るさ    -1–+1
    skin_warmth:         float = 0.0   # 肌の色温度    -1–+1
    whitening_strength:  float = 0.0   # 美白           0–1

    # ── 顔形・輪郭 ─────────────────────────────────────────
    face_slim_strength:        float = 0.0   # 顔痩せ        -1–+1
    head_size_strength:        float = 0.0   # 頭サイズ      -1–+1
    mid_face_shorten_strength: float = 0.0   # 中顔面短縮    -1–+1
    cheek_width_strength:      float = 0.0   # 頬横幅        -1–+1
    jaw_strength:              float = 0.0   # エラ削り      -1–+1
    chin_length_strength:      float = 0.0   # 顎縦幅        -1–+1

    # ── 鼻 ─────────────────────────────────────────────────
    nose_width_strength:  float = 0.0   # 小鼻サイズ    -1–+1
    nose_height_strength: float = 0.0   # 鼻縦幅        -1–+1

    # ── 目 ─────────────────────────────────────────────────
    eye_size_strength:     float = 0.0   # 目のサイズ    -1–+1
    eye_position_strength: float = 0.0   # 目の位置      -1–+1
    eye_sparkle_strength:  float = 0.0   # 目の反射       0–1
    iris_size_strength:    float = 0.0   # 黒目サイズ    -1–+1
    eye_tilt_strength:     float = 0.0   # タレ目/つり目 -1–+1
    dark_circle_strength:  float = 0.0   # クマ消し       0–1

    # ── 口 ─────────────────────────────────────────────────
    mouth_size_strength:      float = 0.0   # 口サイズ      -1–+1
    mouth_corner_strength:    float = 0.0   # 口角          -1–+1
    philtrum_strength:        float = 0.0   # 人中          -1–+1
    teeth_whitening_strength: float = 0.0   # 歯ホワイトニング 0–1

    # ── メイクアップ ────────────────────────────────────────
    cheek_strength: float = 0.0
    cheek_color:    str   = "#FFB7C5"
    lip_strength:   float = 0.0
    lip_color:      str   = "#FF6B9D"
    tear_bag_strength: float = 0.0


# ── BeautyPipeline ────────────────────────────────────────────

class BeautyPipeline:
    """
    全美容加工を順番に適用するパイプライン。
    apply() が公開 API（静止画用）。
    apply_realtime() はリアルタイム用（4機能のみ）。

    背景除去には rembg (MIT) + U²-Net (Apache 2.0) を使用。
    rembg が未インストールの場合は MediaPipe SelfieSegmentation に
    自動フォールバックする。
    """

    # rembg セッションはプロセス内でシングルトン共有（モデルロードは重いため）
    _rembg_session = None
    _rembg_lock    = threading.Lock()

    def __init__(self) -> None:
        self._detector = FaceMeshDetector(max_num_faces=1)

        # rembg が使えない場合のフォールバック用
        if not _REMBG_AVAILABLE:
            import mediapipe as mp
            self._segmenter = mp.solutions.selfie_segmentation.SelfieSegmentation(
                model_selection=1
            )
            self._seg_lock = threading.Lock()

    # ── rembg セッション取得（遅延初期化・スレッドセーフ） ──────────
    @classmethod
    def _get_rembg_session(cls):
        """u2net_human_seg セッションをシングルトンで返す。"""
        if cls._rembg_session is None:
            with cls._rembg_lock:
                if cls._rembg_session is None:
                    # u2net_human_seg: 人物セグメンテーション専用モデル
                    # 初回呼び出し時に ~/.u2net/ へ自動ダウンロード（約176MB）
                    cls._rembg_session = new_session("u2net_human_seg")
        return cls._rembg_session

    # ── 人体マスク取得 ────────────────────────────────────────────
    def _body_mask(self, bgr: np.ndarray) -> np.ndarray:
        """人体マスクを返す（float32 H×W, 0–1、1=人物）。

        rembg が利用可能な場合は U²-Net で高精度に切り抜く。
        インストールされていない場合は MediaPipe にフォールバックする。
        """
        if _REMBG_AVAILABLE:
            return self._body_mask_rembg(bgr)
        return self._body_mask_mediapipe(bgr)

    def _body_mask_rembg(self, bgr: np.ndarray) -> np.ndarray:
        """rembg (U²-Net) によるマスク生成。

        rembg は RGBA PNG を返すので、アルファチャンネルをそのままマスクに使う。
        U²-Net はすでに人物の細部（髪の毛・指先）を高精度に捉えるため、
        MediaPipe のような後処理補正は最小限にとどめる。
        """
        h, w = bgr.shape[:2]
        session = self._get_rembg_session()

        # BGR → RGB PNG bytes に変換して rembg へ渡す
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        _, enc = cv2.imencode(".png", rgb)
        png_bytes = enc.tobytes()

        # rembg: RGBA PNG を返す（アルファ = 人物マスク、0–255）
        result_bytes = rembg_remove(png_bytes, session=session)
        result_arr   = np.frombuffer(result_bytes, dtype=np.uint8)
        rgba          = cv2.imdecode(result_arr, cv2.IMREAD_UNCHANGED)

        if rgba is None or rgba.shape[2] < 4:
            # デコード失敗時は全面人物扱い
            return np.ones((h, w), np.float32)

        alpha = rgba[:, :, 3].astype(np.float32) / 255.0  # 0–1

        # ── 後処理（最小限） ──────────────────────────────────────
        # ① 小さなノイズ除去（細かい飛び地を消す）
        m8 = (alpha * 255).astype(np.uint8)
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        m8 = cv2.morphologyEx(m8, cv2.MORPH_CLOSE, kernel_close)

        # ② 輪郭ブレンド用の軽いぼかし（ハードエッジを和らげる）
        alpha = cv2.GaussianBlur(m8.astype(np.float32) / 255, (7, 7), 2.0)

        return alpha

    def _body_mask_mediapipe(self, bgr: np.ndarray) -> np.ndarray:
        """MediaPipe SelfieSegmentation によるフォールバック実装。

        rembg が未インストールの場合にのみ呼ばれる。
        """
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        with self._seg_lock:
            res = self._segmenter.process(rgb)
        if res.segmentation_mask is None:
            return np.ones((h, w), np.float32)
        mask = res.segmentation_mask
        if mask.max() < 0.1:
            return np.ones((h, w), np.float32)

        mask = np.clip((mask - 0.3) / 0.35, 0.0, 1.0)
        m8 = (mask * 255).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        m8 = cv2.morphologyEx(m8, cv2.MORPH_CLOSE, kernel)
        return cv2.GaussianBlur(m8.astype(np.float32) / 255, (5, 5), 1.5)

    def replace_background(self, bgr: np.ndarray, bg_color: str) -> np.ndarray:
        """人体マスクを取得し、背景を bg_color（hex）で塗りつぶす。"""
        h, w = bgr.shape[:2]
        mask = self._body_mask(bgr)  # float32 H×W, 0–1（1=人物）

        hc = bg_color.lstrip('#')
        r_val = int(hc[0:2], 16)
        g_val = int(hc[2:4], 16)
        b_val = int(hc[4:6], 16)
        bg = np.empty((h, w, 3), np.float32)
        bg[:, :, 0] = b_val   # BGR
        bg[:, :, 1] = g_val
        bg[:, :, 2] = r_val

        mask3 = mask[:, :, np.newaxis]
        out = bgr.astype(np.float32) * mask3 + bg * (1.0 - mask3)
        return np.clip(out, 0, 255).astype(np.uint8)

    def apply(self, bgr: np.ndarray, params: BeautyParams) -> np.ndarray:
        """
        全21機能を段階的に適用する（静止画レタッチ用）。

        適用順序:
          [色補正・テクスチャ] 肌なめらか → シャープネス →
          明るさ → 色温度 → 美白
          [ランドマーク検出]
          [ワープ変形] 全14ワープ一括
          [色乗算] クマ消し → 歯 → 目反射 →
          チーク → リップ → 涙袋
        """
        out = bgr.copy()

        # 人体マスクを先に計算（美肌・美白で共用）
        body_mask: Optional[np.ndarray] = None
        if params.smoothing_strength > 0 or params.sharpness_strength > 0 or params.whitening_strength > 0:
            body_mask = self._body_mask(bgr)

        # ── ランドマーク不要処理 ──────────────────────────
        if params.smoothing_strength > 0:
            out = smooth_skin(out, params.smoothing_strength, body_mask)
        if params.sharpness_strength > 0:
            out = apply_sharpness(out, params.sharpness_strength, body_mask)
        if params.skin_brightness != 0:
            out = adjust_skin_brightness(out, params.skin_brightness)
        if params.skin_warmth != 0:
            out = apply_tone(out, params.skin_warmth)
        if params.whitening_strength > 0:
            out = whiten_skin(out, params.whitening_strength, body_mask)

        # ── ランドマーク検出 ──────────────────────────────
        lm: Optional[FaceLandmarks] = self._detector.detect(bgr)
        if lm is None:
            return out

        # ── ワープ変形（全14機能を1回の remap） ──────────
        out = apply_all_warps(out, lm, params)

        # ── ランドマーク再検出（ワープ後の位置で色処理） ──
        lm2: Optional[FaceLandmarks] = self._detector.detect(out)
        lm2 = lm2 if lm2 is not None else lm

        if params.dark_circle_strength > 0:
            out = _apply_dark_circle(out, lm2, params)
        if params.teeth_whitening_strength > 0:
            out = whiten_teeth(out, lm2, params.teeth_whitening_strength)
        if params.eye_sparkle_strength > 0:
            out = add_eye_sparkle(out, lm2, params.eye_sparkle_strength)
        if params.cheek_strength > 0:
            out = _apply_cheek(out, lm2, params)
        if params.lip_strength > 0:
            out = _apply_lip(out, lm2, params)
        if params.tear_bag_strength > 0:
            out = _apply_tear_bag(out, lm2, params)

        return out

    def apply_realtime(
        self,
        bgr: np.ndarray,
        smoothing: float = 0.0,
        skin_warmth: float = 0.0,
        face_slim: float = 0.0,
        eye_size: float = 0.0,
    ) -> np.ndarray:
        """
        リアルタイム処理（撮影中 15fps 目標）。
        美肌 / 肌の色 / 顔痩せ / 目のサイズ の軽量版のみ。

        注意: リアルタイム用途では rembg（U²-Net）は重すぎるため、
        美肌処理の body_mask には MediaPipe を直接使用する。
        """
        from .warp import apply_realtime_warps
        out = bgr.copy()

        if smoothing > 0:
            from .smoothing import _skin_mask
            import mediapipe as mp

            smoothed = cv2.bilateralFilter(bgr, 7, 60, 60)
            alpha    = float(smoothing) * 0.7
            mask     = _skin_mask(bgr, blur_ksize=15)

            # リアルタイム用は MediaPipe で body mask を取る
            # （初回のみインスタンス生成）
            if not hasattr(self, '_rt_segmenter'):
                self._rt_segmenter = mp.solutions.selfie_segmentation.SelfieSegmentation(
                    model_selection=1
                )
                self._rt_seg_lock = threading.Lock()
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            with self._rt_seg_lock:
                res = self._rt_segmenter.process(rgb)
            if res.segmentation_mask is not None:
                body = np.clip(
                    (res.segmentation_mask - 0.3) / 0.35, 0.0, 1.0
                )
            else:
                body = np.ones(bgr.shape[:2], np.float32)

            mask = mask * body[:, :, np.newaxis]
            out = (bgr.astype(np.float32) * (1 - mask * alpha)
                   + smoothed.astype(np.float32) * (mask * alpha))
            out = np.clip(out, 0, 255).astype(np.uint8)

        if skin_warmth != 0:
            out = apply_tone(out, skin_warmth)

        if face_slim != 0 or eye_size != 0:
            lm = self._detector.detect(bgr)
            if lm is not None:
                out = apply_realtime_warps(out, lm, face_slim, eye_size)

        return out


# ── シングルトン + base64 ラッパー ────────────────────────────

_pipeline = BeautyPipeline()


def bg_replace_b64(b64_image: str, bg_color: str) -> str:
    """人体マスクで背景を bg_color（hex）で塗りつぶす。"""
    data = base64.b64decode(b64_image)
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return b64_image
    out = _pipeline.replace_background(img, bg_color)
    _, buf = cv2.imencode('.jpg', out, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return base64.b64encode(buf.tobytes()).decode()


def beauty_retouch_b64(b64_image: str, params: BeautyParams) -> str:
    """base64 JPEG/PNG → 処理 → base64 PNG を返す（静止画）。"""
    data = base64.b64decode(b64_image)
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return b64_image
    out = _pipeline.apply(img, params)
    _, buf = cv2.imencode('.png', out)
    return base64.b64encode(buf.tobytes()).decode()


def beauty_realtime_b64(
    b64_image: str,
    smoothing: float = 0.0,
    skin_warmth: float = 0.0,
    face_slim: float = 0.0,
    eye_size: float = 0.0,
) -> str:
    """base64 JPEG → リアルタイム処理 → base64 JPEG を返す。"""
    data = base64.b64decode(b64_image)
    arr  = np.frombuffer(data, dtype=np.uint8)
    img  = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return b64_image
    out = _pipeline.apply_realtime(img, smoothing, skin_warmth, face_slim, eye_size)
    _, buf = cv2.imencode('.jpg', out, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buf.tobytes()).decode()