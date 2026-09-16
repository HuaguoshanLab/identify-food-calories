import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { randomUUID } from 'node:crypto'
import { expect, test, type Page } from '@playwright/test'
import { login, registerAndActivate } from './auth-helpers'

function card(page: Page, slot: string) {
  return page.getByRole('heading', { name: slot, exact: true }).locator('xpath=ancestor::*[@data-slot="card"][1]')
}

test('分类菜品组合成餐，换餐保留其他明细，失格后历史仍可读', async ({ page, request }) => {
  test.setTimeout(120_000)
  const account = { email: 'meal-bundles@example.test', password: 'Meal-bundles-check-2026!' }
  await page.goto('/register')
  await registerAndActivate(page, request, account)
  await promisify(execFile)('.venv/bin/python', ['tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli', 'bootstrap', '--email', account.email, '--reason', 'Isolated bundle regression fixture'], { cwd: '../backend' })
  const api = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT ?? '8000'}/api/v1`
  const signedIn = await request.post(`${api}/auth/login`, { data: account })
  expect(signedIn.ok()).toBeTruthy()
  const { access_token: token } = await signedIn.json()
  async function post(path: string, data: unknown, revision?: number) {
    const response = await request.post(`${api}${path}`, { data, headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': randomUUID(), ...(revision === undefined ? {} : { 'If-Match': String(revision) }) } })
    expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy()
    return response.json()
  }
  const reason = { reason: '隔离组合餐测试数据', confirm: true }
  await post('/admin/runtime-config', { ...reason, provider: 'deepseek', model_alias: 'deepseek-v4-flash', enabled: true, single_call_cap_usd: '0.02', period_cap_usd: '12', input_usd_per_m: '0.14', output_usd_per_m: '0.28' }, 0)
  const foods = [
    { name: '测试早餐', role: '单独候选', grams: 100, nutrients: ['400', '20', '15', '60'] },
    { name: '测试米饭', role: '主食', grams: 280, nutrients: ['150', '3', '1', '32'] },
    { name: '测试鸡胸肉', role: '蛋白质菜', grams: 100, nutrients: ['180', '25', '8', '2'] },
    { name: '测试鱼肉', role: '蛋白质菜', grams: 100, nutrients: ['180', '25', '8', '2'] },
    { name: '测试青菜', role: '蔬菜', grams: 150, nutrients: ['40', '2', '1', '6'] },
  ]
  const vegetableIds: string[] = []
  for (const food of foods) {
    const [energy, protein, fat, carbs] = food.nutrients
    const draft = await post('/admin/catalog-drafts', { canonical_name: food.name, aliases: [food.name], energy_kcal_per_100g: energy, protein_g_per_100g: protein, fat_g_per_100g: fat, carbohydrate_g_per_100g: carbs, source_name: '隔离合成数据', source_url: 'https://example.test/meal-bundles', authorization_status: 'authorized', reason: reason.reason })
    await post(`/admin/catalog-drafts/${draft.id}/review`, reason, draft.revision)
    await post(`/admin/catalog-drafts/${draft.id}/publish`, reason, draft.revision)
    const slots = food.role === '单独候选' ? ['早餐'] : ['午餐', '晚餐']
    const imported = await post('/admin/recipe-candidates/import', { ...reason, csv_text: '关联目录菜品名称,餐次,单份克数,份量说明,做法标签,口味标签,状态,餐内角色\n' + slots.map(slot => `${food.name},${slot},${food.grams},一份,蒸,清淡,待审核,${food.role}\n`).join('') })
    await post('/admin/recipe-candidates/enable', { ...reason, ids: imported.candidate_ids })
    if (food.role === '蔬菜') vegetableIds.push(...imported.candidate_ids)
  }
  await login(page, account, '/app/plans')
  await page.getByRole('button', { name: '确认时区' }).click()
  await page.getByRole('link', { name: '去填写', exact: true }).click()
  await page.getByRole('button', { name: '填写身体资料与目标' }).click()
  await page.getByLabel('身高').fill('160')
  await page.getByRole('spinbutton', { name: '体重' }).fill('50')
  await page.getByLabel('年龄').fill('28')
  await page.getByLabel('使用女性参数').check()
  await page.getByLabel('日常活动水平').selectOption('sedentary')
  await page.getByLabel('目标', { exact: true }).selectOption('maintain')
  await page.getByLabel('目标速度').selectOption('maintain')
  await page.getByRole('button', { name: '保存个人资料' }).click()
  await expect(page.getByRole('button', { name: '编辑个人资料' })).toBeVisible()
  await page.goto('/app/plans')
  await page.getByLabel('我已复核以上饮食偏好').check()
  await page.getByRole('button', { name: '生成今日餐单' }).click()
  await expect(page.getByText(/已自动保存.*第 1 版/)).toBeVisible()
  await expect(page.getByText('全部指标在目标范围内', { exact: true })).toBeVisible()
  const lunch = card(page, '午餐')
  await expect(lunch).toContainText('主食')
  await expect(lunch).toContainText('蛋白质菜')
  await expect(lunch).toContainText('测试青菜')
  const saved = await request.get(`${api}/planning/plans/today`, { headers: { Authorization: `Bearer ${token}` } })
  expect(saved.ok()).toBeTruthy()
  type Item = { display_name: string; portion_grams: string; nutrients: Record<string, string> }
  const { plan } = await saved.json() as { plan: { report: { meals: (Item & { items: Item[] })[] } } }
  let adapted = false
  for (const meal of plan.report.meals.filter(meal => meal.items.length)) {
    for (const item of meal.items) {
      const source = foods.find(food => food.name === item.display_name)!
      const grams = Number(item.portion_grams)
      expect(Number.isInteger(grams)).toBeTruthy()
      expect(grams).toBeGreaterThanOrEqual(source.grams * 0.75)
      expect(grams).toBeLessThanOrEqual(source.grams * 1.25)
      adapted ||= grams !== source.grams
      for (const [index, metric] of ['energy_kcal', 'protein_g', 'fat_g', 'carbohydrate_g'].entries()) {
        expect(Number(item.nutrients[metric])).toBeCloseTo(Number(source.nutrients[index]) * grams / 100, 2)
      }
    }
    for (const metric of ['energy_kcal', 'protein_g', 'fat_g', 'carbohydrate_g']) {
      expect(Number(meal.nutrients[metric])).toBeCloseTo(meal.items.reduce((sum, item) => sum + Number(item.nutrients[metric]), 0), 2)
    }
  }
  expect(adapted).toBeTruthy()
  const breakfast = await card(page, '早餐').innerText()
  const dinner = await card(page, '晚餐').innerText()
  const originalLunch = await lunch.innerText()
  await page.reload()
  await expect(lunch).toHaveText(originalLunch, { useInnerText: true })
  await page.getByLabel('告诉我们想换什么').fill('午餐换清淡一些')
  await page.getByRole('button', { name: '提交调整', exact: true }).click()
  await expect(page.getByText(/已自动保存.*第 2 版/)).toBeVisible()
  await expect(lunch).toContainText('已调整')
  expect(await card(page, '早餐').innerText()).toBe(breakfast)
  expect(await card(page, '晚餐').innerText()).toBe(dinner)
  const changedLunch = await lunch.innerText()
  await page.getByLabel('告诉我们想换什么').fill('午餐换清淡一些')
  await page.getByRole('button', { name: '提交调整', exact: true }).click()
  await expect(page.getByText(/已自动保存.*第 3 版/)).toBeVisible()
  expect(await lunch.innerText()).not.toBe(changedLunch)
  expect(await card(page, '早餐').innerText()).toBe(breakfast)
  expect(await card(page, '晚餐').innerText()).toBe(dinner)
  const latestLunch = await lunch.innerText()
  await page.getByRole('link', { name: '历史计划', exact: true }).click()
  await page.getByRole('link', { name: /三餐计划/ }).click()
  await expect(lunch).toContainText('测试青菜')
  await expect(lunch).toContainText(latestLunch.match(/合计 [\d,]+ kcal/)![0])
  const archivedLunch = await lunch.innerText()
  await post('/admin/recipe-candidates/disable', { ...reason, ids: vegetableIds })
  await page.reload()
  await expect(lunch).toHaveText(archivedLunch, { useInnerText: true })
  await page.goto('/app/plans')
  await page.getByRole('button', { name: '重新生成今日计划' }).click()
  await page.getByLabel('我已复核以上饮食偏好').check()
  await page.getByRole('button', { name: '生成今日餐单' }).click()
  await expect(page.getByRole('alert')).toContainText('没有满足当前要求的可用候选')
  await page.getByRole('button', { name: '取消重新生成' }).click()
  await expect(page.getByText(/已自动保存.*第 3 版/)).toBeVisible()
  await post('/admin/recipe-candidates/enable', { ...reason, ids: vegetableIds })
})
