"""
warp.py — 顔変形処理（ラジアル変位場 + cv2.remap）

全ワープ操作を1つの変位場に蓄積して1回の remap で適用することで
補間劣化を最小化する。

【後退写像 (backward mapping) の符号規則】
  cv2.remap は「出力ピクセル (x,y) がどこから来るか」を指定する。
  _WarpField.push(cx, cy, radius, fx, fy) では
    (fx, fy) = 特徴点の順方向変位（正→右/下）
    内部では dx -= wt*fx として後退写像に変換する。

  検証:
    鼻が x=100 にある。x=95 に移動させたい (fx=-5)。
    dx -= wt*(-5)  →  dx = +5 が x=100 近傍に設定される。
    出力 x=95 の画素は map_x = 95 + 5 = 100 を参照 ✓

【スケール変形】
  scale_region(cx, cy, r, s):
    source_x = cx + (dest_x - cx) / s
    disp = source - dest = (dest-cx)*(1/s - 1)
  s>1 → 拡大、s<1 → 縮小。
"""

from __future__ import annotations
import math
import numpy as np
import cv2

from .landmarks import FaceLandmarks

# ── MediaPipe Face Mesh ランドマーク定数 ──────────────────────────
# refine_landmarks=True で 478点（虹彩 468–477 含む）

_L_EYE_OUTER   = 33
_L_EYE_INNER   = 133
_L_EYE_TOP     = 159
_L_EYE_BOT     = 145
_L_EYE_OUTER_T = 130   # 外側上まぶた
_L_IRIS        = 468   # 左虹彩中心
_L_IRIS_TOP    = 469
_L_IRIS_RIGHT  = 470
_L_IRIS_BOT    = 471
_L_IRIS_LEFT   = 472

_R_EYE_OUTER   = 263
_R_EYE_INNER   = 362
_R_EYE_TOP     = 386
_R_EYE_BOT     = 374
_R_EYE_OUTER_T = 359
_R_IRIS        = 473
_R_IRIS_TOP    = 474
_R_IRIS_RIGHT  = 475
_R_IRIS_BOT    = 476
_R_IRIS_LEFT   = 477

_NOSE_TIP      = 4
_NOSE_BRIDGE   = 6
_NOSE_BOT      = 2
_L_NOSTRIL     = 129   # 左小鼻外側
_R_NOSTRIL     = 358   # 右小鼻外側

_MOUTH_L       = 61
_MOUTH_R       = 291
_UPPER_LIP     = 0    # 上唇外側中央（鼻下）
_LOWER_LIP     = 17   # 下唇外側中央

_CHIN          = 152
_FOREHEAD      = 10

# 顎ライン（左右）
_L_JAW = [234, 93, 132, 136, 150, 149, 176, 148]
_R_JAW = [454, 323, 361, 288, 397, 365, 379, 377]
# 頬外側
_L_CHEEK_OUTER = [234, 93]
_R_CHEEK_OUTER = [454, 323]
# エラ（顎角部）
_L_JAW_ANGLE   = [136, 172, 150]
_R_JAW_ANGLE   = [365, 397, 379]


# ── _WarpField ────────────────────────────────────────────────

