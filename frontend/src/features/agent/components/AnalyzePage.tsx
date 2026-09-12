import { useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { Camera, ChevronDown, ChevronUp, CircleAlert, CircleCheck, ImagePlus, MessageSquareText, RefreshCw, ShieldCheck, Trash2, X } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { createAgentImageThread, createAgentThread, deleteAgentThread, getAgentThread, submitAgentInput, uploadAgentMealImage } from '../api/client.generated'
import { agentErrorResponseSchema, agentImageAcceptedResponseSchema, agentThreadSnapshotSchema, type AgentThreadSnapshot } from '../api/schemas.generated'
import type { SafeStreamStage } from '../api/stream'
import { useAgentEventStream } from '../stream/useAgentEventStream'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { confirmMealRecord, localMealTime, suggestedMealSlot, mealSlotLabels, mealMetadataFormSchema, type MealMetadataForm } from '@/features/records/api/client'
import { SafeProgressStages } from './SafeProgressStages'

const MAX_DESCRIPTION_LENGTH = 1000
const MAX_IMAGE_BYTES = 10 * 1024 * 1024
const ACCEPTED_IMAGE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

// The catalog remains authoritative and English-keyed. This UI-only map gives its bounded,
// known foods Chinese display names without translating unknown model or catalog text.
const CONTROLLED_FOOD_DISPLAY_NAMES: Readonly<Record<string, string>> = {
  rice: '米饭', 'cooked rice': '米饭', 'rice, white, long-grain, regular, cooked, enriched': '米饭',
  'chicken breast': '鸡胸肉', 'cooked chicken breast': '鸡胸肉', 'chicken breast, cooked, skinless': '鸡胸肉',
  'boiled egg': '水煮蛋', 'hard boiled egg': '水煮蛋', 'egg, whole, cooked, hard-boiled': '水煮蛋',
  broccoli: '西兰花', 'cooked broccoli': '西兰花', 'broccoli, cooked': '西兰花',
  potato: '土豆', 'boiled potato': '土豆', 'potatoes, boiled': '土豆',
  salmon: '三文鱼', 'cooked salmon': '三文鱼', 'salmon, atlantic, cooked': '三文鱼',
  'ground beef': '牛肉末', 'lean ground beef': '牛肉末', 'beef, ground, lean, cooked': '牛肉末',
}

type AnalysisStatus = 'idle' | 'validating-image' | 'uploading-image' | 'submitting' | 'deleting' | 'error' | 'completed'
type ReportItem = { item_id?: string; name: string; grams: string; energy_kcal?: string; protein_g?: string; fat_g?: string; carbohydrate_g?: string; is_estimated?: boolean }
type Candidate = { item_id: string; food_id: string; catalog_version: string; label: string }
type ClarificationQuestion = { item_id: string; field: 'grams' | 'food'; message: string; candidates: Candidate[] }
type AnalysisReport = {
  items?: ReportItem[]
  understood_items?: Array<{ item_id: string; name: string; grams: string | null }>
  questions?: ClarificationQuestion[]
  unaccounted_items?: string[]
  is_partial?: boolean
  totals?: Record<string, string>
  disclaimer?: string
  context_references?: string[]
}

const SAFE_UNACCOUNTED_ITEM_LABEL = '未能匹配的餐品'
const INTERNAL_ITEM_IDENTIFIER = /^(?:item|food)[_-]?\d+$/i

function displayFoodName(name: string): string {
  return CONTROLLED_FOOD_DISPLAY_NAMES[name.trim().toLocaleLowerCase()] ?? name
}

function displayFoodCandidate(label: string): string {
  const name = label.replace(/(?:（[^）]+）|\([^)]+\))$/, '').trim()
  const localizedName = displayFoodName(name)
  return localizedName === name ? label : localizedName
}

function displayUnaccountedItems(
  itemIds: readonly string[] | undefined,
  understoodItems: AnalysisReport['understood_items'],
): string {
  if (!itemIds?.length) return '请补充菜品和份量'
  const namesById = new Map(understoodItems?.map((item) => [item.item_id, item.name]))
  return itemIds.map((itemId) => {
    const name = namesById.get(itemId)?.trim()
    if (!name || name === itemId || INTERNAL_ITEM_IDENTIFIER.test(name)) {
      return SAFE_UNACCOUNTED_ITEM_LABEL
    }
    return displayFoodName(name)
  }).join('、')
}

async function safeErrorMessage(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => undefined)
  const parsed = agentErrorResponseSchema.safeParse(body)
  return parsed.success ? parsed.data.error.message : fallback
}

