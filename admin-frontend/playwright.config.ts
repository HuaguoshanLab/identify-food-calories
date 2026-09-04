import { defineConfig, devices } from '@playwright/test'

function localPort(variableName: string, fallback: string) {
  const value = process.env[variableName] ?? fallback
  if (!/^\d{2,5}$/.test(value)) throw new Error(`${variableName} must be a local TCP port number.`)
  return value
}

const backendPort = localPort('E2E_ADMIN_BACKEND_PORT', '8003')
const userFrontendPort = localPort('E2E_ADMIN_USER_FRONTEND_PORT', '5183')
const adminFrontendPort = localPort('E2E_ADMIN_FRONTEND_PORT', '5184')
const backendOrigin = `http://127.0.0.1:${backendPort}`
const userFrontendUrl = `http://127.0.0.1:${userFrontendPort}`
const adminFrontendUrl = `http://127.0.0.1:${adminFrontendPort}`

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: {
    baseURL: adminFrontendUrl,
    trace: 'retain-on-failure',
    viewport: { width: 1280, height: 900 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      name: 'FastAPI isolated test backend',
      cwd: '..',
      command: 'docker compose up -d --wait postgres-test mailpit && cd backend && exec .venv/bin/python tests/run_pg.py --env-file .env.test.example -- .venv/bin/python scripts/run_initialized_app.py --host 127.0.0.1 --port ' + backendPort,
      env: {
        ...process.env,
        CORS_ORIGINS: JSON.stringify([userFrontendUrl, adminFrontendUrl]),
        SMTP_HOST: '127.0.0.1',
        SMTP_PORT: '1025',
      },
      url: `${backendOrigin}/api/v1/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
    {
      name: 'User Vite preview',
      cwd: '../frontend',
      command: `npm run build && npm run preview:e2e -- --port ${userFrontendPort}`,
      env: { ...process.env, VITE_DEV_API_PROXY_TARGET: backendOrigin },
      url: userFrontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
    {
      name: 'Admin Vite preview',
      cwd: '.',
      command: `VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run preview -- --port ${adminFrontendPort}`,
      env: { ...process.env, VITE_ADMIN_API_PROXY_TARGET: backendOrigin },
      url: adminFrontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
  ],
})
