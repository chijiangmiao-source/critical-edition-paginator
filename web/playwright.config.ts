import { defineConfig, devices } from '@playwright/test'

// 端到端测试同时拉起真实后端（uvicorn）与前端（vite dev），
// 前端经 vite 代理访问 /api，验证真实联调。
const apiPort = Number(process.env.E2E_API_PORT ?? 8123)
const webPort = Number(process.env.E2E_WEB_PORT ?? 5173)

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${process.env.E2E_PYTHON ?? 'python3'} -m uvicorn app.main:app --app-dir ../api --port ${apiPort}`,
      url: `http://localhost:${apiPort}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: `npm run dev -- --port ${webPort} --strictPort`,
      url: `http://localhost:${webPort}`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: { VITE_API_PROXY_TARGET: `http://localhost:${apiPort}` },
    },
  ],
})
