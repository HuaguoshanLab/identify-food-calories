import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ForgotPasswordPage } from './ForgotPasswordPage'
import { LoginPage } from './LoginPage'
import { RegisterPage } from './RegisterPage'
import { RegisterVerifyPage } from './RegisterVerifyPage'
import { ResetPasswordPage } from './ResetPasswordPage'
import { AuthProvider } from './AuthProvider'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function renderAuthPage(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/login" element={<AuthProvider><LoginPage /></AuthProvider>} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/register/verify" element={<RegisterVerifyPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('authentication forms', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses permanent labels, autocomplete and client validation for the login form', async () => {
    const user = userEvent.setup()
    renderAuthPage('/login')

    expect(screen.getByRole('button', { name: '登录并继续' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '忘记密码？' })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
    expect(screen.getByLabelText('邮箱')).toHaveAttribute('autocomplete', 'email')
    expect(screen.getByLabelText('密码')).toHaveAttribute('autocomplete', 'current-password')

    await user.click(screen.getByRole('button', { name: '登录并继续' }))

    expect(await screen.findByText('请输入有效的邮箱地址。')).toBeInTheDocument()
    expect(screen.getByLabelText('邮箱')).toHaveFocus()
  })

  it('sends only the registration email and password before replacing the verification route', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            status: 'CODE_DISPATCH_ACCEPTED',
            masked_email: 'm***@example.com',
            resend_available_at: '2026-08-27T00:01:00Z',
            expires_at: '2026-08-27T00:10:00Z',
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          masked_email: 'm***@example.com',
          resend_available_at: '2026-08-27T00:01:00Z',
          expires_at: '2026-08-27T00:10:00Z',
        }),
      )
    vi.stubGlobal('fetch', fetchMock)

    renderAuthPage('/register')
    await user.type(screen.getByLabelText('邮箱'), 'mina@example.com')
    await user.type(screen.getByLabelText('密码'), 'correct horse battery')
    await user.type(screen.getByLabelText('确认密码'), 'correct horse battery')
    await user.click(screen.getByRole('button', { name: '发送验证码' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/auth/register')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      email: 'mina@example.com',
      password: 'correct horse battery',
    })
    expect(screen.getByRole('heading', { name: '验证邮箱' })).toBeInTheDocument()
  })

  it('keeps entry-form progress and field-level errors accessible', async () => {
    const user = userEvent.setup()
    const registerPage = renderAuthPage('/register')

    expect(screen.getByText('步骤 1/2')).toBeInTheDocument()
    const registerEmail = screen.getByLabelText('邮箱')
    expect(registerEmail).toHaveAttribute('aria-invalid', 'false')
    await user.click(screen.getByRole('button', { name: '发送验证码' }))
    expect(await screen.findByText('请输入有效的邮箱地址。')).toBeInTheDocument()
    expect(registerEmail).toHaveAttribute('aria-describedby', 'register-email-error')
    registerPage.unmount()

    renderAuthPage('/forgot-password')

    expect(screen.getByText('步骤 1/2')).toBeInTheDocument()
    const forgotEmail = screen.getByLabelText('邮箱')
    expect(forgotEmail).toHaveAttribute('aria-invalid', 'false')
    await user.click(screen.getByRole('button', { name: '发送重置验证码' }))
    expect(await screen.findByText('请输入有效的邮箱地址。')).toBeInTheDocument()
    expect(forgotEmail).toHaveAttribute('aria-describedby', 'forgot-email-error')
  })

  it('maps expired verification, resend replacement and accessible cooldown states', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          masked_email: 'm***@example.com',
          resend_available_at: '2020-01-01T00:00:00Z',
          expires_at: '2026-08-27T00:10:00Z',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: 'VERIFICATION_CODE_EXPIRED', request_id: 'request-1' } },
          410,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            status: 'CODE_DISPATCH_ACCEPTED',
            masked_email: 'm***@example.com',
            resend_available_at: new Date(Date.now() + 60_000).toISOString(),
            expires_at: '2026-08-27T00:10:00Z',
          },
          202,
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    renderAuthPage('/register/verify')
    const codeInput = await screen.findByRole('textbox', { name: '6 位邮箱验证码' })
    expect(screen.getByText('步骤 2/2')).toBeInTheDocument()
    expect(codeInput).toHaveAttribute('autocomplete', 'one-time-code')
    expect(codeInput).toHaveAttribute('inputmode', 'numeric')
    expect(codeInput).toHaveAttribute('maxlength', '6')
    fireEvent.change(codeInput, { target: { value: '１２３４５６' } })
    expect(codeInput).toHaveValue('')

    await user.type(codeInput, '123456')
    await user.click(screen.getByRole('button', { name: '验证并激活账号' }))

    expect(await screen.findByText('验证码已过期，请重新发送。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '验证并激活账号' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: '重新发送验证码' }))

    expect(await screen.findByText('新验证码已发送，之前的验证码已失效。')).toHaveAttribute(
      'aria-live',
      'polite',
    )
    expect(codeInput).toHaveValue('')
    await waitFor(() => expect(codeInput).toHaveFocus())
    expect(screen.getByRole('button', { name: /秒后可重新发送/ })).toBeDisabled()
  })

  it('maps terminal and invalid pending contexts to explicit recovery actions', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          masked_email: 'm***@example.com',
          resend_available_at: '2020-01-01T00:00:00Z',
          expires_at: '2026-08-27T00:10:00Z',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: 'VERIFICATION_ATTEMPTS_EXCEEDED', request_id: 'request-2' } },
          429,
        ),
      )
    vi.stubGlobal('fetch', fetchMock)

    renderAuthPage('/register/verify')
    const codeInput = await screen.findByRole('textbox', { name: '6 位邮箱验证码' })
    await user.type(codeInput, '123456')
    await user.click(screen.getByRole('button', { name: '验证并激活账号' }))

    expect(await screen.findByText('验证码已失效，请重新发送后再试。')).toBeInTheDocument()
    expect(codeInput).toHaveValue('')
    expect(screen.getByRole('button', { name: '验证并激活账号' })).toBeDisabled()

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: 'VERIFICATION_CONTEXT_INVALID' } }, 409),
      ),
    )
    renderAuthPage('/register/verify')
    expect(await screen.findByText('验证信息已失效，请重新开始。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回注册' })).toHaveAttribute('href', '/register')
  })

  it('uses the server retry_after cooldown and offers explicit network recovery', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          masked_email: 'm***@example.com',
          resend_available_at: '2020-01-01T00:00:00Z',
          expires_at: '2026-08-27T00:10:00Z',
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: 'RESEND_COOLDOWN', retry_after: 17, request_id: 'request-3' } },
          429,
        ),
      )
    vi.stubGlobal('fetch', fetchMock)
    renderAuthPage('/register/verify')

    await screen.findByRole('textbox', { name: '6 位邮箱验证码' })
    await user.click(screen.getByRole('button', { name: '重新发送验证码' }))
    expect(await screen.findByRole('button', { name: '17 秒后可重新发送' })).toBeDisabled()
  })

  it('offers explicit recovery when verification loses network connectivity', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({
            masked_email: 'm***@example.com',
            resend_available_at: '2020-01-01T00:00:00Z',
            expires_at: '2026-08-27T00:10:00Z',
          }),
        )
        .mockRejectedValueOnce(new TypeError('offline')),
    )
    renderAuthPage('/register/verify')
    const codeInput = await screen.findByRole('textbox', { name: '6 位邮箱验证码' })
    await user.type(codeInput, '123456')
    await user.click(screen.getByRole('button', { name: '验证并激活账号' }))

    expect(await screen.findByText('暂时无法连接服务，请检查网络后重试。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新尝试验证' })).toBeInTheDocument()
  })

  it('keeps recovery shells public without persisting email, code, or passwords', async () => {
    const user = userEvent.setup()
    renderAuthPage('/forgot-password')

    expect(screen.getByRole('heading', { name: '忘记密码' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('邮箱'), 'mina@example.com')
    await user.click(screen.getByRole('button', { name: '发送重置验证码' }))
    expect(await screen.findByText('服务暂时不可用，请稍后再试。')).toBeInTheDocument()

    renderAuthPage('/reset-password')
    expect(screen.getByRole('heading', { name: '重置密码' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '重新申请重置' })).toHaveAttribute(
      'href',
      '/forgot-password',
    )
  })
})
