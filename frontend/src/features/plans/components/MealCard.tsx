import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { formatPlanNumber } from '../format'
import type { PlanMeal, PlanMealAdjustment } from './PlanPage'

const slotLabels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐' } as const

export function MealCard({ meal, adjustment }: { meal: PlanMeal; adjustment?: PlanMealAdjustment }) {
  const constraints = [...meal.matched_preference_summaries, ...meal.matched_exclusion_summaries]
  const tags = [...meal.method_tags, ...meal.flavour_tags]

  return (
    <Card aria-labelledby={`meal-${meal.slot}-title`}>
      <CardHeader className="space-y-1 border-b border-border/60 pb-3">
        <div className="flex items-center gap-2"><h3 className="text-base font-semibold leading-6 text-primary" id={`meal-${meal.slot}-title`}>{slotLabels[meal.slot]}</h3>{adjustment ? <Badge>已调整</Badge> : null}</div>
        <p className="tabular-nums text-sm text-muted-foreground">合计 {formatPlanNumber(meal.nutrients.energy_kcal)} kcal</p>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="break-words text-[15px] font-semibold leading-6">{meal.display_name}</p>
        <p className="tabular-nums text-sm text-muted-foreground">{formatPlanNumber(meal.portion_grams)}g · {meal.portion_description}</p>
        {tags.length ? <div aria-label="烹饪与口味标签" className="flex flex-wrap gap-2">{tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}</div> : null}
        <p className="rounded-md bg-muted/60 p-2.5 text-[13px] leading-5 text-muted-foreground">已遵守：{constraints.length ? constraints.join(' · ') : '已确认的忌口与口味'}</p>
        {adjustment ? <div className="space-y-1 border-t border-border pt-2 text-sm text-muted-foreground"><p>已替换：{adjustment.previousName}</p><p>已满足：{adjustment.matchedConstraint}</p><p>全天营养：{adjustment.rangeStatus}</p></div> : null}
      </CardContent>
    </Card>
  )
}
