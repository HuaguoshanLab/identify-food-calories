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
import { SessionsDetailsPage } from './app/SessionsDetailsPage'
import { AnalyzePage } from './features/agent/components/AnalyzePage'
import { RecordsPage } from './features/records/components/RecordsPage'
import { MealRecordDetailPage } from './features/records/components/MealRecordDetailPage'
import { MealRecordEditPage } from './features/records/components/MealRecordEditPage'
import { MemoryManagementPage } from './features/memory/components/MemoryManagementPage'
import { MemoryEditPage } from './features/memory/components/MemoryEditPage'
import { PersonalProfilePage } from './features/plans/components/PersonalProfilePage'
import { PlanHistoryPage } from './features/plans/components/PlanHistoryPage'
import { SavedPlanPage } from './features/plans/components/SavedPlanPage'
import { PlanPage } from './features/plans/components/PlanPage'
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
          <Route index element={<Navigate replace to="analyze" />} />
          <Route element={<AppShell />}>
            <Route path="analyze" element={<AnalyzePage />} />
            <Route path="records" element={<RecordsPage />} />
            <Route path="plans" element={<PlanPage />} />
            <Route path="me" element={<MePage />} />
          </Route>
          <Route element={<DetailLayout title="账号资料" />}>
            <Route path="me/account" element={<AccountDetailsPage />} />
          </Route>
          <Route element={<DetailLayout title="历史计划" />}><Route path="plans/history" element={<PlanHistoryPage />} /></Route>
          <Route element={<DetailLayout title="计划详情" />}><Route path="plans/detail" element={<SavedPlanPage />} /></Route>
          <Route element={<DetailLayout title="个人资料" />}>
            <Route path="me/profile" element={<PersonalProfilePage />} />
          </Route>
          <Route element={<DetailLayout title="登录会话" />}>
            <Route path="me/sessions" element={<SessionsDetailsPage />} />
          </Route>
          <Route element={<DetailLayout title="餐食记录" />}>
            <Route path="records/:recordId" element={<MealRecordDetailPage />} />
          </Route>
          <Route element={<DetailLayout title="编辑餐食" />}>
            <Route path="records/:recordId/edit" element={<MealRecordEditPage />} />
          </Route>
          <Route element={<DetailLayout title="饮食偏好与记忆" />}>
            <Route path="me/memories" element={<MemoryManagementPage />} />
          </Route>
          <Route element={<DetailLayout title="编辑记忆" />}>
            <Route path="me/memories/:memoryId/edit" element={<MemoryEditPage />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  )
}
