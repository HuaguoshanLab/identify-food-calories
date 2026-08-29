import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import config from './playwright.config'

const backendDirectory = resolve(process.cwd(), '../backend')
const backendPython = resolve(backendDirectory, '.venv/bin/python')
const runPg = resolve(backendDirectory, 'tests/run_pg.py')
const testEnvironment = resolve(backendDirectory, '.env.test.example')

function fastApiServer() {
  const servers = config.webServer
  if (!Array.isArray(servers)) {
    throw new Error('Playwright must own both FastAPI and Vite web servers.')
  }
  const server = servers.find((candidate) => candidate.name === 'FastAPI')
  if (!server) {
    throw new Error('FastAPI web server configuration is required.')
  }
  return server
}

describe('Playwright provisioning contract', () => {
  it('runs a real wrapper child with distinct official database variables', () => {
    const output = execFileSync(
      backendPython,
      [
        runPg,
        '--env-file',
        testEnvironment,
        '--',
        backendPython,
        '-c',
        [
          'from app.core.config import Settings, validate_test_database_configuration',
          'settings = Settings(_env_file=None)',
          "assert settings.app_env == 'test'",
          "assert settings.database_url.endswith(':5432/food_agent_dev')",
          "assert settings.test_database_url and settings.test_database_url.endswith(':55432/food_agent_test')",
          'assert settings.database_url != settings.test_database_url',
          "assert validate_test_database_configuration(settings).endswith(':55432/food_agent_test')",
          "print('playwright-child-contract-ok')",
        ].join('; '),
      ],
      { cwd: backendDirectory, encoding: 'utf8' },
    )

    expect(output.trim()).toBe('playwright-child-contract-ok')
  })

  it('uses the guarded launcher instead of bare schema commands or a reusable server', () => {
    const server = fastApiServer()

    expect(server.cwd).toBe('../backend')
    expect(server.command).toContain('docker compose up -d --wait postgres-test mailpit')
    expect(server.command).toContain('tests/run_pg.py --env-file .env.test.example')
    expect(server.command).toContain('scripts/run_initialized_app.py')
    expect(server.command).not.toContain('DATABASE_URL=')
    expect(server.command).not.toContain('DROP SCHEMA')
    expect(server.command).not.toContain('alembic upgrade')
    expect(server.reuseExistingServer).toBe(false)
  })
})
