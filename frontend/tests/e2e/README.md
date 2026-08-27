# Frontend E2E Tests

## 职责

`tests/e2e/` 通过真实浏览器验证 Vite 页面与 FastAPI API 的跨栈契约。Playwright 配置负责启动依赖、等待 readiness，并在测试结束时清理其拥有的应用进程。

## 允许依赖

- 只使用 `@playwright/test` 和公开 HTTP 合约。
- 基础设施限定为 `postgres-test` 与 Mailpit；不得连接开发数据库或外部服务。
- 禁止固定 `sleep`；所有等待必须基于 HTTP readiness 或可观察页面状态。

## 文件索引

| 文件 | 职责 |
|---|---|
| `health.spec.ts` | Vite、FastAPI 与版本化健康端点的最小全栈证明 |
| `auth-skeleton.spec.ts` | 从 Mailpit 取真实验证码的注册、恢复、会话撤销与登出浏览器证据 |
