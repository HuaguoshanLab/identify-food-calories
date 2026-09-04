import { execFile as execFileCallback } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const execFile = promisify(execFileCallback)
const mailpitApi = 'http://127.0.0.1:8025/api/v1'
const userFrontendUrl = `http://127.0.0.1:${process.env.E2E_ADMIN_USER_FRONTEND_PORT ?? '5183'}`

type Account = Readonly<{ email: string, password: string }>
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

async function registerAndVerify(page: Page, request: APIRequestContext, account: Account) {
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

async function bootstrapFirstAdmin(account: Account) {
  const result = await execFile('../backend/.venv/bin/python', [
    'tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli',
    'bootstrap', '--email', account.email, '--reason', 'Playwright verified first-admin bootstrap',
  ], { cwd: '../backend' })
  expect(result.stderr).not.toContain(account.password)
  expect(result.stdout).toContain('admin role change recorded:')
}

async function loginToAdmin(page: Page, account: Account, returnTo: string) {
  const probe = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/probe')
    && response.status() === 200
    && response.request().headers().authorization?.startsWith('Bearer '))
  await page.goto(`/admin/login?returnTo=${encodeURIComponent(returnTo)}`)
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: '登录后台' }).click()
  await probe
  await expect(page).toHaveURL(new RegExp(`${returnTo.replaceAll('/', '\\/')}$`))
}

async function createRuntimeConfig(page: Page) {
  const configPost = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/runtime-config') && response.request().method() === 'POST' && response.status() === 201)
  await expect(page.getByRole('heading', { name: '尚无运行配置' })).toBeVisible()
  await page.getByRole('button', { name: '变更未来配置' }).click()
  const dialog = page.getByRole('alertdialog', { name: '确认变更未来运行配置？' })
  await expect(dialog.getByRole('button', { name: '取消' })).toBeFocused()
  const enabled = dialog.getByRole('checkbox', { name: '启用新的运行配置' })
  if (!(await enabled.isChecked())) await enabled.check()
  await dialog.getByLabel('单次调用上限（USD）').fill('0.02')
  await dialog.getByLabel('周期上限（USD）').fill('12')
  await dialog.getByLabel('输入价格（USD / 百万 token）').fill('0.14')
  await dialog.getByLabel('输出价格（USD / 百万 token）').fill('0.28')
  await dialog.getByLabel('变更原因').fill('为隔离 E2E 创建首个启用策略')
  await dialog.getByRole('button', { name: '确认保存未来配置' }).click()
  const response = await configPost
  expect(response.request().headers()['if-match']).toBe('0')
  expect(response.request().headers()['idempotency-key']).toBeTruthy()
  await expect(page.getByText('配置版本 v1')).toBeVisible()
}

