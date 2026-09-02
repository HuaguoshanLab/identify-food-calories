# Admin Frontend Architecture

## 状态与目标

`admin-frontend/` 是 Phase 6 的独立、桌面优先管理后台 React SPA。本文件是实施前的架构合同：它规定后续代码的落点和边界，不声称当前已存在应用入口、依赖锁或业务页面。

后台服务于五类管理员工作：运行概览、营养目录版本治理、Agent 运行审计、模型配置与操作审计。它只访问公开 `/api/v1/admin/*`；用户 H5 保持四 Tab，绝不包含后台路由、导航或业务组件。

```text
浏览器
  → admin-frontend/（独立 Vite 构建）
  → 运行时内存中的 access token + HttpOnly refresh Cookie
  → 公开 /api/v1/admin/* HTTP 合约
  → FastAPI admin API → Service → Repository → PostgreSQL 当前角色与审计

前端 route guard / 菜单可见性 ── 仅改善体验，不能替代后端 RBAC
```

## 目标运行时组成

后续入口必须保持以下单向组合；应用级文件只装配 Provider 与路由，不承载业务请求或领域状态。

```text
main.tsx
  → BrowserRouter
  → QueryClientProvider
  → AdminAuthProvider
  → App.tsx（后台路由组合）
       ├─ layouts/AdminShell
       ├─ auth/AdminLoginPage + admin probe guard
       └─ features/<capability>/components
            → features/<capability>/api（Zod DTO + 请求函数）
            → TanStack Query
            → /api/v1/admin/*
```

管理员身份恢复后先调用 admin probe。probe 成功才可进入受保护路由；401、403 和会话刷新失败必须回到安全登录/无权限状态。无论前端曾得到什么状态，所有读取与 mutation 都要接受后端的实时角色校验结果。

## 目录地图与新代码落点

下列目录在相应执行计划创建前可能还不存在；首次创建必须同时加入本级 README 和父级索引。

| 位置 | 责任 | 新代码放置规则 |
|---|---|---|
| `src/main.tsx` | React、Router、Query、认证 Provider 装配 | 仅启动与 Provider 顺序；不写请求、页面或业务状态。 |
| `src/App.tsx` | 路由、guard 与页面组合 | 仅登记和组合路由；不得导入用户 H5。 |
| `src/routePaths.ts` | 静态后台路径合同 | 所有可复用静态路径与重定向目标集中维护。 |
| `src/styles/` | Tailwind 入口、后台语义 token、全局焦点/reduced-motion 规则 | 不放 feature 局部样式或业务条件。 |
| `src/layouts/` | `AdminShell`、侧栏、顶部栏、桌面/窄屏结构 | 只管布局和导航，不请求领域 API。 |
| `src/components/ui/` | 官方 shadcn/Base UI 原语 | 无业务含义、无网络、无认证上下文；只从官方 registry 引入。 |
| `src/components/` | 真正跨两个以上后台 feature 的组合组件 | 必须先证明复用；否则组件留在所属 feature。 |
| `src/auth/` | 管理员登录、运行时身份、probe、登出与 guard | 只处理认证协议与会话体验，不把前端状态当授权来源。 |
| `src/features/overview/` | 近 24 小时运行指标与到 runs 的筛选深链 | 指标 API、格式化、页面和测试都留在本 feature。 |
| `src/features/catalog/` | 目录草稿、审核、发布、失格与字段级差异 | 所有目录 mutation 走严格 API 客户端与理由确认。 |
| `src/features/runs/` | 运行筛选、列表和最小化详情 | 只消费安全摘要；不渲染 Provider 原文或完整 State。 |
| `src/features/model-configs/` | 非密钥 Provider/模型版本、费用上限与启停 | 不出现密钥、端点或 Provider body 字段。 |
| `src/features/audit/` | 管理员操作审计时间线/表格 | 只读、分页、最小化 DTO；不自行拼装敏感详情。 |
| `src/test/` | Vitest、Testing Library、MSW 通用 setup | 清理 mock、Query cache 与 DOM；不放 feature 测试主体。 |
| `tests/e2e/` | Playwright 真实公开 API 跨栈路径 | 不通过直写数据库、伪造 token 或内部函数建立验收状态。 |

