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
| `auth-helpers.ts` | 仅通过页面与公开 Mailpit HTTP 创建、验证、登录和恢复隔离测试账号的复用夹具 |
| `auth-skeleton.spec.ts` | 从 Mailpit 取真实验证码的注册、恢复、会话撤销与登出浏览器证据 |
| `h5-visual.spec.ts` | 430px 八张视觉基线、Phase 2 文字分析与 Phase 3 图片估算 candidate，以及 320px/桌面、键盘、历史和滚动边界回归 |
| `h5-visual.spec.ts-snapshots/` | Git 维护的八张 H5 视觉基线与其安全更新合同 |
| `agent.spec.ts` | 真实注册登录后的文字 Agent 纵向报告、SSE 公开路径、刷新同线程恢复与图片 multipart 估算报告。 |
