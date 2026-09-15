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
    if (path === '/memories/preference-summary') return new Response(JSON.stringify({ exclusions: ['花生'], taste_preferences: ['清淡'] }))
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

    expect(await screen.findByText('170 cm')).toBeInTheDocument()
    expect(screen.getByText('65 kg')).toBeInTheDocument()
    expect(screen.getByText('30 岁')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '身体资料与目标' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '修改' })).toHaveAttribute('href', '/app/me/profile')
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('将本次身体资料和目标保存到个人资料')).not.toBeInTheDocument()
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

  it('keeps server profile errors visible without silently writing the saved profile', async () => {
    const user = userEvent.setup()
    const request = requestWith()
    request.mockImplementation(async (path: string) => {
      if (path === '/planning/profile') return new Response(JSON.stringify(profile))
      if (path === '/memories/preference-summary') return new Response(JSON.stringify({ exclusions: [], taste_preferences: [] }))
      if (path === '/agent/threads/diet-planning') return new Response(JSON.stringify({ detail: [{ loc: ['body', 'profile', 'height_cm'], msg: '身高必须在 100 到 250 cm 之间。' }] }), { status: 422 })
      return new Response('', { status: 500 })
    })
    renderForm(request)
    await screen.findByText('170 cm')

    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))

    expect(await screen.findByText('身高必须在 100 到 250 cm 之间。')).toBeInTheDocument()
    const start = request.mock.calls.find(([path]) => path === '/agent/threads/diet-planning')
    expect(JSON.parse(String(start?.[1]?.body)).save_profile).toBe(false)
  })
  it.each([404, 500])('blocks generation when profile is absent or unavailable (%s)', async (status) => {
    const user = userEvent.setup()
    const request = requestWith(new Response('', { status }))
    renderForm(request)
    await screen.findByText('忌口：已确认 花生')
    await user.click(screen.getByLabelText('我已复核以上饮食偏好'))
    expect(screen.getByRole('button', { name: '生成今日餐单' })).toBeDisabled()
    expect(request.mock.calls.some(([path]) => path === '/agent/threads/diet-planning')).toBe(false)
    expect(screen.getByRole('link', { name: status === 404 ? '去填写' : '查看个人资料' })).toHaveAttribute('href', '/app/me/profile')
  })

  it('requires a fresh review when the preference summary changes', async () => {
    const user = userEvent.setup()
    const request = requestWith()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}><ProfileGoalForm /></AuthContext.Provider></QueryClientProvider>)
    await screen.findByText('忌口：已确认 花生')
    const checkbox = screen.getByLabelText('我已复核以上饮食偏好')
    await user.click(checkbox)
    expect(checkbox).toBeChecked()
    client.setQueryData(['planning-preference-summary'], { exclusions: ['不吃辣'], tastePreferences: ['少油'] })
    await screen.findByText('忌口：已确认 不吃辣')
    await waitFor(() => expect(checkbox).not.toBeChecked())
    await user.click(screen.getByRole('button', { name: '生成今日餐单' }))
    expect(request.mock.calls.some(([path]) => path === '/agent/threads/diet-planning')).toBe(false)
  })

  it('blocks generation when the preference summary is unavailable', async () => {
    const fallback = requestWith()
    const request = vi.fn(async (path: string, init?: RequestInit) => path === '/memories/preference-summary' ? new Response('', { status: 503 }) : fallback(path, init))
    renderForm(request)
    await screen.findByText('暂时无法读取饮食偏好，请稍后重试。')
    expect(screen.getByRole('button', { name: '生成今日餐单' })).toBeDisabled()
    expect(request.mock.calls.some(([path]) => path === '/agent/threads/diet-planning')).toBe(false)
  })

})
