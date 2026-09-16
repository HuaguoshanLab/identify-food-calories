import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { formatPlanNumber } from '../format'
import type { PlanMeal, PlanMealAdjustment } from './PlanPage'

const slotLabels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' } as const

export function MealCard({ meal, adjustment }: { meal: PlanMeal; adjustment?: PlanMealAdjustment }) {
  const entries = meal.items?.length ? meal.items : [meal]
  const roleLabels = { staple: '主食', protein: '蛋白质菜', vegetable: '蔬菜' } as const

  return (
    <Card aria-labelledby={`meal-${meal.slot}-title`}>
      <CardHeader className="flex items-center justify-between gap-3 border-b border-border/60 pb-2!">
        <div className="flex items-center gap-2"><h3 className="text-base font-semibold leading-6 text-primary" id={`meal-${meal.slot}-title`}>{slotLabels[meal.slot]}</h3>{adjustment ? <Badge>已调整</Badge> : null}</div>
        <p className="shrink-0 text-right tabular-nums text-sm leading-6 text-muted-foreground">合计 {formatPlanNumber(meal.nutrients.energy_kcal)} kcal</p>
      </CardHeader>
      <CardContent className="space-y-2">
        {entries.map((entry, index) => <div className="space-y-2 border-border/60 [&:not(:first-child)]:border-t [&:not(:first-child)]:pt-3" key={index}>
        {'meal_role' in entry ? <p className="text-xs text-muted-foreground">{roleLabels[entry.meal_role]}</p> : null}
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 flex-1 break-words text-[15px] font-semibold leading-6">{entry.display_name}</p>
          <p className="max-w-[45%] shrink-0 break-words text-right tabular-nums text-sm leading-6 text-muted-foreground">{formatPlanNumber(entry.portion_grams)}g · {entry.portion_description}</p>
        </div>
        {meal.items?.length ? <p className="text-right text-xs tabular-nums text-muted-foreground">{formatPlanNumber(entry.nutrients.energy_kcal)} kcal</p> : null}
        {[...entry.method_tags, ...entry.flavour_tags].length ? <div aria-label="烹饪与口味标签" className="flex flex-wrap gap-2">{[...new Set([...entry.method_tags, ...entry.flavour_tags])].map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}</div> : null}
        </div>)}
        {adjustment ? <div className="space-y-1 border-t border-border pt-2 text-sm text-muted-foreground"><p>已替换：{adjustment.previousName}</p><p>已满足：{adjustment.matchedConstraint}</p><p>全天营养：{adjustment.rangeStatus}</p></div> : null}
      </CardContent>
    </Card>
  )
}
