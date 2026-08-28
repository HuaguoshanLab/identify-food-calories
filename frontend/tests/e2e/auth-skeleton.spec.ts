import { expect, test } from '@playwright/test'

import {
  clearMailbox,
  createSecondDeviceSession,
  login,
  registerAndActivate,
  resetPasswordThroughUi,
  revokeOtherSession,
  type E2eAccount,
} from './auth-helpers'

const account: E2eAccount = {
  email: 'auth-skeleton@example.test',
  password: 'correct-horse-battery-staple',
  replacementPassword: 'new-correct-horse-battery-staple',
}

test.describe('full-stack auth', () => {
  test.describe.configure({ mode: 'serial' })

  test('uses public APIs and Mailpit to prove registration, recovery and session protection', async ({ browser, page, request }) => {
    await clearMailbox(request)

    await page.setViewportSize({ width: 320, height: 800 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' })).toBeVisible()
    await page.getByRole('link', { name: '创建账号' }).press('Enter')
    await registerAndActivate(page, request, account)
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()

    await login(page, account, '/app/me/sessions')
    await expect(page).toHaveURL(/\/app\/me\/sessions$/)
    await expect(page.getByRole('heading', { name: '登录会话', exact: true })).toBeVisible()

    const secondContext = await createSecondDeviceSession(browser, account)
    await page.reload()
    await revokeOtherSession(page)
    await expect(page.getByRole('status')).toHaveText('登录会话已撤销。')
    const secondPage = secondContext.pages()[0]
    await secondPage.reload()
    await expect(secondPage.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await secondContext.close()

    await page.getByRole('button', { name: '退出当前设备' }).click()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await page.goBack()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()

    await resetPasswordThroughUi(page, request, account)
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await login(page, { ...account, password: account.replacementPassword! }, '/app/me')

    await page.addStyleTag({ content: 'html { font-size: 200%; }' })
    await page.getByRole('link', { name: '登录会话' }).scrollIntoViewIfNeeded()
    await expect(page.getByRole('link', { name: '登录会话' })).toBeVisible()
  })
})
