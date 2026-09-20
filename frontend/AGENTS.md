# Frontend Development Guidelines

本文件只细化根 `AGENTS.md`，不能放宽根级架构、安全、测试或目录文档约束。

## Architecture

- 这是独立 React + TypeScript + Vite SPA，不得引入 Next.js 或后端运行时代码。
- 只依赖 FastAPI 的公开 `/api/v1` 合约；不得读取数据库、服务端密钥或内部模型。
- 服务端状态由 TanStack Query 管理，表单由 React Hook Form + Zod 校验。
- access token 后续只能保存在运行时内存；refresh token 只能由 HttpOnly Cookie 管理。
- `ARCHITECTURE.md` 是前端目录、依赖方向和新代码落点的强制合同。新增页面、API、传输层或共享组件前必须先按该文件选择目录；不允许创建无所有者的全局 `utils/`、`services/`、`hooks/` 或 `types/` 目录。
- `App.tsx` 只登记和组合路由；`layouts/` 只管理页面壳；业务代码归入 `features/<feature>/`，认证代码归入 `auth/`，非领域“我的”内容归入 `app/`。
- feature 之间默认隔离。禁止导入其他 feature 的组件、内部状态或私有类型；唯一允许的跨 feature 依赖是具名公开 `api/` 边界，并且必须在相关 README 中登记原因。

## Testing

- 用户可见行为使用 Vitest、Testing Library 与 MSW。
- 关键跨栈流程使用 Playwright；测试必须自行启动和清理所需进程。
- 每次完成用户可见的页面、表单、路由、上传或可视化改动后，必须用 Codex 内置浏览器按真实用户路径验收至少一次；不能只凭组件测试、API 响应或静态截图宣称 UI 可用。
- 浏览器验收必须走前端页面与真实公开 API，覆盖成功路径及与本次改动相关的错误/空态；在交付说明中记录访问地址、路径和观察结果。
- 不得把真实模型或云服务调用放入 PR 测试。

## Documentation

- 只有新建业务 feature 根目录时必须增加 README。约定俗成的 `api/`、`components/`、`tests/` 子目录不强制单独 README。
- README 仅维护稳定责任、关键入口和例外依赖；普通文件增删不连锁更新多级索引。

## H5 UI Contract

- 修改用户 H5 的页面、组件、布局或样式前，必须先阅读 `../docs/ui/h5-design-guidelines.md`，并将其作为实现与验收基线。
- 不得以局部页面的临时便利为由突破其中关于四 Tab、页面壳、唯一滚动区、安全区、语义色 token、触控尺寸和可访问性的约束。
- UI 规范定义的是设计决策而非运行时代码；实施时应优先把可复用规则沉淀为 token 与基础组件，避免散落的硬编码样式。
