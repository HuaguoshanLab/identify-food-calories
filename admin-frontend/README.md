# Admin Frontend

## 职责

`admin-frontend/` 是 Phase 6 的独立桌面优先 React SPA。它为管理员提供运行概览、营养目录版本治理、Agent 运行审计、模型配置和操作审计界面。

它不是用户 H5 的扩展：不得导入 `frontend/src`、不得向用户 H5 注册后台路由，也不得读取数据库或服务端源码。所有数据只能通过公开的 `/api/v1/admin/*` HTTP 合约取得；最终授权始终由后端读取 PostgreSQL 当前角色决定。

当前已具备独立的 Vite 供应链与构建边界；应用入口和业务页面仍按已批准的 Phase 6 计划分步创建。后台可独立部署，构建产物不包含用户 H5 的源码、路由或组件。

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
npm run typecheck
npm run build
npm test
npm run test:e2e
```

开发服务器固定在 `127.0.0.1:5179`，仅将 `/api/v1/admin` 代理到显式配置的本地后端目标。生产构建必须提供 `VITE_ADMIN_API_BASE_URL`：它只能是 `/api/v1/admin`（或其子路径）或路径同样以 `/api/v1/admin` 开头的 HTTPS URL。缺失、非 HTTPS、协议相对 URL 或越出 admin API 边界的值都会让构建失败；不存在面向用户 H5 或通用 `/api/v1` 的静默回退。

前端路由和可见性只改善体验。每一个真实请求仍由后端 `/api/v1/admin/*` 从 PostgreSQL 读取当前角色并执行 RBAC；前端不能保存、伪造或替代该授权判断。

## 文件索引

| 路径 | 职责 |
|---|---|
| `README.md` | 目录职责、允许依赖与文件索引 |
| `AGENTS.md` | 管理后台局部实现、安全、测试和文档约束 |
| `ARCHITECTURE.md` | 独立后台的模块地图、依赖方向、新代码落点与变更门禁 |
| `src/` | 独立 SPA 入口、认证运行时、全局样式和共享测试 setup；目录索引见 `src/README.md`。 |
| `package.json` / `package-lock.json` | 已审计直接依赖、脚本与可复现 npm 安装锁 |
| `vite.config.ts` | 独立端口、开发代理与生产 admin API fail-closed 校验 |
| `tsconfig*.json` / `vite-env.d.ts` | 应用与 Vite 配置的严格 TypeScript project references、初始环境类型锚点 |
| `tailwind.config.ts` / `postcss.config.js` | 后台语义 token 与 Tailwind 构建适配 |
| `components.json` | 官方 shadcn Base UI registry 的受限生成配置 |

## 实施顺序

实施从已批准的 [Phase 6 计划](../.planning/phases/06-user-dashboard-admin/) 开始。先建立锁定的 Vite 供应链与独立入口，再创建认证壳、严格 API 客户端和各功能模块；不得跳过计划直接手写后台页面。
