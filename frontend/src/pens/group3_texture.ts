// ============================================================
// pens/group3_texture.ts — グループ3: 質感系ペン（5種）
//
// 白ネオン / 黒ネオン / ぷっくり / ぷっくりカゲ / クレヨン
//
// 【特徴】
// ネオン系はグループ1のカラーネオンと似た方式ですが
// 色が固定（白 or 黒）です。
// ぷっくり系は白いハイライト線を上に重ねることで
// 丸みのある立体感を出します。
// クレヨンは複数の微妙にずれたレイヤーと
// 点描ノイズで紙の上で擦ったような質感を再現します。
// ============================================================

import type { PenConfig, Point } from './index';
import { catmullRom } from './index';

// ── 決定論的ハッシュ関数 ─────────────────────────────────────
/**
 * 任意の数値シードから 0〜1 の擬似乱数を返す。
 * Math.random() と違い、同じシードを渡せば必ず同じ値が返る。
 *
 * 【なぜ Math.random() ではダメか】
 * Math.random() はリドロー（Undo→再描画）するたびに
 * 異なる値を返してしまい、クレヨンの質感がちらつく。
 * このハッシュ関数を使うと「同じ筆跡 = 同じ質感」になる。
 *
 * 係数（127.1, 311.7, 43758.5453）はノイズ生成でよく使われる
 * 定番の魔法数。これにより小数部がよく分散する。
 */
function sr(seed: number): number {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x); // 小数部だけ取り出して 0〜1 にする
}

export const group3Pens: PenConfig[] = [

  // ────────────────────────────────────────────────────────────
  // ぷっくり — 上にハイライト線を重ねてぷっくりした立体感
  //            ぷっくりカゲより単純（影なし）
  // ────────────────────────────────────────────────────────────
  {
    id: 'pukkuri',
    name: 'ぷっくり',
    group: 3,
    baseSize: 10,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = catmullRom(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // 本体ライン
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      // ハイライト（左上に 0.2 * size ずらした細い白線）
      // 光が左上から当たって表面が丸く光っているイメージ
      ctx.strokeStyle = 'rgba(255,255,255,0.7)';
      ctx.lineWidth = size * 0.3; // 本体の 30%の細さ
      ctx.beginPath();
      ctx.moveTo(smooth[0].x - size * 0.2, smooth[0].y - size * 0.2);
      smooth.forEach(p => ctx.lineTo(p.x - size * 0.2, p.y - size * 0.2));
      ctx.stroke();

      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // ぷっくりカゲ — ぷっくり + 下方向に影を追加して立体感を強調
  //
  // 描画順:
  //   1. 暗い影（右下方向にずれた太い半透明線）
  //   2. 本体色
  //   3. ハイライト（左上にずれた白線）
  // ────────────────────────────────────────────────────────────
  {
    id: 'pukkuri_shadow',
    name: 'ぷっくりカゲ',
    group: 3,
    baseSize: 10,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = catmullRom(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // 影（右下方向にずらして太い暗い線を描く）
      ctx.strokeStyle = 'rgba(0,0,0,0.25)';
      ctx.lineWidth = size + 4;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x + size * 0.1, smooth[0].y + size * 0.3); // 右下にオフセット
      smooth.forEach(p => ctx.lineTo(p.x + size * 0.1, p.y + size * 0.3));
      ctx.stroke();

      // 本体色
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      // ハイライト（左上にずれた白線）
      ctx.strokeStyle = 'rgba(255,255,255,0.65)';
      ctx.lineWidth = size * 0.3;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x - size * 0.15, smooth[0].y - size * 0.2);
      smooth.forEach(p => ctx.lineTo(p.x - size * 0.15, p.y - size * 0.2));
      ctx.stroke();

      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // クレヨン — 複数のずれたレイヤー + ランダムな点描で
  //            実際のクレヨンで紙に描いたような質感を再現する
  //
  // 【仕組み】
  //   1. 少しずつ幅・位置がずれた半透明ストロークを3層描く
  //      → クレヨンがムラになって塗られた感じ
  //   2. 点列の各点近くにランダムな小さい円を散らす（点描）
  //      → 紙の凹凸にインクが乗ったようなザラザラ感
  //
  // 全てのランダムに sr()（決定論的ハッシュ）を使うことで
  // Undo しても質感が変わらない。
  // ────────────────────────────────────────────────────────────
  {
    id: 'crayon',
    name: 'クレヨン',
    group: 3,
    baseSize: 12,
    color: '#FF85A1',
    opacity: 0.85,
    render(ctx, points, size, color, opacity) {
      const smooth = catmullRom(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // --- 3層のずれたストロークでクレヨンの塗りムラを表現 ---
      for (let layer = 0; layer < 3; layer++) {
        ctx.globalAlpha = opacity * 0.4; // 半透明で重ねる
        ctx.strokeStyle = color;
        // sr() でレイヤーごとに少し違う幅にする（±25%程度のぶれ）
        ctx.lineWidth = size + (sr(layer * 7.1) - 0.5) * size * 0.5;
        ctx.beginPath();
        ctx.moveTo(smooth[0].x, smooth[0].y);
        smooth.forEach((p, pi) => ctx.lineTo(
          // 各点の位置もわずかにずらす（±0.75px 程度）
          p.x + (sr(layer * 100 + pi * 3.1) - 0.5) * 1.5,
          p.y + (sr(layer * 200 + pi * 3.7) - 0.5) * 1.5,
        ));
        ctx.stroke();
      }

      // --- 点描ノイズ: 紙の凹凸によるザラザラ感 ---
      // 2点おきに処理して描画負荷を抑える
      for (let i = 0; i < smooth.length; i += 2) {
        for (let n = 0; n < 3; n++) {
          const seed = i * 31 + n * 7; // 点ごとに一意なシード
          const ox = (sr(seed + 1) - 0.5) * size;    // X 方向のオフセット
          const oy = (sr(seed + 2) - 0.5) * size;    // Y 方向のオフセット
          const r  = sr(seed + 3) * size * 0.3;       // 円の半径（最大 size*30%）

          // 白と本体色の小円をランダムに混在させて紙の凹凸感を出す
          ctx.globalAlpha = opacity * (0.05 + sr(seed + 4) * 0.15);
          ctx.fillStyle = sr(seed + 5) > 0.5 ? 'white' : color;
          ctx.beginPath();
          ctx.arc(smooth[i].x + ox, smooth[i].y + oy, r, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.restore();
    },
  },
];
