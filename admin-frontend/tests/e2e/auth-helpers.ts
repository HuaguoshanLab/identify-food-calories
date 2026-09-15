import { execFile as execFileCallback } from 'node:child_process'
import { promisify } from 'node:util'
import { expect, type APIRequestContext, type Page } from '@playwright/test'

const execFile = promisify(execFileCallback)
const mailpitApi = `http://127.0.0.1:${process.env.E2E_ADMIN_MAILPIT_PORT ?? '8026'}/api/v1`
const userFrontendUrl = `http://127.0.0.1:${process.env.E2E_ADMIN_USER_FRONTEND_PORT ?? '5183'}`
const e2eDatabaseUrl = 'postgresql+psycopg://postgres:postgres@127.0.0.1:55433/food_agent_e2e_test'
const e2eCliEnvironment = {
  ...process.env,
  APP_ENV: 'test',
  DATABASE_URL: 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev',
  TEST_DATABASE_URL: e2eDatabaseUrl,
}

export type Account = Readonly<{ email: string, password: string }>
type MailpitMessage = Readonly<{ ID?: string, Text?: string, To?: Array<{ Address?: string }> }>

async function messageText(request: APIRequestContext, message: MailpitMessage) {
  if (message.Text) return message.Text
  if (!message.ID) return ''
  const response = await request.get(`${mailpitApi}/message/${message.ID}`)
  if (!response.ok()) return ''
  return ((await response.json()) as MailpitMessage).Text ?? ''
}

async function readVerificationCode(request: APIRequestContext, email: string) {
  async function matchingMessage() {
    const response = await request.get(`${mailpitApi}/messages`)
    const body = await response.json() as { messages?: MailpitMessage[] }
    return body.messages?.find((message) => message.To?.some((recipient) => recipient.Address?.toLowerCase() === email.toLowerCase()))
  }

  await expect.poll(async () => {
    const message = await matchingMessage()
    if (!message) return undefined
    return (await messageText(request, message)).match(/\b(\d{6})\b/)?.[1]
  }, { timeout: 10_000 }).toMatch(/^\d{6}$/)

  const message = await matchingMessage()
  const text = message ? await messageText(request, message) : ''
  const code = text?.match(/\b(\d{6})\b/)?.[1]
  if (!code) throw new Error('Mailpit delivered no verification code')
  return code
}

export async function registerAndVerify(page: Page, request: APIRequestContext, account: Account) {
  await page.goto(`${userFrontendUrl}/register`)
  await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByLabel('确认密码').fill(account.password)
  await page.getByRole('button', { name: '发送验证码' }).click()
  await expect(page.getByRole('heading', { name: '验证邮箱' })).toBeVisible()
  await page.getByLabel('6 位邮箱验证码').fill(await readVerificationCode(request, account.email))
  await page.getByRole('button', { name: '验证并激活账号' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

export async function bootstrapFirstAdmin(account: Account) {
  const result = await execFile('../backend/.venv/bin/python', [
    '-m', 'app.admin.cli',
    'bootstrap', '--email', account.email, '--reason', 'Playwright verified first-admin bootstrap',
  ], { cwd: '../backend', env: e2eCliEnvironment })
  expect(result.stderr).not.toContain(account.password)
  expect(result.stdout).toContain('admin role change recorded:')
}

