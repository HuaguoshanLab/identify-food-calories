import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { planReportSchema } from '../api/report'
import { MealCard } from './MealCard'

const nutrients = { energy_kcal: '180', protein_g: '10', fat_g: '4', carbohydrate_g: '25' }
const meal = { slot: 'lunch', display_name: '午餐组合餐', portion_grams: '450', portion_description: '三种食物', method_tags: ['蒸'], flavour_tags: ['清淡'], matched_preference_summaries: [], matched_exclusion_summaries: [], nutrients: { ...nutrients, energy_kcal: '540' } }
const items = [
  { meal_role: 'staple', display_name: '米饭' }, { meal_role: 'protein', display_name: '鸡胸肉' }, { meal_role: 'vegetable', display_name: '西兰花' },
].map(item => ({ ...item, portion_grams: '150', portion_description: '一份', method_tags: ['蒸'], flavour_tags: ['清淡'], nutrients }))
function report(mealItems?: unknown[]) {
  return { stage: 'complete', disclaimer: '普通饮食参考，不替代医疗建议。', target: Object.fromEntries(Object.keys(nutrients).map(key => [key, { lower: '0', upper: '2000' }])), meals: [{ ...meal, slot: 'breakfast' }, { ...meal, ...(mealItems ? { items: mealItems } : {}) }, { ...meal, slot: 'dinner' }] }
}

describe('MealCard components', () => {
  it('逐项展示菜名、角色、克数和热量，同时只显示一次餐次总热量', () => {
    const data = planReportSchema.parse(report(items))
    render(<MealCard meal={data.meals[1]} />)
    for (const label of ['米饭', '鸡胸肉', '西兰花', '主食', '蛋白质菜', '蔬菜']) expect(screen.getByText(label)).toBeVisible()
    expect(screen.getAllByText('150g · 一份')).toHaveLength(3)
    expect(screen.getAllByText('180 kcal')).toHaveLength(3)
    expect(screen.getByText('合计 540 kcal')).toBeVisible()
  })
  it('兼容没有明细的旧报告，拒绝残缺组合和泄露内部身份的报告', () => {
    const data = planReportSchema.parse(report())
    render(<MealCard meal={data.meals[1]} />)
    expect(screen.getByText('午餐组合餐')).toBeVisible()
    expect(screen.getByText('450g · 三种食物')).toBeVisible()
    expect(planReportSchema.safeParse(report(items.slice(0, 2))).success).toBe(false)
    expect(planReportSchema.safeParse(report([{ ...items[0], recipe_id: 'internal' }, ...items.slice(1)])).success).toBe(false)
  })
})
