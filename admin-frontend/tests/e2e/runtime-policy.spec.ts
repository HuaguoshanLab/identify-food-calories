import { expect, test } from '@playwright/test'
import { bootstrapFirstAdmin, registerAndVerify } from './auth-helpers'

test('a verified administrator configures future runs; ordinary accounts remain forbidden', async ({ browser, page, request }) => {
  const admin = { email: `runtime-admin-${Date.now()}@example.test`, password: 'Runtime-policy-test-2026!' }
  await registerAndVerify(page, request, admin)
  await bootstrapFirstAdmin(admin)
  await page.goto('/admin/login?returnTo=/admin/model-configs')
  await page.getByLabel('邮箱').fill(admin.email)
  await page.getByLabel('密码', { exact: true }).fill(admin.password)
  await page.getByRole('button', { name: '登录后台' }).click()
  await expect(page.getByRole('heading', { name: '文字模型尚无运行策略' })).toBeVisible()
  await page.getByRole('button', { name: '修改文字模型设置' }).click()
  const dialog = page.getByRole('alertdialog', { name: '确认变更未来运行配置？' })
  await dialog.getByRole('checkbox', { name: '启用新的运行配置' }).check()
  await dialog.getByLabel('单次调用上限（USD）').fill('0.02')
  await dialog.getByLabel('周期上限（USD）').fill('12')
  await dialog.getByLabel('输入价格（USD / 百万 token）').fill('0.14')
  await dialog.getByLabel('输出价格（USD / 百万 token）').fill('0.28')
  await dialog.getByLabel('变更原因').fill('隔离浏览器门禁验证 Fake Provider 运行策略')
  const created = page.waitForResponse(response => response.url().endsWith('/api/v1/admin/runtime-config') && response.request().method() === 'POST')
  await dialog.getByRole('button', { name: '确认保存未来配置' }).click()
  const mutation = await created
  expect(mutation.status()).toBe(201)
  expect(mutation.request().headers()['if-match']).toBe('0')
  expect(mutation.request().headers()['idempotency-key']).toBeTruthy()
  await expect(page.getByText('当前运行策略：第 1 版')).toBeVisible()
  await page.reload()
  await expect(page.getByText('当前运行策略：第 1 版')).toBeVisible()
  await page.getByRole('link', { name: '操作审计' }).click()
  await expect(page.getByRole('table')).toBeVisible()

  const ordinaryContext = await browser.newContext()
  try {
    const ordinaryPage = await ordinaryContext.newPage()
    const ordinary = { email: `runtime-user-${Date.now()}@example.test`, password: admin.password }
    await registerAndVerify(ordinaryPage, request, ordinary)
    await ordinaryPage.goto(`http://127.0.0.1:${process.env.E2E_ADMIN_FRONTEND_PORT ?? '5184'}/admin/login?returnTo=/admin/model-configs`)
    await ordinaryPage.getByLabel('邮箱').fill(ordinary.email)
    await ordinaryPage.getByLabel('密码', { exact: true }).fill(ordinary.password)
    const denied = ordinaryPage.waitForResponse(response => response.url().endsWith('/api/v1/admin/probe') && response.status() === 403)
    await ordinaryPage.getByRole('button', { name: '登录后台' }).click()
    await denied
    await expect(ordinaryPage).toHaveURL(/\/admin\/forbidden$/)
    await expect(ordinaryPage.getByRole('button', { name: '修改文字模型设置' })).toHaveCount(0)
  } finally {
    await ordinaryContext.close()
  }
})
