<script lang="ts">
  import { appState, defaultBeauty } from '../stores/appState';
  import { Droplets, ScanFace, Scan, Eye, Smile, Paintbrush } from 'lucide-svelte';

  let state = $appState;
  $: state = $appState;
  $: b = state?.beauty ?? defaultBeauty;

  const LIP_COLORS   = ['#FF6B9D', '#E91E63', '#FF8A80', '#F48FB1', '#EF9A9A', '#D81B60', '#FF4081', '#F06292'];
  const CHEEK_COLORS = ['#FFB7C5', '#FF8A80', '#F8BBD0', '#FFCDD2', '#FFE0B2', '#FFA0B0', '#FFB0D8', '#FFC0D0'];

  // Svelte 5 proxy から文字列を取り出して比較に使う
  $: currentCheekColor = String(b.cheekColor);
  $: currentLipColor   = String(b.lipColor);

  // 「肌」セクションだけを初期開放する。
  // 肌補正は最も使用頻度が高く、開いた状態でスクロールを始める UX にしている。
  let open = new Set<string>(['skin']);

  function toggle(id: string) {
    open.has(id) ? open.delete(id) : open.add(id);
    open = open; // Svelte のリアクティビティを発火させるための再代入
  }

  /** スライダー値を appState に反映する。テンプレートから頻繁に呼ばれるため短い名前にしている。 */
  function updateParam(key: string, val: number | string) {
    appState.updateBeauty({ [key]: val } as any);
  }

  /** 正負を明示した文字列に変換する（+10, -5 のように表示するため）。 */
  function formatSigned(v: number) { return v > 0 ? `+${v}` : `${v}`; }
</script>

