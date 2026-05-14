<script lang="ts">
  // ============================================================
  // Edit.svelte — 落書き・加工・保存画面（Phase 3）
  //
  // 【画面構成】
  //   左パネル: ペン / スタンプ / レタッチ の3タブ
  //   中央: 4層の Canvas スタック（写真 → 落書き → スタンプ → フレーム）
  //
  // 【4層 Canvas の構造】
  //   Layer 1 (bgCanvasEl)    : 写真 or 背景色 + フロントエンドレタッチ
  //   Layer 2 (PenCanvas)     : 落書き（ペン・消しゴム・Undo）
  //   Layer 3 (stamps-layer)  : スタンプ（ドラッグ・拡縮・削除）
  //   Layer 4 (frameCanvasEl) : フレームの枠・装飾オーバーレイ
  //
  // 【スタンプのpointer-events設計】
  //   stamps-layer の div は常に pointer-events:none。
  //   個々の .stamp-item だけ isEraser でなければ pointer-events:auto。
  //   これにより「スタンプのない場所」では PenCanvas がマウスを受け取れる。
  // ============================================================

  import { onMount, onDestroy, tick } from 'svelte';
  import { get } from 'svelte/store';
  import { gsap } from 'gsap';
  import { appState } from '../stores/appState';
  import { bgmEnabled, tryPlay } from '../stores/bgmStore';
  import { Pencil, Eraser, Undo2, Trash2, Sparkles, Stamp, WandSparkles, LoaderCircle, Printer, RotateCcw, Music } from 'lucide-svelte';
  import PenPalette from '../components/PenPalette.svelte';
  import PenCanvas from '../components/PenCanvas.svelte';
  import RetouchSliders from '../components/RetouchSliders.svelte';
  import StampPanel from '../components/StampPanel.svelte';
  import FrameCanvas from '../components/FrameCanvas.svelte';

  let state = $appState;
  $: state = $appState;

  // ── タブ・ペン状態 ────────────────────────────────────────────
  type Tab = 'pen' | 'stamp' | 'retouch';
  let activeTab: Tab = 'pen';

  let selectedPenId = 'normal';
  let penColor   = '#FF85A1';
  let penSize    = 8;
  let penOpacity = 1;
  let isEraser   = false;

  // ── Canvas 参照 ───────────────────────────────────────────────
  let penCanvasComp: ReturnType<typeof PenCanvas>; // PenCanvas コンポーネントへの参照
  let bgCanvasEl: HTMLCanvasElement;               // Layer1: 写真/背景
  let frameCanvasEl: HTMLCanvasElement;            // Layer4: フレーム
  let canvasStackEl: HTMLDivElement;               // 4層を束ねる div
  let canvasAnimEl: HTMLDivElement;                // GSAP アニメーション用ラッパー

  // ── レスポンシブ ──────────────────────────────────────────────
  let canvasScale = 1; // モバイル時の縮小率（1 = デスクトップ等倍）

  function updateCanvasScale() {
    if (typeof window === 'undefined') return;
    canvasScale = window.innerWidth < 768
      ? Math.min(1, (window.innerWidth - 32) / FRAME_W)
      : 1;
  }

  // ── フレームごとのデータ管理 ─────────────────────────────────
  // 写真ごとに独立した落書きデータを保持する（IndexedArray）
  let frameDrawings: (ImageData | null)[] = [];   // 落書きのスナップショット（フレーム番号→ImageData）
  let retouchedPhotos: (string | null)[] = [];    // AI レタッチ済み写真（フレーム番号→base64 or null）

  let currentPhotoIdx = 0;  // 現在表示中のフレーム番号
  let prevPhotoIdx = -1;    // 直前のフレーム番号（切り替え検知用）

  // Canvas の表示サイズ（px）。保存時は 1200×1800 の高解像度にスケール
  const FRAME_W = 480;
  const FRAME_H = 360;

  // ── フレーム装飾パターン ─────────────────────────────────────
  // borderStyle → 上下の装飾文字の配列（6文字で1サイクル）
  const FRAME_DECO: Record<string, string[]> = {
    hearts:  ['♥', '♡', '♥', '♡', '♥', '♡'],
    stars:   ['★', '☆', '★', '☆', '★', '☆'],
    flowers: ['✿', '❀', '✾', '✿', '❀', '✾'],
    dots:    ['●', '○', '◉', '●', '○', '◉'],
    clouds:  ['☁', '⛅', '☁', '⛅', '☁', '⛅'],
    ribbons: ['❥', '❧', '❥', '❧', '❥', '❧'],
    cherries:['🌸', '🌺', '🌸', '🌺', '🌸', '🌺'],
    simple:  ['—', '·', '—', '·', '—', '·'],
  };

  // ── スタンプ管理 ─────────────────────────────────────────────
  /**
   * スタンプ1件のデータ型。
   * size は高さ。テキストスタンプは横長になるので stampW（幅）を別途持つ。
   */
  type StampItem = {
    id: string; svg: string;
    x: number; y: number;
    size: number;      // 高さ（正方形スタンプはこれが幅も兼ねる）
    stampW?: number;   // テキストスタンプ等の横長スタンプの幅（省略時は size と同じ）
    rotation: number;  // 回転角度（度）
  };
  let stamps: StampItem[] = [];
  let frameStamps: StampItem[][] = [];        // フレームごとのスタンプ保存領域
  let selectedStampId: string | null = null;  // 選択中スタンプの ID
  let draggingStamp: StampItem | null = null; // ドラッグ中のスタンプ
  let dragOffX = 0, dragOffY = 0;             // ドラッグ開始時のオフセット
  type DragMode = 'move' | 'resize' | 'rotate';
  let dragMode: DragMode = 'move';
  let dragStartDist = 0;
  let dragStartSize = 0, dragStartW = 0, dragStartCx = 0, dragStartCy = 0;
  let dragStartAngle = 0, dragStartRotation = 0;

  // ── 保存 / AI レタッチ状態 ────────────────────────────────────
  let isSaving    = false;
  let saveSuccess = false;
  let isRetouching  = false;
  let retouchError  = '';
  let isBgReplacing = false;  // 背景置換の処理中フラグ

  // bgReplacedPhotos: 背景をプリカラーで置換した写真（null = 未処理）
  let bgReplacedPhotos: (string | null)[] = [];

  // 現在表示する写真: AI レタッチ済み → 背景置換済み → オリジナル の優先順
  $: currentPhoto = retouchedPhotos[currentPhotoIdx]
    ?? bgReplacedPhotos[currentPhotoIdx]
    ?? state.capturedFrames[currentPhotoIdx];

  // ── BGM ──────────────────────────────────────────────────────
  let bgm: HTMLAudioElement | null = null;
  let bgmCleanup = () => {};
  $: if (bgm) { $bgmEnabled ? bgm.play().catch(() => {}) : bgm.pause(); }

  // ── 初期化 ────────────────────────────────────────────────────
  onMount(() => {
    bgm = new Audio('/sounds/MEET%20UP.mp3');
    bgm.loop = true;
    bgm.volume = 0.35;
    if (get(bgmEnabled)) bgmCleanup = tryPlay(bgm);
    // フレーム数分の配列を null / [] で初期化
    frameDrawings    = state.capturedFrames.map(() => null);
    retouchedPhotos  = state.capturedFrames.map(() => null);
    bgReplacedPhotos = state.capturedFrames.map(() => null);
    frameStamps      = state.capturedFrames.map(() => []);
    updateCanvasScale();
    window.addEventListener('resize', updateCanvasScale);
    tick().then(() => {
      drawBackground();
      drawFrameOverlay();
      animateIn();
      applyBgReplace(); // 背景をプリカラーで自動置換
    });
  });

  onDestroy(() => {
    bgmCleanup();
    bgm?.pause();
    bgm = null;
    window.removeEventListener('resize', updateCanvasScale);
  });

  // currentPhoto が変わったら背景を再描画
  $: if (currentPhoto !== undefined) {
    tick().then(drawBackground);
  }
  // currentPhotoIdx が変わったらフレーム切り替え処理
  $: if (currentPhotoIdx !== prevPhotoIdx) {
    tick().then(switchFrame);
  }

  /** 画面入場アニメーション */
  function animateIn() {
    if (!canvasAnimEl) return;
    gsap.fromTo(canvasAnimEl,
      { opacity: 0, scale: 0.95 },
      { opacity: 1, scale: 1, duration: 0.4, ease: 'back.out(1.4)' }
    );
  }

  /**
   * フレーム（写真）を切り替える。
   * 切り替え前に現フレームの落書きを保存し、
   * 切り替え後に新フレームの落書きを復元する。
   */
  async function switchFrame() {
    // 切り替え前の落書き・スタンプを保存
    if (prevPhotoIdx >= 0 && penCanvasComp) {
      frameDrawings[prevPhotoIdx] = penCanvasComp.getImageData();
    }
    if (prevPhotoIdx >= 0) {
      frameStamps[prevPhotoIdx] = stamps;
    }
    prevPhotoIdx = currentPhotoIdx;

    await tick(); // DOM 更新を待つ
    drawBackground();
    drawFrameOverlay();

    // 新フレームの落書きを復元（なければ消去）
    if (frameDrawings[currentPhotoIdx] && penCanvasComp) {
      penCanvasComp.putImageData(frameDrawings[currentPhotoIdx]!);
    } else if (penCanvasComp) {
      penCanvasComp.clearSilent(); // Undo 履歴も消去（切り替えなのでアンドゥ不要）
    }

    // 新フレームのスタンプを復元（なければ空に）
    stamps = [...(frameStamps[currentPhotoIdx] ?? [])];
    selectedStampId = null;
    draggingStamp   = null;

    // スライドアニメーション
    if (canvasAnimEl) {
      gsap.fromTo(canvasAnimEl,
        { x: 15, opacity: 0.6 },
        { x: 0, opacity: 1, duration: 0.25, ease: 'power2.out' }
      );
    }
  }

  /**
   * Layer1（写真/背景）を描画する。
   * 写真がある場合は非同期ロードしてから applyFrontendRetouch() を適用。
   */
  function drawBackground() {
    if (!bgCanvasEl) return;
    const ctx = bgCanvasEl.getContext('2d')!;
    ctx.clearRect(0, 0, FRAME_W, FRAME_H);
    const photo = currentPhoto;
    if (photo) {
      const img = new Image();
      img.onload = () => {
        ctx.drawImage(img, 0, 0, FRAME_W, FRAME_H);
        applyFrontendRetouch(ctx); // 写真の上に CSS 的な明るさ・チーク効果を重ねる
      };
      img.src = photo;
    } else {
      // 写真なし → 背景色で塗りつぶす
      ctx.fillStyle = state.selectedBg.value;
      ctx.fillRect(0, 0, FRAME_W, FRAME_H);
    }
  }

  /**
   * フロントエンドで手軽にかけられる簡易レタッチ。
   * AI レタッチ（バックエンド）の代わりに、ほんのり即時プレビューを提供する。
   *
   * 対応項目:
   *   - skinBrightness: Canvas の compositeOperation（screen/multiply）で実装
   *   - cheekStrength: 放射状グラデーション（multiply）で頬に色を乗せる
   */
  function applyFrontendRetouch(ctx: CanvasRenderingContext2D) {
    const bv = state.beauty;
    if (bv.skinBrightness === 0 && bv.cheekStrength === 0 && bv.lipStrength === 0) return;

    if (bv.skinBrightness !== 0) {
      ctx.save();
      ctx.globalCompositeOperation = bv.skinBrightness > 0 ? 'screen' : 'multiply';
      ctx.globalAlpha = Math.abs(bv.skinBrightness) / 400;
      ctx.fillStyle = bv.skinBrightness > 0 ? '#ffffff' : '#000000';
      ctx.fillRect(0, 0, FRAME_W, FRAME_H);
      ctx.restore();
    }

    if (bv.cheekStrength > 0) {
      ctx.save();
      ctx.globalCompositeOperation = 'multiply';
      for (const [fx, fy] of [[0.25, 0.55], [0.75, 0.55]] as [number, number][]) {
        ctx.globalAlpha = bv.cheekStrength / 400;
        const g = ctx.createRadialGradient(
          FRAME_W * fx, FRAME_H * fy, 5,
          FRAME_W * fx, FRAME_H * fy, FRAME_W * 0.2
        );
        g.addColorStop(0, bv.cheekColor);
        g.addColorStop(1, 'transparent');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, FRAME_W, FRAME_H);
      }
      ctx.restore();
    }
  }

  /**
   * Layer4（フレームオーバーレイ）を描画する。
   * 4辺の帯 + 内側の細い矩形 + 上下の装飾文字。
   * 選択中のフレームデザインの borderStyle に応じた文字を使う。
   */
  function drawFrameOverlay() {
    if (!frameCanvasEl) return;
    const ctx = frameCanvasEl.getContext('2d')!;
    ctx.clearRect(0, 0, FRAME_W, FRAME_H);
    const f = state.selectedFrame;
    const bwH = 28; // 上下（横線）の太さ
    const bwV = 18; // 左右（縦線）の太さ

    ctx.fillStyle = f.color;
    ctx.fillRect(0, 0, FRAME_W, bwH);
    ctx.fillRect(0, FRAME_H - bwH, FRAME_W, bwH);
    ctx.fillRect(0, 0, bwV, FRAME_H);
    ctx.fillRect(FRAME_W - bwV, 0, bwV, FRAME_H);

    ctx.strokeStyle = f.accent;
    ctx.lineWidth = 2;
    ctx.strokeRect(bwV + 4, bwH + 4, FRAME_W - (bwV + 4) * 2, FRAME_H - (bwH + 4) * 2);

    ctx.fillStyle = f.accent;
    ctx.font = '12px "M PLUS Rounded 1c"';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const deco = FRAME_DECO[f.borderStyle] ?? FRAME_DECO.hearts;
    for (let i = 0; i < 6; i++) {
      const x = (FRAME_W / 7) * (i + 1);
      ctx.fillText(deco[i % deco.length], x, bwH / 2);
      ctx.fillText(deco[i % deco.length], x, FRAME_H - bwH / 2);
    }
  }

  // ── 背景置換 ─────────────────────────────────────────────────
  /**
   * 全フレームの背景をプリカラー（state.selectedBg.value）で置換する。
   * バックエンドに接続できない場合はエラーを無視してオリジナルのまま表示する。
   */
  async function applyBgReplace() {
    if (!state.capturedFrames.length) return;
    isBgReplacing = true;
    const bgColor = state.selectedBg.value;
    try {
      const results = await Promise.all(
        state.capturedFrames.map(async (photo, i) => {
          const b64 = photo.split(',')[1] ?? photo;
          const res = await fetch('/api/bg_replace', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: b64, bg_color: bgColor }),
          });
          if (!res.ok) return null;
          const data = await res.json();
          return `data:image/jpeg;base64,${data.image}`;
        })
      );
      bgReplacedPhotos = results;
    } catch (e) {
      console.warn('[bg_replace] API unavailable, using original photos:', e);
    } finally {
      isBgReplacing = false;
      await tick();
      drawBackground();
    }
  }

  // ── AI レタッチ ───────────────────────────────────────────────
  /**
   * バックエンド（FastAPI）に写真 + レタッチパラメータを送り、
   * AI 加工済み画像を受け取って retouchedPhotos に保存する。
   * 失敗時はエラーメッセージを表示し、元の写真のままにする。
   */
  async function applyAiRetouch() {
    // 背景置換済みがあればそちらをレタッチのベースにする
    const photo = bgReplacedPhotos[currentPhotoIdx] ?? state.capturedFrames[currentPhotoIdx];
    if (!photo) return;
    isRetouching = true;
    retouchError = '';
    try {
      const b64 = photo.split(',')[1] ?? photo;
      const bv = state.beauty;
      const res = await fetch('/api/beauty_retouch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image:                    b64,
          smoothing_strength:       bv.smoothing      / 100,
          sharpness_strength:       bv.sharpness      / 100,
          skin_brightness:          bv.skinBrightness / 100,
          skin_warmth:              bv.skinWarmth     / 100,
          whitening_strength:       bv.whitening      / 100,
          face_slim_strength:        bv.faceSlim   / 100,
          head_size_strength:        bv.headSize   / 100,
          mid_face_shorten_strength: bv.midFace    / 100,
          cheek_width_strength:      bv.cheekWidth / 100,
          jaw_strength:             bv.jaw            / 100,
          chin_length_strength:     bv.chinLength     / 100,
          nose_width_strength:      bv.noseWidth      / 100,
          nose_height_strength:     bv.noseHeight     / 100,
          eye_size_strength:        bv.eyeSize        / 100,
          eye_position_strength:    bv.eyePosition    / 100,
          eye_sparkle_strength:     bv.eyeSparkle     / 100,
          iris_size_strength:       bv.irisSize       / 100,
          eye_tilt_strength:        bv.eyeTilt        / 100,
          dark_circle_strength:     bv.darkCircle     / 100,
          mouth_size_strength:      bv.mouthSize      / 100,
          mouth_corner_strength:    bv.mouthCorner    / 100,
          philtrum_strength:        bv.philtrum       / 100,
          teeth_whitening_strength: bv.teethWhitening / 100,
          cheek_strength:           bv.cheekStrength  / 100,
          cheek_color:              bv.cheekColor,
          lip_strength:             bv.lipStrength    / 100,
          lip_color:                bv.lipColor,
          tear_bag_strength:        bv.tearBag        / 100,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // レスポンスの base64 を data URL に変換して保存
      retouchedPhotos[currentPhotoIdx] = `data:image/png;base64,${data.image}`;
      retouchedPhotos = retouchedPhotos; // Svelte のリアクティビティを発火させる
      await tick();
      drawBackground();
    } catch (e) {
      retouchError = 'バックエンドに接続できません。ローカルプレビューを使用中です。';
    } finally {
      isRetouching = false;
    }
  }

  // ── スタンプ ─────────────────────────────────────────────────

  /**
   * スタンプを追加する。
   * SVG の viewBox からアスペクト比を計算して初期サイズを決める。
   * テキストスタンプ（横長）は高さ 44px 固定で幅を比率から算出。
   */
  function addStamp(svg: string) {
    const vbMatch = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
    let initH = 60, initW = 60;
    if (vbMatch) {
      const svgW = parseFloat(vbMatch[1]), svgH = parseFloat(vbMatch[2]);
      const aspect = svgW / svgH;
      if (aspect > 1.8) {
        // 横長スタンプ（テキスト等）: 高さ 44px で幅を計算
        initH = 44;
        initW = Math.round(initH * aspect);
      }
    }
    const newStamp: StampItem = {
      id: Math.random().toString(36).slice(2),
      svg,
      x: FRAME_W / 2 - initW / 2,
      y: FRAME_H / 2 - initH / 2,
      size: initH,
      stampW: initW !== initH ? initW : undefined,
      rotation: 0,
    };
    stamps = [...stamps, newStamp];
    selectedStampId = newStamp.id;
  }

  /**
   * スタンプのドラッグ開始（mousedown）。
   * 右クリックで削除、左クリックでドラッグ開始。
   * e.stopPropagation() で PenCanvas への伝播を防ぐ。
   */
  function onStampMouseDown(e: MouseEvent, stamp: StampItem) {
    e.preventDefault();
    e.stopPropagation();
    if (e.button === 2) {
      stamps = stamps.filter(s => s.id !== stamp.id);
      if (selectedStampId === stamp.id) selectedStampId = null;
      return;
    }
    selectedStampId = stamp.id;
    draggingStamp = stamp;
    dragMode = 'move';
    const rect = (e.currentTarget as HTMLElement).closest('.canvas-stack')!.getBoundingClientRect();
    dragOffX = (e.clientX - rect.left) / canvasScale - stamp.x;
    dragOffY = (e.clientY - rect.top)  / canvasScale - stamp.y;
  }

  function onResizeHandleMouseDown(e: MouseEvent, stamp: StampItem) {
    e.preventDefault(); e.stopPropagation();
    selectedStampId = stamp.id;
    draggingStamp = stamp; dragMode = 'resize';
    const rect = (e.currentTarget as HTMLElement).closest('.canvas-stack')!.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / canvasScale;
    const my = (e.clientY - rect.top)  / canvasScale;
    const w = stamp.stampW ?? stamp.size;
    dragStartCx = stamp.x + w / 2;
    dragStartCy = stamp.y + stamp.size / 2;
    dragStartDist = Math.hypot(mx - dragStartCx, my - dragStartCy) || 1;
    dragStartSize = stamp.size;
    dragStartW = w;
  }

  function onRotateHandleMouseDown(e: MouseEvent, stamp: StampItem) {
    e.preventDefault(); e.stopPropagation();
    selectedStampId = stamp.id;
    draggingStamp = stamp; dragMode = 'rotate';
    const rect = (e.currentTarget as HTMLElement).closest('.canvas-stack')!.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / canvasScale;
    const my = (e.clientY - rect.top)  / canvasScale;
    const w = stamp.stampW ?? stamp.size;
    const cx = stamp.x + w / 2, cy = stamp.y + stamp.size / 2;
    dragStartAngle = Math.atan2(my - cy, mx - cx) * 180 / Math.PI;
    dragStartRotation = stamp.rotation;
  }

  /**
   * スタンプのドラッグ移動。
   * canvas-stack（4層の親 div）の mousemove イベントを受け取る。
   * 境界クランプでスタンプがキャンバス外に出ないようにする。
   */
  function onCanvasMouseMove(e: MouseEvent) {
    if (!draggingStamp) return;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const mx = (e.clientX - rect.left) / canvasScale;
    const my = (e.clientY - rect.top)  / canvasScale;
    const w = draggingStamp.stampW ?? draggingStamp.size;
    if (dragMode === 'move') {
      draggingStamp.x = Math.max(0, Math.min(FRAME_W - w,                    mx - dragOffX));
      draggingStamp.y = Math.max(0, Math.min(FRAME_H - draggingStamp.size,   my - dragOffY));
    } else if (dragMode === 'resize') {
      const dist = Math.hypot(mx - dragStartCx, my - dragStartCy) || 1;
      const s = dist / dragStartDist;
      const newH = Math.max(20, Math.min(400, dragStartSize * s));
      const newW = dragStartW * (newH / dragStartSize);
      draggingStamp.size = newH;
      draggingStamp.stampW = draggingStamp.stampW !== undefined ? newW : undefined;
      draggingStamp.x = dragStartCx - newW / 2;
      draggingStamp.y = dragStartCy - newH / 2;
    } else if (dragMode === 'rotate') {
      const cx = draggingStamp.x + (draggingStamp.stampW ?? draggingStamp.size) / 2;
      const cy = draggingStamp.y + draggingStamp.size / 2;
      const angle = Math.atan2(my - cy, mx - cx) * 180 / Math.PI;
      draggingStamp.rotation = dragStartRotation + (angle - dragStartAngle);
    }
    stamps = stamps;
  }

  function onCanvasMouseUp() {
    if (draggingStamp === null) selectedStampId = null;
    draggingStamp = null;
  }

  /**
   * マウスホイールでスタンプを拡大縮小。
   * 横長スタンプ（stampW あり）はアスペクト比を保ちながら縮小する。
   */
  function onStampWheel(e: WheelEvent, stamp: StampItem) {
    e.preventDefault();
    selectedStampId = stamp.id;
    const delta = e.deltaY * 0.08;
    const prevH = stamp.size;
    stamp.size = Math.max(20, Math.min(400, stamp.size - delta));
    if (stamp.stampW !== undefined) {
      stamp.stampW = Math.round(stamp.stampW * (stamp.size / prevH));
    }
    stamps = stamps;
  }

  // ── PNG エクスポート ──────────────────────────────────────────
  /**
   * 全フレームを1枚の PNG（L判シール形式 1200×1800px）に合成して
   * ブラウザからダウンロードさせる。
   *
   * 【合成順序（各フレームセルごと）】
   *   1. 写真 or 背景色
   *   2. 落書きレイヤー（frameDrawings）
   *   3. フレームオーバーレイ（枠・装飾）
   *
   * 【スタンプについて】
   * 現状は現在表示中のフレームにのみスタンプを合成する。
   *
   * 【スケールの考え方】
   *   表示サイズ: FRAME_W×FRAME_H = 480×360
   *   出力1セル: cellW×cellH = 600×600（2列の場合、1200/2）
   *   scale = cellW / FRAME_W = 1.25 倍
   */
  async function saveSticker() {
    // 保存前に現フレームの落書き・スタンプを保存しておく
    if (penCanvasComp) {
      frameDrawings[currentPhotoIdx] = penCanvasComp.getImageData();
    }
    frameStamps[currentPhotoIdx] = stamps;

    isSaving = true;
    await tick();

    const total = state.shootCount;
    const cols = 2;
    const rows = Math.ceil(total / cols);
    const cellW = 600;
    const cellH = Math.round(cellW * FRAME_H / FRAME_W); // 450（表示と同じ 4:3 比率）
    const outW = cellW * cols;   // 1200
    const outH = cellH * rows;   // 1350（3行）or 900（2行）

    const out = document.createElement('canvas');
    out.width  = outW;
    out.height = outH;
    const ctx = out.getContext('2d')!;
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, outW, outH);

    const scale    = cellW / FRAME_W; // 1.25
    const bwH_out  = Math.round(28 * scale); // 上下フレームの太さ
    const bwV_out  = Math.round(18 * scale); // 左右フレームの太さ
    const f = state.selectedFrame;

    // 各フレームセルを順に描画
    for (let i = 0; i < total; i++) {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const px = col * cellW; // セルの左上 X
      const py = row * cellH; // セルの左上 Y

      // ── 1. 写真 or 背景色 ──────────────────────────────────────
      // cellH = FRAME_H * scale なので比率が一致 → letterbox なし
      ctx.fillStyle = state.selectedBg.value;
      ctx.fillRect(px, py, cellW, cellH);

      const photo = retouchedPhotos[i] ?? bgReplacedPhotos[i] ?? state.capturedFrames[i];
      if (photo) {
        const img = new Image();
        await new Promise<void>(res => { img.onload = () => res(); img.src = photo; });
        ctx.drawImage(img, px, py, cellW, cellH);
      }

      // ── 2. 落書きレイヤー ─────────────────────────────────────
      const drawing = i === currentPhotoIdx
        ? penCanvasComp?.getCanvas()
        : null;

      if (drawing) {
        ctx.drawImage(drawing, px, py, cellW, cellH);
      } else if (frameDrawings[i]) {
        const tmp = document.createElement('canvas');
        tmp.width = FRAME_W; tmp.height = FRAME_H;
        tmp.getContext('2d')!.putImageData(frameDrawings[i]!, 0, 0);
        ctx.drawImage(tmp, px, py, cellW, cellH);
      }

      // ── 3. フレームオーバーレイ ───────────────────────────────
      ctx.fillStyle = f.color;
      ctx.fillRect(px, py, cellW, bwH_out);                          // 上辺（太）
      ctx.fillRect(px, py + cellH - bwH_out, cellW, bwH_out);        // 下辺（太）
      ctx.fillRect(px, py, bwV_out, cellH);                          // 左辺
      ctx.fillRect(px + cellW - bwV_out, py, bwV_out, cellH);        // 右辺
      ctx.strokeStyle = f.accent;
      ctx.lineWidth = 2;
      const insetX = bwV_out + Math.round(4 * scale);
      const insetY = bwH_out + Math.round(4 * scale);
      ctx.strokeRect(px + insetX, py + insetY, cellW - insetX * 2, cellH - insetY * 2);

      ctx.fillStyle = f.accent;
      ctx.font = `${Math.round(bwH_out * 0.7)}px "M PLUS Rounded 1c"`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const decoOut = FRAME_DECO[f.borderStyle] ?? FRAME_DECO.hearts;
      for (let di = 0; di < 6; di++) {
        const dx = px + (cellW / 7) * (di + 1);
        ctx.fillText(decoOut[di % decoOut.length], dx, py + bwH_out / 2);
        ctx.fillText(decoOut[di % decoOut.length], dx, py + cellH - bwH_out / 2);
      }

      // ── 4. スタンプ（フレームごと） ───────────────────────────
      for (const stamp of (frameStamps[i] ?? [])) {
        const blob = new Blob([stamp.svg], { type: 'image/svg+xml' });
        const url  = URL.createObjectURL(blob);
        const img  = new Image();
        await new Promise<void>(res => { img.onload = () => res(); img.src = url; });
        const sw  = (stamp.stampW ?? stamp.size) * scale;
        const sh  = stamp.size * scale;
        const scx = px + (stamp.x + (stamp.stampW ?? stamp.size) / 2) * scale;
        const scy = py + (stamp.y + stamp.size / 2) * scale;
        ctx.save();
        ctx.translate(scx, scy);
        ctx.rotate(stamp.rotation * Math.PI / 180);
        ctx.drawImage(img, -sw / 2, -sh / 2, sw, sh);
        ctx.restore();
        URL.revokeObjectURL(url);
      }
    }

    // ── ダウンロード ──────────────────────────────────────────
    const link = document.createElement('a');
    link.download = `sticker_${Date.now()}.png`;
    link.href = out.toDataURL('image/png');
    link.click(); // クリックを模倣してダウンロードダイアログを開く

    isSaving = false;
    saveSuccess = true;
    gsap.fromTo('.save-success-hint',
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.3, ease: 'power2.out' }
    );
    setTimeout(() => { saveSuccess = false; }, 3000);
  }

  /** 撮り直しボタン: Setup 画面に戻る */
  function goBack() {
    appState.setPhase('setup');
  }