class _WarpField:
    """全ワープ操作を蓄積し1回の cv2.remap で適用する。"""

    def __init__(self, h: int, w: int) -> None:
        self.h, self.w = h, w
        ys, xs = np.mgrid[0:h, 0:w]
        self._xs = xs.astype(np.float32)
        self._ys = ys.astype(np.float32)
        self._dx = np.zeros((h, w), np.float32)
        self._dy = np.zeros((h, w), np.float32)

    def push(
        self,
        cx: float, cy: float,
        radius: float,
        fx: float, fy: float,
        power: float = 2.0,
    ) -> None:
        """
        (cx,cy) にある特徴点を順方向 (fx,fy) だけ移動させる。
        power が大きいほど境界が鋭くなる。
        """
        r = max(radius, 1.0)
        dx = self._xs - cx
        dy = self._ys - cy
        dist = np.sqrt(dx * dx + dy * dy)
        wt = np.clip(1.0 - (dist / r) ** power, 0.0, 1.0)
        self._dx -= wt * fx
        self._dy -= wt * fy

    def scale_region(
        self,
        cx: float, cy: float,
        radius: float,
        scale: float,
        power: float = 2.0,
    ) -> None:
        """
        (cx,cy) を中心に scale 倍拡縮する。
        scale>1 → 拡大、scale<1 → 縮小。
        """
        r = max(radius, 1.0)
        dx = self._xs - cx
        dy = self._ys - cy
        dist = np.sqrt(dx * dx + dy * dy)
        wt = np.clip(1.0 - (dist / r) ** power, 0.0, 1.0)
        inv_s = 1.0 / max(scale, 0.01)
        self._dx += wt * dx * (inv_s - 1.0)
        self._dy += wt * dy * (inv_s - 1.0)

    def translate_region(
        self,
        cx: float, cy: float,
        inner_r: float,
        outer_r: float,
        fx: float, fy: float,
    ) -> None:
        """
        inner_r 以内を (fx, fy) だけ均等平行移動し、
        inner_r → outer_r 間をコサイン補間でフォールオフさせる。
        push() と異なり内側は wt=1（全ピクセル同量）なので形が歪まない。
        """
        dx = self._xs - cx
        dy = self._ys - cy
        dist = np.sqrt(dx * dx + dy * dy)
        t  = np.clip((dist - inner_r) / max(outer_r - inner_r, 1.0), 0.0, 1.0)
        wt = (0.5 * (1.0 + np.cos(np.pi * t))).astype(np.float32)
        self._dx -= wt * fx
        self._dy -= wt * fy

    def compress_lower_face(
        self,
        anchor_y: float,
        bottom_y: float,
        max_shift_y: float,
        face_cx: float,
        face_half_w: float,
    ) -> None:
        """
        anchor_y〜bottom_y の範囲を目側（上）へ線形圧縮する。
        anchor_y のピクセルは動かさず、bottom_y ほど max_shift_y ぶん上へシフトする。
        水平方向は face_cx を中心に face_half_w で滑らかにフォールオフする。
        """
        lower_h = max(bottom_y - anchor_y, 1.0)
        # 縦: anchor_y より下にいるほど 0→1 で線形増加
        vert_wt = np.clip(
            (self._ys - anchor_y) / lower_h, 0.0, 1.0
        ).astype(np.float32)
        # 横: 顔中心ほど強く、外に向かって 2 次でフォールオフ
        horiz_wt = np.clip(
            1.0 - ((self._xs - face_cx) / max(face_half_w, 1.0)) ** 2,
            0.0, 1.0,
        ).astype(np.float32)
        self._dy -= vert_wt * horiz_wt * float(max_shift_y)

    def apply(self, bgr: np.ndarray) -> np.ndarray:
        map_x = np.clip(self._xs + self._dx, 0.0, float(self.w - 1))
        map_y = np.clip(self._ys + self._dy, 0.0, float(self.h - 1))
        return cv2.remap(
            bgr, map_x, map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )


# ── 参照寸法ヘルパー ──────────────────────────────────────────

def _face_metrics(lm: FaceLandmarks):
    """顔の基準寸法（中心座標・顔高・目間距離）を返す。"""
    fx, fy   = lm.ptf(_FOREHEAD)
    cx_c, cy_c = lm.ptf(_CHIN)
    face_h   = math.sqrt((fx - cx_c) ** 2 + (fy - cy_c) ** 2)
    face_cx  = (fx + cx_c) / 2.0
    face_cy  = (fy + cy_c) / 2.0
    eye_w    = abs(lm.ptf(_L_EYE_OUTER)[0] - lm.ptf(_R_EYE_OUTER)[0])
    return face_cx, face_cy, face_h, eye_w


# ── 個別ワープ操作（_WarpField に変位を加算） ──────────────────

def _add_face_slim(field: _WarpField, lm: FaceLandmarks,
                   face_cx: float, face_h: float, strength: float) -> None:
    """顎・頬ラインを縦軸（face_cx）に向かって内側へ寄せる。"""
    ratio = float(np.clip(strength, -1.0, 1.0)) * 0.12
    for idx in _L_JAW + _R_JAW:
        px, py = lm.ptf(idx)
        dx = px - face_cx
        r  = face_h * 0.22
        field.push(px, py, r, dx * ratio, 0.0, power=2.0)


def _add_head_size(field: _WarpField, lm: FaceLandmarks,
                   face_cx: float, face_cy: float, face_h: float,
                   strength: float) -> None:
    """顔全体を中心から拡縮する（頭サイズ）。"""
    scale = 1.0 + float(np.clip(strength, -1.0, 1.0)) * 0.10
    field.scale_region(face_cx, face_cy, face_h * 1.3, scale, power=1.5)


