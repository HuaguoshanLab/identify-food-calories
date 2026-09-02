import { expect, test, type Page } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

function mealCard(page: Page, mealName: '早餐' | '午餐' | '晚餐') {
  return page.getByRole('heading', { name: mealName, exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
}

test.describe('phase 5 daily planning H5', () => {
  test('a real registered user generates the controlled breakfast, lunch, and dinner snapshot', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'daily-plans@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, account)
    await login(page, account, '/app/plans')

    await page.getByLabel('身高').fill('170')
    await page.getByRole('spinbutton', { name: '体重' }).fill('65')
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
    const firstMeal = mealCard(page, '早餐')
    await expect(firstMeal).toContainText(/\d+g · /)
    await expect(firstMeal).toContainText(/ · /)
    await expect(firstMeal).toContainText('已遵守：')
    await expect(page.locator('footer')).toHaveText('普通饮食参考，不替代医疗建议。')
    for (const width of [320, 375, 430, 768]) {
      await page.setViewportSize({ width, height: 932 })
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    }
  })

  test('a real user can adjust one owned plan without changing the other meal cards or the reading position', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'daily-plan-adjustment@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, account)
    await login(page, account, '/app/plans')

    await page.getByLabel('身高').fill('170')
    await page.getByRole('spinbutton', { name: '体重' }).fill('65')
    await page.getByLabel('年龄').fill('30')
    await page.getByLabel('使用女性参数').check()
    await page.getByLabel('中度每周规律中等强度活动').check()
    await page.getByLabel('维持体重').check()
    await page.getByLabel('目标速度').selectOption('maintain')
    await page.getByLabel('我已复核以上饮食偏好').check()
    await page.getByRole('button', { name: '生成今日餐单' }).click()
    await expect(page.getByRole('heading', { name: '今日三餐计划' })).toBeVisible()

    const breakfast = await mealCard(page, '早餐').innerText()
    const dinner = await mealCard(page, '晚餐').innerText()
    await page.getByLabel('告诉我们想换什么').fill('午餐换清淡一些')
    const submitButton = page.getByRole('button', { name: '提交调整' })
    const scrollArea = page.getByTestId('page-scroll-area')
    await scrollArea.evaluate((element) => { element.scrollTop = element.scrollHeight })
    const scrollTopBeforeAdjustment = await scrollArea.evaluate((element) => element.scrollTop)
    expect(scrollTopBeforeAdjustment).toBeGreaterThan(0)
    await submitButton.focus()
    await expect(submitButton).toBeFocused()
    await submitButton.click()

    const completionSummary = page.getByText('已更新午餐，其余餐次保持不变。')
    await expect(completionSummary).toBeVisible()
    await expect(completionSummary).toHaveAttribute('aria-live', 'polite')
    await expect(completionSummary).not.toHaveAttribute('tabindex')
    await expect(completionSummary).not.toBeFocused()
    await expect(submitButton).toBeFocused()
    await expect.poll(() => scrollArea.evaluate((element) => element.scrollTop)).toBe(scrollTopBeforeAdjustment)
    await expect(mealCard(page, '午餐')).toContainText('已调整')
    expect(await mealCard(page, '早餐').innerText()).toBe(breakfast)
    expect(await mealCard(page, '晚餐').innerText()).toBe(dinner)
  })
})
