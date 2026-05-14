<script lang="ts">
  // ============================================================
  // PenPalette.svelte — ペン選択パネル
  //
  // 20種のペン一覧・カラーパレット・サイズ・不透明度スライダーを
  // 表示する左サイドパネルのコンポーネント。
  //
  // 親（Edit.svelte）の selectedPenId / penColor / penSize /
  // penOpacity を $bindable() で双方向バインドしている。
  // 子コンポーネント内で値を変えると親にも反映される。
  // ============================================================

  import { group1Pens } from '../pens/group1_effects';
  import { group2Pens } from '../pens/group2_basic';
  import { group3Pens } from '../pens/group3_texture';
  import { group4Pens } from '../pens/group4_transparent';
  import { PALETTE_COLORS } from '../pens/index';
  import type { PenConfig } from '../pens/index';

  // ── props ────────────────────────────────────────────────────
  // $bindable() を使うと親の変数と双方向同期する（Svelte 5 の新機能）
  let {
    selectedPenId = $bindable('normal'),  // 選択中ペン ID
    penColor      = $bindable('#FF85A1'), // 選択中カラー
    penSize       = $bindable(8),         // サイズ（px）
    penOpacity    = $bindable(1),         // 不透明度（0.0〜1.0）
    onSelectPen,  // ペンが選択されたときに呼ばれるコールバック（省略可）
  }: {
    selectedPenId?: string;
    penColor?: string;
    penSize?: number;
    penOpacity?: number;
    onSelectPen?: (pen: PenConfig) => void;
  } = $props();

  // ノーマルを先頭に、残りをグループ順で並べた配列
  const normal = group2Pens.find(p => p.id === 'normal')!;
  const allPens: PenConfig[] = [
    normal,
    ...group2Pens.filter(p => p.id !== 'normal'),
    ...group1Pens,
    ...group3Pens,
    ...group4Pens,
  ];

  /**
   * ペンを選択したときの処理。
   * selectedPenId を更新して、コールバックがあれば呼ぶ。
   */
  function select(pen: PenConfig) {
    selectedPenId = pen.id;
    onSelectPen?.(pen); // ?. は「関数が渡されていれば呼ぶ」という省略記法
  }

  // ペングループのラベル（現状は表示に使っていないが将来のため残す）
  const groupLabels = ['エフェクト', 'ベーシック', '質感', '透明・ぼかし'];

  // ── プレビューキャンバス ──────────────────────────────────────
  const PW = 60, PH = 26; // プレビューキャンバスのサイズ（px）

  // S字カーブ: 左から右へ波打つサンプル点（右端に余白を確保してグロー系がはみ出ないようにする）
  const PREVIEW_PTS = [
    {x: 4,  y: 20}, {x: 10, y: 9},  {x: 18, y: 19},
    {x: 27, y: 8},  {x: 36, y: 18}, {x: 44, y: 9}, {x: 50, y: 16},
  ];

  let previewCanvases: (HTMLCanvasElement | null)[] = allPens.map(() => null);

  function renderPreviews() {
    allPens.forEach((pen, i) => {
      const canvas = previewCanvases[i];
      if (!canvas) return;
      const ctx = canvas.getContext('2d')!;
      ctx.clearRect(0, 0, PW, PH);
      const sz = Math.min(pen.baseSize, 7);
      try {
        pen.render(ctx, PREVIEW_PTS, sz, penColor, pen.opacity);
      } catch (_) { /* フォールバックは無描画 */ }
    });
  }

  // $effect はルーンなのでインポート不要。
  // マウント後に実行され、penColor（renderPreviews 内で参照）が変わるたびに再実行される。
  $effect(() => {
    renderPreviews();
  });
</script>

<div class="pen-palette">
  <div class="palette-title">ペンを選ぶ</div>

  <!-- 3列×5行のペングリッド（全15種） -->
  <div class="pen-grid">
    {#each allPens as pen, i}
      <button
        class="pen-cell"
        class:active={selectedPenId === pen.id}
        onclick={() => select(pen)}
        title={pen.name}
      >
        <!-- 実際の render() 関数で描いたキャンバスプレビュー -->
        <div class="pen-preview">
          <canvas
            bind:this={previewCanvases[i]}
            width={PW}
            height={PH}
            class="pen-preview-canvas"
          ></canvas>
        </div>
        <span class="pen-name">{pen.name}</span>
      </button>
    {/each}
  </div>

  <!-- カラーパレット（24色） -->
  <div class="palette-section">
    <div class="section-label">カラー</div>
    <div class="color-grid">
      {#each PALETTE_COLORS as c}
        <button
          class="color-dot"
          class:selected={penColor === c}
          style="background: {c}; {c === '#FFFFFF' ? 'border: 2px solid #ccc;' : ''}"
          aria-label={c}
          onclick={() => { penColor = c; }}
        ></button>
      {/each}
    </div>
  </div>

  <!-- サイズスライダー -->
  <div class="palette-section">
    <div class="section-label">サイズ <span class="slider-val">{penSize}px</span></div>
    <input type="range" min="1" max="30" bind:value={penSize} class="slider" />
  </div>

  <!-- 不透明度スライダー -->
  <div class="palette-section">
    <div class="section-label">透明度 <span class="slider-val">{Math.round(penOpacity * 100)}%</span></div>
    <input type="range" min="0.1" max="1" step="0.05" bind:value={penOpacity} class="slider" />
  </div>
</div>

<style>
  .pen-palette {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    overflow-y: auto;
    max-height: 100%;
  }

  .palette-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: #C060A0;
    text-align: center;
    padding: 4px 0;
    border-bottom: 2px solid #FFE0F0;
  }

  .pen-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
  }

  .pen-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 5px 3px;
    border-radius: 10px;
    border: 2px solid transparent;
    background: #FFF8FC;
    cursor: pointer;
    transition: all 0.15s;
  }
  .pen-cell:hover {
    background: #FFE8F4;
    border-color: #F0A0C0;
  }
  .pen-cell.active {
    background: linear-gradient(135deg, rgba(240,160,192,0.2), rgba(212,160,240,0.2));
    border-color: #F0A0C0;
    box-shadow: 0 2px 8px rgba(240,160,192,0.3);
  }

  .pen-preview {
    width: 60px;
    height: 26px;
    overflow: hidden;
    border-radius: 4px;
    background: #fff;
  }
  .pen-preview-canvas {
    display: block;
  }

  .pen-name {
    font-size: 0.55rem;
    color: #888;
    white-space: nowrap;
    font-weight: 600;
  }
  .pen-cell.active .pen-name {
    color: #C060A0;
  }

  .palette-section {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .section-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #C060A0;
    display: flex;
    justify-content: space-between;
  }
  .slider-val {
    color: #888;
    font-weight: 400;
  }

  .color-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 4px;
  }

  .color-dot {
    aspect-ratio: 1;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: all 0.15s;
    padding: 0;
    min-width: 0;
  }
  .color-dot:hover {
    transform: scale(1.15);
  }
  .color-dot.selected {
    border-color: #F0A0C0;
    box-shadow: 0 0 0 2px rgba(240,160,192,0.5);
    transform: scale(1.1);
  }

  .slider {
    -webkit-appearance: none;
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(to right, #F0A0C0, #D4A0F0);
    outline: none;
  }
  .slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: white;
    border: 2px solid #F0A0C0;
    cursor: pointer;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  }
</style>
