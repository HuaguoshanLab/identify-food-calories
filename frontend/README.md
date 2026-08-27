# Frontend

## 职责

`frontend/` 是独立的 React + TypeScript + Vite 用户端 SPA。当前提供产品落地页、隐私/条款与认证入口路由；完整认证生命周期、Agent 对话和饮食规划按后续计划接入。后台是 Phase 6 的独立 `admin-frontend/` 项目，本用户 H5 不创建后台目录、路由或调用。

## 允许依赖

- React、React Router 与 TanStack Query 负责页面、路由和服务端状态。
- React Hook Form、Zod 与 `@hookform/resolvers` 负责客户端表单体验；FastAPI 始终是输入校验权威。
- Tailwind CSS、shadcn、Base UI 与 Lucide 是批准的 UI 工具。
- Vitest、Testing Library、MSW 与 Playwright 负责前端和跨栈测试。
- 禁止导入 backend 源码、数据库客户端、服务端密钥或 Next.js 运行时。

## 本地运行

```bash
npm ci
npm run dev
```

生产构建使用 `npm run build`。浏览器通过 `http://127.0.0.1:8000/api/v1` 访问本地 FastAPI。提交前执行完整前端门禁：

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

Vite 同时运行 React 与 Tailwind CSS v4 插件；Vitest 使用 jsdom 和 Testing Library 验证用户可见行为。

健康 E2E 不要求手工启动服务：

```bash
npm run test:e2e -- --grep "full-stack health"
```

Playwright 会启动隔离的 `postgres-test` 与 Mailpit、在 Alembic 配置存在时迁移测试库，并以固定 test 环境启动 FastAPI 和 Vite preview。应用进程由 Playwright 进程组清理；Docker 测试服务可被后续用例安全复用。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 前端架构、安全、测试和文档细则 |
| `package.json` | 固定命令与受审核依赖清单 |
| `package-lock.json` | npm 完整依赖锁与完整性摘要 |
| `eslint.config.js` | TypeScript、React Hooks 与 Vite 刷新边界静态检查 |
| `tsconfig.json` | 浏览器源码与测试共用的严格 TypeScript 配置 |
| `vite.config.ts` | React、Tailwind CSS 与 Vitest 的统一构建配置 |
| `index.html` | Vite HTML 入口 |
| `components.json` | shadcn 官方 Base UI registry、样式入口与路径 aliases |
| `playwright.config.ts` | 确定性的基础设施、FastAPI 与 Vite E2E 生命周期 |
| `src/` | React 运行时代码与目录契约 |
| `tests/` | 前端测试边界与 Playwright E2E 用例 |