function recoveryContent(code: string | null | undefined) {
  if (code === 'OUTCOME_UNKNOWN') return { title: '正在确认本次请求状态', body: '为避免重复收费，系统不会自动再次提交。', action: '发起新的分析' }
  if (code === 'LIMIT_REACHED') return { title: '本次分析达到运行上限', body: '请开始新的分析，或改为文字描述。', action: '开始新的分析' }
  if (code === 'VISION_ANALYSIS_FAILED') return { title: '图片未能识别', body: '你可以改用文字描述这餐。', action: '改为文字描述这餐' }
  return { title: '本次餐食分析未完成', body: '请检查餐食描述后重新尝试。', action: '检查餐食描述' }
}

const macroSegments = [
  { key: 'protein_g', label: '蛋白质', factor: 4, color: 'var(--macro-protein)' },
  { key: 'fat_g', label: '脂肪', factor: 9, color: 'var(--macro-fat)' },
  { key: 'carbohydrate_g', label: '碳水', factor: 4, color: 'var(--macro-carbs)' },
] as const

function MacroComposition({ totals }: { totals: Record<string, string> }) {
  const energy = Number(totals.energy_kcal) || 0
  const values = macroSegments.map((macro) => ({ ...macro, value: Number(totals[macro.key]) || 0 }))
  const macroEnergy = values.reduce((sum, macro) => sum + macro.value * macro.factor, 0)
  let offset = 0
  const segments = values.map((macro) => {
    const share = macroEnergy > 0 ? macro.value * macro.factor / macroEnergy * 100 : 0
    const segment = { ...macro, share, offset }
    offset += share
    return segment
  })

  return <Card aria-label="营养素构成" className="gap-3 py-3 [--card-spacing:--spacing(3)]"><CardHeader className="pb-1"><h2 className="text-base font-semibold leading-6">营养素构成</h2></CardHeader><CardContent className="space-y-3"><div className="relative mx-auto size-40" role="img" aria-label={`总热量 ${energy} kcal；营养素估算供能占比：${segments.map((segment) => `${segment.label} ${segment.share.toFixed(1)}%`).join('，')}`}><svg aria-hidden="true" className="size-full -rotate-90" viewBox="0 0 200 200"><circle cx="100" cy="100" fill="none" r="72" stroke="var(--muted)" strokeWidth="26" />{segments.filter((segment) => segment.share > 0).map((segment) => <circle cx="100" cy="100" fill="none" key={segment.key} pathLength="100" r="72" stroke={segment.color} strokeDasharray={`${Math.max(0, segment.share - Math.min(1.2, segment.share / 2))} 100`} strokeDashoffset={-segment.offset} strokeWidth="26" />)}</svg><div aria-hidden="true" className="absolute inset-0 flex flex-col items-center justify-center gap-0.5"><span className="text-[13px] font-medium text-muted-foreground">总热量</span><span className="tabular-nums text-xl font-bold leading-6">{energy}</span><span className="text-[13px] text-muted-foreground">kcal</span></div></div><dl className="grid grid-cols-3 gap-2 text-center">{segments.map((segment) => <div key={segment.key}><dt className="flex items-center justify-center gap-1 text-[13px] font-semibold"><span aria-hidden="true" className="size-2 rounded-full" style={{ backgroundColor: segment.color }} />{segment.label}</dt><dd className="mt-0.5 tabular-nums text-[13px] font-semibold text-muted-foreground">{segment.value.toFixed(1)}g</dd></div>)}</dl></CardContent></Card>
}

