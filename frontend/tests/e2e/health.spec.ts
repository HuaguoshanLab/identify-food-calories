import { expect, test } from '@playwright/test'

test('full-stack health starts React and FastAPI without manual services', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: '饮食健康 Agent' })).toBeVisible()
  await expect(page.getByRole('status')).toContainText('后端状态：正常（API v1）')

  const health = await page.evaluate(async () => {
    const response = await fetch('http://127.0.0.1:8000/api/v1/health')
    return { status: response.status, body: await response.json() }
  })

  expect(health).toEqual({
    status: 200,
    body: { status: 'ok', version: 'v1' },
  })
})
