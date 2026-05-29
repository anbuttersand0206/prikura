"""beauty/ — 顔加工パイプラインパッケージ。

main.py は BeautyParams（リクエストの型）と
beauty_retouch_b64 / bg_replace_b64（処理関数）だけを使う。
内部モジュール（smoothing, warp 等）は直接 import しない。
"""

from .pipeline import BeautyParams, BeautyPipeline

__all__ = ["BeautyParams", "BeautyPipeline"]
