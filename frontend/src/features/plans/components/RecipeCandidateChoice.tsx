import { Button } from '@/components/ui/button'
import type { RecipeClarificationReport } from '../api/report'
import { formatPlanNumber } from '../format'

const slotLabels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }

export function RecipeCandidateChoice({ report, selectedId, busy, onSelect, onSubmit }: {
  report: RecipeClarificationReport
  selectedId?: string
  busy: boolean
  onSelect: (id: string) => void
  onSubmit: () => void
}) {
  return <section aria-labelledby="recipe-choice-title" className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
    <h2 className="text-base font-semibold leading-6" id="recipe-choice-title">请选择具体菜谱</h2>
    <p className="text-[15px] leading-6 text-muted-foreground">{report.message}</p>
    <fieldset className="space-y-2" disabled={busy}>
      <legend className="sr-only">可用菜谱</legend>
      {report.candidates.map((candidate) => <label className="flex min-h-14 cursor-pointer items-start gap-3 rounded-lg border border-input p-3 has-checked:border-primary has-checked:bg-accent" key={candidate.recipe_id}>
        <input className="mt-1 size-4 accent-primary" type="radio" name="replacement-recipe" value={candidate.recipe_id} checked={selectedId === candidate.recipe_id} onChange={() => onSelect(candidate.recipe_id)} />
        <span className="min-w-0 space-y-1">
          <span className="block text-[15px] font-medium">{candidate.display_name}</span>
          <span className="block text-sm tabular-nums">{slotLabels[candidate.meal_slot]} · {formatPlanNumber(candidate.portion_grams)}g · {candidate.portion_description}</span>
          <span className="block text-[13px] text-muted-foreground">{[...candidate.method_tags, ...candidate.flavour_tags].join(' · ')}</span>
        </span>
      </label>)}
    </fieldset>
    <p className="text-[13px] text-muted-foreground">请选择后再确认；其他餐次和已确认忌口保持不变。</p>
    <Button className="h-11 w-full" disabled={!selectedId || busy} onClick={onSubmit} type="button">{busy ? '正在替换…' : '确认菜谱并替换'}</Button>
  </section>
}