def _add_nose_width(field: _WarpField, lm: FaceLandmarks,
                    strength: float) -> None:
    """小鼻外側ランドマークを鼻中心軸へ移動（鼻幅）。"""
    ratio = float(np.clip(strength, -1.0, 1.0)) * 0.4
    nose_cx = lm.ptf(_NOSE_TIP)[0]
    nl_x, nl_y = lm.ptf(_L_NOSTRIL)
    nr_x, nr_y = lm.ptf(_R_NOSTRIL)
    r = abs(nl_x - nr_x) * 0.45
    field.push(nl_x, nl_y, r, (nl_x - nose_cx) * ratio, 0.0)
    field.push(nr_x, nr_y, r, (nr_x - nose_cx) * ratio, 0.0)


def _add_nose_height(field: _WarpField, lm: FaceLandmarks,
                     face_h: float, strength: float) -> None:
    """鼻先を上（短縮）/ 下（伸長）へ移動（鼻縦幅）。"""
    ratio  = float(np.clip(strength, -1.0, 1.0)) * 0.12
    tip_x, tip_y    = lm.ptf(_NOSE_TIP)
    bridge_y        = lm.ptf(_NOSE_BRIDGE)[1]
    nose_h          = tip_y - bridge_y
    r               = abs(nose_h) * 0.9
    field.push(tip_x, tip_y, r, 0.0, nose_h * ratio)


def _add_eye_size(field: _WarpField, lm: FaceLandmarks,
                  eye_w: float, strength: float) -> None:
    """目全体を虹彩中心から拡縮（目のサイズ）。"""
    scale = 1.0 + float(np.clip(strength, -1.0, 1.0)) * 0.22
    r = eye_w * 0.18
    for iris in [_L_IRIS, _R_IRIS]:
        cx, cy = lm.ptf(iris)
        field.scale_region(cx, cy, r, scale)


def _add_eye_position(field: _WarpField, lm: FaceLandmarks,
                      face_h: float, strength: float) -> None:
    """目を上（正）/ 下（負）へ平行移動。目の形は変えずに周囲の肌を馴染ませる。
    translate_region で目の全ピクセルを同量移動させることで歪みを防ぐ。"""
    if strength == 0.0:
        return
    # 正 = おでこ側（上）= image座標 y が減る → fy は負
    fy = -float(np.clip(strength, -1.0, 1.0)) * face_h * 0.04

    for outer, inner, top, bot in [
        (_L_EYE_OUTER, _L_EYE_INNER, _L_EYE_TOP, _L_EYE_BOT),
        (_R_EYE_OUTER, _R_EYE_INNER, _R_EYE_TOP, _R_EYE_BOT),
    ]:
        ox, _  = lm.ptf(outer)
        ix, _  = lm.ptf(inner)
        _, ty  = lm.ptf(top)
        _, by  = lm.ptf(bot)
        cx     = (lm.ptf(outer)[0] + lm.ptf(inner)[0]) / 2.0
        cy     = (ty + by) / 2.0

        eye_half_w = abs(ox - ix) / 2.0
        eye_half_h = abs(by - ty) / 2.0
        # 目全体（まぶた含む）を囲む内側半径
        inner_r = math.sqrt(eye_half_w ** 2 + eye_half_h ** 2) * 1.2
        # 周囲の肌が馴染む遷移帯
        outer_r = inner_r + face_h * 0.12

        field.translate_region(cx, cy, inner_r, outer_r, 0.0, fy)


def _add_iris_size(field: _WarpField, lm: FaceLandmarks,
                   strength: float) -> None:
    """虹彩のみを拡縮（黒目サイズ）。"""
    scale = 1.0 + float(np.clip(strength, -1.0, 1.0)) * 0.28
    for iris, top in [(_L_IRIS, _L_IRIS_TOP), (_R_IRIS, _R_IRIS_TOP)]:
        cx, cy   = lm.ptf(iris)
        _, top_y = lm.ptf(top)
        r = abs(cy - top_y) * 1.6
        field.scale_region(cx, cy, r, scale)


