import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { formatPlanNumber } from '../format'
import type { PlanMeal } from './PlanPage'

const slotLabels = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐' } as const

export function MealCard({ meal }: { meal: PlanMeal }) {
  const constraints = [...meal.matched_preference_summaries, ...meal.matched_exclusion_summaries]
  const tags = [...meal.method_tags, ...meal.flavour_tags]

  return (
    <Card aria-labelledby={`meal-${meal.slot}-title`}>
      <CardHeader className="space-y-1">
        <h3 className="text-base font-semibold leading-none" id={`meal-${meal.slot}-title`}>{slotLabels[meal.slot]}</h3>
        <p className="tabular-nums text-sm text-muted-foreground">合计 {formatPlanNumber(meal.nutrients.energy_kcal)} kcal</p>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="font-semibold">{meal.display_name}</p>
        <p className="tabular-nums text-sm text-muted-foreground">{formatPlanNumber(meal.portion_grams)}g · {meal.portion_description}</p>
        {tags.length ? <div aria-label="烹饪与口味标签" className="flex flex-wrap gap-2">{tags.map((tag) => <Badge key={tag} variant="secondary">{tag}</Badge>)}</div> : null}
        <p className="text-sm text-muted-foreground">已遵守：{constraints.length ? constraints.join(' · ') : '已确认的忌口与口味'}</p>
      </CardContent>
    </Card>
  )
}