<div class="beauty-panel">

  <!-- 肌 -->
  <div class="section">
    <button class="sec-hdr" onclick={() => toggle('skin')}>
      <span class="sec-title"><Droplets size={14} /> 肌</span>
      <span class="chev" class:open={open.has('skin')}>▾</span>
    </button>
    {#if open.has('skin')}
    <div class="sec-body">
      <div class="row">
        <label for="sl-smoothing">美肌 <span>{b.smoothing}</span></label>
        <input id="sl-smoothing" type="range" min="0" max="100" value={b.smoothing}
          oninput={(e) => updateParam('smoothing', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label for="sl-sharpness">シャープネス <span>{b.sharpness}</span></label>
        <input id="sl-sharpness" type="range" min="0" max="100" value={b.sharpness}
          oninput={(e) => updateParam('sharpness', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label for="sl-skin-brightness">明るさ <span>{formatSigned(b.skinBrightness)}</span></label>
        <input id="sl-skin-brightness" type="range" min="-100" max="100" value={b.skinBrightness}
          oninput={(e) => updateParam('skinBrightness', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-skin-warmth">色温度 <span>{formatSigned(b.skinWarmth)}</span></label>
        <input id="sl-skin-warmth" type="range" min="-100" max="100" value={b.skinWarmth}
          oninput={(e) => updateParam('skinWarmth', +(e.target as HTMLInputElement).value)} class="warm" />
      </div>
      <div class="row">
        <label for="sl-whitening">美白 <span>{b.whitening}</span></label>
        <input id="sl-whitening" type="range" min="0" max="100" value={b.whitening}
          oninput={(e) => updateParam('whitening', +(e.target as HTMLInputElement).value)} />
      </div>
    </div>
    {/if}
  </div>

  <!-- 顔形 -->
  <div class="section">
    <button class="sec-hdr" onclick={() => toggle('face')}>
      <span class="sec-title"><ScanFace size={14} /> 顔形</span>
      <span class="chev" class:open={open.has('face')}>▾</span>
    </button>
    {#if open.has('face')}
    <div class="sec-body">
      <div class="row">
        <label for="sl-face-slim">顔痩せ <span>{formatSigned(b.faceSlim)}</span></label>
        <input id="sl-face-slim" type="range" min="-100" max="100" value={b.faceSlim}
          oninput={(e) => updateParam('faceSlim', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-head-size">頭サイズ <span>{formatSigned(b.headSize)}</span></label>
        <input id="sl-head-size" type="range" min="-100" max="100" value={b.headSize}
          oninput={(e) => updateParam('headSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-mid-face">中顔面短縮 <span>{formatSigned(b.midFace)}</span></label>
        <input id="sl-mid-face" type="range" min="-100" max="100" value={b.midFace}
          oninput={(e) => updateParam('midFace', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-cheek-width">頬横幅 <span>{formatSigned(b.cheekWidth)}</span></label>
        <input id="sl-cheek-width" type="range" min="-100" max="100" value={b.cheekWidth}
          oninput={(e) => updateParam('cheekWidth', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-jaw">エラ削り <span>{formatSigned(b.jaw)}</span></label>
        <input id="sl-jaw" type="range" min="-100" max="100" value={b.jaw}
          oninput={(e) => updateParam('jaw', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-chin-length">顎縦幅 <span>{formatSigned(b.chinLength)}</span></label>
        <input id="sl-chin-length" type="range" min="-100" max="100" value={b.chinLength}
          oninput={(e) => updateParam('chinLength', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
    </div>
    {/if}
  </div>

  <!-- 鼻 -->
  <div class="section">
    <button class="sec-hdr" onclick={() => toggle('nose')}>
      <span class="sec-title"><Scan size={14} /> 鼻</span>
      <span class="chev" class:open={open.has('nose')}>▾</span>
    </button>
    {#if open.has('nose')}
    <div class="sec-body">
      <div class="row">
        <label for="sl-nose-width">小鼻サイズ <span>{formatSigned(b.noseWidth)}</span></label>
        <input id="sl-nose-width" type="range" min="-100" max="100" value={b.noseWidth}
          oninput={(e) => updateParam('noseWidth', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-nose-height">鼻縦幅 <span>{formatSigned(b.noseHeight)}</span></label>
        <input id="sl-nose-height" type="range" min="-100" max="100" value={b.noseHeight}
          oninput={(e) => updateParam('noseHeight', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
    </div>
    {/if}
  </div>

  <!-- 目 -->
  <div class="section">
    <button class="sec-hdr" onclick={() => toggle('eye')}>
      <span class="sec-title"><Eye size={14} /> 目</span>
      <span class="chev" class:open={open.has('eye')}>▾</span>
    </button>
    {#if open.has('eye')}
    <div class="sec-body">
      <div class="row">
        <label for="sl-eye-size">目のサイズ <span>{formatSigned(b.eyeSize)}</span></label>
        <input id="sl-eye-size" type="range" min="-100" max="100" value={b.eyeSize}
          oninput={(e) => updateParam('eyeSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-eye-position">目の位置 <span>{formatSigned(b.eyePosition)}</span></label>
        <input id="sl-eye-position" type="range" min="-100" max="100" value={b.eyePosition}
          oninput={(e) => updateParam('eyePosition', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-iris-size">黒目サイズ <span>{formatSigned(b.irisSize)}</span></label>
        <input id="sl-iris-size" type="range" min="-100" max="100" value={b.irisSize}
          oninput={(e) => updateParam('irisSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-eye-tilt">タレ目/つり目 <span>{formatSigned(b.eyeTilt)}</span></label>
        <input id="sl-eye-tilt" type="range" min="-100" max="100" value={b.eyeTilt}
          oninput={(e) => updateParam('eyeTilt', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-eye-sparkle">目の反射 <span>{b.eyeSparkle}</span></label>
        <input id="sl-eye-sparkle" type="range" min="0" max="100" value={b.eyeSparkle}
          oninput={(e) => updateParam('eyeSparkle', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label for="sl-dark-circle">クマとり <span>{b.darkCircle}</span></label>
        <input id="sl-dark-circle" type="range" min="0" max="100" value={b.darkCircle}
          oninput={(e) => updateParam('darkCircle', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label for="sl-tear-bag">涙袋 <span>{b.tearBag}</span></label>
        <input id="sl-tear-bag" type="range" min="0" max="100" value={b.tearBag}
          oninput={(e) => updateParam('tearBag', +(e.target as HTMLInputElement).value)} />
      </div>
    </div>
    {/if}
  </div>

  <!-- 口 -->
  <div class="section">
    <button class="sec-hdr" onclick={() => toggle('mouth')}>
      <span class="sec-title"><Smile size={14} /> 口</span>
      <span class="chev" class:open={open.has('mouth')}>▾</span>
    </button>
    {#if open.has('mouth')}
    <div class="sec-body">
      <div class="row">
        <label for="sl-mouth-size">口サイズ <span>{formatSigned(b.mouthSize)}</span></label>
        <input id="sl-mouth-size" type="range" min="-100" max="100" value={b.mouthSize}
          oninput={(e) => updateParam('mouthSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-mouth-corner">口角 <span>{formatSigned(b.mouthCorner)}</span></label>
        <input id="sl-mouth-corner" type="range" min="-100" max="100" value={b.mouthCorner}
          oninput={(e) => updateParam('mouthCorner', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-philtrum">口の位置 <span>{formatSigned(b.philtrum)}</span></label>
        <input id="sl-philtrum" type="range" min="-100" max="100" value={b.philtrum}
          oninput={(e) => updateParam('philtrum', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label for="sl-teeth-whitening">歯ホワイトニング <span>{b.teethWhitening}</span></label>
        <input id="sl-teeth-whitening" type="range" min="0" max="100" value={b.teethWhitening}
          oninput={(e) => updateParam('teethWhitening', +(e.target as HTMLInputElement).value)} />
      </div>
    </div>
    {/if}
  </div>

  <!-- メイク -->
  <div class="section">
    <button class="sec-hdr" onclick={() => toggle('makeup')}>
      <span class="sec-title"><Paintbrush size={14} /> メイク</span>
      <span class="chev" class:open={open.has('makeup')}>▾</span>
    </button>
    {#if open.has('makeup')}
    <div class="sec-body">
      <div class="color-group">
        <div class="color-label">チークカラー</div>
        <div class="color-row">
          {#each CHEEK_COLORS as c}
            <button class="color-dot" class:sel={currentCheekColor === c}
              style="background:{c}" aria-label={c} onclick={() => updateParam('cheekColor', c)}></button>
          {/each}
        </div>
        <div class="row">
          <label for="sl-cheek-strength">強さ <span>{b.cheekStrength}</span></label>
          <input id="sl-cheek-strength" type="range" min="0" max="100" value={b.cheekStrength}
            oninput={(e) => updateParam('cheekStrength', +(e.target as HTMLInputElement).value)} />
        </div>
      </div>

      <div class="color-group">
        <div class="color-label">リップカラー</div>
        <div class="color-row">
          {#each LIP_COLORS as c}
            <button class="color-dot" class:sel={currentLipColor === c}
              style="background:{c}" aria-label={c} onclick={() => updateParam('lipColor', c)}></button>
          {/each}
        </div>
        <div class="row">
          <label for="sl-lip-strength">強さ <span>{b.lipStrength}</span></label>
          <input id="sl-lip-strength" type="range" min="0" max="100" value={b.lipStrength}
            oninput={(e) => updateParam('lipStrength', +(e.target as HTMLInputElement).value)} />
        </div>
      </div>

    </div>
    {/if}
  </div>

</div>

<style>
  .beauty-panel {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .section {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #F0E0F0;
    background: white;
  }

  .sec-hdr {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border: none;
    background: #FFF8FC;
    cursor: pointer;
    font-size: 0.72rem;
    font-weight: 700;
    color: #C060A0;
    transition: background 0.15s;
  }
  .sec-title {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .sec-hdr:hover { background: #FFF0F8; }

  .chev {
    font-size: 0.8rem;
    color: #D4A0C8;
    transition: transform 0.2s;
    display: inline-block;
  }
  .chev.open { transform: rotate(180deg); }

  .sec-body {
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .row {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  label {
    display: flex;
    justify-content: space-between;
    font-size: 0.65rem;
    font-weight: 600;
    color: #999;
  }
  label span { color: #C060A0; }

  input[type="range"] {
    -webkit-appearance: none;
    width: 100%;
    height: 5px;
    border-radius: 3px;
    background: linear-gradient(to right, #F0A0C0, #D4A0F0);
    outline: none;
  }
  input[type="range"].bi {
    background: linear-gradient(to right, #A0C4E8, #E8D0F0 50%, #D4A0F0);
  }
  input[type="range"].warm {
    background: linear-gradient(to right, #AED6F1, #FF9966);
  }
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: white;
    border: 2px solid #F0A0C0;
    cursor: pointer;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  }

  .color-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-bottom: 4px;
    border-bottom: 1px solid #F5E8F5;
  }
  .color-group:last-child { border-bottom: none; padding-bottom: 0; }

  .color-label {
    font-size: 0.63rem;
    font-weight: 600;
    color: #AAA;
  }

  .color-row {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .color-dot {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    padding: 0;
    transition: transform 0.12s;
  }
  .color-dot:hover { transform: scale(1.15); }
  .color-dot.sel {
    border-color: #C060A0;
    box-shadow: 0 0 0 2px rgba(192,96,160,0.3);
  }
</style>
