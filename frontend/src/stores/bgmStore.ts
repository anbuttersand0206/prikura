import { writable } from 'svelte/store';
export const bgmEnabled = writable(true);

/**
 * audio.play() を試みる。Autoplay Policy でブロックされた場合は
 * 最初のユーザー操作（click / touchstart / keydown）で再試行する。
 * 返り値の関数をコンポーネントの onDestroy で呼ぶとリスナーを解除できる。
 */
export function tryPlay(audio: HTMLAudioElement): () => void {
  let removeListeners = () => {};
  audio.play().catch(() => {
    const resume = () => {
      audio.play().catch(() => {});
      removeListeners();
    };
    window.addEventListener('click',      resume, { once: true });
    window.addEventListener('touchstart', resume, { once: true });
    window.addEventListener('keydown',    resume, { once: true });
    removeListeners = () => {
      window.removeEventListener('click',      resume);
      window.removeEventListener('touchstart', resume);
      window.removeEventListener('keydown',    resume);
    };
  });
  return () => removeListeners();
}
