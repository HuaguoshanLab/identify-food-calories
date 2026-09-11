import { execFile as execFileCallback, spawn, type ChildProcess } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { promisify } from 'node:util'

import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const execFile = promisify(execFileCallback)
const mailpitApi = `http://127.0.0.1:${process.env.E2E_ADMIN_MAILPIT_PORT ?? '8026'}/api/v1`
const userFrontendUrl = `http://127.0.0.1:${process.env.E2E_ADMIN_USER_FRONTEND_PORT ?? '5183'}`
const e2eDatabaseUrl = 'postgresql+psycopg://postgres:postgres@127.0.0.1:55433/food_agent_e2e_test'
const e2eCliEnvironment = {
  ...process.env,
  APP_ENV: 'test',
  DATABASE_URL: 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev',
  TEST_DATABASE_URL: e2eDatabaseUrl,
}

type Account = Readonly<{ email: string, password: string }>
type MailpitMessage = Readonly<{ ID?: string, Text?: string, To?: Array<{ Address?: string }> }>

async function messageText(request: APIRequestContext, message: MailpitMessage) {
  if (message.Text) return message.Text
  if (!message.ID) return ''
  const response = await request.get(`${mailpitApi}/message/${message.ID}`)
  if (!response.ok()) return ''
  return ((await response.json()) as MailpitMessage).Text ?? ''
}

async function readVerificationCode(request: APIRequestContext, email: string) {
  async function matchingMessage() {
    const response = await request.get(`${mailpitApi}/messages`)
    const body = await response.json() as { messages?: MailpitMessage[] }
    return body.messages?.find((message) => message.To?.some((recipient) => recipient.Address?.toLowerCase() === email.toLowerCase()))
  }

  await expect.poll(async () => {
    const message = await matchingMessage()
    if (!message) return undefined
    return (await messageText(request, message)).match(/\b(\d{6})\b/)?.[1]
  }, { timeout: 10_000 }).toMatch(/^\d{6}$/)

  const message = await matchingMessage()
  const text = message ? await messageText(request, message) : ''
  const code = text?.match(/\b(\d{6})\b/)?.[1]
  if (!code) throw new Error('Mailpit delivered no verification code')
  return code
}

async function registerAndVerify(page: Page, request: APIRequestContext, account: Account) {
  await page.goto(`${userFrontendUrl}/register`)
  await expect(page.getByRole('heading', { name: '创建账号' })).toBeVisible()
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByLabel('确认密码').fill(account.password)
  await page.getByRole('button', { name: '发送验证码' }).click()
  await expect(page.getByRole('heading', { name: '验证邮箱' })).toBeVisible()
  await page.getByLabel('6 位邮箱验证码').fill(await readVerificationCode(request, account.email))
  await page.getByRole('button', { name: '验证并激活账号' }).click()
  await expect(page).toHaveURL(/\/login$/)
}

async function bootstrapFirstAdmin(account: Account) {
  const result = await execFile('../backend/.venv/bin/python', [
    '-m', 'app.admin.cli',
    'bootstrap', '--email', account.email, '--reason', 'Playwright verified first-admin bootstrap',
  ], { cwd: '../backend', env: e2eCliEnvironment })
  expect(result.stderr).not.toContain(account.password)
  expect(result.stdout).toContain('admin role change recorded:')
}

async function adminUserId(page: Page, email: string) {
  const users = page.waitForResponse((response) => response.url().includes('/api/v1/admin/users') && response.status() === 200)
  await page.getByRole('link', { name: '管理员管理' }).click()
  const body = await (await users).json() as { items: Array<{ id: string, email: string }> }
  const user = body.items.find((item) => item.email === email)
  if (!user) throw new Error('authenticated administrator is missing from the public admin users response')
  return user.id
}

type VectorBuild = Readonly<{ buildId: string, vectorSpaceId: string }>

async function createVectorBuild(actorUserId: string, suffix: string): Promise<VectorBuild> {
  const result = await execFile('../backend/.venv/bin/python', [
    '-m', 'app.admin.cli', 'vector-build', '--actor-user-id', actorUserId,
    '--reason', 'isolated E2E evidence-bound activation preparation',
    '--idempotency-key', `e2e-vector-build-${suffix}`,
  ], { cwd: '../backend', env: e2eCliEnvironment })
  const [buildId, vectorSpaceId] = result.stdout.trim().split(/\s+/)
  if (!buildId || !vectorSpaceId) throw new Error('controlled vector-build CLI returned no build identifiers')
  return { buildId, vectorSpaceId }
}

