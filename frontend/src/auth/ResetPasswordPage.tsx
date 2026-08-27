import { Link } from 'react-router-dom'

import { AuthEntryPage } from './PublicPages'

export function ResetPasswordPage() {
  return (
    <AuthEntryPage title="重置密码" description="验证信息已失效，请重新开始。">
      <Link className="mt-6 inline-block text-sm text-slate-700 underline hover:text-teal-700" to="/forgot-password">
        重新申请重置
      </Link>
    </AuthEntryPage>
  )
}
