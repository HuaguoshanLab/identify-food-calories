import { useEffect, useRef, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

type PublicPageProps = {
  children?: ReactNode
  description: string
  title: string
}

function PublicPage({ children, description, title }: PublicPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <main className="min-h-dvh px-4 py-8 md:px-6">
      <div className="mx-auto flex w-full max-w-md flex-col gap-6">
        <Link className="w-fit text-sm font-medium text-slate-700 underline hover:text-teal-700" to="/">
          饮食健康 Agent
        </Link>
        <section className="rounded-xl bg-card p-6 shadow-sm ring-1 ring-foreground/10">
          <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold tracking-tight">
            {title}
          </h1>
          <p className="mt-2 text-slate-600">{description}</p>
          {children}
        </section>
      </div>
    </main>
  )
}

export function LandingPage() {
  return (
    <main className="min-h-dvh px-4 py-8 md:px-6">
      <div className="mx-auto flex w-full max-w-md flex-col gap-8 py-8">
        <p className="text-sm font-semibold text-teal-700">饮食健康 Agent</p>
        <section>
          <h1 className="text-3xl font-semibold tracking-tight">
            拍下或描述一餐，获得可追问的饮食分析
          </h1>
          <p className="mt-4 text-slate-700">
            登录后使用餐食分析、记录和规划功能。结果仅作普通饮食参考。
          </p>
        </section>
        <div className="flex flex-col gap-3">
          <Link
            className="inline-flex min-h-11 items-center justify-center rounded-lg bg-teal-600 px-4 py-2 font-medium text-white transition-colors hover:bg-teal-700"
            to="/register"
          >
            创建账号
          </Link>
          <Link
            className="inline-flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium text-slate-800 transition-colors hover:bg-slate-100"
            to="/login"
          >
            登录
          </Link>
        </div>
        <nav aria-label="法律信息" className="flex gap-4 text-sm">
          <Link className="text-slate-700 underline hover:text-teal-700" to="/privacy">
            查看隐私说明
          </Link>
          <Link className="text-slate-700 underline hover:text-teal-700" to="/terms">
            查看使用条款
          </Link>
        </nav>
      </div>
    </main>
  )
}

type AuthEntryPageProps = {
  children?: ReactNode
  description: string
  title: string
}

export function AuthEntryPage({ children, description, title }: AuthEntryPageProps) {
  return (
    <PublicPage description={description} title={title}>
      {children}
    </PublicPage>
  )
}

export function PrivacyPage() {
  return (
    <PublicPage
      title="隐私说明"
      description="我们只在提供账号与饮食服务所必需的范围内处理信息。认证安全状态由服务器验证。"
    >
      <Link className="mt-6 inline-block text-sm text-slate-700 underline hover:text-teal-700" to="/">
        返回首页
      </Link>
    </PublicPage>
  )
}

export function TermsPage() {
  return (
    <PublicPage
      title="使用条款"
      description="饮食分析和规划结果仅作普通饮食参考，不提供医疗诊断或治疗建议。"
    >
      <Link className="mt-6 inline-block text-sm text-slate-700 underline hover:text-teal-700" to="/">
        返回首页
      </Link>
    </PublicPage>
  )
}

export function ProtectedAppEntry() {
  const location = useLocation()
  const returnTo = `${location.pathname}${location.search}`

  return (
    <AuthEntryPage
      title="欢迎回来"
      description="请先登录后继续使用账号功能。"
    >
      <Link
        className="mt-6 inline-block text-sm text-slate-700 underline hover:text-teal-700"
        to={`/login?returnTo=${encodeURIComponent(returnTo)}`}
      >
        前往登录
      </Link>
    </AuthEntryPage>
  )
}
