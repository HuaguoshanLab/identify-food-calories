import { expect, type APIRequestContext, type Browser, type BrowserContext, type Page } from '@playwright/test'

const mailpitApi = 'http://127.0.0.1:8025/api/v1'

export type E2eAccount = {
  email: string
  password: string
  replacementPassword?: string
}

type MailpitMessage = {
  ID?: string
  Text?: string
  To?: Array<{ Address?: string }>
}

export async function clearMailbox(request: APIRequestContext) {
  const response = await request.delete(`${mailpitApi}/messages`)
  expect(response.ok()).toBeTruthy()
}

async function messageText(request: APIRequestContext, message: MailpitMessage) {
  if (message.Text) return message.Text
  if (!message.ID) return ''

  const response = await request.get(`${mailpitApi}/message/${message.ID}`)
  if (!response.ok()) return ''
  return ((await response.json()) as MailpitMessage).Text ?? ''
}

export async function readCode(request: APIRequestContext, email: string) {
  const matchingMessage = async () => {
    const response = await request.get(`${mailpitApi}/messages`)
    if (!response.ok()) return undefined
    const body = await response.json() as { messages?: MailpitMessage[] }
    return body.messages?.find((candidate) => candidate.To?.some(
      (recipient) => recipient.Address?.toLowerCase() === email.toLowerCase(),
    ))
  }

  await expect.poll(async () => {
    const message = await matchingMessage()
    return message ? (await messageText(request, message)).match(/\b(\d{6})\b/)?.[1] : undefined
  }, { timeout: 10_000 }).toMatch(/^\d{6}$/)

  const message = await matchingMessage()
  const code = message ? (await messageText(request, message)).match(/\b(\d{6})\b/)?.[1] : undefined
  if (!code) throw new Error('Mailpit delivered a message without a verification code')
  return code
}

/**
 * Account setup intentionally mirrors a new user: registration and verification are browser
 * interactions, while Mailpit is read only through its public HTTP test API. This prevents the
 * E2E suite from hiding route, cookie, or request-contract regressions behind direct seeding.
 */
export async function registerAndActivate(page: Page, request: APIRequestContext, account: E2eAccount) {
  await expect(page.getByRole('heading', { name: '创建账号' })).toBeFocused()
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByLabel('确认密码').fill(account.password)
  await page.getByRole('button', { name: '发送验证码' }).click()

  await expect(page.getByRole('heading', { name: '验证邮箱' })).toBeVisible()
  await page.getByLabel('6 位邮箱验证码').fill(await readCode(request, account.email))
  await page.getByRole('button', { name: '验证并激活账号' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

export async function login(page: Page, account: E2eAccount, returnTo = '/app/me') {
  await page.goto(`/login?returnTo=${encodeURIComponent(returnTo)}`)
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: '登录并继续' }).click()
  await expect(page).toHaveURL(new RegExp(`${returnTo.replaceAll('/', '\\/')}$`))
}

export async function createSecondDeviceSession(browser: Browser, account: E2eAccount): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext()
  const page = await context.newPage()
  await login(page, account)
  return { context, page }
}

export async function revokeOtherSession(page: Page) {
  await expect(page.getByRole('button', { name: '撤销会话' })).toBeVisible()
  await page.getByRole('button', { name: '撤销会话' }).click()
  await page.getByRole('button', { name: '撤销这个会话' }).click()
}

export async function resetPasswordThroughUi(page: Page, request: APIRequestContext, account: E2eAccount) {
  if (!account.replacementPassword) throw new Error('A replacement password is required for recovery testing')

  await clearMailbox(request)
  await page.goto('/forgot-password')
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByRole('button', { name: '发送重置验证码' }).click()
  await expect(page.getByRole('heading', { name: '重置密码' })).toBeVisible()
  await page.getByLabel('6 位邮箱验证码').fill(await readCode(request, account.email))
  await page.getByLabel('新密码', { exact: true }).fill(account.replacementPassword)
  await page.getByLabel('确认新密码').fill(account.replacementPassword)
  await page.getByRole('button', { name: '更新密码' }).click()
  await expect(page).toHaveURL(/\/login$/)
}