def _add_eye_tilt(field: _WarpField, lm: FaceLandmarks,
                  eye_w: float, strength: float) -> None:
    """
    外目尻を上（つり目・正）/ 下（タレ目・負）へ移動。
    内目尻はアンカー（固定）。
    """
    shift_y = float(np.clip(strength, -1.0, 1.0)) * eye_w * 0.025
    r_outer = eye_w * 0.10
    r_inner = eye_w * 0.06

    for outer, inner in [(_L_EYE_OUTER, _L_EYE_INNER),
                          (_R_EYE_OUTER, _R_EYE_INNER)]:
        ox, oy = lm.ptf(outer)
        ix, iy = lm.ptf(inner)
        field.push(ox, oy, r_outer, 0.0, -shift_y)   # 外側を動かす
        field.push(ix, iy, r_inner, 0.0,  0.0)        # 内側は固定アンカー


def _add_chin_length(field: _WarpField, lm: FaceLandmarks,
                     face_h: float, strength: float) -> None:
    """顎先を下（伸長）/ 上（短縮）へ移動（顎縦幅）。"""
    shift_y = float(np.clip(strength, -1.0, 1.0)) * face_h * 0.07
    cx, cy  = lm.ptf(_CHIN)
    r       = face_h * 0.22
    field.push(cx, cy, r, 0.0, shift_y)


def _add_mid_face_shorten(field: _WarpField, lm: FaceLandmarks,
                          face_cx: float, face_h: float, strength: float) -> None:
    """
    目下端をアンカーとし、顎先に向かって線形に上方向シフトを強める。
    鼻・口・顎が目側へ詰まり、縦方向に下顔面全体が短縮して見える。
    strength > 0 = 短縮（顎が上がる）、< 0 = 伸長。
    """
    if strength == 0.0:
        return

    ratio     = float(np.clip(strength, -1.0, 1.0)) * 0.13
    eye_bot_y = (lm.ptf(_L_EYE_BOT)[1] + lm.ptf(_R_EYE_BOT)[1]) / 2.0
    chin_y    = lm.ptf(_CHIN)[1]
    lower_h   = max(chin_y - eye_bot_y, 1.0)

    field.compress_lower_face(
        anchor_y    = eye_bot_y,
        bottom_y    = chin_y,
        max_shift_y = lower_h * ratio,   # 顎先での最大上方向シフト
        face_cx     = face_cx,
        face_half_w = face_h * 0.42,     # 顔幅に合わせた水平フォールオフ半径
    )


def _add_cheek_width(field: _WarpField, lm: FaceLandmarks,
                     face_cx: float, face_h: float, strength: float) -> None:
    """頬骨外側のみを拡縮（頬横幅）。"""
    ratio = float(np.clip(strength, -1.0, 1.0)) * 0.15
    r = face_h * 0.20
    for idx in [234, 93, 123, 454, 323, 352]:
        px, py = lm.ptf(idx)
        dx = px - face_cx
        field.push(px, py, r, dx * ratio, 0.0)


def _add_jaw(field: _WarpField, lm: FaceLandmarks,
             face_cx: float, strength: float) -> None:
    """顎角部（エラ）を縦軸へ向かって削る（エラ削り）。"""
    ratio = float(np.clip(strength, -1.0, 1.0)) * 0.20
    for idx in _L_JAW_ANGLE + _R_JAW_ANGLE:
        px, py = lm.ptf(idx)
        dx = px - face_cx
        r  = abs(dx) * 0.9 + 10.0
        field.push(px, py, r, dx * ratio, 0.0)


def _add_mouth_size(field: _WarpField, lm: FaceLandmarks,
                    strength: float) -> None:
    """口全体を拡縮（口のサイズ）。strength > 0 = 大きく、< 0 = 小さく。"""
    scale = 1.0 + float(np.clip(strength, -1.0, 1.0)) * 0.28
    mx_l, _  = lm.ptf(_MOUTH_L)
    mx_r, _  = lm.ptf(_MOUTH_R)
    _, uy    = lm.ptf(_UPPER_LIP)
    _, ly    = lm.ptf(_LOWER_LIP)
    cx = (mx_l + mx_r) / 2.0
    cy = (uy + ly) / 2.0
    r  = abs(mx_l - mx_r) * 0.75
    field.scale_region(cx, cy, r, scale)


def _add_mouth_corners(field: _WarpField, lm: FaceLandmarks,
                       eye_w: float, strength: float) -> None:
    """口角を上（正）/ 下（負）へ移動（口角）。"""
    shift_y = float(np.clip(strength, -1.0, 1.0)) * eye_w * 0.018
    r = eye_w * 0.08
    for corner in [_MOUTH_L, _MOUTH_R]:
        cx, cy = lm.ptf(corner)
        field.push(cx, cy, r, 0.0, -shift_y)


