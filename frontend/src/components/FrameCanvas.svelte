<script lang="ts">
  // ============================================================
  // FrameCanvas.svelte — フレーム + 写真の描画キャンバス
  //
  // このコンポーネントは2つの役割を持つ:
  //   1. 写真（または背景色）の上にフレームの枠線・装飾を重ねて表示
  //   2. compositeToCanvas() で全レイヤーを合成した Canvas を返す
  //
  // Edit.svelte の「レイヤー4（フレームオーバーレイ）」として使われる。
  // ============================================================

  import { onMount } from 'svelte';
  import type { FrameDesign } from '../stores/appState';

  // ── props ────────────────────────────────────────────────────
  let {
    width = 480,          // 表示幅（px）
    height = 360,         // 表示高さ（px）
    frame,               // フレームデザイン設定（色・アクセント色・装飾種別）
    photoDataUrl = '',    // 写真の base64 URL。空なら背景色で塗りつぶす
    bgColor = '#FFD6E0',  // 写真がないときの背景色
  }: {
    width?: number;
    height?: number;
    frame: FrameDesign;
    photoDataUrl?: string;
    bgColor?: string;
  } = $props();

  let canvasEl: HTMLCanvasElement;

  // props が変わるたびに自動で再描画する（Svelte 5 の $effect）
  $effect(() => {
    if (canvasEl) draw();
  });

  onMount(() => {
    draw(); // 初回マウント時に描画
  });

  /**
   * キャンバスを描画する。
   * 写真がある場合は Image オブジェクトに読み込んでから
   * フレームオーバーレイを重ねる（非同期 onload を使う）。
   */
  export function draw() {
    if (!canvasEl) return;
    const ctx = canvasEl.getContext('2d')!;
    ctx.clearRect(0, 0, width, height);

    if (photoDataUrl) {
      // 写真の読み込みは非同期なので onload コールバック内で描画
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, width, height);
        drawFrameOverlay(ctx); // 写真の上にフレームを重ねる
      };
      img.src = photoDataUrl;
    } else {
      // 写真なし → 背景色で塗りつぶしてフレームを描く
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, width, height);
      drawFrameOverlay(ctx);
    }
  }

  /**
   * フレームの枠線・角装飾・上下の装飾文字を描く。
   *
   * 【構成】
   *   - 4辺の帯（bw px 幅）: フレームの主色で塗りつぶす
   *   - 内側の細い矩形: アクセント色でストローク
   *   - 四隅: ♥★♥★ の文字
   *   - 上辺・下辺: ♥★♡☆✿❀ の繰り返し文字列
   */
  function drawFrameOverlay(ctx: CanvasRenderingContext2D) {
    // フレーム帯の太さ（幅の 4% 以上、最低 12px）
    const bw = Math.max(12, Math.round(width * 0.04));
    const f = frame;

    // 4辺の帯を主色で塗りつぶす
    ctx.fillStyle = f.color;
    ctx.fillRect(0, 0, width, bw);              // 上辺
    ctx.fillRect(0, height - bw, width, bw);    // 下辺
    ctx.fillRect(0, 0, bw, height);             // 左辺
    ctx.fillRect(width - bw, 0, bw, height);    // 右辺

    // 内側に細い矩形ライン（アクセント色）
    ctx.strokeStyle = f.accent;
    ctx.lineWidth = 2;
    const inset = bw + 4; // 帯の内側から 4px 余白を取る
    ctx.strokeRect(inset, inset, width - inset * 2, height - inset * 2);

    // 四隅の装飾文字
    const corners: [number, number, number][] = [
      [inset - 4, inset - 4, 0],
      [width - inset + 4, inset - 4, 0],
      [inset - 4, height - inset + 4, 0],
      [width - inset + 4, height - inset + 4, 0],
    ];
    ctx.fillStyle = f.accent;
    ctx.font = `${bw * 0.8}px "M PLUS Rounded 1c"`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const deco = ['♥', '★', '♥', '★'];
    corners.forEach(([x, y], i) => {
      ctx.fillText(deco[i], x, y);
    });

    // 上辺・下辺に等間隔で装飾文字を並べる
    ctx.font = `${bw * 0.75}px "M PLUS Rounded 1c"`;
    const symbols = ['♥', '★', '♡', '☆', '✿', '❀'];
    const count = 5; // 1辺に並べる数
    for (let i = 0; i < count; i++) {
      const x = inset + (width - inset * 2) / (count + 1) * (i + 1);
      ctx.fillText(symbols[i % symbols.length], x, bw / 2);            // 上辺
      ctx.fillText(symbols[i % symbols.length], x, height - bw / 2);   // 下辺
    }
  }

  /** この Canvas 要素を返す（外部からの参照用） */
  export function getCanvas(): HTMLCanvasElement {
    return canvasEl;
  }

  /**
   * 写真 + 落書き + スタンプ + フレームを1枚の Canvas に合成して返す。
   * ※ 現在の実装では写真と落書きのみ合成（スタンプは Edit.svelte 側で処理）。
   *
   * @param drawingCanvas - 落書きレイヤーの Canvas
   * @param stampImages   - スタンプの情報配列（現在は未使用、将来拡張用）
   */
  export function compositeToCanvas(
    drawingCanvas: HTMLCanvasElement,
    stampImages: Array<{ dataUrl: string; x: number; y: number; size: number }>,
  ): HTMLCanvasElement {
    const out = document.createElement('canvas');
    out.width = width;
    out.height = height;
    const ctx = out.getContext('2d')!;

    ctx.drawImage(canvasEl, 0, 0);       // この Canvas（写真+フレーム）を貼る
    ctx.drawImage(drawingCanvas, 0, 0);  // 落書きレイヤーを重ねる

    return out;
  }
</script>

<canvas bind:this={canvasEl} {width} {height}></canvas>
