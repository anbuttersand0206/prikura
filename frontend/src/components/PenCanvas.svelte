<script lang="ts">
  // ============================================================
  // PenCanvas.svelte — 落書き描画キャンバス
  //
  // マウス/タッチ操作を受け取って Canvas に描画する。
  // Undo（元に戻す）のためにスナップショット（ImageData）を保存する。
  // 外部から getCanvas() / getImageData() / putImageData() /
  // clearSilent() / clear() / undo() を呼べる（export 関数）。
  // ============================================================

  import { onMount, onDestroy } from 'svelte';
  import { group1Pens } from '../pens/group1_effects';
  import { group2Pens } from '../pens/group2_basic';
  import { group3Pens } from '../pens/group3_texture';
  import { group4Pens } from '../pens/group4_transparent';
  import type { PenConfig, Point } from '../pens/index';
  import { initPenEngine } from '../wasm/penEngineLoader';

  // ── props（外から受け取る設定値） ────────────────────────────
  let {
    width = 600,           // キャンバスの幅（px）
    height = 800,          // キャンバスの高さ（px）
    selectedPenId = 'normal', // 現在選択中のペン ID
    penColor = '#FF85A1',  // 現在のペン色
    penSize = 8,           // 現在のサイズ
    penOpacity = 1,        // 現在の不透明度
    isEraser = false,      // true なら消しゴムモード
    disabled = false,      // true なら一切描画を受け付けない
  }: {
    width?: number;
    height?: number;
    selectedPenId?: string;
    penColor?: string;
    penSize?: number;
    penOpacity?: number;
    isEraser?: boolean;
    disabled?: boolean;
  } = $props();

  // ── ペンの一覧マップ ─────────────────────────────────────────
  // 全グループのペンを1つの配列に結合し、ID→ペン設定のマップを作る
  const allPens: PenConfig[] = [...group1Pens, ...group2Pens, ...group3Pens, ...group4Pens];
  const penMap = new Map(allPens.map(p => [p.id, p]));

  // ── 内部状態 ─────────────────────────────────────────────────
  let canvasEl: HTMLCanvasElement;    // Canvas DOM 要素への参照
  let isDrawing = false;              // 現在描画中かどうか
  let currentPoints: Point[] = [];   // 今のストロークの座標列（描画途中に溜まる）

  const MAX_UNDO = 20; // Undo 履歴の最大保存数（これを超えると古い方から削除）
  let undoStack: ImageData[] = [];   // Undo 用スナップショットのスタック（後入れ先出し）

  // ── 外部公開関数 ─────────────────────────────────────────────

  /** キャンバス要素を返す（Edit.svelte の合成処理で使う） */
  export function getCanvas(): HTMLCanvasElement {
    return canvasEl;
  }

  /**
   * 現在の描画内容を ImageData として返す。
   * フレームを切り替えるとき、今の描画を保存するために呼ぶ。
   */
  export function getImageData(): ImageData {
    return canvasEl.getContext('2d')!.getImageData(0, 0, canvasEl.width, canvasEl.height);
  }

  /**
   * 保存した ImageData を復元する。
   * フレームを切り替えて戻ってきたとき、保存した描画を再表示するために呼ぶ。
   */
  export function putImageData(data: ImageData) {
    canvasEl.getContext('2d')!.putImageData(data, 0, 0);
  }

  /**
   * Undo 履歴を残さずにキャンバスを消去する。
   * フレーム切り替え時に使う（ユーザーの意図しない Undo を防ぐため）。
   */
  export function clearSilent() {
    canvasEl.getContext('2d')!.clearRect(0, 0, canvasEl.width, canvasEl.height);
    undoStack = []; // Undo 履歴もリセット
  }

  /**
   * Undo 可能な消去。消す前のスナップショットを保存してから消去する。
   * ツールバーの「全消し」ボタンから呼ぶ。
   */
  export function clear() {
    const ctx = canvasEl.getContext('2d')!;
    saveUndo(); // 消す前に保存
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
  }

  /**
   * 1手前の状態に戻す（Undo）。
   * スタックから最新のスナップショットを取り出して復元する。
   */
  export function undo() {
    if (undoStack.length === 0) return; // 履歴がなければ何もしない
    const ctx = canvasEl.getContext('2d')!;
    const prev = undoStack.pop()!; // スタックの一番上（最新）を取り出す
    ctx.putImageData(prev, 0, 0);
  }

  // ── 内部関数 ─────────────────────────────────────────────────

  /**
   * 現在のキャンバスの状態を Undo スタックに保存する。
   * ストローク開始前に呼ぶことで、描き始める前の状態を保持する。
   * MAX_UNDO を超えた場合は最も古いスナップショットを削除する。
   */
  function saveUndo() {
    const ctx = canvasEl.getContext('2d')!;
    undoStack.push(ctx.getImageData(0, 0, canvasEl.width, canvasEl.height));
    if (undoStack.length > MAX_UNDO) undoStack.shift(); // 古いものを削除
  }

  /**
   * マウス/タッチイベントから Canvas 内の座標を計算して返す。
   *
   * 【なぜ scaleX/scaleY が必要か】
   * Canvas の内部解像度（width/height 属性）と
   * 表示サイズ（CSS の width/height）が異なる場合、
   * クリック座標をそのまま使うとズレる。
   * getBoundingClientRect() で表示サイズを取得して比率を計算する。
   */
  function getPos(e: MouseEvent | TouchEvent): Point {
    const rect = canvasEl.getBoundingClientRect();
    const scaleX = canvasEl.width / rect.width;
    const scaleY = canvasEl.height / rect.height;
    if (e instanceof TouchEvent) {
      const t = e.touches[0]; // タッチは最初の1点のみ使う
      return { x: (t.clientX - rect.left) * scaleX, y: (t.clientY - rect.top) * scaleY };
    }
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  }

  /**
   * 描画開始（mousedown / touchstart）。
   * Undo 用スナップショットを保存してから描画フラグをセット。
   */
  function startDraw(e: MouseEvent | TouchEvent) {
    if (disabled) return;
    e.preventDefault();
    saveUndo();
    isDrawing = true;
    currentPoints = [getPos(e)];
  }

  /**
   * 描画中（mousemove / touchmove）。
   *
   * 【消しゴムモード】
   * destination-out 合成で、なぞった部分のピクセルを透明にする。
   *
   * 【ペンモードのリドロー最適化】
   * 3点以上溜まったら Undo スナップショットからリドローする。
   * これにより「ストロークの途中経過」が正しく表示され、
   * 1ストロークを最終状態で決定できる（ジグザグな途中状態が残らない）。
   */
  function moveDraw(e: MouseEvent | TouchEvent) {
    e.preventDefault();
    if (!isDrawing) return;
    currentPoints.push(getPos(e));

    const ctx = canvasEl.getContext('2d')!;

    // ── 消しゴム処理 ──────────────────────────────────────────
    if (isEraser) {
      const p = currentPoints[currentPoints.length - 1];
      ctx.save();
      ctx.globalCompositeOperation = 'destination-out'; // 描く → 透明にする
      ctx.beginPath();
      ctx.arc(p.x, p.y, penSize * 1.5, 0, Math.PI * 2); // 円形の消しゴム
      ctx.fillStyle = 'rgba(0,0,0,1)';
      ctx.fill();
      ctx.restore();
      return;
    }

    // ── ペン描画処理 ──────────────────────────────────────────
    const pen = penMap.get(selectedPenId);
    if (!pen || currentPoints.length < 2) return;

    // 3点以上のとき: スナップショットに戻してから全点を再描画する
    // （こうしないとストロークが塗り重なってドンドン太くなる問題が起きる）
    if (currentPoints.length > 3) {
      const snapshot = undoStack[undoStack.length - 1];
      if (snapshot) {
        ctx.putImageData(snapshot, 0, 0); // 描き始め前の状態に戻す
      }
      pen.render(ctx, currentPoints, penSize, penColor, penOpacity);
    } else {
      pen.render(ctx, currentPoints, penSize, penColor, penOpacity);
    }
  }

  /**
   * 描画終了（mouseup / touchend / mouseleave）。
   * 最終的な点列でもう一度描画して確定させる。
   */
  function endDraw(e: MouseEvent | TouchEvent) {
    if (!isDrawing) return;
    isDrawing = false;

    if (currentPoints.length >= 2 && !isEraser) {
      const ctx = canvasEl.getContext('2d')!;
      // スナップショットに戻してから最終描画（moveDraw の最後と同じ処理）
      const snapshot = undoStack[undoStack.length - 1];
      if (snapshot) ctx.putImageData(snapshot, 0, 0);
      const pen = penMap.get(selectedPenId);
      pen?.render(ctx, currentPoints, penSize, penColor, penOpacity);
    }
    currentPoints = []; // 次のストロークに備えてリセット
  }

  // ── マウント時の初期化 ────────────────────────────────────────
  onMount(() => {
    // Wasm ペンエンジンを先読み（fire-and-forget）
    // ロード完了後は interpolate() が自動的に Wasm 版に切り替わる
    initPenEngine();

    // Ctrl+Z / Cmd+Z でキーボードから Undo できるようにする
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener('keydown', handler);
    // コンポーネントが破棄されるときにイベントリスナーを解除（メモリリーク防止）
    return () => window.removeEventListener('keydown', handler);
  });
</script>

<!-- Canvas 要素本体 -->
<!-- touch-action:none → ブラウザのスワイプ/ピンチ操作を無効にして描画を優先 -->
<!-- cursor: 消しゴム時は cell（＋印）、通常は crosshair（十字）-->
<canvas
  bind:this={canvasEl}
  {width}
  {height}
  style="touch-action: none; cursor: {disabled ? 'default' : isEraser ? 'cell' : 'crosshair'};"
  onmousedown={startDraw}
  onmousemove={moveDraw}
  onmouseup={endDraw}
  onmouseleave={endDraw}
  ontouchstart={startDraw}
  ontouchmove={moveDraw}
  ontouchend={endDraw}
></canvas>