async function activateVectorBuild(actorUserId: string, build: VectorBuild, suffix: string) {
  return execFile('../backend/.venv/bin/python', [
    '-m', 'evals.phase_06_3.activate', '--actor-user-id', actorUserId,
    '--build-id', build.buildId, '--vector-space-id', build.vectorSpaceId,
    '--reason', 'isolated E2E activation after completion evidence',
    '--idempotency-key', `e2e-vector-activation-${suffix}`,
  ], { cwd: '../backend', env: e2eCliEnvironment })
}

async function startProductWorker(request: APIRequestContext, outcomes: string): Promise<ChildProcess> {
  const child = spawn('../backend/.venv/bin/python', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8005'], {
    cwd: '../backend',
    env: { ...e2eCliEnvironment, EMBEDDING_WORKER_ENABLED: 'true', EMBEDDING_WORKER_POLL_INTERVAL_SECONDS: '1', TEST_EMBEDDING_OUTCOMES: outcomes },
    // Keep the product lifecycle's safe operational logs visible when a local
    // E2E environment fails to start; the worker never logs controlled names.
    stdio: 'inherit',
  })
  await expect.poll(async () => {
    try {
      return (await request.get('http://127.0.0.1:8005/api/v1/health')).status()
    } catch {
      return 0
    }
  }, { timeout: 15_000 }).toBe(200)
  return child
}

async function stopProductWorker(child: ChildProcess) {
  if (child.exitCode !== null) return
  const stopped = new Promise<void>((resolve) => child.once('exit', () => resolve()))
  child.kill('SIGTERM')
  await Promise.race([stopped, new Promise<void>((resolve) => setTimeout(resolve, 10_000))])
  if (child.exitCode === null) child.kill('SIGKILL')
}

async function activateAfterCompletion(actorUserId: string, build: VectorBuild, suffix: string) {
  let latestError: Error | undefined
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      await activateVectorBuild(actorUserId, build, suffix)
      return
    } catch (error) {
      latestError = error instanceof Error ? error : new Error('activation command failed')
      await new Promise((resolve) => setTimeout(resolve, 1_000))
    }
  }
  throw latestError ?? new Error('activation did not observe worker completion evidence')
}

async function loginToAdmin(page: Page, account: Account, returnTo: string) {
  const probe = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/probe')
    && response.status() === 200
    && response.request().headers().authorization?.startsWith('Bearer '))
  await page.goto(`/admin/login?returnTo=${encodeURIComponent(returnTo)}`)
  await page.getByLabel('邮箱').fill(account.email)
  await page.getByLabel('密码', { exact: true }).fill(account.password)
  await page.getByRole('button', { name: '登录后台' }).click()
  await probe
  await expect(page).toHaveURL(new RegExp(`${returnTo.replaceAll('/', '\\/')}$`))
}

async function createRuntimeConfig(page: Page) {
  const configPost = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/runtime-config') && response.request().method() === 'POST' && response.status() === 201)
  await expect(page.getByRole('heading', { name: '尚无运行配置' })).toBeVisible()
  await page.getByRole('button', { name: '变更未来配置' }).click()
  const dialog = page.getByRole('alertdialog', { name: '确认变更未来运行配置？' })
  await expect(dialog.getByRole('button', { name: '取消' })).toBeFocused()
  const enabled = dialog.getByRole('checkbox', { name: '启用新的运行配置' })
  if (!(await enabled.isChecked())) await enabled.check()
  await dialog.getByLabel('单次调用上限（USD）').fill('0.02')
  await dialog.getByLabel('周期上限（USD）').fill('12')
  await dialog.getByLabel('输入价格（USD / 百万 token）').fill('0.14')
  await dialog.getByLabel('输出价格（USD / 百万 token）').fill('0.28')
  await dialog.getByLabel('变更原因').fill('为隔离 E2E 创建首个启用策略')
  await dialog.getByRole('button', { name: '确认保存未来配置' }).click()
  const response = await configPost
  expect(response.request().headers()['if-match']).toBe('0')
  expect(response.request().headers()['idempotency-key']).toBeTruthy()
  await expect(page.getByText('配置版本 v1')).toBeVisible()
}

