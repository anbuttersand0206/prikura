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

  let open = new Set<string>(['skin']);

  function toggle(id: string) {
    open.has(id) ? open.delete(id) : open.add(id);
    open = open;
  }

  function upd(key: string, val: number | string) {
    appState.updateBeauty({ [key]: val } as any);
  }

  function fmt(v: number) { return v > 0 ? `+${v}` : `${v}`; }
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
        <label>美肌 <span>{b.smoothing}</span></label>
        <input type="range" min="0" max="100" value={b.smoothing}
          oninput={(e) => upd('smoothing', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label>シャープネス <span>{b.sharpness}</span></label>
        <input type="range" min="0" max="100" value={b.sharpness}
          oninput={(e) => upd('sharpness', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label>明るさ <span>{fmt(b.skinBrightness)}</span></label>
        <input type="range" min="-100" max="100" value={b.skinBrightness}
          oninput={(e) => upd('skinBrightness', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>色温度 <span>{fmt(b.skinWarmth)}</span></label>
        <input type="range" min="-100" max="100" value={b.skinWarmth}
          oninput={(e) => upd('skinWarmth', +(e.target as HTMLInputElement).value)} class="warm" />
      </div>
      <div class="row">
        <label>美白 <span>{b.whitening}</span></label>
        <input type="range" min="0" max="100" value={b.whitening}
          oninput={(e) => upd('whitening', +(e.target as HTMLInputElement).value)} />
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
        <label>顔痩せ <span>{fmt(b.faceSlim)}</span></label>
        <input type="range" min="-100" max="100" value={b.faceSlim}
          oninput={(e) => upd('faceSlim', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>頭サイズ <span>{fmt(b.headSize)}</span></label>
        <input type="range" min="-100" max="100" value={b.headSize}
          oninput={(e) => upd('headSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>中顔面短縮 <span>{fmt(b.midFace)}</span></label>
        <input type="range" min="-100" max="100" value={b.midFace}
          oninput={(e) => upd('midFace', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>頬横幅 <span>{fmt(b.cheekWidth)}</span></label>
        <input type="range" min="-100" max="100" value={b.cheekWidth}
          oninput={(e) => upd('cheekWidth', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>エラ削り <span>{fmt(b.jaw)}</span></label>
        <input type="range" min="-100" max="100" value={b.jaw}
          oninput={(e) => upd('jaw', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>顎縦幅 <span>{fmt(b.chinLength)}</span></label>
        <input type="range" min="-100" max="100" value={b.chinLength}
          oninput={(e) => upd('chinLength', +(e.target as HTMLInputElement).value)} class="bi" />
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
        <label>小鼻サイズ <span>{fmt(b.noseWidth)}</span></label>
        <input type="range" min="-100" max="100" value={b.noseWidth}
          oninput={(e) => upd('noseWidth', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>鼻縦幅 <span>{fmt(b.noseHeight)}</span></label>
        <input type="range" min="-100" max="100" value={b.noseHeight}
          oninput={(e) => upd('noseHeight', +(e.target as HTMLInputElement).value)} class="bi" />
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
        <label>目のサイズ <span>{fmt(b.eyeSize)}</span></label>
        <input type="range" min="-100" max="100" value={b.eyeSize}
          oninput={(e) => upd('eyeSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>目の位置 <span>{fmt(b.eyePosition)}</span></label>
        <input type="range" min="-100" max="100" value={b.eyePosition}
          oninput={(e) => upd('eyePosition', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>黒目サイズ <span>{fmt(b.irisSize)}</span></label>
        <input type="range" min="-100" max="100" value={b.irisSize}
          oninput={(e) => upd('irisSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>タレ目/つり目 <span>{fmt(b.eyeTilt)}</span></label>
        <input type="range" min="-100" max="100" value={b.eyeTilt}
          oninput={(e) => upd('eyeTilt', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>目の反射 <span>{b.eyeSparkle}</span></label>
        <input type="range" min="0" max="100" value={b.eyeSparkle}
          oninput={(e) => upd('eyeSparkle', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label>クマとり <span>{b.darkCircle}</span></label>
        <input type="range" min="0" max="100" value={b.darkCircle}
          oninput={(e) => upd('darkCircle', +(e.target as HTMLInputElement).value)} />
      </div>
      <div class="row">
        <label>涙袋 <span>{b.tearBag}</span></label>
        <input type="range" min="0" max="100" value={b.tearBag}
          oninput={(e) => upd('tearBag', +(e.target as HTMLInputElement).value)} />
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
        <label>口サイズ <span>{fmt(b.mouthSize)}</span></label>
        <input type="range" min="-100" max="100" value={b.mouthSize}
          oninput={(e) => upd('mouthSize', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>口角 <span>{fmt(b.mouthCorner)}</span></label>
        <input type="range" min="-100" max="100" value={b.mouthCorner}
          oninput={(e) => upd('mouthCorner', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>口の位置 <span>{fmt(b.philtrum)}</span></label>
        <input type="range" min="-100" max="100" value={b.philtrum}
          oninput={(e) => upd('philtrum', +(e.target as HTMLInputElement).value)} class="bi" />
      </div>
      <div class="row">
        <label>歯ホワイトニング <span>{b.teethWhitening}</span></label>
        <input type="range" min="0" max="100" value={b.teethWhitening}
          oninput={(e) => upd('teethWhitening', +(e.target as HTMLInputElement).value)} />
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
              style="background:{c}" aria-label={c} onclick={() => upd('cheekColor', c)}></button>
          {/each}
        </div>
        <div class="row">
          <label>強さ <span>{b.cheekStrength}</span></label>
          <input type="range" min="0" max="100" value={b.cheekStrength}
            oninput={(e) => upd('cheekStrength', +(e.target as HTMLInputElement).value)} />
        </div>
      </div>

      <div class="color-group">
        <div class="color-label">リップカラー</div>
        <div class="color-row">
          {#each LIP_COLORS as c}
            <button class="color-dot" class:sel={currentLipColor === c}
              style="background:{c}" aria-label={c} onclick={() => upd('lipColor', c)}></button>
          {/each}
        </div>
        <div class="row">
          <label>強さ <span>{b.lipStrength}</span></label>
          <input type="range" min="0" max="100" value={b.lipStrength}
            oninput={(e) => upd('lipStrength', +(e.target as HTMLInputElement).value)} />
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
