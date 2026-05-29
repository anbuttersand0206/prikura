"""
face_processor.py — 顔加工処理モジュール

MediaPipe Face Mesh（468 点ランドマーク）と OpenCV を組み合わせて
プリクラ風の顔加工（肌補正・目拡大・小顔・リップ・チーク・涙袋）を実装する。

【mediapipe が使えない環境では】
ImportError をキャッチして _MP_AVAILABLE = False にすることで、
MediaPipe が不要な処理（明るさ・色温度の変更など）だけを実行する
グレースフルデグレードを実現している。

【各処理の方式】
  肌の明るさ  : YCrCb 色空間で肌マスクを作り、HSV の V チャンネルを調整
  肌の色温度  : RGB を直接増減（R+ / B-）
  肌なめらか  : YCrCb 肌マスク × bilateralFilter で肌部分のみ平滑化
  目拡大      : 虹彩ランドマーク中心から cv2.remap で拡大変形
  小顔        : 顔の軸（額→顎）から face-local 座標を計算し
                cv2.remap で横・縦を縮小
  チーク      : 頬ランドマーク周辺にぼかしたグラデーション円を描く
  リップ      : 口唇ランドマークで作った多角形マスクに色を乗算合成
  涙袋        : 目の下に楕円形の明るい領域を合成
"""

from __future__ import annotations
import base64
import math
import numpy as np
import cv2
from dataclasses import dataclass
from typing import Tuple

# ── MediaPipe の条件付きインポート ────────────────────────────
# インストールされていない環境でもサーバーが起動できるよう
# try/except でラップする
try:
    import mediapipe as mp
    _MP_AVAILABLE = True
    _mp_face_mesh = mp.solutions.face_mesh
except ImportError:
    _MP_AVAILABLE = False
    _mp_face_mesh = None


# ── レタッチパラメータの定義 ──────────────────────────────────

@dataclass
class RetouchParams:
    """
    顔加工の各パラメータをまとめたデータクラス。
    dataclass を使うと __init__ が自動生成される。
    全てデフォルト値があるので RetouchParams() で「加工なし」状態を作れる。
    """
    skin_brightness: int = 0     # 肌の明るさ (-50〜+50)
    skin_warmth: int = 0         # 肌の色温度 (-50〜+50)
    face_slim: int = 0           # 小顔の強さ (0〜30)
    eye_size: int = 0            # 目の拡大 (0〜30)
    tear_bag: int = 0            # 涙袋 (0〜30)
    lip_color: str = "#FF6B9D"   # リップカラー（16進数）
    lip_strength: int = 0        # リップの強さ (0〜80)
    cheek_color: str = "#FFB7C5" # チークカラー
    cheek_strength: int = 0      # チークの強さ (0〜80)


# ── ユーティリティ関数 ────────────────────────────────────────

def hex_to_bgr(hex_color: str) -> Tuple[int, int, int]:
    """
    CSS の 16進数カラー文字列（例: '#FF85A1'）を
    OpenCV が使う BGR タプルに変換する。

    OpenCV は RGB でなく BGR（Blue→Green→Red）の順なので
    R と B の順序を入れ替える必要がある。
    """
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (b, g, r)  # BGR の順で返す


# ── FaceProcessor クラス ──────────────────────────────────────

