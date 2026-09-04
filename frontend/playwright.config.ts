import { defineConfig, devices } from '@playwright/test'

function localPort(variableName: string, fallback: string) {
  const value = process.env[variableName] ?? fallback
  if (!/^\d{2,5}$/.test(value)) {
    throw new Error(`${variableName} must be a local TCP port number.`)
  }
  return value
}

const frontendPort = localPort('E2E_FRONTEND_PORT', '5178')
const backendPort = localPort('E2E_BACKEND_PORT', '8000')
const recordsAdminFrontendPort = localPort('E2E_RECORDS_ADMIN_FRONTEND_PORT', '5185')
const frontendUrl = `http://127.0.0.1:${frontendPort}`
const backendOrigin = `http://127.0.0.1:${backendPort}`
const backendUrl = `${backendOrigin}/api/v1/health`
const recordsAdminFrontendUrl = `http://127.0.0.1:${recordsAdminFrontendPort}`

const backendEnvironment = {
  ...process.env,
  CORS_ORIGINS: JSON.stringify([frontendUrl, recordsAdminFrontendUrl]),
  SMTP_HOST: '127.0.0.1',
  SMTP_PORT: '1025',
}

const frontendEnvironment = {
  ...process.env,
  VITE_DEV_API_PROXY_TARGET: backendOrigin,
}

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  reporter: [['list']],
  use: {
    baseURL: frontendUrl,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      name: 'FastAPI',
      cwd: '../backend',
      command:
        'cd .. && docker compose up -d --wait postgres-test mailpit && cd backend && ' +
        'exec .venv/bin/python tests/run_pg.py --env-file .env.test.example -- ' +
        `.venv/bin/python scripts/run_initialized_app.py --host 127.0.0.1 --port ${backendPort}`,
      env: backendEnvironment,
      url: backendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
    {
      name: 'Vite',
      cwd: '.',
      command: `npm run build && npm run preview:e2e -- --port ${frontendPort}`,
      env: frontendEnvironment,
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
    {
      name: 'Records admin Vite preview',
      cwd: '../admin-frontend',
      command: `VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run build && VITE_ADMIN_API_BASE_URL=/api/v1/admin npm run preview -- --port ${recordsAdminFrontendPort}`,
      env: { ...process.env, VITE_ADMIN_API_PROXY_TARGET: backendOrigin },
      url: recordsAdminFrontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
  ],
})
