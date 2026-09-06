import type { PropsWithChildren } from 'react'

/**
 * Owns the H5 viewport boundary so pages cannot each create a competing scroll root.
 * The desktop frame changes only its outer chrome; descendants keep the 430px mobile flow.
 */
export function MobileFrame({ children }: PropsWithChildren) {
  return (
    <div
      className="relative flex h-dvh w-full flex-col overflow-hidden bg-background min-[768px]:mx-auto min-[768px]:my-4 min-[768px]:h-[calc(100dvh-2rem)] min-[768px]:w-[min(430px,calc(100vw-2rem))] min-[768px]:rounded-[32px] min-[768px]:border min-[768px]:border-border/60 min-[768px]:shadow-xl"
      data-testid="mobile-frame"
    >
      {children}
    </div>
  )
}