export function AnalyzePage() {
  const textInputRef = useRef<HTMLTextAreaElement>(null)
  const submitButtonRef = useRef<HTMLButtonElement>(null)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const galleryInputRef = useRef<HTMLInputElement>(null)
  const { request, status: authenticationStatus } = useAuth()
  const [inputMode, setInputMode] = useState<'image' | 'text'>('image')
  const [description, setDescription] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [imageError, setImageError] = useState<string>()
  const [status, setStatus] = useState<AnalysisStatus>('idle')
  const [snapshot, setSnapshot] = useState<AgentThreadSnapshot>()
  const [progress, setProgress] = useState('')
  const [progressStage, setProgressStage] = useState<SafeStreamStage>()
  const [selectedImage, setSelectedImage] = useState<File>()
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string>()
  const [selectedCandidates, setSelectedCandidates] = useState<Record<string, string>>({})
  const [gramAnswers, setGramAnswers] = useState<Record<string, string>>({})
  const [expandedFoodItems, setExpandedFoodItems] = useState<Record<string, boolean>>({})
  const [correction, setCorrection] = useState('')
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [savedRecordId, setSavedRecordId] = useState<string>()
  const [savingRecord, setSavingRecord] = useState(false)
  const saveForm = useForm<MealMetadataForm>({ resolver: zodResolver(mealMetadataFormSchema), defaultValues: { mealSlot: suggestedMealSlot(), consumedAt: localMealTime() } })
  const resetSaveForm = saveForm.reset
  const saveLock = useRef(false)
  const [saveError, setSaveError] = useState('')
  const [followupError, setFollowupError] = useState('')
  const activeThreadRef = useRef<string | undefined>(undefined)
  const selectedMealSlot = saveForm.watch('mealSlot')

  const applySnapshot = useCallback(async (response: Response) => {
    const body = await response.json().catch(() => undefined)
    if (!response.ok) throw new Error('agent snapshot request failed')
    const next = agentThreadSnapshotSchema.parse(body)
    if (activeThreadRef.current !== next.thread_id) {
      setSavedRecordId(undefined)
      setExpandedFoodItems({})
      resetSaveForm({ mealSlot: suggestedMealSlot(), consumedAt: localMealTime() })
    }
    setSnapshot(next)
    setStatus(next.status === 'completed' ? 'completed' : next.status === 'retryable' || next.status === 'terminal' ? 'error' : 'idle')
    if (next.status === 'completed') { setProgress('分析报告已生成。'); setProgressStage('completed') }
    if (next.status === 'retryable' || next.status === 'terminal') { setProgress('分析未能完成。'); setProgressStage(next.status) }
    // A replayed waiting snapshot must not erase an answer the user is correcting.
    if (activeThreadRef.current !== next.thread_id || next.status !== 'waiting') {
      setSelectedCandidates({})
      setGramAnswers({})
      setFollowupError('')
    }
    activeThreadRef.current = next.thread_id
    const url = new URL(window.location.href)
    url.searchParams.set('thread', next.thread_id)
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
  }, [resetSaveForm])

  const refreshSnapshot = useCallback(async (threadId: string) => {
    await applySnapshot(await getAgentThread(request, threadId))
  }, [applySnapshot, request])

  useEffect(() => {
    if (authenticationStatus !== 'authenticated') return
    const threadId = new URL(window.location.href).searchParams.get('thread')
    if (!threadId || snapshot?.thread_id === threadId) return
    void getAgentThread(request, threadId).then(applySnapshot).catch(() => {
      const url = new URL(window.location.href)
      url.searchParams.delete('thread')
      window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
    })
  }, [applySnapshot, authenticationStatus, request, snapshot?.thread_id])
  useEffect(() => {
    if (!selectedImage || !ACCEPTED_IMAGE_TYPES.has(selectedImage.type) || typeof URL.createObjectURL !== 'function') {
      setImagePreviewUrl(undefined)
      return
    }
    const previewUrl = URL.createObjectURL(selectedImage)
    setImagePreviewUrl(previewUrl)
    return () => URL.revokeObjectURL(previewUrl)
  }, [selectedImage])
  useAgentEventStream({ threadId: snapshot?.thread_id, request, onEvent: (event) => {
    if (snapshot?.status === 'retryable' || snapshot?.status === 'terminal' || snapshot?.status === 'completed') return
    setProgressStage(event.stage)
  }, onInvalidEvent: () => { setStatus('error'); setProgressStage('retryable'); setProgress('分析进度暂时不可用，请重新尝试。') }, onSnapshot: applySnapshot })

  const isBusy = savingRecord || ['validating-image', 'uploading-image', 'submitting', 'deleting'].includes(status)
  const report = snapshot?.report as AnalysisReport | undefined
  const hasCalculatedItems = Boolean(report?.items?.length)
  const canDisplayReport = !report?.is_partial || hasCalculatedItems
  const waiting = snapshot?.status === 'waiting' && report?.questions?.length
  const recoveryCode = typeof snapshot?.recovery_code === 'string' ? snapshot.recovery_code : undefined
  const recovery = snapshot?.status === 'retryable' || snapshot?.status === 'terminal' ? recoveryContent(recoveryCode) : undefined

  function focusTextFallback() {
    setInputMode('text')
    window.requestAnimationFrame(() => textInputRef.current?.focus())
  }

  async function submitImage(file: File, existingThreadId?: string) {
    setImageError(undefined)
    setStatus('validating-image')
    setProgress('正在检查图片')
    if (!ACCEPTED_IMAGE_TYPES.has(file.type)) {
      setStatus('error')
      setImageError('这张图片无法安全分析。请选择 JPG、PNG 或 WebP 格式的餐食图片。')
      return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setStatus('error')
      setImageError('图片超过 10 MB 限制，请选择更小的文件。')
      return
    }
    try {
      const threadId = existingThreadId ?? agentThreadSnapshotSchema.parse(await (await createAgentImageThread(request)).json()).thread_id
      if (!existingThreadId) await refreshSnapshot(threadId)
      setStatus('uploading-image')
      setProgress('正在识别菜品')
      const response = await uploadAgentMealImage(request, threadId, file, `image-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`)
      if (!response.ok) {
        setStatus('error')
        setImageError(await safeErrorMessage(response, '图片上传未完成，请重新选择后重试。'))
        return
      }
      agentImageAcceptedResponseSchema.parse(await response.json())
      await refreshSnapshot(threadId)
    } catch {
      setStatus('error')
      setImageError('服务暂时不可用。系统未重复提交同一分析，请重新选择图片或改用文字描述。')
    }
  }

  function handleImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setSelectedImage(file)
    void submitImage(file)
  }

  function clearSelectedImage() {
    setSelectedImage(undefined)
    setImageError(undefined)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const inputText = description.trim()
    if (!inputText) { setFieldError('请先描述这餐吃了什么。'); return }
    if (description.length > MAX_DESCRIPTION_LENGTH) { setFieldError(`描述最多可输入 ${MAX_DESCRIPTION_LENGTH} 个字符。`); return }
    setFieldError(undefined)
    setProgress('正在提交描述')
    setProgressStage('perception')
    setStatus('submitting')
    try { await applySnapshot(await createAgentThread(request, { input_text: inputText })) } catch { setStatus('error'); setProgressStage('retryable'); setProgress('暂时无法完成分析，请检查描述后重试。') } finally { window.requestAnimationFrame(() => submitButtonRef.current?.focus()) }
  }

  function retryAnalysis() {
    if (!description.trim()) { setProgress('请重新描述餐食后再试。'); focusTextFallback(); return }
    textInputRef.current?.form?.requestSubmit()
  }

  async function submitFollowup(payload: Record<string, unknown>) {
    if (!snapshot) return
    setFollowupError('')
    setStatus('submitting')
    try {
      const response = await submitAgentInput(request, snapshot.thread_id, { kind: 'description', text: JSON.stringify(payload) })
      if (!response.ok) {
        setFollowupError(await safeErrorMessage(response, '这次补充没有生效，请检查后重试。'))
        setStatus(snapshot.status === 'completed' ? 'completed' : 'idle')
        return
      }
      await refreshSnapshot(snapshot.thread_id)
    } catch { setStatus(snapshot.status === 'completed' ? 'completed' : 'idle'); setFollowupError('这次补充没有生效，请检查后重试。') }
  }

  function submitClarification() {
    const answers: Record<string, Record<string, string>> = {}
    for (const question of report?.questions ?? []) {
      if (question.field === 'food' && selectedCandidates[question.item_id]) answers[question.item_id] = { candidate_id: selectedCandidates[question.item_id] }
      if (question.field === 'grams' && gramAnswers[question.item_id]?.trim()) answers[question.item_id] = { grams: gramAnswers[question.item_id].trim() }
    }
    if (Object.keys(answers).length !== (report?.questions?.length ?? 0)) { setFollowupError('请完成所有补充项；系统不会替你自动选择候选。'); return }
    void submitFollowup({ answers })
  }

  function submitCorrection() {
    const normalized = correction.trim()
    const target = report?.items?.find((item) => item.item_id && (normalized.includes(item.name) || normalized.includes(displayFoodName(item.name))))
    if (!target?.item_id) { setFollowupError('请写明要修改的食物和重量，或明确写“排除”。'); return }
    const label = normalized.includes(target.name) ? target.name : displayFoodName(target.name)
    // Preserve the entire weight suffix: digit extraction would turn 100kg into 100g.
    const grams = normalized.slice(normalized.indexOf(label) + label.length).trim().replace(/^(?:改为|改成|调整为)\s*/, '')
    if (!grams && !normalized.includes('排除')) { setFollowupError('请写明要修改的食物和重量，或明确写“排除”。'); return }
    void submitFollowup({ corrections: { [target.item_id]: normalized.includes('排除') ? { exclude: true } : { grams } } })
  }

  async function confirmDeletion() {
    if (!snapshot) return
    setStatus('deleting')
    setDeleteError('')
    try {
      const response = await deleteAgentThread(request, snapshot.thread_id)
      if (!response.ok) throw new Error('agent deletion request failed')
      setSnapshot(undefined); setDescription(''); setCorrection(''); setSelectedCandidates({}); setGramAnswers({})
      setProgressStage(undefined)
      setProgress('删除请求已提交：分析、事件流和本地缓存已关闭，数据将在 24 小时内清理。')
      setStatus('idle'); setDeleteOpen(false)
      const url = new URL(window.location.href); url.searchParams.delete('thread')
      window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
    } catch { setStatus('completed'); setDeleteError('无法提交删除请求。请检查网络后重试；当前分析仍保留。') }
  }

  function startNewImageAnalysis() {
    setSnapshot(undefined); setSelectedImage(undefined); setImageError(undefined); setProgress('请选择一张新的餐食图片。'); setStatus('idle')
    const url = new URL(window.location.href); url.searchParams.delete('thread')
    window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
  }

  async function confirmSave(values: MealMetadataForm) {
    if (!snapshot || saveLock.current) return
    saveLock.current = true
    setSavingRecord(true); setSaveError('')
    try {
      const record = await confirmMealRecord(request, snapshot.thread_id, `save-${crypto.randomUUID()}`, { mealSlot: values.mealSlot, consumedAt: new Date(values.consumedAt).toISOString() })
      setSavedRecordId(record.id)
    } catch { setSaveError('保存失败，请稍后重试。') } finally { saveLock.current = false; setSavingRecord(false) }
  }

  return (
    <section className="mx-auto w-full max-w-xl space-y-4 pb-4">
      <Card><CardHeader><CardTitle>{inputMode === 'image' ? '上传餐食图片' : '文字描述餐食'}</CardTitle><CardDescription>{inputMode === 'image' ? '选择一张餐食图片，系统会识别菜品并在需要时向你确认。' : '用文字描述这一餐吃了什么，越详细估算越准确。'}</CardDescription></CardHeader><CardContent className="space-y-3">
        {inputMode === 'image' ? <>
          {imagePreviewUrl ? <div className="relative overflow-hidden rounded-lg border border-border"><img alt="已选择的餐食图片" className="aspect-[4/3] w-full object-cover" src={imagePreviewUrl} /><Button aria-label="移除已选图片" className="absolute right-2 top-2 size-8 rounded-full bg-background/90 p-0 shadow-sm hover:bg-background" disabled={isBusy} onClick={clearSelectedImage} type="button" variant="secondary"><X aria-hidden="true" className="size-4" /></Button></div> : <div className="grid grid-cols-2 gap-2"><Button className="h-11" disabled={isBusy} onClick={() => cameraInputRef.current?.click()} type="button"><Camera aria-hidden="true" className="size-5" />拍照</Button><Button className="h-11" disabled={isBusy} onClick={() => galleryInputRef.current?.click()} type="button" variant="outline"><ImagePlus aria-hidden="true" className="size-5" />从相册选择</Button></div>}
          <input accept="image/jpeg,image/png,image/webp" aria-describedby={imageError ? 'meal-image-error' : 'meal-image-help'} aria-label="拍照上传" capture="environment" className="sr-only" disabled={isBusy} onChange={handleImageChange} ref={cameraInputRef} tabIndex={-1} type="file" />
          <input accept="image/jpeg,image/png,image/webp" aria-describedby={imageError ? 'meal-image-error' : 'meal-image-help'} aria-label="从相册选择上传" className="sr-only" disabled={isBusy} onChange={handleImageChange} ref={galleryInputRef} tabIndex={-1} type="file" />
          {!imagePreviewUrl ? <p id="meal-image-help" className="text-[13px] leading-5 text-muted-foreground">支持 JPG、PNG、WebP，最大 10 MB。相机不可用时仍可从相册选择。</p> : null}
          {imageError ? <Alert id="meal-image-error" variant="destructive"><CircleAlert aria-hidden="true" /><AlertTitle>这张图片无法安全分析</AlertTitle><AlertDescription>{imageError}</AlertDescription></Alert> : null}
          <details className="rounded-lg border border-border p-3 text-[13px] leading-5 text-muted-foreground"><summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-foreground"><ShieldCheck aria-hidden="true" className="size-5" />仅用于本次分析；完成或超时后删除。</summary><p className="pt-2">图片会由第三方视觉模型处理；本服务会在本次分析完成或超时后删除临时副本。</p></details>
          <Button className="h-9 w-full" disabled={isBusy} onClick={focusTextFallback} type="button" variant="outline"><MessageSquareText aria-hidden="true" className="size-4" />改为文字描述这餐</Button>
        </> : <form className="space-y-3" noValidate onSubmit={handleSubmit}><div className="space-y-2"><Label htmlFor="meal-description">餐食描述</Label><textarea aria-describedby={fieldError ? 'meal-description-error' : undefined} aria-invalid={Boolean(fieldError)} className="min-h-28 w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 text-base leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50" disabled={isBusy} id="meal-description" onChange={(event) => setDescription(event.target.value)} placeholder="例如：米饭 100 克" ref={textInputRef} value={description} />{fieldError ? <p id="meal-description-error" className="text-[13px] leading-5 text-destructive">{fieldError}</p> : null}</div><Button className="h-11 w-full" disabled={isBusy} ref={submitButtonRef} type="submit">{status === 'submitting' ? '正在分析…' : '开始分析'}</Button><Button className="h-9 w-full" disabled={isBusy} onClick={() => setInputMode('image')} type="button" variant="outline"><ImagePlus aria-hidden="true" className="size-4" />改为上传图片</Button></form>}
      </CardContent></Card>
      {progressStage ? <SafeProgressStages onRetry={retryAnalysis} stage={progressStage} /> : <Alert aria-live="polite" role="status"><RefreshCw aria-hidden="true" className={isBusy ? 'size-4 animate-spin motion-reduce:animate-none' : 'size-4'} /><AlertTitle>{progress || '等待分析'}</AlertTitle><AlertDescription>阶段状态只显示安全摘要，最终结果以报告卡片为准。</AlertDescription></Alert>}
      {recovery ? <Alert variant={recoveryCode === 'OUTCOME_UNKNOWN' ? 'default' : 'destructive'}><CircleAlert aria-hidden="true" /><AlertTitle>{recovery.title}</AlertTitle><AlertDescription className="space-y-3"><p>{recovery.body}</p>{recoveryCode === 'OUTCOME_UNKNOWN' ? <Button className="h-11 w-full" onClick={startNewImageAnalysis} type="button" variant="outline">{recovery.action}</Button> : <Button className="h-11 w-full" onClick={focusTextFallback} type="button" variant="outline">{recovery.action}</Button>}</AlertDescription></Alert> : null}
      {waiting ? <Card aria-label="集中补充信息" className="space-y-3"><CardHeader><h2 className="flex items-center gap-2 text-xl font-semibold"><CircleAlert aria-hidden="true" className="size-5" />需要补充的信息</h2></CardHeader><CardContent className="space-y-3">{report.understood_items?.length ? <div className="space-y-1 text-sm"><h3 className="font-semibold">已理解的项目</h3>{report.understood_items.map((item) => <p key={item.item_id}>{displayFoodName(item.name)}{item.grams ? ` · ${item.grams}g` : ' · 份量待确认'}</p>)}</div> : null}{report.questions?.map((question) => <fieldset className="space-y-2" key={`${question.item_id}-${question.field}`}><legend className="text-sm font-medium">{question.message}</legend>{question.field === 'grams' ? <div className="space-y-1"><Label htmlFor={`${question.item_id}-grams`}>克数</Label><Input className="h-11" id={`${question.item_id}-grams`} aria-describedby="meal-weight-help" onChange={(event) => setGramAnswers((current) => ({ ...current, [question.item_id]: event.target.value }))} placeholder="例如：100 克" value={gramAnswers[question.item_id] ?? ''} /></div> : null}{question.field === 'food' ? <div className="grid gap-2">{question.candidates.slice(0, 3).map((candidate) => <button aria-pressed={selectedCandidates[question.item_id] === candidate.food_id} className="min-h-11 cursor-pointer rounded-lg border border-input px-3 py-2 text-left text-sm transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:border-primary aria-pressed:bg-primary/10" key={candidate.food_id} onClick={() => setSelectedCandidates((current) => ({ ...current, [question.item_id]: candidate.food_id }))} type="button">{displayFoodCandidate(candidate.label)}</button>)}</div> : null}</fieldset>)}<p className="text-[13px] text-muted-foreground" id="meal-weight-help">数字默认克；支持 g、kg、克、公斤、千克、公克、斤、市斤、两、市两。1 市斤＝500 克，1 市两＝50 克；每项最多 2000 克。</p>{followupError ? <p className="text-sm text-destructive" role="alert">{followupError}</p> : null}<Button className="h-11 w-full" disabled={isBusy} onClick={submitClarification} type="button">提交补充信息</Button></CardContent></Card> : null}
      {report?.is_partial ? <Alert><CircleAlert aria-hidden="true" /><AlertTitle>{hasCalculatedItems ? '当前总量不完整' : '无法生成营养报告'}</AlertTitle><AlertDescription>{hasCalculatedItems ? <>以下项目未计入总量：{displayUnaccountedItems(report.unaccounted_items, report.understood_items)}。</> : <>未匹配菜品：{displayUnaccountedItems(report.unaccounted_items, report.understood_items)}。</>} 请补充信息或改用目录中的菜品后重新分析。</AlertDescription></Alert> : null}
      {snapshot?.status === 'completed' && report?.totals && canDisplayReport ? <div className="space-y-4">
        <Card aria-label="估算总热量" className="gap-3 py-3 [--card-spacing:--spacing(3)]"><CardContent className="px-4"><p className="text-sm font-medium text-muted-foreground">{report.is_partial ? '已计入项目的估算总热量' : '估算总热量'}</p><p className="mt-0.5 flex items-baseline gap-1 tabular-nums"><span className="text-3xl font-bold leading-9 text-foreground">{report.totals.energy_kcal}</span><span className="text-[13px] font-medium text-muted-foreground">kcal</span></p><p className="mt-1 text-[13px] leading-5 text-muted-foreground">数值由受控营养目录计算，实际份量可能有偏差。</p></CardContent></Card>
        <Card aria-label="食物明细"><CardHeader className="pb-2"><h2 className="text-base font-semibold leading-6">食物明细</h2></CardHeader><CardContent className="space-y-2">{report.items?.map((item) => {
          const foodKey = item.item_id ?? `${item.name}-${item.grams}`
          const expanded = expandedFoodItems[foodKey] === true
          return <article key={foodKey}><button aria-expanded={expanded} className={`flex w-full items-center justify-between rounded-lg border border-border p-2.5 text-left transition-colors hover:bg-muted/50 ${expanded ? 'rounded-b-none bg-muted/50' : ''}`} onClick={() => setExpandedFoodItems((current) => ({ ...current, [foodKey]: !expanded }))} type="button"><div className="min-w-0 flex-1"><h3 className="truncate text-[14px] font-medium leading-5 text-foreground">{displayFoodName(item.name)}</h3><p className="mt-0.5 tabular-nums text-[12px] leading-5 text-muted-foreground">{item.grams}g · {item.energy_kcal} kcal</p>{item.is_estimated ? <p className="text-[11px] leading-4 text-muted-foreground">估算重量，可能与实际份量存在偏差。</p> : null}</div><div className="ml-2 flex shrink-0 items-center gap-2">{item.is_estimated ? <Badge className="text-[10px] font-medium" variant="outline">估算重量</Badge> : null}<Badge className="text-[10px] font-medium" variant="outline">蛋白 {item.protein_g ?? '—'}g</Badge>{expanded ? <ChevronUp aria-hidden="true" className="size-4 text-muted-foreground" /> : <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground" />}</div></button>{expanded ? <div className="grid grid-cols-3 gap-2 rounded-b-lg border-x border-b border-border px-2.5 py-2 text-center"><div><p className="text-[11px] text-muted-foreground">蛋白质</p><p className="tabular-nums text-[13px] font-semibold text-foreground">{item.protein_g ?? '—'}g</p></div><div><p className="text-[11px] text-muted-foreground">脂肪</p><p className="tabular-nums text-[13px] font-semibold text-foreground">{item.fat_g ?? '—'}g</p></div><div><p className="text-[11px] text-muted-foreground">碳水</p><p className="tabular-nums text-[13px] font-semibold text-foreground">{item.carbohydrate_g ?? '—'}g</p></div></div> : null}</article>
        })}<p className="pt-1 text-[13px] leading-5 text-muted-foreground">份量为估算值，可在下方修正</p></CardContent></Card>
        <MacroComposition totals={report.totals} />
        {!report.is_partial ? <Card aria-label="保存餐食记录" className="gap-3 py-3 [--card-spacing:--spacing(3)]"><CardContent className="px-4">{savedRecordId ? <div className="space-y-2"><p className="text-sm font-medium text-primary">已保存</p><Link className="inline-flex h-11 w-full items-center justify-center rounded-lg border border-input text-sm font-medium" to={`/app/records/${savedRecordId}`}>查看记录</Link></div> : <form className="space-y-3" id="save-meal-record" onSubmit={(event) => void saveForm.handleSubmit(confirmSave)(event)} noValidate><fieldset className="space-y-3" disabled={savingRecord}><div className="space-y-2"><Label className="text-[13px]" id="save-meal-slot-label">餐次</Label><input type="hidden" {...saveForm.register('mealSlot')} /><div aria-labelledby="save-meal-slot-label" className="grid grid-cols-4 gap-1 rounded-2xl bg-muted p-1" role="radiogroup">{Object.entries(mealSlotLabels).map(([value, label]) => <button aria-checked={selectedMealSlot === value} className="h-10 rounded-xl text-sm font-semibold text-foreground transition-colors aria-checked:bg-primary aria-checked:text-primary-foreground" key={value} onClick={() => saveForm.setValue('mealSlot', value as MealMetadataForm['mealSlot'], { shouldDirty: true, shouldValidate: true })} role="radio" type="button">{label}</button>)}</div></div><div className="space-y-1"><Label className="text-[13px]" htmlFor="save-consumed-at">用餐时间</Label><Input className="h-11" id="save-consumed-at" type="datetime-local" max={localMealTime()} {...saveForm.register('consumedAt')} aria-invalid={Boolean(saveForm.formState.errors.consumedAt)} aria-describedby="save-time-help" /><p className="text-[13px] text-muted-foreground" id="save-time-help">按当前设备时区填写；补录时请确认餐次和时间。</p></div>{saveForm.formState.errors.consumedAt ? <p className="text-sm text-destructive" role="alert">{saveForm.formState.errors.consumedAt.message}</p> : null}</fieldset>{saveError ? <p className="mt-2 text-sm text-destructive" role="alert">{saveError}</p> : null}</form>}</CardContent></Card> : null}
        <Card aria-label="修正项目区域" className="gap-3 py-3 [--card-spacing:--spacing(3)]"><CardContent className="space-y-2 px-4">{followupError ? <p className="text-sm text-destructive" role="alert">{followupError}</p> : null}<Label className="text-[13px]" htmlFor="meal-correction">修正或排除项目</Label><div className="flex gap-2"><Input className="h-11 flex-1" id="meal-correction" onChange={(event) => setCorrection(event.target.value)} placeholder="例如：米饭改为 150 克，或排除米饭" value={correction} /><Button className="h-11 shrink-0 px-4" disabled={isBusy} onClick={submitCorrection} type="button" variant="outline">应用修正</Button></div></CardContent></Card>
        <div aria-label="报告操作" className="space-y-3"><p className="text-center text-[13px] leading-5 text-muted-foreground">{report.disclaimer || '本结果仅供一般饮食参考，不替代医疗建议。'}</p>{!report.is_partial && !savedRecordId ? <Button className="h-12 w-full text-base" disabled={savingRecord} form="save-meal-record" type="submit"><CircleCheck aria-hidden="true" className="size-5" />{savingRecord ? '正在保存…' : '确认并保存'}</Button> : null}<div className="grid grid-cols-2 gap-2"><Button className="h-11 text-base" disabled={isBusy} onClick={startNewImageAnalysis} type="button" variant="outline"><RefreshCw aria-hidden="true" className="size-5" />重新分析</Button><Button className="h-11 border-destructive/30 text-base text-destructive hover:bg-destructive/10 hover:text-destructive" disabled={status === 'deleting'} onClick={() => { setDeleteError(''); setDeleteOpen(true) }} type="button" variant="outline"><Trash2 aria-hidden="true" className="size-5" />删除</Button></div></div>
      </div> : null}
      <AlertDialog open={deleteOpen} onOpenChange={(open) => { if (status !== 'deleting') setDeleteOpen(open) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>删除这次分析？</AlertDialogTitle><AlertDialogDescription>这会停止当前分析和事件流。数据将在 24 小时内删除。此操作无法撤销。</AlertDialogDescription></AlertDialogHeader>{deleteError ? <p className="text-sm text-destructive" role="alert">{deleteError}</p> : null}<AlertDialogFooter><AlertDialogCancel disabled={status === 'deleting'}>保留这次分析</AlertDialogCancel><AlertDialogAction disabled={status === 'deleting'} onClick={() => void confirmDeletion()} variant="destructive">{status === 'deleting' ? '正在提交删除…' : '确认删除'}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    </section>
  )
}
