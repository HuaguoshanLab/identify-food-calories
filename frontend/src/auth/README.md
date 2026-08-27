# Authentication UI

## 职责

`src/auth/` 保存用户 H5 的公开认证页面、表单边界和受控 API 适配器。它只处理浏览器侧路由、输入体验和 FastAPI `/api/v1` 公共合约；账号权限、验证码当前性和会话安全始终由服务端决定。

## 允许依赖

- 可依赖 React、React Router、TanStack Query、React Hook Form、Zod 与 `@hookform/resolvers`。
- 可依赖 `src/components/ui/` 中已审核的官方 shadcn/Base UI 原语。
- 网络请求只能访问受控 FastAPI `/api/v1/auth/*` 和 `/api/v1/users/*` 合约，并使用受控 origin。
- 禁止访问 localStorage、sessionStorage、IndexedDB、Cookie 内容、backend 源码、数据库、密钥或 `/api/v1/admin/*`。

## 文件索引

| 文件 | 职责 |
|---|---|
| `README.md` | 认证 UI 边界、允许依赖和文件索引 |
| `PublicPages.tsx` | 落地页、隐私/条款和表单页共用公开布局 |
| `PublicRoutes.test.tsx` | 公开路由、受保护入口和无后台表面证据 |
| `LoginPage.tsx` | 登录表单与统一、非枚举错误映射；不持久化 access token |
| `RegisterPage.tsx` | 注册与非枚举验证码分发；只发送 email/password |
| `RegisterVerifyPage.tsx` | 注册验证码、掩码邮箱、冷却、重发和显式错误恢复 |
| `ForgotPasswordPage.tsx` | 密码恢复申请壳；等待后端恢复 API 合约 |
| `ResetPasswordPage.tsx` | 缺少有效恢复上下文时的安全重置入口 |
| `api.ts` | 受控注册、验证和登录 API 适配器；不暴露 Cookie 或 token |
| `schemas.ts` | React Hook Form 使用的 Zod 运行时输入契约 |
| `AuthForms.test.tsx` | 表单、payload、错误、冷却和可访问性行为测试 |
