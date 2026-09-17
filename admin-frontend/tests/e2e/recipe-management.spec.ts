import { expect, test, type Page } from '@playwright/test'
import { bootstrapFirstAdmin, registerAndVerify, type Account } from './auth-helpers'

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

test('管理员导入、分类、审计和候选生命周期', async ({ page, request }) => {
  test.setTimeout(90_000)
  const suffix = `${Date.now()}-${Math.floor(Math.random() * 10_000)}`
  const account = { email: `recipe-admin-${suffix}@example.test`, password: 'Recipe-admin-password-2026!' }
  const foodName = `白米饭 ${suffix}`
  await registerAndVerify(page, request, account)
  await bootstrapFirstAdmin(account)
  await login(page, account)
  await publishFood(page, foodName)
  await page.getByRole('link', { name: '菜谱管理', exact: true }).click()
  await expect(page.getByRole('heading', { name: '菜谱管理', exact: true })).toBeVisible()

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
  await page.getByRole('button', { name: '补齐三维分类', exact: true }).click()
  await expect(page.getByText(/待补齐 3 条/)).toBeVisible()
  await page.getByLabel('修改原因').fill('E2E 补齐三维分类')
  await page.getByRole('button', { name: '保存分类', exact: true }).click()
  await expect(page.getByText(/已补齐 3 条菜谱的三维分类/)).toBeVisible()
  await page.reload()
  await expect(page.getByRole('cell', { name: '米及制品', exact: true })).toHaveCount(3)
  await page.getByRole('button', { name: '全选全部（3）' }).click()
  await page.getByRole('button', { name: '补齐三维分类', exact: true }).click()
  await expect(page.getByText(/待补齐 0 条，已分类跳过 3 条/)).toBeVisible()
  await expect(page.getByRole('button', { name: '保存分类', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '取消', exact: true }).click()
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

  await page.getByRole('button', { name: '导入', exact: true }).click()
  const roleCsv = '关联目录菜品名称,餐次,单份克数,份量说明,做法标签,口味标签,状态,配餐用途,餐内角色,食材标签,分类依据\n'
    + `${foodName},午餐,100,一份,蒸,清淡,待审核,组合组成项,主食,米及制品,测试目录白米饭\n`
  await page.getByLabel('选择 CSV 文件').setInputFiles({ name: 'classification.csv', mimeType: 'text/csv', buffer: Buffer.from(roleCsv) })
  await expect(page.getByRole('cell', { name: '主食', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: '米及制品', exact: true })).toBeVisible()
  await page.getByLabel('导入原因').fill('核对三维分类')
  await page.getByRole('button', { name: '确认导入 1 条' }).click()
  await expect(page.getByText('成功导入 1 条菜谱候选。')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('cell', { name: '主食', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: '旧配餐角色', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '设置旧角色（不参与配餐）' })).toHaveCount(0)
  await page.getByRole('button', { name: `编辑 ${foodName} 分类`, exact: true }).click()
  await page.getByLabel('配餐用途', { exact: true }).selectOption('component')
  await page.getByLabel('餐内角色', { exact: true }).selectOption('staple')
  await page.getByLabel('米及制品', { exact: true }).check()
  await page.getByLabel('分类依据').fill('测试目录明确为白米饭')
  await page.getByLabel('修改原因').fill('E2E 人工复核三维分类')
  await page.getByRole('button', { name: '保存修改', exact: true }).click()
  await expect(page.getByText('分类已更新，将用于新配餐。')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('cell', { name: '主食', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: '米及制品', exact: true })).toBeVisible()
  await page.getByRole('link', { name: '操作审计', exact: true }).click()
  await expect(page.getByRole('cell', { name: '补齐菜谱三维分类', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('cell', { name: 'E2E 人工复核三维分类', exact: true }).first()).toBeVisible()
  console.log(`Native verification account: ${account.email}`)
})
