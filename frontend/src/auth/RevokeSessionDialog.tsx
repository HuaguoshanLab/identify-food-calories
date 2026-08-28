import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'

import type { AuthSessionSummary } from './api'

type RevokeSessionDialogProps = {
  error?: string
  onConfirm: () => void
  onOpenChange: (open: boolean) => void
  open: boolean
  pending: boolean
  session?: AuthSessionSummary
}

export function RevokeSessionDialog({ error, onConfirm, onOpenChange, open, pending, session }: RevokeSessionDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="w-[calc(100%-2rem)] max-w-[360px]">
        <AlertDialogHeader>
          <AlertDialogTitle>撤销这个登录会话？</AlertDialogTitle>
          <AlertDialogDescription>该设备将需要重新登录。此操作不会删除账号或饮食数据。</AlertDialogDescription>
        </AlertDialogHeader>
        {session ? <p className="text-base leading-6 text-muted-foreground">设备：{session.device_label ?? '未知设备'}</p> : null}
        {error ? <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert> : null}
        <AlertDialogFooter>
          <AlertDialogCancel className="min-h-11 w-full sm:w-auto" disabled={pending}>保留这个会话</AlertDialogCancel>
          <AlertDialogAction className="min-h-11 w-full sm:w-auto" disabled={pending} onClick={onConfirm} variant="destructive">{pending ? '正在撤销…' : '撤销这个会话'}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
