import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { parseSafePlanningStageEvent } from '../api/stream'
import { SafePlanningProgress } from './SafePlanningProgress'

describe('SafePlanningProgress', () => {
  it('accepts only the versioned safe SSE contract and rejects extra runtime fields', () => {
    expect(parseSafePlanningStageEvent({
      schema_version: 'safe-stream-stage.v1',
      stage: 'validation',
      message: '正在校验营养与已确认约束。',
    })).toEqual({
      schema_version: 'safe-stream-stage.v1',
      stage: 'validation',
      message: '正在校验营养与已确认约束。',
    })
    expect(() => parseSafePlanningStageEvent({
      schema_version: 'safe-stream-stage.v1',
      stage: 'validation',
      message: '正在校验营养与已确认约束。',
      graph_state: { private: true },
    })).toThrow()
  })

  it('renders the five shared business stages with a polite changed-stage announcement', () => {
    const { rerender } = render(<SafePlanningProgress stage="awaiting_input" />)
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('status')).toHaveTextContent('等待你补充信息')
    expect(screen.getByText('感知资料')).toBeInTheDocument()
    expect(screen.getByText('等待补充')).toBeInTheDocument()
    expect(screen.getByText('目标计算')).toBeInTheDocument()
    expect(screen.getByText('结果校验')).toBeInTheDocument()
    expect(screen.getByText('完成计划')).toBeInTheDocument()

    rerender(<SafePlanningProgress stage="completed" />)
    expect(screen.getByRole('status')).toHaveTextContent('计划已生成')
  })

  it('keeps retry bounded and never retries waiting or scope refusal automatically', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    const { rerender } = render(<SafePlanningProgress onRetry={retry} stage="retryable" />)
    await user.click(screen.getByRole('button', { name: '重新尝试' }))
    expect(retry).toHaveBeenCalledTimes(1)

    rerender(<SafePlanningProgress onRetry={retry} stage="awaiting_input" />)
    expect(screen.queryByRole('button', { name: '重新尝试' })).not.toBeInTheDocument()
    rerender(<SafePlanningProgress onRetry={retry} stage="terminal" />)
    expect(screen.queryByRole('button', { name: '重新尝试' })).not.toBeInTheDocument()
    expect(screen.queryByText(/provider|node|stack|reasoning|raw payload/i)).not.toBeInTheDocument()
  })
})
