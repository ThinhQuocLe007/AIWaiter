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
    // host: true → bind 0.0.0.0 (IPv4). Mặc định Vite chỉ bind 'localhost', mà máy
    // resolve localhost→::1 (IPv6) nên browser gọi 127.0.0.1 (IPv4) bị
    // ERR_CONNECTION_REFUSED. Bind IPv4 vừa fix lỗi vừa cho test qua LAN.
    host: true,
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
  // `vite preview` (lệnh `make serve`, phục vụ bản build production trong dist/)
  // KHÔNG dùng `server.proxy` ở trên — đó chỉ áp cho dev server. Thiếu khối này
  // thì bản production gọi /api, /ws sẽ 404 (không tới được FastAPI:8000). Mirror
  // y hệt proxy dev để test production cục bộ vẫn cùng origin, không dính CORS.
  // (Deploy thật: cho FastAPI serve thẳng dist/ cùng origin thì khỏi cần proxy.)
  preview: {
    host: true,
    port: 4173,
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
