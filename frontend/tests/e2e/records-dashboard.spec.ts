import { execFile as execFileCallback } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type Page } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

const execFile = promisify(execFileCallback)
const adminFrontendUrl = `http://127.0.0.1:${process.env.E2E_RECORDS_ADMIN_FRONTEND_PORT ?? '5185'}`
const forbiddenTerms = /provider|node|stack|reasoning|raw payload|api[_ -]?key|password|base64|image data/i
const dashboardPath = '/api/v1/dashboard/'
const timezoneContexts = ['Asia/Shanghai', 'America/Los_Angeles'] as const

type ObservedRequest = {
  url: string
  method: string
  headers: Record<string, string>
  postData: string | null
}

type StatisticsObservation = {
  requests: ObservedRequest[]
  confirmationStatuses: number[]
}

function observeStatisticsRequests(page: Page): StatisticsObservation {
  const requests: ObservedRequest[] = []
  const confirmationStatuses: number[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/meal-records/dashboard-time-zone-confirmations' || url.pathname.startsWith(dashboardPath)) {
      requests.push({ url: request.url(), method: request.method(), headers: request.headers(), postData: request.postData() })
    }
  })
  page.on('response', (response) => {
    if (new URL(response.url()).pathname === '/api/v1/meal-records/dashboard-time-zone-confirmations'
      && response.request().method() === 'POST') confirmationStatuses.push(response.status())
  })
  return { requests, confirmationStatuses }
}

function assertConfirmedDashboardReadContract(observation: StatisticsObservation, timeZone: string) {
  const { requests, confirmationStatuses } = observation
  const confirmationIndex = requests.findIndex((request) => new URL(request.url).pathname === '/api/v1/meal-records/dashboard-time-zone-confirmations'
    && request.method === 'POST')
  expect(confirmationIndex).toBeGreaterThanOrEqual(0)
  const confirmation = requests[confirmationIndex]
  if (!confirmation) throw new Error('statistics timezone confirmation was not observed')
  expect(JSON.parse(confirmation.postData ?? '{}')).toEqual({ time_zone: timeZone })
  expect(confirmationStatuses.some((status) => status === 200 || status === 409)).toBeTruthy()

  const dashboardRequests = requests.filter((request) => new URL(request.url).pathname.startsWith(dashboardPath) && request.method === 'GET')
  expect(dashboardRequests.length).toBeGreaterThanOrEqual(3)
  expect(dashboardRequests.some((request) => new URL(request.url).pathname.endsWith('/overview'))).toBeTruthy()
  expect(dashboardRequests.some((request) => new URL(request.url).pathname.endsWith('/history'))).toBeTruthy()
  expect(dashboardRequests.some((request) => new URL(request.url).pathname.endsWith('/weekly-review'))).toBeTruthy()

  for (const request of dashboardRequests) {
    expect(requests.indexOf(request)).toBeGreaterThan(confirmationIndex)
    const url = new URL(request.url)
    expect(url.searchParams.has('time_zone')).toBeFalsy()
    expect(request.headers.time_zone).toBeUndefined()
    expect(request.headers['x-time-zone']).toBeUndefined()
    expect(request.postData).toBeNull()
  }
}

async function bootstrapFirstAdmin(account: E2eAccount) {
  const result = await execFile('../backend/.venv/bin/python', [
    'tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli',
    'bootstrap', '--email', account.email, '--reason', 'Records E2E verified first-admin bootstrap',
  ], { cwd: '../backend' })
  expect(result.stderr).not.toContain(account.password)
  expect(result.stdout).toContain('admin role change recorded:')
}

async function loginToAdmin(page: Page, account: E2eAccount) {
  const probe = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/probe')
    && response.request().headers().authorization?.startsWith('Bearer ')
    && response.status() === 200)
  await page.goto(`${adminFrontendUrl}/admin/login?returnTo=/admin/model-configs`)
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: '登录后台' }).click()
  await probe
  await expect(page).toHaveURL(/\/admin\/model-configs$/)
}

