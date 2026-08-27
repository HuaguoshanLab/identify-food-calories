import { defineConfig, devices } from '@playwright/test'

const frontendUrl = 'http://127.0.0.1:4173'
const backendUrl = 'http://127.0.0.1:8000/api/v1/health'

const backendEnvironment = {
  ...process.env,
  APP_ENV: 'test',
  // The spawned application must use only the isolated database; Alembic receives
  // its required distinct development URL inline while it validates TEST_DATABASE_URL.
  DATABASE_URL: 'postgresql+psycopg://postgres:postgres@127.0.0.1:55432/food_agent_test',
  TEST_DATABASE_URL:
    'postgresql+psycopg://postgres:postgres@127.0.0.1:55432/food_agent_test',
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
        "docker compose -f ../docker-compose.yml up -d --wait postgres-test mailpit && " +
        "docker compose -f ../docker-compose.yml exec -T postgres-test psql -U postgres -d food_agent_test -v ON_ERROR_STOP=1 -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' && " +
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev .venv/bin/alembic upgrade 0001 && " +
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev .venv/bin/alembic upgrade head && " +
        'exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000',
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
      command: 'npm run build && npm run preview',
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'pipe',
      stderr: 'pipe',
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
    },
  ],
})
