import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test'

const mailpitApi = 'http://127.0.0.1:8025/api/v1'
const password = 'correct-horse-battery-staple'
const replacementPassword = 'new-correct-horse-battery-staple'

type MailpitMessage = {
  ID?: string
  Text?: string
  To?: Array<{ Address?: string }>
}

async function clearMailbox(request: APIRequestContext) {
  const response = await request.delete(`${mailpitApi}/messages`)
  expect(response.ok()).toBeTruthy()
}

async function readCode(request: APIRequestContext, email: string) {
  await expect.poll(async () => {
    const response = await request.get(`${mailpitApi}/messages`)
    if (!response.ok()) return null
    const body = await response.json() as { messages?: MailpitMessage[] }
    const message = body.messages?.find((candidate) =>
      candidate.To?.some((recipient) => recipient.Address?.toLowerCase() === email),
    )
    if (!message) return null
    const text = message.Text ?? (message.ID
      ? (await (await request.get(`${mailpitApi}/message/${message.ID}`)).json() as MailpitMessage).Text
      : undefined)
    return text?.match(/\b(\d{6})\b/)?.[1] ?? null
  }, { timeout: 10_000 }).toMatch(/^\d{6}$/)

  const response = await request.get(`${mailpitApi}/messages`)
  const body = await response.json() as { messages?: MailpitMessage[] }
  const message = body.messages?.find((candidate) =>
    candidate.To?.some((recipient) => recipient.Address?.toLowerCase() === email),
  )
  const text = message?.Text ?? (message?.ID
    ? (await (await request.get(`${mailpitApi}/message/${message.ID}`)).json() as MailpitMessage).Text
    : '')
  const code = text.match(/\b(\d{6})\b/)?.[1]
  if (!code) throw new Error('Mailpit delivered a message without a verification code')
  return code
}

async function login(page: Page, email: string, userPassword: string) {
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码', { exact: true }).fill(userPassword)
  await page.getByRole('button', { name: '登录并继续' }).click()
  await expect(page.getByRole('heading', { name: '账号与会话' })).toBeVisible()
}

test.describe('full-stack auth', () => {
  test.describe.configure({ mode: 'serial' })

  test('uses public APIs and Mailpit to prove registration, recovery and session protection', async ({ browser, page, request }) => {
    const email = `phase-one-e2e-${Date.now()}@example.test`
    await clearMailbox(request)

    await page.setViewportSize({ width: 320, height: 800 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' })).toBeVisible()
    await page.getByRole('link', { name: '创建账号' }).press('Enter')
    await expect(page.getByRole('heading', { name: '创建账号' })).toBeFocused()
    await page.getByLabel('邮箱').fill(email)
    await page.getByLabel('密码', { exact: true }).fill(password)
    await page.getByLabel('确认密码').fill(password)
    await page.getByRole('button', { name: '发送验证码' }).click()

    await expect(page.getByRole('heading', { name: '验证邮箱' })).toBeVisible()
    const registrationCode = await readCode(request, email)
    await page.getByLabel('6 位邮箱验证码').fill(registrationCode)
    await page.getByRole('button', { name: '验证并激活账号' }).click()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()

    await page.goto('/login?returnTo=%2Fapp%3Ftab%3Dsessions')
    await login(page, email, password)
    await expect(page).toHaveURL(/\/app\?tab=sessions$/)
    await expect(page.getByText(email)).toBeVisible()

    const refreshedIdentity = await page.evaluate(async () => {
      const refreshed = await fetch('http://127.0.0.1:8000/api/v1/auth/refresh', {
        method: 'POST', credentials: 'include', headers: { Origin: window.location.origin },
      })
      const access = (await refreshed.json()) as { access_token: string }
      const me = await fetch('http://127.0.0.1:8000/api/v1/users/me', {
        headers: { Authorization: `Bearer ${access.access_token}` },
      })
      return { refreshStatus: refreshed.status, me: await me.json(), meStatus: me.status }
    })
    expect(refreshedIdentity.refreshStatus).toBe(200)
    expect(refreshedIdentity.meStatus).toBe(200)
    expect(refreshedIdentity.me.email).toBe(email)

    const secondContext = await browser.newContext()
    const secondPage = await secondContext.newPage()
    await secondPage.goto('/login')
    await login(secondPage, email, password)
    await page.reload()
    await expect(page.getByRole('button', { name: '撤销会话' })).toBeVisible()
    await page.getByRole('button', { name: '撤销会话' }).click()
    await page.getByRole('button', { name: '撤销这个会话' }).click()
    await expect(page.getByRole('status')).toHaveText('登录会话已撤销。')
    await secondPage.reload()
    await expect(secondPage.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await secondContext.close()

    await page.getByRole('button', { name: '退出当前设备' }).click()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await page.goBack()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()

    await clearMailbox(request)
    await page.goto('/forgot-password')
    await page.getByLabel('邮箱').fill(email)
    await page.getByRole('button', { name: '发送重置验证码' }).click()
    await expect(page.getByRole('heading', { name: '重置密码' })).toBeVisible()
    const recoveryCode = await readCode(request, email)
    await page.getByLabel('6 位邮箱验证码').fill(recoveryCode)
    await page.getByLabel('新密码').fill(replacementPassword)
    await page.getByLabel('确认新密码').fill(replacementPassword)
    await page.getByRole('button', { name: '更新密码' }).click()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await login(page, email, replacementPassword)

    await page.addStyleTag({ content: 'html { font-size: 200%; }' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  })
})
