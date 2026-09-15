import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { PlanPage } from './PlanPage'

const profile = {
  height_cm: '170.00', weight_kg: '65.00', age_years: 30,
  formula_variant: 'mifflin_st_jeor_female', activity_level: 'moderate', goal: 'maintain', goal_speed: 'maintain',
  target_policy_version: 'target-policy.v1', formula_version: 'mifflin-st-jeor.v1',
}

const report = {
  stage: 'complete',
  target: {
    energy_kcal: { lower: '1800', upper: '2000' }, carbohydrate_g: { lower: '200', upper: '250' },
    protein_g: { lower: '80', upper: '100' }, fat_g: { lower: '50', upper: '70' },
  },
  meals: [
    { slot: 'breakfast', display_name: '燕麦鸡蛋早餐', portion_description: '一份', portion_grams: '320', method_tags: ['蒸煮'], flavour_tags: ['清淡'], matched_preference_summaries: ['偏好：清淡'], matched_exclusion_summaries: ['不吃花生'], nutrients: { energy_kcal: '560', carbohydrate_g: '62', protein_g: '28', fat_g: '18' } },
    { slot: 'lunch', display_name: '鸡胸肉米饭午餐', portion_description: '一份', portion_grams: '480', method_tags: ['清炒'], flavour_tags: ['少油'], matched_preference_summaries: ['偏好：清淡'], matched_exclusion_summaries: ['不吃花生'], nutrients: { energy_kcal: '720', carbohydrate_g: '78', protein_g: '42', fat_g: '20' } },
    { slot: 'dinner', display_name: '三文鱼蔬菜晚餐', portion_description: '一份', portion_grams: '420', method_tags: ['烤制'], flavour_tags: ['清淡'], matched_preference_summaries: ['偏好：清淡'], matched_exclusion_summaries: ['不吃花生'], nutrients: { energy_kcal: '640', carbohydrate_g: '70', protein_g: '30', fat_g: '22' } },
  ],
  disclaimer: '普通饮食参考，不替代医疗建议。',
}

const adjustedReport = {
  ...report,
  meals: [
    report.meals[0],
    { ...report.meals[1], display_name: '清淡豆腐菌菇午餐', portion_description: '一份', portion_grams: '450', flavour_tags: ['清淡'], nutrients: { energy_kcal: '680', carbohydrate_g: '72', protein_g: '38', fat_g: '18' } },
    report.meals[2],
  ],
  adjustment: {
    changed_slots: ['lunch'],
    matched_constraint: '清淡',
    range_status: { energy_kcal: 'in_range', carbohydrate_g: 'in_range', protein_g: 'in_range', fat_g: 'in_range' },
  },
}

