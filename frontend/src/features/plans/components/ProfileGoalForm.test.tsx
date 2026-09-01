import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { ProfileGoalForm } from './ProfileGoalForm'

const profile = {
  height_cm: '170.00',
  weight_kg: '65.00',
  age_years: 30,
  formula_variant: 'mifflin_st_jeor_female',
  activity_level: 'moderate',
  goal: 'maintain',
  goal_speed: 'maintain',
  target_policy_version: 'target-policy.v1',
  formula_version: 'mifflin-st-jeor.v1',
}

function renderForm(request: AuthContextValue['request']) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}>
        <ProfileGoalForm />
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

function requestWith(profileResponse: Response = new Response(JSON.stringify(profile))) {
  return vi.fn(async (path: string, init?: RequestInit) => {
    if (path === '/planning/profile') return profileResponse
    if (path === '/memories') return new Response(JSON.stringify([
      { id: '11111111-1111-4111-8111-111111111111', category: 'avoidance', source_kind: 'user_maintained', canonical_text: '花生', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
      { id: '22222222-2222-4222-8222-222222222222', category: 'stable_preference', source_kind: 'user_maintained', canonical_text: '清淡', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' },
    ]))
    if (path === '/agent/threads/diet-planning') {
      expect(init?.method).toBe('POST')
      return new Response(JSON.stringify({ thread_id: '33333333-3333-4333-8333-333333333333', status: 'accepted', revision: 0 }), { status: 201 })
    }
    return new Response('', { status: 500 })
  })
}

describe('ProfileGoalForm', () => {
  it('shows complete visible body, formula, activity, conservative-speed, and read-only preference review before submit', async () => {
    renderForm(requestWith())

    await waitFor(() => expect(screen.getByLabelText('身高')).toHaveValue(170))
    expect(screen.getByLabelText('体重')).toHaveValue(65)
    expect(screen.getByLabelText('年龄')).toHaveValue(30)
    expect(screen.getByRole('group', { name: '用于目标估算的身体参数' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: '日常活动水平' })).toHaveTextContent('久坐大部分时间坐着，几乎不运动')
    expect(screen.getByRole('group', { name: '日常活动水平' })).toHaveTextContent('非常高高强度训练或体力工作为主')
    expect(screen.getByLabelText('目标速度')).toHaveValue('maintain')
    expect(screen.getByText('目标估算结果是饮食参考，不是医疗诊断。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '本次饮食偏好' })).toBeInTheDocument()
    expect(screen.getByText('忌口：已确认 花生')).toBeInTheDocument()
    expect(screen.getByText('口味：已确认 清淡')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '管理饮食偏好' })).toHaveAttribute('href', '/app/me/memories')
    expect(screen.queryByRole('textbox', { name: /忌口|口味/ })).not.toBeInTheDocument()
  })

  it('does not submit before preference review is confirmed and starts only the transient command when saving is off', async () => {
    const user = userEvent.setup()
    const request = requestWith()
    renderForm(request)
    await screen.findByText('忌口：已确认 花生')

    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    expect(screen.getByText('请先确认已复核本次饮食偏好。')).toBeInTheDocument()
    expect(request.mock.calls.some(([path]) => path === '/agent/threads/diet-planning')).toBe(false)

    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))

    await waitFor(() => expect(request.mock.calls.some(([path]) => path === '/agent/threads/diet-planning')).toBe(true))
    const start = request.mock.calls.find(([path]) => path === '/agent/threads/diet-planning')
    expect(JSON.parse(String(start?.[1]?.body))).toEqual({
      profile: {
        height_cm: '170', weight_kg: '65', age_years: 30, formula_variant: 'mifflin_st_jeor_female', activity_level: 'moderate', goal: 'maintain', goal_speed: 'maintain',
        is_pregnant_or_breastfeeding: false, has_disease_or_treatment: false, uses_medication: false, has_eating_disorder_or_self_harm_risk: false, has_extreme_weight_control_goal: false,
      },
      preferences: { confirmed: true, exclusions: ['花生'], taste_preferences: ['清淡'] },
      save_profile: false,
    })
    expect(request.mock.calls.filter(([path, init]) => path === '/planning/profile' && init?.method && init.method !== 'GET')).toHaveLength(0)
  })

  it('sends true only after the user explicitly selects the save control and keeps server field errors authoritative', async () => {
    const user = userEvent.setup()
    const request = requestWith()
    request.mockImplementation(async (path: string) => {
      if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories') return new Response('[]')
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ detail: [{ loc: ['body', 'profile', 'height_cm'], msg: '身高必须在 100 到 250 cm 之间。' }] }), { status: 422 })
      return new Response('', { status: 500 })
    })
    renderForm(request)
    await screen.findByLabelText('身高')

    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByLabelText('将本次身体资料和目标保存到个人资料'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))

    expect(await screen.findByText('身高必须在 100 到 250 cm 之间。')).toBeInTheDocument()
    const start = request.mock.calls.find(([path]) => path === '/agent/threads/diet-planning')
    expect(JSON.parse(String(start?.[1]?.body)).save_profile).toBe(true)
  })
})
