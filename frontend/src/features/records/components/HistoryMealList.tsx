import { mealSlotLabels } from '../api/mealMetadata'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { DashboardHistoryPage } from '../api/dashboard'
const dateFormatter = new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long' }); const timeFormatter = new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }); const energy = (value: string) => new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(Number(value))
export function HistoryMealList({ isLoadingMore, onLoadMore, page }: { isLoadingMore: boolean; onLoadMore: (cursor: string) => void; page: DashboardHistoryPage }) { return <section aria-labelledby="history-title" className="space-y-4"><h2 className="text-base font-semibold leading-6" id="history-title">历史记录</h2>{page.groups.length === 0 ? <Card><CardContent className="py-8 text-center"><p className="font-medium">还没有已保存的餐食</p><p className="mt-1 text-sm text-muted-foreground">完成一餐分析后，确认保存即可在这里查看。</p></CardContent></Card> : page.groups.map((group) => <div className="space-y-2" key={group.consumed_local_date}><h3 className="text-sm font-semibold text-muted-foreground">{dateFormatter.format(new Date(`${group.consumed_local_date}T00:00:00`))}</h3>{group.items.map((record) => <Link className="block rounded-md focus-visible:outline-none" key={record.id} to={`/app/records/${record.id}`}><Card className="rounded-2xl py-4 shadow-none transition-colors hover:bg-muted/40"><CardContent className="flex items-center gap-2 px-2.5 min-[375px]:gap-3">
  <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent text-sm font-semibold text-foreground">{record.meal_slot ? mealSlotLabels[record.meal_slot][0] : '餐'}</span>
  <span className="min-w-0 flex-1">
    <span className="flex flex-wrap items-center gap-1.5"><span className="text-[15px] font-semibold tabular-nums">{timeFormatter.format(new Date(record.consumed_at))}</span><Badge className="min-h-5 px-1.5 text-[11px]">已保存</Badge></span>
    <span className="mt-1 block text-[13px] leading-5 text-muted-foreground">{record.meal_slot ? mealSlotLabels[record.meal_slot] : '未分类'}</span>
  </span>
  <span className="flex shrink-0 flex-wrap items-baseline justify-end gap-x-1 text-right tabular-nums"><span className="text-base font-semibold">{energy(record.totals.energy_kcal)}</span><span className="text-xs text-muted-foreground">kcal</span></span>
  <ChevronRight aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
</CardContent></Card></Link>)}</div>)}{page.next_cursor ? <Button className="h-11 w-full" disabled={isLoadingMore} onClick={() => onLoadMore(page.next_cursor!)} type="button" variant="outline">{isLoadingMore ? '正在加载…' : '加载更多记录'}</Button> : null}</section> }
