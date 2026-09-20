# Admin Frontend Development Guidelines

本文件只细化根 `AGENTS.md`，不能放宽根级架构、安全、测试或目录文档约束。

## 架构

- `admin-frontend/` 是独立 React + TypeScript + Vite SPA，不是用户 H5 子项目；禁止导入 `../frontend/src`、后端模块或数据库客户端。
- `ARCHITECTURE.md` 是后台目录、依赖方向、新代码落点和跨 feature 依赖的强制合同。新增页面、API 客户端、共享组件或目录前必须先阅读它。
- 后台只能调用公开 `/api/v1/admin/*`；前端路由守卫、菜单隐藏和按钮禁用不构成授权，后端数据库 RBAC 才是唯一授权真相。
- 访问令牌仅保留在内存；不得写入 localStorage、sessionStorage、IndexedDB 或可读 Cookie。刷新凭据只由 HttpOnly Cookie 管理。
- 每个功能的 HTTP 请求与 Zod DTO 都归入自身 `features/<feature>/api/`；页面不得直接 `fetch` 或相信未经运行时校验的响应。

## 安全与数据最小化

- 不展示、缓存或记录密钥、Provider 原文、用户邮箱、原图、用户原文、完整 Graph State 或模型思维链。
- 运行详情只能使用后端提供的工具名、耗时、费用、调用数、失败码和安全摘要。
- 所有会改变目录、Provider 启停或配置版本的动作都必须显示原因和后端返回的可审计结果；前端不能伪造成功状态。
- 生产构建必须显式提供受验证的 `VITE_ADMIN_API_BASE_URL`，且它只能落在公开 `/api/v1/admin` 边界；禁止回退到用户 H5 API base、HTTP URL 或任意第三方地址。
- 依赖只允许本项目已审查并锁定的包。使用 `npm ci` 安装；不得以 `npx` 临时下载组件、脚手架或依赖。

## 测试与文档

- 组件行为使用 Vitest、Testing Library 与 MSW；跨栈路径使用 Playwright。
- 页面、表单、路由、图表或跨栈交互完成后，必须经真实公开 API 在 Codex 内置浏览器验证；不得通过直写数据库、伪造 token 或截图替代。
- 只有新建后台 feature 根目录时必须增加 README。常规 `api/`、`components/`、`tests/` 子目录和普通文件增删不强制创建或连锁更新索引。
