import { defineConfig, devices } from '@playwright/test'

const frontendUrl = 'http://127.0.0.1:4173'
const backendUrl = 'http://127.0.0.1:8000/api/v1/health'

const backendEnvironment = {
  ...process.env,
  CORS_ORIGINS: JSON.stringify([frontendUrl]),
  SMTP_HOST: '127.0.0.1',
  SMTP_PORT: '1025',
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
        '.venv/bin/python scripts/run_initialized_app.py --host 127.0.0.1 --port 8000',
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
      command: 'npm run build && npm run preview:e2e',
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
  ],
})
