import { execFile as execFileCallback } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type Page } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

const execFile = promisify(execFileCallback)
const forbiddenTerms = /provider|node|stack|reasoning|raw payload|api[_ -]?key|password|base64|image data/i
const dashboardPath = '/api/v1/dashboard/'
const timezoneContexts = ['Asia/Shanghai'] as const

test.use({ timezoneId: 'Asia/Shanghai' })

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

type DashboardOverviewPayload = {
  today: { consumed_local_date: string }
  week: Array<{ consumed_local_date: string }>
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
  // A fresh account has no stored preference; accepting 409 here would hide a broken confirmation flow.
  expect(confirmationStatuses).toEqual([200])

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

    const isCurrentWindow = url.pathname.endsWith('/overview') || url.pathname.endsWith('/weekly-review')
    if (isCurrentWindow) expect(url.searchParams.has('week_start')).toBeFalsy()
  }
}

function assertOverviewTodayIsInItsServerOwnedWeek(payload: DashboardOverviewPayload) {
  expect(payload.week).toHaveLength(7)
  expect(payload.week.map((day) => day.consumed_local_date)).toContain(payload.today.consumed_local_date)
}

async function bootstrapFirstAdmin(account: E2eAccount) {
  const result = await execFile('../backend/.venv/bin/python', [
    'tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli',
    'bootstrap', '--email', account.email, '--reason', 'Records E2E verified first-admin bootstrap',
  ], { cwd: '../backend' })
  expect(result.stderr).not.toContain(account.password)
  expect(result.stdout).toContain('admin role change recorded:')
}

async function configureTestRuntime(account: E2eAccount) {
  const result = await execFile('../backend/.venv/bin/python', [
    'tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli',
    'runtime-config', '--actor-email', account.email, '--reason', 'Records E2E enabled fake-provider policy',
    '--idempotency-key', `records-runtime-${Date.now()}`,
  ], { cwd: '../backend' })
  expect(result.stderr).not.toContain(account.password)
  expect(result.stdout).toContain('runtime configuration recorded:')
}

test.describe.configure({ mode: 'serial' })

test('runtime policy enables a normal user analyze, save, and Records dashboard', async ({ page, request }) => {
  test.setTimeout(120_000)
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const admin: E2eAccount = { email: `records-admin-${suffix}@example.test`, password: 'Records-admin-password-2026!' }

  await clearMailbox(request)
  await page.goto('/register')
  await registerAndActivate(page, request, admin)
  await bootstrapFirstAdmin(admin)
  await configureTestRuntime(admin)

  for (const timeZone of timezoneContexts) {
    const user: E2eAccount = { email: `records-user-${timeZone.replace('/', '-').toLowerCase()}-${suffix}@example.test`, password: 'Records-user-password-2026!' }
    const userPage = page
    const statisticsObservation = observeStatisticsRequests(userPage)
      await clearMailbox(request)
      await userPage.goto('/register')
      await registerAndActivate(userPage, request, user)
      await login(userPage, user, '/app/analyze')

      await userPage.getByRole('button', { name: '改为文字描述这餐' }).click()
      const stream = userPage.waitForResponse((response) => response.url().includes('/api/v1/agent/')
        && response.headers()['content-type']?.includes('text/event-stream'))
      await userPage.getByLabel('餐食描述').fill('米饭 100 克')
      await userPage.getByRole('button', { name: '开始分析' }).click()
      const streamResponse = await stream
      expect(await streamResponse.text()).not.toMatch(forbiddenTerms)
      await expect(userPage.getByRole('status')).toHaveText('分析已完成')
      await expect(userPage.getByRole('button', { name: '确认并保存' })).toBeVisible()
      await expect(userPage.locator('body')).not.toContainText(forbiddenTerms)

      await userPage.getByRole('radio', { name: '早餐' }).click()
      const savedResponse = userPage.waitForResponse((response) => new URL(response.url()).pathname === '/api/v1/meal-records' && response.request().method() === 'POST')
      await userPage.getByRole('button', { name: '确认并保存' }).click()
      expect((await (await savedResponse).json()).meal_slot).toBe('breakfast')
      await expect(userPage.getByRole('link', { name: /查看记录/ })).toBeVisible()
      await userPage.getByRole('link', { name: /查看记录/ }).click()
      await expect(userPage).toHaveURL(/\/app\/records\/[0-9a-f-]+$/)
      await userPage.getByRole('button', { name: '返回上一页' }).click()
      await expect(userPage).toHaveURL(/\/app\/analyze\?thread=/)
      const overviewResponse = userPage.waitForResponse((response) => {
        const url = new URL(response.url())
        return url.pathname === '/api/v1/dashboard/overview' && response.request().method() === 'GET' && response.status() === 200
      })
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
      assertOverviewTodayIsInItsServerOwnedWeek(await (await overviewResponse).json() as DashboardOverviewPayload)
  }

})
