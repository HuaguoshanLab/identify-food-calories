import { Dialog } from '@base-ui/react/dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'

export function CatalogDialog({ title, description, children, onClose, busy = false }: Readonly<{
  title: string; description: string; children: ReactNode; onClose: () => void; busy?: boolean
}>) {
  return <Dialog.Root open onOpenChange={(open) => { if (!open && !busy) onClose() }}>
    <Dialog.Portal>
      <Dialog.Backdrop className="fixed inset-0 z-40 bg-foreground/25" />
      <Dialog.Viewport className="fixed inset-0 z-40 flex justify-end">
        <Dialog.Popup className="flex h-dvh w-full max-w-2xl flex-col border-l bg-card shadow-xl">
          <div className="flex items-start justify-between gap-4 border-b px-6 py-5">
            <div><Dialog.Title className="text-xl font-semibold">{title}</Dialog.Title><Dialog.Description className="mt-1 text-sm text-muted-foreground">{description}</Dialog.Description></div>
            <Dialog.Close aria-label="关闭窗口" className="rounded-md p-2 hover:bg-muted disabled:opacity-50" disabled={busy}><X size={18} /></Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-6">{children}</div>
        </Dialog.Popup>
      </Dialog.Viewport>
    </Dialog.Portal>
  </Dialog.Root>
}
