/** Keep persisted Decimal strings human-readable without changing their stored precision. */
const nutritionNumber = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function formatNutrition(value: string): string {
  const numericValue = Number(value)
  return Number.isFinite(numericValue) ? nutritionNumber.format(numericValue) : value
}

export function toLocalDateTimeInput(value: string): string {
  const date = new Date(value)
  const pad = (part: number) => part.toString().padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
