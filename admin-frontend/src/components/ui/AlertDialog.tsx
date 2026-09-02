import { AlertDialog as BaseAlertDialog } from '@base-ui/react/alert-dialog'
import { type ComponentProps, forwardRef } from 'react'

export const AlertDialog = BaseAlertDialog

export const AlertDialogContent = forwardRef<HTMLDivElement, ComponentProps<typeof BaseAlertDialog.Popup>>(
  ({ className = '', ...props }, ref) => (
    <BaseAlertDialog.Portal>
      <BaseAlertDialog.Backdrop className="fixed inset-0 z-50 bg-foreground/20" />
      <BaseAlertDialog.Viewport className="fixed inset-0 z-50 grid place-items-center p-4">
        <BaseAlertDialog.Popup
          className={`w-full max-w-lg rounded-lg border bg-card p-6 text-card-foreground shadow-lg ${className}`}
          ref={ref}
          {...props}
        />
      </BaseAlertDialog.Viewport>
    </BaseAlertDialog.Portal>
  ),
)
AlertDialogContent.displayName = 'AlertDialogContent'
