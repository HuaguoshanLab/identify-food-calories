import { forwardRef, type HTMLAttributes, type PropsWithChildren } from 'react'

type PageScrollAreaProps = PropsWithChildren<
  Omit<HTMLAttributes<HTMLElement>, 'children'> & {
    contentId?: string
  }
>

/**
 * Keep scrolling on one semantic main landmark. `min-h-0` is essential in a flex column:
 * without it, long content can expand the frame and hide fixed frame siblings.
 */
export const PageScrollArea = forwardRef<HTMLElement, PageScrollAreaProps>(function PageScrollArea(
  { children, className = '', contentId = 'main-content', ...props },
  ref,
) {
  return (
    <main
      {...props}
      ref={ref}
      id={contentId}
      tabIndex={-1}
      className={`min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 ${className}`.trim()}
      data-testid="page-scroll-area"
    >
      {children}
    </main>
  )
})