async function createEnabledRuntimeConfig(page: Page) {
  const post = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/runtime-config')
    && response.request().method() === 'POST' && response.status() === 201)
  await expect(page.getByRole('heading', { name: '尚无运行配置' })).toBeVisible()
  await page.getByRole('button', { name: '变更未来配置' }).click()
  const dialog = page.getByRole('alertdialog', { name: '确认变更未来运行配置？' })
  const enabled = dialog.getByRole('checkbox', { name: '启用新的运行配置' })
  if (!(await enabled.isChecked())) await enabled.check()
  await dialog.getByLabel('单次调用上限（USD）').fill('0.02')
  await dialog.getByLabel('周期上限（USD）').fill('12')
  await dialog.getByLabel('输入价格（USD / 百万 token）').fill('0.14')
  await dialog.getByLabel('输出价格（USD / 百万 token）').fill('0.28')
  await dialog.getByLabel('变更原因').fill('为 Records 隔离 E2E 创建首个启用策略')
  await dialog.getByRole('button', { name: '确认保存未来配置' }).click()
  const response = await post
  expect(response.request().headers()['if-match']).toBe('0')
  expect(response.request().headers()['idempotency-key']).toBeTruthy()
  await expect(page.getByText('配置版本 v1')).toBeVisible()
}

test.describe.configure({ mode: 'serial' })

test('admin RuntimeConfig preflight enables a normal user analyze, safe SSE, save, and Records dashboard', async ({ browser, page, request }) => {
  test.setTimeout(90_000)
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const admin: E2eAccount = { email: `records-admin-${suffix}@example.test`, password: 'Records-admin-password-2026!' }

  await clearMailbox(request)
  await page.goto('/register')
  await registerAndActivate(page, request, admin)
  await bootstrapFirstAdmin(admin)

  const adminContext = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const adminPage = await adminContext.newPage()
  try {
    await loginToAdmin(adminPage, admin)
    await createEnabledRuntimeConfig(adminPage)
  } finally {
    await adminContext.close()
  }

  for (const timeZone of timezoneContexts) {
    const user: E2eAccount = { email: `records-user-${timeZone.replace('/', '-').toLowerCase()}-${suffix}@example.test`, password: 'Records-user-password-2026!' }
    const userContext = await browser.newContext({ timezoneId: timeZone })
    const userPage = await userContext.newPage()
    const statisticsObservation = observeStatisticsRequests(userPage)
    try {
      await clearMailbox(request)
      await userPage.goto('/register')
      await registerAndActivate(userPage, request, user)
      await login(userPage, user, '/app/analyze')

      const stream = userPage.waitForResponse((response) => response.url().includes('/api/v1/agent/')
        && response.headers()['content-type']?.includes('text/event-stream'))
      await userPage.getByLabel('餐食描述').fill('米饭 100 克')
      await userPage.getByRole('button', { name: '开始分析' }).click()
      const streamResponse = await stream
      expect(await streamResponse.text()).not.toMatch(forbiddenTerms)
      await expect(userPage.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
      await expect(userPage.getByRole('button', { name: '确认并保存' })).toBeVisible()
      await expect(userPage.locator('body')).not.toContainText(forbiddenTerms)

      await userPage.getByRole('button', { name: '确认并保存' }).click()
      await expect(userPage.getByRole('link', { name: /查看记录/ })).toBeVisible()
      await userPage.getByRole('link', { name: /查看记录/ }).click()
      await expect(userPage).toHaveURL(/\/app\/records\/[0-9a-f-]+$/)
      await userPage.getByRole('button', { name: '返回上一页' }).click()
      await expect(userPage).toHaveURL(/\/app\/analyze\?thread=/)
      await userPage.getByRole('link', { name: '记录', exact: true }).click()
      await expect(userPage).toHaveURL(/\/app\/records$/)
      await expect(userPage.getByText('今日已记录摄入')).toBeVisible()
      await expect(userPage.getByRole('img', { name: '近七日能量趋势' })).toBeVisible()
      await expect(userPage.getByRole('table', { name: '近七日能量数据表' })).toBeVisible()
      await expect(userPage.getByRole('heading', { name: '历史记录' })).toBeVisible()
      await expect(userPage.getByRole('heading', { name: '周复盘' })).toBeVisible()
      await expect(userPage.getByText(/记录仍不足以生成建议/)).toBeVisible()
      await expect(userPage.getByRole('link', { name: '分析' })).toBeVisible()
      await expect(userPage.getByRole('link', { name: '计划' })).toBeVisible()
      await expect(userPage.getByRole('link', { name: '记录' })).toBeVisible()
      await expect(userPage.getByRole('link', { name: '我的' })).toBeVisible()
      await expect(userPage.locator('body')).not.toContainText(forbiddenTerms)
      await expect.poll(() => statisticsObservation.requests.filter((request) => new URL(request.url).pathname.startsWith(dashboardPath)).length).toBeGreaterThanOrEqual(3)
      assertConfirmedDashboardReadContract(statisticsObservation, timeZone)
    } finally {
      await userContext.close()
    }
  }
})
