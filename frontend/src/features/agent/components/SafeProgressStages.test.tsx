import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { parseSafeAgentStageEvent } from '../api/stream'
import { SafeProgressStages } from './SafeProgressStages'

const fiveBusinessStages = ['perception', 'awaiting_input', 'tool_calculation', 'validation', 'completed'] as const

describe('SafeProgressStages', () => {
  it('strictly accepts the five public stages and bounded safe failures only', () => {
    for (const stage of [...fiveBusinessStages, 'retryable', 'terminal'] as const) {
      expect(parseSafeAgentStageEvent({
        schema_version: 'safe-stream-stage.v1',
        stage,
        message: '安全业务摘要。',
      }).stage).toBe(stage)
    }

    expect(() => parseSafeAgentStageEvent({
      schema_version: 'safe-stream-stage.v1',
      stage: 'completed',
      message: '安全业务摘要。',
      provider: 'fake-provider',
    })).toThrow()
    expect(() => parseSafeAgentStageEvent({
      schema_version: 'safe-stream-stage.v1',
      stage: 'internal_node',
      message: 'node=validate',
    })).toThrow()
  })

  it('shows every business stage but politely announces only the changed current stage', () => {
    const { rerender } = render(<SafeProgressStages stage="perception" />)

    for (const label of ['感知餐食', '等待补充', '营养计算', '结果校验', '完成分析']) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('status')).toHaveTextContent('正在识别餐食信息')

    rerender(<SafeProgressStages stage="validation" />)
    expect(screen.getByRole('status')).toHaveTextContent('正在校验分析结果')
  })

  it('offers one explicit retry for retryable failures without treating waiting or refusal as completion', async () => {
    const user = userEvent.setup()
    const retry = vi.fn()
    const { rerender } = render(<SafeProgressStages onRetry={retry} stage="retryable" />)

    await user.click(screen.getByRole('button', { name: '重新尝试' }))
    expect(retry).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('完成分析')).not.toHaveAttribute('aria-current', 'step')

    rerender(<SafeProgressStages stage="awaiting_input" />)
    expect(screen.queryByRole('button', { name: '重新尝试' })).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('等待你补充信息')

    rerender(<SafeProgressStages stage="terminal" />)
    expect(screen.queryByRole('button', { name: '重新尝试' })).not.toBeInTheDocument()
    expect(screen.queryByText('完成分析')).not.toHaveAttribute('aria-current', 'step')
  })

  it('never renders internal implementation words or raw payloads', () => {
    render(<SafeProgressStages stage="tool_calculation" />)
    expect(screen.queryByText(/provider|node|stack|reasoning|raw payload/i)).not.toBeInTheDocument()
  })
})
