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
    await expect(page.getByRole('heading', { name: '米饭' })).toBeVisible()
    await expect(page.getByText('100g · 130.0 kcal')).toBeVisible()
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

  test('phase 2 resumes a single clarification, applies a correction, and hides a foreign thread', async ({ browser, page, request }) => {
    await clearMailbox(request)
    const owner: E2eAccount = { email: 'agent-resume-owner@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, owner)
    await login(page, owner, '/app/analyze')

    await page.getByLabel('餐食描述').fill('米饭')
    await page.getByRole('button', { name: '开始分析' }).click()
    await expect(page.getByRole('region', { name: '集中补充信息' })).toBeVisible()
    await page.getByLabel('rice-1 克数').fill('100')
    await page.getByRole('button', { name: '提交补充信息' }).click()
    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    const threadId = new URL(page.url()).searchParams.get('thread')
    expect(threadId).toBeTruthy()

    await page.getByLabel('修正或排除项目').fill('米饭改为 150 克')
    await page.getByRole('button', { name: '应用修正' }).click()
    await expect(page.getByText('150g · 195.0 kcal')).toBeVisible()
    await expect(page.getByText('合计 195.0 kcal')).toBeVisible()

    const foreignContext = await browser.newContext()
    const foreignPage = await foreignContext.newPage()
    const foreign: E2eAccount = { email: 'agent-foreign@example.test', password: 'correct-horse-battery-staple' }
    await foreignPage.goto('/register')
    await registerAndActivate(foreignPage, request, foreign)
    await login(foreignPage, foreign, '/app/analyze')
    await foreignPage.goto(`/app/analyze?thread=${threadId}`)
    await expect(foreignPage).not.toHaveURL(/thread=/)
    await expect(foreignPage.getByRole('heading', { name: '分析这餐' })).toBeVisible()
    await expect(foreignPage.getByRole('heading', { name: '营养分析报告' })).toBeHidden()
    await foreignContext.close()
  })

  test('phase 2 delete thread requires confirmation and makes the public thread unavailable', async ({ page, request }) => {
    await clearMailbox(request)
    const deleting: E2eAccount = { email: 'agent-delete@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, deleting)
    await login(page, deleting, '/app/analyze')
    await page.getByLabel('餐食描述').fill('米饭 100 克')
    await page.getByRole('button', { name: '开始分析' }).click()
    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    const threadId = new URL(page.url()).searchParams.get('thread')
    expect(threadId).toBeTruthy()
    await page.getByRole('button', { name: '删除这次分析' }).click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    await page.getByRole('button', { name: '确认删除' }).click()
    await expect(page.getByText('删除请求已提交：分析、事件流和本地缓存已关闭，数据将在 24 小时内清理。')).toBeVisible()
    await expect(page).not.toHaveURL(/thread=/)
    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeHidden()
    await page.goto(`/app/analyze?thread=${threadId}`)
    await expect(page).not.toHaveURL(/thread=/)
    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeHidden()
  })
})

test.describe('phase 3 multimodal image upload', () => {
  test('a real authenticated page uploads one image and shows an explicitly estimated report', async ({ page, request }) => {
    await clearMailbox(request)
    const imageAccount: E2eAccount = { email: 'agent-image-upload@example.test', password: 'correct-horse-battery-staple' }
    await page.goto('/register')
    await registerAndActivate(page, request, imageAccount)
    await login(page, imageAccount, '/app/analyze')

    let uploadCount = 0
    page.on('request', (candidate) => {
      if (candidate.method() === 'POST' && /\/api\/v1\/agent\/threads\/[^/]+\/images$/.test(candidate.url())) uploadCount += 1
    })
    await page.getByLabel('从相册选择上传').setInputFiles({
      name: 'meal.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP8zwACTGCSAQANHQEDgslx/wAAAABJRU5ErkJggg==', 'base64'),
    })

    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    await expect(page.getByText('估算重量', { exact: true })).toBeVisible()
    await expect(page.getByText('估算重量，可能与实际份量存在偏差。')).toBeVisible()
    expect(uploadCount).toBe(1)
  })
})

test.describe('phase 4 direct preference memory', () => {
  test('a real user can capture, maintain, delete, and refresh an explicit avoidance', async ({ page, request }) => {
    await clearMailbox(request)
    const memoryAccount: E2eAccount = {
      email: 'agent-direct-memory@example.test',
      password: 'correct-horse-battery-staple',
    }
    await page.goto('/register')
    await registerAndActivate(page, request, memoryAccount)
    await login(page, memoryAccount, '/app/analyze')

    await page.getByLabel('餐食描述').fill('米饭 100 克，我不吃辣')
    await page.getByRole('button', { name: '开始分析' }).click()
    await expect(page.getByRole('heading', { name: '营养分析报告' })).toBeVisible()
    await expect(page.getByText('合计 130.0 kcal')).toBeVisible()

    await page.getByRole('link', { name: '我的' }).click()
    await page.getByRole('link', { name: '饮食偏好与记忆' }).click()
    await expect(page.getByRole('heading', { name: '饮食偏好与记忆' })).toBeVisible()
    const memoryLink = page.getByRole('link', { name: /忌口 · 不吃辣/ })
    await expect(memoryLink).toBeVisible()
    await expect(page.getByText(/用户直接表达 · 更新于/)).toBeVisible()
    await expect(page.getByText(/fake-direct|request_key|external_memory_id/)).toHaveCount(0)

    await memoryLink.click()
    const memoryId = page.url().match(/\/app\/me\/memories\/([^/]+)\/edit/)?.[1]
    expect(memoryId).toBeTruthy()
    await page.getByLabel('偏好内容').fill('不吃微辣')
    await page.getByRole('button', { name: '保存修改' }).click()
    await expect(page.getByText('忌口 · 不吃微辣')).toBeVisible()
    await expect(page.getByText(/用户手动维护 · 更新于/)).toBeVisible()

    await page.getByRole('link', { name: /忌口 · 不吃微辣/ }).click()
    await page.getByRole('button', { name: '删除这条记忆' }).click()
    await expect(page.getByRole('alertdialog')).toBeVisible()
    await page.getByRole('button', { name: '确认删除' }).click()
    await expect(page.getByText('还没有长期偏好。你在分析时明确说明的饮食目标和忌口会保存在这里。')).toBeVisible()
    await page.reload()
    await expect(page.getByText('还没有长期偏好。你在分析时明确说明的饮食目标和忌口会保存在这里。')).toBeVisible()
    await page.setViewportSize({ width: 320, height: 932 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  })
})