def _add_mouth_position(field: _WarpField, lm: FaceLandmarks,
                        face_h: float, strength: float) -> None:
    """口を上（正）/ 下（負）へ平行移動。口の形は変えずに周囲の肌を馴染ませる。"""
    if strength == 0.0:
        return
    # 正 = 鼻側（上）= image座標 y 減少 → fy 負
    fy = -float(np.clip(strength, -1.0, 1.0)) * face_h * 0.04

    mx_l, _  = lm.ptf(_MOUTH_L)
    mx_r, _  = lm.ptf(_MOUTH_R)
    _, uy    = lm.ptf(_UPPER_LIP)
    _, ly    = lm.ptf(_LOWER_LIP)

    cx = (mx_l + mx_r) / 2.0
    cy = (uy + ly) / 2.0

    mouth_half_w = abs(mx_l - mx_r) / 2.0
    mouth_half_h = abs(uy - ly) / 2.0
    inner_r = math.sqrt(mouth_half_w ** 2 + mouth_half_h ** 2) * 1.2
    outer_r = inner_r + face_h * 0.12

    field.translate_region(cx, cy, inner_r, outer_r, 0.0, fy)


# ── 公開 API ─────────────────────────────────────────────────

def apply_all_warps(bgr: np.ndarray, lm: FaceLandmarks, params) -> np.ndarray:
    """
    BeautyParams の全ワープ項目を1回の remap で適用する。

    適用順序（変位場への加算順）:
      頭サイズ → 顔痩せ → 頬横幅 → エラ →
      顎縦幅 → 中顔面短縮 → 鼻幅 → 鼻縦 → 目サイズ → 目位置 →
      黒目 → つり目 → 口角 → 人中
    """
    h, w = bgr.shape[:2]
    face_cx, face_cy, face_h, eye_w = _face_metrics(lm)
    field = _WarpField(h, w)

    if params.head_size_strength:
        _add_head_size(field, lm, face_cx, face_cy, face_h,
                       params.head_size_strength)
    if params.face_slim_strength:
        _add_face_slim(field, lm, face_cx, face_h, params.face_slim_strength)
    if params.cheek_width_strength:
        _add_cheek_width(field, lm, face_cx, face_h, params.cheek_width_strength)
    if params.jaw_strength:
        _add_jaw(field, lm, face_cx, params.jaw_strength)
    if params.chin_length_strength:
        _add_chin_length(field, lm, face_h, params.chin_length_strength)
    if params.mid_face_shorten_strength:
        _add_mid_face_shorten(field, lm, face_cx, face_h, params.mid_face_shorten_strength)

    if params.nose_width_strength:
        _add_nose_width(field, lm, params.nose_width_strength)
    if params.nose_height_strength:
        _add_nose_height(field, lm, face_h, params.nose_height_strength)

    if params.eye_size_strength:
        _add_eye_size(field, lm, eye_w, params.eye_size_strength)
    if params.eye_position_strength:
        _add_eye_position(field, lm, face_h, params.eye_position_strength)
    if params.iris_size_strength:
        _add_iris_size(field, lm, params.iris_size_strength)
    if params.eye_tilt_strength:
        _add_eye_tilt(field, lm, eye_w, params.eye_tilt_strength)

    if params.mouth_size_strength:
        _add_mouth_size(field, lm, params.mouth_size_strength)
    if params.mouth_corner_strength:
        _add_mouth_corners(field, lm, eye_w, params.mouth_corner_strength)
    if params.philtrum_strength:
        _add_mouth_position(field, lm, face_h, params.philtrum_strength)

    return field.apply(bgr)


# ── リアルタイム軽量版 ────────────────────────────────────────

def apply_realtime_warps(bgr: np.ndarray, lm: FaceLandmarks,
                         face_slim: float, eye_size: float) -> np.ndarray:
    """
    撮影中のリアルタイム処理用。顔痩せ・目のサイズのみ適用。
    フルパスより大幅に軽い（2操作のみ）。
    """
    if face_slim == 0.0 and eye_size == 0.0:
        return bgr
    h, w = bgr.shape[:2]
    face_cx, face_cy, face_h, eye_w = _face_metrics(lm)
    field = _WarpField(h, w)
    if face_slim:
        _add_face_slim(field, lm, face_cx, face_h, face_slim)
    if eye_size:
        _add_eye_size(field, lm, eye_w, eye_size)
    return field.apply(bgr)
