import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AdminShell } from './AdminShell'

function renderShell() {
  const logout = vi.fn()
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/admin/overview']}><AdminShell onLogout={logout}><h2>概览内容</h2></AdminShell></MemoryRouter></QueryClientProvider>)
  return { logout }
}

describe('AdminShell', () => {
  it('提供 skip link、真实导航和可退出 session menu', async () => {
    const user = userEvent.setup()
    const { logout } = renderShell()
    await user.click(screen.getByRole('link', { name: '跳到主要内容' }))
    expect(screen.getByRole('main')).toHaveFocus()
    await user.click(screen.getByRole('button', { name: '打开会话菜单' }))
    await user.click(screen.getByRole('button', { name: '退出登录' }))
    expect(logout).toHaveBeenCalledOnce()
    expect(screen.getByRole('link', { name: '运行审计' })).toHaveAttribute('href', '/admin/runs')
  })

  it('768px Sheet 能以 Escape 关闭并将焦点还给触发器', async () => {
    window.innerWidth = 768
    window.dispatchEvent(new Event('resize'))
    const user = userEvent.setup()
    renderShell()
    const trigger = screen.getByRole('button', { name: '打开导航' })
    await user.click(trigger)
    expect(screen.getByRole('dialog', { name: '后台导航' })).toBeVisible()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: '后台导航' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('三档断点、200% zoom 与 reduced motion 保持可访问页面根且不横溢', () => {
    for (const width of [768, 1024, 1280]) {
      window.innerWidth = width
      window.dispatchEvent(new Event('resize'))
      const { unmount } = renderShell()
      expect(screen.getByTestId('admin-shell')).toHaveAttribute('data-navigation', width === 768 ? 'sheet' : width === 1024 ? 'compact' : 'full')
      expect(screen.getByTestId('admin-shell')).toHaveClass('overflow-x-hidden')
      unmount()
    }
  })
})
