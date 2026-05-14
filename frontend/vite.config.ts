import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'url'
import { dirname, resolve, extname } from 'path'
import { readFile } from 'fs'

const __dirname = dirname(fileURLToPath(import.meta.url))

// assets/fonts/ を /fonts/ として配信するカスタムプラグイン。
// SVG スタンプのフォント埋め込みに使う。
function serveFonts() {
  const fontsDir = resolve(__dirname, '../assets/fonts')
  const handle = (req: any, res: any, next: any) => {
    const safePath = (req.url as string).split('?')[0].replace(/\.\./g, '')
    readFile(resolve(fontsDir, '.' + safePath), (err, data) => {
      if (err) return next()
      const mime = extname(safePath) === '.otf' ? 'font/otf' : 'font/ttf'
      res.setHeader('Content-Type', mime)
      res.setHeader('Cache-Control', 'public, max-age=31536000, immutable')
      res.end(data)
    })
  }
  return {
    name: 'serve-assets-fonts',
    configureServer(server: any) { server.middlewares.use('/fonts', handle) },
    configurePreviewServer(server: any) { server.middlewares.use('/fonts', handle) },
  }
}

function serveSounds() {
  const soundsDir = resolve(__dirname, '../assets/sounds')
  const handle = (req: any, res: any, next: any) => {
    const rawPath = (req.url as string).split('?')[0].replace(/\.\./g, '')
    const safePath = decodeURIComponent(rawPath)
    readFile(resolve(soundsDir, '.' + safePath), (err, data) => {
      if (err) return next()
      res.setHeader('Content-Type', 'audio/mpeg')
      res.setHeader('Cache-Control', 'public, max-age=3600')
      res.end(data)
    })
  }
  return {
    name: 'serve-assets-sounds',
    configureServer(server: any) { server.middlewares.use('/sounds', handle) },
    configurePreviewServer(server: any) { server.middlewares.use('/sounds', handle) },
  }
}

function serveStamps() {
  const stampsDir = resolve(__dirname, '../assets/stamps')
  const handle = (req: any, res: any, next: any) => {
    const safePath = (req.url as string).split('?')[0].replace(/\.\./g, '')
    readFile(resolve(stampsDir, '.' + safePath), (err, data) => {
      if (err) return next()
      res.setHeader('Content-Type', 'image/png')
      res.setHeader('Cache-Control', 'public, max-age=3600')
      res.end(data)
    })
  }
  return {
    name: 'serve-assets-stamps',
    configureServer(server: any) { server.middlewares.use('/stamps', handle) },
    configurePreviewServer(server: any) { server.middlewares.use('/stamps', handle) },
  }
}

export default defineConfig({
  plugins: [tailwindcss(), svelte(), serveFonts(), serveSounds(), serveStamps()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