async function createAndDisqualifyCatalogEntry(page: Page, suffix: string) {
  // Protected routes keep the Bearer token only in React memory, so navigate through the
  // SPA shell rather than using a full browser load that would deliberately clear it.
  await page.getByRole('link', { name: '营养目录' }).click()
  await expect(page).toHaveURL(/\/admin\/catalog$/)
  await page.getByLabel('菜品名称').fill(`E2E 燕麦 ${suffix}`)
  await page.getByLabel('别名').fill(`E2E燕麦${suffix}, e2e-oats-${suffix}`)
  await page.getByLabel('每 100g 能量（kcal）').fill('389')
  await page.getByLabel('每 100g 蛋白质（g）').fill('16.9')
  await page.getByLabel('每 100g 脂肪（g）').fill('6.9')
  await page.getByLabel('每 100g 碳水（g）').fill('66.3')
  await page.getByLabel('来源名称').fill('USDA FoodData Central')
  await page.getByLabel('来源链接').fill('https://fdc.nal.usda.gov/')
  await page.getByLabel('授权状态').selectOption('authorized')
  await page.getByLabel('变更原因').fill('E2E 验证目录治理的公开审计链')
  await page.getByRole('button', { name: '预览并确认' }).click()
  const draftDialog = page.getByRole('alertdialog', { name: '确认创建营养目录草稿？' })
  await expect(draftDialog.getByText('服务器字段差异')).toBeVisible()
  await expect(draftDialog.getByText(/影响范围：/)).toBeVisible()
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/catalog-drafts') && response.request().method() === 'POST' && response.status() === 201)
  await draftDialog.getByRole('button', { name: '确认创建草稿' }).click()
  await created
  await page.getByRole('link', { name: '审核与发布目录' }).click()
  await expect(page.getByRole('region', { name: '发布前字段差异' })).toBeVisible()

  for (const [button, confirm, reason, responsePath] of [
    ['审核目录草稿', '确认审核草稿', 'E2E 已完成来源复核', '/review'],
    ['发布营养目录版本', '确认发布版本', 'E2E 已确认发布范围', '/publish'],
    ['立即失格', '确认立即失格', 'E2E 验证未来使用立即失格', '/disqualifications'],
  ] as const) {
    await page.getByRole('button', { name: button }).click()
    const dialog = page.getByRole('alertdialog')
    await expect(dialog.getByRole('button', { name: '取消' })).toBeFocused()
    await dialog.getByLabel('变更原因').fill(reason)
    const mutation = page.waitForResponse((response) => response.url().includes(`/api/v1/admin/catalog-${responsePath === '/disqualifications' ? 'publications' : 'drafts'}`) && response.url().endsWith(responsePath) && response.request().method() === 'POST' && response.status() === 200)
    const confirmation = dialog.getByRole('button', { name: confirm })
    await confirmation.scrollIntoViewIfNeeded()
    await expect(confirmation).toBeInViewport()
    await confirmation.click()
    await mutation
  }
  await expect(page.getByText('已立即失格，操作已记录。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '操作审计' })).toBeVisible()
}

test.describe.configure({ mode: 'serial' })

test('verified first admin uses public RuntimeConfig and catalog lifecycle; ordinary user is denied', async ({ browser, page, request }) => {
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const admin = { email: `e2e-admin-${suffix}@example.test`, password: 'E2E-admin-password-2026!' }
  await request.delete(`${mailpitApi}/messages`)
  await registerAndVerify(page, request, admin)
  await bootstrapFirstAdmin(admin)
  await loginToAdmin(page, admin, '/admin/model-configs')
  await createRuntimeConfig(page)
  await createAndDisqualifyCatalogEntry(page, suffix)

  const adminRequests: string[] = []
  page.on('request', (requestEvent) => {
    const url = new URL(requestEvent.url())
    if (url.pathname.startsWith('/api/v1/')) adminRequests.push(url.pathname)
  })
  await page.getByRole('link', { name: '概览' }).click()
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await page.getByRole('link', { name: '运行审计' }).click()
  await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()
  expect(adminRequests).not.toHaveLength(0)
  expect(adminRequests.every((path) => path.startsWith('/api/v1/admin/'))).toBeTruthy()
  await expect(page.locator('body')).not.toContainText(admin.email)
  await expect(page.locator('body')).not.toContainText(/api_key|endpoint|reasoning|provider body/i)

  const ordinaryContext = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const ordinaryPage = await ordinaryContext.newPage()
  const ordinary = { email: `e2e-user-${suffix}@example.test`, password: 'E2E-user-password-2026!' }
  try {
    await registerAndVerify(ordinaryPage, request, ordinary)
    const forbiddenProbe = ordinaryPage.waitForResponse((response) => response.url().endsWith('/api/v1/admin/probe')
      && response.status() === 403
      && response.request().headers().authorization?.startsWith('Bearer '))
    await ordinaryPage.goto('/admin/login?returnTo=/admin/catalog')
    await ordinaryPage.getByLabel('邮箱').fill(ordinary.email)
    await ordinaryPage.getByLabel('密码', { exact: true }).fill(ordinary.password)
    await ordinaryPage.getByRole('button', { name: '登录后台' }).click()
    await forbiddenProbe
    await expect(ordinaryPage).toHaveURL(/\/admin\/forbidden$/)
    await expect(ordinaryPage.getByTestId('admin-shell')).toHaveCount(0)
    await expect(ordinaryPage.getByText('营养目录草稿')).toHaveCount(0)
    await expect(ordinaryPage.getByText('运行概览')).toHaveCount(0)
  } finally {
    await ordinaryContext.close()
  }
})
