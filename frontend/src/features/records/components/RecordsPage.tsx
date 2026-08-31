import { NotebookText } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/useAuth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { listMealRecords, type MealRecord } from '../api/client'

function dateLabel(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long' }).format(new Date(value)) }
function timeLabel(value: string) { return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(value)) }

export function RecordsPage() {
  const { request } = useAuth(); const headingRef = useRef<HTMLHeadingElement>(null)
  const [records, setRecords] = useState<MealRecord[]>(); const [error, setError] = useState('')
  useEffect(() => { headingRef.current?.focus(); void listMealRecords(request).then(setRecords).catch(() => setError('暂时无法加载记录，请稍后重试。')) }, [request])
  const groups = (records ?? []).reduce<Record<string, MealRecord[]>>((current, record) => { const key = dateLabel(record.consumed_at); (current[key] ??= []).push(record); return current }, {})
  return <section className="mx-auto w-full max-w-xl space-y-4 pb-4"><div><h1 ref={headingRef} tabIndex={-1} className="text-[28px] font-bold leading-9 tracking-tight">记录</h1><p className="mt-2 text-[15px] leading-6 text-muted-foreground">查看你已确认保存的餐食。</p></div>{error ? <Alert variant="destructive"><AlertTitle>加载失败</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}{records === undefined && !error ? <p className="text-sm text-muted-foreground">正在加载记录…</p> : null}{records?.length === 0 ? <Card><CardContent className="space-y-3 py-8 text-center"><NotebookText aria-hidden="true" className="mx-auto size-8 text-muted-foreground" /><h2 className="text-xl font-semibold">还没有已保存的餐食</h2><p className="text-sm text-muted-foreground">完成一餐分析后，确认保存即可在这里查看。</p><Link className="inline-flex h-11 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground" to="/app/analyze">去分析一餐</Link></CardContent></Card> : null}{Object.entries(groups).map(([day, items]) => <div className="space-y-2" key={day}><h2 className="text-sm font-semibold text-muted-foreground">{day}</h2>{items.map((record) => <Link className="block" key={record.id} to={`/app/records/${record.id}`}><Card><CardContent className="flex items-center justify-between gap-3 py-3"><div><p className="font-medium">{record.items.map((item) => item.display_name).join('、')}</p><p className="mt-1 text-[13px] text-muted-foreground">{timeLabel(record.consumed_at)} · 已保存</p></div><p className="tabular-nums text-sm font-semibold">{record.energy_kcal} kcal</p></CardContent></Card></Link>)}</div>)}</section>
}
