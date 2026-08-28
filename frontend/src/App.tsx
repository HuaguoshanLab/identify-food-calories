import { Route, Routes } from 'react-router-dom'

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

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/register/verify" element={<RegisterVerifyPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/app" element={<RequireAuthentication />} />
      <Route path="*" element={<LandingPage />} />
    </Routes>
  )
}
