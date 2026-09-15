import { expect, test } from '@playwright/test'

import { login, registerAndActivate } from './auth-helpers'

test('legacy compound preferences are separated for review without rewriting memories', async ({ page, request }) => {
  const account = { email: 'preference-review@example.test', password: 'correct-horse-battery-staple' }
  await page.goto('/register')
  await registerAndActivate(page, request, account)
  const loginResponse = page.waitForResponse((response) => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST')
  await login(page, account, '/app/me')
  await page.goto('/app/me/memories')
  await expect(page.getByText(/还没有长期偏好/)).toBeVisible()
  // Model historical/manual entries through the public, owner-authenticated API.
  // The token is obtained by the real login above, never fabricated or persisted.
  const { access_token: accessToken } = await (await loginResponse).json()
  const headers = { Authorization: `Bearer ${accessToken}` }
  for (const canonicalText of ['不吃辣 饮食清淡', '今天不吃牛肉']) {
    const created = await page.request.post('/api/v1/memories', { headers, data: { category: 'avoidance', canonical_text: canonicalText } })
    expect(created.status()).toBe(201)
  }
  await page.reload()
  await expect(page.getByRole('link', { name: /不吃辣 饮食清淡/ })).toBeVisible()
  await page.goto('/app/plans')
  await page.getByRole('button', { name: '确认时区' }).click()
  await expect(page.getByText('忌口：已确认 不吃辣', { exact: true })).toBeVisible()
  await expect(page.getByText('口味：已确认 清淡', { exact: true })).toBeVisible()
  await expect(page.getByText(/今天不吃牛肉/)).toHaveCount(0)
  await expect(page.getByLabel('我已复核以上饮食偏好')).not.toBeChecked()
  await page.getByLabel('我已复核以上饮食偏好').check()
  await expect(page.getByLabel('我已复核以上饮食偏好')).toBeChecked()
  await page.getByRole('link', { name: '管理饮食偏好' }).click()
  await expect(page.getByRole('link', { name: /不吃辣 饮食清淡/ })).toBeVisible()
  const original = await page.request.get('/api/v1/memories', { headers })
  expect((await original.json()).map((item: { canonical_text: string }) => item.canonical_text).sort()).toEqual(['不吃辣 饮食清淡', '今天不吃牛肉'].sort())
})
