# Frontend

## 职责

`frontend/` 是独立的 React + TypeScript + Vite 用户端 SPA。当前运行壳只展示 FastAPI 健康状态；认证、Agent 对话和饮食规划将在后续计划接入。

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

生产构建使用 `npm run build`。浏览器通过 `http://127.0.0.1:8000/api/v1` 访问本地 FastAPI；后续 Vite 配置计划会统一开发代理和静态检查。

## 文件索引

| 路径 | 职责 |
|---|---|
| `AGENTS.md` | 前端架构、安全、测试和文档细则 |
| `package.json` | 固定命令与受审核依赖清单 |
| `package-lock.json` | npm 完整依赖锁与完整性摘要 |
| `index.html` | Vite HTML 入口 |
| `src/` | React 运行时代码与目录契约 |
| `tests/` | 前端测试边界与 Playwright E2E 用例 |
