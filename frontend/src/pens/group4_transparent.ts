// ============================================================
// pens/group4_transparent.ts — グループ4: 透明・ぼかし系ペン（5種）
//
// 半透明 / 半透明ふち / なかぬり / 半透明なかぬり / ぼかし
//
// 【特徴】
// このグループの目玉は「中が空洞のストローク（なかぬり系）」です。
// Canvas の destination-out 合成を使って内側を消す技法を
// drawHollowStroke() に共通化しています。
//
// 【OffscreenCanvas を使う理由】
// destination-out をメインキャンバスで直接使うと、
// 下のレイヤー（写真など）まで消えてしまう。
// 別のバッファ（OffscreenCanvas）で完成させてから
// メインに貼り付けることで、他の描画に影響しない。
// ============================================================

import type { PenConfig } from './index';
import { interpolate } from '../wasm/penEngineLoader';

// ── ペン定義 ──────────────────────────────────────────────────

export const group4Pens: PenConfig[] = [

  // ────────────────────────────────────────────────────────────
  // 半透明 — globalAlpha を 0.5 に下げるだけのシンプル実装
  //          下の絵が透けて見えるマーカーのような見た目
  // ────────────────────────────────────────────────────────────
  {
    id: 'semi_trans',
    name: '半透明',
    group: 4,
    baseSize: 8,
    color: '#FF85A1',
    opacity: 0.5,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = 0.5 * opacity; // ユーザーの不透明度設定をさらに半分に
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // 半透明ふち — 中は半透明、ふちだけ不透明のリングストローク
  //
  // 【ネストした OffscreenCanvas の理由】
  // ぴったり重なる2つのレイヤー（半透明塗り + 不透明ふち）を
  // 独立させる必要があるため、さらにもう1枚 OffscreenCanvas を使う:
  //   off  = 最終合成先（半透明の塗りを持つ）
  //   off2 = ふちのリング（不透明）
  // off2 を off に drawImage → off をメインに drawImage する。
  // ────────────────────────────────────────────────────────────
  {
    id: 'semi_trans_border',
    name: '半透明ふち',
    group: 4,
    baseSize: 10,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;

      // 中間バッファ: 半透明塗り
      const off = new OffscreenCanvas(ctx.canvas.width, ctx.canvas.height);
      const oc = off.getContext('2d') as OffscreenCanvasRenderingContext2D;
      oc.lineCap = 'round';
      oc.lineJoin = 'round';

      // 中の半透明塗りを描く（外径と同じ太さで 40% の不透明度）
      oc.globalAlpha = 0.4;
      oc.strokeStyle = color;
      oc.lineWidth = size;
      oc.beginPath();
      oc.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => oc.lineTo(p.x, p.y));
      oc.stroke();

      // ふちのリングを別の OffscreenCanvas で作る
      const off2 = new OffscreenCanvas(ctx.canvas.width, ctx.canvas.height);
      const oc2 = off2.getContext('2d') as OffscreenCanvasRenderingContext2D;
      oc2.lineCap = 'round';
      oc2.lineJoin = 'round';

      // 外側の太いストローク（不透明）
      oc2.strokeStyle = color;
      oc2.lineWidth = size + 5; // 中の塗りより少し太め → ふちがはみ出る
      oc2.beginPath();
      oc2.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => oc2.lineTo(p.x, p.y));
      oc2.stroke();

      // destination-out で内側を削除 → 不透明なリング（ふち）になる
      oc2.globalCompositeOperation = 'destination-out';
      oc2.lineWidth = size - 2; // 内側を少し小さめに削除してふちの幅を確保
      oc2.beginPath();
      oc2.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => oc2.lineTo(p.x, p.y));
      oc2.stroke();

      // ふちリングを中間バッファに貼る
      oc.drawImage(off2, 0, 0);

      // 最終的にメインキャンバスに合成
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.drawImage(off, 0, 0);
      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // ぼかし — CSS の blur フィルターで輪郭をぼかして水彩のような印象に
  // ────────────────────────────────────────────────────────────
  {
    id: 'blur_pen',
    name: 'ぼかし',
    group: 4,
    baseSize: 12,
    color: '#FF85A1',
    opacity: 0.8,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      // size に比例したぼかし量（最小 2px）でぼわっとした線にする
      ctx.filter = `blur(${Math.max(2, size * 0.4)}px)`;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();
      ctx.filter = 'none'; // 次の描画に影響しないようリセット
      ctx.restore();
    },
  },
];
