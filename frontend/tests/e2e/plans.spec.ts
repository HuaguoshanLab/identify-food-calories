import { expect, test } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

test.describe('phase 5 daily planning H5', () => {
  test('a real registered user generates the controlled breakfast, lunch, and dinner snapshot', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'daily-plans@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, account)
    await login(page, account, '/app/plans')

    await page.getByLabel('身高').fill('170')
    await page.getByLabel('体重').fill('65')
    await page.getByLabel('年龄').fill('30')
    await page.getByLabel('使用女性参数').check()
    await page.getByLabel('中度每周规律中等强度活动').check()
    await page.getByLabel('维持体重').check()
    await page.getByLabel('目标速度').selectOption('maintain')
    await page.getByLabel('我已复核以上饮食偏好').check()
    await page.getByRole('button', { name: '生成今日餐单' }).click()

    await expect(page.getByRole('heading', { name: '今日三餐计划' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '早餐' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '午餐' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '晚餐' })).toBeVisible()
    const firstMeal = page.getByRole('heading', { name: '早餐' }).locator('..')
    await expect(firstMeal).toContainText(/\d+g · /)
    await expect(firstMeal).toContainText(/ · /)
    await expect(firstMeal).toContainText('已遵守：')
    await expect(page.getByText('普通饮食参考，不替代医疗建议。')).toBeVisible()
    await page.setViewportSize({ width: 320, height: 932 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  })

  test('a real user can adjust one owned plan without changing the other meal cards', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'daily-plan-adjustment@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, account)
    await login(page, account, '/app/plans')

    await page.getByLabel('身高').fill('170')
    await page.getByLabel('体重').fill('65')
    await page.getByLabel('年龄').fill('30')
    await page.getByLabel('使用女性参数').check()
    await page.getByLabel('中度每周规律中等强度活动').check()
    await page.getByLabel('维持体重').check()
    await page.getByLabel('目标速度').selectOption('maintain')
    await page.getByLabel('我已复核以上饮食偏好').check()
    await page.getByRole('button', { name: '生成今日餐单' }).click()
    await expect(page.getByRole('heading', { name: '今日三餐计划' })).toBeVisible()

    const breakfast = await page.getByRole('heading', { name: '早餐' }).locator('..').innerText()
    const dinner = await page.getByRole('heading', { name: '晚餐' }).locator('..').innerText()
    await page.getByLabel('告诉我们想换什么').fill('午餐换清淡一些')
    await page.getByRole('button', { name: '提交调整' }).click()

    await expect(page.getByText('已更新午餐，其余餐次保持不变。')).toBeFocused()
    await expect(page.getByRole('heading', { name: '午餐' }).locator('..')).toContainText('已调整')
    await expect(page.getByRole('heading', { name: '早餐' }).locator('..')).toHaveText(breakfast)
    await expect(page.getByRole('heading', { name: '晚餐' }).locator('..')).toHaveText(dinner)
  })
})
