# Authentication UI

## 职责

`src/auth/` 保存用户 H5 的认证页面、内存会话和受控 API 适配器。它只处理浏览器侧路由、输入体验和 FastAPI `/api/v1` 公共合约；身份、权限、验证码当前性和会话安全始终由服务端决定。

## 允许依赖

- 可依赖 React、React Router、TanStack Query、React Hook Form、Zod 与 `@hookform/resolvers`。
- 可依赖 `src/components/ui/` 中已审核的官方 shadcn/Base UI 原语。
- 网络请求只能访问受控 FastAPI `/api/v1/auth/*` 和 `/api/v1/users/*` 合约，并使用受控 origin。
- 禁止访问 localStorage、sessionStorage、IndexedDB、Cookie 内容、backend 源码、数据库、密钥或 `/api/v1/admin/*`。

## 文件索引

| 文件 | 职责 |
|---|---|
| `README.md` | 认证 UI 边界、允许依赖和文件索引 |
| `PublicPages.tsx` | 落地页与隐私/条款的纯内容组件；它们交由 `PublicAuthLayout` 提供 H5 视口、品牌入口和唯一滚动区。`AuthEntryPage` 继续为认证表单提供共用内容结构。 |
| `PublicRoutes.test.tsx` | 公开路由、主次 CTA、法律页公开滚动边界、受保护入口和无后台表面证据 |
| `LoginPage.tsx` | 登录表单与统一、非枚举错误映射；不持久化 access token |
| `RegisterPage.tsx` | 注册与非枚举验证码分发；只发送 email/password |
| `RegisterVerifyPage.tsx` | 注册验证码、掩码邮箱、冷却、重发和显式错误恢复 |
| `ForgotPasswordPage.tsx` | 密码恢复申请壳；等待后端恢复 API 合约 |
| `ResetPasswordPage.tsx` | 缺少有效恢复上下文时的安全重置入口 |
| `api.ts` | 受控注册、验证、登录、refresh 与 `/users/me` API 适配器；默认走同源 `/api/v1`，生产绝不把回环 API 地址编进 bundle，也不暴露 Cookie 或 token |
| `AuthProvider.tsx` | access token 仅存运行时内存；页面内 single-flight 与跨标签 Web Locks 协调 refresh 后以 `/users/me` 建立数据库权威身份 |
| `refreshCoordinator.ts` | 页面内 refresh single-flight 与同源标签页 Web Locks 协调；不放宽服务端真实 replay 的 family revoke |
| `AuthContext.ts` / `useAuth.ts` | 认证状态契约、`AuthenticatedRequest` 浏览器请求能力与消费 Hook；请求能力作为 feature API 的依赖传入，避免 feature 间借用传输类型 |
| `RouteGuards.tsx` | 统一 `/app/*` pathless `Outlet` 守卫；拥有 bootstrap、身份错误重试与精确登录回跳，不承载账号或会话业务页面 |
| `returnTo.ts` | 同源、相对、已登记受保护路由的登录返回地址解析 |
| `SessionList.tsx` | `/app` 身份后的 TanStack Query 会话列表、重试、退出当前设备与远端撤销入口 |
| `RevokeSessionDialog.tsx` | Base UI AlertDialog 的破坏性远端会话撤销确认，不允许撤销当前会话 |
| `schemas.ts` | React Hook Form 使用的 Zod 运行时输入契约 |
| `AuthForms.test.tsx` | 表单、payload、错误、冷却和可访问性行为测试 |
| `AuthSession.test.tsx` | refresh、数据库权威身份、独立 Provider bootstrap、并发 401 重试与 token 非持久化测试 |
| `refreshCoordinator.test.ts` | 隔离标签页运行时的 refresh 锁串行化测试 |
| `ProtectedRoutes.test.tsx` | 受保护深链、安全 returnTo 与无 admin 路由测试 |

H5第5项：SessionList调整为12px圆角轻阴影卡片与13px日期文字；Query、退出及撤销交互保持原有所有权。
