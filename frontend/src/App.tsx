import { Navigate, Route, Routes } from 'react-router-dom'

import {
  LandingPage,
  PrivacyPage,
  TermsPage,
} from './auth/PublicPages'
import { RequireAuthentication } from './auth/RouteGuards'
import { ForgotPasswordPage } from './auth/ForgotPasswordPage'
import { LoginPage } from './auth/LoginPage'
import { RegisterPage } from './auth/RegisterPage'
import { RegisterVerifyPage } from './auth/RegisterVerifyPage'
import { ResetPasswordPage } from './auth/ResetPasswordPage'
import { AccountDetailsPage } from './app/AccountDetailsPage'
import { MePage } from './app/MePage'
import { PlaceholderTabPage } from './app/PlaceholderTabPage'
import { SessionsDetailsPage } from './app/SessionsDetailsPage'
import { AppShell } from './layouts/AppShell'
import { DetailLayout } from './layouts/DetailLayout'
import { PublicAuthLayout } from './layouts/PublicAuthLayout'

export function App() {
  return (
    <Routes>
      <Route element={<PublicAuthLayout mode="entry" />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
      </Route>

      <Route element={<PublicAuthLayout backTo="/register" mode="step" />}>
        <Route path="/register/verify" element={<RegisterVerifyPage />} />
      </Route>

      <Route element={<PublicAuthLayout backTo="/forgot-password" mode="step" />}>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Route>

      <Route element={<RequireAuthentication />}>
        <Route path="/app">
          <Route index element={<Navigate replace to="me" />} />
          <Route element={<AppShell />}>
            <Route path="analyze" element={<PlaceholderTabPage title="分析" />} />
            <Route path="records" element={<PlaceholderTabPage title="记录" />} />
            <Route path="plans" element={<PlaceholderTabPage title="计划" />} />
            <Route path="me" element={<MePage />} />
          </Route>
          <Route element={<DetailLayout title="账号资料" />}>
            <Route path="me/account" element={<AccountDetailsPage />} />
          </Route>
          <Route element={<DetailLayout title="登录会话" />}>
            <Route path="me/sessions" element={<SessionsDetailsPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  )
}
