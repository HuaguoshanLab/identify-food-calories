import { useEffect, useRef, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

const MAX_DESCRIPTION_LENGTH = 1000

type AnalysisStatus = 'idle' | 'submitting' | 'unavailable' | 'error'

type AnalyzePageProps = {
  /**
   * The temporary seam keeps this view independent from the future OpenAPI client. Until that
   * client exists, the default rejects explicitly instead of making an unobservable request.
   */
  submitAnalysis?: (description: string) => Promise<'unavailable'>
}

async function unavailableSubmission(): Promise<'unavailable'> {
  return 'unavailable'
}

function statusMessage(status: AnalysisStatus) {
  switch (status) {
    case 'submitting':
      return '正在提交描述…'
    case 'error':
      return '暂时无法提交分析，请稍后重试。'
    case 'idle':
    case 'unavailable':
      return '分析能力正在接线中，暂时无法提交。'
  }
}

export function AnalyzePage({ submitAnalysis = unavailableSubmission }: AnalyzePageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)
  const [description, setDescription] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [status, setStatus] = useState<AnalysisStatus>('unavailable')

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedDescription = description.trim()

    if (!trimmedDescription) {
      setFieldError('请先描述这餐吃了什么。')
      setStatus('idle')
      return
    }
    if (description.length > MAX_DESCRIPTION_LENGTH) {
      setFieldError(`描述最多可输入 ${MAX_DESCRIPTION_LENGTH} 个字符。`)
      setStatus('idle')
      return
    }

    setFieldError(undefined)
    setStatus('submitting')
    try {
      await submitAnalysis(trimmedDescription)
      // This shell deliberately has no result schema yet, so a resolved test seam cannot imply
      // that an analysis report exists. The real controller replaces this path with typed data.
      setStatus('unavailable')
    } catch {
      setStatus('error')
    }
  }

  const isSubmitting = status === 'submitting'

  return (
    <section className="mx-auto w-full max-w-xl space-y-6">
      <div className="space-y-2">
        <h1 ref={headingRef} tabIndex={-1} className="text-[28px] font-bold leading-9 tracking-tight">
          描述这餐吃了什么
        </h1>
        <p className="text-[15px] leading-6 text-muted-foreground">
          写下食物和大致份量；完整信息接通后会直接进入分析，不需要额外确认步骤。
        </p>
      </div>

      <form className="space-y-4" noValidate onSubmit={handleSubmit}>
        <div className="space-y-2">
          <Label htmlFor="meal-description">餐食描述</Label>
          <textarea
            aria-describedby={fieldError ? 'meal-description-error' : undefined}
            aria-invalid={Boolean(fieldError)}
            className="min-h-28 w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isSubmitting}
            id="meal-description"
            onChange={(event) => setDescription(event.target.value)}
            placeholder="例如：一碗番茄鸡蛋面，约一人份"
            value={description}
          />
          {fieldError ? (
            <p id="meal-description-error" className="text-[13px] leading-5 text-destructive">
              {fieldError}
            </p>
          ) : null}
        </div>

        <Button className="h-11 w-full" disabled={isSubmitting} type="submit">
          {isSubmitting ? '正在提交…' : '开始分析'}
        </Button>
      </form>

      <div aria-live="polite" className="rounded-lg border bg-card p-4 text-sm text-muted-foreground" role="status">
        {statusMessage(status)}
      </div>
    </section>
  )
}