async function createAndDisqualifyCatalogEntry(page: Page, suffix: string) {
  // Protected routes keep the Bearer token only in React memory, so navigate through the
  // SPA shell rather than using a full browser load that would deliberately clear it.
  await page.getByRole('link', { name: '营养目录' }).click()
  await expect(page).toHaveURL(/\/admin\/catalog$/)
  await expect(page.getByRole('table')).toBeVisible()
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '新增营养目录' })
  await editor.getByLabel('菜品名称').fill(`E2E 燕麦 ${suffix}`)
  await editor.getByLabel('别名').fill(`E2E燕麦${suffix}, e2e-oats-${suffix}`)
  await editor.getByLabel('每 100g 能量（kcal）').fill('389')
  await editor.getByLabel('每 100g 蛋白质（g）').fill('16.9')
  await editor.getByLabel('每 100g 脂肪（g）').fill('6.9')
  await editor.getByLabel('每 100g 碳水（g）').fill('66.3')
  await editor.getByLabel('来源名称').fill('USDA FoodData Central')
  await editor.getByLabel('来源链接').fill('https://fdc.nal.usda.gov/')
  await editor.getByLabel('授权状态').selectOption('authorized')
  await editor.getByLabel('变更原因').fill('E2E 验证目录治理的公开审计链')
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/catalog-drafts') && response.request().method() === 'POST' && response.status() === 201)
  await editor.getByRole('button', { name: '保存草稿' }).click()
  await created

  for (const [button, confirm, reason, responsePath] of [
    ['审核', '确认审核草稿', 'E2E 已完成来源复核', '/review'],
    ['发布', '确认发布版本', 'E2E 已确认发布范围', '/publish'],
  ] as const) {
    await page.getByRole('row').filter({ hasText: `E2E 燕麦 ${suffix}` }).getByRole('button', { name: button, exact: true }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByRole('button', { name: '关闭窗口' })).toBeFocused()
    const bounds = await dialog.boundingBox()
    expect(bounds).toBeTruthy()
    expect(Math.abs(bounds!.x + bounds!.width / 2 - 640)).toBeLessThan(2)
    expect(Math.abs(bounds!.y + bounds!.height / 2 - 450)).toBeLessThan(2)
    await expect(dialog.locator('details')).not.toHaveAttribute('open')
    await dialog.getByLabel('操作原因').fill(reason)
    const mutation = page.waitForResponse((response) => response.url().includes('/api/v1/admin/catalog-drafts') && response.url().endsWith(responsePath) && response.request().method() === 'POST' && response.status() === 200)
    const confirmation = dialog.getByRole('button', { name: confirm })
    await confirmation.scrollIntoViewIfNeeded()
    await expect(confirmation).toBeInViewport()
    await confirmation.click()
    await mutation
    await expect(dialog).toBeHidden()
  }
  await page.getByRole('link', { name: '详情', exact: true }).click()
  await page.getByRole('button', { name: '立即失格', exact: true }).click()
  const disqualify = page.getByRole('alertdialog')
  await disqualify.getByLabel('变更原因').fill('E2E 验证未来使用立即失格')
  await disqualify.getByRole('button', { name: '确认立即失格', exact: true }).click()
  await expect(page.getByText('已立即失格，操作已记录。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '操作审计' })).toBeVisible()
}

async function verifyCatalogCsvAndFilters(page: Page, suffix: string) {
  await page.getByRole('link', { name: '营养目录', exact: true }).click()
  const filename = `CSV 燕麦 ${suffix}`
  const csvText = '\ufeff菜品名称,别名,能量(kcal/100g),蛋白质(g/100g),脂肪(g/100g),碳水(g/100g),来源名称,来源链接,授权状态\r\n'
    + `${filename},csv-oats,389,16.9,6.9,66.3,CSV fixture,https://example.test/,待确认\r\n`
  await page.getByRole('button', { name: '导入', exact: true }).click()
  await page.getByLabel('选择 CSV 文件').setInputFiles({ name: 'catalog.csv', mimeType: 'text/csv', buffer: Buffer.from(csvText) })
  await expect(page.getByText('共 1 条，1 条校验通过。')).toBeVisible()
  await page.getByLabel('导入原因').fill('CSV 表格管理隔离验收')
  const imported = page.waitForResponse((response) => response.url().endsWith('/catalog-drafts/import') && response.status() === 201)
  await page.getByRole('button', { name: '确认导入 1 条' }).click()
  expect((await (await imported).json()).imported_count).toBe(1)
  await expect(page.getByText(/成功导入 1 条草稿/)).toBeVisible()
  await page.getByPlaceholder('搜索名称或别名').fill('csv-oats')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.getByRole('table').getByRole('button', { name: filename, exact: true })).toBeVisible()
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(2)
  const exporting = page.waitForResponse((response) => response.url().includes('/catalog-drafts/export?') && response.status() === 200)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出', exact: true }).click()
  const downloaded = await download
  expect(downloaded.suggestedFilename()).toBe('营养目录.csv')
  const response = await exporting
  expect(new URL(response.url()).searchParams.get('search')).toBe('csv-oats')
  const path = await downloaded.path()
  expect(path).toBeTruthy()
  const csv = await readFile(path!, 'utf-8')
  expect(csv).toContain(filename)
  expect(csv).not.toContain(`E2E 燕麦 ${suffix}`)
  await page.getByPlaceholder('搜索名称或别名').fill('no matching nutrition item')
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.getByText('没有符合条件的目录')).toBeVisible()
  await page.getByRole('button', { name: '重置', exact: true }).click()
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(3)
  await page.getByRole('row').filter({ hasText: filename }).getByRole('button', { name: '编辑', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '编辑营养目录' })
  await editor.getByLabel('菜品名称').fill(`${filename} 更新`)
  await editor.getByLabel('变更原因').fill('CSV 导入后编辑验证')
  await editor.getByRole('button', { name: '保存草稿' }).click()
  await expect(page.getByRole('table').getByRole('button', { name: `${filename} 更新`, exact: true })).toBeVisible()
}

