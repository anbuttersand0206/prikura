<script lang="ts">
  // ============================================================
  // StampPanel.svelte — スタンプ & テキストパネル
  //
  // プリセットスタンプ（12種）と、ユーザーが入力したテキストを
  // SVG 形式でスタンプとして Edit.svelte に渡すパネル。
  //
  // 【SVG をスタンプとして使う理由】
  // SVG はベクター形式なので拡大縮小しても品質が落ちない。
  // また画像ファイル不要で、テキストも動的に生成できる。
  //
  // 【フォント埋め込みの仕組み】
  // SVG を <img> として canvas に描画する場合、ページの CSS フォントは
  // 参照できない。そのため、フォントファイルを base64 に変換して
  // SVG の <defs><style>@font-face{...}</style></defs> に埋め込む。
  // M PLUS Rounded 1c は Google Fonts なので埋め込みせず sans-serif にフォールバック。
  // ============================================================

  import { onMount } from 'svelte';

  // ── props ────────────────────────────────────────────────────
  let {
    onStampSelect, // スタンプが選ばれたとき呼ばれるコールバック
  }: {
    onStampSelect?: (svg: string) => void;
  } = $props();

  // ── フォント定義 ─────────────────────────────────────────────
  // url: Vite プラグインで /fonts/ に配信されるパス。
  //      null の場合はファイル埋め込みなし（CSS フォントを使用）。
  type FontDef = { label: string; name: string; url: string | null };
  const FONTS: FontDef[] = [
    { label: 'M PLUS Rounded 1c', name: 'M PLUS Rounded 1c', url: null },
    { label: 'はちまるポップ', name: 'HachiMaruPop', url: '/fonts/Hachi_Maru_Pop/HachiMaruPop-Regular.ttf' },
    { label: '平成女児★ふぉんと',     name: 'HeiseijyojiFont',  url: '/fonts/HeiseijyojiFont/HeiseijyojiFont.otf' },
  ];

  // フォント選択状態（初期値: まるゴシック）
  let selectedFont = $state<FontDef>(FONTS[0]);

  // フォントロード完了カウンター（増加するとフォントボタンが再描画される）
  let _fontLoadCount = $state(0);

  // base64 キャッシュ: url → { dataUrl, format }
  // SVG 生成のたびにフォントファイルを再取得しないために使う。
  const fontCache = new Map<string, { dataUrl: string; format: string }>();

  // ロード済みフォント名のセット
  // document.fonts.check() はフォールバックで描画できる場合も true を返すため
  // 独自にロード済みを管理する
  const loadedFontNames = new Set<string>();

  /** フォントファイルを取得して base64 データ URL に変換する（キャッシュあり） */
  async function loadFont(url: string): Promise<{ dataUrl: string; format: string }> {
    if (fontCache.has(url)) return fontCache.get(url)!;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Font fetch failed: ${res.status} ${url}`);
    const buf = await res.arrayBuffer();
    // btoa へ直接スプレッドすると大きいファイルでスタックオーバーフローするため
    // ループで文字列を組み立てる。
    const bytes = new Uint8Array(buf);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    const b64 = btoa(binary);
    const isOtf = url.endsWith('.otf');
    const result = {
      dataUrl: `data:font/${isOtf ? 'otf' : 'ttf'};base64,${b64}`,
      format: isOtf ? 'opentype' : 'truetype',
    };
    fontCache.set(url, result);
    return result;
  }

  /**
   * フォントを document.fonts に確実にロードする。
   * インライン SVG の <text> がフォント挿入前に確実に正しいフォントで描画されるよう、
   * FontFace API 経由でロードを完了してから SVG を生成する必要がある。
   * （@font-face を SVG defs に埋め込むだけだと非同期デコードによるタイミング問題が起きる）
   */
  async function ensureFontLoaded(name: string, dataUrl: string): Promise<void> {
    if (loadedFontNames.has(name)) return;
    const face = new FontFace(name, `url('${dataUrl}')`);
    await face.load();
    document.fonts.add(face);
    loadedFontNames.add(name);
  }

  /** SVG テキストに埋め込む特殊文字をエスケープする */
  function escapeXml(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /** テキストスタンプ SVG を生成して親に渡す */
  async function addTextStamp() {
    if (!textInput.trim()) return;

    const text = escapeXml(textInput);
    const charW = textSize * 1.1 + letterSpacing; // 1文字あたりの幅（letter-spacing は各文字後に加算）
    const svgW = Math.ceil(charW * textInput.length + textSize * 0.6);
    const svgH = Math.ceil(textSize * 1.3);

    let defs = '';
    const fontStyle = `font-family:'${selectedFont.name}',sans-serif;font-weight:700;letter-spacing:${letterSpacing}px;`;

    if (selectedFont.url) {
      const { dataUrl, format } = await loadFont(selectedFont.url);
      // canvas エクスポート用: Blob URL として img 読み込みする際に CSS は参照できないため
      // base64 @font-face を SVG に直接埋め込む
      defs = `<defs><style>@font-face{font-family:'${selectedFont.name}';src:url('${dataUrl}') format('${format}');}</style></defs>`;
      // DOM 表示用: SVG 挿入前にフォントを document.fonts にロード済みにする
      // これにより挿入直後から正しいフォントで描画される（タイミング問題の回避）
      await ensureFontLoaded(selectedFont.name, dataUrl);
    }

    onStampSelect?.(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${svgW} ${svgH}">${defs}` +
      `<text x="2" y="${textSize}" font-size="${textSize}" fill="${textColor}" ` +
      `style="${fontStyle}">${text}</text></svg>`
    );
    textInput = '';
  }

  // コンポーネントマウント時にカスタムフォントをページにも読み込む（フォントボタンのプレビュー用）。
  // loadFont 経由で data URL を取得してキャッシュし、FontFace API でロードする。
  // こうすることで addTextStamp 時に再 fetch が発生しない。
  onMount(() => {
    for (const url of STAMP_FILES) {
      loadStampDataUrl(url).catch(() => {});
    }
    for (const f of FONTS) {
      if (!f.url) continue;
      loadFont(f.url).then(({ dataUrl }) => {
        ensureFontLoaded(f.name, dataUrl)
          .then(() => { _fontLoadCount++; })
          .catch(() => {});
      }).catch(() => {});
    }
  });

  // ── プリセットスタンプ ────────────────────────────────────────
  const STAMP_FILES: string[] = Array.from({ length: 24 }, (_, i) =>
    `/stamps/${String(i + 1).padStart(3, '0')}.png`
  );

  const stampCache = new Map<string, string>(); // url → base64 data URL

  async function loadStampDataUrl(url: string): Promise<string> {
    if (stampCache.has(url)) return stampCache.get(url)!;
    const res = await fetch(url);
    const buf = await res.arrayBuffer();
    const bytes = new Uint8Array(buf);
    const CHUNK = 8192;
    let binary = '';
    for (let i = 0; i < bytes.length; i += CHUNK) {
      binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
    }
    const dataUrl = `data:image/png;base64,${btoa(binary)}`;
    stampCache.set(url, dataUrl);
    return dataUrl;
  }

  async function handleStampClick(url: string) {
    const dataUrl = await loadStampDataUrl(url);
    onStampSelect?.(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">` +
      `<image href="${dataUrl}" width="100" height="100"/>` +
      `</svg>`
    );
  }

  // ── テキストスタンプの状態 ────────────────────────────────────
  let textInput       = $state('');         // 入力中のテキスト
  let textColor       = $state('#FF85A1');  // テキストカラー
  let textSize        = $state(24);         // テキストサイズ（px）
  let letterSpacing   = $state(0);          // 字間（px、SVG letter-spacing と同単位）
  const TEXT_COLORS = ['#FF85A1','#A29BFE','#74B9FF','#00B894','#FFEAA7','#FF4081','#FFFFFF','#333333'];
