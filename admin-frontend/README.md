# Admin Frontend

## 职责

`admin-frontend/` 是 Phase 6 的独立桌面优先 React SPA。它为管理员提供运行概览、营养目录版本治理、Agent 运行审计、模型配置和操作审计界面。

它不是用户 H5 的扩展：不得导入 `frontend/src`、不得向用户 H5 注册后台路由，也不得读取数据库或服务端源码。所有数据只能通过公开的 `/api/v1/admin/*` HTTP 合约取得；最终授权始终由后端读取 PostgreSQL 当前角色决定。

当前目录只包含实施前的架构合同。构建配置、依赖锁、应用入口和功能代码由 Phase 6 已批准计划按顺序创建。

## 允许依赖

- React、TypeScript、Vite、React Router 和 TanStack Query：独立 SPA、路由与服务端状态。
- Tailwind CSS、官方 shadcn/Base UI registry、Lucide：后台视觉原语；不得增加第二套组件库或图表库。
- React Hook Form、Zod：表单体验和 HTTP DTO 运行时校验；FastAPI 仍是输入与权限的权威。
- Vitest、Testing Library、MSW、Playwright：组件、公开 API 合约与真实浏览器路径验证。

禁止依赖 `frontend/src`、后端 Python 模块、数据库客户端、服务端密钥、Provider SDK 或 Next.js 运行时。access token 仅可位于运行时内存，refresh token 只能由 HttpOnly Cookie 承载。

## 文件索引

| 路径 | 职责 |
|---|---|
| `README.md` | 目录职责、允许依赖与文件索引 |
| `AGENTS.md` | 管理后台局部实现、安全、测试和文档约束 |
| `ARCHITECTURE.md` | 独立后台的模块地图、依赖方向、新代码落点与变更门禁 |

## 实施顺序

实施从已批准的 [Phase 6 计划](../.planning/phases/06-user-dashboard-admin/) 开始。先建立锁定的 Vite 供应链与独立入口，再创建认证壳、严格 API 客户端和各功能模块；不得跳过计划直接手写后台页面。
