import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '@/auth/AuthContext'
import { PersonalProfilePage } from './PersonalProfilePage'

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

function renderPage(request: AuthContextValue['request']) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <AuthContext.Provider value={{ login: vi.fn(), logout: vi.fn(), request, retryBootstrap: vi.fn(), status: 'authenticated' }}>
          <PersonalProfilePage />
        </AuthContext.Provider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

function requestWithProfile(initialProfile: typeof profile | null = profile) {
  let current = initialProfile
  return vi.fn(async (path: string, init?: RequestInit) => {
    if (path !== '/planning/profile') return new Response('', { status: 500 })
    if (!init?.method || init.method === 'GET') {
      return current
        ? new Response(JSON.stringify(current))
        : new Response('', { status: 404 })
    }
    if (init.method === 'PUT' || init.method === 'PATCH') {
      current = { ...profile, ...JSON.parse(String(init.body)) }
      return new Response(JSON.stringify(current))
    }
    if (init.method === 'DELETE') {
      current = null
      return new Response(null, { status: 204 })
    }
    return new Response('', { status: 500 })
  })
}

describe('PersonalProfilePage', () => {
  it('renders body and goal details with the memory page as the only preference destination', async () => {
    const request = requestWithProfile()
    renderPage(request)

    expect(await screen.findByText('170 cm')).toBeInTheDocument()
    expect(screen.getByText('65 kg')).toBeInTheDocument()
    expect(screen.getByText('30 岁')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '管理饮食偏好' })).toHaveAttribute('href', '/app/me/memories')
    expect(screen.queryByRole('textbox', { name: /忌口|口味/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/避免|口味偏好/)).not.toBeInTheDocument()
  })

  it('requires an explicit save action and keeps server errors visible beside the form', async () => {
    const user = userEvent.setup()
    const request = requestWithProfile()
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByRole('button', { name: '编辑个人资料' }))
    await user.clear(screen.getByLabelText('身高'))
    await user.type(screen.getByLabelText('身高'), '171')
    await user.click(screen.getByRole('button', { name: '保存个人资料' }))

    await waitFor(() => expect(request).toHaveBeenCalledWith('/planning/profile', expect.objectContaining({ method: 'PUT' })))
    expect(await screen.findByText('171 cm')).toBeInTheDocument()
  })

  it('confirms the irreversible deletion, invalidates cached profile data, and shows the empty state', async () => {
    const user = userEvent.setup()
    const request = requestWithProfile()
    renderPage(request)

    await screen.findByText('170 cm')
    await user.click(screen.getByRole('button', { name: '删除个人资料' }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent('删除个人资料后，后续计划将不再读取这些身体资料和目标。此操作无法撤销。')
    await user.click(screen.getByRole('button', { name: '取消' }))
    expect(request.mock.calls.some(([path, init]) => path === '/planning/profile' && init?.method === 'DELETE')).toBe(false)

    await user.click(screen.getByRole('button', { name: '删除个人资料' }))
    await user.click(screen.getByRole('button', { name: '确认删除' }))

    expect(await screen.findByRole('heading', { name: '还没有保存个人资料' })).toBeInTheDocument()
    expect(screen.getByText('请先在计划页填写身体资料和目标，保存后会在这里显示。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '去计划页填写' })).toHaveAttribute('href', '/app/plans')
    expect(screen.getByText('个人资料已删除。后续计划不会再读取这些资料。')).toBeInTheDocument()
    expect(request.mock.calls.some(([path, init]) => path === '/planning/profile' && init?.method === 'DELETE')).toBe(true)
  })
})
