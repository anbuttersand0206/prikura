// ============================================================
// pens/index.ts — ペン共通の型定義・補間関数・カラーパレット
//
// 全20種ペンが共通で使う「型」「スプライン補間」「カラー一覧」を
// このファイルにまとめています。
// 各グループ（group1〜4）はここの型・関数を import して使います。
// ============================================================

// ── 型定義 ────────────────────────────────────────────────────

/** 2D座標を表す型。Canvas の座標系で使う（左上が原点）。 */
export type Point = { x: number; y: number };

/**
 * ペン1種類分の設定と描画関数をまとめた型。
 * 各グループファイルで PenConfig[] の配列として定義される。
 */
export interface PenConfig {
  id: string;        // 内部識別子（例: 'normal', 'neon_outline'）
  name: string;      // 表示名（例: 'ノーマル', 'ネオンふち'）
  group: number;     // グループ番号（1〜4）
  baseSize: number;  // デフォルトのペンサイズ（px）
  color: string;     // デフォルトのペンカラー（CSS カラー文字列）
  opacity: number;   // デフォルトの不透明度（0.0〜1.0）

  /**
   * 実際に Canvas に描画する関数。
   * @param ctx     - 描画先の 2D コンテキスト
   * @param points  - ユーザーがなぞった座標の生データ
   * @param size    - ユーザーが選択したサイズ
   * @param color   - ユーザーが選択した色
   * @param opacity - ユーザーが選択した不透明度
   */
  render: (
    ctx: CanvasRenderingContext2D,
    points: Point[],
    size: number,
    color: string,
    opacity: number,
  ) => void;

  /** PenPalette のプレビュー用の SVG パス（省略可） */
  previewPath?: string;
}

// ── Catmull-Rom スプライン補間 ────────────────────────────────

/**
 * Catmull-Rom スプライン補間。
 * ユーザーが指でなぞったガタガタの点列を、なめらかな曲線の点列に変換する。
 *
 * 【アルゴリズムの概要】
 * 4点 P0〜P3 を使って P1〜P2 間をなめらかに補間する。
 * tension（張力）パラメータが大きいほど角張った曲線になり、
 * 小さいほど丸くゆるい曲線になる。
 *
 * 【数式: Hermite 形式の Catmull-Rom】
 * 各区間で接線ベクトル m を求め、3次 Hermite 曲線で点を生成する。
 *   m_1 = tension × (P2 - P0)  ← P1 での接線
 *   m_2 = tension × (P3 - P1)  ← P2 での接線
 *   P(t) = h1·P1 + h2·m1 + h3·P2 + h4·m2  (0 ≤ t ≤ 1)
 * ここで h1〜h4 は Hermite 基底関数（t の 3次多項式）。
 *
 * 【なぜ端点を複製するのか】
 * 最初の区間（P0〜P1 間）と最後の区間（Pn-1〜Pn 間）でも
 * 同じ式を使えるよう、両端に同じ点を追加して「幽霊点」として使う。
 *
 * @param points  - 入力点列（マウス/タッチの生座標）
 * @param tension - 張力 (0.0〜1.0、標準値 0.5)
 * @returns 補間後の滑らかな点列
 */
export function catmullRom(points: Point[], tension = 0.5): Point[] {
  if (points.length < 2) return points;
  if (points.length === 2) return points;

  const result: Point[] = [];

  // 両端に同じ点を複製して追加（端の補間を安定させるため）
  const pts = [points[0], ...points, points[points.length - 1]];

  for (let i = 1; i < pts.length - 2; i++) {
    const p0 = pts[i - 1], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2];

    // 接線ベクトルを計算（tension を掛けることで曲線の「伸び具合」を制御）
    const m1x = tension * (p2.x - p0.x), m1y = tension * (p2.y - p0.y); // P1 の接線
    const m2x = tension * (p3.x - p1.x), m2y = tension * (p3.y - p1.y); // P2 の接線

    // t を 0〜1 で刻んで区間内の補間点を生成（0.05刻み = 1区間に最大21点）
    for (let t = 0; t <= 1; t += 0.05) {
      const t2 = t * t, t3 = t2 * t;

      // Hermite 基底関数（t の 3次多項式）
      const h1 = 2*t3 - 3*t2 + 1; // t=0 で 1、t=1 で 0
      const h2 = t3 - 2*t2 + t;   // 接線項（P1 側）
      const h3 = -2*t3 + 3*t2;    // t=0 で 0、t=1 で 1
      const h4 = t3 - t2;          // 接線項（P2 側）

      result.push({
        x: h1*p1.x + h2*m1x + h3*p2.x + h4*m2x,
        y: h1*p1.y + h2*m1y + h3*p2.y + h4*m2y,
      });
    }
  }

  // 最後の点を追加（ループでは最終点まで到達しないため手動追加）
  result.push(points[points.length - 1]);
  return result;
}

/**
 * 補間済みの点列を Canvas に描画するユーティリティ。
 * 各グループのペンが内部で使う場合に便利。
 */
function drawSmooth(ctx: CanvasRenderingContext2D, points: Point[], tension = 0.5) {
  const smooth = catmullRom(points, tension);
  if (smooth.length < 2) return;
  ctx.beginPath();
  ctx.moveTo(smooth[0].x, smooth[0].y);
  for (let i = 1; i < smooth.length; i++) {
    ctx.lineTo(smooth[i].x, smooth[i].y);
  }
  ctx.stroke();
}

// ── カラーパレット ────────────────────────────────────────────

/**
 * ペンパレットに表示する 24 色。
 * ピンク・パープル・ブルー系を中心に、
 * ホワイト・グレー・ダーク系も含めてバランスを取っている。
 */
export const PALETTE_COLORS = [
  '#FF85A1', '#FF6B6B', '#FF9F43', '#FFEAA7', '#A8E6CF',
  '#74B9FF', '#A29BFE', '#FD79A8', '#E17055', '#00B894',
  '#0984E3', '#6C5CE7', '#FFFFFF', '#F8F9FA', '#DEE2E6',
  '#ADB5BD', '#495057', '#212529', '#FF99CC', '#CC99FF',
  '#99CCFF', '#99FFCC', '#FFCC99', '#FF6699',
];
