import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

// 代理目标固定 8010:与 api/main.py 的默认端口一致(项目约定:后端端口固定,不换)。
// **不要默认指向 8000**:本机 8000 是沙箱 SSH 隧道(SANDBOX_URL 指向它),
// 指过去会把前端 API 请求打到沙箱服务上。需要覆盖时用环境变量 VITE_PROXY_TARGET。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = process.env.VITE_PROXY_TARGET || env.VITE_PROXY_TARGET || 'http://127.0.0.1:8010'

  return {
    plugins: [vue()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          // 后端路由无 /api 前缀,proxy 只负责剥掉它
          rewrite: (p) => p.replace(/^\/api/, ''),
          // SSE 必须关闭代理层聚合缓冲,否则事件会被攒住一次性下发
          configure: (proxy) => {
            proxy.on('proxyRes', (proxyRes) => {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform'
            })
          },
        },
      },
    },
    build: { outDir: 'dist', sourcemap: true, target: 'es2022' },
  }
})