test.describe.configure({ mode: 'serial' })

async function verifyBulkLifecycle(page: Page, suffix: string) {
  const names = [`批量验收甲 ${suffix}`, `批量验收乙 ${suffix}`]
  const csv = '菜品名称,别名,能量(kcal/100g),蛋白质(g/100g),脂肪(g/100g),碳水(g/100g),来源名称,来源链接,授权状态\r\n'
    + names.map((name, i) => `${name},bulk-${suffix}-${i},100,3,2,18,隔离批量验收,https://example.test/,已授权\r\n`).join('')
  await page.getByRole('button', { name: '导入', exact: true }).click()
  await page.getByLabel('选择 CSV 文件').setInputFiles({ name: 'bulk.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) })
  await expect(page.getByText('共 2 条，2 条校验通过。')).toBeVisible()
  await page.getByLabel('导入原因').fill('隔离环境批量审核发布验收')
  await page.getByRole('button', { name: '确认导入 2 条' }).click()
  await expect(page.getByText(/成功导入 2 条草稿/)).toBeVisible()
  await page.getByPlaceholder('搜索名称或别名').fill(`bulk-${suffix}`)
  await page.getByRole('button', { name: '查询', exact: true }).click()
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(3)
  await page.getByRole('button', { name: '全选全部（2）' }).click()
  await expect(page.getByText('已选 2 条')).toBeVisible()
  for (const action of ['审核', '发布']) {
    await page.getByRole('button', { name: `批量${action}`, exact: true }).click()
    const dialog = page.getByRole('dialog', { name: `批量${action}` })
    await expect(dialog.getByRole('button', { name: `确认批量${action}（2）` })).toBeEnabled()
    await dialog.getByLabel('批量操作原因').fill(`批量${action}隔离验收`)
    await dialog.getByRole('button', { name: `确认批量${action}（2）` }).click()
    await expect(dialog.getByRole('status')).toHaveText('成功 2 条 · 跳过/失败 0 条 · 结果未确认 0 条 · 待处理 0 条')
    await expect(dialog.getByText(new RegExp(`${action}成功 · v1 · 已记录审计`))).toHaveCount(2)
    await dialog.getByRole('button', { name: '完成', exact: true }).click()
  }
  await page.getByRole('button', { name: '批量发布', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '批量发布' })
  await expect(dialog.getByText('当前版本已发布，跳过。')).toHaveCount(2)
  await expect(dialog.getByRole('button', { name: '确认批量发布（0）' })).toBeDisabled()
  await dialog.getByRole('button', { name: '取消', exact: true }).click()
}

test('verified first admin uses public RuntimeConfig and catalog lifecycle; ordinary user is denied', async ({ browser, page, request }) => {
  test.setTimeout(180_000)
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const admin = { email: `e2e-admin-${suffix}@example.test`, password: 'E2E-admin-password-2026!' }
  // Verification reads are scoped to this run's unique email; leave other local mail intact.
  await registerAndVerify(page, request, admin)
  await bootstrapFirstAdmin(admin)
  await loginToAdmin(page, admin, '/admin/model-configs')
  await createRuntimeConfig(page)
  await createAndDisqualifyCatalogEntry(page, suffix)
  await verifyCatalogCsvAndFilters(page, suffix)
  await verifyBulkLifecycle(page, suffix)
  // A real reload loses React memory: only the HttpOnly cookie may restore access.
  const restored = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/refresh') && response.status() === 200)
  await page.reload()
  await restored
  await expect(page).toHaveURL(/\/admin\/catalog$/)
  await expect(page.getByRole('table')).toBeVisible()

  const adminRequests: string[] = []
  page.on('request', (requestEvent) => {
    const url = new URL(requestEvent.url())
    if (url.pathname.startsWith('/api/v1/')) adminRequests.push(url.pathname)
  })
  await page.getByRole('link', { name: '概览' }).click()
  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await page.getByRole('link', { name: '运行审计' }).click()
  await expect(page.getByRole('heading', { name: '运行诊断' })).toBeVisible()
  expect(adminRequests).not.toHaveLength(0)
  expect(adminRequests.every((path) => path.startsWith('/api/v1/admin/'))).toBeTruthy()
  await expect(page.locator('body')).not.toContainText(admin.email)
  await expect(page.locator('body')).not.toContainText(/api_key|endpoint|reasoning|provider body/i)

  const ordinaryContext = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const ordinaryPage = await ordinaryContext.newPage()
  const ordinary = { email: `e2e-user-${suffix}@example.test`, password: 'E2E-user-password-2026!' }
  await registerAndVerify(ordinaryPage, request, ordinary)
  await page.getByRole('link', { name: '管理员管理' }).click()
  await page.getByLabel('邮箱').fill(ordinary.email)
  await page.getByRole('button', { name: '查询', exact: true }).click()
  const targetRow = page.getByRole('row').filter({ hasText: ordinary.email })
  await targetRow.getByRole('button', { name: '设为管理员' }).click()
  await page.getByLabel('变更原因').fill('E2E 验证管理员角色治理')
  await page.getByRole('button', { name: '确认变更角色' }).click()
  await expect(page.getByRole('status')).toContainText('操作已记录')

  const rolesRead = ordinaryPage.waitForResponse((response) => response.url().endsWith('/api/v1/admin/roles') && response.status() === 200)
  await loginToAdmin(ordinaryPage, ordinary, '/admin/roles')
  const ordinaryAdminToken = (await rolesRead).request().headers().authorization
  expect(ordinaryAdminToken).toMatch(/^Bearer /)
  await expect(ordinaryPage.getByRole('heading', { name: '角色管理' })).toBeVisible()

  await targetRow.getByRole('button', { name: '撤销管理员' }).click()
  await page.getByLabel('变更原因').fill('E2E 验证降权保留普通用户会话')
  await page.getByRole('button', { name: '确认变更角色' }).click()
  await expect(page.getByRole('status')).toContainText('更新为 user')
  const demotedStatus = await ordinaryPage.evaluate(async (authorization) => {
    const response = await fetch('/api/v1/admin/runs', { headers: { Authorization: authorization } })
    return response.status
  }, ordinaryAdminToken as string)
  expect(demotedStatus).toBe(403)
  await ordinaryContext.close()
  await page.getByRole('button', { name: '打开会话菜单' }).click()
  const revoked = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/logout') && response.ok())
  await page.getByRole('menuitem', { name: '退出登录' }).click()
  await revoked
  await page.reload()
  await expect(page.getByRole('heading', { name: '后台登录' })).toBeVisible()
  await expect(page.getByTestId('admin-shell')).toHaveCount(0)
})

async function publishMultiNameCatalogEntry(page: Page, suffix: string) {
  const name = `E2E 索引验收 ${suffix}`
  await page.getByRole('link', { name: '营养目录', exact: true }).click()
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '新增营养目录' })
  await editor.getByLabel('菜品名称').fill(name)
  await editor.getByLabel('别名').fill(`index-${suffix}`)
  await editor.getByLabel('每 100g 能量（kcal）').fill('100')
  await editor.getByLabel('每 100g 蛋白质（g）').fill('3')
  await editor.getByLabel('每 100g 脂肪（g）').fill('2')
  await editor.getByLabel('每 100g 碳水（g）').fill('18')
  await editor.getByLabel('来源名称').fill('E2E controlled source')
  await editor.getByLabel('来源链接').fill('https://example.test/e2e-index')
  await editor.getByLabel('授权状态').selectOption('authorized')
  await editor.getByLabel('变更原因').fill('公开 UI 创建多名称索引验收条目')
  const created = page.waitForResponse((response) => response.url().endsWith('/api/v1/admin/catalog-drafts') && response.request().method() === 'POST' && response.status() === 201)
  await editor.getByRole('button', { name: '保存草稿' }).click()
  const draft = await (await created).json() as { id: string }

  for (const [action, confirm, path] of [['审核', '确认审核草稿', '/review'], ['发布', '确认发布版本', '/publish']] as const) {
    await page.getByRole('row').filter({ hasText: name }).getByRole('button', { name: action, exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('操作原因').fill(`公开 UI ${action} 索引验收条目`)
    const mutation = page.waitForResponse((response) => response.url().includes('/api/v1/admin/catalog-drafts') && response.url().endsWith(path) && response.request().method() === 'POST' && response.status() === 200)
    await dialog.getByRole('button', { name: confirm }).click()
    await mutation
  }
  // The catalog's SPA-level detail link retains the runtime-only access token.
  // A row-local anchor performs a full navigation and would deliberately clear it.
  await page.getByRole('link', { name: '详情', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/admin/catalog/${draft.id}`))
  return draft.id
}

async function waitForVisibleEmbeddingStatus(page: Page, label: '部分失败' | '已就绪') {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (await page.getByRole('region', { name: '嵌入构建状态' }).getByText(label, { exact: false }).count()) return
    await page.getByRole('button', { name: '刷新嵌入构建状态' }).click()
    await page.waitForTimeout(1_000)
  }
  await expect(page.getByRole('region', { name: '嵌入构建状态' })).toContainText(label)
}

async function changeRole(page: Page, email: string, action: '设为管理员' | '撤销管理员') {
  await page.getByRole('link', { name: '管理员管理' }).click()
  await page.getByLabel('邮箱').fill(email)
  await page.getByRole('button', { name: '查询', exact: true }).click()
  const row = page.getByRole('row').filter({ hasText: email })
  await row.getByRole('button', { name: action }).click()
  await page.getByLabel('变更原因').fill(`E2E ${action} 验证实时目录索引 RBAC`)
  await page.getByRole('button', { name: '确认变更角色' }).click()
  await expect(page.getByRole('status')).toBeVisible()
}

test('admin embedding status and batch retry', async ({ browser, page, request }) => {
  test.setTimeout(180_000)
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const admin = { email: `e2e-index-admin-${suffix}@example.test`, password: 'E2E-index-admin-password-2026!' }
  await registerAndVerify(page, request, admin)
  await bootstrapFirstAdmin(admin)
  await loginToAdmin(page, admin, '/admin/catalog')
  const actorUserId = await adminUserId(page, admin.email)
  await page.getByRole('link', { name: '营养目录', exact: true }).click()
  // Stage 1: real product worker, then durable evidence-bound activation.
  const build = await createVectorBuild(actorUserId, suffix)
  const activationWorker = await startProductWorker(request, Array(128).fill('success').join(','))
  try {
    await activateAfterCompletion(actorUserId, build, suffix)
  } finally {
    await stopProductWorker(activationWorker)
  }
  // Stage 2: restart the same worker with the closed partial-failure script.
  const publicationWorker = await startProductWorker(request, 'success,permanent_failure,success')
  try {
  const draftId = await publishMultiNameCatalogEntry(page, suffix)
  await waitForVisibleEmbeddingStatus(page, '部分失败')

  const status = page.getByRole('region', { name: '嵌入构建状态' })
  await expect(status).toContainText('失败 1')
  await expect(status.getByRole('row')).toHaveCount(3)

  const ordinaryGet = { email: `e2e-index-get-${suffix}@example.test`, password: 'E2E-index-user-password-2026!' }
  const ordinaryPost = { email: `e2e-index-post-${suffix}@example.test`, password: 'E2E-index-user-password-2026!' }
  const getContext = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const postContext = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const getPage = await getContext.newPage()
  const postPage = await postContext.newPage()
  await registerAndVerify(getPage, request, ordinaryGet)
  await registerAndVerify(postPage, request, ordinaryPost)
  await changeRole(page, ordinaryGet.email, '设为管理员')
  await changeRole(page, ordinaryPost.email, '设为管理员')
  await loginToAdmin(getPage, ordinaryGet, '/admin/catalog')
  await loginToAdmin(postPage, ordinaryPost, '/admin/catalog')
  await getPage.getByRole('link', { name: '详情', exact: true }).click()
  await postPage.getByRole('link', { name: '详情', exact: true }).click()
  await expect(getPage.getByRole('region', { name: '嵌入构建状态' })).toBeVisible()
  await expect(postPage.getByRole('region', { name: '嵌入构建状态' })).toBeVisible()

  await changeRole(page, ordinaryGet.email, '撤销管理员')
  await changeRole(page, ordinaryPost.email, '撤销管理员')
  const deniedGet = getPage.waitForResponse((response) => response.url().includes('/embedding-status') && response.status() === 403)
  await getPage.getByRole('button', { name: '刷新嵌入构建状态' }).click()
  await deniedGet
  await expect(getPage.getByRole('heading', { name: '无后台访问权限' })).toBeVisible()
  const deniedPost = postPage.waitForResponse((response) => response.url().includes('/embedding-retries') && response.request().method() === 'POST' && response.status() === 403)
  await postPage.getByRole('button', { name: '重试 1 个可恢复任务' }).click()
  const forbiddenDialog = postPage.getByRole('alertdialog', { name: '重新排队可恢复的嵌入任务？' })
  await forbiddenDialog.getByLabel('变更原因').fill('普通用户不可重试')
  await forbiddenDialog.getByRole('button', { name: '确认重新排队' }).click()
  await deniedPost
  await expect(postPage.getByRole('heading', { name: '无后台访问权限' })).toBeVisible()
  await getContext.close()
  await postContext.close()

  // Role changes deliberately navigate the original administrator session to
  // user management. Return through the SPA before exercising the visible
  // retry control; otherwise this test is no longer operating the catalog UI.
  await page.getByRole('link', { name: '营养目录', exact: true }).click()
  await page.getByRole('link', { name: '详情', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/admin/catalog/${draftId}`))
  await expect(status).toBeVisible()

  const retry = page.waitForResponse((response) => response.url().includes('/embedding-retries') && response.request().method() === 'POST' && response.status() === 200)
  await page.getByRole('button', { name: '重试 1 个可恢复任务' }).click()
  const dialog = page.getByRole('alertdialog', { name: '重新排队可恢复的嵌入任务？' })
  await dialog.getByLabel('变更原因').fill('公开页面确认失败任务重新排队')
  await dialog.getByRole('button', { name: '确认重新排队' }).click()
  expect((await (await retry).json()) as { reset_count: number }).toMatchObject({ reset_count: 1 })
  await waitForVisibleEmbeddingStatus(page, '已就绪')
  await expect(status).toContainText('完成 2')
  await expect(status.getByRole('row')).toHaveCount(3)
  // Repeating the visible status action proves the completed retry did not add jobs.
  await page.getByRole('button', { name: '刷新嵌入构建状态' }).click()
  await expect(status).toContainText('完成 2')
  await expect(status.getByRole('row')).toHaveCount(3)
  } finally {
    await stopProductWorker(publicationWorker)
  }
})
