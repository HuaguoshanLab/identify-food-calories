import { Route, Routes } from 'react-router-dom'

import {
  AuthEntryPage,
  LandingPage,
  PrivacyPage,
  ProtectedAppEntry,
  TermsPage,
} from './auth/PublicPages'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/login"
        element={<AuthEntryPage title="欢迎回来" description="登录后继续管理你的饮食与登录会话。" />}
      />
      <Route
        path="/register"
        element={<AuthEntryPage title="创建账号" description="使用邮箱创建你的饮食健康档案。" />}
      />
      <Route
        path="/register/verify"
        element={<AuthEntryPage title="验证邮箱" description="请先完成注册后再输入验证码。" />}
      />
      <Route
        path="/forgot-password"
        element={<AuthEntryPage title="忘记密码" description="输入邮箱以申请重置验证码。" />}
      />
      <Route
        path="/reset-password"
        element={<AuthEntryPage title="重置密码" description="请先申请重置验证码。" />}
      />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/app" element={<ProtectedAppEntry />} />
      <Route path="*" element={<LandingPage />} />
    </Routes>
  )
}
