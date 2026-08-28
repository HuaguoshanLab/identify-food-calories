import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AppHeader } from './AppHeader'
import { MobileFrame } from './MobileFrame'
import { PageScrollArea } from './PageScrollArea'

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
})
