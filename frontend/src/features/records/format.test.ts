import { describe, expect, it } from 'vitest'

import { formatNutrition, toLocalDateTimeInput } from './format'

describe('record presentation formatters', () => {
  it('renders persisted decimal strings with user-facing precision', () => {
    expect(formatNutrition('130.000000')).toBe('130.0')
    expect(formatNutrition('0.300000')).toBe('0.3')
  })

  it('converts API instants into the local datetime input value', () => {
    expect(new Date(toLocalDateTimeInput('2026-08-31T11:47:00.000Z')).toISOString()).toBe('2026-08-31T11:47:00.000Z')
  })
})
