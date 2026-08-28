import { expect, test } from '@playwright/test'

import {
  clearMailbox,
  createSecondDeviceSession,
  login,
  registerAndActivate,
  type E2eAccount,
} from './auth-helpers'

const visualAccount: E2eAccount = {
  email: 'h5-visual@example.test',
  password: 'h5-visual-password',
}

const screenshotOptions = {
  animations: 'disabled' as const,
  fullPage: true,
}

test.describe('H5 visual and interaction contract', () => {
  test.describe.configure({ mode: 'serial' })
  test.use({ colorScheme: 'light', reducedMotion: 'reduce', viewport: { width: 430, height: 932 } })

  test('captures eight deterministic 430px baselines from a real account lifecycle', async ({ browser, page, request }) => {
    await clearMailbox(request)

    await page.goto('/')
    await expect(page.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' })).toBeVisible()
    await expect(page).toHaveScreenshot('landing-430.png', screenshotOptions)

    await page.getByRole('link', { name: '登录' }).click()
    await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
    await expect(page).toHaveScreenshot('login-430.png', screenshotOptions)

    await page.getByRole('link', { name: '创建账号' }).click()
    await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
    await expect(page).toHaveScreenshot('register-430.png', screenshotOptions)
    await registerAndActivate(page, request, visualAccount)

    await login(page, visualAccount, '/app/analyze')
    await expect(page.getByRole('heading', { name: '分析' })).toBeVisible()
    await expect(page).toHaveScreenshot('analyze-430.png', screenshotOptions)

    await page.getByRole('link', { name: '我的' }).click()
    await expect(page.getByRole('heading', { name: '我的' })).toBeVisible()
    await expect(page).toHaveScreenshot('me-430.png', screenshotOptions)

    await page.getByRole('link', { name: '账号资料' }).click()
    await expect(page.locator('h1', { hasText: '账号资料' })).toBeVisible()
    await expect(page).toHaveScreenshot('account-430.png', screenshotOptions)

    await page.getByRole('link', { name: '返回我的' }).click()
    const secondDevice = await createSecondDeviceSession(browser, visualAccount)
    await page.getByRole('link', { name: '登录会话' }).click()
    await expect(page.locator('h1', { hasText: '登录会话' })).toBeVisible()
    await expect(page).toHaveScreenshot('sessions-430.png', {
      ...screenshotOptions,
      mask: [page.getByTestId('session-dates')],
    })

    await page.getByRole('button', { name: '撤销会话' }).click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    await expect(page).toHaveScreenshot('revoke-dialog-430.png', {
      ...screenshotOptions,
      mask: [page.getByTestId('session-dates')],
    })
    await secondDevice.context.close()
  })

  test('keeps responsive geometry, one scrolling owner, keyboard operations, and tab history observable', async ({ browser, page }) => {
    await page.setViewportSize({ width: 320, height: 800 })
    await login(page, visualAccount, '/app/me/sessions')
    await createSecondDeviceSession(browser, visualAccount)
    await page.reload()

    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
    const revokeButton = page.getByRole('button', { name: '撤销会话' }).last()
    await revokeButton.scrollIntoViewIfNeeded()
    const revokeBox = await revokeButton.boundingBox()
    expect(revokeBox?.width).toBeGreaterThanOrEqual(44)

    await revokeButton.click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('alertdialog')).toBeHidden()
    await expect(revokeButton).toBeFocused()

    await page.goto('/app/me')
    const skipLink = page.getByRole('link', { name: '跳到主要内容' })
    await skipLink.focus()
    await expect(skipLink).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.getByTestId('page-scroll-area')).toBeFocused()

    const accountLink = page.getByRole('link', { name: '账号资料' })
    await page.keyboard.press('Tab')
    await expect(accountLink).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/app\/me\/account$/)
    await page.goBack()
    await expect(page).toHaveURL(/\/app\/me(?:#main-content)?$/)

    await page.getByRole('link', { name: '分析' }).click()
    await expect(page).toHaveURL(/\/app\/analyze$/)
    await page.goBack()
    await expect(page).toHaveURL(/\/app\/me(?:#main-content)?$/)

    for (const viewport of [768, 1024, 1440]) {
      await page.setViewportSize({ width: viewport, height: 1000 })
      const frame = page.getByTestId('mobile-frame')
      await expect(frame).toBeVisible()
      const box = await frame.boundingBox()
      expect(box?.width).toBe(430)
      expect(Math.abs((box?.x ?? 0) - (viewport - 430) / 2)).toBeLessThanOrEqual(1)
      expect(box?.height).toBeLessThanOrEqual(932)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
      await expect(page.getByTestId('page-scroll-area')).toHaveCount(1)
      await expect(frame).toHaveCSS('overflow-y', 'hidden')
    }
  })
})
