import { describe, expect, it } from 'vitest'

import { cn } from '@/components/ui/utils'

describe('cn', () => {
  it('combines conditional classes and keeps the final Tailwind conflict', () => {
    expect(cn('px-2 text-slate-600', false && 'hidden', ['px-4'])).toBe(
      'text-slate-600 px-4',
    )
  })
})
