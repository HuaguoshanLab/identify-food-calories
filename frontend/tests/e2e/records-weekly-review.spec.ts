import { expect, test } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

test('真实登录后的记录页显示低覆盖周复盘且公开 API 不泄露 Provider 细节', async ({ page, request }) => {
  const account: E2eAccount = { email: `weekly-review-${Date.now()}@example.test`, password: 'SafePassphrase123!' }
  const observedRequests: Array<{ url: string; method: string; headers: Record<string, string>; postData: string | null }> = []
  const confirmationStatuses: number[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (url.pathname === '/api/v1/meal-records/dashboard-time-zone-confirmations' || url.pathname === '/api/v1/dashboard/weekly-review') {
      observedRequests.push({ url: request.url(), method: request.method(), headers: request.headers(), postData: request.postData() })
    }
  })
  page.on('response', (response) => {
    if (new URL(response.url()).pathname === '/api/v1/meal-records/dashboard-time-zone-confirmations'
      && response.request().method() === 'POST') confirmationStatuses.push(response.status())
  })
  await clearMailbox(request)
  await page.goto('/register')
  await registerAndActivate(page, request, account)
  const weeklyReviewResponse = page.waitForResponse((response) => response.url().includes('/api/v1/dashboard/weekly-review?week_start=') && response.request().method() === 'GET')
  await login(page, account, '/app/records')

  const response = await weeklyReviewResponse
  expect(response.ok()).toBeTruthy()
  const body = await response.json() as { status: string; suggestions: unknown[]; provider_error?: unknown; abstention_code?: unknown }
  expect(body.status).toBe('insufficient_coverage')
  expect(body.suggestions).toEqual([])
  expect(body.provider_error).toBeUndefined()
  expect(body.abstention_code).toBeUndefined()

  const confirmationIndex = observedRequests.findIndex((request) => new URL(request.url).pathname === '/api/v1/meal-records/dashboard-time-zone-confirmations'
    && request.method === 'POST')
  const reviewIndex = observedRequests.findIndex((request) => new URL(request.url).pathname === '/api/v1/dashboard/weekly-review'
    && request.method === 'GET')
  expect(confirmationIndex).toBeGreaterThanOrEqual(0)
  expect(reviewIndex).toBeGreaterThan(confirmationIndex)
  const confirmation = observedRequests[confirmationIndex]
  if (!confirmation) throw new Error('statistics timezone confirmation was not observed')
  expect(JSON.parse(confirmation.postData ?? '{}')).toEqual({ time_zone: expect.any(String) })
  expect(confirmationStatuses.some((status) => status === 200 || status === 409)).toBeTruthy()
  const reviewRequest = observedRequests[reviewIndex]
  if (!reviewRequest) throw new Error('weekly review request was not observed')
  const reviewUrl = new URL(reviewRequest.url)
  expect(reviewUrl.searchParams.has('time_zone')).toBeFalsy()
  expect(reviewRequest.headers.time_zone).toBeUndefined()
  expect(reviewRequest.headers['x-time-zone']).toBeUndefined()
  expect(reviewRequest.postData).toBeNull()

  await expect(page.getByRole('heading', { name: '周复盘' })).toBeVisible()
  await expect(page.getByText(/记录仍不足以生成建议/)).toBeVisible()
  await expect(page.getByRole('button', { name: '重新生成' })).toHaveCount(0)
})
