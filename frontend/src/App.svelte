<script lang="ts">
  import { appState } from './stores/appState';
  import { bgmEnabled } from './stores/bgmStore';
  import { Volume2, VolumeX } from 'lucide-svelte';
  import Setup from './phases/Setup.svelte';
  import Camera from './phases/Camera.svelte';
  import Edit from './phases/Edit.svelte';

  let state = $appState;
  $: state = $appState;
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="">
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+Rounded+1c:wght@400;700;800&display=swap" rel="stylesheet">

{#if state.phase === 'setup'}
  <Setup />
{:else if state.phase === 'camera'}
  <Camera />
{:else if state.phase === 'edit'}
  <Edit />
{/if}

<!-- BGM トグルボタン（全画面共通・固定表示） -->
<button
  class="bgm-toggle"
  onclick={() => { $bgmEnabled = !$bgmEnabled; }}
  title={$bgmEnabled ? 'BGMをオフにする' : 'BGMをオンにする'}
  aria-label={$bgmEnabled ? 'BGMをオフにする' : 'BGMをオンにする'}
>
  {#if $bgmEnabled}<Volume2 size={20} />{:else}<VolumeX size={20} />{/if}
</button>

<style>
  .bgm-toggle {
    position: fixed;
    top: 14px;
    right: 14px;
    z-index: 9999;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    border: none;
    background: rgba(255, 255, 255, 0.18);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    font-size: 1.1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    transition: background 0.2s, transform 0.15s;
  }
  .bgm-toggle:hover {
    background: rgba(255, 255, 255, 0.32);
    transform: scale(1.1);
  }
  .bgm-toggle:active {
    transform: scale(0.95);
  }
</style>
