import { expect, test } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

test.describe('phase 5 personal profile', () => {
  test('a real user can view, edit, and delete only body and goal details', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'planning-profile@example.test', password: 'correct-horse-battery-staple' }
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
    await page.getByLabel('将本次身体资料和目标保存到个人资料').check()
    await page.getByRole('button', { name: '生成今日餐单' }).click()

    await page.getByRole('link', { name: '我的' }).click()
    await page.getByRole('link', { name: '个人资料' }).click()
    await expect(page.getByRole('heading', { name: '个人资料', exact: true })).toBeVisible()
    await expect(page.getByText('170 cm')).toBeVisible()
    await expect(page.getByRole('link', { name: '管理饮食偏好' })).toHaveAttribute('href', '/app/me/memories')
    await expect(page.getByLabel(/忌口|口味/)).toHaveCount(0)

    await page.getByRole('button', { name: '编辑个人资料' }).click()
    await page.getByLabel('身高').fill('171')
    await page.getByRole('button', { name: '保存个人资料' }).click()
    await expect(page.getByText('171 cm')).toBeVisible()

    await page.getByRole('button', { name: '删除个人资料' }).click()
    await expect(page.getByRole('alertdialog')).toContainText('删除个人资料后，后续计划将不再读取这些身体资料和目标。此操作无法撤销。')
    await page.getByRole('button', { name: '确认删除' }).click()
    await expect(page.getByRole('heading', { name: '还没有保存个人资料' })).toBeVisible()
    await expect(page.getByRole('link', { name: '去计划页填写' })).toHaveAttribute('href', '/app/plans')
    await page.setViewportSize({ width: 320, height: 932 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  })
})
