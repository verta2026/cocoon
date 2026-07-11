import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 构建产物是纯静态文件，由 cocoon 桥按现有 frontend/ 同样的方式伺服。
// base 用相对路径：部署路径无论挂在 / 还是 /app/ 都能跑。
export default defineConfig({
  // React Compiler：自动记忆化，手写 memo 之外的全树兜底调优
  plugins: [react({ babel: { plugins: ['babel-plugin-react-compiler'] } })],
  // 构建指纹：侧栏可见，"页面跑的是哪版"一眼定案
  define: { __BUILD__: JSON.stringify(new Date().toISOString().slice(5, 16).replace('T', ' ') + ' UTC') },
  base: './',
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      input: {
        index: new URL('./index.html', import.meta.url).pathname,
        login: new URL('./login.html', import.meta.url).pathname,
      },
    },
  },
  server: {
    // 本地开发时把 API 转发给桥（start.sh 默认 8080，改端口的部署自己调）
    proxy: {
      '/auth': 'http://127.0.0.1:8080',
      '/send': 'http://127.0.0.1:8080',
      '/bridge': 'http://127.0.0.1:8080',
      '/app-config': 'http://127.0.0.1:8080',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
