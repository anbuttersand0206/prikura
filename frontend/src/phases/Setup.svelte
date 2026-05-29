<script lang="ts">
  // ============================================================
  // Setup.svelte — セットアップ画面（Phase 1）
  //
  // 撮影前にフレーム・背景色・枚数・ポーズガイドを選ぶ画面。
  // 「撮影スタート」ボタンで Camera 画面に遷移する。
  // ============================================================

  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { appState, FRAME_DESIGNS, BG_COLORS } from '../stores/appState';
  import { bgmEnabled, tryPlay } from '../stores/bgmStore';
  import { Music } from 'lucide-svelte';

  let bgm: HTMLAudioElement | null = null;
  let bgmCleanup = () => {};
  onMount(() => {
    bgm = new Audio('/sounds/1minute.mp3');
    bgm.loop = true;
    bgm.volume = 0.35;
    if (get(bgmEnabled)) bgmCleanup = tryPlay(bgm);
  });
  onDestroy(() => {
    bgmCleanup();
    bgm?.pause();
    bgm = null;
  });

  $: if (bgm) { $bgmEnabled ? bgm.play().catch(() => {}) : bgm.pause(); }

  // $appState 購読（ストアの中身が変わると自動で state が更新される）
  let state = $appState;
  $: state = $appState;

  /** フレームデザインを選択する */
  function selectFrame(f: typeof FRAME_DESIGNS[0]) {
    appState.setFrame(f);
  }

  /** 背景色を選択する */
  function selectBg(b: typeof BG_COLORS[0]) {
    appState.setBg(b);
  }

  /** 撮影枚数を設定する */
  function setCount(n: 6 | 8 | 10) {
    appState.setShootCount(n);
  }

  /**
   * 撮影開始。
   * 以前の撮影データをリセットしてから Camera 画面に遷移する。
   */
  function start() {
    appState.resetFrames(); // 撮り直し時のゴミデータを消す
    appState.setPhase('camera');
  }

  // フレーム選択UIに表示する装飾パターンのプレビュー文字列
  // （borderStyle キーと1対1で対応）
  const frameBorderPatterns: Record<string, string> = {
    hearts: '♥ ♡ ♥ ♡',
    stars: '★ ☆ ★ ☆',
    flowers: '✿ ❀ ✿ ❀',
    dots: '● ○ ● ○',
    clouds: '☁ ⛅ ☁ ⛅',
    ribbons: '❥ ❧ ❥ ❧',
    cherries: '🌸 🌺 🌸 🌺',
    simple: '— — — —',
  };
</script>

