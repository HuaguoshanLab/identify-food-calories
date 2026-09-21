import { useEffect, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { buttonVariants } from '@/components/ui/button'

type PublicPageProps = {
  children?: ReactNode
  description: string
  progress?: string
  title: string
}

function PublicPage({ children, description, progress, title }: PublicPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <section className="mx-auto flex w-full max-w-md flex-col py-8">
      <div className="rounded-3xl bg-card p-6 shadow-sm ring-1 ring-border/60">
        {progress ? <p className="mb-2 text-sm text-muted-foreground">{progress}</p> : null}
        <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold tracking-tight">
          {title}
        </h1>
        <p className="mt-2 text-muted-foreground">{description}</p>
        {children}
      </div>
    </section>
  )
}

export function LandingPage() {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-8 py-8">
      <section className="flex flex-col gap-4"><p className="text-xs font-semibold tracking-[0.2em] text-primary">好好吃饭，从了解一餐开始</p><div aria-hidden="true" className="mb-2 flex h-36 items-center justify-center rounded-[32px] bg-accent"><span className="flex size-24 items-center justify-center rounded-full border-[12px] border-card bg-primary/10"><span className="size-9 rounded-full bg-primary/70" /></span></div>
        <h1 ref={headingRef} tabIndex={-1} className="text-[28px] leading-9 font-semibold tracking-tight">
          拍下或描述一餐，获得可追问的饮食分析
        </h1>
        <p className="text-base leading-6 text-muted-foreground">
          登录后使用餐食分析、记录和规划功能。结果仅作普通饮食参考。
        </p>
      </section>
      <div className="flex flex-col gap-4">
        <Link
          className={buttonVariants({
            className: 'h-11 w-full cursor-pointer text-base font-semibold',
          })}
          to="/register"
        >
          创建账号
        </Link>
        <Link
          className={buttonVariants({
            className: 'h-11 w-full cursor-pointer text-base font-semibold',
            variant: 'outline',
          })}
          to="/login"
        >
          登录
        </Link>
      </div>
      <nav aria-label="法律信息" className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
        <Link className="text-foreground underline underline-offset-4 hover:text-primary" to="/privacy">
          查看隐私说明
        </Link>
        <Link className="text-foreground underline underline-offset-4 hover:text-primary" to="/terms">
          查看使用条款
        </Link>
      </nav>
    </div>
  )
}

type AuthEntryPageProps = {
  children?: ReactNode
  description: string
  progress?: string
  title: string
}

export function AuthEntryPage({ children, description, progress, title }: AuthEntryPageProps) {
  return (
    <PublicPage description={description} progress={progress} title={title}>
      {children}
    </PublicPage>
  )
}

export function PrivacyPage() {
  return (
    <LegalPage
      title="隐私说明"
      description="我们只在提供账号与饮食服务所必需的范围内处理信息。认证安全状态由服务器验证。"
    />
  )
}

export function TermsPage() {
  return (
    <LegalPage
      title="使用条款"
      description="饮食分析和规划结果仅作普通饮食参考，不提供医疗诊断或治疗建议。"
    />
  )
}

function LegalPage({ description, title }: Omit<PublicPageProps, 'children'>) {
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    headingRef.current?.focus()
  }, [])

  return (
    <article className="mx-auto flex w-full max-w-md flex-col gap-6 py-8">
      <div className="flex flex-col gap-4">
        <h1 ref={headingRef} tabIndex={-1} className="text-[28px] leading-9 font-semibold tracking-tight">
          {title}
        </h1>
        <p className="text-base leading-6 text-muted-foreground">{description}</p>
      </div>
      <Link className="w-fit text-sm text-foreground underline underline-offset-4 hover:text-primary" to="/">
        返回首页
      </Link>
    </article>
  )
}
