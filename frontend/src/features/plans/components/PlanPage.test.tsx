import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

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

function renderPage(request: AuthContextValue['request']) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}>
        <PlanPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

function requestWithSnapshot() {
  return vi.fn(async (path: string, init?: RequestInit) => {
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
  it('owns read-only profile and memory queries, passes their displayed values into the form, and never writes while pre-filling', async () => {
    const request = requestWithSnapshot()
    renderPage(request)

    await waitFor(() => expect(screen.getByLabelText('身高')).toHaveValue(170))
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

    await screen.findByRole('heading', { name: '今日三餐计划' })
    const start = request.mock.calls.find(([path]) => path === '/agent/threads/diet-planning')
    expect(JSON.parse(String(start?.[1]?.body))).toMatchObject({
      profile: { height_cm: '170', weight_kg: '65', age_years: 30 },
      preferences: { confirmed: true, exclusions: ['花生'], taste_preferences: ['清淡'] }, save_profile: false,
    })
    expect(screen.getAllByRole('heading', { level: 3 }).map((heading) => heading.textContent)).toEqual(['早餐', '午餐', '晚餐'])
    expect(screen.getByText('燕麦鸡蛋早餐')).toBeInTheDocument()
    expect(screen.getByText('320g · 一份')).toBeInTheDocument()
    expect(screen.getByText('蒸煮 · 清淡')).toBeInTheDocument()
    expect(screen.getByText('已遵守：偏好：清淡 · 不吃花生')).toBeInTheDocument()
    expect(screen.getByText('目标：1,800–2,000 kcal · 计划：1,920 kcal · 适中')).toBeInTheDocument()
    expect(screen.getByText('普通饮食参考，不替代医疗建议。')).toBeInTheDocument()
  })

  it('never trusts raw stream text and does not provide a bypass when the safe snapshot refuses planning', async () => {
    const request = requestWithSnapshot()
    request.mockImplementation(async (path: string) => {
      if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning' || path.startsWith('/agent/threads/33333333')) return new Response(JSON.stringify({
        thread_id: '33333333-3333-4333-8333-333333333333', status: 'terminal', revision: 1,
        report: { stage: 'refusal', message: '我们不能为你当前描述的情况生成个性化餐单。' },
      }))
      return new Response('', { status: 500 })
    })
    renderPage(request)

    expect(screen.queryByText(/provider|token|reasoning|raw-event/i)).not.toBeInTheDocument()
  })
})