## 后台路由与页面壳

路由只属于这个项目：

```text
/admin/login
/admin/overview
/admin/catalog
/admin/runs
/admin/model-configs
/admin/audit
```

`AdminShell` 面向桌面工作流：1280px 及以上使用 240px 固定侧栏；1024–1279px 为 208px 紧凑侧栏；768–1023px 收起为可键盘关闭的 Sheet；小于 768px 只显示受控说明和退出入口，不伪装成可操作的 H5 后台。页面根不得横向溢出，宽表允许在自身区域横向滚动。

## 依赖规则

允许主方向：

```text
App → layouts / auth / features
layouts → routePaths + components/ui
features/<name>/components → 自己的 api/format + auth 的公开接口 + components/ui
features/<name>/api → auth 的认证请求接口 + Zod
features/<name>/api → /api/v1/admin/*
components/ui → React / Base UI / 样式工具
```

硬规则：

1. `App.tsx` 与 `layouts/` 不发领域请求；请求、运行时 DTO 和 Query key 都由所属 feature 的 `api/` 拥有。
2. feature 默认隔离，禁止导入其他 feature 的组件、内部状态或私有类型。确实需要共享时，必须提升为有明确所有者的公开 API 或跨 feature 组件，并更新双方 README。
3. 所有 API 响应在 feature `api/` 中经 Zod（或等价生成校验器）验证。组件不能直接 `fetch`、定义后端 DTO 或把响应视为可信。
4. TanStack Query 只管理服务端状态；筛选框、对话框开关等瞬时状态留在组件本地。表单使用 React Hook Form + Zod，禁止散落手写校验。
5. 不创建全局 `services/`、`hooks/`、`utils/`、`types/`、`pages/` 或通用“admin API”垃圾桶目录；代码先归属一个能力。
6. 禁止导入 `frontend/src`、`backend/`、SQLAlchemy、Provider SDK 或任何密钥。后台与后端的唯一数据边界是公开 HTTP 合约。

## 认证、授权与敏感数据

- access token 只能存于 `AdminAuthProvider` 的内存；refresh token 是 HttpOnly Cookie，不能被 JavaScript 读取或复制到浏览器持久化存储。
- 前端 guard 只决定体验路径；每个 `/api/v1/admin/*` 请求由后端从 PostgreSQL 当前角色做最终授权。普通用户收到 403 时必须安全失败。
- 运行列表与详情只允许工具名、耗时、估算费用、调用计数、图/模型版本、失败节点/码和安全摘要。禁止用户邮箱、原文、原图、完整 Graph State、Provider body、密钥与模型思维链。
- 目录发布、失格、Provider 启停和模型配置变更必须展示后端返回的字段级可读差异/影响范围，并要求理由与确认；不可把原始 JSON diff 当作管理界面。
- 当前配置只显示非密钥字段。历史版本和运行配置快照必须可追溯，但不得让正在运行的任务被前端“硬中断”。

## 质量门禁

每个 feature 至少提供：严格 DTO/API 客户端测试、组件行为测试、必要的 HTTPX/真实 PostgreSQL 后端证据，以及与用户可见行为对应的 Playwright 路径。完成页面、表单、路由、图表或跨栈交互后，还必须经 Codex 内置浏览器通过真实产品页面和公开 API 验收。

浏览器验收不得通过直写数据库、伪造 token、调用内部函数或只看截图代替。目录创建、文件移动和依赖方向改变时，同步更新本目录与父级 README 索引。

## 变更门禁

1. 先在对应 feature `api/` 定义并校验公开 HTTP 合约，再写 Query/页面；禁止先写假数据页面。
2. 新建目录同次创建 README，写清职责、允许依赖和文件索引；更新父级索引。
3. 引入 UI 原语只允许官方 shadcn/Base UI registry，且不得引入新的图表库、远程字体或用户 H5 组件复制品。
4. 后端 RBAC、审计、不可变目录版本、迁移和服务事务仍在 `backend/` 实现；后台前端不拥有这些规则。
5. 任何对敏感字段、令牌存储或权限体验的变动，必须同时通过静态扫描、组件/API 测试与真实浏览器路径验证。
