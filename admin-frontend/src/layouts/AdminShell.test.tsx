import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AdminShell } from './AdminShell'
import { AdminAuthProvider } from '@/auth/AdminAuthProvider'

function renderShell() {
  const logout = vi.fn()
  const result = render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/admin/overview']}><AdminAuthProvider><AdminShell onLogout={logout}><h2>概览内容</h2></AdminShell></AdminAuthProvider></MemoryRouter></QueryClientProvider>)
  return { logout, ...result }
}

describe('AdminShell', () => {
  it('提供 skip link、真实导航和可退出 session menu', async () => {
    const user = userEvent.setup()
    const { logout } = renderShell()
    await user.click(screen.getByRole('link', { name: '跳到主要内容' }))
    expect(screen.getByRole('main')).toHaveFocus()
    await user.click(screen.getByRole('button', { name: '打开会话菜单' }))
    await user.click(screen.getByRole('menuitem', { name: '退出登录' }))
    expect(logout).toHaveBeenCalledOnce()
    expect(screen.getByRole('link', { name: '运行审计' })).toHaveAttribute('href', '/admin/runs')
  })

  it('窄屏抽屉能以 Escape 关闭并将焦点还给触发器', async () => {
    window.innerWidth = 768
    window.dispatchEvent(new Event('resize'))
    const user = userEvent.setup()
    renderShell()
    const trigger = screen.getByRole('button', { name: '打开导航' })
    await user.click(trigger)
    expect(screen.getByRole('dialog', { name: '后台导航' })).toBeVisible()
    expect(screen.getByRole('button', { name: '关闭导航' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: '后台导航' })).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('移动与桌面断点保持可访问页面根且不横溢', () => {
    for (const width of [768, 1024, 1280]) {
      window.innerWidth = width
      window.dispatchEvent(new Event('resize'))
      const { unmount } = renderShell()
      expect(screen.getByTestId('admin-shell')).toHaveAttribute('data-navigation', width < 1024 ? 'mobile' : 'desktop')
      expect(screen.getByTestId('admin-shell')).toHaveAttribute('data-sidebar-collapsed', width === 1024 ? 'true' : 'false')
      expect(screen.getByTestId('admin-shell')).toHaveClass('overflow-x-hidden')
      unmount()
    }
  })

  it('桌面端主内容区域可纵向滚动，避免超出视口的页面被裁切', () => {
    window.innerWidth = 1440
    window.dispatchEvent(new Event('resize'))
    renderShell()

    expect(screen.getByRole('main')).toHaveClass('lg:overflow-y-auto')
    expect(screen.getByRole('main')).not.toHaveClass('lg:overflow-hidden')
  })

  it('二级菜单可折叠，并为访问过的页面创建和关闭标签', async () => {
    window.innerWidth = 1440
    window.dispatchEvent(new Event('resize'))
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: '内容管理' }))
    expect(screen.queryByRole('link', { name: '营养目录' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '内容管理' }))
    await user.click(screen.getByRole('link', { name: '营养目录' }))

    expect(screen.getByRole('tab', { name: '营养目录' })).toHaveAttribute('aria-selected', 'true')
    await user.click(screen.getByRole('button', { name: '关闭营养目录' }))
    expect(screen.getByRole('tab', { name: '运行概览' })).toHaveAttribute('aria-selected', 'true')
  })
})
