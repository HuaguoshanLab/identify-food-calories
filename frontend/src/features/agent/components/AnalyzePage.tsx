import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { CircleAlert, CircleCheck } from 'lucide-react'

import { useAuth } from '@/auth/useAuth'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { agentThreadSnapshotSchema, type AgentThreadSnapshot } from '../api/schemas.generated'
import { useAgentEventStream } from '../stream/useAgentEventStream'

const MAX_DESCRIPTION_LENGTH = 1000
type AnalysisStatus = 'idle' | 'submitting' | 'error' | 'completed'

type ReportItem = {
  item_id?: string
  name: string
  grams: string
  energy_kcal?: string
  protein_g?: string
  fat_g?: string
  carbohydrate_g?: string
}
type Candidate = { item_id: string; food_id: string; catalog_version: string; label: string }
type ClarificationQuestion = { item_id: string; field: 'grams' | 'food'; message: string; candidates: Candidate[] }
type AnalysisReport = {
  items?: ReportItem[]
  understood_items?: Array<{ item_id: string; name: string; grams: string | null }>
  questions?: ClarificationQuestion[]
  unaccounted_items?: string[]
  is_partial?: boolean
  waiting_input?: boolean
  totals?: Record<string, string>
  disclaimer?: string
}

export function AnalyzePage() {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const { request, status: authenticationStatus } = useAuth()
  const [description, setDescription] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [status, setStatus] = useState<AnalysisStatus>('idle')
  const [snapshot, setSnapshot] = useState<AgentThreadSnapshot>()
  const [progress, setProgress] = useState('')
  const [selectedCandidates, setSelectedCandidates] = useState<Record<string, string>>({})
  const [gramAnswers, setGramAnswers] = useState<Record<string, string>>({})
  const [correction, setCorrection] = useState('')

  const applySnapshot = useCallback(async (response: Response) => {
    const body = await response.json().catch(() => undefined)
    if (!response.ok) throw new Error('agent snapshot request failed')
    const next = agentThreadSnapshotSchema.parse(body)
    setSnapshot(next)
    setStatus(next.status === 'completed' ? 'completed' : 'idle')
    setSelectedCandidates({})
    setGramAnswers({})
    const url = new URL(window.location.href)
    url.searchParams.set('thread', next.thread_id)
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
  }, [])

  useEffect(() => { headingRef.current?.focus() }, [])
  useEffect(() => {
    if (authenticationStatus !== 'authenticated') return
    const threadId = new URL(window.location.href).searchParams.get('thread')
    if (!threadId || snapshot?.thread_id === threadId) return
    void request(`/agent/threads/${encodeURIComponent(threadId)}`)
      .then(applySnapshot)
      .catch(() => {
        // A deleted or foreign URL thread stays undisclosed; discard only its local reference.
        const url = new URL(window.location.href)
        url.searchParams.delete('thread')
        window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
      })
  }, [applySnapshot, authenticationStatus, request, snapshot?.thread_id])
  useAgentEventStream({
    threadId: snapshot?.thread_id,
    request,
    onEvent: (event) => setProgress(event.summary),
    onSnapshot: applySnapshot,
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
      await applySnapshot(response)
    } catch {
      setStatus('error')
      setProgress('暂时无法完成分析，请检查描述后重试。')
    }
  }

  async function refreshSnapshot(threadId: string) {
    const response = await request(`/agent/threads/${encodeURIComponent(threadId)}`)
    await applySnapshot(response)
  }

  async function submitFollowup(payload: Record<string, unknown>) {
    if (!snapshot) return
    setStatus('submitting')
    try {
      const response = await request(`/agent/threads/${encodeURIComponent(snapshot.thread_id)}/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'description', text: JSON.stringify(payload) }),
      })
      if (!response.ok) throw new Error('agent followup request failed')
      await refreshSnapshot(snapshot.thread_id)
    } catch {
      setStatus('error')
      setProgress('这次补充没有生效，请检查后重试。')
    }
  }

  function submitClarification() {
    const answers: Record<string, Record<string, string>> = {}
    for (const question of report?.questions ?? []) {
      if (question.field === 'food' && selectedCandidates[question.item_id]) {
        answers[question.item_id] = { candidate_id: selectedCandidates[question.item_id] }
      }
      if (question.field === 'grams' && gramAnswers[question.item_id]?.trim()) {
        answers[question.item_id] = { grams: gramAnswers[question.item_id].trim() }
      }
    }
    if (Object.keys(answers).length !== (report?.questions?.length ?? 0)) {
      setProgress('请完成所有补充项；系统不会替你自动选择候选。')
      return
    }
    void submitFollowup({ answers })
  }

  function submitCorrection() {
    const normalized = correction.trim()
    const target = report?.items?.find((item) => normalized.includes(item.name) && item.item_id)
    const grams = normalized.match(/(?<!\d)(\d+(?:\.\d+)?)\s*(?:g|克)?/i)?.[1]
    if (!target?.item_id || (!grams && !normalized.includes('排除'))) {
      setProgress('请写明要修改的食物和克数，或明确写“排除”。')
      return
    }
    void submitFollowup({ corrections: { [target.item_id]: normalized.includes('排除') ? { exclude: true } : { grams } } })
  }

  const report = snapshot?.report as AnalysisReport | undefined
  const waiting = snapshot?.status === 'waiting' && report?.questions?.length

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
      {waiting ? (
        <section aria-label="集中补充信息" className="space-y-3 rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2">
            <CircleAlert aria-hidden="true" className="size-5 text-muted-foreground" />
            <h2 className="text-xl font-semibold">需要补充的信息</h2>
          </div>
          {report.understood_items?.length ? <div className="space-y-1 text-sm"><h3 className="font-semibold">已理解的项目</h3>{report.understood_items.map((item) => <p key={item.item_id}>{item.name}{item.grams ? ` · ${item.grams}g` : ' · 份量待确认'}</p>)}</div> : null}
          {report.questions?.map((question) => (
            <fieldset className="space-y-2" key={`${question.item_id}-${question.field}`}>
              <legend className="text-sm font-medium">{question.message}</legend>
              {question.field === 'grams' ? <input aria-label={`${question.item_id} 克数`} className="h-11 w-full rounded-lg border border-input bg-transparent px-3 text-base" inputMode="decimal" onChange={(event) => setGramAnswers((current) => ({ ...current, [question.item_id]: event.target.value }))} placeholder="例如：100 克" value={gramAnswers[question.item_id] ?? ''} /> : null}
              {question.field === 'food' ? <div className="grid gap-2">{question.candidates.map((candidate) => <button aria-pressed={selectedCandidates[question.item_id] === candidate.food_id} className="min-h-11 rounded-lg border border-input px-3 py-2 text-left text-sm focus-visible:ring-3 focus-visible:ring-ring/50" key={candidate.food_id} onClick={() => setSelectedCandidates((current) => ({ ...current, [question.item_id]: candidate.food_id }))} type="button">{candidate.label}</button>)}</div> : null}
            </fieldset>
          ))}
          <Button className="h-11 w-full" disabled={status === 'submitting'} onClick={submitClarification} type="button">提交补充信息</Button>
        </section>
      ) : null}
      {report?.is_partial ? <p className="flex items-center gap-2 rounded-lg border border-input bg-card p-3 text-sm text-muted-foreground"><CircleAlert aria-hidden="true" className="size-5" />部分项目未计入总量：{report.unaccounted_items?.join('、') || '请查看待补充项'}</p> : null}
      {snapshot?.status === 'completed' && report?.totals ? (
        <section aria-label="营养分析报告" className="space-y-3 rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2"><CircleCheck aria-hidden="true" className="size-5 text-muted-foreground" /><h2 className="text-xl font-semibold">营养分析报告</h2></div>
          {report.items?.map((item) => <p key={`${item.name}-${item.grams}`} className="tabular-nums text-sm">{item.name} · {item.grams}g · {item.energy_kcal} kcal</p>)}
          <p className="tabular-nums text-base font-semibold">合计 {report.totals.energy_kcal} kcal</p>
          <p className="tabular-nums text-sm text-muted-foreground">蛋白质 {report.totals.protein_g}g · 脂肪 {report.totals.fat_g}g · 碳水 {report.totals.carbohydrate_g}g</p>
          <p className="text-[13px] leading-5 text-muted-foreground">{report.disclaimer}</p>
          <div className="space-y-2 border-t pt-3">
            <Label htmlFor="meal-correction">修正或排除项目</Label>
            <input className="h-11 w-full rounded-lg border border-input bg-transparent px-3 text-base" id="meal-correction" onChange={(event) => setCorrection(event.target.value)} placeholder="例如：米饭改为 150 克，或排除米饭" value={correction} />
            <Button className="h-11 w-full" disabled={status === 'submitting'} onClick={submitCorrection} type="button">应用修正</Button>
          </div>
        </section>
      ) : null}
    </section>
  )
}
