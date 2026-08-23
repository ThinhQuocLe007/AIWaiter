import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Voice-pipeline monitor. Standalone app per the per-surface convention; shares the
// dependency-free WS/REST helpers with the other frontends via the @shared alias.
export default defineConfig({
  // Production is served by FastAPI at http://<server>:8000/monitor (see main.py `_mount_spa`).
  base: '/monitor/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
    },
  },
  server: {
    host: true,
    // Fixed port 5176 (port convention: customer_ui 5173 · kiosk 5174 · panel 5175 · monitor 5176).
    port: 5176,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