function renderPage(request: AuthContextValue['request']) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}>
          <PlanPage />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function requestWithSnapshot() {
  return vi.fn(async (path: string, init?: RequestInit) => {
    void init
    if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
    if (path === '/planning/profile') return new Response(JSON.stringify(profile))
    if (path === '/memories') return new Response(JSON.stringify([
      { id: '11111111-1111-4111-8111-111111111111', category: 'avoidance', source_kind: 'user_maintained', canonical_text: '花生', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
      { id: '22222222-2222-4222-8222-222222222222', category: 'stable_preference', source_kind: 'user_maintained', canonical_text: '清淡', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
    ]))
    if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed', revision: 1, report }))
    if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed', revision: 1, report }))
    if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
    return new Response('', { status: 500 })
  })
}

describe('PlanPage', () => {
  it('accepts sequenced progress during regeneration and reconciles the final snapshot', async () => {
    const user = userEvent.setup()
    const fallback = requestWithSnapshot()
    const threadId = '33333333-3333-4333-8333-333333333333'
    let finished = false
    let streamController: ReadableStreamDefaultController<Uint8Array> | undefined
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === `/agent/threads/${threadId}`) return Response.json({
        thread_id: threadId, status: finished ? 'completed' : 'partial', revision: 1,
        report: finished ? report : null,
      })
      if (path.endsWith('/events')) return new Response(new ReadableStream<Uint8Array>({
        start(controller) { streamController = controller },
      }), { headers: { 'Content-Type': 'text/event-stream' } })
      return fallback(path, init)
    })
    renderPage(request)
    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    await waitFor(() => expect(streamController).toBeDefined())
    streamController!.enqueue(new TextEncoder().encode('id: 1\ndata: {"schema_version":"safe-stream-stage.v1","stage":"validation","message":"正在校验"}\n\n'))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('正在校验营养与已确认约束'))
    expect(screen.queryByText('请确认信息后再发起一次。')).not.toBeInTheDocument()
    finished = true
    streamController!.enqueue(new TextEncoder().encode('id: 2\ndata: {"schema_version":"safe-stream-stage.v1","stage":"completed","message":"已完成"}\n\n'))
    streamController!.close()
    expect(await screen.findByText('燕麦鸡蛋早餐')).toBeInTheDocument()
  })

  it('keeps the specific terminal report after replaying earlier stages', async () => {
    const user = userEvent.setup()
    const fallback = requestWithSnapshot()
    const message = '没有满足目录资格和三餐槽位的已启用候选菜。'
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return Response.json({
        thread_id: '33333333-3333-4333-8333-333333333333', status: 'terminal', revision: 1,
        report: { stage: 'needs_input', message },
      })
      if (path.endsWith('/events')) return new Response('id: 1\ndata: {"schema_version":"safe-stream-stage.v1","stage":"perception","message":"读取资料"}\n\nid: 2\ndata: {"schema_version":"safe-stream-stage.v1","stage":"terminal","message":"未完成"}\n\n')
      return fallback(path, init)
    })
    renderPage(request)
    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    await waitFor(() => expect(request.mock.calls.filter(([path]) => path === '/agent/threads/33333333-3333-4333-8333-333333333333')).toHaveLength(2))
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(screen.queryByText('请确认信息后再发起一次。')).not.toBeInTheDocument()
  })

  it('owns read-only profile and memory queries, passes their displayed values into the form, and never writes while pre-filling', async () => {
    const request = requestWithSnapshot()
    renderPage(request)

    expect(await screen.findByText('170 cm')).toBeInTheDocument()
    expect(screen.getByText('忌口：已确认 花生')).toBeInTheDocument()
    expect(screen.getByText('口味：已确认 清淡')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '管理饮食偏好' })).toHaveAttribute('href', '/app/me/memories')
    expect(request.mock.calls.filter(([path, init]) => path === '/planning/profile' && init?.method && init.method !== 'GET')).toHaveLength(0)
    expect(request.mock.calls.filter(([path, init]) => path === '/memories' && init?.method && init.method !== 'GET')).toHaveLength(0)
  })

  it('only sends displayed and confirmed values after submit, then renders the controlled three-meal snapshot in order', async () => {
    const user = userEvent.setup()
    const request = requestWithSnapshot()
    renderPage(request)

    await screen.findByText('忌口：已确认 花生')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))

    await screen.findByRole('heading', { name: '今日饮食计划' })
    const start = request.mock.calls.find(([path]) => path === '/agent/threads/diet-planning')
    expect(JSON.parse(String(start?.[1]?.body))).toMatchObject({
      profile: { height_cm: '170', weight_kg: '65', age_years: 30 },
      preferences: { confirmed: true, exclusions: ['花生'], taste_preferences: ['清淡'] }, save_profile: false,
    })
    expect(screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)).toEqual(['早餐', '午餐', '晚餐'])
    expect(screen.getByText('燕麦鸡蛋早餐')).toBeInTheDocument()
    expect(screen.getByText('320g · 一份')).toBeInTheDocument()
    expect(screen.getByText('蒸煮')).toBeInTheDocument()
    expect(screen.getAllByText('清淡')).not.toHaveLength(0)
    expect(screen.queryByText(/已遵守：/)).not.toBeInTheDocument()
    expect(screen.getByText('（目标 1,800–2,000 kcal）')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /计划总热量 1,920 kcal；营养素估算供能占比/ })).toBeInTheDocument()
    expect(screen.getByText('100.0g')).toBeInTheDocument()
    expect(screen.getByText('（80–100g）')).toBeInTheDocument()
    expect(screen.queryByText('查看目标范围与计划值')).not.toBeInTheDocument()
    expect(screen.queryByText('计划进度')).not.toBeInTheDocument()
    expect(screen.getAllByText('普通饮食参考，不替代医疗建议。')).not.toHaveLength(0)
  })

  it('never trusts raw stream text and does not provide a bypass when the safe snapshot refuses planning', async () => {
    const user = userEvent.setup()
    const request = requestWithSnapshot()
    request.mockImplementation(async (path: string) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
    if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning' || path.startsWith('/agent/threads/33333333')) return new Response(JSON.stringify({
        thread_id: '33333333-3333-4333-8333-333333333333', status: 'retryable', revision: 1,
        report: { stage: 'needs_input', message: '我们不能为你当前描述的情况生成个性化餐单。孕期或哺乳期、未成年人、疾病或用药、进食障碍或自伤，以及极端减重/增重目标需要专业评估。请咨询医生或注册营养师。你仍可以查看通用、非医疗的均衡饮食原则。' },
      }))
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))

    expect(await screen.findByText(/我们不能为你当前描述的情况生成个性化餐单/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '今日饮食计划' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /继续生成/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/provider|token|reasoning|raw-event/i)).not.toBeInTheDocument()
  })

  it('does not mislabel bounded candidate exhaustion as a health-scope refusal', async () => {
    const user = userEvent.setup()
    const request = requestWithSnapshot()
    request.mockImplementation(async (path: string) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
    if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning' || path.startsWith('/agent/threads/33333333')) return new Response(JSON.stringify({
        thread_id: '33333333-3333-4333-8333-333333333333', status: 'terminal', revision: 3,
        report: { stage: 'needs_input', message: '当前受控餐单暂时无法同时满足已确认约束；请稍后重试或修改饮食偏好。' },
      }))
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))

    const exhaustionTitle = await screen.findByText('暂时无法生成计划')
    expect(exhaustionTitle.closest('[role="alert"]')).toHaveTextContent('当前受控餐单暂时无法同时满足已确认约束；请稍后重试或修改饮食偏好。')
    expect(screen.getByText('当前受控餐单暂时无法同时满足已确认约束；请稍后重试或修改饮食偏好。')).toBeInTheDocument()
    expect(screen.queryByText('暂不能生成个性化餐单')).not.toBeInTheDocument()
    expect(screen.queryByText(/provider|node|stack|reasoning|raw payload/i)).not.toBeInTheDocument()
  })

  it('does not invent a previous meal when a saved adjustment is replayed after reload', async () => {
    const threadId = '33333333-3333-4333-8333-333333333333'
    const saved = {
      id: '44444444-4444-4444-8444-444444444444', plan_date: '2026-09-06', time_zone: 'Asia/Shanghai',
      current_version: 2, version: 2, created_at: '2026-09-06T00:00:00Z', updated_at: '2026-09-06T00:01:00Z', saved_at: '2026-09-06T00:01:00Z',
      report: adjustedReport, totals: { energy_kcal: '1900', carbohydrate_g: '200', protein_g: '100', fat_g: '60' }, adjustment_thread_id: threadId,
    }
    const request = vi.fn(async (path: string) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: saved }))
      if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === `/agent/threads/${threadId}`) return new Response(JSON.stringify({ thread_id: threadId, status: 'completed', revision: 2, report: adjustedReport }))
      if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
      return new Response('', { status: 500 })
    })
    renderPage(request)
    await screen.findByText('清淡豆腐菌菇午餐')
    await waitFor(() => expect(request).toHaveBeenCalledWith(`/agent/threads/${threadId}`, expect.anything()))
    expect(screen.queryByText(/^已替换：/)).not.toBeInTheDocument()
    expect(screen.queryByText('已更新午餐，其余餐次保持不变。')).not.toBeInTheDocument()
  })

  it('submits one labelled adjustment on the owned thread without moving focus to the polite replacement summary', async () => {
    const user = userEvent.setup()
    let adjusted = false
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      void init
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
    if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed', revision: 1, report }))
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333/input') {
        adjusted = true
        return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed' }))
      }
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed', revision: adjusted ? 2 : 1, report: adjusted ? adjustedReport : report }))
      if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    await screen.findByRole('heading', { name: '今日饮食计划' })
    await user.type(screen.getByLabelText('告诉我们想换什么'), '午餐换清淡一些，provider 不应显示')
    const submitButton = screen.getByRole('button', { name: '提交调整' })
    submitButton.focus()
    expect(submitButton).toHaveFocus()
    await user.click(submitButton)

    const adjustment = request.mock.calls.find(([path]) => path.endsWith('/input'))
    expect(JSON.parse(String(adjustment?.[1]?.body))).toEqual({ kind: 'description', text: '午餐换清淡一些，provider 不应显示' })
    expect(await screen.findByText('清淡豆腐菌菇午餐')).toBeInTheDocument()
    expect(screen.getAllByText('已调整')).toHaveLength(1)
    expect(screen.getByText('已替换：鸡胸肉米饭午餐')).toBeInTheDocument()
    expect(screen.getByText('已满足：清淡')).toBeInTheDocument()
    const completionSummary = screen.getByText('已更新午餐，其余餐次保持不变。')
    expect(completionSummary).toHaveAttribute('aria-live', 'polite')
    expect(completionSummary).not.toHaveAttribute('tabindex')
    expect(completionSummary).not.toHaveFocus()
    expect(submitButton).toHaveFocus()
    expect(screen.getByText('燕麦鸡蛋早餐')).toBeInTheDocument()
    expect(screen.getByText('三文鱼蔬菜晚餐')).toBeInTheDocument()
    expect(screen.queryByText('provider 不应显示')).not.toBeInTheDocument()
  })

  it('shows catalog candidates without auto-selection and resumes with only the chosen identity', async () => {
    const user = userEvent.setup()
    const foodId = '44444444-4444-4444-8444-444444444444'
    const clarification = {
      stage: 'food_clarification', message: '请选择要用于替换的受控菜品。',
      candidates: [{
        item_id: 'planning-substitution', food_id: foodId, catalog_version: 'catalog-v1', label: '番茄炒蛋（熟制）',
        canonical_label: '番茄炒蛋', relation_label: 'name_variant', prepared_state: '熟制', portion_hints: [], source_name: '受控营养目录',
      }],
    }
    let snapshot: object = report
    const inputBodies: unknown[] = []
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
      if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed', revision: 1, report }))
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333/input') {
        inputBodies.push(JSON.parse(String(init?.body)))
        snapshot = inputBodies.length === 1 ? clarification : adjustedReport
        return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: inputBodies.length === 1 ? 'waiting' : 'completed' }))
      }
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: snapshot === clarification ? 'waiting' : 'completed', revision: inputBodies.length + 1, report: snapshot }))
      if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    await screen.findByRole('heading', { name: '今日饮食计划' })
    await user.type(screen.getByLabelText('告诉我们想换什么'), '午餐换成西红柿炒鸡蛋')
    await user.click(screen.getByRole('button', { name: '提交调整' }))

    const candidateHeading = await screen.findByRole('heading', { name: '请选择要替换的菜品' })
    const submittedAdjustment = screen.getByRole('button', { name: '提交调整' })
    expect(submittedAdjustment).toBeDisabled()
    expect(submittedAdjustment.compareDocumentPosition(candidateHeading) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0)
    const option = screen.getByRole('radio', { name: /番茄炒蛋/ })
    expect(option).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('button', { name: '提交选择' })).toBeDisabled()
    expect(screen.queryByText(foodId)).not.toBeInTheDocument()

    await user.click(option)
    await user.click(screen.getByRole('button', { name: '提交选择' }))

    expect(inputBodies).toEqual([
      { kind: 'description', text: '午餐换成西红柿炒鸡蛋' },
      { kind: 'description', text: JSON.stringify({ candidate_id: foodId, catalog_version: 'catalog-v1' }) },
    ])
    expect(await screen.findByText('清淡豆腐菌菇午餐')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '请选择要替换的菜品' })).not.toBeInTheDocument()
  })

  it('waits for a specific recipe and submits only its identity and revision', async () => {
    const user = userEvent.setup()
    const foodId = '44444444-4444-4444-8444-444444444444'
    const clarification = {
      stage: 'food_clarification', message: '请选择要用于替换的受控菜品。',
      candidates: [{
        item_id: 'planning-substitution', food_id: foodId, catalog_version: 'catalog-v1', label: '番茄炒蛋（熟制）',
        canonical_label: '番茄炒蛋', relation_label: 'name_variant', prepared_state: '熟制', portion_hints: [], source_name: '受控营养目录',
      }],
    }
    const recipes = { stage: 'recipe_clarification', schema_version: 'recipe-choices.v1', message: '请选择份量和做法。', candidates: [
      { recipe_id: '55555555-5555-4555-8555-555555555555', revision: 2, food_id: foodId, catalog_version: 'catalog-v1', display_name: '烤鱼', meal_slot: 'lunch', portion_grams: '180', portion_description: '小份', method_tags: ['烤'], flavour_tags: ['清淡'] },
      { recipe_id: '66666666-6666-4666-8666-666666666666', revision: 3, food_id: foodId, catalog_version: 'catalog-v1', display_name: '烤鱼', meal_slot: 'lunch', portion_grams: '250', portion_description: '大份', method_tags: ['烤'], flavour_tags: ['麻辣'] },
    ] }
    let snapshot: object = report
    const inputBodies: unknown[] = []
    const request = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
      if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed', revision: 1, report }))
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333/input') {
        inputBodies.push(JSON.parse(String(init?.body)))
        snapshot = inputBodies.length === 1 ? clarification : inputBodies.length === 2 ? recipes : adjustedReport
        return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: inputBodies.length < 3 ? 'waiting' : 'completed' }))
      }
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: snapshot === clarification || snapshot === recipes ? 'waiting' : 'completed', revision: inputBodies.length + 1, report: snapshot }))
      if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    await screen.findByRole('heading', { name: '今日饮食计划' })
    await user.type(screen.getByLabelText('告诉我们想换什么'), '午餐换成西红柿炒鸡蛋')
    await user.click(screen.getByRole('button', { name: '提交调整' }))

    const candidateHeading = await screen.findByRole('heading', { name: '请选择要替换的菜品' })
    const submittedAdjustment = screen.getByRole('button', { name: '提交调整' })
    expect(submittedAdjustment).toBeDisabled()
    expect(submittedAdjustment.compareDocumentPosition(candidateHeading) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0)
    const option = screen.getByRole('radio', { name: /番茄炒蛋/ })
    expect(option).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('button', { name: '提交选择' })).toBeDisabled()
    expect(screen.queryByText(foodId)).not.toBeInTheDocument()

    await user.click(option)
    await user.click(screen.getByRole('button', { name: '提交选择' }))
    const recipeHeading = await screen.findByRole('heading', { name: '请选择具体菜谱' })
    expect(screen.getByRole('button', { name: '提交调整' }).compareDocumentPosition(recipeHeading) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0)
    const recipeButton = screen.getByRole('button', { name: '确认菜谱并替换' })
    expect(recipeButton).toBeDisabled()
    const large = screen.getByRole('radio', { name: /大份/ })
    expect(large).not.toBeChecked()
    expect(screen.getByRole('radio', { name: /小份/ })).not.toBeChecked()
    expect(screen.getByLabelText('告诉我们想换什么')).toBeDisabled()
    expect(screen.getByText('燕麦鸡蛋早餐')).toBeInTheDocument()
    expect(screen.getByText('三文鱼蔬菜晚餐')).toBeInTheDocument()
    await user.click(large)
    expect(recipeButton).toBeEnabled()
    await user.click(recipeButton)


    expect(inputBodies).toEqual([
      { kind: 'description', text: '午餐换成西红柿炒鸡蛋' },
      { kind: 'description', text: JSON.stringify({ candidate_id: foodId, catalog_version: 'catalog-v1' }) },
      { kind: 'description', text: JSON.stringify({ recipe_id: recipes.candidates[1].recipe_id, recipe_revision: 3 }) },
    ])
    expect(await screen.findByText('清淡豆腐菌菇午餐')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '请选择要替换的菜品' })).not.toBeInTheDocument()
  })

  it('contains ambiguous selection, makes permitted relaxation transparent, and never exposes raw feedback or internal IDs', async () => {
    const user = userEvent.setup()
    const ambiguous = { stage: 'needs_input', message: '请选择要调整的餐次。', input_choices: ['breakfast', 'lunch', 'dinner'] }
    const relaxed = {
      ...adjustedReport,
      adjustment: {
        ...adjustedReport.adjustment,
        relaxation: { metric: 'energy_kcal', original_range: { lower: '1800', upper: '2000' }, plan_value: '1760', deviation: '-40', reason: '在保留已确认约束后无严格合格替代项。' },
      },
    }
    let snapshot: object = ambiguous
    const request = vi.fn(async (path: string) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
    if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'waiting', revision: 1, report: snapshot }))
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333/input') { snapshot = relaxed; return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'completed' })) }
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: snapshot === ambiguous ? 'waiting' : 'completed', revision: 2, report: snapshot }))
      if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    await screen.findByRole('heading', { name: '请确认要调整哪一餐' })
    expect(screen.getAllByRole('button', { name: /早餐|午餐|晚餐/ })).toHaveLength(3)
    expect(screen.queryByText(/checkpoint|thread_id|raw feedback|memory_id/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '午餐' }))

    const relaxationAlert = await screen.findByText('已按现有约束生成餐单，但目标已调整')
    expect(relaxationAlert.closest('[role="alert"]')).toHaveTextContent('能量')
    expect(relaxationAlert.closest('[role="alert"]')).toHaveTextContent('1,800–2,000 kcal')
    expect(relaxationAlert.closest('[role="alert"]')).toHaveTextContent('1,760 kcal')
    expect(relaxationAlert.closest('[role="alert"]')).toHaveTextContent('-40 kcal')
    expect(relaxationAlert.closest('[role="alert"]')).toHaveTextContent('忌口和你明确排除的食物未被放宽。')
  })

  it('blocks a fourth adjustment with the exact limit actions and focuses a refusal without cards or bypass', async () => {
    const user = userEvent.setup()
    const limit = { stage: 'needs_input', code: 'LIMIT_REACHED', message: '本次计划已达到三次调整上限；请新建计划或修改资料与目标。' }
    const request = vi.fn(async (path: string) => {
      if (path === '/planning/plans/today') return new Response(JSON.stringify({ time_zone: 'Asia/Shanghai', today: '2026-09-06', plan: null }))
    if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'terminal', revision: 3, report: limit }))
      if (path === '/agent/threads/33333333-3333-4333-8333-333333333333') return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'terminal', revision: 3, report: limit }))
      if (path.endsWith('/events')) return new Response('', { headers: { 'Content-Type': 'text/event-stream' } })
      return new Response('', { status: 500 })
    })
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    expect(await screen.findByText(/已完成 3 次自动调整，无法在当前约束内继续修改/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '新建计划' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '修改个人资料' })).toHaveAttribute('href', '/app/me/profile')
    expect(screen.queryByLabelText('告诉我们想换什么')).not.toBeInTheDocument()
    expect(request.mock.calls.filter(([path]) => path.endsWith('/input'))).toHaveLength(0)
  })
})
