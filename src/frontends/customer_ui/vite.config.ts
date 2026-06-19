import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    // Cố định port 5173. strictPort: true để Vite báo lỗi ngay nếu 5173 đang bận,
    // thay vì âm thầm nhảy sang 5174/5175.
    port: 5173,
    strictPort: true,
    // Proxy: browser chỉ gọi chính origin của Vite (đường dẫn tương đối /api, /ws),
    // Vite chuyển tiếp sang FastAPI:8000 phía server → KHÔNG còn CORS, khớp với
    // production (FastAPI serve static cùng origin). Đổi port Vite không ảnh hưởng gì.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        // không rewrite: endpoint backend cũng là /ws
      },
    },
  },
})
