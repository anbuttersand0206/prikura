<script lang="ts">
  // ============================================================
  // Camera.svelte — 撮影画面（Phase 2）
  //
  // Webカメラのライブ映像を Canvas にミラー表示しながら、
  // 設定した枚数だけ自動インターバル撮影を行う。
  //
  // 【処理の大きな流れ】
  //   1. カメラ起動
  //   2. drawLoop() で毎フレーム Canvas をミラー表示（requestAnimationFrame）
  //   3. カウントダウン後に shoot() で Canvas を JPEG キャプチャして保存
  //   4. 設定枚数に達したら Edit 画面に遷移
  // ============================================================

  import { onMount, onDestroy, tick } from 'svelte';
  import { get } from 'svelte/store';
  import { gsap } from 'gsap';
  import { appState } from '../stores/appState';
  import { bgmEnabled, tryPlay } from '../stores/bgmStore';
  import { ArrowLeft, Music } from 'lucide-svelte';

  let bgm: HTMLAudioElement | null = null;
  let bgmCleanup = () => {};
  $: if (bgm) { $bgmEnabled ? bgm.play().catch(() => {}) : bgm.pause(); }

  let state = $appState;
  $: state = $appState;

  // ── DOM 要素への参照 ─────────────────────────────────────────
  let videoEl: HTMLVideoElement;   // カメラ映像を受け取る非表示 <video>
  let canvasEl: HTMLCanvasElement; // 実際に表示する Canvas
  let stream: MediaStream | null = null; // カメラのメディアストリーム
  let animFrame: number;                 // requestAnimationFrame の ID

  // ── UI 状態 ──────────────────────────────────────────────────
  let countdown = 0;             // カウントダウン残り秒数（3→2→1→撮影）
  let intervalTimer = 0;         // 次の撮影まで何秒か（3秒固定）
  let isIntervalPhase = false;   // インターバル待機中か
  let shotDone = false;          // 撮影完了フラッシュ用
  let flashActive = false;       // シャッター時の白フラッシュ
  let countdownEl: HTMLSpanElement | null = null; // カウントダウン数字の DOM

  const INTERVAL_SEC  = 3; // 撮影間隔（秒）
  const COUNTDOWN_SEC = 3; // カウントダウン開始秒数

  // リアクティブ宣言（store の値に依存して自動更新）
  $: capturedCount = state.capturedFrames.length; // 撮影済み枚数
  $: totalCount = state.shootCount;               // 目標枚数
  $: allDone = capturedCount >= totalCount;        // 全枚撮影完了か

  // ── マウント時の初期化 ────────────────────────────────────────
  onMount(async () => {
    bgm = new Audio('/sounds/bpm150.mp3');
    bgm.loop = true;
    bgm.volume = 0.35;
    if (get(bgmEnabled)) bgmCleanup = tryPlay(bgm);
    await startCamera();
    if (!allDone) scheduleNextShot(); // まだ枚数が足りなければ撮影スケジュールを開始
  });

  // ── 破棄時のクリーンアップ ────────────────────────────────────
  onDestroy(() => {
    bgmCleanup();
    bgm?.pause();
    bgm = null;
    stopCamera();
    clearAllTimers();
  });

  // ── カメラ起動 ────────────────────────────────────────────────
  /**
   * getUserMedia でカメラを起動し、映像を videoEl に流し込む。
   * メタデータが読み込まれたら canvas のサイズを合わせて drawLoop を開始。
   */
  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: 'user' },
        audio: false,
      });
      videoEl.srcObject = stream;

      await new Promise<void>(res => {
        videoEl.onloadedmetadata = () => {
          canvasEl.width  = videoEl.videoWidth  || 1280;
          canvasEl.height = videoEl.videoHeight || 720;
          res();
        };
      });

      await videoEl.play();
      drawLoop();
    } catch (e) {
      console.error('Camera error:', e);
    }
  }

  /** カメラとアニメーションを停止する */
  function stopCamera() {
    if (stream) stream.getTracks().forEach(t => t.stop());
    cancelAnimationFrame(animFrame);
  }

  // ── 描画ループ ────────────────────────────────────────────────
  /** requestAnimationFrame でカメラ映像をミラー表示し続ける */
  function drawLoop() {
    animFrame = requestAnimationFrame(drawLoop);
    if (!videoEl || !canvasEl || videoEl.readyState < 2) return;

    const ctx = canvasEl.getContext('2d')!;
    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(videoEl, -canvasEl.width, 0, canvasEl.width, canvasEl.height);
    ctx.restore();
  }

  // ── タイマー管理 ─────────────────────────────────────────────
  let countdownInterval: ReturnType<typeof setInterval> | null = null;

  /** 全てのタイマーを安全に停止する（コンポーネント破棄時・戻るボタン時） */
  function clearAllTimers() {
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = null;
  }

  /**
   * 次の撮影をスケジュールする。
   * - 1枚目: すぐカウントダウンを開始
   * - 2枚目以降: インターバル（ポーズ変え時間）を挟んでからカウントダウン
   */
  function scheduleNextShot() {
    if (allDone) return;
    if (capturedCount > 0) {
      startInterval();  // インターバル待ち
    } else {
      startCountdown(); // 1枚目はすぐカウントダウン
    }
  }

  /**
   * インターバルフェーズ（次の撮影まで INTERVAL_SEC 秒待つ）。
   * ポーズガイドモードなら次のポーズメッセージを表示する。
   */
  function startInterval() {
    isIntervalPhase = true;
    intervalTimer = INTERVAL_SEC;
    countdownInterval = setInterval(() => {
      intervalTimer--;
      if (intervalTimer <= 0) {
        if (countdownInterval) clearInterval(countdownInterval);
        isIntervalPhase = false;
        startCountdown(); // インターバル終了 → カウントダウン開始
      }
    }, 1000);
  }

  /**
   * カウントダウン（COUNTDOWN_SEC → 1 → shoot）。
   * tick() で DOM の更新を待ってから GSAP アニメーションを実行する。
   * tick() は「Svelte が DOM を更新するまで待つ」Promise。
   */
  function startCountdown() {
    countdown = COUNTDOWN_SEC;
    tick().then(() => animateCountdown()); // 数字が DOM に現れてからアニメーション
    countdownInterval = setInterval(() => {
      countdown--;
      if (countdown <= 0) {
        if (countdownInterval) clearInterval(countdownInterval);
        shoot(); // 0 になったら撮影
      } else {
        tick().then(() => animateCountdown());
      }
    }, 1000);
  }

  /** GSAP でカウントダウン数字をアニメーションさせる（大 → 小 + フェードイン） */
  function animateCountdown() {
    if (!countdownEl) return;
    gsap.fromTo(countdownEl,
      { scale: 2.2, opacity: 0 },
      { scale: 1, opacity: 1, duration: 0.55, ease: 'elastic.out(1, 0.5)' }
    );
  }

  // ── 撮影 ─────────────────────────────────────────────────────
  /**
   * シャッター処理。
   * Canvas の現在の内容を JPEG として保存し、appState に追加する。
   * 撮影完了後、枚数に達したら Edit 画面に遷移する。
   */
  function shoot() {
    if (!canvasEl) return;

    // 白フラッシュエフェクト（0.3秒）
    flashActive = true;
    setTimeout(() => { flashActive = false; }, 300);

    // canvasEl の現在の映像を別の Canvas にコピーして保存
    // （drawLoop が続いて上書きされないよう、新しい Canvas に複製する）
    const snap = document.createElement('canvas');
    snap.width  = canvasEl.width;
    snap.height = canvasEl.height;
    const sCtx = snap.getContext('2d')!;
    sCtx.drawImage(canvasEl, 0, 0);

    const dataUrl = snap.toDataURL('image/jpeg', 0.92); // JPEG 92% 品質で保存
    appState.addFrame(dataUrl); // グローバルストアに追加

    shotDone = true;
    setTimeout(() => { shotDone = false; }, 500);

    const newCount = capturedCount + 1;
    if (newCount >= totalCount) {
      // 全枚撮影完了 → 0.8秒後に Edit 画面へ
      setTimeout(() => appState.setPhase('edit'), 800);
    } else {
      startInterval(); // まだある → 次のインターバルへ
    }
  }

  /** セットアップ画面に戻る。タイマーをリセットして状態をクリアする。 */
  function goBack() {
    clearAllTimers();
    appState.resetFrames();
    appState.setPhase('setup');
  }
