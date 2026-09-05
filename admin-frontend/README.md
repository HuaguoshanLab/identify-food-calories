# Admin Frontend

## 职责

`admin-frontend/` 是 Phase 6 的独立桌面优先 React SPA。它为管理员提供运行概览、营养目录版本治理、Agent 运行审计、模型配置和操作审计界面。

它不是用户 H5 的扩展：不得导入 `frontend/src`、不得向用户 H5 注册后台路由，也不得读取数据库或服务端源码。所有数据只能通过公开的 `/api/v1/admin/*` HTTP 合约取得；最终授权始终由后端读取 PostgreSQL 当前角色决定。

当前已具备登录/probe shell、overview、catalog lifecycle、runs、runtime config 与 audit 页面。后台可独立部署，构建产物不包含用户 H5 的源码、路由或组件。

后台刷新页面会先用 HttpOnly Cookie 恢复会话、核实当前用户，再检查管理员权限；有效会话保留原路由，不因内存 token 清空而立即跳登录。退出仍通过服务端撤销，令牌不写入浏览器持久化存储。

本地后端的 `CORS_ORIGINS` 必须明确包含 `http://127.0.0.1:5179`（使用 localhost 时也添加对应来源）。该配置同时用于 refresh/logout 的 CSRF 来源校验；即使 Vite 已代理请求，遗漏后台来源仍会返回 `CSRF_ORIGIN_INVALID`。修改后需重新加载后端，不能关闭来源校验来绕过。

营养目录入口 `/admin/catalog` 使用“上方筛选、下方表格”：名称/别名、来源、授权状态可组合查询，支持分页与重置。“新增”及每行“编辑”打开居中表单，直接“保存草稿”；每行“审核”“发布”分别打开精简的居中确认弹窗，原因必填、字段差异默认折叠，不再跳转长详情页。“详情”保留审计及失格操作。“下载模板”提供中文 UTF-8 CSV 表头；“导入”在居中弹窗先显示逐行校验结果，所有行通过后填写原因并确认新增草稿（最多 500 条/1 MB，不覆盖或自动发布）。“导出”下载当前查询条件的全部匹配目录，最多 10000 条；CSV 可由 Excel 打开。

## 允许依赖

- React、TypeScript、Vite、React Router 和 TanStack Query：独立 SPA、路由与服务端状态。
- Tailwind CSS、官方 shadcn/Base UI registry、Lucide：后台视觉原语；不得增加第二套组件库或图表库。
- React Hook Form、Zod：表单体验和 HTTP DTO 运行时校验；FastAPI 仍是输入与权限的权威。
- Vitest、Testing Library、MSW、Playwright：组件、公开 API 合约与真实浏览器路径验证。

禁止依赖 `frontend/src`、后端 Python 模块、数据库客户端、服务端密钥、Provider SDK 或 Next.js 运行时。access token 仅可位于运行时内存，refresh token 只能由 HttpOnly Cookie 承载。

## 安装与构建

```bash
cd admin-frontend
npm ci
npm test
npm run typecheck
npm run build
npm run test:e2e
```

开发服务器固定在 `127.0.0.1:5179`，将 `/api/v1/admin` 及登录必须的公开 `/api/v1/auth`、`/api/v1/users` 代理到显式配置的本地后端目标。生产构建必须提供 `VITE_ADMIN_API_BASE_URL`：它只能是 `/api/v1/admin`（或其子路径）或路径同样以 `/api/v1/admin` 开头的 HTTPS URL。缺失、非 HTTPS、协议相对 URL 或越出 admin API 边界的值都会让构建失败；公开认证仍使用同源 `/api/v1`，不存在面向用户 H5 领域 API 的静默回退。

前端路由和可见性只改善体验。每一个真实请求仍由后端 `/api/v1/admin/*` 从 PostgreSQL 读取当前角色并执行 RBAC；前端不能保存、伪造或替代该授权判断。

`npm run test:e2e -- --grep admin-management` 使用独立 Playwright runner：固定 backend `8003`、用户 SPA `5183`、admin SPA `5184`，每次从受 `run_pg.py` 验证的 `food_agent_test` reset 开始，并以 Mailpit 公共 HTTP 完成浏览器邮箱验证。它严格验证“验证账户 → audited first-admin CLI → Guard Bearer probe 200 → RuntimeConfig UI POST 201 → catalog lifecycle/audit”；普通用户必须获得真实 probe 403，且不能渲染 AdminShell 或私有数据。CLI 仅写首位角色审计，绝不创建 RuntimeConfig 或替代端点 RBAC。该命令必须在可访问本机 Docker 的隔离测试环境中运行；未实际运行时不能将配置存在、Vitest、构建或手工观察表述为 Playwright PASS。

### Phase 6 后台调试

```bash
# feature-owned strict DTO、页面与 RBAC 会话体验
npm test -- --run \
  src/auth/AdminLoginPage.test.tsx \
  src/features/catalog/CatalogDraftPage.test.tsx \
  src/features/catalog/CatalogLifecyclePage.test.tsx \
  src/features/runs/RunsPage.test.tsx \
  src/features/audit/AuditPage.test.tsx \
  src/features/overview/AdminOverviewPage.test.tsx
npm run typecheck && npm run build
```

## 文件索引

| 路径 | 职责 |
|---|---|
| `README.md` | 目录职责、允许依赖与文件索引 |
| `AGENTS.md` | 管理后台局部实现、安全、测试和文档约束 |
| `ARCHITECTURE.md` | 独立后台的模块地图、依赖方向、新代码落点与变更门禁 |
| `src/` | 独立 SPA 入口、认证运行时、全局样式和共享测试 setup；目录索引见 `src/README.md`。 |
| `tests/` | 后台浏览器级跨栈验收；只能通过真实产品页面和公开 `/api/v1/admin/*` API 建立证据，目录索引见 `tests/README.md`。 |
| `package.json` / `package-lock.json` | 已审计直接依赖、脚本与可复现 npm 安装锁 |
| `vite.config.ts` | 独立端口、开发代理与生产 admin API fail-closed 校验 |
| `playwright.config.ts` | 独占端口、受保护 backend、双 Vite preview、readiness 与 SIGTERM cleanup 的后台 E2E runner。 |
| `tsconfig*.json` / `vite-env.d.ts` | 应用与 Vite 配置的严格 TypeScript project references、初始环境类型锚点 |
| `tailwind.config.ts` / `postcss.config.js` | 后台语义 token 与 Tailwind 构建适配 |
| `components.json` | 官方 shadcn Base UI registry 的受限生成配置 |
| `src/auth/` | 公开登录、只驻留内存的 access token、probe guard 与 Query cache 清理 |
| `src/features/catalog/` | 严格预览、草稿、审核、发布与失格 UI；可信 diff 始终来自后端 |
| `src/features/runs/` / `src/features/audit/` | 最小运行诊断和 append-only 审计读取 UI |

## 实施顺序

实施从已批准的 [Phase 6 计划](../.planning/phases/06-user-dashboard-admin/) 开始。先建立锁定的 Vite 供应链与独立入口，再创建认证壳、严格 API 客户端和各功能模块；不得跳过计划直接手写后台页面。