</script>

<div class="edit-screen">
  <!-- 左パネル: ペン / スタンプ / レタッチ タブ -->
  <aside class="left-panel">
    <div class="tab-bar">
      {#each (['pen', 'stamp', 'retouch'] as Tab[]) as tab}
        <button
          class="tab-btn"
          class:active={activeTab === tab}
          onclick={() => { activeTab = tab; }}
        >
          {#if tab === 'pen'}<Pencil size={13} /> ペン{:else if tab === 'stamp'}<Stamp size={13} /> スタンプ{:else}<Sparkles size={13} /> レタッチ{/if}
        </button>
      {/each}
    </div>

    <div class="panel-content">
      {#if activeTab === 'pen'}
        <!-- ペン / 消しゴム / Undo / 全消し のツールバー -->
        <div class="eraser-row">
          <button class="tool-btn" class:active={!isEraser} onclick={() => { isEraser = false; }}><Pencil size={12} /> ペン</button>
          <button class="tool-btn" class:active={isEraser}  onclick={() => { isEraser = true; }}><Eraser size={12} /> 消しゴム</button>
          <button class="tool-btn" onclick={() => penCanvasComp?.undo()}><Undo2 size={12} /> Undo</button>
          <button class="tool-btn danger" onclick={() => penCanvasComp?.clear()}><Trash2 size={12} /> 全消し</button>
        </div>
        <PenPalette
          bind:selectedPenId
          bind:penColor
          bind:penSize
          bind:penOpacity
        />
      {:else if activeTab === 'stamp'}
        <StampPanel onStampSelect={addStamp} />
      {:else}
        <RetouchSliders />
        <div class="retouch-actions">
          <button
            class="ai-retouch-btn"
            onclick={applyAiRetouch}
            disabled={isRetouching || !state.capturedFrames[currentPhotoIdx]}
          >
            {#if isRetouching}
              <span class="spin"><LoaderCircle size={16} /></span> AI 処理中…
            {:else}
              <WandSparkles size={16} /> AI レタッチ適用
            {/if}
          </button>
          {#if retouchedPhotos[currentPhotoIdx]}
            <!-- AI レタッチ済みのとき「元に戻す」ボタンを表示 -->
            <button
              class="reset-retouch-btn"
              onclick={() => {
                retouchedPhotos[currentPhotoIdx] = null;
                retouchedPhotos = retouchedPhotos; // リアクティビティ発火
                tick().then(drawBackground);
              }}
            >
              元に戻す
            </button>
          {/if}
          {#if retouchError}
            <p class="retouch-error">{retouchError}</p>
          {/if}
        </div>
      {/if}
    </div>
  </aside>

  <!-- 中央: Canvas エリア -->
  <main class="canvas-area">
    <!-- 写真セレクタ（タブ形式） -->
    <div class="photo-tabs">
      {#each state.capturedFrames as _, i}
        <button
          class="photo-tab"
          class:active={currentPhotoIdx === i}
          class:retouched={!!retouchedPhotos[i]}
          onclick={() => { currentPhotoIdx = i; }}
        >
          <img src={state.capturedFrames[i]} alt={`frame ${i+1}`} />
          <span>{i + 1}</span>
          {#if retouchedPhotos[i]}<div class="ai-badge">AI</div>{/if}
        </button>
      {/each}
    </div>

    <!-- 4層の Canvas スタック -->
    {#if isBgReplacing}
      <div class="bg-replacing-badge"><span class="spin"><LoaderCircle size={14} /></span> 背景処理中…</div>
    {/if}
    <div bind:this={canvasAnimEl} class="canvas-anim-wrapper">
      <div class="canvas-scale-outer" style="width:{FRAME_W * canvasScale}px; height:{FRAME_H * canvasScale}px;">
    <div
      bind:this={canvasStackEl}
      role="application"
      aria-label="落書きキャンバス"
      class="canvas-stack"
      style="width:{FRAME_W}px; height:{FRAME_H}px; transform:scale({canvasScale}); transform-origin:top left;"
      onmousemove={onCanvasMouseMove}
      onmouseup={onCanvasMouseUp}
      oncontextmenu={(e) => e.preventDefault()}
    >
      <!-- Layer 1: 写真 or 背景色 -->
      <canvas bind:this={bgCanvasEl} width={FRAME_W} height={FRAME_H} class="canvas-layer" style="z-index:1"></canvas>

      <!-- Layer 2: 落書き (PenCanvas) -->
      <div class="canvas-layer" style="z-index:2">
        <PenCanvas
          bind:this={penCanvasComp}
          width={FRAME_W}
          height={FRAME_H}
          {selectedPenId}
          {penColor}
          {penSize}
          {penOpacity}
          {isEraser}
          disabled={activeTab !== 'pen'}
        />
      </div>

      <!-- Layer 3: スタンプ
           コンテナ div は pointer-events:none で常に透過。
           個々のスタンプ要素だけが pointer-events:auto（消しゴム時は none）。
           これにより「スタンプのない場所」で PenCanvas が描画を受け取れる。 -->
      <div class="canvas-layer stamps-layer" style="z-index:3; pointer-events:none;">
        {#each stamps as stamp}
          <div
            role="button"
            tabindex="0"
            aria-label="スタンプ"
            class="stamp-item"
            class:selected={selectedStampId === stamp.id}
            style="left:{stamp.x}px; top:{stamp.y}px; width:{stamp.stampW ?? stamp.size}px; height:{stamp.size}px; transform:rotate({stamp.rotation}deg); transform-origin:center; pointer-events:{isEraser ? 'none' : 'auto'};"
            onmousedown={(e) => onStampMouseDown(e, stamp)}
            onwheel={(e) => onStampWheel(e, stamp)}
          >
            {@html stamp.svg}
            {#if selectedStampId === stamp.id && !isEraser}
              <div class="handle handle-tl" onmousedown={(e) => onResizeHandleMouseDown(e, stamp)}></div>
              <div class="handle handle-tr" onmousedown={(e) => onResizeHandleMouseDown(e, stamp)}></div>
              <div class="handle handle-bl" onmousedown={(e) => onResizeHandleMouseDown(e, stamp)}></div>
              <div class="handle handle-br" onmousedown={(e) => onResizeHandleMouseDown(e, stamp)}></div>
              <div class="handle handle-rotate" onmousedown={(e) => onRotateHandleMouseDown(e, stamp)}></div>
              <button
                class="stamp-delete-btn"
                aria-label="スタンプを削除"
                onmousedown={(e) => { e.stopPropagation(); e.preventDefault(); stamps = stamps.filter(s => s.id !== stamp.id); selectedStampId = null; }}
              >✕</button>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Layer 4: フレームオーバーレイ（pointer-events:none で常に透過） -->
      <canvas bind:this={frameCanvasEl} width={FRAME_W} height={FRAME_H} class="canvas-layer" style="z-index:4; pointer-events:none"></canvas>
    </div>
      </div>
    </div>

    <!-- アクション行 -->
    <div class="action-row">
      <button class="action-btn secondary" onclick={goBack}><RotateCcw size={16} /> 撮り直す</button>
      <button class="action-btn primary" onclick={saveSticker} disabled={isSaving}>
        {#if isSaving}<span class="spin"><LoaderCircle size={16} /></span> 保存中…
        {:else if saveSuccess}<span class="save-success-hint">✓ 保存しました！</span>
        {:else}<Printer size={16} /> シールとして保存
        {/if}
      </button>
    </div>
    <a class="music-credit" href="https://moerumusic.com" target="_blank" rel="noopener noreferrer"><Music size={10} /> moeru music.</a>
  </main>
</div>

<style>
  .edit-screen {
    display: flex;
    height: 100vh;
    background: linear-gradient(160deg, #FFF0F8 0%, #F0E8FF 100%);
    overflow: hidden;
  }

  .left-panel {
    width: 260px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background: white;
    box-shadow: 2px 0 12px rgba(0,0,0,0.08);
    overflow: hidden;
  }

  .tab-bar {
    display: flex;
    border-bottom: 2px solid #FFE0F0;
    flex-shrink: 0;
  }
  .tab-btn {
    flex: 1;
    padding: 10px 4px;
    border: none;
    background: white;
    font-size: 0.65rem;
    font-weight: 700;
    color: #AAA;
    cursor: pointer;
    transition: all 0.2s;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
  }
  .tab-btn.active {
    color: #C060A0;
    border-bottom-color: #F0A0C0;
    background: #FFF8FC;
  }

  .panel-content {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .eraser-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }
  .tool-btn {
    padding: 6px 4px;
    border-radius: 8px;
    border: 2px solid #E8C0D8;
    background: white;
    font-size: 0.65rem;
    font-weight: 600;
    color: #888;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
  }
  .tool-btn:hover { background: #FFF0F8; }
  .tool-btn.active {
    background: linear-gradient(135deg, #F0A0C0, #D4A0F0);
    border-color: transparent;
    color: white;
  }
  .tool-btn.danger { border-color: #FFB3B3; color: #E05050; }
  .tool-btn.danger:hover { background: #FFE8E8; }

  .retouch-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 4px;
  }
  .ai-retouch-btn {
    width: 100%;
    padding: 10px;
    border-radius: 12px;
    border: none;
    background: linear-gradient(135deg, #74B9FF, #A29BFE);
    color: white;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .ai-retouch-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(116,185,255,0.5); }
  .ai-retouch-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
  .reset-retouch-btn {
    width: 100%;
    padding: 6px;
    border-radius: 10px;
    border: 2px solid #E8C0D8;
    background: white;
    color: #C060A0;
    font-size: 0.7rem;
    cursor: pointer;
  }
  .retouch-error {
    font-size: 0.6rem;
    color: #E05050;
    margin: 0;
    line-height: 1.4;
  }

  .canvas-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 16px;
    overflow: auto;
  }

  .photo-tabs {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    max-width: 100%;
    padding: 4px 4px 8px;
  }
  .photo-tab {
    position: relative;
    width: 50px;
    height: 38px;
    border-radius: 8px;
    border: 3px solid transparent;
    overflow: visible;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
    transition: all 0.15s;
  }
  .photo-tab.active { border-color: #F0A0C0; box-shadow: 0 0 8px rgba(240,160,192,0.5); }
  .photo-tab.retouched { border-color: #74B9FF; }
  .photo-tab.active.retouched { border-color: #A29BFE; }
  .photo-tab img { width: 100%; height: 100%; object-fit: cover; border-radius: 5px; }
  .photo-tab span {
    position: absolute; bottom: 1px; right: 3px;
    font-size: 0.6rem; color: white; font-weight: 700;
    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
  }
  .ai-badge {
    position: absolute; top: -6px; left: -4px;
    background: #74B9FF; color: white;
    font-size: 0.45rem; font-weight: 800;
    padding: 1px 4px; border-radius: 4px;
  }

  .canvas-anim-wrapper {
    flex-shrink: 0;
  }
  .canvas-scale-outer {
    position: relative;
    overflow: hidden;
    border-radius: 8px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.2);
  }
  .canvas-stack {
    position: relative;
    overflow: hidden;
  }
  /* 全レイヤーを同じ位置に重ねるために position:absolute を使う */
  .canvas-layer {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
  }
  .stamps-layer { overflow: visible; }
  .stamp-item {
    position: absolute;
    cursor: move;
    user-select: none;
  }
  .stamp-item :global(svg) { width: 100%; height: 100%; }
  .stamp-item.selected {
    filter: drop-shadow(0 0 5px rgba(240, 160, 192, 0.9));
  }

  .handle {
    position: absolute;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: white;
    border: 2px solid #F0A0C0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.25);
    z-index: 10;
    pointer-events: auto;
  }
  .handle-tl { top: -6px;  left: -6px;  cursor: nwse-resize; }
  .handle-tr { top: -6px;  right: -6px; cursor: nesw-resize; }
  .handle-bl { bottom: -6px; left: -6px;  cursor: nesw-resize; }
  .handle-br { bottom: -6px; right: -6px; cursor: nwse-resize; }
  .handle-rotate {
    top: -28px;
    left: 50%;
    transform: translateX(-50%);
    cursor: grab;
    border-color: #74B9FF;
    background: #EBF5FF;
  }
  .handle-rotate:active { cursor: grabbing; }

  .stamp-delete-btn {
    position: absolute;
    top: -10px;
    right: -10px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 2px solid white;
    background: #FF4B4B;
    color: white;
    font-size: 9px;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    transition: transform 0.1s;
    pointer-events: auto;
  }
  .stamp-delete-btn:hover {
    transform: scale(1.2);
    background: #E03030;
  }

  .action-row {
    display: flex;
    gap: 12px;
    margin-top: 4px;
  }
  .action-btn {
    padding: 12px 24px;
    border-radius: 100px;
    border: none;
    font-size: 0.9rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .action-btn.primary {
    background: linear-gradient(135deg, #FF85A1, #C070E0);
    color: white;
    box-shadow: 0 4px 16px rgba(255,133,161,0.4);
  }
  .action-btn.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(255,133,161,0.5);
  }
  .action-btn.secondary {
    background: white;
    color: #C060A0;
    border: 2px solid #F0A0C0;
  }
  .action-btn:disabled { opacity: 0.7; cursor: not-allowed; transform: none !important; }

  .save-success-hint { color: white; }

  .music-credit {
    font-size: 0.6rem;
    color: #C8A0C0;
    text-decoration: none;
    opacity: 0.75;
    letter-spacing: 0.04em;
    margin-top: 2px;
    display: flex;
    align-items: center;
    gap: 3px;
  }
  .music-credit:hover { opacity: 1; text-decoration: underline; }

  .spin {
    display: inline-flex;
    animation: spin-anim 1s linear infinite;
  }
  @keyframes spin-anim {
    to { transform: rotate(360deg); }
  }

  .bg-replacing-badge {
    font-size: 0.68rem;
    font-weight: 600;
    color: #C060A0;
    background: rgba(255,240,252,0.92);
    border: 1px solid #F0A0C0;
    border-radius: 100px;
    padding: 4px 12px;
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    gap: 4px;
  }

  @media (max-width: 767px) {
    .edit-screen {
      flex-direction: column;
      height: 100dvh;
    }

    .left-panel {
      order: 2;
      width: 100%;
      height: auto;
      max-height: 44vh;
      box-shadow: 0 -2px 12px rgba(0,0,0,0.08);
    }

    .tab-btn {
      font-size: 0.6rem;
      padding: 8px 2px;
    }

    .canvas-area {
      order: 1;
      flex: 1 1 auto;
      padding: 8px;
      gap: 6px;
      overflow: hidden;
      justify-content: flex-start;
    }

    .photo-tabs {
      padding: 2px 2px 4px;
      gap: 4px;
    }
    .photo-tab {
      width: 40px;
      height: 30px;
    }

    .action-row {
      margin-top: 2px;
      gap: 8px;
    }
    .action-btn {
      padding: 9px 16px;
      font-size: 0.78rem;
    }
  }
</style>