class FaceProcessor:
    """
    顔加工処理のメインクラス。
    シングルトンとして使われる（ファイル末尾で _processor = FaceProcessor() ）。
    MediaPipe の FaceMesh インスタンスをキャッシュして効率化する。
    """

    def __init__(self):
        self._mesh = None            # FaceMesh インスタンス
        self._frame_skip = 0         # フレームスキップカウンター（リアルタイム処理用）
        self._last_landmarks = None  # 直前フレームのランドマーク（スキップ時に再利用）

        if _MP_AVAILABLE:
            # FaceMesh を初期化する
            # refine_landmarks=True で目の虹彩（468・473番）も取得できる
            self._mesh = _mp_face_mesh.FaceMesh(
                max_num_faces=1,               # 1人のみ検出（処理高速化）
                refine_landmarks=True,          # 虹彩ランドマーク有効化
                min_detection_confidence=0.5,   # 検出の最低確信度
                min_tracking_confidence=0.5,    # トラッキングの最低確信度
            )

    def process_frame(self, img: np.ndarray, params: RetouchParams) -> np.ndarray:
        """
        カメラのリアルタイムフレーム処理（速度優先）。
        eye_size と face_slim は重いので含めない。

        【フレームスキップの仕組み】
        MediaPipe の検出は GPU がない環境では重い。
        2フレームに1回だけ検出して、スキップしたフレームは
        直前のランドマークを再利用する（帯域削減に加えてここでも負荷軽減）。
        """
        out = img.copy()

        # MediaPipe 不要の処理を先に行う
        if params.skin_brightness != 0:
            out = self._apply_brightness(out, params.skin_brightness)
        if params.skin_warmth != 0:
            out = self._apply_warmth(out, params.skin_warmth)

        if not _MP_AVAILABLE:
            return out  # MediaPipe なしでここで終了

        # 2フレームに1回だけランドマークを検出する
        self._frame_skip += 1
        if self._frame_skip % 2 == 0:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # MediaPipe は RGB で動く
            result = self._mesh.process(rgb)
            if result.multi_face_landmarks:
                self._last_landmarks = result.multi_face_landmarks[0]

        if self._last_landmarks is None:
            return out  # まだランドマークが取れていない

        lm = self._last_landmarks
        h, w = out.shape[:2]

        # ランドマークを使う処理
        if params.cheek_strength > 0:
            out = self._apply_cheek(out, lm, h, w, params)
        if params.lip_strength > 0:
            out = self._apply_lip(out, lm, h, w, params)
        if params.tear_bag > 0:
            out = self._apply_tear_bag(out, lm, h, w, params)

        return out

    def retouch_image(self, img: np.ndarray, params: RetouchParams) -> np.ndarray:
        """
        撮影後写真の高品質レタッチ（品質優先）。
        eye_size / face_slim など全パラメータを適用する。
        リアルタイムより処理に時間がかかるが、1枚処理なので許容される。
        """
        out = img.copy()

        if params.skin_brightness != 0:
            out = self._apply_brightness(out, params.skin_brightness)
        if params.skin_warmth != 0:
            out = self._apply_warmth(out, params.skin_warmth)

        # 肌なめらか処理（bilateralFilter）を追加で適用
        out = self._smooth_skin(out)

        if not _MP_AVAILABLE:
            return out

        # 高品質処理ではスキップなしで毎回ランドマークを取得する
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)
        if not result.multi_face_landmarks:
            return out  # 顔が検出できなければそのまま返す

        lm = result.multi_face_landmarks[0]
        h, w = out.shape[:2]

        # 適用順序: 形状変更（目・顔）→ 色乗算（チーク・リップ・涙袋）
        if params.eye_size > 0:
            out = self._enlarge_eyes(out, lm, h, w, params.eye_size)
        if params.face_slim > 0:
            out = self._slim_face(out, lm, h, w, params.face_slim)
        if params.cheek_strength > 0:
            out = self._apply_cheek(out, lm, h, w, params)
        if params.lip_strength > 0:
            out = self._apply_lip(out, lm, h, w, params)
        if params.tear_bag > 0:
            out = self._apply_tear_bag(out, lm, h, w, params)

        return out

    # ── 肌の明るさ ───────────────────────────────────────────────

    def _apply_brightness(self, img: np.ndarray, value: int) -> np.ndarray:
        """
        肌部分だけを明るく/暗くする。

        【YCrCb 色空間による肌マスクの仕組み】
        YCrCb は輝度（Y）と色差（Cr, Cb）に分離した色空間。
        Cr（赤系）と Cb（青系）の範囲で人肌の色域を絞り込める。
        inRange(Cr: 133〜173, Cb: 77〜127) で肌っぽい色だけを抽出。

        【HSV で明るさを変える理由】
        RGB をそのまま加算すると色相も変わってしまう。
        HSV の V チャンネル（輝度）だけを変えることで
        色味を保ったまま明るさだけを調整できる。
        """
        # 肌マスクを作る（肌領域: 白、それ以外: 黒）
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
        # マスクをぼかして境界を自然にする
        skin_mask = cv2.GaussianBlur(skin_mask, (15, 15), 5)

        # HSV で V チャンネル（明るさ）を変更
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        # 肌部分は 2.2 倍強く、それ以外は 1.0 倍で調整
        v_boost = np.where(skin_mask > 64, value * 2.2, value * 1.0)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] + v_boost, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # ── 肌の色温度 ────────────────────────────────────────────────

    def _apply_warmth(self, img: np.ndarray, value: int) -> np.ndarray:
        """
        色温度を上げる（暖かく）/ 下げる（クールに）。
        value > 0 のとき: 赤チャンネルを上げ、青チャンネルを下げる（暖色方向）
        value < 0 のとき: 逆方向（寒色）
        """
        out = img.astype(np.float32)
        factor = value / 100.0  # -0.5〜+0.5 の範囲に正規化
        out[:, :, 2] = np.clip(out[:, :, 2] + factor * 30, 0, 255)  # R チャンネル
        out[:, :, 0] = np.clip(out[:, :, 0] - factor * 20, 0, 255)  # B チャンネル
        return out.astype(np.uint8)

    # ── 肌なめらか ────────────────────────────────────────────────

    def _smooth_skin(self, img: np.ndarray) -> np.ndarray:
        """
        肌部分のみ bilateralFilter で平滑化する（毛穴・ニキビを目立たなくする）。

        【bilateralFilter の特徴】
        通常のぼかし（GaussianBlur）と違い、
        色の差が大きい境界（輪郭・目・眉など）はぼかさず、
        色の差が小さい領域（肌の平坦部分）のみぼかす。
        これにより輪郭を保ちながら肌だけをすべすべにできる。

        【アルファブレンドで肌マスクを使う理由】
        bilateralFilter を全体に適用すると
        目や口の輪郭もぼけてしまう。
        肌マスクで「なめらか」と「元画像」をブレンドすることで
        肌部分だけを処理できる。
        """
        # 肌マスク（0〜1 の浮動小数点）
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
        skin_mask = cv2.GaussianBlur(skin_mask, (21, 21), 7).astype(np.float32) / 255.0
        skin_mask = skin_mask[:, :, np.newaxis]  # (H, W) → (H, W, 1) でブロードキャスト可能にする

        # bilateralFilter: d=9（近傍半径）, sigmaColor=75, sigmaSpace=75
        smoothed = cv2.bilateralFilter(img, 9, 75, 75)

        # skin_mask の割合でブレンド: mask=1 → なめらか, mask=0 → 元画像
        result = (img.astype(np.float32) * (1 - skin_mask) +
                  smoothed.astype(np.float32) * skin_mask)
        return np.clip(result, 0, 255).astype(np.uint8)

    # ── ランドマーク取得ユーティリティ ────────────────────────────

    def _get_pt(self, lm, idx: int, h: int, w: int) -> Tuple[int, int]:
        """
        ランドマーク idx の座標を整数ピクセル値で返す。
        MediaPipe のランドマーク座標は 0.0〜1.0 の正規化値なので
        幅・高さを掛けてピクセル座標に変換する。
        """
        p = lm.landmark[idx]
        return (int(p.x * w), int(p.y * h))

    def _get_pt_f(self, lm, idx: int, h: int, w: int) -> Tuple[float, float]:
        """_get_pt の浮動小数点版（目の中心計算等の精度が必要な処理に使う）"""
        p = lm.landmark[idx]
        return (p.x * w, p.y * h)

    # ── チーク（頬） ──────────────────────────────────────────────

    def _apply_cheek(self, img: np.ndarray, lm, h: int, w: int, params: RetouchParams) -> np.ndarray:
        """
        頬ランドマーク周辺に放射状のぼかしたカラーを乗算合成する。

        ランドマーク 234: 左頬の外側
        ランドマーク 454: 右頬の外側

        乗算合成（alpha ブレンド）で自然に肌に馴染む。
        強さの上限を 300 で割ることで「最大でも 80/300 ≈ 27% の合成率」に抑える。
        """
        out = img.copy().astype(np.float32)
        bgr = hex_to_bgr(params.cheek_color)
        alpha = params.cheek_strength / 300.0

        for idx in [234, 454]:  # 左右の頬ランドマーク
            cx, cy = self._get_pt(lm, idx, h, w)
            radius = int(w * 0.12)  # 幅の 12% を半径にする

            # 円形のマスク（中心 1.0, 外側 0.0 のグラデーション）を作る
            mask = np.zeros((h, w), dtype=np.float32)
            cv2.circle(mask, (cx, cy), radius, 1.0, -1)  # 塗りつぶし円
            mask = cv2.GaussianBlur(mask, (radius | 1, radius | 1), radius / 3)  # ぼかす

            # 各 BGR チャンネルにアルファブレンドでカラーを乗せる
            for c_idx, c_val in enumerate(bgr):
                out[:, :, c_idx] = out[:, :, c_idx] * (1 - mask * alpha) + c_val * mask * alpha

        return np.clip(out, 0, 255).astype(np.uint8)

    # ── リップ ────────────────────────────────────────────────────

    def _apply_lip(self, img: np.ndarray, lm, h: int, w: int, params: RetouchParams) -> np.ndarray:
        """
        口唇ランドマーク群で多角形マスクを作り、カラーを乗算合成する。

        lip_pts: MediaPipe の口の輪郭ランドマーク番号（上下唇の外側）
        20 点を使って口の形に沿ったマスクを fillPoly で描く。
        GaussianBlur で境界をぼかして自然に馴染ませる。
        """
        out = img.copy().astype(np.float32)
        bgr = hex_to_bgr(params.lip_color)
        alpha = params.lip_strength / 200.0  # 最大 80/200 = 0.4 の合成率

        # 口の輪郭ランドマーク（上唇外側 + 下唇外側の時計回り順）
        lip_pts = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291,
                   375, 321, 405, 314, 17, 84, 181, 91, 146]
        pts = np.array([self._get_pt(lm, i, h, w) for i in lip_pts], dtype=np.int32)

        # 口の多角形マスク
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.fillPoly(mask, [pts], 1.0)
        mask = cv2.GaussianBlur(mask, (15, 15), 5)  # 境界をぼかす

        # リップカラーを乗算合成
        for c_idx, c_val in enumerate(bgr):
            out[:, :, c_idx] = out[:, :, c_idx] * (1 - mask * alpha) + c_val * mask * alpha

        return np.clip(out, 0, 255).astype(np.uint8)

    # ── 涙袋 ─────────────────────────────────────────────────────

    def _apply_tear_bag(self, img: np.ndarray, lm, h: int, w: int, params: RetouchParams) -> np.ndarray:
        """
        目の下に楕円形のハーフムーン（明るい影）を描いて涙袋を作る。

        ランドマークペア:
          (374, 380): 左目の下まぶた
          (145, 153): 右目の下まぶた
        2点の中点の少し下（+h*0.018）に半楕円のマスクを描く。
        塗りつぶし色は肌より少し明るいクリーム白（RGB: 230, 215, 225）。
        """
        out = img.copy().astype(np.float32)
        alpha = params.tear_bag / 150.0

        for idx_pair in [(374, 380), (145, 153)]:
            # 2点の中点を計算
            cx = (self._get_pt(lm, idx_pair[0], h, w)[0] + self._get_pt(lm, idx_pair[1], h, w)[0]) // 2
            cy = (self._get_pt(lm, idx_pair[0], h, w)[1] + self._get_pt(lm, idx_pair[1], h, w)[1]) // 2
            cy_offset = cy + int(h * 0.018)  # 少し下にずらす
            r = int(w * 0.028)  # 楕円の半径

            # 半楕円マスク（0〜180 度 = 下半分の弧）
            mask = np.zeros((h, w), dtype=np.float32)
            cv2.ellipse(mask, (cx, cy_offset), (r, r // 2), 0, 0, 180, 1.0, -1)
            mask = cv2.GaussianBlur(mask, (r | 1, r | 1), r / 3)

            # クリーム白を乗算合成（BGR: 225, 215, 230）
            for c_idx, c_val in enumerate((225, 215, 230)):
                out[:, :, c_idx] = out[:, :, c_idx] * (1 - mask * alpha) + c_val * mask * alpha

        return np.clip(out, 0, 255).astype(np.uint8)

    # ── 目の拡大 ─────────────────────────────────────────────────

    def _enlarge_eyes(self, img: np.ndarray, lm, h: int, w: int, strength: int) -> np.ndarray:
        """
        目の中心（虹彩ランドマーク）を基準にして目の周辺を拡大変形する。

        【cv2.remap によるバックワードマップ変形】
        remap は「出力画像の各ピクセル (dst_x, dst_y) がどこから来るか」を
        マップとして渡す（バックワードマップ）。

        拡大の式:
          src_x = center_x + (dst_x - center_x) / (1 + factor * (scale - 1))
          src_y = center_y + (dst_y - center_y) / (1 + factor * (scale - 1))

        factor は中心からの距離に応じた重み（中心ほど強く拡大, 外側は変形なし）。
        これにより自然な拡大感が生まれる。

        ランドマーク 468: 左目の虹彩中心
        ランドマーク 473: 右目の虹彩中心
        """
        out = img.copy()
        scale = 1.0 + strength * 0.007  # 強さ30 → 1.21倍拡大

        for eye_center_idx in [468, 473]:  # 左目・右目の虹彩中心
            cx_f, cy_f = self._get_pt_f(lm, eye_center_idx, h, w)
            cx, cy = int(cx_f), int(cy_f)
            r = int(w * 0.065)  # 処理する目の周辺領域の半径（幅の 6.5%）

            # 処理する矩形 ROI（Region of Interest）の範囲を計算
            x1, y1 = max(0, cx - r), max(0, cy - r)
            x2, y2 = min(w, cx + r), min(h, cy + r)
            if x2 <= x1 or y2 <= y1:
                continue  # 境界外なら処理しない

            roi = out[y1:y2, x1:x2].astype(np.float32)
            rh, rw = roi.shape[:2]
            local_cx, local_cy = cx_f - x1, cy_f - y1  # ROI 内の中心座標

            # バックワードマップを NumPy の配列演算でベクトル化して計算
            ry_arr, rx_arr = np.mgrid[0:rh, 0:rw].astype(np.float32)
            dx = rx_arr - local_cx
            dy = ry_arr - local_cy
            dist = np.sqrt(dx * dx + dy * dy)

            # 距離に応じた重み: 中心（dist=0）で 1.0, 外周（dist=r）で 0.0
            factor = np.where(dist < r, (1.0 - (dist / r) ** 2), 0.0)

            # バックワードマップの座標（どこから持ってくるか）
            src_x = np.clip(local_cx + dx / (1.0 + factor * (scale - 1.0)), 0, rw - 1)
            src_y = np.clip(local_cy + dy / (1.0 + factor * (scale - 1.0)), 0, rh - 1)

            map_x = src_x.astype(np.float32)
            map_y = src_y.astype(np.float32)

            # remap で変形
            warped = cv2.remap(roi, map_x, map_y, cv2.INTER_LINEAR)
            out[y1:y2, x1:x2] = warped.astype(np.uint8)

        return out

    # ── 小顔（フェイスライン縮小） ────────────────────────────────

    def _slim_face(self, img: np.ndarray, lm, h: int, w: int, strength: int) -> np.ndarray:
        """
        顔の横幅（輪郭）と縦（あご〜頬）を縮める小顔変形。

        【顔ローカル座標系を使う理由】
        顔が斜めを向いていたり傾いていたりしても正しく機能させるため、
        「額→顎」のランドマークから顔の軸を求め、
        画像座標でなく顔に正対した座標系（along_axis / along_perp）で
        処理する。

        【バックワードマップの符号について】
        cv2.remap は「出力ピクセルがどこから来るか」を指定する。
        小顔効果（顎を上に移動させる）には:
          map_y = y + (y - face_cy) * influence * ratio
        のように「元の位置よりも遠い場所（face_cy から離れた方向）から
        サンプル」することで、画面上では顎が上に引き寄せられて見える。

        具体的に:
          along_perp = 0（中心線）から遠いほど width_infl が大きい
          d_perp = along_perp * width_infl * ratio で「中心方向へのずれ」を計算
          map_x = xs + disp_x でサンプル元（バックワード）を指定
          → 出力ピクセルが中心から離れた方向から来るため、輪郭が内側に見える

        【ランドマーク番号】
          10  : 額の中心（forehead）
          152 : 顎の先端（chin）
          234, 454 等: 顎ライン・頬の外側ランドマーク
        """
        if strength == 0:
            return img

        ratio = strength * 0.004   # 強さ30 → ratio = 0.12

        # 顔の軸ベクトルを計算（額→顎の方向）
        fx,  fy  = lm.landmark[10].x  * w, lm.landmark[10].y  * h   # 額
        cfx, cfy = lm.landmark[152].x * w, lm.landmark[152].y * h   # 顎

        # 顔の中心点（額と顎の中点）
        face_cx = (fx + cfx) / 2.0
        face_cy = (fy + cfy) / 2.0

        # 顔軸ベクトルを単位化（ax, ay が「上→下」方向の単位ベクトル）
        ax = cfx - fx;  ay = cfy - fy
        a_len = math.sqrt(ax * ax + ay * ay)
        if a_len < 10:
            return img  # 顔が小さすぎる（検出ミス等）場合はスキップ
        ax /= a_len
        ay /= a_len
        # 顎方向軸を90度回転して横方向の単位ベクトルを得る
        px_u = -ay
        py_u = ax

        # 全ピクセルの座標グリッドを作成（NumPy のベクトル演算で高速化）
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = xs - face_cx
        dy = ys - face_cy

        # 各ピクセルの顔ローカル座標への射影
        along_axis = dx * ax   + dy * ay    # 顎方向成分（正 = 顎側）
        along_perp = dx * px_u + dy * py_u  # 横方向成分（中心線からの距離）

        # ── 横方向の影響マップ（顎ライン・頬ランドマーク） ──────
        jaw_ids = [234, 93, 132, 136, 150, 149, 176, 148, 152,
                   454, 323, 361, 288, 397, 365, 379, 378]
        w_radius = w * 0.13  # 影響半径（幅の 13%）
        width_infl = np.zeros((h, w), np.float32)
        for idx in jaw_ids:
            # ランドマーク位置から face_cx/cy を引いてローカル化
            jx = lm.landmark[idx].x * w - face_cx
            jy = lm.landmark[idx].y * h - face_cy
            dist = np.sqrt((dx - jx) ** 2 + (dy - jy) ** 2)
            # 距離が小さいほど影響が強い（2乗で急激に減衰）
            wt = np.clip(1.0 - dist / w_radius, 0.0, 1.0) ** 2
            np.maximum(width_infl, wt, out=width_infl)  # 複数ランドマークの最大値

        # ── 縦方向の影響マップ（顎ランドマーク、顎方向のみ） ────
        chin_ids = [152, 148, 176, 149, 150, 378, 379, 365, 397]
        h_radius = a_len * 0.35  # 顔の縦幅の 35%
        height_infl = np.zeros((h, w), np.float32)
        for idx in chin_ids:
            jx = lm.landmark[idx].x * w - face_cx
            jy = lm.landmark[idx].y * h - face_cy
            dist = np.sqrt((dx - jx) ** 2 + (dy - jy) ** 2)
            wt = np.clip(1.0 - dist / h_radius, 0.0, 1.0) ** 2
            np.maximum(height_infl, wt, out=height_infl)
        # 顔の中心より下（顎側）だけに縦方向の影響を限定
        height_infl *= (along_axis > 0).astype(np.float32)

        # ── バックワード変位の計算 ────────────────────────────────
        # 横方向: 中心線から遠い方向へサンプル → 輪郭が内側に見える
        d_perp = along_perp * width_infl * ratio
        # 縦方向: 顎方向へサンプル → 顎が上に引き上げられて見える (0.5 倍で弱め)
        d_axis = along_axis * height_infl * ratio * 0.5

        # 顔ローカルの変位を画像座標系に戻す
        disp_x = d_perp * px_u + d_axis * ax
        disp_y = d_perp * py_u + d_axis * ay

        # バックワードマップとして cv2.remap に渡す
        map_x = np.clip(xs + disp_x, 0, w - 1)
        map_y = np.clip(ys + disp_y, 0, h - 1)

        # BORDER_REFLECT_101: 境界付近のピクセルを反射パディングで補完
        return cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REFLECT_101)


# ── シングルトンのプロセッサインスタンス ──────────────────────
# 起動時に1回だけ FaceMesh を初期化してキャッシュする
_processor = FaceProcessor()


# ── 外部公開関数（main.py から呼ばれる） ─────────────────────

def process_frame_b64(b64_image: str, params: RetouchParams) -> str:
    """
    base64 エンコードされた JPEG 画像を受け取って処理し、
    JPEG base64 で返す（リアルタイム処理向け）。

    変換フロー:
      base64 文字列 → バイト列 → NumPy 配列 → OpenCV 画像
      → 処理 → JPEG エンコード → base64 文字列
    """
    data = base64.b64decode(b64_image)
    arr = np.frombuffer(data, dtype=np.uint8)   # バイト列を NumPy 配列に変換
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)   # JPEG デコードして BGR 画像に
    if img is None:
        return b64_image  # デコード失敗時は入力をそのまま返す
    out = _processor.process_frame(img, params)
    _, buf = cv2.imencode('.jpg', out, [cv2.IMWRITE_JPEG_QUALITY, 80])  # 品質80 で JPEG エンコード
    return base64.b64encode(buf.tobytes()).decode()


def retouch_image_b64(b64_image: str, params: RetouchParams) -> str:
    """
    base64 エンコードされた JPEG/PNG 画像を受け取って高品質レタッチし、
    PNG base64 で返す（撮影後の高品質処理向け）。

    PNG で返す理由: JPEG は非可逆圧縮なので、複数回エンコードすると
    画質が劣化する。撮影後の最終処理では PNG で保持する。
    """
    data = base64.b64decode(b64_image)
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return b64_image
    out = _processor.retouch_image(img, params)
    _, buf = cv2.imencode('.png', out)   # 可逆圧縮の PNG でエンコード
    return base64.b64encode(buf.tobytes()).decode()
