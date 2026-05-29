// アプリのエントリーポイント。
// Svelte 5 の mount() は旧来の new App() より明示的で、
// ツリーシェイキングが効きやすいため採用している。
import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app
