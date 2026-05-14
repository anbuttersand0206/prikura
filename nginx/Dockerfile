# ── Stage 1: フロントエンドビルド ────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# package*.json だけ先にコピーして依存関係レイヤーをキャッシュする
COPY frontend/package*.json ./
RUN npm ci

# ソースをコピー
COPY frontend/ ./

# pen_engine.wasm が未ビルドの場合はスタブを生成する。
# Vite のバンドル時に動的 import が解決できないためビルドが失敗するのを防ぐ。
# スタブは即 reject するので、penEngineLoader.ts の try/catch が JS フォールバックに切り替える。
RUN mkdir -p src/wasm && \
    if [ ! -f src/wasm/pen_engine.js ]; then \
      printf 'export default () => Promise.reject(new Error("pen_engine not built"));\n' \
        > src/wasm/pen_engine.js; \
    fi

RUN npm run build

# ── Stage 2: nginx で配信 ─────────────────────────────────────────
FROM nginx:1.27-alpine

RUN apk add --no-cache apache2-utils

# ビルド済みフロントエンドをコピー
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

# フォントファイルを /fonts/ として配信（StampPanel のフォント選択機能で使用）
COPY assets/fonts /usr/share/nginx/html/fonts

# BGM・スタンプを配信
COPY assets/sounds /usr/share/nginx/html/sounds
COPY assets/stamps /usr/share/nginx/html/stamps

# nginx 設定（デフォルトの conf を上書き）
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 起動時に .htpasswd を生成する
COPY nginx/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80
CMD ["/entrypoint.sh"]
