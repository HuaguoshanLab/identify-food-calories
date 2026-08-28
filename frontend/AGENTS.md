# Frontend Development Guidelines

本文件只细化根 `AGENTS.md`，不能放宽根级架构、安全、测试或目录文档约束。

## Architecture

- 这是独立 React + TypeScript + Vite SPA，不得引入 Next.js 或后端运行时代码。
- 只依赖 FastAPI 的公开 `/api/v1` 合约；不得读取数据库、服务端密钥或内部模型。
- 服务端状态由 TanStack Query 管理，表单由 React Hook Form + Zod 校验。
- access token 后续只能保存在运行时内存；refresh token 只能由 HttpOnly Cookie 管理。

## Testing

- 用户可见行为使用 Vitest、Testing Library 与 MSW。
- 关键跨栈流程使用 Playwright；测试必须自行启动和清理所需进程。
- 每次完成用户可见的页面、表单、路由、上传或可视化改动后，必须用 Codex 内置浏览器按真实用户路径验收至少一次；不能只凭组件测试、API 响应或静态截图宣称 UI 可用。
- 浏览器验收必须走前端页面与真实公开 API，覆盖成功路径及与本次改动相关的错误/空态；在交付说明中记录访问地址、路径和观察结果。
- 不得把真实模型或云服务调用放入 PR 测试。

## Documentation

- 新增目录时必须同次增加 README，写明职责、允许依赖和文件索引。
- 文件增删时同步维护本目录和父目录索引。
