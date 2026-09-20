import { lazy, Suspense } from 'react'
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
import { AppShell } from './layouts/AppShell'
import { DetailLayout } from './layouts/DetailLayout'
import { PublicAuthLayout } from './layouts/PublicAuthLayout'

const AccountDetailsPage = lazy(() => import('./app/AccountDetailsPage').then((module) => ({ default: module.AccountDetailsPage })))
const MePage = lazy(() => import('./app/MePage').then((module) => ({ default: module.MePage })))
const SessionsDetailsPage = lazy(() => import('./app/SessionsDetailsPage').then((module) => ({ default: module.SessionsDetailsPage })))
const AnalyzePage = lazy(() => import('./features/agent/components/AnalyzePage').then((module) => ({ default: module.AnalyzePage })))
const RecordsPage = lazy(() => import('./features/records/components/RecordsPage').then((module) => ({ default: module.RecordsPage })))
const MealRecordDetailPage = lazy(() => import('./features/records/components/MealRecordDetailPage').then((module) => ({ default: module.MealRecordDetailPage })))
const MealRecordEditPage = lazy(() => import('./features/records/components/MealRecordEditPage').then((module) => ({ default: module.MealRecordEditPage })))
const MemoryManagementPage = lazy(() => import('./features/memory/components/MemoryManagementPage').then((module) => ({ default: module.MemoryManagementPage })))
const MemoryEditPage = lazy(() => import('./features/memory/components/MemoryEditPage').then((module) => ({ default: module.MemoryEditPage })))
const PersonalProfilePage = lazy(() => import('./features/plans/components/PersonalProfilePage').then((module) => ({ default: module.PersonalProfilePage })))
const PlanHistoryPage = lazy(() => import('./features/plans/components/PlanHistoryPage').then((module) => ({ default: module.PlanHistoryPage })))
const SavedPlanPage = lazy(() => import('./features/plans/components/SavedPlanPage').then((module) => ({ default: module.SavedPlanPage })))
const PlanPage = lazy(() => import('./features/plans/components/PlanPage').then((module) => ({ default: module.PlanPage })))

export function App() {
  return (
    <Suspense fallback={<p className="p-4 text-sm text-muted-foreground" role="status">正在加载页面…</p>}>
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
          <Route element={<DetailLayout title="餐食详情" />}>
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
    </Suspense>
  )
}
