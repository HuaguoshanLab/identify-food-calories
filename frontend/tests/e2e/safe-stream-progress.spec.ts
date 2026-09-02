import { expect, test } from '@playwright/test'

import { clearMailbox, login, registerAndActivate, type E2eAccount } from './auth-helpers'

test.describe('safe stream progress', () => {
  test('a real user sees safe analysis stages without internal details and retains keyboard focus', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'safe-analysis-progress@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, account)
    await login(page, account, '/app/analyze')

    await page.getByLabel('餐食描述').fill('米饭 100 克')
    const submit = page.getByRole('button', { name: '开始分析' })
    await submit.focus()
    await submit.click()

    await expect(page.getByRole('status')).toContainText(/正在识别餐食信息|等待你补充信息|正在进行营养计算|正在校验分析结果|分析已完成/)
    await expect(page.getByText(/provider|node|stack|reasoning|raw payload/i)).toHaveCount(0)
    await expect(submit).toBeFocused()
  })

  test('a real user sees safe planning stages without a synthetic completion', async ({ page, request }) => {
    await clearMailbox(request)
    const account: E2eAccount = { email: 'safe-planning-progress@example.test', password: 'correct-horse-battery-staple' }
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
    const submit = page.getByRole('button', { name: '生成今日餐单' })
    await submit.focus()
    await submit.click()

    await expect(page.getByRole('status')).toContainText(/正在读取已确认的资料与饮食偏好|等待你补充信息|正在计算每日目标区间|正在校验营养与已确认约束|计划已生成|本次计划暂未完成，你可以重新尝试/)
    await expect(page.getByRole('status')).not.toContainText('计划已生成')
    await expect(page.getByText(/provider|node|stack|reasoning|raw payload/i)).toHaveCount(0)
    await expect(submit).toBeFocused()
  })
})
