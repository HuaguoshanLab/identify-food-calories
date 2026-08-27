import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from './App'

function renderApp() {
  return render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('renders the public product landing page', () => {
    renderApp()

    expect(
      screen.getByRole('heading', { name: '拍下或描述一餐，获得可追问的饮食分析' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '创建账号' })).toHaveAttribute('href', '/register')
  })
})
