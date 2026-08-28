import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { routePaths } from '@/routePaths'

import { MePage } from './MePage'
import { PlaceholderTabPage } from './PlaceholderTabPage'

describe('honest placeholder tab pages', () => {
  it.each(['分析', '记录', '计划'] as const)('renders only the locked %s status', (title) => {
    render(
      <MemoryRouter>
        <PlaceholderTabPage title={title} />
      </MemoryRouter>,
    )

    const heading = screen.getByRole('heading', { level: 1, name: title })
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(screen.getByText('功能即将开放')).toBeInTheDocument()
    expect(heading).toHaveFocus()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/上传|加载|骨架/i)).not.toBeInTheDocument()
  })
})

describe('my settings root page', () => {
  it('exposes only the two complete settings links and keeps keyboard navigation native', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <MePage />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1, name: '我的' })).toBeInTheDocument()
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(2)
    expect(screen.getByRole('link', { name: /账号资料/ })).toHaveAttribute('href', routePaths.account)
    expect(screen.getByRole('link', { name: /登录会话/ })).toHaveAttribute('href', routePaths.sessions)
    expect(screen.queryByText(/@/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /退出|保存|编辑/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/偏好|设置/i)).not.toBeInTheDocument()

    for (const link of links) {
      expect(link.querySelectorAll('svg')).toHaveLength(2)
    }

    await user.tab()
    expect(screen.getByRole('link', { name: /账号资料/ })).toHaveFocus()
  })
})