</script>

<div class="camera-screen">
  <!-- カメラプレビューエリア -->
  <div class="preview-area" class:flash={flashActive}>
    <!-- video は非表示。Canvas への描画の元データとして使う -->
    <video bind:this={videoEl} playsinline muted style="display:none"></video>
    <canvas bind:this={canvasEl} class="preview-canvas"></canvas>

    <!-- カウントダウン数字のオーバーレイ -->
    {#if countdown > 0}
      <div class="countdown-overlay">
        <span bind:this={countdownEl} class="countdown-num">{countdown}</span>
      </div>
    {/if}

    <!-- インターバル中のオーバーレイ（ローディングスピナー） -->
    {#if isIntervalPhase}
      <div class="interval-overlay">
        <div class="loader"></div>
      </div>
    {/if}

    <!-- 撮影進捗インジケーター（右上） -->
    <div class="shot-counter">
      {Math.min(capturedCount + 1, totalCount)} / {totalCount}
    </div>

  </div>

  <!-- 撮影済みサムネイル一覧 -->
  <div class="thumbnail-bar">
    {#each Array(totalCount) as _, i}
      <div class="thumb-slot" class:filled={i < capturedCount}>
        {#if i < capturedCount}
          <img src={state.capturedFrames[i]} alt="shot {i+1}" />
        {:else}
          <span class="thumb-num">{i + 1}</span>
        {/if}
      </div>
    {/each}
  </div>

  <!-- 戻るボタン -->
  <button class="back-btn" onclick={goBack}><ArrowLeft size={14} /> 戻る</button>

  <a class="music-credit" href="https://moerumusic.com" target="_blank" rel="noopener noreferrer"><Music size={10} /> moeru music.</a>
</div>

<style>
  .camera-screen {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: #1a1a2e;
    position: relative;
  }

  .preview-area {
    flex: 1;
    position: relative;
    overflow: hidden;
    background: #000;
    transition: opacity 0.1s;
  }
  .preview-area.flash {
    background: white;
  }
  .preview-area.flash .preview-canvas {
    opacity: 0;
  }

  .preview-canvas {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: opacity 0.1s;
  }

  .countdown-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.3);
  }
  .countdown-num {
    font-size: 12rem;
    font-weight: 900;
    color: white;
    text-shadow: 0 0 40px rgba(255,133,161,0.8), 0 4px 20px rgba(0,0,0,0.5);
    animation: pulse 0.9s ease-in-out;
  }
  @keyframes pulse {
    0% { transform: scale(1.5); opacity: 0; }
    50% { transform: scale(1.1); opacity: 1; }
    100% { transform: scale(1); opacity: 1; }
  }

  .interval-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0,0,0,0.35);
  }
  .loader {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    border: 6px solid rgba(255,255,255,0.2);
    border-top-color: #FFB7C5;
    animation: spin 0.9s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .shot-counter {
    position: absolute;
    top: 16px;
    right: 62px;
    background: rgba(240,160,192,0.9);
    color: white;
    font-size: 1.2rem;
    font-weight: 800;
    padding: 6px 16px;
    border-radius: 100px;
    backdrop-filter: blur(4px);
  }

  .thumbnail-bar {
    display: flex;
    gap: 6px;
    padding: 10px 12px;
    background: #16122a;
    overflow-x: auto;
    flex-shrink: 0;
  }

  .thumb-slot {
    width: 60px;
    height: 80px;
    border-radius: 8px;
    border: 2px solid #333;
    overflow: hidden;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #2a2040;
    transition: all 0.3s;
  }
  .thumb-slot.filled {
    border-color: #F0A0C0;
    box-shadow: 0 0 8px rgba(240,160,192,0.4);
  }
  .thumb-slot img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .thumb-num {
    color: #666;
    font-size: 1.2rem;
    font-weight: 700;
  }

  .back-btn {
    position: absolute;
    bottom: 110px;
    left: 16px;
    background: rgba(255,255,255,0.15);
    color: white;
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 100px;
    padding: 8px 16px;
    font-size: 0.85rem;
    cursor: pointer;
    backdrop-filter: blur(4px);
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .back-btn:hover {
    background: rgba(255,255,255,0.25);
  }

  .music-credit {
    position: absolute;
    bottom: 8px;
    right: 12px;
    font-size: 0.58rem;
    color: rgba(255,255,255,0.45);
    text-decoration: none;
    letter-spacing: 0.04em;
    pointer-events: auto;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 3px;
  }
  .music-credit:hover { color: rgba(255,255,255,0.8); text-decoration: underline; }

  @media (max-width: 767px) {
    .camera-screen {
      height: 100dvh;
    }

    .countdown-num {
      font-size: 7rem;
    }

    .shot-counter {
      font-size: 0.95rem;
      padding: 4px 12px;
      top: 10px;
      right: 58px;
    }

    .thumbnail-bar {
      padding: 8px 10px;
      gap: 4px;
    }
    .thumb-slot {
      width: 44px;
      height: 58px;
    }

    .back-btn {
      bottom: 88px;
      padding: 6px 12px;
      font-size: 0.78rem;
    }
  }
</style>
