import { writable } from 'svelte/store';

export type Phase = 'setup' | 'camera' | 'edit';

export type FrameDesign = {
  id: string; name: string; color: string; accent: string; borderStyle: string;
};
export type BgColor = { id: string; name: string; value: string; };

export const FRAME_DESIGNS: FrameDesign[] = [
  { id: 'f1', name: 'ピンクハート',   color: '#FFB7C5', accent: '#FF85A1', borderStyle: 'hearts' },
  { id: 'f2', name: 'ラベンダー',     color: '#C9B8F0', accent: '#9B8FD0', borderStyle: 'stars' },
  { id: 'f3', name: 'ミントフレッシュ', color: '#B5EAD7', accent: '#7DC9AB', borderStyle: 'flowers' },
  { id: 'f4', name: 'サニーイエロー', color: '#FFEAA7', accent: '#F0C050', borderStyle: 'dots' },
  { id: 'f5', name: 'スカイブルー',   color: '#AED6F1', accent: '#6BB8E0', borderStyle: 'clouds' },
  { id: 'f6', name: 'ピーチベージュ', color: '#FFDAB9', accent: '#E8A878', borderStyle: 'ribbons' },
  { id: 'f7', name: 'チェリーレッド', color: '#FFB3B3', accent: '#FF6B6B', borderStyle: 'cherries' },
  { id: 'f8', name: 'モカブラウン',   color: '#D4B896', accent: '#A07850', borderStyle: 'simple' },
];

export const BG_COLORS: BgColor[] = [
  { id: 'bg1', name: 'ピンク',     value: '#FFD6E0' },
  { id: 'bg2', name: 'ラベンダー', value: '#E8D5F5' },
  { id: 'bg3', name: 'ミント',     value: '#D5F5E3' },
  { id: 'bg4', name: 'イエロー',   value: '#FFF9C4' },
  { id: 'bg5', name: '空色',       value: '#D6EAF8' },
  { id: 'bg6', name: 'ピーチ',     value: '#FDEBD0' },
  { id: 'bg7', name: 'ホワイト',   value: '#FFFFFF' },
  { id: 'bg8', name: 'ローズ',     value: '#FADBD8' },
];

/**
 * 美容加工パラメータ。
 * 0–100 は単方向（0 = なし、100 = 最大）。
 * -100–+100 は双方向（0 = なし、正/負で方向が変わる）。
 * バックエンドへは /100 して 0–1 / -1–+1 に正規化して送る。
 */
export type BeautySettings = {
  // 肌・テクスチャ
  smoothing:      number;   // 美肌          0–100
  sharpness:      number;   // シャープネス   0–100
  skinBrightness: number;   // 明るさ      -100–+100
  skinWarmth:     number;   // 色温度      -100–+100
  whitening:      number;   // 美白          0–100
  darkCircle:     number;   // クマ消し       0–100
  // 顔形
  faceSlim:    number;   // 顔痩せ      -100–+100
  headSize:    number;   // 頭サイズ    -100–+100
  midFace:     number;   // 中顔面短縮  -100–+100
  cheekWidth:  number;   // 頬横幅      -100–+100
  jaw:         number;   // エラ削り    -100–+100
  chinLength:  number;   // 顎縦幅      -100–+100
  // 鼻
  noseWidth:  number;   // 小鼻サイズ  -100–+100
  noseHeight: number;   // 鼻縦幅      -100–+100
  // 目
  eyeSize:     number;   // 目のサイズ  -100–+100
  eyePosition: number;   // 目の位置    -100–+100
  irisSize:    number;   // 黒目サイズ  -100–+100
  eyeTilt:     number;   // タレ目/つり目 -100–+100
  eyeSparkle:  number;   // 目の反射      0–100
  // 口
  mouthSize:      number;   // 口サイズ      -100–+100
  mouthCorner:    number;   // 口角          -100–+100
  philtrum:       number;   // 人中          -100–+100
  teethWhitening: number;   // 歯ホワイトニング 0–100
  // メイク
  cheekColor:    string;
  cheekStrength: number;   // 0–100
  lipColor:      string;
  lipStrength:   number;   // 0–100
  tearBag:       number;   // 0–100
};

export const defaultBeauty: BeautySettings = {
  smoothing: 0, sharpness: 0, skinBrightness: 0, skinWarmth: 0, whitening: 0,
  darkCircle: 0,
  faceSlim: 0, headSize: 0, midFace: 0, cheekWidth: 0, jaw: 0, chinLength: 0,
  noseWidth: 0, noseHeight: 0,
  eyeSize: 0, eyePosition: 0, irisSize: 0, eyeTilt: 0, eyeSparkle: 0,
  mouthSize: 0, mouthCorner: 0, philtrum: 0, teethWhitening: 0,
  cheekColor: '#FFB7C5', cheekStrength: 0,
  lipColor: '#FF6B9D', lipStrength: 0,
  tearBag: 0,
};

// ファクトリ関数パターンを使う理由:
// Svelte の writable ストアを直接 export すると内部 state が外から直接 set() できてしまう。
// ファクトリでメソッド（setPhase 等）だけを公開することで、
// 状態変更の経路を限定し、意図しない上書きを防ぐ。
function createAppState() {
  const { subscribe, set, update } = writable({
    phase: 'setup' as Phase,
    selectedFrame: FRAME_DESIGNS[0],
    selectedBg: BG_COLORS[0],
    shootCount: 6 as 6 | 8 | 10,
    capturedFrames: [] as string[],
    beauty: { ...defaultBeauty },
  });

  return {
    subscribe,
    setPhase:      (phase: Phase)       => update(s => ({ ...s, phase })),
    setFrame:      (frame: FrameDesign) => update(s => ({ ...s, selectedFrame: frame })),
    setBg:         (bg: BgColor)        => update(s => ({ ...s, selectedBg: bg })),
    setShootCount: (n: 6 | 8 | 10)     => update(s => ({ ...s, shootCount: n })),
    addFrame:      (dataUrl: string)    => update(s => ({
      ...s, capturedFrames: [...s.capturedFrames, dataUrl],
    })),
    resetFrames: () => update(s => ({ ...s, capturedFrames: [] })),
    updateBeauty: (r: Partial<BeautySettings>) => update(s => ({
      ...s, beauty: { ...s.beauty, ...r },
    })),
    resetBeauty: () => update(s => ({ ...s, beauty: { ...defaultBeauty } })),
  };
}

export const appState = createAppState();
