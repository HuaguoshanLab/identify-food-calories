import { expect, test } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

test('真实登录后的记录页显示低覆盖周复盘且公开 API 不泄露 Provider 细节', async ({ page, request }) => {
  const account: E2eAccount = { email: `weekly-review-${Date.now()}@example.test`, password: 'SafePassphrase123!' }
  await clearMailbox(request)
  await page.goto('/register')
  await registerAndActivate(page, request, account)
  await login(page, account, '/app/records')

  const response = await page.request.get('/api/v1/dashboard/weekly-review')
  expect(response.ok()).toBeTruthy()
  const review = await response.json() as { status: string; suggestions: unknown[]; provider_error?: unknown; abstention_code?: unknown }
  expect(review.status).toBe('insufficient_coverage')
  expect(review.suggestions).toEqual([])
  expect(review.provider_error).toBeUndefined()
  expect(review.abstention_code).toBeUndefined()

  await expect(page.getByRole('heading', { name: '周复盘' })).toBeVisible()
  await expect(page.getByText(/记录仍不足以生成建议/)).toBeVisible()
  await expect(page.getByRole('button', { name: '重新生成' })).toHaveCount(0)
})
