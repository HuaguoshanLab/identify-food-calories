import { expect, test } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

const account: E2eAccount = {
  email: 'agent-direct-grams@example.test',
  password: 'correct-horse-battery-staple',
}

test.describe('phase 2 direct grams contract', () => {
  test('a normally registered user receives the controlled rice snapshot', async ({ page, request }) => {
    await clearMailbox(request)
    await page.goto('/register')
    await registerAndActivate(page, request, account)
    await login(page, account, '/app/analyze')

    await page.getByLabel('餐食描述').fill('米饭 100 克')
    await page.getByRole('button', { name: '开始分析' }).click()

    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    await expect(page.getByText('合计 130.0 kcal')).toBeVisible()
    await expect(page.getByText('蛋白质 2.7g · 脂肪 0.3g · 碳水 28.2g')).toBeVisible()
    await expect(page.getByText('普通饮食参考，不替代医疗建议。')).toBeVisible()
  })

  test('phase 2 reconnect reloads the same authoritative thread without a second analysis command', async ({ page, request }) => {
    await clearMailbox(request)
    await page.goto('/register')
    await registerAndActivate(page, request, {
      email: 'agent-reconnect@example.test',
      password: 'correct-horse-battery-staple',
    })
    await login(page, {
      email: 'agent-reconnect@example.test',
      password: 'correct-horse-battery-staple',
    }, '/app/analyze')

    await page.getByLabel('餐食描述').fill('米饭 100 克')
    await page.getByRole('button', { name: '开始分析' }).click()
    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    let followupCommands = 0
    page.on('request', (candidate) => {
      if (candidate.method() === 'POST' && /\/api\/v1\/agent\/threads(?:\?|$)/.test(candidate.url())) {
        followupCommands += 1
      }
    })

    await page.reload()

    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    await expect(page.getByText('合计 130.0 kcal')).toBeVisible()
    expect(followupCommands).toBe(0)
  })
})
