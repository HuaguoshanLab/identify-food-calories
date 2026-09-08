import { execFile as execFileCallback } from 'node:child_process'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const execFile = promisify(execFileCallback)
const mailpitApi = 'http://127.0.0.1:8025/api/v1'
const userFrontendUrl = `http://127.0.0.1:${process.env.E2E_ADMIN_USER_FRONTEND_PORT ?? '5183'}`

type Account = Readonly<{ email: string, password: string }>

async function verificationCode(request: APIRequestContext, email: string) {
  await expect.poll(async () => {
    const body = await (await request.get(`${mailpitApi}/messages`)).json() as { messages?: Array<{ ID?: string, To?: Array<{ Address?: string }> }> }
    const message = body.messages?.find(item => item.To?.some(recipient => recipient.Address === email))
    if (!message?.ID) return undefined
    const detail = await (await request.get(`${mailpitApi}/message/${message.ID}`)).json() as { Text?: string }
    return detail.Text?.match(/\b(\d{6})\b/)?.[1]
  }).toMatch(/^\d{6}$/)
  const body = await (await request.get(`${mailpitApi}/messages`)).json() as { messages?: Array<{ ID?: string, To?: Array<{ Address?: string }> }> }
  const id = body.messages?.find(item => item.To?.some(recipient => recipient.Address === email))?.ID
  const detail = id ? await (await request.get(`${mailpitApi}/message/${id}`)).json() as { Text?: string } : {}
  return detail.Text!.match(/\b(\d{6})\b/)![1]
}

async function registerAndVerify(page: Page, request: APIRequestContext, account: Account) {
  await page.goto(`${userFrontendUrl}/register`)
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByLabel('确认密码').fill(account.password)
  await page.getByRole('button', { name: '发送验证码' }).click()
  await page.getByLabel('6 位邮箱验证码').fill(await verificationCode(request, account.email))
  await page.getByRole('button', { name: '验证并激活账号' }).click()
}

async function bootstrap(account: Account) {
  await execFile('../backend/.venv/bin/python', ['tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli', 'bootstrap', '--email', account.email, '--reason', 'Recipe candidate E2E bootstrap'], { cwd: '../backend' })
}

async function login(page: Page, account: Account) {
  const probe = page.waitForResponse(response => response.url().endsWith('/api/v1/admin/probe') && response.status() === 200)
  await page.goto('/admin/login?returnTo=/admin/catalog')
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: '登录后台' }).click()
  await probe
}

async function publishFood(page: Page, name: string) {
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '新增营养目录' })
  await dialog.getByLabel('菜品名称').fill(name)
  await dialog.getByLabel('别名').fill(`recipe-${Date.now()}`)
  await dialog.getByLabel('每 100g 能量（kcal）').fill('200')
  await dialog.getByLabel('每 100g 蛋白质（g）').fill('10')
  await dialog.getByLabel('每 100g 脂肪（g）').fill('6')
  await dialog.getByLabel('每 100g 碳水（g）').fill('20')
  await dialog.getByLabel('来源名称').fill('E2E catalog')
  await dialog.getByLabel('来源链接').fill('https://example.test/catalog')
  await dialog.getByLabel('授权状态').selectOption('authorized')
  await dialog.getByLabel('变更原因').fill('为菜谱候选创建合格目录')
  await dialog.getByRole('button', { name: '保存草稿' }).click()
  const row = page.getByRole('row').filter({ hasText: name })
  for (const [action, button] of [['审核', '确认审核草稿'], ['发布', '确认发布版本']] as const) {
    await row.getByRole('button', { name: action, exact: true }).click()
    const lifecycle = page.getByRole('dialog')
    await lifecycle.getByLabel('操作原因').fill(`E2E ${action}目录`)
    await lifecycle.getByRole('button', { name: button }).click()
    await expect(lifecycle).toBeHidden()
  }
}

test('管理员通过真实页面导入并批量启用、停用、删除菜谱候选', async ({ page, request }) => {
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const account = { email: `recipe-admin-${suffix}@example.test`, password: 'Recipe-admin-password-2026!' }
  const foodName = `候选菜目录 ${suffix}`
  await registerAndVerify(page, request, account)
  await bootstrap(account)
  await login(page, account)
  await publishFood(page, foodName)
  await page.getByRole('link', { name: '菜谱管理', exact: true }).click()
  await expect(page.locator('h1', { hasText: '菜谱管理' })).toBeVisible()

  const csv = '关联目录菜品名称,餐次,单份克数,份量说明,做法标签,口味标签,状态\r\n'
    + `${foodName},早餐,300,一份,炒,家常,待审核\r\n${foodName},午餐,300,一份,炒,家常,待审核\r\n${foodName},晚餐,300,一份,炒,家常,待审核\r\n`
  await page.getByRole('button', { name: '导入', exact: true }).click()
  await page.getByLabel('选择 CSV 文件').setInputFiles({ name: 'recipes.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
  await expect(page.getByText('共 3 条，3 条校验通过。')).toBeVisible()
  await page.getByLabel('导入原因').fill('E2E 导入菜谱候选')
  const imported = page.waitForResponse(response => response.url().endsWith('/recipe-candidates/import') && response.status() === 201)
  await page.getByRole('button', { name: '确认导入 3 条' }).click()
  await imported
  await expect(page.getByText('成功导入 3 条菜谱候选。')).toBeVisible()
  await expect(page.getByLabel('每页条数')).toHaveValue('20')
  await expect(page.getByRole('navigation', { name: '菜谱分页' })).toBeVisible()
  await expect(page.getByRole('button', { name: '下一页' })).toBeDisabled()

  await page.getByRole('button', { name: '全选全部（3）' }).click()
  await expect(page.getByText('已选 3 条')).toBeVisible()
  for (const [action, reason, expected] of [['批量启用', 'E2E 启用候选', '已启用 3 条菜谱候选。'], ['批量停用', 'E2E 停用候选', '已停用 3 条菜谱候选。'], ['批量删除', 'E2E 删除候选', '已删除 3 条菜谱候选。']] as const) {
    await page.getByRole('button', { name: action, exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('操作原因').fill(reason)
    const mutation = page.waitForResponse(response => response.url().includes('/api/v1/admin/recipe-candidates/') && response.request().method() === 'POST' && response.status() === 200)
    await dialog.getByRole('button', { name: '确认操作' }).click()
    await mutation
    await expect(page.getByText(expected)).toBeVisible()
    if (action !== '批量删除') await page.getByRole('checkbox', { name: '全选当前页' }).check()
  }
  await expect(page.getByText('暂无菜谱候选')).toBeVisible()
})
