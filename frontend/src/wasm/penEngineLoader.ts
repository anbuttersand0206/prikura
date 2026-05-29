// ============================================================
// penEngineLoader.ts — Wasm ペンエンジンのローダー
//
// C++ で実装したペン補間ロジック (pen_engine.wasm) を
// 動的にロードして使えるようにします。
// Wasm が存在しない環境（ビルドしていない場合など）では、
// 自動的に JavaScript 純正実装（catmullRom）に切り替えます。
//
// 【初心者向け補足】
// Wasm（WebAssembly）は C++ などで書いたコードをブラウザで
// 高速に動かす仕組みです。JS より速いですが、ビルドが必要なので
// 未ビルドのときのフォールバック（代替処理）が重要です。
// ============================================================

import { catmullRom } from '../pens/index';
import type { Point } from '../pens/index';

/**
 * ペンエンジンの共通インターフェース。
 * Wasm 版も JS 版も同じ型で使えるようにする。
 */
type WasmModule = {
  /** 入力点列を Catmull-Rom スプライン補間して滑らかな点列を返す */
  catmullRomInterpolate: (pts: Point[], tension?: number) => Point[];
  /** true なら Wasm 版、false なら JS フォールバック版 */
  isWasm: boolean;
};

/** ロード済みのエンジンをキャッシュする変数（2回目以降は再ロード不要） */
let _cachedEngine: WasmModule | null = null;

const TAG = '[PenEngine]';

/**
 * Wasm モジュールのロードを試みる。
 * ロードに失敗した場合（ファイルが存在しない・対応ブラウザでないなど）は
 * null を返す。エラーは握りつぶして呼び出し元に null で通知する。
 */
async function tryLoadWasm(): Promise<WasmModule | null> {
  try {
    // 動的インポート — .wasm が存在しない場合ここで例外が発生する
    const PenEngineFactory = await import('./pen_engine.js' as string) as any;
    // Emscripten が生成したファクトリ関数を呼んでモジュールを初期化
    const mod = await PenEngineFactory.default();

    // C++ 関数を JS から呼べるようにラップ（cwrap = C function wrap）
    // 引数: (関数名, 戻り値型, [引数型の配列])
    const interpolateFn = mod.cwrap('catmull_rom_interpolate', 'number', [
      'number', 'number', 'number', 'number', 'number',
    ]);

    return {
      isWasm: true,
      /**
       * Wasm 版の補間関数。
       * Wasm のメモリに点列を書き込み → C++ 関数を呼ぶ → 結果を読み返す。
       *
       * 【メモリ操作の仕組み】
       * Wasm は独自のメモリ（共有バッファ）を持つ。
       * _malloc でメモリを確保して Float32 配列として書き込み、
       * 処理後に _free で解放する（C の malloc/free と同じ）。
       */
      catmullRomInterpolate(pts: Point[], tension = 0.5): Point[] {
        const n = pts.length;
        if (n < 2) return pts;

        const maxOut = n * 25; // 出力点の最大数（入力1点につき最大25点補間）

        // 入力バッファ: [x0, y0, x1, y1, ...] の Float32 配列
        const inBuf = mod._malloc(n * 2 * 4);   // float32 = 4バイト
        // 出力バッファ: 補間後の点列用
        const outBuf = mod._malloc(maxOut * 2 * 4);

        const heap = mod.HEAPF32; // Wasm のメモリを Float32 として参照

        // JS の Point[] → Wasm メモリに書き込む
        // >> 2 は「バイトアドレスを Float32 インデックスに変換」する操作
        for (let i = 0; i < n; i++) {
          heap[(inBuf >> 2) + i * 2]     = pts[i].x;
          heap[(inBuf >> 2) + i * 2 + 1] = pts[i].y;
        }

        // C++ 関数を呼ぶ。返り値は実際に書き込まれた点の数
        const count = interpolateFn(inBuf, n, outBuf, maxOut, tension);

        // Wasm メモリから結果を読み取って JS の Point[] に変換
        const result: Point[] = [];
        for (let i = 0; i < count; i++) {
          result.push({
            x: heap[(outBuf >> 2) + i * 2],
            y: heap[(outBuf >> 2) + i * 2 + 1],
          });
        }

        // メモリ解放（忘れると Wasm ヒープが枯渇する）
        mod._free(inBuf);
        mod._free(outBuf);
        return result;
      },
    };
  } catch (err) {
    console.warn(`${TAG} ⚠️ Wasm ロード失敗 — TypeScript 版にフォールバック`, err);
    return null;
  }
}

/**
 * ペンエンジンを取得する。初回は Wasm ロードを試み、
 * 失敗した場合は JS 版にフォールバックする。
 * 2回目以降はキャッシュ済みのエンジンをそのまま返す。
 */
export async function getPenEngine(): Promise<WasmModule> {
  if (_cachedEngine) return _cachedEngine; // キャッシュがあれば即返す

  const wasm = await tryLoadWasm();

  if (wasm) {
    _cachedEngine = wasm;
  } else {
    // Wasm が使えない場合は TypeScript 実装にフォールバックして継続する
    _cachedEngine = { isWasm: false, catmullRomInterpolate: catmullRom };
  }

  return _cachedEngine;
}

/** 切り替えログを1回だけ出すためのフラグ（二重ログ防止） */
let _hasSwitchLogged = false;

/**
 * 同期的にスプライン補間を行う。
 * Wasm がロード済みならば Wasm 版、未ロードなら JS フォールバックを使う。
 * ペンの render() は同期関数なので、このラッパーを介して呼ぶ。
 */
export function interpolate(pts: Point[], tension = 0.5): Point[] {
  if (_cachedEngine) {
    if (!_hasSwitchLogged) {
      _hasSwitchLogged = true;
      const label = _cachedEngine.isWasm ? 'C++ Wasm 版' : 'TypeScript 版';
      console.info(`${TAG} 補間エンジン確定: ${label}`);
    }
    return _cachedEngine.catmullRomInterpolate(pts, tension);
  }
  return catmullRom(pts, tension); // Wasm 未ロード時のフォールバック
}

/**
 * アプリ起動時に Wasm を非同期で先読みする（fire-and-forget）。
 * onMount などで呼ぶことで、最初のペン操作より前に Wasm を準備できる。
 * 読み込みが完了すると以降の interpolate() 呼び出しが自動的に Wasm 版になる。
 */
export async function initPenEngine(): Promise<void> {
  await getPenEngine();
}
