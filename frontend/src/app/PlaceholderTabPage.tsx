import { useEffect, useRef } from 'react'

export type PlaceholderTabTitle = '分析' | '记录' | '计划'

type PlaceholderTabPageProps = {
  title: PlaceholderTabTitle
}

/**
 * These tabs deliberately contain no simulated controls or data. Keeping the title union closed
 * makes it harder for a future unfinished route to appear as a finished capability by accident.
 */
export function PlaceholderTabPage({ title }: PlaceholderTabPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <section>
      <h1 ref={headingRef} tabIndex={-1} className="text-[28px] font-bold leading-9 tracking-tight">
        {title}
      </h1>
      <p className="mt-3 text-[15px] leading-6 text-muted-foreground">功能即将开放</p>
    </section>
  )
}
