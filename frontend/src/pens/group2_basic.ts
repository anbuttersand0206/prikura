// ============================================================
// pens/group2_basic.ts — グループ2: ベーシック系ペン（5種）
//
// ノーマル / ほそ / 白ふち / 黒ふち / ゆる
//
// 【特徴】
// 特殊な合成は使わず、Canvas の標準的な描画 API だけで実装している
// シンプルなペン群です。「ふち」系は2回描き（背景色 → 本体色の順）で
// 輪郭線を表現します。
// ============================================================

import type { PenConfig, Point } from './index';
import { interpolate } from '../wasm/penEngineLoader';

export const group2Pens: PenConfig[] = [

  // ────────────────────────────────────────────────────────────
  // ノーマル — 最もシンプルな普通の線
  // ────────────────────────────────────────────────────────────
  {
    id: 'normal',
    name: 'ノーマル',
    group: 2,
    baseSize: 6,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points); // なめらかな曲線に変換
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
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
  // ほそ — ノーマルの細い版。size * 0.4 に縮小する
  // ────────────────────────────────────────────────────────────
  {
    id: 'thin',
    name: 'ほそ',
    group: 2,
    baseSize: 2,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, size * 0.4); // 最小1pxを保証
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
  // 白ふち — 白い輪郭線 + 本体色を2回描きで実現
  //
  // 描画順序が重要:
  //   1. 白ライン（size + 4 で太め）を先に描く ← 下に来る
  //   2. 本体色ライン（size）を上に描く ← 白がはみ出て「ふち」になる
  // ────────────────────────────────────────────────────────────
  {
    id: 'white_border',
    name: '白ふち',
    group: 2,
    baseSize: 8,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // 先に白いふち（太め）を描く
      ctx.strokeStyle = 'white';
      ctx.lineWidth = size + 4; // 本体より 4px 太くしてふちをはみ出させる
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      // 本体色を上から描く（白ふちが外側にはみ出た状態になる）
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // 黒ふち — 白ふちと同じ方式、ふちの色が黒になる
  // ────────────────────────────────────────────────────────────
  {
    id: 'black_border',
    name: '黒ふち',
    group: 2,
    baseSize: 8,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // 黒いふちを先に描く
      ctx.strokeStyle = '#111111';
      ctx.lineWidth = size + 4;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      // 本体色を上に描く
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // ゆる — tension=0.8 の高張力スプライン + 二次ベジェ曲線
  //        でゆるゆるとした手書き感を出す
  //
  // 【quadraticCurveTo とは】
  // 制御点1つを使った二次ベジェ曲線。
  // 隣り合う2点の中点を「目標点」、元の点を「制御点」にすることで
  // 角ばらずなめらかに折れ曲がる曲線を描く。
  // ────────────────────────────────────────────────────────────
  {
    id: 'yuru',
    name: 'ゆる',
    group: 2,
    baseSize: 6,
    color: '#A29BFE',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      // tension を 0.8 にすることでより角張った曲線になる（ゆるっとした感じ）
      const smooth = interpolate(points, 0.8);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);

      // 隣り合う点の中点を目標点、smooth[i] を制御点として二次ベジェを描く
      // これにより各区間が丸くつながる
      for (let i = 1; i < smooth.length - 1; i++) {
        const mx = (smooth[i].x + smooth[i + 1].x) / 2; // 中点 X
        const my = (smooth[i].y + smooth[i + 1].y) / 2; // 中点 Y
        ctx.quadraticCurveTo(smooth[i].x, smooth[i].y, mx, my);
      }
      // 最後の点だけは直線でつなぐ
      ctx.lineTo(smooth[smooth.length - 1].x, smooth[smooth.length - 1].y);
      ctx.stroke();
      ctx.restore();
    },
  },
];
