"""
main.py — FastAPI バックエンドのエントリーポイント

エンドポイント一覧:
  GET  /health                     ヘルスチェック
  POST /api/bg_replace             背景をプリカラーで置換
  POST /api/beauty_retouch         高品質レタッチ（21機能）

起動方法:
  uvicorn main:app --port 8000 --reload
"""

from __future__ import annotations
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from beauty import BeautyParams
from beauty.pipeline import beauty_retouch_b64, bg_replace_b64

# ── ログ設定 ──────────────────────────────────────────────────
# INFO レベル以上のログをコンソールに出力する
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── FastAPI アプリの初期化 ────────────────────────────────────
app = FastAPI(title="Prikura Backend")

# ── CORS（クロスオリジンリソース共有）設定 ──────────────────
# フロントエンド（localhost:5173 等）からの API アクセスを許可する。
# 本番環境では allow_origins を特定ドメインに限定すること。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",        # Docker / nginx（ポート80、明示なし）
        "http://127.0.0.1",
        "http://localhost:5173",   # Vite 開発サーバー（デフォルト）
        "http://localhost:5174",   # 2つ目の Vite インスタンス
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    # ポートあり・なし両方の localhost / 127.0.0.1 を許可（http / https 共通）
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],    # GET / POST / OPTIONS など全て許可
    allow_headers=["*"],    # 任意のリクエストヘッダーを許可
)


# ── エンドポイント定義 ────────────────────────────────────────

@app.get("/health")
async def health():
    """サーバーが正常に動いているか確認するためのエンドポイント。"""
    return {"status": "ok"}


class BgReplaceRequest(BaseModel):
    """POST /api/bg_replace のリクエストボディ。"""
    image:    str
    bg_color: str = "#FFFFFF"


@app.post("/api/bg_replace")
async def bg_replace_endpoint(req: BgReplaceRequest):
    """Selfie Segmentation で背景を指定色に置換する。"""
    result = await asyncio.get_event_loop().run_in_executor(
        None, bg_replace_b64, req.image, req.bg_color
    )
    return {"image": result}


class BeautyRetouchRequest(BaseModel):
    """POST /api/beauty_retouch のリクエストボディ（全21機能）。"""
    image: str
    # 肌・テクスチャ
    smoothing_strength:  float = 0.0
    sharpness_strength:  float = 0.0
    skin_brightness:     float = 0.0
    skin_warmth:         float = 0.0
    whitening_strength:  float = 0.0
    # 顔形
    face_slim_strength:        float = 0.0
    head_size_strength:        float = 0.0
    mid_face_shorten_strength: float = 0.0
    cheek_width_strength:      float = 0.0
    jaw_strength:              float = 0.0
    chin_length_strength:      float = 0.0
    # 鼻
    nose_width_strength:  float = 0.0
    nose_height_strength: float = 0.0
    # 目
    eye_size_strength:     float = 0.0
    eye_position_strength: float = 0.0
    eye_sparkle_strength:  float = 0.0
    iris_size_strength:    float = 0.0
    eye_tilt_strength:     float = 0.0
    dark_circle_strength:  float = 0.0
    # 口
    mouth_size_strength:      float = 0.0
    mouth_corner_strength:    float = 0.0
    philtrum_strength:        float = 0.0
    teeth_whitening_strength: float = 0.0
    # メイクアップ
    cheek_strength: float = 0.0
    cheek_color:    str   = "#FFB7C5"
    lip_strength:   float = 0.0
    lip_color:      str   = "#FF6B9D"
    tear_bag_strength: float = 0.0


@app.post("/api/beauty_retouch")
async def beauty_retouch(req: BeautyRetouchRequest):
    """
    beauty パッケージによる高品質顔加工（全21機能）。
    撮影後の静止画レタッチに使用する。
    """
    params = BeautyParams(
        smoothing_strength=req.smoothing_strength,
        sharpness_strength=req.sharpness_strength,
        skin_brightness=req.skin_brightness,
        skin_warmth=req.skin_warmth,
        whitening_strength=req.whitening_strength,
        face_slim_strength=req.face_slim_strength,
        head_size_strength=req.head_size_strength,
        mid_face_shorten_strength=req.mid_face_shorten_strength,
        cheek_width_strength=req.cheek_width_strength,
        jaw_strength=req.jaw_strength,
        chin_length_strength=req.chin_length_strength,
        nose_width_strength=req.nose_width_strength,
        nose_height_strength=req.nose_height_strength,
        eye_size_strength=req.eye_size_strength,
        eye_position_strength=req.eye_position_strength,
        eye_sparkle_strength=req.eye_sparkle_strength,
        iris_size_strength=req.iris_size_strength,
        eye_tilt_strength=req.eye_tilt_strength,
        dark_circle_strength=req.dark_circle_strength,
        mouth_size_strength=req.mouth_size_strength,
        mouth_corner_strength=req.mouth_corner_strength,
        philtrum_strength=req.philtrum_strength,
        teeth_whitening_strength=req.teeth_whitening_strength,
        cheek_strength=req.cheek_strength,
        cheek_color=req.cheek_color,
        lip_strength=req.lip_strength,
        lip_color=req.lip_color,
        tear_bag_strength=req.tear_bag_strength,
    )
    result = await asyncio.get_event_loop().run_in_executor(
        None, beauty_retouch_b64, req.image, params
    )
    return {"image": result}