</script>

<div class="stamp-panel">
  <div class="panel-title">スタンプ・テキスト</div>

  <!-- スタンプグリッド -->
  <div class="section-label">スタンプ</div>
  <div class="stamp-grid">
    {#each STAMP_FILES as url}
      <button class="stamp-btn" onclick={() => handleStampClick(url)}>
        <img src={url} alt="" />
      </button>
    {/each}
  </div>

  <!-- テキストスタンプ生成 -->
  <div class="section-label" style="margin-top:8px">テキスト</div>
  <div class="text-section">
    <!-- カラー選択 -->
    <div class="text-color-row">
      {#each TEXT_COLORS as c}
        <button
          class="color-dot"
          class:sel={textColor === c}
          style="background: {c}; {c==='#FFFFFF' ? 'border:2px solid #ccc' : ''}"
          aria-label={c}
          onclick={() => { textColor = c; }}
        ></button>
      {/each}
    </div>

    <!-- サイズスライダー -->
    <div class="text-size-row">
      <span>サイズ {textSize}px</span>
      <input type="range" min="12" max="72" bind:value={textSize} class="slider" />
    </div>

    <!-- 字間スライダー -->
    <div class="text-size-row">
      <span>字間 {letterSpacing}px</span>
      <input type="range" min="-4" max="20" bind:value={letterSpacing} class="slider" />
    </div>

    <!-- フォント選択 -->
    {#key _fontLoadCount}
    <div class="text-font-row">
      {#each FONTS as font}
        <button
          class="font-btn"
          class:sel={selectedFont.name === font.name}
          style="font-family: '{font.name}', sans-serif"
          onclick={() => { selectedFont = font; }}
        >{font.label}</button>
      {/each}
    </div>
    {/key}

    <!-- テキスト入力 + 追加ボタン -->
    <div class="text-input-row">
      <input
        type="text"
        bind:value={textInput}
        placeholder="テキストを入力…"
        class="text-field"
        maxlength="20"
      />
      <button
        class="add-text-btn"
        onclick={addTextStamp}
        disabled={!textInput.trim()}
      >
        追加
      </button>
    </div>
  </div>
</div>

<style>
  .stamp-panel {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    background: white;
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    overflow-y: auto;
    max-height: 100%;
  }

  .panel-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: #C060A0;
    text-align: center;
    padding: 4px 0;
    border-bottom: 2px solid #FFE0F0;
  }

  .section-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #C060A0;
  }

  .stamp-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 4px;
  }

  .stamp-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    padding: 4px;
    border-radius: 8px;
    border: 2px solid transparent;
    background: #FFF8FC;
    cursor: pointer;
    transition: all 0.15s;
  }
  .stamp-btn:hover {
    background: #FFE8F4;
    border-color: #F0A0C0;
    transform: scale(1.08);
  }
  .stamp-btn img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .text-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .text-color-row {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .color-dot {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    padding: 0;
    transition: all 0.15s;
  }
  .color-dot:hover { transform: scale(1.15); }
  .color-dot.sel {
    border-color: #C060A0;
    box-shadow: 0 0 0 2px rgba(192,96,160,0.3);
  }

  .text-size-row {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 0.65rem;
    color: #888;
  }
  .slider {
    -webkit-appearance: none;
    width: 100%;
    height: 5px;
    border-radius: 3px;
    background: linear-gradient(to right, #F0A0C0, #D4A0F0);
    outline: none;
  }
  .slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: white;
    border: 2px solid #F0A0C0;
    cursor: pointer;
  }

  .text-font-row {
    display: flex;
    gap: 4px;
  }
  .font-btn {
    flex: 1;
    padding: 5px 4px;
    border-radius: 8px;
    border: 2px solid transparent;
    background: #FFF8FC;
    cursor: pointer;
    font-size: 0.7rem;
    color: #555;
    transition: all 0.15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .font-btn:hover {
    background: #FFE8F4;
    border-color: #F0A0C0;
  }
  .font-btn.sel {
    border-color: transparent;
    background: linear-gradient(135deg, #F0A0C0, #D4A0F0);
    color: white;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(240,160,192,0.5);
  }

  .text-input-row {
    display: flex;
    gap: 6px;
  }
  .text-field {
    flex: 1;
    padding: 6px 10px;
    border: 2px solid #F0D0E0;
    border-radius: 10px;
    font-size: 0.8rem;
    outline: none;
    font-family: inherit;
  }
  .text-field:focus {
    border-color: #F0A0C0;
  }
  .add-text-btn {
    padding: 6px 10px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, #F0A0C0, #D4A0F0);
    color: white;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
  }
  .add-text-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
