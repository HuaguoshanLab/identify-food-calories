import { useEffect, useRef, useState, type FormEvent } from 'react'

import { useAuth } from '@/auth/useAuth'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { agentThreadSnapshotSchema, type AgentThreadSnapshot } from '../api/schemas.generated'
import { useAgentEventStream } from '../stream/useAgentEventStream'

const MAX_DESCRIPTION_LENGTH = 1000
type AnalysisStatus = 'idle' | 'submitting' | 'error' | 'completed'

export function AnalyzePage() {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const { request } = useAuth()
  const [description, setDescription] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [status, setStatus] = useState<AnalysisStatus>('idle')
  const [snapshot, setSnapshot] = useState<AgentThreadSnapshot>()
  const [progress, setProgress] = useState('')

  useEffect(() => { headingRef.current?.focus() }, [])
  useAgentEventStream({
    threadId: snapshot?.thread_id,
    request,
    onEvent: (event) => setProgress(event.summary),
  })

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const inputText = description.trim()
    if (!inputText) {
      setFieldError('请先描述这餐吃了什么。')
      return
    }
    if (description.length > MAX_DESCRIPTION_LENGTH) {
      setFieldError(`描述最多可输入 ${MAX_DESCRIPTION_LENGTH} 个字符。`)
      return
    }
    setFieldError(undefined)
    setProgress('正在提交描述…')
    setStatus('submitting')
    try {
      const response = await request('/agent/threads', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input_text: inputText }),
      })
      const body = await response.json().catch(() => undefined)
      if (!response.ok) throw new Error('agent request failed')
      const next = agentThreadSnapshotSchema.parse(body)
      setSnapshot(next)
      setStatus(next.status === 'completed' ? 'completed' : 'idle')
    } catch {
      setStatus('error')
      setProgress('暂时无法完成分析，请检查描述后重试。')
    }
  }

  const report = snapshot?.report as { items?: Array<Record<string, string>>; totals?: Record<string, string>; disclaimer?: string } | undefined

  return (
    <section className="mx-auto w-full max-w-xl space-y-6">
      <div className="space-y-2">
        <h1 ref={headingRef} tabIndex={-1} className="text-[28px] font-bold leading-9 tracking-tight">描述这餐吃了什么</h1>
        <p className="text-[15px] leading-6 text-muted-foreground">写下食物和明确克数；营养数值由后端受控目录确定性计算。</p>
      </div>
      <form className="space-y-4" noValidate onSubmit={handleSubmit}>
        <div className="space-y-2">
          <Label htmlFor="meal-description">餐食描述</Label>
          <textarea aria-describedby={fieldError ? 'meal-description-error' : undefined} aria-invalid={Boolean(fieldError)} className="min-h-28 w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50" disabled={status === 'submitting'} id="meal-description" onChange={(event) => setDescription(event.target.value)} placeholder="例如：米饭 100 克" value={description} />
          {fieldError ? <p id="meal-description-error" className="text-[13px] leading-5 text-destructive">{fieldError}</p> : null}
        </div>
        <Button className="h-11 w-full" disabled={status === 'submitting'} type="submit">{status === 'submitting' ? '正在分析…' : '开始分析'}</Button>
      </form>
      <div aria-live="polite" className="rounded-lg border bg-card p-4 text-sm text-muted-foreground" role="status">{progress || '输入“米饭 100 克”体验首个受控目录分析。'}</div>
      {status === 'completed' && report?.totals ? (
        <section aria-label="营养分析报告" className="space-y-3 rounded-lg border bg-card p-4">
          <h2 className="text-xl font-semibold">营养分析报告</h2>
          {report.items?.map((item) => <p key={`${item.name}-${item.grams}`} className="tabular-nums text-sm">{item.name} · {item.grams}g · {item.energy_kcal} kcal</p>)}
          <p className="tabular-nums text-base font-semibold">合计 {report.totals.energy_kcal} kcal</p>
          <p className="tabular-nums text-sm text-muted-foreground">蛋白质 {report.totals.protein_g}g · 脂肪 {report.totals.fat_g}g · 碳水 {report.totals.carbohydrate_g}g</p>
          <p className="text-[13px] leading-5 text-muted-foreground">{report.disclaimer}</p>
        </section>
      ) : null}
    </section>
  )
}
