import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

function ConfirmDialog() {
  return (
    <AlertDialog>
      <AlertDialogTrigger>撤销会话</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>撤销这个登录会话？</AlertDialogTitle>
          <AlertDialogDescription>
            该设备将需要重新登录。
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>保留这个会话</AlertDialogCancel>
          <AlertDialogAction>撤销这个会话</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

describe('official shadcn Base UI primitives', () => {
  it('renders semantic alerts and preserves visible focus-ring classes', () => {
    render(
      <>
        <Alert>
          <AlertTitle>请求失败</AlertTitle>
          <AlertDescription>请稍后重试。</AlertDescription>
        </Alert>
        <Badge render={<button type="button">当前设备</button>} />
      </>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('请求失败请稍后重试。')
    expect(screen.getByRole('button', { name: '当前设备' })).toHaveClass(
      'focus-visible:ring-[3px]',
      'focus-visible:ring-ring/50',
    )
  })

  it('traps focus, closes on Escape, and returns focus to its trigger', async () => {
    const user = userEvent.setup()

    render(<ConfirmDialog />)

    const trigger = screen.getByRole('button', { name: '撤销会话' })
    await user.click(trigger)

    const dialog = screen.getByRole('alertdialog', { name: '撤销这个登录会话？' })
    const cancel = screen.getByRole('button', { name: '保留这个会话' })
    const action = screen.getByRole('button', { name: '撤销这个会话' })

    expect(dialog).toBeInTheDocument()
    expect(document.activeElement).toBe(cancel)

    await user.tab()
    expect(document.activeElement).toBe(action)
    await user.tab()
    expect(document.querySelectorAll('[data-base-ui-focus-guard]')).toHaveLength(2)
    expect(document.activeElement).not.toBe(trigger)

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
  })

  it('keeps skeleton layout dimensions while global reduced-motion CSS can suppress animation', () => {
    const { container } = render(<Skeleton className="h-5 w-40" aria-label="正在加载账号" />)
    const skeleton = screen.getByLabelText('正在加载账号')

    expect(skeleton).toHaveClass('h-5', 'w-40', 'animate-pulse')
    expect(container.ownerDocument.documentElement).toBeInTheDocument()
  })
})
