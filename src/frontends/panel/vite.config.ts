import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Control panel (kitchen / manager). Standalone app per the per-surface convention;
// shares dependency-free code with the other frontends via the @shared alias.
export default defineConfig({
  // Production is served by FastAPI at http://<server>:8000/panel (see main.py `_mount_spa`).
  // Without this the bundle would request its assets from /assets/* — the path customer_ui
  // owns at the root mount — and the panel would load a blank page.
  base: '/panel/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@shared': fileURLToPath(new URL('../shared', import.meta.url)),
    },
  },
  server: {
    // host: true → bind 0.0.0.0 (IPv4). Mặc định Vite bind 'localhost' mà máy resolve
    // localhost→::1 (IPv6) nên browser gọi 127.0.0.1 bị ERR_CONNECTION_REFUSED.
    host: true,
    // Fixed port 5175 (port convention: customer_ui 5173 · kiosk 5174 · panel 5175).
    port: 5175,
    strictPort: true,
    // Same-origin proxy to FastAPI so there is no CORS (matches customer_ui setup).
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