<div class="setup-screen">
  <!-- ヘッダー -->
  <div class="setup-header">
    <img src="/logo.png" alt="プリクラメーカー" class="header-logo" />
  </div>

  <div class="setup-body">
    <div class="body-inner">
    <!-- フレーム選択（8種） -->
    <section class="setup-section">
      <h2>フレームを選ぶ</h2>
      <div class="frame-grid">
        {#each FRAME_DESIGNS as frame}
          <button
            class="frame-card"
            class:selected={state.selectedFrame.id === frame.id}
            style="--fc: {frame.color}; --fa: {frame.accent}"
            onclick={() => selectFrame(frame)}
          >
            <!-- フレームのプレビュー: 主色の背景にアクセント色の枠 -->
            <div class="frame-preview">
              <div class="frame-inner">
                <span class="frame-pattern">{frameBorderPatterns[frame.borderStyle]}</span>
              </div>
            </div>
            <span class="frame-name">{frame.name}</span>
          </button>
        {/each}
      </div>
    </section>

    <!-- 背景色選択（8色） -->
    <section class="setup-section">
      <h2>プリカラーを選ぶ</h2>
      <div class="bg-grid">
        {#each BG_COLORS as bg}
          <button
            class="bg-swatch"
            class:selected={state.selectedBg.id === bg.id}
            style="background: {bg.value}"
            onclick={() => selectBg(bg)}
            title={bg.name}
          >
            {#if state.selectedBg.id === bg.id}
              <span class="check">✓</span>
            {/if}
            <span class="bg-name">{bg.name}</span>
          </button>
        {/each}
      </div>
    </section>

    <!-- 撮影枚数選択（6 / 8 / 10） -->
    <section class="setup-section">
      <h2>撮影枚数を選ぶ</h2>
      <div class="count-buttons">
        {#each [6, 8, 10] as n}
          <button
            class="count-btn"
            class:selected={state.shootCount === n}
            onclick={() => setCount(n as 6|8|10)}
          >
            {n}枚
          </button>
        {/each}
      </div>
    </section>

    </div>
  </div>

  <!-- スタートボタン -->
  <div class="setup-footer">
    <div class="footer-inner">
      <button class="start-btn" onclick={start}>
        撮影スタート ▶
      </button>
      <a class="music-credit" href="https://moerumusic.com" target="_blank" rel="noopener noreferrer">
        <Music size={10} /> moeru music.
      </a>
    </div>
  </div>
</div>

<style>
  .setup-screen {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: linear-gradient(160deg, #FFF0F8 0%, #F0E8FF 100%);
    overflow: hidden;
  }

  .setup-header {
    text-align: center;
    padding: 16px;
    background: linear-gradient(135deg, #F0A0C0, #D4A0F0);
    color: white;
    flex-shrink: 0;
  }
  .header-logo {
    height: 62px;
    width: auto;
    display: block;
    margin: 0 auto;
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5));
  }

  .setup-body {
    flex: 1;
    overflow-y: auto;
  }

  .body-inner {
    max-width: 680px;
    margin: 0 auto;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .setup-section h2 {
    font-size: 1rem;
    font-weight: 700;
    color: #C060A0;
    margin: 0 0 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .setup-section h2::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 1em;
    background: #F0A0C0;
    border-radius: 2px;
  }

  .frame-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .frame-card {
    background: white;
    border: 3px solid transparent;
    border-radius: 16px;
    padding: 8px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  .frame-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(240,160,192,0.4);
  }
  .frame-card.selected {
    border-color: var(--fa);
    background: color-mix(in srgb, var(--fc) 20%, white);
  }

  .frame-preview {
    width: 100%;
    aspect-ratio: 3/4;
    border-radius: 10px;
    background: var(--fc);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    position: relative;
  }
  .frame-inner {
    position: absolute;
    inset: 4px;
    border: 2px solid var(--fa);
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .frame-pattern {
    font-size: 0.55rem;
    color: var(--fa);
    opacity: 0.7;
    letter-spacing: 1px;
  }
  .frame-name {
    font-size: 0.65rem;
    font-weight: 600;
    color: #666;
    text-align: center;
  }

  .bg-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 8px;
  }
  .bg-swatch {
    aspect-ratio: 1;
    border-radius: 50%;
    border: 3px solid transparent;
    cursor: pointer;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    transition: all 0.2s;
    padding: 0;
  }
  .bg-swatch:hover {
    transform: scale(1.1);
  }
  .bg-swatch.selected {
    border-color: #F0A0C0;
    box-shadow: 0 0 0 3px rgba(240,160,192,0.4);
  }
  .check {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-size: 1.2rem;
    font-weight: bold;
    text-shadow: 0 1px 3px rgba(0,0,0,0.5);
  }
  .bg-name {
    position: absolute;
    bottom: -18px;
    font-size: 0.55rem;
    color: #888;
    white-space: nowrap;
  }

  .count-buttons {
    display: flex;
    gap: 12px;
  }
  .count-btn {
    flex: 1;
    padding: 12px;
    border-radius: 16px;
    border: 2px solid #E8C0D8;
    background: white;
    font-size: 1rem;
    font-weight: 700;
    color: #C060A0;
    cursor: pointer;
    transition: all 0.2s;
  }
  .count-btn.selected {
    background: linear-gradient(135deg, #F0A0C0, #D4A0F0);
    border-color: transparent;
    color: white;
    box-shadow: 0 4px 12px rgba(240,160,192,0.5);
  }

  .setup-footer {
    flex-shrink: 0;
  }

  .footer-inner {
    max-width: 680px;
    margin: 0 auto;
    padding: 16px 20px;
  }

  .start-btn {
    width: 100%;
    padding: 16px;
    border-radius: 100px;
    border: none;
    background: linear-gradient(135deg, #FF85A1, #C070E0);
    color: white;
    font-size: 1.2rem;
    font-weight: 800;
    cursor: pointer;
    box-shadow: 0 6px 20px rgba(255,133,161,0.5);
    transition: all 0.2s;
    letter-spacing: 0.1em;
  }
  .start-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgba(255,133,161,0.6);
  }
  .start-btn:active {
    transform: translateY(-1px);
  }

  .music-credit {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-size: 0.62rem;
    color: #C8A0C0;
    text-decoration: none;
    margin-top: 8px;
    opacity: 0.8;
    letter-spacing: 0.04em;
  }
  .music-credit:hover { opacity: 1; text-decoration: underline; }

  @media (max-width: 767px) {
    .setup-screen {
      height: 100dvh;
    }

    .setup-header {
      padding: 14px 16px;
    }
    .header-logo {
      height: 44px;
    }

    .body-inner {
      padding: 12px 14px;
      gap: 16px;
    }

    .frame-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
    }

    .bg-grid {
      grid-template-columns: repeat(4, 1fr);
    }

    .count-btn {
      padding: 10px;
      font-size: 0.9rem;
    }

    .footer-inner {
      padding: 12px 14px;
    }
    .start-btn {
      padding: 14px;
      font-size: 1.05rem;
    }
  }
</style>
