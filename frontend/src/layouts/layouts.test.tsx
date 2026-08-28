import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppHeader } from './AppHeader'
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

  it('renders a focusable deterministic return link in the detail header', () => {
    render(
      <MemoryRouter>
        <AppHeader title="账号资料" />
      </MemoryRouter>,
    )

    const backLink = screen.getByRole('link', { name: '返回我的' })
    expect(backLink).toHaveAttribute('href', '/app/me')
    expect(backLink).toHaveClass('h-11', 'w-11')
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

  it('keeps detail pages in their own no-tab layout with a stable my return route', () => {
    render(
      <MemoryRouter initialEntries={['/app/me/sessions']}>
        <Routes>
          <Route element={<DetailLayout title="登录会话" />}>
            <Route path="/app/me/sessions" element={<p>会话列表</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: '返回我的' })).toHaveAttribute('href', '/app/me')
    expect(screen.getByRole('main')).toHaveTextContent('会话列表')
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})
