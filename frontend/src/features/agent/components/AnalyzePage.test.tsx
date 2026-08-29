import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AnalyzePage } from './AnalyzePage'

describe('AnalyzePage', () => {
  it('uses a labelled text input and states that analysis is not connected without a fake report', () => {
    render(<AnalyzePage />)

    expect(screen.getByRole('heading', { name: '描述这餐吃了什么' })).toBeInTheDocument()
    expect(screen.getByLabelText('餐食描述')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('分析能力正在接线中')
    expect(screen.queryByText(/kcal/i)).not.toBeInTheDocument()
  })

  it('explains empty and too-long descriptions next to the input', async () => {
    const user = userEvent.setup()
    render(<AnalyzePage />)

    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(screen.getByText('请先描述这餐吃了什么。')).toBeInTheDocument()

    await user.type(screen.getByLabelText('餐食描述'), 'a'.repeat(1001))
    await user.click(screen.getByRole('button', { name: '开始分析' }))
    expect(screen.getByText('描述最多可输入 1000 个字符。')).toBeInTheDocument()
  })

  it('announces submitting and then the honest unavailable state', async () => {
    const user = userEvent.setup()
    let settle: ((value: 'unavailable') => void) | undefined
    const submitAnalysis = vi.fn(() => new Promise<'unavailable'>((resolve) => { settle = resolve }))
    render(<AnalyzePage submitAnalysis={submitAnalysis} />)

    await user.type(screen.getByLabelText('餐食描述'), '一碗番茄鸡蛋面')
    await user.click(screen.getByRole('button', { name: '开始分析' }))

    expect(screen.getByRole('button', { name: '正在提交…' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('正在提交描述')

    settle?.('unavailable')
    expect(await screen.findByRole('status')).toHaveTextContent('分析能力正在接线中')
  })
})
