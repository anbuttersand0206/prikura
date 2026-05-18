// ============================================================
// pens/group1_effects.ts — グループ1: エフェクト系ペン（5種）
//
// 立体 / カラーネオン / ふわネオン / ネオンふち / ぷるぷる
//
// 【特徴】
// このグループは「重ね描き」と「ぼかしフィルター」を多用して
// 光や質感を表現します。
// ネオンふち だけは OffscreenCanvas + destination-out を使って
// 「中が空洞のリング状」ストロークを実現しています。
// ============================================================

import type { PenConfig, Point } from './index';
import { interpolate } from '../wasm/penEngineLoader';

export const group1Pens: PenConfig[] = [

  // ────────────────────────────────────────────────────────────
  // 立体ペン — 影 + 本体色 + ハイライトの3層で立体感を出す
  // ────────────────────────────────────────────────────────────
  {
    id: 'tridimensional',
    name: '立体',
    group: 1,
    baseSize: 8,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points); // まずなめらかな曲線に変換
      if (smooth.length < 2) return;

      ctx.save(); // 以下の描画設定を他に影響させないよう保存
      ctx.globalAlpha = opacity;
      ctx.lineCap = 'round';    // 線の端を丸くする
      ctx.lineJoin = 'round';   // 折れ曲がり部分も丸くする

      // --- 層1: 影（ドロップシャドウ） ---
      // shadowOffsetX/Y でずらした影を描くことで浮き上がった感じを出す
      ctx.strokeStyle = 'rgba(0,0,0,0.3)'; // 半透明の黒
      ctx.lineWidth = size + 4; // 本体より少し太く
      ctx.shadowColor = 'rgba(0,0,0,0.4)';
      ctx.shadowBlur = 6;
      ctx.shadowOffsetX = 3;
      ctx.shadowOffsetY = 3;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      // 影の設定をリセット（次の層に引き継がないよう）
      ctx.shadowColor = 'transparent';
      ctx.shadowBlur = 0;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 0;

      // --- 層2: 本体色 ---
      ctx.strokeStyle = color;
      ctx.lineWidth = size;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      // --- 層3: ハイライト（左上方向に1pxずらした細い白線） ---
      // 光が左上から当たっているように見せる
      ctx.strokeStyle = 'rgba(255,255,255,0.6)';
      ctx.lineWidth = size * 0.35;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x - 1, smooth[0].y - 1); // 1px ずらす
      smooth.forEach(p => ctx.lineTo(p.x - 1, p.y - 1));
      ctx.stroke();

      ctx.restore(); // 保存した状態に戻す
    },
  },

  // ────────────────────────────────────────────────────────────
  // カラーネオン — ぼかしレイヤーを重ねて光輝く発光感を出す
  // ────────────────────────────────────────────────────────────
  {
    id: 'color_neon',
    name: 'カラーネオン',
    group: 1,
    baseSize: 6,
    color: '#FF85A1',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.globalAlpha = opacity;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // 幅・透明度・ぼかし量を変えた3つのハローレイヤーを描く
      // 外側ほど広くぼかして、ネオンサインのような発光を表現
      const glowLayers = [
        { width: size * 5,   alpha: 0.1 }, // 最も外側: 広くて薄い
        { width: size * 3,   alpha: 0.2 }, // 中間
        { width: size * 1.5, alpha: 0.5 }, // 内側: 狭くてやや濃い
      ];
      for (const layer of glowLayers) {
        ctx.strokeStyle = color;
        ctx.lineWidth = layer.width;
        ctx.globalAlpha = opacity * layer.alpha;
        ctx.filter = `blur(${size * 0.6}px)`; // CSS blur フィルター
        ctx.beginPath();
        ctx.moveTo(smooth[0].x, smooth[0].y);
        smooth.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.stroke();
      }

      // ぼかしをリセットして本体ラインを最前面に描く
      ctx.filter = 'none';
      ctx.globalAlpha = opacity;
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
  // ふわネオン — 広いぼかしで柔らかい発光感、中心線は白く
  // ────────────────────────────────────────────────────────────
  {
    id: 'fuwa_neon',
    name: 'ふわネオン',
    group: 1,
    baseSize: 8,
    color: '#A29BFE',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;
      ctx.save();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // [幅, 透明度, ぼかし量] の3段階グロー
      // カラーネオンより各段の幅が大きく、よりふんわりした印象になる
      for (const [w, a, b] of [
        [size * 8, 0.05, size * 2],   // 最外周: 超広い薄いグロー
        [size * 5, 0.1,  size * 1.5], // 中間
        [size * 2, 0.3,  size * 0.8], // 内側
      ] as [number, number, number][]) {
        ctx.globalAlpha = opacity * a;
        ctx.strokeStyle = color;
        ctx.lineWidth = w;
        ctx.filter = `blur(${b}px)`;
        ctx.beginPath();
        ctx.moveTo(smooth[0].x, smooth[0].y);
        smooth.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.stroke();
      }

      // 中心線を白く細く描いて「光の芯」を表現
      ctx.filter = 'none';
      ctx.globalAlpha = opacity * 0.9;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.lineWidth = size * 0.5;
      ctx.beginPath();
      ctx.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => ctx.lineTo(p.x, p.y));
      ctx.stroke();

      ctx.restore();
    },
  },

  // ────────────────────────────────────────────────────────────
  // ネオンふち — 中が空洞のリング状ストローク
  //
  // 【アルゴリズム】
  // 直接 destination-out を使うと下にある画像まで消えてしまうので、
  // 別の「オフスクリーンキャンバス（見えないキャンバス）」に描いてから
  // 最後にメインキャンバスに合成する手順を踏む。
  //
  //   1. OffscreenCanvas に太いストロークを描く（色付き）
  //   2. destination-out モードで細いストロークを描く
  //      → 太いストロークの内側が消えて「リング」になる
  //   3. メインキャンバスにグロー（ぼかし光）を描く
  //   4. OffscreenCanvas の結果を最前面に合成する
  // ────────────────────────────────────────────────────────────
  {
    id: 'neon_outline',
    name: 'ネオンふち',
    group: 1,
    baseSize: 10,
    color: '#00B894',
    opacity: 1,
    render(ctx, points, size, color, opacity) {
      const smooth = interpolate(points);
      if (smooth.length < 2) return;

      // ── オフスクリーンキャンバスでリング形状を作る ──────────
      // メインキャンバスと同じサイズの「見えない描画バッファ」
      const off = new OffscreenCanvas(ctx.canvas.width, ctx.canvas.height);
      const oc = off.getContext('2d') as OffscreenCanvasRenderingContext2D;
      oc.lineCap = 'round';
      oc.lineJoin = 'round';

      // 外側の輪郭線を描く（ここがリングの「ふち」になる）
      oc.strokeStyle = color;
      oc.lineWidth = size;
      oc.beginPath();
      oc.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => oc.lineTo(p.x, p.y));
      oc.stroke();

      // destination-out: 新しく描いたピクセルが「消しゴム」になる
      // 内側の細い線で外側の線の中央部分を削除 → リング（中空）になる
      oc.globalCompositeOperation = 'destination-out';
      oc.strokeStyle = 'rgba(0,0,0,1)'; // 色は何でもよい（アルファが0になる）
      oc.lineWidth = Math.max(1, size * 0.6); // 外周より細くして「ふち」を残す
      oc.beginPath();
      oc.moveTo(smooth[0].x, smooth[0].y);
      smooth.forEach(p => oc.lineTo(p.x, p.y));
      oc.stroke();

      // ── メインキャンバスにグロー（発光ハロー）を描く ──────
      ctx.save();
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';

      // リングの背後にぼかした光を重ねてネオンらしさを出す
      for (const [lw, alpha, blur] of [
        [size * 4,   0.12, size * 2],   // 最外周グロー
        [size * 2.5, 0.25, size * 1],   // 中間グロー
        [size * 1.5, 0.45, size * 0.4], // 内側グロー
      ] as [number, number, number][]) {
        ctx.globalAlpha = opacity * alpha;
        ctx.strokeStyle = color;
        ctx.lineWidth = lw;
        ctx.filter = `blur(${blur}px)`;
        ctx.beginPath();
        ctx.moveTo(smooth[0].x, smooth[0].y);
        smooth.forEach(p => ctx.lineTo(p.x, p.y));
        ctx.stroke();
      }
      ctx.filter = 'none';

      // ── オフスクリーンのリングを最前面に合成 ────────────────
      ctx.globalAlpha = opacity;
      ctx.drawImage(off, 0, 0); // OffscreenCanvas を丸ごと貼り付ける

      ctx.restore();
    },
  },

];
