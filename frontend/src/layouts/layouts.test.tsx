import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  createMemoryRouter,
  MemoryRouter,
  Route,
  RouterProvider,
  Routes,
} from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppHeader } from './AppHeader'
import { AppShell } from './AppShell'
import { DetailLayout } from './DetailLayout'
import { MobileFrame } from './MobileFrame'
import { PageScrollArea } from './PageScrollArea'
import { PublicAuthLayout } from './PublicAuthLayout'

describe('layout foundations', () => {
  it('keeps the frame as the viewport flex owner and the page as the only main landmark', () => {
    const { container } = render(
      <MobileFrame>
        <PageScrollArea>内容</PageScrollArea>
      </MobileFrame>,
    )

    const frame = screen.getByTestId('mobile-frame')
    const main = screen.getByRole('main')

    expect(frame).toHaveClass('h-dvh', 'flex', 'flex-col', 'overflow-hidden')
    expect(frame).toHaveClass('min-[768px]:w-[min(430px,calc(100vw-2rem))]')
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toHaveClass('flex-1', 'min-h-0', 'overflow-y-auto')
    expect(container.querySelectorAll('main')).toHaveLength(1)
  })

  it('returns through browser history in the detail header', async () => {
    const user = userEvent.setup()
    const router = createMemoryRouter([
      { element: <p>记录内容</p>, path: '/app/records' },
      { element: <AppHeader title="餐食记录" />, path: '/app/records/record-id' },
    ], { initialEntries: ['/app/records', '/app/records/record-id'], initialIndex: 1 })

    render(<RouterProvider router={router} />)

    const backButton = screen.getByRole('button', { name: '返回上一页' })
    expect(backButton).toHaveClass('h-11', 'w-11')
    await user.click(backButton)
    expect(router.state.location.pathname).toBe('/app/records')
  })

  it('keeps the detail title focusable', () => {
    render(
      <MemoryRouter>
        <AppHeader title="账号资料" />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '账号资料' })).toHaveClass('truncate')
  })

  it('uses an entry header without a tab bar for public pages', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<PublicAuthLayout mode="entry" />}>
            <Route path="/login" element={<h1>登录</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '饮食健康 Agent' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('main')).toHaveTextContent('登录')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('uses an explicit deep-link-safe return target for later auth steps', () => {
    render(
      <MemoryRouter initialEntries={['/register/verify']}>
        <Routes>
          <Route element={<PublicAuthLayout backTo="/register" mode="step" />}>
            <Route path="/register/verify" element={<h1>验证邮箱</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '返回上一步' })).toHaveAttribute('href', '/register')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('keeps detail pages in their own no-tab layout with a history return action', () => {
    render(
      <MemoryRouter initialEntries={['/app/me/sessions']}>
        <Routes>
          <Route element={<DetailLayout title="登录会话" />}>
            <Route path="/app/me/sessions" element={<p>会话列表</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: '返回上一页' })).toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveTextContent('会话列表')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})

describe('tab shell navigation', () => {
  function createTabRouter(initialEntry = '/app/me') {
    return createMemoryRouter(
      [
        {
          element: <AppShell />,
          path: '/app',
          children: [
            { element: <p>分析内容</p>, path: 'analyze' },
            { element: <p>记录内容</p>, path: 'records' },
            { element: <p>计划内容</p>, path: 'plans' },
            { element: <p>我的内容</p>, path: 'me' },
          ],
        },
      ],
      { initialEntries: [initialEntry] },
    )
  }

  it('renders the four controlled route tabs in the fixed order with the active page exposed', () => {
    const router = createTabRouter()
    const { container } = render(<RouterProvider router={router} />)

    const navigation = screen.getByRole('navigation', { name: '主要导航' })
    const tabs = within(navigation).getAllByRole('link')

    expect(tabs.map((tab) => tab.textContent)).toEqual(['分析', '记录', '计划', '我的'])
    expect(tabs.map((tab) => tab.getAttribute('href'))).toEqual([
      '/app/analyze',
      '/app/records',
      '/app/plans',
      '/app/me',
    ])
    expect(screen.getByRole('link', { name: '我的' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: '我的' })).toHaveClass('font-semibold', 'text-primary')
    expect(navigation).toHaveClass('shrink-0')
    expect(navigation).not.toHaveClass('fixed')
    expect(within(navigation).getAllByRole('link')).toHaveLength(4)
    expect(container.querySelectorAll('h1')).toHaveLength(1)
  })

  it('keeps ordinary tab navigation in browser history and exposes a visible-focus skip link', async () => {
    const user = userEvent.setup()
    const router = createTabRouter()
    render(<RouterProvider router={router} />)

    const skipLink = screen.getByRole('link', { name: '跳到主要内容' })
    expect(skipLink).toHaveAttribute('href', '#main-content')
    expect(skipLink).toHaveClass('focus:not-sr-only')

    await user.click(screen.getByRole('link', { name: '计划' }))
    expect(router.state.location.pathname).toBe('/app/plans')

    await act(() => router.navigate(-1))
    expect(router.state.location.pathname).toBe('/app/me')
  })

  it('keeps the main scroll region and bottom navigation as frame siblings', () => {
    const router = createTabRouter('/app/analyze')
    render(<RouterProvider router={router} />)

    const frame = screen.getByTestId('mobile-frame')
    const main = screen.getByRole('main')
    const navigation = screen.getByRole('navigation', { name: '主要导航' })

    expect(main.parentElement).toBe(frame)
    expect(navigation.parentElement).toBe(frame)
    expect(screen.getByRole('banner').parentElement).toBe(frame)
    expect(screen.getByRole('heading', { level: 1, name: '分析这餐' })).toHaveFocus()
  })

  it('resets scrolling and focuses the title on tab changes, but preserves same-page query updates', async () => {
    const router = createTabRouter('/app/analyze')
    render(<RouterProvider router={router} />)
    const main = screen.getByRole('main')
    main.scrollTop = 240
    main.focus()

    await act(() => router.navigate('/app/analyze?thread=existing'))
    expect(main.scrollTop).toBe(240)
    expect(main).toHaveFocus()

    await act(() => router.navigate('/app/records'))
    expect(main.scrollTop).toBe(0)
    expect(screen.getByRole('heading', { level: 1, name: '饮食记录' })).toHaveFocus()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })
})
