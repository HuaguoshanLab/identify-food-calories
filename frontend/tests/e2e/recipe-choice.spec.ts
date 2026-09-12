import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { randomUUID } from 'node:crypto'
import { expect, test } from '@playwright/test'
import { clearMailbox, login, registerAndActivate } from './auth-helpers'

test('specific recipe confirmation survives reload and rejects an administratively disabled choice', async ({ page, request }) => {
  test.setTimeout(90_000)
  const account = { email: 'recipe-choice-check@example.test', password: 'Recipe-choice-check-2026!' }
  await clearMailbox(request)
  await page.goto('/register')
  await registerAndActivate(page, request, account)
  // This exact account is authorized only for the guarded local test database.
  await promisify(execFile)('.venv/bin/python', ['tests/run_pg.py', '--env-file', '.env.test.example', '--', '.venv/bin/python', '-m', 'app.admin.cli', 'bootstrap', '--email', account.email, '--reason', 'Isolated recipe-choice regression fixture'], { cwd: '../backend' })
  const api = `http://127.0.0.1:${process.env.E2E_BACKEND_PORT ?? '8000'}/api/v1`
  const signedIn = await request.post(`${api}/auth/login`, { data: account })
  expect(signedIn.ok()).toBeTruthy()
  const { access_token: token } = await signedIn.json()
  async function post(path: string, data: unknown, revision?: number) {
    const response = await request.post(`${api}${path}`, { data, headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': randomUUID(), ...(revision === undefined ? {} : { 'If-Match': String(revision) }) } })
    expect(response.ok(), `${path}: ${await response.text()}`).toBeTruthy()
    return response.json()
  }
  const reason = { reason: '隔离菜谱回归合成数据', confirm: true }
  await post('/admin/runtime-config', { ...reason, provider: 'deepseek', model_alias: 'deepseek-v4-flash', enabled: true, single_call_cap_usd: '0.02', period_cap_usd: '12', input_usd_per_m: '0.14', output_usd_per_m: '0.28' }, 0)
  const names = ['验收早餐拼盘', '验收午餐拼盘', '验收晚餐拼盘', '验收清蒸鱼']
  for (const name of names) {
    const draft = await post('/admin/catalog-drafts', { canonical_name: name, aliases: [`${name}别名`], energy_kcal_per_100g: '100', protein_g_per_100g: '5', fat_g_per_100g: '3.333333', carbohydrate_g_per_100g: '12.5', source_name: '隔离合成数据', source_url: 'https://example.test/recipe-choice', authorization_status: 'authorized', reason: reason.reason })
    await post(`/admin/catalog-drafts/${draft.id}/review`, reason, draft.revision)
    await post(`/admin/catalog-drafts/${draft.id}/publish`, reason, draft.revision)
  }
  async function recipe(name: string, slot: string, grams: number, description: string) {
    const result = await post('/admin/recipe-candidates/import', { ...reason, csv_text: `关联目录菜品名称,餐次,单份克数,份量说明,做法标签,口味标签,状态\n${name},${slot},${grams},${description},蒸,清淡,待审核\n` })
    await post('/admin/recipe-candidates/enable', { ...reason, ids: result.candidate_ids })
    return result.candidate_ids
  }
  for (const [index, slot] of ['早餐', '午餐', '晚餐'].entries()) await recipe(names[index], slot, 650, '标准一份')
  await post('/meal-records/dashboard-time-zone-confirmations', { time_zone: 'Asia/Shanghai' })
  await post('/agent/threads/diet-planning', { profile: { height_cm: '170', weight_kg: '65', age_years: 30, formula_variant: 'mifflin_st_jeor_female', activity_level: 'moderate', goal: 'loss', goal_speed: 'gradual_loss' }, preferences: { confirmed: true, exclusions: [], taste_preferences: [] }, save_profile: false })
  const small = await recipe(names[3], '午餐', 600, '小份清蒸')
  await recipe(names[3], '午餐', 650, '大份清蒸')
  await login(page, account, '/app/plans')
  const breakfast = page.getByRole('region', { name: '早餐', exact: true })
  const dinner = page.getByRole('region', { name: '晚餐', exact: true })
  const originalBreakfast = await breakfast.innerText()
  const originalDinner = await dinner.innerText()
  await page.getByLabel('告诉我们想换什么').fill('午餐换成验收清蒸鱼')
  await page.getByRole('button', { name: '提交调整', exact: true }).click()
  const submit = page.getByRole('button', { name: '确认菜谱并替换' })
  await expect(page.getByRole('radio')).toHaveCount(2)
  await expect(page.locator('input[type=radio]:checked')).toHaveCount(0)
  await expect(submit).toBeDisabled()
  await expect(page.getByLabel('告诉我们想换什么')).toBeDisabled()
  await page.reload()
  if (page.url().includes('/login')) await login(page, account, '/app/plans')
  await expect(page.getByRole('radio')).toHaveCount(2)
  await page.getByRole('radio', { name: /小份清蒸/ }).check()
  await post('/admin/recipe-candidates/disable', { ...reason, ids: small })
  await submit.click()
  await expect(page.getByRole('radio')).toHaveCount(1)
  await expect(submit).toBeDisabled()
  await expect(page.getByText(/已自动保存.*第\s*1\s*版/)).toBeVisible()
  await page.getByRole('radio', { name: /大份清蒸/ }).check()
  await submit.click()
  await expect(page.getByText(/已自动保存.*第\s*2\s*版/)).toBeVisible()
  await expect(page.getByRole('region', { name: '午餐', exact: true })).toContainText('验收清蒸鱼')
  await expect(breakfast).toHaveText(originalBreakfast, { useInnerText: true })
  await expect(dinner).toHaveText(originalDinner, { useInnerText: true })
})
