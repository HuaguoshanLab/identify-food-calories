import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

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
