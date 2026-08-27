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
| `LoginPage.tsx` | 登录表单（后续任务加入） |
| `RegisterPage.tsx` | 注册与非枚举验证码分发（后续任务加入） |
| `RegisterVerifyPage.tsx` | 注册验证码、冷却与错误恢复（后续任务加入） |
| `ForgotPasswordPage.tsx` | 密码恢复申请壳（后续任务加入） |
| `ResetPasswordPage.tsx` | 密码重置壳（后续任务加入） |
| `api.ts` | 受控认证 API 适配器（后续任务加入） |
| `schemas.ts` | 表单运行时校验契约（后续任务加入） |
| `AuthForms.test.tsx` | 表单、错误和可访问性行为测试（后续任务加入） |
