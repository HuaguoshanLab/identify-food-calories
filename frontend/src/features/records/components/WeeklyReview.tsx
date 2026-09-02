import { CircleAlert, RotateCw } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { WeeklyReviewResponse } from '../api/weeklyReview'

const dateFormatter = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric' })
const disclaimer = '仅基于已记录数据，供一般饮食参考，不构成医疗建议。'

export function WeeklyReview({ review, onRefresh, isRefreshing }: { review: WeeklyReviewResponse; onRefresh: () => void; isRefreshing: boolean }) {
  const range = `${dateFormatter.format(new Date(`${review.week_start}T00:00:00`))}—${dateFormatter.format(new Date(`${review.week_end}T00:00:00`))}`
  return <section aria-labelledby="weekly-review-title" className="space-y-3"><h2 className="text-xl font-semibold leading-7" id="weekly-review-title">周复盘</h2><Card><CardHeader><CardTitle className="text-base">{range}</CardTitle></CardHeader><CardContent className="space-y-4"><p className="tabular-nums text-sm text-muted-foreground">已记录 {review.coverage_days} 天 · {review.meal_count} 餐</p><p className="tabular-nums text-sm">{review.totals.energy_kcal} kcal</p><ReviewState review={review} onRefresh={onRefresh} isRefreshing={isRefreshing} /></CardContent></Card></section>
}

function ReviewState({ review, onRefresh, isRefreshing }: { review: WeeklyReviewResponse; onRefresh: () => void; isRefreshing: boolean }) {
  if (review.status === 'success') return <div aria-live="polite" className="space-y-3"><ul aria-label="一般饮食参考" className="list-disc space-y-2 pl-5 text-sm leading-6">{review.suggestions.map((suggestion) => <li key={suggestion}>{suggestion}</li>)}</ul><p className="text-sm text-muted-foreground">{disclaimer}</p></div>
  if (review.status === 'insufficient_coverage') return <Alert><CircleAlert aria-hidden="true" /><AlertTitle>记录仍不足以生成建议</AlertTitle><AlertDescription>继续记录更多餐食后，再查看本周复盘。</AlertDescription></Alert>
  if (review.status === 'safety_abstain') return <Alert><CircleAlert aria-hidden="true" /><AlertTitle>暂不提供本周建议</AlertTitle><AlertDescription>当前只展示已记录的客观汇总，不生成饮食建议。</AlertDescription></Alert>
  return <Alert variant="destructive"><CircleAlert aria-hidden="true" /><AlertTitle>暂时无法生成周复盘</AlertTitle><AlertDescription className="space-y-3"><p>请检查网络后重新生成。</p><Button className="h-11 w-full" disabled={isRefreshing} onClick={onRefresh} type="button" variant="outline"><RotateCw aria-hidden="true" />{isRefreshing ? '正在重新生成…' : '重新生成'}</Button></AlertDescription></Alert>
}
